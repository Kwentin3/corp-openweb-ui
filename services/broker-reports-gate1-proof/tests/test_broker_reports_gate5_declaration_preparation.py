from __future__ import annotations

from pathlib import Path

from broker_reports_gate1 import build_retention_policy
from broker_reports_gate1.gate5_evidence_intake import (
    FACTORY_REQUIRED as INTAKE_FACTORY_REQUIRED,
    FORBIDDEN as INTAKE_FORBIDDEN,
    Gate5EvidenceIntakeRuntimeFactory,
)
from broker_reports_gate1.gate5_declaration_preparation import (
    FACTORY_REQUIRED as PREPARATION_FACTORY_REQUIRED,
    FORBIDDEN as PREPARATION_FORBIDDEN,
    Gate5DeclarationPreparationRuntimeFactory,
)
from broker_reports_gate1.gate5_declaration_scope_resolution import (
    GATE5_USER_INTENT_SCHEMA_VERSION,
)
from broker_reports_gate1.gate5_human_gap_closure import (
    Gate5HumanGapClosureRuntimeFactory,
)
from broker_reports_gate1.gate5_residency_evidence import (
    GATE5_RESIDENCY_EVIDENCE_PROPOSAL_SCHEMA_VERSION,
)

import test_broker_reports_gate5_deterministic_source_fact_consumption as source_fixtures


def test_complete_intake_types_metadata_and_financial_facts_without_tax_inference(
    tmp_path: Path,
) -> None:
    store, context = source_fixtures._case(tmp_path / "intake")
    _publish_metadata(store, context)

    intake = (
        Gate5EvidenceIntakeRuntimeFactory(
            store=store,
            read_enabled=True,
        )
        .create()
        .collect(context=context)
    )

    assert intake["terminals"] == ["EVIDENCE_INTAKE_CONTRACT_PROVEN"]
    fact_types = {item["fact_type"] for item in intake["metadata_facts"]}
    assert {
        "DOCUMENT_TYPE",
        "DOCUMENT_DATE",
        "BROKER_LEGAL_NAME",
        "PARTY_NAME",
        "ACCOUNT_IDENTIFIER",
        "ACCOUNT_CONTRACT_IDENTIFIER",
        "STATEMENT_PERIOD",
    } <= fact_types
    assert intake["coverage"]["lost_upstream"] == 0
    assert intake["coverage"]["provenance_complete"] is True
    assert intake["coverage"]["financial_category_counts"]["SECURITY_FACT"] == 3
    assert intake["coverage"]["financial_category_counts"]["SOURCE_TOTAL"] == 2
    assert intake["tax_meaning_assigned"] is False
    assert intake["broker_country_to_income_source_inferred"] is False
    assert intake["broker_country_to_taxpayer_residency_inferred"] is False
    assert intake["reconciliation"] == "not_performed"


