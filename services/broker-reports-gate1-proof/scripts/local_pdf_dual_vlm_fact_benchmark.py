#!/usr/bin/env python3
"""Run and seal the reference-free dual-VLM financial-fact benchmark."""

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
    SERVICE_ROOT / "benchmarks" / "pdf_dual_vlm_fact_v1" / "manifest.json"
)
DEFAULT_CORPUS_ROOT = (
    DEFAULT_REPO_ROOT
    / "local"
    / "stage2"
    / "broker_reports_pdf_structural_holdout_public_v5_2026-07-15"
    / "corpus"
)
TERMINAL_SCHEMA_VERSION = "broker_reports_pdf_dual_vlm_fact_terminal_v1"
SEAL_SCHEMA_VERSION = "broker_reports_pdf_dual_vlm_fact_terminal_seal_v1"
EXPECTED_CASE_IDS = [
    "betterment_p02",
    "betterment_p04",
    "drivewealth_p07",
    "drivewealth_p09",
    "moomoo_annual_p14",
    "moomoo_midyear_p10",
    "ibkr_annual_p11",
    "ibkr_midyear_p03",
]
FORBIDDEN_REFERENCE_KEYS = {
    "accepted",
    "answer_key",
    "expected",
    "gold",
    "ground_truth",
    "human_reference",
    "label",
    "reference",
    "truth",
}
OPERATION_IDENTITIES = {
    "table_region_detection": {
        "provider": "google",
        "provider_profile": "google_gemini",
        "model": "models/gemini-3.5-flash",
    },
    "gemini_crop_financial_fact_extraction": {
        "provider": "google",
        "provider_profile": "google_gemini",
        "model": "models/gemini-3.5-flash",
    },
    "openai_crop_financial_fact_extraction": {
        "provider": "openai",
        "provider_profile": "openai_gpt",
        "model": "gpt-5.4-mini-2026-03-17",
    },
}


sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from broker_reports_gate1.pdf_table_raster import (  # noqa: E402
    PdfTableRasterConfig,
    PdfTableRasterFactory,
)
from broker_reports_gate1.pdf_text_layer import (  # noqa: E402
    PdfParserCapabilityRequest,
    PdfTextLayerParserFactory,
)
from pdf_dual_vlm_fact_contracts import (  # noqa: E402
    DETECTION_PROMPT_VERSION,
    FACT_PROMPT_VERSION,
    MANIFEST_SCHEMA_VERSION,
    AGREEMENT_STATUSES,
    build_crop_contract,
    canonical_json_bytes,
    compare_provider_facts,
    detection_model_view,
    detection_schema,
    fact_model_view,
    financial_fact_schema,
    normalized_to_source_bbox,
    sha256_json,
    validate_consensus,
    validate_crop_contract,
    validate_detection_output,
    validate_fact_extraction_output,
)
from pdf_dual_vlm_fact_evidence import (  # noqa: E402
    PdfDualVlmFactEvidenceFactory,
    validate_evidence_result,
)
from pdf_dual_vlm_fact_providers import (  # noqa: E402
    PdfDualVlmFactProviderConfig,
    PdfDualVlmFactProviderFactory,
)


class BenchmarkError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--corpus-root", default=str(DEFAULT_CORPUS_ROOT))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--env-file", default=str(DEFAULT_REPO_ROOT / ".env"))
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT))
    args = parser.parse_args(argv)
    return run(args)


