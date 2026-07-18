from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any

from .artifact_models import ArtifactAccessContext, ArtifactStoreError, utc_now_iso
from .artifact_resolver import ArtifactResolver
from .contracts import stable_digest
from .gate1_public_contracts import reproduce_normalized_value
from .gate2_source_fact_contracts import (
    COMPLETENESS_VALUES,
    FACT_TYPES,
    NORMALIZED_VALUE_FIELDS,
    PACKAGE_SCHEMA_VERSION,
    SOURCE_FACTS_SCHEMA_VERSION,
    VALIDATION_SCHEMA_VERSION,
    Gate2ManagedPrompt,
    source_facts_json_schema,
)
from .gate2_domain_packages import DOMAIN_PACKAGE_SCHEMA_VERSION
from .gate2_model_contracts import GATE2_STRICT_STRUCTURED_OUTPUT_MODES


FACTORY_REQUIRED = (
    "Gate2SourceFactValidatorFactory.create is the only production source-fact validator entrypoint"
)
FORBIDDEN = (
    "Runners and pipes must not promote model candidates or mint validated fact ids outside the deterministic validator"
)

FORBIDDEN_OUTPUT_FIELDS = {
    "raw_text",
    "full_text",
    "raw_rows",
    "rows",
    "filename",
    "raw_filename",
    "file_id",
    "openwebui_file_id",
    "private_path",
    "path",
    "account_number",
    "personal_data",
    "secret",
    "env_value",
}
FORBIDDEN_GATE3_FIELDS = {
    "profit",
    "profit_loss",
    "gain_loss",
    "cost_basis",
    "tax_base",
    "tax_amount_calculated",
    "tax_calculation",
    "deductible_amount",
    "deductibility",
    "declaration_field",
    "declaration_mapping",
    "filing_readiness",
    "xlsx",
    "xls",
    "matched_lot_refs",
    "canonical_duplicate_ref",
    "fx_lookup",
    "computed_conversion",
}
NORMALIZATION_KIND_BY_FIELD = {
    "date": "iso_date_exact",
    "amount": "decimal_dot",
    "currency": "currency_code_visible",
    "quantity": "decimal_dot",
    "rate": "decimal_dot",
    "converted_amount": "decimal_dot",
    "identifier": "trimmed_text",
    "label": "trimmed_text",
}


@dataclass(frozen=True)
class Gate2SourceFactValidationOutcome:
    validation: dict[str, Any]
    finalized_source_facts: dict[str, Any] | None


class Gate2SourceFactValidatorFactory:
    def __init__(
        self,
        *,
        resolver: ArtifactResolver,
        context: ArtifactAccessContext,
    ) -> None:
        self.resolver = resolver
        self.context = context

    def create(self) -> "Gate2SourceFactValidator":
        return Gate2SourceFactValidator(resolver=self.resolver, context=self.context)


