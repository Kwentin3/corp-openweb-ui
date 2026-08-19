#!/usr/bin/env python3
"""Run the proof-only G5.72 visual-Markdown metadata microstand."""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any

from jsonschema import Draft202012Validator
import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

import live_g570_vlm_metadata_microstand as g570  # noqa: E402
from broker_reports_gate1.gate2_model_clients import (  # noqa: E402
    Gate2StructuredModelClientFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2StructuredModelClientConfig,
    gate2_provider_execution_safe_metadata,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    GATE3_LLM_METADATA_REQUEST_PROFILE,
)
from broker_reports_gate1.gate3_llm_metadata_adapter import (  # noqa: E402
    GATE3_LLM_METADATA_INSTRUCTION,
    GATE3_LLM_METADATA_INSTRUCTION_VERSION,
    GATE3_LLM_METADATA_PROPOSAL_SCHEMA_VERSION,
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
from broker_reports_gate1.pdf_dual_vlm_fact_providers import (  # noqa: E402
    PdfDualVlmFactProviderConfig,
    PdfDualVlmFactProviderFactory,
)
from live_gate2_economy_contract_qualification import (  # noqa: E402
    _completion_boundary,
    _request_context,
)
from live_gate2_synthetic_extraction_smoke import _current_user  # noqa: E402
from live_gate3_chunk_batch_labeling import (  # noqa: E402
    _base_url,
    _is_within,
    _read_env,
    _signin,
    _url,
)
from local_pdf_vlm_guided_intake_development import (  # noqa: E402
    _openwebui_request,
)


TRANSCRIPTION_SCHEMA_VERSION = "visual_region_markdown_transcription_v1"
TRANSCRIPTION_VIEW_VERSION = "visual_region_to_markdown_view_v1"
TRANSCRIPTION_INSTRUCTION_VERSION = "faithful_visual_markdown_v1"
TRANSCRIPTION_RESULT_PRIVATE_VERSION = "broker_reports_g572_transcription_private_v1"
TRANSCRIPTION_RESULT_SAFE_VERSION = "broker_reports_g572_transcription_safe_v1"
HUMAN_AUDIT_SCHEMA_VERSION = "broker_reports_g572_human_visual_audit_v1"
CLASSIFICATION_FREEZE_VERSION = "broker_reports_g572_classification_freeze_v1"
CLASSIFICATION_RESULT_PRIVATE_VERSION = "broker_reports_g572_classification_private_v1"
CLASSIFICATION_RESULT_SAFE_VERSION = "broker_reports_g572_classification_safe_v1"
REGION_ALIAS = "m001"
DEVELOPMENT_CASE_IDS = ("case_b", "case_f", "case_c")
GEMINI_ARM = {
    "arm": "gemini",
    "provider_profile": "google_gemini",
    "model_id": "models/gemini-3.5-flash",
}
STRONG_ARM = {
    "arm": "strong",
    "provider_profile": "openai_gpt",
    "model_id": "gpt-5.6-sol",
}

FACTORY_REQUIRED = (
    "PdfGridExperimentProviderFactory.create_for_openwebui owns image-to-Markdown; "
    "Gate2StructuredModelClientFactory.create owns Gemini text classification; "
    "PdfDualVlmFactProviderFactory.create_for_openwebui owns OpenAI Responses text"
)
FORBIDDEN = (
    "direct provider transport, metadata vocabulary in visual transcription, "
    "Markdown repair, model-specific prompts, retries, best-of-N, voting, judge, "
    "broker rules, regex semantics, product activation or financial reasoning"
)

TRANSCRIPTION_INSTRUCTION = (
    "Transfer the content of the attached image region into Markdown as faithfully "
    "as possible. Preserve the source words, labels, values, lines, tables, "
    "headings, row and column relationships, and value boundaries. Do not classify "
    "the content, rename any label, explain its meaning, correct the source, or add "
    "information that is not visibly present. Return the Markdown transcription in "
    "the required response object."
)

AUDIT_COUNT_FIELDS = (
    "lost_source_text",
    "invented_text",
    "semantic_rewrites",
    "broken_label_value_relations",
    "broken_row_column_relations",
    "changed_value_boundaries",
)


class G572Error(RuntimeError):
    """Stable proof-harness terminal."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def transcription_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "markdown"],
        "properties": {
            "schema_version": {
                "type": "string",
                "enum": [TRANSCRIPTION_SCHEMA_VERSION],
            },
            "markdown": {"type": "string", "minLength": 1, "maxLength": 16_384},
        },
    }


def transcription_model_view() -> dict[str, Any]:
    return {
        "schema_version": TRANSCRIPTION_VIEW_VERSION,
        "input": {"kind": "IMAGE_REGION", "region_alias": REGION_ALIAS},
        "instruction_version": TRANSCRIPTION_INSTRUCTION_VERSION,
        "instruction": TRANSCRIPTION_INSTRUCTION,
    }


def semantic_model_visible_request(markdown: str) -> dict[str, Any]:
    if not isinstance(markdown, str) or not markdown.strip():
        raise G572Error("g572_frozen_markdown_invalid")
    contract = {
        "contract_version": GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
        "allowed_fact_types": list(GATE3_MINIMAL_METADATA_FACT_TYPES),
        "output_schema_version": GATE3_LLM_METADATA_PROPOSAL_SCHEMA_VERSION,
    }
    context = {
        "context_policy": "immutable_visual_markdown_v1",
        "regions": [
            {
                "alias": REGION_ALIAS,
                "content_kind": "FROZEN_MARKDOWN",
                "content": markdown,
            }
        ],
    }
    schema = metadata_proposal_response_schema()
    return {
        "messages": [
            {"role": "system", "content": GATE3_LLM_METADATA_INSTRUCTION},
            {
                "role": "user",
                "content": json.dumps(contract, ensure_ascii=False, separators=(",", ":")),
            },
            {
                "role": "user",
                "content": json.dumps(context, ensure_ascii=False, separators=(",", ":")),
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": GATE3_LLM_METADATA_PROPOSAL_SCHEMA_VERSION,
                "strict": True,
                "schema": schema,
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    transcribe = subparsers.add_parser("transcribe")
    transcribe.add_argument("--execute-frozen-transcription", action="store_true")
    transcribe.add_argument("--source-freeze", type=Path, required=True)
    transcribe.add_argument("--private-output-root", type=Path, required=True)
    transcribe.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    transcribe.add_argument("--timeout-seconds", type=int, default=300)

    freeze = subparsers.add_parser("freeze-classification")
    freeze.add_argument("--transcription-result", type=Path, required=True)
    freeze.add_argument("--human-audit", type=Path, required=True)
    freeze.add_argument("--output", type=Path, required=True)
    freeze.add_argument(
        "--phase",
        choices=(
            "development_initial",
            "strong_transport_replay",
            "repeatability",
        ),
        required=True,
    )
    freeze.add_argument("--prior-result", type=Path)
    freeze.add_argument("--candidate-arm", action="append", default=[])

    classify = subparsers.add_parser("classify")
    classify.add_argument("--execute-frozen-classification", action="store_true")
    classify.add_argument("--freeze", type=Path, required=True)
    classify.add_argument("--private-output-root", type=Path, required=True)
    classify.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    classify.add_argument("--timeout-seconds", type=int, default=300)

    args = parser.parse_args()
    if args.command == "transcribe":
        return run_transcription(args)
    if args.command == "freeze-classification":
        build_classification_freeze(args)
        return 0
    return run_classification(args)


def run_transcription(args: argparse.Namespace) -> int:
    if not args.execute_frozen_transcription:
        raise G572Error("g572_explicit_transcription_flag_required")
    if args.timeout_seconds < 1 or args.timeout_seconds > 900:
        raise G572Error("g572_timeout_out_of_bounds")
    source_freeze_path = args.source_freeze.resolve()
    output_root = args.private_output_root.resolve()
    _require_new_private_root(output_root)
    source_freeze = _read_json(source_freeze_path)
    cases = _load_development_cases(source_freeze, source_freeze_path)
    request = _openwebui_request(args.env_file.resolve())
    adapter = PdfGridExperimentProviderFactory(
        PdfGridProviderConfig(
            provider_profile=source_freeze["provider_profile"],
            model_id=source_freeze["model_id"],
            timeout_seconds=args.timeout_seconds,
            maximum_output_tokens=source_freeze["maximum_output_tokens"],
            maximum_counted_input_tokens=source_freeze[
                "maximum_counted_input_tokens"
            ],
            thinking_level=source_freeze["thinking_level"],
        )
    ).create_for_openwebui(request)
    qualification = adapter.qualify()
    if qualification.get("status") != "qualified":
        raise G572Error("g572_transcription_provider_not_qualified")

    output_root.mkdir(parents=True)
    schema = transcription_response_schema()
    model_view = transcription_model_view()
    private_runs: list[dict[str, Any]] = []
    safe_runs: list[dict[str, Any]] = []
    for case_id in DEVELOPMENT_CASE_IDS:
        case = cases[case_id]
        crop_bytes = case["crop_path"].read_bytes()
        response = None
        error = None
        try:
            response = adapter.invoke(
                task_id=f"g572_transcribe_{case_id}",
                model_view=model_view,
                output_schema=schema,
                png_bytes=crop_bytes,
                crop_sha256=case["crop_sha256"],
                attempt_number=1,
                attempt_lineage=[],
            )
        except Exception as exc:  # one terminal record per frozen slot
            error = {
                "type": type(exc).__name__,
                "code": str(getattr(exc, "code", "g572_provider_exception")),
            }
        private_run = _transcription_run(case_id, case, response, error, schema)
        private_runs.append(private_run)
        safe_runs.append(_safe_transcription_run(private_run))

    technically_valid = all(
        not run["transport_failure"] and not run["contract_errors"]
        for run in private_runs
    )
    source_inputs_unchanged = all(
        _sha256_file(case["crop_path"]) == case["crop_sha256"]
        for case in cases.values()
    )
    private = {
        "schema_version": TRANSCRIPTION_RESULT_PRIVATE_VERSION,
        "goal": "G5.72",
        "phase": "development_transcription",
        "source_freeze_sha256": _sha256_file(source_freeze_path),
        "model_id": source_freeze["model_id"],
        "model_view": model_view,
        "response_schema": schema,
        "qualification": qualification,
        "cases": [_private_case(case_id, cases[case_id]) for case_id in DEVELOPMENT_CASE_IDS],
        "runs": private_runs,
        "provider_submissions": len(private_runs),
        "source_inputs_unchanged": source_inputs_unchanged,
        "technically_valid": technically_valid,
        "metadata_roles_visible_to_transcriber": False,
        "broker_hints": 0,
        "manual_markdown_repair": False,
        "retries": 0,
        "best_of_n": False,
        "product_activation": False,
    }
    safe = {
        "schema_version": TRANSCRIPTION_RESULT_SAFE_VERSION,
        "goal": "G5.72",
        "phase": "development_transcription",
        "terminal": (
            "G572_VISUAL_MARKDOWN_READY_FOR_HUMAN_AUDIT"
            if technically_valid and source_inputs_unchanged
            else "G572_VISUAL_MARKDOWN_TECHNICALLY_INCOMPLETE"
        ),
        "source_freeze_sha256": private["source_freeze_sha256"],
        "model_id": private["model_id"],
        "model_view_sha256": _sha256_json(model_view),
        "response_schema_sha256": _sha256_json(schema),
        "case_ids": list(DEVELOPMENT_CASE_IDS),
        "runs": safe_runs,
        "provider_submissions": len(private_runs),
        "source_inputs_unchanged": source_inputs_unchanged,
        "technically_valid": technically_valid,
        "metadata_roles_visible_to_transcriber": False,
        "broker_hints": 0,
        "manual_markdown_repair": False,
        "retries": 0,
        "best_of_n": False,
        "private_values_committed": False,
        "product_activation": False,
    }
    _write_json(output_root / "result.private.json", private)
    _write_json(output_root / "result.safe.json", safe)
    print(json.dumps(safe, ensure_ascii=False, indent=2))
    return 0 if technically_valid and source_inputs_unchanged else 2


def build_classification_freeze(args: argparse.Namespace) -> None:
    result_path = args.transcription_result.resolve()
    audit_path = args.human_audit.resolve()
    output_path = args.output.resolve()
    if _is_within(output_path, REPO_ROOT.resolve()):
        raise G572Error("g572_classification_freeze_inside_repository")
    if output_path.exists():
        raise G572Error("g572_classification_freeze_exists")
    result = _read_json(result_path)
    audit = _read_json(audit_path)
    qualified = validate_human_audit(
        transcription_result=result,
        transcription_result_sha256=_sha256_file(result_path),
        audit=audit,
    )
    arms = [copy.deepcopy(GEMINI_ARM), copy.deepcopy(STRONG_ARM)]
    if args.phase == "development_initial":
        if args.prior_result is not None or args.candidate_arm:
            raise G572Error("g572_initial_freeze_arguments_invalid")
        runs = [
            {
                "run_id": f"initial_{arm['arm']}_{case_id}",
                "arm": arm["arm"],
                "case_id": case_id,
                "ordinal": 1,
            }
            for arm in arms
            for case_id in DEVELOPMENT_CASE_IDS
        ]
    elif args.phase == "strong_transport_replay":
        runs = _strong_transport_replay_runs(
            prior_result_path=args.prior_result,
            candidate_arms=args.candidate_arm,
        )
    else:
        runs = _repeatability_runs(
            prior_result_path=args.prior_result,
            candidate_arms=args.candidate_arm,
            arms=arms,
        )
    freeze = {
        "schema_version": CLASSIFICATION_FREEZE_VERSION,
        "goal": "G5.72",
        "phase": args.phase,
        "transcription_result_sha256": _sha256_file(result_path),
        "human_audit_sha256": _sha256_file(audit_path),
        "contract_version": GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
        "semantic_instruction_version": GATE3_LLM_METADATA_INSTRUCTION_VERSION,
        "semantic_instruction_sha256": _sha256_text(GATE3_LLM_METADATA_INSTRUCTION),
        "response_schema_sha256": _sha256_json(metadata_proposal_response_schema()),
        "arms": arms,
        "cases": qualified,
        "runs": runs,
        "same_markdown_across_models": True,
        "model_specific_prompt": False,
        "broker_hints": 0,
        "regex_semantics": 0,
        "manual_markdown_repair": False,
        "retries": 0,
        "best_of_n": False,
        "voting": False,
        "judge_model": False,
        "product_activation": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output_path, freeze)
    print(json.dumps(_safe_freeze(freeze, output_path), ensure_ascii=False, indent=2))


def validate_human_audit(
    *,
    transcription_result: dict[str, Any],
    transcription_result_sha256: str,
    audit: dict[str, Any],
) -> list[dict[str, Any]]:
    if (
        transcription_result.get("schema_version")
        != TRANSCRIPTION_RESULT_PRIVATE_VERSION
        or transcription_result.get("technically_valid") is not True
        or audit.get("schema_version") != HUMAN_AUDIT_SCHEMA_VERSION
        or audit.get("transcription_result_sha256")
        != transcription_result_sha256
        or audit.get("auditor") != "HUMAN_VISUAL_COMPARISON"
    ):
        raise G572Error("g572_human_audit_binding_invalid")
    audit_cases = audit.get("cases")
    if not isinstance(audit_cases, list) or len(audit_cases) != 3:
        raise G572Error("g572_human_audit_cases_invalid")
    by_case = {item.get("case_id"): item for item in audit_cases if isinstance(item, dict)}
    run_by_case = {item["case_id"]: item for item in transcription_result["runs"]}
    case_by_id = {item["case_id"]: item for item in transcription_result["cases"]}
    if set(by_case) != set(DEVELOPMENT_CASE_IDS):
        raise G572Error("g572_human_audit_case_ids_invalid")
    qualified: list[dict[str, Any]] = []
    for case_id in DEVELOPMENT_CASE_IDS:
        item = by_case[case_id]
        run = run_by_case[case_id]
        output = run.get("raw_output")
        markdown = output.get("markdown") if isinstance(output, dict) else None
        if (
            set(item)
            != {
                "case_id",
                "markdown_sha256",
                *AUDIT_COUNT_FIELDS,
                "qualified",
                "classification",
                "notes",
            }
            or not isinstance(markdown, str)
            or item.get("markdown_sha256") != _sha256_text(markdown)
            or any(
                not isinstance(item.get(field), int)
                or isinstance(item.get(field), bool)
                or item[field] < 0
                for field in AUDIT_COUNT_FIELDS
            )
        ):
            raise G572Error("g572_human_audit_case_invalid")
        clean = all(item[field] == 0 for field in AUDIT_COUNT_FIELDS)
        if item.get("qualified") is not clean:
            raise G572Error("g572_human_audit_qualification_invalid")
        if not clean:
            raise G572Error("g572_visual_markdown_intermediate_not_reliable")
        source_case = case_by_id[case_id]
        qualified.append(
            {
                "case_id": case_id,
                "role": source_case["role"],
                "crop_sha256": source_case["crop_sha256"],
                "markdown": markdown,
                "markdown_sha256": _sha256_text(markdown),
                "human_visual_transcription": source_case["human_transcription"],
                "truth": copy.deepcopy(source_case["truth"]),
                "non_contract_observations": copy.deepcopy(
                    source_case["non_contract_observations"]
                ),
                "audit_classification": item["classification"],
            }
        )
    return qualified


def run_classification(args: argparse.Namespace) -> int:
    if not args.execute_frozen_classification:
        raise G572Error("g572_explicit_classification_flag_required")
    if args.timeout_seconds < 1 or args.timeout_seconds > 900:
        raise G572Error("g572_timeout_out_of_bounds")
    freeze_path = args.freeze.resolve()
    output_root = args.private_output_root.resolve()
    _require_new_private_root(output_root)
    freeze = _read_json(freeze_path)
    _validate_classification_freeze(freeze)
    output_root.mkdir(parents=True)

    scheduled_arms = {item["arm"] for item in freeze["runs"]}
    submissions = {arm["arm"]: 0 for arm in freeze["arms"]}
    clients: dict[str, Any] = {}
    if "gemini" in scheduled_arms:
        env = _read_env(args.env_file.resolve())
        base_url = _base_url(env)
        session = requests.Session()
        session.headers.update({"Accept": "application/json"})
        session.get(_url(base_url, "/health"), timeout=20).raise_for_status()
        token = _signin(session, base_url, env)
        session.headers.update({"Authorization": f"Bearer {token}"})
        live_user_id = str(_current_user(session, base_url).get("id") or "")
        if not live_user_id:
            raise G572Error("g572_authenticated_user_missing")
        base_completion = _completion_boundary(
            session=session,
            base_url=base_url,
            timeout=args.timeout_seconds,
        )
    else:
        session = None
        live_user_id = ""
        base_completion = None
    for arm in freeze["arms"]:
        arm_id = arm["arm"]
        if arm_id != "gemini" or arm_id not in scheduled_arms:
            continue

        def counted_completion(*, form_data, _arm=arm_id, **kwargs):
            submissions[_arm] += 1
            if base_completion is None:
                raise G572Error("g572_completion_boundary_missing")
            return base_completion(form_data=form_data, **kwargs)

        clients[arm_id] = Gate2StructuredModelClientFactory(
            config=Gate2StructuredModelClientConfig(
                request_profile=GATE3_LLM_METADATA_REQUEST_PROFILE,
                provider_profile_id=arm["provider_profile"],
                capability_probe=False,
                economy_budget_enforcement=False,
            ),
            user=SimpleNamespace(id=live_user_id),
            request=_request_context(session, base_url),
            completion_resolver=lambda _user_id, completion=counted_completion: (
                completion,
                SimpleNamespace(id=live_user_id),
            ),
        ).create()

    strong_adapter = None
    strong_qualification = None
    if "strong" in scheduled_arms:
        bundle = PdfDualVlmFactProviderFactory(
            PdfDualVlmFactProviderConfig(
                openai_model_id=STRONG_ARM["model_id"],
                timeout_seconds=args.timeout_seconds,
                extraction_maximum_output_tokens=16_384,
                maximum_counted_input_tokens=24_000,
            )
        ).create_for_openwebui(
            _openwebui_request(args.env_file.resolve()), include_openai=True
        )
        strong_adapter = bundle.openai
        if strong_adapter is None:
            raise G572Error("g572_strong_text_adapter_missing")
        strong_qualification = strong_adapter.qualify()
        if strong_qualification.get("status") != "qualified":
            raise G572Error("g572_strong_text_model_not_qualified")

    cases = {item["case_id"]: item for item in freeze["cases"]}
    arms = {item["arm"]: item for item in freeze["arms"]}
    private_runs: list[dict[str, Any]] = []
    safe_runs: list[dict[str, Any]] = []
    for scheduled in freeze["runs"]:
        case = cases[scheduled["case_id"]]
        arm = arms[scheduled["arm"]]
        before = submissions[arm["arm"]]
        if arm["arm"] == "strong":
            submissions["strong"] += 1
            private_run = _classify_strong_once(
                scheduled=scheduled,
                case=case,
                arm=arm,
                adapter=strong_adapter,
            )
        else:
            private_run = asyncio.run(
                _classify_once(
                    scheduled=scheduled,
                    case=case,
                    arm=arm,
                    client=clients[arm["arm"]],
                )
            )
        private_run["provider_submissions"] = submissions[arm["arm"]] - before
        private_runs.append(private_run)
        safe_runs.append(_safe_classification_run(private_run))

    expected_submissions = len(freeze["runs"])
    actual_submissions = sum(submissions.values())
    technically_valid = (
        actual_submissions == expected_submissions
        and all(
            not run["transport_failure"] and not run["contract_errors"]
            for run in private_runs
        )
    )
    totals = g570._sum_metrics(safe_runs)
    private = {
        "schema_version": CLASSIFICATION_RESULT_PRIVATE_VERSION,
        "goal": "G5.72",
        "phase": freeze["phase"],
        "freeze_sha256": _sha256_file(freeze_path),
        "arms": copy.deepcopy(freeze["arms"]),
        "strong_qualification": strong_qualification,
        "cases": copy.deepcopy(freeze["cases"]),
        "runs": private_runs,
        "totals": totals,
        "provider_submissions": actual_submissions,
        "technically_valid": technically_valid,
        "same_markdown_across_models": True,
        "model_specific_prompt": False,
        "retries": 0,
        "best_of_n": False,
        "voting": False,
        "judge_model": False,
        "manual_output_repair": False,
        "product_activation": False,
    }
    safe = {
        "schema_version": CLASSIFICATION_RESULT_SAFE_VERSION,
        "goal": "G5.72",
        "phase": freeze["phase"],
        "terminal": (
            "G572_MARKDOWN_CLASSIFICATION_PHASE_COMPLETE"
            if technically_valid
            else "G572_MARKDOWN_CLASSIFICATION_PHASE_TECHNICALLY_INCOMPLETE"
        ),
        "freeze_sha256": private["freeze_sha256"],
        "arms": copy.deepcopy(freeze["arms"]),
        "case_ids": list(cases),
        "runs": safe_runs,
        "totals": totals,
        "provider_submissions": actual_submissions,
        "technically_valid": technically_valid,
        "same_markdown_across_models": True,
        "semantic_instruction_sha256": freeze["semantic_instruction_sha256"],
        "response_schema_sha256": freeze["response_schema_sha256"],
        "model_specific_prompt": False,
        "retries": 0,
        "best_of_n": False,
        "voting": False,
        "judge_model": False,
        "manual_output_repair": False,
        "private_values_committed": False,
        "product_activation": False,
    }
    _write_json(output_root / "result.private.json", private)
    _write_json(output_root / "result.safe.json", safe)
    print(json.dumps(safe, ensure_ascii=False, indent=2))
    return 0 if technically_valid else 2


async def _classify_once(
    *, scheduled: dict[str, Any], case: dict[str, Any], arm: dict[str, Any], client: Any
) -> dict[str, Any]:
    request = semantic_model_visible_request(case["markdown"])
    raw_output = None
    model_result = None
    error = None
    try:
        model_result = await client.propose_gate3_metadata_once(
            model_visible_request=request,
            canonical_schema=metadata_proposal_response_schema(),
            model_id=arm["model_id"],
        )
        raw_output = _decode_output(model_result.adapter_extracted_output)
    except Exception as exc:  # one terminal record per frozen slot
        error = {
            "type": type(exc).__name__,
            "code": str(getattr(exc, "code", "g572_provider_exception")),
            "failure_class": getattr(exc, "failure_class", None),
        }
    transport_failure = int(error is not None)
    contract_errors = []
    metrics = g570._empty_metrics(len(case["truth"]))
    details: dict[str, Any] = {}
    if not transport_failure:
        contract_errors = g570.validate_visual_proposal(
            raw_output, response_schema=metadata_proposal_response_schema()
        )
        if not contract_errors:
            metrics, details = g570.evaluate_visual_proposal(
                raw_output,
                truth=case["truth"],
                non_contract_observations=case["non_contract_observations"],
                human_transcription=case["markdown"],
            )
    execution = (
        gate2_provider_execution_safe_metadata(model_result.execution_metadata)
        if model_result is not None
        else None
    )
    return {
        "run_id": scheduled["run_id"],
        "case_id": scheduled["case_id"],
        "arm": scheduled["arm"],
        "ordinal": scheduled["ordinal"],
        "markdown_sha256": case["markdown_sha256"],
        "model_visible_request": request,
        "prepared_request": copy.deepcopy(
            model_result.prepared_request.form_data if model_result else None
        ),
        "raw_provider_response": copy.deepcopy(
            model_result.raw_provider_response if model_result else None
        ),
        "raw_output": raw_output,
        "error": error,
        "execution": execution,
        "transport_failure": transport_failure,
        "contract_errors": contract_errors,
        "contract_invalid": int(bool(contract_errors)),
        "metrics": metrics,
        "details": details,
        "semantic_exact": (
            not transport_failure
            and not contract_errors
            and all(
                metrics[field] == 0
                for field in (
                    "missed",
                    "wrong_role",
                    "extra_fact",
                    "wrong_value_boundary",
                    "invented_value",
                )
            )
        ),
        "single_shot": True,
        "selected": False,
        "repaired": False,
    }


def _classify_strong_once(
    *, scheduled: dict[str, Any], case: dict[str, Any], arm: dict[str, Any], adapter: Any
) -> dict[str, Any]:
    if adapter is None:
        raise G572Error("g572_strong_text_adapter_missing")
    request = semantic_model_visible_request(case["markdown"])
    response = None
    error = None
    try:
        response = adapter.invoke_text(
            task_id=f"g572_{scheduled['run_id']}",
            model_visible_request=request,
            output_schema=metadata_proposal_response_schema(),
            attempt_number=1,
            attempt_lineage=[],
        )
    except Exception as exc:  # one terminal record per frozen slot
        error = {
            "type": type(exc).__name__,
            "code": str(getattr(exc, "code", "g572_provider_exception")),
            "failure_class": getattr(exc, "failure_class", None),
        }
    attempt = copy.deepcopy((response or {}).get("attempt") or {})
    raw_output = copy.deepcopy((response or {}).get("json_output"))
    transport_failure = int(
        error is not None or attempt.get("terminal_failure_class") is not None
    )
    contract_errors = []
    metrics = g570._empty_metrics(len(case["truth"]))
    details: dict[str, Any] = {}
    if not transport_failure:
        contract_errors = g570.validate_visual_proposal(
            raw_output, response_schema=metadata_proposal_response_schema()
        )
        if not contract_errors:
            metrics, details = g570.evaluate_visual_proposal(
                raw_output,
                truth=case["truth"],
                non_contract_observations=case["non_contract_observations"],
                human_transcription=case["markdown"],
            )
    usage = attempt.get("usage") if isinstance(attempt.get("usage"), dict) else {}
    execution = {
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "duration_ms": attempt.get("duration_ms"),
    }
    return {
        "run_id": scheduled["run_id"],
        "case_id": scheduled["case_id"],
        "arm": scheduled["arm"],
        "ordinal": scheduled["ordinal"],
        "markdown_sha256": case["markdown_sha256"],
        "model_visible_request": request,
        "prepared_request": None,
        "raw_provider_response": copy.deepcopy(
            (response or {}).get("raw_private_response")
        ),
        "raw_output": raw_output,
        "attempt": attempt,
        "error": error,
        "execution": execution,
        "transport_failure": transport_failure,
        "contract_errors": contract_errors,
        "contract_invalid": int(bool(contract_errors)),
        "metrics": metrics,
        "details": details,
        "semantic_exact": (
            not transport_failure
            and not contract_errors
            and all(
                metrics[field] == 0
                for field in (
                    "missed",
                    "wrong_role",
                    "extra_fact",
                    "wrong_value_boundary",
                    "invented_value",
                )
            )
        ),
        "single_shot": True,
        "selected": False,
        "repaired": False,
    }


def _load_development_cases(
    source_freeze: dict[str, Any], source_freeze_path: Path
) -> dict[str, dict[str, Any]]:
    raw_cases = source_freeze.get("cases")
    if (
        source_freeze.get("provider_profile") != "google_gemini"
        or source_freeze.get("model_id") != GEMINI_ARM["model_id"]
        or not isinstance(raw_cases, list)
    ):
        raise G572Error("g572_source_freeze_invalid")
    by_case = {item.get("case_id"): item for item in raw_cases if isinstance(item, dict)}
    if set(by_case) != set(DEVELOPMENT_CASE_IDS):
        raise G572Error("g572_development_cases_invalid")
    result: dict[str, dict[str, Any]] = {}
    for case_id in DEVELOPMENT_CASE_IDS:
        raw = copy.deepcopy(by_case[case_id])
        crop_path = (source_freeze_path.parent / raw["crop_path"]).resolve()
        if _sha256_file(crop_path) != raw["crop_sha256"]:
            raise G572Error("g572_crop_hash_mismatch")
        raw["crop_path"] = crop_path
        result[case_id] = raw
    return result


def _transcription_run(
    case_id: str,
    case: dict[str, Any],
    response: dict[str, Any] | None,
    error: dict[str, Any] | None,
    schema: dict[str, Any],
) -> dict[str, Any]:
    raw_output = copy.deepcopy((response or {}).get("json_output"))
    attempt = copy.deepcopy((response or {}).get("attempt") or {})
    transport_failure = int(error is not None or attempt.get("terminal_failure_class") is not None)
    contract_errors = (
        [
            "json_schema:" + item.json_path + ":" + item.message
            for item in Draft202012Validator(schema).iter_errors(raw_output)
        ]
        if not transport_failure
        else []
    )
    return {
        "case_id": case_id,
        "crop_sha256": case["crop_sha256"],
        "raw_output": raw_output,
        "raw_private_response": copy.deepcopy((response or {}).get("raw_private_response")),
        "attempt": attempt,
        "response_hash": (response or {}).get("response_hash"),
        "error": error,
        "transport_failure": transport_failure,
        "contract_errors": sorted(contract_errors),
        "single_shot": True,
        "selected": False,
        "repaired": False,
    }


def _safe_transcription_run(run: dict[str, Any]) -> dict[str, Any]:
    output = run.get("raw_output")
    markdown = output.get("markdown") if isinstance(output, dict) else None
    attempt = run.get("attempt") if isinstance(run.get("attempt"), dict) else {}
    usage = attempt.get("usage") if isinstance(attempt.get("usage"), dict) else {}
    return {
        "case_id": run["case_id"],
        "crop_sha256": run["crop_sha256"],
        "markdown_sha256": _sha256_text(markdown) if isinstance(markdown, str) else None,
        "markdown_characters": len(markdown) if isinstance(markdown, str) else 0,
        "transport_failure": run["transport_failure"],
        "contract_invalid": int(bool(run["contract_errors"])),
        "total_tokens": usage.get("total_tokens"),
        "duration_ms": attempt.get("duration_ms"),
        "human_audit_required": True,
    }


def _safe_classification_run(run: dict[str, Any]) -> dict[str, Any]:
    execution = run.get("execution") if isinstance(run.get("execution"), dict) else {}
    return {
        "run_id": run["run_id"],
        "case_id": run["case_id"],
        "arm": run["arm"],
        "ordinal": run["ordinal"],
        "markdown_sha256": run["markdown_sha256"],
        "provider_submissions": run.get("provider_submissions", 0),
        "transport_failure": run["transport_failure"],
        "contract_invalid": run["contract_invalid"],
        "metrics": copy.deepcopy(run["metrics"]),
        "semantic_exact": run["semantic_exact"],
        "input_tokens": execution.get("input_tokens"),
        "output_tokens": execution.get("output_tokens"),
        "total_tokens": execution.get("total_tokens"),
        "duration_ms": execution.get("duration_ms"),
    }


def _private_case(case_id: str, case: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "role": case["role"],
        "crop_path": str(case["crop_path"]),
        "crop_sha256": case["crop_sha256"],
        "human_transcription": case["human_transcription"],
        "truth": copy.deepcopy(case["truth"]),
        "non_contract_observations": copy.deepcopy(case["non_contract_observations"]),
    }


def _repeatability_runs(
    *, prior_result_path: Path | None, candidate_arms: list[str], arms: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if prior_result_path is None or not candidate_arms:
        raise G572Error("g572_repeatability_candidate_required")
    allowed = {item["arm"] for item in arms}
    if len(set(candidate_arms)) != len(candidate_arms) or not set(candidate_arms) <= allowed:
        raise G572Error("g572_repeatability_candidate_invalid")
    prior = _read_json(prior_result_path.resolve())
    if prior.get("schema_version") != CLASSIFICATION_RESULT_PRIVATE_VERSION:
        raise G572Error("g572_repeatability_prior_invalid")
    for arm in candidate_arms:
        arm_runs = [item for item in prior["runs"] if item["arm"] == arm]
        if {item["case_id"] for item in arm_runs} != set(DEVELOPMENT_CASE_IDS) or not all(
            item["semantic_exact"] for item in arm_runs
        ):
            raise G572Error("g572_repeatability_candidate_not_clean")
    return [
        {
            "run_id": f"repeat_{arm}_{case_id}_{ordinal}",
            "arm": arm,
            "case_id": case_id,
            "ordinal": ordinal,
        }
        for arm in candidate_arms
        for case_id in ("case_b", "case_f")
        for ordinal in (1, 2, 3)
    ]


def _strong_transport_replay_runs(
    *, prior_result_path: Path | None, candidate_arms: list[str]
) -> list[dict[str, Any]]:
    if prior_result_path is None or candidate_arms:
        raise G572Error("g572_strong_transport_replay_arguments_invalid")
    prior = _read_json(prior_result_path.resolve())
    if prior.get("schema_version") != CLASSIFICATION_RESULT_PRIVATE_VERSION:
        raise G572Error("g572_strong_transport_replay_prior_invalid")
    strong_runs = [item for item in prior.get("runs", []) if item.get("arm") == "strong"]
    if (
        {item.get("case_id") for item in strong_runs} != set(DEVELOPMENT_CASE_IDS)
        or not all(
            item.get("transport_failure") == 1 and item.get("raw_output") is None
            for item in strong_runs
        )
    ):
        raise G572Error("g572_strong_transport_replay_not_technical")
    return [
        {
            "run_id": f"strong_transport_replay_{case_id}",
            "arm": "strong",
            "case_id": case_id,
            "ordinal": 1,
        }
        for case_id in DEVELOPMENT_CASE_IDS
    ]


def _validate_classification_freeze(freeze: dict[str, Any]) -> None:
    arms = freeze.get("arms")
    cases = freeze.get("cases")
    runs = freeze.get("runs")
    if (
        freeze.get("schema_version") != CLASSIFICATION_FREEZE_VERSION
        or freeze.get("goal") != "G5.72"
        or freeze.get("phase")
        not in {
            "development_initial",
            "strong_transport_replay",
            "repeatability",
        }
        or freeze.get("contract_version") != GATE3_MINIMAL_METADATA_CONTRACT_VERSION
        or freeze.get("semantic_instruction_version")
        != GATE3_LLM_METADATA_INSTRUCTION_VERSION
        or freeze.get("semantic_instruction_sha256")
        != _sha256_text(GATE3_LLM_METADATA_INSTRUCTION)
        or freeze.get("response_schema_sha256")
        != _sha256_json(metadata_proposal_response_schema())
        or arms != [GEMINI_ARM, STRONG_ARM]
        or not isinstance(cases, list)
        or {item.get("case_id") for item in cases if isinstance(item, dict)}
        != set(DEVELOPMENT_CASE_IDS)
        or not isinstance(runs, list)
        or freeze.get("same_markdown_across_models") is not True
        or freeze.get("model_specific_prompt") is not False
        or freeze.get("manual_markdown_repair") is not False
    ):
        raise G572Error("g572_classification_freeze_invalid")
    for case in cases:
        if _sha256_text(case.get("markdown")) != case.get("markdown_sha256"):
            raise G572Error("g572_frozen_markdown_hash_mismatch")
    case_ids = {item["case_id"] for item in cases}
    arm_ids = {item["arm"] for item in arms}
    if any(
        item.get("case_id") not in case_ids
        or item.get("arm") not in arm_ids
        or not isinstance(item.get("ordinal"), int)
        for item in runs
    ):
        raise G572Error("g572_classification_schedule_invalid")


def _safe_freeze(freeze: dict[str, Any], path: Path) -> dict[str, Any]:
    return {
        "schema_version": CLASSIFICATION_FREEZE_VERSION,
        "goal": "G5.72",
        "phase": freeze["phase"],
        "freeze_sha256": _sha256_file(path),
        "arms": copy.deepcopy(freeze["arms"]),
        "case_ids": [item["case_id"] for item in freeze["cases"]],
        "markdown_sha256": {
            item["case_id"]: item["markdown_sha256"] for item in freeze["cases"]
        },
        "scheduled_runs": len(freeze["runs"]),
        "same_markdown_across_models": True,
        "model_specific_prompt": False,
        "private_values_committed": False,
    }


def _decode_output(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return copy.deepcopy(value)


def _require_new_private_root(path: Path) -> None:
    if _is_within(path, REPO_ROOT.resolve()):
        raise G572Error("g572_output_inside_repository")
    if path.exists():
        raise G572Error("g572_output_root_must_be_new")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G572Error("g572_json_object_required")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _sha256_text(value: Any) -> str:
    if not isinstance(value, str):
        raise G572Error("g572_text_required")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
