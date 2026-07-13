#!/usr/bin/env python3
"""Compare current candidate JSON with free CSV and candidate CSV on real tables."""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import mimetypes
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import FileInput, Gate1Normalizer  # noqa: E402
from broker_reports_gate1.artifact_store import (  # noqa: E402
    ArtifactStoreConfig,
    ArtifactStoreFactory,
)
from broker_reports_gate1.pdf_csv_experiment import (  # noqa: E402
    PDF_CSV_EXPERIMENT_VERSION,
    PDF_CSV_TOPOLOGY_SCHEMA,
    PdfCsvExperimentError,
    PdfCsvExperimentFactory,
    hash_text,
)
from broker_reports_gate1.pdf_csv_experiment_provider import (  # noqa: E402
    PdfCsvExperimentProviderFactory,
    PdfCsvProviderConfig,
    PdfCsvProviderError,
)
from broker_reports_gate1.pdf_hybrid_budget import PdfHybridBudgetFactory  # noqa: E402
from broker_reports_gate1.pdf_hybrid_compaction import (  # noqa: E402
    PdfHybridCompactionFactory,
)
from broker_reports_gate1.pdf_hybrid_contracts import (  # noqa: E402
    canonical_json_bytes,
    sha256_json,
)
from broker_reports_gate1.pdf_hybrid_materialization import (  # noqa: E402
    PdfHybridMaterializationFactory,
)
from broker_reports_gate1.pdf_hybrid_provider import (  # noqa: E402
    PdfHybridProviderConfig,
    PdfHybridProviderFactory,
)
from broker_reports_gate1.pdf_hybrid_structure import (  # noqa: E402
    PDF_HYBRID_CONTINUATION_SCHEMA,
    PdfHybridStructureFactory,
)
from broker_reports_gate1.pdf_hybrid_windows import (  # noqa: E402
    PdfHybridWindowFactory,
)
from broker_reports_gate1.pdf_table_classification import (  # noqa: E402
    PdfTableClassifierConfig,
    PdfTableClassifierFactory,
)
from broker_reports_gate1.pdf_table_raster import PdfTableRasterFactory  # noqa: E402
from broker_reports_gate1.pdf_table_validation import (  # noqa: E402
    PdfTableValidationFactory,
)
SAFE_SCHEMA = "broker_reports_real_table_csv_vs_json_experiment_safe_v1"
PRIVATE_SCHEMA = "broker_reports_real_table_csv_vs_json_experiment_private_v1"
TARGET_KEYS = ("1:2", "1:3", "3:2", "4:1", "4:2", "5:3")
REPEAT_KEYS = {"1:2", "1:3", "3:2", "4:1", "4:2"}
JSON_LIVE3_KEYS = {"1:3", "3:2", "4:1", "4:2", "5:3"}
STRUCTURAL_SIGNALS = {
    "1:2": {"header_depth": 2},
    "1:3": {"multi_row_or_merged_header": True, "header_depth": 3},
    "3:2": {"multi_row_or_merged_header": True, "header_depth": 2},
    "4:1": {"continuation_signal": True, "header_depth": 0},
    "4:2": {"multi_row_or_merged_header": True, "header_depth": 3},
    "5:3": {"multi_row_or_merged_header": True, "header_depth": 2},
}
CONTINUATION_GROUP_ID = "controlled_trade_table_pages_3_4"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--json-control-dir", required=True)
    parser.add_argument("--model-id", default="models/gemini-3.5-flash")
    parser.add_argument("--skip-provider", action="store_true")
    parser.add_argument("--resume-journal-only", action="store_true")
    args = parser.parse_args()
    if args.skip_provider and args.resume_journal_only:
        parser.error("--skip-provider and --resume-journal-only are mutually exclusive")

    pdf_path = Path(args.pdf).resolve()
    reference_path = Path(args.reference).resolve()
    output_dir = Path(args.output_dir).resolve()
    private_dir = output_dir / "private"
    private_dir.mkdir(parents=True, exist_ok=True)
    pdf_bytes = pdf_path.read_bytes()
    pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    reference_tables = {
        str(item.get("table_key") or ""): item
        for item in reference.get("tables") or []
        if isinstance(item, dict)
    }
    missing_reference = sorted(set(TARGET_KEYS) - set(reference_tables))
    if missing_reference:
        raise RuntimeError(
            "csv_experiment_reference_missing:" + ",".join(missing_reference)
        )

    result = Gate1Normalizer().normalize(
        [
            FileInput.from_bytes(
                private_ref=f"controlled-private-pdf:{pdf_sha256}",
                filename="controlled.pdf",
                content=pdf_bytes,
                mime_type=mimetypes.guess_type("controlled.pdf")[0]
                or "application/pdf",
                source_kind="local_private_test",
            )
        ],
        entrypoint="local_pdf_csv_vs_json_experiment",
        trigger_type="controlled_private_research",
        input_context={
            "pdf_layout_slice2_enabled": True,
            "pdf_compact_canonical_dual_write": False,
            "pdf_hybrid_shadow_enabled": False,
            "pdf_hybrid_reliability_shadow_enabled": False,
        },
    )
    states, continuation_contract = _build_states(
        result.package,
        pdf_bytes=pdf_bytes,
        pdf_sha256=pdf_sha256,
        reference_tables=reference_tables,
    )
    csv_runtime = PdfCsvExperimentFactory().create()
    jobs = _build_csv_jobs(states, csv_runtime, args.model_id)
    journal_path = private_dir / "journal.private.json"
    journal = _read_list(journal_path)
    qualification: dict[str, Any]
    csv_provider = None
    json_provider = None
    if args.resume_journal_only:
        existing_safe_path = output_dir / "experiment.safe.json"
        if not existing_safe_path.is_file():
            raise RuntimeError("csv_experiment_resume_safe_missing")
        existing_safe = json.loads(existing_safe_path.read_text(encoding="utf-8"))
        recorded_qualification = existing_safe.get("provider_qualification") or {}
        if recorded_qualification.get("status") != "qualified":
            raise RuntimeError("csv_experiment_resume_qualification_missing")
        expected_csv_jobs = {job["job_key"] for job in jobs}
        recorded_csv_jobs = {
            str((item.get("safe") or {}).get("job_key") or "")
            for item in journal
            if (item.get("safe") or {}).get("arm")
            in {"free_csv", "candidate_csv", "candidate_csv_topology"}
        }
        json_simple_attempts = {
            int((item.get("safe") or {}).get("attempt_number") or 0)
            for item in journal
            if (item.get("safe") or {}).get("arm")
            == "candidate_json_control_simple"
        }
        if recorded_csv_jobs != expected_csv_jobs or json_simple_attempts != {1, 2}:
            raise RuntimeError("csv_experiment_resume_journal_incomplete")
        qualification = copy.deepcopy(recorded_qualification)
        qualification["evidence_resume"] = "journal_only_no_provider_calls"
    elif args.skip_provider:
        qualification = {"status": "skipped"}
    else:
        request = _openwebui_request(Path(args.env_file))
        csv_provider = PdfCsvExperimentProviderFactory(
            PdfCsvProviderConfig(model_id=args.model_id)
        ).create_for_openwebui(request)
        json_provider = PdfHybridProviderFactory(
            PdfHybridProviderConfig(
                model_id=args.model_id,
                maximum_output_tokens=8192,
            )
        ).create_for_openwebui(request)
        qualification = csv_provider.qualify()
        if qualification.get("status") != "qualified":
            raise RuntimeError("csv_experiment_provider_not_qualified")

    journal = _run_csv_jobs(
        jobs=jobs,
        journal=journal,
        journal_path=journal_path,
        provider=csv_provider,
        runtime=csv_runtime,
    )
    journal = _run_json_simple_jobs(
        state=states["1:2"],
        journal=journal,
        journal_path=journal_path,
        provider=json_provider,
    )
    journal = _revalidate_journal(journal, jobs, states, csv_runtime)
    _write_json(journal_path, journal)

    free_outcomes = _free_outcomes(states, journal, csv_runtime)
    candidate_outcomes = _candidate_outcomes(
        arm="candidate_csv",
        states=states,
        journal=journal,
        runtime=csv_runtime,
    )
    topology_outcomes = _candidate_outcomes(
        arm="candidate_csv_topology",
        states=states,
        journal=journal,
        runtime=csv_runtime,
    )
    json_control = _load_json_control(
        Path(args.json_control_dir).resolve(),
        states=states,
        journal=journal,
    )
    comparisons = _cross_arm_comparisons(
        states=states,
        free_outcomes=free_outcomes,
        candidate_outcomes=candidate_outcomes,
        topology_outcomes=topology_outcomes,
        runtime=csv_runtime,
    )
    continuation = {
        "free_csv": _free_continuation(free_outcomes),
        "candidate_csv": _candidate_continuation(
            candidate_outcomes, continuation_contract
        ),
        "candidate_csv_topology": _candidate_continuation(
            topology_outcomes, continuation_contract
        ),
    }
    repeatability = {
        "json_control": _json_repeatability(json_control),
        "free_csv": _repeatability("free_csv", free_outcomes, journal),
        "candidate_csv": _repeatability(
            "candidate_csv", candidate_outcomes, journal
        ),
        "candidate_csv_topology": _repeatability(
            "candidate_csv_topology", topology_outcomes, journal
        ),
        "later_matching_answer_can_clear_conflict": False,
    }
    arms = {
        "candidate_json_control": json_control,
        "free_csv": _arm_summary(free_outcomes, states),
        "candidate_csv": _arm_summary(candidate_outcomes, states),
        "candidate_csv_topology": _arm_summary(topology_outcomes, states),
    }
    safe = {
        "schema_version": SAFE_SCHEMA,
        "experiment_version": PDF_CSV_EXPERIMENT_VERSION,
        "source_revision": _git_revision(),
        "pdf_sha256": pdf_sha256,
        "reference_status": reference.get("human_review_status"),
        "reference_is_provisional": True,
        "provider_qualification": qualification,
        "csv_dialect": csv_runtime.dialect_contract(),
        "topology_sidecar": {
            "schema_version": PDF_CSV_TOPOLOGY_SCHEMA,
            "maximum_bytes": csv_runtime.config.maximum_topology_bytes,
            "full_grid_repetition_forbidden": True,
            "candidate_dictionary_repetition_forbidden": True,
            "independent_parser_coordinate_validation_required": True,
        },
        "corpus": [
            {
                "table_key": key,
                "structural_case": _structural_case(key),
                "reference_rows": len(reference_tables[key].get("cells") or []),
                "reference_columns": max(
                    (len(row) for row in reference_tables[key].get("cells") or []),
                    default=0,
                ),
                "parser_rows": states[key]["ledger"].get("row_count"),
                "parser_columns": states[key]["ledger"].get("column_count"),
                "candidate_count": len(states[key]["ledger"].get("candidate_order") or []),
                "window_count": len(states[key]["packages"]),
                "deterministic_projection_status": states[key]["deterministic"].get(
                    "projection_status"
                ),
            }
            for key in TARGET_KEYS
        ],
        "arms": arms,
        "cross_arm_comparisons": comparisons,
        "continuation": continuation,
        "repeatability": repeatability,
        "job_accounting": {
            "jobs_expected": len(jobs) + 2,
            "jobs_terminal": len(
                [
                    item
                    for item in journal
                    if (item.get("safe") or {}).get("arm")
                    in {
                        "free_csv",
                        "candidate_csv",
                        "candidate_csv_topology",
                        "candidate_json_control_simple",
                    }
                ]
            ),
            "csv_provider_attempts": len(
                [
                    item
                    for item in journal
                    if (item.get("safe") or {}).get("arm")
                    in {"free_csv", "candidate_csv", "candidate_csv_topology"}
                ]
            ),
            "hidden_retries": 0,
            "provider_failovers": 0,
        },
        "hard_invariants": {
            "production_pdf_pipeline_changed": False,
            "production_gate2_selection_changed": False,
            "existing_validators_weakened": False,
            "free_csv_authoritative": False,
            "candidate_csv_free_values_allowed": False,
            "whole_pdf_provider_transport_used": False,
            "ocr_used": False,
            "knowledge_rag_vector_used": False,
            "openwebui_core_patched": False,
            "raw_customer_values_in_safe_output": False,
            "raw_crops_in_safe_output": False,
        },
    }
    private_result = {
        "schema_version": PRIVATE_SCHEMA,
        "pdf_path": str(pdf_path),
        "reference_path": str(reference_path),
        "journal": journal,
    }
    _write_json(private_dir / "experiment.private.json", private_result)
    _write_json(output_dir / "experiment.safe.json", safe)
    print(json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _build_states(
    package: dict[str, Any],
    *,
    pdf_bytes: bytes,
    pdf_sha256: str,
    reference_tables: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    source_payload = next(
        item
        for item in package.get("private_normalized_source_payloads") or []
        if isinstance(item, dict)
    )
    document_ref = str(source_payload.get("document_ref") or "")
    projection = source_payload.get("pdf_text_layer_projection") or {}
    table_map = _table_reference_map(source_payload, reference_tables)
    refs_by_key = {key: ref for ref, key in table_map.items()}
    missing = sorted(set(TARGET_KEYS) - set(refs_by_key))
    if missing:
        raise RuntimeError("csv_experiment_table_mapping_missing:" + ",".join(missing))
    candidates = {
        str(item.get("table_candidate_ref") or ""): item
        for item in projection.get("table_candidate_inventory") or []
        if isinstance(item, dict)
    }
    pages = {
        str(item.get("page_ref") or ""): int(item.get("page_number") or 0)
        for item in projection.get("page_inventory") or []
        if isinstance(item, dict)
    }
    bboxes = {
        str(item.get("bbox_ref") or ""): list(item.get("bbox") or [])
        for item in projection.get("bbox_inventory") or []
        if isinstance(item, dict)
    }
    deterministic = {
        str(item.get("table_ref") or ""): item
        for item in package.get("private_normalized_table_projections") or []
        if isinstance(item, dict)
    }
    compactor = PdfHybridCompactionFactory().create()
    budget = PdfHybridBudgetFactory().create()
    windows = PdfHybridWindowFactory().create(budget=budget)
    raster = PdfTableRasterFactory().create()
    classifier = PdfTableClassifierFactory(
        PdfTableClassifierConfig(
            shadow_allowlist=tuple(refs_by_key[key] for key in TARGET_KEYS)
        )
    ).create()
    states: dict[str, dict[str, Any]] = {}
    for key in TARGET_KEYS:
        table_ref = refs_by_key[key]
        candidate = candidates[table_ref]
        page_ref = str(candidate.get("page_ref") or "")
        page_number = pages[page_ref]
        table_bbox = bboxes[str(candidate.get("bbox_ref") or "")]
        classification = classifier.classify(
            document_ref=document_ref,
            document_checksum=pdf_sha256,
            page_ref=page_ref,
            page_number=page_number,
            table_candidate=candidate,
            deterministic_projection=deterministic.get(table_ref, {}),
            signals=STRUCTURAL_SIGNALS[key],
        )
        ledger = compactor.compact(
            document_ref=document_ref,
            pdf_sha256=pdf_sha256,
            page_ref=page_ref,
            page_number=page_number,
            table_candidate=candidate,
            pdf_text_layer_projection=projection,
            header_depth=int(STRUCTURAL_SIGNALS[key].get("header_depth") or 0),
        )
        plan = windows.plan(compact_ledger=ledger)
        full_render = raster.render(
            pdf_bytes=pdf_bytes,
            pdf_sha256=pdf_sha256,
            document_ref=document_ref,
            page_number=page_number,
            table_ref=table_ref,
            table_bbox=table_bbox,
            dpi=150,
        )
        packages = []
        png_by_package = {}
        for window in plan.get("windows") or []:
            rendered = raster.render(
                pdf_bytes=pdf_bytes,
                pdf_sha256=pdf_sha256,
                document_ref=document_ref,
                page_number=page_number,
                table_ref=table_ref,
                table_bbox=list(window.get("crop_bbox") or []),
                dpi=150,
            )
            evidence = windows.build_package(
                compact_ledger=ledger,
                plan=plan,
                window=window,
                crop_manifest=rendered["manifest"],
                private_crop_artifact_ref=(
                    "research-private-crop:" + rendered["manifest"]["png_sha256"]
                ),
            )
            packages.append(evidence)
            png_by_package[evidence["package_id"]] = base64.b64decode(
                rendered["private_png_base64"]
            )
        states[key] = {
            "table_key": key,
            "table_ref": table_ref,
            "reference": reference_tables[key],
            "deterministic": deterministic.get(table_ref, {}),
            "classification": classification,
            "ledger": ledger,
            "plan": plan,
            "packages": packages,
            "png_by_package": png_by_package,
            "full_crop_manifest": full_render["manifest"],
            "full_crop_png": base64.b64decode(full_render["private_png_base64"]),
            "windows_runtime": windows,
        }
    continuation = {
        "schema_version": PDF_HYBRID_CONTINUATION_SCHEMA,
        "continuation_group_id": CONTINUATION_GROUP_ID,
        "shared_column_count": 16,
        "fragments": [
            {
                "fragment_order": 1,
                "page_number": 3,
                "table_ref": states["3:2"]["table_ref"],
                "repeated_header_policy": "source_header",
            },
            {
                "fragment_order": 2,
                "page_number": 4,
                "table_ref": states["4:1"]["table_ref"],
                "repeated_header_policy": "no_repeated_header",
            },
        ],
        "subtotal_policy": "preserve_fragment_subtotals",
        "duplicate_row_policy": "allow_explicit_repeated_header_only",
        "fragment_coverage_required": True,
        "joined_coverage_required": True,
        "authoritative": False,
    }
    return states, continuation


def _build_csv_jobs(
    states: dict[str, dict[str, Any]], runtime: Any, model_id: str
) -> list[dict[str, Any]]:
    jobs = []
    for key in TARGET_KEYS:
        state = states[key]
        attempts = (1, 2) if key in REPEAT_KEYS else (1,)
        parser_grid = runtime.parser_grid(state["ledger"])
        parser_shape = (
            len(parser_grid),
            max((len(row) for row in parser_grid), default=0),
        )
        free_prompt = runtime.free_csv_prompt(table_identity=f"table-{key}")
        for attempt in attempts:
            jobs.append(
                _job(
                    arm="free_csv",
                    table_key=key,
                    package_id="full-table-crop",
                    prompt=free_prompt,
                    png=state["full_crop_png"],
                    crop_manifest=state["full_crop_manifest"],
                    attempt=attempt,
                    model_id=model_id,
                    package=None,
                    continuation=None,
                    expected_shape=parser_shape,
                )
            )
        for package in state["packages"]:
            continuation = _continuation_identity(key)
            for arm, with_topology in (
                ("candidate_csv", False),
                ("candidate_csv_topology", True),
            ):
                prompt = runtime.candidate_csv_prompt(
                    evidence_package=package,
                    topology_sidecar=with_topology,
                    continuation=continuation,
                )
                for attempt in attempts:
                    jobs.append(
                        _job(
                            arm=arm,
                            table_key=key,
                            package_id=package["package_id"],
                            prompt=prompt,
                            png=state["png_by_package"][package["package_id"]],
                            crop_manifest=package["crop_identity"],
                            attempt=attempt,
                            model_id=model_id,
                            package=package,
                            continuation=continuation,
                            expected_shape=None,
                        )
                    )
    return sorted(
        jobs,
        key=lambda item: (
            item["arm"],
            TARGET_KEYS.index(item["table_key"]),
            item["package_id"],
            item["attempt_number"],
        ),
    )


def _job(
    *,
    arm: str,
    table_key: str,
    package_id: str,
    prompt: str,
    png: bytes,
    crop_manifest: dict[str, Any],
    attempt: int,
    model_id: str,
    package: dict[str, Any] | None,
    continuation: list[Any] | None,
    expected_shape: tuple[int, int] | None,
) -> dict[str, Any]:
    crop_sha256 = str(
        crop_manifest.get("crop_sha256") or crop_manifest.get("png_sha256") or ""
    )
    task_id = "pdfcsvtask_" + hashlib.sha256(
        canonical_json_bytes(
            {
                "arm": arm,
                "table_key": table_key,
                "package_id": package_id,
                "prompt_hash": hash_text(prompt),
                "crop_sha256": crop_sha256,
                "model_id": model_id,
            }
        )
    ).hexdigest()[:24]
    return {
        "job_key": f"{task_id}:a{attempt}",
        "task_id": task_id,
        "arm": arm,
        "table_key": table_key,
        "package_id": package_id,
        "prompt": prompt,
        "png": png,
        "crop_sha256": crop_sha256,
        "crop_manifest": crop_manifest,
        "attempt_number": attempt,
        "package": package,
        "continuation": continuation,
        "expected_shape": list(expected_shape) if expected_shape else None,
    }


def _run_csv_jobs(
    *,
    jobs: list[dict[str, Any]],
    journal: list[dict[str, Any]],
    journal_path: Path,
    provider: Any,
    runtime: Any,
) -> list[dict[str, Any]]:
    completed = {
        str((item.get("safe") or {}).get("job_key") or "") for item in journal
    }
    for job in jobs:
        if job["job_key"] in completed:
            continue
        if provider is None:
            outcome = _provider_skipped(job)
        else:
            lineage = [
                str((item.get("safe") or {}).get("attempt_id") or "")
                for item in journal
                if (item.get("safe") or {}).get("task_id") == job["task_id"]
                and int((item.get("safe") or {}).get("attempt_number") or 0)
                < job["attempt_number"]
            ]
            try:
                counted = provider.count_tokens(
                    prompt=job["prompt"],
                    png_bytes=job["png"],
                    crop_sha256=job["crop_sha256"],
                )
                provider_result = provider.invoke(
                    task_id=job["task_id"],
                    prompt=job["prompt"],
                    png_bytes=job["png"],
                    crop_sha256=job["crop_sha256"],
                    attempt_number=job["attempt_number"],
                    attempt_lineage=lineage,
                )
                outcome = _parse_csv_provider_result(job, counted, provider_result, runtime)
            except (PdfCsvProviderError, PdfCsvExperimentError) as exc:
                outcome = _failed_job(job, getattr(exc, "code", type(exc).__name__))
        journal.append(outcome)
        journal.sort(key=lambda item: str((item.get("safe") or {}).get("job_key") or ""))
        _write_json(journal_path, journal)
        completed.add(job["job_key"])
    return journal


def _parse_csv_provider_result(
    job: dict[str, Any], counted: dict[str, Any], result: dict[str, Any], runtime: Any
) -> dict[str, Any]:
    attempt = result["attempt"]
    text = result.get("text")
    parsed = None
    topology = None
    binding = None
    parse_error = None
    if attempt.get("terminal_failure_class") is None and isinstance(text, str):
        try:
            if job["arm"] == "free_csv":
                state_rows, state_columns = _expected_free_shape(job)
                parsed = runtime.parse_free_csv(
                    text,
                    expected_rows=state_rows,
                    expected_columns=state_columns,
                )
            else:
                package = job["package"]
                window = package.get("window") or {}
                candidate_ids = list(window.get("candidate_ids") or [])
                if job["arm"] == "candidate_csv":
                    parsed = runtime.parse_candidate_csv(
                        text,
                        expected_rows=int(window.get("row_count") or 0),
                        expected_columns=int(window.get("column_count") or 0),
                        candidate_ids=candidate_ids,
                    )
                else:
                    parsed, topology = runtime.parse_candidate_topology_envelope(
                        text,
                        expected_rows=int(window.get("row_count") or 0),
                        expected_columns=int(window.get("column_count") or 0),
                        candidate_ids=candidate_ids,
                        expected_continuation=job["continuation"],
                    )
                binding = runtime.binding_from_csv(
                    evidence_package=package,
                    parsed=parsed,
                    topology=topology,
                    global_header_depth=int(
                        ((package.get("model_facing") or {}).get("h") or [None, 0])[1]
                        or 0
                    ),
                )
        except PdfCsvExperimentError as exc:
            parse_error = exc.code
    actual = (attempt.get("usage") or {}).get("input_tokens")
    counted_total = int(counted.get("total_tokens") or 0)
    error_tokens = (
        abs(int(actual) - counted_total) if isinstance(actual, int) else None
    )
    package = job.get("package") or {}
    candidates = ((package.get("model_facing") or {}).get("c") or [])
    safe = {
        "job_key": job["job_key"],
        "task_id": job["task_id"],
        "arm": job["arm"],
        "table_key": job["table_key"],
        "package_id": job["package_id"],
        "attempt_id": attempt.get("attempt_id"),
        "attempt_number": job["attempt_number"],
        "attempt_lineage": attempt.get("attempt_lineage"),
        "provider_status": (
            "passed" if attempt.get("terminal_failure_class") is None else "failed"
        ),
        "artifact_status": "accepted" if parsed is not None and parse_error is None else "failed",
        "validation_error": parse_error,
        "terminal_failure_class": attempt.get("terminal_failure_class"),
        "http_status": attempt.get("http_status"),
        "finish_reason": attempt.get("finish_reason"),
        "model_requested": attempt.get("model_requested"),
        "model_resolved": attempt.get("model_resolved"),
        "raw_response_hash": result.get("response_hash"),
        "visible_output_hash": result.get("visible_output_hash"),
        "parsed_csv_grid_hash": parsed.get("grid_hash") if parsed else None,
        "candidate_grid_hash": parsed.get("candidate_grid_hash") if parsed else None,
        "topology_hash": topology.get("topology_hash") if topology else None,
        "prompt_bytes": len(job["prompt"].encode("utf-8")),
        "candidate_bytes": (
            0
            if job["arm"] == "free_csv"
            else len(canonical_json_bytes(candidates))
        ),
        "sidecar_bytes": int(parsed.get("topology_bytes") or 0) if parsed else 0,
        "csv_bytes": int(parsed.get("csv_bytes") or 0) if parsed else 0,
        "visible_output_bytes": result.get("visible_output_bytes"),
        "provider_response_bytes": result.get("response_bytes"),
        "provider_counted_input_tokens": counted_total,
        "provider_actual_input_tokens": actual,
        "counted_to_actual_error_tokens": error_tokens,
        "counted_to_actual_error_ratio": (
            round(error_tokens / counted_total, 6)
            if isinstance(error_tokens, int) and counted_total
            else None
        ),
        "provider_output_tokens": (attempt.get("usage") or {}).get("output_tokens"),
        "candidate_count": len(candidates),
        "maximum_row_bytes": parsed.get("maximum_row_bytes") if parsed else None,
        "crop_bytes": len(job["png"]),
        "crop_width": job["crop_manifest"].get("width"),
        "crop_height": job["crop_manifest"].get("height"),
        "crop_dpi": job["crop_manifest"].get("dpi"),
        "hidden_retry": False,
        "provider_failover": False,
    }
    return {
        "private": {
            "prompt": job["prompt"],
            "text": text,
            "raw_provider_response": result.get("raw_private_response"),
            "parsed": parsed,
            "topology": topology,
            "binding": binding,
        },
        "safe": safe,
    }


def _run_json_simple_jobs(
    *,
    state: dict[str, Any],
    journal: list[dict[str, Any]],
    journal_path: Path,
    provider: Any,
) -> list[dict[str, Any]]:
    package = state["packages"][0]
    png = state["png_by_package"][package["package_id"]]
    existing = {
        int((item.get("safe") or {}).get("attempt_number") or 0): item
        for item in journal
        if (item.get("safe") or {}).get("arm") == "candidate_json_control_simple"
    }
    for attempt_number in (1, 2):
        if attempt_number in existing:
            continue
        if provider is None:
            job = {
                "job_key": f"json-simple-a{attempt_number}",
                "task_id": "json-simple",
                "arm": "candidate_json_control_simple",
                "table_key": "1:2",
                "package_id": package["package_id"],
                "attempt_number": attempt_number,
            }
            outcome = _provider_skipped(job)
        else:
            lineage = [
                str((existing[index].get("safe") or {}).get("attempt_id") or "")
                for index in range(1, attempt_number)
            ]
            counted = provider.count_tokens(evidence_package=package, png_bytes=png)
            result = provider.invoke(
                evidence_package=package,
                png_bytes=png,
                attempt_number=attempt_number,
                attempt_lineage=lineage,
            )
            provider_attempt = result["attempt"]
            raw_text = _gemini_text(result.get("raw_private_response") or {})
            binding = result.get("binding_output")
            safe = {
                "job_key": f"json-simple-a{attempt_number}",
                "task_id": provider_attempt.get("same_evidence_task_id"),
                "arm": "candidate_json_control_simple",
                "table_key": "1:2",
                "package_id": package["package_id"],
                "attempt_id": provider_attempt.get("attempt_id"),
                "attempt_number": attempt_number,
                "provider_status": (
                    "passed" if provider_attempt.get("terminal_failure_class") is None else "failed"
                ),
                "artifact_status": "accepted" if binding is not None else "failed",
                "validation_error": None if binding is not None else "json_binding_unavailable",
                "terminal_failure_class": provider_attempt.get("terminal_failure_class"),
                "finish_reason": provider_attempt.get("finish_reason"),
                "raw_response_hash": result.get("response_hash"),
                "visible_output_hash": hash_text(raw_text) if raw_text else None,
                "parsed_csv_grid_hash": None,
                "candidate_grid_hash": None,
                "topology_hash": None,
                "prompt_bytes": int(
                    (package.get("component_accounting") or {}).get("model_facing_text_bytes")
                    or 0
                ),
                "candidate_bytes": int(
                    len(
                        canonical_json_bytes(
                            ((package.get("model_facing") or {}).get("c") or [])
                        )
                    )
                ),
                "sidecar_bytes": int(
                    (package.get("component_accounting") or {}).get("schema_bytes") or 0
                ),
                "csv_bytes": 0,
                "visible_output_bytes": len(raw_text.encode("utf-8")) if raw_text else 0,
                "provider_response_bytes": result.get("response_bytes"),
                "provider_counted_input_tokens": counted.get("total_tokens"),
                "provider_actual_input_tokens": (provider_attempt.get("usage") or {}).get(
                    "input_tokens"
                ),
                "provider_output_tokens": (provider_attempt.get("usage") or {}).get(
                    "output_tokens"
                ),
                "candidate_count": int(
                    (package.get("component_accounting") or {}).get("candidate_count") or 0
                ),
                "maximum_row_bytes": None,
                "crop_bytes": (package.get("component_accounting") or {}).get("image_bytes"),
                "crop_width": (package.get("crop_identity") or {}).get("width"),
                "crop_height": (package.get("crop_identity") or {}).get("height"),
                "crop_dpi": (package.get("crop_identity") or {}).get("dpi"),
                "hidden_retry": False,
                "provider_failover": False,
            }
            outcome = {
                "private": {
                    "raw_provider_response": result.get("raw_private_response"),
                    "text": raw_text,
                    "binding": binding,
                },
                "safe": safe,
            }
        journal.append(outcome)
        existing[attempt_number] = outcome
        _write_json(journal_path, journal)
    return journal


def _revalidate_journal(
    journal: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
    states: dict[str, dict[str, Any]],
    runtime: Any,
) -> list[dict[str, Any]]:
    by_key = {job["job_key"]: job for job in jobs}
    for item in journal:
        safe = item.get("safe") if isinstance(item.get("safe"), dict) else {}
        private = item.get("private") if isinstance(item.get("private"), dict) else {}
        job = by_key.get(str(safe.get("job_key") or ""))
        if job is None or safe.get("provider_status") != "passed":
            continue
        text = private.get("text")
        try:
            if job["arm"] == "free_csv":
                state_rows, state_columns = _expected_free_shape(job)
                parsed = runtime.parse_free_csv(
                    text,
                    expected_rows=state_rows,
                    expected_columns=state_columns,
                )
                topology = None
                binding = None
            else:
                package = job["package"]
                window = package.get("window") or {}
                if job["arm"] == "candidate_csv":
                    parsed = runtime.parse_candidate_csv(
                        text,
                        expected_rows=int(window.get("row_count") or 0),
                        expected_columns=int(window.get("column_count") or 0),
                        candidate_ids=list(window.get("candidate_ids") or []),
                    )
                    topology = None
                else:
                    parsed, topology = runtime.parse_candidate_topology_envelope(
                        text,
                        expected_rows=int(window.get("row_count") or 0),
                        expected_columns=int(window.get("column_count") or 0),
                        candidate_ids=list(window.get("candidate_ids") or []),
                        expected_continuation=job["continuation"],
                    )
                binding = runtime.binding_from_csv(
                    evidence_package=package,
                    parsed=parsed,
                    topology=topology,
                    global_header_depth=int(
                        ((package.get("model_facing") or {}).get("h") or [None, 0])[1]
                        or 0
                    ),
                )
            private.update({"parsed": parsed, "topology": topology, "binding": binding})
            safe.update(
                {
                    "artifact_status": "accepted",
                    "validation_error": None,
                    "parsed_csv_grid_hash": parsed.get("grid_hash"),
                    "candidate_grid_hash": parsed.get("candidate_grid_hash"),
                    "topology_hash": topology.get("topology_hash") if topology else None,
                    "csv_bytes": parsed.get("csv_bytes"),
                    "sidecar_bytes": parsed.get("topology_bytes", 0),
                    "maximum_row_bytes": parsed.get("maximum_row_bytes"),
                    "crop_bytes": len(job["png"]),
                }
            )
        except PdfCsvExperimentError as exc:
            private.update({"parsed": None, "topology": None, "binding": None})
            safe.update(
                {
                    "artifact_status": "failed",
                    "validation_error": exc.code,
                    "crop_bytes": len(job["png"]),
                }
            )
        item["private"] = private
        item["safe"] = safe
    return journal


def _free_outcomes(
    states: dict[str, dict[str, Any]], journal: list[dict[str, Any]], runtime: Any
) -> dict[str, dict[int, dict[str, Any]]]:
    outcomes: dict[str, dict[int, dict[str, Any]]] = {}
    for key in TARGET_KEYS:
        outcomes[key] = {}
        for attempt in ((1, 2) if key in REPEAT_KEYS else (1,)):
            entry = _journal_entry(journal, "free_csv", key, attempt)
            parsed = (entry.get("private") or {}).get("parsed") if entry else None
            reference = states[key]["reference"].get("cells") or []
            parser_grid = runtime.parser_grid(states[key]["ledger"])
            grid = parsed.get("rows") if isinstance(parsed, dict) else None
            entry_safe = (entry.get("safe") or {}) if entry else {}
            reason_codes = [] if grid is not None else [
                str(
                    entry_safe.get("validation_error")
                    or entry_safe.get("terminal_failure_class")
                    or "provider_failed"
                )
            ]
            outcome = {
                "table_key": key,
                "attempt_number": attempt,
                "terminal_status": (
                    "parsed_diagnostic" if grid is not None else "malformed_or_provider_failed"
                ),
                "reason_codes": reason_codes,
                "authoritative": False,
                "grid_hash": parsed.get("grid_hash") if isinstance(parsed, dict) else None,
                "topology_hash": None,
                "placement_hash": None,
                "score": runtime.compare_views(
                    free_grid=grid,
                    candidate_grid=None,
                    parser_grid=parser_grid,
                    reference_grid=reference,
                )["free_vs_reference"],
                "comparison": runtime.compare_views(
                    free_grid=grid,
                    candidate_grid=None,
                    parser_grid=parser_grid,
                    reference_grid=reference,
                ),
                "materialization": None,
                "structural_validation": None,
                "validation": None,
                "metrics": _metrics_for_entries([entry] if entry else [], states[key]),
                "_private_grid": grid,
            }
            outcomes[key][attempt] = outcome
    return outcomes


def _candidate_outcomes(
    *,
    arm: str,
    states: dict[str, dict[str, Any]],
    journal: list[dict[str, Any]],
    runtime: Any,
) -> dict[str, dict[int, dict[str, Any]]]:
    materializer = PdfHybridMaterializationFactory().create()
    structure = PdfHybridStructureFactory().create()
    validator = PdfTableValidationFactory().create()
    outcomes: dict[str, dict[int, dict[str, Any]]] = {}
    for key in TARGET_KEYS:
        state = states[key]
        outcomes[key] = {}
        for attempt in ((1, 2) if key in REPEAT_KEYS else (1,)):
            entries = [
                _journal_entry(journal, arm, key, attempt, package["package_id"])
                for package in state["packages"]
            ]
            terminal = "malformed_or_provider_failed"
            error_codes = []
            materialization = None
            structural_validation = None
            validation = None
            candidate_grid = None
            grid_hash = None
            topology_hash = None
            placement_hash = None
            if all(
                entry
                and (entry.get("safe") or {}).get("artifact_status") == "accepted"
                and isinstance((entry.get("private") or {}).get("binding"), dict)
                for entry in entries
            ):
                try:
                    bindings = [(entry.get("private") or {})["binding"] for entry in entries]
                    logical_evidence, joined = state["windows_runtime"].join(
                        compact_ledger=state["ledger"],
                        plan=state["plan"],
                        packages=state["packages"],
                        bindings=bindings,
                    )
                    materialization = materializer.materialize(
                        evidence_package=logical_evidence,
                        binding_output=joined,
                    )
                    structural_validation = structure.validate_placement(
                        compact_ledger=state["ledger"],
                        materialization=materialization,
                    )
                    validation = validator.validate(
                        evidence_package=logical_evidence,
                        binding_output=joined,
                        materialization=materialization,
                        classification=state["classification"],
                        independent_structural_validation=structural_validation,
                    )
                    candidate_grid = _materialization_grid(materialization)
                    placement_hash = materialization.get("placement_checksum")
                    grid_hash = sha256_json(candidate_grid)
                    topology_hash = sha256_json(
                        [
                            (entry.get("safe") or {}).get("topology_hash")
                            for entry in entries
                        ]
                    ) if arm == "candidate_csv_topology" else None
                    terminal = (
                        "accepted_shadow"
                        if validation.get("aggregate_result") == "accepted_shadow"
                        else "blocked_structural_or_contract"
                    )
                    error_codes = sorted(
                        set(structural_validation.get("reason_codes") or [])
                        | set(validation.get("reason_codes") or [])
                    )
                except Exception as exc:
                    error_codes = [getattr(exc, "code", type(exc).__name__)]
            else:
                error_codes = sorted(
                    {
                        str(
                            (entry.get("safe") or {}).get("validation_error")
                            or (entry.get("safe") or {}).get("terminal_failure_class")
                            or "provider_failed"
                        )
                        for entry in entries
                        if entry
                        and (entry.get("safe") or {}).get("artifact_status")
                        != "accepted"
                    }
                )
            parser_grid = runtime.parser_grid(state["ledger"])
            reference = state["reference"].get("cells") or []
            comparison = runtime.compare_views(
                free_grid=None,
                candidate_grid=candidate_grid,
                parser_grid=parser_grid,
                reference_grid=reference,
            )
            outcomes[key][attempt] = {
                "table_key": key,
                "attempt_number": attempt,
                "terminal_status": terminal,
                "reason_codes": error_codes,
                "authoritative": False,
                "grid_hash": grid_hash,
                "topology_hash": topology_hash,
                "placement_hash": placement_hash,
                "score": comparison["candidate_vs_reference"],
                "comparison": comparison,
                "materialization": materialization,
                "structural_validation": structural_validation,
                "validation": validation,
                "metrics": _metrics_for_entries([item for item in entries if item], state),
                "_compact_ledger": state["ledger"],
            }
    return outcomes


def _load_json_control(
    control_dir: Path,
    *,
    states: dict[str, dict[str, Any]],
    journal: list[dict[str, Any]],
) -> dict[str, Any]:
    safe = json.loads((control_dir / "evidence.safe.json").read_text(encoding="utf-8"))
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=control_dir / "artifacts.sqlite3",
            payload_root=control_dir / "payloads",
        )
    ).create()
    records = store.list_by_run(str(safe.get("normalization_run_id") or ""))
    packages = {}
    for record in records:
        if record.artifact_type != "broker_reports_pdf_hybrid_window_evidence_v2":
            continue
        payload = store.read_payload(record)
        if not isinstance(payload, dict):
            continue
        packages[str(payload.get("package_id") or "")] = payload
    attempts = {}
    for record in records:
        if record.artifact_type != "broker_reports_pdf_provider_attempt_v1":
            continue
        payload = store.read_payload(record)
        if isinstance(payload, dict):
            attempts[(str(payload.get("same_evidence_task_id") or ""), int(payload.get("attempt_number") or 0))] = payload
    raw = {}
    for record in records:
        if record.artifact_type != "broker_reports_pdf_hybrid_raw_response_v1":
            continue
        metadata = record.safe_metadata or {}
        key = (str(metadata.get("package_id") or ""), int(metadata.get("attempt_number") or 0))
        raw[key] = {
            "payload": store.read_payload(record),
            "response_bytes": metadata.get("response_bytes"),
            "response_hash": metadata.get("response_hash"),
        }
    safe_by_key = {
        str(item.get("table_key") or ""): item
        for item in safe.get("tables") or []
        if isinstance(item, dict)
    }
    table_ref_by_key = {
        key: str(item.get("table_ref") or "") for key, item in safe_by_key.items()
    }
    outcomes = {}
    for key in sorted(JSON_LIVE3_KEYS, key=TARGET_KEYS.index):
        unique_visible = _unique_visible_text_bytes(
            states[key]["reference"].get("cells") or []
        )
        table_ref = table_ref_by_key[key]
        table_packages = [
            package
            for package in packages.values()
            if package.get("table_ref") == table_ref
            and int((package.get("crop_identity") or {}).get("dpi") or 0) == 150
        ]
        table_packages = list({item["package_id"]: item for item in table_packages}.values())
        primary_attempts = []
        output_bytes = 0
        visible_hashes = []
        for package in table_packages:
            package_id = package["package_id"]
            task_id = "pdfhybridtask_" + package_id.removeprefix("pdfhybridpkg_")
            attempt = attempts.get((task_id, 1), {})
            primary_attempts.append(attempt)
            raw_item = raw.get((package_id, 1), {})
            text = _gemini_text(raw_item.get("payload") or {})
            output_bytes += len(text.encode("utf-8")) if text else 0
            visible_hashes.append(hash_text(text) if text else None)
        source = safe_by_key[key]
        outcome = {
            "table_key": key,
            "terminal_status": source.get("terminal_status"),
            "score": source.get("score"),
            "placement_hash": source.get("placement_checksum"),
            "repeat_placement_hash": source.get("repeat_placement_checksum"),
            "metrics": {
                "package_count": len(table_packages),
                "candidate_count": source.get("logical_candidates"),
                "prompt_bytes": sum(
                    int((item.get("component_accounting") or {}).get("model_facing_text_bytes") or 0)
                    for item in table_packages
                ),
                "candidate_bytes": sum(
                    len(
                        canonical_json_bytes(
                            ((item.get("model_facing") or {}).get("c") or [])
                        )
                    )
                    for item in table_packages
                ),
                "sidecar_or_schema_bytes": sum(
                    int((item.get("component_accounting") or {}).get("schema_bytes") or 0)
                    for item in table_packages
                ),
                "crop_count": len(table_packages),
                "crop_bytes": sum(
                    int((item.get("component_accounting") or {}).get("image_bytes") or 0)
                    for item in table_packages
                ),
                "crop_width_min": min(
                    (
                        int((item.get("crop_identity") or {}).get("width") or 0)
                        for item in table_packages
                        if int((item.get("crop_identity") or {}).get("width") or 0) > 0
                    ),
                    default=0,
                ),
                "crop_width_max": max(
                    (int((item.get("crop_identity") or {}).get("width") or 0) for item in table_packages),
                    default=0,
                ),
                "crop_height_min": min(
                    (
                        int((item.get("crop_identity") or {}).get("height") or 0)
                        for item in table_packages
                        if int((item.get("crop_identity") or {}).get("height") or 0) > 0
                    ),
                    default=0,
                ),
                "crop_height_max": max(
                    (int((item.get("crop_identity") or {}).get("height") or 0) for item in table_packages),
                    default=0,
                ),
                "crop_dpi_values": sorted(
                    {
                        int((item.get("crop_identity") or {}).get("dpi") or 0)
                        for item in table_packages
                        if int((item.get("crop_identity") or {}).get("dpi") or 0) > 0
                    }
                ),
                "unique_visible_text_bytes": unique_visible,
                "model_facing_amplification": (
                    round(
                        sum(
                            int((item.get("component_accounting") or {}).get("model_facing_text_bytes") or 0)
                            for item in table_packages
                        )
                        / unique_visible,
                        6,
                    )
                    if unique_visible
                    else None
                ),
                "visible_output_bytes": output_bytes,
                "provider_input_tokens": sum(
                    int((item.get("usage") or {}).get("input_tokens") or 0)
                    for item in primary_attempts
                ),
                "provider_output_tokens": sum(
                    int((item.get("usage") or {}).get("output_tokens") or 0)
                    for item in primary_attempts
                ),
                "malformed_outputs": sum(
                    item.get("validation_result") != "passed" for item in primary_attempts
                ),
                "raw_response_hashes": [
                    (raw.get((item["package_id"], 1), {}) or {}).get("response_hash")
                    for item in table_packages
                ],
                "visible_output_hashes": visible_hashes,
            },
            "authoritative": False,
        }
        outcomes[key] = outcome
    simple = _json_simple_outcome(states["1:2"], journal)
    outcomes["1:2"] = simple
    control_tables = [outcomes[key] for key in TARGET_KEYS]
    accuracy_scores = [
        item.get("score") or _failed_scheduled_score(states["1:2"]["reference"])
        for item in control_tables
    ]
    accepted_count = sum(
        item.get("terminal_status") == "accepted_shadow" for item in control_tables
    )
    return {
        "tables": control_tables,
        "aggregate": {
            **_aggregate_scores(accuracy_scores, len(TARGET_KEYS), accepted_count),
            **_aggregate_arm_tables(control_tables),
        },
        "source_control_run": str(control_dir),
        "source_control_revision": safe.get("source_revision"),
        "same_model_config": True,
        "existing_validators_unchanged": True,
    }


