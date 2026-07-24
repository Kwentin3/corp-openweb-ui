from __future__ import annotations

from .gate2_financial_evidence_materialization_contracts import (
    COMPLETENESS_VALUES,
    MAX_LITERAL_LENGTH,
    SOURCE_PACKAGE_SCHEMA_VERSION,
    FinancialEvidenceAuthoritativeSourceValue,
    Gate2FinancialEvidenceSourcePackage,
    fail,
    identifier,
    normalize_comparison_value,
    sha256_json,
    sorted_identifiers,
    source_value_payload,
)


FACTORY_REQUIRED = (
    "Gate2FinancialEvidenceSourcePackageFactory.create is the only "
    "authoritative financial source-package sealing entrypoint"
)
FORBIDDEN = (
    "Models and providers must not mint source-package integrity, literal "
    "values, evidence refs or lineage"
)


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
            identifier(value, field)
        if self.completeness not in COMPLETENESS_VALUES:
            fail("financial_evidence_source_package_completeness_invalid")
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
            fail("financial_evidence_source_value_ref_duplicate")
        source_evidence_refs = sorted_identifiers(
            self.source_evidence_refs,
            field="source_evidence_ref",
            required=True,
        )
        restriction_codes = sorted_identifiers(
            self.restriction_codes,
            field="restriction_code",
        )
        issue_refs = sorted_identifiers(
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
                source_value_payload(item) for item in source_values
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
            integrity_hash=sha256_json(payload),
        )


def validate_source_package_integrity(
    package: Gate2FinancialEvidenceSourcePackage,
) -> None:
    if package.schema_version != SOURCE_PACKAGE_SCHEMA_VERSION:
        fail("financial_evidence_source_package_version_invalid")
    payload = {
        "schema_version": package.schema_version,
        "package_ref": package.package_ref,
        "normalization_run_ref": package.normalization_run_ref,
        "document_ref": package.document_ref,
        "source_scope_ref": package.source_scope_ref,
        "source_family_id": package.source_family_id,
        "source_values": [
            source_value_payload(item) for item in package.source_values
        ],
        "source_evidence_refs": list(package.source_evidence_refs),
        "completeness": package.completeness,
        "restriction_codes": list(package.restriction_codes),
        "issue_refs": list(package.issue_refs),
    }
    if package.integrity_hash != sha256_json(payload):
        fail("financial_evidence_source_package_integrity_invalid")


def _normalize_authoritative_source_value(
    value: FinancialEvidenceAuthoritativeSourceValue,
    *,
    document_ref: str,
) -> FinancialEvidenceAuthoritativeSourceValue:
    identifier(value.source_value_ref, "source_value_ref")
    identifier(value.source_ref, "source_ref")
    if (
        not isinstance(value.literal_value, str)
        or not value.literal_value
        or len(value.literal_value) > MAX_LITERAL_LENGTH
    ):
        fail("financial_evidence_literal_value_invalid")
    normalize_comparison_value(
        literal_value=value.literal_value,
        value_type=value.value_type,
    )
    evidence_refs = sorted_identifiers(
        value.source_evidence_refs,
        field="source_evidence_ref",
        required=True,
    )
    lineage = value.lineage
    if lineage.document_ref != document_ref:
        fail("financial_evidence_lineage_document_mismatch")
    identifier(lineage.document_ref, "lineage_document_ref")
    locators = (
        lineage.page_ref,
        lineage.table_ref,
        lineage.row_ref,
        lineage.cell_ref,
        lineage.text_segment_ref,
    )
    if not any(locators):
        fail("financial_evidence_lineage_locator_missing")
    for locator in locators:
        if locator is not None:
            identifier(locator, "lineage_locator")
    return FinancialEvidenceAuthoritativeSourceValue(
        source_value_ref=value.source_value_ref,
        source_ref=value.source_ref,
        value_type=value.value_type,
        literal_value=value.literal_value,
        source_evidence_refs=evidence_refs,
        lineage=lineage,
    )
