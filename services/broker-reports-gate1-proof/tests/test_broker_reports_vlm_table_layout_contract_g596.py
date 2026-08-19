from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SERVICE_ROOT / "scripts" / "local_vlm_table_layout_contract_g596.py"
MANIFEST_PATH = (
    SERVICE_ROOT / "benchmarks" / "table_layout_contract_g596" / "manifest.json"
)
sys.path.insert(0, str(SERVICE_ROOT))


def _load_runner():
    spec = importlib.util.spec_from_file_location("g596_runner_test", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = _load_runner()


def _table_contract(*, columns: int = 3, hints: bool = True) -> dict:
    return {
        "local_name": "table_candidate",
        "start_hints": {
            "anchor_tokens": ["Section"],
            "table_ordinal_after_anchor": 1,
        },
        "end_hints": {"boundary": "footer", "anchor_tokens": []},
        "structure": {
            "columns": columns,
            "header_rows": 1,
            "continuation": False,
            "body_row_pattern": "repeated",
            "wrapped_rows": "absent",
            "subtotal_rows": "absent",
        },
        "header_cell_token_hints": (
            [{"tokens": [value]} for value in ("Alpha", "Beta", "Gamma")]
            if hints
            else []
        ),
    }


def _layout(*, duplicate_candidate: bool = False) -> dict:
    words = [
        {"parser_ordinal": 1, "text": "Alpha", "bbox": [5.0, 11.0, 15.0, 15.0]},
        {"parser_ordinal": 2, "text": "Beta", "bbox": [45.0, 11.0, 55.0, 15.0]},
        {"parser_ordinal": 3, "text": "Gamma", "bbox": [85.0, 11.0, 95.0, 15.0]},
        {"parser_ordinal": 4, "text": "left", "bbox": [5.0, 21.0, 15.0, 25.0]},
        {"parser_ordinal": 5, "text": "middle", "bbox": [45.0, 21.0, 55.0, 25.0]},
        {"parser_ordinal": 6, "text": "right", "bbox": [85.0, 21.0, 95.0, 25.0]},
    ]
    cells = [
        {"bbox": [x0, y0, x1, y1]}
        for y0, y1 in ((10.0, 20.0), (20.0, 30.0))
        for x0, x1 in ((0.0, 25.0), (25.0, 50.0), (50.0, 75.0), (75.0, 100.0))
    ]
    candidate = {
        "bbox": [0.0, 10.0, 100.0, 30.0],
        "table_strategy_ref": "ruled_lines_v0",
        "rows_total": 2,
        "columns_total": 4,
        "cell_inventory": cells,
        "contributing_word_parser_ordinals": [1, 2, 3, 4, 5, 6],
    }
    candidates = [candidate, json.loads(json.dumps(candidate))] if duplicate_candidate else [candidate]
    return {
        "height": 100.0,
        "line_inventory": [
            {"text": "Section", "bbox": [0.0, 1.0, 30.0, 5.0]},
            {"text": "Footer", "bbox": [0.0, 95.0, 100.0, 99.0]},
        ],
        "word_inventory": words,
        "table_candidate_inventory": candidates,
    }


def _variant_a() -> dict:
    values = ("Alpha", "Beta", "Gamma", "left", "middle", "right")
    word_refs = [f"pdfword_{index}" for index in range(1, 7)]
    return {
        "lines": [
            {
                "word_parser_ordinals": list(range(1, 7)),
                "word_refs": word_refs,
            }
        ],
        "source_units": [
            {
                "pdf_layout_source_value_index": [
                    {
                        "source_object_ref": word_ref,
                        "source_value_ref": f"srcval_{index}",
                    }
                    for index, word_ref in enumerate(word_refs, 1)
                ]
            }
        ],
        "table_projections": [
            {
                "private_values": [
                    {"source_object_ref": word_ref, "normalized_value": literal}
                    for word_ref, literal in zip(word_refs, values)
                ]
            }
        ],
    }


def test_manifest_freezes_only_the_narrow_development_and_controls() -> None:
    manifest = RUNNER._load_manifest(MANIFEST_PATH)

    assert [case["page"] for case in manifest["cases"]] == [23, 24, 25, 26, 27, 28, 64]
    assert sum(case["role"].startswith("known_wrong") for case in manifest["cases"]) == 5
    assert manifest["acceptance"]["vlm_body_values_used"] == 0
    assert manifest["scope"]["production_activation"] is False


def test_vlm_contract_has_no_body_authority_canonical_id_or_bbox_channel() -> None:
    value = {"tables": [_table_contract()]}
    RUNNER.validate_vlm_page_contract(value)

    value["tables"][0]["body_values"] = ["forbidden"]
    with pytest.raises(RUNNER.G596Error, match="g596_vlm_forbidden_authority_field"):
        RUNNER.validate_vlm_page_contract(value)

    numeric_hint = {"tables": [_table_contract()]}
    numeric_hint["tables"][0]["start_hints"]["anchor_tokens"] = ["100"]
    with pytest.raises(RUNNER.G596Error, match="g596_vlm_body_value_like_hint_forbidden"):
        RUNNER.validate_vlm_page_contract(numeric_hint)


def test_layout_hints_rebin_only_exact_parser_words_and_source_refs() -> None:
    result = RUNNER.resolve_and_materialize(
        page_layout=_layout(),
        variant_a_page=_variant_a(),
        contract=_table_contract(),
        page_number=1,
        axis_registry={},
    )

    assert result["source_region"]["parser_columns"] == 4
    assert result["column_count"] == 3
    assert result["row_count"] == 2
    assert result["materialization_mode"] == "header_axis_rematerialized"
    assert result["source_word_count"] == 6
    assert result["source_value_ref_count"] == 6
    assert result["source_ref_coverage_ratio"] == 1.0
    assert result["invented_source_literals"] == 0
    assert result["vlm_body_values_used"] == 0
    assert [cell["literal"] for cell in result["rows"][1]["cells"]] == [
        "left",
        "middle",
        "right",
    ]


def test_existing_correct_source_grid_is_preserved_without_header_heuristics() -> None:
    layout = _layout()
    candidate = layout["table_candidate_inventory"][0]
    candidate["columns_total"] = 4
    contract = _table_contract(columns=4, hints=False)
    contract["structure"]["continuation"] = True
    axis_registry = {
        (RUNNER._line_signature(layout["line_inventory"][0]), 4): [
            0.0,
            25.0,
            50.0,
            75.0,
            100.0,
        ]
    }

    result = RUNNER.resolve_and_materialize(
        page_layout=layout,
        variant_a_page=_variant_a(),
        contract=contract,
        page_number=1,
        axis_registry=axis_registry,
    )

    assert result["materialization_mode"] == "preserved_verified_axis_candidate"
    assert result["column_count"] == result["source_region"]["parser_columns"] == 4
    assert result["source_ref_coverage_ratio"] == 1.0


def test_independent_headerless_contract_cannot_materialize_prose_candidate() -> None:
    contract = _table_contract(columns=4, hints=False)

    with pytest.raises(RUNNER.G596Error, match="g596_layout_axis_not_resolvable"):
        RUNNER.resolve_and_materialize(
            page_layout=_layout(),
            variant_a_page=_variant_a(),
            contract=contract,
            page_number=1,
            axis_registry={},
        )


def test_correct_source_grid_can_ignore_one_unresolved_vlm_header_hint() -> None:
    candidate = _layout()["table_candidate_inventory"][0]
    words = [
        {"parser_ordinal": 1, "text": "Alpha", "bbox": [5.0, 11.0, 15.0, 15.0]},
        {"parser_ordinal": 2, "text": "Beta", "bbox": [30.0, 11.0, 40.0, 15.0]},
        {"parser_ordinal": 3, "text": "Gamma", "bbox": [55.0, 11.0, 65.0, 15.0]},
    ]
    hints = [
        {"tokens": ["Alpha"]},
        {"tokens": ["Beta"]},
        {"tokens": ["Gamma"]},
        {"tokens": ["Approximate missing label"]},
    ]

    boundaries = RUNNER._verified_source_candidate_axis(words, candidate, hints, 4)

    assert boundaries == [0.0, 25.0, 50.0, 75.0, 100.0]


def test_two_source_regions_fail_closed_instead_of_selecting_by_overlap() -> None:
    with pytest.raises(RUNNER.G596Error, match="g596_source_region_ambiguous"):
        RUNNER.resolve_and_materialize(
            page_layout=_layout(duplicate_candidate=True),
            variant_a_page=_variant_a(),
            contract=_table_contract(),
            page_number=1,
            axis_registry={},
        )


def test_zero_or_repeated_breadcrumb_lines_fail_closed() -> None:
    missing = _layout()
    missing["line_inventory"][0]["text"] = "Different"
    with pytest.raises(RUNNER.G596Error, match="g596_breadcrumb_line_not_found"):
        RUNNER.resolve_and_materialize(
            page_layout=missing,
            variant_a_page=_variant_a(),
            contract=_table_contract(),
            page_number=1,
            axis_registry={},
        )

    repeated = _layout()
    repeated["line_inventory"].insert(1, {"text": "Section", "bbox": [0.0, 6.0, 30.0, 9.0]})
    with pytest.raises(RUNNER.G596Error, match="g596_breadcrumb_line_ambiguous"):
        RUNNER.resolve_and_materialize(
            page_layout=repeated,
            variant_a_page=_variant_a(),
            contract=_table_contract(),
            page_number=1,
            axis_registry={},
        )


def test_research_harness_uses_maintained_factories_and_has_no_page_rules() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    evidence = RUNNER._complexity_evidence()

    assert "PdfTextLayerParserFactory().create" in source
    assert "PdfGridExperimentProviderFactory(" in source
    assert "PdfPlumberLayoutAdapter(" not in source
    assert evidence["document_specific_code_branches"] == 0
    assert evidence["body_value_heuristic_rules"] == 0
    assert evidence["production_owner_changes"] == 0
