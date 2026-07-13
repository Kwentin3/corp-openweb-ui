#!/usr/bin/env python3
"""Run the Goal 3 hybrid context and structural reliability proof."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    FileInput,
    Gate1Normalizer,
    persist_gate1_result,
)
from broker_reports_gate1.artifact_models import RetentionPolicy  # noqa: E402
from broker_reports_gate1.pdf_hybrid_provider import (  # noqa: E402
    PdfHybridProviderConfig,
    PdfHybridProviderFactory,
)
from broker_reports_gate1.pdf_hybrid_reliability_shadow import (  # noqa: E402
    PdfHybridReliabilityShadowConfig,
    PdfHybridReliabilityShadowFactory,
)
from broker_reports_gate1.pdf_hybrid_structure import (  # noqa: E402
    PDF_HYBRID_CONTINUATION_SCHEMA,
)
from local_pdf_hybrid_goal2_proof import (  # noqa: E402
    _aggregate_scores,
    _counts,
    _deterministic_control_repeat,
    _failed_scheduled_score,
    _git_revision,
    _openwebui_request,
    _score,
    _table_reference_map,
)


SAFE_SCHEMA = "broker_reports_pdf_hybrid_reliability_controlled_proof_v2"
TARGET_KEYS = ("1:3", "3:2", "4:1", "4:2", "5:3")
STRUCTURAL_SIGNALS = {
    "1:3": {"multi_row_or_merged_header": True, "header_depth": 3},
    "3:2": {"multi_row_or_merged_header": True, "header_depth": 2},
    "4:1": {"continuation_signal": True, "header_depth": 0},
    "4:2": {"multi_row_or_merged_header": True, "header_depth": 3},
    "5:3": {"multi_row_or_merged_header": True, "header_depth": 2},
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--goal2-baseline")
    parser.add_argument("--skip-provider", action="store_true")
    parser.add_argument("--model-id", default="models/gemini-3.5-flash")
    args = parser.parse_args()

    pdf_path = Path(args.pdf).resolve()
    reference_path = Path(args.reference).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_bytes = pdf_path.read_bytes()
    pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    reference_tables = {
        str(item.get("table_key") or ""): item
        for item in reference.get("tables") or []
        if isinstance(item, dict)
    }
    file_input = FileInput.from_bytes(
        private_ref=f"controlled-private-pdf:{pdf_sha256}",
        filename="controlled.pdf",
        content=pdf_bytes,
        mime_type=mimetypes.guess_type("controlled.pdf")[0] or "application/pdf",
        source_kind="local_private_test",
    )
    result = Gate1Normalizer().normalize(
        [file_input],
        entrypoint="local_pdf_hybrid_reliability_proof",
        trigger_type="controlled_private_proof",
        input_context={
            "pdf_layout_slice2_enabled": True,
            "pdf_compact_canonical_dual_write": True,
            "pdf_hybrid_shadow_enabled": False,
            "pdf_hybrid_reliability_shadow_enabled": True,
        },
    )
    run_id = result.package["normalization_run"]["run_id"]
    context = ArtifactAccessContext(
        user_id="controlled-proof-user",
        case_id="controlled-proof-case",
        chat_id="controlled-proof-chat",
        workspace_model_id="broker-reports-gate1",
        normalization_run_id=run_id,
        allow_private=True,
    )
    retention = RetentionPolicy(
        mode="synthetic_dev",
        ttl_seconds=None,
        expires_at=None,
        explicit=True,
    )
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=output_dir / "artifacts.sqlite3",
            payload_root=output_dir / "payloads",
        )
    ).create()
    gate1_manifest = persist_gate1_result(
        store=store,
        result=result,
        context=context,
        retention_policy=retention,
        source_file_refs=[
            {
                "provider": "controlled_private_registry",
                "file_hash_sha256": pdf_sha256,
                "content_type": "application/pdf",
                "size_bytes": len(pdf_bytes),
            }
        ],
    )
    source_payload = (result.package.get("private_normalized_source_payloads") or [])[0]
    table_map = _table_reference_map(source_payload, reference_tables)
    ref_by_key = {table_key: table_ref for table_ref, table_key in table_map.items()}
    missing = sorted(set(TARGET_KEYS) - set(ref_by_key))
    if missing:
        raise RuntimeError(f"controlled_table_mapping_missing:{','.join(missing)}")
    signal_overrides = {
        table_ref: STRUCTURAL_SIGNALS[table_key]
        for table_ref, table_key in table_map.items()
        if table_key in TARGET_KEYS
    }
    continuation_contract = {
        "schema_version": PDF_HYBRID_CONTINUATION_SCHEMA,
        "continuation_group_id": "controlled_trade_table_pages_3_4",
        "shared_column_count": 16,
        "fragments": [
            {
                "fragment_order": 1,
                "page_number": 3,
                "table_ref": ref_by_key["3:2"],
                "repeated_header_policy": "source_header",
            },
            {
                "fragment_order": 2,
                "page_number": 4,
                "table_ref": ref_by_key["4:1"],
                "repeated_header_policy": "no_repeated_header",
            },
        ],
        "subtotal_policy": "preserve_fragment_subtotals",
        "duplicate_row_policy": "allow_explicit_repeated_header_only",
        "fragment_coverage_required": True,
        "joined_coverage_required": True,
        "authoritative": False,
    }

    provider = None
    qualification: dict[str, Any]
    if args.skip_provider:
        qualification = {"status": "skipped"}
    else:
        try:
            provider = PdfHybridProviderFactory(
                PdfHybridProviderConfig(
                    model_id=args.model_id,
                    maximum_output_tokens=8_192,
                )
            ).create_for_openwebui(_openwebui_request(Path(args.env_file)))
            qualification = provider.qualify()
            if qualification.get("status") != "qualified":
                provider = None
        except Exception as exc:
            qualification = {
                "status": "blocked",
                "failure_class": type(exc).__name__,
            }
            provider = None

    runtime = PdfHybridReliabilityShadowFactory(
        PdfHybridReliabilityShadowConfig(
            enabled=True,
            table_allowlist=tuple(ref_by_key[key] for key in TARGET_KEYS),
        )
    ).create(provider=provider)
    shadow = runtime.run(
        store=store,
        package=result.package,
        context=context,
        retention_policy=retention,
        pdf_bytes_by_sha256={pdf_sha256: pdf_bytes},
        signal_overrides_by_table=signal_overrides,
        continuation_contracts=[continuation_contract],
        dpi_escalation_reasons_by_table={
            ref_by_key["4:1"]: "pdf_hybrid_continuation_structure_sensitivity_check"
        },
    )
    arbitration_by_ref = {
        str(item.get("table_ref") or ""): item for item in shadow.get("arbitrations") or []
    }
    states = shadow.get("states") or {}
    table_results = []
    materialized_scores = []
    accepted_scores = []
    scheduled_scores = []
    for key in TARGET_KEYS:
        table_ref = ref_by_key[key]
        state = states[table_ref]
        primary = state.get("primary") if isinstance(state.get("primary"), dict) else {}
        materialization = (
            primary.get("materialization")
            if isinstance(primary.get("materialization"), dict)
            else None
        )
        arbitration = arbitration_by_ref.get(table_ref, {})
        score = _score(reference_tables[key], materialization) if materialization else None
        if score:
            materialized_scores.append(score)
        if score and arbitration.get("terminal_status") == "accepted_shadow":
            accepted_scores.append(score)
            scheduled_scores.append(score)
        else:
            scheduled_scores.append(_failed_scheduled_score(reference_tables[key]))
        packages = primary.get("packages") or []
        calibrations = primary.get("calibrations") or []
        structural = primary.get("structural_validation") or {}
        repeatability = state.get("repeatability") or {}
        table_results.append(
            {
                "table_key": key,
                "table_ref": table_ref,
                "terminal_status": arbitration.get("terminal_status"),
                "reason_codes": arbitration.get("reason_codes"),
                "primary_reason_codes": primary.get("reason_codes"),
                "source_rows": state.get("compact_ledger", {}).get("row_count"),
                "source_columns": state.get("compact_ledger", {}).get("column_count"),
                "logical_candidates": state.get("window_plan", {}).get("candidate_count"),
                "window_count": len(state.get("window_plan", {}).get("windows") or []),
                "maximum_window_candidates": max(
                    (
                        int(item.get("component_accounting", {}).get("candidate_count") or 0)
                        for item in packages
                    ),
                    default=0,
                ),
                "maximum_window_model_text_bytes": max(
                    (
                        int(
                            item.get("component_accounting", {}).get(
                                "model_facing_text_bytes"
                            )
                            or 0
                        )
                        for item in packages
                    ),
                    default=0,
                ),
                "maximum_provider_counted_input_tokens": max(
                    (int(item.get("provider_counted_input_tokens") or 0) for item in calibrations),
                    default=0,
                ),
                "maximum_provider_actual_input_tokens": max(
                    (int(item.get("provider_actual_input_tokens") or 0) for item in calibrations),
                    default=0,
                ),
                "maximum_calibration_error_ratio": max(
                    (float(item.get("counted_to_actual_error_ratio") or 0) for item in calibrations),
                    default=0,
                ),
                "structural_placement_passed": structural.get("passed"),
                "full_grid_validation": primary.get("full_grid_validation", {}).get(
                    "aggregate_result"
                ),
                "selected_candidates": len(
                    materialization.get("selected_candidate_ids") or []
                )
                if materialization
                else 0,
                "omitted_candidates": len(materialization.get("omitted_candidate_ids") or [])
                if materialization
                else 0,
                "model_invented_values_total": materialization.get(
                    "model_invented_values_total"
                )
                if materialization
                else None,
                "repeatability_required": repeatability.get("required"),
                "repeatability_passed": repeatability.get("passed"),
                "repeatability_ever_conflicted": repeatability.get("ever_conflicted"),
                "placement_checksum": materialization.get("placement_checksum")
                if materialization
                else None,
                "repeat_placement_checksum": repeatability.get(
                    "repeat_placement_checksum"
                ),
                "score": score,
            }
        )

    records = store.list_by_run(run_id)
    baseline = None
    if args.goal2_baseline:
        baseline = json.loads(Path(args.goal2_baseline).read_text(encoding="utf-8"))
    deterministic_repeat = _deterministic_control_repeat(
        pdf_bytes=pdf_bytes,
        pdf_sha256=pdf_sha256,
        primary_package=result.package,
        decisions=[
            {
                "hybrid_status": "deterministic_control_no_vlm",
                "table_ref": next(
                    (
                        item.get("table_ref")
                        for item in result.package.get("private_normalized_table_projections") or []
                        if item.get("projection_status") == "ready"
                    ),
                    None,
                ),
            }
        ],
    )
    safe = {
        "schema_version": SAFE_SCHEMA,
        "source_revision": _git_revision(),
        "pdf_sha256": pdf_sha256,
        "normalization_run_id": run_id,
        "provider_qualification": qualification,
        "terminal_outcomes": shadow.get("summary", {}).get("terminal_outcomes"),
        "tables": table_results,
        "scheduled_score": _aggregate_scores(
            scheduled_scores,
            scheduled_total=len(TARGET_KEYS),
            accepted_scored_tables=len(accepted_scores),
        ),
        "accepted_only_score": _aggregate_scores(
            accepted_scores,
            scheduled_total=len(accepted_scores),
            accepted_scored_tables=len(accepted_scores),
        ),
        "materialized_diagnostic_score": _aggregate_scores(
            materialized_scores,
            scheduled_total=len(materialized_scores),
            accepted_scored_tables=len(materialized_scores),
        ),
        "context_summary": shadow.get("summary", {}).get("context"),
        "before_after": _before_after(baseline, table_results),
        "repeatability": {
            "deterministic_control": deterministic_repeat,
            "ledger_records": len(
                shadow.get("repeatability_ledger", {}).get("records") or []
            ),
            "conflicted_tasks": len(
                shadow.get("repeatability_ledger", {}).get("conflicted_task_keys")
                or []
            ),
            "later_agreement_can_clear_conflict": False,
        },
        "goal1": {
            "accepted_tables": sum(
                item.get("projection_status") == "ready"
                for item in result.package.get("private_normalized_table_projections") or []
            ),
            "blocked_tables": sum(
                item.get("projection_status") != "ready"
                for item in result.package.get("private_normalized_table_projections") or []
            ),
            "compact_artifacts": sum(
                record.artifact_type == "broker_reports_pdf_compact_canonical_document_v1"
                for record in records
            ),
            "production_gate2_selection_changed": False,
        },
        "artifact_counts": _counts(record.artifact_type for record in records),
        "reference_status": reference.get("human_review_status"),
        "reference_is_provisional": True,
        "gate1_manifest_ref_present": bool(gate1_manifest.gate2_handoff_ref),
        "authority_state": "non_authoritative",
        "production_ready": False,
        "production_gate2_selection_changed": False,
        "private_shadow_artifacts_only": True,
        "knowledge_rag_used": False,
        "vectorization_performed": False,
        "ocr_used": False,
        "customer_values_included": False,
        "crop_bytes_included": False,
        "raw_provider_response_included": False,
        "private_paths_included": False,
    }
    (output_dir / "evidence.safe.json").write_text(
        json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _before_after(
    baseline: dict[str, Any] | None,
    tables: list[dict[str, Any]],
) -> dict[str, Any]:
    before_by_key = {
        str(item.get("table_key") or ""): item
        for item in (baseline or {}).get("tables") or []
        if isinstance(item, dict)
    }
    rows = []
    for table in tables:
        before = before_by_key.get(table["table_key"], {})
        context = before.get("context") if isinstance(before.get("context"), dict) else {}
        rows.append(
            {
                "table_key": table["table_key"],
                "before_candidate_count": context.get("candidate_count"),
                "after_maximum_window_candidates": table.get(
                    "maximum_window_candidates"
                ),
                "before_model_facing_text_bytes": context.get(
                    "model_facing_text_bytes"
                ),
                "after_maximum_window_model_text_bytes": table.get(
                    "maximum_window_model_text_bytes"
                ),
                "before_provider_input_tokens": next(
                    (
                        item.get("input_tokens")
                        for item in (baseline or {}).get("provider_attempts") or []
                        if item.get("table_key") == table["table_key"]
                        and not item.get("repeatability_probe")
                    ),
                    None,
                ),
                "after_maximum_provider_actual_input_tokens": table.get(
                    "maximum_provider_actual_input_tokens"
                ),
                "source_candidates_preserved": table.get("logical_candidates"),
                "omitted_candidates": table.get("omitted_candidates"),
            }
        )
    return {"baseline_available": baseline is not None, "tables": rows}


if __name__ == "__main__":
    raise SystemExit(main())
