from __future__ import annotations

import base64
import copy
import hashlib
from dataclasses import dataclass
from typing import Any, Mapping

from .contracts import sha256_json, stable_digest
from .logical_row_table_recovery import (
    LogicalRowTableFactory,
    LogicalRowTableRecoveryResult,
)
from .pdf_table_locator_provider import (
    PDF_DOCUMENT_VISUAL_PROVIDER_ADAPTER_VERSION,
    PdfGridProviderError,
    PdfTableLocatorProviderFactory,
)
from .pdf_table_raster import PdfTableRasterError, PdfTableRasterFactory
from .pdf_text_layer import (
    PDF_TEXT_LAYER_PROJECTION_SCHEMA_VERSION,
    validate_pdf_text_layer_payload,
)
from .source_bound_table_scope import (
    SOURCE_BOUND_TABLE_SCOPE_PROPOSAL_SCHEMA,
    SourceBoundTableScopeError,
    SourceBoundTableScopeFactory,
)


DOCUMENT_VISUAL_ADJUDICATION_SCHEMA = (
    "broker_reports_pdf_document_visual_adjudication_v1"
)
DOCUMENT_VISUAL_ADJUDICATION_POLICY = (
    "pdf_document_visual_adjudication_policy_v1_proposed_inactive"
)
DOCUMENT_UNRESOLVED_VISUAL_POLICY = (
    "pdf_document_unresolved_visual_localization_policy_v1_inactive"
)
FACTORY_REQUIRED = (
    "PdfDocumentVisualAdjudicationFactory.create_for_openwebui is the only "
    "inactive document-wide visual orchestration entrypoint"
)
FORBIDDEN = (
    "inactive only: no ready receipt input, table identity, continuation, "
    "source literal, Canonical mutation, fact publication, or product import"
)
_DOCUMENT_VISUAL_TRANSPORT_IDENTITY = (
    "gemini_generate_content_native_document_full_page_json_schema"
)


class PdfDocumentVisualAdjudicationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PdfDocumentVisualAdjudicationResult:
    status: str
    recovery: LogicalRowTableRecoveryResult
    page_coverage: tuple[dict[str, Any], ...]
    observation_coverage: tuple[dict[str, Any], ...]
    parser_candidate_coverage: tuple[dict[str, Any], ...]
    issues: tuple[dict[str, Any], ...]
    provider_accounting: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return copy.deepcopy(
            {
                "schema_version": DOCUMENT_VISUAL_ADJUDICATION_SCHEMA,
                "policy_version": DOCUMENT_VISUAL_ADJUDICATION_POLICY,
                "status": self.status,
                "page_coverage": list(self.page_coverage),
                "observation_coverage": list(self.observation_coverage),
                "parser_candidate_coverage": list(
                    self.parser_candidate_coverage
                ),
                "issues": list(self.issues),
                "provider_accounting": self.provider_accounting,
                "recovery": self.recovery.as_dict(),
                "publication_allowed": False,
                "document_complete": False,
                "table_identity_assigned_by_coordinator": False,
                "continuation_decided_by_coordinator": False,
                "ready_scope_receipt_public_input": False,
                "product_reachability": False,
            }
        )


@dataclass(frozen=True)
class PdfDocumentUnresolvedVisualResult:
    status: str
    unresolved_table_region_refs: tuple[str, ...]
    localization: dict[str, Any] | None
    issues: tuple[dict[str, Any], ...]
    provider_accounting: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return copy.deepcopy(
            {
                "schema_version": (
                    "broker_reports_pdf_document_unresolved_visual_v1"
                ),
                "policy_version": DOCUMENT_UNRESOLVED_VISUAL_POLICY,
                "status": self.status,
                "unresolved_table_region_refs": list(
                    self.unresolved_table_region_refs
                ),
                "localization": self.localization,
                "issues": list(self.issues),
                "provider_accounting": self.provider_accounting,
                "publication_allowed": False,
                "document_complete": False,
                "recovery_performed": False,
                "table_identity_assigned": False,
                "continuation_decided": False,
                "product_reachability": False,
            }
        )


class PdfDocumentVisualAdjudicationFactory:
    def create_for_openwebui(
        self, request: Any
    ) -> "_PdfDocumentVisualAdjudicationRuntime":
        return _PdfDocumentVisualAdjudicationRuntime(
            provider=PdfTableLocatorProviderFactory().create_for_openwebui(
                request
            ),
            raster=PdfTableRasterFactory().create(),
            logical_rows=LogicalRowTableFactory().create(),
            scope_binder=SourceBoundTableScopeFactory().create(),
        )


