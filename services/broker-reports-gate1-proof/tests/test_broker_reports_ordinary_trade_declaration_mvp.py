from __future__ import annotations

import copy
import hashlib
import json
import base64
from dataclasses import replace
from importlib import resources

from lxml import etree
from pathlib import Path

import pytest

from broker_reports_gate1.artifact_retention import build_retention_policy
from broker_reports_gate1.authenticated_case_taxpayer_binding import (
    AUTHENTICATED_CASE_TAXPAYER_ASSERTION_SCHEMA_VERSION,
)
from broker_reports_gate1.gate5_human_gap_closure import (
    Gate5HumanGapClosureRuntimeFactory,
)
from broker_reports_gate1.gate5_full_target_xml_projection import (
    Gate5FullTargetXmlProjectionRuntimeFactory,
)
from broker_reports_gate1.ordinary_trade_declaration_mvp import (
    DECLARATION_EXTERNAL_AUTHORITY_SCHEMA_VERSION,
    ORDINARY_TRADE_DECLARATION_MVP_TERMINAL,
    OrdinaryTradeDeclarationMvpError,
)
from broker_reports_gate1.ordinary_trade_production_runtime import (
    OrdinaryTradeProductionRuntimeFactory,
)

import test_broker_reports_active_category_declaration_assembly as assembly_fixtures
import test_broker_reports_gate5_human_fact_scope as human_fixtures


class IdentityProvider:
    def __init__(self, value: dict) -> None:
        self.value = value

    def current_assertions(self, *, context):
        return (copy.deepcopy(self.value),)


class ExternalFactsProvider:
    def __init__(self, value: dict) -> None:
        self.value = value

    def current_facts(self, *, context):
        return copy.deepcopy(self.value)


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
    assert first["taxpayer_scope_ref"] == "taxpayer-authenticated-1"
    assert first["taxpayer_scope_ref"] != "security-disposal-1"
    assert first["semantic_accounting"]["mapping_occurrences_total"] == 49
    assert len(first["authority_bindings"]["user_case_fact_refs"]) == 7
    assert "user_facts_artifact_ref" not in first["authority_bindings"]
    assert first["authority_bindings"]["canonical_coverage_ref"].startswith(
        "ordinary_trade_coverage_"
    )
    assert first["semantic_reconciliation"]["status"] == "passed"
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


