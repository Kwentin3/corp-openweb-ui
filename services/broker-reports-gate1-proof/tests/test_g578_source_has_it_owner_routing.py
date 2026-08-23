from __future__ import annotations

from pathlib import Path
from typing import Any

from broker_reports_gate1.artifact_models import ArtifactAccessContext
from broker_reports_gate1.gate5_client_evidence_review import (
    Gate5ClientEvidenceReviewRuntime,
)
from broker_reports_gate1.gate5_declaration_scope_resolution import (
    GATE5_DECLARATION_SCOPE_ACTIVATION_SCHEMA_VERSION,
)
from broker_reports_gate1.gate5_deterministic_source_fact_consumption import (
    GATE5_AVAILABLE_SOURCE_FACT_ASSEMBLY_SCHEMA_VERSION,
)
from broker_reports_gate1.gate5_evidence_intake import (
    GATE5_EVIDENCE_INTAKE_SCHEMA_VERSION,
)
from broker_reports_gate1.gate5_human_gap_closure import (
    Gate5HumanGapClosureRuntimeFactory,
    gate5_case_taxpayer_scope_ref,
)
from broker_reports_gate1.gate5_residency_evidence import (
    Gate5ResidencyEvidenceRuntimeFactory,
)


_REPO_ROOT = Path(__file__).resolve().parents[3]


def test_source_absent_acquisition_gap_remains_external_evidence_demand() -> None:
    finding, action, closure = _route(
        _blocker(
            "gate5_source_fact_acquisition_quantity_insufficient",
            terminal="MISSING_EVIDENCE",
            acquisition_gap=True,
        )
    )

    assert finding["routing"]["ownership_state"] == (
        "SOURCE_ABSENT_WITHIN_SUPPLIED_EVIDENCE_HORIZON"
    )
    assert action["closure_type"] == "ADDITIONAL_DOCUMENT"
    assert action["gap_owner_classification"] == "REAL_SOURCE_EVIDENCE_MISSING"
    assert action["answer_contract"] == {"kind": "document_submission"}
    assert action in closure["user_facing_required_actions"]
    assert action not in closure["internal_owner_required_actions"]


def test_source_has_literal_role_loss_routes_to_gate3_gate4_owner_only() -> None:
    finding, action, closure = _route(
        _blocker("gate5_source_fact_required_role_missing")
    )

    assert finding["routing"] == {
        "ownership_state": "SOURCE_HAS_IT_ROLE_BINDING_LOST",
        "route": "UPSTREAM_SOURCE_FACT_PRODUCTION_REVIEW",
        "owner": (
            "Gate3EvidenceDemandPortFactory.create -> "
            "Gate4FinancialCaseMaterializerFactory.create"
        ),
        "closure_type": "EXISTING_EVIDENCE",
        "gap_owner_classification": "INTERNAL_CONTRACT_OR_PIPELINE_DEFECT",
        "user_or_additional_document_allowed": False,
    }
    assert action["closure_type"] == "EXISTING_EVIDENCE"
    assert action["gap_owner_classification"] == (
        "INTERNAL_CONTRACT_OR_PIPELINE_DEFECT"
    )
    assert action["answer_contract"]["kind"] == "owner_replay"
    assert "do not ask the user" in action["question"]
    _assert_internal_only(action, closure)


def test_source_has_literal_decimal_failure_routes_to_normalization_owner_only() -> (
    None
):
    finding, action, closure = _route(_blocker("gate5_source_fact_decimal_invalid"))

    assert finding["routing"]["ownership_state"] == (
        "SOURCE_HAS_IT_NORMALIZATION_FAILED"
    )
    assert finding["routing"]["route"] == "NORMALIZATION_OWNER_REVIEW"
    assert finding["routing"]["owner"] == (
        "Gate4FinancialCaseMaterializerFactory.create"
    )
    assert action["closure_type"] == "EXISTING_EVIDENCE"
    assert action["gap_owner_classification"] == (
        "INTERNAL_CONTRACT_OR_PIPELINE_DEFECT"
    )
    assert action["answer_contract"]["kind"] == "owner_replay"
    _assert_internal_only(action, closure)


def test_unknown_source_blocker_fails_closed_without_defaulting_to_user() -> None:
    finding, action, closure = _route(_blocker("unclassified_source_failure"))

    assert finding["routing"]["ownership_state"] == "OWNER_UNRESOLVED"
    assert action["closure_type"] == "OWNER_UNRESOLVED"
    assert action["gap_owner_classification"] == (
        "INTERNAL_CONTRACT_OR_PIPELINE_DEFECT"
    )
    assert action["answer_contract"] == {"kind": "owner_resolution"}
    assert "do not ask the user" in action["question"]
    _assert_internal_only(action, closure)


