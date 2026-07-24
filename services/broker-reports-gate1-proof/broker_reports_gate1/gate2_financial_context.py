from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from .gate2_financial_context_contracts import (
    FINANCIAL_CONTEXT_PROJECTION_POLICY_VERSION,
    FINANCIAL_CONTEXT_SCHEMA_VERSION,
    Gate2FinancialContextProjectionError,
    fail,
)
from .gate2_financial_context_validation import validate_financial_context
from .gate2_financial_evidence_materialization_contracts import (
    Gate2FinancialEvidenceSourcePackage,
    sha256_json,
    source_value_payload,
)
from .gate2_financial_evidence_materialization_validation import (
    validate_financial_evidence_inputs,
)
from .gate2_financial_evidence_registry import (
    REGISTRY_ID,
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_evidence_source_package import (
    validate_source_package_integrity,
)


FACTORY_REQUIRED = (
    "Gate2FinancialContextProjectionFactory.create is the only production "
    "model-facing financial context projection entrypoint"
)
FORBIDDEN = (
    "Raw Gate 1 representations, duplicate interpretation entries, provider "
    "responses, tax methodology and answer fields must not enter context"
)

__all__ = [
    "FINANCIAL_CONTEXT_PROJECTION_POLICY_VERSION",
    "FINANCIAL_CONTEXT_SCHEMA_VERSION",
    "Gate2FinancialContextProjectionError",
    "Gate2FinancialContextProjectionFactory",
    "validate_financial_context",
]


class Gate2FinancialContextProjectionFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
    ) -> None:
        self.registry = registry

    def create(
        self,
        *,
        materialized_artifacts: Iterable[dict[str, Any]],
        source_packages: Iterable[Gate2FinancialEvidenceSourcePackage],
    ) -> dict[str, Any]:
        artifacts = self._validated_artifacts(materialized_artifacts)
        packages = self._validated_packages(source_packages)
        artifact_package_refs = {
            item["source_package"]["package_ref"] for item in artifacts
        }
        if artifact_package_refs != set(packages):
            fail("financial_context_source_package_set_mismatch")
        entries = [
            self._entry(
                artifact=artifact,
                source_package=packages[
                    artifact["source_package"]["package_ref"]
                ],
            )
            for artifact in artifacts
        ]
        entries.sort(key=lambda item: item["source_scope_ref"])
        scopes = [item["source_scope_ref"] for item in entries]
        if len(scopes) != len(set(scopes)):
            fail("financial_context_duplicate_interpretation_scope")
        status_counts = Counter(item["status"] for item in entries)
        payload: dict[str, Any] = {
            "schema_version": FINANCIAL_CONTEXT_SCHEMA_VERSION,
            "projection_policy_version": (
                FINANCIAL_CONTEXT_PROJECTION_POLICY_VERSION
            ),
            "registry": {
                "registry_id": REGISTRY_ID,
                "registry_version": self.registry.registry_version,
                "registry_hash": self.registry.registry_hash,
            },
            "entries": entries,
            "scope_coverage": {
                "source_scopes_total": len(entries),
                "interpretation_representations_total": len(entries),
                "provenance_only_representations_total": sum(
                    len(item["provenance_only_representations"])
                    for item in entries
                ),
                "status_counts": {
                    status: status_counts.get(status, 0)
                    for status in (
                        "no_financial_input",
                        "typed_input",
                        "unclassified_financial_input",
                        "unsupported",
                    )
                },
                "duplicate_interpretation_representations_total": 0,
                "calculated_aggregates_total": 0,
            },
        }
        payload["integrity_hash"] = sha256_json(payload)
        validate_financial_context(
            payload=payload,
            registry=self.registry,
        )
        return payload

    def _validated_artifacts(
        self,
        artifacts: Iterable[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        unique: dict[tuple[str, str], dict[str, Any]] = {}
        for artifact in artifacts:
            validate_financial_evidence_inputs(
                payload=artifact,
                registry=self.registry,
            )
            key = (
                artifact["artifact_id"],
                artifact["integrity_hash"],
            )
            unique[key] = artifact
        return sorted(
            unique.values(),
            key=lambda item: (
                item["source_package"]["source_scope_ref"],
                item["artifact_id"],
                item["integrity_hash"],
            ),
        )

    def _validated_packages(
        self,
        packages: Iterable[Gate2FinancialEvidenceSourcePackage],
    ) -> dict[str, Gate2FinancialEvidenceSourcePackage]:
        result: dict[str, Gate2FinancialEvidenceSourcePackage] = {}
        for package in packages:
            validate_source_package_integrity(package)
            previous = result.get(package.package_ref)
            if previous is not None and previous != package:
                fail("financial_context_source_package_ref_conflict")
            result[package.package_ref] = package
        return result

    def _entry(
        self,
        *,
        artifact: dict[str, Any],
        source_package: Gate2FinancialEvidenceSourcePackage,
    ) -> dict[str, Any]:
        expected_package = artifact["source_package"]
        if (
            expected_package["integrity_hash"]
            != source_package.integrity_hash
            or expected_package["source_scope_ref"]
            != source_package.source_scope_ref
            or expected_package["source_family_id"]
            != source_package.source_family_id
        ):
            fail("financial_context_source_package_authority_mismatch")
        status = artifact["terminal_disposition"]
        terminal = self._terminal_object(artifact)
        values = self._values(terminal)
        evidence_identity = self._evidence_identity(
            artifact=artifact,
            source_package=source_package,
            terminal=terminal,
            values=values,
        )
        representation_id = (
            artifact["coverage"]["coverage_id"]
            if terminal is None
            else terminal.get("input_id")
            or terminal["unclassified_input_id"]
        )
        interpretation = {
            "representation_id": representation_id,
            "representation_role": "interpretation",
            "status": status,
            "input_type": self._input_type(terminal),
            "aggregate_semantics": self._aggregate_semantics(
                status=status,
                terminal=terminal,
            ),
            "literal_source_labels": sorted(
                {
                    item["literal_value"]
                    for item in values
                    if item["role_id"] == "source_label"
                }
            ),
            "values": values,
            "date_period": (
                dict(terminal["date_period"]) if terminal else {}
            ),
            "currency_unit": (
                dict(terminal["currency_unit"]) if terminal else {}
            ),
            "source_location": {
                "document_ref": source_package.document_ref,
                "page_refs": sorted(
                    {
                        item.lineage.page_ref
                        for item in source_package.source_values
                        if item.lineage.page_ref
                    }
                ),
                "source_scope_ref": source_package.source_scope_ref,
            },
            "restrictions": {
                "completeness": source_package.completeness,
                "restriction_codes": list(
                    source_package.restriction_codes
                ),
                "issue_refs": list(source_package.issue_refs),
            },
            "evidence_identity": evidence_identity,
            "terminal_reason_code": artifact["coverage"]["reason_code"],
        }
        entry_id = "finctx_" + sha256_json(
            {
                "source_scope_ref": source_package.source_scope_ref,
                "status": status,
                "interpretation_representation_id": representation_id,
                "evidence_identity": evidence_identity,
            }
        )[:32]
        return {
            "context_entry_id": entry_id,
            "source_scope_ref": source_package.source_scope_ref,
            "status": status,
            "interpretation_representation": interpretation,
            "provenance_only_representations": (
                self._provenance_representations(source_package)
            ),
        }

    def _terminal_object(
        self,
        artifact: dict[str, Any],
    ) -> dict[str, Any] | None:
        if artifact["typed_inputs"]:
            return artifact["typed_inputs"][0]
        if artifact["unclassified_inputs"]:
            return artifact["unclassified_inputs"][0]
        return None

    def _values(
        self,
        terminal: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        if terminal is None:
            return []
        return [
            {
                "role_id": item["role_id"],
                "source_value_ref": item["source_value_ref"],
                "value_type": item["value_type"],
                "literal_value": item["literal_value"],
                "source_sign": item["source_sign"],
            }
            for item in terminal["source_values"]
        ]

    def _input_type(
        self,
        terminal: dict[str, Any] | None,
    ) -> dict[str, str] | None:
        if terminal is None or "input_type_id" not in terminal:
            return None
        declaration = self.registry.get(terminal["input_type_id"])
        return {
            "input_type_id": declaration.input_type_id,
            "title": declaration.title,
            "semantic_class": declaration.semantic_class,
        }

    def _aggregate_semantics(
        self,
        *,
        status: str,
        terminal: dict[str, Any] | None,
    ) -> str:
        if status == "unclassified_financial_input":
            return "unclassified"
        if status != "typed_input" or terminal is None:
            return "not_applicable"
        if (
            terminal["input_type_id"]
            == "printed_financial_metric_v1"
        ):
            return "source_printed"
        return "not_aggregate"

    def _evidence_identity(
        self,
        *,
        artifact: dict[str, Any],
        source_package: Gate2FinancialEvidenceSourcePackage,
        terminal: dict[str, Any] | None,
        values: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "financial_evidence_artifact_id": artifact["artifact_id"],
            "financial_evidence_artifact_integrity_hash": artifact[
                "integrity_hash"
            ],
            "terminal_object_id": (
                artifact["coverage"]["coverage_id"]
                if terminal is None
                else terminal.get("input_id")
                or terminal["unclassified_input_id"]
            ),
            "terminal_object_integrity_hash": (
                terminal["integrity_hash"] if terminal else None
            ),
            "source_package_ref": source_package.package_ref,
            "source_package_integrity_hash": (
                source_package.integrity_hash
            ),
            "source_value_refs": sorted(
                item["source_value_ref"] for item in values
            ),
            "source_evidence_refs": (
                list(source_package.source_evidence_refs)
                if terminal is None
                else list(terminal["source_evidence_refs"])
            ),
        }

    def _provenance_representations(
        self,
        source_package: Gate2FinancialEvidenceSourcePackage,
    ) -> list[dict[str, Any]]:
        grouped: dict[str, list] = {}
        for value in source_package.source_values:
            grouped.setdefault(value.source_ref, []).append(value)
        representations = []
        for source_ref, values in grouped.items():
            value_refs = sorted(
                item.source_value_ref for item in values
            )
            evidence_refs = sorted(
                {
                    evidence_ref
                    for item in values
                    for evidence_ref in item.source_evidence_refs
                }
            )
            lineages = {
                sha256_json(source_value_payload(item)["lineage"]): (
                    source_value_payload(item)["lineage"]
                )
                for item in values
            }
            representation_id = "finprov_" + sha256_json(
                {
                    "source_package_integrity_hash": (
                        source_package.integrity_hash
                    ),
                    "source_ref": source_ref,
                    "source_value_refs": value_refs,
                    "source_evidence_refs": evidence_refs,
                    "lineage": [
                        lineages[key] for key in sorted(lineages)
                    ],
                }
            )[:32]
            representations.append(
                {
                    "representation_id": representation_id,
                    "representation_role": "provenance_only",
                    "source_ref": source_ref,
                    "source_value_refs": value_refs,
                    "source_evidence_refs": evidence_refs,
                    "lineage": [
                        lineages[key] for key in sorted(lineages)
                    ],
                }
            )
        return sorted(
            representations,
            key=lambda item: item["representation_id"],
        )
