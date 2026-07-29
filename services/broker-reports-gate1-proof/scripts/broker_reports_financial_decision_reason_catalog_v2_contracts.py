from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any


CATALOG_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_decision_reason_catalog_v2"
)
CATALOG_ID = "broker_reports_gate2_financial_decision_reason_catalog"
CATALOG_SEMANTIC_VERSION = "2.0.0"
MANAGED_ASSET_FAMILY_ID = "broker_reports_gate2_financial_domain_assets"
CATALOG_AUTHORITY_STATUS = "future_v2_1_candidate_not_live"
CATALOG_LIFECYCLE_STATUS = "draft"
CATALOG_LOCALE = "en"
CATALOG_DISPOSITION = "unclassified_financial_input"
RESPONSE_PROFILE_STATUS = "not_implemented"
FAMILY_PACKAGING_STATUS = "not_packaged_until_goal7"
PREDECESSOR_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_decision_reason_catalog_v1"
)
PREDECESSOR_SEMANTIC_VERSION = "1.0.0"
PREDECESSOR_SEMANTIC_INTEGRITY_SHA256 = (
    "d7290593410cafd6b35281ed3a6159802f0d7e87b7a085f3ec2cd2b46f4a3e15"
)
ADDED_REASON_CODE = "single_registry_type_no_safe_record"
SELECTION_DIMENSIONS = (
    "plausible_distinct_available_financial_type_count",
    "uniquely_safe_prebound_choice_count",
)
FACTORY_REQUIRED = (
    "Gate2FinancialDecisionReasonCatalogV2ContractFactory.create is the only "
    "inactive catalog-v2 candidate validation entrypoint"
)
FORBIDDEN = (
    "The catalog-v2 validator must not own human reason wording, activate a "
    "Choice profile, change the historical catalog/family, inspect benchmark "
    "literals, or access providers and runtime"
)

_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "catalog_id",
        "semantic_version",
        "predecessor",
        "managed_asset_family_id",
        "authority_status",
        "runtime_activation",
        "response_profile_status",
        "family_packaging_status",
        "lifecycle",
        "locale",
        "applies_to_disposition",
        "selection_dimensions",
        "gui",
        "reasons",
        "integrity_sha256",
    }
)
_PREDECESSOR_FIELDS = frozenset(
    {
        "schema_version",
        "semantic_version",
        "semantic_integrity_sha256",
    }
)
_LIFECYCLE_FIELDS = frozenset(
    {
        "status",
        "draft_rollback",
        "active_rollback",
    }
)
_GUI_FIELDS = frozenset(
    {
        "collection_title",
        "item_key",
        "item_label",
        "order_field",
        "editable_fields",
        "immutable_fields",
    }
)
_REASON_FIELDS = frozenset(
    {
        "code",
        "display_order",
        "human_title",
        "meaning",
        "use_when",
        "do_not_use_when",
        "positive_example",
        "contrast_with_neighbouring_reasons",
        "selection_boundary",
    }
)
_CONTRAST_FIELDS = frozenset({"reason_code", "distinction"})
_SELECTION_BOUNDARY_FIELDS = frozenset(SELECTION_DIMENSIONS)
_RANGE_FIELDS = frozenset({"minimum_inclusive", "maximum_inclusive"})
_EDITABLE_REASON_FIELDS = (
    "human_title",
    "meaning",
    "use_when",
    "do_not_use_when",
    "positive_example",
    "contrast_with_neighbouring_reasons",
)
_IMMUTABLE_REASON_FIELDS = (
    "code",
    "selection_boundary",
)
_EXPECTED_BOUNDARIES = (
    (0, 0, 0, 0),
    (1, 1, 0, 0),
    (2, "unbounded", 0, 0),
)
_PRESERVED_HUMAN_FIELDS = (
    "human_title",
    "meaning",
    "use_when",
    "do_not_use_when",
    "positive_example",
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class Gate2FinancialDecisionReasonCatalogV2ContractError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2FinancialDecisionReasonCatalogV2Snapshot:
    schema_version: str
    catalog_id: str
    semantic_version: str
    lifecycle_status: str
    runtime_activation: bool
    response_profile_status: str
    family_packaging_status: str
    predecessor_reason_codes: tuple[str, ...]
    reason_codes: tuple[str, ...]
    added_reason_code: str
    integrity_sha256: str
    canonical_semantic_bytes: int

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "catalog_id": self.catalog_id,
            "semantic_version": self.semantic_version,
            "lifecycle_status": self.lifecycle_status,
            "runtime_activation": self.runtime_activation,
            "response_profile_status": self.response_profile_status,
            "family_packaging_status": self.family_packaging_status,
            "predecessor_reason_codes": list(self.predecessor_reason_codes),
            "reason_codes": list(self.reason_codes),
            "added_reason_code": self.added_reason_code,
            "integrity_sha256": self.integrity_sha256,
            "canonical_semantic_bytes": self.canonical_semantic_bytes,
        }


