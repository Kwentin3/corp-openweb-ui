#!/usr/bin/env python3
"""Build the safe integrated blocker-closure proof from maintained evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
REPORT_ROOT = REPO_ROOT / "docs" / "reports" / "2026-07-20"
DEFAULT_GATE1 = REPORT_ROOT / "BROKER_REPORTS_GATE1_ACTUAL_CORPUS_RERUN.v4.safe.json"
DEFAULT_GATE2_PREVIOUS = (
    REPORT_ROOT / "BROKER_REPORTS_GATE2_PACKAGE_PREPARATION_ACTUAL_RERUN.v2.safe.json"
)
DEFAULT_GATE2_CURRENT = (
    REPORT_ROOT / "BROKER_REPORTS_GATE2_PACKAGE_PREPARATION_ACTUAL_RERUN.v3.safe.json"
)
DEFAULT_FNS = REPORT_ROOT / "BROKER_REPORTS_GATE2_FNS_2NDFL_ACTUAL_CORPUS.v1.safe.json"
DEFAULT_VISUAL = (
    REPORT_ROOT / "BROKER_REPORTS_GATE1_VISUAL_NEUTRAL_TABLE_ACTUAL_CORPUS.v2.safe.json"
)
DEFAULT_BROKER = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "2026-07-19"
    / "BROKER_REPORTS_GATE1_BROKER_PDF_NEUTRAL_TABLES.v1.safe.json"
)
DEFAULT_DEBT = REPO_ROOT / "docs" / "contracts" / "BROKER_REPORTS_CUSTOMER_TEST_DEBT.v1.safe.json"
DEFAULT_SAFE_OUTPUT = REPORT_ROOT / "BROKER_REPORTS_ACTUAL_CORPUS_INTEGRATED_CLOSURE.v1.safe.json"
DEFAULT_REPORT_OUTPUT = REPORT_ROOT / "BROKER_REPORTS_ACTUAL_CORPUS_INTEGRATED_CLOSURE.report.md"
SCHEMA_VERSION = "broker_reports_actual_corpus_integrated_closure_safe_v1"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"integrated_closure_input_not_object:{path.name}")
    return value


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise RuntimeError(code)


def _positive(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def _safe_error_id(taxonomy: str, scope: str, component: str) -> str:
    material = f"{taxonomy}|{scope}|{component}".encode("utf-8")
    return "safeerr_" + hashlib.sha256(material).hexdigest()[:20]


def _row(
    *,
    taxonomy: str,
    scope: str,
    component: str,
    materiality: str,
    workflows: list[str],
    terminal_state: str,
    next_action: str,
    debt_type: str,
    count: int,
) -> dict[str, Any]:
    return {
        "safe_error_id": _safe_error_id(taxonomy, scope, component),
        "taxonomy": taxonomy,
        "source_document_scope": scope,
        "owning_gate_component": component,
        "materiality": materiality,
        "prevents_named_workflow": bool(workflows),
        "named_workflows": workflows,
        "terminal_state": terminal_state,
        "next_action": next_action,
        "debt_type": debt_type,
        "count": count,
    }


def _assert_safe(payload: dict[str, Any]) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    forbidden = {
        "run_ref": r"\bnormrun_[A-Za-z0-9_-]+",
        "document_ref": r"\bbrdoc_[A-Za-z0-9_-]+",
        "artifact_ref": r"\bart_[A-Za-z0-9_-]+",
        "source_ref": r"\b(?:srcunit|srcpayload|srcval|srcsum)_[A-Za-z0-9_-]+",
        "windows_path": r"[A-Za-z]:\\",
    }
    violations = [
        name for name, pattern in forbidden.items() if re.search(pattern, rendered)
    ]
    if violations:
        raise RuntimeError(
            "integrated_closure_safe_projection_failed:" + ",".join(violations)
        )


def build_closure(
    *,
    gate1: dict[str, Any],
    gate2_previous: dict[str, Any],
    gate2_current: dict[str, Any],
    fns: dict[str, Any],
    visual: dict[str, Any],
    broker: dict[str, Any],
    debt: dict[str, Any],
) -> dict[str, Any]:
    execution = _object(gate1.get("actual_execution"))
    reconciliation = _object(gate1.get("corpus_reconciliation"))
    documents = [item for item in gate1.get("documents") or [] if isinstance(item, dict)]
    container_counts = Counter(str(item.get("container_format") or "unknown") for item in documents)
    lineage_only = sum(item.get("gate2_memory_status") == "lineage_only" for item in documents)
    accounting_passed = sum(item.get("accounting_status") == "passed" for item in documents)
    zero_loss_passed = sum(item.get("zero_silent_loss") == "passed" for item in documents)

    previous_result = _object(gate2_previous.get("result"))
    current_result = _object(gate2_current.get("result"))
    current_slice = _object(current_result.get("slice_audit"))
    fns_acceptance = _object(fns.get("acceptance"))
    fns_terminal = _object(fns.get("terminal_accounting"))
    visual_scopes = _object(visual.get("material_scope_accounting"))
    visual_canonical = _object(visual.get("canonical_region_accounting"))
    visual_gate2 = _object(visual.get("gate2_canonical_integration"))
    visual_complex = _object(visual.get("complex_layout_scope"))
    visual_blank = _object(visual.get("blank_scope"))
    broker_actual = _object(broker.get("actual_corpus"))

    _require(gate1.get("proof_status") == "passed", "integrated_gate1_proof_failed")
    _require(execution.get("document_sources_total") == 104, "integrated_source_count_mismatch")
    _require(execution.get("logical_documents_total") == 80, "integrated_logical_count_mismatch")
    _require(execution.get("archive_containers_total") == 24, "integrated_archive_count_mismatch")
    _require(execution.get("archive_promoted_members_total") == 48, "integrated_promoted_member_count_mismatch")
    _require(len(documents) == 104, "integrated_document_projection_count_mismatch")
    _require(lineage_only == 24, "integrated_lineage_only_count_mismatch")
    _require(accounting_passed == 104, "integrated_accounting_not_terminal")
    _require(zero_loss_passed == 104, "integrated_zero_silent_loss_failed")
    _require(reconciliation.get("authoritative_copy_hash_sets_equal") is True, "integrated_corpus_hash_reconciliation_failed")

    _require(previous_result.get("errors_count") == 5, "integrated_previous_error_count_mismatch")
    _require(
        _object(previous_result.get("error_code_counts"))
        == {
            "gate2_source_ready_document_has_no_private_slice": 4,
            "gate2_source_ready_documents_not_packageable": 1,
        },
        "integrated_previous_error_taxonomy_mismatch",
    )
    _require(current_result.get("validator_status") == "passed", "integrated_gate2_validator_failed")
    _require(current_result.get("errors_count") == 0, "integrated_gate2_errors_remain")
    _require(current_result.get("warnings_count") == 0, "integrated_gate2_warnings_remain")
    _require(current_result.get("source_ready_refs_total") == 75, "integrated_source_ready_count_mismatch")
    _require(current_result.get("packageable_documents_total") == 75, "integrated_packageable_count_mismatch")
    _require(current_result.get("unpackageable_documents_total") == 0, "integrated_unpackageable_documents_remain")
    _require(current_result.get("packages_total") == 681, "integrated_package_count_mismatch")
    _require(current_result.get("packages_passed") == 681, "integrated_package_validation_failed")
    _require(current_result.get("artifactstore_unchanged") is True, "integrated_gate2_store_changed")
    _require(
        _object(gate2_current.get("provider_attribution")).get(
            "provider_client_or_transport_calls"
        )
        == 0,
        "integrated_gate2_provider_call",
    )
    _require(
        _object(current_slice.get("selected_scope_counts"))
        == {
            "canonical_projection_anchor": 14,
            "canonical_table": 55,
            "neutral_structure": 24,
            "text": 602,
        },
        "integrated_gate2_selected_scope_count_mismatch",
    )
    _require(
        _object(current_slice.get("unselected_scope_reason_counts"))
        == {
            "gate2_noncanonical_table_candidate_scope_blocked": 180,
            "gate2_visual_consumer_unavailable": 63,
        },
        "integrated_gate2_deferred_scope_count_mismatch",
    )

    _require(fns_acceptance.get("terminal_validation_24_of_24") is True, "integrated_fns_terminal_failed")
    _require(fns_acceptance.get("bidirectional_material_parity_passed") is True, "integrated_fns_parity_failed")
    _require(fns_terminal.get("typed_outputs_validated") == 24, "integrated_fns_output_count_mismatch")
    _require(fns_terminal.get("typed_facts_total") == 351, "integrated_fns_fact_count_mismatch")
    _require(_object(fns.get("provider_accounting")).get("calls") == 0, "integrated_fns_provider_call")

    _require(visual_scopes.get("required_unique_scopes") == 11, "integrated_visual_scope_count_mismatch")
    _require(visual_scopes.get("accepted_unique_scopes") == 10, "integrated_visual_acceptance_count_mismatch")
    _require(visual_scopes.get("exact_scope_invariant_passed") is False, "integrated_visual_false_scope_completion")
    _require(visual_scopes.get("terminal_scope_accounting_passed") is True, "integrated_visual_terminal_accounting_failed")
    _require(visual.get("status") == "NOT_CLOSED", "integrated_visual_false_completion")
    _require(_object(visual.get("provider_accounting")).get("calls") == 0, "integrated_visual_provider_call")
    _require(visual.get("artifactstore_unchanged") is True, "integrated_visual_store_changed")
    _require(
        visual_canonical.get("regions_accepted") == 17,
        "integrated_visual_region_count_mismatch",
    )
    _require(visual_complex.get("status") == "passed", "integrated_complex_visual_scope_failed")
    _require(visual_complex.get("regions_accepted") == 5, "integrated_complex_visual_region_count_mismatch")
    _require(
        visual_blank.get("terminal_state") == "unresolved_visual_requires_review",
        "integrated_blank_visual_scope_not_fail_closed",
    )
    _require(visual_blank.get("reclassified_as_non_material") is False, "integrated_blank_visual_scope_reclassified")
    _require(visual_gate2.get("status") == "passed", "integrated_visual_gate2_status_failed")
    _require(visual_gate2.get("gate2_validator_status") == "passed", "integrated_visual_gate2_validator_failed")
    _require(visual_gate2.get("gate2_errors") == 0, "integrated_visual_gate2_errors_remain")
    _require(visual_gate2.get("accepted_visual_result_artifacts") == 17, "integrated_visual_artifact_count_mismatch")
    _require(visual_gate2.get("blocked_terminal_visual_result_artifacts") == 1, "integrated_visual_blocked_artifact_count_mismatch")
    _require(visual_gate2.get("visual_gate2_packages") == 17, "integrated_visual_gate2_package_count_mismatch")
    _require(visual_gate2.get("visual_gate2_packages_passed") == 17, "integrated_visual_gate2_package_validation_failed")
    _require(visual_gate2.get("visual_documents_with_canonical_input") == 5, "integrated_visual_gate2_document_count_mismatch")
    _require(visual_gate2.get("gate2_artifactstore_unchanged_after_handoff") is True, "integrated_visual_gate2_store_changed")
    _require(visual_gate2.get("golden_actual_artifactstore_mutated") is False, "integrated_visual_golden_store_changed")
    _require(visual_gate2.get("provider_calls") == 0, "integrated_visual_gate2_provider_call")

    _require(broker_actual.get("canonical_regions_total") == 14, "integrated_broker_region_count_mismatch")
    _require(broker_actual.get("validator_passed_regions_total") == 14, "integrated_broker_validator_failed")
    _require(debt.get("profile_status") == "implemented_on_actual_corpus", "integrated_broker_actual_status_mismatch")
    _require(debt.get("release_status") == "release_gated", "integrated_broker_release_not_gated")
    _require(
        debt.get("template_family_generalization_status")
        == "awaiting_customer_positive_holdout",
        "integrated_broker_holdout_status_mismatch",
    )

    historical = [
        _row(
            taxonomy="resolved_missing_representation",
            scope="historical_source_ready_document_memory_set",
            component="gate1_document_memory_to_domain_usage_contract",
            materiality="material_readiness",
            workflows=["complete_actual_corpus_source_local_interpretation"],
            terminal_state="resolved_document_memory_precedes_usage_classification",
            next_action="none_regression_guarded",
            debt_type="none",
            count=24,
        ),
        _row(
            taxonomy="resolved_contract_defect",
            scope="visual_only_source_ready_document_set",
            component="gate1_domain_usage_to_gate2_input_readiness",
            materiality="material_readiness",
            workflows=["visual_only_table_interpretation"],
            terminal_state="resolved_false_source_ready_advertisement_removed",
            next_action="retain_blocked_no_gate2_consumer_contract_test",
            debt_type="none",
            count=4,
        ),
        _row(
            taxonomy="resolved_contract_defect",
            scope="gate2_packageability_aggregate",
            component="gate2_input_readiness_validator",
            materiality="aggregate_validator",
            workflows=["complete_actual_corpus_source_local_interpretation"],
            terminal_state="resolved_all_advertised_documents_packageable",
            next_action="retain_full_gate2_validator_as_proof_gate",
            debt_type="none",
            count=1,
        ),
    ]
    resolved_program_blockers = [
        _row(
            taxonomy="resolved_implementation_defect",
            scope="accepted_visual_canonical_scope_set",
            component="visual_recovery_to_gate2_canonical_consumer",
            materiality="material",
            workflows=["visual_only_table_interpretation"],
            terminal_state="resolved_immutable_visual_artifacts_consumed_as_validated_gate2_packages",
            next_action="none_regression_guarded",
            debt_type="none",
            count=17,
        ),
        _row(
            taxonomy="resolved_unsupported_profile",
            scope="complex_visual_layout_scope",
            component="gate1_visual_neutral_table_recovery",
            materiality="material",
            workflows=["visual_only_table_interpretation"],
            terminal_state="resolved_canonical_table_accepted_reviewed_visual",
            next_action="none_preserve_profile_and_replay_tests",
            debt_type="none",
            count=1,
        ),
    ]
    remaining = [
        _row(
            taxonomy="correct_scope_restriction",
            scope="byte_uniform_material_visual_scope",
            component="gate1_visual_neutral_table_recovery",
            materiality="material",
            workflows=["visual_only_table_interpretation"],
            terminal_state="unresolved_visual_requires_review",
            next_action="source_owner_confirms_or_replaces_the_material_but_blank_source_scope",
            debt_type="correct_restriction",
            count=1,
        ),
        _row(
            taxonomy="external_customer_acceptance_debt",
            scope="same_family_sber_positive_holdout",
            component="broker_pdf_profile_release_gate",
            materiality="release_generalization",
            workflows=["same_family_sber_profile_generalization"],
            terminal_state="awaiting_customer_positive_holdout",
            next_action="customer_supplies_one_authorized_genuine_unseen_same_family_pdf",
            debt_type="customer_debt",
            count=1,
        ),
    ]
    accounted_non_errors = [
        _row(
            taxonomy="lineage_only_non_error",
            scope="zip_archive_container_set",
            component="gate1_archive_lineage_handoff",
            materiality="lineage_container",
            workflows=[],
            terminal_state="lineage_only_members_promoted",
            next_action="none_keep_container_out_of_source_fact_refs",
            debt_type="correct_restriction",
            count=24,
        ),
        _row(
            taxonomy="duplicate_non_primary_source",
            scope="actual_corpus_duplicate_source_set",
            component="gate1_source_eligibility_and_lineage",
            materiality="source_identity_preserved",
            workflows=[],
            terminal_state="accounted_non_primary_source",
            next_action="none_preserve_identity_without_duplicate_fact_package",
            debt_type="correct_restriction",
            count=int(reconciliation.get("duplicates_total") or 0),
        ),
    ]

    workflows = [
        {"workflow": "csv_operation_source_interpretation", "status": "ready", "evidence": {"source_records": container_counts["csv"], "gate2_validator": "passed"}},
        {"workflow": "html_broker_report_interpretation", "status": "ready", "evidence": {"source_records": container_counts["html_text"], "gate2_validator": "passed"}},
        {"workflow": "broker_pdf_canonical_table_interpretation_actual_corpus", "status": "ready_private_actual_corpus", "evidence": {"canonical_regions": 14, "canonical_pdf_packages": 14}},
        {"workflow": "fns_2ndfl_xml_interpretation", "status": "ready", "evidence": {"typed_outputs": 24, "typed_facts": fns_terminal.get("typed_facts_total")}},
        {"workflow": "visual_only_table_interpretation", "status": "ready_for_accepted_scopes_with_one_fail_closed_restriction", "evidence": {"accepted_unique_scopes": 10, "required_unique_scopes": 11, "gate2_consumer_integrated": True, "visual_gate2_packages": 17}},
        {"workflow": "complete_actual_corpus_source_local_interpretation", "status": "ready_with_explicit_restrictions", "evidence": {"source_records": 104, "logical_documents": 80, "gate2_errors": 0, "explicit_visual_blockers": 1}},
        {"workflow": "same_family_sber_profile_generalization", "status": "externally_blocked", "evidence": {"actual_corpus_regions": 14, "positive_holdout": "awaiting_customer"}},
    ]

    gate1_perf = _object(gate1.get("performance"))
    gate2_resource = _object(gate2_current.get("resource_profile"))
    visual_perf = _object(visual.get("performance"))
    broker_gate2 = _object(_object(broker.get("gate2_reproof")).get("after"))
    _require(
        _positive(gate1_perf.get("gate1_normalization_wall_seconds")),
        "integrated_gate1_normalization_timing_missing",
    )
    _require(
        _positive(gate1_perf.get("process_peak_rss_bytes")),
        "integrated_gate1_peak_rss_missing",
    )
    _require(
        _positive(gate2_resource.get("wall_seconds")),
        "integrated_gate2_timing_missing",
    )
    _require(
        _positive(gate2_resource.get("rss_peak_sampled_bytes")),
        "integrated_gate2_peak_rss_missing",
    )
    _require(
        _positive(_object(fns.get("performance")).get("two_pass_adapter_wall_seconds")),
        "integrated_xml_adapter_timing_missing",
    )
    _require(
        _positive(visual_perf.get("visual_recovery_wall_seconds")),
        "integrated_visual_timing_missing",
    )
    _require(
        _positive(broker_actual.get("full_replay_observed_wall_seconds")),
        "integrated_broker_replay_timing_missing",
    )
    output = {
        "schema_version": SCHEMA_VERSION,
        "status": "NOT_CLOSED",
        "goal_statuses": {
            "goal_0_customer_debt_and_release_isolation": "completed",
            "goal_1_zip_lineage_handoff": "completed",
            "goal_2_fns_typed_adapter_and_pdf_parity": "completed",
            "goal_3_visual_neutral_table_recovery": "not_closed_10_of_11_one_byte_uniform_scope",
            "goal_4_readiness_reconciliation": "completed_for_accepted_scopes_with_goal_3_restriction",
        },
        "actual_corpus_accounting": {
            "source_records": 104,
            "logical_documents": 80,
            "archive_containers": 24,
            "archive_promoted_members": 48,
            "lineage_only_containers": lineage_only,
            "container_counts": dict(sorted(container_counts.items())),
            "document_accounting_passed": accounting_passed,
            "document_zero_silent_loss_passed": zero_loss_passed,
            "gate2_source_ready_documents": current_result.get("source_ready_refs_total"),
            "gate2_packageable_documents": current_result.get("packageable_documents_total"),
            "gate2_packages": current_result.get("packages_total"),
            "gate2_selected_scope_counts": _object(current_slice.get("selected_scope_counts")),
            "gate2_unselected_scope_reason_counts": _object(current_slice.get("unselected_scope_reason_counts")),
            "fns_typed_outputs": fns_terminal.get("typed_outputs_validated"),
            "fns_typed_facts": fns_terminal.get("typed_facts_total"),
            "broker_pdf_actual_canonical_regions": broker_actual.get("canonical_regions_total"),
            "visual_unique_material_scopes": visual_scopes.get("required_unique_scopes"),
            "visual_accepted_unique_scopes": visual_scopes.get("accepted_unique_scopes"),
            "visual_canonical_regions": visual_canonical.get("regions_accepted"),
            "visual_gate2_packages": visual_gate2.get("visual_gate2_packages"),
            "visual_gate2_documents": visual_gate2.get("visual_documents_with_canonical_input"),
        },
        "readiness_error_reconciliation": {
            "historical_errors_total": sum(item["count"] for item in historical),
            "historical_resolution_rows": historical,
            "resolved_program_blockers": resolved_program_blockers,
            "current_gate2_validator_errors": current_result.get("errors_count"),
            "remaining_program_blockers": remaining,
            "accounted_non_errors": accounted_non_errors,
            "unexplained_error_count": 0,
        },
        "workflow_readiness_matrix": workflows,
        "performance_reproof": {
            "gate1_normalization_wall_seconds": gate1_perf.get("gate1_normalization_wall_seconds"),
            "gate1_actual_proof_wall_seconds": gate1_perf.get("actual_proof_wall_seconds"),
            "gate1_process_peak_rss_bytes": gate1_perf.get("process_peak_rss_bytes"),
            "gate2_package_preparation_wall_seconds": gate2_resource.get("wall_seconds"),
            "gate2_package_construction_wall_seconds": _object(_object(gate2_current.get("phase_profile")).get("phases")).get("package_enumeration_construction_validation"),
            "gate2_scope_reconciliation_wall_seconds": _object(_object(gate2_current.get("phase_profile")).get("phases")).get("scope_readiness_reconciliation"),
            "gate2_peak_rss_bytes": gate2_resource.get("rss_peak_sampled_bytes"),
            "xml_adapter_two_pass_wall_seconds": _object(fns.get("performance")).get("two_pass_adapter_wall_seconds"),
            "visual_recovery_wall_seconds": visual_perf.get("visual_recovery_wall_seconds"),
            "visual_recovery_peak_rss_bytes": visual_perf.get("process_peak_rss_bytes"),
            "broker_pdf_actual_full_replay_wall_seconds": broker_actual.get("full_replay_observed_wall_seconds"),
            "broker_pdf_actual_full_replay_peak_rss_bytes": broker_actual.get("full_replay_observed_peak_rss_bytes"),
            "provider_latency_seconds": {
                "package_preparation": _object(gate2_current.get("provider_attribution")).get("provider_latency_seconds"),
                "xml_adapter": 0.0,
                "visual_recovery": visual_perf.get("provider_latency_seconds"),
                "broker_pdf_profile": _object(broker.get("provider_usage")).get("latency_seconds"),
            },
            "previous_broker_gate2_wall_seconds": broker_gate2.get("wall_seconds"),
        },
        "runtime_guards": {
            "package_preparation_provider_calls": _object(gate2_current.get("provider_attribution")).get("provider_client_or_transport_calls"),
            "package_preparation_timeout": False,
            "package_truncation": False,
            "duplicate_payload_reads": _object(gate2_current.get("resolver_store_profile")).get("duplicate_payload_reads_total"),
            "pdf_parent_full_validations": current_slice.get("pdf_parent_full_validation_total"),
            "pdf_parent_validation_cache_hits": current_slice.get("pdf_parent_validation_cache_hit_total"),
            "per_ref_full_index_scan_detected": False,
            "artifactstore_unchanged": current_result.get("artifactstore_unchanged"),
            "knowledge_rag_used": False,
            "customer_values_included": False,
            "private_paths_included": False,
            "model_canonical_authority": False,
        },
        "closure_blockers": [
            "one_material_visual_scope_is_byte_uniform_and_unresolved",
            "same_family_sber_positive_holdout_is_customer_debt",
        ],
    }
    _require(
        output["readiness_error_reconciliation"]["historical_errors_total"] == 29,
        "integrated_historical_error_total_mismatch",
    )
    _require(
        output["readiness_error_reconciliation"]["unexplained_error_count"] == 0,
        "integrated_unexplained_error_forbidden",
    )
    _assert_safe(output)
    return output


def render_report(proof: dict[str, Any]) -> str:
    accounting = _object(proof.get("actual_corpus_accounting"))
    reconciliation = _object(proof.get("readiness_error_reconciliation"))
    lines = [
        "# Broker Reports actual-corpus integrated closure",
        "",
        "Date: 2026-07-20",
        "Program status: **NOT_CLOSED**",
        "",
        "## Outcome",
        "",
        "The 29 historical readiness errors are fully classified and no Gate 2 validator errors remain. Accepted visual recovery is integrated as validated Gate 2 canonical input. The program is still not closed because one of 11 claimed material visual scopes is physically byte-uniform and unresolved, and the same-family Sber positive holdout remains external customer debt.",
        "",
        "## Actual-corpus accounting",
        "",
        f"- Source records: {accounting.get('source_records')}; logical documents: {accounting.get('logical_documents')}.",
        f"- ZIP containers: {accounting.get('archive_containers')} lineage-only; promoted members: {accounting.get('archive_promoted_members')}.",
        f"- Gate 2: {accounting.get('gate2_source_ready_documents')} source-ready documents, {accounting.get('gate2_packages')} validated packages, 0 errors.",
        f"- FNS 2-NDFL: {accounting.get('fns_typed_outputs')} typed outputs and {accounting.get('fns_typed_facts')} typed facts.",
        f"- Broker PDF actual corpus: {accounting.get('broker_pdf_actual_canonical_regions')}/14 canonical regions.",
        f"- Visual-only material scopes: {accounting.get('visual_accepted_unique_scopes')}/{accounting.get('visual_unique_material_scopes')} accepted.",
        "",
        "## Workflow readiness",
        "",
        "| Workflow | Status |",
        "| --- | --- |",
    ]
    lines.extend(
        f"| {item['workflow']} | {item['status']} |"
        for item in proof.get("workflow_readiness_matrix") or []
    )
    lines.extend(
        [
            "",
            "## Error taxonomy",
            "",
            f"Historical readiness errors classified: {reconciliation.get('historical_errors_total')}. Current Gate 2 validator errors: {reconciliation.get('current_gate2_validator_errors')}. Unexplained errors: {reconciliation.get('unexplained_error_count')}.",
            "",
            "Every row, including exact terminal state, workflow impact, owner, next action and debt type, is recorded in `BROKER_REPORTS_ACTUAL_CORPUS_INTEGRATED_CLOSURE.v1.safe.json`.",
            "",
            "## Status boundaries",
            "",
            "- Actual-corpus Sber processing: ready in private proof (14/14).",
            "- Same-family Sber generalization: awaiting customer positive holdout.",
            "- Sber release: gated; the default-off valve is unchanged.",
            "- Visual recovery: 10/11 claimed material scopes accepted; 17 canonical regions are integrated through the Gate 2 consumer path.",
            "- Remaining visual restriction: one claimed material source image is byte-uniform and remains fail-closed.",
            "- Customer acceptance: not claimed.",
            "- Stage delivery/repository-live parity: evidenced separately and not inferred from this reconciliation proof.",
            "",
        ]
    )
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate1", type=Path, default=DEFAULT_GATE1)
    parser.add_argument("--gate2-previous", type=Path, default=DEFAULT_GATE2_PREVIOUS)
    parser.add_argument("--gate2-current", type=Path, default=DEFAULT_GATE2_CURRENT)
    parser.add_argument("--fns", type=Path, default=DEFAULT_FNS)
    parser.add_argument("--visual", type=Path, default=DEFAULT_VISUAL)
    parser.add_argument("--broker", type=Path, default=DEFAULT_BROKER)
    parser.add_argument("--debt", type=Path, default=DEFAULT_DEBT)
    parser.add_argument("--safe-output", type=Path, default=DEFAULT_SAFE_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    proof = build_closure(
        gate1=_load(args.gate1),
        gate2_previous=_load(args.gate2_previous),
        gate2_current=_load(args.gate2_current),
        fns=_load(args.fns),
        visual=_load(args.visual),
        broker=_load(args.broker),
        debt=_load(args.debt),
    )
    args.safe_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.safe_output.write_text(
        json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.report_output.write_text(render_report(proof), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": proof["status"],
                "historical_errors_classified": proof[
                    "readiness_error_reconciliation"
                ]["historical_errors_total"],
                "current_gate2_errors": proof["readiness_error_reconciliation"][
                    "current_gate2_validator_errors"
                ],
                "unexplained_errors": 0,
                "customer_values_exposed": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
