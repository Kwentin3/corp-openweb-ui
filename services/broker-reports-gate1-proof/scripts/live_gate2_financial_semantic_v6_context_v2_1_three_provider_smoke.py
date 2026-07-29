#!/usr/bin/env python3
"""Preflight, execute or resume the frozen Context V2.1 GOAL 12 smoke."""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import hmac
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
REPORT_DIR = REPO_ROOT / "docs" / "reports" / "2026-07-29"
PRECALL_SAFE_PATH = (
    REPORT_DIR
    / "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12.precall.plan.safe.json"
)
PRECALL_TRANSPARENT_PATH = (
    REPORT_DIR
    / "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12.precall.transparent.json"
)
TRANSPARENT_REPORT_PATH = (
    REPORT_DIR
    / "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12.transparent.json"
)
SAFE_RECEIPT_PATH = (
    REPORT_DIR
    / "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12.receipt.safe.json"
)
MARKDOWN_REPORT_PATH = (
    REPORT_DIR
    / "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12.report.md"
)
PLAN_BUILD_SCRIPT = (
    SCRIPT_DIR / "build_context_v2_1_budget_smoke_plan.py"
)
TIMEOUT_SECONDS = 240

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (  # noqa: E402
    sha256_json,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_context_v2_1_budget_smoke import (  # noqa: E402,E501
    BUDGET_SMOKE_CONTINUATION_KEY,
    BUDGET_SMOKE_SNAPSHOT_AUTHORITY_KEY,
    Gate2FinancialSemanticV6ContextV21BudgetSmokeCoordinator,
    build_financial_semantic_v6_context_v2_1_budget_smoke_plan,
)
from broker_reports_gate1.gate2_financial_semantic_v6_context_v2_1_budget_smoke_plan import (  # noqa: E402,E501
    financial_semantic_v6_context_v2_1_budget_smoke_operation_identity,
)
from broker_reports_gate1.gate2_financial_semantic_v6_evidence import (  # noqa: E402,E501
    V6_CONTEXT_V2_1_BUDGET_SMOKE_FAILURE_PRIVATE_EVIDENCE_SCHEMA_VERSION,
    V6_CONTEXT_V2_1_BUDGET_SMOKE_PRIVATE_EVIDENCE_SCHEMA_VERSION,
    Gate2FinancialSemanticV6ContextV21BudgetSmokeEvidenceBundle,
    Gate2FinancialSemanticV6ContextV21BudgetSmokeFailureEvidenceBundle,
    restore_financial_semantic_v6_context_v2_1_budget_smoke_private_evidence,
    validate_financial_semantic_v6_context_v2_1_budget_smoke_evidence_bundle,
)
from broker_reports_gate1.gate2_financial_semantic_v6_qualification import (  # noqa: E402,E501
    Gate2FinancialSemanticV6QualificationFixtureFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_smoke_report import (  # noqa: E402,E501
    Gate2FinancialSemanticV6TransparentSmokeReportFactory,
)
from broker_reports_gate1.gate2_model_clients import (  # noqa: E402
    Gate2StructuredModelClientFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2StructuredModelClientConfig,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE,
)
from live_gate2_economy_contract_qualification import (  # noqa: E402
    _published_model_ids,
    _request_context,
)
from live_gate2_synthetic_extraction_smoke import (  # noqa: E402
    _current_user,
)
from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _read_env,
    _signin,
)


STATE_SCHEMA_VERSION = (
    "broker_reports_gate2_context_v2_1_budget_smoke_private_state_v1"
)
SAFE_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate2_context_v2_1_budget_smoke_safe_receipt_v1"
)
EXECUTION_LOCK_SCHEMA_VERSION = (
    "broker_reports_gate2_context_v2_1_budget_smoke_execution_lock_v1"
)
REMOTE_EXECUTION_LOCK_SCHEMA_VERSION = (
    "broker_reports_gate2_context_v2_1_budget_smoke_remote_execution_lock_v1"
)
SLOT_SUBMISSION_CLAIM_SCHEMA_VERSION = (
    "broker_reports_gate2_context_v2_1_budget_smoke_slot_claim_v1"
)
REMOTE_EXECUTION_LOCK_TAG_PREFIX = (
    "broker-reports-goal12-execution-lock-"
)
BROKER_REPORTS_ACTIONS_WORKFLOW_NAME = "Broker Reports CI"
BROKER_REPORTS_ACTIONS_JOB_NAME = "broker-reports-ci"
BROKER_REPORTS_ACTIONS_WORKFLOW_PATH = (
    ".github/workflows/broker-reports-ci.yml"
)
_ACTIONS_DETAILS_URL_RE = re.compile(
    r"^https://github\.com/[^/]+/[^/]+/actions/runs/([1-9][0-9]*)"
    r"/job/[1-9][0-9]*$"
)
FACTORY_REQUIRED = (
    "This CLI delegates all request, provider, semantic, evidence and report "
    "work to the existing GOAL 12 factories"
)
FORBIDDEN = (
    "The CLI must not accept model/parameter overrides, retry, repair, fall "
    "back, store private evidence in Git, repeat a consumed slot, bypass the "
    "real Actions prerequisite or admit production"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--resume", action="store_true")
    parser.add_argument("--private-state-dir")
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    args = parser.parse_args()

    if args.preflight_only:
        if args.private_state_dir is not None:
            parser.error("--preflight-only does not accept a state directory")
    elif not args.private_state_dir:
        parser.error("--execute/--resume require --private-state-dir")

    registry, fixture, audit_manifest, plan = _authorities()
    _require_precall_artifacts(plan.integrity_hash)
    if args.preflight_only:
        output = _preflight_summary(plan=plan)
        print(_pretty_json(output))
        return 0

    private_dir = _validated_private_state_dir(
        Path(args.private_state_dir)
    )
    if args.execute:
        _require_result_artifacts_absent()
    head = _clean_repository_head(
        allowed_untracked_paths=(
            (
                TRANSPARENT_REPORT_PATH,
                SAFE_RECEIPT_PATH,
                MARKDOWN_REPORT_PATH,
            )
            if args.resume
            else ()
        )
    )
    _require_green_actions(head)
    env = _read_env(Path(args.env_file))
    base_url = (
        args.base_url.rstrip("/")
        if args.base_url
        else _base_url(env)
    )
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})
    user = _current_user(session, base_url)
    published_model_ids = _published_model_ids(session, base_url)
    request_context = _request_context(session, base_url)
    if args.execute:
        if private_dir.exists():
            raise RuntimeError("goal12_private_state_already_exists")
        execution_claim_id = secrets.token_hex(32)
        _claim_execution_lock(
            path=_execution_lock_path(plan.integrity_hash),
            plan_hash=plan.integrity_hash,
            head=head,
            private_dir=private_dir,
            execution_claim_id=execution_claim_id,
        )
        state_authority_key = _state_authority_key(
            execution_claim_id=execution_claim_id,
            plan_hash=plan.integrity_hash,
            head=head,
        )
        state = _create_private_state(
            private_dir=private_dir,
            plan=plan,
            head=head,
            base_url=base_url,
            published_model_ids=published_model_ids,
            state_authority_key=state_authority_key,
        )
        _claim_remote_execution_lock(
            plan_hash=plan.integrity_hash,
            head=head,
            private_dir=private_dir,
            execution_claim_id=execution_claim_id,
        )
    else:
        execution_claim_id = _require_execution_lock(
            path=_execution_lock_path(plan.integrity_hash),
            plan_hash=plan.integrity_hash,
            head=head,
            private_dir=private_dir,
        )
        state_authority_key = _state_authority_key(
            execution_claim_id=execution_claim_id,
            plan_hash=plan.integrity_hash,
            head=head,
        )
        if not private_dir.exists() or (
            private_dir.is_dir() and not any(private_dir.iterdir())
        ):
            state = _create_private_state(
                private_dir=private_dir,
                plan=plan,
                head=head,
                base_url=base_url,
                published_model_ids=published_model_ids,
                state_authority_key=state_authority_key,
                allow_empty_existing=True,
            )
        else:
            state = _restore_private_state(
                private_dir=private_dir,
                plan=plan,
                head=head,
                base_url=base_url,
                state_authority_key=state_authority_key,
            )
        _resume_remote_execution_lock(
            plan_hash=plan.integrity_hash,
            head=head,
            private_dir=private_dir,
            execution_claim_id=execution_claim_id,
        )

    clients = _clients(
        plan=plan,
        published_model_ids=published_model_ids,
        user_id=str(user["id"]),
        request_context=request_context,
    )
    state_path = private_dir / "state.private.json"
    cases_dir = private_dir / "cases"
    submission_claims_dir = private_dir / "submission-claims"
    cases_dir.mkdir(parents=True, exist_ok=True)
    submission_claims_dir.mkdir(parents=True, exist_ok=True)
    slot_by_id = {item.slot_id: item for item in plan.slots}

    def consume_slot(slot, operation_identity: str) -> None:
        entry = state["slots"][slot.slot_id]
        if entry["status"] != "pending":
            raise RuntimeError("goal12_slot_not_pending")
        _claim_slot_submission(
            path=(
                submission_claims_dir
                / _slot_submission_claim_filename(slot)
            ),
            plan_hash=plan.integrity_hash,
            head=head,
            slot=slot,
            operation_identity=operation_identity,
            execution_claim_id=execution_claim_id,
        )
        entry["status"] = "consumed_pending_response"
        entry["operation_identity_sha256"] = _sha256_text(
            operation_identity
        )
        entry["provider_submission_budget_consumed"] = True
        _write_private_state(
            state_path,
            state,
            state_authority_key=state_authority_key,
        )

    def private_checkpoint(
        slot_id: str,
        payload: dict[str, Any],
    ) -> None:
        path = cases_dir / _case_filename(slot_by_id[slot_id])
        _write_json_atomically(
            path,
            payload,
            require_absent=True,
            sort_keys=False,
        )

    def safe_checkpoint(
        slot_id: str,
        payload: dict[str, Any],
    ) -> None:
        entry = state["slots"][slot_id]
        if entry["status"] not in {
            "pending",
            "consumed_pending_response",
        }:
            raise RuntimeError("goal12_slot_checkpoint_state_invalid")
        entry["status"] = "completed"
        entry["safe_summary"] = copy.deepcopy(payload)
        _write_private_state(
            state_path,
            state,
            state_authority_key=state_authority_key,
        )

    coordinator = (
        Gate2FinancialSemanticV6ContextV21BudgetSmokeCoordinator(
            plan=plan,
            fixture=fixture,
            outcome_audit_manifest=audit_manifest,
            registry=registry,
            clients=clients,
            consume_slot=consume_slot,
            private_checkpoint=private_checkpoint,
            safe_checkpoint=safe_checkpoint,
        )
    )

    if args.resume:
        _recover_slot_submission_claims(
            state=state,
            state_path=state_path,
            submission_claims_dir=submission_claims_dir,
            plan=plan,
            head=head,
            execution_claim_id=execution_claim_id,
            state_authority_key=state_authority_key,
        )
        _recover_private_checkpoints(
            state=state,
            state_path=state_path,
            cases_dir=cases_dir,
            plan=plan,
            state_authority_key=state_authority_key,
        )

    for slot in plan.slots:
        entry = state["slots"][slot.slot_id]
        if entry["status"] == "completed":
            continue
        if entry["status"] == "consumed_pending_response":
            asyncio.run(
                _record_consumed_failure(
                    coordinator=coordinator,
                    slot=slot,
                )
            )
            continue
        if entry["status"] != "pending":
            raise RuntimeError("goal12_private_state_slot_invalid")
        if slot.exact_model_id not in published_model_ids:
            coordinator.record_preflight_failure(
                slot=slot,
                failure_code="stage_models_endpoint_model_absent",
                failure_class="provider_configuration",
                raw_output={
                    "exact_model_published": False,
                    "published_models_total": len(
                        published_model_ids
                    ),
                },
            )
            continue
        asyncio.run(coordinator.execute_slot(slot=slot))

    report = _build_transparent_report(
        state=state,
        cases_dir=cases_dir,
        plan=plan,
    )
    safe_receipt = _safe_receipt(
        plan=plan,
        report=report,
        head=head,
    )
    markdown = _markdown_report(
        report=report,
        safe_receipt=safe_receipt,
    )
    _write_or_validate_text(
        TRANSPARENT_REPORT_PATH,
        _pretty_json(report) + "\n",
    )
    _write_or_validate_text(
        SAFE_RECEIPT_PATH,
        _pretty_json(safe_receipt) + "\n",
    )
    _write_or_validate_text(
        MARKDOWN_REPORT_PATH,
        markdown,
    )
    state["status"] = "completed"
    state["transparent_report_sha256"] = sha256_json(report)
    state["safe_receipt_hash"] = safe_receipt["receipt_hash"]
    _write_private_state(
        state_path,
        state,
        state_authority_key=state_authority_key,
    )
    print(_pretty_json(safe_receipt))
    return 0