def _json_simple_outcome(state: dict[str, Any], journal: list[dict[str, Any]]) -> dict[str, Any]:
    entries = [
        _journal_entry(journal, "candidate_json_control_simple", "1:2", attempt)
        for attempt in (1, 2)
    ]
    materializer = PdfHybridMaterializationFactory().create()
    structure = PdfHybridStructureFactory().create()
    validator = PdfTableValidationFactory().create()
    materials = []
    primary_validation = None
    primary_structure = None
    reason_codes = []
    for entry in entries:
        binding = (entry.get("private") or {}).get("binding") if entry else None
        if not isinstance(binding, dict):
            materials.append(None)
            continue
        evidence, joined = state["windows_runtime"].join(
            compact_ledger=state["ledger"],
            plan=state["plan"],
            packages=state["packages"],
            bindings=[binding],
        )
        material = materializer.materialize(
            evidence_package=evidence, binding_output=joined
        )
        structural = structure.validate_placement(
            compact_ledger=state["ledger"], materialization=material
        )
        validation = validator.validate(
            evidence_package=evidence,
            binding_output=joined,
            materialization=material,
            classification=state["classification"],
            independent_structural_validation=structural,
        )
        materials.append(material)
        if primary_validation is None:
            primary_validation = validation
            primary_structure = structural
            reason_codes = sorted(
                set(validation.get("reason_codes") or [])
                | set(structural.get("reason_codes") or [])
            )
    reference = state["reference"].get("cells") or []
    grid = _materialization_grid(materials[0]) if materials and materials[0] else None
    score = PdfCsvExperimentFactory().create().compare_views(
        free_grid=None,
        candidate_grid=grid,
        parser_grid=PdfCsvExperimentFactory().create().parser_grid(state["ledger"]),
        reference_grid=reference,
    )["candidate_vs_reference"]
    score["headers_exact"] = bool(materials and materials[0]) and len(
        materials[0].get("header_rows") or []
    ) == int(state["reference"].get("header_rows") or 0)
    placement = materials[0].get("placement_checksum") if materials and materials[0] else None
    repeat = materials[1].get("placement_checksum") if len(materials) > 1 and materials[1] else None
    return {
        "table_key": "1:2",
        "terminal_status": (
            "accepted_shadow"
            if primary_validation and primary_validation.get("aggregate_result") == "accepted_shadow"
            else "blocked_structural_or_contract"
        ),
        "reason_codes": reason_codes,
        "score": score,
        "placement_hash": placement,
        "repeat_placement_hash": repeat,
        "metrics": _metrics_for_entries([item for item in entries[:1] if item], state),
        "authoritative": False,
    }


