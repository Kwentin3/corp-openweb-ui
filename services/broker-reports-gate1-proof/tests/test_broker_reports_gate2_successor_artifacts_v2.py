from __future__ import annotations

import ast
import asyncio
import copy
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_deterministic_financial_scopes import (  # noqa: E402
    Gate2DeterministicFinancialScopeFromGate1V2Factory,
)
from broker_reports_gate1.gate2_financial_context import (  # noqa: E402
    Gate2FinancialContextProjectionFactory,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_evidence_source_context import (  # noqa: E402
    Gate2FinancialEvidenceSourceContextFactory,
)
from broker_reports_gate1.gate2_financial_evidence_successor import (  # noqa: E402
    SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V3,
    SUCCESSOR_PROMPT_CONTRACT_ID_V3,
    Gate2FinancialEvidenceSuccessorConfig,
    Gate2FinancialEvidenceSuccessorRunnerFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2ProviderExecutionMetadata,
    Gate2StructuredModelResult,
)
from broker_reports_gate1.gate2_successor_artifacts import (  # noqa: E402
    SUCCESSOR_COMPATIBILITY_PROJECTION_SCHEMA_VERSION,
)
from broker_reports_gate1.gate2_successor_artifacts_v2 import (  # noqa: E402
    FACTORY_REQUIRED,
    FORBIDDEN,
    SUCCESSOR_ARTIFACT_POLICY_VERSION_V2,
    SUCCESSOR_EXECUTION_RECEIPT_SCHEMA_VERSION_V2,
    SUCCESSOR_PACKAGE_ARTIFACT_SCHEMA_VERSION_V2,
    SUCCESSOR_RUN_ARTIFACT_SCHEMA_VERSION_V2,
    Gate2SuccessorArtifactFamilyV2Factory,
    Gate2SuccessorArtifactV2Error,
    Gate2SuccessorArtifactV2Input,
    validate_successor_artifact_family_v2,
    validate_successor_package_artifact_v2,
)
from broker_reports_gate1.gate2_successor_compatibility import (  # noqa: E402
    Gate2SuccessorCompatibilityReaderFactory,
)
from broker_reports_gate1.gate2_successor_local_proof import (  # noqa: E402
    _fixture_package,
)


MANIFEST_PATH = (
    ROOT
    / "benchmarks"
    / "gate2_financial_successor_v2"
    / "manifest.json"
)
MODULE_PATH = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_successor_artifacts_v2.py"
)
MODEL_ID = "gpt-5.4-nano-2026-03-17"
PROVIDER_PROFILE_ID = "openai_gpt"


class _DecisionClient:
    async def extract(self, **kwargs):
        bindings = [
            {
                "role_id": value["allowed_roles"][0],
                "source_value_ref": value["source_value_ref"],
            }
            for group in kwargs["package"]["source_groups"]
            for value in group["values"]
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
                provider_profile_revision="artifact-v2-test",
                adapter_id="openai_response_format",
                adapter_version="artifact-v2-test",
                requested_model_id=MODEL_ID,
                resolved_model_id=MODEL_ID,
                structured_output_mode=(
                    "openwebui_response_format_json_schema"
                ),
                response_format_type="json_schema",
                response_format_schema_mode="strict_json_schema",
            ),
        )


def _family():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    case = next(
        item
        for item in manifest["cases"]
        if item["case_id"] == "syn_successor_v2_unique_cash"
    )
    fixture = _fixture_package(case)
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    scope = Gate2DeterministicFinancialScopeFromGate1V2Factory(
        registry=registry
    ).create(gate1_packages=(fixture.payload,)).scopes[0]
    source_context = Gate2FinancialEvidenceSourceContextFactory().create(
        source_scope_ref=scope.source_package.source_scope_ref,
        source_values=scope.source_package.source_values,
        candidates=scope.decision_contract.package.candidates,
        gate1_packages=(fixture.payload,),
    )
    runner = Gate2FinancialEvidenceSuccessorRunnerFactory(
        registry=registry,
        model_client=_DecisionClient(),
        config=Gate2FinancialEvidenceSuccessorConfig(
            model_id=MODEL_ID,
            provider_profile_id=PROVIDER_PROFILE_ID,
            model_input_schema_version=(
                SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V3
            ),
            prompt_contract_id=SUCCESSOR_PROMPT_CONTRACT_ID_V3,
        ),
    ).create()
    result = asyncio.run(
        runner.run(
            scope=scope,
            source_context=source_context,
            execution_ref="execution:artifact-v2:test",
            decision_validation_ref="validation:artifact-v2:test",
        )
    )
    financial_context = Gate2FinancialContextProjectionFactory(
        registry=registry
    ).create(
        materialized_artifacts=(result.materialized_artifact,),
        source_packages=(scope.source_package,),
    )
    family = Gate2SuccessorArtifactFamilyV2Factory(
        registry=registry
    ).create(
        run_ref="run:successor-artifact-v2:test",
        source_extraction_run_ref="run:source-extraction-v2:test",
        inputs=(
            Gate2SuccessorArtifactV2Input(
                scope=scope,
                source_context=source_context,
                result=result,
            ),
        ),
        financial_context=financial_context,
    )
    return family, registry


