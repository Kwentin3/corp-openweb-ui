"""Narrow production adapter from current ordinary-trade facts to FNS XML."""

from __future__ import annotations

import copy
import base64
import hashlib
import json
import re
from typing import Any, Protocol

from .active_category_declaration_assembly import (
    ACTIVE_CATEGORY_TO_DECLARATION_ASSEMBLY_PROVEN,
    ActiveCategoryDeclarationAssemblyRuntimeFactory,
)
from .artifact_models import (
    ArtifactAccessContext,
    ArtifactRecord,
    ArtifactStorePort,
    RetentionPolicy,
)
from .authenticated_case_taxpayer_binding import (
    AuthenticatedCaseTaxpayerBindingRuntimeFactory,
    AuthenticatedTaxpayerIdentityProvider,
)
from .gate4_ordinary_trade_candidate import Gate4OrdinaryTradeCandidateRuntimeFactory
from .gate5_full_target_xml_projection import Gate5FullTargetXmlProjectionRuntimeFactory
from .gate5_full_target_xml_projection import Gate5FullTargetXmlProjectionError
from .gate5_human_gap_closure import (
    Gate5HumanGapClosureError,
    Gate5HumanGapClosureRuntimeFactory,
)
from .gate5_declaration_right_side_assembly import (
    Gate5DeclarationRightSideAssemblyRuntimeFactory,
)
from .gate5_residency_evidence import gate5_residency_methodology_input
from .gate5_tax_period_category_aggregation import (
    GATE5_TAX_PERIOD_CATEGORY_SCOPE_SCHEMA_VERSION,
    GATE5_TAX_PERIOD_COMPLETENESS_EVIDENCE_SCHEMA_VERSION,
)
from .gate5_trusted_methodology import (
    GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_VERSION,
    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
)
from .ordinary_trade_tax_model_bridge import OrdinaryTradeTaxModelBridgeRuntimeFactory


ORDINARY_TRADE_DECLARATION_MVP_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_declaration_mvp_receipt_v1"
)
ORDINARY_TRADE_DECLARATION_XML_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_declaration_xml_v1"
)
DECLARATION_EXTERNAL_AUTHORITY_SCHEMA_VERSION = (
    "broker_reports_declaration_external_authority_v1"
)
ORDINARY_TRADE_DECLARATION_MVP_TERMINAL = "ORDINARY_TRADE_FNS_XML_MVP_PRODUCED"
FACTORY_REQUIRED = (
    "OrdinaryTradeProductionRuntimeFactory.create is the only active composition root",
    "ActiveCategoryDeclarationAssemblyRuntimeFactory.create remains the assembler",
    "Gate5FullTargetXmlProjectionRuntimeFactory.create remains the XML owner",
)
FORBIDDEN = (
    "caller-selected taxpayer, operation, methodology or downstream artifact",
    "PDF reread, Gate 3, SQL, LLM/provider calculation or declaration assembly",
    "synthetic production identity, inferred external authority or partial XML",
)

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$")
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_MONEY = re.compile(r"^(?:0|[1-9][0-9]{0,17})\.[0-9]{2}$")
_INN10 = re.compile(r"^[0-9]{10}$")
_CODE4 = re.compile(r"^[0-9]{4}$")
_KBK = re.compile(r"^[0-9]{20}$")
_OKTMO = re.compile(r"^[0-9]{8}(?:[0-9]{3})?$")
_CREDIT_KEYS = frozenset(
    {
        "withheld_at_source", "material_benefit_withheld", "trade_fee_credit",
        "fixed_advance_credit", "foreign_tax_credit", "patent_credit",
    }
)
_EXTERNAL_KEYS = frozenset(
    {
        "schema_version", "publication_id", "case_id", "tax_period",
        "operation_applicability", "filing_destination", "income_source",
        "budget", "origin",
    }
)


class OrdinaryTradeDeclarationMvpError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class DeclarationExternalAuthorityProvider(Protocol):
    def current_facts(self, *, context: ArtifactAccessContext) -> dict[str, Any]: ...


