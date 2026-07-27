from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .gate2_financial_evidence_materialization import (
    FinancialEvidenceExecutionMetadata,
    Gate2FinancialEvidenceMaterializationError,
    Gate2FinancialEvidenceMaterializerFactory,
    Gate2FinancialEvidenceSourcePackage,
)
from .gate2_financial_evidence_materialization_contracts import sha256_json
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_semantic_v6_bundle import (
    Gate2FinancialEvidenceBundle,
)
from .gate2_financial_semantic_v6_candidate_compiler import (
    Gate2FinancialCandidateCompilation,
)
from .gate2_financial_semantic_v6_choice import (
    Gate2FinancialSemanticV6ChoiceContract,
)
from .gate2_financial_semantic_v6_expansion import (
    Gate2FinancialSemanticV6ExpandedDecision,
    Gate2FinancialSemanticV6ExpansionError,
    validate_financial_semantic_v6_expanded_decision,
)
from .gate2_financial_semantic_v6_packet import (
    Gate2FinancialSemanticV6Packet,
)


TOTAL_MATERIALIZATION_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_total_materialization_v6"
)
TOTAL_MATERIALIZATION_POLICY_VERSION = (
    "broker_reports_gate2_candidate_records_by_construction_v1"
)
TOTALITY_CHECKS = (
    "canonical_validation",
    "role_cardinality",
    "date_period_completeness",
    "currency_unit_completeness",
    "source_sign_policy",
    "identity_roles",
    "semantic_pack_registry_identity",
    "source_ownership",
    "terminal_artifact_validation",
)

FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV6TotalMaterializerFactory.create is the only "
    "V6 expanded-decision-to-canonical-artifact entrypoint"
)
FORBIDDEN = (
    "The V6 totality boundary must not implement a second materializer, "
    "repair a validated decision, change a disposition, or publish an "
    "artifact that bypassed canonical materialization validation"
)


class Gate2FinancialSemanticV6TotalityError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2FinancialSemanticV6TotalMaterialization:
    schema_version: str
    policy_version: str
    expansion_integrity_hash: str
    source_package_integrity_hash: str
    execution_ref: str
    decision_validation_ref: str
    terminal_disposition: str
    terminal_source_value_refs: tuple[str, ...]
    terminal_source_value_refs_hash: str
    canonical_artifact: dict[str, Any]
    canonical_artifact_hash: str
    totality_checks: tuple[str, ...]
    validated_but_unmaterializable: bool
    materializer_totality_status: str
    integrity_hash: str

    def to_private_dict(self) -> dict[str, Any]:
        return {
            **_totality_payload_without_integrity(self),
            "integrity_hash": self.integrity_hash,
        }

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "expansion_integrity_hash": self.expansion_integrity_hash,
            "source_package_integrity_hash": (self.source_package_integrity_hash),
            "terminal_disposition": self.terminal_disposition,
            "terminal_source_values_total": len(self.terminal_source_value_refs),
            "terminal_source_value_refs_hash": (self.terminal_source_value_refs_hash),
            "canonical_artifact_hash": self.canonical_artifact_hash,
            "totality_checks": list(self.totality_checks),
            "validated_but_unmaterializable": (self.validated_but_unmaterializable),
            "materializer_totality_status": (self.materializer_totality_status),
            "ownership_gaps_total": 0,
            "date_period_failures_after_model_total": 0,
            "provider_calls_total": 0,
            "contains_source_literals": False,
            "contains_source_value_refs": False,
            "integrity_hash": self.integrity_hash,
        }


