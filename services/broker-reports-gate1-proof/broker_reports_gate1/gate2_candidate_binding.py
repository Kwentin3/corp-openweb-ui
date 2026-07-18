from __future__ import annotations

import copy
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from .contracts import stable_digest
from .gate1_public_contracts import reproduce_normalized_value


CANDIDATE_SET_SCHEMA_VERSION = "broker_reports_source_value_candidate_set_v0"
RELATION_SET_SCHEMA_VERSION = "broker_reports_candidate_relation_set_v0"
BINDING_PROFILE_SCHEMA_VERSION = "broker_reports_domain_candidate_binding_profile_v0"
BINDING_OUTPUT_SCHEMA_VERSION = "broker_reports_candidate_binding_output_v0"
BINDING_VALIDATION_SCHEMA_VERSION = "broker_reports_candidate_binding_validation_v0"

FACTORY_REQUIRED = (
    "Gate2CandidateBindingKernelFactory.create is the only production candidate-binding entrypoint"
)
FORBIDDEN = (
    "Candidate discovery and finalization must not choose semantic roles or invent source values"
)

def _role(path: str, *kinds: str) -> dict[str, Any]:
    return {"fact_field_path": path, "candidate_kinds": list(kinds)}


DOMAIN_BINDING_PROFILES: dict[str, dict[str, Any]] = {
    "cash_movement": {
        "roles": {
            "movement_amount": _role("normalized_values.amount", "decimal_amount"),
            "movement_currency": _role("normalized_values.currency", "currency_code"),
            "movement_date": _role("normalized_values.date", "date"),
            "movement_direction": _role("extracted_fields.movement_type_candidate", "categorical_direction"),
            "movement_description": _role("extracted_fields.description_value_refs", "short_visible_label"),
        },
        "required_roles": ["movement_amount"],
        "required_role_groups": [],
        "required_relation_kinds": [],
        "candidate_reuse": {},
        "subtypes": ["deposit", "withdrawal", "credit", "debit", "unknown"],
    },
    "income": {
        "roles": {
            "income_amount": _role("normalized_values.amount", "decimal_amount"),
            "income_currency": _role("normalized_values.currency", "currency_code"),
            "income_date": _role("normalized_values.date", "date"),
            "income_subtype": _role("extracted_fields.income_type_candidate", "categorical_direction", "short_visible_label"),
            "income_source_country": _role("extracted_fields.source_country_value_refs", "short_visible_label"),
        },
        "required_roles": ["income_amount"],
        "required_role_groups": [],
        "required_relation_kinds": [],
        "candidate_reuse": {},
        "subtypes": ["dividend", "coupon", "interest", "sale_proceeds", "other", "unknown"],
    },
    "withholding_tax": {
        "roles": {
            "tax_amount": _role("normalized_values.amount", "decimal_amount"),
            "tax_currency": _role("normalized_values.currency", "currency_code"),
            "tax_date": _role("normalized_values.date", "date"),
            "tax_country": _role("normalized_values.label", "short_visible_label"),
        },
        "required_roles": ["tax_amount", "tax_currency"],
        "required_role_groups": [],
        "required_relation_kinds": ["amount_with_currency"],
        "required_relation_role_sets": {
            "amount_with_currency": ["tax_amount", "tax_currency"],
        },
        "candidate_reuse": {},
        "subtypes": ["domestic", "foreign", "unknown"],
    },
    "fee_commission": {
        "roles": {
            "fee_amount": _role("normalized_values.amount", "decimal_amount"),
            "fee_currency": _role("normalized_values.currency", "currency_code"),
            "fee_date": _role("normalized_values.date", "date"),
            "fee_subtype": _role("extracted_fields.fee_type_candidate", "categorical_direction", "short_visible_label"),
        },
        "required_roles": ["fee_amount"],
        "required_role_groups": [],
        "required_relation_kinds": [],
        "candidate_reuse": {},
        "subtypes": ["broker_commission", "exchange_fee", "custody_fee", "other", "unknown"],
    },
    "position_snapshot": {
        "roles": {
            "position_instrument": _role("normalized_values.identifier", "instrument_identifier", "instrument_label"),
            "position_quantity": _role("normalized_values.quantity", "quantity"),
            "position_valuation": _role("normalized_values.amount", "decimal_amount", "source_provided_total"),
            "position_currency": _role("normalized_values.currency", "currency_code"),
            "snapshot_date": _role("normalized_values.date", "date"),
        },
        "required_roles": ["position_instrument"],
        "required_role_groups": [["position_quantity", "position_valuation"]],
        "required_relation_kinds": [],
        "candidate_reuse": {},
        "subtypes": ["security_position", "cash_position", "other", "unknown"],
    },
    "trade_operation": {
        "roles": {
            "trade_direction": _role("extracted_fields.operation_type_candidate", "categorical_direction"),
            "trade_instrument": _role("normalized_values.identifier", "instrument_identifier", "instrument_label"),
            "trade_quantity": _role("normalized_values.quantity", "quantity"),
            "trade_amount": _role("normalized_values.amount", "decimal_amount"),
            "trade_price": _role("normalized_values.rate", "decimal_amount", "explicit_fx_rate"),
            "trade_date": _role("normalized_values.date", "date"),
            "trade_fee": _role("normalized_values.converted_amount", "decimal_amount"),
        },
        "required_roles": ["trade_direction", "trade_instrument"],
        "required_role_groups": [["trade_quantity", "trade_amount"]],
        "required_relation_kinds": [],
        "candidate_reuse": {},
        "subtypes": ["buy", "sell", "redemption", "transfer", "corporate_action", "unknown"],
    },
    "currency_fx": {
        "roles": {
            "base_amount": _role("normalized_values.amount", "decimal_amount"),
            "quote_amount": _role("normalized_values.converted_amount", "decimal_amount"),
            "base_currency": _role("normalized_values.currency", "currency_code"),
            "quote_currency": _role("normalized_values.label", "currency_code"),
            "explicit_rate": _role("normalized_values.rate", "explicit_fx_rate", "decimal_amount"),
            "rate_date": _role("normalized_values.date", "date"),
        },
        "required_roles": ["base_amount", "quote_amount", "base_currency", "quote_currency"],
        "required_role_groups": [],
        "required_relation_kinds": ["base_quote_amount_currency_group"],
        "required_relation_role_sets": {
            "base_quote_amount_currency_group": [
                "base_amount",
                "quote_amount",
                "base_currency",
                "quote_currency",
            ],
        },
        "candidate_reuse": {},
        "subtypes": ["currency_amount", "explicit_rate", "source_provided_conversion", "unknown"],
    },
    "document_summary_evidence": {
        "roles": {
            "summary_value": _role("normalized_values.amount", "source_provided_total", "decimal_amount"),
            "summary_currency": _role("normalized_values.currency", "currency_code"),
            "summary_date": _role("normalized_values.date", "date"),
            "summary_label": _role("normalized_values.label", "short_visible_label"),
        },
        "required_roles": ["summary_value"],
        "required_role_groups": [],
        "required_relation_kinds": [],
        "candidate_reuse": {},
        "subtypes": ["source_summary", "document_total", "section_total", "unknown"],
    },
    "unknown_source_row": {
        "roles": {},
        "required_roles": [],
        "required_role_groups": [],
        "required_relation_kinds": [],
        "candidate_reuse": {},
        "subtypes": ["unknown"],
    },
}


