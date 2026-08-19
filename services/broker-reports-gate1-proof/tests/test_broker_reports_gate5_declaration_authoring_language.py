from __future__ import annotations

import copy
import hashlib
import inspect
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from broker_reports_gate1.gate5_declaration_authoring_language import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    GATE5_DECLARATION_AUTHORING_LANGUAGE_PAYLOAD_RESOURCE_SHA256,
    GATE5_DECLARATION_AUTHORING_LANGUAGE_G522_PAYLOAD_RESOURCE_SHA256,
    GATE5_DECLARATION_AUTHORING_LANGUAGE_G522_TRIAL_ID,
    GATE5_DECLARATION_AUTHORING_LANGUAGE_G523_PAYLOAD_RESOURCE_SHA256,
    GATE5_DECLARATION_AUTHORING_LANGUAGE_G523_TRIAL_ID,
    GATE5_DECLARATION_AUTHORING_LANGUAGE_G524_PAYLOAD_RESOURCE_SHA256,
    GATE5_DECLARATION_AUTHORING_LANGUAGE_G524_TRIAL_ID,
    GATE5_DECLARATION_AUTHORING_LANGUAGE_SCHEMA_VERSION,
    GATE5_DECLARATION_AUTHORING_LANGUAGE_TRIAL_ID,
    Gate5DeclarationAuthoringLanguageError,
    Gate5DeclarationAuthoringLanguageV2Factory,
    build_unfrozen_declaration_authoring_language_payload_g522,
    build_unfrozen_declaration_authoring_language_payload_g523,
    build_unfrozen_declaration_authoring_language_payload_g524,
)
import broker_reports_gate1.gate5_declaration_authoring_language as language_module


REPO_ROOT = Path(__file__).resolve().parents[3]
G522_CANDIDATE = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "2026-08-10"
    / "BROKER_REPORTS_GATE5_SECTION2_CALCULATION_SEMANTICS_G5_22.candidate.json"
)
G523_CANDIDATE = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "2026-08-10"
    / "BROKER_REPORTS_GATE5_SINGLETON_CATEGORY_AGGREGATION_G5_23.candidate.json"
)
G524_CANDIDATE = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "2026-08-10"
    / "BROKER_REPORTS_GATE5_SECTION2_PROJECTION_G5_24.candidate.json"
)


def _artifact_ref(kind: str, artifact_id: str, version: str) -> dict[str, str]:
    return {
        "artifact_kind": kind,
        "artifact_id": artifact_id,
        "artifact_version": version,
    }


