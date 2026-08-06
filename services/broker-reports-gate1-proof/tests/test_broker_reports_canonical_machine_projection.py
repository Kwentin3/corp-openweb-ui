from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import pytest

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    CanonicalArtifactError,
    CanonicalArtifactStoreFactory,
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
    CanonicalReaderFactory,
    CanonicalStorageConfig,
    assess_canonical_completeness,
    build_retention_policy,
    render_neutral_canonical_projection,
)
from broker_reports_gate1.artifact_lifecycle import lifecycle_for_visibility
from broker_reports_gate1.artifact_models import ArtifactRecord
from broker_reports_gate1.canonical_wave2_shadow import (
    WAVE2_SHADOW_CONTRACTS,
    CanonicalWave2ShadowFactory,
)


FORMATS = ("pdf", "html", "csv", "xlsx")
TABLE_ROWS = [["Metric", "Value"], ["Revenue", "10"], ["Cost", "4"]]


def test_reader_projection_and_wave2_contract_are_format_opaque(tmp_path: Path) -> None:
    store = _store(tmp_path)
    context = _context()
    reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
    resolved: dict[str, dict] = {}
    layouts: set[str] = set()

    for index, source_format in enumerate(FORMATS, start=1):
        document_id = f"doc33-{source_format}"
        source_ref = f"doc33-source-{source_format}"
        _put_source(
            store,
            context=context,
            source_ref=source_ref,
            document_id=document_id,
        )
        artifact = _build_artifact(source_format, source_ref=source_ref)
        persisted = (
            CanonicalArtifactStoreFactory(
                store=store,
                config=CanonicalStorageConfig(
                    small_payload_max_bytes=100_000 if index % 2 else 1,
                    large_table_cell_threshold=100_000 if index % 2 else 1,
                ),
            )
            .create()
            .put_candidate(
                artifact=artifact,
                context=context,
                retention_policy=build_retention_policy(mode="api_smoke"),
                compare_receipt=None,
            )
        )
        reader.activate(
            canonical_version_id=persisted.canonical_version_id,
            expected_previous_version_id=None,
            context=context,
            actor="doc33-test",
            reason="unified reader proof",
        )
        envelope = reader.read_active_envelope(document_id, context)
        resolved[source_format] = envelope.artifact
        layouts.add(envelope.physical_layout)

    assert layouts == {"single_payload", "chunked"}
    assert {artifact["schema_version"] for artifact in resolved.values()} == {
        "canonical_artifact_v1"
    }
    assert {frozenset(artifact) for artifact in resolved.values()} == {
        frozenset(next(iter(resolved.values())))
    }
    assert all(
        assess_canonical_completeness(artifact)["status"] == "passed"
        for artifact in resolved.values()
    )
    projections = {
        source_format: render_neutral_canonical_projection(artifact)
        for source_format, artifact in resolved.items()
    }
    assert all(value.strip() and "[TABLE]" in value for value in projections.values())
    assert len({_logical_table_signature(value) for value in resolved.values()}) == 1

    renderer_source = inspect.getsource(render_neutral_canonical_projection)
    for forbidden in (
        "source_format",
        "ArtifactStore",
        "ArtifactResolver",
        "raw_pdf",
        "provider_payload",
        "private_evidence",
    ):
        assert forbidden not in renderer_source

    shadow = (
        CanonicalWave2ShadowFactory(
            store=store,
            contract=WAVE2_SHADOW_CONTRACTS[0],
            enabled=True,
        )
        .create()
        .read_active(document_id="doc33-xlsx", context=context)
    )
    assert shadow.compatibility_status == "CANONICAL_OK"
    assert shadow.output is not None
    assert "source_format" not in shadow.output
    assert shadow.output["legacy_fallback"] is False
    assert shadow.output["product_writes"] == 0
    assert shadow.output["provider_requests"] == 0


@pytest.mark.parametrize("source_format", FORMATS)
def test_nonempty_source_without_machine_content_fails_closed(
    source_format: str,
) -> None:
    source_ref = f"doc33-empty-{source_format}"
    document_format = "html_text" if source_format == "html" else source_format
    document = {
        "container_format": document_format,
        "sha256": hashlib.sha256(f"nonempty-{source_format}".encode()).hexdigest(),
        "declared_mime_type": _mime_type(source_format),
    }
    source_payloads: list[dict] = []
    if source_format == "pdf":
        source_payloads = [
            {
                "parser_completeness_status": "failed",
                "parser_completeness_reason_codes": ["source_nonempty"],
                "pdf_text_layer_projection": {
                    "page_inventory": [{"page_number": 1}],
                    "line_inventory": [],
                },
            }
        ]
    with pytest.raises(CanonicalArtifactError) as raised:
        CanonicalNormalizerFactory(
            CanonicalNormalizerConfig(normalizer_version="canonical-doc33-test-v1")
        ).create().build(
            tenant_id="doc33-user",
            artifact_version=1,
            document=document,
            source_artifact_ref=source_ref,
            source_payloads=source_payloads,
            source_units=[],
            table_projections=[],
        )
    assert raised.value.code in {
        "canonical_artifact_validation_failed",
        "canonical_pdf_source_atom_accounting_incomplete",
    }


def test_reader_rejects_unified_contract_ref_and_root_tampering(tmp_path: Path) -> None:
    store = _store(tmp_path)
    context = _context()
    source_ref = "doc33-source-tamper"
    document_id = "doc33-tamper"
    _put_source(
        store,
        context=context,
        source_ref=source_ref,
        document_id=document_id,
    )
    artifact = _build_artifact("csv", source_ref=source_ref)
    artifact["containers"][0]["container_type"] = "WORKBOOK"
    with pytest.raises(Exception) as raised:
        CanonicalArtifactStoreFactory(store=store).create().put_candidate(
            artifact=artifact,
            context=context,
            retention_policy=build_retention_policy(mode="api_smoke"),
            compare_receipt=None,
        )
    assert getattr(raised.value, "code", None) == "artifact_blocked"


def _build_artifact(source_format: str, *, source_ref: str) -> dict:
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
                "unit_ref": "doc33-table",
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
                "source_location": {"row_start": 1, "row_end": 3},
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
    return (
        CanonicalNormalizerFactory(
            CanonicalNormalizerConfig(normalizer_version="canonical-doc33-test-v1")
        )
        .create()
        .build(
            tenant_id="doc33-user",
            artifact_version=1,
            document={
                "container_format": document_format,
                "sha256": hashlib.sha256(f"doc33-{source_format}".encode()).hexdigest(),
                "declared_mime_type": _mime_type(source_format),
            },
            source_artifact_ref=source_ref,
            source_payloads=source_payloads,
            source_units=source_units,
            table_projections=[],
        )
    )


def _logical_table_signature(artifact: dict) -> tuple[tuple[int, int, object], ...]:
    table = next(node for node in artifact["nodes"] if node["node_type"] == "TABLE")
    return tuple(
        (int(cell["row"]), int(cell["column"]), cell["value"])
        for cell in sorted(
            table["content"]["cells"],
            key=lambda value: (int(value["row"]), int(value["column"])),
        )
    )


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
        user_id="doc33-user",
        normalization_run_id="doc33-run",
        case_id="doc33-case",
        workspace_model_id="doc33-workspace",
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


def _mime_type(source_format: str) -> str:
    return {
        "pdf": "application/pdf",
        "html": "text/html",
        "csv": "text/csv",
        "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    }[source_format]