@dataclass(frozen=True)
class Gate2CandidateBindingConfig:
    max_candidates: int = 96
    max_relations: int = 128


class Gate2CandidateBindingKernelFactory:
    def __init__(self, config: Gate2CandidateBindingConfig | None = None) -> None:
        self.config = config or Gate2CandidateBindingConfig()

    def create(self) -> "Gate2CandidateBindingKernel":
        return Gate2CandidateBindingKernel(self.config)


class Gate2CandidateBindingKernel:
    def __init__(self, config: Gate2CandidateBindingConfig) -> None:
        self.config = config

    def build(self, package: dict[str, Any]) -> dict[str, Any]:
        domain = str(package.get("extractor_domain") or "")
        profile = candidate_binding_profile(domain)
        candidate_set = _discover_candidates(package, profile, self.config)
        relation_set = _discover_relations(package, candidate_set, profile, self.config)
        return {
            "candidate_set": candidate_set,
            "relation_set": relation_set,
            "profile": profile,
        }


def candidate_binding_profile(domain: str) -> dict[str, Any]:
    if domain not in DOMAIN_BINDING_PROFILES:
        raise ValueError("candidate_binding_profile_domain_invalid")
    value = copy.deepcopy(DOMAIN_BINDING_PROFILES[domain])
    value.setdefault("required_relation_role_sets", {})
    value.update(
        {
            "schema_version": BINDING_PROFILE_SCHEMA_VERSION,
            "profile_id": f"binding_profile_{domain}_v0",
            "domain": domain,
            "unknown_policy": "null_or_unknown_source_row",
            "ambiguity_policy": "explicit_model_resolution_required",
            "allowed_candidate_kinds": sorted(
                {
                    kind
                    for spec in _object(value.get("roles")).values()
                    for kind in _strings(_object(spec).get("candidate_kinds"))
                }
            ),
            "allowed_fact_field_paths": sorted(
                {
                    str(_object(spec).get("fact_field_path") or "")
                    for spec in _object(value.get("roles")).values()
                    if _object(spec).get("fact_field_path")
                }
            ),
            "optional_roles": sorted(
                set(_object(value.get("roles")))
                - set(_strings(value.get("required_roles")))
            ),
            "mutually_exclusive_role_groups": [],
            "role_cardinality": {
                role: {"minimum": 1 if role in _strings(value.get("required_roles")) else 0, "maximum": 1}
                for role in _object(value.get("roles"))
            },
            "candidate_reuse_policy": "forbidden_unless_explicitly_allowed",
            "optional_relation_kinds": [
                "same_row_candidate_group",
                "amount_with_currency",
                "quantity_with_instrument",
            ],
            "forbidden_relation_kinds": [],
            "minimum_evidence": {
                "source_value_refs_required": True,
                "value_checksum_refs_required": True,
                "single_source_row_required": True,
            },
            "completeness_policy": "complete_forbidden_when_linked_issues_limit_confirmation",
            "confidence_policy": "model_assigned_but_validator_bounded",
            "downstream_policy": "gate2_source_facts_only",
            "finalizer_semantic_choice_allowed": False,
            "tax_calculation_allowed": False,
            "declaration_mapping_allowed": False,
            "cross_document_consolidation_allowed": False,
        }
    )
    return value


