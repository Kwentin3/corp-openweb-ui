from __future__ import annotations

import copy
import hashlib
import json

import pytest

from broker_reports_gate1 import canonical_artifact as canonical_artifact_module
from broker_reports_gate1.canonical_artifact import validate_canonical_artifact
from broker_reports_gate1.ordinary_trade_semantic_compiler import (
    ORDINARY_TRADE_MANAGED_HEADER_VIEW_SCHEMA_VERSION,
    OrdinaryTradeSemanticCompilerError,
    ordinary_trade_canonical_managed_header_view,
    ordinary_trade_canonical_table_rows,
)
from tests.test_broker_reports_logical_row_table_recovery import (
    _source_bound_multirow_header_case,
)
from tests.test_broker_reports_managed_canonical_projection import (
    _canonical_from_handoff,
    _canonical_handoff,
)
from tests.test_broker_reports_managed_pdf_document_v2 import _managed_full_source
from tests.test_broker_reports_pdf_document_visual_adjudication import (
    _page_candidate_refs,
    _visual_table,
)


def _multirow_canonical(monkeypatch: pytest.MonkeyPatch) -> tuple[dict, dict, dict]:
    pdf_bytes, _, _ = _source_bound_multirow_header_case(second_leaf_header="Date")
    source_ref = "private_pdf_managed_header_view"
    payload = _managed_full_source(
        pdf_bytes,
        source_artifact_ref=source_ref,
    ).payloads[0]
    pages = []
    for page_number in (1, 2):
        refs = _page_candidate_refs(payload, page_number)
        pages.append(
            {
                "tables": [
                    _visual_table(
                        payload,
                        page_number=page_number,
                        title_refs=[],
                        header_groups=[refs[:2], refs[2:4]],
                        body_refs=refs[4:],
                    )
                ]
            }
        )
    handoff = _canonical_handoff(
        monkeypatch,
        pdf_bytes=pdf_bytes,
        source_ref=source_ref,
        observations={"pages": pages},
    )
    canonical = _canonical_from_handoff(handoff, source_ref=source_ref)
    table = next(node for node in canonical["nodes"] if node["node_type"] == "TABLE")
    binding = {
        "document_id": "document_managed_header_view",
        "canonical_version_id": "canonical_managed_header_view",
        "canonical_root_sha256": canonical["canonical_root_hash"],
        "source_artifact_ref": canonical["source"]["source_artifact_ref"],
        "source_sha256": canonical["source"]["source_sha256"],
    }
    return canonical, table, binding


def _view(canonical: dict, table: dict, binding: dict) -> dict:
    return ordinary_trade_canonical_managed_header_view(
        canonical=canonical,
        canonical_binding=binding,
        table_node_id=table["node_id"],
    )


def _entry_record(canonical: dict, cell: dict) -> dict:
    return next(
        item
        for item in canonical["provenance"]
        if item["provenance_id"] == cell["source_refs"][0]
    )


