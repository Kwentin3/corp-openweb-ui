from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any


CATALOG_SCHEMA_VERSION = "broker_reports_gate2_financial_decision_reason_catalog_v1"
CATALOG_ID = "broker_reports_gate2_financial_decision_reason_catalog"
CATALOG_SEMANTIC_VERSION = "1.0.0"
MANAGED_ASSET_FAMILY_ID = "broker_reports_gate2_financial_domain_assets"
CODE_CONTRACT_VERSION = "broker_reports_gate2_financial_evidence_decision_v1"
CATALOG_AUTHORITY_STATUS = "target_normative_not_live"
CATALOG_LIFECYCLE_STATUS = "draft"
CATALOG_LOCALE = "en"
CATALOG_DISPOSITION = "unclassified_financial_input"
SELECTION_METRIC = "plausible_distinct_available_financial_type_count"
FACTORY_REQUIRED = (
    "Gate2FinancialDecisionReasonCatalogContractFactory.create is the only "
    "managed decision-reason catalog validation entrypoint"
)
FORBIDDEN = (
    "Python must not own human reason wording, financial type meaning, "
    "provider repair, runtime activation, or filesystem and network access"
)

_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "catalog_id",
        "semantic_version",
        "managed_asset_family_id",
        "code_contract_version",
        "authority_status",
        "runtime_activation",
        "lifecycle",
        "locale",
        "applies_to_disposition",
        "selection_metric",
        "gui",
        "reasons",
        "integrity_sha256",
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
_BOUNDARY_FIELDS = frozenset(
    {
        "minimum_inclusive",
        "maximum_inclusive",
    }
)
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
    (0, 0),
    (2, "unbounded"),
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class Gate2FinancialDecisionReasonCatalogContractError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2FinancialDecisionReasonCatalogSnapshot:
    schema_version: str
    catalog_id: str
    semantic_version: str
    lifecycle_status: str
    runtime_activation: bool
    reason_codes: tuple[str, ...]
    reasons: tuple[dict[str, Any], ...]
    integrity_sha256: str
    canonical_semantic_bytes: int

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "catalog_id": self.catalog_id,
            "semantic_version": self.semantic_version,
            "lifecycle_status": self.lifecycle_status,
            "runtime_activation": self.runtime_activation,
            "reason_codes": list(self.reason_codes),
            "integrity_sha256": self.integrity_sha256,
            "canonical_semantic_bytes": self.canonical_semantic_bytes,
        }


