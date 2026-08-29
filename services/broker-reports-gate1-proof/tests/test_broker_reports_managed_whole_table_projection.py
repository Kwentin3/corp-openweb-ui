from __future__ import annotations

import copy
from functools import lru_cache

from pytest import MonkeyPatch

from broker_reports_gate1.managed_document_contracts import (
    compute_document_integrity_sha256,
)
from broker_reports_gate1.managed_document_contracts_v2 import (
    ManagedDocumentV2,
    _source_unit_ledger_inventory,
)
from broker_reports_gate1.managed_pdf_document_v2 import (
    ManagedPdfDocumentV2Factory,
)
from broker_reports_gate1.managed_whole_table_projection import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    PROJECTION_SCHEMA_VERSION,
    _project_sealed_adjudicated_managed_document,
)
from tests.test_broker_reports_managed_pdf_document_v2 import (
    _GeminiBoundary,
    _managed_full_source,
    _openwebui_request,
    _route_openwebui_resolver_to_boundary,
    _schema,
    _source_bound_case,
    _two_page_observations,
)
from tests.test_broker_reports_logical_row_table_recovery import (
    _source_bound_table_vectors,
)
from tests.test_broker_reports_pdf_layout_slice2 import _pdf_bytes


@lru_cache(maxsize=1)
def _repeated_header_managed() -> ManagedDocumentV2:
    pdf_bytes, _, _ = _source_bound_case(
        second_header_labels=("Instrument", "Currency")
    )
    source_ref = "private_pdf_whole_table_projection"
    payload = _managed_full_source(
        pdf_bytes,
        source_artifact_ref=source_ref,
    ).payloads[0]
    observations = _two_page_observations(payload, repeated_header=True)
    monkeypatch = MonkeyPatch()
    request = _openwebui_request()
    try:
        with _GeminiBoundary([observations, observations]) as boundary:
            _route_openwebui_resolver_to_boundary(
                monkeypatch,
                request=request,
                boundary=boundary,
            )
            result = (
                ManagedPdfDocumentV2Factory()
                .create_adjudicated_for_openwebui(_schema(), request)
                .build(
                    pdf_bytes,
                    source_artifact_ref=source_ref,
                    task_id="managed_whole_table_projection",
                )
            )
    finally:
        monkeypatch.undo()
    assert result.status == "COMPLETE"
    assert result.managed_document is not None
    return result.managed_document


def _resealed_lookalike(
    mutator,
) -> ManagedDocumentV2:
    payload = copy.deepcopy(_repeated_header_managed().payload)
    mutator(payload)
    payload["integrity_sha256"] = compute_document_integrity_sha256(payload)
    return ManagedDocumentV2(payload=payload)


def _adjudicated_source_bound_result(
    monkeypatch: MonkeyPatch,
    *,
    source_ref: str,
    distinct_second_title: bool = False,
    second_header_labels: tuple[str, str] | None = None,
    second_title: bool = False,
    repeated_header: bool = False,
):
    pdf_bytes, _, _ = _source_bound_case(
        distinct_second_title=distinct_second_title,
        second_header_labels=second_header_labels,
    )
    payload = _managed_full_source(
        pdf_bytes,
        source_artifact_ref=source_ref,
    ).payloads[0]
    observations = _two_page_observations(
        payload,
        second_title=second_title,
        repeated_header=repeated_header,
    )
    request = _openwebui_request()
    with _GeminiBoundary([observations, observations]) as boundary:
        _route_openwebui_resolver_to_boundary(
            monkeypatch,
            request=request,
            boundary=boundary,
        )
        return (
            ManagedPdfDocumentV2Factory()
            .create_adjudicated_for_openwebui(_schema(), request)
            .build(
                pdf_bytes,
                source_artifact_ref=source_ref,
                task_id=source_ref,
            )
        )


