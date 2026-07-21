from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .artifact_lifecycle import lifecycle_for_visibility
from .artifact_models import ArtifactAccessContext, ArtifactRecord, RetentionPolicy, utc_now_iso
from .artifact_store import SqliteArtifactStoreAdapter, new_artifact_id
from .pdf_compact_canonical import (
    PdfCompactCanonicalError,
    PdfCompactCanonicalFactory,
    canonical_json_bytes,
)
from .pdf_compact_gate2_adapter import PdfCompactGate2MappingValidator
from .pdf_normalization_acceptance import PdfNormalizationAcceptanceFactory


@dataclass(frozen=True)
class Gate1ArtifactManifest:
    normalization_run_id: str
    gate2_handoff_ref: str
    safe_refs: list[str]
    private_slice_refs: list[str]
    private_source_payload_refs: list[str]
    private_source_unit_refs: list[str]
    pdf_table_candidate_refs: list[str]
    pdf_table_detection_attempt_refs: list[str]
    blocker_refs: list[str]
    artifact_refs_by_type: dict[str, list[str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "normalization_run_id": self.normalization_run_id,
            "gate2_handoff_ref": self.gate2_handoff_ref,
            "safe_refs": list(self.safe_refs),
            "private_slice_refs": list(self.private_slice_refs),
            "private_source_payload_refs": list(self.private_source_payload_refs),
            "private_source_unit_refs": list(self.private_source_unit_refs),
            "pdf_table_candidate_refs": list(self.pdf_table_candidate_refs),
            "pdf_table_detection_attempt_refs": list(
                self.pdf_table_detection_attempt_refs
            ),
            "blocker_refs": list(self.blocker_refs),
            "artifact_refs_by_type": {key: list(value) for key, value in self.artifact_refs_by_type.items()},
        }


def persist_gate1_result(
    *,
    store: SqliteArtifactStoreAdapter,
    result,
    context: ArtifactAccessContext,
    retention_policy: RetentionPolicy,
    source_file_refs: list[dict[str, Any]] | None = None,
) -> Gate1ArtifactManifest:
    package = result.package
    safe_report = result.safe_report
    bounded_graph = getattr(result, "bounded_graph", None)
    run_id = package["normalization_run"]["run_id"]
    validation_status = _validation_status(package)
    documents = package.get("document_inventory", {}).get("documents", [])
    source_refs = _source_refs_for_documents(documents, source_file_refs or [])
    if bounded_graph is not None:
        bounded_graph.assert_compatible(
            store=store,
            context=context,
            retention_policy=retention_policy,
        )
    refs_by_type: dict[str, list[str]] = (
        {
            key: list(value)
            for key, value in bounded_graph.refs_by_type.items()
        }
        if bounded_graph is not None
        else {}
    )
    source_records_by_doc: dict[str, dict[str, Any]] = (
        dict(bounded_graph.source_records_by_doc)
        if bounded_graph is not None
        else {}
    )
    source_artifact_ids_by_doc: dict[str, str] = (
        dict(bounded_graph.source_artifact_ids_by_doc)
        if bounded_graph is not None
        else {}
    )
    safe_refs: list[str] = list(source_artifact_ids_by_doc.values())
    private_refs_by_doc: dict[str, list[str]] = (
        {
            key: list(value)
            for key, value in bounded_graph.private_refs_by_doc.items()
        }
        if bounded_graph is not None
        else {}
    )
    private_refs: list[str] = (
        list(
            bounded_graph.collection(
                "private_normalized_slices"
            ).artifact_ids
        )
        if bounded_graph is not None
        else []
    )
    private_source_payload_refs_by_doc: dict[str, list[str]] = (
        {
            key: list(value)
            for key, value in bounded_graph.private_source_payload_refs_by_doc.items()
        }
        if bounded_graph is not None
        else {}
    )
    private_source_payload_refs: list[str] = (
        list(
            bounded_graph.collection(
                "private_normalized_source_payloads"
            ).artifact_ids
        )
        if bounded_graph is not None
        else []
    )
    private_source_unit_refs_by_doc: dict[str, list[str]] = (
        {
            key: list(value)
            for key, value in bounded_graph.private_source_unit_refs_by_doc.items()
        }
        if bounded_graph is not None
        else {}
    )
    private_source_unit_refs: list[str] = (
        list(
            bounded_graph.collection(
                "private_normalized_source_units"
            ).artifact_ids
        )
        if bounded_graph is not None
        else []
    )
    pdf_table_candidate_refs: list[str] = []
    pdf_table_candidate_refs_by_doc: dict[str, list[str]] = {}
    pdf_table_detection_attempt_refs: list[str] = []
    table_projection_refs_by_doc: dict[str, list[str]] = (
        {
            key: list(value)
            for key, value in bounded_graph.table_projection_refs_by_doc.items()
        }
        if bounded_graph is not None
        else {}
    )
    clarification_resolution_refs: list[str] = []
    passport_refs_by_doc: dict[str, str] = {}
    blocker_refs: list[str] = []

    def put(record: ArtifactRecord) -> ArtifactRecord:
        stored = store.put_record(record)
        refs_by_type.setdefault(stored.artifact_type, []).append(stored.artifact_id)
        return stored

    access_policy = {
        "requires_user_id": True,
        "requires_case_or_chat": True,
        "requires_workspace_model_id_when_present": bool(context.workspace_model_id),
    }

    if bounded_graph is not None:
        bounded_source_refs = [
            source_records_by_doc.get(str(document.get("document_id") or ""))
            for document in documents
        ]
        if bounded_source_refs != source_refs:
            raise ValueError("bounded_graph_source_refs_mismatch")
    for document, source_ref in (
        [] if bounded_graph is not None else zip(documents, source_refs)
    ):
        source_record = put(
            _record(
                artifact_type="source_file_ref_v0",
                context=context,
                retention_policy=retention_policy,
                document_id=document.get("document_id"),
                source_file_ref=source_ref,
                visibility="safe_internal",
                storage_backend="openwebui_file",
                validation_status=validation_status,
                payload=source_ref,
                safe_metadata={
                    "source_kind": document.get("source_kind"),
                    "container_format": document.get("container_format"),
                },
                access_policy=access_policy,
            )
        )
        source_records_by_doc[str(document.get("document_id"))] = source_record.source_file_ref or source_ref
        source_artifact_ids_by_doc[str(document.get("document_id"))] = source_record.artifact_id
        safe_refs.append(source_record.artifact_id)

    safe_payloads = [
        ("normalization_run_v0", package["normalization_run"], None),
        (
            "broker_reports_gate1_supported_pilot_profile_v1",
            package.get("gate1_supported_profile"),
            None,
        ),
        (
            "broker_reports_gate1_supported_profile_assessment_v1",
            package.get("gate1_supported_profile_assessment"),
            None,
        ),
        ("document_inventory_v0", package["document_inventory"], None),
        ("technical_readability_profile_v0", package["technical_readability_profiles"], None),
        (
            "broker_reports_gate1_archive_source_manifest_v1",
            package.get("archive_source_manifests"),
            None,
        ),
        ("taxonomy_candidates_v0", package["taxonomy_candidates"], None),
        ("normalization_blockers_v0", package["normalization_blockers"], None),
        (
            "broker_reports_file_processing_batch_v1",
            package.get("file_processing_outcomes"),
            None,
        ),
        ("document_source_eligibility_v0", package["document_source_eligibility"], None),
        ("gate1_issue_ledger_v0", package.get("gate1_issue_ledger"), None),
        ("document_usage_classification_v0", package.get("document_usage_classification"), None),
        (
            "broker_reports_gate1_document_memory_manifest_v1",
            package.get("document_memory_manifest"),
            None,
        ),
        ("domain_context_packet_v0", package.get("domain_context_packet"), None),
        (
            "broker_reports_pdf_table_intake_run_v1",
            package.get("pdf_table_intake"),
            None,
        ),
        ("validation_result_v0", package["validation_result"], None),
        ("chat_visible_normalization_report_v0", safe_report, "openwebui_chat"),
    ]
    for artifact_type, payload, backend_override in safe_payloads:
        if payload is None:
            continue
        record = put(
            _record(
                artifact_type=artifact_type,
                context=context,
                retention_policy=retention_policy,
                document_id=None,
                source_file_ref=None,
                visibility="chat_visible" if artifact_type == "chat_visible_normalization_report_v0" else "safe_internal",
                storage_backend=backend_override or "project_artifact_store",
                validation_status=validation_status,
                payload=payload,
                safe_metadata=_safe_metadata_for_payload(package, artifact_type),
                access_policy=access_policy,
                warning_codes=_warning_codes(package),
            )
        )
        if artifact_type == "normalization_blockers_v0":
            blocker_refs.append(record.artifact_id)
        else:
            safe_refs.append(record.artifact_id)

    for candidate in package.get("private_pdf_table_candidates", []):
        manifest = candidate.get("manifest") if isinstance(candidate, dict) else {}
        document_id = manifest.get("document_ref") if isinstance(manifest, dict) else None
        candidate_status = (
            "validated"
            if manifest.get("schema_version") == "broker_reports_pdf_table_candidate_v1"
            and manifest.get("png_sha256")
            and candidate.get("private_png_base64")
            else "blocked"
        )
        record = put(
            _record(
                artifact_type="broker_reports_pdf_table_candidate_v1",
                context=context,
                retention_policy=retention_policy,
                document_id=document_id,
                source_file_ref=source_records_by_doc.get(str(document_id)),
                visibility="private_case",
                storage_backend="project_artifact_payload",
                validation_status=candidate_status,
                payload=candidate,
                safe_metadata={
                    "schema_version": manifest.get("schema_version"),
                    "policy_version": manifest.get("policy_version"),
                    "candidate_ref": manifest.get("candidate_ref"),
                    "document_ref": document_id,
                    "page_number": manifest.get("page_number"),
                    "png_sha256": manifest.get("png_sha256"),
                    "manifest_hash": manifest.get("manifest_hash"),
                    "horizontal_padding_fraction": manifest.get(
                        "horizontal_padding_fraction"
                    ),
                    "vertical_padding_fraction": manifest.get(
                        "vertical_padding_fraction"
                    ),
                    "downstream_contract": manifest.get("downstream_contract"),
                },
                access_policy={**access_policy, "requires_gate2_resolver": True},
            )
        )
        pdf_table_candidate_refs.append(record.artifact_id)
        pdf_table_candidate_refs_by_doc.setdefault(str(document_id), []).append(
            record.artifact_id
        )

    for attempt in package.get("private_pdf_table_detection_attempts", []):
        document_id = attempt.get("document_ref") if isinstance(attempt, dict) else None
        attempt_status = (
            "validated"
            if attempt.get("terminal_status") == "validated"
            else "blocked"
        )
        record = put(
            _record(
                artifact_type="broker_reports_pdf_table_detection_attempt_v1",
                context=context,
                retention_policy=retention_policy,
                document_id=document_id,
                source_file_ref=source_records_by_doc.get(str(document_id)),
                visibility="private_case",
                storage_backend="project_artifact_payload",
                validation_status=attempt_status,
                payload=attempt,
                safe_metadata={
                    "schema_version": attempt.get("schema_version"),
                    "request_id": attempt.get("request_id"),
                    "document_ref": document_id,
                    "page_number": attempt.get("page_number"),
                    "provider_response_hash": attempt.get(
                        "provider_response_hash"
                    ),
                    "terminal_status": attempt.get("terminal_status"),
                    "hidden_retry": attempt.get("hidden_retry"),
                    "provider_failover": attempt.get("provider_failover"),
                },
                access_policy={**access_policy, "requires_gate2_resolver": True},
            )
        )
        pdf_table_detection_attempt_refs.append(record.artifact_id)

    for private_slice in (
        []
        if bounded_graph is not None
        else package.get("private_normalized_slices", [])
    ):
        artifact_type = (
            "private_normalized_table_slice_v0"
            if private_slice.get("slice_type") == "table_rows"
            else "private_normalized_text_slice_v0"
        )
        document_id = private_slice.get("document_id")
        record = put(
            _record(
                artifact_type=artifact_type,
                context=context,
                retention_policy=retention_policy,
                document_id=document_id,
                source_file_ref=source_records_by_doc.get(str(document_id)),
                visibility="private_case",
                storage_backend="project_artifact_payload",
                validation_status=validation_status,
                payload=private_slice,
                safe_metadata={
                    "slice_type": private_slice.get("slice_type"),
                    "schema_version": private_slice.get("schema_version"),
                    "source_unit_schema_version": private_slice.get("source_unit_schema_version"),
                    "document_id": document_id,
                    "profile_id": private_slice.get("profile_id"),
                    "table_ref": private_slice.get("table_ref"),
                    "row_range_ref": private_slice.get("row_range_ref"),
                    "row_refs_count": len(private_slice.get("row_refs") or []),
                    "cell_refs_count": len(private_slice.get("cell_refs") or []),
                    "source_value_refs_count": len(private_slice.get("source_value_refs") or []),
                    "text_segment_refs_count": len(private_slice.get("text_segment_refs") or []),
                    "source_checksum_ref": private_slice.get("source_checksum_ref"),
                    "parser_ref": private_slice.get("parser_ref"),
                    "coverage_ref": (private_slice.get("coverage") or {}).get("coverage_ref"),
                    "coverage_complete": (private_slice.get("coverage") or {}).get(
                        "all_selected_refs_accounted"
                    ),
                },
                access_policy={**access_policy, "requires_gate2_resolver": True},
            )
        )
        private_refs.append(record.artifact_id)
        private_refs_by_doc.setdefault(str(document_id), []).append(record.artifact_id)

    for source_payload in (
        []
        if bounded_graph is not None
        else package.get("private_normalized_source_payloads", [])
    ):
        document_id = source_payload.get("document_ref")
        record = put(
            _record(
                artifact_type="private_normalized_source_payload_v0",
                context=context,
                retention_policy=retention_policy,
                document_id=document_id,
                source_file_ref=source_records_by_doc.get(str(document_id)),
                visibility="private_case",
                storage_backend="project_artifact_payload",
                validation_status=validation_status,
                payload=source_payload,
                safe_metadata={
                    "schema_version": source_payload.get("schema_version"),
                    "document_ref": document_id,
                    "container_format": source_payload.get("container_format"),
                    "logical_identity": source_payload.get("logical_identity"),
                    "parser_ref": source_payload.get("parser_ref"),
                    "source_checksum_ref": source_payload.get("source_checksum_ref"),
                    "payload_checksum_ref": source_payload.get("payload_checksum_ref"),
                    "parser_completeness_status": source_payload.get(
                        "parser_completeness_status"
                    ),
                    "parser_completeness_reason_codes": list(
                        source_payload.get("parser_completeness_reason_codes") or []
                    ),
                    "rows_total": int(source_payload.get("rows_total") or 0),
                    "cells_total": int(source_payload.get("cells_total") or 0),
                    "text_characters_total": int(
                        source_payload.get("text_characters_total") or 0
                    ),
                    "extraction_units_total": len(
                        source_payload.get("extraction_unit_refs") or []
                    ),
                    "full_source_coverage_available": (
                        source_payload.get("coverage_index") or {}
                    ).get("full_source_coverage_available")
                    is True,
                    "pdf_text_layer_projection_status": source_payload.get(
                        "text_layer_projection_status"
                    ),
                    "pdf_visible_content_coverage_status": source_payload.get(
                        "visible_content_coverage_status"
                    ),
                    "ocr_vlm_used": source_payload.get("ocr_vlm_used"),
                    "page_rendering_used_for_extraction": source_payload.get(
                        "page_rendering_used_for_extraction"
                    ),
                },
                access_policy={**access_policy, "requires_gate2_resolver": True},
            )
        )
        private_source_payload_refs.append(record.artifact_id)
        private_source_payload_refs_by_doc.setdefault(str(document_id), []).append(
            record.artifact_id
        )

    for source_unit in (
        []
        if bounded_graph is not None
        else package.get("private_normalized_source_units", [])
    ):
        document_id = source_unit.get("document_id")
        record = put(
            _record(
                artifact_type="private_normalized_source_unit_v0",
                context=context,
                retention_policy=retention_policy,
                document_id=document_id,
                source_file_ref=source_records_by_doc.get(str(document_id)),
                visibility="private_case",
                storage_backend="project_artifact_payload",
                validation_status=validation_status,
                payload=source_unit,
                safe_metadata={
                    "schema_version": source_unit.get("schema_version"),
                    "document_ref": document_id,
                    "unit_ref": source_unit.get("unit_ref"),
                    "parent_payload_ref": source_unit.get("parent_payload_ref"),
                    "parser_ref": source_unit.get("parser_ref"),
                    "source_checksum_ref": source_unit.get("source_checksum_ref"),
                    "payload_checksum_ref": source_unit.get("payload_checksum_ref"),
                    "source_unit_checksum_ref": source_unit.get(
                        "source_unit_checksum_ref"
                    ),
                    "coverage_ref": (source_unit.get("coverage") or {}).get(
                        "coverage_ref"
                    ),
                    "coverage_selected_total": (source_unit.get("coverage") or {}).get(
                        "selected_total"
                    ),
                    "source_slice_truncated": source_unit.get(
                        "source_slice_truncated"
                    ),
                    "parent_remainder_status": source_unit.get(
                        "parent_remainder_status"
                    ),
                    "parser_completeness_status": source_unit.get(
                        "parser_completeness_status"
                    ),
                    "pdf_unit_type": source_unit.get("pdf_unit_type"),
                    "pdf_text_layer_projection_status": source_unit.get(
                        "text_layer_projection_status"
                    ),
                    "ocr_vlm_used": source_unit.get("ocr_vlm_used"),
                    "page_rendering_used_for_extraction": source_unit.get(
                        "page_rendering_used_for_extraction"
                    ),
                },
                access_policy={**access_policy, "requires_gate2_resolver": True},
            )
        )
        private_source_unit_refs.append(record.artifact_id)
        private_source_unit_refs_by_doc.setdefault(str(document_id), []).append(
            record.artifact_id
        )

    for table_projection in (
        []
        if bounded_graph is not None
        else package.get("private_normalized_table_projections", [])
    ):
        document_id = table_projection.get("source_document_ref")
        record = put(
            _record(
                artifact_type="broker_reports_normalized_table_projection_v0",
                context=context,
                retention_policy=retention_policy,
                document_id=document_id,
                source_file_ref=source_records_by_doc.get(str(document_id)),
                visibility="private_case",
                storage_backend="project_artifact_payload",
                validation_status=(
                    "validated"
                    if table_projection.get("validator_status") == "passed"
                    and table_projection.get("projection_status") == "ready"
                    else "blocked"
                ),
                payload=table_projection,
                safe_metadata={
                    "schema_version": table_projection.get("schema_version"),
                    "table_projection_id": table_projection.get(
                        "table_projection_id"
                    ),
                    "table_ref": table_projection.get("table_ref"),
                    "source_document_ref": document_id,
                    "source_unit_ref": table_projection.get("source_unit_ref"),
                    "source_unit_refs_count": len(
                        table_projection.get("source_unit_refs") or []
                    ),
                    "source_format": table_projection.get("source_format"),
                    "table_origin": table_projection.get("table_origin"),
                    "projection_status": table_projection.get("projection_status"),
                    "table_candidate_status": table_projection.get(
                        "table_candidate_status"
                    ),
                    "reconstruction_quality": table_projection.get(
                        "reconstruction_quality"
                    ),
                    "row_count": int(table_projection.get("row_count") or 0),
                    "column_count": int(
                        table_projection.get("column_count") or 0
                    ),
                    "cell_count": int(table_projection.get("cell_count") or 0),
                    "source_value_refs_count": len(
                        table_projection.get("source_value_refs") or []
                    ),
                    "fallback_refs_count": len(
                        (table_projection.get("coverage") or {}).get(
                            "fallback_text_refs"
                        )
                        or []
                    ),
                    "coverage_status": (
                        table_projection.get("coverage") or {}
                    ).get("coverage_status"),
                    "canonical_table_id": table_projection.get(
                        "canonical_table_id"
                    ),
                    "logical_table_id": table_projection.get(
                        "logical_table_id"
                    ),
                    "canonical_profile_id": table_projection.get(
                        "canonical_profile_id"
                    ),
                    "canonical_table_scope": table_projection.get(
                        "canonical_table_scope"
                    ),
                    "canonical_validation_status": (
                        table_projection.get("canonical_validation") or {}
                    ).get("validator_status"),
                    "knowledge_rag_used": False,
                    "vectorization_performed": False,
                },
                access_policy={**access_policy, "requires_gate2_resolver": True},
            )
        )
        table_projection_refs_by_doc.setdefault(str(document_id), []).append(
            record.artifact_id
        )

    _persist_pdf_compact_dual_write(
        put=put,
        package=package,
        documents=documents,
        source_records_by_doc=source_records_by_doc,
        source_artifact_ids_by_doc=source_artifact_ids_by_doc,
        source_payload_refs_by_doc=private_source_payload_refs_by_doc,
        source_unit_refs_by_doc=private_source_unit_refs_by_doc,
        table_projection_refs_by_doc=table_projection_refs_by_doc,
        context=context,
        retention_policy=retention_policy,
        access_policy=access_policy,
    )

    prompt_snapshot = package.get("llm_prompt_snapshot")
    if isinstance(prompt_snapshot, dict):
        record = put(
            _record(
                artifact_type="llm_prompt_snapshot_v0",
                context=context,
                retention_policy=retention_policy,
                document_id=None,
                source_file_ref=None,
                visibility="safe_internal",
                storage_backend="project_artifact_store",
                validation_status=validation_status,
                payload=prompt_snapshot,
                safe_metadata={
                    "llm_prompt_ref": prompt_snapshot.get("llm_prompt_ref"),
                    "llm_prompt_version": prompt_snapshot.get("llm_prompt_version"),
                    "llm_prompt_hash": prompt_snapshot.get("llm_prompt_hash"),
                    "output_schema_id": prompt_snapshot.get("output_schema_id"),
                    "output_schema_version": prompt_snapshot.get("output_schema_version"),
                    "output_schema_hash": prompt_snapshot.get("output_schema_hash"),
                },
                access_policy=access_policy,
                warning_codes=_warning_codes(package),
            )
        )
        safe_refs.append(record.artifact_id)

    for llm_package in package.get("llm_document_packages", []):
        document_id = llm_package.get("document_id")
        output_schema = llm_package.get("output_schema") if isinstance(llm_package.get("output_schema"), dict) else {}
        record = put(
            _record(
                artifact_type="llm_document_package_v0",
                context=context,
                retention_policy=retention_policy,
                document_id=document_id,
                source_file_ref=source_records_by_doc.get(str(document_id)),
                visibility="private_case",
                storage_backend="project_artifact_payload",
                validation_status=validation_status,
                payload=llm_package,
                safe_metadata={
                    "document_id": document_id,
                    "llm_input_package_id": llm_package.get("llm_input_package_id"),
                    "schema_version": llm_package.get("schema_version"),
                    "output_schema_id": output_schema.get("output_schema_id"),
                    "output_schema_version": output_schema.get("output_schema_version"),
                    "output_schema_hash": output_schema.get("output_schema_hash"),
                },
                access_policy={**access_policy, "requires_gate2_resolver": True},
                warning_codes=_warning_codes(package),
            )
        )

    for raw_output in package.get("llm_passport_raw_outputs", []):
        document_id = raw_output.get("document_id")
        record = put(
            _record(
                artifact_type="llm_passport_raw_output_v0",
                context=context,
                retention_policy=retention_policy,
                document_id=document_id,
                source_file_ref=source_records_by_doc.get(str(document_id)),
                visibility="private_case",
                storage_backend="project_artifact_payload",
                validation_status=validation_status,
                payload=raw_output,
                safe_metadata={
                    "document_id": document_id,
                    "model_call_status": raw_output.get("model_call_status"),
                    "schema_version": raw_output.get("schema_version"),
                    "structured_output_mode": raw_output.get("structured_output_mode"),
                    "response_format_type": raw_output.get("response_format_type"),
                    "response_format_schema_mode": raw_output.get("response_format_schema_mode"),
                    "schema_attempted": raw_output.get("schema_attempted"),
                    "fallback_used": raw_output.get("fallback_used"),
                    "native_structured_output_error_code": raw_output.get("native_structured_output_error_code"),
                    "repair_attempted": raw_output.get("repair_attempted"),
                    "repair_attempt_count": raw_output.get("repair_attempt_count"),
                    "validator_guided_repair_applied": raw_output.get("validator_guided_repair_applied"),
                    "validator_error_summary": raw_output.get("validator_error_summary"),
                    "output_schema_id": raw_output.get("output_schema_id"),
                    "output_schema_version": raw_output.get("output_schema_version"),
                    "output_schema_hash": raw_output.get("output_schema_hash"),
                    "llm_model_id": raw_output.get("llm_model_id"),
                    "llm_prompt_ref": raw_output.get("llm_prompt_ref"),
                    "llm_prompt_version": raw_output.get("llm_prompt_version"),
                    "llm_prompt_hash": raw_output.get("llm_prompt_hash"),
                },
                access_policy={**access_policy, "requires_gate2_resolver": True},
                warning_codes=_warning_codes(package),
            )
        )

    passport_validation = package.get("document_metadata_passport_validation")
    if isinstance(passport_validation, dict):
        record = put(
            _record(
                artifact_type="document_metadata_passport_validation_v0",
                context=context,
                retention_policy=retention_policy,
                document_id=None,
                source_file_ref=None,
                visibility="safe_internal",
                storage_backend="project_artifact_store",
                validation_status=validation_status,
                payload=passport_validation,
                safe_metadata={
                    "validator_status": passport_validation.get("validator_status"),
                    "passports_total": passport_validation.get("passports_total"),
                    "passed": passport_validation.get("passed"),
                    "failed": passport_validation.get("failed"),
                    "error_code_summary": passport_validation.get("error_code_summary"),
                    "structured_output_mode_counts": passport_validation.get("structured_output_mode_counts"),
                    "response_format_type_counts": passport_validation.get("response_format_type_counts"),
                    "repair_attempted_count": passport_validation.get("repair_attempted_count"),
                    "validator_guided_repair_count": passport_validation.get("validator_guided_repair_count"),
                    "fallback_used_count": passport_validation.get("fallback_used_count"),
                    "output_schema_id": passport_validation.get("output_schema_id"),
                    "output_schema_version": passport_validation.get("output_schema_version"),
                    "output_schema_hash": passport_validation.get("output_schema_hash"),
                    "llm_model_id": passport_validation.get("llm_model_id"),
                    "llm_prompt_ref": passport_validation.get("llm_prompt_ref"),
                    "llm_prompt_version": passport_validation.get("llm_prompt_version"),
                    "llm_prompt_hash": passport_validation.get("llm_prompt_hash"),
                },
                access_policy=access_policy,
                warning_codes=_warning_codes(package),
            )
        )
        safe_refs.append(record.artifact_id)

    for passport in package.get("document_metadata_passports", []):
        document_id = passport.get("document_id")
        record = put(
            _record(
                artifact_type="document_metadata_passport_v0",
                context=context,
                retention_policy=retention_policy,
                document_id=document_id,
                source_file_ref=source_records_by_doc.get(str(document_id)),
                visibility="safe_internal",
                storage_backend="project_artifact_store",
                validation_status=validation_status if passport.get("validator_status") == "passed" else "blocked",
                payload=passport,
                safe_metadata={
                    "document_id": document_id,
                    "passport_status": passport.get("passport_status"),
                    "validator_status": passport.get("validator_status"),
                    "source_candidate_confidence": passport.get("source_candidate_confidence"),
                    "metadata_confidence": passport.get("metadata_confidence"),
                    "llm_prompt_hash": passport.get("llm_prompt_hash"),
                    "llm_prompt_ref": passport.get("llm_prompt_ref"),
                    "llm_prompt_version": passport.get("llm_prompt_version"),
                    "llm_model_id": passport.get("llm_model_id"),
                },
                access_policy=access_policy,
                warning_codes=_warning_codes(package),
            )
        )
        safe_refs.append(record.artifact_id)
        passport_refs_by_doc[str(document_id)] = record.artifact_id

    gap_report = package.get("gate1_metadata_gap_report")
    if isinstance(gap_report, dict):
        record = put(
            _record(
                artifact_type="gate1_metadata_gap_report_v0",
                context=context,
                retention_policy=retention_policy,
                document_id=None,
                source_file_ref=None,
                visibility="safe_internal",
                storage_backend="project_artifact_store",
                validation_status=validation_status,
                payload=gap_report,
                safe_metadata={
                    "gap_report_id": gap_report.get("gap_report_id"),
                    "gaps_total": (gap_report.get("summary") or {}).get("gaps_total"),
                    "blocking_gaps_total": (gap_report.get("summary") or {}).get("blocking_gaps_total"),
                    "gap_type_counts": (gap_report.get("summary") or {}).get("gap_type_counts"),
                    "criticality_counts": (gap_report.get("summary") or {}).get("criticality_counts"),
                    "critical_gaps_total": (gap_report.get("summary") or {}).get("critical_gaps_total"),
                    "clarifying_gaps_total": (gap_report.get("summary") or {}).get("clarifying_gaps_total"),
                    "non_critical_gaps_total": (gap_report.get("summary") or {}).get("non_critical_gaps_total"),
                    "handoff_mode": gap_report.get("handoff_mode"),
                },
                access_policy=access_policy,
                warning_codes=_warning_codes(package),
            )
        )
        safe_refs.append(record.artifact_id)

    clarification_prompt_snapshot = package.get("gate1_clarification_prompt_snapshot")
    if isinstance(clarification_prompt_snapshot, dict):
        record = put(
            _record(
                artifact_type="llm_clarification_prompt_snapshot_v0",
                context=context,
                retention_policy=retention_policy,
                document_id=None,
                source_file_ref=None,
                visibility="safe_internal",
                storage_backend="project_artifact_store",
                validation_status=validation_status,
                payload=clarification_prompt_snapshot,
                safe_metadata={
                    "llm_prompt_ref": clarification_prompt_snapshot.get("llm_prompt_ref"),
                    "llm_prompt_version": clarification_prompt_snapshot.get("llm_prompt_version"),
                    "llm_prompt_hash": clarification_prompt_snapshot.get("llm_prompt_hash"),
                    "output_schema_id": clarification_prompt_snapshot.get("output_schema_id"),
                    "output_schema_version": clarification_prompt_snapshot.get("output_schema_version"),
                    "output_schema_hash": clarification_prompt_snapshot.get("output_schema_hash"),
                },
                access_policy=access_policy,
                warning_codes=_warning_codes(package),
            )
        )
        safe_refs.append(record.artifact_id)

    clarification_raw_output = package.get("llm_clarification_raw_output")
    if isinstance(clarification_raw_output, dict):
        record = put(
            _record(
                artifact_type="llm_clarification_raw_output_v0",
                context=context,
                retention_policy=retention_policy,
                document_id=None,
                source_file_ref=None,
                visibility="private_case",
                storage_backend="project_artifact_payload",
                validation_status=validation_status
                if clarification_raw_output.get("model_call_status") == "passed"
                else "blocked",
                payload=clarification_raw_output,
                safe_metadata={
                    "model_call_status": clarification_raw_output.get("model_call_status"),
                    "structured_output_mode": clarification_raw_output.get("structured_output_mode"),
                    "response_format_type": clarification_raw_output.get("response_format_type"),
                    "fallback_used": clarification_raw_output.get("fallback_used"),
                    "error_code": clarification_raw_output.get("error_code"),
                    "output_schema_id": clarification_raw_output.get("output_schema_id"),
                    "output_schema_version": clarification_raw_output.get("output_schema_version"),
                    "output_schema_hash": clarification_raw_output.get("output_schema_hash"),
                    "llm_model_id": clarification_raw_output.get("llm_model_id"),
                    "llm_prompt_ref": clarification_raw_output.get("llm_prompt_ref"),
                    "llm_prompt_version": clarification_raw_output.get("llm_prompt_version"),
                    "llm_prompt_hash": clarification_raw_output.get("llm_prompt_hash"),
                },
                access_policy={**access_policy, "requires_gate2_resolver": True},
                warning_codes=_warning_codes(package),
            )
        )
        private_refs.append(record.artifact_id)

    clarification_request = package.get("gate1_clarification_request")
    if isinstance(clarification_request, dict):
        validation = package.get("gate1_clarification_request_validation")
        request_validated = isinstance(validation, dict) and validation.get("validator_status") == "passed"
        record = put(
            _record(
                artifact_type="gate1_clarification_request_v0",
                context=context,
                retention_policy=retention_policy,
                document_id=None,
                source_file_ref=None,
                visibility="safe_internal",
                storage_backend="project_artifact_store",
                validation_status=validation_status if request_validated else "blocked",
                payload=clarification_request,
                safe_metadata={
                    "clarification_request_id": clarification_request.get("clarification_request_id"),
                    "gap_report_id": clarification_request.get("gap_report_id"),
                    "questions_total": (clarification_request.get("summary") or {}).get("questions_total"),
                    "required_questions_total": (clarification_request.get("summary") or {}).get("required_questions_total"),
                    "gap_type_counts": (clarification_request.get("summary") or {}).get("gap_type_counts"),
                    "criticality_counts": (clarification_request.get("summary") or {}).get("criticality_counts"),
                    "critical_questions_total": (clarification_request.get("summary") or {}).get("critical_questions_total"),
                    "clarifying_questions_total": (clarification_request.get("summary") or {}).get("clarifying_questions_total"),
                    "non_critical_questions_total": (clarification_request.get("summary") or {}).get("non_critical_questions_total"),
                    "validator_status": validation.get("validator_status") if isinstance(validation, dict) else None,
                    "output_schema_hash": clarification_request.get("output_schema_hash"),
                    "llm_model_id": clarification_request.get("llm_model_id"),
                    "llm_prompt_hash": clarification_request.get("llm_prompt_hash"),
                },
                access_policy=access_policy,
                warning_codes=_warning_codes(package),
            )
        )
        safe_refs.append(record.artifact_id)

    for resolution in package.get("gate1_clarification_resolutions", []):
        if not isinstance(resolution, dict):
            continue
        document_id = resolution.get("target_document_ref")
        record = put(
            _record(
                artifact_type="gate1_clarification_resolution_v0",
                context=context,
                retention_policy=retention_policy,
                document_id=document_id,
                source_file_ref=source_records_by_doc.get(str(document_id)),
                visibility="private_case",
                storage_backend="project_artifact_payload",
                validation_status=validation_status if resolution.get("validation_status") == "passed" else "blocked",
                payload=resolution,
                safe_metadata={
                    "resolution_id": resolution.get("resolution_id"),
                    "question_id": resolution.get("question_id"),
                    "gap_type": resolution.get("gap_type"),
                    "resolved_field": resolution.get("resolved_field"),
                    "answer_type": resolution.get("answer_type"),
                    "source": resolution.get("source"),
                    "validation_status": resolution.get("validation_status"),
                    "usable_by_source_eligibility_v2": resolution.get("usable_by_source_eligibility_v2"),
                },
                access_policy={**access_policy, "requires_gate2_resolver": True},
                warning_codes=_warning_codes(package),
            )
        )
        private_refs.append(record.artifact_id)
        if (
            resolution.get("validation_status") == "passed"
            and resolution.get("usable_by_source_eligibility_v2") is True
        ):
            clarification_resolution_refs.append(record.artifact_id)

    handoff_decision = package.get("gate2_handoff", {})
    included_document_ids = [str(item) for item in handoff_decision.get("included_document_ids", [])]
    included_private_refs = [
        private_ref
        for document_id in included_document_ids
        for private_ref in private_refs_by_doc.get(document_id, [])
    ]
    handoff_status = package["normalization_run"]["gate2_handoff_status"]
    if handoff_status == "blocked":
        included_private_refs = []
    included_source_unit_refs = [
        private_ref
        for document_id in included_document_ids
        for private_ref in private_source_unit_refs_by_doc.get(document_id, [])
    ]
    if handoff_status == "blocked":
        included_source_unit_refs = []
    eligibility_refs = refs_by_type.get("document_source_eligibility_v0", [])
    issue_ledger_refs = refs_by_type.get("gate1_issue_ledger_v0", [])
    usage_classification_refs = refs_by_type.get("document_usage_classification_v0", [])
    domain_context_packet_refs = refs_by_type.get("domain_context_packet_v0", [])
    document_memory_manifest_refs = refs_by_type.get(
        "broker_reports_gate1_document_memory_manifest_v1", []
    )
    domain_context_packet = package.get("domain_context_packet") if isinstance(package.get("domain_context_packet"), dict) else {}
    next_stage_refs = (
        domain_context_packet.get("next_stage_refs")
        if isinstance(domain_context_packet.get("next_stage_refs"), dict)
        else {}
    )
    handoff_payload = {
        "artifact_type": "gate2_handoff_v0",
        "normalization_run_id": run_id,
        "case_id": context.case_id,
        "chat_id": context.chat_id,
        "user_id": context.user_id,
        "validation_status": validation_status,
        "handoff_status": handoff_status,
        "handoff_mode": package["normalization_run"].get("gate2_handoff_mode"),
        "reduced_subset_validated": handoff_decision.get("reduced_subset_validated") is True,
        "eligibility_ref": eligibility_refs[-1] if eligibility_refs else None,
        "issue_ledger_ref": issue_ledger_refs[-1] if issue_ledger_refs else None,
        "document_usage_classification_ref": usage_classification_refs[-1] if usage_classification_refs else None,
        "domain_context_packet_ref": domain_context_packet_refs[-1] if domain_context_packet_refs else None,
        "document_memory_manifest_ref": (
            document_memory_manifest_refs[-1]
            if document_memory_manifest_refs
            else None
        ),
        "unresolved_issue_refs": list(domain_context_packet.get("unresolved_issue_refs") or []),
        "domain_stage_readiness": dict(domain_context_packet.get("stage_readiness") or {}),
        "next_stage_refs": copy.deepcopy(next_stage_refs),
        "next_stage_ref_summary": copy.deepcopy(domain_context_packet.get("next_stage_ref_summary") or {}),
        "document_issue_refs": copy.deepcopy(domain_context_packet.get("document_issue_refs") or {}),
        "source_unit_contract": copy.deepcopy(domain_context_packet.get("private_slice_access") or {}),
        "included_document_refs": _document_artifact_refs(
            included_document_ids,
            source_artifact_ids_by_doc,
        ),
        "accepted_source_candidate_refs": _document_artifact_refs(
            handoff_decision.get("accepted_source_candidate_document_ids", []),
            source_artifact_ids_by_doc,
        ),
        "excluded_document_refs": _document_artifact_refs(
            handoff_decision.get("excluded_document_ids", []),
            source_artifact_ids_by_doc,
        ),
        "pending_review_refs": _document_artifact_refs(
            handoff_decision.get("pending_review_document_ids", []),
            source_artifact_ids_by_doc,
        ),
        "source_policy_review_refs": _document_artifact_refs(
            handoff_decision.get("source_policy_review_document_ids", []),
            source_artifact_ids_by_doc,
        ),
        "metadata_review_refs": _document_artifact_refs(
            handoff_decision.get("metadata_review_document_ids", []),
            source_artifact_ids_by_doc,
        ),
        "ocr_required_refs": _document_artifact_refs(
            handoff_decision.get("ocr_required_document_ids", []),
            source_artifact_ids_by_doc,
        ),
        "duplicate_review_refs": _document_artifact_refs(
            handoff_decision.get("duplicate_review_document_ids", []),
            source_artifact_ids_by_doc,
        ),
        "auto_resolved_duplicate_document_ids": list(
            handoff_decision.get("auto_resolved_duplicate_document_ids") or []
        ),
        "auto_canonical_duplicate_groups": list(
            handoff_decision.get("auto_canonical_duplicate_groups") or []
        ),
        "metadata_passport_refs": _document_artifact_refs(
            handoff_decision.get("included_document_ids", []),
            passport_refs_by_doc,
        ),
        "clarification_resolution_refs": clarification_resolution_refs,
        "reason_codes": list(handoff_decision.get("reason_codes", [])),
        "decision_status_counts": dict(handoff_decision.get("decision_status_counts") or {}),
        "handoff_blocker_counts": dict(handoff_decision.get("handoff_blocker_counts") or {}),
        "safe_refs": safe_refs,
        "private_slice_refs": included_private_refs,
        "private_source_unit_refs": included_source_unit_refs,
        "pdf_table_intake_status": _object(package.get("pdf_table_intake")).get(
            "status"
        ),
        "pdf_table_intake_contract": {
            "run_schema_version": _object(package.get("pdf_table_intake")).get(
                "schema_version"
            ),
            "detector_contract_version": _object(
                package.get("pdf_table_intake")
            ).get("detector_contract_version"),
            "candidate_contract_version": _object(
                package.get("pdf_table_intake")
            ).get("candidate_contract_version"),
            "gate2_boundary_ready": _object(package.get("pdf_table_intake")).get(
                "gate2_boundary_ready"
            ),
        },
        "pdf_table_candidate_refs": list(pdf_table_candidate_refs),
        "pdf_table_candidate_refs_by_document": copy.deepcopy(
            pdf_table_candidate_refs_by_doc
        ),
        "private_source_unit_refs_by_next_stage_bucket": _private_slice_refs_by_next_stage_bucket(
            next_stage_refs,
            private_source_unit_refs_by_doc,
        ),
        "private_slice_refs_by_next_stage_bucket": _private_slice_refs_by_next_stage_bucket(
            next_stage_refs,
            private_refs_by_doc,
        ),
        "blocker_refs": blocker_refs,
        "created_at": utc_now_iso(),
    }
    handoff_record_validation_status = _handoff_record_validation_status(
        package=package,
        gate1_validation_status=validation_status,
    )
    handoff_record = put(
        _record(
            artifact_type="gate2_handoff_v0",
            context=context,
            retention_policy=retention_policy,
            document_id=None,
            source_file_ref=None,
            visibility="safe_internal",
            storage_backend="project_artifact_store",
            validation_status=handoff_record_validation_status,
            payload=handoff_payload,
            safe_metadata={
                "handoff_status": handoff_payload["handoff_status"],
                "handoff_mode": handoff_payload["handoff_mode"],
                "decision_status_counts": handoff_payload["decision_status_counts"],
                "handoff_blocker_counts": handoff_payload["handoff_blocker_counts"],
                "next_stage_ref_summary": handoff_payload["next_stage_ref_summary"],
                "document_memory_manifest_ref": handoff_payload[
                    "document_memory_manifest_ref"
                ],
                "source_unit_schema_version": handoff_payload["source_unit_contract"].get(
                    "source_unit_schema_version"
                ),
                "source_fact_input_manifest_status": (
                    "resolver_ready"
                    if handoff_record_validation_status == "validated"
                    else "blocked"
                ),
                "auto_resolved_duplicate_document_ids": handoff_payload["auto_resolved_duplicate_document_ids"],
                "auto_canonical_duplicate_groups": handoff_payload["auto_canonical_duplicate_groups"],
            },
            access_policy={**access_policy, "requires_validated_gate1": True},
            warning_codes=_warning_codes(package),
        )
    )
    refs_by_type.setdefault("gate2_handoff_v0", [])
    return Gate1ArtifactManifest(
        normalization_run_id=run_id,
        gate2_handoff_ref=handoff_record.artifact_id,
        safe_refs=safe_refs,
        private_slice_refs=private_refs,
        private_source_payload_refs=private_source_payload_refs,
        private_source_unit_refs=private_source_unit_refs,
        pdf_table_candidate_refs=pdf_table_candidate_refs,
        pdf_table_detection_attempt_refs=pdf_table_detection_attempt_refs,
        blocker_refs=blocker_refs,
        artifact_refs_by_type=refs_by_type,
    )


def _persist_pdf_compact_dual_write(
    *,
    put,
    package: dict[str, Any],
    documents: list[dict[str, Any]],
    source_records_by_doc: dict[str, dict[str, Any]],
    source_artifact_ids_by_doc: dict[str, str],
    source_payload_refs_by_doc: dict[str, list[str]],
    source_unit_refs_by_doc: dict[str, list[str]],
    table_projection_refs_by_doc: dict[str, list[str]],
    context: ArtifactAccessContext,
    retention_policy: RetentionPolicy,
    access_policy: dict[str, Any],
) -> None:
    if _object(package.get("input_context")).get(
        "pdf_compact_canonical_dual_write"
    ) is not True:
        return
    run_id = str(_object(package.get("normalization_run")).get("run_id") or "")
    all_decisions = _dicts(package.get("table_projection_decisions"))
    for document in documents:
        if document.get("container_format") != "pdf":
            continue
        document_id = str(document.get("document_id") or "")
        source_payloads = _document_items(
            package.get("private_normalized_source_payloads"),
            document_id,
            field="document_ref",
        )
        source_units = _document_items(
            package.get("private_normalized_source_units"),
            document_id,
            field="document_id",
        )
        table_projections = [
            item
            for item in _document_items(
                package.get("private_normalized_table_projections"),
                document_id,
                field="source_document_ref",
            )
            if item.get("source_format") == "pdf"
        ]
        table_decisions = [
            item for item in all_decisions if str(item.get("document_ref") or "") == document_id
        ]
        try:
            if len(source_payloads) != 1:
                raise PdfCompactCanonicalError(
                    "pdf_compact_source_payload_cardinality_invalid", document_id
                )
            compact_builder = PdfCompactCanonicalFactory().create()
            build_args = {
                "normalization_run_id": run_id,
                "document": document,
                "original_pdf_artifact_ref": source_artifact_ids_by_doc.get(document_id, ""),
                "source_payload": source_payloads[0],
                "source_units": source_units,
                "table_projections": table_projections,
                "table_decisions": table_decisions,
            }
            compact = compact_builder.build(**build_args)
            repeated = compact_builder.build(**build_args)
            reproducibility_passed = (
                compact.get("canonical_document_checksum_ref")
                == repeated.get("canonical_document_checksum_ref")
                and canonical_json_bytes(compact) == canonical_json_bytes(repeated)
            )
            mapping_validation = PdfCompactGate2MappingValidator().validate(
                compact_document=compact,
                current_projections=table_projections,
            )
            compact_artifact_id = new_artifact_id()
            acceptance = PdfNormalizationAcceptanceFactory().create().build(
                compact_document=compact,
                compact_canonical_artifact_ref=compact_artifact_id,
                source_payloads=source_payloads,
                source_units=source_units,
                table_projections=table_projections,
                current_artifact_refs={
                    "source_payloads": list(
                        source_payload_refs_by_doc.get(document_id) or []
                    ),
                    "source_units": list(source_unit_refs_by_doc.get(document_id) or []),
                    "table_projections": list(
                        table_projection_refs_by_doc.get(document_id) or []
                    ),
                },
                mapping_validation=mapping_validation,
                reproducibility_passed=reproducibility_passed,
            )
            compact_record = put(
                _record(
                    artifact_id=compact_artifact_id,
                    artifact_type="broker_reports_pdf_compact_canonical_document_v1",
                    context=context,
                    retention_policy=retention_policy,
                    document_id=document_id,
                    source_file_ref=source_records_by_doc.get(document_id),
                    visibility="private_case",
                    storage_backend="project_artifact_payload",
                    validation_status="validated",
                    payload=compact,
                    safe_metadata={
                        "schema_version": compact.get("schema_version"),
                        "canonical_document_id": compact.get("canonical_document_id"),
                        "canonical_document_checksum_ref": compact.get(
                            "canonical_document_checksum_ref"
                        ),
                        "document_ref": document_id,
                        "original_pdf_artifact_ref": compact.get(
                            "original_pdf_artifact_ref"
                        ),
                        "page_count": len(compact.get("pages") or []),
                        "table_candidates_total": _object(
                            compact.get("coverage")
                        ).get("table_candidates_total"),
                        "tables_accepted_total": _object(compact.get("coverage")).get(
                            "tables_accepted_total"
                        ),
                        "tables_blocked_total": _object(compact.get("coverage")).get(
                            "tables_blocked_total"
                        ),
                        "knowledge_rag_used": False,
                        "vectorization_performed": False,
                    },
                    access_policy={**access_policy, "requires_gate2_resolver": True},
                )
            )
            if compact_record.artifact_id != compact_artifact_id:
                raise PdfCompactCanonicalError("pdf_compact_reserved_artifact_ref_changed")
            acceptance_status = str(acceptance.get("acceptance_status") or "blocked")
            put(
                _record(
                    artifact_type="broker_reports_pdf_normalization_acceptance_v1",
                    context=context,
                    retention_policy=retention_policy,
                    document_id=document_id,
                    source_file_ref=source_records_by_doc.get(document_id),
                    visibility="safe_internal",
                    storage_backend="project_artifact_store",
                    validation_status=(
                        "validated"
                        if acceptance_status
                        in {"accepted_complete", "accepted_with_explicit_blocked_tables"}
                        else "blocked"
                    ),
                    payload=acceptance,
                    safe_metadata={
                        "schema_version": acceptance.get("schema_version"),
                        "acceptance_id": acceptance.get("acceptance_id"),
                        "acceptance_status": acceptance_status,
                        "approval_required": acceptance.get("approval_required") is True,
                        "document_ref": document_id,
                        "compact_canonical_artifact_ref": compact_artifact_id,
                        "table_candidates_total": _object(
                            acceptance.get("metrics")
                        ).get("table_candidates_total"),
                        "tables_accepted_total": _object(
                            acceptance.get("metrics")
                        ).get("tables_accepted_total"),
                        "tables_blocked_total": _object(
                            acceptance.get("metrics")
                        ).get("tables_blocked_total"),
                        "compact_json_bytes": _object(acceptance.get("metrics")).get(
                            "compact_json_bytes"
                        ),
                        "production_gate2_selection_changed": False,
                        "acceptance_mode": compact.get("acceptance_mode"),
                        "authority_state": compact.get("authority_state"),
                        "production_ready": compact.get("production_ready"),
                    },
                    access_policy=access_policy,
                )
            )
        except PdfCompactCanonicalError as exc:
            _persist_pdf_compact_failure(
                put=put,
                code=exc.code,
                run_id=run_id,
                document_id=document_id,
                source_file_ref=source_records_by_doc.get(document_id),
                context=context,
                retention_policy=retention_policy,
                access_policy=access_policy,
            )
        except Exception:
            _persist_pdf_compact_failure(
                put=put,
                code="pdf_compact_unexpected_build_failure",
                run_id=run_id,
                document_id=document_id,
                source_file_ref=source_records_by_doc.get(document_id),
                context=context,
                retention_policy=retention_policy,
                access_policy=access_policy,
            )


def _persist_pdf_compact_failure(
    *,
    put,
    code: str,
    run_id: str,
    document_id: str,
    source_file_ref: dict[str, Any] | None,
    context: ArtifactAccessContext,
    retention_policy: RetentionPolicy,
    access_policy: dict[str, Any],
) -> None:
    payload = {
        "schema_version": "broker_reports_pdf_compact_build_failure_v1",
        "normalization_run_id": run_id,
        "document_id": document_id,
        "failure_code": code,
        "dual_write_enabled": True,
        "current_normalization_available": True,
        "partial_compact_accepted": False,
        "production_gate2_selection_changed": False,
        "current_artifacts_deleted": False,
        "knowledge_rag_used": False,
        "vectorization_performed": False,
    }
    put(
        _record(
            artifact_type="broker_reports_pdf_compact_build_failure_v1",
            context=context,
            retention_policy=retention_policy,
            document_id=document_id,
            source_file_ref=source_file_ref,
            visibility="safe_internal",
            storage_backend="project_artifact_store",
            validation_status="blocked",
            payload=payload,
            safe_metadata={
                "failure_code": code,
                "document_ref": document_id,
                "current_normalization_available": True,
                "partial_compact_accepted": False,
            },
            access_policy=access_policy,
        )
    )


def _record(
    *,
    artifact_type: str,
    context: ArtifactAccessContext,
    retention_policy: RetentionPolicy,
    document_id: str | None,
    source_file_ref: dict[str, Any] | None,
    visibility: str,
    storage_backend: str,
    validation_status: str,
    payload: Any,
    safe_metadata: dict[str, Any],
    access_policy: dict[str, Any],
    warning_codes: list[str] | None = None,
    artifact_id: str | None = None,
) -> ArtifactRecord:
    lifecycle_status = lifecycle_for_visibility(visibility=visibility, validation_status=validation_status)
    return ArtifactRecord(
        artifact_id=artifact_id or new_artifact_id(),
        artifact_type=artifact_type,
        case_id=context.case_id,
        chat_id=context.chat_id,
        user_id=context.user_id,
        workspace_model_id=context.workspace_model_id,
        normalization_run_id=context.normalization_run_id,
        document_id=document_id,
        source_file_ref=source_file_ref,
        visibility=visibility,
        storage_backend=storage_backend,
        retention_policy=retention_policy,
        access_policy=access_policy,
        validation_status=validation_status,
        lifecycle_status=lifecycle_status,
        payload_kind="json_file" if storage_backend == "project_artifact_payload" else "inline_json",
        payload=payload,
        safe_metadata=safe_metadata,
        warning_codes=warning_codes or [],
    )


def _source_refs_for_documents(
    documents: list[dict[str, Any]],
    source_file_refs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    refs = []
    for index, document in enumerate(documents):
        root_ordinal = int(document.get("root_input_ordinal") or (index + 1))
        provided = (
            source_file_refs[root_ordinal - 1]
            if 0 < root_ordinal <= len(source_file_refs)
            else {}
        )
        refs.append(
            {
                "provider": (
                    "bounded_zip_member"
                    if document.get("archive_member_ref")
                    else provided.get("provider")
                    or document.get("source_kind")
                    or "unknown"
                ),
                "openwebui_file_id": provided.get("openwebui_file_id"),
                "file_hash_sha256": document.get("sha256") or provided.get("file_hash_sha256"),
                "content_type": document.get("declared_mime_type") or provided.get("content_type"),
                "size_bytes": document.get("size_bytes") or provided.get("size_bytes"),
                "source_deleted": bool(provided.get("source_deleted", False)),
                "source_delete_observed_at": provided.get("source_delete_observed_at"),
                "archive_parent_document_ref": document.get(
                    "archive_parent_document_ref"
                ),
                "archive_member_ref": document.get("archive_member_ref"),
                "archive_member_index": document.get("archive_member_index"),
            }
        )
    return refs


def _document_artifact_refs(
    document_ids: list[Any],
    source_artifact_ids_by_doc: dict[str, str],
) -> list[str]:
    refs = []
    for document_id in document_ids:
        artifact_id = source_artifact_ids_by_doc.get(str(document_id))
        if artifact_id:
            refs.append(artifact_id)
    return refs


def _private_slice_refs_by_next_stage_bucket(
    next_stage_refs: dict[str, Any],
    private_refs_by_doc: dict[str, list[str]],
) -> dict[str, list[str]]:
    bucket_refs = {}
    for bucket in (
        "primary_source_extraction_refs",
        "secondary_source_extraction_refs",
        "cross_check_refs",
        "declaration_support_refs",
        "audit_reference_refs",
        "duplicate_or_non_primary_refs",
    ):
        refs = []
        for document_ref in next_stage_refs.get(bucket) or []:
            refs.extend(private_refs_by_doc.get(str(document_ref), []))
        bucket_refs[bucket] = refs
    return bucket_refs


def _validation_status(package: dict) -> str:
    status = package.get("validation_result", {}).get("status")
    if status == "passed":
        return "validated"
    if status == "privacy_failed":
        return "privacy_failed"
    return "blocked"


def _handoff_record_validation_status(
    *,
    package: dict[str, Any],
    gate1_validation_status: str,
) -> str:
    if gate1_validation_status != "validated":
        return gate1_validation_status
    domain_context_packet = (
        package.get("domain_context_packet")
        if isinstance(package.get("domain_context_packet"), dict)
        else {}
    )
    source_fact_readiness = (
        domain_context_packet.get("stage_readiness", {}).get("source_fact_extraction")
        if isinstance(domain_context_packet.get("stage_readiness"), dict)
        else None
    )
    if source_fact_readiness in {"ready", "ready_with_issue_context"}:
        # Full/reduced compatibility handoff may still be blocked by metadata,
        # while the DCP explicitly permits source-fact extraction with issue
        # context. Keep the resolver manifest readable without changing the
        # compatibility status carried in its payload.
        return "validated"
    if package.get("normalization_run", {}).get("gate2_handoff_status") == "blocked":
        return "blocked"
    return gate1_validation_status


def _safe_metadata_for_payload(package: dict, artifact_type: str) -> dict[str, Any]:
    run = package["normalization_run"]
    metadata = {
        "artifact_type": artifact_type,
        "normalizer_version": package["normalizer_version"],
        "run_status": run["run_status"],
        "gate2_handoff_status": run["gate2_handoff_status"],
        "gate2_handoff_mode": run.get("gate2_handoff_mode"),
        "files_total": package["summary_counts"]["files_total"],
    }
    workload_job_id = _object(package.get("input_context")).get(
        "workload_job_id"
    )
    if workload_job_id:
        metadata["workload_job_id"] = str(workload_job_id)
    if artifact_type == "gate1_issue_ledger_v0":
        summary = (package.get("gate1_issue_ledger") or {}).get("summary") or {}
        metadata.update(
            {
                "issues_total": summary.get("issues_total"),
                "unresolved_issues_total": summary.get("unresolved_issues_total"),
                "skipped_unresolved_issues_total": summary.get("skipped_unresolved_issues_total"),
                "awaiting_answer_unresolved_issues_total": summary.get(
                    "awaiting_answer_unresolved_issues_total"
                ),
            }
        )
    elif artifact_type == "document_usage_classification_v0":
        summary = (package.get("document_usage_classification") or {}).get("summary") or {}
        metadata.update(
            {
                "documents_total": summary.get("documents_total"),
                "source_fact_extraction_ready_total": summary.get("source_fact_extraction_ready_total"),
                "source_fact_extraction_blocked_total": summary.get("source_fact_extraction_blocked_total"),
            }
        )
    elif artifact_type == "domain_context_packet_v0":
        packet = package.get("domain_context_packet") or {}
        metadata.update(
            {
                "domain_ingestion_status": packet.get("domain_ingestion_status"),
                "unresolved_issue_summary": packet.get("unresolved_issue_summary"),
                "stage_readiness": packet.get("stage_readiness"),
                "next_stage_ref_summary": packet.get("next_stage_ref_summary"),
                "vector_knowledge_guard": packet.get("vector_knowledge_guard"),
            }
        )
    return metadata


def _warning_codes(package: dict) -> list[str]:
    return sorted({str(item.get("code")) for item in package.get("normalization_blockers", []) if item.get("code")})


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)] if isinstance(value, list) else []


def _document_items(
    value: Any,
    document_id: str,
    *,
    field: str,
) -> list[dict[str, Any]]:
    iter_document = getattr(value, "iter_document", None)
    if callable(iter_document):
        return list(iter_document(document_id))
    return [
        item
        for item in value or []
        if isinstance(item, dict)
        and str(item.get(field) or "") == document_id
    ] if isinstance(value, list) else []
