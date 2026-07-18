from __future__ import annotations

import copy
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from .contracts import stable_digest
from .gate1_public_contracts import reproduce_normalized_value
from .gate2_candidate_binding import (
    BINDING_OUTPUT_SCHEMA_VERSION,
    BINDING_VALIDATION_SCHEMA_VERSION,
)
from .gate2_source_fact_contracts import NORMALIZED_VALUE_FIELDS


FACTORY_REQUIRED = (
    "Gate2CandidateBindingRuntimeFactory.create is the only production binding validation/materialization entrypoint"
)
FORBIDDEN = (
    "The binding materializer must not choose candidates, semantic roles, relations or ambiguity resolutions"
)


class Gate2CandidateBindingRuntimeFactory:
    def create(self) -> "Gate2CandidateBindingRuntime":
        return Gate2CandidateBindingRuntime()


@dataclass(frozen=True)
class Gate2CandidateBindingOutcome:
    validation: dict[str, Any]
    legacy_candidate: dict[str, Any] | None


class Gate2CandidateBindingRuntime:
    def validate_and_materialize(
        self,
        *,
        selection: dict[str, Any],
        package: dict[str, Any],
    ) -> Gate2CandidateBindingOutcome:
        validation = validate_candidate_binding_selection(
            selection=selection,
            package=package,
        )
        if validation["validator_status"] != "passed":
            return Gate2CandidateBindingOutcome(validation=validation, legacy_candidate=None)
        return Gate2CandidateBindingOutcome(
            validation=validation,
            legacy_candidate=materialize_candidate_binding_selection(
                selection=selection,
                package=package,
            ),
        )


def candidate_binding_response_format(package: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "broker_reports_candidate_binding_output_v0",
            "strict": True,
            "schema": candidate_binding_provider_json_schema(package),
        },
    }


def candidate_binding_provider_json_schema(package: dict[str, Any]) -> dict[str, Any]:
    candidate_set = _object(package.get("source_value_candidate_set"))
    relation_set = _object(package.get("candidate_relation_set"))
    profile = _object(package.get("candidate_binding_profile"))
    candidates = _dict_list(candidate_set.get("candidates"))
    relations = _dict_list(relation_set.get("relations"))
    selected_refs = _strings(
        _object(package.get("coverage_expectation")).get("selected_source_refs")
    )
    domain = str(package.get("extractor_domain") or "")
    candidate_ids = sorted(
        str(item.get("candidate_id") or "") for item in candidates if item.get("candidate_id")
    )
    semantic_roles = sorted(
        {
            role
            for item in candidates
            for role in _strings(item.get("allowed_semantic_roles"))
        }
    )
    fact_field_paths = sorted(
        {
            str(path)
            for item in candidates
            for path in _strings(item.get("allowed_fact_field_paths"))
        }
    )
    relation_ids = sorted(
        str(item.get("relation_id") or "") for item in relations if item.get("relation_id")
    )
    ambiguity_refs = sorted(
        {
            str(item.get("ambiguity_group_ref"))
            for item in candidates
            if item.get("ambiguity_group_ref")
        }
    )
    issue_limited = bool(_strings(package.get("allowed_issue_refs")))
    binding_item = _strict_object(
        {
            "fact_field_path": _enum_or_uninhabited(fact_field_paths),
            "candidate_id": _enum_or_uninhabited(candidate_ids),
            "semantic_role": _enum_or_uninhabited(semantic_roles),
        }
    )
    result_item = _strict_object(
        {
            "source_ref": {"type": "string", "enum": selected_refs},
            "fact_type": {
                "type": "string",
                "enum": [domain, "unknown_source_row"],
            },
            "selected_bindings": {
                "type": "array",
                "items": binding_item,
                "maxItems": len(candidate_ids),
                "uniqueItems": True,
            },
            "selected_relation_ids": _restricted_array(relation_ids),
            "subtype_candidate": {
                "type": "string",
                "enum": sorted(set(_strings(profile.get("subtypes")) + ["unknown"])),
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low", "none"],
            },
            "completeness": {
                "type": "string",
                "enum": (
                    ["partial", "uncertain", "blocked"]
                    if issue_limited
                    else ["complete", "partial", "uncertain", "blocked"]
                ),
            },
            "uncertainty_codes": {
                "type": "array",
                "items": {"type": "string"},
            },
            "resolved_ambiguity_group_refs": _restricted_array(ambiguity_refs),
        }
    )
    no_fact = _strict_object(
        {
            "source_ref": {"type": "string", "enum": selected_refs},
            "reason_code": {
                "type": "string",
                "enum": [
                    "header_row",
                    "blank_row",
                    "layout_only",
                    "repeated_header",
                    "non_fact_annotation",
                    "unsupported_source_shape",
                ],
            },
        }
    )
    return _strict_object(
        {
            "schema_version": {
                "type": "string",
                "const": BINDING_OUTPUT_SCHEMA_VERSION,
            },
            "package_id": {
                "type": "string",
                "const": package.get("package_id"),
            },
            "candidate_set_id": {
                "type": "string",
                "const": candidate_set.get("candidate_set_id"),
            },
            "candidate_set_hash": {
                "type": "string",
                "const": candidate_set.get("candidate_set_hash"),
            },
            "relation_set_id": {
                "type": "string",
                "const": relation_set.get("relation_set_id"),
            },
            "relation_set_hash": {
                "type": "string",
                "const": relation_set.get("relation_set_hash"),
            },
            "binding_results": {
                "type": "array",
                "items": result_item,
                "maxItems": len(selected_refs),
            },
            "no_fact_results": {"type": "array", "items": no_fact},
        }
    )


