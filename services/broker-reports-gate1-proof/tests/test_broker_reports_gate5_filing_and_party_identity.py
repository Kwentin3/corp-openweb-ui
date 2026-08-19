from __future__ import annotations

import copy
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from broker_reports_gate1.gate5_declaration_scope_resolution import (
    GATE5_DECLARATION_SCOPE_COMPONENT_EVIDENCE_SCHEMA_VERSION,
)
from broker_reports_gate1 import gate5_declaration_filing_context as module
from broker_reports_gate1.gate5_declaration_filing_context import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    GATE5_FILING_AND_PARTY_IDENTITY_COMPONENT_SCHEMA_VERSION,
    GATE5_FILING_AND_PARTY_IDENTITY_INPUT_SCHEMA_VERSION,
    Gate5FilingAndPartyIdentityError,
    Gate5FilingAndPartyIdentityRuntimeFactory,
)
import test_broker_reports_gate5_resolved_declaration_package as package_fixtures


def test_exact_synthetic_component_closes_first_machine_blocker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, model, scope_receipt = package_fixtures._scope_case(
        tmp_path, monkeypatch
    )
    component = _component(scope_receipt["scope_binding"])
    package = package_fixtures._runtime(store).assemble(
        definition_ref=package_fixtures._definition_ref(),
        scope_receipt=scope_receipt,
        typed_component_snapshots=[
            package_fixtures._component(model),
            _component_evidence(component),
        ],
        context=context,
    )

    filing = next(
        row
        for row in package["requirement_resolutions"]
        if row["domain_id"] == "filing_and_party_identity"
    )
    assert filing["state"] == "RESOLVED"
    assert filing["scope_state"] == "APPLICABLE"
    assert len(filing["component_refs"]) == 1
    assert package["completeness_receipt"]["first_blocker"] == {
        "domain_id": "declaration_budget_disposition",
        "blocker_class": "component",
        "state": "REQUIRED_MISSING",
        "reason": "required_component_missing",
    }
    assert package["status"] == "DECLARATION_INCOMPLETE_FOR_SUPPLIED_CASE"
    assert package_fixtures._closed_runtime().validate_package(package=package) == (
        package
    )


def test_component_is_deterministic_exact_and_explicitly_synthetic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _context, _model, scope_receipt = package_fixtures._scope_case(
        tmp_path, monkeypatch
    )
    runtime = Gate5FilingAndPartyIdentityRuntimeFactory.create()
    value = _input(scope_receipt["scope_binding"])

    first = runtime.create_component(component_input=value)
    second = runtime.create_component(component_input=copy.deepcopy(value))

    assert first == second
    assert first["status"] == "complete"
    assert first["root_coverage"] == "exact_root_domain"
    assert first["input_snapshot"]["evidence"]["status"] == ("synthetic_proof_evidence")
    assert first["input_snapshot"]["evidence"]["real_user_fact"] is False
    assert (
        runtime.validate_component(
            component=first,
            scope_binding=scope_receipt["scope_binding"],
        )
        == first
    )


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (
            lambda value: value["evidence"].__setitem__("real_user_fact", True),
            "gate5_filing_party_evidence_invalid",
        ),
        (
            lambda value: value["filing_instance"].__setitem__("tax_period", "2024"),
            "gate5_filing_party_filing_instance_invalid",
        ),
        (
            lambda value: value["signer"].__setitem__(
                "signer_capacity", "representative"
            ),
            "gate5_filing_party_signer_invalid",
        ),
    ],
)
def test_component_rejects_false_identity_or_synthetic_marking(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation,
    code: str,
) -> None:
    _store, _context, _model, scope_receipt = package_fixtures._scope_case(
        tmp_path, monkeypatch
    )
    value = _input(scope_receipt["scope_binding"])
    mutation(value)

    with pytest.raises(Gate5FilingAndPartyIdentityError) as exc_info:
        Gate5FilingAndPartyIdentityRuntimeFactory.create().create_component(
            component_input=value
        )
    assert exc_info.value.code == code


