from __future__ import annotations

import copy
import hashlib
import inspect
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreError,
    ArtifactStoreFactory,
    CanonicalArtifactError,
    CanonicalArtifactStoreFactory,
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
    CanonicalReaderFactory,
    FileInput,
    Gate1Normalizer,
    LocalPdfCompactResearchCanonicalAdapterFactory,
    build_retention_policy,
    persist_gate1_result,
)
from broker_reports_gate1.artifact_models import ArtifactRecord
from broker_reports_gate1.canonical_artifact import validate_canonical_artifact
from broker_reports_gate1.canonical_consumer_migration import (
    _render_generic_pdf_projection,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]


SOURCE_SHA256 = "a" * 64


def _payload(*, pages: int = 1, empty: bool = False) -> dict:
    return {
        "parser_completeness_status": "complete",
        "parser_completeness_reason_codes": (
            ["EMPTY_SOURCE_DOCUMENT"] if empty else []
        ),
        "pdf_text_layer_projection": {
            "page_inventory": [
                {"page_number": page} for page in range(1, pages + 1)
            ],
            "line_inventory": [
                {"line_ref": f"line-{page}"} for page in range(1, pages + 1)
            ],
        },
    }


def _unit(ref: str, *, page: int, text: str) -> dict:
    return {
        "unit_ref": ref,
        "pdf_unit_type": "pdf_page_text_unit",
        "source_location": {"page": page, "line_start": 1},
        "coverage": {
            "selected_source_refs": [f"atom-{ref}"],
            "all_selected_refs_accounted": True,
        },
        "text": text,
    }


def _build(
    *,
    source_ref: str = "source-doc32",
    payloads: list[dict] | None = None,
    units: list[dict] | None = None,
    projections: list[dict] | None = None,
    normalizer_version: str = "canonical-doc32-test-v1",
) -> dict:
    return CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(normalizer_version=normalizer_version)
    ).create().build(
        tenant_id="doc32-user",
        artifact_version=1,
        document={
            "container_format": "pdf",
            "sha256": SOURCE_SHA256,
            "declared_mime_type": "application/pdf",
        },
        source_artifact_ref=source_ref,
        source_payloads=payloads if payloads is not None else [_payload()],
        source_units=units if units is not None else [_unit("text-1", page=1, text="Visible text")],
        table_projections=projections or [],
    )


def _context(run_id: str = "doc32-run") -> ArtifactAccessContext:
    return ArtifactAccessContext(
        user_id="doc32-user",
        normalization_run_id=run_id,
        case_id="doc32-case",
        workspace_model_id="doc32-workspace",
        allow_private=True,
        require_source_available=True,
    )


def _store(root: Path):
    return ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "artifacts.sqlite3",
            payload_root=root / "payloads",
        )
    ).create()


def _source_record(context: ArtifactAccessContext, document_id: str) -> ArtifactRecord:
    source_ref = "source-doc32"
    source_file_ref = {
        "provider": "doc32-test",
        "openwebui_file_id": "doc32-source",
        "file_hash_sha256": SOURCE_SHA256,
        "content_type": "application/pdf",
        "size_bytes": 64,
    }
    return ArtifactRecord(
        artifact_id=source_ref,
        artifact_type="source_file_ref_v0",
        case_id=context.case_id,
        chat_id=context.chat_id,
        user_id=context.user_id,
        workspace_model_id=context.workspace_model_id,
        normalization_run_id=context.normalization_run_id,
        document_id=document_id,
        source_file_ref=source_file_ref,
        visibility="private_case",
        storage_backend="project_artifact_payload",
        retention_policy=build_retention_policy(mode="api_smoke"),
        access_policy={
            "requires_user_id": True,
            "requires_case_or_chat": True,
        },
        validation_status="validated",
        lifecycle_status="private_ready",
        payload_kind="json_file",
        payload={
            "schema_version": "source_file_ref_v0",
            "document_id": document_id,
            "source_file_ref": source_file_ref,
        },
        safe_metadata={"source_available": True},
    )


def _publish(root: Path, artifact: dict | None = None):
    context = _context()
    document_id = "doc32-document"
    store = _store(root)
    store.put_record(_source_record(context, document_id))
    artifact = artifact or _build()
    persisted = CanonicalArtifactStoreFactory(store=store).create().put_candidate(
        artifact=artifact,
        context=context,
        retention_policy=build_retention_policy(mode="api_smoke"),
        compare_receipt=None,
    )
    reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
    reader.activate(
        canonical_version_id=persisted.canonical_version_id,
        expected_previous_version_id=None,
        context=context,
        actor="doc32-test",
        reason="test activation",
    )
    return store, reader, context, document_id, artifact


