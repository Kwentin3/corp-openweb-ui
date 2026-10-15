#!/usr/bin/env python3
"""Rehearse a bounded DB downgrade on a disposable copy, never a WebUI server.

Requires adjacent verify_migration.py/prepare_stage.py. Inputs are read only.
The new private work directory retains snapshots, copied uploads and logs.
Synthetic writes use candidate ORM models; this is not ordinary-user UI proof.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import time
import uuid

sys.dont_write_bytecode = True
from verify_migration import OLD_REVISION, NEW_REVISION, columns, file_digest, identifier, readonly, table_names

OLD_IMAGE = 'sha256:665f7fd87fcc43752aa3ffa8c9c85a1ef8e1d142525f367eef3a8d8a29ecb8e8'
UPSTREAM_COMMIT = '6a18585ff4c2e5f6805f682222cfbc46dc669ef8'
MARKER = '__ROLLBACK_PROOF__'

# Runs only in the candidate image against the disposable bind mount.
CANDIDATE_CODE = r'''
import hashlib,json,os,sqlite3,time,uuid
from pathlib import Path
os.umask(0o077)
from sqlalchemy.orm import Session
from open_webui.internal.db import engine
from open_webui.models.chats import Chat,ChatFile
from open_webui.models.chat_messages import ChatMessage
from open_webui.models.files import File
from open_webui.models.users import User
proof=Path('/proof');inputs=json.loads((proof/'inputs.private.json').read_text())
owner=inputs['owner_id'];chat_id=str(uuid.uuid4());file_id=str(uuid.uuid4())
user_id=str(uuid.uuid4());answer_id=str(uuid.uuid4());now=int(time.time())
payload=b'Rollback rehearsal: preserved ordinary file bytes.\n'
filename='rollback-rehearsal.txt';path=Path('/app/backend/data/uploads')/(file_id+'_'+filename)
path.write_bytes(payload);sha=hashlib.sha256(payload).hexdigest()
attachment={'id':file_id,'name':filename,'type':'file','url':'/api/v1/files/'+file_id+'/content'}
messages={user_id:{'id':user_id,'parentId':None,'childrenIds':[answer_id],'role':'user','content':'Preserve this ordinary chat and file.','timestamp':now},
answer_id:{'id':answer_id,'parentId':user_id,'childrenIds':[],'role':'assistant','content':'Ordinary reply preserved through downgrade.','timestamp':now,'done':True,'files':[attachment]}}
chat={'id':chat_id,'title':'Rollback rehearsal','models':[],'history':{'currentId':answer_id,'messages':messages},'messages':list(messages.values())}
with Session(engine) as session:
    assert session.get(User,owner) is not None
    session.add(Chat(id=chat_id,user_id=owner,title='Rollback rehearsal',chat=chat,meta={},variables={},current_message_id=answer_id,created_at=now,updated_at=now,archived=False,pinned=False))
    session.add(File(id=file_id,user_id=owner,hash=sha,filename=filename,path=str(path),data={'status':'completed'},meta={'name':filename,'content_type':'text/plain','size':len(payload)},created_at=now,updated_at=now))
    session.flush()
    for message in messages.values():
        session.add(ChatMessage(id=chat_id+'-'+message['id'],chat_id=chat_id,user_id=owner,role=message['role'],parent_id=message.get('parentId'),content=message['content'],files=message.get('files'),done=True,created_at=now,updated_at=now))
    session.add(ChatFile(id=str(uuid.uuid4()),user_id=owner,chat_id=chat_id,message_id=answer_id,file_id=file_id,created_at=now,updated_at=now))
    session.commit()
engine.dispose()
fixture={'owner_id':owner,'chat_id':chat_id,'file_id':file_id,'file_sha256':sha,'file_relative_path':str(path.relative_to('/app/backend/data/uploads'))}
(proof/'fixture.private.json').write_text(json.dumps(fixture),encoding='utf-8')
with sqlite3.connect('file:/app/backend/data/webui.db?mode=ro',uri=True) as incoming,sqlite3.connect('/proof/before.sqlite3') as outgoing:
    incoming.backup(outgoing)
from alembic import command
from alembic.config import Config
config=Config('/app/backend/open_webui/alembic.ini')
config.set_main_option('script_location','/app/backend/open_webui/migrations')
command.downgrade(config,'d4c1a8e37b62')
print('__ROLLBACK_PROOF__'+json.dumps({'native_downgrade_completed':True,'synthetic_chat_rows':1,'synthetic_message_rows':2,'synthetic_file_rows':1}))
'''

# Native 0.11.4 ORM classes, custom read-only engine; no main/lifespan/plugins.
OLD_ORM_CODE = r'''
import hashlib,importlib,json
from pathlib import Path
from sqlalchemy import create_engine,select,text
from sqlalchemy.orm import Session
proof=Path('/proof');expected=json.loads((proof/'orm-expected.private.json').read_text())
mapping={'user':('users','User'),'auth':('auths','Auth'),'chat':('chats','Chat'),'chat_message':('chat_messages','ChatMessage'),'chat_file':('chats','ChatFile'),'file':('files','File'),'model':('models','Model'),'tool':('tools','Tool'),'skill':('skills','Skill'),'function':('functions','Function'),'config':('config','Config'),'access_grant':('access_grants','AccessGrant'),'group':('groups','Group'),'group_member':('groups','GroupMember')}
engine=create_engine('sqlite:///file:/app/backend/data/webui.db?mode=ro&immutable=1&uri=true')
counts={}
with Session(engine) as session:
    session.execute(text('PRAGMA query_only=ON'))
    for table,(module,name) in mapping.items():
        model=getattr(importlib.import_module('open_webui.models.'+module),name)
        count=sum(1 for _ in session.scalars(select(model).execution_options(yield_per=10)))
        counts[table]=count
        assert count==expected['counts'][table]
    from open_webui.models.chats import Chat,ChatModel
    from open_webui.models.files import File,FileModel
    chat=ChatModel.model_validate(session.get(Chat,expected['chat_id']))
    file=FileModel.model_validate(session.get(File,expected['file_id']))
    assert chat.user_id==file.user_id==expected['owner_id']
    assert len(chat.chat['history']['messages'])==2
    assert any(item.get('files') for item in chat.chat['history']['messages'].values())
    assert hashlib.sha256(Path(file.path).read_bytes()).hexdigest()==expected['file_sha256']==file.hash
engine.dispose()
print('__ROLLBACK_PROOF__'+json.dumps({'old_orm_read_ok':True,'counts':counts,'synthetic_chat_and_file_read_ok':True}))
'''


def private_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=True, indent=2)
        stream.write('\n')


def json_value(value):
    return json.loads(value) if isinstance(value, str) else value


def feature_gate(source, migrated):
    """Only migration-created initial versions may be discarded by downgrade."""
    blocked = {}
    for table in ('app',):
        blocked[table] = migrated.execute('SELECT count(*) FROM ' + identifier(table)).fetchone()[0]
    for table in ('message', 'channel_member'):
        blocked[table + '_app_authorship'] = migrated.execute(
            'SELECT count(*) FROM ' + identifier(table) + ' WHERE app_id IS NOT NULL').fetchone()[0]
    blocked['mfa_or_session_stamp'] = sum(
        json_value(row['mfa']) is not None or row['session_stamp'] is not None
        for row in migrated.execute('SELECT mfa,session_stamp FROM auth'))
    blocked['group_hierarchy'] = migrated.execute('SELECT count(*) FROM "group" WHERE parent_group_id IS NOT NULL').fetchone()[0]
    row = migrated.execute("SELECT value FROM config WHERE key='auth.mfa.enable'").fetchone()
    blocked['mfa_enabled'] = int(bool(row and json_value(row[0])))
    blocked['multi_file_skills'] = sum(
        json_value(row['data']) != {'files': [{'path': 'SKILL.md', 'content': row['content']}]}
        for row in migrated.execute('SELECT content,data FROM skill'))
    for kind in ('model', 'tool', 'function', 'skill'):
        baseline = {row['id']: dict(row) for row in source.execute('SELECT * FROM ' + identifier(kind))}
        current = {row['id']: dict(row) for row in migrated.execute('SELECT * FROM ' + identifier(kind))}
        history = list(migrated.execute('SELECT * FROM ' + identifier(kind + '_history')))
        invalid = len(set(baseline) ^ set(current)) + abs(len(history) - len(baseline))
        seen = set()
        for version in history:
            entity_id = version[kind + '_id']
            initial = baseline.get(entity_id)
            entity = current.get(entity_id)
            invalid += int(entity_id in seen or initial is None or entity is None or version['parent_id'] is not None
                           or version['commit_message'] is not None or (entity and entity['version_id'] != version['id']))
            if initial:
                created = initial['updated_at'] if kind == 'skill' else initial['updated_at'] or initial['created_at'] or 0
                invalid += int(version['created_at'] != created)
            seen.add(entity_id)
        blocked[kind + '_version_history'] = invalid
    return blocked


def backup(source, target):
    with closing(readonly(source)) as incoming, closing(sqlite3.connect(target)) as outgoing:
        incoming.backup(outgoing)


def inventory(directory):
    result = []
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise ValueError('Upload symlinks need separate review')
        if path.is_file():
            result.append((str(path.relative_to(directory)), path.stat().st_size, file_digest(path)))
    return result


def foreign_keys(connection):
    return Counter(tuple(row) for row in connection.execute('PRAGMA foreign_key_check'))


def run_container(image, work, code, phase, *, readonly_data=False):
    name = 'owui-rollback-' + phase + '-' + uuid.uuid4().hex[:12]
    env = {'DATA_DIR': '/app/backend/data', 'DATABASE_URL': 'sqlite:////app/backend/data/webui.db',
           'ENABLE_DB_MIGRATIONS': 'false', 'WEBUI_AUTH': 'false', 'OFFLINE_MODE': 'true',
           'STORAGE_PROVIDER': 'local', 'VECTOR_DB': 'chroma', 'CHROMA_HTTP_HOST': '',
           'REDIS_URL': '', 'WEBSOCKET_MANAGER': '', 'WEBSOCKET_REDIS_URL': '',
           'STATIC_DIR': '/tmp/static', 'FRONTEND_BUILD_DIR': '/tmp/no-frontend',
           'PYTHONDONTWRITEBYTECODE': '1', 'HF_HUB_OFFLINE': '1'}
    command = ['docker', 'run', '--rm', '--pull=never', '--name', name, '--network', 'none',
               '--memory', '1g', '--memory-swap', '1g', '--cpus', '0.5', '--pids-limit', '256',
               '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
               '--tmpfs', '/tmp:rw,nosuid,noexec,size=128m', '--entrypoint', 'python',
               '--workdir', '/app/backend',
               '--mount', 'type=bind,src=' + str(work / 'data') + ',dst=/app/backend/data' + (',readonly' if readonly_data else ''),
               '--mount', 'type=bind,src=' + str(work) + ',dst=/proof' + (',readonly' if readonly_data else '')]
    for key, value in env.items():
        command.extend(['--env', key + '=' + value])
    command.extend([image, '-B', '-c', code])
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=240)
    except subprocess.TimeoutExpired:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=30)
        raise
    for label, value in (('stdout', result.stdout), ('stderr', result.stderr)):
        with (work / (phase + '.' + label + '.private.log')).open('x', encoding='utf-8') as stream:
            stream.write(value)
    if result.returncode:
        raise RuntimeError('Isolated container failed; inspect its private logs')
    return json.loads(next(line[len(MARKER):] for line in reversed(result.stdout.splitlines()) if line.startswith(MARKER)))


def rehearse(args):
    started = time.monotonic()
    os.umask(0o077)
    work = args.work_dir.resolve()
    if any(char in str(work) for char in ',\r\n'):
        raise ValueError('Unsupported work directory characters')
    parent = work.parent.stat()
    if stat.S_IMODE(parent.st_mode) & 0o077 or parent.st_uid != os.getuid():
        raise ValueError('Work parent must be caller-owned and private')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', args.candidate_image):
        raise ValueError('Use the exact installed candidate image ID')
    if args.source.resolve() == args.candidate.resolve() or work == args.candidate.parent.resolve():
        raise ValueError('Separate source, candidate and disposable paths are required')
    if not args.uploads.is_dir():
        raise ValueError('The source uploads directory must exist')
    work.mkdir(mode=0o700)  # Exclusive: never refresh or destroy an earlier attempt.
    data = work / 'data'
    data.mkdir(mode=0o700)
    summary = {'ok': False, 'proof': 'database_and_old_orm_only', 'third_webui_started': False}
    try:
        images = json.loads(subprocess.check_output(['docker', 'image', 'inspect', args.candidate_image, OLD_IMAGE], timeout=30))
        if {item['Id'] for item in images} != {args.candidate_image, OLD_IMAGE}:
            raise ValueError('Image identities differ')
        labels = next(item for item in images if item['Id'] == args.candidate_image)['Config']['Labels']
        if labels.get('corp.upstream.version') != '0.12.2' or labels.get('corp.upstream.commit') != UPSTREAM_COMMIT:
            raise ValueError('Unqualified candidate image')
        backup(args.candidate, data / 'webui.db')
        (data / 'cache').mkdir()
        uploads = data / 'uploads'
        uploads.mkdir()
        original_uploads = inventory(args.uploads.resolve())
        for relative, _, _ in original_uploads:
            target = uploads / relative
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            shutil.copy2(args.uploads / relative, target)
        if original_uploads != inventory(uploads):
            raise ValueError('Copied upload bytes differ')
        private_json(work / 'uploads-before.private.json', original_uploads)
        with closing(readonly(args.source)) as source, closing(readonly(data / 'webui.db')) as migrated:
            if [row[0] for row in source.execute('SELECT version_num FROM alembic_version')] != [OLD_REVISION]:
                raise ValueError('Unexpected source revision')
            if [row[0] for row in migrated.execute('SELECT version_num FROM alembic_version')] != [NEW_REVISION]:
                raise ValueError('Unexpected candidate revision')
            if not source.execute('SELECT 1 FROM user WHERE id=?', (args.owner_id,)).fetchone():
                raise ValueError('Fixture owner must exist in the source')
            gates = feature_gate(source, migrated)
            baseline_fk = foreign_keys(source)
            if baseline_fk != foreign_keys(migrated):
                raise ValueError('Candidate changed inherited foreign key violations')
            schema = {table: [row['name'] for row in columns(source, table)]
                      for table in table_names(source) if not table.startswith('sqlite_') and table != 'alembic_version'}
        summary['unsupported_feature_counts'] = gates
        if any(gates.values()):
            raise ValueError('Unsupported feature state blocks this rollback window')
        private_json(work / 'inputs.private.json', {'owner_id': args.owner_id})
        summary['downgrade'] = run_container(args.candidate_image, work, CANDIDATE_CODE, 'downgrade')
        fixture = json.loads((work / 'fixture.private.json').read_text())
        # Finalize only the disposable DB so the old ORM can mount it immutable/RO.
        with closing(sqlite3.connect(data / 'webui.db')) as connection:
            connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            connection.execute('PRAGMA journal_mode=DELETE')
        mismatches = []
        counts = {}
        with closing(readonly(work / 'before.sqlite3', memory_snapshot=True)) as before, \
                closing(readonly(data / 'webui.db', memory_snapshot=True)) as after:
            if [row[0] for row in before.execute('SELECT version_num FROM alembic_version')] != [NEW_REVISION]:
                raise ValueError('Fixture snapshot has wrong revision')
            if [row[0] for row in after.execute('SELECT version_num FROM alembic_version')] != [OLD_REVISION]:
                raise ValueError('Native downgrade did not reach old revision')
            for role, connection in (('before', before), ('after', after)):
                if [row[0] for row in connection.execute('PRAGMA integrity_check')] != ['ok']:
                    raise ValueError('Disposable database integrity failed')
            inherited = foreign_keys(before)
            if inherited != baseline_fk:
                mismatches.append('synthetic_write_foreign_key_set')
            if inherited != foreign_keys(after):
                mismatches.append('foreign_key_set')
            for table, names in schema.items():
                query = 'SELECT ' + ','.join(map(identifier, names)) + ' FROM ' + identifier(table)
                old_rows = Counter(tuple(row) for row in before.execute(query))
                new_rows = Counter(tuple(row) for row in after.execute(query))
                counts[table] = sum(new_rows.values())
                if old_rows != new_rows:
                    mismatches.append(table)
                del old_rows, new_rows
        expected_uploads = original_uploads + [(fixture['file_relative_path'],
                             (uploads / fixture['file_relative_path']).stat().st_size, fixture['file_sha256'])]
        if sorted(expected_uploads) != inventory(uploads):
            mismatches.append('upload_bytes')
        summary.update(shared_tables_compared=len(schema), inherited_fk_violations=sum(inherited.values()),
                       retained_uploads=len(expected_uploads), mismatch_count=len(mismatches))
        private_json(work / 'comparison.private.json', {'mismatches': mismatches, 'table_counts': counts})
        if mismatches:
            raise ValueError('Shared records or uploaded bytes changed')
        private_json(work / 'orm-expected.private.json', {**fixture, 'counts': counts})
        database_hash = file_digest(data / 'webui.db')
        summary['old_orm'] = run_container(OLD_IMAGE, work, OLD_ORM_CODE, 'old-orm', readonly_data=True)
        if database_hash != file_digest(data / 'webui.db') or sorted(expected_uploads) != inventory(uploads):
            raise ValueError('Old ORM process changed retained data')
        private_json(work / 'evidence-hashes.private.json', {
            'old_image': OLD_IMAGE, 'candidate_image': args.candidate_image,
            'source_checkpoint_sha256': file_digest(args.source),
            'candidate_checkpoint_sha256': file_digest(args.candidate),
            'before_downgrade_db_sha256': file_digest(work / 'before.sqlite3'),
            'after_downgrade_db_sha256': database_hash,
        })
        summary['ok'] = True
        summary['elapsed_seconds'] = round(time.monotonic() - started, 3)
        private_json(work / 'result.private.json', summary)
        return summary
    except Exception as error:
        summary.update(error_type=type(error).__name__, verification_incomplete=True,
                       elapsed_seconds=round(time.monotonic() - started, 3))
        private_json(work / 'failure.private.json', {'type': type(error).__name__, 'message': str(error)})
        private_json(work / 'result.private.json', summary)
        return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Preserved 0.11.4 SQLite checkpoint')
    parser.add_argument('--candidate', type=Path, required=True,
                        help='Preserved firstboot checkpoint, e.g. /opt/openwebui-upgrade-0122/first-boot-webui.sqlite3')
    parser.add_argument('--uploads', type=Path, required=True, help='Read-only source uploads directory')
    parser.add_argument('--candidate-image', required=True)
    parser.add_argument('--owner-id', required=True, help='An existing source user; no account is created')
    parser.add_argument('--work-dir', type=Path, required=True, help='New child of an existing mode-0700 directory')
    args = parser.parse_args()
    try:
        summary = rehearse(args)
    except Exception as error:
        summary = {'ok': False, 'error_type': type(error).__name__, 'verification_incomplete': True}
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
