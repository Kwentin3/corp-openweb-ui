#!/usr/bin/env python3
"""Qualify the current Goal #391 mapping prompt on frozen private Canonicals.

This is a deliberately small R&D seam.  It reads explicitly supplied frozen
Canonical snapshots, sends exactly one stateless structured request per case
through the existing OpenWebUI provider connection, validates the existing
semantic-mapping contract, and writes only a value-free receipt outside Git.
It does not create a chat, touch ArtifactStore, or mutate a Canonical.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from broker_reports_gate1.gate2_model_clients import Gate2StructuredModelClientFactory  # noqa: E402
from broker_reports_gate1.gate2_model_contracts import Gate2StructuredModelClientConfig  # noqa: E402
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    ORDINARY_TRADE_SEMANTIC_MAPPING_REQUEST_PROFILE,
)
from broker_reports_gate1.ordinary_trade_mapping_prompt import (  # noqa: E402
    OrdinaryTradeMappingPromptConfig,
    OrdinaryTradeMappingPromptResolverFactory,
    OrdinaryTradeMappingPromptUserContext,
)
from broker_reports_gate1.canonical_artifact import validate_canonical_artifact  # noqa: E402
from broker_reports_gate1.ordinary_trade_semantic_mapping import (  # noqa: E402
    MAPPING_RESPONSE_SCHEMA_VERSION,
    OrdinaryTradeSemanticMappingFactory,
)
from broker_reports_gate1.ordinary_trade_semantic_mapping_qualification import (  # noqa: E402
    _require_one_strict_result,
)


PROVIDER_PROFILE_ID = "google_gemini"
MODEL_ID = "models/gemini-3.5-flash"
SAFE_RECEIPT_SCHEMA_VERSION = "goal391_current_mapping_lab_receipt_v7"


class Goal391CurrentMappingLabError(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-one-clean-call-per-case", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--expectations", type=Path, required=True)
    parser.add_argument("--safe-receipt", type=Path, required=True)
    parser.add_argument("--progress-receipt", type=Path)
    parser.add_argument("--expected-git-head", required=True)
    parser.add_argument("--ordinary-user-id", required=True)
    parser.add_argument("--prompt-db-path", type=Path, required=True)
    parser.add_argument("--prompt-id", required=True)
    parser.add_argument("--prompt-version", required=True)
    parser.add_argument("--prompt-hash", required=True)
    parser.add_argument("--server-runtime", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=600)
    args = parser.parse_args()
    if args.execute_one_clean_call_per_case == args.preflight_only:
        raise SystemExit("goal391_exactly_one_execution_mode_required")
    if not 1 <= args.timeout_seconds <= 900:
        raise SystemExit("goal391_timeout_out_of_bounds")
    ordinary_user_id = str(args.ordinary_user_id or "").strip()
    if not ordinary_user_id:
        raise SystemExit("goal391_ordinary_user_id_invalid")
    prompt = _resolve_mapping_prompt(
        db_path=args.prompt_db_path,
        prompt_id=args.prompt_id,
        prompt_version=args.prompt_version,
        prompt_hash=args.prompt_hash,
        ordinary_user_id=ordinary_user_id,
    )

    corpus_root = args.corpus_root.resolve()
    expectation_path = args.expectations.resolve()
    receipt_path = args.safe_receipt.resolve()
    if _is_within(receipt_path, REPO_ROOT.resolve()):
        raise SystemExit("goal391_safe_receipt_must_be_outside_repository")
    if receipt_path.exists():
        raise SystemExit("goal391_safe_receipt_must_be_new")
    progress_path = args.progress_receipt.resolve() if args.progress_receipt else None
    if args.execute_one_clean_call_per_case and progress_path is None:
        raise SystemExit("goal391_progress_receipt_required")
    if progress_path is not None and (
        _is_within(progress_path, REPO_ROOT.resolve()) or progress_path.exists()
    ):
        raise SystemExit("goal391_progress_receipt_invalid")
    semantic = OrdinaryTradeSemanticMappingFactory.create()
    candidate = _current_candidate(
        semantic=semantic, prompt=prompt, expected_git_head=args.expected_git_head
    )
    cases = _preflight(
        corpus_root=corpus_root,
        expectation_path=expectation_path,
        candidate=candidate,
    )
    if args.preflight_only:
        receipt = _preflight_receipt(candidate=candidate, cases=cases)
        _write_json(receipt_path, receipt)
        print(json.dumps(_public_summary(receipt), ensure_ascii=False, sort_keys=True))
        return 0

    if not args.server_runtime:
        raise SystemExit("goal391_server_runtime_required")
    receipt = asyncio.run(
        _run_live_qualification(
            semantic=semantic,
            prompt=prompt,
            candidate=candidate,
            cases=cases,
            ordinary_user_id=ordinary_user_id,
            progress_path=progress_path,
        )
    )
    _write_json(receipt_path, receipt)
    print(json.dumps(_public_summary(receipt), ensure_ascii=False, sort_keys=True))
    if receipt["status"] != "PASSED":
        raise SystemExit("goal391_current_mapping_lab_failed")
    return 0


async def _run_live_qualification(
    *,
    semantic: Any,
    prompt: Any,
    candidate: Mapping[str, Any],
    cases: list[Mapping[str, Any]],
    ordinary_user_id: str,
    progress_path: Path | None,
) -> dict[str, Any]:
    request, user, chat_count = await _server_runtime_context(
        ordinary_user_id=ordinary_user_id
    )
    chats_before = await chat_count()
    if chats_before < 0:
        raise SystemExit("goal391_chat_count_unavailable")
    submissions = {"count": 0}

    def progress(state: str, case: Mapping[str, Any] | None = None) -> None:
        assert progress_path is not None
        value: dict[str, Any] = {
            "schema_version": "goal391_current_mapping_lab_progress_v1",
            "state": state,
            "candidate_sha256": _sha256(candidate),
            "provider_calls_started_total": submissions["count"],
        }
        if case is not None:
            value["case_sha256"] = _sha256(case["case_id"])
        _write_json(progress_path, value, atomic=True)

    progress("READY")

    async def one_shot_completion(*, form_data, **_kwargs):
        submissions["count"] += 1
        from open_webui.main import generate_chat_completion

        return await generate_chat_completion(request, form_data, user=user)

    client = Gate2StructuredModelClientFactory(
        config=Gate2StructuredModelClientConfig(
            request_profile=ORDINARY_TRADE_SEMANTIC_MAPPING_REQUEST_PROFILE,
            provider_profile_id=PROVIDER_PROFILE_ID,
            capability_probe=False,
            economy_budget_enforcement=False,
        ),
        user=user,
        request=request,
        completion_resolver=lambda _user_id: (
            one_shot_completion,
            user,
        ),
    ).create()

    records, terminal_error = await _run_all_cases(
        semantic=semantic,
        prompt=prompt,
        client=client,
        cases=cases,
        submissions=submissions,
        progress=progress,
    )

    lifecycle = client.qualification_lifecycle_snapshot()
    expected_calls = len(cases)
    chats_after = await chat_count()
    passed = (
        submissions["count"] == expected_calls
        and lifecycle == {
            "local_invocations_total": expected_calls,
            "provider_submissions_total": expected_calls,
            "provider_responses_total": expected_calls,
        }
        and all(record["outcome"] != "FAIL" for record in records)
        and terminal_error is None
        and chats_after >= 0
        and chats_after == chats_before
    )
    return {
        "schema_version": SAFE_RECEIPT_SCHEMA_VERSION,
        "status": "PASSED" if passed else "FAILED",
        "candidate": candidate,
        "corpus": {
            "cases_total": expected_calls,
            "provider_calls_started_total": submissions["count"],
            "provider_calls_returned_total": lifecycle["provider_responses_total"],
            "records": records,
        },
        "constraints": {
            "retries": 0,
            "best_of_n": False,
            "manual_output_repair": False,
            "chat_persistence": "forbidden",
            "chat_count_unchanged": chats_after == chats_before,
            "artifact_store_mutation": False,
            "canonical_mutation": False,
        },
        "terminal_error": terminal_error,
    }


async def _server_runtime_context(*, ordinary_user_id: str):
    """Use OpenWebUI's in-process completion owner; never read provider keys."""

    from starlette.requests import Request
    from open_webui.main import app
    from open_webui.models.chats import Chats
    from open_webui.models.users import Users

    if not isinstance(ordinary_user_id, str) or not ordinary_user_id:
        raise SystemExit("goal391_ordinary_user_id_invalid")

    result = await Users.get_users()
    users = result.get("users", []) if isinstance(result, dict) else []
    user = next(
        (
            item
            for item in users
            if getattr(item, "id", None) == ordinary_user_id
            and getattr(item, "role", None) == "user"
        ),
        None,
    )
    if user is None or not getattr(user, "id", None):
        raise SystemExit("goal391_ordinary_user_unavailable")
    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/chat/completions",
            "raw_path": b"/api/chat/completions",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 0),
            "server": ("127.0.0.1", 80),
            "app": app,
        }
    )
    await _ensure_server_model_available(
        request=request,
        user=user,
        model_id=MODEL_ID,
    )

    async def chat_count() -> int:
        value = await Chats.get_chats_by_user_id(user.id)
        items = getattr(value, "chats", None)
        if items is None:
            items = getattr(value, "items", None)
        if items is None and isinstance(value, dict):
            items = value.get("chats")
        if items is None and isinstance(value, list):
            items = value
        return len(items) if isinstance(items, list) else -1

    return request, user, chat_count


