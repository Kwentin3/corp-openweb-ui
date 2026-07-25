from __future__ import annotations

import copy
import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .gate2_domain_packages import (
    Gate2DomainPackageBuilderConfig,
    Gate2DomainPackageBuilderFactory,
)
from .gate2_domain_routing import Gate2SourceUnitRouterFactory
from .gate2_financial_evidence_catalog import SUPPORTED_SOURCE_FAMILIES
from .gate2_financial_evidence_decision import (
    DECISION_SCHEMA_VERSION,
    FinancialEvidenceDecisionPackage,
    FinancialEvidenceValueCandidate,
    Gate2FinancialEvidenceDecisionContract,
    Gate2FinancialEvidenceDecisionContractFactory,
)
from .gate2_financial_evidence_materialization import (
    FinancialEvidenceAuthoritativeSourceValue,
    FinancialEvidenceSourceLineage,
    Gate2FinancialEvidenceSourcePackage,
    Gate2FinancialEvidenceSourcePackageFactory,
)
from .gate2_financial_evidence_materialization_contracts import (
    sha256_json,
    source_value_payload,
)
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_evidence_source_package import (
    validate_source_package_integrity,
)
from .gate2_source_unit_segmentation import (
    Gate2SourceUnitSegmenterConfig,
    Gate2SourceUnitSegmenterFactory,
    mark_segmentation_selection,
    validate_source_unit_segmentation,
)


DETERMINISTIC_FINANCIAL_SCOPE_SCHEMA_VERSION = (
    "broker_reports_gate2_deterministic_financial_scope_package_v1"
)
DETERMINISTIC_FINANCIAL_SCOPE_BATCH_SCHEMA_VERSION = (
    "broker_reports_gate2_deterministic_financial_scope_batch_v1"
)
DETERMINISTIC_FINANCIAL_SCOPE_POLICY_VERSION = (
    "gate2_deterministic_financial_scope_from_gate1_v1"
)
NORMALIZED_TEXT_SOURCE_FAMILY = (
    "broker_reports_normalized_text_projection_v0"
)

FACTORY_REQUIRED = (
    "Gate2DeterministicFinancialScopeFromGate1Factory.create is the only "
    "successor Gate 1-to-Financial Evidence scope authority entrypoint"
)
FORBIDDEN = (
    "Providers, models, persistence adapters and production routers must not "
    "mint deterministic financial scopes, source values, lineage, coverage "
    "or integrity"
)

_DECIMAL_RE = re.compile(r"^[+-]?(?:0|[1-9]\d*)(?:\.\d+)?$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CURRENCIES = frozenset(
    {"AED", "CHF", "CNY", "EUR", "GBP", "HKD", "JPY", "KZT", "RUB", "USD"}
)


class Gate2DeterministicFinancialScopeError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2DeterministicFinancialScopeConfig:
    table_max_selected_refs: int = 8
    text_max_selected_refs: int = 12
    maximum_scopes: int = 64


@dataclass(frozen=True)
class Gate2DeterministicFinancialScope:
    package: dict[str, Any]
    decision_contract: Gate2FinancialEvidenceDecisionContract
    source_package: Gate2FinancialEvidenceSourcePackage
    selected_source_refs: tuple[str, ...]


@dataclass(frozen=True)
class Gate2DeterministicFinancialScopeBatch:
    scopes: tuple[Gate2DeterministicFinancialScope, ...]
    segmentation_plans: tuple[dict[str, Any], ...]
    coverage: dict[str, Any]

    def safe_summary(self) -> dict[str, Any]:
        safe_coverage = {
            "selected_source_refs_total": self.coverage[
                "selected_source_refs_total"
            ],
            "decision_scope_source_refs_total": self.coverage[
                "decision_scope_source_refs_total"
            ],
            "deterministic_no_fact_source_refs_total": self.coverage[
                "deterministic_no_fact_source_refs_total"
            ],
            "unaccounted_source_refs_total": len(
                self.coverage["unaccounted_source_refs"]
            ),
            "duplicate_terminal_owner_refs_total": len(
                self.coverage["duplicate_terminal_owner_refs"]
            ),
            "all_selected_refs_terminally_accounted": self.coverage[
                "all_selected_refs_terminally_accounted"
            ],
        }
        return {
            "schema_version": DETERMINISTIC_FINANCIAL_SCOPE_BATCH_SCHEMA_VERSION,
            "scope_schema_version": DETERMINISTIC_FINANCIAL_SCOPE_SCHEMA_VERSION,
            "scope_policy_version": DETERMINISTIC_FINANCIAL_SCOPE_POLICY_VERSION,
            "scopes_total": len(self.scopes),
            "segmentation_plans_total": len(self.segmentation_plans),
            "coverage": safe_coverage,
            "scope_integrity_hashes": [
                item.package["integrity_hash"] for item in self.scopes
            ],
            "model_calls_total": 0,
            "provider_calls_total": 0,
            "persistence_writes_total": 0,
        }


