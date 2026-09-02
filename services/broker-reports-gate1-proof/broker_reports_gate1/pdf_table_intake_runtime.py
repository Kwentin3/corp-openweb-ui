from __future__ import annotations

import base64
import copy
import hashlib
import math
import weakref
from dataclasses import dataclass
from typing import Any

from .contracts import sha256_json, stable_digest
from .pdf_table_locator_provider import (
    PDF_GRID_PROVIDER_ADAPTER_VERSION,
    PdfTableLocatorProviderConfig,
    PdfTableLocatorProviderError,
    PdfTableLocatorProviderFactory,
)
from .pdf_table_locator import (
    PDF_TABLE_LOCATOR_COORDINATE_CONTRACT,
    PDF_TABLE_LOCATOR_OUTPUT_SCHEMA,
    PDF_TABLE_LOCATOR_POLICY_VERSION,
    PDF_TABLE_LOCATOR_PROJECTION_SCHEMA,
    PDF_TABLE_LOCATOR_PROMPT,
    PDF_TABLE_LOCATOR_RESPONSE_SCHEMA,
    PdfTableLocatorError,
    PdfTableLocatorProjectionConfig,
    PdfTableLocatorProjectionFactory,
)
from .pdf_table_raster import (
    PdfTableRasterConfig,
    PdfTableRasterError,
    PdfTableRasterFactory,
)


PDF_TABLE_DETECTION_REQUEST_SCHEMA = "broker_reports_pdf_table_detection_request_v4"
PDF_TABLE_DETECTION_RESPONSE_SCHEMA = PDF_TABLE_LOCATOR_RESPONSE_SCHEMA
PDF_TABLE_DETECTION_ATTEMPT_SCHEMA = "broker_reports_pdf_table_detection_attempt_v1"
PDF_TABLE_INTAKE_RUN_SCHEMA = "broker_reports_pdf_table_intake_run_v1"
PDF_TABLE_INTAKE_POLICY_VERSION = "pdf_table_intake_policy_v6"
PDF_TABLE_SOURCE_BOUND_LOCALIZATION_SCHEMA = (
    "broker_reports_pdf_table_source_bound_localization_v1"
)

_SOURCE_BOUND_FACTORY_CAPABILITY = object()


class SourceBoundLocalizationScope(dict):
    """Process-local owner-minted scope; serialization carries no authority."""

    __slots__ = ("__weakref__",)


def _scope_registry():
    entries: dict[int, tuple[weakref.ReferenceType[SourceBoundLocalizationScope], str]] = {}

    def mint(value: dict[str, Any]) -> SourceBoundLocalizationScope:
        scope = SourceBoundLocalizationScope(copy.deepcopy(value))
        identity = id(scope)

        def cleanup(reference: weakref.ReferenceType[SourceBoundLocalizationScope]) -> None:
            current = entries.get(identity)
            if current is not None and current[0] is reference:
                entries.pop(identity, None)

        reference = weakref.ref(scope, cleanup)
        entries[identity] = (reference, sha256_json(value))
        return scope

    def fingerprint(value: object) -> str | None:
        entry = entries.get(id(value))
        return entry[1] if entry is not None and entry[0]() is value else None

    return mint, fingerprint


_mint_localization_scope, _localization_scope_fingerprint = _scope_registry()
FACTORY_REQUIRED = (
    "PdfTableIntakeRuntimeFactory.create_for_openwebui is the only supported "
    "live PDF table detection and crop entrypoint"
)
FORBIDDEN = (
    "The Pipe and operator smoke must not call a VLM adapter or raster renderer "
    "directly; Gate 1 must not infer rows, columns, cells, values, or financial semantics"
)


class PdfTableIntakeError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        private_attempt: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.private_attempt = private_attempt
        super().__init__(code)


@dataclass(frozen=True)
class PdfTableIntakeConfig:
    enabled: bool = False
    source_bound_localization_enabled: bool = False
    detector_provider_profile: str = "google_gemini"
    detector_model_id: str = "models/gemini-3.5-flash"
    dpi: int = 150
    maximum_pages: int = 64
    maximum_candidates_per_page: int = 32
    horizontal_padding_fraction: float = 0.08
    vertical_padding_fraction: float = 0.08


