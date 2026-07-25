#!/usr/bin/env python3
"""Diagnose one Gemini 3.1 unclassified financial response without raw values."""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.gate2_financial_evidence_decision import (  # noqa: E402
    Gate2FinancialEvidenceDecisionError,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_evidence_shadow_qualification import (  # noqa: E402
    Gate2FinancialEvidenceShadowDecisionRunnerFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    gate2_provider_execution_safe_metadata,
    gate2_provider_profile,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    FINANCIAL_EVIDENCE_REQUEST_PROFILE,
)
from broker_reports_gate1.gate2_provider_adapters import (  # noqa: E402
    Gate2ProviderAdapterFactory,
)
from live_gate2_economy_contract_qualification import (  # noqa: E402
    _completion_boundary,
    _dry_build,
    _live_qualification_action,
    _model_client,
    _published_model_ids,
    _qualification_authorizations,
    _request_context,
    build_financial_qualification_cases,
)
from live_gate2_synthetic_extraction_smoke import _current_user  # noqa: E402
from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _read_env,
    _signin,
)


SCHEMA_VERSION = "broker_reports_gate2_financial_unclassified_shape_diagnostic_v1"
EXACT_MODEL_ID = "models/gemini-3.1-flash-lite"
PROVIDER_PROFILE_ID = "google_gemini"
EXPECTED_DECISION_KEYS = frozenset({"disposition", "reason_code", "value_bindings"})
FACTORY_REQUIRED = (
    "Gate2StructuredModelClientFactory and "
    "Gate2FinancialEvidenceShadowDecisionRunnerFactory are the only "
    "provider request and package entrypoints"
)
FORBIDDEN = (
    "This diagnostic must not retain raw provider output, literal values, "
    "customer data, repair, fallback, or more than one provider call"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--receipt-path")
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()
    if not args.preflight_only and not args.receipt_path:
        parser.error("--receipt-path is required for live execution")
    receipt_path = Path(args.receipt_path).resolve() if args.receipt_path else None
    if receipt_path is not None and not receipt_path.name.endswith(".safe.json"):
        parser.error("--receipt-path must end with .safe.json")

    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})

    published = _published_model_ids(session, base_url)
    case = next(
        item
        for item in build_financial_qualification_cases()
        if item.case_id == "unclassified"
    )
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    output: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "qualification_subject": {
            "exact_model_id": EXACT_MODEL_ID,
            "provider_profile_id": PROVIDER_PROFILE_ID,
            "workload_class": "gate2_financial_evidence",
            "case_id": case.case_id,
        },
        "boundary": {
            "synthetic_non_customer_only": True,
            "customer_calls": 0,
            "maximum_provider_calls": 1,
            "fallback_calls": 0,
            "repair_attempts": 0,
            "raw_provider_output_included": False,
            "literal_values_included": False,
        },
        "inventory": {
            "exact_model_published": EXACT_MODEL_ID in published,
            "published_models_total": len(published),
            "qualification_action": _live_qualification_action(session, base_url),
        },
        "qualification_authorization": _qualification_authorizations(
            model_id=EXACT_MODEL_ID,
            provider_profile_id=PROVIDER_PROFILE_ID,
            workload_contracts=(
                (
                    "gate2_financial_evidence",
                    "broker_reports_gate2_financial_evidence_decision_v1",
                ),
            ),
        )[0],
    }
    if EXACT_MODEL_ID not in published:
        output.update(
            {
                "status": "blocked",
                "failure_code": "stage_models_endpoint_model_absent",
                "provider_calls": 0,
            }
        )
        _emit(output)
        return 2

    user = _current_user(session, base_url)
    client = _model_client(
        request_profile=FINANCIAL_EVIDENCE_REQUEST_PROFILE,
        provider_profile_id=PROVIDER_PROFILE_ID,
        user_id=str(user["id"]),
        request_context=_request_context(session, base_url),
        completion=_completion_boundary(
            session=session,
            base_url=base_url,
            timeout=args.timeout,
        ),
    )
    runner = Gate2FinancialEvidenceShadowDecisionRunnerFactory(
        registry=registry,
        model_client=client,
        model_id=EXACT_MODEL_ID,
        provider_profile_id=PROVIDER_PROFILE_ID,
    ).create()
    package = runner.model_package(case.contract, case.source_package)
    response_format = case.contract.openai_response_format()
    dry_build = _dry_build(
        request_profile=FINANCIAL_EVIDENCE_REQUEST_PROFILE,
        provider_profile_id=PROVIDER_PROFILE_ID,
        model_id=EXACT_MODEL_ID,
        prompt=runner.prompt,
        package=package,
        response_format=response_format,
    )
    projection = schema_projection_summary(response_format)
    output["schema_projection"] = {**dry_build, **projection}
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
        _emit(output)
        return 0

    assert receipt_path is not None
    output.update(
        {
            "status": "in_progress",
            "provider_calls": 0,
            "diagnostic": None,
        }
    )
    write_safe_receipt_atomically(path=receipt_path, payload=output)
    diagnostic = asyncio.run(
        diagnose_unclassified_shape(
            model_client=client,
            case=case,
            prompt=runner.prompt,
            package=package,
            response_format=response_format,
            projected_disposition_discriminator_present=projection[
                "adapted_disposition_enum_present"
            ],
        )
    )
    output["diagnostic"] = diagnostic
    output["provider_calls"] = 1
    output["input_tokens"] = diagnostic["economy_budget_receipt"]["input_tokens"]
    output["output_tokens"] = diagnostic["economy_budget_receipt"]["output_tokens"]
    output["actual_cost_usd"] = diagnostic["economy_budget_receipt"]["actual_cost_usd"]
    output["status"] = "passed" if diagnostic["owner_localized"] is True else "failed"
    write_safe_receipt_atomically(path=receipt_path, payload=output)
    _emit(
        {
            "schema_version": SCHEMA_VERSION,
            "status": output["status"],
            "provider_calls": 1,
            "canonical_validation_code": diagnostic["canonical_validation_code"],
            "missing_decision_keys": diagnostic["response_shape"][
                "missing_decision_keys"
            ],
            "extra_decision_keys": diagnostic["response_shape"]["extra_decision_keys"],
            "owner": diagnostic["owner"],
            "receipt_path": str(receipt_path),
            "receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
            "raw_provider_output_included": False,
        }
    )
    return 0 if output["status"] == "passed" else 1