class Gate2DeterministicFinancialScopeFromGate1Factory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
        config: Gate2DeterministicFinancialScopeConfig | None = None,
    ) -> None:
        self.registry = registry
        self.config = config or Gate2DeterministicFinancialScopeConfig()

    def create(
        self,
        *,
        gate1_packages: Iterable[dict[str, Any]],
    ) -> Gate2DeterministicFinancialScopeBatch:
        self._validate_config()
        packages = tuple(
            sorted(
                (copy.deepcopy(item) for item in gate1_packages),
                key=_gate1_package_key,
            )
        )
        if not packages:
            _fail("deterministic_financial_scope_gate1_packages_empty")
        _validate_gate1_package_identities(packages)

        segmentation_plans: list[dict[str, Any]] = []
        domain_packages: list[dict[str, Any]] = []
        selected_refs: set[str] = set()
        deterministic_no_fact_refs: set[str] = set()
        decision_refs: set[str] = set()
        routing_evidence: dict[str, dict[str, Any]] = {}

        segmenter = Gate2SourceUnitSegmenterFactory(
            Gate2SourceUnitSegmenterConfig(
                table_max_selected_refs=self.config.table_max_selected_refs,
                text_max_selected_refs=self.config.text_max_selected_refs,
            )
        ).create()
        router = Gate2SourceUnitRouterFactory().create()
        domain_builder = Gate2DomainPackageBuilderFactory(
            Gate2DomainPackageBuilderConfig(
                include_secondary_candidates=True,
                candidate_binding_enabled=False,
            )
        ).create()

        for base_package in packages:
            parent_route = router.route(base_package)
            parent_selected = tuple(parent_route["selected_source_refs"])
            overlap = selected_refs & set(parent_selected)
            if overlap:
                _fail(
                    "deterministic_financial_scope_selected_ref_cross_package_duplicate"
                )
            selected_refs.update(parent_selected)

            segmentation = segmenter.segment(
                base_package=base_package,
                parent_route=parent_route,
            )
            selected_segment_refs = [
                str(item["segmentation"]["segment_ref"])
                for item in segmentation.derived_packages
            ]
            plan = mark_segmentation_selection(
                segmentation.plan,
                selected_segment_refs,
            )
            validate_source_unit_segmentation(
                plan,
                segmentation.derived_packages,
            )
            segmentation_plans.append(plan)

            for derived in segmentation.derived_packages:
                route = router.route(derived)
                for entry in route["route_entries"]:
                    source_ref = str(entry["source_ref"])
                    if source_ref in routing_evidence:
                        _fail(
                            "deterministic_financial_scope_derived_ref_duplicate"
                        )
                    routing_evidence[source_ref] = {
                        "route_kind": entry["route_kind"],
                        "candidate_domains": copy.deepcopy(
                            entry["candidate_domains"]
                        ),
                        "primary_suggested_domain": entry[
                            "primary_suggested_domain"
                        ],
                        "reason_codes": copy.deepcopy(
                            entry.get("reason_codes") or []
                        ),
                        "routing_policy_version": route[
                            "routing_policy_version"
                        ],
                        "derived_source_unit_ref": route["source_unit_ref"],
                    }
                    if entry["route_kind"] == "deterministic_no_fact":
                        deterministic_no_fact_refs.add(source_ref)
                    else:
                        decision_refs.add(source_ref)
                domain_packages.extend(
                    domain_builder.build(
                        base_package=derived,
                        route=route,
                    )
                )

        if set(routing_evidence) != selected_refs:
            _fail("deterministic_financial_scope_routing_coverage_incomplete")
        if decision_refs & deterministic_no_fact_refs:
            _fail("deterministic_financial_scope_terminal_ownership_duplicate")
        if decision_refs | deterministic_no_fact_refs != selected_refs:
            _fail("deterministic_financial_scope_terminal_coverage_incomplete")

        scopes = tuple(
            self._scope(
                component=component,
                routing_evidence=routing_evidence,
            )
            for component in _canonical_components(tuple(domain_packages))
        )
        if len(scopes) > self.config.maximum_scopes:
            _fail("deterministic_financial_scope_limit_exceeded")
        scoped_refs = {
            source_ref
            for scope in scopes
            for source_ref in scope.selected_source_refs
        }
        if scoped_refs != decision_refs:
            _fail("deterministic_financial_scope_decision_coverage_incomplete")
        if sum(len(scope.selected_source_refs) for scope in scopes) != len(
            scoped_refs
        ):
            _fail("deterministic_financial_scope_cross_scope_binding")

        coverage = {
            "selected_source_refs": sorted(selected_refs),
            "decision_scope_source_refs": sorted(decision_refs),
            "deterministic_no_fact_source_refs": sorted(
                deterministic_no_fact_refs
            ),
            "selected_source_refs_total": len(selected_refs),
            "decision_scope_source_refs_total": len(decision_refs),
            "deterministic_no_fact_source_refs_total": len(
                deterministic_no_fact_refs
            ),
            "unaccounted_source_refs": [],
            "duplicate_terminal_owner_refs": [],
            "all_selected_refs_terminally_accounted": True,
            "model_calls_total": 0,
        }
        return Gate2DeterministicFinancialScopeBatch(
            scopes=scopes,
            segmentation_plans=tuple(segmentation_plans),
            coverage=coverage,
        )

    def _validate_config(self) -> None:
        if self.config.table_max_selected_refs <= 0:
            _fail("deterministic_financial_scope_table_limit_invalid")
        if self.config.text_max_selected_refs <= 0:
            _fail("deterministic_financial_scope_text_limit_invalid")
        if self.config.maximum_scopes <= 0:
            _fail("deterministic_financial_scope_limit_invalid")

    def _scope(
        self,
        *,
        component: tuple[dict[str, Any], ...],
        routing_evidence: dict[str, dict[str, Any]],
    ) -> Gate2DeterministicFinancialScope:
        selected_refs = tuple(
            sorted(
                {
                    str(source_ref)
                    for package in component
                    for source_ref in package["coverage_expectation"][
                        "selected_source_refs"
                    ]
                }
            )
        )
        if not selected_refs:
            _fail("deterministic_financial_scope_selected_refs_empty")
        document_ref = _single_value(
            component,
            "document_ref",
            "deterministic_financial_scope_cross_document",
        )
        normalization_run_ref = _single_value(
            component,
            "normalization_run_id",
            "deterministic_financial_scope_cross_normalization_run",
        )
        source_family_id, source_family_evidence = _source_family(component)
        source_values, candidates, value_origins = _authoritative_values(
            packages=component,
            document_ref=document_ref,
        )

        identity_seed = {
            "schema_version": DETERMINISTIC_FINANCIAL_SCOPE_SCHEMA_VERSION,
            "policy_version": DETERMINISTIC_FINANCIAL_SCOPE_POLICY_VERSION,
            "normalization_run_ref": normalization_run_ref,
            "document_ref": document_ref,
            "selected_source_refs": list(selected_refs),
            "source_value_refs": [
                item.source_value_ref for item in source_values
            ],
            "source_family_id": source_family_id,
        }
        scope_digest = sha256_json(identity_seed)[:24]
        source_scope_ref = (
            f"scope:gate2:deterministic-financial:{scope_digest}"
        )
        source_values, candidates, value_origins = _add_reference_values(
            source_values=source_values,
            candidates=candidates,
            value_origins=value_origins,
            document_ref=document_ref,
            source_scope_ref=source_scope_ref,
            selected_refs=selected_refs,
        )
        restriction_codes = tuple(
            sorted(
                {
                    str(code)
                    for package in component
                    for code in package.get("forbidden_assumptions") or []
                    if code
                }
            )
        )
        issue_refs = tuple(
            sorted(
                {
                    str(ref)
                    for package in component
                    for ref in package.get("allowed_issue_refs") or []
                    if ref
                }
            )
        )
        source_evidence_refs = tuple(
            sorted(
                {
                    ref
                    for value in source_values
                    for ref in value.source_evidence_refs
                }
            )
        )
        source_package = Gate2FinancialEvidenceSourcePackageFactory(
            package_ref=(
                f"package:gate2:deterministic-financial:{scope_digest}"
            ),
            normalization_run_ref=normalization_run_ref,
            document_ref=document_ref,
            source_scope_ref=source_scope_ref,
            source_family_id=source_family_id,
            source_values=source_values,
            source_evidence_refs=source_evidence_refs,
            completeness="complete",
            restriction_codes=restriction_codes,
            issue_refs=issue_refs,
        ).create()
        decision_contract = Gate2FinancialEvidenceDecisionContractFactory(
            registry=self.registry,
            package=FinancialEvidenceDecisionPackage(
                source_scope_ref=source_scope_ref,
                source_family_id=source_family_id,
                candidates=candidates,
            ),
        ).create()
        candidate_by_ref = {
            item.source_value_ref: item
            for item in decision_contract.package.candidates
        }
        source_values_payload = []
        for value in source_package.source_values:
            payload = source_value_payload(value)
            payload["allowed_roles"] = list(
                candidate_by_ref[value.source_value_ref].allowed_roles
            )
            payload["value_authority"] = value_origins[
                value.source_value_ref
            ]
            source_values_payload.append(payload)

        package = {
            "schema_version": DETERMINISTIC_FINANCIAL_SCOPE_SCHEMA_VERSION,
            "package_ref": source_package.package_ref,
            "scope_policy_version": (
                DETERMINISTIC_FINANCIAL_SCOPE_POLICY_VERSION
            ),
            "authority": "gate1_evidence_and_deterministic_registry_rules",
            "source_scope_ref": source_scope_ref,
            "normalization_run_ref": normalization_run_ref,
            "document_ref": document_ref,
            "authoritative_source_refs": list(selected_refs),
            "source_values": source_values_payload,
            "source_package_authority": _source_package_payload(
                source_package
            ),
            "source_family_evidence": source_family_evidence,
            "registry": {
                "registry_version": self.registry.registry_version,
                "registry_hash": self.registry.registry_hash,
                "eligible_input_type_ids": list(
                    decision_contract.eligible_type_ids
                ),
            },
            "decision_contract": {
                "schema_version": DECISION_SCHEMA_VERSION,
                "schema_hash": decision_contract.canonical_schema_hash(),
                "candidate_source_value_refs": [
                    item.source_value_ref
                    for item in decision_contract.package.candidates
                ],
            },
            "routing_hints": [
                {
                    "source_ref": source_ref,
                    **copy.deepcopy(routing_evidence[source_ref]),
                }
                for source_ref in selected_refs
            ],
            "terminal_coverage_boundary": {
                "authorized_source_refs": list(selected_refs),
                "decision_required_source_refs": list(selected_refs),
                "external_source_refs_allowed": False,
                "terminal_dispositions": [
                    "typed_input",
                    "unclassified_financial_input",
                    "no_financial_input",
                    "unsupported",
                ],
                "authorized_total": len(selected_refs),
                "accounted_total": len(selected_refs),
                "unaccounted_source_refs": [],
                "duplicate_owner_source_refs": [],
                "all_authorized_refs_accounted": True,
            },
            "execution_boundary": {
                "provider_calls": 0,
                "semantic_classification": False,
                "materialization": False,
                "persistence": False,
                "production_routing": False,
            },
        }
        package["integrity_hash"] = sha256_json(package)
        scope = Gate2DeterministicFinancialScope(
            package=package,
            decision_contract=decision_contract,
            source_package=source_package,
            selected_source_refs=selected_refs,
        )
        validate_deterministic_financial_scope(scope)
        return scope