def test_review_scope_and_questions_are_exact_minimal_and_separated(
    tmp_path: Path,
) -> None:
    store, context = source_fixtures._case(
        tmp_path / "gaps",
        include_purchases=False,
        include_withheld_detail=False,
        include_withheld_total=False,
    )
    _publish_metadata(store, context)

    result = _prepare(store, context, evidence_mode="SYNTHETIC_CONTROL")

    assert result["terminals"] == [
        "EVIDENCE_INTAKE_CONTRACT_PROVEN",
        "CLIENT_EVIDENCE_REVIEW_PROVEN",
        "DECLARATION_SCOPE_ACTIVATION_PROVEN",
        "HUMAN_GAP_CLOSURE_LOOP_PROVEN",
        "RESIDENCY_EVIDENCE_BOUNDARY_PROVEN",
        "DECLARATION_PREPARATION_WORKFLOW_PROVEN",
        "SYNTHETIC_DECLARATION_PREPARATION_CONTROL",
    ]
    scope = result["scope_activation"]
    assert scope["metrics"] == {
        "definition_demands": 25,
        "active_demands": 9,
        "inactive_demands_suppressed": 16,
        "active_domains": 5,
        "runtime_questions_created": 0,
    }
    active = {item["demand"] for item in scope["active_demands"]}
    assert "obl_securities_and_derivatives_results" in active
    assert "obl_digital_financial_asset_and_right_results" not in active
    assert "obl_investment_partnership_results" not in active
    assert scope["absence_converted_to_not_applicable"] is False
    review = result["client_review"]
    assert review["commission_sanity"]["mode"] == "hybrid"
    assert review["commission_sanity"]["detail_count"] == 4
    assert review["commission_sanity"]["aggregate_count"] == 1
    assert review["commission_sanity"]["reconciliation"] == "not_performed"
    acquisition = next(
        item
        for item in review["required_blockers"]
        if item["reason_code"]
        == "gate5_source_fact_acquisition_evidence_horizon_unproven"
    )
    assert acquisition["quantitative_gap"] == {
        "required_quantity": "12",
        "available_prior_quantity": "0",
        "minimum_missing_quantity": "12",
    }
    assert review["advisory_findings"][0]["reason_code"] == (
        "withholding_evidence_absent"
    )
    assert review["llm_adapter_input"]["raw_transactions_supplied"] is False
    closure = result["gap_closure"]
    assert any(
        item["closure_type"] == "ADDITIONAL_DOCUMENT"
        and item["subject"].get("asset") == "ACME"
        for item in closure["required_actions"]
    )
    taxpayer = next(
        item
        for item in closure["required_actions"]
        if item["fact_key"] == "taxpayer_identity_confirmed"
    )
    assert taxpayer["evidence_refs"]
    assert "named in the supplied broker evidence" in taxpayer["question"]
    assert closure["llm_adapter_input"]["raw_transactions_supplied"] is False
    assert closure["metrics"]["known_document_facts_reused"] == 1
    source_jurisdiction = next(
        item
        for item in closure["required_actions"]
        if "obl_foreign_source_taxable_income_and_foreign_tax" in item["demand_refs"]
    )
    assert source_jurisdiction["closure_type"] == "METHODOLOGY_RESEARCH"
    assert source_jurisdiction["fact_key"] is None
    assert "belong to Gate 5 methodology" in source_jurisdiction["reason"]
    assert source_jurisdiction not in closure["user_facing_required_actions"]
    assert not any(
        item.get("fact_key") == "income_source_classification"
        for item in closure["required_actions"]
    )
    residency = next(
        item
        for item in closure["required_actions"]
        if item.get("fact_key") == "residency_evidence"
    )
    assert residency["answer_contract"]["kind"] == "residency_evidence"
    assert "Do not answer only" in residency["question"]
    assert closure["residency_classification"]["status"] == ("INSUFFICIENT_EVIDENCE")
    assert result["metrics"]["invented_source_facts"] == 0
    assert result["metrics"]["invented_relations"] == 0


def test_broker_reported_withholding_does_not_trigger_a_duplicate_document_request(
    tmp_path: Path,
) -> None:
    store, context = source_fixtures._case(tmp_path / "withholding")
    _publish_metadata(store, context)

    result = _prepare(store, context, evidence_mode="REAL_EVIDENCE")
    closure = result["gap_closure"]
    foreign_requests = [
        item
        for item in closure["required_actions"]
        if "obl_foreign_source_taxable_income_and_foreign_tax" in item["demand_refs"]
    ]

    assert foreign_requests
    assert {item["closure_type"] for item in foreign_requests} == {
        "METHODOLOGY_RESEARCH"
    }
    assert all(item["evidence_refs"] for item in foreign_requests)
    assert not any(
        item["closure_type"] == "ADDITIONAL_DOCUMENT"
        and "obl_foreign_source_taxable_income_and_foreign_tax" in item["demand_refs"]
        for item in closure["user_facing_required_actions"]
    )