def _enum_or_uninhabited(values: list[str]) -> dict[str, Any]:
    if values:
        return {"type": "string", "enum": values}
    return {"type": "string", "enum": ["__no_admissible_value__"]}


def candidate_binding_schema_hash(package: dict[str, Any]) -> str:
    return stable_digest(candidate_binding_provider_json_schema(package), length=64)


def parse_candidate_binding_model_output(value: Any) -> dict[str, Any]:
    parsed = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("candidate_binding_structured_output_required") from exc
    if not isinstance(parsed, dict):
        raise ValueError("candidate_binding_schema_mismatch")
    return copy.deepcopy(parsed)


def validate_candidate_binding_selection(
    *, selection: dict[str, Any], package: dict[str, Any]
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    _require_exact_keys(
        selection,
        {
            "schema_version",
            "package_id",
            "candidate_set_id",
            "candidate_set_hash",
            "relation_set_id",
            "relation_set_hash",
            "binding_results",
            "no_fact_results",
        },
        "$",
        errors,
    )
    if not isinstance(selection.get("binding_results"), list) or not isinstance(
        selection.get("no_fact_results"), list
    ):
        errors.append(_error("candidate_binding_schema_mismatch", "$.results"))
    else:
        if len(_dict_list(selection.get("binding_results"))) != len(
            selection["binding_results"]
        ) or len(_dict_list(selection.get("no_fact_results"))) != len(
            selection["no_fact_results"]
        ):
            errors.append(_error("candidate_binding_schema_mismatch", "$.results"))
    candidate_set = _object(package.get("source_value_candidate_set"))
    relation_set = _object(package.get("candidate_relation_set"))
    profile = _object(package.get("candidate_binding_profile"))
    candidates = {
        str(item.get("candidate_id") or ""): item
        for item in _dict_list(candidate_set.get("candidates"))
        if item.get("candidate_id")
    }
    relations = {
        str(item.get("relation_id") or ""): item
        for item in _dict_list(relation_set.get("relations"))
        if item.get("relation_id")
    }
    exact = {
        "schema_version": BINDING_OUTPUT_SCHEMA_VERSION,
        "package_id": package.get("package_id"),
        "candidate_set_id": candidate_set.get("candidate_set_id"),
        "candidate_set_hash": candidate_set.get("candidate_set_hash"),
        "relation_set_id": relation_set.get("relation_set_id"),
        "relation_set_hash": relation_set.get("relation_set_hash"),
    }
    for field, expected in exact.items():
        if selection.get(field) != expected:
            errors.append(_error("candidate_binding_contract_mismatch", field))
    selected_refs = _strings(
        _object(package.get("coverage_expectation")).get("selected_source_refs")
    )
    _validate_package_binding_contract(
        package=package,
        candidate_set=candidate_set,
        relation_set=relation_set,
        candidates=candidates,
        relations=relations,
        selected_refs=selected_refs,
        errors=errors,
    )
    accounted: list[str] = []
    for index, result in enumerate(_dict_list(selection.get("binding_results"))):
        path = f"$.binding_results[{index}]"
        _require_exact_keys(
            result,
            {
                "source_ref",
                "fact_type",
                "selected_bindings",
                "selected_relation_ids",
                "subtype_candidate",
                "confidence",
                "completeness",
                "uncertainty_codes",
                "resolved_ambiguity_group_refs",
            },
            path,
            errors,
        )
        for field in (
            "selected_bindings",
            "selected_relation_ids",
            "uncertainty_codes",
            "resolved_ambiguity_group_refs",
        ):
            if not isinstance(result.get(field), list):
                errors.append(_error("candidate_binding_schema_mismatch", f"{path}.{field}"))
        source_ref = str(result.get("source_ref") or "")
        accounted.append(source_ref)
        if source_ref not in selected_refs:
            errors.append(_error("candidate_binding_cross_package_scope", source_ref))
        fact_type = str(result.get("fact_type") or "")
        if fact_type == "unknown_source_row":
            if _dict_list(result.get("selected_bindings")):
                errors.append(_error("candidate_binding_unknown_has_bindings", path))
            if _strings(result.get("selected_relation_ids")):
                errors.append(_error("candidate_binding_unknown_has_relations", path))
            if not _strings(result.get("uncertainty_codes")):
                errors.append(_error("candidate_binding_unknown_reason_missing", path))
            if result.get("subtype_candidate") != "unknown":
                errors.append(_error("candidate_binding_subtype_forbidden", path))
            if result.get("confidence") not in {"low", "none"}:
                errors.append(_error("candidate_binding_confidence_forbidden", path))
            if result.get("completeness") not in {"uncertain", "blocked"}:
                errors.append(_error("candidate_binding_completeness_forbidden", path))
            allowed_unknown_ambiguity_refs = {
                str(item.get("ambiguity_group_ref"))
                for item in candidates.values()
                if item.get("ambiguity_group_ref")
                and str(item.get("row_ref") or "") == source_ref
            }
            resolved_unknown_ambiguity_refs = _strings(
                result.get("resolved_ambiguity_group_refs")
            )
            if (
                not set(resolved_unknown_ambiguity_refs)
                <= allowed_unknown_ambiguity_refs
                or len(resolved_unknown_ambiguity_refs)
                != len(set(resolved_unknown_ambiguity_refs))
            ):
                errors.append(
                    _error("candidate_binding_ambiguity_resolution_invalid", path)
                )
            continue
        if fact_type != profile.get("domain"):
            errors.append(_error("candidate_binding_fact_type_forbidden", fact_type))
            continue
        if result.get("subtype_candidate") not in _strings(profile.get("subtypes")):
            errors.append(_error("candidate_binding_subtype_forbidden", path))
        if result.get("confidence") not in {"high", "medium", "low", "none"}:
            errors.append(_error("candidate_binding_confidence_forbidden", path))
        if result.get("completeness") not in {
            "complete",
            "partial",
            "uncertain",
            "blocked",
        }:
            errors.append(_error("candidate_binding_completeness_forbidden", path))
        seen_roles: set[str] = set()
        seen_fields: set[str] = set()
        candidate_roles: dict[str, list[str]] = defaultdict(list)
        selected_candidate_ids: set[str] = set()
        allowed_ambiguity_refs = {
            str(item.get("ambiguity_group_ref"))
            for item in candidates.values()
            if item.get("ambiguity_group_ref")
            and str(item.get("row_ref") or "") == source_ref
        }
        resolved_ambiguity_refs = _strings(
            result.get("resolved_ambiguity_group_refs")
        )
        if (
            not set(resolved_ambiguity_refs) <= allowed_ambiguity_refs
            or len(resolved_ambiguity_refs) != len(set(resolved_ambiguity_refs))
        ):
            errors.append(_error("candidate_binding_ambiguity_resolution_invalid", path))
        for binding_index, binding in enumerate(_dict_list(result.get("selected_bindings"))):
            binding_path = f"{path}.selected_bindings[{binding_index}]"
            _require_exact_keys(
                binding,
                {"fact_field_path", "candidate_id", "semantic_role"},
                binding_path,
                errors,
            )
            candidate_id = str(binding.get("candidate_id") or "")
            role = str(binding.get("semantic_role") or "")
            field_path = str(binding.get("fact_field_path") or "")
            candidate = candidates.get(candidate_id)
            if candidate is None:
                errors.append(_error("candidate_binding_foreign_candidate_id", candidate_id))
                continue
            if str(candidate.get("row_ref") or "") != source_ref:
                errors.append(_error("candidate_binding_cross_row_candidate", candidate_id))
            if fact_type not in _strings(candidate.get("allowed_fact_types")):
                errors.append(_error("candidate_binding_candidate_domain_forbidden", candidate_id))
            spec = _object(_object(profile.get("roles")).get(role))
            if not spec or role not in _strings(candidate.get("allowed_semantic_roles")):
                errors.append(_error("candidate_binding_semantic_role_forbidden", role))
            else:
                if field_path != spec.get("fact_field_path"):
                    errors.append(_error("candidate_binding_fact_field_forbidden", field_path))
                if field_path not in _strings(candidate.get("allowed_fact_field_paths")):
                    errors.append(_error("candidate_binding_fact_field_forbidden", field_path))
                if candidate.get("candidate_kind") not in _strings(spec.get("candidate_kinds")):
                    errors.append(_error("candidate_binding_candidate_kind_forbidden", candidate_id))
            if role in seen_roles:
                errors.append(_error("candidate_binding_duplicate_role", role))
            if field_path in seen_fields:
                errors.append(_error("candidate_binding_duplicate_fact_field", field_path))
            seen_roles.add(role)
            seen_fields.add(field_path)
            candidate_roles[candidate_id].append(role)
            selected_candidate_ids.add(candidate_id)
            ambiguity_ref = str(candidate.get("ambiguity_group_ref") or "")
            if ambiguity_ref and ambiguity_ref not in _strings(
                result.get("resolved_ambiguity_group_refs")
            ):
                errors.append(_error("candidate_binding_ambiguity_unresolved", ambiguity_ref))
            if not _strings(candidate.get("source_value_refs")):
                errors.append(_error("candidate_binding_source_value_ref_missing", candidate_id))
            if not _strings(candidate.get("value_checksum_refs")):
                errors.append(_error("candidate_binding_checksum_ref_missing", candidate_id))
        for candidate_id, roles in candidate_roles.items():
            if len(roles) > 1 and not _candidate_reuse_allowed(profile, roles):
                errors.append(_error("candidate_binding_candidate_reuse_forbidden", candidate_id))
        for role in _strings(profile.get("required_roles")):
            if role not in seen_roles:
                errors.append(_error("candidate_binding_required_role_missing", role))
        for group in profile.get("required_role_groups") or []:
            group_roles = _strings(group)
            if group_roles and not set(group_roles) & seen_roles:
                errors.append(
                    _error("candidate_binding_required_role_group_missing", ":".join(group_roles))
                )
        selected_relations: list[dict[str, Any]] = []
        selected_relation_ids = _strings(result.get("selected_relation_ids"))
        if len(selected_relation_ids) != len(set(selected_relation_ids)):
            errors.append(_error("candidate_binding_duplicate_relation", path))
        for relation_id in selected_relation_ids:
            relation = relations.get(relation_id)
            if relation is None:
                errors.append(_error("candidate_binding_relation_not_found", relation_id))
                continue
            selected_relations.append(relation)
            if relation.get("validation_status") != "passed":
                errors.append(_error("candidate_binding_relation_invalid", relation_id))
            if _strings(relation.get("row_refs")) != [source_ref]:
                errors.append(_error("candidate_binding_cross_row_relation", relation_id))
            if fact_type not in _strings(relation.get("allowed_domains")):
                errors.append(_error("candidate_binding_relation_domain_forbidden", relation_id))
            relation_candidates = set(_strings(relation.get("candidate_ids")))
            if not relation_candidates & selected_candidate_ids:
                errors.append(
                    _error("candidate_binding_relation_selection_mismatch", relation_id)
                )
        for kind in _strings(profile.get("required_relation_kinds")):
            matches = [item for item in selected_relations if item.get("relation_kind") == kind]
            if not matches:
                errors.append(_error("candidate_binding_required_relation_missing", kind))
            elif any(
                len(_strings(item.get("candidate_ids")))
                < int(_object(item.get("cardinality")).get("minimum") or 0)
                for item in matches
            ):
                errors.append(_error("candidate_binding_relation_cardinality_invalid", kind))
            else:
                required_roles = _strings(
                    _object(profile.get("required_relation_role_sets")).get(kind)
                )
                required_candidate_ids = {
                    candidate_id
                    for candidate_id, roles in candidate_roles.items()
                    if set(roles) & set(required_roles)
                }
                if required_roles and not any(
                    required_candidate_ids <= set(_strings(item.get("candidate_ids")))
                    for item in matches
                ):
                    errors.append(
                        _error("candidate_binding_relation_selection_mismatch", kind)
                    )
        if result.get("completeness") == "complete" and package.get("allowed_issue_refs"):
            errors.append(_error("candidate_binding_issue_limited_completeness", source_ref))
    for index, item in enumerate(_dict_list(selection.get("no_fact_results"))):
        _require_exact_keys(
            item,
            {"source_ref", "reason_code"},
            f"$.no_fact_results[{index}]",
            errors,
        )
        source_ref = str(item.get("source_ref") or "")
        accounted.append(source_ref)
        if source_ref not in selected_refs:
            errors.append(_error("candidate_binding_cross_package_scope", source_ref))
        if item.get("reason_code") not in {
            "header_row",
            "blank_row",
            "layout_only",
            "repeated_header",
            "non_fact_annotation",
            "unsupported_source_shape",
        }:
            errors.append(_error("candidate_binding_no_fact_reason_forbidden", source_ref))
    if len(accounted) != len(set(accounted)):
        errors.append(_error("candidate_binding_duplicate_source_ownership", "$.coverage"))
    if set(accounted) != set(selected_refs):
        errors.append(_error("candidate_binding_coverage_gap", "$.coverage"))
    return {
        "schema_version": BINDING_VALIDATION_SCHEMA_VERSION,
        "package_id": package.get("package_id"),
        "candidate_set_id": candidate_set.get("candidate_set_id"),
        "relation_set_id": relation_set.get("relation_set_id"),
        "validator_status": "passed" if not errors else "failed",
        "errors_count": len(errors),
        "errors": errors,
        "error_code_counts": dict(sorted(Counter(item["code"] for item in errors).items())),
        "selected_refs_total": len(selected_refs),
        "accounted_refs_total": len(set(accounted) & set(selected_refs)),
    }


def _validate_package_binding_contract(
    *,
    package: dict[str, Any],
    candidate_set: dict[str, Any],
    relation_set: dict[str, Any],
    candidates: dict[str, dict[str, Any]],
    relations: dict[str, dict[str, Any]],
    selected_refs: list[str],
    errors: list[dict[str, str]],
) -> None:
    candidate_values = _dict_list(candidate_set.get("candidates"))
    relation_values = _dict_list(relation_set.get("relations"))
    candidate_ids = [str(item.get("candidate_id") or "") for item in candidate_values]
    relation_ids = [str(item.get("relation_id") or "") for item in relation_values]
    if candidate_ids != _strings(candidate_set.get("candidate_ids")) or len(candidate_ids) != len(
        set(candidate_ids)
    ):
        errors.append(_error("candidate_binding_candidate_id_list_mismatch", "candidate_set"))
    if relation_ids != _strings(relation_set.get("relation_ids")) or len(relation_ids) != len(
        set(relation_ids)
    ):
        errors.append(_error("candidate_binding_relation_id_list_mismatch", "relation_set"))
    if candidate_set.get("candidate_set_hash") != stable_digest(candidate_values, length=32):
        errors.append(_error("candidate_binding_candidate_set_integrity_failed", "candidate_set"))
    if relation_set.get("relation_set_hash") != stable_digest(relation_values, length=32):
        errors.append(_error("candidate_binding_relation_set_integrity_failed", "relation_set"))
    expected_scope = {
        "package_id": package.get("package_id"),
        "extractor_domain": package.get("extractor_domain"),
        "validation_status": "passed",
    }
    for field, expected in expected_scope.items():
        if candidate_set.get(field) != expected:
            errors.append(_error("candidate_binding_candidate_set_scope_invalid", field))
        if relation_set.get(field) != expected:
            errors.append(_error("candidate_binding_relation_set_scope_invalid", field))

    unit = copy.deepcopy(_object(package.get("source_unit")))
    unit["cells"] = copy.deepcopy(
        _object(unit.get("normalized_source_projection")).get("cells") or []
    )
    index_by_ref = {
        str(item.get("source_value_ref") or ""): item
        for item in _dict_list(unit.get("source_value_index"))
        if item.get("source_value_ref")
    }
    allowed_value_refs = set(_strings(package.get("allowed_source_value_refs")))
    selected_ref_set = set(selected_refs)
    for candidate_id, candidate in candidates.items():
        row_ref = str(candidate.get("row_ref") or "")
        source_value_refs = _strings(candidate.get("source_value_refs"))
        if row_ref not in selected_ref_set or len(source_value_refs) != 1:
            errors.append(_error("candidate_binding_candidate_scope_invalid", candidate_id))
            continue
        source_value_ref = source_value_refs[0]
        source_index = index_by_ref.get(source_value_ref)
        if source_value_ref not in allowed_value_refs or source_index is None:
            errors.append(_error("candidate_binding_candidate_scope_invalid", candidate_id))
            continue
        indexed_row_ref = str(source_index.get("row_ref") or "")
        if indexed_row_ref and indexed_row_ref != row_ref:
            errors.append(_error("candidate_binding_candidate_scope_invalid", candidate_id))
        expected_checksums = _strings([source_index.get("value_checksum_ref")])
        if _strings(candidate.get("value_checksum_refs")) != expected_checksums:
            errors.append(_error("candidate_binding_candidate_checksum_mismatch", candidate_id))
        try:
            reproduced = reproduce_normalized_value(
                unit,
                source_value_ref,
                str(candidate.get("normalization_kind") or ""),
            )
        except ValueError:
            errors.append(_error("candidate_binding_candidate_value_unreproducible", candidate_id))
        else:
            if str(candidate.get("normalized_value")) != reproduced:
                errors.append(
                    _error("candidate_binding_candidate_value_unreproducible", candidate_id)
                )

    for relation_id, relation in relations.items():
        relation_candidate_ids = _strings(relation.get("candidate_ids"))
        minimum = int(_object(relation.get("cardinality")).get("minimum") or 0)
        maximum = int(_object(relation.get("cardinality")).get("maximum") or 0)
        if (
            len(relation_candidate_ids) < minimum
            or (maximum and len(relation_candidate_ids) > maximum)
        ):
            errors.append(_error("candidate_binding_relation_cardinality_invalid", relation_id))
        missing = [item for item in relation_candidate_ids if item not in candidates]
        if missing:
            errors.append(_error("candidate_binding_relation_candidate_not_found", relation_id))
            continue
        candidate_rows = {
            str(candidates[item].get("row_ref") or "") for item in relation_candidate_ids
        }
        if len(candidate_rows) != 1 or candidate_rows != set(_strings(relation.get("row_refs"))):
            errors.append(_error("candidate_binding_relation_scope_invalid", relation_id))


def materialize_candidate_binding_selection(
    *, selection: dict[str, Any], package: dict[str, Any]
) -> dict[str, Any]:
    candidate_set = _object(package.get("source_value_candidate_set"))
    candidates = {
        str(item.get("candidate_id") or ""): item
        for item in _dict_list(candidate_set.get("candidates"))
    }
    facts = []
    for result in _dict_list(selection.get("binding_results")):
        source_ref = str(result.get("source_ref") or "")
        fact_type = str(result.get("fact_type") or "")
        normalized = {field: None for field in NORMALIZED_VALUE_FIELDS}
        original = {field: [] for field in NORMALIZED_VALUE_FIELDS}
        extracted = _default_extracted_fields(
            fact_type=fact_type,
            subtype=str(result.get("subtype_candidate") or "unknown"),
            uncertainty_codes=_strings(result.get("uncertainty_codes")),
        )
        for binding in _dict_list(result.get("selected_bindings")):
            candidate = candidates[str(binding["candidate_id"])]
            field_path = str(binding.get("fact_field_path") or "")
            if field_path.startswith("normalized_values."):
                field = field_path.split(".", 1)[1]
                if field in normalized:
                    normalized[field] = str(candidate.get("normalized_value"))
                    original[field] = _strings(candidate.get("source_value_refs"))
            else:
                _materialize_extracted_binding(
                    extracted=extracted,
                    fact_type=fact_type,
                    field_path=field_path,
                    candidate=candidate,
                )
        facts.append(
            {
                "fact_id": "pending",
                "fact_type": fact_type,
                "fact_subtype": str(result.get("subtype_candidate") or "unknown"),
                "document_ref": package.get("document_ref"),
                "extraction_package_ref": package.get("package_artifact_ref"),
                "source_unit_ref": _object(package.get("source_unit")).get("unit_id"),
                "source_location": {"row_ref": source_ref},
                "extracted_fields": extracted,
                "normalized_values": normalized,
                "original_value_refs": original,
                "date": None,
                "amount": None,
                "currency": None,
                "quantity": None,
                "instrument": None,
                "confidence": result.get("confidence"),
                "completeness": result.get("completeness"),
                "evidence_refs": [source_ref],
                "linked_issue_refs": [],
                "issue_impact": {},
                "extraction_warnings": _strings(result.get("uncertainty_codes")),
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
    return {
        "facts": facts,
        "coverage": {
            "no_fact_results": copy.deepcopy(
                _dict_list(selection.get("no_fact_results"))
            )
        },
    }


def _default_extracted_fields(
    *, fact_type: str, subtype: str, uncertainty_codes: list[str]
) -> dict[str, Any]:
    if fact_type == "trade_operation":
        return {"operation_type_candidate": subtype, "source_visible_direction_refs": []}
    if fact_type == "income":
        return {"income_type_candidate": subtype, "source_country_candidate": None, "source_country_value_refs": []}
    if fact_type == "withholding_tax":
        return {"withholding_type_candidate": subtype, "source_country_candidate": None, "related_income_source_refs": []}
    if fact_type == "fee_commission":
        return {"fee_type_candidate": subtype, "related_operation_source_refs": []}
    if fact_type == "cash_movement":
        return {"movement_type_candidate": subtype, "description_safe_label": None, "description_value_refs": []}
    if fact_type == "currency_fx":
        return {"fx_fact_kind": subtype}
    if fact_type == "position_snapshot":
        return {"position_kind_candidate": subtype}
    if fact_type == "document_summary_evidence":
        return {"summary_kind_candidate": subtype, "source_provided": True}
    return {"unknown_reason_codes": uncertainty_codes or ["candidate_binding_unknown"]}


def _materialize_extracted_binding(
    *, extracted: dict[str, Any], fact_type: str, field_path: str, candidate: dict[str, Any]
) -> None:
    refs = _strings(candidate.get("source_value_refs"))
    value = str(candidate.get("normalized_value") or "")
    if field_path.endswith("description_value_refs"):
        extracted["description_value_refs"] = refs
        extracted["description_safe_label"] = value[:64] or None
    elif field_path.endswith("source_country_value_refs"):
        extracted["source_country_value_refs"] = refs
        extracted["source_country_candidate"] = value[:64] or None
    elif field_path.endswith("source_visible_direction_refs"):
        extracted["source_visible_direction_refs"] = refs
    elif fact_type == "cash_movement" and field_path.endswith("movement_type_candidate"):
        extracted["movement_type_candidate"] = _safe_subtype(value, {"deposit", "withdrawal", "credit", "debit"})
    elif fact_type == "income" and field_path.endswith("income_type_candidate"):
        extracted["income_type_candidate"] = _safe_subtype(value, {"dividend", "coupon", "interest", "sale_proceeds", "other"})
    elif fact_type == "fee_commission" and field_path.endswith("fee_type_candidate"):
        extracted["fee_type_candidate"] = _safe_subtype(value, {"broker_commission", "exchange_fee", "custody_fee", "other"})
    elif fact_type == "trade_operation" and field_path.endswith("operation_type_candidate"):
        extracted["operation_type_candidate"] = _safe_subtype(value, {"buy", "sell", "redemption", "transfer", "corporate_action"})


def _safe_subtype(value: str, allowed: set[str]) -> str:
    token = value.strip().lower()
    return token if token in allowed else "unknown"


def _candidate_reuse_allowed(profile: dict[str, Any], roles: list[str]) -> bool:
    reuse = _object(profile.get("candidate_reuse"))
    return all(bool(reuse.get(role)) for role in roles)


def _require_exact_keys(
    value: dict[str, Any],
    expected: set[str],
    path: str,
    errors: list[dict[str, str]],
) -> None:
    if set(value) != expected:
        errors.append(_error("candidate_binding_schema_mismatch", path))


def _strict_object(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": copy.deepcopy(properties),
        "required": list(properties),
    }


def _restricted_array(values: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "type": "array",
        "items": {"type": "string"},
        "maxItems": len(values),
    }
    if values:
        result["items"]["enum"] = sorted(set(values))
    return result


def _error(code: str, subject: Any) -> dict[str, str]:
    return {"code": code, "subject": str(subject or "")[:240]}


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)] if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in value or [] if item is not None and str(item)] if isinstance(value, list) else []
