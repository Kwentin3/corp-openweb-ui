from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

from .full_source import FullSourceArtifactFactory
from .logical_row_table_recovery import (
    LogicalRowTableFactory,
    LogicalRowTableRecoveryResult,
    logical_table_block_id,
)
from .managed_document_contracts_v2 import (
    ManagedDocumentContractV2Validator,
    ManagedDocumentV2,
)


MANAGED_PDF_V2_BUILDER_VERSION = (
    "broker_reports_managed_pdf_document_v2_builder_v1"
)
SAFE_BUILD_DIAGNOSTICS_SCHEMA_VERSION = (
    "broker_reports_managed_pdf_document_v2_build_safe_v1"
)
PRIVATE_BUILD_DIAGNOSTICS_SCHEMA_VERSION = (
    "broker_reports_managed_pdf_document_v2_build_private_v1"
)
_SOURCE_BOUND_RECOVERY_ONLY_SOURCE_PART_FIELDS = frozenset(
    {
        "source_bound_scope_ref",
        "source_bound_binding_status",
        "source_bound_structural_authority",
        "source_bound_proposal_sha256",
        "source_bound_raster_manifest_hash",
        "source_bound_receipt_title_word_refs",
        "source_bound_receipt_header_word_ref_groups",
        "source_bound_receipt_body_word_refs",
        "source_bound_title_word_refs",
        "source_bound_header_status",
        "source_bound_header_word_ref_groups",
        "source_bound_body_word_refs",
    }
)

FACTORY_REQUIRED = (
    "ManagedPdfDocumentV2Factory.create is the sole inactive PDF to Managed "
    "Document v2 orchestration route"
)
FORBIDDEN = (
    "The v2 builder must not read PdfLayoutUnitBuilder units, historical grid "
    "owners, provider output, visual gold, product routes, or generated bundles"
)


class ManagedPdfDocumentV2Error(ValueError):
    """Raised when the inactive v2 document cannot be assembled exactly."""


@dataclass(frozen=True)
class ManagedPdfDocumentV2Config:
    created_at: str = "2026-08-02T00:00:00Z"
    profile_id: str = "broker_reports_managed_document_v2"


@dataclass(frozen=True)
class ManagedPdfDocumentV2BuildResult:
    status: str
    managed_document: ManagedDocumentV2
    safe_diagnostics: dict[str, Any]
    private_diagnostics: dict[str, Any]