def test_new_document_and_typed_answer_trigger_deterministic_replay(
    tmp_path: Path,
) -> None:
    store, context = source_fixtures._case(
        tmp_path / "replay",
        include_purchases=False,
    )
    _publish_metadata(store, context)
    runtime = Gate5DeclarationPreparationRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()
    before = runtime.prepare(**_prepare_args(context, "SYNTHETIC_CONTROL", []))
    human = Gate5HumanGapClosureRuntimeFactory.create(
        store=store,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
    )
    published_before = _publish_requests(human, before, context, [])
    document_request = next(
        item
        for item in published_before["required_actions"]
        if item["closure_type"] == "ADDITIONAL_DOCUMENT"
        and item["subject"].get("asset") == "ACME"
    )
    routed = human.normalize_answer(
        request=document_request,
        answer={"kind": "document_submission", "value": True},
        context=context,
    )
    assert routed == {
        "status": "NORMALIZATION_REQUIRED",
        "request_id": document_request["request_id"],
        "typed_user_case_fact": None,
        "route": "ordinary normalization path through Gate 1 to Gate 4",
    }

    source_fixtures._publish(
        store,
        context,
        document_id="earlier-acquisition",
        source_rows=("Purchase|01.01.2025|ACME|12|120.00|RUB",),
        fact_specs=(
            (
                "SECURITY_PURCHASE",
                source_fixtures._security_roles("01.01.2025", "12", "120.00", "RUB"),
            ),
        ),
        purchase_date="01.01.2025",
    )
    source_fixtures._gate4(store).rebuild_case(context=context)
    after_document = runtime.replay(**_prepare_args(context, "SYNTHETIC_CONTROL", []))
    assert (
        after_document["machine_readable_declaration_draft"]["calculation_count"] == 1
    )
    assert not any(
        item["subject"].get("asset") == "ACME"
        and item["closure_type"] == "ADDITIONAL_DOCUMENT"
        for item in after_document["gap_closure"]["required_actions"]
    )

    published_after_document = _publish_requests(human, after_document, context, [])
    taxpayer_request = next(
        item
        for item in published_after_document["required_actions"]
        if item["fact_key"] == "taxpayer_identity_confirmed"
    )
    normalized = human.normalize_answer(
        request=taxpayer_request,
        answer={"kind": "confirmation", "value": True},
        context=context,
    )
    user_fact = normalized["typed_user_case_fact"]
    after_answer = runtime.replay(
        **_prepare_args(context, "SYNTHETIC_CONTROL", [user_fact])
    )
    assert not any(
        item["fact_key"] == "taxpayer_identity_confirmed"
        for item in after_answer["gap_closure"]["required_actions"]
    )
    assert after_answer["gap_closure"]["metrics"]["already_known_not_asked"] == 1
    assert after_answer["replay"]["stale_llm_state_reused"] is False
    assert after_answer["target_release"]["xml_emitted"] is False
    assert after_answer["target_release"]["projection_owner"] == (
        "Gate5FullTargetXmlProjectionRuntimeFactory.create"
    )

    published_after_answer = _publish_requests(
        human, after_answer, context, [user_fact]
    )
    residency_request = next(
        item
        for item in published_after_answer["required_actions"]
        if item.get("fact_key") == "residency_evidence"
    )
    residency = human.normalize_answer(
        request=residency_request,
        answer={
            "kind": "residency_evidence",
            "value": {
                "human_answer": (
                    "В 2025 году находился в России с 01.01.2025 по 02.07.2025, "
                    "отсутствовал с 03.07.2025 по 31.12.2025; иных причин нет."
                ),
                "proposal": {
                    "schema_version": (
                        GATE5_RESIDENCY_EVIDENCE_PROPOSAL_SCHEMA_VERSION
                    ),
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
                    "evidence_refs": ["authenticated-human-answer"],
                },
            },
        },
        context=context,
    )["typed_user_case_fact"]
    after_residency = runtime.replay(
        **_prepare_args(
            context,
            "SYNTHETIC_CONTROL",
            [user_fact, residency],
        )
    )
    assert after_residency["residency_classification"]["status"] == "RESIDENT"
    taxpayer_readiness = next(
        item
        for item in after_residency["machine_readable_declaration_draft"][
            "active_demand_readiness"
        ]
        if item["demand"] == "obl_taxpayer_identity_and_period_status"
    )
    assert taxpayer_readiness["readiness"] == "METHODOLOGY_RESULT_AVAILABLE"
    assert not any(
        item.get("fact_key") == "residency_evidence"
        for item in after_residency["gap_closure"]["required_actions"]
    )


def test_preparation_consumes_closed_filing_election_without_reinterpreting_it(
    tmp_path: Path,
) -> None:
    store, context = source_fixtures._case(tmp_path / "closed-filing-election")
    _publish_metadata(store, context)
    preparation = Gate5DeclarationPreparationRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()
    before = preparation.prepare(
        **_prepare_args(context, "SYNTHETIC_CONTROL", [])
    )
    human = Gate5HumanGapClosureRuntimeFactory.create(
        store=store,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
    )
    published = _publish_requests(human, before, context, [])
    filing_request = next(
        item
        for item in published["required_actions"]
        if item.get("fact_key") == "filing_instance_identity"
    )
    filing_fact = human.normalize_answer(
        request=filing_request,
        answer={"kind": "code", "value": "INITIAL"},
        context=context,
    )["typed_user_case_fact"]

    after = preparation.replay(
        **_prepare_args(context, "SYNTHETIC_CONTROL", [filing_fact])
    )
    filing_readiness = next(
        item
        for item in after["machine_readable_declaration_draft"][
            "active_demand_readiness"
        ]
        if item["demand"] == "obl_filing_instance_identity"
    )
    assert filing_readiness["readiness"] == "USER_FACT_AVAILABLE"
    assert "INITIAL" not in repr(after["machine_readable_declaration_draft"])
    assert any(
        item["closure_type"] == "EXTERNAL_AUTHORITY"
        and item["demand_refs"] == ["obl_filing_instance_identity"]
        for item in after["gap_closure"]["internal_owner_required_actions"]
    )