async def diagnose_unclassified_shape(
    *,
    model_client,
    case,
    prompt,
    package: dict[str, Any],
    response_format: dict[str, Any],
    projected_disposition_discriminator_present: bool,
) -> dict[str, Any]:
    result = await model_client.extract(
        prompt=prompt,
        package=package,
        model_id=EXACT_MODEL_ID,
        response_format=response_format,
    )
    shape = safe_decision_shape(result.content)
    canonical_code = "passed"
    try:
        case.contract.parse_model_output(result.content)
    except Gate2FinancialEvidenceDecisionError as exc:
        canonical_code = exc.code
    projection_removed_discriminator = (
        projected_disposition_discriminator_present is False
        and shape["disposition"] == "unclassified_financial_input"
        and (bool(shape["missing_decision_keys"]) or bool(shape["extra_decision_keys"]))
    )
    return {
        "provider_generated_output": True,
        "provider_execution": gate2_provider_execution_safe_metadata(
            result.execution_metadata
        ),
        "economy_budget_receipt": result.economy_budget_receipt,
        "response_shape": shape,
        "canonical_validation_ran": True,
        "canonical_validation_code": canonical_code,
        "projected_disposition_discriminator_present": (
            projected_disposition_discriminator_present
        ),
        "owner_localized": projection_removed_discriminator,
        "owner": (
            "gemini_adapter_projection_disposition_discriminator"
            if projection_removed_discriminator
            else "not_localized"
        ),
        "raw_provider_output_included": False,
        "literal_values_included": False,
        "fallback_used": result.fallback_used,
        "repair_attempt_count": result.repair_attempt_count,
    }


def safe_decision_shape(content: Any) -> dict[str, Any]:
    parsed = json.loads(content) if isinstance(content, str) else content
    root_keys = sorted(parsed) if isinstance(parsed, dict) else []
    decision = parsed.get("decision") if isinstance(parsed, dict) else None
    decision_keys = sorted(decision) if isinstance(decision, dict) else []
    disposition = (
        decision.get("disposition")
        if isinstance(decision, dict) and isinstance(decision.get("disposition"), str)
        else None
    )
    bindings = decision.get("value_bindings") if isinstance(decision, dict) else None
    binding_item_keys = (
        sorted({key for item in bindings if isinstance(item, dict) for key in item})
        if isinstance(bindings, list)
        else []
    )
    return {
        "root_type": _json_type(parsed),
        "root_keys": root_keys,
        "decision_type": _json_type(decision),
        "decision_keys": decision_keys,
        "disposition": disposition,
        "missing_decision_keys": sorted(EXPECTED_DECISION_KEYS - set(decision_keys)),
        "extra_decision_keys": sorted(set(decision_keys) - EXPECTED_DECISION_KEYS),
        "value_bindings_type": _json_type(bindings),
        "value_binding_item_keys": binding_item_keys,
        "raw_values_included": False,
    }


def decision_branch_shapes(schema: dict[str, Any]) -> list[dict[str, Any]]:
    decision = schema.get("properties", {}).get("decision", {})
    variants = decision.get("anyOf") if isinstance(decision, dict) else None
    result = []
    for index, variant in enumerate(variants or []):
        properties = variant.get("properties") if isinstance(variant, dict) else None
        disposition = (
            properties.get("disposition") if isinstance(properties, dict) else None
        )
        result.append(
            {
                "ordinal": index,
                "required_keys": sorted(variant.get("required") or []),
                "property_keys": sorted(properties or {}),
                "disposition_enum_present": (
                    isinstance(disposition, dict)
                    and isinstance(disposition.get("enum"), list)
                ),
            }
        )
    return result


def schema_projection_summary(
    response_format: dict[str, Any],
) -> dict[str, Any]:
    adapter = Gate2ProviderAdapterFactory(
        profile=gate2_provider_profile(PROVIDER_PROFILE_ID),
        capability_probe=True,
    ).create()
    prepared = adapter.prepare_form_data(
        form_data={"response_format": copy.deepcopy(response_format)},
        response_format=response_format,
    )
    canonical_schema = response_format["json_schema"]["schema"]
    adapted_schema = prepared.form_data["response_format"]["json_schema"]["schema"]
    canonical_branches = decision_branch_shapes(canonical_schema)
    adapted_branches = decision_branch_shapes(adapted_schema)
    return {
        "canonical_branches": canonical_branches,
        "adapted_branches": adapted_branches,
        "canonical_disposition_enum_present": all(
            item["disposition_enum_present"] for item in canonical_branches
        ),
        "adapted_disposition_enum_present": all(
            item["disposition_enum_present"] for item in adapted_branches
        ),
        "canonical_schema_hash": prepared.canonical_schema_hash,
        "adapted_schema_hash": prepared.adapted_schema_hash,
        "schema_transform_count": prepared.schema_transform_count,
        "adapter_observation": (
            "Gemini projection removes the disposition enum while retaining "
            "branch-specific object shapes"
        ),
    }


def write_safe_receipt_atomically(
    *,
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)):
        return "number"
    return value.__class__.__name__


def _emit(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