def test_only_production_factory_activates_the_mvp_adapter(tmp_path: Path) -> None:
    _runtime, context, providers, store = _case(
        tmp_path, proceeds="60.00", include_store=True
    )
    identity, external, _human = providers
    production = OrdinaryTradeProductionRuntimeFactory(
        store=store,
        read_enabled=True,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
        identity_provider=identity,
        external_authority_provider=external,
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


def test_review_fixture_is_official_xsd_valid_and_semantically_reconciled() -> None:
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
    semantic = (
        Gate5FullTargetXmlProjectionRuntimeFactory.create()
        .validate_supported_profile_semantics(xml_bytes=fixture.read_bytes())
    )
    assert semantic["status"] == "passed"
    assert semantic["values"] == {
        "gross_income": "60.00",
        "accepted_expenses": "43.00",
        "tax_base": "17.00",
        "calculated_tax": "2",
        "tax_payable": "2",
        "tax_refundable": "0",
        "source_income": "60.00",
        "budget_payable": "2",
    }


@pytest.mark.parametrize(
    ("path", "attribute", "value"),
    [
        (".//РасчНалБаза", "НалБаза", "18.00"),
        (".//РасчНалПУ", "Исчисл", "3"),
        (".//РасчНалПУ", "ПодлУпл", "3"),
        (".//СумНалПуИскл227", "ПодлУпл", "3"),
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


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("foreign_taxpayer", "authenticated_taxpayer_binding_context_mismatch"),
        ("foreign_external", "ordinary_trade_declaration_external_authority_invalid"),
        ("missing_inspection", "ordinary_trade_declaration_external_authority_invalid"),
        ("unsupported_iis", "ordinary_trade_declaration_external_authority_invalid"),
        ("cross_period", "ordinary_trade_declaration_external_authority_invalid"),
    ],
)
def test_identity_authority_and_unsupported_inputs_fail_closed(
    tmp_path: Path, mutation: str, code: str
) -> None:
    runtime, context, providers = _case(tmp_path, proceeds="60.00")
    identity, external, _human = providers
    if mutation == "foreign_taxpayer":
        identity.value["case_id"] = "foreign-case"
    elif mutation == "foreign_external":
        external.value["case_id"] = "foreign-case"
    elif mutation == "missing_inspection":
        external.value["filing_destination"]["code"] = ""
    elif mutation == "unsupported_iis":
        external.value["operation_applicability"]["iis_status"] = "inside_iis"
    elif mutation == "cross_period":
        external.value["tax_period"] = "2024"

    with pytest.raises(Exception) as error:
        _run(runtime, context)
    assert getattr(error.value, "code", str(error.value)) == code


def test_multiple_disposals_are_not_silently_duplicated_or_dropped(
    tmp_path: Path,
) -> None:
    runtime, context, _providers = _case(
        tmp_path, proceeds="60.00", duplicate_disposal=True
    )

    with pytest.raises(OrdinaryTradeDeclarationMvpError) as blocked:
        _run(runtime, context)

    assert blocked.value.code == "ordinary_trade_declaration_disposal_binding_required"


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
    assert result["product"]["terminal"] == (
        "ordinary_trade_declaration_human_facts_missing"
    )
    assert result["product"]["xml_created"] is False


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
        context=context_b,
        taxpayer_scope_ref="taxpayer-authenticated-1",
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
    assert mixed.value.code == "ordinary_trade_declaration_mvp_stale_or_misbound"


def _case(
    root: Path,
    *,
    proceeds: str,
    include_store: bool = False,
    duplicate_disposal: bool = False,
    extra_incomplete_operation: bool = False,
    publish_human_facts: bool = True,
):
    if duplicate_disposal or extra_incomplete_operation:
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
    identity = IdentityProvider(_identity(context))
    external = ExternalFactsProvider(_external(context))
    retention = build_retention_policy(mode="synthetic_dev")
    human = Gate5HumanGapClosureRuntimeFactory.create(
        store=store,
        retention_policy=retention,
    )
    if publish_human_facts:
        _publish_human_facts(
            human,
            context=context,
            taxpayer_scope_ref="taxpayer-authenticated-1",
        )
    runtime = OrdinaryTradeProductionRuntimeFactory(
        store=store,
        read_enabled=True,
        retention_policy=retention,
        identity_provider=identity,
        external_authority_provider=external,
    ).create()
    result = (runtime, context, (identity, external, human))
    return (*result, store) if include_store else result


def _publish_human_facts(human, *, context, taxpayer_scope_ref: str) -> None:
    published = human.publish_requests(
        **human_fixtures._plan_inputs(
            context,
            taxpayer_scope_ref=taxpayer_scope_ref,
        )
    )
    requests = [
        *published["required_actions"],
        *published["deferred_actions"],
    ]
    for request in requests:
        if request["closure_type"] != "USER_FACT":
            continue
        result = human.normalize_answer(
            request=request,
            answer=human_fixtures._answer(request["fact_key"]),
            context=context,
        )
        assert result["status"] == "TYPED_USER_CASE_FACT_READY"


def _run(runtime, context) -> dict:
    result = runtime.run(canonical_artifact_refs=[], context=context)
    if result["declaration"] is None:
        raise OrdinaryTradeDeclarationMvpError(result["product"]["terminal"])
    return result["declaration"]


def _identity(context) -> dict:
    return {
        "schema_version": AUTHENTICATED_CASE_TAXPAYER_ASSERTION_SCHEMA_VERSION,
        "assertion_id": "authenticated-taxpayer-assertion-1",
        "authenticated_user_id": context.user_id,
        "case_id": context.case_id,
        "taxpayer_scope_ref": "taxpayer-authenticated-1",
        "taxpayer": {
            "inn": "500100732259",
            "last_name": "Иванов",
            "first_name": "Иван",
            "middle_name": "Иванович",
        },
        "origin": {
            "kind": "authenticated_identity_provider",
            "provider_id": "openwebui-authenticated-case-owner",
        },
    }


def _external(context) -> dict:
    return {
        "schema_version": DECLARATION_EXTERNAL_AUTHORITY_SCHEMA_VERSION,
        "publication_id": "official-case-authority-2025-1",
        "case_id": context.case_id,
        "tax_period": "2025",
        "operation_applicability": {
            "organized_market_status": "organized_market",
            "iis_status": "outside_iis",
            "exemption_applicability": "not_applicable",
        },
        "filing_destination": {"ref": "inspection-7705", "code": "7705"},
        "income_source": {
            "source_ref": "broker-source-1",
            "jurisdiction_kind": "russian_source",
            "jurisdiction_code": "RU",
            "income_kind": "securities_disposal",
            "source_party": {
                "party_kind": "organization",
                "display_name": "АО Тестовый брокер",
                "inn": "7707083893",
                "kpp": "773601001",
                "oktmo": "45382000",
            },
        },
        "budget": {
            "source_ref": "fns-budget-2025-1",
            "budget_allocation_ref": "budget-allocation-2025-1",
            "kbk": "18210102030011000110",
            "oktmo": "45382000",
        },
        "origin": {
            "kind": "external_authority_provider",
            "provider_id": "fns-case-reference-owner",
        },
    }
