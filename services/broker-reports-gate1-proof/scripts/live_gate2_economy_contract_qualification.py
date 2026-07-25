#!/usr/bin/env python3
"""Qualify one published economy model on synthetic Gate 2 contracts."""

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

from broker_reports_gate1.gate2_economy_budget import (  # noqa: E402
    Gate2EconomyBudgetSessionFactory,
)
from broker_reports_gate1.gate2_economy_qualification_policy import (  # noqa: E402
    Gate2EconomyQualificationContractIdentity,
    Gate2EconomyQualificationPolicyFactory,
)
from broker_reports_gate1.gate2_economy_workload_qualification import (  # noqa: E402
    CONTRACT_GATE2_FINANCIAL_CHECKSUM,
    CONTRACT_GATE2_FINANCIAL_EVIDENCE,
    Gate2EconomyWorkloadQualificationFactory,
)
from broker_reports_gate1.gate2_financial_context import (  # noqa: E402
    Gate2FinancialContextProjectionFactory,
)
from broker_reports_gate1.gate2_financial_context_checksum import (  # noqa: E402
    Gate2ChecksumExpectedMetric,
    Gate2ChecksumMetricRequest,
    Gate2FinancialContextChecksumComparatorFactory,
    Gate2FinancialContextChecksumContractFactory,
    Gate2FinancialContextChecksumRunnerFactory,
    safe_checksum_receipt,
)
from broker_reports_gate1.gate2_financial_evidence_catalog import (  # noqa: E402
    SUPPORTED_SOURCE_FAMILIES,
)
from broker_reports_gate1.gate2_financial_evidence_decision import (  # noqa: E402
    FinancialEvidenceDecisionPackage,
    FinancialEvidenceValueCandidate,
    Gate2FinancialEvidenceDecisionContract,
    Gate2FinancialEvidenceDecisionContractFactory,
)
from broker_reports_gate1.gate2_financial_evidence_materialization import (  # noqa: E402
    FinancialEvidenceAuthoritativeSourceValue,
    FinancialEvidenceExecutionMetadata,
    FinancialEvidenceSourceLineage,
    Gate2FinancialEvidenceMaterializerFactory,
    Gate2FinancialEvidenceSourcePackageFactory,
    Gate2FinancialEvidenceValidatedDecisionFactory,
)
from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (  # noqa: E402
    Gate2FinancialEvidenceSourcePackage,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_evidence_shadow_qualification import (  # noqa: E402
    Gate2FinancialEvidenceShadowDecisionRunnerFactory,
)
from broker_reports_gate1.gate2_model_clients import (  # noqa: E402
    Gate2StructuredModelClientFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2SourceFactRuntimeError,
    Gate2StructuredModelClientConfig,
    gate2_provider_execution_safe_metadata,
    gate2_provider_profile,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    FINANCIAL_CONTEXT_CHECKSUM_REQUEST_PROFILE,
    FINANCIAL_EVIDENCE_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)
from broker_reports_gate1.gate2_provider_adapters import (  # noqa: E402
    Gate2ProviderAdapterFactory,
)
from live_gate2_synthetic_extraction_smoke import _current_user  # noqa: E402
from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _read_env,
    _signin,
    _url,
)


FACTORY_REQUIRED = (
    "Gate2StructuredModelClientFactory, "
    "Gate2FinancialEvidenceShadowDecisionRunnerFactory and "
    "Gate2FinancialContextChecksumRunnerFactory are the only live model "
    "execution entrypoints"
)
FORBIDDEN = (
    "This qualification harness must not use customer data, direct vendor "
    "calls, output repair, fallback, expensive models or raw provider "
    "output in its safe receipt"
)
QUALIFICATION_SCHEMA_VERSION = "broker_reports_gate2_economy_contract_qualification_v1"
ALLOWED_PROVIDER_PROFILES = {
    "openai_gpt",
    "google_gemini",
    "anthropic_claude",
}
QUALIFICATION_ACTION_ID = "broker_reports_gate2_economy_qualification_action"
QUALIFICATION_ACTION_PATH = (
    SERVICE_ROOT
    / "openwebui_actions"
    / "broker_reports_gate2_economy_qualification_action.py"
)


