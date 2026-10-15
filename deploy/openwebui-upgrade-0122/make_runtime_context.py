"""Package only reviewed public code and frontend; exclude local/private data."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil


def main(frontend, output):
    repo = Path(__file__).resolve().parents[2]
    receipt = json.loads((frontend / 'frontend-artifact-receipt.json').read_text(encoding='utf-8'))
    assert receipt['native_build_success'] is True
    assert receipt['upstream_commit'] == '6a18585ff4c2e5f6805f682222cfbc46dc669ef8'
    manifest_path = frontend / 'frontend-files.json'
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == receipt['build_files_manifest_sha256']
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    build = Path(receipt['build_directory'])
    assert build.is_dir()
    actual = {path.relative_to(build).as_posix(): path for path in build.rglob('*') if path.is_file()}
    assert set(actual) == set(manifest)
    for name, path in actual.items():
        assert not path.is_symlink()
        with path.open('rb') as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == manifest[name]['sha256']
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(build, output / 'build')
    bundles = {'tool-context': 'tool-context-v0.12.2', 'media-upload': 'media-upload-v0.12.2'}
    for destination, source in bundles.items():
        target = output / destination
        target.mkdir()
        for path in (repo / 'deploy/openwebui-patches' / source).iterdir():
            if path.is_file() and path.suffix in {'.py', '.json'}:
                shutil.copyfile(path, target / path.name)
    for name in ('runtime.Dockerfile', 'verify_frontend_artifact.py'):
        shutil.copyfile(Path(__file__).parent / name, output / name)
    shutil.copyfile(manifest_path, output / 'frontend-files.json')
    safe = {key: receipt[key] for key in ('upstream_version', 'upstream_commit', 'build_identity',
            'native_build_command', 'source_archive_sha256', 'input_receipt_sha256', 'frontend_sources_sha256',
            'artifact_sha256', 'build_files', 'build_uncompressed_bytes', 'build_files_manifest_sha256',
            'native_build_success', 'sourcemap')}
    (output / 'frontend-receipt.json').write_text(json.dumps(safe, indent=2), encoding='utf-8')
    print(json.dumps({'context': str(output), 'build_identity': receipt['build_identity'],
                      'frontend_files': len(actual), 'public_inputs_only': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frontend', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    main(args.frontend, args.output)