class _PdfDocumentVisualAdjudicationRuntime:
    __slots__ = (
        "_provider",
        "_expected_model_id",
        "_raster",
        "_logical_rows",
        "_scope_binder",
        "_authority_binding",
        "_sealed",
    )

    def __init__(
        self,
        *,
        provider: Any,
        raster: Any,
        logical_rows: Any,
        scope_binder: Any,
    ) -> None:
        object.__setattr__(self, "_provider", provider)
        object.__setattr__(
            self,
            "_expected_model_id",
            _expected_provider_model_id(provider),
        )
        object.__setattr__(self, "_raster", raster)
        object.__setattr__(self, "_logical_rows", logical_rows)
        object.__setattr__(self, "_scope_binder", scope_binder)
        object.__setattr__(
            self,
            "_authority_binding",
            _provider_authority_binding(provider),
        )
        object.__setattr__(self, "_sealed", True)

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_sealed", False):
            raise PdfDocumentVisualAdjudicationError(
                "document_visual_runtime_mutation_forbidden"
            )
        object.__setattr__(self, name, value)

    def _assert_authority(self) -> None:
        if (
            _provider_authority_binding(self._provider)
            != self._authority_binding
        ):
            raise PdfDocumentVisualAdjudicationError(
                "document_visual_provider_authority_mutated"
            )

    def adjudicate(
        self,
        *,
        task_id: str,
        pdf_bytes: bytes,
        full_source_payload: Mapping[str, Any],
        source_checksum_sha256: str,
        private_evidence_ref: str,
        dpi: int = 150,
    ) -> PdfDocumentVisualAdjudicationResult:
        self._assert_authority()
        payload, projection, pages = _validated_input(
            pdf_bytes=pdf_bytes,
            full_source_payload=full_source_payload,
            source_checksum_sha256=source_checksum_sha256,
        )
        page_images, manifests = self._render_pages(
            pdf_bytes=pdf_bytes,
            source_checksum_sha256=source_checksum_sha256,
            document_ref=payload["document_ref"],
            pages=pages,
            dpi=dpi,
        )
        document_binding = _document_binding(page_images)
        proposal_result = self._provider.invoke_document_visual_geometry(
            task_id=f"{task_id}_proposal",
            phase="PROPOSAL",
            page_images=page_images,
            first_geometry_proposal=None,
            attempt_number=1,
            attempt_lineage=[],
        )
        proposal = _terminal_output(proposal_result, "proposal")
        proposal_attempt = _attempt(proposal_result, "proposal")
        self._assert_authority()
        critic_result = self._provider.invoke_document_visual_geometry(
            task_id=f"{task_id}_critic",
            phase="CRITIC",
            page_images=page_images,
            first_geometry_proposal=proposal,
            attempt_number=2,
            attempt_lineage=[proposal_attempt["attempt_id"]],
        )
        critic = _terminal_output(critic_result, "critic")
        critic_attempt = _attempt(critic_result, "critic")
        provider_accounting = _validate_provider_accounting(
            proposal_attempt,
            critic_attempt,
            expected_document_binding=document_binding,
            expected_model_id=self._expected_model_id,
            proposal_task_id=f"{task_id}_proposal",
            critic_task_id=f"{task_id}_critic",
        )

        plan = self._coverage_plan(
            payload=payload,
            projection=projection,
            pages=pages,
            manifests=manifests,
            source_checksum_sha256=source_checksum_sha256,
            proposal=proposal,
            critic=critic,
        )
        requests = tuple(plan["scope_requests"])
        if requests:
            recovery = self._logical_rows.recover_with_source_bound_scopes(
                full_source_payload=payload,
                source_checksum_sha256=source_checksum_sha256,
                private_evidence_ref=private_evidence_ref,
                source_bound_scope_requests=requests,
            )
        else:
            recovery = self._logical_rows.recover(
                projection,
                source_checksum_sha256=source_checksum_sha256,
                private_evidence_ref=private_evidence_ref,
            )
        _require_exact_word_accounting(projection, recovery)
        recovery_partial = any(
            table.get("completeness_status") == "PARTIAL"
            for table in recovery.tables
        )
        issues = tuple(plan["issues"])
        status = (
            "PARTIAL" if issues or recovery_partial else "COVERAGE_COMPLETE"
        )
        return PdfDocumentVisualAdjudicationResult(
            status=status,
            recovery=recovery,
            page_coverage=tuple(plan["page_coverage"]),
            observation_coverage=tuple(plan["observation_coverage"]),
            parser_candidate_coverage=tuple(
                plan["parser_candidate_coverage"]
            ),
            issues=issues,
            provider_accounting={
                **provider_accounting,
                "proposal_attempt_id": proposal_attempt["attempt_id"],
                "critic_attempt_id": critic_attempt["attempt_id"],
                "proposal_sha256": sha256_json(proposal),
                "critic_sha256": sha256_json(critic),
            },
        )

    def localize_unresolved_regions(
        self,
        *,
        task_id: str,
        pdf_bytes: bytes,
        full_source_payload: Mapping[str, Any],
        source_checksum_sha256: str,
        dpi: int = 150,
    ) -> PdfDocumentUnresolvedVisualResult:
        """Observe D1 unresolved regions once; never repair or publish them."""

        self._assert_authority()
        payload, projection, pages = _validated_input(
            pdf_bytes=pdf_bytes,
            full_source_payload=full_source_payload,
            source_checksum_sha256=source_checksum_sha256,
        )
        unresolved = [
            item
            for item in projection.get("unresolved_table_region_inventory") or []
            if isinstance(item, dict)
        ]
        unresolved_refs = tuple(
            str(item.get("unresolved_table_region_ref") or "")
            for item in unresolved
        )
        if not unresolved:
            return PdfDocumentUnresolvedVisualResult(
                status="NOT_APPLICABLE",
                unresolved_table_region_refs=(),
                localization=None,
                issues=(),
                provider_accounting={
                    "provider_http_calls": 0,
                    "model_generation_calls": 0,
                    "count_tokens_http_calls": 0,
                    "same_raster_binding": False,
                },
            )
        if any(not ref for ref in unresolved_refs) or len(unresolved_refs) != len(
            set(unresolved_refs)
        ):
            raise PdfDocumentVisualAdjudicationError(
                "document_unresolved_visual_inventory_invalid"
            )
        try:
            page_images, manifests = self._render_pages(
                pdf_bytes=pdf_bytes,
                source_checksum_sha256=source_checksum_sha256,
                document_ref=payload["document_ref"],
                pages=pages,
                dpi=dpi,
            )
        except PdfTableRasterError as exc:
            return PdfDocumentUnresolvedVisualResult(
                status="BLOCKED",
                unresolved_table_region_refs=unresolved_refs,
                localization=None,
                issues=({"code": exc.code},),
                provider_accounting={
                    "provider_http_calls": 0,
                    "model_generation_calls": 0,
                    "count_tokens_http_calls": 0,
                    "same_raster_binding": False,
                },
            )
        document_binding = _document_binding(page_images)
        provider_result: Mapping[str, Any] | None = None
        try:
            provider_result = self._provider.invoke_document_visual_geometry(
                task_id=f"{task_id}_unresolved_visual",
                phase="PROPOSAL",
                page_images=page_images,
                first_geometry_proposal=None,
                attempt_number=1,
                attempt_lineage=[],
            )
            provider_value = _terminal_output(provider_result, "proposal")
            attempt = _attempt(provider_result, "proposal")
            accounting = _validate_single_provider_accounting(
                attempt,
                expected_document_binding=document_binding,
                expected_model_id=self._expected_model_id,
                task_id=f"{task_id}_unresolved_visual",
            )
        except (PdfGridProviderError, PdfDocumentVisualAdjudicationError) as exc:
            code = getattr(exc, "code", str(exc))
            failed_attempt = (
                provider_result.get("attempt")
                if isinstance(provider_result, Mapping)
                and isinstance(provider_result.get("attempt"), Mapping)
                else {}
            )
            safe_details = getattr(exc, "safe_details", {})

            return PdfDocumentUnresolvedVisualResult(
                status="BLOCKED",
                unresolved_table_region_refs=unresolved_refs,
                localization=None,
                issues=({"code": str(code)},),
                provider_accounting={
                    "provider_http_calls": _observed_count(
                        failed_attempt, safe_details, "provider_http_calls"
                    ),
                    "model_generation_calls": _observed_count(
                        failed_attempt,
                        safe_details,
                        "model_generation_calls"
                    ),
                    "count_tokens_http_calls": _observed_count(
                        failed_attempt,
                        safe_details,
                        "count_tokens_http_calls"
                    ),
                    "same_raster_binding": False,
                },
            )
        self._assert_authority()
        try:
            localization = self._scope_binder.bind_unresolved_observations(
                provider_value=provider_value,
                full_source_payload=payload,
                source_checksum_sha256=source_checksum_sha256,
                raster_manifests=manifests,
            )
        except SourceBoundTableScopeError as exc:
            return PdfDocumentUnresolvedVisualResult(
                status="BLOCKED",
                unresolved_table_region_refs=unresolved_refs,
                localization=None,
                issues=({"code": exc.code},),
                provider_accounting=accounting,
            )
        return PdfDocumentUnresolvedVisualResult(
            status="BLOCKED",
            unresolved_table_region_refs=unresolved_refs,
            localization=localization,
            issues=tuple(copy.deepcopy(localization.get("issues") or [])),
            provider_accounting={
                **accounting,
                "proposal_attempt_id": attempt["attempt_id"],
                "proposal_sha256": sha256_json(provider_value),
            },
        )
    def _render_pages(
        self,
        *,
        pdf_bytes: bytes,
        source_checksum_sha256: str,
        document_ref: str,
        pages: list[dict[str, Any]],
        dpi: int,
    ) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
        images = []
        manifests = {}
        for page in pages:
            expected_bbox = _page_bbox(page)
            rendered = self._raster.render_full_page(
                pdf_bytes=pdf_bytes,
                pdf_sha256=source_checksum_sha256,
                document_ref=document_ref,
                page_ref=page["page_ref"],
                page_number=page["page_number"],
                expected_page_bbox=expected_bbox,
                dpi=dpi,
            )
            manifest = copy.deepcopy(rendered["manifest"])
            png_bytes = base64.b64decode(rendered["private_png_base64"])
            images.append(
                {
                    "png_bytes": png_bytes,
                    "raster_manifest": manifest,
                }
            )
            manifests[page["page_ref"]] = manifest
        return images, manifests

    def _coverage_plan(
        self,
        *,
        payload: dict[str, Any],
        projection: dict[str, Any],
        pages: list[dict[str, Any]],
        manifests: dict[str, dict[str, Any]],
        source_checksum_sha256: str,
        proposal: dict[str, Any],
        critic: dict[str, Any],
    ) -> dict[str, list[Any]]:
        issues: list[dict[str, Any]] = []
        observations: list[dict[str, Any]] = []
        scope_requests: list[dict[str, Any]] = []
        candidate_matches: dict[str, list[dict[str, Any]]] = {}
        candidates = _candidates(projection, pages)

        for page_index, page in enumerate(pages):
            first_tables = proposal["pages"][page_index]["tables"]
            critic_tables = critic["pages"][page_index]["tables"]
            blocked_hashes = {
                *_duplicate_or_overlapping_hashes(first_tables),
                *_duplicate_or_overlapping_hashes(critic_tables),
            }
            first_hashes = [sha256_json(table) for table in first_tables]
            critic_hashes = [sha256_json(table) for table in critic_tables]
            for first_index, (first, table_hash) in enumerate(
                zip(first_tables, first_hashes, strict=True)
            ):
                uniquely_reviewed = (
                    first_hashes.count(table_hash) == 1
                    and critic_hashes.count(table_hash) == 1
                )
                observation_ref = "visualobs_" + stable_digest(
                    [page["page_ref"], "proposal", first_index, table_hash],
                    length=24,
                )
                entry = {
                    "observation_ref": observation_ref,
                    "page_ref": page["page_ref"],
                    "proposal_observed": True,
                    "critic_observed": uniquely_reviewed,
                    "geometry_sha256": table_hash,
                    "locator_candidate_ref": None,
                    "status": "PARTIAL",
                }
                if not uniquely_reviewed and table_hash not in blocked_hashes:
                    _issue(
                        issues,
                        "document_visual_proposal_not_confirmed",
                        page_ref=page["page_ref"],
                        observation_ref=observation_ref,
                    )
                elif table_hash in blocked_hashes:
                    _issue(
                        issues,
                        "document_visual_region_nonunique_or_overlapping",
                        page_ref=page["page_ref"],
                        observation_ref=observation_ref,
                    )
                elif not _roles_inside_table(first):
                    _issue(
                        issues,
                        "document_visual_role_geometry_conflict",
                        page_ref=page["page_ref"],
                        observation_ref=observation_ref,
                    )
                else:
                    raw_proposal = _scope_proposal(first)
                    try:
                        bound = self._scope_binder.bind(
                            proposal=raw_proposal,
                            full_source_payload=payload,
                            source_checksum_sha256=source_checksum_sha256,
                            page_ref=page["page_ref"],
                            page_number=page["page_number"],
                            raster_manifest=manifests[page["page_ref"]],
                        )
                    except SourceBoundTableScopeError as exc:
                        _issue(
                            issues,
                            "document_visual_runtime_binding_failed",
                            page_ref=page["page_ref"],
                            observation_ref=observation_ref,
                            detail_code=exc.code,
                        )
                    else:
                        scope = bound.scopes[0]
                        entry["locator_candidate_ref"] = scope.locator_candidate_ref
                        if scope.locator_candidate_ref is None:
                            _issue(
                                issues,
                                "document_visual_region_without_parser_candidate",
                                page_ref=page["page_ref"],
                                observation_ref=observation_ref,
                            )
                        else:
                            candidate_matches.setdefault(
                                scope.locator_candidate_ref, []
                            ).append(
                                {
                                    "entry": entry,
                                    "scope": scope,
                                    "request": {
                                        "proposal": raw_proposal,
                                        "page_ref": page["page_ref"],
                                        "page_number": page["page_number"],
                                        "raster_manifest": copy.deepcopy(
                                            manifests[page["page_ref"]]
                                        ),
                                    },
                                }
                            )
                observations.append(entry)
            for critic_index, (_reviewed, table_hash) in enumerate(
                zip(critic_tables, critic_hashes, strict=True)
            ):
                if (
                    critic_hashes.count(table_hash) == 1
                    and first_hashes.count(table_hash) == 1
                ):
                    continue
                observation_ref = "visualobs_" + stable_digest(
                    [page["page_ref"], "critic", critic_index, table_hash],
                    length=24,
                )
                observations.append(
                    {
                        "observation_ref": observation_ref,
                        "page_ref": page["page_ref"],
                        "proposal_observed": False,
                        "critic_observed": True,
                        "geometry_sha256": table_hash,
                        "locator_candidate_ref": None,
                        "status": "PARTIAL",
                    }
                )
                _issue(
                    issues,
                    (
                        "document_visual_region_nonunique_or_overlapping"
                        if table_hash in blocked_hashes
                        else "document_visual_critic_only_region"
                    ),
                    page_ref=page["page_ref"],
                    observation_ref=observation_ref,
                )

        candidate_coverage = []
        for candidate in candidates:
            matches = candidate_matches.get(candidate["table_candidate_ref"], [])
            item = {
                "table_candidate_ref": candidate["table_candidate_ref"],
                "page_ref": candidate["page_ref"],
                "observation_refs": sorted(
                    match["entry"]["observation_ref"] for match in matches
                ),
                "status": "PARTIAL",
            }
            if len(matches) != 1:
                _issue(
                    issues,
                    (
                        "document_visual_parser_candidate_missed"
                        if not matches
                        else "document_visual_parser_candidate_nonunique"
                    ),
                    page_ref=candidate["page_ref"],
                    candidate_ref=candidate["table_candidate_ref"],
                )
            else:
                match = matches[0]
                scope = match["scope"]
                if scope.binding_status != "BOUND":
                    _issue(
                        issues,
                        "document_visual_candidate_non_authoritative",
                        page_ref=candidate["page_ref"],
                        candidate_ref=candidate["table_candidate_ref"],
                        detail_code=";".join(scope.issue_codes),
                    )
                elif scope.header_status == "ABSENT":
                    # Two visual passes still do not prove absence from source.
                    # LogicalRow may independently prove continuation.
                    item["status"] = "REVIEWED_ABSENCE_NONAUTHORITATIVE"
                    match["entry"]["status"] = item["status"]
                else:
                    item["status"] = "REVIEWED_SOURCE_BOUND"
                    match["entry"]["status"] = item["status"]
                    scope_requests.append(match["request"])
            candidate_coverage.append(item)

        page_coverage = []
        for page in pages:
            page_candidates = [
                item for item in candidate_coverage if item["page_ref"] == page["page_ref"]
            ]
            page_observations = [
                item for item in observations if item["page_ref"] == page["page_ref"]
            ]
            page_issue = any(
                issue.get("page_ref") == page["page_ref"] for issue in issues
            )
            page_coverage.append(
                {
                    "page_ref": page["page_ref"],
                    "page_number": page["page_number"],
                    "proposal_observations": sum(
                        bool(item["proposal_observed"])
                        for item in page_observations
                    ),
                    "critic_observations": sum(
                        bool(item["critic_observed"])
                        for item in page_observations
                    ),
                    "parser_candidates": len(page_candidates),
                    "status": "PARTIAL" if page_issue else "ACCOUNTED",
                }
            )
        return {
            "issues": sorted(issues, key=sha256_json),
            "page_coverage": page_coverage,
            "observation_coverage": sorted(
                observations, key=lambda item: item["observation_ref"]
            ),
            "parser_candidate_coverage": candidate_coverage,
            "scope_requests": scope_requests,
        }


