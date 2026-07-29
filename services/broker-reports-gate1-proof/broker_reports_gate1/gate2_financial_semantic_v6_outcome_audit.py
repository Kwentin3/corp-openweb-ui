from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .gate2_financial_evidence_materialization_contracts import sha256_json
from .gate2_financial_semantic_v6_benchmark import (
    validate_financial_semantic_v6_benchmark,
)


OUTCOME_AUDIT_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v6_outcome_audit_v1"
)
OUTCOME_AUDIT_BENCHMARK_ID = (
    "gate2_financial_semantic_v6_outcome_audit"
)
OUTCOME_AUDIT_INTEGRITY_SHA256 = (
    "774acd03c95ddc2d898112b6b62e3bed54613cfeaac7f98689e7c05224d271ae"
)
HISTORICAL_BENCHMARK_SHA256 = (
    "3688fe9d47534cc6f810550561460f1508acd095e798ea90c5998b55c63b0d33"
)
BASE_MANIFEST_SHA256 = (
    "430bea21d0a36e993bc50184d971f36dfc75a1d2be12bcf5e43fba7436797d66"
)
SEMANTIC_PACK_INTEGRITY_SHA256 = (
    "ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8"
)
REASON_CATALOG_V2_INTEGRITY_SHA256 = (
    "2510b57b51749a14f76b987cddaa3eea19f1bb975a97c6c089565253dc3593e9"
)
NEW_REASON_CODE = "single_registry_type_no_safe_record"
FACTORY_REQUIRED = (
    "validate_financial_semantic_v6_outcome_audit is the only additive "
    "corrected-expectation audit validation entrypoint"
)
FORBIDDEN = (
    "The outcome audit must not mutate or replace historical manifests, "
    "infer semantic truth from fixture labels, call a provider, activate "
    "runtime, or become an active V6 qualification route"
)