def _cross_arm_comparisons(
    *,
    states: dict[str, dict[str, Any]],
    free_outcomes: dict[str, dict[int, dict[str, Any]]],
    candidate_outcomes: dict[str, dict[int, dict[str, Any]]],
    topology_outcomes: dict[str, dict[int, dict[str, Any]]],
    runtime: Any,
) -> dict[str, Any]:
    tables = []
    for key in TARGET_KEYS:
        free = free_outcomes[key][1]
        candidate = candidate_outcomes[key][1]
        topology = topology_outcomes[key][1]
        free_grid = _outcome_grid(free)
        candidate_grid = _materialization_grid(candidate.get("materialization"))
        topology_grid = _materialization_grid(topology.get("materialization"))
        parser_grid = runtime.parser_grid(states[key]["ledger"])
        reference = states[key]["reference"].get("cells") or []
        tables.append(
            {
                "table_key": key,
                "free_vs_candidate_csv": runtime.compare_views(
                    free_grid=free_grid,
                    candidate_grid=candidate_grid,
                    parser_grid=parser_grid,
                    reference_grid=reference,
                ),
                "free_vs_candidate_csv_topology": runtime.compare_views(
                    free_grid=free_grid,
                    candidate_grid=topology_grid,
                    parser_grid=parser_grid,
                    reference_grid=reference,
                ),
            }
        )
    return {"tables": tables}


