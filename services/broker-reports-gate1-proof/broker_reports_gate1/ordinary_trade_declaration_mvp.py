"""Narrow production adapter from current ordinary-trade facts to FNS XML."""

from __future__ import annotations

import copy
import base64
import hashlib
import json
import re
from typing import Any

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
from .gate4_ordinary_trade_candidate import Gate4OrdinaryTradeCandidateRuntimeFactory
from .gate5_full_target_xml_projection import Gate5FullTargetXmlProjectionRuntimeFactory
from .gate5_full_target_xml_projection import Gate5FullTargetXmlProjectionError
from .gate5_declaration_semantic_input import (
    Gate5DeclarationSemanticInputError,
    Gate5DeclarationSemanticInputRuntimeFactory,
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
    GATE5_DECLARATION_INPUT_METHODOLOGY_ID,
    GATE5_DECLARATION_INPUT_METHODOLOGY_VERSION,
    GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_VERSION,
    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
    Gate5TrustedMethodologyAuthorityFactory,
    Gate5TrustedMethodologyError,
)
from .ordinary_trade_tax_model_bridge import OrdinaryTradeTaxModelBridgeRuntimeFactory
from .ordinary_trade_candidate_runtime import OrdinaryTradeCandidateRuntimeFactory
from .ordinary_trade_declaration_case_inputs import (
    ORDINARY_TRADE_DECLARATION_CASE_INPUTS_SCHEMA_VERSION,
    OrdinaryTradeDeclarationCaseInputsRuntimeFactory,
)


