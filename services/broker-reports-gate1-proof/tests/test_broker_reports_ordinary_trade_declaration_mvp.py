from __future__ import annotations

import copy
import hashlib
import inspect
import json
import base64
from dataclasses import replace
from importlib import resources

from lxml import etree
from pathlib import Path

import pytest

from broker_reports_gate1.artifact_retention import build_retention_policy
from broker_reports_gate1.gate5_human_gap_closure import (
    Gate5HumanGapClosureError,
    Gate5HumanGapClosureRuntimeFactory,
)
from broker_reports_gate1.gate5_full_target_xml_projection import (
    Gate5FullTargetXmlProjectionRuntimeFactory,
)
import broker_reports_gate1.gate5_full_target_xml_projection as xml_projection_module
from broker_reports_gate1.gate5_declaration_semantic_input import (
    Gate5DeclarationSemanticInputRuntimeFactory,
)
from broker_reports_gate1.ordinary_trade_declaration_mvp import (
    ORDINARY_TRADE_DECLARATION_MVP_TERMINAL,
    OrdinaryTradeDeclarationMvpError,
)
from broker_reports_gate1.ordinary_trade_production_runtime import (
    OrdinaryTradeProductionRuntimeFactory,
)
from broker_reports_gate1.ordinary_trade_declaration_case_inputs import (
    OrdinaryTradeDeclarationCaseInputsError,
    OrdinaryTradeDeclarationCaseInputsRuntime,
    OrdinaryTradeDeclarationCaseInputsRuntimeFactory,
    primary_taxpayer_scope_ref,
)
from broker_reports_gate1.ordinary_trade_projection import (
    OrdinaryTradeProjectionFactory,
)
from broker_reports_gate1.ordinary_trade_candidate_runtime import (
    OrdinaryTradeCandidateRuntimeFactory,
)
from broker_reports_gate1.gate5_trusted_methodology import (
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
    Gate5TrustedMethodologyError,
)

import test_broker_reports_active_category_declaration_assembly as assembly_fixtures
import test_broker_reports_gate5_human_fact_scope as human_fixtures


_METADATA_LINES = (
    "ФИО: Иванов Иван Иванович",
    "ИНН налогоплательщика: 500100732259",
    "Брокер: АО Тестовый брокер",
    "ИНН брокера: 7707083893",
    "КПП брокера: 773601001",
    "ОКТМО брокера: 45382000",
    "Юрисдикция брокера: RU",
    "Место реализации: RU",
    "Допуск к торгам: ADMITTED",
    "Рыночная котировка: AVAILABLE",
    "Режим счета: OUTSIDE_IIS",
    "Заявленное освобождение: NONE",
)


def test_persisted_canonical_facts_reach_byte_stable_official_xsd_xml(
    tmp_path: Path,
) -> None:
    runtime, context, _providers = _case(tmp_path, proceeds="60.00")

    first = _run(runtime, context)
    second = _run(runtime, context)

    assert first["terminal"] == ORDINARY_TRADE_DECLARATION_MVP_TERMINAL
    assert first["xml_bytes"] == second["xml_bytes"]
    assert first["xml_sha256"] == second["xml_sha256"]
    assert first["xsd_conformance"]["xsd_valid"] is True
    assert first["provider_calls_total"] == 0
    assert first["taxpayer_scope_ref"].startswith("taxpayer_slot_")
    assert first["taxpayer_scope_ref"] != "security-disposal-1"
    assert first["semantic_accounting"]["mapping_occurrences_total"] == 49
    assert len(first["authority_bindings"]["user_case_fact_refs"]) == 10
    assert "user_facts_artifact_ref" not in first["authority_bindings"]
    assert first["authority_bindings"]["canonical_coverage_ref"].startswith(
        "ordinary_trade_coverage_"
    )
    assert first["semantic_reconciliation"]["status"] == "passed"
    filing_component = next(
        item
        for item in first["assembly_receipt"]["owner_artifacts"]["package"][
            "component_snapshots"
        ]
        if item["domain_id"] == "filing_and_party_identity"
    )
    filing_input = filing_component["snapshot"]["input_snapshot"]
    provenance = filing_input["field_provenance"]
    assert provenance["declarant_category"]["source_kind"] == (
        "methodology_derived_result"
    )
    assert filing_input["evidence"]["real_user_fact"] is False
    assert first["receipt_artifact_ref"].startswith("mvp_receipt_")
    assert first["xml_artifact_ref"].startswith("mvp_xml_")
    assert b"NO_NDFL3_1_033_00_05_20_01" not in first["xml_bytes"]
    assert first["xml_bytes"].startswith(b"<?xml")
    fixture = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "reports"
        / "2026-08-23"
        / "BROKER_REPORTS_ISSUE_302_MVP_DECLARATION.safe.xml"
    )
    assert etree.tostring(etree.fromstring(first["xml_bytes"]), method="c14n") == (
        etree.tostring(etree.fromstring(fixture.read_bytes()), method="c14n")
    )


def test_user_attested_candidate_defer_draft_and_same_case_xml_resume(
    tmp_path: Path,
) -> None:
    runtime, context, _providers = _case(
        tmp_path,
        proceeds="60.00",
        publish_human_facts=False,
    )
    first = runtime.run(canonical_artifact_refs=[], context=context)
    actions = first["product"]["preparation"]["user_actions"]
    by_key = {item["fact_key"]: item for item in actions}
    candidate = by_key["taxpayer_identity"]["answer_contract"]["candidate"]

    assert first["product"]["status"] == "INPUT_REQUIRED"
    assert candidate["inn"] == "500100732259"
    assert candidate["source_fact_refs"]
    deferred = runtime.normalize_declaration_action(
        request_publication_ref=by_key["taxpayer_identity"][
            "request_publication_ref"
        ],
        answer={
            "kind": "identity_choice",
            "value": {"choice": "DEFER", "identity": None},
        },
        context=context,
    )
    assert deferred["status"] == "USER_CASE_FACT_DEFERRED"
    assert deferred["typed_user_case_fact"] is None

    for key in (
        "taxpayer_capacity",
        "residency_evidence",
        "ordinary_trade_declaration_zero_scope_confirmed",
    ):
        runtime.normalize_declaration_action(
            request_publication_ref=by_key[key]["request_publication_ref"],
            answer=_product_answer(key),
            context=context,
        )
    draft = runtime.run(canonical_artifact_refs=[], context=context)
    assert draft["product"]["status"] == "DRAFT_READY"
    assert draft["product"]["xml_created"] is False
    assert draft["declaration"] is None
    assert draft["product"]["preparation"]["calculation_preview"][
        "status"
    ] == "calculated"
    assert "taxpayer_identity" in draft["product"]["preparation"][
        "checklist_fact_keys"
    ]

    for key, request in by_key.items():
        if key in {
            "taxpayer_capacity",
            "residency_evidence",
            "ordinary_trade_declaration_zero_scope_confirmed",
        }:
            continue
        result = runtime.normalize_declaration_action(
            request_publication_ref=request["request_publication_ref"],
            answer=_product_answer(key),
            context=context,
        )
        assert result["status"] == "TYPED_USER_CASE_FACT_READY"
        assert result["typed_user_case_fact"]["provenance"]["source_kind"] == (
            "USER_ATTESTED_CASE_FACT"
        )
    ready = runtime.run(canonical_artifact_refs=[], context=context)
    assert ready["product"]["status"] == "DECLARATION_XML_READY"


