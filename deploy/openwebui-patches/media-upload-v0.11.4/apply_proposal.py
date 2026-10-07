"""Apply this exact proposal to its pinned upstream source checkout, or check only."""
import argparse
import hashlib
import json
import pathlib
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('source_root', type=pathlib.Path)
parser.add_argument('--check', action='store_true')
args = parser.parse_args()
root = args.source_root.resolve(strict=True)
bundle = pathlib.Path(__file__).resolve().parent
manifest = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8'))
if subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip() != manifest['upstream_commit']:
    raise SystemExit('Source checkout is not the pinned upstream commit')
patch = bundle / 'proposed.patch'
if hashlib.sha256(patch.read_bytes()).hexdigest() != manifest['patch_sha256']:
    raise SystemExit('Patch differs from the reviewed proposal')
states = []
for relative, expected in manifest['files'].items():
    source = (root / relative).resolve(strict=True)
    if not source.is_relative_to(root):
        raise SystemExit('Proposal path leaves source checkout')
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest == expected['upstream_sha256']:
        states.append('upstream')
    elif digest == expected['candidate_sha256']:
        states.append('candidate')
    else:
        raise SystemExit('Unexpected source at ' + relative)
if len(set(states)) != 1:
    raise SystemExit('Mixed patch state; do not partially apply or guess')
if states[0] == 'candidate':
    print('Exact proposal already present; no changes')
else:
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--check', str(patch)], cwd=root, check=True)
    if args.check:
        print('Exact upstream identity and diff applicability verified; no changes')
    else:
        subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', str(patch)], cwd=root, check=True)
        for relative, expected in manifest['files'].items():
            if hashlib.sha256((root / relative).read_bytes()).hexdigest() != expected['candidate_sha256']:
                raise SystemExit('Applied result differs at ' + relative)
        print('Exact four-file proposal applied and verified')
