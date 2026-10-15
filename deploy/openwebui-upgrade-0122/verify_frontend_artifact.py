"""Check complete frontend bytes and native build identity inside the image."""
import hashlib
import json
import os
from pathlib import Path

package = Path('/usr/local/lib/openwebui-media-upload')
receipt = json.loads((package / 'frontend-receipt.json').read_text())
manifest = json.loads((package / 'frontend-files.json').read_text())
root = Path('/app/build')
assert receipt['upstream_commit'] == '6a18585ff4c2e5f6805f682222cfbc46dc669ef8'
assert receipt['build_identity'] == os.environ['WEBUI_BUILD_HASH']
assert json.loads((root / '_app/version.json').read_text())['version'] == receipt['build_identity']
actual = {path.relative_to(root).as_posix(): path for path in root.rglob('*') if path.is_file()}
assert set(actual) == set(manifest), 'Frontend files differ from the reviewed complete build'
for name, path in actual.items():
    assert not path.is_symlink(), 'Unexpected frontend link'
    expected = manifest[name]
    assert path.stat().st_size == expected['bytes']
    with path.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == expected['sha256'], name
print(json.dumps({'frontend_files': len(actual), 'native_build_hash': receipt['build_identity'],
                  'complete_manifest': 'verified'}))