def _candidate() -> dict:
    language = Gate5DeclarationAuthoringLanguageV2Factory.create()
    target = language.model_payload()["official_evidence"]["declaration"]
    methodology_ref = _artifact_ref(
        "trusted_methodology",
        "ru-ndfl-securities-tax-model-proof",
        "2026.1-experimental",
    )
    projection_ref = _artifact_ref(
        "validated_declaration_projection",
        "ru-3ndfl-2025-appendix8-securities-proof",
        "2026.0-proof",
    )
    return {
        "schema_version": GATE5_DECLARATION_AUTHORING_LANGUAGE_SCHEMA_VERSION,
        "definition_id": "synthetic-semantic-language-case",
        "definition_version": "2.0.0-proof",
        "target": target,
        "scope": {
            "domain": "bounded securities disposal",
            "taxpayer_profile": "resident individual",
            "operation_profile": "organized-market securities outside IIS",
            "boundary": "static authoring compatibility only",
        },
        "requirements": [
            {
                "requirement_id": "appendix8-supported-surface",
                "official_requirement": (
                    "Produce the supplied Appendix 8 securities semantics."
                ),
                "evidence_refs": [
                    "appendix8_form_lines_010_050",
                    "appendix8_xsd_contract",
                ],
                "semantic_outputs": [
                    "complete_operation_model",
                    "complete_category_projection",
                    "appendix8_fragment",
                ],
                "runtime_support": "supported",
                "compositions": [
                    {
                        "capability_id": "execute_published_typed_behavior_v1",
                        "behavior_ref": {
                            "methodology_id": ("ru-ndfl-securities-tax-model-proof"),
                            "methodology_version": "2026.1-experimental",
                            "behavior_id": (
                                "securities_disposal_operation_tax_model_v0"
                            ),
                        },
                        "artifact_refs": [methodology_ref],
                    },
                    {
                        "capability_id": "aggregate_complete_category_scope_v0",
                        "behavior_ref": None,
                        "artifact_refs": [methodology_ref, projection_ref],
                    },
                    {
                        "capability_id": ("project_validated_declaration_fragment_v0"),
                        "behavior_ref": None,
                        "artifact_refs": [projection_ref],
                    },
                ],
                "gap_refs": [],
            },
            {
                "requirement_id": "section2-unsupported-semantic",
                "official_requirement": (
                    "Produce the supplied Section 2 calculated semantics."
                ),
                "evidence_refs": [
                    "section2_form_lines_001_060",
                    "section2_electronic_contract",
                ],
                "semantic_outputs": ["section2_calculated_fragment"],
                "runtime_support": "unsupported",
                "compositions": [],
                "gap_refs": ["section2-published-behavior-gap"],
            },
        ],
        "gaps": [
            {
                "gap_id": "section2-published-behavior-gap",
                "requirement_id": "section2-unsupported-semantic",
                "gap_type": "missing_published_behavior",
                "required_semantic": (
                    "Deterministically derive the official Section 2 values."
                ),
                "related_capability_ids": ["execute_published_typed_behavior_v1"],
                "related_artifact_refs": [projection_ref],
                "evidence_refs": ["section2_electronic_contract"],
                "explanation": (
                    "The supplied inventory has no published behavior for this "
                    "semantic."
                ),
            }
        ],
        "first_blocking_gap_id": "section2-published-behavior-gap",
    }


def test_frozen_v2_payload_is_exact_and_history_free() -> None:
    language = Gate5DeclarationAuthoringLanguageV2Factory.create()
    payload = language.model_payload()

    assert hashlib.sha256(language.model_payload_bytes()).hexdigest() == (
        GATE5_DECLARATION_AUTHORING_LANGUAGE_PAYLOAD_RESOURCE_SHA256
    )
    assert len(language.model_payload_bytes()) == 24971
    assert list(payload) == [
        "official_evidence",
        "output_schema",
        "published_artifact_inventory",
        "research_policy",
        "runtime_capabilities",
        "system_instructions",
    ]
    assert language.bias_audit()["status"] == "passed"
    assert language.bias_audit()["disallowed_hits"] == []


def test_g522_replay_payload_is_additive_exact_and_history_free() -> None:
    historical = Gate5DeclarationAuthoringLanguageV2Factory.create()
    replay = Gate5DeclarationAuthoringLanguageV2Factory.create_g522_replay()
    historical_payload = historical.model_payload()
    payload = replay.model_payload()

    assert hashlib.sha256(replay.model_payload_bytes()).hexdigest() == (
        GATE5_DECLARATION_AUTHORING_LANGUAGE_G522_PAYLOAD_RESOURCE_SHA256
    )
    assert len(replay.model_payload_bytes()) == 26614
    assert payload == build_unfrozen_declaration_authoring_language_payload_g522()
    assert payload["runtime_capabilities"] == historical_payload["runtime_capabilities"]
    assert payload["official_evidence"] == historical_payload["official_evidence"]
    assert (
        payload["published_artifact_inventory"]["artifacts"][:-1]
        == (historical_payload["published_artifact_inventory"]["artifacts"])
    )
    artifact = payload["published_artifact_inventory"]["artifacts"][-1]
    assert artifact["artifact_ref"] == {
        "artifact_kind": "trusted_methodology",
        "artifact_id": "ru-ndfl-securities-tax-model-proof",
        "artifact_version": "2026.2-experimental",
    }
    assert artifact["behavior_id"] == "securities_income_group_tax_base_v0"
    assert replay.bias_audit()["status"] == "passed"
    assert replay.bias_audit()["disallowed_hits"] == []
    assert replay.pre_inference_record()["trial_id"] == (
        GATE5_DECLARATION_AUTHORING_LANGUAGE_G522_TRIAL_ID
    )