def _synthetic_pdf_bytes() -> bytes:
    writer = PdfWriter()
    font = writer._add_object(
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
    )
    for page_number in (1, 2):
        page = writer.add_blank_page(width=320, height=320)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        stream = DecodedStreamObject()
        stream.set_data(
            (
                "BT /F1 10 Tf 20 280 Td "
                f"(DOC32 durable page {page_number}) Tj ET"
            ).encode("latin-1")
        )
        page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_nonempty_pdf_zero_node_build_fails_closed() -> None:
    with pytest.raises(CanonicalArtifactError) as raised:
        _build(payloads=[_payload(pages=1)], units=[])
    assert raised.value.code == "canonical_pdf_source_atom_accounting_incomplete"
    assert "pdf_nonempty_zero_nodes" in raised.value.subject


def test_proved_empty_pdf_is_explicit_and_valid() -> None:
    artifact = _build(payloads=[_payload(pages=0, empty=True)], units=[])
    assert artifact["nodes"] == []
    assert any(
        issue["summary"] == "EMPTY_SOURCE_DOCUMENT"
        for issue in artifact["issues"]
    )
    receipt = artifact["containers"][0]["metadata"]["pdf_completeness"]
    assert receipt["empty_source_document"] is True
    assert receipt["source_atom_accounting_percent"] == 100.0
    assert validate_canonical_artifact(artifact)["passed"] is True


def test_source_atom_accounting_and_table_duplicate_suppression() -> None:
    units = [
        _unit("table-1", page=1, text="A B 1 2"),
        _unit("text-1", page=1, text="After table"),
        {
            "unit_ref": "visual-1",
            "pdf_unit_type": "pdf_visual_page_unit",
            "source_location": {"page": 1},
            "coverage": {"selected_source_refs": ["visual-atom-1"]},
        },
    ]
    projection = {
        "projection_status": "ready",
        "table_projection_id": "projection-1",
        "source_unit_ref": "table-1",
        "row_count": 2,
        "column_count": 2,
        "header_model": {"header_row_refs": ["row-1"]},
        "cells": [
            {"row_ordinal": 1, "column_ordinal": 1, "normalized_private_value_path": "v1"},
            {"row_ordinal": 1, "column_ordinal": 2, "normalized_private_value_path": "v2"},
            {"row_ordinal": 2, "column_ordinal": 1, "normalized_private_value_path": "v3"},
            {"row_ordinal": 2, "column_ordinal": 2, "normalized_private_value_path": "v4"},
        ],
        "private_values": [
            {"value_path_ref": "v1", "normalized_value": "A"},
            {"value_path_ref": "v2", "normalized_value": "B"},
            {"value_path_ref": "v3", "normalized_value": "1"},
            {"value_path_ref": "v4", "normalized_value": "2"},
        ],
    }
    artifact = _build(units=units, projections=[projection])
    receipt = artifact["containers"][0]["metadata"]["pdf_completeness"]
    assert receipt["source_atom_accounting_percent"] == 100.0
    assert receipt["unresolved_source_atoms_total"] == 0
    assert receipt["ready_table_projections_total"] == 1
    assert receipt["represented_ready_table_projections_total"] == 1
    assert receipt["duplicate_table_text_reduction_percent"] == 100.0
    assert [node["node_type"] for node in artifact["nodes"]] == ["TABLE", "TEXT"]
    assert receipt["categories"]["EVIDENCE_ONLY"] == 1


def test_failed_zero_node_candidate_preserves_active_pointer(tmp_path: Path) -> None:
    store, reader, context, document_id, active = _publish(tmp_path)
    before = reader.read_active(document_id, context)["canonical_root_hash"]
    forged = copy.deepcopy(active)
    forged["nodes"] = []
    forged["containers"][0]["metadata"]["pdf_completeness"][
        "logical_node_count"
    ] = 0
    validation = validate_canonical_artifact(forged)
    assert "canonical_pdf_nonempty_zero_nodes" in validation["error_codes"]
    with pytest.raises(ArtifactStoreError) as raised:
        CanonicalArtifactStoreFactory(store=store).create().put_candidate(
            artifact=forged,
            context=context,
            retention_policy=build_retention_policy(mode="api_smoke"),
            compare_receipt=None,
        )
    assert raised.value.code == "artifact_blocked"
    assert reader.read_active(document_id, context)["canonical_root_hash"] == before