def validate_deterministic_financial_scope(
    scope: Gate2DeterministicFinancialScope,
) -> None:
    package = scope.package
    if (
        package.get("schema_version")
        != DETERMINISTIC_FINANCIAL_SCOPE_SCHEMA_VERSION
    ):
        _fail("deterministic_financial_scope_schema_invalid")
    payload = copy.deepcopy(package)
    integrity_hash = payload.pop("integrity_hash", None)
    if integrity_hash != sha256_json(payload):
        _fail("deterministic_financial_scope_integrity_invalid")
    validate_source_package_integrity(scope.source_package)
    if package.get("source_package_authority") != _source_package_payload(
        scope.source_package
    ):
        _fail("deterministic_financial_scope_source_package_mismatch")
    if package.get("package_ref") != scope.source_package.package_ref:
        _fail("deterministic_financial_scope_package_ref_mismatch")
    if package.get("source_scope_ref") != scope.source_package.source_scope_ref:
        _fail("deterministic_financial_scope_scope_ref_mismatch")
    if (
        package.get("source_scope_ref")
        != scope.decision_contract.package.source_scope_ref
    ):
        _fail("deterministic_financial_scope_decision_scope_mismatch")
    if (
        package.get("registry", {}).get("registry_version")
        != scope.decision_contract.registry.registry_version
        or package.get("registry", {}).get("registry_hash")
        != scope.decision_contract.registry.registry_hash
        or package.get("registry", {}).get("eligible_input_type_ids")
        != list(scope.decision_contract.eligible_type_ids)
    ):
        _fail("deterministic_financial_scope_registry_mismatch")
    if (
        package.get("decision_contract", {}).get("schema_hash")
        != scope.decision_contract.canonical_schema_hash()
    ):
        _fail("deterministic_financial_scope_decision_hash_mismatch")

    authoritative_refs = package.get("authoritative_source_refs")
    if authoritative_refs != sorted(set(authoritative_refs or [])):
        _fail("deterministic_financial_scope_authoritative_refs_invalid")
    if tuple(authoritative_refs) != scope.selected_source_refs:
        _fail("deterministic_financial_scope_authoritative_refs_mismatch")
    boundary = package.get("terminal_coverage_boundary") or {}
    if (
        boundary.get("authorized_source_refs") != authoritative_refs
        or boundary.get("decision_required_source_refs")
        != authoritative_refs
        or boundary.get("accounted_total") != len(authoritative_refs)
        or boundary.get("authorized_total") != len(authoritative_refs)
        or boundary.get("unaccounted_source_refs") != []
        or boundary.get("duplicate_owner_source_refs") != []
        or boundary.get("all_authorized_refs_accounted") is not True
        or boundary.get("external_source_refs_allowed") is not False
    ):
        _fail("deterministic_financial_scope_terminal_coverage_invalid")

    values = package.get("source_values") or []
    value_refs = [str(item.get("source_value_ref") or "") for item in values]
    source_package_refs = [
        item.source_value_ref for item in scope.source_package.source_values
    ]
    candidate_refs = [
        item.source_value_ref
        for item in scope.decision_contract.package.candidates
    ]
    if (
        value_refs != sorted(set(value_refs))
        or value_refs != source_package_refs
        or value_refs != candidate_refs
    ):
        _fail("deterministic_financial_scope_source_value_identity_invalid")
    for item in values:
        lineage = item.get("lineage") or {}
        if lineage.get("document_ref") != package.get("document_ref"):
            _fail("deterministic_financial_scope_lineage_document_invalid")
        if not any(
            lineage.get(field)
            for field in (
                "page_ref",
                "table_ref",
                "row_ref",
                "cell_ref",
                "text_segment_ref",
            )
        ):
            _fail("deterministic_financial_scope_lineage_locator_missing")
        if not item.get("source_evidence_refs"):
            _fail("deterministic_financial_scope_evidence_refs_missing")
        if not item.get("allowed_roles"):
            _fail("deterministic_financial_scope_allowed_roles_missing")
        if item.get("value_authority") not in {
            "gate1_authoritative_literal",
            "deterministic_source_reference",
        }:
            _fail("deterministic_financial_scope_value_authority_invalid")


