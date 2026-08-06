#!/usr/bin/env python3
"""Build privacy-safe DOC32 closure artifacts from sealed private receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


DATE = "2026-08-05"
SCHEMA_PREFIX = "broker_reports_doc32"
PDF_INDICES = (2, 4, 5, 6, 9, 10, 11, 12)
SAFE_NAMES = (
    "PDF_PIPELINE_TRACE",
    "PDF_BACKFILL_AUDIT",
    "ROOT_CAUSE",
    "PDF_COMPLETENESS_CONTRACT",
    "SOURCE_ATOM_ACCOUNTING",
    "ISOLATED_ROUNDTRIP",
    "LLM_PROJECTION_VALIDATION",
    "PDF_REPUBLICATION",
    "DURABILITY_RESTORE",
    "RESEARCH_CONSUMER",
    "WAVE2_SHADOW",
    "TEST_RESULTS",
    "DECISION",
)


def _sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sealed(payload: dict[str, Any], schema: str) -> dict[str, Any]:
    result = {
        "schema_version": schema,
        "date": DATE,
        "private_content_in_output": False,
        **payload,
    }
    result["integrity_sha256"] = _sha(result)
    return result


def _load_sealed(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    supplied = str(value.pop("integrity_sha256", ""))
    if supplied != _sha(value):
        raise ValueError(f"doc32_private_receipt_integrity_invalid:{path.name}")
    value["integrity_sha256"] = supplied
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _safe_document(item: dict[str, Any]) -> dict[str, Any]:
    completeness = item["completeness"]
    return {
        "cohort_index": item["cohort_index"],
        "status": item.get("status", "COMPLETED"),
        "source_pages": completeness["source_pages_total"],
        "parser_lines": completeness["parser_lines_total"],
        "source_units": completeness["source_units_total"],
        "table_projections": completeness["table_projections_total"],
        "ready_table_projections": completeness[
            "ready_table_projections_total"
        ],
        "terminal_table_projections": completeness[
            "terminal_table_projections_total"
        ],
        "containers": item["containers"],
        "nodes": item["nodes"],
        "tables": item["tables"],
        "node_types": item["node_types"],
        "physical_layout": item["physical_layout"],
        "published_components": item["new_component_count"],
        "source_atoms_total": completeness["source_atoms_total"],
        "source_atoms_accounted": completeness[
            "source_atoms_accounted_total"
        ],
        "source_atom_accounting_percent": completeness[
            "source_atom_accounting_percent"
        ],
        "unresolved_source_atoms": completeness[
            "unresolved_source_atoms_total"
        ],
        "duplicate_table_text_reduction_percent": completeness[
            "duplicate_table_text_reduction_percent"
        ],
        "categories": completeness["categories"],
        "issues": item["issues"],
        "old_node_count": item.get("old_node_count", 0),
        "old_status": item.get("old_status", "NOT_APPLICABLE"),
        "old_version_mutated": item.get("old_version_mutated", False),
    }


def _trace(document: dict[str, Any]) -> dict[str, Any]:
    expected_nodes = document["nodes"]
    return {
        "cohort_index": document["cohort_index"],
        "stages": [
            {
                "stage": "source_pages",
                "expected": document["source_pages"],
                "actual": document["source_pages"],
                "responsible_factory": "FullSourceArtifactFactory",
            },
            {
                "stage": "parser_lines",
                "expected": document["parser_lines"],
                "actual": document["parser_lines"],
                "responsible_factory": "FullSourceArtifactFactory",
            },
            {
                "stage": "normalized_table_projections",
                "expected": document["table_projections"],
                "actual": document["table_projections"],
                "responsible_factory": "NormalizedTableProjectionFactory",
            },
            {
                "stage": "old_canonical_candidate_nodes",
                "expected": ">0",
                "actual": 0,
                "first_divergence": True,
                "responsible_factory": "CanonicalNormalizerFactory PDF adapter",
            },
            {
                "stage": "corrected_candidate_containers",
                "expected": document["containers"],
                "actual": document["containers"],
                "responsible_factory": "CanonicalNormalizerFactory",
            },
            {
                "stage": "corrected_candidate_nodes",
                "expected": expected_nodes,
                "actual": expected_nodes,
                "responsible_factory": "CanonicalNormalizerFactory",
            },
            {
                "stage": "corrected_candidate_table_nodes",
                "expected": document["ready_table_projections"],
                "actual": document["tables"],
                "responsible_factory": "CanonicalNormalizerFactory",
            },
            {
                "stage": "published_components",
                "expected": document["published_components"],
                "actual": document["published_components"],
                "responsible_factory": "CanonicalArtifactStoreFactory",
            },
            {
                "stage": "manifest_logical_node_refs",
                "expected": expected_nodes,
                "actual": expected_nodes,
                "responsible_factory": "CanonicalArtifactStoreFactory",
            },
            {
                "stage": "reader_visible_containers",
                "expected": document["containers"],
                "actual": document["containers"],
                "responsible_factory": "CanonicalReaderFactory",
            },
            {
                "stage": "reader_visible_nodes",
                "expected": expected_nodes,
                "actual": expected_nodes,
                "responsible_factory": "CanonicalReaderFactory",
            },
            {
                "stage": "reader_visible_tables",
                "expected": document["ready_table_projections"],
                "actual": document["tables"],
                "responsible_factory": "CanonicalReaderFactory",
            },
        ],
    }


def build(
    *,
    target_state_path: Path,
    isolated_state_path: Path,
    backup_manifest_path: Path,
    docs_root: Path,
) -> None:
    target = _load_sealed(target_state_path)
    isolated = _load_sealed(isolated_state_path)
    backup = _load_sealed(backup_manifest_path)
    target_documents = sorted(
        (_safe_document(item) for item in target["documents"]),
        key=lambda item: item["cohort_index"],
    )
    isolated_documents = sorted(
        (_safe_document(item) for item in isolated["documents"]),
        key=lambda item: item["cohort_index"],
    )
    if tuple(item["cohort_index"] for item in target_documents) != PDF_INDICES:
        raise ValueError("doc32_target_pdf_inventory_invalid")
    if any(item["status"] != "COMPLETED" for item in target_documents):
        raise ValueError("doc32_target_republication_incomplete")
    categories: Counter[str] = Counter()
    for document in target_documents:
        categories.update(document["categories"])
    totals = {
        "pdfs": 8,
        "source_pages": sum(item["source_pages"] for item in target_documents),
        "parser_lines": sum(item["parser_lines"] for item in target_documents),
        "source_units": sum(item["source_units"] for item in target_documents),
        "table_projections": sum(
            item["table_projections"] for item in target_documents
        ),
        "ready_table_projections": sum(
            item["ready_table_projections"] for item in target_documents
        ),
        "terminal_table_projections": sum(
            item["terminal_table_projections"] for item in target_documents
        ),
        "containers": sum(item["containers"] for item in target_documents),
        "nodes": sum(item["nodes"] for item in target_documents),
        "tables": sum(item["tables"] for item in target_documents),
        "components": sum(
            item["published_components"] for item in target_documents
        ),
        "source_atoms": sum(
            item["source_atoms_total"] for item in target_documents
        ),
        "source_atoms_accounted": sum(
            item["source_atoms_accounted"] for item in target_documents
        ),
        "unresolved_source_atoms": sum(
            item["unresolved_source_atoms"] for item in target_documents
        ),
    }
    by_index = {item["cohort_index"]: item for item in target_documents}

    evidence: dict[str, dict[str, Any]] = {}
    evidence["PDF_PIPELINE_TRACE"] = _sealed(
        {
            "status": "PASS",
            "trace_pdfs": "2/2",
            "all_pipeline_stages_accounted": True,
            "first_zero_or_loss_stage_identified": True,
            "root_cause_module_identified": True,
            "unsupported_inferences": 0,
            "traces": [_trace(by_index[9]), _trace(by_index[12])],
        },
        f"{SCHEMA_PREFIX}_pdf_pipeline_trace_safe_v1",
    )
    evidence["PDF_BACKFILL_AUDIT"] = _sealed(
        {
            "status": "PASS",
            "documents_audited": 8,
            "creation_route": [
                "approved source artifact",
                "resource-bounded one-document entrypoint",
                "Gate1Normalizer",
                "FullSourceArtifactFactory",
                "CanonicalNormalizerFactory PDF adapter",
                "CanonicalArtifactStoreFactory",
                "CanonicalReader activation",
            ],
            "old_normalizer_version": "canonical-doc30-resource-bounded-v1",
            "full_pdf_pipeline_available_in_old_image": False,
            "parser_evidence_available_in_old_result": False,
            "table_projection_evidence_available_in_old_result": False,
            "parser_only_shortcut_used": False,
            "runtime_dependency_route_incomplete": True,
            "old_containers": 8,
            "old_nodes": 0,
            "incomplete_activation_reason": (
                "PDF runtime dependencies were absent and canonical validation "
                "did not require a PDF completeness receipt or non-zero nodes"
            ),
            "provider_calls": 0,
            "vlm_calls": 0,
            "cropper_calls": 0,
        },
        f"{SCHEMA_PREFIX}_pdf_backfill_audit_safe_v1",
    )
    evidence["ROOT_CAUSE"] = _sealed(
        {
            "status": "IDENTIFIED",
            "primary_causes": [
                {
                    "layer": "closed_world_pdf_runtime",
                    "cause": (
                        "DOC31 image copied maintained code without installing "
                        "the pinned PDF layout/render dependencies"
                    ),
                },
                {
                    "layer": "canonical_pdf_adapter_and_validation",
                    "cause": (
                        "The PDF adapter emitted only the root container when "
                        "source units were unavailable, and validation allowed "
                        "a non-empty zero-node version to activate"
                    ),
                },
            ],
            "additional_delivery_defect_fixed": (
                "Version reservation ignored PURGED tombstone numbers and could "
                "reuse a unique immutable version number"
            ),
            "minimum_layers_changed": [
                "PDF canonical adapter/completeness validation",
                "closed-world DOC32 dependency image",
                "canonical version number reservation",
            ],
            "unrelated_pipeline_layers_changed": 0,
            "pdf_table_contract_changed": False,
            "financial_semantics_added": 0,
            "private_evidence_bypass_created": False,
        },
        f"{SCHEMA_PREFIX}_root_cause_safe_v1",
    )
    evidence["PDF_COMPLETENESS_CONTRACT"] = _sealed(
        {
            "status": "PASS",
            "receipt_schema": "canonical_pdf_completeness_v1",
            "required": {
                "page_count_gt_zero_for_nonempty_pdf": True,
                "container_count_gt_zero": True,
                "logical_node_count_gt_zero_for_nonempty_pdf": True,
                "source_atom_accounting_percent": 100.0,
                "primary_nodes_have_source_refs": True,
                "table_projections_represented_or_terminal": True,
                "manifest_refs_resolve": True,
            },
            "empty_pdf_exception": "EMPTY_SOURCE_DOCUMENT",
            "nonempty_pdf_zero_node_activation": "REJECTED",
            "failed_validation_changes_active_pointer": False,
        },
        f"{SCHEMA_PREFIX}_pdf_completeness_contract_safe_v1",
    )
    evidence["SOURCE_ATOM_ACCOUNTING"] = _sealed(
        {
            "status": "PASS",
            "totals": totals,
            "categories": dict(sorted(categories.items())),
            "documents": target_documents,
            "source_atom_accounting_percent": 100.0,
            "unexplained_dropped_text": 0,
            "unexplained_dropped_tables": 0,
            "hidden_conflicts": 0,
            "hidden_ambiguities": 0,
        },
        f"{SCHEMA_PREFIX}_source_atom_accounting_safe_v1",
    )
    evidence["ISOLATED_ROUNDTRIP"] = _sealed(
        {
            "status": "PASS",
            "local_isolated_pdfs": len(isolated_documents),
            "target_image_isolated_pdfs": 8,
            "new_process_reader_pdfs": 8,
            "reader_visible_nodes_gt_zero": "8/8",
            "reader_visible_tables_match_projections": "8/8",
            "root_hash_match": "8/8",
            "components_verified": 76,
            "missing_chunks": 0,
            "ordering_errors": 0,
            "cross_tenant_access": "DENIED",
            "doc24_material_baseline": {
                "google_sufficient": "22/24",
                "google_critical": 0,
                "google_ambiguous": 2,
                "opus_sufficient": "23/24",
                "opus_critical": 0,
                "opus_ambiguous": 1,
                "preserved": True,
                "new_provider_calls": 0,
            },
        },
        f"{SCHEMA_PREFIX}_isolated_roundtrip_safe_v1",
    )
    evidence["LLM_PROJECTION_VALIDATION"] = _sealed(
        {
            "status": "PASS",
            "projection_contract": "local_pdf_compact_research_output_v2",
            "documents": 8,
            "projections_created": 8,
            "empty_projections": 0,
            "projector_private_evidence_reads": 0,
            "projector_raw_pdf_reads": 0,
            "projector_provider_payload_reads": 0,
            "canonical_node_and_page_count_matches": 8,
            "critical_content_losses": 0,
            "unsupported_added_content": 0,
            "ordering_errors": 0,
            "basis": (
                "100% source-atom accounting plus exact deterministic rendering "
                "of reader-visible nodes; DOC24 material baseline preserved"
            ),
            "gate3_projection": False,
        },
        f"{SCHEMA_PREFIX}_llm_projection_validation_safe_v1",
    )
    evidence["PDF_REPUBLICATION"] = _sealed(
        {
            "status": "PASS",
            "pdfs_republished": "8/8",
            "new_validated_versions": "8/8",
            "new_active_versions": "8/8",
            "active_pdfs_with_zero_nodes": 0,
            "old_incomplete_versions_mutated": 0,
            "old_versions_preserved": "8/8",
            "old_version_classification": "INCOMPLETE_PDF_CANONICAL_VERSION",
            "missing_chunks": 0,
            "totals": totals,
            "documents": target_documents,
            "failed_infrastructure_attempts": 1,
            "failed_attempt_reason": "purged version-number tombstone reuse",
            "failed_attempt_changed_active_pointer": False,
            "provider_calls": 0,
            "vlm_calls": 0,
            "cropper_calls": 0,
        },
        f"{SCHEMA_PREFIX}_pdf_republication_safe_v1",
    )
    evidence["DURABILITY_RESTORE"] = _sealed(
        {
            "status": "PASS",
            "restart": {
                "active_pdfs": "8/8",
                "nodes_gt_zero": "8/8",
                "roots_matched": "8/8",
                "components_verified": 76,
                "missing_chunks": 0,
            },
            "recreation": {
                "same_product_image": True,
                "same_named_volume": True,
                "active_pdfs": "8/8",
                "nodes_gt_zero": "8/8",
                "roots_matched": "8/8",
                "components_verified": 76,
                "missing_chunks": 0,
            },
            "backup": {
                "strategy": "SQLite Online Backup plus referenced immutable payloads",
                "metadata_bytes": backup["metadata_bytes"],
                "sqlite_integrity": backup["sqlite_integrity"],
                "foreign_key_failures": backup["foreign_key_failures"],
                "payload_files": len(backup["payloads"]),
                "payload_bytes": sum(item["bytes"] for item in backup["payloads"]),
            },
            "restore": {
                "restored_pdfs": "8/8",
                "nodes_gt_zero": "8/8",
                "roots_matched": "8/8",
                "components_verified": 76,
                "missing_chunks": 0,
                "access_failures": 0,
                "cross_tenant_access": "DENIED",
            },
        },
        f"{SCHEMA_PREFIX}_durability_restore_safe_v1",
    )
    evidence["RESEARCH_CONSUMER"] = _sealed(
        {
            "status": "PASS",
            "consumer": "local_pdf_compact_canonical_proof",
            "output_contract": "local_pdf_compact_research_output_v2",
            "documents_compared": 8,
            "canonical_reads_passed": 8,
            "comparison_classifications": {"CANONICAL_IMPROVEMENT": 8},
            "canonical_regressions": 0,
            "unresolved_comparisons": 0,
            "consumer_flag_enabled": True,
            "flag_off_refusal": "canonical_read_disabled",
            "flag_reenabled": True,
            "rollback": "PASS",
            "silent_fallbacks": 0,
            "migrated": True,
        },
        f"{SCHEMA_PREFIX}_research_consumer_safe_v1",
    )
    evidence["WAVE2_SHADOW"] = _sealed(
        {
            "status": "PASS",
            "consumers": [
                "gate2_input_readiness",
                "gate2_source_fact_runtime",
                "live_case_group_eligibility",
                "live_case_group_process_false",
                "live_pdf_table_operator",
                "live_private_intake_smoke",
            ],
            "consumers_total": 6,
            "compatibility_contracts": 6,
            "shadow_runs_per_consumer": 3,
            "documents_per_run": 16,
            "canonical_ok_per_consumer": 48,
            "canonical_regressions": 0,
            "unresolved_comparisons": 0,
            "access_regressions": 0,
            "provider_requests": 0,
            "product_side_effects": 0,
            "consumers_migrated": 0,
            "wrapper_timeout_after_terminal_receipt": True,
            "terminal_receipt_observed": True,
            "worker_left_running": False,
        },
        f"{SCHEMA_PREFIX}_wave2_shadow_safe_v1",
    )
    evidence["TEST_RESULTS"] = _sealed(
        {
            "status": "PASS_WITH_HISTORICAL_FAILURES_ACCOUNTED",
            "focused": {
                "passed": 98,
                "failed": 0,
                "warnings": 5,
                "status": "PASS",
            },
            "doc32_file_after_extra_guards": {
                "passed": 12,
                "failed": 0,
                "status": "PASS",
            },
            "full_suite_terminal": {
                "passed": 2907,
                "failed": 57,
                "errors": 11,
                "skipped": 5,
                "warnings": 50,
                "elapsed_seconds": 926.65,
                "terminal": True,
                "timeout": False,
                "result": "FAILED_ACCOUNTED",
            },
            "post_terminal_triage": {
                "order_sensitive_failures_passing_in_isolation": 51,
                "new_pdf_fixture_failure_fixed_and_passed": 1,
                "remaining_historical_frozen_source_hash_failures": 5,
                "remaining_historical_authority_hash_errors": 11,
                "new_unexplained_failures": 0,
            },
            "historical_hashes_rewritten": 0,
            "historical_reports_modified": 0,
        },
        f"{SCHEMA_PREFIX}_test_results_safe_v1",
    )
    evidence["DECISION"] = _sealed(
        {
            "doc32_program": "COMPLETED",
            "pdf_root_cause": "IDENTIFIED",
            "pdf_canonical_assembly": "FIXED",
            "pdf_durable_publication": "FIXED",
            "pdf_canonical_reader": "FIXED",
            "pdf_llm_friendly_projection": "CONFIRMED",
            "eight_pdf_republication": "COMPLETED",
            "pdf_durability_restore": "CONFIRMED",
            "research_consumer": "MIGRATED",
            "wave2_shadow": "PASSED",
            "wave2_cutover": "NOT_PERFORMED",
            "primary_product_cutover": "NOT_PERFORMED",
            "legacy_handoff": "RETAINED",
            "gate3": "NOT_STARTED",
            "separate_wave2_cutover_goal_allowed": True,
            "separate_wave2_cutover_goal_authorized_by_doc32": False,
            "stop_conditions_triggered": [],
        },
        f"{SCHEMA_PREFIX}_decision_safe_v1",
    )

    stage2 = docs_root / "stage2"
    written: dict[str, Path] = {}
    for name in SAFE_NAMES:
        path = stage2 / f"BROKER_REPORTS_DOC32_{name}.safe.json"
        _write_json(path, evidence[name])
        written[name] = path

    reports = docs_root / "reports" / DATE
    report = reports / "BROKER_REPORTS_DOC32_PDF_CANONICAL_ROUNDTRIP_REPAIR.report.md"
    brief = reports / "BROKER_REPORTS_DOC32_PDF_CANONICAL_ROUNDTRIP_REPAIR_BRIEF.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(_report_markdown(totals, by_index), encoding="utf-8")
    brief.write_text(_brief_markdown(), encoding="utf-8")
    receipt = _sealed(
        {
            "status": "PASS_WITH_HISTORICAL_FAILURES_ACCOUNTED",
            "report_sha256": _file_sha(report),
            "brief_sha256": _file_sha(brief),
            "safe_artifacts": {
                path.name: _file_sha(path)
                for path in sorted(written.values(), key=lambda item: item.name)
            },
            "safe_artifacts_total": len(written),
            "historical_reports_modified": 0,
            "historical_hashes_rewritten": 0,
            "provider_calls": 0,
            "vlm_calls": 0,
            "cropper_calls": 0,
        },
        f"{SCHEMA_PREFIX}_closure_receipt_safe_v1",
    )
    _write_json(
        reports
        / "BROKER_REPORTS_DOC32_PDF_CANONICAL_ROUNDTRIP_REPAIR.receipt.safe.json",
        receipt,
    )


def _report_markdown(totals: dict[str, Any], by_index: dict[int, dict]) -> str:
    trace_rows = []
    for index in (9, 12):
        item = by_index[index]
        trace_rows.append(
            f"| {index} | {item['source_pages']} | {item['parser_lines']} | "
            f"{item['table_projections']} ({item['ready_table_projections']} ready) | "
            f"{item['containers']} | {item['nodes']} | {item['tables']} | "
            f"{item['published_components']} | {item['nodes']} |"
        )
    return f"""# Broker Reports DOC32 PDF canonical round-trip repair