def test_factories_and_non_goals_remain_explicit() -> None:
    assert "Gate3MetadataSourceFactRuntimeFactory.create" in INTAKE_FACTORY_REQUIRED[0]
    assert "tax classification" in INTAKE_FORBIDDEN[0]
    assert "Gate5RealTaxCaseAssemblyRuntimeFactory.create" in (
        PREPARATION_FACTORY_REQUIRED[0]
    )
    assert "manual XML" in PREPARATION_FORBIDDEN[0]


def test_unlabelled_organization_and_generic_tax_id_do_not_become_broker_facts(
    tmp_path: Path,
) -> None:
    store, context = source_fixtures._case(tmp_path / "strict-metadata")
    source_fixtures._publish(
        store,
        context,
        document_id="unlabelled-metadata",
        source_rows=(
            "Example Securities LLC",
            "ИНН: 1234-5678",
            "Commission|1.00|RUB",
        ),
        fact_specs=(
            (
                "COMMISSION",
                (
                    ("amount", "1.00"),
                    ("currency", "RUB"),
                    ("date", None),
                    ("asset", None),
                ),
            ),
        ),
        target_indexes=(2,),
    )
    source_fixtures._gate4(store).rebuild_case(context=context)

    intake = (
        Gate5EvidenceIntakeRuntimeFactory(
            store=store,
            read_enabled=True,
        )
        .create()
        .collect(context=context)
    )

    fact_types = {item["fact_type"] for item in intake["metadata_facts"]}
    assert "BROKER_LEGAL_NAME" not in fact_types
    assert "BROKER_TAX_IDENTIFIER" not in fact_types
    assert intake["coverage"]["unsupported_entity_role_inferences"] == 0


def _publish_metadata(store, context) -> None:
    source_fixtures._publish(
        store,
        context,
        document_id="metadata",
        source_rows=(
            "Отчет брокера",
            "Broker: Example Securities LLC",
            "Client Name: Test Person",
            "Account Number: A-123",
            "Генеральное соглашение: CONTRACT-7",
            "Дата формирования отчета: 31.12.2025",
            "Statement Period: 01.01.2025 - 31.12.2025",
            "Commission|1.00|RUB",
        ),
        fact_specs=(
            (
                "COMMISSION",
                (
                    ("amount", "1.00"),
                    ("currency", "RUB"),
                    ("date", None),
                    ("asset", None),
                ),
            ),
        ),
        target_indexes=(7,),
    )
    source_fixtures._gate4(store).rebuild_case(context=context)


def _prepare(store, context, *, evidence_mode: str):
    return (
        Gate5DeclarationPreparationRuntimeFactory(
            store=store,
            read_enabled=True,
        )
        .create()
        .prepare(**_prepare_args(context, evidence_mode, []))
    )


def _prepare_args(context, evidence_mode: str, user_case_facts: list[dict]):
    return {
        "source_fact_methodology_ref": source_fixtures._source_methodology_ref(),
        "context": context,
        "evidence_mode": evidence_mode,
        "user_intent": {
            "schema_version": GATE5_USER_INTENT_SCHEMA_VERSION,
            "form": "3-NDFL",
            "tax_period": "2025",
            "task": "prepare_tax_declaration",
            "domains": ["broker_securities_income"],
        },
        "taxpayer_scope_ref": "synthetic-taxpayer",
        "user_case_facts": user_case_facts,
    }


def _publish_requests(human, prepared, context, user_case_facts: list[dict]):
    return human.publish_requests(
        intake=prepared["intake"],
        scope_activation=prepared["scope_activation"],
        client_review=prepared["client_review"],
        user_case_facts=user_case_facts,
        residency_classification=prepared["residency_classification"],
        context=context,
        taxpayer_scope_ref="synthetic-taxpayer",
        tax_period="2025",
    )