class Gate2FinancialDecisionReasonCatalogContractFactory:
    def __init__(self, *, decision_contract_source: str) -> None:
        self.reason_codes = _decision_reason_codes(decision_contract_source)
        if len(self.reason_codes) != len(_EXPECTED_BOUNDARIES):
            _fail("decision_reason_catalog_boundary_count_mismatch")

    def schema(self) -> dict[str, Any]:
        reason_codes = list(self.reason_codes)
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
        reason_variants = [
            self._reason_schema(
                reason_code=reason_code,
                title=title,
                text=text,
            )
            for reason_code in reason_codes
        ]
        lifecycle = _strict_object(
            {
                "status": {"const": CATALOG_LIFECYCLE_STATUS},
                "draft_rollback": {"const": "discard_without_runtime_mutation"},
                "active_rollback": {
                    "const": ("select_previous_validated_immutable_family_version")
                },
            }
        )
        gui = _strict_object(
            {
                "collection_title": copy.deepcopy(title),
                "item_key": {"const": "code"},
                "item_label": {"const": "human_title"},
                "order_field": {"const": "display_order"},
                "editable_fields": {"const": list(_EDITABLE_REASON_FIELDS)},
                "immutable_fields": {"const": list(_IMMUTABLE_REASON_FIELDS)},
            }
        )
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": ("urn:broker-reports:gate2:financial-decision-reason-catalog:v1"),
            "title": ("Broker Reports Gate 2 financial decision reason catalog v1"),
            **_strict_object(
                {
                    "schema_version": {"const": CATALOG_SCHEMA_VERSION},
                    "catalog_id": {"const": CATALOG_ID},
                    "semantic_version": {"const": CATALOG_SEMANTIC_VERSION},
                    "managed_asset_family_id": {"const": MANAGED_ASSET_FAMILY_ID},
                    "code_contract_version": {"const": CODE_CONTRACT_VERSION},
                    "authority_status": {"const": CATALOG_AUTHORITY_STATUS},
                    "runtime_activation": {"const": False},
                    "lifecycle": lifecycle,
                    "locale": {"const": CATALOG_LOCALE},
                    "applies_to_disposition": {"const": CATALOG_DISPOSITION},
                    "selection_metric": {"const": SELECTION_METRIC},
                    "gui": gui,
                    "reasons": {
                        "type": "array",
                        "minItems": len(reason_codes),
                        "maxItems": len(reason_codes),
                        "uniqueItems": True,
                        "items": {"oneOf": reason_variants},
                        "allOf": [
                            *[
                                _exact_array_object_field_occurrence(
                                    field="code",
                                    value=reason_code,
                                )
                                for reason_code in reason_codes
                            ],
                            *[
                                _exact_array_object_field_occurrence(
                                    field="display_order",
                                    value=display_order,
                                )
                                for display_order in range(
                                    1,
                                    len(reason_codes) + 1,
                                )
                            ],
                            *[
                                _exact_array_object_field_occurrence(
                                    field="selection_boundary",
                                    value={
                                        "minimum_inclusive": minimum,
                                        "maximum_inclusive": maximum,
                                    },
                                )
                                for minimum, maximum in _EXPECTED_BOUNDARIES
                            ],
                        ],
                    },
                    "integrity_sha256": {
                        "type": "string",
                        "pattern": "^[0-9a-f]{64}$",
                    },
                }
            ),
        }

    def _reason_schema(
        self,
        *,
        reason_code: str,
        title: dict[str, Any],
        text: dict[str, Any],
    ) -> dict[str, Any]:
        neighbours = [value for value in self.reason_codes if value != reason_code]
        contrast_variants = [
            _strict_object(
                {
                    "reason_code": {"const": neighbour},
                    "distinction": copy.deepcopy(text),
                }
            )
            for neighbour in neighbours
        ]
        contrasts = {
            "type": "array",
            "minItems": len(neighbours),
            "maxItems": len(neighbours),
            "uniqueItems": True,
            "items": {"oneOf": contrast_variants},
            "allOf": [
                _exact_array_object_field_occurrence(
                    field="reason_code",
                    value=neighbour,
                )
                for neighbour in neighbours
            ],
        }
        selection_boundaries = [
            {
                "const": {
                    "minimum_inclusive": minimum,
                    "maximum_inclusive": maximum,
                }
            }
            for minimum, maximum in _EXPECTED_BOUNDARIES
        ]
        return _strict_object(
            {
                "code": {"const": reason_code},
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
                "contrast_with_neighbouring_reasons": contrasts,
                "selection_boundary": {
                    "oneOf": selection_boundaries,
                },
            }
        )

    def create(
        self,
        *,
        catalog: Any,
    ) -> Gate2FinancialDecisionReasonCatalogSnapshot:
        if not isinstance(catalog, dict) or set(catalog) != _TOP_LEVEL_FIELDS:
            _fail("decision_reason_catalog_projection_invalid")
        if (
            catalog.get("schema_version") != CATALOG_SCHEMA_VERSION
            or catalog.get("catalog_id") != CATALOG_ID
            or catalog.get("semantic_version") != CATALOG_SEMANTIC_VERSION
            or catalog.get("managed_asset_family_id") != MANAGED_ASSET_FAMILY_ID
            or catalog.get("code_contract_version") != CODE_CONTRACT_VERSION
            or catalog.get("authority_status") != CATALOG_AUTHORITY_STATUS
            or catalog.get("runtime_activation") is not False
            or catalog.get("locale") != CATALOG_LOCALE
            or catalog.get("applies_to_disposition") != CATALOG_DISPOSITION
            or catalog.get("selection_metric") != SELECTION_METRIC
        ):
            _fail("decision_reason_catalog_identity_invalid")
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
            _fail("decision_reason_catalog_integrity_invalid")
        return Gate2FinancialDecisionReasonCatalogSnapshot(
            schema_version=CATALOG_SCHEMA_VERSION,
            catalog_id=CATALOG_ID,
            semantic_version=CATALOG_SEMANTIC_VERSION,
            lifecycle_status=CATALOG_LIFECYCLE_STATUS,
            runtime_activation=False,
            reason_codes=self.reason_codes,
            reasons=tuple(copy.deepcopy(reasons)),
            integrity_sha256=calculated_integrity,
            canonical_semantic_bytes=len(canonical),
        )

    @staticmethod
    def _validate_lifecycle(value: Any) -> None:
        if not isinstance(value, dict) or set(value) != _LIFECYCLE_FIELDS:
            _fail("decision_reason_catalog_lifecycle_invalid")
        if value != {
            "status": CATALOG_LIFECYCLE_STATUS,
            "draft_rollback": "discard_without_runtime_mutation",
            "active_rollback": ("select_previous_validated_immutable_family_version"),
        }:
            _fail("decision_reason_catalog_lifecycle_invalid")

    @staticmethod
    def _validate_gui(value: Any) -> None:
        if not isinstance(value, dict) or set(value) != _GUI_FIELDS:
            _fail("decision_reason_catalog_gui_contract_invalid")
        _human_text(
            value.get("collection_title"),
            "decision_reason_catalog_gui_title_invalid",
            minimum_words=2,
            minimum_characters=5,
            maximum_characters=120,
        )
        if (
            value.get("item_key") != "code"
            or value.get("item_label") != "human_title"
            or value.get("order_field") != "display_order"
            or value.get("editable_fields") != list(_EDITABLE_REASON_FIELDS)
            or value.get("immutable_fields") != list(_IMMUTABLE_REASON_FIELDS)
        ):
            _fail("decision_reason_catalog_gui_contract_invalid")

    def _validate_reasons(self, value: Any) -> list[dict[str, Any]]:
        if (
            not isinstance(value, list)
            or len(value) != len(self.reason_codes)
            or any(not isinstance(item, dict) for item in value)
        ):
            _fail("decision_reason_catalog_reasons_invalid")
        reasons = [copy.deepcopy(item) for item in value]
        codes = [item.get("code") for item in reasons]
        if len(codes) != len(set(codes)) or set(codes) != set(self.reason_codes):
            _fail("decision_reason_catalog_codes_mismatch")
        display_orders = [item.get("display_order") for item in reasons]
        if any(not _json_schema_integer(item) for item in display_orders) or set(
            display_orders
        ) != set(range(1, len(reasons) + 1)):
            _fail("decision_reason_catalog_display_order_invalid")

        boundaries: set[tuple[int | float, int | float | str]] = set()
        human_values: list[str] = []
        for reason in reasons:
            if set(reason) != _REASON_FIELDS:
                _fail("decision_reason_catalog_reason_projection_invalid")
            code = reason["code"]
            _identifier(code, "decision_reason_catalog_code_invalid")
            human_values.append(
                _human_text(
                    reason.get("human_title"),
                    "decision_reason_catalog_human_title_invalid",
                    minimum_words=2,
                    minimum_characters=5,
                    maximum_characters=120,
                )
            )
            for field in (
                "meaning",
                "use_when",
                "do_not_use_when",
                "positive_example",
            ):
                human_values.append(
                    _human_text(
                        reason.get(field),
                        "decision_reason_catalog_" + field + "_invalid",
                    )
                )
            contrasts = reason.get("contrast_with_neighbouring_reasons")
            expected_neighbours = set(self.reason_codes) - {code}
            if not isinstance(contrasts, list) or len(contrasts) != len(
                expected_neighbours
            ):
                _fail("decision_reason_catalog_contrasts_invalid")
            neighbour_codes = []
            for contrast in contrasts:
                if not isinstance(contrast, dict) or set(contrast) != _CONTRAST_FIELDS:
                    _fail("decision_reason_catalog_contrast_invalid")
                neighbour_code = contrast.get("reason_code")
                if neighbour_code == code:
                    _fail("decision_reason_catalog_self_contrast_forbidden")
                neighbour_codes.append(neighbour_code)
                human_values.append(
                    _human_text(
                        contrast.get("distinction"),
                        "decision_reason_catalog_distinction_invalid",
                    )
                )
            if (
                len(neighbour_codes) != len(set(neighbour_codes))
                or set(neighbour_codes) != expected_neighbours
            ):
                _fail("decision_reason_catalog_contrasts_incomplete")
            boundary = reason.get("selection_boundary")
            if not isinstance(boundary, dict) or set(boundary) != _BOUNDARY_FIELDS:
                _fail("decision_reason_catalog_boundary_invalid")
            minimum = boundary.get("minimum_inclusive")
            maximum = boundary.get("maximum_inclusive")
            if (
                not _json_schema_integer(minimum)
                or minimum < 0
                or not (maximum == "unbounded" or _json_schema_integer(maximum))
                or (_json_schema_integer(maximum) and maximum < minimum)
            ):
                _fail("decision_reason_catalog_boundary_invalid")
            boundaries.add((minimum, maximum))

        if boundaries != set(_EXPECTED_BOUNDARIES):
            _fail("decision_reason_catalog_boundaries_invalid")
        normalized_values = [item.casefold() for item in human_values]
        if len(normalized_values) != len(set(normalized_values)):
            _fail("decision_reason_catalog_human_text_not_distinct")
        return reasons


