from __future__ import annotations

import ast
import copy
import hashlib
import inspect
from importlib import resources
import json

import pytest

from broker_reports_gate1 import (
    GATE5_DECLARATION_DEFINITION_CANDIDATE_RESOURCE,
    GATE5_DECLARATION_DEFINITION_CANDIDATE_RESOURCE_SHA256,
    GATE5_DECLARATION_DEFINITION_CONTEXT_RESOURCE,
    GATE5_DECLARATION_DEFINITION_CONTEXT_RESOURCE_SHA256,
    Gate5DeclarationDefinitionAuthoringFactory,
    Gate5DeclarationDefinitionError,
)
from broker_reports_gate1 import gate5_declaration_definition as definition_module
from broker_reports_gate1.gate5_declaration_definition import (
    FACTORY_REQUIRED,
    FORBIDDEN,
)


def test_hash_pinned_context_and_candidate_validate_as_partial_definition() -> None:
    package = resources.files("broker_reports_gate1")
    context_raw = package.joinpath(
        GATE5_DECLARATION_DEFINITION_CONTEXT_RESOURCE
    ).read_bytes()
    candidate_raw = package.joinpath(
        GATE5_DECLARATION_DEFINITION_CANDIDATE_RESOURCE
    ).read_bytes()

    assert hashlib.sha256(context_raw).hexdigest() == (
        GATE5_DECLARATION_DEFINITION_CONTEXT_RESOURCE_SHA256
    )
    assert hashlib.sha256(candidate_raw).hexdigest() == (
        GATE5_DECLARATION_DEFINITION_CANDIDATE_RESOURCE_SHA256
    )

    authoring = Gate5DeclarationDefinitionAuthoringFactory.create()
    validation = authoring.validate_candidate(authoring.candidate())

    assert validation["status"] == "validated"
    assert validation["definition_status"] == "partially_compilable"
    assert validation["gap_count"] == 2
    assert validation["independence_claim"] == (
        "structural_prompt_only_not_blind_to_governance_goal"
    )


def test_exact_model_payload_is_split_measured_and_prompt_has_no_expected_gap_hint() -> (
    None
):
    authoring = Gate5DeclarationDefinitionAuthoringFactory.create()
    payload = authoring.model_payload()
    metrics = authoring.section_metrics()

    assert list(payload) == [
        "system_instructions",
        "research_policy",
        "runtime_capabilities",
        "published_artifact_inventory",
        "official_evidence",
        "output_schema",
    ]
    assert metrics == {
        "token_metric": "unicode_lexical_tokens_v0_not_model_tokenizer",
        "sections": [
            {
                "section": "system_instructions",
                "utf8_bytes": 832,
                "unicode_lexical_tokens": 169,
            },
            {
                "section": "research_policy",
                "utf8_bytes": 593,
                "unicode_lexical_tokens": 110,
            },
            {
                "section": "runtime_capabilities",
                "utf8_bytes": 6775,
                "unicode_lexical_tokens": 1195,
            },
            {
                "section": "published_artifact_inventory",
                "utf8_bytes": 1785,
                "unicode_lexical_tokens": 389,
            },
            {
                "section": "official_evidence",
                "utf8_bytes": 4528,
                "unicode_lexical_tokens": 1071,
            },
            {
                "section": "output_schema",
                "utf8_bytes": 1097,
                "unicode_lexical_tokens": 245,
            },
        ],
        "enveloped_payload_utf8_bytes": 15747,
    }

    prompt = json.dumps(
        {
            "system_instructions": payload["system_instructions"],
            "research_policy": payload["research_policy"],
        },
        ensure_ascii=False,
    ).lower()
    for forbidden in (
        "section 2",
        "раздел 2",
        "line 060",
        "строк 060",
        "group tax base",
        "group-level tax base",
    ):
        assert forbidden not in prompt


def test_model_payload_contains_no_python_or_repository_execution_internals() -> None:
    serialized = json.dumps(
        Gate5DeclarationDefinitionAuthoringFactory.create().model_payload(),
        ensure_ascii=False,
    )

    for forbidden in (
        "RuntimeFactory",
        "Gate5Declaration",
        ".py",
        "ArtifactStore",
        "SELECT ",
        "run_python",
        "search_web",
    ):
        assert forbidden not in serialized


def test_compilation_report_keeps_conditional_fragments_and_both_real_gaps() -> None:
    authoring = Gate5DeclarationDefinitionAuthoringFactory.create()
    result = authoring.validate_candidate(authoring.candidate())
    rows = {item["requirement_id"]: item for item in result["compilation_report"]}

    assert rows["appendix8_complete_category_aggregation"]["status"] == "COMPILABLE"
    assert rows["appendix8_complete_category_aggregation"]["capability_ids"] == [
        "aggregate_complete_category_scope_v0"
    ]
    assert rows["appendix8_projection_from_complete_semantics"]["status"] == (
        "COMPILABLE"
    )
    assert rows["appendix8_operation_members_from_case"]["gap_refs"] == [
        "gap-operation-member-production"
    ]
    assert rows["section2_group_tax_base"]["gap_refs"] == [
        "gap-section2-group-tax-base"
    ]


