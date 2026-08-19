from __future__ import annotations

import copy
import hashlib
import inspect
import json

import pytest

from broker_reports_gate1.gate5_clean_context_declaration_trial import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    GATE5_CLEAN_CONTEXT_PAYLOAD_RESOURCE_SHA256,
    GATE5_CLEAN_CONTEXT_TRIAL_ID,
    GATE5_INDEPENDENT_AUTHORING_TRIAL_ID,
    Gate5CleanContextDeclarationTrialError,
    Gate5CleanContextDeclarationTrialFactory,
)
import broker_reports_gate1.gate5_clean_context_declaration_trial as trial_module


def _artifact_ref(
    kind: str, artifact_id: str, version: str, role: str
) -> dict[str, str]:
    return {
        "artifact_kind": kind,
        "artifact_id": artifact_id,
        "artifact_version": version,
        "role": role,
    }


def _candidate() -> dict:
    trial = Gate5CleanContextDeclarationTrialFactory.create()
    target = trial.model_payload()["official_evidence"]["declaration"]
    projection_ref = _artifact_ref(
        "validated_declaration_projection",
        "ru-3ndfl-2025-appendix8-securities-proof",
        "2026.0-proof",
        "validated_projection",
    )
    methodology_ref = _artifact_ref(
        "trusted_methodology",
        "ru-ndfl-securities-tax-model-proof",
        "2026.1-experimental",
        "registered_behavior",
    )
    return {
        "schema_version": "broker_reports_gate5_clean_context_declaration_definition_v1",
        "definition_id": "synthetic-neutral-validator-case",
        "definition_version": "1.0.0-proof",
        "status": "partially_compilable",
        "target": target,
        "scope": {
            "domain": "bounded securities disposal",
            "taxpayer_profile": "resident individual",
            "operation_profile": "organized-market securities outside IIS",
            "boundary": "static authoring compatibility only",
        },
        "requirements": [
            {
                "requirement_id": "supported-unit",
                "official_requirement": "Project supplied stable declaration semantics.",
                "evidence_refs": ["appendix8_xsd_contract"],
                "semantic_outputs": ["validated_fragment"],
                "availability": "conditionally_compilable",
                "end_to_end_available_from_current_case_evidence": False,
                "boundary_inputs": [],
                "capability_bindings": [
                    {
                        "capability_id": "execute_published_typed_behavior_v1",
                        "declared_input_contracts": [
                            "artifact_access_context",
                            "broker_reports_gate5_contract_identity_v1",
                            "broker_reports_gate5_published_behavior_ref_v1",
                            "registered_behavior_input",
                        ],
                        "declared_output_contract": "broker_reports_gate5_typed_behavior_result_v1",
                        "registered_behavior": {
                            "schema_version": "broker_reports_gate5_published_behavior_ref_v1",
                            "methodology_id": "ru-ndfl-securities-tax-model-proof",
                            "methodology_version": "2026.1-experimental",
                            "behavior_id": "securities_disposal_operation_tax_model_v0",
                            "input_contract_id": "broker_reports_gate5_securities_disposal_resolved_inputs_v0",
                            "output_contract_id": "broker_reports_gate5_securities_disposal_operation_tax_model_v0",
                        },
                        "artifact_refs": [methodology_ref],
                    },
                    {
                        "capability_id": "project_validated_declaration_fragment_v0",
                        "declared_input_contracts": [
                            "broker_reports_gate5_declaration_projection_proof_input_v0"
                        ],
                        "declared_output_contract": "broker_reports_gate5_declaration_projection_fragment_v0",
                        "registered_behavior": None,
                        "artifact_refs": [projection_ref],
                    },
                ],
                "gap_refs": [],
            },
            {
                "requirement_id": "unsupported-unit",
                "official_requirement": "Produce another official declaration semantic.",
                "evidence_refs": ["section2_electronic_contract"],
                "semantic_outputs": ["another_official_semantic"],
                "availability": "not_compilable",
                "end_to_end_available_from_current_case_evidence": False,
                "boundary_inputs": [],
                "capability_bindings": [],
                "gap_refs": ["unpublished-behavior-gap"],
            },
        ],
        "gaps": [
            {
                "gap_id": "unpublished-behavior-gap",
                "requirement_id": "unsupported-unit",
                "gap_type": "missing_published_behavior",
                "required_semantic": "A deterministic official declaration semantic is required.",
                "related_capability_ids": ["execute_published_typed_behavior_v1"],
                "related_artifact_refs": [],
                "missing_behavior_id": "unpublished_neutral_behavior_v0",
                "missing_contract_id": None,
                "missing_artifact_kind": None,
                "evidence_refs": ["section2_electronic_contract"],
                "explanation": "No matching published behavior is present in the supplied inventory.",
            }
        ],
        "findings": {
            "supported_requirement_ids": ["supported-unit"],
            "unsupported_requirement_ids": ["unsupported-unit"],
            "first_blocking_gap_id": "unpublished-behavior-gap",
            "limitations": ["No current case evidence was supplied."],
        },
        "authoring": {
            "supplied_evidence_only": True,
            "prior_project_context_used": False,
            "manual_candidate_repair_allowed": False,
            "notes": [],
        },
    }


