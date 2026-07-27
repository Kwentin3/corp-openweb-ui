from __future__ import annotations

import ast
import asyncio
import copy
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import broker_reports_gate1.gate2_successor_compatibility as successor_compatibility_module  # noqa: E402,E501

from broker_reports_gate1.gate2_financial_context import (  # noqa: E402
    Gate2FinancialContextProjectionFactory,
)
from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (  # noqa: E402
    FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION,
    FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION_V1,
    sha256_json,
)
from broker_reports_gate1.gate2_fns_2ndfl_contracts import (  # noqa: E402
    TYPED_FACTS_SCHEMA_VERSION,
)
from broker_reports_gate1.gate2_source_fact_contracts import (  # noqa: E402
    SOURCE_FACTS_SCHEMA_VERSION,
)
from broker_reports_gate1.gate2_successor_artifacts import (  # noqa: E402
    FACTORY_REQUIRED,
    FORBIDDEN,
    SUCCESSOR_COMPATIBILITY_PROJECTION_SCHEMA_VERSION,
    SUCCESSOR_EXECUTION_RECEIPT_SCHEMA_VERSION,
    SUCCESSOR_PACKAGE_ARTIFACT_SCHEMA_VERSION,
    SUCCESSOR_RUN_ARTIFACT_SCHEMA_VERSION,
    Gate2SuccessorArtifactError,
    Gate2SuccessorArtifactFamilyFactory,
    Gate2SuccessorArtifactInput,
    validate_successor_compatibility_projection,
    validate_successor_package_artifact,
)
from broker_reports_gate1.gate2_successor_compatibility import (  # noqa: E402
    COMPATIBILITY_WRAPPER_DELEGATES_ONLY,
    SUCCESSOR_COMPATIBILITY_READ_RESULT_SCHEMA_VERSION,
    SUCCESSOR_COMPATIBILITY_READER_POLICY_VERSION,
    Gate2SuccessorCompatibilityError,
    Gate2SuccessorCompatibilityReaderFactory,
)
from test_broker_reports_gate2_financial_evidence_compatibility import (  # noqa: E402
    _fns_payload,
    _legacy_payload,
)
from test_broker_reports_gate2_financial_evidence_successor import (  # noqa: E402
    _DecisionClient,
    _runner,
    _scope_and_registry,
)


MODULE_PATHS = (
    ROOT / "broker_reports_gate1" / "gate2_successor_artifacts.py",
    ROOT
    / "broker_reports_gate1"
    / "gate2_successor_compatibility.py",
)


def _successor_family():
    scope, registry = _scope_and_registry()
    result = asyncio.run(
        _runner(registry, _DecisionClient()).run(
            scope=scope,
            execution_ref="execution:successor-artifact:test",
            decision_validation_ref=(
                "validation:successor-artifact:test"
            ),
        )
    )
    financial_context = Gate2FinancialContextProjectionFactory(
        registry=registry
    ).create(
        materialized_artifacts=(result.materialized_artifact,),
        source_packages=(scope.source_package,),
    )
    family = Gate2SuccessorArtifactFamilyFactory(
        registry=registry
    ).create(
        run_ref="run:successor-artifact:test",
        source_extraction_run_ref="run:source-extraction:test",
        inputs=(
            Gate2SuccessorArtifactInput(
                scope=scope,
                result=result,
            ),
        ),
        financial_context=financial_context,
    )
    return family, result, registry


def test_successor_artifact_family_is_explicit_and_deterministic():
    first, result, registry = _successor_family()
    scope, _ = _scope_and_registry()
    context = Gate2FinancialContextProjectionFactory(
        registry=registry
    ).create(
        materialized_artifacts=(result.materialized_artifact,),
        source_packages=(scope.source_package,),
    )
    second = Gate2SuccessorArtifactFamilyFactory(
        registry=registry
    ).create(
        run_ref="run:successor-artifact:test",
        source_extraction_run_ref="run:source-extraction:test",
        inputs=(
            Gate2SuccessorArtifactInput(
                scope=scope,
                result=result,
            ),
        ),
        financial_context=context,
    )

    assert first == second
    assert first.package_artifacts[0]["schema_version"] == (
        SUCCESSOR_PACKAGE_ARTIFACT_SCHEMA_VERSION
    )
    assert first.run_artifact["schema_version"] == (
        SUCCESSOR_RUN_ARTIFACT_SCHEMA_VERSION
    )
    assert first.execution_receipt["schema_version"] == (
        SUCCESSOR_EXECUTION_RECEIPT_SCHEMA_VERSION
    )
    assert first.compatibility_projections[0]["schema_version"] == (
        SUCCESSOR_COMPATIBILITY_PROJECTION_SCHEMA_VERSION
    )
    assert first.execution_receipt["status"] == "passed"


