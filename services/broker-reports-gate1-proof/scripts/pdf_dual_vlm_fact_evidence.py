from __future__ import annotations

import copy
import hashlib
import itertools
import json
import math
from dataclasses import asdict, dataclass
from typing import Any, Iterable


EVIDENCE_RESULT_SCHEMA_VERSION = "broker_reports_pdf_dual_vlm_fact_evidence_v1"
SOURCE_MAP_SCHEMA_VERSION = "broker_reports_pdf_dual_vlm_fact_source_map_v1"
EVIDENCE_POLICY_VERSION = "pdf_dual_vlm_fact_evidence_policy_v1"

FACTORY_REQUIRED = (
    "PdfDualVlmFactEvidenceFactory.create is the only dual-VLM fact evidence "
    "verification entrypoint"
)
FORBIDDEN = (
    "Callers must not use a VLM answer as source evidence, normalize financial "
    "values, construct a parser table, add OCR dependencies, or auto-accept "
    "vision-only facts"
)

EVIDENCE_MEDIA = frozenset({"text_layer", "raster", "mixed"})
PARSER_VERIFIED = "parser_source_verified"
NOT_FOUND = "not_found"
AMBIGUOUS = "ambiguous"
OCR_UNAVAILABLE = "independent_ocr_unavailable"
VISION_ONLY = "models_agree_vision_only"
UNVERIFIED = "unverified"
_QUALIFIER_KINDS = ("period", "currency", "unit", "scale", "entity")
_QUALIFIER_SCOPES = frozenset({"value", "row_label", "header", "table"})
_AGREED_CONSENSUS_STATUSES = frozenset(
    {
        "models_exactly_agree",
        "models_semantically_agree_physical_layout_differs",
    }
)
_OPTIONAL_ATOM_REF_KEYS = (
    "word_ref",
    "bbox_ref",
    "source_value_ref",
    "text_checksum_ref",
)


class PdfDualVlmFactEvidenceError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PdfDualVlmFactEvidenceConfig:
    policy_version: str = EVIDENCE_POLICY_VERSION
    maximum_words_per_page: int = 10_000
    maximum_matches_per_component: int = 64
    maximum_relation_candidates: int = 4_096
    row_y_tolerance_points: float = 2.0
    header_y_tolerance_points: float = 2.0


class PdfDualVlmFactEvidenceFactory:
    def __init__(self, config: PdfDualVlmFactEvidenceConfig | None = None) -> None:
        self.config = config or PdfDualVlmFactEvidenceConfig()

    def create(self) -> "PdfDualVlmFactEvidenceVerifier":
        if self.config.policy_version != EVIDENCE_POLICY_VERSION:
            raise PdfDualVlmFactEvidenceError("fact_evidence_policy_invalid")
        if (
            self.config.maximum_words_per_page < 1
            or self.config.maximum_matches_per_component < 1
            or self.config.maximum_relation_candidates < 1
            or self.config.row_y_tolerance_points < 0
            or self.config.header_y_tolerance_points < 0
        ):
            raise PdfDualVlmFactEvidenceError("fact_evidence_config_invalid")
        return PdfDualVlmFactEvidenceVerifier(self.config)