def test_g523_replay_changes_only_current_capability_truth_and_generic_semantics() -> (
    None
):
    historical = Gate5DeclarationAuthoringLanguageV2Factory.create_g522_replay()
    replay = Gate5DeclarationAuthoringLanguageV2Factory.create_g523_replay()
    historical_payload = historical.model_payload()
    payload = replay.model_payload()

    assert hashlib.sha256(replay.model_payload_bytes()).hexdigest() == (
        GATE5_DECLARATION_AUTHORING_LANGUAGE_G523_PAYLOAD_RESOURCE_SHA256
    )
    assert len(replay.model_payload_bytes()) == 26898
    assert payload == build_unfrozen_declaration_authoring_language_payload_g523()
    for section in (
        "research_policy",
        "published_artifact_inventory",
        "official_evidence",
        "output_schema",
    ):
        assert payload[section] == historical_payload[section]

    aggregate = next(
        item
        for item in payload["runtime_capabilities"]["capabilities"]
        if item["capability_id"] == "aggregate_complete_category_scope_v0"
    )
    assert "at_least_one_complete_operation_model" in aggregate["preconditions"]
    assert "at_least_two_complete_operation_models" not in aggregate["preconditions"]
    assert "empty_operation_member_set" in aggregate["failure_conditions"]
    assert len(payload["runtime_capabilities"]["capabilities"]) == 5

    current_semantics = payload["system_instructions"]["language_semantics"]
    assert (
        current_semantics[:-1]
        == historical_payload["system_instructions"]["language_semantics"]
    )
    assert "every required suitable published artifact" in current_semantics[-1]
    rendered = replay.model_payload_bytes().decode("utf-8").lower()
    assert "singleton" not in rendered
    assert "previous candidate" not in rendered
    assert replay.bias_audit()["status"] == "passed"
    assert replay.bias_audit()["disallowed_hits"] == []
    assert replay.pre_inference_record()["trial_id"] == (
        GATE5_DECLARATION_AUTHORING_LANGUAGE_G523_TRIAL_ID
    )

    compiled = replay.validate_candidate(_candidate())
    assert compiled["definition_status"] == "partially_compilable"
    assert compiled["first_blocking_gap_id"] == "section2-published-behavior-gap"


def test_g522_compiler_accepts_the_new_exact_typed_behavior_composition() -> None:
    candidate = _candidate()
    new_ref = _artifact_ref(
        "trusted_methodology",
        "ru-ndfl-securities-tax-model-proof",
        "2026.2-experimental",
    )
    requirement = candidate["requirements"][1]
    requirement["runtime_support"] = "supported"
    requirement["compositions"] = [
        {
            "capability_id": "execute_published_typed_behavior_v1",
            "behavior_ref": {
                "methodology_id": "ru-ndfl-securities-tax-model-proof",
                "methodology_version": "2026.2-experimental",
                "behavior_id": "securities_income_group_tax_base_v0",
            },
            "artifact_refs": [new_ref],
        }
    ]
    requirement["gap_refs"] = []
    candidate["gaps"] = []
    candidate["first_blocking_gap_id"] = None

    compiled = Gate5DeclarationAuthoringLanguageV2Factory.create_g522_replay().validate_candidate(
        candidate
    )

    resolved = compiled["requirements"][1]["resolved_compositions"][0]
    assert resolved["behavior_binding"] == {
        "behavior_ref": {
            "schema_version": "broker_reports_gate5_published_behavior_ref_v1",
            "methodology_id": "ru-ndfl-securities-tax-model-proof",
            "methodology_version": "2026.2-experimental",
            "behavior_id": "securities_income_group_tax_base_v0",
        },
        "input_contract_id": "broker_reports_gate5_income_group_tax_base_input_v0",
        "output_contract_id": ("broker_reports_gate5_income_group_tax_base_model_v0"),
    }
    assert compiled["definition_status"] == "compilable"
    assert compiled["first_blocking_gap_id"] is None


