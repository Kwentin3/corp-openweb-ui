from __future__ import annotations

import copy
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from broker_reports_gate1 import gate5_end_to_end_full_target_xml as e2e_module
from broker_reports_gate1.gate5_declaration_income_sources import (
    Gate5DeclarationIncomeSourcesRuntimeFactory,
)
from broker_reports_gate1.gate5_declaration_semantic_input import (
    Gate5DeclarationSemanticInputRuntime,
    Gate5DeclarationSemanticInputRuntimeFactory,
)
from broker_reports_gate1.gate5_end_to_end_full_target_xml import (
    Gate5EndToEndFullTargetXmlError,
)
from broker_reports_gate1.gate5_full_target_xml_projection import (
    Gate5FullTargetXmlProjectionError,
    Gate5FullTargetXmlProjectionRuntimeFactory,
)
import test_broker_reports_gate5_consumer_first_projection as consumer_fixtures
import test_broker_reports_gate5_declaration_income_sources as source_fixtures
import test_broker_reports_gate5_declaration_tax_settlement as income_fixtures
import test_broker_reports_gate5_end_to_end_full_target_xml as e2e_fixtures


_TERMINALS = [
    "DECLARATION_CONSUMER_MODEL_PROVEN",
    "DECLARATION_SEMANTIC_MODEL_COMPLETE",
    "END_TO_END_DECLARATION_ASSEMBLY_PROVEN",
    "DECLARATION_VALUE_TRACEABILITY_PROVEN",
    "CROSS_DOMAIN_DECLARATION_CONSISTENCY_PROVEN",
]
_LEGAL_GAPS = [
    "ambiguous_security_disposal_source_classification",
    "partial_acquisition_commission_allocation",
    "non_rub_intermediate_precision_and_rounding",
    "treaty_specific_foreign_tax_credit_limit",
]


@pytest.fixture()
def complete_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    packages: list[dict] = []
    original = Gate5DeclarationSemanticInputRuntime.compile

    def capture(self, *, package: dict) -> dict:
        packages.append(copy.deepcopy(package))
        return original(self, package=package)

    monkeypatch.setattr(Gate5DeclarationSemanticInputRuntime, "compile", capture)
    result, _ = e2e_fixtures._run(tmp_path, e2e_fixtures._proof_input())
    assert result["status"] == "END_TO_END_FULL_TARGET_XML_VALID"
    assert len(packages) == 1
    return packages[0]


def test_a_i_complete_controlled_case_has_exact_origin_for_every_emitted_value(
    tmp_path: Path,
) -> None:
    receipts: list[dict] = []
    result, _ = e2e_fixtures._run(
        tmp_path,
        e2e_fixtures._proof_input(),
        audit_sink=receipts.append,
    )

    assert result["status"] == "END_TO_END_FULL_TARGET_XML_VALID"
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt["status"] == "DECLARATION_MODEL_ASSEMBLY_PROVEN"
    assert receipt["blockers"] == []
    assert receipt["terminals"] == _TERMINALS
    assert receipt["profile"] == {
        "form": "3-NDFL",
        "tax_period": "2025",
        "scope": "bounded_russian_source_broker_securities_payable",
        "controlled_evidence": True,
        "real_taxpayer_evidence": False,
    }
    assert receipt["assembly"]["official_xsd_valid"] is True
    assert receipt["assembly"]["semantic_bypass"] is False
    assert receipt["assembly"]["release_required"] is True
    assert receipt["consumer_inventory"] == {
        "emitted_value_count": 49,
        "released_semantic_value_count": 44,
        "released_semantic_values_consumed": 44,
        "official_constant_count": 4,
        "target_mechanics_count": 1,
        "unconsumed_released_semantic_value_count": 0,
        "unknown_origin_count": 0,
        "unowned_value_count": 0,
    }
    assert len(receipt["value_traceability"]) == 49
    assert all(row["origin_count"] >= 1 for row in receipt["value_traceability"])
    assert all(
        row["methodology_or_direct_binding_known"] is True
        for row in receipt["value_traceability"]
    )
    assert all(row["owner_factory"] for row in receipt["value_traceability"])
    residency = next(
        row
        for row in receipt["value_traceability"]
        if row["mapping_id"] == "taxpayer-status"
    )
    assert residency["origin_kind"] == "DERIVED"
    assert residency["owner_factory"] == (
        "Gate5ResidencyEvidenceRuntimeFactory.create"
    )
    assert residency["origin_binding"]["rule_id"] == (
        "taxpayer-residency-article-207-v1"
    )
    assert receipt["legal_methodology_gaps_remain"] == _LEGAL_GAPS
    assert receipt["safety"]["controlled_case_called_real"] is False


