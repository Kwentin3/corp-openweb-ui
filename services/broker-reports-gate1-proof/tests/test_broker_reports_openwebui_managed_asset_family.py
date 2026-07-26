from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import jsonschema
import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
ASSET_ROOT = SERVICE_ROOT / "managed_assets"
MANIFEST_PATH = (
    ASSET_ROOT / "broker_reports_financial_domain_assets.v1.manifest.json"
)
MANIFEST_SCHEMA_PATH = (
    ASSET_ROOT
    / "broker_reports_financial_domain_assets.v1.manifest.schema.json"
)
SKILL_PATH = (
    ASSET_ROOT
    / "skills"
    / "broker_reports_financial_domain_skill.v1.md"
)
PROMPT_PATH = (
    ASSET_ROOT
    / "prompts"
    / "broker_reports_gate2_financial_matching_prompt.v1.md"
)
TOOL_PATH = (
    ASSET_ROOT
    / "tools"
    / "broker_reports_financial_semantic_pack_tool.v1.py"
)
PACK_PATH = (
    SERVICE_ROOT
    / "semantic_packs"
    / "broker_reports_financial_semantic_pack.v1.json"
)
BUILD_SCRIPT = (
    SERVICE_ROOT / "scripts" / "build_openwebui_managed_financial_assets.py"
)
EXPECTED_PACK_INTEGRITY = (
    "ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8"
)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _git_index_blob(path: Path) -> bytes:
    relative = path.relative_to(REPO_ROOT).as_posix()
    completed = subprocess.run(
        ["git", "show", f":{relative}"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr.decode(
        "utf-8",
        errors="replace",
    )
    return completed.stdout


def _canonical_manifest_hash(manifest: dict[str, Any]) -> str:
    material = copy.deepcopy(manifest)
    material.pop("manifest_sha256")
    canonical = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return _sha256(canonical)


def _load_tool_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "broker_reports_financial_semantic_pack_tool_v1",
        TOOL_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_schema_and_integrity_are_strict() -> None:
    schema = _read_json(MANIFEST_SCHEMA_PATH)
    manifest = _read_json(MANIFEST_PATH)

    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(manifest)
    assert manifest["manifest_sha256"] == _canonical_manifest_hash(manifest)
    assert manifest["schema_version"] == (
        "broker_reports_financial_domain_managed_asset_manifest_v1"
    )
    assert manifest["family_id"] == (
        "broker_reports_gate2_financial_domain_assets"
    )
    assert manifest["semantic_version"] == "1.0.0"
    assert manifest["authority_status"] == "target_normative_not_live"
    assert manifest["runtime_activation"] is False
    assert manifest["hash_boundary"] == "git_blob_bytes"


def test_manifest_pins_exact_git_blob_assets_and_dependencies() -> None:
    manifest = _read_json(MANIFEST_PATH)
    assets = {item["asset_id"]: item for item in manifest["assets"]}
    dependencies = {
        item["dependency_id"]: item for item in manifest["dependencies"]
    }

    assert list(assets) == [
        "broker_reports_financial_domain_skill",
        "broker_reports_gate2_financial_matching_prompt",
        "broker_reports_financial_semantic_pack_tool",
    ]
    assert [item["kind"] for item in manifest["assets"]] == [
        "openwebui_skill",
        "openwebui_prompt",
        "openwebui_workspace_tool",
    ]
    assert set(dependencies) == {
        "broker_reports_financial_semantic_pack",
        "broker_reports_financial_semantic_pack_schema",
        "broker_reports_managed_financial_domain_schema",
        "broker_reports_financial_decision_contract",
    }

    for item in [*manifest["assets"], *manifest["dependencies"]]:
        path = REPO_ROOT / item["repository_relative_path"]
        assert path.is_file()
        assert item["git_blob_sha256"] == _sha256(_git_index_blob(path))

    pack = dependencies["broker_reports_financial_semantic_pack"]
    assert pack["semantic_version"] == "1.0.0"
    assert pack["semantic_integrity_sha256"] == EXPECTED_PACK_INTEGRITY
    assert pack["canonical_semantic_bytes"] == 9404


def test_openwebui_v096_api_identities_and_composition_are_pinned() -> None:
    manifest = _read_json(MANIFEST_PATH)
    openwebui = manifest["openwebui"]
    composition = manifest["composition"]

    assert openwebui == {
        "distribution": "open-webui",
        "target_version": "0.9.6",
        "upstream_tag": "v0.9.6",
        "skill_api": "/api/v1/skills",
        "prompt_api": "/api/v1/prompts",
        "tool_api": "/api/v1/tools",
    }
    assert composition == {
        "method_asset_id": "broker_reports_financial_domain_skill",
        "operation_asset_id": (
            "broker_reports_gate2_financial_matching_prompt"
        ),
        "pack_loader_asset_id": (
            "broker_reports_financial_semantic_pack_tool"
        ),
        "pack_loader_method": "load_financial_semantic_pack",
        "semantic_pack_dependency_id": (
            "broker_reports_financial_semantic_pack"
        ),
        "strict_output_contract": (
            "broker_reports_gate2_financial_evidence_decision_v1"
        ),
        "bounded_input_placeholder": (
            "{{financial_semantic_matching_input_json}}"
        ),
    }
    prompt = next(
        item for item in manifest["assets"] if item["kind"] == "openwebui_prompt"
    )
    assert prompt["api_identity"]["command"] == (
        "broker_gate2_financial_match_v1"
    )
    assert prompt["api_identity"]["version_id"] == "1.0.0"
    tool = next(
        item
        for item in manifest["assets"]
        if item["kind"] == "openwebui_workspace_tool"
    )
    assert tool["api_identity"]["id"].isidentifier()


def test_skill_and_prompt_enforce_pack_only_bounded_safe_method() -> None:
    pack = _read_json(PACK_PATH)
    skill = SKILL_PATH.read_text(encoding="utf-8")
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    combined = skill + "\n" + prompt

    assert "Version: `1.0.0`" in skill
    assert "entire supplied bounded source context" in skill
    assert "unclassified_financial_input" in skill
    assert "Do not invent" in skill
    assert "Do not calculate" in skill
    assert "only authority" in skill
    assert "one strict" in prompt.casefold()
    assert prompt.count("{{financial_semantic_matching_input_json}}") == 1
    assert "RAG" in combined
    assert "Knowledge" in combined
    assert EXPECTED_PACK_INTEGRITY in skill
    assert EXPECTED_PACK_INTEGRITY in prompt
    assert "broker_reports_gate2_financial_evidence_decision_v1" in combined

    for type_definition in pack["full_compact_snapshot"]:
        assert type_definition["input_type_id"] not in combined
        assert type_definition["definition"] not in combined


def test_workspace_tool_returns_exact_complete_pack_and_fails_closed() -> None:
    module = _load_tool_module()
    expected = _git_index_blob(PACK_PATH).decode("utf-8")
    tool = module.Tools()

    assert tool.load_financial_semantic_pack() == expected
    assert _sha256(expected.encode("utf-8")) == (
        module.PACK_GIT_BLOB_SHA256
    )
    assert module.PACK_INTEGRITY_SHA256 == EXPECTED_PACK_INTEGRITY
    assert module.PACK_CANONICAL_SEMANTIC_BYTES == 9404
    assert "Tools.load_financial_semantic_pack" in module.FACTORY_REQUIRED
    assert "must not" in module.FORBIDDEN

    original_payload = module._PACK_PAYLOAD_B85
    module._PACK_PAYLOAD_B85 = b"tampered"
    try:
        with pytest.raises(
            RuntimeError,
            match="financial_semantic_pack_payload_invalid",
        ):
            module.Tools()
    finally:
        module._PACK_PAYLOAD_B85 = original_payload


def test_workspace_tool_is_closed_world_single_file_python() -> None:
    source = TOOL_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots = set()
    tools_methods = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(
                alias.name.split(".", 1)[0] for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.ClassDef) and node.name == "Tools":
            tools_methods = [
                item.name
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not item.name.startswith("_")
            ]

    assert imported_roots == {
        "__future__",
        "base64",
        "hashlib",
        "json",
        "typing",
        "zlib",
    }
    assert tools_methods == ["load_financial_semantic_pack"]
    for forbidden in (
        "Path(",
        "open(",
        "os.environ",
        "process.cwd",
        "requests",
        "urllib",
        "socket",
        "from open_webui",
        "import open_webui",
    ):
        assert forbidden not in source


def test_rag_and_knowledge_cannot_be_semantic_authority() -> None:
    schema = _read_json(MANIFEST_SCHEMA_PATH)
    manifest = _read_json(MANIFEST_PATH)
    authority = manifest["authority"]

    assert authority == {
        "financial_semantic_authority_dependency_id": (
            "broker_reports_financial_semantic_pack"
        ),
        "full_pack_required": True,
        "rag_only_authority_allowed": False,
        "knowledge_authority_allowed": False,
        "python_type_meanings_allowed": False,
        "prompt_type_meanings_allowed": False,
    }
    assert manifest["supporting_knowledge"] == []

    invalid = copy.deepcopy(manifest)
    invalid["authority"]["rag_only_authority_allowed"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(invalid)

    invalid = copy.deepcopy(manifest)
    invalid["supporting_knowledge"] = [{"asset_id": "semantic-authority"}]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(invalid)


def test_generated_tool_and_manifest_are_deterministic() -> None:
    completed = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--check"],
        cwd=SERVICE_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == "passed"
    assert result["mode"] == "check"
    assert result["hash_boundary"] == "git_blob_bytes"
    assert result["tool_git_blob_sha256"] == _sha256(_git_index_blob(TOOL_PATH))
    assert result["manifest_git_blob_sha256"] == _sha256(
        _git_index_blob(MANIFEST_PATH)
    )
