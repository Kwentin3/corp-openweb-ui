from __future__ import annotations

import copy
import hashlib
from importlib import resources
import inspect
import json

import pytest

from broker_reports_gate1.gate5_declaration_definition import (
    Gate5DeclarationDefinitionAuthoringFactory,
)
import broker_reports_gate1.gate5_full_declaration_definition as full_definition_module
from broker_reports_gate1.gate5_full_declaration_definition import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    GATE5_FULL_DECLARATION_DEFINITION_CANDIDATE_RESOURCE,
    GATE5_FULL_DECLARATION_DEFINITION_CANDIDATE_RESOURCE_SHA256,
    GATE5_FULL_DECLARATION_DEFINITION_PAYLOAD_RESOURCE,
    GATE5_FULL_DECLARATION_DEFINITION_PAYLOAD_RESOURCE_SHA256,
    GATE5_FULL_DECLARATION_DEFINITION_REVIEW_RESOURCE,
    GATE5_FULL_DECLARATION_DEFINITION_REVIEW_RESOURCE_SHA256,
    GATE5_FULL_DECLARATION_DEFINITION_SCHEMA_VERSION,
    GATE5_FULL_DECLARATION_OBLIGATION_RESOURCE,
    GATE5_FULL_DECLARATION_OBLIGATION_RESOURCE_SHA256,
    Gate5FullDeclarationDefinitionAuthoringFactory,
    Gate5FullDeclarationDefinitionCandidateFactory,
    Gate5FullDeclarationDefinitionError,
    Gate5TrustedFullDeclarationDefinitionAuthorityFactory,
    build_unfrozen_full_declaration_definition_payload,
)


def _raw(name: str) -> bytes:
    return resources.files("broker_reports_gate1").joinpath(name).read_bytes()


def _error_code(callable_: object) -> str:
    with pytest.raises(Gate5FullDeclarationDefinitionError) as exc:
        callable_()  # type: ignore[operator]
    return exc.value.code


def _synthetic_candidate() -> dict[str, object]:
    owner = Gate5FullDeclarationDefinitionAuthoringFactory.create()
    payload = owner.model_payload()
    package = owner.obligation_package()
    domains = []
    for position, obligation in enumerate(package["reviewed_semantic_obligations"]):
        domains.append(
            {
                "domain_id": f"test_domain_{position:02d}",
                "semantic_meaning": f"Independent semantic obligation owner {position:02d}.",
                "obligation_refs": [obligation["obligation_id"]],
                "expected_component": {
                    "family": f"test_component_{position:02d}",
                    "availability": "missing",
                    "contract_ids": [],
                },
            }
        )
    return {
        "schema_version": GATE5_FULL_DECLARATION_DEFINITION_SCHEMA_VERSION,
        "definition_id": "ru-3ndfl-2025-obligation-test-sentinel",
        "definition_version": "1.0.0-test",
        "declaration_identity": copy.deepcopy(package["declaration_identity"]),
        "obligation_package_binding": copy.deepcopy(
            payload["reviewed_obligation_package_binding"]
        ),
        "domains": domains,
    }


def _domain_for(candidate: dict[str, object], obligation_id: str) -> dict[str, object]:
    return next(
        domain
        for domain in candidate["domains"]  # type: ignore[index]
        if obligation_id in domain["obligation_refs"]
    )


def test_reviewed_obligation_package_is_hash_pinned_complete_and_officially_bound() -> (
    None
):
    raw = _raw(GATE5_FULL_DECLARATION_OBLIGATION_RESOURCE)
    assert hashlib.sha256(raw).hexdigest() == (
        GATE5_FULL_DECLARATION_OBLIGATION_RESOURCE_SHA256
    )
    package = json.loads(raw.decode("utf-8"))
    assert package["review_status"] == "frozen_repository_reviewed"
    assert len(package["reviewed_semantic_obligations"]) == 25
    assert len(package["official_evidence"]["surface_requirements"]) == 14
    assert {
        item["applicability_policy_id"]
        for item in package["reviewed_semantic_obligations"]
    } == {
        "definition_mandatory",
        "elective_claim",
        "factual_occurrence",
        "typed_legal_classification",
    }
    assert all(
        item["url"].startswith("https://www.nalog.gov.ru/")
        for item in package["official_evidence"]["sources"]
    )
    assert all(
        item["root_coverage"] == "bounded_partial_only"
        for item in package["component_inventory"]["contracts"]
    )


def test_frozen_authoring_payload_replays_exactly_without_prior_result_context() -> (
    None
):
    raw = _raw(GATE5_FULL_DECLARATION_DEFINITION_PAYLOAD_RESOURCE)
    assert hashlib.sha256(raw).hexdigest() == (
        GATE5_FULL_DECLARATION_DEFINITION_PAYLOAD_RESOURCE_SHA256
    )
    owner = Gate5FullDeclarationDefinitionAuthoringFactory.create()
    assert owner.model_payload_bytes() == raw
    assert owner.model_payload() == build_unfrozen_full_declaration_definition_payload()
    assert owner.bias_audit() == {
        "schema_version": (
            "broker_reports_gate5_full_declaration_definition_bias_audit_v1"
        ),
        "status": "passed",
        "forbidden_term_count": 10,
        "hits": [],
    }


