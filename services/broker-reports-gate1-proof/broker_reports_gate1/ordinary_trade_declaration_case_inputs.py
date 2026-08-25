"""Owner-bound case inputs for the bounded interactive declaration product."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any

from .artifact_models import ArtifactAccessContext, ArtifactStorePort, RetentionPolicy
from .gate3_metadata_source_facts import Gate3MetadataSourceFactRuntimeFactory
from .gate5_full_target_xml_projection import Gate5FullTargetXmlProjectionRuntimeFactory
from .gate5_human_gap_closure import Gate5HumanGapClosureRuntimeFactory
from .gate5_trusted_methodology import (
    Gate5TrustedMethodologyAuthorityFactory,
    Gate5TrustedMethodologyError,
)


ORDINARY_TRADE_DECLARATION_CASE_INPUTS_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_declaration_case_inputs_v1"
)
FACTORY_REQUIRED = (
    "OrdinaryTradeDeclarationCaseInputsRuntimeFactory.create composes the "
    "current Canonical metadata owner, Gate5HumanGapClosureRuntime and the "
    "pinned Gate5 methodology authority",
)
FORBIDDEN = (
    "caller-selected taxpayer scope, raw answer dictionary, case hash as INN, "
    "human-authored source or legal conclusion, external provider fallback",
)

_SOURCE_TYPES = {
    "BROKER_LEGAL_NAME": "broker_name",
    "BROKER_TAX_IDENTIFIER": "broker_inn",
    "BROKER_KPP": "broker_kpp",
    "BROKER_OKTMO": "broker_oktmo",
    "PAYER_ORGANIZATION_JURISDICTION": "payer_organization_jurisdiction",
    "REALIZATION_LOCATION_JURISDICTION": "realization_location_jurisdiction",
    "ADMITTED_EXCHANGE_FACT": "admitted_exchange_fact",
    "MARKET_QUOTATION_FACT": "market_quotation_fact",
    "IIS_STATUS_ASSERTION": "iis_status_assertion",
    "EXEMPTION_SOURCE_ASSERTION": "exemption_source_assertion",
}
_LEXICAL = {
    "payer_organization_jurisdiction": {"RU": "RU", "РФ": "RU"},
    "realization_location_jurisdiction": {"RU": "RU", "РФ": "RU"},
    "admitted_exchange_fact": {"ADMITTED": "ADMITTED", "ДОПУЩЕНА": "ADMITTED"},
    "market_quotation_fact": {"AVAILABLE": "AVAILABLE", "ИМЕЕТСЯ": "AVAILABLE"},
    "iis_status_assertion": {"OUTSIDE_IIS": "OUTSIDE_IIS", "ВНЕ ИИС": "OUTSIDE_IIS"},
    "exemption_source_assertion": {"NONE": "NONE", "НЕТ": "NONE"},
}


class OrdinaryTradeDeclarationCaseInputsError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class OrdinaryTradeDeclarationCaseInputsRuntimeFactory:
    def __init__(
        self,
        *,
        store: ArtifactStorePort,
        read_enabled: bool,
        retention_policy: RetentionPolicy,
    ) -> None:
        self._store = store
        self._read_enabled = read_enabled
        self._retention_policy = retention_policy

    def create(self) -> "OrdinaryTradeDeclarationCaseInputsRuntime":
        profile_owner = Gate5FullTargetXmlProjectionRuntimeFactory.create()
        return OrdinaryTradeDeclarationCaseInputsRuntime(
            metadata=Gate3MetadataSourceFactRuntimeFactory(
                store=self._store,
                read_enabled=self._read_enabled,
            ).create(),
            human=Gate5HumanGapClosureRuntimeFactory.create(
                store=self._store,
                retention_policy=self._retention_policy,
            ),
            available_profiles=[profile_owner.supported_profile()],
        )


class OrdinaryTradeDeclarationCaseInputsRuntime:
    def __init__(
        self,
        *,
        metadata: Any,
        human: Any,
        available_profiles: list[dict[str, Any]],
    ) -> None:
        self._metadata = metadata
        self._human = human
        self._methodology = Gate5TrustedMethodologyAuthorityFactory.create()
        self._available_profiles = _validated_available_profiles(available_profiles)

    def current(
        self,
        *,
        context: ArtifactAccessContext,
        canonical_coverage: dict[str, Any],
        operation_period_observation: dict[str, Any],
    ) -> dict[str, Any]:
        taxpayer_scope_ref = primary_taxpayer_scope_ref(context=context)
        detected_years = _detected_operation_years(operation_period_observation)
        metadata = self._metadata.collect_current(
            context=context,
            canonical_coverage=canonical_coverage,
        )
        identity_candidates = [
            item
            for item in metadata["metadata_facts"]
            if item.get("fact_type") in {"TAXPAYER_TAX_IDENTIFIER", "PARTY_NAME"}
        ]
        period_selection = self._human.publish_tax_period_selection_request(
            context=context,
            taxpayer_scope_ref=taxpayer_scope_ref,
            detected_operation_years=detected_years,
        )
        selected_fact = period_selection["selected_tax_period_fact"]
        if selected_fact is None:
            return {
                "schema_version": ORDINARY_TRADE_DECLARATION_CASE_INPUTS_SCHEMA_VERSION,
                "taxpayer_scope_ref": taxpayer_scope_ref,
                "tax_period": None,
                "tax_period_selection": period_selection,
                "profile_support": "NOT_EVALUATED",
                "available_profiles": copy.deepcopy(self._available_profiles),
                "profile_mismatch_mode": None,
                "human_fact_publication": {
                    "schema_version": "broker_reports_ordinary_trade_user_actions_v1",
                    "status": "OWNER_PUBLISHED",
                    "scope_binding": period_selection["scope_binding"],
                    "actions": period_selection["actions"],
                    "current_user_case_facts": [],
                    "provider_calls_total": 0,
                },
                "human_facts": [],
                "source_metadata_collection": metadata,
                "source_inputs": {},
                "methodology_inputs": None,
                "internal_blockers": [],
                "provider_calls_total": 0,
            }
        tax_period = str(selected_fact["value"]["value"])
        source, blockers = _source_inputs(metadata["metadata_facts"])
        methodology = None
        profile_support = (
            "NOT_EVALUATED"
            if blockers
            else "SUPPORTED"
            if any(item["tax_period"] == tax_period for item in self._available_profiles)
            else "UNSUPPORTED_EXACT_YEAR_PROFILE"
        )
        mismatch_mode = None
        if not blockers and profile_support == "SUPPORTED":
            try:
                methodology = self._methodology.resolve_ordinary_trade_declaration_product(
                    source_assertions={
                        key: source[key]
                        for key in (
                            "admitted_exchange_fact",
                            "market_quotation_fact",
                            "iis_status_assertion",
                            "exemption_source_assertion",
                            "payer_organization_jurisdiction",
                            "realization_location_jurisdiction",
                        )
                    },
                    tax_period=tax_period,
                )
            except Gate5TrustedMethodologyError as exc:
                blockers.append(
                    {
                        "reason_code": exc.code,
                        "gap_owner_classification": "METHODOLOGY_RULE_MISSING",
                        "owner": "Gate5TrustedMethodologyAuthority",
                    }
                )
        if profile_support == "UNSUPPORTED_EXACT_YEAR_PROFILE":
            mode_publication = self._human.publish_profile_mismatch_mode_request(
                context=context,
                taxpayer_scope_ref=taxpayer_scope_ref,
                tax_period=tax_period,
                available_profiles=self._available_profiles,
            )
            mode_fact = mode_publication["selected_mode_fact"]
            mismatch_mode = (
                None if mode_fact is None else str(mode_fact["value"]["value"])
            )
        if profile_support == "UNSUPPORTED_EXACT_YEAR_PROFILE":
            facts = self._human.current_user_case_facts(
                context=context,
                taxpayer_scope_ref=taxpayer_scope_ref,
                tax_period=tax_period,
            )
            publication = {
                "schema_version": "broker_reports_ordinary_trade_user_actions_v1",
                "status": "OWNER_PUBLISHED",
                "scope_binding": mode_publication["scope_binding"],
                "actions": mode_publication["actions"],
                "current_user_case_facts": facts,
                "provider_calls_total": 0,
            }
        else:
            publication = self._human.publish_ordinary_trade_declaration_requests(
                context=context,
                taxpayer_scope_ref=taxpayer_scope_ref,
                tax_period=tax_period,
                identity_candidates=identity_candidates,
            )
            facts = publication["current_user_case_facts"]
        return {
            "schema_version": ORDINARY_TRADE_DECLARATION_CASE_INPUTS_SCHEMA_VERSION,
            "taxpayer_scope_ref": taxpayer_scope_ref,
            "tax_period": tax_period,
            "tax_period_selection": period_selection,
            "profile_support": profile_support,
            "available_profiles": copy.deepcopy(self._available_profiles),
            "profile_mismatch_mode": mismatch_mode,
            "human_fact_publication": publication,
            "human_facts": facts,
            "source_metadata_collection": metadata,
            "source_inputs": source,
            "methodology_inputs": methodology,
            "internal_blockers": blockers,
            "provider_calls_total": 0,
        }

    def normalize_action(
        self,
        *,
        request_publication_ref: str,
        answer: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        return self._human.normalize_published_answer(
            request_publication_ref=request_publication_ref,
            answer=answer,
            context=context,
        )

    def publish_change_action(
        self,
        *,
        context: ArtifactAccessContext,
        canonical_coverage: dict[str, Any],
        fact_key: str,
    ) -> dict[str, Any]:
        """Ask the Human owner to mint a successor for a bounded fact change."""

        metadata = self._metadata.collect_current(
            context=context,
            canonical_coverage=canonical_coverage,
        )
        del metadata
        taxpayer_scope_ref = primary_taxpayer_scope_ref(context=context)
        selected_period_facts = self._human.current_user_case_facts(
            context=context,
            taxpayer_scope_ref=taxpayer_scope_ref,
            tax_period="0000",
        )
        selected_period = next(
            (
                str(item["value"]["value"])
                for item in selected_period_facts
                if item["fact_key"] == "selected_tax_period"
            ),
            None,
        )
        if selected_period is None:
            raise OrdinaryTradeDeclarationCaseInputsError(
                "ordinary_trade_selected_tax_period_missing"
            )
        return self._human.publish_user_case_fact_change_request(
            context=context,
            taxpayer_scope_ref=taxpayer_scope_ref,
            tax_period=("0000" if fact_key == "selected_tax_period" else selected_period),
            fact_key=fact_key,
        )


def primary_taxpayer_scope_ref(*, context: ArtifactAccessContext) -> str:
    """Mint a private workflow slot; this value is explicitly not identity."""

    if (
        not isinstance(context, ArtifactAccessContext)
        or not context.allow_private
        or not context.user_id
        or not context.case_id
    ):
        raise OrdinaryTradeDeclarationCaseInputsError(
            "ordinary_trade_taxpayer_slot_context_required"
        )
    material = json.dumps(
        {
            "owner": "Gate5HumanGapClosureRuntime",
            "slot_kind": "primary_user_attested_taxpayer",
            "authenticated_user_ref": context.user_id,
            "case_id": context.case_id,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "taxpayer_slot_" + hashlib.sha256(material).hexdigest()[:32]


def _detected_operation_years(value: Any) -> list[str]:
    years = value.get("observed_operation_years") if isinstance(value, dict) else None
    if (
        not isinstance(years, list)
        or years != sorted(set(years))
        or any(re.fullmatch(r"[0-9]{4}", item) is None for item in years)
    ):
        raise OrdinaryTradeDeclarationCaseInputsError(
            "ordinary_trade_operation_period_observation_invalid"
        )
    return copy.deepcopy(years)


def _validated_available_profiles(value: Any) -> list[dict[str, Any]]:
    required = {
        "profile_id",
        "profile_version",
        "tax_period",
        "form",
        "knd",
        "order",
        "electronic_format_version",
        "xsd_name",
        "xsd_sha256",
    }
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, dict) or set(item) != required for item in value)
        or any(
            not isinstance(item["tax_period"], str)
            or re.fullmatch(r"[0-9]{4}", item["tax_period"]) is None
            or item["tax_period"] == "0000"
            or not all(
                isinstance(item[key], str) and item[key]
                for key in required - {"tax_period"}
            )
            or re.fullmatch(r"[0-9a-f]{64}", item["xsd_sha256"]) is None
            for item in value
        )
        or len({item["tax_period"] for item in value}) != len(value)
    ):
        raise OrdinaryTradeDeclarationCaseInputsError(
            "ordinary_trade_available_profiles_invalid"
        )
    return sorted(copy.deepcopy(value), key=lambda item: item["tax_period"])


def _source_inputs(
    facts: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    indexed: dict[str, list[dict[str, Any]]] = {}
    for fact in facts:
        key = _SOURCE_TYPES.get(str(fact.get("fact_type") or ""))
        if key is not None:
            indexed.setdefault(key, []).append(fact)
    values: dict[str, Any] = {}
    refs: dict[str, str] = {}
    blockers: list[dict[str, Any]] = []
    for fact_type, key in _SOURCE_TYPES.items():
        candidates = indexed.get(key, [])
        if len(candidates) != 1:
            blockers.append(
                {
                    "reason_code": (
                        "ordinary_trade_declaration_source_fact_missing"
                        if not candidates
                        else "ordinary_trade_declaration_source_fact_ambiguous"
                    ),
                    "required_source_fact_type": fact_type,
                    "gap_owner_classification": "REAL_SOURCE_EVIDENCE_MISSING",
                    "owner": "Gate3MetadataSourceFactRuntime",
                }
            )
            continue
        try:
            literal = candidates[0]["value"]["normalized"]
            value = _LEXICAL.get(key, {}).get(literal, literal)
            if not isinstance(value, str) or not value:
                raise ValueError
            values[key] = value
            refs[key] = candidates[0]["fact_id"]
        except (KeyError, TypeError, ValueError):
            blockers.append(
                {
                    "reason_code": "ordinary_trade_declaration_source_fact_invalid",
                    "required_source_fact_type": fact_type,
                    "gap_owner_classification": "REAL_SOURCE_EVIDENCE_MISSING",
                    "owner": "Gate3MetadataSourceFactRuntime",
                }
            )
    values["source_fact_refs"] = refs
    if not blockers and (
        re.fullmatch(r"[0-9]{10}", values["broker_inn"]) is None
        or re.fullmatch(r"[0-9]{9}", values["broker_kpp"]) is None
        or re.fullmatch(r"[0-9]{8}(?:[0-9]{3})?", values["broker_oktmo"])
        is None
    ):
        blockers.append(
            {
                "reason_code": "ordinary_trade_declaration_source_party_invalid",
                "gap_owner_classification": "REAL_SOURCE_EVIDENCE_MISSING",
                "owner": "Gate3MetadataSourceFactRuntime",
            }
        )
    return copy.deepcopy(values), blockers


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "ORDINARY_TRADE_DECLARATION_CASE_INPUTS_SCHEMA_VERSION",
    "OrdinaryTradeDeclarationCaseInputsError",
    "OrdinaryTradeDeclarationCaseInputsRuntime",
    "OrdinaryTradeDeclarationCaseInputsRuntimeFactory",
    "primary_taxpayer_scope_ref",
]
