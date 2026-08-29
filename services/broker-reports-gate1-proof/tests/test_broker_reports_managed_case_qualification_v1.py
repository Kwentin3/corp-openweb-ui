from __future__ import annotations

import copy
import inspect

import pytest

from broker_reports_gate1.ordinary_trade_qualified_mappings import (
    MANAGED_CASE_QUALIFICATION_SCHEMA_VERSION,
    OrdinaryTradeQualifiedMappingAuthorityFactory,
)
from broker_reports_gate1.ordinary_trade_semantic_compiler import (
    compile_managed_header_case_mapping_candidate,
)
from tests.test_broker_reports_managed_case_mapping_v4 import (
    _canonical_for_parents,
    _model_decision,
)
from tests.test_broker_reports_managed_header_view import (
    _reseal_canonical_root,
    _reseal_entry_locator,
)


USER_SCOPE_SHA256 = "7" * 64


def _inputs(monkeypatch: pytest.MonkeyPatch) -> tuple[dict, dict, dict]:
    return _canonical_for_parents(
        monkeypatch,
        left_parent="Trade",
        right_parent="Settle",
    )


def _side_decisions() -> list[dict[str, str]]:
    return [{"source_literal": "BUY", "normalized_value": "PURCHASE"}]


def _understandings() -> list[dict[str, str]]:
    return [
        {
            "question_id": "question-side-buy",
            "option_id": "option-purchase",
            "label_sha256": "8" * 64,
            "decision_sha256": "9" * 64,
        }
    ]


def _qualify(
    canonical: dict,
    table: dict,
    binding: dict,
    *,
    side_decisions: list[dict[str, str]] | None = None,
    understandings: list[dict[str, str]] | None = None,
) -> tuple[dict, dict]:
    return (
        OrdinaryTradeQualifiedMappingAuthorityFactory.create()
        .qualify_managed_header_case_mapping(
            canonical=canonical,
            canonical_binding=binding,
            table_node_id=table["node_id"],
            model_mapping_decision=_model_decision(),
            user_scope_sha256=USER_SCOPE_SHA256,
            model_side_normalization_decisions=(
                _side_decisions() if side_decisions is None else side_decisions
            ),
            confirmed_understandings=(
                _understandings() if understandings is None else understandings
            ),
        )
    )


def _rehash_receipt(receipt: dict) -> None:
    from broker_reports_gate1 import ordinary_trade_qualified_mappings as module

    material = copy.deepcopy(receipt)
    material.pop("receipt_sha256", None)
    material.pop("qualification_id", None)
    receipt["qualification_id"] = "otqual_" + module._sha256_json(material)[:32]
    receipt_without_hash = copy.deepcopy(receipt)
    receipt_without_hash.pop("receipt_sha256", None)
    receipt["receipt_sha256"] = module._sha256_json(receipt_without_hash)


