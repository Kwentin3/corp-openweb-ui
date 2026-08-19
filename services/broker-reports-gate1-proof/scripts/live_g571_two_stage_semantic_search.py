#!/usr/bin/env python3
"""Run the frozen G5.71 source-assertion then semantic-classification proof."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
from typing import Any

from jsonschema import Draft202012Validator


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

import live_g570_vlm_metadata_microstand as g570  # noqa: E402
from broker_reports_gate1.gate3_llm_metadata_adapter import (  # noqa: E402
    metadata_proposal_response_schema,
)
from broker_reports_gate1.pdf_dual_vlm_fact_providers import (  # noqa: E402
    PdfDualVlmFactProviderConfig,
    PdfDualVlmFactProviderFactory,
)
from broker_reports_gate1.pdf_grid_experiment_provider import (  # noqa: E402
    PdfGridExperimentProviderFactory,
    PdfGridProviderConfig,
)
from local_pdf_vlm_guided_intake_development import (  # noqa: E402
    _openwebui_request,
)


FREEZE_SCHEMA_VERSION = "broker_reports_g571_two_stage_freeze_v1"
RESULT_PRIVATE_SCHEMA_VERSION = "broker_reports_g571_two_stage_private_v1"
RESULT_SAFE_SCHEMA_VERSION = "broker_reports_g571_two_stage_safe_v1"
ASSERTION_SCHEMA_VERSION = "broker_reports_visual_source_assertions_v1"
ASSERTION_VIEW_SCHEMA_VERSION = "broker_reports_g571_assertion_view_v1"
CLASSIFIER_VIEW_SCHEMA_VERSION = "broker_reports_g571_classifier_view_v1"
ASSERTION_INSTRUCTION_VERSION = "g571-visual-source-assertions-v1"
CLASSIFIER_INSTRUCTION_VERSION = "g571-metadata-semantic-classifier-v1"
REGION_ALIAS = g570.REGION_ALIAS

FACTORY_REQUIRED = (
    "Stage 1 uses PdfGridExperimentProviderFactory.create_for_openwebui and stage 2 "
    "uses PdfDualVlmFactProviderFactory.create_for_openwebui"
)
FORBIDDEN = (
    "direct provider transport, retries, best-of-N, voting, judge selection, broker "
    "vocabulary, regex semantics, prompt blacklist, fixed-layout rules, output "
    "repair, product activation, financial or tax reasoning"
)

ASSERTION_INSTRUCTION = (
    "Read only the attached visual crop, identified as region m001. Transcribe each "
    "explicit metadata assertion with a non-empty visible value. Preserve source "
    "language and copy the complete visible role label into role_label_literal when "
    "one exists; otherwise use null. Copy the complete visible value into "
    "value_literal. For a visible period also copy its exact start and end boundary "
    "literals. Do not map anything to a machine metadata role. Do not infer, "
    "translate, repair, classify, or add absent assertions. Return only the strict "
    "source-assertion object."
)

CLASSIFIER_INSTRUCTION = (
    "Classify only the supplied visual source assertions into the closed metadata "
    "contract. The attached crop may be used only to verify the supplied assertion, "
    "not to introduce a new value. Propose a fact only when the source assertion "
    "explicitly matches exactly one allowed fact role. Omit assertions without an "
    "exact contract match. Never choose an approximate or nearest role. Copy an exact "
    "visible value or exact value substring from the supplied assertion, excluding "
    "its label and unrelated adjacent values. For a statement period copy its exact "
    "visible boundaries. Do not infer, translate, repair, reconcile, or add missing "
    "facts. Return only the unchanged published proposal object."
)


class G571TwoStageError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def assertion_response_schema() -> dict[str, Any]:
    nullable_text = {
        "anyOf": [
            {"type": "string", "minLength": 1, "maxLength": 256},
            {"type": "null"},
        ]
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "assertions"],
        "properties": {
            "schema_version": {
                "type": "string",
                "enum": [ASSERTION_SCHEMA_VERSION],
            },
            "assertions": {
                "type": "array",
                "maxItems": 48,
                "uniqueItems": True,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "role_label_literal",
                        "value_literal",
                        "period_start_literal",
                        "period_end_literal",
                    ],
                    "properties": {
                        "role_label_literal": copy.deepcopy(nullable_text),
                        "value_literal": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 512,
                        },
                        "period_start_literal": copy.deepcopy(nullable_text),
                        "period_end_literal": copy.deepcopy(nullable_text),
                    },
                },
            },
        },
    }


def assertion_model_view() -> dict[str, Any]:
    return {
        "schema_version": ASSERTION_VIEW_SCHEMA_VERSION,
        "goal": "G5.71",
        "domain": "VISUAL_SOURCE_ASSERTION_TRANSCRIPTION",
        "input": {
            "kind": "VISUAL_CROP",
            "region_alias": REGION_ALIAS,
            "flattened_canonical_text": False,
            "ocr_dump": False,
            "parser_reconstruction": False,
        },
        "instruction_version": ASSERTION_INSTRUCTION_VERSION,
        "instruction": ASSERTION_INSTRUCTION,
        "metadata_contract_visible": False,
        "broker_hints": [],
    }


def classifier_model_view_template() -> dict[str, Any]:
    return _classifier_model_view({"schema_version": ASSERTION_SCHEMA_VERSION, "assertions": []})


def _classifier_model_view(assertions: dict[str, Any]) -> dict[str, Any]:
    if set(g570.FACT_SEMANTICS) != set(g570.GATE3_MINIMAL_METADATA_FACT_TYPES):
        raise G571TwoStageError("g571_two_stage_contract_semantics_drift")
    return {
        "schema_version": CLASSIFIER_VIEW_SCHEMA_VERSION,
        "goal": "G5.71",
        "domain": "METADATA_SEMANTIC_ADAPTER",
        "input": {
            "kind": "VISUAL_SOURCE_ASSERTIONS_WITH_CROP_VERIFICATION",
            "region_alias": REGION_ALIAS,
            "source_assertions": copy.deepcopy(assertions),
        },
        "contract": {
            "contract_version": g570.GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
            "allowed_fact_types": list(g570.GATE3_MINIMAL_METADATA_FACT_TYPES),
            "fact_semantics": copy.deepcopy(g570.FACT_SEMANTICS),
            "output_schema": "broker_reports_llm_metadata_proposal_v2",
        },
        "instruction_version": CLASSIFIER_INSTRUCTION_VERSION,
        "instruction": CLASSIFIER_INSTRUCTION,
        "broker_hints": [],
    }


def validate_assertions(value: Any) -> list[str]:
    errors = [
        "json_schema:" + error.json_path + ":" + error.message
        for error in Draft202012Validator(assertion_response_schema()).iter_errors(value)
    ]
    if errors or not isinstance(value, dict):
        return sorted(errors) or ["assertion_output_not_object"]
    seen: set[tuple[str, str, str, str]] = set()
    for index, assertion in enumerate(value.get("assertions") or []):
        start = assertion.get("period_start_literal")
        end = assertion.get("period_end_literal")
        if (start is None) != (end is None):
            errors.append(f"assertion_{index}_partial_period_boundary")
        identity = (
            g570._normalize(str(assertion.get("role_label_literal") or "")),
            g570._normalize(str(assertion.get("value_literal") or "")),
            g570._normalize(str(start or "")),
            g570._normalize(str(end or "")),
        )
        if identity in seen:
            errors.append(f"assertion_{index}_duplicate")
        seen.add(identity)
    return sorted(errors)


def validate_freeze(
    freeze: dict[str, Any], *, freeze_path: Path
) -> dict[str, dict[str, Any]]:
    required = {
        "schema_version",
        "goal",
        "phase",
        "hypothesis_id",
        "candidate_id",
        "solution_frozen",
        "contract_version",
        "assertion_instruction_version",
        "classifier_instruction_version",
        "assertion_model_view_sha256",
        "assertion_response_schema_sha256",
        "classifier_model_view_template_sha256",
        "published_response_schema_sha256",
        "stage1_provider_profile",
        "stage1_model_id",
        "stage2_provider_profile",
        "stage2_model_id",
        "maximum_output_tokens",
        "maximum_counted_input_tokens",
        "provider_calls_per_document",
        "broker_hints",
        "regex_semantics",
        "prompt_blacklist",
        "fixed_layout_semantics",
        "prompt_tuning_after_freeze",
        "product_activation",
        "cases",
        "runs",
    }
    if not isinstance(freeze, dict) or set(freeze) != required:
        raise G571TwoStageError("g571_two_stage_freeze_fields_invalid")
    if (
        freeze["schema_version"] != FREEZE_SCHEMA_VERSION
        or freeze["goal"] != "G5.71"
        or freeze["phase"] not in {"development", "repeatability", "holdout"}
        or freeze["hypothesis_id"] != "H5_JOINT_EXTRACTION_CLASSIFICATION_OVERLOAD"
        or freeze["candidate_id"] != "VISUAL_ASSERTIONS_THEN_SEMANTIC_CLASSIFICATION"
        or freeze["solution_frozen"] != (freeze["phase"] == "holdout")
        or freeze["contract_version"] != g570.GATE3_MINIMAL_METADATA_CONTRACT_VERSION
        or freeze["assertion_instruction_version"] != ASSERTION_INSTRUCTION_VERSION
        or freeze["classifier_instruction_version"] != CLASSIFIER_INSTRUCTION_VERSION
        or freeze["assertion_model_view_sha256"]
        != g570._sha256_json(assertion_model_view())
        or freeze["assertion_response_schema_sha256"]
        != g570._sha256_json(assertion_response_schema())
        or freeze["classifier_model_view_template_sha256"]
        != g570._sha256_json(classifier_model_view_template())
        or freeze["published_response_schema_sha256"]
        != g570._sha256_json(metadata_proposal_response_schema())
        or freeze["stage1_provider_profile"] != "google_gemini"
        or freeze["stage1_model_id"] != "models/gemini-3.5-flash"
        or freeze["stage2_provider_profile"] != "openai_gpt"
        or freeze["stage2_model_id"] != "gpt-5.6-sol"
        or freeze["provider_calls_per_document"] != 2
        or freeze["broker_hints"] != []
        or freeze["regex_semantics"] is not False
        or freeze["prompt_blacklist"] is not False
        or freeze["fixed_layout_semantics"] is not False
        or freeze["prompt_tuning_after_freeze"] is not False
        or freeze["product_activation"] is not False
    ):
        raise G571TwoStageError("g571_two_stage_freeze_contract_invalid")
    for field, minimum, maximum in (
        ("maximum_output_tokens", 256, 8192),
        ("maximum_counted_input_tokens", 1000, 24000),
    ):
        value = freeze[field]
        if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
            raise G571TwoStageError("g571_two_stage_freeze_budget_invalid")
    if not isinstance(freeze["cases"], list) or not freeze["cases"]:
        raise G571TwoStageError("g571_two_stage_cases_invalid")
    cases: dict[str, dict[str, Any]] = {}
    for raw in freeze["cases"]:
        try:
            case = g570._validate_case(raw, freeze_root=freeze_path.parent)
        except g570.G570MicrostandError as exc:
            raise G571TwoStageError(
                "g571_two_stage_" + exc.code.removeprefix("g570_")
            ) from exc
        if case["case_id"] in cases:
            raise G571TwoStageError("g571_two_stage_case_duplicate")
        cases[case["case_id"]] = case
    if not isinstance(freeze["runs"], list) or not freeze["runs"]:
        raise G571TwoStageError("g571_two_stage_runs_invalid")
    run_ids: set[str] = set()
    for run in freeze["runs"]:
        if (
            not isinstance(run, dict)
            or set(run) != {"run_id", "case_id", "purpose"}
            or not g570._simple_id(run.get("run_id"))
            or run.get("case_id") not in cases
            or run.get("purpose") != freeze["phase"]
            or run["run_id"] in run_ids
        ):
            raise G571TwoStageError("g571_two_stage_run_invalid")
        run_ids.add(run["run_id"])
    if freeze["phase"] == "holdout" and (len(cases) != 1 or len(freeze["runs"]) != 1):
        raise G571TwoStageError("g571_two_stage_holdout_not_single_shot")
    return cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-frozen-runs", action="store_true")
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--private-output-root", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()
    if not args.execute_frozen_runs:
        raise SystemExit("g571_two_stage_explicit_execution_flag_required")
    freeze_path = args.freeze.resolve()
    output_root = args.private_output_root.resolve()
    if g570._is_within(output_root, REPO_ROOT.resolve()):
        raise SystemExit("g571_two_stage_output_inside_repository")
    if output_root.exists():
        raise SystemExit("g571_two_stage_output_root_must_be_new")
    freeze = g570._read_json(freeze_path)
    cases = validate_freeze(freeze, freeze_path=freeze_path)
    request = _openwebui_request(args.env_file.resolve())
    stage1 = PdfGridExperimentProviderFactory(
        PdfGridProviderConfig(
            provider_profile=freeze["stage1_provider_profile"],
            model_id=freeze["stage1_model_id"],
            timeout_seconds=args.timeout_seconds,
            maximum_output_tokens=freeze["maximum_output_tokens"],
            maximum_counted_input_tokens=freeze["maximum_counted_input_tokens"],
            thinking_level="minimal",
        )
    ).create_for_openwebui(request)
    bundle = PdfDualVlmFactProviderFactory(
        PdfDualVlmFactProviderConfig(
            openai_model_id=freeze["stage2_model_id"],
            timeout_seconds=args.timeout_seconds,
            extraction_maximum_output_tokens=freeze["maximum_output_tokens"],
            maximum_counted_input_tokens=freeze["maximum_counted_input_tokens"],
        )
    ).create_for_openwebui(request, include_openai=True)
    if bundle.openai is None:
        raise SystemExit("g571_two_stage_openai_adapter_missing")
    stage2 = bundle.openai
    qualification = {"stage1": stage1.qualify(), "stage2": stage2.qualify()}
    if any(item.get("status") != "qualified" for item in qualification.values()):
        raise SystemExit("g571_two_stage_provider_not_qualified")

    output_root.mkdir(parents=True)
    runs_private: list[dict[str, Any]] = []
    runs_safe: list[dict[str, Any]] = []
    submissions = 0
    for scheduled in freeze["runs"]:
        case = cases[scheduled["case_id"]]
        png = case["crop_path"].read_bytes()
        stage1_response = stage1.invoke(
            task_id="g571_assert_" + g570._identifier(scheduled["run_id"]),
            model_view=assertion_model_view(),
            output_schema=assertion_response_schema(),
            png_bytes=png,
            crop_sha256=case["crop_sha256"],
            attempt_number=1,
            attempt_lineage=[],
        )
        submissions += 1
        assertions = copy.deepcopy(stage1_response.get("json_output"))
        stage1_errors = (
            [str(stage1_response["attempt"].get("terminal_failure_class"))]
            if stage1_response["attempt"].get("terminal_failure_class")
            else validate_assertions(assertions)
        )
        stage2_response: dict[str, Any] | None = None
        if not stage1_errors:
            stage2_response = stage2.invoke(
                task_id="g571_classify_" + g570._identifier(scheduled["run_id"]),
                model_view=_classifier_model_view(assertions),
                output_schema=metadata_proposal_response_schema(),
                png_bytes=png,
                crop_sha256=case["crop_sha256"],
                attempt_number=1,
                attempt_lineage=[],
            )
            submissions += 1
        run = _build_run(
            scheduled=scheduled,
            case=case,
            assertions=assertions,
            stage1_response=stage1_response,
            stage1_errors=stage1_errors,
            stage2_response=stage2_response,
        )
        runs_private.append(run)
        runs_safe.append(_safe_run(run))
        with (output_root / "journal.private.jsonl").open("a", encoding="utf-8") as journal:
            journal.write(json.dumps(run, ensure_ascii=False) + "\n")

    source_inputs_unchanged = all(
        g570._sha256_file(case["crop_path"]) == case["crop_sha256"]
        and g570._sha256_file(case["source_evidence_path"])
        == case["source_evidence_sha256"]
        for case in cases.values()
    )
    expected_submissions = len(freeze["runs"]) * 2
    transport_failures = sum(run["transport_failures"] for run in runs_safe)
    contract_invalid = sum(run["contract_invalid"] for run in runs_safe)
    technically_valid = (
        submissions == expected_submissions
        and source_inputs_unchanged
        and transport_failures == 0
        and contract_invalid == 0
    )
    totals = g570._sum_metrics(runs_safe)
    usage = _sum_usage(runs_safe)
    duration_ms = sum(run["duration_ms"] for run in runs_safe)
    private = {
        "schema_version": RESULT_PRIVATE_SCHEMA_VERSION,
        "goal": "G5.71",
        "phase": freeze["phase"],
        "hypothesis_id": freeze["hypothesis_id"],
        "candidate_id": freeze["candidate_id"],
        "solution_frozen": freeze["solution_frozen"],
        "freeze_sha256": g570._sha256_file(freeze_path),
        "qualification": qualification,
        "assertion_model_view": assertion_model_view(),
        "assertion_response_schema": assertion_response_schema(),
        "classifier_model_view_template": classifier_model_view_template(),
        "published_response_schema": metadata_proposal_response_schema(),
        "cases": [
            {
                "case_id": case_id,
                "crop_path": str(case["crop_path"]),
                "source_evidence_path": str(case["source_evidence_path"]),
                "human_transcription": case["human_transcription"],
                "truth": copy.deepcopy(case["truth"]),
                "non_contract_observations": copy.deepcopy(case["non_contract_observations"]),
            }
            for case_id, case in cases.items()
        ],
        "provider_submissions": submissions,
        "runs": runs_private,
        "totals": totals,
        "usage": usage,
        "duration_ms": duration_ms,
        "transport_failures": transport_failures,
        "contract_invalid": contract_invalid,
        "source_inputs_unchanged": source_inputs_unchanged,
        "technically_valid": technically_valid,
        "retries": 0,
        "best_of_n": False,
        "voting": False,
        "judge_model": False,
        "result_selection": False,
        "manual_output_repair": False,
        "broker_hints": False,
        "regex_semantics": False,
        "prompt_blacklist": False,
        "fixed_layout_semantics": False,
        "product_activation": False,
    }
    safe = {
        "schema_version": RESULT_SAFE_SCHEMA_VERSION,
        "goal": "G5.71",
        "phase": freeze["phase"],
        "terminal": (
            "G571_TWO_STAGE_PHASE_COMPLETE"
            if technically_valid
            else "G571_TWO_STAGE_PHASE_TECHNICALLY_INCOMPLETE"
        ),
        "hypothesis_id": freeze["hypothesis_id"],
        "candidate_id": freeze["candidate_id"],
        "solution_frozen": freeze["solution_frozen"],
        "freeze_sha256": g570._sha256_file(freeze_path),
        "stage1_model_id": freeze["stage1_model_id"],
        "stage2_model_id": freeze["stage2_model_id"],
        "assertion_model_view_sha256": g570._sha256_json(assertion_model_view()),
        "assertion_response_schema_sha256": g570._sha256_json(assertion_response_schema()),
        "classifier_model_view_template_sha256": g570._sha256_json(classifier_model_view_template()),
        "published_response_schema_sha256": g570._sha256_json(metadata_proposal_response_schema()),
        "case_ids": list(cases),
        "provider_calls_per_document": 2,
        "provider_submissions": submissions,
        "runs": runs_safe,
        "totals": totals,
        "usage": usage,
        "duration_ms": duration_ms,
        "transport_failures": transport_failures,
        "contract_invalid": contract_invalid,
        "source_inputs_unchanged": source_inputs_unchanged,
        "technically_valid": technically_valid,
        "retries": 0,
        "best_of_n": False,
        "voting": False,
        "judge_model": False,
        "result_selection": False,
        "manual_output_repair": False,
        "broker_hints": False,
        "regex_semantics": False,
        "prompt_blacklist": False,
        "fixed_layout_semantics": False,
        "product_activation": False,
        "private_values_committed": False,
    }
    g570._write_json(output_root / "result.private.json", private)
    g570._write_json(output_root / "result.safe.json", safe)
    print(json.dumps(safe, ensure_ascii=False, indent=2))
    return 0 if technically_valid else 2


def _build_run(
    *,
    scheduled: dict[str, Any],
    case: dict[str, Any],
    assertions: Any,
    stage1_response: dict[str, Any],
    stage1_errors: list[str],
    stage2_response: dict[str, Any] | None,
) -> dict[str, Any]:
    stage1_attempt = copy.deepcopy(stage1_response.get("attempt") or {})
    stage2_attempt = copy.deepcopy((stage2_response or {}).get("attempt") or {})
    stage2_output = copy.deepcopy((stage2_response or {}).get("json_output"))
    stage2_terminal = stage2_attempt.get("terminal_failure_class")
    stage2_errors: list[str] = []
    if stage2_response is None:
        stage2_errors = ["stage2_not_submitted_due_stage1_terminal"]
    elif stage2_terminal:
        stage2_errors = [str(stage2_terminal)]
    else:
        stage2_errors = g570.validate_visual_proposal(stage2_output)
    metrics = g570._empty_metrics(len(case["truth"]))
    details: dict[str, Any] = {}
    if not stage1_errors and not stage2_errors:
        metrics, details = g570.evaluate_visual_proposal(
            stage2_output,
            truth=case["truth"],
            non_contract_observations=case["non_contract_observations"],
            human_transcription=case["human_transcription"],
        )
    semantic_exact = (
        not stage1_errors
        and not stage2_errors
        and all(
            metrics[name] == 0
            for name in (
                "missed",
                "wrong_role",
                "extra_fact",
                "wrong_value_boundary",
                "invented_value",
            )
        )
    )
    return {
        "run_id": scheduled["run_id"],
        "case_id": scheduled["case_id"],
        "purpose": scheduled["purpose"],
        "crop_sha256": case["crop_sha256"],
        "assertions": assertions,
        "stage1_private_response": copy.deepcopy(stage1_response.get("raw_private_response")),
        "stage1_attempt": stage1_attempt,
        "stage1_errors": stage1_errors,
        "stage2_output": stage2_output,
        "stage2_private_response": copy.deepcopy((stage2_response or {}).get("raw_private_response")),
        "stage2_attempt": stage2_attempt,
        "stage2_errors": stage2_errors,
        "metrics": metrics,
        "details": details,
        "semantic_exact": semantic_exact,
        "single_shot_per_stage": True,
        "selected": False,
        "repaired": False,
    }


def _safe_run(run: dict[str, Any]) -> dict[str, Any]:
    attempts = [run["stage1_attempt"], run["stage2_attempt"]]
    usage = {
        name: sum(int((attempt.get("usage") or {}).get(name) or 0) for attempt in attempts)
        for name in ("input_tokens", "output_tokens", "total_tokens")
    }
    transport_failures = sum(
        int(bool(attempt.get("terminal_failure_class"))) for attempt in attempts
    )
    return {
        "run_id": run["run_id"],
        "case_id": run["case_id"],
        "purpose": run["purpose"],
        "crop_sha256": run["crop_sha256"],
        "stage1_request_hash": run["stage1_attempt"].get("request_hash"),
        "stage2_request_hash": run["stage2_attempt"].get("request_hash"),
        "stage1_model_resolved": run["stage1_attempt"].get("model_resolved"),
        "stage2_model_resolved": run["stage2_attempt"].get("model_resolved"),
        "stage1_finish_reason": run["stage1_attempt"].get("finish_reason"),
        "stage2_finish_reason": run["stage2_attempt"].get("finish_reason"),
        "stage1_assertion_count": len((run.get("assertions") or {}).get("assertions") or []),
        "stage1_contract_invalid": int(bool(run["stage1_errors"])),
        "stage2_contract_invalid": int(bool(run["stage2_errors"])),
        "transport_failures": transport_failures,
        "contract_invalid": int(bool(run["stage1_errors"] or run["stage2_errors"])),
        "duration_ms": sum(int(attempt.get("duration_ms") or 0) for attempt in attempts),
        "usage": usage,
        "metrics": copy.deepcopy(run["metrics"]),
        "semantic_exact": run["semantic_exact"],
        "single_shot_per_stage": True,
        "selected": False,
        "repaired": False,
    }


def _sum_usage(runs: list[dict[str, Any]]) -> dict[str, int]:
    return {
        name: sum(int((run.get("usage") or {}).get(name) or 0) for run in runs)
        for name in ("input_tokens", "output_tokens", "total_tokens")
    }


if __name__ == "__main__":
    raise SystemExit(main())