def test_reader_roundtrip_and_generic_projection_use_only_canonical(tmp_path: Path) -> None:
    store, reader, context, document_id, _ = _publish(tmp_path)
    result = LocalPdfCompactResearchCanonicalAdapterFactory(
        store=store,
        enabled=True,
    ).create().read_active(document_id=document_id, context=context)
    assert result.compatibility_status == "CANONICAL_OK"
    assert result.output is not None
    projection = result.output["generic_projection"]
    assert projection.startswith("[DOCUMENT]\n[PAGE] 1\n[TEXT]\nVisible text\n")
    assert result.output["generic_projection_sha256"] == hashlib.sha256(
        projection.encode("utf-8")
    ).hexdigest()
    source = inspect.getsource(_render_generic_pdf_projection)
    for forbidden in (
        "ArtifactStore",
        "read_payload",
        "private_normalized",
        "source_payload",
        "raw_pdf",
        "provider_payload",
    ):
        assert forbidden not in source
    resolved = reader.read_active(document_id, context)
    assert _render_generic_pdf_projection(resolved) == projection


def test_three_identical_pdf_builds_have_one_root_hash() -> None:
    roots = {
        _build(normalizer_version="canonical-doc32-deterministic-v1")[
            "canonical_root_hash"
        ]
        for _ in range(3)
    }
    assert len(roots) == 1


def test_cross_tenant_reader_is_fail_closed(tmp_path: Path) -> None:
    _, reader, context, document_id, _ = _publish(tmp_path)
    other = ArtifactAccessContext(
        user_id="other-user",
        normalization_run_id=context.normalization_run_id,
        case_id=context.case_id,
        workspace_model_id=context.workspace_model_id,
        allow_private=True,
        require_source_available=True,
    )
    with pytest.raises(ArtifactStoreError) as raised:
        reader.read_active(document_id, other)
    assert raised.value.code in {"artifact_access_denied", "canonical_version_not_active"}


def test_doc32_closed_world_image_pins_pdf_runtime_and_entrypoint() -> None:
    dockerfile = (SERVICE_ROOT / "Dockerfile.doc32").read_text(encoding="utf-8")
    assert "pypdf==6.7.5" in dockerfile
    assert "pdfplumber==0.11.10" in dockerfile
    assert "PyMuPDF==1.26.5" in dockerfile
    assert "pdfminer.six==20260107" in dockerfile
    assert "Pillow==12.3.0" in dockerfile
    assert "pypdfium2==5.11.0" in dockerfile
    assert "COPY broker_reports_gate1 /opt/broker-reports-doc32/broker_reports_gate1" in dockerfile
    assert "doc32_pdf_roundtrip_repair.py" in dockerfile
    assert "../" not in dockerfile


def test_doc32_command_uses_only_owned_factory_routes_and_safe_projection_output() -> None:
    command = (SERVICE_ROOT / "scripts" / "doc32_pdf_roundtrip_repair.py").read_text(
        encoding="utf-8"
    )
    for required in (
        "Gate1Normalizer().normalize(",
        "persist_gate1_result(",
        "CanonicalReaderFactory(",
        "LocalPdfCompactResearchCanonicalAdapterFactory(",
        "CanonicalWave2ShadowFactory(",
    ):
        assert required in command
    for forbidden in (
        "generic_projection\": projection",
        "requests.post(",
        "openai.",
        "anthropic.",
    ):
        assert forbidden not in command


def test_pdf_normalize_persist_reopen_reader_and_projection(tmp_path: Path) -> None:
    normalized = Gate1Normalizer().normalize(
        [
            FileInput.from_bytes(
                private_ref="doc32-synthetic-private-ref",
                filename="doc32-synthetic.pdf",
                content=_synthetic_pdf_bytes(),
                mime_type="application/pdf",
            )
        ],
        entrypoint="doc32_regression_test",
        input_context={
            "canonical_gate2_write_enabled": True,
            "canonical_gate2_compare_enabled": True,
            "canonical_gate2_read_enabled": False,
            "normalizer_version": "canonical-doc32-e2e-test-v1",
        },
    )
    document = normalized.package["document_inventory"]["documents"][0]
    context = ArtifactAccessContext(
        user_id="doc32-user",
        normalization_run_id=normalized.package["normalization_run"]["run_id"],
        case_id="doc32-case",
        workspace_model_id="doc32-workspace",
        allow_private=True,
        require_source_available=True,
    )
    store = _store(tmp_path)
    manifest = persist_gate1_result(
        store=store,
        result=normalized,
        context=context,
        retention_policy=build_retention_policy(mode="api_smoke"),
        source_file_refs=[
            {
                "provider": "doc32-test",
                "openwebui_file_id": "doc32-synthetic-source",
                "file_hash_sha256": document["sha256"],
                "content_type": "application/pdf",
                "size_bytes": document["size_bytes"],
            }
        ],
    )
    canonical_refs = manifest.artifact_refs_by_type[
        "broker_reports_canonical_artifact_v1"
    ]
    assert len(canonical_refs) == 1
    version = store.get_canonical_version_by_manifest(
        context=context,
        manifest_ref=canonical_refs[0],
    )
    CanonicalReaderFactory(store=store, read_enabled=True).create().activate(
        canonical_version_id=version.canonical_version_id,
        expected_previous_version_id=None,
        context=context,
        actor="doc32-test",
        reason="durable PDF regression",
    )

    reopened = _store(tmp_path)
    envelope = CanonicalReaderFactory(
        store=reopened, read_enabled=True
    ).create().read_active_envelope(document["document_id"], context)
    node_types = [item["node_type"] for item in envelope.artifact["nodes"]]
    assert node_types.count("TEXT") == 2
    assert node_types.count("PAGE_BREAK") == 1
    assert envelope.component_count > 0
    projection = LocalPdfCompactResearchCanonicalAdapterFactory(
        store=reopened,
        enabled=True,
    ).create().read_active(document_id=document["document_id"], context=context)
    assert projection.compatibility_status == "CANONICAL_OK"
    assert projection.output is not None
    assert projection.output["generic_projection"].count("[PAGE]") == 2
    assert "DOC32 durable page 1" in projection.output["generic_projection"]
    assert "DOC32 durable page 2" in projection.output["generic_projection"]


