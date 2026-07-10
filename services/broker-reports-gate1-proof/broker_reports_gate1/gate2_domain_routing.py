from __future__ import annotations

import copy
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from .contracts import stable_digest
from .gate2_source_fact_contracts import FACT_TYPES


ROUTE_SCHEMA_VERSION = "broker_reports_source_unit_domain_route_v0"
ROUTING_POLICY_VERSION = "gate2_source_unit_domain_routing_v1"
FALLBACK_DOMAIN = "unknown_source_row"

FACT_DOMAIN_ORDER = (
    "trade_operation",
    "income",
    "withholding_tax",
    "fee_commission",
    "cash_movement",
    "currency_fx",
    "position_snapshot",
    "document_summary_evidence",
    FALLBACK_DOMAIN,
)
DOMAIN_EXTRACTOR_IDS = {
    domain: f"{domain}_extractor" for domain in FACT_DOMAIN_ORDER
}
DOMAIN_ALLOWED_FACT_TYPES = {
    domain: [domain] if domain == FALLBACK_DOMAIN else [domain, FALLBACK_DOMAIN]
    for domain in FACT_DOMAIN_ORDER
}

FACTORY_REQUIRED = (
    "Gate2SourceUnitRouterFactory.create is the only production source-unit routing entrypoint"
)
FORBIDDEN = (
    "Pipes, prompts and model outputs must not assign final row ownership or bypass the deterministic router"
)


@dataclass(frozen=True)
class Gate2SourceUnitRouterConfig:
    max_candidate_domains: int = 2


class Gate2SourceUnitRouterFactory:
    def __init__(self, config: Gate2SourceUnitRouterConfig | None = None) -> None:
        self.config = config or Gate2SourceUnitRouterConfig()

    def create(self) -> "Gate2SourceUnitRouter":
        if self.config.max_candidate_domains not in {1, 2}:
            raise ValueError("gate2_domain_router_candidate_limit_invalid")
        return Gate2SourceUnitRouter(self.config)