def _discover_candidates(
    package: dict[str, Any],
    profile: dict[str, Any],
    config: Gate2CandidateBindingConfig,
) -> dict[str, Any]:
    unit = _object(package.get("source_unit"))
    projection = _object(unit.get("model_source_projection"))
    rows = _dict_list(projection.get("rows"))
    pseudo = copy.deepcopy(unit)
    pseudo["cells"] = copy.deepcopy(
        _object(unit.get("normalized_source_projection")).get("cells") or []
    )
    index_by_ref = {
        str(item.get("source_value_ref") or ""): item
        for item in _dict_list(unit.get("source_value_index"))
    }
    header_refs_by_label: dict[str, list[str]] = defaultdict(list)
    for item in _dict_list(unit.get("normalized_header_descriptors")):
        label = str(item.get("normalized_label") or "unknown")
        if item.get("header_ref"):
            header_refs_by_label[label].append(str(item["header_ref"]))

    candidates: list[dict[str, Any]] = []
    for row in rows:
        row_ref = str(row.get("row_ref") or "")
        row_role = str(row.get("row_role") or row.get("row_kind") or "data_row")
        operation_tokens = {
            str(cell.get("value") or "").strip().lower()
            for cell in _dict_list(row.get("cells"))
            if str(cell.get("value") or "").strip().lower() in _CATEGORICAL_TOKENS
        }
        for cell in _dict_list(row.get("cells")):
            source_value_ref = str(cell.get("source_value_ref") or "")
            if not source_value_ref or source_value_ref not in index_by_ref:
                continue
            header = str(cell.get("header_label") or "unknown")
            kinds: list[tuple[str, str]] = []
            if _can_reproduce(pseudo, source_value_ref, "decimal_dot"):
                if header == "quantity":
                    kinds.append(("quantity", "decimal_dot"))
                elif header == "rate":
                    kinds.append(("explicit_fx_rate", "decimal_dot"))
                else:
                    kinds.append(("decimal_amount", "decimal_dot"))
                if operation_tokens & {"explicit_fx_rate", "fx_rate", "currency_conversion"}:
                    kinds.append(("explicit_fx_rate", "decimal_dot"))
                if row_role in {"summary_row", "subtotal_row"}:
                    kinds.append(("source_provided_total", "decimal_dot"))
            if _can_reproduce(pseudo, source_value_ref, "iso_date_exact"):
                kinds.append(("date", "iso_date_exact"))
            if _can_reproduce(pseudo, source_value_ref, "currency_code_visible"):
                kinds.append(("currency_code", "currency_code_visible"))
            if _can_reproduce(pseudo, source_value_ref, "trimmed_text"):
                value = reproduce_normalized_value(pseudo, source_value_ref, "trimmed_text")
                if header == "instrument":
                    kinds.append(
                        (
                            "instrument_identifier"
                            if len(value) <= 32 and " " not in value
                            else "instrument_label",
                            "trimmed_text",
                        )
                    )
                if value and len(value) <= 64:
                    kinds.append(("short_visible_label", "trimmed_text"))
                    if value.strip().lower() in _CATEGORICAL_TOKENS:
                        kinds.append(("categorical_direction", "trimmed_text"))
                if not kinds and value and len(value) <= 64:
                    kinds.append(("unknown_mechanical_value", "trimmed_text"))
            for candidate_kind, normalization_kind in kinds:
                normalized_value = reproduce_normalized_value(
                    pseudo, source_value_ref, normalization_kind
                )
                allowed = _allowed_roles(profile, candidate_kind)
                if not allowed:
                    continue
                entry = index_by_ref[source_value_ref]
                candidate_id = "svcand_" + stable_digest(
                    [
                        package.get("package_id"),
                        row_ref,
                        cell.get("cell_ref"),
                        source_value_ref,
                        candidate_kind,
                        normalized_value,
                    ],
                    length=24,
                )
                candidates.append(
                    {
                        "candidate_id": candidate_id,
                        "candidate_kind": candidate_kind,
                        "document_ref": package.get("document_ref"),
                        "source_unit_ref": unit.get("unit_id"),
                        "table_projection_ref": unit.get("table_projection_id"),
                        "row_ref": row_ref,
                        "cell_refs": _strings([cell.get("cell_ref")]),
                        "source_value_refs": [source_value_ref],
                        "character_span_refs": [],
                        "column_ref": cell.get("column_ref"),
                        "column_ordinal": cell.get("column_ordinal"),
                        "header_refs": sorted(set(header_refs_by_label.get(header, []))),
                        "safe_header_descriptors": [header],
                        "normalized_value": normalized_value,
                        "normalization_kind": normalization_kind,
                        "value_checksum_refs": _strings([entry.get("value_checksum_ref")]),
                        "value_kind": candidate_kind,
                        "sign_evidence": _sign_evidence(normalized_value, candidate_kind),
                        "direction_evidence": sorted(operation_tokens & _CATEGORICAL_TOKENS),
                        "currency_context_refs": [],
                        "date_context_refs": [],
                        "instrument_context_refs": [],
                        "allowed_semantic_roles": sorted(allowed),
                        "allowed_fact_types": [profile["domain"]],
                        "allowed_fact_field_paths": sorted(
                            {profile["roles"][role]["fact_field_path"] for role in allowed}
                        ),
                        "ambiguity_group_ref": None,
                        "composite_group_ref": None,
                        "candidate_scope": "single_source_value",
                        "reason_codes": ["mechanically_reproducible_source_value"],
                        "evidence_quality": "high",
                        "visibility": "private_case",
                        "storage_backend": "project_artifact_payload",
                    }
                )
    candidates = _deduplicate_candidates(candidates)
    _assign_ambiguity_groups(candidates, package)
    if len(candidates) > config.max_candidates:
        raise ValueError("candidate_binding_candidate_budget_exceeded")
    candidate_set_id = "svcset_" + stable_digest(
        [package.get("package_id"), [item["candidate_id"] for item in candidates]],
        length=24,
    )
    return {
        "schema_version": CANDIDATE_SET_SCHEMA_VERSION,
        "candidate_set_id": candidate_set_id,
        "package_id": package.get("package_id"),
        "extractor_domain": profile["domain"],
        "candidates": candidates,
        "candidate_ids": [item["candidate_id"] for item in candidates],
        "candidate_set_hash": stable_digest(candidates, length=32),
        "max_candidates": config.max_candidates,
        "visibility": "private_case",
        "storage_backend": "project_artifact_payload",
        "validation_status": "passed",
    }


