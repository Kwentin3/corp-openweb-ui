"""Inactive composition from the active ordinary Category Tax Model to XSD."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .artifact_models import ArtifactAccessContext, ArtifactStorePort, RetentionPolicy
from .gate4_ordinary_trade_candidate import (
    Gate4OrdinaryTradeCandidateRuntime,
    Gate4OrdinaryTradeCandidateRuntimeFactory,
)
from .gate5_declaration_budget_outcome import (
    GATE5_DECLARATION_BUDGET_DISPOSITION_COMPONENT_SCHEMA_VERSION,
)
from .gate5_declaration_filing_context import (
    GATE5_FILING_AND_PARTY_IDENTITY_COMPONENT_SCHEMA_VERSION,
)
from .gate5_declaration_financial_investment_results import (
    GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_SCHEMA_VERSION,
)
from .gate5_declaration_income_sources import (
    GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_SCHEMA_VERSION,
)
from .gate5_declaration_right_side_assembly import (
    Gate5DeclarationRightSideAssemblyRuntime,
    Gate5DeclarationRightSideAssemblyRuntimeFactory,
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
from .gate5_income_group_tax_base import Gate5IncomeGroupTaxBaseRuntimeFactory
from .gate5_residency_evidence import gate5_residency_methodology_input
from .gate5_resolved_declaration_package import (
    Gate5ResolvedDeclarationPackageRuntimeFactory,
)
from .gate5_securities_disposal_tax_model import (
    GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION,
)
from .gate5_tax_period_category_aggregation import (
    Gate5TaxPeriodCategoryAggregationRuntimeFactory,
)
from .gate5_trusted_methodology import (
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
_CURRENT_FACT_BOUNDARY = "Gate4OrdinaryTradeCandidateRuntimeFactory.create"
_STAGE_NAMES = (
    "operation_tax_model_sha256",
    "category_tax_model_sha256",
    "income_group_tax_base_sha256",
    "scope_receipt_sha256",
    "component_set_sha256",
    "package_sha256",
    "semantic_value_sha256",
    "release_receipt_sha256",
    "projection_receipt_sha256",
    "xml_sha256",
)
_OWNER_ARTIFACT_KEYS = frozenset(
    {
        "operation_tax_model",
        "category_tax_model",
        "income_group_tax_base",
        "scope_receipt",
        "package",
        "released_values",
        "projection_input",
        "target_mechanics",
        "target_receipt",
    }
)
_EXPECTED_RELEASED_VALUES = 44
_EXPECTED_TARGET_OCCURRENCES = 49
_SUCCESS_RECEIPT_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "terminal",
        "blockers",
        "demands",
        "route",
        "identity_binding",
        "fact_v2_binding",
        "owner_artifacts",
        "stage_hashes",
        "category_to_income_group_binding",
        "hash_chain",
        "release_accounting",
        "target_accounting",
        "visual_accounting",
        "execution_constraints",
        "receipt_sha256",
    }
)

FACTORY_REQUIRED = (
    "ActiveCategoryDeclarationAssemblyRuntimeFactory.create composes existing owners",
    "Gate4OrdinaryTradeCandidateRuntimeFactory.create is injected into Scope here",
    "OrdinaryTradeTaxModelBridgeRuntimeFactory.create owns Fact v2 to Category",
    "Gate5DeclarationRightSideAssemblyRuntimeFactory.create owns the unchanged G5.35 right side",
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
        gate4_runtime = Gate4OrdinaryTradeCandidateRuntimeFactory(
            store=self._store,
            read_enabled=self._read_enabled,
        ).create()
        scope_runtime = Gate5DeclarationScopeResolutionRuntimeFactory(
            store=self._store,
            read_enabled=self._read_enabled,
            retention_policy=self._retention_policy,
        ).create_current_source_fact_scope(
            gate4_runtime=gate4_runtime,
            source_boundary=_CURRENT_FACT_BOUNDARY,
        )
        return ActiveCategoryDeclarationAssemblyRuntime(
            bridge=OrdinaryTradeTaxModelBridgeRuntimeFactory(
                store=self._store,
                read_enabled=self._read_enabled,
                retention_policy=self._retention_policy,
            ).create(),
            source_facts=gate4_runtime,
            right_side=Gate5DeclarationRightSideAssemblyRuntimeFactory.create(),
            scope=scope_runtime,
            package=Gate5ResolvedDeclarationPackageRuntimeFactory(
                store=self._store,
                read_enabled=self._read_enabled,
                retention_policy=self._retention_policy,
            ).create_current_source_fact_package(scope_runtime=scope_runtime),
        )


class ActiveCategoryDeclarationAssemblyRuntime:
    def __init__(
        self,
        *,
        bridge: OrdinaryTradeTaxModelBridgeRuntime,
        source_facts: Gate4OrdinaryTradeCandidateRuntime,
        right_side: Gate5DeclarationRightSideAssemblyRuntime,
        scope: Any,
        package: Any,
    ) -> None:
        self._bridge = bridge
        self._source_facts = source_facts
        self._right_side = right_side
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
            if "raw_ordinary_trade_table" in right_side_inputs:
                _fail(
                    "gate5_active_assembly_raw_control_forbidden",
                    "raw_ordinary_trade_table",
                )
            residency = self._right_side.residency_classification(right_side_inputs)
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
                    "gap_owner_classification": _gap_class(code, field),
                    "owner": _owner(code, field),
                    "blocking_scope": _stage(code, field),
                },
                last_stage=_stage(code, field),
            )
        return result

    def validate_receipt(
        self,
        receipt: dict[str, Any],
        *,
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        """Replay every sealed artifact through its canonical owner."""

        if not isinstance(receipt, dict):
            _fail("gate5_active_assembly_receipt_chain_invalid")
        artifacts = receipt.get("owner_artifacts")
        if (
            set(receipt) != _SUCCESS_RECEIPT_KEYS
            or receipt.get("schema_version")
            != ACTIVE_CATEGORY_DECLARATION_ASSEMBLY_SCHEMA_VERSION
            or receipt.get("status") != "proven"
            or receipt.get("terminal") != ACTIVE_CATEGORY_TO_DECLARATION_ASSEMBLY_PROVEN
            or receipt.get("blockers") != []
            or receipt.get("demands") != []
            or receipt.get("route") != _route()
            or receipt.get("execution_constraints") != _constraints()
            or not isinstance(artifacts, dict)
            or set(artifacts) != _OWNER_ARTIFACT_KEYS
            or not isinstance(receipt.get("stage_hashes"), dict)
            or tuple(receipt["stage_hashes"]) != _STAGE_NAMES
            or receipt.get("hash_chain") != _hash_chain(receipt["stage_hashes"])
        ):
            _fail("gate5_active_assembly_receipt_chain_invalid")

        category_runtime = Gate5TaxPeriodCategoryAggregationRuntimeFactory.create()
        operation = category_runtime.validate_operation_member(
            tax_model=artifacts["operation_tax_model"]
        )
        category = category_runtime.validate_category_model(
            tax_model=artifacts["category_tax_model"]
        )
        identity = category_runtime.validate_operation_taxpayer_scope_binding(
            binding=receipt.get("identity_binding")
        )
        tax_base = Gate5IncomeGroupTaxBaseRuntimeFactory.create().validate_model(
            methodology_ref=_income_group_methodology_ref(),
            tax_base_model=artifacts["income_group_tax_base"],
        )
        scope_receipt = self._scope.validate_receipt(
            receipt=artifacts["scope_receipt"],
            context=context,
        )
        if (
            identity is None
            or identity != scope_receipt.get("taxpayer_binding")
            or identity["operation_subject_ref"]
            != operation["operation_scope"]["subject_ref"]
            or identity["taxpayer_scope_ref"]
            != category["calculation_scope"]["taxpayer_scope_ref"]
            or identity["taxpayer_scope_ref"]
            != scope_receipt["scope_binding"]["taxpayer_scope_ref"]
            or receipt.get("fact_v2_binding") != scope_receipt["gate4_binding"]
            or receipt.get("category_to_income_group_binding")
            != tax_base["calculation_scope"]["input_binding"]
        ):
            _fail("gate5_active_assembly_identity_or_scope_binding_invalid")
        package = self._package.validate_package(package=artifacts["package"])
        semantic = Gate5DeclarationSemanticInputRuntimeFactory.create()
        released = semantic.validate_released_declaration_values(
            package=package,
            released=artifacts["released_values"],
        )
        projection_input = semantic.prepare_released_projection_input(
            package=package,
            released=released,
        )
        if artifacts["projection_input"] != projection_input:
            _fail("gate5_active_assembly_projection_input_invalid")
        replayed = Gate5FullTargetXmlProjectionRuntimeFactory.create().project_released(
            released_values=projection_input,
            target_mechanics=artifacts["target_mechanics"],
        )
        if replayed["receipt"] != artifacts["target_receipt"]:
            _fail("gate5_active_assembly_target_receipt_invalid")
        expected_stage_hashes = _stage_hashes(
            operation=operation,
            category=category,
            tax_base=tax_base,
            scope_receipt=scope_receipt,
            package=package,
            released=released,
            projection_receipt=replayed["receipt"],
        )
        if receipt["stage_hashes"] != expected_stage_hashes:
            _fail("gate5_active_assembly_owner_artifact_binding_invalid")

        expected_release = released["release_receipt"]["evidence_accounting"]
        expected_target = _target_accounting(
            mappings=replayed["receipt"]["semantic_mapping_proof"]["mappings"],
            release_bindings=expected_release["bindings"],
            xsd_conformance=replayed["receipt"]["conformance_proof"],
        )
        if (
            expected_release["declared_value_count"] != _EXPECTED_RELEASED_VALUES
            or expected_target["mapping_occurrences_total"]
            != _EXPECTED_TARGET_OCCURRENCES
            or expected_target["known_owner_occurrences"]
            != _EXPECTED_TARGET_OCCURRENCES
            or expected_target["xsd_conformance"].get("xsd_valid") is not True
            or receipt.get("release_accounting") != expected_release
            or receipt.get("target_accounting") != expected_target
        ):
            _fail("gate5_active_assembly_receipt_accounting_invalid")
        source_facts = tuple(self._source_facts.list_facts(context=context))
        expected_visual = _visual_accounting(
            bridge_operation=operation,
            category=category,
            tax_base=tax_base,
            package=package,
            released=released,
            projection=replayed,
            source_facts=source_facts,
            gate4_binding=scope_receipt["gate4_binding"],
        )
        if receipt.get("visual_accounting") != expected_visual:
            _fail("gate5_active_assembly_visual_accounting_invalid")
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
        tax_base = self._right_side.income_group_tax_base(
            category=category,
            residency=residency,
            inputs=right_side_inputs,
        )
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
        settlement = self._right_side.settlement_component(
            inputs=right_side_inputs,
            scope_binding=scope_binding,
            tax_base=tax_base,
        )
        income_source = self._right_side.income_source_component(
            inputs=right_side_inputs,
            scope_binding=scope_binding,
            settlement=settlement,
        )
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
        filing = self._right_side.filing_component(
            inputs=right_side_inputs,
            scope_binding=scope_binding,
            residency=residency,
        )
        budget = self._right_side.budget_component(
            inputs=right_side_inputs,
            scope_binding=scope_binding,
            filing=filing,
            settlement=settlement,
        )
        financial = self._right_side.financial_component(
            inputs=right_side_inputs,
            scope_binding=scope_binding,
            category=category,
        )
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
        stage_hashes = _stage_hashes(
            operation=operation,
            category=category,
            tax_base=tax_base,
            scope_receipt=scope_receipt,
            package=package,
            released=released,
            projection_receipt=first["receipt"],
        )
        source_facts = tuple(self._source_facts.list_facts(context=context))
        owner_artifacts = {
            "operation_tax_model": copy.deepcopy(operation),
            "category_tax_model": copy.deepcopy(category),
            "income_group_tax_base": copy.deepcopy(tax_base),
            "scope_receipt": copy.deepcopy(scope_receipt),
            "package": copy.deepcopy(package),
            "released_values": copy.deepcopy(released),
            "projection_input": copy.deepcopy(projection_input),
            "target_mechanics": copy.deepcopy(mechanics),
            "target_receipt": copy.deepcopy(first["receipt"]),
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
            "owner_artifacts": owner_artifacts,
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
                bridge_operation=operation,
                category=category,
                tax_base=tax_base,
                package=package,
                released=released,
                projection=first,
                source_facts=source_facts,
                gate4_binding=scope_receipt["gate4_binding"],
            ),
            "execution_constraints": _constraints(),
        }
        receipt = {**receipt_base, "receipt_sha256": _sha(receipt_base)}
        return self.validate_receipt(receipt, context=context)


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
    bridge_operation: dict[str, Any],
    category: dict[str, Any],
    tax_base: dict[str, Any],
    package: dict[str, Any],
    released: dict[str, Any],
    projection: dict[str, Any],
    source_facts: tuple[dict[str, Any], ...],
    gate4_binding: dict[str, Any],
) -> dict[str, Any]:
    fact_ids = sorted(_fact_ids(bridge_operation))
    return {
        "source_bound_fact_v2": _source_fact_view(
            source_facts=source_facts,
            gate4_binding=gate4_binding,
            selected_fact_ids=fact_ids,
        ),
        "fact_v2_ids": fact_ids,
        "recognized_expense_components": copy.deepcopy(
            bridge_operation["related_expenses"]["components"]
        ),
        "operation_values": {
            "gross_income": copy.deepcopy(bridge_operation["gross_income"]),
            "related_expenses": copy.deepcopy(bridge_operation["related_expenses"]),
            "allowable_expenses": copy.deepcopy(bridge_operation["allowable_expenses"]),
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


def _source_fact_view(
    *,
    source_facts: tuple[dict[str, Any], ...],
    gate4_binding: dict[str, Any],
    selected_fact_ids: list[str],
) -> list[dict[str, Any]]:
    binding_hashes = {
        item["fact_id"]: item["fact_sha256"] for item in gate4_binding["facts"]
    }
    facts = {item["fact_id"]: item for item in source_facts}
    if set(binding_hashes) != set(facts) or any(
        _sha(fact) != binding_hashes[fact_id] for fact_id, fact in facts.items()
    ):
        _fail("gate5_active_assembly_source_fact_binding_invalid")
    rows = []
    for fact_id in selected_fact_ids:
        fact = facts.get(fact_id)
        if fact is None:
            _fail("gate5_active_assembly_source_fact_missing", fact_id)
        rows.append(
            {
                "fact_id": fact_id,
                "fact_sha256": binding_hashes[fact_id],
                "financial_type": fact["financial_type"],
                "roles": [
                    {
                        "role": role["role"],
                        "normalized_value": role["value"],
                        "source_literal": role["source_binding"]["source_literal"],
                        "source_target": copy.deepcopy(
                            role["source_binding"]["target"]
                        ),
                    }
                    for role in fact["roles"]
                ],
            }
        )
    return rows


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


def _income_group_methodology_ref() -> dict[str, str]:
    return {
        "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
        "methodology_id": GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
        "methodology_version": (
            GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_VERSION
        ),
    }


def _stage_hashes(
    *,
    operation: dict[str, Any],
    category: dict[str, Any],
    tax_base: dict[str, Any],
    scope_receipt: dict[str, Any],
    package: dict[str, Any],
    released: dict[str, Any],
    projection_receipt: dict[str, Any],
) -> dict[str, str]:
    return {
        "operation_tax_model_sha256": _sha(operation),
        "category_tax_model_sha256": _sha(category),
        "income_group_tax_base_sha256": _sha(tax_base),
        "scope_receipt_sha256": scope_receipt["receipt_sha256"],
        "component_set_sha256": package["completeness_receipt"]["component_set_sha256"],
        "package_sha256": package["package_sha256"],
        "semantic_value_sha256": released["semantic_value_sha256"],
        "release_receipt_sha256": released["release_receipt"]["receipt_sha256"],
        "projection_receipt_sha256": projection_receipt["receipt_sha256"],
        "xml_sha256": projection_receipt["xml_binding"]["xml_sha256"],
    }


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
        "Gate4OrdinaryTradeCandidateRuntimeFactory.create",
        "OrdinaryTradeTaxModelBridgeRuntimeFactory.create",
        "Gate5DeclarationRightSideAssemblyRuntimeFactory.create",
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


def _gap_class(code: str, field: str = "") -> str:
    if field == "source_party":
        return "SOURCE_EVIDENCE_INSUFFICIENT"
    if "income_sources" in code or "income_source" in code:
        return "SOURCE_EVIDENCE_INSUFFICIENT"
    if (
        "residency" in code
        or "filing" in code
        or "input_missing" in code
        or "fact_missing" in code
    ):
        return "USER_CASE_FACT_MISSING"
    if "source" in code:
        return "SOURCE_EVIDENCE_INSUFFICIENT"
    if "completeness" in code or "binding" in code or "package" in code:
        return "INTERNAL_CONTRACT_OR_PIPELINE_DEFECT"
    return "INTERNAL_CONTRACT_OR_PIPELINE_DEFECT"


def _owner(code: str, field: str = "") -> str:
    if "right_side" in code or "direct_taxpayer_status" in code:
        return "Gate5DeclarationRightSideAssemblyRuntime"
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


def _stage(code: str, field: str = "") -> str:
    return (
        _owner(code, field).removeprefix("Gate5").removesuffix("Runtime")
        or "declaration_assembly"
    )


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