class Gate2SourceFactValidator:
    def __init__(self, *, resolver: ArtifactResolver, context: ArtifactAccessContext) -> None:
        self.resolver = resolver
        self.context = context

    def validate(
        self,
        *,
        candidate: dict[str, Any],
        package: dict[str, Any],
        package_artifact_ref: str,
        raw_output_artifact_ref: str,
        validation_artifact_ref: str,
        prompt: Gate2ManagedPrompt,
        model_id: str,
        expected_candidate_audit: dict[str, Any] | None = None,
    ) -> Gate2SourceFactValidationOutcome:
        errors: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        privacy_errors: list[dict[str, str]] = []
        boundary_errors: list[dict[str, str]] = []

        self._validate_artifact_refs(
            package=package,
            package_artifact_ref=package_artifact_ref,
            raw_output_artifact_ref=raw_output_artifact_ref,
            prompt=prompt,
            model_id=model_id,
            errors=errors,
        )
        if expected_candidate_audit is not None:
            package = copy.deepcopy(package)
            package["expected_candidate_audit"] = copy.deepcopy(
                expected_candidate_audit
            )
        _validate_schema_subset(
            candidate,
            source_facts_json_schema(),
            path="$",
            errors=errors,
        )
        privacy_errors.extend(_forbidden_field_errors(candidate, FORBIDDEN_OUTPUT_FIELDS, "source_fact_private_field_forbidden"))
        privacy_errors.extend(_long_string_errors(candidate))
        boundary_errors.extend(_forbidden_field_errors(candidate, FORBIDDEN_GATE3_FIELDS, "source_fact_gate3_boundary_forbidden"))

        self._validate_top_scope(
            candidate=candidate,
            package=package,
            package_artifact_ref=package_artifact_ref,
            errors=errors,
        )
        self._validate_audit(
            audit=_object(candidate.get("extraction_audit")),
            expected=_object(package.get("expected_candidate_audit")),
            prompt=prompt,
            model_id=model_id,
            path="$.extraction_audit",
            errors=errors,
        )

        accepted_fact_ids: list[str] = []
        deterministic_ids: set[str] = set()
        fact_covered_refs: set[str] = set()
        facts = _dict_list(candidate.get("facts"))
        for index, fact in enumerate(facts):
            path = f"$.facts[{index}]"
            deterministic_id = self._validate_fact(
                fact=fact,
                path=path,
                package=package,
                package_artifact_ref=package_artifact_ref,
                prompt=prompt,
                model_id=model_id,
                errors=errors,
                privacy_errors=privacy_errors,
                boundary_errors=boundary_errors,
                fact_covered_refs=fact_covered_refs,
            )
            if deterministic_id:
                if deterministic_id in deterministic_ids:
                    errors.append(_error("source_fact_duplicate_id", path))
                deterministic_ids.add(deterministic_id)
                accepted_fact_ids.append(deterministic_id)

        self._validate_coverage(
            candidate=candidate,
            package=package,
            fact_covered_refs=fact_covered_refs,
            errors=errors,
        )
        self._validate_issue_linkage_summary(
            candidate=candidate,
            package=package,
            facts=facts,
            errors=errors,
        )

        errors.extend(privacy_errors)
        errors.extend(boundary_errors)
        privacy_status = "passed" if not privacy_errors else "failed"
        boundary_status = "passed" if not boundary_errors else "failed"
        validator_status = "passed" if not errors else (
            "privacy_failed" if privacy_errors else "failed"
        )
        finalized = None
        if validator_status == "passed":
            finalized = _finalize_candidate(
                candidate=candidate,
                validation_artifact_ref=validation_artifact_ref,
                raw_output_artifact_ref=raw_output_artifact_ref,
                deterministic_fact_ids=accepted_fact_ids,
            )

        coverage = _object(candidate.get("coverage"))
        validation = {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "validation_id": f"sfval_{stable_digest([validation_artifact_ref], length=20)}",
            "extraction_run_id": package.get("extraction_run_id"),
            "package_ref": package_artifact_ref,
            "document_ref": package.get("document_ref"),
            "source_unit_ref": _object(package.get("source_unit")).get("unit_id"),
            "validator_status": validator_status,
            "accepted_fact_ids": accepted_fact_ids if finalized is not None else [],
            "rejected_fact_ids": [] if finalized is not None else [
                str(item.get("fact_id") or f"candidate_{index + 1}")
                for index, item in enumerate(facts)
            ],
            "errors": errors,
            "warnings": warnings,
            "coverage": {
                "selected_total": len(_string_list(coverage.get("selected_source_refs"))),
                "fact_covered_total": len(_string_list(coverage.get("fact_covered_refs"))),
                "no_fact_total": len(_dict_list(coverage.get("no_fact_results"))),
                "rejected_total": len(_string_list(coverage.get("rejected_refs"))),
                "pending_total": len(_string_list(coverage.get("pending_refs"))),
                "coverage_status": coverage.get("coverage_status"),
            },
            "issue_carry_forward": {
                "allowed_issue_refs": _string_list(package.get("allowed_issue_refs")),
                "issue_linked_facts_total": sum(1 for fact in facts if fact.get("linked_issue_refs")),
            },
            "privacy_status": privacy_status,
            "boundary_status": boundary_status,
            "prompt_schema_model_audit": {
                "prompt_ref": prompt.prompt_ref,
                "prompt_hash": prompt.hash,
                "output_schema_id": prompt.output_schema_id,
                "output_schema_version": prompt.output_schema_version,
                "model_id": model_id,
                "structured_output_mode": _object(candidate.get("extraction_audit")).get("structured_output_mode"),
            },
            "validated_at": utc_now_iso(),
        }
        return Gate2SourceFactValidationOutcome(
            validation=validation,
            finalized_source_facts=finalized,
        )

    def _validate_artifact_refs(
        self,
        *,
        package: dict[str, Any],
        package_artifact_ref: str,
        raw_output_artifact_ref: str,
        prompt: Gate2ManagedPrompt,
        model_id: str,
        errors: list[dict[str, str]],
    ) -> None:
        expected_package_type = (
            DOMAIN_PACKAGE_SCHEMA_VERSION
            if package.get("schema_version") == DOMAIN_PACKAGE_SCHEMA_VERSION
            else PACKAGE_SCHEMA_VERSION
        )
        expected_types = {
            package_artifact_ref: expected_package_type,
            raw_output_artifact_ref: "broker_reports_source_fact_raw_output_v0",
            str(_object(package.get("source_unit")).get("private_slice_artifact_ref") or ""): None,
        }
        for artifact_ref, expected_type in expected_types.items():
            if not artifact_ref:
                errors.append(_error("source_fact_provenance_missing", "artifact_ref"))
                continue
            try:
                resolved = self.resolver.resolve(artifact_ref, self.context)
            except ArtifactStoreError as exc:
                errors.append(_error("source_fact_ref_cross_scope", f"{artifact_ref}:{exc.code}"))
                continue
            record = resolved["record"]
            if expected_type and record.artifact_type != expected_type:
                errors.append(_error("source_fact_scope_mismatch", artifact_ref))
            if artifact_ref == package_artifact_ref and resolved["payload"] != package:
                errors.append(_error("source_fact_scope_mismatch", package_artifact_ref))
            if artifact_ref == raw_output_artifact_ref:
                raw = _object(resolved["payload"])
                repair_attempt_count = int(raw.get("repair_attempt_count") or 0)
                package_schema_hash_field = (
                    "repair_package_response_schema_hash"
                    if repair_attempt_count == 1
                    else "package_response_schema_hash"
                )
                raw_expected = {
                    "schema_version": "broker_reports_source_fact_raw_output_v0",
                    "extraction_run_id": package.get("extraction_run_id"),
                    "package_ref": package_artifact_ref,
                    "document_ref": package.get("document_ref"),
                    "source_unit_ref": _object(package.get("source_unit")).get("unit_id"),
                    "model_call_status": "passed",
                    "structured_output_mode": "openwebui_response_format_json_schema",
                    "response_format_type": "json_schema",
                    "response_format_schema_mode": "strict_json_schema",
                    "fallback_used": False,
                    "repair_attempt_count": repair_attempt_count,
                    "extraction_attempt_ordinal": repair_attempt_count + 1,
                    "provider_response_schema_hash": _object(
                        package.get("output_schema")
                    ).get("provider_response_schema_hash"),
                    "package_response_schema_hash": _object(
                        package.get("output_schema")
                    ).get(package_schema_hash_field),
                    "provider_union_keyword": "anyOf",
                    "model_id": model_id,
                }
                for field, value in raw_expected.items():
                    if (
                        field == "structured_output_mode"
                        and raw.get(field) in GATE2_STRICT_STRUCTURED_OUTPUT_MODES
                    ):
                        continue
                    if raw.get(field) != value:
                        code = (
                            "source_fact_structured_output_required"
                            if field
                            in {
                                "structured_output_mode",
                                "response_format_type",
                                "response_format_schema_mode",
                                "fallback_used",
                                "repair_attempt_count",
                            }
                            else "source_fact_prompt_audit_mismatch"
                        )
                        errors.append(_error(code, f"raw_output.{field}"))
                snapshot = _object(raw.get("prompt_snapshot"))
                if (
                    snapshot.get("prompt_ref") != prompt.prompt_ref
                    or snapshot.get("prompt_hash") != prompt.hash
                    or snapshot.get("output_schema_hash")
                    != _object(package.get("output_schema")).get("output_schema_hash")
                    or snapshot.get("provider_response_schema_hash")
                    != _object(package.get("output_schema")).get(
                        "provider_response_schema_hash"
                    )
                    or snapshot.get("provider_union_keyword") != "anyOf"
                ):
                    errors.append(_error("source_fact_prompt_audit_mismatch", "raw_output.prompt_snapshot"))
            if expected_type is None and record.artifact_type not in {
                "private_normalized_table_slice_v0",
                "private_normalized_text_slice_v0",
                "private_normalized_source_unit_v0",
                "broker_reports_normalized_table_projection_v0",
            }:
                errors.append(_error("source_fact_scope_mismatch", artifact_ref))

    def _validate_top_scope(
        self,
        *,
        candidate: dict[str, Any],
        package: dict[str, Any],
        package_artifact_ref: str,
        errors: list[dict[str, str]],
    ) -> None:
        expected = {
            "schema_version": SOURCE_FACTS_SCHEMA_VERSION,
            "source_facts_set_id": package.get("expected_source_facts_set_id"),
            "extraction_run_id": package.get("extraction_run_id"),
            "normalization_run_id": package.get("normalization_run_id"),
            "case_id": package.get("case_id"),
            "package_refs": [package_artifact_ref],
            "document_refs": [package.get("document_ref")],
            "validation_ref": None,
            "validator_status": "pending",
        }
        for field, value in expected.items():
            if candidate.get(field) != value:
                errors.append(_error("source_fact_scope_mismatch", f"$.{field}"))

    def _validate_fact(
        self,
        *,
        fact: dict[str, Any],
        path: str,
        package: dict[str, Any],
        package_artifact_ref: str,
        prompt: Gate2ManagedPrompt,
        model_id: str,
        errors: list[dict[str, str]],
        privacy_errors: list[dict[str, str]],
        boundary_errors: list[dict[str, str]],
        fact_covered_refs: set[str],
    ) -> str | None:
        source_unit = _object(package.get("source_unit"))
        expected_scope = {
            "document_ref": package.get("document_ref"),
            "extraction_package_ref": package_artifact_ref,
            "source_unit_ref": source_unit.get("unit_id"),
            "validator_status": "pending",
            "validation_ref": None,
        }
        for field, value in expected_scope.items():
            if fact.get(field) != value:
                errors.append(_error("source_fact_scope_mismatch", f"{path}.{field}"))
        if fact.get("fact_id") != "pending":
            errors.append(_error("source_fact_duplicate_id", f"{path}.fact_id"))
        fact_type = str(fact.get("fact_type") or "")
        if fact_type not in FACT_TYPES:
            errors.append(_error("source_fact_schema_mismatch", f"{path}.fact_type"))
        allowed_fact_types = set(_string_list(package.get("allowed_fact_types")))
        if allowed_fact_types and fact_type not in allowed_fact_types:
            errors.append(
                _error("source_fact_domain_fact_type_forbidden", f"{path}.fact_type")
            )
        hint_by_row_ref = {
            str(item.get("row_ref") or ""): str(item.get("fact_type_hint") or "")
            for item in _dict_list(
                _object(source_unit.get("model_source_projection")).get("rows")
            )
            if item.get("row_ref") and item.get("fact_type_hint")
        }
        row_ref = str(_object(fact.get("source_location")).get("row_ref") or "")
        if hint_by_row_ref.get(row_ref) and hint_by_row_ref[row_ref] != fact_type:
            errors.append(_error("source_fact_type_hint_mismatch", f"{path}.fact_type"))

        allowed_evidence = set(_string_list(package.get("allowed_evidence_refs")))
        evidence_refs = _string_list(fact.get("evidence_refs"))
        if not evidence_refs:
            errors.append(_error("source_fact_provenance_missing", f"{path}.evidence_refs"))
        if not set(evidence_refs) <= allowed_evidence:
            errors.append(_error("source_fact_unknown_evidence_ref", f"{path}.evidence_refs"))
        selected_refs = set(_string_list(_object(package.get("coverage_expectation")).get("selected_source_refs")))
        covered = set(evidence_refs) & selected_refs
        if not covered:
            errors.append(_error("source_fact_provenance_missing", f"{path}.selected_source_ref"))
        fact_covered_refs.update(covered)
        self._validate_source_location(
            location=_object(fact.get("source_location")),
            package=package,
            evidence_refs=set(evidence_refs),
            path=f"{path}.source_location",
            errors=errors,
        )

        pseudo_slice = _package_source_slice(package)
        allowed_values = set(_string_list(package.get("allowed_source_value_refs")))
        original_refs = _object(fact.get("original_value_refs"))
        normalized_values = _object(fact.get("normalized_values"))
        all_original_refs: list[str] = []
        for field in NORMALIZED_VALUE_FIELDS:
            refs = _string_list(original_refs.get(field))
            all_original_refs.extend(refs)
            if not set(refs) <= allowed_values:
                errors.append(_error("source_fact_unknown_value_ref", f"{path}.original_value_refs.{field}"))
            value = normalized_values.get(field)
            if value is None:
                if refs:
                    errors.append(_error("source_fact_invented_value", f"{path}.normalized_values.{field}"))
                continue
            if len(refs) != 1:
                errors.append(_error("source_fact_normalized_value_unreproducible", f"{path}.normalized_values.{field}"))
                continue
            try:
                reproduced = reproduce_normalized_value(
                    pseudo_slice,
                    refs[0],
                    NORMALIZATION_KIND_BY_FIELD[field],
                )
            except ValueError:
                errors.append(_error("source_fact_normalized_value_unreproducible", f"{path}.normalized_values.{field}"))
                continue
            if str(value) != reproduced:
                errors.append(_error("source_fact_normalized_value_unreproducible", f"{path}.normalized_values.{field}"))
        if not all_original_refs:
            errors.append(_error("source_fact_provenance_missing", f"{path}.original_value_refs"))

        extracted = _object(fact.get("extracted_fields"))
        for field in (
            "source_visible_direction_refs",
            "source_country_value_refs",
            "description_value_refs",
        ):
            if not set(_string_list(extracted.get(field))) <= allowed_values:
                errors.append(
                    _error(
                        "source_fact_unknown_value_ref",
                        f"{path}.extracted_fields.{field}",
                    )
                )
        for field in (
            "related_income_source_refs",
            "related_operation_source_refs",
        ):
            if not set(_string_list(extracted.get(field))) <= allowed_evidence:
                errors.append(
                    _error(
                        "source_fact_unknown_evidence_ref",
                        f"{path}.extracted_fields.{field}",
                    )
                )

        self._validate_common_values(
            fact=fact,
            path=path,
            normalized_values=normalized_values,
            original_refs=original_refs,
            errors=errors,
        )
        self._validate_type_requirements(fact=fact, path=path, errors=errors)
        self._validate_issue_policy(fact=fact, package=package, path=path, errors=errors)
        self._validate_audit(
            audit=_object(fact.get("extraction_audit")),
            expected=_object(package.get("expected_candidate_audit")),
            prompt=prompt,
            model_id=model_id,
            path=f"{path}.extraction_audit",
            errors=errors,
        )
        privacy_errors.extend(_forbidden_field_errors(fact, FORBIDDEN_OUTPUT_FIELDS, "source_fact_private_field_forbidden", prefix=path))
        boundary_errors.extend(_forbidden_field_errors(fact, FORBIDDEN_GATE3_FIELDS, "source_fact_gate3_boundary_forbidden", prefix=path))

        primary_ref = sorted(covered)[0] if covered else "missing"
        deterministic_id = f"sf_{stable_digest([package.get('extraction_run_id'), package.get('document_ref'), source_unit.get('unit_id'), primary_ref, fact_type, sorted(set(all_original_refs))], length=24)}"
        return deterministic_id

    def _validate_source_location(
        self,
        *,
        location: dict[str, Any],
        package: dict[str, Any],
        evidence_refs: set[str],
        path: str,
        errors: list[dict[str, str]],
    ) -> None:
        unit = _object(package.get("source_unit"))
        expected = {
            "private_slice_artifact_ref": unit.get("private_slice_artifact_ref"),
            "slice_ref": unit.get("slice_ref"),
            "parser_ref": unit.get("parser_ref"),
            "source_checksum_ref": unit.get("source_checksum_ref"),
        }
        for field, value in expected.items():
            if location.get(field) != value:
                errors.append(_error("source_fact_scope_mismatch", f"{path}.{field}"))
        location_refs = set(_string_list(location.get("cell_refs"))) | set(
            _string_list(location.get("text_segment_refs"))
        )
        for field in ("page_ref", "section_ref", "table_ref", "row_ref", "row_range_ref"):
            if location.get(field):
                location_refs.add(str(location[field]))
        if not location_refs or not location_refs <= evidence_refs:
            errors.append(_error("source_fact_provenance_missing", path))

    def _validate_common_values(
        self,
        *,
        fact: dict[str, Any],
        path: str,
        normalized_values: dict[str, Any],
        original_refs: dict[str, Any],
        errors: list[dict[str, str]],
    ) -> None:
        mappings = {
            "date": ("value", "date"),
            "amount": ("value_decimal", "amount"),
            "currency": ("code", "currency"),
            "quantity": ("value_decimal", "quantity"),
        }
        for object_field, (value_field, normalized_field) in mappings.items():
            item = fact.get(object_field)
            expected_value = normalized_values.get(normalized_field)
            expected_refs = _string_list(original_refs.get(normalized_field))
            if expected_value is None:
                if item is not None:
                    errors.append(_error("source_fact_invented_value", f"{path}.{object_field}"))
                continue
            if not isinstance(item, dict):
                errors.append(_error("source_fact_missing_field", f"{path}.{object_field}"))
                continue
            if str(item.get(value_field)) != str(expected_value):
                errors.append(_error("source_fact_normalized_value_unreproducible", f"{path}.{object_field}.{value_field}"))
            if _string_list(item.get("original_value_refs")) != expected_refs:
                errors.append(_error("source_fact_unknown_value_ref", f"{path}.{object_field}.original_value_refs"))
        instrument = fact.get("instrument")
        identifier_value = normalized_values.get("identifier")
        identifier_refs = _string_list(original_refs.get("identifier"))
        if identifier_value is None:
            if instrument is not None:
                errors.append(_error("source_fact_invented_value", f"{path}.instrument"))
        elif not isinstance(instrument, dict):
            errors.append(_error("source_fact_missing_field", f"{path}.instrument"))
        else:
            identifiers = _dict_list(instrument.get("identifiers"))
            if len(identifiers) != 1:
                errors.append(_error("source_fact_missing_field", f"{path}.instrument.identifiers"))
            elif (
                str(identifiers[0].get("identifier_value")) != str(identifier_value)
                or _string_list(identifiers[0].get("original_value_refs")) != identifier_refs
            ):
                errors.append(_error("source_fact_normalized_value_unreproducible", f"{path}.instrument"))

    def _validate_type_requirements(
        self,
        *,
        fact: dict[str, Any],
        path: str,
        errors: list[dict[str, str]],
    ) -> None:
        fact_type = str(fact.get("fact_type") or "")
        normalized = _object(fact.get("normalized_values"))
        extracted = _object(fact.get("extracted_fields"))
        if fact_type == "trade_operation" and not any(
            normalized.get(field) is not None for field in ("date", "amount", "quantity", "identifier")
        ):
            errors.append(_error("source_fact_missing_field", f"{path}.trade_visible_value"))
        elif fact_type == "income" and normalized.get("amount") is None:
            errors.append(_error("source_fact_missing_field", f"{path}.normalized_values.amount"))
        elif fact_type == "withholding_tax" and (
            normalized.get("amount") is None or normalized.get("currency") is None
        ):
            errors.append(_error("source_fact_missing_field", f"{path}.withholding_amount_currency"))
        elif fact_type == "fee_commission" and normalized.get("amount") is None:
            errors.append(_error("source_fact_missing_field", f"{path}.normalized_values.amount"))
        elif fact_type == "cash_movement" and normalized.get("amount") is None:
            errors.append(_error("source_fact_missing_field", f"{path}.normalized_values.amount"))
        elif fact_type == "currency_fx" and not any(
            normalized.get(field) is not None for field in ("amount", "rate", "converted_amount")
        ):
            errors.append(_error("source_fact_missing_field", f"{path}.fx_visible_value"))
        elif fact_type == "position_snapshot" and not any(
            normalized.get(field) is not None for field in ("date", "quantity", "amount", "identifier")
        ):
            errors.append(_error("source_fact_missing_field", f"{path}.position_visible_value"))
        elif fact_type == "document_summary_evidence" and (
            extracted.get("source_provided") is not True
            or not any(normalized.get(field) is not None for field in NORMALIZED_VALUE_FIELDS)
        ):
            errors.append(_error("source_fact_missing_field", f"{path}.source_summary_value"))
        elif fact_type == "unknown_source_row":
            if not _string_list(extracted.get("unknown_reason_codes")):
                errors.append(_error("source_fact_missing_field", f"{path}.unknown_reason_codes"))
            if fact.get("confidence") not in {"low", "none"}:
                errors.append(_error("source_fact_completeness_overstated", f"{path}.confidence"))
            if fact.get("completeness") not in {"uncertain", "blocked"}:
                errors.append(_error("source_fact_completeness_overstated", f"{path}.completeness"))

    def _validate_issue_policy(
        self,
        *,
        fact: dict[str, Any],
        package: dict[str, Any],
        path: str,
        errors: list[dict[str, str]],
    ) -> None:
        expected = _expected_issue_policy(package)
        if _string_list(fact.get("linked_issue_refs")) != expected["linked_issue_refs"]:
            errors.append(_error("source_fact_issue_not_carried", f"{path}.linked_issue_refs"))
        if _object(fact.get("issue_impact")) != expected["issue_impact"]:
            errors.append(_error("source_fact_issue_not_carried", f"{path}.issue_impact"))
        completeness = fact.get("completeness")
        downstream = _object(fact.get("downstream_use"))
        if expected["issue_impact"]["blocks_fact_issue_refs"]:
            if completeness != "blocked" or downstream.get("downstream_usable") is not False:
                errors.append(_error("source_fact_completeness_overstated", path))
        elif expected["issue_impact"]["limits_confirmation_issue_refs"] and completeness == "complete":
            errors.append(_error("source_fact_completeness_overstated", f"{path}.completeness"))
        if downstream.get("cross_document_consolidation_allowed") is not False:
            errors.append(_error("source_fact_duplicate_resolution_forbidden", f"{path}.downstream_use"))
        if downstream.get("tax_calculation_allowed") is not False:
            errors.append(_error("source_fact_tax_conclusion_forbidden", f"{path}.downstream_use"))
        if downstream.get("declaration_mapping_allowed") is not False:
            errors.append(_error("source_fact_declaration_mapping_forbidden", f"{path}.downstream_use"))
        if completeness not in COMPLETENESS_VALUES:
            errors.append(_error("source_fact_schema_mismatch", f"{path}.completeness"))

    def _validate_audit(
        self,
        *,
        audit: dict[str, Any],
        expected: dict[str, Any],
        prompt: Gate2ManagedPrompt,
        model_id: str,
        path: str,
        errors: list[dict[str, str]],
    ) -> None:
        expected_values = copy.deepcopy(expected)
        expected_values.update(
            {
                "prompt_ref": prompt.prompt_ref,
                "prompt_hash": prompt.hash,
                "model_id": model_id,
                "raw_output_artifact_ref": None,
            }
        )
        for field, value in expected_values.items():
            if audit.get(field) != value:
                errors.append(_error("source_fact_prompt_audit_mismatch", f"{path}.{field}"))
        if audit.get("structured_output_mode") not in GATE2_STRICT_STRUCTURED_OUTPUT_MODES:
            errors.append(_error("source_fact_structured_output_required", f"{path}.structured_output_mode"))
        if audit.get("response_format_type") != "json_schema" or audit.get("fallback_used") is not False:
            errors.append(_error("source_fact_structured_output_required", path))

    def _validate_coverage(
        self,
        *,
        candidate: dict[str, Any],
        package: dict[str, Any],
        fact_covered_refs: set[str],
        errors: list[dict[str, str]],
    ) -> None:
        coverage = _object(candidate.get("coverage"))
        expectation = _object(package.get("coverage_expectation"))
        selected = _string_list(expectation.get("selected_source_refs"))
        if _string_list(coverage.get("selected_source_refs")) != selected:
            errors.append(_error("source_fact_coverage_gap", "$.coverage.selected_source_refs"))
        if set(_string_list(coverage.get("fact_covered_refs"))) != fact_covered_refs:
            errors.append(_error("source_fact_coverage_gap", "$.coverage.fact_covered_refs"))
        no_fact = _dict_list(coverage.get("no_fact_results"))
        no_fact_refs = [str(item.get("source_ref") or "") for item in no_fact]
        if len(no_fact_refs) != len(set(no_fact_refs)):
            errors.append(_error("source_fact_coverage_gap", "$.coverage.no_fact_results"))
        selected_set = set(selected)
        if not set(no_fact_refs) <= selected_set or set(no_fact_refs) & fact_covered_refs:
            errors.append(_error("source_fact_coverage_gap", "$.coverage.no_fact_results"))
        expected_no_fact = {
            **{ref: {"header_row", "repeated_header"} for ref in _string_list(expectation.get("ignorable_header_refs"))},
            **{ref: {"blank_row"} for ref in _string_list(expectation.get("ignorable_blank_refs"))},
            **{ref: {"layout_only", "non_fact_annotation"} for ref in _string_list(expectation.get("layout_candidate_refs"))},
        }
        if not set(expected_no_fact) <= set(no_fact_refs):
            errors.append(_error("source_fact_coverage_gap", "$.coverage.no_fact_results"))
        for item in no_fact:
            source_ref = str(item.get("source_ref") or "")
            if source_ref in expected_no_fact and item.get("reason_code") not in expected_no_fact[source_ref]:
                errors.append(_error("source_fact_coverage_gap", source_ref))
        accounted = fact_covered_refs | set(no_fact_refs)
        if accounted != selected_set:
            errors.append(_error("source_fact_coverage_gap", "$.coverage"))
        if _string_list(coverage.get("rejected_refs")) or _string_list(coverage.get("pending_refs")):
            errors.append(_error("source_fact_coverage_gap", "$.coverage.pending_or_rejected"))
        if coverage.get("coverage_status") != "complete":
            errors.append(_error("source_fact_coverage_gap", "$.coverage.coverage_status"))
        if coverage.get("unit_coverage_ref") != expectation.get("coverage_ref"):
            errors.append(_error("source_fact_coverage_gap", "$.coverage.unit_coverage_ref"))

    def _validate_issue_linkage_summary(
        self,
        *,
        candidate: dict[str, Any],
        package: dict[str, Any],
        facts: list[dict[str, Any]],
        errors: list[dict[str, str]],
    ) -> None:
        summary = _object(candidate.get("issue_linkage_summary"))
        allowed = _string_list(package.get("allowed_issue_refs"))
        expected_links = sum(len(_string_list(fact.get("linked_issue_refs"))) for fact in facts)
        unresolved = sorted(
            str(item.get("issue_ref"))
            for item in _dict_list(package.get("issue_context"))
            if item.get("status") == "unresolved" and item.get("issue_ref")
        )
        if summary.get("package_issue_refs") != allowed:
            errors.append(_error("source_fact_issue_not_carried", "$.issue_linkage_summary.package_issue_refs"))
        if summary.get("fact_issue_links_total") != expected_links:
            errors.append(_error("source_fact_issue_not_carried", "$.issue_linkage_summary.fact_issue_links_total"))
        if summary.get("unresolved_issue_refs") != unresolved:
            errors.append(_error("source_fact_issue_not_carried", "$.issue_linkage_summary.unresolved_issue_refs"))


