from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import goal391_instructional_classification_contract as contract  # noqa: E402


def _case():
    return contract.build_case(table={"table_ref": "table_1", "header_row_choices": [1], "rows": [], "rows_total": 0, "rows_truncated": False, "column_distinct_values": [], "source_context": {"entries": [{"context_ref": "context_1", "relation": "PRECEDING_SAME_CONTAINER", "literal": "Example"}]}})


def test_instructional_response_requires_selected_owner_context() -> None:
    value = {
        "schema_version": contract.OUTPUT_SCHEMA_VERSION,
        "classification": "INSTRUCTIONAL_REFERENCE",
        "header_row": 1,
        "classification_evidence": [
            {"context_ref": "context_1", "relation": "PRECEDING_SAME_CONTAINER"}
        ],
    }
    assert contract.validate_response(response=value, case=_case()) == value


@pytest.mark.parametrize("classification,evidence", [("INSTRUCTIONAL_REFERENCE", []), ("NOT_INSTRUCTIONAL", [{"context_ref": "context_1", "relation": "PRECEDING_SAME_CONTAINER"}])])
def test_instructional_evidence_cannot_be_missing_or_leak_to_other_status(classification, evidence) -> None:
    with pytest.raises(contract.InstructionalClassificationContractError):
        contract.validate_response(
            response={
                "schema_version": contract.OUTPUT_SCHEMA_VERSION,
                "classification": classification,
                "header_row": 1,
                "classification_evidence": evidence,
            },
            case=_case(),
        )


def test_header_must_be_one_of_owner_supplied_choices() -> None:
    with pytest.raises(contract.InstructionalClassificationContractError):
        contract.validate_response(
            response={
                "schema_version": contract.OUTPUT_SCHEMA_VERSION,
                "classification": "NOT_INSTRUCTIONAL",
                "header_row": 2,
                "classification_evidence": [],
            },
            case=_case(),
        )
