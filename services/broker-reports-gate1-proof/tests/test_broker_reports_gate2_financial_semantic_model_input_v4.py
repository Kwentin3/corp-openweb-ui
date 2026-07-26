from __future__ import annotations

import ast
import asyncio
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_financial_evidence_successor import (  # noqa: E402
    SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V4,
    SUCCESSOR_PROMPT_CONTRACT_ID_V4,
    SUCCESSOR_RESULT_SCHEMA_VERSION_V4,
    Gate2FinancialEvidenceSuccessorConfig,
    Gate2FinancialEvidenceSuccessorError,
    Gate2FinancialEvidenceSuccessorRunnerFactory,
    validate_financial_evidence_successor_model_input_v4,
)
from broker_reports_gate1.gate2_financial_semantic_model_assets import (  # noqa: E402,E501
    FACTORY_REQUIRED,
    FORBIDDEN,
    MANAGED_PROMPT_GIT_BLOB_SHA256,
    PACK_INTEGRITY_SHA256,
    load_gate2_financial_semantic_model_assets,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2ProviderExecutionMetadata,
    Gate2StructuredModelResult,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    FINANCIAL_EVIDENCE_SUCCESSOR_QUALIFICATION_REQUEST_PROFILE_V3,
    Gate2OpenWebUIRequestBuilder,
)
from test_broker_reports_gate2_financial_successor_projection_v3 import (  # noqa: E402,E501
    MODEL_ID,
    PROVIDER_PROFILE_ID,
    _scope_context,
)


PACK_PATH = (
    ROOT
    / "semantic_packs"
    / "broker_reports_financial_semantic_pack.v1.json"
)
MANIFEST_PATH = (
    ROOT
    / "managed_assets"
    / "broker_reports_financial_domain_assets.v1.manifest.json"
)
PROMPT_PATH = (
    ROOT
    / "managed_assets"
    / "prompts"
    / "broker_reports_gate2_financial_matching_prompt.v1.md"
)
RUNTIME_PATH = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_semantic_model_assets.py"
)
BUILD_SCRIPT = (
    ROOT / "scripts" / "build_gate2_financial_semantic_model_assets.py"
)


class _TerminalDecisionClient:
    def __init__(self) -> None:
        self.calls = []

    async def extract(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        bindings = [
            {
                "role_id": item["allowed_roles"][0],
                "source_value_ref": item["source_value_ref"],
            }
            for item in kwargs["package"]["structural_scope"][
                "allowed_role_ref_combinations"
            ]
        ]
        return Gate2StructuredModelResult(
            content={
                "decision": {
                    "disposition": "unclassified_financial_input",
                    "value_bindings": bindings,
                    "reason_code": "ambiguous_registry_type",
                }
            },
            execution_metadata=Gate2ProviderExecutionMetadata(
                provider_id="openai",
                provider_profile_id=PROVIDER_PROFILE_ID,
                provider_profile_revision="semantic-pack-v4-test",
                adapter_id="openai_response_format",
                adapter_version="semantic-pack-v4-test",
                requested_model_id=MODEL_ID,
                resolved_model_id=MODEL_ID,
                structured_output_mode=(
                    "openwebui_response_format_json_schema"
                ),
                response_format_type="json_schema",
                response_format_schema_mode="strict_json_schema",
            ),
        )


def _runner(registry, client=None):
    return Gate2FinancialEvidenceSuccessorRunnerFactory(
        registry=registry,
        model_client=client or _TerminalDecisionClient(),
        config=Gate2FinancialEvidenceSuccessorConfig(
            model_id=MODEL_ID,
            provider_profile_id=PROVIDER_PROFILE_ID,
            model_input_schema_version=(
                SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V4
            ),
            prompt_contract_id=SUCCESSOR_PROMPT_CONTRACT_ID_V4,
        ),
    ).create()


def test_generated_assets_are_exact_complete_and_path_free():
    assets = load_gate2_financial_semantic_model_assets()
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest_assets = {
        item["asset_id"]: item for item in manifest["assets"]
    }

    assert assets["semantic_pack"]["full_compact_snapshot"] == (
        pack["full_compact_snapshot"]
    )
    assert assets["semantic_pack"]["integrity_sha256"] == (
        PACK_INTEGRITY_SHA256
    )
    assert assets["prompt_content"] == PROMPT_PATH.read_text(
        encoding="utf-8"
    ).replace("\r\n", "\n")
    assert assets["prompt_git_blob_sha256"] == (
        MANAGED_PROMPT_GIT_BLOB_SHA256
    )
    assert assets["managed_assets"]["skill"]["git_blob_sha256"] == (
        manifest_assets["broker_reports_financial_domain_skill"][
            "git_blob_sha256"
        ]
    )
    assert assets["managed_assets"]["prompt"]["git_blob_sha256"] == (
        manifest_assets[
            "broker_reports_gate2_financial_matching_prompt"
        ]["git_blob_sha256"]
    )
    serialized = json.dumps(assets["managed_assets"], sort_keys=True)
    assert "repository_relative_path" not in serialized
    assert "managed_assets/" not in serialized


def test_runtime_projection_is_closed_world_and_deterministic():
    source = RUNTIME_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        str(node.module or "").split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )

    assert imported_roots == {
        "__future__",
        "base64",
        "copy",
        "hashlib",
        "json",
        "typing",
        "zlib",
    }
    assert "only closed-world" in FACTORY_REQUIRED
    assert "must not read runtime files" in FORBIDDEN
    for forbidden in ("Path(", "open(", "requests", "urllib", "socket"):
        assert forbidden not in source

    completed = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == "passed"
    assert result["mode"] == "check"
    assert result["runtime_projection_git_blob_sha256"] == hashlib.sha256(
        RUNTIME_PATH.read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()


def test_v4_model_input_has_one_complete_semantic_authority():
    scope, context, registry = _scope_context(
        "syn_successor_signed_literal"
    )
    model_input = _runner(registry).model_input(
        scope=scope,
        source_context=context,
    )
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))

    assert set(model_input) == {
        "managed_assets",
        "semantic_pack",
        "structural_scope",
        "source_groups",
    }
    assert model_input["semantic_pack"]["full_compact_snapshot"] == (
        pack["full_compact_snapshot"]
    )
    assert model_input["structural_scope"]["eligible_type_ids"] == [
        "cash_balance_snapshot_v1",
        "printed_financial_metric_v1",
    ]
    assert len(
        model_input["structural_scope"][
            "allowed_role_ref_combinations"
        ]
    ) == len(scope.decision_contract.package.candidates)
    assert all(
        "allowed_roles" not in value
        for group in model_input["source_groups"]
        for value in group["values"]
    )
    serialized = json.dumps(model_input, ensure_ascii=False, sort_keys=True)
    for forbidden in (
        '"eligible_types"',
        '"document_id"',
        '"document_ref"',
        '"path"',
        '"provenance_graph"',
        '"system_audit"',
        '"expected_answer"',
        '"gate3_methodology"',
    ):
        assert forbidden not in serialized


