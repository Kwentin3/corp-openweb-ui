from __future__ import annotations

import copy
import math
import re
from dataclasses import dataclass, replace
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from .contracts import sha256_json, stable_digest
from .pdf_table_locator import (
    PDF_TABLE_LOCATOR_COORDINATE_CONTRACT,
    PdfTableLocatorError,
    PdfTableLocatorProjectionFactory,
)
from .pdf_text_layer import (
    PDF_TEXT_LAYER_PROJECTION_SCHEMA_VERSION,
    validate_pdf_text_layer_payload,
)


SOURCE_BOUND_TABLE_SCOPE_PROPOSAL_SCHEMA = (
    "broker_reports_source_bound_table_scope_proposal_v1"
)
SOURCE_BOUND_TABLE_SCOPE_PROJECTION_SCHEMA = (
    "broker_reports_source_bound_table_scope_projection_v1"
)
SOURCE_BOUND_TABLE_SCOPE_POLICY_VERSION = (
    "source_bound_table_scope_policy_v1_proposed_inactive"
)
SOURCE_BOUND_UNRESOLVED_VISUAL_SCHEMA = (
    "broker_reports_source_bound_unresolved_visual_projection_v1"
)
SOURCE_BOUND_UNRESOLVED_VISUAL_POLICY_VERSION = (
    "source_bound_unresolved_visual_policy_v1_char_centers_inactive"
)
FACTORY_REQUIRED = (
    "SourceBoundTableScopeFactory.create is the only inactive boundary from "
    "geometry-only table observations to FullSource-owned word refs"
)
FORBIDDEN = (
    "inactive only: no model-authored text, table identity, continuation, "
    "financial meaning, Canonical mutation, fact publication, or product import"
)


class SourceBoundTableScopeError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class SourceBoundTableScopeReceipt:
    scope_ref: str
    source_checksum_sha256: str
    page_ref: str
    page_number: int
    raster_manifest_hash: str
    proposal_sha256: str
    binding_status: str
    body_status: str
    locator_candidate_ref: str | None
    locator_bbox_ref: str | None
    locator_bbox_pdf_points: tuple[float, float, float, float] | None
    title_status: str
    title_word_refs: tuple[str, ...]
    header_status: str
    header_word_ref_groups: tuple[tuple[str, ...], ...]
    body_anchor_word_refs: tuple[str, ...]
    body_word_refs: tuple[str, ...]
    scope_word_refs: tuple[str, ...]
    issue_codes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "scope_ref": self.scope_ref,
            "source_checksum_sha256": self.source_checksum_sha256,
            "page_ref": self.page_ref,
            "page_number": self.page_number,
            "raster_manifest_hash": self.raster_manifest_hash,
            "proposal_sha256": self.proposal_sha256,
            "binding_status": self.binding_status,
            "body_status": self.body_status,
            "locator_candidate_ref": self.locator_candidate_ref,
            "locator_bbox_ref": self.locator_bbox_ref,
            "locator_bbox_pdf_points": (
                list(self.locator_bbox_pdf_points)
                if self.locator_bbox_pdf_points is not None
                else None
            ),
            "title_status": self.title_status,
            "title_word_refs": list(self.title_word_refs),
            "header_status": self.header_status,
            "header_word_ref_groups": [
                list(group) for group in self.header_word_ref_groups
            ],
            "body_anchor_word_refs": list(self.body_anchor_word_refs),
            "body_word_refs": list(self.body_word_refs),
            "scope_word_refs": list(self.scope_word_refs),
            "issue_codes": list(self.issue_codes),
        }


@dataclass(frozen=True)
class SourceBoundTableScopeProjection:
    schema_version: str
    policy_version: str
    source_checksum_sha256: str
    page_ref: str
    page_number: int
    raster_manifest_hash: str
    proposal_sha256: str
    scopes: tuple[SourceBoundTableScopeReceipt, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "source_binding": {
                "source_sha256": self.source_checksum_sha256,
                "page_ref": self.page_ref,
                "page_number": self.page_number,
                "raster_manifest_hash": self.raster_manifest_hash,
            },
            "proposal_sha256": self.proposal_sha256,
            "scopes": [scope.as_dict() for scope in self.scopes],
            "model_literals_used_as_source_values": False,
            "table_identity_assigned": False,
            "continuation_decided": False,
            "downstream_authority": False,
            "product_reachability": False,
        }


def proposal_schema() -> dict[str, Any]:
    box = {
        "type": "array",
        "minItems": 4,
        "maxItems": 4,
        "items": {"type": "integer", "minimum": 0, "maximum": 1000},
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "tables"],
        "properties": {
            "schema_version": {
                "type": "string",
                "enum": [SOURCE_BOUND_TABLE_SCOPE_PROPOSAL_SCHEMA],
            },
            "tables": {
                "type": "array",
                "maxItems": 64,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "title_status",
                        "title_boxes_2d",
                        "header_status",
                        "header_boxes_2d",
                        "body_status",
                        "body_anchor_boxes_2d",
                    ],
                    "properties": {
                        "title_status": {
                            "type": "string",
                            "enum": ["PRESENT", "ABSENT"],
                        },
                        "title_boxes_2d": {
                            "type": "array",
                            "maxItems": 4,
                            "items": copy.deepcopy(box),
                        },
                        "header_status": {
                            "type": "string",
                            "enum": ["PRESENT", "ABSENT"],
                        },
                        "header_boxes_2d": {
                            "type": "array",
                            "maxItems": 8,
                            "items": copy.deepcopy(box),
                        },
                        "body_status": {
                            "type": "string",
                            "enum": [
                                "HAS_DATA",
                                "EMPTY_TEMPLATE",
                                "EXPLAINER",
                                "UNCERTAIN",
                            ],
                        },
                        "body_anchor_boxes_2d": {
                            "type": "array",
                            "maxItems": 8,
                            "items": copy.deepcopy(box),
                        },
                    },
                },
            },
        },
    }