def _validate_gate1_package_identities(
    packages: tuple[dict[str, Any], ...],
) -> None:
    package_ids: set[str] = set()
    unit_ids: set[str] = set()
    for package in packages:
        package_id = str(package.get("package_id") or "")
        unit_id = str((package.get("source_unit") or {}).get("unit_id") or "")
        if not package_id or not unit_id:
            _fail("deterministic_financial_scope_gate1_identity_missing")
        if package_id in package_ids:
            _fail("deterministic_financial_scope_gate1_package_duplicate")
        if unit_id in unit_ids:
            _fail("deterministic_financial_scope_gate1_unit_duplicate")
        package_ids.add(package_id)
        unit_ids.add(unit_id)


def _gate1_package_key(package: dict[str, Any]) -> tuple[str, str, str]:
    unit = package.get("source_unit") or {}
    return (
        str(package.get("document_ref") or ""),
        str(unit.get("unit_id") or ""),
        str(package.get("package_id") or ""),
    )


def _canonical_components(
    packages: tuple[dict[str, Any], ...],
) -> tuple[tuple[dict[str, Any], ...], ...]:
    ordered = tuple(
        sorted(
            packages,
            key=lambda item: (
                str(item.get("document_ref") or ""),
                str(item.get("package_id") or ""),
                str(item.get("extractor_domain") or ""),
            ),
        )
    )
    remaining = set(range(len(ordered)))
    refs = [
        set(
            item["coverage_expectation"]["selected_source_refs"]
        )
        for item in ordered
    ]
    result: list[tuple[dict[str, Any], ...]] = []
    while remaining:
        pending = [min(remaining)]
        component: set[int] = set()
        while pending:
            current = pending.pop()
            if current in component:
                continue
            component.add(current)
            remaining.discard(current)
            pending.extend(
                other
                for other in sorted(remaining)
                if refs[current] & refs[other]
            )
        result.append(tuple(ordered[index] for index in sorted(component)))
    return tuple(result)


