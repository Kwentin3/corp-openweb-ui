from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path

import pytest

from broker_reports_gate1.artifact_models import ArtifactStoreError
from broker_reports_gate1.pdf_document_ai import (
    PdfDocumentExtraction,
    PdfDocumentImageRef,
)
from broker_reports_gate1.mistral_pdf_document_ai import (
    MISTRAL_OCR_ADAPTER_ID,
    MISTRAL_OCR_MODEL,
    MISTRAL_OCR_PROVIDER_ID,
    MISTRAL_OCR_REQUEST_CONTRACT_VERSION,
    MISTRAL_OCR_REQUEST_PARAMETERS,
)
from broker_reports_gate1.pdf_document_ai_qualification import (
    PDF_DOCUMENT_AI_QUALIFICATION_FIXTURES,
    PdfDocumentAiQualificationError,
)
from openwebui_actions.broker_reports_gate1_pipe import (
    PDF_DOCUMENT_AI_QUALIFICATION_COMMAND,
    Pipe,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
HEAD = "a" * 40


class _QualificationExtractor:
    def extract(self, pdf_bytes, source_context):
        fidelity_sha256 = PDF_DOCUMENT_AI_QUALIFICATION_FIXTURES[1][2]
        image_count = (
            8 if hashlib.sha256(pdf_bytes).hexdigest() == fidelity_sha256 else 0
        )
        image_refs = []
        markdown_text = (
            f"# Qualified public fixture\n\npages={source_context.preflight_page_count}\n"
        )
        for index in range(image_count):
            content = f"qualification-image-{index}".encode("ascii")
            target = f"img-{index}.jpeg"
            markdown_text += f"\n![image]({target})"
            image_refs.append(
                PdfDocumentImageRef(
                    page_number=index + 1,
                    markdown_target=target,
                    local_ref=f"pdfimg_qualification_{index}",
                    sha256=hashlib.sha256(content).hexdigest(),
                    media_type="image/jpeg",
                    content_bytes=content,
                )
            )
        markdown = markdown_text.encode("utf-8")
        page_digest = hashlib.sha256(markdown).hexdigest()
        return PdfDocumentExtraction(
            source_pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
            page_numbers=tuple(range(1, source_context.preflight_page_count + 1)),
            markdown_bytes=markdown,
            markdown_sha256=hashlib.sha256(markdown).hexdigest(),
            image_refs=tuple(image_refs),
            provider_id=MISTRAL_OCR_PROVIDER_ID,
            requested_model_id=MISTRAL_OCR_MODEL,
            model_id=MISTRAL_OCR_MODEL,
            adapter_id=MISTRAL_OCR_ADAPTER_ID,
            request_contract_version=MISTRAL_OCR_REQUEST_CONTRACT_VERSION,
            request_parameters=MISTRAL_OCR_REQUEST_PARAMETERS,
            request_parameters_sha256=hashlib.sha256(
                json.dumps(
                    dict(MISTRAL_OCR_REQUEST_PARAMETERS),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest(),
            page_markdown_sha256=tuple(
                page_digest for _ in range(source_context.preflight_page_count)
            ),
            qualification_status="qualification_attempt",
            usage_page_count=source_context.preflight_page_count,
        )


class _OuterQualificationRequest:
    async def json(self) -> dict:
        return _body()


def _body() -> dict:
    files = []
    for fixture_id, repository_path, _expected_sha256 in (
        PDF_DOCUMENT_AI_QUALIFICATION_FIXTURES
    ):
        files.append(
            {
                "type": "file",
                "file": {
                    "id": f"qualification-{fixture_id}",
                    "filename": f"{fixture_id}.pdf",
                    "mime_type": "application/pdf",
                    "content_bytes": (REPO_ROOT / repository_path).read_bytes(),
                },
            }
        )
    return {
        "messages": [
            {
                "role": "user",
                "content": PDF_DOCUMENT_AI_QUALIFICATION_COMMAND,
                "files": files,
            }
        ]
    }


def _pipe(tmp_path: Path) -> Pipe:
    pipe = Pipe()
    pipe.valves.artifact_store_path = str(tmp_path / "artifacts.sqlite3")
    pipe.valves.artifact_payload_root = str(tmp_path / "payloads")
    pipe.valves.pdf_document_ai_qualification_repository_head = HEAD
    return pipe


def test_exact_admin_command_runs_two_real_pipe_slices_then_purges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import broker_reports_gate1.normalizer as normalizer_module

    monkeypatch.setattr(
        normalizer_module.PdfDocumentExtractorFactory,
        "create",
        lambda **_kwargs: _QualificationExtractor(),
    )
    private_review_events = []

    async def event_call(event):
        private_review_events.append(event)
        return True

    content = asyncio.run(
        _pipe(tmp_path).pipe(
            _body(),
            __user__={"id": "qualification-admin", "role": "admin"},
            __metadata__={
                "chat_id": "qualification-chat",
                "model_id": "broker_reports_gate1_pipe",
            },
            __event_call__=event_call,
        )
    )
    receipt = json.loads(content)

    assert receipt["status"] == "succeeded", json.dumps(receipt, sort_keys=True)
    assert receipt["provider_call_slots_consumed_total"] == 2
    assert [item["status"] for item in receipt["outcomes"]] == [
        "succeeded",
        "succeeded",
    ]
    assert len(
        list(
            (tmp_path / "pdf-document-ai-qualification-claims").glob(
                "*.consumed.safe.json"
            )
        )
    ) == 2
    assert private_review_events
    assert all(item["type"] == "confirmation" for item in private_review_events)
    source_messages = [
        item["data"]["message"]
        for item in private_review_events
        if item["data"]["title"].endswith(" source")
    ]
    assert len(source_messages) == 2
    assert "qualification-drivewealth" in source_messages[0]
    assert "qualification-fidelity" in source_messages[1]
    assert "Qualified public fixture" not in content
    assert all(item["review"]["status"] == "passed" for item in receipt["outcomes"])


def test_internal_task_body_cannot_consume_restored_qualification_then_primary_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import broker_reports_gate1.normalizer as normalizer_module

    extraction_calls = 0

    class CountingQualificationExtractor(_QualificationExtractor):
        def extract(self, pdf_bytes, source_context):
            nonlocal extraction_calls
            extraction_calls += 1
            return super().extract(pdf_bytes, source_context)

    monkeypatch.setattr(
        normalizer_module.PdfDocumentExtractorFactory,
        "create",
        lambda **_kwargs: CountingQualificationExtractor(),
    )
    pipe = _pipe(tmp_path)
    files = _body()["messages"][0]["files"]

    internal_content = asyncio.run(
        pipe.pipe(
            {"messages": [{"role": "user", "content": "Generate search queries"}]},
            __user__={"id": "qualification-admin", "role": "admin"},
            __request__=_OuterQualificationRequest(),
            __metadata__={
                "chat_id": "qualification-chat",
                "model_id": "broker_reports_gate1_pipe",
                "files": files,
            },
        )
    )

    assert (
        internal_content
        == "PDF Document AI qualification is unavailable for internal tasks."
    )
    assert extraction_calls == 0
    assert not (tmp_path / "pdf-document-ai-qualification-claims").exists()

    async def event_call(_event):
        return True

    content = asyncio.run(
        pipe.pipe(
            _body(),
            __user__={"id": "qualification-admin", "role": "admin"},
            __request__=_OuterQualificationRequest(),
            __metadata__={
                "chat_id": "qualification-chat",
                "model_id": "broker_reports_gate1_pipe",
            },
            __event_call__=event_call,
        )
    )
    receipt = json.loads(content)

    assert receipt["status"] == "succeeded"
    assert receipt["provider_call_slots_consumed_total"] == 2
    assert extraction_calls == 2
    assert len(
        list(
            (tmp_path / "pdf-document-ai-qualification-claims").glob(
                "*.consumed.safe.json"
            )
        )
    ) == 2


def test_qualification_command_rejects_non_admin_before_any_slot(
    tmp_path: Path,
) -> None:
    with pytest.raises(PdfDocumentAiQualificationError) as caught:
        asyncio.run(
            _pipe(tmp_path).pipe(
                _body(),
                __user__={"id": "ordinary-user", "role": "user"},
                __metadata__={
                    "chat_id": "qualification-chat",
                    "model_id": "broker_reports_gate1_pipe",
                },
            )
        )

    assert caught.value.code == "pdf_document_ai_qualification_admin_required"
    assert not (tmp_path / "pdf-document-ai-qualification-claims").exists()


def test_qualification_rejects_unverified_scope_before_any_slot(
    tmp_path: Path,
) -> None:
    with pytest.raises(ArtifactStoreError) as caught:
        asyncio.run(
            _pipe(tmp_path).pipe(
                _body(),
                __user__={"id": "qualification-admin", "role": "admin"},
            )
        )

    assert caught.value.code == "artifact_scope_unverified"
    assert not (tmp_path / "pdf-document-ai-qualification-claims").exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits are not Windows ACLs")
def test_qualification_rejects_unavailable_artifact_store_before_any_slot(
    tmp_path: Path,
) -> None:
    payload_root = tmp_path / "payloads"
    payload_root.mkdir(mode=0o755)
    payload_root.chmod(0o755)

    with pytest.raises(ArtifactStoreError) as caught:
        asyncio.run(
            _pipe(tmp_path).pipe(
                _body(),
                __user__={"id": "qualification-admin", "role": "admin"},
                __metadata__={
                    "chat_id": "qualification-chat",
                    "model_id": "broker_reports_gate1_pipe",
                },
            )
        )

    assert caught.value.code == "artifact_store_unavailable"
    assert not (tmp_path / "pdf-document-ai-qualification-claims").exists()
