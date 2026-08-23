from __future__ import annotations

import copy
import hashlib
import json
import base64
from importlib import resources

from lxml import etree
from pathlib import Path

import pytest

from broker_reports_gate1.artifact_retention import build_retention_policy
from broker_reports_gate1.authenticated_case_taxpayer_binding import (
    AUTHENTICATED_CASE_TAXPAYER_ASSERTION_SCHEMA_VERSION,
)
from broker_reports_gate1.ordinary_trade_declaration_mvp import (
    AUTHENTICATED_DECLARATION_FACTS_SCHEMA_VERSION,
    DECLARATION_EXTERNAL_AUTHORITY_SCHEMA_VERSION,
    ORDINARY_TRADE_DECLARATION_MVP_TERMINAL,
    OrdinaryTradeDeclarationMvpError,
)
from broker_reports_gate1.ordinary_trade_production_runtime import (
    OrdinaryTradeProductionRuntimeFactory,
)

import test_broker_reports_active_category_declaration_assembly as assembly_fixtures


class IdentityProvider:
    def __init__(self, value: dict) -> None:
        self.value = value

    def current_assertions(self, *, context):
        return (copy.deepcopy(self.value),)


class UserFactsProvider:
    def __init__(self, value: dict) -> None:
        self.value = value

    def current_facts(self, *, context):
        return copy.deepcopy(self.value)


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
    identity, user, external = providers
    production = OrdinaryTradeProductionRuntimeFactory(
        store=store,
        read_enabled=True,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
        identity_provider=identity,
        user_facts_provider=user,
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


def test_xsd_valid_but_semantically_changed_xml_is_not_current(tmp_path: Path) -> None:
    runtime, context, _providers = _case(tmp_path, proceeds="60.00")
    result = _run(runtime, context)
    changed = result["xml_bytes"].replace(
        'НалБаза="17.00"'.encode("windows-1251"),
        'НалБаза="18.00"'.encode("windows-1251"),
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
    assert invalid.value.code == "ordinary_trade_declaration_mvp_stale_or_misbound"


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("foreign_taxpayer", "authenticated_taxpayer_binding_context_mismatch"),
        ("foreign_user_facts", "ordinary_trade_declaration_authenticated_facts_invalid"),
        ("foreign_external", "ordinary_trade_declaration_external_authority_invalid"),
        ("missing_inspection", "ordinary_trade_declaration_external_authority_invalid"),
        ("unsupported_iis", "ordinary_trade_declaration_external_authority_invalid"),
        ("cross_period", "ordinary_trade_declaration_authenticated_facts_invalid"),
    ],
)
def test_identity_authority_and_unsupported_inputs_fail_closed(
    tmp_path: Path, mutation: str, code: str
) -> None:
    runtime, context, providers = _case(tmp_path, proceeds="60.00")
    identity, user, external = providers
    if mutation == "foreign_taxpayer":
        identity.value["case_id"] = "foreign-case"
    elif mutation == "foreign_user_facts":
        user.value["taxpayer_scope_ref"] = "foreign-taxpayer"
    elif mutation == "foreign_external":
        external.value["case_id"] = "foreign-case"
    elif mutation == "missing_inspection":
        external.value["filing_destination"]["code"] = ""
    elif mutation == "unsupported_iis":
        external.value["operation_applicability"]["iis_status"] = "inside_iis"
    elif mutation == "cross_period":
        user.value["tax_period"] = "2024"

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


def test_live_fact_and_owner_successors_invalidate_old_output(tmp_path: Path) -> None:
    runtime_a, context_a, providers = _case(tmp_path / "a", proceeds="60.00")
    first = _run(runtime_a, context_a)
    _identity, user, external = providers
    user.value["filing_instance"]["declaration_date"] = "2026-08-24"
    successor = _run(runtime_a, context_a)
    assert successor["xml_sha256"] != first["xml_sha256"]
    with pytest.raises(OrdinaryTradeDeclarationMvpError) as stale:
        runtime_a.validate_current_declaration(result=first, context=context_a)
    assert stale.value.code == "ordinary_trade_declaration_mvp_stale_or_misbound"

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
):
    if duplicate_disposal:
        bridge = assembly_fixtures.bridge_fixtures
        disposal = assembly_fixtures._with_amount(
            bridge._row(side=bridge._DISPOSAL_SIDE, charges=True), proceeds
        )
        store, context, _facts = bridge._case(
            root,
            rows=(
                bridge._HEADERS,
                bridge._row(side=bridge._PURCHASE_SIDE, charges=False),
                disposal,
                disposal,
            ),
        )
    else:
        store, context, _facts = assembly_fixtures._case(root, proceeds=proceeds)
    identity = IdentityProvider(_identity(context))
    user = UserFactsProvider(_user(context))
    external = ExternalFactsProvider(_external(context))
    runtime = OrdinaryTradeProductionRuntimeFactory(
        store=store,
        read_enabled=True,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
        identity_provider=identity,
        user_facts_provider=user,
        external_authority_provider=external,
    ).create()
    result = (runtime, context, (identity, user, external))
    return (*result, store) if include_store else result


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


def _user(context) -> dict:
    residency = assembly_fixtures._right_side(context.user_id)["residency_evidence"]
    return {
        "schema_version": AUTHENTICATED_DECLARATION_FACTS_SCHEMA_VERSION,
        "assertion_id": "authenticated-declaration-facts-1",
        "authenticated_user_id": context.user_id,
        "case_id": context.case_id,
        "taxpayer_scope_ref": "taxpayer-authenticated-1",
        "tax_period": "2025",
        "residency_evidence": {
            "human_answer": residency["human_answer"],
            "proposal": copy.deepcopy(residency["proposal"]),
        },
        "filing_instance": {
            "declaration_instance_ref": "mvp-declaration-2025-initial",
            "correction_kind": "initial",
            "correction_number": 0,
            "declaration_date": "2026-08-23",
        },
        "declarant_category": "other_individual_declaring_article_228_income",
        "signer_capacity": "taxpayer_self",
        "representation_authority": None,
        "income_scope": {
            "other_group_income": "0.00",
            "other_group_allowable_expenses": "0.00",
            "non_taxable_income": "0.00",
            "tax_deductions": "0.00",
            "loss_treatment": "none",
        },
        "credits": {
            "withheld_at_source": "0.00",
            "material_benefit_withheld": "0.00",
            "trade_fee_credit": "0.00",
            "fixed_advance_credit": "0.00",
            "foreign_tax_credit": "0.00",
            "patent_credit": "0.00",
        },
        "simplified_returned_or_credited_amount": "0.00",
        "origin": {
            "kind": "authenticated_user_fact_provider",
            "provider_id": "openwebui-human-fact-owner",
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
