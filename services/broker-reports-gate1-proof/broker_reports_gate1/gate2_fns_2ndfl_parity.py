from __future__ import annotations

import copy
import re
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from .contracts import stable_digest
from .gate2_fns_2ndfl_contracts import (
    ADAPTER_ID,
    integrity_ref,
    validate_fns_2ndfl_typed_output,
)


PARITY_SCHEMA_VERSION = "broker_reports_fns_2ndfl_pdf_xml_parity_v1"
PARITY_VALIDATION_SCHEMA_VERSION = (
    "broker_reports_fns_2ndfl_pdf_xml_parity_validation_v1"
)
PARITY_SAFE_REPORT_SCHEMA_VERSION = (
    "broker_reports_fns_2ndfl_pdf_xml_parity_safe_report_v1"
)

TERMINAL_CLASSES = {
    "matched_material_financial",
    "xml_only_certificate_metadata",
    "pdf_only_presentational",
    "permitted_format_specific_metadata",
    "unmatched_material_error",
}

MATERIAL_FACT_FAMILIES = {
    "income_source_row",
    "deduction_source_row",
    "tax_summary_source_fact",
}

FACTORY_REQUIRED = (
    "Gate2Fns2NdflParityFactory.create is the only production paired FNS "
    "PDF/XML representation-reconciliation entrypoint"
)
FORBIDDEN = (
    "The parity service must not merge or delete source identities, promote "
    "a PDF candidate to canonical, infer tax, call a provider, or accept a "
    "material contradiction"
)