def test_sealed_exact_coverage_cannot_be_rehashed_into_another_kind(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, model, scope_receipt = package_fixtures._scope_case(
        tmp_path, monkeypatch
    )
    package = package_fixtures._runtime(store).assemble(
        definition_ref=package_fixtures._definition_ref(),
        scope_receipt=scope_receipt,
        typed_component_snapshots=[
            package_fixtures._component(model),
            _component_evidence(_component(scope_receipt["scope_binding"])),
        ],
        context=context,
    )
    changed = copy.deepcopy(package)
    sealed = next(
        item
        for item in changed["component_snapshots"]
        if item["component_contract_id"]
        == GATE5_FILING_AND_PARTY_IDENTITY_COMPONENT_SCHEMA_VERSION
    )
    sealed["root_coverage"] = "bounded_partial_only"
    base = {
        key: value for key, value in sealed.items() if key != "component_binding_sha256"
    }
    sealed["component_binding_sha256"] = _sha256(base)

    with pytest.raises(Exception) as exc_info:
        package_fixtures._closed_runtime().validate_package(package=changed)
    assert getattr(exc_info.value, "code", "") == (
        "gate5_resolved_package_component_binding_invalid"
    )


def test_factory_and_forbidden_boundaries_are_source_enforced() -> None:
    source = inspect.getsource(module)

    assert FACTORY_REQUIRED == (
        "Gate5FilingAndPartyIdentityRuntimeFactory.create owns exact component validation",
    )
    assert "Gate5FilingAndPartyIdentityRuntimeFactory.create" in source
    assert FORBIDDEN
    assert "ArtifactStore" not in source
    assert "Gate4FinancialCase" not in source
    assert "sqlite" not in source.lower()
    assert "openai" not in source.lower()


def _component(scope_binding: dict) -> dict:
    return Gate5FilingAndPartyIdentityRuntimeFactory.create().create_component(
        component_input=_input(scope_binding)
    )


def _component_evidence(component: dict) -> dict:
    return {
        "schema_version": GATE5_DECLARATION_SCOPE_COMPONENT_EVIDENCE_SCHEMA_VERSION,
        "component_contract_id": (
            GATE5_FILING_AND_PARTY_IDENTITY_COMPONENT_SCHEMA_VERSION
        ),
        "component_sha256": _sha256(component),
        "payload": copy.deepcopy(component),
    }


def _input(scope_binding: dict) -> dict:
    return {
        "schema_version": GATE5_FILING_AND_PARTY_IDENTITY_INPUT_SCHEMA_VERSION,
        "scope_binding": copy.deepcopy(scope_binding),
        "filing_instance": {
            "declaration_instance_ref": "synthetic-declaration-2025-initial",
            "correction_kind": "initial",
            "correction_number": 0,
            "declaration_date": "2026-08-11",
            "tax_period": scope_binding["tax_period"],
            "destination_tax_authority_ref": "synthetic-tax-authority",
            "tax_authority_code": "7705",
        },
        "taxpayer": {
            "taxpayer_ref": scope_binding["taxpayer_scope_ref"],
            "period_status": "resident_individual",
            "declarant_category": "other_individual_declaring_article_228_income",
            "last_name": "Тестов",
            "first_name": "Тест",
            "middle_name": "Тестович",
            "inn": "990000000041",
        },
        "signer": {
            "signer_ref": scope_binding["authenticated_user_ref"],
            "signer_capacity": "taxpayer_self",
            "representation_authority": None,
        },
        "evidence": {
            "schema_version": "broker_reports_gate5_synthetic_case_evidence_v0",
            "status": "synthetic_proof_evidence",
            "source_ref": "g531-synthetic-filing-party-proof",
            "case_id": scope_binding["case_id"],
            "tax_period": scope_binding["tax_period"],
            "input_channel": "filing_and_party_identity",
            "real_user_fact": False,
        },
    }


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
