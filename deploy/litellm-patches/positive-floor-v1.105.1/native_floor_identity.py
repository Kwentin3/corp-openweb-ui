"""Representation-only identity for the two permitted disposable SDK variants.

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
PROXY = "proxy/proxy_server.py"


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
    assert value in ("stock", VARIANT), "Unknown native SDK variant"
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
    if variant() != "stock":
        manifest = load_manifest()
        assert expected[PROXY] == manifest["original_sha256"], "Derivative applied to another native baseline"
        expected[PROXY] = manifest["patched_sha256"]
    return expected


def identity():
    manifest = load_manifest()
    return {"variant": variant(), "base_image": BASE_IMAGE, "base_revision": BASE_REVISION,
            "image_ref": image_ref(), "proxy_sha256": manifest["original_sha256"] if variant() == "stock" else manifest["patched_sha256"],
            "patch_sha256": None if variant() == "stock" else manifest["patch_sha256"],
            "manifest_sha256": hashlib.sha256(Path(__file__).with_name("manifest.json").read_bytes()).hexdigest()}


def inspect_sources():
    manifest = load_manifest()
    expected = selected_hashes({key.removeprefix("litellm/"): value
                                for key, value in manifest["native_export_sha256"].items()})
    package = Path(importlib.util.find_spec("litellm").origin).parent
    actual = {key: hashlib.sha256((package / key).read_bytes()).hexdigest() for key in expected}
    assert actual == expected, "Running native SDK differs from selected source artifact"
    return {"native_sha256": actual, "native_artifact": identity()}


def verify_build(receipt):
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
