from __future__ import annotations

import base64
import copy
import hashlib
import math
from dataclasses import dataclass
from typing import Any

from .contracts import stable_digest
from .pdf_grid_experiment_provider import (
    PdfGridExperimentProviderFactory,
    PdfGridProviderConfig,
    PdfGridProviderError,
)
from .pdf_hybrid_contracts import sha256_json
from .pdf_table_raster import (
    PDF_TABLE_CANDIDATE_RASTER_POLICY_VERSION,
    PDF_TABLE_CANDIDATE_SCHEMA,
    PdfTableRasterConfig,
    PdfTableRasterError,
    PdfTableRasterFactory,
)


PDF_TABLE_DETECTION_REQUEST_SCHEMA = "broker_reports_pdf_table_detection_request_v2"
PDF_TABLE_DETECTION_RESPONSE_SCHEMA = "broker_reports_pdf_table_detection_response_v1"
PDF_TABLE_DETECTION_ATTEMPT_SCHEMA = "broker_reports_pdf_table_detection_attempt_v1"
PDF_TABLE_INTAKE_RUN_SCHEMA = "broker_reports_pdf_table_intake_run_v1"
PDF_TABLE_INTAKE_POLICY_VERSION = "pdf_table_intake_policy_v2"
FACTORY_REQUIRED = (
    "PdfTableIntakeRuntimeFactory.create_for_openwebui is the only supported "
    "live PDF table detection and crop entrypoint"
)
FORBIDDEN = (
    "The Pipe and operator smoke must not call a VLM adapter or raster renderer "
    "directly; Gate 1 must not infer rows, columns, cells, values, or financial semantics"
)


class PdfTableIntakeError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PdfTableIntakeConfig:
    enabled: bool = False
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


