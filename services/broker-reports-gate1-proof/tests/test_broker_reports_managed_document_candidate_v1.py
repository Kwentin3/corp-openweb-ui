from __future__ import annotations

import copy
from collections.abc import Iterable

import pytest

from broker_reports_gate1.ordinary_trade_qualified_mappings import (
    OrdinaryTradeQualifiedMappingAuthorityFactory,
)
from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    MANAGED_DOCUMENT_CANDIDATE_SCHEMA_VERSION,
    OrdinaryTradeSemanticMappingFactory,
)
from tests.test_broker_reports_logical_row_table_recovery import (
    _page_candidate_refs,
    _pdf_bytes,
)
from tests.test_broker_reports_managed_canonical_projection import (
    _canonical_from_handoff,
    _canonical_handoff,
)
from tests.test_broker_reports_managed_case_mapping_v4 import _model_decision
from tests.test_broker_reports_managed_case_qualification_v1 import (
    USER_SCOPE_SHA256,
    _side_decisions,
    _understandings,
)
from tests.test_broker_reports_managed_header_view import (
    _reseal_canonical_root,
)
from tests.test_broker_reports_managed_pdf_document_v2 import (
    _managed_full_source,
)
from tests.test_broker_reports_pdf_document_visual_adjudication import (
    _visual_table,
)


def _page(*, title: str, first_date: str, second_date: str) -> dict:
    x_positions = (10, 70, 110, 150, 190, 230, 270)
    x_boundaries = (7, 67, 107, 147, 187, 227, 267, 319)
    parent_labels = ("Trade", "Settle", "Oper", "Qty", "Unit", "Curr", "Gross")
    leaf_labels = ("Date", "Date", "Side", "Qty", "Price", "Code", "Amount")
    first = (first_date, "AAA", "BUY", "10", "100", "RUB", "1000")
    second = (second_date, "BBB", "BUY", "20", "200", "RUB", "4000")
    return {
        "texts": [
            (10, 96, title),
            *[
                (x, 72, literal)
                for x, literal in zip(x_positions, parent_labels, strict=True)
            ],
            *[
                (x, 55, literal)
                for x, literal in zip(x_positions, leaf_labels, strict=True)
            ],
            *[
                (x, 38, literal)
                for x, literal in zip(x_positions, first, strict=True)
            ],
            *[
                (x, 22, literal)
                for x, literal in zip(x_positions, second, strict=True)
            ],
        ],
        "vectors": [
            *[f"7 {y} m 319 {y} l S" for y in (15, 30, 46, 63, 82)],
            *[f"{x} 15 m {x} 82 l S" for x in x_boundaries],
        ],
    }


