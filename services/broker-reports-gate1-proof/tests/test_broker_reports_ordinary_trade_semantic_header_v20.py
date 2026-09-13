from __future__ import annotations

import pytest

from broker_reports_gate1.ordinary_trade_grouped_mapping_v20 import (
    ORDINARY_TRADE_GROUPED_MAPPING_V20_RESPONSE_SCHEMA_VERSION,
    expand_grouped_response,
)
from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    OrdinaryTradeSemanticMappingError,
    _validate_table_decision,
)


def _v20_response(*, header_row: int | None, disposition: str = "NO_NAMED_CONSUMER") -> dict:
    return {
        "schema_version": ORDINARY_TRADE_GROUPED_MAPPING_V20_RESPONSE_SCHEMA_VERSION,
        "status": "COMPLETE",
        "table_decisions": [
            {
                "table_ref": "table_1",
                "header_row": header_row,
                "disposition": disposition,
                "columns": [],
                "amount_currency_bindings": [],
                "side_values": [],
                "row_dispositions": [],
                "no_consumer_kind": "OTHER_NO_NAMED_CONSUMER",
            }
        ],
        "clarification": None,
        "message": "complete",
        "explicit_header_source_claims": {
            "schema_version": "broker_reports_ordinary_trade_explicit_header_source_response_v1",
            "claims": [],
        },
    }


def test_v20_preserves_model_selected_real_header_row_through_compact_adapter() -> None:
    # There is deliberately no physical-header field in the package surface.
    # The V20 choice remains a row reference until the semantic owner binds it.
    expanded = expand_grouped_response(
        response=_v20_response(header_row=2),
        package={"case": {"tables": [{"table_ref": "table_1", "rows": [
            {"row": 1, "cells": [{"column": 1, "literal": "note"}]},
            {"row": 2, "cells": [{"column": 1, "literal": "Date"}]},
        ]}]}},
    )
    assert expanded["schema_version"] == "broker_reports_ordinary_trade_semantic_mapping_response_v15"
    assert expanded["table_decisions"][0]["header_row"] == 2


def test_v20_header_selection_is_bound_to_a_nonempty_canonical_row_only() -> None:
    table = {
        "table_node_id": "table-a",
        "physical_header_row": None,
        "source_context_evidence": [{
            "context_ref": "context-a", "relation": "PRECEDING_SAME_CONTAINER",
            "canonical_node_id": "context-node-a", "literal_sha256": "a" * 64,
        }],
        "rows": [
            {"row": 1, "cells": [{"column": 1, "literal": "Date"}]},
            {"row": 2, "cells": [{"column": 1, "literal": "2026-01-01"}]},
        ],
    }
    decision = {
        "table_node_id": "table-a", "header_row": 1,
        "disposition": "NO_NAMED_CONSUMER", "columns": [],
        "amount_currency_bindings": [], "side_values": [], "row_dispositions": [],
        "no_consumer_kind": "OTHER_NO_NAMED_CONSUMER",
    }
    assert _validate_table_decision(
        decision=decision, table=table, allow_model_selected_header=True
    )["header_row"] == 1
    with pytest.raises(OrdinaryTradeSemanticMappingError) as exc:
        _validate_table_decision(
            decision={**decision, "header_row": 3},
            table=table,
            allow_model_selected_header=True,
        )
    assert exc.value.code == "ordinary_trade_semantic_mapping_header_invalid"
    with pytest.raises(OrdinaryTradeSemanticMappingError):
        _validate_table_decision(decision=decision, table=table)
