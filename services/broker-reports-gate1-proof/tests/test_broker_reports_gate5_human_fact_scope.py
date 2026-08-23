from __future__ import annotations

import ast
import copy
from dataclasses import replace
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from broker_reports_gate1 import build_retention_policy
from broker_reports_gate1.artifact_models import ArtifactAccessContext
from broker_reports_gate1.gate5_client_evidence_review import (
    GATE5_CLIENT_EVIDENCE_REVIEW_SCHEMA_VERSION,
    Gate5ClientEvidenceReviewRuntime,
)
from broker_reports_gate1.gate5_declaration_scope_resolution import (
    GATE5_DECLARATION_SCOPE_ACTIVATION_SCHEMA_VERSION,
)
from broker_reports_gate1.gate5_evidence_intake import (
    GATE5_EVIDENCE_INTAKE_SCHEMA_VERSION,
)
from broker_reports_gate1.gate5_human_gap_closure import (
    GATE5_GAP_REQUEST_SCHEMA_VERSION,
    GATE5_HUMAN_FACT_SCOPE_SCHEMA_VERSION,
    GATE5_LEGACY_USER_CASE_FACT_SCHEMA_VERSION,
    GATE5_USER_CASE_FACT_SCHEMA_VERSION,
    Gate5HumanGapClosureError,
    Gate5HumanGapClosureRuntimeFactory,
)
from broker_reports_gate1.gate5_residency_evidence import (
    GATE5_RESIDENCY_EVIDENCE_PROPOSAL_SCHEMA_VERSION,
    Gate5ResidencyEvidenceRuntimeFactory,
)
from broker_reports_gate1 import gate5_human_gap_closure as human_module

import test_broker_reports_gate4_sql_materialization as gate4_fixtures
import test_g578_source_has_it_owner_routing as routing_fixtures


SYNTHETIC_TAXPAYER_A = "synthetic-taxpayer-a"
SYNTHETIC_TAXPAYER_B = "synthetic-taxpayer-b"


def test_all_current_human_fact_kinds_are_owner_published_and_deterministic(
    tmp_path: Path,
) -> None:
    runtime, context = _runtime(tmp_path)
    published = runtime.publish_requests(**_plan_inputs(context))
    all_requests = [
        *published["required_actions"],
        *published["advisory_actions"],
        *published["deferred_actions"],
    ]
    assert len({item["semantic_request_key"] for item in all_requests}) == len(
        all_requests
    )

    user_requests = {
        item["fact_key"]: item
        for item in [
            *published["required_actions"],
            *published["deferred_actions"],
        ]
        if item["closure_type"] == "USER_FACT"
    }
    assert set(user_requests) == {
        "taxpayer_identity_confirmed",
        "filing_instance_identity",
        "signer_and_representation",
        "budget_disposition",
        "residency_evidence",
        "declaration_date",
        "ordinary_trade_declaration_zero_scope_confirmed",
    }
    assert all(
        item["schema_version"] == GATE5_GAP_REQUEST_SCHEMA_VERSION
        and item["scope_binding"]["schema_version"]
        == GATE5_HUMAN_FACT_SCOPE_SCHEMA_VERSION
        for item in user_requests.values()
    )
    assert SYNTHETIC_TAXPAYER_A not in {context.user_id, context.case_id}
    facts = []
    for fact_key, request in sorted(user_requests.items()):
        first = runtime.normalize_answer(
            request=request,
            answer=_answer(fact_key),
            context=context,
        )["typed_user_case_fact"]
        second = runtime.normalize_answer(
            request=request,
            answer=_answer(fact_key),
            context=context,
        )["typed_user_case_fact"]
        assert first == second
        assert first["schema_version"] == GATE5_USER_CASE_FACT_SCHEMA_VERSION
        assert first["scope_binding"] == request["scope_binding"]
        assert first["request_binding"] == {
            "request_ref": request["request_ref"],
            "request_id": request["request_id"],
            "request_sha256": request["request_sha256"],
            "request_publication_ref": request[
                "request_publication_ref"
            ],
        }
        facts.append(first)

    assert runtime.validate_user_case_facts(
        facts,
        context=context,
        taxpayer_scope_ref=SYNTHETIC_TAXPAYER_A,
        tax_period="2025",
    ) == sorted(facts, key=lambda item: item["fact_key"])
    assert runtime.current_user_case_facts(
        context=context,
        taxpayer_scope_ref=SYNTHETIC_TAXPAYER_A,
        tax_period="2025",
    ) == sorted(facts, key=lambda item: item["fact_key"])
    assert published["metrics"]["provider_calls"] == 0


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("foreign_user", "gate5_user_case_fact_owner_binding_invalid"),
        ("foreign_case", "gate5_user_case_fact_owner_binding_invalid"),
        ("foreign_workspace", "gate5_user_case_fact_owner_binding_invalid"),
        ("foreign_taxpayer", "gate5_user_case_fact_owner_binding_invalid"),
        ("foreign_period", "gate5_user_case_fact_owner_binding_invalid"),
    ],
)
def test_foreign_identity_dimensions_fail_closed(
    tmp_path: Path, mutation: str, expected_code: str
) -> None:
    runtime, context = _runtime(tmp_path)
    fact = _taxpayer_fact(runtime, context)
    replay_context = context
    taxpayer = SYNTHETIC_TAXPAYER_A
    period = "2025"
    if mutation == "foreign_user":
        replay_context = replace(context, user_id="synthetic-user-b")
    elif mutation == "foreign_case":
        replay_context = replace(context, case_id="synthetic-case-b")
    elif mutation == "foreign_workspace":
        replay_context = replace(context, workspace_model_id="synthetic-workspace-b")
    elif mutation == "foreign_taxpayer":
        taxpayer = SYNTHETIC_TAXPAYER_B
    else:
        period = "2024"

    with pytest.raises(Gate5HumanGapClosureError) as error:
        runtime.validate_user_case_facts(
            [fact],
            context=replay_context,
            taxpayer_scope_ref=taxpayer,
            tax_period=period,
        )
    assert error.value.code == expected_code