@dataclass(frozen=True)
class PdfTableIntakeResult:
    safe_summary: dict[str, Any]
    private_candidates: list[dict[str, Any]]
    private_detection_attempts: list[dict[str, Any]]
    private_page_results: list[dict[str, Any]]


class PdfTableIntakeRuntimeFactory:
    def __init__(self, config: PdfTableIntakeConfig | None = None) -> None:
        self.config = config or PdfTableIntakeConfig()
        self._validate_config()

    def create_for_openwebui(self, request: Any) -> "PdfTableIntakeRuntime":
        provider = PdfTableLocatorProviderFactory(
            PdfTableLocatorProviderConfig(
                provider_profile=self.config.detector_provider_profile,
                model_id=self.config.detector_model_id,
            )
        ).create_for_openwebui(request)
        return self._create(provider, capability=_SOURCE_BOUND_FACTORY_CAPABILITY)

    def create_with_provider(self, provider: Any) -> "PdfTableIntakeRuntime":
        """Explicit external-provider seam for deterministic contract tests."""

        if self.config.source_bound_localization_enabled:
            raise PdfTableIntakeError(
                "pdf_table_source_bound_canonical_factory_required"
            )
        return self._create(provider)

    def _create(self, provider: Any, *, capability: object | None = None) -> "PdfTableIntakeRuntime":
        raster = PdfTableRasterFactory(
            PdfTableRasterConfig(
                horizontal_padding_fraction=(self.config.horizontal_padding_fraction),
                vertical_padding_fraction=self.config.vertical_padding_fraction,
            )
        ).create()
        locator = PdfTableLocatorProjectionFactory(
            PdfTableLocatorProjectionConfig(
                maximum_tables=self.config.maximum_candidates_per_page
            )
        ).create()
        return PdfTableIntakeRuntime(
            self.config,
            provider,
            raster,
            locator,
            _source_bound_capability=capability,
        )

    def _validate_config(self) -> None:
        if self.config.dpi != 150:
            raise PdfTableIntakeError("pdf_table_intake_dpi_invalid")
        if self.config.maximum_pages < 1 or self.config.maximum_pages > 512:
            raise PdfTableIntakeError("pdf_table_intake_page_budget_invalid")
        if (
            self.config.maximum_candidates_per_page < 1
            or self.config.maximum_candidates_per_page > 64
        ):
            raise PdfTableIntakeError("pdf_table_intake_candidate_budget_invalid")
        for value in (
            self.config.horizontal_padding_fraction,
            self.config.vertical_padding_fraction,
        ):
            if not math.isfinite(value) or value < 0 or value > 0.25:
                raise PdfTableIntakeError("pdf_table_intake_padding_invalid")


