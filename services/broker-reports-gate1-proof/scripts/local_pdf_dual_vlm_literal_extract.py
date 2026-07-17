#!/usr/bin/env python3
"""Run reference-free dual-provider literal extraction on one frozen crop variant."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
DEFAULT_MANIFEST = SERVICE_ROOT / "benchmarks" / "pdf_dual_vlm_literal_v1" / "manifest.json"

sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from broker_reports_gate1.pdf_hybrid_provider import project_gemini_schema  # noqa: E402
from broker_reports_gate1.pdf_text_layer import (  # noqa: E402
    PdfParserCapabilityRequest,
    PdfTextLayerParserFactory,
)
from local_pdf_dual_vlm_literal_detection import (  # noqa: E402
    _json,
    _openwebui_request,
    _source_cases,
    _source_path,
    _source_revision,
)
from pdf_dual_vlm_fact_providers import (  # noqa: E402
    PdfDualVlmFactProviderConfig,
    PdfDualVlmFactProviderFactory,
)
from pdf_dual_vlm_literal_contracts import (  # noqa: E402
    LITERAL_SCHEMA_VERSION,
    PADDING_VARIANTS,
    TERMINAL_SCHEMA_VERSION,
    build_literal_diffs,
    canonical_json_bytes,
    canonicalize_text,
    literal_model_view,
    literal_observation_schema,
    schema_equivalence_record,
    sha256_json,
    validate_literal_output,
)


TERMINAL_SEAL_SCHEMA_VERSION = "broker_reports_pdf_dual_vlm_literal_terminal_seal_v2"


class LiteralExtractionError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--detection-terminal", required=True)
    parser.add_argument("--detection-seal", required=True)
    parser.add_argument("--padding-experiment", required=True)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--corpus-root", default=str(
        REPO_ROOT
        / "local"
        / "stage2"
        / "broker_reports_pdf_structural_holdout_public_v5_2026-07-15"
        / "corpus"
    ))
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--diagnostic-padding", type=float)
    parser.add_argument("--allow-invalid-upstream-diagnostic", action="store_true")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    return run(args)


def run(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise LiteralExtractionError("literal_extraction_fresh_output_required")
    output_dir.mkdir(parents=True, exist_ok=True)
    terminal_path = output_dir / "OPENWEBUI_PDF_TABLE_DUAL_VLM_LITERAL_TERMINAL.v1.json"
    seal_path = output_dir / "OPENWEBUI_PDF_TABLE_DUAL_VLM_LITERAL_TERMINAL.v1.sha256.json"
    detection_path = Path(args.detection_terminal).resolve()
    detection_seal_path = Path(args.detection_seal).resolve()
    padding_path = Path(args.padding_experiment).resolve()
    manifest = _json(Path(args.manifest).resolve())
    detection = _json(detection_path)
    detection_seal = _json(detection_seal_path)
    padding = _json(padding_path)
    _verify_detection(detection_path, detection, detection_seal)
    if detection.get("manifest_sha256") != sha256_json(manifest):
        raise LiteralExtractionError("literal_extraction_manifest_mismatch")
    if padding.get("detection_terminal_sha256") != detection_seal.get("terminal_sha256"):
        raise LiteralExtractionError("literal_extraction_padding_lineage_mismatch")
    selected = padding.get("selected_padding_fraction_per_page_side")
    diagnostic = False
    if selected is None:
        if not args.allow_invalid_upstream_diagnostic:
            raise LiteralExtractionError("literal_extraction_padding_gate_failed")
        if args.diagnostic_padding not in PADDING_VARIANTS:
            raise LiteralExtractionError("literal_extraction_diagnostic_padding_invalid")
        selected = args.diagnostic_padding
        diagnostic = True
    elif args.diagnostic_padding is not None and args.diagnostic_padding != selected:
        raise LiteralExtractionError("literal_extraction_selected_padding_override_forbidden")

    provider_contracts = manifest.get("provider_contracts") or {}
    gemini_contract = provider_contracts.get("gemini_extraction") or {}
    openai_contract = provider_contracts.get("openai_extraction") or {}
    detector_contract = provider_contracts.get("detection") or {}
    bundle = PdfDualVlmFactProviderFactory(
        PdfDualVlmFactProviderConfig(
            gemini_model_id=str(gemini_contract["model_id"]),
            openai_model_id=str(openai_contract["model_id"]),
            detection_maximum_output_tokens=int(detector_contract["maximum_output_tokens"]),
            extraction_maximum_output_tokens=int(gemini_contract["maximum_output_tokens"]),
            maximum_counted_input_tokens=min(
                int(gemini_contract["maximum_counted_input_tokens"]),
                int(openai_contract["maximum_counted_input_tokens"]),
            ),
            gemini_thinking_level=str(gemini_contract["thinking_level"]),
            openai_image_detail=str(openai_contract["image_detail"]),
        )
    ).create_for_openwebui(_openwebui_request(Path(args.env_file).resolve()))
    qualification = bundle.qualify()
    if any(
        (qualification.get(role) or {}).get("status") != "qualified"
        for role in ("gemini", "openai")
    ):
        raise LiteralExtractionError("literal_extraction_provider_not_qualified")
    schema = literal_observation_schema()
    adapted_schema, transform_count = project_gemini_schema(json.loads(json.dumps(schema)))
    schema_equivalence = schema_equivalence_record(schema, adapted_schema)
    schema_equivalence["gemini_schema_transform_count"] = transform_count
    schema_equivalence["canonical_fixture_roundtrip"] = _schema_fixture_roundtrip()
    if not schema_equivalence["logical_contract_equivalent"]:
        raise LiteralExtractionError("literal_extraction_schema_logical_equivalence_failed")

    cases_by_id = {str(case["case_id"]): case for case in _source_cases(manifest)}
    corpus_root = Path(args.corpus_root).resolve()
    parser = PdfTextLayerParserFactory().create(
        PdfParserCapabilityRequest(capability="layout_words")
    )
    parse_cache: dict[str, Any] = {}
    pdf_cache: dict[str, bytes] = {}
    results: list[dict[str, Any]] = []
    parser_accounting: list[dict[str, Any]] = []
    for detected_case in detection.get("cases") or []:
        case_id = str(detected_case["case_id"])
        source_case = cases_by_id[case_id]
        pdf_sha = str(source_case["pdf_sha256"])
        if pdf_sha not in pdf_cache:
            pdf_bytes = _source_path(corpus_root, str(source_case["relative_pdf"])).read_bytes()
            if hashlib.sha256(pdf_bytes).hexdigest() != pdf_sha:
                raise LiteralExtractionError("literal_extraction_source_sha_mismatch")
            pdf_cache[pdf_sha] = pdf_bytes
            started = time.perf_counter()
            parse_cache[pdf_sha] = parser.parse(pdf_bytes)
            parser_accounting.append(
                {
                    "document_sha256": pdf_sha,
                    "input_bytes": len(pdf_bytes),
                    "duration_ms": round((time.perf_counter() - started) * 1000),
                    "table_construction_performed": False,
                    "ocr_performed": False,
                }
            )
        page = parse_cache[pdf_sha].pages[int(source_case["page_number"]) - 1]
        words = page.get("word_inventory") or []
        for candidate in detected_case.get("candidates") or []:
            if candidate.get("decision") != "present":
                continue
            if candidate.get("bbox_contract_valid") is not True:
                results.append(
                    {
                        "case_id": case_id,
                        "candidate_id": candidate.get("candidate_id"),
                        "terminal_status": "not_extracted_invalid_detection_bbox",
                        "upstream_crop_set_valid": False,
                    }
                )
                continue
            variant = next(
                (
                    item
                    for item in candidate.get("padding_variants") or []
                    if float(item.get("padding_fraction_per_page_side", -1))
                    == float(selected)
                ),
                None,
            )
            if variant is None:
                results.append(
                    {
                        "case_id": case_id,
                        "candidate_id": candidate.get("candidate_id"),
                        "terminal_status": "not_extracted_padding_artifact_missing",
                        "upstream_crop_set_valid": False,
                    }
                )
                continue
            results.append(
                _extract_crop(
                    case=source_case,
                    candidate=candidate,
                    variant=variant,
                    gemini=bundle.gemini,
                    openai=bundle.openai,
                    schema=schema,
                    words=words,
                    upstream_valid=bool(padding.get("gate_a_passed")),
                    diagnostic=diagnostic,
                )
            )

    terminal = {
        "schema_version": TERMINAL_SCHEMA_VERSION,
        "benchmark_id": manifest["benchmark_id"],
        "entrypoint": SCRIPT_PATH.name,
        "reference_argument_supported": False,
        "reference_accessed": False,
        "human_reference_available_to_providers": False,
        "parser_text_available_to_providers": False,
        "other_provider_result_available_to_provider": False,
        "production_authority": False,
        "production_pipeline_changed": False,
        "openwebui_core_changed": False,
        "hidden_retry": False,
        "provider_failover": False,
        "third_llm_arbiter_used": False,
        "detection_terminal_sha256": detection_seal["terminal_sha256"],
        "padding_experiment_sha256": hashlib.sha256(padding_path.read_bytes()).hexdigest(),
        "padding_fraction_per_page_side": selected,
        "padding_selected_by_passing_experiment": not diagnostic,
        "diagnostic_invalid_upstream_crop_set": diagnostic,
        "upstream_detection_and_cropping_gate_passed": padding.get("gate_a_passed") is True,
        "source_revision": _source_revision(),
        "provider_qualification": qualification,
        "schema_equivalence": schema_equivalence,
        "parser_accounting": parser_accounting,
        "crops": results,
        "run_status": "diagnostic_completed" if diagnostic else "completed",
    }
    terminal_bytes = canonical_json_bytes(terminal)
    terminal_path.write_bytes(terminal_bytes)
    seal = {
        "schema_version": TERMINAL_SEAL_SCHEMA_VERSION,
        "terminal_sha256": hashlib.sha256(terminal_bytes).hexdigest(),
        "terminal_size_bytes": len(terminal_bytes),
        "reference_accessed": False,
    }
    seal_path.write_bytes(canonical_json_bytes(seal))
    print(json.dumps({"terminal": str(terminal_path), "seal": str(seal_path), "terminal_sha256": seal["terminal_sha256"], "run_status": terminal["run_status"], "crop_records": len(results)}, ensure_ascii=False, sort_keys=True))
    return 0


def _extract_crop(
    *,
    case: dict[str, Any],
    candidate: dict[str, Any],
    variant: dict[str, Any],
    gemini: Any,
    openai: Any,
    schema: dict[str, Any],
    words: list[dict[str, Any]],
    upstream_valid: bool,
    diagnostic: bool,
) -> dict[str, Any]:
    crop_bytes = base64.b64decode(variant["png_base64"])
    crop_sha = hashlib.sha256(crop_bytes).hexdigest()
    if crop_sha != variant.get("crop_sha256"):
        raise LiteralExtractionError("literal_extraction_crop_sha_mismatch")
    table_identifier = f"{case['case_id']}:{candidate['candidate_id']}"
    model_view = literal_model_view(
        crop_sha256=crop_sha,
        table_identifier=table_identifier,
        image_width=int(variant["crop_width"]),
        image_height=int(variant["crop_height"]),
    )
    gemini_operation = _provider_operation(
        provider=gemini,
        provider_name="gemini",
        task_id=f"literal:{case['case_id']}:{candidate['candidate_id']}:gemini",
        model_view=model_view,
        output_schema=schema,
        png_bytes=crop_bytes,
        table_identifier=table_identifier,
    )
    openai_operation = _provider_operation(
        provider=openai,
        provider_name="openai",
        task_id=f"literal:{case['case_id']}:{candidate['candidate_id']}:openai",
        model_view=model_view,
        output_schema=schema,
        png_bytes=crop_bytes,
        table_identifier=table_identifier,
    )
    shared_input = _shared_input_truth(gemini_operation, openai_operation, crop_sha)
    if not shared_input["all_identical"]:
        raise LiteralExtractionError("literal_extraction_provider_input_diverged")
    gemini_output = gemini_operation.get("json_output")
    openai_output = openai_operation.get("json_output")
    diffs = None
    if (
        gemini_operation.get("terminal_status") == "completed"
        and openai_operation.get("terminal_status") == "completed"
    ):
        diffs = build_literal_diffs(
            gemini_entries=gemini_output["entries"],
            openai_entries=openai_output["entries"],
        )
    evidence_medium = _evidence_medium(case, variant["padded_crop_bbox"], words)
    evidence = {
        "gemini": _parser_evidence(
            entries=(gemini_output or {}).get("entries") or [],
            crop_bbox=variant["padded_crop_bbox"],
            page_bbox_points=case["page_bbox_points"],
            words=words,
            evidence_medium=evidence_medium,
        ),
        "openai": _parser_evidence(
            entries=(openai_output or {}).get("entries") or [],
            crop_bbox=variant["padded_crop_bbox"],
            page_bbox_points=case["page_bbox_points"],
            words=words,
            evidence_medium=evidence_medium,
        ),
    }
    return {
        "case_id": case["case_id"],
        "document_sha256": case["pdf_sha256"],
        "page_number": case["page_number"],
        "candidate_id": candidate["candidate_id"],
        "detected_bbox": candidate["detected_bbox"],
        "padded_crop_bbox": variant["padded_crop_bbox"],
        "padding_fraction_per_page_side": variant[
            "padding_fraction_per_page_side"
        ],
        "crop_sha256": crop_sha,
        "crop_bytes": len(crop_bytes),
        "crop_width": variant["crop_width"],
        "crop_height": variant["crop_height"],
        "crop_png_base64": variant["png_base64"],
        "crop_reproducible": variant["byte_identical_reproduction"],
        "upstream_crop_set_valid": upstream_valid,
        "diagnostic_only": diagnostic,
        "model_view": model_view,
        "shared_provider_input_truth": shared_input,
        "gemini": gemini_operation,
        "openai": openai_operation,
        "provider_diffs_reference_free": diffs,
        "parser_evidence": evidence,
        "evidence_medium": evidence_medium,
        "terminal_status": (
            "completed"
            if gemini_operation["terminal_status"] == "completed"
            and openai_operation["terminal_status"] == "completed"
            else "completed_with_provider_failure"
        ),
    }


def _provider_operation(
    *,
    provider: Any,
    provider_name: str,
    task_id: str,
    model_view: dict[str, Any],
    output_schema: dict[str, Any],
    png_bytes: bytes,
    table_identifier: str,
) -> dict[str, Any]:
    crop_sha = hashlib.sha256(png_bytes).hexdigest()
    operation: dict[str, Any] = {
        "provider": provider_name,
        "task_id": task_id,
        "crop_sha256": crop_sha,
        "input_bytes": len(png_bytes),
        "prompt_sha256": sha256_json(model_view),
        "schema_sha256": sha256_json(output_schema),
        "model_view_hash": sha256_json(model_view),
        "count_or_preflight_calls_attempted": 1,
        "count_or_preflight_calls_completed": 0,
        "generate_calls_attempted": 0,
        "generate_calls_completed": 0,
        "count_tokens": None,
        "attempt": None,
        "raw_provider_text": None,
        "json_output": None,
        "contract_errors": [],
        "failure_code": None,
        "terminal_status": "failed_before_preflight",
        "hidden_retry": False,
        "provider_failover": False,
    }
    try:
        counted = provider.count_tokens(
            model_view=model_view,
            output_schema=output_schema,
            png_bytes=png_bytes,
            crop_sha256=crop_sha,
        )
    except Exception as exc:
        operation["failure_code"] = _error_code(exc, "literal_extraction_preflight_failed")
        return operation
    operation["count_or_preflight_calls_completed"] = 1
    operation["count_tokens"] = counted
    operation["generate_calls_attempted"] = 1
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
        operation["failure_code"] = _error_code(exc, "literal_extraction_generate_failed")
        operation["terminal_status"] = "terminal_provider_failure"
        return operation
    operation["generate_calls_completed"] = 1
    if not isinstance(result, dict):
        operation["failure_code"] = "literal_extraction_provider_result_invalid"
        operation["terminal_status"] = "terminal_provider_failure"
        return operation
    attempt = result.get("attempt") if isinstance(result.get("attempt"), dict) else {}
    operation["attempt"] = attempt
    operation["raw_provider_text"] = result.get("text")
    operation["json_output"] = result.get("json_output")
    operation["response_bytes"] = result.get("response_bytes")
    if attempt.get("attempt_number") != 1 or attempt.get("attempt_lineage") != []:
        operation["failure_code"] = "literal_extraction_attempt_contract_invalid"
    elif attempt.get("hidden_retry") is not False or attempt.get("provider_failover") is not False:
        operation["failure_code"] = "literal_extraction_execution_policy_invalid"
    elif attempt.get("crop_sha256") != crop_sha:
        operation["failure_code"] = "literal_extraction_provider_crop_sha_mismatch"
    elif attempt.get("model_view_hash") != sha256_json(model_view):
        operation["failure_code"] = "literal_extraction_provider_model_view_mismatch"
    elif attempt.get("terminal_failure_class") is not None:
        operation["failure_code"] = "literal_extraction_provider_terminal_failure"
    if operation["failure_code"]:
        operation["terminal_status"] = "terminal_provider_failure"
        return operation
    errors = validate_literal_output(
        operation["json_output"],
        crop_sha256=crop_sha,
        table_identifier=table_identifier,
    )
    operation["contract_errors"] = errors
    if errors:
        operation["failure_code"] = errors[0]
        operation["terminal_status"] = "terminal_contract_failure"
        return operation
    operation["terminal_status"] = "completed"
    return operation


def _shared_input_truth(
    gemini: dict[str, Any], openai: dict[str, Any], crop_sha: str
) -> dict[str, Any]:
    fields = {
        "crop_sha256": (
            gemini.get("crop_sha256"),
            openai.get("crop_sha256"),
            crop_sha,
        ),
        "model_view_hash": (
            gemini.get("model_view_hash"),
            openai.get("model_view_hash"),
        ),
        "canonical_schema_hash": (
            gemini.get("schema_sha256"),
            openai.get("schema_sha256"),
        ),
        "input_bytes": (gemini.get("input_bytes"), openai.get("input_bytes")),
    }
    checks = {key: len(set(values)) == 1 for key, values in fields.items()}
    return {"checks": checks, "values": fields, "all_identical": all(checks.values())}


def _parser_evidence(
    *,
    entries: list[dict[str, Any]],
    crop_bbox: list[float],
    page_bbox_points: list[float],
    words: list[dict[str, Any]],
    evidence_medium: str,
) -> list[dict[str, Any]]:
    if evidence_medium == "raster":
        return [
            {
                "entry_id": entry.get("entry_id"),
                "status": "parser_not_applicable_raster",
                "independent_text_evidence": "vision_only_no_independent_text_evidence",
                "parser_atom_ids": [],
                "binding_unique": False,
            }
            for entry in entries
        ]
    crop_words = [
        word
        for word in words
        if _center_inside_points(word.get("bbox"), _normalized_page_to_points(crop_bbox, page_bbox_points))
    ]
    result: list[dict[str, Any]] = []
    for entry in entries:
        row_bbox = _crop_bbox_to_page_points(entry["row_label_bbox"], crop_bbox, page_bbox_points)
        value_bbox = _crop_bbox_to_page_points(entry["value_bbox"], crop_bbox, page_bbox_points)
        header_boxes = [
            _crop_bbox_to_page_points(item, crop_bbox, page_bbox_points)
            for item in entry["header_bboxes"]
        ]
        row_match = _text_evidence(entry["row_label_text"], row_bbox, crop_words)
        value_match = _text_evidence(entry["visible_value_text"], value_bbox, crop_words)
        header_matches = [
            _text_evidence(text, bbox, crop_words)
            for text, bbox in zip(entry["column_header_path"], header_boxes)
        ]
        header_verified = len(header_matches) == len(entry["column_header_path"]) and all(
            item["verified"] for item in header_matches
        )
        components = [row_match, value_match, *header_matches]
        atom_ids = sorted(
            {
                atom
                for component in components
                for atom in component["parser_atom_ids"]
            }
        )
        unique = all(component["unique"] for component in components)
        if row_match["verified"] and value_match["verified"] and header_verified and unique:
            status = "parser_literal_verified"
        elif value_match["verified"] and not unique:
            status = "parser_value_verified_binding_ambiguous"
        elif any(component["verified"] for component in components):
            status = "parser_text_partial"
        else:
            status = "parser_no_matching_text"
        result.append(
            {
                "entry_id": entry["entry_id"],
                "status": status,
                "row_label_verified": row_match["verified"],
                "header_path_verified": header_verified,
                "visible_value_verified": value_match["verified"],
                "parser_atom_ids": atom_ids,
                "source_bboxes": [
                    component["source_bbox"]
                    for component in components
                    if component["source_bbox"] is not None
                ],
                "binding_unique": unique,
                "parser_constructed_table": False,
                "parser_selected_provider": False,
                "parser_rewrote_text": False,
            }
        )
    return result


def _text_evidence(
    text: str, source_bbox: list[float], words: list[dict[str, Any]]
) -> dict[str, Any]:
    desired = canonicalize_text(text)
    local = [word for word in words if _center_inside_points(word.get("bbox"), source_bbox)]
    local_sorted = sorted(
        local,
        key=lambda item: (
            round(float(item["bbox"][1]) / 3) if item.get("bbox") else 0,
            float(item["bbox"][0]) if item.get("bbox") else 0,
        ),
    )
    rendered = canonicalize_text(" ".join(str(item.get("text") or "") for item in local_sorted))
    verified = bool(desired) and (desired == rendered or desired in rendered)
    occurrences = _phrase_occurrences(desired, words)
    return {
        "verified": verified,
        "unique": verified and occurrences == 1,
        "occurrences_in_crop": occurrences,
        "parser_atom_ids": [
            int(item["parser_ordinal"])
            for item in local_sorted
            if isinstance(item.get("parser_ordinal"), int)
        ],
        "source_bbox": _union_bbox(
            [item["bbox"] for item in local_sorted if isinstance(item.get("bbox"), list)]
        ),
    }


def _phrase_occurrences(text: str, words: list[dict[str, Any]]) -> int:
    if not text:
        return 0
    tokens = text.casefold().split()
    word_tokens = [canonicalize_text(item.get("text")).casefold() for item in words]
    if not tokens:
        return 0
    return sum(
        word_tokens[index : index + len(tokens)] == tokens
        for index in range(max(0, len(word_tokens) - len(tokens) + 1))
    )


def _evidence_medium(
    case: dict[str, Any], crop_bbox: list[float], words: list[dict[str, Any]]
) -> str:
    page_bbox_points = case["page_bbox_points"]
    crop_points = _normalized_page_to_points(crop_bbox, page_bbox_points)
    inside = [word for word in words if _center_inside_points(word.get("bbox"), crop_points)]
    raster_tagged = bool(
        {"raster_image", "without_text_layer"} & set(case.get("category_tags") or [])
    )
    if raster_tagged:
        return "mixed" if inside else "raster"
    return "text_layer"


def _crop_bbox_to_page_points(
    entry_bbox: list[float],
    crop_bbox: list[float],
    page_bbox_points: list[float],
) -> list[float]:
    width = crop_bbox[2] - crop_bbox[0]
    height = crop_bbox[3] - crop_bbox[1]
    page_normalized = [
        crop_bbox[0] + entry_bbox[0] * width,
        crop_bbox[1] + entry_bbox[1] * height,
        crop_bbox[0] + entry_bbox[2] * width,
        crop_bbox[1] + entry_bbox[3] * height,
    ]
    return _normalized_page_to_points(page_normalized, page_bbox_points)


def _normalized_page_to_points(
    bbox: list[float], page_bbox_points: list[float]
) -> list[float]:
    x0, y0, x1, y1 = (float(item) for item in page_bbox_points)
    width = x1 - x0
    height = y1 - y0
    return [
        x0 + bbox[0] * width,
        y0 + bbox[1] * height,
        x0 + bbox[2] * width,
        y0 + bbox[3] * height,
    ]


def _center_inside_points(value: Any, scope: list[float]) -> bool:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return False
    center_x = (float(value[0]) + float(value[2])) / 2
    center_y = (float(value[1]) + float(value[3])) / 2
    return scope[0] <= center_x <= scope[2] and scope[1] <= center_y <= scope[3]


def _union_bbox(values: list[list[float]]) -> list[float] | None:
    if not values:
        return None
    return [
        min(float(item[0]) for item in values),
        min(float(item[1]) for item in values),
        max(float(item[2]) for item in values),
        max(float(item[3]) for item in values),
    ]


def _schema_fixture_roundtrip() -> dict[str, Any]:
    fixture = {
        "schema_version": LITERAL_SCHEMA_VERSION,
        "crop_sha256": "f" * 64,
        "table_identifier": "fixture_table",
        "entries": [
            {
                "entry_id": "fixture_entry",
                "row_label_text": "Cash and cash equivalents",
                "column_header_path": ["Assets", "31 December 2025"],
                "visible_value_text": "1,000",
                "row_label_bbox": [0.05, 0.2, 0.4, 0.25],
                "header_bboxes": [
                    [0.6, 0.05, 0.95, 0.1],
                    [0.7, 0.1, 0.95, 0.15],
                ],
                "value_bbox": [0.75, 0.2, 0.95, 0.25],
                "cell_state": "value",
                "uncertainty_codes": [],
            }
        ],
    }
    errors = validate_literal_output(
        fixture, crop_sha256="f" * 64, table_identifier="fixture_table"
    )
    gemini_roundtrip = json.loads(canonical_json_bytes(fixture))
    openai_roundtrip = json.loads(canonical_json_bytes(fixture))
    return {
        "fixture_sha256": sha256_json(fixture),
        "canonical_validation_errors": errors,
        "gemini_adapter_roundtrip_sha256": sha256_json(gemini_roundtrip),
        "openai_adapter_roundtrip_sha256": sha256_json(openai_roundtrip),
        "canonical_equivalence": (
            fixture == gemini_roundtrip == openai_roundtrip and not errors
        ),
    }


def _verify_detection(
    path: Path, terminal: dict[str, Any], seal: dict[str, Any]
) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if (
        seal.get("terminal_sha256") != digest
        or seal.get("terminal_size_bytes") != path.stat().st_size
    ):
        raise LiteralExtractionError("literal_extraction_detection_seal_mismatch")
    if terminal.get("reference_accessed") is not False:
        raise LiteralExtractionError("literal_extraction_detection_reference_boundary_invalid")


def _error_code(exc: BaseException, fallback: str) -> str:
    return str(getattr(exc, "code", None) or fallback)


if __name__ == "__main__":
    raise SystemExit(main())
