from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter, defaultdict
from typing import Any

from .bounded_graph import ArtifactStoreBackedList
from .contracts import stable_digest


SUPPORTED_PROFILE_SCHEMA_VERSION = "broker_reports_gate1_supported_pilot_profile_v1"
SUPPORTED_PROFILE_ID = "broker_reports_gate1_source_evidence_profile_v1"
SUPPORTED_PROFILE_ASSESSMENT_SCHEMA_VERSION = (
    "broker_reports_gate1_supported_profile_assessment_v1"
)
DOCUMENT_MEMORY_SCHEMA_VERSION = "broker_reports_gate1_document_memory_manifest_v1"
DOCUMENT_MEMORY_POLICY_VERSION = "broker_reports_gate1_document_memory_policy_v1"

TERMINAL_STATES = {
    "complete",
    "partial",
    "blocked",
    "unsupported",
    "unreadable",
    "review_required",
}
GATE2_MEMORY_READY_STATES = {"complete", "review_required"}
SUPPORTED_CONTAINERS = {"csv", "html_text", "pdf", "xml", "zip"}
SUPPORTED_HTML_ENCODINGS = {"utf-8-sig", "utf-8", "cp1251"}

FACTORY_REQUIRED = (
    "Gate1DocumentMemoryFactory.create is the only production document-memory "
    "root builder entrypoint"
)
FORBIDDEN = (
    "Callers must not mint document-memory roots, mark partial input complete, "
    "or copy private source values into safe manifests"
)

_PRIVATE_FIELD_NAMES = {
    "cells",
    "content",
    "filename",
    "normalized_projection",
    "original_filename",
    "private_path",
    "raw_rows",
    "raw_text",
    "rows",
    "source_value_index",
    "text",
}


def supported_pilot_profile_v1() -> dict[str, Any]:
    """Return the immutable safe contract for the bounded pilot source profile."""

    return {
        "schema_version": SUPPORTED_PROFILE_SCHEMA_VERSION,
        "profile_id": SUPPORTED_PROFILE_ID,
        "scope": "pilot_source_evidence_documents",
        "formats": {
            "csv": {
                "variant": "broker_reports_csv_supported_profile_v1",
                "encodings": ["utf-8-sig", "utf-8", "cp1251"],
                "delimiters": [",", ";", "tab", "|"],
                "max_input_bytes": 5_000_000,
                "max_rows": 10_000,
                "max_columns": 256,
                "max_cells": 100_000,
                "max_field_characters": 32_000,
                "max_materialized_json_bytes": 20_000_000,
                "logical_document_policy": "one_file_one_logical_document",
                "table_policy": "common_normalized_table_contract_required",
            },
            "html_text": {
                "variant": "static_html_text_and_tables_v1",
                "encodings": ["utf-8-sig", "utf-8", "cp1251"],
                "max_input_bytes": 5_000_000,
                "max_logical_units": 65,
                "max_rows_per_table": 10_000,
                "max_cells_per_table": 100_000,
                "max_text_characters_per_unit": 200_000,
                "scripts": "unsupported_review_required",
                "embedded_media_objects": (
                    "bounded_data_image_visual_memory_review_required"
                ),
                "nested_tables": "unsupported_review_required",
                "style_elements": "excluded_non_content_and_counted",
                "logical_document_policy": "one_file_one_logical_document",
                "table_policy": "common_normalized_table_contract_required",
            },
            "pdf": {
                "variant": "text_layout_and_bounded_visual_fallback_v1",
                "max_input_bytes": 50_000_000,
                "max_pages": 2_000,
                "max_page_content_stream_bytes": 10_000_000,
                "max_text_characters_per_page": 200_000,
                "max_layout_characters_per_page": 50_000,
                "max_layout_words_per_page": 10_000,
                "max_layout_lines_per_page": 2_000,
                "max_layout_objects_per_document": 75_000,
                "image_only_pages": "bounded_visual_page_memory_review_required",
                "mixed_text_image_pages": "bounded_visual_page_memory_review_required",
                "embedded_attachments": "unsupported_review_required",
                "table_policy": (
                    "common_normalized_table_when_geometry_is_validated; "
                    "otherwise explicit review with text fallback lineage"
                ),
                "logical_document_policy": "one_file_one_logical_document",
            },
            "xml": {
                "variant": "neutral_ordered_xml_event_memory_v1",
                "max_input_bytes": 5_000_000,
                "max_events": 100_000,
                "max_depth": 64,
                "max_attributes": 100_000,
                "dtd_and_entities": "forbidden",
                "financial_semantics": "not_claimed",
                "canonical_table_scope": "unavailable_review_required",
                "logical_document_policy": "one_member_one_logical_document",
                "table_policy": "common_neutral_event_table_contract",
            },
            "zip": {
                "variant": "bounded_source_container_v1",
                "max_input_bytes": 10_000_000,
                "max_members": 100,
                "max_member_bytes": 20_000_000,
                "max_expanded_bytes": 50_000_000,
                "max_compression_ratio": 100.0,
                "promoted_member_formats": ["pdf", "xml"],
                "accounted_signature_sidecars": ["p7s"],
                "nested_archives": "forbidden",
                "logical_document_policy": (
                    "archive_container_only_members_become_logical_documents"
                ),
            },
        },
        "explicitly_outside_profile": {
            "xlsx": (
                "pilot workbooks contain formulas and are methodology/output "
                "artifacts; formula, merge and embedded-object memory is not closed"
            ),
            "docx": "body-only projection is partial",
            "txt": "not present as a required source-evidence class in the approved pool",
            "xls": "not present as a required source-evidence class in the approved pool",
        },
        "terminal_states": {
            "complete": "all declared profile scope is normalized and accounted",
            "review_required": (
                "source memory and fallback lineage are complete, but structural "
                "interpretation remains explicitly unresolved"
            ),
            "partial": "some declared source scope is not normalized",
            "blocked": "normalization could not produce a usable bounded memory",
            "unsupported": "container or variant is outside this profile",
            "unreadable": "source bytes are unavailable or unreadable",
        },
        "complete_requires_validator_proof": True,
        "silent_omission_allowed": False,
        "financial_semantics_allowed": False,
        "private_values_allowed_in_safe_contract": False,
        "knowledge_rag_allowed": False,
    }


