#!/usr/bin/env python3
"""Build the explicitly reviewed, disposable two-function LiteLLM derivative.

Exports source from the pinned image, applies git's patch format, checks the
complete AST delta, and records the local immutable image ID. No running proxy,
credentials, database, provider or production route is accessed.
"""
from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PATCH_DIR = ROOT / "deploy/litellm-patches/positive-floor-v1.105.1"
sys.path.insert(0, str(PATCH_DIR))
import native_floor_identity as native_identity

BASE_IMAGE = native_identity.BASE_IMAGE
BASE_REVISION = native_identity.BASE_REVISION
TARGET = "litellm/proxy/proxy_server.py"
FUNCTIONS = {"get_current_spend", "_authoritative_floor_spend"}


def sha(value):
    return hashlib.sha256(value).hexdigest()


def validate_delta(before, after):
    old, new = ast.parse(before), ast.parse(after)
    assert len(old.body) == len(new.body), "Native top-level structure changed"
    changed = set()
    for first, second in zip(old.body, new.body):
        if ast.dump(first) == ast.dump(second):
            continue
        assert isinstance(first, ast.AsyncFunctionDef) and isinstance(second, ast.AsyncFunctionDef)
        assert first.name == second.name and first.name in FUNCTIONS, "Native change exceeds two approved functions"
        assert [ast.dump(item) for item in first.decorator_list] == [ast.dump(item) for item in second.decorator_list]
        if first.name == "get_current_spend":
            assert ast.dump(first.args) == ast.dump(second.args), "Public admission signature changed"
        changed.add(first.name)
    assert changed == FUNCTIONS, "Expected exactly the two reviewed native functions"
    compile(after, TARGET, "exec")


def run(argv, **kwargs):
    return subprocess.check_output(argv, timeout=kwargs.pop("timeout", 180), **kwargs)