def _reseal_entry_locator(canonical: dict, cell: dict, mutator) -> None:
    record = _entry_record(canonical, cell)
    old_ref = record["provenance_id"]
    mutator(record["source_locator"])
    new_ref = "prov_" + hashlib.sha256(
        json.dumps(
            [canonical["source"]["source_sha256"], record["source_locator"]],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:24]
    record["provenance_id"] = new_ref
    assert cell["source_refs"] == [old_ref]
    cell["source_refs"] = [new_ref]


def _reseal_canonical_root(canonical: dict, binding: dict) -> dict:
    source = canonical["source"]
    canonical["canonical_root_hash"] = canonical_artifact_module._sha256(
        canonical_artifact_module._root_hash_material(
            normalizer_version=canonical["normalizer_version"],
            source_format=source["source_format"],
            source_sha256=source["source_sha256"],
            containers=canonical["containers"],
            nodes=canonical["nodes"],
            provenance=canonical["provenance"],
            issues=canonical["issues"],
        )
    )
    updated = copy.deepcopy(binding)
    updated["canonical_root_sha256"] = canonical["canonical_root_hash"]
    return updated


def test_multirow_header_view_keeps_exact_primary_paths_and_filters_continuation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical, table, binding = _multirow_canonical(monkeypatch)

    view = _view(canonical, table, binding)

    assert view["schema_version"] == ORDINARY_TRADE_MANAGED_HEADER_VIEW_SCHEMA_VERSION
    assert view["representation_only"] is True
    assert view["consumer_eligible"] is False
    assert view["managed_binding"] == {
        "source_representation_owner": "managed_document_v2",
        "managed_whole_table_projection_id": table["content"]["metadata"][
            "managed_whole_table_projection_id"
        ],
        "managed_document_id": table["content"]["metadata"]["managed_document_id"],
        "managed_document_integrity_sha256": table["content"]["metadata"][
            "managed_document_integrity_sha256"
        ],
        "managed_table_id": table["content"]["metadata"]["managed_table_id"],
    }
    assert [
        [item["literal"] for item in column["primary_header_path"]]
        for column in view["columns"]
    ] == [["Trade", "Date"], ["Settlement", "Date"]]
    assert all(
        len(column["filtered_entry_refs"]) == 2
        for column in view["continuation_accounting"]["columns"]
    )
    assert len(view["continuation_accounting"]["filtered_entry_refs"]) == 4
    assert all(item["row_id"] for item in view["primary_header_rows"])
    assert all(item["row_id"] for item in view["continuation_accounting"]["rows"])
    assert all(
        item["row_id"]
        and len(item["source_refs"]) == 1
        and item["canonical_provenance_ref"] == item["source_refs"][0]
        for column in view["columns"]
        for item in column["primary_header_path"]
    )
    hash_material = copy.deepcopy(view)
    actual_hash = hash_material.pop("header_view_sha256")
    assert actual_hash == hashlib.sha256(
        json.dumps(
            hash_material,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    hash_material["continuation_accounting"]["filtered_entry_refs"].pop()
    assert actual_hash != hashlib.sha256(
        json.dumps(
            hash_material,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    assert view["header_view_sha256"] == _view(canonical, table, binding)[
        "header_view_sha256"
    ]
    with pytest.raises(OrdinaryTradeSemanticCompilerError) as exc:
        ordinary_trade_canonical_table_rows(
            table,
            provenance=canonical["provenance"],
            source=canonical["source"],
        )
    assert exc.value.code == "ordinary_trade_canonical_managed_header_invalid"


def test_header_view_fails_closed_on_old_noncontiguous_or_invalid_owner_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical, table, binding = _multirow_canonical(monkeypatch)
    base = copy.deepcopy(canonical)
    table_id = table["node_id"]

    cases: list[tuple[dict, str, bool]] = []
    old = copy.deepcopy(base)
    old_table = next(node for node in old["nodes"] if node["node_id"] == table_id)
    old_cell = old_table["content"]["cells"][0]
    _reseal_entry_locator(
        old,
        old_cell,
        lambda locator: [
            locator.pop(key)
            for key in (
                "managed_entry_binding_schema_version",
                "managed_column_binding_status",
                "managed_logical_column_id",
                "managed_covers_logical_column_ids",
            )
        ],
    )
    cases.append(
        (old, "ordinary_trade_canonical_managed_entry_binding_invalid", True)
    )

    foreign = copy.deepcopy(base)
    foreign_table = next(
        node for node in foreign["nodes"] if node["node_id"] == table_id
    )
    _reseal_entry_locator(
        foreign,
        foreign_table["content"]["cells"][0],
        lambda locator: locator.update({"managed_logical_column_id": "column_foreign"}),
    )
    cases.append(
        (foreign, "ordinary_trade_canonical_managed_entry_binding_invalid", True)
    )

    empty = copy.deepcopy(base)
    empty_table = next(node for node in empty["nodes"] if node["node_id"] == table_id)
    empty_table["content"]["metadata"]["logical_columns"][0]["header_path"] = []
    cases.append((empty, "ordinary_trade_canonical_managed_header_path_invalid", True))

    missing_path = copy.deepcopy(base)
    missing_path_table = next(
        node for node in missing_path["nodes"] if node["node_id"] == table_id
    )
    missing_path_table["content"]["metadata"]["logical_columns"][0].pop(
        "header_path"
    )
    cases.append(
        (
            missing_path,
            "ordinary_trade_canonical_managed_header_path_invalid",
            True,
        )
    )

    missing_provenance = copy.deepcopy(base)
    missing_provenance_table = next(
        node for node in missing_provenance["nodes"] if node["node_id"] == table_id
    )
    missing_ref = missing_provenance_table["content"]["cells"][0]["source_refs"][0]
    missing_provenance["provenance"] = [
        record
        for record in missing_provenance["provenance"]
        if record["provenance_id"] != missing_ref
    ]
    cases.append(
        (
            missing_provenance,
            "ordinary_trade_canonical_managed_header_view_canonical_invalid",
            False,
        )
    )

    uncovered = copy.deepcopy(base)
    uncovered_table = next(
        node for node in uncovered["nodes"] if node["node_id"] == table_id
    )
    uncovered_cell = uncovered_table["content"]["cells"][0]
    uncovered_record = _entry_record(uncovered, uncovered_cell)
    uncovered_entry_id = uncovered_record["source_locator"]["managed_entry_id"]
    _reseal_entry_locator(
        uncovered,
        uncovered_cell,
        lambda locator: locator.update(
            {
                "managed_logical_column_id": None,
                "managed_covers_logical_column_ids": [],
                "managed_column_binding_status": "NOT_APPLICABLE",
            }
        ),
    )
    first_column = uncovered_table["content"]["metadata"]["logical_columns"][0]
    first_column["header_path"].remove(uncovered_entry_id)
    cases.append(
        (
            uncovered,
            "ordinary_trade_canonical_managed_continuation_header_invalid",
            True,
        )
    )

    swapped = copy.deepcopy(base)
    swapped_table = next(
        node for node in swapped["nodes"] if node["node_id"] == table_id
    )
    left, right = swapped_table["content"]["metadata"]["logical_columns"]
    left["header_path"], right["header_path"] = right["header_path"], left["header_path"]
    cases.append(
        (swapped, "ordinary_trade_canonical_managed_header_path_invalid", True)
    )

    noncontiguous = copy.deepcopy(base)
    gap_table = next(
        node for node in noncontiguous["nodes"] if node["node_id"] == table_id
    )
    for cell in gap_table["content"]["cells"]:
        if cell["row"] == 2:
            cell["row"] = 3
        elif cell["row"] == 3:
            cell["row"] = 2
    sequence = gap_table["content"]["metadata"]["managed_row_sequence"]
    sequence[1], sequence[2] = sequence[2], sequence[1]
    for ordinal, item in enumerate(sequence):
        item["ordinal"] = ordinal
    cases.append(
        (noncontiguous, "ordinary_trade_canonical_managed_header_invalid", True)
    )

    for candidate, expected_code, canonical_should_pass in cases:
        candidate_table = next(
            node for node in candidate["nodes"] if node["node_id"] == table_id
        )
        candidate_binding = _reseal_canonical_root(candidate, binding)
        assert validate_canonical_artifact(candidate)["passed"] is canonical_should_pass
        with pytest.raises(OrdinaryTradeSemanticCompilerError) as exc:
            _view(candidate, candidate_table, candidate_binding)
        assert exc.value.code == expected_code


def test_data_row_cannot_be_relabelled_as_incomplete_continuation_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical, table, binding = _multirow_canonical(monkeypatch)
    sequence = table["content"]["metadata"]["managed_row_sequence"]
    row_number = next(
        index
        for index, item in enumerate(sequence, start=1)
        if item["role"] == "DATA"
    )
    sequence[row_number - 1]["role"] = "CONTINUATION_HEADER"
    for cell in table["content"]["cells"]:
        if cell["row"] == row_number:
            _reseal_entry_locator(
                canonical,
                cell,
                lambda locator: locator.update(
                    {"managed_row_role": "CONTINUATION_HEADER"}
                ),
            )
    candidate_binding = _reseal_canonical_root(canonical, binding)
    assert validate_canonical_artifact(canonical)["passed"] is True

    with pytest.raises(OrdinaryTradeSemanticCompilerError) as exc:
        _view(canonical, table, candidate_binding)
    assert (
        exc.value.code
        == "ordinary_trade_canonical_managed_continuation_header_invalid"
    )


def test_changed_continuation_literal_cannot_be_filtered_as_exact_repeat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical, table, binding = _multirow_canonical(monkeypatch)
    sequence = table["content"]["metadata"]["managed_row_sequence"]
    row_number = next(
        index
        for index, item in enumerate(sequence, start=1)
        if item["role"] == "CONTINUATION_HEADER"
    )
    cells = sorted(
        (
            cell
            for cell in table["content"]["cells"]
            if cell["row"] == row_number
        ),
        key=lambda cell: cell["column"],
    )
    changed = cells[0]["displayed_value"] + " changed"
    cells[0]["value"] = changed
    cells[0]["raw_value"] = changed
    cells[0]["displayed_value"] = changed
    sequence[row_number - 1]["entry_texts"][0] = changed
    candidate_binding = _reseal_canonical_root(canonical, binding)
    assert validate_canonical_artifact(canonical)["passed"] is True

    with pytest.raises(OrdinaryTradeSemanticCompilerError) as exc:
        _view(canonical, table, candidate_binding)
    assert (
        exc.value.code
        == "ordinary_trade_canonical_managed_continuation_header_invalid"
    )