def test_unknown_capability_fails_closed() -> None:
    authoring, candidate = _candidate()
    requirement = _requirement(candidate, "appendix8_complete_category_aggregation")
    requirement["capability_refs"][0]["capability_id"] = "calculate_3ndfl_2025"

    with pytest.raises(Gate5DeclarationDefinitionError) as caught:
        authoring.validate_candidate(candidate)

    assert caught.value.code == "gate5_declaration_definition_capability_unsupported"


def test_capability_output_and_input_contract_mismatches_fail_closed() -> None:
    authoring, candidate = _candidate()
    projection = _requirement(candidate, "appendix8_projection_from_complete_semantics")
    projection["semantic_output"]["contract"] = (
        "broker_reports_gate5_tax_period_category_aggregation_result_v0"
    )

    with pytest.raises(Gate5DeclarationDefinitionError) as output_caught:
        authoring.validate_candidate(candidate)
    assert output_caught.value.code == (
        "gate5_declaration_definition_output_incompatible"
    )

    authoring, candidate = _candidate()
    projection = _requirement(candidate, "appendix8_projection_from_complete_semantics")
    projection["declared_inputs"][0]["contract"] = (
        "broker_reports_gate5_combined_requirement_check_result_v0"
    )
    with pytest.raises(Gate5DeclarationDefinitionError) as input_caught:
        authoring.validate_candidate(candidate)
    assert input_caught.value.code == "gate5_declaration_definition_input_incompatible"


def test_unknown_or_incompatible_artifact_reference_fails_closed() -> None:
    authoring, candidate = _candidate()
    projection = _requirement(candidate, "appendix8_projection_from_complete_semantics")
    projection["artifact_refs"][0]["artifact_version"] = "2099.0"

    with pytest.raises(Gate5DeclarationDefinitionError) as unknown:
        authoring.validate_candidate(candidate)
    assert unknown.value.code == "gate5_declaration_definition_artifact_unresolvable"

    authoring, candidate = _candidate()
    projection = _requirement(candidate, "appendix8_projection_from_complete_semantics")
    projection["artifact_refs"][0]["role"] = "nested_validated_projection"
    with pytest.raises(Gate5DeclarationDefinitionError) as incompatible:
        authoring.validate_candidate(candidate)
    assert (
        incompatible.value.code == "gate5_declaration_definition_artifact_incompatible"
    )


def test_free_form_execution_field_is_rejected_before_schema_fallback() -> None:
    authoring, candidate = _candidate()
    candidate["action"] = "run_python"

    with pytest.raises(Gate5DeclarationDefinitionError) as caught:
        authoring.validate_candidate(candidate)

    assert caught.value.code == (
        "gate5_declaration_definition_free_form_execution_forbidden"
    )


def test_unresolved_requirement_and_gap_type_must_stay_consistent() -> None:
    authoring, candidate = _candidate()
    requirement = _requirement(candidate, "section2_group_tax_base")
    requirement["gap_refs"] = []

    with pytest.raises(Gate5DeclarationDefinitionError) as missing_link:
        authoring.validate_candidate(candidate)
    assert missing_link.value.code == (
        "gate5_declaration_definition_gap_status_inconsistent"
    )

    authoring, candidate = _candidate()
    gap = next(
        item
        for item in candidate["gaps"]
        if item["gap_id"] == "gap-section2-group-tax-base"
    )
    gap["missing_artifact_kind"] = "projection"
    with pytest.raises(Gate5DeclarationDefinitionError) as wrong_type:
        authoring.validate_candidate(candidate)
    assert wrong_type.value.code == (
        "gate5_declaration_definition_gap_type_inconsistent"
    )


def test_target_must_equal_official_evidence_identity() -> None:
    authoring, candidate = _candidate()
    candidate["target"]["tax_period"] = "2024"

    with pytest.raises(Gate5DeclarationDefinitionError) as caught:
        authoring.validate_candidate(candidate)

    assert caught.value.code == (
        "gate5_declaration_definition_target_evidence_mismatch"
    )


def test_validator_is_static_factory_routed_and_has_no_dynamic_loading() -> None:
    assert any("Factory.create" in item for item in FACTORY_REQUIRED)
    assert any("workflow engine" in item for item in FORBIDDEN)

    source = inspect.getsource(definition_module)
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_from = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "importlib" not in imports
    assert "importlib.util" not in imported_from
    assert "importlib.machinery" not in imported_from
    assert "import_module(" not in source
    assert "__import__(" not in source
    assert "for step in" not in source


def _candidate() -> tuple[object, dict]:
    authoring = Gate5DeclarationDefinitionAuthoringFactory.create()
    return authoring, copy.deepcopy(authoring.candidate())


def _requirement(candidate: dict, requirement_id: str) -> dict:
    return next(
        item
        for item in candidate["requirements"]
        if item["requirement_id"] == requirement_id
    )