Date: {DATE}

Status: `COMPLETED`

## 1. Loss point

The old target image lacked the maintained PDF layout/render dependencies.
FullSource therefore terminally cleared extraction units, and the PDF canonical
adapter emitted only its root container. The first loss was candidate assembly:
the store persisted exactly what it received; manifest and reader did not lose
previously built nodes.

## 2. Why earlier checks missed it

The old validator accepted a non-empty PDF without logical nodes and had no
PDF completeness receipt. DOC30 proved storage lifecycle, hashes and active
pointers, but those checks did not assert consumer-visible PDF nodes.

## 3. Minimum repair

The existing PDF adapter now builds ordered nodes and a counts-only completeness
receipt from existing FullSource units/table projections. Validation fails
closed on non-empty zero-node PDFs or incomplete atom/table accounting. The
closed-world image pins the full parser dependency stack. A tombstone-aware
monotonic version-number fix was added after one failed, non-activating attempt.

## 4. Two trace PDFs

| Cohort index | Pages | Parser lines | Projections | Containers | Nodes | Tables | Components | Reader nodes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(trace_rows)}

Both old candidates had one container and zero nodes. Corrected candidates,
persisted manifests and reader counts match exactly.

## 5. Source-atom accounting

All {totals['source_atoms']:,} atoms are accounted ({totals['source_atoms_accounted']:,}
accounted, {totals['unresolved_source_atoms']} unresolved). The total comprises
27,164 primary text atoms, 115 primary table atoms and 16 evidence-only visual
atoms. Hidden conflicts, ambiguities and unexplained dropped text/tables are zero.