class Gate1DocumentMemoryFactory:
    def create(self) -> "Gate1DocumentMemoryBuilder":
        return Gate1DocumentMemoryBuilder()


class Gate1DocumentMemoryBuilder:
    def assess_supported_profile(self, package: dict[str, Any]) -> dict[str, Any]:
        run_id = _run_id(package)
        documents = _documents(package)
        summaries = {
            str(item.get("document_ref") or ""): item
            for item in _dicts(
                _object(package.get("full_source_coverage_summary")).get("documents")
            )
            if item.get("document_ref")
        }
        decisions_by_doc = _group_by(
            _dicts(package.get("table_projection_decisions")),
            "document_ref",
        )
        technical_profiles = {
            str(item.get("document_id") or ""): item
            for item in _dicts(package.get("technical_readability_profiles"))
            if item.get("document_id")
        }
        archive_manifests = {
            str(item.get("parent_document_ref") or ""): item
            for item in _dicts(package.get("archive_source_manifests"))
            if item.get("parent_document_ref")
        }

        entries = []
        for document in documents:
            document_ref = str(document.get("document_id") or "")
            entries.append(
                self._assess_document(
                    document=document,
                    summary=summaries.get(document_ref, {}),
                    payloads=_items_for_document(
                        package.get("private_normalized_source_payloads"),
                        document_ref,
                        field="document_ref",
                    ),
                    units=_items_for_document(
                        package.get("private_normalized_source_units"),
                        document_ref,
                        field="document_id",
                    ),
                    projections=_items_for_document(
                        package.get("private_normalized_table_projections"),
                        document_ref,
                        field="source_document_ref",
                    ),
                    decisions=decisions_by_doc.get(document_ref, []),
                    technical_profile=technical_profiles.get(document_ref, {}),
                    archive_manifest=archive_manifests.get(document_ref, {}),
                )
            )
        status_counts = Counter(str(item["terminal_status"]) for item in entries)
        return {
            "schema_version": SUPPORTED_PROFILE_ASSESSMENT_SCHEMA_VERSION,
            "profile_id": SUPPORTED_PROFILE_ID,
            "normalization_run_id": run_id,
            "entries": entries,
            "summary": {
                "documents_total": len(entries),
                "profile_accepted_total": sum(
                    1
                    for item in entries
                    if item.get("profile_acceptance") == "accepted"
                ),
                "archive_containers_accepted_total": sum(
                    1
                    for item in entries
                    if item.get("profile_acceptance") == "container_accepted"
                ),
                "gate2_memory_ready_total": sum(
                    1 for item in entries if item.get("gate2_memory_status") == "ready"
                ),
                "gate2_memory_restricted_total": sum(
                    1
                    for item in entries
                    if item.get("gate2_memory_status") == "ready_with_restrictions"
                ),
                "terminal_status_counts": dict(sorted(status_counts.items())),
            },
            "raw_private_values_present": False,
            "knowledge_rag_used": False,
            "vectorization_performed": False,
        }

    def build_manifest(
        self,
        package: dict[str, Any],
        assessment: dict[str, Any],
        issue_ledger: dict[str, Any],
    ) -> dict[str, Any]:
        run_id = _run_id(package)
        assessment_by_doc = {
            str(item.get("document_ref") or ""): item
            for item in _dicts(assessment.get("entries"))
        }
        issue_refs_by_doc: dict[str, list[str]] = defaultdict(list)
        for issue in _dicts(issue_ledger.get("entries")):
            for document_ref in _strings(issue.get("target_document_refs")):
                if issue.get("issue_id"):
                    issue_refs_by_doc[document_ref].append(str(issue["issue_id"]))

        decisions_by_doc = _group_by(
            _dicts(package.get("table_projection_decisions")),
            "document_ref",
        )
        summaries_by_doc = {
            str(item.get("document_ref") or ""): item
            for item in _dicts(
                _object(package.get("full_source_coverage_summary")).get("documents")
            )
            if item.get("document_ref")
        }
        archive_by_parent = {
            str(item.get("parent_document_ref") or ""): item
            for item in _dicts(package.get("archive_source_manifests"))
            if item.get("parent_document_ref")
        }
        entries = []
        for document in _documents(package):
            document_ref = str(document.get("document_id") or "")
            assessment_entry = assessment_by_doc.get(document_ref, {})
            payloads = _items_for_document(
                package.get("private_normalized_source_payloads"),
                document_ref,
                field="document_ref",
            )
            units = _items_for_document(
                package.get("private_normalized_source_units"),
                document_ref,
                field="document_id",
            )
            projections = _items_for_document(
                package.get("private_normalized_table_projections"),
                document_ref,
                field="source_document_ref",
            )
            is_archive_container = document.get("container_format") == "zip"
            logical_document_refs = (
                []
                if is_archive_container
                else [
                    "logicaldoc_"
                    + stable_digest(
                        [run_id, document_ref, "one_file_one_logical_document"],
                        length=24,
                    )
                ]
            )
            scope = self._scope(
                document=document,
                assessment=assessment_entry,
                payloads=payloads,
                units=units,
                projections=projections,
                decisions=decisions_by_doc.get(document_ref, []),
                summary=summaries_by_doc.get(document_ref, {}),
                archive_manifest=archive_by_parent.get(document_ref, {}),
            )
            entries.append(
                {
                    "source_file_ref": document_ref,
                    "logical_document_refs": logical_document_refs,
                    "logical_document_policy": (
                        "archive_container_only_members_are_logical_documents"
                        if is_archive_container
                        else "one_file_one_logical_document"
                    ),
                    "normalization_run_id": run_id,
                    "profile_id": SUPPORTED_PROFILE_ID,
                    "profile_variant": assessment_entry.get("profile_variant"),
                    "profile_acceptance": assessment_entry.get("profile_acceptance"),
                    "container_format": document.get("container_format"),
                    "source_checksum_ref": _source_checksum_ref(document),
                    "source_lineage": {
                        "archive_parent_source_ref": document.get(
                            "archive_parent_document_ref"
                        ),
                        "archive_member_ref": document.get("archive_member_ref"),
                        "archive_member_index": document.get("archive_member_index"),
                        "archive_manifest_ref": _object(
                            archive_by_parent.get(document_ref)
                        ).get("archive_ref"),
                        "duplicate_group_ref": document.get("duplicate_group_id"),
                        "duplicate_of_source_file_ref": document.get(
                            "duplicate_of_document_id"
                        ),
                    },
                    "normalized_artifact_refs": {
                        "source_payload_refs": sorted(
                            str(item.get("source_payload_ref") or "")
                            for item in payloads
                            if item.get("source_payload_ref")
                        ),
                        "source_unit_refs": sorted(
                            str(item.get("unit_ref") or "")
                            for item in units
                            if item.get("unit_ref")
                        ),
                        "table_projection_refs": sorted(
                            str(item.get("table_projection_id") or "")
                            for item in projections
                            if item.get("table_projection_id")
                        ),
                    },
                    "source_scope": scope,
                    "issue_refs": sorted(set(issue_refs_by_doc.get(document_ref, []))),
                    "completeness": {
                        "terminal_status": assessment_entry.get("terminal_status"),
                        "accounting_status": assessment_entry.get("accounting_status"),
                        "zero_silent_loss": assessment_entry.get("zero_silent_loss"),
                        "reason_codes": copy.deepcopy(
                            assessment_entry.get("reason_codes") or []
                        ),
                    },
                    "gate2_memory_status": assessment_entry.get("gate2_memory_status"),
                    "private_values_copied_to_manifest": False,
                }
            )
        status_counts = Counter(
            str(_object(item.get("completeness")).get("terminal_status") or "blocked")
            for item in entries
        )
        all_artifact_refs = [
            ref
            for entry in entries
            for refs in _object(entry.get("normalized_artifact_refs")).values()
            for ref in _strings(refs)
        ]
        manifest = {
            "schema_version": DOCUMENT_MEMORY_SCHEMA_VERSION,
            "policy_version": DOCUMENT_MEMORY_POLICY_VERSION,
            "manifest_id": "docmem_"
            + stable_digest([run_id, len(entries), SUPPORTED_PROFILE_ID], length=24),
            "normalization_run_id": run_id,
            "profile_id": SUPPORTED_PROFILE_ID,
            "case_root": {
                "scope": "artifact_access_context_case_or_chat",
                "source_file_refs": sorted(
                    str(item.get("source_file_ref") or "") for item in entries
                ),
                "logical_document_refs": sorted(
                    ref
                    for item in entries
                    for ref in _strings(item.get("logical_document_refs"))
                ),
                "archive_container_refs": sorted(
                    str(item.get("source_file_ref") or "")
                    for item in entries
                    if item.get("container_format") == "zip"
                ),
            },
            "documents": entries,
            "summary": {
                "source_files_total": len(entries),
                "logical_documents_total": sum(
                    len(_strings(item.get("logical_document_refs"))) for item in entries
                ),
                "normalized_artifacts_total": len(all_artifact_refs),
                "duplicate_normalized_artifact_refs_total": len(all_artifact_refs)
                - len(set(all_artifact_refs)),
                "terminal_status_counts": dict(sorted(status_counts.items())),
                "accepted_documents_total": sum(
                    1
                    for item in entries
                    if item.get("profile_acceptance") == "accepted"
                ),
                "accepted_archive_containers_total": sum(
                    1
                    for item in entries
                    if item.get("profile_acceptance") == "container_accepted"
                ),
                "gate2_memory_ready_total": sum(
                    1 for item in entries if item.get("gate2_memory_status") == "ready"
                ),
                "gate2_memory_restricted_total": sum(
                    1
                    for item in entries
                    if item.get("gate2_memory_status") == "ready_with_restrictions"
                ),
                "zero_silent_loss_status": (
                    "passed_for_all_profile_accepted_documents"
                    if all(
                        item.get("profile_acceptance")
                        not in {"accepted", "container_accepted"}
                        or _object(item.get("completeness")).get("zero_silent_loss")
                        == "passed"
                        for item in entries
                    )
                    else "failed"
                ),
            },
            "public_handoff": {
                "resolver_required": True,
                "format_specific_parser_required_by_gate2": False,
                "private_payloads_embedded": False,
                "source_unit_schema_version": "private_normalized_source_unit_v0",
                "table_schema_version": "broker_reports_normalized_table_projection_v0",
                "scope_readiness_required": True,
                "review_required_never_implies_canonical_table_ready": True,
                "visual_units_require_visual_consumer": True,
            },
            "knowledge_vector_guard": {
                "customer_docs_loaded_to_knowledge": False,
                "rag_used": False,
                "vectorization_performed": False,
            },
            "created_at": "not_recorded",
        }
        manifest["integrity_hash"] = _integrity_hash(manifest)
        return manifest

    def _assess_document(
        self,
        *,
        document: dict[str, Any],
        summary: dict[str, Any],
        payloads: list[dict[str, Any]],
        units: list[dict[str, Any]],
        projections: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
        technical_profile: dict[str, Any],
        archive_manifest: dict[str, Any],
    ) -> dict[str, Any]:
        document_ref = str(document.get("document_id") or "")
        container = str(document.get("container_format") or "unknown")
        reasons: list[str] = []
        terminal_status = "complete"
        profile_variant = {
            "csv": "broker_reports_csv_supported_profile_v1",
            "html_text": "static_html_text_and_tables_v1",
            "pdf": "text_layout_and_bounded_visual_fallback_v1",
            "xml": "neutral_ordered_xml_event_memory_v1",
            "zip": "bounded_source_container_v1",
        }.get(container, "outside_supported_profile_v1")

        if document.get("bytes_status") != "available" or document.get(
            "read_error_class"
        ):
            terminal_status = "unreadable"
            reasons.append("source_bytes_unavailable_or_unreadable")
        elif container not in SUPPORTED_CONTAINERS:
            terminal_status = "unsupported"
            reasons.append(f"container_outside_supported_profile:{container}")
        elif container == "zip":
            if (
                archive_manifest.get("terminal_status") == "complete"
                and archive_manifest.get("all_members_accounted") is True
                and int(archive_manifest.get("blocked_members_total") or 0) == 0
                and int(archive_manifest.get("promoted_members_total") or 0) > 0
                and all(
                    item.get("disposition") != "promoted_source_document"
                    or item.get("promoted_document_ref")
                    for item in _dicts(archive_manifest.get("member_inventory"))
                )
            ):
                return {
                    "document_ref": document_ref,
                    "container_format": container,
                    "profile_variant": profile_variant,
                    "profile_acceptance": "container_accepted",
                    "terminal_status": "complete",
                    "accounting_status": "passed",
                    "zero_silent_loss": "passed",
                    "gate2_memory_status": "lineage_only",
                    "reason_codes": ["archive_members_fully_accounted"],
                    "payloads_total": 0,
                    "source_units_total": 0,
                    "table_projections_total": 0,
                }
            terminal_status = "blocked"
            reasons.extend(
                _strings(archive_manifest.get("reason_codes"))
                or ["archive_source_container_not_complete"]
            )
        elif not summary:
            terminal_status = "blocked"
            reasons.append("full_source_summary_missing")
        else:
            parser_status = str(summary.get("parser_completeness_status") or "blocked")
            if (
                parser_status != "complete"
                or summary.get("full_coverage_available") is not True
            ):
                terminal_status = "partial" if parser_status == "partial" else "blocked"
                reasons.extend(
                    _strings(summary.get("parser_completeness_reason_codes"))
                    or ["full_source_coverage_not_complete"]
                )
            if container == "csv" and terminal_status == "complete":
                if technical_profile.get("supported_csv_profile_status") != "accepted":
                    terminal_status = "blocked"
                    reasons.append("csv_supported_profile_not_accepted")
            if container == "html_text" and terminal_status == "complete":
                if int(document.get("size_bytes") or 0) > 5_000_000:
                    terminal_status = "partial"
                    reasons.append("html_input_byte_budget_exceeded")
                if len(payloads) > 65:
                    terminal_status = "partial"
                    reasons.append("html_logical_unit_budget_exceeded")
                encodings = {
                    str(_object(item.get("source_location")).get("encoding") or "")
                    for item in payloads
                }
                if not encodings or not encodings <= SUPPORTED_HTML_ENCODINGS:
                    terminal_status = "unsupported"
                    reasons.append("html_encoding_outside_supported_profile")
                structural_reasons = sorted(
                    {
                        reason
                        for item in payloads
                        for reason in _strings(item.get("format_reason_codes"))
                    }
                )
                if structural_reasons:
                    terminal_status = "review_required"
                    reasons.extend(structural_reasons)
            if container == "xml" and terminal_status == "complete":
                if technical_profile.get("xml_neutral_profile_status") != "accepted":
                    terminal_status = "blocked"
                    reasons.append("xml_neutral_profile_not_accepted")
                else:
                    terminal_status = "review_required"
                    reasons.extend(
                        [
                            "xml_neutral_structure_ready",
                            "xml_canonical_financial_table_unavailable",
                        ]
                    )
            if container == "pdf" and terminal_status == "complete":
                if int(document.get("size_bytes") or 0) > 50_000_000:
                    terminal_status = "partial"
                    reasons.append("pdf_document_budget_exceeded")
                visual_complete = summary.get(
                    "pdf_visual_fallback_status"
                ) == "complete" and int(
                    summary.get("pdf_visual_pages_total") or 0
                ) == int(summary.get("pdf_visual_requested_pages_total") or 0)
                if summary.get("pdf_text_layer_projection_status") != "complete":
                    if visual_complete:
                        terminal_status = "review_required"
                        reasons.append("pdf_text_scope_unavailable_visual_scope_ready")
                    else:
                        terminal_status = "partial"
                        reasons.append("pdf_text_layer_projection_not_complete")
                if summary.get("pdf_layout_projection_status") != "complete":
                    if visual_complete:
                        terminal_status = "review_required"
                        reasons.append(
                            "pdf_layout_scope_restricted_visual_fallback_ready"
                        )
                    elif (
                        summary.get("pdf_text_layer_projection_status") == "complete"
                        and summary.get("pdf_visible_content_coverage_status")
                        == "complete_text_only"
                    ):
                        terminal_status = "review_required"
                        reasons.append(
                            "pdf_layout_scope_restricted_text_fallback_ready"
                        )
                    else:
                        terminal_status = "partial"
                        reasons.append("pdf_layout_projection_not_complete")
                if summary.get("pdf_visible_content_coverage_status") not in {
                    "complete_text_only",
                    "complete_with_visual_fallback",
                }:
                    terminal_status = "partial"
                    reasons.append("pdf_visible_content_coverage_not_complete")
                elif visual_complete and terminal_status == "complete":
                    terminal_status = "review_required"
                    reasons.append("pdf_visual_scope_ready_requires_operator_review")
                table_candidates = int(summary.get("pdf_table_candidates_total") or 0)
                pdf_projections = sum(
                    1
                    for item in projections
                    if item.get("source_format") == "pdf"
                    and item.get("validator_status") == "passed"
                )
                blocked_decisions = sum(
                    1
                    for item in decisions
                    if item.get("status")
                    in {"blocked", "rejected_to_line_cluster", "partial"}
                )
                if terminal_status == "complete" and (
                    table_candidates > pdf_projections or blocked_decisions
                ):
                    terminal_status = "review_required"
                    reasons.append(
                        "pdf_table_structure_requires_review_with_text_fallback"
                    )

        accounting_errors = _accounting_errors(
            document=document,
            summary=summary,
            payloads=payloads,
            units=units,
            projections=projections,
            terminal_status=terminal_status,
        )
        if accounting_errors and terminal_status in GATE2_MEMORY_READY_STATES:
            terminal_status = "partial"
        reasons.extend(accounting_errors)
        profile_acceptance = (
            "accepted"
            if terminal_status in GATE2_MEMORY_READY_STATES
            else "not_accepted"
        )
        accounting_status = "passed" if not accounting_errors else "failed"
        zero_silent_loss = (
            "passed"
            if profile_acceptance == "accepted" and accounting_status == "passed"
            else "not_proven"
        )
        if terminal_status in GATE2_MEMORY_READY_STATES:
            if container == "xml" or (
                container == "pdf" and int(summary.get("pdf_pages_with_text") or 0) == 0
            ):
                memory_status = "ready_with_restrictions"
            else:
                memory_status = "ready"
        else:
            memory_status = "blocked"
        return {
            "document_ref": document_ref,
            "container_format": container,
            "profile_variant": profile_variant,
            "profile_acceptance": profile_acceptance,
            "terminal_status": terminal_status,
            "accounting_status": accounting_status,
            "zero_silent_loss": zero_silent_loss,
            "gate2_memory_status": memory_status,
            "reason_codes": sorted(set(reasons)),
            "payloads_total": len(payloads),
            "source_units_total": len(units),
            "table_projections_total": len(projections),
        }

    @staticmethod
    def _scope(
        *,
        document: dict[str, Any],
        assessment: dict[str, Any],
        payloads: list[dict[str, Any]],
        units: list[dict[str, Any]],
        projections: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
        summary: dict[str, Any],
        archive_manifest: dict[str, Any],
    ) -> dict[str, Any]:
        pages = max(
            (
                int(item.get("page_refs_count") or 0)
                or len(_strings(item.get("page_refs")))
                for item in payloads
                if item.get("container_format") == "pdf"
            ),
            default=0,
        )
        container = str(document.get("container_format") or "unknown")
        visual_units = [
            item
            for item in units
            if item.get("slice_type") in {"visual_page", "visual_media"}
            or item.get("pdf_unit_type") == "pdf_visual_page_unit"
        ]
        visual_page_units = [
            item
            for item in visual_units
            if item.get("slice_type") == "visual_page"
            or item.get("pdf_unit_type") == "pdf_visual_page_unit"
        ]
        visual_media_units = [
            item for item in visual_units if item.get("slice_type") == "visual_media"
        ]
        validated_projections = [
            item for item in projections if item.get("validator_status") == "passed"
        ]
        unresolved_decisions = [
            item
            for item in decisions
            if item.get("status") in {"blocked", "partial", "rejected_to_line_cluster"}
        ]
        declared = {
            "source_files": 1,
            "logical_documents": 0 if container == "zip" else 1,
            "logical_content_artifacts": len(payloads),
            "rows_total": sum(int(item.get("rows_total") or 0) for item in payloads),
            "cells_total": sum(int(item.get("cells_total") or 0) for item in payloads),
            "text_characters": sum(
                int(item.get("text_characters_total") or 0) for item in payloads
            ),
            "pages": pages,
            "visual_pages": len(visual_page_units),
            "visual_media": len(visual_media_units),
            "normalized_tables": len(projections),
            "archive_members": int(archive_manifest.get("members_total") or 0),
            "archive_promoted_members": int(
                archive_manifest.get("promoted_members_total") or 0
            ),
            "archive_signature_sidecars": int(
                archive_manifest.get("signature_sidecars_total") or 0
            ),
        }
        accepted = assessment.get("profile_acceptance") in {
            "accepted",
            "container_accepted",
        }
        if container == "xml":
            canonical_table_scope = "unavailable_neutral_structure_only"
        elif container == "zip":
            canonical_table_scope = "not_applicable_archive_container"
        elif validated_projections and not unresolved_decisions:
            canonical_table_scope = "ready_validated_projection_only"
        elif projections or unresolved_decisions:
            canonical_table_scope = "restricted_unresolved_topology"
        else:
            canonical_table_scope = "unavailable"
        text_characters = int(declared["text_characters"])
        if text_characters > 0:
            text_scope = "ready"
        elif container == "xml" and accepted:
            text_scope = "neutral_structure_ready"
        elif visual_units:
            text_scope = "unavailable_visual_scope_only"
        else:
            text_scope = "unavailable"
        restrictions = []
        if canonical_table_scope not in {
            "ready_validated_projection_only",
            "not_applicable_archive_container",
        }:
            restrictions.append("canonical_financial_table_not_available")
        if text_scope != "ready":
            restrictions.append("text_scope_not_ready_for_text_only_consumer")
        if document.get("duplicate_of_document_id"):
            restrictions.append("duplicate_source_requires_canonical_choice")
        if visual_units:
            restrictions.append("visual_units_require_visual_consumer")
        scope_readiness = {
            "text_scope": text_scope,
            "visual_scope": "ready" if visual_units else "not_required",
            "canonical_table_scope": canonical_table_scope,
            "neutral_structure_scope": (
                "ready" if container == "xml" and accepted else "not_applicable"
            ),
            "archive_lineage_scope": (
                "ready"
                if container == "zip" and accepted
                else "member_linked"
                if document.get("archive_member_ref")
                else "not_applicable"
            ),
            "fallback_lineage": (
                "resolver_required_source_binary_available"
                if document.get("sha256")
                else "unavailable"
            ),
            "unresolved_table_topology": bool(unresolved_decisions)
            or container == "xml",
            "financial_interpretation": "restricted_to_ready_artifact_scopes",
            "restrictions": sorted(set(restrictions)),
            "review_required_does_not_imply_canonical_table": True,
        }
        return {
            "scope_ref": "docscope_"
            + stable_digest(
                [
                    document.get("document_id"),
                    document.get("sha256"),
                    json.dumps(declared, sort_keys=True),
                ],
                length=24,
            ),
            "declared": declared,
            "normalized": copy.deepcopy(declared)
            if accepted
            else {
                **copy.deepcopy(declared),
                "logical_content_artifacts": len(units),
            },
            "deferred": 0 if accepted else 1,
            "unreadable": 1 if assessment.get("terminal_status") == "unreadable" else 0,
            "unsupported": 1
            if assessment.get("terminal_status") == "unsupported"
            else 0,
            "review_required": (
                1 if assessment.get("terminal_status") == "review_required" else 0
            ),
            "over_limit": sum(
                1
                for reason in _strings(assessment.get("reason_codes"))
                if "budget" in reason or "limit" in reason
            ),
            "accounting_status": assessment.get("accounting_status"),
            "source_units_total": len(units),
            "scope_readiness": scope_readiness,
            "full_source_status": summary.get("parser_completeness_status"),
        }