def test_fact_replays_across_run_but_not_across_semantic_scope(tmp_path: Path) -> None:
    runtime, context = _runtime(tmp_path)
    fact = _taxpayer_fact(runtime, context)
    later_run = replace(context, normalization_run_id="synthetic-run-b")

    assert runtime.validate_user_case_facts(
        [fact],
        context=later_run,
        taxpayer_scope_ref=SYNTHETIC_TAXPAYER_A,
        tax_period="2025",
    ) == [fact]
    assert "normalization_run_id" not in fact["scope_binding"]
    assert "workspace_model_id" not in fact["scope_binding"]


def test_two_synthetic_taxpayer_scopes_in_one_case_remain_distinct(
    tmp_path: Path,
) -> None:
    runtime, context = _runtime(tmp_path)
    plan_a = runtime.publish_requests(
        **_plan_inputs(context, taxpayer_scope_ref=SYNTHETIC_TAXPAYER_A)
    )
    plan_b = runtime.publish_requests(
        **_plan_inputs(context, taxpayer_scope_ref=SYNTHETIC_TAXPAYER_B)
    )
    fact_a = runtime.normalize_answer(
        request=_request(plan_a, "taxpayer_identity_confirmed"),
        answer={"kind": "confirmation", "value": True},
        context=context,
    )["typed_user_case_fact"]
    fact_b = runtime.normalize_answer(
        request=_request(plan_b, "taxpayer_identity_confirmed"),
        answer={"kind": "confirmation", "value": True},
        context=context,
    )["typed_user_case_fact"]

    assert fact_a["scope_binding"]["taxpayer_scope_ref"] == SYNTHETIC_TAXPAYER_A
    assert fact_b["scope_binding"]["taxpayer_scope_ref"] == SYNTHETIC_TAXPAYER_B
    assert fact_a["user_case_fact_ref"] != fact_b["user_case_fact_ref"]
    for fact, foreign_taxpayer in (
        (fact_a, SYNTHETIC_TAXPAYER_B),
        (fact_b, SYNTHETIC_TAXPAYER_A),
    ):
        with pytest.raises(Gate5HumanGapClosureError) as foreign:
            runtime.validate_user_case_facts(
                [fact],
                context=context,
                taxpayer_scope_ref=foreign_taxpayer,
                tax_period="2025",
            )
        assert foreign.value.code == "gate5_user_case_fact_owner_binding_invalid"


def test_resealed_foreign_fact_and_request_mix_is_rejected(tmp_path: Path) -> None:
    runtime, context_a = _runtime(tmp_path)
    fact_a = _taxpayer_fact(runtime, context_a)
    context_b = replace(
        context_a,
        user_id="synthetic-user-b",
        case_id="synthetic-case-b",
        normalization_run_id="synthetic-run-b",
    )
    published_b = runtime.publish_requests(**_plan_inputs(context_b))
    request_b = _request(published_b, "taxpayer_identity_confirmed")

    hybrid = copy.deepcopy(fact_a)
    hybrid["scope_binding"] = copy.deepcopy(request_b["scope_binding"])
    hybrid["request_binding"] = {
        "request_ref": request_b["request_ref"],
        "request_id": request_b["request_id"],
        "request_sha256": request_b["request_sha256"],
        "request_publication_ref": request_b[
            "request_publication_ref"
        ],
    }
    _reseal_fact(hybrid)

    with pytest.raises(Gate5HumanGapClosureError) as error:
        runtime.validate_user_case_facts(
            [hybrid],
            context=context_b,
            taxpayer_scope_ref=SYNTHETIC_TAXPAYER_B,
            tax_period="2025",
        )
    assert error.value.code == "gate5_user_case_fact_owner_binding_invalid"