class Gate2SourceUnitRouter:
    def __init__(self, config: Gate2SourceUnitRouterConfig) -> None:
        self.config = config

    def route(self, package: dict[str, Any]) -> dict[str, Any]:
        source_unit = _object(package.get("source_unit"))
        unit_ref = str(source_unit.get("unit_id") or "")
        selected_refs = _string_list(
            _object(package.get("coverage_expectation")).get("selected_source_refs")
        )
        mandatory_no_fact = {
            str(item.get("source_ref") or ""): str(item.get("reason_code") or "")
            for item in _dict_list(
                _object(package.get("coverage_expectation")).get(
                    "mandatory_no_fact_results"
                )
            )
            if item.get("source_ref")
        }
        rows = {
            str(item.get("row_ref") or ""): item
            for item in _dict_list(
                _object(source_unit.get("model_source_projection")).get("rows")
            )
            if item.get("row_ref")
        }
        segments = {
            str(item.get("text_segment_ref") or ""): item
            for item in _dict_list(
                _object(source_unit.get("model_source_projection")).get("segments")
            )
            if item.get("text_segment_ref")
        }
        header_signals = sorted(
            {
                str(item.get("normalized_label") or "unknown")
                for item in _dict_list(source_unit.get("normalized_header_descriptors"))
            }
        )
        entries: list[dict[str, Any]] = []
        for source_ref in selected_refs:
            if source_ref in mandatory_no_fact:
                entries.append(
                    self._no_fact_entry(
                        source_ref=source_ref,
                        reason_code=mandatory_no_fact[source_ref],
                        header_signals=header_signals,
                        package=package,
                    )
                )
            elif source_ref in rows:
                entries.append(
                    self._route_row(
                        source_ref=source_ref,
                        row=rows[source_ref],
                        header_signals=header_signals,
                        package=package,
                    )
                )
            elif source_ref in segments:
                entries.append(
                    self._route_segment(
                        source_ref=source_ref,
                        segment=segments[source_ref],
                        header_signals=header_signals,
                        package=package,
                    )
                )
            else:
                entries.append(
                    self._unknown_entry(
                        source_ref=source_ref,
                        source_kind="unprojected_selected_ref",
                        header_signals=header_signals,
                        value_kinds=[],
                        package=package,
                        reason_codes=["selected_ref_missing_from_model_projection"],
                    )
                )

        route_id = f"sfroute_{stable_digest([package.get('extraction_run_id'), package.get('package_id'), unit_ref, selected_refs, ROUTING_POLICY_VERSION], length=24)}"
        route = {
            "schema_version": ROUTE_SCHEMA_VERSION,
            "route_id": route_id,
            "extraction_run_id": package.get("extraction_run_id"),
            "normalization_run_id": package.get("normalization_run_id"),
            "case_id": package.get("case_id"),
            "document_ref": package.get("document_ref"),
            "source_unit_ref": unit_ref,
            "base_package_id": package.get("package_id"),
            "routing_policy_version": ROUTING_POLICY_VERSION,
            "fallback_domain": FALLBACK_DOMAIN,
            "route_entries": entries,
            "selected_source_refs": selected_refs,
            "issue_refs": sorted(_string_list(package.get("allowed_issue_refs"))),
            "ownership_policy": {
                "policy_id": "gate2_single_owner_or_explicit_conflict_v0",
                "silent_double_claim_allowed": False,
                "explicit_multi_fact_rule_ids": [],
                "unknown_is_coverage_preserving": True,
            },
            "coverage": {
                "selected_total": len(selected_refs),
                "routed_total": len(entries),
                "deterministic_no_fact_total": sum(
                    1 for item in entries if item["route_kind"] == "deterministic_no_fact"
                ),
                "unknown_total": sum(
                    1 for item in entries if item["primary_suggested_domain"] == FALLBACK_DOMAIN
                ),
                "ambiguous_total": sum(
                    1 for item in entries if len(item["candidate_domains"]) > 1
                ),
                "all_selected_refs_routed": len(entries) == len(selected_refs),
            },
        }
        validate_source_unit_domain_route(route)
        return route

    def _route_row(
        self,
        *,
        source_ref: str,
        row: dict[str, Any],
        header_signals: list[str],
        package: dict[str, Any],
    ) -> dict[str, Any]:
        scores: defaultdict[str, int] = defaultdict(int)
        reasons: defaultdict[str, list[str]] = defaultdict(list)
        hint = str(row.get("fact_type_hint") or "")
        if hint in FACT_TYPES:
            scores[hint] += 100
            reasons[hint].append("exact_fact_type_hint")

        segment_signal = _object(
            _object(package.get("source_unit")).get("safe_segment_signals")
        )
        segment_domain = str(segment_signal.get("uniform_primary_domain") or "")
        if (
            segment_signal.get("signal_policy")
            == "parent_route_contiguous_cluster_v0"
            and segment_signal.get("confidence") == "high"
            and segment_domain in FACT_TYPES
            and segment_domain != FALLBACK_DOMAIN
            and _string_list(segment_signal.get("candidate_domains"))
            == [segment_domain]
        ):
            scores[segment_domain] += 100
            reasons[segment_domain].append(
                "derived_segment_uniform_high_confidence_domain"
            )

        cells = _dict_list(row.get("cells"))
        for cell in cells:
            header = str(cell.get("header_label") or "unknown").strip().lower()
            token = _safe_token(cell.get("value"))
            for domain in _domains_for_exact_visible_token(token):
                scores[domain] += 80
                reasons[domain].append(f"visible_label:{domain}")
            for domain in _domains_for_header(header):
                scores[domain] += 35
                reasons[domain].append(f"header_signal:{header}")

        for header in header_signals:
            for domain in _domains_for_header(header):
                scores[domain] += 20
                reasons[domain].append(f"unit_header_signal:{header}")

        value_kinds = sorted(
            {
                kind
                for cell in cells
                for kind in _safe_value_kinds(cell.get("value"))
            }
        )
        ranked = sorted(
            scores,
            key=lambda domain: (-scores[domain], FACT_DOMAIN_ORDER.index(domain)),
        )
        if not ranked:
            return self._unknown_entry(
                source_ref=source_ref,
                source_kind="table_row",
                header_signals=header_signals,
                value_kinds=value_kinds,
                package=package,
                reason_codes=["no_safe_domain_signal"],
            )
        top_score = scores[ranked[0]]
        candidates = [
            domain for domain in ranked if scores[domain] >= max(top_score - 20, 35)
        ][: self.config.max_candidate_domains]
        primary = candidates[0]
        confidence = "high" if top_score >= 80 and len(candidates) == 1 else (
            "medium" if top_score >= 55 else "low"
        )
        return self._entry(
            source_ref=source_ref,
            source_kind="table_row",
            route_kind="model_candidate",
            header_signals=header_signals,
            value_kinds=value_kinds,
            candidate_domains=candidates,
            primary=primary,
            package=package,
            reason_codes=sorted(set(reasons[primary] + (["ambiguous_domain_signals"] if len(candidates) > 1 else []))),
            confidence=confidence,
        )

    def _route_segment(
        self,
        *,
        source_ref: str,
        segment: dict[str, Any],
        header_signals: list[str],
        package: dict[str, Any],
    ) -> dict[str, Any]:
        token = _safe_token(segment.get("value"))
        domains = _domains_for_exact_visible_token(token)
        if not domains:
            domains = ["document_summary_evidence"]
            reasons = ["text_segment_default_summary_evidence"]
            confidence = "low"
        else:
            domains = domains[: self.config.max_candidate_domains]
            reasons = ["text_visible_domain_helper_signal"]
            confidence = "medium"
        return self._entry(
            source_ref=source_ref,
            source_kind="text_segment",
            route_kind="model_candidate",
            header_signals=header_signals,
            value_kinds=_safe_value_kinds(segment.get("value")),
            candidate_domains=domains,
            primary=domains[0],
            package=package,
            reason_codes=reasons,
            confidence=confidence,
        )

    def _no_fact_entry(
        self,
        *,
        source_ref: str,
        reason_code: str,
        header_signals: list[str],
        package: dict[str, Any],
    ) -> dict[str, Any]:
        return self._entry(
            source_ref=source_ref,
            source_kind="coverage_only",
            route_kind="deterministic_no_fact",
            header_signals=header_signals,
            value_kinds=[],
            candidate_domains=[],
            primary=None,
            package=package,
            reason_codes=[reason_code],
            confidence="high",
        )

    def _unknown_entry(
        self,
        *,
        source_ref: str,
        source_kind: str,
        header_signals: list[str],
        value_kinds: list[str],
        package: dict[str, Any],
        reason_codes: list[str],
    ) -> dict[str, Any]:
        return self._entry(
            source_ref=source_ref,
            source_kind=source_kind,
            route_kind="model_candidate",
            header_signals=header_signals,
            value_kinds=value_kinds,
            candidate_domains=[FALLBACK_DOMAIN],
            primary=FALLBACK_DOMAIN,
            package=package,
            reason_codes=reason_codes,
            confidence="low",
        )

    def _entry(
        self,
        *,
        source_ref: str,
        source_kind: str,
        route_kind: str,
        header_signals: list[str],
        value_kinds: list[str],
        candidate_domains: list[str],
        primary: str | None,
        package: dict[str, Any],
        reason_codes: list[str],
        confidence: str,
    ) -> dict[str, Any]:
        return {
            "source_ref": source_ref,
            "source_kind": source_kind,
            "route_kind": route_kind,
            "safe_header_signals": copy.deepcopy(header_signals),
            "safe_source_signals": {
                "value_kinds": sorted(set(value_kinds)),
                "passport_document_kind": _object(
                    _object(package.get("document_context")).get("passport")
                ).get("document_kind_candidate"),
                "usage_modes": sorted(
                    _string_list(
                        _object(package.get("document_context")).get("usage_modes")
                    )
                ),
                "fact_type_hint_present": "exact_fact_type_hint" in reason_codes,
                "derived_segment_signal_present": (
                    "derived_segment_uniform_high_confidence_domain"
                    in reason_codes
                ),
            },
            "candidate_domains": candidate_domains,
            "primary_suggested_domain": primary,
            "allowed_extractor_ids": [
                DOMAIN_EXTRACTOR_IDS[domain] for domain in candidate_domains
            ],
            "issue_refs": sorted(_string_list(package.get("allowed_issue_refs"))),
            "reason_codes": reason_codes,
            "confidence": confidence,
            "fallback_domain": FALLBACK_DOMAIN,
            "multi_fact_rule_id": None,
        }