async def _record_consumed_failure(
    *,
    coordinator: (
        Gate2FinancialSemanticV6ContextV21BudgetSmokeCoordinator
    ),
    slot: Any,
) -> None:
    coordinator.record_consumed_slot_failure(slot=slot)


def _authorities():
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    historical = _read_json(
        SERVICE_ROOT
        / "benchmarks"
        / "gate2_financial_semantic_v6"
        / "manifest.json"
    )
    base = _read_json(
        SERVICE_ROOT
        / "benchmarks"
        / "gate2_financial_successor_v2"
        / "manifest.json"
    )
    audit = _read_json(
        SERVICE_ROOT
        / "benchmarks"
        / "gate2_financial_semantic_v6_outcome_audit_v1"
        / "manifest.json"
    )
    fixture = Gate2FinancialSemanticV6QualificationFixtureFactory(
        registry=registry,
        snapshot_authority_key=BUDGET_SMOKE_SNAPSHOT_AUTHORITY_KEY,
        continuation_key=BUDGET_SMOKE_CONTINUATION_KEY,
    ).create(
        manifest=historical,
        base_manifest=base,
    )
    plan = build_financial_semantic_v6_context_v2_1_budget_smoke_plan(
        fixture=fixture,
        outcome_audit_manifest=audit,
        registry=registry,
    )
    return registry, fixture, audit, plan