def _free_continuation(outcomes: dict[str, dict[int, dict[str, Any]]]) -> dict[str, Any]:
    first = _outcome_grid(outcomes["3:2"][1])
    second = _outcome_grid(outcomes["4:1"][1])
    columns = [max((len(row) for row in grid or []), default=0) for grid in (first, second)]
    passed = bool(first) and bool(second) and columns == [16, 16]
    return {
        "fragments_evaluated_separately": True,
        "logical_group_evaluated": True,
        "fragment_order": ["3:2", "4:1"],
        "shared_columns": columns,
        "joined_rows": len(first or []) + len(second or []),
        "passed": passed,
        "reason_codes": [] if passed else ["pdf_csv_free_continuation_shape_mismatch"],
        "authoritative": False,
    }


def _candidate_continuation(
    outcomes: dict[str, dict[int, dict[str, Any]]], contract: dict[str, Any]
) -> dict[str, Any]:
    structure = PdfHybridStructureFactory().create()
    fragments = []
    for key in ("3:2", "4:1"):
        outcome = outcomes[key][1]
        fragments.append(
            {
                "compact_ledger": None,
                "materialization": outcome.get("materialization"),
                "structural_validation": outcome.get("structural_validation"),
            }
        )
    # The validator needs ledgers; attach the original values through the private outcome hook.
    for item, key in zip(fragments, ("3:2", "4:1")):
        item["compact_ledger"] = outcomes[key][1].get("_compact_ledger")
    if any(item.get("compact_ledger") is None for item in fragments):
        return {
            "passed": False,
            "reason_codes": ["pdf_csv_continuation_fragment_unavailable"],
            "fragment_count": 2,
            "authoritative": False,
        }
    result = structure.validate_continuation(
        contract=contract, fragment_results=fragments
    )
    result["authoritative"] = False
    return result