def test_frozen_payload_is_exact_v1_six_section_clean_context() -> None:
    trial = Gate5CleanContextDeclarationTrialFactory.create()
    payload = trial.model_payload()

    assert set(payload) == {
        "system_instructions",
        "research_policy",
        "runtime_capabilities",
        "published_artifact_inventory",
        "official_evidence",
        "output_schema",
    }
    assert hashlib.sha256(trial.model_payload_bytes()).hexdigest() == (
        GATE5_CLEAN_CONTEXT_PAYLOAD_RESOURCE_SHA256
    )
    capability_ids = {
        item["capability_id"]
        for item in payload["runtime_capabilities"]["capabilities"]
    }
    assert "execute_published_typed_behavior_v1" in capability_ids
    assert "execute_published_calculation_behavior_v0" not in capability_ids


def test_bias_audit_allows_official_evidence_term_only() -> None:
    audit = Gate5CleanContextDeclarationTrialFactory.create().bias_audit()

    assert audit["status"] == "passed"
    assert audit["disallowed_hits"] == []
    assert audit["official_evidence_allowed_hits"] == [
        {
            "term": "line 060",
            "path": "official_evidence.requirements[7].claim",
        }
    ]


def test_pre_inference_record_binds_one_history_free_message() -> None:
    record = Gate5CleanContextDeclarationTrialFactory.create().pre_inference_record()

    assert record["trial_id"] == GATE5_CLEAN_CONTEXT_TRIAL_ID
    assert record["status"] == "frozen_before_inference"
    assert record["conversation_history"] == "none"
    assert len(record["application_messages"]) == 1
    assert record["application_messages"][0]["role"] == "user"
    assert record["payload_sha256"] == GATE5_CLEAN_CONTEXT_PAYLOAD_RESOURCE_SHA256
    assert record["bias_audit"]["status"] == "passed"
    assert record["invocation_profile"]["retry_limit"] == 0


def test_independent_pre_inference_record_reuses_frozen_semantics_without_provider_schema() -> (
    None
):
    record = Gate5CleanContextDeclarationTrialFactory.create().independent_pre_inference_record()

    assert record["trial_id"] == GATE5_INDEPENDENT_AUTHORING_TRIAL_ID
    assert record["status"] == "frozen_before_inference"
    assert record["payload_sha256"] == GATE5_CLEAN_CONTEXT_PAYLOAD_RESOURCE_SHA256
    assert record["conversation_history"] == "none"
    assert record["invocation_profile"]["provider_output_schema"] == "none"
    assert record["invocation_profile"]["candidate_parser"] == (
        "one_utf8_json_object_no_repair_v1"
    )
    assert record["invocation_profile"]["retry_limit"] == 0
    assert record["invocation_profile"]["response_repair"] == "forbidden"


def test_plain_json_candidate_response_parser_preserves_and_validates_exact_object() -> (
    None
):
    trial = Gate5CleanContextDeclarationTrialFactory.create()
    candidate = _candidate()
    response_bytes = json.dumps(candidate, ensure_ascii=False).encode("utf-8")

    assert trial.parse_candidate_response(response_bytes) == candidate
    assert trial.validate_candidate_response(response_bytes)["status"] == "passed"


@pytest.mark.parametrize(
    ("response_bytes", "error"),
    [
        (b"", "gate5_clean_context_candidate_response_empty"),
        (b"```json\\n{}\\n```", "gate5_clean_context_candidate_response_invalid"),
        (b"{} {}", "gate5_clean_context_candidate_response_invalid"),
        (b"[]", "gate5_clean_context_candidate_response_not_object"),
    ],
)
def test_plain_json_candidate_response_parser_rejects_non_object_or_repairable_text(
    response_bytes: bytes, error: str
) -> None:
    with pytest.raises(Gate5CleanContextDeclarationTrialError, match=error):
        Gate5CleanContextDeclarationTrialFactory.create().parse_candidate_response(
            response_bytes
        )