def test_g522_unchanged_replay_candidate_removes_old_gap_and_exposes_next_gap() -> None:
    language = Gate5DeclarationAuthoringLanguageV2Factory.create_g522_replay()
    raw = G522_CANDIDATE.read_bytes()
    candidate = language.parse_candidate_response(raw)

    assert hashlib.sha256(raw).hexdigest() == (
        "dee9cec002449e31ae7536a36e1a897fe2df1c7355f65ec999c7723cf5d70bf2"
    )
    Draft202012Validator(language.output_schema()).validate(candidate)
    rendered = raw.decode("utf-8")
    assert "section2_calculation_behavior_missing" not in rendered
    assert "securities_income_group_tax_base_v0" in rendered
    assert candidate["first_blocking_gap_id"] == ("gap.singleton_category_aggregation")

    with pytest.raises(
        Gate5DeclarationAuthoringLanguageError,
        match=("artifact_missing:requirements\\[6\\]\\.compositions\\[1\\]"),
    ):
        language.validate_candidate(candidate)


def test_g523_history_free_candidate_compiles_and_discovers_projection_gap() -> None:
    language = Gate5DeclarationAuthoringLanguageV2Factory.create_g523_replay()
    raw = G523_CANDIDATE.read_bytes()
    candidate = language.parse_candidate_response(raw)

    assert hashlib.sha256(raw).hexdigest() == (
        "1b681477ee6f3d09cf69ca533f42d53cebb26397912f57ccbf362c5decce7b4b"
    )
    assert len(raw) == 11146
    Draft202012Validator(language.output_schema()).validate(candidate)
    compiled = language.validate_candidate(candidate)

    rendered = raw.decode("utf-8")
    assert "gap.singleton_category_aggregation" not in rendered
    assert candidate["first_blocking_gap_id"] == (
        "section2_validated_projection_artifact_missing"
    )
    assert all(
        composition["artifact_refs"]
        for requirement in candidate["requirements"]
        for composition in requirement["compositions"]
    )
    assert compiled["status"] == "passed"
    assert compiled["definition_status"] == "partially_compilable"
    assert compiled["manual_repairs_total"] == 0
    assert compiled["first_blocking_gap_id"] == (
        "section2_validated_projection_artifact_missing"
    )