def _expected_issue_policy(package: dict[str, Any]) -> dict[str, Any]:
    impact = {
        "warning_issue_refs": [],
        "limits_confirmation_issue_refs": [],
        "blocks_fact_issue_refs": [],
        "blocks_consolidation_issue_refs": [],
        "blocks_declaration_issue_refs": [],
        "forbidden_assumption_codes": sorted(_string_list(package.get("forbidden_assumptions"))),
    }
    mapping = {
        "warning": "warning_issue_refs",
        "limits_confirmation": "limits_confirmation_issue_refs",
        "blocks_fact": "blocks_fact_issue_refs",
        "blocks_consolidation": "blocks_consolidation_issue_refs",
        "blocks_declaration": "blocks_declaration_issue_refs",
    }
    for item in _dict_list(package.get("issue_context")):
        key = mapping.get(str(item.get("impact") or ""))
        if key and item.get("issue_ref"):
            impact[key].append(str(item["issue_ref"]))
    for key in mapping.values():
        impact[key] = sorted(set(impact[key]))
    return {
        "linked_issue_refs": sorted(_string_list(package.get("allowed_issue_refs"))),
        "issue_impact": impact,
    }


def _package_source_slice(package: dict[str, Any]) -> dict[str, Any]:
    unit = copy.deepcopy(_object(package.get("source_unit")))
    projection = _object(unit.get("normalized_source_projection"))
    unit["cells"] = copy.deepcopy(projection.get("cells") or [])
    unit["text"] = str(projection.get("text") or "")
    unit["source_value_refs"] = _string_list(package.get("allowed_source_value_refs"))
    return unit