def test_invalid_calendar_date_and_inn_checksum_are_rejected_before_fact(
    tmp_path: Path,
) -> None:
    runtime, context, _providers = _case(
        tmp_path,
        proceeds="60.00",
        publish_human_facts=False,
    )
    first = runtime.run(canonical_artifact_refs=[], context=context)
    by_key = {
        item["fact_key"]: item
        for item in first["product"]["preparation"]["user_actions"]
    }
    with pytest.raises(Exception) as invalid_inn:
        runtime.normalize_declaration_action(
            request_publication_ref=by_key["taxpayer_identity"][
                "request_publication_ref"
            ],
            answer={
                "kind": "identity_choice",
                "value": {
                    "choice": "CHANGE",
                    "identity": {
                        "inn": "123456789012",
                        "last_name": "Иванов",
                        "first_name": "Иван",
                        "middle_name": "Иванович",
                        "source_fact_refs": [],
                    },
                },
            },
            context=context,
        )
    assert getattr(invalid_inn.value, "code", "") == (
        "gate5_gap_taxpayer_inn_checksum_invalid"
    )
    with pytest.raises(Exception) as invalid_date:
        runtime.normalize_declaration_action(
            request_publication_ref=by_key["declaration_date"][
                "request_publication_ref"
            ],
            answer={"kind": "text", "value": "2025-99-99"},
            context=context,
        )
    assert getattr(invalid_date.value, "code", "") == (
        "gate5_gap_declaration_date_invalid"
    )
    current = runtime.run(canonical_artifact_refs=[], context=context)
    current_keys = {
        item["fact_key"]
        for item in current["product"]["preparation"]["user_actions"]
    }
    assert {"taxpayer_identity", "declaration_date"} <= current_keys


def test_owner_published_fill_fact_successor_allows_safe_correction(
    tmp_path: Path,
) -> None:
    runtime, context, _providers = _case(tmp_path, proceeds="60.00")
    ready = runtime.run(canonical_artifact_refs=[], context=context)
    assert ready["product"]["status"] == "DECLARATION_XML_READY"

    successor = runtime.publish_declaration_change_action(
        fact_key="declaration_date",
        context=context,
    )
    pending = runtime.run(canonical_artifact_refs=[], context=context)
    assert pending["product"]["status"] == "DRAFT_READY"
    assert pending["product"]["xml_created"] is False
    assert [
        item["fact_key"]
        for item in pending["product"]["preparation"]["user_actions"]
    ] == ["declaration_date"]

    with pytest.raises(Exception) as invalid:
        runtime.normalize_declaration_action(
            request_publication_ref=successor["request_publication_ref"],
            answer={"kind": "text", "value": "2025-99-99"},
            context=context,
        )
    assert getattr(invalid.value, "code", "") == "gate5_gap_declaration_date_invalid"
    still_pending = runtime.run(canonical_artifact_refs=[], context=context)
    assert still_pending["product"]["status"] == "DRAFT_READY"
    accepted = runtime.normalize_declaration_action(
        request_publication_ref=successor["request_publication_ref"],
        answer={"kind": "text", "value": "2026-08-24"},
        context=context,
    )
    assert accepted["status"] == "TYPED_USER_CASE_FACT_READY"
    corrected = runtime.run(canonical_artifact_refs=[], context=context)
    assert corrected["product"]["status"] == "DECLARATION_XML_READY"
    identity_successor = runtime.publish_declaration_change_action(
        fact_key="taxpayer_identity",
        context=context,
    )
    identity_pending = runtime.run(canonical_artifact_refs=[], context=context)
    assert identity_pending["product"]["status"] == "DRAFT_READY"
    assert identity_pending["product"]["preparation"]["checklist_fact_keys"] == [
        "taxpayer_identity"
    ]
    runtime.normalize_declaration_action(
        request_publication_ref=identity_successor["request_publication_ref"],
        answer={
            "kind": "identity_choice",
            "value": {
                "choice": "CHANGE",
                "identity": {
                    "inn": "500100732322",
                    "last_name": "Иванов",
                    "first_name": "Иван",
                    "middle_name": "Иванович",
                    "source_fact_refs": [],
                },
            },
        },
        context=context,
    )
    identity_corrected = runtime.run(canonical_artifact_refs=[], context=context)
    assert identity_corrected["product"]["status"] == "DECLARATION_XML_READY"
    assert identity_corrected["declaration"]["xml_sha256"] != corrected[
        "declaration"
    ]["xml_sha256"]
    assert ready["product"]["xml_created"] is True
    assert ready["declaration"]["provider_calls_total"] == 0
    assert b"TBD" not in ready["declaration"]["xml_bytes"]
    assert b"000000000000" not in ready["declaration"]["xml_bytes"]


def test_identity_candidate_successor_stales_old_confirmation_and_cross_scope(
    tmp_path: Path,
) -> None:
    runtime, context_a, _providers, store = _case(
        tmp_path,
        proceeds="60.00",
        publish_human_facts=False,
        include_store=True,
    )
    first = runtime.run(canonical_artifact_refs=[], context=context_a)
    old = next(
        item
        for item in first["product"]["preparation"]["user_actions"]
        if item["fact_key"] == "taxpayer_identity"
    )
    for request in first["product"]["preparation"]["user_actions"]:
        accepted = runtime.normalize_declaration_action(
            request_publication_ref=request["request_publication_ref"],
            answer=_product_answer(request["fact_key"]),
            context=context_a,
        )
        assert accepted["status"] == "TYPED_USER_CASE_FACT_READY"
    ready = runtime.run(canonical_artifact_refs=[], context=context_a)
    assert ready["product"]["status"] == "DECLARATION_XML_READY"
    assert ready["product"]["xml_created"] is True
    with pytest.raises(Exception) as foreign:
        runtime.normalize_declaration_action(
            request_publication_ref=old["request_publication_ref"],
            answer=_product_answer("taxpayer_identity"),
            context=replace(context_a, user_id="foreign-user"),
        )
    assert getattr(foreign.value, "code", "") == (
        "gate5_gap_request_publication_invalid"
    )

    active = store.get_active_canonical_version(
        context=context_a,
        document_id="ordinary-trade-declaration-metadata",
    )
    context_b = replace(context_a, normalization_run_id="g4-runtime-run-2")
    changed_lines = tuple(
        "ИНН налогоплательщика: 500100732322"
        if line.startswith("ИНН налогоплательщика:")
        else line
        for line in _METADATA_LINES
    )
    assembly_fixtures.bridge_fixtures.ordinary_fixtures.gate4_fixtures._activate_canonical(
        store=store,
        context=context_b,
        document_id="ordinary-trade-declaration-metadata",
        artifact_version=2,
        expected_previous_version_id=active.canonical_version_id,
        source_rows=changed_lines,
    )
    current = store.get_active_canonical_version(
        context=context_b,
        document_id="ordinary-trade-declaration-metadata",
    )
    successor = runtime.run(
        canonical_artifact_refs=[str(current.manifest_ref)],
        context=context_b,
    )
    assert successor["product"]["status"] == "DRAFT_READY"
    assert successor["product"]["xml_created"] is False
    assert successor["declaration"] is None
    new = next(
        item
        for item in successor["product"]["preparation"]["user_actions"]
        if item["fact_key"] == "taxpayer_identity"
    )
    assert new["request_publication_ref"] != old["request_publication_ref"]
    with pytest.raises(Exception) as stale:
        runtime.normalize_declaration_action(
            request_publication_ref=old["request_publication_ref"],
            answer=_product_answer("taxpayer_identity"),
            context=context_b,
        )
    assert getattr(stale.value, "code", "") == "gate5_gap_request_stale"
    accepted = runtime.normalize_declaration_action(
        request_publication_ref=new["request_publication_ref"],
        answer=_product_answer("taxpayer_identity"),
        context=context_b,
    )
    assert accepted["status"] == "TYPED_USER_CASE_FACT_READY"
    current = runtime.run(canonical_artifact_refs=[], context=context_b)
    assert current["product"]["status"] == "DECLARATION_XML_READY"
    assert current["declaration"]["xml_sha256"] != ready["declaration"]["xml_sha256"]


