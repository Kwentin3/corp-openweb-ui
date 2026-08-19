from __future__ import annotations

import copy
import hashlib
import inspect
import json

import pytest

from broker_reports_gate1.gate5_declaration_semantic_input import (
    Gate5DeclarationSemanticInputError,
    Gate5DeclarationSemanticInputRuntime,
    Gate5DeclarationSemanticInputRuntimeFactory,
)
from broker_reports_gate1 import gate5_resolved_declaration_package as package_module
from broker_reports_gate1.gate5_resolved_declaration_package import (
    Gate5ResolvedDeclarationPackageRuntimeFactory,
)
import test_broker_reports_gate5_end_to_end_full_target_xml as e2e_fixtures


_RELEASE_SCHEMA_VERSION = "broker_reports_gate5_released_declaration_values_v0"
_RELEASE_RECEIPT_SCHEMA_VERSION = "broker_reports_gate5_declaration_release_receipt_v0"
_RELEASE_STATUS = "DECLARATION_VALUES_RELEASED"


@pytest.fixture(scope="module")
def complete_package(tmp_path_factory: pytest.TempPathFactory) -> dict:
    packages: list[dict] = []
    original_compile = Gate5DeclarationSemanticInputRuntime.compile

    def capture_package(self, *, package: dict) -> dict:
        packages.append(copy.deepcopy(package))
        return original_compile(self, package=package)

    Gate5DeclarationSemanticInputRuntime.compile = capture_package
    try:
        result, _ = e2e_fixtures._run(
            tmp_path_factory.mktemp("g539af-complete-package"),
            e2e_fixtures._proof_input(),
        )
    finally:
        Gate5DeclarationSemanticInputRuntime.compile = original_compile

    assert result["status"] == "END_TO_END_FULL_TARGET_XML_VALID"
    assert len(packages) == 1
    return packages[0]


def test_af_release_complete_case_accounts_obligations_and_every_declared_value(
    complete_package: dict,
) -> None:
    runtime = Gate5DeclarationSemanticInputRuntimeFactory.create()
    candidate = runtime.compile_declaration_value_candidate(package=complete_package)

    released = runtime.release_declaration_value_candidate(
        package=complete_package,
        candidate=candidate,
    )

    assert released["schema_version"] == _RELEASE_SCHEMA_VERSION
    assert released["status"] == _RELEASE_STATUS
    assert released["value_contract"] == candidate["value_contract"]
    assert released["declaration_values"] == candidate["declaration_values"]
    assert released["semantic_value_sha256"] == candidate["semantic_value_sha256"]
    receipt = released["release_receipt"]
    assert receipt["schema_version"] == _RELEASE_RECEIPT_SCHEMA_VERSION
    assert receipt["status"] == _RELEASE_STATUS
    assert (
        receipt["source_binding"]["package_sha256"]
        == complete_package["package_sha256"]
    )
    assert receipt["source_binding"]["completeness_receipt_sha256"] == (
        complete_package["completeness_receipt"]["receipt_sha256"]
    )

    obligation_accounting = receipt["obligation_accounting"]
    assert obligation_accounting["total_count"] == 25
    assert obligation_accounting["unique_count"] == 25
    assert obligation_accounting["terminal_count"] == 25
    assert obligation_accounting["state_counts"] == {
        "RESOLVED": 11,
        "NOT_APPLICABLE": 0,
        "NOT_ACTIVATED_FOR_SUPPLIED_CASE": 14,
    }
    assert len(obligation_accounting["dispositions"]) == 25

    evidence = receipt["evidence_accounting"]
    assert evidence["declared_value_count"] == 44
    assert evidence["unique_value_path_count"] == 44
    assert evidence["origin_kind_counts"] == {
        "DERIVED": 15,
        "DIRECT": 26,
        "REFERENCE": 3,
    }
    bindings = evidence["bindings"]
    assert len({item["declared_value_path"] for item in bindings}) == 44
    for binding in bindings:
        if binding["origin_kind"] == "DERIVED":
            assert "calculation_authority_sha256" in binding
            assert "replayable_input_snapshot_sha256" in binding
            assert "direct_evidence_sha256" not in binding
        else:
            assert "direct_evidence_sha256" in binding
            assert "calculation_authority_sha256" not in binding
            assert "replayable_input_snapshot_sha256" not in binding
    assert {item["owner_factory"] for item in bindings} == {
        "Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create.resolve",
        "Gate5FilingAndPartyIdentityRuntimeFactory.create.validate_component",
        "Gate5DeclarationBudgetOutcomeRuntimeFactory.create.validate_component",
        "Gate5DeclarationBudgetOutcomeRuntimeFactory.create",
        "Gate5IncomeGroupTaxBaseRuntimeFactory.create",
        "Gate5DeclarationTaxSettlementRuntimeFactory.create.validate_component",
        "Gate5DeclarationTaxSettlementRuntimeFactory.create",
        "Gate5DeclarationIncomeSourcesRuntimeFactory.create.validate_component",
        "Gate5TaxPeriodCategoryAggregationRuntimeFactory.create",
    }

    receipt_text = json.dumps(receipt, ensure_ascii=False, sort_keys=True)
    assert "declaration_values" not in receipt_text
    assert (
        runtime.validate_released_declaration_values(
            package=complete_package,
            released=released,
        )
        == released
    )


