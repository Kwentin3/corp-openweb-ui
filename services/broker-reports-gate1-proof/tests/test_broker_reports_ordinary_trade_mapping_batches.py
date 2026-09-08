from __future__ import annotations

import copy
import hashlib
import json

import pytest

from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    OrdinaryTradeSemanticMappingError,
    OrdinaryTradeSemanticMappingFactory,
)

import test_broker_reports_issue312_mapping_case as case_fixtures
import test_broker_reports_ordinary_trade_production_candidate as candidate_fixtures


def _prepared(tmp_path):
    _store, context, _document_id, canonical, binding = (
        case_fixtures._unknown_two_table_case(tmp_path)
    )
    semantic = OrdinaryTradeSemanticMappingFactory.create()
    target_ids = [
        item["node_id"] for item in canonical["nodes"] if item["node_type"] == "TABLE"
    ]
    plan = semantic.build_mapping_batch_plan(
        canonical=canonical,
        confirmed_understandings=[],
        target_table_node_ids=target_ids,
    )
    plan = {
        **plan,
        "batches": [
            {
                "batch_id": f"batch_{index:04d}",
                "target_table_node_ids": [table_node_id],
                "mapping_package_sha256": _sha256_json(
                    semantic.build_mapping_package(
                        canonical=canonical,
                        confirmed_understandings=[],
                        target_table_node_ids=[table_node_id],
                    )
                ),
            }
            for index, table_node_id in enumerate(plan["target_table_node_ids"], start=1)
        ],
    }
    tables = {item["node_id"]: item for item in canonical["nodes"] if item["node_type"] == "TABLE"}
    outcomes = []
    for batch in plan["batches"]:
        table = tables[batch["target_table_node_ids"][0]]
        headers = tuple(
            cell["displayed_value"]
            for cell in sorted(
                (
                    cell
                    for cell in table["content"]["cells"]
                    if cell["row"] == 1
                ),
                key=lambda cell: cell["column"],
            )
        )
        response = case_fixtures._complete(
            table, candidate_fixtures._mapping_from_headers(headers)
        )
        outcomes.append(
            {
                "batch_id": batch["batch_id"],
                "outcome": semantic.validate_mapping_response(
                    response=response,
                    canonical=canonical,
                    canonical_binding=binding,
                    model_id="models/gemini-3.5-flash",
                    provider_profile_id="google_gemini",
                    execution_metadata=case_fixtures._metadata(),
                    confirmed_understandings=[],
                    user_scope_sha256=hashlib.sha256(
                        context.user_id.encode()
                    ).hexdigest(),
                    target_table_node_ids=batch["target_table_node_ids"],
                ),
            }
        )
    return semantic, canonical, binding, context, plan, outcomes


def _sha256_json(value) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        .encode("utf-8")
    ).hexdigest()


def test_aggregate_replays_compiler_after_full_disjoint_coverage(tmp_path) -> None:
    semantic, canonical, binding, context, plan, outcomes = _prepared(tmp_path)

    aggregate = semantic.aggregate_mapping_batch_outcomes(
        canonical=canonical,
        canonical_binding=binding,
        user_scope_sha256=hashlib.sha256(context.user_id.encode()).hexdigest(),
        confirmed_understandings=[],
        batch_plan=plan,
        batch_outcomes=outcomes,
    )

    assert aggregate["status"] == "COMPLETE"
    assert [item["table_node_id"] for item in aggregate["table_resolutions"]] == plan[
        "target_table_node_ids"
    ]
    assert [item["table_node_id"] for item in aggregate["projection"]["qualified_table_resolutions"]] == plan[
        "target_table_node_ids"
    ]
    assert aggregate["projection"]["runtime_records"]


@pytest.mark.parametrize("kind", ["overlap", "missing"])
def test_batch_plan_rejects_overlap_or_missing_coverage(tmp_path, kind: str) -> None:
    semantic, canonical, binding, context, plan, outcomes = _prepared(tmp_path)
    forged = copy.deepcopy(plan)
    if kind == "overlap":
        forged["batches"][1]["target_table_node_ids"] = list(
            forged["batches"][0]["target_table_node_ids"]
        )
    else:
        forged["batches"] = forged["batches"][:1]

    with pytest.raises(OrdinaryTradeSemanticMappingError) as rejected:
        semantic.aggregate_mapping_batch_outcomes(
            canonical=canonical,
            canonical_binding=binding,
            user_scope_sha256=hashlib.sha256(context.user_id.encode()).hexdigest(),
            confirmed_understandings=[],
            batch_plan=forged,
            batch_outcomes=outcomes,
        )

    assert rejected.value.code == "ordinary_trade_mapping_batch_plan_coverage_invalid"


def test_aggregate_rejects_outcome_attached_to_wrong_batch(tmp_path) -> None:
    semantic, canonical, binding, context, plan, outcomes = _prepared(tmp_path)
    forged = copy.deepcopy(outcomes)
    forged[0]["batch_id"], forged[1]["batch_id"] = (
        forged[1]["batch_id"],
        forged[0]["batch_id"],
    )

    with pytest.raises(OrdinaryTradeSemanticMappingError) as rejected:
        semantic.aggregate_mapping_batch_outcomes(
            canonical=canonical,
            canonical_binding=binding,
            user_scope_sha256=hashlib.sha256(context.user_id.encode()).hexdigest(),
            confirmed_understandings=[],
            batch_plan=plan,
            batch_outcomes=forged,
        )

    assert rejected.value.code == "ordinary_trade_mapping_batch_outcome_coverage_invalid"
