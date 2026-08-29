from __future__ import annotations

import copy

import pytest

from broker_reports_gate1.canonical_artifact import (
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
)
from broker_reports_gate1.logical_row_table_recovery import (
    LogicalRowTableRecoveryResult,
)
from broker_reports_gate1.gate2_model_contracts import Gate2ProviderExecutionMetadata
from broker_reports_gate1.table_scoped_role_research import (
    TableScopedRoleResearchError,
    TableScopedRoleResearchFactory,
)
from broker_reports_gate1.visual_role_context_research import (
    VisualRoleContextResearchFactory,
    enrich_role_request,
)
from scripts.canonical_financial_role_mapping_research import (
    apply_contract,
    build_table_surface,
    compose_request,
    extract_tables,
    validate_response,
)
from scripts.live_table_scoped_financial_role_research import _jsonable


SOURCE_SHA = "a" * 64


def test_live_receipt_serializes_provider_metadata_as_mapping() -> None:
    metadata = Gate2ProviderExecutionMetadata(
        provider_id="provider",
        provider_profile_id="profile",
        provider_profile_revision="revision",
        adapter_id="adapter",
        adapter_version="version",
        requested_model_id="model",
        structured_output_mode="json_schema",
        response_format_type="json_schema",
        response_format_schema_mode="strict",
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
    )

    serialized = _jsonable(metadata)

    assert serialized["schema_version"] == "gate2_provider_execution_metadata_v1"
    assert serialized["input_tokens"] == 10
    assert serialized["output_tokens"] == 5
    assert serialized["total_tokens"] == 15


def _fixture() -> tuple[
    LogicalRowTableRecoveryResult,
    list[dict],
    list[dict],
    dict,
]:
    texts = {
        "w_title": "Trades",
        "w_h1": "Date",
        "w_h2": "Amount",
        "w_d1": "2025-01-01",
        "w_d2": "100",
        "w_other_h": "Reference",
        "w_other_d": "Note",
    }
    words = [
        {
            "word_ref": ref,
            "source_value_ref": f"sv_{ref}",
            "page_ref": "page_1",
            "parser_ordinal": ordinal,
            "text": text,
        }
        for ordinal, (ref, text) in enumerate(texts.items(), start=1)
    ]
    payload = {
        "source_payload_ref": "payload_1",
        "parser_completeness_status": "complete",
        "parser_completeness_reason_codes": [],
        "pdf_text_layer_projection": {
            "page_inventory": [{"page_ref": "page_1", "page_number": 1}],
            "word_inventory": words,
        },
    }
    visual_unit = {
        "unit_ref": "visual_1",
        "document_id": "document_1",
        "parent_payload_ref": "payload_1",
        "normalization_run_id": "run_1",
        "pdf_unit_type": "pdf_visual_page_unit",
        "source_location": {"kind": "pdf_visual_page_render", "page": 1},
        "page_refs": ["page_1"],
    }
    target_rows = [
        {
            "row_id": "target_header",
            "role": "COLUMN_HEADER",
            "entries": [
                _entry("target_h1", "col_1", ["a_h1"]),
                _entry("target_h2", "col_2", ["a_h2"]),
            ],
        },
        {
            "row_id": "target_data",
            "role": "DATA",
            "entries": [
                _entry("target_d1", "col_1", ["a_d1"]),
                _entry("target_d2", "col_2", ["a_d2"]),
            ],
        },
    ]
    other_rows = [
        {
            "row_id": "other_header",
            "role": "COLUMN_HEADER",
            "entries": [_entry("other_h", "other_col", ["a_other_h"])],
        },
        {
            "row_id": "other_data",
            "role": "DATA",
            "entries": [_entry("other_d", "other_col", ["a_other_d"])],
        },
    ]
    target = _table("arbitrary_target_id", ["col_1", "col_2"], target_rows)
    other = _table("unrelated_table", ["other_col"], other_rows)
    anchor_words = {
        "a_h1": "w_h1",
        "a_h2": "w_h2",
        "a_d1": "w_d1",
        "a_d2": "w_d2",
        "a_other_h": "w_other_h",
        "a_other_d": "w_other_d",
    }
    owner_entry = {
        "a_h1": ("arbitrary_target_id", "target_h1"),
        "a_h2": ("arbitrary_target_id", "target_h2"),
        "a_d1": ("arbitrary_target_id", "target_d1"),
        "a_d2": ("arbitrary_target_id", "target_d2"),
        "a_other_h": ("unrelated_table", "other_h"),
        "a_other_d": ("unrelated_table", "other_d"),
    }
    anchors = [
        {
            "anchor_id": anchor_id,
            "locator": {"source_block_ref": word_ref, "page": 1},
        }
        for anchor_id, word_ref in anchor_words.items()
    ]
    ownership = [
        {
            "source_anchor_id": anchor_id,
            "source_word_id": f"source_{anchor_id}",
            "table_id": table_id,
            "owner_entry_id": entry_id,
        }
        for anchor_id, (table_id, entry_id) in owner_entry.items()
    ]
    recovery = LogicalRowTableRecoveryResult(
        schema_version="broker_reports_logical_row_table_recovery_v1",
        recovery_policy_version="test-v1",
        tables=[target, other],
        anchors=anchors,
        geometry_evidence=[],
        source_word_ownership=ownership,
        issues=[],
        paragraph_owned_word_refs=["w_title"],
        unowned_word_refs=[],
        diagnostics={},
    )
    bound = {
        "schema_version": "broker_reports_visual_table_structure_projection_rd_v3",
        "page_number": 1,
        "tables": [
            {
                "table_order": 7,
                "title_status": "PRESENT",
                "title_boxes_2d": [[0, 0, 80, 300]],
                "title_word_refs": ["w_title"],
                "header_status": "PRESENT",
                "header_boxes_2d": [[100, 0, 200, 1000]],
                "header_word_refs": ["w_h1", "w_h2"],
                "body_status": "HAS_DATA",
            }
        ],
    }
    return recovery, [payload], [visual_unit], bound