class PdfTableIntakeRuntimeFactory:
    def __init__(self, config: PdfTableIntakeConfig | None = None) -> None:
        self.config = config or PdfTableIntakeConfig()
        self._validate_config()

    def create_for_openwebui(self, request: Any) -> "PdfTableIntakeRuntime":
        provider = PdfGridExperimentProviderFactory(
            PdfGridProviderConfig(
                provider_profile=self.config.detector_provider_profile,
                model_id=self.config.detector_model_id,
            )
        ).create_for_openwebui(request)
        return self._create(provider)

    def create_with_provider(self, provider: Any) -> "PdfTableIntakeRuntime":
        """Explicit external-provider seam for deterministic contract tests."""

        return self._create(provider)

    def _create(self, provider: Any) -> "PdfTableIntakeRuntime":
        raster = PdfTableRasterFactory(
            PdfTableRasterConfig(
                horizontal_padding_fraction=(
                    self.config.horizontal_padding_fraction
                ),
                vertical_padding_fraction=self.config.vertical_padding_fraction,
            )
        ).create()
        return PdfTableIntakeRuntime(self.config, provider, raster)

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
    def __init__(self, config: PdfTableIntakeConfig, provider: Any, raster: Any) -> None:
        self.config = config
        self.provider = provider
        self.raster = raster

    def run(self, documents: list[dict[str, Any]]) -> PdfTableIntakeResult:
        if not self.config.enabled:
            return PdfTableIntakeResult(
                safe_summary=self._summary(
                    status="disabled",
                    documents_total=0,
                    pages_total=0,
                    candidates_total=0,
                    failed_pages=[],
                    detector_qualification=None,
                ),
                private_candidates=[],
                private_detection_attempts=[],
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
                    detector_qualification=None,
                ),
                private_candidates=[],
                private_detection_attempts=[],
            )
        try:
            qualification = self.provider.qualify()
        except Exception as exc:
            raise PdfTableIntakeError("pdf_table_detector_qualification_failed") from exc
        if qualification.get("status") != "qualified":
            raise PdfTableIntakeError("pdf_table_detector_not_qualified")

        candidates: list[dict[str, Any]] = []
        attempts: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        pages_total = 0
        for document in normalized_documents:
            page_count = self._page_count(document["pdf_bytes"])
            pages_total += page_count
            if pages_total > self.config.maximum_pages:
                raise PdfTableIntakeError("pdf_table_intake_page_budget_exceeded")
            for page_number in range(1, page_count + 1):
                try:
                    page_candidates, attempt = self._run_page(
                        document=document,
                        page_number=page_number,
                        qualification=qualification,
                    )
                    candidates.extend(page_candidates)
                    attempts.append(attempt)
                except (PdfTableIntakeError, PdfTableRasterError, PdfGridProviderError) as exc:
                    code = getattr(exc, "code", "pdf_table_intake_page_failed")
                    failures.append(
                        {
                            "document_ref": document["document_ref"],
                            "page_number": page_number,
                            "failure_code": str(code),
                        }
                    )

        status = "completed" if not failures else "failed"
        return PdfTableIntakeResult(
            safe_summary=self._summary(
                status=status,
                documents_total=len(normalized_documents),
                pages_total=pages_total,
                candidates_total=len(candidates),
                failed_pages=failures,
                detector_qualification=qualification,
            ),
            private_candidates=candidates,
            private_detection_attempts=attempts,
        )

    def _run_page(
        self,
        *,
        document: dict[str, Any],
        page_number: int,
        qualification: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
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
        regions = validate_table_detection_output(
            response.get("json_output"),
            request_id=request_id,
            maximum_candidates=self.config.maximum_candidates_per_page,
        )
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
        page_candidates = []
        for region in regions:
            candidate_ref = "pdftable_" + stable_digest(
                [
                    PDF_TABLE_CANDIDATE_SCHEMA,
                    document["pdf_sha256"],
                    page_number,
                    region,
                    self.config.horizontal_padding_fraction,
                    self.config.vertical_padding_fraction,
                    self.config.dpi,
                ],
                length=24,
            )
            rendered = self.raster.render_detected_region(
                pdf_bytes=document["pdf_bytes"],
                pdf_sha256=document["pdf_sha256"],
                document_ref=document["document_ref"],
                page_number=page_number,
                candidate_ref=candidate_ref,
                detected_bbox_normalized=region,
                detector_contract_version=PDF_TABLE_DETECTION_RESPONSE_SCHEMA,
                detector_identity=detector_identity,
                dpi=self.config.dpi,
            )
            page_candidates.append(rendered)
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
            "terminal_status": "validated",
            "hidden_retry": False,
            "provider_failover": False,
        }
        return page_candidates, private_attempt

    def _summary(
        self,
        *,
        status: str,
        documents_total: int,
        pages_total: int,
        candidates_total: int,
        failed_pages: list[dict[str, Any]],
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
            "failed_pages_total": len(failed_pages),
            "failed_pages": copy.deepcopy(failed_pages),
            "detector_contract_version": PDF_TABLE_DETECTION_RESPONSE_SCHEMA,
            "candidate_contract_version": PDF_TABLE_CANDIDATE_SCHEMA,
            "raster_policy_version": PDF_TABLE_CANDIDATE_RASTER_POLICY_VERSION,
            "detector_provider_profile": self.config.detector_provider_profile,
            "detector_model_id": self.config.detector_model_id,
            "dpi": self.config.dpi,
            "horizontal_padding_fraction": self.config.horizontal_padding_fraction,
            "vertical_padding_fraction": self.config.vertical_padding_fraction,
            "padding_basis": "page_dimensions_per_side",
            "detector_qualification": safe_qualification,
            "gate2_boundary_ready": status == "completed",
            "rows_columns_cells_inferred": False,
            "financial_semantics_inferred": False,
        }
        payload["configuration_hash"] = sha256_json(
            {
                key: payload[key]
                for key in (
                    "policy_version",
                    "detector_contract_version",
                    "candidate_contract_version",
                    "raster_policy_version",
                    "detector_provider_profile",
                    "detector_model_id",
                    "dpi",
                    "horizontal_padding_fraction",
                    "vertical_padding_fraction",
                    "padding_basis",
                )
            }
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
            raise PdfTableIntakeError("pdf_table_intake_dependency_unavailable") from exc
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
            "task": "detect_table_regions_only",
            "instructions": [
                "Inspect the entire page image and return every visible table region.",
                "A table can be ruled or borderless. Sparse but aligned content is evidence of rows or columns.",
                "Return the OUTER boundary of the complete table, never an interior numeric or data-only rectangle.",
                "The left boundary must include the leftmost row label or first column, and the right boundary must include the rightmost label, value, or border.",
                "Include the complete title, all header rows, all visible data rows, totals, footnotes, currency symbols, and edge labels that visually belong to the table.",
                "For a continued multi-page table, include the complete visible continuation from its repeated header through its last visible row or total on this page.",
                "Do not split one physical table into arbitrary panels. Separate only side-by-side tables that have independent headings or outer borders.",
                "If a table border, header, row label, or row content reaches a page edge, use coordinate 0 or 1 for that edge.",
                "Before answering, verify that no title, header, first label, last label, outer border, continuation row, or total lies outside the bbox.",
                "Return normalized page coordinates for the complete visual table. Deterministic padding is only a safety margin and must not compensate for an incomplete boundary.",
                "Do not read, normalize, summarize, translate, or interpret cell values.",
                "Do not infer rows, columns, cells, financial meaning, or a canonical table.",
                "If a table boundary cannot be located reliably, return table_presence=uncertain and no regions.",
            ],
            "coordinate_contract": {
                "space": "normalized_page_top_left",
                "order": ["x0", "y0", "x1", "y1"],
                "range": [0, 1],
            },
        }


