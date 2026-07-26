from __future__ import annotations

from typing import Any

from .gate2_financial_domain_contracts import (
    FINANCIAL_DOMAIN_CATALOG_SCHEMA_VERSION,
    FINANCIAL_DOMAIN_COVERAGE_SCHEMA_VERSION,
    FINANCIAL_DOMAIN_PROVENANCE_SCHEMA_VERSION,
    FINANCIAL_DOMAIN_TYPED_RECORD_SCHEMA_VERSION,
    FINANCIAL_DOMAIN_UNCLASSIFIED_RECORD_SCHEMA_VERSION,
    sha256_json,
)
from .gate2_financial_evidence_materialization_contracts import (
    Gate2FinancialEvidenceSourcePackage,
)
from .gate2_financial_evidence_registry import REGISTRY_ID


def terminal(artifact: dict[str, Any]) -> dict[str, Any] | None:
    if artifact["typed_inputs"]:
        return artifact["typed_inputs"][0]
    if artifact["unclassified_inputs"]:
        return artifact["unclassified_inputs"][0]
    return None


def domain_record(
    *,
    snapshot_id: str,
    semantic_pack_identity: dict[str, str],
    artifact: dict[str, Any],
    source_package: Gate2FinancialEvidenceSourcePackage,
    terminal_record: dict[str, Any] | None,
    provenance: dict[str, Any],
) -> dict[str, Any] | None:
    if terminal_record is None:
        return None
    source_values = [
        _source_value(value, include_role=False)
        for value in terminal_record["source_values"]
    ]
    dimensions = _dimensions(
        source_package=source_package,
        terminal_record=terminal_record,
    )
    if artifact["terminal_disposition"] == "typed_input":
        record: dict[str, Any] = {
            "schema_version": FINANCIAL_DOMAIN_TYPED_RECORD_SCHEMA_VERSION,
            "record_kind": "typed",
            "record_id": terminal_record["input_id"],
            "domain_snapshot_id": snapshot_id,
            "semantic_pack_identity": semantic_pack_identity,
            "input_type_id": terminal_record["input_type_id"],
            "role_values": [
                _source_value(value, include_role=True)
                for value in terminal_record["source_values"]
            ],
            "dimensions": dimensions,
            "provenance_ref": provenance["provenance_ref"],
            "provenance": None,
        }
    else:
        record = {
            "schema_version": (
                FINANCIAL_DOMAIN_UNCLASSIFIED_RECORD_SCHEMA_VERSION
            ),
            "record_kind": "unclassified",
            "record_id": terminal_record["unclassified_input_id"],
            "domain_snapshot_id": snapshot_id,
            "semantic_pack_identity": semantic_pack_identity,
            "source_values": source_values,
            "reason_codes": [terminal_record["gap_reason_code"]],
            "dimensions": dimensions,
            "provenance_ref": provenance["provenance_ref"],
            "provenance": None,
        }
    record["record_sha256"] = sha256_json(record)
    return record


def provenance_record(
    *,
    snapshot_id: str,
    source_package: Gate2FinancialEvidenceSourcePackage,
    terminal_record: dict[str, Any] | None,
) -> dict[str, Any]:
    values = (
        terminal_record["source_values"]
        if terminal_record is not None
        else [
            {
                "source_value_ref": value.source_value_ref,
                "source_ref": value.source_ref,
                "source_evidence_refs": list(
                    value.source_evidence_refs
                ),
                "lineage": {
                    "document_ref": value.lineage.document_ref,
                    "page_ref": value.lineage.page_ref,
                    "table_ref": value.lineage.table_ref,
                    "row_ref": value.lineage.row_ref,
                    "cell_ref": value.lineage.cell_ref,
                    "text_segment_ref": value.lineage.text_segment_ref,
                },
            }
            for value in source_package.source_values
        ]
    )
    material = {
        "document_refs": [source_package.document_ref],
        "source_scope_refs": [source_package.source_scope_ref],
        "source_refs": sorted(
            {str(value["source_ref"]) for value in values}
        ),
        "source_value_refs": sorted(
            {str(value["source_value_ref"]) for value in values}
        ),
        "source_evidence_refs": sorted(
            {
                *source_package.source_evidence_refs,
                *(
                    ref
                    for value in values
                    for ref in value["source_evidence_refs"]
                ),
            }
        ),
        "source_package_refs": [source_package.package_ref],
        "source_package_integrity_hashes": [
            source_package.integrity_hash
        ],
        "lineage": sorted(
            (
                {
                    "source_value_ref": value["source_value_ref"],
                    "lineage": value["lineage"],
                }
                for value in values
            ),
            key=lambda item: item["source_value_ref"],
        ),
    }
    provenance_ref = "findomprov_" + sha256_json(
        {
            "domain_snapshot_id": snapshot_id,
            "material": material,
        }
    )[:32]
    result = {
        "schema_version": FINANCIAL_DOMAIN_PROVENANCE_SCHEMA_VERSION,
        "provenance_ref": provenance_ref,
        "domain_snapshot_id": snapshot_id,
        **{key: value for key, value in material.items() if key != "lineage"},
    }
    result["lineage_sha256"] = sha256_json(result)
    return result