def _two_table_inputs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    incomplete_second: bool = False,
) -> tuple[dict, dict, list[dict]]:
    pdf_bytes = _pdf_bytes(
        [
            _page(
                title="First trades",
                first_date="15.01.2025",
                second_date="16.01.2025",
            ),
            _page(
                title="Second trades",
                first_date="17.01.2025",
                second_date="18.01.2025",
            ),
        ]
    )
    source_ref = "private_pdf_managed_document_atomicity"
    payload = _managed_full_source(
        pdf_bytes,
        source_artifact_ref=source_ref,
    ).payloads[0]
    projection = payload["pdf_text_layer_projection"]
    pages = []
    for page_number in (1, 2):
        refs = _page_candidate_refs(payload, page_number)
        assert len(refs) == 28
        page_ref = next(
            item["page_ref"]
            for item in projection["page_inventory"]
            if item["page_number"] == page_number
        )
        title_refs = [
            item["word_ref"]
            for item in projection["word_inventory"]
            if item["page_ref"] == page_ref and item["word_ref"] not in refs
        ]
        pages.append(
            {
                "tables": [
                    _visual_table(
                        payload,
                        page_number=page_number,
                        title_refs=title_refs,
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
        observations={"pages": pages},
    )
    canonical = _canonical_from_handoff(handoff, source_ref=source_ref)
    tables = sorted(
        [node for node in canonical["nodes"] if node["node_type"] == "TABLE"],
        key=lambda item: item["content"]["title"],
    )
    assert [item["content"]["title"] for item in tables] == [
        "First trades",
        "Second trades",
    ]
    binding = {
        "document_id": "document_managed_document_atomicity",
        "canonical_version_id": "canonical_managed_document_atomicity",
        "canonical_root_sha256": canonical["canonical_root_hash"],
        "source_artifact_ref": canonical["source"]["source_artifact_ref"],
        "source_sha256": canonical["source"]["source_sha256"],
    }
    if incomplete_second:
        table = tables[1]
        sequence = table["content"]["metadata"]["managed_row_sequence"]
        row_number = next(
            index
            for index, item in enumerate(sequence, start=1)
            if item["role"] == "DATA"
        )
        cell = next(
            item
            for item in table["content"]["cells"]
            if item["row"] == row_number and item["column"] == 2
        )
        cell["value"] = ""
        cell["raw_value"] = ""
        cell["displayed_value"] = ""
        sequence[row_number - 1]["entry_texts"][1] = ""
        binding = _reseal_canonical_root(canonical, binding)

    return canonical, binding, _qualified_table_cases(canonical, binding)


def _qualified_table_cases(canonical: dict, binding: dict) -> list[dict]:
    authority = OrdinaryTradeQualifiedMappingAuthorityFactory.create()
    tables = sorted(
        [node for node in canonical["nodes"] if node["node_type"] == "TABLE"],
        key=lambda item: item["node_id"],
    )
    table_cases = []
    for table in tables:
        _, receipt = authority.qualify_managed_header_case_mapping(
            canonical=canonical,
            canonical_binding=binding,
            table_node_id=table["node_id"],
            model_mapping_decision=_model_decision(),
            user_scope_sha256=USER_SCOPE_SHA256,
            model_side_normalization_decisions=_side_decisions(),
            confirmed_understandings=_understandings(),
        )
        table_cases.append(
            {
                "table_node_id": table["node_id"],
                "model_mapping_decision": _model_decision(),
                "model_side_normalization_decisions": _side_decisions(),
                "confirmed_understandings": _understandings(),
                "receipt": receipt,
            }
        )
    return table_cases


def _compile(
    canonical: dict,
    binding: dict,
    table_cases: Iterable[dict],
    *,
    user_scope_sha256: str = USER_SCOPE_SHA256,
) -> dict:
    return OrdinaryTradeSemanticMappingFactory.create().compile_managed_document_candidate(
        canonical=canonical,
        canonical_binding=binding,
        user_scope_sha256=user_scope_sha256,
        table_cases=table_cases,
    )


def _recursive_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            key
            for nested in value.values()
            for key in _recursive_keys(nested)
        }
    if isinstance(value, list):
        return {
            key for nested in value for key in _recursive_keys(nested)
        }
    return set()


def test_two_exact_tables_form_one_inactive_atomic_document_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical, binding, table_cases = _two_table_inputs(monkeypatch)

    result = _compile(canonical, binding, list(reversed(table_cases)))
    repeated = _compile(canonical, binding, table_cases)

    assert result == repeated
    assert result["schema_version"] == MANAGED_DOCUMENT_CANDIDATE_SCHEMA_VERSION
    assert result["document_candidate_status"] == "CANDIDATE_COMPLETE"
    assert result["runtime_activation"] is False
    assert result["publication_authorized"] is False
    assert result["global_reuse"] is False
    assert result["document_completeness_asserted"] is False
    assert result["canonical_binding"] == binding
    assert len(result["table_inventory"]) == 2
    assert [item["terminal"] for item in result["table_outcomes"]] == [
        "COMPILED_COMPLETE",
        "COMPILED_COMPLETE",
    ]
    assert result["blockers"] == []
    assert len(result["document_record_candidates"]) == 4
    assert len(
        {
            item["record_candidate_id"]
            for item in result["document_record_candidates"]
        }
    ) == 4
    row_refs = {
        row["row_compilation_id"]
        for outcome in result["table_outcomes"]
        for row in outcome["row_compilations"]
    }
    assert {
        item["source_row_compilation_ref"]
        for item in result["document_record_candidates"]
    } == row_refs
    assert {"facts", "runtime_records"}.isdisjoint(result)
    assert all("record_candidates" not in item for item in result["table_outcomes"])


def test_one_partial_table_blocks_all_document_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical, binding, table_cases = _two_table_inputs(
        monkeypatch,
        incomplete_second=True,
    )

    result = _compile(canonical, binding, table_cases)

    assert result["document_candidate_status"] == "BLOCKED"
    assert result["document_record_candidates"] == []
    assert [item["terminal"] for item in result["table_outcomes"]] == [
        "COMPILED_COMPLETE",
        "RELEVANT_PARTIAL",
    ]
    assert result["blockers"] == [
        {
            "table_node_id": result["table_outcomes"][1]["table_node_id"],
            "reason_code": "TABLE_RELEVANT_PARTIAL",
        }
    ]
    assert result["table_outcomes"][1]["relevant_unmapped"]


def test_missing_table_is_inspectable_unclassified_blocker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical, binding, table_cases = _two_table_inputs(monkeypatch)

    result = _compile(canonical, binding, table_cases[:1])

    assert result["document_candidate_status"] == "BLOCKED"
    assert result["document_record_candidates"] == []
    assert [item["terminal"] for item in result["table_outcomes"]].count(
        "UNCLASSIFIED"
    ) == 1
    assert result["blockers"][0]["reason_code"] == "TABLE_CASE_UNCLASSIFIED"
    assert result["table_outcomes"][1]["managed_header_view_sha256"]


def test_duplicate_or_foreign_table_receipt_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical, binding, table_cases = _two_table_inputs(monkeypatch)

    with pytest.raises(RuntimeError) as exc:
        _compile(canonical, binding, [table_cases[0], copy.deepcopy(table_cases[0])])
    assert str(exc.value) == "ordinary_trade_managed_document_table_case_duplicate"

    unknown_table = copy.deepcopy(table_cases)
    unknown_table[0]["table_node_id"] = "foreign_table_node"
    with pytest.raises(RuntimeError) as exc:
        _compile(canonical, binding, unknown_table)
    assert str(exc.value) == "ordinary_trade_managed_document_table_case_foreign"

    foreign = copy.deepcopy(table_cases)
    foreign[0]["receipt"] = copy.deepcopy(table_cases[1]["receipt"])
    with pytest.raises(RuntimeError) as exc:
        _compile(canonical, binding, foreign)
    assert str(exc.value) == (
        "ordinary_trade_managed_case_qualification_receipt_invalid"
    )

    for forbidden in (
        "compiled_case",
        "ledger",
        "safe_auxiliary",
        "unsupported",
        "ambiguity",
    ):
        injected = copy.deepcopy(table_cases)
        injected[0][forbidden] = {}
        with pytest.raises(RuntimeError) as exc:
            _compile(canonical, binding, injected)
        assert str(exc.value) == (
            "ordinary_trade_managed_document_table_case_invalid"
        )


def test_stateful_case_iterator_cannot_mix_mutated_canonical_or_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical, binding, table_cases = _two_table_inputs(monkeypatch)
    frozen_binding = copy.deepcopy(binding)

    def mutating_cases():
        yield table_cases[0]
        canonical["nodes"].clear()
        binding["canonical_root_sha256"] = "0" * 64
        binding["source_artifact_ref"] = "mutated_during_iteration"
        yield table_cases[1]

    result = _compile(canonical, binding, mutating_cases())

    assert result["document_candidate_status"] == "CANDIDATE_COMPLETE"
    assert len(result["table_inventory"]) == 2
    assert result["canonical_binding"] == frozen_binding
    assert canonical["nodes"] == []
    assert binding != frozen_binding


def test_scope_binding_and_same_shape_canonical_replay_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical, binding, table_cases = _two_table_inputs(monkeypatch)
    baseline = _compile(canonical, binding, table_cases)

    with pytest.raises(RuntimeError) as exc:
        _compile(
            canonical,
            binding,
            table_cases,
            user_scope_sha256="f" * 64,
        )
    assert str(exc.value) == (
        "ordinary_trade_managed_case_qualification_receipt_invalid"
    )

    stale_binding = copy.deepcopy(binding)
    stale_binding["canonical_root_sha256"] = "0" * 64
    with pytest.raises(RuntimeError) as exc:
        _compile(canonical, stale_binding, table_cases)
    assert str(exc.value) == "ordinary_trade_canonical_binding_invalid"

    resealed = copy.deepcopy(canonical)
    resealed["containers"][0].setdefault("metadata", {})[
        "document_candidate_test_variant"
    ] = "same_shape_foreign"
    resealed_binding = _reseal_canonical_root(resealed, binding)
    assert resealed["canonical_root_hash"] != canonical["canonical_root_hash"]

    with pytest.raises(RuntimeError) as exc:
        _compile(resealed, resealed_binding, table_cases)
    assert str(exc.value) == (
        "ordinary_trade_managed_case_qualification_receipt_invalid"
    )

    fresh_cases = _qualified_table_cases(resealed, resealed_binding)
    fresh = _compile(resealed, resealed_binding, fresh_cases)
    assert fresh["document_candidate_status"] == "CANDIDATE_COMPLETE"
    assert fresh["document_candidate_sha256"] != baseline[
        "document_candidate_sha256"
    ]


def test_document_candidate_contains_no_publication_material_recursively(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical, binding, table_cases = _two_table_inputs(monkeypatch)

    result = _compile(canonical, binding, table_cases)

    assert {
        "facts",
        "runtime_records",
        "safe_auxiliary",
        "publication_artifact",
        "publication_artifacts",
        "publication_receipt",
        "published_facts",
    }.isdisjoint(_recursive_keys(result))
