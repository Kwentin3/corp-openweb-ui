"""Resolve closed hash-pinned methodologies and retain the G5.7 adapter."""

from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
from importlib import resources
import json
from typing import Any

from .artifact_models import ArtifactAccessContext, ArtifactStorePort, RetentionPolicy
from .gate5_methodology_calculation import (
    GATE5_CALCULATION_METHODOLOGY_SCHEMA_VERSION,
    Gate5MethodologyCalculationRuntime,
    Gate5MethodologyCalculationRuntimeFactory,
)


GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION = (
    "broker_reports_gate5_trusted_methodology_ref_v0"
)
GATE5_TRUSTED_CALCULATION_RESULT_SCHEMA_VERSION = (
    "broker_reports_gate5_trusted_calculation_result_v0"
)
GATE5_TRUSTED_METHODOLOGY_AUTHORITY_OWNER = "repository_versioned_package_resource"
GATE5_TRUSTED_METHODOLOGY_ID = "ru-ndfl-securities-proof"
GATE5_TRUSTED_METHODOLOGY_VERSION = "2026.0-experimental"
GATE5_TRUSTED_METHODOLOGY_RESOURCE = (
    "gate5_tax_methodology.ru_ndfl_securities_proof.v0.json"
)
GATE5_TRUSTED_METHODOLOGY_RESOURCE_SHA256 = (
    "220844b6e39678b4e26e6f5ff4eec3784b0086213767f1444b832fe99cecf4e9"
)
GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_SCHEMA_VERSION = (
    "broker_reports_gate5_securities_disposal_tax_model_methodology_v0"
)
GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID = (
    "ru-ndfl-securities-tax-model-proof"
)
GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_VERSION = "2026.0-experimental"
GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_RESOURCE = (
    "gate5_tax_methodology.ru_ndfl_securities_tax_model_proof.v0.json"
)
GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_RESOURCE_SHA256 = (
    "a1b2db00a78e92e1b47d873b5841edd6c34794a09f0a483c0cb0bda3abd6fc63"
)
GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_SCHEMA_VERSION = (
    "broker_reports_gate5_securities_disposal_operation_tax_model_methodology_v0"
)
GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_VERSION = "2026.2-audited"
GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_RESOURCE = (
    "gate5_tax_methodology.ru_ndfl_securities_operation_tax_model_proof.v0.json"
)
GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_RESOURCE_SHA256 = (
    "d2070ad33a74d6ca9de0a8abebcb4ab96045bff5127845d38fd08d1fc4393199"
)
GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_SCHEMA_VERSION = (
    "broker_reports_gate5_securities_income_group_tax_base_methodology_v0"
)
GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_VERSION = "2026.3-audited"
GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_RESOURCE = (
    "gate5_tax_methodology.ru_ndfl_securities_income_group_tax_base_proof.v0.json"
)
GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_RESOURCE_SHA256 = (
    "feffc538795825e346f92082d26d4de56d83ec51437bb9fa0037c60f5bd72116"
)
GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_SCHEMA_VERSION = (
    "broker_reports_gate5_income_group_tax_settlement_methodology_v1"
)
GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_ID = (
    "ru-3ndfl-2025-income-group-settlement-proof"
)
GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_VERSION = "2026.4-audited"
GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_RESOURCE = (
    "gate5_tax_methodology.ru_3ndfl_2025_income_group_settlement.v1.json"
)
GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_RESOURCE_SHA256 = (
    "69931290db849acea3512395a0bb954ace53de8b0956694090c8983d346e5816"
)
_GATE5_INCOME_GROUP_TAX_SETTLEMENT_SUPERSEDED_VERSION = "2026.3-experimental"
_GATE5_INCOME_GROUP_TAX_SETTLEMENT_SUPERSEDED_RESOURCE = (
    "gate5_tax_methodology.ru_3ndfl_2025_income_group_settlement.v0.json"
)
_GATE5_INCOME_GROUP_TAX_SETTLEMENT_SUPERSEDED_RESOURCE_SHA256 = (
    "aa72892a061428ca622066e6b4ef222ba4f9e325cd6fbe2bc92da40a50c49a79"
)
_GATE5_INCOME_GROUP_TAX_SETTLEMENT_SUPERSEDED_SCHEMA_VERSION = (
    "broker_reports_gate5_income_group_tax_settlement_methodology_v0"
)
GATE5_DECLARATION_INPUT_METHODOLOGY_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_input_methodology_v1"
)
GATE5_DECLARATION_INPUT_METHODOLOGY_ID = (
    "ru-3ndfl-2025-declaration-input-contract"
)
GATE5_DECLARATION_INPUT_METHODOLOGY_VERSION = (
    "2026.3-current-authority"
)
GATE5_DECLARATION_INPUT_METHODOLOGY_RESOURCE = (
    "gate5_tax_methodology.ru_3ndfl_2025_declaration_input_contract.v3.json"
)
GATE5_DECLARATION_INPUT_METHODOLOGY_RESOURCE_SHA256 = (
    "2d75ec75cdc6b3a0ab20cae697abfe6ad06d2b2d398140c9a171bf617ebdbbf6"
)
GATE5_ORDINARY_TRADE_PRODUCT_METHODOLOGY_SCHEMA_VERSION = (
    "broker_reports_gate5_ordinary_trade_declaration_product_methodology_v1"
)
GATE5_ORDINARY_TRADE_PRODUCT_METHODOLOGY_ID = (
    "ru-ordinary-trade-declaration-product"
)
GATE5_ORDINARY_TRADE_PRODUCT_METHODOLOGY_VERSION = "2025.1"
GATE5_ORDINARY_TRADE_PRODUCT_METHODOLOGY_RESOURCE = (
    "gate5_tax_methodology.ru_ordinary_trade_declaration_product.v1.json"
)
GATE5_ORDINARY_TRADE_PRODUCT_METHODOLOGY_RESOURCE_SHA256 = (
    "ca38485830352e6de49765c3ea20e38082dc3d3a7bf82bbe210477512bb7fae7"
)
GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_SCHEMA_VERSION = (
    "broker_reports_gate5_deterministic_source_fact_consumption_methodology_v0"
)
GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID = (
    "ru-ndfl-securities-source-fact-consumption-proof"
)
GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION = (
    "2026.7-current-authority"
)
GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_RESOURCE = (
    "gate5_tax_methodology."
    "ru_ndfl_securities_real_source_fact_contract.v2.json"
)
GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_RESOURCE_SHA256 = (
    "8fcf311f6205eaf714279fec3e651d4518ea0c2a08e87a7be389484564b5ade0"
)
_GATE5_SOURCE_FACT_CONSUMPTION_SUPERSEDED_VERSION = "2026.5-experimental"
_GATE5_SOURCE_FACT_CONSUMPTION_SUPERSEDED_RESOURCE = (
    "gate5_tax_methodology."
    "ru_ndfl_securities_real_source_fact_contract.v0.json"
)
_GATE5_SOURCE_FACT_CONSUMPTION_SUPERSEDED_RESOURCE_SHA256 = (
    "06947c90e1a24ff7ec62f893eff582e9de4e637a6173bd1a4b027eb783045091"
)
_GATE5_SOURCE_FACT_CONSUMPTION_EARLY_SUPERSEDED_VERSION = "2026.4-experimental"
_GATE5_SOURCE_FACT_CONSUMPTION_EARLY_SUPERSEDED_RESOURCE = (
    "gate5_tax_methodology."
    "ru_ndfl_securities_source_fact_consumption_proof.v0.json"
)
_GATE5_SOURCE_FACT_CONSUMPTION_EARLY_SUPERSEDED_RESOURCE_SHA256 = (
    "ed541a77f390cd7ee787f5ff179208545df6ef0c66d6e2d02c106cdc54a98ac7"
)