class ManagedPdfDocumentV2Factory:
    """Compose the established FullSource, recovery and v2 contract owners."""

    def __init__(
        self,
        config: ManagedPdfDocumentV2Config | None = None,
    ) -> None:
        self.config = config or ManagedPdfDocumentV2Config()

    def create(self, schema: Mapping[str, Any]) -> "ManagedPdfDocumentV2Builder":
        if not self.config.created_at or not self.config.profile_id:
            raise ManagedPdfDocumentV2Error(
                "managed_pdf_v2_config_invalid"
            )
        validated_schema = copy.deepcopy(dict(schema))
        ManagedDocumentContractV2Validator(validated_schema)
        schema_json = json.dumps(
            validated_schema,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return ManagedPdfDocumentV2Builder(
            config=self.config,
            schema_json=schema_json,
        )


class ManagedPdfDocumentV2Builder:
    __slots__ = ("config", "_schema_json")

    def __init__(
        self,
        *,
        config: ManagedPdfDocumentV2Config,
        schema_json: bytes,
    ) -> None:
        self.config = config
        self._schema_json = schema_json

    def build(
        self,
        content_bytes: bytes,
        *,
        source_artifact_ref: str | None = None,
    ) -> ManagedPdfDocumentV2BuildResult:
        return self._build_owned_source(
            content_bytes=content_bytes,
            source_artifact_ref=source_artifact_ref,
            source_bound_scope_requests=(),
        )

    def build_with_source_bound_scopes(
        self,
        content_bytes: bytes,
        *,
        source_artifact_ref: str | None = None,
        source_bound_scope_requests: tuple[Mapping[str, Any], ...],
    ) -> ManagedPdfDocumentV2BuildResult:
        """Build once and bind raw visual scope requests in the same call."""

        if not source_bound_scope_requests:
            raise ManagedPdfDocumentV2Error(
                "managed_pdf_v2_source_bound_scope_requests_invalid"
            )
        return self._build_owned_source(
            content_bytes=content_bytes,
            source_artifact_ref=source_artifact_ref,
            source_bound_scope_requests=source_bound_scope_requests,
        )

    def _build_owned_source(
        self,
        *,
        content_bytes: bytes,
        source_artifact_ref: str | None,
        source_bound_scope_requests: tuple[Mapping[str, Any], ...],
    ) -> ManagedPdfDocumentV2BuildResult:
        if not isinstance(content_bytes, bytes) or not content_bytes:
            raise ManagedPdfDocumentV2Error(
                "managed_pdf_v2_source_bytes_invalid"
            )
        private_ref = _private_source_ref(source_artifact_ref)
        if not isinstance(source_bound_scope_requests, tuple):
            raise ManagedPdfDocumentV2Error(
                "managed_pdf_v2_source_bound_scope_requests_invalid"
            )
        document_id = _identifier(
            "document_pdf",
            ["private_source_artifact_identity", private_ref],
        )
        source_checksum = hashlib.sha256(content_bytes).hexdigest()
        full_source = FullSourceArtifactFactory().create().build(
            normalization_run_id=f"normrun_doc6_{source_checksum[:24]}",
            document_id=document_id,
            profile_id=self.config.profile_id,
            container_format="pdf",
            content_bytes=content_bytes,
            source_checksum_sha256=source_checksum,
        )
        payload = _sole_complete_pdf_payload(full_source)
        projection = payload.get("pdf_text_layer_projection")
        if not isinstance(projection, Mapping):
            raise ManagedPdfDocumentV2Error(
                "managed_pdf_v2_full_source_projection_missing"
            )
        recovery_runtime = LogicalRowTableFactory().create()
        if source_bound_scope_requests:
            recovered: LogicalRowTableRecoveryResult = (
                recovery_runtime.recover_with_source_bound_scopes(
                    full_source_payload=payload,
                    source_checksum_sha256=source_checksum,
                    private_evidence_ref=private_ref,
                    source_bound_scope_requests=source_bound_scope_requests,
                )
            )
        else:
            recovered = recovery_runtime.recover(
                projection,
                source_checksum_sha256=source_checksum,
                private_evidence_ref=private_ref,
            )
        recovered, reviewed_plan = _managed_document_recovery_projection(
            recovered,
            allow_reviewed=bool(source_bound_scope_requests),
        )
        candidate, assembly = _assemble_document(
            projection=projection,
            recovered=recovered,
            document_id=document_id,
            content_size=len(content_bytes),
            source_checksum_sha256=source_checksum,
            private_source_ref=private_ref,
            created_at=self.config.created_at,
        )
        validator = ManagedDocumentContractV2Validator(
            json.loads(self._schema_json.decode("utf-8"))
        )
        managed_document = (
            validator._seal_reviewed_source_bound(
                candidate,
                expected_reviewed_source_bound=reviewed_plan,
            )
            if reviewed_plan
            else validator.seal(candidate)
        )
        status = str(managed_document.payload["quality"]["status"])
        safe_diagnostics = {
            "schema_version": SAFE_BUILD_DIAGNOSTICS_SCHEMA_VERSION,
            "builder_version": MANAGED_PDF_V2_BUILDER_VERSION,
            "status": status,
            "pages_total": assembly["pages_total"],
            "source_words_total": assembly["source_words_total"],
            "logical_tables_total": assembly["logical_tables_total"],
            "logical_rows_total": assembly["logical_rows_total"],
            "paragraph_blocks_total": assembly["paragraph_blocks_total"],
            "table_words_total": assembly["table_words_total"],
            "paragraph_words_total": assembly["paragraph_words_total"],
            "unowned_words_total": 0,
            "multiple_word_owners_total": 0,
            "paragraph_table_overlap_total": 0,
            "factory_route": [
                "ManagedPdfDocumentV2Factory.create",
                "FullSourceArtifactFactory.create",
                "LogicalRowTableFactory.create",
                "ManagedDocumentContractV2Validator.seal",
            ],
            "canonical_projection_field": (
                "FullSourceBuildResult.payloads[0]."
                "pdf_text_layer_projection"
            ),
            "pdf_layout_units_consumed": 0,
            "grid_owner_calls": 0,
            "provider_calls_total": 0,
            "product_route_connected": False,
            "generated_bundle_connected": False,
            "private_values_included": False,
            "managed_document_schema_canonical_sha256": (
                validator.schema_canonical_sha256
            ),
            "managed_document_integrity_sha256": (
                managed_document.integrity_sha256
            ),
        }
        private_diagnostics = {
            "schema_version": PRIVATE_BUILD_DIAGNOSTICS_SCHEMA_VERSION,
            "builder_version": MANAGED_PDF_V2_BUILDER_VERSION,
            "document_id": document_id,
            "source_checksum_sha256": source_checksum,
            "private_source_ref": private_ref,
            "full_source_payload_ref": payload.get("source_payload_ref"),
            "full_source_summary": copy.deepcopy(
                getattr(full_source, "summary", {})
            ),
            "recovery_schema_version": recovered.schema_version,
            "recovery_policy_version": recovered.recovery_policy_version,
            "recovery_diagnostics": copy.deepcopy(recovered.diagnostics),
            "paragraph_owned_word_refs": list(
                recovered.paragraph_owned_word_refs
            ),
            "unowned_word_refs": list(recovered.unowned_word_refs),
            "table_ids": [
                str(table["table_id"]) for table in recovered.tables
            ],
            "managed_document_integrity_sha256": (
                managed_document.integrity_sha256
            ),
        }
        return ManagedPdfDocumentV2BuildResult(
            status=status,
            managed_document=managed_document,
            safe_diagnostics=safe_diagnostics,
            private_diagnostics=private_diagnostics,
        )


def _private_source_ref(value: str | None) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 180
    ):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_private_source_ref_required"
        )
    return value