def test_migration_policy_blocks_writes_and_preserves_rollback_boundary():
    family, _, _ = _successor_family()
    policy = family.run_artifact["migration_policy"]

    assert policy == {
        "legacy_read": "preserved",
        "legacy_payloads_immutable": True,
        "legacy_rewrite_allowed": False,
        "silent_upcast_allowed": False,
        "successor_reader": "explicit_schema_dispatch",
        "successor_single_write": (
            "blocked_pending_production_admission"
        ),
        "production_write_admitted": False,
        "rollback_boundary": "future_routing_only",
        "fns_specialized_path": "separate_unchanged",
    }
    assert family.execution_receipt[
        "legacy_payloads_rewritten_total"
    ] == 0
    assert family.execution_receipt["silent_conversions_total"] == 0
    assert family.execution_receipt["production_write_admitted"] is False


def test_projection_has_own_identity_and_only_computable_fields():
    family, _, _ = _successor_family()
    projection = family.compatibility_projections[0]

    assert projection["projection_ref"].startswith(
        "successor-compatibility:"
    )
    assert projection["legacy_schema_version"] is None
    assert projection["legacy_emulation"] is False
    assert projection["subtype_created"] is False
    assert projection["model_confidence_created"] is False
    assert projection["model_output_emulated"] is False
    assert not {"subtype", "confidence", "model_output"} & set(
        projection
    )

    tampered = copy.deepcopy(projection)
    tampered["subtype"] = "invented"
    tampered["integrity_hash"] = sha256_json(
        {
            key: value
            for key, value in tampered.items()
            if key != "integrity_hash"
        }
    )
    with pytest.raises(
        Gate2SuccessorArtifactError,
        match="successor_compatibility_projection_field_forbidden",
    ):
        validate_successor_compatibility_projection(tampered)


def test_artifact_validator_fails_closed_on_tampering():
    family, _, _ = _successor_family()
    tampered = copy.deepcopy(family.package_artifacts[0])
    tampered["migration_policy"]["silent_upcast_allowed"] = True

    with pytest.raises(
        Gate2SuccessorArtifactError,
        match="successor_package_artifact_integrity_invalid",
    ):
        validate_successor_package_artifact(tampered)


@pytest.mark.parametrize(
    ("payload_factory", "schema_version", "read_kind"),
    (
        (
            _legacy_payload,
            SOURCE_FACTS_SCHEMA_VERSION,
            "legacy_source_facts",
        ),
        (
            _fns_payload,
            TYPED_FACTS_SCHEMA_VERSION,
            "fns_specialized",
        ),
    ),
)
def test_explicit_reader_retains_legacy_and_fns_without_rewrite(
    payload_factory,
    schema_version,
    read_kind,
):
    _, _, registry = _successor_family()
    reader = Gate2SuccessorCompatibilityReaderFactory(
        registry=registry
    ).create()
    payload = payload_factory()
    before = copy.deepcopy(payload)
    before_hash = sha256_json(payload)

    result = reader.read(
        artifact_ref=f"artifact:{read_kind}:test",
        payload=payload,
    )

    assert payload == before
    assert sha256_json(payload) == before_hash
    assert result.schema_version == (
        SUCCESSOR_COMPATIBILITY_READ_RESULT_SCHEMA_VERSION
    )
    assert result.reader_policy_version == (
        SUCCESSOR_COMPATIBILITY_READER_POLICY_VERSION
    )
    assert result.artifact_schema_version == schema_version
    assert result.artifact_sha256 == before_hash
    assert result.read_kind == read_kind
    assert result.legacy_reader_retained is True
    assert result.legacy_payload_rewritten is False
    assert result.silent_conversion_used is False
    assert result.fns_specialized_separate is (
        read_kind == "fns_specialized"
    )


