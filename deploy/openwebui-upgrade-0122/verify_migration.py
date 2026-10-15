#!/usr/bin/env python3
"""Compare the first healthy candidate with its preserved, pre-stage SQLite copy.

Run before login or QA changes. Databases are opened read-only/query-only; the
only optional write is a new mode-0600 report in an existing private directory.
Stdout contains counts and verdicts, never row contents, IDs, paths or secrets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import time

sys.dont_write_bytecode = True
from prepare_stage import decode_value, rewrite

OLD_REVISION = 'd4c1a8e37b62'
NEW_REVISION = '0bd252b206fb'
CORE_TABLES = ('user', 'auth', 'chat', 'chat_message', 'file', 'model', 'tool', 'skill', 'function', 'config')
OPTIONAL_TABLES = ('access_grant', 'group', 'group_member', 'chat_file')
STAGE_CONFIG = {'tool_server.connections', 'terminal_server.connections', 'webui.url', 'automations.enable'}
NEW_TABLES = {'app', 'skill_history', 'model_history', 'tool_history', 'function_history'}
NEW_COLUMNS = {'auth': {'mfa', 'session_stamp'}, 'group': {'parent_group_id'},
               'skill': {'version_id', 'data'}, 'model': {'version_id'},
               'tool': {'version_id'}, 'function': {'version_id'}}
# Exact config.py defaults at upstream 6a18585, not a blanket allowance for
# startup writes. Different/new configuration remains an explicit mismatch.
NEW_CONFIG_DEFAULTS = {
    'web.search.tavily_search_depth': 'basic',
    'audio.realtime.enabled': False,
    'audio.realtime.provider': 'openai',
    'audio.realtime.auth_type': 'api_key',
    'audio.realtime.openai.api_base_url': 'https://api.openai.com/v1',
    'audio.realtime.openai.api_key': '',
    'audio.realtime.model': 'gpt-realtime-2.1-mini',
    'audio.realtime.voice': 'marin',
    'audio.realtime.transcription_model': 'gpt-transcribe',
    'audio.realtime.input_params': None,
    'audio.realtime.prompt_template': None,
    'audio.tts.realtime.prompt_template': None,
    'apps.enable': False,
    'chat.tool_search.enable': False,
    'chat.tool_search.defer_threshold': 400,
    'chat.tool_search.always_loaded': [],
    'chat.tool_search.defer_builtin_tools': True,
    'auth.mfa.enable': False,
    'auth.mfa.allow_oauth_bypass': False,
    'auth.mfa.allow_trusted_header_bypass': False,
}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, sort_keys=True, default=str).encode()).hexdigest()


def file_digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def identifier(name):
    return '"' + name.replace('"', '""') + '"'


def readonly(path, memory_snapshot=False):
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)
    connection.execute('PRAGMA query_only=ON')
    if memory_snapshot:
        # Native backup includes the committed WAL and makes a consistent read
        # snapshot. Check its pages in RAM instead of random disk reads during
        # integrity_check; the live database remains read-only.
        snapshot = sqlite3.connect(':memory:')
        try:
            connection.backup(snapshot)
        except BaseException:
            snapshot.close()
            raise
        finally:
            connection.close()
        connection = snapshot
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA query_only=ON')
    connection.execute('BEGIN')
    return connection


def table_names(connection):
    return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def columns(connection, table):
    return list(connection.execute('PRAGMA table_info(' + identifier(table) + ')'))


def rows(connection, table, names, keys):
    records = connection.execute('SELECT ' + ','.join(map(identifier, names)) + ' FROM ' + identifier(table))
    result = {}
    for row in records:
        key = tuple(row[name] for name in keys)
        if key in result:
            raise ValueError('A compared table has duplicate row identities')
        result[key] = dict(row)
    return result


def expected_row(table, source, config_keys, valve_ids):
    result = dict(source)
    if table == 'config' and source['key'] in config_keys:
        value = rewrite(decode_value(source['value']))
        if source['key'] == 'webui.url':
            value = 'http://127.0.0.1:18122'
        elif source['key'] == 'automations.enable':
            value = False
        result['value'] = json.dumps(value)
    if table == 'function':
        if source['id'] in valve_ids:
            result['valves'] = json.dumps(rewrite(decode_value(source['valves'])))
        if source['id'] == 'stage2_media_intake':
            result['is_active'] = 0
    return result


def verify(source_path, candidate_path, receipt_path, *, memory_snapshot=False):
    started = time.monotonic()
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    details = {'mismatches': [], 'unmanifested_uploads': [], 'new_tables': [], 'new_columns': {}}
    summary = {'ok': False, 'tables': {}, 'database_checks': {}, 'files': {}, 'mismatch_count': 0}

    def mismatch(kind, **location):
        details['mismatches'].append({'kind': kind, **location})

    config_keys = set(receipt['config_override_keys'])
    valve_ids = set(receipt['valve_override_functions'])
    if not config_keys <= STAGE_CONFIG:
        mismatch('unrecognized_receipt_config_overrides')
    if receipt.get('media_event_temporarily_disabled') is not True:
        mismatch('missing_media_event_override_contract')
    if source_path.resolve() == candidate_path.resolve():
        raise ValueError('Source and candidate must differ')

    source = readonly(source_path, memory_snapshot)
    candidate = readonly(candidate_path, memory_snapshot)
    try:
        foreign_key_sets = {}
        for role, connection, expected_revision in (
            ('source', source, OLD_REVISION), ('candidate', candidate, NEW_REVISION)
        ):
            revision = [row[0] for row in connection.execute('SELECT version_num FROM alembic_version')]
            integrity = list(connection.execute('PRAGMA integrity_check'))
            foreign_keys = list(connection.execute('PRAGMA foreign_key_check'))
            foreign_key_sets[role] = {tuple(row) for row in foreign_keys}
            summary['database_checks'][role] = {
                'revision_ok': revision == [expected_revision],
                'integrity_ok': [row[0] for row in integrity] == ['ok'],
                'foreign_key_violations': len(foreign_keys),
            }
            if revision != [expected_revision]:
                mismatch('revision', database=role, actual_sha256=digest(revision))
            if [row[0] for row in integrity] != ['ok']:
                mismatch('integrity', database=role)
        # Preserve inherited inconsistencies exactly; migration must not add or
        # silently remove an orphan. A pre-existing orphan is not an upgrade
        # regression and this operation does not repair unrelated source data.
        for row in foreign_key_sets['candidate'] - foreign_key_sets['source']:
            mismatch('new_foreign_key', table=row[0], rowid=row[1], parent=row[2], fk=row[3])
        for row in foreign_key_sets['source'] - foreign_key_sets['candidate']:
            mismatch('removed_foreign_key', table=row[0], rowid=row[1], parent=row[2], fk=row[3])
        summary['inherited_foreign_keys_unchanged'] = foreign_key_sets['source'] == foreign_key_sets['candidate']
        if receipt.get('source_revision') != OLD_REVISION:
            mismatch('receipt_source_revision')

        source_tables, candidate_tables = table_names(source), table_names(candidate)
        details['new_tables'] = sorted(candidate_tables - source_tables)
        for table in candidate_tables - source_tables - NEW_TABLES:
            mismatch('unrecognized_new_table', table=table)
        tables = list(CORE_TABLES) + [name for name in OPTIONAL_TABLES if name in source_tables]
        source_users = {row['id']: row['email'] for row in source.execute('SELECT id,email FROM user')}
        source_auth_ids = {row['id'] for row in source.execute('SELECT id FROM auth')}
        expected_auth_ids = set(source_users) - source_auth_ids
        seen_valves, seen_config, seen_media_event = set(), set(), False

        for table in tables:
            if table not in source_tables or table not in candidate_tables:
                mismatch('missing_table', table=table)
                continue
            source_columns = columns(source, table)
            source_names = [row['name'] for row in source_columns]
            candidate_names = {row['name'] for row in columns(candidate, table)}
            missing_columns = set(source_names) - candidate_names
            details['new_columns'][table] = sorted(candidate_names - set(source_names))
            unexpected_columns = candidate_names - set(source_names) - NEW_COLUMNS.get(table, set())
            if unexpected_columns:
                mismatch('unrecognized_new_columns', table=table, columns=sorted(unexpected_columns))
            if missing_columns:
                mismatch('missing_columns', table=table, columns=sorted(missing_columns))
                continue
            keys = [row['name'] for row in sorted(source_columns, key=lambda row: row['pk']) if row['pk']]
            if not keys:
                raise ValueError('A compared table has no primary key')
            original = rows(source, table, source_names, keys)
            migrated = rows(candidate, table, source_names, keys)
            missing = set(original) - set(migrated)
            added = set(migrated) - set(original)
            counts = {'source': len(original), 'candidate': len(migrated), 'missing_rows': len(missing),
                      'unexpected_rows': 0, 'changed_rows': 0, 'allowed_auth_backfill_rows': 0,
                      'allowed_native_config_defaults': 0}
            summary['tables'][table] = counts
            if table in receipt['source_counts'] and len(original) != receipt['source_counts'][table]:
                mismatch('receipt_source_count', table=table)
            for key in missing:
                mismatch('missing_row', table=table, key=list(key))
            for key in added:
                actual = migrated[key]
                if table == 'config' and actual['key'] in NEW_CONFIG_DEFAULTS:
                    value = decode_value(actual['value'])
                    expected = NEW_CONFIG_DEFAULTS[actual['key']]
                    if type(value) is type(expected) and value == expected:
                        counts['allowed_native_config_defaults'] += 1
                        continue
                if table == 'auth' and actual['id'] in expected_auth_ids:
                    expected = {'id': actual['id'], 'email': source_users[actual['id']], 'password': '', 'active': 1}
                    if all(actual.get(name) == value for name, value in expected.items()):
                        counts['allowed_auth_backfill_rows'] += 1
                        continue
                counts['unexpected_rows'] += 1
                mismatch('unexpected_row', table=table, key=list(key))
            if table == 'auth':
                actual_backfill = {row['id'] for row in migrated.values()} - source_auth_ids
                for missing_id in expected_auth_ids - actual_backfill:
                    mismatch('missing_auth_backfill', table=table, key=[missing_id])
            for key in set(original) & set(migrated):
                before = original[key]
                if table == 'config' and before['key'] in config_keys:
                    seen_config.add(before['key'])
                if table == 'function':
                    if before['id'] in valve_ids:
                        seen_valves.add(before['id'])
                    if before['id'] == 'stage2_media_intake':
                        seen_media_event = True
                expected = expected_row(table, before, config_keys & STAGE_CONFIG, valve_ids)
                actual = migrated[key]
                different = [name for name in source_names if expected[name] != actual[name]]
                if different:
                    counts['changed_rows'] += 1
                    mismatch('changed_row', table=table, key=list(key), columns=different,
                             expected_sha256=digest(expected), actual_sha256=digest(actual))
        if seen_config != config_keys or seen_valves != valve_ids or not seen_media_event:
            mismatch('receipt_override_target_missing')
    finally:
        source.close()
        candidate.close()

    manifest_path = receipt_path.parent / 'uploads-candidate.private.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest_hash = hashlib.sha256(json.dumps(manifest).encode()).hexdigest()
    if manifest_hash != receipt['uploads_sha256'] or len(manifest) != receipt['upload_files']:
        mismatch('uploads_manifest_identity')
    upload_root = (candidate_path.parent / 'uploads').resolve()
    expected_paths = set()
    file_counts = {'expected': len(manifest), 'verified': 0, 'missing_or_changed': 0,
                   'unmanifested_upload_files': 0}
    for relative, size, expected_hash in manifest:
        path = (upload_root / relative).resolve()
        if not path.is_relative_to(upload_root) or relative in expected_paths:
            mismatch('invalid_upload_manifest_path')
            file_counts['missing_or_changed'] += 1
            continue
        expected_paths.add(relative)
        if not path.is_file() or path.stat().st_size != size or file_digest(path) != expected_hash:
            file_counts['missing_or_changed'] += 1
            mismatch('upload_bytes', path=relative, expected_sha256=expected_hash)
        else:
            file_counts['verified'] += 1
    if upload_root.exists():
        for path in upload_root.rglob('*'):
            if path.is_file() and str(path.relative_to(upload_root)) not in expected_paths:
                file_counts['unmanifested_upload_files'] += 1
                details['unmanifested_uploads'].append(str(path.relative_to(upload_root)))
    summary['files'] = file_counts
    summary['new_native_tables'] = len(details['new_tables'])
    summary['mismatch_count'] = len(details['mismatches'])
    summary['ok'] = not details['mismatches']
    summary['read_snapshot'] = 'native-sqlite-backup-in-memory' if memory_snapshot else 'readonly-file-transaction'
    summary['elapsed_seconds'] = round(time.monotonic() - started, 3)
    details['input_hashes'] = {'source_db': file_digest(source_path), 'receipt': file_digest(receipt_path),
                             'uploads_manifest': file_digest(manifest_path)}
    return summary, details


def write_private_report(path, summary, details):
    parent = path.parent.resolve()
    metadata = parent.stat()
    if os.name != 'nt' and (stat.S_IMODE(metadata.st_mode) & 0o077 or metadata.st_uid != os.getuid()):
        raise ValueError('Output directory must be private and owned by the caller')
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(parent / path.name, flags, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump({'summary': summary, 'details': details}, stream, ensure_ascii=True, indent=2)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--memory-snapshot', action='store_true', help='Use native SQLite backup into RAM for read checks')
    args = parser.parse_args()
    try:
        summary, details = verify(args.source, args.candidate, args.receipt, memory_snapshot=args.memory_snapshot)
        if args.output:
            write_private_report(args.output, summary, details)
    except Exception as error:
        print(json.dumps({'ok': False, 'error_type': type(error).__name__, 'verification_incomplete': True}))
        return 2
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