class SourceBoundTableScopeFactory:
    def create(self) -> "SourceBoundTableScopeBinder":
        return SourceBoundTableScopeBinder()


class SourceBoundTableScopeBinder:
    """Bind reviewed geometry to existing FullSource words and candidates."""

    def bind(
        self,
        *,
        proposal: Any,
        full_source_payload: Mapping[str, Any],
        source_checksum_sha256: str,
        page_ref: str,
        page_number: int,
        raster_manifest: Mapping[str, Any],
    ) -> SourceBoundTableScopeProjection:
        value = _validated_proposal(proposal)
        proposal_sha256 = sha256_json(value)
        source_checksum = _sha256(source_checksum_sha256, "source_checksum")
        payload = _validated_full_source_payload(
            full_source_payload,
            source_checksum_sha256=source_checksum,
        )
        raster_hash = _sha256(
            raster_manifest.get("manifest_hash")
            if isinstance(raster_manifest, Mapping)
            else None,
            "raster_manifest_hash",
        )
        if not isinstance(page_ref, str) or not page_ref:
            raise SourceBoundTableScopeError("source_bound_table_scope_page_invalid")
        if not isinstance(page_number, int) or isinstance(page_number, bool):
            raise SourceBoundTableScopeError("source_bound_table_scope_page_invalid")
        if (
            not isinstance(raster_manifest, Mapping)
            or raster_manifest.get("pdf_sha256") != source_checksum
            or raster_manifest.get("document_ref") != payload.get("document_ref")
            or raster_manifest.get("page_ref") != page_ref
            or raster_manifest.get("page_number") != page_number
        ):
            raise SourceBoundTableScopeError(
                "source_bound_table_scope_source_binding_mismatch"
            )
        page, words, candidates = _projection_page(
            payload["pdf_text_layer_projection"],
            page_ref=page_ref,
            page_number=page_number,
        )
        projected_groups = _project_box_groups(
            value["tables"],
            raster_manifest=raster_manifest,
            page=page,
        )
        used_role_refs: set[str] = set()
        used_scope_refs: set[str] = set()
        scopes: list[SourceBoundTableScopeReceipt] = []
        for raw, projected in zip(value["tables"], projected_groups, strict=True):
            title_groups = _bind_box_groups(projected["title"], words)
            header_groups = _bind_box_groups(projected["header"], words)
            body_anchor_groups = _bind_box_groups(
                projected["body_anchor"], words
            )
            _presence(raw["title_status"], title_groups, "title")
            _presence(raw["header_status"], header_groups, "header")
            _body_presence(raw["body_status"], body_anchor_groups)

            title_refs = _flatten_unique(title_groups)
            header_refs = _flatten_unique(header_groups)
            body_anchor_refs = _flatten_unique(body_anchor_groups)
            role_refs = {*title_refs, *header_refs, *body_anchor_refs}
            if len(role_refs) != len(title_refs) + len(header_refs) + len(
                body_anchor_refs
            ):
                raise SourceBoundTableScopeError(
                    "source_bound_table_scope_cross_role_overlap"
                )
            if role_refs.intersection(used_role_refs):
                raise SourceBoundTableScopeError(
                    "source_bound_table_scope_cross_table_overlap"
                )
            used_role_refs.update(role_refs)

            matches = [
                candidate
                for candidate in candidates
                if body_anchor_refs
                and set(body_anchor_refs).issubset(candidate["word_refs"])
                and set(header_refs).issubset(candidate["word_refs"])
            ]
            issues: list[str] = []
            candidate = matches[0] if len(matches) == 1 else None
            if raw["body_status"] == "EMPTY_TEMPLATE":
                issues.append("source_bound_table_scope_empty_template_partial")
            elif raw["body_status"] == "EXPLAINER":
                issues.append("source_bound_table_scope_explainer_non_authoritative")
            elif raw["body_status"] == "UNCERTAIN":
                issues.append("source_bound_table_scope_uncertain")
            if body_anchor_refs and not matches:
                issues.append("source_bound_table_scope_locator_missing")
            elif len(matches) > 1:
                issues.append("source_bound_table_scope_locator_ambiguous")

            candidate_refs = set(candidate["word_refs"]) if candidate else set()
            body_refs = tuple(
                ref
                for ref in candidate["ordered_word_refs"]
                if ref not in set(title_refs) and ref not in set(header_refs)
            ) if candidate else ()
            if raw["body_status"] == "HAS_DATA" and candidate and not body_refs:
                issues.append("source_bound_table_scope_body_empty")
            scope_words = tuple(
                ref
                for ref in words["ordered_refs"]
                if ref in candidate_refs or ref in set(title_refs)
            )
            if not candidate:
                scope_words = tuple(
                    ref for ref in words["ordered_refs"] if ref in role_refs
                )
            if set(scope_words).intersection(used_scope_refs):
                raise SourceBoundTableScopeError(
                    "source_bound_table_scope_cross_table_overlap"
                )
            used_scope_refs.update(scope_words)

            status = "BOUND" if not issues else "PARTIAL"
            scope = SourceBoundTableScopeReceipt(
                scope_ref="",
                source_checksum_sha256=source_checksum,
                page_ref=page_ref,
                page_number=page_number,
                raster_manifest_hash=raster_hash,
                proposal_sha256=proposal_sha256,
                binding_status=status,
                body_status=raw["body_status"],
                locator_candidate_ref=(
                    candidate["candidate_ref"] if candidate else None
                ),
                locator_bbox_ref=(candidate["bbox_ref"] if candidate else None),
                locator_bbox_pdf_points=(candidate["bbox"] if candidate else None),
                title_status=raw["title_status"],
                title_word_refs=title_refs,
                header_status=raw["header_status"],
                header_word_ref_groups=tuple(header_groups),
                body_anchor_word_refs=body_anchor_refs,
                body_word_refs=body_refs,
                scope_word_refs=scope_words,
                issue_codes=tuple(issues),
            )
            scopes.append(replace(scope, scope_ref=_scope_receipt_ref(scope)))

        return SourceBoundTableScopeProjection(
            schema_version=SOURCE_BOUND_TABLE_SCOPE_PROJECTION_SCHEMA,
            policy_version=SOURCE_BOUND_TABLE_SCOPE_POLICY_VERSION,
            source_checksum_sha256=source_checksum,
            page_ref=page_ref,
            page_number=page_number,
            raster_manifest_hash=raster_hash,
            proposal_sha256=proposal_sha256,
            scopes=tuple(scopes),
        )

    def bind_unresolved_observations(
        self,
        *,
        provider_value: Mapping[str, Any],
        full_source_payload: Mapping[str, Any],
        source_checksum_sha256: str,
        raster_manifests: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Bind untrusted document geometry to exact FullSource word refs."""

        source_checksum = _sha256(source_checksum_sha256, "source_checksum")
        payload = _validated_full_source_payload(
            full_source_payload,
            source_checksum_sha256=source_checksum,
        )
        projection = payload["pdf_text_layer_projection"]
        pages = _dicts(projection.get("page_inventory"))
        value = _validated_unresolved_visual_value(provider_value, len(pages))
        unresolved = _dicts(
            projection.get("unresolved_table_region_inventory")
        )
        unresolved_by_page: dict[str, list[dict[str, Any]]] = {}
        unresolved_by_ref: dict[str, dict[str, Any]] = {}
        for region in unresolved:
            ref = region.get("unresolved_table_region_ref")
            page_ref = region.get("page_ref")
            refs = region.get("contributing_word_refs")
            if (
                not isinstance(ref, str)
                or not ref
                or not isinstance(page_ref, str)
                or not isinstance(refs, list)
                or not refs
                or len(refs) != len(set(refs))
            ):
                raise SourceBoundTableScopeError(
                    "source_bound_unresolved_region_inventory_invalid"
                )
            unresolved_by_page.setdefault(page_ref, []).append(region)
            unresolved_by_ref[ref] = region

        observations: list[dict[str, Any]] = []
        region_matches: dict[str, list[str]] = {
            str(region["unresolved_table_region_ref"]): []
            for region in unresolved
        }
        issues: list[dict[str, Any]] = []
        page_coverage: list[dict[str, Any]] = []
        used_role_refs: set[str] = set()
        used_section_refs: set[str] = set()
        for page_index, page in enumerate(pages):
            page_ref = str(page.get("page_ref") or "")
            page_number = int(page.get("page_number") or 0)
            manifest = raster_manifests.get(page_ref)
            if not isinstance(manifest, Mapping):
                raise SourceBoundTableScopeError(
                    "source_bound_unresolved_raster_coverage_invalid"
                )
            page_shape, words, _ = _projection_page(
                projection,
                page_ref=page_ref,
                page_number=page_number,
                allow_empty_words=True,
                require_char_identity=True,
            )
            if (
                manifest.get("pdf_sha256") != source_checksum
                or manifest.get("document_ref") != payload.get("document_ref")
                or manifest.get("page_ref") != page_ref
                or manifest.get("page_number") != page_number
            ):
                raise SourceBoundTableScopeError(
                    "source_bound_unresolved_raster_coverage_invalid"
                )
            tables = value["pages"][page_index]["tables"]
            projected = _project_unresolved_visual_boxes(
                tables, raster_manifest=manifest, page=page_shape
            )
            page_observation_refs = []
            for table_index, (raw, boxes) in enumerate(
                zip(tables, projected, strict=True), 1
            ):
                section_refs = _bind_single_box_by_chars(boxes["section"], words)
                title_groups = _bind_box_groups_by_chars(boxes["title"], words)
                header_groups = _bind_box_groups_by_chars(boxes["header"], words)
                body_groups = _bind_box_groups_by_chars(
                    boxes["body_anchor"], words
                )
                title_refs = _flatten_unique(title_groups)
                header_refs = _flatten_unique(header_groups)
                body_refs = _flatten_unique(body_groups)
                role_refs = (*title_refs, *header_refs, *body_refs)
                observation_issues: list[str] = []
                if len(role_refs) != len(set(role_refs)):
                    observation_issues.append(
                        "source_bound_unresolved_cross_role_overlap"
                    )
                if not set(role_refs) <= set(section_refs):
                    observation_issues.append(
                        "source_bound_unresolved_role_outside_section"
                    )
                if set(role_refs).intersection(used_role_refs):
                    observation_issues.append(
                        "source_bound_unresolved_cross_observation_role_overlap"
                    )
                if set(section_refs).intersection(used_section_refs):
                    observation_issues.append(
                        "source_bound_unresolved_section_overlap"
                    )
                used_role_refs.update(role_refs)
                used_section_refs.update(section_refs)
                for status_key, groups, role in (
                    ("title_status", title_groups, "title"),
                    ("header_status", header_groups, "header"),
                ):
                    status = raw[status_key]
                    if status != "PRESENT":
                        observation_issues.append(
                            f"source_bound_unresolved_{role}_{status.lower()}"
                        )
                    if (status == "PRESENT") != bool(groups):
                        observation_issues.append(
                            f"source_bound_unresolved_{role}_presence_mismatch"
                        )
                if raw["body_status"] != "HAS_DATA":
                    observation_issues.append(
                        "source_bound_unresolved_body_"
                        + str(raw["body_status"]).lower()
                    )
                if raw["body_status"] in {"HAS_DATA", "EXPLAINER"} and not body_groups:
                    observation_issues.append(
                        "source_bound_unresolved_body_presence_mismatch"
                    )
                anchor_refs = set((*header_refs, *body_refs))
                matches = [
                    region
                    for region in unresolved_by_page.get(page_ref, [])
                    if anchor_refs.intersection(
                        set(region.get("contributing_word_refs") or [])
                    )
                ]
                observation_ref = "unresolvedvisualobs_" + stable_digest(
                    [
                        source_checksum,
                        page_ref,
                        manifest.get("manifest_hash"),
                        table_index,
                        raw,
                        *section_refs,
                    ],
                    length=24,
                )
                page_observation_refs.append(observation_ref)
                if len(matches) != 1:
                    observation_issues.append(
                        "source_bound_unresolved_region_"
                        + ("missing" if not matches else "ambiguous")
                    )
                for region in matches:
                    region_matches[str(region["unresolved_table_region_ref"])].append(
                        observation_ref
                    )
                observations.append(
                    {
                        "observation_ref": observation_ref,
                        "page_ref": page_ref,
                        "page_number": page_number,
                        "raster_manifest_hash": manifest.get("manifest_hash"),
                        "section_bbox_pdf_points": list(boxes["section"]),
                        "section_word_refs": list(section_refs),
                        "title_status": raw["title_status"],
                        "title_word_refs": list(title_refs),
                        "header_status": raw["header_status"],
                        "header_word_ref_groups": [list(group) for group in header_groups],
                        "body_status": raw["body_status"],
                        "body_anchor_word_refs": list(body_refs),
                        "matched_unresolved_table_region_refs": [
                            str(region["unresolved_table_region_ref"])
                            for region in matches
                        ],
                        "status": "UNRESOLVED",
                        "issue_codes": sorted(set(observation_issues)),
                    }
                )
                issues.extend(
                    {"code": code, "observation_ref": observation_ref, "page_ref": page_ref}
                    for code in sorted(set(observation_issues))
                )
            page_coverage.append(
                {
                    "page_ref": page_ref,
                    "page_number": page_number,
                    "observation_refs": page_observation_refs,
                    "status": "ACCOUNTED",
                }
            )

        unresolved_coverage = []
        for region_ref, observation_refs in region_matches.items():
            source_region = unresolved_by_ref[region_ref]
            status = "OBSERVED" if len(observation_refs) == 1 else "UNRESOLVED"
            if status == "UNRESOLVED":
                issues.append(
                    {
                        "code": "source_bound_unresolved_region_coverage_"
                        + ("missing" if not observation_refs else "ambiguous"),
                        "unresolved_table_region_ref": region_ref,
                    }
                )
            unresolved_coverage.append(
                {
                    "unresolved_table_region_ref": region_ref,
                    "page_ref": source_region.get("page_ref"),
                    "source_region_bbox_ref": source_region.get("bbox_ref"),
                    "source_region_reason_codes": copy.deepcopy(
                        source_region.get("reason_codes") or []
                    ),
                    "source_region_contributing_word_refs": copy.deepcopy(
                        source_region.get("contributing_word_refs") or []
                    ),
                    "source_region_words_total": len(
                        source_region.get("contributing_word_refs") or []
                    ),
                    "observation_refs": sorted(observation_refs),
                    "status": status,
                }
            )
        return {
            "schema_version": SOURCE_BOUND_UNRESOLVED_VISUAL_SCHEMA,
            "policy_version": SOURCE_BOUND_UNRESOLVED_VISUAL_POLICY_VERSION,
            "source_checksum_sha256": source_checksum,
            "status": "UNRESOLVED",
            "page_coverage": page_coverage,
            "observations": observations,
            "unresolved_region_coverage": unresolved_coverage,
            "coverage": {
                "declared_unresolved_table_region_refs": sorted(
                    region_matches
                ),
                "accounted_unresolved_table_region_refs": sorted(
                    item["unresolved_table_region_ref"]
                    for item in unresolved_coverage
                ),
                "declared_total": len(region_matches),
                "accounted_total": len(unresolved_coverage),
                "all_declared_regions_accounted": (
                    len(region_matches) == len(unresolved_coverage)
                ),
                "all_source_pages_accounted": len(page_coverage) == len(pages),
            },
            "issues": sorted(issues, key=sha256_json),
            "publication_allowed": False,
            "table_identity_assigned": False,
            "continuation_decided": False,
            "model_literals_used_as_source_values": False,
        }


def _scope_receipt_ref(scope: SourceBoundTableScopeReceipt) -> str:
    value = scope.as_dict()
    value.pop("scope_ref")
    return "tablescopereceipt_" + sha256_json(value)[:24]


def _validated_full_source_payload(
    value: Mapping[str, Any], *, source_checksum_sha256: str
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SourceBoundTableScopeError(
            "source_bound_table_scope_full_source_invalid"
        )
    payload = copy.deepcopy(value)
    try:
        validation = validate_pdf_text_layer_payload(payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise SourceBoundTableScopeError(
            "source_bound_table_scope_full_source_invalid"
        ) from exc
    if validation.get("validator_status") != "passed":
        raise SourceBoundTableScopeError(
            "source_bound_table_scope_full_source_invalid"
        )
    expected_source_checksum_ref = "srcsum_" + stable_digest(
        [payload.get("document_ref"), source_checksum_sha256], length=24
    )
    if payload.get("source_checksum_ref") != expected_source_checksum_ref:
        raise SourceBoundTableScopeError(
            "source_bound_table_scope_source_binding_mismatch"
        )
    projection = payload.get("pdf_text_layer_projection")
    if not isinstance(projection, dict):
        raise SourceBoundTableScopeError(
            "source_bound_table_scope_full_source_invalid"
        )
    return payload


def _validated_proposal(value: Any) -> dict[str, Any]:
    errors = sorted(
        Draft202012Validator(proposal_schema()).iter_errors(value),
        key=lambda item: list(item.path),
    )
    if errors:
        raise SourceBoundTableScopeError("source_bound_table_scope_proposal_invalid")
    result = copy.deepcopy(value)
    for table in result["tables"]:
        for key in ("title_boxes_2d", "header_boxes_2d", "body_anchor_boxes_2d"):
            boxes = table[key]
            if any(_invalid_box(box) for box in boxes):
                raise SourceBoundTableScopeError(
                    "source_bound_table_scope_proposal_invalid"
                )
    return result


def _projection_page(
    projection: Mapping[str, Any],
    *,
    page_ref: str,
    page_number: int,
    allow_empty_words: bool = False,
    require_char_identity: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(projection, Mapping):
        raise SourceBoundTableScopeError("source_bound_table_scope_projection_invalid")
    if projection.get("schema_version") != PDF_TEXT_LAYER_PROJECTION_SCHEMA_VERSION:
        raise SourceBoundTableScopeError("source_bound_table_scope_projection_invalid")
    all_pages = _dicts(projection.get("page_inventory"))
    page_refs = [item.get("page_ref") for item in all_pages]
    page_numbers = [item.get("page_number") for item in all_pages]
    if (
        not all(isinstance(ref, str) and ref for ref in page_refs)
        or len(page_refs) != len(set(page_refs))
        or not all(
            isinstance(number, int)
            and not isinstance(number, bool)
            and number > 0
            for number in page_numbers
        )
        or len(page_numbers) != len(set(page_numbers))
    ):
        raise SourceBoundTableScopeError("source_bound_table_scope_page_invalid")
    pages = [
        item
        for item in all_pages
        if item.get("page_ref") == page_ref and item.get("page_number") == page_number
    ]
    if len(pages) != 1:
        raise SourceBoundTableScopeError("source_bound_table_scope_page_invalid")
    width = _positive_number(
        pages[0].get("layout_page_width") or pages[0].get("width")
    )
    height = _positive_number(
        pages[0].get("layout_page_height") or pages[0].get("height")
    )
    raw_bbox_by_ref: dict[str, Any] = {}
    bbox_page_by_ref: dict[str, str] = {}
    for item in _dicts(projection.get("bbox_inventory")):
        ref = item.get("bbox_ref")
        owner_page_ref = item.get("page_ref")
        if (
            not isinstance(ref, str)
            or not ref
            or ref in raw_bbox_by_ref
            or owner_page_ref not in set(page_refs)
        ):
            raise SourceBoundTableScopeError(
                "source_bound_table_scope_bbox_inventory_invalid"
            )
        raw_bbox_by_ref[ref] = item.get("bbox")
        bbox_page_by_ref[ref] = owner_page_ref
    char_by_ref: dict[str, tuple[float, float, float, float]] = {}
    if require_char_identity:
        for item in _dicts(projection.get("char_inventory")):
            ref = item.get("char_ref")
            owner_page_ref = item.get("page_ref")
            bbox_ref = item.get("bbox_ref")
            if (
                not isinstance(ref, str)
                or not ref
                or ref in char_by_ref
                or owner_page_ref not in set(page_refs)
                or bbox_ref not in raw_bbox_by_ref
                or bbox_page_by_ref.get(bbox_ref) != owner_page_ref
            ):
                raise SourceBoundTableScopeError(
                    "source_bound_table_scope_char_inventory_invalid"
                )
            char_by_ref[ref] = _bbox(raw_bbox_by_ref[bbox_ref])
    word_by_ref: dict[str, dict[str, Any]] = {}
    all_word_refs: set[str] = set()
    selected_orders: set[int] = set()
    for item in _dicts(projection.get("word_inventory")):
        owner_page_ref = item.get("page_ref")
        ref = item.get("word_ref")
        bbox_ref = item.get("bbox_ref")
        raw_bbox = raw_bbox_by_ref.get(bbox_ref)
        order = item.get("geometry_reading_order", item.get("parser_ordinal"))
        char_refs = item.get("char_refs")
        if (
            not isinstance(ref, str)
            or not ref
            or ref in all_word_refs
            or owner_page_ref not in set(page_refs)
            or raw_bbox is None
            or bbox_page_by_ref.get(bbox_ref) != owner_page_ref
            or not isinstance(order, int)
            or isinstance(order, bool)
            or (
                require_char_identity
                and (
                    not isinstance(char_refs, list)
                    or not char_refs
                    or len(char_refs) != len(set(char_refs))
                    or any(char_ref not in char_by_ref for char_ref in char_refs)
                )
            )
        ):
            raise SourceBoundTableScopeError(
                "source_bound_table_scope_word_inventory_invalid"
            )
        bbox = _bbox(raw_bbox)
        all_word_refs.add(ref)
        if owner_page_ref != page_ref:
            continue
        if order in selected_orders:
            raise SourceBoundTableScopeError(
                "source_bound_table_scope_word_inventory_invalid"
            )
        selected_orders.add(order)
        word_by_ref[ref] = {
            "word_ref": ref,
            "bbox": bbox,
            "char_bboxes": (
                tuple(char_by_ref[value] for value in char_refs)
                if require_char_identity
                else ()
            ),
            "order": order,
        }
    if not word_by_ref and not allow_empty_words:
        raise SourceBoundTableScopeError(
            "source_bound_table_scope_word_inventory_invalid"
        )
    ordered_refs = tuple(
        item["word_ref"]
        for item in sorted(word_by_ref.values(), key=lambda item: item["order"])
    )
    candidates = []
    candidate_refs: set[str] = set()
    for item in _dicts(projection.get("table_candidate_inventory")):
        owner_page_ref = item.get("page_ref")
        candidate_ref = item.get("table_candidate_ref")
        bbox_ref = item.get("bbox_ref")
        refs = item.get("contributing_word_refs")
        if (
            not isinstance(candidate_ref, str)
            or not candidate_ref
            or candidate_ref in candidate_refs
            or owner_page_ref not in set(page_refs)
            or not isinstance(bbox_ref, str)
            or bbox_ref not in raw_bbox_by_ref
            or bbox_page_by_ref.get(bbox_ref) != owner_page_ref
            or not isinstance(refs, list)
            or not refs
            or any(not isinstance(ref, str) or ref not in all_word_refs for ref in refs)
            or len(refs) != len(set(refs))
        ):
            raise SourceBoundTableScopeError(
                "source_bound_table_scope_locator_candidate_invalid"
            )
        candidate_refs.add(candidate_ref)
        if owner_page_ref != page_ref:
            continue
        if any(ref not in word_by_ref for ref in refs):
            raise SourceBoundTableScopeError(
                "source_bound_table_scope_locator_candidate_invalid"
            )
        ordered_candidate_refs = tuple(ref for ref in ordered_refs if ref in set(refs))
        candidates.append(
            {
                "candidate_ref": candidate_ref,
                "bbox_ref": bbox_ref,
                "bbox": _bbox(raw_bbox_by_ref[bbox_ref]),
                "word_refs": set(refs),
                "ordered_word_refs": ordered_candidate_refs,
            }
        )
    return (
        {"width": width, "height": height},
        {"by_ref": word_by_ref, "ordered_refs": ordered_refs},
        candidates,
    )


def _project_box_groups(
    tables: list[dict[str, Any]],
    *,
    raster_manifest: Mapping[str, Any],
    page: dict[str, Any],
    page_abs_tol: float = 1e-6,
) -> list[dict[str, tuple[tuple[float, float, float, float], ...]]]:
    if not isinstance(raster_manifest, dict):
        raise SourceBoundTableScopeError(
            "source_bound_table_scope_raster_manifest_invalid"
        )
    actual_page_bbox = raster_manifest.get("actual_page_bbox")
    try:
        owner = PdfTableLocatorProjectionFactory().create()
        transform_check = owner.project(
            provider_value={"tables": []},
            raster_manifest=copy.deepcopy(raster_manifest),
            expected_page_bbox=copy.deepcopy(actual_page_bbox),
        )
    except PdfTableLocatorError as exc:
        raise SourceBoundTableScopeError(
            "source_bound_table_scope_raster_manifest_invalid"
        ) from exc
    page_bbox = _bbox(transform_check.get("page_bbox_pdf_points"))
    if (
        not math.isclose(
            page_bbox[2] - page_bbox[0], page["width"], abs_tol=page_abs_tol
        )
        or not math.isclose(
            page_bbox[3] - page_bbox[1], page["height"], abs_tol=page_abs_tol
        )
        or transform_check.get("coordinate_contract")
        != PDF_TABLE_LOCATOR_COORDINATE_CONTRACT
    ):
        raise SourceBoundTableScopeError(
            "source_bound_table_scope_raster_page_mismatch"
        )

    result = []
    for table in tables:
        projected: dict[str, tuple[tuple[float, float, float, float], ...]] = {}
        for role, key in (
            ("title", "title_boxes_2d"),
            ("header", "header_boxes_2d"),
            ("body_anchor", "body_anchor_boxes_2d"),
        ):
            role_boxes = []
            for box in table[key]:
                try:
                    owner_value = owner.project(
                        provider_value={"tables": [{"box_2d": list(box)}]},
                        raster_manifest=copy.deepcopy(raster_manifest),
                        expected_page_bbox=list(page_bbox),
                    )
                except PdfTableLocatorError as exc:
                    raise SourceBoundTableScopeError(
                        "source_bound_table_scope_raster_manifest_invalid"
                    ) from exc
                role_boxes.append(_bbox(owner_value["tables"][0]["bbox_pdf_points"]))
            projected[role] = tuple(role_boxes)
        result.append(projected)
    return result


def _bind_box_groups(
    boxes: tuple[tuple[float, float, float, float], ...], words: dict[str, Any]
) -> tuple[tuple[str, ...], ...]:
    groups = []
    for box in boxes:
        box_x0, box_top, box_x1, box_bottom = box
        selected = []
        for ref in words["ordered_refs"]:
            x0, top, x1, bottom = words["by_ref"][ref]["bbox"]
            center_x = (x0 + x1) / 2.0
            center_y = (top + bottom) / 2.0
            if (
                box_x0 <= center_x <= box_x1
                and box_top <= center_y <= box_bottom
            ):
                selected.append(ref)
        if not selected:
            raise SourceBoundTableScopeError(
                "source_bound_table_scope_box_binding_empty"
            )
        groups.append(tuple(selected))
    return tuple(groups)


def _bind_single_box(
    box: tuple[float, float, float, float], words: dict[str, Any]
) -> tuple[str, ...]:
    return _bind_box_groups((box,), words)[0]


def _bind_box_groups_by_chars(
    boxes: tuple[tuple[float, float, float, float], ...], words: dict[str, Any]
) -> tuple[tuple[str, ...], ...]:
    groups = []
    for box in boxes:
        box_x0, box_top, box_x1, box_bottom = box
        selected = []
        for ref in words["ordered_refs"]:
            char_centers = [
                ((x0 + x1) / 2.0, (top + bottom) / 2.0)
                for x0, top, x1, bottom in words["by_ref"][ref]["char_bboxes"]
            ]
            if char_centers and all(
                box_x0 <= center_x <= box_x1
                and box_top <= center_y <= box_bottom
                for center_x, center_y in char_centers
            ):
                selected.append(ref)
        if not selected:
            raise SourceBoundTableScopeError(
                "source_bound_table_scope_box_binding_empty"
            )
        groups.append(tuple(selected))
    return tuple(groups)


def _bind_single_box_by_chars(
    box: tuple[float, float, float, float], words: dict[str, Any]
) -> tuple[str, ...]:
    return _bind_box_groups_by_chars((box,), words)[0]


def _validated_unresolved_visual_value(
    value: Any, page_count: int
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {"pages"}:
        raise SourceBoundTableScopeError(
            "source_bound_unresolved_visual_value_invalid"
        )
    pages = value.get("pages")
    if not isinstance(pages, list) or len(pages) != page_count:
        raise SourceBoundTableScopeError(
            "source_bound_unresolved_visual_page_coverage_invalid"
        )
    result = copy.deepcopy(dict(value))
    required = {
        "table_box_2d",
        "title_status",
        "title_boxes_2d",
        "header_status",
        "header_boxes_2d",
        "body_status",
        "body_anchor_boxes_2d",
    }
    for page in result["pages"]:
        if not isinstance(page, dict) or set(page) != {"tables"}:
            raise SourceBoundTableScopeError(
                "source_bound_unresolved_visual_value_invalid"
            )
        tables = page.get("tables")
        if not isinstance(tables, list) or len(tables) > 64:
            raise SourceBoundTableScopeError(
                "source_bound_unresolved_visual_value_invalid"
            )
        for table in tables:
            if not isinstance(table, dict) or set(table) != required:
                raise SourceBoundTableScopeError(
                    "source_bound_unresolved_visual_value_invalid"
                )
            if table["title_status"] not in {"PRESENT", "ABSENT", "UNCERTAIN"}:
                raise SourceBoundTableScopeError(
                    "source_bound_unresolved_visual_value_invalid"
                )
            if table["header_status"] not in {"PRESENT", "ABSENT", "UNCERTAIN"}:
                raise SourceBoundTableScopeError(
                    "source_bound_unresolved_visual_value_invalid"
                )
            if table["body_status"] not in {
                "HAS_DATA", "EMPTY_TEMPLATE", "EXPLAINER", "UNCERTAIN"
            }:
                raise SourceBoundTableScopeError(
                    "source_bound_unresolved_visual_value_invalid"
                )
            for key in (
                "table_box_2d",
                "title_boxes_2d",
                "header_boxes_2d",
                "body_anchor_boxes_2d",
            ):
                boxes = [table[key]] if key == "table_box_2d" else table[key]
                if not isinstance(boxes, list) or any(_invalid_box(box) for box in boxes):
                    raise SourceBoundTableScopeError(
                        "source_bound_unresolved_visual_value_invalid"
                    )
    return result


def _project_unresolved_visual_boxes(
    tables: list[dict[str, Any]],
    *,
    raster_manifest: Mapping[str, Any],
    page: dict[str, Any],
) -> list[dict[str, Any]]:
    projected_roles = _project_box_groups(
        tables,
        raster_manifest=raster_manifest,
        page=page,
        page_abs_tol=1e-4,
    )
    owner = PdfTableLocatorProjectionFactory().create()
    result = []
    for table, roles in zip(tables, projected_roles, strict=True):
        try:
            projected = owner.project(
                provider_value={"tables": [{"box_2d": table["table_box_2d"]}]},
                raster_manifest=copy.deepcopy(raster_manifest),
                expected_page_bbox=copy.deepcopy(
                    raster_manifest.get("actual_page_bbox")
                ),
            )
        except PdfTableLocatorError as exc:
            raise SourceBoundTableScopeError(
                "source_bound_unresolved_raster_manifest_invalid"
            ) from exc
        section = _bbox(projected["tables"][0]["bbox_pdf_points"])
        role_boxes = [
            box
            for key in ("title", "header", "body_anchor")
            for box in roles[key]
        ]
        if role_boxes:
            section = (
                min([section[0], *[box[0] for box in role_boxes]]),
                min([section[1], *[box[1] for box in role_boxes]]),
                max([section[2], *[box[2] for box in role_boxes]]),
                max([section[3], *[box[3] for box in role_boxes]]),
            )
        result.append({"section": section, **roles})
    return result


def _presence(status: str, groups: tuple[tuple[str, ...], ...], kind: str) -> None:
    if (status == "PRESENT") != bool(groups):
        raise SourceBoundTableScopeError(
            f"source_bound_table_scope_{kind}_presence_mismatch"
        )


def _body_presence(status: str, groups: tuple[tuple[str, ...], ...]) -> None:
    if status in {"HAS_DATA", "EXPLAINER"} and not groups:
        raise SourceBoundTableScopeError(
            "source_bound_table_scope_body_presence_mismatch"
        )
    if status == "EMPTY_TEMPLATE" and groups:
        raise SourceBoundTableScopeError(
            "source_bound_table_scope_body_presence_mismatch"
        )


def _flatten_unique(groups: tuple[tuple[str, ...], ...]) -> tuple[str, ...]:
    values = tuple(ref for group in groups for ref in group)
    if len(values) != len(set(values)):
        raise SourceBoundTableScopeError(
            "source_bound_table_scope_box_word_overlap"
        )
    return values


def _invalid_box(value: list[int]) -> bool:
    ymin, xmin, ymax, xmax = value
    return ymax <= ymin or xmax <= xmin


def _bbox(value: Any) -> tuple[float, float, float, float]:
    if (
        not isinstance(value, list)
        or len(value) != 4
        or any(
            not isinstance(item, (int, float))
            or isinstance(item, bool)
            or not math.isfinite(float(item))
            for item in value
        )
    ):
        raise SourceBoundTableScopeError("source_bound_table_scope_bbox_invalid")
    result = tuple(float(item) for item in value)
    if result[2] <= result[0] or result[3] <= result[1]:
        raise SourceBoundTableScopeError("source_bound_table_scope_bbox_invalid")
    return result


def _positive_number(value: Any) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or float(value) <= 0
    ):
        raise SourceBoundTableScopeError("source_bound_table_scope_page_invalid")
    return float(value)


def _sha256(value: Any, name: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise SourceBoundTableScopeError(f"source_bound_table_scope_{name}_invalid")
    return value


def _dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise SourceBoundTableScopeError("source_bound_table_scope_projection_invalid")
    return value


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "SOURCE_BOUND_TABLE_SCOPE_POLICY_VERSION",
    "SOURCE_BOUND_TABLE_SCOPE_PROJECTION_SCHEMA",
    "SOURCE_BOUND_TABLE_SCOPE_PROPOSAL_SCHEMA",
    "SOURCE_BOUND_UNRESOLVED_VISUAL_SCHEMA",
    "SOURCE_BOUND_UNRESOLVED_VISUAL_POLICY_VERSION",
    "SourceBoundTableScopeReceipt",
    "SourceBoundTableScopeBinder",
    "SourceBoundTableScopeError",
    "SourceBoundTableScopeFactory",
    "SourceBoundTableScopeProjection",
    "proposal_schema",
]
