from __future__ import annotations

import hashlib
import json
import asyncio
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

from .artifact_models import ArtifactAccessContext, ArtifactStoreError, ArtifactStorePort
from .artifact_resolver import ArtifactResolver


PDF_DOCUMENT_AI_REVIEW_POLICY_VERSION = "broker_reports_pdf_document_ai_review_v2"
PDF_DOCUMENT_AI_BASELINE_SCHEMA_VERSION = (
    "broker_reports_pdf_document_ai_ocr41_baseline_v1"
)
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
    "administrative_noise_not_financial_fact",
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
    source_file_id: str
    source_pdf_sha256: str
    source_pdf_bytes: bytes = field(repr=False)
    live_output_digest: str
    execution_binding: dict[str, object]
    content_evidence: dict[str, object]
    structural_counts: dict[str, int]
    markdown: str = field(repr=False)
    images: tuple[tuple[int, str, str, bytes, str], ...] = field(repr=False)


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
        source_file_id: str,
        source_pdf_bytes: bytes,
        expected_source_pdf_sha256: str,
        expected_image_count: int,
        expires_at: datetime,
    ) -> "PdfDocumentAiQualificationReviewLease":
        if (
            not full_source_refs
            or not source_file_id
            or expires_at.tzinfo is None
            or hashlib.sha256(source_pdf_bytes).hexdigest()
            != expected_source_pdf_sha256
        ):
            raise PdfDocumentAiQualificationReviewError(
                "pdf_document_ai_review_lease_invalid"
            )
        return PdfDocumentAiQualificationReviewLease(
            store=store,
            context=context,
            full_source_refs=tuple(full_source_refs),
            repository_head=repository_head,
            fixture_id=fixture_id,
            source_file_id=source_file_id,
            source_pdf_bytes=source_pdf_bytes,
            expected_source_pdf_sha256=expected_source_pdf_sha256,
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
        source_file_id: str,
        source_pdf_bytes: bytes,
        expected_source_pdf_sha256: str,
        expected_image_count: int,
        expires_at: datetime,
    ) -> None:
        self._store = store
        self._context = context
        self._refs = full_source_refs
        self._head = repository_head
        self._fixture_id = fixture_id
        self._source_file_id = source_file_id
        self._source_pdf_bytes = source_pdf_bytes
        self._source_pdf_sha256 = expected_source_pdf_sha256
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
            if _view_digest(view) != view.live_output_digest:
                raise PdfDocumentAiQualificationReviewError(
                    "pdf_document_ai_review_view_mutated"
                )
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
            completed_at = datetime.now(timezone.utc)
            receipt = {
                "policy_version": PDF_DOCUMENT_AI_REVIEW_POLICY_VERSION,
                "status": "passed" if passed else "failed",
                "repository_head": view.repository_head,
                "fixture_id": view.fixture_id,
                "source_pdf_sha256": view.source_pdf_sha256,
                "live_output_digest": view.live_output_digest,
                "execution_binding": view.execution_binding,
                "content_evidence": view.content_evidence,
                "structural_counts": view.structural_counts,
                "checks": dict(verdict.checks),
                "checks_passed": sum(verdict.checks.values()),
                "checks_total": len(PDF_DOCUMENT_AI_REVIEW_CHECKS),
                "reviewer_id": self._context.user_id,
                "reviewed_at": completed_at.isoformat(),
                "contains_private_payload": False,
            }
            if passed:
                receipt["baseline_candidate"] = {
                    "schema_version": PDF_DOCUMENT_AI_BASELINE_SCHEMA_VERSION,
                    "repository_head": view.repository_head,
                    "fixture_id": view.fixture_id,
                    "source_pdf_sha256": view.source_pdf_sha256,
                    "live_output_digest": view.live_output_digest,
                    "execution_binding": view.execution_binding,
                    "content_evidence": view.content_evidence,
                    "structural_counts": view.structural_counts,
                    "checks": dict(verdict.checks),
                    "reviewer_id": self._context.user_id,
                    "reviewed_at": completed_at.isoformat(),
                    "contains_private_payload": False,
                }
            return receipt
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
        images: list[tuple[int, str, str, bytes, str]] = []
        markdown_hashes: list[str] = []
        page_markdown_hashes: list[str] = []
        execution_binding: dict[str, object] | None = None
        pages_count = 0
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
            provenance = payload.get("document_ai_provenance")
            inventory = payload.get("format_structural_inventory")
            if not isinstance(provenance, dict) or not isinstance(inventory, dict):
                raise PdfDocumentAiQualificationReviewError(
                    "pdf_document_ai_review_provenance_invalid"
                )
            candidate_binding = {
                "provider_id": provenance.get("provider_id"),
                "requested_model_id": provenance.get("requested_model_id"),
                "provider_reported_model_id": provenance.get("model_id"),
                "adapter_id": provenance.get("adapter_id"),
                "request_contract_version": provenance.get("request_contract_version"),
                "request_parameters": provenance.get("request_parameters"),
                "request_parameters_sha256": provenance.get(
                    "request_parameters_sha256"
                ),
            }
            parameter_value = candidate_binding.get("request_parameters")
            parameter_sha256 = str(
                candidate_binding.get("request_parameters_sha256") or ""
            )
            if (
                not isinstance(parameter_value, dict)
                or hashlib.sha256(
                    json.dumps(
                        parameter_value,
                        ensure_ascii=True,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest()
                != parameter_sha256
            ):
                raise PdfDocumentAiQualificationReviewError(
                    "pdf_document_ai_review_request_parameters_mismatch"
                )
            if (
                provenance.get("source_pdf_sha256") != self._source_pdf_sha256
                or not all(candidate_binding.values())
                or execution_binding not in (None, candidate_binding)
            ):
                raise PdfDocumentAiQualificationReviewError(
                    "pdf_document_ai_review_provenance_mismatch"
                )
            execution_binding = candidate_binding
            observed_page_hashes = provenance.get("page_markdown_sha256")
            if not isinstance(observed_page_hashes, list) or not all(
                isinstance(item, str) and len(item) == 64
                for item in observed_page_hashes
            ):
                raise PdfDocumentAiQualificationReviewError(
                    "pdf_document_ai_review_page_digests_invalid"
                )
            page_markdown_hashes.extend(observed_page_hashes)
            observed_pages_count = inventory.get("pages_count")
            if type(observed_pages_count) is not int or observed_pages_count != len(
                observed_page_hashes
            ):
                raise PdfDocumentAiQualificationReviewError(
                    "pdf_document_ai_review_page_count_mismatch"
                )
            pages_count += observed_pages_count
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
                page_number = association.get("page_number")
                target = str(association.get("markdown_target") or "")
                image_sha256 = str(binary["content_sha256"])
                images.append(
                    (
                        page_number,
                        target,
                        image_sha256,
                        binary["content"],
                        str(binary["media_type"]),
                    )
                )
                image_material.append(
                    {
                        "page_number": page_number,
                        "markdown_target": target,
                        "sha256": image_sha256,
                    }
                )
        if len(images) != self._expected_images:
            raise PdfDocumentAiQualificationReviewError(
                "pdf_document_ai_review_image_count_mismatch"
            )
        if execution_binding is None:
            raise PdfDocumentAiQualificationReviewError(
                "pdf_document_ai_review_provenance_invalid"
            )
        structural_counts = {
            "pages_count": pages_count,
            "markdown_bytes": sum(len(part.encode("utf-8")) for part in markdown_parts),
            "images_count": len(images),
        }
        content_evidence = {
            "markdown_sha256": markdown_hashes,
            "page_markdown_sha256": page_markdown_hashes,
            "image_associations": image_material,
        }
        view = PdfDocumentAiQualificationReviewView(
            repository_head=self._head,
            fixture_id=self._fixture_id,
            source_file_id=self._source_file_id,
            source_pdf_sha256=self._source_pdf_sha256,
            source_pdf_bytes=self._source_pdf_bytes,
            live_output_digest="",
            execution_binding=execution_binding,
            content_evidence=content_evidence,
            structural_counts=structural_counts,
            markdown="\n\n".join(markdown_parts),
            images=tuple(images),
        )
        return replace(view, live_output_digest=_view_digest(view))

    def _require_same_scope(self, actor: ArtifactAccessContext) -> None:
        if actor != self._context or not actor.allow_private:
            raise ArtifactStoreError(
                "artifact_access_denied", "Qualification review scope mismatch"
            )


def _view_digest(view: PdfDocumentAiQualificationReviewView) -> str:
    return build_safe_review_evidence_digest(
        repository_head=view.repository_head,
        fixture_id=view.fixture_id,
        source_pdf_sha256=view.source_pdf_sha256,
        execution_binding=view.execution_binding,
        content_evidence=view.content_evidence,
        structural_counts=view.structural_counts,
    )


def build_safe_review_evidence_digest(
    *,
    repository_head: str,
    fixture_id: str,
    source_pdf_sha256: str,
    execution_binding: Mapping[str, object],
    content_evidence: Mapping[str, object],
    structural_counts: Mapping[str, object],
) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "policy_version": PDF_DOCUMENT_AI_REVIEW_POLICY_VERSION,
                "repository_head": repository_head,
                "fixture_id": fixture_id,
                "source_pdf_sha256": source_pdf_sha256,
                "execution_binding": execution_binding,
                "content_evidence": content_evidence,
                "structural_counts": structural_counts,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def validate_passed_review_receipt(
    receipt: Mapping[str, object],
    *,
    repository_head: str,
    fixture_id: str,
    source_pdf_sha256: str,
    expected_image_count: int,
    execution_contract: Mapping[str, object],
) -> bool:
    """Validate one safe positive receipt without reopening private payloads."""

    binding = receipt.get("execution_binding")
    checks = receipt.get("checks")
    content = receipt.get("content_evidence")
    counts = receipt.get("structural_counts")
    baseline = receipt.get("baseline_candidate")
    receipt_keys = {
        "policy_version",
        "status",
        "repository_head",
        "fixture_id",
        "source_pdf_sha256",
        "live_output_digest",
        "execution_binding",
        "content_evidence",
        "structural_counts",
        "checks",
        "checks_passed",
        "checks_total",
        "reviewer_id",
        "reviewed_at",
        "contains_private_payload",
        "baseline_candidate",
    }
    if not all(
        (
            set(receipt) == receipt_keys,
            receipt.get("policy_version") == PDF_DOCUMENT_AI_REVIEW_POLICY_VERSION,
            receipt.get("status") == "passed",
            receipt.get("repository_head") == repository_head,
            receipt.get("fixture_id") == fixture_id,
            receipt.get("source_pdf_sha256") == source_pdf_sha256,
            isinstance(binding, Mapping),
            isinstance(checks, Mapping),
            isinstance(content, Mapping),
            isinstance(counts, Mapping),
            isinstance(baseline, Mapping),
            receipt.get("contains_private_payload") is False,
        )
    ):
        return False
    expected_binding = {
        key: value
        for key, value in execution_contract.items()
        if key != "accepted_provider_reported_model_ids"
    }
    reported_model = binding.get("provider_reported_model_id")
    accepted_models = execution_contract.get("accepted_provider_reported_model_ids")
    if (
        set(binding) != {*expected_binding, "provider_reported_model_id"}
        or set(content) != {
            "markdown_sha256",
            "page_markdown_sha256",
            "image_associations",
        }
        or set(counts) != {"pages_count", "markdown_bytes", "images_count"}
        or
        {key: value for key, value in binding.items() if key != "provider_reported_model_id"}
        != expected_binding
        or not isinstance(accepted_models, list)
        or reported_model not in accepted_models
    ):
        return False
    if set(checks) != set(PDF_DOCUMENT_AI_REVIEW_CHECKS) or not all(
        value is True for value in checks.values()
    ):
        return False
    if (
        receipt.get("checks_passed") != len(PDF_DOCUMENT_AI_REVIEW_CHECKS)
        or receipt.get("checks_total") != len(PDF_DOCUMENT_AI_REVIEW_CHECKS)
    ):
        return False
    digest = receipt.get("live_output_digest")
    reviewer_id = receipt.get("reviewer_id")
    reviewed_at = receipt.get("reviewed_at")
    if (
        not isinstance(digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", digest)
        or not isinstance(reviewer_id, str)
        or not reviewer_id
        or not isinstance(reviewed_at, str)
    ):
        return False
    try:
        parsed_time = datetime.fromisoformat(reviewed_at)
    except ValueError:
        return False
    if parsed_time.tzinfo is None:
        return False
    markdown_hashes = content.get("markdown_sha256")
    page_hashes = content.get("page_markdown_sha256")
    images = content.get("image_associations")
    if not all(isinstance(value, list) for value in (markdown_hashes, page_hashes, images)):
        return False
    if not markdown_hashes or not page_hashes:
        return False
    if not all(
        isinstance(item, str) and re.fullmatch(r"[0-9a-f]{64}", item)
        for item in [*markdown_hashes, *page_hashes]
    ):
        return False
    if not all(
        isinstance(item, Mapping)
        and set(item) == {"page_number", "markdown_target", "sha256"}
        and type(item.get("page_number")) is int
        and isinstance(item.get("markdown_target"), str)
        and isinstance(item.get("sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
        for item in images
    ):
        return False
    if (
        type(counts.get("pages_count")) is not int
        or counts.get("pages_count", 0) < 1
        or counts.get("pages_count") != len(page_hashes)
        or type(counts.get("images_count")) is not int
        or counts.get("images_count") != len(images)
        or counts.get("images_count") != expected_image_count
        or type(counts.get("markdown_bytes")) is not int
        or counts.get("markdown_bytes", -1) < 0
    ):
        return False
    recomputed_digest = build_safe_review_evidence_digest(
        repository_head=repository_head,
        fixture_id=fixture_id,
        source_pdf_sha256=source_pdf_sha256,
        execution_binding=binding,
        content_evidence=content,
        structural_counts=counts,
    )
    if digest != recomputed_digest:
        return False
    expected_baseline = {
        "schema_version": PDF_DOCUMENT_AI_BASELINE_SCHEMA_VERSION,
        "repository_head": repository_head,
        "fixture_id": fixture_id,
        "source_pdf_sha256": source_pdf_sha256,
        "live_output_digest": digest,
        "execution_binding": dict(binding),
        "content_evidence": dict(content),
        "structural_counts": dict(counts),
        "checks": dict(checks),
        "reviewer_id": reviewer_id,
        "reviewed_at": reviewed_at,
        "contains_private_payload": False,
    }
    return dict(baseline) == expected_baseline