class Gate2FinancialDecisionReasonCatalogV2ContractFactory:
    def __init__(
        self,
        *,
        predecessor_catalog: Any,
        candidate_catalog: Any,
    ) -> None:
        self.predecessor_catalog = _validated_predecessor(predecessor_catalog)
        self.predecessor_reason_codes = tuple(
            item["code"] for item in self.predecessor_catalog["reasons"]
        )
        self.reason_codes = _candidate_reason_codes(candidate_catalog)
        added = set(self.reason_codes) - set(self.predecessor_reason_codes)
        if (
            len(self.reason_codes) != len(self.predecessor_reason_codes) + 1
            or not set(self.predecessor_reason_codes).issubset(self.reason_codes)
            or len(added) != 1
        ):
            _fail("decision_reason_catalog_v2_successor_code_set_invalid")
        self.added_reason_code = next(iter(added))
        if self.added_reason_code != ADDED_REASON_CODE:
            _fail("decision_reason_catalog_v2_added_reason_code_invalid")

    def schema(self) -> dict[str, Any]:
        title = _human_text_schema(
            minimum_length=5,
            maximum_length=120,
            minimum_words=2,
        )
        text = _human_text_schema(
            minimum_length=12,
            maximum_length=800,
            minimum_words=6,
        )
        count_range = _strict_object(
            {
                "minimum_inclusive": {
                    "type": "integer",
                    "minimum": 0,
                },
                "maximum_inclusive": {
                    "oneOf": [
                        {"type": "integer", "minimum": 0},
                        {"const": "unbounded"},
                    ]
                },
            }
        )
        boundary = _strict_object(
            {
                SELECTION_DIMENSIONS[0]: copy.deepcopy(count_range),
                SELECTION_DIMENSIONS[1]: copy.deepcopy(count_range),
            }
        )
        contrast = _strict_object(
            {
                "reason_code": {
                    "type": "string",
                    "enum": list(self.reason_codes),
                },
                "distinction": copy.deepcopy(text),
            }
        )
        reason = _strict_object(
            {
                "code": {
                    "type": "string",
                    "enum": list(self.reason_codes),
                },
                "display_order": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": len(self.reason_codes),
                },
                "human_title": copy.deepcopy(title),
                "meaning": copy.deepcopy(text),
                "use_when": copy.deepcopy(text),
                "do_not_use_when": copy.deepcopy(text),
                "positive_example": copy.deepcopy(text),
                "contrast_with_neighbouring_reasons": {
                    "type": "array",
                    "minItems": len(self.reason_codes) - 1,
                    "maxItems": len(self.reason_codes) - 1,
                    "uniqueItems": True,
                    "items": contrast,
                },
                "selection_boundary": boundary,
            }
        )
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": (
                "urn:broker-reports:gate2:"
                "financial-decision-reason-catalog:v2"
            ),
            "title": (
                "Broker Reports Gate 2 financial decision reason catalog v2"
            ),
            **_strict_object(
                {
                    "schema_version": {"const": CATALOG_SCHEMA_VERSION},
                    "catalog_id": {"const": CATALOG_ID},
                    "semantic_version": {"const": CATALOG_SEMANTIC_VERSION},
                    "predecessor": _strict_object(
                        {
                            "schema_version": {
                                "const": self.predecessor_catalog[
                                    "schema_version"
                                ]
                            },
                            "semantic_version": {
                                "const": self.predecessor_catalog[
                                    "semantic_version"
                                ]
                            },
                            "semantic_integrity_sha256": {
                                "const": self.predecessor_catalog[
                                    "integrity_sha256"
                                ]
                            },
                        }
                    ),
                    "managed_asset_family_id": {
                        "const": MANAGED_ASSET_FAMILY_ID
                    },
                    "authority_status": {
                        "const": CATALOG_AUTHORITY_STATUS
                    },
                    "runtime_activation": {"const": False},
                    "response_profile_status": {
                        "const": RESPONSE_PROFILE_STATUS
                    },
                    "family_packaging_status": {
                        "const": FAMILY_PACKAGING_STATUS
                    },
                    "lifecycle": _strict_object(
                        {
                            "status": {"const": CATALOG_LIFECYCLE_STATUS},
                            "draft_rollback": {
                                "const": "discard_without_runtime_mutation"
                            },
                            "active_rollback": {
                                "const": (
                                    "select_previous_validated_immutable_"
                                    "family_version"
                                )
                            },
                        }
                    ),
                    "locale": {"const": CATALOG_LOCALE},
                    "applies_to_disposition": {
                        "const": CATALOG_DISPOSITION
                    },
                    "selection_dimensions": {
                        "const": list(SELECTION_DIMENSIONS)
                    },
                    "gui": _strict_object(
                        {
                            "collection_title": copy.deepcopy(title),
                            "item_key": {"const": "code"},
                            "item_label": {"const": "human_title"},
                            "order_field": {"const": "display_order"},
                            "editable_fields": {
                                "const": list(_EDITABLE_REASON_FIELDS)
                            },
                            "immutable_fields": {
                                "const": list(_IMMUTABLE_REASON_FIELDS)
                            },
                        }
                    ),
                    "reasons": {
                        "type": "array",
                        "minItems": len(self.reason_codes),
                        "maxItems": len(self.reason_codes),
                        "uniqueItems": True,
                        "items": reason,
                    },
                    "integrity_sha256": {
                        "type": "string",
                        "pattern": "^[0-9a-f]{64}$",
                    },
                }
            ),
        }

    def create(
        self,
        *,
        catalog: Any,
    ) -> Gate2FinancialDecisionReasonCatalogV2Snapshot:
        if not isinstance(catalog, dict) or set(catalog) != _TOP_LEVEL_FIELDS:
            _fail("decision_reason_catalog_v2_projection_invalid")
        if (
            catalog.get("schema_version") != CATALOG_SCHEMA_VERSION
            or catalog.get("catalog_id") != CATALOG_ID
            or catalog.get("semantic_version") != CATALOG_SEMANTIC_VERSION
            or catalog.get("managed_asset_family_id")
            != MANAGED_ASSET_FAMILY_ID
            or catalog.get("authority_status") != CATALOG_AUTHORITY_STATUS
            or catalog.get("runtime_activation") is not False
            or catalog.get("response_profile_status")
            != RESPONSE_PROFILE_STATUS
            or catalog.get("family_packaging_status")
            != FAMILY_PACKAGING_STATUS
            or catalog.get("locale") != CATALOG_LOCALE
            or catalog.get("applies_to_disposition")
            != CATALOG_DISPOSITION
            or catalog.get("selection_dimensions")
            != list(SELECTION_DIMENSIONS)
        ):
            _fail("decision_reason_catalog_v2_identity_invalid")
        self._validate_predecessor(catalog.get("predecessor"))
        self._validate_lifecycle(catalog.get("lifecycle"))
        self._validate_gui(catalog.get("gui"))
        reasons = self._validate_reasons(catalog.get("reasons"))
        material = copy.deepcopy(catalog)
        supplied_integrity = material.pop("integrity_sha256", None)
        canonical = _canonical_json(material)
        calculated_integrity = hashlib.sha256(canonical).hexdigest()
        if (
            not isinstance(supplied_integrity, str)
            or not _SHA256_RE.fullmatch(supplied_integrity)
            or supplied_integrity != calculated_integrity
        ):
            _fail("decision_reason_catalog_v2_integrity_invalid")
        return Gate2FinancialDecisionReasonCatalogV2Snapshot(
            schema_version=CATALOG_SCHEMA_VERSION,
            catalog_id=CATALOG_ID,
            semantic_version=CATALOG_SEMANTIC_VERSION,
            lifecycle_status=CATALOG_LIFECYCLE_STATUS,
            runtime_activation=False,
            response_profile_status=RESPONSE_PROFILE_STATUS,
            family_packaging_status=FAMILY_PACKAGING_STATUS,
            predecessor_reason_codes=self.predecessor_reason_codes,
            reason_codes=self.reason_codes,
            added_reason_code=self.added_reason_code,
            integrity_sha256=calculated_integrity,
            canonical_semantic_bytes=len(canonical),
        )

    def _validate_predecessor(self, value: Any) -> None:
        if not isinstance(value, dict) or set(value) != _PREDECESSOR_FIELDS:
            _fail("decision_reason_catalog_v2_predecessor_invalid")
        if value != {
            "schema_version": self.predecessor_catalog["schema_version"],
            "semantic_version": self.predecessor_catalog["semantic_version"],
            "semantic_integrity_sha256": self.predecessor_catalog[
                "integrity_sha256"
            ],
        }:
            _fail("decision_reason_catalog_v2_predecessor_invalid")

    @staticmethod
    def _validate_lifecycle(value: Any) -> None:
        if not isinstance(value, dict) or set(value) != _LIFECYCLE_FIELDS:
            _fail("decision_reason_catalog_v2_lifecycle_invalid")
        if value != {
            "status": CATALOG_LIFECYCLE_STATUS,
            "draft_rollback": "discard_without_runtime_mutation",
            "active_rollback": (
                "select_previous_validated_immutable_family_version"
            ),
        }:
            _fail("decision_reason_catalog_v2_lifecycle_invalid")

    @staticmethod
    def _validate_gui(value: Any) -> None:
        if not isinstance(value, dict) or set(value) != _GUI_FIELDS:
            _fail("decision_reason_catalog_v2_gui_invalid")
        _human_text(
            value.get("collection_title"),
            "decision_reason_catalog_v2_gui_title_invalid",
            minimum_words=2,
            minimum_characters=5,
            maximum_characters=120,
        )
        if (
            value.get("item_key") != "code"
            or value.get("item_label") != "human_title"
            or value.get("order_field") != "display_order"
            or value.get("editable_fields")
            != list(_EDITABLE_REASON_FIELDS)
            or value.get("immutable_fields")
            != list(_IMMUTABLE_REASON_FIELDS)
        ):
            _fail("decision_reason_catalog_v2_gui_invalid")

    def _validate_reasons(self, value: Any) -> list[dict[str, Any]]:
        if (
            not isinstance(value, list)
            or len(value) != len(self.reason_codes)
            or any(not isinstance(item, dict) for item in value)
        ):
            _fail("decision_reason_catalog_v2_reasons_invalid")
        reasons = copy.deepcopy(value)
        codes = tuple(item.get("code") for item in reasons)
        if (
            codes != self.reason_codes
            or len(codes) != len(set(codes))
        ):
            _fail("decision_reason_catalog_v2_codes_invalid")
        if [item.get("display_order") for item in reasons] != list(
            range(1, len(reasons) + 1)
        ):
            _fail("decision_reason_catalog_v2_display_order_invalid")
        predecessor_by_code = {
            item["code"]: item for item in self.predecessor_catalog["reasons"]
        }
        boundaries: list[tuple[int, int | str, int, int | str]] = []
        all_human_values: list[str] = []
        for reason in reasons:
            if set(reason) != _REASON_FIELDS:
                _fail("decision_reason_catalog_v2_reason_projection_invalid")
            code = _identifier(
                reason.get("code"),
                "decision_reason_catalog_v2_code_invalid",
            )
            for field in _PRESERVED_HUMAN_FIELDS:
                observed = _human_text(
                    reason.get(field),
                    "decision_reason_catalog_v2_human_text_invalid",
                    minimum_words=2 if field == "human_title" else 6,
                    minimum_characters=5 if field == "human_title" else 12,
                    maximum_characters=120 if field == "human_title" else 800,
                )
                all_human_values.append(observed)
                predecessor = predecessor_by_code.get(code)
                if (
                    predecessor is not None
                    and observed != predecessor.get(field)
                ):
                    _fail(
                        "decision_reason_catalog_v2_predecessor_meaning_drift"
                    )
            contrasts = reason.get("contrast_with_neighbouring_reasons")
            expected_neighbours = set(self.reason_codes) - {code}
            if (
                not isinstance(contrasts, list)
                or len(contrasts) != len(expected_neighbours)
            ):
                _fail("decision_reason_catalog_v2_contrasts_invalid")
            observed_neighbours: list[str] = []
            for contrast in contrasts:
                if (
                    not isinstance(contrast, dict)
                    or set(contrast) != _CONTRAST_FIELDS
                ):
                    _fail("decision_reason_catalog_v2_contrast_invalid")
                neighbour = contrast.get("reason_code")
                if neighbour == code:
                    _fail(
                        "decision_reason_catalog_v2_self_contrast_forbidden"
                    )
                observed_neighbours.append(neighbour)
                all_human_values.append(
                    _human_text(
                        contrast.get("distinction"),
                        "decision_reason_catalog_v2_distinction_invalid",
                    )
                )
            if (
                len(observed_neighbours) != len(set(observed_neighbours))
                or set(observed_neighbours) != expected_neighbours
            ):
                _fail("decision_reason_catalog_v2_contrasts_incomplete")
            boundaries.append(_boundary_tuple(reason.get("selection_boundary")))
        if tuple(boundaries) != _EXPECTED_BOUNDARIES:
            _fail("decision_reason_catalog_v2_boundaries_invalid")
        normalized = [item.casefold() for item in all_human_values]
        if len(normalized) != len(set(normalized)):
            _fail("decision_reason_catalog_v2_human_text_not_distinct")
        return reasons