class Gate2Fns2NdflParityError(RuntimeError):
    def __init__(self, code: str, subject: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.subject = subject


@dataclass(frozen=True)
class Gate2Fns2NdflParityConfig:
    minimum_normalized_value_characters: int = 2


class Gate2Fns2NdflParityFactory:
    def __init__(self, config: Gate2Fns2NdflParityConfig | None = None) -> None:
        self.config = config or Gate2Fns2NdflParityConfig()

    def create(self) -> "Gate2Fns2NdflParityService":
        if self.config.minimum_normalized_value_characters < 1:
            raise ValueError("fns_2ndfl_parity_value_length_policy_invalid")
        return Gate2Fns2NdflParityService(self.config)


class Gate2Fns2NdflParityService:
    def __init__(self, config: Gate2Fns2NdflParityConfig) -> None:
        self.config = config

    def reconcile(
        self,
        *,
        typed_xml_output: dict[str, Any],
        paired_pdf_document_ref: str,
        pdf_source_units: list[dict[str, Any]],
    ) -> dict[str, Any]:
        typed_validation = validate_fns_2ndfl_typed_output(typed_xml_output)
        if typed_validation.get("validator_status") != "passed":
            raise Gate2Fns2NdflParityError("fns_2ndfl_parity_typed_xml_invalid")
        if not paired_pdf_document_ref:
            raise Gate2Fns2NdflParityError("fns_2ndfl_parity_pdf_identity_missing")
        if not pdf_source_units:
            raise Gate2Fns2NdflParityError("fns_2ndfl_parity_pdf_units_missing")

        for unit in pdf_source_units:
            if _document_ref(unit) != paired_pdf_document_ref:
                raise Gate2Fns2NdflParityError(
                    "fns_2ndfl_parity_pdf_document_scope_mismatch"
                )
        candidate_units = [
            unit
            for unit in pdf_source_units
            if _unit_kind(unit)
            in {"pdf_table_candidate", "pdf_table_candidate_unit"}
        ]
        candidate_refs = [str(unit.get("unit_id") or "") for unit in candidate_units]
        if not candidate_refs or "" in candidate_refs or len(candidate_refs) != len(
            set(candidate_refs)
        ):
            raise Gate2Fns2NdflParityError(
                "fns_2ndfl_parity_pdf_candidate_identity_invalid"
            )

        pdf_text = " ".join(_unit_text(unit) for unit in pdf_source_units)
        normalized_pdf = _normalized_value(pdf_text)
        material_pdf_text = " ".join(
            _unit_text(unit)
            for unit in candidate_units
            if _candidate_role(_unit_text(unit))[0] != "other_form_or_heading"
        )
        forward: list[dict[str, Any]] = []
        for fact in typed_xml_output.get("facts") or []:
            if not isinstance(fact, dict):
                continue
            family = str(fact.get("fact_family") or "")
            material = family in MATERIAL_FACT_FAMILIES
            for field in fact.get("fields") or []:
                if not isinstance(field, dict):
                    continue
                normalized = _normalized_value(
                    field.get("source_lexeme")
                    if field.get("source_lexeme") is not None
                    else field.get("value")
                )
                if material:
                    classification, comparison_policy = _material_field_match(
                        field=field,
                        normalized_value=normalized,
                        normalized_pdf=normalized_pdf,
                        pdf_text=material_pdf_text,
                        minimum_characters=(
                            self.config.minimum_normalized_value_characters
                        ),
                    )
                else:
                    classification = (
                        "permitted_format_specific_metadata"
                        if normalized and normalized in normalized_pdf
                        else "xml_only_certificate_metadata"
                    )
                    comparison_policy = "casefold_alnum_normalized_substring_v1"
                forward.append(
                    {
                        "direction": "xml_to_pdf",
                        "fact_id": fact.get("fact_id"),
                        "field_code": field.get("field_code"),
                        "xml_original_value_ref": field.get("original_value_ref"),
                        "classification": classification,
                        "comparison_policy": comparison_policy,
                    }
                )

        typed_field_codes = {
            str(field.get("field_code") or "")
            for fact in typed_xml_output.get("facts") or []
            if isinstance(fact, dict)
            for field in fact.get("fields") or []
            if isinstance(field, dict)
        }
        section_refs = {
            str(fact.get("source_section_ref") or "")
            for fact in typed_xml_output.get("facts") or []
            if isinstance(fact, dict)
            and fact.get("fact_family") == "tax_summary_source_fact"
            and fact.get("source_section_ref")
        }
        reverse: list[dict[str, Any]] = []
        candidate_role_counts: Counter[str] = Counter()
        for unit in candidate_units:
            text = _unit_text(unit)
            role, required_codes, labels_complete = _candidate_role(text)
            candidate_role_counts[role] += 1
            if role == "other_form_or_heading":
                classification = (
                    "permitted_format_specific_metadata"
                    if _contains_metadata_signal(text)
                    else "pdf_only_presentational"
                )
                reason_code = "non_financial_form_or_heading_scope"
            elif labels_complete and required_codes <= typed_field_codes:
                classification = "matched_material_financial"
                reason_code = "typed_xml_field_family_and_pdf_labels_present"
            else:
                classification = "unmatched_material_error"
                reason_code = (
                    "pdf_material_labels_or_typed_field_family_incomplete"
                )
            reverse.append(
                {
                    "direction": "pdf_to_xml",
                    "pdf_candidate_ref": unit.get("unit_id"),
                    "pdf_candidate_role": role,
                    "classification": classification,
                    "reason_code": reason_code,
                    "recovery_disposition": (
                        "recovery_deferred_validated_paired_xml_coverage"
                    ),
                    "pdf_integrity_ref": unit.get("source_unit_checksum_ref"),
                }
            )

        material_role_counts = {
            role: candidate_role_counts.get(role, 0)
            for role in (
                "income_deduction_table",
                "tax_summary_table",
                "nonwithheld_tax_table",
            )
        }
        for role, count in material_role_counts.items():
            if count != len(section_refs):
                reverse.append(
                    {
                        "direction": "pdf_to_xml",
                        "pdf_candidate_ref": None,
                        "pdf_candidate_role": role,
                        "classification": "unmatched_material_error",
                        "reason_code": "pdf_xml_material_section_cardinality_mismatch",
                        "recovery_disposition": "blocked_contradiction",
                        "pdf_integrity_ref": None,
                    }
                )

        all_entries = [*forward, *reverse]
        terminal_counts = Counter(
            str(item.get("classification") or "unknown") for item in all_entries
        )
        unmatched = terminal_counts.get("unmatched_material_error", 0)
        payload = {
            "schema_version": PARITY_SCHEMA_VERSION,
            "parity_id": f"fnsparity_{stable_digest([typed_xml_output.get('source_document_ref'), paired_pdf_document_ref, *sorted(candidate_refs)], length=24)}",
            "adapter_id": ADAPTER_ID,
            "typed_xml_document_ref": typed_xml_output.get("source_document_ref"),
            "typed_xml_package_ref": typed_xml_output.get("source_package_ref"),
            "paired_pdf_document_ref": paired_pdf_document_ref,
            "pdf_candidate_refs": sorted(candidate_refs),
            "forward_field_results": forward,
            "reverse_scope_results": reverse,
            "terminal_class_counts": dict(sorted(terminal_counts.items())),
            "candidate_role_counts": dict(sorted(candidate_role_counts.items())),
            "unmatched_material_errors": unmatched,
            "terminal_status": "validated" if unmatched == 0 else "blocked",
            "representation_satisfaction": {
                "workflow": "withholding_source_evidence",
                "selected_representation": "typed_fns_2ndfl_xml",
                "typed_xml_satisfies_named_workflow": unmatched == 0,
                "pdf_source_identity_preserved": True,
                "pdf_candidates_preserved": len(candidate_refs),
                "pdf_candidates_canonicalized": 0,
                "pdf_recovery_status": (
                    "recovery_deferred_validated_paired_xml_coverage"
                    if unmatched == 0
                    else "blocked_contradiction"
                ),
                "source_identities_merged_or_deleted": False,
            },
            "provider_accounting": {
                "calls": 0,
                "tokens": 0,
                "cost": 0,
                "llm_fallback_allowed": False,
            },
        }
        payload["integrity_ref"] = integrity_ref("fnsparitychk", payload)
        if unmatched:
            forward_unmatched = sum(
                item.get("classification") == "unmatched_material_error"
                for item in forward
            )
            reverse_unmatched = sum(
                item.get("classification") == "unmatched_material_error"
                for item in reverse
            )
            forward_unmatched_fields = Counter(
                str(item.get("field_code") or "unknown")
                for item in forward
                if item.get("classification") == "unmatched_material_error"
            )
            raise Gate2Fns2NdflParityError(
                "fns_2ndfl_parity_unmatched_material_error",
                (
                    f"forward={forward_unmatched};reverse={reverse_unmatched};"
                    f"sections={len(section_refs)};roles="
                    + ",".join(
                        f"{key}:{value}"
                        for key, value in sorted(material_role_counts.items())
                    )
                    + ";forward_fields="
                    + ",".join(
                        f"{key}:{value}"
                        for key, value in sorted(forward_unmatched_fields.items())
                    )
                ),
            )
        validation = validate_fns_2ndfl_parity(
            payload, expected_pdf_candidate_refs=candidate_refs
        )
        if validation.get("validator_status") != "passed":
            code = str((validation.get("errors") or [{}])[0].get("code") or "")
            raise Gate2Fns2NdflParityError(
                code or "fns_2ndfl_parity_validation_failed"
            )
        return payload


def validate_fns_2ndfl_parity(
    payload: dict[str, Any],
    *,
    expected_pdf_candidate_refs: list[str] | None = None,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    parity_id = str(payload.get("parity_id") or "")
    entries = [
        item
        for key in ("forward_field_results", "reverse_scope_results")
        for item in payload.get(key) or []
        if isinstance(item, dict)
    ]
    candidate_refs = _string_list(payload.get("pdf_candidate_refs"))
    expected_refs = sorted(str(item) for item in expected_pdf_candidate_refs or [])
    if payload.get("schema_version") != PARITY_SCHEMA_VERSION:
        errors.append(_error("fns_2ndfl_parity_schema_invalid", parity_id))
    if payload.get("adapter_id") != ADAPTER_ID:
        errors.append(_error("fns_2ndfl_parity_adapter_invalid", parity_id))
    if payload.get("terminal_status") != "validated":
        errors.append(_error("fns_2ndfl_parity_terminal_status_invalid", parity_id))
    if not parity_id or not payload.get("typed_xml_document_ref") or not payload.get(
        "paired_pdf_document_ref"
    ):
        errors.append(_error("fns_2ndfl_parity_source_identity_missing", parity_id))
    if len(candidate_refs) != len(set(candidate_refs)) or not candidate_refs:
        errors.append(_error("fns_2ndfl_parity_candidate_identity_invalid", parity_id))
    if expected_refs and sorted(candidate_refs) != expected_refs:
        errors.append(_error("fns_2ndfl_parity_candidate_refs_mismatch", parity_id))
    invalid_classes = {
        str(item.get("classification") or "") for item in entries
    } - TERMINAL_CLASSES
    if invalid_classes:
        errors.append(_error("fns_2ndfl_parity_terminal_class_invalid", parity_id))
    if any(
        item.get("classification") == "unmatched_material_error" for item in entries
    ) or payload.get("unmatched_material_errors") != 0:
        errors.append(_error("fns_2ndfl_parity_unmatched_material_error", parity_id))
    representation = _object(payload.get("representation_satisfaction"))
    for key, expected in (
        ("typed_xml_satisfies_named_workflow", True),
        ("pdf_source_identity_preserved", True),
        ("pdf_candidates_canonicalized", 0),
        ("source_identities_merged_or_deleted", False),
    ):
        if representation.get(key) != expected:
            errors.append(_error("fns_2ndfl_parity_representation_guard_failed", key))
    if representation.get("pdf_candidates_preserved") != len(candidate_refs):
        errors.append(_error("fns_2ndfl_parity_candidate_accounting_mismatch", parity_id))
    provider = _object(payload.get("provider_accounting"))
    if provider != {
        "calls": 0,
        "tokens": 0,
        "cost": 0,
        "llm_fallback_allowed": False,
    }:
        errors.append(_error("fns_2ndfl_parity_provider_guard_failed", parity_id))
    expected_integrity = integrity_ref(
        "fnsparitychk",
        {key: value for key, value in payload.items() if key != "integrity_ref"},
    )
    if payload.get("integrity_ref") != expected_integrity:
        errors.append(_error("fns_2ndfl_parity_integrity_mismatch", parity_id))
    return {
        "schema_version": PARITY_VALIDATION_SCHEMA_VERSION,
        "parity_id": parity_id,
        "validator_status": "passed" if not errors else "failed",
        "entries_total": len(entries),
        "pdf_candidates_preserved": len(candidate_refs),
        "errors": errors,
    }


def render_fns_2ndfl_parity_safe_report(payload: dict[str, Any]) -> dict[str, Any]:
    validation = validate_fns_2ndfl_parity(payload)
    safe = {
        "schema_version": PARITY_SAFE_REPORT_SCHEMA_VERSION,
        "opaque_pair_id": integrity_ref("fnspair", payload.get("parity_id")),
        "terminal_status": payload.get("terminal_status"),
        "validator_status": validation.get("validator_status"),
        "terminal_class_counts": copy.deepcopy(
            payload.get("terminal_class_counts") or {}
        ),
        "candidate_role_counts": copy.deepcopy(
            payload.get("candidate_role_counts") or {}
        ),
        "pdf_candidates_preserved": len(payload.get("pdf_candidate_refs") or []),
        "pdf_candidates_canonicalized": _object(
            payload.get("representation_satisfaction")
        ).get("pdf_candidates_canonicalized"),
        "typed_xml_satisfies_named_workflow": _object(
            payload.get("representation_satisfaction")
        ).get("typed_xml_satisfies_named_workflow"),
        "unmatched_material_errors": payload.get("unmatched_material_errors"),
        "provider_calls": _object(payload.get("provider_accounting")).get("calls"),
        "provider_tokens": _object(payload.get("provider_accounting")).get("tokens"),
        "provider_cost": _object(payload.get("provider_accounting")).get("cost"),
        "customer_values_in_report": False,
        "source_identities_in_report": False,
        "parity_integrity_ref": payload.get("integrity_ref"),
    }
    safe["integrity_ref"] = integrity_ref("fnsparitysafechk", safe)
    return safe


def _candidate_role(text: str) -> tuple[str, set[str], bool]:
    compact = " ".join(str(text or "").casefold().split())
    if (
        "месяц" in compact
        and "сумма дохода" in compact
        and "сумма вычета" in compact
    ):
        return (
            "income_deduction_table",
            {"Месяц", "КодДоход", "СумДоход"},
            compact.count("код") >= 2,
        )
    if "налоговая база" in compact and "общая сумма дохода" in compact:
        return (
            "tax_summary_table",
            {"СумДохОбщ", "НалБаза", "НалИсчисл", "НалУдерж"},
            "сумма налога исчисленная" in compact
            and "сумма налога удержанная" in compact,
        )
    if "сумма неудержанного налога" in compact:
        return (
            "nonwithheld_tax_table",
            {"СумДохНеУдерж", "СумНеУдНал"},
            "сумма дохода" in compact and "не удержан" in compact,
        )
    return "other_form_or_heading", set(), True


def _contains_metadata_signal(text: str) -> bool:
    compact = str(text or "").casefold()
    return any(
        signal in compact
        for signal in (
            "сведения",
            "физического лица",
            "налоговый агент",
            "документ",
            "код",
        )
    )


def _document_ref(unit: dict[str, Any]) -> str:
    return str(unit.get("document_ref") or unit.get("document_id") or "")


def _unit_kind(unit: dict[str, Any]) -> str:
    return str(unit.get("unit_kind") or unit.get("pdf_unit_type") or "")


def _unit_text(unit: dict[str, Any]) -> str:
    projection = _object(unit.get("normalized_source_projection"))
    return str(projection.get("text") or unit.get("text") or "")


def _normalized_value(value: Any) -> str:
    return re.sub(r"[^0-9a-zа-яё]+", "", str(value or "").casefold())


def _material_field_match(
    *,
    field: dict[str, Any],
    normalized_value: str,
    normalized_pdf: str,
    pdf_text: str,
    minimum_characters: int,
) -> tuple[str, str]:
    value_type = field.get("value_type")
    if value_type == "decimal":
        try:
            expected = Decimal(str(field.get("value") or ""))
        except InvalidOperation:
            expected = None
        for token in _numeric_tokens(pdf_text):
            observed = _decimal_token(token)
            if expected is not None and observed == expected:
                comparison_policy = (
                    "casefold_alnum_normalized_substring_v1"
                    if _normalized_value(token) == normalized_value
                    else "schema_integer_decimal_token_equivalence_v1"
                )
                return "matched_material_financial", comparison_policy
        if expected is not None and _numeric_digit_sequence_present(
            str(field.get("source_lexeme") or field.get("value") or ""),
            pdf_text,
        ):
            return (
                "matched_material_financial",
                "schema_decimal_grouping_separator_equivalence_v1",
            )
        if expected == Decimal("0"):
            return (
                "matched_material_financial",
                "schema_zero_to_blank_representation_equivalence_v1",
            )
        return "unmatched_material_error", "schema_decimal_token_match_v1"
    if value_type == "month":
        try:
            expected_month = int(str(field.get("value") or ""))
        except ValueError:
            expected_month = None
        for token in _numeric_tokens(pdf_text):
            observed = _decimal_token(token)
            if (
                expected_month is not None
                and observed is not None
                and observed == Decimal(expected_month)
            ):
                policy = (
                    "casefold_alnum_normalized_substring_v1"
                    if token == str(field.get("value") or "")
                    else "schema_month_leading_zero_equivalence_v1"
                )
                return "matched_material_financial", policy
        return "unmatched_material_error", "schema_month_token_match_v1"
    source_lexeme = str(
        field.get("source_lexeme")
        if field.get("source_lexeme") is not None
        else field.get("value")
    )
    if source_lexeme.isdigit():
        if re.search(rf"(?<!\d){re.escape(source_lexeme)}(?!\d)", pdf_text):
            return "matched_material_financial", "numeric_code_token_match_v1"
        return "unmatched_material_error", "numeric_code_token_match_v1"
    if len(normalized_value) >= minimum_characters and normalized_value in normalized_pdf:
        return "matched_material_financial", "casefold_alnum_normalized_substring_v1"
    return "unmatched_material_error", "casefold_alnum_normalized_substring_v1"


def _numeric_tokens(text: str) -> list[str]:
    return re.findall(
        r"(?<!\d)-?\d+(?:[ \u00a0]\d{3})*(?:[.,][ \u00a0]*\d{1,2})?(?!\d)",
        str(text or ""),
    )


def _decimal_token(token: str) -> Decimal | None:
    normalized = re.sub(r"\s+", "", token).replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def _numeric_digit_sequence_present(source_value: str, text: str) -> bool:
    digits = re.sub(r"\D", "", source_value)
    if not digits:
        return False
    pattern = r"(?<!\d)" + r"[ \u00a0.,]*".join(
        re.escape(digit) for digit in digits
    ) + r"(?!\d)"
    return re.search(pattern, str(text or "")) is not None


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value or [] if item is not None and str(item)]


def _error(code: str, subject: object) -> dict[str, str]:
    return {"code": code, "subject": str(subject or "unknown")}