class Gate2FinancialSemanticV6TotalMaterializerFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
    ) -> None:
        self.registry = registry

    def create(
        self,
        *,
        expansion: Gate2FinancialSemanticV6ExpandedDecision,
        model_output: str | dict[str, Any],
        choice_contract: Gate2FinancialSemanticV6ChoiceContract,
        packet: Gate2FinancialSemanticV6Packet,
        evidence_bundle: Gate2FinancialEvidenceBundle,
        source_package: Gate2FinancialEvidenceSourcePackage,
        compilation: Gate2FinancialCandidateCompilation,
    ) -> Gate2FinancialSemanticV6TotalMaterialization:
        return self._materialize(
            expansion=expansion,
            model_output=model_output,
            choice_contract=choice_contract,
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
        )

    def _materialize(
        self,
        *,
        expansion: Gate2FinancialSemanticV6ExpandedDecision,
        model_output: str | dict[str, Any],
        choice_contract: Gate2FinancialSemanticV6ChoiceContract,
        packet: Gate2FinancialSemanticV6Packet,
        evidence_bundle: Gate2FinancialEvidenceBundle,
        source_package: Gate2FinancialEvidenceSourcePackage,
        compilation: Gate2FinancialCandidateCompilation,
    ) -> Gate2FinancialSemanticV6TotalMaterialization:
        _validate_expansion(
            expansion=expansion,
            model_output=model_output,
            choice_contract=choice_contract,
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            registry=self.registry,
        )
        proof_seed = expansion.integrity_hash[:24]
        execution = FinancialEvidenceExecutionMetadata(
            execution_ref=f"execution:v6-totality:{proof_seed}",
            decision_validation_ref=(f"validation:v6-totality:{proof_seed}"),
        )
        try:
            artifact = (
                Gate2FinancialEvidenceMaterializerFactory(
                    registry=self.registry,
                    source_package=source_package,
                    execution_metadata=execution,
                )
                .create()
                .materialize(validated_decision=expansion.validated_decision)
            )
        except Gate2FinancialEvidenceMaterializationError as exc:
            raise Gate2FinancialSemanticV6TotalityError(
                "financial_semantic_v6_validated_but_unmaterializable"
            ) from exc
        terminal_refs = _validate_terminal_artifact(
            artifact=artifact,
            expansion=expansion,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            registry=self.registry,
            execution=execution,
            compilation=compilation,
        )
        material = {
            "schema_version": TOTAL_MATERIALIZATION_SCHEMA_VERSION,
            "policy_version": TOTAL_MATERIALIZATION_POLICY_VERSION,
            "expansion_integrity_hash": expansion.integrity_hash,
            "source_package_integrity_hash": source_package.integrity_hash,
            "execution_ref": execution.execution_ref,
            "decision_validation_ref": execution.decision_validation_ref,
            "terminal_disposition": artifact["terminal_disposition"],
            "terminal_source_value_refs": list(terminal_refs),
            "terminal_source_value_refs_hash": sha256_json(list(terminal_refs)),
            "canonical_artifact": copy.deepcopy(artifact),
            "canonical_artifact_hash": sha256_json(artifact),
            "totality_checks": list(TOTALITY_CHECKS),
            "validated_but_unmaterializable": False,
            "materializer_totality_status": "proven_for_expansion",
        }
        return Gate2FinancialSemanticV6TotalMaterialization(
            schema_version=TOTAL_MATERIALIZATION_SCHEMA_VERSION,
            policy_version=TOTAL_MATERIALIZATION_POLICY_VERSION,
            expansion_integrity_hash=expansion.integrity_hash,
            source_package_integrity_hash=source_package.integrity_hash,
            execution_ref=execution.execution_ref,
            decision_validation_ref=execution.decision_validation_ref,
            terminal_disposition=artifact["terminal_disposition"],
            terminal_source_value_refs=terminal_refs,
            terminal_source_value_refs_hash=sha256_json(list(terminal_refs)),
            canonical_artifact=copy.deepcopy(artifact),
            canonical_artifact_hash=sha256_json(artifact),
            totality_checks=TOTALITY_CHECKS,
            validated_but_unmaterializable=False,
            materializer_totality_status="proven_for_expansion",
            integrity_hash=sha256_json(material),
        )


