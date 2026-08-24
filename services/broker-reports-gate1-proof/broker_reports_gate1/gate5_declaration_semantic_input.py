"""Minimal target-independent semantic view over a sealed Declaration package."""

from __future__ import annotations

import copy
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from typing import Any

from .gate5_resolved_declaration_package import (
    Gate5ResolvedDeclarationPackageError,
    Gate5ResolvedDeclarationPackageRuntime,
    Gate5ResolvedDeclarationPackageRuntimeFactory,
)


GATE5_DECLARATION_SEMANTIC_INPUT_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_semantic_input_v0"
)
GATE5_DECLARATION_SEMANTIC_INPUT_STATUS = "DECLARATION_SEMANTIC_INPUT_READY"
GATE5_DECLARATION_SEMANTIC_BOUNDARY_VERDICT = "H2_MINIMAL_SEMANTIC_VIEW"

_DECLARATION_VALUE_CANDIDATE_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_value_candidate_v0"
)
_DECLARATION_VALUE_CANDIDATE_STATUS = "DECLARATION_VALUE_CANDIDATE_READY_NOT_RELEASED"
_DECLARATION_VALUE_CONTRACT = {
    "id": "ru_3ndfl_2025_supplied_case_declaration_values",
    "version": "2026-08-14.0-g545-bounded",
}
_RELEASED_DECLARATION_VALUES_SCHEMA_VERSION = (
    "broker_reports_gate5_released_declaration_values_v0"
)
_DECLARATION_RELEASE_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_release_receipt_v0"
)
_DECLARATION_RELEASE_STATUS = "DECLARATION_VALUES_RELEASED"
_DECLARATION_RELEASE_POLICY = {
    "id": "supplied_case_existing_evidence_release",
    "version": "2026-08-12.0-bounded",
}
GATE5_RELEASED_DECLARATION_PROJECTION_INPUT_SCHEMA_VERSION = (
    "broker_reports_gate5_released_declaration_projection_input_v0"
)
GATE5_RELEASED_DECLARATION_PROJECTION_INPUT_STATUS = _DECLARATION_RELEASE_STATUS

FACTORY_REQUIRED = (
    "Gate5DeclarationSemanticInputRuntimeFactory.create owns semantic view construction, release accounting and the thin released projection handoff",
    "Gate5ResolvedDeclarationPackageRuntimeFactory.create_validation_only owns sealed package validation",
)
FORBIDDEN = (
    "Gate 4, SQL, ArtifactStore business-value, document, provider or LLM reads",
    "tax calculation, applicability reasoning, component selection or semantic reconstruction",
    "flattened Form DTO, target locator, XML/PDF projection or product activation",
    "new Declaration Model authority, DB, registry, graph, rules engine or framework",
)