_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "benchmark_id",
        "status",
        "contains_customer_data",
        "frozen",
        "case_count",
        "historical_benchmark",
        "base_manifest",
        "semantic_pack",
        "reason_catalog",
        "execution_policy",
        "truth_table",
        "cases",
        "zero_choice_audit",
        "integrity_sha256",
    }
)
_CORRECTED_CASE_IDS = frozenset(
    {
        "syn_successor_v2_detail_vs_subtotal",
        "syn_successor_v2_adjacent_equal",
        "syn_successor_v2_adjacent_fx",
    }
)
_ZERO_CHOICE_CASE_IDS = (
    "syn_successor_v2_multiple_compatible",
    "syn_successor_v2_detail_vs_subtotal",
    "syn_successor_v2_adjacent_equal",
    "syn_successor_v2_adjacent_fx",
)
_EXPECTED_CASE_TAXONOMY = {
    "syn_successor_v2_unique_cash": (
        "typed_safe_1",
        ("cash_balance_snapshot_v1",),
    ),
    "syn_successor_v2_unique_printed_total": (
        "typed_safe_1",
        ("printed_financial_metric_v1",),
    ),
    "syn_successor_v2_multiple_compatible": (
        "ambiguous_type_2plus",
        (
            "cash_balance_snapshot_v1",
            "printed_financial_metric_v1",
        ),
    ),
    "syn_successor_v2_no_registry_type": ("no_type_0", ()),
    "syn_successor_v2_missing_discriminator": (
        "ambiguous_type_2plus",
        (
            "cash_balance_snapshot_v1",
            "printed_financial_metric_v1",
        ),
    ),
    "syn_successor_v2_repeated_header": (
        "insufficient_source_context",
        None,
    ),
    "syn_successor_v2_detail_vs_subtotal": (
        "single_type_no_safe_record",
        ("printed_financial_metric_v1",),
    ),
    "syn_successor_v2_adjacent_equal": (
        "single_type_no_safe_record",
        ("cash_balance_snapshot_v1",),
    ),
    "syn_successor_v2_adjacent_fx": (
        "single_type_no_safe_record",
        ("cash_balance_snapshot_v1",),
    ),
    "syn_successor_v2_optional_missing": (
        "typed_safe_1",
        ("cash_balance_snapshot_v1",),
    ),
    "syn_successor_v2_forbidden_neighbour": (
        "typed_safe_1",
        ("cash_balance_snapshot_v1",),
    ),
    "syn_successor_v2_unsupported_shape": ("technical_failure", None),
}
_EXPECTED_ZERO_CHOICE_EVIDENCE_POINTERS = {
    "syn_successor_v2_multiple_compatible": (
        tuple(f"/cases/2/cells/{index}" for index in range(6)),
        (
            "/full_compact_snapshot/0",
            "/full_compact_snapshot/1",
        ),
    ),
    "syn_successor_v2_detail_vs_subtotal": (
        tuple(f"/cases/6/cells/{index}" for index in range(5)),
        (
            "/full_compact_snapshot/0",
            "/full_compact_snapshot/1",
        ),
    ),
    "syn_successor_v2_adjacent_equal": (
        tuple(f"/cases/7/cells/{index}" for index in range(5)),
        (
            "/full_compact_snapshot/0",
            "/full_compact_snapshot/1",
        ),
    ),
    "syn_successor_v2_adjacent_fx": (
        tuple(f"/cases/8/cells/{index}" for index in range(6)),
        (
            "/full_compact_snapshot/0",
            "/full_compact_snapshot/1",
        ),
    ),
}
_EXPECTED_EXECUTION_POLICY = {
    "provider_calls": 0,
    "full_benchmark_run": False,
    "hidden_retry": False,
    "repair": False,
    "fallback": False,
    "fixture_decisions_are_provider_outputs": False,
    "runtime_activation": False,
    "active_v6_consumer": False,
}
_TRUTH_TABLE_FIELDS = frozenset(
    {
        "state",
        "plausible_type_count",
        "uniquely_safe_choice_count",
        "route",
        "semantic_disposition",
        "semantic_reason_code",
        "terminal_policy",
    }
)
_EXPECTED_TRUTH_TABLE = (
    (
        "typed_safe_1",
        (1, 1),
        (1, 1),
        "semantic_model",
        "typed_input",
        "typed_supported",
        "canonical_choice",
    ),
    (
        "no_type_0",
        (0, 0),
        (0, 0),
        "semantic_model",
        "unclassified_financial_input",
        "no_registry_type",
        "canonical_choice",
    ),
    (
        "ambiguous_type_2plus",
        (2, "unbounded"),
        (0, 0),
        "semantic_model",
        "unclassified_financial_input",
        "ambiguous_registry_type",
        "canonical_choice",
    ),
    (
        "single_type_no_safe_record",
        (1, 1),
        (0, 0),
        "semantic_model",
        "unclassified_financial_input",
        NEW_REASON_CODE,
        "future_v2_1_choice_profile_required",
    ),
    (
        "insufficient_source_context",
        None,
        None,
        "technical_preclose",
        None,
        None,
        "code_owned_source_or_layout_outcome",
    ),
    (
        "technical_failure",
        None,
        None,
        "technical_preclose",
        None,
        None,
        "fail_closed_technical_contract",
    ),
)


class Gate2FinancialSemanticV6OutcomeAuditError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2FinancialSemanticV6OutcomeAuditSnapshot:
    schema_version: str
    benchmark_id: str
    cases_total: int
    corrected_expected_answers_total: int
    zero_choice_plausible_type_counts: tuple[int, ...]
    reason_catalog_integrity_sha256: str
    semantic_pack_integrity_sha256: str
    integrity_sha256: str

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "benchmark_id": self.benchmark_id,
            "cases_total": self.cases_total,
            "corrected_expected_answers_total": (
                self.corrected_expected_answers_total
            ),
            "zero_choice_plausible_type_counts": list(
                self.zero_choice_plausible_type_counts
            ),
            "reason_catalog_integrity_sha256": (
                self.reason_catalog_integrity_sha256
            ),
            "semantic_pack_integrity_sha256": (
                self.semantic_pack_integrity_sha256
            ),
            "integrity_sha256": self.integrity_sha256,
        }