def run(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        print("dual_vlm_fresh_output_directory_required", file=sys.stderr)
        return 2
    output_dir.mkdir(parents=True, exist_ok=True)
    terminal_path = output_dir / "terminal.private.json"
    seal_path = output_dir / "terminal.private.sha256.json"
    terminal: dict[str, Any] = {
        "schema_version": TERMINAL_SCHEMA_VERSION,
        "runner": {
            "pid": os.getpid(),
            "entrypoint": "local_pdf_dual_vlm_fact_benchmark.py",
            "reference_argument_supported": False,
            "provider_factory": ("PdfDualVlmFactProviderFactory.create_for_openwebui"),
            "raster_factory": "PdfTableRasterFactory.create",
            "parser_factory": "PdfTextLayerParserFactory.create(layout_words)",
            "evidence_factory": "PdfDualVlmFactEvidenceFactory.create",
        },
        "reference_accessed": False,
        "human_reference_available_to_runner": False,
        "production_authority": False,
        "production_pipeline_changed": False,
        "production_gate1_changed": False,
        "production_gate2_changed": False,
        "openwebui_core_changed": False,
        "knowledge_or_rag_used": False,
        "ocr_performed": False,
        "hidden_retry": False,
        "provider_failover": False,
        "third_llm_arbiter_used": False,
        "manifest_sha256": None,
        "target_manifest": None,
        "source_revision": {},
        "prompt_contracts": {},
        "provider_qualification": None,
        "parser_accounting": {
            "unique_documents": [],
            "total_duration_ms": 0,
            "table_construction_performed": False,
        },
        "cases": [],
        "failures": [],
        "run_status": "failed_before_execution",
    }
    exit_code = 1
    try:
        manifest_path = Path(args.manifest).resolve()
        manifest = _json_object(
            manifest_path.read_bytes(), "dual_vlm_manifest_json_invalid"
        )
        _validate_manifest(manifest)
        terminal["manifest_sha256"] = sha256_json(manifest)
        terminal["target_manifest"] = manifest
        terminal["source_revision"] = _source_revision(Path(args.repo_root).resolve())
        terminal["prompt_contracts"] = _prompt_contracts(manifest)
        sources = _verify_sources(manifest, Path(args.corpus_root).resolve())

        provider_contracts = _object(manifest["provider_contracts"])
        detector_contract = _object(provider_contracts["detection"])
        gemini_contract = _object(provider_contracts["gemini_extraction"])
        openai_contract = _object(provider_contracts["openai_extraction"])
        provider_bundle = PdfDualVlmFactProviderFactory(
            PdfDualVlmFactProviderConfig(
                gemini_model_id=str(gemini_contract["model_id"]),
                openai_model_id=str(openai_contract["model_id"]),
                detection_maximum_output_tokens=int(
                    detector_contract["maximum_output_tokens"]
                ),
                extraction_maximum_output_tokens=int(
                    gemini_contract["maximum_output_tokens"]
                ),
                maximum_counted_input_tokens=min(
                    int(detector_contract["maximum_counted_input_tokens"]),
                    int(gemini_contract["maximum_counted_input_tokens"]),
                    int(openai_contract["maximum_counted_input_tokens"]),
                ),
                gemini_thinking_level=str(
                    gemini_contract.get("thinking_level") or "minimal"
                ),
                openai_image_detail=str(openai_contract.get("image_detail") or "high"),
            )
        ).create_for_openwebui(_openwebui_request(Path(args.env_file).resolve()))
        qualification = provider_bundle.qualify()
        terminal["provider_qualification"] = qualification
        if any(
            _object(qualification.get(role)).get("status") != "qualified"
            for role in ("detector", "gemini", "openai")
        ):
            raise BenchmarkError("dual_vlm_provider_not_qualified")

        renderer = PdfTableRasterFactory(
            PdfTableRasterConfig(padding_points=0)
        ).create()
        parser = PdfTextLayerParserFactory().create(
            PdfParserCapabilityRequest(capability="layout_words")
        )
        evidence_verifier = PdfDualVlmFactEvidenceFactory().create()
        pdf_cache: dict[str, bytes] = {}
        parse_cache: dict[str, Any] = {}
        for case in manifest["cases"]:
            case_id = str(case["case_id"])
            try:
                pdf_sha = str(case["pdf_sha256"])
                if pdf_sha not in pdf_cache:
                    pdf_cache[pdf_sha] = sources[case_id].read_bytes()
                    started = time.perf_counter()
                    parse_cache[pdf_sha] = parser.parse(pdf_cache[pdf_sha])
                    duration_ms = round((time.perf_counter() - started) * 1000)
                    terminal["parser_accounting"]["unique_documents"].append(
                        {
                            "pdf_sha256": pdf_sha,
                            "pdf_bytes": len(pdf_cache[pdf_sha]),
                            "duration_ms": duration_ms,
                            "pages_parsed": len(parse_cache[pdf_sha].pages),
                            "capability": "layout_words",
                            "table_construction_performed": False,
                        }
                    )
                    terminal["parser_accounting"]["total_duration_ms"] += duration_ms
                case_result = _run_case(
                    case=case,
                    pdf_bytes=pdf_cache[pdf_sha],
                    parse_result=parse_cache[pdf_sha],
                    renderer=renderer,
                    detector=provider_bundle.detector,
                    gemini=provider_bundle.gemini,
                    openai=provider_bundle.openai,
                    evidence_verifier=evidence_verifier,
                    output_dir=output_dir,
                )
                terminal["cases"].append(case_result)
                terminal["failures"].extend(_case_terminal_failures(case_result))
            except Exception as exc:  # every case must be terminal
                code = _error_code(exc, "dual_vlm_case_unexpected_failure")
                terminal["cases"].append(_failed_case(case, code))
                terminal["failures"].append({"case_id": case_id, "code": code})
        terminal["run_status"] = (
            "completed" if not terminal["failures"] else "completed_with_failures"
        )
        exit_code = 0 if terminal["run_status"] == "completed" else 1
    except Exception as exc:
        terminal["failures"].append(
            {"case_id": None, "code": _error_code(exc, "dual_vlm_runner_failure")}
        )
        terminal["run_status"] = "failed_before_case_completion"

    _derive_terminal_execution_truth(terminal)
    terminal_bytes = canonical_json_bytes(terminal)
    terminal_path.write_bytes(terminal_bytes)
    seal = {
        "schema_version": SEAL_SCHEMA_VERSION,
        "terminal_sha256": hashlib.sha256(terminal_bytes).hexdigest(),
        "terminal_size_bytes": len(terminal_bytes),
        "reference_accessed": False,
    }
    seal_path.write_bytes(canonical_json_bytes(seal))
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
    detector: Any,
    gemini: Any,
    openai: Any,
    evidence_verifier: Any,
    output_dir: Path,
) -> dict[str, Any]:
    case_id = str(case["case_id"])
    page_number = int(case["page_number"])
    page_bbox = [float(item) for item in case["page_bbox_points"]]
    page = parse_result.pages[page_number - 1]
    if [float(page["width"]), float(page["height"])] != [page_bbox[2], page_bbox[3]]:
        raise BenchmarkError("dual_vlm_parser_page_identity_mismatch")

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
    page_png, page_manifest = _validated_raster_payload(
        full_page,
        expected_pdf_sha256=str(case["pdf_sha256"]),
        expected_page_number=page_number,
        expected_bbox=page_bbox,
        code_prefix="dual_vlm_page_raster",
    )
    page_sha = hashlib.sha256(page_png).hexdigest()
    page_path = case_dir / "page.private.png"
    page_path.write_bytes(page_png)
    detect_view = detection_model_view(
        document_id=case_id,
        page_number=page_number,
        page_image_sha256=page_sha,
    )
    detection_operation = _safe_provider_operation(
        provider=detector,
        task_id=f"{case_id}_detect",
        kind="table_region_detection",
        model_view=detect_view,
        output_schema=detection_schema(),
        png_bytes=page_png,
        artifact_dir=case_dir,
        artifact_stem="detection",
    )
    detection = detection_operation.get("json_output")
    detection_errors = validate_detection_output(
        detection,
        expected_document_id=case_id,
        expected_page_number=page_number,
    )
    if detection_operation.get("failure_code"):
        detection_errors.append(str(detection_operation["failure_code"]))
    crops: list[dict[str, Any]] = []
    if not detection_errors:
        for index, candidate in enumerate(detection.get("candidates") or [], start=1):
            if candidate.get("state") != "present":
                crops.append(_uncertain_candidate(candidate, index))
                continue
            try:
                crop = _run_crop(
                    case=case,
                    candidate=candidate,
                    region_index=index,
                    pdf_bytes=pdf_bytes,
                    page_png_sha256=page_sha,
                    page_bbox=page_bbox,
                    word_inventory=page.get("word_inventory") or [],
                    renderer=renderer,
                    gemini=gemini,
                    openai=openai,
                    evidence_verifier=evidence_verifier,
                    case_dir=case_dir,
                )
            except Exception as exc:
                crop = _failed_crop(
                    candidate,
                    index,
                    _error_code(exc, "dual_vlm_crop_unexpected_failure"),
                )
            crops.append(crop)
    crop_failed = any(
        isinstance(crop, dict)
        and crop.get("terminal_status") not in {"completed", "uncertain_not_extracted"}
        for crop in crops
    )
    return {
        "case_id": case_id,
        "broker": case["broker"],
        "categories": case["category_tags"],
        "input": {
            "pdf_sha256": case["pdf_sha256"],
            "pdf_bytes": case["pdf_bytes"],
            "relative_pdf": case["relative_pdf"],
            "page_number": page_number,
            "page_bbox_points": page_bbox,
            "page_png_sha256": page_sha,
            "page_png_bytes": len(page_png),
            "page_artifact": str(page_path.relative_to(output_dir)),
            "page_raster_manifest": page_manifest,
            "word_inventory_total": len(page.get("word_inventory") or []),
        },
        "detection": {
            "status": "completed" if not detection_errors else "contract_invalid",
            "output": detection,
            "contract_errors": sorted(set(detection_errors)),
            "operation": detection_operation,
        },
        "crops": crops,
        "terminal_status": (
            "detection_invalid"
            if detection_errors
            else "completed_with_crop_failures"
            if crop_failed
            else "completed"
        ),
    }


