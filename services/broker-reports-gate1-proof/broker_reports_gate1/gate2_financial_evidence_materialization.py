from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from .gate2_financial_evidence_decision import (
    DECISION_SCHEMA_VERSION,
    FinancialEvidenceDecision,
    Gate2FinancialEvidenceDecisionContract,
    NoFinancialInputDecision,
    TypedFinancialInputDecision,
    UnclassifiedFinancialInputDecision,
    UnsupportedFinancialInputDecision,
)
from .gate2_financial_evidence_registry import (
    REGISTRY_ID,
    Gate2FinancialEvidenceRegistrySnapshot,
)


FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION = (
    "broker_reports_financial_evidence_inputs_v1"
)
SOURCE_PACKAGE_SCHEMA_VERSION = (
    "broker_reports_financial_evidence_source_package_v1"
)
VALIDATED_DECISION_SCHEMA_VERSION = (
    "broker_reports_financial_evidence_validated_decision_v1"
)
MATERIALIZATION_POLICY_VERSION = (
    "broker_reports_financial_evidence_materialization_v1"
)

FACTORY_REQUIRED = (
    "Gate2FinancialEvidenceMaterializerFactory.create and materialize are "
    "the only production financial evidence materialization path"
)
FORBIDDEN = (
    "Models, prompts and providers must not mint input IDs, provenance, "
    "normalized values, ownership, completeness, integrity or Gate 3 fields"
)

COMPLETENESS_VALUES = frozenset(
    {"blocked", "complete", "partial", "restricted"}
)
_IDENTIFIER_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_:.\\/-]*$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_TEMPORAL_ROLES = frozenset(
    {"as_of_date", "event_date", "period", "period_end", "period_start"}
)
_MEASUREMENT_ROLES = frozenset({"currency", "unit"})
_MAX_LITERAL_LENGTH = 20_000


class Gate2FinancialEvidenceMaterializationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class FinancialEvidenceSourceLineage:
    document_ref: str
    page_ref: str | None = None
    table_ref: str | None = None
    row_ref: str | None = None
    cell_ref: str | None = None
    text_segment_ref: str | None = None


@dataclass(frozen=True)
class FinancialEvidenceAuthoritativeSourceValue:
    source_value_ref: str
    source_ref: str
    value_type: str
    literal_value: str
    source_evidence_refs: tuple[str, ...]
    lineage: FinancialEvidenceSourceLineage


@dataclass(frozen=True)
class Gate2FinancialEvidenceSourcePackage:
    schema_version: str
    package_ref: str
    normalization_run_ref: str
    document_ref: str
    source_scope_ref: str
    source_family_id: str
    source_values: tuple[FinancialEvidenceAuthoritativeSourceValue, ...]
    source_evidence_refs: tuple[str, ...]
    completeness: str
    restriction_codes: tuple[str, ...]
    issue_refs: tuple[str, ...]
    integrity_hash: str


@dataclass(frozen=True)
class FinancialEvidenceExecutionMetadata:
    execution_ref: str
    decision_validation_ref: str


@dataclass(frozen=True)
class FinancialEvidenceValidatedDecision:
    schema_version: str
    decision_schema_version: str
    decision_schema_hash: str
    registry_version: str
    registry_hash: str
    source_scope_ref: str
    source_family_id: str
    candidate_refs: tuple[str, ...]
    candidate_authority_hash: str
    decision: FinancialEvidenceDecision


class Gate2FinancialEvidenceSourcePackageFactory:
    def __init__(
        self,
        *,
        package_ref: str,
        normalization_run_ref: str,
        document_ref: str,
        source_scope_ref: str,
        source_family_id: str,
        source_values: tuple[
            FinancialEvidenceAuthoritativeSourceValue, ...
        ],
        source_evidence_refs: tuple[str, ...],
        completeness: str,
        restriction_codes: tuple[str, ...] = (),
        issue_refs: tuple[str, ...] = (),
    ) -> None:
        self.package_ref = package_ref
        self.normalization_run_ref = normalization_run_ref
        self.document_ref = document_ref
        self.source_scope_ref = source_scope_ref
        self.source_family_id = source_family_id
        self.source_values = source_values
        self.source_evidence_refs = source_evidence_refs
        self.completeness = completeness
        self.restriction_codes = restriction_codes
        self.issue_refs = issue_refs

    def create(self) -> Gate2FinancialEvidenceSourcePackage:
        for value, field in (
            (self.package_ref, "package_ref"),
            (self.normalization_run_ref, "normalization_run_ref"),
            (self.document_ref, "document_ref"),
            (self.source_scope_ref, "source_scope_ref"),
            (self.source_family_id, "source_family_id"),
        ):
            _identifier(value, field)
        if self.completeness not in COMPLETENESS_VALUES:
            _fail("financial_evidence_source_package_completeness_invalid")
        source_values = tuple(
            sorted(
                (
                    _normalize_authoritative_source_value(
                        item,
                        document_ref=self.document_ref,
                    )
                    for item in self.source_values
                ),
                key=lambda item: item.source_value_ref,
            )
        )
        refs = [item.source_value_ref for item in source_values]
        if len(refs) != len(set(refs)):
            _fail("financial_evidence_source_value_ref_duplicate")
        source_evidence_refs = _sorted_identifiers(
            self.source_evidence_refs,
            field="source_evidence_ref",
            required=True,
        )
        restriction_codes = _sorted_identifiers(
            self.restriction_codes,
            field="restriction_code",
        )
        issue_refs = _sorted_identifiers(
            self.issue_refs,
            field="issue_ref",
        )
        payload = {
            "schema_version": SOURCE_PACKAGE_SCHEMA_VERSION,
            "package_ref": self.package_ref,
            "normalization_run_ref": self.normalization_run_ref,
            "document_ref": self.document_ref,
            "source_scope_ref": self.source_scope_ref,
            "source_family_id": self.source_family_id,
            "source_values": [
                _source_value_payload(item) for item in source_values
            ],
            "source_evidence_refs": list(source_evidence_refs),
            "completeness": self.completeness,
            "restriction_codes": list(restriction_codes),
            "issue_refs": list(issue_refs),
        }
        return Gate2FinancialEvidenceSourcePackage(
            schema_version=SOURCE_PACKAGE_SCHEMA_VERSION,
            package_ref=self.package_ref,
            normalization_run_ref=self.normalization_run_ref,
            document_ref=self.document_ref,
            source_scope_ref=self.source_scope_ref,
            source_family_id=self.source_family_id,
            source_values=source_values,
            source_evidence_refs=source_evidence_refs,
            completeness=self.completeness,
            restriction_codes=restriction_codes,
            issue_refs=issue_refs,
            integrity_hash=_sha256_json(payload),
        )


