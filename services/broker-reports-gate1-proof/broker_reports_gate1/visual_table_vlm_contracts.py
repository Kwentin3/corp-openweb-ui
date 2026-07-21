"""Bounded visual-table proposal contracts and deterministic validation.

The provider describes what it sees in one declared image scope.  It never
publishes a canonical table.  This module owns the versioned provider schema
and proves structural/source-region invariants before a proposal can advance.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import warnings
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from PIL import Image, UnidentifiedImageError


VISUAL_TABLE_SCOPE_SCHEMA_VERSION = "broker_reports_visual_table_scope_v1"
VISUAL_TABLE_PROPOSAL_SCHEMA_VERSION = (
    "broker_reports_visual_table_provider_proposal_v1"
)
VISUAL_TABLE_RESULT_SCHEMA_VERSION = "broker_reports_visual_table_vlm_result_v1"
VISUAL_TABLE_VALIDATOR_VERSION = "broker_reports_visual_table_validator_v1"
VISUAL_TABLE_ACCEPTANCE_STATUS = "disabled_until_server_authenticated_evidence_binding"

VISUAL_TABLE_SCOPE_KINDS = frozenset({"declared_page", "table_crop"})
VISUAL_TABLE_TERMINAL_RESULTS = frozenset(
    {
        "proposal_validated_and_accepted",
        "proposal_requires_review",
        "proposal_rejected",
        "malformed_provider_output",
        "unresolved_visual_scope",
        "unsupported_visual_layout",
    }
)

_LAYOUT_STATES = frozenset({"supported", "unresolved", "unsupported"})
_ROW_ROLES = frozenset({"header", "body", "subtotal", "total"})
_CONTENT_STATES = frozenset({"present", "empty", "unreadable"})
_CONTINUATION_STATES = frozenset(
    {
        "none",
        "continues_from_previous",
        "continues_to_next",
        "bidirectional",
        "unresolved",
    }
)
_RELATIONSHIP_TYPES = frozenset({"cell_value", "omission"})
_CODE = re.compile(r"^[a-z][a-z0-9_]{2,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TOTAL_LABEL = re.compile(r"(?:^|\s)(?:итого|всего|total|subtotal)(?:\s|$)", re.I)

_SCOPE_KEYS = {
    "schema_version",
    "scope_kind",
    "source_ref",
    "document_ref",
    "page_number",
    "region_ref",
    "declared_region_bbox",
    "page_size_pixels",
    "image_size_pixels",
    "image_sha256",
    "image_mime_type",
    "renderer_version",
    "source_region_inventory",
}
_SOURCE_REGION_REQUIRED_KEYS = {
    "source_region_ref",
    "normalized_bbox",
    "segment_sha256",
    "material",
}
_SOURCE_REGION_EVIDENCE_KEYS = {
    "deterministic_text",
    "deterministic_text_sha256",
    "deterministic_extractor_ref",
}
_PROPOSAL_KEYS = {
    "schema_version",
    "request_ref",
    "layout_status",
    "detected_table_regions",
    "source_region_relationships",
    "uncertainties",
    "omissions",
}
_TABLE_KEYS = {
    "table_ref",
    "normalized_bbox",
    "ordered_rows",
    "ordered_columns",
    "cells",
    "headers",
    "spanning_cells",
    "totals",
    "continuation_evidence",
}
_ROW_KEYS = {"row_ref", "order", "structural_role"}
_COLUMN_KEYS = {"column_ref", "order"}
_CELL_KEYS = {
    "cell_ref",
    "row_ref",
    "column_ref",
    "row_span",
    "column_span",
    "content_state",
    "source_text",
    "normalized_bbox",
    "source_region_refs",
}
_HEADER_KEYS = {
    "header_cell_ref",
    "parent_header_cell_ref",
    "applies_to_column_refs",
    "applies_to_cell_refs",
}
_SPAN_KEYS = {
    "cell_ref",
    "row_span",
    "column_span",
    "covered_row_refs",
    "covered_column_refs",
}
_TOTAL_KEYS = {
    "row_ref",
    "structural_role",
    "label_cell_refs",
    "value_cell_refs",
}
_CONTINUATION_KEYS = {
    "state",
    "evidence_cell_refs",
    "adjacent_page_numbers",
}
_RELATIONSHIP_KEYS = {
    "source_region_ref",
    "relationship_type",
    "target_ref",
}
_UNCERTAINTY_KEYS = {
    "uncertainty_ref",
    "subject_ref",
    "code",
    "material",
}
_OMISSION_KEYS = {
    "omission_ref",
    "source_region_refs",
    "reason_code",
    "material",
}


class VisualTableContractError(ValueError):
    def __init__(self, code: str, subject: str = "") -> None:
        self.code = code
        self.subject = subject
        super().__init__(code if not subject else f"{code}:{subject}")


@dataclass(frozen=True)
class VisualTableContractConfig:
    maximum_image_bytes: int = 15_728_640
    maximum_image_dimension: int = 8_192
    maximum_image_pixels: int = 20_000_000
    maximum_request_bytes: int = 33_554_432
    maximum_response_bytes: int = 4_194_304
    maximum_output_tokens: int = 131_072
    maximum_tables: int = 16
    maximum_rows_per_table: int = 256
    maximum_columns_per_table: int = 128
    maximum_cells: int = 4_096
    maximum_source_regions: int = 16_384
    maximum_annotations: int = 4_096
    maximum_refs_per_item: int = 256
    maximum_identifier_chars: int = 255
    maximum_source_text_chars: int = 4_096

    def __post_init__(self) -> None:
        values = tuple(vars(self).values())
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value <= 0
            for value in values
        ):
            raise VisualTableContractError("visual_table_contract_budget_invalid")
        encoded_image_ceiling = 4 * ((self.maximum_image_bytes + 2) // 3)
        if (
            self.maximum_request_bytes <= encoded_image_ceiling
            or self.maximum_output_tokens > self.maximum_response_bytes
            or self.maximum_identifier_chars > self.maximum_source_text_chars
            or self.maximum_image_pixels
            > self.maximum_image_dimension * self.maximum_image_dimension
            or self.maximum_refs_per_item > self.maximum_source_regions
            or self.maximum_cells
            > self.maximum_tables
            * self.maximum_rows_per_table
            * self.maximum_columns_per_table
        ):
            raise VisualTableContractError("visual_table_contract_budget_incoherent")


@dataclass(frozen=True)
class VisualTableValidationOutcome:
    terminal_result: str
    reason_codes: tuple[str, ...]
    proposal: dict[str, Any] | None
    proposal_sha256: str | None


def canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise VisualTableContractError("visual_table_json_not_canonicalizable") from exc


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def visual_table_proposal_json_schema(
    config: VisualTableContractConfig | None = None,
) -> dict[str, Any]:
    """Return the strict provider-facing JSON schema.

    Confidence and provider-agreement fields are intentionally absent and all
    objects reject additional properties.  Neither can become authority by
    slipping into the proposal envelope.
    """

    config = config or VisualTableContractConfig()
    bbox = {
        "type": "array",
        "minItems": 4,
        "maxItems": 4,
        "items": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    }
    identifier = {
        "type": "string",
        "minLength": 1,
        "maxLength": config.maximum_identifier_chars,
    }
    optional_identifier = {
        "type": "string",
        "maxLength": config.maximum_identifier_chars,
    }
    code = {
        "type": "string",
        "maxLength": min(128, config.maximum_identifier_chars),
        "pattern": _CODE.pattern,
    }

    def string_array(maximum_items: int) -> dict[str, Any]:
        return {
            "type": "array",
            "maxItems": maximum_items,
            "items": identifier,
        }

    row = _schema_object(
        {
            "row_ref": identifier,
            "order": {"type": "integer", "minimum": 0},
            "structural_role": {"type": "string", "enum": sorted(_ROW_ROLES)},
        },
        _ROW_KEYS,
    )
    column = _schema_object(
        {
            "column_ref": identifier,
            "order": {"type": "integer", "minimum": 0},
        },
        _COLUMN_KEYS,
    )
    cell = _schema_object(
        {
            "cell_ref": identifier,
            "row_ref": identifier,
            "column_ref": identifier,
            "row_span": {"type": "integer", "minimum": 1},
            "column_span": {"type": "integer", "minimum": 1},
            "content_state": {
                "type": "string",
                "enum": sorted(_CONTENT_STATES),
            },
            "source_text": {
                "type": "string",
                "maxLength": config.maximum_source_text_chars,
            },
            "normalized_bbox": bbox,
            "source_region_refs": string_array(config.maximum_refs_per_item),
        },
        _CELL_KEYS,
    )
    header = _schema_object(
        {
            "header_cell_ref": identifier,
            "parent_header_cell_ref": optional_identifier,
            "applies_to_column_refs": string_array(config.maximum_columns_per_table),
            "applies_to_cell_refs": string_array(config.maximum_cells),
        },
        _HEADER_KEYS,
    )
    span = _schema_object(
        {
            "cell_ref": identifier,
            "row_span": {"type": "integer", "minimum": 1},
            "column_span": {"type": "integer", "minimum": 1},
            "covered_row_refs": string_array(config.maximum_rows_per_table),
            "covered_column_refs": string_array(config.maximum_columns_per_table),
        },
        _SPAN_KEYS,
    )
    total = _schema_object(
        {
            "row_ref": identifier,
            "structural_role": {
                "type": "string",
                "enum": ["subtotal", "total"],
            },
            "label_cell_refs": string_array(config.maximum_cells),
            "value_cell_refs": string_array(config.maximum_cells),
        },
        _TOTAL_KEYS,
    )
    continuation = _schema_object(
        {
            "state": {"type": "string", "enum": sorted(_CONTINUATION_STATES)},
            "evidence_cell_refs": string_array(config.maximum_cells),
            "adjacent_page_numbers": {
                "type": "array",
                "maxItems": 2,
                "items": {"type": "integer", "minimum": 1},
            },
        },
        _CONTINUATION_KEYS,
    )
    table = _schema_object(
        {
            "table_ref": identifier,
            "normalized_bbox": bbox,
            "ordered_rows": {
                "type": "array",
                "minItems": 1,
                "maxItems": config.maximum_rows_per_table,
                "items": row,
            },
            "ordered_columns": {
                "type": "array",
                "minItems": 1,
                "maxItems": config.maximum_columns_per_table,
                "items": column,
            },
            "cells": {
                "type": "array",
                "minItems": 1,
                "maxItems": config.maximum_cells,
                "items": cell,
            },
            "headers": {
                "type": "array",
                "maxItems": config.maximum_cells,
                "items": header,
            },
            "spanning_cells": {
                "type": "array",
                "maxItems": config.maximum_cells,
                "items": span,
            },
            "totals": {
                "type": "array",
                "maxItems": config.maximum_rows_per_table,
                "items": total,
            },
            "continuation_evidence": continuation,
        },
        _TABLE_KEYS,
    )
    relationship = _schema_object(
        {
            "source_region_ref": identifier,
            "relationship_type": {
                "type": "string",
                "enum": sorted(_RELATIONSHIP_TYPES),
            },
            "target_ref": identifier,
        },
        _RELATIONSHIP_KEYS,
    )
    uncertainty = _schema_object(
        {
            "uncertainty_ref": identifier,
            "subject_ref": identifier,
            "code": code,
            "material": {"type": "boolean"},
        },
        _UNCERTAINTY_KEYS,
    )
    omission = _schema_object(
        {
            "omission_ref": identifier,
            "source_region_refs": string_array(config.maximum_refs_per_item),
            "reason_code": code,
            "material": {"type": "boolean"},
        },
        _OMISSION_KEYS,
    )
    return {
        "$id": VISUAL_TABLE_PROPOSAL_SCHEMA_VERSION,
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "schema_version": {
                "type": "string",
                "enum": [VISUAL_TABLE_PROPOSAL_SCHEMA_VERSION],
            },
            "request_ref": identifier,
            "layout_status": {"type": "string", "enum": sorted(_LAYOUT_STATES)},
            "detected_table_regions": {
                "type": "array",
                "maxItems": config.maximum_tables,
                "items": table,
            },
            "source_region_relationships": {
                "type": "array",
                "maxItems": config.maximum_source_regions,
                "items": relationship,
            },
            "uncertainties": {
                "type": "array",
                "maxItems": config.maximum_annotations,
                "items": uncertainty,
            },
            "omissions": {
                "type": "array",
                "maxItems": config.maximum_annotations,
                "items": omission,
            },
        },
        "required": sorted(_PROPOSAL_KEYS),
    }


def parse_visual_table_proposal(
    value: bytes | str | dict[str, Any],
    *,
    config: VisualTableContractConfig | None = None,
) -> tuple[dict[str, Any], bytes]:
    """Parse and syntactically validate one untrusted provider response."""

    config = config or VisualTableContractConfig()
    raw_bytes: bytes
    if isinstance(value, bytes):
        raw_bytes = value
        if len(raw_bytes) > config.maximum_response_bytes:
            raise VisualTableContractError("visual_table_provider_output_too_large")
        try:
            parsed = json.loads(
                value.decode("utf-8"),
                parse_constant=_reject_json_constant,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise VisualTableContractError(
                "visual_table_provider_json_invalid"
            ) from exc
    elif isinstance(value, str):
        raw_bytes = value.encode("utf-8")
        if len(raw_bytes) > config.maximum_response_bytes:
            raise VisualTableContractError("visual_table_provider_output_too_large")
        try:
            parsed = json.loads(value, parse_constant=_reject_json_constant)
        except (json.JSONDecodeError, ValueError) as exc:
            raise VisualTableContractError(
                "visual_table_provider_json_invalid"
            ) from exc
    elif isinstance(value, dict):
        raw_bytes = canonical_json_bytes(value)
        parsed = copy.deepcopy(value)
    else:
        raise VisualTableContractError("visual_table_provider_output_type_invalid")
    if len(raw_bytes) > config.maximum_response_bytes:
        raise VisualTableContractError("visual_table_provider_output_too_large")
    _validate_proposal_shape(parsed, config=config)
    return copy.deepcopy(parsed), raw_bytes


def validate_visual_table_scope(
    scope: Any,
    *,
    image_bytes: bytes,
    config: VisualTableContractConfig | None = None,
) -> list[str]:
    config = config or VisualTableContractConfig()
    errors: list[str] = []
    if not isinstance(scope, dict) or set(scope) != _SCOPE_KEYS:
        return ["visual_table_scope_shape_invalid"]
    actual_image_sha256 = (
        hashlib.sha256(image_bytes).hexdigest()
        if isinstance(image_bytes, bytes)
        else None
    )
    if scope.get("schema_version") != VISUAL_TABLE_SCOPE_SCHEMA_VERSION:
        errors.append("visual_table_scope_schema_invalid")
    if scope.get("scope_kind") not in VISUAL_TABLE_SCOPE_KINDS:
        errors.append("visual_table_scope_kind_invalid")
    for field in ("source_ref", "document_ref", "region_ref", "renderer_version"):
        if not _bounded_nonempty_string(
            scope.get(field), maximum_chars=config.maximum_identifier_chars
        ):
            errors.append(f"visual_table_scope_{field}_invalid")
    page_number = scope.get("page_number")
    if not _positive_int(page_number):
        errors.append("visual_table_scope_page_number_invalid")
    page_size = _integer_pair(scope.get("page_size_pixels"))
    image_size = _integer_pair(scope.get("image_size_pixels"))
    bbox = _integer_bbox(scope.get("declared_region_bbox"))
    if page_size is None or image_size is None:
        errors.append("visual_table_scope_image_dimensions_invalid")
    elif (
        max(image_size) > config.maximum_image_dimension
        or image_size[0] * image_size[1] > config.maximum_image_pixels
    ):
        errors.append("visual_table_scope_image_pixel_budget_exceeded")
    if page_size is not None and (
        bbox is None
        or not _bbox_within_pixel_extent(bbox, width=page_size[0], height=page_size[1])
    ):
        errors.append("visual_table_scope_region_invalid")
    if (
        scope.get("scope_kind") == "declared_page"
        and page_size is not None
        and image_size is not None
        and (bbox != [0, 0, page_size[0], page_size[1]] or image_size != page_size)
    ):
        errors.append("visual_table_declared_page_not_exact")
    if (
        scope.get("scope_kind") == "table_crop"
        and bbox is not None
        and image_size is not None
        and image_size != [bbox[2] - bbox[0], bbox[3] - bbox[1]]
    ):
        errors.append("visual_table_crop_not_exact")
    if not isinstance(image_bytes, bytes) or not image_bytes:
        errors.append("visual_table_scope_image_missing")
    elif len(image_bytes) > config.maximum_image_bytes:
        errors.append("visual_table_scope_image_budget_exceeded")
    elif scope.get("image_sha256") != actual_image_sha256:
        errors.append("visual_table_scope_image_hash_mismatch")
    mime_type = scope.get("image_mime_type")
    if mime_type not in {"image/png", "image/jpeg"}:
        errors.append("visual_table_scope_image_mime_type_invalid")
    elif (
        isinstance(image_bytes, bytes)
        and image_bytes
        and len(image_bytes) <= config.maximum_image_bytes
        and scope.get("image_sha256") == actual_image_sha256
    ):
        decoded_size, decode_error = _decode_raster_dimensions(
            image_bytes,
            mime_type=mime_type,
            config=config,
        )
        if decode_error is not None:
            errors.append(decode_error)
        elif image_size is not None and decoded_size != image_size:
            errors.append("visual_table_scope_image_dimensions_mismatch")
    inventory = scope.get("source_region_inventory")
    if (
        not isinstance(inventory, list)
        or len(inventory) > config.maximum_source_regions
    ):
        errors.append("visual_table_source_region_inventory_invalid")
        return sorted(set(errors))
    seen: set[str] = set()
    for item in inventory:
        if not isinstance(item, dict) or set(item) not in {
            frozenset(_SOURCE_REGION_REQUIRED_KEYS),
            frozenset(_SOURCE_REGION_REQUIRED_KEYS | _SOURCE_REGION_EVIDENCE_KEYS),
        }:
            errors.append("visual_table_source_region_shape_invalid")
            continue
        ref = item.get("source_region_ref")
        if (
            not _bounded_nonempty_string(
                ref, maximum_chars=config.maximum_identifier_chars
            )
            or ref in seen
        ):
            errors.append("visual_table_source_region_identity_invalid")
        else:
            seen.add(ref)
        if _normalized_bbox(item.get("normalized_bbox")) is None:
            errors.append("visual_table_source_region_bbox_invalid")
        if not isinstance(item.get("segment_sha256"), str) or not _SHA256.fullmatch(
            item["segment_sha256"]
        ):
            errors.append("visual_table_source_region_hash_invalid")
        if not isinstance(item.get("material"), bool):
            errors.append("visual_table_source_region_materiality_invalid")
        if _SOURCE_REGION_EVIDENCE_KEYS <= set(item):
            deterministic_text = item["deterministic_text"]
            if (
                not isinstance(deterministic_text, str)
                or len(deterministic_text) > config.maximum_source_text_chars
            ):
                errors.append("visual_table_source_value_evidence_text_invalid")
            elif (
                item["deterministic_text_sha256"]
                != hashlib.sha256(deterministic_text.encode("utf-8")).hexdigest()
            ):
                errors.append("visual_table_source_value_evidence_hash_mismatch")
            if not _bounded_nonempty_string(
                item["deterministic_extractor_ref"],
                maximum_chars=config.maximum_identifier_chars,
            ):
                errors.append("visual_table_source_value_evidence_origin_invalid")
    if not inventory:
        errors.append("visual_table_source_region_inventory_empty")
    return sorted(set(errors))


class VisualTableProposalValidator:
    def __init__(
        self,
        config: VisualTableContractConfig | None = None,
    ) -> None:
        self.config = config or VisualTableContractConfig()

    def validate(
        self,
        *,
        proposal: dict[str, Any],
        scope: dict[str, Any],
        request_ref: str,
    ) -> VisualTableValidationOutcome:
        """Prove deterministic structure and return one terminal state."""

        proposal_hash = sha256_json(proposal)
        errors: list[str] = []
        review_reasons: list[str] = []
        if proposal.get("request_ref") != request_ref:
            errors.append("visual_table_proposal_request_lineage_mismatch")
        layout = proposal.get("layout_status")
        tables = proposal["detected_table_regions"]
        uncertainties = proposal["uncertainties"]
        if layout == "unsupported":
            if tables or not uncertainties:
                errors.append("visual_table_unsupported_layout_evidence_invalid")
        elif layout == "unresolved":
            if tables or not uncertainties:
                errors.append("visual_table_unresolved_scope_evidence_invalid")
        elif not tables:
            errors.append("visual_table_supported_layout_has_no_tables")

        inventory = {
            item["source_region_ref"]: item for item in scope["source_region_inventory"]
        }
        refs: set[str] = set(inventory)
        all_subject_refs: set[str] = set(refs)
        cell_owners: dict[str, str] = {}
        table_boxes: list[list[float]] = []
        total_cells = 0
        for table in tables:
            table_ref = table["table_ref"]
            if table_ref in all_subject_refs:
                errors.append("visual_table_proposal_identity_duplicate")
            bbox = _normalized_bbox(table["normalized_bbox"])
            if bbox is None:
                errors.append("visual_table_region_bbox_invalid")
                continue
            if any(_bbox_overlaps(bbox, prior) for prior in table_boxes):
                errors.append("visual_table_detected_regions_overlap")
            table_boxes.append(bbox)
            table_errors, table_reviews, table_refs, owners = self._validate_table(
                table,
                page_number=scope["page_number"],
                inventory=inventory,
            )
            errors.extend(table_errors)
            review_reasons.extend(table_reviews)
            table_refs.add(table_ref)
            if table_refs & all_subject_refs:
                errors.append("visual_table_proposal_identity_duplicate")
            all_subject_refs.update(table_refs)
            for source_ref, cell_ref in owners.items():
                if source_ref in cell_owners:
                    errors.append("visual_table_source_region_ownership_duplicate")
                else:
                    cell_owners[source_ref] = cell_ref
            total_cells += len(table["cells"])
        if total_cells > self.config.maximum_cells:
            errors.append("visual_table_cell_budget_exceeded")

        omission_owners: dict[str, str] = {}
        omission_refs: set[str] = set()
        for omission in proposal["omissions"]:
            omission_ref = omission["omission_ref"]
            if omission_ref in omission_refs or omission_ref in all_subject_refs:
                errors.append("visual_table_omission_identity_duplicate")
            omission_refs.add(omission_ref)
            all_subject_refs.add(omission_ref)
            source_refs = omission["source_region_refs"]
            if not source_refs or len(source_refs) != len(set(source_refs)):
                errors.append("visual_table_omission_region_set_invalid")
            materials: list[bool] = []
            for source_ref in source_refs:
                if source_ref not in inventory:
                    errors.append("visual_table_omission_source_region_unknown")
                    continue
                materials.append(bool(inventory[source_ref]["material"]))
                if source_ref in omission_owners:
                    errors.append("visual_table_source_region_ownership_duplicate")
                omission_owners[source_ref] = omission_ref
            expected_material = any(materials)
            if omission["material"] is not expected_material:
                errors.append("visual_table_omission_materiality_mismatch")
            if expected_material:
                review_reasons.append("visual_table_material_omission_requires_review")

        expected_relationships = {
            source_ref: ("cell_value", target)
            for source_ref, target in cell_owners.items()
        }
        expected_relationships.update(
            {
                source_ref: ("omission", target)
                for source_ref, target in omission_owners.items()
            }
        )
        observed_relationships: dict[str, tuple[str, str]] = {}
        for relationship in proposal["source_region_relationships"]:
            source_ref = relationship["source_region_ref"]
            relation = (
                relationship["relationship_type"],
                relationship["target_ref"],
            )
            if source_ref in observed_relationships:
                errors.append("visual_table_source_relationship_duplicate")
            observed_relationships[source_ref] = relation
        if expected_relationships != observed_relationships:
            errors.append("visual_table_source_relationships_incomplete")
        if set(expected_relationships) != refs:
            errors.append("visual_table_source_region_accounting_incomplete")
        if set(cell_owners) & set(omission_owners):
            errors.append("visual_table_source_region_ownership_duplicate")

        uncertainty_refs: set[str] = set()
        for uncertainty in uncertainties:
            uncertainty_ref = uncertainty["uncertainty_ref"]
            if (
                uncertainty_ref in uncertainty_refs
                or uncertainty_ref in all_subject_refs
            ):
                errors.append("visual_table_uncertainty_identity_duplicate")
            uncertainty_refs.add(uncertainty_ref)
            if uncertainty["subject_ref"] not in all_subject_refs:
                errors.append("visual_table_uncertainty_subject_unknown")
            review_reasons.append("visual_table_uncertainty_requires_review")

        if errors:
            return self._outcome("proposal_rejected", errors, proposal, proposal_hash)
        if layout == "unsupported":
            return self._outcome(
                "unsupported_visual_layout",
                ["visual_table_layout_unsupported"],
                proposal,
                proposal_hash,
            )
        if layout == "unresolved":
            return self._outcome(
                "unresolved_visual_scope",
                ["visual_table_scope_unresolved"],
                proposal,
                proposal_hash,
            )
        # The current scaffold has no server-authenticated evidence origin.
        # Caller-supplied text plus its caller-supplied hash may strengthen
        # deterministic comparison, but can never authorize acceptance.
        review_reasons.append("visual_table_evidence_origin_not_server_authenticated")
        if review_reasons:
            return self._outcome(
                "proposal_requires_review",
                review_reasons,
                proposal,
                proposal_hash,
            )
        raise AssertionError("visual_table_unreachable_acceptance_state")

    def _validate_table(
        self,
        table: dict[str, Any],
        *,
        page_number: int,
        inventory: dict[str, dict[str, Any]],
    ) -> tuple[list[str], list[str], set[str], dict[str, str]]:
        errors: list[str] = []
        reviews: list[str] = []
        subject_refs: set[str] = set()
        owners: dict[str, str] = {}
        table_bbox = _normalized_bbox(table["normalized_bbox"])
        rows = table["ordered_rows"]
        columns = table["ordered_columns"]
        row_refs = [row["row_ref"] for row in rows]
        column_refs = [column["column_ref"] for column in columns]
        local_identity_sequence = [table["table_ref"], *row_refs, *column_refs]
        if len(local_identity_sequence) != len(set(local_identity_sequence)):
            errors.append("visual_table_proposal_identity_duplicate")
        subject_refs.add(table["table_ref"])
        subject_refs.update(row_refs)
        subject_refs.update(column_refs)
        if (
            len(rows) > self.config.maximum_rows_per_table
            or [row["order"] for row in rows] != list(range(len(rows)))
            or len(row_refs) != len(set(row_refs))
        ):
            errors.append("visual_table_row_order_invalid")
        if (
            len(columns) > self.config.maximum_columns_per_table
            or [column["order"] for column in columns] != list(range(len(columns)))
            or len(column_refs) != len(set(column_refs))
        ):
            errors.append("visual_table_column_order_invalid")
        row_index = {ref: index for index, ref in enumerate(row_refs)}
        column_index = {ref: index for index, ref in enumerate(column_refs)}
        header_row_indexes = [
            index
            for index, row in enumerate(rows)
            if row["structural_role"] == "header"
        ]
        if header_row_indexes != list(range(len(header_row_indexes))):
            errors.append("visual_table_header_rows_not_ordered_prefix")
        if not header_row_indexes:
            reviews.append("visual_table_header_association_requires_review")

        cells = table["cells"]
        cells_by_ref: dict[str, dict[str, Any]] = {}
        coverage: dict[tuple[int, int], str] = {}
        cell_boxes: dict[str, list[float]] = {}
        source_ref_seen_in_table: set[str] = set()
        for cell in cells:
            cell_ref = cell["cell_ref"]
            if cell_ref in subject_refs:
                errors.append("visual_table_cell_identity_duplicate")
                if cell_ref in cells_by_ref:
                    continue
            cells_by_ref[cell_ref] = cell
            subject_refs.add(cell_ref)
            row = row_index.get(cell["row_ref"])
            column = column_index.get(cell["column_ref"])
            row_span = cell["row_span"]
            column_span = cell["column_span"]
            if (
                row is None
                or column is None
                or row + row_span > len(rows)
                or column + column_span > len(columns)
            ):
                errors.append("visual_table_cell_span_invalid")
                continue
            for row_slot in range(row, row + row_span):
                for column_slot in range(column, column + column_span):
                    slot = (row_slot, column_slot)
                    if slot in coverage:
                        errors.append("visual_table_cell_slot_owned_twice")
                    coverage[slot] = cell_ref
            cell_bbox = _normalized_bbox(cell["normalized_bbox"])
            if (
                table_bbox is None
                or cell_bbox is None
                or not _bbox_contains(table_bbox, cell_bbox)
            ):
                errors.append("visual_table_cell_bbox_outside_table")
            elif any(_bbox_overlaps(cell_bbox, prior) for prior in cell_boxes.values()):
                errors.append("visual_table_cell_regions_overlap")
            else:
                cell_boxes[cell_ref] = cell_bbox
            source_refs = cell["source_region_refs"]
            if len(source_refs) != len(set(source_refs)):
                errors.append("visual_table_cell_source_region_duplicate")
            state = cell["content_state"]
            text = cell["source_text"]
            if state == "present" and (not text or not source_refs):
                errors.append("visual_table_present_cell_evidence_missing")
            elif state == "present":
                if len(source_refs) != 1:
                    reviews.append("visual_table_source_value_evidence_required")
                else:
                    source_evidence = inventory.get(source_refs[0], {})
                    deterministic_text = source_evidence.get("deterministic_text")
                    if deterministic_text is None:
                        reviews.append("visual_table_source_value_evidence_required")
                    elif deterministic_text != text:
                        errors.append("visual_table_source_value_evidence_mismatch")
            if state == "empty" and (text or source_refs):
                errors.append("visual_table_empty_cell_contract_invalid")
            elif state == "empty":
                reviews.append("visual_table_empty_cell_requires_review")
            if state == "unreadable":
                if text:
                    errors.append("visual_table_unreadable_cell_text_forbidden")
                reviews.append("visual_table_unreadable_cell_requires_review")
            for source_ref in source_refs:
                source = inventory.get(source_ref)
                if source is None:
                    errors.append("visual_table_cell_source_region_unknown")
                    continue
                if source_ref in source_ref_seen_in_table:
                    errors.append("visual_table_source_region_ownership_duplicate")
                source_ref_seen_in_table.add(source_ref)
                source_bbox = _normalized_bbox(source["normalized_bbox"])
                if (
                    cell_bbox is None
                    or source_bbox is None
                    or not _bbox_contains(cell_bbox, source_bbox)
                ):
                    errors.append("visual_table_source_region_cell_binding_invalid")
                owners[source_ref] = cell_ref
        if set(coverage) != {
            (row, column) for row in range(len(rows)) for column in range(len(columns))
        }:
            errors.append("visual_table_grid_accounting_incomplete")
        errors.extend(
            _validate_grid_geometry_order(
                coverage,
                cell_boxes=cell_boxes,
                rows_total=len(rows),
                columns_total=len(columns),
            )
        )

        errors.extend(
            self._validate_spans(
                table["spanning_cells"],
                cells_by_ref=cells_by_ref,
                row_refs=row_refs,
                column_refs=column_refs,
                row_index=row_index,
                column_index=column_index,
            )
        )
        errors.extend(
            self._validate_headers(
                table["headers"],
                cells_by_ref=cells_by_ref,
                rows=rows,
                row_index=row_index,
                column_refs=column_refs,
                column_index=column_index,
            )
        )
        errors.extend(
            self._validate_totals(
                table["totals"],
                cells_by_ref=cells_by_ref,
                rows=rows,
            )
        )
        continuation_errors, continuation_reviews = self._validate_continuation(
            table["continuation_evidence"],
            page_number=page_number,
            cell_refs=set(cells_by_ref),
        )
        errors.extend(continuation_errors)
        reviews.extend(continuation_reviews)
        return errors, reviews, subject_refs, owners

    @staticmethod
    def _validate_spans(
        spans: list[dict[str, Any]],
        *,
        cells_by_ref: dict[str, dict[str, Any]],
        row_refs: list[str],
        column_refs: list[str],
        row_index: dict[str, int],
        column_index: dict[str, int],
    ) -> list[str]:
        errors: list[str] = []
        span_by_ref: dict[str, dict[str, Any]] = {}
        for span in spans:
            cell_ref = span["cell_ref"]
            if cell_ref in span_by_ref:
                errors.append("visual_table_span_identity_duplicate")
            span_by_ref[cell_ref] = span
        expected_refs = {
            ref
            for ref, cell in cells_by_ref.items()
            if cell["row_span"] > 1 or cell["column_span"] > 1
        }
        if set(span_by_ref) != expected_refs:
            errors.append("visual_table_spanning_cell_accounting_incomplete")
        for cell_ref, span in span_by_ref.items():
            cell = cells_by_ref.get(cell_ref)
            if cell is None:
                errors.append("visual_table_span_cell_unknown")
                continue
            row = row_index.get(cell["row_ref"])
            column = column_index.get(cell["column_ref"])
            if row is None or column is None:
                continue
            expected_rows = row_refs[row : row + cell["row_span"]]
            expected_columns = column_refs[column : column + cell["column_span"]]
            if (
                span["row_span"] != cell["row_span"]
                or span["column_span"] != cell["column_span"]
                or span["covered_row_refs"] != expected_rows
                or span["covered_column_refs"] != expected_columns
            ):
                errors.append("visual_table_span_relationship_invalid")
        return errors

    @staticmethod
    def _validate_headers(
        headers: list[dict[str, Any]],
        *,
        cells_by_ref: dict[str, dict[str, Any]],
        rows: list[dict[str, Any]],
        row_index: dict[str, int],
        column_refs: list[str],
        column_index: dict[str, int],
    ) -> list[str]:
        errors: list[str] = []
        header_by_ref: dict[str, dict[str, Any]] = {}
        expected_header_cells: set[str] = set()
        for ref, cell in cells_by_ref.items():
            row_position = row_index.get(cell["row_ref"])
            if row_position is None:
                continue
            if rows[row_position]["structural_role"] == "header":
                expected_header_cells.add(ref)
                header_rows_total = sum(
                    row["structural_role"] == "header" for row in rows
                )
                if row_position + cell["row_span"] > header_rows_total:
                    errors.append("visual_table_header_span_crosses_body")
        for header in headers:
            header_ref = header["header_cell_ref"]
            if header_ref in header_by_ref:
                errors.append("visual_table_header_identity_duplicate")
            header_by_ref[header_ref] = header
        if set(header_by_ref) != expected_header_cells:
            errors.append("visual_table_header_accounting_incomplete")
        associated_cells: set[str] = set()
        for header_ref, header in header_by_ref.items():
            cell = cells_by_ref.get(header_ref)
            if cell is None:
                errors.append("visual_table_header_cell_unknown")
                continue
            start_column = column_index.get(cell["column_ref"])
            if start_column is None:
                errors.append("visual_table_header_column_unknown")
                continue
            expected_columns = column_refs[
                start_column : start_column + cell["column_span"]
            ]
            applies_columns = header["applies_to_column_refs"]
            applies_cells = header["applies_to_cell_refs"]
            if not applies_columns or set(applies_columns) != set(expected_columns):
                errors.append("visual_table_header_column_association_invalid")
            if len(applies_cells) != len(set(applies_cells)):
                errors.append("visual_table_header_cell_association_duplicate")
            for target_ref in applies_cells:
                target = cells_by_ref.get(target_ref)
                if target is None or target_ref in expected_header_cells:
                    errors.append("visual_table_header_target_invalid")
                    continue
                target_column = column_index.get(target["column_ref"])
                if target_column is None:
                    errors.append("visual_table_header_target_column_mismatch")
                    continue
                target_columns = set(
                    column_refs[target_column : target_column + target["column_span"]]
                )
                if not target_columns & set(applies_columns):
                    errors.append("visual_table_header_target_column_mismatch")
                associated_cells.add(target_ref)
            parent = header["parent_header_cell_ref"]
            if parent:
                parent_cell = cells_by_ref.get(parent)
                if (
                    parent not in header_by_ref
                    or parent_cell is None
                    or row_index.get(parent_cell["row_ref"], len(rows))
                    >= row_index.get(cell["row_ref"], -1)
                ):
                    errors.append("visual_table_header_parent_invalid")
        expected_body_cells = set(cells_by_ref) - expected_header_cells
        if expected_header_cells and associated_cells != expected_body_cells:
            errors.append("visual_table_header_association_incomplete")
        return errors

    @staticmethod
    def _validate_totals(
        totals: list[dict[str, Any]],
        *,
        cells_by_ref: dict[str, dict[str, Any]],
        rows: list[dict[str, Any]],
    ) -> list[str]:
        errors: list[str] = []
        expected_rows = {
            row["row_ref"]: row["structural_role"]
            for row in rows
            if row["structural_role"] in {"subtotal", "total"}
        }
        total_by_row: dict[str, dict[str, Any]] = {}
        for total in totals:
            row_ref = total["row_ref"]
            if row_ref in total_by_row:
                errors.append("visual_table_total_identity_duplicate")
            total_by_row[row_ref] = total
        if set(total_by_row) != set(expected_rows):
            errors.append("visual_table_total_accounting_incomplete")
        for row_ref, total in total_by_row.items():
            row_cells = {
                ref
                for ref, cell in cells_by_ref.items()
                if cell["row_ref"] == row_ref and cell["content_state"] == "present"
            }
            labels = total["label_cell_refs"]
            values = total["value_cell_refs"]
            if (
                total["structural_role"] != expected_rows.get(row_ref)
                or not labels
                or not values
                or set(labels) & set(values)
                or set(labels) | set(values) != row_cells
            ):
                errors.append("visual_table_total_relationship_invalid")
                continue
            label_text = " ".join(
                cells_by_ref[ref]["source_text"]
                for ref in labels
                if ref in cells_by_ref
            ).strip()
            if not _TOTAL_LABEL.search(label_text):
                errors.append("visual_table_total_label_evidence_missing")
        return errors

    @staticmethod
    def _validate_continuation(
        continuation: dict[str, Any],
        *,
        page_number: int,
        cell_refs: set[str],
    ) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        reviews: list[str] = []
        state = continuation["state"]
        evidence = continuation["evidence_cell_refs"]
        pages = continuation["adjacent_page_numbers"]
        if len(evidence) != len(set(evidence)) or not set(evidence) <= cell_refs:
            errors.append("visual_table_continuation_evidence_invalid")
        expected_pages: list[int]
        if state == "none":
            expected_pages = []
            if evidence:
                errors.append("visual_table_continuation_none_has_evidence")
        elif state == "continues_from_previous":
            expected_pages = [page_number - 1]
        elif state == "continues_to_next":
            expected_pages = [page_number + 1]
        elif state == "bidirectional":
            expected_pages = [page_number - 1, page_number + 1]
        else:
            expected_pages = []
        if state != "none":
            reviews.append("visual_table_continuation_requires_review")
        if pages != expected_pages:
            errors.append("visual_table_continuation_page_lineage_invalid")
        if state not in {"none", "unresolved"} and not evidence:
            errors.append("visual_table_continuation_evidence_missing")
        if any(page <= 0 for page in pages):
            errors.append("visual_table_continuation_page_lineage_invalid")
        return errors, reviews

    @staticmethod
    def _outcome(
        terminal_result: str,
        reason_codes: list[str],
        proposal: dict[str, Any],
        proposal_hash: str,
    ) -> VisualTableValidationOutcome:
        if terminal_result not in VISUAL_TABLE_TERMINAL_RESULTS:
            raise AssertionError("visual_table_terminal_result_internal_invalid")
        return VisualTableValidationOutcome(
            terminal_result=terminal_result,
            reason_codes=tuple(sorted(set(reason_codes))),
            proposal=(
                None
                if terminal_result == "proposal_rejected"
                else copy.deepcopy(proposal)
            ),
            proposal_sha256=proposal_hash,
        )


def _validate_proposal_shape(
    value: Any,
    *,
    config: VisualTableContractConfig,
) -> None:
    _exact_dict(value, _PROPOSAL_KEYS, "visual_table_proposal_shape_invalid")
    if value["schema_version"] != VISUAL_TABLE_PROPOSAL_SCHEMA_VERSION:
        raise VisualTableContractError("visual_table_proposal_schema_invalid")
    _required_string(
        value["request_ref"],
        "visual_table_request_ref_invalid",
        maximum_chars=config.maximum_identifier_chars,
    )
    if value["layout_status"] not in _LAYOUT_STATES:
        raise VisualTableContractError("visual_table_layout_status_invalid")
    tables = _dict_list(
        value["detected_table_regions"], "visual_table_regions_shape_invalid"
    )
    if len(tables) > config.maximum_tables:
        raise VisualTableContractError("visual_table_region_budget_exceeded")
    total_cells = 0
    for table in tables:
        _exact_dict(table, _TABLE_KEYS, "visual_table_region_shape_invalid")
        _required_string(
            table["table_ref"],
            "visual_table_ref_invalid",
            maximum_chars=config.maximum_identifier_chars,
        )
        _require_bbox_shape(table["normalized_bbox"])
        rows = _dict_list(table["ordered_rows"], "visual_table_rows_shape_invalid")
        columns = _dict_list(
            table["ordered_columns"], "visual_table_columns_shape_invalid"
        )
        cells = _dict_list(table["cells"], "visual_table_cells_shape_invalid")
        if not rows or len(rows) > config.maximum_rows_per_table:
            raise VisualTableContractError("visual_table_rows_shape_invalid")
        if not columns or len(columns) > config.maximum_columns_per_table:
            raise VisualTableContractError("visual_table_columns_shape_invalid")
        total_cells += len(cells)
        if not cells or total_cells > config.maximum_cells:
            raise VisualTableContractError("visual_table_cell_budget_exceeded")
        for row in rows:
            _exact_dict(row, _ROW_KEYS, "visual_table_row_shape_invalid")
            _required_string(
                row["row_ref"],
                "visual_table_row_ref_invalid",
                maximum_chars=config.maximum_identifier_chars,
            )
            _nonnegative_integer(row["order"], "visual_table_row_order_type_invalid")
            if row["structural_role"] not in _ROW_ROLES:
                raise VisualTableContractError("visual_table_row_role_invalid")
        for column in columns:
            _exact_dict(column, _COLUMN_KEYS, "visual_table_column_shape_invalid")
            _required_string(
                column["column_ref"],
                "visual_table_column_ref_invalid",
                maximum_chars=config.maximum_identifier_chars,
            )
            _nonnegative_integer(
                column["order"], "visual_table_column_order_type_invalid"
            )
        for cell in cells:
            _exact_dict(cell, _CELL_KEYS, "visual_table_cell_shape_invalid")
            for field in ("cell_ref", "row_ref", "column_ref"):
                _required_string(
                    cell[field],
                    "visual_table_cell_identity_invalid",
                    maximum_chars=config.maximum_identifier_chars,
                )
            _positive_integer(cell["row_span"], "visual_table_cell_span_type_invalid")
            _positive_integer(
                cell["column_span"], "visual_table_cell_span_type_invalid"
            )
            if cell["content_state"] not in _CONTENT_STATES:
                raise VisualTableContractError(
                    "visual_table_cell_content_state_invalid"
                )
            if (
                not isinstance(cell["source_text"], str)
                or len(cell["source_text"]) > config.maximum_source_text_chars
            ):
                raise VisualTableContractError("visual_table_cell_text_type_invalid")
            _require_bbox_shape(cell["normalized_bbox"])
            _string_list(
                cell["source_region_refs"],
                "visual_table_cell_refs_invalid",
                maximum_items=config.maximum_refs_per_item,
                maximum_chars=config.maximum_identifier_chars,
            )
        headers = _dict_list(table["headers"], "visual_table_headers_shape_invalid")
        if len(headers) > config.maximum_cells:
            raise VisualTableContractError("visual_table_headers_shape_invalid")
        for header in headers:
            _exact_dict(header, _HEADER_KEYS, "visual_table_header_shape_invalid")
            _required_string(
                header["header_cell_ref"],
                "visual_table_header_ref_invalid",
                maximum_chars=config.maximum_identifier_chars,
            )
            if (
                not isinstance(header["parent_header_cell_ref"], str)
                or len(header["parent_header_cell_ref"])
                > config.maximum_identifier_chars
            ):
                raise VisualTableContractError(
                    "visual_table_header_parent_type_invalid"
                )
            _string_list(
                header["applies_to_column_refs"],
                "visual_table_header_columns_invalid",
                maximum_items=config.maximum_columns_per_table,
                maximum_chars=config.maximum_identifier_chars,
            )
            _string_list(
                header["applies_to_cell_refs"],
                "visual_table_header_cells_invalid",
                maximum_items=config.maximum_cells,
                maximum_chars=config.maximum_identifier_chars,
            )
        spans = _dict_list(table["spanning_cells"], "visual_table_spans_shape_invalid")
        if len(spans) > config.maximum_cells:
            raise VisualTableContractError("visual_table_spans_shape_invalid")
        for span in spans:
            _exact_dict(span, _SPAN_KEYS, "visual_table_span_shape_invalid")
            _required_string(
                span["cell_ref"],
                "visual_table_span_ref_invalid",
                maximum_chars=config.maximum_identifier_chars,
            )
            _positive_integer(span["row_span"], "visual_table_span_value_invalid")
            _positive_integer(span["column_span"], "visual_table_span_value_invalid")
            _string_list(
                span["covered_row_refs"],
                "visual_table_span_rows_invalid",
                maximum_items=config.maximum_rows_per_table,
                maximum_chars=config.maximum_identifier_chars,
            )
            _string_list(
                span["covered_column_refs"],
                "visual_table_span_columns_invalid",
                maximum_items=config.maximum_columns_per_table,
                maximum_chars=config.maximum_identifier_chars,
            )
        totals = _dict_list(table["totals"], "visual_table_totals_shape_invalid")
        if len(totals) > config.maximum_rows_per_table:
            raise VisualTableContractError("visual_table_totals_shape_invalid")
        for total in totals:
            _exact_dict(total, _TOTAL_KEYS, "visual_table_total_shape_invalid")
            _required_string(
                total["row_ref"],
                "visual_table_total_row_invalid",
                maximum_chars=config.maximum_identifier_chars,
            )
            if total["structural_role"] not in {"subtotal", "total"}:
                raise VisualTableContractError("visual_table_total_role_invalid")
            _string_list(
                total["label_cell_refs"],
                "visual_table_total_labels_invalid",
                maximum_items=config.maximum_cells,
                maximum_chars=config.maximum_identifier_chars,
            )
            _string_list(
                total["value_cell_refs"],
                "visual_table_total_values_invalid",
                maximum_items=config.maximum_cells,
                maximum_chars=config.maximum_identifier_chars,
            )
        continuation = table["continuation_evidence"]
        _exact_dict(
            continuation,
            _CONTINUATION_KEYS,
            "visual_table_continuation_shape_invalid",
        )
        if continuation["state"] not in _CONTINUATION_STATES:
            raise VisualTableContractError("visual_table_continuation_state_invalid")
        _string_list(
            continuation["evidence_cell_refs"],
            "visual_table_continuation_cells_invalid",
            maximum_items=config.maximum_cells,
            maximum_chars=config.maximum_identifier_chars,
        )
        if len(continuation["adjacent_page_numbers"]) > 2:
            raise VisualTableContractError("visual_table_continuation_pages_invalid")
        _positive_integer_list(
            continuation["adjacent_page_numbers"],
            "visual_table_continuation_pages_invalid",
        )
    relationships = _dict_list(
        value["source_region_relationships"],
        "visual_table_relationships_shape_invalid",
    )
    if len(relationships) > config.maximum_source_regions:
        raise VisualTableContractError("visual_table_relationships_shape_invalid")
    for relationship in relationships:
        _exact_dict(
            relationship,
            _RELATIONSHIP_KEYS,
            "visual_table_relationship_shape_invalid",
        )
        _required_string(
            relationship["source_region_ref"],
            "visual_table_relationship_source_invalid",
            maximum_chars=config.maximum_identifier_chars,
        )
        if relationship["relationship_type"] not in _RELATIONSHIP_TYPES:
            raise VisualTableContractError("visual_table_relationship_type_invalid")
        _required_string(
            relationship["target_ref"],
            "visual_table_relationship_target_invalid",
            maximum_chars=config.maximum_identifier_chars,
        )
    uncertainties = _dict_list(
        value["uncertainties"], "visual_table_uncertainties_shape_invalid"
    )
    if len(uncertainties) > config.maximum_annotations:
        raise VisualTableContractError("visual_table_uncertainties_shape_invalid")
    for uncertainty in uncertainties:
        _exact_dict(
            uncertainty,
            _UNCERTAINTY_KEYS,
            "visual_table_uncertainty_shape_invalid",
        )
        _required_string(
            uncertainty["uncertainty_ref"],
            "visual_table_uncertainty_ref_invalid",
            maximum_chars=config.maximum_identifier_chars,
        )
        _required_string(
            uncertainty["subject_ref"],
            "visual_table_uncertainty_subject_invalid",
            maximum_chars=config.maximum_identifier_chars,
        )
        _require_code(uncertainty["code"], "visual_table_uncertainty_code_invalid")
        if not isinstance(uncertainty["material"], bool):
            raise VisualTableContractError(
                "visual_table_uncertainty_materiality_invalid"
            )
    omissions = _dict_list(value["omissions"], "visual_table_omissions_shape_invalid")
    if len(omissions) > config.maximum_annotations:
        raise VisualTableContractError("visual_table_omissions_shape_invalid")
    for omission in omissions:
        _exact_dict(omission, _OMISSION_KEYS, "visual_table_omission_shape_invalid")
        _required_string(
            omission["omission_ref"],
            "visual_table_omission_ref_invalid",
            maximum_chars=config.maximum_identifier_chars,
        )
        _string_list(
            omission["source_region_refs"],
            "visual_table_omission_regions_invalid",
            maximum_items=config.maximum_refs_per_item,
            maximum_chars=config.maximum_identifier_chars,
        )
        _require_code(omission["reason_code"], "visual_table_omission_reason_invalid")
        if not isinstance(omission["material"], bool):
            raise VisualTableContractError("visual_table_omission_materiality_invalid")


def _schema_object(properties: dict[str, Any], required: set[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": sorted(required),
    }


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"JSON constant is forbidden: {value}")


def _exact_dict(value: Any, keys: set[str], code: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise VisualTableContractError(code)


def _dict_list(value: Any, code: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise VisualTableContractError(code)
    return value


def _string_list(
    value: Any,
    code: str,
    *,
    maximum_items: int | None = None,
    maximum_chars: int | None = None,
) -> list[str]:
    if (
        not isinstance(value, list)
        or (maximum_items is not None and len(value) > maximum_items)
        or any(
            not isinstance(item, str)
            or (maximum_chars is not None and len(item) > maximum_chars)
            for item in value
        )
    ):
        raise VisualTableContractError(code)
    return value


def _positive_integer_list(value: Any, code: str) -> list[int]:
    if not isinstance(value, list) or any(not _positive_int(item) for item in value):
        raise VisualTableContractError(code)
    return value


def _required_string(value: Any, code: str, *, maximum_chars: int | None = None) -> str:
    if not _nonempty_string(value) or (
        maximum_chars is not None and len(value) > maximum_chars
    ):
        raise VisualTableContractError(code)
    return value


def _require_code(value: Any, code: str) -> str:
    if not isinstance(value, str) or not _CODE.fullmatch(value):
        raise VisualTableContractError(code)
    return value


def _positive_integer(value: Any, code: str) -> int:
    if not _positive_int(value):
        raise VisualTableContractError(code)
    return value


def _nonnegative_integer(value: Any, code: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise VisualTableContractError(code)
    return value


def _require_bbox_shape(value: Any) -> None:
    if _normalized_bbox(value) is None:
        raise VisualTableContractError("visual_table_normalized_bbox_invalid")


def _normalized_bbox(value: Any) -> list[float] | None:
    if (
        not isinstance(value, list)
        or len(value) != 4
        or any(
            not isinstance(item, (int, float))
            or isinstance(item, bool)
            or not 0.0 <= float(item) <= 1.0
            for item in value
        )
    ):
        return None
    result = [float(item) for item in value]
    if result[0] >= result[2] or result[1] >= result[3]:
        return None
    return result


def _integer_bbox(value: Any) -> list[int] | None:
    if (
        not isinstance(value, list)
        or len(value) != 4
        or any(not isinstance(item, int) or isinstance(item, bool) for item in value)
    ):
        return None
    if value[0] < 0 or value[1] < 0 or value[0] >= value[2] or value[1] >= value[3]:
        return None
    return list(value)


def _integer_pair(value: Any) -> list[int] | None:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(not _positive_int(item) for item in value)
    ):
        return None
    return list(value)


def _bbox_within_pixel_extent(bbox: list[int], *, width: int, height: int) -> bool:
    return bbox[0] >= 0 and bbox[1] >= 0 and bbox[2] <= width and bbox[3] <= height


def _bbox_contains(outer: list[float], inner: list[float]) -> bool:
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and outer[2] >= inner[2]
        and outer[3] >= inner[3]
    )


def _bbox_overlaps(left: list[float], right: list[float]) -> bool:
    return not (
        left[2] <= right[0]
        or right[2] <= left[0]
        or left[3] <= right[1]
        or right[3] <= left[1]
    )


def _validate_grid_geometry_order(
    coverage: dict[tuple[int, int], str],
    *,
    cell_boxes: dict[str, list[float]],
    rows_total: int,
    columns_total: int,
) -> list[str]:
    errors: list[str] = []
    for row in range(rows_total):
        for column in range(columns_total - 1):
            left_ref = coverage.get((row, column))
            right_ref = coverage.get((row, column + 1))
            if left_ref == right_ref:
                continue
            left = cell_boxes.get(str(left_ref))
            right = cell_boxes.get(str(right_ref))
            if (
                left is not None
                and right is not None
                and ((left[0] + left[2]) / 2 >= (right[0] + right[2]) / 2)
            ):
                errors.append("visual_table_column_geometry_order_invalid")
    for row in range(rows_total - 1):
        for column in range(columns_total):
            upper_ref = coverage.get((row, column))
            lower_ref = coverage.get((row + 1, column))
            if upper_ref == lower_ref:
                continue
            upper = cell_boxes.get(str(upper_ref))
            lower = cell_boxes.get(str(lower_ref))
            if (
                upper is not None
                and lower is not None
                and ((upper[1] + upper[3]) / 2 >= (lower[1] + lower[3]) / 2)
            ):
                errors.append("visual_table_row_geometry_order_invalid")
    return sorted(set(errors))


def _decode_raster_dimensions(
    image_bytes: bytes,
    *,
    mime_type: str,
    config: VisualTableContractConfig,
) -> tuple[list[int] | None, str | None]:
    """Fully decode one bounded raster before any provider call.

    Pillow is an explicit dependency of the pinned OpenWebUI runtime image.  A
    header probe is insufficient: truncated PNG/JPEG payloads can carry valid
    dimensions while failing only when the compressed pixel stream is decoded.
    """

    expected_format = {"image/png": "PNG", "image/jpeg": "JPEG"}[mime_type]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(image_bytes)) as raster:
                if raster.format != expected_format:
                    return None, "visual_table_scope_image_encoding_invalid"
                width, height = raster.size
                if (
                    width <= 0
                    or height <= 0
                    or max(width, height) > config.maximum_image_dimension
                    or width * height > config.maximum_image_pixels
                ):
                    return None, "visual_table_scope_image_pixel_budget_exceeded"
                raster.verify()
            with Image.open(BytesIO(image_bytes)) as raster:
                if raster.format != expected_format or raster.size != (width, height):
                    return None, "visual_table_scope_image_encoding_invalid"
                raster.load()
                if raster.size != (width, height):
                    return None, "visual_table_scope_image_encoding_invalid"
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
    ):
        return None, "visual_table_scope_image_encoding_invalid"
    return [width, height], None


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _bounded_nonempty_string(value: Any, *, maximum_chars: int) -> bool:
    return _nonempty_string(value) and len(value) <= maximum_chars