def record_index(
    *,
    record: dict[str, Any],
    source_package: Gate2FinancialEvidenceSourcePackage,
    terminal_disposition: str,
) -> dict[str, Any]:
    dimensions = record["dimensions"]
    return {
        "record_id": record["record_id"],
        "record_kind": record["record_kind"],
        "input_type_id": record.get("input_type_id"),
        "normalization_run_ref": source_package.normalization_run_ref,
        "document_refs": dimensions["document_refs"],
        "period_keys": [
            item["period_key"] for item in dimensions["periods"]
        ],
        "currency_keys": dimensions["currency_keys"],
        "classification_status": terminal_disposition,
        "provenance_ref": record["provenance_ref"],
    }


def coverage_record(
    *,
    artifact: dict[str, Any],
    source_package: Gate2FinancialEvidenceSourcePackage,
    provenance_ref: str,
    record: dict[str, Any] | None,
) -> dict[str, Any]:
    dimensions = (
        record["dimensions"]
        if record is not None
        else {
            "document_refs": [source_package.document_ref],
            "periods": [],
            "currency_keys": [],
        }
    )
    return {
        "coverage_id": artifact["coverage"]["coverage_id"],
        "source_scope_ref": source_package.source_scope_ref,
        "normalization_run_ref": source_package.normalization_run_ref,
        "document_refs": dimensions["document_refs"],
        "period_keys": [
            item["period_key"] for item in dimensions["periods"]
        ],
        "currency_keys": dimensions["currency_keys"],
        "classification_status": artifact["terminal_disposition"],
        "input_type_id": (
            record.get("input_type_id") if record is not None else None
        ),
        "terminal_owner_id": (
            record["record_id"]
            if record is not None
            else artifact["coverage"]["coverage_id"]
        ),
        "scope_accounted": artifact["coverage"]["scope_accounted"],
        "provenance_refs": [provenance_ref],
    }


def domain_coverage(
    *,
    snapshot_id: str,
    coverage_records: list[dict[str, Any]],
) -> dict[str, Any]:
    declared = sorted(
        item["source_scope_ref"] for item in coverage_records
    )
    dispositions = {
        "typed_input": "typed_source_refs_total",
        "unclassified_financial_input": (
            "unclassified_source_refs_total"
        ),
        "no_financial_input": "no_financial_input_source_refs_total",
        "unsupported": "unsupported_source_refs_total",
    }
    terminal_counts = {
        field: sum(
            item["classification_status"] == status
            for item in coverage_records
        )
        for status, field in dispositions.items()
    }
    terminal_counts.update(
        {
            "uncovered_source_refs_total": 0,
            "duplicate_terminal_ownership_total": 0,
            "ownership_conflicts_total": 0,
        }
    )
    result = {
        "schema_version": FINANCIAL_DOMAIN_COVERAGE_SCHEMA_VERSION,
        "coverage_ref": "findomcov_"
        + sha256_json(
            {
                "domain_snapshot_id": snapshot_id,
                "declared_source_refs": declared,
            }
        )[:32],
        "domain_snapshot_id": snapshot_id,
        "coverage_status": "complete",
        "declared_source_refs_total": len(declared),
        "declared_source_refs_sha256": sha256_json(declared),
        "terminal_counts": terminal_counts,
        "terminal_ownership_complete": True,
        "uncovered_source_refs": [],
    }
    result["coverage_sha256"] = sha256_json(result)
    return result


