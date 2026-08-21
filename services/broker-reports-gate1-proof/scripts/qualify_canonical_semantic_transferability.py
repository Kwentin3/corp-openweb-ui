#!/usr/bin/env python3
"""Research-only holdout preparation for Semantic Compiler transferability."""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    CanonicalArtifactStoreFactory,
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
    CanonicalReaderFactory,
    CanonicalStorageConfig,
    Gate3StructuralChunkFactory,
    PdfTableIntakeConfig,
    PdfTableIntakeRuntimeFactory,
)
from broker_reports_gate1.artifact_models import ArtifactRecord  # noqa: E402
from broker_reports_gate1.artifact_lifecycle import (  # noqa: E402
    lifecycle_for_visibility,
)
from broker_reports_gate1.artifact_retention import (  # noqa: E402
    build_retention_policy,
)
from broker_reports_gate1.inputs import FileInput  # noqa: E402
from broker_reports_gate1.normalizer import Gate1Normalizer  # noqa: E402
from scripts.local_minimal_native_pdfplumber_plan_g5100 import (  # noqa: E402
    _openwebui_request,
)
import qualify_canonical_minimal_semantic_compiler as msc  # noqa: E402
import qualify_canonical_semantic_task_forms as forms  # noqa: E402
import qualify_canonical_typed_broker_registers_benchmark as typed  # noqa: E402


SCHEMA_VERSION = "broker_semantic_transferability_freeze_v0"
MANIFEST_VERSION = "broker_semantic_transferability_canonical_manifest_v0"
REVIEW_VERSION = "broker_semantic_transferability_review_pack_v0"
TRUTH_VERSION = "broker_semantic_transferability_truth_v0"
RESULT_VERSION = "broker_semantic_transferability_result_v0"
SELECTION_PROFILE = "same_broker_changed_period_plus_cross_broker"
MODEL_ID = "models/gemini-3.5-flash"
PROVIDER_PROFILE = "google_gemini"
RUNS = 3
ALIAS_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")


class TransferabilityError(RuntimeError):
    pass


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TransferabilityError("transferability_json_object_required")
    return value


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _parse_document(value: str) -> dict[str, Any]:
    alias, separator, raw_path = value.partition("=")
    if not separator or ALIAS_RE.fullmatch(alias) is None:
        raise TransferabilityError("transferability_document_argument_invalid")
    path = Path(raw_path).resolve()
    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise TransferabilityError("transferability_document_pdf_invalid")
    payload = path.read_bytes()
    try:
        import fitz
    except ImportError as exc:
        raise TransferabilityError(
            "transferability_pdf_dependency_unavailable"
        ) from exc
    document = fitz.open(stream=payload, filetype="pdf")
    try:
        pages = len(document)
    finally:
        document.close()
    if pages < 1:
        raise TransferabilityError("transferability_document_empty")
    return {
        "alias": alias,
        "path": path,
        "pdf_bytes": payload,
        "source_sha256": _sha256_bytes(payload),
        "size_bytes": len(payload),
        "pages": pages,
    }


def _freeze_contract(documents: list[dict[str, Any]]) -> dict[str, Any]:
    frozen_documents = [
        {
            "alias": item["alias"],
            "source_sha256": item["source_sha256"],
            "size_bytes": item["size_bytes"],
            "pages": item["pages"],
        }
        for item in documents
    ]
    contract = {
        "task_form": "H3+H6+H8+deterministic_materialization",
        "table_types": list(msc.TABLE_TYPES),
        "normalized_roles": list(msc.NORMALIZED_ROLES),
        "residual_codes": list(msc.RESIDUAL_CODES),
        "runs": RUNS,
        "retry": False,
        "repair": False,
        "best_of_n": False,
        "unknown_is_unmapped": True,
        "reuse_requires_exact_structural_fingerprint": True,
        "reuse_on_changed_fingerprint": False,
        "source_values_copied_by_code": True,
        "model_creates_source_literals": False,
        "model_creates_economic_relations": False,
        "production_activation": False,
        "legacy_fallback": False,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "frozen_before_provider_execution": True,
        "selection_profile": SELECTION_PROFILE,
        "development_canonical_root_excluded": forms.FROZEN_CANONICAL_ROOT_SHA256,
        "documents": frozen_documents,
        "semantic_contract": contract,
        "semantic_contract_sha256": _sha256_json(contract),
        "provider_profile": PROVIDER_PROFILE,
        "model_id": MODEL_ID,
        "expected_locator_calls": sum(item["pages"] for item in documents),
        "source_truth_available_to_locator": False,
        "semantic_truth_available_to_locator": False,
        "semantic_truth_available_to_semantic_model": False,
    }


def _source_record(
    *,
    context: ArtifactAccessContext,
    retention: Any,
    document_id: str,
    alias: str,
    source_sha256: str,
    size_bytes: int,
) -> ArtifactRecord:
    source_ref = f"transfer_source_{source_sha256[:24]}"
    return ArtifactRecord(
        artifact_id=source_ref,
        artifact_type="source_file_ref_v0",
        case_id=context.case_id,
        chat_id=context.chat_id,
        user_id=context.user_id,
        workspace_model_id=context.workspace_model_id,
        normalization_run_id=context.normalization_run_id,
        document_id=document_id,
        source_file_ref={
            "provider": "local_transferability_holdout",
            "openwebui_file_id": source_ref,
            "content_type": "application/pdf",
            "size_bytes": size_bytes,
            "source_deleted": False,
        },
        visibility="private_case",
        storage_backend="project_artifact_payload",
        retention_policy=retention,
        access_policy={"requires_user_id": True},
        validation_status="validated",
        lifecycle_status=lifecycle_for_visibility(
            visibility="private_case", validation_status="validated"
        ),
        payload={
            "schema_version": "broker_semantic_transfer_source_v0",
            "alias": alias,
            "source_sha256": source_sha256,
        },
    )


