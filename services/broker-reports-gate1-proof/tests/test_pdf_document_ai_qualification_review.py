from __future__ import annotations

import asyncio
import hashlib
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from broker_reports_gate1.artifact_models import (
    ArtifactAccessContext,
    ArtifactRecord,
    ArtifactStoreError,
    build_private_binary_payload,
)
from broker_reports_gate1.artifact_retention import build_retention_policy
from broker_reports_gate1.artifact_store import ArtifactStoreConfig, ArtifactStoreFactory
from broker_reports_gate1.pdf_document_ai_qualification_review import (
    PDF_DOCUMENT_AI_REVIEW_CHECKS,
    PdfDocumentAiQualificationReviewError,
    PdfDocumentAiQualificationReviewFactory,
    PdfDocumentAiQualificationReviewVerdict,
)


NOW = datetime.now(timezone.utc)


def _lease(tmp_path: Path):
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "artifacts.sqlite3",
            payload_root=tmp_path / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        user_id="reviewer",
        case_id="qualification-case",
        chat_id="qualification-chat",
        workspace_model_id="broker_reports_gate1_pipe",
        normalization_run_id="qualification-run",
        allow_private=True,
        require_source_available=True,
    )
    retention = build_retention_policy(
        mode="expires_after_ttl", ttl_seconds=900, now=NOW
    )
    image = b"private-image"
    image_sha = hashlib.sha256(image).hexdigest()
    markdown = "# Live result\n\n| A | B |\n|---|---|\n| 1 | 2 |"
    markdown_sha = hashlib.sha256(markdown.encode()).hexdigest()
    common = {
        "case_id": context.case_id,
        "chat_id": context.chat_id,
        "user_id": context.user_id,
        "workspace_model_id": context.workspace_model_id,
        "normalization_run_id": context.normalization_run_id,
        "document_id": "doc-live",
        "source_file_ref": {"openwebui_file_id": "public-fixture"},
        "visibility": "private_case",
        "storage_backend": "project_artifact_payload",
        "retention_policy": retention,
        "access_policy": {"requires_user_id": True},
        "validation_status": "validated",
        "lifecycle_status": "private_ready",
    }
    store.put_records_atomic(
        [
            ArtifactRecord(
                artifact_id="art_full_source",
                artifact_type="private_normalized_source_payload_v0",
                payload={
                    "normalized_projection": {"text": markdown},
                    "document_ai_markdown_sha256": markdown_sha,
                    "document_ai_image_refs": [
                        {
                            "page_number": 1,
                            "markdown_target": "img-0.jpeg",
                            "local_ref": "art_image",
                            "sha256": image_sha,
                        }
                    ],
                },
                **common,
            ),
            ArtifactRecord(
                artifact_id="art_image",
                artifact_type="private_binary_artifact_v1",
                payload=build_private_binary_payload(
                    content=image, media_type="image/jpeg"
                ),
                **common,
            ),
        ]
    )
    lease = PdfDocumentAiQualificationReviewFactory.create(
        store=store,
        context=context,
        full_source_refs=["art_full_source"],
        repository_head="a" * 40,
        fixture_id="fidelity",
        expected_image_count=1,
        expires_at=NOW + timedelta(seconds=900),
    )
    return store, context, lease


async def _passing_reviewer(view):
    assert "Live result" in view.markdown
    assert view.images[0][1] == b"private-image"
    return PdfDocumentAiQualificationReviewVerdict(
        live_output_digest=view.live_output_digest,
        checks={key: True for key in PDF_DOCUMENT_AI_REVIEW_CHECKS},
    )


def test_same_user_review_is_digest_bound_and_guarantees_purge(tmp_path: Path) -> None:
    store, context, lease = _lease(tmp_path)
    receipt = asyncio.run(
        lease.review(actor_context=context, reviewer=_passing_reviewer, now=NOW)
    )
    assert receipt["status"] == "passed"
    assert receipt["checks_passed"] == len(PDF_DOCUMENT_AI_REVIEW_CHECKS)
    assert receipt["contains_private_payload"] is False
    with pytest.raises(ArtifactStoreError) as purged:
        store.read_payload(store.get_record_unchecked("art_full_source"))
    assert purged.value.code == "artifact_purged"


def test_cross_user_review_is_denied_without_destroying_owner_graph(tmp_path: Path) -> None:
    store, context, lease = _lease(tmp_path)
    with pytest.raises(ArtifactStoreError) as denied:
        asyncio.run(
            lease.review(
                actor_context=replace(context, user_id="other-user"),
                reviewer=_passing_reviewer,
                now=NOW,
            )
        )
    assert denied.value.code == "artifact_access_denied"
    assert store.read_payload(store.get_record_unchecked("art_full_source"))[
        "normalized_projection"
    ]["text"]


def test_digest_mismatch_is_terminal_and_purges(tmp_path: Path) -> None:
    store, context, lease = _lease(tmp_path)

    async def forged(_view):
        return PdfDocumentAiQualificationReviewVerdict(
            live_output_digest="0" * 64,
            checks={key: True for key in PDF_DOCUMENT_AI_REVIEW_CHECKS},
        )

    with pytest.raises(PdfDocumentAiQualificationReviewError) as caught:
        asyncio.run(lease.review(actor_context=context, reviewer=forged, now=NOW))
    assert caught.value.code == "pdf_document_ai_review_digest_mismatch"
    assert store.get_record_unchecked("art_full_source").purge_status == "purged"


def test_expired_lease_is_terminal_and_purges(tmp_path: Path) -> None:
    store, context, lease = _lease(tmp_path)
    with pytest.raises(PdfDocumentAiQualificationReviewError) as caught:
        asyncio.run(
            lease.review(
                actor_context=context,
                reviewer=_passing_reviewer,
                now=NOW + timedelta(seconds=901),
            )
        )
    assert caught.value.code == "pdf_document_ai_review_lease_expired"
    assert store.get_record_unchecked("art_full_source").purge_status == "purged"


def test_reviewer_abort_is_terminal_and_purges(tmp_path: Path) -> None:
    store, context, lease = _lease(tmp_path)

    async def abort(_view):
        raise RuntimeError("review aborted")

    with pytest.raises(RuntimeError, match="review aborted"):
        asyncio.run(lease.review(actor_context=context, reviewer=abort, now=NOW))
    assert store.get_record_unchecked("art_full_source").purge_status == "purged"
