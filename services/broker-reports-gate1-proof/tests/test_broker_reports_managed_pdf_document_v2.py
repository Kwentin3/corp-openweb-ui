from __future__ import annotations

import ast
import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from broker_reports_gate1.logical_row_table_recovery import (
    LogicalRowTableRecoveryResult,
)
from broker_reports_gate1.managed_document_contracts_v2 import (
    SCHEMA_CANONICAL_SHA256,
    ManagedDocumentContractV2Error,
    ManagedDocumentContractV2Validator,
)
from broker_reports_gate1.managed_pdf_document_v2 import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    ManagedPdfDocumentV2Error,
    ManagedPdfDocumentV2Factory,
)
from tests.test_broker_reports_pdf_layout_slice2 import _ruled_table_pdf


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SERVICE_ROOT.parents[1]
SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_MANAGED_DOCUMENT.v2.schema.json"
)
MODULE_PATH = (
    SERVICE_ROOT
    / "broker_reports_gate1"
    / "managed_pdf_document_v2.py"
)


def _document_id_for_source_ref(source_artifact_ref: str) -> str:
    canonical = json.dumps(
        ["private_source_artifact_identity", source_artifact_ref],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"document_pdf_{hashlib.sha256(canonical).hexdigest()[:24]}"


def _source_word_id_for_ref(source_block_ref: str) -> str:
    canonical = json.dumps(
        [source_block_ref],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"source_word_{hashlib.sha256(canonical).hexdigest()[:24]}"


class _FakeFullSourceBuilder:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def build(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            payloads=[self.payload],
            units=[{"must_not_be_consumed": True}],
            summary={"parser_completeness_status": "complete"},
        )


class _FakeFullSourceFactory:
    def __init__(self, builder: _FakeFullSourceBuilder) -> None:
        self.builder = builder
        self.create_calls = 0

    def create(self) -> _FakeFullSourceBuilder:
        self.create_calls += 1
        return self.builder


class _FakeRecoveryRuntime:
    def __init__(self, result: LogicalRowTableRecoveryResult) -> None:
        self.result = result
        self.projection: Any = None
        self.kwargs: dict[str, Any] = {}

    def recover(
        self,
        projection: dict[str, Any],
        **kwargs: Any,
    ) -> LogicalRowTableRecoveryResult:
        self.projection = projection
        self.kwargs = kwargs
        return self.result


class _FakeRecoveryFactory:
    def __init__(self, runtime: _FakeRecoveryRuntime) -> None:
        self.runtime = runtime
        self.create_calls = 0

    def create(self) -> _FakeRecoveryRuntime:
        self.create_calls += 1
        return self.runtime


def _schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _projection() -> dict[str, Any]:
    return {
        "schema_version": "pdf_text_layer_projection_v0",
        "page_inventory": [
            {
                "page_ref": "page_fixture",
                "page_number": 1,
                "layout_page_width": 320.0,
                "layout_page_height": 320.0,
            }
        ],
        "bbox_inventory": [
            {
                "bbox_ref": "bbox_before",
                "page_ref": "page_fixture",
                "bbox": [20.0, 20.0, 80.0, 30.0],
            },
            {
                "bbox_ref": "bbox_table",
                "page_ref": "page_fixture",
                "bbox": [20.0, 60.0, 80.0, 70.0],
            },
            {
                "bbox_ref": "bbox_after",
                "page_ref": "page_fixture",
                "bbox": [20.0, 100.0, 80.0, 110.0],
            },
        ],
        "word_inventory": [
            _word("word_before", "Before", "bbox_before", 1),
            _word("word_table", "TableOwned", "bbox_table", 2),
            _word("word_after", "After", "bbox_after", 3),
        ],
        "line_inventory": [
            _line("line_before", "word_before"),
            _line("line_table", "word_table"),
            _line("line_after", "word_after"),
        ],
        "block_inventory": [
            _block("source_block_before", "line_before"),
            _block("source_block_table", "line_table"),
            _block("source_block_after", "line_after"),
        ],
    }


def _word(
    word_ref: str,
    text: str,
    bbox_ref: str,
    order: int,
) -> dict[str, Any]:
    return {
        "word_ref": word_ref,
        "page_ref": "page_fixture",
        "bbox_ref": bbox_ref,
        "text": text,
        "geometry_reading_order": order,
        "parser_ordinal": order,
    }


def _line(line_ref: str, word_ref: str) -> dict[str, Any]:
    return {
        "line_ref": line_ref,
        "page_ref": "page_fixture",
        "word_refs": [word_ref],
    }


def _block(block_ref: str, line_ref: str) -> dict[str, Any]:
    return {
        "block_ref": block_ref,
        "page_ref": "page_fixture",
        "line_refs": [line_ref],
    }


def _recovery() -> LogicalRowTableRecoveryResult:
    anchor = {
        "information_class": "PROVENANCE",
        "anchor_id": "anchor_fixture_table_word",
        "source_format": "PDF",
        "checksum_sha256": "a" * 64,
        "locator": {
            "kind": "PDF",
            "source_part_index": 1,
            "page": 1,
            "source_block_ref": "word_table",
            "bbox": [20.0, 60.0, 80.0, 70.0],
            "private_locator": {
                "information_class": "PRIVATE_SOURCE",
                "status": "PRESENT",
                "ref": "private_fixture#anchor_fixture_table_word",
                "checksum_sha256": "b" * 64,
            },
        },
    }
    region_anchor = {
        "information_class": "PROVENANCE",
        "anchor_id": "anchor_fixture_table_region",
        "source_format": "PDF",
        "checksum_sha256": "a" * 64,
        "locator": {
            "kind": "PDF",
            "source_part_index": 1,
            "page": 1,
            "source_block_ref": "source_block_table",
            "bbox": [20.0, 60.0, 80.0, 70.0],
            "private_locator": {
                "information_class": "PRIVATE_SOURCE",
                "status": "PRESENT",
                "ref": "private_fixture#anchor_fixture_table_region",
                "checksum_sha256": "2" * 64,
            },
        },
    }
    geometry = {
        "information_class": "PRIVATE_SOURCE",
        "geometry_evidence_id": "geometry_fixture_table",
        "kind": "TABLE_REGION",
        "origin": "DETERMINISTIC_DERIVED",
        "source_anchor_ids": ["anchor_fixture_table_region"],
        "private_artifact": {
            "information_class": "PRIVATE_SOURCE",
            "status": "PRESENT",
            "ref": "private_fixture#geometry_fixture_table",
            "checksum_sha256": "c" * 64,
        },
        "evidence_checksum_sha256": "d" * 64,
        "issue_ids": [],
    }
    row_geometry = {
        "information_class": "PRIVATE_SOURCE",
        "geometry_evidence_id": "geometry_fixture_row",
        "kind": "ROW_BAND",
        "origin": "DETERMINISTIC_DERIVED",
        "source_anchor_ids": ["anchor_fixture_table_word"],
        "private_artifact": {
            "information_class": "PRIVATE_SOURCE",
            "status": "PRESENT",
            "ref": "private_fixture#geometry_fixture_row",
            "checksum_sha256": "3" * 64,
        },
        "evidence_checksum_sha256": "4" * 64,
        "issue_ids": [],
    }
    entry_geometry = {
        "information_class": "PRIVATE_SOURCE",
        "geometry_evidence_id": "geometry_fixture_entry_base",
        "kind": "ENTRY_REGION",
        "origin": "DETERMINISTIC_DERIVED",
        "source_anchor_ids": ["anchor_fixture_table_word"],
        "private_artifact": {
            "information_class": "PRIVATE_SOURCE",
            "status": "PRESENT",
            "ref": "private_fixture#geometry_fixture_entry_base",
            "checksum_sha256": "5" * 64,
        },
        "evidence_checksum_sha256": "6" * 64,
        "issue_ids": [],
    }
    table = {
        "information_class": "CONTENT",
        "table_id": "table_fixture",
        "completeness_status": "COMPLETE",
        "ordered_rows": [
            {
                "row_id": "row_fixture",
                "ordinal": 0,
                "role": "DATA",
                "role_origin": "DETERMINISTIC_DERIVED",
                "nesting_level": 0,
                "parent_row_id": None,
                "entries": [
                    {
                        "entry_id": "entry_fixture",
                        "ordinal": 0,
                        "kind": "LABEL",
                        "text": "TableOwned",
                        "origin": "DETERMINISTIC_DERIVED",
                        "column_binding_status": "NOT_APPLICABLE",
                        "logical_column_id": None,
                        "covers_logical_column_ids": [],
                        "source_anchor_ids": ["anchor_fixture_table_word"],
                        "geometry_evidence_ids": [
                            "geometry_fixture_entry_base"
                        ],
                        "issue_ids": [],
                    }
                ],
                "source_anchor_ids": ["anchor_fixture_table_word"],
                "geometry_evidence_ids": ["geometry_fixture_row"],
                "issue_ids": [],
            }
        ],
        "logical_columns": [],
        "source_parts": [
            {
                "source_part_id": "source_part_fixture",
                "ordinal": 0,
                "page": 1,
                "region_anchor_id": "anchor_fixture_table_region",
                "first_row_id": "row_fixture",
                "last_row_id": "row_fixture",
                "continuation_status": "SINGLE",
                "geometry_evidence_ids": ["geometry_fixture_table"],
                "continuation_evidence_ids": [],
                "issue_ids": [],
            }
        ],
        "relations": [],
        "issues": [],
        "known_gap_ids": [],
    }
    ownership = {
        "information_class": "PRIVATE_SOURCE",
        "source_word_id": _source_word_id_for_ref("word_table"),
        "table_id": "table_fixture",
        "owner_status": "OWNED",
        "owner_entry_id": "entry_fixture",
        "duplicate_of_source_word_id": None,
        "source_anchor_id": "anchor_fixture_table_word",
        "issue_ids": [],
    }
    return LogicalRowTableRecoveryResult(
        schema_version="broker_reports_logical_row_table_recovery_v1",
        recovery_policy_version="logical_row_geometry_recovery_policy_v1",
        tables=[table],
        anchors=[anchor, region_anchor],
        geometry_evidence=[geometry, row_geometry, entry_geometry],
        source_word_ownership=[ownership],
        issues=[],
        paragraph_owned_word_refs=["word_before", "word_after"],
        unowned_word_refs=[],
        diagnostics={
            "logical_tables_total": 1,
            "multiple_word_owners_total": 0,
            "unowned_words_total": 0,
        },
    )


def _cover_bound_recovery() -> LogicalRowTableRecoveryResult:
    recovery = copy.deepcopy(_recovery())
    table = recovery.tables[0]
    row = table["ordered_rows"][0]
    entry = row["entries"][0]
    column_ids = ["column_fixture_left", "column_fixture_right"]
    entry_geometry_id = "geometry_fixture_entry"
    entry.update(
        {
            "column_binding_status": "BOUND",
            "logical_column_id": None,
            "covers_logical_column_ids": column_ids,
            "geometry_evidence_ids": [entry_geometry_id],
        }
    )
    row["role"] = "COLUMN_HEADER"
    table["logical_columns"] = [
        {
            "column_id": column_id,
            "ordinal": ordinal,
            "header_path": [entry["entry_id"]],
            "source_anchor_ids": list(entry["source_anchor_ids"]),
            "geometry_evidence_ids": [f"geometry_fixture_column_{ordinal}"],
            "issue_ids": [],
        }
        for ordinal, column_id in enumerate(column_ids)
    ]

    def geometry(evidence_id: str, kind: str, checksum: str) -> dict[str, Any]:
        return {
            "information_class": "PRIVATE_SOURCE",
            "geometry_evidence_id": evidence_id,
            "kind": kind,
            "origin": "DETERMINISTIC_DERIVED",
            "source_anchor_ids": list(entry["source_anchor_ids"]),
            "private_artifact": {
                "information_class": "PRIVATE_SOURCE",
                "status": "PRESENT",
                "ref": f"private_fixture#{evidence_id}",
                "checksum_sha256": checksum * 64,
            },
            "evidence_checksum_sha256": checksum * 64,
            "issue_ids": [],
        }

    recovery.geometry_evidence[:] = [
        item
        for item in recovery.geometry_evidence
        if item["geometry_evidence_id"] != "geometry_fixture_entry_base"
    ]
    recovery.geometry_evidence.extend(
        [
            geometry(entry_geometry_id, "ENTRY_REGION", "e"),
            geometry("geometry_fixture_column_0", "COLUMN_ALIGNMENT", "f"),
            geometry("geometry_fixture_column_1", "COLUMN_ALIGNMENT", "1"),
        ]
    )
    return recovery


def _payload(projection: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_payload_ref": "source_payload_fixture",
        "container_format": "pdf",
        "parser_completeness_status": "complete",
        "text_layer_projection_status": "complete",
        "layout_projection_status": "complete",
        "pdf_text_layer_projection": projection,
        "normalized_projection": {"must_not_be_consumed": True},
    }


def _factory_fixture(
    recovery: LogicalRowTableRecoveryResult | None = None,
) -> tuple[
    ManagedPdfDocumentV2Factory,
    dict[str, Any],
    _FakeFullSourceFactory,
    _FakeRecoveryFactory,
]:
    projection = _projection()
    full_builder = _FakeFullSourceBuilder(_payload(projection))
    full_factory = _FakeFullSourceFactory(full_builder)
    recovery_runtime = _FakeRecoveryRuntime(recovery or _recovery())
    recovery_factory = _FakeRecoveryFactory(recovery_runtime)
    factory = ManagedPdfDocumentV2Factory(
        full_source_factory=full_factory,
        logical_row_table_factory=recovery_factory,
    )
    return factory, projection, full_factory, recovery_factory


def test_factory_route_uses_only_full_source_projection_and_seals_v2() -> None:
    factory, projection, full_factory, recovery_factory = _factory_fixture()
    content = b"%PDF-1.7 synthetic boundary fixture"
    result = factory.create(_schema()).build(
        content,
        source_artifact_ref="private_pdf_fixture",
    )

    assert full_factory.create_calls == 1
    assert recovery_factory.create_calls == 1
    assert recovery_factory.runtime.projection is projection
    assert full_factory.builder.calls == [
        {
            "normalization_run_id": (
                "normrun_doc6_" + hashlib.sha256(content).hexdigest()[:24]
            ),
            "document_id": (
                _document_id_for_source_ref("private_pdf_fixture")
            ),
            "profile_id": "broker_reports_managed_document_v2",
            "container_format": "pdf",
            "content_bytes": content,
            "source_checksum_sha256": hashlib.sha256(content).hexdigest(),
        }
    ]
    assert recovery_factory.runtime.kwargs == {
        "source_checksum_sha256": hashlib.sha256(content).hexdigest(),
        "private_evidence_ref": "private_pdf_fixture",
    }
    assert result.status == "COMPLETE"
    assert (
        ManagedDocumentContractV2Validator(_schema())
        .validate(result.managed_document.payload)
        .payload
        == result.managed_document.payload
    )


def test_factory_rejects_same_id_schema_tampering() -> None:
    factory, _, _, _ = _factory_fixture()
    tampered_schema = _schema()
    tampered_schema["$defs"]["tableContent"]["additionalProperties"] = True

    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_schema_hash_invalid",
    ):
        factory.create(tampered_schema)


def test_document_id_is_opaque_source_artifact_identity_not_source_hash() -> None:
    source_ref = "private_pdf_stable_identity"
    first_factory, _, _, _ = _factory_fixture()
    second_factory, _, _, _ = _factory_fixture()
    third_factory, _, _, _ = _factory_fixture()

    first = first_factory.create(_schema()).build(
        b"synthetic source alpha",
        source_artifact_ref=source_ref,
    )
    second = second_factory.create(_schema()).build(
        b"synthetic source beta",
        source_artifact_ref=source_ref,
    )
    third = third_factory.create(_schema()).build(
        b"synthetic source alpha",
        source_artifact_ref="private_pdf_different_identity",
    )
    first_id = first.managed_document.payload["document_id"]

    assert first_id == _document_id_for_source_ref(source_ref)
    assert second.managed_document.payload["document_id"] == first_id
    assert third.managed_document.payload["document_id"] != first_id
    assert hashlib.sha256(b"synthetic source alpha").hexdigest()[:24] not in first_id
    assert source_ref not in first_id


def test_source_artifact_identity_is_required_for_safe_document_id() -> None:
    factory, _, _, _ = _factory_fixture()

    with pytest.raises(
        ManagedPdfDocumentV2Error,
        match="managed_pdf_v2_private_source_ref_required",
    ):
        factory.create(_schema()).build(b"synthetic source")


def test_factory_strictly_seals_cover_bound_header_entry() -> None:
    factory, _, _, _ = _factory_fixture(_cover_bound_recovery())

    result = factory.create(_schema()).build(
        b"synthetic covered source",
        source_artifact_ref="private_pdf_fixture",
    )
    table = next(
        block["content"]
        for block in result.managed_document.payload["blocks"]
        if block["block_type"] == "TABLE"
    )
    entry = table["ordered_rows"][0]["entries"][0]
    column_ids = [column["column_id"] for column in table["logical_columns"]]

    assert entry["column_binding_status"] == "BOUND"
    assert entry["logical_column_id"] is None
    assert entry["covers_logical_column_ids"] == column_ids
    assert [column["header_path"] for column in table["logical_columns"]] == [
        [entry["entry_id"]],
        [entry["entry_id"]],
    ]
    assert (
        ManagedDocumentContractV2Validator(_schema())
        .validate(result.managed_document.payload)
        .payload
        == result.managed_document.payload
    )


def test_table_is_emitted_at_first_owned_word_and_never_in_paragraph() -> None:
    factory, _, _, _ = _factory_fixture()
    result = factory.create(_schema()).build(
        b"synthetic source",
        source_artifact_ref="private_pdf_fixture",
    )
    blocks = result.managed_document.payload["blocks"]

    assert [block["block_type"] for block in blocks] == [
        "BOUNDARY",
        "PARAGRAPH",
        "TABLE",
        "PARAGRAPH",
    ]
    paragraph_texts = [
        block["content"]["raw_text"]
        for block in blocks
        if block["block_type"] == "PARAGRAPH"
    ]
    assert paragraph_texts == ["Before", "After"]
    assert all("TableOwned" not in text for text in paragraph_texts)
    table = next(
        block["content"] for block in blocks if block["block_type"] == "TABLE"
    )
    assert table["ordered_rows"][0]["entries"][0]["text"] == "TableOwned"
    assert result.safe_diagnostics["paragraph_table_overlap_total"] == 0
    assert result.safe_diagnostics["unowned_words_total"] == 0


def test_paragraph_preserves_full_source_physical_line_boundaries() -> None:
    factory, projection, _, recovery_factory = _factory_fixture()
    projection["bbox_inventory"].append(
        {
            "bbox_ref": "bbox_before_second",
            "page_ref": "page_fixture",
            "bbox": [20.0, 35.0, 100.0, 45.0],
        }
    )
    for word in projection["word_inventory"]:
        if word["word_ref"] in {"word_table", "word_after"}:
            word["geometry_reading_order"] += 1
            word["parser_ordinal"] += 1
    projection["word_inventory"].append(
        _word(
            "word_before_second",
            "SecondLine",
            "bbox_before_second",
            2,
        )
    )
    projection["line_inventory"].append(
        _line("line_before_second", "word_before_second")
    )
    first_block = next(
        block
        for block in projection["block_inventory"]
        if block["block_ref"] == "source_block_before"
    )
    first_block["line_refs"].append("line_before_second")
    recovery_factory.runtime.result = replace(
        recovery_factory.runtime.result,
        paragraph_owned_word_refs=[
            "word_before",
            "word_before_second",
            "word_after",
        ],
    )

    result = factory.create(_schema()).build(
        b"synthetic source",
        source_artifact_ref="private_pdf_fixture",
    )
    paragraph_texts = [
        block["content"]["raw_text"]
        for block in result.managed_document.payload["blocks"]
        if block["block_type"] == "PARAGRAPH"
    ]

    assert paragraph_texts == ["Before\nSecondLine", "After"]


def test_public_factories_complete_real_synthetic_pdf_without_word_gaps() -> (
    None
):
    result = (
        ManagedPdfDocumentV2Factory()
        .create(_schema())
        .build(
            _ruled_table_pdf(),
            source_artifact_ref="private_pdf_ruled_fixture",
        )
    )

    assert result.status == "COMPLETE"
    assert [
        block["block_type"]
        for block in result.managed_document.payload["blocks"]
    ] == ["BOUNDARY", "PARAGRAPH", "TABLE", "PARAGRAPH"]
    assert result.safe_diagnostics["logical_tables_total"] == 1
    assert result.safe_diagnostics["unowned_words_total"] == 0
    assert result.safe_diagnostics["multiple_word_owners_total"] == 0
    assert result.safe_diagnostics["paragraph_table_overlap_total"] == 0
    assert (
        result.safe_diagnostics["table_words_total"]
        + result.safe_diagnostics["paragraph_words_total"]
        == result.safe_diagnostics["source_words_total"]
    )


def test_safe_and_private_diagnostics_are_separate() -> None:
    factory, _, _, _ = _factory_fixture()
    result = factory.create(_schema()).build(
        b"synthetic source",
        source_artifact_ref="private_pdf_fixture",
    )

    safe_text = json.dumps(result.safe_diagnostics, sort_keys=True)
    assert "private_pdf_fixture" not in safe_text
    assert "word_before" not in safe_text
    assert "TableOwned" not in safe_text
    assert result.safe_diagnostics["private_values_included"] is False
    assert "document_id" not in result.safe_diagnostics
    assert result.safe_diagnostics[
        "managed_document_schema_canonical_sha256"
    ] == SCHEMA_CANONICAL_SHA256
    assert result.private_diagnostics["private_source_ref"] == (
        "private_pdf_fixture"
    )
    assert result.private_diagnostics["document_id"] == (
        result.managed_document.payload["document_id"]
    )
    assert result.private_diagnostics["paragraph_owned_word_refs"] == [
        "word_before",
        "word_after",
    ]


def test_partition_gap_or_overlap_fails_before_contract_seal() -> None:
    missing = replace(
        _recovery(),
        paragraph_owned_word_refs=["word_before"],
    )
    factory, _, _, _ = _factory_fixture(missing)
    with pytest.raises(
        ManagedPdfDocumentV2Error,
        match="managed_pdf_v2_source_word_partition_invalid",
    ):
        factory.create(_schema()).build(
            b"synthetic source",
            source_artifact_ref="private_pdf_fixture",
        )

    overlap = replace(
        _recovery(),
        paragraph_owned_word_refs=[
            "word_before",
            "word_table",
            "word_after",
        ],
    )
    factory, _, _, _ = _factory_fixture(overlap)
    with pytest.raises(
        ManagedPdfDocumentV2Error,
        match="managed_pdf_v2_paragraph_table_word_overlap",
    ):
        factory.create(_schema()).build(
            b"synthetic source",
            source_artifact_ref="private_pdf_fixture",
        )


def test_inactive_v2_builder_has_no_product_or_bundle_reachability() -> None:
    assert "ManagedPdfDocumentV2Factory.create" in FACTORY_REQUIRED
    assert "PdfLayoutUnitBuilder" in FORBIDDEN
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "pdf_layout_units" not in imported_modules
    assert "broker_pdf_neutral_tables" not in imported_modules
    assert "table_projection" not in imported_modules
    assert "managed_pdf_document_v2" not in (
        SERVICE_ROOT / "broker_reports_gate1" / "__init__.py"
    ).read_text(encoding="utf-8")
    assert not any(
        "managed_pdf_document_v2" in path.read_text(
            encoding="utf-8",
            errors="ignore",
        )
        for path in (SERVICE_ROOT / "openwebui_actions").glob("*.py")
    )
