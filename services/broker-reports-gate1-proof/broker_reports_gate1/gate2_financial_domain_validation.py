from __future__ import annotations

from typing import Any

from .gate2_financial_domain_contracts import (
    FINANCIAL_DOMAIN_CATALOG_SCHEMA_VERSION,
    FINANCIAL_DOMAIN_CONTRACT_VERSION,
    FINANCIAL_DOMAIN_COVERAGE_SCHEMA_VERSION,
    FINANCIAL_DOMAIN_PROVENANCE_SCHEMA_VERSION,
    FINANCIAL_DOMAIN_SNAPSHOT_SCHEMA_VERSION,
    FINANCIAL_DOMAIN_TYPED_RECORD_SCHEMA_VERSION,
    FINANCIAL_DOMAIN_UNCLASSIFIED_RECORD_SCHEMA_VERSION,
    fail,
    sha256_json,
    validate_timestamp,
)
from .gate2_financial_domain_projection import (
    snapshot_integrity_material,
)


def validate_financial_domain_snapshot(
    *,
    schema_version: str,
    snapshot_id: str,
    snapshot_seed_sha256: str,
    integrity_sha256: str,
    registry_version: str,
    registry_hash: str,
    completeness_status: str,
    snapshot: dict[str, Any],
    pack: dict[str, Any],
    catalog: dict[str, Any],
    coverage: dict[str, Any],
    typed_records: list[dict[str, Any]],
    unclassified_records: list[dict[str, Any]],
    record_index: list[dict[str, Any]],
    coverage_records: list[dict[str, Any]],
    provenance_records: list[dict[str, Any]],
) -> None:
    _validate_snapshot_shapes(
        snapshot=snapshot,
        pack=pack,
        catalog=catalog,
        coverage=coverage,
        typed_records=typed_records,
        unclassified_records=unclassified_records,
        record_index=record_index,
        coverage_records=coverage_records,
        provenance_records=provenance_records,
    )
    records = sorted(
        [*typed_records, *unclassified_records],
        key=lambda item: item["record_id"],
    )
    if (
        schema_version != FINANCIAL_DOMAIN_SNAPSHOT_SCHEMA_VERSION
        or snapshot.get("schema_version") != schema_version
        or snapshot.get("contract_version")
        != FINANCIAL_DOMAIN_CONTRACT_VERSION
        or snapshot.get("domain_snapshot_id") != snapshot_id
        or snapshot.get("snapshot_status") != "immutable"
        or snapshot.get("semantic_pack_identity") != pack
        or catalog.get("domain_snapshot_id") != snapshot_id
        or catalog.get("semantic_pack_identity") != pack
        or coverage.get("domain_snapshot_id") != snapshot_id
        or snapshot.get("catalog_ref") != catalog.get("catalog_ref")
        or snapshot.get("coverage_ref") != coverage.get("coverage_ref")
        or snapshot.get("records_total") != len(records)
        or snapshot_id != "findom_" + snapshot_seed_sha256[:32]
    ):
        fail("financial_domain_snapshot_integrity_invalid")
    _validate_hashed_object(
        catalog,
        hash_field="catalog_sha256",
        schema_version=FINANCIAL_DOMAIN_CATALOG_SCHEMA_VERSION,
    )
    _validate_hashed_object(
        coverage,
        hash_field="coverage_sha256",
        schema_version=FINANCIAL_DOMAIN_COVERAGE_SCHEMA_VERSION,
    )
    for record in records:
        expected_schema = (
            FINANCIAL_DOMAIN_TYPED_RECORD_SCHEMA_VERSION
            if record.get("record_kind") == "typed"
            else FINANCIAL_DOMAIN_UNCLASSIFIED_RECORD_SCHEMA_VERSION
        )
        _validate_hashed_object(
            record,
            hash_field="record_sha256",
            schema_version=expected_schema,
        )
        if (
            record.get("domain_snapshot_id") != snapshot_id
            or record.get("semantic_pack_identity") != pack
        ):
            fail("financial_domain_record_authority_invalid")
    record_set = [
        {
            "record_id": item["record_id"],
            "record_sha256": item["record_sha256"],
        }
        for item in records
    ]
    if snapshot.get("record_set_sha256") != sha256_json(record_set):
        fail("financial_domain_record_set_integrity_invalid")
    if (
        len(record_index) != len(records)
        or {item["record_id"] for item in record_index}
        != {item["record_id"] for item in records}
        or coverage.get("declared_source_refs_total")
        != len(coverage_records)
    ):
        fail("financial_domain_snapshot_index_invalid")
    _validate_snapshot_accounting(
        snapshot=snapshot,
        catalog=catalog,
        coverage=coverage,
        records=records,
        record_index=record_index,
        coverage_records=coverage_records,
        provenance_records=provenance_records,
    )
    for item in provenance_records:
        _validate_hashed_object(
            item,
            hash_field="lineage_sha256",
            schema_version=FINANCIAL_DOMAIN_PROVENANCE_SCHEMA_VERSION,
        )
        if item.get("domain_snapshot_id") != snapshot_id:
            fail("financial_domain_provenance_authority_invalid")
    material = snapshot_integrity_material(
        snapshot=snapshot,
        catalog=catalog,
        coverage=coverage,
        typed_records=typed_records,
        unclassified_records=unclassified_records,
        record_index_values=record_index,
        coverage_records=coverage_records,
        provenance_records=provenance_records,
        registry_version=registry_version,
        registry_hash=registry_hash,
        completeness_status=completeness_status,
        snapshot_seed_sha256=snapshot_seed_sha256,
    )
    if integrity_sha256 != sha256_json(material):
        fail("financial_domain_snapshot_integrity_invalid")


