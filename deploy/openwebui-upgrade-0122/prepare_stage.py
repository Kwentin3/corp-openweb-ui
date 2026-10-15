"""Prepare an isolated candidate from the inspected production owner, without boot.

Run on the deployment host. Secrets and detailed evidence stay in a mode-0700
directory; stdout contains only safe receipts. Does not stop production services.
"""
from __future__ import annotations

import hashlib
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time

BASE_ROOT = Path('/opt/openwebui-upgrade-0122')
ROOT = BASE_ROOT
DEFAULT_VOLUME_PREFIX = 'openwebui-0122'
SOURCE_IMAGE = 'sha256:665f7fd87fcc43752aa3ffa8c9c85a1ef8e1d142525f367eef3a8d8a29ecb8e8'
NAMES = {'webui': 'openwebui-0114-openwebui-0114-1',
         'stt': 'openwebui-0114-stage2-stt-0114-1',
         'terminal': 'openwebui-0114-open-terminal-0114-1',
         'office': 'openwebui-0114-officecli-0114-1'}
SOURCE_VOLUMES = {'data': 'openwebui-0114_data', 'stt_data': 'openwebui-0114_stt_data',
                  'terminal_home': 'openwebui-0114_terminal_home'}
IMAGE_ENV = {'PATH', 'LANG', 'GPG_KEY', 'PYTHON_VERSION', 'PYTHON_SHA256', 'PYTHONUNBUFFERED',
             'PYTHONDONTWRITEBYTECODE', 'ENV', 'PORT', 'USE_OLLAMA_DOCKER', 'USE_CUDA_DOCKER',
             'USE_SLIM_DOCKER', 'USE_CUDA_DOCKER_VER', 'USE_EMBEDDING_MODEL_DOCKER',
             'USE_RERANKING_MODEL_DOCKER', 'USE_AUXILIARY_EMBEDDING_MODEL_DOCKER', 'HOME',
             'UV_LINK_MODE', 'WEBUI_BUILD_VERSION', 'DOCKER', 'SHELL'}
REWRITES = {'http://officecli-0114:8080': 'http://officecli-0122:8080',
            'http://open-terminal-0114:8000': 'http://open-terminal-0122:8000',
            'http://stage2-stt-0114:8080': 'http://stage2-stt-0122:8080',
            'http://stage2-stt:8080': 'http://stage2-stt-0122:8080'}


def command(args):
    return subprocess.check_output(args, text=True, timeout=90).strip()


def write_private(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        stream.write(value)


def json_private(name, value):
    write_private(ROOT / name, json.dumps(value, ensure_ascii=True, indent=2))


def rewrite(value):
    if isinstance(value, dict):
        return {key: rewrite(child) for key, child in value.items()}
    if isinstance(value, list):
        return [rewrite(child) for child in value]
    if isinstance(value, str):
        for old, new in REWRITES.items():
            if value == old or value.startswith(old + '/'):
                return new + value[len(old):]
    return value


def decode_value(value):
    # SQLite returns native numeric/null JSON scalars directly, text as JSON.
    return json.loads(value) if isinstance(value, (str, bytes, bytearray)) else value


def backup_sqlite(source, target):
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=5)) as incoming:
        with closing(sqlite3.connect(target)) as outgoing, outgoing:
            incoming.backup(outgoing)
            assert outgoing.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


def inventory(root):
    result = []
    uploads = root / 'uploads'
    if uploads.exists():
        for path in sorted(uploads.rglob('*')):
            if path.is_file():
                digest = hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()
                result.append((str(path.relative_to(uploads)), path.stat().st_size, digest))
    return result


def validate_options(root, volume_prefix, resume_config):
    root = Path(root)
    if not root.is_absolute() or '..' in root.parts:
        raise ValueError('Use an absolute phase root without parent traversal')
    root = root.resolve()
    base = BASE_ROOT.resolve()
    if base != BASE_ROOT:
        raise ValueError('Task root must not resolve through a different filesystem location')
    if root != base and not root.is_relative_to(base):
        raise ValueError('Phase root must stay under /opt/openwebui-upgrade-0122')
    if re.fullmatch(r'openwebui-0122(?:-[a-z0-9]+(?:-[a-z0-9]+)*)?', volume_prefix) is None:
        raise ValueError('Volume prefix must be openwebui-0122 or openwebui-0122-<phase>')
    if resume_config and (root != base or volume_prefix != DEFAULT_VOLUME_PREFIX):
        raise ValueError('Configuration-only resume belongs to the original default snapshot')
    if root != base and root.exists():
        raise ValueError('Phase root already exists; do not overwrite QA or recovery data')
    return root, {suffix: volume_prefix + '_' + suffix for suffix in SOURCE_VOLUMES}


