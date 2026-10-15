"""Check exact-source installation/rejection without changing supplied sources."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

import apply_media


def verify(source):
    manifest = json.loads((apply_media.BUNDLE / 'manifest.json').read_text(encoding='utf-8'))
    assert hashlib.sha256((apply_media.BUNDLE / 'media.patch').read_bytes()).hexdigest() == manifest['patch_sha256']
    originals = {p: (source / p).read_bytes() for p in manifest['files']}
    assert all(hashlib.sha256(data).hexdigest() == manifest['files'][p]['upstream_sha256']
               for p, data in originals.items()), 'Supply pristine v0.12.2 files'
    passed = []
    with tempfile.TemporaryDirectory(prefix='media-0122-installer-') as temporary:
        root = Path(temporary)

        def restore():
            for relative, content in originals.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)

        def snapshot():
            return {p: (root / p).read_bytes() for p in originals}

        def reject(expected):
            before = snapshot()
            try:
                apply_media.apply(root)
            except RuntimeError as exc:
                assert expected in str(exc), str(exc)
                assert snapshot() == before, 'Rejected input was modified'
            else:
                raise AssertionError('Unsupported source was accepted')

        restore()
        apply_media.apply(root, check=True)
        assert snapshot() == originals
        passed.append('check-only preserves all four files')
        apply_media.apply(root)
        candidates = snapshot()
        assert all(hashlib.sha256(data).hexdigest() == manifest['files'][p]['candidate_sha256']
                   for p, data in candidates.items())
        assert 'already present' in apply_media.apply(root) and snapshot() == candidates
        passed.append('exact reviewed result and idempotent repeat')
        restore()
        first = next(iter(originals))
        (root / first).write_bytes(candidates[first])
        reject('Mixed patch state')
        restore()
        (root / first).write_bytes(originals[first] + b'\n# foreign input\n')
        reject('Unexpected source')
        restore()
        (root / first).write_bytes(originals[first].replace(b'\n', b'\r\n'))
        reject('Unexpected source')
        passed.append('mixed, foreign and newline-drift sources rejected before write')
        restore()
        apply_media.apply(root, backend_only=True)
        assert all((root / p).read_bytes() == (candidates[p] if p.startswith('backend/') else originals[p])
                   for p in originals)
        assert 'already present' in apply_media.apply(root, backend_only=True)
        passed.append('runtime backend-only mode preserves frontend source')
    assert originals == {p: (source / p).read_bytes() for p in originals}
    return passed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('upstream_source', type=Path)
    args = parser.parse_args()
    print(json.dumps({'passed': verify(args.upstream_source.resolve(strict=True)), 'supplied_source_preserved': True}))
