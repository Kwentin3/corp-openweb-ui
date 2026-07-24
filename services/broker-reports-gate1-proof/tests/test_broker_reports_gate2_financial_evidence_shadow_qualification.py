from __future__ import annotations

import ast
import asyncio
import copy
from dataclasses import replace
from pathlib import Path

from broker_reports_gate1.gate2_financial_evidence_decision import (
    FinancialEvidenceDecisionPackage,
    FinancialEvidenceValueCandidate,
    Gate2FinancialEvidenceDecisionContractFactory,
)
from broker_reports_gate1.gate2_financial_evidence_materialization import (
    FinancialEvidenceAuthoritativeSourceValue,
    FinancialEvidenceExecutionMetadata,
    FinancialEvidenceSourceLineage,
    Gate2FinancialEvidenceMaterializerFactory,
    Gate2FinancialEvidenceSourcePackageFactory,
    Gate2FinancialEvidenceValidatedDecisionFactory,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_evidence_shadow_qualification import (
    SHADOW_QUALIFICATION_SCHEMA_VERSION,
    FinancialEvidenceShadowDecisionResult,
    FinancialEvidenceShadowQualificationInput,
    Gate2FinancialEvidenceShadowDecisionRunnerFactory,
    Gate2FinancialEvidenceShadowQualificationFactory,
    private_evidence_hash,
    shadow_scope_from_result,
)
from broker_reports_gate1.gate2_model_contracts import (
    Gate2StructuredModelResult,
)
from broker_reports_gate1.gate2_model_requests import (
    FINANCIAL_EVIDENCE_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_evidence_shadow_qualification.py"
)


class _FakeModelClient:
    def __init__(self, content):
        self.content = content
        self.calls = []

    async def extract(self, **kwargs):
        self.calls.append(kwargs)
        return Gate2StructuredModelResult(content=copy.deepcopy(self.content))


def _registry():
    return Gate2FinancialEvidenceRegistryFactory().create()


def _case(suffix: str, disposition: str = "unclassified"):
    registry = _registry()
    source_value = FinancialEvidenceAuthoritativeSourceValue(
        source_value_ref=f"value:text:{suffix}",
        source_ref=f"source:text:{suffix}",
        value_type="source_text",
        literal_value=f"Synthetic value {suffix}",
        source_evidence_refs=(f"evidence:text:{suffix}",),
        lineage=FinancialEvidenceSourceLineage(
            document_ref=f"document:synthetic:{suffix}",
            text_segment_ref=f"segment:synthetic:{suffix}",
        ),
    )
    source_package = Gate2FinancialEvidenceSourcePackageFactory(
        package_ref=f"package:synthetic:{suffix}",
        normalization_run_ref=f"normalization:synthetic:{suffix}",
        document_ref=f"document:synthetic:{suffix}",
        source_scope_ref=f"scope:synthetic:{suffix}",
        source_family_id="source_family:unclassified",
        source_values=(source_value,),
        source_evidence_refs=(f"evidence:document:{suffix}",),
        completeness="complete",
    ).create()
    candidate = FinancialEvidenceValueCandidate(
        source_value_ref=source_value.source_value_ref,
        source_ref=source_value.source_ref,
        value_type=source_value.value_type,
        allowed_roles=("source_label",),
    )
    contract = Gate2FinancialEvidenceDecisionContractFactory(
        registry=registry,
        package=FinancialEvidenceDecisionPackage(
            source_scope_ref=source_package.source_scope_ref,
            source_family_id=source_package.source_family_id,
            candidates=(candidate,),
        ),
    ).create()
    if disposition == "unclassified":
        output = {
            "decision": {
                "disposition": "unclassified_financial_input",
                "value_bindings": [
                    {
                        "role_id": "source_label",
                        "source_value_ref": source_value.source_value_ref,
                    }
                ],
                "reason_code": "no_registry_type",
            }
        }
    else:
        output = {
            "decision": {
                "disposition": disposition,
                "reason_code": (
                    "non_financial_content"
                    if disposition == "no_financial_input"
                    else "source_shape_unsupported"
                ),
            }
        }
    validated = Gate2FinancialEvidenceValidatedDecisionFactory(
        contract=contract
    ).create(output)
    artifact = Gate2FinancialEvidenceMaterializerFactory(
        registry=registry,
        source_package=source_package,
        execution_metadata=FinancialEvidenceExecutionMetadata(
            execution_ref=f"execution:synthetic:{suffix}",
            decision_validation_ref=f"validation:synthetic:{suffix}",
        ),
    ).create().materialize(validated_decision=validated)
    return (
        contract,
        source_package,
        FinancialEvidenceShadowDecisionResult(
            artifact=artifact,
            source_package=source_package,
            provider_execution={},
            fallback_used=False,
            repair_attempt_count=0,
        ),
        output,
    )


def _qualification_input(scopes):
    return FinancialEvidenceShadowQualificationInput(
        authorized_source_refs=(
            "source:selected:a",
            "source:selected:b",
            "source:selected:legacy",
        ),
        compatibility_no_financial_refs=(
            "source:selected:a",
            "source:selected:legacy",
        ),
        scopes=tuple(scopes),
        source_ready_documents_total=1,
        parent_units_total=2,
        derived_segments_total=3,
        domain_packages_total=2,
        canonical_decision_scopes_total=2,
        baseline_selected_refs_total=3,
        baseline_accounted_refs_total=2,
        baseline_uncovered_refs_total=1,
        baseline_rejected_packages_total=1,
        browser_limits_used=False,
        shadow_only=True,
        private_evidence_hash="a" * 64,
    )


def _passing_bundle():
    first = _case("a")
    second = _case("b", "no_financial_input")
    first_scope = shadow_scope_from_result(
        result=first[2],
        selected_source_refs=("source:selected:a",),
    )
    second_scope = shadow_scope_from_result(
        result=second[2],
        selected_source_refs=("source:selected:b",),
    )
    return (first, second), (first_scope, second_scope)


def test_full_scope_qualification_passes_with_explicit_legacy_supersession():
    results, scopes = _passing_bundle()

    receipt = Gate2FinancialEvidenceShadowQualificationFactory(
        registry=_registry()
    ).create(
        qualification_input=_qualification_input(scopes),
        decision_results=tuple(item[2] for item in results),
    )

    assert receipt["schema_version"] == SHADOW_QUALIFICATION_SCHEMA_VERSION
    assert receipt["status"] == "passed"
    assert receipt["terminal"]["accounted_source_refs_total"] == 3
    assert receipt["terminal"]["uncovered_source_refs_total"] == 0
    assert receipt["terminal"][
        "compatibility_refs_superseded_total"
    ] == 1
    assert receipt["quality"]["contradictory_decisions_total"] == 0
    assert receipt["quality"]["duplicate_interpretations_total"] == 0
    assert receipt["quality"][
        "unclassified_scopes_fully_retained_total"
    ] == 1
    assert receipt["customer_values_in_receipt"] is False
    assert all(receipt["checks"].values())


def test_duplicate_interpretation_owner_fails_closed():
    first = _case("a")
    second = _case("b")
    first_scope = shadow_scope_from_result(
        result=first[2],
        selected_source_refs=("source:selected:a",),
    )
    duplicate = replace(
        shadow_scope_from_result(
            result=second[2],
            selected_source_refs=("source:selected:b",),
        ),
        selected_source_refs=("source:selected:a",),
    )
    qualification = _qualification_input((first_scope, duplicate))

    receipt = Gate2FinancialEvidenceShadowQualificationFactory(
        registry=_registry()
    ).create(
        qualification_input=qualification,
        decision_results=(first[2], second[2]),
    )

    assert receipt["status"] == "failed"
    assert receipt["quality"]["duplicate_interpretations_total"] == 1
    assert receipt["checks"]["ownership_conflicts_zero"] is False


def test_unclassified_value_loss_and_provider_failure_are_visible():
    results, scopes = _passing_bundle()
    failed_scope = replace(
        scopes[0],
        provider_status="failed",
    )

    receipt = Gate2FinancialEvidenceShadowQualificationFactory(
        registry=_registry()
    ).create(
        qualification_input=_qualification_input(
            (failed_scope, scopes[1])
        ),
        decision_results=tuple(item[2] for item in results),
    )

    assert receipt["status"] == "failed"
    assert receipt["quality"]["provider_failures_total"] == 1
    assert receipt["checks"][
        "unclassified_value_retention_100_percent"
    ] is True
    assert receipt["checks"]["unexplained_rejected_scopes_zero"] is False


def test_shadow_runner_uses_canonical_contract_and_materializer():
    contract, source_package, _, output = _case("runner")
    model_client = _FakeModelClient(output)
    runner = Gate2FinancialEvidenceShadowDecisionRunnerFactory(
        registry=_registry(),
        model_client=model_client,
        model_id="gpt-5.6-sol",
        provider_profile_id="openai_gpt",
    ).create()

    result = asyncio.run(
        runner.run(
            contract=contract,
            source_package=source_package,
            execution_ref="execution:shadow:runner",
            decision_validation_ref="validation:shadow:runner",
        )
    )

    assert result.artifact["terminal_disposition"] == (
        "unclassified_financial_input"
    )
    assert result.artifact["coverage"]["scope_accounted"] is True
    assert len(model_client.calls) == 1
    call = model_client.calls[0]
    assert call["response_format"] == contract.openai_response_format()
    assert call["package"]["llm_context_package"]["source_values"][0][
        "literal_value"
    ] == "Synthetic value runner"


def test_financial_request_profile_has_isolated_task_and_no_fallback():
    contract, source_package, _, _ = _case("request")
    model_client = _FakeModelClient({})
    runner = Gate2FinancialEvidenceShadowDecisionRunnerFactory(
        registry=_registry(),
        model_client=model_client,
        model_id="gpt-5.6-sol",
        provider_profile_id="openai_gpt",
    ).create()
    package = runner._model_package(contract, source_package)

    form = Gate2OpenWebUIRequestBuilder(
        request_profile=FINANCIAL_EVIDENCE_REQUEST_PROFILE
    ).build(
        prompt=runner.prompt,
        package=package,
        model_id="gpt-5.6-sol",
        response_format=contract.openai_response_format(),
    )

    assert form["stream"] is False
    assert form["metadata"]["broker_reports_gate2"][
        "financial_evidence_shadow"
    ] is True
    assert "extract_broker_reports_source_facts_v0" not in str(form)
    assert "financial_evidence_package_json" not in str(form)


def test_private_evidence_hash_is_deterministic_without_projection():
    private = {"source": "synthetic-private", "value": "42"}

    first = private_evidence_hash(private)
    second = private_evidence_hash(dict(reversed(tuple(private.items()))))

    assert first == second
    assert len(first) == 64
    assert "synthetic-private" not in first


def test_shadow_qualification_boundary_is_factory_managed_and_closed_world():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert "Goal 7 decision and qualification entrypoints" in source
    assert "must not call providers directly" in source
    assert not any(
        name.startswith(("openai", "requests", "httpx"))
        for name in imported_modules
    )
    assert "ArtifactStore" not in source