def test_changed_and_stale_requests_fail_before_fact_publication(
    tmp_path: Path,
) -> None:
    runtime, context = _runtime(tmp_path)
    first = runtime.publish_requests(**_plan_inputs(context))
    old_request = _request(first, "taxpayer_identity_confirmed")
    old_fact = runtime.normalize_answer(
        request=old_request,
        answer={"kind": "confirmation", "value": True},
        context=context,
    )["typed_user_case_fact"]

    changed = copy.deepcopy(old_request)
    changed["question"] = "synthetic attacker changed the question"
    _reseal_request(changed)
    with pytest.raises(Gate5HumanGapClosureError) as changed_error:
        runtime.normalize_answer(
            request=changed,
            answer={"kind": "confirmation", "value": True},
            context=context,
        )
    assert changed_error.value.code == "gate5_gap_request_owner_binding_invalid"

    caller_lane = copy.deepcopy(old_request)
    caller_lane["semantic_request_key"] = "human_fact:caller_selected_lane"
    _reseal_request(caller_lane)
    with pytest.raises(Gate5HumanGapClosureError) as caller_lane_error:
        runtime.normalize_answer(
            request=caller_lane,
            answer={"kind": "confirmation", "value": True},
            context=context,
        )
    assert caller_lane_error.value.code == "gate5_gap_request_owner_binding_invalid"

    inputs = _plan_inputs(context)
    inputs["intake"]["metadata_facts"] = [
        {"fact_type": "PARTY_NAME", "fact_id": "synthetic-party-fact"}
    ]
    latest = runtime.publish_requests(**inputs)
    changed_request = _request(latest, "taxpayer_identity_confirmed")
    assert changed_request != old_request
    assert changed_request["semantic_request_key"] == old_request[
        "semantic_request_key"
    ]
    changed_fact = runtime.normalize_answer(
        request=changed_request,
        answer={"kind": "confirmation", "value": True},
        context=context,
    )["typed_user_case_fact"]
    with pytest.raises(Gate5HumanGapClosureError) as stale_error:
        runtime.normalize_answer(
            request=old_request,
            answer={"kind": "confirmation", "value": True},
            context=context,
        )
    assert stale_error.value.code == "gate5_gap_request_stale"
    with pytest.raises(Gate5HumanGapClosureError) as stale_fact_error:
        runtime.validate_user_case_facts(
            [old_fact],
            context=context,
            taxpayer_scope_ref=SYNTHETIC_TAXPAYER_A,
            tax_period="2025",
        )
    assert stale_fact_error.value.code == "gate5_gap_request_stale"

    restored = runtime.publish_requests(**_plan_inputs(context))
    restored_request = _request(restored, "taxpayer_identity_confirmed")
    assert restored_request["request_ref"] == old_request["request_ref"]
    assert (
        restored_request["request_publication_ref"]
        != old_request["request_publication_ref"]
    )
    restored_fact = runtime.normalize_answer(
        request=restored_request,
        answer={"kind": "confirmation", "value": True},
        context=context,
    )["typed_user_case_fact"]
    assert restored_fact["request_binding"]["request_publication_ref"] == (
        restored_request["request_publication_ref"]
    )
    with pytest.raises(Gate5HumanGapClosureError) as changed_stale:
        runtime.normalize_answer(
            request=changed_request,
            answer={"kind": "confirmation", "value": True},
            context=context,
        )
    assert changed_stale.value.code == "gate5_gap_request_stale"
    for stale_fact in (old_fact, changed_fact):
        with pytest.raises(Gate5HumanGapClosureError) as stale_after_restore:
            runtime.validate_user_case_facts(
                [stale_fact],
                context=context,
                taxpayer_scope_ref=SYNTHETIC_TAXPAYER_A,
                tax_period="2025",
            )
        assert stale_after_restore.value.code == "gate5_gap_request_stale"

    repeated = runtime.publish_requests(**_plan_inputs(context))
    assert _request(repeated, "taxpayer_identity_confirmed") == restored_request
    later_run = replace(context, normalization_run_id="synthetic-run-later")
    cross_run = runtime.publish_requests(**_plan_inputs(later_run))
    assert _request(cross_run, "taxpayer_identity_confirmed") == restored_request
    current_selector = inspect.getsource(runtime._current_request_publication)
    assert "created_at" not in current_selector
    assert "sorted(" not in current_selector
    assert "max(" not in current_selector