class Gate2FinancialEvidenceValidatedDecisionFactory:
    def __init__(
        self,
        *,
        contract: Gate2FinancialEvidenceDecisionContract,
    ) -> None:
        self.contract = contract

    def create(
        self, model_output: str | dict[str, Any]
    ) -> FinancialEvidenceValidatedDecision:
        decision = self.contract.parse_model_output(model_output)
        return FinancialEvidenceValidatedDecision(
            schema_version=VALIDATED_DECISION_SCHEMA_VERSION,
            decision_schema_version=DECISION_SCHEMA_VERSION,
            decision_schema_hash=self.contract.canonical_schema_hash(),
            registry_version=self.contract.registry.registry_version,
            registry_hash=self.contract.registry.registry_hash,
            source_scope_ref=self.contract.package.source_scope_ref,
            source_family_id=self.contract.package.source_family_id,
            candidate_refs=tuple(
                item.source_value_ref
                for item in self.contract.package.candidates
            ),
            candidate_authority_hash=_sha256_json(
                [
                    {
                        "source_value_ref": item.source_value_ref,
                        "source_ref": item.source_ref,
                        "value_type": item.value_type,
                    }
                    for item in self.contract.package.candidates
                ]
            ),
            decision=decision,
        )


class Gate2FinancialEvidenceMaterializerFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
        source_package: Gate2FinancialEvidenceSourcePackage,
        execution_metadata: FinancialEvidenceExecutionMetadata,
    ) -> None:
        self.registry = registry
        self.source_package = source_package
        self.execution_metadata = execution_metadata

    def create(self) -> "Gate2FinancialEvidenceMaterializer":
        _validate_source_package_integrity(self.source_package)
        _identifier(
            self.execution_metadata.execution_ref,
            "execution_ref",
        )
        _identifier(
            self.execution_metadata.decision_validation_ref,
            "decision_validation_ref",
        )
        return Gate2FinancialEvidenceMaterializer(
            registry=self.registry,
            source_package=self.source_package,
            execution_metadata=self.execution_metadata,
        )