_INPUT_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "source_binding",
        "declaration_semantics",
        "case_identity",
        "completeness",
        "domains",
        "semantic_input_sha256",
    }
)
_SOURCE_BINDING_KEYS = frozenset(
    {
        "package_sha256",
        "definition_sha256",
        "scope_receipt_sha256",
        "component_set_sha256",
        "resolution_manifest_sha256",
    }
)
_DECLARATION_SEMANTICS_KEYS = frozenset(
    {
        "definition_id",
        "definition_version",
        "jurisdiction",
        "declaration_kind",
        "tax_period",
    }
)
_CASE_IDENTITY_FIELDS = (
    "scope_ref",
    "taxpayer_scope_ref",
    "tax_period",
    "case_id",
    "scope_binding_sha256",
)
_CASE_IDENTITY_KEYS = frozenset(_CASE_IDENTITY_FIELDS)
_COMPLETENESS_KEYS = frozenset(
    {
        "completeness_kind",
        "real_world_taxpayer_completeness_asserted",
    }
)
_DOMAIN_KEYS = frozenset(
    {
        "domain_id",
        "semantic_meaning",
        "obligation_refs",
        "state",
        "typed_components",
    }
)
_COMPONENT_KEYS = frozenset(
    {
        "source_component_contract_id",
        "source_component_sha256",
        "semantic_payload",
        "semantic_payload_sha256",
    }
)
_TERMINAL_STATES = {
    "RESOLVED",
    "NOT_APPLICABLE",
    "NOT_ACTIVATED_FOR_SUPPLIED_CASE",
}
_TARGET_SPECIFIC_KEYS = {
    "electronic_format_version",
    "knd",
    "order",
    "xml_element",
    "xml_attribute",
    "pdf_field",
    "form_section",
    "form_appendix",
    "form_line",
    "target_locator",
}
_DECLARATION_VALUE_CANDIDATE_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "value_contract",
        "declaration_values",
        "semantic_value_sha256",
    }
)
_RELEASED_DECLARATION_VALUES_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "value_contract",
        "declaration_values",
        "semantic_value_sha256",
        "release_receipt",
        "released_values_sha256",
    }
)
_RELEASED_DECLARATION_PROJECTION_INPUT_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "value_contract",
        "declaration_values",
        "semantic_value_sha256",
        "release_receipt_sha256",
        "projection_input_sha256",
    }
)
_DECLARATION_RELEASE_RECEIPT_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "release_policy",
        "source_binding",
        "obligation_accounting",
        "evidence_accounting",
        "semantic_value_sha256",
        "receipt_sha256",
    }
)
_DECLARATION_RELEASE_SOURCE_BINDING_KEYS = frozenset(
    {
        "package_sha256",
        "semantic_input_sha256",
        "completeness_receipt_sha256",
        "definition_sha256",
        "scope_receipt_sha256",
        "component_set_sha256",
        "resolution_manifest_sha256",
    }
)
_DECLARATION_RELEASE_OBLIGATION_ACCOUNTING_KEYS = frozenset(
    {
        "total_count",
        "unique_count",
        "terminal_count",
        "state_counts",
        "dispositions",
        "obligation_manifest_sha256",
    }
)
_DECLARATION_RELEASE_OBLIGATION_DISPOSITION_KEYS = frozenset(
    {"obligation_ref", "domain_id", "state", "resolution_sha256"}
)
_DECLARATION_RELEASE_EVIDENCE_ACCOUNTING_KEYS = frozenset(
    {
        "declared_value_count",
        "unique_value_path_count",
        "origin_kind_counts",
        "bindings",
        "evidence_binding_manifest_sha256",
    }
)
_DECLARATION_RELEASE_BINDING_COMMON_KEYS = frozenset(
    {
        "declared_value_path",
        "origin_kind",
        "declared_value_sha256",
        "owner_factory",
        "authority_contract_id",
        "authority_sha256",
    }
)
_DECLARATION_RELEASE_DERIVED_BINDING_KEYS = frozenset(
    {
        "calculation_authority_sha256",
        "replayable_input_snapshot_sha256",
    }
)
_DECLARATION_RELEASE_DIRECT_BINDING_KEYS = frozenset({"direct_evidence_sha256"})
_DECLARATION_VALUE_ROOT_KEYS = frozenset(
    {
        "tax_period",
        "filing",
        "taxpayer",
        "signer",
        "budget_dispositions",
        "income_group_results",
        "russian_source_income",
        "financial_investment_results",
    }
)
_FILING_VALUE_KEYS = frozenset(
    {"correction_number", "declaration_date", "tax_authority_code"}
)
_TAXPAYER_VALUE_KEYS = frozenset({"inn", "name", "period_status", "declarant_category"})
_NAME_VALUE_KEYS = frozenset({"last_name", "first_name", "middle_name"})
_SIGNER_VALUE_KEYS = frozenset({"capacity"})
_BUDGET_DISPOSITION_VALUE_KEYS = frozenset(
    {"kbk", "oktmo", "payable", "refundable"}
)
_INCOME_GROUP_VALUE_KEYS = frozenset(
    {
        "income_group",
        "total_income",
        "non_taxable_income",
        "taxable_income",
        "tax_deductions",
        "accepted_expenses",
        "tax_base",
        "calculated_tax",
        "settlement_amounts",
        "tax_payable",
        "tax_refundable",
    }
)
_SETTLEMENT_AMOUNT_KEYS = frozenset(
    {
        "withheld_at_source",
        "material_benefit_withheld",
        "trade_fee_credit",
        "fixed_advance_credit",
        "foreign_tax_credit",
        "patent_credit",
        "simplified_procedure_returned_or_credited",
    }
)
_RUSSIAN_SOURCE_INCOME_VALUE_KEYS = frozenset(
    {"income_kind", "source_party", "gross_income", "withheld_tax"}
)
_SOURCE_PARTY_VALUE_KEYS = frozenset(
    {"display_name", "inn", "kpp", "oktmo"}
)
_FINANCIAL_INVESTMENT_VALUE_KEYS = frozenset(
    {
        "operation_category",
        "category_gross_income",
        "related_expenses",
        "allowable_expenses",
        "loss_treatment",
    }
)
_MONEY_VALUE_KEYS = frozenset({"kind", "amount", "currency"})
_DECLARATION_VALUE_AUDIT_KEYS = frozenset(
    {
        "package",
        "semantic_input",
        "source_binding",
        "component",
        "scope",
        "case",
        "run",
        "completeness",
        "obligation",
        "obligation_refs",
        "domain_id",
        "state",
        "status",
        "methodology_binding",
        "derivation",
        "provenance",
        "evidence",
        "input_snapshot",
        "projection_definition",
        "electronic_format_version",
        "knd",
        "program_version",
        "electronic_file_id",
        *_TARGET_SPECIFIC_KEYS,
    }
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class Gate5DeclarationSemanticInputError(ValueError):
    def __init__(self, code: str, field: str = "") -> None:
        self.code = code
        self.field = field
        super().__init__(code if not field else f"{code}:{field}")


class Gate5DeclarationSemanticInputRuntimeFactory:
    @classmethod
    def create(cls) -> "Gate5DeclarationSemanticInputRuntime":
        return Gate5DeclarationSemanticInputRuntime(
            package_runtime=(
                Gate5ResolvedDeclarationPackageRuntimeFactory.create_validation_only()
            )
        )


class Gate5DeclarationSemanticInputRuntime:
    def __init__(
        self,
        *,
        package_runtime: Gate5ResolvedDeclarationPackageRuntime,
    ) -> None:
        self._package_runtime = package_runtime

    def compile(self, *, package: dict[str, Any]) -> dict[str, Any]:
        try:
            sealed = self._package_runtime.validate_package(package=package)
        except Gate5ResolvedDeclarationPackageError as exc:
            raise Gate5DeclarationSemanticInputError(
                "gate5_declaration_semantic_source_package_invalid",
                exc.code,
            ) from exc
        return _semantic_input_from_sealed_package(sealed)

    def _validated_source_package(self, *, package: dict[str, Any]) -> dict[str, Any]:
        try:
            sealed = self._package_runtime.validate_package(package=package)
        except Gate5ResolvedDeclarationPackageError as exc:
            raise Gate5DeclarationSemanticInputError(
                "gate5_declaration_semantic_source_package_invalid",
                exc.code,
            ) from exc
        return sealed

    def validate_semantic_input(
        self,
        *,
        semantic_input: dict[str, Any],
    ) -> dict[str, Any]:
        return _validated_semantic_input(semantic_input)

    def compile_declaration_value_candidate(
        self,
        *,
        package: dict[str, Any],
    ) -> dict[str, Any]:
        semantic_input = self.compile(package=package)
        return _declaration_value_candidate(semantic_input)

    def validate_declaration_value_candidate(
        self,
        *,
        candidate: dict[str, Any],
    ) -> dict[str, Any]:
        return _validated_declaration_value_candidate(candidate)

    def release_declaration_value_candidate(
        self,
        *,
        package: dict[str, Any],
        candidate: dict[str, Any],
    ) -> dict[str, Any]:
        frozen_package = copy.deepcopy(package)
        sealed = self._validated_source_package(package=frozen_package)
        semantic_input = _semantic_input_from_sealed_package(sealed)
        expected_candidate = _declaration_value_candidate(semantic_input)
        supplied_candidate = self.validate_declaration_value_candidate(
            candidate=candidate
        )
        if supplied_candidate != expected_candidate:
            _fail("gate5_declaration_release_candidate_mismatch")
        released = _released_declaration_values(
            sealed=sealed,
            semantic_input=semantic_input,
            candidate=expected_candidate,
        )
        return _validated_released_declaration_values(released)

    def validate_released_declaration_values(
        self,
        *,
        package: dict[str, Any],
        released: dict[str, Any],
    ) -> dict[str, Any]:
        checked = _validated_released_declaration_values(released)
        candidate = {
            "schema_version": _DECLARATION_VALUE_CANDIDATE_SCHEMA_VERSION,
            "status": _DECLARATION_VALUE_CANDIDATE_STATUS,
            "value_contract": copy.deepcopy(checked["value_contract"]),
            "declaration_values": copy.deepcopy(checked["declaration_values"]),
            "semantic_value_sha256": checked["semantic_value_sha256"],
        }
        expected = self.release_declaration_value_candidate(
            package=package,
            candidate=candidate,
        )
        supplied_bindings = {
            item["declared_value_path"]: item
            for item in checked["release_receipt"]["evidence_accounting"]["bindings"]
        }
        expected_bindings = {
            item["declared_value_path"]: item
            for item in expected["release_receipt"]["evidence_accounting"]["bindings"]
        }
        for path, expected_binding in expected_bindings.items():
            supplied_binding = supplied_bindings[path]
            if supplied_binding["owner_factory"] != expected_binding["owner_factory"]:
                _fail("gate5_declaration_release_evidence_owner_unknown", path)
            if supplied_binding != expected_binding:
                _fail("gate5_declaration_release_evidence_binding_invalid", path)
        if checked != expected:
            _fail("gate5_declaration_release_package_binding_mismatch")
        return checked

    def prepare_released_projection_input(
        self,
        *,
        package: dict[str, Any],
        released: dict[str, Any],
    ) -> dict[str, Any]:
        checked = self.validate_released_declaration_values(
            package=package,
            released=released,
        )
        return _released_projection_input(checked)

    def validate_released_projection_input(
        self,
        *,
        projection_input: dict[str, Any],
    ) -> dict[str, Any]:
        return _validated_released_projection_input(projection_input)

    def reconcile_serialized_projection_values(
        self,
        *,
        projection_input: dict[str, Any],
        serialized_values: dict[str, Any],
    ) -> dict[str, Any]:
        """Bind representation-extracted literals to owner-released semantics."""

        checked = _validated_released_projection_input(projection_input)
        expected = _serialized_value_view(checked["declaration_values"])
        supplied = _validated_serialized_value_view(serialized_values)
        if supplied != expected:
            _fail("gate5_declaration_serialized_values_mismatch")
        base = {
            "schema_version": "broker_reports_gate5_serialized_value_reconciliation_v1",
            "status": "passed",
            "comparison_owner": (
                "Gate5DeclarationSemanticInputRuntimeFactory.create"
            ),
            "projection_input_sha256": checked["projection_input_sha256"],
            "values": supplied,
        }
        return {**base, "proof_sha256": _canonical_sha256(base)}


def _semantic_input_from_sealed_package(sealed: dict[str, Any]) -> dict[str, Any]:
    completeness = sealed["completeness_receipt"]
    if (
        sealed["status"] != "DECLARATION_COMPLETE_FOR_SUPPLIED_CASE"
        or completeness["status"] != "DECLARATION_COMPLETE_FOR_SUPPLIED_CASE"
        or completeness["blockers"]
        or completeness["first_blocker"] is not None
    ):
        _fail("gate5_declaration_semantic_source_package_incomplete")

    definition = sealed["definition_snapshot"]
    definition_identity = definition["declaration_identity"]
    scope_binding = sealed["scope_receipt_snapshot"]["scope_binding"]
    if not all(
        _nonempty(definition_identity.get(key))
        for key in ("jurisdiction", "form", "tax_period")
    ):
        _fail("gate5_declaration_semantic_declaration_identity_invalid")
    if definition_identity["tax_period"] != scope_binding.get("tax_period"):
        _fail("gate5_declaration_semantic_tax_period_mismatch")

    resolutions = sealed["requirement_resolutions"]
    if len(resolutions) != len(definition["domains"]):
        _fail("gate5_declaration_semantic_definition_accounting_invalid")
    components_by_domain: dict[str, list[dict[str, Any]]] = {}
    for component in sealed["component_snapshots"]:
        if component["root_coverage"] == "exact_root_domain":
            components_by_domain.setdefault(component["domain_id"], []).append(
                component
            )

    domains = []
    for domain, resolution in zip(definition["domains"], resolutions, strict=True):
        if (
            resolution["domain_id"] != domain["domain_id"]
            or resolution["state"] not in _TERMINAL_STATES
        ):
            _fail("gate5_declaration_semantic_definition_accounting_invalid")
        exact_components = components_by_domain.get(domain["domain_id"], [])
        if resolution["state"] == "RESOLVED":
            if not exact_components:
                _fail(
                    "gate5_declaration_semantic_resolved_component_missing",
                    domain["domain_id"],
                )
        elif exact_components:
            _fail(
                "gate5_declaration_semantic_terminal_component_orphan",
                domain["domain_id"],
            )
        domains.append(
            {
                "domain_id": domain["domain_id"],
                "semantic_meaning": domain["semantic_meaning"],
                "obligation_refs": copy.deepcopy(domain["obligation_refs"]),
                "state": resolution["state"],
                "typed_components": [
                    _semantic_component(domain_id=domain["domain_id"], item=item)
                    for item in exact_components
                ],
            }
        )

    base = {
        "schema_version": GATE5_DECLARATION_SEMANTIC_INPUT_SCHEMA_VERSION,
        "status": GATE5_DECLARATION_SEMANTIC_INPUT_STATUS,
        "source_binding": {
            "package_sha256": sealed["package_sha256"],
            "definition_sha256": sealed["definition_binding"]["definition_sha256"],
            "scope_receipt_sha256": sealed["scope_receipt_snapshot"]["receipt_sha256"],
            "component_set_sha256": completeness["component_set_sha256"],
            "resolution_manifest_sha256": completeness["resolution_manifest_sha256"],
        },
        "declaration_semantics": {
            "definition_id": definition["definition_id"],
            "definition_version": definition["definition_version"],
            "jurisdiction": definition_identity["jurisdiction"],
            "declaration_kind": definition_identity["form"],
            "tax_period": definition_identity["tax_period"],
        },
        "case_identity": {
            key: copy.deepcopy(scope_binding[key]) for key in _CASE_IDENTITY_FIELDS
        },
        "completeness": {
            "completeness_kind": completeness["completeness_kind"],
            "real_world_taxpayer_completeness_asserted": completeness[
                "real_world_taxpayer_completeness_asserted"
            ],
        },
        "domains": domains,
    }
    value = {**base, "semantic_input_sha256": _canonical_sha256(base)}
    return _validated_semantic_input(value)


def _declaration_value_candidate(semantic_input: dict[str, Any]) -> dict[str, Any]:
    declaration_values = _declaration_values_from_semantic_input(semantic_input)
    value_contract = copy.deepcopy(_DECLARATION_VALUE_CONTRACT)
    semantic_value = {
        "value_contract": value_contract,
        "declaration_values": declaration_values,
    }
    candidate = {
        "schema_version": _DECLARATION_VALUE_CANDIDATE_SCHEMA_VERSION,
        "status": _DECLARATION_VALUE_CANDIDATE_STATUS,
        **semantic_value,
        "semantic_value_sha256": _canonical_sha256(semantic_value),
    }
    return _validated_declaration_value_candidate(candidate)


def _released_declaration_values(
    *,
    sealed: dict[str, Any],
    semantic_input: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    dispositions = _release_obligation_dispositions(sealed)
    bindings = _release_evidence_bindings(
        sealed=sealed,
        declaration_values=candidate["declaration_values"],
    )
    state_counts = {
        state: sum(item["state"] == state for item in dispositions)
        for state in (
            "RESOLVED",
            "NOT_APPLICABLE",
            "NOT_ACTIVATED_FOR_SUPPLIED_CASE",
        )
    }
    origin_kind_counts = {
        kind: sum(item["origin_kind"] == kind for item in bindings)
        for kind in ("DERIVED", "DIRECT", "REFERENCE")
    }
    completeness = sealed["completeness_receipt"]
    receipt_base = {
        "schema_version": _DECLARATION_RELEASE_RECEIPT_SCHEMA_VERSION,
        "status": _DECLARATION_RELEASE_STATUS,
        "release_policy": copy.deepcopy(_DECLARATION_RELEASE_POLICY),
        "source_binding": {
            "package_sha256": sealed["package_sha256"],
            "semantic_input_sha256": semantic_input["semantic_input_sha256"],
            "completeness_receipt_sha256": completeness["receipt_sha256"],
            "definition_sha256": sealed["definition_binding"]["definition_sha256"],
            "scope_receipt_sha256": sealed["scope_receipt_snapshot"]["receipt_sha256"],
            "component_set_sha256": completeness["component_set_sha256"],
            "resolution_manifest_sha256": completeness["resolution_manifest_sha256"],
        },
        "obligation_accounting": {
            "total_count": len(dispositions),
            "unique_count": len({item["obligation_ref"] for item in dispositions}),
            "terminal_count": sum(
                item["state"] in _TERMINAL_STATES for item in dispositions
            ),
            "state_counts": state_counts,
            "dispositions": dispositions,
            "obligation_manifest_sha256": _canonical_sha256(dispositions),
        },
        "evidence_accounting": {
            "declared_value_count": len(bindings),
            "unique_value_path_count": len(
                {item["declared_value_path"] for item in bindings}
            ),
            "origin_kind_counts": origin_kind_counts,
            "bindings": bindings,
            "evidence_binding_manifest_sha256": _canonical_sha256(bindings),
        },
        "semantic_value_sha256": candidate["semantic_value_sha256"],
    }
    receipt = {
        **receipt_base,
        "receipt_sha256": _canonical_sha256(receipt_base),
    }
    released_base = {
        "schema_version": _RELEASED_DECLARATION_VALUES_SCHEMA_VERSION,
        "status": _DECLARATION_RELEASE_STATUS,
        "value_contract": copy.deepcopy(candidate["value_contract"]),
        "declaration_values": copy.deepcopy(candidate["declaration_values"]),
        "semantic_value_sha256": candidate["semantic_value_sha256"],
        "release_receipt": receipt,
    }
    return {
        **released_base,
        "released_values_sha256": _canonical_sha256(released_base),
    }


def _release_obligation_dispositions(
    sealed: dict[str, Any],
) -> list[dict[str, str]]:
    definitions = sealed["definition_snapshot"]["domains"]
    resolutions = sealed["requirement_resolutions"]
    if len(definitions) != len(resolutions):
        _fail("gate5_declaration_release_obligation_accounting_invalid")
    result = []
    seen = set()
    for definition, resolution in zip(definitions, resolutions, strict=True):
        if (
            definition["domain_id"] != resolution["domain_id"]
            or resolution["state"] not in _TERMINAL_STATES
            or not _sha256(resolution.get("resolution_sha256"))
        ):
            _fail("gate5_declaration_release_obligation_incomplete")
        for obligation_ref in definition["obligation_refs"]:
            if not _nonempty(obligation_ref):
                _fail("gate5_declaration_release_obligation_unknown")
            if obligation_ref in seen:
                _fail(
                    "gate5_declaration_release_obligation_duplicate",
                    obligation_ref,
                )
            seen.add(obligation_ref)
            result.append(
                {
                    "obligation_ref": obligation_ref,
                    "domain_id": definition["domain_id"],
                    "state": resolution["state"],
                    "resolution_sha256": resolution["resolution_sha256"],
                }
            )
    if not result:
        _fail("gate5_declaration_release_obligation_accounting_invalid")
    return result


def _release_evidence_bindings(
    *,
    sealed: dict[str, Any],
    declaration_values: dict[str, Any],
) -> list[dict[str, Any]]:
    components: dict[str, dict[str, Any]] = {}
    for item in sealed["component_snapshots"]:
        if item["root_coverage"] != "exact_root_domain":
            continue
        domain_id = item["domain_id"]
        if domain_id in components:
            _fail("gate5_declaration_release_evidence_binding_duplicate", domain_id)
        components[domain_id] = item
    try:
        return [
            _release_evidence_binding(
                path=path,
                value=value,
                sealed=sealed,
                components=components,
            )
            for path, value in _release_value_items(declaration_values)
        ]
    except (IndexError, KeyError, TypeError) as exc:
        _fail("gate5_declaration_release_evidence_binding_missing", str(exc))


def _release_evidence_binding(
    *,
    path: str,
    value: Any,
    sealed: dict[str, Any],
    components: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if path == "$.tax_period":
        definition = sealed["definition_snapshot"]
        scope_binding = sealed["scope_receipt_snapshot"]["scope_binding"]
        return _release_direct_binding(
            path=path,
            value=value,
            origin_kind="REFERENCE",
            owner_factory=(
                "Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create.resolve"
            ),
            authority_contract_id=(
                f"{definition['definition_id']}@{definition['definition_version']}"
            ),
            authority_sha256=sealed["definition_binding"]["definition_sha256"],
            direct_evidence={
                "declaration_identity": definition["declaration_identity"],
                "scope_tax_period": scope_binding["tax_period"],
            },
        )

    if path.startswith(("$.filing.", "$.taxpayer.", "$.signer.")):
        component = _release_component(components, "filing_and_party_identity")
        return _release_direct_component_binding(
            path=path,
            value=value,
            component=component,
            direct_evidence=component["snapshot"]["input_snapshot"]["evidence"],
        )

    indexed = _release_indexed_path(path, "budget_dispositions")
    if indexed is not None:
        _, field = indexed
        component = _release_component(components, "declaration_budget_disposition")
        snapshot = component["snapshot"]
        if field in {"payable", "refundable"}:
            return _release_derived_component_binding(
                path=path,
                value=value,
                component=component,
                owner_factory="Gate5DeclarationBudgetOutcomeRuntimeFactory.create",
                calculation_authority=snapshot["disposition"]["derivation"],
                replayable_input=snapshot["input_snapshot"],
            )
        if field in {"kbk", "oktmo"}:
            return _release_direct_component_binding(
                path=path,
                value=value,
                component=component,
                origin_kind="REFERENCE",
                direct_evidence=snapshot["input_snapshot"]["allocation_evidence"],
            )

    indexed = _release_indexed_path(path, "income_group_results")
    if indexed is not None:
        index, field = indexed
        component = _release_component(components, "income_group_tax_results")
        group = component["snapshot"]["group_results"][index]
        model = group["tax_base_model"]
        if field in {
            "income_group",
            "total_income",
            "taxable_income",
            "accepted_expenses",
            "tax_base",
        }:
            return _release_derived_binding(
                path=path,
                value=value,
                owner_factory="Gate5IncomeGroupTaxBaseRuntimeFactory.create",
                authority_contract_id=model["schema_version"],
                authority_sha256=group["tax_base_model_sha256"],
                calculation_authority=model["methodology_binding"],
                replayable_input=model["input_snapshot"],
            )
        if field in {"calculated_tax", "tax_payable", "tax_refundable"}:
            return _release_derived_component_binding(
                path=path,
                value=value,
                component=component,
                owner_factory="Gate5DeclarationTaxSettlementRuntimeFactory.create",
                calculation_authority={
                    "methodology_binding": component["snapshot"]["methodology_binding"],
                    "derivation": group["derivation"],
                },
                replayable_input=component["snapshot"]["input_snapshot"],
            )
        if field in {"non_taxable_income", "tax_deductions"}:
            return _release_direct_component_binding(
                path=path,
                value=value,
                component=component,
                direct_evidence=model["input_snapshot"]["group_values"][field],
            )
        settlement_prefix = "settlement_amounts."
        if field.startswith(settlement_prefix):
            settlement_name = field[len(settlement_prefix) :]
            if settlement_name == "simplified_procedure_returned_or_credited":
                budget = _release_component(
                    components,
                    "declaration_budget_disposition",
                )
                return _release_direct_component_binding(
                    path=path,
                    value=value,
                    component=budget,
                    direct_evidence=budget["snapshot"]["input_snapshot"][
                        "allocation_evidence"
                    ],
                )
            return _release_direct_component_binding(
                path=path,
                value=value,
                component=component,
                direct_evidence=group["settlement_facts"][settlement_name],
            )

    indexed = _release_indexed_path(path, "russian_source_income")
    if indexed is not None:
        index, _ = indexed
        component = _release_component(components, "taxable_income_by_source")
        entry = component["snapshot"]["source_entries"][index]
        return _release_direct_component_binding(
            path=path,
            value=value,
            component=component,
            direct_evidence=entry["provenance"],
        )

    indexed = _release_indexed_path(path, "financial_investment_results")
    if indexed is not None:
        index, _ = indexed
        component = _release_component(components, "financial_investment_results")
        model = component["snapshot"]["category_tax_models"][index]
        return _release_derived_binding(
            path=path,
            value=value,
            owner_factory="Gate5TaxPeriodCategoryAggregationRuntimeFactory.create",
            authority_contract_id=model["schema_version"],
            authority_sha256=_canonical_sha256(model),
            calculation_authority=model["methodology_binding"],
            replayable_input={
                "calculation_scope": model["calculation_scope"],
                "member_operations": model["member_operations"],
            },
        )

    _fail("gate5_declaration_release_evidence_binding_unknown", path)


def _release_component(
    components: dict[str, dict[str, Any]],
    domain_id: str,
) -> dict[str, Any]:
    component = components.get(domain_id)
    if component is None:
        _fail("gate5_declaration_release_evidence_binding_missing", domain_id)
    return component


def _release_direct_component_binding(
    *,
    path: str,
    value: Any,
    component: dict[str, Any],
    direct_evidence: Any,
    origin_kind: str = "DIRECT",
) -> dict[str, Any]:
    return _release_direct_binding(
        path=path,
        value=value,
        origin_kind=origin_kind,
        owner_factory=component["component_owner"],
        authority_contract_id=component["component_contract_id"],
        authority_sha256=component["content_sha256"],
        direct_evidence=direct_evidence,
    )


def _release_direct_binding(
    *,
    path: str,
    value: Any,
    origin_kind: str,
    owner_factory: str,
    authority_contract_id: str,
    authority_sha256: str,
    direct_evidence: Any,
) -> dict[str, Any]:
    return {
        "declared_value_path": path,
        "origin_kind": origin_kind,
        "declared_value_sha256": _canonical_sha256(value),
        "owner_factory": owner_factory,
        "authority_contract_id": authority_contract_id,
        "authority_sha256": authority_sha256,
        "direct_evidence_sha256": _canonical_sha256(direct_evidence),
    }


def _release_derived_component_binding(
    *,
    path: str,
    value: Any,
    component: dict[str, Any],
    owner_factory: str,
    calculation_authority: Any,
    replayable_input: Any,
) -> dict[str, Any]:
    return _release_derived_binding(
        path=path,
        value=value,
        owner_factory=owner_factory,
        authority_contract_id=component["component_contract_id"],
        authority_sha256=component["content_sha256"],
        calculation_authority=calculation_authority,
        replayable_input=replayable_input,
    )


def _release_derived_binding(
    *,
    path: str,
    value: Any,
    owner_factory: str,
    authority_contract_id: str,
    authority_sha256: str,
    calculation_authority: Any,
    replayable_input: Any,
) -> dict[str, Any]:
    return {
        "declared_value_path": path,
        "origin_kind": "DERIVED",
        "declared_value_sha256": _canonical_sha256(value),
        "owner_factory": owner_factory,
        "authority_contract_id": authority_contract_id,
        "authority_sha256": authority_sha256,
        "calculation_authority_sha256": _canonical_sha256(calculation_authority),
        "replayable_input_snapshot_sha256": _canonical_sha256(replayable_input),
    }


def _release_indexed_path(path: str, collection: str) -> tuple[int, str] | None:
    match = re.fullmatch(rf"\$\.{re.escape(collection)}\[([0-9]+)\]\.(.+)", path)
    if match is None:
        return None
    return int(match.group(1)), match.group(2)


def _release_value_items(
    value: Any,
    path: str = "$",
) -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        if set(value) == _MONEY_VALUE_KEYS and value.get("kind") == "money":
            return [(path, copy.deepcopy(value))]
        result = []
        for key, item in value.items():
            result.extend(_release_value_items(item, f"{path}.{key}"))
        return result
    if isinstance(value, list):
        result = []
        for index, item in enumerate(value):
            result.extend(_release_value_items(item, f"{path}[{index}]"))
        return result
    return [(path, copy.deepcopy(value))]


def _validated_released_declaration_values(value: Any) -> dict[str, Any]:
    released = _release_mapping(
        value,
        required=_RELEASED_DECLARATION_VALUES_KEYS,
        path="released",
    )
    if (
        released["schema_version"] != _RELEASED_DECLARATION_VALUES_SCHEMA_VERSION
        or released["status"] != _DECLARATION_RELEASE_STATUS
    ):
        _release_invalid("released")
    candidate = {
        "schema_version": _DECLARATION_VALUE_CANDIDATE_SCHEMA_VERSION,
        "status": _DECLARATION_VALUE_CANDIDATE_STATUS,
        "value_contract": copy.deepcopy(released["value_contract"]),
        "declaration_values": copy.deepcopy(released["declaration_values"]),
        "semantic_value_sha256": released["semantic_value_sha256"],
    }
    _validated_declaration_value_candidate(candidate)
    _validate_release_receipt(
        released["release_receipt"],
        declaration_values=released["declaration_values"],
        semantic_value_sha256=released["semantic_value_sha256"],
    )
    released_base = {
        key: copy.deepcopy(item)
        for key, item in released.items()
        if key != "released_values_sha256"
    }
    if not _sha256(released["released_values_sha256"]) or released[
        "released_values_sha256"
    ] != _canonical_sha256(released_base):
        _fail("gate5_declaration_release_hash_mismatch")
    return copy.deepcopy(released)


def _serialized_value_view(values: dict[str, Any]) -> dict[str, Any]:
    income = values["income_group_results"]
    source = values["russian_source_income"]
    financial = values["financial_investment_results"]
    budget = values["budget_dispositions"]
    if not all(len(rows) == 1 for rows in (income, source, financial, budget)):
        _fail("gate5_declaration_serialized_profile_unsupported")
    group = income[0]

    def amount(value: Any) -> str:
        try:
            return _normalized_nonnegative_decimal(value["amount"])
        except (InvalidOperation, KeyError, TypeError):
            _fail("gate5_declaration_serialized_values_invalid")

    return {
        "income_group": {
            key: amount(group[key])
            for key in (
                "total_income",
                "non_taxable_income",
                "taxable_income",
                "tax_deductions",
                "accepted_expenses",
                "tax_base",
                "calculated_tax",
            )
        }
        | {
            "settlement_amounts": {
                key: amount(group["settlement_amounts"][key])
                for key in (
                    "withheld_at_source",
                    "material_benefit_withheld",
                    "trade_fee_credit",
                    "fixed_advance_credit",
                    "foreign_tax_credit",
                    "patent_credit",
                )
            },
            "tax_payable": amount(group["tax_payable"]),
            "tax_refundable": amount(group["tax_refundable"]),
            "simplified_procedure_returned_or_credited": amount(
                group["settlement_amounts"][
                    "simplified_procedure_returned_or_credited"
                ]
            ),
        },
        "financial_investment": {
            "category_gross_income": amount(financial[0]["category_gross_income"]),
            "related_expenses": amount(financial[0]["related_expenses"]),
            "allowable_expenses": amount(financial[0]["allowable_expenses"]),
        },
        "russian_source": {
            "gross_income": amount(source[0]["gross_income"]),
            "withheld_tax": amount(source[0]["withheld_tax"]),
        },
        "budget": {
            "payable": amount(budget[0]["payable"]),
            "refundable": amount(budget[0]["refundable"]),
        },
    }


def _validated_serialized_value_view(value: Any) -> dict[str, Any]:
    expected_keys = {
        "income_group": {
            "total_income",
            "non_taxable_income",
            "taxable_income",
            "tax_deductions",
            "accepted_expenses",
            "tax_base",
            "calculated_tax",
            "settlement_amounts",
            "tax_payable",
            "tax_refundable",
            "simplified_procedure_returned_or_credited",
        },
        "financial_investment": {
            "category_gross_income", "related_expenses", "allowable_expenses"
        },
        "russian_source": {"gross_income", "withheld_tax"},
        "budget": {"payable", "refundable"},
    }
    credit_keys = {
        "withheld_at_source",
        "material_benefit_withheld",
        "trade_fee_credit",
        "fixed_advance_credit",
        "foreign_tax_credit",
        "patent_credit",
    }
    try:
        valid = (
            isinstance(value, dict)
            and set(value) == set(expected_keys)
            and all(
                isinstance(value[key], dict)
                and set(value[key]) == keys
                for key, keys in expected_keys.items()
            )
            and isinstance(value["income_group"]["settlement_amounts"], dict)
            and set(value["income_group"]["settlement_amounts"]) == credit_keys
        )
    except (KeyError, TypeError):
        valid = False
    if not valid:
        _fail("gate5_declaration_serialized_values_invalid")
    normalized = copy.deepcopy(value)
    for section, fields in expected_keys.items():
        for field in fields - {"settlement_amounts"}:
            normalized[section][field] = _normalized_nonnegative_decimal(
                value[section][field]
            )
    normalized["income_group"]["settlement_amounts"] = {
        key: _normalized_nonnegative_decimal(
            value["income_group"]["settlement_amounts"][key]
        )
        for key in sorted(credit_keys)
    }
    return normalized


def _normalized_nonnegative_decimal(value: Any) -> str:
    if not isinstance(value, str):
        _fail("gate5_declaration_serialized_values_invalid")
    try:
        parsed = Decimal(value)
    except (InvalidOperation, TypeError):
        _fail("gate5_declaration_serialized_values_invalid")
    if not parsed.is_finite() or parsed < 0:
        _fail("gate5_declaration_serialized_values_invalid")
    return format(parsed.normalize(), "f")


def _released_projection_input(released: dict[str, Any]) -> dict[str, Any]:
    base = {
        "schema_version": (
            GATE5_RELEASED_DECLARATION_PROJECTION_INPUT_SCHEMA_VERSION
        ),
        "status": GATE5_RELEASED_DECLARATION_PROJECTION_INPUT_STATUS,
        "value_contract": copy.deepcopy(released["value_contract"]),
        "declaration_values": copy.deepcopy(released["declaration_values"]),
        "semantic_value_sha256": released["semantic_value_sha256"],
        "release_receipt_sha256": released["release_receipt"]["receipt_sha256"],
    }
    return _validated_released_projection_input(
        {**base, "projection_input_sha256": _canonical_sha256(base)}
    )


def _validated_released_projection_input(value: Any) -> dict[str, Any]:
    projection_input = _release_mapping(
        value,
        required=_RELEASED_DECLARATION_PROJECTION_INPUT_KEYS,
        path="projection_input",
    )
    if (
        projection_input["schema_version"]
        != GATE5_RELEASED_DECLARATION_PROJECTION_INPUT_SCHEMA_VERSION
        or projection_input["status"]
        != GATE5_RELEASED_DECLARATION_PROJECTION_INPUT_STATUS
        or not _sha256(projection_input["release_receipt_sha256"])
    ):
        _release_invalid("projection_input")
    candidate = {
        "schema_version": _DECLARATION_VALUE_CANDIDATE_SCHEMA_VERSION,
        "status": _DECLARATION_VALUE_CANDIDATE_STATUS,
        "value_contract": copy.deepcopy(projection_input["value_contract"]),
        "declaration_values": copy.deepcopy(
            projection_input["declaration_values"]
        ),
        "semantic_value_sha256": projection_input["semantic_value_sha256"],
    }
    _validated_declaration_value_candidate(candidate)
    base = {
        key: copy.deepcopy(item)
        for key, item in projection_input.items()
        if key != "projection_input_sha256"
    }
    if (
        not _sha256(projection_input["projection_input_sha256"])
        or projection_input["projection_input_sha256"]
        != _canonical_sha256(base)
    ):
        _fail("gate5_declaration_projection_input_hash_mismatch")
    return copy.deepcopy(projection_input)


def _validate_release_receipt(
    value: Any,
    *,
    declaration_values: dict[str, Any],
    semantic_value_sha256: str,
) -> None:
    receipt = _release_mapping(
        value,
        required=_DECLARATION_RELEASE_RECEIPT_KEYS,
        path="release_receipt",
    )
    if (
        receipt["schema_version"] != _DECLARATION_RELEASE_RECEIPT_SCHEMA_VERSION
        or receipt["status"] != _DECLARATION_RELEASE_STATUS
        or receipt["release_policy"] != _DECLARATION_RELEASE_POLICY
        or receipt["semantic_value_sha256"] != semantic_value_sha256
    ):
        _release_invalid("release_receipt")
    source_binding = _release_mapping(
        receipt["source_binding"],
        required=_DECLARATION_RELEASE_SOURCE_BINDING_KEYS,
        path="release_receipt.source_binding",
    )
    if not all(_sha256(source_binding[key]) for key in source_binding):
        _release_invalid("release_receipt.source_binding")
    _validate_release_obligation_accounting(receipt["obligation_accounting"])
    _validate_release_evidence_accounting(
        receipt["evidence_accounting"],
        declaration_values=declaration_values,
    )
    receipt_base = {
        key: copy.deepcopy(item)
        for key, item in receipt.items()
        if key != "receipt_sha256"
    }
    if not _sha256(receipt["receipt_sha256"]) or receipt[
        "receipt_sha256"
    ] != _canonical_sha256(receipt_base):
        _fail("gate5_declaration_release_receipt_hash_mismatch")


def _validate_release_obligation_accounting(value: Any) -> None:
    accounting = _release_mapping(
        value,
        required=_DECLARATION_RELEASE_OBLIGATION_ACCOUNTING_KEYS,
        path="release_receipt.obligation_accounting",
    )
    dispositions = accounting["dispositions"]
    if not isinstance(dispositions, list) or not dispositions:
        _fail("gate5_declaration_release_obligation_incomplete")
    seen = set()
    states = []
    for item in dispositions:
        row = _release_mapping(
            item,
            required=_DECLARATION_RELEASE_OBLIGATION_DISPOSITION_KEYS,
            path="release_receipt.obligation_accounting.disposition",
        )
        obligation_ref = row["obligation_ref"]
        if not _nonempty(obligation_ref) or not _nonempty(row["domain_id"]):
            _fail("gate5_declaration_release_obligation_unknown")
        if obligation_ref in seen:
            _fail("gate5_declaration_release_obligation_duplicate", obligation_ref)
        if row["state"] not in _TERMINAL_STATES:
            _fail("gate5_declaration_release_obligation_incomplete", obligation_ref)
        if not _sha256(row["resolution_sha256"]):
            _release_invalid("release_receipt.obligation_accounting.disposition")
        seen.add(obligation_ref)
        states.append(row["state"])
    expected_counts = {
        state: states.count(state)
        for state in (
            "RESOLVED",
            "NOT_APPLICABLE",
            "NOT_ACTIVATED_FOR_SUPPLIED_CASE",
        )
    }
    if (
        accounting["total_count"] != len(dispositions)
        or accounting["unique_count"] != len(seen)
        or accounting["terminal_count"] != len(dispositions)
        or accounting["state_counts"] != expected_counts
        or accounting["obligation_manifest_sha256"] != _canonical_sha256(dispositions)
    ):
        _fail("gate5_declaration_release_obligation_accounting_invalid")


def _validate_release_evidence_accounting(
    value: Any,
    *,
    declaration_values: dict[str, Any],
) -> None:
    accounting = _release_mapping(
        value,
        required=_DECLARATION_RELEASE_EVIDENCE_ACCOUNTING_KEYS,
        path="release_receipt.evidence_accounting",
    )
    bindings = accounting["bindings"]
    if not isinstance(bindings, list):
        _release_invalid("release_receipt.evidence_accounting.bindings")
    supplied_paths = []
    for item in bindings:
        if not isinstance(item, dict):
            _release_invalid("release_receipt.evidence_accounting.binding")
        path = item.get("declared_value_path")
        if path in supplied_paths:
            _fail("gate5_declaration_release_evidence_binding_duplicate", str(path))
        supplied_paths.append(path)
    declared_items = _release_value_items(declaration_values)
    declared_by_path = dict(declared_items)
    declared_paths = [path for path, _ in declared_items]
    missing = [path for path in declared_paths if path not in supplied_paths]
    if missing:
        _fail("gate5_declaration_release_evidence_binding_missing", missing[0])
    unknown = [path for path in supplied_paths if path not in declared_by_path]
    if unknown:
        _fail("gate5_declaration_release_evidence_binding_unknown", str(unknown[0]))
    if supplied_paths != declared_paths:
        _fail("gate5_declaration_release_evidence_binding_order_invalid")
    origins = []
    for item in bindings:
        path = item["declared_value_path"]
        origin = item.get("origin_kind")
        required = (
            _DECLARATION_RELEASE_BINDING_COMMON_KEYS
            | _DECLARATION_RELEASE_DERIVED_BINDING_KEYS
            if origin == "DERIVED"
            else _DECLARATION_RELEASE_BINDING_COMMON_KEYS
            | _DECLARATION_RELEASE_DIRECT_BINDING_KEYS
        )
        row = _release_mapping(
            item,
            required=required,
            path="release_receipt.evidence_accounting.binding",
        )
        if origin not in {"DERIVED", "DIRECT", "REFERENCE"}:
            _release_invalid("release_receipt.evidence_accounting.binding.origin_kind")
        if (
            not _nonempty(row["owner_factory"])
            or not _nonempty(row["authority_contract_id"])
            or not _sha256(row["declared_value_sha256"])
            or row["declared_value_sha256"] != _canonical_sha256(declared_by_path[path])
            or not _sha256(row["authority_sha256"])
        ):
            _fail("gate5_declaration_release_evidence_binding_invalid", path)
        variant_hashes = (
            _DECLARATION_RELEASE_DERIVED_BINDING_KEYS
            if origin == "DERIVED"
            else _DECLARATION_RELEASE_DIRECT_BINDING_KEYS
        )
        if not all(_sha256(row[key]) for key in variant_hashes):
            _fail("gate5_declaration_release_evidence_binding_invalid", path)
        origins.append(origin)
    expected_origin_counts = {
        kind: origins.count(kind) for kind in ("DERIVED", "DIRECT", "REFERENCE")
    }
    if (
        accounting["declared_value_count"] != len(declared_paths)
        or accounting["unique_value_path_count"] != len(set(supplied_paths))
        or accounting["origin_kind_counts"] != expected_origin_counts
        or accounting["evidence_binding_manifest_sha256"] != _canonical_sha256(bindings)
    ):
        _fail("gate5_declaration_release_evidence_accounting_invalid")


def _release_mapping(
    value: Any,
    *,
    required: frozenset[str],
    path: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != required:
        _release_invalid(path)
    return value


def _release_invalid(path: str) -> None:
    _fail("gate5_declaration_release_invalid", path)


def _declaration_values_from_semantic_input(
    semantic_input: dict[str, Any],
) -> dict[str, Any]:
    filing_payload = _candidate_domain_payload(
        semantic_input,
        "filing_and_party_identity",
    )
    budget_payload = _candidate_domain_payload(
        semantic_input,
        "declaration_budget_disposition",
    )
    income_payload = _candidate_domain_payload(
        semantic_input,
        "income_group_tax_results",
    )
    source_payload = _candidate_domain_payload(
        semantic_input,
        "taxable_income_by_source",
    )
    financial_payload = _candidate_domain_payload(
        semantic_input,
        "financial_investment_results",
    )
    try:
        filing = filing_payload["filing_instance"]
        taxpayer = filing_payload["taxpayer"]
        source_signer = filing_payload["signer"]
        signer = {"capacity": copy.deepcopy(source_signer["signer_capacity"])}

        budget_dispositions = [
            {
                "kbk": copy.deepcopy(row["kbk"]),
                "oktmo": copy.deepcopy(row["oktmo"]),
                "payable": copy.deepcopy(row["amount"]),
                "refundable": copy.deepcopy(
                    budget_payload["refund_available_amount"]
                ),
            }
            for row in budget_payload["budget_allocations"]
        ]
        income_group_results = [
            {
                "income_group": copy.deepcopy(row["income_group_semantic"]),
                "total_income": copy.deepcopy(row["total_income"]),
                "non_taxable_income": copy.deepcopy(row["non_taxable_income"]),
                "taxable_income": copy.deepcopy(row["taxable_income"]),
                "tax_deductions": copy.deepcopy(row["tax_deductions"]),
                "accepted_expenses": copy.deepcopy(row["accepted_expenses"]),
                "tax_base": copy.deepcopy(row["tax_base"]),
                "calculated_tax": copy.deepcopy(row["calculated_tax"]),
                "settlement_amounts": {
                    **copy.deepcopy(row["settlement_facts"]),
                    "simplified_procedure_returned_or_credited": copy.deepcopy(
                        budget_payload[
                            "simplified_procedure_returned_or_credited_amount"
                        ]
                    ),
                },
                "tax_payable": copy.deepcopy(row["tax_payable"]),
                "tax_refundable": copy.deepcopy(row["tax_refundable"]),
            }
            for row in income_payload["group_results"]
        ]
        source_entries = source_payload["source_entries"]
        if any(
            row["jurisdiction_kind"] != "russian_source"
            or row["jurisdiction_code"] != "RU"
            for row in source_entries
        ):
            _candidate_missing("russian_source_income")
        russian_source_income = [
            {
                "income_kind": copy.deepcopy(row["income_kind"]),
                "source_party": {
                    key: copy.deepcopy(row["source_party"][key])
                    for key in _SOURCE_PARTY_VALUE_KEYS
                },
                "gross_income": copy.deepcopy(row["gross_income"]),
                "withheld_tax": copy.deepcopy(row["tax_agent"]["withheld_tax"]),
            }
            for row in source_entries
        ]
        financial_investment_results = [
            {
                "operation_category": copy.deepcopy(row["operation_category"]),
                "category_gross_income": copy.deepcopy(row["category_gross_income"]),
                "related_expenses": copy.deepcopy(row["related_expenses"]),
                "allowable_expenses": copy.deepcopy(row["allowable_expenses"]),
                "loss_treatment": copy.deepcopy(row["loss_treatment"]),
            }
            for row in financial_payload["category_results"]
        ]
        return {
            "tax_period": copy.deepcopy(
                semantic_input["declaration_semantics"]["tax_period"]
            ),
            "filing": {
                "correction_number": copy.deepcopy(filing["correction_number"]),
                "declaration_date": copy.deepcopy(filing["declaration_date"]),
                "tax_authority_code": copy.deepcopy(filing["tax_authority_code"]),
            },
            "taxpayer": {
                "inn": copy.deepcopy(taxpayer["inn"]),
                "name": {
                    "last_name": copy.deepcopy(taxpayer["last_name"]),
                    "first_name": copy.deepcopy(taxpayer["first_name"]),
                    "middle_name": copy.deepcopy(taxpayer["middle_name"]),
                },
                "period_status": copy.deepcopy(taxpayer["period_status"]),
                "declarant_category": copy.deepcopy(taxpayer["declarant_category"]),
            },
            "signer": signer,
            "budget_dispositions": budget_dispositions,
            "income_group_results": income_group_results,
            "russian_source_income": russian_source_income,
            "financial_investment_results": financial_investment_results,
        }
    except (KeyError, TypeError) as exc:
        _candidate_missing(str(exc))


def _candidate_domain_payload(
    semantic_input: dict[str, Any],
    domain_id: str,
) -> dict[str, Any]:
    rows = [
        row
        for row in semantic_input.get("domains", [])
        if row.get("domain_id") == domain_id
    ]
    if (
        len(rows) != 1
        or rows[0].get("state") != "RESOLVED"
        or not isinstance(rows[0].get("typed_components"), list)
        or len(rows[0]["typed_components"]) != 1
        or not isinstance(
            rows[0]["typed_components"][0].get("semantic_payload"),
            dict,
        )
    ):
        _candidate_missing(domain_id)
    return rows[0]["typed_components"][0]["semantic_payload"]


def _validated_declaration_value_candidate(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        _assert_candidate_no_audit_leakage(value.get("declaration_values"))
    candidate = _candidate_mapping(
        value,
        required=_DECLARATION_VALUE_CANDIDATE_KEYS,
        path="candidate",
    )
    if (
        candidate["schema_version"] != _DECLARATION_VALUE_CANDIDATE_SCHEMA_VERSION
        or candidate["status"] != _DECLARATION_VALUE_CANDIDATE_STATUS
    ):
        _candidate_invalid("candidate")
    value_contract = _candidate_mapping(
        candidate["value_contract"],
        required=frozenset(_DECLARATION_VALUE_CONTRACT),
        path="value_contract",
    )
    if value_contract != _DECLARATION_VALUE_CONTRACT:
        _candidate_invalid("value_contract")
    values = _candidate_mapping(
        candidate["declaration_values"],
        required=_DECLARATION_VALUE_ROOT_KEYS,
        path="declaration_values",
    )
    _validate_candidate_declaration_values(values)
    if not _sha256(candidate["semantic_value_sha256"]):
        _candidate_invalid("semantic_value_sha256")
    semantic_value = {
        "value_contract": copy.deepcopy(value_contract),
        "declaration_values": copy.deepcopy(values),
    }
    if candidate["semantic_value_sha256"] != _canonical_sha256(semantic_value):
        _fail("gate5_declaration_value_candidate_hash_mismatch")
    return copy.deepcopy(candidate)


def _validate_candidate_declaration_values(values: dict[str, Any]) -> None:
    _candidate_string(values["tax_period"], "declaration_values.tax_period")
    filing = _candidate_mapping(
        values["filing"],
        required=_FILING_VALUE_KEYS,
        path="declaration_values.filing",
    )
    if (
        not isinstance(filing["correction_number"], int)
        or isinstance(filing["correction_number"], bool)
        or filing["correction_number"] < 0
    ):
        _candidate_invalid("declaration_values.filing.correction_number")
    for key in ("declaration_date", "tax_authority_code"):
        _candidate_string(filing[key], f"declaration_values.filing.{key}")

    taxpayer = _candidate_mapping(
        values["taxpayer"],
        required=_TAXPAYER_VALUE_KEYS,
        path="declaration_values.taxpayer",
    )
    for key in ("inn", "period_status", "declarant_category"):
        _candidate_string(taxpayer[key], f"declaration_values.taxpayer.{key}")
    name = _candidate_mapping(
        taxpayer["name"],
        required=_NAME_VALUE_KEYS,
        path="declaration_values.taxpayer.name",
    )
    for key in _NAME_VALUE_KEYS:
        _candidate_string(name[key], f"declaration_values.taxpayer.name.{key}")

    signer = _candidate_mapping(
        values["signer"],
        required=_SIGNER_VALUE_KEYS,
        path="declaration_values.signer",
    )
    _candidate_string(signer["capacity"], "declaration_values.signer.capacity")

    _candidate_rows(
        values["budget_dispositions"],
        path="declaration_values.budget_dispositions",
        required=_BUDGET_DISPOSITION_VALUE_KEYS,
        validator=_validate_budget_disposition_value,
    )
    _candidate_rows(
        values["income_group_results"],
        path="declaration_values.income_group_results",
        required=_INCOME_GROUP_VALUE_KEYS,
        validator=_validate_income_group_value,
    )
    _candidate_rows(
        values["russian_source_income"],
        path="declaration_values.russian_source_income",
        required=_RUSSIAN_SOURCE_INCOME_VALUE_KEYS,
        validator=_validate_russian_source_income_value,
    )
    _candidate_rows(
        values["financial_investment_results"],
        path="declaration_values.financial_investment_results",
        required=_FINANCIAL_INVESTMENT_VALUE_KEYS,
        validator=_validate_financial_investment_value,
    )


def _validate_budget_disposition_value(value: dict[str, Any], path: str) -> None:
    for key in ("kbk", "oktmo"):
        _candidate_string(value[key], f"{path}.{key}")
    _candidate_money(value["payable"], f"{path}.payable")
    _candidate_money(value["refundable"], f"{path}.refundable")


def _validate_income_group_value(value: dict[str, Any], path: str) -> None:
    _candidate_string(value["income_group"], f"{path}.income_group")
    for key in (
        "total_income",
        "non_taxable_income",
        "taxable_income",
        "tax_deductions",
        "accepted_expenses",
        "tax_base",
        "calculated_tax",
        "tax_payable",
        "tax_refundable",
    ):
        _candidate_money(value[key], f"{path}.{key}")
    settlements = _candidate_mapping(
        value["settlement_amounts"],
        required=_SETTLEMENT_AMOUNT_KEYS,
        path=f"{path}.settlement_amounts",
    )
    for key in _SETTLEMENT_AMOUNT_KEYS:
        _candidate_money(settlements[key], f"{path}.settlement_amounts.{key}")


def _validate_russian_source_income_value(value: dict[str, Any], path: str) -> None:
    _candidate_string(value["income_kind"], f"{path}.income_kind")
    source_party = _candidate_mapping(
        value["source_party"],
        required=_SOURCE_PARTY_VALUE_KEYS,
        path=f"{path}.source_party",
    )
    for key in _SOURCE_PARTY_VALUE_KEYS:
        _candidate_string(source_party[key], f"{path}.source_party.{key}")
    _candidate_money(value["gross_income"], f"{path}.gross_income")
    _candidate_money(value["withheld_tax"], f"{path}.withheld_tax")


def _validate_financial_investment_value(value: dict[str, Any], path: str) -> None:
    _candidate_string(value["operation_category"], f"{path}.operation_category")
    _candidate_string(value["loss_treatment"], f"{path}.loss_treatment")
    for key in (
        "category_gross_income",
        "related_expenses",
        "allowable_expenses",
    ):
        _candidate_money(value[key], f"{path}.{key}")


def _candidate_rows(
    value: Any,
    *,
    path: str,
    required: frozenset[str],
    validator,
) -> None:
    if not isinstance(value, list) or not value:
        _candidate_missing(path)
    for index, row in enumerate(value):
        row_path = f"{path}[{index}]"
        checked = _candidate_mapping(row, required=required, path=row_path)
        validator(checked, row_path)


def _candidate_mapping(
    value: Any,
    *,
    required: frozenset[str],
    path: str,
    optional: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    if not isinstance(value, dict):
        _candidate_invalid(path)
    missing = required - set(value)
    if missing:
        _candidate_missing(f"{path}.{sorted(missing)[0]}")
    if set(value) - required - optional:
        _candidate_invalid(path)
    return value


def _candidate_money(value: Any, path: str) -> None:
    money = _candidate_mapping(value, required=_MONEY_VALUE_KEYS, path=path)
    if money["kind"] != "money":
        _candidate_invalid(f"{path}.kind")
    _candidate_string(money["amount"], f"{path}.amount")
    _candidate_string(money["currency"], f"{path}.currency")


def _candidate_string(value: Any, path: str) -> None:
    if not _nonempty(value):
        _candidate_invalid(path)


def _assert_candidate_no_audit_leakage(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = key.lower()
            if lowered in _DECLARATION_VALUE_AUDIT_KEYS or lowered.endswith(
                ("_sha256", "_ref", "_refs", "_id", "_version")
            ):
                _fail("gate5_declaration_value_candidate_audit_leakage", key)
            _assert_candidate_no_audit_leakage(item)
    elif isinstance(value, list):
        for item in value:
            _assert_candidate_no_audit_leakage(item)


def _candidate_missing(path: str) -> None:
    _fail("gate5_declaration_value_candidate_required_value_missing", path)


def _candidate_invalid(path: str) -> None:
    _fail("gate5_declaration_value_candidate_invalid", path)


def _validated_semantic_input(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _INPUT_KEYS:
        _fail("gate5_declaration_semantic_input_invalid")
    if (
        value.get("schema_version") != GATE5_DECLARATION_SEMANTIC_INPUT_SCHEMA_VERSION
        or value.get("status") != GATE5_DECLARATION_SEMANTIC_INPUT_STATUS
        or not _sha256(value.get("semantic_input_sha256"))
    ):
        _fail("gate5_declaration_semantic_input_invalid")
    _validate_source_binding(value.get("source_binding"))
    declaration = _validate_declaration_semantics(value.get("declaration_semantics"))
    case_identity = _validate_case_identity(value.get("case_identity"))
    if declaration["tax_period"] != case_identity["tax_period"]:
        _fail("gate5_declaration_semantic_tax_period_mismatch")
    _validate_completeness(value.get("completeness"))
    _validate_domains(value.get("domains"))
    _assert_target_independent(value)
    base = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "semantic_input_sha256"
    }
    if value["semantic_input_sha256"] != _canonical_sha256(base):
        _fail("gate5_declaration_semantic_input_hash_mismatch")
    return copy.deepcopy(value)


def _validate_source_binding(value: Any) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != _SOURCE_BINDING_KEYS
        or not all(_sha256(value.get(key)) for key in _SOURCE_BINDING_KEYS)
    ):
        _fail("gate5_declaration_semantic_source_binding_invalid")


def _validate_declaration_semantics(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != _DECLARATION_SEMANTICS_KEYS
        or not all(_nonempty(value.get(key)) for key in _DECLARATION_SEMANTICS_KEYS)
    ):
        _fail("gate5_declaration_semantic_declaration_identity_invalid")
    return value


def _validate_case_identity(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != _CASE_IDENTITY_KEYS
        or not all(
            _nonempty(value.get(key))
            for key in _CASE_IDENTITY_KEYS
            if key != "scope_binding_sha256"
        )
        or not _sha256(value.get("scope_binding_sha256"))
    ):
        _fail("gate5_declaration_semantic_case_identity_invalid")
    return value


def _validate_completeness(value: Any) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != _COMPLETENESS_KEYS
        or value.get("completeness_kind") != "supplied_case_evidence_set"
        or value.get("real_world_taxpayer_completeness_asserted") is not False
    ):
        _fail("gate5_declaration_semantic_completeness_invalid")


def _validate_domains(value: Any) -> None:
    if not isinstance(value, list) or not value:
        _fail("gate5_declaration_semantic_domains_invalid")
    seen_domains = set()
    for position, domain in enumerate(value):
        if (
            not isinstance(domain, dict)
            or set(domain) != _DOMAIN_KEYS
            or not _nonempty(domain.get("domain_id"))
            or domain["domain_id"] in seen_domains
            or not _nonempty(domain.get("semantic_meaning"))
            or domain.get("state") not in _TERMINAL_STATES
            or not _nonempty_strings(domain.get("obligation_refs"))
            or not isinstance(domain.get("typed_components"), list)
        ):
            _fail("gate5_declaration_semantic_domain_invalid", str(position))
        seen_domains.add(domain["domain_id"])
        components = domain["typed_components"]
        if (domain["state"] == "RESOLVED") != bool(components):
            _fail(
                "gate5_declaration_semantic_domain_state_invalid", domain["domain_id"]
            )
        seen_contracts = set()
        for component in components:
            _validate_component(
                component,
                domain_id=domain["domain_id"],
            )
            contract_id = component["source_component_contract_id"]
            if contract_id in seen_contracts:
                _fail(
                    "gate5_declaration_semantic_component_ambiguous",
                    domain["domain_id"],
                )
            seen_contracts.add(contract_id)


def _validate_component(
    value: Any,
    *,
    domain_id: str,
) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != _COMPONENT_KEYS
        or not _nonempty(value.get("source_component_contract_id"))
        or not _sha256(value.get("source_component_sha256"))
        or not isinstance(value.get("semantic_payload"), dict)
        or not value["semantic_payload"]
        or not _sha256(value.get("semantic_payload_sha256"))
        or value["semantic_payload_sha256"]
        != _canonical_sha256(value["semantic_payload"])
    ):
        _fail("gate5_declaration_semantic_component_invalid", domain_id)


def _semantic_payload(*, domain_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    try:
        if domain_id == "filing_and_party_identity":
            source = snapshot["input_snapshot"]
            return {
                "filing_instance": copy.deepcopy(source["filing_instance"]),
                "taxpayer": copy.deepcopy(source["taxpayer"]),
                "signer": copy.deepcopy(source["signer"]),
            }
        if domain_id == "declaration_budget_disposition":
            disposition = snapshot["disposition"]
            return {
                key: copy.deepcopy(disposition[key])
                for key in (
                    "kind",
                    "calculated_tax",
                    "credited_or_withheld_amount",
                    "reduction_amount",
                    "payment_or_additional_payment_amount",
                    "refund_available_amount",
                    "simplified_procedure_returned_or_credited_amount",
                    "budget_allocations",
                )
            }
        if domain_id == "income_group_tax_results":
            return {
                "group_results": [
                    _income_group_semantic_result(row)
                    for row in snapshot["group_results"]
                ]
            }
        if domain_id == "taxable_income_by_source":
            return {
                "source_entries": [
                    {
                        key: copy.deepcopy(item[key])
                        for key in (
                            "source_ref",
                            "income_group_semantic",
                            "jurisdiction_kind",
                            "jurisdiction_code",
                            "income_kind",
                            "source_party",
                            "gross_income",
                            "taxable_income",
                            "tax_agent",
                            "foreign_tax",
                        )
                    }
                    for item in snapshot["source_entries"]
                ],
                "obligation_resolutions": copy.deepcopy(
                    snapshot["obligation_resolutions"]
                ),
            }
        if domain_id == "financial_investment_results":
            return {
                "category_results": [
                    _financial_category_semantic_result(item)
                    for item in snapshot["category_tax_models"]
                ],
                "obligation_resolutions": [
                    {
                        "obligation_ref": item["obligation_ref"],
                        "state": item["state"],
                        "real_world_absence_asserted": item[
                            "real_world_absence_asserted"
                        ],
                    }
                    for item in snapshot["obligation_resolutions"]
                ],
            }
    except (KeyError, TypeError) as exc:
        raise Gate5DeclarationSemanticInputError(
            "gate5_declaration_semantic_component_projection_invalid",
            domain_id,
        ) from exc
    _fail("gate5_declaration_semantic_component_projection_unavailable", domain_id)


def _semantic_component(
    *,
    domain_id: str,
    item: dict[str, Any],
) -> dict[str, Any]:
    payload = _semantic_payload(domain_id=domain_id, snapshot=item["snapshot"])
    return {
        "source_component_contract_id": item["component_contract_id"],
        "source_component_sha256": item["content_sha256"],
        "semantic_payload": payload,
        "semantic_payload_sha256": _canonical_sha256(payload),
    }


def _income_group_semantic_result(value: dict[str, Any]) -> dict[str, Any]:
    model = value["tax_base_model"]
    return {
        "income_group_semantic": value["income_group_semantic"],
        "income_group_code": value["income_group_code"],
        "total_income": copy.deepcopy(model["total_income"]["value"]),
        "non_taxable_income": copy.deepcopy(
            model["input_snapshot"]["group_values"]["non_taxable_income"]["value"]
        ),
        "taxable_income": copy.deepcopy(model["taxable_income"]["value"]),
        "tax_deductions": copy.deepcopy(
            model["input_snapshot"]["group_values"]["tax_deductions"]["value"]
        ),
        "accepted_expenses": copy.deepcopy(model["accepted_expenses"]["value"]),
        "tax_base": copy.deepcopy(model["tax_base"]["value"]),
        "tax_rate": value["derivation"]["rate_band"]["marginal_rate"],
        "calculated_tax": copy.deepcopy(value["calculated_tax"]),
        "settlement_facts": {
            key: copy.deepcopy(item["value"])
            for key, item in value["settlement_facts"].items()
        },
        "tax_payable": copy.deepcopy(value["tax_payable"]),
        "tax_refundable": copy.deepcopy(value["tax_refundable"]),
    }


def _financial_category_semantic_result(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "model_kind": value["model_kind"],
        "status": value["status"],
        "operation_category": value["operation_category"]["value"],
        "category_gross_income": copy.deepcopy(value["category_gross_income"]["value"]),
        "related_expenses": copy.deepcopy(value["related_expenses"]["value"]),
        "allowable_expenses": copy.deepcopy(value["allowable_expenses"]["value"]),
        "loss_treatment": value["loss_treatment"]["value"],
    }


def _assert_target_independent(value: Any) -> None:
    if isinstance(value, dict):
        if any(key.lower() in _TARGET_SPECIFIC_KEYS for key in value):
            _fail("gate5_declaration_semantic_target_leakage")
        for item in value.values():
            _assert_target_independent(item)
    elif isinstance(value, list):
        for item in value:
            _assert_target_independent(item)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _nonempty_strings(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and len(value) == len(set(value))
        and all(_nonempty(item) for item in value)
    )


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA256.fullmatch(value))


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _fail(code: str, field: str = "") -> None:
    raise Gate5DeclarationSemanticInputError(code, field)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_DECLARATION_SEMANTIC_BOUNDARY_VERDICT",
    "GATE5_DECLARATION_SEMANTIC_INPUT_SCHEMA_VERSION",
    "GATE5_DECLARATION_SEMANTIC_INPUT_STATUS",
    "GATE5_RELEASED_DECLARATION_PROJECTION_INPUT_SCHEMA_VERSION",
    "GATE5_RELEASED_DECLARATION_PROJECTION_INPUT_STATUS",
    "Gate5DeclarationSemanticInputError",
    "Gate5DeclarationSemanticInputRuntime",
    "Gate5DeclarationSemanticInputRuntimeFactory",
]