def _managed_document_recovery_projection(
    recovered: LogicalRowTableRecoveryResult,
    *,
    allow_reviewed: bool,
) -> tuple[LogicalRowTableRecoveryResult, tuple[dict[str, Any], ...]]:
    """Adapt same-call receipt transport into inspectable v2 provenance."""

    if _recovery_contains_ready_reviewed_evidence(recovered):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_ready_reviewed_evidence_forbidden"
        )
    if not allow_reviewed and _recovery_contains_source_bound_fields(recovered):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_reviewed_source_bound_legacy_forbidden"
        )
    tables = copy.deepcopy(recovered.tables)
    anchor_by_id = {
        str(anchor.get("anchor_id") or ""): anchor
        for anchor in recovered.anchors
        if isinstance(anchor, dict)
    }
    for table in tables:
        reviewed_refs_by_role = {
            "TABLE_TITLE": set(),
            "COLUMN_HEADER": set(),
            "DATA": set(),
        }
        for source_part in table.get("source_parts") or []:
            if not isinstance(source_part, dict):
                continue
            scope_ref = source_part.get("source_bound_scope_ref")
            binding_status = source_part.get("source_bound_binding_status")
            proposal_sha256 = source_part.get("source_bound_proposal_sha256")
            raster_sha256 = source_part.get(
                "source_bound_raster_manifest_hash"
            )
            title_refs = list(
                source_part.get("source_bound_receipt_title_word_refs") or []
            )
            header_groups = list(
                source_part.get("source_bound_receipt_header_word_ref_groups")
                or []
            )
            header_refs = [ref for group in header_groups for ref in group]
            body_refs = list(
                source_part.get("source_bound_receipt_body_word_refs") or []
            )
            accepted_structural = (
                source_part.get("source_bound_structural_authority") is True
                and binding_status == "BOUND"
                and source_part.get("source_bound_header_status") == "PRESENT"
                and list(
                    source_part.get("source_bound_header_word_ref_groups")
                    or []
                )
                == header_groups
                and list(source_part.get("source_bound_body_word_refs") or [])
                == body_refs
                and list(source_part.get("source_bound_title_word_refs") or [])
                == title_refs
            )
            if all(
                isinstance(value, str) and value
                for value in (scope_ref, proposal_sha256, raster_sha256)
            ):
                evidence = {
                    "binding_status": binding_status,
                    "scope_receipt_ref": scope_ref,
                    "proposal_sha256": proposal_sha256,
                    "raster_manifest_sha256": raster_sha256,
                    "title_word_refs": title_refs,
                    "header_word_refs": header_refs,
                    "body_word_refs": body_refs,
                }
                if accepted_structural:
                    source_part["reviewed_source_bound_evidence"] = {
                        "origin": "REVIEWED_SOURCE_BOUND",
                        **evidence,
                    }
                    reviewed_refs_by_role["TABLE_TITLE"].update(title_refs)
                    reviewed_refs_by_role["COLUMN_HEADER"].update(header_refs)
                    reviewed_refs_by_role["DATA"].update(body_refs)
                else:
                    source_part["source_bound_audit_evidence"] = {
                        "structural_authority": False,
                        **evidence,
                    }
            for field in _SOURCE_BOUND_RECOVERY_ONLY_SOURCE_PART_FIELDS:
                source_part.pop(field, None)
        for row in table.get("ordered_rows") or []:
            if not isinstance(row, dict):
                continue
            role = str(row.get("role") or "")
            reviewed_refs = reviewed_refs_by_role.get(role, set())
            row_word_refs = _row_word_refs(row, anchor_by_id=anchor_by_id)
            if reviewed_refs and row_word_refs and row_word_refs <= reviewed_refs:
                row["role_origin"] = "REVIEWED_SOURCE_BOUND"
                for entry in row.get("entries") or []:
                    if isinstance(entry, dict):
                        entry["origin"] = "REVIEWED_SOURCE_BOUND"
    return replace(recovered, tables=tables), _reviewed_source_bound_plan(tables)