def _run_crop(
    *,
    case: dict[str, Any],
    candidate: dict[str, Any],
    region_index: int,
    pdf_bytes: bytes,
    page_png_sha256: str,
    page_bbox: list[float],
    word_inventory: list[dict[str, Any]],
    renderer: Any,
    gemini: Any,
    openai: Any,
    evidence_verifier: Any,
    case_dir: Path,
) -> dict[str, Any]:
    case_id = str(case["case_id"])
    normalized_bbox = [float(item) for item in candidate["bbox"]]
    source_bbox = normalized_to_source_bbox(normalized_bbox, page_bbox)
    table_ref = f"{case_id}_candidate_{region_index}"
    render_kwargs = {
        "pdf_bytes": pdf_bytes,
        "pdf_sha256": str(case["pdf_sha256"]),
        "document_ref": case_id,
        "page_number": int(case["page_number"]),
        "table_ref": table_ref,
        "table_bbox": source_bbox,
        "dpi": int(case["render_dpi"]),
    }
    first = renderer.render(**render_kwargs)
    second = renderer.render(**render_kwargs)
    first_png, first_manifest = _validated_raster_payload(
        first,
        expected_pdf_sha256=str(case["pdf_sha256"]),
        expected_page_number=int(case["page_number"]),
        expected_bbox=source_bbox,
        code_prefix="dual_vlm_crop_raster",
    )
    second_png, second_manifest = _validated_raster_payload(
        second,
        expected_pdf_sha256=str(case["pdf_sha256"]),
        expected_page_number=int(case["page_number"]),
        expected_bbox=source_bbox,
        code_prefix="dual_vlm_crop_raster",
    )
    reproducible = first_png == second_png and first_manifest == second_manifest
    if not reproducible:
        raise BenchmarkError("dual_vlm_crop_not_reproducible")
    crop_sha = hashlib.sha256(first_png).hexdigest()
    crop_contract = build_crop_contract(
        document_id=case_id,
        page_image_sha256=page_png_sha256,
        normalized_bbox=normalized_bbox,
        raster_manifest=first_manifest,
    )
    crop_errors = validate_crop_contract(crop_contract)
    if crop_errors:
        raise BenchmarkError(crop_errors[0])
    _validate_crop_contract_binding(
        crop_contract,
        expected_document_id=case_id,
        expected_pdf_sha256=str(case["pdf_sha256"]),
        expected_page_number=int(case["page_number"]),
        expected_page_image_sha256=page_png_sha256,
        expected_normalized_bbox=normalized_bbox,
        expected_source_bbox=source_bbox,
        expected_png_bytes=len(first_png),
        expected_png_sha256=crop_sha,
        expected_crop_id=str(first_manifest["crop_id"]),
        expected_raster_manifest_hash=str(first_manifest["manifest_hash"]),
    )
    crop_id = str(crop_contract["crop_id"])
    crop_path = case_dir / f"crop_{region_index}.private.png"
    crop_path.write_bytes(first_png)
    contract_path = case_dir / f"crop_{region_index}.contract.json"
    contract_path.write_bytes(canonical_json_bytes(crop_contract))
    identity = {
        "document_id": case_id,
        "page_number": int(case["page_number"]),
        "crop_id": crop_id,
        "crop_sha256": crop_sha,
    }
    model_view = fact_model_view(**identity)
    schema = financial_fact_schema()
    gemini_operation = _safe_provider_operation(
        provider=gemini,
        task_id=f"{table_ref}_gemini",
        kind="gemini_crop_financial_fact_extraction",
        model_view=model_view,
        output_schema=schema,
        png_bytes=first_png,
        artifact_dir=case_dir,
        artifact_stem=f"crop_{region_index}_gemini",
    )
    openai_operation = _safe_provider_operation(
        provider=openai,
        task_id=f"{table_ref}_openai",
        kind="openai_crop_financial_fact_extraction",
        model_view=model_view,
        output_schema=schema,
        png_bytes=first_png,
        artifact_dir=case_dir,
        artifact_stem=f"crop_{region_index}_openai",
    )
    gemini_output = gemini_operation.get("json_output")
    openai_output = openai_operation.get("json_output")
    gemini_errors = validate_fact_extraction_output(
        gemini_output, expected_identity=identity
    )
    openai_errors = validate_fact_extraction_output(
        openai_output, expected_identity=identity
    )
    if gemini_operation.get("failure_code"):
        gemini_errors.append(str(gemini_operation["failure_code"]))
    if openai_operation.get("failure_code"):
        openai_errors.append(str(openai_operation["failure_code"]))
    consensus = None
    evidence = None
    consensus_errors: list[str] = []
    evidence_errors: list[str] = []
    evidence_medium = _evidence_medium(
        case.get("category_tags") or [], word_inventory, source_bbox
    )
    if not gemini_errors and not openai_errors:
        try:
            consensus = compare_provider_facts(gemini_output, openai_output)
            consensus_errors.extend(validate_consensus(consensus))
        except Exception as exc:
            consensus_errors.append(
                _error_code(exc, "dual_vlm_consensus_unexpected_failure")
            )
        if not consensus_errors and consensus is not None:
            evidence_facts = [
                copy.deepcopy(entry)
                for entry in consensus["entries"]
                if entry.get("status") in AGREEMENT_STATUSES
                and isinstance(entry.get("canonical_fact"), dict)
            ]
            try:
                evidence = evidence_verifier.verify(
                    consensus_facts=evidence_facts,
                    word_inventory=word_inventory,
                    crop_contract=crop_contract,
                    page_width=float(page_bbox[2]),
                    page_height=float(page_bbox[3]),
                    medium=evidence_medium,
                )
                evidence_errors.extend(validate_evidence_result(evidence))
            except Exception as exc:
                evidence_errors.append(
                    _error_code(exc, "dual_vlm_evidence_unexpected_failure")
                )
    if gemini_errors or openai_errors:
        terminal_status = "provider_contract_invalid"
    elif consensus_errors:
        terminal_status = "consensus_invalid"
    elif evidence_errors:
        terminal_status = "evidence_invalid"
    else:
        terminal_status = "completed"
    return {
        "candidate": copy.deepcopy(candidate),
        "candidate_index": region_index,
        "crop_contract": crop_contract,
        "crop_reproducibility": {
            "renders": 2,
            "byte_identical": reproducible,
            "first_sha256": crop_sha,
            "second_sha256": hashlib.sha256(second_png).hexdigest(),
        },
        "crop_artifact": str(crop_path.relative_to(case_dir.parents[1])),
        "crop_contract_artifact": str(contract_path.relative_to(case_dir.parents[1])),
        "same_crop_sha256_for_both_extractors": (
            _operation_crop_sha(gemini_operation) == crop_sha
            and _operation_crop_sha(openai_operation) == crop_sha
        ),
        "evidence_medium": evidence_medium,
        "gemini": {
            "status": "completed" if not gemini_errors else "contract_invalid",
            "output": gemini_output,
            "contract_errors": sorted(set(gemini_errors)),
            "operation": gemini_operation,
        },
        "openai": {
            "status": "completed" if not openai_errors else "contract_invalid",
            "output": openai_output,
            "contract_errors": sorted(set(openai_errors)),
            "operation": openai_operation,
        },
        "consensus": consensus,
        "consensus_contract_errors": sorted(set(consensus_errors)),
        "evidence": evidence,
        "evidence_contract_errors": sorted(set(evidence_errors)),
        "runtime_acceptance_used_human_reference": False,
        "terminal_status": terminal_status,
    }


