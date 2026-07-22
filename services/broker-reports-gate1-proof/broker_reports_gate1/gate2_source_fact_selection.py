from __future__ import annotations

import copy
import json
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .contracts import stable_digest
from .gate1_public_contracts import reproduce_normalized_value
from .gate2_source_fact_contracts import (
    FACT_TYPES,
    NO_FACT_REASON_VALUES,
    NORMALIZED_VALUE_FIELDS,
)


FACTORY_REQUIRED = "Gate2SourceFactSelectionFactory.create is the only production semantic-selection validation/materialization entrypoint"
FORBIDDEN = "The semantic-selection materializer must not invent model-selected fact types, source ownership, values or refs"

SOURCE_FACT_SELECTION_SCHEMA_VERSION = "broker_reports_source_fact_selection_v2"
SOURCE_FACT_SELECTION_VALIDATION_SCHEMA_VERSION = (
    "broker_reports_source_fact_selection_validation_v2"
)

_NORMALIZATION_KIND_BY_FIELD = {
    "date": "iso_date_exact",
    "amount": "decimal_dot",
    "currency": "currency_code_visible",
    "quantity": "decimal_dot",
    "rate": "decimal_dot",
    "converted_amount": "decimal_dot",
    "identifier": "trimmed_text",
    "label": "trimmed_text",
}

_FIELD_BY_HEADER_LABEL = {
    "date": "date",
    "amount": "amount",
    "currency": "currency",
    "quantity": "quantity",
    "rate": "rate",
    "converted_amount": "converted_amount",
    "identifier": "identifier",
    "instrument": "identifier",
    "label": "label",
}

_REQUIRED_ANY_FIELDS_BY_FACT_TYPE = {
    "trade_operation": {"date", "amount", "quantity", "identifier"},
    "income": {"amount"},
    "fee_commission": {"amount"},
    "cash_movement": {"amount"},
    "currency_fx": {"amount", "rate", "converted_amount"},
    "position_snapshot": {"date", "quantity", "amount", "identifier"},
    "document_summary_evidence": set(NORMALIZED_VALUE_FIELDS),
}


@dataclass(frozen=True)
class Gate2SourceFactSelectionOutcome:
    validation: dict[str, Any]
    canonical_candidate: dict[str, Any] | None


class Gate2SourceFactSelectionFactory:
    def create(self) -> "Gate2SourceFactSelectionRuntime":
        return Gate2SourceFactSelectionRuntime()


class Gate2SourceFactSelectionRuntime:
    def validate_and_materialize(
        self,
        *,
        selection: dict[str, Any],
        package: dict[str, Any],
    ) -> Gate2SourceFactSelectionOutcome:
        validation = validate_source_fact_selection(
            selection=selection,
            package=package,
        )
        if validation["validator_status"] != "passed":
            return Gate2SourceFactSelectionOutcome(
                validation=validation,
                canonical_candidate=None,
            )
        return Gate2SourceFactSelectionOutcome(
            validation=validation,
            canonical_candidate=materialize_source_fact_selection(
                selection=selection,
                package=package,
            ),
        )


def source_fact_selection_response_format(package: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": SOURCE_FACT_SELECTION_SCHEMA_VERSION,
            "strict": True,
            "schema": source_fact_selection_provider_json_schema(package),
        },
    }


