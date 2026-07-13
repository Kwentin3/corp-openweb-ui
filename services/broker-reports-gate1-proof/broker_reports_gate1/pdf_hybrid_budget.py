from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .pdf_hybrid_contracts import canonical_json_bytes, sha256_json


PDF_HYBRID_BUDGET_SCHEMA = "broker_reports_pdf_hybrid_image_context_budget_v2"
PDF_HYBRID_BUDGET_POLICY_VERSION = "pdf_hybrid_image_context_budget_policy_v2"
FACTORY_REQUIRED = (
    "PdfHybridBudgetFactory.create is the only image-inclusive hybrid budget entrypoint"
)
FORBIDDEN = (
    "Provider calls must not bypass the static guard, provider countTokens guard, or calibration record"
)


class PdfHybridBudgetError(ValueError):
    def __init__(self, code: str, *, accounting: dict[str, Any] | None = None) -> None:
        self.code = code
        self.accounting = accounting or {}
        super().__init__(code)


@dataclass(frozen=True)
class PdfHybridBudgetConfig:
    policy_version: str = PDF_HYBRID_BUDGET_POLICY_VERSION
    maximum_candidates_per_window: int = 192
    maximum_rows_per_window: int = 12
    maximum_columns: int = 24
    maximum_grid_positions_per_window: int = 288
    maximum_model_text_bytes: int = 48 * 1024
    maximum_estimated_input_tokens: int = 18_000
    maximum_counted_input_tokens: int = 20_000
    provider_input_safety_margin_tokens: int = 2_000
    maximum_provider_input_tokens: int = 24_000
    maximum_output_tokens: int = 8_192
    maximum_calibration_error_ratio: float = 0.10
    conservative_utf8_bytes_per_token: float = 2.5


class PdfHybridBudgetFactory:
    def __init__(self, config: PdfHybridBudgetConfig | None = None) -> None:
        self.config = config or PdfHybridBudgetConfig()

    def create(self) -> "PdfHybridBudgetGuard":
        if self.config.policy_version != PDF_HYBRID_BUDGET_POLICY_VERSION:
            raise PdfHybridBudgetError("pdf_hybrid_budget_policy_invalid")
        if (
            self.config.maximum_counted_input_tokens
            + self.config.provider_input_safety_margin_tokens
            > self.config.maximum_provider_input_tokens
        ):
            raise PdfHybridBudgetError("pdf_hybrid_budget_margin_invalid")
        return PdfHybridBudgetGuard(self.config)