def _single_value(
    packages: tuple[dict[str, Any], ...],
    field: str,
    error_code: str,
) -> str:
    values = {str(item.get(field) or "") for item in packages}
    if len(values) != 1 or not next(iter(values)):
        _fail(error_code)
    return next(iter(values))


def _source_family(
    packages: tuple[dict[str, Any], ...],
) -> tuple[str, dict[str, Any]]:
    explicit = {
        str(
            item.get("source_family_id")
            or (item.get("source_unit") or {}).get("source_family_id")
            or ""
        )
        for item in packages
    }
    explicit.discard("")
    unit_kinds = sorted(
        {
            str((item.get("source_unit") or {}).get("unit_kind") or "")
            for item in packages
        }
    )
    unit_refs = sorted(
        {
            str((item.get("source_unit") or {}).get("unit_id") or "")
            for item in packages
        }
    )
    if len(explicit) > 1:
        _fail("deterministic_financial_scope_source_family_conflict")
    if explicit:
        source_family_id = next(iter(explicit))
        resolution = "gate1_explicit_source_family"
    elif unit_kinds and set(unit_kinds) == {"table_row_window"}:
        source_family_id = SUPPORTED_SOURCE_FAMILIES[0]
        resolution = "deterministic_gate1_unit_kind_mapping"
    else:
        source_family_id = NORMALIZED_TEXT_SOURCE_FAMILY
        resolution = "deterministic_gate1_unit_kind_mapping"
    return source_family_id, {
        "source_family_id": source_family_id,
        "resolution": resolution,
        "source_unit_kinds": unit_kinds,
        "source_unit_refs": unit_refs,
    }