class PdfTableIntakeRuntime:
    def __init__(
        self,
        config: PdfTableIntakeConfig,
        provider: Any,
        raster: Any,
        locator: Any,
        *,
        _source_bound_capability: object | None = None,
    ) -> None:
        self.config = config
        self.provider = provider
        self.raster = raster
        self.locator = locator
        self._source_bound_authorized = (
            _source_bound_capability is _SOURCE_BOUND_FACTORY_CAPABILITY
        )

    def run(self, documents: list[dict[str, Any]]) -> PdfTableIntakeResult:
        if (
            self.config.source_bound_localization_enabled
            and not self._source_bound_authorized
        ):
            raise PdfTableIntakeError("pdf_table_source_bound_canonical_factory_required")
        if not self.config.enabled:
            return PdfTableIntakeResult(
                safe_summary=self._summary(
                    status="disabled",
                    documents_total=0,
                    pages_total=0,
                    candidates_total=0,
                    failed_pages=[],
                    rejected_regions=[],
                    detector_qualification=None,
                ),
                private_candidates=[],
                private_detection_attempts=[],
                private_page_results=[],
            )
        normalized_documents = self._validate_documents(documents)
        if not normalized_documents:
            return PdfTableIntakeResult(
                safe_summary=self._summary(
                    status="completed",
                    documents_total=0,
                    pages_total=0,
                    candidates_total=0,
                    failed_pages=[],
                    rejected_regions=[],
                    detector_qualification=None,
                ),
                private_candidates=[],
                private_detection_attempts=[],
                private_page_results=[],
            )
        try:
            qualification = self.provider.qualify()
        except Exception as exc:
            raise PdfTableIntakeError(
                "pdf_table_detector_qualification_failed"
            ) from exc
        if qualification.get("status") != "qualified":
            raise PdfTableIntakeError("pdf_table_detector_not_qualified")

        candidates: list[dict[str, Any]] = []
        attempts: list[dict[str, Any]] = []
        page_results: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        rejected_regions: list[dict[str, Any]] = []
        pages_total = 0
        for document in normalized_documents:
            page_count = self._page_count(document["pdf_bytes"])
            pages_total += page_count
            if pages_total > self.config.maximum_pages:
                raise PdfTableIntakeError("pdf_table_intake_page_budget_exceeded")
            for page_number in range(1, page_count + 1):
                try:
                    page_result, attempt = self._run_page(
                        document=document,
                        page_number=page_number,
                        qualification=qualification,
                    )
                    candidates.extend(page_result["regions"])
                    page_results.append(page_result)
                    attempts.append(attempt)
                    rejected_total = int(attempt.get("rejected_regions_total") or 0)
                    if rejected_total:
                        rejected_regions.append(
                            {
                                "document_ref": document["document_ref"],
                                "page_number": page_number,
                                "rejected_regions_total": rejected_total,
                                "reason_codes": list(
                                    attempt.get("rejected_region_reason_codes") or []
                                ),
                            }
                        )
                except (
                    PdfTableIntakeError,
                    PdfTableRasterError,
                    PdfTableLocatorProviderError,
                    PdfTableLocatorError,
                ) as exc:
                    code = getattr(exc, "code", "pdf_table_intake_page_failed")
                    private_attempt = getattr(exc, "private_attempt", None)
                    if isinstance(private_attempt, dict):
                        attempts.append(copy.deepcopy(private_attempt))
                    failures.append(
                        {
                            "document_ref": document["document_ref"],
                            "page_number": page_number,
                            "failure_code": str(code),
                        }
                    )
                    page_results.append(
                        {
                            "schema_version": "broker_reports_pdf_table_locator_page_v1",
                            "document_ref": document["document_ref"],
                            "pdf_sha256": document["pdf_sha256"],
                            "page_number": page_number,
                            "status": "failed",
                            "failure_code": str(code),
                            "regions": [],
                        }
                    )

        status = (
            "failed"
            if failures
            else (
                "completed_with_rejected_regions"
                if rejected_regions
                else (
                    "localized_pending_admission"
                    if self.config.source_bound_localization_enabled
                    else "completed"
                )
            )
        )
        return PdfTableIntakeResult(
            safe_summary=self._summary(
                status=status,
                documents_total=len(normalized_documents),
                pages_total=pages_total,
                candidates_total=len(candidates),
                failed_pages=failures,
                rejected_regions=rejected_regions,
                detector_qualification=qualification,
            ),
            # Legacy VLM-transcription crops are intentionally not produced.
            private_candidates=[],
            private_detection_attempts=attempts,
            private_page_results=page_results,
        )

    def _run_page(
        self,
        *,
        document: dict[str, Any],
        page_number: int,
        qualification: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        page_ref = "pdfpage_" + stable_digest(
            [document["pdf_sha256"], page_number], length=24
        )
        request_id = "pdftabledetect_" + stable_digest(
            [
                PDF_TABLE_DETECTION_REQUEST_SCHEMA,
                document["pdf_sha256"],
                page_number,
                self.config.detector_provider_profile,
                self.config.detector_model_id,
            ],
            length=24,
        )
        page_bbox = self._page_bbox(document["pdf_bytes"], page_number)
        page_raster = self.raster.render_full_page(
            pdf_bytes=document["pdf_bytes"],
            pdf_sha256=document["pdf_sha256"],
            document_ref=document["document_ref"],
            page_ref=page_ref,
            page_number=page_number,
            expected_page_bbox=page_bbox,
            dpi=self.config.dpi,
        )
        png_bytes = base64.b64decode(
            page_raster["private_png_base64"].encode("ascii"), validate=True
        )
        page_png_sha256 = hashlib.sha256(png_bytes).hexdigest()
        model_view = self._model_view(request_id=request_id, page_number=page_number)
        output_schema = table_detection_output_schema()
        token_count = self.provider.count_tokens(
            model_view=model_view,
            output_schema=output_schema,
            png_bytes=png_bytes,
            crop_sha256=page_png_sha256,
        )
        task_id = "pdf_table_detection_" + stable_digest(
            [request_id, page_png_sha256], length=24
        )
        response = self.provider.invoke(
            task_id=task_id,
            model_view=model_view,
            output_schema=output_schema,
            png_bytes=png_bytes,
            crop_sha256=page_png_sha256,
            attempt_number=1,
            attempt_lineage=[],
        )
        attempt = copy.deepcopy(response.get("attempt") or {})
        if attempt.get("terminal_failure_class") is not None:
            raise PdfTableIntakeError("pdf_table_detector_terminal_failure")
        try:
            projection = self.locator.project(
                provider_value=response.get("json_output"),
                raster_manifest=page_raster["manifest"],
                expected_page_bbox=page_bbox,
            )
        except PdfTableLocatorError as exc:
            raise PdfTableIntakeError(
                exc.code,
                private_attempt={
                    "schema_version": PDF_TABLE_DETECTION_ATTEMPT_SCHEMA,
                    "request_id": request_id,
                    "document_ref": document["document_ref"],
                    "pdf_sha256": document["pdf_sha256"],
                    "page_number": page_number,
                    "page_ref": page_ref,
                    "page_raster_manifest": page_raster["manifest"],
                    "model_view_hash": sha256_json(model_view),
                    "output_schema_hash": sha256_json(output_schema),
                    "token_count": token_count,
                    "provider_attempt": attempt,
                    "provider_response_hash": response.get("response_hash"),
                    "raw_private_response": copy.deepcopy(
                        response.get("raw_private_response") or {}
                    ),
                    "rejected_json_output": copy.deepcopy(
                        response.get("json_output")
                    ),
                    "validated_regions": [],
                    "terminal_status": "rejected",
                    "validation_error_code": exc.code,
                    "hidden_retry": False,
                    "provider_failover": False,
                },
            ) from exc
        detector_identity = {
            "provider_profile": attempt.get("provider_profile"),
            "provider_profile_revision": attempt.get("provider_profile_revision"),
            "model_requested": attempt.get("model_requested"),
            "model_resolved": attempt.get("model_resolved"),
            "adapter_identity": attempt.get("adapter_identity"),
            "request_hash": attempt.get("request_hash"),
            "response_hash": response.get("response_hash"),
            "qualification_response_hash": qualification.get("response_hash"),
        }
        regions = [
            {
                **copy.deepcopy(region),
                "document_ref": document["document_ref"],
                "pdf_sha256": document["pdf_sha256"],
                "page_number": page_number,
                "page_ref": page_ref,
                "detector_identity": copy.deepcopy(detector_identity),
                "detector_contract_version": PDF_TABLE_DETECTION_RESPONSE_SCHEMA,
                "model_values_used_as_source_literals": False,
            }
            for region in projection["tables"]
        ]
        private_attempt = {
            "schema_version": PDF_TABLE_DETECTION_ATTEMPT_SCHEMA,
            "request_id": request_id,
            "document_ref": document["document_ref"],
            "pdf_sha256": document["pdf_sha256"],
            "page_number": page_number,
            "page_ref": page_ref,
            "page_raster_manifest": page_raster["manifest"],
            "model_view_hash": sha256_json(model_view),
            "output_schema_hash": sha256_json(output_schema),
            "token_count": token_count,
            "provider_attempt": attempt,
            "provider_response_hash": response.get("response_hash"),
            "raw_private_response": copy.deepcopy(
                response.get("raw_private_response") or {}
            ),
            "validated_regions": copy.deepcopy(regions),
            "rejected_regions_total": 0,
            "rejected_region_reason_codes": [],
            "terminal_status": "validated",
            "hidden_retry": False,
            "provider_failover": False,
        }
        page_result = {
            "schema_version": "broker_reports_pdf_table_locator_page_v1",
            "policy_version": PDF_TABLE_LOCATOR_POLICY_VERSION,
            "document_ref": document["document_ref"],
            "pdf_sha256": document["pdf_sha256"],
            "page_number": page_number,
            "page_ref": page_ref,
            "status": "located" if regions else "located_no_tables",
            "page_bbox_pdf_points": list(page_bbox),
            "regions": regions,
            "model_values_used_as_source_literals": False,
            "pdfplumber_settings_selected_by_model": False,
        }
        if self.config.source_bound_localization_enabled:
            private_attempt["full_page_png_sha256"] = page_png_sha256
        if self.config.source_bound_localization_enabled:
            page_result["source_bound_localization_scope"] = (
                _mint_localization_scope(
                    _build_source_bound_localization_scope(
                        page_result=page_result,
                        detection_attempt=private_attempt,
                        expected_provider_profile=self.config.detector_provider_profile,
                        expected_model_id=self.config.detector_model_id,
                    )
                )
            )
        return page_result, private_attempt

    def _summary(
        self,
        *,
        status: str,
        documents_total: int,
        pages_total: int,
        candidates_total: int,
        failed_pages: list[dict[str, Any]],
        rejected_regions: list[dict[str, Any]],
        detector_qualification: dict[str, Any] | None,
    ) -> dict[str, Any]:
        safe_qualification = None
        if detector_qualification is not None:
            safe_qualification = {
                key: detector_qualification.get(key)
                for key in (
                    "status",
                    "provider_profile",
                    "provider_profile_revision",
                    "requested_model_id",
                    "resolved_model_id",
                    "exact_model_match",
                    "image_input_supported",
                    "structured_output_supported",
                    "response_hash",
                    "native_provider_transport",
                    "credentials_from_openwebui_connection",
                    "hidden_retry",
                    "provider_failover",
                )
            }
        payload = {
            "schema_version": PDF_TABLE_INTAKE_RUN_SCHEMA,
            "policy_version": PDF_TABLE_INTAKE_POLICY_VERSION,
            "enabled": self.config.enabled,
            "status": status,
            "documents_total": documents_total,
            "pages_total": pages_total,
            "candidates_total": candidates_total,
            "regions_total": candidates_total,
            "failed_pages_total": len(failed_pages),
            "failed_pages": copy.deepcopy(failed_pages),
            "rejected_regions_total": sum(
                int(item.get("rejected_regions_total") or 0)
                for item in rejected_regions
            ),
            "rejected_regions": copy.deepcopy(rejected_regions),
            "detector_region_completeness_status": (
                "partial"
                if failed_pages or rejected_regions
                else "complete"
            ),
            "detector_contract_version": PDF_TABLE_DETECTION_RESPONSE_SCHEMA,
            "locator_policy_version": PDF_TABLE_LOCATOR_POLICY_VERSION,
            "locator_projection_schema": PDF_TABLE_LOCATOR_PROJECTION_SCHEMA,
            "coordinate_contract": PDF_TABLE_LOCATOR_COORDINATE_CONTRACT,
            "detector_provider_profile": self.config.detector_provider_profile,
            "detector_model_id": self.config.detector_model_id,
            "dpi": self.config.dpi,
            "horizontal_padding_fraction": self.config.horizontal_padding_fraction,
            "vertical_padding_fraction": self.config.vertical_padding_fraction,
            "padding_basis": "legacy_configuration_retained_not_applied",
            "crop_boundary_basis": "locator_region_pdf_points",
            "detector_qualification": safe_qualification,
            "gate2_boundary_ready": status == "completed",
            "legacy_vlm_transcription_route_active": False,
            "model_values_used_as_source_literals": False,
            "pdfplumber_settings_selected_by_model": False,
            "rows_columns_cells_inferred": False,
            "financial_semantics_inferred": False,
        }
        configuration_keys = [
            "policy_version",
            "detector_contract_version",
            "locator_policy_version",
            "locator_projection_schema",
            "coordinate_contract",
            "detector_provider_profile",
            "detector_model_id",
            "dpi",
            "horizontal_padding_fraction",
            "vertical_padding_fraction",
            "padding_basis",
            "crop_boundary_basis",
        ]
        if self.config.source_bound_localization_enabled:
            payload.update(
                {
                    "source_bound_localization_enabled": True,
                    "source_bound_localization_status": (
                        "BOUND_PENDING_ADMISSION"
                        if status == "localized_pending_admission"
                        else "BLOCKED"
                    ),
                    "visual_completeness_claimed": False,
                }
            )
            configuration_keys.append("source_bound_localization_enabled")
        payload["configuration_hash"] = sha256_json(
            {key: payload[key] for key in configuration_keys}
        )
        return payload

    @staticmethod
    def _validate_documents(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for document in documents:
            if not isinstance(document, dict):
                raise PdfTableIntakeError("pdf_table_intake_document_invalid")
            document_ref = document.get("document_ref")
            pdf_bytes = document.get("pdf_bytes")
            pdf_sha256 = document.get("pdf_sha256")
            if (
                not isinstance(document_ref, str)
                or not document_ref
                or not isinstance(pdf_bytes, bytes)
                or not pdf_bytes
                or not isinstance(pdf_sha256, str)
                or hashlib.sha256(pdf_bytes).hexdigest() != pdf_sha256
            ):
                raise PdfTableIntakeError("pdf_table_intake_document_invalid")
            result.append(
                {
                    "document_ref": document_ref,
                    "pdf_bytes": pdf_bytes,
                    "pdf_sha256": pdf_sha256,
                }
            )
        return result

    @staticmethod
    def _page_count(pdf_bytes: bytes) -> int:
        try:
            import fitz
        except ImportError as exc:
            raise PdfTableIntakeError(
                "pdf_table_intake_dependency_unavailable"
            ) from exc
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            if len(document) < 1:
                raise PdfTableIntakeError("pdf_table_intake_pdf_empty")
            return len(document)
        finally:
            document.close()

    @staticmethod
    def _page_bbox(pdf_bytes: bytes, page_number: int) -> list[float]:
        import fitz

        document = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            return [round(float(value), 6) for value in document[page_number - 1].rect]
        finally:
            document.close()

    @staticmethod
    def _model_view(*, request_id: str, page_number: int) -> dict[str, Any]:
        return {
            "schema_version": PDF_TABLE_DETECTION_REQUEST_SCHEMA,
            "request_id": request_id,
            "page_number": page_number,
            "task": PDF_TABLE_LOCATOR_PROMPT,
        }


def table_detection_output_schema() -> dict[str, Any]:
    return copy.deepcopy(PDF_TABLE_LOCATOR_OUTPUT_SCHEMA)


def validate_source_bound_localization_scope(
    *,
    page_result: Any,
    detection_attempt: Any,
    expected_provider_profile: str,
    expected_model_id: str,
) -> tuple[dict[str, Any], ...]:
    """Validate the inactive locator-to-admission boundary projection.

    This proves source/provider binding and exact ordered region coverage.  It
    deliberately does not prove that a locator bbox contains a complete table.
    """

    expected = _build_source_bound_localization_scope(
        page_result=page_result,
        detection_attempt=detection_attempt,
        expected_provider_profile=expected_provider_profile,
        expected_model_id=expected_model_id,
    )
    observed = page_result.get("source_bound_localization_scope")
    if (
        not isinstance(observed, SourceBoundLocalizationScope)
        or _localization_scope_fingerprint(observed) != sha256_json(expected)
        or sha256_json(observed) != sha256_json(expected)
        or observed != expected
    ):
        raise PdfTableIntakeError("pdf_table_source_bound_localization_invalid")
    return tuple(copy.deepcopy(expected["region_admission_projection"]))


def _build_source_bound_localization_scope(
    *,
    page_result: Any,
    detection_attempt: Any,
    expected_provider_profile: str,
    expected_model_id: str,
) -> dict[str, Any]:
    if not isinstance(page_result, dict) or not isinstance(detection_attempt, dict):
        raise PdfTableIntakeError("pdf_table_source_bound_localization_invalid")
    regions = page_result.get("regions")
    attempt_regions = detection_attempt.get("validated_regions")
    raster = detection_attempt.get("page_raster_manifest")
    provider_attempt = detection_attempt.get("provider_attempt")
    if (
        page_result.get("status") not in {"located", "located_no_tables"}
        or not isinstance(regions, list)
        or not isinstance(attempt_regions, list)
        or regions != attempt_regions
        or not isinstance(raster, dict)
        or not isinstance(provider_attempt, dict)
        or detection_attempt.get("terminal_status") != "validated"
        or detection_attempt.get("document_ref") != page_result.get("document_ref")
        or detection_attempt.get("pdf_sha256") != page_result.get("pdf_sha256")
        or detection_attempt.get("page_number") != page_result.get("page_number")
        or detection_attempt.get("page_ref") != page_result.get("page_ref")
    ):
        raise PdfTableIntakeError("pdf_table_source_bound_localization_invalid")
    projection: list[dict[str, Any]] = []
    for region in regions:
        if not isinstance(region, dict):
            raise PdfTableIntakeError("pdf_table_source_bound_localization_invalid")
        region_ref = region.get("region_ref")
        bbox = region.get("bbox_pdf_points")
        if (
            not isinstance(region_ref, str)
            or not region_ref
            or not isinstance(bbox, list)
            or len(bbox) != 4
        ):
            raise PdfTableIntakeError("pdf_table_source_bound_localization_invalid")
        projection.append(
            {"region_ref": region_ref, "bbox_pdf_points": copy.deepcopy(bbox)}
        )
    region_refs = [item["region_ref"] for item in projection]
    bbox_keys = [tuple(item["bbox_pdf_points"]) for item in projection]
    if (
        len(region_refs) != len(set(region_refs))
        or len(bbox_keys) != len(set(bbox_keys))
    ):
        raise PdfTableIntakeError("pdf_table_source_bound_localization_invalid")
    required_provider = {
        "attempt_number": 1,
        "attempt_lineage": [],
        "terminal_failure_class": None,
        "finish_reason": "STOP",
        "parse_result": "parsed_object",
        "hidden_retry": False,
        "provider_failover": False,
        "crop_sha256": detection_attempt.get("full_page_png_sha256"),
        "model_view_hash": detection_attempt.get("model_view_hash"),
    }
    if any(provider_attempt.get(key) != value for key, value in required_provider.items()):
        raise PdfTableIntakeError("pdf_table_source_bound_provider_invalid")
    for key in (
        "provider_profile",
        "provider_profile_revision",
        "model_requested",
        "model_resolved",
        "request_hash",
        "canonical_schema_hash",
        "adapted_schema_hash",
        "adapter_identity",
    ):
        if not isinstance(provider_attempt.get(key), str) or not provider_attempt[key]:
            raise PdfTableIntakeError("pdf_table_source_bound_provider_invalid")
    if provider_attempt["model_requested"] != provider_attempt["model_resolved"]:
        raise PdfTableIntakeError("pdf_table_source_bound_provider_invalid")
    if (
        provider_attempt["provider_profile"] != expected_provider_profile
        or provider_attempt["model_requested"] != expected_model_id
        or provider_attempt["model_resolved"] != expected_model_id
        or provider_attempt["adapter_identity"] != PDF_GRID_PROVIDER_ADAPTER_VERSION
    ):
        raise PdfTableIntakeError("pdf_table_source_bound_provider_invalid")
    if provider_attempt["canonical_schema_hash"] != detection_attempt.get(
        "output_schema_hash"
    ):
        raise PdfTableIntakeError("pdf_table_source_bound_provider_invalid")
    for key in ("manifest_hash",):
        if not isinstance(raster.get(key), str) or not raster[key]:
            raise PdfTableIntakeError("pdf_table_source_bound_raster_invalid")
    manifest_unsigned = copy.deepcopy(raster)
    manifest_hash = manifest_unsigned.pop("manifest_hash", None)
    if manifest_hash != sha256_json(manifest_unsigned):
        raise PdfTableIntakeError("pdf_table_source_bound_raster_invalid")
    for key in ("request_hash", "response_hash"):
        if not isinstance(detection_attempt.get("token_count", {}).get(key), str):
            raise PdfTableIntakeError("pdf_table_source_bound_provider_invalid")
    if detection_attempt.get("token_count", {}).get("within_hard_guard") is not True:
        raise PdfTableIntakeError("pdf_table_source_bound_provider_invalid")
    response_hash = detection_attempt.get("provider_response_hash")
    png_hash = detection_attempt.get("full_page_png_sha256")
    if not isinstance(response_hash, str) or not response_hash or not isinstance(png_hash, str) or len(png_hash) != 64:
        raise PdfTableIntakeError("pdf_table_source_bound_provider_invalid")
    if (
        raster.get("pdf_sha256") != page_result.get("pdf_sha256")
        or raster.get("document_ref") != page_result.get("document_ref")
        or raster.get("page_number") != page_result.get("page_number")
        or raster.get("page_ref") != page_result.get("page_ref")
        or raster.get("png_sha256") != png_hash
        or raster.get("render_scope") != "full_page"
        or raster.get("full_page_identity_verified") is not True
        or raster.get("actual_page_bbox") != page_result.get("page_bbox_pdf_points")
    ):
        raise PdfTableIntakeError("pdf_table_source_bound_raster_invalid")
    unsigned = {
        "schema_version": PDF_TABLE_SOURCE_BOUND_LOCALIZATION_SCHEMA,
        "source_pdf_sha256": page_result["pdf_sha256"],
        "page_number": page_result["page_number"],
        "page_ref": page_result["page_ref"],
        "page_bbox_pdf_points": copy.deepcopy(page_result["page_bbox_pdf_points"]),
        "full_page_raster_manifest_hash": raster["manifest_hash"],
        "full_page_png_sha256": png_hash,
        "provider_profile": provider_attempt["provider_profile"],
        "provider_reported_profile_revision": provider_attempt["provider_profile_revision"],
        "model_requested": provider_attempt["model_requested"],
        "model_resolved": provider_attempt["model_resolved"],
        "provider_reported_request_hash": provider_attempt["request_hash"],
        "provider_response_hash": response_hash,
        "model_view_hash": detection_attempt["model_view_hash"],
        "canonical_schema_hash": provider_attempt["canonical_schema_hash"],
        "provider_reported_adapted_schema_hash": provider_attempt["adapted_schema_hash"],
        "adapter_identity": provider_attempt["adapter_identity"],
        "count_request_hash": detection_attempt["token_count"]["request_hash"],
        "count_response_hash": detection_attempt["token_count"]["response_hash"],
        "attempt_number": 1,
        "attempt_lineage": [],
        "finish_reason": "STOP",
        "hidden_retry": False,
        "provider_failover": False,
        "ordered_region_refs": region_refs,
        "region_admission_projection": projection,
        "admission_request_status": (
            "READY_FOR_PR1_BUILDER" if projection else "NOT_REQUIRED_NO_REGIONS"
        ),
        "visual_completeness_claimed": False,
    }
    return {**unsigned, "scope_checksum": sha256_json(unsigned)}