def _prepare_one_canonical(
    *,
    item: dict[str, Any],
    page_results: list[dict[str, Any]],
    store: Any,
) -> dict[str, Any]:
    file_input = FileInput(
        private_ref=f"transferability-{item['alias']}",
        original_filename_private=f"{item['alias']}.pdf",
        mime_type="application/pdf",
        source_kind="research_holdout",
        declared_size_bytes=item["size_bytes"],
        bytes_provider=lambda payload=item["pdf_bytes"]: payload,
        provider_label="local_transferability_holdout",
    )
    normalizer = Gate1Normalizer()
    run_id = normalizer.plan_run_id([file_input])
    normalized = normalizer.normalize(
        [file_input],
        input_context={
            "canonical_gate2_write_enabled": True,
            "pdf_layout_slice2_enabled": True,
            "broker_pdf_neutral_table_profile_v1_enabled": True,
        },
        pdf_table_locator_pages_by_sha256={
            item["source_sha256"]: copy.deepcopy(page_results)
        },
    )
    documents = list(normalized.package["document_inventory"]["documents"])
    if len(documents) != 1:
        raise TransferabilityError("transferability_document_inventory_invalid")
    document = documents[0]
    context = ArtifactAccessContext(
        user_id="semantic-transferability-research",
        case_id=f"semantic-transfer-{item['alias']}",
        chat_id=f"semantic-transfer-{item['alias']}",
        workspace_model_id="broker-reports-semantic-transferability",
        normalization_run_id=run_id,
        allow_private=True,
        require_source_available=True,
    )
    retention = build_retention_policy(
        mode="customer_approved_test", explicit=True
    )
    source = _source_record(
        context=context,
        retention=retention,
        document_id=document["document_id"],
        alias=item["alias"],
        source_sha256=item["source_sha256"],
        size_bytes=item["size_bytes"],
    )
    store.put_record(source)
    canonical = CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(
            normalizer_version="semantic_transferability_research_v0"
        )
    ).create().build(
        tenant_id=context.user_id,
        artifact_version=1,
        document=document,
        source_artifact_ref=source.artifact_id,
        source_payloads=normalized.package["private_normalized_source_payloads"],
        source_units=normalized.package["private_normalized_source_units"],
        table_projections=normalized.package[
            "private_normalized_table_projections"
        ],
    )
    canonical_store = CanonicalArtifactStoreFactory(
        store=store,
        config=CanonicalStorageConfig(capacity_check_enabled=False),
    ).create()
    persisted = canonical_store.put_candidate(
        artifact=canonical,
        context=context,
        retention_policy=retention,
        compare_receipt=None,
    )
    activated = CanonicalReaderFactory(
        store=store, read_enabled=True
    ).create().activate(
        canonical_version_id=persisted.canonical_version_id,
        expected_previous_version_id=None,
        context=context,
        actor="semantic-transferability-research",
        reason="frozen holdout canonical preparation",
    )
    if activated.status != "changed":
        raise TransferabilityError("transferability_canonical_activation_invalid")
    envelope = CanonicalReaderFactory(
        store=store, read_enabled=True
    ).create().read_active_envelope(document["document_id"], context)
    chunks = Gate3StructuralChunkFactory(
        store=store, read_enabled=True
    ).create(document_id=document["document_id"], context=context)
    table_nodes = [
        node
        for node in envelope.artifact.get("nodes") or []
        if node.get("node_type") == "TABLE"
    ]
    ready_projections = [
        projection
        for projection in normalized.package[
            "private_normalized_table_projections"
        ]
        if projection.get("projection_status") == "ready"
    ]
    return {
        "alias": item["alias"],
        "source_sha256": item["source_sha256"],
        "document_id": document["document_id"],
        "normalization_run_id": run_id,
        "context": {
            "user_id": context.user_id,
            "case_id": context.case_id,
            "chat_id": context.chat_id,
            "workspace_model_id": context.workspace_model_id,
            "normalization_run_id": context.normalization_run_id,
            "require_source_available": True,
        },
        "canonical_version_id": envelope.canonical_version_id,
        "canonical_root_sha256": envelope.canonical_root_sha256,
        "physical_layout": envelope.physical_layout,
        "canonical_nodes": len(envelope.artifact.get("nodes") or []),
        "canonical_tables": len(table_nodes),
        "ready_table_projections": len(ready_projections),
        "table_projection_status_counts": _counts(
            projection.get("projection_status")
            for projection in normalized.package[
                "private_normalized_table_projections"
            ]
        ),
        "chunk_count": len(chunks["chunks"]),
        "eligible_targets": chunks["coverage"]["eligible_targets"],
        "lost_targets": chunks["coverage"]["lost_targets"],
        "duplicated_working_targets": chunks["coverage"][
            "duplicated_working_targets"
        ],
    }