def _validated_raster_payload(
    value: Any,
    *,
    expected_pdf_sha256: str,
    expected_page_number: int,
    expected_bbox: list[float],
    code_prefix: str,
) -> tuple[bytes, dict[str, Any]]:
    if not isinstance(value, dict) or not isinstance(value.get("manifest"), dict):
        raise BenchmarkError(f"{code_prefix}_result_invalid")
    encoded = value.get("private_png_base64")
    if not isinstance(encoded, str):
        raise BenchmarkError(f"{code_prefix}_bytes_missing")
    try:
        png_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise BenchmarkError(f"{code_prefix}_base64_invalid") from exc
    manifest = copy.deepcopy(value["manifest"])
    unsigned_manifest = copy.deepcopy(manifest)
    manifest_hash = unsigned_manifest.pop("manifest_hash", None)
    if not _sha256_text(manifest_hash) or manifest_hash != sha256_json(
        unsigned_manifest
    ):
        raise BenchmarkError(f"{code_prefix}_manifest_checksum_mismatch")
    png_sha256 = hashlib.sha256(png_bytes).hexdigest()
    if manifest.get("png_sha256") != png_sha256 or manifest.get("png_bytes") != len(
        png_bytes
    ):
        raise BenchmarkError(f"{code_prefix}_png_identity_mismatch")
    dimensions = _png_dimensions(png_bytes)
    if dimensions != (manifest.get("width"), manifest.get("height")):
        raise BenchmarkError(f"{code_prefix}_png_dimensions_mismatch")
    expected = [round(float(item), 6) for item in expected_bbox]
    if (
        manifest.get("pdf_sha256") != expected_pdf_sha256
        or manifest.get("page_number") != expected_page_number
    ):
        raise BenchmarkError(f"{code_prefix}_source_identity_mismatch")
    if (
        manifest.get("declared_table_bbox") != expected
        or manifest.get("rendered_bbox") != expected
    ):
        raise BenchmarkError(f"{code_prefix}_bbox_identity_mismatch")
    if (
        manifest.get("padding_points") != 0
        or manifest.get("lossless") is not True
        or manifest.get("silent_resize_performed") is not False
    ):
        raise BenchmarkError(f"{code_prefix}_immutability_invalid")
    if not _source_to_pixel_transform_matches(
        manifest.get("source_to_pixel_transform"),
        expected_bbox=expected,
        width=int(dimensions[0]),
        height=int(dimensions[1]),
    ):
        raise BenchmarkError(f"{code_prefix}_transform_identity_mismatch")
    return png_bytes, manifest


