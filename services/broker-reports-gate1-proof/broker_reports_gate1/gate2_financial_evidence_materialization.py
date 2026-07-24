from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .gate2_financial_evidence_decision import (
    DECISION_SCHEMA_VERSION,
    Gate2FinancialEvidenceDecisionContract,
    NoFinancialInputDecision,
    TypedFinancialInputDecision,
    UnclassifiedFinancialInputDecision,
    UnsupportedFinancialInputDecision,
)
from .gate2_financial_evidence_materialization_contracts import (
    FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION,
    MATERIALIZATION_POLICY_VERSION,
    MEASUREMENT_ROLES,
    SHA256_RE,
    SOURCE_PACKAGE_SCHEMA_VERSION,
    TEMPORAL_ROLES,
    VALIDATED_DECISION_SCHEMA_VERSION,
    FinancialEvidenceAuthoritativeSourceValue,
    FinancialEvidenceExecutionMetadata,
    FinancialEvidenceSourceLineage,
    FinancialEvidenceValidatedDecision,
    Gate2FinancialEvidenceMaterializationError,
    Gate2FinancialEvidenceSourcePackage,
    evidence_refs,
    fail,
    identifier,
    normalize_comparison_value,
    role_projection,
    sha256_json,
    source_sign,
    unique_lineage,
)
from .gate2_financial_evidence_materialization_validation import (
    validate_financial_evidence_inputs,
)
from .gate2_financial_evidence_registry import (
    REGISTRY_ID,
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_evidence_source_package import (
    Gate2FinancialEvidenceSourcePackageFactory,
    validate_source_package_integrity,
)


FACTORY_REQUIRED = (
    "Gate2FinancialEvidenceMaterializerFactory.create and materialize are "
    "the only production financial evidence materialization path"
)
FORBIDDEN = (
    "Models, prompts and providers must not mint input IDs, provenance, "
    "normalized values, ownership, completeness, integrity or Gate 3 fields"
)

__all__ = [
    "FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION",
    "MATERIALIZATION_POLICY_VERSION",
    "SOURCE_PACKAGE_SCHEMA_VERSION",
    "VALIDATED_DECISION_SCHEMA_VERSION",
    "FinancialEvidenceAuthoritativeSourceValue",
    "FinancialEvidenceExecutionMetadata",
    "FinancialEvidenceSourceLineage",
    "FinancialEvidenceValidatedDecision",
    "Gate2FinancialEvidenceMaterializationError",
    "Gate2FinancialEvidenceMaterializer",
    "Gate2FinancialEvidenceMaterializerFactory",
    "Gate2FinancialEvidenceSourcePackage",
    "Gate2FinancialEvidenceSourcePackageFactory",
    "Gate2FinancialEvidenceValidatedDecisionFactory",
    "validate_financial_evidence_inputs",
]


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
        candidates = self.contract.package.candidates
        return FinancialEvidenceValidatedDecision(
            schema_version=VALIDATED_DECISION_SCHEMA_VERSION,
            decision_schema_version=DECISION_SCHEMA_VERSION,
            decision_schema_hash=self.contract.canonical_schema_hash(),
            registry_version=self.contract.registry.registry_version,
            registry_hash=self.contract.registry.registry_hash,
            source_scope_ref=self.contract.package.source_scope_ref,
            source_family_id=self.contract.package.source_family_id,
            candidate_refs=tuple(
                item.source_value_ref for item in candidates
            ),
            candidate_authority_hash=sha256_json(
                [
                    {
                        "source_value_ref": item.source_value_ref,
                        "source_ref": item.source_ref,
                        "value_type": item.value_type,
                    }
                    for item in candidates
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
        validate_source_package_integrity(self.source_package)
        identifier(
            self.execution_metadata.execution_ref,
            "execution_ref",
        )
        identifier(
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
            fail("financial_evidence_decision_type_invalid")

        disposition = decision.disposition
        coverage = self._coverage(
            disposition=disposition,
            reason_code=decision.reason_code,
            bound_refs=bound_refs,
        )
        terminal_ids = [
            item["input_id"] for item in typed_inputs
        ] + [
            item["unclassified_input_id"] for item in unclassified_inputs
        ]
        artifact_id = "finset_" + sha256_json(
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
            "source_package": self._source_package_projection(),
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
        payload["integrity_hash"] = sha256_json(payload)
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
            or not SHA256_RE.fullmatch(
                validated_decision.decision_schema_hash
            )
        ):
            fail("financial_evidence_validated_decision_invalid")
        if (
            validated_decision.registry_version
            != self.registry.registry_version
            or validated_decision.registry_hash
            != self.registry.registry_hash
        ):
            fail("financial_evidence_registry_authority_mismatch")
        if (
            validated_decision.source_scope_ref
            != self.source_package.source_scope_ref
            or validated_decision.source_family_id
            != self.source_package.source_family_id
        ):
            fail("financial_evidence_source_package_scope_mismatch")
        source_values = {
            item.source_value_ref: item
            for item in self.source_package.source_values
        }
        if set(validated_decision.candidate_refs) != set(source_values):
            fail("financial_evidence_source_candidate_set_mismatch")
        source_authority_hash = sha256_json(
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
            fail("financial_evidence_source_candidate_authority_mismatch")

    def _materialize_typed(
        self,
        decision: TypedFinancialInputDecision,
    ) -> dict[str, Any]:
        declaration = self.registry.get(decision.input_type_id)
        values = self._bound_values(decision.value_bindings)
        if not set(declaration.required_roles) <= {
            item["role_id"] for item in values
        }:
            fail("financial_evidence_required_role_missing")
        identity_roles = tuple(declaration.identity_policy.identity_roles)
        evidence = evidence_refs(
            values,
            self.source_package.source_evidence_refs,
        )
        input_id = "finin_" + sha256_json(
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
                    for item in values
                    if item["role_id"] in identity_roles
                ],
                "source_evidence_refs": evidence,
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
            **self._value_projections(values),
            "source_sign_policy": declaration.source_sign_policy,
            "identity_policy": {
                "identity_roles": list(identity_roles),
                "include_source_scope": (
                    declaration.identity_policy.include_source_scope
                ),
                "include_source_evidence_refs": (
                    declaration.identity_policy.include_source_evidence_refs
                ),
            },
            **self._source_context(values, evidence),
        }
        payload["integrity_hash"] = sha256_json(payload)
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
            fail("financial_evidence_unclassified_value_loss")
        evidence = evidence_refs(
            values,
            self.source_package.source_evidence_refs,
        )
        unclassified_id = "finun_" + sha256_json(
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
                "source_evidence_refs": evidence,
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
            **self._value_projections(values),
            **self._source_context(values, evidence),
        }
        payload["integrity_hash"] = sha256_json(payload)
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
                fail("financial_evidence_binding_source_value_missing")
            normalized = normalize_comparison_value(
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
                    "source_sign": source_sign(
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

    def _value_projections(
        self,
        values: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "source_values": values,
            "normalized_comparison_values": {
                item["source_value_ref"]: item[
                    "normalized_comparison_value"
                ]
                for item in values
            },
            "date_period": role_projection(values, TEMPORAL_ROLES),
            "currency_unit": role_projection(
                values,
                MEASUREMENT_ROLES,
            ),
            "source_sign_by_value_ref": {
                item["source_value_ref"]: item["source_sign"]
                for item in values
                if item["source_sign"] != "not_applicable"
            },
        }

    def _source_context(
        self,
        values: list[dict[str, Any]],
        evidence: list[str],
    ) -> dict[str, Any]:
        return {
            "source_evidence_refs": evidence,
            "lineage": unique_lineage(values),
            "source_ownership": {
                "normalization_run_ref": (
                    self.source_package.normalization_run_ref
                ),
                "document_ref": self.source_package.document_ref,
                "source_package_ref": self.source_package.package_ref,
                "source_scope_ref": self.source_package.source_scope_ref,
            },
            "completeness": self.source_package.completeness,
            "restriction_codes": list(
                self.source_package.restriction_codes
            ),
            "issue_refs": list(self.source_package.issue_refs),
        }

    def _source_package_projection(self) -> dict[str, Any]:
        return {
            "schema_version": self.source_package.schema_version,
            "package_ref": self.source_package.package_ref,
            "integrity_hash": self.source_package.integrity_hash,
            "source_scope_ref": self.source_package.source_scope_ref,
            "source_family_id": self.source_package.source_family_id,
            "source_values_total": len(self.source_package.source_values),
            "source_value_refs_hash": sha256_json(
                [
                    item.source_value_ref
                    for item in self.source_package.source_values
                ]
            ),
        }

    def _coverage(
        self,
        *,
        disposition: str,
        reason_code: str,
        bound_refs: tuple[str, ...],
    ) -> dict[str, Any]:
        coverage_id = "finclose_" + sha256_json(
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
