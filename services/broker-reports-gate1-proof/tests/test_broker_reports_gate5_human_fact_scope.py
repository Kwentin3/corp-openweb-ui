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
    gate5_case_taxpayer_scope_ref,
)
from broker_reports_gate1.gate5_residency_evidence import (
    GATE5_RESIDENCY_EVIDENCE_PROPOSAL_SCHEMA_VERSION,
    Gate5ResidencyEvidenceRuntimeFactory,
)
from broker_reports_gate1 import gate5_human_gap_closure as human_module

import test_broker_reports_gate4_sql_materialization as gate4_fixtures
import test_g578_source_has_it_owner_routing as routing_fixtures


def test_all_current_human_fact_kinds_are_owner_published_and_deterministic(
    tmp_path: Path,
) -> None:
    runtime, context = _runtime(tmp_path)
    published = runtime.publish_requests(**_plan_inputs(context))

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
    }
    assert all(
        item["schema_version"] == GATE5_GAP_REQUEST_SCHEMA_VERSION
        and item["scope_binding"]["schema_version"]
        == GATE5_HUMAN_FACT_SCOPE_SCHEMA_VERSION
        for item in user_requests.values()
    )
    derived_taxpayer = gate5_case_taxpayer_scope_ref(context)
    assert derived_taxpayer not in {context.user_id, context.case_id}
    assert (
        gate5_case_taxpayer_scope_ref(
            replace(context, normalization_run_id="another-run")
        )
        == derived_taxpayer
    )
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
        }
        facts.append(first)

    assert runtime.validate_user_case_facts(
        facts,
        context=context,
        taxpayer_scope_ref=gate5_case_taxpayer_scope_ref(context),
        tax_period="2025",
    ) == sorted(facts, key=lambda item: item["fact_key"])
    assert published["metrics"]["provider_calls"] == 0


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("foreign_user", "gate5_user_case_fact_owner_binding_invalid"),
        ("foreign_case", "gate5_human_fact_scope_invalid"),
        ("foreign_workspace", "gate5_user_case_fact_owner_binding_invalid"),
        ("foreign_taxpayer", "gate5_human_fact_scope_invalid"),
        ("foreign_period", "gate5_user_case_fact_owner_binding_invalid"),
    ],
)
def test_foreign_identity_dimensions_fail_closed(
    tmp_path: Path, mutation: str, expected_code: str
) -> None:
    runtime, context = _runtime(tmp_path)
    fact = _taxpayer_fact(runtime, context)
    replay_context = context
    taxpayer = gate5_case_taxpayer_scope_ref(context)
    period = "2025"
    if mutation == "foreign_user":
        replay_context = replace(context, user_id="synthetic-user-b")
    elif mutation == "foreign_case":
        replay_context = replace(context, case_id="synthetic-case-b")
    elif mutation == "foreign_workspace":
        replay_context = replace(context, workspace_model_id="synthetic-workspace-b")
    elif mutation == "foreign_taxpayer":
        taxpayer = gate5_case_taxpayer_scope_ref(
            replace(context, case_id="synthetic-case-b")
        )
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
        taxpayer_scope_ref=gate5_case_taxpayer_scope_ref(later_run),
        tax_period="2025",
    ) == [fact]
    assert "normalization_run_id" not in fact["scope_binding"]
    assert "workspace_model_id" not in fact["scope_binding"]


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
    }
    _reseal_fact(hybrid)

    with pytest.raises(Gate5HumanGapClosureError) as error:
        runtime.validate_user_case_facts(
            [hybrid],
            context=context_b,
            taxpayer_scope_ref=gate5_case_taxpayer_scope_ref(context_b),
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

    inputs = _plan_inputs(context)
    inputs["intake"]["metadata_facts"] = [
        {"fact_type": "PARTY_NAME", "fact_id": "synthetic-party-fact"}
    ]
    latest = runtime.publish_requests(**inputs)
    assert _request(latest, "taxpayer_identity_confirmed") != old_request
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
            taxpayer_scope_ref=gate5_case_taxpayer_scope_ref(context),
            tax_period="2025",
        )
    assert stale_fact_error.value.code == "gate5_gap_request_stale"


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
    no = runtime.normalize_answer(
        request=request,
        answer={"kind": "confirmation", "value": False},
        context=context,
    )["typed_user_case_fact"]

    for facts in ([yes, no], [yes, yes]):
        with pytest.raises(Gate5HumanGapClosureError) as duplicate:
            runtime.validate_user_case_facts(
                facts,
                context=context,
                taxpayer_scope_ref=gate5_case_taxpayer_scope_ref(context),
                tax_period="2025",
            )
        assert duplicate.value.code == "gate5_user_case_fact_duplicate"

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
                taxpayer_scope_ref=gate5_case_taxpayer_scope_ref(context),
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
            taxpayer_scope_ref or gate5_case_taxpayer_scope_ref(context)
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
        return {"kind": "text", "value": "INITIAL"}
    if fact_key == "signer_and_representation":
        return {"kind": "code", "value": "SELF"}
    if fact_key == "budget_disposition":
        return {"kind": "code", "value": "PAYMENT"}
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
        if key not in {"request_ref", "request_id", "request_sha256"}
    }
    request_sha256 = _sha(base)
    request["request_id"] = "g5request_" + request_sha256[:32]
    request["request_sha256"] = request_sha256
    with_identity = {
        key: copy.deepcopy(value)
        for key, value in request.items()
        if key != "request_ref"
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