async def _ensure_server_model_available(
    *,
    request: Any,
    user: Any,
    model_id: str,
    model_loader=None,
) -> None:
    """Load the native catalog once, then require the released exact model ID."""

    if model_loader is None:
        from open_webui.utils.models import get_all_models

        model_loader = get_all_models
    models = await model_loader(request, user=user)
    available_ids = {
        item.get("id")
        for item in models
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    if model_id not in available_ids:
        raise SystemExit("goal391_released_model_not_available")


def _preflight(
    *,
    corpus_root: Path,
    expectation_path: Path,
    candidate: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if not corpus_root.is_dir() or not expectation_path.is_file():
        raise SystemExit("goal391_private_inputs_missing")
    expectations = _read_json(expectation_path)
    if (
        set(expectations) != {"schema_version", "candidate", "cases"}
        or expectations.get("schema_version")
        != "broker_reports_role_mapping_lab_disposition_expectations_v3"
        or expectations.get("candidate") != candidate
        or not isinstance(expectations.get("cases"), list)
        # The frozen manifest, not this runner, defines the closed qualification
        # scope.  An empty manifest cannot qualify a candidate; any non-empty
        # manifest is still fully validated below before a provider boundary is
        # reachable.
        or not expectations["cases"]
    ):
        raise SystemExit("goal391_expectations_invalid")
    cases = []
    for expected in expectations["cases"]:
        snapshot_id = expected.get("snapshot_id")
        if not isinstance(snapshot_id, str) or not snapshot_id:
            raise SystemExit("goal391_snapshot_id_invalid")
        snapshot_path = corpus_root / f"{snapshot_id}.canonical.json"
        if not snapshot_path.is_file():
            snapshot_path = corpus_root / "canonical" / f"{snapshot_id}.json"
        canonical = _read_json(snapshot_path)
        cases.append(_fixture(canonical=canonical, expected=expected))
    if len({case["case_id"] for case in cases}) != len(cases):
        raise SystemExit("goal391_case_id_duplicate")
    return cases


def _fixture(*, canonical: dict[str, Any], expected: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "case_id",
        "confirmed_understandings",
        "document_id",
        "expected_assessment",
        "fixture_identity",
        "frozen_mappings",
        "snapshot_id",
        "target_table_node_ids",
        "user_scope_sha256",
    }
    if set(expected) != required:
        raise SystemExit("goal391_expectation_case_invalid")
    _validate_expected_assessment(expected["expected_assessment"])
    source = canonical.get("source") or {}
    if validate_canonical_artifact(canonical).get("passed") is not True:
        raise SystemExit("goal391_canonical_invalid")
    binding = {
        "document_id": expected["document_id"],
        "canonical_version_id": str(canonical.get("artifact_id") or ""),
        "canonical_root_sha256": str(canonical.get("canonical_root_hash") or ""),
        "source_artifact_ref": str(source.get("source_artifact_ref") or ""),
        "source_sha256": str(source.get("source_sha256") or ""),
    }
    if not all(binding.values()):
        raise SystemExit("goal391_canonical_binding_invalid")
    expected_assessment = dict(expected["expected_assessment"])
    return {
        "case_id": expected["case_id"],
        "canonical": canonical,
        "canonical_binding": binding,
        "confirmed_understandings": expected["confirmed_understandings"],
        "target_table_node_ids": expected["target_table_node_ids"],
        "frozen_mappings": expected["frozen_mappings"],
        "user_scope_sha256": expected["user_scope_sha256"],
        "expected_assessment": expected_assessment,
        # The mapping owner, not a human manifest or the model, owns the full
        # bounded source envelope for an exclusion. It remains private here;
        # receipts contain only deterministic hashes and counts.
        "owner_classification_envelopes": _owner_classification_envelopes(
            canonical=canonical,
            confirmed_understandings=expected["confirmed_understandings"],
            target_table_node_ids=expected["target_table_node_ids"],
            required_table_decisions=expected_assessment[
                "required_table_decisions"
            ],
        ),
    }


def _owner_classification_envelopes(
    *,
    canonical: Mapping[str, Any],
    confirmed_understandings: list[dict[str, Any]],
    target_table_node_ids: list[str] | None,
    required_table_decisions: list[dict[str, Any]],
) -> dict[str, list[dict[str, str]]]:
    """Return full deterministic owner envelopes for new exclusion expectations.

    The frozen expectation supplies only semantic disposition and kind. This
    calls the existing mapping owner to project Canonical context; it does not
    select evidence or assign meaning.
    """

    required_ids = [
        decision["table_node_id"]
        for decision in required_table_decisions
        if decision["disposition"] == "NO_NAMED_CONSUMER"
        # Older immutable manifests may retain a model-selected subset. Read
        # compatibility is preserved below, but new expectations never use it.
        and "classification_evidence" not in decision
    ]
    if not required_ids:
        return {}
    package = OrdinaryTradeSemanticMappingFactory.create().build_mapping_package(
        canonical=canonical,
        confirmed_understandings=confirmed_understandings,
        target_table_node_ids=target_table_node_ids,
    )
    tables = ((package.get("case") or {}).get("tables"))
    if not isinstance(tables, list):
        raise SystemExit("goal391_owner_classification_envelope_invalid")
    by_node_id = {
        table.get("table_node_id"): table
        for table in tables
        if isinstance(table, Mapping) and isinstance(table.get("table_node_id"), str)
    }
    envelopes: dict[str, list[dict[str, str]]] = {}
    for table_node_id in required_ids:
        table = by_node_id.get(table_node_id)
        if table is None:
            raise SystemExit("goal391_owner_classification_envelope_invalid")
        envelopes[table_node_id] = _owner_classification_envelope(
            table.get("source_context_evidence")
        )
    return envelopes


async def _run_case(
    *, semantic, prompt, client, case: Mapping[str, Any], progress
) -> dict[str, Any]:
    package = semantic.build_mapping_package(
        canonical=case["canonical"],
        confirmed_understandings=case["confirmed_understandings"],
        target_table_node_ids=case["target_table_node_ids"],
    )
    progress("DISPATCH_INTENT", case)
    response = await client.extract(
        prompt=prompt,
        package=package,
        model_id=MODEL_ID,
        response_format=semantic.mapping_response_format(),
    )
    progress("RESPONSE_RECEIVED", case)
    _require_one_strict_result(response)
    if semantic.mapping_response_contract_failure_code(response) is not None:
        raise Goal391CurrentMappingLabError("goal391_model_response_contract_invalid")
    outcome = semantic.validate_mapping_response(
        response=response,
        canonical=case["canonical"],
        canonical_binding=case["canonical_binding"],
        model_id=MODEL_ID,
        provider_profile_id=PROVIDER_PROFILE_ID,
        execution_metadata=response.execution_metadata,
        confirmed_understandings=case["confirmed_understandings"],
        user_scope_sha256=case["user_scope_sha256"],
        target_table_node_ids=case["target_table_node_ids"],
        frozen_mappings=case["frozen_mappings"],
    )
    return {"outcome": outcome, "response": response}


async def _run_all_cases(*, semantic, prompt, client, cases, submissions, progress):
    records = []
    terminal_error = None
    for case in cases:
        before = submissions["count"]
        lifecycle_before = client.qualification_lifecycle_snapshot()
        progress("CASE_PREPARED", case)
        try:
            outcome = await _run_case(
                semantic=semantic,
                prompt=prompt,
                client=client,
                case=case,
                progress=progress,
            )
            if submissions["count"] - before != 1:
                raise Goal391CurrentMappingLabError("goal391_exactly_one_call_required")
            records.append(_safe_record(case=case, outcome=outcome))
        except Exception as exc:
            terminal_error = _safe_error_code(exc)
            lifecycle_after = client.qualification_lifecycle_snapshot()
            started = (
                lifecycle_after["provider_submissions_total"]
                - lifecycle_before["provider_submissions_total"]
            )
            returned = (
                lifecycle_after["provider_responses_total"]
                - lifecycle_before["provider_responses_total"]
            )
            records.append(
                {
                    "case_sha256": _sha256(case["case_id"]),
                    "canonical_root_sha256": case["canonical_binding"]["canonical_root_sha256"],
                    "expected_assessment_sha256": _sha256(case["expected_assessment"]),
                    "actual_status": "NOT_REACHED",
                    "outcome": (
                        "TRANSPORT_ERROR"
                        if returned == 0
                        else "POST_RESPONSE_VALIDATION_ERROR"
                    ),
                    "provider_calls_started_total": started,
                    "provider_calls_returned_total": returned,
                    "error_code": terminal_error,
                }
            )
            break
    return records, terminal_error


def _safe_record(*, case: Mapping[str, Any], outcome: Mapping[str, Any]) -> dict[str, Any]:
    assessment = case["expected_assessment"]
    result = outcome["outcome"]
    actual_status = result.get("status")
    raw_actual_resolutions = {
        item.get("table_node_id"): item
        for item in result.get("table_resolutions") or []
        if isinstance(item, Mapping) and isinstance(item.get("table_node_id"), str)
    }
    actual_resolutions = {
        item.get("table_node_id"): {
            key: item.get(key)
            for key in ("table_node_id", "disposition", "no_consumer_kind")
            if key in item
        }
        for item in result.get("table_resolutions") or []
        if isinstance(item, Mapping)
    }
    if actual_status == "CURRENCY_ASSERTION_REQUIRED":
        response = (result.get("currency_mapping_plan") or {}).get("response")
        decisions = response.get("table_decisions") if isinstance(response, Mapping) else []
        targets = case["target_table_node_ids"]
        if isinstance(decisions, list) and len(decisions) == len(targets) == 1:
            decision = decisions[0]
            if isinstance(decision, Mapping):
                actual_resolutions[targets[0]] = {
                    "table_node_id": targets[0],
                    **{
                        key: decision.get(key)
                        for key in ("disposition", "no_consumer_kind")
                        if key in decision
                    },
                }
                raw_actual_resolutions[targets[0]] = decision
    required = {
        item["table_node_id"]: item
        for item in assessment["required_table_decisions"]
    }
    expected_classification_evidence_signatures = {
        node_id: _classification_evidence_list_signature(
            decision["classification_evidence"]
        )
        for node_id, decision in required.items()
        if "classification_evidence" in decision
    }
    expected_owner_classification_envelope_signatures = {
        node_id: _owner_classification_envelope_signature(envelope)
        for node_id, envelope in (
            case.get("owner_classification_envelopes") or {}
        ).items()
    }
    actual_classification_evidence_signatures = {
        node_id: _classification_evidence_list_signature(
            resolution["classification_evidence"]
        )
        for node_id, resolution in raw_actual_resolutions.items()
        if node_id in expected_classification_evidence_signatures
        and "classification_evidence" in resolution
    }
    actual_owner_classification_envelope_signatures = {
        node_id: _owner_classification_envelope_signature(
            resolution["classification_evidence"]
        )
        for node_id, resolution in raw_actual_resolutions.items()
        if node_id in expected_owner_classification_envelope_signatures
        and "classification_evidence" in resolution
    }
    qualified_table_node_ids = sorted(
        str(item["case_scope"]["table_node_id"])
        for item in result.get("qualification_receipts") or []
        if isinstance(item, Mapping)
        and isinstance(item.get("case_scope"), Mapping)
        and isinstance(item["case_scope"].get("table_node_id"), str)
    )
    unresolved = (
        sorted(case["target_table_node_ids"])
        if actual_status == "SPECIALIST_REVIEW_REQUIRED"
        else []
    )
    required_decisions_match = all(
        actual_resolutions.get(node_id)
        == {
            key: value
            for key, value in decision.items()
            if key != "classification_evidence"
        }
        for node_id, decision in required.items()
    )
    classification_evidence_matches = (
        actual_classification_evidence_signatures
        == expected_classification_evidence_signatures
    )
    owner_classification_envelope_matches = (
        actual_owner_classification_envelope_signatures
        == expected_owner_classification_envelope_signatures
    )
    expected_exclusion_path_required = any(
        decision["disposition"] == "NO_NAMED_CONSUMER"
        for decision in required.values()
    )
    actual_exclusion_path_present = any(
        resolution.get("disposition") == "NO_NAMED_CONSUMER"
        for resolution in actual_resolutions.values()
    )
    complete_without_required_exclusion_path = (
        actual_status == "COMPLETE"
        and expected_exclusion_path_required
        and not actual_exclusion_path_present
    )
    unresolved_table_set_match = (
        unresolved == sorted(assessment["unresolved_table_node_ids"])
    )
    forbidden_qualified_mapping_clear = not set(qualified_table_node_ids).intersection(
        assessment["forbidden_qualified_mapping_table_node_ids"]
    )
    status_matches = actual_status == assessment.get("expected_status")
    matches = (
        status_matches
        and required_decisions_match
        and classification_evidence_matches
        and owner_classification_envelope_matches
        and unresolved_table_set_match
        and forbidden_qualified_mapping_clear
        and not complete_without_required_exclusion_path
    )
    actual_disposition_counts: dict[str, int] = {}
    actual_no_consumer_kind_counts: dict[str, int] = {}
    for resolution in actual_resolutions.values():
        disposition = resolution.get("disposition")
        if isinstance(disposition, str):
            actual_disposition_counts[disposition] = (
                actual_disposition_counts.get(disposition, 0) + 1
            )
        no_consumer_kind = resolution.get("no_consumer_kind")
        if isinstance(no_consumer_kind, str):
            actual_no_consumer_kind_counts[no_consumer_kind] = (
                actual_no_consumer_kind_counts.get(no_consumer_kind, 0) + 1
            )
    return {
        "case_sha256": _sha256(case["case_id"]),
        "canonical_root_sha256": case["canonical_binding"]["canonical_root_sha256"],
        "expected_assessment_sha256": _sha256(assessment),
        "actual_table_decisions_sha256": _sha256(actual_resolutions),
        "qualified_table_node_ids_sha256": _sha256(qualified_table_node_ids),
        "qualified_mapping_total": len(qualified_table_node_ids),
        "actual_table_decision_count": len(actual_resolutions),
        "actual_disposition_counts": dict(sorted(actual_disposition_counts.items())),
        "actual_no_consumer_kind_counts": dict(
            sorted(actual_no_consumer_kind_counts.items())
        ),
        "expected_classification_evidence_sha256": _sha256(
            expected_classification_evidence_signatures
        ),
        "actual_classification_evidence_sha256": _sha256(
            actual_classification_evidence_signatures
        ),
        "expected_owner_classification_envelope_sha256": _sha256(
            expected_owner_classification_envelope_signatures
        ),
        "actual_owner_classification_envelope_sha256": _sha256(
            actual_owner_classification_envelope_signatures
        ),
        "classification_evidence_required_total": sum(
            _classification_evidence_list_count(
                decision.get("classification_evidence")
            )
            for decision in required.values()
            if "classification_evidence" in decision
        ),
        "actual_classification_evidence_total": sum(
            _classification_evidence_list_count(
                resolution.get("classification_evidence")
            )
            for node_id, resolution in raw_actual_resolutions.items()
            if node_id in expected_classification_evidence_signatures
            and "classification_evidence" in resolution
        ),
        "classification_evidence_matches": classification_evidence_matches,
        "owner_classification_envelope_required_total": sum(
            _owner_classification_envelope_count(envelope)
            for envelope in (case.get("owner_classification_envelopes") or {}).values()
        ),
        "actual_owner_classification_envelope_total": sum(
            _owner_classification_envelope_count(
                resolution.get("classification_evidence")
            )
            for node_id, resolution in raw_actual_resolutions.items()
            if node_id in expected_owner_classification_envelope_signatures
        ),
        "owner_classification_envelope_matches": (
            owner_classification_envelope_matches
        ),
        "complete_without_required_exclusion_path": (
            complete_without_required_exclusion_path
        ),
        "actual_status": actual_status,
        "status_matches": status_matches,
        "required_decisions_match": required_decisions_match,
        "unresolved_table_set_match": unresolved_table_set_match,
        "forbidden_qualified_mapping_clear": forbidden_qualified_mapping_clear,
        "outcome": "PASS" if matches else "FAIL",
        "provider_calls_started_total": 1,
        "provider_calls_returned_total": 1,
    }


def _public_summary(receipt: Mapping[str, Any]) -> dict[str, Any]:
    corpus = receipt["corpus"]
    outcomes = [item.get("outcome") for item in corpus["records"]]
    return {
        "schema_version": receipt["schema_version"],
        "status": receipt["status"],
        "cases_total": corpus["cases_total"],
        "provider_calls": [
            corpus["provider_calls_started_total"],
            corpus["provider_calls_returned_total"],
        ],
        "pass_total": outcomes.count("PASS"),
        "fail_total": outcomes.count("FAIL"),
    }


def _preflight_receipt(
    *, candidate: Mapping[str, Any], cases: list[Mapping[str, Any]]
) -> dict[str, Any]:
    return {
        "schema_version": SAFE_RECEIPT_SCHEMA_VERSION,
        "status": "PREFLIGHT_PASSED",
        "candidate": dict(candidate),
        "corpus": {
            "cases_total": len(cases),
            "provider_calls_started_total": 0,
            "provider_calls_returned_total": 0,
            "records": [
                {
                    "case_sha256": _sha256(case["case_id"]),
                    "canonical_root_sha256": case["canonical_binding"][
                        "canonical_root_sha256"
                    ],
                    "expected_assessment_sha256": _sha256(
                        case["expected_assessment"]
                    ),
                }
                for case in cases
            ],
        },
        "constraints": {
            "provider_calls": 0,
            "chat_persistence": "forbidden",
            "artifact_store_mutation": False,
            "canonical_mutation": False,
        },
        "terminal_error": None,
    }


def _safe_error_code(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code:
        return code
    return type(exc).__name__


def _current_candidate(*, semantic: Any, prompt: Any, expected_git_head: str) -> dict[str, str]:
    if re.fullmatch(r"[0-9a-f]{40}", expected_git_head) is None:
        raise SystemExit("goal391_expected_git_head_invalid")
    try:
        actual_git_head = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit("goal391_git_head_unavailable") from exc
    if actual_git_head != expected_git_head:
        raise SystemExit("goal391_git_head_mismatch")
    return {
        "git_head": actual_git_head,
        "model_id": MODEL_ID,
        "provider_profile_id": PROVIDER_PROFILE_ID,
        "prompt_ref": prompt.prompt_ref,
        "prompt_version": prompt.version,
        "prompt_sha256": prompt.hash,
        "prompt_contract_id": prompt.prompt_contract_id,
        "prompt_input_schema_version": prompt.input_schema_version,
        "prompt_output_schema_id": prompt.output_schema_id,
        "prompt_output_schema_version": prompt.output_schema_version,
        "response_schema_version": MAPPING_RESPONSE_SCHEMA_VERSION,
        "response_format_sha256": _sha256(semantic.mapping_response_format()),
    }


def _resolve_mapping_prompt(
    *,
    db_path: Path,
    prompt_id: str,
    prompt_version: str,
    prompt_hash: str,
    ordinary_user_id: str,
):
    """Resolve the version-pinned Workspace Prompt without exposing its body."""

    selector_id = str(prompt_id or "").strip()
    if not selector_id:
        raise SystemExit("goal391_mapping_prompt_selector_invalid")
    return OrdinaryTradeMappingPromptResolverFactory(
        OrdinaryTradeMappingPromptConfig(
            source="openwebui_sqlite",
            db_path=db_path,
            prompt_id=selector_id,
            command=None,
            release_prompt_version=str(prompt_version or "").strip() or None,
            release_prompt_hash=str(prompt_hash or "").strip() or None,
        )
    ).create().resolve(
        OrdinaryTradeMappingPromptUserContext(
            user_id=ordinary_user_id,
            user_role="user",
        )
    )


def _validate_expected_assessment(value: Any) -> None:
    required = {
        "expected_status",
        "required_table_decisions",
        "unresolved_table_node_ids",
        "forbidden_qualified_mapping_table_node_ids",
    }
    if (
        not isinstance(value, Mapping)
        or set(value) != required
        or not isinstance(value["expected_status"], str)
        or not value["expected_status"]
        or not isinstance(value["required_table_decisions"], list)
        or not isinstance(value["unresolved_table_node_ids"], list)
        or not isinstance(value["forbidden_qualified_mapping_table_node_ids"], list)
    ):
        raise SystemExit("goal391_expected_assessment_invalid")
    table_ids = set()
    for decision in value["required_table_decisions"]:
        if not isinstance(decision, Mapping):
            raise SystemExit("goal391_expected_assessment_invalid")
        disposition = decision.get("disposition")
        expected_keys = {"table_node_id", "disposition"}
        if disposition == "NO_NAMED_CONSUMER":
            expected_keys.add("no_consumer_kind")
        if "classification_evidence" in decision:
            expected_keys.add("classification_evidence")
        if (
            set(decision) != expected_keys
            or not isinstance(decision.get("table_node_id"), str)
            or not decision["table_node_id"]
            or decision["table_node_id"] in table_ids
            or not isinstance(disposition, str)
            or not disposition
            or (
                disposition == "NO_NAMED_CONSUMER"
                and decision.get("no_consumer_kind")
                not in {"INSTRUCTIONAL_REFERENCE", "OTHER_NO_NAMED_CONSUMER"}
            )
            or (
                "classification_evidence" in decision
                and (
                    disposition != "NO_NAMED_CONSUMER"
                    or _classification_evidence_list_signature(
                        decision["classification_evidence"], strict=True
                    )
                    is None
                )
            )
        ):
            raise SystemExit("goal391_expected_assessment_invalid")
        table_ids.add(decision["table_node_id"])
    for key in (
        "unresolved_table_node_ids",
        "forbidden_qualified_mapping_table_node_ids",
    ):
        if (
            any(not isinstance(item, str) or not item for item in value[key])
            or len(value[key]) != len(set(value[key]))
        ):
            raise SystemExit("goal391_expected_assessment_invalid")


def _classification_evidence_list_signature(
    value: Any, *, strict: bool = False
) -> str | None:
    """Return a value-free fingerprint of one ordered exact evidence list."""

    if not isinstance(value, list) or not value:
        return None
    canonical: list[dict[str, str]] = []
    for item in value:
        if (
            not isinstance(item, Mapping)
            or (strict and set(item) != {"context_ref", "relation"})
            or not isinstance(item.get("context_ref"), str)
            or not item["context_ref"]
            or not isinstance(item.get("relation"), str)
            or not item["relation"]
        ):
            return None
        canonical.append(
            {"context_ref": item["context_ref"], "relation": item["relation"]}
        )
    if len(canonical) != len(
        {(item["context_ref"], item["relation"]) for item in canonical}
    ):
        return None
    return _sha256(canonical)


def _classification_evidence_list_count(value: Any) -> int:
    """Return only a list length; receipt code never returns the list itself."""

    return len(value) if isinstance(value, list) else 0


def _owner_classification_envelope(value: Any) -> list[dict[str, str]]:
    """Reduce the owner's private projection to its immutable response shape."""

    if not isinstance(value, list) or not value:
        raise SystemExit("goal391_owner_classification_envelope_invalid")
    envelope: list[dict[str, str]] = []
    for entry in value:
        if (
            not isinstance(entry, Mapping)
            or not all(
                isinstance(entry.get(key), str) and entry[key]
                for key in (
                    "context_ref",
                    "relation",
                    "canonical_node_id",
                    "literal_sha256",
                )
            )
            or re.fullmatch(r"[0-9a-f]{64}", entry["literal_sha256"]) is None
        ):
            raise SystemExit("goal391_owner_classification_envelope_invalid")
        envelope.append(
            {
                key: entry[key]
                for key in (
                    "context_ref",
                    "relation",
                    "canonical_node_id",
                    "literal_sha256",
                )
            }
        )
    if len(envelope) != len(
        {
            (entry["context_ref"], entry["relation"])
            for entry in envelope
        }
    ):
        raise SystemExit("goal391_owner_classification_envelope_invalid")
    return envelope


def _owner_classification_envelope_signature(value: Any) -> str | None:
    """Fingerprint one exact full owner envelope without emitting its values."""

    if not isinstance(value, list) or not value:
        return None
    normalized: list[dict[str, str]] = []
    for entry in value:
        if (
            not isinstance(entry, Mapping)
            or set(entry)
            != {
                "context_ref",
                "relation",
                "canonical_node_id",
                "literal_sha256",
            }
            or not all(
                isinstance(entry.get(key), str) and entry[key]
                for key in (
                    "context_ref",
                    "relation",
                    "canonical_node_id",
                    "literal_sha256",
                )
            )
            or re.fullmatch(r"[0-9a-f]{64}", entry["literal_sha256"]) is None
        ):
            return None
        normalized.append({key: entry[key] for key in sorted(entry)})
    if len(normalized) != len(
        {
            (entry["context_ref"], entry["relation"])
            for entry in normalized
        }
    ):
        return None
    return _sha256(normalized)


def _owner_classification_envelope_count(value: Any) -> int:
    """Return a count only after strict full-envelope validation."""

    return len(value) if _owner_classification_envelope_signature(value) else 0


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit("goal391_private_json_invalid") from exc
    if not isinstance(value, dict):
        raise SystemExit("goal391_private_json_object_required")
    return value


def _write_json(path: Path, value: Mapping[str, Any], *, atomic: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if not atomic:
        path.write_text(serialized, encoding="utf-8")
        return
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(serialized)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def _sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
