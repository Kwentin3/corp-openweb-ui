from __future__ import annotations

import hashlib
import json
import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from .artifact_models import ArtifactAccessContext, ArtifactStoreError, ArtifactStorePort
from .artifact_resolver import ArtifactResolver


PDF_DOCUMENT_AI_REVIEW_POLICY_VERSION = "broker_reports_pdf_document_ai_review_v1"
PDF_DOCUMENT_AI_REVIEW_CHECKS = (
    "pages_exact_once_in_order",
    "tables_and_rows_complete",
    "headers_bound_to_values",
    "dates_and_periods_not_mixed",
    "page_continuations_correct",
    "adjacent_and_two_panel_tables_not_mixed",
    "numbers_signs_currencies_dates_footnotes_preserved",
    "all_private_images_reviewed",
    "full_source_reviewed",
)

FACTORY_REQUIRED = (
    "PdfDocumentAiQualificationReviewFactory.create is the only qualification "
    "review lease entrypoint"
)
FORBIDDEN = (
    "Review must not copy Full Source or image bytes to a second store, public "
    "receipt or log"
)


class PdfDocumentAiQualificationReviewError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PdfDocumentAiQualificationReviewView:
    repository_head: str
    fixture_id: str
    live_output_digest: str
    markdown: str
    images: tuple[tuple[str, bytes, str], ...]


@dataclass(frozen=True)
class PdfDocumentAiQualificationReviewVerdict:
    live_output_digest: str
    checks: dict[str, bool]


Reviewer = Callable[
    [PdfDocumentAiQualificationReviewView],
    Awaitable[PdfDocumentAiQualificationReviewVerdict],
]


class PdfDocumentAiQualificationReviewFactory:
    @staticmethod
    def create(
        *,
        store: ArtifactStorePort,
        context: ArtifactAccessContext,
        full_source_refs: list[str],
        repository_head: str,
        fixture_id: str,
        expected_image_count: int,
        expires_at: datetime,
    ) -> "PdfDocumentAiQualificationReviewLease":
        if not full_source_refs or expires_at.tzinfo is None:
            raise PdfDocumentAiQualificationReviewError(
                "pdf_document_ai_review_lease_invalid"
            )
        return PdfDocumentAiQualificationReviewLease(
            store=store,
            context=context,
            full_source_refs=tuple(full_source_refs),
            repository_head=repository_head,
            fixture_id=fixture_id,
            expected_image_count=expected_image_count,
            expires_at=expires_at.astimezone(timezone.utc),
        )