def _recovery_contains_source_bound_fields(
    recovered: LogicalRowTableRecoveryResult,
) -> bool:
    return any(
        isinstance(part, Mapping)
        and any(str(key).startswith("source_bound_") for key in part)
        for table in recovered.tables
        for part in table.get("source_parts") or []
    )


def _recovery_contains_ready_reviewed_evidence(
    recovered: LogicalRowTableRecoveryResult,
) -> bool:
    return any(
        (
            isinstance(part, Mapping)
            and (
                "reviewed_source_bound_evidence" in part
                or "source_bound_audit_evidence" in part
            )
        )
        for table in recovered.tables
        for part in table.get("source_parts") or []
    ) or any(
        row.get("role_origin") == "REVIEWED_SOURCE_BOUND"
        or any(
            entry.get("origin") == "REVIEWED_SOURCE_BOUND"
            for entry in row.get("entries") or []
        )
        for table in recovered.tables
        for row in table.get("ordered_rows") or []
    )


def _reviewed_source_bound_plan(
    tables: list[dict[str, Any]],
) -> tuple[dict[str, Any], ...]:
    plan: list[dict[str, Any]] = []
    for table in tables:
        rows = list(table.get("ordered_rows") or [])
        row_ordinal = {
            str(row.get("row_id") or ""): index
            for index, row in enumerate(rows)
        }
        for part in table.get("source_parts") or []:
            evidence = part.get("reviewed_source_bound_evidence")
            if not isinstance(evidence, dict):
                continue
            first = row_ordinal[str(part["first_row_id"])]
            last = row_ordinal[str(part["last_row_id"])]
            reviewed_rows = [
                {
                    "row_id": row["row_id"],
                    "role": row["role"],
                    "role_origin": row["role_origin"],
                    "entries": [
                        {
                            "entry_id": entry["entry_id"],
                            "origin": entry["origin"],
                        }
                        for entry in row["entries"]
                    ],
                }
                for row in rows[first : last + 1]
                if row["role_origin"] == "REVIEWED_SOURCE_BOUND"
            ]
            plan.append(
                {
                    "table_id": table["table_id"],
                    "source_part_id": part["source_part_id"],
                    "evidence": copy.deepcopy(evidence),
                    "reviewed_rows": reviewed_rows,
                }
            )
    return tuple(plan)


def _row_word_refs(
    row: Mapping[str, Any],
    *,
    anchor_by_id: Mapping[str, Mapping[str, Any]],
) -> set[str]:
    refs: set[str] = set()
    for anchor_id in row.get("source_anchor_ids") or []:
        anchor = anchor_by_id.get(str(anchor_id))
        locator = anchor.get("locator") if isinstance(anchor, Mapping) else None
        if isinstance(locator, Mapping) and locator.get("source_block_ref"):
            refs.add(str(locator["source_block_ref"]))
    return refs


def _sole_complete_pdf_payload(full_source: Any) -> dict[str, Any]:
    payloads = getattr(full_source, "payloads", None)
    if not isinstance(payloads, list) or len(payloads) != 1:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_full_source_payload_count_invalid"
        )
    payload = payloads[0]
    if not isinstance(payload, dict) or payload.get("container_format") != "pdf":
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_full_source_payload_invalid"
        )
    if (
        payload.get("parser_completeness_status") != "complete"
        or payload.get("text_layer_projection_status") != "complete"
        or payload.get("layout_projection_status") != "complete"
    ):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_full_source_projection_incomplete"
        )
    return payload


