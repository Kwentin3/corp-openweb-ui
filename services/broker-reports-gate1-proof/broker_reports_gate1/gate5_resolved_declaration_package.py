"""Definition-bound sealed Declaration package completeness proof."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any

from .artifact_models import ArtifactAccessContext, ArtifactStorePort, RetentionPolicy
from .gate5_declaration_scope_resolution import (
    GATE5_CURRENT_FACT_DECLARATION_SCOPE_RECEIPT_SCHEMA_VERSION,
    GATE5_DECLARATION_SCOPE_COMPONENT_EVIDENCE_SCHEMA_VERSION,
    GATE5_DECLARATION_SCOPE_RECEIPT_SCHEMA_VERSION,
    GATE5_DECLARATION_SCOPE_SEMANTICS,
    Gate5DeclarationScopeResolutionError,
    Gate5DeclarationScopeResolutionRuntime,
    Gate5DeclarationScopeResolutionRuntimeFactory,
)
from .gate5_full_declaration_definition import (
    GATE5_FULL_DECLARATION_DEFINITION_PUBLICATION_SCHEMA_VERSION,
    Gate5FullDeclarationDefinitionError,
    Gate5TrustedFullDeclarationDefinitionAuthority,
    Gate5TrustedFullDeclarationDefinitionAuthorityFactory,
)
from .gate5_declaration_filing_context import (
    GATE5_FILING_AND_PARTY_IDENTITY_COMPONENT_FAMILY,
    GATE5_FILING_AND_PARTY_IDENTITY_COMPONENT_OWNER,
    GATE5_FILING_AND_PARTY_IDENTITY_COMPONENT_SCHEMA_VERSION,
    GATE5_FILING_AND_PARTY_IDENTITY_DOMAIN_ID,
    GATE5_FILING_AND_PARTY_IDENTITY_OBLIGATION_REFS,
    Gate5FilingAndPartyIdentityRuntime,
    Gate5FilingAndPartyIdentityRuntimeFactory,
)
from .gate5_declaration_budget_outcome import (
    GATE5_DECLARATION_BUDGET_DISPOSITION_COMPONENT_FAMILY,
    GATE5_DECLARATION_BUDGET_DISPOSITION_COMPONENT_OWNER,
    GATE5_DECLARATION_BUDGET_DISPOSITION_COMPONENT_SCHEMA_VERSION,
    GATE5_DECLARATION_BUDGET_DISPOSITION_DOMAIN_ID,
    GATE5_DECLARATION_BUDGET_DISPOSITION_OBLIGATION_REFS,
    Gate5DeclarationBudgetOutcomeRuntime,
    Gate5DeclarationBudgetOutcomeRuntimeFactory,
)
from .gate5_declaration_tax_settlement import (
    GATE5_INCOME_GROUP_TAX_RESULTS_COMPONENT_FAMILY,
    GATE5_INCOME_GROUP_TAX_RESULTS_COMPONENT_OWNER,
    GATE5_INCOME_GROUP_TAX_RESULTS_COMPONENT_SCHEMA_VERSION,
    GATE5_INCOME_GROUP_TAX_RESULTS_DOMAIN_ID,
    GATE5_INCOME_GROUP_TAX_RESULTS_OBLIGATION_REFS,
    Gate5DeclarationTaxSettlementRuntime,
    Gate5DeclarationTaxSettlementRuntimeFactory,
)
from .gate5_declaration_income_sources import (
    GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_FAMILY,
    GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_OWNER,
    GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_SCHEMA_VERSION,
    GATE5_TAXABLE_INCOME_SOURCE_DOMAIN_ID,
    GATE5_TAXABLE_INCOME_SOURCE_OBLIGATION_REFS,
    Gate5DeclarationIncomeSourcesRuntime,
    Gate5DeclarationIncomeSourcesRuntimeFactory,
)
from .gate5_declaration_financial_investment_results import (
    GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_FAMILY,
    GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_OWNER,
    GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_SCHEMA_VERSION,
    GATE5_FINANCIAL_INVESTMENT_RESULTS_DOMAIN_ID,
    GATE5_FINANCIAL_INVESTMENT_RESULTS_OBLIGATION_REFS,
    Gate5DeclarationFinancialInvestmentResultsRuntime,
    Gate5DeclarationFinancialInvestmentResultsRuntimeFactory,
)
from .gate5_securities_disposal_tax_model import (
    GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION,
)
from .gate5_tax_period_category_aggregation import (
    Gate5TaxPeriodCategoryAggregationRuntime,
    Gate5TaxPeriodCategoryAggregationRuntimeFactory,
)
from .ordinary_trade_tax_model_bridge import (
    validate_ordinary_trade_taxpayer_binding,
)


GATE5_RESOLVED_DECLARATION_PACKAGE_SCHEMA_VERSION = (
    "broker_reports_gate5_resolved_declaration_package_v1"
)
GATE5_DECLARATION_PACKAGE_COMPONENT_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_package_component_v0"
)
GATE5_DECLARATION_REQUIREMENT_RESOLUTION_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_requirement_resolution_v1"
)
GATE5_DEFINITION_BOUND_COMPLETENESS_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate5_definition_bound_completeness_receipt_v1"
)

FACTORY_REQUIRED = (
    "Gate5ResolvedDeclarationPackageRuntimeFactory.create owns package assembly",
    "Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create owns requirements",
    "Gate5DeclarationScopeResolutionRuntimeFactory.create owns applicability receipt validation",
    "Gate5TaxPeriodCategoryAggregationRuntimeFactory.create validates the bounded typed snapshot",
    "Gate5FilingAndPartyIdentityRuntimeFactory.create validates the exact self-bound filing snapshot",
    "Gate5DeclarationTaxSettlementRuntimeFactory.create validates the exact self-bound income-group snapshot",
    "Gate5DeclarationBudgetOutcomeRuntimeFactory.create validates the exact self-bound budget snapshot",
    "Gate5DeclarationIncomeSourcesRuntimeFactory.create validates the exact self-bound taxable-source snapshot",
    "Gate5DeclarationFinancialInvestmentResultsRuntimeFactory.create validates the exact supplied-case financial snapshot",
    "Gate5ResolvedDeclarationPackageRuntimeFactory.create_current_source_fact_package "
    "injects the existing current Fact v2 scope owner",
)
FORBIDDEN = (
    "copied Declaration domain or expected-component lists",
    "Gate 4, SQL, CanonicalArtifact, Gate 3 or ArtifactStore business-value reads",
    "bounded component promotion to exact root-domain completeness",
    "tax calculation, applicability reasoning, user interaction or blocker implementation",
    "Declaration DB, component registry service, dependency graph or sixth primitive",
    "Declaration Model flattening, PROJECT, XML/PDF or product activation",
)

_PUBLICATION_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "definition_id",
        "definition_version",
        "definition_sha256",
        "validation_sha256",
        "obligation_package_sha256",
    }
)
_PACKAGE_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "definition_binding",
        "definition_snapshot",
        "scope_receipt_snapshot",
        "component_snapshots",
        "requirement_resolutions",
        "completeness_receipt",
        "package_sha256",
    }
)
_COMPONENT_INPUT_KEYS = frozenset(
    {"schema_version", "component_contract_id", "component_sha256", "payload"}
)
_SEALED_COMPONENT_KEYS = frozenset(
    {
        "schema_version",
        "component_ref",
        "domain_id",
        "component_contract_id",
        "component_owner",
        "component_family",
        "root_coverage",
        "covered_obligation_refs",
        "definition_component_availability",
        "scope_decision_sha256",
        "content_sha256",
        "snapshot",
        "component_binding_sha256",
    }
)
_REQUIREMENT_RESOLUTION_KEYS = frozenset(
    {
        "schema_version",
        "domain_id",
        "scope_state",
        "scope_decision_sha256",
        "required_component",
        "state",
        "component_refs",
        "diagnostics",
        "resolution_sha256",
    }
)
_COMPLETENESS_RECEIPT_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "definition_sha256",
        "scope_receipt_sha256",
        "scope_binding_sha256",
        "component_set_sha256",
        "resolution_manifest_sha256",
        "blockers",
        "first_blocker",
        "completeness_kind",
        "real_world_taxpayer_completeness_asserted",
        "receipt_sha256",
    }
)
_SCOPE_STATES = {
    "APPLICABLE",
    "NOT_APPLICABLE",
    "NOT_ACTIVATED_FOR_SUPPLIED_CASE",
    "UNRESOLVED",
    "CONFLICT",
}
_PACKAGE_STATES = {
    "RESOLVED",
    "NOT_APPLICABLE",
    "NOT_ACTIVATED_FOR_SUPPLIED_CASE",
    "SCOPE_UNRESOLVED",
    "SCOPE_CONFLICT",
    "REQUIRED_MISSING",
}
_TERMINAL_PACKAGE_STATES = {
    "RESOLVED",
    "NOT_APPLICABLE",
    "NOT_ACTIVATED_FOR_SUPPLIED_CASE",
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_OPERATION_COMPONENT_OWNER = (
    "Gate5TaxPeriodCategoryAggregationRuntimeFactory.create.validate_operation_member"
)


class Gate5ResolvedDeclarationPackageError(ValueError):
    def __init__(self, code: str, field: str = "") -> None:
        self.code = code
        self.field = field
        super().__init__(code if not field else f"{code}:{field}")


class Gate5ResolvedDeclarationPackageRuntimeFactory:
    def __init__(
        self,
        *,
        store: ArtifactStorePort | None,
        read_enabled: bool,
        retention_policy: RetentionPolicy,
    ) -> None:
        self._store = store
        self._read_enabled = read_enabled
        self._retention_policy = retention_policy

    def create(self) -> "Gate5ResolvedDeclarationPackageRuntime":
        if not isinstance(self._retention_policy, RetentionPolicy):
            _fail("gate5_resolved_package_retention_policy_required")
        validation_only = self._store is None
        scope_runtime = (
            None
            if validation_only
            else Gate5DeclarationScopeResolutionRuntimeFactory(
                store=self._store,
                read_enabled=self._read_enabled,
                retention_policy=self._retention_policy,
            ).create()
        )
        return self._create_with_scope(
            scope_runtime=scope_runtime,
            validation_only=validation_only,
        )

    def _create_with_scope(
        self,
        *,
        scope_runtime: Gate5DeclarationScopeResolutionRuntime | None,
        validation_only: bool,
    ) -> "Gate5ResolvedDeclarationPackageRuntime":
        return Gate5ResolvedDeclarationPackageRuntime(
            definition_authority=(
                None
                if validation_only
                else Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create()
            ),
            scope_runtime=scope_runtime,
            component_runtime=(
                None
                if validation_only
                else Gate5TaxPeriodCategoryAggregationRuntimeFactory.create()
            ),
            filing_runtime=(
                None
                if validation_only
                else Gate5FilingAndPartyIdentityRuntimeFactory.create()
            ),
            settlement_runtime=(
                None
                if validation_only
                else Gate5DeclarationTaxSettlementRuntimeFactory.create()
            ),
            budget_runtime=(
                None
                if validation_only
                else Gate5DeclarationBudgetOutcomeRuntimeFactory.create()
            ),
            income_sources_runtime=(
                None
                if validation_only
                else Gate5DeclarationIncomeSourcesRuntimeFactory.create()
            ),
            financial_investment_runtime=(
                None
                if validation_only
                else Gate5DeclarationFinancialInvestmentResultsRuntimeFactory.create()
            ),
        )

    def create_current_source_fact_package(
        self,
    ) -> "Gate5ResolvedDeclarationPackageRuntime":
        """Assemble through the active Fact-v2 scope reader without SQL fallback."""

        if self._store is None:
            _fail("gate5_resolved_package_assembly_store_required")
        if not isinstance(self._retention_policy, RetentionPolicy):
            _fail("gate5_resolved_package_retention_policy_required")
        return self._create_with_scope(
            scope_runtime=Gate5DeclarationScopeResolutionRuntimeFactory(
                store=self._store,
                read_enabled=self._read_enabled,
                retention_policy=self._retention_policy,
            ).create_current_source_fact_scope(),
            validation_only=False,
        )

    @classmethod
    def create_validation_only(cls) -> "Gate5ResolvedDeclarationPackageRuntime":
        """Create the sealed-byte validator without a store or upstream reads."""
        return cls(
            store=None,
            read_enabled=False,
            retention_policy=RetentionPolicy(
                mode="validation_only",
                ttl_seconds=None,
                expires_at=None,
                explicit=True,
            ),
        ).create()


class Gate5ResolvedDeclarationPackageRuntime:
    def __init__(
        self,
        *,
        definition_authority: Gate5TrustedFullDeclarationDefinitionAuthority | None,
        scope_runtime: Gate5DeclarationScopeResolutionRuntime | None,
        component_runtime: Gate5TaxPeriodCategoryAggregationRuntime | None,
        filing_runtime: Gate5FilingAndPartyIdentityRuntime | None,
        settlement_runtime: Gate5DeclarationTaxSettlementRuntime | None,
        budget_runtime: Gate5DeclarationBudgetOutcomeRuntime | None,
        income_sources_runtime: Gate5DeclarationIncomeSourcesRuntime | None,
        financial_investment_runtime: (
            Gate5DeclarationFinancialInvestmentResultsRuntime | None
        ),
    ) -> None:
        self._definition_authority = definition_authority
        self._scope_runtime = scope_runtime
        self._component_runtime = component_runtime
        self._filing_runtime = filing_runtime
        self._settlement_runtime = settlement_runtime
        self._budget_runtime = budget_runtime
        self._income_sources_runtime = income_sources_runtime
        self._financial_investment_runtime = financial_investment_runtime

    def assemble(
        self,
        *,
        definition_ref: dict[str, Any],
        scope_receipt: dict[str, Any],
        typed_component_snapshots: list[dict[str, Any]],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        if (
            self._definition_authority is None
            or self._scope_runtime is None
            or self._component_runtime is None
            or self._filing_runtime is None
            or self._settlement_runtime is None
            or self._budget_runtime is None
            or self._income_sources_runtime is None
            or self._financial_investment_runtime is None
        ):
            _fail("gate5_resolved_package_assembly_store_required")
        publication, definition = self._trusted_definition(definition_ref)
        try:
            validated_scope_receipt = self._scope_runtime.validate_receipt(
                receipt=scope_receipt,
                context=context,
            )
        except Gate5DeclarationScopeResolutionError as exc:
            raise Gate5ResolvedDeclarationPackageError(
                "gate5_resolved_package_scope_receipt_invalid",
                exc.code,
            ) from exc
        if validated_scope_receipt["definition_binding"] != publication:
            _fail("gate5_resolved_package_definition_scope_mismatch")
        components = self._seal_components(
            typed_component_snapshots,
            definition=definition,
            scope_receipt=validated_scope_receipt,
        )
        resolutions = _requirement_resolutions(
            definition=definition,
            scope_receipt=validated_scope_receipt,
            components=components,
        )
        completeness = _completeness_receipt(
            publication=publication,
            scope_receipt=validated_scope_receipt,
            components=components,
            resolutions=resolutions,
        )
        base = {
            "schema_version": GATE5_RESOLVED_DECLARATION_PACKAGE_SCHEMA_VERSION,
            "status": completeness["status"],
            "definition_binding": publication,
            "definition_snapshot": definition,
            "scope_receipt_snapshot": validated_scope_receipt,
            "component_snapshots": components,
            "requirement_resolutions": resolutions,
            "completeness_receipt": completeness,
        }
        package = {**base, "package_sha256": _canonical_sha256(base)}
        return self.validate_package(package=package)

    def validate_package(self, *, package: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(package, dict) or set(package) != _PACKAGE_KEYS:
            _fail("gate5_resolved_package_invalid")
        if (
            package.get("schema_version")
            != GATE5_RESOLVED_DECLARATION_PACKAGE_SCHEMA_VERSION
        ):
            _fail("gate5_resolved_package_schema_invalid")
        if self._definition_authority is None:
            publication = _publication(package.get("definition_binding"))
            trusted_definition = _sealed_definition(
                package.get("definition_snapshot"),
                publication=publication,
            )
        else:
            publication, trusted_definition = self._trusted_definition(
                package.get("definition_binding")
            )
            if package.get("definition_snapshot") != trusted_definition:
                _fail("gate5_resolved_package_definition_snapshot_invalid")
        scope_receipt = _sealed_scope_receipt(
            package.get("scope_receipt_snapshot"),
            publication=publication,
            definition=trusted_definition,
        )
        components = self._validate_sealed_components(
            package.get("component_snapshots"),
            definition=trusted_definition,
            scope_receipt=scope_receipt,
        )
        expected_resolutions = _requirement_resolutions(
            definition=trusted_definition,
            scope_receipt=scope_receipt,
            components=components,
        )
        if package.get("requirement_resolutions") != expected_resolutions:
            _fail("gate5_resolved_package_resolution_manifest_invalid")
        expected_completeness = _completeness_receipt(
            publication=publication,
            scope_receipt=scope_receipt,
            components=components,
            resolutions=expected_resolutions,
        )
        if package.get("completeness_receipt") != expected_completeness:
            _fail("gate5_resolved_package_completeness_receipt_invalid")
        if package.get("status") != expected_completeness["status"]:
            _fail("gate5_resolved_package_status_invalid")
        base = {
            key: copy.deepcopy(package[key])
            for key in package
            if key != "package_sha256"
        }
        if package.get("package_sha256") != _canonical_sha256(base):
            _fail("gate5_resolved_package_hash_mismatch")
        return copy.deepcopy(package)

    def _trusted_definition(self, value: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        publication = _publication(value)
        if self._definition_authority is None:
            _fail("gate5_resolved_package_definition_authority_required")
        try:
            definition = self._definition_authority.resolve(
                publication["definition_id"],
                publication["definition_version"],
                publication["definition_sha256"],
            )
        except Gate5FullDeclarationDefinitionError as exc:
            raise Gate5ResolvedDeclarationPackageError(
                "gate5_resolved_package_definition_binding_invalid",
                exc.code,
            ) from exc
        publication = self._definition_authority.publication()
        if value != publication:
            _fail("gate5_resolved_package_definition_binding_invalid")
        return copy.deepcopy(publication), definition

    def _seal_components(
        self,
        value: Any,
        *,
        definition: dict[str, Any],
        scope_receipt: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            _fail("gate5_resolved_package_components_invalid")
        domains = {item["domain_id"]: item for item in definition["domains"]}
        order = {
            item["domain_id"]: position
            for position, item in enumerate(definition["domains"])
        }
        scope_rows = {item["domain_id"]: item for item in scope_receipt["domains"]}
        evidence = _scope_component_evidence(scope_receipt)
        supplied_evidence: set[tuple[str, str]] = set()
        unique_contracts: set[tuple[str, str]] = set()
        result = []
        for position, item in enumerate(value):
            if (
                not isinstance(item, dict)
                or set(item) != _COMPONENT_INPUT_KEYS
                or item.get("schema_version")
                != GATE5_DECLARATION_SCOPE_COMPONENT_EVIDENCE_SCHEMA_VERSION
                or not isinstance(item.get("component_contract_id"), str)
                or not _sha256(item.get("component_sha256"))
                or not isinstance(item.get("payload"), dict)
                or item["component_sha256"] != _canonical_sha256(item["payload"])
            ):
                _fail("gate5_resolved_package_component_invalid", str(position))
            evidence_key = (
                item["component_contract_id"],
                item["component_sha256"],
            )
            binding = evidence.get(evidence_key)
            if binding is None and item["component_contract_id"] not in {
                GATE5_FILING_AND_PARTY_IDENTITY_COMPONENT_SCHEMA_VERSION,
                GATE5_INCOME_GROUP_TAX_RESULTS_COMPONENT_SCHEMA_VERSION,
                GATE5_DECLARATION_BUDGET_DISPOSITION_COMPONENT_SCHEMA_VERSION,
                GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_SCHEMA_VERSION,
                GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_SCHEMA_VERSION,
            }:
                _fail("gate5_resolved_package_component_scope_binding_missing")
            validated = self._validated_component_payload(
                contract_id=item["component_contract_id"],
                payload=item["payload"],
                scope_binding=scope_receipt["scope_binding"],
                taxpayer_binding=scope_receipt.get("taxpayer_binding"),
            )
            if binding is None:
                if validated["root_coverage"] != "exact_root_domain":
                    _fail("gate5_resolved_package_component_scope_binding_missing")
                domain_id = validated["domain_id"]
                scope_row = scope_rows.get(domain_id)
                if scope_row is None or scope_row["state"] != "APPLICABLE":
                    _fail("gate5_resolved_package_component_scope_binding_missing")
                binding = {
                    "domain_id": domain_id,
                    "scope_decision_sha256": scope_row["decision_sha256"],
                }
            else:
                supplied_evidence.add(evidence_key)
            domain = domains.get(binding["domain_id"])
            component_family = (
                validated["component_family"]
                if validated["component_family"] is not None
                else domain["expected_component"]["family"]
                if domain is not None
                else None
            )
            if (
                domain is None
                or validated["domain_id"] not in {None, binding["domain_id"]}
                or component_family != domain["expected_component"]["family"]
                or not set(validated["covered_obligation_refs"]).issubset(
                    domain["obligation_refs"]
                )
                or (
                    validated["root_coverage"] == "bounded_partial_only"
                    and item["component_contract_id"]
                    not in domain["expected_component"]["contract_ids"]
                )
            ):
                _fail("gate5_resolved_package_component_orphan")
            contract_key = (binding["domain_id"], item["component_contract_id"])
            if contract_key in unique_contracts:
                _fail("gate5_resolved_package_component_ambiguous")
            unique_contracts.add(contract_key)
            component_ref = f"component:{item['component_sha256']}"
            base = {
                "schema_version": GATE5_DECLARATION_PACKAGE_COMPONENT_SCHEMA_VERSION,
                "component_ref": component_ref,
                "domain_id": binding["domain_id"],
                "component_contract_id": item["component_contract_id"],
                "component_owner": validated["component_owner"],
                "component_family": component_family,
                "root_coverage": validated["root_coverage"],
                "covered_obligation_refs": validated["covered_obligation_refs"],
                "definition_component_availability": domain["expected_component"][
                    "availability"
                ],
                "scope_decision_sha256": binding["scope_decision_sha256"],
                "content_sha256": item["component_sha256"],
                "snapshot": validated["snapshot"],
            }
            result.append({**base, "component_binding_sha256": _canonical_sha256(base)})
        if supplied_evidence != set(evidence):
            _fail("gate5_resolved_package_scope_component_snapshot_missing")
        return sorted(
            result,
            key=lambda item: (
                order[item["domain_id"]],
                item["component_contract_id"],
                item["content_sha256"],
            ),
        )

    def _validate_sealed_components(
        self,
        value: Any,
        *,
        definition: dict[str, Any],
        scope_receipt: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            _fail("gate5_resolved_package_components_invalid")
        domains = {item["domain_id"]: item for item in definition["domains"]}
        order = {
            item["domain_id"]: position
            for position, item in enumerate(definition["domains"])
        }
        scope_rows = {item["domain_id"]: item for item in scope_receipt["domains"]}
        evidence = _scope_component_evidence(scope_receipt)
        supplied_evidence: set[tuple[str, str]] = set()
        unique_contracts: set[tuple[str, str]] = set()
        for position, item in enumerate(value):
            if (
                not isinstance(item, dict)
                or set(item) != _SEALED_COMPONENT_KEYS
                or item.get("schema_version")
                != GATE5_DECLARATION_PACKAGE_COMPONENT_SCHEMA_VERSION
                or not _sha256(item.get("content_sha256"))
                or not _sha256(item.get("component_binding_sha256"))
                or not isinstance(item.get("snapshot"), dict)
            ):
                _fail("gate5_resolved_package_component_invalid", str(position))
            if item["content_sha256"] != _canonical_sha256(item["snapshot"]):
                _fail("gate5_resolved_package_component_invalid", str(position))
            evidence_key = (
                item.get("component_contract_id"),
                item["content_sha256"],
            )
            binding = evidence.get(evidence_key)
            domain = domains.get(item.get("domain_id"))
            contract_id = item.get("component_contract_id")
            if (
                contract_id
                == GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION
            ):
                expected_owner = _OPERATION_COMPONENT_OWNER
                expected_domain_id = (
                    binding.get("domain_id") if isinstance(binding, dict) else None
                )
                expected_family = (
                    domain["expected_component"]["family"]
                    if isinstance(domain, dict)
                    else None
                )
                expected_coverage = "bounded_partial_only"
                expected_obligations: list[str] = []
                definition_authorized = (
                    isinstance(domain, dict)
                    and contract_id in domain["expected_component"]["contract_ids"]
                )
            elif (
                contract_id == GATE5_FILING_AND_PARTY_IDENTITY_COMPONENT_SCHEMA_VERSION
            ):
                expected_owner = GATE5_FILING_AND_PARTY_IDENTITY_COMPONENT_OWNER
                expected_domain_id = GATE5_FILING_AND_PARTY_IDENTITY_DOMAIN_ID
                expected_family = GATE5_FILING_AND_PARTY_IDENTITY_COMPONENT_FAMILY
                expected_coverage = "exact_root_domain"
                expected_obligations = list(
                    GATE5_FILING_AND_PARTY_IDENTITY_OBLIGATION_REFS
                )
                definition_authorized = (
                    isinstance(domain, dict)
                    and domain["obligation_refs"] == expected_obligations
                    and domain["expected_component"]["family"] == expected_family
                )
            elif contract_id == GATE5_INCOME_GROUP_TAX_RESULTS_COMPONENT_SCHEMA_VERSION:
                expected_owner = GATE5_INCOME_GROUP_TAX_RESULTS_COMPONENT_OWNER
                expected_domain_id = GATE5_INCOME_GROUP_TAX_RESULTS_DOMAIN_ID
                expected_family = GATE5_INCOME_GROUP_TAX_RESULTS_COMPONENT_FAMILY
                expected_coverage = "exact_root_domain"
                expected_obligations = list(
                    GATE5_INCOME_GROUP_TAX_RESULTS_OBLIGATION_REFS
                )
                definition_authorized = (
                    isinstance(domain, dict)
                    and domain["obligation_refs"] == expected_obligations
                    and domain["expected_component"]["family"] == expected_family
                )
            elif (
                contract_id
                == GATE5_DECLARATION_BUDGET_DISPOSITION_COMPONENT_SCHEMA_VERSION
            ):
                expected_owner = GATE5_DECLARATION_BUDGET_DISPOSITION_COMPONENT_OWNER
                expected_domain_id = GATE5_DECLARATION_BUDGET_DISPOSITION_DOMAIN_ID
                expected_family = GATE5_DECLARATION_BUDGET_DISPOSITION_COMPONENT_FAMILY
                expected_coverage = "exact_root_domain"
                expected_obligations = list(
                    GATE5_DECLARATION_BUDGET_DISPOSITION_OBLIGATION_REFS
                )
                definition_authorized = (
                    isinstance(domain, dict)
                    and domain["obligation_refs"] == expected_obligations
                    and domain["expected_component"]["family"] == expected_family
                )
            elif contract_id == GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_SCHEMA_VERSION:
                expected_owner = GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_OWNER
                expected_domain_id = GATE5_TAXABLE_INCOME_SOURCE_DOMAIN_ID
                expected_family = GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_FAMILY
                expected_coverage = "exact_root_domain"
                expected_obligations = list(GATE5_TAXABLE_INCOME_SOURCE_OBLIGATION_REFS)
                definition_authorized = (
                    isinstance(domain, dict)
                    and domain["obligation_refs"] == expected_obligations
                    and domain["expected_component"]["family"] == expected_family
                )
            elif (
                contract_id
                == GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_SCHEMA_VERSION
            ):
                expected_owner = GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_OWNER
                expected_domain_id = GATE5_FINANCIAL_INVESTMENT_RESULTS_DOMAIN_ID
                expected_family = GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_FAMILY
                expected_coverage = "exact_root_domain"
                expected_obligations = list(
                    GATE5_FINANCIAL_INVESTMENT_RESULTS_OBLIGATION_REFS
                )
                definition_authorized = (
                    isinstance(domain, dict)
                    and domain["obligation_refs"] == expected_obligations
                    and domain["expected_component"]["family"] == expected_family
                )
            else:
                _fail("gate5_resolved_package_component_binding_invalid")
            if (
                domain is None
                or expected_domain_id != item["domain_id"]
                or not definition_authorized
                or item.get("component_ref") != f"component:{item['content_sha256']}"
                or item.get("definition_component_availability")
                != domain["expected_component"]["availability"]
                or item.get("component_owner") != expected_owner
                or item.get("component_family") != expected_family
                or item.get("root_coverage") != expected_coverage
                or item.get("covered_obligation_refs") != expected_obligations
                or item.get("scope_decision_sha256")
                != scope_rows[item["domain_id"]]["decision_sha256"]
                or scope_rows[item["domain_id"]]["state"] != "APPLICABLE"
            ):
                _fail("gate5_resolved_package_component_binding_invalid")
            contract_key = (item["domain_id"], item["component_contract_id"])
            if evidence_key in supplied_evidence or contract_key in unique_contracts:
                _fail("gate5_resolved_package_component_ambiguous")
            if binding is not None:
                supplied_evidence.add(evidence_key)
            unique_contracts.add(contract_key)
            base = {
                key: copy.deepcopy(item[key])
                for key in item
                if key != "component_binding_sha256"
            }
            if item["component_binding_sha256"] != _canonical_sha256(base):
                _fail("gate5_resolved_package_component_binding_invalid")
        if supplied_evidence != set(evidence):
            _fail("gate5_resolved_package_scope_component_snapshot_missing")
        expected_order = sorted(
            value,
            key=lambda item: (
                order[item["domain_id"]],
                item["component_contract_id"],
                item["content_sha256"],
            ),
        )
        if value != expected_order:
            _fail("gate5_resolved_package_component_order_invalid")
        return copy.deepcopy(value)

    def _validated_component_payload(
        self,
        *,
        contract_id: str,
        payload: dict[str, Any],
        scope_binding: dict[str, Any],
        taxpayer_binding: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if (
            self._component_runtime is None
            or self._filing_runtime is None
            or self._settlement_runtime is None
            or self._budget_runtime is None
            or self._income_sources_runtime is None
            or self._financial_investment_runtime is None
        ):
            _fail("gate5_resolved_package_component_authority_required")
        try:
            if (
                contract_id
                == GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION
            ):
                validated = self._component_runtime.validate_operation_member(
                    tax_model=payload
                )
                operation_scope = validated["operation_scope"]
                current_identity = operation_scope.get("subject_ref") == (
                    taxpayer_binding or {}
                ).get("operation_subject_ref") and scope_binding[
                    "taxpayer_scope_ref"
                ] == (taxpayer_binding or {}).get("taxpayer_scope_ref")
                historical_identity = (
                    taxpayer_binding is None
                    and operation_scope.get("subject_ref")
                    == scope_binding["taxpayer_scope_ref"]
                )
                if (
                    not (current_identity or historical_identity)
                    or operation_scope.get("tax_period", {}).get("value")
                    != scope_binding["tax_period"]
                ):
                    _fail("gate5_resolved_package_component_scope_mismatch")
                return {
                    "snapshot": validated,
                    "component_owner": _OPERATION_COMPONENT_OWNER,
                    "domain_id": None,
                    "component_family": None,
                    "root_coverage": "bounded_partial_only",
                    "covered_obligation_refs": [],
                }
            if contract_id == GATE5_FILING_AND_PARTY_IDENTITY_COMPONENT_SCHEMA_VERSION:
                validated = self._filing_runtime.validate_component(
                    component=payload,
                    scope_binding=scope_binding,
                )
                return {
                    "snapshot": validated,
                    "component_owner": GATE5_FILING_AND_PARTY_IDENTITY_COMPONENT_OWNER,
                    "domain_id": GATE5_FILING_AND_PARTY_IDENTITY_DOMAIN_ID,
                    "component_family": GATE5_FILING_AND_PARTY_IDENTITY_COMPONENT_FAMILY,
                    "root_coverage": "exact_root_domain",
                    "covered_obligation_refs": list(
                        GATE5_FILING_AND_PARTY_IDENTITY_OBLIGATION_REFS
                    ),
                }
            if contract_id == GATE5_INCOME_GROUP_TAX_RESULTS_COMPONENT_SCHEMA_VERSION:
                validated = self._settlement_runtime.validate_component(
                    component=payload,
                    scope_binding=scope_binding,
                )
                return {
                    "snapshot": validated,
                    "component_owner": GATE5_INCOME_GROUP_TAX_RESULTS_COMPONENT_OWNER,
                    "domain_id": GATE5_INCOME_GROUP_TAX_RESULTS_DOMAIN_ID,
                    "component_family": GATE5_INCOME_GROUP_TAX_RESULTS_COMPONENT_FAMILY,
                    "root_coverage": "exact_root_domain",
                    "covered_obligation_refs": list(
                        GATE5_INCOME_GROUP_TAX_RESULTS_OBLIGATION_REFS
                    ),
                }
            if (
                contract_id
                == GATE5_DECLARATION_BUDGET_DISPOSITION_COMPONENT_SCHEMA_VERSION
            ):
                validated = self._budget_runtime.validate_component(
                    component=payload,
                    scope_binding=scope_binding,
                )
                return {
                    "snapshot": validated,
                    "component_owner": GATE5_DECLARATION_BUDGET_DISPOSITION_COMPONENT_OWNER,
                    "domain_id": GATE5_DECLARATION_BUDGET_DISPOSITION_DOMAIN_ID,
                    "component_family": GATE5_DECLARATION_BUDGET_DISPOSITION_COMPONENT_FAMILY,
                    "root_coverage": "exact_root_domain",
                    "covered_obligation_refs": list(
                        GATE5_DECLARATION_BUDGET_DISPOSITION_OBLIGATION_REFS
                    ),
                }
            if contract_id == GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_SCHEMA_VERSION:
                validated = self._income_sources_runtime.validate_component(
                    component=payload,
                    scope_binding=scope_binding,
                )
                return {
                    "snapshot": validated,
                    "component_owner": GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_OWNER,
                    "domain_id": GATE5_TAXABLE_INCOME_SOURCE_DOMAIN_ID,
                    "component_family": GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_FAMILY,
                    "root_coverage": "exact_root_domain",
                    "covered_obligation_refs": list(
                        GATE5_TAXABLE_INCOME_SOURCE_OBLIGATION_REFS
                    ),
                }
            if (
                contract_id
                == GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_SCHEMA_VERSION
            ):
                validated = self._financial_investment_runtime.validate_component(
                    component=payload,
                    scope_binding=scope_binding,
                )
                return {
                    "snapshot": validated,
                    "component_owner": (
                        GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_OWNER
                    ),
                    "domain_id": GATE5_FINANCIAL_INVESTMENT_RESULTS_DOMAIN_ID,
                    "component_family": (
                        GATE5_FINANCIAL_INVESTMENT_RESULTS_COMPONENT_FAMILY
                    ),
                    "root_coverage": "exact_root_domain",
                    "covered_obligation_refs": list(
                        GATE5_FINANCIAL_INVESTMENT_RESULTS_OBLIGATION_REFS
                    ),
                }
        except Gate5ResolvedDeclarationPackageError:
            raise
        except ValueError as exc:
            raise Gate5ResolvedDeclarationPackageError(
                "gate5_resolved_package_component_validation_failed",
                contract_id,
            ) from exc
        _fail("gate5_resolved_package_component_validator_unavailable", contract_id)


def _publication(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != _PUBLICATION_KEYS
        or value.get("schema_version")
        != GATE5_FULL_DECLARATION_DEFINITION_PUBLICATION_SCHEMA_VERSION
        or value.get("status") != "trusted_repository_published"
        or not all(
            isinstance(value.get(key), str) and value[key]
            for key in ("definition_id", "definition_version")
        )
        or not all(
            _sha256(value.get(key))
            for key in (
                "definition_sha256",
                "validation_sha256",
                "obligation_package_sha256",
            )
        )
    ):
        _fail("gate5_resolved_package_definition_binding_invalid")
    return copy.deepcopy(value)


def _sealed_definition(
    value: Any,
    *,
    publication: dict[str, Any],
) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "schema_version",
            "definition_id",
            "definition_version",
            "declaration_identity",
            "obligation_package_binding",
            "domains",
        }
        or value.get("definition_id") != publication["definition_id"]
        or value.get("definition_version") != publication["definition_version"]
        or _canonical_sha256(value) != publication["definition_sha256"]
        or not isinstance(value.get("declaration_identity"), dict)
        or not isinstance(value.get("domains"), list)
        or not value["domains"]
    ):
        _fail("gate5_resolved_package_definition_snapshot_invalid")
    seen = set()
    for domain in value["domains"]:
        component = (
            domain.get("expected_component") if isinstance(domain, dict) else None
        )
        if (
            not isinstance(domain, dict)
            or set(domain)
            != {
                "domain_id",
                "semantic_meaning",
                "obligation_refs",
                "expected_component",
            }
            or not isinstance(domain.get("domain_id"), str)
            or domain["domain_id"] in seen
            or not isinstance(component, dict)
            or set(component) != {"family", "availability", "contract_ids"}
            or component.get("availability")
            not in {"missing", "published_bounded", "published_exact"}
            or not isinstance(component.get("contract_ids"), list)
            or len(component["contract_ids"]) != len(set(component["contract_ids"]))
        ):
            _fail("gate5_resolved_package_definition_snapshot_invalid")
        seen.add(domain["domain_id"])
    return copy.deepcopy(value)


def _sealed_scope_receipt(
    value: Any,
    *,
    publication: dict[str, Any],
    definition: dict[str, Any],
) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or value.get("schema_version")
        not in {
            GATE5_DECLARATION_SCOPE_RECEIPT_SCHEMA_VERSION,
            GATE5_CURRENT_FACT_DECLARATION_SCOPE_RECEIPT_SCHEMA_VERSION,
        }
        or value.get("definition_binding") != publication
        or value.get("scope_semantics") != GATE5_DECLARATION_SCOPE_SEMANTICS
        or not _sha256(value.get("receipt_sha256"))
        or not isinstance(value.get("scope_binding"), dict)
        or not _sha256(value["scope_binding"].get("scope_binding_sha256"))
        or value["scope_binding"].get("tax_period")
        != definition["declaration_identity"]["tax_period"]
    ):
        _fail("gate5_resolved_package_scope_receipt_invalid")
    base = {key: copy.deepcopy(value[key]) for key in value if key != "receipt_sha256"}
    if value["receipt_sha256"] != _canonical_sha256(base):
        _fail("gate5_resolved_package_scope_receipt_hash_mismatch")
    scope_base = {
        key: copy.deepcopy(value["scope_binding"][key])
        for key in value["scope_binding"]
        if key != "scope_binding_sha256"
    }
    if value["scope_binding"]["scope_binding_sha256"] != _canonical_sha256(scope_base):
        _fail("gate5_resolved_package_scope_binding_hash_mismatch")
    if (
        value["schema_version"]
        == GATE5_CURRENT_FACT_DECLARATION_SCOPE_RECEIPT_SCHEMA_VERSION
    ):
        taxpayer_binding = validate_ordinary_trade_taxpayer_binding(
            value.get("taxpayer_binding")
        )
        if taxpayer_binding is None or taxpayer_binding["taxpayer_scope_ref"] != value[
            "scope_binding"
        ].get("taxpayer_scope_ref"):
            _fail("gate5_resolved_package_scope_identity_binding_invalid")
    domains = value.get("domains")
    expected_ids = [item["domain_id"] for item in definition["domains"]]
    if (
        not isinstance(domains, list)
        or [
            item.get("domain_id") if isinstance(item, dict) else None
            for item in domains
        ]
        != expected_ids
    ):
        _fail("gate5_resolved_package_scope_domain_accounting_invalid")
    unresolved = []
    conflicts = []
    for row in domains:
        state = row.get("state")
        if state not in _SCOPE_STATES or not _sha256(row.get("decision_sha256")):
            _fail("gate5_resolved_package_scope_domain_row_invalid")
        decision_base = {
            key: copy.deepcopy(row[key]) for key in row if key != "decision_sha256"
        }
        if row["decision_sha256"] != _canonical_sha256(decision_base):
            _fail("gate5_resolved_package_scope_decision_hash_mismatch")
        if state == "UNRESOLVED":
            unresolved.append(row["domain_id"])
        elif state == "CONFLICT":
            conflicts.append(row["domain_id"])
    expected_status = (
        "SCOPE_RESOLVED_FOR_SUPPLIED_CASE"
        if not unresolved and not conflicts
        else "SCOPE_INCOMPLETE_FOR_SUPPLIED_CASE"
    )
    if (
        value.get("unresolved_domains") != unresolved
        or value.get("conflicts") != conflicts
        or value.get("status") != expected_status
    ):
        _fail("gate5_resolved_package_scope_receipt_accounting_invalid")
    return copy.deepcopy(value)


def _scope_component_evidence(
    scope_receipt: dict[str, Any],
) -> dict[tuple[str, str], dict[str, str]]:
    result = {}
    for row in scope_receipt["domains"]:
        for evidence in row.get("evidence_bindings", []):
            if evidence.get("authority_class") != "validated_typed_component":
                continue
            key = (evidence.get("evidence_kind"), evidence.get("evidence_sha256"))
            if (
                not isinstance(key[0], str)
                or not _sha256(key[1])
                or evidence.get("evidence_ref") != key[1]
                or key in result
            ):
                _fail("gate5_resolved_package_scope_component_evidence_invalid")
            result[key] = {
                "domain_id": row["domain_id"],
                "scope_decision_sha256": row["decision_sha256"],
            }
    return result


def _requirement_resolutions(
    *,
    definition: dict[str, Any],
    scope_receipt: dict[str, Any],
    components: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    components_by_domain: dict[str, list[dict[str, Any]]] = {}
    for component in components:
        components_by_domain.setdefault(component["domain_id"], []).append(component)
    scope_by_domain = {item["domain_id"]: item for item in scope_receipt["domains"]}
    result = []
    for domain in definition["domains"]:
        domain_id = domain["domain_id"]
        scope_row = scope_by_domain[domain_id]
        domain_components = components_by_domain.get(domain_id, [])
        scope_state = scope_row["state"]
        expected = copy.deepcopy(domain["expected_component"])
        if scope_state == "NOT_APPLICABLE":
            if domain_components:
                _fail("gate5_resolved_package_not_applicable_component_orphan")
            state = "NOT_APPLICABLE"
            diagnostics: list[str] = []
        elif scope_state == "NOT_ACTIVATED_FOR_SUPPLIED_CASE":
            if domain_components:
                _fail("gate5_resolved_package_not_activated_component_orphan")
            state = "NOT_ACTIVATED_FOR_SUPPLIED_CASE"
            diagnostics = ["supplied_case_activation_absent"]
        elif scope_state == "UNRESOLVED":
            state = "SCOPE_UNRESOLVED"
            diagnostics = (
                ["missing_source_indicated"]
                if any(
                    evidence.get("polarity") == "blocking"
                    for evidence in scope_row.get("evidence_bindings", [])
                )
                else []
            )
        elif scope_state == "CONFLICT":
            state = "SCOPE_CONFLICT"
            diagnostics = ["bounded_component_available"] if domain_components else []
        elif any(
            item["root_coverage"] == "exact_root_domain"
            and item["component_family"] == expected["family"]
            and item["covered_obligation_refs"] == domain["obligation_refs"]
            for item in domain_components
        ):
            state = "RESOLVED"
            diagnostics = []
        else:
            state = "REQUIRED_MISSING"
            diagnostics = (
                ["bounded_component_available"]
                if expected["availability"] == "published_bounded" and domain_components
                else []
            )
        row = {
            "schema_version": GATE5_DECLARATION_REQUIREMENT_RESOLUTION_SCHEMA_VERSION,
            "domain_id": domain_id,
            "scope_state": scope_state,
            "scope_decision_sha256": scope_row["decision_sha256"],
            "required_component": expected,
            "state": state,
            "component_refs": [
                item["component_binding_sha256"] for item in domain_components
            ],
            "diagnostics": diagnostics,
        }
        result.append({**row, "resolution_sha256": _canonical_sha256(row)})
    return result


def _completeness_receipt(
    *,
    publication: dict[str, Any],
    scope_receipt: dict[str, Any],
    components: list[dict[str, Any]],
    resolutions: list[dict[str, Any]],
) -> dict[str, Any]:
    blockers = [
        _blocker(row)
        for row in resolutions
        if row["state"] not in _TERMINAL_PACKAGE_STATES
    ]
    status = (
        "DECLARATION_COMPLETE_FOR_SUPPLIED_CASE"
        if not blockers
        else "DECLARATION_INCOMPLETE_FOR_SUPPLIED_CASE"
    )
    base = {
        "schema_version": GATE5_DEFINITION_BOUND_COMPLETENESS_RECEIPT_SCHEMA_VERSION,
        "status": status,
        "definition_sha256": publication["definition_sha256"],
        "scope_receipt_sha256": scope_receipt["receipt_sha256"],
        "scope_binding_sha256": scope_receipt["scope_binding"]["scope_binding_sha256"],
        "component_set_sha256": _canonical_sha256(
            [item["component_binding_sha256"] for item in components]
        ),
        "resolution_manifest_sha256": _canonical_sha256(resolutions),
        "blockers": blockers,
        "first_blocker": copy.deepcopy(blockers[0]) if blockers else None,
        "completeness_kind": "supplied_case_evidence_set",
        "real_world_taxpayer_completeness_asserted": False,
    }
    return {**base, "receipt_sha256": _canonical_sha256(base)}


def _blocker(row: dict[str, Any]) -> dict[str, str]:
    state = row["state"]
    if state == "SCOPE_UNRESOLVED":
        blocker_class = "scope"
        reason = (
            "missing_source_indicated"
            if "missing_source_indicated" in row["diagnostics"]
            else "applicability_unresolved"
        )
    elif state == "SCOPE_CONFLICT":
        blocker_class = "scope"
        reason = "applicability_conflict"
    else:
        blocker_class = "component"
        availability = row["required_component"]["availability"]
        reason = (
            "required_component_missing"
            if availability == "missing"
            else "required_component_bounded_only"
            if availability == "published_bounded"
            else "required_component_snapshot_missing"
        )
    return {
        "domain_id": row["domain_id"],
        "blocker_class": blocker_class,
        "state": state,
        "reason": reason,
    }


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


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
    raise Gate5ResolvedDeclarationPackageError(code, field)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_DECLARATION_PACKAGE_COMPONENT_SCHEMA_VERSION",
    "GATE5_DECLARATION_REQUIREMENT_RESOLUTION_SCHEMA_VERSION",
    "GATE5_DEFINITION_BOUND_COMPLETENESS_RECEIPT_SCHEMA_VERSION",
    "GATE5_RESOLVED_DECLARATION_PACKAGE_SCHEMA_VERSION",
    "Gate5ResolvedDeclarationPackageError",
    "Gate5ResolvedDeclarationPackageRuntime",
    "Gate5ResolvedDeclarationPackageRuntimeFactory",
]