def _validated_predecessor(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or value.get("schema_version")
        != PREDECESSOR_SCHEMA_VERSION
        or value.get("catalog_id") != CATALOG_ID
        or value.get("semantic_version") != PREDECESSOR_SEMANTIC_VERSION
        or value.get("runtime_activation") is not False
        or not isinstance(value.get("reasons"), list)
        or not value["reasons"]
        or not isinstance(value.get("integrity_sha256"), str)
        or value.get("integrity_sha256")
        != PREDECESSOR_SEMANTIC_INTEGRITY_SHA256
    ):
        _fail("decision_reason_catalog_v2_predecessor_invalid")
    material = copy.deepcopy(value)
    supplied = material.pop("integrity_sha256")
    if hashlib.sha256(_canonical_json(material)).hexdigest() != supplied:
        _fail("decision_reason_catalog_v2_predecessor_integrity_invalid")
    codes = [item.get("code") for item in value["reasons"]]
    if (
        any(not isinstance(item, dict) for item in value["reasons"])
        or any(not _IDENTIFIER_RE.fullmatch(str(code)) for code in codes)
        or len(codes) != len(set(codes))
    ):
        _fail("decision_reason_catalog_v2_predecessor_invalid")
    return copy.deepcopy(value)


def _candidate_reason_codes(value: Any) -> tuple[str, ...]:
    if not isinstance(value, dict) or not isinstance(value.get("reasons"), list):
        _fail("decision_reason_catalog_v2_candidate_unreadable")
    codes = tuple(item.get("code") for item in value["reasons"])
    if (
        not codes
        or any(
            not isinstance(code, str) or not _IDENTIFIER_RE.fullmatch(code)
            for code in codes
        )
        or len(codes) != len(set(codes))
    ):
        _fail("decision_reason_catalog_v2_candidate_unreadable")
    return codes


