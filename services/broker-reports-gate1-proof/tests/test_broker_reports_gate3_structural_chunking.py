from __future__ import annotations

from collections import Counter
import hashlib
import inspect
import json
from pathlib import Path
import re
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    CanonicalArtifactStoreFactory,
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
    CanonicalReaderFactory,
    CanonicalStorageConfig,
    Gate3ProjectionFactory,
    Gate3StructuralChunkError,
    Gate3StructuralChunkFactory,
    build_retention_policy,
)
from broker_reports_gate1.artifact_lifecycle import lifecycle_for_visibility
from broker_reports_gate1.artifact_models import ARTIFACT_TYPES, ArtifactRecord
from broker_reports_gate1.gate3_structural_chunking import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    _chunk_rendered_units,
)


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parents[1]
CONTRACTS = REPOSITORY_ROOT / "docs" / "stage2" / "contracts"
ALIAS_RE = re.compile(r"(?<!\\)\[(t[0-9]{3,})\]")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


TARGET_SCHEMA = _read_json(CONTRACTS / "BROKER_REPORTS_GATE3_TARGET.v1.schema.json")
CHUNK_SCHEMA = _read_json(
    CONTRACTS / "BROKER_REPORTS_GATE3_STRUCTURAL_CHUNK_SET.v1.schema.json"
)
CHUNK_VALIDATOR = Draft202012Validator(
    CHUNK_SCHEMA,
    registry=Registry().with_resource(
        TARGET_SCHEMA["$id"], Resource.from_contents(TARGET_SCHEMA)
    ),
)


def test_compact_document_stays_one_exact_whole_projection(tmp_path: Path) -> None:
    store = _store(tmp_path)
    context = _context()
    document_id = "g3-chunk-compact"
    _put_and_activate(
        store,
        context=context,
        document_id=document_id,
        artifact=_html_artifact(document_id=document_id, blocks=8),
    )
    projection = Gate3ProjectionFactory(store=store, read_enabled=True).create(
        document_id=document_id,
        context=context,
    )
    factory = Gate3StructuralChunkFactory(
        store=store,
        read_enabled=True,
        max_chunk_chars=60_000,
    )

    first = factory.create(document_id=document_id, context=context)
    second = factory.create(document_id=document_id, context=context)

    assert first == second
    CHUNK_VALIDATOR.validate(first)
    assert len(first["chunks"]) == 1
    chunk = first["chunks"][0]
    assert chunk["structural_kind"] == "whole_document"
    assert chunk["model_view"]["content"] == projection["model_view"]["content"]
    assert chunk["target_mappings"] == projection["target_mappings"]
    assert first["coverage"] == _expected_coverage(len(projection["target_mappings"]))


def test_large_table_uses_contiguous_whole_rows_with_context(tmp_path: Path) -> None:
    store = _store(tmp_path)
    context = _context()
    document_id = "g3-chunk-large-table"
    rows = [["Column A", "Column B", "Column C"]] + [
        [f"row-{index}", f"value-{index}", "x" * 24]
        for index in range(1, 181)
    ]
    _put_and_activate(
        store,
        context=context,
        document_id=document_id,
        artifact=_csv_artifact(document_id=document_id, rows=rows),
    )
    projection = Gate3ProjectionFactory(store=store, read_enabled=True).create(
        document_id=document_id,
        context=context,
    )
    result = Gate3StructuralChunkFactory(
        store=store,
        read_enabled=True,
        max_chunk_chars=2_400,
    ).create(document_id=document_id, context=context)

    CHUNK_VALIDATOR.validate(result)
    chunks = result["chunks"]
    assert len(chunks) > 2
    assert {chunk["structural_kind"] for chunk in chunks} == {"table_rows"}
    assert max(chunk["metrics"]["model_view_chars"] for chunk in chunks) <= 2_400
    assert all(chunk["context_policy"]["data_row_overlap"] == 0 for chunk in chunks)
    ranges = [
        (
            chunk["structural_scope"]["row_start"],
            chunk["structural_scope"]["row_end"],
        )
        for chunk in chunks
    ]
    assert ranges[0][0] == 1
    assert ranges[-1][1] == len(rows)
    assert all(current[1] + 1 == following[0] for current, following in zip(ranges, ranges[1:]))
    assert chunks[0]["context_policy"]["repeated_table_header"] is False
    assert all(
        chunk["context_policy"]["repeated_table_header"] is True
        for chunk in chunks[1:]
    )
    for chunk in chunks:
        content = chunk["model_view"]["content"]
        assert "Structural context (context only)" in content
        assert "Target content" in content
        assert "| row | column 1 | column 2 | column 3 |" in content
    assert "Column A" in chunks[0]["model_view"]["content"]
    assert "Column A" in chunks[1]["model_view"]["content"]
    _assert_exact_target_coverage(projection=projection, chunk_set=result)