def _validate_crop_contract_binding(
    value: dict[str, Any],
    *,
    expected_document_id: str,
    expected_pdf_sha256: str,
    expected_page_number: int,
    expected_page_image_sha256: str,
    expected_normalized_bbox: list[float],
    expected_source_bbox: list[float],
    expected_png_bytes: int,
    expected_png_sha256: str,
    expected_crop_id: str,
    expected_raster_manifest_hash: str,
) -> None:
    expected_normalized = [round(float(item), 9) for item in expected_normalized_bbox]
    expected_source = [round(float(item), 6) for item in expected_source_bbox]
    if (
        value.get("document_id") != expected_document_id
        or value.get("pdf_sha256") != expected_pdf_sha256
        or value.get("page_number") != expected_page_number
        or value.get("page_image_sha256") != expected_page_image_sha256
        or value.get("crop_id") != expected_crop_id
    ):
        raise BenchmarkError("dual_vlm_crop_contract_source_identity_mismatch")
    if (
        value.get("normalized_bbox") != expected_normalized
        or value.get("source_bbox_points") != expected_source
        or value.get("rendered_bbox_points") != expected_source
    ):
        raise BenchmarkError("dual_vlm_crop_contract_bbox_identity_mismatch")
    if (
        value.get("rendered_image_bytes") != expected_png_bytes
        or value.get("rendered_image_sha256") != expected_png_sha256
    ):
        raise BenchmarkError("dual_vlm_crop_contract_png_identity_mismatch")
    if value.get("raster_manifest_hash") != expected_raster_manifest_hash:
        raise BenchmarkError("dual_vlm_crop_contract_manifest_identity_mismatch")
    unsigned = copy.deepcopy(value)
    checksum = unsigned.pop("contract_checksum", None)
    if not _sha256_text(checksum) or checksum != sha256_json(unsigned):
        raise BenchmarkError("dual_vlm_crop_contract_checksum_invalid")


def _png_dimensions(value: bytes) -> tuple[int, int]:
    if len(value) < 24 or value[:8] != b"\x89PNG\r\n\x1a\n" or value[12:16] != b"IHDR":
        raise BenchmarkError("dual_vlm_raster_png_invalid")
    width = int.from_bytes(value[16:20], "big")
    height = int.from_bytes(value[20:24], "big")
    if width <= 0 or height <= 0:
        raise BenchmarkError("dual_vlm_raster_png_dimensions_invalid")
    return width, height


def _source_to_pixel_transform_matches(
    value: Any,
    *,
    expected_bbox: list[float],
    width: int,
    height: int,
) -> bool:
    if not isinstance(value, dict):
        return False
    bbox_width = expected_bbox[2] - expected_bbox[0]
    bbox_height = expected_bbox[3] - expected_bbox[1]
    expected = {
        "scale_x": round(width / bbox_width, 9),
        "scale_y": round(height / bbox_height, 9),
        "translate_source_x": round(-expected_bbox[0], 9),
        "translate_source_y": round(-expected_bbox[1], 9),
    }
    return value == expected


def _evidence_medium(
    categories: list[str],
    word_inventory: list[dict[str, Any]],
    source_bbox: list[float],
) -> str:
    scoped = [
        word
        for word in word_inventory
        if isinstance(word, dict)
        and _point_bbox(word.get("bbox"))
        and _center_inside(word["bbox"], source_bbox)
    ]
    raster_tagged = bool({"raster_image", "without_text_layer"} & set(categories))
    if not scoped:
        return "raster" if raster_tagged else "text_layer"
    return "mixed" if raster_tagged else "text_layer"


def _point_bbox(value: Any) -> bool:
    return bool(
        isinstance(value, (list, tuple))
        and len(value) == 4
        and all(isinstance(item, (int, float)) for item in value)
    )


