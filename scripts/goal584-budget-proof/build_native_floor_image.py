#!/usr/bin/env python3
"""Build an explicitly selected, reviewed disposable LiteLLM derivative.

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
STREAM_DIR = ROOT / "deploy/litellm-patches/stream-usage-v1.105.1"
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
    owner = os.environ.get("GOAL584_NATIVE_BUILD_OWNER")
    if owner and argv[:2] == ["docker", "run"]:
        assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", owner), "Invalid native build owner label"
        argv = [*argv[:2], "--label", "goal584.owner=" + owner, *argv[2:]]
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


def validate_stream_delta(before, after, target, declaration):
    """Constrain only the explicitly reviewed extension source files."""
    old, new = ast.parse(before), ast.parse(after)
    def functions(tree):
        result = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                result[node.name] = node
            elif isinstance(node, ast.ClassDef):
                result.update({node.name + "." + item.name: item for item in node.body
                               if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))})
        return result
    first, second = functions(old), functions(new)
    changed, added = set(declaration["changed_functions"]), set(declaration["added_functions"])
    assert set(first) <= set(second) and set(second) - set(first) == added
    assert {name for name in first if ast.dump(first[name]) != ast.dump(second[name])} == changed
    for name in changed:
        assert type(first[name]) is type(second[name])
        assert [ast.dump(item) for item in first[name].decorator_list] == [ast.dump(item) for item in second[name].decorator_list]
        if name not in declaration["signature_changes"]:
            assert ast.dump(first[name].args) == ast.dump(second[name].args)
        first[name].body = second[name].body = [ast.Pass()]
        if name in declaration["signature_changes"]:
            first[name].args = second[name].args
    for node in new.body:
        if isinstance(node, ast.ClassDef):
            node.body = [item for item in node.body if node.name + "." + getattr(item, "name", "") not in added]
    new.body = [node for node in new.body if getattr(node, "name", "") not in added]
    assert ast.dump(old) == ast.dump(new), "Stream change exceeds the reviewed function set: " + target
    compile(after, target, "exec")


def export_stream_base(args, stream, floor):
    expected = {**floor["native_export_sha256"],
                **{"litellm/" + name: target["original_sha256"] for name, target in stream["targets"].items()},
                **{"openai/" + name: digest for name, digest in stream["sdk"]["files_sha256"].items()}}
    export = """import base64,importlib.metadata,importlib.util,json,pathlib,sys
roots={};versions={};files={};errors={}
for name in ('litellm','openai','httpx'):
 try:
  versions[name]=importlib.metadata.version(name)
  spec=importlib.util.find_spec(name)
  if name!='httpx': roots[name]=pathlib.Path(spec.origin).parent
 except (ImportError,AttributeError,ValueError): errors[name]='package_unavailable'
for path in sys.argv[1:]:
 try:
  package,relative=path.split('/',1)
  files[path]=base64.b64encode((roots[package]/relative).read_bytes()).decode('ascii')
 except (KeyError,OSError): errors[path]='source_unavailable'