class PdfHybridBudgetGuard:
    def __init__(self, config: PdfHybridBudgetConfig) -> None:
        self.config = config

    def estimate(
        self,
        *,
        model_facing: dict[str, Any],
        output_schema: dict[str, Any],
        crop_manifest: dict[str, Any],
        candidate_count: int,
        row_count: int,
        column_count: int,
    ) -> dict[str, Any]:
        model_bytes = len(canonical_json_bytes(model_facing))
        schema_bytes = len(canonical_json_bytes(output_schema))
        text_tokens = math.ceil(
            model_bytes / self.config.conservative_utf8_bytes_per_token
        )
        schema_tokens = math.ceil(
            schema_bytes / self.config.conservative_utf8_bytes_per_token
        )
        width = int(crop_manifest.get("width") or 0)
        height = int(crop_manifest.get("height") or 0)
        dpi = int(crop_manifest.get("dpi") or 0)
        image_tokens, image_tiles = _gemini_image_token_estimate(width, height)
        expected_output_tokens = min(
            self.config.maximum_output_tokens,
            192 + row_count * column_count * 7 + candidate_count * 2,
        )
        estimated_input = text_tokens + schema_tokens + image_tokens
        failures = []
        checks = [
            (
                candidate_count > self.config.maximum_candidates_per_window,
                "pdf_hybrid_window_candidate_budget_exceeded",
            ),
            (
                row_count > self.config.maximum_rows_per_window,
                "pdf_hybrid_window_row_budget_exceeded",
            ),
            (
                column_count > self.config.maximum_columns,
                "pdf_hybrid_window_column_budget_exceeded",
            ),
            (
                row_count * column_count
                > self.config.maximum_grid_positions_per_window,
                "pdf_hybrid_window_grid_budget_exceeded",
            ),
            (
                model_bytes > self.config.maximum_model_text_bytes,
                "pdf_hybrid_window_text_bytes_budget_exceeded",
            ),
            (
                estimated_input > self.config.maximum_estimated_input_tokens,
                "pdf_hybrid_window_static_input_budget_exceeded",
            ),
        ]
        failures.extend(code for failed, code in checks if failed)
        result = {
            "schema_version": PDF_HYBRID_BUDGET_SCHEMA,
            "policy_version": self.config.policy_version,
            "image_width": width,
            "image_height": height,
            "image_dpi": dpi,
            "image_pixels": width * height,
            "image_bytes": int(crop_manifest.get("png_bytes") or 0),
            "image_tile_estimate": image_tiles,
            "estimated_image_tokens": image_tokens,
            "model_facing_text_bytes": model_bytes,
            "schema_bytes": schema_bytes,
            "estimated_model_text_tokens": text_tokens,
            "estimated_schema_tokens": schema_tokens,
            "estimated_input_tokens": estimated_input,
            "candidate_count": candidate_count,
            "row_count": row_count,
            "column_count": column_count,
            "grid_positions": row_count * column_count,
            "expected_output_tokens": expected_output_tokens,
            "requested_maximum_output_tokens": self.config.maximum_output_tokens,
            "maximum_counted_input_tokens": self.config.maximum_counted_input_tokens,
            "provider_input_safety_margin_tokens": self.config.provider_input_safety_margin_tokens,
            "maximum_provider_input_tokens": self.config.maximum_provider_input_tokens,
            "hard_budget_failure_codes": sorted(failures),
            "static_pre_provider_budget_passed": not failures,
            "provider_counted_input_tokens": None,
            "provider_counted_budget_passed": None,
            "provider_actual_input_tokens": None,
            "counted_to_actual_error_tokens": None,
            "counted_to_actual_error_ratio": None,
            "estimator_calibration_passed": None,
        }
        result["budget_checksum"] = sha256_json(result)
        return result

    def require_static(self, accounting: dict[str, Any]) -> None:
        failures = list(accounting.get("hard_budget_failure_codes") or [])
        if failures:
            raise PdfHybridBudgetError(str(failures[0]), accounting=accounting)

    def apply_provider_count(
        self,
        accounting: dict[str, Any],
        *,
        counted_input_tokens: int,
        modality_token_counts: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        result = dict(accounting)
        counted = int(counted_input_tokens)
        passed = (
            counted <= self.config.maximum_counted_input_tokens
            and counted + self.config.provider_input_safety_margin_tokens
            <= self.config.maximum_provider_input_tokens
        )
        result["provider_counted_input_tokens"] = counted
        result["provider_counted_modality_tokens"] = list(
            modality_token_counts or []
        )
        result["provider_counted_budget_passed"] = passed
        failures = set(result.get("hard_budget_failure_codes") or [])
        if not passed:
            failures.add("pdf_hybrid_provider_counted_input_budget_exceeded")
        result["hard_budget_failure_codes"] = sorted(failures)
        result["budget_checksum"] = sha256_json(
            {key: value for key, value in result.items() if key != "budget_checksum"}
        )
        return result

    def require_provider_count(self, accounting: dict[str, Any]) -> None:
        if accounting.get("provider_counted_budget_passed") is not True:
            raise PdfHybridBudgetError(
                "pdf_hybrid_provider_counted_input_budget_exceeded",
                accounting=accounting,
            )

    def reconcile_actual(
        self,
        accounting: dict[str, Any],
        *,
        actual_input_tokens: int | None,
    ) -> dict[str, Any]:
        result = dict(accounting)
        counted = result.get("provider_counted_input_tokens")
        if not isinstance(actual_input_tokens, int) or not isinstance(counted, int):
            result["provider_actual_input_tokens"] = actual_input_tokens
            result["estimator_calibration_passed"] = False
            result["calibration_failure_code"] = (
                "pdf_hybrid_provider_token_calibration_usage_missing"
            )
        else:
            error = actual_input_tokens - counted
            ratio = abs(error) / max(1, actual_input_tokens)
            result["provider_actual_input_tokens"] = actual_input_tokens
            result["counted_to_actual_error_tokens"] = error
            result["counted_to_actual_error_ratio"] = round(ratio, 6)
            result["estimator_calibration_passed"] = (
                ratio <= self.config.maximum_calibration_error_ratio
            )
            result["calibration_failure_code"] = (
                None
                if result["estimator_calibration_passed"]
                else "pdf_hybrid_provider_token_calibration_error_exceeded"
            )
        result["budget_checksum"] = sha256_json(
            {key: value for key, value in result.items() if key != "budget_checksum"}
        )
        return result


def _gemini_image_token_estimate(width: int, height: int) -> tuple[int, int]:
    if width <= 0 or height <= 0:
        return 0, 0
    if width <= 384 and height <= 384:
        return 258, 1
    crop_unit = max(1, math.floor(min(width, height) / 1.5))
    tiles = math.ceil(width / crop_unit) * math.ceil(height / crop_unit)
    return tiles * 258, tiles