class PdfDualVlmFactEvidenceVerifier:
    def __init__(self, config: PdfDualVlmFactEvidenceConfig) -> None:
        self.config = config

    def verify(
        self,
        *,
        consensus_facts: list[dict[str, Any]],
        word_inventory: list[dict[str, Any]],
        crop_contract: dict[str, Any],
        page_width: float,
        page_height: float,
        medium: str,
    ) -> dict[str, Any]:
        if not isinstance(consensus_facts, list) or any(
            not isinstance(item, dict) for item in consensus_facts
        ):
            raise PdfDualVlmFactEvidenceError("fact_evidence_facts_invalid")
        if not isinstance(word_inventory, list):
            raise PdfDualVlmFactEvidenceError("fact_evidence_word_inventory_invalid")
        if medium not in EVIDENCE_MEDIA:
            raise PdfDualVlmFactEvidenceError("fact_evidence_medium_invalid")

        crop = _validated_crop_contract(
            crop_contract,
            page_width=page_width,
            page_height=page_height,
        )
        fact_bytes_before = [canonical_json_bytes(item) for item in consensus_facts]
        words = _usable_words(word_inventory)
        if len(words) > self.config.maximum_words_per_page:
            raise PdfDualVlmFactEvidenceError("fact_evidence_page_word_budget_exceeded")
        table_words = [
            word for word in words if _center_inside(word["bbox"], crop["table_bbox"])
        ]
        table_words.sort(key=_word_order_key)

        source_maps = [
            self._verify_fact(
                fact=fact,
                table_words=table_words,
                crop=crop,
                medium=medium,
            )
            for fact in consensus_facts
        ]
        fact_bytes_after = [canonical_json_bytes(item) for item in consensus_facts]
        if fact_bytes_after != fact_bytes_before:
            raise RuntimeError("fact_evidence_input_fact_mutated")

        counts = {
            status: sum(item["evidence_status"] == status for item in source_maps)
            for status in (PARSER_VERIFIED, NOT_FOUND, AMBIGUOUS, OCR_UNAVAILABLE)
        }
        result: dict[str, Any] = {
            "schema_version": EVIDENCE_RESULT_SCHEMA_VERSION,
            "policy_version": self.config.policy_version,
            "policy_configuration_hash": sha256_json(asdict(self.config)),
            "medium": medium,
            "crop_identity": copy.deepcopy(crop),
            "parser_words_total": len(words),
            "table_scoped_words_total": len(table_words),
            "source_maps": source_maps,
            "summary": {
                "facts_total": len(source_maps),
                "status_counts": counts,
                "parser_source_verified": counts[PARSER_VERIFIED],
                "human_review_required": counts[AMBIGUOUS] + counts[OCR_UNAVAILABLE],
                "rejected_or_unverified": counts[NOT_FOUND],
                "vision_only_facts": sum(
                    item["strongest_consensus_evidence_status"] == VISION_ONLY
                    for item in source_maps
                ),
                "automatic_acceptance_eligible": sum(
                    item["automatic_acceptance_eligible"] for item in source_maps
                ),
                "false_accepted_facts": None,
                "reference_scoring_performed": False,
            },
            "parser_role": "fact_evidence_and_coordinate_layer_only",
            "table_construction_performed": False,
            "value_normalization_performed": False,
            "ocr_performed": False,
            "human_reference_used": False,
            "input_facts_unchanged": True,
        }
        result["evidence_result_checksum"] = sha256_json(result)
        return result

    def _verify_fact(
        self,
        *,
        fact: dict[str, Any],
        table_words: list[dict[str, Any]],
        crop: dict[str, Any],
        medium: str,
    ) -> dict[str, Any]:
        fact_before = canonical_json_bytes(fact)
        components = _fact_components(fact)
        fact_id = components["fact_id"]
        consensus_status = components["consensus_status"]

        if medium == "raster" or not table_words:
            strongest_status = (
                VISION_ONLY
                if consensus_status in _AGREED_CONSENSUS_STATUSES
                else UNVERIFIED
            )
            source_map = self._source_map(
                fact=fact,
                fact_id=fact_id,
                consensus_status=consensus_status,
                medium=medium,
                evidence_status=OCR_UNAVAILABLE,
                strongest_status=strongest_status,
                automatic_acceptance_eligible=False,
                component_matches=_empty_component_matches(components),
                relation_candidates=[],
                reason_codes=[
                    "independent_ocr_evidence_unavailable",
                    "parser_table_words_unavailable",
                ]
                if not table_words
                else ["independent_ocr_evidence_unavailable"],
                crop=crop,
                components=components,
            )
            if canonical_json_bytes(fact) != fact_before:
                raise RuntimeError("fact_evidence_input_fact_mutated")
            return source_map

        component_matches, missing_reasons = self._component_matches(
            components=components,
            table_words=table_words,
            crop=crop,
        )
        relation_candidates = self._relation_candidates(component_matches)
        if len(relation_candidates) == 1:
            evidence_status = PARSER_VERIFIED
            strongest_status = PARSER_VERIFIED
            reason_codes: list[str] = []
        elif len(relation_candidates) > 1:
            evidence_status = AMBIGUOUS
            strongest_status = UNVERIFIED
            reason_codes = ["multiple_complete_relation_tuples"]
        else:
            evidence_status = NOT_FOUND
            strongest_status = UNVERIFIED
            reason_codes = missing_reasons or ["complete_relation_tuple_not_found"]

        eligible = (
            evidence_status == PARSER_VERIFIED
            and consensus_status in _AGREED_CONSENSUS_STATUSES
        )
        source_map = self._source_map(
            fact=fact,
            fact_id=fact_id,
            consensus_status=consensus_status,
            medium=medium,
            evidence_status=evidence_status,
            strongest_status=strongest_status,
            automatic_acceptance_eligible=eligible,
            component_matches=component_matches,
            relation_candidates=relation_candidates,
            reason_codes=reason_codes,
            crop=crop,
            components=components,
        )
        if canonical_json_bytes(fact) != fact_before:
            raise RuntimeError("fact_evidence_input_fact_mutated")
        return source_map

    def _component_matches(
        self,
        *,
        components: dict[str, Any],
        table_words: list[dict[str, Any]],
        crop: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str]]:
        reasons: list[str] = []
        row_matches = self._matches_in_region(
            words=table_words,
            target=components["row_label"]["text"],
            crop_region=components["row_label"]["source_region"],
            crop=crop,
            allow_single_atom_substring=False,
        )
        value_matches = self._matches_in_region(
            words=table_words,
            target=components["value"]["text"],
            crop_region=components["value"]["source_region"],
            crop=crop,
            allow_single_atom_substring=False,
        )
        if not row_matches:
            reasons.append("row_label_evidence_not_found")
        if not value_matches:
            reasons.append("exact_visible_value_evidence_not_found")

        header_matches: list[list[dict[str, Any]]] = []
        for index, header in enumerate(components["headers"], start=1):
            matches = self._matches_in_region(
                words=table_words,
                target=header["text"],
                crop_region=header["source_region"],
                crop=crop,
                allow_single_atom_substring=False,
            )
            header_matches.append(matches)
            if not matches:
                reasons.append(f"header_{index}_evidence_not_found")

        qualifier_matches: dict[str, list[dict[str, Any]]] = {}
        for kind, qualifier in components["qualifiers"].items():
            matches = self._matches_in_region(
                words=table_words,
                target=qualifier["text"],
                crop_region=qualifier["source_region"],
                crop=crop,
                allow_single_atom_substring=True,
            )
            qualifier_matches[kind] = matches
            if not matches:
                reasons.append(f"{kind}_evidence_not_found")

        return (
            {
                "row_label": row_matches,
                "value": value_matches,
                "headers": header_matches,
                "qualifiers": qualifier_matches,
                "qualifier_scopes": {
                    kind: value["scope"]
                    for kind, value in components["qualifiers"].items()
                },
            },
            reasons,
        )

    def _matches_in_region(
        self,
        *,
        words: list[dict[str, Any]],
        target: str,
        crop_region: list[float],
        crop: dict[str, Any],
        allow_single_atom_substring: bool,
    ) -> list[dict[str, Any]]:
        region = _project_crop_bbox(crop_region, crop["rendered_bbox"])
        scoped = [word for word in words if _center_inside(word["bbox"], region)]
        scoped.sort(key=_word_order_key)
        matches = _exact_matches(
            scoped,
            target,
            allow_single_atom_substring=allow_single_atom_substring,
        )
        if len(matches) > self.config.maximum_matches_per_component:
            raise PdfDualVlmFactEvidenceError(
                "fact_evidence_component_match_budget_exceeded"
            )
        return matches

    def _relation_candidates(
        self, component_matches: dict[str, Any]
    ) -> list[dict[str, Any]]:
        rows = component_matches["row_label"]
        values = component_matches["value"]
        headers = component_matches["headers"]
        qualifiers = component_matches["qualifiers"]
        if not rows or not values or any(not group for group in headers):
            return []
        if any(not qualifiers[kind] for kind in qualifiers):
            return []

        header_products: Iterable[tuple[dict[str, Any], ...]] = (
            itertools.product(*headers) if headers else [tuple()]
        )
        qualifier_kinds = sorted(qualifiers)
        qualifier_products: Iterable[tuple[dict[str, Any], ...]] = (
            itertools.product(*(qualifiers[kind] for kind in qualifier_kinds))
            if qualifier_kinds
            else [tuple()]
        )
        header_combinations = list(header_products)
        qualifier_combinations = list(qualifier_products)
        candidates: list[dict[str, Any]] = []
        for row, value, header_values, qualifier_values in itertools.product(
            rows,
            values,
            header_combinations,
            qualifier_combinations,
        ):
            if not _same_row(
                row["source_bbox"],
                value["source_bbox"],
                tolerance=self.config.row_y_tolerance_points,
            ):
                continue
            if not _headers_compatible(
                header_values,
                value,
                tolerance=self.config.header_y_tolerance_points,
            ):
                continue
            selected_qualifiers = dict(zip(qualifier_kinds, qualifier_values))
            if not _qualifiers_compatible(
                selected_qualifiers,
                component_matches["qualifier_scopes"],
                row=row,
                value=value,
                row_tolerance=self.config.row_y_tolerance_points,
                header_tolerance=self.config.header_y_tolerance_points,
            ):
                continue
            candidates.append(
                {
                    "row_label": copy.deepcopy(row),
                    "value": copy.deepcopy(value),
                    "headers": copy.deepcopy(list(header_values)),
                    "qualifiers": copy.deepcopy(selected_qualifiers),
                    "relation_proof": {
                        "row_value_same_row_compatible": True,
                        "headers_ordered_above_and_column_compatible": True,
                        "qualifier_scopes_compatible": True,
                    },
                }
            )
            if len(candidates) > self.config.maximum_relation_candidates:
                raise PdfDualVlmFactEvidenceError(
                    "fact_evidence_relation_candidate_budget_exceeded"
                )
        return candidates

    def _source_map(
        self,
        *,
        fact: dict[str, Any],
        fact_id: str,
        consensus_status: str,
        medium: str,
        evidence_status: str,
        strongest_status: str,
        automatic_acceptance_eligible: bool,
        component_matches: dict[str, Any],
        relation_candidates: list[dict[str, Any]],
        reason_codes: list[str],
        crop: dict[str, Any],
        components: dict[str, Any],
    ) -> dict[str, Any]:
        value: dict[str, Any] = {
            "schema_version": SOURCE_MAP_SCHEMA_VERSION,
            "policy_version": self.config.policy_version,
            "fact_id": fact_id,
            "input_fact_sha256": sha256_json(fact),
            "consensus_status": consensus_status,
            "medium": medium,
            "evidence_status": evidence_status,
            "strongest_consensus_evidence_status": strongest_status,
            "automatic_acceptance_eligible": automatic_acceptance_eligible,
            "source_identity": copy.deepcopy(crop),
            "evidence_requests": _projected_evidence_requests(components, crop),
            "component_matches": copy.deepcopy(component_matches),
            "relation_candidate_count": len(relation_candidates),
            "relation_candidates": copy.deepcopy(relation_candidates),
            "reason_codes": sorted(set(reason_codes)),
            "parser_role": "fact_evidence_and_coordinate_layer_only",
            "table_construction_performed": False,
            "value_normalization_performed": False,
            "ocr_performed": False,
            "input_fact_unchanged": True,
        }
        value["source_map_checksum"] = sha256_json(value)
        return value


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def validate_source_map(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["fact_source_map_not_object"]
    errors: list[str] = []
    if value.get("schema_version") != SOURCE_MAP_SCHEMA_VERSION:
        errors.append("fact_source_map_schema_invalid")
    status = value.get("evidence_status")
    if status not in {PARSER_VERIFIED, NOT_FOUND, AMBIGUOUS, OCR_UNAVAILABLE}:
        errors.append("fact_source_map_status_invalid")
    if (
        status == OCR_UNAVAILABLE
        and value.get("automatic_acceptance_eligible") is not False
    ):
        errors.append("fact_source_map_vision_only_acceptance_invalid")
    if value.get("value_normalization_performed") is not False:
        errors.append("fact_source_map_value_normalization_invalid")
    if value.get("table_construction_performed") is not False:
        errors.append("fact_source_map_table_construction_invalid")
    stored = value.get("source_map_checksum")
    unsigned = copy.deepcopy(value)
    unsigned.pop("source_map_checksum", None)
    if not _sha256(stored) or stored != sha256_json(unsigned):
        errors.append("fact_source_map_checksum_invalid")
    return errors


def validate_evidence_result(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["fact_evidence_result_not_object"]
    errors: list[str] = []
    if value.get("schema_version") != EVIDENCE_RESULT_SCHEMA_VERSION:
        errors.append("fact_evidence_result_schema_invalid")
    maps = value.get("source_maps")
    if not isinstance(maps, list):
        errors.append("fact_evidence_result_source_maps_invalid")
    else:
        for source_map in maps:
            errors.extend(validate_source_map(source_map))
    stored = value.get("evidence_result_checksum")
    unsigned = copy.deepcopy(value)
    unsigned.pop("evidence_result_checksum", None)
    if not _sha256(stored) or stored != sha256_json(unsigned):
        errors.append("fact_evidence_result_checksum_invalid")
    return errors


def _validated_crop_contract(
    value: Any, *, page_width: float, page_height: float
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PdfDualVlmFactEvidenceError("fact_evidence_crop_contract_invalid")
    width = _positive_number(page_width)
    height = _positive_number(page_height)
    if width is None or height is None:
        raise PdfDualVlmFactEvidenceError("fact_evidence_page_dimensions_invalid")
    pdf_sha256 = value.get("pdf_sha256")
    page_number = value.get("page_number")
    table_bbox = _bbox(
        value.get("table_bbox")
        or value.get("declared_table_bbox")
        or value.get("source_bbox_points")
    )
    rendered_bbox = _bbox(
        value.get("rendered_bbox") or value.get("rendered_bbox_points")
    )
    crop_sha256 = (
        value.get("crop_sha256")
        or value.get("png_sha256")
        or value.get("rendered_image_sha256")
    )
    transform = value.get("source_to_pixel_transform")
    if (
        not _sha256(pdf_sha256)
        or not isinstance(page_number, int)
        or isinstance(page_number, bool)
        or page_number < 1
        or table_bbox is None
        or rendered_bbox is None
        or not _sha256(crop_sha256)
        or not isinstance(transform, dict)
        or not _transform_valid(transform)
        or not _contains([0.0, 0.0, width, height], rendered_bbox)
        or not _contains(rendered_bbox, table_bbox)
    ):
        raise PdfDualVlmFactEvidenceError("fact_evidence_crop_contract_invalid")
    contract_checksum = value.get("contract_checksum")
    if contract_checksum is not None:
        unsigned = copy.deepcopy(value)
        unsigned.pop("contract_checksum", None)
        if not _sha256(contract_checksum) or contract_checksum != sha256_json(unsigned):
            raise PdfDualVlmFactEvidenceError(
                "fact_evidence_crop_contract_checksum_invalid"
            )
    result = {
        "pdf_sha256": str(pdf_sha256),
        "page_number": page_number,
        "table_bbox": table_bbox,
        "rendered_bbox": rendered_bbox,
        "crop_sha256": str(crop_sha256),
        "source_to_pixel_transform": {
            key: float(transform[key])
            for key in (
                "scale_x",
                "scale_y",
                "translate_source_x",
                "translate_source_y",
            )
        },
        "page_dimensions": {"width": width, "height": height},
    }
    for source_key, target_key in (
        ("crop_id", "crop_id"),
        ("contract_checksum", "crop_contract_checksum"),
        ("render_dpi", "render_dpi"),
        ("dimensions", "crop_dimensions"),
    ):
        if source_key in value:
            result[target_key] = copy.deepcopy(value[source_key])
    return result


def _fact_components(fact: dict[str, Any]) -> dict[str, Any]:
    payload = fact.get("canonical_fact")
    payload = payload if isinstance(payload, dict) else fact
    if "fact_checksum" in payload:
        unsigned_payload = copy.deepcopy(payload)
        checksum = unsigned_payload.pop("fact_checksum", None)
        if not _sha256(checksum) or checksum != sha256_json(unsigned_payload):
            raise PdfDualVlmFactEvidenceError(
                "fact_evidence_canonical_fact_checksum_invalid"
            )
    fact_id = fact.get("fact_id") or fact.get("consensus_id") or payload.get("fact_id")
    consensus_status = (
        fact.get("consensus_status")
        or fact.get("status")
        or payload.get("consensus_status")
    )
    if not isinstance(fact_id, str) or not fact_id:
        raise PdfDualVlmFactEvidenceError("fact_evidence_fact_id_invalid")
    if not isinstance(consensus_status, str) or not consensus_status:
        raise PdfDualVlmFactEvidenceError("fact_evidence_consensus_status_invalid")

    if "gemini_source_regions" in payload or "openai_source_regions" in payload:
        observed = payload
        regions = _intersected_consensus_regions(payload)
        row_raw = observed.get("row_label_exact")
        value_raw = observed.get("value_exact")
        raw_headers = observed.get("header_path_exact")
        requested = payload.get("evidence_request")
        requested = requested if isinstance(requested, dict) else {}
        requested_text = requested.get("requested_text")
        requested_text = requested_text if isinstance(requested_text, dict) else {}
        interpreted = payload.get("interpreted")
        interpreted = interpreted if isinstance(interpreted, dict) else {}
        raw_qualifiers = {
            "period": requested_text.get("period_exact"),
            "currency": requested_text.get("currency_exact"),
            "unit": requested_text.get("unit_exact"),
            "scale": requested_text.get("scale_exact"),
            "entity": requested_text.get("entity_exact"),
        }
        material_qualifiers = {
            "period": interpreted.get("period"),
            "currency": interpreted.get("currency_literal")
            or interpreted.get("currency_code"),
            "unit": interpreted.get("unit"),
            "scale": interpreted.get("scale"),
            "entity": interpreted.get("entity"),
        }
        for kind, material in material_qualifiers.items():
            if _material_text(material) and not _material_text(
                raw_qualifiers.get(kind)
            ):
                raise PdfDualVlmFactEvidenceError(
                    f"fact_evidence_{kind}_source_text_missing"
                )
        source_region_policy = "intersection_of_provider_regions"
    else:
        observed = payload.get("observed_content")
        observed = observed if isinstance(observed, dict) else payload
        regions = payload.get("source_regions") or observed.get("source_regions")
        regions = _normalized_region_contract(regions)
        row_raw = observed.get(
            "exact_visible_row_label",
            observed.get("row_label_exact", observed.get("row_label")),
        )
        value_raw = observed.get(
            "exact_visible_value",
            observed.get("value_exact", observed.get("visible_value")),
        )
        raw_headers = observed.get("header_path", observed.get("header_path_exact"))
        raw_qualifiers = observed.get("qualifiers")
        raw_qualifiers = raw_qualifiers if isinstance(raw_qualifiers, dict) else {}
        source_region_policy = "canonical_consensus_region"

    row = _component(
        row_raw,
        fallback_region=regions.get("row_label"),
        error_code="fact_evidence_row_label_invalid",
    )
    value = _component(
        value_raw,
        fallback_region=regions.get("value"),
        error_code="fact_evidence_visible_value_invalid",
    )

    if not isinstance(raw_headers, list):
        raise PdfDualVlmFactEvidenceError("fact_evidence_header_path_invalid")
    region_headers = regions.get("headers")
    region_headers = region_headers if isinstance(region_headers, list) else []
    headers = [
        _component(
            raw,
            fallback_region=(
                region_headers[index] if index < len(region_headers) else None
            ),
            error_code="fact_evidence_header_invalid",
        )
        for index, raw in enumerate(raw_headers)
    ]

    evidence_request = payload.get("evidence_request")
    evidence_request = evidence_request if isinstance(evidence_request, dict) else {}
    qualifier_scopes = (
        fact.get("qualifier_scopes")
        or payload.get("qualifier_scopes")
        or evidence_request.get("qualifier_scopes")
    )
    qualifier_scopes = qualifier_scopes if isinstance(qualifier_scopes, dict) else {}
    region_qualifiers = regions.get("qualifiers")
    region_qualifiers = region_qualifiers if isinstance(region_qualifiers, dict) else {}
    qualifiers: dict[str, dict[str, Any]] = {}
    for kind in _QUALIFIER_KINDS:
        raw = raw_qualifiers.get(kind, observed.get(kind))
        text = _component_text(raw)
        if text is None or text in {"", "unknown"}:
            continue
        raw_scope = raw.get("scope") if isinstance(raw, dict) else None
        scope = raw_scope or qualifier_scopes.get(kind)
        if scope not in _QUALIFIER_SCOPES:
            raise PdfDualVlmFactEvidenceError(f"fact_evidence_{kind}_scope_invalid")
        fallback_region = region_qualifiers.get(kind, regions.get(kind))
        component = _component(
            raw,
            fallback_region=fallback_region,
            error_code=f"fact_evidence_{kind}_invalid",
        )
        component["scope"] = scope
        qualifiers[kind] = component

    return {
        "fact_id": fact_id,
        "consensus_status": consensus_status,
        "row_label": row,
        "value": value,
        "headers": headers,
        "qualifiers": qualifiers,
        "source_region_policy": source_region_policy,
    }


def _intersected_consensus_regions(payload: dict[str, Any]) -> dict[str, Any]:
    gemini = payload.get("gemini_source_regions")
    openai = payload.get("openai_source_regions")
    gemini = gemini if isinstance(gemini, dict) else {}
    openai = openai if isinstance(openai, dict) else {}
    gemini_headers = gemini.get("header_bboxes")
    openai_headers = openai.get("header_bboxes")
    gemini_headers = gemini_headers if isinstance(gemini_headers, list) else []
    openai_headers = openai_headers if isinstance(openai_headers, list) else []
    if len(gemini_headers) != len(openai_headers):
        headers: list[list[float] | None] = []
    else:
        headers = [
            _bbox_intersection(left, right)
            for left, right in zip(gemini_headers, openai_headers)
        ]
    gemini_qualifiers = gemini.get("qualifier_bboxes")
    openai_qualifiers = openai.get("qualifier_bboxes")
    gemini_qualifiers = gemini_qualifiers if isinstance(gemini_qualifiers, dict) else {}
    openai_qualifiers = openai_qualifiers if isinstance(openai_qualifiers, dict) else {}
    return {
        "row_label": _bbox_intersection(
            gemini.get("row_label_bbox"), openai.get("row_label_bbox")
        ),
        "value": _bbox_intersection(gemini.get("value_bbox"), openai.get("value_bbox")),
        "headers": headers,
        "qualifiers": {
            kind: _bbox_intersection(
                gemini_qualifiers.get(kind), openai_qualifiers.get(kind)
            )
            for kind in _QUALIFIER_KINDS
        },
    }


def _normalized_region_contract(value: Any) -> dict[str, Any]:
    value = value if isinstance(value, dict) else {}
    qualifiers = value.get("qualifiers") or value.get("qualifier_bboxes")
    qualifiers = qualifiers if isinstance(qualifiers, dict) else {}
    return {
        "row_label": value.get("row_label") or value.get("row_label_bbox"),
        "value": value.get("value") or value.get("value_bbox"),
        "headers": value.get("headers") or value.get("header_bboxes") or [],
        "qualifiers": qualifiers,
    }


def _bbox_intersection(left: Any, right: Any) -> list[float] | None:
    left_bbox = _normalized_bbox(left)
    right_bbox = _normalized_bbox(right)
    if left_bbox is None or right_bbox is None:
        return None
    intersection = [
        max(left_bbox[0], right_bbox[0]),
        max(left_bbox[1], right_bbox[1]),
        min(left_bbox[2], right_bbox[2]),
        min(left_bbox[3], right_bbox[3]),
    ]
    return _normalized_bbox(intersection)


def _component(value: Any, *, fallback_region: Any, error_code: str) -> dict[str, Any]:
    text = _component_text(value)
    raw_region = (
        value.get("source_region", value.get("bbox"))
        if isinstance(value, dict)
        else None
    )
    region = _normalized_bbox(raw_region if raw_region is not None else fallback_region)
    if not isinstance(text, str) or not text or region is None:
        raise PdfDualVlmFactEvidenceError(error_code)
    return {"text": text, "source_region": region}


def _component_text(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("exact_visible_text", "text", "value"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                return candidate
    return None


def _material_text(value: Any) -> bool:
    return isinstance(value, str) and value not in {"", "unknown"}


def _usable_words(word_inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    seen_ordinals: set[int] = set()
    for raw in word_inventory:
        if not isinstance(raw, dict):
            continue
        ordinal = raw.get("parser_ordinal")
        text = raw.get("text")
        bbox = _bbox(raw.get("bbox"))
        if (
            not isinstance(ordinal, int)
            or isinstance(ordinal, bool)
            or ordinal < 1
            or ordinal in seen_ordinals
            or not isinstance(text, str)
            or not text
            or bbox is None
        ):
            continue
        seen_ordinals.add(ordinal)
        word: dict[str, Any] = {
            "parser_ordinal": ordinal,
            "geometry_reading_order": raw.get("geometry_reading_order"),
            "text": text,
            "bbox": bbox,
        }
        for key in _OPTIONAL_ATOM_REF_KEYS:
            if key in raw:
                word[key] = copy.deepcopy(raw[key])
        words.append(word)
    return words


def _exact_matches(
    words: list[dict[str, Any]],
    target: str,
    *,
    allow_single_atom_substring: bool,
) -> list[dict[str, Any]]:
    target_key = _whitespace_key(target)
    if not target_key:
        return []
    matches: list[dict[str, Any]] = []
    seen: set[tuple[int, ...]] = set()
    for start in range(len(words)):
        for end in range(start + 1, len(words) + 1):
            selected = words[start:end]
            exact_source_text = " ".join(item["text"] for item in selected)
            source_key = _whitespace_key(exact_source_text)
            exact = source_key == target_key
            substring = (
                allow_single_atom_substring
                and len(selected) == 1
                and target_key in source_key
            )
            if exact or substring:
                ordinals = tuple(item["parser_ordinal"] for item in selected)
                if ordinals not in seen:
                    seen.add(ordinals)
                    atoms = [copy.deepcopy(item) for item in selected]
                    matches.append(
                        {
                            "parser_ordinals": list(ordinals),
                            "exact_source_text": exact_source_text,
                            "claimed_exact_text": target,
                            "match_mode": (
                                "whitespace_only_token_join"
                                if exact
                                else "exact_substring_in_single_atom"
                            ),
                            "source_bbox": _bbox_union(
                                [item["bbox"] for item in selected]
                            ),
                            "atoms": atoms,
                            "word_refs": _present_refs(atoms, "word_ref"),
                            "bbox_refs": _present_refs(atoms, "bbox_ref"),
                            "source_value_refs": _present_refs(
                                atoms, "source_value_ref"
                            ),
                            "text_checksum_refs": _present_refs(
                                atoms, "text_checksum_ref"
                            ),
                        }
                    )
            if len(source_key) > len(target_key) and not (
                allow_single_atom_substring and len(selected) == 1
            ):
                break
    return matches


def _present_refs(atoms: list[dict[str, Any]], key: str) -> list[Any]:
    return [copy.deepcopy(atom[key]) for atom in atoms if key in atom]


def _empty_component_matches(components: dict[str, Any]) -> dict[str, Any]:
    return {
        "row_label": [],
        "value": [],
        "headers": [[] for _ in components["headers"]],
        "qualifiers": {kind: [] for kind in components["qualifiers"]},
        "qualifier_scopes": {
            kind: value["scope"] for kind, value in components["qualifiers"].items()
        },
    }


def _projected_evidence_requests(
    components: dict[str, Any], crop: dict[str, Any]
) -> dict[str, Any]:
    def projected(component: dict[str, Any]) -> dict[str, Any]:
        return {
            "exact_visible_text": component["text"],
            "crop_normalized_bbox": copy.deepcopy(component["source_region"]),
            "page_bbox": _project_crop_bbox(
                component["source_region"], crop["rendered_bbox"]
            ),
        }

    return {
        "source_region_policy": components["source_region_policy"],
        "row_label": projected(components["row_label"]),
        "value": projected(components["value"]),
        "headers": [projected(header) for header in components["headers"]],
        "qualifiers": {
            kind: {**projected(qualifier), "scope": qualifier["scope"]}
            for kind, qualifier in components["qualifiers"].items()
        },
    }


def _same_row(left: list[float], right: list[float], *, tolerance: float) -> bool:
    return not (left[3] + tolerance < right[1] or right[3] + tolerance < left[1])


def _headers_compatible(
    headers: tuple[dict[str, Any], ...],
    value: dict[str, Any],
    *,
    tolerance: float,
) -> bool:
    value_bbox = value["source_bbox"]
    previous_y = -math.inf
    for header in headers:
        bbox = header["source_bbox"]
        if bbox[1] < previous_y or bbox[3] > value_bbox[1] + tolerance:
            return False
        if not _horizontal_compatible(bbox, value_bbox):
            return False
        previous_y = bbox[1]
    return True


def _qualifiers_compatible(
    qualifiers: dict[str, dict[str, Any]],
    scopes: dict[str, str],
    *,
    row: dict[str, Any],
    value: dict[str, Any],
    row_tolerance: float,
    header_tolerance: float,
) -> bool:
    for kind, match in qualifiers.items():
        bbox = match["source_bbox"]
        scope = scopes[kind]
        if scope == "value" and not _overlaps(bbox, value["source_bbox"]):
            return False
        if scope == "row_label" and not _same_row(
            bbox, row["source_bbox"], tolerance=row_tolerance
        ):
            return False
        if scope == "header":
            if bbox[3] > value["source_bbox"][1] + header_tolerance:
                return False
            if not _horizontal_compatible(bbox, value["source_bbox"]):
                return False
    return True


def _horizontal_compatible(left: list[float], right: list[float]) -> bool:
    return min(left[2], right[2]) > max(left[0], right[0])


def _overlaps(left: list[float], right: list[float]) -> bool:
    return not (
        left[2] < right[0]
        or right[2] < left[0]
        or left[3] < right[1]
        or right[3] < left[1]
    )


def _project_crop_bbox(
    normalized_bbox: list[float], rendered_bbox: list[float]
) -> list[float]:
    x0, y0, x1, y1 = normalized_bbox
    rx0, ry0, rx1, ry1 = rendered_bbox
    width = rx1 - rx0
    height = ry1 - ry0
    return [
        round(rx0 + x0 * width, 9),
        round(ry0 + y0 * height, 9),
        round(rx0 + x1 * width, 9),
        round(ry0 + y1 * height, 9),
    ]


def _word_order_key(value: dict[str, Any]) -> tuple[Any, ...]:
    order = value.get("geometry_reading_order")
    bbox = value["bbox"]
    return (
        0
        if isinstance(order, int) and not isinstance(order, bool) and order > 0
        else 1,
        order
        if isinstance(order, int) and not isinstance(order, bool) and order > 0
        else round(bbox[1], 6),
        round(bbox[0], 6),
        value["parser_ordinal"],
    )


def _whitespace_key(value: str) -> str:
    return "".join(value.split())


def _normalized_bbox(value: Any) -> list[float] | None:
    bbox = _bbox(value)
    if bbox is None or any(item < 0 or item > 1 for item in bbox):
        return None
    return bbox


def _bbox(value: Any) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    if any(
        not isinstance(item, (int, float))
        or isinstance(item, bool)
        or not math.isfinite(float(item))
        for item in value
    ):
        return None
    bbox = [float(item) for item in value]
    if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
        return None
    return bbox


def _bbox_union(values: list[list[float]]) -> list[float]:
    return [
        min(value[0] for value in values),
        min(value[1] for value in values),
        max(value[2] for value in values),
        max(value[3] for value in values),
    ]


def _center_inside(value: list[float], scope: list[float]) -> bool:
    x = (value[0] + value[2]) / 2.0
    y = (value[1] + value[3]) / 2.0
    return scope[0] <= x <= scope[2] and scope[1] <= y <= scope[3]


def _contains(outer: list[float], inner: list[float]) -> bool:
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and outer[2] >= inner[2]
        and outer[3] >= inner[3]
    )


def _transform_valid(value: dict[str, Any]) -> bool:
    required = {
        "scale_x",
        "scale_y",
        "translate_source_x",
        "translate_source_y",
    }
    if not required <= set(value):
        return False
    numbers = [_finite_number(value[key]) for key in required]
    return all(number is not None for number in numbers) and (
        float(value["scale_x"]) > 0 and float(value["scale_y"]) > 0
    )


def _positive_number(value: Any) -> float | None:
    number = _finite_number(value)
    return number if number is not None and number > 0 else None


def _finite_number(value: Any) -> float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
