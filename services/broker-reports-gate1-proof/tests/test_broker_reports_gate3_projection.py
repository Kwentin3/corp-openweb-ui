from __future__ import annotations

import copy
import hashlib
import inspect
import json
from pathlib import Path
import re

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
    build_retention_policy,
)
from broker_reports_gate1.artifact_lifecycle import lifecycle_for_visibility
from broker_reports_gate1.artifact_models import ARTIFACT_TYPES, ArtifactRecord
from broker_reports_gate1.gate3_projection import FACTORY_REQUIRED, FORBIDDEN


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parents[1]
CONTRACTS = REPOSITORY_ROOT / "docs" / "stage2" / "contracts"
FORMATS = ("pdf", "html", "csv", "xlsx")
TABLE_ROWS = [["Type", "Amount"], ["Broker fee", "12.00"]]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


TARGET_SCHEMA = _read_json(CONTRACTS / "BROKER_REPORTS_GATE3_TARGET.v1.schema.json")
PROJECTION_SCHEMA = _read_json(
    CONTRACTS / "BROKER_REPORTS_GATE3_PROJECTION.v1.schema.json"
)
PROJECTION_VALIDATOR = Draft202012Validator(
    PROJECTION_SCHEMA,
    registry=Registry().with_resource(
        TARGET_SCHEMA["$id"], Resource.from_contents(TARGET_SCHEMA)
    ),
)