def validate_financial_semantic_v6_total_materialization(
    *,
    result: Gate2FinancialSemanticV6TotalMaterialization,
    expansion: Gate2FinancialSemanticV6ExpandedDecision,
    model_output: str | dict[str, Any],
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    packet: Gate2FinancialSemanticV6Packet,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    compilation: Gate2FinancialCandidateCompilation,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> None:
    if not isinstance(
        result,
        Gate2FinancialSemanticV6TotalMaterialization,
    ):
        _fail("financial_semantic_v6_total_materialization_invalid")
    expected = Gate2FinancialSemanticV6TotalMaterializerFactory(
        registry=registry
    )._materialize(
        expansion=expansion,
        model_output=model_output,
        choice_contract=choice_contract,
        packet=packet,
        evidence_bundle=evidence_bundle,
        source_package=source_package,
        compilation=compilation,
    )
    if result != expected:
        _fail("financial_semantic_v6_total_materialization_integrity_invalid")


def _validate_terminal_artifact(
    *,
    artifact: dict[str, Any],
    expansion: Gate2FinancialSemanticV6ExpandedDecision,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    execution: FinancialEvidenceExecutionMetadata,
    compilation: Gate2FinancialCandidateCompilation,
) -> tuple[str, ...]:
    if (
        artifact.get("terminal_disposition") != expansion.disposition
        or artifact.get("integrity_hash")
        != sha256_json(
            {key: value for key, value in artifact.items() if key != "integrity_hash"}
        )
        or artifact.get("semantic_pack", {}).get("integrity_sha256")
        != expansion.validated_decision.semantic_pack_integrity_sha256
        or artifact.get("registry", {}).get("registry_hash") != registry.registry_hash
        or artifact.get("source_package", {}).get("integrity_hash")
        != source_package.integrity_hash
        or artifact.get("execution", {}).get("execution_ref") != execution.execution_ref
        or artifact.get("execution", {}).get("decision_validation_ref")
        != execution.decision_validation_ref
    ):
        _fail("financial_semantic_v6_terminal_artifact_identity_invalid")
    typed_inputs = artifact.get("typed_inputs")
    unclassified_inputs = artifact.get("unclassified_inputs")
    if not isinstance(typed_inputs, list) or not isinstance(
        unclassified_inputs,
        list,
    ):
        _fail("financial_semantic_v6_terminal_artifact_shape_invalid")
    if expansion.disposition == "typed_input":
        if len(typed_inputs) != 1 or unclassified_inputs:
            _fail("financial_semantic_v6_typed_terminal_invalid")
        terminal = typed_inputs[0]
        option = _selected_option(
            expansion=expansion,
            compilation=compilation,
        )
        if terminal.get("input_type_id") != option.input_type_id:
            _fail("financial_semantic_v6_typed_terminal_invalid")
    else:
        if typed_inputs or len(unclassified_inputs) != 1:
            _fail("financial_semantic_v6_unclassified_terminal_invalid")
        terminal = unclassified_inputs[0]
        if terminal.get("typed_input_published") is not False:
            _fail("financial_semantic_v6_unclassified_terminal_invalid")
    source_values = terminal.get("source_values")
    if not isinstance(source_values, list):
        _fail("financial_semantic_v6_terminal_source_values_invalid")
    terminal_refs = tuple(
        sorted(item.get("source_value_ref") for item in source_values)
    )
    expected_refs = tuple(sorted(expansion.retained_source_value_refs))
    if terminal_refs != expected_refs or len(terminal_refs) != len(set(terminal_refs)):
        _fail("financial_semantic_v6_terminal_source_values_invalid")
    ownership = terminal.get("source_ownership")
    if ownership != {
        "normalization_run_ref": source_package.normalization_run_ref,
        "document_ref": source_package.document_ref,
        "source_package_ref": source_package.package_ref,
        "source_scope_ref": source_package.source_scope_ref,
    }:
        _fail("financial_semantic_v6_terminal_ownership_invalid")
    if expansion.disposition == "unclassified_financial_input" and (
        terminal_refs != tuple(sorted(evidence_bundle.retention_set))
    ):
        _fail("financial_semantic_v6_unclassified_retention_loss")
    return terminal_refs


def _selected_option(
    *,
    expansion: Gate2FinancialSemanticV6ExpandedDecision,
    compilation: Gate2FinancialCandidateCompilation,
):
    matches = tuple(
        item
        for item in compilation.typed_options
        if item.typed_option_id == expansion.selected_typed_option_id
    )
    if len(matches) != 1:
        _fail("financial_semantic_v6_totality_option_invalid")
    option = matches[0]
    if (
        option.materializability_receipt.status != "materializable"
        or option.materializability_receipt.typed_inputs_total != 1
        or option.materializability_receipt.unclassified_inputs_total != 0
    ):
        _fail("financial_semantic_v6_totality_option_unproven")
    return option


def _validate_expansion(
    *,
    expansion: Gate2FinancialSemanticV6ExpandedDecision,
    model_output: str | dict[str, Any],
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    packet: Gate2FinancialSemanticV6Packet,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    compilation: Gate2FinancialCandidateCompilation,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> None:
    try:
        validate_financial_semantic_v6_expanded_decision(
            expansion=expansion,
            model_output=model_output,
            choice_contract=choice_contract,
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            registry=registry,
        )
    except Gate2FinancialSemanticV6ExpansionError as exc:
        raise Gate2FinancialSemanticV6TotalityError(
            "financial_semantic_v6_totality_expansion_invalid"
        ) from exc


def _totality_payload_without_integrity(
    result: Gate2FinancialSemanticV6TotalMaterialization,
) -> dict[str, Any]:
    return {
        "schema_version": result.schema_version,
        "policy_version": result.policy_version,
        "expansion_integrity_hash": result.expansion_integrity_hash,
        "source_package_integrity_hash": (result.source_package_integrity_hash),
        "execution_ref": result.execution_ref,
        "decision_validation_ref": result.decision_validation_ref,
        "terminal_disposition": result.terminal_disposition,
        "terminal_source_value_refs": list(result.terminal_source_value_refs),
        "terminal_source_value_refs_hash": (result.terminal_source_value_refs_hash),
        "canonical_artifact": copy.deepcopy(result.canonical_artifact),
        "canonical_artifact_hash": result.canonical_artifact_hash,
        "totality_checks": list(result.totality_checks),
        "validated_but_unmaterializable": (result.validated_but_unmaterializable),
        "materializer_totality_status": (result.materializer_totality_status),
    }


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV6TotalityError(code)
