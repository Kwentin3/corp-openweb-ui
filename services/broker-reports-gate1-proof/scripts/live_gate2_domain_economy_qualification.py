#!/usr/bin/env python3
"""Qualify one exact economy model on frozen synthetic domain fixtures."""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.gate2_candidate_binding_runtime import (  # noqa: E402
    Gate2CandidateBindingRuntimeFactory,
    candidate_binding_response_format,
    candidate_binding_schema_hash,
    parse_candidate_binding_model_output,
)
from broker_reports_gate1.gate2_domain_finalization import (  # noqa: E402
    Gate2DomainCandidateFinalizerFactory,
)
from broker_reports_gate1.gate2_domain_packages import (  # noqa: E402
    Gate2DomainPackageBuilderConfig,
    Gate2DomainPackageBuilderFactory,
    validate_domain_extraction_package,
)
from broker_reports_gate1.gate2_domain_routing import (  # noqa: E402
    Gate2SourceUnitRouterFactory,
)
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
    DOMAIN_QUALIFICATION_REQUEST_PROFILE,
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
    "Gate2StructuredModelClientFactory, Gate2SourceUnitRouterFactory, "
    "Gate2DomainPackageBuilderFactory, "
    "Gate2CandidateBindingRuntimeFactory and "
    "Gate2DomainCandidateFinalizerFactory are the only domain "
    "qualification authorization, execution and canonical validation "
    "entrypoints"
)
FORBIDDEN = (
    "This harness must not use customer data, a live production Pipe, "
    "direct vendor calls, free JSON, repair, fallback, paid tools, "
    "expensive models, cross-row bindings or raw provider output in its "
    "safe receipt"
)

DOMAIN_QUALIFICATION_SCHEMA_VERSION = (
    "broker_reports_gate2_domain_economy_qualification_v1"
)
DOMAIN_QUALIFICATION_MANIFEST_SCHEMA_VERSION = (
    "broker_reports_gate2_domain_qualification_manifest_v1"
)
DOMAIN_QUALIFICATION_PACKAGE_SCHEMA_VERSION = (
    "broker_reports_gate2_domain_economy_qualification_package_v1"
)
DOMAIN_QUALIFICATION_PROMPT_VERSION = (
    "broker_reports_gate2_domain_economy_qualification_prompt_v1"
)
DOMAIN_QUALIFICATION_COMPARATOR_VERSION = (
    "broker_reports_gate2_domain_qualification_comparator_v1"
)
DOMAIN_QUALIFICATION_OUTPUT_VERSION = "broker_reports_candidate_binding_output_v0"
DEFAULT_MANIFEST_PATH = (
    SERVICE_ROOT / "benchmarks" / "gate2_domain_qualification_v1" / "manifest.json"
)
ALLOWED_EXACT_MODEL_IDS = (
    "models/gemini-3.1-flash-lite",
    "models/gemini-3.5-flash-lite",
)
PROVIDER_PROFILE_ID = "google_gemini"


@dataclass(frozen=True)
class DomainQualificationCase:
    case_id: str
    family: str
    package: dict[str, Any]
    expected_selection: dict[str, Any]
    forbidden_source_refs: tuple[str, ...]
    response_format: dict[str, Any]
    prompt: Any