def domain_catalog(
    *,
    snapshot_id: str,
    pack_identity: dict[str, str],
    type_contracts: tuple[Any, ...],
    typed_records: list[dict[str, Any]],
    unclassified_records: list[dict[str, Any]],
) -> dict[str, Any]:
    records = [*typed_records, *unclassified_records]
    declared_types = [
        {
            "input_type_id": contract.input_type_id,
            "title": contract.title,
            "semantic_class": contract.semantic_class,
            "lifecycle": contract.lifecycle,
        }
        for contract in type_contracts
    ]
    populated_types = [
        {
            "input_type_id": input_type_id,
            "records_total": sum(
                record.get("input_type_id") == input_type_id
                for record in typed_records
            ),
        }
        for input_type_id in sorted(
            {
                str(record["input_type_id"])
                for record in typed_records
            }
        )
    ]
    result = {
        "schema_version": FINANCIAL_DOMAIN_CATALOG_SCHEMA_VERSION,
        "catalog_ref": "findomcat_"
        + sha256_json(
            {
                "domain_snapshot_id": snapshot_id,
                "semantic_pack_identity": pack_identity,
            }
        )[:32],
        "domain_snapshot_id": snapshot_id,
        "semantic_pack_identity": pack_identity,
        "declared_types": declared_types,
        "populated_types": populated_types,
        "typed_records_total": len(typed_records),
        "unclassified_records_total": len(unclassified_records),
        "records_total": len(records),
        "documents": _dimension_counts(
            records,
            values=lambda record: record["dimensions"][
                "document_refs"
            ],
        ),
        "periods": _dimension_counts(
            records,
            values=lambda record: [
                item["period_key"]
                for item in record["dimensions"]["periods"]
            ],
        ),
        "currencies": _dimension_counts(
            records,
            values=lambda record: record["dimensions"][
                "currency_keys"
            ],
        ),
    }
    result["catalog_sha256"] = sha256_json(result)
    return result


def snapshot_integrity_material(
    *,
    snapshot: dict[str, Any],
    catalog: dict[str, Any],
    coverage: dict[str, Any],
    typed_records: list[dict[str, Any]],
    unclassified_records: list[dict[str, Any]],
    record_index_values: list[dict[str, Any]],
    coverage_records: list[dict[str, Any]],
    provenance_records: list[dict[str, Any]],
    registry_version: str,
    registry_hash: str,
    completeness_status: str,
    snapshot_seed_sha256: str,
) -> dict[str, Any]:
    return {
        "snapshot": snapshot,
        "catalog": catalog,
        "coverage": coverage,
        "typed_records": typed_records,
        "unclassified_records": unclassified_records,
        "record_index": record_index_values,
        "coverage_records": coverage_records,
        "provenance_records": provenance_records,
        "registry": {
            "registry_id": REGISTRY_ID,
            "registry_version": registry_version,
            "registry_hash": registry_hash,
        },
        "completeness_status": completeness_status,
        "snapshot_seed_sha256": snapshot_seed_sha256,
    }


def _source_value(
    value: dict[str, Any],
    *,
    include_role: bool,
) -> dict[str, Any]:
    result = {
        "source_value_ref": value["source_value_ref"],
        "source_ref": value["source_ref"],
        "value_type": value["value_type"],
        "literal_value": value["literal_value"],
        "normalized_value": value["normalized_comparison_value"],
        "source_sign": value["source_sign"],
        "source_evidence_refs": sorted(
            set(value["source_evidence_refs"])
        ),
    }
    if include_role:
        return {"role_id": value["role_id"], **result}
    return result


def _dimensions(
    *,
    source_package: Gate2FinancialEvidenceSourcePackage,
    terminal_record: dict[str, Any],
) -> dict[str, Any]:
    values_by_role = {
        value["role_id"]: value
        for value in terminal_record["source_values"]
    }
    periods = []
    for role_id, normalized in sorted(
        terminal_record["date_period"].items()
    ):
        source = values_by_role[role_id]
        period_kind = "source_literal_only"
        start_date = None
        end_date = None
        as_of_date = None
        if role_id in {"as_of_date", "event_date"}:
            period_kind = "instant"
            as_of_date = normalized
        elif role_id == "start_date":
            period_kind = "range"
            start_date = normalized
        elif role_id in {"end_date", "period_end"}:
            period_kind = "range"
            end_date = normalized
        elif role_id == "period":
            period_kind = "named_period"
        periods.append(
            {
                "period_key": str(normalized),
                "period_kind": period_kind,
                "source_literal": source["literal_value"],
                "start_date": start_date,
                "end_date": end_date,
                "as_of_date": as_of_date,
            }
        )
    return {
        "document_refs": [source_package.document_ref],
        "periods": periods,
        "currency_keys": sorted(
            {
                str(value)
                for role, value in terminal_record[
                    "currency_unit"
                ].items()
                if role == "currency"
            }
        ),
    }


def _dimension_counts(
    records: list[dict[str, Any]],
    *,
    values: Any,
) -> list[dict[str, Any]]:
    keys = sorted(
        {
            str(key)
            for record in records
            for key in values(record)
        }
    )
    return [
        {
            "key": key,
            "records_total": sum(
                key in values(record) for record in records
            ),
        }
        for key in keys
    ]