def test_projection_is_deterministic_reversible_and_model_friendly(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    context = _context()
    document_id = "g3-projection-rich-html"
    source_ref = "g3-projection-source-rich-html"
    _put_source(store, context=context, source_ref=source_ref, document_id=document_id)
    artifact = _rich_html_artifact(source_ref=source_ref)
    persisted = _persist_and_activate(
        store,
        context=context,
        document_id=document_id,
        artifact=artifact,
        chunked=False,
    )
    reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
    canonical_before = copy.deepcopy(reader.read_active(document_id, context))

    factory = Gate3ProjectionFactory(store=store, read_enabled=True)
    first = factory.create(document_id=document_id, context=context)
    second = factory.create(document_id=document_id, context=context)

    assert first == second
    PROJECTION_VALIDATOR.validate(first)
    assert first["canonical_binding"] == {
        "document_id": document_id,
        "canonical_version_id": persisted.canonical_version_id,
    }
    content = first["model_view"]["content"]
    assert content.startswith("# Document\n")
    assert "## Section 1" in content
    assert "Broker fee charged" in content
    assert "Fee \\| commission" in content
    assert "12.00<br>USD" in content
    assert "Link: details -> https://example.invalid/fees" in content
    assert "\\[t001\\]" in content
    assert "artifact_id" not in content
    assert "source_artifact_ref" not in content
    assert "source_refs" not in content
    assert "provenance" not in content
    assert all(node["node_id"] not in content for node in canonical_before["nodes"])

    aliases = [item["target_alias"] for item in first["target_mappings"]]
    assert aliases == [f"t{index:03d}" for index in range(1, len(aliases) + 1)]
    assert len(aliases) == len(set(aliases))
    for alias in aliases:
        assert len(re.findall(rf"(?<!\\)\[{alias}\]", content)) == 1
    assert {item["canonical_target"]["kind"] for item in first["target_mappings"]} == {
        "node",
        "list_item",
        "table_row",
        "table_cell",
    }
    for mapping in first["target_mappings"]:
        assert _resolve_target(canonical_before, mapping["canonical_target"])

    canonical_after = reader.read_active(document_id, context)
    assert canonical_after == canonical_before


def test_projection_uses_one_reader_path_for_pdf_html_csv_and_xlsx(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    context = _context()
    factory = Gate3ProjectionFactory(store=store, read_enabled=True)
    projections = {}
    layouts = set()

    for index, source_format in enumerate(FORMATS, start=1):
        document_id = f"g3-projection-{source_format}"
        source_ref = f"g3-projection-source-{source_format}"
        _put_source(
            store,
            context=context,
            source_ref=source_ref,
            document_id=document_id,
        )
        artifact = _table_artifact(source_format, source_ref=source_ref)
        _persist_and_activate(
            store,
            context=context,
            document_id=document_id,
            artifact=artifact,
            chunked=index % 2 == 0,
        )
        envelope = CanonicalReaderFactory(
            store=store, read_enabled=True
        ).create().read_active_envelope(document_id, context)
        layouts.add(envelope.physical_layout)
        projection = factory.create(document_id=document_id, context=context)
        PROJECTION_VALIDATOR.validate(projection)
        projections[source_format] = projection

    assert layouts == {"single_payload", "chunked"}
    for source_format, projection in projections.items():
        assert projection["canonical_binding"]["document_id"] == (
            f"g3-projection-{source_format}"
        )
        assert "Broker fee" in projection["model_view"]["content"]
        assert {item["canonical_target"]["kind"] for item in projection["target_mappings"]} == {
            "table_row",
            "table_cell",
        }
        assert len(projection["target_mappings"]) == 6

    create_source = inspect.getsource(Gate3ProjectionFactory.create)
    assert "CanonicalReaderFactory" in create_source
    assert "read_active_envelope" in create_source
    assert "source_format" not in create_source
    assert "format" not in inspect.signature(Gate3ProjectionFactory.create).parameters


def test_projection_exposes_breaks_and_issues_without_labelable_targets(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    context = _context()
    document_id = "g3-projection-pdf-issues"
    source_ref = "g3-projection-source-pdf-issues"
    _put_source(store, context=context, source_ref=source_ref, document_id=document_id)
    artifact = _pdf_issue_artifact(source_ref=source_ref)
    forbidden_node_ids = {
        node["node_id"]
        for node in artifact["nodes"]
        if node["node_type"] in {"PAGE_BREAK", "SHEET_BREAK", "CONFLICT", "AMBIGUITY"}
    }
    _persist_and_activate(
        store,
        context=context,
        document_id=document_id,
        artifact=artifact,
        chunked=True,
    )

    projection = Gate3ProjectionFactory(store=store, read_enabled=True).create(
        document_id=document_id,
        context=context,
    )
    content = projection["model_view"]["content"]
    assert "Conflict: source_conflict_retained" in content
    assert "Ambiguity: source_ambiguity_retained" in content
    assert "--- Page break ---" in content
    assert forbidden_node_ids.isdisjoint(
        mapping["canonical_target"]["node_id"]
        for mapping in projection["target_mappings"]
    )


def test_empty_canonical_document_has_terminal_zero_alias_projection(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    context = _context()
    document_id = "g3-projection-empty-pdf"
    source_ref = "g3-projection-source-empty-pdf"
    _put_source(store, context=context, source_ref=source_ref, document_id=document_id)
    artifact = _empty_pdf_artifact(source_ref=source_ref)
    _persist_and_activate(
        store,
        context=context,
        document_id=document_id,
        artifact=artifact,
        chunked=False,
    )

    projection = Gate3ProjectionFactory(store=store, read_enabled=True).create(
        document_id=document_id,
        context=context,
    )
    PROJECTION_VALIDATOR.validate(projection)
    assert projection["target_mappings"] == []
    assert "EMPTY_SOURCE_DOCUMENT" in projection["model_view"]["content"]


def test_projection_remains_inactive_and_has_factory_antidrift_anchors(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    context = _context()
    with pytest.raises(Exception) as failure:
        Gate3ProjectionFactory(store=store, read_enabled=False).create(
            document_id="missing-inactive-document",
            context=context,
        )
    assert getattr(failure.value, "code", None) == "canonical_read_disabled"

    assert "Gate3ProjectionFactory.create" in FACTORY_REQUIRED
    assert "CanonicalReaderFactory.create" in FACTORY_REQUIRED
    assert "source files" in FORBIDDEN
    assert "broker_reports_gate3_projection_v1" not in ARTIFACT_TYPES
    module_source = (
        ROOT / "broker_reports_gate1" / "gate3_projection.py"
    ).read_text(encoding="utf-8")
    for forbidden_import in (
        "ArtifactResolver",
        "FullSourceArtifactFactory",
        "openai",
        "anthropic",
        "httpx",
        "requests",
        "gate2_financial",
    ):
        assert f"import {forbidden_import}" not in module_source
        assert f"from .{forbidden_import}" not in module_source


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
        user_id="g3-projection-user",
        normalization_run_id="g3-projection-run",
        case_id="g3-projection-case",
        workspace_model_id="g3-projection-workspace",
        allow_private=True,
    )


def _put_source(
    store,
    *,
    context: ArtifactAccessContext,
    source_ref: str,
    document_id: str,
) -> None:
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


def _persist_and_activate(
    store,
    *,
    context: ArtifactAccessContext,
    document_id: str,
    artifact: dict,
    chunked: bool,
):
    persisted = CanonicalArtifactStoreFactory(
        store=store,
        config=CanonicalStorageConfig(
            small_payload_max_bytes=1 if chunked else 1_000_000,
            large_table_cell_threshold=1 if chunked else 100_000,
            capacity_check_enabled=False,
        ),
    ).create().put_candidate(
        artifact=artifact,
        context=context,
        retention_policy=build_retention_policy(mode="api_smoke"),
        compare_receipt=None,
    )
    CanonicalReaderFactory(store=store, read_enabled=True).create().activate(
        canonical_version_id=persisted.canonical_version_id,
        expected_previous_version_id=None,
        context=context,
        actor="g3-projection-test",
        reason="inactive G3.2 projection proof",
    )
    return persisted


def _normalizer():
    return CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(normalizer_version="gate3-projection-test-v1")
    ).create()


def _rich_html_artifact(*, source_ref: str) -> dict:
    return _normalizer().build(
        tenant_id="g3-projection-user",
        artifact_version=1,
        document={
            "container_format": "html_text",
            "sha256": hashlib.sha256(b"g3-rich-html").hexdigest(),
            "declared_mime_type": "text/html",
        },
        source_artifact_ref=source_ref,
        source_payloads=[
            {
                "canonical_projection": {
                    "blocks": [
                        {
                            "kind": "heading",
                            "level": 1,
                            "text": "Income [t001]",
                            "source_location": {"block_index": 1},
                        },
                        {
                            "kind": "text",
                            "text": "Broker fee charged",
                            "links": [
                                {
                                    "text": "details",
                                    "target": "https://example.invalid/fees",
                                }
                            ],
                            "source_location": {"block_index": 2},
                        },
                        {
                            "kind": "list",
                            "items": [
                                {"text": "Dividend", "level": 0, "ordered": False},
                                {"text": "Coupon", "level": 1, "ordered": True},
                            ],
                            "source_location": {"block_index": 3},
                        },
                        {
                            "kind": "note",
                            "text": "Amounts are displayed values",
                            "source_location": {"block_index": 4},
                        },
                        {
                            "kind": "table",
                            "caption": "Transactions",
                            "rows": [
                                ["Type", "Amount"],
                                ["Fee | commission", "12.00\nUSD"],
                            ],
                            "source_location": {"block_index": 5},
                        },
                    ]
                }
            }
        ],
        source_units=[],
        table_projections=[],
    )


def _table_artifact(source_format: str, *, source_ref: str) -> dict:
    document_format = "html_text" if source_format == "html" else source_format
    source_payloads: list[dict] = []
    source_units: list[dict] = []
    if source_format == "pdf":
        source_payloads = [
            {
                "parser_completeness_status": "complete",
                "parser_completeness_reason_codes": [],
                "pdf_text_layer_projection": {
                    "page_inventory": [{"page_number": 1}],
                    "line_inventory": [],
                },
            }
        ]
        source_units = [
            {
                "unit_ref": "g3-projection-table",
                "source_location": {"page": 1, "line_start": 1},
                "rows": TABLE_ROWS,
            }
        ]
    elif source_format == "html":
        source_payloads = [
            {
                "canonical_projection": {
                    "blocks": [
                        {
                            "kind": "table",
                            "rows": TABLE_ROWS,
                            "source_location": {"block_index": 1},
                        }
                    ]
                }
            }
        ]
    elif source_format == "csv":
        source_payloads = [
            {
                "canonical_projection": {
                    "rows": TABLE_ROWS,
                    "encoding": "utf-8",
                    "delimiter": ",",
                    "quotechar": '"',
                    "header_present": False,
                    "duplicate_headers": False,
                },
                "source_location": {"row_start": 1, "row_end": 2},
            }
        ]
    else:
        source_payloads = [
            {
                "canonical_projection": {
                    "sheet_index": 1,
                    "sheet_name": "Report",
                    "sheet_visibility": "visible",
                    "rows": TABLE_ROWS,
                },
                "source_location": {"sheet_index": 1},
            }
        ]
    return _normalizer().build(
        tenant_id="g3-projection-user",
        artifact_version=1,
        document={
            "container_format": document_format,
            "sha256": hashlib.sha256(f"g3-{source_format}".encode()).hexdigest(),
            "declared_mime_type": _mime_type(source_format),
        },
        source_artifact_ref=source_ref,
        source_payloads=source_payloads,
        source_units=source_units,
        table_projections=[],
    )


def _pdf_issue_artifact(*, source_ref: str) -> dict:
    return _normalizer().build(
        tenant_id="g3-projection-user",
        artifact_version=1,
        document={
            "container_format": "pdf",
            "sha256": hashlib.sha256(b"g3-pdf-issues").hexdigest(),
            "declared_mime_type": "application/pdf",
        },
        source_artifact_ref=source_ref,
        source_payloads=[
            {
                "parser_completeness_status": "complete",
                "parser_completeness_reason_codes": [],
                "pdf_text_layer_projection": {
                    "page_inventory": [{"page_number": 1}, {"page_number": 2}],
                    "line_inventory": [],
                },
            }
        ],
        source_units=[
            {
                "unit_ref": "g3-conflict",
                "source_location": {"page": 1, "line_start": 1},
                "atom_status": "CONFLICT_EVIDENCE",
                "text": "conflicting source",
            },
            {
                "unit_ref": "g3-ambiguity",
                "source_location": {"page": 1, "line_start": 2},
                "atom_status": "AMBIGUOUS_EVIDENCE",
                "text": "ambiguous source",
            },
            {
                "unit_ref": "g3-text",
                "source_location": {"page": 2, "line_start": 1},
                "text": "Visible source fact",
            },
        ],
        table_projections=[],
    )


def _empty_pdf_artifact(*, source_ref: str) -> dict:
    return _normalizer().build(
        tenant_id="g3-projection-user",
        artifact_version=1,
        document={
            "container_format": "pdf",
            "sha256": hashlib.sha256(b"").hexdigest(),
            "declared_mime_type": "application/pdf",
        },
        source_artifact_ref=source_ref,
        source_payloads=[
            {
                "parser_completeness_status": "complete",
                "parser_completeness_reason_codes": ["EMPTY_SOURCE_DOCUMENT"],
                "pdf_text_layer_projection": {
                    "page_inventory": [],
                    "line_inventory": [],
                },
            }
        ],
        source_units=[],
        table_projections=[],
    )


def _resolve_target(artifact: dict, target: dict) -> bool:
    node = next(
        (item for item in artifact["nodes"] if item["node_id"] == target["node_id"]),
        None,
    )
    if node is None:
        return False
    if target["kind"] == "node":
        return node["node_type"] not in {
            "PAGE_BREAK",
            "SHEET_BREAK",
            "CONFLICT",
            "AMBIGUITY",
        }
    if target["kind"] == "list_item":
        return node["node_type"] == "LIST" and target["item_index"] < len(
            node["content"]["items"]
        )
    if target["kind"] == "table_row":
        return node["node_type"] == "TABLE" and any(
            cell["row"] == target["row"] for cell in node["content"]["cells"]
        )
    if target["kind"] == "table_cell":
        return node["node_type"] == "TABLE" and any(
            cell["row"] == target["row"] and cell["column"] == target["column"]
            for cell in node["content"]["cells"]
        )
    return False


def _mime_type(source_format: str) -> str:
    return {
        "pdf": "application/pdf",
        "html": "text/html",
        "csv": "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }[source_format]