def _observed_count(
    failed_attempt: Mapping[str, Any], safe_details: Mapping[str, Any], key: str
) -> int:
    value = failed_attempt.get(key, safe_details.get(key, 0))
    return (
        int(value)
        if isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= 2
        else 0
    )


def _validated_input(
    *,
    pdf_bytes: bytes,
    full_source_payload: Mapping[str, Any],
    source_checksum_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    if (
        not isinstance(pdf_bytes, bytes)
        or hashlib.sha256(pdf_bytes).hexdigest() != source_checksum_sha256
        or not isinstance(full_source_payload, dict)
    ):
        raise PdfDocumentVisualAdjudicationError(
            "document_visual_source_binding_invalid"
        )
    payload = copy.deepcopy(full_source_payload)
    try:
        validation = validate_pdf_text_layer_payload(payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise PdfDocumentVisualAdjudicationError(
            "document_visual_full_source_invalid"
        ) from exc
    if validation.get("validator_status") != "passed":
        raise PdfDocumentVisualAdjudicationError(
            "document_visual_full_source_invalid"
        )
    expected_ref = "srcsum_" + stable_digest(
        [payload.get("document_ref"), source_checksum_sha256], length=24
    )
    if payload.get("source_checksum_ref") != expected_ref:
        raise PdfDocumentVisualAdjudicationError(
            "document_visual_source_binding_invalid"
        )
    projection = payload.get("pdf_text_layer_projection")
    if (
        not isinstance(projection, dict)
        or projection.get("schema_version")
        != PDF_TEXT_LAYER_PROJECTION_SCHEMA_VERSION
    ):
        raise PdfDocumentVisualAdjudicationError(
            "document_visual_projection_invalid"
        )
    pages = sorted(
        [copy.deepcopy(item) for item in projection.get("page_inventory", [])],
        key=lambda item: item.get("page_number", 0),
    )
    if (
        not pages
        or [item.get("page_number") for item in pages]
        != list(range(1, len(pages) + 1))
        or len({item.get("page_ref") for item in pages}) != len(pages)
    ):
        raise PdfDocumentVisualAdjudicationError(
            "document_visual_page_inventory_invalid"
        )
    return payload, projection, pages


def _page_bbox(page: Mapping[str, Any]) -> list[float]:
    width = page.get("layout_page_width") or page.get("width")
    height = page.get("layout_page_height") or page.get("height")
    if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
        raise PdfDocumentVisualAdjudicationError(
            "document_visual_page_inventory_invalid"
        )
    return [0.0, 0.0, float(width), float(height)]


def _document_binding(page_images: list[dict[str, Any]]) -> dict[str, Any]:
    pages = []
    document_ref: str | None = None
    pdf_sha256: str | None = None
    for ordinal, item in enumerate(page_images, start=1):
        png_bytes = item.get("png_bytes")
        manifest = item.get("raster_manifest")
        if not isinstance(png_bytes, bytes) or not isinstance(manifest, dict):
            raise PdfDocumentVisualAdjudicationError(
                "document_visual_rendered_page_invalid"
            )
        unhashed = copy.deepcopy(manifest)
        manifest_hash = unhashed.pop("manifest_hash", None)
        png_sha256 = hashlib.sha256(png_bytes).hexdigest()
        if (
            manifest_hash != sha256_json(unhashed)
            or manifest.get("png_sha256") != png_sha256
            or manifest.get("png_bytes") != len(png_bytes)
            or manifest.get("page_number") != ordinal
            or not isinstance(manifest.get("page_ref"), str)
            or not manifest.get("page_ref")
        ):
            raise PdfDocumentVisualAdjudicationError(
                "document_visual_rendered_page_invalid"
            )
        if document_ref is None:
            document_ref = manifest.get("document_ref")
            pdf_sha256 = manifest.get("pdf_sha256")
        elif (
            manifest.get("document_ref") != document_ref
            or manifest.get("pdf_sha256") != pdf_sha256
        ):
            raise PdfDocumentVisualAdjudicationError(
                "document_visual_rendered_page_invalid"
            )
        pages.append(
            {
                "page_ordinal": ordinal,
                "page_number": manifest["page_number"],
                "page_ref": manifest["page_ref"],
                "raster_manifest_hash": manifest_hash,
                "png_sha256": png_sha256,
            }
        )
    if not pages or not isinstance(document_ref, str) or not _sha256(pdf_sha256):
        raise PdfDocumentVisualAdjudicationError(
            "document_visual_rendered_page_invalid"
        )
    return {
        "document_ref": document_ref,
        "pdf_sha256": pdf_sha256,
        "pages": pages,
    }


def _terminal_output(result: Any, phase: str) -> dict[str, Any]:
    if not isinstance(result, Mapping) or not isinstance(
        result.get("json_output"), dict
    ):
        raise PdfDocumentVisualAdjudicationError(
            f"document_visual_{phase}_not_terminal"
        )
    return copy.deepcopy(result["json_output"])


def _attempt(result: Mapping[str, Any], phase: str) -> dict[str, Any]:
    attempt = result.get("attempt")
    if not isinstance(attempt, dict) or not isinstance(
        attempt.get("attempt_id"), str
    ):
        raise PdfDocumentVisualAdjudicationError(
            f"document_visual_{phase}_attempt_invalid"
        )
    return copy.deepcopy(attempt)


def _validate_provider_accounting(
    proposal: Mapping[str, Any],
    critic: Mapping[str, Any],
    *,
    expected_document_binding: Mapping[str, Any],
    expected_model_id: str,
    proposal_task_id: str,
    critic_task_id: str,
) -> dict[str, Any]:
    binding = copy.deepcopy(dict(expected_document_binding))
    binding_sha256 = sha256_json(binding)
    expected = (
        (proposal, "PROPOSAL", proposal_task_id, 1, []),
        (
            critic,
            "CRITIC",
            critic_task_id,
            2,
            [proposal.get("attempt_id")],
        ),
    )
    for attempt, phase, task_id, attempt_number, lineage in expected:
        request_hash = attempt.get("request_hash")
        counted_tokens = attempt.get("counted_input_tokens")
        maximum_tokens = attempt.get("maximum_counted_input_tokens")
        if (
            attempt.get("task_id") != task_id
            or attempt.get("attempt_id") != f"{task_id}_a{attempt_number}"
            or attempt.get("attempt_number") != attempt_number
            or attempt.get("attempt_lineage") != lineage
            or attempt.get("phase") != phase
            or attempt.get("document_binding") != binding
            or attempt.get("document_binding_sha256") != binding_sha256
            or attempt.get("adapter_identity")
            != PDF_DOCUMENT_VISUAL_PROVIDER_ADAPTER_VERSION
            or attempt.get("transport_identity")
            != _DOCUMENT_VISUAL_TRANSPORT_IDENTITY
            or attempt.get("provider_calls") != 2
            or attempt.get("provider_http_calls") != 2
            or attempt.get("count_tokens_http_calls") != 1
            or attempt.get("model_generation_calls") != 1
            or attempt.get("http_status") not in range(200, 300)
            or attempt.get("finish_reason") != "STOP"
            or attempt.get("parse_result") != "parsed_object"
            or attempt.get("terminal_failure_class") is not None
            or attempt.get("hidden_retry") is not False
            or attempt.get("provider_failover") is not False
            or attempt.get("model_values_used_as_source_literals") is not False
            or attempt.get("table_identity_assigned") is not False
            or attempt.get("continuation_decided") is not False
            or attempt.get("product_reachability") is not False
            or not _sha256(request_hash)
            or attempt.get("generation_request_hash") != request_hash
            or attempt.get("counted_generation_body_hash") != request_hash
            or not _sha256(attempt.get("count_tokens_request_hash"))
            or not _sha256(attempt.get("count_tokens_response_hash"))
            or not _positive_int(attempt.get("generation_request_bytes"))
            or not _positive_int(attempt.get("count_tokens_request_bytes"))
            or not isinstance(counted_tokens, int)
            or isinstance(counted_tokens, bool)
            or counted_tokens < 0
            or not _positive_int(maximum_tokens)
            or counted_tokens > maximum_tokens
            or attempt.get("count_tokens_within_hard_guard") is not True
            or not _sha256(attempt.get("canonical_schema_hash"))
            or not _sha256(attempt.get("adapted_schema_hash"))
            or attempt.get("model_requested") != expected_model_id
            or attempt.get("model_resolved") != expected_model_id
        ):
            raise PdfDocumentVisualAdjudicationError(
                "document_visual_provider_accounting_invalid"
            )
    same_raster_binding = all(
        attempt.get("document_binding") == binding
        and attempt.get("document_binding_sha256") == binding_sha256
        for attempt in (proposal, critic)
    )
    return {
        "provider_http_calls": sum(
            int(attempt["provider_http_calls"])
            for attempt in (proposal, critic)
        ),
        "model_generation_calls": sum(
            int(attempt["model_generation_calls"])
            for attempt in (proposal, critic)
        ),
        "count_tokens_http_calls": sum(
            int(attempt["count_tokens_http_calls"])
            for attempt in (proposal, critic)
        ),
        "same_raster_binding": same_raster_binding,
        "document_binding_sha256": binding_sha256,
    }


def _validate_single_provider_accounting(
    attempt: Mapping[str, Any],
    *,
    expected_document_binding: Mapping[str, Any],
    expected_model_id: str,
    task_id: str,
) -> dict[str, Any]:
    binding = copy.deepcopy(dict(expected_document_binding))
    binding_sha256 = sha256_json(binding)
    request_hash = attempt.get("request_hash")
    counted_tokens = attempt.get("counted_input_tokens")
    maximum_tokens = attempt.get("maximum_counted_input_tokens")
    if (
        attempt.get("task_id") != task_id
        or attempt.get("attempt_id") != f"{task_id}_a1"
        or attempt.get("attempt_number") != 1
        or attempt.get("attempt_lineage") != []
        or attempt.get("phase") != "PROPOSAL"
        or attempt.get("document_binding") != binding
        or attempt.get("document_binding_sha256") != binding_sha256
        or attempt.get("adapter_identity")
        != PDF_DOCUMENT_VISUAL_PROVIDER_ADAPTER_VERSION
        or attempt.get("transport_identity") != _DOCUMENT_VISUAL_TRANSPORT_IDENTITY
        or attempt.get("provider_calls") != 2
        or attempt.get("provider_http_calls") != 2
        or attempt.get("count_tokens_http_calls") != 1
        or attempt.get("model_generation_calls") != 1
        or attempt.get("http_status") not in range(200, 300)
        or attempt.get("finish_reason") != "STOP"
        or attempt.get("parse_result") != "parsed_object"
        or attempt.get("terminal_failure_class") is not None
        or attempt.get("hidden_retry") is not False
        or attempt.get("provider_failover") is not False
        or attempt.get("model_values_used_as_source_literals") is not False
        or attempt.get("table_identity_assigned") is not False
        or attempt.get("continuation_decided") is not False
        or attempt.get("product_reachability") is not False
        or not _sha256(request_hash)
        or attempt.get("generation_request_hash") != request_hash
        or attempt.get("counted_generation_body_hash") != request_hash
        or not _sha256(attempt.get("count_tokens_request_hash"))
        or not _sha256(attempt.get("count_tokens_response_hash"))
        or not _positive_int(attempt.get("generation_request_bytes"))
        or not _positive_int(attempt.get("count_tokens_request_bytes"))
        or not isinstance(counted_tokens, int)
        or isinstance(counted_tokens, bool)
        or counted_tokens < 0
        or not _positive_int(maximum_tokens)
        or counted_tokens > maximum_tokens
        or attempt.get("count_tokens_within_hard_guard") is not True
        or not _sha256(attempt.get("canonical_schema_hash"))
        or not _sha256(attempt.get("adapted_schema_hash"))
        or attempt.get("model_requested") != expected_model_id
        or attempt.get("model_resolved") != expected_model_id
    ):
        raise PdfDocumentVisualAdjudicationError(
            "document_visual_provider_accounting_invalid"
        )
    return {
        "provider_http_calls": 2,
        "model_generation_calls": 1,
        "count_tokens_http_calls": 1,
        "same_raster_binding": True,
        "document_binding_sha256": binding_sha256,
    }


def _expected_provider_model_id(provider: Any) -> str:
    config = getattr(provider, "config", None)
    profile = getattr(provider, "profile", None)
    model_id = getattr(config, "model_id", None)
    approved_model_ids = getattr(profile, "approved_model_ids", None)
    if (
        not isinstance(model_id, str)
        or model_id != model_id.strip()
        or not model_id.startswith("models/")
        or model_id.count("/") != 1
        or len(model_id) <= len("models/")
        or not isinstance(approved_model_ids, tuple)
        or model_id not in approved_model_ids
    ):
        raise PdfDocumentVisualAdjudicationError(
            "document_visual_provider_model_invalid"
        )
    return model_id


def _provider_authority_binding(provider: Any) -> tuple[Any, ...]:
    config = getattr(provider, "config", None)
    profile = getattr(provider, "profile", None)
    connection = getattr(provider, "connection", None)
    invoke = getattr(provider, "invoke_document_visual_geometry", None)
    invoke_function = getattr(invoke, "__func__", invoke)
    invoke_owner = getattr(invoke, "__self__", None)
    api_key = getattr(connection, "api_key", None)
    api_key_sha256 = (
        hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        if isinstance(api_key, str)
        else None
    )
    transport = getattr(provider, "urlopen_fn", None)
    return (
        id(provider),
        type(provider).__module__,
        type(provider).__qualname__,
        id(invoke_function),
        id(invoke_owner),
        id(config),
        type(config).__module__,
        type(config).__qualname__,
        getattr(config, "provider_profile", None),
        getattr(config, "model_id", None),
        getattr(config, "timeout_seconds", None),
        getattr(config, "maximum_output_tokens", None),
        getattr(config, "maximum_counted_input_tokens", None),
        getattr(config, "thinking_level", None),
        id(profile),
        type(profile).__module__,
        type(profile).__qualname__,
        getattr(profile, "profile_id", None),
        getattr(profile, "approved_model_ids", None),
        getattr(profile, "connection_base_url_prefixes", None),
        id(connection),
        type(connection).__module__,
        type(connection).__qualname__,
        getattr(connection, "base_url", None),
        api_key_sha256,
        id(transport),
        type(transport).__module__,
        type(transport).__qualname__,
    )


def _sha256(value: Any) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _scope_proposal(table: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SOURCE_BOUND_TABLE_SCOPE_PROPOSAL_SCHEMA,
        "tables": [
            {
                "title_status": table["title_status"],
                "title_boxes_2d": copy.deepcopy(table["title_boxes_2d"]),
                "header_status": table["header_status"],
                "header_boxes_2d": copy.deepcopy(table["header_boxes_2d"]),
                "body_status": table["body_status"],
                "body_anchor_boxes_2d": copy.deepcopy(
                    table["body_anchor_boxes_2d"]
                ),
            }
        ],
    }


def _duplicate_or_overlapping_hashes(
    tables: list[dict[str, Any]],
) -> set[str]:
    hashes = [sha256_json(table) for table in tables]
    blocked = {value for value in hashes if hashes.count(value) > 1}
    for index, left in enumerate(tables):
        for right in tables[index + 1 :]:
            if _boxes_overlap(left["table_box_2d"], right["table_box_2d"]):
                blocked.update((sha256_json(left), sha256_json(right)))
    return blocked


def _roles_inside_table(table: Mapping[str, Any]) -> bool:
    outer = table["table_box_2d"]
    return all(
        _box_inside(box, outer)
        for key in (
            "title_boxes_2d",
            "header_boxes_2d",
            "body_anchor_boxes_2d",
        )
        for box in table[key]
    )


def _box_inside(inner: list[int], outer: list[int]) -> bool:
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and inner[2] <= outer[2]
        and inner[3] <= outer[3]
    )


def _boxes_overlap(left: list[int], right: list[int]) -> bool:
    return (
        max(left[0], right[0]) < min(left[2], right[2])
        and max(left[1], right[1]) < min(left[3], right[3])
    )


def _candidates(
    projection: Mapping[str, Any], pages: list[dict[str, Any]]
) -> list[dict[str, str]]:
    page_order = {page["page_ref"]: index for index, page in enumerate(pages)}
    return sorted(
        [
            {
                "table_candidate_ref": item["table_candidate_ref"],
                "page_ref": item["page_ref"],
            }
            for item in projection.get("table_candidate_inventory", [])
        ],
        key=lambda item: (
            page_order[item["page_ref"]],
            item["table_candidate_ref"],
        ),
    )


def _issue(
    issues: list[dict[str, Any]],
    code: str,
    *,
    page_ref: str,
    observation_ref: str | None = None,
    candidate_ref: str | None = None,
    detail_code: str | None = None,
) -> None:
    issues.append(
        {
            "code": code,
            "page_ref": page_ref,
            "observation_ref": observation_ref,
            "table_candidate_ref": candidate_ref,
            "detail_code": detail_code,
        }
    )


def _require_exact_word_accounting(
    projection: Mapping[str, Any], recovery: LogicalRowTableRecoveryResult
) -> None:
    source_refs = {
        item["word_ref"] for item in projection.get("word_inventory", [])
    }
    # The public ownership record stores source_word_id; paragraph refs plus
    # table ownership cardinality are therefore the stable public proof here.
    if (
        recovery.unowned_word_refs
        or len(recovery.source_word_ownership)
        + len(recovery.paragraph_owned_word_refs)
        != len(source_refs)
    ):
        raise PdfDocumentVisualAdjudicationError(
            "document_visual_source_accounting_invalid"
        )