def test_artifact_v2_family_pins_exact_successor_contracts():
    family, _ = _family()
    package = family.package_artifacts[0]

    assert package["schema_version"] == (
        SUCCESSOR_PACKAGE_ARTIFACT_SCHEMA_VERSION_V2
    )
    assert package["artifact_policy_version"] == (
        SUCCESSOR_ARTIFACT_POLICY_VERSION_V2
    )
    assert package["deterministic_scope"]["schema_version"].endswith(
        "_package_v2"
    )
    assert package["source_context"] == {
        "schema_version": (
            "broker_reports_gate2_financial_evidence_source_context_v2"
        ),
        "policy_version": (
            "gate2_financial_evidence_bounded_source_context_v2"
        ),
        "integrity_hash": package["source_context"]["integrity_hash"],
        "private_payload_stored": False,
    }
    assert package["model_input"]["schema_version"].endswith(
        "_model_input_v3"
    )
    assert package["model_input"]["prompt_contract_id"].endswith(
        "_prompt_v3"
    )
    assert package["provider_projection"]["schema_version"].endswith(
        "_projection_v3"
    )
    assert package["compatibility_projection"]["schema_version"] == (
        SUCCESSOR_COMPATIBILITY_PROJECTION_SCHEMA_VERSION
    )
    assert family.run_artifact["schema_version"] == (
        SUCCESSOR_RUN_ARTIFACT_SCHEMA_VERSION_V2
    )
    assert family.execution_receipt["schema_version"] == (
        SUCCESSOR_EXECUTION_RECEIPT_SCHEMA_VERSION_V2
    )
    assert family.execution_receipt["status"] == "passed"


def test_artifact_v2_is_deterministic_and_safe_summary_is_private_free():
    first, _ = _family()
    second, _ = _family()

    assert first == second
    validate_successor_artifact_family_v2(family=first)
    summary = first.safe_summary()
    assert summary["status"] == "passed"
    assert summary["private_source_context_stored"] is False
    assert summary["production_write_admitted"] is False
    assert summary["fallback_total"] == 0
    assert summary["repair_attempts_total"] == 0
    assert "Cash balance" not in json.dumps(summary)


def test_artifact_v2_reader_is_explicit_and_never_rewrites():
    family, registry = _family()
    reader = Gate2SuccessorCompatibilityReaderFactory(
        registry=registry
    ).create()
    cases = (
        (
            family.package_artifacts[0],
            SUCCESSOR_PACKAGE_ARTIFACT_SCHEMA_VERSION_V2,
            "successor_package_artifact_v2",
        ),
        (
            family.run_artifact,
            SUCCESSOR_RUN_ARTIFACT_SCHEMA_VERSION_V2,
            "successor_run_artifact_v2",
        ),
        (
            family.execution_receipt,
            SUCCESSOR_EXECUTION_RECEIPT_SCHEMA_VERSION_V2,
            "successor_execution_receipt_v2",
        ),
    )

    for index, (payload, schema_version, read_kind) in enumerate(cases):
        before = copy.deepcopy(payload)
        read = reader.read(
            artifact_ref=f"artifact:v2:{index}",
            payload=payload,
        )
        assert payload == before
        assert read.artifact_schema_version == schema_version
        assert read.read_kind == read_kind
        assert read.legacy_payload_rewritten is False
        assert read.silent_conversion_used is False


def test_artifact_v2_rejects_private_context_or_identity_tamper():
    family, _ = _family()
    tampered = copy.deepcopy(family.package_artifacts[0])
    tampered["source_context"]["private_payload_stored"] = True
    material = copy.deepcopy(tampered)
    material.pop("integrity_hash")
    from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (  # noqa: E501
        sha256_json,
    )

    tampered["integrity_hash"] = sha256_json(material)
    with pytest.raises(
        Gate2SuccessorArtifactV2Error,
        match="successor_package_artifact_v2_contract_invalid",
    ):
        validate_successor_package_artifact_v2(tampered)


def test_artifact_v2_preserves_migration_and_release_stop():
    family, _ = _family()
    policy = family.run_artifact["migration_policy"]

    assert policy["legacy_read"] == "preserved"
    assert policy["legacy_payloads_immutable"] is True
    assert policy["legacy_rewrite_allowed"] is False
    assert policy["silent_upcast_allowed"] is False
    assert policy["production_write_admitted"] is False
    assert policy["rollback_boundary"] == "future_routing_only"
    assert family.execution_receipt[
        "private_source_contexts_stored_total"
    ] == 0
    assert family.execution_receipt[
        "legacy_payloads_rewritten_total"
    ] == 0
    assert family.execution_receipt["silent_conversions_total"] == 0


def test_artifact_v2_factory_has_no_store_or_production_bypass():
    assert "only scope-v2" in FACTORY_REQUIRED
    assert "must not store private source context" in FORBIDDEN
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imported_modules = {
        str(node.module or "")
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not {
        module
        for module in imported_modules
        if "artifact_store" in module
        or "production_runtime" in module
        or "gate2_domain_runtime" in module
        or "gate2_source_fact_runtime" in module
    }
