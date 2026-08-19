"""G5.61 one-contract LLM metadata adapter and provenance validator."""

from __future__ import annotations

import copy
import inspect

import pytest
from jsonschema import Draft202012Validator

from broker_reports_gate1.canonical_artifact import (
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
    validate_canonical_artifact,
)
from broker_reports_gate1.gate2_model_contracts import gate2_provider_profile
from broker_reports_gate1.gate2_model_requests import (
    GATE3_LLM_METADATA_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)
from broker_reports_gate1.gate2_provider_adapters import (
    Gate2ProviderAdapterFactory,
)
from broker_reports_gate1.gate3_llm_metadata_adapter import (
    GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION,
    GATE3_LLM_METADATA_INSTRUCTION,
    GATE3_LLM_METADATA_INSTRUCTION_VERSION,
    GATE3_LLM_METADATA_PROPOSAL_SCHEMA_VERSION,
    Gate3LlmMetadataAdapterError,
    build_metadata_context_package,
    compose_metadata_model_visible_request,
    metadata_proposal_response_schema,
    validate_metadata_proposal,
)
import broker_reports_gate1.gate3_llm_metadata_adapter as metadata_adapter_module
import broker_reports_gate1.canonical_artifact as canonical_artifact_module
from broker_reports_gate1.gate3_metadata_source_facts import (
    GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
    GATE3_MINIMAL_METADATA_FACT_TYPES,
)


DOCUMENT_ID = "document-g561"
MODEL_ID = "models/gemini-3.5-flash"


def _canonical(*texts: str) -> dict:
    artifact = (
        CanonicalNormalizerFactory(
            CanonicalNormalizerConfig(normalizer_version="g561-test-v1")
        )
        .create()
        .build(
            tenant_id="g561-test-user",
            artifact_version=1,
            document={
                "container_format": "pdf",
                "sha256": "6" * 64,
                "declared_mime_type": "application/pdf",
            },
            source_artifact_ref="source-g561",
            source_payloads=[
                {
                    "parser_completeness_status": "complete",
                    "parser_completeness_reason_codes": [],
                    "pdf_text_layer_projection": {
                        "page_inventory": [{"page_number": 1}],
                        "line_inventory": [],
                    },
                }
            ],
            source_units=[
                {
                    "unit_ref": f"g561-unit-{index}",
                    "source_location": {"page": 1, "line_start": index},
                    "text": text,
                }
                for index, text in enumerate(texts, start=1)
            ],
            table_projections=[],
        )
    )
    assert validate_canonical_artifact(artifact)["passed"]
    return artifact


def _canonical_table(rows: tuple[tuple[str, ...], ...]) -> dict:
    cells = []
    private_values = []
    for row_index, row in enumerate(rows, start=1):
        for column_index, value in enumerate(row, start=1):
            value_ref = f"v{row_index}_{column_index}"
            cells.append(
                {
                    "row_ordinal": row_index,
                    "column_ordinal": column_index,
                    "normalized_private_value_path": value_ref,
                }
            )
            private_values.append(
                {"value_path_ref": value_ref, "normalized_value": value}
            )
    artifact = (
        CanonicalNormalizerFactory(
            CanonicalNormalizerConfig(normalizer_version="g564-table-test-v1")
        )
        .create()
        .build(
            tenant_id="g564-test-user",
            artifact_version=1,
            document={
                "container_format": "pdf",
                "sha256": "7" * 64,
                "declared_mime_type": "application/pdf",
            },
            source_artifact_ref="source-g564-table",
            source_payloads=[
                {
                    "parser_completeness_status": "complete",
                    "parser_completeness_reason_codes": [],
                    "pdf_text_layer_projection": {
                        "page_inventory": [{"page_number": 1}],
                        "line_inventory": [],
                    },
                }
            ],
            source_units=[
                {
                    "unit_ref": "g564-table-unit",
                    "source_location": {"page": 1, "line_start": 1},
                    "text": " ".join(value for row in rows for value in row),
                }
            ],
            table_projections=[
                {
                    "projection_status": "ready",
                    "table_projection_id": "g564-table-projection",
                    "source_unit_ref": "g564-table-unit",
                    "row_count": len(rows),
                    "column_count": len(rows[0]),
                    "cells": cells,
                    "private_values": private_values,
                }
            ],
        )
    )
    assert validate_canonical_artifact(artifact)["passed"]
    return artifact