def test_human_actions_cannot_close_missing_source_or_methodology_fact(
    tmp_path: Path,
) -> None:
    lines = tuple(
        line for line in _METADATA_LINES if not line.startswith("Допуск к торгам:")
    )
    runtime, context, _providers = _case(
        tmp_path,
        proceeds="60.00",
        publish_human_facts=False,
        metadata_lines=lines,
    )

    result = runtime.run(canonical_artifact_refs=[], context=context)

    assert result["product"]["status"] == "PREPARATION_INCOMPLETE"
    blockers = result["product"]["preparation"]["internal_blockers"]
    assert any(
        item.get("required_source_fact_type") == "ADMITTED_EXCHANGE_FACT"
        and item["gap_owner_classification"] == "REAL_SOURCE_EVIDENCE_MISSING"
        for item in blockers
    )
    assert all(
        item["closure_type"] == "USER_FACT"
        for item in result["product"]["preparation"]["user_actions"]
    )
    assert all(
        item["fact_key"] != "admitted_exchange_fact"
        for item in result["product"]["preparation"]["user_actions"]
    )


def test_duplicate_confirmation_is_idempotent_without_duplicate_fact(
    tmp_path: Path,
) -> None:
    runtime, context, _providers, store = _case(
        tmp_path,
        proceeds="60.00",
        publish_human_facts=False,
        include_store=True,
    )
    first = runtime.run(canonical_artifact_refs=[], context=context)
    request = next(
        item
        for item in first["product"]["preparation"]["user_actions"]
        if item["fact_key"] == "taxpayer_identity"
    )
    kwargs = {
        "request_publication_ref": request["request_publication_ref"],
        "answer": _product_answer("taxpayer_identity"),
        "context": context,
    }

    accepted_a = runtime.normalize_declaration_action(**kwargs)
    accepted_b = runtime.normalize_declaration_action(**kwargs)

    assert accepted_a["typed_user_case_fact"] == accepted_b["typed_user_case_fact"]
    identity_ref = accepted_a["typed_user_case_fact"]["user_case_fact_ref"]
    assert sum(
        record.artifact_id == identity_ref
        for record in store.list_by_case(context.case_id)
    ) == 1


def test_only_production_factory_activates_the_mvp_adapter(tmp_path: Path) -> None:
    _runtime, context, providers, store = _case(
        tmp_path, proceeds="60.00", include_store=True
    )
    production = OrdinaryTradeProductionRuntimeFactory(
        store=store,
        read_enabled=True,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
    ).create()

    result = production.run(canonical_artifact_refs=[], context=context)

    assert result["product"]["status"] == "DECLARATION_XML_READY"
    assert result["product"]["declaration_ready"] is True
    assert result["product"]["xml_created"] is True
    assert result["product"]["preparation"]["gap_closure"] == {
        "user_facing_required_actions": [],
        "internal_owner_required_actions": [],
    }
    assert result["declaration"]["terminal"] == ORDINARY_TRADE_DECLARATION_MVP_TERMINAL


def test_production_without_declaration_owners_names_exact_blocker(tmp_path: Path) -> None:
    _configured, context, _providers, store = _case(
        tmp_path, proceeds="60.00", include_store=True
    )
    runtime = OrdinaryTradeProductionRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()

    result = runtime.run(canonical_artifact_refs=[], context=context)

    assert result["declaration"] is None
    assert result["product"]["status"] == "PREPARATION_INCOMPLETE"
    assert result["product"]["terminal"] == (
        "ordinary_trade_declaration_authority_owners_required"
    )
    assert result["product"]["declaration_ready"] is False
    assert result["product"]["xml_created"] is False


def test_review_fixture_is_official_xsd_valid_and_semantically_reconciled(
    tmp_path: Path,
) -> None:
    fixture = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "reports"
        / "2026-08-23"
        / "BROKER_REPORTS_ISSUE_302_MVP_DECLARATION.safe.xml"
    )
    xml = etree.fromstring(fixture.read_bytes())
    encoded_xsd = resources.files("broker_reports_gate1").joinpath(
        "gate5_full_target_xml_schema.NO_NDFL3_1_033_00_05_20_01.xsd.b64"
    ).read_bytes()
    schema = etree.XMLSchema(etree.fromstring(base64.b64decode(encoded_xsd)))

    assert schema.validate(xml), schema.error_log
    calculation = xml.find(".//РасчНалБаза")
    securities = xml.find(".//ДохОперЦБ")
    assert calculation is not None and securities is not None
    assert calculation.get("СумДох") == securities.get("ДохСовОпер") == "60.00"
    assert calculation.get("СумРасх") == securities.get("РасхРеалЦБ") == "43.00"
    assert calculation.get("НалБаза") == "17.00"
    extracted = (
        Gate5FullTargetXmlProjectionRuntimeFactory.create()
        .extract_supported_profile_values(xml_bytes=fixture.read_bytes())
    )
    runtime, context, _providers = _case(tmp_path, proceeds="60.00")
    owner_result = _run(runtime, context)
    semantic = Gate5DeclarationSemanticInputRuntimeFactory.create().reconcile_serialized_projection_values(
        projection_input=owner_result["assembly_receipt"]["owner_artifacts"][
            "projection_input"
        ],
        serialized_values=extracted["values"],
    )
    assert extracted["status"] == "extracted"
    assert semantic["status"] == "passed"
    assert semantic["comparison_owner"] == (
        "Gate5DeclarationSemanticInputRuntimeFactory.create"
    )


@pytest.mark.parametrize(
    ("path", "attribute", "value"),
    [
        (".//РасчНалБаза", "НалБаза", "18.00"),
        (".//РасчНалПУ", "Исчисл", "3"),
        (".//РасчНалПУ", "ПодлУпл", "3"),
        (".//РасчНалПУ", "ПодлВозв", "1"),
        (".//СумНалПуИскл227", "ПодлУпл", "3"),
        (".//СумНалПуИскл227", "ПодлВозв", "1"),
        (".//ДоходИстРФ", "Доход", "61.00"),
    ],
)
def test_xsd_valid_numeric_xml_mutations_fail_independent_reconciliation(
    tmp_path: Path, path: str, attribute: str, value: str
) -> None:
    runtime, context, _providers = _case(tmp_path, proceeds="60.00")
    result = _run(runtime, context)
    tree = etree.fromstring(result["xml_bytes"])
    node = tree.find(path)
    assert node is not None
    node.set(attribute, value)
    changed = etree.tostring(
        tree,
        xml_declaration=True,
        encoding="windows-1251",
        pretty_print=False,
    )
    encoded_xsd = resources.files("broker_reports_gate1").joinpath(
        "gate5_full_target_xml_schema.NO_NDFL3_1_033_00_05_20_01.xsd.b64"
    ).read_bytes()
    schema = etree.XMLSchema(etree.fromstring(base64.b64decode(encoded_xsd)))
    assert changed != result["xml_bytes"]
    assert schema.validate(etree.fromstring(changed))

    hybrid = copy.deepcopy(result)
    hybrid["xml_bytes"] = changed
    hybrid["xml_sha256"] = hashlib.sha256(changed).hexdigest()
    with pytest.raises(OrdinaryTradeDeclarationMvpError) as invalid:
        runtime.validate_current_declaration(result=hybrid, context=context)
    assert invalid.value.code == "ordinary_trade_declaration_xml_semantics_invalid"