def _center_inside(value: list[float], scope: list[float]) -> bool:
    x = (float(value[0]) + float(value[2])) / 2
    y = (float(value[1]) + float(value[3])) / 2
    return scope[0] <= x <= scope[2] and scope[1] <= y <= scope[3]


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
    if _find_forbidden_reference_key(model_view):
        raise BenchmarkError("dual_vlm_model_view_reference_leak")
    crop_sha = hashlib.sha256(png_bytes).hexdigest()
    operation = _empty_provider_operation(
        kind=kind,
        task_id=task_id,
        png_bytes=png_bytes,
        model_view=model_view,
        output_schema=output_schema,
    )
    model_view_path = artifact_dir / f"{artifact_stem}.model_view.json"
    model_view_path.write_bytes(canonical_json_bytes(model_view))
    operation["artifact_paths"]["model_view"] = str(
        model_view_path.relative_to(artifact_dir.parents[1])
    )
    accounting = _object(operation["call_accounting"])
    accounting["count_or_preflight_calls_attempted"] = 1
    try:
        count = provider.count_tokens(
            model_view=model_view,
            output_schema=output_schema,
            png_bytes=png_bytes,
            crop_sha256=crop_sha,
        )
    except Exception as exc:
        operation["failure_code"] = _error_code(
            exc, "dual_vlm_provider_count_unexpected_failure"
        )
        return operation
    accounting["count_or_preflight_calls_completed"] = 1
    operation["count_tokens"] = count
    count_errors = _count_provenance_errors(
        count,
        kind=kind,
        output_schema=output_schema,
    )
    if count_errors:
        operation["provenance_errors"] = count_errors
        operation["failure_code"] = count_errors[0]
        return operation

    accounting["generate_calls_attempted"] = 1
    try:
        result = provider.invoke(
            task_id=task_id,
            model_view=model_view,
            output_schema=output_schema,
            png_bytes=png_bytes,
            crop_sha256=crop_sha,
            attempt_number=1,
            attempt_lineage=[],
        )
    except Exception as exc:
        operation["hidden_retry"] = None
        operation["provider_failover"] = None
        operation["failure_code"] = _error_code(
            exc, "dual_vlm_provider_generate_unexpected_failure"
        )
        return operation
    accounting["generate_calls_completed"] = 1
    if not isinstance(result, dict):
        operation["hidden_retry"] = None
        operation["provider_failover"] = None
        operation["failure_code"] = "dual_vlm_provider_result_not_object"
        return operation

    attempt = _object(result.get("attempt"))
    operation.update(
        {
            "attempt": attempt or None,
            "response_bytes": result.get("response_bytes"),
            "response_hash": result.get("response_hash"),
            "visible_output_bytes": result.get("visible_output_bytes"),
            "visible_output_hash": result.get("visible_output_hash"),
            "json_output": result.get("json_output"),
            "hidden_retry": (
                attempt.get("hidden_retry")
                if isinstance(attempt.get("hidden_retry"), bool)
                else None
            ),
            "provider_failover": (
                attempt.get("provider_failover")
                if isinstance(attempt.get("provider_failover"), bool)
                else None
            ),
        }
    )
    provenance_errors = _attempt_provenance_errors(
        attempt,
        task_id=task_id,
        kind=kind,
        crop_sha256=crop_sha,
        model_view=model_view,
        output_schema=output_schema,
        count=count,
    )
    operation["provenance_errors"] = provenance_errors
    operation["provenance_verified"] = not provenance_errors
    if provenance_errors:
        operation["failure_code"] = provenance_errors[0]
    elif attempt.get("terminal_failure_class") is not None:
        operation["failure_code"] = "dual_vlm_provider_terminal_failure"

    raw_path = artifact_dir / f"{artifact_stem}.provider_response.private.json"
    output_path = artifact_dir / f"{artifact_stem}.output.private.json"
    try:
        raw_path.write_bytes(
            canonical_json_bytes(result.get("raw_private_response") or {})
        )
        output_path.write_bytes(canonical_json_bytes(result.get("json_output")))
    except Exception as exc:
        operation.setdefault(
            "failure_code",
            _error_code(exc, "dual_vlm_provider_artifact_write_failure"),
        )
        return operation
    operation["artifact_paths"].update(
        {
            "provider_response_private": str(
                raw_path.relative_to(artifact_dir.parents[1])
            ),
            "output_private": str(output_path.relative_to(artifact_dir.parents[1])),
        }
    )
    return operation


def _safe_provider_operation(**kwargs: Any) -> dict[str, Any]:
    try:
        return _provider_operation(**kwargs)
    except Exception as exc:
        operation = _empty_provider_operation(
            kind=kwargs["kind"],
            task_id=kwargs["task_id"],
            png_bytes=kwargs["png_bytes"],
            model_view=kwargs["model_view"],
            output_schema=kwargs["output_schema"],
        )
        operation["failure_code"] = _error_code(
            exc, "dual_vlm_provider_operation_unexpected_failure"
        )
        return operation


def _empty_provider_operation(
    *,
    kind: str,
    task_id: str,
    png_bytes: bytes,
    model_view: dict[str, Any],
    output_schema: dict[str, Any],
) -> dict[str, Any]:
    return {
        "kind": kind,
        "task_id": task_id,
        "image_bytes": len(png_bytes),
        "model_view_bytes": len(canonical_json_bytes(model_view)),
        "schema_bytes": len(canonical_json_bytes(output_schema)),
        "count_tokens": None,
        "attempt": None,
        "response_bytes": None,
        "response_hash": None,
        "visible_output_bytes": None,
        "visible_output_hash": None,
        "json_output": None,
        "artifact_paths": {},
        "call_accounting": {
            "count_or_preflight_calls_attempted": 0,
            "count_or_preflight_calls_completed": 0,
            "generate_calls_attempted": 0,
            "generate_calls_completed": 0,
        },
        "hidden_retry": False,
        "provider_failover": False,
        "provenance_verified": False,
        "provenance_errors": [],
    }


def _count_provenance_errors(
    value: Any,
    *,
    kind: str,
    output_schema: dict[str, Any],
) -> list[str]:
    identity = OPERATION_IDENTITIES.get(kind)
    if identity is None:
        return []
    if not isinstance(value, dict):
        return ["dual_vlm_count_result_not_object"]
    errors: list[str] = []
    if value.get("model_requested") != identity["model"]:
        errors.append("dual_vlm_count_model_identity_mismatch")
    if value.get("canonical_schema_hash") != sha256_json(output_schema):
        errors.append("dual_vlm_count_schema_identity_mismatch")
    if not _sha256_text(value.get("adapted_schema_hash")):
        errors.append("dual_vlm_count_adapted_schema_hash_invalid")
    transforms = value.get("schema_transform_count")
    if (
        not isinstance(transforms, int)
        or isinstance(transforms, bool)
        or transforms < 0
    ):
        errors.append("dual_vlm_count_schema_transform_invalid")
    tokens = value.get("total_tokens")
    if not isinstance(tokens, int) or isinstance(tokens, bool) or tokens < 0:
        errors.append("dual_vlm_count_tokens_invalid")
    if value.get("within_hard_guard") is not True:
        errors.append("dual_vlm_count_hard_guard_invalid")
    for key in ("request_hash", "response_hash"):
        if not _sha256_text(value.get(key)):
            errors.append(f"dual_vlm_count_{key}_invalid")
    return sorted(set(errors))