def test_af_release_is_thin_factory_owned_accounting_without_forbidden_reads() -> None:
    runtime_source = inspect.getsource(
        Gate5DeclarationSemanticInputRuntime.release_declaration_value_candidate
    )
    assert "self._validated_source_package(package=frozen_package)" in runtime_source
    assert "_semantic_input_from_sealed_package(sealed)" in runtime_source
    assert "_declaration_value_candidate(semantic_input)" in runtime_source
    for forbidden in (
        "gate4financialcaseruntimefactory",
        "sqliteartifactstoreadapter",
        "artifactresolver",
        "canonicalreaderfactory",
        "taxmodelruntimefactory.create",
        "openai",
        "select ",
        "open(",
        "xml",
        "project",
    ):
        assert forbidden not in runtime_source.lower()


def test_af_release_candidate_tamper_fails_closed(complete_package: dict) -> None:
    runtime = Gate5DeclarationSemanticInputRuntimeFactory.create()
    candidate = runtime.compile_declaration_value_candidate(package=complete_package)
    changed = copy.deepcopy(candidate)
    changed["declaration_values"]["financial_investment_results"][0][
        "allowable_expenses"
    ]["amount"] = "71.00"
    changed["semantic_value_sha256"] = _sha256(
        {
            "value_contract": changed["value_contract"],
            "declaration_values": changed["declaration_values"],
        }
    )

    with pytest.raises(Gate5DeclarationSemanticInputError) as exc_info:
        runtime.release_declaration_value_candidate(
            package=complete_package,
            candidate=changed,
        )

    assert exc_info.value.code == "gate5_declaration_release_candidate_mismatch"


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("missing", "gate5_declaration_release_evidence_binding_missing"),
        ("duplicate", "gate5_declaration_release_evidence_binding_duplicate"),
        ("unknown-owner", "gate5_declaration_release_evidence_owner_unknown"),
    ],
)
def test_af_release_evidence_accounting_tamper_fails_closed(
    complete_package: dict,
    mutation: str,
    expected_code: str,
) -> None:
    runtime = Gate5DeclarationSemanticInputRuntimeFactory.create()
    candidate = runtime.compile_declaration_value_candidate(package=complete_package)
    released = runtime.release_declaration_value_candidate(
        package=complete_package,
        candidate=candidate,
    )
    changed = copy.deepcopy(released)
    bindings = changed["release_receipt"]["evidence_accounting"]["bindings"]
    if mutation == "missing":
        bindings.pop()
    elif mutation == "duplicate":
        bindings.append(copy.deepcopy(bindings[0]))
    else:
        bindings[0]["owner_factory"] = "UnknownReleaseEvidenceOwner.create"
    _rehash_release(changed)

    with pytest.raises(Gate5DeclarationSemanticInputError) as exc_info:
        runtime.validate_released_declaration_values(
            package=complete_package,
            released=changed,
        )

    assert exc_info.value.code == expected_code


def test_af_release_incomplete_package_reuses_existing_fail_closed_terminal(
    complete_package: dict,
) -> None:
    incomplete = _incomplete_package(complete_package)
    assert incomplete["status"] == "DECLARATION_INCOMPLETE_FOR_SUPPLIED_CASE"
    candidate = Gate5DeclarationSemanticInputRuntimeFactory.create().compile_declaration_value_candidate(
        package=complete_package
    )

    with pytest.raises(Gate5DeclarationSemanticInputError) as exc_info:
        Gate5DeclarationSemanticInputRuntimeFactory.create().release_declaration_value_candidate(
            package=incomplete,
            candidate=candidate,
        )

    assert exc_info.value.code == "gate5_declaration_semantic_source_package_incomplete"


def _incomplete_package(complete_package: dict) -> dict:
    changed = copy.deepcopy(complete_package)
    components = [
        item
        for item in changed["component_snapshots"]
        if item["domain_id"] != "filing_and_party_identity"
    ]
    resolutions = package_module._requirement_resolutions(
        definition=changed["definition_snapshot"],
        scope_receipt=changed["scope_receipt_snapshot"],
        components=components,
    )
    completeness = package_module._completeness_receipt(
        publication=changed["definition_binding"],
        scope_receipt=changed["scope_receipt_snapshot"],
        components=components,
        resolutions=resolutions,
    )
    base = {
        **{
            key: copy.deepcopy(value)
            for key, value in changed.items()
            if key != "package_sha256"
        },
        "status": completeness["status"],
        "component_snapshots": components,
        "requirement_resolutions": resolutions,
        "completeness_receipt": completeness,
    }
    incomplete = {**base, "package_sha256": _sha256(base)}
    return Gate5ResolvedDeclarationPackageRuntimeFactory.create_validation_only().validate_package(
        package=incomplete
    )


def _rehash_release(value: dict) -> None:
    receipt = value["release_receipt"]
    evidence = receipt["evidence_accounting"]
    evidence["evidence_binding_manifest_sha256"] = _sha256(evidence["bindings"])
    receipt["receipt_sha256"] = _sha256(
        {key: item for key, item in receipt.items() if key != "receipt_sha256"}
    )
    value["released_values_sha256"] = _sha256(
        {key: item for key, item in value.items() if key != "released_values_sha256"}
    )


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
