#!/usr/bin/env python3
"""Run one frozen G5.71 semantic-adaptation experiment or holdout."""

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


FREEZE_SCHEMA_VERSION = "broker_reports_g571_semantic_search_freeze_v1"
RESULT_PRIVATE_SCHEMA_VERSION = "broker_reports_g571_semantic_search_private_v1"
RESULT_SAFE_SCHEMA_VERSION = "broker_reports_g571_semantic_search_safe_v1"
DECISION_SCHEMA_VERSION = "broker_reports_metadata_semantic_decisions_v1"
MODEL_VIEW_SCHEMA_VERSION = "broker_reports_g571_semantic_model_view_v1"
INSTRUCTION_VERSION = "g571-explicit-no-match-v1"
REGION_ALIAS = g570.REGION_ALIAS
MAX_DECISIONS = 48

FACTORY_REQUIRED = (
    "Existing PdfGridExperimentProviderFactory.create_for_openwebui or "
    "PdfDualVlmFactProviderFactory.create_for_openwebui is required"
)
FORBIDDEN = (
    "direct provider transport, retries, failover, selection, broker vocabulary, "
    "regex semantics, prompt blacklist, fixed-layout rules, output repair, product "
    "activation, financial or tax reasoning"
)

SEMANTIC_INSTRUCTION = (
    "Read only the attached visual crop, identified as region m001. Enumerate each "
    "explicit metadata assertion that has a non-empty source-authored value. For "
    "each assertion make exactly one semantic decision: CONTRACT_FACT when the "
    "visually asserted role exactly matches one allowed contract fact type, or "
    "NO_CONTRACT_MATCH when it does not. NO_CONTRACT_MATCH is a normal terminal "
    "decision. Never choose an approximate or nearest contract role. Copy the exact "
    "visible value without its label into source_literal. Copy the exact visible "
    "role label into role_label_literal when one exists; otherwise use null. Use "
    "m001 for both aliases. For a CONTRACT_FACT statement period, also copy its "
    "exact visible start and end boundary literals. Do not infer, translate, repair, "
    "reconcile, or add absent assertions. Return only the strict response object."
)


