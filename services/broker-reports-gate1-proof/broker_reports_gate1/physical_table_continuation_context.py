"""Project one verified physical-table sidecar onto immutable Canonical ids.

This is an evidence adapter, not a semantic owner: it neither reads storage nor
interprets tables.  Its caller supplies already ACL-checked records and payload.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .artifact_models import (
    PHYSICAL_TABLE_CONTINUATION_ARTIFACT_TYPE,
    ArtifactRecord,
)
from .physical_table_continuation import (
    PhysicalTableContinuationError,
    validate_physical_table_continuation_sidecar,
)


PHYSICAL_TABLE_CONTINUATION_CONTEXT_SCHEMA_VERSION = (
    "broker_reports_physical_table_continuation_context_v1"
)


class PhysicalTableContinuationContextError(ValueError):
    """The sidecar cannot be safely bound to this Canonical version."""


def bind_physical_table_continuation_context(
    *,
    canonical: Mapping[str, Any],
    canonical_binding: Mapping[str, Any],
    source_record: ArtifactRecord,
    sidecar_record: ArtifactRecord,
    sidecar: Mapping[str, Any],
) -> dict[str, Any]:
    """Return opaque Canonical table links for one exact private source batch.

    The binding is deliberately entirely identifier-based.  It never compares
    page layout, Markdown, titles, table contents, headers or financial terms.
    """

    _validate_records(
        canonical_binding=canonical_binding,
        source_record=source_record,
        sidecar_record=sidecar_record,
    )
    try:
        validated = validate_physical_table_continuation_sidecar(sidecar)
    except PhysicalTableContinuationError as exc:
        raise PhysicalTableContinuationContextError(
            "physical_table_continuation_context_sidecar_invalid"
        ) from exc
    if (
        validated["normalization_run_id"] != source_record.normalization_run_id
        or validated["document_id"] != source_record.document_id
        or validated["source_pdf_sha256"]
        != canonical_binding["source_sha256"]
    ):
        raise PhysicalTableContinuationContextError(
            "physical_table_continuation_context_binding_stale"
        )

    table_ids_by_unit = _table_ids_by_source_unit(canonical)
    links: list[dict[str, str]] = []
    for link in validated["links"]:
        parent_id = _unique_table_id(
            table_ids_by_unit, link["parent"]["unit_ref"]
        )
        child_id = _unique_table_id(
            table_ids_by_unit, link["child"]["unit_ref"]
        )
        if parent_id == child_id:
            raise PhysicalTableContinuationContextError(
                "physical_table_continuation_context_endpoint_collapsed"
            )
        links.append(
            {
                "parent_table_node_id": parent_id,
                "child_table_node_id": child_id,
            }
        )
    if not links or len(links) != len(
        {(item["parent_table_node_id"], item["child_table_node_id"]) for item in links}
    ):
        raise PhysicalTableContinuationContextError(
            "physical_table_continuation_context_links_invalid"
        )
    return {
        "schema_version": PHYSICAL_TABLE_CONTINUATION_CONTEXT_SCHEMA_VERSION,
        "sidecar_artifact_ref": sidecar_record.artifact_id,
        "sidecar_id": validated["sidecar_id"],
        "source_binding": {
            "normalization_run_id": source_record.normalization_run_id,
            "document_id": source_record.document_id,
            "source_artifact_ref": source_record.artifact_id,
            "source_sha256": canonical_binding["source_sha256"],
            "canonical_version_id": canonical_binding["canonical_version_id"],
            "canonical_root_sha256": canonical_binding["canonical_root_sha256"],
        },
        "links": links,
    }


def _validate_records(
    *,
    canonical_binding: Mapping[str, Any],
    source_record: ArtifactRecord,
    sidecar_record: ArtifactRecord,
) -> None:
    required_binding = {
        "document_id",
        "canonical_version_id",
        "canonical_root_sha256",
        "source_artifact_ref",
        "source_sha256",
    }
    if (
        not isinstance(canonical_binding, Mapping)
        or set(canonical_binding) != required_binding
        or not all(isinstance(canonical_binding[key], str) and canonical_binding[key] for key in required_binding)
        or source_record.artifact_id != canonical_binding["source_artifact_ref"]
        or source_record.document_id != canonical_binding["document_id"]
        or sidecar_record.artifact_type
        != PHYSICAL_TABLE_CONTINUATION_ARTIFACT_TYPE
        or sidecar_record.visibility != "private_case"
        or sidecar_record.storage_backend != "project_artifact_payload"
        or sidecar_record.document_id != source_record.document_id
        or sidecar_record.normalization_run_id != source_record.normalization_run_id
        or sidecar_record.user_id != source_record.user_id
        or sidecar_record.case_id != source_record.case_id
        or sidecar_record.chat_id != source_record.chat_id
        or sidecar_record.workspace_model_id != source_record.workspace_model_id
        or sidecar_record.source_file_ref != source_record.source_file_ref
    ):
        raise PhysicalTableContinuationContextError(
            "physical_table_continuation_context_record_binding_invalid"
        )


def _table_ids_by_source_unit(canonical: Mapping[str, Any]) -> dict[str, set[str]]:
    nodes = canonical.get("nodes")
    provenance = canonical.get("provenance")
    if not isinstance(nodes, list) or not isinstance(provenance, list):
        raise PhysicalTableContinuationContextError(
            "physical_table_continuation_context_canonical_invalid"
        )
    provenance_by_id: dict[str, Mapping[str, Any]] = {}
    for item in provenance:
        if not isinstance(item, Mapping):
            raise PhysicalTableContinuationContextError(
                "physical_table_continuation_context_canonical_invalid"
            )
        provenance_id = item.get("provenance_id")
        if not isinstance(provenance_id, str) or not provenance_id or provenance_id in provenance_by_id:
            raise PhysicalTableContinuationContextError(
                "physical_table_continuation_context_canonical_invalid"
            )
        provenance_by_id[provenance_id] = item
    result: dict[str, set[str]] = {}
    for node in nodes:
        if not isinstance(node, Mapping) or node.get("node_type") != "TABLE":
            continue
        node_id = node.get("node_id")
        source_refs = node.get("source_refs")
        if not isinstance(node_id, str) or not node_id or not isinstance(source_refs, list):
            raise PhysicalTableContinuationContextError(
                "physical_table_continuation_context_canonical_invalid"
            )
        for source_ref in source_refs:
            locator = (provenance_by_id.get(str(source_ref)) or {}).get(
                "source_locator"
            )
            unit_ref = locator.get("source_unit_ref") if isinstance(locator, Mapping) else None
            if isinstance(unit_ref, str) and unit_ref:
                result.setdefault(unit_ref, set()).add(node_id)
    return result


def _unique_table_id(table_ids_by_unit: Mapping[str, set[str]], unit_ref: Any) -> str:
    candidates = table_ids_by_unit.get(unit_ref) if isinstance(unit_ref, str) else None
    if not candidates:
        raise PhysicalTableContinuationContextError(
            "physical_table_continuation_context_endpoint_unmapped"
        )
    if len(candidates) != 1:
        raise PhysicalTableContinuationContextError(
            "physical_table_continuation_context_endpoint_ambiguous"
        )
    return next(iter(candidates))