def prepare(context, exported):
    manifest = native_identity.load_manifest()
    patch = (PATCH_DIR / "floor.patch").read_bytes()
    license_bytes = (PATCH_DIR / "LICENSE").read_bytes()
    assert sha(patch) == manifest["patch_sha256"] and sha(license_bytes) == manifest["license_sha256"]
    expected = manifest["native_export_sha256"]
    assert len(expected) == 5 and expected[TARGET] == manifest["original_sha256"]
    assert set(exported) == set(expected), "Incomplete native image export"
    for name, digest in expected.items():
        assert name.startswith("litellm/") and ".." not in Path(name).parts and re.fullmatch("[0-9a-f]{64}", digest)
        content = base64.b64decode(exported[name], validate=True)
        assert sha(content) == digest, "Pinned image source mismatch: " + name
        destination = context / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    original = (context / TARGET).read_bytes()
    apply = ["git", "-c", "core.autocrlf=false", "-c", "core.eol=lf", "apply"]
    run([*apply, "--check", str(PATCH_DIR / "floor.patch")], cwd=context)
    run([*apply, str(PATCH_DIR / "floor.patch")], cwd=context)
    patched = (context / TARGET).read_bytes()
    assert sha(patched) == manifest["patched_sha256"]
    validate_delta(original, patched)
    (context / "LICENSE").write_bytes(license_bytes)
    (context / "manifest.json").write_bytes((PATCH_DIR / "manifest.json").read_bytes())
    return manifest, original


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    assert args.context.is_absolute() and not args.context.exists(), "Use a new dedicated build context"
    assert not args.receipt.exists() and args.receipt.parent.is_dir()
    args.context.mkdir(mode=0o700, parents=True)
    manifest = native_identity.load_manifest()
    paths = list(manifest["native_export_sha256"])
    export = ("import base64,importlib.util,json,pathlib,sys;"
              "root=pathlib.Path(importlib.util.find_spec('litellm').origin).parent.parent;"
              "print(json.dumps({p:base64.b64encode((root/p).read_bytes()).decode('ascii') for p in sys.argv[1:]}))")
    exported = json.loads(run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "python",
                              BASE_IMAGE, "-B", "-c", export, *paths], timeout=240))
    manifest, original = prepare(args.context, exported)
    # Tests export companions under their original litellm/... paths. Keep the
    # pristine target separately; the build context target is now patched.
    originals = args.context / "original"
    for name in paths:
        destination = originals / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(base64.b64decode(exported[name], validate=True))
    environment = {**os.environ, "GOAL584_NATIVE_FLOOR_SOURCE": str(originals / TARGET)}
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "scripts/goal584-budget-proof",
                    "-p", "test_native_floor_patch.py", "-v"], cwd=ROOT, env=environment, check=True, timeout=120)
    # No downloads or package changes inside the image. Recheck the actual
    # base bytes before copying, even though the host already exported them.
    install = ("import hashlib,importlib.util,pathlib;"
               "p=pathlib.Path(importlib.util.find_spec('litellm').origin).parent/'proxy/proxy_server.py';"
               f"assert hashlib.sha256(p.read_bytes()).hexdigest()=={manifest['original_sha256']!r};"
               "b=pathlib.Path('/tmp/goal584-proxy_server.py').read_bytes();"
               f"assert hashlib.sha256(b).hexdigest()=={manifest['patched_sha256']!r};"
               "compile(b,str(p),'exec');p.write_bytes(b);pathlib.Path('/tmp/goal584-proxy_server.py').unlink()")
    dockerfile = (f"FROM {BASE_IMAGE}\n"
                  f"LABEL org.alpha-soft.goal584.native-variant={manifest['variant']}\n"
                  f"COPY {TARGET} /tmp/goal584-proxy_server.py\n"
                  "COPY LICENSE manifest.json /usr/share/doc/goal584-native-floor/\n"
                  "RUN python -B -c " + json.dumps(install) + "\n")
    (args.context / "Dockerfile").write_text(dockerfile, encoding="utf-8")
    iidfile = args.context / "image-id.txt"
    subprocess.run(["docker", "build", "--network=none", "--iidfile", str(iidfile), str(args.context)],
                   check=True, timeout=300)
    image_id = iidfile.read_text(encoding="ascii").strip()
    assert re.fullmatch("sha256:[0-9a-f]{64}", image_id), "Derivative image ID missing"
    image = json.loads(run(["docker", "image", "inspect", image_id]))[0]
    assert image["Id"] == image_id and image["Config"]["Labels"]["org.alpha-soft.goal584.native-variant"] == manifest["variant"]
    verify = ("import hashlib,importlib.util,json,pathlib;"
              "p=pathlib.Path(importlib.util.find_spec('litellm').origin).parent/'proxy/proxy_server.py';"
              "print(json.dumps({'proxy_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),"
              "'manifest':json.loads(pathlib.Path('/usr/share/doc/goal584-native-floor/manifest.json').read_text())}))")
    actual = json.loads(run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "python", image_id, "-B", "-c", verify]))
    assert actual == {"proxy_sha256": manifest["patched_sha256"], "manifest": manifest}
    receipt = {"schema": 1, "variant": manifest["variant"], "base_revision": BASE_REVISION,
               "base_image": BASE_IMAGE, "image_ref": image_id, "image_id": image_id,
               "original_sha256": sha(original), "patched_sha256": actual["proxy_sha256"],
               "patch_sha256": manifest["patch_sha256"], "native_export_sha256": manifest["native_export_sha256"],
               "files_sha256": {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p.read_bytes()) for p in (
                   Path(__file__), PATCH_DIR / "manifest.json", PATCH_DIR / "floor.patch", PATCH_DIR / "LICENSE",
                   PATCH_DIR / "native_floor_identity.py", ROOT / "scripts/goal584-budget-proof/test_native_floor_patch.py")}}
    args.receipt.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"variant": manifest["variant"], "image_ref": image_id, "patched_sha256": actual["proxy_sha256"]}))


if __name__ == "__main__":
    main()