@dataclass(frozen=True)
class FinancialQualificationCase:
    case_id: str
    expected_disposition: str
    contract: Gate2FinancialEvidenceDecisionContract
    source_package: Gate2FinancialEvidenceSourcePackage


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--model-id", required=True)
    parser.add_argument(
        "--provider-profile-id",
        required=True,
        choices=sorted(ALLOWED_PROVIDER_PROFILES),
    )
    parser.add_argument(
        "--workload",
        choices=("financial", "checksum", "all"),
        default="all",
    )
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()

    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})
    user = _current_user(session, base_url)
    published = _published_model_ids(session, base_url)
    model_published = args.model_id in published
    qualification_action = _live_qualification_action(
        session,
        base_url,
    )
    output: dict[str, Any] = {
        "schema_version": QUALIFICATION_SCHEMA_VERSION,
        "qualification_subject": {
            "exact_model_id": args.model_id,
            "provider_profile_id": args.provider_profile_id,
        },
        "boundary": {
            "synthetic_non_customer_only": True,
            "customer_calls": 0,
            "fallback_calls": 0,
            "repair_attempts": 0,
            "expensive_model_calls": 0,
            "raw_provider_output_included": False,
        },
        "inventory": {
            "exact_model_published": model_published,
            "published_models_total": len(published),
            "qualification_action": qualification_action,
        },
        "workloads": {},
    }
    if not model_published:
        output["status"] = "blocked"
        output["failure_code"] = "stage_models_endpoint_model_absent"
        print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
        return 2

    workload_contracts = []
    if args.workload in {"financial", "all"}:
        workload_contracts.append(
            (
                "gate2_financial_evidence",
                CONTRACT_GATE2_FINANCIAL_EVIDENCE,
            )
        )
    if args.workload in {"checksum", "all"}:
        workload_contracts.append(
            (
                "gate2_financial_checksum",
                CONTRACT_GATE2_FINANCIAL_CHECKSUM,
            )
        )
    output["qualification_authorizations"] = _qualification_authorizations(
        model_id=args.model_id,
        provider_profile_id=args.provider_profile_id,
        workload_contracts=tuple(workload_contracts),
    )
    if args.preflight_only:
        output["status"] = "passed"
        output["preflight_only"] = True
        output["provider_calls"] = 0
        output["estimated_cost_usd_total"] = "0"
        print(
            json.dumps(
                output,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    request_context = _request_context(session, base_url)
    completion = _completion_boundary(
        session=session,
        base_url=base_url,
        timeout=args.timeout,
    )
    common = {
        "model_id": args.model_id,
        "provider_profile_id": args.provider_profile_id,
        "user_id": str(user["id"]),
        "request_context": request_context,
        "completion": completion,
    }
    if args.workload in {"financial", "all"}:
        output["workloads"]["gate2_financial_evidence"] = asyncio.run(
            _qualify_financial(**common)
        )
    if args.workload in {"checksum", "all"}:
        output["workloads"]["gate2_financial_checksum"] = asyncio.run(
            _qualify_checksum(**common)
        )
    statuses = [
        item.get("status")
        for item in output["workloads"].values()
        if isinstance(item, dict)
    ]
    output["status"] = (
        "passed"
        if statuses and all(item == "passed" for item in statuses)
        else "failed"
    )
    output["estimated_cost_usd_total"] = _receipt_cost_total(output["workloads"])
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if output["status"] == "passed" else 1


async def _qualify_financial(
    *,
    model_id: str,
    provider_profile_id: str,
    user_id: str,
    request_context: Any,
    completion,
) -> dict[str, Any]:
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    cases = build_financial_qualification_cases()
    client = _model_client(
        request_profile=FINANCIAL_EVIDENCE_REQUEST_PROFILE,
        provider_profile_id=provider_profile_id,
        user_id=user_id,
        request_context=request_context,
        completion=completion,
    )
    runner = Gate2FinancialEvidenceShadowDecisionRunnerFactory(
        registry=registry,
        model_client=client,
        model_id=model_id,
        provider_profile_id=provider_profile_id,
    ).create()
    results: list[dict[str, Any]] = []
    for case in cases:
        package = runner.model_package(
            case.contract,
            case.source_package,
        )
        try:
            dry_build = _dry_build(
                request_profile=FINANCIAL_EVIDENCE_REQUEST_PROFILE,
                provider_profile_id=provider_profile_id,
                model_id=model_id,
                prompt=runner.prompt,
                package=package,
                response_format=case.contract.openai_response_format(),
            )
            result = await runner.run(
                contract=case.contract,
                source_package=case.source_package,
                execution_ref=f"execution:qualification:{case.case_id}",
                decision_validation_ref=(f"validation:qualification:{case.case_id}"),
            )
            observed = result.artifact["terminal_disposition"]
            passed = (
                observed == case.expected_disposition
                and result.fallback_used is False
                and result.repair_attempt_count == 0
            )
            results.append(
                {
                    "case_id": case.case_id,
                    "status": "passed" if passed else "failed",
                    "expected_disposition": case.expected_disposition,
                    "observed_disposition": observed,
                    "provider_execution": result.provider_execution,
                    "economy_budget_receipt": (result.economy_budget_receipt),
                    "schema_dry_build": dry_build,
                    "canonical_validator_passed": True,
                    "deterministic_materialization_passed": True,
                    "fallback_used": False,
                    "repair_attempt_count": 0,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "case_id": case.case_id,
                    "status": "failed",
                    "expected_disposition": case.expected_disposition,
                    **_safe_error(exc),
                    "canonical_validator_passed": False,
                    "deterministic_materialization_passed": False,
                    "fallback_used": False,
                    "repair_attempt_count": 0,
                }
            )
    passed = sum(item["status"] == "passed" for item in results)
    return {
        "status": "passed" if passed == len(results) else "failed",
        "contract_version": ("broker_reports_gate2_financial_evidence_decision_v1"),
        "cases_total": len(results),
        "cases_passed": passed,
        "four_dispositions_covered": len(results) == 4,
        "cases": results,
    }


async def _qualify_checksum(
    *,
    model_id: str,
    provider_profile_id: str,
    user_id: str,
    request_context: Any,
    completion,
) -> dict[str, Any]:
    contract, expected = build_checksum_qualification_fixture()
    client = _model_client(
        request_profile=FINANCIAL_CONTEXT_CHECKSUM_REQUEST_PROFILE,
        provider_profile_id=provider_profile_id,
        user_id=user_id,
        request_context=request_context,
        completion=completion,
    )
    try:
        runner = Gate2FinancialContextChecksumRunnerFactory(
            model_client=client,
            model_id=model_id,
            provider_profile_id=provider_profile_id,
            qualification_candidate=True,
        ).create()
        dry_build = _dry_build(
            request_profile=FINANCIAL_CONTEXT_CHECKSUM_REQUEST_PROFILE,
            provider_profile_id=provider_profile_id,
            model_id=model_id,
            prompt=runner.prompt,
            package=contract.model_package(),
            response_format=contract.openai_response_format(),
        )
        result = await runner.run(contract=contract)
        private_receipt = Gate2FinancialContextChecksumComparatorFactory().create(
            contract=contract,
            expected_metrics=expected,
            answer_rows=result["rows"],
        )
        receipt = safe_checksum_receipt(private_receipt)
        passed = (
            receipt["status"] == "passed"
            and result["fallback_used"] is False
            and result["repair_attempt_count"] == 0
        )
        return {
            "status": "passed" if passed else "failed",
            "contract_version": ("broker_reports_gate2_financial_context_checksum_v1"),
            "schema_dry_build": dry_build,
            "provider_execution": result["provider_execution"],
            "economy_budget_receipt": result["economy_budget_receipt"],
            "checksum_receipt": receipt,
            "fallback_used": False,
            "repair_attempt_count": 0,
        }
    except Exception as exc:
        return {
            "status": "failed",
            "contract_version": ("broker_reports_gate2_financial_context_checksum_v1"),
            **_safe_error(exc),
            "fallback_used": False,
            "repair_attempt_count": 0,
        }


def build_financial_qualification_cases() -> tuple[FinancialQualificationCase, ...]:
    typed_definitions = (
        (
            "amount",
            "source_decimal",
            "-120.50",
            ("amount",),
        ),
        (
            "printed_label",
            "source_reference",
            "Printed closing total",
            ("printed_label_evidence_ref",),
        ),
        (
            "scope",
            "source_reference",
            "Synthetic statement",
            ("statement_scope",),
        ),
        ("period", "source_period", "2025 Q4", ("period",)),
        ("currency", "source_currency", "RUB", ("currency",)),
        (
            "label",
            "source_text",
            "Synthetic printed financial total",
            ("source_label",),
        ),
    )
    definitions = (
        (
            "typed",
            "typed_input",
            typed_definitions,
            ("printed_financial_metric_v1",),
        ),
        (
            "unclassified",
            "unclassified_financial_input",
            (
                (
                    "label",
                    "source_text",
                    "Synthetic financial value 77.70 with a deliberately "
                    "unknown financial type",
                    ("source_label",),
                ),
            ),
            (),
        ),
        (
            "no_financial",
            "no_financial_input",
            (
                (
                    "label",
                    "source_text",
                    "Section header: account information; no financial "
                    "value is present",
                    ("source_label",),
                ),
            ),
            (),
        ),
        (
            "unsupported",
            "unsupported",
            (
                (
                    "label",
                    "source_text",
                    "Potential financial value exists only in an "
                    "unsupported chart image without reliable rows",
                    ("source_label",),
                ),
            ),
            (),
        ),
    )
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    return tuple(
        _financial_case(
            registry=registry,
            case_id=case_id,
            expected_disposition=expected_disposition,
            definitions=case_definitions,
            allowed_type_ids=allowed_type_ids,
        )
        for (
            case_id,
            expected_disposition,
            case_definitions,
            allowed_type_ids,
        ) in definitions
    )


def build_checksum_qualification_fixture():
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    specifications = (
        ("a", "-120.50", "RUB", "negative"),
        ("b", "0", "USD", "zero"),
        ("c", "9876.54", "EUR", "positive"),
    )
    materialized = tuple(
        _typed_checksum_case(
            registry=registry,
            suffix=suffix,
            literal_value=literal_value,
            currency=currency,
        )
        for suffix, literal_value, currency, _ in specifications
    )
    context = Gate2FinancialContextProjectionFactory(registry=registry).create(
        materialized_artifacts=tuple(item[0] for item in materialized),
        source_packages=tuple(item[1] for item in materialized),
    )
    requests = tuple(
        Gate2ChecksumMetricRequest(
            metric_id=f"metric:{suffix}",
            source_label=f"Synthetic metric {suffix}",
        )
        for suffix, _, _, _ in specifications
    )
    contract = Gate2FinancialContextChecksumContractFactory(registry=registry).create(
        financial_context=context,
        metric_requests=requests,
    )
    entries = {
        item["source_scope_ref"]: item for item in contract.financial_context["entries"]
    }
    expected = tuple(
        Gate2ChecksumExpectedMetric(
            metric_id=f"metric:{suffix}",
            source_label=f"Synthetic metric {suffix}",
            normalized_value=literal_value,
            currency=currency,
            unit="",
            sign=sign,
            period_literals=("2025 Q4", "2025-Q4"),
            context_entry_id=entries[f"scope:{suffix}"]["context_entry_id"],
            source_scope_ref=f"scope:{suffix}",
            source_value_ref=f"value:amount:{suffix}",
            page_ref=f"page:{suffix}",
            semantic_visual_table_derived=True,
            arithmetic_operands=((literal_value,) if suffix == "a" else ()),
        )
        for suffix, literal_value, currency, sign in specifications
    )
    return contract, expected


def _financial_case(
    *,
    registry,
    case_id: str,
    expected_disposition: str,
    definitions,
    allowed_type_ids: tuple[str, ...],
) -> FinancialQualificationCase:
    document_ref = f"document:qualification:{case_id}"
    source_values = tuple(
        FinancialEvidenceAuthoritativeSourceValue(
            source_value_ref=f"value:{name}:{case_id}",
            source_ref=f"source:{name}:{case_id}",
            value_type=value_type,
            literal_value=literal_value,
            source_evidence_refs=(f"evidence:{case_id}",),
            lineage=FinancialEvidenceSourceLineage(
                document_ref=document_ref,
                page_ref=f"page:{case_id}",
                text_segment_ref=f"segment:{case_id}:{index}",
            ),
        )
        for index, (
            name,
            value_type,
            literal_value,
            _,
        ) in enumerate(definitions, start=1)
    )
    source_package = Gate2FinancialEvidenceSourcePackageFactory(
        package_ref=f"package:qualification:{case_id}",
        normalization_run_ref="normalization:qualification:synthetic",
        document_ref=document_ref,
        source_scope_ref=f"scope:qualification:{case_id}",
        source_family_id=SUPPORTED_SOURCE_FAMILIES[0],
        source_values=source_values,
        source_evidence_refs=(f"evidence:{case_id}",),
        completeness="complete",
    ).create()
    candidates = tuple(
        FinancialEvidenceValueCandidate(
            source_value_ref=f"value:{name}:{case_id}",
            source_ref=f"source:{name}:{case_id}",
            value_type=value_type,
            allowed_roles=roles,
        )
        for name, value_type, _, roles in definitions
    )
    contract = Gate2FinancialEvidenceDecisionContractFactory(
        registry=registry,
        package=FinancialEvidenceDecisionPackage(
            source_scope_ref=source_package.source_scope_ref,
            source_family_id=source_package.source_family_id,
            candidates=candidates,
            allowed_type_ids=allowed_type_ids,
        ),
    ).create()
    return FinancialQualificationCase(
        case_id=case_id,
        expected_disposition=expected_disposition,
        contract=contract,
        source_package=source_package,
    )


def _typed_checksum_case(
    *,
    registry,
    suffix: str,
    literal_value: str,
    currency: str,
):
    document_ref = "document:checksum:synthetic"
    definitions = (
        ("amount", "source_decimal", literal_value, ("amount",)),
        (
            "printed_label",
            "source_reference",
            "Printed total",
            ("printed_label_evidence_ref",),
        ),
        (
            "scope",
            "source_reference",
            "Synthetic statement",
            ("statement_scope",),
        ),
        ("period", "source_period", "2025 Q4", ("period",)),
        ("currency", "source_currency", currency, ("currency",)),
        (
            "label",
            "source_text",
            f"Synthetic metric {suffix}",
            ("source_label",),
        ),
    )
    values = tuple(
        FinancialEvidenceAuthoritativeSourceValue(
            source_value_ref=f"value:{name}:{suffix}",
            source_ref=f"source:{name}:{suffix}",
            value_type=value_type,
            literal_value=value,
            source_evidence_refs=(f"evidence:{suffix}",),
            lineage=FinancialEvidenceSourceLineage(
                document_ref=document_ref,
                page_ref=f"page:{suffix}",
                table_ref=f"table:{suffix}",
                row_ref=f"row:{suffix}",
                cell_ref=f"cell:{suffix}:{index}",
            ),
        )
        for index, (
            name,
            value_type,
            value,
            _,
        ) in enumerate(definitions, start=1)
    )
    package = Gate2FinancialEvidenceSourcePackageFactory(
        package_ref=f"package:checksum:{suffix}",
        normalization_run_ref="normalization:checksum:synthetic",
        document_ref=document_ref,
        source_scope_ref=f"scope:{suffix}",
        source_family_id=SUPPORTED_SOURCE_FAMILIES[0],
        source_values=values,
        source_evidence_refs=(f"evidence:{suffix}",),
        completeness="complete",
    ).create()
    candidates = tuple(
        FinancialEvidenceValueCandidate(
            source_value_ref=f"value:{name}:{suffix}",
            source_ref=f"source:{name}:{suffix}",
            value_type=value_type,
            allowed_roles=roles,
        )
        for name, value_type, _, roles in definitions
    )
    contract = Gate2FinancialEvidenceDecisionContractFactory(
        registry=registry,
        package=FinancialEvidenceDecisionPackage(
            source_scope_ref=package.source_scope_ref,
            source_family_id=package.source_family_id,
            candidates=candidates,
            allowed_type_ids=("printed_financial_metric_v1",),
        ),
    ).create()
    decision = {
        "decision": {
            "disposition": "typed_input",
            "input_type_id": "printed_financial_metric_v1",
            "value_bindings": {
                "amount": f"value:amount:{suffix}",
                "printed_label_evidence_ref": (f"value:printed_label:{suffix}"),
                "statement_scope": f"value:scope:{suffix}",
                "as_of_date": None,
                "currency": f"value:currency:{suffix}",
                "period": f"value:period:{suffix}",
                "source_label": f"value:label:{suffix}",
                "unit": None,
            },
            "reason_code": "typed_supported",
        }
    }
    validated = Gate2FinancialEvidenceValidatedDecisionFactory(
        contract=contract
    ).create(decision)
    artifact = (
        Gate2FinancialEvidenceMaterializerFactory(
            registry=registry,
            source_package=package,
            execution_metadata=FinancialEvidenceExecutionMetadata(
                execution_ref=f"execution:checksum:{suffix}",
                decision_validation_ref=f"validation:checksum:{suffix}",
            ),
        )
        .create()
        .materialize(validated_decision=validated)
    )
    return artifact, package


def _model_client(
    *,
    request_profile: str,
    provider_profile_id: str,
    user_id: str,
    request_context: Any,
    completion,
):
    return Gate2StructuredModelClientFactory(
        config=Gate2StructuredModelClientConfig(
            request_profile=request_profile,
            provider_profile_id=provider_profile_id,
            capability_probe=True,
            economy_budget_enforcement=True,
        ),
        user=SimpleNamespace(id=user_id),
        request=request_context,
        completion_resolver=lambda _user_id: (
            completion,
            SimpleNamespace(id=user_id),
        ),
    ).create()


def _dry_build(
    *,
    request_profile: str,
    provider_profile_id: str,
    model_id: str,
    prompt,
    package: dict[str, Any],
    response_format: dict[str, Any],
) -> dict[str, Any]:
    form_data = Gate2OpenWebUIRequestBuilder(request_profile=request_profile).build(
        prompt=prompt,
        package=package,
        model_id=model_id,
        response_format=response_format,
    )
    authorization = (
        Gate2EconomyBudgetSessionFactory()
        .create(request_profile=request_profile)
        .prepare_call(
            form_data=form_data,
            model_id=model_id,
            provider_profile_id=provider_profile_id,
            operation_identity="schema-dry-build",
        )
    )
    profile = gate2_provider_profile(provider_profile_id)
    adapter = Gate2ProviderAdapterFactory(
        profile=profile,
        capability_probe=True,
    ).create()
    adapter.validate_model(authorization.exact_model_id)
    prepared = adapter.prepare_form_data(
        form_data=authorization.prepared_form_data,
        response_format=response_format,
    )
    return {
        "status": "passed",
        "canonical_schema_hash": prepared.canonical_schema_hash,
        "adapted_schema_hash": prepared.adapted_schema_hash,
        "schema_transform_count": prepared.schema_transform_count,
        "estimated_input_tokens": authorization.estimated_input_tokens,
        "maximum_output_tokens": authorization.maximum_output_tokens,
        "estimated_cost_usd": authorization.estimated_cost_usd,
    }


def _request_context(
    session: requests.Session,
    base_url: str,
) -> Any:
    response = session.get(_url(base_url, "/openai/config"), timeout=30)
    response.raise_for_status()
    config = response.json()
    if not isinstance(config, dict):
        raise RuntimeError("openwebui_provider_config_invalid")
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


def _completion_boundary(
    *,
    session: requests.Session,
    base_url: str,
    timeout: int,
):
    def complete(*, form_data, **_kwargs):
        response = session.post(
            _url(base_url, "/api/chat/completions"),
            json=form_data,
            timeout=timeout,
        )
        try:
            payload = response.json()
        except ValueError:
            return {
                "error": {"type": "non_json_provider_response"},
                "status_code": response.status_code,
            }
        if not isinstance(payload, dict):
            return {
                "error": {"type": "non_object_provider_response"},
                "status_code": response.status_code,
            }
        if response.status_code >= 400:
            payload.setdefault("status_code", response.status_code)
        return payload

    return complete


def _published_model_ids(
    session: requests.Session,
    base_url: str,
) -> set[str]:
    response = session.get(_url(base_url, "/api/models"), timeout=30)
    response.raise_for_status()
    payload = response.json()
    items = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise RuntimeError("models_response_invalid")
    return {
        str(item["id"]) for item in items if isinstance(item, dict) and item.get("id")
    }


def _live_qualification_action(
    session: requests.Session,
    base_url: str,
) -> dict[str, Any]:
    response = session.get(
        _url(
            base_url,
            f"/api/v1/functions/id/{QUALIFICATION_ACTION_ID}",
        ),
        timeout=30,
    )
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict):
        raise RuntimeError("qualification_action_response_invalid")
    content = str(value.get("content") or "")
    repository_content = QUALIFICATION_ACTION_PATH.read_text(encoding="utf-8")
    live_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
    repository_sha256 = hashlib.sha256(repository_content.encode("utf-8")).hexdigest()
    policy = Gate2EconomyQualificationPolicyFactory().create()
    meta = value.get("meta") if isinstance(value.get("meta"), dict) else {}
    checks = {
        "content_hash_exact": live_sha256 == repository_sha256,
        "type_action": value.get("type") == "action",
        "active": value.get("is_active") is True,
        "not_global": value.get("is_global") is False,
        "scope_qualification_only": (
            meta.get("qualification_scope") == "qualification_only"
        ),
        "policy_hash_exact": (
            meta.get("qualification_policy_hash") == policy.qualification_policy_hash
        ),
    }
    if not all(checks.values()):
        raise RuntimeError(
            "qualification_action_live_parity_failed:"
            + json.dumps(checks, sort_keys=True)
        )
    return {
        "action_id": QUALIFICATION_ACTION_ID,
        "content_sha256": live_sha256,
        "qualification_policy_hash": (policy.qualification_policy_hash),
        "checks": checks,
    }


def _qualification_authorizations(
    *,
    model_id: str,
    provider_profile_id: str,
    workload_contracts: tuple[tuple[str, str], ...],
) -> list[dict[str, object]]:
    registry = Gate2EconomyWorkloadQualificationFactory().create()
    policy = Gate2EconomyQualificationPolicyFactory().create()
    receipts = []
    for workload_class, contract_version in workload_contracts:
        evidence = registry.status(
            exact_model_id=model_id,
            provider_profile_id=provider_profile_id,
            workload_class=workload_class,
            contract_version=contract_version,
        )
        authorization = policy.authorize(
            workload_class=workload_class,
            exact_model_id=model_id,
            provider_profile_id=provider_profile_id,
            receipt_identity=(
                Gate2EconomyQualificationContractIdentity(
                    provider_route_revision=(evidence.provider_route_revision),
                    input_contract_version=(evidence.input_contract_version),
                    output_contract_version=(evidence.output_contract_version),
                    prompt_version=evidence.prompt_version,
                    adapter_projection_revision=(evidence.adapter_projection_revision),
                    canonical_validator_revision=(
                        evidence.canonical_validator_revision
                    ),
                )
            ),
        )
        receipts.append(authorization.safe_receipt())
    return receipts


def _safe_error(exc: Exception) -> dict[str, Any]:
    code = str(getattr(exc, "code", None) or exc.__class__.__name__)
    result: dict[str, Any] = {
        "failure_code": code,
        "failure_class": str(
            getattr(exc, "failure_class", None) or exc.__class__.__name__
        ),
    }
    execution = getattr(exc, "execution_metadata", None)
    if execution is not None:
        result["provider_execution"] = gate2_provider_execution_safe_metadata(execution)
    rich_execution = getattr(exc, "provider_execution", None)
    if isinstance(rich_execution, dict):
        result["provider_execution"] = copy.deepcopy(rich_execution)
    budget = getattr(exc, "economy_budget_receipt", None)
    if isinstance(budget, dict):
        result["economy_budget_receipt"] = copy.deepcopy(budget)
    if isinstance(exc, Gate2SourceFactRuntimeError):
        raw = exc.raw_output
        if isinstance(raw, dict) and isinstance(
            raw.get("economy_budget_receipt"),
            dict,
        ):
            result["economy_budget_receipt"] = copy.deepcopy(
                raw["economy_budget_receipt"]
            )
    return result


def _receipt_cost_total(workloads: dict[str, Any]) -> str:
    costs: list[Decimal] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if value.get(
                "schema_version"
            ) == "broker_reports_gate2_economy_budget_v1" and isinstance(
                value.get("actual_cost_usd"), str
            ):
                costs.append(Decimal(value["actual_cost_usd"]))
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    visit(workloads)
    return format(sum(costs, Decimal("0")), "f")


if __name__ == "__main__":
    raise SystemExit(main())