def _entry(entry_id: str, column_id: str, anchors: list[str]) -> dict:
    return {
        "entry_id": entry_id,
        "logical_column_id": column_id,
        "covers_logical_column_ids": [],
        "source_anchor_ids": anchors,
    }


def _table(table_id: str, columns: list[str], rows: list[dict]) -> dict:
    return {
        "table_id": table_id,
        "completeness_status": "COMPLETE",
        "logical_columns": [{"column_id": item} for item in columns],
        "ordered_rows": rows,
        "source_parts": [{"page": 1}],
        "relations": [],
        "issues": [],
        "known_gap_ids": [],
    }


def _canonical(scoped) -> dict:
    return CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(normalizer_version="table-scope-test-v1")
    ).create().build(
        tenant_id="tenant-test",
        artifact_version=1,
        document={
            "container_format": "pdf",
            "sha256": SOURCE_SHA,
            "declared_mime_type": "application/pdf",
        },
        source_artifact_ref="source-test",
        source_payloads=_fixture()[1],
        source_units=scoped.canonical_source_units,
        table_projections=scoped.projection_result.projections,
    )


def _tbank_scope_fixture():
    headers = [f"Unused {ordinal}" for ordinal in range(1, 33)]
    semantic_headers = {
        1: "Номер сделки",
        4: "Дата заключения",
        5: "Время",
        6: "Торговая площадка",
        8: "Вид сделки",
        9: "Сокращенное наименование актива",
        10: "Код актива",
        11: "Цена за единицу",
        12: "Валюта цены",
        13: "Количество",
        16: "Сумма сделки",
        17: "Валюта расчетов",
        18: "Комиссия брокера",
        19: "Валюта комиссии брокера",
        20: "Комиссия биржи",
        21: "Валюта комиссии биржи",
        26: "Дата расчетов",
        28: "Статус брокера",
    }
    for ordinal, literal in semantic_headers.items():
        headers[ordinal - 1] = literal

    def data_row(index: int) -> list[str]:
        values = [f"n/a-{index}-{ordinal}" for ordinal in range(1, 33)]
        replacements = {
            1: f"558641935{index}",
            4: "06.06.2022",
            5: "15:04:08",
            6: "ММВБ",
            8: "Покупка",
            9: "Ozon Holdings PLC ORD SHS ADR",
            10: "OZON",
            11: "793",
            12: "RUB",
            13: "1",
            16: "793",
            17: "RUB",
            18: "2,38",
            19: "RUB",
            20: "0.04",
            21: "RUB",
            26: "08.06.2022",
            28: "К",
        }
        for ordinal, literal in replacements.items():
            values[ordinal - 1] = literal
        return values

    matrix = [headers, *(data_row(index) for index in range(1, 6))]
    words = []
    anchors = []
    ownership = []
    rows = []
    word_number = 1
    title_ref = f"pdfword_{word_number:024x}"
    words.append(
        {
            "word_ref": title_ref,
            "source_value_ref": "sv_title",
            "page_ref": "page_1",
            "parser_ordinal": word_number,
            "text": "1.1 Сделки",
        }
    )
    word_number += 1
    header_refs = []
    for row_ordinal, values in enumerate(matrix):
        entries = []
        for column_ordinal, literal in enumerate(values, start=1):
            word_ref = f"pdfword_{word_number:024x}"
            anchor_id = f"a_{row_ordinal}_{column_ordinal}"
            entry_id = f"e_{row_ordinal}_{column_ordinal}"
            words.append(
                {
                    "word_ref": word_ref,
                    "source_value_ref": f"sv_{row_ordinal}_{column_ordinal}",
                    "page_ref": "page_1",
                    "parser_ordinal": word_number,
                    "text": literal,
                }
            )
            if row_ordinal == 0:
                header_refs.append(word_ref)
            anchors.append(
                {
                    "anchor_id": anchor_id,
                    "locator": {"source_block_ref": word_ref, "page": 1},
                }
            )
            ownership.append(
                {
                    "source_anchor_id": anchor_id,
                    "source_word_id": f"source_{anchor_id}",
                    "table_id": "random_tbank_target",
                    "owner_entry_id": entry_id,
                }
            )
            entries.append(_entry(entry_id, f"col_{column_ordinal}", [anchor_id]))
            word_number += 1
        rows.append(
            {
                "row_id": f"row_{row_ordinal}",
                "role": "COLUMN_HEADER" if row_ordinal == 0 else "DATA",
                "entries": entries,
            }
        )
    recovery = LogicalRowTableRecoveryResult(
        schema_version="broker_reports_logical_row_table_recovery_v1",
        recovery_policy_version="test-v1",
        tables=[
            _table(
                "random_tbank_target",
                [f"col_{ordinal}" for ordinal in range(1, 33)],
                rows,
            )
        ],
        anchors=anchors,
        geometry_evidence=[],
        source_word_ownership=ownership,
        issues=[],
        paragraph_owned_word_refs=[title_ref],
        unowned_word_refs=[],
        diagnostics={},
    )
    payload = {
        "source_payload_ref": "payload_tbank",
        "parser_completeness_status": "complete",
        "parser_completeness_reason_codes": [],
        "pdf_text_layer_projection": {
            "page_inventory": [{"page_ref": "page_1", "page_number": 1}],
            "word_inventory": words,
        },
    }
    visual_unit = {
        "unit_ref": "visual_tbank",
        "document_id": "document_tbank",
        "parent_payload_ref": "payload_tbank",
        "normalization_run_id": "run_tbank",
        "pdf_unit_type": "pdf_visual_page_unit",
        "source_location": {"kind": "pdf_visual_page_render", "page": 1},
        "page_refs": ["page_1"],
    }
    bound = {
        "schema_version": "broker_reports_visual_table_structure_projection_rd_v3",
        "page_number": 1,
        "tables": [
            {
                "table_order": 1,
                "title_status": "PRESENT",
                "title_boxes_2d": [[0, 0, 80, 1000]],
                "title_word_refs": [title_ref],
                "header_status": "PRESENT",
                "header_boxes_2d": [[100, 0, 200, 1000]],
                "header_word_refs": header_refs,
                "body_status": "HAS_DATA",
            }
        ],
    }
    parser_words = [
        {
            "parser_ordinal": 1,
            "text": "1.1 Сделки",
            "bbox": [0.0, 0.0, 500.0, 8.0],
            "source_bbox": [0.0, 0.0, 500.0, 8.0],
            "source_word_ref": title_ref,
        }
    ]
    for ordinal, (literal, word_ref) in enumerate(
        zip(headers, header_refs, strict=True), start=1
    ):
        bbox = [float((ordinal - 1) * 100), 10.0, float(ordinal * 100 - 5), 20.0]
        parser_words.append(
            {
                "parser_ordinal": ordinal + 1,
                "text": literal,
                "bbox": bbox,
                "source_bbox": copy.deepcopy(bbox),
                "source_word_ref": word_ref,
            }
        )
    parser_page = {
        "page_number": 1,
        "source_sha256": SOURCE_SHA,
        "width": 3200.0,
        "height": 100.0,
        "word_inventory": parser_words,
    }
    return recovery, [payload], [visual_unit], bound, parser_page