def _headerless_pdf_with_paragraph() -> bytes:
    return _pdf_bytes(
        [
            {
                "texts": [
                    (25, 120, "Portfolio note outside grid"),
                    (25, 55, "Item"),
                    (200, 55, "Amount"),
                    (25, 38, "Cash"),
                    (200, 38, "10"),
                    (25, 22, "Bonds"),
                    (200, 22, "20"),
                ],
                "vectors": _source_bound_table_vectors(
                    y0=15,
                    y1=65,
                    horizontal_ys=(15, 30, 46, 65),
                ),
            },
            {
                "texts": [
                    (25, 305, "Funds"),
                    (200, 305, "30"),
                    (25, 288, "Shares"),
                    (200, 288, "40"),
                    (25, 271, "Options"),
                    (200, 271, "50"),
                ],
                "vectors": _source_bound_table_vectors(
                    y0=260,
                    y1=315,
                    horizontal_ys=(260, 279, 296, 315),
                ),
            },
        ]
    )


def _ledger_plan(
    managed: ManagedDocumentV2,
) -> tuple[dict, ...]:
    return tuple(_source_unit_ledger_inventory(managed.payload))


def _tables(managed: ManagedDocumentV2) -> list[dict]:
    return [
        block["content"]
        for block in managed.payload["blocks"]
        if block["block_type"] == "TABLE"
    ]


def _entry_texts(table: dict) -> list[str]:
    return [
        str(entry["text"])
        for row in table["ordered_rows"]
        for entry in row["entries"]
        if entry.get("text") is not None
    ]


def test_private_same_call_projection_preserves_managed_and_exact_ledger() -> None:
    managed = _repeated_header_managed()
    before_bytes = managed.canonical_json_bytes()
    before_integrity = managed.integrity_sha256
    table = next(
        block["content"]
        for block in managed.payload["blocks"]
        if block["block_type"] == "TABLE"
    )

    result = _project_sealed_adjudicated_managed_document(
        managed,
        expected_source_unit_ledger=_ledger_plan(managed),
    )

    assert result.status == "READY"
    assert result.issues == ()
    assert len(result.projections) == 1
    projection = result.projections[0]
    assert projection["schema_version"] == PROJECTION_SCHEMA_VERSION
    assert projection["managed_document_integrity_sha256"] == before_integrity
    assert projection["ordered_rows"] == table["ordered_rows"]
    assert projection["source_parts"] == table["source_parts"]
    assert projection["source_part_refs"] == [
        part["source_part_id"] for part in table["source_parts"]
    ]
    assert projection["covered_source_atom_refs"] == table[
        "covered_source_atom_refs"
    ]
    assert projection["covered_source_word_refs"] == table[
        "covered_source_word_refs"
    ]
    assert projection["covered_source_unit_refs"] == sorted(
        unit["unit_ref"]
        for part in table["source_parts"]
        for unit in part["covered_source_units"]
    )
    second_part = table["source_parts"][1]
    repeated_header = next(
        row
        for row in table["ordered_rows"]
        if row["row_id"] == second_part["first_row_id"]
    )
    assert repeated_header["role"] == "CONTINUATION_HEADER"
    assert repeated_header in projection["ordered_rows"]
    assert projection["continuation_header_row_refs"] == [
        repeated_header["row_id"]
    ]
    assert projection["receipt"]["continuation_headers_collapsed"] is False
    assert managed.canonical_json_bytes() == before_bytes
    assert managed.integrity_sha256 == before_integrity


def test_headerless_continuation_keeps_outside_paragraph_out_of_projection(
    monkeypatch: MonkeyPatch,
) -> None:
    pdf_bytes = _headerless_pdf_with_paragraph()
    source_ref = "private_pdf_whole_table_projection_paragraph"
    payload = _managed_full_source(
        pdf_bytes,
        source_artifact_ref=source_ref,
    ).payloads[0]
    paragraph_word_refs = {
        word["word_ref"]
        for word in payload["pdf_text_layer_projection"]["word_inventory"]
        if word["text"] in {"Portfolio", "note", "outside", "grid"}
    }
    observations = _two_page_observations(payload)
    request = _openwebui_request()

    with _GeminiBoundary([observations, observations]) as boundary:
        _route_openwebui_resolver_to_boundary(
            monkeypatch,
            request=request,
            boundary=boundary,
        )
        result = (
            ManagedPdfDocumentV2Factory()
            .create_adjudicated_for_openwebui(_schema(), request)
            .build(
                pdf_bytes,
                source_artifact_ref=source_ref,
                task_id="managed_whole_table_projection_paragraph",
            )
        )

    assert result.status == "COMPLETE"
    assert result.managed_document is not None
    assert result.safe_diagnostics["whole_table_projection_status"] == "READY"
    assert result.safe_diagnostics["whole_table_projections_total"] == 1
    paragraph_blocks = [
        block
        for block in result.managed_document.payload["blocks"]
        if block["block_type"] == "PARAGRAPH"
    ]
    assert [block["content"]["raw_text"] for block in paragraph_blocks] == [
        "Portfolio note outside grid"
    ]
    assert len(result.whole_table_projections) == 1
    projection = result.whole_table_projections[0]
    assert set(projection["covered_source_word_refs"]).isdisjoint(
        paragraph_word_refs
    )
    assert result.safe_diagnostics["canonical_artifacts_created"] == 0
    assert result.safe_diagnostics["facts_published"] == 0