def _counts(values: Any) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        key = str(value or "missing")
        result[key] = result.get(key, 0) + 1
    return dict(sorted(result.items()))


def prepare_canonicals(args: argparse.Namespace) -> dict[str, Any]:
    output_root = args.private_output_root.resolve()
    if _is_within(output_root, REPO_ROOT.resolve()):
        raise TransferabilityError("private_output_must_be_outside_repository")
    if output_root.exists() and any(output_root.iterdir()):
        raise TransferabilityError("private_output_must_be_new_or_empty")
    documents = [_parse_document(value) for value in args.document]
    aliases = [item["alias"] for item in documents]
    hashes = [item["source_sha256"] for item in documents]
    if len(documents) < 3 or len(aliases) != len(set(aliases)):
        raise TransferabilityError("transferability_document_set_invalid")
    if len(hashes) != len(set(hashes)):
        raise TransferabilityError("transferability_duplicate_source")
    freeze = _freeze_contract(documents)
    output_root.mkdir(parents=True, exist_ok=True)
    _write_json(output_root / "freeze.private.json", freeze)

    intake_documents = [
        {
            "document_ref": f"transfer_{item['alias']}",
            "pdf_bytes": item["pdf_bytes"],
            "pdf_sha256": item["source_sha256"],
        }
        for item in documents
    ]
    intake = PdfTableIntakeRuntimeFactory(
        PdfTableIntakeConfig(
            enabled=True,
            detector_provider_profile=PROVIDER_PROFILE,
            detector_model_id=MODEL_ID,
            maximum_pages=sum(item["pages"] for item in documents),
        )
    ).create_for_openwebui(
        _openwebui_request(args.env_file.resolve())
    ).run(intake_documents)
    _write_json(
        output_root / "locator.private.json",
        {
            "safe_summary": intake.safe_summary,
            "private_detection_attempts": intake.private_detection_attempts,
            "private_page_results": intake.private_page_results,
        },
    )
    if intake.safe_summary.get("status") != "completed":
        raise TransferabilityError("transferability_locator_not_complete")

    return _assemble_canonicals(
        output_root=output_root,
        documents=documents,
        freeze=freeze,
        locator={
            "safe_summary": intake.safe_summary,
            "private_detection_attempts": intake.private_detection_attempts,
            "private_page_results": intake.private_page_results,
        },
    )


def _assemble_canonicals(
    *,
    output_root: Path,
    documents: list[dict[str, Any]],
    freeze: dict[str, Any],
    locator: dict[str, Any],
) -> dict[str, Any]:
    if (output_root / "canonical-manifest.private.json").exists():
        raise TransferabilityError("transferability_manifest_already_exists")
    attempts = locator.get("private_detection_attempts")
    page_results_all = locator.get("private_page_results")
    if (
        not isinstance(attempts, list)
        or not isinstance(page_results_all, list)
        or (locator.get("safe_summary") or {}).get("status") != "completed"
        or len(attempts) != freeze["expected_locator_calls"]
    ):
        raise TransferabilityError("transferability_preserved_locator_invalid")

    store_root = output_root / "canonical-store"
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=store_root / "artifacts.sqlite3",
            payload_root=store_root / "payloads",
        )
    ).create()
    manifest_documents = []
    for item in documents:
        page_results = [
            value
            for value in page_results_all
            if value.get("pdf_sha256") == item["source_sha256"]
        ]
        if len(page_results) != item["pages"]:
            raise TransferabilityError("transferability_page_accounting_invalid")
        manifest_documents.append(
            _prepare_one_canonical(
                item=item,
                page_results=page_results,
                store=store,
            )
        )
    manifest = {
        "schema_version": MANIFEST_VERSION,
        "freeze_sha256": _sha256_json(freeze),
        "store_relative_path": "canonical-store",
        "documents": manifest_documents,
        "production_changed": False,
        "legacy_fallback_used": False,
        "provider_calls": len(attempts),
        "source_values_from_model": False,
    }
    _write_json(output_root / "canonical-manifest.private.json", manifest)
    return manifest


def assemble_canonicals(args: argparse.Namespace) -> dict[str, Any]:
    output_root = args.private_output_root.resolve()
    if _is_within(output_root, REPO_ROOT.resolve()):
        raise TransferabilityError("private_output_must_be_outside_repository")
    freeze = _read_object(output_root / "freeze.private.json")
    locator = _read_object(output_root / "locator.private.json")
    if freeze.get("schema_version") != SCHEMA_VERSION:
        raise TransferabilityError("transferability_freeze_invalid")
    documents = [_parse_document(value) for value in args.document]
    actual = [
        {
            "alias": item["alias"],
            "source_sha256": item["source_sha256"],
            "size_bytes": item["size_bytes"],
            "pages": item["pages"],
        }
        for item in documents
    ]
    if actual != freeze.get("documents"):
        raise TransferabilityError("transferability_frozen_document_drift")
    return _assemble_canonicals(
        output_root=output_root,
        documents=documents,
        freeze=freeze,
        locator=locator,
    )


def _context(value: dict[str, Any]) -> ArtifactAccessContext:
    return ArtifactAccessContext(**value, allow_private=True)


