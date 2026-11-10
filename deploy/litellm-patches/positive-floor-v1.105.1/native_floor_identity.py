"""Representation-only identity for explicitly permitted disposable SDK variants.

The committed manifest owns expected source hashes. Environment selects an
explicit variant and supplies only its built image ID, never expected code.
This module and manifest are mounted read-only beside each other in /proof.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re

BASE_IMAGE = "ghcr.io/berriai/litellm:v1.105.1@sha256:b7b9e2c306343721802253d0dd9436b9634a2eb4e14da7c7cf06c5c7b7530802"
BASE_REVISION = "d665dc1a6315847fcad6cc2c1264ceb47c06abce"
VARIANT = "positive-floor-v1.105.1"
STREAM_VARIANT = "stream-usage-v1.105.1"
PROXY = "proxy/proxy_server.py"
STREAM_TARGETS = frozenset({"llms/openai/openai.py", "proxy/common_request_processing.py", "proxy/utils.py", PROXY})
SDK_FILES = frozenset({"_version.py", "_types.py", "_models.py", "_base_client.py", "_streaming.py",
                       "_legacy_response.py", "types/chat/chat_completion_chunk.py", "types/completion_usage.py"})


def load_manifest():
    value = json.loads(Path(__file__).with_name("manifest.json").read_text(encoding="utf-8"))
    assert set(value) == {"schema", "variant", "base_image", "base_revision", "target", "original_sha256",
                          "patched_sha256", "patch_sha256", "native_export_sha256", "license_sha256"}
    assert type(value["schema"]) is int and value["schema"] == 1 and value["variant"] == VARIANT
    assert value["base_image"] == BASE_IMAGE and value["base_revision"] == BASE_REVISION
    assert value["target"] == "litellm/" + PROXY
    for key in ("original_sha256", "patched_sha256", "patch_sha256", "license_sha256"):
        assert isinstance(value[key], str) and re.fullmatch("[0-9a-f]{64}", value[key])
    assert value["original_sha256"] != value["patched_sha256"]
    assert len(value["native_export_sha256"]) == 5
    assert value["native_export_sha256"][value["target"]] == value["original_sha256"]
    return value


def variant():
    value = os.environ.get("PROOF_NATIVE_VARIANT", "stock")
    assert value in ("stock", VARIANT, STREAM_VARIANT), "Unknown native SDK variant"
    return value


def image_ref():
    value = os.environ.get("PROOF_LITELLM_IMAGE", BASE_IMAGE)
    if variant() == "stock":
        assert value == BASE_IMAGE, "Stock proof requires the exact upstream image"
    else:
        assert re.fullmatch("sha256:[0-9a-f]{64}", value), "Derivative requires an immutable local image ID"
    return value


def selected_hashes(pristine):
    expected = dict(pristine)
    if variant() == STREAM_VARIANT:
        manifest = load_stream_manifest()
        for name, target in manifest["targets"].items():
            if name in expected:
                assert expected[name] == target["original_sha256"], "Stream derivative baseline differs: " + name
                expected[name] = target["patched_sha256"]
        return expected
    if variant() != "stock":
        manifest = load_manifest()
        assert expected[PROXY] == manifest["original_sha256"], "Derivative applied to another native baseline"
        expected[PROXY] = manifest["patched_sha256"]
    return expected


def identity():
    manifest = load_manifest()
    result = {"variant": variant(), "base_image": BASE_IMAGE, "base_revision": BASE_REVISION,
            "image_ref": image_ref(), "proxy_sha256": manifest["original_sha256"] if variant() == "stock" else manifest["patched_sha256"],
            "patch_sha256": None if variant() == "stock" else manifest["patch_sha256"],
            "manifest_sha256": hashlib.sha256(Path(__file__).with_name("manifest.json").read_bytes()).hexdigest()}
    if variant() == STREAM_VARIANT:
        stream = load_stream_manifest()
        result["proxy_sha256"] = stream["targets"][PROXY]["patched_sha256"]
        result["stream_manifest_sha256"] = stream_manifest_hash()
        result["stream_source_sha256"] = {name: target["patched_sha256"] for name, target in stream["targets"].items()}
        result["openai_version"] = stream["sdk"]["version"]
    return result


def inspect_sources():
    manifest = load_manifest()
    expected = selected_hashes({key.removeprefix("litellm/"): value
                                for key, value in manifest["native_export_sha256"].items()})
    package = Path(importlib.util.find_spec("litellm").origin).parent
    actual = {key: hashlib.sha256((package / key).read_bytes()).hexdigest() for key in expected}
    assert actual == expected, "Running native SDK differs from selected source artifact"
    result = {"native_sha256": actual, "native_artifact": identity()}
    if variant() == STREAM_VARIANT:
        from importlib.metadata import version
        stream = load_stream_manifest()
        sdk = Path(importlib.util.find_spec("openai").origin).parent
        observed = {name: hashlib.sha256((package / name).read_bytes()).hexdigest() for name in stream["targets"]}
        sdk_hashes = {name: hashlib.sha256((sdk / name).read_bytes()).hexdigest() for name in SDK_FILES}
        assert observed == {name: target["patched_sha256"] for name, target in stream["targets"].items()}
        assert version("openai") == stream["sdk"]["version"] and sdk_hashes == stream["sdk"]["files_sha256"]
        result.update(stream_source_sha256=observed, openai_source_sha256=sdk_hashes)
    return result


def verify_build(receipt):
    if variant() == STREAM_VARIANT:
        return _verify_stream_build(receipt)
    manifest = load_manifest()
    assert set(receipt) == {"schema", "variant", "base_revision", "base_image", "image_ref", "image_id",
                            "original_sha256", "patched_sha256", "patch_sha256", "native_export_sha256", "files_sha256"}
    assert variant() == VARIANT
    assert type(receipt["schema"]) is int and receipt["schema"] == 1 and receipt["variant"] == VARIANT
    assert receipt["base_image"] == BASE_IMAGE and receipt["base_revision"] == BASE_REVISION
    assert receipt["image_ref"] == receipt["image_id"] == image_ref()
    for key in ("original_sha256", "patched_sha256", "patch_sha256", "native_export_sha256"):
        assert receipt[key] == manifest[key], "Build receipt disagrees with committed manifest"
    root = Path(__file__).resolve().parents[3]
    required = {"scripts/goal584-budget-proof/build_native_floor_image.py",
                "deploy/litellm-patches/positive-floor-v1.105.1/manifest.json",
                "deploy/litellm-patches/positive-floor-v1.105.1/floor.patch",
                "deploy/litellm-patches/positive-floor-v1.105.1/LICENSE",
                "deploy/litellm-patches/positive-floor-v1.105.1/native_floor_identity.py",
                "scripts/goal584-budget-proof/test_native_floor_patch.py"}
    assert set(receipt["files_sha256"]) == required
    assert all(hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
               for name, digest in receipt["files_sha256"].items())
    return identity()


def stream_manifest_path():
    source = Path(__file__).resolve().parent.parent / STREAM_VARIANT / "manifest.json"
    return source if source.is_file() else Path("/usr/share/doc/goal584-stream-usage/manifest.json")


def stream_manifest_hash():
    return hashlib.sha256(stream_manifest_path().read_bytes()).hexdigest()


def load_stream_manifest():
    """One explicit stand extension; old floor manifest remains its own authority."""
    value = json.loads(stream_manifest_path().read_text(encoding="utf-8"))
    assert set(value) == {"schema", "variant", "base_image", "base_revision", "floor_manifest_sha256",
                          "patch_sha256", "sdk", "targets", "license_sha256"}
    assert type(value["schema"]) is int and value["schema"] == 1 and value["variant"] == STREAM_VARIANT
    assert value["base_image"] == BASE_IMAGE and value["base_revision"] == BASE_REVISION
    floor = load_manifest()
    assert value["floor_manifest_sha256"] == hashlib.sha256(Path(__file__).with_name("manifest.json").read_bytes()).hexdigest()
    assert value["license_sha256"] == floor["license_sha256"]
    assert set(value["patch_sha256"]) == {"raw-usage.patch", "core-cancel.patch"}
    assert set(value["sdk"]) == {"version", "files_sha256"} and isinstance(value["sdk"]["version"], str)
    assert set(value["sdk"]["files_sha256"]) == SDK_FILES and set(value["targets"]) == STREAM_TARGETS
    hashes = [*value["patch_sha256"].values(), *value["sdk"]["files_sha256"].values()]
    for name, target in value["targets"].items():
        expected = {"original_sha256", "patched_sha256", "changed_functions", "added_functions", "signature_changes"}
        assert set(target) == expected | ({"floor_patched_sha256"} if name == PROXY else set())
        if name == PROXY:
            assert target["original_sha256"] == floor["original_sha256"] and target["floor_patched_sha256"] == floor["patched_sha256"]
        assert target["original_sha256"] != target["patched_sha256"]
        hashes.extend((target["original_sha256"], target["patched_sha256"]))
        for key in ("changed_functions", "added_functions", "signature_changes"):
            assert isinstance(target[key], list) and len(target[key]) == len(set(target[key]))
            assert all(isinstance(name, str) and re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", name) for name in target[key])
        assert set(target["signature_changes"]) <= set(target["changed_functions"])
    assert all(isinstance(digest, str) and re.fullmatch("[0-9a-f]{64}", digest) for digest in hashes)
    return value


def _verify_stream_build(receipt):
    floor, stream = load_manifest(), load_stream_manifest()
    original = {"schema", "variant", "base_revision", "base_image", "image_ref", "image_id",
                "original_sha256", "patched_sha256", "patch_sha256", "native_export_sha256", "files_sha256"}
    assert set(receipt) == original | {"stream_manifest_sha256", "stream_source_sha256", "openai_version", "openai_source_sha256"}
    assert receipt["schema"] == 1 and receipt["variant"] == STREAM_VARIANT
    assert receipt["base_image"] == BASE_IMAGE and receipt["base_revision"] == BASE_REVISION
    assert receipt["image_ref"] == receipt["image_id"] == image_ref()
    for key in ("original_sha256", "patch_sha256", "native_export_sha256"):
        assert receipt[key] == floor[key]
    assert receipt["patched_sha256"] == stream["targets"][PROXY]["patched_sha256"]
    assert receipt["stream_manifest_sha256"] == stream_manifest_hash()
    assert receipt["stream_source_sha256"] == {name: target["patched_sha256"] for name, target in stream["targets"].items()}
    assert receipt["openai_version"] == stream["sdk"]["version"] and receipt["openai_source_sha256"] == stream["sdk"]["files_sha256"]
    root = Path(__file__).resolve().parents[3]
    required = {"scripts/goal584-budget-proof/build_native_floor_image.py",
                "scripts/goal584-budget-proof/test_native_floor_patch.py",
                *("deploy/litellm-patches/positive-floor-v1.105.1/" + name for name in
                  ("manifest.json", "floor.patch", "LICENSE", "native_floor_identity.py")),
                *("deploy/litellm-patches/stream-usage-v1.105.1/" + name for name in
                  ("manifest.json", "raw-usage.patch", "core-cancel.patch", "LICENSE"))}
    assert set(receipt["files_sha256"]) == required
    assert all(hashlib.sha256((root / name).read_bytes()).hexdigest() == digest for name, digest in receipt["files_sha256"].items())
    return identity()