def test_b_missing_residency_evidence_has_exact_blocker_and_no_release(
    tmp_path: Path,
) -> None:
    proof = e2e_fixtures._proof_input()
    del proof["residency_evidence"]
    receipts: list[dict] = []

    with pytest.raises(Gate5EndToEndFullTargetXmlError) as exc_info:
        e2e_fixtures._run(tmp_path, proof, audit_sink=receipts.append)

    assert exc_info.value.code == "gate5_e2e_residency_evidence_insufficient"
    assert exc_info.value.blocker == {
        "stage": "residency_methodology_input",
        "gap_class": "MISSING_EVIDENCE",
        "missing_fact": "residency_evidence",
        "reason": "residency_evidence_missing",
        "action": "provide_complete_residency_presence_and_absence_evidence",
    }
    assert receipts == []


def test_c_removing_nonsemantic_release_audit_metadata_does_not_change_target(
    complete_package: dict,
) -> None:
    case = consumer_fixtures._released_case(complete_package)
    projector = Gate5FullTargetXmlProjectionRuntimeFactory.create()
    before = projector.project_released(
        released_values=case["projection_input"],
        target_mechanics=case["target_mechanics"],
    )
    audit_only = copy.deepcopy(case["released"])
    del audit_only["release_receipt"]["evidence_accounting"]["bindings"]
    audit_only["release_receipt"]["review_metadata"] = {"reviewed": False}
    after = projector.project_released(
        released_values=case["projection_input"],
        target_mechanics=case["target_mechanics"],
    )

    assert "release_receipt" not in case["projection_input"]
    assert before["xml_bytes"] == after["xml_bytes"]


def test_d_one_disposal_proceeds_change_has_exact_bounded_downstream_delta(
    tmp_path: Path,
) -> None:
    baseline_receipts: list[dict] = []
    changed_receipts: list[dict] = []
    e2e_fixtures._run(
        tmp_path / "baseline",
        e2e_fixtures._proof_input(),
        audit_sink=baseline_receipts.append,
    )
    proof = e2e_fixtures._proof_input()
    source = proof["supplied_source"]
    source["content_utf8"] = source["content_utf8"].replace(
        ",1,100.00,100.00,RUB",
        ",1,100.00,200.00,RUB",
    )
    source["content_sha256"] = hashlib.sha256(
        source["content_utf8"].encode("utf-8")
    ).hexdigest()
    e2e_fixtures._run(
        tmp_path / "changed",
        proof,
        audit_sink=changed_receipts.append,
    )

    baseline = {
        row["mapping_id"]: row
        for row in baseline_receipts[0]["value_traceability"]
    }
    changed = {
        row["mapping_id"]: row
        for row in changed_receipts[0]["value_traceability"]
    }
    changed_mapping_ids = [
        mapping_id
        for mapping_id in baseline
        if baseline[mapping_id]["target_value_sha256"]
        != changed[mapping_id]["target_value_sha256"]
    ]
    assert changed_mapping_ids == [
        "budget-payable",
        "total-income",
        "taxable-income",
        "tax-base",
        "calculated-tax",
        "tax-payable",
        "source-income",
        "securities-gross-income",
    ]
    assert baseline_receipts[0]["assembly"]["xml_sha256"] != (
        changed_receipts[0]["assembly"]["xml_sha256"]
    )


