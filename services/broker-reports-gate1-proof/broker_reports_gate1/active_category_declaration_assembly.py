"""Inactive composition from the active ordinary Category Tax Model to XSD."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .artifact_models import ArtifactAccessContext, ArtifactStorePort, RetentionPolicy
from .gate5_declaration_budget_outcome import (
    GATE5_DECLARATION_BUDGET_DISPOSITION_COMPONENT_SCHEMA_VERSION,
    GATE5_DECLARATION_BUDGET_DISPOSITION_INPUT_SCHEMA_VERSION,
    Gate5DeclarationBudgetOutcomeRuntimeFactory,
)
from .gate5_declaration_filing_context import (
    GATE5_FILING_AND_PARTY_IDENTITY_COMPONENT_SCHEMA_VERSION,
    GATE5_FILING_AND_PARTY_IDENTITY_INPUT_SCHEMA_VERSION,
    Gate5FilingAndPartyIdentityRuntimeFactory,
)
from .gate5_declaration_financial_investment_results import (
    GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPLETENESS_SCHEMA_VERSION,
    GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_SCHEMA_VERSION,
    GATE5_FINANCIAL_INVESTMENT_RESULTS_INPUT_SCHEMA_VERSION,
    Gate5DeclarationFinancialInvestmentResultsRuntimeFactory,
)
from .gate5_declaration_income_sources import (
    GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_SCHEMA_VERSION,
    GATE5_TAXABLE_INCOME_SOURCE_INPUT_SCHEMA_VERSION,
    Gate5DeclarationIncomeSourcesRuntimeFactory,
)
from .gate5_declaration_scope_resolution import (
    GATE5_DECLARATION_SCOPE_COMPONENT_EVIDENCE_SCHEMA_VERSION,
    GATE5_DECLARATION_SCOPE_SCHEMA_VERSION,
    Gate5DeclarationScopeResolutionRuntimeFactory,
)
from .gate5_declaration_semantic_input import (
    Gate5DeclarationSemanticInputRuntimeFactory,
)
from .gate5_declaration_tax_settlement import (
    GATE5_INCOME_GROUP_TAX_RESULTS_COMPONENT_SCHEMA_VERSION,
    GATE5_INCOME_GROUP_TAX_RESULTS_INPUT_SCHEMA_VERSION,
    Gate5DeclarationTaxSettlementRuntimeFactory,
)
from .gate5_full_declaration_definition import (
    Gate5TrustedFullDeclarationDefinitionAuthorityFactory,
)
from .gate5_full_target_xml_projection import (
    GATE5_CONSUMER_FIRST_XML_STATUS,
    GATE5_TARGET_MECHANICS_SCHEMA_VERSION,
    GATE5_TARGET_MECHANICS_STATUS,
    Gate5FullTargetXmlProjectionRuntimeFactory,
)
from .gate5_income_group_tax_base import (
    GATE5_INCOME_GROUP_TAX_BASE_COMPLETENESS_SCHEMA_VERSION,
    GATE5_INCOME_GROUP_TAX_BASE_INPUT_SCHEMA_VERSION,
    Gate5IncomeGroupTaxBaseRuntimeFactory,
)
from .gate5_residency_evidence import (
    Gate5ResidencyEvidenceRuntimeFactory,
    gate5_residency_methodology_input,
)
from .gate5_resolved_declaration_package import (
    Gate5ResolvedDeclarationPackageRuntimeFactory,
)
from .gate5_securities_disposal_tax_model import (
    GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION,
)
from .gate5_trusted_methodology import (
    GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_ID,
    GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_VERSION,
    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
    GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
)
from .ordinary_trade_tax_model_bridge import (
    ACTIVE_FACT_V2_TO_CATEGORY_TAX_MODEL_PROVEN,
    OrdinaryTradeTaxModelBridgeRuntime,
    OrdinaryTradeTaxModelBridgeRuntimeFactory,
)


ACTIVE_CATEGORY_DECLARATION_ASSEMBLY_SCHEMA_VERSION = (
    "broker_reports_active_category_declaration_assembly_v0"
)
ACTIVE_CATEGORY_TO_DECLARATION_ASSEMBLY_PROVEN = (
    "ACTIVE_CATEGORY_TO_DECLARATION_ASSEMBLY_PROVEN"
)
BOUNDED_DECLARATION_ASSEMBLY_BLOCKERS_PROVEN = (
    "BOUNDED_DECLARATION_ASSEMBLY_BLOCKERS_PROVEN"
)

FACTORY_REQUIRED = (
    "ActiveCategoryDeclarationAssemblyRuntimeFactory.create composes existing owners",
    "OrdinaryTradeTaxModelBridgeRuntimeFactory.create owns Fact v2 to Category",
    "Gate5IncomeGroupTaxBaseRuntimeFactory.create owns income-group tax base",
    "Gate5DeclarationScopeResolutionRuntimeFactory.create_current_source_fact_scope owns scope",
    "Gate5ResolvedDeclarationPackageRuntimeFactory.create_current_source_fact_package owns package",
    "Gate5DeclarationSemanticInputRuntimeFactory.create owns release",
    "Gate5FullTargetXmlProjectionRuntimeFactory.create owns target and XSD",
)
FORBIDDEN = (
    "prebuilt operation/category model, package, semantic input or released values",
    "Gate 3, historical SQL Gate 4, Canonical or Source Observation downstream reads",
    "tax calculation, completeness policy, projector defaults, provider or LLM calls",
    "production activation, persistence or downloadable declaration",
)


class ActiveCategoryDeclarationAssemblyError(ValueError):
    def __init__(self, code: str, field: str = "") -> None:
        self.code = code
        self.field = field
        super().__init__(code if not field else f"{code}:{field}")


class ActiveCategoryDeclarationAssemblyRuntimeFactory:
    def __init__(
        self,
        *,
        store: ArtifactStorePort,
        read_enabled: bool,
        retention_policy: RetentionPolicy,
    ) -> None:
        self._store = store
        self._read_enabled = read_enabled
        self._retention_policy = retention_policy

    def create(self) -> "ActiveCategoryDeclarationAssemblyRuntime":
        if not isinstance(self._retention_policy, RetentionPolicy):
            _fail("gate5_active_assembly_retention_policy_required")
        return ActiveCategoryDeclarationAssemblyRuntime(
            bridge=OrdinaryTradeTaxModelBridgeRuntimeFactory(
                store=self._store,
                read_enabled=self._read_enabled,
                retention_policy=self._retention_policy,
            ).create(),
            scope=Gate5DeclarationScopeResolutionRuntimeFactory(
                store=self._store,
                read_enabled=self._read_enabled,
                retention_policy=self._retention_policy,
            ).create_current_source_fact_scope(),
            package=Gate5ResolvedDeclarationPackageRuntimeFactory(
                store=self._store,
                read_enabled=self._read_enabled,
                retention_policy=self._retention_policy,
            ).create_current_source_fact_package(),
        )


class ActiveCategoryDeclarationAssemblyRuntime:
    def __init__(
        self, *, bridge: OrdinaryTradeTaxModelBridgeRuntime, scope: Any, package: Any
    ) -> None:
        self._bridge = bridge
        self._scope = scope
        self._package = package

    def run(
        self,
        *,
        operation_methodology_ref: dict[str, Any],
        source_fact_methodology_ref: dict[str, Any],
        resolved_inputs: dict[str, Any],
        disposal_fact_id: str,
        operation_ref: str,
        source_scope_ref: str,
        category_scope: dict[str, Any],
        taxpayer_binding: dict[str, Any] | None,
        category_completeness_evidence: dict[str, Any] | None,
        right_side_inputs: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        try:
            residency = _residency(right_side_inputs)
        except Exception as exc:
            code = str(
                getattr(exc, "code", "gate5_active_assembly_residency_evidence_missing")
            )
            field = str(getattr(exc, "field", "") or "residency_evidence")
            return _blocked(
                bridge=_empty_bridge(),
                blocker={
                    "schema_version": "broker_reports_active_assembly_blocker_v0",
                    "reason_code": code,
                    "required_input": field,
                    "gap_owner_classification": "USER_CASE_FACT_MISSING",
                    "owner": "Gate5ResidencyEvidenceRuntime",
                    "blocking_scope": "residency_classification",
                },
                last_stage="current_fact_v2",
            )
        bound_resolved_inputs = copy.deepcopy(resolved_inputs)
        tax_context = bound_resolved_inputs.get("tax_context")
        if not isinstance(tax_context, dict):
            return _blocked(
                bridge=_empty_bridge(),
                blocker={
                    "schema_version": "broker_reports_active_assembly_blocker_v0",
                    "reason_code": "gate5_active_assembly_tax_context_missing",
                    "required_input": "resolved_inputs.tax_context",
                    "gap_owner_classification": "USER_CASE_FACT_MISSING",
                    "owner": "Gate5SecuritiesDisposalTaxModelRuntime",
                    "blocking_scope": "operation_tax_model",
                },
                last_stage="current_fact_v2",
            )
        tax_context["residency"] = gate5_residency_methodology_input(
            residency,
            input_channel="minimal_tax_context",
        )
        bridge = self._bridge.run(
            operation_methodology_ref=operation_methodology_ref,
            source_fact_methodology_ref=source_fact_methodology_ref,
            resolved_inputs=bound_resolved_inputs,
            disposal_fact_id=disposal_fact_id,
            operation_ref=operation_ref,
            source_scope_ref=source_scope_ref,
            category_scope=category_scope,
            taxpayer_binding=taxpayer_binding,
            completeness_evidence=category_completeness_evidence,
            context=context,
        )
        if (
            bridge["terminal"] != ACTIVE_FACT_V2_TO_CATEGORY_TAX_MODEL_PROVEN
            or bridge["blockers"]
            or bridge["demands"]
        ):
            return _blocked(
                bridge=bridge,
                blocker=(
                    bridge["blockers"][0]
                    if bridge["blockers"]
                    else {
                        "schema_version": "broker_reports_active_assembly_blocker_v0",
                        "reason_code": bridge["demands"][0]["required_input"],
                        "required_input": bridge["demands"][0]["required_input"],
                        "gap_owner_classification": bridge["demands"][0][
                            "gap_owner_classification"
                        ],
                        "owner": bridge["demands"][0]["owner"],
                        "blocking_scope": "declaration_release",
                    }
                ),
                last_stage="active_category_tax_model",
            )
        try:
            result = self._assemble(
                bridge=bridge,
                right_side_inputs=right_side_inputs,
                taxpayer_binding=taxpayer_binding,
                residency=residency,
                context=context,
            )
        except Exception as exc:
            code = str(getattr(exc, "code", "gate5_active_assembly_internal_failure"))
            field = str(getattr(exc, "field", "") or "")
            return _blocked(
                bridge=bridge,
                blocker={
                    "schema_version": "broker_reports_active_assembly_blocker_v0",
                    "reason_code": code,
                    "required_input": field or code,
                    "gap_owner_classification": _gap_class(code),
                    "owner": _owner(code),
                    "blocking_scope": _stage(code),
                },
                last_stage=_stage(code),
            )
        return result

    def validate_receipt(self, receipt: dict[str, Any]) -> dict[str, Any]:
        """Fail closed on any changed stage binding or receipt-chain row."""

        if (
            not isinstance(receipt, dict)
            or receipt.get("schema_version")
            != ACTIVE_CATEGORY_DECLARATION_ASSEMBLY_SCHEMA_VERSION
            or receipt.get("terminal") != ACTIVE_CATEGORY_TO_DECLARATION_ASSEMBLY_PROVEN
            or receipt.get("route") != _route()
            or receipt.get("execution_constraints") != _constraints()
            or not isinstance(receipt.get("stage_hashes"), dict)
            or receipt.get("hash_chain") != _hash_chain(receipt["stage_hashes"])
        ):
            _fail("gate5_active_assembly_receipt_chain_invalid")
        base = {
            key: copy.deepcopy(value)
            for key, value in receipt.items()
            if key != "receipt_sha256"
        }
        if receipt.get("receipt_sha256") != _sha(base):
            _fail("gate5_active_assembly_receipt_hash_mismatch")
        return copy.deepcopy(receipt)

    def _assemble(
        self,
        *,
        bridge: dict[str, Any],
        right_side_inputs: dict[str, Any],
        taxpayer_binding: dict[str, Any] | None,
        residency: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        operation = bridge["operation_result"]["tax_model"]
        category = bridge["category_result"]["category_tax_model"]
        tax_base = _tax_base(category, residency, right_side_inputs)
        definition = (
            Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create().publication()
        )
        scope_input = _scope_input(right_side_inputs)
        operation_evidence = _component_evidence(
            GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION,
            operation,
        )
        provisional_scope = self._scope.resolve(
            definition_ref=definition,
            scope=scope_input,
            typed_component_evidence=[operation_evidence],
            assertion_refs=[],
            taxpayer_binding=taxpayer_binding,
            context=context,
        )
        scope_binding = provisional_scope["scope_binding"]
        settlement = _settlement(right_side_inputs, scope_binding, tax_base)
        income_source = _income_source(right_side_inputs, scope_binding, settlement)
        scope_receipt = self._scope.resolve(
            definition_ref=definition,
            scope=scope_input,
            typed_component_evidence=[
                operation_evidence,
                _component_evidence(
                    GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_SCHEMA_VERSION,
                    income_source,
                ),
            ],
            assertion_refs=[],
            taxpayer_binding=taxpayer_binding,
            context=context,
        )
        scope_binding = scope_receipt["scope_binding"]
        filing = _filing(right_side_inputs, scope_binding, residency)
        budget = _budget(right_side_inputs, scope_binding, filing, settlement)
        financial = _financial(right_side_inputs, scope_binding, category)
        components = [
            operation_evidence,
            _component_evidence(
                GATE5_FILING_AND_PARTY_IDENTITY_COMPONENT_SCHEMA_VERSION, filing
            ),
            _component_evidence(
                GATE5_DECLARATION_BUDGET_DISPOSITION_COMPONENT_SCHEMA_VERSION, budget
            ),
            _component_evidence(
                GATE5_INCOME_GROUP_TAX_RESULTS_COMPONENT_SCHEMA_VERSION, settlement
            ),
            _component_evidence(
                GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_SCHEMA_VERSION, income_source
            ),
            _component_evidence(
                GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_SCHEMA_VERSION, financial
            ),
        ]
        package = self._package.assemble(
            definition_ref=definition,
            scope_receipt=scope_receipt,
            typed_component_snapshots=components,
            context=context,
        )
        semantic = Gate5DeclarationSemanticInputRuntimeFactory.create()
        candidate = semantic.compile_declaration_value_candidate(package=package)
        released = semantic.release_declaration_value_candidate(
            package=package,
            candidate=candidate,
        )
        projection_input = semantic.prepare_released_projection_input(
            package=package,
            released=released,
        )
        mechanics = _target_mechanics(filing)
        projection = Gate5FullTargetXmlProjectionRuntimeFactory.create()
        first = projection.project_released(
            released_values=projection_input,
            target_mechanics=mechanics,
        )
        second = projection.project_released(
            released_values=projection_input,
            target_mechanics=mechanics,
        )
        if first["receipt"]["status"] != GATE5_CONSUMER_FIRST_XML_STATUS:
            _fail("gate5_active_assembly_consumer_projection_invalid")
        if first["xml_bytes"] != second["xml_bytes"]:
            _fail("gate5_active_assembly_projection_nondeterministic")
        release_receipt = released["release_receipt"]
        mappings = first["receipt"]["semantic_mapping_proof"]["mappings"]
        stage_hashes = {
            "operation_tax_model_sha256": _sha(operation),
            "category_tax_model_sha256": _sha(category),
            "income_group_tax_base_sha256": _sha(tax_base),
            "scope_receipt_sha256": scope_receipt["receipt_sha256"],
            "component_set_sha256": package["completeness_receipt"][
                "component_set_sha256"
            ],
            "package_sha256": package["package_sha256"],
            "semantic_value_sha256": released["semantic_value_sha256"],
            "release_receipt_sha256": release_receipt["receipt_sha256"],
            "projection_receipt_sha256": first["receipt"]["receipt_sha256"],
            "xml_sha256": first["receipt"]["xml_binding"]["xml_sha256"],
        }
        receipt_base = {
            "schema_version": ACTIVE_CATEGORY_DECLARATION_ASSEMBLY_SCHEMA_VERSION,
            "status": "proven",
            "terminal": ACTIVE_CATEGORY_TO_DECLARATION_ASSEMBLY_PROVEN,
            "blockers": [],
            "demands": [],
            "route": _route(),
            "identity_binding": copy.deepcopy(taxpayer_binding),
            "fact_v2_binding": copy.deepcopy(scope_receipt["gate4_binding"]),
            "stage_hashes": stage_hashes,
            "category_to_income_group_binding": copy.deepcopy(
                tax_base["calculation_scope"]["input_binding"]
            ),
            "hash_chain": _hash_chain(stage_hashes),
            "release_accounting": copy.deepcopy(release_receipt["evidence_accounting"]),
            "target_accounting": _target_accounting(
                mappings=mappings,
                release_bindings=release_receipt["evidence_accounting"]["bindings"],
                xsd_conformance=first["receipt"]["conformance_proof"],
            ),
            "visual_accounting": _visual_accounting(
                bridge=bridge,
                tax_base=tax_base,
                package=package,
                released=released,
                projection=first,
                right_side_inputs=right_side_inputs,
            ),
            "execution_constraints": _constraints(),
        }
        receipt = {**receipt_base, "receipt_sha256": _sha(receipt_base)}
        return self.validate_receipt(receipt)


def _tax_base(
    category: dict[str, Any], residency: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    facts = _required(inputs, "income_group", "Gate5IncomeGroupTaxBaseRuntime")
    group_values = copy.deepcopy(
        _required(facts, "group_values", "Gate5IncomeGroupTaxBaseRuntime")
    )
    taxpayer_status = gate5_residency_methodology_input(
        residency, input_channel="taxpayer_status"
    )
    runtime = Gate5IncomeGroupTaxBaseRuntimeFactory.create()
    binding = runtime.describe_input(
        category_tax_model=category,
        taxpayer_status=taxpayer_status,
        group_values=group_values,
    )
    provenance = _required(
        facts, "completeness_provenance", "Gate5IncomeGroupTaxBaseRuntime"
    )
    evidence = {
        "schema_version": GATE5_INCOME_GROUP_TAX_BASE_COMPLETENESS_SCHEMA_VERSION,
        "status": "asserted_complete",
        "coverage_kind": "all_income_and_reductions_in_stable_income_group",
        "input_binding_sha256": binding["input_binding_sha256"],
        "provenance": copy.deepcopy(provenance),
    }
    supplied_hash = facts.get("completeness_input_binding_sha256")
    if supplied_hash is not None:
        evidence["input_binding_sha256"] = supplied_hash
    return runtime.run(
        methodology_ref={
            "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
            "methodology_id": GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
            "methodology_version": GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_VERSION,
        },
        behavior_input={
            "schema_version": GATE5_INCOME_GROUP_TAX_BASE_INPUT_SCHEMA_VERSION,
            "category_tax_model": copy.deepcopy(category),
            "taxpayer_status": taxpayer_status,
            "group_values": group_values,
            "completeness_evidence": evidence,
        },
    )


def _residency(inputs: dict[str, Any]) -> dict[str, Any]:
    facts = _required(inputs, "residency_evidence", "Gate5ResidencyEvidenceRuntime")
    runtime = Gate5ResidencyEvidenceRuntimeFactory.create()
    evidence = runtime.normalize_human_answer(
        human_answer=_required(facts, "human_answer", "Gate5ResidencyEvidenceRuntime"),
        proposal=copy.deepcopy(
            _required(facts, "proposal", "Gate5ResidencyEvidenceRuntime")
        ),
        source_ref=_required(facts, "source_ref", "Gate5ResidencyEvidenceRuntime"),
    )
    classification = runtime.classify(evidence=evidence)
    if classification["status"] not in {"RESIDENT", "NON_RESIDENT"}:
        _fail("gate5_active_assembly_residency_evidence_missing", "residency_evidence")
    return classification


def _settlement(
    inputs: dict[str, Any], scope: dict[str, Any], tax_base: dict[str, Any]
) -> dict[str, Any]:
    facts = _required(inputs, "settlement", "Gate5DeclarationTaxSettlementRuntime")
    credits = _required(facts, "credits", "Gate5DeclarationTaxSettlementRuntime")
    model_hash = _sha(tax_base)
    values = {"income_group_model_sha256": model_hash}
    for name in (
        "withheld_at_source",
        "material_benefit_withheld",
        "trade_fee_credit",
        "fixed_advance_credit",
        "foreign_tax_credit",
        "patent_credit",
    ):
        values[name] = {
            "value": _money(
                _required(credits, name, "Gate5DeclarationTaxSettlementRuntime")
            ),
            "provenance": _synthetic(
                f"{facts['evidence_ref_prefix']}-{name}", "income_group_tax_settlement"
            ),
        }
    return Gate5DeclarationTaxSettlementRuntimeFactory.create().create_component(
        component_input={
            "schema_version": GATE5_INCOME_GROUP_TAX_RESULTS_INPUT_SCHEMA_VERSION,
            "methodology_ref": {
                "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
                "methodology_id": GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_ID,
                "methodology_version": GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_VERSION,
            },
            "scope_binding": copy.deepcopy(scope),
            "income_group_tax_base_models": [copy.deepcopy(tax_base)],
            "settlement_facts": [values],
            "completeness_evidence": {
                "schema_version": "broker_reports_gate5_income_group_results_completeness_v0",
                "status": "asserted_complete",
                "coverage_kind": "all_applicable_income_groups_for_declaration_scope",
                "scope_binding_sha256": scope["scope_binding_sha256"],
                "income_group_model_sha256s": [model_hash],
                "provenance": _synthetic(
                    facts["completeness_source_ref"],
                    "income_group_results_completeness",
                ),
            },
        }
    )


def _income_source(
    inputs: dict[str, Any], scope: dict[str, Any], settlement: dict[str, Any]
) -> dict[str, Any]:
    facts = _required(
        inputs, "taxable_income_source", "Gate5DeclarationIncomeSourcesRuntime"
    )
    result = settlement["group_results"][0]
    model = result["tax_base_model"]
    source_ref = _required(facts, "source_ref", "Gate5DeclarationIncomeSourcesRuntime")
    return Gate5DeclarationIncomeSourcesRuntimeFactory.create().create_component(
        component_input={
            "schema_version": GATE5_TAXABLE_INCOME_SOURCE_INPUT_SCHEMA_VERSION,
            "scope_binding": copy.deepcopy(scope),
            "income_group_results_component": copy.deepcopy(settlement),
            "source_entries": [
                {
                    "source_ref": source_ref,
                    "income_group_semantic": result["income_group_semantic"],
                    "jurisdiction_kind": _required(
                        facts,
                        "jurisdiction_kind",
                        "Gate5DeclarationIncomeSourcesRuntime",
                    ),
                    "jurisdiction_code": _required(
                        facts,
                        "jurisdiction_code",
                        "Gate5DeclarationIncomeSourcesRuntime",
                    ),
                    "income_kind": _required(
                        facts, "income_kind", "Gate5DeclarationIncomeSourcesRuntime"
                    ),
                    "source_party": copy.deepcopy(
                        _required(
                            facts,
                            "source_party",
                            "Gate5DeclarationIncomeSourcesRuntime",
                        )
                    ),
                    "gross_income": copy.deepcopy(model["total_income"]["value"]),
                    "taxable_income": copy.deepcopy(model["taxable_income"]["value"]),
                    "tax_agent": {
                        "status": "absent",
                        "withheld_tax": copy.deepcopy(
                            result["settlement_facts"]["withheld_at_source"]["value"]
                        ),
                    },
                    "foreign_tax": None,
                    "provenance": _synthetic(source_ref, "taxable_income_source"),
                }
            ],
            "completeness_evidence": {
                "schema_version": "broker_reports_gate5_taxable_income_source_completeness_v0",
                "status": "asserted_complete",
                "coverage_kind": "all_taxable_income_sources_for_declaration_scope",
                "scope_binding_sha256": scope["scope_binding_sha256"],
                "income_group_results_component_id": settlement["component_id"],
                "source_refs": [source_ref],
                "provenance": _synthetic(
                    facts["completeness_source_ref"],
                    "taxable_income_source_completeness",
                ),
            },
        }
    )


def _filing(
    inputs: dict[str, Any], scope: dict[str, Any], residency: dict[str, Any]
) -> dict[str, Any]:
    facts = _required(
        inputs, "filing_and_party_identity", "Gate5FilingAndPartyIdentityRuntime"
    )
    filing = copy.deepcopy(
        _required(facts, "filing_instance", "Gate5FilingAndPartyIdentityRuntime")
    )
    taxpayer = copy.deepcopy(
        _required(facts, "taxpayer", "Gate5FilingAndPartyIdentityRuntime")
    )
    signer = copy.deepcopy(
        _required(facts, "signer", "Gate5FilingAndPartyIdentityRuntime")
    )
    taxpayer["period_status"] = gate5_residency_methodology_input(
        residency, input_channel="taxpayer_status"
    )["value"]
    return Gate5FilingAndPartyIdentityRuntimeFactory.create().create_component(
        component_input={
            "schema_version": GATE5_FILING_AND_PARTY_IDENTITY_INPUT_SCHEMA_VERSION,
            "scope_binding": copy.deepcopy(scope),
            "filing_instance": filing,
            "taxpayer": taxpayer,
            "signer": signer,
            "evidence": {
                "schema_version": "broker_reports_gate5_synthetic_case_evidence_v0",
                "status": "synthetic_proof_evidence",
                "source_ref": facts["evidence_source_ref"],
                "case_id": scope["case_id"],
                "tax_period": scope["tax_period"],
                "input_channel": "filing_and_party_identity",
                "real_user_fact": False,
            },
        }
    )


def _budget(
    inputs: dict[str, Any],
    scope: dict[str, Any],
    filing: dict[str, Any],
    settlement: dict[str, Any],
) -> dict[str, Any]:
    facts = _required(
        inputs, "budget_disposition", "Gate5DeclarationBudgetOutcomeRuntime"
    )
    allocation = {
        key: _required(facts, key, "Gate5DeclarationBudgetOutcomeRuntime")
        for key in (
            "source_ref",
            "budget_allocation_ref",
            "kbk",
            "oktmo",
            "simplified_procedure_returned_or_credited_amount",
        )
    }
    return Gate5DeclarationBudgetOutcomeRuntimeFactory.create().create_component(
        component_input={
            "schema_version": GATE5_DECLARATION_BUDGET_DISPOSITION_INPUT_SCHEMA_VERSION,
            "scope_binding": copy.deepcopy(scope),
            "filing_component": copy.deepcopy(filing),
            "income_group_results_component": copy.deepcopy(settlement),
            "allocation_evidence": {
                "schema_version": "broker_reports_gate5_synthetic_case_evidence_v0",
                "status": "synthetic_proof_evidence",
                **copy.deepcopy(allocation),
                "case_id": scope["case_id"],
                "tax_period": scope["tax_period"],
                "input_channel": "declaration_budget_disposition",
                "real_user_fact": False,
            },
        }
    )


def _financial(
    inputs: dict[str, Any], scope: dict[str, Any], category: dict[str, Any]
) -> dict[str, Any]:
    facts = _required(
        inputs,
        "financial_investment",
        "Gate5DeclarationFinancialInvestmentResultsRuntime",
    )
    return Gate5DeclarationFinancialInvestmentResultsRuntimeFactory.create().create_component(
        component_input={
            "schema_version": GATE5_FINANCIAL_INVESTMENT_RESULTS_INPUT_SCHEMA_VERSION,
            "scope_binding": copy.deepcopy(scope),
            "category_tax_models": [copy.deepcopy(category)],
            "completeness_evidence": {
                "schema_version": GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPLETENESS_SCHEMA_VERSION,
                "status": "asserted_complete_for_supplied_case",
                "coverage_kind": "all_financial_investment_evidence_supplied_to_case",
                "scope_binding_sha256": scope["scope_binding_sha256"],
                "category_model_sha256s": [_sha(category)],
                "activated_obligation_refs": copy.deepcopy(
                    facts["activated_obligation_refs"]
                ),
                "not_activated_obligation_refs": copy.deepcopy(
                    facts["not_activated_obligation_refs"]
                ),
                "real_world_taxpayer_absence_asserted": False,
                "provenance": _synthetic(
                    facts["completeness_source_ref"],
                    "financial_investment_supplied_case_completeness",
                ),
            },
        }
    )


def _scope_input(inputs: dict[str, Any]) -> dict[str, Any]:
    scope = _required(inputs, "scope", "Gate5DeclarationScopeResolutionRuntime")
    return {
        "schema_version": GATE5_DECLARATION_SCOPE_SCHEMA_VERSION,
        "scope_ref": _required(
            scope, "scope_ref", "Gate5DeclarationScopeResolutionRuntime"
        ),
        "taxpayer_scope_ref": _required(
            scope, "taxpayer_scope_ref", "Gate5DeclarationScopeResolutionRuntime"
        ),
        "tax_period": _required(
            scope, "tax_period", "Gate5DeclarationScopeResolutionRuntime"
        ),
    }


def _target_mechanics(filing_component: dict[str, Any]) -> dict[str, Any]:
    electronic_file_id = filing_component["input_snapshot"]["filing_instance"][
        "declaration_instance_ref"
    ]
    base = {
        "schema_version": GATE5_TARGET_MECHANICS_SCHEMA_VERSION,
        "status": GATE5_TARGET_MECHANICS_STATUS,
        "electronic_file_id": electronic_file_id,
    }
    return {**base, "target_mechanics_sha256": _sha(base)}


def _component_evidence(contract_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": GATE5_DECLARATION_SCOPE_COMPONENT_EVIDENCE_SCHEMA_VERSION,
        "component_contract_id": contract_id,
        "component_sha256": _sha(payload),
        "payload": copy.deepcopy(payload),
    }


def _visual_accounting(
    *,
    bridge: dict[str, Any],
    tax_base: dict[str, Any],
    package: dict[str, Any],
    released: dict[str, Any],
    projection: dict[str, Any],
    right_side_inputs: dict[str, Any],
) -> dict[str, Any]:
    consumption = bridge["operation_result"]["source_fact_consumption"]
    security = consumption["securities"][0]
    operation = bridge["operation_result"]["tax_model"]
    category = bridge["category_result"]["category_tax_model"]
    return {
        "raw_control": copy.deepcopy(right_side_inputs.get("raw_ordinary_trade_table")),
        "fact_v2_ids": sorted(_fact_ids(operation)),
        "fifo": copy.deepcopy(security["recognized_acquisition_cost"]),
        "operation_values": {
            "gross_income": copy.deepcopy(operation["gross_income"]),
            "related_expenses": copy.deepcopy(operation["related_expenses"]),
            "allowable_expenses": copy.deepcopy(operation["allowable_expenses"]),
        },
        "category_values": {
            key: copy.deepcopy(category[key])
            for key in (
                "category_gross_income",
                "related_expenses",
                "allowable_expenses",
                "loss_treatment",
            )
        },
        "income_group_values": copy.deepcopy(tax_base),
        "component_states": [
            {"domain_id": item["domain_id"], "content_sha256": item["content_sha256"]}
            for item in package["component_snapshots"]
        ],
        "package_status": package["status"],
        "released_value_count": released["release_receipt"]["evidence_accounting"][
            "declared_value_count"
        ],
        "target_mapping_count": projection["receipt"]["semantic_mapping_proof"][
            "mapping_occurrences_total"
        ],
        "xsd_valid": projection["receipt"]["conformance_proof"]["xsd_valid"],
    }


def _target_accounting(
    *,
    mappings: list[dict[str, Any]],
    release_bindings: list[dict[str, Any]],
    xsd_conformance: dict[str, Any],
) -> dict[str, Any]:
    released_by_source = {
        "$root.declaration_values" + item["declared_value_path"][1:]: item
        for item in release_bindings
    }
    origin_rows = []
    for mapping in mappings:
        source = mapping["resolved_source"]
        if source in released_by_source:
            binding = released_by_source[source]
            owner = binding["owner_factory"]
            origin_kind = "RELEASED_SEMANTIC_VALUE"
            known_binding = bool(
                binding.get("direct_evidence_sha256")
                or (
                    binding.get("calculation_authority_sha256")
                    and binding.get("replayable_input_snapshot_sha256")
                )
            )
        elif source is None:
            owner = "Gate5ConsumerFirstXmlProjectionDefinitionAuthorityFactory.create"
            origin_kind = "OFFICIAL_TARGET_CONSTANT"
            known_binding = bool(mapping["evidence_refs"])
        elif source == "$root.target_mechanics.electronic_file_id":
            owner = "Gate5FilingAndPartyIdentityRuntimeFactory.create"
            origin_kind = "FILING_TARGET_MECHANICS"
            known_binding = bool(mapping["evidence_refs"])
        else:
            _fail("gate5_active_assembly_target_origin_unknown", str(source))
        if not owner or not known_binding:
            _fail(
                "gate5_active_assembly_target_owner_binding_missing",
                mapping["mapping_id"],
            )
        origin_rows.append(
            {
                "mapping_id": mapping["mapping_id"],
                "resolved_source": source,
                "target": mapping["target"],
                "target_value_sha256": mapping["target_value_sha256"],
                "origin_kind": origin_kind,
                "owner_factory": owner,
                "methodology_or_direct_binding_known": True,
            }
        )
    return {
        "mapping_occurrences_total": len(mappings),
        "known_owner_occurrences": len(origin_rows),
        "released_semantic_occurrences": sum(
            item["origin_kind"] == "RELEASED_SEMANTIC_VALUE" for item in origin_rows
        ),
        "official_constant_occurrences": sum(
            item["origin_kind"] == "OFFICIAL_TARGET_CONSTANT" for item in origin_rows
        ),
        "target_mechanics_occurrences": sum(
            item["origin_kind"] == "FILING_TARGET_MECHANICS" for item in origin_rows
        ),
        "mapping_projection": origin_rows,
        "xsd_conformance": copy.deepcopy(xsd_conformance),
        "deterministic_identical_xml_bytes": True,
    }


def _blocked(
    *, bridge: dict[str, Any], blocker: dict[str, Any], last_stage: str
) -> dict[str, Any]:
    base = {
        "schema_version": ACTIVE_CATEGORY_DECLARATION_ASSEMBLY_SCHEMA_VERSION,
        "status": "blocked",
        "terminal": BOUNDED_DECLARATION_ASSEMBLY_BLOCKERS_PROVEN,
        "blockers": [copy.deepcopy(blocker)],
        "demands": copy.deepcopy(bridge["demands"]),
        "upstream_bridge": copy.deepcopy(bridge),
        "last_completed_stage": last_stage,
        "released_values": None,
        "target_receipt": None,
        "route": _route(),
        "execution_constraints": _constraints(),
    }
    return {**base, "receipt_sha256": _sha(base)}


def _empty_bridge() -> dict[str, Any]:
    return {
        "status": "not_started",
        "terminal": None,
        "blockers": [],
        "demands": [],
        "operation_result": None,
        "category_result": None,
        "taxpayer_binding": None,
    }


def _fact_ids(value: Any) -> set[str]:
    if isinstance(value, dict):
        result = (
            {value["fact_id"]}
            if value.get("source_kind") == "normalized_source_fact"
            and isinstance(value.get("fact_id"), str)
            else set()
        )
        for nested in value.values():
            result.update(_fact_ids(nested))
        return result
    if isinstance(value, list):
        result: set[str] = set()
        for nested in value:
            result.update(_fact_ids(nested))
        return result
    return set()


def _hash_chain(stage_hashes: dict[str, str]) -> list[dict[str, str | None]]:
    rows: list[dict[str, str | None]] = []
    previous = None
    for stage, artifact_sha256 in stage_hashes.items():
        base = {
            "stage": stage,
            "artifact_sha256": artifact_sha256,
            "previous_sha256": previous,
        }
        row_hash = _sha(base)
        rows.append({**base, "row_sha256": row_hash})
        previous = row_hash
    return rows


def _route() -> list[str]:
    return [
        "OrdinaryTradeTaxModelBridgeRuntimeFactory.create",
        "Gate5IncomeGroupTaxBaseRuntimeFactory.create",
        "Gate5DeclarationTaxSettlementRuntimeFactory.create",
        "Gate5DeclarationScopeResolutionRuntimeFactory.create_current_source_fact_scope",
        "Gate5ResolvedDeclarationPackageRuntimeFactory.create_current_source_fact_package",
        "Gate5DeclarationSemanticInputRuntimeFactory.create.release_declaration_value_candidate",
        "Gate5FullTargetXmlProjectionRuntimeFactory.create.project_released",
    ]


def _constraints() -> dict[str, Any]:
    return {
        "active": False,
        "shadow_only": True,
        "persisted": False,
        "downloadable": False,
        "provider_calls": 0,
        "gate3_execution": False,
        "historical_sql_gate4_reads": False,
        "canonical_reads_downstream": False,
        "source_observation_reads_downstream": False,
        "prebuilt_tax_models": False,
    }


def _required(value: Any, key: str, owner: str) -> Any:
    if not isinstance(value, dict) or key not in value or value[key] is None:
        raise ActiveCategoryDeclarationAssemblyError(
            f"gate5_active_assembly_{_snake(owner)}_input_missing", key
        )
    return value[key]


def _gap_class(code: str) -> str:
    if "income_sources" in code or "income_source" in code:
        return "SOURCE_EVIDENCE_INSUFFICIENT"
    if "residency" in code or "filing" in code or "input_missing" in code:
        return "USER_CASE_FACT_MISSING"
    if "source" in code:
        return "SOURCE_EVIDENCE_INSUFFICIENT"
    if "completeness" in code or "binding" in code or "package" in code:
        return "INTERNAL_CONTRACT_OR_PIPELINE_DEFECT"
    return "INTERNAL_CONTRACT_OR_PIPELINE_DEFECT"


def _owner(code: str) -> str:
    owners = (
        ("income_group", "Gate5IncomeGroupTaxBaseRuntime"),
        ("residency", "Gate5ResidencyEvidenceRuntime"),
        ("filing", "Gate5FilingAndPartyIdentityRuntime"),
        ("income_source", "Gate5DeclarationIncomeSourcesRuntime"),
        ("settlement", "Gate5DeclarationTaxSettlementRuntime"),
        ("budget", "Gate5DeclarationBudgetOutcomeRuntime"),
        ("scope", "Gate5DeclarationScopeResolutionRuntime"),
        ("package", "Gate5ResolvedDeclarationPackageRuntime"),
        ("release", "Gate5DeclarationSemanticInputRuntime"),
        ("projection", "Gate5FullTargetXmlProjectionRuntime"),
    )
    return next(
        (owner for marker, owner in owners if marker in code),
        "ActiveCategoryDeclarationAssemblyRuntime",
    )


def _stage(code: str) -> str:
    return (
        _owner(code).removeprefix("Gate5").removesuffix("Runtime")
        or "declaration_assembly"
    )


def _synthetic(source_ref: str, input_channel: str) -> dict[str, Any]:
    return {
        "source_kind": "synthetic_proof_evidence",
        "source_ref": source_ref,
        "input_channel": input_channel,
        "real_user_fact": False,
    }


def _money(amount: str) -> dict[str, str]:
    return {"kind": "money", "amount": amount, "currency": "RUB"}


def _sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _snake(value: str) -> str:
    result = []
    for char in value:
        if char.isupper() and result:
            result.append("_")
        result.append(char.lower())
    return "".join(result)


def _fail(code: str, field: str = "") -> None:
    raise ActiveCategoryDeclarationAssemblyError(code, field)


__all__ = [
    "ACTIVE_CATEGORY_DECLARATION_ASSEMBLY_SCHEMA_VERSION",
    "ACTIVE_CATEGORY_TO_DECLARATION_ASSEMBLY_PROVEN",
    "BOUNDED_DECLARATION_ASSEMBLY_BLOCKERS_PROVEN",
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "ActiveCategoryDeclarationAssemblyError",
    "ActiveCategoryDeclarationAssemblyRuntime",
    "ActiveCategoryDeclarationAssemblyRuntimeFactory",
]
