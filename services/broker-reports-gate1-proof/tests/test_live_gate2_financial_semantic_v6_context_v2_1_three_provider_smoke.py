from __future__ import annotations

import ast
import asyncio
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (
    sha256_json,
)
from broker_reports_gate1.gate2_financial_semantic_v6_context_v2_1_budget_smoke import (
    _technical_error_category,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
CLI_PATH = (
    SERVICE_ROOT
    / "scripts"
    / "live_gate2_financial_semantic_v6_context_v2_1_three_provider_smoke.py"
)
PRECALL_SAFE_PATH = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "2026-07-29"
    / "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12.precall.plan.safe.json"
)
PRECALL_TRANSPARENT_PATH = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "2026-07-29"
    / "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12.precall.transparent.json"
)
CANONICAL_PLAN_INTEGRITY_HASH = (
    "9191197bdc947d6ba86db3169ba0d8c911ef88423d611e2c4424a9379167cbab"
)
CANONICAL_PRECALL_SAFE_FILE_SHA256 = (
    "2b3a25cd04f0fffc6532477a44b93f6ce78e7e32f76bc239cceb13a2f5abacfe"
)
CANONICAL_PRECALL_TRANSPARENT_FILE_SHA256 = (
    "f64ef2e1daa92cc3eaa204ed34f1e753595ce0d4c7a4fd937492a6c145c58537"
)
CANONICAL_PRECALL_TRANSPARENT_INTEGRITY = (
    "a91e86892fe8d9855265a02e4ac3607050130a09173c5030f2b9021faadbbebb"
)
ZERO_LIFECYCLE = {
    "local_invocations_total": 0,
    "provider_submissions_total": 0,
    "provider_responses_total": 0,
    "semantic_repair_total": 0,
    "retry_total": 0,
    "repair_total": 0,
    "fallback_total": 0,
}


