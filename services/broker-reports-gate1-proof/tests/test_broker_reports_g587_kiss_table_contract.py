from __future__ import annotations

import copy
from pathlib import Path
import sys

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SERVICE_ROOT / "scripts"
sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(SCRIPTS))

from g587_kiss_table_contract import (  # noqa: E402
    G587ContractError,
    SCHEMA_VERSION,
    compose_request,
    table_rows,
    validate_and_map,
)
from broker_reports_gate1.gate3_role_labeling import (  # noqa: E402
    Gate3RoleLabelingError,
)
from live_g587_kiss_table_microstand import (  # noqa: E402
    DEV_ORDINALS,
    _development_complete_for_holdout,
)


def _chunk() -> dict:
    return {
        "chunk_id": "g3chunk_test",
        "ordinal": 1,
        "canonical_binding": {
            "document_id": "brdoc_test",
            "canonical_version_id": "canver_test",
        },
        "structural_kind": "whole_table",
        "structural_scope": {
            "container_refs": ["container_test"],
            "node_refs": ["node_table"],
            "row_start": None,
            "row_end": None,
        },
        "context_policy": {
            "ancestor_headings": 2,
            "context_only_target_aliases": 0,
            "data_row_overlap": 0,
            "repeated_table_header": False,
            "repeated_table_notes": False,
        },
        "model_view": {
            "media_type": "text/markdown",
            "content": (
                "### Table\n\n| row | column 1 | column 2 |\n"
                "| --- | --- | --- |\n"
                "| [t001] 1 | [t002] Дата | [t003] Описание |\n"
                "| [t004] 2 | [t005] 2025-01-01 | [t006] Налог удержан |\n"
            ),
        },
        "target_mappings": [
            {
                "target_alias": "t001",
                "canonical_target": {
                    "kind": "table_row",
                    "node_id": "node_table",
                    "row": 1,
                },
            },
            {
                "target_alias": "t002",
                "canonical_target": {
                    "kind": "table_cell",
                    "node_id": "node_table",
                    "row": 1,
                    "column": 1,
                },
            },
            {
                "target_alias": "t003",
                "canonical_target": {
                    "kind": "table_cell",
                    "node_id": "node_table",
                    "row": 1,
                    "column": 2,
                },
            },
            {
                "target_alias": "t004",
                "canonical_target": {
                    "kind": "table_row",
                    "node_id": "node_table",
                    "row": 2,
                },
            },
            {
                "target_alias": "t005",
                "canonical_target": {
                    "kind": "table_cell",
                    "node_id": "node_table",
                    "row": 2,
                    "column": 1,
                },
            },
            {
                "target_alias": "t006",
                "canonical_target": {
                    "kind": "table_cell",
                    "node_id": "node_table",
                    "row": 2,
                    "column": 2,
                },
            },
        ],
        "metrics": {
            "model_view_chars": 1,
            "target_count": 6,
            "context_overhead_chars": 0,
        },
    }


def _response() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "rows": [
            {"row_id": "t001", "status": "NONE", "assertions": []},
            {
                "row_id": "t004",
                "status": "CLASSIFIED",
                "assertions": [{"financial_type": "TAX_WITHHELD", "roles": []}],
            },
        ],
    }


def _validate(response: dict):
    return validate_and_map(
        raw_model_output=response,
        chunk=_chunk(),
        canonical_artifact={"nodes": [], "provenance": []},
        model_id="models/gemini-3.5-flash",
    )


def test_exhaustive_response_maps_to_current_v2_contract_without_second_role_call():
    result = _validate(_response())

    assert result["row_statuses"] == {"t001": "NONE", "t004": "CLASSIFIED"}
    assert result["annotation_row_ids"] == ["t004"]
    mapped = result["mapped_financial_annotations_v2"]
    assert mapped["schema_version"] == "broker_reports_financial_annotations_v2"
    assert mapped["annotations"][0]["target"] == {
        "kind": "table_row",
        "node_id": "node_table",
        "row": 2,
    }
    assert mapped["annotations"][0]["financial_label"] == "TAX_WITHHELD"
    assert {item["status"] for item in mapped["annotations"][0]["roles"]} == {"missing"}