def test_exact_header_selects_one_table_and_preserves_full_source_partition() -> None:
    recovery, payloads, source_units, bound = _fixture()
    scoped = TableScopedRoleResearchFactory().create().build(
        recovery=recovery,
        payloads=payloads,
        source_units=source_units,
        bound_visual_projection=bound,
        source_checksum_sha256=SOURCE_SHA,
    )

    assert scoped.selected_table_id == "arbitrary_target_id"
    assert scoped.scope_binding["source_words_total"] == 7
    assert scoped.scope_binding["selected_table_words_total"] == 4
    assert scoped.scope_binding["complement_words_total"] == 3
    assert scoped.scope_binding["document_complete"] is False
    assert scoped.scope_binding["publication_allowed"] is False
    projection = scoped.projection_result.projections[0]
    assert projection["row_count"] == 2
    assert projection["column_count"] == 2

    canonical = _canonical(scoped)
    table = next(item for item in canonical["nodes"] if item["node_type"] == "TABLE")
    assert table["content"]["header"] == ["Date", "Amount"]
    assert table["content"]["rows"] == [["2025-01-01", "100"]]
    assert canonical["status"] == "validated"


def test_zero_or_two_header_matches_stop_before_canonical() -> None:
    recovery, payloads, source_units, bound = _fixture()
    missing = copy.deepcopy(bound)
    missing["tables"][0]["header_word_refs"] = ["w_title"]
    with pytest.raises(TableScopedRoleResearchError, match="table_scope_header_not_matched"):
        TableScopedRoleResearchFactory().create().build(
            recovery=recovery,
            payloads=payloads,
            source_units=source_units,
            bound_visual_projection=missing,
            source_checksum_sha256=SOURCE_SHA,
        )

    ambiguous = copy.deepcopy(recovery)
    clone = copy.deepcopy(ambiguous.tables[0])
    clone["table_id"] = "second_matching_table"
    ambiguous.tables.append(clone)
    with pytest.raises(TableScopedRoleResearchError, match="table_scope_header_ambiguous"):
        TableScopedRoleResearchFactory().create().build(
            recovery=ambiguous,
            payloads=payloads,
            source_units=source_units,
            bound_visual_projection=bound,
            source_checksum_sha256=SOURCE_SHA,
        )