def _discover_relations(
    package: dict[str, Any],
    candidate_set: dict[str, Any],
    profile: dict[str, Any],
    config: Gate2CandidateBindingConfig,
) -> dict[str, Any]:
    by_row: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in _dict_list(candidate_set.get("candidates")):
        by_row[str(candidate.get("row_ref") or "")].append(candidate)
    relations: list[dict[str, Any]] = []
    for row_ref, candidates in sorted(by_row.items()):
        if len(candidates) > 1:
            relations.append(
                _relation(package, profile, row_ref, "same_row_candidate_group", candidates)
            )
        amounts = [item for item in candidates if item.get("candidate_kind") in {"decimal_amount", "source_provided_total"}]
        currencies = [item for item in candidates if item.get("candidate_kind") == "currency_code"]
        for amount in amounts:
            for currency in currencies:
                relations.append(
                    _relation(package, profile, row_ref, "amount_with_currency", [amount, currency])
                )
        quantities = [item for item in candidates if item.get("candidate_kind") == "quantity"]
        instruments = [item for item in candidates if item.get("candidate_kind") in {"instrument_identifier", "instrument_label"}]
        for quantity in quantities:
            for instrument in instruments:
                relations.append(
                    _relation(package, profile, row_ref, "quantity_with_instrument", [quantity, instrument])
                )
        if profile["domain"] == "currency_fx" and len(amounts) >= 2 and len(currencies) >= 2:
            ordered = sorted(
                [*amounts[:2], *currencies[:2]],
                key=lambda item: (int(item.get("column_ordinal") or 0), item["candidate_id"]),
            )
            relations.append(
                _relation(
                    package,
                    profile,
                    row_ref,
                    "base_quote_amount_currency_group",
                    ordered,
                )
            )
    relations = _deduplicate_relations(relations)
    if len(relations) > config.max_relations:
        raise ValueError("candidate_binding_relation_budget_exceeded")
    relation_set_id = "svrelset_" + stable_digest(
        [package.get("package_id"), [item["relation_id"] for item in relations]],
        length=24,
    )
    return {
        "schema_version": RELATION_SET_SCHEMA_VERSION,
        "relation_set_id": relation_set_id,
        "package_id": package.get("package_id"),
        "extractor_domain": profile["domain"],
        "relations": relations,
        "relation_ids": [item["relation_id"] for item in relations],
        "relation_set_hash": stable_digest(relations, length=32),
        "max_relations": config.max_relations,
        "visibility": "private_case",
        "storage_backend": "project_artifact_payload",
        "validation_status": "passed",
    }


