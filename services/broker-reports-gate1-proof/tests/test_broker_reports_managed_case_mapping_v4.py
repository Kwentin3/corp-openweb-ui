from __future__ import annotations

import copy
import hashlib
import json

import pytest

from broker_reports_gate1 import ordinary_trade_semantic_compiler as compiler_module
from broker_reports_gate1.ordinary_trade_semantic_compiler import (
    ORDINARY_TRADE_MANAGED_CASE_MAPPING_SCHEMA_VERSION,
    OrdinaryTradeSemanticCompilerError,
    OrdinaryTradeSemanticCompilerFactory,
    compile_managed_header_case_mapping_candidate,
    compile_schema_mapping,
    validate_managed_header_case_mapping_candidate,
    validate_schema_mapping,
)
from tests.test_broker_reports_logical_row_table_recovery import (
    _pdf_bytes,
)
from tests.test_broker_reports_managed_canonical_projection import (
    _canonical_from_handoff,
    _canonical_handoff,
    _synchronized_table_mutation,
)
from tests.test_broker_reports_managed_pdf_document_v2 import _managed_full_source
from tests.test_broker_reports_pdf_document_visual_adjudication import (
    _page_candidate_refs,
    _visual_table,
)


def _canonical_for_parents(
    monkeypatch: pytest.MonkeyPatch,
    *,
    left_parent: str,
    right_parent: str,
    case_suffix: str = "base",
    span_first_parent: bool = False,
) -> tuple[dict, dict, dict]:
    x_positions = (10, 54, 98, 142, 186, 230, 274)
    x_boundaries = (7, 51, 95, 139, 183, 227, 271, 319)
    parent_labels = (
        left_parent,
        right_parent,
        "Oper",
        "Qty",
        "Unit",
        "Curr",
        "Gross",
    )
    leaf_labels = ("Date", "Date", "Side", "Qty", "Price", "Code", "Amount")
    data_values = (
        "D1",
        "D2",
        "BUY",
        "10",
        "100",
        "RUB",
        "1000",
    )
    pages = []
    for y_parent, y_leaf, y_data, y_second, y0, y1, horizontal_ys in (
        (72, 55, 38, 22, 15, 82, (15, 30, 46, 63, 82)),
    ):
        pages.append(
            {
                "texts": [
                    *[
                        (x, y_parent, literal)
                        for x, literal in zip(x_positions, parent_labels, strict=True)
                    ],
                    *[
                        (x, y_leaf, literal)
                        for x, literal in zip(x_positions, leaf_labels, strict=True)
                    ],
                    *[
                        (x, y_data, literal)
                        for x, literal in zip(x_positions, data_values, strict=True)
                    ],
                    *[
                        (x, y_second, literal)
                        for x, literal in zip(x_positions, data_values, strict=True)
                    ],
                ],
                "vectors": [
                    *[f"7 {y} m 319 {y} l S" for y in horizontal_ys],
                    *[
                        f"{x} {y0} m {x} {y1} l S"
                        for x in x_boundaries
                    ],
                ],
            }
        )
    pdf_bytes = _pdf_bytes(pages)
    source_ref = f"private_pdf_managed_case_{left_parent.lower()}_{case_suffix}"
    payload = _managed_full_source(
        pdf_bytes,
        source_artifact_ref=source_ref,
    ).payloads[0]
    observations = []
    for page_number in (1,):
        refs = _page_candidate_refs(payload, page_number)
        observations.append(
            {
                "tables": [
                    _visual_table(
                        payload,
                        page_number=page_number,
                        title_refs=[],
                        header_groups=[refs[:7], refs[7:14]],
                        body_refs=refs[14:],
                    )
                ]
            }
        )
    handoff = _canonical_handoff(
        monkeypatch,
        pdf_bytes=pdf_bytes,
        source_ref=source_ref,
        observations={"pages": observations},
    )
    if span_first_parent:
        original = handoff.result.whole_table_projections[0]
        column_ids = [
            column["column_id"] for column in original["logical_columns"]
        ]

        def span(table: dict) -> None:
            entry = table["ordered_rows"][0]["entries"][0]
            entry["covers_logical_column_ids"] = column_ids[:2]
            entry["column_binding_status"] = "BOUND"
            table["logical_columns"][1]["header_path"].insert(
                0, entry["entry_id"]
            )

        managed_payload, projection = _synchronized_table_mutation(handoff, span)
        canonical = _canonical_from_handoff(
            handoff,
            source_ref=source_ref,
            managed_payload=managed_payload,
            projections=(projection,),
        )
    else:
        canonical = _canonical_from_handoff(handoff, source_ref=source_ref)
    table = next(node for node in canonical["nodes"] if node["node_type"] == "TABLE")
    binding = {
        "document_id": f"document_{left_parent.lower()}_{case_suffix}",
        "canonical_version_id": f"canonical_{left_parent.lower()}_{case_suffix}",
        "canonical_root_sha256": canonical["canonical_root_hash"],
        "source_artifact_ref": canonical["source"]["source_artifact_ref"],
        "source_sha256": canonical["source"]["source_sha256"],
    }
    return canonical, table, binding