def test_candidate_parser_requires_one_utf8_json_object() -> None:
    owner = Gate5FullDeclarationDefinitionAuthoringFactory.create()
    assert (
        _error_code(lambda: owner.parse_candidate_response(b"[]"))
        == "gate5_full_declaration_definition_candidate_not_object"
    )
    assert (
        _error_code(lambda: owner.parse_candidate_response(b"{} {}"))
        == "gate5_full_declaration_definition_candidate_json_invalid"
    )
    assert (
        _error_code(lambda: owner.parse_candidate_response(b'{"x":NaN}'))
        == "gate5_full_declaration_definition_candidate_json_invalid"
    )


def test_validator_accounts_for_every_obligation_once_and_derives_policy() -> None:
    audit = Gate5FullDeclarationDefinitionAuthoringFactory.create().validate_candidate(
        _synthetic_candidate()
    )
    assert audit["status"] == "eligible_for_review"
    assert audit["obligation_accounting"]["obligation_count"] == 25
    assert audit["obligation_accounting"]["missing_obligation_ids"] == []
    assert audit["obligation_accounting"]["duplicate_obligation_ids"] == []
    assert audit["obligation_accounting"]["unknown_obligation_ids"] == []
    assert {row["policy"] for row in audit["applicability_audit"]["rows"]} == {
        "definition_mandatory",
        "elective_claim",
        "factual_occurrence",
        "typed_legal_classification",
    }


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (
            lambda candidate: candidate["domains"].pop(),
            "gate5_full_declaration_definition_obligation_missing",
        ),
        (
            lambda candidate: candidate["domains"][1]["obligation_refs"].__setitem__(
                0, candidate["domains"][0]["obligation_refs"][0]
            ),
            "gate5_full_declaration_definition_obligation_duplicate",
        ),
        (
            lambda candidate: candidate["domains"][0]["obligation_refs"].__setitem__(
                0, "obl_unknown"
            ),
            "gate5_full_declaration_definition_obligation_unknown",
        ),
        (
            lambda candidate: candidate["domains"][0].__setitem__(
                "obligation_refs", []
            ),
            "gate5_full_declaration_definition_obligation_empty",
        ),
    ],
)
def test_missing_duplicate_unknown_and_empty_obligation_refs_fail_closed(
    mutation: object,
    expected: str,
) -> None:
    owner = Gate5FullDeclarationDefinitionAuthoringFactory.create()
    candidate = _synthetic_candidate()
    mutation(candidate)  # type: ignore[operator]
    assert _error_code(lambda: owner.validate_candidate(candidate)) == expected


def test_one_domain_cannot_mix_applicability_policies() -> None:
    owner = Gate5FullDeclarationDefinitionAuthoringFactory.create()
    candidate = _synthetic_candidate()
    elective = _domain_for(candidate, "obl_refundable_amount_disposal_election")
    mandatory = candidate["domains"][0]  # type: ignore[index]
    mandatory["obligation_refs"].append(elective["obligation_refs"][0])
    candidate["domains"].remove(elective)  # type: ignore[index]
    assert (
        _error_code(lambda: owner.validate_candidate(candidate))
        == "gate5_full_declaration_definition_policy_mixed"
    )


def test_component_contracts_are_allowlisted_scope_bound_and_not_promoted() -> None:
    owner = Gate5FullDeclarationDefinitionAuthoringFactory.create()
    candidate = _synthetic_candidate()
    domain = _domain_for(candidate, "obl_securities_and_derivatives_results")
    component = domain["expected_component"]
    component["availability"] = "published_bounded"
    component["contract_ids"] = [
        "broker_reports_gate5_securities_disposal_tax_model_v0"
    ]
    assert owner.validate_candidate(candidate)["component_audit"]["status"] == "passed"

    candidate = _synthetic_candidate()
    component = _domain_for(candidate, "obl_securities_and_derivatives_results")[
        "expected_component"
    ]
    component["availability"] = "published_bounded"
    component["contract_ids"] = ["invented_contract_v0"]
    assert (
        _error_code(lambda: owner.validate_candidate(candidate))
        == "gate5_full_declaration_definition_component_ref_invalid"
    )

    candidate = _synthetic_candidate()
    component = _domain_for(candidate, "obl_securities_and_derivatives_results")[
        "expected_component"
    ]
    component["availability"] = "published_exact"
    component["contract_ids"] = [
        "broker_reports_gate5_securities_disposal_tax_model_v0"
    ]
    assert (
        _error_code(lambda: owner.validate_candidate(candidate))
        == "gate5_full_declaration_definition_component_coverage_invalid"
    )

    candidate = _synthetic_candidate()
    component = _domain_for(candidate, "obl_securities_and_derivatives_results")[
        "expected_component"
    ]
    component["availability"] = "published_bounded"
    component["contract_ids"] = ["broker_reports_gate5_income_group_tax_base_model_v0"]
    assert (
        _error_code(lambda: owner.validate_candidate(candidate))
        == "gate5_full_declaration_definition_component_scope_invalid"
    )