def _decision_reason_codes(source: str) -> tuple[str, ...]:
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError) as exc:
        raise Gate2FinancialDecisionReasonCatalogContractError(
            "decision_reason_code_authority_unreadable"
        ) from exc
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(
            isinstance(target, ast.Name) and target.id == "UNCLASSIFIED_REASON_CODES"
            for target in targets
        ):
            continue
        try:
            literal = ast.literal_eval(node.value)
        except (ValueError, TypeError) as exc:
            raise Gate2FinancialDecisionReasonCatalogContractError(
                "decision_reason_code_authority_invalid"
            ) from exc
        if (
            not isinstance(literal, tuple)
            or not literal
            or any(not isinstance(item, str) for item in literal)
            or len(literal) != len(set(literal))
        ):
            _fail("decision_reason_code_authority_invalid")
        for item in literal:
            _identifier(item, "decision_reason_code_authority_invalid")
        return tuple(literal)
    _fail("decision_reason_code_authority_missing")


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


def _exact_array_object_field_occurrence(
    *,
    field: str,
    value: Any,
) -> dict[str, Any]:
    return {
        "contains": {
            "type": "object",
            "properties": {field: {"const": value}},
            "required": [field],
        },
        "minContains": 1,
        "maxContains": 1,
    }


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _json_schema_integer(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, float) and value.is_integer()


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
    raise Gate2FinancialDecisionReasonCatalogContractError(code)
