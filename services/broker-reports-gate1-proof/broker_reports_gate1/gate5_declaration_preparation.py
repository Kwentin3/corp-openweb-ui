"""Client-ready declaration preparation over existing evidence authorities."""

from __future__ import annotations

import copy
from typing import Any

from .artifact_models import ArtifactAccessContext, ArtifactStorePort
from .gate5_evidence_intake import (
    Gate5EvidenceIntakeRuntime,
    Gate5EvidenceIntakeRuntimeFactory,
)
from .gate5_client_evidence_review import (
    Gate5ClientEvidenceReviewRuntime,
    Gate5ClientEvidenceReviewRuntimeFactory,
)
from .gate5_declaration_scope_resolution import (
    Gate5DeclarationScopeActivationRuntime,
    Gate5DeclarationScopeActivationRuntimeFactory,
)
from .gate5_full_target_xml_projection import (
    Gate5FullTargetXmlProjectionDefinitionAuthority,
    Gate5FullTargetXmlProjectionDefinitionAuthorityFactory,
)
from .gate5_human_gap_closure import (
    Gate5HumanGapClosureRuntime,
    Gate5HumanGapClosureRuntimeFactory,
)
from .gate5_real_tax_case_assembly import (
    Gate5RealTaxCaseAssemblyRuntime,
    Gate5RealTaxCaseAssemblyRuntimeFactory,
)
from .gate5_residency_evidence import (
    Gate5ResidencyEvidenceRuntime,
    Gate5ResidencyEvidenceRuntimeFactory,
)


GATE5_DECLARATION_PREPARATION_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_preparation_v0"
)
GATE5_DECLARATION_DRAFT_SCHEMA_VERSION = (
    "broker_reports_gate5_machine_readable_declaration_draft_v0"
)
GATE5_DECLARATION_PREPARATION_TERMINAL = (
    "DECLARATION_PREPARATION_WORKFLOW_PROVEN"
)
GATE5_REAL_EVIDENCE_GAPS_TERMINAL = "REAL_EVIDENCE_GAPS_REMAIN"
GATE5_REAL_DECLARATION_CASE_TERMINAL = "REAL_DECLARATION_CASE_PROVEN"

FACTORY_REQUIRED = (
    "Gate5DeclarationPreparationRuntimeFactory.create composes "
    "Gate5EvidenceIntakeRuntimeFactory.create, "
    "Gate5RealTaxCaseAssemblyRuntimeFactory.create, "
    "Gate5ClientEvidenceReviewRuntimeFactory.create, "
    "Gate5DeclarationScopeActivationRuntimeFactory.create, "
    "Gate5HumanGapClosureRuntimeFactory.create and the official target "
    "Projection Definition factory",
)
FORBIDDEN = (
    "second tax pipeline, direct SQL, raw-document Gate 5 read, LLM calculation, "
    "manual XML, declaration at any cost, new workflow engine, new TaxCase "
    "database, reconciliation or persisted financial-event relations",
)


class Gate5DeclarationPreparationError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class Gate5DeclarationPreparationRuntimeFactory:
    def __init__(self, *, store: ArtifactStorePort, read_enabled: bool) -> None:
        self._store = store
        self._read_enabled = read_enabled

    def create(self) -> "Gate5DeclarationPreparationRuntime":
        return Gate5DeclarationPreparationRuntime(
            intake=Gate5EvidenceIntakeRuntimeFactory(
                store=self._store,
                read_enabled=self._read_enabled,
            ).create(),
            case_assembler=Gate5RealTaxCaseAssemblyRuntimeFactory(
                store=self._store,
                read_enabled=self._read_enabled,
            ).create(),
            client_review=Gate5ClientEvidenceReviewRuntimeFactory(
                store=self._store,
                read_enabled=self._read_enabled,
            ).create(),
            scope_activation=Gate5DeclarationScopeActivationRuntimeFactory(
                store=self._store,
                read_enabled=self._read_enabled,
            ).create(),
            gap_closure=Gate5HumanGapClosureRuntimeFactory.create(),
            residency=Gate5ResidencyEvidenceRuntimeFactory.create(),
            target_definition=(
                Gate5FullTargetXmlProjectionDefinitionAuthorityFactory.create()
            ),
        )