def test_successor_reader_delegates_legacy_and_registered_validation(
    monkeypatch,
) -> None:
    family, _, registry = _successor_family()
    legacy_payload = _legacy_payload()
    legacy_ref = "artifact:legacy:delegation"
    delegated = (
        successor_compatibility_module.Gate2FinancialEvidenceCompatibilityFactory(
            registry=registry
        )
        .create()
        .read(artifact_ref=legacy_ref, payload=legacy_payload)
    )
    calls = []

    class SpyLegacyReader:
        def read(self, *, artifact_ref, payload):
            calls.append(("legacy_read", artifact_ref, payload))
            return delegated

    class SpyLegacyReaderFactory:
        def __init__(self, *, registry):
            calls.append(("legacy_factory", registry))

        def create(self):
            return SpyLegacyReader()

    monkeypatch.setattr(
        successor_compatibility_module,
        "Gate2FinancialEvidenceCompatibilityFactory",
        SpyLegacyReaderFactory,
    )
    reader = Gate2SuccessorCompatibilityReaderFactory(
        registry=registry
    ).create()
    legacy_result = reader.read(
        artifact_ref=legacy_ref,
        payload=legacy_payload,
    )

    successor_payload = family.package_artifacts[0]
    schema_version = successor_payload["schema_version"]
    read_kind, validator = (
        successor_compatibility_module._SUCCESSOR_VALIDATORS[
            schema_version
        ]
    )

    def spy_successor_validator(payload):
        calls.append(("successor_validator", payload))
        validator(payload)

    monkeypatch.setitem(
        successor_compatibility_module._SUCCESSOR_VALIDATORS,
        schema_version,
        (read_kind, spy_successor_validator),
    )
    successor_result = reader.read(
        artifact_ref="artifact:successor:delegation",
        payload=successor_payload,
    )

    assert COMPATIBILITY_WRAPPER_DELEGATES_ONLY is True
    assert calls[0] == ("legacy_factory", registry)
    assert calls[1] == ("legacy_read", legacy_ref, legacy_payload)
    assert calls[2] == ("successor_validator", successor_payload)
    assert legacy_result.read_kind == delegated.read_kind
    assert successor_result.read_kind == read_kind


def test_reader_explicitly_dispatches_financial_input_and_successor_family():
    family, result, registry = _successor_family()
    reader = Gate2SuccessorCompatibilityReaderFactory(
        registry=registry
    ).create()
    cases = (
        (
            result.materialized_artifact,
            FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION,
            "successor_financial_evidence",
        ),
        (
            family.package_artifacts[0],
            SUCCESSOR_PACKAGE_ARTIFACT_SCHEMA_VERSION,
            "successor_package_artifact",
        ),
        (
            family.run_artifact,
            SUCCESSOR_RUN_ARTIFACT_SCHEMA_VERSION,
            "successor_run_artifact",
        ),
        (
            family.execution_receipt,
            SUCCESSOR_EXECUTION_RECEIPT_SCHEMA_VERSION,
            "successor_execution_receipt",
        ),
        (
            family.compatibility_projections[0],
            SUCCESSOR_COMPATIBILITY_PROJECTION_SCHEMA_VERSION,
            "successor_compatibility_projection",
        ),
    )

    for index, (payload, schema_version, read_kind) in enumerate(cases):
        read = reader.read(
            artifact_ref=f"artifact:explicit:{index}",
            payload=payload,
        )
        assert read.artifact_schema_version == schema_version
        assert read.read_kind == read_kind
        assert read.silent_conversion_used is False

    projection_read = reader.read(
        artifact_ref="artifact:projection:test",
        payload=family.compatibility_projections[0],
    )
    assert projection_read.compatibility_projection_ref == (
        family.compatibility_projections[0]["projection_ref"]
    )


def test_reader_rejects_unknown_schema_and_all_writes_before_admission():
    family, _, registry = _successor_family()
    reader = Gate2SuccessorCompatibilityReaderFactory(
        registry=registry
    ).create()

    with pytest.raises(
        Gate2SuccessorCompatibilityError,
        match="successor_compatibility_schema_unsupported",
    ):
        reader.read(
            artifact_ref="artifact:unknown:test",
            payload={"schema_version": "unknown_schema_v1"},
        )
    with pytest.raises(
        Gate2SuccessorCompatibilityError,
        match="successor_single_write_not_admitted",
    ):
        reader.validate_successor_single_write(
            family.package_artifacts[0]
        )


def test_contract_boundaries_are_explicit_and_legacy_versions_are_unchanged():
    assert "Factory" in FACTORY_REQUIRED
    assert "rewrite legacy" in FORBIDDEN
    assert SOURCE_FACTS_SCHEMA_VERSION == "broker_reports_source_facts_v0"
    assert FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION == (
        "broker_reports_financial_evidence_inputs_v2"
    )
    assert FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION_V1 == (
        "broker_reports_financial_evidence_inputs_v1"
    )
    assert TYPED_FACTS_SCHEMA_VERSION == (
        "broker_reports_fns_2ndfl_source_facts_v1"
    )
    for module_path in MODULE_PATHS:
        assert module_path.exists()
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        modules = {
            str(node.module or "")
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        assert not {
            module
            for module in modules
            if module.endswith("artifact_store")
            or module.endswith("gate2_domain_runtime")
            or module.endswith("gate2_source_fact_runtime")
            or module.endswith(
                "gate2_financial_evidence_production_runtime"
            )
        }