def validate_financial_semantic_v6_outcome_audit(
    *,
    manifest: Any,
    historical_manifest: Any,
    base_manifest: Any,
    semantic_pack: Any,
    reason_catalog_v2: Any,
) -> Gate2FinancialSemanticV6OutcomeAuditSnapshot:
    validate_financial_semantic_v6_benchmark(
        manifest=historical_manifest,
        base_manifest=base_manifest,
    )
    if (
        not isinstance(manifest, dict)
        or set(manifest) != _TOP_LEVEL_FIELDS
        or manifest.get("schema_version") != OUTCOME_AUDIT_SCHEMA_VERSION
        or manifest.get("benchmark_id") != OUTCOME_AUDIT_BENCHMARK_ID
        or manifest.get("status")
        != "frozen_corrected_expectations_not_executed"
        or manifest.get("contains_customer_data") is not False
        or manifest.get("frozen") is not True
        or manifest.get("case_count") != 12
        or manifest.get("execution_policy") != _EXPECTED_EXECUTION_POLICY
    ):
        _fail("financial_semantic_v6_outcome_audit_identity_invalid")
    _validate_integrity(
        manifest,
        expected=OUTCOME_AUDIT_INTEGRITY_SHA256,
        code="financial_semantic_v6_outcome_audit_integrity_invalid",
    )
    _validate_predecessors(
        manifest=manifest,
        historical_manifest=historical_manifest,
        base_manifest=base_manifest,
        semantic_pack=semantic_pack,
        reason_catalog_v2=reason_catalog_v2,
    )
    _validate_truth_table(manifest.get("truth_table"))
    cases = _validate_cases(
        manifest.get("cases"),
        historical_manifest=historical_manifest,
        semantic_pack=semantic_pack,
        reason_catalog_v2=reason_catalog_v2,
    )
    counts = _validate_zero_choice_audit(
        manifest.get("zero_choice_audit"),
        cases=cases,
        base_manifest=base_manifest,
        semantic_pack=semantic_pack,
    )
    return Gate2FinancialSemanticV6OutcomeAuditSnapshot(
        schema_version=OUTCOME_AUDIT_SCHEMA_VERSION,
        benchmark_id=OUTCOME_AUDIT_BENCHMARK_ID,
        cases_total=len(cases),
        corrected_expected_answers_total=len(_CORRECTED_CASE_IDS),
        zero_choice_plausible_type_counts=counts,
        reason_catalog_integrity_sha256=(
            REASON_CATALOG_V2_INTEGRITY_SHA256
        ),
        semantic_pack_integrity_sha256=SEMANTIC_PACK_INTEGRITY_SHA256,
        integrity_sha256=OUTCOME_AUDIT_INTEGRITY_SHA256,
    )


def _validate_predecessors(
    *,
    manifest: dict[str, Any],
    historical_manifest: Any,
    base_manifest: Any,
    semantic_pack: Any,
    reason_catalog_v2: Any,
) -> None:
    if (
        not isinstance(historical_manifest, dict)
        or sha256_json(historical_manifest) != HISTORICAL_BENCHMARK_SHA256
        or manifest.get("historical_benchmark")
        != {
            "schema_version": historical_manifest.get("schema_version"),
            "benchmark_id": historical_manifest.get("benchmark_id"),
            "canonical_sha256": HISTORICAL_BENCHMARK_SHA256,
        }
        or not isinstance(base_manifest, dict)
        or sha256_json(base_manifest) != BASE_MANIFEST_SHA256
        or manifest.get("base_manifest")
        != {
            "schema_version": base_manifest.get("schema_version"),
            "benchmark_id": base_manifest.get("benchmark_id"),
            "canonical_sha256": BASE_MANIFEST_SHA256,
            "case_count": 12,
        }
    ):
        _fail("financial_semantic_v6_outcome_audit_predecessor_invalid")
    _validate_integrity(
        semantic_pack,
        expected=SEMANTIC_PACK_INTEGRITY_SHA256,
        code="financial_semantic_v6_outcome_audit_pack_invalid",
    )
    if manifest.get("semantic_pack") != {
        "schema_version": semantic_pack.get("schema_version"),
        "pack_id": semantic_pack.get("pack_id"),
        "semantic_version": semantic_pack.get("semantic_version"),
        "semantic_integrity_sha256": SEMANTIC_PACK_INTEGRITY_SHA256,
    }:
        _fail("financial_semantic_v6_outcome_audit_pack_invalid")
    _validate_integrity(
        reason_catalog_v2,
        expected=REASON_CATALOG_V2_INTEGRITY_SHA256,
        code="financial_semantic_v6_outcome_audit_catalog_invalid",
    )
    reason_codes = [
        item.get("code") for item in reason_catalog_v2.get("reasons", [])
    ]
    if (
        NEW_REASON_CODE not in reason_codes
        or manifest.get("reason_catalog")
        != {
            "schema_version": reason_catalog_v2.get("schema_version"),
            "catalog_id": reason_catalog_v2.get("catalog_id"),
            "semantic_version": reason_catalog_v2.get("semantic_version"),
            "semantic_integrity_sha256": (
                REASON_CATALOG_V2_INTEGRITY_SHA256
            ),
            "added_reason_code": NEW_REASON_CODE,
            "runtime_activation": False,
            "response_profile_status": "not_implemented",
        }
    ):
        _fail("financial_semantic_v6_outcome_audit_catalog_invalid")