def test_g524_replay_changes_only_current_project_and_projection_inventory_truth() -> (
    None
):
    historical = Gate5DeclarationAuthoringLanguageV2Factory.create_g523_replay()
    replay = Gate5DeclarationAuthoringLanguageV2Factory.create_g524_replay()
    historical_payload = historical.model_payload()
    payload = replay.model_payload()

    assert hashlib.sha256(replay.model_payload_bytes()).hexdigest() == (
        GATE5_DECLARATION_AUTHORING_LANGUAGE_G524_PAYLOAD_RESOURCE_SHA256
    )
    assert len(replay.model_payload_bytes()) == 28631
    assert payload == build_unfrozen_declaration_authoring_language_payload_g524()
    for section in ("research_policy", "official_evidence", "output_schema"):
        assert payload[section] == historical_payload[section]
    assert payload["system_instructions"] == historical_payload["system_instructions"]

    capabilities = {
        item["capability_id"]: item
        for item in payload["runtime_capabilities"]["capabilities"]
    }
    assert len(capabilities) == 5
    assert "project_validated_declaration_fragment_v0" not in capabilities
    assert capabilities["project_validated_declaration_fragment_v1"]["inputs"] == [
        {
            "name": "projection_ref",
            "contract": "broker_reports_gate5_declaration_projection_ref_v1",
            "required": True,
        },
        {
            "name": "declaration_semantics",
            "contract": "registered_projection_input",
            "required": True,
        },
    ]
    inventory = payload["published_artifact_inventory"]
    assert inventory["inventory_version"] == "2026.3-proof"
    projection_artifacts = [
        item
        for item in inventory["artifacts"]
        if item["artifact_ref"]["artifact_kind"]
        == "validated_declaration_projection"
    ]
    assert {item["artifact_ref"]["artifact_id"] for item in projection_artifacts} == {
        "ru-3ndfl-2025-appendix8-securities-proof",
        "ru-3ndfl-2025-section2-securities-income-group-proof",
    }
    section2 = next(
        item
        for item in projection_artifacts
        if item["artifact_ref"]["artifact_id"]
        == "ru-3ndfl-2025-section2-securities-income-group-proof"
    )
    assert section2["semantic_input_contract"] == (
        "broker_reports_gate5_income_group_tax_base_model_v0"
    )
    assert section2["semantic_output_contract"] == (
        "broker_reports_gate5_declaration_projection_fragment_v1"
    )
    assert section2["capability_uses"] == [
        {
            "capability_id": "project_validated_declaration_fragment_v1",
            "role": "validated_projection",
        }
    ]
    rendered = replay.model_payload_bytes().decode("utf-8").lower()
    assert "section2_validated_projection_artifact_missing" not in rendered
    assert "section2_projection_contract_incompatible" not in rendered
    assert replay.bias_audit()["status"] == "passed"
    assert replay.bias_audit()["disallowed_hits"] == []
    assert replay.pre_inference_record()["trial_id"] == (
        GATE5_DECLARATION_AUTHORING_LANGUAGE_G524_TRIAL_ID
    )


def test_g524_compiler_accepts_section2_projection_without_old_gap() -> None:
    candidate = json.loads(G523_CANDIDATE.read_text(encoding="utf-8"))
    candidate["definition_version"] = "2026.3-proof"
    for requirement in candidate["requirements"]:
        for composition in requirement["compositions"]:
            if (
                composition["capability_id"]
                == "project_validated_declaration_fragment_v0"
            ):
                composition["capability_id"] = (
                    "project_validated_declaration_fragment_v1"
                )
        if requirement["requirement_id"] == (
            "section2_group_bound_declaration_projection"
        ):
            requirement["runtime_support"] = "supported"
            requirement["compositions"].append(
                {
                    "capability_id": "project_validated_declaration_fragment_v1",
                    "behavior_ref": None,
                    "artifact_refs": [
                        {
                            "artifact_kind": "validated_declaration_projection",
                            "artifact_id": (
                                "ru-3ndfl-2025-section2-securities-income-group-proof"
                            ),
                            "artifact_version": "2026.0-proof",
                        }
                    ],
                }
            )
            requirement["gap_refs"] = []
    candidate["gaps"] = []
    candidate["first_blocking_gap_id"] = None

    compiled = (
        Gate5DeclarationAuthoringLanguageV2Factory.create_g524_replay()
        .validate_candidate(candidate)
    )

    assert compiled["definition_status"] == "compilable"
    assert compiled["gaps_total"] == 0
    assert compiled["manual_repairs_total"] == 0
    section2 = next(
        item
        for item in compiled["requirements"]
        if item["requirement_id"]
        == "section2_group_bound_declaration_projection"
    )
    projected = section2["resolved_compositions"][-1]
    assert projected["capability_id"] == (
        "project_validated_declaration_fragment_v1"
    )
    assert projected["capability_output_contract"] == (
        "broker_reports_gate5_declaration_projection_fragment_v1"
    )


