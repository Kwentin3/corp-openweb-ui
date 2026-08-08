from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = SERVICE_ROOT / "scripts"
PACKAGE_ROOT = SERVICE_ROOT / "broker_reports_gate1"
ASSET_ROOT = SERVICE_ROOT / "managed_assets"
sys.path.insert(0, str(SCRIPT_ROOT))

import build_openwebui_managed_financial_assets as builder  # noqa: E402
import live_publish_gate3_financial_label_assets as publisher  # noqa: E402
from broker_reports_gate1.gate3_financial_label_dictionary import (  # noqa: E402
    GATE3_DICTIONARY_OPENWEBUI_SKILL_ID,
    GATE3_DICTIONARY_OPENWEBUI_TOOL_ID,
    GATE3_DICTIONARY_OPENWEBUI_TOOL_METHOD,
    GATE3_DICTIONARY_V1_FILE_SHA256,
    GATE3_DICTIONARY_V1_MODEL_VIEW_SHA256,
    Gate3FinancialLabelDictionaryFactory,
)


DICTIONARY_PATH = (
    PACKAGE_ROOT / "gate3_financial_label_dictionary.v1.json"
)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_tool():
    spec = importlib.util.spec_from_file_location(
        "gate3_financial_label_dictionary_tool_test",
        builder.GATE3_TOOL_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_managed_binding_has_stable_ids_and_exact_dictionary_hashes() -> None:
    owner = Gate3FinancialLabelDictionaryFactory.create()
    binding = owner.managed_binding()
    assert binding == {
        "schema_version": (
            "broker_reports_gate3_financial_label_managed_binding_v1"
        ),
        "dictionary_identity": {
            "dictionary_id": "broker-reports-financial-labels",
            "semantic_version": "1.0.0",
            "file_sha256": GATE3_DICTIONARY_V1_FILE_SHA256,
            "model_view_sha256": GATE3_DICTIONARY_V1_MODEL_VIEW_SHA256,
        },
        "operator_surface": {
            "kind": "openwebui_skill",
            "stable_id": GATE3_DICTIONARY_OPENWEBUI_SKILL_ID,
            "gui_path": "Workspace -> Skills -> Financial labels",
        },
        "exact_delivery": {
            "kind": "openwebui_workspace_tool",
            "stable_id": GATE3_DICTIONARY_OPENWEBUI_TOOL_ID,
            "method": GATE3_DICTIONARY_OPENWEBUI_TOOL_METHOD,
        },
        "runtime_loader": "Gate3FinancialLabelDictionaryFactory.create",
        "knowledge_rag_used": False,
    }


def test_generated_skill_tool_and_manifest_are_exact_projections() -> None:
    skill, tool, manifest_bytes, schema_bytes = (
        builder.build_gate3_financial_label_assets()
    )
    assert builder._portable_text_blob(builder.GATE3_SKILL_PATH) == skill
    assert builder._portable_text_blob(builder.GATE3_TOOL_PATH) == tool
    assert builder._portable_text_blob(builder.GATE3_MANIFEST_PATH) == (
        manifest_bytes
    )
    assert builder._portable_text_blob(
        builder.GATE3_MANIFEST_SCHEMA_PATH
    ) == schema_bytes

    manifest = json.loads(manifest_bytes)
    schema = json.loads(schema_bytes)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(manifest)
    supplied = manifest.pop("manifest_sha256")
    assert supplied == _sha256(builder._canonical_json(manifest))
    assert manifest["authority"] == {
        "financial_meaning_owner_count": 1,
        "skill_is_generated_projection": True,
        "tool_is_exact_generated_delivery": True,
        "prompt_definitions_allowed": False,
        "python_definitions_allowed": False,
        "knowledge_rag_allowed": False,
    }
    assert manifest["supporting_knowledge"] == []
    assert manifest["composition"]["prompt_asset_id"] is None

    model_view = (
        Gate3FinancialLabelDictionaryFactory.create().render_model_markdown()
    )
    skill_text = skill.decode("utf-8")
    assert skill_text.count(model_view) == 1
    assert _sha256(model_view.encode("utf-8")) == (
        GATE3_DICTIONARY_V1_MODEL_VIEW_SHA256
    )


def test_workspace_tool_returns_byte_exact_published_dictionary() -> None:
    module = _load_tool()
    expected = DICTIONARY_PATH.read_text(encoding="utf-8")
    assert module.Tools().load_financial_label_dictionary() == expected
    assert module.DICTIONARY_FILE_SHA256 == _sha256(
        DICTIONARY_PATH.read_bytes()
    )
    assert "Tools.load_financial_label_dictionary" in module.FACTORY_REQUIRED
    assert "filesystem path" in module.FORBIDDEN
    source = builder.GATE3_TOOL_PATH.read_text(encoding="utf-8")
    assert "requests" not in source
    assert "urllib" not in source
    assert "open(" not in source
    assert "Path(" not in source
    assert "knowledge" in module.FORBIDDEN.casefold()
    assert "rag" in module.FORBIDDEN.casefold()
    assert "knowledge_id" not in source
    assert "vector" not in source.casefold()


def test_live_readback_evaluator_requires_exact_stable_id_bytes_and_method() -> None:
    expected = publisher._expected_assets()
    skill_identity = expected["skills"]["asset"]["api_identity"]
    tool_identity = expected["tools"]["asset"]["api_identity"]
    skill_record = {
        **skill_identity,
        "content": expected["skills"]["content"],
    }
    tool_record = {
        "id": tool_identity["id"],
        "name": tool_identity["name"],
        "content": expected["tools"]["content"],
        "meta": {
            "description": tool_identity["description"],
            "manifest": {"title": "Broker Reports Financial Labels"},
        },
        "specs": [{"name": tool_identity["meta"]["tool_method"]}],
    }
    assert publisher.evaluate_record(
        kind="skills",
        expected=expected["skills"],
        record=skill_record,
    )["passed"] is True
    assert publisher.evaluate_record(
        kind="tools",
        expected=expected["tools"],
        record=tool_record,
    )["passed"] is True

    renamed = {**skill_record, "name": "Display name changed"}
    renamed_check = publisher.evaluate_record(
        kind="skills",
        expected=expected["skills"],
        record=renamed,
    )
    assert renamed_check["stable_id_match"] is True
    assert renamed_check["name_match"] is False
    assert renamed_check["passed"] is False


def test_publisher_uses_native_stable_id_routes_and_no_semantic_bypass() -> None:
    source = (
        SCRIPT_ROOT / "live_publish_gate3_financial_label_assets.py"
    ).read_text(encoding="utf-8")
    assert "/api/v1/{kind}/id/{stable_id}/delete" in source
    assert "/api/v1/{kind}/id/{identity['id']}/update" in source
    assert "build_gate3_financial_label_assets" in source
    assert "get_by_name" not in source
    assert "provider_calls\": 0" in source
    assert "FACTORY_REQUIRED" in source
    assert "FORBIDDEN" in source
