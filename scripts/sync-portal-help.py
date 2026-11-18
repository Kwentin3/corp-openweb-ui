#!/usr/bin/env python3
"""Sync the dedicated help KB with oikb 0.6.0, then publish native Skill pointers.

Run inside the environment's bounded process owner. No automatic mutation retries.
An uncertain oikb/API outcome requires inspection before another invocation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

MARKER = '[managed:portal-help]'
NAME = 'Помощь по порталу и работе с ИИ'
DESCRIPTION = 'Помощь сотрудникам по порталу, работе с ИИ, документам, шаблонам, поиску и доступным возможностям.'
INDEX = 'references/knowledge-index.md'
GRANTS = [{'principal_type': 'user', 'principal_id': '*', 'permission': 'read'}]
ROOT = Path(__file__).resolve().parents[1]


class ContractError(Exception):
    """A safe operator-facing error, without native response bodies or credentials."""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def grants(value):
    if not isinstance(value, list):
        raise ContractError('Native grants are missing')
    return sorted((g.get('principal_type'), g.get('principal_id'), g.get('permission')) for g in value)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class API:
    def __init__(self, url, token):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ContractError('Expected a trusted HTTP(S) OpenWebUI origin')
        self.url, self.token = url.rstrip('/') + '/api/v1', token
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, path, payload=None, raw=False, missing=False, timeout=20):
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(self.url + path, body, {
            'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json',
        }, method=method)
        try:
            with self.opener.open(req, timeout=timeout) as response:
                data = response.read(16 * 1024 * 1024 + 1)
                if len(data) > 16 * 1024 * 1024:
                    raise ContractError('Native response exceeds 16 MiB')
                return data if raw else json.loads(data)
        except urllib.error.HTTPError as error:
            if missing and error.code == 404:
                return None
            raise ContractError(f'Native {method} failed with HTTP {error.code}; inspect state before retry') from None
        except (OSError, ValueError):
            raise ContractError(f'Native {method} outcome unconfirmed; inspect state before retry') from None


def read_sources(directory):
    directory = Path(directory).resolve(strict=True)
    sources = {}
    names = set()
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise ContractError('Source symlinks are not supported')
        if not path.is_file():
            continue
        if path.suffix.lower() != '.md':
            raise ContractError('Dedicated source directory must contain only Markdown files')
        data = path.read_bytes()
        text = data.decode('utf-8')
        if not text.strip() or '\x00' in text:
            raise ContractError('Each Markdown source must contain nonempty UTF-8 text')
        if path.name in names:
            raise ContractError('Markdown basenames must be unique for exact native membership verification')
        names.add(path.name)
        relative = path.relative_to(directory).as_posix()
        title = next((m.group(1).strip() for line in text.splitlines()
                      if (m := re.match(r'^#{1,6}\s+(.+?)\s*#*$', line))), path.stem)
        sources[relative] = {'filename': path.name, 'sha256': sha(data), 'size': len(data), 'title': title}
    if not sources:
        raise ContractError('Empty Markdown source refused before any mutation')
    return sources


def manifest(sources):
    return [{'filename': item['filename'], 'path': path.rsplit('/', 1)[0] if '/' in path else '',
             'checksum': item['sha256'], 'size': item['size']} for path, item in sources.items()]


def members(api, kb, deadline=None):
    items, total = [], None
    for page in range(1, 101):
        timeout = 20 if deadline is None else min(20, max(0.1, deadline - time.monotonic()))
        if deadline is not None and time.monotonic() >= deadline:
            raise ContractError('Processing verification exceeded 60 seconds')
        result = api.request('GET', f'/knowledge/{kb}/files?page={page}', timeout=timeout)
        if not isinstance(result.get('items'), list) or not isinstance(result.get('total'), int):
            raise ContractError('Invalid native membership response')
        if total is not None and total != result['total']:
            raise ContractError('Native membership changed during pagination')
        total = result['total']
        items.extend(result['items'])
        if len(items) >= total:
            if len(items) != total or len({i['id'] for i in items}) != total:
                raise ContractError('Duplicate or inconsistent native membership')
            return items
        if not result['items']:
            break
    raise ContractError('Native membership pagination incomplete')


def verify_members(api, kb, sources):
    deadline = time.monotonic() + 60
    wanted = {item['filename']: (path, item) for path, item in sources.items()}
    while True:
        listing = members(api, kb, deadline)
        if any(item.get('filename') not in wanted for item in listing) or len(listing) > len(wanted):
            raise ContractError('Unexpected native members; Skill publication refused')
        if len({item.get('filename') for item in listing}) != len(listing):
            raise ContractError('Duplicate native filename; Skill publication refused')
        verified, pending = {}, len(listing) != len(wanted)
        for member in listing:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ContractError('Processing verification exceeded 60 seconds')
            native = api.request('GET', '/files/' + member['id'], timeout=min(20, remaining))
            path, source = wanted[member['filename']]
            if native.get('id') != member['id'] or native.get('filename') != source['filename']:
                raise ContractError('Native file identity changed; Skill publication refused')
            status = (native.get('data') or {}).get('status')
            if status == 'failed':
                raise ContractError('Native ingestion failed; Skill publication refused')
            if status != 'completed':
                pending = True
                continue
            # Verify actual stored original bytes, rather than trusting client-supplied meta.file_hash.
            original = api.request('GET', '/files/' + member['id'] + '/content', raw=True,
                                   timeout=min(20, max(0.1, deadline - time.monotonic())))
            if sha(original) != source['sha256'] or len(original) != source['size']:
                raise ContractError('Native original hash differs from canonical source; Skill publication refused')
            if not (native.get('data') or {}).get('content', '').strip():
                raise ContractError('Native extracted content is empty; Skill publication refused')
            verified[path] = {**source, 'file_id': member['id']}
        if not pending:
            return verified
        if time.monotonic() >= deadline:
            raise ContractError('Processing verification exceeded 60 seconds')
        time.sleep(min(1, max(0, deadline - time.monotonic())))


def make_index(kb, verified):
    lines = ['# Индекс справки портала', '', MARKER, '', f'Knowledge ID: `{kb}`.', '',
             'Это указатели на native Knowledge, а не копия документов.', '']
    for path, item in sorted(verified.items()):
        lines.extend([f'## {item["title"]}', f'- Файл: `{path}`',
                      f'- Native File ID: `{item["file_id"]}`', f'- SHA-256: `{item["sha256"]}`', ''])
    return '\n'.join(lines)


def skill_state(api, skill_id, user_id):
    path = '/skills/id/' + skill_id
    current = api.request('GET', path, missing=True)
    if current is None:
        return None, None
    if current.get('user_id') != user_id or current.get('write_access') is not True or MARKER not in current.get('content', ''):
        raise ContractError('Existing Skill is not this authenticated owner\'s managed help Skill')
    if any(g[2] == 'write' for g in grants(current.get('access_grants'))):
        raise ContractError('Existing managed Skill has shared WRITE; inspect grants before sync')
    version = current.get('version_id')
    if not version:
        raise ContractError('Existing Skill version is missing')
    files = api.request('GET', path + '/files?version_id=' + urllib.parse.quote(version))
    if files.get('version_id') != version or {f['path'] for f in files.get('files', [])} - {'SKILL.md', INDEX}:
        raise ContractError('Existing Skill has unrelated supporting files or an inconsistent version')
    contents = {}
    for item in files['files']:
        query = urllib.parse.urlencode({'path': item['path'], 'version_id': version})
        contents[item['path']] = api.request('GET', path + '/files/content?' + query, raw=True).decode('utf-8')
    if contents.get('SKILL.md') != current['content']:
        raise ContractError('Existing Skill content/version mismatch')
    return current, contents


def publish_skill(api, skill_id, user_id, content, index, baseline, description=DESCRIPTION):
    current, contents = skill_state(api, skill_id, user_id)
    if (current or {}).get('version_id') != (baseline or {}).get('version_id'):
        raise ContractError('Skill changed during KB sync; publication refused')
    desired_files = {'SKILL.md': content, INDEX: index}
    metadata = {'tags': ['portal-help']}
    same = (current is not None and contents == desired_files and current.get('name') == NAME
            and current.get('description') == description and current.get('is_active') is True
            and current.get('meta', {}).get('tags') == metadata['tags']
            and not current.get('meta', {}).get('i18n') and grants(current.get('access_grants')) == grants(GRANTS))
    changed = not same
    if changed:
        payload = {'id': skill_id, 'name': NAME, 'description': description,
                   'files': [{'path': path, 'content': text} for path, text in desired_files.items()],
                   'meta': metadata, 'is_active': True, 'access_grants': GRANTS}
        if current:
            payload['expected_version_id'] = current['version_id']
        api.request('POST', '/skills/id/' + skill_id + '/update' if current else '/skills/create', payload)
    saved, saved_files = skill_state(api, skill_id, user_id)
    if (saved is None or saved_files != desired_files or saved.get('name') != NAME
            or saved.get('description') != description or saved.get('is_active') is not True
            or saved.get('meta', {}).get('tags') != metadata['tags'] or saved.get('meta', {}).get('i18n')
            or grants(saved.get('access_grants')) != grants(GRANTS)):
        raise ContractError('Native Skill readback differs from intended content/index/metadata/grants')
    return {'changed': changed, 'version_id': saved['version_id'], 'index_sha256': sha(index.encode('utf-8'))}


def run_oikb(executable, url, token, directory, kb, dry_run):
    env = {**os.environ, 'OPEN_WEBUI_URL': url, 'OPEN_WEBUI_API_KEY': token}
    try:
        version = subprocess.run([executable, '--version'], env=env, capture_output=True, timeout=10, check=False)
        if version.returncode or not re.search(rb'\b0\.6\.0\b', version.stdout + version.stderr):
            raise ContractError('Expected pinned oikb 0.6.0 executable')
        command = [executable, 'sync', str(directory), '--kb-id', kb, '--concurrency', '1']
        if dry_run:
            command.append('--dry-run')
        result = subprocess.run(command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90, check=False)
        if result.returncode:
            raise ContractError('oikb failed; inspect native state before retry, no Skill published')
    except subprocess.TimeoutExpired:
        raise ContractError('oikb outcome uncertain after timeout; stop and inspect managed process tree/native state before retry') from None
    except OSError:
        raise ContractError('oikb executable could not run') from None


def execute(args, api_factory=API, sync=run_oikb):
    sources = read_sources(args.source_dir)  # Fail empty/invalid before API or mutation.
    content = Path(args.skill_source).read_text(encoding='utf-8')
    if MARKER not in content or not content.strip():
        raise ContractError('Skill source must contain the managed help ownership marker')
    description = DESCRIPTION
    if content.startswith('---\n'):
        frontmatter = content.split('---', 2)[1]
        for line in frontmatter.splitlines():
            if line.startswith('description: '):
                try:
                    description = json.loads(line[len('description: '):])
                except ValueError:
                    raise ContractError('Skill description must be a quoted JSON/YAML string') from None
                if not isinstance(description, str) or not description.strip():
                    raise ContractError('Skill description must be nonempty text')
    if not re.fullmatch(r'[a-z0-9_-]+', args.skill_id) or not re.fullmatch(r'[A-Za-z0-9_-]+', args.knowledge_id):
        raise ContractError('Invalid native Skill or Knowledge ID')
    token = Path(args.token_file).read_text(encoding='utf-8-sig').strip()
    if not token or any(c.isspace() for c in token):
        raise ContractError('Token file must contain one raw bearer token')
    api = api_factory(args.url, token)
    user = api.request('GET', '/auths/')
    kb_path = '/knowledge/' + args.knowledge_id
    kb = api.request('GET', kb_path)
    if kb.get('id') != args.knowledge_id or MARKER not in kb.get('description', '') or kb.get('write_access') is not True:
        raise ContractError('Dedicated managed Knowledge identity/write access not confirmed')
    if grants(kb.get('access_grants')) != grants(GRANTS):
        raise ContractError('Managed Knowledge must grant user:* READ only')
    baseline, _ = skill_state(api, args.skill_id, user['id'])
    sync(args.oikb, args.url, token, Path(args.source_dir).resolve(), args.knowledge_id, args.dry_run)
    if read_sources(args.source_dir) != sources or Path(args.skill_source).read_text(encoding='utf-8') != content:
        raise ContractError('Canonical inputs changed during sync; no Skill published')
    receipt = {'status': 'dry-run' if args.dry_run else 'verified', 'knowledge_id': args.knowledge_id,
               'skill_id': args.skill_id, 'source_count': len(sources), 'skill_published': False}
    if args.dry_run:
        preview = api.request('POST', kb_path + '/sync/diff', {'manifest': manifest(sources)})
        receipt['planned_changes'] = {key: preview.get(key) for key in
                                      ('added', 'modified', 'deleted', 'mkdir', 'rmdir', 'unmodified_count')}
        return receipt
    verified = verify_members(api, args.knowledge_id, sources)
    diff = api.request('POST', kb_path + '/sync/diff', {'manifest': manifest(sources)})
    if any(diff.get(key) for key in ('added', 'modified', 'deleted', 'mkdir', 'rmdir')) or diff.get('unmodified_count') != len(sources):
        raise ContractError('Native final manifest differs; no Skill published')
    final_members = members(api, args.knowledge_id)
    if {i['id'] for i in final_members} != {i['file_id'] for i in verified.values()}:
        raise ContractError('Native membership changed before publication')
    current_kb = api.request('GET', kb_path)
    if current_kb.get('description') != kb['description'] or grants(current_kb.get('access_grants')) != grants(GRANTS):
        raise ContractError('Managed Knowledge metadata/grants changed before publication')
    if read_sources(args.source_dir) != sources or Path(args.skill_source).read_text(encoding='utf-8') != content:
        raise ContractError('Canonical inputs changed during verification; no Skill published')
    receipt['skill'] = publish_skill(api, args.skill_id, user['id'], content, make_index(args.knowledge_id, verified), baseline, description)
    receipt.update(skill_published=True, files=[{'path': path, 'file_id': item['file_id'], 'sha256': item['sha256']}
                                              for path, item in sorted(verified.items())])
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('url', 'token-file', 'knowledge-id', 'receipt'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--oikb', default='oikb')
    parser.add_argument('--source-dir', type=Path, default=ROOT / 'deploy/openwebui-knowledge/portal-help')
    parser.add_argument('--skill-source', type=Path, default=ROOT / 'deploy/openwebui-skills/portal-help.md')
    parser.add_argument('--skill-id', default='portal-help')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        receipt = execute(args)
        code = 0
    except (ContractError, OSError, UnicodeError) as error:
        receipt = {'status': 'unconfirmed', 'skill_published': None,
                   'knowledge_id': args.knowledge_id, 'skill_id': args.skill_id,
                   'error': str(error) if isinstance(error, ContractError) else type(error).__name__,
                   'next_step': 'Inspect native state and owned process completion before retry; no automatic rollback.'}
        code = 1
    Path(args.receipt).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': receipt['status'], 'receipt': str(args.receipt)}, ensure_ascii=False))
    return code


if __name__ == '__main__':
    sys.exit(main())