def test_g524_history_free_candidate_compiles_and_preserves_next_gap() -> None:
    language = Gate5DeclarationAuthoringLanguageV2Factory.create_g524_replay()
    raw = G524_CANDIDATE.read_bytes()
    candidate = language.parse_candidate_response(raw)

    assert len(raw) == 7405
    assert hashlib.sha256(raw).hexdigest() == (
        "c2efa5639a8d083ef6f7c9d9cef4f873a1027cdfbcc4d765b80c66555aa8c8c1"
    )
    Draft202012Validator(language.output_schema()).validate(candidate)
    compiled = language.validate_candidate(candidate)

    rendered = raw.decode("utf-8")
    assert "section2_validated_projection_artifact_missing" not in rendered
    assert "section2_projection_contract_incompatible" not in rendered
    assert candidate["first_blocking_gap_id"] == (
        "complete_electronic_declaration_assembly_gap"
    )
    assert compiled["status"] == "passed"
    assert compiled["definition_status"] == "partially_compilable"
    assert compiled["requirements_total"] == 5
    assert compiled["supported_requirements_total"] == 4
    assert compiled["unsupported_requirements_total"] == 1
    assert compiled["resolved_compositions_total"] == 6
    assert compiled["manual_repairs_total"] == 0
    assert compiled["first_blocking_gap_id"] == (
        "complete_electronic_declaration_assembly_gap"
    )

    # Preserve observable model semantics without turning them into authority:
    # 003 is classification evidence, not a Section 2 fragment field, and one
    # PROJECT invocation accepts exactly one projection artifact reference.
    section2 = next(
        requirement
        for requirement in candidate["requirements"]
        if requirement["requirement_id"]
        == "section2_securities_income_group_fragment"
    )
    assert "section2_income_type_code" in section2["semantic_outputs"]
    full_document = next(
        requirement
        for requirement in candidate["requirements"]
        if requirement["requirement_id"]
        == "complete_electronic_declaration_contract"
    )
    assert len(full_document["compositions"][0]["artifact_refs"]) == 2


def test_v2_schema_keeps_semantics_and_removes_mechanical_repetition() -> None:
    schema = Gate5DeclarationAuthoringLanguageV2Factory.create().output_schema()
    root_properties = schema["properties"]
    requirement_properties = root_properties["requirements"]["items"]["properties"]
    composition_properties = requirement_properties["compositions"]["items"][
        "properties"
    ]
    gap_properties = root_properties["gaps"]["items"]["properties"]

    assert "status" not in root_properties
    assert "findings" not in root_properties
    assert "authoring" not in root_properties
    assert "end_to_end_available_from_current_case_evidence" not in (
        requirement_properties
    )
    assert "boundary_inputs" not in requirement_properties
    assert "declared_input_contracts" not in composition_properties
    assert "declared_output_contract" not in composition_properties
    assert "missing_behavior_id" not in gap_properties
    assert "missing_contract_id" not in gap_properties
    assert "missing_artifact_kind" not in gap_properties


def test_pre_inference_record_binds_derived_metadata_and_one_message() -> None:
    record = Gate5DeclarationAuthoringLanguageV2Factory.create().pre_inference_record()

    assert record["trial_id"] == GATE5_DECLARATION_AUTHORING_LANGUAGE_TRIAL_ID
    assert record["status"] == "frozen_before_inference"
    assert record["conversation_history"] == "none"
    assert len(record["application_messages"]) == 1
    assert record["payload_sha256"] == (
        GATE5_DECLARATION_AUTHORING_LANGUAGE_PAYLOAD_RESOURCE_SHA256
    )
    assert record["derived_metadata_policy"] == {
        "capability_io_contracts": "deterministic_resolver",
        "behavior_io_contracts": "deterministic_registry",
        "definition_status": "deterministic_compiler",
        "case_input_assessment": "not_evaluated_no_case_evidence",
    }
    assert record["invocation_profile"]["retry_limit"] == 0