def _validate_truth_table(value: Any) -> None:
    if not isinstance(value, list) or len(value) != len(_EXPECTED_TRUTH_TABLE):
        _fail("financial_semantic_v6_outcome_audit_truth_table_invalid")
    observed = []
    for item in value:
        if not isinstance(item, dict) or set(item) != _TRUTH_TABLE_FIELDS:
            _fail("financial_semantic_v6_outcome_audit_truth_table_invalid")
        observed.append(
            (
                item.get("state"),
                _range_tuple(item.get("plausible_type_count")),
                _range_tuple(item.get("uniquely_safe_choice_count")),
                item.get("route"),
                item.get("semantic_disposition"),
                item.get("semantic_reason_code"),
                item.get("terminal_policy"),
            )
        )
    if tuple(observed) != _EXPECTED_TRUTH_TABLE:
        _fail("financial_semantic_v6_outcome_audit_truth_table_invalid")


def _validate_cases(
    value: Any,
    *,
    historical_manifest: dict[str, Any],
    semantic_pack: dict[str, Any],
    reason_catalog_v2: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if (
        not isinstance(value, list)
        or len(value) != 12
        or any(not isinstance(item, dict) for item in value)
    ):
        _fail("financial_semantic_v6_outcome_audit_cases_invalid")
    historical_cases = historical_manifest["cases"]
    if [item.get("case_id") for item in value] != [
        item.get("case_id") for item in historical_cases
    ]:
        _fail("financial_semantic_v6_outcome_audit_cases_invalid")
    pack_type_ids = {
        item.get("input_type_id")
        for item in semantic_pack.get("full_compact_snapshot", [])
    }
    catalog_reason_codes = {
        item.get("code") for item in reason_catalog_v2.get("reasons", [])
    }
    by_id: dict[str, dict[str, Any]] = {}
    observed_corrections: set[str] = set()
    for item, historical in zip(value, historical_cases, strict=True):
        technical = historical["expected_route"] == "technical_preclose"
        expected_fields = {
            "case_id",
            "feature_families",
            "taxonomy_state",
            "plausible_type_ids",
            "expected_route",
            "expected_disposition",
            "expected_input_type_id",
            "expected_reason_code",
            "expected_typed_options",
            *(("technical_evidence",) if technical else ()),
        }
        if (
            set(item) != expected_fields
            or item["feature_families"] != historical["feature_families"]
            or item["expected_route"] != historical["expected_route"]
            or item["expected_disposition"]
            != historical["expected_disposition"]
            or item["expected_input_type_id"]
            != historical["expected_input_type_id"]
            or item["expected_typed_options"]
            != historical["expected_typed_options"]
            or (
                technical
                and item.get("technical_evidence")
                != historical.get("technical_evidence")
            )
        ):
            _fail("financial_semantic_v6_outcome_audit_case_invalid")
        case_id = item["case_id"]
        historical_reason = historical["expected_reason_code"]
        if case_id in _CORRECTED_CASE_IDS:
            if (
                historical_reason != "ambiguous_registry_type"
                or item["expected_reason_code"] != NEW_REASON_CODE
            ):
                _fail(
                    "financial_semantic_v6_outcome_audit_correction_invalid"
                )
            observed_corrections.add(case_id)
        elif item["expected_reason_code"] != historical_reason:
            _fail("financial_semantic_v6_outcome_audit_correction_invalid")
        plausible = item["plausible_type_ids"]
        state = item["taxonomy_state"]
        if plausible is not None and (
            not isinstance(plausible, list)
            or len(plausible) != len(set(plausible))
            or not set(plausible).issubset(pack_type_ids)
        ):
            _fail("financial_semantic_v6_outcome_audit_types_invalid")
        observed_taxonomy = (
            state,
            None if plausible is None else tuple(plausible),
        )
        if observed_taxonomy != _EXPECTED_CASE_TAXONOMY.get(case_id):
            _fail("financial_semantic_v6_outcome_audit_types_invalid")
        _validate_case_state(
            item=item,
            state=state,
            plausible=plausible,
            catalog_reason_codes=catalog_reason_codes,
        )
        by_id[case_id] = copy.deepcopy(item)
    if observed_corrections != set(_CORRECTED_CASE_IDS):
        _fail("financial_semantic_v6_outcome_audit_correction_invalid")
    return by_id


def _validate_case_state(
    *,
    item: dict[str, Any],
    state: Any,
    plausible: Any,
    catalog_reason_codes: set[Any],
) -> None:
    reason = item["expected_reason_code"]
    if state == "typed_safe_1":
        valid = (
            isinstance(plausible, list)
            and len(plausible) == 1
            and item["expected_disposition"] == "typed_input"
            and item["expected_input_type_id"] == plausible[0]
            and reason == "typed_supported"
        )
    elif state == "no_type_0":
        valid = (
            plausible == []
            and item["expected_disposition"] == "unclassified_financial_input"
            and reason == "no_registry_type"
        )
    elif state == "ambiguous_type_2plus":
        valid = (
            isinstance(plausible, list)
            and len(plausible) >= 2
            and item["expected_disposition"] == "unclassified_financial_input"
            and reason == "ambiguous_registry_type"
        )
    elif state == "single_type_no_safe_record":
        valid = (
            isinstance(plausible, list)
            and len(plausible) == 1
            and item["expected_disposition"] == "unclassified_financial_input"
            and reason == NEW_REASON_CODE
        )
    elif state == "insufficient_source_context":
        valid = (
            plausible is None
            and item["expected_route"] == "technical_preclose"
            and item["expected_disposition"] == "no_financial_input"
        )
    elif state == "technical_failure":
        valid = (
            plausible is None
            and item["expected_route"] == "technical_preclose"
            and item["expected_disposition"] == "unsupported"
        )
    else:
        valid = False
    if not valid or (
        item["expected_disposition"] == "unclassified_financial_input"
        and reason not in catalog_reason_codes
    ):
        _fail("financial_semantic_v6_outcome_audit_state_invalid")


def _validate_zero_choice_audit(
    value: Any,
    *,
    cases: dict[str, dict[str, Any]],
    base_manifest: dict[str, Any],
    semantic_pack: dict[str, Any],
) -> tuple[int, ...]:
    if (
        not isinstance(value, list)
        or any(not isinstance(item, dict) for item in value)
        or tuple(item.get("case_id") for item in value)
        != _ZERO_CHOICE_CASE_IDS
    ):
        _fail("financial_semantic_v6_outcome_audit_zero_choice_invalid")
    base_cases = {
        item["case_id"]: item for item in base_manifest.get("cases", [])
    }
    counts = []
    changed = set()
    for audit in value:
        if not isinstance(audit, dict) or set(audit) != {
            "case_id",
            "plausible_type_ids",
            "primary_evidence",
            "assessment",
            "historical_reason_code",
            "corrected_reason_code",
            "expected_answer_changed",
        }:
            _fail("financial_semantic_v6_outcome_audit_zero_choice_invalid")
        case = cases.get(audit["case_id"])
        if (
            case is None
            or case["expected_typed_options"] != 0
            or audit["plausible_type_ids"] != case["plausible_type_ids"]
            or audit["historical_reason_code"] != "ambiguous_registry_type"
            or audit["corrected_reason_code"] != case["expected_reason_code"]
            or not isinstance(audit["assessment"], str)
            or len(audit["assessment"].split()) < 8
        ):
            _fail("financial_semantic_v6_outcome_audit_zero_choice_invalid")
        expected_changed = audit["case_id"] in _CORRECTED_CASE_IDS
        if audit["expected_answer_changed"] is not expected_changed:
            _fail("financial_semantic_v6_outcome_audit_zero_choice_invalid")
        if expected_changed:
            changed.add(audit["case_id"])
        evidence = audit.get("primary_evidence")
        if not isinstance(evidence, dict) or set(evidence) != {
            "source_manifest_pointers",
            "semantic_pack_pointers",
        }:
            _fail("financial_semantic_v6_outcome_audit_evidence_invalid")
        source_pointers = evidence["source_manifest_pointers"]
        pack_pointers = evidence["semantic_pack_pointers"]
        expected_source_pointers, expected_pack_pointers = (
            _EXPECTED_ZERO_CHOICE_EVIDENCE_POINTERS[audit["case_id"]]
        )
        if (
            not isinstance(source_pointers, list)
            or not isinstance(pack_pointers, list)
            or tuple(source_pointers) != expected_source_pointers
            or tuple(pack_pointers) != expected_pack_pointers
        ):
            _fail("financial_semantic_v6_outcome_audit_evidence_invalid")
        source_values = [
            _json_pointer_get(base_manifest, pointer)
            for pointer in source_pointers
        ]
        pack_values = [
            _json_pointer_get(semantic_pack, pointer)
            for pointer in pack_pointers
        ]
        if (
            not source_values
            or any(not isinstance(item, dict) for item in source_values)
            or base_cases[audit["case_id"]]["cells"] != source_values
            or {
                item.get("input_type_id") for item in pack_values
            }
            != {
                item.get("input_type_id")
                for item in semantic_pack["full_compact_snapshot"]
            }
        ):
            _fail("financial_semantic_v6_outcome_audit_evidence_invalid")
        counts.append(len(audit["plausible_type_ids"]))
    if changed != set(_CORRECTED_CASE_IDS) or tuple(counts) != (2, 1, 1, 1):
        _fail("financial_semantic_v6_outcome_audit_zero_choice_invalid")
    return tuple(counts)


def _range_tuple(value: Any) -> tuple[int, int | str] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {
        "minimum_inclusive",
        "maximum_inclusive",
    }:
        _fail("financial_semantic_v6_outcome_audit_truth_table_invalid")
    return value["minimum_inclusive"], value["maximum_inclusive"]


def _validate_integrity(value: Any, *, expected: str, code: str) -> None:
    if not isinstance(value, dict):
        _fail(code)
    material = copy.deepcopy(value)
    supplied = material.pop("integrity_sha256", None)
    calculated = hashlib.sha256(_canonical_json(material)).hexdigest()
    if supplied != expected or calculated != expected:
        _fail(code)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _json_pointer_get(value: Any, pointer: Any) -> Any:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        _fail("financial_semantic_v6_outcome_audit_evidence_invalid")
    current = value
    try:
        for raw in pointer.removeprefix("/").split("/"):
            segment = raw.replace("~1", "/").replace("~0", "~")
            current = (
                current[int(segment)]
                if isinstance(current, list)
                else current[segment]
            )
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        raise Gate2FinancialSemanticV6OutcomeAuditError(
            "financial_semantic_v6_outcome_audit_evidence_invalid"
        ) from exc
    return current


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV6OutcomeAuditError(code)