def test_budget_state_transitions_share_one_lane_and_stale_old_artifacts(
    tmp_path: Path,
) -> None:
    runtime, context = _runtime(tmp_path)
    blocked_review = Gate5ClientEvidenceReviewRuntime(source_runtime=None).review(
        source_assembly=routing_fixtures._source_assembly(
            routing_fixtures._blocker(
                "gate5_source_fact_direct_expense_missing"
            )
        )
    )

    deferred_plan = runtime.publish_requests(
        **_plan_inputs(context, client_review=blocked_review)
    )
    deferred = _request(deferred_plan, "budget_disposition")
    deferred_fact = runtime.normalize_answer(
        request=deferred,
        answer={"kind": "code", "value": "PAYMENT"},
        context=context,
    )["typed_user_case_fact"]
    assert deferred["kind"] == "DEFERRED"
    assert deferred["semantic_request_key"] == "human_fact:budget_disposition"

    required_plan = runtime.publish_requests(**_plan_inputs(context))
    required = _request(required_plan, "budget_disposition")
    assert required["kind"] == "REQUIRED"
    assert required["semantic_request_key"] == deferred["semantic_request_key"]
    assert required["request_publication_ref"] != deferred[
        "request_publication_ref"
    ]
    _assert_answer_error(
        runtime,
        request=deferred,
        context=context,
        answer={"kind": "code", "value": "PAYMENT"},
        expected="gate5_gap_request_stale",
    )
    _assert_fact_stale(runtime, deferred_fact, context=context)
    required_fact = runtime.normalize_answer(
        request=required,
        answer={"kind": "code", "value": "REFUND"},
        context=context,
    )["typed_user_case_fact"]

    later_run = replace(context, normalization_run_id="synthetic-run-later")
    deferred_again_plan = runtime.publish_requests(
        **_plan_inputs(later_run, client_review=blocked_review)
    )
    deferred_again = _request(deferred_again_plan, "budget_disposition")
    assert deferred_again["kind"] == "DEFERRED"
    assert deferred_again["request_ref"] == deferred["request_ref"]
    assert deferred_again["semantic_request_key"] == required[
        "semantic_request_key"
    ]
    assert deferred_again["request_publication_ref"] not in {
        deferred["request_publication_ref"],
        required["request_publication_ref"],
    }
    _assert_answer_error(
        runtime,
        request=required,
        context=later_run,
        answer={"kind": "code", "value": "REFUND"},
        expected="gate5_gap_request_stale",
    )
    _assert_fact_stale(runtime, required_fact, context=later_run)
    result = runtime.normalize_answer(
        request=deferred_again,
        answer={"kind": "code", "value": "REDUCTION"},
        context=later_run,
    )
    assert result["status"] == "TYPED_USER_CASE_FACT_READY"