def _validate_hashed_object(
    value: dict[str, Any],
    *,
    hash_field: str,
    schema_version: str,
) -> None:
    if value.get("schema_version") != schema_version:
        fail("financial_domain_object_schema_invalid")
    claimed = value.get(hash_field)
    unsigned = dict(value)
    unsigned.pop(hash_field, None)
    if claimed != sha256_json(unsigned):
        fail("financial_domain_object_integrity_invalid")


def _validate_snapshot_shapes(
    *,
    snapshot: dict[str, Any],
    pack: dict[str, Any],
    catalog: dict[str, Any],
    coverage: dict[str, Any],
    typed_records: list[dict[str, Any]],
    unclassified_records: list[dict[str, Any]],
    record_index: list[dict[str, Any]],
    coverage_records: list[dict[str, Any]],
    provenance_records: list[dict[str, Any]],
) -> None:
    if set(pack) != {
        "pack_schema_version",
        "semantic_version",
        "canonical_sha256",
        "managed_asset_ref",
    } or set(snapshot) != {
        "schema_version",
        "contract_version",
        "domain_snapshot_id",
        "snapshot_status",
        "source_extraction_run_refs",
        "gate2_run_refs",
        "semantic_pack_identity",
        "catalog_ref",
        "coverage_ref",
        "records_total",
        "record_set_sha256",
        "access_scope",
        "created_at",
        "expires_at",
    }:
        fail("financial_domain_snapshot_shape_invalid")
    access_scope = snapshot["access_scope"]
    if (
        not isinstance(access_scope, dict)
        or set(access_scope)
        != {
            "access_scope_ref",
            "access_scope_fingerprint",
            "same_user_required",
            "same_case_or_chat_required",
            "same_workspace_required_when_present",
            "source_availability_required",
        }
        or access_scope["same_user_required"] is not True
        or access_scope["same_case_or_chat_required"] is not True
        or access_scope["source_availability_required"] is not True
    ):
        fail("financial_domain_access_scope_invalid")
    validate_timestamp(snapshot["created_at"], field="created_at")
    if snapshot["expires_at"] is not None:
        validate_timestamp(snapshot["expires_at"], field="expires_at")
    if set(catalog) != {
        "schema_version",
        "catalog_ref",
        "domain_snapshot_id",
        "semantic_pack_identity",
        "declared_types",
        "populated_types",
        "typed_records_total",
        "unclassified_records_total",
        "records_total",
        "documents",
        "periods",
        "currencies",
        "catalog_sha256",
    } or set(coverage) != {
        "schema_version",
        "coverage_ref",
        "domain_snapshot_id",
        "coverage_status",
        "declared_source_refs_total",
        "declared_source_refs_sha256",
        "terminal_counts",
        "terminal_ownership_complete",
        "uncovered_source_refs",
        "coverage_sha256",
    }:
        fail("financial_domain_catalog_coverage_shape_invalid")
    for record in typed_records:
        _validate_record_shape(record, typed=True)
    for record in unclassified_records:
        _validate_record_shape(record, typed=False)
    for item in record_index:
        _require_keys(
            item,
            {
                "record_id",
                "record_kind",
                "input_type_id",
                "normalization_run_ref",
                "document_refs",
                "period_keys",
                "currency_keys",
                "classification_status",
                "provenance_ref",
            },
            "financial_domain_record_index_shape_invalid",
        )
    for item in coverage_records:
        _require_keys(
            item,
            {
                "coverage_id",
                "source_scope_ref",
                "normalization_run_ref",
                "document_refs",
                "period_keys",
                "currency_keys",
                "classification_status",
                "input_type_id",
                "terminal_owner_id",
                "scope_accounted",
                "provenance_refs",
            },
            "financial_domain_coverage_record_shape_invalid",
        )
    for item in provenance_records:
        _require_keys(
            item,
            {
                "schema_version",
                "provenance_ref",
                "domain_snapshot_id",
                "document_refs",
                "source_scope_refs",
                "source_refs",
                "source_value_refs",
                "source_evidence_refs",
                "source_package_refs",
                "source_package_integrity_hashes",
                "lineage_sha256",
            },
            "financial_domain_provenance_shape_invalid",
        )