def _model_decision() -> dict:
    return {
        "columns": [
            {"column": 1, "semantic_role": "trade_date"},
            {"column": 2, "semantic_role": "asset_name"},
            {"column": 3, "semantic_role": "side"},
            {"column": 4, "semantic_role": "quantity"},
            {"column": 5, "semantic_role": "unit_price"},
            {"column": 6, "semantic_role": "currency"},
            {"column": 7, "semantic_role": "gross_amount"},
        ],
        "amount_currency_bindings": [
            {"amount_column": 7, "currency_column": 6}
        ],
    }


def _candidate(canonical: dict, table: dict, binding: dict) -> dict:
    return compile_managed_header_case_mapping_candidate(
        canonical=canonical,
        canonical_binding=binding,
        table_node_id=table["node_id"],
        model_decision=_model_decision(),
    )


def _rehash_candidate(candidate: dict) -> None:
    material = copy.deepcopy(candidate)
    material.pop("candidate_id", None)
    candidate["candidate_id"] = (
        "otmapcase_" + compiler_module._sha256_json(material)[:32]
    )


def test_same_leaf_different_parent_has_distinct_host_fingerprint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trade = _canonical_for_parents(
        monkeypatch,
        left_parent="Trade",
        right_parent="Settle",
    )
    order = _canonical_for_parents(
        monkeypatch,
        left_parent="Order",
        right_parent="Settle",
    )
    same_structure_new_case = _canonical_for_parents(
        monkeypatch,
        left_parent="Trade",
        right_parent="Settle",
        case_suffix="other",
    )
    spanning = _canonical_for_parents(
        monkeypatch,
        left_parent="Trade",
        right_parent="Settle",
        case_suffix="span",
        span_first_parent=True,
    )

    trade_candidate = _candidate(*trade)
    order_candidate = _candidate(*order)
    same_structure_candidate = _candidate(*same_structure_new_case)
    spanning_candidate = _candidate(*spanning)
    alternate_decision = _model_decision()
    alternate_decision["columns"][0]["semantic_role"] = "asset_name"
    alternate_decision["columns"][1]["semantic_role"] = "trade_date"
    alternate_semantics_candidate = compile_managed_header_case_mapping_candidate(
        canonical=trade[0],
        canonical_binding=trade[2],
        table_node_id=trade[1]["node_id"],
        model_decision=alternate_decision,
    )

    assert trade_candidate["schema_version"] == (
        ORDINARY_TRADE_MANAGED_CASE_MAPPING_SCHEMA_VERSION
    )
    assert trade_candidate["mapping_status"] == "CANDIDATE_ONLY"
    assert trade_candidate["runtime_activation"] is False
    assert trade_candidate["global_reuse"] is False
    assert "qualification_ref" not in trade_candidate
    assert "side_values" not in trade_candidate
    assert [
        column["header_path"][-1]["literal"]
        for column in trade_candidate["columns"][:2]
    ] == ["Date", "Date"]
    assert trade_candidate["structural_fingerprint"] != order_candidate[
        "structural_fingerprint"
    ]
    assert trade_candidate["structural_fingerprint"] == same_structure_candidate[
        "structural_fingerprint"
    ]
    assert trade_candidate["structural_fingerprint"] != spanning_candidate[
        "structural_fingerprint"
    ]
    assert trade_candidate["structural_fingerprint"] == (
        alternate_semantics_candidate["structural_fingerprint"]
    )
    assert trade_candidate["candidate_id"] != alternate_semantics_candidate[
        "candidate_id"
    ]
    assert trade_candidate["candidate_id"] != same_structure_candidate[
        "candidate_id"
    ]


def test_rehashed_forged_reordered_or_truncated_host_path_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical, table, binding = _canonical_for_parents(
        monkeypatch,
        left_parent="Trade",
        right_parent="Settle",
    )
    base = _candidate(canonical, table, binding)
    candidates = []

    forged = copy.deepcopy(base)
    forged["columns"][0]["header_path"][0]["literal"] = "Forged"
    candidates.append(forged)

    reordered = copy.deepcopy(base)
    reordered["columns"][0]["header_path"].reverse()
    candidates.append(reordered)

    truncated = copy.deepcopy(base)
    truncated["columns"][0]["header_path"].pop()
    candidates.append(truncated)

    boolean_ordinal = copy.deepcopy(base)
    boolean_ordinal["columns"][0]["column"] = True
    candidates.append(boolean_ordinal)

    for candidate in candidates:
        _rehash_candidate(candidate)
        with pytest.raises(OrdinaryTradeSemanticCompilerError) as exc:
            validate_managed_header_case_mapping_candidate(
                value=candidate,
                canonical=canonical,
                canonical_binding=binding,
                table_node_id=table["node_id"],
            )
        assert exc.value.code == "ordinary_trade_managed_case_mapping_columns_invalid"