ORDINARY_TRADE_DECLARATION_MVP_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_declaration_mvp_receipt_v1"
)
ORDINARY_TRADE_DECLARATION_XML_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_declaration_xml_v1"
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
_INN12 = re.compile(r"^[0-9]{12}$")
_CODE4 = re.compile(r"^[0-9]{4}$")
_OKTMO = re.compile(r"^[0-9]{8}(?:[0-9]{3})?$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CREDIT_KEYS = frozenset(
    {
        "withheld_at_source", "material_benefit_withheld", "trade_fee_credit",
        "fixed_advance_credit", "foreign_tax_credit", "patent_credit",
    }
)
class OrdinaryTradeDeclarationMvpError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class OrdinaryTradeDeclarationMvpRuntime:
    def __init__(
        self,
        *,
        store: ArtifactStorePort,
        read_enabled: bool,
        retention_policy: RetentionPolicy,
    ) -> None:
        self._store = store
        self._retention_policy = retention_policy
        self._case_inputs = OrdinaryTradeDeclarationCaseInputsRuntimeFactory(
            store=store,
            read_enabled=read_enabled,
            retention_policy=retention_policy,
        ).create()
        self._facts = Gate4OrdinaryTradeCandidateRuntimeFactory(
            store=store, read_enabled=read_enabled
        ).create()
        self._source = OrdinaryTradeCandidateRuntimeFactory(
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
        self._supported_profile = self._projector.supported_profile()
        self._semantic_input = Gate5DeclarationSemanticInputRuntimeFactory.create()
        self._methodology = Gate5TrustedMethodologyAuthorityFactory.create()

    def run(
        self,
        *,
        context: ArtifactAccessContext,
        canonical_coverage: dict[str, Any],
    ) -> dict[str, Any]:
        coverage = _validated_canonical_coverage(
            canonical_coverage,
            context=context,
        )
        source_assembly = self._source.assemble_available(
            methodology_ref=_source_methodology_ref(),
            context=context,
        )
        case_inputs = self._case_inputs.current(
            context=context,
            canonical_coverage=coverage,
            operation_period_observation=source_assembly[
                "operation_period_observation"
            ],
        )
        if (
            case_inputs.get("tax_period") != "2025"
            or case_inputs.get("profile_support") != "SUPPORTED"
        ):
            _fail("ordinary_trade_declaration_exact_profile_required")
        if case_inputs["internal_blockers"]:
            _fail(case_inputs["internal_blockers"][0]["reason_code"])
        taxpayer_ref = case_inputs["taxpayer_scope_ref"]
        owner_facts = case_inputs["human_facts"]
        user = _declaration_user_inputs_from_owner_facts(
            owner_facts,
            context=context,
            taxpayer_scope_ref=taxpayer_ref,
        )
        external = _owner_composed_case_data(
            case_inputs=case_inputs,
            user=user,
            context=context,
        )
        try:
            declarant_category = self._methodology.classify_declarant_category(
                methodology_ref=_declaration_methodology_ref(),
                taxpayer_capacity=user["taxpayer_capacity"],
                tax_period="2025",
            )
        except Gate5TrustedMethodologyError as exc:
            raise OrdinaryTradeDeclarationMvpError(exc.code) from exc
        binding = _user_attested_taxpayer_binding(
            context=context,
            taxpayer_scope_ref=taxpayer_ref,
            user=user,
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
                "source_kind": "USER_ATTESTED_CASE_FACT",
                "source_ref": user["human_fact_refs_by_key"]["taxpayer_identity"],
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
            declarant_category=declarant_category,
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
        extracted_values = self._projector.extract_supported_profile_values(
            xml_bytes=xml_bytes
        )
        semantic_reconciliation = self._semantic_input.reconcile_serialized_projection_values(
            projection_input=assembly["owner_artifacts"]["projection_input"],
            serialized_values=extracted_values["values"],
        )
        semantic_reconciliation["representation_proof"] = extracted_values
        bindings = {
            "taxpayer_binding_ref": binding["binding_ref"],
            "user_case_fact_refs": sorted(
                item["user_case_fact_ref"] for item in owner_facts
            ),
            "user_case_facts_sha256": _sha(owner_facts),
            "case_inputs_sha256": _sha(case_inputs),
            "source_metadata_sha256": _sha(
                case_inputs["source_metadata_collection"]
            ),
            "product_methodology_binding": copy.deepcopy(
                case_inputs["methodology_inputs"]["authority_binding"]
            ),
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

    def prepare(
        self,
        *,
        context: ArtifactAccessContext,
        canonical_coverage: dict[str, Any],
    ) -> dict[str, Any]:
        """Return INPUT_REQUIRED, DRAFT_READY or the exact XML result."""

        coverage = _validated_canonical_coverage(
            canonical_coverage,
            context=context,
        )
        source_assembly = self._source.assemble_available(
            methodology_ref=_source_methodology_ref(),
            context=context,
        )
        case_inputs = self._case_inputs.current(
            context=context,
            canonical_coverage=coverage,
            operation_period_observation=source_assembly[
                "operation_period_observation"
            ],
        )
        actions = case_inputs["human_fact_publication"]["actions"]
        security_groups = source_assembly["security_groups"]
        if (
            security_groups
            and all(
                group["position_scope"]["state"] == "OPEN_LONG_PROVEN"
                and group["position_scope"]["tax_activation_status"]
                == "NOT_ACTIVATED_NO_DISPOSAL"
                for group in security_groups
            )
            and not source_assembly["blockers"]
            and not source_assembly["fifo_calculations"]
        ):
            return self._with_case_summary(
                result=_preparation_state(
                    status="OPEN_POSITION_RETAINED",
                    actions=[],
                    internal_blockers=[],
                ),
                case_inputs=case_inputs,
                source_assembly=source_assembly,
            )
        if case_inputs.get("tax_period") is None:
            result = _preparation_state(
                status="INPUT_REQUIRED",
                actions=actions,
                internal_blockers=[],
                missing_critical=["selected_tax_period"],
            )
            return self._with_case_summary(
                result=result,
                case_inputs=case_inputs,
                source_assembly=source_assembly,
            )
        if case_inputs["internal_blockers"]:
            return self._with_case_summary(
                result=_preparation_state(
                    status="PREPARATION_INCOMPLETE",
                    actions=actions,
                    internal_blockers=case_inputs["internal_blockers"],
                ),
                case_inputs=case_inputs,
                source_assembly=source_assembly,
            )
        if case_inputs.get("profile_support") != "SUPPORTED":
            mode = case_inputs.get("profile_mismatch_mode")
            if mode is None:
                result = _preparation_state(
                    status="INPUT_REQUIRED",
                    actions=actions,
                    internal_blockers=[],
                    missing_critical=["profile_mismatch_mode"],
                )
            else:
                status = {
                    "ANALYSIS_ONLY": "ANALYSIS_ONLY_READY",
                    "SURROGATE_DRAFT": "NON_FILING_SURROGATE_READY",
                    "STOP_RESUMABLE": "STOPPED_RESUMABLE",
                }[mode]
                result = _preparation_state(
                    status=status,
                    actions=[],
                    internal_blockers=[],
                )
                analysis = {
                    "fifo_calculations": copy.deepcopy(
                        source_assembly["fifo_calculations"]
                    ),
                    "security_groups": copy.deepcopy(
                        source_assembly["security_groups"]
                    ),
                    "filing_eligible": False,
                    "surrogate": mode == "SURROGATE_DRAFT",
                }
                if mode == "ANALYSIS_ONLY":
                    analysis["analysis_mode"] = "DOCUMENT_ANALYSIS_ONLY"
                elif mode == "SURROGATE_DRAFT":
                    result["surrogate_preview"] = _non_filing_surrogate_preview(
                        case_inputs=case_inputs,
                        source_assembly=source_assembly,
                    )
                else:
                    result["resume_state"] = {
                        "status": "PAUSED_BY_USER",
                        "selected_tax_period": case_inputs["tax_period"],
                        "may_resume_when_exact_profile_available": True,
                    }
                result["analysis"] = analysis
            return self._with_case_summary(
                result=result,
                case_inputs=case_inputs,
                source_assembly=source_assembly,
            )
        if source_assembly["blockers"]:
            status = (
                "ANALYSIS_READY_WITH_OPEN_ITEMS"
                if source_assembly["fifo_calculations"]
                else "PREPARATION_INCOMPLETE"
            )
            return self._with_case_summary(
                result=_preparation_state(
                    status=status,
                    actions=[],
                    internal_blockers=source_assembly["blockers"],
                ),
                case_inputs=case_inputs,
                source_assembly=source_assembly,
            )
        facts_by_key = {
            item["fact_key"]: item for item in case_inputs["human_facts"]
        }
        critical = {
            "taxpayer_capacity",
            "residency_evidence",
            "ordinary_trade_declaration_zero_scope_confirmed",
        }
        missing_critical = sorted(critical - set(facts_by_key))
        if missing_critical:
            return self._with_case_summary(
                result=_preparation_state(
                    status="INPUT_REQUIRED",
                    actions=actions,
                    internal_blockers=[],
                    missing_critical=missing_critical,
                ),
                case_inputs=case_inputs,
                source_assembly=source_assembly,
            )
        preview = self._calculate_preview(
            context=context,
            canonical_coverage=coverage,
            case_inputs=case_inputs,
        )
        if preview.get("status") != "calculated":
            return self._with_case_summary(
                result=_preparation_state(
                    status="PREPARATION_INCOMPLETE",
                    actions=actions,
                    internal_blockers=[
                        {
                            "reason_code": preview.get(
                                "reason_code", "ordinary_trade_declaration_preview_blocked"
                            ),
                            "gap_owner_classification": "METHODOLOGY_RULE_MISSING",
                            "owner": "ActiveCategoryDeclarationAssemblyRuntime",
                        }
                    ],
                ),
                case_inputs=case_inputs,
                source_assembly=source_assembly,
            )
        if actions:
            result = _preparation_state(
                status="DRAFT_READY",
                actions=actions,
                internal_blockers=[],
            )
            result["calculation_preview"] = preview
            result["checklist_fact_keys"] = sorted(
                item["fact_key"] for item in actions
            )
            return self._with_case_summary(
                result=result,
                case_inputs=case_inputs,
                source_assembly=source_assembly,
            )
        declaration = self.run(
            context=context,
            canonical_coverage=coverage,
        )
        return self._with_case_summary(
            result={
                "schema_version": "broker_reports_ordinary_trade_declaration_preparation_v1",
                "status": "DECLARATION_XML_READY",
                "terminal": declaration["terminal"],
                "declaration_ready": True,
                "xml_created": True,
                "user_actions": [],
                "internal_blockers": [],
                "declaration": declaration,
                "provider_calls_total": 0,
            },
            case_inputs=case_inputs,
            source_assembly=source_assembly,
        )

    def _with_case_summary(
        self,
        *,
        result: dict[str, Any],
        case_inputs: dict[str, Any],
        source_assembly: dict[str, Any],
    ) -> dict[str, Any]:
        result["period_profile"] = _period_profile_summary(
            case_inputs=case_inputs,
            source_assembly=source_assembly,
            supported_profile=self._supported_profile,
        )
        result.setdefault(
            "analysis",
            {
                "fifo_calculations": copy.deepcopy(
                    source_assembly["fifo_calculations"]
                ),
                "security_groups": copy.deepcopy(source_assembly["security_groups"]),
                "filing_eligible": result.get("declaration_ready") is True,
                "surrogate": False,
            },
        )
        result["final_note"] = _final_case_note(
            result=result,
            case_inputs=case_inputs,
            source_assembly=source_assembly,
            supported_profile=self._supported_profile,
        )
        return result

    def normalize_action(
        self,
        *,
        request_publication_ref: str,
        answer: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        return self._case_inputs.normalize_action(
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
        return self._case_inputs.publish_change_action(
            context=context,
            canonical_coverage=_validated_canonical_coverage(
                canonical_coverage,
                context=context,
            ),
            fact_key=fact_key,
        )

    def _calculate_preview(
        self,
        *,
        context: ArtifactAccessContext,
        canonical_coverage: dict[str, Any],
        case_inputs: dict[str, Any],
    ) -> dict[str, Any]:
        user = _draft_user_inputs_from_owner_facts(
            case_inputs["human_facts"],
            context=context,
            taxpayer_scope_ref=case_inputs["taxpayer_scope_ref"],
        )
        external = _owner_composed_source_data(case_inputs=case_inputs)
        facts = tuple(self._facts.list_facts(context=context))
        disposal = _single(
            tuple(
                item
                for item in facts
                if item.get("financial_type") == "SECURITY_DISPOSAL"
            ),
            "disposal",
        )
        _validate_supported_fact_set(facts=facts, disposal=disposal)
        subject_ref = "security-disposal-1"
        taxpayer_ref = case_inputs["taxpayer_scope_ref"]
        compatibility_binding = _operation_taxpayer_slot_binding(
            operation_subject_ref=subject_ref,
            taxpayer_scope_ref=taxpayer_ref,
            source_ref=case_inputs["human_fact_publication"]["scope_binding"][
                "scope_binding_sha256"
            ],
        )
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
        right_side = _draft_right_side(
            taxpayer_scope_ref=taxpayer_ref,
            user=user,
        )
        residency = (
            Gate5DeclarationRightSideAssemblyRuntimeFactory.create()
            .residency_classification(right_side)
        )
        resolved_inputs["tax_context"]["residency"] = (
            gate5_residency_methodology_input(
                residency,
                input_channel="minimal_tax_context",
            )
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
        if not isinstance(incomplete.get("category_result"), dict):
            return {
                "schema_version": "broker_reports_active_category_declaration_preview_v1",
                "status": "blocked",
                "reason_code": str(
                    (incomplete.get("blockers") or incomplete.get("demands") or [{}])[
                        0
                    ].get("reason_code")
                    or (incomplete.get("demands") or [{}])[0].get(
                        "required_input"
                    )
                    or "ordinary_trade_declaration_preview_bridge_blocked"
                ),
                "xml_created": False,
            }
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
                "source_ref": canonical_coverage["coverage_ref"],
                "input_channel": "tax_period_scope_completeness",
            },
        }
        return self._assembly.preview(
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
            extracted_values = self._projector.extract_supported_profile_values(
                xml_bytes=result.get("xml_bytes")
            )
            projection_input = result["assembly_receipt"]["owner_artifacts"][
                "projection_input"
            ]
            self._semantic_input.reconcile_serialized_projection_values(
                projection_input=projection_input,
                serialized_values=extracted_values["values"],
            )
        except (
            Gate5FullTargetXmlProjectionError,
            Gate5DeclarationSemanticInputError,
            KeyError,
            TypeError,
        ) as exc:
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
                "methodology_derived_result",
                external_ref,
                "resolved_operation_property",
            ),
            "iis_status": tagged(
                external["operation_applicability"]["iis_status"],
                "methodology_derived_result",
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
                "methodology_derived_result",
                external_ref,
                "minimal_tax_context",
            ),
            "loss_treatment": tagged(
                user["income_scope"]["loss_treatment"],
                "USER_ATTESTED_CASE_FACT",
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
    external: dict[str, Any], declarant_category: dict[str, Any],
    facts: tuple[dict[str, Any], ...],
    canonical_coverage: dict[str, Any]
) -> dict[str, Any]:
    taxpayer_ref = binding["scope"]["taxpayer_scope_ref"]
    user_ref = user["assertion_id"]
    user_refs = user["human_fact_refs_by_key"]
    external_ref = external["publication_id"]
    current_ref = "current-fact-set-" + _sha(facts)[:24]
    user_provenance = {
        "source_kind": "USER_ATTESTED_CASE_FACT",
        "source_ref": user_refs[
            "ordinary_trade_declaration_zero_scope_confirmed"
        ],
        "input_channel": "ordinary_trade_declaration_zero_scope",
        "real_user_fact": True,
    }
    external_provenance = {
        "source_kind": "current_canonical_source_fact",
        "source_ref": external_ref,
        "input_channel": "ordinary_trade_declaration_source",
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
                "declarant_category": declarant_category["declarant_category"],
                **copy.deepcopy(binding["taxpayer"]),
            },
            "signer": {
                "signer_ref": context.user_id,
                "signer_capacity": user["signer_capacity"],
                "representation_authority": copy.deepcopy(
                    user["representation_authority"]
                ),
            },
            "field_provenance": {
                "filing_instance": {
                    "source_kind": "USER_ATTESTED_CASE_FACT",
                    "source_refs": [
                        user_refs["filing_instance_identity"],
                        user_refs["declaration_date"],
                    ],
                },
                "destination_tax_authority": {
                    "source_kind": "USER_ATTESTED_CASE_FACT",
                    "source_refs": [external["filing_destination"]["ref"]],
                },
                "taxpayer_identity": {
                    "source_kind": "USER_ATTESTED_CASE_FACT",
                    "source_refs": [
                        user_refs["taxpayer_identity"]
                    ],
                },
                "taxpayer_period_status": {
                    "source_kind": "methodology_derived_result",
                    "source_refs": [user_refs["residency_evidence"]],
                },
                "declarant_category": {
                    "source_kind": "methodology_derived_result",
                    "source_refs": [
                        user_refs["taxpayer_capacity"],
                        declarant_category["authority_binding"]["resource_sha256"],
                    ],
                },
                "signer": {
                    "source_kind": "USER_ATTESTED_CASE_FACT",
                    "source_refs": [user_refs["signer_and_representation"]],
                },
            },
            "evidence_source_ref": (
                "filing-composition-"
                + _sha(
                    {
                        "binding": binding["binding_ref"],
                        "user": user_refs,
                        "external": external_ref,
                        "category": declarant_category,
                    }
                )[:32]
            ),
            "evidence": {
                "schema_version": "broker_reports_gate5_owner_composed_evidence_v1",
                "status": "owner_composed_evidence",
                "real_user_fact": False,
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
                "input_channel": "canonical_case_completeness",
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
                "document_scope",
                "projections",
                "missing_projection_documents",
                "unexpected_projection_documents",
                "runtime_ready_observations",
                "relevant_unmapped_observations",
                "coverage_ref",
                "coverage_sha256",
            }
            and value["schema_version"]
            == "broker_reports_ordinary_trade_current_case_coverage_v2"
            and value["case_id"] == context.case_id
            and value["status"] == "complete"
            and isinstance(value["document_scope"], list)
            and bool(value["document_scope"])
            and isinstance(value["projections"], list)
            and bool(value["projections"])
            and len(value["document_scope"]) == len(value["projections"])
            and value["missing_projection_documents"] == []
            and value["unexpected_projection_documents"] == []
            and value["runtime_ready_observations"] > 0
            and value["relevant_unmapped_observations"] == 0
            and all(
                set(item)
                == {
                    "document_id",
                    "canonical_version_id",
                    "canonical_root_sha256",
                    "manifest_ref",
                }
                and _identifier(item["document_id"])
                and _identifier(item["canonical_version_id"])
                and _SHA256.fullmatch(item["canonical_root_sha256"])
                is not None
                and _identifier(item["manifest_ref"])
                for item in value["document_scope"]
            )
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
            and [
                (
                    item["document_id"],
                    item["canonical_version_id"],
                    item["canonical_root_sha256"],
                )
                for item in value["document_scope"]
            ]
            == [
                (
                    item["document_id"],
                    item["canonical_version_id"],
                    item["canonical_root_sha256"],
                )
                for item in value["projections"]
            ]
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
        "taxpayer_identity",
        "taxpayer_capacity",
        "residency_evidence",
        "filing_instance_identity",
        "declaration_date",
        "filing_destination_code",
        "signer_and_representation",
        "budget_disposition",
        "budget_oktmo",
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
                == "USER_ATTESTED_CASE_FACT"
                and _identifier(fact["user_case_fact_ref"])
            )
        except (KeyError, TypeError):
            valid = False
        if not valid:
            _fail("ordinary_trade_declaration_human_fact_invalid")
        return copy.deepcopy(fact["value"]["value"])

    identity = owned("taxpayer_identity", "identity_choice")
    capacity = owned("taxpayer_capacity", "code")
    zero_scope = owned(
        "ordinary_trade_declaration_zero_scope_confirmed", "confirmation"
    )
    if zero_scope is not True:
        _fail("ordinary_trade_declaration_human_fact_invalid")
    filing = owned("filing_instance_identity", "code")
    signer = owned("signer_and_representation", "code")
    budget = owned("budget_disposition", "code")
    declaration_date = owned("declaration_date", "text")
    filing_destination_code = owned("filing_destination_code", "code")
    budget_oktmo = owned("budget_oktmo", "code")
    residency = owned("residency_evidence", "residency_evidence")
    if filing == "CORRECTION":
        _fail("ordinary_trade_declaration_correction_number_required")
    if (
        filing != "INITIAL"
        or signer != "SELF"
        or budget not in {"PAYMENT", "ADDITIONAL_PAYMENT"}
        or capacity != "individual_not_ip_not_private_practice"
        or not isinstance(identity, dict)
        or set(identity)
        != {"inn", "last_name", "first_name", "middle_name", "source_fact_refs"}
        or _INN12.fullmatch(identity["inn"]) is None
        or _CODE4.fullmatch(filing_destination_code) is None
        or _OKTMO.fullmatch(budget_oktmo) is None
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
        "taxpayer": copy.deepcopy(identity),
        "taxpayer_capacity": capacity,
        "residency_evidence": {"normalized_evidence": residency},
        "filing_instance": {
            "declaration_instance_ref": "mvp-declaration-2025-" + filing.lower(),
            "correction_kind": filing.lower(),
            "correction_number": 0,
            "declaration_date": declaration_date,
        },
        "signer_capacity": "taxpayer_self",
        "representation_authority": None,
        "income_scope": zeros,
        "credits": {key: "0.00" for key in _CREDIT_KEYS},
        "simplified_returned_or_credited_amount": "0.00",
        "filing_destination_code": filing_destination_code,
        "budget_oktmo": budget_oktmo,
        "human_fact_refs_by_key": {
            key: by_key[key]["user_case_fact_ref"] for key in sorted(by_key)
        },
        "human_fact_refs": sorted(
            item["user_case_fact_ref"] for item in facts
        ),
    }


def _owner_composed_case_data(
    *,
    case_inputs: dict[str, Any],
    user: dict[str, Any],
    context: ArtifactAccessContext,
) -> dict[str, Any]:
    if (
        case_inputs.get("schema_version")
        != ORDINARY_TRADE_DECLARATION_CASE_INPUTS_SCHEMA_VERSION
        or case_inputs.get("taxpayer_scope_ref") is None
        or case_inputs.get("internal_blockers") != []
        or not isinstance(case_inputs.get("source_inputs"), dict)
        or not isinstance(case_inputs.get("methodology_inputs"), dict)
    ):
        _fail("ordinary_trade_declaration_case_inputs_invalid")
    source = case_inputs["source_inputs"]
    methodology = case_inputs["methodology_inputs"]
    refs = source.get("source_fact_refs")
    if not isinstance(refs, dict) or set(refs) != set(source) - {"source_fact_refs"}:
        _fail("ordinary_trade_declaration_case_inputs_invalid")
    return {
        "schema_version": "broker_reports_declaration_owner_composed_case_data_v1",
        "publication_id": "owner-case-data-" + _sha(
            {
                "coverage_ref": case_inputs["source_metadata_collection"][
                    "coverage_ref"
                ],
                "source_refs": refs,
                "human_refs": user["human_fact_refs_by_key"],
                "methodology": methodology["authority_binding"],
            }
        )[:32],
        "case_id": context.case_id,
        "tax_period": "2025",
        "operation_applicability": copy.deepcopy(
            methodology["operation_applicability"]
        ),
        "taxpayer_capacity": {
            "kind": user["taxpayer_capacity"],
            "source_ref": user["human_fact_refs_by_key"]["taxpayer_capacity"],
        },
        "filing_destination": {
            "ref": user["human_fact_refs_by_key"]["filing_destination_code"],
            "code": user["filing_destination_code"],
        },
        "income_source": {
            "source_ref": refs["broker_name"],
            "jurisdiction_kind": methodology["income_source_jurisdiction"],
            "jurisdiction_code": "RU",
            "income_kind": "securities_disposal",
            "source_party": {
                "party_kind": "organization",
                "display_name": source["broker_name"],
                "inn": source["broker_inn"],
                "kpp": source["broker_kpp"],
                "oktmo": source["broker_oktmo"],
            },
        },
        "budget": {
            "source_ref": methodology["authority_binding"]["resource_sha256"],
            "budget_allocation_ref": user["human_fact_refs_by_key"][
                "budget_disposition"
            ],
            "kbk": methodology["kbk"],
            "oktmo": user["budget_oktmo"],
        },
        "origin": {
            "kind": "owner_composed_current_case_inputs",
            "source_metadata_refs": sorted(refs.values()),
            "human_fact_refs": user["human_fact_refs"],
            "methodology_resource_sha256": methodology["authority_binding"][
                "resource_sha256"
            ],
        },
    }


def _owner_composed_source_data(*, case_inputs: dict[str, Any]) -> dict[str, Any]:
    methodology = case_inputs["methodology_inputs"]
    return {
        "publication_id": "owner-source-methodology-" + _sha(
            {
                "source": case_inputs["source_inputs"],
                "methodology": methodology["authority_binding"],
            }
        )[:32],
        "operation_applicability": copy.deepcopy(
            methodology["operation_applicability"]
        ),
    }


def _draft_user_inputs_from_owner_facts(
    value: Any,
    *,
    context: ArtifactAccessContext,
    taxpayer_scope_ref: str,
) -> dict[str, Any]:
    facts = value if isinstance(value, list) else []
    by_key = {
        item.get("fact_key"): item
        for item in facts
        if isinstance(item, dict) and isinstance(item.get("fact_key"), str)
    }
    required = {
        "taxpayer_capacity",
        "residency_evidence",
        "ordinary_trade_declaration_zero_scope_confirmed",
    }
    if not required <= set(by_key):
        _fail("ordinary_trade_declaration_critical_human_facts_missing")

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
                == "USER_ATTESTED_CASE_FACT"
            )
        except (KeyError, TypeError):
            valid = False
        if not valid:
            _fail("ordinary_trade_declaration_human_fact_invalid")
        return copy.deepcopy(fact["value"]["value"])

    capacity = owned("taxpayer_capacity", "code")
    residency = owned("residency_evidence", "residency_evidence")
    zero_scope = owned(
        "ordinary_trade_declaration_zero_scope_confirmed", "confirmation"
    )
    if (
        capacity != "individual_not_ip_not_private_practice"
        or zero_scope is not True
        or not isinstance(residency, dict)
    ):
        _fail("ordinary_trade_declaration_scenario_unsupported")
    refs = {
        key: by_key[key]["user_case_fact_ref"] for key in sorted(required)
    }
    return {
        "assertion_id": "human-draft-facts-" + _sha(refs)[:32],
        "taxpayer_capacity": capacity,
        "residency_evidence": {"normalized_evidence": residency},
        "income_scope": {
            "other_group_income": "0.00",
            "other_group_allowable_expenses": "0.00",
            "non_taxable_income": "0.00",
            "tax_deductions": "0.00",
            "loss_treatment": "none",
        },
        "credits": {key: "0.00" for key in _CREDIT_KEYS},
        "human_fact_refs_by_key": refs,
    }


def _draft_right_side(
    *, taxpayer_scope_ref: str, user: dict[str, Any]
) -> dict[str, Any]:
    refs = user["human_fact_refs_by_key"]
    completeness_ref = refs["ordinary_trade_declaration_zero_scope_confirmed"]
    user_provenance = {
        "source_kind": "USER_ATTESTED_CASE_FACT",
        "source_ref": completeness_ref,
        "input_channel": "ordinary_trade_draft_preview",
        "real_user_fact": True,
    }
    zeros = user["income_scope"]
    return {
        "scope": {
            "scope_ref": "mvp-declaration-2025",
            "taxpayer_scope_ref": taxpayer_scope_ref,
            "tax_period": "2025",
        },
        "residency_evidence": {
            "source_ref": refs["residency_evidence"],
            **copy.deepcopy(user["residency_evidence"]),
        },
        "income_group": {
            "group_values": {
                key: {
                    "value": {
                        "kind": "money",
                        "amount": zeros[key],
                        "currency": "RUB",
                    },
                    "provenance": {
                        "source_kind": "user_verified_fact",
                        "source_ref": completeness_ref,
                        "input_channel": "income_group_tax_base",
                    },
                }
                for key in (
                    "other_group_income",
                    "other_group_allowable_expenses",
                    "non_taxable_income",
                    "tax_deductions",
                )
            },
            "completeness_provenance": {
                "source_kind": "user_verified_fact",
                "source_ref": completeness_ref,
                "input_channel": "income_group_completeness",
            },
        },
        "settlement": {
            "credits": copy.deepcopy(user["credits"]),
            "evidence_ref_prefix": user["assertion_id"],
            "completeness_source_ref": completeness_ref,
            "provenance": user_provenance,
            "completeness_provenance": user_provenance,
        },
    }


def _operation_taxpayer_slot_binding(
    *, operation_subject_ref: str, taxpayer_scope_ref: str, source_ref: str
) -> dict[str, Any]:
    return {
        "schema_version": "broker_reports_ordinary_trade_taxpayer_binding_v0",
        "operation_subject_ref": operation_subject_ref,
        "taxpayer_scope_ref": taxpayer_scope_ref,
        "provenance": {
            "source_kind": "owner_minted_user_attested_taxpayer_slot",
            "source_ref": source_ref,
            "input_channel": "operation_taxpayer_binding",
        },
    }


def _preparation_state(
    *,
    status: str,
    actions: list[dict[str, Any]],
    internal_blockers: list[dict[str, Any]],
    missing_critical: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "broker_reports_ordinary_trade_declaration_preparation_v1",
        "status": status,
        "terminal": {
            "INPUT_REQUIRED": "ordinary_trade_declaration_user_input_required",
            "DRAFT_READY": "ordinary_trade_declaration_draft_ready",
            "ANALYSIS_ONLY_READY": "ordinary_trade_analysis_only_non_filing",
            "NON_FILING_SURROGATE_READY": (
                "ordinary_trade_surrogate_draft_non_filing"
            ),
            "STOPPED_RESUMABLE": "ordinary_trade_preparation_stopped_resumable",
            "OPEN_POSITION_RETAINED": "ordinary_trade_closed_disposal_absent",
        }.get(
            status,
            internal_blockers[0]["reason_code"]
            if internal_blockers
            else "ordinary_trade_declaration_preparation_incomplete",
        ),
        "declaration_ready": False,
        "xml_created": False,
        "user_actions": copy.deepcopy(actions),
        "internal_blockers": copy.deepcopy(internal_blockers),
        "missing_calculation_critical_fact_keys": missing_critical or [],
        "provider_calls_total": 0,
    }


def _period_profile_summary(
    *,
    case_inputs: dict[str, Any],
    source_assembly: dict[str, Any],
    supported_profile: dict[str, Any],
) -> dict[str, Any]:
    observation = source_assembly["operation_period_observation"]
    supported = case_inputs.get("profile_support") == "SUPPORTED"
    selected = case_inputs.get("tax_period")
    if supported and selected != supported_profile["tax_period"]:
        _fail("ordinary_trade_declaration_profile_period_binding_invalid")
    return {
        "selected_tax_period": selected,
        "detected_operation_years": copy.deepcopy(
            observation["observed_operation_years"]
        ),
        "document_period_status": "NOT_PROVEN_BY_CURRENT_FACT_CONTRACT",
        "evidence_horizon_status": observation["evidence_horizon_status"],
        "profile_support": case_inputs.get("profile_support"),
        "profile_mismatch_mode": case_inputs.get("profile_mismatch_mode"),
        "available_profiles": copy.deepcopy(case_inputs["available_profiles"]),
        "form_version": (
            supported_profile["electronic_format_version"] if supported else None
        ),
        "xsd_name": supported_profile["xsd_name"] if supported else None,
        "methodology_version": (
            (case_inputs.get("methodology_inputs") or {})
            .get("authority_binding", {})
            .get("methodology_version")
        ),
        "filing_profile_available": supported,
        "xml_profile_available": supported,
    }


def _non_filing_surrogate_preview(
    *,
    case_inputs: dict[str, Any],
    source_assembly: dict[str, Any],
) -> dict[str, Any]:
    available = copy.deepcopy(case_inputs["available_profiles"])
    if not available:
        _fail("ordinary_trade_declaration_available_profile_required")
    profile = available[-1]
    source = case_inputs["source_inputs"]
    human_values = {
        item["fact_key"]: copy.deepcopy(item["value"]["value"])
        for item in case_inputs["human_facts"]
        if item["fact_key"] != "profile_mismatch_mode"
    }
    confirmed_fields = {
        "selected_tax_period": case_inputs["tax_period"],
        "detected_operation_years": copy.deepcopy(
            source_assembly["operation_period_observation"]["observed_operation_years"]
        ),
        "broker_name": source.get("broker_name"),
        "broker_inn": source.get("broker_inn"),
        "broker_kpp": source.get("broker_kpp"),
        "broker_oktmo": source.get("broker_oktmo"),
        "owner_human_facts": human_values,
        "fifo_calculations": copy.deepcopy(source_assembly["fifo_calculations"]),
        "positions": [
            {
                "asset": item["asset"],
                "state": item["position_scope"]["state"],
            }
            for item in source_assembly["security_groups"]
        ],
    }
    placeholders = [
        {
            "fact_key": fact_key,
            "placeholder": "REQUIRES_OWNER_BOUND_FACT_FOR_EXACT_PROFILE",
        }
        for fact_key in (
            "taxpayer_identity",
            "taxpayer_capacity",
            "residency_evidence",
            "filing_instance_identity",
            "declaration_date",
            "filing_destination_code",
            "signer_and_representation",
            "budget_disposition",
        )
        if fact_key not in human_values
    ]
    return {
        "schema_version": "broker_reports_non_filing_surrogate_preview_v0",
        "status": "NON_FILING_TEMPLATE_ONLY",
        "profile_id": profile["profile_id"],
        "profile": profile,
        "selected_tax_period": case_inputs["tax_period"],
        "profile_tax_period": profile["tax_period"],
        "period_mismatch": case_inputs["tax_period"] != profile["tax_period"],
        "confirmed_fields": confirmed_fields,
        "placeholders": placeholders,
        "checks": [
            "obtain an exact declaration profile for the selected tax period",
            "revalidate every placeholder through its existing domain owner",
            "rerun deterministic calculation and release validation",
        ],
        "non_filing_warning": (
            "This preview uses an available profile from a different tax period. "
            "It is not a declaration, cannot be filed, and has no XML download."
        ),
        "filing_eligible": False,
        "xml_created": False,
        "download_available": False,
    }


def _final_case_note(
    *,
    result: dict[str, Any],
    case_inputs: dict[str, Any],
    source_assembly: dict[str, Any],
    supported_profile: dict[str, Any],
) -> dict[str, Any]:
    period_profile = _period_profile_summary(
        case_inputs=case_inputs,
        source_assembly=source_assembly,
        supported_profile=supported_profile,
    )
    required_checks = {
        str(item["reason_code"])
        for item in source_assembly["blockers"]
        if isinstance(item, dict) and item.get("reason_code")
    }
    required_checks.update(
        str(item["reason_code"])
        for item in result.get("internal_blockers", [])
        if isinstance(item, dict) and item.get("reason_code")
    )
    required_checks.update(
        str(item["fact_key"])
        for item in result.get("user_actions", [])
        if isinstance(item, dict) and item.get("fact_key")
    )
    return {
        "schema_version": "broker_reports_ordinary_trade_case_note_v1",
        "source_completeness_status": (
            "SOURCE_EVIDENCE_PARTIALLY_AVAILABLE"
            if source_assembly["blockers"]
            and source_assembly["fifo_calculations"]
            else "SOURCE_EVIDENCE_INSUFFICIENT"
            if source_assembly["blockers"]
            else "COMPLETE_FOR_OBSERVED_SECURITY_FACTS"
        ),
        "position_evaluation_status": "EVALUATED_FROM_SOURCE_FACTS",
        "selected_tax_period": period_profile["selected_tax_period"],
        "detected_operation_years": period_profile["detected_operation_years"],
        "profile": {
            "support": period_profile["profile_support"],
            "mismatch_mode": period_profile["profile_mismatch_mode"],
            "form_version": period_profile["form_version"],
            "xsd_name": period_profile["xsd_name"],
            "methodology_version": period_profile["methodology_version"],
        },
        "positions": [
            {
                "asset": item["asset"],
                "state": item["position_scope"]["state"],
                "open_long_quantity": item["position_scope"][
                    "open_long_quantity"
                ],
                "proven_open_short_quantity": item["position_scope"][
                    "proven_open_short_quantity"
                ],
            }
            for item in source_assembly["security_groups"]
        ],
        "calculated_disposal_fact_ids": sorted(
            str(item["disposal_fact_id"])
            for item in source_assembly["fifo_calculations"]
        ),
        "required_checks": sorted(required_checks),
        "filing_eligible": result.get("declaration_ready") is True,
        "xml_created": result.get("xml_created") is True,
    }


def _user_attested_taxpayer_binding(
    *,
    context: ArtifactAccessContext,
    taxpayer_scope_ref: str,
    user: dict[str, Any],
) -> dict[str, Any]:
    identity_ref = user["human_fact_refs_by_key"]["taxpayer_identity"]
    taxpayer = {
        key: user["taxpayer"][key]
        for key in ("inn", "last_name", "first_name", "middle_name")
    }
    base = {
        "scope": {
            "authenticated_user_id": context.user_id,
            "case_id": context.case_id,
            "taxpayer_scope_ref": taxpayer_scope_ref,
        },
        "taxpayer": taxpayer,
        "origin": {
            "kind": "USER_ATTESTED_CASE_FACT",
            "source_ref": identity_ref,
        },
    }
    return {
        **base,
        "binding_ref": "user_attested_taxpayer_" + _sha(base)[:32],
    }


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


def _declaration_methodology_ref() -> dict[str, str]:
    return {
        "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
        "methodology_id": GATE5_DECLARATION_INPUT_METHODOLOGY_ID,
        "methodology_version": GATE5_DECLARATION_INPUT_METHODOLOGY_VERSION,
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
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "ORDINARY_TRADE_DECLARATION_MVP_TERMINAL",
    "OrdinaryTradeDeclarationMvpError",
    "OrdinaryTradeDeclarationMvpRuntime",
]