def _authoritative_values(
    *,
    packages: tuple[dict[str, Any], ...],
    document_ref: str,
) -> tuple[
    tuple[FinancialEvidenceAuthoritativeSourceValue, ...],
    tuple[FinancialEvidenceValueCandidate, ...],
    dict[str, str],
]:
    values_by_ref: dict[str, FinancialEvidenceAuthoritativeSourceValue] = {}
    candidates_by_ref: dict[str, FinancialEvidenceValueCandidate] = {}
    for package in packages:
        for value, candidate in _package_values(
            package=package,
            document_ref=document_ref,
        ):
            previous = values_by_ref.get(value.source_value_ref)
            if previous is not None and previous != value:
                _fail("deterministic_financial_scope_source_value_conflict")
            previous_candidate = candidates_by_ref.get(
                candidate.source_value_ref
            )
            if (
                previous_candidate is not None
                and previous_candidate != candidate
            ):
                _fail("deterministic_financial_scope_candidate_conflict")
            values_by_ref[value.source_value_ref] = value
            candidates_by_ref[candidate.source_value_ref] = candidate
    if not values_by_ref:
        _fail("deterministic_financial_scope_source_values_empty")
    ordered_refs = sorted(values_by_ref)
    return (
        tuple(values_by_ref[ref] for ref in ordered_refs),
        tuple(candidates_by_ref[ref] for ref in ordered_refs),
        {ref: "gate1_authoritative_literal" for ref in ordered_refs},
    )


