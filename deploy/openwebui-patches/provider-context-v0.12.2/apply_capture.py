"""Observe final serialized requests in exact OpenWebUI 0.12.2 routers."""
import argparse
import hashlib
from pathlib import Path

UPSTREAM_COMMIT = '6a18585ff4c2e5f6805f682222cfbc46dc669ef8'
SUPPORTED = {
    # Pristine v0.12.2, or the accepted Responses context overlay applied first.
    'af02463b799a817b307da5d03af25874ca14f477b883e913051b3b797d365955':
        '2fecc777ed2f835c0903f654cf9d6a0657346048e0e56815eb375b27c9010dd0',
    'a543d986125e66f5161bf60f480a6fa15bd2d95ebcac4b03b856d1ff9619f834':
        '0039f04db833b705f2e64b9ed168efdcd93bb07b699a96e5ebb898f75960a829',
}
IMPORT = b'from open_webui.utils.json_codec import JSONCodec\n'
SERIALIZE = b'    payload = JSONCodec.dumps(payload)\n'
HOOK = (
    b'    await capture_provider_context(\n'
    b'        metadata, payload, request_url,\n'
    b"        selected_model=form_data.get('model'), user_id=user.id,\n"
    b'    )\n'
)


def apply(root, *, check=False):
    path = Path(root) / 'routers/openai.py'
    source = path.read_bytes()
    digest = hashlib.sha256(source).hexdigest()
    if digest in SUPPORTED.values():
        return digest
    if digest not in SUPPORTED:
        raise RuntimeError(f'Unsupported provider router sha256={digest}')
    if source.count(IMPORT) != 1 or source.count(SERIALIZE) != 1:
        raise RuntimeError('Expected one exact native serialization point')
    updated = source.replace(
        IMPORT,
        IMPORT + b'from open_webui.utils.provider_context_capture import capture_provider_context\n',
    ).replace(SERIALIZE, SERIALIZE + HOOK)
    result = hashlib.sha256(updated).hexdigest()
    if result != SUPPORTED[digest]:
        raise RuntimeError('Unexpected provider observer result')
    compile(updated, str(path), 'exec')
    if not check:
        path.write_bytes(updated)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/app/backend/open_webui'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    print(apply(args.root, check=args.check))