def _assemble_document(
    *,
    projection: Mapping[str, Any],
    recovered: LogicalRowTableRecoveryResult,
    document_id: str,
    content_size: int,
    source_checksum_sha256: str,
    private_source_ref: str,
    created_at: str,
) -> tuple[dict[str, Any], dict[str, int]]:
    pages = _dict_items(projection.get("page_inventory"))
    words = _dict_items(projection.get("word_inventory"))
    if not pages:
        raise ManagedPdfDocumentV2Error("managed_pdf_v2_pages_missing")
    page_numbers = [int(item.get("page_number") or 0) for item in pages]
    if sorted(page_numbers) != list(range(1, len(pages) + 1)):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_page_order_invalid"
        )
    page_by_ref = _unique_by_id(pages, "page_ref", "page")
    word_by_ref = _unique_by_id(words, "word_ref", "word")
    bbox_by_ref = _unique_by_id(
        _dict_items(projection.get("bbox_inventory")),
        "bbox_ref",
        "bbox",
    )

    recovery_anchors = copy.deepcopy(recovered.anchors)
    recovery_anchor_by_id = _unique_by_id(
        recovery_anchors,
        "anchor_id",
        "recovery_anchor",
    )
    table_word_refs, word_table_id = _table_word_partition(
        recovered=recovered,
        recovery_anchor_by_id=recovery_anchor_by_id,
        word_by_ref=word_by_ref,
    )
    paragraph_word_refs = set(recovered.paragraph_owned_word_refs)
    all_word_refs = set(word_by_ref)
    if set(recovered.unowned_word_refs):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_unowned_source_words"
        )
    if paragraph_word_refs & table_word_refs:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_paragraph_table_word_overlap"
        )
    if paragraph_word_refs | table_word_refs != all_word_refs:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_source_word_partition_invalid"
        )

    tables_by_id = _unique_by_id(
        copy.deepcopy(recovered.tables),
        "table_id",
        "table",
    )
    if set(tables_by_id) != set(word_table_id.values()):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_table_word_owner_missing"
        )
    table_blocks = {
        table_id: _table_block(table)
        for table_id, table in tables_by_id.items()
    }
    word_group, word_line = _word_source_groups(projection, word_by_ref)
    anchors = recovery_anchors
    blocks: list[dict[str, Any]] = []
    emitted_tables: set[str] = set()

    for page_number in sorted(page_numbers):
        page = next(
            item for item in pages if int(item["page_number"]) == page_number
        )
        boundary, boundary_anchor = _page_boundary(
            page,
            source_checksum_sha256=source_checksum_sha256,
            private_source_ref=private_source_ref,
        )
        anchors.append(boundary_anchor)
        blocks.append(boundary)

        current_key: str | None = None
        current_words: list[dict[str, Any]] = []

        def flush_paragraph() -> None:
            nonlocal current_key, current_words
            if not current_words:
                return
            block, anchor = _paragraph_block(
                page_number=page_number,
                source_group=current_key or "ungrouped",
                words=current_words,
                line_by_word_ref=word_line,
                bbox_by_ref=bbox_by_ref,
                source_checksum_sha256=source_checksum_sha256,
                private_source_ref=private_source_ref,
            )
            anchors.append(anchor)
            blocks.append(block)
            current_key = None
            current_words = []

        for word_ref in _ordered_page_word_refs(
            page,
            page_by_ref=page_by_ref,
            word_by_ref=word_by_ref,
        ):
            table_id = word_table_id.get(word_ref)
            if table_id is not None:
                flush_paragraph()
                if table_id not in emitted_tables:
                    blocks.append(table_blocks[table_id])
                    emitted_tables.add(table_id)
                continue
            if word_ref not in paragraph_word_refs:
                raise ManagedPdfDocumentV2Error(
                    "managed_pdf_v2_source_word_not_routable"
                )
            group = word_group[word_ref]
            if current_words and group != current_key:
                flush_paragraph()
            current_key = group
            current_words.append(word_by_ref[word_ref])
        flush_paragraph()

    if emitted_tables != set(tables_by_id):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_table_not_emitted"
        )
    for ordinal, block in enumerate(blocks):
        block["ordinal"] = ordinal

    anchor_by_id = _unique_by_id(anchors, "anchor_id", "anchor")
    del anchor_by_id
    issues = copy.deepcopy(recovered.issues)
    has_partial_table = any(
        table["completeness_status"] != "COMPLETE"
        for table in tables_by_id.values()
    )
    document = {
        "schema_version": "broker_reports_managed_document_v2",
        "document_id": document_id,
        "information_partition": {
            "CONTENT": ["/metadata", "/blocks/*/content"],
            "PROVENANCE": ["/source", "/anchors", "/relations"],
            "CONTROL": [
                "/information_partition",
                "/blocks/*/restoration",
                "/quality",
            ],
            "PRIVATE_SOURCE": [
                "/document_id",
                "/source/artifact",
                "/anchors/*/locator/private_locator",
                "/blocks/*/content/private_artifact",
                "/geometry_evidence",
                "/source_word_ownership",
            ],
        },
        "source": {
            "information_class": "PROVENANCE",
            "format": "PDF",
            "artifact": _private_ref(
                private_source_ref,
                source_checksum_sha256,
            ),
            "checksum_sha256": source_checksum_sha256,
            "mime_type": "application/pdf",
            "size_bytes": content_size,
            "source_part_count": len(pages),
            "normalizer": {
                "name": "FullSourceArtifactFactory",
                "version": str(projection.get("schema_version") or "unknown"),
            },
            "created_at": created_at,
            "source_details": {
                "kind": "PDF",
                "encrypted_status": "NOT_ENCRYPTED",
            },
        },
        "metadata": _unknown_metadata(),
        "anchors": anchors,
        "geometry_evidence": copy.deepcopy(recovered.geometry_evidence),
        "source_word_ownership": copy.deepcopy(
            recovered.source_word_ownership
        ),
        "blocks": blocks,
        "relations": [],
        "quality": {
            "information_class": "CONTROL",
            "status": "PARTIAL" if has_partial_table else "COMPLETE",
            "source_elements_total": len(blocks),
            "preserved_blocks_total": len(blocks),
            "unknown_blocks_total": 0,
            "unsupported_elements_total": 0,
            "known_losses_total": 0,
            "conflicts_total": 0,
            "unaccounted_context_loss_total": 0,
            "blocking_losses_total": 0,
            "issue_ledger": issues,
            "loss_ledger": [],
        },
    }
    return document, {
        "pages_total": len(pages),
        "source_words_total": len(words),
        "logical_tables_total": len(tables_by_id),
        "logical_rows_total": sum(
            len(table["ordered_rows"])
            for table in tables_by_id.values()
        ),
        "paragraph_blocks_total": sum(
            block["block_type"] == "PARAGRAPH" for block in blocks
        ),
        "table_words_total": len(table_word_refs),
        "paragraph_words_total": len(paragraph_word_refs),
    }


