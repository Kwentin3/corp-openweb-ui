from __future__ import annotations

import asyncio
import hashlib
import io
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from zipfile import ZipFile

import pytest

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactResolver,
    ArtifactStoreConfig,
    ArtifactStoreError,
    ArtifactStoreFactory,
    FullSourceArtifactFactory,
    Gate1BoundedGraphConfig,
    Gate1BoundedGraphFactory,
    PdfDocumentExtraction,
    PdfDocumentImageRef,
)
from broker_reports_gate1.artifact_models import RetentionPolicy
from openwebui_actions.broker_reports_gate1_pipe import (
    FULL_SOURCE_PROJECTION_SCHEMA_VERSION,
    FULL_SOURCE_ZIP_FILENAME,
    Pipe,
)


def _full_source_graph(tmp_path: Path):
    run_id = "full-source-delivery-run"
    context = ArtifactAccessContext(
        user_id="user-a",
        normalization_run_id=run_id,
        case_id="case-a",
        chat_id="chat-a",
        workspace_model_id="broker_reports_gate1_pipe",
        allow_private=True,
    )
    retention = RetentionPolicy(
        mode="synthetic_dev",
        ttl_seconds=None,
        expires_at=None,
        explicit=True,
    )
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "artifacts.sqlite3",
            payload_root=tmp_path / "payloads",
        )
    ).create()
    source_bytes = (b"%PDF-source-a", b"%PDF-source-b")
    graph = Gate1BoundedGraphFactory(
        Gate1BoundedGraphConfig(
            store=store,
            context=context,
            retention_policy=retention,
            source_file_refs=tuple(
                {
                    "provider": "openwebui",
                    "openwebui_file_id": f"native-source-{ordinal}",
                    "filename": "source.pdf",
                    "content_type": "application/pdf",
                    "size_bytes": len(content),
                    "source_deleted": False,
                }
                for ordinal, content in enumerate(source_bytes, start=1)
            ),
        )
    ).create(normalization_run_id=run_id)
    documents = []
    for ordinal, content in enumerate(source_bytes, start=1):
        document_id = f"document-{ordinal}"
        document = {
            "document_id": document_id,
            "root_input_ordinal": ordinal,
            "source_kind": "openwebui_pipe",
            "container_format": "pdf",
            "declared_mime_type": "application/pdf",
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
        }
        graph.register_document(document)
        documents.append(document)

    expected = []
    parameter_sha256 = hashlib.sha256(b"{}").hexdigest()
    for ordinal, document in enumerate(documents, start=1):
        markdown = f"# Документ {ordinal}\n\n![график](img.png)".encode("utf-8")
        image_bytes = f"image-{ordinal}".encode("ascii")
        image = PdfDocumentImageRef(
            page_number=1,
            markdown_target="img.png",
            local_ref=f"pdfimg_delivery_{ordinal}",
            sha256=hashlib.sha256(image_bytes).hexdigest(),
            media_type="image/png",
            content_bytes=image_bytes,
        )
        extraction = PdfDocumentExtraction(
            source_pdf_sha256=document["sha256"],
            page_numbers=(1,),
            markdown_bytes=markdown,
            markdown_sha256=hashlib.sha256(markdown).hexdigest(),
            image_refs=(image,),
            provider_id="fixture-provider",
            requested_model_id="fixture-model",
            model_id="fixture-model",
            adapter_id="fixture-adapter",
            request_contract_version="fixture-request-v1",
            request_parameters=(),
            request_parameters_sha256=parameter_sha256,
            page_markdown_sha256=(hashlib.sha256(markdown).hexdigest(),),
            qualification_status="offline_fixture",
            usage_page_count=1,
        )
        full_source = (
            FullSourceArtifactFactory()
            .create()
            .build_document_extraction(
                normalization_run_id=run_id,
                document_id=document["document_id"],
                profile_id=f"profile-{ordinal}",
                extraction=extraction,
            )
        )
        graph.publish_pdf_full_source_atomic(
            result=full_source,
            image_refs=(image,),
        )
        expected.append((markdown, image_bytes))
    manifest = SimpleNamespace(
        private_source_payload_refs=list(
            graph.refs_by_type["private_normalized_source_payload_v0"]
        ),
        private_source_unit_refs=list(
            graph.refs_by_type["private_normalized_source_unit_v0"]
        ),
    )
    return store, context, manifest, expected


def _install_openwebui_file_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    corrupt_upload: bool = False,
):
    rows: dict[str, SimpleNamespace] = {}
    calls = {"upload": 0, "insert": 0, "delete": 0}

    class FileForm:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Files:
        @staticmethod
        async def get_file_by_id(file_id):
            return rows.get(file_id)

        @staticmethod
        async def insert_new_file(user_id, form):
            calls["insert"] += 1
            row = SimpleNamespace(**form.__dict__, user_id=user_id)
            rows[form.id] = row
            return row

    class Storage:
        @staticmethod
        def upload_file(stream, name, headers):
            calls["upload"] += 1
            calls["headers"] = headers
            content = stream.read()
            stored = content + b"corrupt" if corrupt_upload else content
            path = tmp_path / name
            path.write_bytes(stored)
            return stored, str(path)

        @staticmethod
        def get_file(path):
            return path

        @staticmethod
        def delete_file(path):
            calls["delete"] += 1
            Path(path).unlink(missing_ok=True)

    modules = {
        "open_webui": ModuleType("open_webui"),
        "open_webui.models": ModuleType("open_webui.models"),
        "open_webui.models.files": ModuleType("open_webui.models.files"),
        "open_webui.storage": ModuleType("open_webui.storage"),
        "open_webui.storage.provider": ModuleType("open_webui.storage.provider"),
    }
    modules["open_webui.models.files"].FileForm = FileForm
    modules["open_webui.models.files"].Files = Files
    modules["open_webui.storage.provider"].Storage = Storage
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    return rows, calls