def test_envelope_is_bound_to_canonical_and_cannot_enable_publication() -> None:
    recovery, payloads, source_units, bound = _fixture()
    service = TableScopedRoleResearchFactory().create()
    scoped = service.build(
        recovery=recovery,
        payloads=payloads,
        source_units=source_units,
        bound_visual_projection=bound,
        source_checksum_sha256=SOURCE_SHA,
    )
    canonical = _canonical(scoped)
    envelope = service.bind_canonical(
        scope_binding=scoped.scope_binding,
        canonical=canonical,
    )
    service.validate_envelope(envelope=envelope, canonical=canonical)

    tampered = copy.deepcopy(envelope)
    tampered["publication_allowed"] = True
    with pytest.raises(TableScopedRoleResearchError, match="table_scope_envelope_invalid"):
        service.validate_envelope(envelope=tampered, canonical=canonical)


def test_32_column_scope_reaches_roles_and_still_publishes_zero_facts() -> None:
    recovery, payloads, source_units, bound, parser_page = _tbank_scope_fixture()
    service = TableScopedRoleResearchFactory().create()
    scoped = service.build(
        recovery=recovery,
        payloads=payloads,
        source_units=source_units,
        bound_visual_projection=bound,
        source_checksum_sha256=SOURCE_SHA,
    )
    canonical = CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(normalizer_version="table-scope-32-test-v1")
    ).create().build(
        tenant_id="tenant-test",
        artifact_version=1,
        document={
            "container_format": "pdf",
            "sha256": SOURCE_SHA,
            "declared_mime_type": "application/pdf",
        },
        source_artifact_ref="source-test",
        source_payloads=payloads,
        source_units=scoped.canonical_source_units,
        table_projections=scoped.projection_result.projections,
    )
    envelope = service.bind_canonical(
        scope_binding=scoped.scope_binding, canonical=canonical
    )
    table = extract_tables(canonical)[0]
    assert len(table["rows"]) == 6
    assert len(table["columns"]) == 32
    assert table["rows"][1]["cells"][7]["literal"] == "Покупка"
    assert table["rows"][1]["cells"][8]["literal"] == (
        "Ozon Holdings PLC ORD SHS ADR"
    )

    visual_context = VisualRoleContextResearchFactory().create().build_from_table_projection(
        parser_page=parser_page,
        bound_structure=scoped.bound_structure,
        table_projection=scoped.projection_result.projections[0],
        expected_source_sha256=SOURCE_SHA,
    )
    request = enrich_role_request(
        baseline_request=compose_request(
            table=table,
            table_ref="table_1",
            variant="header_plus_profiles",
        ),
        visual_context=visual_context,
    )
    assert "source_bound_visual_context" in request["messages"][1]["content"]
    surface = build_table_surface(
        table, table_ref="table_1", variant="header_plus_profiles"
    )
    purchase_ref = next(
        item["value_ref"]
        for profile in surface["column_profiles"]
        if profile["column_ref"] == "c8"
        for item in profile["categorical_values"]
        if item["literal"] == "Покупка"
    )
    roles = [
        "trade_id",
        "unmapped",
        "unmapped",
        "trade_date",
        "trade_time",
        "venue",
        "unmapped",
        "side",
        "asset_name",
        "security_code",
        "unit_price",
        "currency",
        "quantity",
        "unmapped",
        "accrued_interest",
        "gross_amount",
        "currency",
        "broker_commission",
        "currency",
        "exchange_commission",
        "currency",
        "unmapped",
        "currency",
        "unmapped",
        "unmapped",
        "settlement_date",
        "unmapped",
        "status",
        "unmapped",
        "unmapped",
        "unmapped",
        "unmapped",
    ]
    frozen_response = {
        "schema_version": "broker_reports_research_table_role_mapping_v1",
        "table_ref": "table_1",
        "table_kind": "ORDINARY_SECURITY_TRADES",
        "header_row": 1,
        "columns": [
            {"column_ref": f"c{ordinal}", "role": role}
            for ordinal, role in enumerate(roles, start=1)
        ],
        "amount_currency_bindings": [
            {"amount_column_ref": "c16", "currency_column_ref": "c17"},
            {"amount_column_ref": "c18", "currency_column_ref": "c19"},
            {"amount_column_ref": "c20", "currency_column_ref": "c21"},
        ],
        "categorical_normalizations": [
            {
                "column_ref": "c8",
                "value_ref": purchase_ref,
                "normalized_value": "PURCHASE",
            }
        ],
    }
    contract = validate_response(
        raw_response=frozen_response,
        table=table,
        table_ref="table_1",
    )
    application = apply_contract(
        table=table,
        contract=contract,
        table_ref="table_1",
    )
    assert application["terminal"] == "COMPLETE"
    assert application["rows_accounted"] == 6
    assert len(application["observations"]) == 5
    assert {item["normalized_side"] for item in application["observations"]} == {
        "PURCHASE"
    }
    commission_bindings = [
        binding
        for observation in application["observations"]
        for binding in observation["bindings"]
        if binding["role"] in {"broker_commission", "exchange_commission"}
    ]
    assert len(commission_bindings) == 10
    assert envelope["document_complete"] is False
    assert envelope["publication_allowed"] is False
    assert envelope["facts_published"] == 0