def _attempt_provenance_errors(
    attempt: dict[str, Any],
    *,
    task_id: str,
    kind: str,
    crop_sha256: str,
    model_view: dict[str, Any],
    output_schema: dict[str, Any],
    count: dict[str, Any],
) -> list[str]:
    identity = OPERATION_IDENTITIES.get(kind)
    if identity is None:
        return ["dual_vlm_operation_kind_unknown"]
    if not attempt:
        return ["dual_vlm_attempt_missing"]
    errors: list[str] = []
    if (
        attempt.get("task_id") != task_id
        or attempt.get("attempt_id") != f"{task_id}_a1"
    ):
        errors.append("dual_vlm_attempt_task_identity_mismatch")
    if attempt.get("attempt_number") != 1 or attempt.get("attempt_lineage") != []:
        errors.append("dual_vlm_attempt_lineage_invalid")
    if (
        attempt.get("provider") != identity["provider"]
        or attempt.get("provider_profile") != identity["provider_profile"]
    ):
        errors.append("dual_vlm_attempt_provider_identity_mismatch")
    if (
        attempt.get("model_requested") != identity["model"]
        or attempt.get("model_resolved") != identity["model"]
    ):
        errors.append("dual_vlm_attempt_model_identity_mismatch")
    if attempt.get("crop_sha256") != crop_sha256:
        errors.append("dual_vlm_attempt_crop_identity_mismatch")
    if attempt.get("model_view_hash") != sha256_json(model_view):
        errors.append("dual_vlm_attempt_model_view_identity_mismatch")
    if attempt.get("canonical_schema_hash") != sha256_json(output_schema):
        errors.append("dual_vlm_attempt_schema_identity_mismatch")
    if attempt.get("adapted_schema_hash") != count.get("adapted_schema_hash"):
        errors.append("dual_vlm_attempt_adapted_schema_identity_mismatch")
    if attempt.get("schema_transform_count") != count.get("schema_transform_count"):
        errors.append("dual_vlm_attempt_schema_transform_mismatch")
    if not _sha256_text(attempt.get("request_hash")):
        errors.append("dual_vlm_attempt_request_hash_invalid")
    if not isinstance(attempt.get("adapter_identity"), str) or not attempt.get(
        "adapter_identity"
    ):
        errors.append("dual_vlm_attempt_adapter_identity_invalid")
    if not isinstance(attempt.get("transport_identity"), str) or not attempt.get(
        "transport_identity"
    ):
        errors.append("dual_vlm_attempt_transport_identity_invalid")
    if attempt.get("hidden_retry") is not False:
        errors.append("dual_vlm_hidden_retry_detected")
    if attempt.get("provider_failover") is not False:
        errors.append("dual_vlm_provider_failover_detected")
    return sorted(set(errors))


def _operation_crop_sha(operation: dict[str, Any]) -> str | None:
    return str(_object(operation.get("attempt")).get("crop_sha256") or "") or None


def _uncertain_candidate(candidate: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "candidate": copy.deepcopy(candidate),
        "candidate_index": index,
        "terminal_status": "uncertain_not_extracted",
        "reason": "detector_candidate_uncertain",
    }


def _failed_crop(candidate: dict[str, Any], index: int, code: str) -> dict[str, Any]:
    return {
        "candidate": copy.deepcopy(candidate),
        "candidate_index": index,
        "crop_contract": None,
        "crop_reproducibility": None,
        "crop_artifact": None,
        "crop_contract_artifact": None,
        "same_crop_sha256_for_both_extractors": False,
        "evidence_medium": None,
        "gemini": None,
        "openai": None,
        "consensus": None,
        "consensus_contract_errors": [],
        "evidence": None,
        "evidence_contract_errors": [],
        "runtime_acceptance_used_human_reference": False,
        "terminal_status": "failed",
        "failure_code": code,
    }


