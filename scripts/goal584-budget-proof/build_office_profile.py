"""Compose existing public Office/WebUI build owners on a fresh Linux CI runner."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

UPSTREAM = '6a18585ff4c2e5f6805f682222cfbc46dc669ef8'
NODE = 'node:22-alpine3.20@sha256:2289fb1fba0f4633b08ec47b94a89c7e20b829fc5679f9b7b298eaa2f1ed8b7e'
NODE_OPTIONS = '--max-old-space-size=5120'
INPUTS = ('deploy/openwebui-upgrade-0122', 'deploy/openwebui-patches/media-upload-v0.12.2',
    'deploy/openwebui-patches/tool-context-v0.12.2', 'deploy/openwebui-patches/provider-context-v0.12.2',
    'services/officecli-openapi-proof')
WEBUI_FILES = ('config.py', 'utils/middleware.py', 'routers/openai.py', 'utils/payload.py',
    'routers/terminals.py', 'utils/tools.py', 'utils/misc.py', 'routers/files.py', 'storage/provider.py')
OFFICE_FILES = ('app.py', 'openwebui_client.py', 'rendering.py', 'config.py', 'officecli.py')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def manifest(root):
    paths = sorted(root.rglob('*'))
    if any(path.is_symlink() for path in paths):
        raise ValueError('Artifact contains a symlink')
    return {p.relative_to(root).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha(p)}
        for p in paths if p.is_file()}


def main(work, receipt):
    repo = Path(__file__).resolve().parents[2]
    if sys.platform != 'linux':
        raise ValueError('Execution requires a separately prepared Linux CI runner')
    if not work.is_absolute() or work != work.resolve() or work.exists() or not work.parent.is_dir() or work.is_relative_to(repo):
        raise ValueError('work-root must be a fresh absolute directory with an existing parent')
    if not receipt.is_absolute() or not receipt.resolve().is_relative_to(work) or receipt.exists():
        raise ValueError('receipt must be a fresh absolute file inside work-root')
    head = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    if os.environ.get('GITHUB_SHA', head) != head:
        raise ValueError('GITHUB_SHA differs from source HEAD')
    if subprocess.check_output(['git', '-C', str(repo), 'status', '--porcelain', '--untracked-files=all']):
        raise ValueError('Build requires a clean committed repository, including this CLI')
    work.mkdir()
    (work / 'logs').mkdir()
    (work / 'home').mkdir()
    env = {'PATH': os.environ['PATH'], 'HOME': str(work / 'home'), 'LC_ALL': 'C.UTF-8',
        'DOCKER_BUILDKIT': '1', 'DOCKER_CONFIG': str(work / 'docker-config'),
        'GIT_CONFIG_NOSYSTEM': '1', 'GIT_TERMINAL_PROMPT': '0', 'PYTHONDONTWRITEBYTECODE': '1'}
    commands = []

    def run(*args, cwd=repo, capture=False):
        args = [str(arg) for arg in args]
        log = work / 'logs' / f'{len(commands):03d}.log'
        commands.append({'argv': args, 'log': log.relative_to(work).as_posix()})
        write(work / 'commands.json', commands)
        with log.open('wb') as stream:
            subprocess.run(args, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, check=True)
        return log.read_text(encoding='utf-8').strip() if capture else None

    info = json.loads(run('docker', 'info', '--format', '{{json .}}', capture=True))
    mem = {line.split(':')[0]: int(line.split()[1]) * 1024
        for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')}
    resources = {'work_disk_free': shutil.disk_usage(work).free,
        'docker_disk_free': shutil.disk_usage(info['DockerRootDir']).free,
        'ram_available': mem['MemAvailable'], 'docker_memory': info['MemTotal']}
    write(work / 'resources.json', resources)
    if min(resources['work_disk_free'], resources['docker_disk_free']) < 20 * 1024**3 or resources['ram_available'] < 6 * 1024**3 or resources['docker_memory'] < 7 * 1024**3:
        raise ValueError('Runner requires 20GiB free disk, 6GiB available RAM and 7GiB Docker memory')
    archive = work / 'git-inputs.tar'
    run('git', 'archive', '--format=tar', '--output', archive, head, *INPUTS)
    source = work / 'source'
    source.mkdir()
    with tarfile.open(archive) as bundle:
        bundle.extractall(source, filter='data')
    git_inputs = manifest(source)
    write(work / 'git-inputs.json', git_inputs)
    upstream = work / 'upstream'
    run('git', 'init', upstream)
    run('git', '-C', upstream, 'remote', 'add', 'origin', 'https://github.com/open-webui/open-webui.git')
    run('git', '-C', upstream, 'fetch', '--depth=1', 'origin', UPSTREAM)
    run('git', '-c', 'core.autocrlf=false', '-C', upstream, 'checkout', '--detach', UPSTREAM)
    if run('git', '-C', upstream, 'rev-parse', 'HEAD', capture=True) != UPSTREAM or run('git', '-C', upstream, 'status', '--porcelain', capture=True):
        raise ValueError('Official upstream checkout is inconsistent')
    upstream_archive = work / 'upstream-source.tar'
    run('git', '-C', upstream, 'archive', '--format=tar', '--output', upstream_archive, UPSTREAM)
    media = source / INPUTS[1]
    run(sys.executable, media / 'verify_installer.py', upstream)
    run(sys.executable, media / 'apply_media.py', upstream, '--check')
    run(sys.executable, media / 'apply_media.py', upstream)
    run(sys.executable, media / 'verify_backend.py', upstream)
    tracked = run('git', '-C', upstream, 'ls-files', capture=True).splitlines()
    frontend_sources = {name: sha(upstream / name) for name in tracked}
    upstream_status = run('git', '-C', upstream, 'status', '--porcelain', '--untracked-files=all', capture=True)
    write(work / 'frontend-sources.json', frontend_sources)
    build_inputs = {'source_commit': head, 'upstream_commit': UPSTREAM, 'node_image': NODE,
        'node_options': NODE_OPTIONS,
        'runtime_base': (source / INPUTS[0] / 'runtime.Dockerfile').read_text().splitlines()[0].partition('=')[2],
        'source_archive_sha256': sha(upstream_archive), 'git_inputs_sha256': sha(work / 'git-inputs.json'),
        'frontend_sources_sha256': sha(work / 'frontend-sources.json')}
    write(work / 'build-inputs.json', build_inputs)
    identity = sha(work / 'build-inputs.json')
    (work / '.build_identity').write_text(identity + '\n', encoding='ascii')
    tags = {name: f'goal584-office-{name}:{head[:12]}-{identity[:12]}' for name in ('frontend', 'webui', 'office')}
    run('docker', 'build', '--platform=linux/amd64', '--target', 'frontend', '--build-context', f'media_overlay={media}',
        '--build-arg', f'NODE_IMAGE={NODE}', '--build-arg', f'BUILD_HASH={identity}',
        '--build-arg', f'NODE_OPTIONS={NODE_OPTIONS}',
        '--iidfile', work / 'frontend.iid', '-f', media / 'frontend.Dockerfile', '-t', tags['frontend'], upstream)
    frontend = work / 'frontend'
    frontend.mkdir()
    container = run('docker', 'create', (work / 'frontend.iid').read_text().strip(), capture=True)
    try:
        run('docker', 'cp', f'{container}:/app/build', frontend / 'build')
    finally:
        run('docker', 'rm', container)
    files = manifest(frontend / 'build')
    if not files or json.loads((frontend / 'build/_app/version.json').read_text())['version'] != identity:
        raise ValueError('Actual frontend version does not match native build identity')
    write(frontend / 'frontend-files.json', files)
    artifact = frontend / 'frontend.tar'
    with tarfile.open(artifact, 'w') as bundle:
        bundle.add(frontend / 'build', arcname='build')
    write(frontend / 'frontend-artifact-receipt.json', {'upstream_version': '0.12.2', 'upstream_commit': UPSTREAM,
        'build_identity': identity, 'native_build_command': 'npm run build', 'source_archive_sha256': sha(upstream_archive),
        'input_receipt_sha256': sha(work / 'build-inputs.json'), 'frontend_sources_sha256': sha(work / 'frontend-sources.json'),
        'artifact_sha256': sha(artifact), 'build_files': len(files), 'build_uncompressed_bytes': sum(v['bytes'] for v in files.values()),
        'build_files_manifest_sha256': sha(frontend / 'frontend-files.json'), 'native_build_success': True,
        'sourcemap': any(name.endswith('.map') for name in files), 'build_directory': str(frontend / 'build')})
    runtime = work / 'runtime-context'
    run(sys.executable, source / INPUTS[0] / 'make_runtime_context.py', '--frontend', frontend, '--output', runtime)
    run('docker', 'build', '--platform=linux/amd64', '--network=none', '--target', 'runtime',
        '--build-arg', f'BUILD_HASH={identity}', '--iidfile', work / 'webui.iid', '-f', runtime / 'runtime.Dockerfile', '-t', tags['webui'], runtime)
    run('docker', 'build', '--platform=linux/amd64', '--iidfile', work / 'office.iid', '-f', source / INPUTS[4] / 'Dockerfile', '-t', tags['office'], source)
    images = {}
    for name, tag in tags.items():
        frozen_id = (work / f'{name}.iid').read_text().strip()
        image = json.loads(run('docker', 'image', 'inspect', frozen_id, capture=True))[0]
        if image['Os'] != 'linux' or image['Architecture'] != 'amd64':
            raise ValueError('Unexpected image platform')
        images[name] = {'id': image['Id'], 'tag': tag, 'repo_digests': image['RepoDigests']}
    node_version = run('docker', 'run', '--rm', '--network=none', '--read-only', '--entrypoint', 'node', images['frontend']['id'], '--version', capture=True)
    inspect_webui = 'import hashlib,json,os,pathlib; r=pathlib.Path("/app/backend/open_webui"); print(json.dumps({"modules":{n:hashlib.sha256((r/n).read_bytes()).hexdigest() for n in ' + repr(WEBUI_FILES) + '},"build_hash":os.environ["WEBUI_BUILD_HASH"],"version":json.loads(pathlib.Path("/app/build/_app/version.json").read_text())["version"]}))'
    webui = json.loads(run('docker', 'run', '--rm', '--network=none', '--read-only', '--entrypoint', 'python', images['webui']['id'], '-c', inspect_webui, capture=True))
    if webui['build_hash'] != identity or webui['version'] != identity:
        raise ValueError('In-image native build identity differs')
    inspect_office = 'import hashlib,json,pathlib,subprocess; r=pathlib.Path("/app/officecli_openapi_proof"); print(json.dumps({"modules":{n:hashlib.sha256((r/n).read_bytes()).hexdigest() for n in ' + repr(OFFICE_FILES) + '},"binary_sha256":hashlib.sha256(pathlib.Path("/usr/local/bin/officecli").read_bytes()).hexdigest(),"version":subprocess.check_output(["/usr/local/bin/officecli","--version"],text=True).strip()}))'
    office = json.loads(run('docker', 'run', '--rm', '--network=none', '--read-only', '--tmpfs', '/tmp', '--entrypoint', 'python', images['office']['id'], '-c', inspect_office, capture=True))
    if office['modules'] != {n: sha(source / INPUTS[4] / 'officecli_openapi_proof' / n) for n in OFFICE_FILES}:
        raise ValueError('In-image Office source differs from committed inputs')
    if {name: sha(upstream / name) for name in tracked} != frontend_sources or run('git', '-C', upstream, 'status', '--porcelain', '--untracked-files=all', capture=True) != upstream_status:
        raise ValueError('Official frontend inputs changed during build')
    if manifest(source) != git_inputs or subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip() != head or subprocess.check_output(['git', '-C', str(repo), 'status', '--porcelain', '--untracked-files=all']):
        raise ValueError('Git or exported build inputs changed during build')
    receipt.parent.mkdir(parents=True, exist_ok=True)
    if receipt.exists():
        raise ValueError('Receipt path collides with a build artifact')
    write(receipt, {'schema': 1, 'source_commit': head, 'build_identity': identity, 'inputs': build_inputs,
        'images': images, 'node_version': node_version, 'webui': webui, 'office': office, 'resources': resources,
        'runtime_dockerfile_sha256': sha(runtime / 'runtime.Dockerfile'),
        'frontend_manifest_sha256': sha(frontend / 'frontend-files.json'),
        'commands_sha256': sha(work / 'commands.json'), 'native_office_accepted': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', required=True, type=Path)
    parser.add_argument('--receipt', required=True, type=Path)
    options = parser.parse_args()
    main(options.work_root, options.receipt)
