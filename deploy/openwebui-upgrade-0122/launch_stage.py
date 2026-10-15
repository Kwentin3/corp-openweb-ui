"""Validate and start only the isolated, loopback-bound release candidate."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time
import sqlite3

BASE_ROOT = Path('/opt/openwebui-upgrade-0122')
COMPOSE = BASE_ROOT / 'compose/openwebui.release-0122.compose.yml'
SOURCE_ROLES = ('webui', 'office', 'stt', 'terminal')
ENV_SELECTORS = {'RELEASE_WEBUI_ENV_FILE': 'webui.env',
                 'RELEASE_STT_ENV_FILE': 'stt.env',
                 'RELEASE_TERMINAL_ENV_FILE': 'terminal.env'}
VOLUME_SELECTORS = {'RELEASE_DATA_VOLUME': 'data',
                    'RELEASE_STT_DATA_VOLUME': 'stt_data',
                    'RELEASE_TERMINAL_HOME_VOLUME': 'terminal_home'}


def validate_prepared(root, prepared, approved):
    expected_sources = {role: {'id': approved[role]['Id'], 'image': approved[role]['Image']}
                        for role in SOURCE_ROLES}
    if (prepared.get('source_container') != approved['webui']['Id']
            or prepared.get('source_image') != approved['webui']['Image']):
        raise RuntimeError('Prepared snapshot has a different approved source identity')
    if 'phase_root' in prepared:
        if prepared['phase_root'] != str(root):
            raise RuntimeError('Prepared snapshot belongs to a different phase root')
        if prepared.get('source_containers') != expected_sources:
            raise RuntimeError('Prepared source container/image identities changed')
    else:
        legacy_volumes = {name: 'openwebui-0122_' + name for name in VOLUME_SELECTORS.values()}
        if (root != BASE_ROOT or prepared.get('volumes') != legacy_volumes
                or prepared.get('source_stopped', False)
                or ('source_containers' in prepared and prepared['source_containers'] != expected_sources)):
            raise RuntimeError('Only the original default snapshot may omit phase_root')
    if set(prepared['volumes']) != set(VOLUME_SELECTORS.values()):
        raise RuntimeError('Prepared snapshot must bind exactly the three candidate volumes')


def read_private_env(path):
    metadata = path.lstat()
    if (not stat.S_ISREG(metadata.st_mode) or path.resolve(strict=True) != path
            or stat.S_IMODE(metadata.st_mode) != 0o600 or metadata.st_uid != os.geteuid()):
        raise RuntimeError('Environment must be an owned mode-0600 regular file without symlinks: ' + path.name)
    result = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if not separator or re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key) is None or key in result:
            raise RuntimeError('Unexpected or duplicate raw environment key in ' + path.name)
        result[key] = value
    return result


def validate_environment(root, prepared):
    compose = read_private_env(root / 'compose.env')
    selectors = {}
    for key, filename in ENV_SELECTORS.items():
        path = root / filename
        if compose.get(key) != str(path):
            raise RuntimeError('Environment selector belongs to a different phase root: ' + key)
        values = read_private_env(path)
        if filename == 'webui.env' and {'WEBUI_BUILD_HASH', 'WEBUI_BUILD_CHANNEL'} & values.keys():
            raise RuntimeError('Prepared WebUI environment must not override candidate image build identity')
        selectors[key] = str(path)
    for key, logical in VOLUME_SELECTORS.items():
        expected = prepared['volumes'][logical]
        if 'phase_root' in prepared:
            if compose.get(key) != expected:
                raise RuntimeError('Volume selector differs from the prepared snapshot: ' + key)
        elif key in compose:
            raise RuntimeError('Original snapshot must retain its native default volume selectors')
        selectors[key] = expected
    return selectors


def main(image, root=BASE_ROOT):
    root = Path(root)
    if (not root.is_absolute() or '..' in root.parts or root.resolve(strict=True) != root
            or not root.is_relative_to(BASE_ROOT) or BASE_ROOT.resolve(strict=True) != BASE_ROOT):
        raise RuntimeError('Use an exact phase root under the task base without symlinks')
    ROOT = root
    os.umask(0o077)
    prepared = json.loads((ROOT / 'prepared.private.json').read_text(encoding='utf-8'))
    approved = json.loads((BASE_ROOT / 'production-inspect.private.json').read_text(encoding='utf-8'))
    validate_prepared(ROOT, prepared, approved)
    selectors = validate_environment(ROOT, prepared)
    assert not prepared.get('booted'), 'Candidate already launched; use a separately reviewed recovery path'
    marker = ROOT / 'launch-started.private.json'
    assert not marker.exists(), 'Candidate launch already attempted; inspect its outcome before retry'
    existing = subprocess.check_output(['docker', 'ps', '-aq', '--filter',
                                       'label=com.docker.compose.project=openwebui-0122'], text=True).strip()
    assert not existing, 'Candidate containers already exist; do not replace them implicitly'
    data_volume = prepared['volumes']['data']
    assert data_volume.startswith('openwebui-0122') and '/' not in data_volume
    data_path = Path('/var/lib/docker/volumes') / data_volume / '_data/webui.db'
    with sqlite3.connect(data_path.as_uri() + '?mode=ro', uri=True) as connection:
        assert connection.execute("SELECT count(*) FROM chat WHERE timer_at IS NOT NULL AND json_extract(meta,'$.status')='pending'").fetchone()[0] == 0
        assert connection.execute('SELECT count(*) FROM calendar_event').fetchone()[0] == 0
        for key in ('events.webhooks', 'webhook_url', 'webhook.url'):
            row = connection.execute('SELECT value FROM config WHERE key=?', (key,)).fetchone()
            value = json.loads(row[0]) if row and isinstance(row[0], str) else row[0] if row else None
            assert not value, 'Copied webhooks must not receive stage startup events'
    for role in SOURCE_ROLES:
        current = json.loads(subprocess.check_output(['docker', 'inspect', approved[role]['Id']]))[0]
        if current['Id'] != approved[role]['Id'] or current['Image'] != approved[role]['Image']:
            raise RuntimeError('Approved source container/image identity changed: ' + role)
        if current['State']['Running'] is not (not prepared.get('source_stopped', False)):
            raise RuntimeError('Approved source running state changed: ' + role)
        if role == 'webui' and not prepared.get('source_stopped'):
            if current['State']['Health']['Status'] != 'healthy':
                raise RuntimeError('Online snapshot requires the healthy production WebUI')
    candidate_image = json.loads(subprocess.check_output(['docker', 'image', 'inspect', image]))[0]
    assert candidate_image['Config']['Labels']['corp.upstream.version'] == '0.12.2'
    assert candidate_image['Config']['Labels']['corp.upstream.commit'] == '6a18585ff4c2e5f6805f682222cfbc46dc669ef8'
    # Compose interpolation otherwise lets ambient shell selectors override --env-file.
    process_env = {**os.environ, **selectors, 'RELEASE_WEBUI_IMAGE': candidate_image['Id']}
    command = ['docker', 'compose', '--env-file', str(ROOT / 'compose.env'), '-f', str(COMPOSE)]
    resolved = subprocess.check_output([*command, 'config', '--format', 'json'], env=process_env)
    config = json.loads(resolved)
    services = config['services']
    assert config['name'] == 'openwebui-0122'
    assert set(services) == {'openwebui-0122', 'officecli-0122', 'stage2-stt-0122', 'open-terminal-0122'}
    for name, service in services.items():
        assert service['labels']['traefik.enable'] == 'false'
        for mount in service.get('volumes', []):
            if mount['type'] == 'volume':
                assert config['volumes'][mount['source']]['name'] in prepared['volumes'].values()
    bindings = {'openwebui-0122': ('data', '/app/backend/data'),
                'stage2-stt-0122': ('stt_data', '/data/stage2-stt'),
                'open-terminal-0122': ('terminal_home', '/home')}
    for name, (logical, target) in bindings.items():
        assert config['volumes'][logical]['name'] == prepared['volumes'][logical]
        mounts = [item for item in services[name].get('volumes', []) if item['type'] == 'volume']
        assert len(mounts) == 1 and mounts[0]['source'] == logical and mounts[0]['target'] == target
    webui = services['openwebui-0122']
    assert webui['image'] == candidate_image['Id']
    assert len(webui['ports']) == 1 and webui['ports'][0]['host_ip'] == '127.0.0.1'
    assert webui['environment']['ENABLE_RESPONSES_API_STATEFUL'] == 'false'
    assert services['officecli-0122']['environment']['OPENWEBUI_BASE_URL'] == 'http://openwebui-0122:8080'
    assert services['officecli-0122']['init'] is True
    with (ROOT / 'resolved-candidate.private.json').open('xb') as stream:
        stream.write(resolved)
    with marker.open('x', encoding='utf-8') as stream:
        json.dump({'image_id': candidate_image['Id'], 'started_at': time.time(),
                   'resolved_compose_sha256': hashlib.sha256(resolved).hexdigest()}, stream)
    with (ROOT / 'compose.env').open('a', encoding='utf-8') as stream:
        stream.write('RELEASE_WEBUI_IMAGE=' + candidate_image['Id'] + '\n')
    subprocess.run([*command, 'up', '-d'], env=process_env, check=True)
    prepared['booted'] = True
    prepared['boot_image_id'] = candidate_image['Id']
    temporary = ROOT / 'prepared.private.tmp'
    temporary.write_text(json.dumps(prepared, indent=2), encoding='utf-8')
    temporary.replace(ROOT / 'prepared.private.json')
    print(json.dumps({'image_id': candidate_image['Id'], 'resolved_compose_sha256': hashlib.sha256(resolved).hexdigest(),
                      'services': sorted(services), 'production_route_enabled': False,
                      'health_and_product_acceptance': 'pending'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--root', type=Path, default=BASE_ROOT)
    args = parser.parse_args()
    main(args.image, args.root)