def source_fact_selection_provider_json_schema(
    package: dict[str, Any],
) -> dict[str, Any]:
    decision_refs = _decision_source_refs(package)
    reproducible_refs = _reproducible_value_refs_by_field(package)
    allowed_fact_types = _provider_allowed_fact_types(
        package=package,
        reproducible_fields=set(reproducible_refs),
    )
    binding_variants = [
        _strict_object(
            {
                "field": {"type": "string", "const": field},
                "source_value_ref": _enum_or_uninhabited(refs),
            }
        )
        for field, refs in sorted(reproducible_refs.items())
        if refs
    ]
    value_binding = (
        {"anyOf": binding_variants}
        if binding_variants
        else _strict_object(
            {
                "field": _enum_or_uninhabited([]),
                "source_value_ref": _enum_or_uninhabited([]),
            }
        )
    )
    fact = _strict_object(
        {
            "source_ref": _enum_or_uninhabited(decision_refs),
            "fact_type": {
                "type": "string",
                "enum": sorted(allowed_fact_types),
            },
            "value_bindings": {
                "type": "array",
                "items": copy.deepcopy(value_binding),
                "maxItems": len(binding_variants),
            },
        }
    )
    no_fact = _strict_object(
        {
            "source_ref": _enum_or_uninhabited(decision_refs),
            "reason_code": {
                "type": "string",
                "enum": sorted(NO_FACT_REASON_VALUES),
            },
        }
    )
    return _strict_object(
        {
            "facts": {
                "type": "array",
                "items": fact,
                "maxItems": len(decision_refs),
            },
            "no_fact_results": {
                "type": "array",
                "items": no_fact,
                "maxItems": len(decision_refs),
            },
        }
    )


def source_fact_selection_schema_hash(package: dict[str, Any]) -> str:
    return stable_digest(
        source_fact_selection_provider_json_schema(package),
        length=64,
    )


def parse_source_fact_selection_model_output(value: Any) -> dict[str, Any]:
    parsed = value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped.startswith("{") or not stripped.endswith("}"):
            raise ValueError("source_fact_selection_structured_output_required")
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError("source_fact_selection_schema_mismatch") from exc
    if not isinstance(parsed, dict):
        raise ValueError("source_fact_selection_schema_mismatch")
    return copy.deepcopy(parsed)