def test_concurrent_internal_requests_keep_distinct_owner_semantics(
    tmp_path: Path,
) -> None:
    runtime, context = _runtime(tmp_path)
    role_blocker = routing_fixtures._blocker(
        "gate5_source_fact_required_role_missing"
    )
    decimal_blocker = routing_fixtures._blocker(
        "gate5_source_fact_decimal_invalid"
    )
    first_plan = runtime.publish_requests(
        **_plan_inputs(
            context,
            client_review=_review_for_blockers(role_blocker, decimal_blocker),
        )
    )
    first = _internal_requests_by_route(first_plan)
    assert set(first) == {
        "UPSTREAM_SOURCE_FACT_PRODUCTION_REVIEW",
        "NORMALIZATION_OWNER_REVIEW",
    }
    assert first["UPSTREAM_SOURCE_FACT_PRODUCTION_REVIEW"][
        "semantic_request_key"
    ] != first["NORMALIZATION_OWNER_REVIEW"]["semantic_request_key"]
    assert first["UPSTREAM_SOURCE_FACT_PRODUCTION_REVIEW"][
        "request_publication_ref"
    ] != first["NORMALIZATION_OWNER_REVIEW"]["request_publication_ref"]
    _assert_all_internal_requests_current(runtime, first_plan, context=context)

    changed_role = copy.deepcopy(role_blocker)
    changed_role["fact_id"] = "g4fact_control_changed"
    changed_role["evidence_searched"] = {
        "document_id": "document-control-changed",
        "source_fact_id": "g4fact_control_changed",
    }
    changed_role["why_insufficient"] = "changed owner display explanation"
    changed_role["closing_evidence"] = "changed exact owner evidence state"
    second_plan = runtime.publish_requests(
        **_plan_inputs(
            context,
            client_review=_review_for_blockers(changed_role, decimal_blocker),
        )
    )
    second = _internal_requests_by_route(second_plan)
    old_role = first["UPSTREAM_SOURCE_FACT_PRODUCTION_REVIEW"]
    new_role = second["UPSTREAM_SOURCE_FACT_PRODUCTION_REVIEW"]
    old_decimal = first["NORMALIZATION_OWNER_REVIEW"]
    new_decimal = second["NORMALIZATION_OWNER_REVIEW"]
    assert new_role["request_ref"] != old_role["request_ref"]
    assert new_role["semantic_request_key"] == old_role["semantic_request_key"]
    assert new_role["request_publication_ref"] != old_role[
        "request_publication_ref"
    ]
    assert new_decimal == old_decimal
    _assert_answer_error(
        runtime,
        request=old_role,
        context=context,
        answer={"kind": "code", "value": "owner-review"},
        expected="gate5_gap_request_stale",
    )
    _assert_all_internal_requests_current(runtime, second_plan, context=context)


def test_additional_document_evidence_change_supersedes_same_lane(
    tmp_path: Path,
) -> None:
    runtime, context = _runtime(tmp_path)
    first_blocker = routing_fixtures._blocker(
        "gate5_source_fact_direct_expense_missing"
    )
    first_plan = runtime.publish_requests(
        **_plan_inputs(
            context,
            client_review=_review_for_blockers(first_blocker),
        )
    )
    old_request = next(
        item
        for item in first_plan["required_actions"]
        if item["closure_type"] == "ADDITIONAL_DOCUMENT"
    )

    changed_blocker = copy.deepcopy(first_blocker)
    changed_blocker["fact_id"] = "g4fact_changed"
    changed_blocker["evidence_searched"] = {
        "document_id": "document-changed",
        "source_fact_id": "g4fact_changed",
    }
    changed_blocker["why_insufficient"] = "changed evidence-state explanation"
    changed_blocker["closing_evidence"] = "changed exact missing document"
    second_plan = runtime.publish_requests(
        **_plan_inputs(
            context,
            client_review=_review_for_blockers(changed_blocker),
        )
    )
    new_request = next(
        item
        for item in second_plan["required_actions"]
        if item["closure_type"] == "ADDITIONAL_DOCUMENT"
    )
    assert new_request["semantic_request_key"] == old_request[
        "semantic_request_key"
    ]
    assert new_request["request_publication_ref"] != old_request[
        "request_publication_ref"
    ]
    _assert_answer_error(
        runtime,
        request=old_request,
        context=context,
        answer={"kind": "document_submission", "value": True},
        expected="gate5_gap_request_stale",
    )
    assert runtime.normalize_answer(
        request=new_request,
        answer={"kind": "document_submission", "value": True},
        context=context,
    )["status"] == "NORMALIZATION_REQUIRED"


def test_duplicate_conflict_missing_binding_and_v0_downgrade_fail_closed(
    tmp_path: Path,
) -> None:
    runtime, context = _runtime(tmp_path)
    published = runtime.publish_requests(**_plan_inputs(context))
    request = _request(published, "taxpayer_identity_confirmed")
    yes = runtime.normalize_answer(
        request=request,
        answer={"kind": "confirmation", "value": True},
        context=context,
    )["typed_user_case_fact"]
    conflict = runtime.normalize_answer(
        request=request,
        answer={"kind": "confirmation", "value": False},
        context=context,
    )
    assert conflict["status"] == "USER_CASE_FACT_CONFLICT"
    no = conflict["typed_user_case_fact"]

    for facts in ([yes], [no], [yes, no], [no, yes]):
        with pytest.raises(Gate5HumanGapClosureError) as duplicate:
            runtime.validate_user_case_facts(
                facts,
                context=context,
                taxpayer_scope_ref=SYNTHETIC_TAXPAYER_A,
                tax_period="2025",
            )
        assert duplicate.value.code == "gate5_user_case_fact_conflict"

    later_run = replace(context, normalization_run_id="synthetic-run-later")
    for fact in (yes, no):
        with pytest.raises(Gate5HumanGapClosureError) as later_conflict:
            runtime.validate_user_case_facts(
                [fact],
                context=later_run,
                taxpayer_scope_ref=SYNTHETIC_TAXPAYER_A,
                tax_period="2025",
            )
        assert later_conflict.value.code == "gate5_user_case_fact_conflict"

    repeated = runtime.normalize_answer(
        request=request,
        answer={"kind": "confirmation", "value": False},
        context=context,
    )
    assert repeated == conflict

    missing = copy.deepcopy(yes)
    del missing["scope_binding"]
    legacy = {
        "schema_version": GATE5_LEGACY_USER_CASE_FACT_SCHEMA_VERSION,
        "fact_key": "taxpayer_identity_confirmed",
        "value": {"kind": "confirmation", "value": True},
        "provenance": {"source_kind": "authenticated_user_case_fact"},
    }
    for invalid in (missing, legacy):
        with pytest.raises(Gate5HumanGapClosureError) as invalid_error:
            runtime.validate_user_case_facts(
                [invalid],
                context=context,
                taxpayer_scope_ref=SYNTHETIC_TAXPAYER_A,
                tax_period="2025",
            )
        assert invalid_error.value.code == "gate5_user_case_facts_invalid"