def test_e_projection_is_independent_from_release_receipt_audit_identity(
    complete_package: dict,
) -> None:
    case = consumer_fixtures._released_case(complete_package)
    first_input = _with_release_receipt_hash(case["projection_input"], "a" * 64)
    second_input = _with_release_receipt_hash(case["projection_input"], "b" * 64)
    projector = Gate5FullTargetXmlProjectionRuntimeFactory.create()
    first = projector.project_released(
        released_values=first_input,
        target_mechanics=case["target_mechanics"],
    )
    second = projector.project_released(
        released_values=second_input,
        target_mechanics=case["target_mechanics"],
    )

    assert first_input["declaration_values"] == second_input["declaration_values"]
    assert first["xml_bytes"] == second["xml_bytes"]
    assert first["receipt"]["xml_binding"] == second["receipt"]["xml_binding"]


def test_f_consumer_first_audit_route_rejects_raw_semantics_and_has_no_bypass(
    complete_package: dict,
) -> None:
    case = consumer_fixtures._released_case(complete_package)

    with pytest.raises(Gate5FullTargetXmlProjectionError) as exc_info:
        Gate5FullTargetXmlProjectionRuntimeFactory.create().project_released(
            released_values=case["semantic_input"],
            target_mechanics=case["target_mechanics"],
        )
    assert exc_info.value.code == "gate5_consumer_first_released_values_invalid"
    source = inspect.getsource(
        e2e_module.Gate5EndToEndFullTargetXmlRuntime._declaration_model_audit_receipt
    )
    assert ".project_released(" in source
    assert ".project(" not in source


def test_g_absent_foreign_domain_is_terminal_and_not_projected(
    tmp_path: Path,
) -> None:
    receipts: list[dict] = []
    e2e_fixtures._run(
        tmp_path,
        e2e_fixtures._proof_input(),
        audit_sink=receipts.append,
    )
    scope = receipts[0]["conditional_scope"]

    assert scope["source_obligation_resolutions"] == [
        {
            "obligation_ref": "obl_russian_source_taxable_income",
            "state": "RESOLVED",
            "real_world_absence_asserted": False,
        },
        {
            "obligation_ref": (
                "obl_foreign_source_taxable_income_and_foreign_tax"
            ),
            "state": "NOT_ACTIVATED_FOR_SUPPLIED_CASE",
            "real_world_absence_asserted": False,
        },
    ]
    assert scope["foreign_target_mapping_count"] == 0
    assert scope["unrelated_conditional_domains_activated"] == 0


def test_h_proven_foreign_source_activates_only_its_exact_obligation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _context, _operation, receipt, tax_base = income_fixtures._proof_models(
        tmp_path, monkeypatch
    )
    income = income_fixtures._component(receipt["scope_binding"], tax_base)
    value = source_fixtures._input(receipt["scope_binding"], income)
    entry = value["source_entries"][0]
    entry["jurisdiction_kind"] = "foreign_source"
    entry["jurisdiction_code"] = "US"
    entry["foreign_tax"] = {
        "paid_tax": {"kind": "money", "amount": "0.00", "currency": "RUB"},
        "authority_ref": "g545-controlled-foreign-authority",
        "evidence_ref": "g545-controlled-foreign-tax-evidence",
    }

    component = Gate5DeclarationIncomeSourcesRuntimeFactory.create().create_component(
        component_input=value
    )

    assert component["obligation_resolutions"] == [
        {
            "obligation_ref": "obl_russian_source_taxable_income",
            "state": "NOT_ACTIVATED_FOR_SUPPLIED_CASE",
            "real_world_absence_asserted": False,
        },
        {
            "obligation_ref": (
                "obl_foreign_source_taxable_income_and_foreign_tax"
            ),
            "state": "RESOLVED",
            "real_world_absence_asserted": False,
        },
    ]
    assert component["covered_obligation_refs"] == [
        "obl_russian_source_taxable_income",
        "obl_foreign_source_taxable_income_and_foreign_tax",
    ]


def _with_release_receipt_hash(value: dict, receipt_hash: str) -> dict:
    result = copy.deepcopy(value)
    result["release_receipt_sha256"] = receipt_hash
    base = {
        key: copy.deepcopy(item)
        for key, item in result.items()
        if key != "projection_input_sha256"
    }
    result["projection_input_sha256"] = _sha256(base)
    return result


def _sha256(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