def test_v4_pack_identity_completeness_and_system_fields_fail_closed():
    scope, context, registry = _scope_context(
        "syn_successor_signed_literal"
    )
    model_input = _runner(registry).model_input(
        scope=scope,
        source_context=context,
    )

    incomplete = copy.deepcopy(model_input)
    incomplete["semantic_pack"]["full_compact_snapshot"].pop()
    with pytest.raises(
        Gate2FinancialEvidenceSuccessorError,
        match="financial_evidence_successor_semantic_pack_incomplete",
    ):
        validate_financial_evidence_successor_model_input_v4(
            model_input=incomplete,
            scope=scope,
            source_context=context,
        )

    wrong_identity = copy.deepcopy(model_input)
    wrong_identity["managed_assets"]["prompt"][
        "git_blob_sha256"
    ] = "0" * 64
    with pytest.raises(
        Gate2FinancialEvidenceSuccessorError,
        match="financial_evidence_successor_managed_asset_identity_invalid",
    ):
        validate_financial_evidence_successor_model_input_v4(
            model_input=wrong_identity,
            scope=scope,
            source_context=context,
        )

    leaked = copy.deepcopy(model_input)
    leaked["source_groups"][0]["document_id"] = "private"
    with pytest.raises(
        Gate2FinancialEvidenceSuccessorError,
        match="financial_evidence_successor_model_system_field_forbidden",
    ):
        validate_financial_evidence_successor_model_input_v4(
            model_input=leaked,
            scope=scope,
            source_context=context,
        )


def test_v4_runner_reaches_terminal_result_with_exact_managed_prompt():
    scope, context, registry = _scope_context(
        "syn_successor_signed_literal"
    )
    client = _TerminalDecisionClient()
    runner = _runner(registry, client)

    result = asyncio.run(
        runner.run(
            scope=scope,
            source_context=context,
            execution_ref="execution:semantic-pack-v4:test",
            decision_validation_ref="validation:semantic-pack-v4:test",
        )
    )

    assert len(client.calls) == 1
    assert client.calls[0]["prompt"].content == PROMPT_PATH.read_text(
        encoding="utf-8"
    ).replace("\r\n", "\n")
    assert client.calls[0]["prompt"].hash == (
        MANAGED_PROMPT_GIT_BLOB_SHA256
    )
    assert result.safe_summary["schema_version"] == (
        SUCCESSOR_RESULT_SCHEMA_VERSION_V4
    )
    assert result.safe_summary["semantic_pack_integrity_sha256"] == (
        PACK_INTEGRITY_SHA256
    )
    assert result.safe_summary["semantic_pack_types_total"] == 2
    assert result.safe_summary["semantic_selection_owner"] == "llm"
    assert result.safe_summary["duplicate_semantic_authorities_total"] == 0
    assert result.safe_summary["terminal_disposition"] == (
        "unclassified_financial_input"
    )


def test_v3_request_builder_embeds_exact_v4_package_without_tooling():
    scope, context, registry = _scope_context(
        "syn_successor_signed_literal"
    )
    runner = _runner(registry)
    package = runner.model_input(
        scope=scope,
        source_context=context,
    )
    response_format = scope.decision_contract.openai_response_format()
    request = Gate2OpenWebUIRequestBuilder(
        request_profile=(
            FINANCIAL_EVIDENCE_SUCCESSOR_QUALIFICATION_REQUEST_PROFILE_V3
        )
    ).build(
        prompt=runner.prompt,
        package=package,
        model_id=MODEL_ID,
        response_format=response_format,
    )

    system_content = request["messages"][0]["content"]
    assert "{{financial_semantic_matching_input_json}}" not in system_content
    assert json.dumps(
        package,
        ensure_ascii=False,
        sort_keys=True,
    ) in system_content
    metadata = request["metadata"]["broker_reports_gate2"]
    assert metadata["semantic_pack_complete"] is True
    assert metadata["semantic_selection_owner"] == "llm"
    assert metadata["knowledge_rag_used"] is False
    assert metadata["vectorization_performed"] is False