def test_taxpayer_slot_is_scope_not_identity(tmp_path: Path) -> None:
    runtime, context, _providers = _case(tmp_path, proceeds="60.00")
    result = _run(runtime, context)

    assert result["taxpayer_scope_ref"] == primary_taxpayer_scope_ref(
        context=context
    )
    assert result["taxpayer_scope_ref"] != "500100732259"
    assert result["taxpayer_scope_ref"] != "security-disposal-1"
    filing = next(
        item
        for item in result["assembly_receipt"]["owner_artifacts"]["package"][
            "component_snapshots"
        ]
        if item["domain_id"] == "filing_and_party_identity"
    )
    assert filing["snapshot"]["input_snapshot"]["field_provenance"][
        "taxpayer_identity"
    ]["source_kind"] == "USER_ATTESTED_CASE_FACT"


def test_multiple_disposals_are_not_silently_duplicated_or_dropped(
    tmp_path: Path,
) -> None:
    runtime, context, _providers = _case(
        tmp_path, proceeds="60.00", duplicate_disposal=True
    )

    with pytest.raises(OrdinaryTradeDeclarationMvpError) as blocked:
        _run(runtime, context)

    assert blocked.value.code == "ordinary_trade_declaration_disposal_binding_required"


def test_whole_active_canonical_document_without_projection_blocks_before_xml(
    tmp_path: Path,
) -> None:
    runtime, context, _providers, store = _case(
        tmp_path, proceeds="60.00", include_store=True
    )
    bridge = assembly_fixtures.bridge_fixtures
    second = bridge.ordinary_fixtures.gate4_fixtures._activate_canonical(
        store=store,
        context=context,
        document_id="g4-runtime-second-document",
        artifact_version=1,
        expected_previous_version_id=None,
        table_rows=(
            bridge._HEADERS,
            bridge._row(side=bridge._PURCHASE_SIDE, charges=False),
            assembly_fixtures._with_amount(
                bridge._row(side=bridge._DISPOSAL_SIDE, charges=True), "64.00"
            ),
        ),
    )

    missing = runtime.run(canonical_artifact_refs=[], context=context)
    assert missing["declaration"] is None
    assert missing["product"]["xml_created"] is False
    assert missing["product"]["terminal"] == (
        "ordinary_trade_declaration_canonical_projection_missing"
    )

    complete = runtime.run(
        canonical_artifact_refs=[second.artifact_ref],
        context=context,
    )
    assert complete["documents_total"] == 3
    assert complete["product"]["gate4"]["security_facts_total"] == 4
    assert complete["declaration"] is None
    assert complete["product"]["xml_created"] is False
    assert complete["product"]["terminal"] == (
        "ordinary_trade_declaration_disposal_binding_required"
    )


def test_relevant_unmapped_incomplete_operation_blocks_before_xml(
    tmp_path: Path,
) -> None:
    runtime, context, _providers = _case(
        tmp_path,
        proceeds="60.00",
        extra_incomplete_operation=True,
    )

    result = runtime.run(canonical_artifact_refs=[], context=context)

    assert result["declaration"] is None
    assert result["product"]["xml_created"] is False
    assert result["product"]["terminal"] == (
        "ordinary_trade_declaration_canonical_relevant_unmapped"
    )
    assert result["product"]["gate4"]["security_facts_total"] == 2
    assert result["system_identity"]["canonical_coverage_sha256"]


def test_missing_request_bound_human_facts_cannot_be_replaced_by_provider_dict(
    tmp_path: Path,
) -> None:
    runtime, context, _providers = _case(
        tmp_path,
        proceeds="60.00",
        publish_human_facts=False,
    )

    result = runtime.run(canonical_artifact_refs=[], context=context)

    assert result["declaration"] is None
    assert result["product"]["status"] == "INPUT_REQUIRED"
    assert result["product"]["terminal"] == (
        "ordinary_trade_declaration_user_input_required"
    )
    assert result["product"]["xml_created"] is False


def test_correction_without_owner_produced_number_is_typed_blocked(
    tmp_path: Path,
) -> None:
    runtime, context, providers = _case(
        tmp_path,
        proceeds="60.00",
        publish_human_facts=False,
    )
    _publish_human_facts(
        providers[2],
        store=runtime._store,
        context=context,
        taxpayer_scope_ref=primary_taxpayer_scope_ref(context=context),
        answer_overrides={
            "filing_instance_identity": {"kind": "code", "value": "CORRECTION"}
        },
    )

    result = runtime.run(canonical_artifact_refs=[], context=context)
    assert result["declaration"] is None
    assert result["product"]["xml_created"] is False
    assert result["product"]["terminal"] == (
        "ordinary_trade_declaration_correction_number_required"
    )


def test_unsupported_authoritative_taxpayer_capacity_is_methodology_blocked(
    tmp_path: Path,
) -> None:
    runtime, context, providers, store = _case(
        tmp_path,
        proceeds="60.00",
        publish_human_facts=False,
        include_store=True,
    )
    _publish_human_facts(
        providers[2],
        store=store,
        context=context,
        taxpayer_scope_ref=primary_taxpayer_scope_ref(context=context),
        answer_overrides={
            "taxpayer_capacity": {
                "kind": "code",
                "value": "individual_entrepreneur",
            }
        },
    )

    result = runtime.run(canonical_artifact_refs=[], context=context)
    assert result["declaration"] is None
    assert result["product"]["xml_created"] is False
    assert result["product"]["terminal"] == (
        "ordinary_trade_declaration_scenario_unsupported"
    )


def test_xml_projection_extracts_representation_without_tax_formula() -> None:
    source = inspect.getsource(xml_projection_module._supported_profile_xml_values)
    assert "0.13" not in source
    assert "ROUND_HALF_UP" not in source
    assert "expected_tax" not in source