def validate_source_fact_selection(
    *,
    selection: dict[str, Any],
    package: dict[str, Any],
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    model_system_metadata_fields_total = _unexpected_field_count(selection)
    _require_exact_keys(selection, {"facts", "no_fact_results"}, "$", errors)
    facts_value = selection.get("facts")
    no_fact_value = selection.get("no_fact_results")
    if not isinstance(facts_value, list):
        errors.append(_error("source_fact_selection_schema_mismatch", "$.facts"))
    if not isinstance(no_fact_value, list):
        errors.append(
            _error("source_fact_selection_schema_mismatch", "$.no_fact_results")
        )
    facts = _dict_list(facts_value)
    no_fact_results = _dict_list(no_fact_value)
    if isinstance(facts_value, list) and len(facts) != len(facts_value):
        errors.append(_error("source_fact_selection_schema_mismatch", "$.facts"))
    if isinstance(no_fact_value, list) and len(no_fact_results) != len(no_fact_value):
        errors.append(
            _error("source_fact_selection_schema_mismatch", "$.no_fact_results")
        )

    decision_refs = _decision_source_refs(package)
    decision_ref_set = set(decision_refs)
    reproducible_refs = _reproducible_value_refs_by_field(package)
    allowed_fact_types = _provider_allowed_fact_types(
        package=package,
        reproducible_fields=set(reproducible_refs),
    )
    accounted: list[str] = []
    materialized_values: dict[int, dict[str, tuple[str, str]]] = {}

    for index, fact in enumerate(facts):
        path = f"$.facts[{index}]"
        _require_exact_keys(
            fact,
            {
                "source_ref",
                "fact_type",
                "value_bindings",
            },
            path,
            errors,
        )
        source_ref = str(fact.get("source_ref") or "")
        accounted.append(source_ref)
        if source_ref not in decision_ref_set:
            errors.append(
                _error("source_fact_selection_cross_package_scope", source_ref)
            )
        fact_type = str(fact.get("fact_type") or "")
        if fact_type not in allowed_fact_types:
            errors.append(
                _error("source_fact_selection_fact_type_forbidden", f"{path}.fact_type")
            )
        hinted_fact_type = _fact_type_hint_for_source(
            package=package,
            source_ref=source_ref,
        )
        if hinted_fact_type and fact_type != hinted_fact_type:
            errors.append(_error("source_fact_selection_fact_type_hint_mismatch", path))
        if fact_type == "unknown_source_row" and fact.get("value_bindings"):
            errors.append(
                _error("source_fact_selection_unknown_binding_forbidden", path)
            )

        bindings_value = fact.get("value_bindings")
        bindings = _dict_list(bindings_value)
        if not isinstance(bindings_value, list) or len(bindings) != len(
            bindings_value if isinstance(bindings_value, list) else []
        ):
            errors.append(
                _error(
                    "source_fact_selection_schema_mismatch", f"{path}.value_bindings"
                )
            )
            continue
        seen_fields: set[str] = set()
        resolved: dict[str, tuple[str, str]] = {}
        for binding_index, binding in enumerate(bindings):
            binding_path = f"{path}.value_bindings[{binding_index}]"
            _require_exact_keys(
                binding,
                {"field", "source_value_ref"},
                binding_path,
                errors,
            )
            field = str(binding.get("field") or "")
            source_value_ref = str(binding.get("source_value_ref") or "")
            if field not in NORMALIZED_VALUE_FIELDS:
                errors.append(
                    _error("source_fact_selection_field_forbidden", binding_path)
                )
                continue
            if field in seen_fields:
                errors.append(
                    _error("source_fact_selection_duplicate_field", binding_path)
                )
                continue
            seen_fields.add(field)
            if source_value_ref not in set(reproducible_refs.get(field, [])):
                errors.append(
                    _error(
                        "source_fact_selection_value_binding_not_admissible",
                        binding_path,
                    )
                )
                continue
            if not _source_value_ref_matches_source(
                package=package,
                source_value_ref=source_value_ref,
                source_ref=source_ref,
            ):
                errors.append(
                    _error(
                        "source_fact_selection_value_ref_out_of_scope",
                        binding_path,
                    )
                )
                continue
            try:
                normalized_value = reproduce_normalized_value(
                    _package_source_slice(package),
                    source_value_ref,
                    _NORMALIZATION_KIND_BY_FIELD[field],
                )
            except ValueError:
                errors.append(
                    _error(
                        "source_fact_selection_value_unreproducible",
                        binding_path,
                    )
                )
                continue
            resolved[field] = (source_value_ref, normalized_value)
        materialized_values[index] = resolved
        _validate_fact_minimum_values(
            fact_type=fact_type,
            resolved=resolved,
            path=path,
            errors=errors,
        )

    for index, item in enumerate(no_fact_results):
        path = f"$.no_fact_results[{index}]"
        _require_exact_keys(item, {"source_ref", "reason_code"}, path, errors)
        source_ref = str(item.get("source_ref") or "")
        accounted.append(source_ref)
        if source_ref not in decision_ref_set:
            errors.append(
                _error("source_fact_selection_cross_package_scope", source_ref)
            )
        if item.get("reason_code") not in NO_FACT_REASON_VALUES:
            errors.append(
                _error("source_fact_selection_no_fact_reason_forbidden", path)
            )

    if len(accounted) != len(set(accounted)):
        errors.append(
            _error("source_fact_selection_duplicate_source_ownership", "$.coverage")
        )
    if set(accounted) != decision_ref_set:
        errors.append(_error("source_fact_selection_coverage_gap", "$.coverage"))
    validation = {
        "schema_version": SOURCE_FACT_SELECTION_VALIDATION_SCHEMA_VERSION,
        "validator_status": "passed" if not errors else "failed",
        "errors_count": len(errors),
        "errors": errors,
        "error_code_counts": dict(
            sorted(Counter(item["code"] for item in errors).items())
        ),
        "decision_source_refs_total": len(decision_refs),
        "accounted_source_refs_total": len(set(accounted) & decision_ref_set),
        "facts_total": len(facts),
        "no_fact_results_total": len(no_fact_results),
        "value_bindings_total": sum(len(item) for item in materialized_values.values()),
        "model_system_metadata_fields_total": model_system_metadata_fields_total,
    }
    return validation


def materialize_source_fact_selection(
    *,
    selection: dict[str, Any],
    package: dict[str, Any],
) -> dict[str, Any]:
    facts = []
    for fact in _dict_list(selection.get("facts")):
        fact_type = str(fact["fact_type"])
        subtype = "unknown"
        uncertainty_codes = (
            ["source_fact_selection_unknown"]
            if fact_type == "unknown_source_row"
            else []
        )
        normalized = {field: None for field in NORMALIZED_VALUE_FIELDS}
        original = {field: [] for field in NORMALIZED_VALUE_FIELDS}
        source_ref = str(fact["source_ref"])
        for binding in _dict_list(fact.get("value_bindings")):
            field = str(binding["field"])
            source_value_ref = str(binding["source_value_ref"])
            normalized[field] = reproduce_normalized_value(
                _package_source_slice(package),
                source_value_ref,
                _NORMALIZATION_KIND_BY_FIELD[field],
            )
            original[field] = [source_value_ref]
        facts.append(
            {
                "fact_id": "pending",
                "fact_type": fact_type,
                "fact_subtype": subtype,
                "document_ref": None,
                "extraction_package_ref": None,
                "source_unit_ref": None,
                "source_location": {
                    "row_ref": source_ref,
                    "text_segment_refs": [source_ref],
                },
                "extracted_fields": _default_extracted_fields(
                    fact_type=fact_type,
                    subtype=subtype,
                    uncertainty_codes=uncertainty_codes,
                ),
                "normalized_values": normalized,
                "original_value_refs": original,
                "date": None,
                "amount": None,
                "currency": None,
                "quantity": None,
                "instrument": None,
                "confidence": "low" if fact_type == "unknown_source_row" else "medium",
                "completeness": (
                    "uncertain" if fact_type == "unknown_source_row" else "partial"
                ),
                "evidence_refs": [source_ref],
                "linked_issue_refs": [],
                "issue_impact": {},
                "extraction_warnings": uncertainty_codes,
                "downstream_use": {
                    "downstream_usable": fact_type != "unknown_source_row",
                    "gate3_ledger_candidate": False,
                    "cross_document_consolidation_allowed": False,
                    "tax_calculation_allowed": False,
                    "declaration_mapping_allowed": False,
                    "restriction_codes": [],
                },
                "extraction_audit": {},
                "validator_status": "pending",
                "validation_ref": None,
            }
        )
    mandatory = copy.deepcopy(
        _dict_list(
            _object(package.get("coverage_expectation")).get(
                "mandatory_no_fact_results"
            )
        )
    )
    return {
        "facts": facts,
        "coverage": {
            "no_fact_results": [
                *mandatory,
                *copy.deepcopy(_dict_list(selection.get("no_fact_results"))),
            ]
        },
    }


def _decision_source_refs(package: dict[str, Any]) -> list[str]:
    expectation = _object(package.get("coverage_expectation"))
    selected = _strings(expectation.get("selected_source_refs"))
    mandatory = {
        str(item.get("source_ref") or "")
        for item in _dict_list(expectation.get("mandatory_no_fact_results"))
        if item.get("source_ref")
    }
    return [item for item in selected if item not in mandatory]


def _allowed_fact_types(package: dict[str, Any]) -> set[str]:
    allowed = set(_strings(package.get("allowed_fact_types")))
    return (allowed & FACT_TYPES) or set(FACT_TYPES)


def _provider_allowed_fact_types(
    *,
    package: dict[str, Any],
    reproducible_fields: set[str],
) -> set[str]:
    result = {"unknown_source_row"}
    for fact_type in _allowed_fact_types(package) - {"unknown_source_row"}:
        if fact_type == "withholding_tax":
            if {"amount", "currency"} <= reproducible_fields:
                result.add(fact_type)
            continue
        if (
            _REQUIRED_ANY_FIELDS_BY_FACT_TYPE.get(fact_type, set())
            & reproducible_fields
        ):
            result.add(fact_type)
    return result


def _reproducible_value_refs_by_field(
    package: dict[str, Any],
) -> dict[str, list[str]]:
    unit = _object(package.get("source_unit"))
    projection = _object(unit.get("model_source_projection"))
    candidates: dict[str, set[str]] = {
        field: set() for field in NORMALIZED_VALUE_FIELDS
    }
    allowed_refs = set(_strings(package.get("allowed_source_value_refs")))

    for item in _dict_list(package.get("deterministic_value_candidates")):
        field = str(item.get("field") or "")
        source_value_ref = str(item.get("source_value_ref") or "")
        if field in candidates and source_value_ref in allowed_refs:
            candidates[field].add(source_value_ref)

    for row in _dict_list(projection.get("rows")):
        for cell in _dict_list(row.get("cells")):
            field = _FIELD_BY_HEADER_LABEL.get(str(cell.get("header_label") or ""))
            source_value_ref = str(cell.get("source_value_ref") or "")
            if field and source_value_ref in allowed_refs:
                candidates[field].add(source_value_ref)

    for segment in _dict_list(projection.get("segments")):
        source_value_ref = str(segment.get("source_value_ref") or "")
        if source_value_ref in allowed_refs:
            candidates["label"].add(source_value_ref)

    for item in _dict_list(unit.get("segment_provenance")):
        for source_value_ref in [
            *_strings(item.get("source_value_refs")),
            *([str(item["source_value_ref"])] if item.get("source_value_ref") else []),
        ]:
            if source_value_ref in allowed_refs:
                candidates["label"].add(source_value_ref)

    source_slice = _package_source_slice(package)
    result: dict[str, list[str]] = {}
    for field, refs in candidates.items():
        reproducible = []
        for source_value_ref in sorted(refs):
            try:
                reproduce_normalized_value(
                    source_slice,
                    source_value_ref,
                    _NORMALIZATION_KIND_BY_FIELD[field],
                )
            except ValueError:
                continue
            reproducible.append(source_value_ref)
        if reproducible:
            result[field] = reproducible
    return result


def _source_value_ref_matches_source(
    *,
    package: dict[str, Any],
    source_value_ref: str,
    source_ref: str,
) -> bool:
    if source_value_ref not in set(_strings(package.get("allowed_source_value_refs"))):
        return False
    unit = _object(package.get("source_unit"))
    projection = _object(unit.get("model_source_projection"))
    row_value_refs = {
        str(cell.get("source_value_ref"))
        for row in _dict_list(projection.get("rows"))
        if str(row.get("row_ref") or "") == source_ref
        for cell in _dict_list(row.get("cells"))
        if cell.get("source_value_ref")
    }
    segment_value_refs = {
        str(segment.get("source_value_ref"))
        for segment in _dict_list(projection.get("segments"))
        if str(segment.get("text_segment_ref") or "") == source_ref
        and segment.get("source_value_ref")
    }
    if source_value_ref in row_value_refs | segment_value_refs:
        return True
    provenance_value_refs = {
        str(value_ref)
        for item in [
            *_dict_list(unit.get("row_provenance")),
            *_dict_list(unit.get("segment_provenance")),
        ]
        if source_ref
        in {
            str(item.get("row_ref") or ""),
            str(item.get("text_segment_ref") or ""),
        }
        for value_ref in [
            *_strings(item.get("source_value_refs")),
            *([item.get("source_value_ref")] if item.get("source_value_ref") else []),
        ]
    }
    if source_value_ref in provenance_value_refs:
        return True
    item = next(
        (
            value
            for value in _dict_list(unit.get("source_value_index"))
            if str(value.get("source_value_ref") or "") == source_value_ref
        ),
        None,
    )
    if item is None:
        return False
    linked_refs = {
        str(value)
        for value in (item.get("row_ref"), item.get("text_segment_ref"))
        if value is not None and str(value)
    }
    return source_ref in linked_refs


def _fact_type_hint_for_source(
    *,
    package: dict[str, Any],
    source_ref: str,
) -> str | None:
    projection = _object(
        _object(package.get("source_unit")).get("model_source_projection")
    )
    for row in _dict_list(projection.get("rows")):
        if str(row.get("row_ref") or "") != source_ref:
            continue
        value = str(row.get("fact_type_hint") or "")
        return value if value in FACT_TYPES else None
    return None


def _package_source_slice(package: dict[str, Any]) -> dict[str, Any]:
    unit = copy.deepcopy(_object(package.get("source_unit")))
    projection = _object(unit.get("normalized_source_projection"))
    unit["cells"] = copy.deepcopy(projection.get("cells") or [])
    unit["text"] = str(projection.get("text") or "")
    unit["source_value_refs"] = _strings(package.get("allowed_source_value_refs"))
    return unit


def _validate_fact_minimum_values(
    *,
    fact_type: str,
    resolved: dict[str, tuple[str, str]],
    path: str,
    errors: list[dict[str, str]],
) -> None:
    fields = set(resolved)
    if fact_type == "unknown_source_row":
        return
    if fact_type == "withholding_tax":
        if not {"amount", "currency"} <= fields:
            errors.append(_error("source_fact_selection_required_value_missing", path))
        return
    required = _REQUIRED_ANY_FIELDS_BY_FACT_TYPE.get(fact_type, set())
    if required and not required & fields:
        errors.append(_error("source_fact_selection_required_value_missing", path))


def _default_extracted_fields(
    *,
    fact_type: str,
    subtype: str,
    uncertainty_codes: list[str],
) -> dict[str, Any]:
    if fact_type == "trade_operation":
        return {
            "operation_type_candidate": subtype,
            "source_visible_direction_refs": [],
        }
    if fact_type == "income":
        return {
            "income_type_candidate": subtype,
            "source_country_candidate": None,
            "source_country_value_refs": [],
        }
    if fact_type == "withholding_tax":
        return {
            "withholding_type_candidate": subtype,
            "source_country_candidate": None,
            "related_income_source_refs": [],
        }
    if fact_type == "fee_commission":
        return {
            "fee_type_candidate": subtype,
            "related_operation_source_refs": [],
        }
    if fact_type == "cash_movement":
        return {
            "movement_type_candidate": subtype,
            "description_safe_label": None,
            "description_value_refs": [],
        }
    if fact_type == "currency_fx":
        return {"fx_fact_kind": subtype}
    if fact_type == "position_snapshot":
        return {"position_kind_candidate": subtype}
    if fact_type == "document_summary_evidence":
        return {"summary_kind_candidate": subtype, "source_provided": True}
    return {
        "unknown_reason_codes": uncertainty_codes or ["source_fact_selection_unknown"]
    }


def _enum_or_uninhabited(values: list[str]) -> dict[str, Any]:
    return {
        "type": "string",
        "enum": values or ["__no_admissible_value__"],
    }


def _unexpected_field_count(selection: dict[str, Any]) -> int:
    total = len(set(selection) - {"facts", "no_fact_results"})
    fact_fields = {
        "source_ref",
        "fact_type",
        "value_bindings",
    }
    for fact in _dict_list(selection.get("facts")):
        total += len(set(fact) - fact_fields)
        for binding in _dict_list(fact.get("value_bindings")):
            total += len(set(binding) - {"field", "source_value_ref"})
    for item in _dict_list(selection.get("no_fact_results")):
        total += len(set(item) - {"source_ref", "reason_code"})
    return total


def _strict_object(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": copy.deepcopy(properties),
        "required": list(properties),
    }


def _require_exact_keys(
    value: dict[str, Any],
    expected: set[str],
    path: str,
    errors: list[dict[str, str]],
) -> None:
    if set(value) != expected:
        errors.append(_error("source_fact_selection_schema_mismatch", path))


def _error(code: str, subject: Any) -> dict[str, str]:
    return {"code": code, "subject": str(subject or "")[:240]}


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_list(value: Any) -> list[dict[str, Any]]:
    return (
        [item for item in value or [] if isinstance(item, dict)]
        if isinstance(value, list)
        else []
    )


def _strings(value: Any) -> list[str]:
    return (
        [str(item) for item in value or [] if item is not None and str(item)]
        if isinstance(value, list)
        else []
    )
