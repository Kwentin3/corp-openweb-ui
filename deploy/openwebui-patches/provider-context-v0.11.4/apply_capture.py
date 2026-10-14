"""Apply the final-body observer to exact OpenWebUI 0.11.4 source only."""
import argparse
import hashlib
from pathlib import Path

ORIGINAL = 'c6b514f057e9273206cd7d61e064e000ffe4db5cd5e06c0379a408e9aa1e964a'
PATCHED = '18dab762a43165934aba9b2f3c83d13300c69b1598b2ad4559bc020085fb4c17'


def apply(root):
    path = Path(root) / 'routers/openai.py'
    source = path.read_bytes()
    digest = hashlib.sha256(source).hexdigest()
    if digest == PATCHED:
        return
    if digest != ORIGINAL:
        raise RuntimeError(f'Unsupported provider router sha256={digest}')
    old_import = b'from open_webui.utils.json_codec import JSONCodec\n'
    old_send = b'    payload = JSONCodec.dumps(payload)\n'
    if source.count(old_import) != 1 or source.count(old_send) != 1:
        raise RuntimeError('Expected one exact native request serialization point')
    updated = source.replace(old_import, old_import + b'from open_webui.utils.provider_context_capture import capture_provider_context\n')
    updated = updated.replace(old_send, old_send + b'    capture_provider_context(metadata, payload, request_url)\n')
    if hashlib.sha256(updated).hexdigest() != PATCHED:
        raise RuntimeError('Unexpected provider observer result')
    compile(updated, str(path), 'exec')
    path.write_bytes(updated)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/app/backend/open_webui'))
    apply(parser.parse_args().root)