def test_same_case_canonical_fact_successor_60_to_64_invalidates_old_output(
    tmp_path: Path,
) -> None:
    runtime_a, context_a, _providers, store = _case(
        tmp_path / "a", proceeds="60.00", include_store=True
    )
    first = _run(runtime_a, context_a)
    bridge = assembly_fixtures.bridge_fixtures
    projection_record, _projection = bridge.OrdinaryTradeProjectionFactory(
        store=store, read_enabled=True
    ).create().current_case(context=context_a)[0]
    active = store.get_active_canonical_version(
        context=context_a,
        document_id=projection_record.document_id,
    )
    context_b = replace(context_a, normalization_run_id="g4-runtime-run-2")
    _publish_human_facts(
        _providers[2],
        store=store,
        context=context_b,
        taxpayer_scope_ref=primary_taxpayer_scope_ref(context=context_b),
    )
    disposal_64 = assembly_fixtures._with_amount(
        bridge._row(side=bridge._DISPOSAL_SIDE, charges=True), "64.00"
    )
    bridge.ordinary_fixtures.gate4_fixtures._activate_canonical(
        store=store,
        context=context_b,
        document_id=projection_record.document_id,
        artifact_version=2,
        expected_previous_version_id=active.canonical_version_id,
        table_rows=(
            bridge._HEADERS,
            bridge._row(side=bridge._PURCHASE_SIDE, charges=False),
            disposal_64,
        ),
    )
    current = store.get_active_canonical_version(
        context=context_b,
        document_id=projection_record.document_id,
    )
    successor_result = runtime_a.run(
        canonical_artifact_refs=[str(current.manifest_ref)],
        context=context_b,
    )
    successor = successor_result["declaration"]
    assert successor is not None
    assert successor["xml_sha256"] != first["xml_sha256"]
    assert (
        successor["authority_bindings"]["fact_set_sha256"]
        != first["authority_bindings"]["fact_set_sha256"]
    )
    successor_xml = etree.fromstring(successor["xml_bytes"])
    assert successor_xml.find(".//РасчНалБаза").get("СумДох") == "64.00"
    with pytest.raises(OrdinaryTradeDeclarationMvpError) as stale:
        runtime_a.validate_current_declaration(result=first, context=context_b)
    assert stale.value.code == "ordinary_trade_declaration_mvp_stale_or_misbound"