def _table_word_partition(
    *,
    recovered: LogicalRowTableRecoveryResult,
    recovery_anchor_by_id: dict[str, dict[str, Any]],
    word_by_ref: dict[str, dict[str, Any]],
) -> tuple[set[str], dict[str, str]]:
    table_word_refs: set[str] = set()
    word_table_id: dict[str, str] = {}
    source_word_ids: set[str] = set()
    for owner in recovered.source_word_ownership:
        source_word_id = str(owner.get("source_word_id") or "")
        if not source_word_id or source_word_id in source_word_ids:
            raise ManagedPdfDocumentV2Error(
                "managed_pdf_v2_source_word_owner_id_invalid"
            )
        source_word_ids.add(source_word_id)
        if owner.get("owner_status") not in {"OWNED", "PROVEN_DUPLICATE"}:
            raise ManagedPdfDocumentV2Error(
                "managed_pdf_v2_unresolved_table_word_owner"
            )
        anchor = recovery_anchor_by_id.get(
            str(owner.get("source_anchor_id") or "")
        )
        locator = anchor.get("locator") if isinstance(anchor, dict) else None
        word_ref = (
            str(locator.get("source_block_ref") or "")
            if isinstance(locator, dict)
            else ""
        )
        if word_ref not in word_by_ref or word_ref in table_word_refs:
            raise ManagedPdfDocumentV2Error(
                "managed_pdf_v2_multiple_or_unknown_table_word_owner"
            )
        table_word_refs.add(word_ref)
        word_table_id[word_ref] = str(owner.get("table_id") or "")
    return table_word_refs, word_table_id


def _table_block(table: dict[str, Any]) -> dict[str, Any]:
    table_id = str(table["table_id"])
    source_anchor_ids = list(
        dict.fromkeys(
            str(part["region_anchor_id"])
            for part in table["source_parts"]
        )
    )
    if not source_anchor_ids:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_table_source_anchor_missing"
        )
    completeness = str(table["completeness_status"])
    if completeness == "BLOCKED":
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_blocked_table_not_sealable"
        )
    return {
        "block_id": logical_table_block_id(table_id),
        "ordinal": 0,
        "block_type": "TABLE",
        "content": table,
        "source_anchor_ids": source_anchor_ids,
        "restoration": {
            "information_class": "CONTROL",
            "status": "RESTORED" if completeness == "COMPLETE" else "PARTIAL",
            "classification_origin": "DETERMINISTIC_DERIVED",
            "issue_ids": list(table["issues"]),
        },
        "issue_ids": list(table["issues"]),
    }


