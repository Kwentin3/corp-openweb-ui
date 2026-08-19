#!/usr/bin/env python3
"""Run one frozen, proof-only VLM-first metadata microstand phase."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from jsonschema import Draft202012Validator
from PIL import Image


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.gate3_llm_metadata_adapter import (  # noqa: E402
    GATE3_LLM_METADATA_INSTRUCTION_VERSION,
    metadata_proposal_response_schema,
)
from broker_reports_gate1.gate3_metadata_source_facts import (  # noqa: E402
    GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
    GATE3_MINIMAL_METADATA_FACT_TYPES,
)
from broker_reports_gate1.pdf_grid_experiment_provider import (  # noqa: E402
    PdfGridExperimentProviderFactory,
    PdfGridProviderConfig,
)
from local_pdf_vlm_guided_intake_development import (  # noqa: E402
    _openwebui_request,
)


FREEZE_SCHEMA_VERSION = "broker_reports_g570_vlm_metadata_freeze_v1"
RESULT_PRIVATE_SCHEMA_VERSION = "broker_reports_g570_vlm_metadata_result_private_v1"
RESULT_SAFE_SCHEMA_VERSION = "broker_reports_g570_vlm_metadata_result_safe_v1"
MODEL_VIEW_SCHEMA_VERSION = "broker_reports_g570_vlm_metadata_model_view_v1"
INSTRUCTION_VERSION = "g570-vlm-first-metadata-v1"
REGION_ALIAS = "m001"
MAX_FACTS = 32

FACTORY_REQUIRED = (
    "PdfGridExperimentProviderFactory.create_for_openwebui is the only provider "
    "entrypoint"
)
FORBIDDEN = (
    "direct provider payloads or secrets, retries, failover, best-of-N, voting, "
    "broker hints, regex semantics, output repair, product activation"
)

VLM_INSTRUCTION = (
    "Read only the attached visual crop, identified as region m001. Extract only "
    "facts that the crop explicitly asserts for the closed metadata contract. "
    "Do not infer missing facts, convert one identifier role into another, or use "
    "value shape as role evidence. Copy only the exact source-authored value, "
    "without its label or delimiter, into source_literal. Use m001 for both source "
    "aliases. For STATEMENT_PERIOD also copy the exact visible start and end "
    "boundary literals. Omit absent or ambiguous facts; an empty facts array is "
    "valid. Return only the strict response object."
)

FACT_SEMANTICS = {
    "PARTY_NAME": (
        "natural person explicitly identified as the current report or account subject"
    ),
    "PERSON_BIRTH_DATE": "birth date explicitly assigned to that person",
    "TAXPAYER_TAX_IDENTIFIER": (
        "tax identifier explicitly assigned to that person, not an issuer"
    ),
    "PERSON_CITIZENSHIP": "citizenship explicitly assigned to that person",
    "DOCUMENT_TYPE": "explicit type of the current report",
    "DOCUMENT_NUMBER": "explicit number of the current report",
    "DOCUMENT_DATE": "explicit date of the current report",
    "STATEMENT_PERIOD": "explicit start and end period of the current report",
    "BROKER_LEGAL_NAME": "legal entity explicitly acting as broker or report issuer",
    "ACCOUNT_IDENTIFIER": "value explicitly identified as a broker or investment account",
    "ACCOUNT_CONTRACT_IDENTIFIER": (
        "value explicitly identified as the current account contract or agreement"
    ),
}


class G570MicrostandError(RuntimeError):
    """Bounded microstand failure with a stable code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-frozen-runs", action="store_true")
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--private-output-root", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()
    if not args.execute_frozen_runs:
        raise SystemExit("g570_explicit_execution_flag_required")
    if args.timeout_seconds < 1 or args.timeout_seconds > 900:
        raise SystemExit("g570_timeout_out_of_bounds")

    freeze_path = args.freeze.resolve()
    output_root = args.private_output_root.resolve()
    if _is_within(output_root, REPO_ROOT.resolve()):
        raise SystemExit("g570_output_inside_repository")
    if output_root.exists():
        raise SystemExit("g570_output_root_must_be_new")
    freeze = _read_json(freeze_path)
    cases = validate_freeze(freeze, freeze_path=freeze_path)
    freeze_sha256 = _sha256_file(freeze_path)

    request = _openwebui_request(args.env_file.resolve())
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
    qualification = adapter.qualify()
    if qualification.get("status") != "qualified":
        raise SystemExit("g570_provider_not_qualified")

    output_root.mkdir(parents=True)
    model_view = visual_metadata_model_view()
    response_schema = metadata_proposal_response_schema()
    runs_private: list[dict[str, Any]] = []
    runs_safe: list[dict[str, Any]] = []
    journal_path = output_root / "journal.private.jsonl"
    submissions = 0

    for scheduled in freeze["runs"]:
        case = cases[scheduled["case_id"]]
        crop_bytes = case["crop_path"].read_bytes()
        task_id = "g570_" + _identifier(scheduled["run_id"])
        submissions += 1
        response: dict[str, Any] | None = None
        error: dict[str, Any] | None = None
        try:
            response = adapter.invoke(
                task_id=task_id,
                model_view=model_view,
                output_schema=response_schema,
                png_bytes=crop_bytes,
                crop_sha256=case["crop_sha256"],
                attempt_number=1,
                attempt_lineage=[],
            )
        except Exception as exc:  # every frozen slot retains one terminal receipt
            error = {
                "type": type(exc).__name__,
                "code": str(getattr(exc, "code", "g570_provider_exception")),
            }
        run_private = build_run_record(
            scheduled=scheduled,
            case=case,
            response=response,
            error=error,
            response_schema=response_schema,
        )
        run_safe = safe_run_record(run_private)
        runs_private.append(run_private)
        runs_safe.append(run_safe)
        with journal_path.open("a", encoding="utf-8") as journal:
            journal.write(json.dumps(run_private, ensure_ascii=False) + "\n")

    source_inputs_unchanged = all(
        _sha256_file(case["crop_path"]) == case["crop_sha256"]
        and _sha256_file(case["source_evidence_path"])
        == case["source_evidence_sha256"]
        for case in cases.values()
    )
    expected_submissions = len(freeze["runs"])
    transport_failures = sum(run["transport_failure"] for run in runs_safe)
    contract_invalid = sum(run["contract_invalid"] for run in runs_safe)
    execution_complete = (
        submissions == expected_submissions and source_inputs_unchanged
    )
    technically_valid = (
        execution_complete and transport_failures == 0 and contract_invalid == 0
    )
    totals = _sum_metrics(runs_safe)
    private = {
        "schema_version": RESULT_PRIVATE_SCHEMA_VERSION,
        "goal": "G5.70",
        "phase": freeze["phase"],
        "freeze_sha256": freeze_sha256,
        "provider_profile": freeze["provider_profile"],
        "model_id": freeze["model_id"],
        "qualification": qualification,
        "model_view": model_view,
        "response_schema": response_schema,
        "cases": [
            {
                "case_id": case_id,
                "role": case["role"],
                "crop_path": str(case["crop_path"]),
                "crop_sha256": case["crop_sha256"],
                "crop_width": case["crop_width"],
                "crop_height": case["crop_height"],
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
        "scheduled_runs": expected_submissions,
        "provider_submissions": submissions,
        "runs": runs_private,
        "totals": totals,
        "transport_failures": transport_failures,
        "contract_invalid": contract_invalid,
        "source_inputs_unchanged": source_inputs_unchanged,
        "execution_complete": execution_complete,
        "technically_valid": technically_valid,
        "retries": 0,
        "provider_failover": False,
        "best_of_n": False,
        "voting": False,
        "result_selection": False,
        "manual_output_repair": False,
        "broker_hints": False,
        "product_activation": False,
    }
    safe = {
        "schema_version": RESULT_SAFE_SCHEMA_VERSION,
        "goal": "G5.70",
        "phase": freeze["phase"],
        "terminal": (
            "VLM_METADATA_MICROSTAND_PHASE_COMPLETE"
            if technically_valid
            else "VLM_METADATA_MICROSTAND_PHASE_TECHNICALLY_INCOMPLETE"
        ),
        "freeze_sha256": freeze_sha256,
        "provider_profile": freeze["provider_profile"],
        "model_id": freeze["model_id"],
        "model_view_sha256": _sha256_json(model_view),
        "response_schema_sha256": _sha256_json(response_schema),
        "case_ids": list(cases),
        "scheduled_runs": expected_submissions,
        "provider_submissions": submissions,
        "runs": runs_safe,
        "totals": totals,
        "transport_failures": transport_failures,
        "contract_invalid": contract_invalid,
        "source_inputs_unchanged": source_inputs_unchanged,
        "execution_complete": execution_complete,
        "technically_valid": technically_valid,
        "retries": 0,
        "provider_failover": False,
        "best_of_n": False,
        "voting": False,
        "result_selection": False,
        "manual_output_repair": False,
        "broker_hints": False,
        "product_activation": False,
        "private_values_committed": False,
    }
    _write_json(output_root / "result.private.json", private)
    _write_json(output_root / "result.safe.json", safe)
    print(json.dumps(safe, ensure_ascii=False, indent=2))
    return 0 if technically_valid else 2


def visual_metadata_model_view() -> dict[str, Any]:
    """Return the one broker-neutral model view used for every crop."""

    if set(FACT_SEMANTICS) != set(GATE3_MINIMAL_METADATA_FACT_TYPES):
        raise G570MicrostandError("g570_contract_semantics_drift")
    return {
        "schema_version": MODEL_VIEW_SCHEMA_VERSION,
        "goal": "G5.70",
        "input": {
            "kind": "VISUAL_CROP",
            "region_alias": REGION_ALIAS,
            "flattened_canonical_text": False,
            "ocr_dump": False,
            "parser_reconstruction": False,
        },
        "contract": {
            "contract_version": GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
            "allowed_fact_types": list(GATE3_MINIMAL_METADATA_FACT_TYPES),
            "fact_semantics": copy.deepcopy(FACT_SEMANTICS),
            "existing_instruction_version": GATE3_LLM_METADATA_INSTRUCTION_VERSION,
            "output_schema": "broker_reports_llm_metadata_proposal_v2",
        },
        "instruction_version": INSTRUCTION_VERSION,
        "instruction": VLM_INSTRUCTION,
        "broker_hints": [],
    }


def validate_freeze(
    freeze: dict[str, Any], *, freeze_path: Path
) -> dict[str, dict[str, Any]]:
    required = {
        "schema_version",
        "goal",
        "phase",
        "contract_version",
        "instruction_version",
        "model_view_sha256",
        "response_schema_sha256",
        "provider_profile",
        "model_id",
        "maximum_output_tokens",
        "maximum_counted_input_tokens",
        "thinking_level",
        "broker_hints",
        "prompt_tuning_after_freeze",
        "product_activation",
        "cases",
        "runs",
    }
    if not isinstance(freeze, dict) or set(freeze) != required:
        raise G570MicrostandError("g570_freeze_fields_invalid")
    if (
        freeze["schema_version"] != FREEZE_SCHEMA_VERSION
        or freeze["goal"] != "G5.70"
        or freeze["phase"] not in {"development_initial", "repeatability", "holdout"}
        or freeze["contract_version"] != GATE3_MINIMAL_METADATA_CONTRACT_VERSION
        or freeze["instruction_version"] != INSTRUCTION_VERSION
        or freeze["model_view_sha256"] != _sha256_json(visual_metadata_model_view())
        or freeze["response_schema_sha256"]
        != _sha256_json(metadata_proposal_response_schema())
        or freeze["provider_profile"] != "google_gemini"
        or freeze["model_id"] != "models/gemini-3.5-flash"
        or freeze["thinking_level"] != "minimal"
        or freeze["broker_hints"] != []
        or freeze["prompt_tuning_after_freeze"] is not False
        or freeze["product_activation"] is not False
    ):
        raise G570MicrostandError("g570_freeze_contract_invalid")
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
            raise G570MicrostandError("g570_freeze_budget_invalid")
    if not isinstance(freeze["cases"], list) or not freeze["cases"]:
        raise G570MicrostandError("g570_freeze_cases_invalid")

    cases: dict[str, dict[str, Any]] = {}
    freeze_root = freeze_path.parent
    for raw in freeze["cases"]:
        case = _validate_case(raw, freeze_root=freeze_root)
        if case["case_id"] in cases:
            raise G570MicrostandError("g570_freeze_case_duplicate")
        cases[case["case_id"]] = case
    if not isinstance(freeze["runs"], list) or not freeze["runs"]:
        raise G570MicrostandError("g570_freeze_runs_invalid")
    run_ids: set[str] = set()
    for run in freeze["runs"]:
        if (
            not isinstance(run, dict)
            or set(run) != {"run_id", "case_id", "purpose"}
            or not _simple_id(run.get("run_id"))
            or run.get("case_id") not in cases
            or run.get("purpose") not in {"initial", "repeatability", "holdout"}
            or run["run_id"] in run_ids
        ):
            raise G570MicrostandError("g570_freeze_run_invalid")
        run_ids.add(run["run_id"])
    return cases


def _validate_case(raw: Any, *, freeze_root: Path) -> dict[str, Any]:
    required = {
        "case_id",
        "role",
        "crop_path",
        "crop_sha256",
        "crop_width",
        "crop_height",
        "truth_authority",
        "human_transcription",
        "truth",
        "non_contract_observations",
    }
    pdf_source_fields = {"source_pdf_path", "source_pdf_sha256"}
    visual_source_fields = {"source_visual_path", "source_visual_sha256"}
    if not isinstance(raw, dict) or set(raw) not in {
        frozenset(required | pdf_source_fields),
        frozenset(required | visual_source_fields),
    }:
        raise G570MicrostandError("g570_freeze_case_fields_invalid")
    if (
        not _simple_id(raw.get("case_id"))
        or raw.get("role")
        not in {
            "BOUNDARY_TWO_COLUMN_METADATA_BLOCK",
            "KNOWN_CLIENT_CODE_ACCOUNT_FAILURE",
            "CLEAN_SUCCESS_CONTROL",
            "UNTOUCHED_HOLDOUT",
        }
        or raw.get("truth_authority") != "VISUAL_HUMAN_TRUTH"
        or not isinstance(raw.get("human_transcription"), str)
        or not raw["human_transcription"].strip()
        or not isinstance(raw.get("truth"), list)
        or not isinstance(raw.get("non_contract_observations"), list)
    ):
        raise G570MicrostandError("g570_freeze_case_invalid")
    crop_path = Path(str(raw["crop_path"]))
    if not crop_path.is_absolute():
        crop_path = (freeze_root / crop_path).resolve()
    if not crop_path.is_file() or crop_path.suffix.lower() != ".png":
        raise G570MicrostandError("g570_crop_missing")
    crop_sha256 = _sha256_file(crop_path)
    if crop_sha256 != raw.get("crop_sha256"):
        raise G570MicrostandError("g570_crop_hash_mismatch")
    with Image.open(crop_path) as image:
        width, height = image.size
        image.verify()
    if width != raw.get("crop_width") or height != raw.get("crop_height"):
        raise G570MicrostandError("g570_crop_dimensions_mismatch")
    if pdf_source_fields <= set(raw):
        source_evidence_kind = "SOURCE_PDF"
        source_path_field = "source_pdf_path"
        source_hash_field = "source_pdf_sha256"
        source_suffix = ".pdf"
    else:
        source_evidence_kind = "VISUAL_PAGE_RENDER"
        source_path_field = "source_visual_path"
        source_hash_field = "source_visual_sha256"
        source_suffix = ".png"
    source_evidence_path = Path(str(raw[source_path_field]))
    if not source_evidence_path.is_absolute():
        source_evidence_path = (freeze_root / source_evidence_path).resolve()
    if (
        not source_evidence_path.is_file()
        or source_evidence_path.suffix.lower() != source_suffix
    ):
        raise G570MicrostandError("g570_source_evidence_missing")
    source_evidence_sha256 = _sha256_file(source_evidence_path)
    if source_evidence_sha256 != raw.get(source_hash_field):
        raise G570MicrostandError("g570_source_evidence_hash_mismatch")
    truth_ids: set[str] = set()
    for fact in raw["truth"]:
        _validate_truth_fact(fact)
        if fact["fact_id"] in truth_ids:
            raise G570MicrostandError("g570_truth_fact_duplicate")
        truth_ids.add(fact["fact_id"])
        if _normalize(fact["source_literal"]) not in _normalize(
            raw["human_transcription"]
        ):
            raise G570MicrostandError("g570_truth_literal_not_visually_transcribed")
    for observation in raw["non_contract_observations"]:
        if (
            not isinstance(observation, dict)
            or set(observation) != {"observation_id", "semantic_role", "source_literal"}
            or not _simple_id(observation.get("observation_id"))
            or not isinstance(observation.get("semantic_role"), str)
            or not observation["semantic_role"]
            or not isinstance(observation.get("source_literal"), str)
            or not observation["source_literal"]
            or _normalize(observation["source_literal"])
            not in _normalize(raw["human_transcription"])
        ):
            raise G570MicrostandError("g570_non_contract_observation_invalid")
    case = copy.deepcopy(raw)
    case["crop_path"] = crop_path
    case["crop_sha256"] = crop_sha256
    case["source_evidence_kind"] = source_evidence_kind
    case["source_evidence_path"] = source_evidence_path
    case["source_evidence_sha256"] = source_evidence_sha256
    return case


def _validate_truth_fact(fact: Any) -> None:
    required = {
        "fact_id",
        "fact_type",
        "source_literal",
        "period_start_literal",
        "period_end_literal",
    }
    if (
        not isinstance(fact, dict)
        or set(fact) != required
        or not _simple_id(fact.get("fact_id"))
        or fact.get("fact_type") not in GATE3_MINIMAL_METADATA_FACT_TYPES
        or not isinstance(fact.get("source_literal"), str)
        or not fact["source_literal"].strip()
    ):
        raise G570MicrostandError("g570_truth_fact_invalid")
    boundaries = (fact["period_start_literal"], fact["period_end_literal"])
    if fact["fact_type"] == "STATEMENT_PERIOD":
        if not all(isinstance(value, str) and value for value in boundaries):
            raise G570MicrostandError("g570_truth_period_boundaries_invalid")
    elif boundaries != (None, None):
        raise G570MicrostandError("g570_truth_non_period_boundaries_invalid")


def build_run_record(
    *,
    scheduled: dict[str, Any],
    case: dict[str, Any],
    response: dict[str, Any] | None,
    error: dict[str, Any] | None,
    response_schema: dict[str, Any],
) -> dict[str, Any]:
    transport_failure = int(error is not None)
    attempt = copy.deepcopy((response or {}).get("attempt") or {})
    raw_output = copy.deepcopy((response or {}).get("json_output"))
    terminal_failure = attempt.get("terminal_failure_class")
    if terminal_failure is not None:
        transport_failure = 1
    contract_errors: list[str] = []
    metrics = _empty_metrics(len(case["truth"]))
    details: dict[str, Any] = {}
    if not transport_failure:
        contract_errors = validate_visual_proposal(
            raw_output, response_schema=response_schema
        )
        if not contract_errors:
            metrics, details = evaluate_visual_proposal(
                raw_output,
                truth=case["truth"],
                non_contract_observations=case["non_contract_observations"],
                human_transcription=case["human_transcription"],
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
        "semantic_exact": (
            not transport_failure
            and not contract_errors
            and metrics["missed"] == 0
            and metrics["wrong_role"] == 0
            and metrics["extra_fact"] == 0
            and metrics["wrong_value_boundary"] == 0
            and metrics["invented_value"] == 0
        ),
        "single_shot": True,
        "selected": False,
        "repaired": False,
    }


def validate_visual_proposal(
    value: Any, *, response_schema: dict[str, Any] | None = None
) -> list[str]:
    schema = response_schema or metadata_proposal_response_schema()
    errors = [
        "json_schema:" + error.json_path + ":" + error.message
        for error in Draft202012Validator(schema).iter_errors(value)
    ]
    if errors or not isinstance(value, dict):
        return sorted(errors) or ["proposal_not_object"]
    facts = value.get("facts")
    if not isinstance(facts, list):
        return ["proposal_facts_invalid"]
    seen: set[tuple[Any, ...]] = set()
    for index, fact in enumerate(facts):
        if not isinstance(fact, dict):
            errors.append(f"fact_{index}_not_object")
            continue
        if fact.get("source_target_alias") != REGION_ALIAS:
            errors.append(f"fact_{index}_source_alias_not_crop")
        if fact.get("role_evidence_target_alias") != REGION_ALIAS:
            errors.append(f"fact_{index}_role_alias_not_crop")
        fact_type = fact.get("fact_type")
        start = fact.get("period_start_literal")
        end = fact.get("period_end_literal")
        if fact_type == "STATEMENT_PERIOD":
            if not all(isinstance(item, str) and item for item in (start, end)):
                errors.append(f"fact_{index}_period_boundaries_missing")
        elif start is not None or end is not None:
            errors.append(f"fact_{index}_non_period_boundaries_present")
        identity = (
            fact_type,
            _normalize(str(fact.get("source_literal") or "")),
            _normalize(str(start or "")),
            _normalize(str(end or "")),
        )
        if identity in seen:
            errors.append(f"fact_{index}_semantic_duplicate")
        seen.add(identity)
    return sorted(errors)


def evaluate_visual_proposal(
    value: dict[str, Any],
    *,
    truth: list[dict[str, Any]],
    non_contract_observations: list[dict[str, Any]],
    human_transcription: str,
) -> tuple[dict[str, int], dict[str, Any]]:
    unmatched_truth = set(range(len(truth)))
    metrics = _empty_metrics(len(truth))
    details: dict[str, list[dict[str, Any]]] = {
        "correct": [],
        "missed": [],
        "wrong_role": [],
        "extra_fact": [],
        "wrong_value_boundary": [],
        "invented_value": [],
    }
    transcription = _normalize(human_transcription)
    observations = {
        _normalize(item["source_literal"]): item
        for item in non_contract_observations
    }
    for proposal_index, proposal in enumerate(value["facts"]):
        exact = next(
            (
                truth_index
                for truth_index in unmatched_truth
                if _fact_exact(proposal, truth[truth_index])
            ),
            None,
        )
        if exact is not None:
            unmatched_truth.remove(exact)
            metrics["correct"] += 1
            details["correct"].append(
                {"proposal_index": proposal_index, "fact_id": truth[exact]["fact_id"]}
            )
            continue
        literal = _normalize(proposal["source_literal"])
        role_match = next(
            (
                truth_index
                for truth_index in unmatched_truth
                if literal == _normalize(truth[truth_index]["source_literal"])
            ),
            None,
        )
        if role_match is not None or literal in observations:
            metrics["wrong_role"] += 1
            detail = {
                "proposal_index": proposal_index,
                "proposed_fact_type": proposal["fact_type"],
            }
            if role_match is not None:
                detail["expected_fact_type"] = truth[role_match]["fact_type"]
            else:
                detail["visible_semantic_role"] = observations[literal]["semantic_role"]
            details["wrong_role"].append(detail)
            continue
        boundary_match = next(
            (
                truth_index
                for truth_index in unmatched_truth
                if proposal["fact_type"] == truth[truth_index]["fact_type"]
                and _literal_overlaps(
                    proposal["source_literal"], truth[truth_index]["source_literal"]
                )
            ),
            None,
        )
        if boundary_match is not None:
            metrics["wrong_value_boundary"] += 1
            details["wrong_value_boundary"].append(
                {
                    "proposal_index": proposal_index,
                    "fact_id": truth[boundary_match]["fact_id"],
                }
            )
            continue
        if literal not in transcription:
            metrics["invented_value"] += 1
            details["invented_value"].append({"proposal_index": proposal_index})
            continue
        metrics["extra_fact"] += 1
        details["extra_fact"].append(
            {"proposal_index": proposal_index, "fact_type": proposal["fact_type"]}
        )

    metrics["missed"] = len(unmatched_truth)
    details["missed"] = [
        {"fact_id": truth[index]["fact_id"], "fact_type": truth[index]["fact_type"]}
        for index in sorted(unmatched_truth)
    ]
    return metrics, details


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


def _fact_exact(proposal: dict[str, Any], truth: dict[str, Any]) -> bool:
    return (
        proposal["fact_type"] == truth["fact_type"]
        and _normalize(proposal["source_literal"])
        == _normalize(truth["source_literal"])
        and _nullable_normalize(proposal["period_start_literal"])
        == _nullable_normalize(truth["period_start_literal"])
        and _nullable_normalize(proposal["period_end_literal"])
        == _nullable_normalize(truth["period_end_literal"])
    )


def _literal_overlaps(left: str, right: str) -> bool:
    left_normalized = _normalize(left)
    right_normalized = _normalize(right)
    return bool(
        left_normalized
        and right_normalized
        and (
            left_normalized in right_normalized
            or right_normalized in left_normalized
        )
    )


def _empty_metrics(missed: int = 0) -> dict[str, int]:
    return {
        "correct": 0,
        "missed": missed,
        "wrong_role": 0,
        "extra_fact": 0,
        "wrong_value_boundary": 0,
        "invented_value": 0,
    }


def _sum_metrics(runs: list[dict[str, Any]]) -> dict[str, int]:
    totals = _empty_metrics()
    for run in runs:
        for key in totals:
            totals[key] += int((run.get("metrics") or {}).get(key) or 0)
    return totals


def _nullable_normalize(value: Any) -> str | None:
    return _normalize(value) if isinstance(value, str) else None


def _normalize(value: str) -> str:
    return " ".join(str(value).replace("\u00a0", " ").replace("\u202f", " ").split())


def _simple_id(value: Any) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 120
        and all(character.isalnum() or character in "_-" for character in value)
    )


def _identifier(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value)


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise G570MicrostandError("g570_freeze_read_failed") from exc
    if not isinstance(value, dict):
        raise G570MicrostandError("g570_freeze_not_object")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