def _repeatability(
    arm: str,
    outcomes: dict[str, dict[int, dict[str, Any]]],
    journal: list[dict[str, Any]],
) -> dict[str, Any]:
    runtime = PdfCsvExperimentFactory().create()
    tables = []
    for key in sorted(REPEAT_KEYS, key=TARGET_KEYS.index):
        first = outcomes[key].get(1, {})
        second = outcomes[key].get(2, {})
        raw_first = _raw_hashes(journal, arm, key, 1)
        raw_second = _raw_hashes(journal, arm, key, 2)
        required = ("grid",) if arm == "free_csv" else (
            ("grid", "topology", "placement")
            if arm == "candidate_csv_topology"
            else ("grid", "placement")
        )
        assessment = runtime.assess_repeatability(
            [
                {
                    "grid": first.get("grid_hash"),
                    "topology": first.get("topology_hash"),
                    "placement": first.get("placement_hash"),
                },
                {
                    "grid": second.get("grid_hash"),
                    "topology": second.get("topology_hash"),
                    "placement": second.get("placement_hash"),
                },
            ],
            required_fields=required,
        )
        tables.append(
            {
                "table_key": key,
                "raw_response_hashes_attempt_1": raw_first,
                "raw_response_hashes_attempt_2": raw_second,
                "raw_response_hash_match": raw_first == raw_second,
                "parsed_grid_hash_match": assessment["fields"]["grid"]["match"],
                "topology_hash_match": (
                    assessment["fields"]["topology"]["match"]
                    if "topology" in assessment["fields"]
                    else None
                ),
                "materialized_placement_hash_match": (
                    assessment["fields"]["placement"]["match"]
                    if "placement" in assessment["fields"]
                    else None
                ),
                "assessed": all(
                    item["assessed"] for item in assessment["fields"].values()
                ),
                "passed": assessment["passed"],
                "ever_conflicted": assessment["ever_conflicted"],
                "later_agreement_can_clear_conflict": False,
            }
        )
    return {
        "tables": tables,
        "repeatability_passed_tables": sum(item["passed"] for item in tables),
        "repeatability_total_tables": len(tables),
        "later_agreement_can_clear_conflict": False,
    }