def _finalize_candidate(
    *,
    candidate: dict[str, Any],
    validation_artifact_ref: str,
    raw_output_artifact_ref: str,
    deterministic_fact_ids: list[str],
) -> dict[str, Any]:
    finalized = copy.deepcopy(candidate)
    finalized["validator_status"] = "passed"
    finalized["validation_ref"] = validation_artifact_ref
    finalized["extraction_audit"]["raw_output_artifact_ref"] = raw_output_artifact_ref
    for fact, fact_id in zip(finalized.get("facts") or [], deterministic_fact_ids):
        fact["fact_id"] = fact_id
        fact["validator_status"] = "passed"
        fact["validation_ref"] = validation_artifact_ref
        fact["extraction_audit"]["raw_output_artifact_ref"] = raw_output_artifact_ref
    return finalized


def _validate_schema_subset(
    value: Any,
    schema: dict[str, Any],
    *,
    path: str,
    errors: list[dict[str, str]],
) -> None:
    if "oneOf" in schema:
        branch_results = []
        for branch in schema["oneOf"]:
            branch_errors: list[dict[str, str]] = []
            _validate_schema_subset(value, branch, path=path, errors=branch_errors)
            branch_results.append(branch_errors)
        passing = [item for item in branch_results if not item]
        if len(passing) != 1:
            errors.append(_error("source_fact_schema_mismatch", path))
        return
    expected_type = schema.get("type")
    if expected_type is not None and not _matches_type(value, expected_type):
        errors.append(_error("source_fact_schema_mismatch", path))
        return
    if "const" in schema and value != schema["const"]:
        errors.append(_error("source_fact_schema_mismatch", path))
    if "enum" in schema and value not in schema["enum"]:
        errors.append(_error("source_fact_schema_mismatch", path))
    if isinstance(value, dict):
        properties = _object(schema.get("properties"))
        required = [str(item) for item in schema.get("required") or []]
        for field in required:
            if field not in value:
                errors.append(_error("source_fact_missing_field", f"{path}.{field}"))
        if schema.get("additionalProperties") is False:
            for field in value:
                if field not in properties:
                    errors.append(_error("source_fact_unknown_field", f"{path}.{field}"))
        for field, child in value.items():
            if field in properties:
                _validate_schema_subset(child, properties[field], path=f"{path}.{field}", errors=errors)
    elif isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, child in enumerate(value):
                _validate_schema_subset(child, item_schema, path=f"{path}[{index}]", errors=errors)
    elif isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in schema and value < int(schema["minimum"]):
            errors.append(_error("source_fact_schema_mismatch", path))
        if "maximum" in schema and value > int(schema["maximum"]):
            errors.append(_error("source_fact_schema_mismatch", path))