def test_compiler_derives_exact_wrapper_and_behavior_contracts() -> None:
    result = Gate5DeclarationAuthoringLanguageV2Factory.create().validate_candidate(
        _candidate()
    )

    assert result["status"] == "passed"
    assert result["definition_status"] == "partially_compilable"
    assert result["case_input_assessment"] == {
        "status": "not_evaluated",
        "reason": "no_case_evidence_in_authoring_context",
    }
    resolved = result["requirements"][0]["resolved_compositions"]
    assert resolved[0]["capability_inputs"] == [
        {
            "contract": "broker_reports_gate5_published_behavior_ref_v1",
            "name": "behavior_ref",
            "required": True,
        },
        {
            "contract": "broker_reports_gate5_contract_identity_v1",
            "name": "input_contract_id",
            "required": True,
        },
        {
            "contract": "broker_reports_gate5_contract_identity_v1",
            "name": "output_contract_id",
            "required": True,
        },
        {
            "contract": "registered_behavior_input",
            "name": "behavior_input",
            "required": True,
        },
        {
            "contract": "artifact_access_context",
            "name": "trusted_case_context",
            "required": True,
        },
    ]
    assert resolved[0]["capability_output_contract"] == (
        "broker_reports_gate5_typed_behavior_result_v1"
    )
    assert resolved[0]["behavior_binding"]["input_contract_id"] == (
        "broker_reports_gate5_securities_disposal_resolved_inputs_v0"
    )
    assert resolved[0]["behavior_binding"]["output_contract_id"] == (
        "broker_reports_gate5_securities_disposal_operation_tax_model_v0"
    )
    assert result["manual_repairs_total"] == 0


def test_gap_does_not_require_an_identifier_for_absent_runtime_object() -> None:
    candidate = _candidate()
    gap = candidate["gaps"][0]
    gap["related_capability_ids"] = []
    gap["related_artifact_refs"] = []

    result = Gate5DeclarationAuthoringLanguageV2Factory.create().validate_candidate(
        candidate
    )

    assert result["status"] == "passed"
    assert result["first_blocking_gap_id"] == gap["gap_id"]


def test_plain_json_parser_is_exact_and_repair_free() -> None:
    language = Gate5DeclarationAuthoringLanguageV2Factory.create()
    candidate = _candidate()
    raw = json.dumps(candidate, ensure_ascii=False).encode("utf-8")

    assert language.parse_candidate_response(raw) == candidate
    assert language.validate_candidate_response(raw)["status"] == "passed"


@pytest.mark.parametrize(
    ("raw", "error"),
    [
        (b"", "candidate_response_empty"),
        (b"```json\n{}\n```", "candidate_response_invalid"),
        (b"{} {}", "candidate_response_invalid"),
        (b"[]", "candidate_response_not_object"),
    ],
)
def test_plain_json_parser_rejects_non_object_or_repairable_text(
    raw: bytes, error: str
) -> None:
    with pytest.raises(Gate5DeclarationAuthoringLanguageError, match=error):
        Gate5DeclarationAuthoringLanguageV2Factory.create().parse_candidate_response(
            raw
        )


def test_schema_rejects_the_old_case_evidence_claim_field() -> None:
    candidate = _candidate()
    candidate["requirements"][0]["end_to_end_available_from_current_case_evidence"] = (
        True
    )

    with pytest.raises(
        Gate5DeclarationAuthoringLanguageError,
        match="candidate_schema_invalid:requirements.0",
    ):
        Gate5DeclarationAuthoringLanguageV2Factory.create().validate_candidate(
            candidate
        )


def test_validator_rejects_unknown_capability() -> None:
    candidate = _candidate()
    candidate["requirements"][0]["compositions"][0]["capability_id"] = (
        "invented_capability_v0"
    )

    with pytest.raises(
        Gate5DeclarationAuthoringLanguageError, match="capability_unknown"
    ):
        Gate5DeclarationAuthoringLanguageV2Factory.create().validate_candidate(
            candidate
        )


