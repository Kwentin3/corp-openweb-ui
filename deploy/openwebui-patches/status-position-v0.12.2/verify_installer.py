"""Check exact-source installation/rejection without modifying supplied sources."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

import apply_status


def verify(source: Path) -> list[str]:
    manifest = json.loads((apply_status.BUNDLE / 'manifest.json').read_text(encoding='utf-8'))
    paths = [apply_status.SOURCE, *manifest['build_identity']]
    originals = {p: (source / p).read_bytes() for p in paths}
    assert hashlib.sha256(originals[apply_status.SOURCE]).hexdigest() == manifest['files'][apply_status.SOURCE]['upstream_sha256']
    passed = []
    with tempfile.TemporaryDirectory(prefix='status-0122-installer-') as temporary:
        root = Path(temporary)

        def restore():
            for relative, content in originals.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)

        def snapshot():
            return {p: (root / p).read_bytes() for p in paths}

        def reject():
            before = snapshot()
            try:
                apply_status.apply(root)
            except RuntimeError:
                assert snapshot() == before, 'Rejected source was modified'
            else:
                raise AssertionError('Unsupported source was accepted')

        restore()
        apply_status.apply(root, check=True)
        assert snapshot() == originals
        apply_status.apply(root)
        candidates = snapshot()
        assert hashlib.sha256(candidates[apply_status.SOURCE]).hexdigest() == manifest['files'][apply_status.SOURCE]['candidate_sha256']
        assert all(candidates[p] == originals[p] for p in manifest['build_identity'])
        assert 'already present' in apply_status.apply(root) and snapshot() == candidates
        passed.append('check-only, exact candidate, unrelated files preserved, idempotent repeat')
        for mutated in (originals[apply_status.SOURCE] + b'\n<!-- foreign -->\n',
                        originals[apply_status.SOURCE].replace(b'\n', b'\r\n')):
            restore()
            (root / apply_status.SOURCE).write_bytes(mutated)
            reject()
        for identity in manifest['build_identity']:
            restore()
            (root / identity).write_bytes(originals[identity] + b'\n')
            reject()
        passed.append('foreign source, newline drift and wrong build identity rejected before write')
    assert originals == {p: (source / p).read_bytes() for p in paths}
    return passed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('upstream_source', type=Path)
    args = parser.parse_args()
    print(json.dumps({'passed': verify(args.upstream_source.resolve(strict=True)), 'supplied_source_preserved': True}))