def validate_source(inspections, *, source_stopped=False, resume_config=False):
    if inspections['webui']['Image'] != SOURCE_IMAGE:
        raise RuntimeError('Production image identity changed')
    original_path = BASE_ROOT / 'production-inspect.private.json'
    if original_path.exists():
        approved = json.loads(original_path.read_text(encoding='utf-8'))
        for role in NAMES:
            if any(inspections[role][key] != approved[role][key] for key in ('Id', 'Image')):
                raise RuntimeError('Approved source container/image identity changed: ' + role)
    elif source_stopped or resume_config or ROOT != BASE_ROOT:
        raise RuntimeError('Original approved production identity is required for this phase')
    if source_stopped:
        if any(item['State']['Running'] is not False for item in inspections.values()):
            raise RuntimeError('Source-stopped snapshot requires all four source containers stopped')
    else:
        if any(item['State']['Running'] is not True for item in inspections.values()):
            raise RuntimeError('Online snapshot requires all four source containers running')
        if inspections['webui']['State']['Health']['Status'] != 'healthy':
            raise RuntimeError('Online snapshot requires the healthy production WebUI')


def validate_target_volumes(names, *, resume_config=False):
    # A successful native listing distinguishes absence from an inspection failure.
    existing = set(command(['docker', 'volume', 'ls', '--format', '{{.Name}}']).splitlines())
    selected = set(names.values())
    if resume_config:
        if not selected.issubset(existing) or not (ROOT / 'source-webui.sqlite3').is_file():
            raise RuntimeError('Configuration-only resume requires the original complete snapshot')
    elif selected & existing:
        raise RuntimeError('Target volume already exists; do not overwrite QA or recovery data')


def candidate_cors(value):
    # Native CORS uses semicolons. Keep every production origin and add only
    # the exact candidate origin; never broaden the environment to a wildcard.
    origins = [origin.strip() for origin in value.split(';') if origin.strip()]
    if not origins or '*' in origins:
        raise RuntimeError('Expected explicit production CORS origins before adding the candidate origin')
    candidate_origin = 'http://127.0.0.1:18122'
    if candidate_origin not in origins:
        origins.append(candidate_origin)
    return ';'.join(origins)


