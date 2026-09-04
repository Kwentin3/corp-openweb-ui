from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from broker_reports_gate1.pdf_document_ai import (
    PdfDocumentExtraction,
    PdfDocumentImageRef,
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
        return PdfDocumentExtraction(
            source_pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
            page_numbers=tuple(range(1, source_context.preflight_page_count + 1)),
            markdown_bytes=markdown,
            markdown_sha256=hashlib.sha256(markdown).hexdigest(),
            image_refs=tuple(image_refs),
            provider_id="qualification-test-provider",
            model_id="qualification-test-model",
            adapter_id="qualification-test-adapter",
            qualification_status="qualification_attempt",
            usage_page_count=source_context.preflight_page_count,
        )


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
    content = asyncio.run(
        _pipe(tmp_path).pipe(
            _body(),
            __user__={"id": "qualification-admin", "role": "admin"},
            __metadata__={
                "chat_id": "qualification-chat",
                "model_id": "broker_reports_gate1_pipe",
            },
        )
    )
    receipt = json.loads(content)

    assert receipt["status"] == "succeeded"
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