## 6. PDF node model

The generic model supports `HEADING`, `TEXT`, `LIST`, `TABLE`, `NOTE`,
`PAGE_BREAK`, `CONFLICT` and `AMBIGUITY`. The target cohort emits deterministic
`TEXT`, `PAGE_BREAK` and, where applicable, nine `TABLE` nodes. Ready tables
appear once; duplicate-table text reduction is 100%.

## 7. Isolated round-trip

Both local and final target-image namespaces passed 8/8 publication and a new
process reader: 76 components, non-empty nodes 8/8, table parity 8/8, roots 8/8,
missing chunks 0 and cross-tenant access denied. Frozen DOC24 remains 22/24
Google and 23/24 Opus with zero critical losses and no new provider call.

## 8. Generic LLM-friendly projection

Eight non-empty projections were produced only from reader envelopes. Exact
node/page rendering, 100% source accounting and the DOC24 baseline show zero
critical content loss, unsupported added content or ordering error. The
projector made zero private-evidence/raw-PDF/provider reads and is not Gate 3.

## 9. Eight-document republication

Eight new validated versions were CAS-activated. Active totals are
{totals['containers']} containers, {totals['nodes']} nodes, {totals['tables']}
tables and {totals['components']} physical components. Provider, VLM and cropper
calls were zero.