def validate_source_unit_domain_route(route: dict[str, Any]) -> None:
    if route.get("schema_version") != ROUTE_SCHEMA_VERSION:
        raise ValueError("gate2_domain_route_schema_mismatch")
    selected = _string_list(route.get("selected_source_refs"))
    entries = _dict_list(route.get("route_entries"))
    refs = [str(item.get("source_ref") or "") for item in entries]
    if refs != selected or len(refs) != len(set(refs)):
        raise ValueError("gate2_domain_route_coverage_mismatch")
    for item in entries:
        candidates = _string_list(item.get("candidate_domains"))
        if not set(candidates) <= set(FACT_DOMAIN_ORDER):
            raise ValueError("gate2_domain_route_domain_invalid")
        if item.get("route_kind") == "model_candidate" and not candidates:
            raise ValueError("gate2_domain_route_candidate_missing")
        if item.get("route_kind") == "deterministic_no_fact" and candidates:
            raise ValueError("gate2_domain_route_no_fact_claim_invalid")
        if item.get("primary_suggested_domain") not in candidates + [None]:
            raise ValueError("gate2_domain_route_primary_invalid")


def _domains_for_header(header: str) -> list[str]:
    value = _safe_token(header)
    result = []
    mappings = {
        "trade_operation": {"trade_type", "deal_type", "buy_sell"},
        "income": {"income", "dividend", "coupon", "interest"},
        "withholding_tax": {"withholding", "withheld_tax", "tax_withheld"},
        "fee_commission": {"fee", "commission", "broker_commission", "exchange_fee"},
        "cash_movement": {"cash", "debit", "credit", "deposit", "withdrawal"},
        "currency_fx": {"fx", "fx_rate", "exchange_rate", "converted_amount"},
        "position_snapshot": {"position", "balance", "opening_balance", "closing_balance"},
        "document_summary_evidence": {"summary", "total", "period"},
    }
    for domain in FACT_DOMAIN_ORDER:
        if domain != FALLBACK_DOMAIN and value in mappings.get(domain, set()):
            result.append(domain)
    return result