print(json.dumps({'files':files,'errors':errors,'versions':versions,'python':sys.version.split()[0],
 'package_paths':{name:str(path) for name,path in roots.items()}}))"""
    actual = json.loads(run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "python",
                             BASE_IMAGE, "-B", "-c", export, *expected], timeout=240))
    exported = actual.pop("files")
    observed = {**actual, "base_image": BASE_IMAGE,
                "source_sha256": {name: sha(base64.b64decode(content, validate=True)) for name, content in exported.items()}}
    # Preserve actual version/hash mismatch evidence before comparing reference pins.
    args.receipt.with_suffix(".sdk-observed.json").write_text(json.dumps(observed, indent=2) + "\n", encoding="utf-8")
    assert not actual["errors"] and set(exported) == set(expected), "Incomplete stock SDK export; see sdk-observed receipt"
    assert actual["versions"].get("litellm") == "1.105.1" and actual["versions"].get("openai") == stream["sdk"]["version"], "Stock SDK version mismatch; no upgrade is permitted"
    assert observed["source_sha256"] == expected, "Stock SDK/source mismatch; inspect exported identity, do not upgrade"
    return exported


def prepare_stream(context, exported, stream):
    for name in (*("litellm/" + key for key in stream["targets"]),
                 *("openai/" + key for key in stream["sdk"]["files_sha256"])):
        path = context / name
        if name == TARGET:
            assert sha(path.read_bytes()) == stream["targets"][native_identity.PROXY]["floor_patched_sha256"]
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(exported[name], validate=True))
    originals = {name: (context / "litellm" / name).read_bytes() for name in stream["targets"]}
    apply = ["git", "-c", "core.autocrlf=false", "-c", "core.eol=lf", "apply"]
    for name, digest in stream["patch_sha256"].items():
        assert sha((STREAM_DIR / name).read_bytes()) == digest
        run([*apply, "--check", str(STREAM_DIR / name)], cwd=context)
        run([*apply, str(STREAM_DIR / name)], cwd=context)
    for name, declaration in stream["targets"].items():
        patched = (context / "litellm" / name).read_bytes()
        assert sha(patched) == declaration["patched_sha256"]
        validate_stream_delta(originals[name], patched, name, declaration)
    assert sha((STREAM_DIR / "LICENSE").read_bytes()) == stream["license_sha256"]
    (context / "stream-usage-manifest.json").write_bytes((STREAM_DIR / "manifest.json").read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--variant", choices=(native_identity.VARIANT, native_identity.STREAM_VARIANT),
                        default=native_identity.VARIANT)
    args = parser.parse_args()
    assert args.context.is_absolute() and not args.context.exists(), "Use a new dedicated build context"
    assert not args.receipt.exists() and args.receipt.parent.is_dir()
    args.context.mkdir(mode=0o700, parents=True)
    manifest = native_identity.load_manifest()
    stream = native_identity.load_stream_manifest() if args.variant == native_identity.STREAM_VARIANT else None
    paths = list(manifest["native_export_sha256"])
    export = ("import base64,importlib.util,json,pathlib,sys;"
              "root=pathlib.Path(importlib.util.find_spec('litellm').origin).parent.parent;"
              "print(json.dumps({p:base64.b64encode((root/p).read_bytes()).decode('ascii') for p in sys.argv[1:]}))")
    exported = (export_stream_base(args, stream, manifest) if stream else
                json.loads(run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "python",
                                BASE_IMAGE, "-B", "-c", export, *paths], timeout=240)))
    manifest, original = prepare(args.context, {name: exported[name] for name in paths} if stream else exported)
    if stream:
        (args.context / "floor-proxy_server.py").write_bytes((args.context / TARGET).read_bytes())
        prepare_stream(args.context, exported, stream)
    # Tests export companions under their original litellm/... paths. Keep the
    # pristine target separately; the build context target is now patched.
    originals = args.context / "original"
    for name in exported:
        destination = originals / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(base64.b64decode(exported[name], validate=True))
    environment = {**os.environ, "GOAL584_NATIVE_FLOOR_SOURCE": str(originals / TARGET)}
    if stream:
        environment["PROOF_NATIVE_VARIANT"] = native_identity.VARIANT
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
    extra_copy = ""
    if stream:
        extras = {name: [value["original_sha256"], value["patched_sha256"], "/tmp/goal584-stream-" + str(index) + ".py"]
                  for index, (name, value) in enumerate(stream["targets"].items())}
        prefix = ("import importlib.metadata;"
                  "root=pathlib.Path(importlib.util.find_spec('litellm').origin).parent;"
                  "sdk=pathlib.Path(importlib.util.find_spec('openai').origin).parent;"
                  f"assert importlib.metadata.version('openai')=={stream['sdk']['version']!r};"
                  f"sdk_pins={stream['sdk']['files_sha256']!r};"
                  "assert all(hashlib.sha256((sdk/n).read_bytes()).hexdigest()==h for n,h in sdk_pins.items());"
                  f"extras={extras!r};"
                  "assert all(hashlib.sha256((root/n).read_bytes()).hexdigest()==v[0] for n,v in extras.items());"
                  "assert all(hashlib.sha256(pathlib.Path(v[2]).read_bytes()).hexdigest()==v[1] for v in extras.values());"
                  "[compile(pathlib.Path(v[2]).read_bytes(),n,'exec') for n,v in extras.items()];")
        install = ("import hashlib,importlib.util,pathlib;" + prefix + install
                   + f";assert hashlib.sha256((root/{native_identity.PROXY!r}).read_bytes()).hexdigest()=={manifest['patched_sha256']!r}"
                   + ";[(root/n).write_bytes(pathlib.Path(v[2]).read_bytes()) for n,v in extras.items()];[pathlib.Path(v[2]).unlink() for v in extras.values()]")
        extra_copy = "".join(f"COPY litellm/{name} {values[2]}\n" for name, values in extras.items())
        extra_copy += "COPY stream-usage-manifest.json /usr/share/doc/goal584-stream-usage/manifest.json\nCOPY LICENSE /usr/share/doc/goal584-stream-usage/LICENSE\n"
    dockerfile = (f"FROM {BASE_IMAGE}\n"
                  f"LABEL org.alpha-soft.goal584.native-variant={args.variant}\n"
                  f"COPY {'floor-proxy_server.py' if stream else TARGET} /tmp/goal584-proxy_server.py\n"
                  "COPY LICENSE manifest.json /usr/share/doc/goal584-native-floor/\n"
                  + extra_copy +
                  "RUN python -B -c " + json.dumps(install) + "\n")
    (args.context / "Dockerfile").write_text(dockerfile, encoding="utf-8")
    iidfile = args.context / "image-id.txt"
    subprocess.run(["docker", "build", "--network=none", "--iidfile", str(iidfile), str(args.context)],
                   check=True, timeout=300)
    image_id = iidfile.read_text(encoding="ascii").strip()
    assert re.fullmatch("sha256:[0-9a-f]{64}", image_id), "Derivative image ID missing"
    image = json.loads(run(["docker", "image", "inspect", image_id]))[0]
    assert image["Id"] == image_id and image["Config"]["Labels"]["org.alpha-soft.goal584.native-variant"] == args.variant
    verify = ("import hashlib,importlib.util,json,pathlib;"
              "p=pathlib.Path(importlib.util.find_spec('litellm').origin).parent/'proxy/proxy_server.py';"
              "print(json.dumps({'proxy_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),"
              "'manifest':json.loads(pathlib.Path('/usr/share/doc/goal584-native-floor/manifest.json').read_text())}))")
    actual = json.loads(run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "python", image_id, "-B", "-c", verify]))
    proxy_digest = stream["targets"][native_identity.PROXY]["patched_sha256"] if stream else manifest["patched_sha256"]
    assert actual == {"proxy_sha256": proxy_digest, "manifest": manifest}
    receipt = {"schema": 1, "variant": args.variant, "base_revision": BASE_REVISION,
               "base_image": BASE_IMAGE, "image_ref": image_id, "image_id": image_id,
               "original_sha256": sha(original), "patched_sha256": actual["proxy_sha256"],
               "patch_sha256": manifest["patch_sha256"], "native_export_sha256": manifest["native_export_sha256"],
               "files_sha256": {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p.read_bytes()) for p in (
                   Path(__file__), PATCH_DIR / "manifest.json", PATCH_DIR / "floor.patch", PATCH_DIR / "LICENSE",
                   PATCH_DIR / "native_floor_identity.py", ROOT / "scripts/goal584-budget-proof/test_native_floor_patch.py")}}
    if stream:
        check = ("import hashlib,importlib.metadata,importlib.util,json,pathlib;"
                 "root=pathlib.Path(importlib.util.find_spec('litellm').origin).parent;"
                 "sdk=pathlib.Path(importlib.util.find_spec('openai').origin).parent;"
                 f"targets={list(stream['targets'])!r};sdk_files={list(stream['sdk']['files_sha256'])!r};"
                 "print(json.dumps({'stream_source_sha256':{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in targets},"
                 "'openai_source_sha256':{n:hashlib.sha256((sdk/n).read_bytes()).hexdigest() for n in sdk_files},"
                 "'openai_version':importlib.metadata.version('openai'),"
                 "'manifest':json.loads(pathlib.Path('/usr/share/doc/goal584-stream-usage/manifest.json').read_text())}))")
        observed = json.loads(run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "python", image_id, "-B", "-c", check]))
        assert observed == {"stream_source_sha256": {name: target["patched_sha256"] for name, target in stream["targets"].items()},
                            "openai_source_sha256": stream["sdk"]["files_sha256"], "openai_version": stream["sdk"]["version"], "manifest": stream}
        observed.pop("manifest")
        receipt.update(observed, stream_manifest_sha256=sha((STREAM_DIR / "manifest.json").read_bytes()))
        receipt["files_sha256"].update({str((STREAM_DIR / name).relative_to(ROOT)).replace('\\', '/'): sha((STREAM_DIR / name).read_bytes())
                                      for name in ("manifest.json", "raw-usage.patch", "core-cancel.patch", "LICENSE")})
    args.receipt.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"variant": args.variant, "image_ref": image_id, "patched_sha256": actual["proxy_sha256"]}))


if __name__ == "__main__":
    main()