def test_human_cannot_replace_fact_key_or_supply_tax_or_source_authority(
    tmp_path: Path,
) -> None:
    runtime, context = _runtime(tmp_path)
    published = runtime.publish_requests(**_plan_inputs(context))
    identity_request = _request(published, "taxpayer_identity_confirmed")
    with pytest.raises(Gate5HumanGapClosureError) as replaced_key:
        runtime.normalize_answer(
            request=identity_request,
            answer={
                "kind": "confirmation",
                "value": True,
                "fact_key": "budget_disposition",
            },
            context=context,
        )
    assert replaced_key.value.code == "gate5_gap_answer_invalid"

    residency_request = _request(published, "residency_evidence")
    with pytest.raises(Gate5HumanGapClosureError) as conclusion:
        runtime.normalize_answer(
            request=residency_request,
            answer={"kind": "code", "value": "resident_individual"},
            context=context,
        )
    assert conclusion.value.code == "gate5_gap_answer_kind_invalid"

    review = Gate5ClientEvidenceReviewRuntime(source_runtime=None).review(
        source_assembly=routing_fixtures._source_assembly(
            routing_fixtures._blocker("gate5_source_fact_direct_expense_missing")
        )
    )
    document_plan = runtime.publish_requests(
        **_plan_inputs(context, client_review=review)
    )
    document_request = next(
        item
        for item in document_plan["required_actions"]
        if item["closure_type"] == "ADDITIONAL_DOCUMENT"
    )
    routed = runtime.normalize_answer(
        request=document_request,
        answer={"kind": "document_submission", "value": True},
        context=context,
    )
    assert routed["typed_user_case_fact"] is None
    assert routed["status"] == "NORMALIZATION_REQUIRED"

    external_review = Gate5ClientEvidenceReviewRuntime(source_runtime=None).review(
        source_assembly=routing_fixtures._source_assembly(
            routing_fixtures._blocker("gate5_source_fact_currency_invalid")
        )
    )
    external_plan = runtime.publish_requests(
        **_plan_inputs(context, client_review=external_review)
    )
    external_request = next(
        item
        for item in external_plan["required_actions"]
        if item["closure_type"] == "EXTERNAL_AUTHORITY"
    )
    with pytest.raises(Gate5HumanGapClosureError) as external:
        runtime.normalize_answer(
            request=external_request,
            answer={"kind": "code", "value": "RUB"},
            context=context,
        )
    assert external.value.code == "gate5_gap_answer_not_user_fact"


