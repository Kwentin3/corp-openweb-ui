from __future__ import annotations

import copy
import hashlib
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .gate2_financial_evidence_materialization_contracts import (
    FinancialEvidenceAuthoritativeSourceValue,
    FinancialEvidenceSourceLineage,
    Gate2FinancialEvidenceMaterializationError,
    Gate2FinancialEvidenceSourcePackage,
    identifier,
    sha256_json,
)
from .gate2_financial_evidence_source_context import (
    FinancialEvidenceVisibleValueContext,
    financial_evidence_visible_value_contexts,
)
from .gate2_financial_evidence_source_package import (
    Gate2FinancialEvidenceSourcePackageFactory,
)


EVIDENCE_BUNDLE_SCHEMA_VERSION = "broker_reports_gate2_financial_evidence_bundle_v1"
EVIDENCE_BUNDLE_POLICY_VERSION = (
    "broker_reports_gate2_candidate_records_by_construction_v1"
)
EVIDENCE_BUNDLE_ID_PREFIX = "financial-evidence-bundle:"

FACTORY_REQUIRED = (
    "Gate2FinancialEvidenceBundleFactory.create is the only V6 "
    "authoritative Evidence Bundle construction entrypoint"
)
FORBIDDEN = (
    "The Evidence Bundle must not import or project Financial Semantic Pack "
    "meanings, type IDs, expected answers or model output; models must not "
    "control source membership, associations, provenance or retention"
)

_ASSOCIATION_KINDS = frozenset({"table_row", "text_segment", "deterministic_reference"})


class Gate2FinancialEvidenceBundleError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class FinancialEvidenceBundleSourceValue:
    source_value_ref: str
    source_ref: str
    value_type: str
    literal_value: str
    source_evidence_refs: tuple[str, ...]
    lineage: FinancialEvidenceSourceLineage
    association_ref: str
    association_kind: str
    column_meaning: str | None
    visible_label: str | None
    row_role: str | None
    section_role: str | None


@dataclass(frozen=True)
class FinancialEvidenceBundleAssociation:
    association_ref: str
    association_kind: str
    source_value_refs: tuple[str, ...]


@dataclass(frozen=True)
class Gate2FinancialEvidenceBundle:
    schema_version: str
    policy_version: str
    bundle_id: str
    source_package_ref: str
    source_package_integrity_hash: str
    normalization_run_ref: str
    document_ref: str
    source_scope_ref: str
    source_family_id: str
    completeness: str
    restriction_codes: tuple[str, ...]
    issue_refs: tuple[str, ...]
    source_values: tuple[FinancialEvidenceBundleSourceValue, ...]
    source_associations: tuple[FinancialEvidenceBundleAssociation, ...]
    provenance_refs: tuple[str, ...]
    retention_set: tuple[str, ...]
    integrity_hash: str

    def to_private_dict(self) -> dict[str, Any]:
        return {
            **_bundle_payload_without_integrity(self),
            "integrity_hash": self.integrity_hash,
        }

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "bundle_id_sha256": hashlib.sha256(
                self.bundle_id.encode("utf-8")
            ).hexdigest(),
            "source_package_integrity_hash": (self.source_package_integrity_hash),
            "source_values_total": len(self.source_values),
            "source_associations_total": len(self.source_associations),
            "provenance_refs_total": len(self.provenance_refs),
            "retention_set_total": len(self.retention_set),
            "source_values_complete_and_exactly_once": True,
            "unclassified_retention_code_owned": True,
            "contains_source_literals": False,
            "contains_source_value_refs": False,
            "contains_financial_type_meaning": False,
            "contains_expected_answer": False,
            "contains_model_output": False,
            "provider_calls_total": 0,
            "integrity_hash": self.integrity_hash,
        }