def export_review(args: argparse.Namespace) -> dict[str, Any]:
    output_root = args.private_output_root.resolve()
    manifest = _read_object(output_root / "canonical-manifest.private.json")
    if manifest.get("schema_version") != MANIFEST_VERSION:
        raise TransferabilityError("transferability_manifest_invalid")
    store_root = output_root / str(manifest["store_relative_path"])
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=store_root / "artifacts.sqlite3",
            payload_root=store_root / "payloads",
        )
    ).create()
    documents = []
    for frozen in manifest["documents"]:
        context = _context(frozen["context"])
        envelope = CanonicalReaderFactory(
            store=store, read_enabled=True
        ).create().read_active_envelope(frozen["document_id"], context)
        if envelope.canonical_root_sha256 != frozen["canonical_root_sha256"]:
            raise TransferabilityError("transferability_canonical_root_drift")
        chunk_set = Gate3StructuralChunkFactory(
            store=store, read_enabled=True
        ).create(document_id=frozen["document_id"], context=context)
        tables = []
        for node in envelope.artifact.get("nodes") or []:
            if node.get("node_type") != "TABLE":
                continue
            content = node.get("content") or {}
            cells = copy.deepcopy(content.get("cells") or [])
            rows = copy.deepcopy(content.get("rows") or [])
            tables.append(
                {
                    "node_id": node.get("node_id"),
                    "container_ref": node.get("container_ref"),
                    "order": node.get("order"),
                    "content": copy.deepcopy(content),
                    "derived_dimensions": {
                        "row_count": max(
                            [int(cell.get("row") or 0) for cell in cells],
                            default=len(rows),
                        ),
                        "column_count": max(
                            [int(cell.get("column") or 0) for cell in cells],
                            default=max((len(row) for row in rows), default=0),
                        ),
                    },
                    "source_refs": copy.deepcopy(node.get("source_refs") or []),
                    "evidence_refs": copy.deepcopy(
                        node.get("evidence_refs") or []
                    ),
                    "issue_refs": copy.deepcopy(node.get("issue_refs") or []),
                }
            )
        documents.append(
            {
                "alias": frozen["alias"],
                "source_sha256": frozen["source_sha256"],
                "canonical_root_sha256": frozen["canonical_root_sha256"],
                "tables": tables,
                "chunks": copy.deepcopy(chunk_set["chunks"]),
                "coverage": copy.deepcopy(chunk_set["coverage"]),
            }
        )
    review = {
        "schema_version": REVIEW_VERSION,
        "canonical_manifest_sha256": _sha256_json(manifest),
        "documents": documents,
        "semantic_model_executions": 0,
        "source_truth_status": "not_yet_authored",
    }
    _write_json(output_root / "review-pack.private.json", review)
    return {
        "schema_version": REVIEW_VERSION,
        "documents": [
            {
                "alias": item["alias"],
                "canonical_root_sha256": item["canonical_root_sha256"],
                "tables": len(item["tables"]),
                "chunks": len(item["chunks"]),
                "eligible_targets": item["coverage"]["eligible_targets"],
            }
            for item in documents
        ],
        "semantic_model_executions": 0,
    }


def _table_chunk(document: dict[str, Any], node_id: str) -> dict[str, Any]:
    matches = [
        chunk
        for chunk in document["chunks"]
        if node_id in (chunk.get("structural_scope") or {}).get("node_refs", [])
        and chunk.get("structural_kind") == "whole_table"
    ]
    if len(matches) != 1:
        raise TransferabilityError("transferability_table_chunk_invalid")
    return matches[0]


def _table_context(
    *, document: dict[str, Any], spec: dict[str, Any]
) -> tuple[dict[str, Any], dict[tuple[int, int], dict[str, Any]]]:
    chunk = _table_chunk(document, str(spec["node_id"]))
    mapping_by_alias = {
        item["target_alias"]: item["canonical_target"]
        for item in chunk["target_mappings"]
    }
    text_by_alias, _ = typed._visible_text_index(
        content=chunk["model_view"]["content"],
        mapping_by_alias=mapping_by_alias,
    )
    cells: dict[tuple[int, int], dict[str, Any]] = {}
    for alias, target in mapping_by_alias.items():
        if target.get("kind") != "table_cell":
            continue
        cells[(int(target["row"]), int(target["column"]))] = {
            "source_ref": alias,
            "row": int(target["row"]),
            "column": int(target["column"]),
            "literal": str(text_by_alias.get(alias) or ""),
        }
    header_row = int(spec["header_row"])
    headers = [
        copy.deepcopy(value)
        for (row, _), value in sorted(cells.items())
        if row == header_row
    ]
    if not headers or len(headers) != len(spec["expected_roles"]):
        raise TransferabilityError("transferability_header_truth_mismatch")
    context: dict[str, Any] = {
        "logical_table_id": spec["case_id"],
        "headers": headers,
        "representative_rows": [
            {
                "source_record_id": f"{spec['case_id']}_r{row}",
                "elements": [
                    copy.deepcopy(value)
                    for (cell_row, _), value in sorted(cells.items())
                    if cell_row == int(row)
                ],
            }
            for row in spec["representative_rows"]
        ],
    }
    if spec.get("title_row") is not None:
        title_cells = [
            value
            for (row, _), value in sorted(cells.items())
            if row == int(spec["title_row"]) and value["literal"]
        ]
        if not title_cells:
            raise TransferabilityError("transferability_table_title_missing")
        context["table_identity"] = {
            "source_ref": title_cells[0]["source_ref"],
            "literal": title_cells[0]["literal"],
        }
    return context, cells