@pytest.mark.parametrize(
    ("kind", "value", "expected_code"),
    [
        ("code", "INITIAL, ИФНС 2367", "gate5_gap_answer_value_invalid"),
        ("text", "INITIAL", "gate5_gap_answer_kind_invalid"),
        ("code", "KBK 18210102010011000110", "gate5_gap_answer_value_invalid"),
        ("code", "OKTMO 45382000", "gate5_gap_answer_value_invalid"),
        ("code", "resident_individual", "gate5_gap_answer_value_invalid"),
        ("code", "RUSSIAN_SOURCE", "gate5_gap_answer_value_invalid"),
        ("code", "DEDUCTIBLE", "gate5_gap_answer_value_invalid"),
        ("code", "SETTLED", "gate5_gap_answer_value_invalid"),
    ],
)
def test_filing_election_closed_code_rejects_authority_smuggling(
    tmp_path: Path,
    kind: str,
    value: str,
    expected_code: str,
) -> None:
    runtime, context = _runtime(tmp_path)
    published = runtime.publish_requests(**_plan_inputs(context))
    filing_request = _request(published, "filing_instance_identity")
    assert filing_request["answer_contract"] == {
        "kind": "code",
        "allowed": ["INITIAL", "CORRECTION"],
    }
    assert "destination" not in filing_request["question"].lower()

    with pytest.raises(Gate5HumanGapClosureError) as rejected:
        runtime.normalize_answer(
            request=filing_request,
            answer={"kind": kind, "value": value},
            context=context,
        )
    assert rejected.value.code == expected_code

    destination_request = next(
        item
        for item in published["internal_owner_required_actions"]
        if item["closure_type"] == "EXTERNAL_AUTHORITY"
        and item["demand_refs"] == ["obl_filing_instance_identity"]
    )
    with pytest.raises(Gate5HumanGapClosureError) as external:
        runtime.normalize_answer(
            request=destination_request,
            answer={"kind": "code", "value": "2367"},
            context=context,
        )
    assert external.value.code == "gate5_gap_answer_not_user_fact"


@pytest.mark.parametrize("election", ["INITIAL", "CORRECTION"])
def test_closed_filing_elections_are_accepted(
    tmp_path: Path,
    election: str,
) -> None:
    runtime, context = _runtime(tmp_path)
    filing_request = _request(
        runtime.publish_requests(**_plan_inputs(context)),
        "filing_instance_identity",
    )
    result = runtime.normalize_answer(
        request=filing_request,
        answer={"kind": "code", "value": election},
        context=context,
    )
    assert result["status"] == "TYPED_USER_CASE_FACT_READY"
    assert result["typed_user_case_fact"]["value"] == {
        "kind": "code",
        "value": election,
    }