class Gate2FinancialEvidenceBundleFactory:
    def create(
        self,
        *,
        source_package: Gate2FinancialEvidenceSourcePackage,
        gate1_packages: Iterable[dict[str, Any]],
    ) -> Gate2FinancialEvidenceBundle:
        _validate_source_package(source_package)
        packages = copy.deepcopy(tuple(gate1_packages))
        if not packages or not all(isinstance(item, dict) for item in packages):
            _fail("financial_evidence_bundle_gate1_packages_invalid")

        package_refs = {
            value.source_value_ref for value in source_package.source_values
        }
        visible = financial_evidence_visible_value_contexts(packages=packages)
        relevant_visible = {
            ref: context for ref, context in visible.items() if ref in package_refs
        }
        _validate_contributing_package_documents(
            packages=packages,
            package_refs=package_refs,
            document_ref=source_package.document_ref,
        )

        values = tuple(
            _bundle_source_value(
                value=value,
                visible_context=relevant_visible.get(value.source_value_ref),
            )
            for value in source_package.source_values
        )
        associations = _source_associations(values)
        retention_set = tuple(value.source_value_ref for value in values)
        provenance_refs = tuple(
            sorted(
                {
                    *source_package.source_evidence_refs,
                    *(
                        ref
                        for value in source_package.source_values
                        for ref in value.source_evidence_refs
                    ),
                }
            )
        )
        identity_material = _identity_material(
            source_package=source_package,
            source_values=values,
            source_associations=associations,
            provenance_refs=provenance_refs,
            retention_set=retention_set,
        )
        bundle_id = EVIDENCE_BUNDLE_ID_PREFIX + sha256_json(identity_material)[:32]
        payload = {
            **identity_material,
            "bundle_id": bundle_id,
        }
        bundle = Gate2FinancialEvidenceBundle(
            schema_version=EVIDENCE_BUNDLE_SCHEMA_VERSION,
            policy_version=EVIDENCE_BUNDLE_POLICY_VERSION,
            bundle_id=bundle_id,
            source_package_ref=source_package.package_ref,
            source_package_integrity_hash=(source_package.integrity_hash),
            normalization_run_ref=(source_package.normalization_run_ref),
            document_ref=source_package.document_ref,
            source_scope_ref=source_package.source_scope_ref,
            source_family_id=source_package.source_family_id,
            completeness=source_package.completeness,
            restriction_codes=source_package.restriction_codes,
            issue_refs=source_package.issue_refs,
            source_values=values,
            source_associations=associations,
            provenance_refs=provenance_refs,
            retention_set=retention_set,
            integrity_hash=sha256_json(payload),
        )
        validate_financial_evidence_bundle(
            bundle=bundle,
            source_package=source_package,
        )
        return bundle


def validate_financial_evidence_bundle(
    *,
    bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
) -> None:
    _validate_source_package(source_package)
    if (
        not isinstance(bundle, Gate2FinancialEvidenceBundle)
        or bundle.schema_version != EVIDENCE_BUNDLE_SCHEMA_VERSION
        or bundle.policy_version != EVIDENCE_BUNDLE_POLICY_VERSION
        or bundle.source_package_ref != source_package.package_ref
        or bundle.source_package_integrity_hash != source_package.integrity_hash
        or bundle.normalization_run_ref != source_package.normalization_run_ref
        or bundle.document_ref != source_package.document_ref
        or bundle.source_scope_ref != source_package.source_scope_ref
        or bundle.source_family_id != source_package.source_family_id
        or bundle.completeness != source_package.completeness
        or bundle.restriction_codes != source_package.restriction_codes
        or bundle.issue_refs != source_package.issue_refs
        or not bundle.source_values
    ):
        _fail("financial_evidence_bundle_identity_invalid")

    expected_core = {
        value.source_value_ref: _source_value_core(value)
        for value in source_package.source_values
    }
    observed_refs: list[str] = []
    for value in bundle.source_values:
        _validate_bundle_source_value(value)
        observed_refs.append(value.source_value_ref)
        if expected_core.get(value.source_value_ref) != (
            _bundle_source_value_core(value)
        ):
            _fail("financial_evidence_bundle_source_authority_mismatch")
    expected_refs = tuple(sorted(expected_core))
    if (
        tuple(observed_refs) != expected_refs
        or len(observed_refs) != len(set(observed_refs))
        or bundle.retention_set != expected_refs
    ):
        _fail("financial_evidence_bundle_source_coverage_invalid")

    expected_provenance = tuple(
        sorted(
            {
                *source_package.source_evidence_refs,
                *(
                    ref
                    for value in source_package.source_values
                    for ref in value.source_evidence_refs
                ),
            }
        )
    )
    if bundle.provenance_refs != expected_provenance:
        _fail("financial_evidence_bundle_provenance_invalid")

    expected_associations = _source_associations(bundle.source_values)
    if bundle.source_associations != expected_associations:
        _fail("financial_evidence_bundle_associations_invalid")

    identity_material = _identity_material(
        source_package=source_package,
        source_values=bundle.source_values,
        source_associations=bundle.source_associations,
        provenance_refs=bundle.provenance_refs,
        retention_set=bundle.retention_set,
    )
    expected_bundle_id = EVIDENCE_BUNDLE_ID_PREFIX + sha256_json(identity_material)[:32]
    payload = {
        **identity_material,
        "bundle_id": expected_bundle_id,
    }
    if bundle.bundle_id != expected_bundle_id or bundle.integrity_hash != sha256_json(
        payload
    ):
        _fail("financial_evidence_bundle_integrity_invalid")