def _declare_first_table_row_as_header(artifact: dict) -> dict:
    result = copy.deepcopy(artifact)
    table = next(node for node in result["nodes"] if node["node_type"] == "TABLE")
    table["content"]["header"] = list(table["content"]["rows"][0])
    source = result["source"]
    result["canonical_root_hash"] = canonical_artifact_module._sha256(
        canonical_artifact_module._root_hash_material(
            normalizer_version=result["normalizer_version"],
            source_format=source["source_format"],
            source_sha256=source["source_sha256"],
            containers=result["containers"],
            nodes=result["nodes"],
            provenance=result["provenance"],
            issues=result["issues"],
        )
    )
    assert validate_canonical_artifact(result)["passed"]
    return result


def _package(artifact: dict) -> tuple[dict, dict]:
    return build_metadata_context_package(
        artifact=artifact,
        document_id=DOCUMENT_ID,
        canonical_version_id=artifact["artifact_id"],
    )


def _proposal(*facts: dict) -> dict:
    return {
        "schema_version": GATE3_LLM_METADATA_PROPOSAL_SCHEMA_VERSION,
        "facts": list(facts),
    }


def _fact(
    fact_type: str,
    alias: str,
    literal: str,
    *,
    role_alias: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    return {
        "fact_type": fact_type,
        "source_target_alias": alias,
        "role_evidence_target_alias": role_alias or alias,
        "source_literal": literal,
        "period_start_literal": start,
        "period_end_literal": end,
    }


def _validate(
    artifact: dict,
    package: dict,
    registry: dict,
    proposal: dict,
) -> dict:
    return validate_metadata_proposal(
        raw_model_output=proposal,
        artifact=artifact,
        context_package=package,
        binding_registry=registry,
        model_id=MODEL_ID,
    )


def test_one_frozen_contract_instruction_schema_and_three_part_request() -> None:
    assert GATE3_MINIMAL_METADATA_CONTRACT_VERSION == "1.0.0"
    assert GATE3_LLM_METADATA_INSTRUCTION_VERSION == "1.2.0"
    assert len(GATE3_MINIMAL_METADATA_FACT_TYPES) == 11
    assert "positive source evidence" in GATE3_LLM_METADATA_INSTRUCTION
    assert "role_evidence_target_alias" in GATE3_LLM_METADATA_INSTRUCTION
    assert "excluding its role label" in GATE3_LLM_METADATA_INSTRUCTION

    schema = metadata_proposal_response_schema()
    Draft202012Validator.check_schema(schema)
    artifact = _canonical("Unfamiliar wording: Ada Lovelace")
    package, _registry = _package(artifact)
    request = compose_metadata_model_visible_request(
        context_package=package,
        response_schema=schema,
    )

    assert [item["role"] for item in request["messages"]] == [
        "system",
        "user",
        "user",
    ]
    assert request["response_format"]["json_schema"]["strict"] is True
    assert request["response_format"]["json_schema"]["name"] == (
        GATE3_LLM_METADATA_PROPOSAL_SCHEMA_VERSION
    )


def test_g567_semantic_contract_is_positive_and_has_no_known_term_blacklist() -> None:
    instruction = GATE3_LLM_METADATA_INSTRUCTION

    assert "explicit assertion that the designation is a broker or investment account" in instruction
    assert "explicit assertion that the legal entity acts as broker or issuer" in instruction
    assert "explicit assertion that the designation is the current account's contract" in instruction
    assert "If positive role evidence is absent or ambiguous, omit the fact" in instruction
    assert "trading code" not in instruction.lower()
    assert "client code" not in instruction.lower()
    assert "company blacklist" not in instruction.lower()


def test_metadata_sealed_request_uses_generic_provider_schema_projection() -> None:
    artifact = _canonical("Unfamiliar wording: Ada Lovelace")
    package, _registry = _package(artifact)
    response_schema = metadata_proposal_response_schema()
    request = compose_metadata_model_visible_request(
        context_package=package,
        response_schema=response_schema,
    )
    form_data = Gate2OpenWebUIRequestBuilder(
        request_profile=GATE3_LLM_METADATA_REQUEST_PROFILE
    ).build_from_sealed_gate3_metadata(
        model_visible_request=request,
        model_id=MODEL_ID,
    )
    adapter = Gate2ProviderAdapterFactory(
        profile=gate2_provider_profile("google_gemini")
    ).create()

    prepared = adapter.prepare_gate3_metadata_form_data(
        form_data=form_data,
        response_format=request["response_format"],
    )

    assert set(prepared.form_data) == {
        "model",
        "messages",
        "stream",
        "response_format",
    }
    assert prepared.form_data["model"] == MODEL_ID
    assert "metadata" not in prepared.form_data
    assert prepared.canonical_schema_hash
    assert prepared.provider_visible_schema["properties"]["facts"]["type"] == ("array")


def test_context_selection_is_structural_and_has_no_semantic_selector() -> None:
    source = "\n".join(
        (
            inspect.getsource(build_metadata_context_package),
            inspect.getsource(
                __import__(
                    "broker_reports_gate1.gate3_llm_metadata_adapter",
                    fromlist=["_text_line_candidates"],
                )._text_line_candidates
            ),
            inspect.getsource(
                __import__(
                    "broker_reports_gate1.gate3_llm_metadata_adapter",
                    fromlist=["_small_table_row_candidates"],
                )._small_table_row_candidates
            ),
        )
    ).lower()

    assert GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION == (
        "broker_reports_metadata_context_policy_v4"
    )
    assert "party_name" not in source
    assert "broker_legal_name" not in source
    assert "account_identifier" not in source
    assert "layout ==" not in source
    assert "page ==" not in source
    assert "_patterns" not in source
    assert "oracle" not in source
    assert "text_head" not in source
    assert "[:24]" not in source
    assert "small_table_rows_max" not in source
    assert "region_chars_max" not in source


def test_text_below_old_cutoff_remains_visible_without_position_rule() -> None:
    lines = [f"opaque structural line {index}" for index in range(80)]
    lines.insert(67, "Unfamiliar assertion :: Ada Lovelace")
    artifact = _canonical("\n".join(lines))
    package, registry = _package(artifact)

    assert package["metrics"]["position_cutoff_applied"] is False
    assert package["metrics"]["all_structural_candidates_selected"] is True
    assert "Ada Lovelace" in package["regions"][67]["content"]

    result = _validate(
        artifact,
        package,
        registry,
        _proposal(_fact("PARTY_NAME", "m068", "Ada Lovelace")),
    )
    assert result["coverage"]["typed_metadata_facts"] == 1


def test_small_table_does_not_invent_header_and_excludes_large_table() -> None:
    def table(cells: list[dict]) -> dict:
        return {
            "node_id": "table-node",
            "node_type": "TABLE",
            "order": 1,
            "source_refs": ["table-ref"],
            "content": {"cells": cells},
        }

    small_cells = [
        {
            "row": row,
            "column": 1,
            "displayed_value": f"opaque-{row}",
            "source_refs": [f"cell-{row}"],
        }
        for row in range(1, 21)
    ]
    small = metadata_adapter_module._small_table_row_candidates(
        node=table(small_cells),
        node_ordinal=0,
    )
    assert len(small) == 20
    assert small[-1]["region_kind"] == "SMALL_TABLE_ROW"
    assert small[-1]["content"] == "R20: C1: opaque-20"
    assert len(small[-1]["fragments"]) == 1
    assert small[-1]["structural_address"] == {
        "kind": "table_cell",
        "row": 20,
        "column": 1,
        "header_row": None,
    }

    large_cells = [
        {
            "row": row,
            "column": 1,
            "displayed_value": f"opaque-{row}",
            "source_refs": [f"cell-{row}"],
        }
        for row in range(1, 66)
    ]
    large = table(large_cells)
    assert metadata_adapter_module._is_large_table(large) is True
    assert (
        metadata_adapter_module._small_table_row_candidates(
            node=large,
            node_ordinal=0,
        )
        == []
    )


def test_each_text_line_has_one_physical_address_without_semantic_routing() -> None:
    artifact = _canonical(
        "Client: Ada Lovelace\n"
        "Signed by: Ada Lovelace\n"
        "Account: ACCOUNT-A"
    )

    package, registry = _package(artifact)

    assert [region["region_kind"] for region in package["regions"]] == [
        "TEXT_LINE",
        "TEXT_LINE",
        "TEXT_LINE",
    ]
    assert [region["content"] for region in package["regions"]] == [
        "L0: Client: Ada Lovelace",
        "L1: Signed by: Ada Lovelace",
        "L2: Account: ACCOUNT-A",
    ]
    assert [
        target["fragments"][0]["field_path"]
        for target in registry["targets"].values()
    ] == [
        "content.text.lines[0]",
        "content.text.lines[1]",
        "content.text.lines[2]",
    ]
    assert all(
        len(target["fragments"]) == 1
        for target in registry["targets"].values()
    )


def test_each_table_alias_has_one_exact_cell_address_with_rich_row_context() -> None:
    artifact = _canonical_table((("Local label", "VALUE-A"),))
    package, registry = _package(artifact)

    assert package["regions"] == [
        {
            "target_alias": "m001",
            "region_kind": "SMALL_TABLE_ROW",
            "target_content": "Local label",
            "content": "R1: C1: Local label | C2: VALUE-A",
            "source_field_path": "content.cells[0]",
        },
        {
            "target_alias": "m002",
            "region_kind": "SMALL_TABLE_ROW",
            "target_content": "VALUE-A",
            "content": "R1: C1: Local label | C2: VALUE-A",
            "source_field_path": "content.cells[1]",
        },
    ]
    assert all(len(target["fragments"]) == 1 for target in registry["targets"].values())


def test_positive_role_evidence_same_target_accepts_explicit_roles_and_clean_value() -> None:
    artifact = _canonical(
        "Account: ACCOUNT-A\n"
        "Broker: Example Broker Ltd\n"
        "Agreement: CONTRACT-7"
    )
    package, registry = _package(artifact)

    result = _validate(
        artifact,
        package,
        registry,
        _proposal(
            _fact("ACCOUNT_IDENTIFIER", "m001", "ACCOUNT-A"),
            _fact("BROKER_LEGAL_NAME", "m002", "Example Broker Ltd"),
            _fact("ACCOUNT_CONTRACT_IDENTIFIER", "m003", "CONTRACT-7"),
        ),
    )

    assert [fact["value"]["normalized"] for fact in result["metadata_facts"]] == [
        "ACCOUNT-A",
        "Example Broker Ltd",
        "CONTRACT-7",
    ]
    assert all(
        fact["source_binding"]["role_evidence_binding"]["source_target_alias"]
        == fact["source_binding"]["source_target_alias"]
        for fact in result["metadata_facts"]
    )


def test_role_header_and_value_row_may_use_different_targets() -> None:
    artifact = _declare_first_table_row_as_header(
        _canonical_table(
            (
                ("Account", "Owner"),
                ("ACCOUNT-A", "Ada Lovelace"),
            )
        )
    )
    package, registry = _package(artifact)

    result = _validate(
        artifact,
        package,
        registry,
        _proposal(
            _fact(
                "ACCOUNT_IDENTIFIER",
                "m003",
                "ACCOUNT-A",
                role_alias="m001",
            )
        ),
    )

    fact = result["metadata_facts"][0]
    assert fact["source_binding"]["source_target_alias"] == "m003"
    assert (
        fact["source_binding"]["role_evidence_binding"]["source_target_alias"]
        == "m001"
    )
    assert (
        fact["source_binding"]["role_evidence_binding"]["value_relation"]
        == "TABLE_HEADER_LINEAGE"
    )


def test_direct_role_value_relation_matrix_is_structural_and_fail_closed() -> None:
    key_value = _canonical_table(
        (
            ("Type of account", "Personal account"),
            ("Client code", "TF1467223"),
        )
    )
    package, registry = _package(key_value)

    same_row = _validate(
        key_value,
        package,
        registry,
        _proposal(
            _fact(
                "ACCOUNT_IDENTIFIER",
                "m004",
                "TF1467223",
                role_alias="m003",
            )
        ),
    )
    assert (
        same_row["metadata_facts"][0]["source_binding"]["role_evidence_binding"]
        ["value_relation"]
        == "SAME_TABLE_ROW"
    )

    with pytest.raises(
        Gate3LlmMetadataAdapterError,
        match="gate3_llm_metadata_role_value_relation_invalid",
    ):
        _validate(
            key_value,
            package,
            registry,
            _proposal(
                _fact(
                    "ACCOUNT_IDENTIFIER",
                    "m004",
                    "TF1467223",
                    role_alias="m001",
                )
            ),
        )


def test_same_page_without_same_atomic_structure_is_not_direct_relation() -> None:
    artifact = _canonical("Account", "ACCOUNT-A")
    package, registry = _package(artifact)

    with pytest.raises(
        Gate3LlmMetadataAdapterError,
        match="gate3_llm_metadata_role_value_relation_invalid",
    ):
        _validate(
            artifact,
            package,
            registry,
            _proposal(
                _fact(
                    "ACCOUNT_IDENTIFIER",
                    "m002",
                    "ACCOUNT-A",
                    role_alias="m001",
                )
            ),
        )


def test_value_without_positive_role_evidence_produces_no_fact() -> None:
    artifact = _canonical(
        "Opaque identifier: CODE-A\n"
        "Payment recipient: Example Company"
    )
    package, registry = _package(artifact)

    result = _validate(artifact, package, registry, _proposal())

    assert result["metadata_facts"] == []
    assert result["coverage"]["published_metadata_facts"] == 0


def test_role_evidence_is_required_and_must_bind_to_canonical_target() -> None:
    artifact = _canonical("Account: ACCOUNT-A")
    package, registry = _package(artifact)
    missing_role = _fact("ACCOUNT_IDENTIFIER", "m001", "ACCOUNT-A")
    missing_role.pop("role_evidence_target_alias")

    with pytest.raises(
        Gate3LlmMetadataAdapterError,
        match="gate3_llm_metadata_response_contract_invalid",
    ):
        _validate(artifact, package, registry, _proposal(missing_role))

    with pytest.raises(
        Gate3LlmMetadataAdapterError,
        match="gate3_llm_metadata_role_target_unknown",
    ):
        _validate(
            artifact,
            package,
            registry,
            _proposal(
                _fact(
                    "ACCOUNT_IDENTIFIER",
                    "m001",
                    "ACCOUNT-A",
                    role_alias="m999",
                )
            ),
        )


def test_factory_uses_canonical_and_gate2_factory_client_without_bypass() -> None:
    source = inspect.getsource(metadata_adapter_module)
    factory_source = inspect.getsource(
        metadata_adapter_module.Gate3LlmMetadataAdapterFactory
    )

    assert "ArtifactResolver(store)" in factory_source
    assert "CanonicalReaderFactory(" in factory_source
    assert ".propose_gate3_metadata_once(" in factory_source
    assert "requests" not in source
    assert "openai" not in source.lower()
    assert "anthropic" not in source.lower()
    assert "gemini" not in source.lower()
    assert "gate4" not in factory_source.lower()
    assert "gate5" not in factory_source.lower()
    assert "persistence" not in factory_source.lower()


def test_new_wording_can_bind_without_a_python_language_rule() -> None:
    artifact = _canonical("Primary beneficial human :: Ada Lovelace")
    package, registry = _package(artifact)
    alias = package["regions"][0]["target_alias"]

    result = _validate(
        artifact,
        package,
        registry,
        _proposal(_fact("PARTY_NAME", alias, "Ada Lovelace")),
    )

    assert result["coverage"]["typed_metadata_facts"] == 1
    assert result["metadata_facts"][0]["fact_type"] == "PARTY_NAME"
    assert result["metadata_facts"][0]["value"] == {
        "kind": "text",
        "normalized": "Ada Lovelace",
    }
    assert result["metadata_facts"][0]["source_binding"]["source_refs"]


def test_multiple_accounts_and_periods_are_preserved_without_reconciliation() -> None:
    artifact = _canonical(
        "\n".join(
            (
                "Portfolio handles :: ACCOUNT-A and ACCOUNT-B",
                "Window alpha :: 01.01.2024 - 31.12.2024",
                "Window beta :: 01.01.2025 - 31.12.2025",
            )
        )
    )
    package, registry = _package(artifact)
    account_alias = package["regions"][0]["target_alias"]
    first_period_alias = package["regions"][1]["target_alias"]
    second_period_alias = package["regions"][2]["target_alias"]

    result = _validate(
        artifact,
        package,
        registry,
        _proposal(
            _fact("ACCOUNT_IDENTIFIER", account_alias, "ACCOUNT-A"),
            _fact("ACCOUNT_IDENTIFIER", account_alias, "ACCOUNT-B"),
            _fact(
                "STATEMENT_PERIOD",
                first_period_alias,
                "01.01.2024 - 31.12.2024",
                start="01.01.2024",
                end="31.12.2024",
            ),
            _fact(
                "STATEMENT_PERIOD",
                second_period_alias,
                "01.01.2025 - 31.12.2025",
                start="01.01.2025",
                end="31.12.2025",
            ),
        ),
    )

    assert [fact["fact_type"] for fact in result["metadata_facts"]] == [
        "ACCOUNT_IDENTIFIER",
        "ACCOUNT_IDENTIFIER",
        "STATEMENT_PERIOD",
        "STATEMENT_PERIOD",
    ]
    assert [fact["value"] for fact in result["metadata_facts"][-2:]] == [
        {"kind": "period", "start": "2024-01-01", "end": "2024-12-31"},
        {"kind": "period", "start": "2025-01-01", "end": "2025-12-31"},
    ]


def test_exact_timestamp_period_boundaries_normalize_without_source_repair() -> None:
    artifact = _canonical("Window :: 2024-12-31 23:59:59 - 2025-12-31 23:59:59")
    package, registry = _package(artifact)

    result = _validate(
        artifact,
        package,
        registry,
        _proposal(
            _fact(
                "STATEMENT_PERIOD",
                "m001",
                "2024-12-31 23:59:59 - 2025-12-31 23:59:59",
                start="2024-12-31 23:59:59",
                end="2025-12-31 23:59:59",
            )
        ),
    )

    assert result["metadata_facts"][0]["value"] == {
        "kind": "period",
        "start": "2024-12-31",
        "end": "2025-12-31",
    }


def test_duplicate_same_physical_assertion_fails_closed() -> None:
    artifact = _canonical("Account assertion :: ACCOUNT-A")
    package, registry = _package(artifact)
    alias = package["regions"][0]["target_alias"]
    duplicate = _fact("ACCOUNT_IDENTIFIER", alias, "ACCOUNT-A")

    with pytest.raises(
        Gate3LlmMetadataAdapterError,
        match="gate3_llm_metadata_duplicate_assertion",
    ):
        _validate(
            artifact,
            package,
            registry,
            _proposal(duplicate, copy.deepcopy(duplicate)),
        )


def test_repeated_same_assertion_publishes_one_fact_with_all_evidence() -> None:
    artifact = _canonical(
        "Client assertion :: Ada Lovelace",
        "Client assertion :: Ada Lovelace",
        "Client assertion :: Ada Lovelace",
    )
    package, registry = _package(artifact)

    result = _validate(
        artifact,
        package,
        registry,
        _proposal(
            *(
                _fact("PARTY_NAME", f"m{index:03d}", "Ada Lovelace")
                for index in range(1, 4)
            )
        ),
    )

    assert result["coverage"]["raw_validated_assertions"] == 3
    assert result["coverage"]["collapsed_repeated_assertions"] == 2
    assert result["coverage"]["published_metadata_facts"] == 1
    fact = result["metadata_facts"][0]
    evidence = fact["source_binding"]["evidence_locations"]
    assert [item["source_target_alias"] for item in evidence] == [
        "m001",
        "m002",
        "m003",
    ]
    assert fact["source_binding"]["source_target_alias"] == "m001"


def test_same_literal_in_different_source_meaning_is_not_collapsed() -> None:
    artifact = _canonical(
        "Client assertion :: Ada Lovelace",
        "Signed by :: Ada Lovelace",
    )
    package, registry = _package(artifact)

    result = _validate(
        artifact,
        package,
        registry,
        _proposal(
            _fact("PARTY_NAME", "m001", "Ada Lovelace"),
            _fact("PARTY_NAME", "m002", "Ada Lovelace"),
        ),
    )

    assert result["coverage"]["raw_validated_assertions"] == 2
    assert result["coverage"]["collapsed_repeated_assertions"] == 0
    assert result["coverage"]["published_metadata_facts"] == 2
    assert all(
        len(fact["source_binding"]["evidence_locations"]) == 1
        for fact in result["metadata_facts"]
    )


def test_repeated_table_value_same_header_collapses_but_accounts_do_not() -> None:
    artifact = _declare_first_table_row_as_header(
        _canonical_table(
            (
                ("Account", "Owner"),
                ("ACCOUNT-A", "Ada Lovelace"),
                ("ACCOUNT-B", "Ada Lovelace"),
            )
        )
    )
    package, registry = _package(artifact)

    result = _validate(
        artifact,
        package,
        registry,
        _proposal(
            _fact("PARTY_NAME", "m004", "Ada Lovelace", role_alias="m002"),
            _fact("ACCOUNT_IDENTIFIER", "m003", "ACCOUNT-A", role_alias="m001"),
            _fact("PARTY_NAME", "m006", "Ada Lovelace", role_alias="m002"),
            _fact("ACCOUNT_IDENTIFIER", "m005", "ACCOUNT-B", role_alias="m001"),
        ),
    )

    assert result["coverage"]["raw_validated_assertions"] == 4
    assert result["coverage"]["collapsed_repeated_assertions"] == 1
    assert result["coverage"]["published_metadata_facts"] == 3
    party = next(
        fact for fact in result["metadata_facts"] if fact["fact_type"] == "PARTY_NAME"
    )
    assert len(party["source_binding"]["evidence_locations"]) == 2
    accounts = [
        fact["value"]["normalized"]
        for fact in result["metadata_facts"]
        if fact["fact_type"] == "ACCOUNT_IDENTIFIER"
    ]
    assert accounts == ["ACCOUNT-A", "ACCOUNT-B"]


def test_same_literal_under_different_table_labels_is_not_collapsed() -> None:
    artifact = _canonical_table(
        (
            ("Current subject", "Ada Lovelace"),
            ("Signed by", "Ada Lovelace"),
        )
    )
    package, registry = _package(artifact)

    result = _validate(
        artifact,
        package,
        registry,
        _proposal(
            _fact("PARTY_NAME", "m002", "Ada Lovelace", role_alias="m001"),
            _fact("PARTY_NAME", "m004", "Ada Lovelace", role_alias="m003"),
        ),
    )

    assert result["coverage"]["collapsed_repeated_assertions"] == 0
    assert result["coverage"]["published_metadata_facts"] == 2


@pytest.mark.parametrize(
    ("proposal", "error"),
    (
        (
            _proposal(_fact("PARTY_NAME", "m999", "Ada Lovelace")),
            "gate3_llm_metadata_target_unknown",
        ),
        (
            _proposal(_fact("PARTY_NAME", "m001", "Invented Person")),
            "gate3_llm_metadata_literal_not_in_target",
        ),
        (
            _proposal(
                _fact(
                    "STATEMENT_PERIOD",
                    "m002",
                    "01.01.2025 - 31.12.2025",
                    start="01.01.2025",
                    end="30.12.2025",
                )
            ),
            "gate3_llm_metadata_period_evidence_invalid",
        ),
        (
            _proposal(
                _fact(
                    "DOCUMENT_DATE",
                    "m003",
                    "Created :: 31.12.2025",
                    start="31.12.2025",
                )
            ),
            "gate3_llm_metadata_nonperiod_boundaries_forbidden",
        ),
    ),
)
def test_invalid_alias_literal_period_or_nonperiod_boundary_fails_closed(
    proposal: dict,
    error: str,
) -> None:
    artifact = _canonical(
        "Subject :: Ada Lovelace\n"
        "Period :: 01.01.2025 - 31.12.2025\n"
        "Created :: 31.12.2025"
    )
    package, registry = _package(artifact)

    with pytest.raises(Gate3LlmMetadataAdapterError, match=error):
        _validate(artifact, package, registry, proposal)


def test_tampered_document_version_path_or_source_refs_fail_closed() -> None:
    artifact = _canonical("Subject :: Ada Lovelace")
    package, registry = _package(artifact)
    proposal = _proposal(_fact("PARTY_NAME", "m001", "Ada Lovelace"))

    for mutate in (
        lambda item: item["targets"]["m001"].update(
            {"canonical_version_id": "other-version"}
        ),
        lambda item: item["targets"]["m001"]["fragments"][0].update(
            {"field_path": "content.text.lines[999]"}
        ),
        lambda item: item["targets"]["m001"].update({"source_refs": []}),
    ):
        tampered = copy.deepcopy(registry)
        mutate(tampered)
        with pytest.raises(
            Gate3LlmMetadataAdapterError,
            match="gate3_llm_metadata_target_binding_invalid",
        ):
            _validate(artifact, package, tampered, proposal)


def test_missing_shape_only_and_unsupported_metadata_create_no_fact() -> None:
    artifact = _canonical(
        "31.12.2025\n"
        "123456789012\n"
        "Mentioned Example Company\n"
        "Email: person@example.test\n"
        "Citizenship statement absent"
    )
    package, registry = _package(artifact)

    result = _validate(artifact, package, registry, _proposal())

    assert result["metadata_facts"] == []
    assert result["tax_meaning_assigned"] is False
    assert "TAX_RESIDENCY" not in GATE3_MINIMAL_METADATA_FACT_TYPES


def test_output_schema_forbids_unsupported_metadata_type() -> None:
    schema = metadata_proposal_response_schema()
    candidate = _proposal(_fact("TAX_RESIDENCY", "m001", "Somewhere"))

    errors = list(Draft202012Validator(schema).iter_errors(candidate))

    assert errors
    assert any("is not one of" in error.message for error in errors)