def test_qualification_rebuilds_candidate_and_binds_exact_managed_side_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical, table, binding = _inputs(monkeypatch)
    candidate, receipt = _qualify(canonical, table, binding)
    rebuilt = compile_managed_header_case_mapping_candidate(
        canonical=canonical,
        canonical_binding=binding,
        table_node_id=table["node_id"],
        model_decision=_model_decision(),
    )

    assert candidate == rebuilt
    assert candidate["mapping_status"] == "CANDIDATE_ONLY"
    assert candidate["runtime_activation"] is False
    assert candidate["global_reuse"] is False
    assert "qualification_ref" not in candidate
    assert receipt["schema_version"] == MANAGED_CASE_QUALIFICATION_SCHEMA_VERSION
    assert receipt["qualification_status"] == "QUALIFIED_CANDIDATE_ONLY"
    assert receipt["runtime_activation"] is False
    assert receipt["global_reuse"] is False
    assert receipt["candidate_binding"]["columns"] == candidate["columns"]
    assert receipt["candidate_binding"]["header_view_binding"] == candidate[
        "header_view_binding"
    ]
    assert receipt["case_binding"] == {
        "canonical_binding": candidate["header_view_binding"][
            "canonical_binding"
        ],
        "table_node_id": table["node_id"],
        "managed_binding": candidate["header_view_binding"]["managed_binding"],
    }
    assert receipt["user_scope_sha256"] == USER_SCOPE_SHA256
    assert receipt["amount_currency_bindings"] == candidate[
        "amount_currency_bindings"
    ]
    assert receipt["side_evidence"]["data_rows_total"] == 2
    assert [
        item["literal"] for item in receipt["side_evidence"]["literals"]
    ] == ["BUY"]
    assert len(receipt["side_evidence"]["literals"][0]["observations"]) == 2
    data_row_numbers = {
        index
        for index, item in enumerate(
            table["content"]["metadata"]["managed_row_sequence"], start=1
        )
        if item["role"] == "DATA"
    }
    assert [
        item["source_coordinate"]
        for item in receipt["side_evidence"]["literals"][0]["observations"]
    ] == [
        cell["source_coordinate"]
        for cell in table["content"]["cells"]
        if cell["row"] in data_row_numbers and cell["column"] == 3
    ]
    assert receipt["side_normalizations"] == [
        {
            "side_evidence_ref": receipt["side_evidence"]["literals"][0][
                "side_evidence_ref"
            ],
            "source_literal": "BUY",
            "normalized_value": "PURCHASE",
        }
    ]

    validated = (
        OrdinaryTradeQualifiedMappingAuthorityFactory.create()
        .validate_managed_header_case_mapping(
            canonical=canonical,
            canonical_binding=binding,
            table_node_id=table["node_id"],
            model_mapping_decision=_model_decision(),
            user_scope_sha256=USER_SCOPE_SHA256,
            model_side_normalization_decisions=_side_decisions(),
            confirmed_understandings=_understandings(),
            receipt=receipt,
        )
    )
    assert validated == (candidate, receipt)


@pytest.mark.parametrize(
    "side_decisions",
    [
        [],
        [{"source_literal": " BUY ", "normalized_value": "PURCHASE"}],
        [{"source_literal": "BUY", "normalized_value": "UNKNOWN"}],
        [
            {
                "source_literal": "BUY",
                "normalized_value": "PURCHASE",
                "side_evidence_ref": "model-authored",
            }
        ],
    ],
)
def test_side_decisions_are_complete_exact_and_closed(
    monkeypatch: pytest.MonkeyPatch,
    side_decisions: list[dict[str, str]],
) -> None:
    canonical, table, binding = _inputs(monkeypatch)
    with pytest.raises(RuntimeError) as exc:
        _qualify(
            canonical,
            table,
            binding,
            side_decisions=side_decisions,
        )
    assert (
        str(exc.value)
        == "ordinary_trade_managed_case_side_normalization_invalid"
    )


