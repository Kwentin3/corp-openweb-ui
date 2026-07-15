from __future__ import annotations

import copy
import math
import re
from dataclasses import dataclass
from typing import Any, Iterable

from .pdf_hybrid_contracts import sha256_json


FACTORY_REQUIRED = (
    "PdfVlmProductRouterFactory.create is the only product-routing runtime "
    "entrypoint"
)
FORBIDDEN = (
    "Product routing must not use page_ref, PDF hashes, filenames, human labels, "
    "development references, or legacy morphology eligibility as decision inputs"
)

PDF_VLM_PRODUCT_ROUTE_SCHEMA = "broker_reports_pdf_vlm_product_route_v1"
PDF_VLM_PRODUCT_ROUTE_POLICY = "pdf_vlm_product_route_v1"

PRODUCT_ROUTES = frozenset(
    {
        "candidate_crop",
        "page_level",
        "skip_obvious_non_table",
        "upstream_failure",
    }
)
DETECTION_RESULTS = frozenset(
    {
        "plausible",
        "implausible",
        "uncertain",
        "absent_due_to_upstream_failure",
    }
)

_FACTORY_TOKEN = object()
_REASON_CODE = re.compile(r"^[a-z][a-z0-9_]{2,95}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_NUMBER_TOKEN = re.compile(r"\d")
_WHITESPACE = re.compile(r"\s+")
_NON_WORD = re.compile(r"[^a-z0-9]+")

_SCHEDULE_INTRODUCERS: tuple[tuple[str, str], ...] = (
    ("following table", "following_table"),
    ("following schedule", "following_schedule"),
    ("consisted of the following", "consisted_of_following"),
    ("consists of the following", "consists_of_following"),
    ("represented by the following", "represented_by_following"),
)
_FINANCIAL_SCHEDULE_TERMS: tuple[tuple[str, str], ...] = (
    ("credit losses", "credit_losses"),
    ("fair value", "fair_value"),
    ("fixed assets", "fixed_assets"),
    ("lease liabilities", "lease_liabilities"),
    ("receivables", "receivables"),
    ("payables", "payables"),
    ("allowance", "allowance"),
    ("assets", "assets"),
    ("liabilities", "liabilities"),
    ("maturities", "maturities"),
    ("securities", "securities"),
    ("balance", "balance"),
)

_OBSERVATION_KEYS = {
    "page_words_total",
    "candidate_present",
    "candidate_strategy",
    "candidate_rows_total",
    "candidate_columns_total",
    "candidate_cells_total",
    "candidate_populated_cells_total",
    "candidate_words_total",
    "candidate_area_ratio",
    "broad_aligned_region",
    "ruled_candidate",
    "numeric_candidate_words_total",
    "axis_numeric_candidate_words_total",
    "repeated_numeric_axes_total",
    "maximum_repeated_numeric_axis_words",
    "repeated_numeric_axis_present",
    "schedule_introducer_codes",
    "financial_schedule_term_codes",
    "financial_schedule_signal_present",
    "table_of_contents_marker_present",
    "upstream_failure_reasons_total",
}


class PdfVlmProductRouterError(ValueError):
    def __init__(self, code: str, subject: str = "") -> None:
        self.code = code
        self.subject = subject
        super().__init__(code if not subject else f"{code}:{subject}")


@dataclass(frozen=True)
class PdfVlmProductRouterConfig:
    policy_version: str = PDF_VLM_PRODUCT_ROUTE_POLICY
    broad_candidate_area_ratio: float = 0.35
    minimum_schedule_numeric_words: int = 2
    minimum_repeated_numeric_axis_words: int = 4
    minimum_repeated_numeric_axis_rows: int = 4
    numeric_axis_tolerance_points: float = 2.0


class PdfVlmProductRouterFactory:
    def __init__(self, config: PdfVlmProductRouterConfig | None = None) -> None:
        self.config = config or PdfVlmProductRouterConfig()

    def create(self) -> "PdfVlmProductRouter":
        if self.config.policy_version != PDF_VLM_PRODUCT_ROUTE_POLICY:
            raise PdfVlmProductRouterError(
                "pdf_vlm_product_router_policy_invalid"
            )
        if not (
            _positive_ratio(self.config.broad_candidate_area_ratio)
            and self.config.broad_candidate_area_ratio < 1.0
            and _positive_int(self.config.minimum_schedule_numeric_words)
            and _positive_int(self.config.minimum_repeated_numeric_axis_words)
            and _positive_int(self.config.minimum_repeated_numeric_axis_rows)
            and _positive_number(self.config.numeric_axis_tolerance_points)
        ):
            raise PdfVlmProductRouterError(
                "pdf_vlm_product_router_config_invalid"
            )
        return PdfVlmProductRouter(
            config=self.config,
            _factory_token=_FACTORY_TOKEN,
        )


class PdfVlmProductRouter:
    def __init__(
        self,
        config: PdfVlmProductRouterConfig | None = None,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise PdfVlmProductRouterError(
                "pdf_vlm_product_router_factory_required"
            )
        self.config = config or PdfVlmProductRouterConfig()

    def route(
        self,
        *,
        page_evidence: dict[str, Any] | None,
        candidate_evidence: dict[str, Any] | None,
        page_words: list[dict[str, Any]],
        bbox_inventory: list[dict[str, Any]],
        upstream_failure_reason_codes: Iterable[str] = (),
    ) -> dict[str, Any]:
        upstream_reasons = _reason_codes(upstream_failure_reason_codes)
        if upstream_reasons:
            return self._result(
                route="upstream_failure",
                detection="absent_due_to_upstream_failure",
                reason_codes=upstream_reasons,
                observations=_empty_observations(
                    upstream_failure_reasons_total=len(upstream_reasons)
                ),
                evidence_checksum=sha256_json(
                    {"upstream_failure_reason_codes": upstream_reasons}
                ),
            )

        normalized = self._normalize_evidence(
            page_evidence=page_evidence,
            candidate_evidence=candidate_evidence,
            page_words=page_words,
            bbox_inventory=bbox_inventory,
        )
        if normalized["failure_reason_codes"]:
            reasons = normalized["failure_reason_codes"]
            return self._result(
                route="upstream_failure",
                detection="absent_due_to_upstream_failure",
                reason_codes=reasons,
                observations=_empty_observations(
                    upstream_failure_reasons_total=len(reasons)
                ),
                evidence_checksum=normalized["evidence_checksum"],
            )

        observations = self._observations(normalized)
        if observations["table_of_contents_marker_present"]:
            route = "skip_obvious_non_table"
            detection = "implausible"
            reasons = ["table_of_contents_marker_present"]
        elif observations["ruled_candidate"]:
            route = "candidate_crop"
            detection = "plausible"
            reasons = ["ruled_candidate_geometry_present"]
        elif (
            observations["financial_schedule_signal_present"]
            and observations["broad_aligned_region"]
        ):
            route = "page_level"
            detection = "uncertain"
            reasons = ["broad_region_contains_objective_schedule_signal"]
        elif observations["repeated_numeric_axis_present"]:
            route = "candidate_crop"
            detection = "plausible"
            reasons = ["repeated_numeric_axis_present"]
        elif observations["financial_schedule_signal_present"]:
            if not observations["candidate_present"]:
                route = "page_level"
                reasons = ["broad_region_contains_objective_schedule_signal"]
            else:
                route = "candidate_crop"
                reasons = ["bounded_region_contains_objective_schedule_signal"]
            detection = "uncertain"
        else:
            route = "skip_obvious_non_table"
            detection = "implausible"
            reasons = ["objective_table_signal_absent"]

        return self._result(
            route=route,
            detection=detection,
            reason_codes=reasons,
            observations=observations,
            evidence_checksum=normalized["evidence_checksum"],
        )

    def validate_result(self, result: dict[str, Any]) -> None:
        if not isinstance(result, dict):
            raise PdfVlmProductRouterError(
                "pdf_vlm_product_route_result_invalid"
            )
        expected_keys = {
            "schema_version",
            "policy_version",
            "route",
            "detection",
            "provider_call_allowed",
            "reason_codes",
            "observations",
            "evidence_checksum",
            "routing_checksum",
        }
        if set(result) != expected_keys:
            raise PdfVlmProductRouterError(
                "pdf_vlm_product_route_keys_invalid"
            )
        if (
            result.get("schema_version") != PDF_VLM_PRODUCT_ROUTE_SCHEMA
            or result.get("policy_version") != self.config.policy_version
            or result.get("route") not in PRODUCT_ROUTES
            or result.get("detection") not in DETECTION_RESULTS
        ):
            raise PdfVlmProductRouterError(
                "pdf_vlm_product_route_contract_invalid"
            )
        reasons = result.get("reason_codes")
        if (
            not isinstance(reasons, list)
            or not reasons
            or reasons != sorted(set(reasons))
            or any(not _REASON_CODE.fullmatch(str(item)) for item in reasons)
        ):
            raise PdfVlmProductRouterError(
                "pdf_vlm_product_route_reason_codes_invalid"
            )
        observations = result.get("observations")
        if not isinstance(observations, dict) or set(observations) != _OBSERVATION_KEYS:
            raise PdfVlmProductRouterError(
                "pdf_vlm_product_route_observations_invalid"
            )
        if not isinstance(result.get("provider_call_allowed"), bool):
            raise PdfVlmProductRouterError(
                "pdf_vlm_product_route_provider_authority_invalid"
            )
        expected_terminal = {
            "candidate_crop": ({"plausible", "uncertain"}, True),
            "page_level": ({"uncertain"}, True),
            "skip_obvious_non_table": ({"implausible"}, False),
            "upstream_failure": ({"absent_due_to_upstream_failure"}, False),
        }[str(result["route"])]
        if (
            result["detection"] not in expected_terminal[0]
            or result["provider_call_allowed"] is not expected_terminal[1]
        ):
            raise PdfVlmProductRouterError(
                "pdf_vlm_product_route_terminal_invalid"
            )
        if not _SHA256.fullmatch(str(result.get("evidence_checksum") or "")):
            raise PdfVlmProductRouterError(
                "pdf_vlm_product_route_evidence_checksum_invalid"
            )
        checksum = str(result.get("routing_checksum") or "")
        material = copy.deepcopy(result)
        material.pop("routing_checksum", None)
        if not _SHA256.fullmatch(checksum) or checksum != sha256_json(material):
            raise PdfVlmProductRouterError(
                "pdf_vlm_product_route_checksum_invalid"
            )

    def _normalize_evidence(
        self,
        *,
        page_evidence: dict[str, Any] | None,
        candidate_evidence: dict[str, Any] | None,
        page_words: list[dict[str, Any]],
        bbox_inventory: list[dict[str, Any]],
    ) -> dict[str, Any]:
        failures: set[str] = set()
        page = page_evidence if isinstance(page_evidence, dict) else {}
        width = _finite_number(page.get("layout_page_width"))
        height = _finite_number(page.get("layout_page_height"))
        if width is None or height is None or width <= 0.0 or height <= 0.0:
            failures.add("pdf_vlm_product_routing_page_geometry_missing")
        if str(page.get("layout_projection_status") or "") not in {
            "complete",
            "partial",
        }:
            failures.add("pdf_vlm_product_routing_page_evidence_unusable")

        bbox_by_ref: dict[str, list[float]] = {}
        if not isinstance(bbox_inventory, list):
            failures.add("pdf_vlm_product_routing_bbox_inventory_invalid")
        else:
            for item in bbox_inventory:
                if not isinstance(item, dict):
                    failures.add("pdf_vlm_product_routing_bbox_inventory_invalid")
                    continue
                ref = str(item.get("bbox_ref") or "")
                bbox = _bbox(item.get("bbox"))
                if not ref:
                    failures.add("pdf_vlm_product_routing_bbox_inventory_invalid")
                    continue
                if bbox is None:
                    # The full parser inventory also contains legitimate
                    # zero-height/zero-width vector boxes. They are irrelevant
                    # here unless a routed word or candidate refers to one.
                    continue
                if ref in bbox_by_ref:
                    failures.add("pdf_vlm_product_routing_bbox_inventory_invalid")
                    continue
                bbox_by_ref[ref] = bbox

        normalized_words: list[dict[str, Any]] = []
        words_by_ref: dict[str, dict[str, Any]] = {}
        if not isinstance(page_words, list):
            failures.add("pdf_vlm_product_routing_page_words_invalid")
        else:
            for ordinal, item in enumerate(page_words, start=1):
                if not isinstance(item, dict):
                    failures.add("pdf_vlm_product_routing_page_words_invalid")
                    continue
                word_ref = str(item.get("word_ref") or "")
                bbox = bbox_by_ref.get(str(item.get("bbox_ref") or ""))
                text = item.get("text")
                order = item.get("geometry_reading_order")
                if (
                    not word_ref
                    or word_ref in words_by_ref
                    or bbox is None
                    or not isinstance(text, str)
                    or isinstance(order, bool)
                    or not isinstance(order, int)
                    or order < 1
                ):
                    failures.add("pdf_vlm_product_routing_page_words_invalid")
                    continue
                normalized = {
                    "word_ref": word_ref,
                    "text": text,
                    "bbox": bbox,
                    "order": order,
                    "source_ordinal": ordinal,
                }
                words_by_ref[word_ref] = normalized
                normalized_words.append(normalized)
        if not normalized_words:
            failures.add("pdf_vlm_product_routing_page_words_missing")
        normalized_words.sort(key=lambda item: (item["order"], item["source_ordinal"]))

        candidate: dict[str, Any] | None = None
        candidate_words: list[dict[str, Any]] = []
        candidate_bbox: list[float] | None = None
        if candidate_evidence is not None:
            if not isinstance(candidate_evidence, dict):
                failures.add("pdf_vlm_product_routing_candidate_invalid")
            else:
                refs = candidate_evidence.get("contributing_word_refs")
                if (
                    not isinstance(refs, list)
                    or any(not isinstance(item, str) or not item for item in refs)
                    or len(refs) != len(set(refs))
                    or any(item not in words_by_ref for item in refs)
                ):
                    failures.add("pdf_vlm_product_routing_candidate_word_scope_invalid")
                    refs = []
                candidate_words = [words_by_ref[item] for item in refs]
                candidate_words.sort(
                    key=lambda item: (item["order"], item["source_ordinal"])
                )
                candidate_bbox = bbox_by_ref.get(
                    str(candidate_evidence.get("bbox_ref") or "")
                )
                if candidate_bbox is None:
                    failures.add("pdf_vlm_product_routing_candidate_bbox_invalid")
                rows = _positive_int_value(candidate_evidence.get("rows_total"))
                columns = _positive_int_value(candidate_evidence.get("columns_total"))
                cells = _positive_int_value(candidate_evidence.get("cells_total"))
                cell_inventory = candidate_evidence.get("cell_inventory")
                if rows is None or columns is None or cells is None:
                    failures.add("pdf_vlm_product_routing_candidate_shape_invalid")
                if not isinstance(cell_inventory, list):
                    failures.add("pdf_vlm_product_routing_candidate_cells_invalid")
                    cell_inventory = []
                strategy = str(candidate_evidence.get("table_strategy_ref") or "")
                if strategy not in {
                    "aligned_text_v0",
                    "ruled_lines_v0",
                    "mixed_geometry_v0",
                    "repeated_x_columns_v0",
                }:
                    failures.add("pdf_vlm_product_routing_candidate_strategy_invalid")
                if str(candidate_evidence.get("table_reconstruction_status") or "") not in {
                    "candidate",
                    "accepted",
                    "partial",
                }:
                    failures.add("pdf_vlm_product_routing_candidate_state_invalid")
                candidate = {
                    "strategy": strategy,
                    "rows": rows or 0,
                    "columns": columns or 0,
                    "cells": cells or 0,
                    "populated_cells": sum(
                        1
                        for item in cell_inventory
                        if isinstance(item, dict)
                        and isinstance(item.get("word_refs"), list)
                        and bool(item["word_refs"])
                    ),
                }

        evidence_material = {
            "page": {
                "width": width,
                "height": height,
                "projection_status": str(page.get("layout_projection_status") or ""),
            },
            "page_words": [
                {
                    "text": item["text"],
                    "bbox": item["bbox"],
                    "order": item["order"],
                }
                for item in normalized_words
            ],
            "candidate": (
                {
                    **candidate,
                    "bbox": candidate_bbox,
                    "words": [
                        {
                            "text": item["text"],
                            "bbox": item["bbox"],
                            "order": item["order"],
                        }
                        for item in candidate_words
                    ],
                }
                if candidate is not None
                else None
            ),
            "failure_reason_codes": sorted(failures),
        }
        return {
            "page_width": width or 0.0,
            "page_height": height or 0.0,
            "page_words": normalized_words,
            "candidate": candidate,
            "candidate_words": candidate_words,
            "candidate_bbox": candidate_bbox,
            "failure_reason_codes": sorted(failures),
            "evidence_checksum": sha256_json(evidence_material),
        }

    def _observations(self, evidence: dict[str, Any]) -> dict[str, Any]:
        candidate = evidence["candidate"]
        candidate_words = evidence["candidate_words"]
        page_text = _normalized_text(evidence["page_words"])
        numeric_words = [
            item for item in candidate_words if _NUMBER_TOKEN.search(item["text"])
        ]
        axis_numeric_words = [
            item for item in numeric_words if _is_axis_numeric_word(item["text"])
        ]
        axis_counts = _numeric_axis_counts(
            axis_numeric_words,
            tolerance=self.config.numeric_axis_tolerance_points,
        )
        repeated_axes = [
            item
            for item in axis_counts
            if item["words_total"] >= self.config.minimum_repeated_numeric_axis_words
            and item["rows_total"] >= self.config.minimum_repeated_numeric_axis_rows
        ]
        maximum_axis_words = max(
            (int(item["words_total"]) for item in repeated_axes), default=0
        )
        schedule_codes = sorted(
            code for phrase, code in _SCHEDULE_INTRODUCERS if phrase in page_text
        )
        term_codes = sorted(
            code for phrase, code in _FINANCIAL_SCHEDULE_TERMS if phrase in page_text
        )
        page_numeric_words = sum(
            1 for item in evidence["page_words"] if _NUMBER_TOKEN.search(item["text"])
        )
        schedule_signal = bool(
            schedule_codes
            and term_codes
            and page_numeric_words >= self.config.minimum_schedule_numeric_words
        )
        area_ratio: float | None = None
        if evidence["candidate_bbox"] is not None:
            x0, top, x1, bottom = evidence["candidate_bbox"]
            area_ratio = round(
                ((x1 - x0) * (bottom - top))
                / (evidence["page_width"] * evidence["page_height"]),
                6,
            )
        broad = bool(
            candidate is not None
            and candidate["strategy"] == "aligned_text_v0"
            and area_ratio is not None
            and area_ratio >= self.config.broad_candidate_area_ratio
        )
        return {
            "page_words_total": len(evidence["page_words"]),
            "candidate_present": candidate is not None,
            "candidate_strategy": candidate["strategy"] if candidate else None,
            "candidate_rows_total": candidate["rows"] if candidate else 0,
            "candidate_columns_total": candidate["columns"] if candidate else 0,
            "candidate_cells_total": candidate["cells"] if candidate else 0,
            "candidate_populated_cells_total": (
                candidate["populated_cells"] if candidate else 0
            ),
            "candidate_words_total": len(candidate_words),
            "candidate_area_ratio": area_ratio,
            "broad_aligned_region": broad,
            "ruled_candidate": bool(
                candidate is not None
                and candidate["strategy"] == "ruled_lines_v0"
            ),
            "numeric_candidate_words_total": len(numeric_words),
            "axis_numeric_candidate_words_total": len(axis_numeric_words),
            "repeated_numeric_axes_total": len(repeated_axes),
            "maximum_repeated_numeric_axis_words": maximum_axis_words,
            "repeated_numeric_axis_present": bool(repeated_axes),
            "schedule_introducer_codes": schedule_codes,
            "financial_schedule_term_codes": term_codes,
            "financial_schedule_signal_present": schedule_signal,
            "table_of_contents_marker_present": "table of contents" in page_text,
            "upstream_failure_reasons_total": 0,
        }

    def _result(
        self,
        *,
        route: str,
        detection: str,
        reason_codes: Iterable[str],
        observations: dict[str, Any],
        evidence_checksum: str,
    ) -> dict[str, Any]:
        result = {
            "schema_version": PDF_VLM_PRODUCT_ROUTE_SCHEMA,
            "policy_version": self.config.policy_version,
            "route": route,
            "detection": detection,
            "provider_call_allowed": route in {"candidate_crop", "page_level"},
            "reason_codes": _reason_codes(reason_codes),
            "observations": observations,
            "evidence_checksum": evidence_checksum,
        }
        result["routing_checksum"] = sha256_json(result)
        self.validate_result(result)
        return result


def _numeric_axis_counts(
    words: list[dict[str, Any]], *, tolerance: float
) -> list[dict[str, int | float]]:
    clusters: list[dict[str, Any]] = []
    for word in sorted(words, key=lambda item: float(item["bbox"][2])):
        right = float(word["bbox"][2])
        row = round((float(word["bbox"][1]) + float(word["bbox"][3])) / 2.0, 1)
        cluster = next(
            (
                item
                for item in clusters
                if abs(float(item["right_edge"]) - right) <= tolerance
            ),
            None,
        )
        if cluster is None:
            clusters.append(
                {"right_edge": right, "words_total": 1, "rows": {row}}
            )
        else:
            total = int(cluster["words_total"])
            cluster["right_edge"] = (
                (float(cluster["right_edge"]) * total) + right
            ) / (total + 1)
            cluster["words_total"] = total + 1
            cluster["rows"].add(row)
    return [
        {
            "right_edge": round(float(item["right_edge"]), 3),
            "words_total": int(item["words_total"]),
            "rows_total": len(item["rows"]),
        }
        for item in clusters
    ]


def _is_axis_numeric_word(value: str) -> bool:
    compact = _WHITESPACE.sub("", value).strip()
    if not compact or any(character.isalpha() for character in compact):
        return False
    digits = "".join(character for character in compact if character.isdigit())
    if not digits:
        return False
    if len(digits) == 4 and 1900 <= int(digits) <= 2100:
        return False
    return True


def _normalized_text(words: list[dict[str, Any]]) -> str:
    joined = " ".join(str(item["text"]) for item in words)
    return _WHITESPACE.sub(" ", _NON_WORD.sub(" ", joined.casefold())).strip()


def _empty_observations(*, upstream_failure_reasons_total: int) -> dict[str, Any]:
    return {
        "page_words_total": 0,
        "candidate_present": False,
        "candidate_strategy": None,
        "candidate_rows_total": 0,
        "candidate_columns_total": 0,
        "candidate_cells_total": 0,
        "candidate_populated_cells_total": 0,
        "candidate_words_total": 0,
        "candidate_area_ratio": None,
        "broad_aligned_region": False,
        "ruled_candidate": False,
        "numeric_candidate_words_total": 0,
        "axis_numeric_candidate_words_total": 0,
        "repeated_numeric_axes_total": 0,
        "maximum_repeated_numeric_axis_words": 0,
        "repeated_numeric_axis_present": False,
        "schedule_introducer_codes": [],
        "financial_schedule_term_codes": [],
        "financial_schedule_signal_present": False,
        "table_of_contents_marker_present": False,
        "upstream_failure_reasons_total": upstream_failure_reasons_total,
    }


def _reason_codes(values: Iterable[str]) -> list[str]:
    if isinstance(values, (str, bytes)):
        values = [str(values)]
    normalized = sorted(set(str(item or "") for item in values))
    if any(not _REASON_CODE.fullmatch(item) for item in normalized):
        raise PdfVlmProductRouterError(
            "pdf_vlm_product_router_reason_code_invalid"
        )
    return normalized


def _bbox(value: Any) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    parsed = [_finite_number(item) for item in value]
    if any(item is None for item in parsed):
        return None
    x0, top, x1, bottom = [float(item) for item in parsed]
    if x1 <= x0 or bottom <= top:
        return None
    return [x0, top, x1, bottom]


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    parsed = float(value)
    return parsed if math.isfinite(parsed) else None


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _positive_int_value(value: Any) -> int | None:
    return int(value) if _positive_int(value) else None


def _positive_number(value: Any) -> bool:
    parsed = _finite_number(value)
    return parsed is not None and parsed > 0.0


def _positive_ratio(value: Any) -> bool:
    parsed = _finite_number(value)
    return parsed is not None and 0.0 < parsed <= 1.0