class Gate2FinancialEvidenceMaterializer:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
        source_package: Gate2FinancialEvidenceSourcePackage,
        execution_metadata: FinancialEvidenceExecutionMetadata,
    ) -> None:
        self.registry = registry
        self.source_package = source_package
        self.execution_metadata = execution_metadata

    def materialize(
        self,
        *,
        validated_decision: FinancialEvidenceValidatedDecision,
    ) -> dict[str, Any]:
        self._validate_authorities(validated_decision)
        decision = validated_decision.decision
        typed_inputs: list[dict[str, Any]] = []
        unclassified_inputs: list[dict[str, Any]] = []
        bound_refs: tuple[str, ...] = ()
        if isinstance(decision, TypedFinancialInputDecision):
            typed_input = self._materialize_typed(decision)
            typed_inputs.append(typed_input)
            bound_refs = tuple(
                item["source_value_ref"]
                for item in typed_input["source_values"]
            )
        elif isinstance(decision, UnclassifiedFinancialInputDecision):
            unclassified = self._materialize_unclassified(decision)
            unclassified_inputs.append(unclassified)
            bound_refs = tuple(
                item["source_value_ref"]
                for item in unclassified["source_values"]
            )
        elif not isinstance(
            decision,
            NoFinancialInputDecision | UnsupportedFinancialInputDecision,
        ):
            _fail("financial_evidence_decision_type_invalid")

        disposition = decision.disposition
        reason_code = decision.reason_code
        coverage = self._coverage(
            disposition=disposition,
            reason_code=reason_code,
            bound_refs=bound_refs,
        )
        terminal_ids = [
            item["input_id"] for item in typed_inputs
        ] + [
            item["unclassified_input_id"] for item in unclassified_inputs
        ]
        artifact_id = "finset_" + _sha256_json(
            {
                "schema_version": FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION,
                "registry_hash": self.registry.registry_hash,
                "source_package_integrity_hash": (
                    self.source_package.integrity_hash
                ),
                "terminal_disposition": disposition,
                "terminal_ids": terminal_ids,
                "coverage_id": coverage["coverage_id"],
            }
        )[:32]
        payload: dict[str, Any] = {
            "schema_version": FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION,
            "materialization_policy_version": (
                MATERIALIZATION_POLICY_VERSION
            ),
            "artifact_id": artifact_id,
            "registry": {
                "registry_id": REGISTRY_ID,
                "registry_version": self.registry.registry_version,
                "registry_hash": self.registry.registry_hash,
            },
            "source_package": {
                "schema_version": self.source_package.schema_version,
                "package_ref": self.source_package.package_ref,
                "integrity_hash": self.source_package.integrity_hash,
                "source_scope_ref": self.source_package.source_scope_ref,
                "source_family_id": self.source_package.source_family_id,
                "source_values_total": len(
                    self.source_package.source_values
                ),
                "source_value_refs_hash": _sha256_json(
                    [
                        item.source_value_ref
                        for item in self.source_package.source_values
                    ]
                ),
            },
            "terminal_disposition": disposition,
            "typed_inputs": typed_inputs,
            "unclassified_inputs": unclassified_inputs,
            "coverage": coverage,
            "execution": {
                "execution_ref": self.execution_metadata.execution_ref,
                "decision_validation_ref": (
                    self.execution_metadata.decision_validation_ref
                ),
                "decision_schema_version": (
                    validated_decision.decision_schema_version
                ),
                "decision_schema_hash": (
                    validated_decision.decision_schema_hash
                ),
            },
        }
        payload["integrity_hash"] = _sha256_json(payload)
        validate_financial_evidence_inputs(
            payload=payload,
            registry=self.registry,
        )
        return payload

    def _validate_authorities(
        self,
        validated_decision: FinancialEvidenceValidatedDecision,
    ) -> None:
        if (
            validated_decision.schema_version
            != VALIDATED_DECISION_SCHEMA_VERSION
            or validated_decision.decision_schema_version
            != DECISION_SCHEMA_VERSION
            or not _SHA256_RE.fullmatch(
                validated_decision.decision_schema_hash
            )
        ):
            _fail("financial_evidence_validated_decision_invalid")
        if (
            validated_decision.registry_version
            != self.registry.registry_version
            or validated_decision.registry_hash
            != self.registry.registry_hash
        ):
            _fail("financial_evidence_registry_authority_mismatch")
        if (
            validated_decision.source_scope_ref
            != self.source_package.source_scope_ref
            or validated_decision.source_family_id
            != self.source_package.source_family_id
        ):
            _fail("financial_evidence_source_package_scope_mismatch")
        source_values = {
            item.source_value_ref: item
            for item in self.source_package.source_values
        }
        if set(validated_decision.candidate_refs) != set(source_values):
            _fail("financial_evidence_source_candidate_set_mismatch")
        source_authority_hash = _sha256_json(
            [
                {
                    "source_value_ref": item.source_value_ref,
                    "source_ref": item.source_ref,
                    "value_type": item.value_type,
                }
                for item in self.source_package.source_values
            ]
        )
        if (
            validated_decision.candidate_authority_hash
            != source_authority_hash
        ):
            _fail("financial_evidence_source_candidate_authority_mismatch")

    def _materialize_typed(
        self,
        decision: TypedFinancialInputDecision,
    ) -> dict[str, Any]:
        declaration = self.registry.get(decision.input_type_id)
        values = self._bound_values(decision.value_bindings)
        bound_roles = {item["role_id"] for item in values}
        if not set(declaration.required_roles) <= bound_roles:
            _fail("financial_evidence_required_role_missing")
        identity_roles = tuple(declaration.identity_policy.identity_roles)
        identity_values = [
            item for item in values if item["role_id"] in identity_roles
        ]
        evidence_refs = _evidence_refs(
            values,
            self.source_package.source_evidence_refs,
        )
        input_id = "finin_" + _sha256_json(
            {
                "registry_hash": self.registry.registry_hash,
                "input_type_id": decision.input_type_id,
                "source_scope_ref": self.source_package.source_scope_ref,
                "identity_values": [
                    {
                        "role_id": item["role_id"],
                        "source_value_ref": item["source_value_ref"],
                        "normalized_comparison_value": item[
                            "normalized_comparison_value"
                        ],
                    }
                    for item in identity_values
                ],
                "source_evidence_refs": evidence_refs,
            }
        )[:32]
        payload: dict[str, Any] = {
            "input_id": input_id,
            "input_type_id": decision.input_type_id,
            "semantic_class": declaration.semantic_class,
            "registry_version": self.registry.registry_version,
            "registry_hash": self.registry.registry_hash,
            "materialization_profile_id": (
                declaration.materialization_profile_id
            ),
            "validation_profile_id": declaration.validation_profile_id,
            "source_scope_ref": self.source_package.source_scope_ref,
            "source_values": values,
            "normalized_comparison_values": {
                item["source_value_ref"]: item[
                    "normalized_comparison_value"
                ]
                for item in values
            },
            "date_period": _role_projection(values, _TEMPORAL_ROLES),
            "currency_unit": _role_projection(
                values,
                _MEASUREMENT_ROLES,
            ),
            "source_sign_policy": declaration.source_sign_policy,
            "source_sign_by_value_ref": {
                item["source_value_ref"]: item["source_sign"]
                for item in values
                if item["source_sign"] != "not_applicable"
            },
            "identity_policy": {
                "identity_roles": list(identity_roles),
                "include_source_scope": (
                    declaration.identity_policy.include_source_scope
                ),
                "include_source_evidence_refs": (
                    declaration.identity_policy.include_source_evidence_refs
                ),
            },
            "source_evidence_refs": evidence_refs,
            "lineage": _unique_lineage(values),
            "source_ownership": self._source_ownership(),
            "completeness": self.source_package.completeness,
            "restriction_codes": list(
                self.source_package.restriction_codes
            ),
            "issue_refs": list(self.source_package.issue_refs),
        }
        payload["integrity_hash"] = _sha256_json(payload)
        return payload

    def _materialize_unclassified(
        self,
        decision: UnclassifiedFinancialInputDecision,
    ) -> dict[str, Any]:
        values = self._bound_values(decision.value_bindings)
        bound_refs = {item["source_value_ref"] for item in values}
        package_refs = {
            item.source_value_ref for item in self.source_package.source_values
        }
        if bound_refs != package_refs:
            _fail("financial_evidence_unclassified_value_loss")
        evidence_refs = _evidence_refs(
            values,
            self.source_package.source_evidence_refs,
        )
        unclassified_id = "finun_" + _sha256_json(
            {
                "registry_hash": self.registry.registry_hash,
                "source_scope_ref": self.source_package.source_scope_ref,
                "source_values": [
                    {
                        "role_id": item["role_id"],
                        "source_value_ref": item["source_value_ref"],
                        "normalized_comparison_value": item[
                            "normalized_comparison_value"
                        ],
                    }
                    for item in values
                ],
                "source_evidence_refs": evidence_refs,
            }
        )[:32]
        payload: dict[str, Any] = {
            "unclassified_input_id": unclassified_id,
            "registry_version": self.registry.registry_version,
            "registry_hash": self.registry.registry_hash,
            "registry_gap": True,
            "gap_reason_code": decision.reason_code,
            "typed_input_published": False,
            "source_scope_ref": self.source_package.source_scope_ref,
            "source_values": values,
            "normalized_comparison_values": {
                item["source_value_ref"]: item[
                    "normalized_comparison_value"
                ]
                for item in values
            },
            "date_period": _role_projection(values, _TEMPORAL_ROLES),
            "currency_unit": _role_projection(
                values,
                _MEASUREMENT_ROLES,
            ),
            "source_sign_by_value_ref": {
                item["source_value_ref"]: item["source_sign"]
                for item in values
                if item["source_sign"] != "not_applicable"
            },
            "source_evidence_refs": evidence_refs,
            "lineage": _unique_lineage(values),
            "source_ownership": self._source_ownership(),
            "completeness": self.source_package.completeness,
            "restriction_codes": list(
                self.source_package.restriction_codes
            ),
            "issue_refs": list(self.source_package.issue_refs),
        }
        payload["integrity_hash"] = _sha256_json(payload)
        return payload

    def _bound_values(self, bindings) -> list[dict[str, Any]]:
        source_values = {
            item.source_value_ref: item
            for item in self.source_package.source_values
        }
        result = []
        for binding in sorted(
            bindings,
            key=lambda item: (item.role_id, item.source_value_ref),
        ):
            source_value = source_values.get(binding.source_value_ref)
            if source_value is None:
                _fail("financial_evidence_binding_source_value_missing")
            normalized = _normalize_comparison_value(
                literal_value=source_value.literal_value,
                value_type=source_value.value_type,
            )
            result.append(
                {
                    "role_id": binding.role_id,
                    "source_value_ref": source_value.source_value_ref,
                    "source_ref": source_value.source_ref,
                    "value_type": source_value.value_type,
                    "literal_value": source_value.literal_value,
                    "normalized_comparison_value": normalized,
                    "source_sign": _source_sign(
                        literal_value=source_value.literal_value,
                        value_type=source_value.value_type,
                    ),
                    "source_evidence_refs": list(
                        source_value.source_evidence_refs
                    ),
                    "lineage": asdict(source_value.lineage),
                }
            )
        return result

    def _source_ownership(self) -> dict[str, str]:
        return {
            "normalization_run_ref": (
                self.source_package.normalization_run_ref
            ),
            "document_ref": self.source_package.document_ref,
            "source_package_ref": self.source_package.package_ref,
            "source_scope_ref": self.source_package.source_scope_ref,
        }

    def _coverage(
        self,
        *,
        disposition: str,
        reason_code: str,
        bound_refs: tuple[str, ...],
    ) -> dict[str, Any]:
        coverage_id = "finclose_" + _sha256_json(
            {
                "registry_hash": self.registry.registry_hash,
                "source_package_integrity_hash": (
                    self.source_package.integrity_hash
                ),
                "source_scope_ref": self.source_package.source_scope_ref,
                "terminal_disposition": disposition,
                "reason_code": reason_code,
                "bound_source_value_refs": sorted(bound_refs),
            }
        )[:32]
        return {
            "coverage_id": coverage_id,
            "source_scope_ref": self.source_package.source_scope_ref,
            "scope_accounted": True,
            "terminal_disposition": disposition,
            "reason_code": reason_code,
            "candidate_refs_total": len(self.source_package.source_values),
            "bound_source_value_refs": sorted(bound_refs),
        }