def _add_reference_values(
    *,
    source_values: tuple[FinancialEvidenceAuthoritativeSourceValue, ...],
    candidates: tuple[FinancialEvidenceValueCandidate, ...],
    value_origins: dict[str, str],
    document_ref: str,
    source_scope_ref: str,
    selected_refs: tuple[str, ...],
) -> tuple[
    tuple[FinancialEvidenceAuthoritativeSourceValue, ...],
    tuple[FinancialEvidenceValueCandidate, ...],
    dict[str, str],
]:
    values = {item.source_value_ref: item for item in source_values}
    candidate_by_ref = {
        item.source_value_ref: item for item in candidates
    }
    origins = dict(value_origins)
    locator = selected_refs[0]
    for role, suffix in (
        ("statement_scope", "statement-scope"),
        ("printed_label_evidence_ref", "printed-label"),
    ):
        ref = f"value:{source_scope_ref}:{suffix}"
        values[ref] = FinancialEvidenceAuthoritativeSourceValue(
            source_value_ref=ref,
            source_ref=locator,
            value_type="source_reference",
            literal_value=locator,
            source_evidence_refs=(locator,),
            lineage=FinancialEvidenceSourceLineage(
                document_ref=document_ref,
                text_segment_ref=locator,
            ),
        )
        candidate_by_ref[ref] = FinancialEvidenceValueCandidate(
            source_value_ref=ref,
            source_ref=locator,
            value_type="source_reference",
            allowed_roles=(role,),
        )
        origins[ref] = "deterministic_source_reference"
    ordered_refs = sorted(values)
    return (
        tuple(values[ref] for ref in ordered_refs),
        tuple(candidate_by_ref[ref] for ref in ordered_refs),
        origins,
    )