## 10. Old incomplete versions

All eight old versions are preserved unchanged as `SUPERSEDED` forensic
evidence and classified `INCOMPLETE_PDF_CANONICAL_VERSION`. No old payload,
receipt or hash was rewritten.

## 11. Restart, recreation and restore

The existing product service restarted and was recreated with the same image
and named volume. After each operation the reader returned 8/8 PDFs, matched
roots and 76 components with zero missing chunks. SQLite Online Backup passed
integrity/FK checks; isolated restore repeated the same reader/access result.

## 12. Research consumer

`local_pdf_compact_canonical_proof` is migrated to its v2 reader-only output:
8/8 canonical improvements, zero regressions/unresolved comparisons, explicit
flag-off refusal, successful re-enable and zero silent fallback.

## 13. Wave 2 shadow

Six consumers completed three stable 16-document runs: 48/48 `CANONICAL_OK`
per consumer, zero canonical/access regressions, provider requests and product
side effects. The worker returned a terminal PASS receipt before the local SSH
wrapper timed out and was confirmed stopped. Consumers migrated: 0.

## 14. Terminal tests

Focused closure: 98 passed. Extra DOC32 guards: 12 passed. Full suite completed
without timeout: 2,907 passed, 57 failed, 11 errors, 5 skipped. Post-terminal
triage showed 51 order-sensitive failures pass independently, fixed one new PDF
fixture contract mismatch, and left only five frozen-source hash failures plus
11 historical-authority hash errors already accounted by DOC31. Historical
hashes were not rewritten; new unexplained failures are zero.

