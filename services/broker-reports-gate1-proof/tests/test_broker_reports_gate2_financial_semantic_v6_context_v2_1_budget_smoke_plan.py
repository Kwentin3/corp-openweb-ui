from __future__ import annotations

import copy
import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pytest

from broker_reports_gate1.gate2_economy_budget import (
    Gate2EconomyBudgetSessionFactory,
)
from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (
    sha256_json,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_context_linter import (
    Gate2FinancialSemanticV6ContextLinterFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_context_v2_1_budget_smoke_plan import (
    BUDGET_SMOKE_CASES,
    BUDGET_SMOKE_MAXIMUM_OUTPUT_TOKENS,
    BUDGET_SMOKE_MAXIMUM_PROVIDER_SUBMISSIONS,
    BUDGET_SMOKE_PROVIDER_MODEL_IDENTITIES,
    BUDGET_SMOKE_PROVIDER_MODELS,
    FACTORY_REQUIRED,
    FORBIDDEN,
    Gate2FinancialSemanticV6ContextV21BudgetSmokePlanError,
    Gate2FinancialSemanticV6ContextV21BudgetSmokePlanFactory,
    Gate2FinancialSemanticV6ContextV21BudgetSmokeSlotProjection,
    financial_semantic_v6_context_v2_1_budget_smoke_operation_identity,
    resolve_financial_semantic_v6_context_v2_1_budget_smoke_expected_answer,
    validate_financial_semantic_v6_context_v2_1_budget_smoke_plan,
)
from broker_reports_gate1.gate2_financial_semantic_v6_outcome_audit import (
    OUTCOME_AUDIT_INTEGRITY_SHA256,
    validate_financial_semantic_v6_outcome_audit,
)
from broker_reports_gate1.gate2_financial_semantic_v6_prompt import (
    V6_SEMANTIC_SYSTEM_PROMPT,
)
from broker_reports_gate1.gate2_financial_semantic_v6_qualification import (
    Gate2FinancialSemanticV6QualificationFixtureFactory,
)
from broker_reports_gate1.gate2_model_contracts import (
    gate2_provider_profile,
)
from broker_reports_gate1.gate2_model_requests import (
    FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)
from broker_reports_gate1.gate2_provider_adapters import (
    CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY,
    Gate2ProviderAdapterFactory,
)


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = (
    ROOT
    / "benchmarks"
    / "gate2_financial_semantic_v6_outcome_audit_v1"
    / "manifest.json"
)
HISTORICAL_PATH = (
    ROOT
    / "benchmarks"
    / "gate2_financial_semantic_v6"
    / "manifest.json"
)
BASE_PATH = (
    ROOT
    / "benchmarks"
    / "gate2_financial_successor_v2"
    / "manifest.json"
)
PACK_PATH = (
    ROOT
    / "semantic_packs"
    / "broker_reports_financial_semantic_pack.v1.json"
)
REASON_CATALOG_PATH = (
    ROOT
    / "managed_assets"
    / "decision_reasons"
    / "broker_reports_gate2_financial_decision_reason_catalog.v2.json"
)
REQUEST_PROFILE = (
    FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE
)
SNAPSHOT_KEY = b"context-v2-1-budget-smoke-plan-snapshot-key"
CONTINUATION_KEY = b"context-v2-1-budget-smoke-plan-continuation"


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


@pytest.fixture(scope="module")
def plan_inputs():
    audit_manifest = _read(AUDIT_PATH)
    historical_manifest = _read(HISTORICAL_PATH)
    base_manifest = _read(BASE_PATH)
    semantic_pack = _read(PACK_PATH)
    reason_catalog = _read(REASON_CATALOG_PATH)
    audit = validate_financial_semantic_v6_outcome_audit(
        manifest=audit_manifest,
        historical_manifest=historical_manifest,
        base_manifest=base_manifest,
        semantic_pack=semantic_pack,
        reason_catalog_v2=reason_catalog,
    )
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    fixture = Gate2FinancialSemanticV6QualificationFixtureFactory(
        registry=registry,
        snapshot_authority_key=SNAPSHOT_KEY,
        continuation_key=CONTINUATION_KEY,
    ).create(
        manifest=historical_manifest,
        base_manifest=base_manifest,
    )
    return {
        "audit": audit,
        "audit_manifest": audit_manifest,
        "fixture": fixture,
        "registry": registry,
    }


class _DeterministicProjector:
    def __init__(self, *, registry) -> None:
        self.registry = registry
        self.budget_session = (
            Gate2EconomyBudgetSessionFactory().create(
                request_profile=REQUEST_PROFILE,
            )
        )
        self.calls: list[tuple[str, str]] = []
        self.authorizations = {}
        self.projections: dict[
            tuple[str, str],
            Gate2FinancialSemanticV6ContextV21BudgetSmokeSlotProjection,
        ] = {}

    def __call__(
        self,
        *,
        case,
        provider_profile,
        exact_model_id,
        request_profile,
        parameters,
    ):
        response_profile = (
            case.choice_contract.context_v2_1_response_profile
        )
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "strict": True,
                "schema": response_profile.canonical_schema(),
            },
        }
        serialized_context = json.dumps(
            case.packet.context_v2_candidate.payload,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        sealed_request = (
            Gate2FinancialSemanticV6ContextLinterFactory(
                registry=self.registry
            ).create_context_v2_1(
                packet=case.packet,
                choice_contract=case.choice_contract,
                evidence_bundle=case.evidence_bundle,
                source_package=case.scope.source_package,
                compilation=case.compilation,
                system_message=V6_SEMANTIC_SYSTEM_PROMPT,
                serialized_context=serialized_context,
                response_format=response_format,
                mapping_receipt=(
                    case.packet.context_v2_mapping_receipt
                ),
            )
        )
        form_data = Gate2OpenWebUIRequestBuilder(
            request_profile=request_profile,
        ).build_from_sealed_context_v2_1(
            model_visible_request=sealed_request.model_visible_request,
            model_id=exact_model_id,
        )
        assert form_data["stream"] is False
        authorization = self.budget_session.prepare_call(
            form_data=form_data,
            model_id=exact_model_id,
            provider_profile_id=provider_profile.profile_id,
            operation_identity=(
                "broker-reports-goal12-preflight:"
                f"{provider_profile.profile_id}:{case.case_id}"
            ),
        )
        adapter = Gate2ProviderAdapterFactory(
            profile=provider_profile,
            capability_probe=True,
        ).create()
        prepared_request = (
            adapter.prepare_context_v2_1_budget_smoke_form_data(
            form_data=authorization.prepared_form_data,
            response_format=sealed_request.response_format,
            )
        )
        transport_contract = (
            adapter.context_v2_1_budget_smoke_transport_contract(
                transport_policy=(
                    CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY
                )
            )
        )
        projection = (
            Gate2FinancialSemanticV6ContextV21BudgetSmokeSlotProjection(
                request_profile=request_profile,
                sealed_request=sealed_request,
                prepared_request=prepared_request,
                transport_contract=transport_contract,
            )
        )
        key = (provider_profile.profile_id, case.case_id)
        self.calls.append(key)
        self.authorizations[key] = authorization
        self.projections[key] = projection
        return projection


def _factory(projector):
    return (
        Gate2FinancialSemanticV6ContextV21BudgetSmokePlanFactory(
            request_profile=REQUEST_PROFILE,
            slot_projector=projector,
        )
    )


def _build_plan(plan_inputs):
    projector = _DeterministicProjector(
        registry=plan_inputs["registry"]
    )
    plan = _factory(projector).create(
        fixture=plan_inputs["fixture"],
        outcome_audit_manifest=plan_inputs["audit_manifest"],
    )
    return plan, projector


def test_frozen_plan_pins_exact_three_by_four_ledger(
    plan_inputs,
) -> None:
    plan, projector = _build_plan(plan_inputs)
    safe = plan.to_safe_dict()
    expected_pairs = tuple(
        (provider_profile_id, case_id)
        for provider_profile_id, _model_id in BUDGET_SMOKE_PROVIDER_MODELS
        for case_id, _taxonomy_state in BUDGET_SMOKE_CASES
    )

    assert plan_inputs["audit"].integrity_sha256 == (
        OUTCOME_AUDIT_INTEGRITY_SHA256
    )
    assert tuple(projector.calls) == expected_pairs
    assert len(plan.slots) == BUDGET_SMOKE_MAXIMUM_PROVIDER_SUBMISSIONS
    assert len({item.slot_id for item in plan.slots}) == 12
    assert tuple(
        (item.provider_profile_id, item.case_id)
        for item in plan.slots
    ) == expected_pairs
    assert safe["provider_order"] == [
        "openai_gpt",
        "anthropic_claude",
        "google_gemini",
    ]
    assert safe["case_order"] == [
        "syn_successor_v2_unique_cash",
        "syn_successor_v2_no_registry_type",
        "syn_successor_v2_multiple_compatible",
        "syn_successor_v2_detail_vs_subtotal",
    ]
    assert [
        item["exact_model_id"]
        for item in safe["provider_model_parameter_ledger"]
    ] == [
        "gpt-5.4-nano-2026-03-17",
        "claude-haiku-4-5-20251001",
        "models/gemini-3.1-flash-lite",
    ]
    assert [
        (
            item["model_identity_kind"],
            item["immutable_model_id_proven"],
            item["model_identity_caveat"],
        )
        for item in safe["provider_model_parameter_ledger"]
    ] == [item[1:] for item in BUDGET_SMOKE_PROVIDER_MODEL_IDENTITIES]
    assert sum(
        not item.immutable_model_id_proven for item in plan.slots
    ) == 4
    assert all(
        item.provider_profile_id == "google_gemini"
        and item.model_identity_kind
        == "stable_selector_not_immutable"
        and item.model_identity_caveat
        == "provider_inventory_has_no_dated_immutable_google_model_id"
        for item in plan.slots
        if not item.immutable_model_id_proven
    )
    assert safe["execution_accounting"] == {
        "planned_slots_total": 12,
        "maximum_provider_submissions_total": 12,
        "provider_submissions_total": 0,
        "provider_responses_total": 0,
        "retry_total": 0,
        "repair_total": 0,
        "fallback_total": 0,
    }
    assert safe["transport_executed"] is False
    assert safe["active"] is False
    assert safe["production_admissions"] == []
    assert safe["integrity_hash"] == sha256_json(
        {
            key: value
            for key, value in safe.items()
            if key != "integrity_hash"
        }
    )
    assert all(
        item.parameters.maximum_output_tokens
        == BUDGET_SMOKE_MAXIMUM_OUTPUT_TOKENS
        and item.maximum_provider_submissions == 1
        and not any(
            (
                item.parameters.model_aliases_allowed,
                item.parameters.runtime_model_override_allowed,
                item.parameters.runtime_parameter_override_allowed,
                item.parameters.retry_allowed,
                item.parameters.repair_allowed,
                item.parameters.fallback_allowed,
            )
        )
        for item in plan.slots
    )


def test_plan_hashes_full_projected_requests_schemas_and_answers(
    plan_inputs,
) -> None:
    plan, projector = _build_plan(plan_inputs)
    audit_cases = {
        item["case_id"]: item
        for item in plan_inputs["audit_manifest"]["cases"]
    }
    fixture_cases = {
        item.case_id: item for item in plan_inputs["fixture"].semantic_cases
    }

    for slot in plan.slots:
        projection = projector.projections[
            (slot.provider_profile_id, slot.case_id)
        ]
        assert slot.sealed_request_hash == sha256_json(
            asdict(projection.sealed_request)
        )
        assert slot.model_visible_request_hash == (
            projection.sealed_request.sealed_request_receipt
            .model_visible_request_hash
        )
        assert slot.prepared_request_hash == sha256_json(
            asdict(projection.prepared_request)
        )
        authorization = projector.authorizations[
            (slot.provider_profile_id, slot.case_id)
        ]
        assert authorization.prepared_form_data["stream"] is False
        assert (
            projection.prepared_request
            .context_v2_1_budget_smoke_contract_is_bound(
                canonical_schema=(
                    fixture_cases[slot.case_id]
                    .choice_contract.context_v2_1_response_profile
                    .canonical_schema()
                ),
                provider_profile=gate2_provider_profile(
                    slot.provider_profile_id
                ),
                model_visible_request=(
                    projection.sealed_request.model_visible_request
                ),
                exact_model_id=slot.exact_model_id,
                operation_identity=(
                    financial_semantic_v6_context_v2_1_budget_smoke_operation_identity(
                        plan=plan,
                        slot=slot,
                    )
                ),
            )
        )
        operation_identity = (
            financial_semantic_v6_context_v2_1_budget_smoke_operation_identity(
                plan=plan,
                slot=slot,
            )
        )
        assert operation_identity == (
            f"{plan.integrity_hash}:{slot.integrity_hash}"
        )
        assert slot.provider_visible_schema_hash == sha256_json(
            projection.prepared_request.provider_visible_schema
        )
        audit_case = audit_cases[slot.case_id]
        fixture_case = fixture_cases[slot.case_id]
        expected = (
            fixture_case.expected_model_choice
            if audit_case["expected_disposition"] == "typed_input"
            else {
                "disposition": "unclassified_financial_input",
                "reason_code": audit_case["expected_reason_code"],
            }
        )
        assert slot.expected_answer_hash == sha256_json(expected)
        assert (
            resolve_financial_semantic_v6_context_v2_1_budget_smoke_expected_answer(
                plan=plan,
                slot=slot,
                fixture=plan_inputs["fixture"],
                outcome_audit_manifest=plan_inputs["audit_manifest"],
            )
            == expected
        )
        assert len(
            {
                slot.sealed_request_hash,
                slot.model_visible_request_hash,
                slot.prepared_request_hash,
                slot.provider_visible_schema_hash,
                slot.expected_answer_hash,
            }
        ) >= 4


def test_plan_is_deterministic_and_provider_call_free(
    plan_inputs,
) -> None:
    first, first_projector = _build_plan(plan_inputs)
    second, second_projector = _build_plan(plan_inputs)

    assert first == second
    assert first.integrity_hash == second.integrity_hash
    assert len(first_projector.calls) == len(second_projector.calls) == 12
    assert first.execution_accounting["provider_submissions_total"] == 0
    assert first.execution_accounting["provider_responses_total"] == 0
    assert "provider" in FORBIDDEN.lower()
    assert (
        "Gate2FinancialSemanticV6ContextV21BudgetSmokePlanFactory.create"
        in FACTORY_REQUIRED
    )


def test_audit_tamper_fails_before_slot_projection(
    plan_inputs,
) -> None:
    class _MustNotProject:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self, **_kwargs):
            self.calls += 1
            raise AssertionError("projection_must_not_run")

    projector = _MustNotProject()
    forged = copy.deepcopy(plan_inputs["audit_manifest"])
    case = next(
        item
        for item in forged["cases"]
        if item["case_id"] == "syn_successor_v2_no_registry_type"
    )
    case["expected_reason_code"] = "ambiguous_registry_type"

    with pytest.raises(
        Gate2FinancialSemanticV6ContextV21BudgetSmokePlanError,
    ) as failure:
        _factory(projector).create(
            fixture=plan_inputs["fixture"],
            outcome_audit_manifest=forged,
        )

    assert failure.value.code == (
        "financial_semantic_v6_context_v2_1_"
        "budget_smoke_outcome_audit_invalid"
    )
    assert projector.calls == 0