def test_distinct_titles_keep_similar_tables_independent(
    monkeypatch: MonkeyPatch,
) -> None:
    result = _adjudicated_source_bound_result(
        monkeypatch,
        source_ref="private_pdf_whole_table_projection_distinct_titles",
        distinct_second_title=True,
        second_title=True,
    )
    assert result.status == "COMPLETE"
    assert result.managed_document is not None
    assert result.safe_diagnostics["whole_table_projection_status"] == "READY"
    assert result.safe_diagnostics["whole_table_projections_total"] == 2

    tables = _tables(result.managed_document)
    table_by_id = {table["table_id"]: table for table in tables}
    projections = list(result.whole_table_projections)

    assert len(tables) == 2
    assert {projection["table_id"] for projection in projections} == set(table_by_id)
    seen_units: set[str] = set()
    seen_atoms: set[str] = set()
    seen_words: set[str] = set()
    for projection in projections:
        table = table_by_id[projection["table_id"]]
        units = set(projection["covered_source_unit_refs"])
        atoms = set(projection["covered_source_atom_refs"])
        words = set(projection["covered_source_word_refs"])
        assert projection["ordered_rows"] == table["ordered_rows"]
        assert projection["source_parts"] == table["source_parts"]
        assert projection["covered_source_atom_refs"] == table[
            "covered_source_atom_refs"
        ]
        assert projection["covered_source_word_refs"] == table[
            "covered_source_word_refs"
        ]
        assert not seen_units & units
        assert not seen_atoms & atoms
        assert not seen_words & words
        seen_units |= units
        seen_atoms |= atoms
        seen_words |= words

    title_hits = [
        "Completed position transfers" in _entry_texts(projection)
        for projection in projections
    ]
    assert title_hits.count(True) == 1
    assert result.safe_diagnostics["canonical_artifacts_created"] == 0
    assert result.safe_diagnostics["facts_published"] == 0


def test_partial_or_missing_ledger_is_typed_not_ready() -> None:
    def partial(payload: dict) -> None:
        payload["quality"]["status"] = "PARTIAL"

    def missing_ledger(payload: dict) -> None:
        payload["source"].pop("table_source_unit_coverage")

    for mutator, expected in (
        (partial, "managed_whole_table_projection_document_not_complete"),
        (missing_ledger, "managed_whole_table_projection_ledger_missing"),
    ):
        result = _project_sealed_adjudicated_managed_document(
            _resealed_lookalike(mutator),
            expected_source_unit_ledger=_ledger_plan(_repeated_header_managed()),
        )
        assert result.status == "NOT_READY"
        assert result.projections == ()
        assert result.issues == ({"code": expected},)