def test_human_boundary_has_no_provider_or_neighbor_implementation_path() -> None:
    source = inspect.getsource(human_module)
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    imported |= {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    for forbidden in (
        "requests",
        "httpx",
        "model_client",
        "chat_completion",
        "ordinary_trade_tax_model_bridge",
        "active_category_declaration_assembly",
    ):
        assert not any(forbidden in item for item in imported)
    lane_source = inspect.getsource(human_module._request_lane_sha256)
    assert "semantic_request_key" in lane_source
    for mutable_field in (
        'validated["kind"]',
        'validated["closure_type"]',
        'validated["fact_key"]',
        'validated["demand_refs"]',
        'validated["subject"]',
    ):
        assert mutable_field not in lane_source


def _runtime(tmp_path: Path):
    store, base = gate4_fixtures._store_context(tmp_path)
    context = ArtifactAccessContext(
        user_id="synthetic-user-a",
        normalization_run_id="synthetic-run-a",
        case_id="synthetic-case-a",
        workspace_model_id="synthetic-workspace-a",
        allow_private=True,
    )
    runtime = Gate5HumanGapClosureRuntimeFactory.create(
        store=store,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
    )
    assert base.allow_private is True
    return runtime, context


def _review_for_blockers(*blockers: dict) -> dict:
    source = routing_fixtures._source_assembly(copy.deepcopy(blockers[0]))
    source["blockers"] = [copy.deepcopy(item) for item in blockers]
    return Gate5ClientEvidenceReviewRuntime(source_runtime=None).review(
        source_assembly=source
    )


def _internal_requests_by_route(plan: dict) -> dict[str, dict]:
    return {
        item["routing"]["route"]: item
        for item in plan["internal_owner_required_actions"]
        if "routing" in item
    }


def _assert_all_internal_requests_current(runtime, plan: dict, *, context) -> None:
    for request in plan["internal_owner_required_actions"]:
        with pytest.raises(Gate5HumanGapClosureError) as current:
            runtime.normalize_answer(
                request=request,
                answer={"kind": "code", "value": "owner-review"},
                context=context,
            )
        assert current.value.code == "gate5_gap_answer_not_user_fact"


def _assert_answer_error(
    runtime,
    *,
    request: dict,
    context,
    answer: dict,
    expected: str,
) -> None:
    with pytest.raises(Gate5HumanGapClosureError) as error:
        runtime.normalize_answer(
            request=request,
            answer=answer,
            context=context,
        )
    assert error.value.code == expected


def _assert_fact_stale(runtime, fact: dict, *, context) -> None:
    with pytest.raises(Gate5HumanGapClosureError) as stale:
        runtime.validate_user_case_facts(
            [fact],
            context=context,
            taxpayer_scope_ref=SYNTHETIC_TAXPAYER_A,
            tax_period="2025",
        )
    assert stale.value.code == "gate5_gap_request_stale"


def _plan_inputs(
    context: ArtifactAccessContext,
    *,
    taxpayer_scope_ref: str | None = None,
    client_review: dict | None = None,
) -> dict:
    return {
        "intake": {
            "schema_version": GATE5_EVIDENCE_INTAKE_SCHEMA_VERSION,
            "metadata_facts": [],
        },
        "scope_activation": {
            "schema_version": GATE5_DECLARATION_SCOPE_ACTIVATION_SCHEMA_VERSION,
            "active_demands": [
                {"demand": "obl_taxpayer_identity_and_period_status"},
                {"demand": "obl_filing_instance_identity"},
                {"demand": "obl_signer_and_representation_authority"},
                {"demand": "obl_declaration_budget_disposition"},
            ],
        },
        "client_review": client_review
        or {
            "schema_version": GATE5_CLIENT_EVIDENCE_REVIEW_SCHEMA_VERSION,
            "required_blockers": [],
            "advisory_findings": [],
        },
        "user_case_facts": [],
        "residency_classification": (
            Gate5ResidencyEvidenceRuntimeFactory.create().classify(evidence=None)
        ),
        "context": context,
        "taxpayer_scope_ref": (
            taxpayer_scope_ref or SYNTHETIC_TAXPAYER_A
        ),
        "tax_period": "2025",
    }


def _taxpayer_fact(runtime, context):
    published = runtime.publish_requests(**_plan_inputs(context))
    return runtime.normalize_answer(
        request=_request(published, "taxpayer_identity_confirmed"),
        answer={"kind": "confirmation", "value": True},
        context=context,
    )["typed_user_case_fact"]


def _request(plan: dict, fact_key: str) -> dict:
    return next(
        item
        for item in [*plan["required_actions"], *plan["deferred_actions"]]
        if item.get("fact_key") == fact_key
    )


def _answer(fact_key: str) -> dict:
    if fact_key == "taxpayer_identity_confirmed":
        return {"kind": "confirmation", "value": True}
    if fact_key == "filing_instance_identity":
        return {"kind": "code", "value": "INITIAL"}
    if fact_key == "signer_and_representation":
        return {"kind": "code", "value": "SELF"}
    if fact_key == "budget_disposition":
        return {"kind": "code", "value": "PAYMENT"}
    if fact_key == "declaration_date":
        return {"kind": "text", "value": "2026-08-23"}
    if fact_key == "ordinary_trade_declaration_zero_scope_confirmed":
        return {"kind": "confirmation", "value": True}
    return {
        "kind": "residency_evidence",
        "value": {
            "human_answer": (
                "Synthetic fixture: present 2025-01-01 to 2025-07-02; "
                "absent 2025-07-03 to 2025-12-31; no other reasons."
            ),
            "proposal": {
                "schema_version": GATE5_RESIDENCY_EVIDENCE_PROPOSAL_SCHEMA_VERSION,
                "tax_period": "2025",
                "window_start": "2025-01-01",
                "window_end": "2025-12-31",
                "presence_intervals": [
                    {"start_date": "2025-01-01", "end_date": "2025-07-02"}
                ],
                "absence_intervals": [
                    {"start_date": "2025-07-03", "end_date": "2025-12-31"}
                ],
                "absence_reason_evidence": [],
                "all_absence_reasons_reported": True,
                "evidence_refs": ["synthetic-human-answer"],
            },
        },
    }


def _reseal_request(request: dict) -> None:
    base = {
        key: copy.deepcopy(value)
        for key, value in request.items()
        if key
        not in {
            "request_ref",
            "request_id",
            "request_sha256",
            "request_publication_ref",
        }
    }
    request_sha256 = _sha(base)
    request["request_id"] = "g5request_" + request_sha256[:32]
    request["request_sha256"] = request_sha256
    with_identity = {
        key: copy.deepcopy(value)
        for key, value in request.items()
        if key not in {"request_ref", "request_publication_ref"}
    }
    request["request_ref"] = (
        "art_" + _sha({"kind": "gap_request", "request": with_identity})[:32]
    )


def _reseal_fact(fact: dict) -> None:
    material = {
        key: copy.deepcopy(value)
        for key, value in fact.items()
        if key not in {"user_case_fact_ref", "fact_sha256"}
    }
    fact["fact_sha256"] = _sha(material)
    fact["user_case_fact_ref"] = (
        "art_"
        + _sha({"kind": "user_case_fact", "fact_sha256": fact["fact_sha256"]})[:32]
    )


def _sha(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