class PdfDocumentAiQualificationReviewLease:
    def __init__(
        self,
        *,
        store: ArtifactStorePort,
        context: ArtifactAccessContext,
        full_source_refs: tuple[str, ...],
        repository_head: str,
        fixture_id: str,
        expected_image_count: int,
        expires_at: datetime,
    ) -> None:
        self._store = store
        self._context = context
        self._refs = full_source_refs
        self._head = repository_head
        self._fixture_id = fixture_id
        self._expected_images = expected_image_count
        self._expires_at = expires_at

    async def review(
        self,
        *,
        actor_context: ArtifactAccessContext,
        reviewer: Reviewer,
        now: datetime | None = None,
    ) -> dict[str, object]:
        self._require_same_scope(actor_context)
        resolver = ArtifactResolver(self._store)
        try:
            observed_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
            if observed_now >= self._expires_at:
                raise PdfDocumentAiQualificationReviewError(
                    "pdf_document_ai_review_lease_expired"
                )
            view = self._resolve_view(resolver)
            remaining = (self._expires_at - observed_now).total_seconds()
            async with asyncio.timeout(remaining):
                verdict = await reviewer(view)
            if verdict.live_output_digest != view.live_output_digest:
                raise PdfDocumentAiQualificationReviewError(
                    "pdf_document_ai_review_digest_mismatch"
                )
            if set(verdict.checks) != set(PDF_DOCUMENT_AI_REVIEW_CHECKS) or any(
                type(value) is not bool for value in verdict.checks.values()
            ):
                raise PdfDocumentAiQualificationReviewError(
                    "pdf_document_ai_review_verdict_invalid"
                )
            passed = all(verdict.checks.values())
            return {
                "policy_version": PDF_DOCUMENT_AI_REVIEW_POLICY_VERSION,
                "status": "passed" if passed else "failed",
                "live_output_digest": view.live_output_digest,
                "checks_passed": sum(verdict.checks.values()),
                "checks_total": len(PDF_DOCUMENT_AI_REVIEW_CHECKS),
                "contains_private_payload": False,
            }
        finally:
            purge = self._store.purge_run(self._context)
            if purge.status != "changed":
                raise PdfDocumentAiQualificationReviewError(
                    "pdf_document_ai_review_purge_failed"
                )
            for artifact_ref in self._refs:
                try:
                    ArtifactResolver(self._store).resolve(artifact_ref, self._context)
                except ArtifactStoreError as exc:
                    if exc.code == "artifact_purged":
                        continue
                    raise
                raise PdfDocumentAiQualificationReviewError(
                    "pdf_document_ai_review_purge_failed"
                )

    def _resolve_view(
        self, resolver: ArtifactResolver
    ) -> PdfDocumentAiQualificationReviewView:
        markdown_parts: list[str] = []
        image_material: list[dict[str, object]] = []
        images: list[tuple[str, bytes, str]] = []
        markdown_hashes: list[str] = []
        for artifact_ref in self._refs:
            resolved = resolver.resolve(artifact_ref, self._context)
            payload = resolved.get("payload")
            projection = (
                payload.get("normalized_projection")
                if isinstance(payload, dict)
                else None
            )
            if not isinstance(projection, dict) or not isinstance(
                projection.get("text"), str
            ):
                raise PdfDocumentAiQualificationReviewError(
                    "pdf_document_ai_review_full_source_invalid"
                )
            markdown = projection["text"]
            markdown_sha256 = str(payload.get("document_ai_markdown_sha256") or "")
            if hashlib.sha256(markdown.encode("utf-8")).hexdigest() != markdown_sha256:
                raise PdfDocumentAiQualificationReviewError(
                    "pdf_document_ai_review_markdown_digest_mismatch"
                )
            markdown_parts.append(markdown)
            markdown_hashes.append(markdown_sha256)
            for association in payload.get("document_ai_image_refs") or []:
                if not isinstance(association, dict):
                    raise PdfDocumentAiQualificationReviewError(
                        "pdf_document_ai_review_image_association_invalid"
                    )
                binary = resolver.resolve_private_binary(
                    str(association.get("local_ref") or ""),
                    self._context,
                    expected_sha256=str(association.get("sha256") or ""),
                )
                images.append(
                    (
                        str(association.get("markdown_target") or ""),
                        binary["content"],
                        str(binary["media_type"]),
                    )
                )
                image_material.append(
                    {
                        "page_number": association.get("page_number"),
                        "markdown_target": association.get("markdown_target"),
                        "sha256": binary["content_sha256"],
                    }
                )
        if len(images) != self._expected_images:
            raise PdfDocumentAiQualificationReviewError(
                "pdf_document_ai_review_image_count_mismatch"
            )
        digest = hashlib.sha256(
            json.dumps(
                {
                    "policy_version": PDF_DOCUMENT_AI_REVIEW_POLICY_VERSION,
                    "repository_head": self._head,
                    "fixture_id": self._fixture_id,
                    "full_source_refs": self._refs,
                    "markdown_sha256": markdown_hashes,
                    "images": image_material,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return PdfDocumentAiQualificationReviewView(
            repository_head=self._head,
            fixture_id=self._fixture_id,
            live_output_digest=digest,
            markdown="\n\n".join(markdown_parts),
            images=tuple(images),
        )

    def _require_same_scope(self, actor: ArtifactAccessContext) -> None:
        if actor != self._context or not actor.allow_private:
            raise ArtifactStoreError(
                "artifact_access_denied", "Qualification review scope mismatch"
            )