def test_case_candidate_binds_exact_view_canonical_managed_and_table_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical, table, binding = _canonical_for_parents(
        monkeypatch,
        left_parent="Trade",
        right_parent="Settle",
    )
    base = _candidate(canonical, table, binding)
    mutations = (
        lambda item: item["header_view_binding"].update(
            {"header_view_sha256": "a" * 64}
        ),
        lambda item: item["header_view_binding"]["canonical_binding"].update(
            {"document_id": "document_forged"}
        ),
        lambda item: item["header_view_binding"].update(
            {"table_node_id": "node_forged"}
        ),
        lambda item: item["header_view_binding"]["managed_binding"].update(
            {"managed_table_id": "table_forged"}
        ),
    )
    for mutate in mutations:
        candidate = copy.deepcopy(base)
        mutate(candidate)
        _rehash_candidate(candidate)
        with pytest.raises(OrdinaryTradeSemanticCompilerError) as exc:
            validate_managed_header_case_mapping_candidate(
                value=candidate,
                canonical=canonical,
                canonical_binding=binding,
                table_node_id=table["node_id"],
            )
        assert exc.value.code == "ordinary_trade_managed_case_mapping_contract_invalid"


def test_model_cannot_author_header_literals_and_v3_rejects_v4(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical, table, binding = _canonical_for_parents(
        monkeypatch,
        left_parent="Trade",
        right_parent="Settle",
    )
    for forbidden_field in (
        "literal",
        "header_path",
        "source_literal",
        "normalized_value",
        "header_view_sha256",
    ):
        decision = _model_decision()
        decision["columns"][0][forbidden_field] = "model-authored"
        with pytest.raises(OrdinaryTradeSemanticCompilerError) as exc:
            compile_managed_header_case_mapping_candidate(
                canonical=canonical,
                canonical_binding=binding,
                table_node_id=table["node_id"],
                model_decision=decision,
            )
        assert exc.value.code == "ordinary_trade_managed_case_model_columns_invalid"

    decision = _model_decision()
    decision["side_values"] = [
        {"source_literal": "BUY", "normalized_value": "PURCHASE"}
    ]
    with pytest.raises(OrdinaryTradeSemanticCompilerError) as exc:
        compile_managed_header_case_mapping_candidate(
            canonical=canonical,
            canonical_binding=binding,
            table_node_id=table["node_id"],
            model_decision=decision,
        )
    assert exc.value.code == "ordinary_trade_managed_case_model_decision_invalid"

    candidate = _candidate(canonical, table, binding)
    with pytest.raises(OrdinaryTradeSemanticCompilerError):
        validate_schema_mapping(candidate)
    with pytest.raises(OrdinaryTradeSemanticCompilerError):
        OrdinaryTradeSemanticCompilerFactory.create().compile(
            canonical=canonical,
            canonical_binding=binding,
            mappings=[candidate],
        )


def test_each_missing_required_role_blocks_candidate_only_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical, table, binding = _canonical_for_parents(
        monkeypatch,
        left_parent="Trade",
        right_parent="Settle",
    )
    for required_role in (
        "asset_name",
        "trade_date",
        "side",
        "quantity",
        "unit_price",
        "currency",
        "gross_amount",
    ):
        decision = _model_decision()
        target = next(
            item
            for item in decision["columns"]
            if item["semantic_role"] == required_role
        )
        target["semantic_role"] = "unmapped"
        if required_role in {"currency", "gross_amount"}:
            decision["amount_currency_bindings"] = []
        with pytest.raises(OrdinaryTradeSemanticCompilerError) as exc:
            compile_managed_header_case_mapping_candidate(
                canonical=canonical,
                canonical_binding=binding,
                table_node_id=table["node_id"],
                model_decision=decision,
            )
        assert exc.value.code == "ordinary_trade_managed_case_required_roles_missing"


def test_one_row_v3_mapping_bytes_remain_frozen() -> None:
    mapping = compile_schema_mapping(
        title_literal=None,
        headers=[
            {"column": index, "literal": f"Header {index}"}
            for index in range(1, 8)
        ],
        model_columns=[
            {"column": index, "semantic_role": role}
            for index, role in enumerate(
                (
                    "asset_name",
                    "trade_date",
                    "side",
                    "quantity",
                    "unit_price",
                    "currency",
                    "gross_amount",
                ),
                start=1,
            )
        ],
        amount_currency_bindings=[{"amount_column": 7, "currency_column": 6}],
        side_values=[{"source_literal": "BUY", "normalized_value": "PURCHASE"}],
        qualification_ref={
            "qualification_id": "otqual_v3_frozen",
            "receipt_sha256": "a" * 64,
        },
    )
    assert validate_schema_mapping(mapping) == mapping
    assert hashlib.sha256(
        json.dumps(
            mapping,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest() == "9eece4e3d176c0a8e74c18f44d7312ba14bf4e96b8398ddb7593fc02d595c65e"