def validate_document_memory_manifest(
    manifest: dict[str, Any],
    *,
    package: dict[str, Any] | None = None,
    assessment: dict[str, Any] | None = None,
    issue_ledger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    if manifest.get("schema_version") != DOCUMENT_MEMORY_SCHEMA_VERSION:
        errors.append(
            _error("document_memory_schema_mismatch", manifest.get("schema_version"))
        )
    if manifest.get("policy_version") != DOCUMENT_MEMORY_POLICY_VERSION:
        errors.append(
            _error("document_memory_policy_mismatch", manifest.get("policy_version"))
        )
    if manifest.get("profile_id") != SUPPORTED_PROFILE_ID:
        errors.append(
            _error("document_memory_profile_mismatch", manifest.get("profile_id"))
        )
    if manifest.get("integrity_hash") != _integrity_hash(manifest):
        errors.append(
            _error("document_memory_integrity_mismatch", manifest.get("manifest_id"))
        )
    if _contains_private_fields(manifest):
        errors.append(
            _error(
                "document_memory_private_field_forbidden", manifest.get("manifest_id")
            )
        )

    documents = _dicts(manifest.get("documents"))
    source_refs = [str(item.get("source_file_ref") or "") for item in documents]
    if not source_refs or any(not ref for ref in source_refs):
        errors.append(
            _error("document_memory_source_ref_missing", manifest.get("manifest_id"))
        )
    if len(source_refs) != len(set(source_refs)):
        errors.append(
            _error("document_memory_source_ref_duplicate", manifest.get("manifest_id"))
        )
    all_artifact_refs: list[str] = []
    for entry in documents:
        terminal_status = str(
            _object(entry.get("completeness")).get("terminal_status") or ""
        )
        if terminal_status not in TERMINAL_STATES:
            errors.append(
                _error(
                    "document_memory_terminal_status_invalid",
                    entry.get("source_file_ref"),
                )
            )
        expected_logical_documents = 0 if entry.get("container_format") == "zip" else 1
        if (
            len(_strings(entry.get("logical_document_refs")))
            != expected_logical_documents
        ):
            errors.append(
                _error(
                    "document_memory_logical_document_identity_invalid",
                    entry.get("source_file_ref"),
                )
            )
        completeness = _object(entry.get("completeness"))
        if entry.get("profile_acceptance") in {"accepted", "container_accepted"} and (
            terminal_status not in GATE2_MEMORY_READY_STATES
            or completeness.get("accounting_status") != "passed"
            or completeness.get("zero_silent_loss") != "passed"
        ):
            errors.append(
                _error(
                    "document_memory_accepted_document_not_complete",
                    entry.get("source_file_ref"),
                )
            )
        if (
            entry.get("gate2_memory_status") in {"ready", "ready_with_restrictions"}
            and terminal_status not in GATE2_MEMORY_READY_STATES
        ):
            errors.append(
                _error(
                    "document_memory_gate2_ready_status_invalid",
                    entry.get("source_file_ref"),
                )
            )
        if (
            entry.get("profile_acceptance") == "container_accepted"
            and entry.get("gate2_memory_status") != "lineage_only"
        ):
            errors.append(
                _error(
                    "document_memory_archive_container_status_invalid",
                    entry.get("source_file_ref"),
                )
            )
        readiness = _object(_object(entry.get("source_scope")).get("scope_readiness"))
        if (
            not readiness
            or readiness.get("review_required_does_not_imply_canonical_table")
            is not True
        ):
            errors.append(
                _error(
                    "document_memory_scope_readiness_missing",
                    entry.get("source_file_ref"),
                )
            )
        if readiness.get("financial_interpretation") != (
            "restricted_to_ready_artifact_scopes"
        ):
            errors.append(
                _error(
                    "document_memory_financial_scope_not_restricted",
                    entry.get("source_file_ref"),
                )
            )
        for refs in _object(entry.get("normalized_artifact_refs")).values():
            all_artifact_refs.extend(_strings(refs))
    if len(all_artifact_refs) != len(set(all_artifact_refs)):
        errors.append(
            _error(
                "document_memory_artifact_ref_duplicate", manifest.get("manifest_id")
            )
        )

    guard = _object(manifest.get("knowledge_vector_guard"))
    if guard != {
        "customer_docs_loaded_to_knowledge": False,
        "rag_used": False,
        "vectorization_performed": False,
    }:
        errors.append(
            _error(
                "document_memory_knowledge_guard_failed", manifest.get("manifest_id")
            )
        )
    if package is not None and assessment is not None and issue_ledger is not None:
        expected = (
            Gate1DocumentMemoryFactory()
            .create()
            .build_manifest(package, assessment, issue_ledger)
        )
        if expected != manifest:
            errors.append(
                _error(
                    "document_memory_package_graph_mismatch",
                    manifest.get("manifest_id"),
                )
            )
    return {
        "schema_version": "broker_reports_gate1_document_memory_validation_v1",
        "manifest_id": manifest.get("manifest_id"),
        "validator_status": "passed" if not errors else "failed",
        "passed": not errors,
        "errors_count": len(errors),
        "errors": errors,
    }


def _accounting_errors(
    *,
    document: dict[str, Any],
    summary: dict[str, Any],
    payloads: list[dict[str, Any]],
    units: list[dict[str, Any]],
    projections: list[dict[str, Any]],
    terminal_status: str,
) -> list[str]:
    if terminal_status not in GATE2_MEMORY_READY_STATES:
        return []
    errors: list[str] = []
    payload_refs = {
        str(item.get("source_payload_ref") or "")
        for item in payloads
        if item.get("source_payload_ref")
    }
    unit_refs = {
        str(item.get("unit_ref") or "") for item in units if item.get("unit_ref")
    }
    declared_unit_refs = {
        str(ref)
        for item in payloads
        for ref in _strings(item.get("extraction_unit_refs"))
    }
    if not payload_refs:
        errors.append("document_memory_payload_missing")
    if not unit_refs:
        errors.append("document_memory_source_unit_missing")
    if unit_refs != declared_unit_refs:
        errors.append("document_memory_payload_unit_ref_mismatch")
    if any(
        str(item.get("parent_payload_ref") or "") not in payload_refs for item in units
    ):
        errors.append("document_memory_unit_parent_missing")
    if int(summary.get("payloads_total") or 0) != len(payloads):
        errors.append("document_memory_payload_count_mismatch")
    if int(summary.get("extraction_units_total") or 0) != len(units):
        errors.append("document_memory_unit_count_mismatch")
    for payload in payloads:
        coverage = _object(payload.get("coverage_index"))
        if coverage.get("all_selected_refs_accounted") is False:
            errors.append("document_memory_payload_coverage_incomplete")
        if _strings(coverage.get("unaccounted_refs")):
            errors.append("document_memory_payload_refs_unaccounted")
        if _strings(coverage.get("duplicate_accounted_refs")):
            errors.append("document_memory_payload_refs_duplicate")
    for unit in units:
        coverage = _object(unit.get("coverage"))
        if coverage.get("all_selected_refs_accounted") is not True:
            errors.append("document_memory_unit_coverage_incomplete")
        if _strings(coverage.get("unaccounted_refs")):
            errors.append("document_memory_unit_refs_unaccounted")
    for projection in projections:
        coverage = _object(projection.get("coverage"))
        if projection.get("validator_status") != "passed":
            errors.append("document_memory_table_projection_not_validated")
        if coverage.get("all_selected_refs_accounted") is not True:
            errors.append("document_memory_table_projection_coverage_incomplete")
    native_table_unit_refs = {
        str(item.get("unit_ref") or "")
        for item in units
        if item.get("slice_type") == "table_rows"
        and item.get("container_format") != "pdf"
    }
    projection_unit_refs = {
        str(item.get("source_unit_ref") or "")
        for item in projections
        if item.get("validator_status") == "passed"
    }
    if not native_table_unit_refs <= projection_unit_refs:
        errors.append("document_memory_native_table_projection_missing")
    if document.get("container_format") != "pdf":
        unit_rows_total = sum(
            int(item.get("rows_count") or item.get("rows_in_slice") or 0)
            for item in units
            if item.get("slice_type") == "table_rows"
        )
        unit_cells_total = sum(
            int(item.get("cell_refs_count") or 0) or len(item.get("cell_refs") or [])
            for item in units
            if item.get("slice_type") == "table_rows"
        )
        unit_text_characters_total = sum(
            int(item.get("chars_count") or item.get("characters_in_slice") or 0)
            for item in units
            if item.get("slice_type") == "text_excerpt"
        )
        if (
            sum(int(item.get("rows_total") or 0) for item in payloads)
            != unit_rows_total
        ):
            errors.append("document_memory_row_count_mismatch")
        if (
            sum(int(item.get("cells_total") or 0) for item in payloads)
            != unit_cells_total
        ):
            errors.append("document_memory_cell_count_mismatch")
        if (
            sum(int(item.get("text_characters_total") or 0) for item in payloads)
            != unit_text_characters_total
        ):
            errors.append("document_memory_text_character_count_mismatch")
    if document.get("container_format") == "pdf":
        if int(summary.get("pdf_pages_total") or 0) <= 0:
            errors.append("document_memory_pdf_page_scope_missing")
        if int(summary.get("pdf_pages_total") or 0) != (
            int(summary.get("pdf_pages_with_text") or 0)
            + int(summary.get("pdf_pages_without_text") or 0)
        ):
            errors.append("document_memory_pdf_page_accounting_mismatch")
        visual_units_total = sum(
            1 for item in units if item.get("pdf_unit_type") == "pdf_visual_page_unit"
        )
        if int(summary.get("pdf_visual_pages_total") or 0) != visual_units_total:
            errors.append("document_memory_pdf_visual_unit_count_mismatch")
        if summary.get("pdf_visual_fallback_status") == "complete" and (
            int(summary.get("pdf_visual_requested_pages_total") or 0)
            != visual_units_total
        ):
            errors.append("document_memory_pdf_visual_coverage_incomplete")
    return sorted(set(errors))


def _source_checksum_ref(document: dict[str, Any]) -> str | None:
    document_ref = str(document.get("document_id") or "")
    checksum = str(document.get("sha256") or "")
    if not document_ref or not checksum:
        return None
    return "srcsum_" + stable_digest([document_ref, checksum], length=24)


def _integrity_hash(manifest: dict[str, Any]) -> str:
    material = copy.deepcopy(manifest)
    material.pop("integrity_hash", None)
    return hashlib.sha256(
        json.dumps(
            material,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _contains_private_fields(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            str(key).lower() in _PRIVATE_FIELD_NAMES or _contains_private_fields(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_private_fields(item) for item in value)
    return False


def _group_by(
    items: list[dict[str, Any]], field: str
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        value = str(item.get(field) or "")
        if value:
            result[value].append(item)
    return result


def _items_for_document(
    value: Any,
    document_ref: str,
    *,
    field: str,
) -> list[dict[str, Any]]:
    if isinstance(value, ArtifactStoreBackedList):
        return list(value.iter_document_compact(document_ref))
    return (
        [
            item
            for item in value or []
            if isinstance(item, dict) and str(item.get(field) or "") == document_ref
        ]
        if isinstance(value, list)
        else []
    )


def _documents(package: dict[str, Any]) -> list[dict[str, Any]]:
    return _dicts(_object(package.get("document_inventory")).get("documents"))


def _run_id(package: dict[str, Any]) -> str:
    return str(_object(package.get("normalization_run")).get("run_id") or "")


def _error(code: str, subject: Any) -> dict[str, str]:
    return {"code": code, "subject": str(subject or "")}


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return (
        [item for item in value or [] if isinstance(item, dict)]
        if isinstance(value, list)
        else []
    )


def _strings(value: Any) -> list[str]:
    return (
        [str(item) for item in value or [] if item is not None and str(item)]
        if isinstance(value, list)
        else []
    )
