#!/usr/bin/env python3
"""Run the isolated PDF table strategy benchmark without reference access.

``run`` renders only manifest-selected pages, executes strategies A and B, and
derives strategy C by evidence-validating the exact strategy B extraction.
``gate`` seals that reference-free terminal before starting the scorer in a
separate process.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import requests


SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
SERVICE_ROOT = SCRIPT_DIR.parent
DEFAULT_REPO_ROOT = SERVICE_ROOT.parents[1]
DEFAULT_MANIFEST = (
    SERVICE_ROOT / "benchmarks" / "pdf_table_strategy_v1" / "manifest.json"
)
DEFAULT_REFERENCE = (
    SERVICE_ROOT
    / "benchmarks"
    / "pdf_table_strategy_v1"
    / "reference.private.json"
)
DEFAULT_CORPUS_ROOT = (
    DEFAULT_REPO_ROOT
    / "local"
    / "stage2"
    / "broker_reports_pdf_structural_holdout_public_v5_2026-07-15"
    / "corpus"
)
DEFAULT_SCORER = SCRIPT_DIR / "local_pdf_table_strategy_benchmark_score.py"

TERMINAL_SCHEMA = "broker_reports_pdf_table_strategy_benchmark_terminal_v1"
SEAL_SCHEMA = "broker_reports_pdf_table_strategy_benchmark_terminal_seal_v1"
PROCESS_SCHEMA = "broker_reports_pdf_table_strategy_benchmark_gate_processes_v1"
MANIFEST_SCHEMA = "broker_reports_pdf_table_strategy_benchmark_manifest_v1"
FORBIDDEN_REFERENCE_KEYS = {
    "accepted",
    "expected",
    "gold",
    "ground_truth",
    "human_reference",
    "label",
    "reference",
    "truth",
}


sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from broker_reports_gate1.pdf_grid_experiment_provider import (  # noqa: E402
    PdfGridExperimentProviderFactory,
    PdfGridProviderConfig,
)
from broker_reports_gate1.pdf_table_raster import (  # noqa: E402
    PdfTableRasterConfig,
    PdfTableRasterFactory,
)
from broker_reports_gate1.pdf_text_layer import (  # noqa: E402
    PdfParserCapabilityRequest,
    PdfTextLayerParserFactory,
)
from pdf_table_strategy_benchmark_contracts import (  # noqa: E402
    CROP_EXTRACTION_MODEL_VIEW_VERSION,
    DETECTION_MODEL_VIEW_VERSION,
    DIRECT_PAGE_MODEL_VIEW_VERSION,
    UNIFIED_EXTRACTION_SCHEMA_VERSION,
    crop_extraction_model_view,
    detection_model_view,
    detection_schema,
    direct_page_model_view,
    project_crop_bbox_to_page,
    sha256_json,
    unified_extraction_schema,
    validate_detection_output,
    validate_extraction_evidence,
    validate_unified_extraction,
)


class BenchmarkError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return _run_command(args)
    if args.command == "gate":
        return _gate_command(args)
    parser.error("command_required")
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="execute without a reference")
    _add_run_arguments(run)
    gate = subparsers.add_parser(
        "gate", help="run, seal, then score in a separate process"
    )
    _add_run_arguments(gate)
    gate.add_argument("--reference", default=str(DEFAULT_REFERENCE))
    gate.add_argument("--scorer-script", default=str(DEFAULT_SCORER))
    return parser


def _add_run_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--corpus-root", default=str(DEFAULT_CORPUS_ROOT))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--env-file", default=str(DEFAULT_REPO_ROOT / ".env"))
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT))


def _run_command(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        print("benchmark_fresh_output_directory_required", file=sys.stderr)
        return 2
    output_dir.mkdir(parents=True, exist_ok=True)
    terminal_path = output_dir / "terminal.private.json"
    seal_path = output_dir / "terminal.private.sha256.json"
    terminal: dict[str, Any] = {
        "schema_version": TERMINAL_SCHEMA,
        "runner": {
            "pid": os.getpid(),
            "entrypoint": "local_pdf_table_strategy_benchmark.py run",
            "reference_argument_supported": False,
            "provider_factory": (
                "PdfGridExperimentProviderFactory.create_for_openwebui"
            ),
            "raster_factory": "PdfTableRasterFactory.create",
            "parser_factory": "PdfTextLayerParserFactory.create(layout_words)",
        },
        "reference_accessed": False,
        "production_authority": False,
        "production_pipeline_changed": False,
        "production_gate2_selection_changed": False,
        "ocr_performed": False,
        "knowledge_or_rag_used": False,
        "hidden_retry": False,
        "provider_failover": False,
        "manifest_sha256": None,
        "target_manifest": None,
        "source_revision": {},
        "prompt_contracts": {},
        "provider_qualification": None,
        "parser_accounting": {
            "unique_documents": [],
            "total_duration_ms": 0,
        },
        "cases": [],
        "failures": [],
        "run_status": "failed_before_execution",
    }
    exit_code = 1
    try:
        manifest_path = Path(args.manifest).resolve()
        manifest_bytes = manifest_path.read_bytes()
        manifest = _json_object(manifest_bytes, "benchmark_manifest_json_invalid")
        _validate_manifest(manifest)
        # Bind semantic JSON, not checkout-dependent CRLF/LF bytes.
        terminal["manifest_sha256"] = sha256_json(manifest)
        terminal["target_manifest"] = manifest
        terminal["source_revision"] = _source_revision(
            Path(args.repo_root).resolve()
        )
        terminal["prompt_contracts"] = _prompt_contracts(manifest)
        sources = _verify_sources(manifest, Path(args.corpus_root).resolve())

        provider_contract = _object(manifest["provider_contract"])
        provider = PdfGridExperimentProviderFactory(
            PdfGridProviderConfig(
                provider_profile=str(provider_contract["provider_profile"]),
                model_id=str(provider_contract["model_id"]),
                maximum_output_tokens=int(
                    provider_contract["maximum_output_tokens"]
                ),
                maximum_counted_input_tokens=int(
                    provider_contract["maximum_counted_input_tokens"]
                ),
                thinking_level=str(provider_contract.get("thinking_level") or "minimal"),
            )
        ).create_for_openwebui(
            _openwebui_request(Path(args.env_file).resolve())
        )
        qualification = provider.qualify()
        terminal["provider_qualification"] = qualification
        if qualification.get("status") != "qualified":
            raise BenchmarkError("benchmark_provider_not_qualified")

        renderer = PdfTableRasterFactory(
            PdfTableRasterConfig(padding_points=0)
        ).create()
        parser = PdfTextLayerParserFactory().create(
            PdfParserCapabilityRequest(capability="layout_words")
        )
        pdf_cache: dict[str, bytes] = {}
        parse_cache: dict[str, Any] = {}
        for case in manifest["cases"]:
            case_id = str(case["case_id"])
            try:
                pdf_sha = str(case["pdf_sha256"])
                if pdf_sha not in pdf_cache:
                    pdf_cache[pdf_sha] = sources[case_id].read_bytes()
                    parser_started = time.perf_counter()
                    parse_cache[pdf_sha] = parser.parse(pdf_cache[pdf_sha])
                    parser_duration_ms = round(
                        (time.perf_counter() - parser_started) * 1000
                    )
                    terminal["parser_accounting"]["unique_documents"].append(
                        {
                            "pdf_sha256": pdf_sha,
                            "pdf_bytes": len(pdf_cache[pdf_sha]),
                            "duration_ms": parser_duration_ms,
                            "pages_parsed": len(parse_cache[pdf_sha].pages),
                            "capability": "layout_words",
                            "table_construction_performed": False,
                        }
                    )
                    terminal["parser_accounting"]["total_duration_ms"] += (
                        parser_duration_ms
                    )
                terminal["cases"].append(
                    _run_case(
                        case=case,
                        pdf_bytes=pdf_cache[pdf_sha],
                        parse_result=parse_cache[pdf_sha],
                        renderer=renderer,
                        provider=provider,
                        output_dir=output_dir,
                    )
                )
            except Exception as exc:  # each case must reach a terminal result
                code = _error_code(exc, "benchmark_case_unexpected_failure")
                terminal["cases"].append(_failed_case(case, code))
                terminal["failures"].append({"case_id": case_id, "code": code})
        terminal["run_status"] = (
            "completed" if not terminal["failures"] else "completed_with_failures"
        )
        exit_code = 0
    except Exception as exc:
        terminal["failures"].append(
            {"case_id": None, "code": _error_code(exc, "benchmark_runner_failure")}
        )
        terminal["run_status"] = "failed_before_case_completion"

    terminal_bytes = _canonical_json_bytes(terminal)
    terminal_path.write_bytes(terminal_bytes)
    seal = {
        "schema_version": SEAL_SCHEMA,
        "terminal_sha256": hashlib.sha256(terminal_bytes).hexdigest(),
        "terminal_size_bytes": len(terminal_bytes),
        "reference_accessed": False,
    }
    seal_path.write_bytes(_canonical_json_bytes(seal))
    print(
        json.dumps(
            {
                "run_status": terminal["run_status"],
                "terminal": str(terminal_path),
                "seal": str(seal_path),
                "terminal_sha256": seal["terminal_sha256"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return exit_code


def _run_case(
    *,
    case: dict[str, Any],
    pdf_bytes: bytes,
    parse_result: Any,
    renderer: Any,
    provider: Any,
    output_dir: Path,
) -> dict[str, Any]:
    case_id = str(case["case_id"])
    page_number = int(case["page_number"])
    page_bbox = [float(value) for value in case["page_bbox_points"]]
    page = parse_result.pages[page_number - 1]
    if [float(page["width"]), float(page["height"])] != [page_bbox[2], page_bbox[3]]:
        raise BenchmarkError("benchmark_parser_page_identity_mismatch")

    case_dir = output_dir / "artifacts" / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    full_page = renderer.render_full_page(
        pdf_bytes=pdf_bytes,
        pdf_sha256=str(case["pdf_sha256"]),
        document_ref=case_id,
        page_ref=case_id,
        page_number=page_number,
        expected_page_bbox=page_bbox,
        dpi=int(case["render_dpi"]),
    )
    page_png = base64.b64decode(full_page["private_png_base64"])
    page_png_path = case_dir / "page.private.png"
    page_png_path.write_bytes(page_png)
    page_input = {
        "pdf_sha256": case["pdf_sha256"],
        "relative_pdf": case["relative_pdf"],
        "pdf_bytes": case["pdf_bytes"],
        "page_number": page_number,
        "page_bbox": page_bbox,
        "page_png_sha256": hashlib.sha256(page_png).hexdigest(),
        "page_png_bytes": len(page_png),
        "raster_manifest": full_page["manifest"],
        "word_inventory_total": len(page.get("word_inventory") or []),
    }

    direct_view = direct_page_model_view(
        case_id=case_id,
        page_number=page_number,
        input_image_sha256=hashlib.sha256(page_png).hexdigest(),
    )
    strategy_a_started = time.perf_counter()
    strategy_a_operation = _safe_provider_operation(
        provider=provider,
        task_id=f"{case_id}_strategy_a_direct",
        kind="direct_page_extraction",
        model_view=direct_view,
        output_schema=unified_extraction_schema(),
        png_bytes=page_png,
        artifact_dir=case_dir,
        artifact_stem="strategy_a_direct",
    )
    a_extraction = strategy_a_operation.get("json_output")
    a_errors = (
        validate_unified_extraction(a_extraction)
        if isinstance(a_extraction, dict)
        else ["benchmark_extraction_missing"]
    )
    strategy_a = {
        "status": "completed" if not a_errors else "contract_invalid",
        "extraction": a_extraction,
        "contract_errors": a_errors,
        "operations": [strategy_a_operation],
        "pipeline_duration_ms": round(
            (time.perf_counter() - strategy_a_started) * 1000
        ),
    }

    strategy_b_started = time.perf_counter()
    detect_view = detection_model_view(
        case_id=case_id,
        page_number=page_number,
        input_image_sha256=hashlib.sha256(page_png).hexdigest(),
    )
    detect_operation = _safe_provider_operation(
        provider=provider,
        task_id=f"{case_id}_strategy_b_detect",
        kind="table_region_detection",
        model_view=detect_view,
        output_schema=detection_schema(),
        png_bytes=page_png,
        artifact_dir=case_dir,
        artifact_stem="strategy_b_detection",
    )
    detection = detect_operation.get("json_output")
    detection_errors = (
        validate_detection_output(detection)
        if isinstance(detection, dict)
        else ["benchmark_detection_missing"]
    )
    b_operations = [detect_operation]
    b_tables: list[dict[str, Any]] = []
    b_document_uncertainty: list[str] = []
    b_errors = list(detection_errors)
    crop_manifests: list[dict[str, Any]] = []
    if not detection_errors:
        for region_index, region in enumerate(detection.get("regions") or [], start=1):
            detected_bbox = [float(value) for value in region["bbox"]]
            source_bbox = _normalized_to_source(detected_bbox, page_bbox)
            crop = renderer.render(
                pdf_bytes=pdf_bytes,
                pdf_sha256=str(case["pdf_sha256"]),
                document_ref=case_id,
                page_number=page_number,
                table_ref=f"{case_id}_detected_{region_index}",
                table_bbox=source_bbox,
                dpi=int(case["render_dpi"]),
            )
            crop_png = base64.b64decode(crop["private_png_base64"])
            crop_path = case_dir / f"strategy_b_crop_{region_index}.private.png"
            crop_path.write_bytes(crop_png)
            crop_manifests.append(crop["manifest"])
            crop_view = crop_extraction_model_view(
                case_id=case_id,
                page_number=page_number,
                region_index=region_index,
                input_image_sha256=hashlib.sha256(crop_png).hexdigest(),
            )
            operation = _safe_provider_operation(
                provider=provider,
                task_id=f"{case_id}_strategy_b_extract_{region_index}",
                kind="detected_crop_extraction",
                model_view=crop_view,
                output_schema=unified_extraction_schema(),
                png_bytes=crop_png,
                artifact_dir=case_dir,
                artifact_stem=f"strategy_b_extraction_{region_index}",
            )
            b_operations.append(operation)
            extracted = operation.get("json_output")
            errors = (
                validate_unified_extraction(extracted)
                if isinstance(extracted, dict)
                else ["benchmark_extraction_missing"]
            )
            b_errors.extend(f"region_{region_index}:{code}" for code in errors)
            if not errors:
                projected = project_crop_bbox_to_page(extracted, detected_bbox)
                b_tables.extend(copy.deepcopy(projected.get("tables") or []))
                b_document_uncertainty.extend(
                    str(value)
                    for value in projected.get("uncertainty_codes") or []
                )
    if b_errors:
        b_document_uncertainty.append("strategy_b_contract_invalid")
    b_extraction = {
        "schema_version": (
            UNIFIED_EXTRACTION_SCHEMA_VERSION
        ),
        "document_status": (
            ("partial" if b_errors else "completed")
            if b_tables
            else ("unsupported" if b_errors else "no_tables")
        ),
        "tables": b_tables,
        "uncertainty_codes": sorted(set(b_document_uncertainty)),
    }
    b_combined_errors = validate_unified_extraction(b_extraction)
    b_errors.extend(b_combined_errors)
    strategy_b = {
        "status": "completed" if not b_errors else "contract_invalid",
        "detection": detection,
        "extraction": b_extraction,
        "contract_errors": sorted(set(b_errors)),
        "crop_manifests": crop_manifests,
        "operations": b_operations,
        "pipeline_duration_ms": round(
            (time.perf_counter() - strategy_b_started) * 1000
        ),
    }

    c_extraction = copy.deepcopy(b_extraction)
    evidence_started = time.perf_counter()
    evidence = (
        validate_extraction_evidence(
            c_extraction,
            page.get("word_inventory") or [],
            page_width=float(page["width"]),
            page_height=float(page["height"]),
        )
        if not b_errors
        else None
    )
    evidence_duration_ms = round((time.perf_counter() - evidence_started) * 1000)
    strategy_c = {
        "status": "completed" if not b_errors else "upstream_contract_invalid",
        "extraction": c_extraction,
        "extraction_sha256": sha256_json(c_extraction),
        "evidence_validation": evidence,
        "replayed_from_strategy": "B",
        "reused_operations_from_strategy": "B",
        "replayed_extraction_sha256": sha256_json(b_extraction),
        "evidence_validation_duration_ms": evidence_duration_ms,
        "pipeline_duration_ms": (
            strategy_b["pipeline_duration_ms"] + evidence_duration_ms
        ),
        "provider_calls": 0,
        "operations": [],
    }
    return {
        "case_id": case_id,
        "broker": case["broker"],
        "categories": case["category_tags"],
        "page_bbox": page_bbox,
        "input": page_input,
        "strategies": {"A": strategy_a, "B": strategy_b, "C": strategy_c},
        "terminal_status": "completed",
    }


def _provider_operation(
    *,
    provider: Any,
    task_id: str,
    kind: str,
    model_view: dict[str, Any],
    output_schema: dict[str, Any],
    png_bytes: bytes,
    artifact_dir: Path,
    artifact_stem: str,
) -> dict[str, Any]:
    crop_sha = hashlib.sha256(png_bytes).hexdigest()
    model_view_path = artifact_dir / f"{artifact_stem}.model_view.json"
    model_view_path.write_bytes(_canonical_json_bytes(model_view))
    count = provider.count_tokens(
        model_view=model_view,
        output_schema=output_schema,
        png_bytes=png_bytes,
        crop_sha256=crop_sha,
    )
    result = provider.invoke(
        task_id=task_id,
        model_view=model_view,
        output_schema=output_schema,
        png_bytes=png_bytes,
        crop_sha256=crop_sha,
        attempt_number=1,
        attempt_lineage=[],
    )
    raw_path = artifact_dir / f"{artifact_stem}.provider_response.private.json"
    raw_path.write_bytes(_canonical_json_bytes(result.get("raw_private_response") or {}))
    output_path = artifact_dir / f"{artifact_stem}.extraction.private.json"
    output_path.write_bytes(_canonical_json_bytes(result.get("json_output")))
    attempt = _object(result.get("attempt") or {})
    if attempt.get("hidden_retry") is not False:
        raise BenchmarkError("benchmark_hidden_retry_detected")
    if attempt.get("provider_failover") is not False:
        raise BenchmarkError("benchmark_provider_failover_detected")
    return {
        "kind": kind,
        "task_id": task_id,
        "image_bytes": len(png_bytes),
        "model_view_bytes": len(_canonical_json_bytes(model_view)),
        "schema_bytes": len(_canonical_json_bytes(output_schema)),
        "count_tokens": count,
        "attempt": attempt,
        "response_bytes": result.get("response_bytes"),
        "response_hash": result.get("response_hash"),
        "visible_output_bytes": result.get("visible_output_bytes"),
        "visible_output_hash": result.get("visible_output_hash"),
        "json_output": result.get("json_output"),
        "artifact_paths": {
            "model_view": str(model_view_path.relative_to(artifact_dir.parents[1])),
            "provider_response_private": str(raw_path.relative_to(artifact_dir.parents[1])),
            "extraction_private": str(output_path.relative_to(artifact_dir.parents[1])),
        },
    }


def _safe_provider_operation(**kwargs: Any) -> dict[str, Any]:
    """Return a terminal operation even when one strategy call fails.

    A provider/counting failure in strategy A must not suppress strategy B on
    the same frozen input.  This wrapper does not retry or fail over.
    """

    try:
        return _provider_operation(**kwargs)
    except Exception as exc:
        return {
            "kind": kwargs["kind"],
            "task_id": kwargs["task_id"],
            "image_bytes": len(kwargs["png_bytes"]),
            "model_view_bytes": len(
                _canonical_json_bytes(kwargs["model_view"])
            ),
            "schema_bytes": len(
                _canonical_json_bytes(kwargs["output_schema"])
            ),
            "count_tokens": None,
            "attempt": None,
            "response_bytes": None,
            "response_hash": None,
            "visible_output_bytes": None,
            "visible_output_hash": None,
            "json_output": None,
            "artifact_paths": {},
            "failure_code": _error_code(
                exc, "benchmark_provider_operation_unexpected_failure"
            ),
            "hidden_retry": False,
            "provider_failover": False,
        }


def _prompt_contracts(manifest: dict[str, Any]) -> dict[str, Any]:
    cases = manifest["cases"]
    sample_case = str(cases[0]["case_id"])
    sample_page = int(cases[0]["page_number"])
    values = {
        "A": {
            "version": DIRECT_PAGE_MODEL_VIEW_VERSION,
            "model_view": direct_page_model_view(
                case_id=sample_case, page_number=sample_page
            ),
            "schema": unified_extraction_schema(),
        },
        "B_detection": {
            "version": DETECTION_MODEL_VIEW_VERSION,
            "model_view": detection_model_view(
                case_id=sample_case, page_number=sample_page
            ),
            "schema": detection_schema(),
        },
        "B_extraction": {
            "version": CROP_EXTRACTION_MODEL_VIEW_VERSION,
            "model_view": crop_extraction_model_view(
                case_id=sample_case, page_number=sample_page, region_index=1
            ),
            "schema": unified_extraction_schema(),
        },
    }
    return {
        key: {
            "version": value["version"],
            "model_view_sha256": sha256_json(value["model_view"]),
            "output_schema_sha256": sha256_json(value["schema"]),
        }
        for key, value in values.items()
    }


def _gate_command(args: argparse.Namespace) -> int:
    return run_gate_processes(
        manifest=Path(args.manifest).resolve(),
        corpus_root=Path(args.corpus_root).resolve(),
        output_root=Path(args.output_dir).resolve(),
        env_file=Path(args.env_file).resolve(),
        repo_root=Path(args.repo_root).resolve(),
        reference=Path(args.reference).resolve(),
        runner_script=SCRIPT_PATH,
        scorer_script=Path(args.scorer_script).resolve(),
    )


def run_gate_processes(
    *,
    manifest: Path,
    corpus_root: Path,
    output_root: Path,
    env_file: Path,
    repo_root: Path,
    reference: Path,
    runner_script: Path,
    scorer_script: Path,
) -> int:
    if output_root.exists() and any(output_root.iterdir()):
        print("benchmark_fresh_output_directory_required", file=sys.stderr)
        return 2
    output_root.mkdir(parents=True, exist_ok=True)
    run_dir = output_root / "run"
    terminal_path = run_dir / "terminal.private.json"
    seal_path = run_dir / "terminal.private.sha256.json"
    score_path = output_root / "score.json"
    run_command = [
        sys.executable,
        str(runner_script),
        "run",
        "--manifest",
        str(manifest),
        "--corpus-root",
        str(corpus_root),
        "--output-dir",
        str(run_dir),
        "--env-file",
        str(env_file),
        "--repo-root",
        str(repo_root),
    ]
    child_env = os.environ.copy()
    child_env["PYTHONIOENCODING"] = "utf-8"
    child_env["PYTHONUTF8"] = "1"
    run_process = subprocess.Popen(
        run_command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=child_env,
    )
    run_stdout, run_stderr = run_process.communicate()
    sealed = terminal_path.is_file() and seal_path.is_file()
    blockers: list[str] = []
    if run_process.returncode != 0:
        blockers.append("benchmark_runner_failed")
    if not sealed:
        blockers.append("benchmark_terminal_not_sealed")
    scorer_process: subprocess.Popen[str] | None = None
    scorer_stdout = ""
    scorer_stderr = ""
    score_command: list[str] = []
    if not blockers:
        score_command = [
            sys.executable,
            str(scorer_script),
            "--terminal",
            str(terminal_path),
            "--seal",
            str(seal_path),
            "--reference",
            str(reference),
            "--output",
            str(score_path),
        ]
        scorer_process = subprocess.Popen(
            score_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=child_env,
        )
        scorer_stdout, scorer_stderr = scorer_process.communicate()
    process = {
        "schema_version": PROCESS_SCHEMA,
        "gate_pid": os.getpid(),
        "run_pid": run_process.pid,
        "scorer_pid": scorer_process.pid if scorer_process else None,
        "run_returncode": run_process.returncode,
        "scorer_returncode": scorer_process.returncode if scorer_process else None,
        "run_stdout": run_stdout,
        "run_stderr": run_stderr,
        "scorer_stdout": scorer_stdout,
        "scorer_stderr": scorer_stderr,
        "terminal_sealed_before_scorer_started": sealed and scorer_process is not None,
        "separate_processes": (
            scorer_process is not None and scorer_process.pid != run_process.pid
        ),
        "reference_argument_passed_to_run": False,
        "reference_argument_passed_to_scorer": scorer_process is not None,
        "gate_blocker_codes": blockers,
        "run_command_argument_names": _argument_names(run_command),
        "score_command_argument_names": _argument_names(score_command),
    }
    (output_root / "gate_processes.safe.json").write_bytes(
        _canonical_json_bytes(process)
    )
    if blockers:
        return run_process.returncode or 1
    assert scorer_process is not None
    return int(scorer_process.returncode or 0)


def _validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise BenchmarkError("benchmark_manifest_schema_invalid")
    if (
        manifest.get("benchmark_id") != "pdf_table_strategy_v1"
        or manifest.get("frozen") is not True
        or manifest.get("case_count") != 8
    ):
        raise BenchmarkError("benchmark_manifest_identity_invalid")
    if _find_forbidden_reference_key(manifest):
        raise BenchmarkError("benchmark_manifest_reference_leakage")
    strategies = manifest.get("strategies")
    expected_strategies = [
        {
            "strategy_id": "A",
            "strategy_key": "direct_vlm_extraction",
            "prompt_contracts": [DIRECT_PAGE_MODEL_VIEW_VERSION],
        },
        {
            "strategy_id": "B",
            "strategy_key": "two_step_vlm_extraction",
            "prompt_contracts": [
                DETECTION_MODEL_VIEW_VERSION,
                CROP_EXTRACTION_MODEL_VIEW_VERSION,
            ],
        },
        {
            "strategy_id": "C",
            "strategy_key": "hybrid_evidence_validation",
            "prompt_contracts": [
                DETECTION_MODEL_VIEW_VERSION,
                CROP_EXTRACTION_MODEL_VIEW_VERSION,
            ],
        },
    ]
    if strategies != expected_strategies:
        raise BenchmarkError("benchmark_manifest_strategies_invalid")
    provider = _object(manifest.get("provider_contract"))
    if (
        provider.get("provider_profile") != "google_gemini"
        or provider.get("model_id") != "models/gemini-3.5-flash"
        or provider.get("maximum_counted_input_tokens") != 24_000
        or provider.get("maximum_output_tokens") != 16_384
    ):
        raise BenchmarkError("benchmark_manifest_provider_contract_invalid")
    if provider.get("hidden_retry") is not False:
        raise BenchmarkError("benchmark_manifest_hidden_retry_invalid")
    if provider.get("provider_failover") is not False:
        raise BenchmarkError("benchmark_manifest_provider_failover_invalid")
    pricing = _object(provider.get("pricing"))
    if pricing != {
        "currency": "USD",
        "input_usd_per_1m_tokens": 1.5,
        "output_usd_per_1m_tokens": 9.0,
        "effective_date": "2026-07-16",
        "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
    }:
        raise BenchmarkError("benchmark_manifest_pricing_contract_invalid")
    prompt_versions = _object(manifest.get("prompt_contract_versions"))
    required_versions = {
        "direct": DIRECT_PAGE_MODEL_VIEW_VERSION,
        "detection": DETECTION_MODEL_VIEW_VERSION,
        "crop": CROP_EXTRACTION_MODEL_VIEW_VERSION,
    }
    if prompt_versions != required_versions:
        raise BenchmarkError("benchmark_manifest_prompt_versions_invalid")
    scoring = _object(manifest.get("scoring_policy"))
    if float(scoring.get("detection_iou_threshold") or 0) != 0.5:
        raise BenchmarkError("benchmark_manifest_iou_threshold_invalid")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or len(cases) != 8:
        raise BenchmarkError("benchmark_manifest_case_count_invalid")
    case_ids: list[str] = []
    expected_case_ids = [
        "betterment_p02",
        "betterment_p04",
        "drivewealth_p07",
        "drivewealth_p09",
        "moomoo_annual_p14",
        "moomoo_midyear_p10",
        "ibkr_annual_p11",
        "ibkr_midyear_p03",
    ]
    required_brokers = {"betterment", "drivewealth", "moomoo", "ibkr"}
    for case in cases:
        if not isinstance(case, dict):
            raise BenchmarkError("benchmark_manifest_case_invalid")
        required = {
            "case_id",
            "broker",
            "relative_pdf",
            "pdf_sha256",
            "pdf_bytes",
            "page_number",
            "page_bbox_points",
            "render_dpi",
            "category_tags",
        }
        if not required.issubset(case):
            raise BenchmarkError("benchmark_manifest_case_invalid")
        if case["render_dpi"] != 150 or case["page_bbox_points"] != [
            0.0,
            0.0,
            612.0,
            792.0,
        ]:
            raise BenchmarkError("benchmark_manifest_render_contract_invalid")
        case_ids.append(str(case["case_id"]))
    if len(case_ids) != len(set(case_ids)):
        raise BenchmarkError("benchmark_manifest_case_duplicate")
    if case_ids != expected_case_ids:
        raise BenchmarkError("benchmark_manifest_case_set_invalid")
    if {str(case["broker"]) for case in cases} != required_brokers:
        raise BenchmarkError("benchmark_manifest_broker_coverage_invalid")
    category_coverage = {
        str(category)
        for case in cases
        for category in case.get("category_tags") or []
    }
    if not set(manifest.get("required_categories") or []).issubset(
        category_coverage
    ):
        raise BenchmarkError("benchmark_manifest_category_coverage_invalid")
    boundary = _object(manifest.get("reference_boundary"))
    if manifest.get("reference_access") != "forbidden" or boundary != {
        "runner_may_accept_reference_argument": False,
        "provider_may_receive_reference_data": False,
        "reference_may_be_opened_only_after_terminal_seal": True,
    }:
        raise BenchmarkError("benchmark_manifest_reference_boundary_invalid")


def _verify_sources(
    manifest: dict[str, Any], corpus_root: Path
) -> dict[str, Path]:
    result: dict[str, Path] = {}
    resolved_root = corpus_root.resolve()
    for case in manifest["cases"]:
        path = (resolved_root / str(case["relative_pdf"])).resolve()
        try:
            path.relative_to(resolved_root)
        except ValueError as exc:
            raise BenchmarkError("benchmark_source_path_escape") from exc
        if not path.is_file():
            raise BenchmarkError("benchmark_source_missing")
        payload = path.read_bytes()
        if len(payload) != int(case["pdf_bytes"]):
            raise BenchmarkError("benchmark_source_size_mismatch")
        if hashlib.sha256(payload).hexdigest() != str(case["pdf_sha256"]):
            raise BenchmarkError("benchmark_source_checksum_mismatch")
        result[str(case["case_id"])] = path
    return result


def _source_revision(repo_root: Path) -> dict[str, Any]:
    commit = _git(repo_root, "rev-parse", "HEAD")
    status = _git(repo_root, "status", "--porcelain")
    if status:
        raise BenchmarkError("benchmark_clean_worktree_required")
    return {
        "repository_commit_sha": commit,
        "worktree_clean": True,
        "branch": _git(repo_root, "branch", "--show-current"),
    }


def _openwebui_request(env_path: Path) -> Any:
    env = _read_env(env_path)
    host = str(
        env.get("OPENWEBUI_HOST")
        or env.get("OPENWEBUI_BASE_URL")
        or env.get("BASE_URL")
        or ""
    ).rstrip("/")
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
    if not all((host, email, password)):
        raise BenchmarkError("benchmark_openwebui_credentials_missing")
    base_url = host if host.startswith(("http://", "https://")) else f"https://{host}"
    session = requests.Session()
    response = session.post(
        base_url + "/api/v1/auths/signin",
        json={"email": email, "password": password},
        timeout=30,
    )
    response.raise_for_status()
    token = str(_object(response.json()).get("token") or "")
    if not token:
        raise BenchmarkError("benchmark_openwebui_token_missing")
    session.headers.update({"Authorization": f"Bearer {token}"})
    config_response = session.get(base_url + "/openai/config", timeout=30)
    config_response.raise_for_status()
    config = _object(config_response.json())
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                config=SimpleNamespace(
                    OPENAI_API_BASE_URLS=config.get("OPENAI_API_BASE_URLS"),
                    OPENAI_API_KEYS=config.get("OPENAI_API_KEYS"),
                    OPENAI_API_CONFIGS=config.get("OPENAI_API_CONFIGS"),
                )
            )
        )
    )


def _read_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise BenchmarkError("benchmark_env_file_missing")
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _failed_case(case: dict[str, Any], code: str) -> dict[str, Any]:
    empty = {
        "status": "failed",
        "extraction": None,
        "contract_errors": [code],
        "operations": [],
    }
    return {
        "case_id": case.get("case_id"),
        "broker": case.get("broker"),
        "categories": case.get("category_tags") or [],
        "page_bbox": case.get("page_bbox_points"),
        "input": None,
        "strategies": {
            "A": copy.deepcopy(empty),
            "B": {**copy.deepcopy(empty), "detection": None},
            "C": {
                **copy.deepcopy(empty),
                "evidence_validation": None,
                "replayed_from_strategy": "B",
                "provider_calls": 0,
            },
        },
        "terminal_status": "failed",
        "failure_code": code,
    }


def _normalized_to_source(
    bbox: list[float], page_bbox: list[float]
) -> list[float]:
    width = page_bbox[2] - page_bbox[0]
    height = page_bbox[3] - page_bbox[1]
    return [
        page_bbox[0] + bbox[0] * width,
        page_bbox[1] + bbox[1] * height,
        page_bbox[0] + bbox[2] * width,
        page_bbox[1] + bbox[3] * height,
    ]


def _find_forbidden_reference_key(value: Any) -> str | None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).strip().lower()
            if (
                normalized in FORBIDDEN_REFERENCE_KEYS
                or normalized.startswith("expected_")
                or normalized.endswith("_reference")
            ):
                return normalized
            found = _find_forbidden_reference_key(nested)
            if found:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _find_forbidden_reference_key(nested)
            if found:
                return found
    return None


def _argument_names(command: list[str]) -> list[str]:
    return [value for value in command if value.startswith("--")]


def _git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _json_object(value: bytes, code: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise BenchmarkError(code) from exc
    if not isinstance(parsed, dict):
        raise BenchmarkError(code)
    return parsed


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _error_code(exc: BaseException, fallback: str) -> str:
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code:
        return code
    if isinstance(exc, requests.RequestException):
        return "benchmark_openwebui_request_failed"
    return fallback


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