def _validate_source_package(
    source_package: Any,
) -> None:
    if not isinstance(
        source_package,
        Gate2FinancialEvidenceSourcePackage,
    ):
        _fail("financial_evidence_bundle_source_package_invalid")
    try:
        expected = Gate2FinancialEvidenceSourcePackageFactory(
            package_ref=source_package.package_ref,
            normalization_run_ref=source_package.normalization_run_ref,
            document_ref=source_package.document_ref,
            source_scope_ref=source_package.source_scope_ref,
            source_family_id=source_package.source_family_id,
            source_values=source_package.source_values,
            source_evidence_refs=source_package.source_evidence_refs,
            completeness=source_package.completeness,
            restriction_codes=source_package.restriction_codes,
            issue_refs=source_package.issue_refs,
        ).create()
    except Gate2FinancialEvidenceMaterializationError as exc:
        raise Gate2FinancialEvidenceBundleError(
            "financial_evidence_bundle_source_package_invalid"
        ) from exc
    if expected != source_package:
        _fail("financial_evidence_bundle_source_package_invalid")


def _validate_contributing_package_documents(
    *,
    packages: tuple[dict[str, Any], ...],
    package_refs: set[str],
    document_ref: str,
) -> None:
    contributed: set[str] = set()
    for package in packages:
        contexts = financial_evidence_visible_value_contexts(packages=(package,))
        relevant = package_refs.intersection(contexts)
        if not relevant:
            continue
        unit = package.get("source_unit") or {}
        if unit.get("document_ref") != document_ref:
            _fail("financial_evidence_bundle_document_mismatch")
        contributed.update(relevant)
    if not contributed:
        _fail("financial_evidence_bundle_visible_context_missing")


def _bundle_source_value(
    *,
    value: FinancialEvidenceAuthoritativeSourceValue,
    visible_context: FinancialEvidenceVisibleValueContext | None,
) -> FinancialEvidenceBundleSourceValue:
    if value.value_type == "source_reference":
        if visible_context is not None:
            _fail("financial_evidence_bundle_reference_context_invalid")
        association_ref = _lineage_association_ref(value)
        association_kind = "deterministic_reference"
        column_meaning = None
        visible_label = None
        row_role = None
        section_role = None
    else:
        if (
            not isinstance(
                visible_context,
                FinancialEvidenceVisibleValueContext,
            )
            or visible_context.literal_value != value.literal_value
            or not visible_context.association_group
            or visible_context.group_kind not in {"table_row", "text_segment"}
        ):
            _fail("financial_evidence_bundle_visible_context_invalid")
        association_ref = visible_context.association_group
        association_kind = visible_context.group_kind
        column_meaning = _optional_text(visible_context.column_meaning)
        visible_label = _optional_text(visible_context.visible_label)
        row_role = _optional_text(visible_context.row_role)
        section_role = _optional_text(visible_context.section_role)
    identifier(association_ref, "association_ref")
    return FinancialEvidenceBundleSourceValue(
        source_value_ref=value.source_value_ref,
        source_ref=value.source_ref,
        value_type=value.value_type,
        literal_value=value.literal_value,
        source_evidence_refs=value.source_evidence_refs,
        lineage=value.lineage,
        association_ref=association_ref,
        association_kind=association_kind,
        column_meaning=column_meaning,
        visible_label=visible_label,
        row_role=row_role,
        section_role=section_role,
    )


def _lineage_association_ref(
    value: FinancialEvidenceAuthoritativeSourceValue,
) -> str:
    lineage = value.lineage
    for ref in (
        lineage.text_segment_ref,
        lineage.row_ref,
        lineage.table_ref,
        lineage.page_ref,
        lineage.cell_ref,
        value.source_ref,
    ):
        if ref:
            return ref
    _fail("financial_evidence_bundle_association_missing")


def _source_associations(
    values: tuple[FinancialEvidenceBundleSourceValue, ...],
) -> tuple[FinancialEvidenceBundleAssociation, ...]:
    grouped: dict[tuple[str, str], list[str]] = {}
    for value in values:
        grouped.setdefault(
            (value.association_kind, value.association_ref),
            [],
        ).append(value.source_value_ref)
    result = tuple(
        FinancialEvidenceBundleAssociation(
            association_ref=association_ref,
            association_kind=association_kind,
            source_value_refs=tuple(sorted(refs)),
        )
        for (
            association_kind,
            association_ref,
        ), refs in sorted(grouped.items())
    )
    observed = [ref for association in result for ref in association.source_value_refs]
    if sorted(observed) != sorted(value.source_value_ref for value in values) or len(
        observed
    ) != len(set(observed)):
        _fail("financial_evidence_bundle_associations_invalid")
    return result