def test_validator_rejects_unknown_behavior() -> None:
    candidate = _candidate()
    candidate["requirements"][0]["compositions"][0]["behavior_ref"]["behavior_id"] = (
        "invented_behavior_v0"
    )

    with pytest.raises(
        Gate5DeclarationAuthoringLanguageError, match="behavior_unknown"
    ):
        Gate5DeclarationAuthoringLanguageV2Factory.create().validate_candidate(
            candidate
        )


def test_validator_requires_behavior_only_for_typed_execution() -> None:
    no_behavior = _candidate()
    no_behavior["requirements"][0]["compositions"][0]["behavior_ref"] = None
    with pytest.raises(
        Gate5DeclarationAuthoringLanguageError, match="behavior_missing"
    ):
        Gate5DeclarationAuthoringLanguageV2Factory.create().validate_candidate(
            no_behavior
        )

    unexpected = _candidate()
    unexpected["requirements"][0]["compositions"][2]["behavior_ref"] = copy.deepcopy(
        unexpected["requirements"][0]["compositions"][0]["behavior_ref"]
    )
    with pytest.raises(
        Gate5DeclarationAuthoringLanguageError, match="behavior_unexpected"
    ):
        Gate5DeclarationAuthoringLanguageV2Factory.create().validate_candidate(
            unexpected
        )


def test_validator_requires_known_artifact_with_matching_capability_role() -> None:
    missing = _candidate()
    missing["requirements"][0]["compositions"][2]["artifact_refs"] = []
    with pytest.raises(
        Gate5DeclarationAuthoringLanguageError, match="artifact_missing"
    ):
        Gate5DeclarationAuthoringLanguageV2Factory.create().validate_candidate(missing)

    wrong_role = _candidate()
    wrong_role["requirements"][0]["compositions"][2]["artifact_refs"] = [
        wrong_role["requirements"][0]["compositions"][0]["artifact_refs"][0]
    ]
    with pytest.raises(
        Gate5DeclarationAuthoringLanguageError, match="artifact_role_mismatch"
    ):
        Gate5DeclarationAuthoringLanguageV2Factory.create().validate_candidate(
            wrong_role
        )


def test_supported_and_unsupported_requirements_fail_closed() -> None:
    supported_without_composition = _candidate()
    supported_without_composition["requirements"][0]["compositions"] = []
    with pytest.raises(
        Gate5DeclarationAuthoringLanguageError, match="supported_unit_invalid"
    ):
        Gate5DeclarationAuthoringLanguageV2Factory.create().validate_candidate(
            supported_without_composition
        )

    unsupported_without_gap = _candidate()
    unsupported_without_gap["requirements"][1]["gap_refs"] = []
    with pytest.raises(
        Gate5DeclarationAuthoringLanguageError, match="unsupported_unit_invalid"
    ):
        Gate5DeclarationAuthoringLanguageV2Factory.create().validate_candidate(
            unsupported_without_gap
        )


def test_first_blocker_must_belong_to_first_unsupported_requirement() -> None:
    candidate = _candidate()
    second = copy.deepcopy(candidate["requirements"][1])
    second["requirement_id"] = "later-unsupported-semantic"
    second["gap_refs"] = ["later-gap"]
    candidate["requirements"].append(second)
    later_gap = copy.deepcopy(candidate["gaps"][0])
    later_gap["gap_id"] = "later-gap"
    later_gap["requirement_id"] = "later-unsupported-semantic"
    candidate["gaps"].append(later_gap)
    candidate["first_blocking_gap_id"] = "later-gap"

    with pytest.raises(
        Gate5DeclarationAuthoringLanguageError, match="first_blocker_invalid"
    ):
        Gate5DeclarationAuthoringLanguageV2Factory.create().validate_candidate(
            candidate
        )


def test_current_language_owner_has_no_provider_transport_or_runtime_execution() -> (
    None
):
    source = inspect.getsource(language_module)

    assert FACTORY_REQUIRED
    assert FORBIDDEN
    for forbidden in (
        "subprocess",
        "requests.",
        "urlopen",
        "codex exec",
        "def run_operation",
        "def execute(",
    ):
        assert forbidden not in source