def _validate_record_shape(
    record: dict[str, Any],
    *,
    typed: bool,
) -> None:
    common = {
        "schema_version",
        "record_kind",
        "record_id",
        "domain_snapshot_id",
        "semantic_pack_identity",
        "dimensions",
        "provenance_ref",
        "provenance",
        "record_sha256",
    }
    expected = (
        common | {"input_type_id", "role_values"}
        if typed
        else common | {"source_values", "reason_codes"}
    )
    _require_keys(
        record,
        expected,
        "financial_domain_record_shape_invalid",
    )
    if record["record_kind"] != ("typed" if typed else "unclassified"):
        fail("financial_domain_record_kind_invalid")
    values = (
        record["role_values"] if typed else record["source_values"]
    )
    if not isinstance(values, list) or not values:
        fail("financial_domain_record_values_invalid")
    value_keys = {
        "source_value_ref",
        "source_ref",
        "value_type",
        "literal_value",
        "normalized_value",
        "source_sign",
        "source_evidence_refs",
    }
    if typed:
        value_keys.add("role_id")
    for value in values:
        _require_keys(
            value,
            value_keys,
            "financial_domain_record_value_shape_invalid",
        )
        if (
            not isinstance(value["literal_value"], str)
            or len(value["literal_value"]) > 4096
            or (
                value["normalized_value"] is not None
                and (
                    not isinstance(value["normalized_value"], str)
                    or len(value["normalized_value"]) > 4096
                )
            )
        ):
            fail("financial_domain_record_value_invalid")
    dimensions = record["dimensions"]
    _require_keys(
        dimensions,
        {"document_refs", "periods", "currency_keys"},
        "financial_domain_record_dimensions_invalid",
    )
    for period in dimensions["periods"]:
        _require_keys(
            period,
            {
                "period_key",
                "period_kind",
                "source_literal",
                "start_date",
                "end_date",
                "as_of_date",
            },
            "financial_domain_record_period_invalid",
        )
        if (
            not isinstance(period["source_literal"], str)
            or not period["source_literal"]
            or len(period["source_literal"]) > 512
        ):
            fail("financial_domain_record_period_invalid")