class OrdinaryTradeDeclarationMvpRuntime:
    def __init__(
        self,
        *,
        store: ArtifactStorePort,
        read_enabled: bool,
        retention_policy: RetentionPolicy,
        identity_provider: AuthenticatedTaxpayerIdentityProvider,
        external_authority_provider: DeclarationExternalAuthorityProvider,
    ) -> None:
        self._store = store
        self._retention_policy = retention_policy
        self._identity = AuthenticatedCaseTaxpayerBindingRuntimeFactory(
            store=store,
            retention_policy=retention_policy,
            identity_provider=identity_provider,
        ).create()
        self._human_facts = Gate5HumanGapClosureRuntimeFactory.create(
            store=store,
            retention_policy=retention_policy,
        )
        self._external_authority_provider = external_authority_provider
        self._facts = Gate4OrdinaryTradeCandidateRuntimeFactory(
            store=store, read_enabled=read_enabled
        ).create()
        self._bridge = OrdinaryTradeTaxModelBridgeRuntimeFactory(
            store=store,
            read_enabled=read_enabled,
            retention_policy=retention_policy,
        ).create()
        self._assembly = ActiveCategoryDeclarationAssemblyRuntimeFactory(
            store=store,
            read_enabled=read_enabled,
            retention_policy=retention_policy,
        ).create()
        self._projector = Gate5FullTargetXmlProjectionRuntimeFactory.create()

    def run(
        self,
        *,
        context: ArtifactAccessContext,
        canonical_coverage: dict[str, Any],
    ) -> dict[str, Any]:
        binding = _single(self._identity.publish_current(context=context), "taxpayer")
        coverage = _validated_canonical_coverage(
            canonical_coverage,
            context=context,
        )
        taxpayer_ref = binding["scope"]["taxpayer_scope_ref"]
        try:
            owner_facts = self._human_facts.current_user_case_facts(
                context=context,
                taxpayer_scope_ref=taxpayer_ref,
                tax_period="2025",
            )
        except Gate5HumanGapClosureError as exc:
            raise OrdinaryTradeDeclarationMvpError(exc.code) from exc
        user = _declaration_user_inputs_from_owner_facts(
            owner_facts,
            context=context,
            taxpayer_scope_ref=taxpayer_ref,
        )
        external = _validated_external_facts(
            self._external_authority_provider.current_facts(context=context),
            context=context,
        )
        external_artifact_ref = "mvp_external_facts_" + _sha(external)[:32]
        self._persist(
            artifact_ref=external_artifact_ref,
            artifact_type=DECLARATION_EXTERNAL_AUTHORITY_SCHEMA_VERSION,
            payload=external,
            context=context,
        )
        facts = tuple(self._facts.list_facts(context=context))
        disposal = _single(
            tuple(item for item in facts if item.get("financial_type") == "SECURITY_DISPOSAL"),
            "disposal",
        )
        _validate_supported_fact_set(facts=facts, disposal=disposal)
        subject_ref = "security-disposal-1"
        compatibility_binding = {
            "schema_version": "broker_reports_ordinary_trade_taxpayer_binding_v0",
            "operation_subject_ref": subject_ref,
            "taxpayer_scope_ref": taxpayer_ref,
            "provenance": {
                "source_kind": "authenticated_identity_provider",
                "source_ref": binding["binding_ref"],
                "input_channel": "operation_taxpayer_binding",
            },
        }
        resolved_inputs = _resolved_inputs(
            subject_ref=subject_ref,
            user=user,
            external=external,
            facts=facts,
        )
        category_scope = {
            "schema_version": GATE5_TAX_PERIOD_CATEGORY_SCOPE_SCHEMA_VERSION,
            "scope_ref": "mvp-organized-securities-2025",
            "taxpayer_scope_ref": taxpayer_ref,
            "tax_period": "2025",
            "operation_category": "organized_market_securities_outside_iis",
        }
        right_side = _right_side(
            context=context,
            binding=binding,
            user=user,
            external=external,
            facts=facts,
            canonical_coverage=coverage,
        )
        residency = Gate5DeclarationRightSideAssemblyRuntimeFactory.create().residency_classification(
            right_side
        )
        resolved_inputs["tax_context"]["residency"] = gate5_residency_methodology_input(
            residency,
            input_channel="minimal_tax_context",
        )
        incomplete = self._bridge.run(
            operation_methodology_ref=_operation_methodology_ref(),
            source_fact_methodology_ref=_source_methodology_ref(),
            resolved_inputs=resolved_inputs,
            disposal_fact_id=disposal["fact_id"],
            operation_ref="mvp-operation-2025",
            source_scope_ref=context.case_id,
            category_scope=category_scope,
            taxpayer_binding=compatibility_binding,
            completeness_evidence=None,
            context=context,
        )
        scope_hash = incomplete["category_result"]["scope_binding"][
            "scope_binding_sha256"
        ]
        completeness = {
            "schema_version": GATE5_TAX_PERIOD_COMPLETENESS_EVIDENCE_SCHEMA_VERSION,
            "status": "asserted_complete",
            "coverage_kind": "all_operations_in_taxpayer_category_period_scope",
            "scope_binding_sha256": scope_hash,
            "provenance": {
                "source_kind": "current_canonical_coverage",
                "source_ref": coverage["coverage_ref"],
                "input_channel": "tax_period_scope_completeness",
            },
        }
        assembly = self._assembly.run(
            operation_methodology_ref=_operation_methodology_ref(),
            source_fact_methodology_ref=_source_methodology_ref(),
            resolved_inputs=resolved_inputs,
            disposal_fact_id=disposal["fact_id"],
            operation_ref="mvp-operation-2025",
            source_scope_ref=context.case_id,
            category_scope=category_scope,
            taxpayer_binding=compatibility_binding,
            category_completeness_evidence=completeness,
            right_side_inputs=right_side,
            context=context,
        )
        if assembly.get("terminal") != ACTIVE_CATEGORY_TO_DECLARATION_ASSEMBLY_PROVEN:
            blocker = (assembly.get("blockers") or [{}])[0].get(
                "reason_code", "ordinary_trade_declaration_mvp_blocked"
            )
            raise OrdinaryTradeDeclarationMvpError(str(blocker))
        projection = self._projector.project_released(
            released_values=assembly["owner_artifacts"]["projection_input"],
            target_mechanics=assembly["owner_artifacts"]["target_mechanics"],
        )
        xml_bytes = projection["xml_bytes"]
        semantic_reconciliation = self._projector.validate_supported_profile_semantics(
            xml_bytes=xml_bytes
        )
        bindings = {
            "taxpayer_binding_ref": binding["binding_ref"],
            "user_case_fact_refs": sorted(
                item["user_case_fact_ref"] for item in owner_facts
            ),
            "user_case_facts_sha256": _sha(owner_facts),
            "external_authority_artifact_ref": external_artifact_ref,
            "external_authority_sha256": _sha(external),
            "canonical_coverage_ref": coverage["coverage_ref"],
            "canonical_coverage_sha256": coverage["coverage_sha256"],
            "fact_set_sha256": _sha(facts),
            "assembly_receipt_sha256": assembly["receipt_sha256"],
            "projection_receipt_sha256": projection["receipt"]["receipt_sha256"],
        }
        receipt_base = {
            "schema_version": ORDINARY_TRADE_DECLARATION_MVP_RECEIPT_SCHEMA_VERSION,
            "status": "produced",
            "terminal": ORDINARY_TRADE_DECLARATION_MVP_TERMINAL,
            "case_id": context.case_id,
            "tax_period": "2025",
            "taxpayer_scope_ref": taxpayer_ref,
            "disposal_fact_id": disposal["fact_id"],
            "authority_bindings": bindings,
            "xml_sha256": hashlib.sha256(xml_bytes).hexdigest(),
            "xml_size_bytes": len(xml_bytes),
            "xsd_conformance": copy.deepcopy(
                projection["receipt"]["conformance_proof"]
            ),
            "semantic_accounting": copy.deepcopy(assembly["target_accounting"]),
            "semantic_reconciliation": semantic_reconciliation,
            "provider_calls_total": 0,
        }
        receipt = {**receipt_base, "receipt_sha256": _sha(receipt_base)}
        receipt_ref = "mvp_receipt_" + receipt["receipt_sha256"][:32]
        xml_ref = "mvp_xml_" + receipt["xml_sha256"][:32] + "_" + _sha(bindings)[:12]
        self._persist(
            artifact_ref=xml_ref,
            artifact_type=ORDINARY_TRADE_DECLARATION_XML_SCHEMA_VERSION,
            payload={
                "schema_version": ORDINARY_TRADE_DECLARATION_XML_SCHEMA_VERSION,
                "xml_base64": base64.b64encode(xml_bytes).decode("ascii"),
                "xml_sha256": receipt["xml_sha256"],
                "receipt_ref": receipt_ref,
            },
            context=context,
        )
        self._persist(
            artifact_ref=receipt_ref,
            artifact_type=ORDINARY_TRADE_DECLARATION_MVP_RECEIPT_SCHEMA_VERSION,
            payload=receipt,
            context=context,
        )
        return {
            **copy.deepcopy(receipt),
            "receipt_artifact_ref": receipt_ref,
            "xml_artifact_ref": xml_ref,
            "xml_bytes": xml_bytes,
            "assembly_receipt": assembly,
        }

    def validate_current(
        self,
        *,
        result: dict[str, Any],
        context: ArtifactAccessContext,
        canonical_coverage: dict[str, Any],
    ) -> dict[str, Any]:
        """Replay every live owner; external hashes cannot select an old lane."""

        if not isinstance(result, dict):
            _fail("ordinary_trade_declaration_mvp_result_invalid")
        try:
            self._projector.validate_supported_profile_semantics(
                xml_bytes=result.get("xml_bytes")
            )
        except Gate5FullTargetXmlProjectionError as exc:
            raise OrdinaryTradeDeclarationMvpError(
                "ordinary_trade_declaration_xml_semantics_invalid"
            ) from exc
        current = self.run(context=context, canonical_coverage=canonical_coverage)
        if result != current:
            _fail("ordinary_trade_declaration_mvp_stale_or_misbound")
        return copy.deepcopy(current)

    def _persist(
        self,
        *,
        artifact_ref: str,
        artifact_type: str,
        payload: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> None:
        existing = self._store.get_record_unchecked(artifact_ref)
        if existing is not None:
            if (
                existing.artifact_type != artifact_type
                or existing.case_id != context.case_id
                or existing.user_id != context.user_id
                or existing.workspace_model_id != context.workspace_model_id
                or self._store.read_payload(existing) != payload
            ):
                _fail("ordinary_trade_declaration_mvp_artifact_conflict")
            return
        self._store.put_record(
            ArtifactRecord(
                artifact_id=artifact_ref,
                artifact_type=artifact_type,
                case_id=context.case_id,
                chat_id=None,
                user_id=context.user_id,
                workspace_model_id=context.workspace_model_id,
                normalization_run_id=context.normalization_run_id,
                document_id=None,
                source_file_ref=None,
                visibility="private_case",
                storage_backend="project_artifact_payload",
                retention_policy=self._retention_policy,
                access_policy={"scope": "case_private"},
                validation_status="validated",
                lifecycle_status="private_ready",
                payload=copy.deepcopy(payload),
                safe_metadata={"schema_version": artifact_type},
            )
        )


def _resolved_inputs(
    *, subject_ref: str, user: dict[str, Any], external: dict[str, Any],
    facts: tuple[dict[str, Any], ...]
) -> dict[str, Any]:
    def tagged(value: Any, kind: str, ref: str, channel: str) -> dict[str, Any]:
        return {
            "value": value,
            "provenance": {
                "source_kind": kind,
                "source_ref": ref,
                "input_channel": channel,
            },
        }

    fact_ref = "current-fact-set-" + _sha(facts)[:24]
    external_ref = external["publication_id"]
    expense = {
        flag: tagged(True, "current_fact_v2", fact_ref, "expense_eligibility_evidence")
        for flag in ("actually_incurred", "documented", "related_to_operation")
    }
    return {
        "schema_version": "broker_reports_gate5_securities_disposal_resolved_inputs_v0",
        "subject_ref": subject_ref,
        "operation_properties": {
            "operation_kind": tagged(
                "sale", "current_fact_v2", fact_ref, "resolved_operation_property"
            ),
            "organized_market_status": tagged(
                external["operation_applicability"]["organized_market_status"],
                "external_authoritative_evidence",
                external_ref,
                "resolved_operation_property",
            ),
            "iis_status": tagged(
                external["operation_applicability"]["iis_status"],
                "external_authoritative_evidence",
                external_ref,
                "resolved_operation_property",
            ),
        },
        "tax_context": {
            "tax_period": tagged(
                "2025", "current_fact_v2", fact_ref, "minimal_tax_context"
            ),
            "residency": tagged(
                "resident_individual",
                "methodology_derived_result",
                "residency-classification:pending",
                "minimal_tax_context",
            ),
            "exemption_applicability": tagged(
                external["operation_applicability"]["exemption_applicability"],
                "external_authoritative_evidence",
                external_ref,
                "minimal_tax_context",
            ),
            "loss_treatment": tagged(
                user["income_scope"]["loss_treatment"],
                "authenticated_user_case_fact",
                user["human_fact_refs_by_key"][
                    "ordinary_trade_declaration_zero_scope_confirmed"
                ],
                "minimal_tax_context",
            ),
        },
        "scope": {},
        "expense_evidence": {
            "acquisition_cost": copy.deepcopy(expense),
            "transaction_expense": copy.deepcopy(expense),
        },
    }


def _right_side(
    *, context: ArtifactAccessContext, binding: dict[str, Any], user: dict[str, Any],
    external: dict[str, Any], facts: tuple[dict[str, Any], ...],
    canonical_coverage: dict[str, Any]
) -> dict[str, Any]:
    taxpayer_ref = binding["scope"]["taxpayer_scope_ref"]
    user_ref = user["assertion_id"]
    user_refs = user["human_fact_refs_by_key"]
    external_ref = external["publication_id"]
    current_ref = "current-fact-set-" + _sha(facts)[:24]
    user_provenance = {
        "source_kind": "authenticated_user_case_fact",
        "source_ref": user_refs[
            "ordinary_trade_declaration_zero_scope_confirmed"
        ],
        "input_channel": "placeholder",
        "real_user_fact": True,
    }
    external_provenance = {
        "source_kind": "external_authoritative_evidence",
        "source_ref": external_ref,
        "input_channel": "placeholder",
        "real_user_fact": False,
    }
    zeros = user["income_scope"]
    def tagged_zero(key: str) -> dict[str, Any]:
        return {
            "value": {"kind": "money", "amount": zeros[key], "currency": "RUB"},
            "provenance": {
                "source_kind": "user_verified_fact",
                "source_ref": user_refs[
                    "ordinary_trade_declaration_zero_scope_confirmed"
                ],
                "input_channel": "income_group_tax_base",
            },
        }
    return {
        "scope": {
            "scope_ref": "mvp-declaration-2025",
            "taxpayer_scope_ref": taxpayer_ref,
            "tax_period": "2025",
        },
        "residency_evidence": {
            "source_ref": user_refs["residency_evidence"],
            **copy.deepcopy(user["residency_evidence"]),
        },
        "income_group": {
            "group_values": {
                key: tagged_zero(key)
                for key in (
                    "other_group_income",
                    "other_group_allowable_expenses",
                    "non_taxable_income",
                    "tax_deductions",
                )
            },
            "completeness_provenance": {
                "source_kind": "user_verified_fact",
                "source_ref": user_refs[
                    "ordinary_trade_declaration_zero_scope_confirmed"
                ],
                "input_channel": "income_group_completeness",
            },
        },
        "settlement": {
            "credits": copy.deepcopy(user["credits"]),
            "evidence_ref_prefix": user_ref,
            "completeness_source_ref": user_refs[
                "ordinary_trade_declaration_zero_scope_confirmed"
            ],
            "provenance": user_provenance,
            "completeness_provenance": user_provenance,
        },
        "filing_and_party_identity": {
            "filing_instance": {
                **copy.deepcopy(user["filing_instance"]),
                "tax_period": "2025",
                "destination_tax_authority_ref": external["filing_destination"]["ref"],
                "tax_authority_code": external["filing_destination"]["code"],
            },
            "taxpayer": {
                "taxpayer_ref": taxpayer_ref,
                "declarant_category": user["declarant_category"],
                **copy.deepcopy(binding["taxpayer"]),
            },
            "signer": {
                "signer_ref": context.user_id,
                "signer_capacity": user["signer_capacity"],
                "representation_authority": copy.deepcopy(
                    user["representation_authority"]
                ),
            },
            "evidence_source_ref": user_refs["filing_instance_identity"],
            "evidence": {
                "schema_version": "broker_reports_gate5_owner_case_evidence_v1",
                "status": "owner_verified_evidence",
                "real_user_fact": True,
            },
        },
        "taxable_income_source": {
            **copy.deepcopy(external["income_source"]),
            "completeness_source_ref": current_ref,
            "provenance": external_provenance,
            "completeness_provenance": external_provenance,
        },
        "budget_disposition": {
            **copy.deepcopy(external["budget"]),
            "simplified_procedure_returned_or_credited_amount": {
                "kind": "money",
                "amount": user["simplified_returned_or_credited_amount"],
                "currency": "RUB",
            },
            "evidence": {
                "schema_version": "broker_reports_gate5_owner_case_evidence_v1",
                "status": "owner_verified_evidence",
                "real_user_fact": False,
            },
        },
        "financial_investment": {
            "activated_obligation_refs": ["obl_securities_and_derivatives_results"],
            "not_activated_obligation_refs": [
                "obl_digital_financial_asset_and_right_results",
                "obl_investment_partnership_results",
            ],
            "completeness_source_ref": canonical_coverage["coverage_ref"],
            "completeness_provenance": {
                "source_kind": "current_canonical_coverage",
                "source_ref": canonical_coverage["coverage_ref"],
                "input_channel": "placeholder",
                "real_user_fact": False,
            },
        },
    }


def _validated_canonical_coverage(
    value: Any, *, context: ArtifactAccessContext
) -> dict[str, Any]:
    try:
        base = {
            key: copy.deepcopy(item)
            for key, item in value.items()
            if key not in {"coverage_ref", "coverage_sha256"}
        }
        digest = _sha(base)
        valid = (
            isinstance(value, dict)
            and set(value)
            == {
                "schema_version",
                "case_id",
                "status",
                "projections",
                "runtime_ready_observations",
                "relevant_unmapped_observations",
                "coverage_ref",
                "coverage_sha256",
            }
            and value["schema_version"]
            == "broker_reports_ordinary_trade_current_case_coverage_v1"
            and value["case_id"] == context.case_id
            and value["status"] == "complete"
            and isinstance(value["projections"], list)
            and bool(value["projections"])
            and value["runtime_ready_observations"] > 0
            and value["relevant_unmapped_observations"] == 0
            and all(
                set(item)
                == {
                    "projection_artifact_id",
                    "document_id",
                    "canonical_version_id",
                    "canonical_root_sha256",
                    "projection_sha256",
                    "runtime_ready_observations",
                    "relevant_unmapped_observations",
                }
                and item["relevant_unmapped_observations"] == 0
                for item in value["projections"]
            )
            and value["coverage_sha256"] == digest
            and value["coverage_ref"]
            == "ordinary_trade_coverage_" + digest[:32]
        )
    except (AttributeError, KeyError, TypeError):
        valid = False
    if not valid:
        _fail("ordinary_trade_declaration_canonical_coverage_invalid")
    return copy.deepcopy(value)


def _declaration_user_inputs_from_owner_facts(
    value: Any, *, context: ArtifactAccessContext, taxpayer_scope_ref: str
) -> dict[str, Any]:
    facts = value if isinstance(value, list) else []
    by_key = {
        item.get("fact_key"): item
        for item in facts
        if isinstance(item, dict) and isinstance(item.get("fact_key"), str)
    }
    required = {
        "taxpayer_identity_confirmed",
        "residency_evidence",
        "filing_instance_identity",
        "declaration_date",
        "signer_and_representation",
        "budget_disposition",
        "ordinary_trade_declaration_zero_scope_confirmed",
    }
    if set(by_key) != required:
        _fail("ordinary_trade_declaration_human_facts_missing")

    def owned(fact_key: str, kind: str) -> Any:
        fact = by_key[fact_key]
        try:
            valid = (
                fact["scope_binding"]["authenticated_user_ref"] == context.user_id
                and fact["scope_binding"]["case_id"] == context.case_id
                and fact["scope_binding"]["taxpayer_scope_ref"]
                == taxpayer_scope_ref
                and fact["scope_binding"]["tax_period"] == "2025"
                and fact["value"]["kind"] == kind
                and fact["provenance"]["source_kind"]
                == "authenticated_user_case_fact"
                and _identifier(fact["user_case_fact_ref"])
            )
        except (KeyError, TypeError):
            valid = False
        if not valid:
            _fail("ordinary_trade_declaration_human_fact_invalid")
        return copy.deepcopy(fact["value"]["value"])

    if owned("taxpayer_identity_confirmed", "confirmation") is not True:
        _fail("ordinary_trade_declaration_human_fact_invalid")
    zero_scope = owned(
        "ordinary_trade_declaration_zero_scope_confirmed", "confirmation"
    )
    if zero_scope is not True:
        _fail("ordinary_trade_declaration_human_fact_invalid")
    filing = owned("filing_instance_identity", "code")
    signer = owned("signer_and_representation", "code")
    budget = owned("budget_disposition", "code")
    declaration_date = owned("declaration_date", "text")
    residency = owned("residency_evidence", "residency_evidence")
    if (
        filing not in {"INITIAL", "CORRECTION"}
        or signer != "SELF"
        or budget not in {"PAYMENT", "ADDITIONAL_PAYMENT"}
        or not isinstance(declaration_date, str)
        or _DATE.fullmatch(declaration_date) is None
        or not isinstance(residency, dict)
    ):
        _fail("ordinary_trade_declaration_human_fact_invalid")
    assertion_id = "human-facts-" + _sha(facts)[:32]
    zeros = {
        "other_group_income": "0.00",
        "other_group_allowable_expenses": "0.00",
        "non_taxable_income": "0.00",
        "tax_deductions": "0.00",
        "loss_treatment": "none",
    }
    return {
        "assertion_id": assertion_id,
        "residency_evidence": {"normalized_evidence": residency},
        "filing_instance": {
            "declaration_instance_ref": "mvp-declaration-2025-" + filing.lower(),
            "correction_kind": filing.lower(),
            "correction_number": 0 if filing == "INITIAL" else 1,
            "declaration_date": declaration_date,
        },
        "declarant_category": "other_individual_declaring_article_228_income",
        "signer_capacity": "taxpayer_self",
        "representation_authority": None,
        "income_scope": zeros,
        "credits": {key: "0.00" for key in _CREDIT_KEYS},
        "simplified_returned_or_credited_amount": "0.00",
        "human_fact_refs_by_key": {
            key: by_key[key]["user_case_fact_ref"] for key in sorted(by_key)
        },
        "human_fact_refs": sorted(
            item["user_case_fact_ref"] for item in facts
        ),
    }


def _validated_external_facts(
    value: Any, *, context: ArtifactAccessContext
) -> dict[str, Any]:
    try:
        party = value["income_source"]["source_party"]
        valid = (
            isinstance(value, dict)
            and set(value) == _EXTERNAL_KEYS
            and value["schema_version"] == DECLARATION_EXTERNAL_AUTHORITY_SCHEMA_VERSION
            and _identifier(value["publication_id"])
            and value["case_id"] == context.case_id
            and value["tax_period"] == "2025"
            and value["origin"]["kind"] == "external_authority_provider"
            and _identifier(value["origin"]["provider_id"])
            and value["operation_applicability"] == {
                "organized_market_status": "organized_market",
                "iis_status": "outside_iis",
                "exemption_applicability": "not_applicable",
            }
            and set(value["filing_destination"]) == {"ref", "code"}
            and _identifier(value["filing_destination"]["ref"])
            and _CODE4.fullmatch(value["filing_destination"]["code"]) is not None
            and value["income_source"]["jurisdiction_kind"] == "russian_source"
            and value["income_source"]["jurisdiction_code"] == "RU"
            and value["income_source"]["income_kind"] == "securities_disposal"
            and set(value["income_source"])
            == {
                "source_ref", "jurisdiction_kind", "jurisdiction_code",
                "income_kind", "source_party",
            }
            and set(party) == {"party_kind", "display_name", "inn", "kpp", "oktmo"}
            and party["party_kind"] == "organization"
            and _INN10.fullmatch(party["inn"]) is not None
            and _OKTMO.fullmatch(party["oktmo"]) is not None
            and _KBK.fullmatch(value["budget"]["kbk"]) is not None
            and set(value["budget"])
            == {"source_ref", "budget_allocation_ref", "kbk", "oktmo"}
            and _OKTMO.fullmatch(value["budget"]["oktmo"]) is not None
        )
    except (KeyError, TypeError):
        valid = False
    if not valid:
        _fail("ordinary_trade_declaration_external_authority_invalid")
    return copy.deepcopy(value)


def _validate_supported_fact_set(
    *, facts: tuple[dict[str, Any], ...], disposal: dict[str, Any]
) -> None:
    types = [item.get("financial_type") for item in facts]
    roles = {item.get("role"): item.get("value") for item in disposal.get("roles", [])}
    if (
        types.count("SECURITY_PURCHASE") != 1
        or types.count("SECURITY_DISPOSAL") != 1
        or any(item not in {"SECURITY_PURCHASE", "SECURITY_DISPOSAL", "TRANSACTION_CHARGE"} for item in types)
        or roles.get("currency") != "RUB"
        or not str(roles.get("date", "")).startswith("2025-")
    ):
        _fail("ordinary_trade_declaration_scenario_unsupported")


def _operation_methodology_ref() -> dict[str, str]:
    return {
        "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
        "methodology_id": GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
        "methodology_version": GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_VERSION,
    }


def _source_methodology_ref() -> dict[str, str]:
    return {
        "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
        "methodology_id": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
        "methodology_version": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    }


def _single(values: tuple[Any, ...], kind: str) -> Any:
    if len(values) != 1:
        _fail("ordinary_trade_declaration_" + kind + "_binding_required")
    return values[0]


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _fail(code: str) -> None:
    raise OrdinaryTradeDeclarationMvpError(code)


__all__ = [
    "DECLARATION_EXTERNAL_AUTHORITY_SCHEMA_VERSION",
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "ORDINARY_TRADE_DECLARATION_MVP_TERMINAL",
    "DeclarationExternalAuthorityProvider",
    "OrdinaryTradeDeclarationMvpError",
    "OrdinaryTradeDeclarationMvpRuntime",
]