def test_pdf_node_model_conflict_and_ambiguity_survive_roundtrip(tmp_path: Path) -> None:
    heading = _unit("heading-1", page=1, text="Heading")
    heading["canonical_node_type"] = "HEADING"
    note = _unit("note-1", page=1, text="Note")
    note["canonical_node_type"] = "NOTE"
    list_unit = _unit("list-1", page=2, text="First item")
    list_unit["canonical_node_type"] = "LIST"
    list_unit["list_items"] = [{"text": "First item", "level": 0}]
    conflict = _unit("conflict-1", page=2, text="")
    conflict["atom_status"] = "CONFLICT_EVIDENCE"
    ambiguity = _unit("ambiguity-1", page=2, text="")
    ambiguity["atom_status"] = "AMBIGUOUS_EVIDENCE"
    artifact = _build(
        payloads=[_payload(pages=2)],
        units=[heading, note, list_unit, conflict, ambiguity],
    )
    _, _, context, document_id, _ = _publish(tmp_path, artifact)
    reopened = _store(tmp_path)
    resolved = CanonicalReaderFactory(
        store=reopened, read_enabled=True
    ).create().read_active(document_id, context)
    node_types = {item["node_type"] for item in resolved["nodes"]}
    assert {
        "HEADING",
        "NOTE",
        "LIST",
        "PAGE_BREAK",
        "CONFLICT",
        "AMBIGUITY",
    }.issubset(node_types)
    receipt = resolved["containers"][0]["metadata"]["pdf_completeness"]
    assert receipt["categories"]["CONFLICT"] == 1
    assert receipt["categories"]["AMBIGUITY"] == 1
    assert receipt["unresolved_source_atoms_total"] == 0


def test_purged_candidate_number_is_never_reused(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first_context = _context("doc32-purged-run-1")
    document_id = "doc32-purged-document"
    first_source = _source_record(first_context, document_id)
    first_source.artifact_id = "doc32-purged-source-1"
    store.put_record(first_source)
    first = store.reserve_canonical_version(
        context=first_context,
        document_id=document_id,
        source_artifact_ref=first_source.artifact_id,
        schema_version="broker_reports_canonical_artifact_v1",
        normalizer_version="canonical-doc32-test-v1",
        source_sha256="1" * 64,
        canonical_root_sha256="2" * 64,
        retention_class="SUPERSEDED_CANONICAL",
    )
    store.abort_canonical_candidate(
        context=first_context,
        canonical_version_id=first.canonical_version_id,
        component_artifact_ids=[],
    )

    second_context = _context("doc32-purged-run-2")
    second_source = _source_record(second_context, document_id)
    second_source.artifact_id = "doc32-purged-source-2"
    store.put_record(second_source)
    second = store.reserve_canonical_version(
        context=second_context,
        document_id=document_id,
        source_artifact_ref=second_source.artifact_id,
        schema_version="broker_reports_canonical_artifact_v1",
        normalizer_version="canonical-doc32-test-v1",
        source_sha256="3" * 64,
        canonical_root_sha256="4" * 64,
        retention_class="SUPERSEDED_CANONICAL",
    )

    assert first.canonical_version_number == 1
    assert second.canonical_version_number == 2
    assert second.previous_version_ref is None