def _domains_for_exact_visible_token(token: str) -> list[str]:
    mappings = {
        "trade_operation": {
            "buy", "sell", "redemption", "trade", "purchase", "sale",
            "покупка", "продажа", "погашение", "сделка",
        },
        "income": {
            "dividend", "coupon", "interest", "income", "sale_proceeds",
            "дивиденд", "дивиденды", "купон", "процент", "проценты", "доход",
        },
        "withholding_tax": {
            "withholding", "withholding_tax", "tax_withheld", "withheld_tax",
            "удержание_налога", "налог_удержан", "удержанный_налог", "налог",
        },
        "fee_commission": {
            "fee", "commission", "broker_commission", "exchange_fee", "custody_fee",
            "комиссия", "комиссия_брокера", "биржевой_сбор", "сбор",
        },
        "cash_movement": {
            "cash_deposit", "cash_withdrawal", "cash_credit", "cash_debit", "deposit", "withdrawal",
            "зачисление", "списание", "пополнение", "вывод", "ввод_денежных_средств", "вывод_денежных_средств",
        },
        "currency_fx": {
            "explicit_fx_rate", "fx_rate", "currency_conversion", "exchange_rate",
            "конвертация", "конвертация_валюты", "обмен_валюты", "курс_валюты",
        },
        "position_snapshot": {
            "position_snapshot", "security_position", "cash_position", "opening_balance", "closing_balance",
            "позиция", "позиции", "остаток", "остаток_на_начало", "остаток_на_конец",
        },
        "document_summary_evidence": {
            "source_summary", "document_summary", "summary", "total",
            "итого", "всего", "сводка",
        },
        FALLBACK_DOMAIN: {
            "unclassified_source_row", "unknown", "unsupported", "ambiguous",
            "неизвестно", "не_классифицировано",
        },
    }
    result = {
        domain for domain in FACT_DOMAIN_ORDER if token in mappings.get(domain, set())
    }
    helper_stems = {
        "trade_operation": ("покуп", "продаж", "погаш", "buy", "sell", "redempt"),
        "income": ("дивид", "купон", "процент", "доход", "dividend", "coupon", "interest"),
        "withholding_tax": ("удерж", "налог", "withhold", "tax_withheld"),
        "fee_commission": ("комисс", "сбор", "commission", "fee"),
        "cash_movement": ("зачисл", "списан", "пополн", "вывод", "cash_deposit", "cash_withdraw"),
        "currency_fx": ("конверт", "обмен_валют", "курс_валют", "currency_conversion", "fx_rate"),
        "position_snapshot": ("позици", "остат", "position", "balance"),
        "document_summary_evidence": ("итог", "всего", "свод", "summary", "total"),
    }
    for domain, stems in helper_stems.items():
        if any(stem in token for stem in stems):
            result.add(domain)
    return [domain for domain in FACT_DOMAIN_ORDER if domain in result]


def _safe_token(value: Any) -> str:
    return re.sub(
        r"_+",
        "_",
        re.sub(r"[^\w]+", "_", str(value or "").strip().lower(), flags=re.UNICODE),
    ).strip("_")


def _safe_value_kinds(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return ["blank"]
    kinds = []
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text.replace(" ", "")):
        kinds.append("decimal_like")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        kinds.append("iso_date_like")
    if re.fullmatch(r"[A-Z]{3}", text):
        kinds.append("currency_code_like")
    if re.fullmatch(r"[A-Z]{2}[A-Z0-9]{10}", text):
        kinds.append("isin_like")
    if not kinds:
        kinds.append("text")
    return kinds


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)] if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value or [] if item is not None and str(item)] if isinstance(value, list) else []