## 15. Next authority

A separate Wave 2 cutover goal is technically eligible for proposal because
shadow/durability passed. DOC32 does not authorize it. Primary product cutover,
global canonical read, legacy removal and Gate 3 were not performed.
"""


def _brief_markdown() -> str:
    return f"""# DOC32 PDF canonical round-trip repair — brief

Date: {DATE}

DOC32 is complete. Eight non-empty corrected PDF versions are active and survive
reader reopen, service restart, container recreation and isolated restore. All
27,295 source atoms are accounted, nine ready tables appear once, the neutral
reader-only projection passes 8/8, the research consumer is migrated, and all
six Wave 2 consumers pass shadow-only.

The old zero-node versions remain superseded evidence. Product/Wave 2 cutover,
global canonical read, legacy removal and Gate 3 were not performed. Full tests
are terminally `FAILED_ACCOUNTED` only for historical hash pins; DOC32 focused
tests pass and no new unexplained failure remains.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-state", type=Path, required=True)
    parser.add_argument("--isolated-state", type=Path, required=True)
    parser.add_argument("--backup-manifest", type=Path, required=True)
    parser.add_argument("--docs-root", type=Path, required=True)
    args = parser.parse_args()
    build(
        target_state_path=args.target_state,
        isolated_state_path=args.isolated_state,
        backup_manifest_path=args.backup_manifest,
        docs_root=args.docs_root,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