def table_detection_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "request_id",
            "table_presence",
            "regions",
        ],
        "properties": {
            "schema_version": {
                "type": "string",
                "enum": [PDF_TABLE_DETECTION_RESPONSE_SCHEMA],
            },
            "request_id": {"type": "string"},
            "table_presence": {
                "type": "string",
                "enum": ["present", "absent", "uncertain"],
            },
            "regions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["bbox_normalized"],
                    "properties": {
                        "bbox_normalized": {
                            "type": "array",
                            "minItems": 4,
                            "maxItems": 4,
                            "items": {"type": "number", "minimum": 0, "maximum": 1},
                        }
                    },
                },
            },
        },
    }


def validate_table_detection_output(
    value: Any,
    *,
    request_id: str,
    maximum_candidates: int,
) -> list[list[float]]:
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "request_id",
        "table_presence",
        "regions",
    }:
        raise PdfTableIntakeError("pdf_table_detector_output_shape_invalid")
    if value.get("schema_version") != PDF_TABLE_DETECTION_RESPONSE_SCHEMA:
        raise PdfTableIntakeError("pdf_table_detector_schema_mismatch")
    if value.get("request_id") != request_id:
        raise PdfTableIntakeError("pdf_table_detector_request_mismatch")
    presence = value.get("table_presence")
    raw_regions = value.get("regions")
    if presence not in {"present", "absent", "uncertain"} or not isinstance(
        raw_regions, list
    ):
        raise PdfTableIntakeError("pdf_table_detector_presence_invalid")
    if presence == "uncertain":
        if raw_regions:
            raise PdfTableIntakeError("pdf_table_detector_uncertain_regions_present")
        raise PdfTableIntakeError("pdf_table_detector_boundary_uncertain")
    if presence == "absent":
        if raw_regions:
            raise PdfTableIntakeError("pdf_table_detector_absent_regions_present")
        return []
    if not raw_regions or len(raw_regions) > maximum_candidates:
        raise PdfTableIntakeError("pdf_table_detector_candidate_count_invalid")
    regions: list[list[float]] = []
    for region in raw_regions:
        if not isinstance(region, dict) or set(region) != {"bbox_normalized"}:
            raise PdfTableIntakeError("pdf_table_detector_region_shape_invalid")
        bbox = region.get("bbox_normalized")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise PdfTableIntakeError("pdf_table_detector_bbox_invalid")
        if not all(
            isinstance(item, (int, float))
            and not isinstance(item, bool)
            and math.isfinite(float(item))
            for item in bbox
        ):
            raise PdfTableIntakeError("pdf_table_detector_bbox_invalid")
        normalized = [round(float(item), 9) for item in bbox]
        x0, y0, x1, y1 = normalized
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            raise PdfTableIntakeError("pdf_table_detector_bbox_invalid")
        regions.append(normalized)
    regions.sort(key=lambda item: (item[1], item[0], item[3], item[2]))
    for index, left in enumerate(regions):
        for right in regions[index + 1 :]:
            if _intersection_over_union(left, right) >= 0.8:
                raise PdfTableIntakeError("pdf_table_detector_regions_ambiguous")
    return regions


def _intersection_over_union(left: list[float], right: list[float]) -> float:
    width = max(0.0, min(left[2], right[2]) - max(left[0], right[0]))
    height = max(0.0, min(left[3], right[3]) - max(left[1], right[1]))
    intersection = width * height
    left_area = (left[2] - left[0]) * (left[3] - left[1])
    right_area = (right[2] - right[0]) * (right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union > 0 else 0.0
