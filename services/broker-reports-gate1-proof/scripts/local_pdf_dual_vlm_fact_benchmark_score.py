#!/usr/bin/env python3
"""Score a sealed dual-VLM run against a human-reviewed immutable reference."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
SERVICE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from pdf_dual_vlm_fact_contracts import (  # noqa: E402
    AGREEMENT_STATUSES,
    FACT_TYPES,
    bbox_iou,
    canonical_json_bytes,
    canonicalize_fact,
    compare_provider_facts,
    detection_model_view,
    detection_schema,
    fact_model_view,
    financial_fact_schema,
    normalize_text,
    normalize_whitespace,
    sha256_json,
    validate_consensus,
    validate_crop_contract,
    validate_detection_output,
    validate_fact_extraction_output,
)
from pdf_dual_vlm_fact_evidence import (  # noqa: E402
    validate_evidence_result,
    validate_source_map,
)
from pdf_dual_vlm_fact_review import (  # noqa: E402
    FINAL_REFERENCE_SCHEMA,
    FINAL_REFERENCE_SEAL_SCHEMA,
)


SCORE_SCHEMA_VERSION = "broker_reports_pdf_dual_vlm_fact_score_v1"
TERMINAL_SCHEMA_VERSION = "broker_reports_pdf_dual_vlm_fact_terminal_v1"
SEAL_SCHEMA_VERSION = "broker_reports_pdf_dual_vlm_fact_terminal_seal_v1"
CONCLUSIONS = {
    "DUAL_VLM_FACT_ARCHITECTURE_RECOMMENDED",
    "DUAL_VLM_FACT_ARCHITECTURE_PROMISING_BUT_NOT_READY",
    "DUAL_VLM_FACT_ARCHITECTURE_NOT_JUSTIFIED",
}

FROZEN_CASES: dict[str, dict[str, Any]] = {
    "betterment_p02": {
        "pdf_sha256": "fbe6a299b05615643a0f0264568c65a64bd857b6b77752163b8c2e52bbcbf71e",
        "page_number": 2,
        "expected_kind": "negative",
    },
    "betterment_p04": {
        "pdf_sha256": "fbe6a299b05615643a0f0264568c65a64bd857b6b77752163b8c2e52bbcbf71e",
        "page_number": 4,
        "expected_kind": "table",
    },
    "drivewealth_p07": {
        "pdf_sha256": "738a0279eba3020c9a6cf3a650df254d0a2a8a0800aae80b4889efcc0a8bec57",
        "page_number": 7,
        "expected_kind": "table",
    },
    "drivewealth_p09": {
        "pdf_sha256": "738a0279eba3020c9a6cf3a650df254d0a2a8a0800aae80b4889efcc0a8bec57",
        "page_number": 9,
        "expected_kind": "table",
    },
    "moomoo_annual_p14": {
        "pdf_sha256": "bad1e5fa045f0735f02487aca14236d84037f82fd2b1230ee3c56ba3420aee67",
        "page_number": 14,
        "expected_kind": "table",
    },
    "moomoo_midyear_p10": {
        "pdf_sha256": "766448b2bf8b9ebe9172e4a07b0392134787a3b642288a93fbe6c0f9999ed0d3",
        "page_number": 10,
        "expected_kind": "table",
    },
    "ibkr_annual_p11": {
        "pdf_sha256": "6486885e58867d382bd433228193e476a07b6cea2061ddbd74bef1dc6c65a118",
        "page_number": 11,
        "expected_kind": "table",
    },
    "ibkr_midyear_p03": {
        "pdf_sha256": "d635df4866a040ce665bfde0da74dbf4dc8933931337a1b023377bf02cf60c2c",
        "page_number": 3,
        "expected_kind": "table",
    },
}
FROZEN_CASE_IDS = tuple(FROZEN_CASES)
FROZEN_PROVIDER_MODELS = {
    "detection": ("google", "models/gemini-3.5-flash", 4096, 1.5, 9.0),
    "gemini_extraction": (
        "google",
        "models/gemini-3.5-flash",
        16384,
        1.5,
        9.0,
    ),
    "openai_extraction": (
        "openai",
        "gpt-5.4-mini-2026-03-17",
        16384,
        0.75,
        4.5,
    ),
}
FROZEN_SCORING_POLICY = {
    "detection_iou_threshold": 0.5,
    "detection_recall_minimum": 1.0,
    "detection_precision_minimum": 0.9,
    "cut_reference_tables_allowed": 0,
    "merged_reference_tables_allowed": 0,
    "split_reference_tables_allowed": 0,
    "crop_reproducibility_required": True,
    "consensus_fact_precision_minimum": 1.0,
    "consensus_fact_recall_minimum": 0.8,
    "accepted_fact_precision_minimum": 1.0,
    "accepted_fact_recall_minimum": 0.8,
    "human_review_rate_maximum": 0.2,
    "accepted_provenance_coverage_minimum": 1.0,
    "false_accepted_facts_maximum": 0,
    "invented_accepted_values_maximum": 0,
    "mutated_accepted_values_maximum": 0,
    "physical_layout_role": "secondary_diagnostic",
    "raster_metrics_separate": True,
}
_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_REVIEWER_TOKENS = {
    "agent",
    "ai",
    "assistant",
    "bot",
    "chatgpt",
    "claude",
    "codex",
    "gemini",
    "gpt",
    "llm",
    "model",
    "openai",
}


class ScoreError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal", required=True)
    parser.add_argument("--seal", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--reference-seal", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        score = score_run(
            terminal_path=Path(args.terminal).resolve(),
            seal_path=Path(args.seal).resolve(),
            reference_path=Path(args.reference).resolve(),
            reference_seal_path=Path(args.reference_seal).resolve(),
        )
        exit_code = 0 if score["scoring_status"] == "completed" else 2
    except Exception as exc:
        score = _failed_score(_error_code(exc, "dual_vlm_scoring_unexpected_failure"))
        exit_code = 2
    output.write_bytes(canonical_json_bytes(score))
    print(
        json.dumps(
            {
                "scoring_status": score["scoring_status"],
                "failure_code": score.get("failure_code"),
                "conclusion": score.get("architectural_conclusion"),
                "output": str(output),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return exit_code


def score_run(
    *,
    terminal_path: Path,
    seal_path: Path,
    reference_path: Path,
    reference_seal_path: Path,
) -> dict[str, Any]:
    terminal_bytes = terminal_path.read_bytes()
    seal_bytes = seal_path.read_bytes()
    seal = _json_object(seal_bytes, "dual_vlm_terminal_seal_json_invalid")
    terminal_sha = hashlib.sha256(terminal_bytes).hexdigest()
    if seal.get("schema_version") != SEAL_SCHEMA_VERSION:
        raise ScoreError("dual_vlm_terminal_seal_schema_invalid")
    if seal.get("terminal_sha256") != terminal_sha or seal.get(
        "terminal_size_bytes"
    ) != len(terminal_bytes):
        raise ScoreError("dual_vlm_terminal_seal_mismatch")
    if seal.get("reference_accessed") is not False:
        raise ScoreError("dual_vlm_terminal_seal_reference_boundary_invalid")
    terminal = _json_object(terminal_bytes, "dual_vlm_terminal_json_invalid")
    if terminal.get("schema_version") != TERMINAL_SCHEMA_VERSION:
        raise ScoreError("dual_vlm_terminal_schema_invalid")
    if (
        terminal.get("reference_accessed") is not False
        or terminal.get("human_reference_available_to_runner") is not False
    ):
        raise ScoreError("dual_vlm_terminal_reference_boundary_invalid")
    if _object(terminal.get("runner")).get("reference_argument_supported") is not False:
        raise ScoreError("dual_vlm_runner_reference_argument_invalid")
    manifest = _object(terminal.get("target_manifest"))
    if terminal.get("manifest_sha256") != sha256_json(manifest):
        raise ScoreError("dual_vlm_terminal_manifest_hash_invalid")
    terminal_verified_before_reference_access = True
    _validate_terminal_contract(terminal, manifest)
    terminal_contract_verified_before_reference_access = True

    if not reference_path.is_file() or not reference_seal_path.is_file():
        return _human_reference_required_score(
            terminal_sha=terminal_sha,
            terminal_verified=terminal_verified_before_reference_access,
            terminal_contract_verified=(
                terminal_contract_verified_before_reference_access
            ),
            manifest_sha=terminal.get("manifest_sha256"),
        )
    reference_bytes = reference_path.read_bytes()
    reference = _json_object(reference_bytes, "dual_vlm_human_reference_json_invalid")
    reference_seal_bytes = reference_seal_path.read_bytes()
    reference_seal = _json_object(
        reference_seal_bytes, "dual_vlm_human_reference_seal_json_invalid"
    )
    reference_sha = hashlib.sha256(reference_bytes).hexdigest()
    _validate_human_reference(
        reference,
        reference_seal,
        reference_sha=reference_sha,
        reference_size=len(reference_bytes),
        manifest_sha=str(terminal["manifest_sha256"]),
        manifest=manifest,
    )
    reference_accessed_after_terminal_verification = True

    detection = _score_detection(terminal, reference, manifest)
    # Contractual order: detection is complete before any fact extraction score.
    facts = _score_facts(terminal, reference, detection)
    operational = _operational_metrics(terminal, manifest)
    provider_structured_output_comparability = (
        _provider_structured_output_comparability(terminal, manifest, operational)
    )
    detection_passed = bool(
        _detection_gate(detection, manifest)
        and operational["detection"]["execution_contract_passed"]
    )
    extraction_passed = bool(
        _extraction_gate(facts, manifest)
        and operational["gemini_extraction"]["execution_contract_passed"]
        and operational["openai_extraction"]["execution_contract_passed"]
    )
    evidence_passed = _evidence_gate(facts, manifest)
    material_improvement = _material_improvement(facts, manifest)
    reference_contract = _reference_contract_diagnostics(reference)
    base_benchmark = _object(manifest.get("base_benchmark"))
    previous_benchmark_comparison = {
        "status": "not_established",
        "comparison_role": base_benchmark.get("comparison_role"),
        "accepted_score_sha256": base_benchmark.get("accepted_score_sha256"),
        "reason": (
            "the scorer compares consensus-plus-evidence with the two current "
            "provider arms and does not load the frozen prior benchmark score"
        ),
        "current_material_improvement_comparator": "current_provider_arms_only",
    }
    conclusion = _conclusion(
        detection_passed=detection_passed,
        extraction_passed=extraction_passed,
        evidence_passed=evidence_passed,
        material_improvement=material_improvement,
        facts=facts,
    )
    terminal_after = terminal_path.read_bytes()
    if hashlib.sha256(terminal_after).hexdigest() != terminal_sha:
        raise ScoreError("dual_vlm_terminal_changed_during_scoring")
    if seal_path.read_bytes() != seal_bytes:
        raise ScoreError("dual_vlm_terminal_seal_changed_during_scoring")
    if reference_path.read_bytes() != reference_bytes:
        raise ScoreError("dual_vlm_human_reference_changed_during_scoring")
    if reference_seal_path.read_bytes() != reference_seal_bytes:
        raise ScoreError("dual_vlm_human_reference_seal_changed_during_scoring")
    result: dict[str, Any] = {
        "schema_version": SCORE_SCHEMA_VERSION,
        "scoring_status": "completed",
        "failure_code": None,
        "terminal_sha256": terminal_sha,
        "manifest_sha256": terminal["manifest_sha256"],
        "reference_sha256": reference_sha,
        "reference_human_reviewed": True,
        "terminal_verified_before_reference_access": (
            terminal_verified_before_reference_access
        ),
        "terminal_contract_verified_before_reference_access": (
            terminal_contract_verified_before_reference_access
        ),
        "reference_accessed_after_terminal_verification": (
            reference_accessed_after_terminal_verification
        ),
        "terminal_unchanged_during_scoring": True,
        "terminal_seal_unchanged_during_scoring": True,
        "reference_unchanged_during_scoring": True,
        "reference_seal_unchanged_during_scoring": True,
        "scoring_order": [
            "table_detection_and_cropping",
            "provider_financial_fact_extraction",
            "dual_model_consensus",
            "fact_evidence_verification",
        ],
        "gates": {
            "TABLE_DETECTION_AND_CROPPING": (
                "PASSED" if detection_passed else "FAILED"
            ),
            "DUAL_VLM_FINANCIAL_FACT_EXTRACTION": (
                "PASSED" if extraction_passed else "FAILED"
            ),
            "FACT_EVIDENCE_VERIFICATION": ("PASSED" if evidence_passed else "FAILED"),
        },
        "architectural_conclusion": conclusion,
        "materially_better_than_single_vlm": material_improvement,
        "previous_benchmark_comparison": previous_benchmark_comparison,
        "reference_contract": reference_contract,
        "provider_structured_output_comparability": (
            provider_structured_output_comparability
        ),
        "detection": detection,
        "facts": facts,
        "operational": operational,
        "scorer_implementation_sha256": hashlib.sha256(
            SCRIPT_PATH.read_bytes()
        ).hexdigest(),
    }
    result["score_checksum"] = sha256_json(result)
    return result


def _validate_terminal_contract(
    terminal: dict[str, Any], manifest: dict[str, Any]
) -> None:
    _validate_frozen_manifest(manifest)
    boundary_flags = {
        "production_authority": False,
        "production_pipeline_changed": False,
        "production_gate1_changed": False,
        "production_gate2_changed": False,
        "openwebui_core_changed": False,
        "knowledge_or_rag_used": False,
        "ocr_performed": False,
        "third_llm_arbiter_used": False,
    }
    if any(
        terminal.get(key) is not expected for key, expected in boundary_flags.items()
    ):
        raise ScoreError("dual_vlm_terminal_authority_boundary_invalid")
    if (
        terminal.get("hidden_retry") is True
        or terminal.get("provider_failover") is True
    ):
        raise ScoreError("dual_vlm_terminal_execution_boundary_invalid")
    if terminal.get("hidden_retry") not in {False, None} or terminal.get(
        "provider_failover"
    ) not in {False, None}:
        raise ScoreError("dual_vlm_terminal_execution_boundary_invalid")
    if terminal.get("run_status") not in {"completed", "completed_with_failures"}:
        raise ScoreError("dual_vlm_terminal_run_status_invalid")
    if not isinstance(terminal.get("failures"), list):
        raise ScoreError("dual_vlm_terminal_failures_invalid")
    source_revision = _object(terminal.get("source_revision"))
    if (
        source_revision.get("worktree_clean") is not True
        or not isinstance(source_revision.get("branch"), str)
        or not source_revision["branch"]
        or not isinstance(source_revision.get("repository_commit_sha"), str)
        or not _HEX_40.fullmatch(source_revision["repository_commit_sha"])
    ):
        raise ScoreError("dual_vlm_terminal_source_revision_invalid")
    _validate_provider_qualification(terminal.get("provider_qualification"))
    cases = terminal.get("cases")
    if not isinstance(cases, list):
        raise ScoreError("dual_vlm_terminal_cases_invalid")
    case_ids = [str(_object(case).get("case_id") or "") for case in cases]
    if tuple(case_ids) != FROZEN_CASE_IDS or len(set(case_ids)) != len(case_ids):
        raise ScoreError("dual_vlm_terminal_cases_invalid")
    manifest_cases = {str(case["case_id"]): case for case in manifest["cases"]}
    for case in cases:
        _validate_terminal_case(case, manifest_cases[str(case["case_id"])])
    operations = _terminal_operations(terminal)
    expected_accounting = {
        "provider_operations": len(operations),
        "count_or_preflight_calls_attempted": 0,
        "count_or_preflight_calls_completed": 0,
        "generate_calls_attempted": 0,
        "generate_calls_completed": 0,
    }
    for operation in operations:
        accounting = _object(operation.get("call_accounting"))
        for key in tuple(expected_accounting)[1:]:
            value = accounting.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ScoreError("dual_vlm_terminal_call_accounting_invalid")
            expected_accounting[key] += value
    if terminal.get("execution_call_accounting") != expected_accounting:
        raise ScoreError("dual_vlm_terminal_call_accounting_mismatch")


def _validate_frozen_manifest(manifest: dict[str, Any]) -> None:
    if (
        manifest.get("schema_version") != "broker_reports_pdf_dual_vlm_fact_manifest_v1"
        or manifest.get("benchmark_id") != "pdf_dual_vlm_fact_v1"
        or manifest.get("corpus_role") != "development_benchmark"
        or manifest.get("frozen") is not True
        or manifest.get("case_count") != len(FROZEN_CASE_IDS)
        or manifest.get("expected_reference_tables") != 9
    ):
        raise ScoreError("dual_vlm_terminal_manifest_frozen_identity_invalid")
    rendering = _object(manifest.get("rendering_contract"))
    if rendering != {
        "dpi": 150,
        "page_bbox_points": [0.0, 0.0, 612.0, 792.0],
        "pixel_format": "png",
        "lossless": True,
        "padding_points": 0,
        "silent_resize_allowed": False,
        "reproducibility_renders": 2,
    }:
        raise ScoreError("dual_vlm_terminal_manifest_rendering_invalid")
    cases = manifest.get("cases")
    if (
        not isinstance(cases, list)
        or tuple(str(_object(case).get("case_id") or "") for case in cases)
        != FROZEN_CASE_IDS
    ):
        raise ScoreError("dual_vlm_terminal_manifest_cases_invalid")
    for case in cases:
        frozen = FROZEN_CASES[str(case["case_id"])]
        if (
            case.get("pdf_sha256") != frozen["pdf_sha256"]
            or case.get("page_number") != frozen["page_number"]
            or case.get("page_bbox_points") != [0.0, 0.0, 612.0, 792.0]
            or case.get("render_dpi") != 150
        ):
            raise ScoreError("dual_vlm_terminal_manifest_case_identity_invalid")
    providers = _object(manifest.get("provider_contracts"))
    if set(providers) != set(FROZEN_PROVIDER_MODELS):
        raise ScoreError("dual_vlm_terminal_manifest_provider_invalid")
    for key, expected in FROZEN_PROVIDER_MODELS.items():
        provider, model, maximum_output, input_price, output_price = expected
        contract = _object(providers.get(key))
        if (
            contract.get("provider") != provider
            or contract.get("model_id") != model
            or contract.get("maximum_counted_input_tokens") != 24000
            or contract.get("maximum_output_tokens") != maximum_output
            or contract.get("temperature") != 0
            or float(contract.get("input_usd_per_1m_tokens", -1)) != input_price
            or float(contract.get("output_usd_per_1m_tokens", -1)) != output_price
        ):
            raise ScoreError("dual_vlm_terminal_manifest_provider_invalid")
    if (
        _object(providers["openai_extraction"]).get("cached_input_usd_per_1m_tokens")
        != 0.075
    ):
        raise ScoreError("dual_vlm_terminal_manifest_provider_invalid")
    if manifest.get("scoring_policy") != FROZEN_SCORING_POLICY:
        raise ScoreError("dual_vlm_terminal_manifest_scoring_policy_invalid")
    if manifest.get("execution_policy") != {
        "count_or_preflight_calls_per_provider_operation": 1,
        "generate_calls_per_provider_operation": 1,
        "hidden_retry": False,
        "provider_failover": False,
        "third_llm_arbiter": False,
        "same_crop_bytes_for_extractors": True,
        "whole_document_prompt": False,
        "reference_available_to_runner": False,
    }:
        raise ScoreError("dual_vlm_terminal_manifest_execution_policy_invalid")
    evidence = _object(manifest.get("evidence_policy"))
    if (
        evidence.get("parser_role") != "fact_relation_evidence_only"
        or evidence.get("parser_table_construction") is not False
        or evidence.get("independent_ocr_adapter") != "unavailable"
        or evidence.get("raster_maximum_status") != "models_agree_vision_only"
        or evidence.get("vision_only_auto_accept") is not False
    ):
        raise ScoreError("dual_vlm_terminal_manifest_evidence_policy_invalid")
    boundary = _object(manifest.get("reference_boundary"))
    if boundary != {
        "required_human_reviewed": True,
        "runner_may_accept_reference_argument": False,
        "provider_may_receive_reference_data": False,
        "reference_may_be_opened_only_after_terminal_seal": True,
        "reference_must_be_immutable_during_scoring": True,
        "pending_operator_decisions_allowed": False,
    }:
        raise ScoreError("dual_vlm_terminal_manifest_reference_boundary_invalid")


def _validate_provider_qualification(value: Any) -> None:
    qualification = _object(value)
    expected = {
        "detector": ("google_gemini", "models/gemini-3.5-flash"),
        "gemini": ("google_gemini", "models/gemini-3.5-flash"),
        "openai": ("openai_gpt", "gpt-5.4-mini-2026-03-17"),
    }
    if set(qualification) != set(expected):
        raise ScoreError("dual_vlm_terminal_provider_qualification_invalid")
    for key, (profile, model) in expected.items():
        item = _object(qualification[key])
        if (
            item.get("status") != "qualified"
            or item.get("provider_profile") != profile
            or item.get("requested_model_id") != model
            or item.get("resolved_model_id") != model
            or item.get("exact_model_match") is not True
            or item.get("image_input_supported") is not True
            or item.get("structured_output_supported") is not True
            or item.get("native_provider_transport") is not True
            or item.get("credentials_from_openwebui_connection") is not True
            or item.get("hidden_retry") is not False
            or item.get("provider_failover") is not False
        ):
            raise ScoreError("dual_vlm_terminal_provider_qualification_invalid")


def _validate_terminal_case(case: Any, manifest_case: dict[str, Any]) -> None:
    if not isinstance(case, dict):
        raise ScoreError("dual_vlm_terminal_case_invalid")
    case_id = str(case.get("case_id") or "")
    if case.get("terminal_status") == "failed":
        failed_detection = _object(case.get("detection"))
        if (
            case.get("input") is not None
            or failed_detection.get("status") != "failed"
            or failed_detection.get("output") is not None
            or failed_detection.get("operation") is not None
            or not isinstance(failed_detection.get("contract_errors"), list)
            or not failed_detection["contract_errors"]
            or case.get("crops") != []
            or not isinstance(case.get("failure_code"), str)
            or not case["failure_code"]
        ):
            raise ScoreError("dual_vlm_terminal_failed_case_invalid")
        return
    input_value = _object(case.get("input"))
    if (
        input_value.get("pdf_sha256") != manifest_case.get("pdf_sha256")
        or input_value.get("pdf_bytes") != manifest_case.get("pdf_bytes")
        or input_value.get("relative_pdf") != manifest_case.get("relative_pdf")
        or input_value.get("page_number") != manifest_case.get("page_number")
        or input_value.get("page_bbox_points") != manifest_case.get("page_bbox_points")
        or not _sha256(input_value.get("page_png_sha256"))
    ):
        raise ScoreError("dual_vlm_terminal_case_input_invalid")
    detection = _object(case.get("detection"))
    if detection.get("status") not in {"completed", "contract_invalid", "failed"}:
        raise ScoreError("dual_vlm_terminal_detection_status_invalid")
    detection_output = detection.get("output")
    detection_errors = validate_detection_output(
        detection_output,
        expected_document_id=case_id,
        expected_page_number=int(manifest_case["page_number"]),
    )
    if detection.get("status") in {"completed", "contract_invalid"}:
        model_view = detection_model_view(
            document_id=case_id,
            page_number=int(manifest_case["page_number"]),
            page_image_sha256=str(input_value["page_png_sha256"]),
        )
        _require_completed_operation(
            detection.get("operation"),
            expected_kind="table_region_detection",
            expected_provider="google",
            expected_model="models/gemini-3.5-flash",
            expected_crop_sha=str(input_value["page_png_sha256"]),
            expected_model_view=model_view,
            expected_schema=detection_schema(),
            expected_output=detection_output,
        )
    if detection.get("status") == "completed":
        if detection_errors or detection.get("contract_errors") != []:
            raise ScoreError("dual_vlm_terminal_detection_contract_invalid")
    elif not detection_errors and not detection.get("contract_errors"):
        raise ScoreError("dual_vlm_terminal_detection_failure_unexplained")
    candidates = (
        [item for item in _object(detection_output).get("candidates") or []]
        if not detection_errors
        else []
    )
    crops = case.get("crops")
    if not isinstance(crops, list) or len(crops) != len(candidates):
        raise ScoreError("dual_vlm_terminal_crop_cardinality_invalid")
    for crop, candidate in zip(crops, candidates):
        if candidate.get("state") == "uncertain":
            if (
                not isinstance(crop, dict)
                or crop.get("terminal_status") != "uncertain_not_extracted"
                or _object(crop.get("candidate")).get("candidate_id")
                != candidate.get("candidate_id")
            ):
                raise ScoreError("dual_vlm_terminal_uncertain_crop_invalid")
            continue
        _validate_terminal_crop(crop, candidate, manifest_case, input_value)


def _validate_terminal_crop(
    crop: Any,
    candidate: dict[str, Any],
    manifest_case: dict[str, Any],
    case_input: dict[str, Any],
) -> None:
    if not isinstance(crop, dict):
        raise ScoreError("dual_vlm_terminal_crop_invalid")
    if crop.get("terminal_status") == "failed":
        if (
            _object(crop.get("candidate")) != candidate
            or crop.get("crop_contract") is not None
            or crop.get("crop_reproducibility") is not None
            or crop.get("gemini") is not None
            or crop.get("openai") is not None
            or crop.get("consensus") is not None
            or crop.get("evidence") is not None
            or not isinstance(crop.get("failure_code"), str)
            or not crop["failure_code"]
        ):
            raise ScoreError("dual_vlm_terminal_failed_crop_invalid")
        return
    contract = _object(crop.get("crop_contract"))
    if validate_crop_contract(contract):
        raise ScoreError("dual_vlm_terminal_crop_contract_invalid")
    if (
        _object(crop.get("candidate")) != candidate
        or contract.get("document_id") != manifest_case.get("case_id")
        or contract.get("pdf_sha256") != manifest_case.get("pdf_sha256")
        or contract.get("page_number") != manifest_case.get("page_number")
        or contract.get("page_image_sha256") != case_input.get("page_png_sha256")
        or contract.get("normalized_bbox")
        != [round(float(item), 9) for item in candidate.get("bbox") or []]
        or contract.get("render_dpi") != manifest_case.get("render_dpi")
    ):
        raise ScoreError("dual_vlm_terminal_crop_identity_invalid")
    crop_sha = str(contract["rendered_image_sha256"])
    reproducibility = _object(crop.get("crop_reproducibility"))
    if (
        reproducibility.get("renders") != 2
        or reproducibility.get("byte_identical") is not True
        or reproducibility.get("first_sha256") != crop_sha
        or reproducibility.get("second_sha256") != crop_sha
    ):
        raise ScoreError("dual_vlm_terminal_crop_reproducibility_invalid")
    identity = {
        "document_id": str(manifest_case["case_id"]),
        "page_number": int(manifest_case["page_number"]),
        "crop_id": str(contract["crop_id"]),
        "crop_sha256": crop_sha,
    }
    model_view = fact_model_view(**identity)
    output_schema = financial_fact_schema()
    completed_outputs: dict[str, dict[str, Any]] = {}
    for arm, provider, model, kind in (
        (
            "gemini",
            "google",
            "models/gemini-3.5-flash",
            "gemini_crop_financial_fact_extraction",
        ),
        (
            "openai",
            "openai",
            "gpt-5.4-mini-2026-03-17",
            "openai_crop_financial_fact_extraction",
        ),
    ):
        arm_value = _object(crop.get(arm))
        if arm_value.get("status") not in {"completed", "contract_invalid"}:
            raise ScoreError("dual_vlm_terminal_provider_arm_status_invalid")
        output = arm_value.get("output")
        errors = validate_fact_extraction_output(output, expected_identity=identity)
        _require_completed_operation(
            arm_value.get("operation"),
            expected_kind=kind,
            expected_provider=provider,
            expected_model=model,
            expected_crop_sha=crop_sha,
            expected_model_view=model_view,
            expected_schema=output_schema,
            expected_output=output,
        )
        if arm_value.get("status") == "completed":
            if errors or arm_value.get("contract_errors") != []:
                raise ScoreError("dual_vlm_terminal_provider_output_invalid")
            completed_outputs[arm] = _object(output)
        elif not errors and not arm_value.get("contract_errors"):
            raise ScoreError("dual_vlm_terminal_provider_failure_unexplained")
    if len(completed_outputs) != 2:
        if crop.get("consensus") is not None or crop.get("evidence") is not None:
            raise ScoreError("dual_vlm_terminal_failed_arm_downstream_output_invalid")
        return
    if crop.get("same_crop_sha256_for_both_extractors") is not True:
        raise ScoreError("dual_vlm_terminal_same_crop_invalid")
    recomputed = compare_provider_facts(
        completed_outputs["gemini"], completed_outputs["openai"]
    )
    stored_consensus = crop.get("consensus")
    if validate_consensus(stored_consensus) or canonical_json_bytes(
        stored_consensus
    ) != canonical_json_bytes(recomputed):
        raise ScoreError("dual_vlm_terminal_consensus_replay_mismatch")
    evidence = crop.get("evidence")
    if validate_evidence_result(evidence):
        raise ScoreError("dual_vlm_terminal_evidence_contract_invalid")
    _validate_evidence_lineage(
        _object(evidence),
        consensus=recomputed,
        crop_contract=contract,
        medium=str(crop.get("evidence_medium") or ""),
    )


def _require_completed_operation(
    value: Any,
    *,
    expected_kind: str,
    expected_provider: str,
    expected_model: str,
    expected_crop_sha: str,
    expected_model_view: dict[str, Any],
    expected_schema: dict[str, Any],
    expected_output: Any,
) -> None:
    operation = _object(value)
    count = _object(operation.get("count_tokens"))
    attempt = _object(operation.get("attempt"))
    accounting = _object(operation.get("call_accounting"))
    schema_metadata = _schema_projection_metadata(operation)
    expected_schema_hash = sha256_json(expected_schema)
    expected_model_view_hash = sha256_json(expected_model_view)
    if (
        operation.get("kind") != expected_kind
        or operation.get("image_bytes", 0) <= 0
        or operation.get("model_view_bytes")
        != len(canonical_json_bytes(expected_model_view))
        or operation.get("schema_bytes") != len(canonical_json_bytes(expected_schema))
        or operation.get("json_output") != expected_output
        or accounting
        != {
            "count_or_preflight_calls_attempted": 1,
            "count_or_preflight_calls_completed": 1,
            "generate_calls_attempted": 1,
            "generate_calls_completed": 1,
        }
        or operation.get("hidden_retry") is not False
        or operation.get("provider_failover") is not False
        or operation.get("provenance_verified") is not True
        or operation.get("provenance_errors") != []
        or operation.get("failure_code") is not None
        or not isinstance(count.get("total_tokens"), int)
        or isinstance(count.get("total_tokens"), bool)
        or count.get("total_tokens") < 0
        or count.get("within_hard_guard") is not True
        or count.get("model_requested") != expected_model
        or count.get("canonical_schema_hash") != expected_schema_hash
        or schema_metadata is None
        or attempt.get("provider") != expected_provider
        or attempt.get("model_requested") != expected_model
        or attempt.get("model_resolved") != expected_model
        or attempt.get("attempt_number") != 1
        or attempt.get("attempt_lineage") != []
        or attempt.get("crop_sha256") != expected_crop_sha
        or attempt.get("model_view_hash") != expected_model_view_hash
        or attempt.get("canonical_schema_hash") != expected_schema_hash
        or attempt.get("terminal_failure_class") is not None
        or attempt.get("hidden_retry") is not False
        or attempt.get("provider_failover") is not False
    ):
        raise ScoreError("dual_vlm_terminal_provider_operation_invalid")


def _schema_projection_metadata(operation: dict[str, Any]) -> dict[str, Any] | None:
    count = _object(operation.get("count_tokens"))
    attempt = _object(operation.get("attempt"))
    canonical_hash = attempt.get("canonical_schema_hash")
    adapted_hash = attempt.get("adapted_schema_hash")
    transform_count = attempt.get("schema_transform_count")
    if (
        not isinstance(canonical_hash, str)
        or not _HEX_64.fullmatch(canonical_hash)
        or not isinstance(adapted_hash, str)
        or not _HEX_64.fullmatch(adapted_hash)
        or not isinstance(transform_count, int)
        or isinstance(transform_count, bool)
        or transform_count < 0
        or count.get("canonical_schema_hash") != canonical_hash
        or count.get("adapted_schema_hash") != adapted_hash
        or count.get("schema_transform_count") != transform_count
    ):
        return None
    return {
        "canonical_schema_hash": canonical_hash,
        "adapted_schema_hash": adapted_hash,
        "schema_transform_count": transform_count,
    }


def _validate_evidence_lineage(
    evidence: dict[str, Any],
    *,
    consensus: dict[str, Any],
    crop_contract: dict[str, Any],
    medium: str,
) -> None:
    if (
        evidence.get("medium") != medium
        or medium not in {"text_layer", "mixed", "raster"}
        or evidence.get("human_reference_used") is not False
        or evidence.get("table_construction_performed") is not False
        or evidence.get("value_normalization_performed") is not False
        or evidence.get("ocr_performed") is not False
        or evidence.get("input_facts_unchanged") is not True
    ):
        raise ScoreError("dual_vlm_terminal_evidence_boundary_invalid")
    entries = {
        str(entry["consensus_id"]): entry
        for entry in consensus["entries"]
        if entry.get("status") in AGREEMENT_STATUSES
        and isinstance(entry.get("canonical_fact"), dict)
    }
    maps = evidence.get("source_maps")
    if not isinstance(maps, list) or len(maps) != len(entries):
        raise ScoreError("dual_vlm_terminal_evidence_lineage_invalid")
    seen: set[str] = set()
    for source_map in maps:
        if not isinstance(source_map, dict):
            raise ScoreError("dual_vlm_terminal_evidence_lineage_invalid")
        fact_id = str(source_map.get("fact_id") or "")
        entry = entries.get(fact_id)
        source_identity = _object(source_map.get("source_identity"))
        if (
            entry is None
            or fact_id in seen
            or source_map.get("input_fact_sha256") != sha256_json(entry)
            or source_map.get("consensus_status") != entry.get("status")
            or source_map.get("medium") != medium
            or source_identity.get("pdf_sha256") != crop_contract.get("pdf_sha256")
            or source_identity.get("page_number") != crop_contract.get("page_number")
            or source_identity.get("crop_sha256")
            != crop_contract.get("rendered_image_sha256")
            or source_identity.get("table_bbox")
            != crop_contract.get("source_bbox_points")
        ):
            raise ScoreError("dual_vlm_terminal_evidence_lineage_invalid")
        seen.add(fact_id)
        if (
            medium == "raster"
            and source_map.get("automatic_acceptance_eligible") is not False
        ):
            raise ScoreError("dual_vlm_terminal_raster_auto_acceptance_invalid")
        if source_map.get(
            "automatic_acceptance_eligible"
        ) is True and not _complete_source_map(source_map):
            raise ScoreError("dual_vlm_terminal_auto_acceptance_provenance_invalid")


def _validate_human_reference(
    reference: dict[str, Any],
    seal: dict[str, Any],
    *,
    reference_sha: str,
    reference_size: int,
    manifest_sha: str,
    manifest: dict[str, Any],
) -> None:
    if (
        set(reference)
        != {
            "schema_version",
            "benchmark_id",
            "manifest_sha256",
            "human_reviewed",
            "reviewer",
            "lineage",
            "cases",
        }
        or reference.get("schema_version") != FINAL_REFERENCE_SCHEMA
    ):
        raise ScoreError("dual_vlm_human_reference_schema_invalid")
    if reference.get("benchmark_id") != manifest.get("benchmark_id"):
        raise ScoreError("dual_vlm_human_reference_benchmark_invalid")
    if reference.get("human_reviewed") is not True:
        raise ScoreError("dual_vlm_human_reference_required")
    reviewer = _object(reference.get("reviewer"))
    if set(reviewer) != {"kind", "identity", "reviewed_at"}:
        raise ScoreError("dual_vlm_human_reviewer_invalid")
    identity = str(reviewer.get("identity") or "").strip()
    if (
        reviewer.get("kind") != "human"
        or not identity
        or _reviewer_identity_forbidden(identity)
        or not _timezone_timestamp(reviewer.get("reviewed_at"))
    ):
        raise ScoreError("dual_vlm_human_reviewer_invalid")
    if reference.get("manifest_sha256") != manifest_sha:
        raise ScoreError("dual_vlm_human_reference_manifest_mismatch")
    if (
        set(seal)
        != {
            "schema_version",
            "reference_filename",
            "reference_sha256",
            "reference_size_bytes",
            "human_reviewed",
            "reviewer_identity",
            "reviewed_at",
            "manifest_sha256",
            "proposed_reference_sha256",
            "review_index_sha256",
            "review_decisions_sha256",
            "seal_sha256",
        }
        or seal.get("schema_version") != FINAL_REFERENCE_SEAL_SCHEMA
    ):
        raise ScoreError("dual_vlm_human_reference_seal_schema_invalid")
    if (
        seal.get("reference_filename") != "reference.human-reviewed.private.json"
        or seal.get("reference_sha256") != reference_sha
        or seal.get("reference_size_bytes") != reference_size
        or seal.get("human_reviewed") is not True
        or seal.get("manifest_sha256") != manifest_sha
        or seal.get("reviewer_identity") != identity
        or seal.get("reviewed_at") != reviewer.get("reviewed_at")
    ):
        raise ScoreError("dual_vlm_human_reference_seal_mismatch")
    unsigned = copy.deepcopy(seal)
    stored = unsigned.pop("seal_sha256", None)
    if stored != sha256_json(unsigned):
        raise ScoreError("dual_vlm_human_reference_seal_checksum_invalid")
    lineage = _object(reference.get("lineage"))
    if set(lineage) != {
        "proposed_reference_sha256",
        "review_index_sha256",
        "review_decisions_sha256",
        "decision_ledger_tail_sha256",
    } or any(not _sha256(lineage.get(key)) for key in lineage):
        raise ScoreError("dual_vlm_human_reference_lineage_invalid")
    if any(
        seal.get(key) != lineage.get(key)
        for key in (
            "proposed_reference_sha256",
            "review_index_sha256",
            "review_decisions_sha256",
        )
    ):
        raise ScoreError("dual_vlm_human_reference_lineage_mismatch")
    cases = reference.get("cases")
    if not isinstance(cases, list) or len(cases) != len(FROZEN_CASE_IDS):
        raise ScoreError("dual_vlm_human_reference_cases_invalid")
    case_ids = [str(_object(case).get("case_id") or "") for case in cases]
    if len(set(case_ids)) != len(case_ids) or set(case_ids) != set(FROZEN_CASE_IDS):
        raise ScoreError("dual_vlm_human_reference_cases_invalid")
    manifest_cases = {
        str(case["case_id"]): case
        for case in manifest["cases"]
        if isinstance(case, dict)
    }
    reference_tables = 0
    for case in cases:
        if not isinstance(case, dict) or set(case) != {
            "case_id",
            "document_id",
            "pdf_sha256",
            "page_number",
            "page_sha256",
            "expected_kind",
            "regions",
            "negative_review",
        }:
            raise ScoreError("dual_vlm_human_reference_case_invalid")
        case_id = str(case["case_id"])
        expected = manifest_cases[case_id]
        frozen = FROZEN_CASES[case_id]
        if (
            case.get("document_id") != case_id
            or case.get("pdf_sha256") != expected.get("pdf_sha256")
            or case.get("pdf_sha256") != frozen["pdf_sha256"]
            or case.get("page_number") != expected.get("page_number")
            or case.get("page_number") != frozen["page_number"]
            or not _sha256(case.get("page_sha256"))
            or case.get("expected_kind") != frozen["expected_kind"]
        ):
            raise ScoreError("dual_vlm_human_reference_case_identity_invalid")
        regions = case.get("regions")
        if not isinstance(regions, list):
            raise ScoreError("dual_vlm_human_reference_regions_invalid")
        if frozen["expected_kind"] == "negative":
            if regions or not _terminal_review(
                case.get("negative_review"), {"approve"}
            ):
                raise ScoreError("dual_vlm_human_reference_negative_invalid")
            continue
        if not regions or case.get("negative_review") is not None:
            raise ScoreError("dual_vlm_human_reference_regions_invalid")
        region_ids: set[str] = set()
        for region in regions:
            _validate_reference_region(region)
            region_id = str(region["region_id"])
            if region_id in region_ids:
                raise ScoreError("dual_vlm_human_reference_region_duplicate")
            region_ids.add(region_id)
            reference_tables += 1
    if reference_tables != int(manifest.get("expected_reference_tables") or -1):
        raise ScoreError("dual_vlm_human_reference_table_count_invalid")


def _validate_reference_region(region: Any) -> None:
    if not isinstance(region, dict) or set(region) != {
        "region_id",
        "bbox_normalized",
        "crop_sha256",
        "evidence_medium",
        "one_complete_table",
        "cuts",
        "includes_neighboring_prose",
        "includes_other_table",
        "facts",
        "review",
    }:
        raise ScoreError("dual_vlm_human_reference_region_invalid")
    cuts = _object(region.get("cuts"))
    if (
        not str(region.get("region_id") or "")
        or not _normalized_bbox(region.get("bbox_normalized"))
        or not _sha256(region.get("crop_sha256"))
        or region.get("evidence_medium") not in {"text_layer", "mixed", "raster"}
        or region.get("one_complete_table") is not True
        or set(cuts) != {"header", "total", "row", "column"}
        or any(cuts.get(key) is not False for key in cuts)
        or not isinstance(region.get("includes_neighboring_prose"), bool)
        or region.get("includes_other_table") is not False
        or not _terminal_review(region.get("review"), {"approve", "correct"})
    ):
        raise ScoreError("dual_vlm_human_reference_region_invalid")
    facts = region.get("facts")
    if not isinstance(facts, list):
        raise ScoreError("dual_vlm_human_reference_facts_invalid")
    fact_ids: set[str] = set()
    for wrapped in facts:
        if not isinstance(wrapped, dict) or set(wrapped) != {
            "fact",
            "review_decision",
            "review_note",
            "accepted_for_scoring",
        }:
            raise ScoreError("dual_vlm_human_reference_fact_wrapper_invalid")
        decision = wrapped.get("review_decision")
        accepted = wrapped.get("accepted_for_scoring")
        if decision not in {
            "confirm",
            "correct",
            "ambiguous",
            "reject",
        } or accepted is not (decision in {"confirm", "correct"}):
            raise ScoreError("dual_vlm_human_reference_fact_decision_invalid")
        if not str(wrapped.get("review_note") or "").strip():
            raise ScoreError("dual_vlm_human_reference_fact_note_invalid")
        fact = _object(wrapped.get("fact"))
        fact_id = str(fact.get("fact_id") or "")
        if not fact_id or fact_id in fact_ids:
            raise ScoreError("dual_vlm_human_reference_fact_duplicate")
        fact_ids.add(fact_id)
        if accepted:
            _validate_reference_fact(fact, crop_sha=str(region["crop_sha256"]))


def _validate_reference_fact(fact: dict[str, Any], *, crop_sha: str) -> None:
    required = {
        "fact_id",
        "fact_type",
        "row_label",
        "normalized_row_identity",
        "header_path",
        "visible_value",
        "numeric_value",
        "sign",
        "period",
        "currency",
        "unit",
        "scale",
        "entity",
        "qualifiers",
        "source_regions",
        "uncertainty",
        "alternative_interpretation",
    }
    if set(fact) != required:
        raise ScoreError("dual_vlm_human_reference_fact_invalid")
    if any(
        not str(fact.get(key) or "").strip()
        for key in ("fact_id", "fact_type", "row_label", "visible_value")
    ):
        raise ScoreError("dual_vlm_human_reference_fact_invalid")
    if fact.get("sign") not in {
        "positive",
        "negative",
        "zero",
        "unknown",
        "not_applicable",
    }:
        raise ScoreError("dual_vlm_human_reference_fact_invalid")
    for key in ("header_path", "qualifiers", "uncertainty"):
        if not isinstance(fact.get(key), list) or any(
            not isinstance(item, str) or not item.strip() for item in fact[key]
        ):
            raise ScoreError("dual_vlm_human_reference_fact_invalid")
    sources = _object(fact.get("source_regions"))
    if set(sources) != {"row_label", "header", "value", "context"}:
        raise ScoreError("dual_vlm_human_reference_fact_source_incomplete")
    headers = sources.get("header")
    context = sources.get("context")
    if (
        sources.get("row_label") is None
        or sources.get("value") is None
        or not isinstance(headers, list)
        or len(headers) != len(fact["header_path"])
        or not isinstance(context, list)
    ):
        raise ScoreError("dual_vlm_human_reference_fact_source_incomplete")
    if (
        not headers
        and not fact["header_path"]
        and "header_not_present_in_source" not in fact["uncertainty"]
    ):
        raise ScoreError("dual_vlm_human_reference_fact_source_incomplete")
    locators = [sources["row_label"], *headers, sources["value"], *context]
    for locator in locators:
        if (
            not isinstance(locator, dict)
            or set(locator) != {"artifact_sha256", "bbox_normalized", "visible_text"}
            or locator.get("artifact_sha256") != crop_sha
            or not _normalized_bbox(locator.get("bbox_normalized"))
            or not str(locator.get("visible_text") or "")
        ):
            raise ScoreError("dual_vlm_human_reference_fact_source_invalid")
    if (
        sources["row_label"]["visible_text"] != fact["row_label"]
        or sources["value"]["visible_text"] != fact["visible_value"]
        or any(
            locator["visible_text"] != expected
            for locator, expected in zip(headers, fact["header_path"])
        )
    ):
        raise ScoreError("dual_vlm_human_reference_fact_source_text_mismatch")


def _score_detection(
    terminal: dict[str, Any], reference: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, Any]:
    refs_by_case = {str(item["case_id"]): item for item in reference["cases"]}
    matches: list[dict[str, Any]] = []
    false_candidates: list[dict[str, Any]] = []
    missed_regions: list[dict[str, Any]] = []
    uncertain_candidates: list[dict[str, Any]] = []
    cut_regions: list[dict[str, Any]] = []
    merged_candidates: list[dict[str, Any]] = []
    split_regions: list[dict[str, Any]] = []
    reproducibility_failures: list[dict[str, Any]] = []
    detection_contract_failures: list[dict[str, Any]] = []
    predicted_total = 0
    reference_total = sum(
        1
        for case in reference["cases"]
        for region in case.get("regions") or []
        if _object(region.get("review")).get("decision") in {"approve", "correct"}
    )
    for case in terminal.get("cases") or []:
        case_id = str(case.get("case_id") or "")
        reference_case = refs_by_case.get(case_id, {})
        ref_regions = [
            region
            for region in reference_case.get("regions") or []
            if _object(region.get("review")).get("decision") in {"approve", "correct"}
        ]
        detection_arm = _object(case.get("detection"))
        if (
            detection_arm.get("status") != "completed"
            or detection_arm.get("contract_errors") != []
        ):
            detection_contract_failures.append(
                {
                    "case_id": case_id,
                    "status": detection_arm.get("status"),
                    "contract_errors": detection_arm.get("contract_errors"),
                }
            )
        detection = (
            _object(detection_arm.get("output"))
            if detection_arm.get("status") == "completed"
            else {}
        )
        candidates = [
            item for item in detection.get("candidates") or [] if isinstance(item, dict)
        ]
        present = [item for item in candidates if item.get("state") == "present"]
        uncertain_candidates.extend(
            {"case_id": case_id, "candidate_id": item.get("candidate_id")}
            for item in candidates
            if item.get("state") == "uncertain"
        )
        predicted_total += len(present)
        crop_by_id = {
            str(_object(item.get("candidate")).get("candidate_id")): (index, item)
            for index, item in enumerate(case.get("crops") or [])
            if isinstance(item, dict)
        }
        pair_candidates: list[tuple[float, int, int]] = []
        for pred_index, predicted in enumerate(present):
            for ref_index, region in enumerate(ref_regions):
                iou = bbox_iou(predicted["bbox"], region["bbox_normalized"])
                if iou >= float(manifest["scoring_policy"]["detection_iou_threshold"]):
                    pair_candidates.append((-iou, pred_index, ref_index))
        used_pred: set[int] = set()
        used_ref: set[int] = set()
        for negative_iou, pred_index, ref_index in sorted(pair_candidates):
            if pred_index in used_pred or ref_index in used_ref:
                continue
            used_pred.add(pred_index)
            used_ref.add(ref_index)
            predicted = present[pred_index]
            region = ref_regions[ref_index]
            crop_index, crop = crop_by_id.get(
                str(predicted.get("candidate_id")), (None, {})
            )
            record = {
                "case_id": case_id,
                "candidate_id": predicted.get("candidate_id"),
                "crop_index": crop_index,
                "reference_region_id": region.get("region_id"),
                "iou": round(-negative_iou, 6),
                "reference_evidence_medium": region.get("evidence_medium"),
            }
            matches.append(record)
            if not _bbox_contains(predicted["bbox"], region["bbox_normalized"], 0.0):
                cut_regions.append(record)
            reproducibility = _object(crop.get("crop_reproducibility"))
            if (
                reproducibility.get("byte_identical") is not True
                or crop.get("same_crop_sha256_for_both_extractors") is not True
            ):
                reproducibility_failures.append(record)
        for index, predicted in enumerate(present):
            if index not in used_pred:
                false_candidates.append(
                    {
                        "case_id": case_id,
                        "candidate_id": predicted.get("candidate_id"),
                    }
                )
            overlaps = [
                region
                for region in ref_regions
                if bbox_iou(predicted["bbox"], region["bbox_normalized"]) >= 0.1
            ]
            if len(overlaps) > 1:
                merged_candidates.append(
                    {
                        "case_id": case_id,
                        "candidate_id": predicted.get("candidate_id"),
                        "reference_region_ids": [
                            item["region_id"] for item in overlaps
                        ],
                    }
                )
        for index, region in enumerate(ref_regions):
            if index not in used_ref:
                missed_regions.append(
                    {"case_id": case_id, "reference_region_id": region.get("region_id")}
                )
            overlaps = [
                predicted
                for predicted in present
                if bbox_iou(predicted["bbox"], region["bbox_normalized"]) >= 0.1
            ]
            if len(overlaps) > 1:
                split_regions.append(
                    {
                        "case_id": case_id,
                        "reference_region_id": region.get("region_id"),
                        "candidate_ids": [
                            item.get("candidate_id") for item in overlaps
                        ],
                    }
                )
    matched_region_keys = {
        (str(item["case_id"]), str(item["reference_region_id"])) for item in matches
    }
    missed_regions = [
        {
            "case_id": str(case["case_id"]),
            "reference_region_id": region.get("region_id"),
        }
        for case in reference["cases"]
        for region in case.get("regions") or []
        if _object(region.get("review")).get("decision") in {"approve", "correct"}
        and (str(case["case_id"]), str(region.get("region_id")))
        not in matched_region_keys
    ]
    found = len(matches)
    precision = _ratio(found, predicted_total)
    recall = _ratio(found, reference_total)
    return {
        "reference_tables": reference_total,
        "predicted_tables": predicted_total,
        "found_reference_tables": found,
        "false_tables": len(false_candidates),
        "missed_tables": len(missed_regions),
        "precision": precision,
        "recall": recall,
        "f1": _f1(precision, recall),
        "mean_matched_iou": (
            round(sum(item["iou"] for item in matches) / len(matches), 6)
            if matches
            else None
        ),
        "cut_reference_tables": len(cut_regions),
        "merged_reference_tables": len(merged_candidates),
        "split_reference_tables": len(split_regions),
        "uncertain_candidates": len(uncertain_candidates),
        "crop_reproducibility_failures": len(reproducibility_failures),
        "detection_contract_failures": len(detection_contract_failures),
        "matches": matches,
        "false_candidates": false_candidates,
        "missed_regions": missed_regions,
        "cut_regions": cut_regions,
        "merged_candidates": merged_candidates,
        "split_regions": split_regions,
        "uncertain_candidate_details": uncertain_candidates,
        "crop_reproducibility_failure_details": reproducibility_failures,
        "detection_contract_failure_details": detection_contract_failures,
    }


def _detection_gate(value: dict[str, Any], manifest: dict[str, Any]) -> bool:
    policy = manifest["scoring_policy"]
    return bool(
        value["recall"] == float(policy["detection_recall_minimum"])
        and value["precision"] is not None
        and value["precision"] >= float(policy["detection_precision_minimum"])
        and value["cut_reference_tables"] <= int(policy["cut_reference_tables_allowed"])
        and value["merged_reference_tables"]
        <= int(policy["merged_reference_tables_allowed"])
        and value["split_reference_tables"]
        <= int(policy["split_reference_tables_allowed"])
        and value["uncertain_candidates"] == 0
        and value["crop_reproducibility_failures"] == 0
        and value["detection_contract_failures"] == 0
    )


def _score_facts(
    terminal: dict[str, Any], reference: dict[str, Any], detection: dict[str, Any]
) -> dict[str, Any]:
    reference_index = _reference_index(reference)
    match_by_crop = {
        (item["case_id"], item["crop_index"]): item
        for item in detection["matches"]
        if item.get("crop_index") is not None
    }
    region_to_crop = {
        (item["case_id"], str(item["reference_region_id"])): int(item["crop_index"])
        for item in detection["matches"]
        if item.get("crop_index") is not None
    }
    reference_facts: list[dict[str, Any]] = []
    for key, refs in reference_index.items():
        medium = _reference_region_medium(reference, key)
        crop_index = region_to_crop.get(key, -1)
        reference_facts.extend(
            _tag_fact(item, key[0], crop_index, medium) for item in refs
        )
    gemini_predictions: list[dict[str, Any]] = []
    openai_predictions: list[dict[str, Any]] = []
    consensus_predictions: list[dict[str, Any]] = []
    evidence_predictions: list[dict[str, Any]] = []
    agreement_counts: dict[str, int] = {}
    evidence_status_counts: dict[str, int] = {}
    provider_contract_failures = {"gemini": 0, "openai": 0}
    orphan_auto_acceptances = 0
    unsupported_auto_acceptances = 0
    raster = {
        "reference_facts": sum(
            1 for item in reference_facts if item.get("medium") == "raster"
        ),
        "consensus_facts": 0,
        "models_agree_vision_only": 0,
        "automatic_acceptance_eligible": 0,
        "human_review_required_facts": 0,
    }
    for case in terminal.get("cases") or []:
        case_id = str(case.get("case_id") or "")
        for crop_index, crop in enumerate(case.get("crops") or []):
            if (
                not isinstance(crop, dict)
                or crop.get("terminal_status") == "uncertain_not_extracted"
            ):
                continue
            match = match_by_crop.get((case_id, crop_index))
            region_key = (
                (
                    case_id,
                    str(match["reference_region_id"]),
                )
                if match
                else None
            )
            reference_medium = (
                str(match.get("reference_evidence_medium")) if match else None
            )
            runtime_medium = str(crop.get("evidence_medium") or "") or None
            medium = reference_medium or runtime_medium
            for provider_name, target in (
                ("gemini", gemini_predictions),
                ("openai", openai_predictions),
            ):
                arm = _object(crop.get(provider_name))
                if arm.get("status") != "completed":
                    provider_contract_failures[provider_name] += 1
                output = _object(arm.get("output"))
                target.extend(
                    _tag_provider_fact(item, case_id, crop_index, medium)
                    for item in output.get("facts") or []
                    if isinstance(item, dict)
                )
            consensus = _object(crop.get("consensus"))
            entries_by_id: dict[str, dict[str, Any]] = {}
            for entry in consensus.get("entries") or []:
                if not isinstance(entry, dict):
                    continue
                status = str(entry.get("status") or "")
                agreement_counts[status] = agreement_counts.get(status, 0) + 1
                entries_by_id[str(entry.get("consensus_id"))] = entry
                if status in AGREEMENT_STATUSES and isinstance(
                    entry.get("canonical_fact"), dict
                ):
                    prediction = _tag_consensus_fact(entry, case_id, crop_index, medium)
                    consensus_predictions.append(prediction)
                    if reference_medium == "raster" or runtime_medium == "raster":
                        raster["consensus_facts"] += 1
            evidence = _object(crop.get("evidence"))
            for source_map in evidence.get("source_maps") or []:
                if not isinstance(source_map, dict):
                    continue
                status = str(source_map.get("evidence_status") or "")
                evidence_status_counts[status] = (
                    evidence_status_counts.get(status, 0) + 1
                )
                if (
                    source_map.get("strongest_consensus_evidence_status")
                    == "models_agree_vision_only"
                ):
                    raster["models_agree_vision_only"] += 1
                if source_map.get("automatic_acceptance_eligible") is not True:
                    continue
                consensus_entry = entries_by_id.get(str(source_map.get("fact_id")))
                if not consensus_entry:
                    orphan_auto_acceptances += 1
                    continue
                prediction = _tag_consensus_fact(
                    consensus_entry, case_id, crop_index, medium
                )
                prediction["source_map"] = source_map
                evidence_predictions.append(prediction)
                if (
                    region_key is None
                    or reference_medium not in {"text_layer", "mixed"}
                    or runtime_medium not in {"text_layer", "mixed"}
                ):
                    unsupported_auto_acceptances += 1
                if reference_medium == "raster" or runtime_medium == "raster":
                    raster["automatic_acceptance_eligible"] += 1

    gemini_score = _fact_metrics(reference_facts, gemini_predictions)
    openai_score = _fact_metrics(reference_facts, openai_predictions)
    consensus_score = _fact_metrics(reference_facts, consensus_predictions)
    supported_reference = [
        item
        for item in reference_facts
        if item.get("medium") in {"text_layer", "mixed"}
    ]
    evidence_score = _fact_metrics(supported_reference, evidence_predictions)
    accepted_total = len(evidence_predictions) + orphan_auto_acceptances
    complete_source_maps = sum(
        _complete_source_map(_object(item.get("source_map")))
        for item in evidence_predictions
    )
    false_accepted = evidence_score["false_positive_facts"] + orphan_auto_acceptances
    raster["human_review_required_facts"] = max(
        0, raster["reference_facts"] - raster["automatic_acceptance_eligible"]
    )
    evidence_score.update(
        {
            "accepted_facts": accepted_total,
            "supported_reference_facts": len(supported_reference),
            "provenance_coverage": _ratio(complete_source_maps, accepted_total),
            "false_accepted_facts": false_accepted,
            "invented_accepted_values": false_accepted,
            "mutated_accepted_values": evidence_score["materially_wrong_matched_facts"],
            "orphan_auto_acceptances": orphan_auto_acceptances,
            "unsupported_auto_acceptances": unsupported_auto_acceptances,
            "human_review_required_facts": max(
                0, len(supported_reference) - evidence_score["true_positive_facts"]
            ),
            "human_review_rate": _ratio(
                max(
                    0, len(supported_reference) - evidence_score["true_positive_facts"]
                ),
                len(supported_reference),
            ),
        }
    )
    best_single_provider = _best_single_provider(gemini_score, openai_score)
    return {
        "reference_facts_total": len(reference_facts),
        "supported_text_layer_reference_facts": len(supported_reference),
        "gemini_alone": gemini_score,
        "openai_alone": openai_score,
        "best_single_provider": best_single_provider,
        "raw_model_agreement": agreement_counts,
        "canonical_consensus": consensus_score,
        "consensus_plus_evidence": evidence_score,
        "evidence_status_counts": evidence_status_counts,
        "provider_contract_failures": provider_contract_failures,
        "raster_separate": raster,
    }


def _reference_index(
    reference: dict[str, Any],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    result: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for case in reference["cases"]:
        case_id = str(case["case_id"])
        for region in case.get("regions") or []:
            facts = [
                _object(item.get("fact"))
                for item in region.get("facts") or []
                if isinstance(item, dict) and item.get("accepted_for_scoring") is True
            ]
            result[(case_id, str(region["region_id"]))] = facts
    return result


def _reference_contract_diagnostics(reference: dict[str, Any]) -> dict[str, Any]:
    fact_type_counts: dict[str, int] = {}
    null_field_counts = {
        key: 0
        for key in (
            "normalized_row_identity",
            "period",
            "currency",
            "unit",
            "scale",
            "entity",
        )
    }
    fact_count = 0
    for case in reference.get("cases") or []:
        for region in case.get("regions") or []:
            for reviewed in region.get("facts") or []:
                fact = _object(reviewed.get("fact"))
                fact_type = str(fact.get("fact_type") or "")
                fact_type_counts[fact_type] = fact_type_counts.get(fact_type, 0) + 1
                fact_count += 1
                for key in null_field_counts:
                    if fact.get(key) is None:
                        null_field_counts[key] += 1
    unsupported = sorted(set(fact_type_counts) - FACT_TYPES)
    return {
        "reference_facts": fact_count,
        "reference_fact_type_counts": dict(sorted(fact_type_counts.items())),
        "provider_fact_types": sorted(FACT_TYPES),
        "unsupported_reference_fact_types": unsupported,
        "fact_type_contract_compatible": not unsupported,
        "exact_fact_type_match_required_for_true_positive": True,
        "provider_precision_recall_interpretation": (
            "contract_limited" if unsupported else "directly_comparable"
        ),
        "null_field_counts": null_field_counts,
    }


def _reference_region_medium(
    reference: dict[str, Any], key: tuple[str, str]
) -> str | None:
    for case in reference["cases"]:
        if str(case["case_id"]) != key[0]:
            continue
        for region in case.get("regions") or []:
            if str(region.get("region_id")) == key[1]:
                return str(region.get("evidence_medium") or "") or None
    return None


def _tag_fact(
    fact: dict[str, Any], case_id: str, crop_index: int, medium: str | None
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "crop_index": crop_index,
        "medium": medium,
        "canonical": _canonical_reference_fact(fact),
        "raw": fact,
    }


def _tag_provider_fact(
    fact: dict[str, Any], case_id: str, crop_index: int, medium: str | None
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "crop_index": crop_index,
        "medium": medium,
        "canonical": canonicalize_fact(fact),
        "raw": fact,
    }


def _tag_consensus_fact(
    entry: dict[str, Any], case_id: str, crop_index: int, medium: str | None
) -> dict[str, Any]:
    fact = _object(entry.get("canonical_fact"))
    return {
        "case_id": case_id,
        "crop_index": crop_index,
        "medium": medium,
        "consensus_id": entry.get("consensus_id"),
        "canonical": copy.deepcopy(fact.get("canonical_identity") or {}),
        "raw": fact,
    }


def _canonical_reference_fact(fact: dict[str, Any]) -> dict[str, Any]:
    currency = fact.get("currency")
    currency_code = (
        str(currency).upper()
        if isinstance(currency, str) and re.fullmatch(r"[A-Za-z]{3}", currency)
        else None
    )
    currency_literal = None if currency_code else normalize_whitespace(currency)
    return {
        "fact_type": str(fact.get("fact_type") or "unknown"),
        "row": normalize_text(
            fact.get("normalized_row_identity") or fact.get("row_label")
        ),
        "header_path": tuple(
            normalize_text(item) for item in fact.get("header_path") or []
        ),
        "value_exact": normalize_whitespace(fact.get("visible_value")),
        "numeric_value": _canonical_decimal(fact.get("numeric_value")),
        "sign": str(fact.get("sign") or "unknown"),
        "period": normalize_text(fact.get("period")),
        "currency_literal": currency_literal,
        "currency_code": currency_code,
        "unit": normalize_text(fact.get("unit")),
        "scale": normalize_text(fact.get("scale")),
        "entity": normalize_text(fact.get("entity")),
        "qualifiers": tuple(
            sorted(normalize_text(item) for item in fact.get("qualifiers") or [])
        ),
    }


_FACT_FIELDS = (
    "fact_type",
    "row",
    "header_path",
    "value_exact",
    "numeric_value",
    "sign",
    "period",
    "currency_literal",
    "currency_code",
    "unit",
    "scale",
    "entity",
    "qualifiers",
)
_NON_CURRENCY_FACT_FIELDS = tuple(
    field
    for field in _FACT_FIELDS
    if field not in {"currency_literal", "currency_code"}
)


def _fact_metrics(
    references: list[dict[str, Any]], predictions: list[dict[str, Any]]
) -> dict[str, Any]:
    exact_candidates: list[tuple[int, int]] = []
    for ref_index, reference in enumerate(references):
        for pred_index, prediction in enumerate(predictions):
            if (
                _same_scope(reference, prediction)
                and all(
                    reference["canonical"].get(field)
                    == prediction["canonical"].get(field)
                    for field in _NON_CURRENCY_FACT_FIELDS
                )
                and _currency_matches(reference["canonical"], prediction["canonical"])
            ):
                exact_candidates.append((ref_index, pred_index))
    used_refs: set[int] = set()
    used_predictions: set[int] = set()
    for ref_index, pred_index in exact_candidates:
        if ref_index not in used_refs and pred_index not in used_predictions:
            used_refs.add(ref_index)
            used_predictions.add(pred_index)
    true_positive = len(used_refs)
    false_positive = len(predictions) - len(used_predictions)
    false_negative = len(references) - len(used_refs)
    field_counts = {field: {"correct": 0, "total": 0} for field in _FACT_FIELDS}
    material_wrong = 0
    pairs = _best_anchor_pairs(references, predictions)
    for ref_index, pred_index in pairs:
        reference = references[ref_index]["canonical"]
        prediction = predictions[pred_index]["canonical"]
        wrong = False
        for field in _FACT_FIELDS:
            expected = reference.get(field)
            if expected is None or expected == ():
                continue
            field_counts[field]["total"] += 1
            if expected == prediction.get(field):
                field_counts[field]["correct"] += 1
            else:
                wrong = True
        material_wrong += int(wrong)
    precision = _ratio(true_positive, len(predictions))
    recall = _ratio(true_positive, len(references))
    return {
        "reference_facts": len(references),
        "predicted_facts": len(predictions),
        "true_positive_facts": true_positive,
        "false_positive_facts": false_positive,
        "false_negative_facts": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": _f1(precision, recall),
        "exact_numeric_value": _field_rate(field_counts["numeric_value"]),
        "correct_sign": _field_rate(field_counts["sign"]),
        "correct_period": _field_rate(field_counts["period"]),
        "correct_currency": _combined_currency_rate(field_counts),
        "correct_unit": _field_rate(field_counts["unit"]),
        "correct_scale": _field_rate(field_counts["scale"]),
        "correct_row_header_relationship": _combined_row_header_rate(field_counts),
        "materially_wrong_matched_facts": material_wrong,
        "field_counts": field_counts,
    }


def _best_anchor_pairs(
    references: list[dict[str, Any]], predictions: list[dict[str, Any]]
) -> list[tuple[int, int]]:
    candidates: list[tuple[int, int, int]] = []
    for ref_index, reference in enumerate(references):
        for pred_index, prediction in enumerate(predictions):
            if not _same_scope(reference, prediction):
                continue
            left = reference["canonical"]
            right = prediction["canonical"]
            score = 0
            if left.get("row") and left.get("row") == right.get("row"):
                score += 50
            if left.get("value_exact") == right.get("value_exact"):
                score += 40
            if left.get("numeric_value") and left.get("numeric_value") == right.get(
                "numeric_value"
            ):
                score += 20
            if left.get("header_path") == right.get("header_path"):
                score += 20
            if score >= 50:
                candidates.append((-score, ref_index, pred_index))
    used_refs: set[int] = set()
    used_predictions: set[int] = set()
    result: list[tuple[int, int]] = []
    for _score, ref_index, pred_index in sorted(candidates):
        if ref_index in used_refs or pred_index in used_predictions:
            continue
        used_refs.add(ref_index)
        used_predictions.add(pred_index)
        result.append((ref_index, pred_index))
    return result


def _same_scope(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        left["case_id"] == right["case_id"]
        and left["crop_index"] == right["crop_index"]
    )


def _extraction_gate(facts: dict[str, Any], manifest: dict[str, Any]) -> bool:
    score = facts["canonical_consensus"]
    policy = manifest["scoring_policy"]
    return bool(
        not any(facts["provider_contract_failures"].values())
        and score["precision"] is not None
        and score["precision"] >= float(policy["consensus_fact_precision_minimum"])
        and score["recall"] is not None
        and score["recall"] >= float(policy["consensus_fact_recall_minimum"])
    )


def _evidence_gate(facts: dict[str, Any], manifest: dict[str, Any]) -> bool:
    score = facts["consensus_plus_evidence"]
    policy = manifest["scoring_policy"]
    return bool(
        score["supported_reference_facts"] > 0
        and score["precision"] is not None
        and score["precision"] >= float(policy["accepted_fact_precision_minimum"])
        and score["recall"] is not None
        and score["recall"] >= float(policy["accepted_fact_recall_minimum"])
        and score["human_review_rate"] is not None
        and score["human_review_rate"] <= float(policy["human_review_rate_maximum"])
        and score["provenance_coverage"]
        == float(policy["accepted_provenance_coverage_minimum"])
        and score["false_accepted_facts"] <= int(policy["false_accepted_facts_maximum"])
        and score["invented_accepted_values"]
        <= int(policy["invented_accepted_values_maximum"])
        and score["mutated_accepted_values"]
        <= int(policy["mutated_accepted_values_maximum"])
        and score["orphan_auto_acceptances"] == 0
        and score["unsupported_auto_acceptances"] == 0
        and facts["raster_separate"]["automatic_acceptance_eligible"] == 0
    )


def _best_single_provider(
    gemini: dict[str, Any], openai: dict[str, Any]
) -> dict[str, Any]:
    def rank(value: dict[str, Any]) -> tuple[float, float, int, float]:
        return (
            _rate(value.get("precision")),
            _rate(value.get("recall")),
            -int(value.get("false_positive_facts") or 0),
            _rate(value.get("f1")),
        )

    gemini_rank = rank(gemini)
    openai_rank = rank(openai)
    provider = (
        "tie"
        if gemini_rank == openai_rank
        else ("gemini" if gemini_rank > openai_rank else "openai")
    )
    return {
        "provider": provider,
        "gemini_rank": list(gemini_rank),
        "openai_rank": list(openai_rank),
    }


def _material_improvement(facts: dict[str, Any], manifest: dict[str, Any]) -> bool:
    evidence = facts["consensus_plus_evidence"]
    singles = (facts["gemini_alone"], facts["openai_alone"])
    if not facts["canonical_consensus"]["predicted_facts"]:
        return False
    best_precision = max(_rate(item.get("precision")) for item in singles)
    fewest_false_accepts = min(
        int(item.get("false_positive_facts") or 0) for item in singles
    )
    evidence_precision = _rate(evidence.get("precision"))
    evidence_false_accepts = int(evidence.get("false_positive_facts") or 0)
    no_worse = (
        evidence_precision >= best_precision
        and evidence_false_accepts <= fewest_false_accepts
    )
    strictly_better = (
        evidence_precision > best_precision
        or evidence_false_accepts < fewest_false_accepts
    )
    safe_recall = _rate(evidence.get("recall")) >= float(
        manifest["scoring_policy"]["accepted_fact_recall_minimum"]
    )
    return bool(no_worse and strictly_better and safe_recall)


def _conclusion(
    *,
    detection_passed: bool,
    extraction_passed: bool,
    evidence_passed: bool,
    material_improvement: bool,
    facts: dict[str, Any],
) -> str:
    if (
        detection_passed
        and extraction_passed
        and evidence_passed
        and material_improvement
    ):
        return "DUAL_VLM_FACT_ARCHITECTURE_RECOMMENDED"
    evidence = facts["consensus_plus_evidence"]
    if (
        detection_passed
        and evidence["accepted_facts"] > 0
        and evidence["false_accepted_facts"] == 0
        and evidence["provenance_coverage"] == 1.0
    ):
        return "DUAL_VLM_FACT_ARCHITECTURE_PROMISING_BUT_NOT_READY"
    return "DUAL_VLM_FACT_ARCHITECTURE_NOT_JUSTIFIED"


def _operational_metrics(
    terminal: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, Any]:
    provider_contracts = manifest["provider_contracts"]
    result = {
        key: {
            "provider": (provider_contracts[key]["provider"] if key != "ocr" else None),
            "model_requested": (
                provider_contracts[key]["model_id"] if key != "ocr" else None
            ),
            "prompt_contract_version": (
                provider_contracts[key]["prompt_contract_version"]
                if key != "ocr"
                else None
            ),
            "models_resolved": [],
            "expected_operations": 0,
            "operations": 0,
            "count_or_preflight_calls": 0,
            "count_or_preflight_calls_completed": 0,
            "generate_calls": 0,
            "generate_calls_completed": 0,
            "image_bytes": 0,
            "prompt_schema_bytes": 0,
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "latency_ms": 0,
            "estimated_cost_microusd": 0.0,
            "malformed_outputs": 0,
            "transport_failures": 0,
            "operation_contract_failures": 0,
            "schema_metadata_valid_operations": 0,
            "schema_metadata_invalid_operations": 0,
            "canonical_schema_hashes": [],
            "adapted_schema_hashes": [],
            "schema_transform_count_histogram": {},
            "schema_transform_total": 0,
            "canonical_schema_equals_adapted_operations": 0,
            "canonical_schema_differs_from_adapted_operations": 0,
            "execution_contract_passed": False,
        }
        for key in ("detection", "gemini_extraction", "openai_extraction", "ocr")
    }
    result["detection"]["expected_operations"] = len(terminal.get("cases") or [])
    for case in terminal.get("cases") or []:
        detection_arm = _object(case.get("detection"))
        detection = _object(detection_arm.get("operation"))
        if detection:
            _add_operation(
                result["detection"],
                detection,
                manifest,
                "detection",
                arm_status=str(detection_arm.get("status") or ""),
            )
        else:
            result["detection"]["operation_contract_failures"] += 1
        for crop in case.get("crops") or []:
            if (
                not isinstance(crop, dict)
                or crop.get("terminal_status") == "uncertain_not_extracted"
            ):
                continue
            for arm, key in (
                ("gemini", "gemini_extraction"),
                ("openai", "openai_extraction"),
            ):
                result[key]["expected_operations"] += 1
                arm_value = _object(crop.get(arm))
                operation = _object(arm_value.get("operation"))
                if operation:
                    _add_operation(
                        result[key],
                        operation,
                        manifest,
                        key,
                        arm_status=str(arm_value.get("status") or ""),
                    )
                else:
                    result[key]["operation_contract_failures"] += 1
    parser = _object(terminal.get("parser_accounting"))
    result["parser"] = {
        "duration_ms": parser.get("total_duration_ms"),
        "unique_documents": len(parser.get("unique_documents") or []),
        "table_construction_performed": parser.get("table_construction_performed"),
    }
    result["ocr"].update(
        {
            "adapter": "independent_ocr_unavailable",
            "performed": False,
            "estimated_cost_microusd": 0.0,
            "execution_contract_passed": True,
        }
    )
    for key in ("detection", "gemini_extraction", "openai_extraction"):
        value = result[key]
        value["models_resolved"] = sorted(set(value["models_resolved"]))
        value["canonical_schema_hashes"] = sorted(set(value["canonical_schema_hashes"]))
        value["adapted_schema_hashes"] = sorted(set(value["adapted_schema_hashes"]))
        value["schema_transform_count_histogram"] = dict(
            sorted(
                value["schema_transform_count_histogram"].items(),
                key=lambda item: int(item[0]),
            )
        )
        value["execution_contract_passed"] = bool(
            value["operations"] == value["expected_operations"]
            and value["count_or_preflight_calls"] == value["expected_operations"]
            and value["count_or_preflight_calls_completed"]
            == value["expected_operations"]
            and value["generate_calls"] == value["expected_operations"]
            and value["generate_calls_completed"] == value["expected_operations"]
            and value["operation_contract_failures"] == 0
        )
    return result


def _add_operation(
    target: dict[str, Any],
    operation: dict[str, Any],
    manifest: dict[str, Any],
    key: str,
    *,
    arm_status: str,
) -> None:
    target["operations"] += 1
    accounting = _object(operation.get("call_accounting"))
    target["count_or_preflight_calls"] += _nonnegative(
        accounting.get("count_or_preflight_calls_attempted")
    )
    target["count_or_preflight_calls_completed"] += _nonnegative(
        accounting.get("count_or_preflight_calls_completed")
    )
    attempt = _object(operation.get("attempt"))
    schema_metadata = _schema_projection_metadata(operation)
    if schema_metadata is None:
        target["schema_metadata_invalid_operations"] += 1
    else:
        target["schema_metadata_valid_operations"] += 1
        canonical_schema_hash = schema_metadata["canonical_schema_hash"]
        adapted_schema_hash = schema_metadata["adapted_schema_hash"]
        schema_transform_count = schema_metadata["schema_transform_count"]
        target["canonical_schema_hashes"].append(canonical_schema_hash)
        target["adapted_schema_hashes"].append(adapted_schema_hash)
        transform_key = str(schema_transform_count)
        target["schema_transform_count_histogram"][transform_key] = (
            target["schema_transform_count_histogram"].get(transform_key, 0) + 1
        )
        target["schema_transform_total"] += schema_transform_count
        if canonical_schema_hash == adapted_schema_hash:
            target["canonical_schema_equals_adapted_operations"] += 1
        else:
            target["canonical_schema_differs_from_adapted_operations"] += 1
    target["generate_calls"] += _nonnegative(accounting.get("generate_calls_attempted"))
    target["generate_calls_completed"] += _nonnegative(
        accounting.get("generate_calls_completed")
    )
    resolved_model = attempt.get("model_resolved")
    if isinstance(resolved_model, str) and resolved_model:
        target["models_resolved"].append(resolved_model)
    target["image_bytes"] += _nonnegative(operation.get("image_bytes"))
    target["prompt_schema_bytes"] += _nonnegative(operation.get("model_view_bytes"))
    target["prompt_schema_bytes"] += _nonnegative(operation.get("schema_bytes"))
    usage = _object(attempt.get("usage"))
    input_value = usage.get("input_tokens")
    if (
        not isinstance(input_value, int)
        or isinstance(input_value, bool)
        or input_value < 0
    ):
        input_value = _object(operation.get("count_tokens")).get("total_tokens")
    input_tokens = _nonnegative(input_value)
    cached_tokens = _nonnegative(usage.get("cached_input_tokens"))
    output_tokens = _nonnegative(usage.get("output_tokens"))
    target["input_tokens"] += input_tokens
    target["cached_input_tokens"] += cached_tokens
    target["output_tokens"] += output_tokens
    target["latency_ms"] += _nonnegative(attempt.get("duration_ms"))
    target["malformed_outputs"] += int(
        attempt.get("terminal_failure_class") == "parse_failure"
        or arm_status == "contract_invalid"
    )
    target["transport_failures"] += int(
        attempt.get("terminal_failure_class")
        in {"timeout", "timeout_or_transport", "provider_server", "rate_limit"}
        or operation.get("failure_code") is not None
    )
    pricing = manifest["provider_contracts"][key]
    if (
        operation.get("count_tokens") is None
        or not attempt
        or attempt.get("attempt_number") != 1
        or attempt.get("attempt_lineage") != []
        or attempt.get("provider") != pricing["provider"]
        or attempt.get("model_requested") != pricing["model_id"]
        or attempt.get("model_resolved") != pricing["model_id"]
        or attempt.get("hidden_retry") is not False
        or attempt.get("provider_failover") is not False
        or arm_status != "completed"
    ):
        target["operation_contract_failures"] += 1
    uncached = max(0, input_tokens - cached_tokens)
    cost = uncached * float(pricing["input_usd_per_1m_tokens"])
    cost += cached_tokens * float(
        pricing.get(
            "cached_input_usd_per_1m_tokens", pricing["input_usd_per_1m_tokens"]
        )
    )
    cost += output_tokens * float(pricing["output_usd_per_1m_tokens"])
    target["estimated_cost_microusd"] += round(cost, 6)


def _provider_structured_output_comparability(
    terminal: dict[str, Any],
    manifest: dict[str, Any],
    operational: dict[str, Any],
) -> dict[str, Any]:
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for case in terminal.get("cases") or []:
        for crop in _object(case).get("crops") or []:
            crop_value = _object(crop)
            if crop_value.get("terminal_status") == "uncertain_not_extracted":
                continue
            gemini_operation = _object(
                _object(crop_value.get("gemini")).get("operation")
            )
            openai_operation = _object(
                _object(crop_value.get("openai")).get("operation")
            )
            if gemini_operation and openai_operation:
                pairs.append(
                    (
                        _object(gemini_operation.get("attempt")),
                        _object(openai_operation.get("attempt")),
                    )
                )

    gemini_contract = _object(
        _object(manifest.get("provider_contracts")).get("gemini_extraction")
    )
    openai_contract = _object(
        _object(manifest.get("provider_contracts")).get("openai_extraction")
    )
    gemini_metrics = _object(operational.get("gemini_extraction"))
    openai_metrics = _object(operational.get("openai_extraction"))
    paired_operations = len(pairs)
    complete_pair_coverage = bool(
        paired_operations > 0
        and paired_operations == gemini_metrics.get("expected_operations")
        and paired_operations == openai_metrics.get("expected_operations")
        and gemini_metrics.get("schema_metadata_valid_operations") == paired_operations
        and openai_metrics.get("schema_metadata_valid_operations") == paired_operations
        and gemini_metrics.get("schema_metadata_invalid_operations") == 0
        and openai_metrics.get("schema_metadata_invalid_operations") == 0
    )

    def all_pairs_match(field: str) -> bool | None:
        if not complete_pair_coverage:
            return None
        return all(gemini.get(field) == openai.get(field) for gemini, openai in pairs)

    shared_prompt_contract = gemini_contract.get("prompt_contract_version")
    if shared_prompt_contract != openai_contract.get("prompt_contract_version"):
        shared_prompt_contract = None
    return {
        "comparison_scope": "model_provider_api_schema_adapter_bundle",
        "paired_extraction_operations": paired_operations,
        "complete_pair_coverage": complete_pair_coverage,
        "identical_crop_sha256_for_all_pairs": all_pairs_match("crop_sha256"),
        "identical_model_view_hash_for_all_pairs": all_pairs_match("model_view_hash"),
        "identical_canonical_schema_hash_for_all_pairs": all_pairs_match(
            "canonical_schema_hash"
        ),
        "identical_adapted_schema_hash_for_all_pairs": all_pairs_match(
            "adapted_schema_hash"
        ),
        "shared_prompt_contract_version": shared_prompt_contract,
        "schema_projection_causal_effect": "not_established",
        "detection": _schema_constraint_summary(_object(operational.get("detection"))),
        "gemini_extraction": _schema_constraint_summary(gemini_metrics),
        "openai_extraction": _schema_constraint_summary(openai_metrics),
    }


def _schema_constraint_summary(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_operations": value.get("expected_operations"),
        "operations": value.get("operations"),
        "schema_metadata_valid_operations": value.get(
            "schema_metadata_valid_operations"
        ),
        "schema_metadata_invalid_operations": value.get(
            "schema_metadata_invalid_operations"
        ),
        "schema_transform_count_histogram": value.get(
            "schema_transform_count_histogram"
        ),
        "schema_transform_total": value.get("schema_transform_total"),
        "canonical_schema_equals_adapted_operations": value.get(
            "canonical_schema_equals_adapted_operations"
        ),
        "canonical_schema_differs_from_adapted_operations": value.get(
            "canonical_schema_differs_from_adapted_operations"
        ),
        "canonical_schema_hashes": value.get("canonical_schema_hashes"),
        "adapted_schema_hashes": value.get("adapted_schema_hashes"),
    }


def _complete_source_map(value: dict[str, Any]) -> bool:
    if (
        validate_source_map(value)
        or value.get("evidence_status") != "parser_source_verified"
        or value.get("automatic_acceptance_eligible") is not True
    ):
        return False
    candidates = value.get("relation_candidates")
    if (
        value.get("relation_candidate_count") != 1
        or not isinstance(candidates, list)
        or len(candidates) != 1
    ):
        return False
    candidate = _object(candidates[0])
    headers = candidate.get("headers")
    qualifiers = candidate.get("qualifiers")
    proof = _object(candidate.get("relation_proof"))
    if (
        not _parser_match(candidate.get("row_label"))
        or not _parser_match(candidate.get("value"))
        or not isinstance(headers, list)
        or not headers
        or any(not _parser_match(item) for item in headers)
        or not isinstance(qualifiers, dict)
        or any(not _parser_match(item) for item in qualifiers.values())
        or proof
        != {
            "row_value_same_row_compatible": True,
            "headers_ordered_above_and_column_compatible": True,
            "qualifier_scopes_compatible": True,
        }
    ):
        return False
    identity = _object(value.get("source_identity"))
    return bool(
        _sha256(identity.get("pdf_sha256"))
        and isinstance(identity.get("page_number"), int)
        and identity["page_number"] > 0
        and _point_bbox(identity.get("table_bbox"))
        and _sha256(identity.get("crop_sha256"))
    )


def _parser_match(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    ordinals = value.get("parser_ordinals")
    atoms = value.get("atoms")
    return bool(
        isinstance(ordinals, list)
        and ordinals
        and all(
            isinstance(item, int) and not isinstance(item, bool) and item > 0
            for item in ordinals
        )
        and len(set(ordinals)) == len(ordinals)
        and isinstance(atoms, list)
        and len(atoms) == len(ordinals)
        and _point_bbox(value.get("source_bbox"))
        and isinstance(value.get("exact_source_text"), str)
        and bool(value["exact_source_text"])
        and isinstance(value.get("claimed_exact_text"), str)
        and bool(value["claimed_exact_text"])
        and value.get("match_mode")
        in {"whitespace_only_token_join", "exact_substring_in_single_atom"}
    )


def _bbox_contains(outer: list[float], inner: list[float], tolerance: float) -> bool:
    return bool(
        outer[0] <= inner[0] + tolerance
        and outer[1] <= inner[1] + tolerance
        and outer[2] >= inner[2] - tolerance
        and outer[3] >= inner[3] - tolerance
    )


def _field_rate(value: dict[str, int]) -> float | None:
    return _ratio(value["correct"], value["total"])


def _combined_currency_rate(fields: dict[str, dict[str, int]]) -> float | None:
    correct = fields["currency_literal"]["correct"] + fields["currency_code"]["correct"]
    total = fields["currency_literal"]["total"] + fields["currency_code"]["total"]
    return _ratio(correct, total)


def _combined_row_header_rate(fields: dict[str, dict[str, int]]) -> float | None:
    correct = fields["row"]["correct"] + fields["header_path"]["correct"]
    total = fields["row"]["total"] + fields["header_path"]["total"]
    return _ratio(correct, total)


def _human_reference_required_score(
    *,
    terminal_sha: str,
    terminal_verified: bool,
    terminal_contract_verified: bool,
    manifest_sha: Any,
) -> dict[str, Any]:
    result = _failed_score("dual_vlm_human_reference_required")
    result.update(
        {
            "scoring_status": "blocked_human_reference_required",
            "terminal_sha256": terminal_sha,
            "manifest_sha256": manifest_sha,
            "terminal_verified_before_reference_access": terminal_verified,
            "terminal_contract_verified_before_reference_access": (
                terminal_contract_verified
            ),
            "reference_accessed_after_terminal_verification": False,
        }
    )
    result["score_checksum"] = sha256_json(
        {key: item for key, item in result.items() if key != "score_checksum"}
    )
    return result


def _failed_score(code: str) -> dict[str, Any]:
    result = {
        "schema_version": SCORE_SCHEMA_VERSION,
        "scoring_status": "failed",
        "failure_code": code,
        "terminal_sha256": None,
        "manifest_sha256": None,
        "reference_sha256": None,
        "reference_human_reviewed": False,
        "terminal_verified_before_reference_access": False,
        "reference_accessed_after_terminal_verification": False,
        "terminal_unchanged_during_scoring": None,
        "scoring_order": [],
        "gates": {
            "TABLE_DETECTION_AND_CROPPING": "NOT_SCORED",
            "DUAL_VLM_FINANCIAL_FACT_EXTRACTION": "NOT_SCORED",
            "FACT_EVIDENCE_VERIFICATION": "NOT_SCORED",
        },
        "architectural_conclusion": None,
        "materially_better_than_single_vlm": None,
        "detection": None,
        "facts": None,
        "operational": None,
        "scorer_implementation_sha256": (
            hashlib.sha256(SCRIPT_PATH.read_bytes()).hexdigest()
            if SCRIPT_PATH.is_file()
            else None
        ),
    }
    result["score_checksum"] = sha256_json(result)
    return result


def _json_object(value: bytes, code: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ScoreError(code) from exc
    if not isinstance(parsed, dict):
        raise ScoreError(code)
    return parsed


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _terminal_operations(terminal: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for case in terminal.get("cases") or []:
        if not isinstance(case, dict):
            continue
        detection = _object(_object(case.get("detection")).get("operation"))
        if detection:
            result.append(detection)
        for crop in case.get("crops") or []:
            if not isinstance(crop, dict):
                continue
            for arm in ("gemini", "openai"):
                operation = _object(_object(crop.get(arm)).get("operation"))
                if operation:
                    result.append(operation)
    return result


def _terminal_review(value: Any, decisions: set[str]) -> bool:
    review = _object(value)
    checklist = review.get("checklist")
    return bool(
        set(review) == {"decision", "note", "checklist"}
        and review.get("decision") in decisions
        and isinstance(review.get("note"), str)
        and bool(review["note"].strip())
        and isinstance(checklist, dict)
        and checklist
        and all(item in {"pass", "issue", "uncertain"} for item in checklist.values())
    )


def _reviewer_identity_forbidden(value: str) -> bool:
    tokens = set(re.findall(r"[a-z0-9]+", value.casefold()))
    return bool(tokens & _FORBIDDEN_REVIEWER_TOKENS)


def _timezone_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and _HEX_64.fullmatch(value) is not None


def _normalized_bbox(value: Any) -> bool:
    return bool(_point_bbox(value) and all(0 <= float(item) <= 1 for item in value))


def _point_bbox(value: Any) -> bool:
    return bool(
        isinstance(value, list)
        and len(value) == 4
        and all(
            isinstance(item, (int, float))
            and not isinstance(item, bool)
            and math.isfinite(float(item))
            for item in value
        )
        and float(value[0]) < float(value[2])
        and float(value[1]) < float(value[3])
    )


def _currency_matches(reference: dict[str, Any], prediction: dict[str, Any]) -> bool:
    reference_code = reference.get("currency_code")
    reference_literal = reference.get("currency_literal")
    if reference_code is not None:
        return prediction.get("currency_code") == reference_code
    if reference_literal is not None:
        return bool(
            prediction.get("currency_literal") == reference_literal
            and prediction.get("currency_code") is None
        )
    return bool(
        prediction.get("currency_literal") is None
        and prediction.get("currency_code") is None
    )


def _canonical_decimal(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    rendered = value.strip()
    if not re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", rendered):
        return rendered
    sign = "-" if rendered.startswith("-") else ""
    unsigned = rendered.removeprefix("-")
    if "." in unsigned:
        whole, fraction = unsigned.split(".", 1)
        fraction = fraction.rstrip("0")
        unsigned = whole + ("." + fraction if fraction else "")
    unsigned = unsigned.lstrip("0") or "0"
    return "0" if unsigned == "0" else sign + unsigned


def _ratio(left: int | float, right: int | float) -> float | None:
    return round(float(left) / float(right), 6) if right else None


def _f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None or precision + recall == 0:
        return None
    return round(2 * precision * recall / (precision + recall), 6)


def _rate(value: Any) -> float:
    return (
        float(value)
        if isinstance(value, (int, float)) and math.isfinite(value)
        else 0.0
    )


def _nonnegative(value: Any) -> int:
    return (
        int(value)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0
        else 0
    )


def _error_code(exc: BaseException, fallback: str) -> str:
    code = getattr(exc, "code", None)
    return code if isinstance(code, str) and code else fallback


if __name__ == "__main__":
    raise SystemExit(main())