def validate_financial_evidence_inputs(
    *,
    payload: dict[str, Any],
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> None:
    expected_keys = {
        "schema_version",
        "materialization_policy_version",
        "artifact_id",
        "registry",
        "source_package",
        "terminal_disposition",
        "typed_inputs",
        "unclassified_inputs",
        "coverage",
        "execution",
        "integrity_hash",
    }
    if not isinstance(payload, dict) or set(payload) != expected_keys:
        _fail("financial_evidence_inputs_shape_invalid")
    if (
        payload["schema_version"]
        != FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION
        or payload["materialization_policy_version"]
        != MATERIALIZATION_POLICY_VERSION
    ):
        _fail("financial_evidence_inputs_version_invalid")
    registry_payload = payload["registry"]
    if registry_payload != {
        "registry_id": REGISTRY_ID,
        "registry_version": registry.registry_version,
        "registry_hash": registry.registry_hash,
    }:
        _fail("financial_evidence_inputs_registry_invalid")
    integrity_hash = payload["integrity_hash"]
    unsigned = dict(payload)
    unsigned.pop("integrity_hash")
    if integrity_hash != _sha256_json(unsigned):
        _fail("financial_evidence_inputs_integrity_invalid")
    typed = payload["typed_inputs"]
    unclassified = payload["unclassified_inputs"]
    disposition = payload["terminal_disposition"]
    if not isinstance(typed, list) or not isinstance(unclassified, list):
        _fail("financial_evidence_inputs_terminal_shape_invalid")
    expected_counts = {
        "typed_input": (1, 0),
        "unclassified_financial_input": (0, 1),
        "no_financial_input": (0, 0),
        "unsupported": (0, 0),
    }
    if (
        disposition not in expected_counts
        or (len(typed), len(unclassified))
        != expected_counts[disposition]
    ):
        _fail("financial_evidence_inputs_terminal_shape_invalid")
    for item in typed:
        _validate_terminal_integrity(item, "input_id", "finin_")
        _validate_typed_input(item, registry)
    for item in unclassified:
        _validate_terminal_integrity(
            item,
            "unclassified_input_id",
            "finun_",
        )
        _validate_unclassified_input(item, registry)
    coverage = payload["coverage"]
    if (
        not isinstance(coverage, dict)
        or set(coverage)
        != {
            "coverage_id",
            "source_scope_ref",
            "scope_accounted",
            "terminal_disposition",
            "reason_code",
            "candidate_refs_total",
            "bound_source_value_refs",
        }
        or coverage.get("scope_accounted") is not True
        or coverage.get("terminal_disposition") != disposition
        or not str(coverage.get("coverage_id") or "").startswith(
            "finclose_"
        )
    ):
        _fail("financial_evidence_coverage_invalid")
    terminal_ids = [
        item["input_id"] for item in typed
    ] + [
        item["unclassified_input_id"] for item in unclassified
    ]
    source_package = payload["source_package"]
    if not isinstance(source_package, dict) or set(source_package) != {
        "schema_version",
        "package_ref",
        "integrity_hash",
        "source_scope_ref",
        "source_family_id",
        "source_values_total",
        "source_value_refs_hash",
    }:
        _fail("financial_evidence_inputs_source_package_invalid")
    for item in [*typed, *unclassified]:
        ownership = item["source_ownership"]
        if (
            item["source_scope_ref"]
            != source_package["source_scope_ref"]
            or not isinstance(ownership, dict)
            or ownership.get("source_package_ref")
            != source_package["package_ref"]
            or ownership.get("source_scope_ref")
            != source_package["source_scope_ref"]
        ):
            _fail("financial_evidence_inputs_source_ownership_invalid")
    if coverage["source_scope_ref"] != source_package["source_scope_ref"]:
        _fail("financial_evidence_coverage_scope_invalid")
    if (
        coverage["candidate_refs_total"]
        != source_package["source_values_total"]
        or not _SHA256_RE.fullmatch(
            source_package["source_value_refs_hash"]
        )
    ):
        _fail("financial_evidence_coverage_candidate_count_invalid")
    expected_bound_refs = sorted(
        value["source_value_ref"]
        for item in [*typed, *unclassified]
        for value in item["source_values"]
    )
    if coverage["bound_source_value_refs"] != expected_bound_refs:
        _fail("financial_evidence_coverage_bound_refs_invalid")
    if (
        disposition == "unclassified_financial_input"
        and _sha256_json(expected_bound_refs)
        != source_package["source_value_refs_hash"]
    ):
        _fail("financial_evidence_unclassified_value_loss")
    expected_coverage_id = "finclose_" + _sha256_json(
        {
            "registry_hash": registry.registry_hash,
            "source_package_integrity_hash": source_package[
                "integrity_hash"
            ],
            "source_scope_ref": source_package["source_scope_ref"],
            "terminal_disposition": disposition,
            "reason_code": coverage["reason_code"],
            "bound_source_value_refs": coverage[
                "bound_source_value_refs"
            ],
        }
    )[:32]
    if coverage["coverage_id"] != expected_coverage_id:
        _fail("financial_evidence_coverage_id_invalid")
    expected_artifact_id = "finset_" + _sha256_json(
        {
            "schema_version": FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION,
            "registry_hash": registry.registry_hash,
            "source_package_integrity_hash": source_package[
                "integrity_hash"
            ],
            "terminal_disposition": disposition,
            "terminal_ids": terminal_ids,
            "coverage_id": coverage["coverage_id"],
        }
    )[:32]
    if payload["artifact_id"] != expected_artifact_id:
        _fail("financial_evidence_inputs_artifact_id_invalid")
    execution = payload["execution"]
    if not isinstance(execution, dict) or set(execution) != {
        "execution_ref",
        "decision_validation_ref",
        "decision_schema_version",
        "decision_schema_hash",
    }:
        _fail("financial_evidence_inputs_execution_invalid")
    if (
        execution["decision_schema_version"] != DECISION_SCHEMA_VERSION
        or not _SHA256_RE.fullmatch(execution["decision_schema_hash"])
    ):
        _fail("financial_evidence_inputs_execution_invalid")
    if _contains_gate3_field(payload):
        _fail("financial_evidence_inputs_gate3_field_forbidden")


def _normalize_authoritative_source_value(
    value: FinancialEvidenceAuthoritativeSourceValue,
    *,
    document_ref: str,
) -> FinancialEvidenceAuthoritativeSourceValue:
    _identifier(value.source_value_ref, "source_value_ref")
    _identifier(value.source_ref, "source_ref")
    if (
        not isinstance(value.literal_value, str)
        or not value.literal_value
        or len(value.literal_value) > _MAX_LITERAL_LENGTH
    ):
        _fail("financial_evidence_literal_value_invalid")
    _normalize_comparison_value(
        literal_value=value.literal_value,
        value_type=value.value_type,
    )
    evidence_refs = _sorted_identifiers(
        value.source_evidence_refs,
        field="source_evidence_ref",
        required=True,
    )
    lineage = value.lineage
    if lineage.document_ref != document_ref:
        _fail("financial_evidence_lineage_document_mismatch")
    _identifier(lineage.document_ref, "lineage_document_ref")
    locators = (
        lineage.page_ref,
        lineage.table_ref,
        lineage.row_ref,
        lineage.cell_ref,
        lineage.text_segment_ref,
    )
    if not any(locators):
        _fail("financial_evidence_lineage_locator_missing")
    for locator in locators:
        if locator is not None:
            _identifier(locator, "lineage_locator")
    return FinancialEvidenceAuthoritativeSourceValue(
        source_value_ref=value.source_value_ref,
        source_ref=value.source_ref,
        value_type=value.value_type,
        literal_value=value.literal_value,
        source_evidence_refs=evidence_refs,
        lineage=lineage,
    )


def _validate_source_package_integrity(
    package: Gate2FinancialEvidenceSourcePackage,
) -> None:
    if package.schema_version != SOURCE_PACKAGE_SCHEMA_VERSION:
        _fail("financial_evidence_source_package_version_invalid")
    payload = {
        "schema_version": package.schema_version,
        "package_ref": package.package_ref,
        "normalization_run_ref": package.normalization_run_ref,
        "document_ref": package.document_ref,
        "source_scope_ref": package.source_scope_ref,
        "source_family_id": package.source_family_id,
        "source_values": [
            _source_value_payload(item) for item in package.source_values
        ],
        "source_evidence_refs": list(package.source_evidence_refs),
        "completeness": package.completeness,
        "restriction_codes": list(package.restriction_codes),
        "issue_refs": list(package.issue_refs),
    }
    if package.integrity_hash != _sha256_json(payload):
        _fail("financial_evidence_source_package_integrity_invalid")


def _source_value_payload(
    value: FinancialEvidenceAuthoritativeSourceValue,
) -> dict[str, Any]:
    return {
        "source_value_ref": value.source_value_ref,
        "source_ref": value.source_ref,
        "value_type": value.value_type,
        "literal_value": value.literal_value,
        "source_evidence_refs": list(value.source_evidence_refs),
        "lineage": asdict(value.lineage),
    }


def _normalize_comparison_value(
    *,
    literal_value: str,
    value_type: str,
) -> str:
    if value_type == "source_decimal":
        try:
            number = Decimal(literal_value)
        except InvalidOperation:
            _fail("financial_evidence_decimal_invalid")
        if not number.is_finite():
            _fail("financial_evidence_decimal_invalid")
        if number == 0:
            return "0"
        return format(number.normalize(), "f")
    if value_type == "source_integer":
        try:
            return str(int(literal_value))
        except ValueError:
            _fail("financial_evidence_integer_invalid")
    if value_type == "source_date":
        try:
            return date.fromisoformat(literal_value).isoformat()
        except ValueError:
            _fail("financial_evidence_date_invalid")
    normalized = " ".join(
        unicodedata.normalize("NFKC", literal_value).split()
    )
    if value_type == "source_currency":
        return normalized.upper()
    if value_type in {
        "source_period",
        "source_reference",
        "source_text",
        "source_unit",
    }:
        return normalized.casefold()
    _fail("financial_evidence_value_type_invalid")


def _source_sign(*, literal_value: str, value_type: str) -> str:
    if value_type not in {"source_decimal", "source_integer"}:
        return "not_applicable"
    number = Decimal(literal_value)
    if number < 0:
        return "negative"
    if number > 0:
        return "positive"
    return "zero"


def _role_projection(
    values: list[dict[str, Any]],
    roles: frozenset[str],
) -> dict[str, str]:
    return {
        item["role_id"]: item["normalized_comparison_value"]
        for item in values
        if item["role_id"] in roles
    }


def _evidence_refs(
    values: list[dict[str, Any]],
    package_refs: tuple[str, ...],
) -> list[str]:
    return sorted(
        set(package_refs).union(
            *(
                set(item["source_evidence_refs"])
                for item in values
            )
        )
    )


def _unique_lineage(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_hash = {
        _sha256_json(item["lineage"]): item["lineage"] for item in values
    }
    return [by_hash[key] for key in sorted(by_hash)]


def _validate_terminal_integrity(
    item: Any,
    id_field: str,
    id_prefix: str,
) -> None:
    if not isinstance(item, dict):
        _fail("financial_evidence_terminal_object_invalid")
    integrity_hash = item.get("integrity_hash")
    unsigned = dict(item)
    unsigned.pop("integrity_hash", None)
    if integrity_hash != _sha256_json(unsigned):
        _fail("financial_evidence_terminal_integrity_invalid")
    if not str(item.get(id_field) or "").startswith(id_prefix):
        _fail("financial_evidence_terminal_id_invalid")


def _validate_typed_input(
    item: dict[str, Any],
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> None:
    expected_keys = {
        "input_id",
        "input_type_id",
        "semantic_class",
        "registry_version",
        "registry_hash",
        "materialization_profile_id",
        "validation_profile_id",
        "source_scope_ref",
        "source_values",
        "normalized_comparison_values",
        "date_period",
        "currency_unit",
        "source_sign_policy",
        "source_sign_by_value_ref",
        "identity_policy",
        "source_evidence_refs",
        "lineage",
        "source_ownership",
        "completeness",
        "restriction_codes",
        "issue_refs",
        "integrity_hash",
    }
    if set(item) != expected_keys:
        _fail("financial_evidence_typed_input_shape_invalid")
    declaration = registry.get(item["input_type_id"])
    if (
        item["semantic_class"] != declaration.semantic_class
        or item["registry_version"] != registry.registry_version
        or item["registry_hash"] != registry.registry_hash
        or item["materialization_profile_id"]
        != declaration.materialization_profile_id
        or item["validation_profile_id"]
        != declaration.validation_profile_id
        or item["source_sign_policy"] != declaration.source_sign_policy
    ):
        _fail("financial_evidence_typed_input_registry_mismatch")
    values = _validate_materialized_values(item["source_values"])
    _validate_materialized_projections(item, values)
    bound_roles = {value["role_id"] for value in values}
    if (
        not set(declaration.required_roles) <= bound_roles
        or not bound_roles
        <= set(declaration.required_roles + declaration.optional_roles)
    ):
        _fail("financial_evidence_typed_input_roles_invalid")
    identity_policy = item["identity_policy"]
    if identity_policy != {
        "identity_roles": list(
            declaration.identity_policy.identity_roles
        ),
        "include_source_scope": (
            declaration.identity_policy.include_source_scope
        ),
        "include_source_evidence_refs": (
            declaration.identity_policy.include_source_evidence_refs
        ),
    }:
        _fail("financial_evidence_typed_input_identity_policy_invalid")
    identity_roles = set(declaration.identity_policy.identity_roles)
    expected_id = "finin_" + _sha256_json(
        {
            "registry_hash": registry.registry_hash,
            "input_type_id": item["input_type_id"],
            "source_scope_ref": item["source_scope_ref"],
            "identity_values": [
                {
                    "role_id": value["role_id"],
                    "source_value_ref": value["source_value_ref"],
                    "normalized_comparison_value": value[
                        "normalized_comparison_value"
                    ],
                }
                for value in values
                if value["role_id"] in identity_roles
            ],
            "source_evidence_refs": item["source_evidence_refs"],
        }
    )[:32]
    if item["input_id"] != expected_id:
        _fail("financial_evidence_typed_input_id_invalid")


def _validate_unclassified_input(
    item: dict[str, Any],
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> None:
    expected_keys = {
        "unclassified_input_id",
        "registry_version",
        "registry_hash",
        "registry_gap",
        "gap_reason_code",
        "typed_input_published",
        "source_scope_ref",
        "source_values",
        "normalized_comparison_values",
        "date_period",
        "currency_unit",
        "source_sign_by_value_ref",
        "source_evidence_refs",
        "lineage",
        "source_ownership",
        "completeness",
        "restriction_codes",
        "issue_refs",
        "integrity_hash",
    }
    if set(item) != expected_keys:
        _fail("financial_evidence_unclassified_shape_invalid")
    if (
        item["registry_version"] != registry.registry_version
        or item["registry_hash"] != registry.registry_hash
        or item["registry_gap"] is not True
        or item["typed_input_published"] is not False
    ):
        _fail("financial_evidence_unclassified_state_invalid")
    values = _validate_materialized_values(item["source_values"])
    _validate_materialized_projections(item, values)
    expected_id = "finun_" + _sha256_json(
        {
            "registry_hash": registry.registry_hash,
            "source_scope_ref": item["source_scope_ref"],
            "source_values": [
                {
                    "role_id": value["role_id"],
                    "source_value_ref": value["source_value_ref"],
                    "normalized_comparison_value": value[
                        "normalized_comparison_value"
                    ],
                }
                for value in values
            ],
            "source_evidence_refs": item["source_evidence_refs"],
        }
    )[:32]
    if item["unclassified_input_id"] != expected_id:
        _fail("financial_evidence_unclassified_id_invalid")


def _validate_materialized_values(
    values: Any,
) -> list[dict[str, Any]]:
    expected_keys = {
        "role_id",
        "source_value_ref",
        "source_ref",
        "value_type",
        "literal_value",
        "normalized_comparison_value",
        "source_sign",
        "source_evidence_refs",
        "lineage",
    }
    if not isinstance(values, list) or not values:
        _fail("financial_evidence_source_values_invalid")
    previous_key: tuple[str, str] | None = None
    for value in values:
        if not isinstance(value, dict) or set(value) != expected_keys:
            _fail("financial_evidence_source_value_shape_invalid")
        key = (value["role_id"], value["source_value_ref"])
        if previous_key is not None and key <= previous_key:
            _fail("financial_evidence_source_values_order_invalid")
        previous_key = key
        expected_normalized = _normalize_comparison_value(
            literal_value=value["literal_value"],
            value_type=value["value_type"],
        )
        if value["normalized_comparison_value"] != expected_normalized:
            _fail("financial_evidence_comparison_value_invalid")
        if value["source_sign"] != _source_sign(
            literal_value=value["literal_value"],
            value_type=value["value_type"],
        ):
            _fail("financial_evidence_source_sign_invalid")
        lineage = value["lineage"]
        if not isinstance(lineage, dict) or set(lineage) != {
            "document_ref",
            "page_ref",
            "table_ref",
            "row_ref",
            "cell_ref",
            "text_segment_ref",
        }:
            _fail("financial_evidence_lineage_shape_invalid")
    return values


def _validate_materialized_projections(
    item: dict[str, Any],
    values: list[dict[str, Any]],
) -> None:
    if item["normalized_comparison_values"] != {
        value["source_value_ref"]: value["normalized_comparison_value"]
        for value in values
    }:
        _fail("financial_evidence_comparison_projection_invalid")
    if item["date_period"] != _role_projection(values, _TEMPORAL_ROLES):
        _fail("financial_evidence_date_period_projection_invalid")
    if item["currency_unit"] != _role_projection(
        values,
        _MEASUREMENT_ROLES,
    ):
        _fail("financial_evidence_currency_unit_projection_invalid")
    if item["source_sign_by_value_ref"] != {
        value["source_value_ref"]: value["source_sign"]
        for value in values
        if value["source_sign"] != "not_applicable"
    }:
        _fail("financial_evidence_source_sign_projection_invalid")
    evidence_refs = item["source_evidence_refs"]
    if (
        not isinstance(evidence_refs, list)
        or evidence_refs != sorted(set(evidence_refs))
        or any(
            not set(value["source_evidence_refs"]) <= set(evidence_refs)
            for value in values
        )
    ):
        _fail("financial_evidence_source_evidence_refs_invalid")
    if item["lineage"] != _unique_lineage(values):
        _fail("financial_evidence_lineage_projection_invalid")
    if item["completeness"] not in COMPLETENESS_VALUES:
        _fail("financial_evidence_completeness_invalid")
    for field in ("restriction_codes", "issue_refs"):
        field_values = item[field]
        if (
            not isinstance(field_values, list)
            or field_values != sorted(set(field_values))
        ):
            _fail(f"financial_evidence_{field}_invalid")


def _contains_gate3_field(value: Any) -> bool:
    forbidden = {
        "answer_instruction",
        "gate3",
        "ledger_candidate",
        "relevance",
        "tax_calculation",
    }
    if isinstance(value, dict):
        return bool(set(value) & forbidden) or any(
            _contains_gate3_field(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_gate3_field(item) for item in value)
    return False


def _sorted_identifiers(
    values: tuple[str, ...],
    *,
    field: str,
    required: bool = False,
) -> tuple[str, ...]:
    if required and not values:
        _fail(f"financial_evidence_{field}_missing")
    if len(values) != len(set(values)):
        _fail(f"financial_evidence_{field}_duplicate")
    for value in values:
        _identifier(value, field)
    return tuple(sorted(values))


def _identifier(value: Any, field: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 240
        or not _IDENTIFIER_RE.fullmatch(value)
    ):
        _fail(f"financial_evidence_{field}_invalid")


def _sha256_json(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _fail(code: str) -> None:
    raise Gate2FinancialEvidenceMaterializationError(code)