def test_workbook_partitions_tables_before_row_groups_and_never_mixes_documents(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    context = _context()
    first_document = "g3-chunk-workbook-a"
    second_document = "g3-chunk-workbook-b"
    _put_and_activate(
        store,
        context=context,
        document_id=first_document,
        artifact=_xlsx_artifact(
            document_id=first_document,
            table_row_counts=(5, 120, 7),
        ),
    )
    _put_and_activate(
        store,
        context=context,
        document_id=second_document,
        artifact=_xlsx_artifact(
            document_id=second_document,
            table_row_counts=(6, 8),
        ),
    )
    factory = Gate3StructuralChunkFactory(
        store=store,
        read_enabled=True,
        max_chunk_chars=2_000,
    )

    first = factory.create(document_id=first_document, context=context)
    second = factory.create(document_id=second_document, context=context)

    CHUNK_VALIDATOR.validate(first)
    CHUNK_VALIDATOR.validate(second)
    assert {chunk["canonical_binding"]["document_id"] for chunk in first["chunks"]} == {
        first_document
    }
    assert {chunk["canonical_binding"]["document_id"] for chunk in second["chunks"]} == {
        second_document
    }
    assert all(len(chunk["structural_scope"]["node_refs"]) <= 1 for chunk in first["chunks"])
    assert "whole_table" in {chunk["structural_kind"] for chunk in first["chunks"]}
    assert "table_rows" in {chunk["structural_kind"] for chunk in first["chunks"]}
    assert all(chunk["metrics"]["target_count"] > 0 for chunk in first["chunks"])
    assert "Sheet break" in first["chunks"][1]["model_view"]["content"]
    row_chunk_node_refs = {
        tuple(chunk["structural_scope"]["node_refs"])
        for chunk in first["chunks"]
        if chunk["structural_kind"] == "table_rows"
    }
    assert len(row_chunk_node_refs) == 1
    assert not ({chunk["chunk_id"] for chunk in first["chunks"]} & {chunk["chunk_id"] for chunk in second["chunks"]})


def test_text_blocks_pack_in_order_with_natural_container_context(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    context = _context()
    document_id = "g3-chunk-text"
    _put_and_activate(
        store,
        context=context,
        document_id=document_id,
        artifact=_html_artifact(document_id=document_id, blocks=45),
    )
    projection = Gate3ProjectionFactory(store=store, read_enabled=True).create(
        document_id=document_id,
        context=context,
    )
    result = Gate3StructuralChunkFactory(
        store=store,
        read_enabled=True,
        max_chunk_chars=700,
    ).create(document_id=document_id, context=context)

    assert len(result["chunks"]) > 1
    assert {chunk["structural_kind"] for chunk in result["chunks"]} == {
        "structural_blocks"
    }
    assert all(
        "Structural context (context only)" in chunk["model_view"]["content"]
        for chunk in result["chunks"]
    )
    _assert_exact_target_coverage(projection=projection, chunk_set=result)


def test_page_breaks_remain_visible_without_forcing_one_chunk_per_page(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    context = _context()
    document_id = "g3-chunk-multipage-pdf"
    source_ref = f"source-{document_id}"
    artifact = _normalizer().build(
        tenant_id=context.user_id,
        artifact_version=1,
        document={
            "container_format": "pdf",
            "sha256": hashlib.sha256(document_id.encode()).hexdigest(),
            "declared_mime_type": "application/pdf",
        },
        source_artifact_ref=source_ref,
        source_payloads=[
            {
                "parser_completeness_status": "complete",
                "parser_completeness_reason_codes": [],
                "pdf_text_layer_projection": {
                    "page_inventory": [
                        {"page_number": 1},
                        {"page_number": 2},
                        {"page_number": 3},
                    ],
                    "line_inventory": [],
                },
            }
        ],
        source_units=[
            {
                "unit_ref": f"page-{page}",
                "source_location": {"page": page, "line_start": 1},
                "text": f"Page {page} " + "x" * 250,
            }
            for page in range(1, 4)
        ],
        table_projections=[],
    )
    _put_and_activate(
        store,
        context=context,
        document_id=document_id,
        artifact=artifact,
    )

    result = Gate3StructuralChunkFactory(
        store=store,
        read_enabled=True,
        max_chunk_chars=800,
    ).create(document_id=document_id, context=context)

    assert len(result["chunks"]) == 2
    assert result["chunks"][0]["metrics"]["target_count"] == 2
    assert result["chunks"][0]["model_view"]["content"].count("Page break") == 1
    assert len(result["chunks"][0]["structural_scope"]["container_refs"]) == 2


def test_adjacent_same_shape_headerless_table_reuses_source_header_as_context() -> None:
    grid = (
        "| row | column 1 | column 2 |",
        "| --- | --- | --- |",
    )
    first_rows = (
        "| [t001] header | [t002] Operation | [t003] Amount |",
        "| [t004] 2 | [t005] Purchase | [t006] 10.00 |",
    )
    second_rows = (
        "| [t007] 1 | [t008] Sale | [t009] 20.00 |",
    )

    def table_unit(node_id: str, page: int, rows: tuple[str, ...], header: bool):
        heading = "### Table"
        content = "\n".join((heading, *grid, *rows))
        return SimpleNamespace(
            unit_kind="table",
            container_id=f"page-{page}",
            ancestor_headings=("# Document", f"## Page {page}"),
            node_id=node_id,
            node_type="TABLE",
            content=content,
            table=SimpleNamespace(
                heading_lines=(heading,),
                grid_header_lines=grid,
                row_lines=rows,
                note_lines=(),
                header_present=header,
            ),
        )

    units = (
        table_unit("table-1", 1, first_rows, True),
        SimpleNamespace(
            unit_kind="break",
            container_id="page-2",
            ancestor_headings=("# Document", "## Page 2"),
            node_id=None,
            node_type="PAGE_BREAK",
            content="Page break",
            table=None,
        ),
        table_unit("table-2", 2, second_rows, False),
    )
    aliases = [f"t{index:03d}" for index in range(1, 10)]
    mappings = {
        alias: {
            "target_alias": alias,
            "canonical_target": {"kind": "node", "node_id": alias},
        }
        for alias in aliases
    }

    chunks = _chunk_rendered_units(
        units=units,
        binding={
            "document_id": "continuation-document",
            "canonical_version_id": "continuation-version",
        },
        mapping_by_alias=mappings,
        mapping_order={alias: index for index, alias in enumerate(aliases)},
        max_chunk_chars=10_000,
    )

    assert len(chunks) == 2
    assert chunks[0]["context_policy"]["repeated_table_header"] is False
    assert chunks[1]["context_policy"]["repeated_table_header"] is True
    assert "Operation" in chunks[1]["model_view"]["content"]
    assert "Amount" in chunks[1]["model_view"]["content"]
    assert "[t002]" not in chunks[1]["model_view"]["content"]
    assert [
        mapping["target_alias"]
        for chunk in chunks
        for mapping in chunk["target_mappings"]
    ] == aliases


def test_indivisible_row_exceeding_budget_fails_closed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    context = _context()
    document_id = "g3-chunk-indivisible-row"
    rows = [["Header A", "Header B"], ["one-row", "x" * 8_000]]
    _put_and_activate(
        store,
        context=context,
        document_id=document_id,
        artifact=_csv_artifact(document_id=document_id, rows=rows),
    )

    with pytest.raises(Gate3StructuralChunkError) as failure:
        Gate3StructuralChunkFactory(
            store=store,
            read_enabled=True,
            max_chunk_chars=900,
        ).create(document_id=document_id, context=context)

    assert failure.value.code == (
        "gate3_structural_chunk_indivisible_unit_exceeds_budget"
    )
    assert failure.value.details["unit_kind"] == "table_row"
    assert failure.value.details["required_chars"] > 900


def test_chunker_is_inactive_factory_routed_and_contains_no_smart_runtime(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    context = _context()
    with pytest.raises(Exception) as failure:
        Gate3StructuralChunkFactory(
            store=store,
            read_enabled=False,
        ).create(document_id="missing-document", context=context)
    assert getattr(failure.value, "code", None) == "canonical_read_disabled"

    create_source = inspect.getsource(Gate3StructuralChunkFactory.create)
    module_source = (
        ROOT / "broker_reports_gate1" / "gate3_structural_chunking.py"
    ).read_text(encoding="utf-8")
    assert "Gate3ProjectionFactory" in create_source
    assert "Gate3StructuralChunkFactory.create" in FACTORY_REQUIRED
    assert "second alias authority" in FORBIDDEN
    assert "broker_reports_gate3_structural_chunk_set_v1" not in ARTIFACT_TYPES
    assert "def main(" not in module_source
    assert "put_record" not in module_source
    assert "async def" not in module_source
    for forbidden_import in (
        "gate3_financial_label_dictionary",
        "gate3_bounded_labeling",
        "gate2_financial",
        "openai",
        "anthropic",
        "requests",
        "httpx",
        "artifact_store",
        "artifact_resolver",
    ):
        assert f"import {forbidden_import}" not in module_source
        assert f"from .{forbidden_import}" not in module_source
    compile_literals = re.findall(r"re\.compile\(r?\"([^\"]+)\"\)", module_source)
    assert compile_literals == [r"(?<!\\)\[(t[0-9]{3,})\]"]


def _assert_exact_target_coverage(*, projection: dict, chunk_set: dict) -> None:
    expected_aliases = ALIAS_RE.findall(projection["model_view"]["content"])
    actual_aliases = [
        mapping["target_alias"]
        for chunk in chunk_set["chunks"]
        for mapping in chunk["target_mappings"]
    ]
    assert actual_aliases == expected_aliases
    expected_targets = {
        mapping["target_alias"]: mapping["canonical_target"]
        for mapping in projection["target_mappings"]
    }
    assert all(
        mapping["canonical_target"] == expected_targets[mapping["target_alias"]]
        for chunk in chunk_set["chunks"]
        for mapping in chunk["target_mappings"]
    )
    visible_counts = Counter(
        alias
        for chunk in chunk_set["chunks"]
        for alias in ALIAS_RE.findall(chunk["model_view"]["content"])
    )
    assert visible_counts == Counter({alias: 1 for alias in expected_aliases})
    assert chunk_set["coverage"] == _expected_coverage(len(expected_aliases))


def _expected_coverage(targets: int) -> dict:
    return {
        "eligible_targets": targets,
        "working_targets": targets,
        "lost_targets": 0,
        "duplicated_working_targets": 0,
        "context_only_target_aliases": 0,
        "data_row_overlap": 0,
        "target_order_preserved": True,
    }


def _store(root: Path):
    return ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "artifacts.sqlite3",
            payload_root=root / "payloads",
        )
    ).create()


def _context() -> ArtifactAccessContext:
    return ArtifactAccessContext(
        user_id="g3-chunk-user",
        normalization_run_id="g3-chunk-run",
        case_id="g3-chunk-case",
        workspace_model_id="g3-chunk-workspace",
        allow_private=True,
    )


def _normalizer():
    return CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(normalizer_version="gate3-chunk-test-v1")
    ).create()


def _put_and_activate(
    store,
    *,
    context: ArtifactAccessContext,
    document_id: str,
    artifact: dict,
) -> None:
    source_ref = str(artifact["source"]["source_artifact_ref"])
    retention = build_retention_policy(mode="api_smoke")
    store.put_record(
        ArtifactRecord(
            artifact_id=source_ref,
            artifact_type="source_file_ref_v0",
            case_id=context.case_id,
            chat_id=context.chat_id,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=context.normalization_run_id,
            document_id=document_id,
            source_file_ref={"openwebui_file_id": f"file-{document_id}"},
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=retention,
            access_policy={"requires_user_id": True},
            validation_status="validated",
            lifecycle_status=lifecycle_for_visibility(
                visibility="private_case", validation_status="validated"
            ),
            payload={"synthetic_fixture": True},
        )
    )
    persisted = CanonicalArtifactStoreFactory(
        store=store,
        config=CanonicalStorageConfig(
            small_payload_max_bytes=1_000_000,
            large_table_cell_threshold=100_000,
            capacity_check_enabled=False,
        ),
    ).create().put_candidate(
        artifact=artifact,
        context=context,
        retention_policy=retention,
        compare_receipt=None,
    )
    CanonicalReaderFactory(store=store, read_enabled=True).create().activate(
        canonical_version_id=persisted.canonical_version_id,
        expected_previous_version_id=None,
        context=context,
        actor="g3-chunk-test",
        reason="inactive G3.4B structural chunk proof",
    )


def _html_artifact(*, document_id: str, blocks: int) -> dict:
    source_ref = f"source-{document_id}"
    return _normalizer().build(
        tenant_id="g3-chunk-user",
        artifact_version=1,
        document={
            "container_format": "html_text",
            "sha256": hashlib.sha256(document_id.encode()).hexdigest(),
            "declared_mime_type": "text/html",
        },
        source_artifact_ref=source_ref,
        source_payloads=[
            {
                "canonical_projection": {
                    "blocks": [
                        {
                            "kind": "heading" if index % 10 == 0 else "text",
                            "level": 2,
                            "text": f"Structural block {index} " + "x" * 72,
                            "source_location": {"block_index": index + 1},
                        }
                        for index in range(blocks)
                    ]
                }
            }
        ],
        source_units=[],
        table_projections=[],
    )


def _csv_artifact(*, document_id: str, rows: list[list[str]]) -> dict:
    source_ref = f"source-{document_id}"
    return _normalizer().build(
        tenant_id="g3-chunk-user",
        artifact_version=1,
        document={
            "container_format": "csv",
            "sha256": hashlib.sha256(document_id.encode()).hexdigest(),
            "declared_mime_type": "text/csv",
        },
        source_artifact_ref=source_ref,
        source_payloads=[
            {
                "canonical_projection": {
                    "rows": rows,
                    "encoding": "utf-8",
                    "delimiter": ",",
                    "quotechar": '"',
                    "header_present": True,
                    "duplicate_headers": False,
                },
                "source_location": {"row_start": 1, "row_end": len(rows)},
            }
        ],
        source_units=[],
        table_projections=[],
    )


def _xlsx_artifact(
    *,
    document_id: str,
    table_row_counts: tuple[int, ...],
) -> dict:
    source_ref = f"source-{document_id}"
    payloads = []
    for sheet_index, row_count in enumerate(table_row_counts, start=1):
        rows = [["Column A", "Column B"]] + [
            [f"sheet-{sheet_index}-row-{row}", "x" * 24]
            for row in range(1, row_count)
        ]
        payloads.append(
            {
                "canonical_projection": {
                    "sheet_index": sheet_index,
                    "sheet_name": f"Sheet {sheet_index}",
                    "sheet_visibility": "visible",
                    "rows": rows,
                },
                "source_location": {"sheet_index": sheet_index},
            }
        )
    return _normalizer().build(
        tenant_id="g3-chunk-user",
        artifact_version=1,
        document={
            "container_format": "xlsx",
            "sha256": hashlib.sha256(document_id.encode()).hexdigest(),
            "declared_mime_type": (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        },
        source_artifact_ref=source_ref,
        source_payloads=payloads,
        source_units=[],
        table_projections=[],
    )