FACTORY_REQUIRED = (
    "Gate5TrustedMethodologyAuthorityFactory.create is the only trusted Tax "
    "Methodology resolution entrypoint",
    "Gate5TrustedMethodologyCalculationRuntimeFactory.create composes trusted "
    "resolution with Gate5MethodologyCalculationRuntimeFactory.create",
)
FORBIDDEN = (
    "caller-supplied methodology contents, caller-supplied authority hash or "
    "implicit default methodology",
    "direct Gate 4, supplemental, ArtifactStore, SQL, OpenWebUI table, source "
    "or provider reads",
    "methodology CRUD, lifecycle workflow, mutable registry, new DB, LLM, DSL "
    "or calculator behavior changes",
)

_REFERENCE_KEYS = frozenset({"schema_version", "methodology_id", "methodology_version"})


class Gate5TrustedMethodologyError(ValueError):
    def __init__(
        self,
        code: str,
        *,
        gap_owner_classification: str | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.gap_owner_classification = gap_owner_classification


@dataclass(frozen=True)
class _PublishedMethodologyResource:
    resource_name: str
    resource_sha256: str
    schema_version: str


_PUBLISHED_METHODOLOGIES = {
    (
        GATE5_TRUSTED_METHODOLOGY_ID,
        GATE5_TRUSTED_METHODOLOGY_VERSION,
    ): _PublishedMethodologyResource(
        resource_name=GATE5_TRUSTED_METHODOLOGY_RESOURCE,
        resource_sha256=GATE5_TRUSTED_METHODOLOGY_RESOURCE_SHA256,
        schema_version=GATE5_CALCULATION_METHODOLOGY_SCHEMA_VERSION,
    ),
    (
        GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
        GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_VERSION,
    ): _PublishedMethodologyResource(
        resource_name=GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_RESOURCE,
        resource_sha256=(
            GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_RESOURCE_SHA256
        ),
        schema_version=(GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_SCHEMA_VERSION),
    ),
    (
        GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
        GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_VERSION,
    ): _PublishedMethodologyResource(
        resource_name=GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_RESOURCE,
        resource_sha256=(
            GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_RESOURCE_SHA256
        ),
        schema_version=(GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_SCHEMA_VERSION),
    ),
    (
        GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
        GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_VERSION,
    ): _PublishedMethodologyResource(
        resource_name=(GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_RESOURCE),
        resource_sha256=(
            GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_RESOURCE_SHA256
        ),
        schema_version=(
            GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_SCHEMA_VERSION
        ),
    ),
    (
        GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_ID,
        _GATE5_INCOME_GROUP_TAX_SETTLEMENT_SUPERSEDED_VERSION,
    ): _PublishedMethodologyResource(
        resource_name=_GATE5_INCOME_GROUP_TAX_SETTLEMENT_SUPERSEDED_RESOURCE,
        resource_sha256=(
            _GATE5_INCOME_GROUP_TAX_SETTLEMENT_SUPERSEDED_RESOURCE_SHA256
        ),
        schema_version=(
            _GATE5_INCOME_GROUP_TAX_SETTLEMENT_SUPERSEDED_SCHEMA_VERSION
        ),
    ),
    (
        GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_ID,
        GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_VERSION,
    ): _PublishedMethodologyResource(
        resource_name=GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_RESOURCE,
        resource_sha256=(GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_RESOURCE_SHA256),
        schema_version=GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_SCHEMA_VERSION,
    ),
    (
        GATE5_DECLARATION_INPUT_METHODOLOGY_ID,
        GATE5_DECLARATION_INPUT_METHODOLOGY_VERSION,
    ): _PublishedMethodologyResource(
        resource_name=GATE5_DECLARATION_INPUT_METHODOLOGY_RESOURCE,
        resource_sha256=GATE5_DECLARATION_INPUT_METHODOLOGY_RESOURCE_SHA256,
        schema_version=GATE5_DECLARATION_INPUT_METHODOLOGY_SCHEMA_VERSION,
    ),
    (
        GATE5_ORDINARY_TRADE_PRODUCT_METHODOLOGY_ID,
        GATE5_ORDINARY_TRADE_PRODUCT_METHODOLOGY_VERSION,
    ): _PublishedMethodologyResource(
        resource_name=GATE5_ORDINARY_TRADE_PRODUCT_METHODOLOGY_RESOURCE,
        resource_sha256=(
            GATE5_ORDINARY_TRADE_PRODUCT_METHODOLOGY_RESOURCE_SHA256
        ),
        schema_version=GATE5_ORDINARY_TRADE_PRODUCT_METHODOLOGY_SCHEMA_VERSION,
    ),
    (
        GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
        _GATE5_SOURCE_FACT_CONSUMPTION_EARLY_SUPERSEDED_VERSION,
    ): _PublishedMethodologyResource(
        resource_name=_GATE5_SOURCE_FACT_CONSUMPTION_EARLY_SUPERSEDED_RESOURCE,
        resource_sha256=(
            _GATE5_SOURCE_FACT_CONSUMPTION_EARLY_SUPERSEDED_RESOURCE_SHA256
        ),
        schema_version=GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_SCHEMA_VERSION,
    ),
    (
        GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
        _GATE5_SOURCE_FACT_CONSUMPTION_SUPERSEDED_VERSION,
    ): _PublishedMethodologyResource(
        resource_name=_GATE5_SOURCE_FACT_CONSUMPTION_SUPERSEDED_RESOURCE,
        resource_sha256=_GATE5_SOURCE_FACT_CONSUMPTION_SUPERSEDED_RESOURCE_SHA256,
        schema_version=GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_SCHEMA_VERSION,
    ),
    (
        GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
        GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    ): _PublishedMethodologyResource(
        resource_name=GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_RESOURCE,
        resource_sha256=GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_RESOURCE_SHA256,
        schema_version=GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_SCHEMA_VERSION,
    ),
}


class Gate5TrustedMethodologyAuthorityFactory:
    @staticmethod
    def create() -> "Gate5TrustedMethodologyAuthority":
        return Gate5TrustedMethodologyAuthority()


class Gate5TrustedMethodologyAuthority:
    def resolve(self, methodology_ref: dict[str, Any]) -> dict[str, Any]:
        identity = _validated_reference(methodology_ref)
        published = _PUBLISHED_METHODOLOGIES.get(identity)
        if published is None:
            raise Gate5TrustedMethodologyError(
                "gate5_trusted_methodology_not_published"
            )
        try:
            raw = (
                resources.files(__package__)
                .joinpath(published.resource_name)
                .read_bytes()
            )
        except (FileNotFoundError, OSError) as exc:
            raise Gate5TrustedMethodologyError(
                "gate5_trusted_methodology_resource_unavailable"
            ) from exc
        resource_sha256 = hashlib.sha256(raw).hexdigest()
        if resource_sha256 != published.resource_sha256:
            raise Gate5TrustedMethodologyError(
                "gate5_trusted_methodology_resource_hash_mismatch"
            )
        try:
            methodology: Any = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Gate5TrustedMethodologyError(
                "gate5_trusted_methodology_resource_json_invalid"
            ) from exc
        if (
            not isinstance(methodology, dict)
            or methodology.get("schema_version") != published.schema_version
            or methodology.get("methodology_id") != identity[0]
            or methodology.get("methodology_version") != identity[1]
        ):
            raise Gate5TrustedMethodologyError(
                "gate5_trusted_methodology_resource_identity_mismatch"
            )
        try:
            projection_sha256 = _projection_sha256(methodology)
        except (RecursionError, TypeError, ValueError) as exc:
            raise Gate5TrustedMethodologyError(
                "gate5_trusted_methodology_resource_json_invalid"
            ) from exc
        return {
            "authority_binding": {
                "authority_owner": GATE5_TRUSTED_METHODOLOGY_AUTHORITY_OWNER,
                "methodology_id": identity[0],
                "methodology_version": identity[1],
                "resource_sha256": resource_sha256,
                "projection_sha256": projection_sha256,
            },
            "methodology": copy.deepcopy(methodology),
        }

    def classify_declarant_category(
        self,
        *,
        methodology_ref: dict[str, Any],
        taxpayer_capacity: str,
        tax_period: str,
    ) -> dict[str, Any]:
        """Apply the one published bounded declarant-category classification."""

        resolved = self.resolve(methodology_ref)
        rules = {
            item.get("rule_id"): item
            for item in resolved["methodology"].get("rules", [])
            if isinstance(item, dict)
        }
        rule = rules.get("declarant-category-fns-order-913-v1")
        if (
            tax_period != "2025"
            or taxpayer_capacity != "individual_not_ip_not_private_practice"
            or not isinstance(rule, dict)
            or rule.get("operation") != "CLASSIFY"
            or rule.get("output")
            != "other_individual_declaring_article_228_income"
        ):
            raise Gate5TrustedMethodologyError(
                "gate5_declarant_category_methodology_unresolved"
            )
        return {
            "declarant_category": rule["output"],
            "rule_id": rule["rule_id"],
            "authority_binding": copy.deepcopy(resolved["authority_binding"]),
        }

    def resolve_ordinary_trade_declaration_product(
        self,
        *,
        source_assertions: dict[str, str],
        tax_period: str,
    ) -> dict[str, Any]:
        """Map exact Canonical assertions through the pinned product rules."""

        expected = {
            "admitted_exchange_fact": "ADMITTED",
            "market_quotation_fact": "AVAILABLE",
            "iis_status_assertion": "OUTSIDE_IIS",
            "exemption_source_assertion": "NONE",
            "payer_organization_jurisdiction": "RU",
            "realization_location_jurisdiction": "RU",
        }
        resolved = self.resolve(
            {
                "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
                "methodology_id": GATE5_ORDINARY_TRADE_PRODUCT_METHODOLOGY_ID,
                "methodology_version": (
                    GATE5_ORDINARY_TRADE_PRODUCT_METHODOLOGY_VERSION
                ),
            }
        )
        rules = {
            item.get("rule_id"): item
            for item in resolved["methodology"].get("rules", [])
            if isinstance(item, dict)
        }
        applicability = rules.get("ordinary-trade-operation-applicability-v1")
        source = rules.get("ordinary-trade-income-source-v1")
        kbk = rules.get("ordinary-trade-article-228-payment-kbk-v1")
        if (
            not isinstance(applicability, dict)
            or applicability.get("required_source_assertions")
            != {key: expected[key] for key in (
                "admitted_exchange_fact",
                "market_quotation_fact",
                "iis_status_assertion",
                "exemption_source_assertion",
            )}
            or applicability.get("output")
            != {
                "organized_market_status": "organized_market",
                "iis_status": "outside_iis",
                "exemption_applicability": "not_applicable",
            }
            or applicability.get("insufficient_inputs")
            != "REAL_SOURCE_EVIDENCE_MISSING"
            or not isinstance(source, dict)
            or source.get("required_source_assertions")
            != {key: expected[key] for key in (
                "payer_organization_jurisdiction",
                "realization_location_jurisdiction",
            )}
            or source.get("output") != "russian_source"
            or source.get("insufficient_inputs")
            != "REAL_SOURCE_EVIDENCE_MISSING"
            or not isinstance(kbk, dict)
            or kbk.get("output") != "18210102030011000110"
        ):
            raise Gate5TrustedMethodologyError(
                "gate5_ordinary_trade_product_methodology_invalid"
            )
        if tax_period != "2025" or source_assertions != expected:
            raise Gate5TrustedMethodologyError(
                "gate5_ordinary_trade_product_source_evidence_unresolved",
                gap_owner_classification=applicability["insufficient_inputs"],
            )
        return {
            "operation_applicability": copy.deepcopy(applicability["output"]),
            "income_source_jurisdiction": source["output"],
            "kbk": kbk["output"],
            "rule_ids": sorted(rules),
            "authority_binding": copy.deepcopy(resolved["authority_binding"]),
        }


class Gate5TrustedMethodologyCalculationRuntimeFactory:
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

    def create(self) -> "Gate5TrustedMethodologyCalculationRuntime":
        authority = Gate5TrustedMethodologyAuthorityFactory.create()
        calculator = Gate5MethodologyCalculationRuntimeFactory(
            store=self._store,
            read_enabled=self._read_enabled,
            retention_policy=self._retention_policy,
        ).create()
        return Gate5TrustedMethodologyCalculationRuntime(
            authority=authority,
            calculator=calculator,
        )


class Gate5TrustedMethodologyCalculationRuntime:
    def __init__(
        self,
        *,
        authority: Gate5TrustedMethodologyAuthority,
        calculator: Gate5MethodologyCalculationRuntime,
    ) -> None:
        self._authority = authority
        self._calculator = calculator

    def calculate(
        self,
        *,
        methodology_ref: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        resolved = self._authority.resolve(methodology_ref)
        result = self._calculator.calculate(
            methodology=resolved["methodology"],
            context=context,
        )
        authority_binding = resolved["authority_binding"]
        if result.get("methodology_binding") != {
            "methodology_id": authority_binding["methodology_id"],
            "methodology_version": authority_binding["methodology_version"],
            "projection_sha256": authority_binding["projection_sha256"],
        }:
            raise Gate5TrustedMethodologyError(
                "gate5_trusted_methodology_result_binding_mismatch"
            )
        return {
            "schema_version": GATE5_TRUSTED_CALCULATION_RESULT_SCHEMA_VERSION,
            "status": "calculated",
            "authority_binding": copy.deepcopy(authority_binding),
            "calculation_result": copy.deepcopy(result),
        }


def _validated_reference(value: Any) -> tuple[str, str]:
    if (
        not isinstance(value, dict)
        or set(value) != _REFERENCE_KEYS
        or value.get("schema_version") != GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION
        or not isinstance(value.get("methodology_id"), str)
        or not value["methodology_id"]
        or not isinstance(value.get("methodology_version"), str)
        or not value["methodology_version"]
    ):
        raise Gate5TrustedMethodologyError("gate5_trusted_methodology_ref_invalid")
    return value["methodology_id"], value["methodology_version"]


def _projection_sha256(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_DECLARATION_INPUT_METHODOLOGY_ID",
    "GATE5_DECLARATION_INPUT_METHODOLOGY_RESOURCE",
    "GATE5_DECLARATION_INPUT_METHODOLOGY_RESOURCE_SHA256",
    "GATE5_DECLARATION_INPUT_METHODOLOGY_SCHEMA_VERSION",
    "GATE5_DECLARATION_INPUT_METHODOLOGY_VERSION",
    "GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_ID",
    "GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_RESOURCE",
    "GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_RESOURCE_SHA256",
    "GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_SCHEMA_VERSION",
    "GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_VERSION",
    "GATE5_ORDINARY_TRADE_PRODUCT_METHODOLOGY_ID",
    "GATE5_ORDINARY_TRADE_PRODUCT_METHODOLOGY_RESOURCE",
    "GATE5_ORDINARY_TRADE_PRODUCT_METHODOLOGY_RESOURCE_SHA256",
    "GATE5_ORDINARY_TRADE_PRODUCT_METHODOLOGY_SCHEMA_VERSION",
    "GATE5_ORDINARY_TRADE_PRODUCT_METHODOLOGY_VERSION",
    "GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_RESOURCE",
    "GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_RESOURCE_SHA256",
    "GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_SCHEMA_VERSION",
    "GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_VERSION",
    "GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID",
    "GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_RESOURCE",
    "GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_RESOURCE_SHA256",
    "GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_SCHEMA_VERSION",
    "GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION",
    "GATE5_TRUSTED_CALCULATION_RESULT_SCHEMA_VERSION",
    "GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID",
    "GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_RESOURCE",
    "GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_RESOURCE_SHA256",
    "GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_SCHEMA_VERSION",
    "GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_VERSION",
    "GATE5_TRUSTED_METHODOLOGY_AUTHORITY_OWNER",
    "GATE5_TRUSTED_METHODOLOGY_ID",
    "GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION",
    "GATE5_TRUSTED_METHODOLOGY_RESOURCE",
    "GATE5_TRUSTED_METHODOLOGY_RESOURCE_SHA256",
    "GATE5_TRUSTED_METHODOLOGY_VERSION",
    "Gate5TrustedMethodologyAuthority",
    "Gate5TrustedMethodologyAuthorityFactory",
    "Gate5TrustedMethodologyCalculationRuntime",
    "Gate5TrustedMethodologyCalculationRuntimeFactory",
    "Gate5TrustedMethodologyError",
]