def _package_values(
    *,
    package: dict[str, Any],
    document_ref: str,
) -> tuple[
    tuple[
        FinancialEvidenceAuthoritativeSourceValue,
        FinancialEvidenceValueCandidate,
    ],
    ...,
]:
    unit = package.get("source_unit") or {}
    allowed = set(package.get("allowed_source_value_refs") or [])
    index = {
        str(item.get("source_value_ref")): item
        for item in unit.get("source_value_index") or []
        if isinstance(item, dict) and item.get("source_value_ref")
    }
    literal_by_ref: dict[str, str] = {}
    segment_by_ref: dict[str, dict[str, Any]] = {}

    def bind_literal(ref: str, value: str) -> None:
        existing = literal_by_ref.get(ref)
        if existing is not None and existing != value:
            _fail(
                "deterministic_financial_scope_authoritative_literal_conflict"
            )
        literal_by_ref[ref] = value

    projection = unit.get("model_source_projection") or {}
    for row in projection.get("rows") or []:
        for cell in row.get("cells") or []:
            value = cell.get("value")
            if not isinstance(value, str) or not value:
                continue
            refs = cell.get("source_value_refs") or [
                cell.get("source_value_ref")
            ]
            for ref in refs:
                normalized_ref = str(ref or "")
                if normalized_ref in allowed:
                    bind_literal(normalized_ref, value)
    for segment in projection.get("segments") or []:
        ref = str(segment.get("source_value_ref") or "")
        value = segment.get("value")
        if ref in allowed and isinstance(value, str) and value:
            bind_literal(ref, value)
            segment_by_ref[ref] = segment
    for private_value in unit.get("private_values") or []:
        value = private_value.get("normalized_value")
        if not isinstance(value, str) or not value:
            continue
        for ref in private_value.get("source_value_refs") or []:
            normalized_ref = str(ref or "")
            if normalized_ref in allowed:
                bind_literal(normalized_ref, value)
    if set(literal_by_ref) != allowed:
        _fail("deterministic_financial_scope_authoritative_literal_missing")

    result = []
    for ref in sorted(allowed):
        literal = literal_by_ref[ref]
        value_type, roles = _infer_type(literal)
        indexed = index.get(ref) or {}
        segment = segment_by_ref.get(ref) or {}
        source_ref = str(
            indexed.get("cell_ref")
            or indexed.get("text_segment_ref")
            or indexed.get("source_object_ref")
            or segment.get("text_segment_ref")
            or ""
        )
        if not source_ref:
            _fail("deterministic_financial_scope_source_ref_missing")
        lineage = FinancialEvidenceSourceLineage(
            document_ref=document_ref,
            page_ref=_optional_string(segment.get("page_ref")),
            table_ref=_optional_string(unit.get("table_ref")),
            row_ref=_optional_string(indexed.get("row_ref")),
            cell_ref=_optional_string(indexed.get("cell_ref")),
            text_segment_ref=_optional_string(
                indexed.get("text_segment_ref")
                or segment.get("text_segment_ref")
            ),
        )
        if not any(
            (
                lineage.page_ref,
                lineage.table_ref,
                lineage.row_ref,
                lineage.cell_ref,
                lineage.text_segment_ref,
            )
        ):
            _fail("deterministic_financial_scope_lineage_locator_missing")
        evidence = tuple(
            sorted(
                {
                    source_ref,
                    *(
                        str(item)
                        for item in package.get("allowed_evidence_refs") or []
                        if item
                    ),
                }
            )
        )
        result.append(
            (
                FinancialEvidenceAuthoritativeSourceValue(
                    source_value_ref=ref,
                    source_ref=source_ref,
                    value_type=value_type,
                    literal_value=literal,
                    source_evidence_refs=evidence,
                    lineage=lineage,
                ),
                FinancialEvidenceValueCandidate(
                    source_value_ref=ref,
                    source_ref=source_ref,
                    value_type=value_type,
                    allowed_roles=roles,
                ),
            )
        )
    return tuple(result)


def _infer_type(literal: str) -> tuple[str, tuple[str, ...]]:
    normalized = literal.strip()
    if _DATE_RE.fullmatch(normalized):
        return "source_date", ("as_of_date",)
    if _DECIMAL_RE.fullmatch(normalized):
        return "source_decimal", ("amount",)
    if normalized.upper() in _CURRENCIES:
        return "source_currency", ("currency",)
    return "source_text", ("source_label",)


def _source_package_payload(
    package: Gate2FinancialEvidenceSourcePackage,
) -> dict[str, Any]:
    return {
        "schema_version": package.schema_version,
        "package_ref": package.package_ref,
        "normalization_run_ref": package.normalization_run_ref,
        "document_ref": package.document_ref,
        "source_scope_ref": package.source_scope_ref,
        "source_family_id": package.source_family_id,
        "source_values": [
            {
                **source_value_payload(item),
                "lineage": asdict(item.lineage),
            }
            for item in package.source_values
        ],
        "source_evidence_refs": list(package.source_evidence_refs),
        "completeness": package.completeness,
        "restriction_codes": list(package.restriction_codes),
        "issue_refs": list(package.issue_refs),
        "integrity_hash": package.integrity_hash,
    }


def _optional_string(value: Any) -> str | None:
    return str(value) if isinstance(value, str) and value else None


def _fail(code: str) -> None:
    raise Gate2DeterministicFinancialScopeError(code)
