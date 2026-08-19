from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SERVICE_ROOT / "scripts" / "local_native_table_engine_g597.py"
MANIFEST_PATH = (
    SERVICE_ROOT
    / "benchmarks"
    / "table_layout_native_engine_g597"
    / "manifest.json"
)


def _load_runner():
    sys.path.insert(0, str(SERVICE_ROOT))
    spec = importlib.util.spec_from_file_location("g597_runner", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _contract(*, columns: int = 2, hints: bool = True) -> dict:
    return {
        "tables": [
            {
                "local_name": "visual_table",
                "start_hints": {
                    "anchor_tokens": ["Section"],
                    "table_ordinal_after_anchor": 1,
                },
                "end_hints": {"boundary": "end_of_page", "anchor_tokens": []},
                "structure": {
                    "columns": columns,
                    "header_rows": 1 if hints else 0,
                    "continuation": not hints,
                    "body_row_pattern": "repeated",
                    "wrapped_rows": "unknown",
                    "subtotal_rows": "unknown",
                },
                "header_cell_token_hints": (
                    [{"tokens": [f"Header{chr(65 + index)}"]} for index in range(columns)]
                    if hints
                    else []
                ),
            }
        ]
    }


def test_manifest_freezes_existing_engine_development_and_unseen_holdout() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["frozen"] is True
    assert manifest["candidate"] == {
        "engine": "pdfplumber",
        "version": "0.11.10",
        "selection_reason": "already_pinned_and_used_by_gate2_pdf_layout_owner",
        "adapter_policy": {
            "source_region": "resolved_engine_neutral_breadcrumb_region",
            "vertical_axis": "resolved_engine_neutral_visual_column_boundaries",
            "horizontal_structure": "native_source_vector_lines",
            "engine_strings_are_source_authority": False,
        },
    }
    assert manifest["development"]["g596_cases"] == [
        "development_01",
        "development_02",
        "development_03",
        "development_04",
        "development_05",
        "known_good_01",
        "non_table_01",
    ]
    assert manifest["unseen_holdout"]["page"] not in {23, 24, 25, 26, 27, 28, 64}
    assert manifest["unseen_holdout"]["attempts"] == 1
    assert manifest["unseen_holdout"]["post_open_tuning"] is False
    assert manifest["scope"]["new_dependency"] is False
    assert manifest["scope"]["production_activation"] is False


def test_layout_contract_rejects_vendor_api_body_values_and_numeric_hints() -> None:
    runner = _load_runner()
    valid = _contract()
    runner._validate_layout_contract(valid)

    vendor = _contract()
    vendor["tables"][0]["vertical_strategy"] = "explicit"
    with pytest.raises(runner.G597Error, match="g597_contract_domain_leakage"):
        runner._validate_layout_contract(vendor)

    body = _contract()
    body["tables"][0]["body_values"] = ["forbidden"]
    with pytest.raises(runner.G597Error, match="g597_contract_domain_leakage"):
        runner._validate_layout_contract(body)

    numeric = _contract()
    numeric["tables"][0]["start_hints"]["anchor_tokens"] = ["2026"]
    with pytest.raises(runner.G597Error, match="g597_hint_token_invalid"):
        runner._validate_layout_contract(numeric)


def test_pdfplumber_adapter_owns_vendor_configuration_and_returns_geometry() -> None:
    runner = _load_runner()

    class FakePage:
        def crop(self, bbox):
            assert bbox == (0.0, 0.0, 20.0, 20.0)
            return self

        def find_tables(self, *, table_settings):
            assert table_settings == {
                "vertical_strategy": "explicit",
                "explicit_vertical_lines": [0.0, 10.0, 20.0],
                "horizontal_strategy": "lines",
            }
            return [
                SimpleNamespace(
                    bbox=(0.0, 0.0, 20.0, 20.0),
                    columns=[object(), object()],
                    rows=[
                        SimpleNamespace(cells=[(0, 0, 10, 10), (10, 0, 20, 10)]),
                        SimpleNamespace(cells=[(0, 10, 10, 20), (10, 10, 20, 20)]),
                    ],
                )
            ]

    adapter = object.__new__(runner.PdfplumberTableExtractorAdapter)
    adapter._pdf = SimpleNamespace(pages=[FakePage()])
    geometry = adapter.extract_geometry(
        page_number=1,
        source_region=[0.0, 0.0, 20.0, 20.0],
        visual_column_boundaries=[0.0, 10.0, 20.0],
        expected_columns=2,
    )

    assert geometry["row_count"] == 2
    assert geometry["column_count"] == 2
    assert geometry["engine_strings_used"] == 0
    assert geometry["configuration"] == {
        "vertical_strategy": "explicit",
        "explicit_vertical_lines": [0.0, 10.0, 20.0],
        "horizontal_strategy": "lines",
    }


def test_native_cells_bind_each_verified_parser_word_and_ref_exactly_once() -> None:
    runner = _load_runner()
    page_layout = {
        "line_inventory": [
            {"parser_ordinal": 1, "word_parser_ordinals": [1, 2]},
            {"parser_ordinal": 2, "word_parser_ordinals": [3]},
        ]
    }
    words = [
        {"parser_ordinal": 1, "text": "A", "bbox": [1, 1, 2, 2]},
        {"parser_ordinal": 2, "text": "B", "bbox": [11, 1, 12, 2]},
        {"parser_ordinal": 3, "text": "C", "bbox": [1, 11, 2, 12]},
    ]
    bindings = {
        1: {"source_word_ref": "pdfword_1", "source_value_ref": "v1", "frozen_literal": "A"},
        2: {"source_word_ref": "pdfword_2", "source_value_ref": "v2", "frozen_literal": "B"},
        3: {"source_word_ref": "pdfword_3", "source_value_ref": "v3", "frozen_literal": "C"},
    }

    rows, assigned = runner._bind_source_words(
        page_layout=page_layout,
        candidate_words=words,
        native_rows=[
            [[0, 0, 10, 10], [10, 0, 20, 10]],
            [[0, 10, 10, 20], [10, 10, 20, 20]],
        ],
        bindings=bindings,
    )

    assert assigned == {1, 2, 3}
    assert [cell["literal"] for row in rows for cell in row["cells"]] == [
        "A",
        "B",
        "C",
        "",
    ]
    assert [
        ref
        for row in rows
        for cell in row["cells"]
        for ref in cell["source_value_refs"]
    ] == ["v1", "v2", "v3"]


def test_headerless_independent_contract_fails_before_table_candidate_search() -> None:
    runner = _load_runner()
    contract = _contract(hints=False)["tables"][0]
    page_layout = {
        "height": 100,
        "line_inventory": [
            {"text": "Section", "bbox": [0, 1, 20, 5]},
        ],
        "word_inventory": [],
        "table_candidate_inventory": [
            {
                "bbox": [0, 10, 100, 90],
                "columns_total": 2,
                "contributing_word_parser_ordinals": [],
                "cell_inventory": [],
            }
        ],
    }

    with pytest.raises(runner.G597Error, match="g597_layout_axis_not_resolvable"):
        runner._resolve_contract(
            page_layout=page_layout,
            contract=contract,
            axis_registry={},
        )


def test_development_terminal_requires_every_frozen_observable() -> None:
    runner = _load_runner()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    aggregate = dict(manifest["development"]["acceptance"])
    aggregate["engine_strings_used"] = 0

    assert runner._development_terminal(aggregate, manifest) == runner.DEVELOPMENT_PROVEN
    aggregate["native_mapping_matches_g596"] -= 1
    assert runner._development_terminal(aggregate, manifest) == runner.DEVELOPMENT_FAILED


def test_research_harness_uses_public_factory_and_has_no_page_rules() -> None:
    runner = _load_runner()
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    complexity = runner._complexity_evidence()

    assert "PdfTextLayerParserFactory().create" in source
    assert "NormalizedTableProjectionFactory" not in source
    assert complexity["document_specific_code_branches"] == 0
    assert complexity["body_value_heuristic_rules"] == 0
    assert complexity["financial_semantic_rules"] == 0
    assert complexity["production_owner_changes"] == 0
    assert complexity["new_dependencies"] == 0
    assert complexity["engine_specific_adapter_functions"] == 1