class G571SearchError(RuntimeError):
    """Bounded experiment failure with a stable code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def semantic_decision_response_schema() -> dict[str, Any]:
    nullable_text = {
        "anyOf": [
            {"type": "string", "minLength": 1, "maxLength": 256},
            {"type": "null"},
        ]
    }
    nullable_fact_type = {
        "anyOf": [
            {
                "type": "string",
                "enum": list(g570.GATE3_MINIMAL_METADATA_FACT_TYPES),
            },
            {"type": "null"},
        ]
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "decisions"],
        "properties": {
            "schema_version": {
                "type": "string",
                "enum": [DECISION_SCHEMA_VERSION],
            },
            "decisions": {
                "type": "array",
                "maxItems": MAX_DECISIONS,
                "uniqueItems": True,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "decision",
                        "fact_type",
                        "source_target_alias",
                        "role_evidence_target_alias",
                        "role_label_literal",
                        "source_literal",
                        "period_start_literal",
                        "period_end_literal",
                    ],
                    "properties": {
                        "decision": {
                            "type": "string",
                            "enum": ["CONTRACT_FACT", "NO_CONTRACT_MATCH"],
                        },
                        "fact_type": nullable_fact_type,
                        "source_target_alias": {
                            "type": "string",
                            "pattern": "^m[0-9]{3,}$",
                        },
                        "role_evidence_target_alias": {
                            "type": "string",
                            "pattern": "^m[0-9]{3,}$",
                        },
                        "role_label_literal": copy.deepcopy(nullable_text),
                        "source_literal": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 256,
                        },
                        "period_start_literal": copy.deepcopy(nullable_text),
                        "period_end_literal": copy.deepcopy(nullable_text),
                    },
                },
            },
        },
    }


def semantic_model_view() -> dict[str, Any]:
    """Return the one broker-neutral semantic-decision view for every crop."""

    if set(g570.FACT_SEMANTICS) != set(g570.GATE3_MINIMAL_METADATA_FACT_TYPES):
        raise G571SearchError("g571_contract_semantics_drift")
    return {
        "schema_version": MODEL_VIEW_SCHEMA_VERSION,
        "goal": "G5.71",
        "input": {
            "kind": "VISUAL_CROP",
            "region_alias": REGION_ALIAS,
            "flattened_canonical_text": False,
            "ocr_dump": False,
            "parser_reconstruction": False,
        },
        "contract": {
            "contract_version": g570.GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
            "allowed_fact_types": list(g570.GATE3_MINIMAL_METADATA_FACT_TYPES),
            "fact_semantics": copy.deepcopy(g570.FACT_SEMANTICS),
            "published_output_schema": "broker_reports_llm_metadata_proposal_v2",
            "internal_decision_schema": DECISION_SCHEMA_VERSION,
        },
        "instruction_version": INSTRUCTION_VERSION,
        "instruction": SEMANTIC_INSTRUCTION,
        "broker_hints": [],
    }


def candidate_model_view(candidate_id: str) -> dict[str, Any]:
    if candidate_id == "EXPLICIT_NO_CONTRACT_MATCH_ONE_CALL":
        return semantic_model_view()
    if candidate_id == "EXISTING_OPENAI_VLM_BASELINE_CONTRACT":
        return g570.visual_metadata_model_view()
    raise G571SearchError("g571_candidate_unknown")


def candidate_response_schema(candidate_id: str) -> dict[str, Any]:
    if candidate_id == "EXPLICIT_NO_CONTRACT_MATCH_ONE_CALL":
        return semantic_decision_response_schema()
    if candidate_id == "EXISTING_OPENAI_VLM_BASELINE_CONTRACT":
        return metadata_proposal_response_schema()
    raise G571SearchError("g571_candidate_unknown")


def project_contract_proposal(value: dict[str, Any]) -> dict[str, Any]:
    """Deterministically discard no-match decisions and preserve typed facts."""

    facts = []
    for decision in value.get("decisions") or []:
        if decision.get("decision") != "CONTRACT_FACT":
            continue
        facts.append(
            {
                "fact_type": decision.get("fact_type"),
                "source_target_alias": decision.get("source_target_alias"),
                "role_evidence_target_alias": decision.get(
                    "role_evidence_target_alias"
                ),
                "source_literal": decision.get("source_literal"),
                "period_start_literal": decision.get("period_start_literal"),
                "period_end_literal": decision.get("period_end_literal"),
            }
        )
    return {
        "schema_version": "broker_reports_llm_metadata_proposal_v2",
        "facts": facts,
    }


def validate_semantic_decisions(value: Any) -> list[str]:
    schema_errors = [
        "json_schema:" + error.json_path + ":" + error.message
        for error in Draft202012Validator(
            semantic_decision_response_schema()
        ).iter_errors(value)
    ]
    if schema_errors or not isinstance(value, dict):
        return sorted(schema_errors) or ["decision_output_not_object"]
    errors: list[str] = []
    seen: set[tuple[Any, ...]] = set()
    for index, item in enumerate(value.get("decisions") or []):
        if item.get("source_target_alias") != REGION_ALIAS:
            errors.append(f"decision_{index}_source_alias_not_crop")
        if item.get("role_evidence_target_alias") != REGION_ALIAS:
            errors.append(f"decision_{index}_role_alias_not_crop")
        decision = item.get("decision")
        fact_type = item.get("fact_type")
        start = item.get("period_start_literal")
        end = item.get("period_end_literal")
        if decision == "NO_CONTRACT_MATCH":
            if fact_type is not None:
                errors.append(f"decision_{index}_no_match_fact_type_present")
            if start is not None or end is not None:
                errors.append(f"decision_{index}_no_match_period_present")
        elif decision == "CONTRACT_FACT":
            if fact_type is None:
                errors.append(f"decision_{index}_contract_fact_type_missing")
            elif fact_type == "STATEMENT_PERIOD":
                if not all(isinstance(item, str) and item for item in (start, end)):
                    errors.append(f"decision_{index}_period_boundaries_missing")
            elif start is not None or end is not None:
                errors.append(f"decision_{index}_non_period_boundaries_present")
        identity = (
            decision,
            fact_type,
            g570._normalize(str(item.get("source_literal") or "")),
            g570._normalize(str(start or "")),
            g570._normalize(str(end or "")),
        )
        if identity in seen:
            errors.append(f"decision_{index}_semantic_duplicate")
        seen.add(identity)
    if not errors:
        errors.extend(
            "projection:" + item
            for item in g570.validate_visual_proposal(
                project_contract_proposal(value),
                response_schema=metadata_proposal_response_schema(),
            )
        )
    return sorted(errors)


def evaluate_semantic_decisions(
    value: dict[str, Any],
    *,
    truth: list[dict[str, Any]],
    non_contract_observations: list[dict[str, Any]],
    human_transcription: str,
) -> tuple[dict[str, int], dict[str, Any]]:
    proposal = project_contract_proposal(value)
    metrics, proposal_details = g570.evaluate_visual_proposal(
        proposal,
        truth=truth,
        non_contract_observations=non_contract_observations,
        human_transcription=human_transcription,
    )
    transcription = g570._normalize(human_transcription)
    unmatched_observations = {
        g570._normalize(item["source_literal"]): item
        for item in non_contract_observations
    }
    truth_by_literal = {
        g570._normalize(item["source_literal"]): item for item in truth
    }
    decision_details: dict[str, list[dict[str, Any]]] = {
        "no_match_correct": [],
        "no_match_missed": [],
        "no_match_wrong": [],
        "no_match_extra": [],
        "no_match_invented": [],
    }
    no_match_correct = 0
    no_match_wrong = 0
    no_match_extra = 0
    no_match_invented = 0
    for index, item in enumerate(value.get("decisions") or []):
        if item.get("decision") != "NO_CONTRACT_MATCH":
            continue
        literal = g570._normalize(str(item.get("source_literal") or ""))
        if literal in unmatched_observations:
            no_match_correct += 1
            observation = unmatched_observations.pop(literal)
            decision_details["no_match_correct"].append(
                {"decision_index": index, "observation_id": observation["observation_id"]}
            )
        elif literal in truth_by_literal:
            no_match_wrong += 1
            decision_details["no_match_wrong"].append(
                {
                    "decision_index": index,
                    "fact_id": truth_by_literal[literal]["fact_id"],
                }
            )
        elif literal not in transcription:
            no_match_invented += 1
            decision_details["no_match_invented"].append({"decision_index": index})
        else:
            no_match_extra += 1
            decision_details["no_match_extra"].append({"decision_index": index})
    decision_details["no_match_missed"] = [
        {"observation_id": item["observation_id"]}
        for item in unmatched_observations.values()
    ]
    metrics.update(
        {
            "no_match_correct": no_match_correct,
            "no_match_missed": len(unmatched_observations),
            "no_match_wrong": no_match_wrong,
            "no_match_extra": no_match_extra,
            "no_match_invented": no_match_invented,
        }
    )
    return metrics, {
        "proposal": proposal_details,
        "semantic_decisions": decision_details,
    }


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
        "instruction_version",
        "model_view_sha256",
        "response_schema_sha256",
        "provider_profile",
        "model_id",
        "maximum_output_tokens",
        "maximum_counted_input_tokens",
        "thinking_level",
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
        raise G571SearchError("g571_freeze_fields_invalid")
    candidate_id = freeze.get("candidate_id")
    if candidate_id == "EXPLICIT_NO_CONTRACT_MATCH_ONE_CALL":
        candidate_identity_valid = (
            freeze.get("hypothesis_id") == "H3_POSITIVE_ONLY_SCHEMA_COERCION"
            and freeze.get("instruction_version") == INSTRUCTION_VERSION
            and freeze.get("provider_profile") == "google_gemini"
            and freeze.get("model_id") == "models/gemini-3.5-flash"
        )
    elif candidate_id == "EXISTING_OPENAI_VLM_BASELINE_CONTRACT":
        candidate_identity_valid = (
            freeze.get("hypothesis_id") == "H4_MODEL_CAPABILITY_FLOOR"
            and freeze.get("instruction_version") == g570.INSTRUCTION_VERSION
            and freeze.get("provider_profile") == "openai_gpt"
            and freeze.get("model_id") == "gpt-5.6-sol"
        )
    else:
        candidate_identity_valid = False
    if (
        freeze["schema_version"] != FREEZE_SCHEMA_VERSION
        or freeze["goal"] != "G5.71"
        or freeze["phase"] not in {"development", "holdout"}
        or not candidate_identity_valid
        or freeze["solution_frozen"] != (freeze["phase"] == "holdout")
        or freeze["contract_version"]
        != g570.GATE3_MINIMAL_METADATA_CONTRACT_VERSION
        or freeze["model_view_sha256"]
        != g570._sha256_json(candidate_model_view(candidate_id))
        or freeze["response_schema_sha256"]
        != g570._sha256_json(candidate_response_schema(candidate_id))
        or freeze["thinking_level"] != "minimal"
        or freeze["provider_calls_per_document"] != 1
        or freeze["broker_hints"] != []
        or freeze["regex_semantics"] is not False
        or freeze["prompt_blacklist"] is not False
        or freeze["fixed_layout_semantics"] is not False
        or freeze["prompt_tuning_after_freeze"] is not False
        or freeze["product_activation"] is not False
    ):
        raise G571SearchError("g571_freeze_contract_invalid")
    for field, minimum, maximum in (
        ("maximum_output_tokens", 256, 8192),
        ("maximum_counted_input_tokens", 1000, 24000),
    ):
        value = freeze[field]
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < minimum
            or value > maximum
        ):
            raise G571SearchError("g571_freeze_budget_invalid")
    if not isinstance(freeze["cases"], list) or not freeze["cases"]:
        raise G571SearchError("g571_freeze_cases_invalid")
    cases: dict[str, dict[str, Any]] = {}
    for raw in freeze["cases"]:
        try:
            case = g570._validate_case(raw, freeze_root=freeze_path.parent)
        except g570.G570MicrostandError as exc:
            raise G571SearchError("g571_" + exc.code.removeprefix("g570_")) from exc
        if case["case_id"] in cases:
            raise G571SearchError("g571_freeze_case_duplicate")
        cases[case["case_id"]] = case
    if not isinstance(freeze["runs"], list) or not freeze["runs"]:
        raise G571SearchError("g571_freeze_runs_invalid")
    run_ids: set[str] = set()
    expected_purpose = freeze["phase"]
    for run in freeze["runs"]:
        if (
            not isinstance(run, dict)
            or set(run) != {"run_id", "case_id", "purpose"}
            or not g570._simple_id(run.get("run_id"))
            or run.get("case_id") not in cases
            or run.get("purpose") != expected_purpose
            or run["run_id"] in run_ids
        ):
            raise G571SearchError("g571_freeze_run_invalid")
        run_ids.add(run["run_id"])
    if freeze["phase"] == "holdout" and (len(cases) != 1 or len(freeze["runs"]) != 1):
        raise G571SearchError("g571_holdout_must_be_one_single_shot")
    return cases


def build_run_record(
    *,
    scheduled: dict[str, Any],
    case: dict[str, Any],
    candidate_id: str,
    response: dict[str, Any] | None,
    error: dict[str, Any] | None,
) -> dict[str, Any]:
    transport_failure = int(error is not None)
    attempt = copy.deepcopy((response or {}).get("attempt") or {})
    raw_output = copy.deepcopy((response or {}).get("json_output"))
    if attempt.get("terminal_failure_class") is not None:
        transport_failure = 1
    contract_errors: list[str] = []
    metrics = _empty_metrics(len(case["truth"]))
    details: dict[str, Any] = {}
    if not transport_failure:
        if candidate_id == "EXPLICIT_NO_CONTRACT_MATCH_ONE_CALL":
            contract_errors = validate_semantic_decisions(raw_output)
            if not contract_errors:
                metrics, details = evaluate_semantic_decisions(
                    raw_output,
                    truth=case["truth"],
                    non_contract_observations=case["non_contract_observations"],
                    human_transcription=case["human_transcription"],
                )
        elif candidate_id == "EXISTING_OPENAI_VLM_BASELINE_CONTRACT":
            contract_errors = g570.validate_visual_proposal(raw_output)
            if not contract_errors:
                baseline_metrics, details = g570.evaluate_visual_proposal(
                    raw_output,
                    truth=case["truth"],
                    non_contract_observations=case["non_contract_observations"],
                    human_transcription=case["human_transcription"],
                )
                metrics.update(baseline_metrics)
        else:
            raise G571SearchError("g571_candidate_unknown")
    exact_error_names = [
        "missed",
        "wrong_role",
        "extra_fact",
        "wrong_value_boundary",
        "invented_value",
    ]
    if candidate_id == "EXPLICIT_NO_CONTRACT_MATCH_ONE_CALL":
        exact_error_names.extend(
            [
                "no_match_missed",
                "no_match_wrong",
                "no_match_extra",
                "no_match_invented",
            ]
        )
    semantic_exact = (
        not transport_failure
        and not contract_errors
        and all(metrics[name] == 0 for name in exact_error_names)
    )
    return {
        "run_id": scheduled["run_id"],
        "case_id": scheduled["case_id"],
        "purpose": scheduled["purpose"],
        "crop_sha256": case["crop_sha256"],
        "raw_output": raw_output,
        "raw_private_response": copy.deepcopy(
            (response or {}).get("raw_private_response")
        ),
        "attempt": attempt,
        "response_hash": (response or {}).get("response_hash"),
        "error": error,
        "transport_failure": transport_failure,
        "contract_errors": contract_errors,
        "contract_invalid": int(bool(contract_errors)),
        "metrics": metrics,
        "details": details,
        "semantic_exact": semantic_exact,
        "single_shot": True,
        "selected": False,
        "repaired": False,
    }


def safe_run_record(run: dict[str, Any]) -> dict[str, Any]:
    attempt = run.get("attempt") if isinstance(run.get("attempt"), dict) else {}
    return {
        "run_id": run["run_id"],
        "case_id": run["case_id"],
        "purpose": run["purpose"],
        "crop_sha256": run["crop_sha256"],
        "request_hash": attempt.get("request_hash"),
        "response_hash": run.get("response_hash"),
        "model_requested": attempt.get("model_requested"),
        "model_resolved": attempt.get("model_resolved"),
        "adapter_identity": attempt.get("adapter_identity"),
        "attempt_number": attempt.get("attempt_number"),
        "hidden_retry": attempt.get("hidden_retry"),
        "provider_failover": attempt.get("provider_failover"),
        "finish_reason": attempt.get("finish_reason"),
        "duration_ms": attempt.get("duration_ms"),
        "usage": copy.deepcopy(attempt.get("usage") or {}),
        "transport_failure": run["transport_failure"],
        "contract_invalid": run["contract_invalid"],
        "contract_error_codes": [
            item.split(":", 1)[0] for item in run["contract_errors"]
        ],
        "metrics": copy.deepcopy(run["metrics"]),
        "semantic_exact": run["semantic_exact"],
        "single_shot": True,
        "selected": False,
        "repaired": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-frozen-runs", action="store_true")
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--private-output-root", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()
    if not args.execute_frozen_runs:
        raise SystemExit("g571_explicit_execution_flag_required")
    if args.timeout_seconds < 1 or args.timeout_seconds > 900:
        raise SystemExit("g571_timeout_out_of_bounds")
    freeze_path = args.freeze.resolve()
    output_root = args.private_output_root.resolve()
    if g570._is_within(output_root, REPO_ROOT.resolve()):
        raise SystemExit("g571_output_inside_repository")
    if output_root.exists():
        raise SystemExit("g571_output_root_must_be_new")
    freeze = g570._read_json(freeze_path)
    cases = validate_freeze(freeze, freeze_path=freeze_path)
    freeze_sha256 = g570._sha256_file(freeze_path)

    request = _openwebui_request(args.env_file.resolve())
    if freeze["candidate_id"] == "EXPLICIT_NO_CONTRACT_MATCH_ONE_CALL":
        adapter = PdfGridExperimentProviderFactory(
            PdfGridProviderConfig(
                provider_profile=freeze["provider_profile"],
                model_id=freeze["model_id"],
                timeout_seconds=args.timeout_seconds,
                maximum_output_tokens=freeze["maximum_output_tokens"],
                maximum_counted_input_tokens=freeze["maximum_counted_input_tokens"],
                thinking_level=freeze["thinking_level"],
            )
        ).create_for_openwebui(request)
    elif freeze["candidate_id"] == "EXISTING_OPENAI_VLM_BASELINE_CONTRACT":
        bundle = PdfDualVlmFactProviderFactory(
            PdfDualVlmFactProviderConfig(
                openai_model_id=freeze["model_id"],
                timeout_seconds=args.timeout_seconds,
                extraction_maximum_output_tokens=freeze["maximum_output_tokens"],
                maximum_counted_input_tokens=freeze["maximum_counted_input_tokens"],
            )
        ).create_for_openwebui(request, include_openai=True)
        if bundle.openai is None:
            raise SystemExit("g571_openai_visual_adapter_missing")
        adapter = bundle.openai
    else:
        raise SystemExit("g571_candidate_unknown")
    qualification = adapter.qualify()
    if qualification.get("status") != "qualified":
        raise SystemExit("g571_provider_not_qualified")

    output_root.mkdir(parents=True)
    model_view = candidate_model_view(freeze["candidate_id"])
    response_schema = candidate_response_schema(freeze["candidate_id"])
    runs_private: list[dict[str, Any]] = []
    runs_safe: list[dict[str, Any]] = []
    journal_path = output_root / "journal.private.jsonl"
    submissions = 0
    for scheduled in freeze["runs"]:
        case = cases[scheduled["case_id"]]
        submissions += 1
        response: dict[str, Any] | None = None
        error: dict[str, Any] | None = None
        try:
            response = adapter.invoke(
                task_id="g571_" + g570._identifier(scheduled["run_id"]),
                model_view=model_view,
                output_schema=response_schema,
                png_bytes=case["crop_path"].read_bytes(),
                crop_sha256=case["crop_sha256"],
                attempt_number=1,
                attempt_lineage=[],
            )
        except Exception as exc:  # every scheduled slot retains one terminal record
            error = {
                "type": type(exc).__name__,
                "code": str(getattr(exc, "code", "g571_provider_exception")),
            }
        run_private = build_run_record(
            scheduled=scheduled,
            case=case,
            candidate_id=freeze["candidate_id"],
            response=response,
            error=error,
        )
        runs_private.append(run_private)
        runs_safe.append(safe_run_record(run_private))
        with journal_path.open("a", encoding="utf-8") as journal:
            journal.write(json.dumps(run_private, ensure_ascii=False) + "\n")

    source_inputs_unchanged = all(
        g570._sha256_file(case["crop_path"]) == case["crop_sha256"]
        and g570._sha256_file(case["source_evidence_path"])
        == case["source_evidence_sha256"]
        for case in cases.values()
    )
    transport_failures = sum(run["transport_failure"] for run in runs_safe)
    contract_invalid = sum(run["contract_invalid"] for run in runs_safe)
    technically_valid = (
        submissions == len(freeze["runs"])
        and source_inputs_unchanged
        and transport_failures == 0
        and contract_invalid == 0
    )
    totals = _sum_metrics(runs_safe)
    usage = _sum_usage(runs_safe)
    duration_ms = sum(int(run.get("duration_ms") or 0) for run in runs_safe)
    private = {
        "schema_version": RESULT_PRIVATE_SCHEMA_VERSION,
        "goal": "G5.71",
        "phase": freeze["phase"],
        "hypothesis_id": freeze["hypothesis_id"],
        "candidate_id": freeze["candidate_id"],
        "solution_frozen": freeze["solution_frozen"],
        "freeze_sha256": freeze_sha256,
        "qualification": qualification,
        "model_view": model_view,
        "response_schema": response_schema,
        "published_response_schema": metadata_proposal_response_schema(),
        "cases": [
            {
                "case_id": case_id,
                "role": case["role"],
                "crop_path": str(case["crop_path"]),
                "crop_sha256": case["crop_sha256"],
                "source_evidence_kind": case["source_evidence_kind"],
                "source_evidence_path": str(case["source_evidence_path"]),
                "source_evidence_sha256": case["source_evidence_sha256"],
                "human_transcription": case["human_transcription"],
                "truth": copy.deepcopy(case["truth"]),
                "non_contract_observations": copy.deepcopy(
                    case["non_contract_observations"]
                ),
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
        "provider_failover": False,
        "best_of_n": False,
        "voting": False,
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
            "G571_SEMANTIC_SEARCH_PHASE_COMPLETE"
            if technically_valid
            else "G571_SEMANTIC_SEARCH_PHASE_TECHNICALLY_INCOMPLETE"
        ),
        "hypothesis_id": freeze["hypothesis_id"],
        "candidate_id": freeze["candidate_id"],
        "solution_frozen": freeze["solution_frozen"],
        "freeze_sha256": freeze_sha256,
        "model_id": freeze["model_id"],
        "model_view_sha256": g570._sha256_json(model_view),
        "response_schema_sha256": g570._sha256_json(response_schema),
        "published_response_schema_sha256": g570._sha256_json(
            metadata_proposal_response_schema()
        ),
        "case_ids": list(cases),
        "provider_calls_per_document": 1,
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
        "provider_failover": False,
        "best_of_n": False,
        "voting": False,
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


def _empty_metrics(missed: int = 0, no_match_missed: int = 0) -> dict[str, int]:
    metrics = g570._empty_metrics(missed)
    metrics.update(
        {
            "no_match_correct": 0,
            "no_match_missed": no_match_missed,
            "no_match_wrong": 0,
            "no_match_extra": 0,
            "no_match_invented": 0,
        }
    )
    return metrics


def _sum_metrics(runs: list[dict[str, Any]]) -> dict[str, int]:
    totals = _empty_metrics()
    for run in runs:
        for name in totals:
            totals[name] += int(run["metrics"].get(name) or 0)
    return totals


def _sum_usage(runs: list[dict[str, Any]]) -> dict[str, int]:
    names = ("input_tokens", "output_tokens", "total_tokens")
    return {
        name: sum(int((run.get("usage") or {}).get(name) or 0) for run in runs)
        for name in names
    }


if __name__ == "__main__":
    raise SystemExit(main())