@pytest.mark.parametrize(
    ("tamper", "expected_code"),
    (
        (
            "request_profile",
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_projection_invalid",
        ),
        (
            "model_alias",
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_prepared_request_invalid",
        ),
        (
            "schema",
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_prepared_request_invalid",
        ),
        (
            "temperature",
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_prepared_request_invalid",
        ),
    ),
)
def test_projector_output_tamper_fails_closed(
    plan_inputs,
    tamper,
    expected_code,
) -> None:
    canonical = _DeterministicProjector(
        registry=plan_inputs["registry"]
    )

    def projector(**kwargs):
        projection = canonical(**kwargs)
        if tamper == "request_profile":
            return replace(
                projection,
                request_profile="forged_context_v2_1_budget_smoke",
            )
        prepared = projection.prepared_request
        if tamper == "schema":
            provider_schema = copy.deepcopy(
                prepared.provider_visible_schema
            )
            provider_schema["x-forged"] = True
            prepared = replace(
                prepared,
                provider_visible_schema=provider_schema,
            )
        else:
            form_data = copy.deepcopy(prepared.form_data)
            if tamper == "model_alias":
                form_data["model"] = "gpt-5.4-nano"
            else:
                form_data["temperature"] = 0
            prepared = replace(prepared, form_data=form_data)
        return replace(projection, prepared_request=prepared)

    with pytest.raises(
        Gate2FinancialSemanticV6ContextV21BudgetSmokePlanError,
    ) as failure:
        _factory(projector).create(
            fixture=plan_inputs["fixture"],
            outcome_audit_manifest=plan_inputs["audit_manifest"],
        )

    assert failure.value.code == expected_code
    assert len(canonical.calls) == 1


def test_resealed_model_alias_plan_tamper_is_rejected(
    plan_inputs,
) -> None:
    plan, _projector = _build_plan(plan_inputs)
    first = plan.slots[0]
    slot_draft = replace(
        first,
        exact_model_id="gpt-5.4-nano",
        integrity_hash="",
    )
    forged_slot = replace(
        slot_draft,
        integrity_hash=sha256_json(slot_draft.integrity_payload()),
    )
    plan_draft = replace(
        plan,
        slots=(forged_slot, *plan.slots[1:]),
        integrity_hash="",
    )
    forged_plan = replace(
        plan_draft,
        integrity_hash=sha256_json(plan_draft.integrity_payload()),
    )

    with pytest.raises(
        Gate2FinancialSemanticV6ContextV21BudgetSmokePlanError,
    ) as failure:
        validate_financial_semantic_v6_context_v2_1_budget_smoke_plan(
            forged_plan
        )

    assert failure.value.code == (
        "financial_semantic_v6_context_v2_1_"
        "budget_smoke_plan_slot_integrity_invalid"
    )