def test_cross_run_genuine_xml_hybrid_remains_rejected(tmp_path: Path) -> None:
    runtime_a, context_a, _ = _case(tmp_path / "a", proceeds="60.00")
    first = _run(runtime_a, context_a)

    runtime_b, context_b, _ = _case(tmp_path / "b", proceeds="64.00")
    changed_fact = _run(runtime_b, context_b)
    assert changed_fact["xml_sha256"] != first["xml_sha256"]
    assert (
        changed_fact["authority_bindings"]["fact_set_sha256"]
        != first["authority_bindings"]["fact_set_sha256"]
    )

    hybrid = copy.deepcopy(changed_fact)
    hybrid["xml_bytes"] = first["xml_bytes"]
    hybrid["xml_sha256"] = first["xml_sha256"]
    receipt_base = {
        key: value
        for key, value in hybrid.items()
        if key
        not in {
            "receipt_sha256",
            "receipt_artifact_ref",
            "xml_artifact_ref",
            "xml_bytes",
            "assembly_receipt",
        }
    }
    hybrid["receipt_sha256"] = hashlib.sha256(
        json.dumps(
            receipt_base,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    with pytest.raises(OrdinaryTradeDeclarationMvpError) as mixed:
        runtime_b.validate_current_declaration(result=hybrid, context=context_b)
    assert mixed.value.code == "ordinary_trade_declaration_xml_semantics_invalid"


def test_tax_period_is_explicitly_selected_after_detected_year_is_shown(
    tmp_path: Path,
) -> None:
    runtime, context, _providers = _case(
        tmp_path,
        proceeds="60.00",
        publish_human_facts=False,
        publish_tax_period=False,
    )

    result = runtime.run(canonical_artifact_refs=[], context=context)
    preparation = result["product"]["preparation"]
    action = preparation["user_actions"][0]

    assert result["product"]["status"] == "INPUT_REQUIRED"
    assert action["fact_key"] == "selected_tax_period"
    assert action["semantic_request_key"] == "human_fact:selected_tax_period"
    assert preparation["period_profile"]["selected_tax_period"] is None
    assert preparation["period_profile"]["detected_operation_years"] == ["2025"]
    assert preparation["period_profile"]["profile_support"] == "NOT_EVALUATED"
    assert result["product"]["xml_created"] is False


def test_period_summary_reads_exact_profile_from_xml_projection_owner() -> None:
    assert Gate5FullTargetXmlProjectionRuntimeFactory.create().supported_profile() == {
        "profile_id": "ru_3ndfl_2025_full_target_supplied_case",
        "profile_version": "2026-08-11.0-proof",
        "tax_period": "2025",
        "form": "3-NDFL",
        "knd": "1151020",
        "order": "FNS_ED-7-11/913@_2025-10-20",
        "electronic_format_version": "5.20",
        "xsd_name": "NO_NDFL3_1_033_00_05_20_01.xsd",
        "xsd_sha256": (
            "083128322833dbafb29be0bf919e33b7b362956244b422d34dd554c99a1e4484"
        ),
    }


def test_available_profile_owner_identity_rejects_neutral_sentinel() -> None:
    profile = Gate5FullTargetXmlProjectionRuntimeFactory.create().supported_profile()
    profile["tax_period"] = "0000"

    with pytest.raises(OrdinaryTradeDeclarationCaseInputsError) as rejected:
        OrdinaryTradeDeclarationCaseInputsRuntime(
            metadata=object(),
            human=object(),
            available_profiles=[profile],
        )
    assert rejected.value.code == "ordinary_trade_available_profiles_invalid"


@pytest.mark.parametrize(
    ("mode", "status", "terminal", "surrogate"),
    [
        (
            "ANALYSIS_ONLY",
            "ANALYSIS_ONLY_READY",
            "ordinary_trade_analysis_only_non_filing",
            False,
        ),
        (
            "SURROGATE_DRAFT",
            "NON_FILING_SURROGATE_READY",
            "ordinary_trade_surrogate_draft_non_filing",
            True,
        ),
        (
            "STOP_RESUMABLE",
            "STOPPED_RESUMABLE",
            "ordinary_trade_preparation_stopped_resumable",
            False,
        ),
    ],
)
def test_wrong_year_profile_never_creates_xml_and_requires_explicit_mode(
    tmp_path: Path,
    mode: str,
    status: str,
    terminal: str,
    surrogate: bool,
) -> None:
    runtime, context, _providers = _case(
        tmp_path / mode.lower(),
        proceeds="60.00",
        publish_human_facts=False,
        publish_tax_period=False,
    )
    first = runtime.run(canonical_artifact_refs=[], context=context)
    period_action = first["product"]["preparation"]["user_actions"][0]
    runtime.normalize_declaration_action(
        request_publication_ref=period_action["request_publication_ref"],
        answer={"kind": "code", "value": "2022"},
        context=context,
    )

    mismatch = runtime.run(canonical_artifact_refs=[], context=context)
    mismatch_action = mismatch["product"]["preparation"]["user_actions"][0]
    assert mismatch_action["fact_key"] == "profile_mismatch_mode"
    assert mismatch["product"]["preparation"]["period_profile"] == {
        "selected_tax_period": "2022",
        "detected_operation_years": ["2025"],
        "document_period_status": "NOT_PROVEN_BY_CURRENT_FACT_CONTRACT",
        "evidence_horizon_status": "OBSERVED_BOUNDS_ONLY",
        "profile_support": "UNSUPPORTED_EXACT_YEAR_PROFILE",
        "profile_mismatch_mode": None,
        "available_profiles": [
            Gate5FullTargetXmlProjectionRuntimeFactory.create().supported_profile()
        ],
        "form_version": None,
        "xsd_name": None,
        "methodology_version": None,
        "filing_profile_available": False,
        "xml_profile_available": False,
    }
    runtime.normalize_declaration_action(
        request_publication_ref=mismatch_action["request_publication_ref"],
        answer={"kind": "code", "value": mode},
        context=context,
    )

    final = runtime.run(canonical_artifact_refs=[], context=context)
    preparation = final["product"]["preparation"]

    assert final["product"]["status"] == status
    assert final["product"]["terminal"] == terminal
    assert final["product"]["xml_created"] is False
    assert final["product"]["declaration_ready"] is False
    assert final["declaration"] is None
    assert preparation["period_profile"]["selected_tax_period"] == "2022"
    assert preparation["period_profile"]["profile_mismatch_mode"] == mode
    assert preparation["analysis"]["surrogate"] is surrogate
    assert preparation["analysis"]["filing_eligible"] is False
    assert preparation["final_note"]["selected_tax_period"] == "2022"
    assert preparation["final_note"]["filing_eligible"] is False
    assert preparation["final_note"]["xml_created"] is False
    if mode == "ANALYSIS_ONLY":
        assert preparation["analysis"]["analysis_mode"] == "DOCUMENT_ANALYSIS_ONLY"
        assert "surrogate_preview" not in preparation
        assert "resume_state" not in preparation
    elif mode == "SURROGATE_DRAFT":
        preview = preparation["surrogate_preview"]
        assert preview["profile_id"] == "ru_3ndfl_2025_full_target_supplied_case"
        assert preview["selected_tax_period"] == "2022"
        assert preview["profile_tax_period"] == "2025"
        assert preview["period_mismatch"] is True
        assert preview["confirmed_fields"]["broker_inn"] == "7707083893"
        assert preview["placeholders"]
        assert preview["checks"]
        assert "not a declaration" in preview["non_filing_warning"]
        assert preview["filing_eligible"] is False
        assert preview["xml_created"] is False
        assert preview["download_available"] is False
        assert "xml_bytes" not in preview
        assert "download" not in preview
    else:
        assert preparation["resume_state"]["status"] == "PAUSED_BY_USER"
        assert "surrogate_preview" not in preparation


def test_exact_profile_methodology_failure_keeps_owner_reason(
    tmp_path: Path,
) -> None:
    runtime, context, _providers = _case(
        tmp_path,
        proceeds="60.00",
        publish_human_facts=False,
    )

    class InvalidMethodology:
        def resolve_ordinary_trade_declaration_product(self, **_kwargs):
            raise Gate5TrustedMethodologyError(
                "gate5_ordinary_trade_product_methodology_invalid"
            )

    runtime._declaration._case_inputs._methodology = InvalidMethodology()
    result = runtime.run(canonical_artifact_refs=[], context=context)
    preparation = result["product"]["preparation"]

    assert result["product"]["status"] == "PREPARATION_INCOMPLETE"
    assert result["product"]["terminal"] == (
        "gate5_ordinary_trade_product_methodology_invalid"
    )
    assert preparation["period_profile"]["profile_support"] == "SUPPORTED"
    assert preparation["user_actions"]
    assert all(
        item["fact_key"] != "profile_mismatch_mode"
        for item in preparation["user_actions"]
    )


def test_exact_profile_source_assertion_mismatch_keeps_exact_blocker(
    tmp_path: Path,
) -> None:
    mismatched = tuple(
        line.replace("ADMITTED", "NOT_ADMITTED") for line in _METADATA_LINES
    )
    runtime, context, _providers = _case(
        tmp_path,
        proceeds="60.00",
        publish_human_facts=False,
        metadata_lines=mismatched,
    )

    result = runtime.run(canonical_artifact_refs=[], context=context)
    preparation = result["product"]["preparation"]

    assert result["product"]["terminal"] == (
        "gate5_ordinary_trade_product_source_evidence_unresolved"
    )
    assert preparation["period_profile"]["profile_support"] == "SUPPORTED"
    assert preparation["internal_blockers"][0]["owner"] == (
        "Gate5TrustedMethodologyAuthority"
    )
    assert preparation["internal_blockers"][0]["gap_owner_classification"] == (
        "REAL_SOURCE_EVIDENCE_MISSING"
    )
    assert all(
        item["fact_key"] != "profile_mismatch_mode"
        for item in preparation["user_actions"]
    )


def test_neutral_period_sentinel_is_never_a_user_tax_period(tmp_path: Path) -> None:
    runtime, context, _providers = _case(
        tmp_path,
        proceeds="60.00",
        publish_human_facts=False,
        publish_tax_period=False,
    )
    action = runtime.run(canonical_artifact_refs=[], context=context)["product"][
        "preparation"
    ]["user_actions"][0]

    with pytest.raises(Gate5HumanGapClosureError) as rejected:
        runtime.normalize_declaration_action(
            request_publication_ref=action["request_publication_ref"],
            answer={"kind": "code", "value": "0000"},
            context=context,
        )
    assert rejected.value.code == "gate5_tax_period_neutral_sentinel_forbidden"


def test_same_case_period_choice_can_be_corrected_to_supported_successor(
    tmp_path: Path,
) -> None:
    runtime, context, _providers = _case(
        tmp_path,
        proceeds="60.00",
        publish_human_facts=False,
        publish_tax_period=False,
    )
    first_action = runtime.run(canonical_artifact_refs=[], context=context)["product"][
        "preparation"
    ]["user_actions"][0]
    first_fact = runtime.normalize_declaration_action(
        request_publication_ref=first_action["request_publication_ref"],
        answer={"kind": "code", "value": "2022"},
        context=context,
    )["typed_user_case_fact"]
    mismatch = runtime.run(canonical_artifact_refs=[], context=context)
    old_mode_action = mismatch["product"]["preparation"]["user_actions"][0]

    successor_action = runtime.publish_declaration_change_action(
        fact_key="selected_tax_period",
        context=context,
    )
    assert successor_action["scope_binding"]["tax_period"] == "0000"
    assert successor_action["answer_contract"][
        "change_of_user_case_fact_ref"
    ] == first_fact["user_case_fact_ref"]
    runtime.normalize_declaration_action(
        request_publication_ref=successor_action["request_publication_ref"],
        answer={"kind": "code", "value": "2025"},
        context=context,
    )

    corrected = runtime.run(canonical_artifact_refs=[], context=context)
    preparation = corrected["product"]["preparation"]
    assert preparation["period_profile"]["selected_tax_period"] == "2025"
    assert preparation["period_profile"]["profile_support"] == "SUPPORTED"
    assert all(
        item["fact_key"] != "profile_mismatch_mode"
        for item in preparation["user_actions"]
    )
    with pytest.raises(Gate5HumanGapClosureError) as stale_period:
        runtime.normalize_declaration_action(
            request_publication_ref=first_action["request_publication_ref"],
            answer={"kind": "code", "value": "2022"},
            context=context,
        )
    assert stale_period.value.code == "gate5_gap_request_stale"
    with pytest.raises(Gate5HumanGapClosureError) as stale_mode:
        runtime.normalize_declaration_action(
            request_publication_ref=old_mode_action["request_publication_ref"],
            answer={"kind": "code", "value": "ANALYSIS_ONLY"},
            context=context,
        )
    assert stale_mode.value.code == "gate5_gap_request_stale"
    still_corrected = runtime.run(canonical_artifact_refs=[], context=context)
    assert still_corrected["product"]["preparation"]["period_profile"][
        "selected_tax_period"
    ] == "2025"

    return_action = runtime.publish_declaration_change_action(
        fact_key="selected_tax_period",
        context=context,
    )
    runtime.normalize_declaration_action(
        request_publication_ref=return_action["request_publication_ref"],
        answer={"kind": "code", "value": "2022"},
        context=context,
    )
    returned = runtime.run(canonical_artifact_refs=[], context=context)
    returned_preparation = returned["product"]["preparation"]
    assert returned["product"]["status"] == "INPUT_REQUIRED"
    assert returned_preparation["period_profile"]["selected_tax_period"] == "2022"
    assert returned_preparation["period_profile"]["profile_mismatch_mode"] is None
    fresh_mode_action = returned_preparation["user_actions"][0]
    assert fresh_mode_action["fact_key"] == "profile_mismatch_mode"
    assert fresh_mode_action["request_publication_ref"] != (
        old_mode_action["request_publication_ref"]
    )


def test_same_case_profile_mode_can_be_changed_by_owner_successor(
    tmp_path: Path,
) -> None:
    runtime, context, _providers = _case(
        tmp_path,
        proceeds="60.00",
        publish_human_facts=False,
        publish_tax_period=False,
    )
    period_action = runtime.run(canonical_artifact_refs=[], context=context)["product"][
        "preparation"
    ]["user_actions"][0]
    runtime.normalize_declaration_action(
        request_publication_ref=period_action["request_publication_ref"],
        answer={"kind": "code", "value": "2022"},
        context=context,
    )
    mismatch = runtime.run(canonical_artifact_refs=[], context=context)
    mode_action = mismatch["product"]["preparation"]["user_actions"][0]
    assert "ru_3ndfl_2025_full_target_supplied_case" in mode_action["question"]
    first_mode = runtime.normalize_declaration_action(
        request_publication_ref=mode_action["request_publication_ref"],
        answer={"kind": "code", "value": "ANALYSIS_ONLY"},
        context=context,
    )["typed_user_case_fact"]

    successor_action = runtime.publish_declaration_change_action(
        fact_key="profile_mismatch_mode",
        context=context,
    )
    assert successor_action["scope_binding"]["tax_period"] == "2022"
    assert successor_action["answer_contract"][
        "change_of_user_case_fact_ref"
    ] == first_mode["user_case_fact_ref"]
    runtime.normalize_declaration_action(
        request_publication_ref=successor_action["request_publication_ref"],
        answer={"kind": "code", "value": "STOP_RESUMABLE"},
        context=context,
    )

    changed = runtime.run(canonical_artifact_refs=[], context=context)
    assert changed["product"]["status"] == "STOPPED_RESUMABLE"
    assert changed["product"]["preparation"]["period_profile"][
        "profile_mismatch_mode"
    ] == "STOP_RESUMABLE"
    with pytest.raises(Gate5HumanGapClosureError) as stale_mode:
        runtime.normalize_declaration_action(
            request_publication_ref=mode_action["request_publication_ref"],
            answer={"kind": "code", "value": "ANALYSIS_ONLY"},
            context=context,
        )
    assert stale_mode.value.code == "gate5_gap_request_stale"


def test_purchase_only_2022_keeps_open_position_separate_from_profile_choice(
    tmp_path: Path,
) -> None:
    bridge = assembly_fixtures.bridge_fixtures
    purchase = bridge._with_roles(
        bridge._row(side=bridge._PURCHASE_SIDE, charges=False),
        trade_date="10.01.2022 10:00:00",
        settlement_date="13.01.2022",
    )
    runtime, context, _providers = _case(
        tmp_path,
        proceeds="60.00",
        publish_human_facts=False,
        publish_tax_period=False,
        financial_rows=(bridge._HEADERS, purchase),
    )

    first = runtime.run(canonical_artifact_refs=[], context=context)
    first_preparation = first["product"]["preparation"]
    group = first["product"]["gate5"]["security_groups"][0]

    assert first["product"]["status"] == "INPUT_REQUIRED"
    assert first["product"]["gate5"]["execution_status"] == (
        "open_position_not_tax_activated"
    )
    assert first["product"]["gate5"]["blocker_reason_codes"] == []
    assert group["position_scope"]["state"] == "OPEN_LONG_PROVEN"
    assert first_preparation["final_note"]["detected_operation_years"] == [
        "2022"
    ]
    period_action = first_preparation["user_actions"][0]
    assert period_action["fact_key"] == "selected_tax_period"
    runtime.normalize_declaration_action(
        request_publication_ref=period_action["request_publication_ref"],
        answer={"kind": "code", "value": "2022"},
        context=context,
    )

    mismatch = runtime.run(canonical_artifact_refs=[], context=context)
    mode_action = mismatch["product"]["preparation"]["user_actions"][0]
    assert mode_action["fact_key"] == "profile_mismatch_mode"
    runtime.normalize_declaration_action(
        request_publication_ref=mode_action["request_publication_ref"],
        answer={"kind": "code", "value": "ANALYSIS_ONLY"},
        context=context,
    )

    final = runtime.run(canonical_artifact_refs=[], context=context)
    note = final["product"]["preparation"]["final_note"]
    assert final["product"]["status"] == "ANALYSIS_ONLY_READY"
    assert note["selected_tax_period"] == "2022"
    assert note["profile"]["support"] == "UNSUPPORTED_EXACT_YEAR_PROFILE"
    assert note["positions"][0]["state"] == "OPEN_LONG_PROVEN"
    assert note["calculated_disposal_fact_ids"] == []
    assert note["filing_eligible"] is False
    assert final["product"]["xml_created"] is False


def test_sale_only_supported_period_retains_exact_evidence_horizon_blocker(
    tmp_path: Path,
) -> None:
    bridge = assembly_fixtures.bridge_fixtures
    runtime, context, _providers = _case(
        tmp_path,
        proceeds="60.00",
        publish_human_facts=False,
        financial_rows=(
            bridge._HEADERS,
            bridge._row(side=bridge._DISPOSAL_SIDE, charges=False),
        ),
    )

    result = runtime.run(canonical_artifact_refs=[], context=context)
    product = result["product"]
    note = product["preparation"]["final_note"]

    assert product["status"] == "PREPARATION_INCOMPLETE"
    assert product["terminal"] == (
        "gate5_source_fact_acquisition_evidence_horizon_unproven"
    )
    assert product["gate5"]["blocker_reason_codes"] == [
        "gate5_source_fact_acquisition_evidence_horizon_unproven"
    ]
    assert note["positions"][0]["state"] == (
        "UNRESOLVED_DISPOSAL_EVIDENCE_HORIZON"
    )
    assert note["filing_eligible"] is False
    assert product["xml_created"] is False


def test_same_case_operation_year_successor_stales_old_period_choice(
    tmp_path: Path,
) -> None:
    bridge = assembly_fixtures.bridge_fixtures
    document_id = "ordinary-trade-candidate-document"
    purchase_2022 = bridge._with_roles(
        bridge._row(side=bridge._PURCHASE_SIDE, charges=False),
        trade_date="10.01.2022 10:00:00",
        settlement_date="13.01.2022",
    )
    runtime, context, _providers, store = _case(
        tmp_path,
        proceeds="60.00",
        include_store=True,
        publish_human_facts=False,
        publish_tax_period=False,
        financial_rows=(bridge._HEADERS, purchase_2022),
    )
    first = runtime.run(canonical_artifact_refs=[], context=context)
    old_action = first["product"]["preparation"]["user_actions"][0]
    runtime.normalize_declaration_action(
        request_publication_ref=old_action["request_publication_ref"],
        answer={"kind": "code", "value": "2022"},
        context=context,
    )
    active = next(
        item
        for item in store.list_canonical_versions(
            context=context,
            document_id=document_id,
        )
        if item.status == "ACTIVE"
    )
    purchase_2024 = bridge._with_roles(
        purchase_2022,
        trade_date="10.01.2024 10:00:00",
        settlement_date="13.01.2024",
    )
    successor_context = replace(
        context,
        normalization_run_id="ordinary-trade-operation-period-successor",
    )
    assembly_fixtures.bridge_fixtures.ordinary_fixtures.gate4_fixtures._activate_canonical(
        store=store,
        context=successor_context,
        document_id=document_id,
        artifact_version=2,
        expected_previous_version_id=active.canonical_version_id,
        table_rows=(bridge._HEADERS, purchase_2024),
    )
    successor = next(
        item
        for item in store.list_canonical_versions(
            context=successor_context,
            document_id=document_id,
        )
        if item.status == "ACTIVE"
    )

    changed = runtime.run(
        canonical_artifact_refs=[str(successor.manifest_ref)],
        context=successor_context,
    )
    changed_preparation = changed["product"]["preparation"]

    assert changed["product"]["status"] == "INPUT_REQUIRED"
    assert changed_preparation["period_profile"]["detected_operation_years"] == [
        "2024"
    ]
    assert changed_preparation["period_profile"]["selected_tax_period"] is None
    assert changed_preparation["user_actions"][0]["semantic_request_key"] == (
        old_action["semantic_request_key"]
    )
    assert changed_preparation["user_actions"][0]["request_publication_ref"] != (
        old_action["request_publication_ref"]
    )
    with pytest.raises(Exception) as stale:
        runtime.normalize_declaration_action(
            request_publication_ref=old_action["request_publication_ref"],
            answer={"kind": "code", "value": "2022"},
            context=successor_context,
        )
    assert getattr(stale.value, "code", "") == "gate5_gap_request_stale"
    assert changed["product"]["xml_created"] is False


def _case(
    root: Path,
    *,
    proceeds: str,
    include_store: bool = False,
    duplicate_disposal: bool = False,
    extra_incomplete_operation: bool = False,
    publish_human_facts: bool = True,
    publish_tax_period: bool = True,
    metadata_lines: tuple[str, ...] = _METADATA_LINES,
    financial_rows: tuple | None = None,
):
    if financial_rows is not None:
        bridge = assembly_fixtures.bridge_fixtures
        store, context, _facts = bridge._case(root, rows=financial_rows)
    elif duplicate_disposal or extra_incomplete_operation:
        bridge = assembly_fixtures.bridge_fixtures
        disposal = assembly_fixtures._with_amount(
            bridge._row(side=bridge._DISPOSAL_SIDE, charges=True), proceeds
        )
        rows = [
            bridge._HEADERS,
            bridge._row(side=bridge._PURCHASE_SIDE, charges=False),
            disposal,
        ]
        if duplicate_disposal:
            rows.append(disposal)
        if extra_incomplete_operation:
            rows.append(bridge._with_roles(disposal, gross_amount=""))
        store, context, _facts = bridge._case(
            root,
            rows=tuple(rows),
        )
    else:
        store, context, _facts = assembly_fixtures._case(root, proceeds=proceeds)
    retention = build_retention_policy(mode="synthetic_dev")
    assembly_fixtures.bridge_fixtures.ordinary_fixtures.gate4_fixtures._activate_canonical(
        store=store,
        context=context,
        document_id="ordinary-trade-declaration-metadata",
        artifact_version=1,
        expected_previous_version_id=None,
        source_rows=metadata_lines,
    )
    OrdinaryTradeProjectionFactory(
        store=store, read_enabled=True
    ).create().compile_and_save(
        document_id="ordinary-trade-declaration-metadata",
        context=context,
    )
    human = Gate5HumanGapClosureRuntimeFactory.create(
        store=store,
        retention_policy=retention,
    )
    if publish_tax_period:
        selection = human.publish_tax_period_selection_request(
            context=context,
            taxpayer_scope_ref=primary_taxpayer_scope_ref(context=context),
            detected_operation_years=["2025"],
        )
        if selection["actions"]:
            selected = human.normalize_published_answer(
                request_publication_ref=selection["actions"][0][
                    "request_publication_ref"
                ],
                answer={"kind": "code", "value": "2025"},
                context=context,
            )
            assert selected["status"] == "TYPED_USER_CASE_FACT_READY"
    if publish_human_facts:
        _publish_human_facts(
            human,
            store=store,
            context=context,
            taxpayer_scope_ref=primary_taxpayer_scope_ref(context=context),
        )
    runtime = OrdinaryTradeProductionRuntimeFactory(
        store=store,
        read_enabled=True,
        retention_policy=retention,
    ).create()
    result = (runtime, context, (None, None, human))
    return (*result, store) if include_store else result


def _publish_human_facts(
    human,
    *,
    store,
    context,
    taxpayer_scope_ref: str,
    answer_overrides: dict[str, dict] | None = None,
) -> None:
    retention = build_retention_policy(mode="synthetic_dev")
    coverage = OrdinaryTradeProjectionFactory(
        store=store, read_enabled=True
    ).create().current_case_coverage(context=context)
    owner = OrdinaryTradeDeclarationCaseInputsRuntimeFactory(
        store=store,
        read_enabled=True,
        retention_policy=retention,
    ).create()
    source_assembly = OrdinaryTradeCandidateRuntimeFactory(
        store=store, read_enabled=True
    ).create().assemble_available(
        methodology_ref={
            "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
            "methodology_id": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
            "methodology_version": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
        },
        context=context,
    )
    published = owner.current(
        context=context,
        canonical_coverage=coverage,
        operation_period_observation=source_assembly[
            "operation_period_observation"
        ],
    )
    requests = published["human_fact_publication"]["actions"]
    for request in requests:
        result = human.normalize_answer(
            request=request,
            answer=(answer_overrides or {}).get(
                request["fact_key"], _product_answer(request["fact_key"])
            ),
            context=context,
        )
        assert result["status"] == "TYPED_USER_CASE_FACT_READY"


def _run(runtime, context) -> dict:
    result = runtime.run(canonical_artifact_refs=[], context=context)
    if result["declaration"] is None:
        raise OrdinaryTradeDeclarationMvpError(result["product"]["terminal"])
    return result["declaration"]


def _product_answer(fact_key: str) -> dict:
    if fact_key == "taxpayer_identity":
        return {
            "kind": "identity_choice",
            "value": {"choice": "CONFIRM", "identity": None},
        }
    if fact_key == "taxpayer_capacity":
        return {
            "kind": "code",
            "value": "individual_not_ip_not_private_practice",
        }
    if fact_key == "filing_destination_code":
        return {"kind": "code", "value": "7705"}
    if fact_key == "budget_oktmo":
        return {"kind": "code", "value": "45382000"}
    return human_fixtures._answer(fact_key)