def test_full_source_zip_preserves_exact_markdown_images_and_native_ids(
    tmp_path: Path,
) -> None:
    store, context, artifact_manifest, expected = _full_source_graph(tmp_path)

    projection = Pipe._build_pdf_full_source_zip(
        store=store,
        context=context,
        artifact_manifest=artifact_manifest,
    )

    assert projection is not None
    with ZipFile(io.BytesIO(projection["content"])) as archive:
        assert archive.read("documents/001/full-source.md") == expected[0][0]
        assert archive.read("documents/001/img.png") == expected[0][1]
        assert archive.read("documents/002/full-source.md") == expected[1][0]
        assert archive.read("documents/002/img.png") == expected[1][1]
        manifest_bytes = archive.read("manifest.json")
        manifest = json.loads(manifest_bytes)
    assert manifest["authority"] == "ArtifactStore"
    assert manifest["representation_only"] is True
    assert [item["source_openwebui_file_id"] for item in manifest["documents"]] == [
        "native-source-1",
        "native-source-2",
    ]
    assert projection["manifest_sha256"] == hashlib.sha256(manifest_bytes).hexdigest()

    foreign_context = ArtifactAccessContext(
        user_id="user-b",
        normalization_run_id=context.normalization_run_id,
        case_id=context.case_id,
        chat_id=context.chat_id,
        workspace_model_id=context.workspace_model_id,
        allow_private=True,
    )
    with pytest.raises(ArtifactStoreError) as denied:
        Pipe._build_pdf_full_source_zip(
            store=store,
            context=foreign_context,
            artifact_manifest=artifact_manifest,
        )
    assert denied.value.code == "artifact_access_denied"


def test_full_source_delivery_is_owner_scoped_reused_and_chat_safe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store, context, artifact_manifest, expected = _full_source_graph(tmp_path)
    rows, calls = _install_openwebui_file_boundary(monkeypatch, tmp_path / "files")
    (tmp_path / "files").mkdir()
    user = {"id": "user-a", "email": "user@example.test", "name": "User"}

    first = asyncio.run(
        Pipe._publish_pdf_full_source_delivery(
            store=store,
            context=context,
            artifact_manifest=artifact_manifest,
            user=user,
        )
    )
    repeated = asyncio.run(
        Pipe._publish_pdf_full_source_delivery(
            store=store,
            context=context,
            artifact_manifest=artifact_manifest,
            user=user,
        )
    )

    assert first == repeated
    assert first is not None
    assert calls["upload"] == 1
    assert calls["insert"] == 1
    assert calls["headers"]["OpenWebUI-User-Id"] == "user-a"
    row = rows[first["file_id"]]
    assert row.user_id == "user-a"
    assert row.filename == FULL_SOURCE_ZIP_FILENAME
    assert row.meta["content_type"] == "application/zip"
    assert row.meta["data"]["projection_only"] is True
    assert row.meta["data"]["artifact_store_authority"] is True
    assert row.meta["data"]["purpose"] == FULL_SOURCE_PROJECTION_SCHEMA_VERSION
    assert Path(row.path).read_bytes()
    chat_line = Pipe._full_source_download_line(first)
    assert chat_line == (
        f"Full Source: [скачать {FULL_SOURCE_ZIP_FILENAME}]({first['url']})"
    )
    assert expected[0][0].decode("utf-8") not in chat_line
    assert expected[1][0].decode("utf-8") not in chat_line
    assert "image-1" not in chat_line
    assert "image-2" not in chat_line


def test_full_source_delivery_uses_native_openwebui_file_event() -> None:
    delivery = {
        "file_id": "file-full-source",
        "filename": FULL_SOURCE_ZIP_FILENAME,
        "url": "/api/v1/files/file-full-source/content?attachment=true",
        "content_type": "application/zip",
    }
    events: list[dict] = []

    async def emitter(event: dict) -> None:
        events.append(event)

    asyncio.run(Pipe._emit_full_source_delivery(emitter, delivery))

    assert events == [
        {
            "type": "files",
            "data": {
                "files": [
                    {
                        "type": "file",
                        "id": "file-full-source",
                        "name": FULL_SOURCE_ZIP_FILENAME,
                        "url": delivery["url"],
                        "content_type": "application/zip",
                    }
                ]
            },
        }
    ]


def test_full_source_upload_hash_mismatch_is_deleted_and_not_published(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store, context, artifact_manifest, _expected = _full_source_graph(tmp_path)
    file_root = tmp_path / "files"
    file_root.mkdir()
    rows, calls = _install_openwebui_file_boundary(
        monkeypatch,
        file_root,
        corrupt_upload=True,
    )

    with pytest.raises(ArtifactStoreError) as failed:
        asyncio.run(
            Pipe._publish_pdf_full_source_delivery(
                store=store,
                context=context,
                artifact_manifest=artifact_manifest,
                user={"id": "user-a"},
            )
        )

    assert failed.value.code == "private_file_projection_upload_hash_mismatch"
    assert calls == {"upload": 1, "insert": 0, "delete": 1, "headers": calls["headers"]}
    assert rows == {}
    assert list(file_root.iterdir()) == []
    # The authoritative ArtifactStore graph remains owner-readable after delivery failure.
    assert (
        ArtifactResolver(store).resolve(
            artifact_manifest.private_source_payload_refs[0], context
        )["payload"]["container_format"]
        == "pdf"
    )