def test_request_is_one_exact_three_part_table_request_with_dynamic_alias_schema():
    request = compose_request(_chunk())

    assert [item["role"] for item in request["messages"]] == ["system", "user", "user"]
    assert request["messages"][2]["content"] == _chunk()["model_view"]["content"]
    schema = request["response_format"]["json_schema"]["schema"]
    row_schema = schema["properties"]["rows"]
    assert row_schema["minItems"] == row_schema["maxItems"] == 2
    assert row_schema["items"]["properties"]["row_id"]["enum"] == ["t001", "t004"]
    assert table_rows(_chunk())[1]["cells"][1]["cell_id"] == "t006"


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda value: value["rows"].pop(), "g587_response_row_missing"),
        (
            lambda value: value["rows"].append(copy.deepcopy(value["rows"][0])),
            "g587_response_row_duplicate",
        ),
        (
            lambda value: value["rows"][0].update(row_id="t999"),
            "g587_response_row_unknown",
        ),
        (
            lambda value: value["rows"][1]["assertions"][0].update(
                financial_type="UNKNOWN"
            ),
            "g587_financial_type_unknown",
        ),
        (
            lambda value: value["rows"][1]["assertions"][0]["roles"].append(
                {"role": "amount", "cell_id": "t002"}
            ),
            "g587_cell_cross_row",
        ),
        (
            lambda value: value["rows"][1]["assertions"][0]["roles"].append(
                {"role": "amount", "cell_id": "t999"}
            ),
            "g587_cell_unknown",
        ),
        (
            lambda value: value["rows"][1]["assertions"][0]["roles"].append(
                {"role": "quantity", "cell_id": "t005"}
            ),
            "g587_role_not_allowed",
        ),
    ],
)
def test_validator_fails_closed_on_contract_drift(mutate, code):
    response = _response()
    mutate(response)

    with pytest.raises(G587ContractError) as caught:
        _validate(response)

    assert caught.value.code == code


def test_none_and_unmapped_cannot_carry_assertions():
    response = _response()
    response["rows"][0]["assertions"] = [{"financial_type": "COMMISSION", "roles": []}]

    with pytest.raises(G587ContractError) as caught:
        _validate(response)

    assert caught.value.code == "g587_response_status_cardinality_invalid"


def test_source_empty_binding_is_rejected_locally_and_restored_as_missing(monkeypatch):
    class EmptyResolver:
        def __init__(self, *, canonical_artifact):
            del canonical_artifact

        def resolve(self, role_binding):
            del role_binding
            raise Gate3RoleLabelingError("gate3_role_target_text_empty")

    monkeypatch.setattr(
        "g587_kiss_table_contract.Gate3RoleValueResolver", EmptyResolver
    )
    response = _response()
    response["rows"][1]["assertions"][0]["roles"] = [
        {"role": "amount", "cell_id": "t006"}
    ]

    result = _validate(response)

    assert result["metrics"]["role_bindings_rejected"] == 1
    assert result["rejected_bindings"] == [
        {
            "row_id": "t004",
            "financial_type": "TAX_WITHHELD",
            "role": "amount",
            "cell_id": "t006",
            "error_code": "gate3_role_target_text_empty",
        }
    ]
    amount = next(
        item
        for item in result["mapped_financial_annotations_v2"]["annotations"][0]["roles"]
        if item["role"] == "amount"
    )
    assert amount == {"role": "amount", "status": "missing"}


def test_live_harness_persists_raw_response_before_local_validation():
    source = (SCRIPTS / "live_g587_kiss_table_microstand.py").read_text(
        encoding="utf-8"
    )

    raw_write = source.index("_atomic_write(raw_path, _json_bytes(raw_evidence))")
    validation = source.index("validated = validate_and_map(", raw_write)

    assert raw_write < validation
    assert '"status": "validator_failed"' in source


def test_frozen_holdout_can_follow_complete_negative_development_without_refinement():
    development = {
        "goal": "G5.88",
        "phase": "development",
        "qualified": False,
        "terminal": "KISS_TABLE_CONTRACT_SEMANTIC_RELIABILITY_INSUFFICIENT",
        "semantic_attempts": len(DEV_ORDINALS),
        "semantic_responses_received": len(DEV_ORDINALS),
        "semantic_retries": 0,
        "outcomes": [{"status": "validated"} for _ in DEV_ORDINALS],
    }

    assert _development_complete_for_holdout(development) is True
    development["semantic_retries"] = 1
    assert _development_complete_for_holdout(development) is False