def _matches_type(value: Any, expected: Any) -> bool:
    values = expected if isinstance(expected, list) else [expected]
    for item in values:
        if item == "null" and value is None:
            return True
        if item == "object" and isinstance(value, dict):
            return True
        if item == "array" and isinstance(value, list):
            return True
        if item == "string" and isinstance(value, str):
            return True
        if item == "boolean" and isinstance(value, bool):
            return True
        if item == "integer" and isinstance(value, int) and not isinstance(value, bool):
            return True
        if item == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
    return False


def _forbidden_field_errors(
    value: Any,
    forbidden: set[str],
    code: str,
    *,
    prefix: str = "$",
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            if str(key).lower() in forbidden:
                errors.append(_error(code, path))
            errors.extend(_forbidden_field_errors(child, forbidden, code, prefix=path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_forbidden_field_errors(child, forbidden, code, prefix=f"{prefix}[{index}]"))
    return errors


def _long_string_errors(value: Any, *, prefix: str = "$") -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            errors.extend(_long_string_errors(child, prefix=f"{prefix}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_long_string_errors(child, prefix=f"{prefix}[{index}]"))
    elif isinstance(value, str) and len(value) > 256:
        errors.append(_error("source_fact_raw_content_forbidden", prefix))
    return errors


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)] if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value or [] if item is not None and str(item)] if isinstance(value, list) else []


def _error(code: str, subject: object) -> dict[str, str]:
    safe_subject = re.sub(r"[^A-Za-z0-9_.$:\-\[\]]", "_", str(subject or ""))[:240]
    return {"code": code, "subject": safe_subject}