def _case_terminal_failures(case: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    detection = _object(case.get("detection"))
    if detection.get("status") != "completed":
        errors = detection.get("contract_errors") or []
        failures.append(
            {
                "case_id": case.get("case_id"),
                "candidate_index": None,
                "code": str(
                    errors[0] if errors else "dual_vlm_detection_terminal_failure"
                ),
            }
        )
    for crop in case.get("crops") or []:
        if not isinstance(crop, dict) or crop.get("terminal_status") in {
            "completed",
            "uncertain_not_extracted",
        }:
            continue
        failures.append(
            {
                "case_id": case.get("case_id"),
                "candidate_index": crop.get("candidate_index"),
                "code": _crop_failure_code(crop),
            }
        )
    return failures


def _crop_failure_code(crop: dict[str, Any]) -> str:
    if crop.get("failure_code"):
        return str(crop["failure_code"])
    for arm in ("gemini", "openai"):
        value = _object(crop.get(arm))
        operation = _object(value.get("operation"))
        if operation.get("failure_code"):
            return str(operation["failure_code"])
        errors = value.get("contract_errors") or []
        if errors:
            return str(errors[0])
    for key in ("consensus_contract_errors", "evidence_contract_errors"):
        errors = crop.get(key) or []
        if errors:
            return str(errors[0])
    return "dual_vlm_crop_terminal_failure"


def _derive_terminal_execution_truth(terminal: dict[str, Any]) -> None:
    operations: list[dict[str, Any]] = []
    for case in terminal.get("cases") or []:
        if not isinstance(case, dict):
            continue
        detection = _object(_object(case.get("detection")).get("operation"))
        if detection:
            operations.append(detection)
        for crop in case.get("crops") or []:
            if not isinstance(crop, dict):
                continue
            for arm in ("gemini", "openai"):
                operation = _object(_object(crop.get(arm)).get("operation"))
                if operation:
                    operations.append(operation)
    terminal["hidden_retry"] = _aggregate_operation_truth(
        [operation.get("hidden_retry") for operation in operations]
    )
    terminal["provider_failover"] = _aggregate_operation_truth(
        [operation.get("provider_failover") for operation in operations]
    )
    totals = {
        "provider_operations": len(operations),
        "count_or_preflight_calls_attempted": 0,
        "count_or_preflight_calls_completed": 0,
        "generate_calls_attempted": 0,
        "generate_calls_completed": 0,
    }
    for operation in operations:
        accounting = _object(operation.get("call_accounting"))
        for key in tuple(totals)[1:]:
            value = accounting.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                totals[key] += value
    terminal["execution_call_accounting"] = totals


def _aggregate_operation_truth(values: list[Any]) -> bool | None:
    if any(value is True for value in values):
        return True
    if any(value is None for value in values):
        return None
    return False


def _failed_case(case: dict[str, Any], code: str) -> dict[str, Any]:
    return {
        "case_id": case.get("case_id"),
        "broker": case.get("broker"),
        "categories": case.get("category_tags") or [],
        "input": None,
        "detection": {
            "status": "failed",
            "output": None,
            "contract_errors": [code],
            "operation": None,
        },
        "crops": [],
        "terminal_status": "failed",
        "failure_code": code,
    }


def _prompt_contracts(manifest: dict[str, Any]) -> dict[str, Any]:
    case = manifest["cases"][0]
    detection = {
        "version": DETECTION_PROMPT_VERSION,
        "model_view": detection_model_view(
            document_id=str(case["case_id"]),
            page_number=int(case["page_number"]),
            page_image_sha256="0" * 64,
        ),
        "schema": detection_schema(),
    }
    fact = {
        "version": FACT_PROMPT_VERSION,
        "model_view": fact_model_view(
            document_id=str(case["case_id"]),
            page_number=int(case["page_number"]),
            crop_id="frozen_contract_sample",
            crop_sha256="0" * 64,
        ),
        "schema": financial_fact_schema(),
    }
    for value in (detection, fact):
        value["model_view_sha256"] = sha256_json(value["model_view"])
        value["schema_sha256"] = sha256_json(value["schema"])
    return {"detection": detection, "fact_extraction": fact}


def _validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise BenchmarkError("dual_vlm_manifest_schema_invalid")
    if (
        manifest.get("benchmark_id") != "pdf_dual_vlm_fact_v1"
        or manifest.get("frozen") is not True
    ):
        raise BenchmarkError("dual_vlm_manifest_identity_invalid")
    cases = manifest.get("cases")
    if (
        not isinstance(cases, list)
        or [item.get("case_id") for item in cases if isinstance(item, dict)]
        != EXPECTED_CASE_IDS
    ):
        raise BenchmarkError("dual_vlm_manifest_cases_invalid")
    rendering = _object(manifest.get("rendering_contract"))
    if (
        rendering.get("padding_points") != 0
        or rendering.get("reproducibility_renders") != 2
    ):
        raise BenchmarkError("dual_vlm_manifest_rendering_invalid")
    providers = _object(manifest.get("provider_contracts"))
    expected = {
        "detection": ("models/gemini-3.5-flash", DETECTION_PROMPT_VERSION, 4096),
        "gemini_extraction": ("models/gemini-3.5-flash", FACT_PROMPT_VERSION, 16384),
        "openai_extraction": ("gpt-5.4-mini-2026-03-17", FACT_PROMPT_VERSION, 16384),
    }
    for key, (model, prompt, maximum_output) in expected.items():
        contract = _object(providers.get(key))
        if (
            contract.get("model_id") != model
            or contract.get("prompt_contract_version") != prompt
            or contract.get("maximum_output_tokens") != maximum_output
            or contract.get("temperature") != 0
        ):
            raise BenchmarkError("dual_vlm_manifest_provider_contract_invalid")
    policy = _object(manifest.get("execution_policy"))
    if policy != {
        "count_or_preflight_calls_per_provider_operation": 1,
        "generate_calls_per_provider_operation": 1,
        "hidden_retry": False,
        "provider_failover": False,
        "third_llm_arbiter": False,
        "same_crop_bytes_for_extractors": True,
        "whole_document_prompt": False,
        "reference_available_to_runner": False,
    }:
        raise BenchmarkError("dual_vlm_manifest_execution_policy_invalid")
    boundary = _object(manifest.get("reference_boundary"))
    if boundary.get("required_human_reviewed") is not True or any(
        boundary.get(key) is not False
        for key in (
            "runner_may_accept_reference_argument",
            "provider_may_receive_reference_data",
            "pending_operator_decisions_allowed",
        )
    ):
        raise BenchmarkError("dual_vlm_manifest_reference_boundary_invalid")


def _verify_sources(manifest: dict[str, Any], corpus_root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    root = corpus_root.resolve()
    for case in manifest["cases"]:
        path = (root / str(case["relative_pdf"])).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise BenchmarkError("dual_vlm_source_path_escape") from exc
        if not path.is_file():
            raise BenchmarkError("dual_vlm_source_missing")
        payload = path.read_bytes()
        if len(payload) != int(case["pdf_bytes"]):
            raise BenchmarkError("dual_vlm_source_size_mismatch")
        if hashlib.sha256(payload).hexdigest() != str(case["pdf_sha256"]):
            raise BenchmarkError("dual_vlm_source_checksum_mismatch")
        result[str(case["case_id"])] = path
    return result


def _source_revision(repo_root: Path) -> dict[str, Any]:
    commit = _git(repo_root, "rev-parse", "HEAD")
    status = _git(repo_root, "status", "--porcelain")
    if status:
        raise BenchmarkError("dual_vlm_clean_worktree_required")
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
        raise BenchmarkError("dual_vlm_openwebui_credentials_missing")
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
        raise BenchmarkError("dual_vlm_openwebui_token_missing")
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
        raise BenchmarkError("dual_vlm_env_file_missing")
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


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


def _sha256_text(value: Any) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _error_code(exc: BaseException, fallback: str) -> str:
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code:
        return code
    if isinstance(exc, requests.RequestException):
        return "dual_vlm_openwebui_request_failed"
    return fallback


if __name__ == "__main__":
    raise SystemExit(main())
