from __future__ import annotations

from typing import Any

from .gate2_source_fact_contracts import (
    FACT_TYPES,
    NO_FACT_REASON_VALUES,
    SOURCE_FACTS_SCHEMA_VERSION,
)


LEGACY_VALIDATOR_ID = (
    "broker_reports_legacy_source_facts_validator_v1"
)
LEGACY_VALIDATOR_POLICY_VERSION = (
    "broker_reports_legacy_source_facts_replay_policy_v1"
)

FACTORY_REQUIRED = (
    "PinnedLegacySourceFactsValidatorFactory.create is the only legacy "
    "broker_reports_source_facts_v0 replay validator entrypoint"
)
FORBIDDEN = (
    "Legacy replay must not call current model/provider paths, repair payloads "
    "or reinterpret legacy fact IDs as Registry type IDs"
)

_REQUIRED_TOP_LEVEL_FIELDS = {
    "schema_version",
    "source_facts_set_id",
    "extraction_run_id",
    "normalization_run_id",
    "case_id",
    "package_refs",
    "document_refs",
    "facts",
    "coverage",
    "issue_linkage_summary",
    "extraction_audit",
    "validation_ref",
    "validator_status",
    "created_at",
}


class PinnedLegacySourceFactsValidatorFactory:
    def create(self) -> "PinnedLegacySourceFactsValidator":
        return PinnedLegacySourceFactsValidator()


class PinnedLegacySourceFactsValidator:
    def validate(self, payload: dict[str, Any]) -> dict[str, Any]:
        errors: list[dict[str, str]] = []
        if not isinstance(payload, dict):
            errors.append(_error("legacy_artifact_not_object", "$"))
            return _receipt(errors=errors, facts_total=0)
        if payload.get("schema_version") != SOURCE_FACTS_SCHEMA_VERSION:
            errors.append(
                _error("legacy_artifact_schema_invalid", "$.schema_version")
            )
        missing = sorted(_REQUIRED_TOP_LEVEL_FIELDS - set(payload))
        for field in missing:
            errors.append(
                _error("legacy_artifact_field_missing", f"$.{field}")
            )
        for field in (
            "source_facts_set_id",
            "extraction_run_id",
            "normalization_run_id",
            "case_id",
            "validation_ref",
            "created_at",
        ):
            if not isinstance(payload.get(field), str) or not payload.get(
                field
            ):
                errors.append(
                    _error(
                        "legacy_artifact_identity_missing",
                        f"$.{field}",
                    )
                )
        if payload.get("validator_status") != "passed":
            errors.append(
                _error(
                    "legacy_artifact_not_terminally_validated",
                    "$.validator_status",
                )
            )
        for field in ("package_refs", "document_refs"):
            values = payload.get(field)
            if (
                not isinstance(values, list)
                or not values
                or any(not isinstance(item, str) or not item for item in values)
                or len(values) != len(set(values))
            ):
                errors.append(
                    _error(
                        "legacy_artifact_provenance_refs_invalid",
                        f"$.{field}",
                    )
                )
        facts = payload.get("facts")
        if not isinstance(facts, list):
            errors.append(_error("legacy_artifact_facts_invalid", "$.facts"))
            facts = []
        fact_ids: set[str] = set()
        validation_ref = payload.get("validation_ref")
        for index, fact in enumerate(facts):
            path = f"$.facts[{index}]"
            if not isinstance(fact, dict):
                errors.append(_error("legacy_fact_not_object", path))
                continue
            fact_id = fact.get("fact_id")
            if (
                not isinstance(fact_id, str)
                or not fact_id
                or fact_id in fact_ids
            ):
                errors.append(_error("legacy_fact_id_invalid", path))
            else:
                fact_ids.add(fact_id)
            if fact.get("fact_type") not in FACT_TYPES:
                errors.append(
                    _error("legacy_fact_type_invalid", f"{path}.fact_type")
                )
            if (
                fact.get("validator_status") != "passed"
                or fact.get("validation_ref") != validation_ref
            ):
                errors.append(
                    _error("legacy_fact_validation_invalid", path)
                )
            evidence_refs = fact.get("evidence_refs")
            if (
                not isinstance(evidence_refs, list)
                or not evidence_refs
                or any(
                    not isinstance(item, str) or not item
                    for item in evidence_refs
                )
            ):
                errors.append(
                    _error("legacy_fact_evidence_refs_invalid", path)
                )
            if not isinstance(fact.get("source_location"), dict):
                errors.append(
                    _error("legacy_fact_source_location_invalid", path)
                )
        _validate_coverage(payload.get("coverage"), errors=errors)
        return _receipt(errors=errors, facts_total=len(facts))


def _validate_coverage(
    coverage: Any,
    *,
    errors: list[dict[str, str]],
) -> None:
    if not isinstance(coverage, dict):
        errors.append(_error("legacy_coverage_invalid", "$.coverage"))
        return
    if coverage.get("coverage_status") != "complete":
        errors.append(
            _error(
                "legacy_coverage_not_complete",
                "$.coverage.coverage_status",
            )
        )
    list_fields = {
        field: coverage.get(field)
        for field in (
            "selected_source_refs",
            "fact_covered_refs",
            "rejected_refs",
            "pending_refs",
        )
    }
    for field, value in list_fields.items():
        if not _is_string_list(value):
            errors.append(
                _error(
                    "legacy_coverage_refs_invalid",
                    f"$.coverage.{field}",
                )
            )
    selected = _string_list(list_fields["selected_source_refs"])
    covered = _string_list(list_fields["fact_covered_refs"])
    rejected = _string_list(list_fields["rejected_refs"])
    pending = _string_list(list_fields["pending_refs"])
    no_fact_results = coverage.get("no_fact_results")
    if not isinstance(no_fact_results, list):
        errors.append(
            _error(
                "legacy_coverage_no_fact_results_invalid",
                "$.coverage.no_fact_results",
            )
        )
        no_fact_results = []
    no_fact_refs: list[str] = []
    for index, item in enumerate(no_fact_results):
        if (
            not isinstance(item, dict)
            or item.get("reason_code") not in NO_FACT_REASON_VALUES
            or not isinstance(item.get("source_ref"), str)
            or not item.get("source_ref")
        ):
            errors.append(
                _error(
                    "legacy_coverage_no_fact_result_invalid",
                    f"$.coverage.no_fact_results[{index}]",
                )
            )
            continue
        no_fact_refs.append(item["source_ref"])
    if (
        len(selected) != len(set(selected))
        or len(covered) != len(set(covered))
        or len(no_fact_refs) != len(set(no_fact_refs))
        or rejected
        or pending
        or set(covered) & set(no_fact_refs)
        or set(covered) | set(no_fact_refs) != set(selected)
    ):
        errors.append(
            _error(
                "legacy_coverage_partition_invalid",
                "$.coverage",
            )
        )


def _receipt(
    *,
    errors: list[dict[str, str]],
    facts_total: int,
) -> dict[str, Any]:
    return {
        "validator_id": LEGACY_VALIDATOR_ID,
        "validator_policy_version": LEGACY_VALIDATOR_POLICY_VERSION,
        "artifact_schema_version": SOURCE_FACTS_SCHEMA_VERSION,
        "validator_status": "passed" if not errors else "failed",
        "facts_total": facts_total,
        "errors": errors,
    }


def _string_list(value: Any) -> list[str]:
    if not _is_string_list(value):
        return []
    return value


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(
        isinstance(item, str) and item for item in value
    )


def _error(code: str, path: str) -> dict[str, str]:
    return {"code": code, "path": path}