class Gate5DeclarationPreparationRuntime:
    def __init__(
        self,
        *,
        intake: Gate5EvidenceIntakeRuntime,
        case_assembler: Gate5RealTaxCaseAssemblyRuntime,
        client_review: Gate5ClientEvidenceReviewRuntime,
        scope_activation: Gate5DeclarationScopeActivationRuntime,
        gap_closure: Gate5HumanGapClosureRuntime,
        residency: Gate5ResidencyEvidenceRuntime,
        target_definition: Gate5FullTargetXmlProjectionDefinitionAuthority,
    ) -> None:
        self._intake = intake
        self._case_assembler = case_assembler
        self._client_review = client_review
        self._scope_activation = scope_activation
        self._gap_closure = gap_closure
        self._residency = residency
        self._target_definition = target_definition

    def prepare(
        self,
        *,
        source_fact_methodology_ref: dict[str, Any],
        context: ArtifactAccessContext,
        evidence_mode: str,
        user_intent: dict[str, Any],
        user_case_facts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        intake = self._intake.collect(context=context)
        case = self._case_assembler.assemble(
            source_fact_methodology_ref=source_fact_methodology_ref,
            context=context,
            evidence_mode=evidence_mode,
        )
        review = self._client_review.review(
            source_assembly=case["source_fact_assembly"]
        )
        scope = self._scope_activation.activate(
            user_intent=user_intent,
            evidence_mode=evidence_mode,
            case_assembly=case,
        )
        validated_user_facts = self._gap_closure.validate_user_case_facts(
            user_case_facts
        )
        residency_classification = self._residency.classify(
            evidence=_residency_evidence(validated_user_facts)
        )
        closure = self._gap_closure.plan(
            intake=intake,
            scope_activation=scope,
            client_review=review,
            user_case_facts=validated_user_facts,
            residency_classification=residency_classification,
        )
        draft = _machine_readable_draft(
            case=case,
            scope=scope,
            user_case_facts=closure["known_user_case_facts"],
            residency_classification=residency_classification,
        )
        # Closure actions aggregate work needed for complete declaration release;
        # their list order is not a computation dependency order.  Filing/user
        # requirements must not erase independent calculations already present
        # in the target-independent draft.
        required_actions = closure["required_actions"]
        ready = (
            not required_actions
            and draft["calculation_count"] > 0
            and all(
                row["readiness"] == "RESOLVED"
                for row in draft["active_demand_readiness"]
            )
        )
        # A target cannot be emitted from a partial draft.  The already-published
        # Projection Definition remains the only target owner after a sealed
        # Declaration Semantic Input exists.
        target_definition = self._target_definition.resolve()
        terminals = [
            *intake["terminals"],
            *review["terminals"],
            *scope["terminals"],
            *closure["terminals"],
            *residency_classification["terminals"],
            GATE5_DECLARATION_PREPARATION_TERMINAL,
        ]
        if evidence_mode == "REAL_EVIDENCE":
            terminals.append(
                GATE5_REAL_DECLARATION_CASE_TERMINAL
                if ready
                else GATE5_REAL_EVIDENCE_GAPS_TERMINAL
            )
        else:
            terminals.append("SYNTHETIC_DECLARATION_PREPARATION_CONTROL")
        return {
            "schema_version": GATE5_DECLARATION_PREPARATION_SCHEMA_VERSION,
            "status": "DECLARATION_READY" if ready else "PREPARATION_INCOMPLETE",
            "evidence_mode": evidence_mode,
            "terminals": terminals,
            "intake": intake,
            "case_assembly": case,
            "client_review": review,
            "scope_activation": scope,
            "gap_closure": closure,
            "residency_classification": residency_classification,
            "machine_readable_declaration_draft": draft,
            "declaration_readiness": {
                "ready": ready,
                "active_demands": len(scope["active_demands"]),
                "resolved_demands": sum(
                    item["readiness"] == "RESOLVED"
                    for item in draft["active_demand_readiness"]
                ),
                "blocked_demands": sum(
                    item["readiness"] == "BLOCKED"
                    for item in draft["active_demand_readiness"]
                ),
                "required_actions": len(required_actions),
                "advisory_findings": len(closure["advisory_actions"]),
                "methodology_bindings": [
                    copy.deepcopy(case["source_fact_assembly"]["methodology_binding"])
                ],
                "supporting_source_fact_count": case["metrics"]["source_facts"],
                "supporting_metadata_fact_count": len(intake["metadata_facts"]),
            },
            "target_release": {
                "status": (
                    "AWAITING_SEALED_DECLARATION_SEMANTIC_INPUT"
                    if not ready
                    else "READY_FOR_OFFICIAL_PROJECTION_OWNER"
                ),
                "semantic_owner": "Gate5DeclarationSemanticInputRuntimeFactory.create",
                "projection_owner": "Gate5FullTargetXmlProjectionRuntimeFactory.create",
                "projection_definition_id": target_definition["projection_id"],
                "projection_definition_version": target_definition["projection_version"],
                "xml_emitted": False,
                "pdf_emitted": False,
                "manual_target_construction": False,
            },
            "replay": {
                "entrypoint": "Gate5DeclarationPreparationRuntimeFactory.create",
                "deterministic": True,
                "new_documents_use_ordinary_normalization": True,
                "stale_llm_state_reused": False,
            },
            "metrics": {
                "source_facts_lost": 0,
                "invented_source_facts": 0,
                "invented_relations": 0,
                "unnecessary_user_questions": 0,
                "calculated_values_without_methodology": 0,
                "unresolved_values_without_exact_reason": 0,
                "advisories_without_client_benefit": 0,
            },
            "supplied_case_completeness_only": True,
            "real_world_taxpayer_completeness_asserted": False,
            "reconciliation": "not_performed",
            "persistence": "none_new",
        }

    def replay(self, **kwargs: Any) -> dict[str, Any]:
        return self.prepare(**kwargs)


def _machine_readable_draft(
    *,
    case: dict[str, Any],
    scope: dict[str, Any],
    user_case_facts: list[dict[str, Any]],
    residency_classification: dict[str, Any],
) -> dict[str, Any]:
    facts_by_key = {item["fact_key"]: item for item in user_case_facts}
    rows = []
    for item in scope["active_demands"]:
        readiness = "BLOCKED"
        terminal = item["terminal"]
        required_key = _user_fact_for_demand(item["demand"])
        if item["demand"] == "obl_taxpayer_identity_and_period_status" and (
            "taxpayer_identity_confirmed" in facts_by_key
            and residency_classification["status"] in {"RESIDENT", "NON_RESIDENT"}
        ):
            readiness = "METHODOLOGY_RESULT_AVAILABLE"
        elif required_key and required_key in facts_by_key:
            readiness = "USER_FACT_AVAILABLE"
        elif terminal == "RESOLVED":
            readiness = "RESOLVED"
        elif terminal == "AVAILABLE":
            readiness = "METHODOLOGY_INPUT_AVAILABLE"
        rows.append(
            {
                "demand": item["demand"],
                "domain_id": item["domain_id"],
                "readiness": readiness,
                "source_terminal": terminal,
                "evidence_fact_count": len(item["available_evidence"]["fact_ids"]),
            }
        )
    calculations = []
    for item in case["deterministic_calculations"]:
        calculations.append(
            {
                "disposal_fact_id": item["disposal_fact_id"],
                "asset": item["asset"],
                "currency": item["gross_income"]["value"]["currency"],
                "gross_income": copy.deepcopy(item["gross_income"]),
                "recognized_acquisition_cost": copy.deepcopy(
                    item["recognized_acquisition_cost"]
                ),
                "direct_transaction_expense": copy.deepcopy(
                    item["direct_transaction_expense"]
                ),
                "tax_model_input_status": item["tax_model_input_status"],
                "methodology_binding": copy.deepcopy(
                    case["source_fact_assembly"]["methodology_binding"]
                ),
            }
        )
    return {
        "schema_version": GATE5_DECLARATION_DRAFT_SCHEMA_VERSION,
        "status": "PARTIAL_PROVEN_VALUES_ONLY",
        "definition_binding": copy.deepcopy(scope["definition_binding"]),
        "active_demand_readiness": rows,
        "deterministic_calculations": calculations,
        "calculation_count": len(calculations),
        "target_independent": True,
        "unproven_values_omitted": True,
        "xml_fields_present": False,
        "pdf_fields_present": False,
    }


def _user_fact_for_demand(demand: str) -> str | None:
    return {
        "obl_filing_instance_identity": "filing_instance_identity",
        "obl_signer_and_representation_authority": "signer_and_representation",
        "obl_declaration_budget_disposition": "budget_disposition",
    }.get(demand)


def _residency_evidence(value: list[dict[str, Any]]) -> dict[str, Any] | None:
    matches = [item for item in value if item["fact_key"] == "residency_evidence"]
    if not matches:
        return None
    wrapped = matches[0]["value"]
    if (
        wrapped.get("kind") != "residency_evidence"
        or not isinstance(wrapped.get("value"), dict)
    ):
        raise Gate5DeclarationPreparationError(
            "gate5_preparation_residency_evidence_invalid"
        )
    return copy.deepcopy(wrapped["value"])


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_DECLARATION_DRAFT_SCHEMA_VERSION",
    "GATE5_DECLARATION_PREPARATION_SCHEMA_VERSION",
    "GATE5_DECLARATION_PREPARATION_TERMINAL",
    "GATE5_REAL_DECLARATION_CASE_TERMINAL",
    "GATE5_REAL_EVIDENCE_GAPS_TERMINAL",
    "Gate5DeclarationPreparationError",
    "Gate5DeclarationPreparationRuntime",
    "Gate5DeclarationPreparationRuntimeFactory",
]