def main(*, root=BASE_ROOT, volume_prefix=DEFAULT_VOLUME_PREFIX, source_stopped=False, resume_config=False):
    global ROOT
    started = time.monotonic()
    ROOT, target_names = validate_options(root, volume_prefix, resume_config)
    os.umask(0o077)
    if (ROOT / 'prepared.private.json').exists():
        raise RuntimeError('Candidate already prepared; inspect the existing receipt before any refresh')
    inspections = {role: json.loads(command(['docker', 'inspect', name]))[0] for role, name in NAMES.items()}
    validate_source(inspections, source_stopped=source_stopped, resume_config=resume_config)
    existing = command(['docker', 'ps', '-a', '--filter', 'label=com.docker.compose.project=openwebui-0122', '-q'])
    assert not existing, 'Candidate containers already exist'
    validate_target_volumes(target_names, resume_config=resume_config)
    ROOT.mkdir(mode=0o700, parents=True, exist_ok=ROOT == BASE_ROOT)
    os.chmod(ROOT, 0o700)
    if resume_config:
        preserved = json.loads((ROOT / 'production-inspect.private.json').read_text())
        assert preserved['webui']['Id'] == inspections['webui']['Id']
    else:
        json_private('production-inspect.private.json', inspections)

    envs = {}
    aliases = ','.join(['openwebui-0122', 'officecli-0122', 'stage2-stt-0122',
                        'open-terminal-0122', 'google-gateway-0122'])
    for role in ('webui', 'stt', 'terminal'):
        env = dict(entry.split('=', 1) for entry in inspections[role]['Config']['Env'] if '=' in entry)
        env = {key: value for key, value in env.items() if key not in IMAGE_ENV}
        for key in ('NO_PROXY', 'no_proxy'):
            if key in env or role != 'terminal':
                env[key] = ','.join(filter(None, [env.get(key, ''), aliases]))
        envs[role] = env
    envs['webui'].update(WEBUI_URL='http://127.0.0.1:18122',
                          STAGE2_STT_BASE_URL='http://stage2-stt-0122:8080',
                          ENABLE_AUTOMATIONS='false', ENABLE_RESPONSES_API_STATEFUL='false',
                          ENABLE_DB_MIGRATIONS='true', DATA_DIR='/app/backend/data',
                          DATABASE_URL='sqlite:////app/backend/data/webui.db',
                          STORAGE_PROVIDER='local', VECTOR_DB='chroma', CHROMA_HTTP_HOST='',
                          REDIS_URL='', WEBSOCKET_MANAGER='', WEBSOCKET_REDIS_URL='')
    candidate_origin = 'http://127.0.0.1:18122'
    envs['webui']['CORS_ALLOW_ORIGIN'] = candidate_cors(envs['webui'].get('CORS_ALLOW_ORIGIN', ''))
    for role, env in envs.items():
        if any('\n' in value or '\r' in value for value in env.values()):
            raise RuntimeError('Unexpected multiline environment; use native structured environment handling')
        if not resume_config:
            write_private(ROOT / (role + '.env'), ''.join(key + '=' + value + '\n' for key, value in sorted(env.items())))

    paths, source_paths = {}, {}
    for suffix, source_name in SOURCE_VOLUMES.items():
        target_name = target_names[suffix]
        assert source_name != target_name
        if not resume_config:
            command(['docker', 'volume', 'create', '--label', 'com.docker.compose.project=openwebui-0122',
                     '--label', 'com.docker.compose.volume=' + suffix, target_name])
        source = Path(json.loads(command(['docker', 'volume', 'inspect', source_name]))[0]['Mountpoint'])
        target = Path(json.loads(command(['docker', 'volume', 'inspect', target_name]))[0]['Mountpoint'])
        assert target.resolve() == Path('/var/lib/docker/volumes') / target_name / '_data'
        assert source.resolve() == Path('/var/lib/docker/volumes') / source_name / '_data'
        paths[suffix] = target
        source_paths[suffix] = source
        if not resume_config:
            assert not any(target.iterdir()), 'New target volume is not empty'

    snapshot_started_at = time.time()
    snapshot_started = time.monotonic()
    for suffix, target in paths.items():
        if resume_config:
            break
        source = source_paths[suffix]
        copy = ['rsync', '-a', '--exclude=webui.db', '--exclude=webui.db-wal', '--exclude=webui.db-shm',
                '--exclude=artifacts.sqlite3', '--exclude=artifacts.sqlite3-wal', '--exclude=artifacts.sqlite3-shm',
                str(source) + '/', str(target) + '/']
        command(copy)
        database_name = {'data': 'webui.db', 'stt_data': 'artifacts.sqlite3'}.get(suffix)
        if database_name and (source / database_name).is_file():
            backup_sqlite(source / database_name, target / database_name)
        if suffix == 'data':
            # A second assets pass includes files which appeared during online DB backup.
            command(copy)
            baseline = inventory(source)
            copied = inventory(target)
            assert baseline == copied, 'Source assets changed; retry snapshot before candidate boot'
            json_private('uploads-source.private.json', baseline)
            json_private('uploads-candidate.private.json', copied)

    database = paths['data'] / 'webui.db'
    if resume_config:
        copied = json.loads((ROOT / 'uploads-candidate.private.json').read_text())
        assert [list(item) for item in inventory(paths['data'])] == copied
        with closing(sqlite3.connect(database)) as target, closing(sqlite3.connect(ROOT / 'source-webui.sqlite3')) as source:
            for table in ('config', 'function'):
                assert target.execute('SELECT * FROM "' + table + '"').fetchall() == source.execute('SELECT * FROM "' + table + '"').fetchall(), 'Candidate changed since snapshot'
    else:
        backup_sqlite(database, ROOT / 'source-webui.sqlite3')
    timing_path = ROOT / 'snapshot-timing.private.json'
    if resume_config:
        snapshot_timing = json.loads(timing_path.read_text(encoding='utf-8')) if timing_path.exists() else {
            'snapshot_started_at': None, 'snapshot_finished_at': None, 'snapshot_elapsed_seconds': None,
        }
    else:
        snapshot_timing = {'snapshot_started_at': snapshot_started_at, 'snapshot_finished_at': time.time(),
                           'snapshot_elapsed_seconds': round(time.monotonic() - snapshot_started, 3)}
        json_private('snapshot-timing.private.json', snapshot_timing)
    with closing(sqlite3.connect(database)) as connection, connection:
        baseline_counts = {table: connection.execute('SELECT count(*) FROM "' + table + '"').fetchone()[0]
                           for table in ('user', 'auth', 'chat', 'chat_message', 'file', 'function', 'model', 'tool', 'skill')}
        revision = connection.execute('SELECT version_num FROM alembic_version').fetchone()[0]
        pending = connection.execute("SELECT count(*) FROM file WHERE json_extract(data,'$.stage2_video_intake.state') IS NOT NULL AND json_extract(data,'$.stage2_video_intake.state') NOT IN ('completed','failed')").fetchone()[0]
        assert pending == 0, 'Do not resume pending copied media before explicit review'
        pending_timers = connection.execute("SELECT count(*) FROM chat WHERE timer_at IS NOT NULL AND json_extract(meta,'$.status')='pending'").fetchone()[0]
        assert pending_timers == 0, 'Copied timers are independent of the automations switch'
        calendar_events = connection.execute('SELECT count(*) FROM calendar_event').fetchone()[0]
        assert calendar_events == 0, 'Review copied calendar reminders before boot'
        assert connection.execute("SELECT count(*) FROM file WHERE path NOT LIKE '/app/backend/data/%' AND path IS NOT NULL").fetchone()[0] == 0
        config_changes = []
        for key, value in connection.execute('SELECT key,value FROM config').fetchall():
            parsed = decode_value(value)
            updated = rewrite(parsed)
            if key == 'automations.enable':
                updated = False
            if key == 'webui.url':
                updated = 'http://127.0.0.1:18122'
            if key == 'events.webhooks':
                updated = []
            if key in {'webhook_url', 'webhook.url'}:
                updated = ''
            if parsed != updated:
                connection.execute('UPDATE config SET value=? WHERE key=?', (json.dumps(updated), key))
                config_changes.append(key)
        valve_changes = []
        for fid, valves in connection.execute('SELECT id,valves FROM function WHERE valves IS NOT NULL').fetchall():
            parsed = decode_value(valves)
            updated = rewrite(parsed)
            if parsed != updated:
                connection.execute('UPDATE function SET valves=? WHERE id=?', (json.dumps(updated), fid))
                valve_changes.append(fid)
        # Keep its copied registry present; native enable follows callback/storage qualification.
        connection.execute("UPDATE function SET is_active=0 WHERE id='stage2_media_intake'")
        connection.commit()
        assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'

    compose_env = {
        'OPENWEBUI_HOST': 'gpt.alpha-soft.ru',
        'RELEASE_WEBUI_ENV_FILE': str(ROOT / 'webui.env'),
        'RELEASE_STT_ENV_FILE': str(ROOT / 'stt.env'),
        'RELEASE_TERMINAL_ENV_FILE': str(ROOT / 'terminal.env'),
        'RELEASE_WEBUI_NO_PROXY': envs['webui']['NO_PROXY'],
        'RELEASE_STT_NO_PROXY': envs['stt']['NO_PROXY'],
        'RELEASE_DATA_VOLUME': target_names['data'],
        'RELEASE_STT_DATA_VOLUME': target_names['stt_data'],
        'RELEASE_TERMINAL_HOME_VOLUME': target_names['terminal_home'],
    }
    write_private(ROOT / 'compose.env', ''.join(key + '=' + value + '\n' for key, value in compose_env.items()))
    receipt = {'source_image': SOURCE_IMAGE, 'source_container': inspections['webui']['Id'],
               'source_containers': {role: {'id': item['Id'], 'image': item['Image']}
                                     for role, item in inspections.items()},
               'source_stopped': source_stopped, 'phase_root': str(ROOT),
               'cors_origin_override': {'origin': candidate_origin, 'written_this_phase': not resume_config,
                                        'source_origins_preserved': True,
                                        'restore_public_only_before_route': True},
               'source_revision': revision, 'source_counts': baseline_counts,
               'upload_files': len(copied), 'uploads_sha256': hashlib.sha256(json.dumps(copied).encode()).hexdigest(),
               'pending_media_rows': pending, 'config_override_keys': config_changes,
               'pending_chat_timers': pending_timers, 'calendar_event_rows': calendar_events,
               'valve_override_functions': valve_changes, 'media_event_temporarily_disabled': True,
               'volumes': {key: path.parent.name for key, path in paths.items()},
               'phase': 'configuration-only-resume' if resume_config else 'full-snapshot',
               **snapshot_timing,
               'phase_elapsed_seconds': round(time.monotonic() - started, 3), 'booted': False}
    json_private('prepared.private.json', receipt)
    print(json.dumps(receipt))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=BASE_ROOT, help='Fresh phase directory under the task root')
    parser.add_argument('--volume-prefix', default=DEFAULT_VOLUME_PREFIX, help='Unique task-owned volume prefix')
    parser.add_argument('--source-stopped', action='store_true', help='Require all approved source containers stopped')
    parser.add_argument('--resume-config', action='store_true', help='Finish only a verified unbooted snapshot')
    args = parser.parse_args()
    main(root=args.root, volume_prefix=args.volume_prefix, source_stopped=args.source_stopped,
         resume_config=args.resume_config)