def _truth_mapping(
    spec: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    return {
        "logical_table_id": spec["case_id"],
        "table_type": spec["expected_table_type"],
        "columns": [
            {
                "header_ref": header["source_ref"],
                "normalized_role": role,
            }
            for header, role in zip(
                context["headers"], spec["expected_roles"], strict=True
            )
        ],
    }


def _residual_batch(
    *, documents: dict[str, dict[str, Any]], truth: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    records = []
    expected = []
    cell_cache: dict[tuple[str, str], dict[tuple[int, int], dict[str, Any]]] = {}
    for spec in truth["residuals"]:
        key = (spec["document_alias"], spec["node_id"])
        if key not in cell_cache:
            document = documents[key[0]]
            chunk = _table_chunk(document, key[1])
            mapping_by_alias = {
                item["target_alias"]: item["canonical_target"]
                for item in chunk["target_mappings"]
            }
            text_by_alias, _ = typed._visible_text_index(
                content=chunk["model_view"]["content"],
                mapping_by_alias=mapping_by_alias,
            )
            cell_cache[key] = {
                (int(target["row"]), int(target["column"])): {
                    "source_ref": alias,
                    "literal": str(text_by_alias.get(alias) or ""),
                }
                for alias, target in mapping_by_alias.items()
                if target.get("kind") == "table_cell"
            }
        cell = cell_cache[key].get(
            (int(spec["row"]), int(spec["wording_column"]))
        )
        if not cell or not cell["literal"]:
            raise TransferabilityError("transferability_residual_source_missing")
        records.append(
            {
                "source_record_id": spec["source_record_id"],
                "table_type": spec["table_type"],
                "source_wording_ref": cell["source_ref"],
                "source_wording": cell["literal"],
            }
        )
        expected.append(
            {
                "source_record_id": spec["source_record_id"],
                "expected_codes": copy.deepcopy(spec["expected_codes"]),
                "expected_asset_span": "",
                "expected_currency_span": "",
            }
        )
    return (
        {"schema_version": "broker_closed_residual_batch_v0", "records": records},
        expected,
    )


def structural_fingerprint(context: dict[str, Any]) -> str:
    return _sha256_json(
        {
            "title": (context.get("table_identity") or {}).get("literal"),
            "headers": [item["literal"] for item in context["headers"]],
            "columns": [item["column"] for item in context["headers"]],
        }
    )


def _materialize_selected(
    *,
    truth: dict[str, Any],
    contexts: dict[str, dict[str, Any]],
    cells_by_case: dict[str, dict[tuple[int, int], dict[str, Any]]],
    mappings: list[dict[str, Any]],
    side_bindings: list[dict[str, str]],
) -> dict[str, Any]:
    mapping_by_id = {item["logical_table_id"]: item for item in mappings}
    side_by_literal = {
        item["source_literal"]: item["normalized_value"]
        for item in side_bindings
    }
    classifications = []
    required = {
        "asset_name",
        "trade_date",
        "side",
        "quantity",
        "unit_price",
        "gross_amount",
        "currency",
    }
    for spec in truth["cases"]:
        case_id = spec["case_id"]
        mapping = mapping_by_id[case_id]
        header_by_ref = {
            item["source_ref"]: item["column"]
            for item in contexts[case_id]["headers"]
        }
        role_by_column = {
            header_by_ref[item["header_ref"]]: item["normalized_role"]
            for item in mapping["columns"]
            if item["normalized_role"] != "unmapped"
        }
        for row in spec["materialization_rows"]:
            source_record_id = f"{case_id}_r{row}"
            row_cells = {
                column: value
                for (cell_row, column), value in cells_by_case[case_id].items()
                if cell_row == int(row)
            }
            disposition = "UNMAPPED"
            typed_records: list[dict[str, Any]] = []
            if mapping["table_type"] == "SECURITY_TRADES":
                roles = {
                    role: row_cells[column]
                    for column, role in role_by_column.items()
                    if column in row_cells and row_cells[column]["literal"]
                }
                side = roles.get("side", {}).get("literal")
                if required <= set(roles) and side in side_by_literal:
                    record = {
                        "record_type": (
                            "SECURITY_PURCHASE"
                            if side_by_literal[side] == "PURCHASE"
                            else "SECURITY_DISPOSAL"
                        ),
                        "roles": [
                            {
                                "role": role,
                                "source_ref": value["source_ref"],
                                "literal": value["literal"],
                            }
                            for role, value in sorted(roles.items())
                            if role != "side"
                        ],
                    }
                    record["typed_record_id"] = "bstr_" + _sha256_json(
                        {
                            "source_record_id": source_record_id,
                            "record_type": record["record_type"],
                            "refs": [item["source_ref"] for item in record["roles"]],
                        }
                    )[:32]
                    typed_records = [record]
                    disposition = "MATERIALIZED"
            classifications.append(
                {
                    "source_record_id": source_record_id,
                    "disposition": disposition,
                    "typed_records": typed_records,
                }
            )
    for residual in truth["residuals"]:
        classifications.append(
            {
                "source_record_id": residual["source_record_id"],
                "disposition": "UNMAPPED",
                "typed_records": [],
            }
        )
    ids = [item["source_record_id"] for item in classifications]
    if len(ids) != len(set(ids)):
        raise TransferabilityError("transferability_source_identity_duplicate")
    return {
        "schema_version": "broker_transferability_projection_v0",
        "classifications": classifications,
    }


def execute_study(args: argparse.Namespace) -> dict[str, Any]:
    output_root = args.private_output_root.resolve()
    if _is_within(output_root, REPO_ROOT.resolve()):
        raise TransferabilityError("private_output_must_be_outside_repository")
    result_path = output_root / "semantic-results.private.json"
    if result_path.exists():
        raise TransferabilityError("transferability_semantic_results_exist")
    review = _read_object(output_root / "review-pack.private.json")
    truth_path = args.private_truth.resolve()
    if _is_within(truth_path, REPO_ROOT.resolve()):
        raise TransferabilityError("transferability_truth_must_be_private")
    truth_raw = truth_path.read_bytes()
    truth = json.loads(truth_raw)
    if (
        not isinstance(truth, dict)
        or truth.get("schema_version") != TRUTH_VERSION
        or truth.get("qualified_before_semantic_model_execution") is not True
        or truth.get("model_output_used_as_truth_hint") is not False
    ):
        raise TransferabilityError("transferability_truth_invalid")
    documents = {item["alias"]: item for item in review["documents"]}
    contexts: dict[str, dict[str, Any]] = {}
    cells_by_case: dict[str, dict[tuple[int, int], dict[str, Any]]] = {}
    truth_mappings = []
    for spec in truth["cases"]:
        context, cells = _table_context(
            document=documents[spec["document_alias"]], spec=spec
        )
        contexts[spec["case_id"]] = context
        cells_by_case[spec["case_id"]] = cells
        truth_mappings.append(_truth_mapping(spec, context))
    ordered_contexts = [contexts[item["case_id"]] for item in truth["cases"]]
    all_header_refs = [
        header["source_ref"]
        for context in ordered_contexts
        for header in context["headers"]
    ]
    h3_version = "broker_transferability_h3_response_v0"
    h3_schema = forms.header_forward_schema(
        version=h3_version,
        table_count=len(ordered_contexts),
        header_refs=all_header_refs,
        maximum=max(len(item["headers"]) for item in ordered_contexts),
        include_table_type=True,
    )
    h3_request = forms._request(
        instruction=(
            "Это только schema translation. Для каждого exact header_ref выбери одну normalized_role "
            "из закрытого каталога и один table_type. Representative rows только помогают понять схему; "
            "не извлекай из них records или values. РЕПО не является обычной покупкой или продажей бумаги. "
            "Unknown верни unmapped. Только strict JSON."
        ),
        contract={
            "normalized_roles": msc.ROLE_CATALOG,
            "table_types": list(msc.TABLE_TYPES),
        },
        batch={
            "schema_version": "broker_transferability_header_task_v0",
            "tables": ordered_contexts,
        },
        schema=h3_schema,
        name=h3_version,
    )
    trade_spec = next(
        item for item in truth["cases"] if item["expected_table_type"] == "SECURITY_TRADES"
    )
    trade_context = contexts[trade_spec["case_id"]]
    candidates = []
    for literal in (
        trade_spec["expected_purchase_literal"],
        trade_spec["expected_disposal_literal"],
    ):
        matches = [
            cell
            for row in trade_context["representative_rows"]
            for cell in row["elements"]
            if cell["literal"] == literal
        ]
        if not matches:
            raise TransferabilityError("transferability_side_candidate_missing")
        candidates.append(
            {"value_ref": matches[0]["source_ref"], "literal": literal}
        )
    side_context = {
        "schema_version": "broker_side_task_v0",
        "logical_table_id": trade_spec["case_id"],
        "candidates": candidates,
    }
    side_version = "broker_transferability_h6_response_v0"
    side_schema = forms.side_schema(
        version=side_version,
        mode="purchase_ref",
        value_refs=[item["value_ref"] for item in candidates],
        count=1,
    )
    side_request = forms._request(
        instruction=(
            "Из двух unique side candidates выбери только exact value_ref, который означает PURCHASE. "
            "Не копируй literal. Только strict JSON."
        ),
        contract={"decision": "purchase_value_ref"},
        batch=side_context,
        schema=side_schema,
        name=side_version,
    )
    residual_batch, residual_truth = _residual_batch(
        documents=documents, truth=truth
    )
    residual_version = "broker_transferability_h8_cash_response_v0"
    cash_codes = ["COMMISSION_ENTRY", "NOT_RELEVANT", "UNMAPPED"]
    residual_schema = forms.residual_codes_schema(
        version=residual_version,
        source_ids=[item["source_record_id"] for item in residual_batch["records"]],
        codes=cash_codes,
        include_spans=True,
    )
    residual_request = forms._request(
        instruction=(
            "Реши только смысл source_wording для CASH_OPERATIONS. Codes ограничены контрактом. "
            "Для неизвестного или невыразимого смысла верни UNMAPPED. asset_span и currency_span "
            "обязаны быть пустыми. Только strict JSON."
        ),
        contract={"table_type": "CASH_OPERATIONS", "codes": cash_codes},
        batch=residual_batch,
        schema=residual_schema,
        name=residual_version,
    )
    typed.model_clients_module.GATE3_OPERATIONAL_RETRY_LIMIT = 0
    client, submissions = typed._live_client(
        env_file=args.env_file.resolve(), timeout_seconds=args.timeout_seconds
    )
    expected_side = [
        {
            "column_role": "side",
            "source_literal": trade_spec["expected_purchase_literal"],
            "normalized_value": "PURCHASE",
        },
        {
            "column_role": "side",
            "source_literal": trade_spec["expected_disposal_literal"],
            "normalized_value": "DISPOSAL",
        },
    ]
    runs = []
    private_runs = []
    interrupted_path = output_root / "semantic-interrupted.private.json"
    interrupted = (
        _read_object(interrupted_path) if interrupted_path.exists() else None
    )
    seeded_provider_calls = int((interrupted or {}).get("provider_calls") or 0)
    expected_residual = {
        item["source_record_id"]: item["expected_codes"]
        for item in residual_truth
    }
    for ordinal in range(1, RUNS + 1):
        private_run: dict[str, Any] = {"ordinal": ordinal}
        h3_result = None
        h3_error = None
        h3_calls = 0
        mappings = None
        if ordinal == 1 and interrupted is not None:
            h3_error = str(interrupted.get("error_type") or "StoredRejection")
            private_run["h3"] = copy.deepcopy(interrupted)
        else:
            before = submissions["count"]
            try:
                h3_result = asyncio.run(
                    client.label_gate3_once(
                        model_visible_request=h3_request,
                        canonical_schema=h3_schema,
                        model_id=msc.NDFL_PROVIDER_MODEL_ID,
                    )
                )
                h3_calls = submissions["count"] - before
                mappings = forms.validate_header_forward(
                    h3_result.adapter_extracted_output,
                    version=h3_version,
                    contexts=ordered_contexts,
                    expect_table_type=True,
                )
                private_run["h3"] = {
                    "mapping": mappings,
                    "raw_model_output": copy.deepcopy(
                        h3_result.adapter_extracted_output
                    ),
                    "raw_provider_response": copy.deepcopy(
                        h3_result.raw_provider_response
                    ),
                }
            except Exception as exc:
                h3_calls = submissions["count"] - before
                h3_error = type(exc).__name__
                private_run["h3"] = {
                    "rejected": True,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "raw_model_output": copy.deepcopy(
                        h3_result.adapter_extracted_output
                    )
                    if h3_result is not None
                    else None,
                    "raw_provider_response": copy.deepcopy(
                        h3_result.raw_provider_response
                    )
                    if h3_result is not None
                    else None,
                }
        if mappings is not None:
            h3_score = forms.score_headers(
                mappings=mappings,
                truth={"schema_mappings": truth_mappings},
            )
        else:
            h3_score = {
                "exact": False,
                "correct": 0,
                "total": sum(len(item["headers"]) + 1 for item in ordered_contexts),
                "table_types_correct": 0,
            }
        before = submissions["count"]
        side_result = None
        side_error = None
        side_bindings: list[dict[str, str]] = []
        try:
            side_result = asyncio.run(
                client.label_gate3_once(
                    model_visible_request=side_request,
                    canonical_schema=side_schema,
                    model_id=msc.NDFL_PROVIDER_MODEL_ID,
                )
            )
            side_bindings = forms.validate_side(
                side_result.adapter_extracted_output,
                version=side_version,
                mode="purchase_ref",
                context=side_context,
                expected=expected_side,
            )
            side_score = forms.score_side(side_bindings, expected_side)
            private_run["h6"] = {
                "bindings": side_bindings,
                "raw_model_output": copy.deepcopy(
                    side_result.adapter_extracted_output
                ),
                "raw_provider_response": copy.deepcopy(
                    side_result.raw_provider_response
                ),
            }
        except Exception as exc:
            side_error = type(exc).__name__
            side_score = {"exact": False}
            private_run["h6"] = {
                "rejected": True,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "raw_model_output": copy.deepcopy(
                    side_result.adapter_extracted_output
                )
                if side_result is not None
                else None,
                "raw_provider_response": copy.deepcopy(
                    side_result.raw_provider_response
                )
                if side_result is not None
                else None,
            }
        side_calls = submissions["count"] - before
        before = submissions["count"]
        residual_result = None
        residual_error = None
        actual_residual: dict[str, list[str]] = {}
        residual = None
        try:
            residual_result = asyncio.run(
                client.label_gate3_once(
                    model_visible_request=residual_request,
                    canonical_schema=residual_schema,
                    model_id=msc.NDFL_PROVIDER_MODEL_ID,
                )
            )
            raw_residual = forms._decode_classifications(
                residual_result.adapter_extracted_output,
                version=residual_version,
                count=len(residual_batch["records"]),
            )
            residual = msc.validate_residual_response(
                {
                    "schema_version": msc.RESIDUAL_RESPONSE_VERSION,
                    "classifications": raw_residual,
                },
                residual_batch=residual_batch,
            )
            actual_residual = {
                item["assertion_id"]: item["codes"]
                for item in residual["classifications"]
            }
            private_run["h8"] = {
                "response": residual,
                "raw_model_output": copy.deepcopy(
                    residual_result.adapter_extracted_output
                ),
                "raw_provider_response": copy.deepcopy(
                    residual_result.raw_provider_response
                ),
            }
        except Exception as exc:
            residual_error = type(exc).__name__
            private_run["h8"] = {
                "rejected": True,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "raw_model_output": copy.deepcopy(
                    residual_result.adapter_extracted_output
                )
                if residual_result is not None
                else None,
                "raw_provider_response": copy.deepcopy(
                    residual_result.raw_provider_response
                )
                if residual_result is not None
                else None,
            }
        residual_calls = submissions["count"] - before
        effective_mappings = mappings or [
            {
                "logical_table_id": context["logical_table_id"],
                "table_type": "UNMAPPED",
                "columns": [
                    {
                        "header_ref": header["source_ref"],
                        "normalized_role": "unmapped",
                    }
                    for header in context["headers"]
                ],
            }
            for context in ordered_contexts
        ]
        projection = _materialize_selected(
            truth=truth,
            contexts=contexts,
            cells_by_case=cells_by_case,
            mappings=effective_mappings,
            side_bindings=side_bindings,
        )
        dispositions = _counts(
            item["disposition"] for item in projection["classifications"]
        )
        runs.append(
            {
                "ordinal": ordinal,
                "h3_exact": h3_score["exact"],
                "h3_correct": h3_score["correct"],
                "h3_total": h3_score["total"],
                "h3_table_types_correct": h3_score["table_types_correct"],
                "h3_terminal": "rejected" if h3_error else "validated",
                "h3_error_type": h3_error,
                "h6_exact": side_score["exact"],
                "h6_terminal": "rejected" if side_error else "validated",
                "h8_exact": actual_residual == expected_residual,
                "h8_correct": sum(
                    actual_residual[key] == expected_residual[key]
                    for key in expected_residual
                    if key in actual_residual
                ),
                "h8_total": len(expected_residual),
                "h8_terminal": "rejected" if residual_error else "validated",
                "projection_sha256": _sha256_json(projection),
                "source_records": len(projection["classifications"]),
                "dispositions": dispositions,
                "provider_calls": h3_calls + side_calls + residual_calls,
            }
        )
        private_run["projection"] = projection
        private_runs.append(private_run)
        _write_json(
            output_root / "semantic-progress.private.json",
            {
                "schema_version": RESULT_VERSION,
                "completed_runs": private_runs,
                "provider_calls": seeded_provider_calls + submissions["count"],
            },
        )
    fingerprints = {
        case_id: structural_fingerprint(context)
        for case_id, context in contexts.items()
    }
    mutated = copy.deepcopy(contexts[trade_spec["case_id"]])
    mutated["headers"] = list(reversed(mutated["headers"]))
    fingerprint_probe = {
        "case_fingerprints_unique": len(set(fingerprints.values()))
        == len(fingerprints),
        "exact_copy_reuses": structural_fingerprint(
            copy.deepcopy(contexts[trade_spec["case_id"]])
        )
        == fingerprints[trade_spec["case_id"]],
        "reordered_header_rejected": structural_fingerprint(mutated)
        != fingerprints[trade_spec["case_id"]],
    }
    projection_hashes = [item["projection_sha256"] for item in runs]
    result = {
        "schema_version": RESULT_VERSION,
        "truth_sha256": _sha256_bytes(truth_raw),
        "runs": runs,
        "private_runs": private_runs,
        "fingerprint_probe": fingerprint_probe,
        "provider_calls": seeded_provider_calls + submissions["count"],
        "retry": False,
        "repair": False,
        "best_of_n": False,
        "legacy_fallback_used": False,
        "production_changed": False,
        "final_projection_repeatable": len(set(projection_hashes)) == 1,
    }
    _write_json(result_path, result)
    return {
        "schema_version": RESULT_VERSION,
        "runs": runs,
        "fingerprint_probe": fingerprint_probe,
        "provider_calls": seeded_provider_calls + submissions["count"],
        "final_projection_repeatable": result["final_projection_repeatable"],
        "legacy_fallback_used": False,
        "production_changed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare-canonicals")
    prepare.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    prepare.add_argument("--private-output-root", type=Path, required=True)
    prepare.add_argument("--document", action="append", required=True)

    review = subparsers.add_parser("export-review")
    review.add_argument("--private-output-root", type=Path, required=True)

    execute = subparsers.add_parser("execute-study")
    execute.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    execute.add_argument("--private-output-root", type=Path, required=True)
    execute.add_argument("--private-truth", type=Path, required=True)
    execute.add_argument("--timeout-seconds", type=int, default=600)

    assemble = subparsers.add_parser("assemble-canonicals")
    assemble.add_argument("--private-output-root", type=Path, required=True)
    assemble.add_argument("--document", action="append", required=True)

    args = parser.parse_args()
    try:
        if args.command == "prepare-canonicals":
            result = prepare_canonicals(args)
        elif args.command == "assemble-canonicals":
            result = assemble_canonicals(args)
        elif args.command == "export-review":
            result = export_review(args)
        elif args.command == "execute-study":
            result = execute_study(args)
        else:
            raise TransferabilityError("transferability_command_invalid")
    except TransferabilityError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