def _validate_snapshot_accounting(
    *,
    snapshot: dict[str, Any],
    catalog: dict[str, Any],
    coverage: dict[str, Any],
    records: list[dict[str, Any]],
    record_index: list[dict[str, Any]],
    coverage_records: list[dict[str, Any]],
    provenance_records: list[dict[str, Any]],
) -> None:
    typed = [
        item for item in records if item["record_kind"] == "typed"
    ]
    unclassified = [
        item
        for item in records
        if item["record_kind"] == "unclassified"
    ]
    if (
        catalog["typed_records_total"] != len(typed)
        or catalog["unclassified_records_total"] != len(unclassified)
        or catalog["records_total"] != len(records)
        or snapshot["records_total"] != len(records)
    ):
        fail("financial_domain_catalog_count_invalid")
    declared_ids = [
        item["input_type_id"] for item in catalog["declared_types"]
    ]
    populated = {
        item["input_type_id"]: item["records_total"]
        for item in catalog["populated_types"]
    }
    expected_populated = {
        input_type_id: sum(
            item["input_type_id"] == input_type_id for item in typed
        )
        for input_type_id in sorted(
            {item["input_type_id"] for item in typed}
        )
    }
    if (
        declared_ids != sorted(set(declared_ids))
        or populated != expected_populated
        or not set(populated) <= set(declared_ids)
    ):
        fail("financial_domain_catalog_type_accounting_invalid")
    index_by_id = {item["record_id"]: item for item in record_index}
    provenance_refs = {
        item["provenance_ref"] for item in provenance_records
    }
    if len(index_by_id) != len(record_index):
        fail("financial_domain_record_index_duplicate")
    for record in records:
        index = index_by_id.get(record["record_id"])
        dimensions = record["dimensions"]
        if (
            index is None
            or index["record_kind"] != record["record_kind"]
            or index["input_type_id"] != record.get("input_type_id")
            or index["document_refs"] != dimensions["document_refs"]
            or index["period_keys"]
            != [
                item["period_key"] for item in dimensions["periods"]
            ]
            or index["currency_keys"] != dimensions["currency_keys"]
            or index["provenance_ref"] != record["provenance_ref"]
            or record["provenance_ref"] not in provenance_refs
        ):
            fail("financial_domain_record_index_invalid")
    status_fields = {
        "typed_input": "typed_source_refs_total",
        "unclassified_financial_input": (
            "unclassified_source_refs_total"
        ),
        "no_financial_input": "no_financial_input_source_refs_total",
        "unsupported": "unsupported_source_refs_total",
    }
    expected_counts = {
        field: sum(
            item["classification_status"] == status
            for item in coverage_records
        )
        for status, field in status_fields.items()
    }
    terminal_counts = coverage["terminal_counts"]
    if (
        coverage["coverage_status"] != "complete"
        or coverage["terminal_ownership_complete"] is not True
        or coverage["uncovered_source_refs"]
        or coverage["declared_source_refs_total"]
        != len(coverage_records)
        or any(
            terminal_counts[field] != count
            for field, count in expected_counts.items()
        )
        or terminal_counts["uncovered_source_refs_total"] != 0
        or terminal_counts["duplicate_terminal_ownership_total"] != 0
        or terminal_counts["ownership_conflicts_total"] != 0
        or any(
            item["scope_accounted"] is not True
            or not set(item["provenance_refs"]) <= provenance_refs
            for item in coverage_records
        )
    ):
        fail("financial_domain_coverage_accounting_invalid")


def _require_keys(
    value: Any,
    expected: set[str],
    code: str,
) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        fail(code)