def _validate_bundle_source_value(
    value: Any,
) -> None:
    if (
        not isinstance(value, FinancialEvidenceBundleSourceValue)
        or value.association_kind not in _ASSOCIATION_KINDS
        or not isinstance(value.literal_value, str)
        or not value.literal_value
        or not isinstance(value.lineage, FinancialEvidenceSourceLineage)
    ):
        _fail("financial_evidence_bundle_source_value_invalid")
    for raw, field in (
        (value.source_value_ref, "source_value_ref"),
        (value.source_ref, "source_ref"),
        (value.association_ref, "association_ref"),
    ):
        identifier(raw, field)
    if value.value_type == "source_reference" and (
        value.association_kind != "deterministic_reference"
        or any(
            item is not None
            for item in (
                value.column_meaning,
                value.visible_label,
                value.row_role,
                value.section_role,
            )
        )
    ):
        _fail("financial_evidence_bundle_reference_context_invalid")
    if (
        value.value_type != "source_reference"
        and value.association_kind == "deterministic_reference"
    ):
        _fail("financial_evidence_bundle_visible_context_invalid")
    for item in (
        value.column_meaning,
        value.visible_label,
        value.row_role,
        value.section_role,
    ):
        if item is not None and (not isinstance(item, str) or not item):
            _fail("financial_evidence_bundle_visible_context_invalid")


def _identity_material(
    *,
    source_package: Gate2FinancialEvidenceSourcePackage,
    source_values: tuple[FinancialEvidenceBundleSourceValue, ...],
    source_associations: tuple[FinancialEvidenceBundleAssociation, ...],
    provenance_refs: tuple[str, ...],
    retention_set: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "schema_version": EVIDENCE_BUNDLE_SCHEMA_VERSION,
        "policy_version": EVIDENCE_BUNDLE_POLICY_VERSION,
        "source_package_ref": source_package.package_ref,
        "source_package_integrity_hash": (source_package.integrity_hash),
        "normalization_run_ref": source_package.normalization_run_ref,
        "document_ref": source_package.document_ref,
        "source_scope_ref": source_package.source_scope_ref,
        "source_family_id": source_package.source_family_id,
        "completeness": source_package.completeness,
        "restriction_codes": list(source_package.restriction_codes),
        "issue_refs": list(source_package.issue_refs),
        "source_values": [
            _bundle_source_value_payload(value) for value in source_values
        ],
        "source_associations": [
            _association_payload(value) for value in source_associations
        ],
        "provenance_refs": list(provenance_refs),
        "retention_set": list(retention_set),
    }


def _bundle_payload_without_integrity(
    bundle: Gate2FinancialEvidenceBundle,
) -> dict[str, Any]:
    return {
        "schema_version": bundle.schema_version,
        "policy_version": bundle.policy_version,
        "bundle_id": bundle.bundle_id,
        "source_package_ref": bundle.source_package_ref,
        "source_package_integrity_hash": (bundle.source_package_integrity_hash),
        "normalization_run_ref": bundle.normalization_run_ref,
        "document_ref": bundle.document_ref,
        "source_scope_ref": bundle.source_scope_ref,
        "source_family_id": bundle.source_family_id,
        "completeness": bundle.completeness,
        "restriction_codes": list(bundle.restriction_codes),
        "issue_refs": list(bundle.issue_refs),
        "source_values": [
            _bundle_source_value_payload(value) for value in bundle.source_values
        ],
        "source_associations": [
            _association_payload(value) for value in bundle.source_associations
        ],
        "provenance_refs": list(bundle.provenance_refs),
        "retention_set": list(bundle.retention_set),
    }


def _source_value_core(
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


def _bundle_source_value_core(
    value: FinancialEvidenceBundleSourceValue,
) -> dict[str, Any]:
    return {
        key: item
        for key, item in _bundle_source_value_payload(value).items()
        if key
        not in {
            "association_ref",
            "association_kind",
            "visible_context",
        }
    }


def _bundle_source_value_payload(
    value: FinancialEvidenceBundleSourceValue,
) -> dict[str, Any]:
    return {
        "source_value_ref": value.source_value_ref,
        "source_ref": value.source_ref,
        "value_type": value.value_type,
        "literal_value": value.literal_value,
        "source_evidence_refs": list(value.source_evidence_refs),
        "lineage": asdict(value.lineage),
        "association_ref": value.association_ref,
        "association_kind": value.association_kind,
        "visible_context": {
            "column_meaning": value.column_meaning,
            "visible_label": value.visible_label,
            "row_role": value.row_role,
            "section_role": value.section_role,
        },
    }


def _association_payload(
    association: FinancialEvidenceBundleAssociation,
) -> dict[str, Any]:
    return {
        "association_ref": association.association_ref,
        "association_kind": association.association_kind,
        "source_value_refs": list(association.source_value_refs),
    }


def _optional_text(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        _fail("financial_evidence_bundle_visible_context_invalid")
    return value


def _fail(code: str) -> None:
    raise Gate2FinancialEvidenceBundleError(code)
