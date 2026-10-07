"""Exercise the approved installer against an actual pinned upstream checkout.

The supplied checkout is preserved. Only a disposable Git worktree is changed.
"""
import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('upstream_source', type=pathlib.Path)
upstream = parser.parse_args().upstream_source.resolve(strict=True)
bundle = pathlib.Path(__file__).resolve().parent
manifest = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8'))
commit = manifest['upstream_commit']


def git(*arguments, cwd=upstream):
    return subprocess.check_output(['git', *arguments], cwd=cwd, stderr=subprocess.PIPE)


assert git('rev-parse', 'HEAD').decode().strip() == commit
original = {p: git('show', commit + ':' + p) for p in manifest['files']}
supplied = {p: (upstream / p).read_bytes() for p in original}
assert all(hashlib.sha256(b).hexdigest() == manifest['files'][p]['upstream_sha256'] for p, b in original.items())
cases = []
with tempfile.TemporaryDirectory(prefix='media-installer-contract-') as temporary:
    temporary_root = pathlib.Path(temporary).resolve()
    target = temporary_root / 'source'
    assert target.resolve().parent == temporary_root

    def snapshot():
        return {p: (target / p).read_bytes() for p in original}

    def restore():
        for p, data in original.items():
            (target / p).write_bytes(data)

    def invoke(*options, bundle_root=bundle, autocrlf=None):
        environment = dict(os.environ)
        if autocrlf is not None:
            environment.update(GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='core.autocrlf', GIT_CONFIG_VALUE_0=autocrlf)
        return subprocess.run([sys.executable, str(bundle_root / 'apply_proposal.py'), str(target), *options], capture_output=True, text=True, env=environment)

    git('-c', 'core.autocrlf=false', 'worktree', 'add', '--detach', str(target), commit)
    try:
        assert snapshot() == original
        checked = invoke('--check')
        assert checked.returncode == 0 and snapshot() == original, (checked.stdout, checked.stderr)
        cases.append('check-only preserves source')
        applied = invoke()
        assert applied.returncode == 0, (applied.stdout, applied.stderr)
        candidate = snapshot()
        assert all(hashlib.sha256(b).hexdigest() == manifest['files'][p]['candidate_sha256'] for p, b in candidate.items())
        cases.append('exact reviewed result')
        repeated = invoke()
        assert repeated.returncode == 0 and snapshot() == candidate and 'already present' in repeated.stdout
        cases.append('idempotent repeat')
        restore()
        converted = invoke(autocrlf='true')
        assert converted.returncode == 0 and snapshot() == candidate, (converted.stdout, converted.stderr)
        cases.append('exact reviewed bytes with caller autocrlf enabled')
        restore()
        first = next(iter(original))
        (target / first).write_bytes(candidate[first])
        before = snapshot()
        mixed = invoke()
        assert mixed.returncode != 0 and 'Mixed patch state' in mixed.stderr and snapshot() == before
        cases.append('mixed state rejected before write')
        restore()
        (target / first).write_bytes(original[first] + b'\n# Foreign test fixture\n')
        before = snapshot()
        foreign = invoke()
        assert foreign.returncode != 0 and 'Unexpected source' in foreign.stderr and snapshot() == before
        cases.append('foreign source rejected before write')
        restore()
        altered_bundle = temporary_root / 'altered-bundle'
        altered_bundle.mkdir()
        assert altered_bundle.resolve().parent == temporary_root
        for name in ['apply_proposal.py', 'manifest.json', 'proposed.patch']:
            (altered_bundle / name).write_bytes((bundle / name).read_bytes())
        patch = altered_bundle / 'proposed.patch'
        patch.write_bytes(patch.read_bytes() + b'\n')
        altered = invoke(bundle_root=altered_bundle)
        assert altered.returncode != 0 and 'Patch differs' in altered.stderr and snapshot() == original
        cases.append('altered patch rejected before write')
        git('-c', 'user.name=Installer fixture', '-c', 'user.email=fixture@localhost', '-c', 'commit.gpgsign=false', 'commit', '--allow-empty', '-m', 'Disposable identity fixture', cwd=target)
        before = snapshot()
        wrong_commit = invoke()
        assert wrong_commit.returncode != 0 and 'not the pinned upstream commit' in wrong_commit.stderr and snapshot() == before
        cases.append('different commit rejected before write')
        git('switch', '--detach', commit, cwd=target)
    finally:
        restore()
        assert target.resolve().parent == temporary_root
        assert not git('status', '--porcelain', cwd=target).strip(), 'Unexpected work retained in probe'
        git('worktree', 'remove', str(target))
assert git('rev-parse', 'HEAD').decode().strip() == commit
assert supplied == {p: (upstream / p).read_bytes() for p in original}
print(json.dumps({'upstream_commit': commit, 'patch_sha256': manifest['patch_sha256'], 'passed': cases, 'supplied_checkout_preserved': True}))