def _load_cli():
    name = "goal12_three_provider_smoke_cli_under_test"
    spec = importlib.util.spec_from_file_location(name, CLI_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CLI = _load_cli()


@pytest.fixture(scope="module")
def authorities():
    registry, fixture, audit_manifest, plan = CLI._authorities()
    return {
        "registry": registry,
        "fixture": fixture,
        "audit_manifest": audit_manifest,
        "plan": plan,
    }


class _Capture:
    def __init__(self, trace: list[Any] | None = None) -> None:
        self.trace = trace if trace is not None else []
        self.consume_calls: list[tuple[Any, str]] = []
        self.private: dict[str, dict[str, Any]] = {}
        self.safe: dict[str, dict[str, Any]] = {}

    def consume(self, slot, operation_identity: str) -> None:
        self.trace.append(("consume", slot.slot_id))
        self.consume_calls.append((slot, operation_identity))

    def private_checkpoint(
        self,
        slot_id: str,
        payload: dict[str, Any],
    ) -> None:
        self.trace.append(("private_checkpoint", slot_id))
        self.private[slot_id] = copy.deepcopy(payload)

    def safe_checkpoint(
        self,
        slot_id: str,
        payload: dict[str, Any],
    ) -> None:
        self.trace.append(("safe_checkpoint", slot_id))
        self.safe[slot_id] = copy.deepcopy(payload)


class _NeverClient:
    def __init__(self) -> None:
        self.snapshot_calls = 0
        self.transport_calls = 0

    def qualification_lifecycle_snapshot(self):
        self.snapshot_calls += 1
        return {
            "local_invocations_total": 0,
            "provider_submissions_total": 0,
            "provider_responses_total": 0,
        }

    async def extract_context_v2_1_once(self, **_kwargs):
        self.transport_calls += 1
        raise AssertionError("provider_transport_must_not_run")


def _coordinator(
    authorities,
    *,
    clients: dict[str, Any],
    capture: _Capture,
):
    return (
        CLI.Gate2FinancialSemanticV6ContextV21BudgetSmokeCoordinator(
            plan=authorities["plan"],
            fixture=authorities["fixture"],
            outcome_audit_manifest=authorities["audit_manifest"],
            registry=authorities["registry"],
            clients=clients,
            consume_slot=capture.consume,
            private_checkpoint=capture.private_checkpoint,
            safe_checkpoint=capture.safe_checkpoint,
        )
    )


def _slot(authorities, provider_profile_id: str, case_id: str | None = None):
    matches = [
        item
        for item in authorities["plan"].slots
        if item.provider_profile_id == provider_profile_id
        and (case_id is None or item.case_id == case_id)
    ]
    assert matches
    return matches[0]


def _outcome_lifecycle(outcome) -> dict[str, int]:
    return {
        key: getattr(outcome, key)
        for key in ZERO_LIFECYCLE
    }


def test_canonical_plan_and_precall_artifacts_are_exact(
    authorities,
) -> None:
    plan = authorities["plan"]
    safe = json.loads(PRECALL_SAFE_PATH.read_text(encoding="utf-8"))
    transparent = json.loads(
        PRECALL_TRANSPARENT_PATH.read_text(encoding="utf-8")
    )

    CLI._require_precall_artifacts(plan.integrity_hash)

    assert plan.integrity_hash == CANONICAL_PLAN_INTEGRITY_HASH
    assert plan.to_safe_dict() == safe
    assert safe["integrity_hash"] == CANONICAL_PLAN_INTEGRITY_HASH
    assert transparent["plan_integrity_hash"] == (
        CANONICAL_PLAN_INTEGRITY_HASH
    )
    assert transparent["integrity_sha256"] == (
        CANONICAL_PRECALL_TRANSPARENT_INTEGRITY
    )
    assert hashlib.sha256(PRECALL_SAFE_PATH.read_bytes()).hexdigest() == (
        CANONICAL_PRECALL_SAFE_FILE_SHA256
    )
    assert hashlib.sha256(
        PRECALL_TRANSPARENT_PATH.read_bytes()
    ).hexdigest() == (
        CANONICAL_PRECALL_TRANSPARENT_FILE_SHA256
    )
    assert transparent["execution_accounting"][
        "provider_calls_total"
    ] == 0


def test_google_identity_failure_is_terminal_before_consume_or_client(
    authorities,
    tmp_path,
) -> None:
    slot = _slot(authorities, "google_gemini")
    never_client = _NeverClient()
    capture = _Capture()
    coordinator = _coordinator(
        authorities,
        clients={"google_gemini": never_client},
        capture=capture,
    )

    outcome = asyncio.run(coordinator.execute_slot(slot=slot))

    assert outcome.status == "failed"
    assert outcome.error_category == "infrastructure_provider_failure"
    assert outcome.failure_class == "provider_model_identity_preflight"
    assert outcome.failure_code == (
        "provider_inventory_has_no_dated_immutable_google_model_id"
    )
    assert _outcome_lifecycle(outcome) == ZERO_LIFECYCLE
    assert capture.consume_calls == []
    assert never_client.snapshot_calls == 0
    assert never_client.transport_calls == 0
    assert list(capture.private) == [slot.slot_id]
    assert list(capture.safe) == [slot.slot_id]

    checkpoint = tmp_path / "google.private.json"
    CLI._write_json_atomically(
        checkpoint,
        capture.private[slot.slot_id],
        require_absent=True,
        sort_keys=False,
    )
    restored = CLI._load_private_bundle(
        path=checkpoint,
        plan=authorities["plan"],
        slot=slot,
    )
    assert restored.private_evidence == (
        capture.private[slot.slot_id]["private_evidence"]
    )
    assert restored.safe_receipt == (
        capture.private[slot.slot_id]["safe_receipt"]
    )

    tampered = copy.deepcopy(capture.private[slot.slot_id])
    tampered["private_evidence"]["failure_code"] = "forged_failure"
    forged_checkpoint = tmp_path / "google-forged.private.json"
    CLI._write_json_atomically(
        forged_checkpoint,
        tampered,
        require_absent=True,
        sort_keys=False,
    )
    with pytest.raises(Exception) as failure:
        CLI._load_private_bundle(
            path=forged_checkpoint,
            plan=authorities["plan"],
            slot=slot,
        )
    assert str(getattr(failure.value, "code", "")).endswith(
        "budget_smoke_private_evidence_hash_invalid"
    )


def test_missing_client_is_preflight_failure_without_consumption(
    authorities,
) -> None:
    slot = _slot(authorities, "openai_gpt")
    capture = _Capture()
    coordinator = _coordinator(
        authorities,
        clients={},
        capture=capture,
    )

    outcome = asyncio.run(coordinator.execute_slot(slot=slot))

    assert outcome.status == "failed"
    assert outcome.error_category == "infrastructure_provider_failure"
    assert outcome.failure_code == "provider_client_preflight_unavailable"
    assert outcome.failure_class == "provider_configuration"
    assert _outcome_lifecycle(outcome) == ZERO_LIFECYCLE
    assert outcome.private_evidence["provider_metrics"] == {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "actual_cost_usd": "0",
        "latency_ms": 0,
    }
    assert capture.consume_calls == []
    assert list(capture.private) == [slot.slot_id]
    assert list(capture.safe) == [slot.slot_id]


def test_transport_contract_projection_tamper_fails_before_consumption(
    authorities,
) -> None:
    slot = _slot(authorities, "openai_gpt")
    never_client = _NeverClient()
    capture = _Capture()
    coordinator = _coordinator(
        authorities,
        clients={"openai_gpt": never_client},
        capture=capture,
    )
    canonical_projector = coordinator._projector

    def tampered_projector(**kwargs):
        projection = canonical_projector(**kwargs)
        return replace(
            projection,
            transport_contract=replace(
                projection.transport_contract,
                retry_calls=1,
            ),
        )

    coordinator._projector = tampered_projector

    with pytest.raises(Exception) as mismatch:
        asyncio.run(coordinator.execute_slot(slot=slot))

    assert str(getattr(mismatch.value, "code", "")).endswith(
        "budget_smoke_slot_projection_mismatch"
    )
    assert capture.consume_calls == []
    assert never_client.snapshot_calls == 0
    assert never_client.transport_calls == 0
    assert capture.private == {}
    assert capture.safe == {}


def test_consumed_slot_failure_accounts_one_submission_without_reconsume(
    authorities,
) -> None:
    slot = _slot(authorities, "openai_gpt")
    capture = _Capture()
    coordinator = _coordinator(
        authorities,
        clients={},
        capture=capture,
    )

    outcome = coordinator.record_consumed_slot_failure(slot=slot)

    assert outcome.status == "failed"
    assert outcome.error_category == "infrastructure_provider_failure"
    assert outcome.failure_code == "consumed_slot_response_unavailable"
    assert outcome.failure_class == "provider_transport"
    assert _outcome_lifecycle(outcome) == {
        "local_invocations_total": 1,
        "provider_submissions_total": 1,
        "provider_responses_total": 0,
        "semantic_repair_total": 0,
        "retry_total": 0,
        "repair_total": 0,
        "fallback_total": 0,
    }
    assert outcome.private_evidence["provider_metrics"] == {
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "actual_cost_usd": None,
        "latency_ms": None,
    }
    assert outcome.safe_receipt["counts"]["input_tokens"] is None
    assert outcome.safe_receipt["counts"]["output_tokens"] is None
    assert outcome.safe_receipt["counts"]["total_tokens"] is None
    assert outcome.safe_receipt["provider_metrics"] == {
        "actual_cost_usd": None,
        "latency_ms": None,
    }
    assert capture.consume_calls == []
    assert list(capture.private) == [slot.slot_id]
    assert list(capture.safe) == [slot.slot_id]


@pytest.mark.parametrize(
    ("failure_code", "failure_class"),
    (
        ("gate2_model_response_not_terminal", "provider_response_invalid"),
        (
            "gate2_model_response_budget_exceeded",
            "response_budget",
        ),
        (
            "financial_semantic_v6_context_v2_1_choice_json_invalid",
            "Gate2FinancialSemanticV6DecisionEvidenceError",
        ),
        (
            "financial_semantic_v6_context_v2_1_choice_key_unknown",
            "Gate2FinancialSemanticV6DecisionEvidenceError",
        ),
    ),
)
def test_only_explicit_terminal_or_choice_failures_are_invalid_response(
    failure_code: str,
    failure_class: str,
) -> None:
    assert (
        _technical_error_category(
            failure_code=failure_code,
            failure_class=failure_class,
        )
        == "invalid_response"
    )


@pytest.mark.parametrize(
    ("failure_code", "failure_class"),
    (
        (
            "gate2_provider_resolved_model_mismatch",
            "provider_model_mismatch",
        ),
        (
            "financial_semantic_v6_context_v2_1_budget_smoke_adapter_output_invalid",
            "Gate2FinancialSemanticV6DecisionEvidenceError",
        ),
        (
            "financial_semantic_v6_context_v2_1_exact_choice_not_preserved",
            "Gate2FinancialSemanticV6DecisionEvidenceError",
        ),
        ("gate2_model_call_failed", "provider_transport"),
        ("gate2_provider_error", "provider_error_response"),
    ),
)
def test_response_count_does_not_reclassify_authority_or_provider_failure(
    failure_code: str,
    failure_class: str,
) -> None:
    assert (
        _technical_error_category(
            failure_code=failure_code,
            failure_class=failure_class,
        )
        == "infrastructure_provider_failure"
    )


def test_private_state_create_restore_tamper_and_repo_boundary(
    authorities,
    tmp_path,
) -> None:
    plan = authorities["plan"]
    private_dir = tmp_path / "goal12-private-state"
    head = "1" * 40
    base_url = "https://stage.example.invalid"
    published_model_ids = {
        item.exact_model_id
        for item in plan.slots
        if item.immutable_model_id_proven
    }
    execution_claim_id = "a" * 64
    state_authority_key = CLI._state_authority_key(
        execution_claim_id=execution_claim_id,
        plan_hash=plan.integrity_hash,
        head=head,
    )

    assert CLI._validated_private_state_dir(private_dir) == (
        private_dir.resolve()
    )
    created = CLI._create_private_state(
        private_dir=private_dir,
        plan=plan,
        head=head,
        base_url=base_url,
        published_model_ids=published_model_ids,
        state_authority_key=state_authority_key,
    )
    restored = CLI._restore_private_state(
        private_dir=private_dir,
        plan=plan,
        head=head,
        base_url=base_url,
        state_authority_key=state_authority_key,
    )

    assert restored == created
    assert created["status"] == "in_progress"
    assert len(created["slots"]) == 12
    assert all(
        entry["status"] == "pending"
        and entry["provider_submission_budget_consumed"] is False
        for entry in created["slots"].values()
    )

    lock_path = tmp_path / "execution-lock.safe.json"
    CLI._claim_execution_lock(
        path=lock_path,
        plan_hash=plan.integrity_hash,
        head=head,
        private_dir=private_dir,
        execution_claim_id=execution_claim_id,
    )
    assert CLI._require_execution_lock(
        path=lock_path,
        plan_hash=plan.integrity_hash,
        head=head,
        private_dir=private_dir,
    ) == execution_claim_id
    lock_text = lock_path.read_text(encoding="utf-8")
    assert str(private_dir.resolve()) not in lock_text
    with pytest.raises(
        RuntimeError,
        match="goal12_execution_already_claimed",
    ):
        CLI._claim_execution_lock(
            path=lock_path,
            plan_hash=plan.integrity_hash,
            head=head,
            private_dir=tmp_path / "different-private-state",
            execution_claim_id="b" * 64,
        )
    with pytest.raises(
        RuntimeError,
        match="goal12_execution_lock_invalid",
    ):
        CLI._require_execution_lock(
            path=lock_path,
            plan_hash=plan.integrity_hash,
            head=head,
            private_dir=tmp_path / "different-private-state",
        )

    first_slot_id = plan.slots[0].slot_id
    forged = copy.deepcopy(created)
    forged["slots"][first_slot_id]["slot_integrity_hash"] = "0" * 64
    CLI._write_json_atomically(
        private_dir / "state.private.json",
        forged,
    )
    with pytest.raises(
        RuntimeError,
        match="goal12_private_state_integrity_invalid",
    ):
        CLI._restore_private_state(
            private_dir=private_dir,
            plan=plan,
            head=head,
            base_url=base_url,
            state_authority_key=state_authority_key,
        )

    with pytest.raises(
        RuntimeError,
        match="goal12_private_state_inside_git",
    ):
        CLI._validated_private_state_dir(
            REPO_ROOT / "goal12-private-state-forbidden"
        )

    other_repository = tmp_path / "other-repository"
    other_repository.mkdir()
    subprocess.run(
        ["git", "init", str(other_repository)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    with pytest.raises(
        RuntimeError,
        match="goal12_private_state_inside_git",
    ):
        CLI._validated_private_state_dir(
            other_repository / "private-evidence"
        )


def test_remote_execution_lock_is_atomic_owned_and_resume_safe(
    authorities,
    monkeypatch,
    tmp_path,
) -> None:
    plan_hash = authorities["plan"].integrity_hash
    head = "4" * 40
    owner_private_dir = tmp_path / "owner-private"
    competing_private_dir = tmp_path / "competing-private"
    owner_claim_id = "c" * 64
    competing_claim_id = "d" * 64
    tag_objects: dict[str, dict[str, Any]] = {}
    remote: dict[str, Any] = {"ref": None}

    def fake_gh_json(command, *, error_code, input_text=None):
        joined = " ".join(command)
        if "repos/{owner}/{repo}/git/tags --input -" in joined:
            payload = json.loads(input_text)
            object_sha = f"{len(tag_objects) + 1:040x}"
            tag_objects[object_sha] = {
                "tag": payload["tag"],
                "message": payload["message"],
                "object": {
                    "sha": payload["object"],
                    "type": payload["type"],
                },
            }
            return {"sha": object_sha}
        if "repos/{owner}/{repo}/git/refs --input -" in joined:
            if remote["ref"] is not None:
                raise RuntimeError(error_code)
            payload = json.loads(input_text)
            remote["ref"] = {
                "ref": payload["ref"],
                "object": {
                    "sha": payload["sha"],
                    "type": "tag",
                },
            }
            return copy.deepcopy(remote["ref"])
        if "/git/ref/tags/" in joined:
            if remote["ref"] is None:
                raise RuntimeError(error_code)
            return copy.deepcopy(remote["ref"])
        if "/git/tags/" in joined:
            object_sha = joined.rsplit("/", 1)[-1]
            if object_sha not in tag_objects:
                raise RuntimeError(error_code)
            return copy.deepcopy(tag_objects[object_sha])
        raise AssertionError(command)

    monkeypatch.setattr(CLI, "_gh_json", fake_gh_json)

    CLI._claim_remote_execution_lock(
        plan_hash=plan_hash,
        head=head,
        private_dir=owner_private_dir,
        execution_claim_id=owner_claim_id,
    )
    CLI._require_remote_execution_lock(
        plan_hash=plan_hash,
        head=head,
        private_dir=owner_private_dir,
        execution_claim_id=owner_claim_id,
    )
    claimed_ref = copy.deepcopy(remote["ref"])

    with pytest.raises(
        RuntimeError,
        match="goal12_remote_execution_lock_invalid",
    ):
        CLI._resume_remote_execution_lock(
            plan_hash=plan_hash,
            head=head,
            private_dir=competing_private_dir,
            execution_claim_id=competing_claim_id,
        )
    assert remote["ref"] == claimed_ref

    remote["ref"] = None
    CLI._resume_remote_execution_lock(
        plan_hash=plan_hash,
        head=head,
        private_dir=owner_private_dir,
        execution_claim_id=owner_claim_id,
    )
    CLI._require_remote_execution_lock(
        plan_hash=plan_hash,
        head=head,
        private_dir=owner_private_dir,
        execution_claim_id=owner_claim_id,
    )


def test_pending_zero_submission_checkpoint_recovers_after_crash(
    authorities,
    tmp_path,
) -> None:
    plan = authorities["plan"]
    slot = _slot(authorities, "openai_gpt")
    capture = _Capture()
    coordinator = _coordinator(
        authorities,
        clients={},
        capture=capture,
    )
    outcome = asyncio.run(coordinator.execute_slot(slot=slot))
    assert outcome.provider_submissions_total == 0

    private_dir = tmp_path / "recover-zero-call"
    cases_dir = private_dir / "cases"
    state_path = private_dir / "state.private.json"
    head = "5" * 40
    base_url = "https://stage.example.invalid"
    execution_claim_id = "e" * 64
    state_authority_key = CLI._state_authority_key(
        execution_claim_id=execution_claim_id,
        plan_hash=plan.integrity_hash,
        head=head,
    )
    state = CLI._create_private_state(
        private_dir=private_dir,
        plan=plan,
        head=head,
        base_url=base_url,
        published_model_ids={slot.exact_model_id},
        state_authority_key=state_authority_key,
    )
    cases_dir.mkdir()
    CLI._write_json_atomically(
        cases_dir / CLI._case_filename(slot),
        capture.private[slot.slot_id],
        require_absent=True,
        sort_keys=False,
    )

    CLI._recover_private_checkpoints(
        state=state,
        state_path=state_path,
        cases_dir=cases_dir,
        plan=plan,
        state_authority_key=state_authority_key,
    )

    entry = state["slots"][slot.slot_id]
    assert entry["status"] == "completed"
    assert entry["provider_submission_budget_consumed"] is False
    assert entry["operation_identity_sha256"] is None
    assert isinstance(entry["safe_summary"], dict)
    restored = CLI._restore_private_state(
        private_dir=private_dir,
        plan=plan,
        head=head,
        base_url=base_url,
        state_authority_key=state_authority_key,
    )
    assert restored == state


def test_slot_submission_claim_is_atomic_and_reconciles_without_resubmit(
    authorities,
    tmp_path,
) -> None:
    plan = authorities["plan"]
    slot = _slot(authorities, "anthropic_claude")
    private_dir = tmp_path / "atomic-slot-claim"
    claims_dir = private_dir / "submission-claims"
    state_path = private_dir / "state.private.json"
    head = "6" * 40
    base_url = "https://stage.example.invalid"
    execution_claim_id = "f" * 64
    operation_identity = (
        CLI.financial_semantic_v6_context_v2_1_budget_smoke_operation_identity(
            plan=plan,
            slot=slot,
        )
    )
    state_authority_key = CLI._state_authority_key(
        execution_claim_id=execution_claim_id,
        plan_hash=plan.integrity_hash,
        head=head,
    )
    state = CLI._create_private_state(
        private_dir=private_dir,
        plan=plan,
        head=head,
        base_url=base_url,
        published_model_ids={slot.exact_model_id},
        state_authority_key=state_authority_key,
    )
    claim_path = (
        claims_dir / CLI._slot_submission_claim_filename(slot)
    )

    CLI._claim_slot_submission(
        path=claim_path,
        plan_hash=plan.integrity_hash,
        head=head,
        slot=slot,
        operation_identity=operation_identity,
        execution_claim_id=execution_claim_id,
    )
    with pytest.raises(
        RuntimeError,
        match="goal12_slot_submission_already_claimed",
    ):
        CLI._claim_slot_submission(
            path=claim_path,
            plan_hash=plan.integrity_hash,
            head=head,
            slot=slot,
            operation_identity=operation_identity,
            execution_claim_id=execution_claim_id,
        )

    CLI._recover_slot_submission_claims(
        state=state,
        state_path=state_path,
        submission_claims_dir=claims_dir,
        plan=plan,
        head=head,
        execution_claim_id=execution_claim_id,
        state_authority_key=state_authority_key,
    )
    entry = state["slots"][slot.slot_id]
    assert entry["status"] == "consumed_pending_response"
    assert entry["provider_submission_budget_consumed"] is True
    assert entry["operation_identity_sha256"] == hashlib.sha256(
        operation_identity.encode("utf-8")
    ).hexdigest()
    with pytest.raises(
        RuntimeError,
        match="goal12_slot_submission_already_claimed",
    ):
        CLI._claim_slot_submission(
            path=claim_path,
            plan_hash=plan.integrity_hash,
            head=head,
            slot=slot,
            operation_identity=operation_identity,
            execution_claim_id=execution_claim_id,
        )


def test_execute_rejects_any_existing_result_artifact(
    monkeypatch,
    tmp_path,
) -> None:
    paths = (
        tmp_path / "transparent.json",
        tmp_path / "safe.json",
        tmp_path / "report.md",
    )
    monkeypatch.setattr(CLI, "TRANSPARENT_REPORT_PATH", paths[0])
    monkeypatch.setattr(CLI, "SAFE_RECEIPT_PATH", paths[1])
    monkeypatch.setattr(CLI, "MARKDOWN_REPORT_PATH", paths[2])

    CLI._require_result_artifacts_absent()
    for path in paths:
        path.write_text("already issued", encoding="utf-8")
        with pytest.raises(
            RuntimeError,
            match="goal12_result_artifact_already_exists",
        ):
            CLI._require_result_artifacts_absent()
        path.unlink()


def test_green_actions_guard_requires_exact_head_name_and_success(
    monkeypatch,
) -> None:
    head = "2" * 40
    pr_number = 218
    run_id = "123456789"
    run_url = f"https://github.com/acme/repo/actions/runs/{run_id}"
    current = {
        "pr": {
            "headRefOid": head,
            "state": "OPEN",
            "isDraft": False,
            "number": pr_number,
            "url": "https://github.com/acme/repo/pull/218",
        },
        "checks": {
            "check_runs": [
                {
                    "name": CLI.BROKER_REPORTS_ACTIONS_JOB_NAME,
                    "app": {"slug": "github-actions"},
                    "head_sha": head,
                    "status": "completed",
                    "conclusion": "success",
                    "details_url": f"{run_url}/job/987654321",
                    "pull_requests": [{"number": pr_number}],
                }
            ]
        },
        "run": {
            "headSha": head,
            "event": "pull_request",
            "status": "completed",
            "conclusion": "success",
            "workflowName": CLI.BROKER_REPORTS_ACTIONS_WORKFLOW_NAME,
            "url": run_url,
            "jobs": [
                {
                    "name": CLI.BROKER_REPORTS_ACTIONS_JOB_NAME,
                    "status": "completed",
                    "conclusion": "success",
                }
            ],
        },
        "run_api": {
            "head_sha": head,
            "event": "pull_request",
            "status": "completed",
            "conclusion": "success",
            "path": CLI.BROKER_REPORTS_ACTIONS_WORKFLOW_PATH,
            "html_url": run_url,
            "pull_requests": [{"number": pr_number}],
        },
    }
    calls: list[list[str]] = []

    def fake_gh_json(command, *, error_code, input_text=None):
        del error_code, input_text
        command = list(command)
        calls.append(command)
        joined = " ".join(command)
        if command[1:3] == ["pr", "view"]:
            return copy.deepcopy(current["pr"])
        if "/check-runs?" in joined:
            return copy.deepcopy(current["checks"])
        if command[1:3] == ["run", "view"]:
            return copy.deepcopy(current["run"])
        if "/actions/runs/" in joined:
            return copy.deepcopy(current["run_api"])
        raise AssertionError(command)

    monkeypatch.setattr(CLI, "_gh_json", fake_gh_json)

    CLI._require_green_actions(head)
    assert len(calls) == 4

    mutations = (
        ("pr", "headRefOid", "3" * 40),
        ("checks", "check_runs", []),
        ("run_api", "path", ".github/workflows/duplicate.yml"),
        ("run_api", "pull_requests", [{"number": 999}]),
    )
    for section, field, invalid_value in mutations:
        original = copy.deepcopy(current[section][field])
        current[section][field] = invalid_value
        with pytest.raises(
            RuntimeError,
            match="goal12_actions_not_green_for_head",
        ):
            CLI._require_green_actions(head)
        current[section][field] = original


def test_cli_preflight_and_parser_expose_no_execution_overrides(
    authorities,
) -> None:
    source = CLI_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    argument_flags = {
        argument.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_argument"
        for argument in node.args
        if isinstance(argument, ast.Constant)
        and isinstance(argument.value, str)
        and argument.value.startswith("--")
    }

    assert argument_flags == {
        "--preflight-only",
        "--execute",
        "--resume",
        "--private-state-dir",
        "--env-file",
        "--base-url",
    }
    assert argument_flags.isdisjoint(
        {
            "--model",
            "--model-id",
            "--temperature",
            "--max-tokens",
            "--reasoning",
            "--retry",
            "--repair",
            "--fallback",
        }
    )
    assert "existing GOAL 12 factories" in CLI.FACTORY_REQUIRED
    assert "must not accept model/parameter overrides" in CLI.FORBIDDEN
    for forbidden in (
        "args.model",
        "args.temperature",
        "args.retry",
        "args.repair",
        "args.fallback",
    ):
        assert forbidden not in source

    completed = subprocess.run(
        [sys.executable, str(CLI_PATH), "--preflight-only"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    assert summary["status"] == "preflight_passed_not_executed"
    assert summary["plan_integrity_hash"] == (
        authorities["plan"].integrity_hash
    )
    assert summary["execution_accounting"] == {
        "provider_submissions_total": 0,
        "provider_responses_total": 0,
        "retry_total": 0,
        "repair_total": 0,
        "fallback_total": 0,
    }
    assert summary["active"] is False
    assert summary["production_admissions"] == []


def test_in_memory_openai_success_consumes_before_one_transport_and_issues_case(
    authorities,
    tmp_path,
) -> None:
    slot = _slot(
        authorities,
        "openai_gpt",
        "syn_successor_v2_no_registry_type",
    )
    trace: list[Any] = []
    capture = _Capture(trace)
    response = {
        "id": "chatcmpl-goal12-in-memory",
        "model": slot.exact_model_id,
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": {
                        "broker_reports_gate2_choice": {
                            "choice": "unclassified",
                            "reason": "no_registry_type",
                        }
                    },
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 12,
            "total_tokens": 112,
        },
    }
    transport_form_data: list[dict[str, Any]] = []

    def direct_transport(profile, form_data):
        assert profile.profile_id == slot.provider_profile_id
        trace.append(("transport", slot.slot_id))
        transport_form_data.append(copy.deepcopy(form_data))
        return copy.deepcopy(response)

    clients = CLI._clients(
        plan=authorities["plan"],
        published_model_ids={slot.exact_model_id},
        user_id="goal12-in-memory-user",
        request_context=SimpleNamespace(),
    )
    clients[slot.provider_profile_id].provider_adapter.native_transport_resolver = (
        direct_transport
    )
    coordinator = _coordinator(
        authorities,
        clients=clients,
        capture=capture,
    )

    outcome = asyncio.run(coordinator.execute_slot(slot=slot))

    assert outcome.status == "passed", (
        outcome.failure_code,
        outcome.failure_class,
        outcome.error_category,
    )
    assert outcome.technical_pipeline_exact is True
    assert outcome.semantic_answer_exact is True
    assert outcome.error_category is None
    assert _outcome_lifecycle(outcome) == {
        "local_invocations_total": 1,
        "provider_submissions_total": 1,
        "provider_responses_total": 1,
        "semantic_repair_total": 0,
        "retry_total": 0,
        "repair_total": 0,
        "fallback_total": 0,
    }
    assert [item[0] for item in trace] == [
        "consume",
        "transport",
        "private_checkpoint",
        "safe_checkpoint",
    ]
    assert len(capture.consume_calls) == 1
    assert len(transport_form_data) == 1
    assert transport_form_data[0] == outcome.prepared_request.form_data

    checkpoint = tmp_path / "openai-success.private.json"
    CLI._write_json_atomically(
        checkpoint,
        capture.private[slot.slot_id],
        require_absent=True,
        sort_keys=False,
    )
    bundle = CLI._load_private_bundle(
        path=checkpoint,
        plan=authorities["plan"],
        slot=slot,
    )
    issued_case = (
        CLI.Gate2FinancialSemanticV6TransparentSmokeReportFactory()
        .create_context_v2_1_budget_smoke_case(
            plan=authorities["plan"],
            plan_slot=slot,
            evidence_bundle=bundle,
        )
    )
    projection = issued_case.to_dict()
    assert projection["slot_id"] == slot.slot_id
    assert projection["technical_smoke_verdict"] == (
        "TECHNICAL_SMOKE_PASSED"
    )
    assert projection["semantic_smoke_verdict"] == (
        "SEMANTIC_SMOKE_PASSED"
    )


def test_post_extraction_choice_failure_preserves_output_without_second_call(
    authorities,
) -> None:
    slot = _slot(
        authorities,
        "openai_gpt",
        "syn_successor_v2_no_registry_type",
    )
    trace: list[Any] = []
    capture = _Capture(trace)
    exact_output = {
        "choice": "unclassified",
        "reason": "not_a_governed_reason",
    }
    response = {
        "id": "chatcmpl-goal12-post-extraction-failure",
        "model": slot.exact_model_id,
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": {
                        "broker_reports_gate2_choice": copy.deepcopy(
                            exact_output
                        )
                    },
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 12,
            "total_tokens": 112,
        },
    }
    transport_calls: list[dict[str, Any]] = []

    def direct_transport(profile, form_data):
        assert profile.profile_id == slot.provider_profile_id
        trace.append(("transport", slot.slot_id))
        transport_calls.append(copy.deepcopy(form_data))
        return copy.deepcopy(response)

    clients = CLI._clients(
        plan=authorities["plan"],
        published_model_ids={slot.exact_model_id},
        user_id="goal12-post-extraction-user",
        request_context=SimpleNamespace(),
    )
    clients[slot.provider_profile_id].provider_adapter.native_transport_resolver = (
        direct_transport
    )
    coordinator = _coordinator(
        authorities,
        clients=clients,
        capture=capture,
    )

    outcome = asyncio.run(coordinator.execute_slot(slot=slot))

    assert outcome.status == "failed"
    assert outcome.technical_pipeline_exact is False
    assert outcome.semantic_answer_exact is False
    assert outcome.error_category == "invalid_response"
    assert outcome.failure_code == (
        "financial_semantic_v6_context_v2_1_choice_reason_invalid"
    )
    assert outcome.adapter_extracted_output == exact_output
    assert outcome.private_evidence["adapter_extracted_output"] == exact_output
    assert outcome.private_evidence["raw_output"] == response
    assert outcome.safe_receipt["hashes"][
        "adapter_extracted_output_hash"
    ] == sha256_json(exact_output)
    assert _outcome_lifecycle(outcome) == {
        "local_invocations_total": 1,
        "provider_submissions_total": 1,
        "provider_responses_total": 1,
        "semantic_repair_total": 0,
        "retry_total": 0,
        "repair_total": 0,
        "fallback_total": 0,
    }
    assert len(transport_calls) == 1
    assert len(capture.consume_calls) == 1
    assert [item[0] for item in trace] == [
        "consume",
        "transport",
        "private_checkpoint",
        "safe_checkpoint",
    ]
    issued_case = (
        CLI.Gate2FinancialSemanticV6TransparentSmokeReportFactory()
        .create_context_v2_1_budget_smoke_case(
            plan=authorities["plan"],
            plan_slot=slot,
            evidence_bundle=outcome.evidence_bundle,
        )
        .to_dict()
    )
    assert issued_case["exact_adapter_extracted_output"] == exact_output
    assert issued_case["normalized_canonical_answer"] is None
    assert issued_case["error_category"] == "invalid_response"