def _boundary_tuple(value: Any) -> tuple[int, int | str, int, int | str]:
    if (
        not isinstance(value, dict)
        or set(value) != _SELECTION_BOUNDARY_FIELDS
    ):
        _fail("decision_reason_catalog_v2_boundary_invalid")
    ranges = []
    for dimension in SELECTION_DIMENSIONS:
        item = value.get(dimension)
        if not isinstance(item, dict) or set(item) != _RANGE_FIELDS:
            _fail("decision_reason_catalog_v2_boundary_invalid")
        minimum = item.get("minimum_inclusive")
        maximum = item.get("maximum_inclusive")
        if (
            isinstance(minimum, bool)
            or not isinstance(minimum, int)
            or minimum < 0
            or not (
                maximum == "unbounded"
                or (
                    not isinstance(maximum, bool)
                    and isinstance(maximum, int)
                    and maximum >= minimum
                )
            )
        ):
            _fail("decision_reason_catalog_v2_boundary_invalid")
        ranges.extend((minimum, maximum))
    return tuple(ranges)  # type: ignore[return-value]


def _strict_object(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties),
    }


def _human_text_schema(
    *,
    minimum_length: int,
    maximum_length: int,
    minimum_words: int,
) -> dict[str, Any]:
    return {
        "type": "string",
        "minLength": minimum_length,
        "maxLength": maximum_length,
        "pattern": rf"^(?:\S+ ){{{minimum_words - 1},}}\S+$",
    }


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _human_text(
    value: Any,
    code: str,
    *,
    minimum_words: int = 6,
    minimum_characters: int = 12,
    maximum_characters: int = 800,
) -> str:
    if (
        not isinstance(value, str)
        or " ".join(value.split()) != value
        or len(value) < minimum_characters
        or len(value) > maximum_characters
        or len(value.split()) < minimum_words
        or value.casefold() in {"todo", "tbd", "placeholder"}
    ):
        _fail(code)
    return value


def _identifier(value: Any, code: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER_RE.fullmatch(value):
        _fail(code)
    return value


def _fail(code: str) -> None:
    raise Gate2FinancialDecisionReasonCatalogV2ContractError(code)