def test_unknown_row_or_empty_side_literal_blocks_qualification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base, base_table, base_binding = _inputs(monkeypatch)

    unknown = copy.deepcopy(base)
    unknown_table = next(
        node for node in unknown["nodes"] if node["node_id"] == base_table["node_id"]
    )
    sequence = unknown_table["content"]["metadata"]["managed_row_sequence"]
    row_number = next(
        index
        for index, item in enumerate(sequence, start=1)
        if item["role"] == "DATA"
    )
    sequence[row_number - 1]["role"] = "UNKNOWN"
    for cell in unknown_table["content"]["cells"]:
        if cell["row"] == row_number:
            _reseal_entry_locator(
                unknown,
                cell,
                lambda locator: locator.update({"managed_row_role": "UNKNOWN"}),
            )
    unknown_binding = _reseal_canonical_root(unknown, base_binding)
    with pytest.raises(RuntimeError) as exc:
        _qualify(unknown, unknown_table, unknown_binding)
    assert "ordinary_trade_canonical_managed_data_replay_roles_invalid" in str(
        exc.value
    )

    empty = copy.deepcopy(base)
    empty_table = next(
        node for node in empty["nodes"] if node["node_id"] == base_table["node_id"]
    )
    empty_sequence = empty_table["content"]["metadata"]["managed_row_sequence"]
    data_row = next(
        index
        for index, item in enumerate(empty_sequence, start=1)
        if item["role"] == "DATA"
    )
    side_cell = next(
        cell
        for cell in empty_table["content"]["cells"]
        if cell["row"] == data_row and cell["column"] == 3
    )
    side_cell["value"] = ""
    side_cell["raw_value"] = ""
    side_cell["displayed_value"] = ""
    empty_sequence[data_row - 1]["entry_texts"][2] = ""
    empty_binding = _reseal_canonical_root(empty, base_binding)
    with pytest.raises(RuntimeError) as exc:
        _qualify(empty, empty_table, empty_binding)
    assert str(exc.value) == (
        "ordinary_trade_managed_case_side_evidence_incomplete"
    )


def test_rehashed_receipt_tamper_and_confirmation_downgrades_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical, table, binding = _inputs(monkeypatch)
    candidate, receipt = _qualify(canonical, table, binding)
    mutations = (
        lambda item: item["candidate_binding"]["columns"][0]["header_path"][
            0
        ].update({"literal": "Forged"}),
        lambda item: item["candidate_binding"]["header_view_binding"].update(
            {"header_view_sha256": "a" * 64}
        ),
        lambda item: item.update({"user_scope_sha256": "b" * 64}),
        lambda item: item["side_evidence"]["literals"][0]["observations"][
            0
        ].update({"canonical_provenance_ref": "prov_forged"}),
        lambda item: item["side_evidence"]["literals"][0]["observations"][
            0
        ].update({"source_coordinate": "row_forged:entry_forged"}),
        lambda item: item["amount_currency_bindings"][0].update(
            {"currency_column": 5}
        ),
    )
    for mutate in mutations:
        forged = copy.deepcopy(receipt)
        mutate(forged)
        _rehash_receipt(forged)
        with pytest.raises(RuntimeError) as exc:
            (
                OrdinaryTradeQualifiedMappingAuthorityFactory.create()
                .validate_managed_header_case_mapping(
                    canonical=canonical,
                    canonical_binding=binding,
                    table_node_id=table["node_id"],
                    model_mapping_decision=_model_decision(),
                    user_scope_sha256=USER_SCOPE_SHA256,
                    model_side_normalization_decisions=_side_decisions(),
                    confirmed_understandings=_understandings(),
                    receipt=forged,
                )
            )
        assert str(exc.value) == (
            "ordinary_trade_managed_case_qualification_receipt_invalid"
        )
    assert candidate["candidate_id"] == receipt["candidate_binding"]["candidate_id"]

    bad_confirmation = _understandings()
    bad_confirmation[0]["decision_sha256"] = "not-a-hash"
    with pytest.raises(RuntimeError) as exc:
        _qualify(
            canonical,
            table,
            binding,
            understandings=bad_confirmation,
        )
    assert str(exc.value) == "ordinary_trade_managed_case_confirmation_invalid"


def test_public_qualification_api_has_no_ready_candidate_or_view_input() -> None:
    authority = OrdinaryTradeQualifiedMappingAuthorityFactory.create()
    parameters = set(
        inspect.signature(
            authority.qualify_managed_header_case_mapping
        ).parameters
    )
    assert parameters == {
        "canonical",
        "canonical_binding",
        "table_node_id",
        "model_mapping_decision",
        "user_scope_sha256",
        "model_side_normalization_decisions",
        "confirmed_understandings",
    }
    assert "candidate" not in parameters
    assert "header_view" not in parameters
    assert "data_replay" not in parameters