def _page_boundary(
    page: dict[str, Any],
    *,
    source_checksum_sha256: str,
    private_source_ref: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    page_number = int(page["page_number"])
    page_ref = str(page["page_ref"])
    bbox = _page_bbox(page)
    anchor_id = _identifier("anchor_page", [page_ref, page_number])
    checksum = _sha256_json(
        [source_checksum_sha256, page_ref, page_number]
    )
    anchor = _pdf_anchor(
        anchor_id=anchor_id,
        page_number=page_number,
        source_block_ref=page_ref,
        bbox=bbox,
        checksum_sha256=checksum,
        private_source_ref=private_source_ref,
    )
    block = {
        "block_id": _identifier("block_page", [page_ref, page_number]),
        "ordinal": 0,
        "block_type": "BOUNDARY",
        "content": {
            "information_class": "CONTENT",
            "boundary_type": "PAGE",
            "source_part_index": page_number,
            "label": {
                "information_class": "CONTENT",
                "status": "PRESENT",
                "origin": "DETERMINISTIC_DERIVED",
                "value": f"Page {page_number}",
                "candidates": [],
                "evidence_anchor_ids": [anchor_id],
            },
        },
        "source_anchor_ids": [anchor_id],
        "restoration": {
            "information_class": "CONTROL",
            "status": "RESTORED",
            "classification_origin": "DETERMINISTIC_DERIVED",
            "issue_ids": [],
        },
        "issue_ids": [],
    }
    return block, anchor


def _paragraph_block(
    *,
    page_number: int,
    source_group: str,
    words: list[dict[str, Any]],
    line_by_word_ref: Mapping[str, str],
    bbox_by_ref: dict[str, dict[str, Any]],
    source_checksum_sha256: str,
    private_source_ref: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    word_refs = [str(word["word_ref"]) for word in words]
    texts = [str(word.get("text") or "") for word in words]
    if any(not text for text in texts):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_paragraph_word_text_missing"
        )
    physical_lines: list[list[str]] = []
    current_line_ref: str | None = None
    for word, word_text in zip(words, texts, strict=True):
        word_ref = str(word["word_ref"])
        line_ref = line_by_word_ref[word_ref]
        if line_ref != current_line_ref:
            physical_lines.append([])
            current_line_ref = line_ref
        physical_lines[-1].append(word_text)
    text = "\n".join(" ".join(line) for line in physical_lines).strip()
    bboxes = [
        _bbox_value(bbox_by_ref.get(str(word.get("bbox_ref") or "")))
        for word in words
    ]
    bbox = _merge_bboxes(bboxes)
    anchor_id = _identifier(
        "anchor_paragraph",
        [page_number, source_group, *word_refs],
    )
    checksum = _sha256_json(
        [source_checksum_sha256, page_number, word_refs, texts]
    )
    anchor = _pdf_anchor(
        anchor_id=anchor_id,
        page_number=page_number,
        source_block_ref=source_group,
        bbox=bbox,
        checksum_sha256=checksum,
        private_source_ref=private_source_ref,
    )
    block = {
        "block_id": _identifier(
            "block_paragraph",
            [page_number, source_group, *word_refs],
        ),
        "ordinal": 0,
        "block_type": "PARAGRAPH",
        "content": {
            "information_class": "CONTENT",
            "raw_text": text,
            "join_events": [],
        },
        "source_anchor_ids": [anchor_id],
        "restoration": {
            "information_class": "CONTROL",
            "status": "RESTORED",
            "classification_origin": "DETERMINISTIC_DERIVED",
            "issue_ids": [],
        },
        "issue_ids": [],
    }
    return block, anchor


def _pdf_anchor(
    *,
    anchor_id: str,
    page_number: int,
    source_block_ref: str,
    bbox: list[float],
    checksum_sha256: str,
    private_source_ref: str,
) -> dict[str, Any]:
    private_checksum = _sha256_json(
        [page_number, source_block_ref, bbox]
    )
    return {
        "information_class": "PROVENANCE",
        "anchor_id": anchor_id,
        "source_format": "PDF",
        "checksum_sha256": checksum_sha256,
        "locator": {
            "kind": "PDF",
            "source_part_index": page_number,
            "page": page_number,
            "source_block_ref": source_block_ref,
            "bbox": bbox,
            "private_locator": _private_ref(
                f"{private_source_ref}#{anchor_id}",
                private_checksum,
            ),
        },
    }


def _word_source_groups(
    projection: Mapping[str, Any],
    word_by_ref: dict[str, dict[str, Any]],
) -> tuple[dict[str, str], dict[str, str]]:
    line_owner: dict[str, str] = {}
    for line in _dict_items(projection.get("line_inventory")):
        line_ref = str(line.get("line_ref") or "")
        for word_ref in _strings(line.get("word_refs")):
            if word_ref in line_owner:
                raise ManagedPdfDocumentV2Error(
                    "managed_pdf_v2_multiple_line_word_owners"
                )
            line_owner[word_ref] = line_ref
    block_owner: dict[str, str] = {}
    line_to_block: dict[str, str] = {}
    for block in _dict_items(projection.get("block_inventory")):
        block_ref = str(block.get("block_ref") or "")
        for line_ref in _strings(block.get("line_refs")):
            if line_ref in line_to_block:
                raise ManagedPdfDocumentV2Error(
                    "managed_pdf_v2_multiple_block_line_owners"
                )
            line_to_block[line_ref] = block_ref
    for word_ref, line_ref in line_owner.items():
        block_owner[word_ref] = line_to_block.get(line_ref, line_ref)
    groups = {
        word_ref: block_owner.get(word_ref, f"word_group_{word_ref}")
        for word_ref in word_by_ref
    }
    lines = {
        word_ref: line_owner.get(word_ref, f"word_line_{word_ref}")
        for word_ref in word_by_ref
    }
    return groups, lines


def _ordered_page_word_refs(
    page: dict[str, Any],
    *,
    page_by_ref: dict[str, dict[str, Any]],
    word_by_ref: dict[str, dict[str, Any]],
) -> list[str]:
    page_ref = str(page["page_ref"])
    if page_ref not in page_by_ref:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_page_ref_invalid"
        )
    page_words = [
        word
        for word in word_by_ref.values()
        if str(word.get("page_ref") or "") == page_ref
    ]
    ordered = sorted(
        page_words,
        key=lambda word: (
            _integer_order(word.get("geometry_reading_order")),
            _integer_order(word.get("parser_ordinal")),
            str(word["word_ref"]),
        ),
    )
    return [str(word["word_ref"]) for word in ordered]


