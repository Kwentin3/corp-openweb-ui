#!/usr/bin/env python3
"""Qualify one exact economy model on frozen synthetic source fixtures."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.gate2_economy_qualification_policy import (  # noqa: E402
    Gate2EconomyQualificationContractIdentity,
    Gate2EconomyQualificationPolicyFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    gate2_provider_execution_safe_metadata,
    gate2_provider_profile,
    gate2_provider_profile_revision,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    SOURCE_QUALIFICATION_REQUEST_PROFILE,
)
from broker_reports_gate1.gate2_secretary_benchmark import (  # noqa: E402
    DEFAULT_MANIFEST_PATH,
    MANIFEST_SCHEMA_VERSION,
    RESULT_SCHEMA_VERSION,
    compare_secretary_response,
    load_secretary_benchmark_manifest,
    render_safe_benchmark_report,
)
from live_gate2_economy_contract_qualification import (  # noqa: E402
    _completion_boundary,
    _dry_build,
    _live_qualification_action,
    _model_client,
    _published_model_ids,
    _request_context,
    _safe_error,
)
from live_gate2_synthetic_extraction_smoke import (  # noqa: E402
    _current_user,
)
from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _read_env,
    _signin,
)


FACTORY_REQUIRED = (
    "Gate2EconomyQualificationPolicyFactory, "
    "Gate2StructuredModelClientFactory and the frozen secretary comparator "
    "are the only source qualification authorization, execution and "
    "validation entrypoints"
)
FORBIDDEN = (
    "This harness must not use customer data, a live production Pipe, "
    "direct vendor calls, free JSON, repair, fallback, paid tools, "
    "expensive models or raw provider output in its safe receipt"
)

SOURCE_QUALIFICATION_SCHEMA_VERSION = (
    "broker_reports_gate2_source_economy_qualification_v1"
)
SOURCE_QUALIFICATION_PACKAGE_SCHEMA_VERSION = (
    "broker_reports_gate2_source_economy_qualification_package_v1"
)
SOURCE_QUALIFICATION_OUTPUT_SCHEMA_VERSION = (
    "broker_reports_gate2_source_economy_qualification_output_v1"
)
SOURCE_QUALIFICATION_PROMPT_VERSION = (
    "broker_reports_gate2_source_economy_qualification_prompt_v1"
)
ALLOWED_EXACT_MODEL_IDS = (
    "models/gemini-3.1-flash-lite",
    "models/gemini-3.5-flash-lite",
)
PROVIDER_PROFILE_ID = "google_gemini"


@dataclass(frozen=True)
class SourceQualificationFixture:
    manifest_hash: str
    cases: tuple[dict[str, Any], ...]
    prompt: Any
    package: dict[str, Any]
    response_format: dict[str, Any]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    parser.add_argument(
        "--model-id",
        required=True,
        choices=ALLOWED_EXACT_MODEL_IDS,
    )
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()

    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})

    live_action = _live_qualification_action(session, base_url)
    published = _published_model_ids(session, base_url)
    if args.model_id not in published:
        print(
            json.dumps(
                {
                    "schema_version": (SOURCE_QUALIFICATION_SCHEMA_VERSION),
                    "status": "blocked",
                    "failure_code": ("stage_models_endpoint_model_absent"),
                    "qualification_subject": {
                        "exact_model_id": args.model_id,
                        "provider_profile_id": PROVIDER_PROFILE_ID,
                        "workload_class": "gate2_source",
                    },
                    "provider_calls": 0,
                    "customer_calls": 0,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    fixture = build_source_qualification_fixture()
    contract_identity = source_qualification_contract_identity(
        manifest_hash=fixture.manifest_hash
    )
    authorization = (
        Gate2EconomyQualificationPolicyFactory()
        .create()
        .authorize(
            workload_class="gate2_source",
            exact_model_id=args.model_id,
            provider_profile_id=PROVIDER_PROFILE_ID,
            receipt_identity=contract_identity,
        )
    )
    dry_build = _dry_build(
        request_profile=SOURCE_QUALIFICATION_REQUEST_PROFILE,
        provider_profile_id=PROVIDER_PROFILE_ID,
        model_id=args.model_id,
        prompt=fixture.prompt,
        package=fixture.package,
        response_format=fixture.response_format,
    )
    output: dict[str, Any] = {
        "schema_version": SOURCE_QUALIFICATION_SCHEMA_VERSION,
        "qualification_subject": {
            "exact_model_id": args.model_id,
            "provider_profile_id": PROVIDER_PROFILE_ID,
            "workload_class": "gate2_source",
        },
        "boundary": {
            "synthetic_non_customer_only": True,
            "customer_calls": 0,
            "live_production_pipe_used": False,
            "direct_vendor_calls": False,
            "fallback_calls": 0,
            "repair_attempts": 0,
            "paid_tools_used": 0,
            "expensive_model_calls": 0,
            "raw_provider_output_included": False,
        },
        "inventory": {
            "exact_model_published": True,
            "published_models_total": len(published),
            "qualification_action": live_action,
        },
        "qualification_authorization": authorization.safe_receipt(),
        "fixture": {
            "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
            "manifest_sha256": fixture.manifest_hash,
            "contains_customer_data": False,
            "frozen": True,
            "source_cases_total": len(fixture.cases),
            "case_ids": [str(case["case_id"]) for case in fixture.cases],
        },
        "schema_dry_build": dry_build,
        "canonical_validator": {
            "revision": (contract_identity.canonical_validator_revision),
            "changed": False,
        },
    }
    if args.preflight_only:
        output.update(
            {
                "status": "passed",
                "preflight_only": True,
                "provider_calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "actual_cost_usd": "0",
            }
        )
        print(
            json.dumps(
                output,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    user = _current_user(session, base_url)
    client = _model_client(
        request_profile=SOURCE_QUALIFICATION_REQUEST_PROFILE,
        provider_profile_id=PROVIDER_PROFILE_ID,
        user_id=str(user["id"]),
        request_context=_request_context(session, base_url),
        completion=_completion_boundary(
            session=session,
            base_url=base_url,
            timeout=args.timeout,
        ),
    )
    try:
        qualification = asyncio.run(
            qualify_source_model(
                model_client=client,
                model_id=args.model_id,
                fixture=fixture,
            )
        )
    except Exception as exc:
        output.update(
            {
                "status": "failed",
                "provider_calls": 1,
                "provider_generated_output": bool(
                    getattr(exc, "execution_metadata", None)
                ),
                "canonical_validation_ran": False,
                **_safe_error(exc),
            }
        )
        print(
            json.dumps(
                output,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    output["qualification"] = qualification
    output["status"] = qualification["status"]
    output["provider_calls"] = 1
    budget = qualification["economy_budget_receipt"]
    output["input_tokens"] = budget["input_tokens"]
    output["output_tokens"] = budget["output_tokens"]
    output["actual_cost_usd"] = budget["actual_cost_usd"]
    print(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if output["status"] == "passed" else 1


async def qualify_source_model(
    *,
    model_client,
    model_id: str,
    fixture: SourceQualificationFixture,
) -> dict[str, Any]:
    result = await model_client.extract(
        prompt=fixture.prompt,
        package=fixture.package,
        model_id=model_id,
        response_format=fixture.response_format,
    )
    if result.fallback_used:
        raise ValueError("source_qualification_fallback_forbidden")
    if result.repair_attempt_count:
        raise ValueError("source_qualification_repair_forbidden")
    parsed = parse_source_qualification_output(
        result.content,
        case_ids=tuple(str(case["case_id"]) for case in fixture.cases),
    )
    results = tuple(
        compare_secretary_response(
            case,
            parsed[str(case["case_id"])],
            provider_schema_accepted=True,
        )
        for case in fixture.cases
    )
    safe_report = render_safe_benchmark_report(
        benchmark_id="broker_reports_gate2_source_secretary_v1",
        model_id=model_id,
        provider_route=PROVIDER_PROFILE_ID,
        contract_version=SOURCE_QUALIFICATION_OUTPUT_SCHEMA_VERSION,
        results=results,
    )
    budget = result.economy_budget_receipt
    if not isinstance(budget, dict) or budget.get("status") != "passed":
        raise ValueError("source_qualification_budget_receipt_missing")
    execution = result.execution_metadata
    if execution is None:
        raise ValueError("source_qualification_execution_metadata_missing")
    checks = {
        "all_cases_passed": safe_report["status"] == "passed",
        "literal_values_exact": (
            safe_report["aggregate_metrics"]["exact_value_accuracy"] == 1.0
        ),
        "source_bindings_exact": (
            safe_report["aggregate_metrics"]["source_binding_accuracy"] == 1.0
        ),
        "invented_values_zero": (
            safe_report["aggregate_metrics"]["invented_value_count"] == 0
        ),
        "duplicate_bindings_zero": (
            safe_report["aggregate_metrics"]["duplicate_binding_count"] == 0
        ),
        "provider_schema_accepted": (
            safe_report["aggregate_metrics"]["provider_schema_acceptance_rate"] == 1.0
        ),
        "canonical_validator_accepted": (
            safe_report["aggregate_metrics"]["canonical_acceptance_rate"] == 1.0
        ),
        "fallback_zero": result.fallback_used is False,
        "repair_zero": result.repair_attempt_count == 0,
    }
    return {
        "status": ("passed" if checks and all(checks.values()) else "failed"),
        "checks": checks,
        "provider_execution": gate2_provider_execution_safe_metadata(execution),
        "economy_budget_receipt": budget,
        "benchmark_safe_report": safe_report,
        "fallback_used": False,
        "repair_attempt_count": 0,
        "raw_provider_output_included": False,
    }


def build_source_qualification_fixture() -> SourceQualificationFixture:
    manifest_bytes = DEFAULT_MANIFEST_PATH.read_bytes()
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    manifest = load_secretary_benchmark_manifest()
    cases = tuple(
        case for case in manifest["cases"] if case["workload"] == "gate2_source"
    )
    if len(cases) != 5:
        raise ValueError("source_qualification_fixture_count_invalid")
    schema = source_qualification_schema(cases)
    schema_hash = _sha256_json(schema)
    prompt_content = (
        "You are a bounded clerical source secretary for Broker Reports "
        "Gate 2 qualification. Process every named synthetic case. Copy "
        "visible literal strings exactly, including signs, leading zeros, "
        "decimal punctuation, dates and currency spelling. Use only each "
        "case's exact source_ref. Choose only an allowed fact_type and "
        "reason_code. Do not infer missing values, do not duplicate refs, "
        "and do not add prose. Return only the supplied strict schema.\n"
        "{{source_qualification_package_json}}"
    )
    prompt_hash = hashlib.sha256(
        (prompt_content + "\nprompt:" + SOURCE_QUALIFICATION_PROMPT_VERSION).encode(
            "utf-8"
        )
    ).hexdigest()
    prompt = SimpleNamespace(
        content=prompt_content,
        prompt_ref="code:" + SOURCE_QUALIFICATION_PROMPT_VERSION,
        hash=prompt_hash,
        output_schema_id=("broker_reports.gate2.source_economy_qualification.schema"),
        output_schema_version=(SOURCE_QUALIFICATION_OUTPUT_SCHEMA_VERSION),
    )
    package = {
        "schema_version": SOURCE_QUALIFICATION_PACKAGE_SCHEMA_VERSION,
        "package_artifact_ref": ("synthetic:gate2:source:economy:qualification:v1"),
        "llm_context_package": {
            "schema_version": (SOURCE_QUALIFICATION_PACKAGE_SCHEMA_VERSION),
            "contains_customer_data": False,
            "cases": [source_qualification_case_input(case) for case in cases],
        },
        "output_schema": {
            "output_schema_id": prompt.output_schema_id,
            "output_schema_version": (SOURCE_QUALIFICATION_OUTPUT_SCHEMA_VERSION),
            "output_schema_hash": schema_hash,
        },
    }
    return SourceQualificationFixture(
        manifest_hash=manifest_hash,
        cases=cases,
        prompt=prompt,
        package=package,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "broker_reports_gate2_source_qualification",
                "strict": True,
                "schema": schema,
            },
        },
    )


def source_qualification_case_input(
    case: dict[str, Any],
) -> dict[str, Any]:
    expected = case["expected_output"]
    literal_paths = tuple(str(path) for path in case["literal_paths"])
    bounded = case.get("bounded_classifications") or {}
    return {
        "case_id": case["case_id"],
        "instruction": case["input_summary"],
        "source_ref": expected["source_ref"],
        "visible_values": {
            path.rsplit(".", 1)[-1]: _value_at_path(
                expected,
                path,
            )
            for path in literal_paths
        },
        "allowed_fact_types": list(bounded.get("$.fact_type") or []),
        "allowed_reason_codes": list(
            bounded.get("$.reason_code")
            or ["selected_visible_value", "repeated_header"]
        ),
    }


def source_qualification_schema(
    cases: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            str(case["case_id"]): _source_case_schema(case) for case in cases
        },
        "required": [str(case["case_id"]) for case in cases],
        "additionalProperties": False,
    }


def _source_case_schema(case: dict[str, Any]) -> dict[str, Any]:
    expected = case["expected_output"]
    bounded = case.get("bounded_classifications") or {}
    properties: dict[str, Any] = {}
    for key, value in expected.items():
        if key == "schema_version":
            properties[key] = {
                "type": "string",
                "enum": [value],
            }
        elif key == "source_ref":
            properties[key] = {
                "type": "string",
                "enum": [value],
            }
        elif key == "fact_type":
            properties[key] = {
                "type": "string",
                "enum": list(bounded.get("$.fact_type") or [value]),
            }
        elif key == "reason_code":
            properties[key] = {
                "type": "string",
                "enum": list(
                    bounded.get("$.reason_code")
                    or ["selected_visible_value", "repeated_header"]
                ),
            }
        elif value is None:
            properties[key] = {"type": ["string", "null"]}
        else:
            properties[key] = {"type": "string"}
    return {
        "type": "object",
        "properties": properties,
        "required": list(expected),
        "additionalProperties": False,
    }


def parse_source_qualification_output(
    value: Any,
    *,
    case_ids: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    parsed = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("source_qualification_strict_json_required") from exc
    if (
        not isinstance(parsed, dict)
        or set(parsed) != set(case_ids)
        or any(not isinstance(parsed.get(case_id), dict) for case_id in case_ids)
    ):
        raise ValueError("source_qualification_output_shape_invalid")
    return {case_id: dict(parsed[case_id]) for case_id in case_ids}


def source_qualification_contract_identity(
    *,
    manifest_hash: str,
) -> Gate2EconomyQualificationContractIdentity:
    profile = gate2_provider_profile(PROVIDER_PROFILE_ID)
    comparator_hash = hashlib.sha256(
        (
            SERVICE_ROOT / "broker_reports_gate1" / "gate2_secretary_benchmark.py"
        ).read_bytes()
    ).hexdigest()
    return Gate2EconomyQualificationContractIdentity(
        provider_route_revision=gate2_provider_profile_revision(profile),
        input_contract_version=(f"{MANIFEST_SCHEMA_VERSION}:{manifest_hash}"),
        output_contract_version=(SOURCE_QUALIFICATION_OUTPUT_SCHEMA_VERSION),
        prompt_version=SOURCE_QUALIFICATION_PROMPT_VERSION,
        adapter_projection_revision=(
            f"{profile.adapter_id}:{profile.adapter_version}:"
            f"{gate2_provider_profile_revision(profile)}"
        ),
        canonical_validator_revision=(f"{RESULT_SCHEMA_VERSION}:{comparator_hash}"),
    )


def _value_at_path(value: dict[str, Any], path: str) -> Any:
    if not path.startswith("$.") or "[" in path:
        raise ValueError("source_qualification_literal_path_invalid")
    result: Any = value
    for part in path[2:].split("."):
        if not isinstance(result, dict) or part not in result:
            raise ValueError("source_qualification_literal_path_missing")
        result = result[part]
    return result


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