def _json_repeatability(control: dict[str, Any]) -> dict[str, Any]:
    tables = []
    for item in control.get("tables") or []:
        if item.get("table_key") not in REPEAT_KEYS:
            continue
        first = item.get("placement_hash")
        second = item.get("repeat_placement_hash")
        assessed = bool(first) and bool(second)
        tables.append(
            {
                "table_key": item.get("table_key"),
                "assessed": assessed,
                "materialized_placement_hash_match": assessed and first == second,
                "ever_conflicted": assessed and first != second,
                "later_agreement_can_clear_conflict": False,
            }
        )
    return {"tables": tables, "later_agreement_can_clear_conflict": False}


def _arm_summary(
    outcomes: dict[str, dict[int, dict[str, Any]]],
    states: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    tables = []
    scores = []
    accepted = 0
    for key in TARGET_KEYS:
        outcome = outcomes[key][1]
        score = copy.deepcopy(outcome.get("score")) if outcome.get("score") else _failed_scheduled_score(states[key]["reference"])
        score["headers_exact"] = _headers_exact(outcome, states[key])
        outcome["score"] = score
        scores.append(score)
        accepted += outcome.get("terminal_status") in {"accepted_shadow", "parsed_diagnostic"}
        tables.append(_safe_outcome(outcome))
    return {
        "tables": tables,
        "aggregate": {
            **_aggregate_scores(scores, len(TARGET_KEYS), accepted),
            **_aggregate_arm_tables(tables),
        },
    }


def _aggregate_arm_tables(tables: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = [item.get("metrics") or {} for item in tables]
    visible_bytes = sum(int(item.get("visible_output_bytes") or 0) for item in metrics)
    prompt_bytes = sum(int(item.get("prompt_bytes") or 0) for item in metrics)
    unique_visible_bytes = sum(
        int(item.get("unique_visible_text_bytes") or 0) for item in metrics
    )
    crop_width_mins = [
        int(item.get("crop_width_min") or 0)
        for item in metrics
        if int(item.get("crop_width_min") or 0) > 0
    ]
    crop_height_mins = [
        int(item.get("crop_height_min") or 0)
        for item in metrics
        if int(item.get("crop_height_min") or 0) > 0
    ]
    return {
        "tables": len(tables),
        "accepted_or_parsed_tables": sum(
            item.get("terminal_status") in {"accepted_shadow", "parsed_diagnostic"}
            for item in tables
        ),
        "prompt_bytes": prompt_bytes,
        "candidate_bytes": sum(int(item.get("candidate_bytes") or 0) for item in metrics),
        "sidecar_or_schema_bytes": sum(
            int(item.get("sidecar_or_schema_bytes") or item.get("sidecar_bytes") or 0)
            for item in metrics
        ),
        "crop_count": sum(int(item.get("crop_count") or 0) for item in metrics),
        "crop_bytes": sum(int(item.get("crop_bytes") or 0) for item in metrics),
        "crop_width_min": min(crop_width_mins, default=0),
        "crop_width_max": max(
            (int(item.get("crop_width_max") or 0) for item in metrics), default=0
        ),
        "crop_height_min": min(crop_height_mins, default=0),
        "crop_height_max": max(
            (int(item.get("crop_height_max") or 0) for item in metrics), default=0
        ),
        "crop_dpi_values": sorted(
            {
                int(dpi)
                for item in metrics
                for dpi in (item.get("crop_dpi_values") or [])
                if int(dpi) > 0
            }
        ),
        "unique_visible_text_bytes": unique_visible_bytes,
        "model_facing_amplification": (
            round(prompt_bytes / unique_visible_bytes, 6)
            if unique_visible_bytes
            else None
        ),
        "visible_output_bytes": visible_bytes,
        "provider_input_tokens": sum(
            int(item.get("provider_input_tokens") or 0) for item in metrics
        ),
        "provider_output_tokens": sum(
            int(item.get("provider_output_tokens") or 0) for item in metrics
        ),
        "malformed_outputs": sum(int(item.get("malformed_outputs") or 0) for item in metrics),
        "maximum_row_bytes": max(
            (int(item.get("maximum_row_bytes") or 0) for item in metrics), default=0
        ),
    }


def _metrics_for_entries(entries: list[dict[str, Any]], state: dict[str, Any]) -> dict[str, Any]:
    safe = [item.get("safe") or {} for item in entries]
    arm = str((safe[0] if safe else {}).get("arm") or "")
    candidate_bound = arm != "free_csv"
    unique_visible = _unique_visible_text_bytes(state["reference"].get("cells") or [])
    prompt_bytes = sum(int(item.get("prompt_bytes") or 0) for item in safe)
    crop_widths = [
        int(item.get("crop_width") or 0)
        for item in safe
        if int(item.get("crop_width") or 0) > 0
    ]
    crop_heights = [
        int(item.get("crop_height") or 0)
        for item in safe
        if int(item.get("crop_height") or 0) > 0
    ]
    return {
        "package_count": len(entries),
        "candidate_count": (
            len(state["ledger"].get("candidate_order") or []) if candidate_bound else 0
        ),
        "prompt_bytes": prompt_bytes,
        "candidate_bytes": (
            sum(int(item.get("candidate_bytes") or 0) for item in safe)
            if candidate_bound
            else 0
        ),
        "sidecar_bytes": sum(int(item.get("sidecar_bytes") or 0) for item in safe),
        "crop_count": len(safe),
        "crop_bytes": sum(int(item.get("crop_bytes") or 0) for item in safe),
        "crop_width_min": min(crop_widths, default=0),
        "crop_width_max": max(crop_widths, default=0),
        "crop_height_min": min(crop_heights, default=0),
        "crop_height_max": max(crop_heights, default=0),
        "crop_dpi_values": sorted(
            {
                int(item.get("crop_dpi") or 0)
                for item in safe
                if int(item.get("crop_dpi") or 0) > 0
            }
        ),
        "visible_output_bytes": sum(
            int(item.get("visible_output_bytes") or 0) for item in safe
        ),
        "provider_input_tokens": sum(
            int(item.get("provider_actual_input_tokens") or 0) for item in safe
        ),
        "provider_output_tokens": sum(
            int(item.get("provider_output_tokens") or 0) for item in safe
        ),
        "malformed_outputs": sum(item.get("artifact_status") != "accepted" for item in safe),
        "maximum_row_bytes": max(
            (int(item.get("maximum_row_bytes") or 0) for item in safe), default=0
        ),
        "maximum_counted_to_actual_error_ratio": max(
            (float(item.get("counted_to_actual_error_ratio") or 0) for item in safe),
            default=0.0,
        ),
        "unique_visible_text_bytes": unique_visible,
        "model_facing_amplification": (
            round(prompt_bytes / unique_visible, 6) if unique_visible else None
        ),
        "provenance_candidate_coverage": (
            1.0
            if entries
            and all((item.get("safe") or {}).get("artifact_status") == "accepted" for item in entries)
            and all((item.get("safe") or {}).get("arm") != "free_csv" for item in entries)
            else 0.0
        ),
    }


def _safe_outcome(outcome: dict[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(outcome.get(key))
        for key in (
            "table_key",
            "attempt_number",
            "terminal_status",
            "reason_codes",
            "authoritative",
            "grid_hash",
            "topology_hash",
            "placement_hash",
            "score",
            "comparison",
            "metrics",
        )
        if key in outcome
    }


def _materialization_grid(materialization: dict[str, Any] | None) -> list[list[str]] | None:
    if not isinstance(materialization, dict):
        return None
    rows = int(materialization.get("row_count") or 0)
    columns = int(materialization.get("column_count") or 0)
    grid = [[""] * columns for _ in range(rows)]
    for cell in materialization.get("cells") or []:
        if not isinstance(cell, dict):
            continue
        row = int(cell.get("row_ordinal") or 0) - 1
        column = int(cell.get("column_ordinal") or 0) - 1
        if 0 <= row < rows and 0 <= column < columns:
            grid[row][column] = " ".join(
                str(value) for value in cell.get("resolved_source_values") or []
            )
    return grid


def _headers_exact(outcome: dict[str, Any], state: dict[str, Any]) -> bool:
    expected_count = int(state["reference"].get("header_rows") or 0)
    materialization = outcome.get("materialization")
    if isinstance(materialization, dict):
        return len(materialization.get("header_rows") or []) == expected_count
    grid = outcome.get("_private_grid")
    reference = state["reference"].get("cells") or []
    if not isinstance(grid, list) or len(grid) < expected_count:
        return False
    for row in range(expected_count):
        expected = [" ".join(str(item or "").split()) for item in reference[row]]
        actual = [" ".join(str(item or "").split()) for item in grid[row]]
        if expected != actual:
            return False
    return True


def _outcome_grid(outcome: dict[str, Any]) -> list[list[str]] | None:
    comparison = outcome.get("comparison") or {}
    # The private grid is intentionally not copied into safe outcomes; callers use materialization when available.
    return outcome.get("_private_grid") or _materialization_grid(outcome.get("materialization"))


def _journal_entry(
    journal: list[dict[str, Any]],
    arm: str,
    table_key: str,
    attempt: int,
    package_id: str | None = None,
) -> dict[str, Any] | None:
    matches = [
        item
        for item in journal
        if (item.get("safe") or {}).get("arm") == arm
        and (item.get("safe") or {}).get("table_key") == table_key
        and int((item.get("safe") or {}).get("attempt_number") or 0) == attempt
        and (
            package_id is None
            or (item.get("safe") or {}).get("package_id") == package_id
        )
    ]
    return matches[0] if len(matches) == 1 else None


def _raw_hashes(
    journal: list[dict[str, Any]], arm: str, table_key: str, attempt: int
) -> list[str | None]:
    return sorted(
        [
            (item.get("safe") or {}).get("raw_response_hash")
            for item in journal
            if (item.get("safe") or {}).get("arm") == arm
            and (item.get("safe") or {}).get("table_key") == table_key
            and int((item.get("safe") or {}).get("attempt_number") or 0) == attempt
        ],
        key=lambda item: str(item),
    )


def _continuation_identity(key: str) -> list[Any] | None:
    if key == "3:2":
        return [CONTINUATION_GROUP_ID, 1, 2]
    if key == "4:1":
        return [CONTINUATION_GROUP_ID, 2, 2]
    return None


def _expected_free_shape(job: dict[str, Any]) -> tuple[int, int]:
    shape = job.get("expected_shape")
    if (
        not isinstance(shape, list)
        or len(shape) != 2
        or not all(isinstance(item, int) and item > 0 for item in shape)
    ):
        raise PdfCsvExperimentError("pdf_csv_expected_shape_missing")
    return int(shape[0]), int(shape[1])


def _unique_visible_text_bytes(rows: list[list[Any]]) -> int:
    unique = []
    seen = set()
    for row in rows:
        for value in row:
            text = " ".join(str(value or "").split())
            if text and text not in seen:
                seen.add(text)
                unique.append(text)
    return len("\n".join(unique).encode("utf-8"))


def _structural_case(key: str) -> str:
    return {
        "1:2": "deterministic_simple_control",
        "1:3": "wide_multi_row_header",
        "3:2": "wide_multiline_header_continuation_fragment_1",
        "4:1": "cross_page_continuation_fragment_2",
        "4:2": "grouped_merged_header",
        "5:3": "tax_summary",
    }[key]


def _openwebui_request(env_path: Path) -> Any:
    env = _read_env(env_path)
    host = str(
        env.get("OPENWEBUI_HOST")
        or env.get("OPENWEBUI_BASE_URL")
        or env.get("BASE_URL")
        or ""
    ).rstrip("/")
    base_url = host if host.startswith(("http://", "https://")) else f"https://{host}"
    email = str(
        env.get("WEBUI_ADMIN_EMAIL")
        or env.get("OPENWEBUI_ADMIN_EMAIL")
        or env.get("ADMIN_EMAIL")
        or ""
    )
    password = str(
        env.get("WEBUI_ADMIN_PASSWORD")
        or env.get("OPENWEBUI_ADMIN_PASSWORD")
        or env.get("ADMIN_PASSWORD")
        or ""
    )
    if not all((base_url, email, password)):
        raise ValueError("openwebui_live_credentials_missing")
    session = requests.Session()
    response = session.post(
        base_url + "/api/v1/auths/signin",
        json={"email": email, "password": password},
        timeout=30,
    )
    response.raise_for_status()
    token = str(response.json().get("token") or "")
    session.headers.update({"Authorization": f"Bearer {token}"})
    config_response = session.get(base_url + "/openai/config", timeout=30)
    config_response.raise_for_status()
    config = config_response.json()
    config_object = SimpleNamespace(
        OPENAI_API_BASE_URLS=config.get("OPENAI_API_BASE_URLS"),
        OPENAI_API_KEYS=config.get("OPENAI_API_KEYS"),
        OPENAI_API_CONFIGS=config.get("OPENAI_API_CONFIGS"),
    )
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(config=config_object)))


def _read_env(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _table_reference_map(
    source_payload: dict[str, Any], reference_tables: dict[str, dict[str, Any]]
) -> dict[str, str]:
    projection = source_payload.get("pdf_text_layer_projection") or {}
    bboxes = {
        str(item.get("bbox_ref") or ""): item.get("bbox")
        for item in projection.get("bbox_inventory") or []
        if isinstance(item, dict)
    }
    page_numbers = {
        str(item.get("page_ref") or ""): int(item.get("page_number") or 0)
        for item in projection.get("page_inventory") or []
        if isinstance(item, dict)
    }
    result = {}
    for candidate in projection.get("table_candidate_inventory") or []:
        if not isinstance(candidate, dict):
            continue
        page = page_numbers.get(str(candidate.get("page_ref") or ""), 0)
        bbox = bboxes.get(str(candidate.get("bbox_ref") or ""))
        direct_key = f"{page}:{int(candidate.get('parser_ordinal') or 0)}"
        if direct_key in reference_tables:
            result[str(candidate.get("table_candidate_ref") or "")] = direct_key
            continue
        choices = [
            item for item in reference_tables.values() if item.get("page") == page
        ]
        match = max(choices, key=lambda item: _iou(bbox, item.get("bbox")), default=None)
        if match and _iou(bbox, match.get("bbox")) > 0.05:
            result[str(candidate.get("table_candidate_ref") or "")] = str(
                match.get("table_key") or ""
            )
    return result


def _iou(left: Any, right: Any) -> float:
    if (
        not isinstance(left, list)
        or not isinstance(right, list)
        or len(left) != 4
        or len(right) != 4
    ):
        return 0.0
    x0, y0 = max(left[0], right[0]), max(left[1], right[1])
    x1, y1 = min(left[2], right[2]), min(left[3], right[3])
    intersection = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    area_left = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    area_right = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    union = area_left + area_right - intersection
    return intersection / union if union else 0.0


def _failed_scheduled_score(reference: dict[str, Any]) -> dict[str, Any]:
    expected = reference.get("cells") or []
    width = max((len(row) for row in expected), default=0)
    values = [
        _normalize(row[column] if column < len(row) else "")
        for row in expected
        for column in range(width)
    ]
    return {
        "structure_exact": False,
        "headers_exact": False,
        "cells_exact": 0,
        "cells_total": len(values),
        "numeric_exact": 0,
        "numeric_total": sum(_numeric(value) for value in values),
        "empty_exact": 0,
        "empty_total": sum(not value for value in values),
        "hallucinated_nonempty": 0,
        "omitted_nonempty": sum(bool(value) for value in values),
    }


def _aggregate_scores(
    scores: list[dict[str, Any]],
    scheduled_total: int,
    accepted_scored_tables: int,
) -> dict[str, Any]:
    cells = sum(item["cells_total"] for item in scores)
    numeric = sum(item["numeric_total"] for item in scores)
    empty = sum(item["empty_total"] for item in scores)
    return {
        "scheduled_tables": scheduled_total,
        "accepted_scored_tables": accepted_scored_tables,
        "structure_exact_tables": sum(item["structure_exact"] for item in scores),
        "header_exact_tables": sum(item["headers_exact"] for item in scores),
        "cells_exact": sum(item["cells_exact"] for item in scores),
        "cells_total": cells,
        "cell_accuracy": (
            round(sum(item["cells_exact"] for item in scores) / cells, 6)
            if cells
            else 0.0
        ),
        "numeric_exact": sum(item["numeric_exact"] for item in scores),
        "numeric_total": numeric,
        "numeric_accuracy": (
            round(sum(item["numeric_exact"] for item in scores) / numeric, 6)
            if numeric
            else 0.0
        ),
        "empty_exact": sum(item["empty_exact"] for item in scores),
        "empty_total": empty,
        "empty_accuracy": (
            round(sum(item["empty_exact"] for item in scores) / empty, 6)
            if empty
            else 0.0
        ),
        "provider_or_validation_failed_scheduled_tables": (
            scheduled_total - accepted_scored_tables
        ),
    }


def _normalize(value: Any) -> str:
    return re.sub(
        r"\s+", " ", unicodedata.normalize("NFKC", str(value or ""))
    ).strip()


def _numeric(value: str) -> bool:
    return bool(re.fullmatch(r"[+\-]?[\d\s]+(?:[.,]\d+)?", value))


def _gemini_text(payload: dict[str, Any]) -> str:
    texts = []
    for candidate in payload.get("candidates") or []:
        content = candidate.get("content") if isinstance(candidate, dict) else {}
        for part in content.get("parts") or [] if isinstance(content, dict) else []:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                texts.append(part["text"])
    return "".join(texts)


def _provider_skipped(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "private": {"prompt": job.get("prompt"), "text": None},
        "safe": {
            "job_key": job.get("job_key"),
            "task_id": job.get("task_id"),
            "arm": job.get("arm"),
            "table_key": job.get("table_key"),
            "package_id": job.get("package_id"),
            "attempt_number": job.get("attempt_number"),
            "provider_status": "skipped",
            "artifact_status": "failed",
            "validation_error": "provider_skipped",
            "hidden_retry": False,
            "provider_failover": False,
        },
    }


def _failed_job(job: dict[str, Any], code: str) -> dict[str, Any]:
    return {
        "private": {"prompt": job.get("prompt"), "text": None},
        "safe": {
            "job_key": job.get("job_key"),
            "task_id": job.get("task_id"),
            "arm": job.get("arm"),
            "table_key": job.get("table_key"),
            "package_id": job.get("package_id"),
            "attempt_number": job.get("attempt_number"),
            "provider_status": "failed",
            "artifact_status": "failed",
            "validation_error": code,
            "hidden_retry": False,
            "provider_failover": False,
        },
    }


def _read_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _git_revision() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()


if __name__ == "__main__":
    raise SystemExit(main())