def _preflight_summary(*, plan: Any) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "status": "preflight_passed_not_executed",
        "plan_integrity_hash": plan.integrity_hash,
        "frozen_slots_total": len(plan.slots),
        "maximum_provider_submissions_total": 12,
        "immutable_model_ids_proven_total": sum(
            item.immutable_model_id_proven for item in plan.slots[::4]
        ),
        "unproven_provider_profiles": sorted(
            {
                item.provider_profile_id
                for item in plan.slots
                if not item.immutable_model_id_proven
            }
        ),
        "execution_accounting": {
            "provider_submissions_total": 0,
            "provider_responses_total": 0,
            "retry_total": 0,
            "repair_total": 0,
            "fallback_total": 0,
        },
        "active": False,
        "production_admissions": [],
    }


def _clients(
    *,
    plan: Any,
    published_model_ids: set[str],
    user_id: str,
    request_context: Any,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for slot in plan.slots[::4]:
        if (
            not slot.immutable_model_id_proven
            or slot.exact_model_id not in published_model_ids
        ):
            continue
        result[slot.provider_profile_id] = (
            Gate2StructuredModelClientFactory(
                config=Gate2StructuredModelClientConfig(
                    request_profile=(
                        FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE
                    ),
                    provider_profile_id=slot.provider_profile_id,
                    capability_probe=True,
                    economy_budget_enforcement=True,
                ),
                user=SimpleNamespace(id=user_id),
                request=request_context,
            ).create()
        )
    return result


def _create_private_state(
    *,
    private_dir: Path,
    plan: Any,
    head: str,
    base_url: str,
    published_model_ids: set[str],
    state_authority_key: bytes,
    allow_empty_existing: bool = False,
) -> dict[str, Any]:
    if private_dir.exists():
        if (
            not allow_empty_existing
            or not private_dir.is_dir()
            or any(private_dir.iterdir())
        ):
            raise RuntimeError("goal12_private_state_already_exists")
    else:
        private_dir.mkdir(parents=True, exist_ok=False)
    state = {
        "schema_version": STATE_SCHEMA_VERSION,
        "status": "in_progress",
        "plan_integrity_hash": plan.integrity_hash,
        "repository_head": head,
        "base_url_sha256": _sha256_text(base_url),
        "published_model_ids_sha256": sha256_json(
            sorted(published_model_ids)
        ),
        "slots": {
            slot.slot_id: {
                "ordinal": slot.ordinal,
                "slot_integrity_hash": slot.integrity_hash,
                "provider_profile_id": slot.provider_profile_id,
                "exact_model_id": slot.exact_model_id,
                "status": "pending",
                "operation_identity_sha256": None,
                "provider_submission_budget_consumed": False,
                "safe_summary": None,
            }
            for slot in plan.slots
        },
        "transparent_report_sha256": None,
        "safe_receipt_hash": None,
    }
    _write_private_state(
        private_dir / "state.private.json",
        state,
        state_authority_key=state_authority_key,
        require_absent=True,
    )
    return state


def _restore_private_state(
    *,
    private_dir: Path,
    plan: Any,
    head: str,
    base_url: str,
    state_authority_key: bytes,
) -> dict[str, Any]:
    state_path = private_dir / "state.private.json"
    if not private_dir.is_dir() or not state_path.is_file():
        raise RuntimeError("goal12_private_state_missing")
    state = _read_json(state_path)
    _validate_private_state_integrity(
        state,
        state_authority_key=state_authority_key,
    )
    expected_slot_ids = {item.slot_id for item in plan.slots}
    if (
        state.get("schema_version") != STATE_SCHEMA_VERSION
        or state.get("status") != "in_progress"
        or state.get("plan_integrity_hash") != plan.integrity_hash
        or state.get("repository_head") != head
        or state.get("base_url_sha256") != _sha256_text(base_url)
        or not isinstance(state.get("slots"), dict)
        or set(state["slots"]) != expected_slot_ids
    ):
        raise RuntimeError("goal12_private_state_invalid")
    for slot in plan.slots:
        entry = state["slots"][slot.slot_id]
        if (
            not isinstance(entry, dict)
            or entry.get("ordinal") != slot.ordinal
            or entry.get("slot_integrity_hash") != slot.integrity_hash
            or entry.get("provider_profile_id")
            != slot.provider_profile_id
            or entry.get("exact_model_id") != slot.exact_model_id
            or entry.get("status")
            not in {"pending", "consumed_pending_response", "completed"}
            or (
                entry.get("status") == "pending"
                and (
                    entry.get("provider_submission_budget_consumed") is not False
                    or entry.get("operation_identity_sha256") is not None
                    or entry.get("safe_summary") is not None
                )
            )
            or (
                entry.get("status") == "consumed_pending_response"
                and (
                    entry.get("provider_submission_budget_consumed") is not True
                    or not _is_sha256(
                        entry.get("operation_identity_sha256")
                    )
                    or entry.get("safe_summary") is not None
                )
            )
            or (
                entry.get("status") == "completed"
                and (
                    not isinstance(entry.get("safe_summary"), dict)
                    or entry.get("provider_submission_budget_consumed")
                    not in {False, True}
                    or (
                        entry.get("provider_submission_budget_consumed")
                        is True
                        and not _is_sha256(
                            entry.get("operation_identity_sha256")
                        )
                    )
                    or (
                        entry.get("provider_submission_budget_consumed")
                        is False
                        and entry.get("operation_identity_sha256")
                        is not None
                    )
                )
            )
        ):
            raise RuntimeError("goal12_private_state_invalid")
    return state


def _recover_private_checkpoints(
    *,
    state: dict[str, Any],
    state_path: Path,
    cases_dir: Path,
    plan: Any,
    state_authority_key: bytes,
) -> None:
    changed = False
    for slot in plan.slots:
        entry = state["slots"][slot.slot_id]
        private_path = cases_dir / _case_filename(slot)
        if entry["status"] == "completed":
            if not private_path.is_file():
                raise RuntimeError(
                    "goal12_completed_private_checkpoint_missing"
                )
            _load_private_bundle(
                path=private_path,
                plan=plan,
                slot=slot,
            )
        elif (
            entry["status"] == "consumed_pending_response"
            and private_path.is_file()
        ):
            bundle = _load_private_bundle(
                path=private_path,
                plan=plan,
                slot=slot,
            )
            entry["status"] = "completed"
            entry["safe_summary"] = {
                "private_evidence_hash": (
                    bundle.private_evidence["private_evidence_hash"]
                ),
                "safe_receipt": copy.deepcopy(bundle.safe_receipt),
            }
            changed = True
        elif (
            entry["status"] == "pending"
            and private_path.is_file()
        ):
            bundle = _load_private_bundle(
                path=private_path,
                plan=plan,
                slot=slot,
            )
            lifecycle = bundle.private_evidence.get("execution_accounting")
            if (
                not isinstance(lifecycle, dict)
                or lifecycle.get("local_invocations_total") != 0
                or lifecycle.get("provider_submissions_total") != 0
                or lifecycle.get("provider_responses_total") != 0
                or entry["provider_submission_budget_consumed"] is not False
                or entry["operation_identity_sha256"] is not None
            ):
                raise RuntimeError(
                    "goal12_unconsumed_private_checkpoint_present"
                )
            entry["status"] = "completed"
            entry["safe_summary"] = {
                "private_evidence_hash": (
                    bundle.private_evidence["private_evidence_hash"]
                ),
                "safe_receipt": copy.deepcopy(bundle.safe_receipt),
            }
            changed = True
        elif entry["status"] == "pending" and private_path.exists():
            raise RuntimeError(
                "goal12_unconsumed_private_checkpoint_present"
            )
    if changed:
        _write_private_state(
            state_path,
            state,
            state_authority_key=state_authority_key,
        )


def _build_transparent_report(
    *,
    state: dict[str, Any],
    cases_dir: Path,
    plan: Any,
) -> dict[str, Any]:
    if any(
        state["slots"][slot.slot_id]["status"] != "completed"
        for slot in plan.slots
    ):
        raise RuntimeError("goal12_execution_not_terminal")
    factory = Gate2FinancialSemanticV6TransparentSmokeReportFactory()
    cases = []
    for slot in plan.slots:
        bundle = _load_private_bundle(
            path=cases_dir / _case_filename(slot),
            plan=plan,
            slot=slot,
        )
        cases.append(
            factory.create_context_v2_1_budget_smoke_case(
                plan=plan,
                plan_slot=slot,
                evidence_bundle=bundle,
            )
        )
    return factory.create_context_v2_1_budget_smoke_report(
        plan=plan,
        case_evidence=cases,
    )


def _load_private_bundle(*, path: Path, plan: Any, slot: Any):
    payload = _read_json(path)
    if set(payload) != {
        "private_evidence",
        "safe_receipt",
        "materialized_artifact",
    }:
        raise RuntimeError("goal12_private_checkpoint_invalid")
    serialized = json.dumps(
        payload["private_evidence"],
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    private_evidence = (
        restore_financial_semantic_v6_context_v2_1_budget_smoke_private_evidence(
            serialized=serialized
        )
    )
    schema_version = private_evidence["schema_version"]
    if (
        schema_version
        == V6_CONTEXT_V2_1_BUDGET_SMOKE_PRIVATE_EVIDENCE_SCHEMA_VERSION
    ):
        if not isinstance(payload["materialized_artifact"], dict):
            raise RuntimeError("goal12_private_checkpoint_invalid")
        bundle = (
            Gate2FinancialSemanticV6ContextV21BudgetSmokeEvidenceBundle(
                private_evidence=private_evidence,
                safe_receipt=copy.deepcopy(payload["safe_receipt"]),
                materialized_artifact=copy.deepcopy(
                    payload["materialized_artifact"]
                ),
            )
        )
    elif (
        schema_version
        == V6_CONTEXT_V2_1_BUDGET_SMOKE_FAILURE_PRIVATE_EVIDENCE_SCHEMA_VERSION
    ):
        if payload["materialized_artifact"] is not None:
            raise RuntimeError("goal12_private_checkpoint_invalid")
        bundle = (
            Gate2FinancialSemanticV6ContextV21BudgetSmokeFailureEvidenceBundle(
                private_evidence=private_evidence,
                safe_receipt=copy.deepcopy(payload["safe_receipt"]),
            )
        )
    else:
        raise RuntimeError("goal12_private_checkpoint_invalid")
    validate_financial_semantic_v6_context_v2_1_budget_smoke_evidence_bundle(
        evidence_bundle=bundle,
        plan=plan,
        plan_slot=slot,
    )
    return bundle


def _safe_receipt(
    *,
    plan: Any,
    report: dict[str, Any],
    head: str,
) -> dict[str, Any]:
    provider_verdicts = [
        {
            "provider_profile_id": item["provider_profile_id"],
            "exact_model_id": item["exact_model_id"],
            "technical_smoke_verdict": item[
                "technical_smoke_verdict"
            ],
            "semantic_smoke_verdict": item[
                "semantic_smoke_verdict"
            ],
            "benchmark_admission_eligible": item["admission_eligible"],
            "error_category_counts": copy.deepcopy(
                item["error_category_counts"]
            ),
        }
        for item in report["provider_verdicts"]
    ]
    draft = {
        "schema_version": SAFE_RECEIPT_SCHEMA_VERSION,
        "status": "completed",
        "repository_head": head,
        "plan_integrity_hash": plan.integrity_hash,
        "transparent_report_hash": sha256_json(report),
        "provider_verdicts": provider_verdicts,
        "execution_accounting": copy.deepcopy(
            report["execution_accounting"]
        ),
        "private_evidence_hashes": [
            item["evidence_hashes"]["private_evidence_hash"]
            for item in report["cases"]
        ],
        "raw_provider_output_included": False,
        "active": False,
        "production_admissions": [],
    }
    return {**draft, "receipt_hash": sha256_json(draft)}


def _markdown_report(
    *,
    report: dict[str, Any],
    safe_receipt: dict[str, Any],
) -> str:
    lines = [
        "# Broker Reports Gate 2 — Context V2.1 GOAL 12 budget smoke",
        "",
        f"- Status: `{report['status']}`",
        f"- Plan: `{report['plan_integrity_hash']}`",
        (
            "- Provider submissions: "
            f"`{report['execution_accounting']['provider_submissions_total']}` "
            "of maximum `12`"
        ),
        "- Retry / repair / fallback: `0 / 0 / 0`",
        "- Context V2.1 active: `false`",
        "- Production admissions: `[]`",
        "",
        "## Provider verdicts",
        "",
        "| Provider | Exact model/selector | Technical | Semantic | Benchmark admission |",
        "|---|---|---|---|---|",
    ]
    for item in report["provider_verdicts"]:
        lines.append(
            "| "
            f"{item['provider_profile_id']} | "
            f"`{item['exact_model_id']}` | "
            f"`{item['technical_smoke_verdict']}` | "
            f"`{item['semantic_smoke_verdict']}` | "
            f"`{str(item['admission_eligible']).lower()}` |"
        )
    lines.extend(
        [
            "",
            "## Evidence",
            "",
            (
                "The adjacent transparent JSON contains every exact synthetic "
                "final request, system message, user content, provider-visible "
                "schema, adapter-extracted output, normalized answer, audited "
                "expected answer, field-level diff, tokens, cost and latency."
            ),
            (
                "Raw provider envelopes and response identifiers are retained "
                "only in hash-linked private evidence outside Git."
            ),
            (
                "Google remained uncalled because the published "
                "`models/gemini-3.1-flash-lite` value is a stable selector, "
                "not a proven dated immutable model ID."
            ),
            "",
            f"Safe receipt: `{safe_receipt['receipt_hash']}`.",
            "",
        ]
    )
    return "\n".join(lines)


def _require_precall_artifacts(plan_hash: str) -> None:
    completed = subprocess.run(
        [sys.executable, str(PLAN_BUILD_SCRIPT), "--check"],
        cwd=SERVICE_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError("goal12_precall_artifact_check_failed")
    safe = _read_json(PRECALL_SAFE_PATH)
    transparent = _read_json(PRECALL_TRANSPARENT_PATH)
    if (
        safe.get("integrity_hash") != plan_hash
        and safe.get("plan_integrity_hash") != plan_hash
    ):
        raise RuntimeError("goal12_precall_plan_hash_mismatch")
    if transparent.get("plan_integrity_hash") != plan_hash:
        raise RuntimeError("goal12_precall_plan_hash_mismatch")


def _clean_repository_head(
    *,
    allowed_untracked_paths: tuple[Path, ...] = (),
) -> str:
    status = subprocess.run(
        [
            "git",
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
    allowed = {
        path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
        for path in allowed_untracked_paths
    }
    entries = [entry for entry in status.split("\0") if entry]
    if any(
        len(entry) < 4
        or entry[:3] != "?? "
        or entry[3:].replace("\\", "/") not in allowed
        for entry in entries
    ):
        raise RuntimeError("goal12_repository_not_clean")
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _require_green_actions(head: str) -> None:
    pr = _gh_json(
        [
            "gh",
            "pr",
            "view",
            "--json",
            "headRefOid,state,isDraft,number,url",
        ],
        error_code="goal12_github_pr_unavailable",
    )
    if (
        pr.get("headRefOid") != head
        or pr.get("state") != "OPEN"
        or pr.get("isDraft") is not False
        or isinstance(pr.get("number"), bool)
        or not isinstance(pr.get("number"), int)
        or pr["number"] < 1
        or not isinstance(pr.get("url"), str)
        or not pr["url"].startswith("https://github.com/")
    ):
        raise RuntimeError("goal12_actions_not_green_for_head")

    check_payload = _gh_json(
        [
            "gh",
            "api",
            "-H",
            "Accept: application/vnd.github+json",
            (
                "repos/{owner}/{repo}/commits/"
                f"{head}/check-runs?filter=latest&per_page=100"
            ),
        ],
        error_code="goal12_github_checks_unavailable",
    )
    checks = check_payload.get("check_runs")
    matching_checks = [
        item
        for item in checks
        if isinstance(item, dict)
        and item.get("name") == BROKER_REPORTS_ACTIONS_JOB_NAME
        and isinstance(item.get("app"), dict)
        and item["app"].get("slug") == "github-actions"
    ] if isinstance(checks, list) else []
    if (
        len(matching_checks) != 1
        or matching_checks[0].get("head_sha") != head
        or matching_checks[0].get("status") != "completed"
        or matching_checks[0].get("conclusion") != "success"
        or not isinstance(
            matching_checks[0].get("pull_requests"),
            list,
        )
        or not any(
            isinstance(item, dict)
            and item.get("number") == pr["number"]
            for item in matching_checks[0]["pull_requests"]
        )
    ):
        raise RuntimeError("goal12_actions_not_green_for_head")
    details_url = matching_checks[0].get("details_url")
    details_match = (
        _ACTIONS_DETAILS_URL_RE.fullmatch(details_url)
        if isinstance(details_url, str)
        else None
    )
    if details_match is None:
        raise RuntimeError("goal12_actions_not_green_for_head")

    run = _gh_json(
        [
            "gh",
            "run",
            "view",
            details_match.group(1),
            "--json",
            "headSha,event,status,conclusion,workflowName,url,jobs",
        ],
        error_code="goal12_github_actions_run_unavailable",
    )
    run_api = _gh_json(
        [
            "gh",
            "api",
            "-H",
            "Accept: application/vnd.github+json",
            (
                "repos/{owner}/{repo}/actions/runs/"
                f"{details_match.group(1)}"
            ),
        ],
        error_code="goal12_github_actions_run_unavailable",
    )
    jobs = run.get("jobs")
    exact_jobs = [
        item
        for item in jobs
        if isinstance(item, dict)
        and item.get("name") == BROKER_REPORTS_ACTIONS_JOB_NAME
    ] if isinstance(jobs, list) else []
    if (
        run.get("headSha") != head
        or run.get("event") != "pull_request"
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
        or run.get("workflowName") != BROKER_REPORTS_ACTIONS_WORKFLOW_NAME
        or run.get("url") != details_url.split("/job/", 1)[0]
        or len(exact_jobs) != 1
        or exact_jobs[0].get("status") != "completed"
        or exact_jobs[0].get("conclusion") != "success"
        or run_api.get("head_sha") != head
        or run_api.get("event") != "pull_request"
        or run_api.get("status") != "completed"
        or run_api.get("conclusion") != "success"
        or run_api.get("path") != BROKER_REPORTS_ACTIONS_WORKFLOW_PATH
        or run_api.get("html_url") != details_url.split("/job/", 1)[0]
        or not isinstance(run_api.get("pull_requests"), list)
        or not any(
            isinstance(item, dict)
            and item.get("number") == pr["number"]
            for item in run_api["pull_requests"]
        )
    ):
        raise RuntimeError("goal12_actions_not_green_for_head")


def _gh_json(
    command: list[str],
    *,
    error_code: str,
    input_text: str | None = None,
) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        input=input_text,
    )
    if result.returncode != 0:
        raise RuntimeError(error_code)
    try:
        payload = json.loads(result.stdout)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(error_code) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(error_code)
    return payload


def _require_result_artifacts_absent() -> None:
    if any(
        path.exists()
        for path in (
            TRANSPARENT_REPORT_PATH,
            SAFE_RECEIPT_PATH,
            MARKDOWN_REPORT_PATH,
        )
    ):
        raise RuntimeError("goal12_result_artifact_already_exists")


def _execution_lock_path(plan_hash: str) -> Path:
    if (
        not isinstance(plan_hash, str)
        or len(plan_hash) != 64
        or any(
            character not in "0123456789abcdef"
            for character in plan_hash
        )
    ):
        raise RuntimeError("goal12_execution_lock_plan_invalid")
    result = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError("goal12_git_common_dir_unavailable")
    common_dir = Path(result.stdout.strip())
    if not common_dir.is_absolute():
        common_dir = REPO_ROOT / common_dir
    common_dir = common_dir.resolve()
    if not common_dir.is_dir():
        raise RuntimeError("goal12_git_common_dir_unavailable")
    return (
        common_dir
        / "codex-broker-reports"
        / "goal12"
        / f"{plan_hash}.execution-lock.safe.json"
    )


def _execution_lock_payload(
    *,
    plan_hash: str,
    head: str,
    private_dir: Path,
    execution_claim_id: str,
) -> dict[str, Any]:
    if not _is_execution_claim_id(execution_claim_id):
        raise RuntimeError("goal12_execution_claim_invalid")
    material = {
        "schema_version": EXECUTION_LOCK_SCHEMA_VERSION,
        "status": "claimed_before_provider_transport",
        "plan_integrity_hash": plan_hash,
        "repository_head": head,
        "private_state_dir_sha256": _sha256_text(
            str(private_dir.resolve())
        ),
        "execution_claim_id": execution_claim_id,
        "provider_submission_budget_claimed": True,
    }
    return {**material, "integrity_hash": sha256_json(material)}


def _claim_execution_lock(
    *,
    path: Path,
    plan_hash: str,
    head: str,
    private_dir: Path,
    execution_claim_id: str,
) -> None:
    payload = _execution_lock_payload(
        plan_hash=plan_hash,
        head=head,
        private_dir=private_dir,
        execution_claim_id=execution_claim_id,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (_pretty_json(payload) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise RuntimeError("goal12_execution_already_claimed") from exc
    try:
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written <= 0:
                raise RuntimeError("goal12_execution_lock_write_failed")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _require_execution_lock(
    *,
    path: Path,
    plan_hash: str,
    head: str,
    private_dir: Path,
) -> str:
    try:
        observed = _read_json(path)
    except (OSError, ValueError) as exc:
        raise RuntimeError("goal12_execution_lock_invalid") from exc
    execution_claim_id = observed.get("execution_claim_id")
    if not _is_execution_claim_id(execution_claim_id):
        raise RuntimeError("goal12_execution_lock_invalid")
    expected = _execution_lock_payload(
        plan_hash=plan_hash,
        head=head,
        private_dir=private_dir,
        execution_claim_id=execution_claim_id,
    )
    if observed != expected:
        raise RuntimeError("goal12_execution_lock_invalid")
    return execution_claim_id


def _remote_execution_lock_tag(plan_hash: str) -> str:
    if not _is_sha256(plan_hash):
        raise RuntimeError("goal12_remote_execution_lock_plan_invalid")
    return f"{REMOTE_EXECUTION_LOCK_TAG_PREFIX}{plan_hash}"


def _remote_execution_lock_payload(
    *,
    plan_hash: str,
    head: str,
    private_dir: Path,
    execution_claim_id: str,
) -> dict[str, Any]:
    if not _is_execution_claim_id(execution_claim_id):
        raise RuntimeError("goal12_execution_claim_invalid")
    material = {
        "schema_version": REMOTE_EXECUTION_LOCK_SCHEMA_VERSION,
        "status": "globally_claimed_before_provider_transport",
        "plan_integrity_hash": plan_hash,
        "repository_head": head,
        "private_state_dir_sha256": _sha256_text(
            str(private_dir.resolve())
        ),
        "execution_claim_id_sha256": _sha256_text(execution_claim_id),
        "maximum_provider_submissions_total": 12,
        "provider_submission_budget_claimed": True,
    }
    return {**material, "integrity_hash": sha256_json(material)}


def _claim_remote_execution_lock(
    *,
    plan_hash: str,
    head: str,
    private_dir: Path,
    execution_claim_id: str,
) -> None:
    tag = _remote_execution_lock_tag(plan_hash)
    message = _pretty_json(
        _remote_execution_lock_payload(
            plan_hash=plan_hash,
            head=head,
            private_dir=private_dir,
            execution_claim_id=execution_claim_id,
        )
    )
    tag_object = _gh_json(
        [
            "gh",
            "api",
            "--method",
            "POST",
            "repos/{owner}/{repo}/git/tags",
            "--input",
            "-",
        ],
        error_code="goal12_remote_execution_tag_object_failed",
        input_text=_pretty_json(
            {
                "tag": tag,
                "message": message,
                "object": head,
                "type": "commit",
            }
        ),
    )
    tag_object_sha = tag_object.get("sha")
    if not _is_git_object_id(tag_object_sha):
        raise RuntimeError("goal12_remote_execution_tag_object_invalid")
    remote_ref = _gh_json(
        [
            "gh",
            "api",
            "--method",
            "POST",
            "repos/{owner}/{repo}/git/refs",
            "--input",
            "-",
        ],
        error_code="goal12_remote_execution_already_claimed",
        input_text=_pretty_json(
            {
                "ref": f"refs/tags/{tag}",
                "sha": tag_object_sha,
            }
        ),
    )
    if (
        remote_ref.get("ref") != f"refs/tags/{tag}"
        or not isinstance(remote_ref.get("object"), dict)
        or remote_ref["object"].get("sha") != tag_object_sha
        or remote_ref["object"].get("type") != "tag"
    ):
        raise RuntimeError("goal12_remote_execution_lock_invalid")


def _require_remote_execution_lock(
    *,
    plan_hash: str,
    head: str,
    private_dir: Path,
    execution_claim_id: str,
) -> None:
    tag = _remote_execution_lock_tag(plan_hash)
    remote_ref = _gh_json(
        [
            "gh",
            "api",
            "-H",
            "Accept: application/vnd.github+json",
            f"repos/{{owner}}/{{repo}}/git/ref/tags/{tag}",
        ],
        error_code="goal12_remote_execution_lock_missing",
    )
    tag_object_sha = (
        remote_ref.get("object", {}).get("sha")
        if isinstance(remote_ref.get("object"), dict)
        else None
    )
    if (
        remote_ref.get("ref") != f"refs/tags/{tag}"
        or remote_ref.get("object", {}).get("type") != "tag"
        or not _is_git_object_id(tag_object_sha)
    ):
        raise RuntimeError("goal12_remote_execution_lock_invalid")
    tag_object = _gh_json(
        [
            "gh",
            "api",
            "-H",
            "Accept: application/vnd.github+json",
            f"repos/{{owner}}/{{repo}}/git/tags/{tag_object_sha}",
        ],
        error_code="goal12_remote_execution_lock_missing",
    )
    expected_message = _pretty_json(
        _remote_execution_lock_payload(
            plan_hash=plan_hash,
            head=head,
            private_dir=private_dir,
            execution_claim_id=execution_claim_id,
        )
    )
    if (
        tag_object.get("tag") != tag
        or tag_object.get("message") != expected_message
        or not isinstance(tag_object.get("object"), dict)
        or tag_object["object"].get("sha") != head
        or tag_object["object"].get("type") != "commit"
    ):
        raise RuntimeError("goal12_remote_execution_lock_invalid")


def _resume_remote_execution_lock(
    *,
    plan_hash: str,
    head: str,
    private_dir: Path,
    execution_claim_id: str,
) -> None:
    try:
        _require_remote_execution_lock(
            plan_hash=plan_hash,
            head=head,
            private_dir=private_dir,
            execution_claim_id=execution_claim_id,
        )
    except RuntimeError as exc:
        if str(exc) != "goal12_remote_execution_lock_missing":
            raise
        _claim_remote_execution_lock(
            plan_hash=plan_hash,
            head=head,
            private_dir=private_dir,
            execution_claim_id=execution_claim_id,
        )


def _slot_submission_claim_filename(slot: Any) -> str:
    return (
        f"{slot.ordinal:02d}-"
        f"{_sha256_text(slot.slot_id)[:16]}.submission-claim.safe.json"
    )


def _slot_submission_claim_payload(
    *,
    plan_hash: str,
    head: str,
    slot: Any,
    operation_identity: str,
    execution_claim_id: str,
) -> dict[str, Any]:
    if (
        not _is_sha256(plan_hash)
        or not _is_git_object_id(head)
        or not isinstance(operation_identity, str)
        or not operation_identity
        or not _is_execution_claim_id(execution_claim_id)
    ):
        raise RuntimeError("goal12_slot_submission_claim_invalid")
    material = {
        "schema_version": SLOT_SUBMISSION_CLAIM_SCHEMA_VERSION,
        "status": "provider_submission_budget_irrevocably_claimed",
        "plan_integrity_hash": plan_hash,
        "repository_head": head,
        "slot_id": slot.slot_id,
        "slot_integrity_hash": slot.integrity_hash,
        "operation_identity_sha256": _sha256_text(operation_identity),
        "execution_claim_id_sha256": _sha256_text(execution_claim_id),
        "provider_submission_budget_consumed": True,
    }
    return {**material, "integrity_hash": sha256_json(material)}


def _claim_slot_submission(
    *,
    path: Path,
    plan_hash: str,
    head: str,
    slot: Any,
    operation_identity: str,
    execution_claim_id: str,
) -> None:
    payload = _slot_submission_claim_payload(
        plan_hash=plan_hash,
        head=head,
        slot=slot,
        operation_identity=operation_identity,
        execution_claim_id=execution_claim_id,
    )
    encoded = (_pretty_json(payload) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise RuntimeError(
            "goal12_slot_submission_already_claimed"
        ) from exc
    try:
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written <= 0:
                raise RuntimeError(
                    "goal12_slot_submission_claim_write_failed"
                )
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _recover_slot_submission_claims(
    *,
    state: dict[str, Any],
    state_path: Path,
    submission_claims_dir: Path,
    plan: Any,
    head: str,
    execution_claim_id: str,
    state_authority_key: bytes,
) -> None:
    expected_paths = {
        _slot_submission_claim_filename(slot): slot
        for slot in plan.slots
    }
    observed_paths = list(submission_claims_dir.iterdir())
    if any(
        not path.is_file() or path.name not in expected_paths
        for path in observed_paths
    ):
        raise RuntimeError("goal12_slot_submission_claim_set_invalid")
    changed = False
    for slot in plan.slots:
        path = (
            submission_claims_dir
            / _slot_submission_claim_filename(slot)
        )
        entry = state["slots"][slot.slot_id]
        operation_identity = (
            financial_semantic_v6_context_v2_1_budget_smoke_operation_identity(
                plan=plan,
                slot=slot,
            )
        )
        expected = _slot_submission_claim_payload(
            plan_hash=plan.integrity_hash,
            head=head,
            slot=slot,
            operation_identity=operation_identity,
            execution_claim_id=execution_claim_id,
        )
        if path.is_file():
            try:
                observed = _read_json(path)
            except (OSError, ValueError, RuntimeError) as exc:
                raise RuntimeError(
                    "goal12_slot_submission_claim_invalid"
                ) from exc
            if observed != expected:
                raise RuntimeError(
                    "goal12_slot_submission_claim_invalid"
                )
            operation_hash = expected["operation_identity_sha256"]
            if entry["status"] == "pending":
                entry["status"] = "consumed_pending_response"
                entry["operation_identity_sha256"] = operation_hash
                entry["provider_submission_budget_consumed"] = True
                changed = True
            elif (
                entry["status"]
                in {"consumed_pending_response", "completed"}
                and entry["provider_submission_budget_consumed"] is True
                and entry["operation_identity_sha256"] == operation_hash
            ):
                continue
            else:
                raise RuntimeError(
                    "goal12_slot_submission_claim_state_invalid"
                )
        elif (
            entry["status"] == "consumed_pending_response"
            or (
                entry["status"] == "completed"
                and entry["provider_submission_budget_consumed"] is True
            )
        ):
            raise RuntimeError(
                "goal12_slot_submission_claim_missing"
            )
    if changed:
        _write_private_state(
            state_path,
            state,
            state_authority_key=state_authority_key,
        )


def _validated_private_state_dir(path: Path) -> Path:
    resolved = path.resolve()
    if _is_within(resolved, REPO_ROOT):
        raise RuntimeError("goal12_private_state_inside_git")
    probe = resolved
    while not probe.exists():
        parent = probe.parent
        if parent == probe:
            raise RuntimeError(
                "goal12_private_state_git_boundary_unverifiable"
            )
        probe = parent
    if probe.is_file():
        probe = probe.parent
    if any(
        ancestor.name == ".git" or (ancestor / ".git").exists()
        for ancestor in (probe, *probe.parents)
    ):
        raise RuntimeError("goal12_private_state_inside_git")
    try:
        repository_probe = subprocess.run(
            [
                "git",
                "-C",
                str(probe),
                "rev-parse",
                "--is-inside-work-tree",
                "--is-inside-git-dir",
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError as exc:
        raise RuntimeError(
            "goal12_private_state_git_boundary_unverifiable"
        ) from exc
    if repository_probe.returncode == 0:
        raise RuntimeError("goal12_private_state_inside_git")
    return resolved


def _case_filename(slot: Any) -> str:
    return f"{slot.ordinal:02d}-{_sha256_text(slot.slot_id)[:16]}.private.json"


def _state_authority_key(
    *,
    execution_claim_id: str,
    plan_hash: str,
    head: str,
) -> bytes:
    if (
        not _is_execution_claim_id(execution_claim_id)
        or not _is_sha256(plan_hash)
        or not isinstance(head, str)
        or re.fullmatch(r"[0-9a-f]{40,64}", head) is None
    ):
        raise RuntimeError("goal12_private_state_authority_invalid")
    return hmac.new(
        BUDGET_SMOKE_SNAPSHOT_AUTHORITY_KEY,
        (
            f"{execution_claim_id}:{plan_hash}:{head}"
        ).encode("utf-8"),
        hashlib.sha256,
    ).digest()


def _private_state_hmac(
    state: dict[str, Any],
    *,
    state_authority_key: bytes,
) -> str:
    if (
        not isinstance(state_authority_key, bytes)
        or len(state_authority_key) != hashlib.sha256().digest_size
    ):
        raise RuntimeError("goal12_private_state_authority_invalid")
    payload = copy.deepcopy(state)
    payload.pop("state_integrity_hmac_sha256", None)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hmac.new(
        state_authority_key,
        encoded,
        hashlib.sha256,
    ).hexdigest()


def _validate_private_state_integrity(
    state: dict[str, Any],
    *,
    state_authority_key: bytes,
) -> None:
    observed = state.get("state_integrity_hmac_sha256")
    expected = _private_state_hmac(
        state,
        state_authority_key=state_authority_key,
    )
    if (
        not _is_sha256(observed)
        or not hmac.compare_digest(observed, expected)
    ):
        raise RuntimeError("goal12_private_state_integrity_invalid")


def _write_private_state(
    path: Path,
    state: dict[str, Any],
    *,
    state_authority_key: bytes,
    require_absent: bool = False,
) -> None:
    state["state_integrity_hmac_sha256"] = _private_state_hmac(
        state,
        state_authority_key=state_authority_key,
    )
    _write_json_atomically(
        path,
        state,
        require_absent=require_absent,
    )


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("goal12_json_object_required")
    return value


def _write_json_atomically(
    path: Path,
    payload: dict[str, Any],
    *,
    require_absent: bool = False,
    sort_keys: bool = True,
) -> None:
    _write_text_atomically(
        path,
        _pretty_json(payload, sort_keys=sort_keys) + "\n",
        require_absent=require_absent,
    )


def _write_text_atomically(
    path: Path,
    text: str,
    *,
    require_absent: bool = False,
) -> None:
    if require_absent and path.exists():
        raise RuntimeError("goal12_output_already_exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _write_or_validate_text(path: Path, text: str) -> None:
    if path.exists():
        try:
            observed = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError("goal12_existing_output_unreadable") from exc
        if observed != text:
            raise RuntimeError("goal12_existing_output_mismatch")
        return
    _write_text_atomically(
        path,
        text,
        require_absent=True,
    )


def _pretty_json(value: Any, *, sort_keys: bool = True) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=sort_keys,
        indent=2,
        allow_nan=False,
    )


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and re.fullmatch(r"[0-9a-f]{64}", value) is not None
    )


def _is_execution_claim_id(value: Any) -> bool:
    return _is_sha256(value)


def _is_git_object_id(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) in {40, 64}
        and re.fullmatch(r"[0-9a-f]+", value) is not None
    )


if __name__ == "__main__":
    raise SystemExit(main())