@dataclass(frozen=True)
class DomainQualificationFixture:
    manifest_hash: str
    cases: tuple[DomainQualificationCase, ...]


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
                    "schema_version": DOMAIN_QUALIFICATION_SCHEMA_VERSION,
                    "status": "blocked",
                    "failure_code": "stage_models_endpoint_model_absent",
                    "qualification_subject": {
                        "exact_model_id": args.model_id,
                        "provider_profile_id": PROVIDER_PROFILE_ID,
                        "workload_class": "gate2_domain",
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

    fixture = build_domain_qualification_fixture()
    contract_identity = domain_qualification_contract_identity(
        manifest_hash=fixture.manifest_hash
    )
    authorization = (
        Gate2EconomyQualificationPolicyFactory()
        .create()
        .authorize(
            workload_class="gate2_domain",
            exact_model_id=args.model_id,
            provider_profile_id=PROVIDER_PROFILE_ID,
            receipt_identity=contract_identity,
        )
    )
    preflight_cases = [
        {
            "case_id": case.case_id,
            "family": case.family,
            "extractor_domain": case.package["extractor_domain"],
            "candidate_source_refs_total": len(case.package["candidate_source_refs"]),
            "candidate_ids_total": len(
                case.package["source_value_candidate_set"]["candidate_ids"]
            ),
            "relation_ids_total": len(
                case.package["candidate_relation_set"]["relation_ids"]
            ),
            "forbidden_source_refs_total": len(case.forbidden_source_refs),
            "schema_dry_build": _dry_build(
                request_profile=DOMAIN_QUALIFICATION_REQUEST_PROFILE,
                provider_profile_id=PROVIDER_PROFILE_ID,
                model_id=args.model_id,
                prompt=case.prompt,
                package=case.package,
                response_format=case.response_format,
            ),
        }
        for case in fixture.cases
    ]
    estimated_input_tokens = sum(
        int(item["schema_dry_build"]["estimated_input_tokens"])
        for item in preflight_cases
    )
    estimated_maximum_cost = sum(
        (
            Decimal(str(item["schema_dry_build"]["estimated_cost_usd"]))
            for item in preflight_cases
        ),
        Decimal("0"),
    )
    output: dict[str, Any] = {
        "schema_version": DOMAIN_QUALIFICATION_SCHEMA_VERSION,
        "qualification_subject": {
            "exact_model_id": args.model_id,
            "provider_profile_id": PROVIDER_PROFILE_ID,
            "workload_class": "gate2_domain",
        },
        "boundary": {
            "synthetic_non_customer_only": True,
            "customer_calls": 0,
            "live_production_pipe_used": False,
            "direct_vendor_calls": False,
            "free_json_used": False,
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
            "manifest_schema_version": (DOMAIN_QUALIFICATION_MANIFEST_SCHEMA_VERSION),
            "manifest_sha256": fixture.manifest_hash,
            "contains_customer_data": False,
            "frozen": True,
            "domain_cases_total": len(fixture.cases),
            "case_ids": [case.case_id for case in fixture.cases],
            "families": sorted({case.family for case in fixture.cases}),
        },
        "preflight_cases": preflight_cases,
        "preflight_aggregate": {
            "provider_calls_if_executed": len(fixture.cases),
            "estimated_input_tokens_total": estimated_input_tokens,
            "estimated_maximum_cost_usd": format(
                estimated_maximum_cost,
                "f",
            ),
            "maximum_output_tokens_per_call": max(
                int(item["schema_dry_build"]["maximum_output_tokens"])
                for item in preflight_cases
            ),
        },
        "canonical_validator": {
            "revision": contract_identity.canonical_validator_revision,
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
        request_profile=DOMAIN_QUALIFICATION_REQUEST_PROFILE,
        provider_profile_id=PROVIDER_PROFILE_ID,
        user_id=str(user["id"]),
        request_context=_request_context(session, base_url),
        completion=_completion_boundary(
            session=session,
            base_url=base_url,
            timeout=args.timeout,
        ),
    )
    execution = asyncio.run(
        qualify_domain_model(
            model_client=client,
            model_id=args.model_id,
            fixture=fixture,
        )
    )
    output["qualification"] = execution["qualification"]
    output["status"] = execution["status"]
    output["provider_calls"] = execution["provider_calls"]
    output["input_tokens"] = execution["input_tokens"]
    output["output_tokens"] = execution["output_tokens"]
    output["actual_cost_usd"] = execution["actual_cost_usd"]
    if execution.get("failure"):
        output["failure"] = execution["failure"]
    print(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if output["status"] == "passed" else 1


async def qualify_domain_model(
    *,
    model_client,
    model_id: str,
    fixture: DomainQualificationFixture,
) -> dict[str, Any]:
    case_receipts: list[dict[str, Any]] = []
    provider_calls = 0
    input_tokens = 0
    output_tokens = 0
    actual_cost = Decimal("0")
    failure: dict[str, Any] | None = None

    for case in fixture.cases:
        provider_calls += 1
        try:
            result = await model_client.extract(
                prompt=case.prompt,
                package=case.package,
                model_id=model_id,
                response_format=case.response_format,
            )
        except Exception as exc:
            failure = {
                "case_id": case.case_id,
                "provider_generated_output": bool(
                    getattr(exc, "execution_metadata", None)
                ),
                "canonical_validation_ran": False,
                **_safe_error(exc),
            }
            break
        if result.fallback_used:
            failure = {
                "case_id": case.case_id,
                "failure_code": "domain_qualification_fallback_forbidden",
                "provider_generated_output": True,
                "canonical_validation_ran": False,
            }
            break
        if result.repair_attempt_count:
            failure = {
                "case_id": case.case_id,
                "failure_code": "domain_qualification_repair_forbidden",
                "provider_generated_output": True,
                "canonical_validation_ran": False,
            }
            break
        budget = result.economy_budget_receipt
        if not isinstance(budget, dict) or budget.get("status") != "passed":
            failure = {
                "case_id": case.case_id,
                "failure_code": ("domain_qualification_budget_receipt_missing"),
                "provider_generated_output": True,
                "canonical_validation_ran": False,
            }
            break
        input_tokens += int(budget["input_tokens"])
        output_tokens += int(budget["output_tokens"])
        actual_cost += Decimal(str(budget["actual_cost_usd"]))
        case_receipts.append(
            validate_domain_qualification_output(
                case=case,
                content=result.content,
                provider_execution=(
                    gate2_provider_execution_safe_metadata(result.execution_metadata)
                ),
                budget_receipt=budget,
            )
        )

    all_cases_executed = len(case_receipts) == len(fixture.cases)
    all_cases_passed = all(receipt["status"] == "passed" for receipt in case_receipts)
    aggregate = {
        "cases_expected": len(fixture.cases),
        "cases_executed": len(case_receipts),
        "cases_passed": sum(receipt["status"] == "passed" for receipt in case_receipts),
        "cases_failed": sum(receipt["status"] != "passed" for receipt in case_receipts),
        "canonical_package_acceptance_rate": _rate(
            receipt["checks"]["canonical_package_valid"] for receipt in case_receipts
        ),
        "canonical_selection_acceptance_rate": _rate(
            receipt["checks"]["canonical_selection_valid"] for receipt in case_receipts
        ),
        "exact_expected_selection_rate": _rate(
            receipt["checks"]["exact_expected_selection"] for receipt in case_receipts
        ),
        "finalized_package_acceptance_rate": _rate(
            receipt["checks"]["finalized_domain_package_valid"]
            for receipt in case_receipts
        ),
        "lost_expected_candidate_count": sum(
            int(receipt["metrics"]["lost_expected_candidate_count"])
            for receipt in case_receipts
        ),
        "cross_row_binding_count": sum(
            int(receipt["metrics"]["cross_row_binding_count"])
            for receipt in case_receipts
        ),
        "forbidden_source_ref_count": sum(
            int(receipt["metrics"]["forbidden_source_ref_count"])
            for receipt in case_receipts
        ),
        "invented_candidate_id_count": sum(
            int(receipt["metrics"]["invented_candidate_id_count"])
            for receipt in case_receipts
        ),
        "duplicate_candidate_binding_count": sum(
            int(receipt["metrics"]["duplicate_candidate_binding_count"])
            for receipt in case_receipts
        ),
        "fallback_calls": 0,
        "repair_attempts": 0,
        "raw_provider_output_included": False,
    }
    status = (
        "passed"
        if failure is None and all_cases_executed and all_cases_passed
        else "failed"
    )
    return {
        "status": status,
        "provider_calls": provider_calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "actual_cost_usd": format(actual_cost, "f"),
        "qualification": {
            "status": status,
            "aggregate_metrics": aggregate,
            "cases": case_receipts,
            "fallback_used": False,
            "repair_attempt_count": 0,
            "raw_provider_output_included": False,
        },
        "failure": failure,
    }


def validate_domain_qualification_output(
    *,
    case: DomainQualificationCase,
    content: Any,
    provider_execution: dict[str, Any],
    budget_receipt: dict[str, Any],
) -> dict[str, Any]:
    selection = parse_candidate_binding_model_output(content)
    validate_domain_extraction_package(case.package)
    outcome = (
        Gate2CandidateBindingRuntimeFactory()
        .create()
        .validate_and_materialize(
            selection=selection,
            package=case.package,
        )
    )
    canonical_selection_valid = (
        outcome.validation.get("validator_status") == "passed"
        and outcome.legacy_candidate is not None
    )
    canonical_actual = canonicalize_selection(selection)
    canonical_expected = canonicalize_selection(case.expected_selection)
    mismatch_paths = sorted(_mismatch_paths(canonical_expected, canonical_actual))
    metrics = domain_selection_metrics(
        case=case,
        selection=selection,
    )
    finalized_valid = False
    finalized_coverage_status: str | None = None
    if canonical_selection_valid and outcome.legacy_candidate is not None:
        finalized = (
            Gate2DomainCandidateFinalizerFactory()
            .create()
            .finalize(
                candidate=outcome.legacy_candidate,
                package=case.package,
            )
        )
        coverage = (
            finalized.get("coverage")
            if isinstance(finalized.get("coverage"), dict)
            else {}
        )
        finalized_coverage_status = str(coverage.get("coverage_status") or "")
        finalized_valid = (
            finalized.get("schema_version") == "broker_reports_source_facts_v0"
            and finalized_coverage_status == "complete"
            and set(coverage.get("selected_source_refs") or [])
            == set(case.package["candidate_source_refs"])
            and set(coverage.get("fact_covered_refs") or [])
            == set(case.package["candidate_source_refs"])
        )
    checks = {
        "canonical_package_valid": True,
        "canonical_selection_valid": canonical_selection_valid,
        "exact_expected_selection": not mismatch_paths,
        "selected_refs_belong_to_package": (metrics["foreign_source_ref_count"] == 0),
        "cross_row_bindings_zero": (metrics["cross_row_binding_count"] == 0),
        "forbidden_source_refs_zero": (metrics["forbidden_source_ref_count"] == 0),
        "lost_expected_candidates_zero": (
            metrics["lost_expected_candidate_count"] == 0
        ),
        "duplicate_candidate_bindings_zero": (
            metrics["duplicate_candidate_binding_count"] == 0
        ),
        "invented_candidate_ids_zero": (metrics["invented_candidate_id_count"] == 0),
        "finalized_domain_package_valid": finalized_valid,
        "fallback_zero": True,
        "repair_zero": True,
    }
    return {
        "case_id": case.case_id,
        "family": case.family,
        "extractor_domain": case.package["extractor_domain"],
        "status": ("passed" if checks and all(checks.values()) else "failed"),
        "checks": checks,
        "metrics": metrics,
        "mismatch_paths": mismatch_paths,
        "canonical_validation": {
            "validator_status": outcome.validation.get("validator_status"),
            "error_code_counts": copy.deepcopy(
                outcome.validation.get("error_code_counts") or {}
            ),
            "finalized_coverage_status": finalized_coverage_status,
        },
        "provider_execution": provider_execution,
        "economy_budget_receipt": copy.deepcopy(budget_receipt),
        "provider_generated_output": True,
        "canonical_validation_ran": True,
        "raw_provider_output_included": False,
    }


def domain_selection_metrics(
    *,
    case: DomainQualificationCase,
    selection: dict[str, Any],
) -> dict[str, int]:
    candidate_set = case.package["source_value_candidate_set"]
    candidate_by_id = {
        str(item["candidate_id"]): item for item in candidate_set["candidates"]
    }
    allowed_ids = set(candidate_by_id)
    allowed_source_refs = set(case.package["candidate_source_refs"])
    forbidden = set(case.forbidden_source_refs)
    expected_ids = {
        str(item["candidate_id"])
        for result in case.expected_selection["binding_results"]
        for item in result["selected_bindings"]
    }
    selected_ids: list[str] = []
    cross_row = 0
    forbidden_count = 0
    foreign_source = 0
    for result in selection.get("binding_results") or []:
        if not isinstance(result, dict):
            continue
        source_ref = str(result.get("source_ref") or "")
        if source_ref not in allowed_source_refs:
            foreign_source += 1
        if source_ref in forbidden:
            forbidden_count += 1
        for binding in result.get("selected_bindings") or []:
            if not isinstance(binding, dict):
                continue
            candidate_id = str(binding.get("candidate_id") or "")
            selected_ids.append(candidate_id)
            candidate = candidate_by_id.get(candidate_id)
            if candidate is None:
                continue
            if str(candidate.get("row_ref") or "") != source_ref:
                cross_row += 1
            if forbidden & {
                str(candidate.get("row_ref") or ""),
                *(
                    str(value)
                    for value in candidate.get(
                        "source_value_refs",
                        [],
                    )
                ),
            }:
                forbidden_count += 1
    selected_set = set(selected_ids)
    return {
        "selected_candidate_count": len(selected_ids),
        "expected_candidate_count": len(expected_ids),
        "lost_expected_candidate_count": len(expected_ids - selected_set),
        "invented_candidate_id_count": len(selected_set - allowed_ids),
        "duplicate_candidate_binding_count": (len(selected_ids) - len(selected_set)),
        "cross_row_binding_count": cross_row,
        "forbidden_source_ref_count": forbidden_count,
        "foreign_source_ref_count": foreign_source,
    }


def build_domain_qualification_fixture(
    path: Path = DEFAULT_MANIFEST_PATH,
) -> DomainQualificationFixture:
    manifest_bytes = path.read_bytes()
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version")
        != DOMAIN_QUALIFICATION_MANIFEST_SCHEMA_VERSION
        or manifest.get("contains_customer_data") is not False
        or manifest.get("frozen") is not True
    ):
        raise ValueError("domain_qualification_manifest_invalid")
    raw_cases = manifest.get("cases")
    if not isinstance(raw_cases, list) or len(raw_cases) != 5:
        raise ValueError("domain_qualification_case_count_invalid")
    case_ids = [
        str(item.get("case_id") or "") for item in raw_cases if isinstance(item, dict)
    ]
    if (
        len(case_ids) != len(raw_cases)
        or len(set(case_ids)) != len(case_ids)
        or any(not case_id for case_id in case_ids)
    ):
        raise ValueError("domain_qualification_case_ids_invalid")
    cases = tuple(
        _build_domain_case(raw_case)
        for raw_case in raw_cases
        if isinstance(raw_case, dict)
    )
    return DomainQualificationFixture(
        manifest_hash=manifest_hash,
        cases=cases,
    )


def _build_domain_case(raw_case: dict[str, Any]) -> DomainQualificationCase:
    case_id = _required_text(raw_case, "case_id")
    family = _required_text(raw_case, "family")
    target_domain = _required_text(raw_case, "target_domain")
    base_package = _build_base_package(raw_case)
    route = Gate2SourceUnitRouterFactory().create().route(base_package)
    packages = (
        Gate2DomainPackageBuilderFactory(
            Gate2DomainPackageBuilderConfig(
                candidate_binding_enabled=True,
            )
        )
        .create()
        .build(
            base_package=base_package,
            route=route,
        )
    )
    package = next(
        (value for value in packages if value.get("extractor_domain") == target_domain),
        None,
    )
    if package is None:
        raise ValueError(f"domain_qualification_target_package_missing:{case_id}")
    package["package_artifact_ref"] = f"synthetic:gate2:domain:qualification:{case_id}"
    package["expected_source_facts_set_id"] = f"sfset_domain_qualification_{case_id}"
    package["expected_candidate_audit"] = {
        "qualification_only": True,
        "prompt_ref": ("code:" + DOMAIN_QUALIFICATION_PROMPT_VERSION),
        "repair_attempt_count": 0,
    }
    validate_domain_extraction_package(package)
    expected_selection = _expected_selection(
        raw_case=raw_case,
        package=package,
    )
    production_context = copy.deepcopy(package["llm_context_package"])
    forbidden_source_refs = tuple(
        str(value) for value in raw_case.get("forbidden_source_refs") or []
    )
    package["llm_context_package"] = {
        "schema_version": DOMAIN_QUALIFICATION_PACKAGE_SCHEMA_VERSION,
        "case_id": case_id,
        "instruction": _required_text(raw_case, "instruction"),
        "target_domain": target_domain,
        "domain_hypotheses": [
            str(value) for value in raw_case.get("domain_hypotheses") or []
        ],
        "allowed_source_refs": copy.deepcopy(package["candidate_source_refs"]),
        "forbidden_source_refs": list(forbidden_source_refs),
        "production_domain_context": production_context,
        "contains_customer_data": False,
    }
    response_format = candidate_binding_response_format(package)
    schema_hash = candidate_binding_schema_hash(package)
    package["output_schema"]["output_schema_hash"] = schema_hash
    prompt = _domain_qualification_prompt(
        case_id=case_id,
        schema_hash=schema_hash,
    )
    return DomainQualificationCase(
        case_id=case_id,
        family=family,
        package=package,
        expected_selection=expected_selection,
        forbidden_source_refs=forbidden_source_refs,
        response_format=response_format,
        prompt=prompt,
    )


def _build_base_package(raw_case: dict[str, Any]) -> dict[str, Any]:
    case_id = _required_text(raw_case, "case_id")
    rows = raw_case.get("rows")
    selected_row_refs = [
        str(value) for value in raw_case.get("selected_row_refs") or []
    ]
    if not isinstance(rows, list) or not rows or not selected_row_refs:
        raise ValueError("domain_qualification_rows_invalid")
    model_rows: list[dict[str, Any]] = []
    row_provenance: list[dict[str, Any]] = []
    cell_provenance: list[dict[str, Any]] = []
    source_value_index: list[dict[str, Any]] = []
    normalized_cells: list[list[str]] = []
    header_labels: list[str] = []
    all_cell_refs: list[str] = []
    all_value_refs: list[str] = []
    for row_ordinal, raw_row in enumerate(rows, start=1):
        if not isinstance(raw_row, dict):
            raise ValueError("domain_qualification_row_invalid")
        row_ref = _required_text(raw_row, "row_ref")
        raw_cells = raw_row.get("cells")
        if not isinstance(raw_cells, list) or not raw_cells:
            raise ValueError("domain_qualification_cells_invalid")
        cells: list[dict[str, Any]] = []
        values: list[str] = []
        for column_ordinal, raw_cell in enumerate(
            raw_cells,
            start=1,
        ):
            if not isinstance(raw_cell, dict):
                raise ValueError("domain_qualification_cell_invalid")
            label = _required_text(raw_cell, "label")
            value = _required_text(raw_cell, "value")
            source_value_ref = _required_text(
                raw_cell,
                "source_value_ref",
            )
            cell_ref = f"cell_{case_id}_{row_ordinal}_{column_ordinal}"
            header_labels.append(label)
            all_cell_refs.append(cell_ref)
            all_value_refs.append(source_value_ref)
            values.append(value)
            cells.append(
                {
                    "column_ordinal": column_ordinal,
                    "column_ref": f"column_{column_ordinal}",
                    "header_label": label,
                    "cell_ref": cell_ref,
                    "source_value_ref": source_value_ref,
                    "value": value,
                    "value_kind_hints": _value_kind_hints(value),
                }
            )
            cell_provenance.append(
                {
                    "row_ordinal": row_ordinal,
                    "column_ordinal": column_ordinal,
                    "cell_ref": cell_ref,
                    "source_value_ref": source_value_ref,
                }
            )
            source_value_index.append(
                {
                    "source_value_ref": source_value_ref,
                    "row_ref": row_ref,
                    "cell_ref": cell_ref,
                    "value_path": {
                        "kind": "table_cell",
                        "row_index": row_ordinal - 1,
                        "column_index": column_ordinal - 1,
                    },
                    "value_checksum_ref": _value_checksum_ref(value),
                }
            )
        normalized_cells.append(values)
        row_provenance.append(
            {
                "row_ref": row_ref,
                "row_ordinal": row_ordinal,
                "row_role": str(raw_row.get("row_role") or "data_row"),
            }
        )
        model_rows.append(
            {
                "row_ref": row_ref,
                "row_role": str(raw_row.get("row_role") or "data_row"),
                "fact_type_hint": raw_row.get("fact_type_hint"),
                "fact_type_hint_policy": ("synthetic_domain_qualification_v1"),
                "cells": cells,
            }
        )
    if not set(selected_row_refs) <= {str(item["row_ref"]) for item in model_rows}:
        raise ValueError("domain_qualification_selected_row_missing")
    unit_ref = f"unit_domain_qualification_{case_id}"
    return {
        "schema_version": "broker_reports_source_fact_package_v0",
        "package_id": f"base_domain_qualification_{case_id}",
        "package_artifact_ref": (f"synthetic:gate2:domain:base:{case_id}"),
        "extraction_run_id": f"run_domain_qualification_{case_id}",
        "normalization_run_id": ("normalization_domain_qualification_synthetic"),
        "case_id": case_id,
        "document_ref": f"document_domain_qualification_{case_id}",
        "source_bucket_roles": ["primary_source_extraction_refs"],
        "document_context": {"usage_modes": ["source_fact"]},
        "source_unit": {
            "unit_id": unit_ref,
            "unit_kind": "table_row_window",
            "source_input_mode": "normalized_table_projection",
            "private_slice_artifact_ref": (f"art_slice_domain_qualification_{case_id}"),
            "slice_ref": f"slice_domain_qualification_{case_id}",
            "document_ref": f"document_domain_qualification_{case_id}",
            "source_checksum_ref": (f"checksum_domain_qualification_{case_id}"),
            "parser_ref": "parser_domain_qualification_synthetic",
            "table_ref": f"table_domain_qualification_{case_id}",
            "table_projection_id": (f"projection_domain_qualification_{case_id}"),
            "row_range_ref": (f"row_range_domain_qualification_{case_id}"),
            "normalized_header_descriptors": [
                {
                    "column_ordinal": index,
                    "normalized_label": label,
                    "header_ref": f"header_{case_id}_{index}",
                }
                for index, label in enumerate(
                    dict.fromkeys(header_labels),
                    start=1,
                )
            ],
            "row_refs": [str(item["row_ref"]) for item in model_rows],
            "row_provenance": row_provenance,
            "cell_refs": all_cell_refs,
            "cell_provenance": cell_provenance,
            "cell_value_refs": all_value_refs,
            "source_value_refs": all_value_refs,
            "source_value_index": source_value_index,
            "text_segment_refs": [],
            "section_refs": [],
            "page_refs": [],
            "character_span_refs": [],
            "segment_provenance": [],
            "normalized_source_projection": {"cells": normalized_cells},
            "model_source_projection": {
                "schema_version": "gate2_model_table_projection_v0",
                "rows": model_rows,
            },
        },
        "allowed_evidence_refs": [
            *selected_row_refs,
            f"table_domain_qualification_{case_id}",
        ],
        "allowed_source_value_refs": all_value_refs,
        "issue_context": [],
        "allowed_issue_refs": [],
        "forbidden_assumptions": [
            "no_free_form_values",
            "no_cross_row_binding",
        ],
        "coverage_expectation": {
            "coverage_ref": f"coverage_domain_qualification_{case_id}",
            "selected_source_refs": selected_row_refs,
            "ignorable_header_refs": [],
            "ignorable_blank_refs": [],
            "layout_candidate_refs": [],
            "mandatory_no_fact_results": [],
            "fact_candidate_refs": selected_row_refs,
            "required_accounting_total": len(selected_row_refs),
        },
        "privacy_policy": {
            "knowledge_rag_used": False,
            "vectorization_performed": False,
        },
        "created_at": "2026-07-25T00:00:00Z",
    }


def _expected_selection(
    *,
    raw_case: dict[str, Any],
    package: dict[str, Any],
) -> dict[str, Any]:
    expected = raw_case.get("expected")
    if not isinstance(expected, dict):
        raise ValueError("domain_qualification_expected_invalid")
    selected_refs = [str(value) for value in raw_case.get("selected_row_refs") or []]
    if len(selected_refs) != 1:
        raise ValueError("domain_qualification_expected_single_row_required")
    candidates = package["source_value_candidate_set"]["candidates"]
    profile = package["candidate_binding_profile"]
    selected_bindings: list[dict[str, Any]] = []
    selected_candidate_ids: set[str] = set()
    for binding in expected.get("bindings") or []:
        if not isinstance(binding, dict):
            raise ValueError("domain_qualification_expected_binding_invalid")
        role = _required_text(binding, "semantic_role")
        kind = _required_text(binding, "candidate_kind")
        source_value_ref = _required_text(
            binding,
            "source_value_ref",
        )
        matches = [
            item
            for item in candidates
            if item.get("candidate_kind") == kind
            and source_value_ref in (item.get("source_value_refs") or [])
            and role in (item.get("allowed_semantic_roles") or [])
        ]
        if len(matches) != 1:
            raise ValueError(
                "domain_qualification_expected_candidate_not_unique:"
                + str(raw_case.get("case_id"))
                + ":"
                + role
            )
        candidate = matches[0]
        selected_candidate_ids.add(str(candidate["candidate_id"]))
        selected_bindings.append(
            {
                "fact_field_path": profile["roles"][role]["fact_field_path"],
                "candidate_id": candidate["candidate_id"],
                "semantic_role": role,
            }
        )
    relations = package["candidate_relation_set"]["relations"]
    selected_relations: list[str] = []
    for kind in expected.get("relation_kinds") or []:
        matches = [
            item
            for item in relations
            if item.get("relation_kind") == kind
            and selected_candidate_ids >= set(item.get("candidate_ids") or [])
        ]
        if len(matches) != 1:
            raise ValueError(
                "domain_qualification_expected_relation_not_unique:"
                + str(raw_case.get("case_id"))
                + ":"
                + str(kind)
            )
        selected_relations.append(str(matches[0]["relation_id"]))
    ambiguity_refs = sorted(
        {
            str(item["ambiguity_group_ref"])
            for item in candidates
            if item.get("candidate_id") in selected_candidate_ids
            and item.get("ambiguity_group_ref")
        }
    )
    result = {
        "source_ref": selected_refs[0],
        "fact_type": _required_text(expected, "fact_type"),
        "selected_bindings": selected_bindings,
        "selected_relation_ids": selected_relations,
        "subtype_candidate": _required_text(
            expected,
            "subtype_candidate",
        ),
        "confidence": _required_text(expected, "confidence"),
        "completeness": _required_text(expected, "completeness"),
        "uncertainty_codes": [
            str(value) for value in expected.get("uncertainty_codes") or []
        ],
        "resolved_ambiguity_group_refs": ambiguity_refs,
    }
    return {
        "schema_version": "broker_reports_candidate_binding_output_v0",
        "package_id": package["package_id"],
        "candidate_set_id": package["source_value_candidate_set"]["candidate_set_id"],
        "candidate_set_hash": package["source_value_candidate_set"][
            "candidate_set_hash"
        ],
        "relation_set_id": package["candidate_relation_set"]["relation_set_id"],
        "relation_set_hash": package["candidate_relation_set"]["relation_set_hash"],
        "binding_results": [result],
        "no_fact_results": [],
    }


def _domain_qualification_prompt(
    *,
    case_id: str,
    schema_hash: str,
) -> Any:
    content = (
        "You are a bounded candidate-binding secretary for Broker Reports "
        "Gate 2 domain qualification. Follow only the synthetic package. "
        "Evaluate the named target domain among the supplied hypotheses. "
        "Bind only existing candidate IDs and relation IDs, preserve exact "
        "row ownership, account for the allowed source row, never select "
        "forbidden refs, never invent a value, and use explicit "
        "unknown_source_row when instructed. Return only the supplied "
        "strict schema with no prose.\n"
        "{{domain_qualification_package_json}}"
    )
    prompt_hash = hashlib.sha256(
        (
            content
            + "\nprompt:"
            + DOMAIN_QUALIFICATION_PROMPT_VERSION
            + "\ncase:"
            + case_id
            + "\nschema:"
            + schema_hash
        ).encode("utf-8")
    ).hexdigest()
    return SimpleNamespace(
        content=content,
        prompt_ref="code:" + DOMAIN_QUALIFICATION_PROMPT_VERSION,
        hash=prompt_hash,
        output_schema_id=("broker_reports.candidate_binding_output.schema.v0"),
        output_schema_version=DOMAIN_QUALIFICATION_OUTPUT_VERSION,
    )


def domain_qualification_contract_identity(
    *,
    manifest_hash: str,
) -> Gate2EconomyQualificationContractIdentity:
    profile = gate2_provider_profile(PROVIDER_PROFILE_ID)
    validator_hash = hashlib.sha256()
    for relative in (
        Path("broker_reports_gate1") / "gate2_candidate_binding_runtime.py",
        Path("broker_reports_gate1") / "gate2_domain_finalization.py",
        Path("scripts") / "live_gate2_domain_economy_qualification.py",
    ):
        validator_hash.update((SERVICE_ROOT / relative).read_bytes())
    return Gate2EconomyQualificationContractIdentity(
        provider_route_revision=gate2_provider_profile_revision(profile),
        input_contract_version=(
            f"{DOMAIN_QUALIFICATION_MANIFEST_SCHEMA_VERSION}:{manifest_hash}"
        ),
        output_contract_version=DOMAIN_QUALIFICATION_OUTPUT_VERSION,
        prompt_version=DOMAIN_QUALIFICATION_PROMPT_VERSION,
        adapter_projection_revision=(
            f"{profile.adapter_id}:{profile.adapter_version}:"
            f"{gate2_provider_profile_revision(profile)}"
        ),
        canonical_validator_revision=(
            f"{DOMAIN_QUALIFICATION_COMPARATOR_VERSION}:{validator_hash.hexdigest()}"
        ),
    )


def canonicalize_selection(value: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(value)
    binding_results = result.get("binding_results")
    if isinstance(binding_results, list):
        for binding_result in binding_results:
            if not isinstance(binding_result, dict):
                continue
            for field in (
                "selected_bindings",
                "selected_relation_ids",
                "uncertainty_codes",
                "resolved_ambiguity_group_refs",
            ):
                values = binding_result.get(field)
                if not isinstance(values, list):
                    continue
                if field == "selected_bindings":
                    values.sort(
                        key=lambda item: (
                            str(
                                item.get("semantic_role")
                                if isinstance(item, dict)
                                else ""
                            ),
                            str(
                                item.get("candidate_id")
                                if isinstance(item, dict)
                                else ""
                            ),
                        )
                    )
                else:
                    values.sort(key=str)
        binding_results.sort(
            key=lambda item: str(
                item.get("source_ref") if isinstance(item, dict) else ""
            )
        )
    no_fact_results = result.get("no_fact_results")
    if isinstance(no_fact_results, list):
        no_fact_results.sort(
            key=lambda item: (
                str(item.get("source_ref") if isinstance(item, dict) else ""),
                str(item.get("reason_code") if isinstance(item, dict) else ""),
            )
        )
    return result


def _mismatch_paths(expected: Any, actual: Any, path: str = "$") -> set[str]:
    if type(expected) is not type(actual):
        return {path}
    if isinstance(expected, dict):
        paths = {f"{path}.{key}" for key in set(expected) ^ set(actual)}
        for key in set(expected) & set(actual):
            paths.update(
                _mismatch_paths(
                    expected[key],
                    actual[key],
                    f"{path}.{key}",
                )
            )
        return paths
    if isinstance(expected, list):
        paths = set()
        if len(expected) != len(actual):
            paths.add(path + ".length")
        for index, (left, right) in enumerate(zip(expected, actual)):
            paths.update(
                _mismatch_paths(
                    left,
                    right,
                    f"{path}[{index}]",
                )
            )
        return paths
    return set() if expected == actual else {path}


def _value_checksum_ref(value: str) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"valuechk_{hashlib.sha256(encoded).hexdigest()[:24]}"


def _value_kind_hints(value: str) -> list[str]:
    stripped = value.strip().replace(" ", "")
    if stripped.replace(".", "", 1).lstrip("+-").isdigit():
        return ["decimal_like"]
    if len(value) == 3 and value.isupper():
        return ["currency_code_like"]
    if len(value) == 10 and value[4:5] == "-" and value[7:8] == "-":
        return ["iso_date_like"]
    return ["text"]


def _required_text(value: dict[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise ValueError(f"domain_qualification_{key}_invalid")
    return result


def _rate(values) -> float:
    measured = [bool(value) for value in values]
    return sum(1 for value in measured if value) / len(measured) if measured else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