def test_checksum_unknown_anchor_and_overlap_fail_closed() -> None:
    checksum_payload = copy.deepcopy(_repeated_header_managed().payload)
    checksum_payload["source"]["checksum_sha256"] = "0" * 64
    checksum = _project_sealed_adjudicated_managed_document(
        ManagedDocumentV2(payload=checksum_payload),
        expected_source_unit_ledger=_ledger_plan(_repeated_header_managed()),
    )
    assert checksum.status == "NOT_READY"
    assert checksum.projections == ()
    assert checksum.issues == (
        {"code": "managed_whole_table_projection_integrity_invalid"},
    )

    def unknown_anchor(payload: dict) -> None:
        table = next(
            block["content"]
            for block in payload["blocks"]
            if block["block_type"] == "TABLE"
        )
        table["ordered_rows"][0]["entries"][0]["source_anchor_ids"] = [
            "anchor_unknown"
        ]

    unknown = _project_sealed_adjudicated_managed_document(
        _resealed_lookalike(unknown_anchor),
        expected_source_unit_ledger=_ledger_plan(_repeated_header_managed()),
    )
    assert unknown.status == "NOT_READY"
    assert unknown.projections == ()
    assert unknown.issues == (
        {"code": "managed_whole_table_projection_source_anchor_unknown"},
    )

    def overlap(payload: dict) -> None:
        table = next(
            block["content"]
            for block in payload["blocks"]
            if block["block_type"] == "TABLE"
        )
        units = [
            unit
            for part in table["source_parts"]
            for unit in part["covered_source_units"]
        ]
        units[1]["selected_source_atom_refs"].append(
            units[0]["selected_source_atom_refs"][0]
        )

    duplicated = _project_sealed_adjudicated_managed_document(
        _resealed_lookalike(overlap),
        expected_source_unit_ledger=_ledger_plan(_repeated_header_managed()),
    )
    assert duplicated.status == "NOT_READY"
    assert duplicated.projections == ()
    assert duplicated.issues == (
        {"code": "managed_whole_table_projection_ledger_plan_mismatch"},
    )


def test_self_consistent_unknown_atom_or_unit_does_not_match_same_call_plan() -> None:
    original = _repeated_header_managed()
    original_plan = _ledger_plan(original)

    def unknown_atom(payload: dict) -> None:
        table = next(
            block["content"]
            for block in payload["blocks"]
            if block["block_type"] == "TABLE"
        )
        part = table["source_parts"][0]
        part["covered_source_units"][0]["selected_source_atom_refs"][0] = (
            "textseg_forged_unknown_atom"
        )
        table["covered_source_atom_refs"] = sorted(
            atom
            for part in table["source_parts"]
            for unit in part["covered_source_units"]
            for atom in unit["selected_source_atom_refs"]
        )
        payload["source"]["table_source_unit_coverage"][
            "covered_source_atom_refs"
        ] = table["covered_source_atom_refs"]

    def unknown_unit(payload: dict) -> None:
        table = next(
            block["content"]
            for block in payload["blocks"]
            if block["block_type"] == "TABLE"
        )
        table["source_parts"][0]["covered_source_units"][0][
            "unit_ref"
        ] = "sourceunit_forged_unknown_unit"
        payload["source"]["table_source_unit_coverage"][
            "covered_source_unit_refs"
        ] = sorted(
            unit["unit_ref"]
            for block in payload["blocks"]
            if block["block_type"] == "TABLE"
            for part in block["content"]["source_parts"]
            for unit in part["covered_source_units"]
        )

    for mutator in (unknown_atom, unknown_unit):
        result = _project_sealed_adjudicated_managed_document(
            _resealed_lookalike(mutator),
            expected_source_unit_ledger=original_plan,
        )
        assert result.status == "NOT_READY"
        assert result.projections == ()
        assert result.issues == (
            {"code": "managed_whole_table_projection_ledger_plan_mismatch"},
        )


def test_inactive_projection_has_no_public_builder_or_neighbor_imports() -> None:
    import broker_reports_gate1.managed_whole_table_projection as module

    source = module.__loader__.get_source(module.__name__)  # type: ignore[attr-defined]
    assert FACTORY_REQUIRED.endswith(
        "_project_sealed_adjudicated_managed_document"
    )
    assert "Callers must not submit" in FORBIDDEN
    assert "FACTORY_REQUIRED" in source
    assert "FORBIDDEN" in source
    assert "class ManagedWholeTableProjectionFactory" not in source
    assert "from .table_projection import" not in source
    assert "from .canonical_artifact import" not in source
    assert "from .gate2_financial" not in source
    assert "openwebui_actions" not in source