def test_component_families_meanings_target_layout_and_logic_are_closed() -> None:
    owner = Gate5FullDeclarationDefinitionAuthoringFactory.create()
    candidate = _synthetic_candidate()
    candidate["domains"][1]["expected_component"]["family"] = (  # type: ignore[index]
        candidate["domains"][0]["expected_component"]["family"]  # type: ignore[index]
    )
    assert (
        _error_code(lambda: owner.validate_candidate(candidate))
        == "gate5_full_declaration_definition_component_family_duplicate"
    )
    candidate = _synthetic_candidate()
    candidate["domains"][0]["semantic_meaning"] = "A Section owner."  # type: ignore[index]
    assert (
        _error_code(lambda: owner.validate_candidate(candidate))
        == "gate5_full_declaration_definition_domain_invalid"
    )
    candidate = _synthetic_candidate()
    candidate["domains"][0]["predicate"] = "presence == true"  # type: ignore[index]
    assert (
        _error_code(lambda: owner.validate_candidate(candidate))
        == "gate5_full_declaration_definition_executable_logic_forbidden"
    )


def test_published_candidate_is_exactly_validated_and_resolved_by_id_version_hash() -> (
    None
):
    candidate_raw = _raw(GATE5_FULL_DECLARATION_DEFINITION_CANDIDATE_RESOURCE)
    review_raw = _raw(GATE5_FULL_DECLARATION_DEFINITION_REVIEW_RESOURCE)
    assert hashlib.sha256(candidate_raw).hexdigest() == (
        GATE5_FULL_DECLARATION_DEFINITION_CANDIDATE_RESOURCE_SHA256
    )
    assert hashlib.sha256(review_raw).hexdigest() == (
        GATE5_FULL_DECLARATION_DEFINITION_REVIEW_RESOURCE_SHA256
    )
    evidence = Gate5FullDeclarationDefinitionCandidateFactory.create()
    assert evidence.validation()["obligation_accounting"]["obligation_count"] == 25
    authority = Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create()
    publication = authority.publication()
    assert publication["status"] == "trusted_repository_published"
    assert publication["obligation_package_sha256"] == (
        GATE5_FULL_DECLARATION_OBLIGATION_RESOURCE_SHA256
    )
    resolved = authority.resolve(
        publication["definition_id"],
        publication["definition_version"],
        publication["definition_sha256"],
    )
    assert resolved == authority.definition()
    scope_contract = authority.resolve_for_scope(
        publication["definition_id"],
        publication["definition_version"],
        publication["definition_sha256"],
    )
    assert scope_contract["definition"] == resolved
    assert scope_contract["publication"] == publication
    assert (
        scope_contract["applicability_audit"]
        == evidence.validation()["applicability_audit"]
    )
    mismatches = [
        (
            "wrong_definition_id",
            publication["definition_version"],
            publication["definition_sha256"],
        ),
        (
            publication["definition_id"],
            "0.0.0-wrong",
            publication["definition_sha256"],
        ),
        (
            publication["definition_id"],
            publication["definition_version"],
            "0" * 64,
        ),
    ]
    for definition_id, definition_version, definition_sha256 in mismatches:
        assert (
            _error_code(
                lambda: authority.resolve(
                    definition_id,
                    definition_version,
                    definition_sha256,
                )
            )
            == "gate5_full_declaration_definition_not_published"
        )


def test_factory_closed_world_boundary_immutability_and_g516_replay_remain_intact() -> (
    None
):
    source = inspect.getsource(full_definition_module)
    assert "resources.files(__package__)" in source
    assert "Path(" not in source
    assert any(
        "Gate5FullDeclarationDefinitionAuthoringFactory.create" in item
        for item in FACTORY_REQUIRED
    )
    assert any(
        "Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create" in item
        for item in FACTORY_REQUIRED
    )
    assert any("case-time scope resolution" in item for item in FORBIDDEN)
    owner = Gate5FullDeclarationDefinitionAuthoringFactory.create()
    payload = owner.model_payload()
    payload["task"] = "mutated"
    assert owner.model_payload()["task"] != "mutated"
    old_candidate = Gate5DeclarationDefinitionAuthoringFactory.create().candidate()
    assert old_candidate["definition_id"] == (
        "ru-3ndfl-2025-securities-supported-surface"
    )