def _relation(
    package: dict[str, Any],
    profile: dict[str, Any],
    row_ref: str,
    kind: str,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    ids = [item["candidate_id"] for item in candidates]
    relation_id = "svrel_" + stable_digest(
        [package.get("package_id"), row_ref, kind, sorted(ids)], length=24
    )
    return {
        "relation_id": relation_id,
        "candidate_ids": ids,
        "relation_kind": kind,
        "shared_source_scope": "same_row",
        "row_refs": [row_ref],
        "cell_refs": sorted({ref for item in candidates for ref in _strings(item.get("cell_refs"))}),
        "header_refs": sorted({ref for item in candidates for ref in _strings(item.get("header_refs"))}),
        "section_refs": [],
        "allowed_domains": [profile["domain"]],
        "allowed_semantic_role_combinations": [],
        "cardinality": {"minimum": len(ids), "maximum": len(ids)},
        "candidate_reuse_policy": "profile_controlled",
        "ambiguity_state": "explicit_selection_required",
        "reason_codes": ["mechanical_same_row_relation"],
        "validation_status": "passed",
    }


def _allowed_roles(profile: dict[str, Any], candidate_kind: str) -> list[str]:
    return [
        role
        for role, spec in _object(profile.get("roles")).items()
        if candidate_kind in _strings(_object(spec).get("candidate_kinds"))
    ]


def _can_reproduce(unit: dict[str, Any], ref: str, kind: str) -> bool:
    try:
        reproduce_normalized_value(unit, ref, kind)
    except ValueError:
        return False
    return True


def _sign_evidence(value: str, kind: str) -> str:
    if kind not in {"decimal_amount", "quantity", "explicit_fx_rate", "source_provided_total"}:
        return "not_applicable"
    if value.startswith("-"):
        return "negative_visible"
    if value.startswith("+"):
        return "positive_visible"
    return "unsigned_visible"


def _deduplicate_candidates(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(item["candidate_id"]): item for item in values}
    return [by_id[key] for key in sorted(by_id)]


def _assign_ambiguity_groups(candidates: list[dict[str, Any]], package: dict[str, Any]) -> None:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        groups[
            (
                str(item.get("row_ref") or ""),
                str(item.get("candidate_kind") or ""),
                str(item.get("normalized_value") or ""),
            )
        ].append(item)
    for key, values in groups.items():
        refs = {tuple(_strings(item.get("source_value_refs"))) for item in values}
        if len(values) < 2 or len(refs) < 2:
            continue
        group_ref = "svamb_" + stable_digest([package.get("package_id"), key, sorted(refs)], length=20)
        for item in values:
            item["ambiguity_group_ref"] = group_ref
            item["reason_codes"] = sorted(
                set(_strings(item.get("reason_codes")) + ["equal_value_distinct_source_refs"])
            )


def _deduplicate_relations(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(item["relation_id"]): item for item in values}
    return [by_id[key] for key in sorted(by_id)]


_CATEGORICAL_TOKENS = {
    "buy",
    "sell",
    "deposit",
    "withdrawal",
    "cash_deposit",
    "cash_withdrawal",
    "credit",
    "debit",
    "dividend",
    "coupon",
    "interest",
    "withholding",
    "withholding_tax",
    "broker_commission",
    "exchange_fee",
    "custody_fee",
    "explicit_fx_rate",
    "position_snapshot",
    "source_summary",
}


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)] if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in value or [] if item is not None and str(item)] if isinstance(value, list) else []