def test_methodology_gap_keeps_existing_methodology_owner_route() -> None:
    finding, action, closure = _route(
        _blocker(
            "gate5_source_fact_fifo_rounding_methodology_unresolved",
            terminal="METHODOLOGY_UNRESOLVED",
        )
    )

    assert finding["closure_type"] == "METHODOLOGY_RESEARCH"
    assert finding["routing"]["owner"] == (
        "Gate5TrustedMethodologyAuthorityFactory.create"
    )
    assert action["closure_type"] == "METHODOLOGY_RESEARCH"
    assert action["gap_owner_classification"] == "METHODOLOGY_RULE_MISSING"
    assert action["answer_contract"]["kind"] == "methodology_review"
    _assert_internal_only(action, closure)


def test_normative_contract_exposes_owner_routes_without_new_router() -> None:
    pipeline = (
        _REPO_ROOT / "docs/stage2/contracts/BROKER_REPORTS_PIPELINE_GATES.v1.md"
    ).read_text(encoding="utf-8")
    preparation = (
        _REPO_ROOT
        / "docs/stage2/contracts/BROKER_REPORTS_GATE5_DECLARATION_PREPARATION.v0.md"
    ).read_text(encoding="utf-8")

    assert "UPSTREAM_SOURCE_FACT_PRODUCTION_REVIEW" in pipeline
    assert "NORMALIZATION_OWNER_REVIEW" in pipeline
    assert "Unknown ownership fails closed as" in pipeline
    assert "user_facing_required_actions" in preparation
    assert "internal_owner_required_actions" in preparation
    assert "OWNER_UNRESOLVED" in preparation


def _assert_internal_only(action: dict[str, Any], closure: dict[str, Any]) -> None:
    assert action in closure["internal_owner_required_actions"]
    assert action not in closure["user_facing_required_actions"]
    assert action not in closure["llm_adapter_input"]["required_actions"]
    assert action["closure_type"] not in {"USER_FACT", "ADDITIONAL_DOCUMENT"}


def _route(
    blocker: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    review = Gate5ClientEvidenceReviewRuntime(source_runtime=None).review(
        source_assembly=_source_assembly(blocker)
    )
    context = ArtifactAccessContext(
        user_id="synthetic-user",
        normalization_run_id="synthetic-run",
        case_id="synthetic-case",
        allow_private=True,
    )
    closure = Gate5HumanGapClosureRuntimeFactory.create().plan(
        intake={
            "schema_version": GATE5_EVIDENCE_INTAKE_SCHEMA_VERSION,
            "metadata_facts": [],
        },
        scope_activation={
            "schema_version": GATE5_DECLARATION_SCOPE_ACTIVATION_SCHEMA_VERSION,
            "active_demands": [],
        },
        client_review=review,
        user_case_facts=[],
        residency_classification=(
            Gate5ResidencyEvidenceRuntimeFactory.create().classify(evidence=None)
        ),
        context=context,
        taxpayer_scope_ref=gate5_case_taxpayer_scope_ref(context),
        tax_period="2025",
    )
    return review["required_blockers"][0], closure["required_actions"][0], closure


def _source_assembly(blocker: dict[str, Any]) -> dict[str, Any]:
    empty_assertions = {"mode": "absent", "detail": [], "aggregate": []}
    return {
        "schema_version": GATE5_AVAILABLE_SOURCE_FACT_ASSEMBLY_SCHEMA_VERSION,
        "security_groups": [],
        "blockers": [blocker],
        "assertions": {
            "commissions": empty_assertions,
            "withheld_tax": empty_assertions,
        },
        "financial_type_counts": {},
    }


def _blocker(
    reason_code: str,
    *,
    terminal: str = "SOURCE_EVIDENCE_INSUFFICIENT",
    acquisition_gap: bool = False,
) -> dict[str, Any]:
    blocker: dict[str, Any] = {
        "terminal": terminal,
        "reason_code": reason_code,
        "fact_id": "g4fact_control",
        "financial_type": "SECURITY_DISPOSAL",
        "evidence_searched": {
            "document_id": "document-control",
            "source_fact_id": "g4fact_control",
        },
        "why_insufficient": reason_code,
        "closing_evidence": "the exact evidence required by the named consumer",
    }
    if acquisition_gap:
        blocker.update(
            {
                "asset": "ACME",
                "currency": "RUB",
                "disposal_date": "2025-01-02",
                "required_quantity": "2",
                "available_prior_quantity": "1",
                "minimum_missing_quantity": "1",
                "acquisition_basis_coverage": {
                    "concept": "ACQUISITION_BASIS_COVERAGE_GAP",
                    "coverage_status": "GAP",
                },
                "current_methodology_blocking_decision": "BLOCKED",
                "current_methodology_blocking_authority": "methodology-control",
            }
        )
    return blocker