def test_neutral_validator_accepts_real_capability_artifact_and_behavior_pairs() -> (
    None
):
    result = Gate5CleanContextDeclarationTrialFactory.create().validate_candidate(
        _candidate()
    )

    assert result == {
        "schema_version": "broker_reports_gate5_clean_context_candidate_validation_v0",
        "status": "passed",
        "definition_id": "synthetic-neutral-validator-case",
        "requirements_total": 2,
        "supported_requirements_total": 1,
        "unsupported_requirements_total": 1,
        "gaps_total": 1,
        "capability_bindings_total": 2,
        "manual_repairs_total": 0,
    }


def test_validator_rejects_unknown_capability() -> None:
    candidate = _candidate()
    candidate["requirements"][0]["capability_bindings"][0]["capability_id"] = (
        "invented_capability_v0"
    )

    with pytest.raises(
        Gate5CleanContextDeclarationTrialError,
        match="gate5_clean_context_candidate_capability_unknown",
    ):
        Gate5CleanContextDeclarationTrialFactory.create().validate_candidate(candidate)


def test_validator_rejects_unknown_artifact() -> None:
    candidate = _candidate()
    candidate["requirements"][0]["capability_bindings"][1]["artifact_refs"][0][
        "artifact_version"
    ] = "invented-version"

    with pytest.raises(
        Gate5CleanContextDeclarationTrialError,
        match="gate5_clean_context_candidate_artifact_unknown",
    ):
        Gate5CleanContextDeclarationTrialFactory.create().validate_candidate(candidate)


def test_validator_rejects_registered_behavior_contract_mismatch() -> None:
    candidate = _candidate()
    candidate["requirements"][0]["capability_bindings"][0]["registered_behavior"][
        "output_contract_id"
    ] = "invented_output_contract_v0"

    with pytest.raises(
        Gate5CleanContextDeclarationTrialError,
        match="gate5_clean_context_candidate_behavior_contract_mismatch",
    ):
        Gate5CleanContextDeclarationTrialFactory.create().validate_candidate(candidate)


def test_validator_rejects_claim_that_published_behavior_is_missing() -> None:
    candidate = _candidate()
    candidate["gaps"][0]["missing_behavior_id"] = (
        "securities_disposal_operation_tax_model_v0"
    )

    with pytest.raises(
        Gate5CleanContextDeclarationTrialError,
        match="gate5_clean_context_candidate_gap_type_inconsistent",
    ):
        Gate5CleanContextDeclarationTrialFactory.create().validate_candidate(candidate)


def test_validator_rejects_current_case_evidence_overclaim() -> None:
    candidate = _candidate()
    candidate["requirements"][0]["end_to_end_available_from_current_case_evidence"] = (
        True
    )

    with pytest.raises(
        Gate5CleanContextDeclarationTrialError,
        match="gate5_clean_context_candidate_case_evidence_overclaim",
    ):
        Gate5CleanContextDeclarationTrialFactory.create().validate_candidate(candidate)


def test_output_schema_contains_no_expected_concrete_gap() -> None:
    schema = Gate5CleanContextDeclarationTrialFactory.create().output_schema()
    rendered = json.dumps(schema, ensure_ascii=False).lower()

    for forbidden in (
        "section 2",
        "line 060",
        "group tax base",
        "group-level tax base",
        "securities_disposal_group_tax_base",
    ):
        assert forbidden not in rendered

    alternate = copy.deepcopy(_candidate())
    alternate["gaps"][0]["missing_behavior_id"] = "another_unpublished_behavior_v0"
    assert (
        Gate5CleanContextDeclarationTrialFactory.create().validate_candidate(alternate)[
            "status"
        ]
        == "passed"
    )


def test_model_payload_excludes_implementation_and_history_routes() -> None:
    payload = Gate5CleanContextDeclarationTrialFactory.create().model_payload()
    rendered = json.dumps(payload, ensure_ascii=False).lower()

    for forbidden in (
        "factory",
        ".py",
        "services/",
        "services\\",
        "gate5_declaration_definition_candidate",
        "g5.16",
        "g5.17",
        "g5.18",
        "roadmap",
    ):
        assert forbidden not in rendered


def test_maintained_trial_owner_has_no_transport_or_runtime_execution_path() -> None:
    source = inspect.getsource(trial_module)

    assert FACTORY_REQUIRED
    assert FORBIDDEN
    for forbidden in (
        "Gate2StructuredModelClientFactory",
        "subprocess",
        "requests.post",
        "httpx",
        "codex exec",
        ".execute(",
        "eval(",
        "exec(",
    ):
        assert forbidden not in source