def _unknown_metadata() -> dict[str, Any]:
    field = {
        "information_class": "CONTENT",
        "status": "UNKNOWN",
        "origin": "UNKNOWN_ORIGIN",
        "value": None,
        "candidates": [],
        "evidence_anchor_ids": [],
    }
    return {
        "document_type": copy.deepcopy(field),
        "title": copy.deepcopy(field),
        "issuer": copy.deepcopy(field),
        "document_date": copy.deepcopy(field),
        "reporting_period": copy.deepcopy(field),
        "owner_or_account": copy.deepcopy(field),
        "language": copy.deepcopy(field),
        "primary_currency": copy.deepcopy(field),
        "additional": [],
    }


def _private_ref(ref: str, checksum: str) -> dict[str, Any]:
    return {
        "information_class": "PRIVATE_SOURCE",
        "status": "PRESENT",
        "ref": ref,
        "checksum_sha256": checksum,
    }


def _page_bbox(page: Mapping[str, Any]) -> list[float]:
    try:
        width = float(page.get("layout_page_width"))
        height = float(page.get("layout_page_height"))
    except (TypeError, ValueError) as exc:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_page_geometry_invalid"
        ) from exc
    if not math.isfinite(width) or not math.isfinite(height):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_page_geometry_invalid"
        )
    if width <= 0 or height <= 0:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_page_geometry_invalid"
        )
    return [0.0, 0.0, width, height]


def _bbox_value(value: dict[str, Any] | None) -> list[float]:
    raw = value.get("bbox") if isinstance(value, dict) else None
    if not isinstance(raw, list) or len(raw) != 4:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_word_bbox_invalid"
        )
    try:
        bbox = [float(item) for item in raw]
    except (TypeError, ValueError) as exc:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_word_bbox_invalid"
        ) from exc
    if any(not math.isfinite(item) for item in bbox):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_word_bbox_invalid"
        )
    if bbox[2] < bbox[0] or bbox[3] < bbox[1]:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_word_bbox_invalid"
        )
    return bbox


def _merge_bboxes(values: Sequence[list[float]]) -> list[float]:
    if not values:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_paragraph_bbox_missing"
        )
    return [
        min(value[0] for value in values),
        min(value[1] for value in values),
        max(value[2] for value in values),
        max(value[3] for value in values),
    ]


def _unique_by_id(
    values: list[dict[str, Any]],
    key: str,
    label: str,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for value in values:
        identifier = str(value.get(key) or "")
        if not identifier or identifier in result:
            raise ManagedPdfDocumentV2Error(
                f"managed_pdf_v2_{label}_id_invalid"
            )
        result[identifier] = value
    return result


def _dict_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_projection_list_invalid"
        )
    return [item for item in value if isinstance(item, dict)]


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None and str(item)]


def _integer_order(value: Any) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_word_order_invalid"
        ) from exc
    if result < 0:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_word_order_invalid"
        )
    return result


def _identifier(prefix: str, parts: Sequence[Any]) -> str:
    digest = hashlib.sha256(_canonical_bytes(list(parts))).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
