"""Production composition root for exact-qualified ordinary security trades."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from .artifact_models import ArtifactAccessContext, ArtifactStorePort, RetentionPolicy
from .canonical_store import CanonicalReaderFactory
from .gate4_ordinary_trade_candidate import (
    Gate4OrdinaryTradeCandidateRuntimeFactory,
)
from .gate5_trusted_methodology import (
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
)
from .ordinary_trade_candidate_runtime import OrdinaryTradeCandidateRuntimeFactory
from .ordinary_trade_projection import OrdinaryTradeProjectionFactory
from .ordinary_trade_mapping_runtime import (
    OrdinaryTradeAutomaticMappingRuntimeFactory,
)
from .ordinary_trade_declaration_mvp import (
    OrdinaryTradeDeclarationMvpError,
    OrdinaryTradeDeclarationMvpRuntime,
)


ORDINARY_TRADE_PRODUCTION_RUN_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_production_run_v1"
)
ORDINARY_TRADE_PRODUCTION_ROUTE_ID = "ordinary_trade_automatic_semantic_mapping_v1"
FACTORY_REQUIRED = (
    "OrdinaryTradeProductionRuntimeFactory.create is the only production "
    "activation, projection and Gate 5 composition entrypoint"
)
FORBIDDEN = (
    "Gate 3 execution, FinancialAnnotationsV2 reads, role-pass execution, old "
    "Gate 4 SQL reads, semantic fallback, broker/year/filename routing or fuzzy "
    "mapping reuse"
)


class OrdinaryTradeProductionError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class OrdinaryTradeProductionRuntimeFactory:
    def __init__(
        self,
        *,
        store: ArtifactStorePort,
        read_enabled: bool,
        retention_policy: RetentionPolicy | None = None,
        mapping_model_client: Any | None = None,
        mapping_review_model_client: Any | None = None,
        mapping_answer_model_client: Any | None = None,
        mapping_model_id: str | None = None,
        mapping_provider_profile_id: str | None = None,
    ) -> None:
        self._store = store
        self._read_enabled = read_enabled
        self._retention_policy = retention_policy
        self._mapping_model_client = mapping_model_client
        self._mapping_review_model_client = mapping_review_model_client
        self._mapping_answer_model_client = mapping_answer_model_client
        self._mapping_model_id = mapping_model_id
        self._mapping_provider_profile_id = mapping_provider_profile_id

    def create(self) -> "OrdinaryTradeProductionRuntime":
        declaration = None
        if self._retention_policy is not None:
            declaration = OrdinaryTradeDeclarationMvpRuntime(
                store=self._store,
                read_enabled=self._read_enabled,
                retention_policy=self._retention_policy,
            )
        mapping = None
        mapping_values = (
            self._mapping_model_client,
            self._mapping_answer_model_client,
            self._mapping_model_id,
            self._mapping_provider_profile_id,
        )
        if any(item is not None for item in (*mapping_values, self._mapping_review_model_client)):
            if not all(item is not None for item in mapping_values):
                raise OrdinaryTradeProductionError(
                    "ordinary_trade_mapping_runtime_configuration_incomplete"
                )
            mapping = OrdinaryTradeAutomaticMappingRuntimeFactory(
                store=self._store,
                read_enabled=self._read_enabled,
                model_client=self._mapping_model_client,
                review_model_client=(
                    self._mapping_review_model_client
                    or self._mapping_model_client
                ),
                answer_model_client=self._mapping_answer_model_client,
                model_id=str(self._mapping_model_id),
                provider_profile_id=str(self._mapping_provider_profile_id),
            ).create()
        return OrdinaryTradeProductionRuntime(
            store=self._store,
            read_enabled=self._read_enabled,
            declaration=declaration,
            mapping=mapping,
        )


class OrdinaryTradeProductionRuntime:
    def __init__(
        self,
        *,
        store: ArtifactStorePort,
        read_enabled: bool,
        declaration: OrdinaryTradeDeclarationMvpRuntime | None = None,
        mapping: Any | None = None,
    ) -> None:
        self._store = store
        self._reader = CanonicalReaderFactory(
            store=store,
            read_enabled=read_enabled,
        ).create()
        self._projections = OrdinaryTradeProjectionFactory(
            store=store,
            read_enabled=read_enabled,
        ).create()
        self._gate4 = Gate4OrdinaryTradeCandidateRuntimeFactory(
            store=store,
            read_enabled=read_enabled,
        ).create()
        self._gate5 = OrdinaryTradeCandidateRuntimeFactory(
            store=store,
            read_enabled=read_enabled,
        ).create()
        self._declaration = declaration
        self._mapping = mapping

    async def run_with_automatic_mapping(
        self,
        *,
        canonical_artifact_refs: Iterable[str],
        context: ArtifactAccessContext,
        user_message: str = "",
        confirmation: bool | None = None,
        expected_confirmation_artifact_id: str | None = None,
    ) -> dict[str, Any]:
        """Run the exact fast path, then resolve one unknown case at a time."""

        refs = list(canonical_artifact_refs)
        result = self.run(canonical_artifact_refs=refs, context=context)
        if self._mapping is None:
            return result
        provider_calls = 0
        mapping_turn = None
        maximum_steps = max(1, len(result.get("documents") or []))
        for _step in range(maximum_steps):
            unresolved = [
                item
                for item in result.get("documents") or []
                if int(item.get("relevant_unmapped_observations") or 0) > 0
            ]
            if not unresolved:
                break
            document_id = str(unresolved[0]["document_id"])
            mapping_turn = await self._mapping.resolve(
                document_id=document_id,
                context=context,
                user_message=user_message,
                confirmation=confirmation,
                expected_confirmation_artifact_id=(
                    expected_confirmation_artifact_id
                ),
            )
            provider_calls += int(
                mapping_turn.get("provider_calls_this_turn") or 0
            )
            user_message = ""
            confirmation = None
            expected_confirmation_artifact_id = None
            if mapping_turn["status"] != "COMPLETE":
                break
            if not refs:
                self._projections.compile_and_save(
                    document_id=document_id,
                    context=context,
                )
            result = self.run(canonical_artifact_refs=refs, context=context)
        result["provider_calls_total"] = provider_calls
        if mapping_turn is not None:
            result["semantic_mapping"] = mapping_turn
        if mapping_turn is not None and mapping_turn["status"] != "COMPLETE":
            _apply_mapping_terminal(result=result, mapping_turn=mapping_turn)
        return result

    def run(
        self,
        *,
        canonical_artifact_refs: Iterable[str],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        refs = list(canonical_artifact_refs)
        if len(refs) != len(set(refs)):
            raise OrdinaryTradeProductionError(
                "ordinary_trade_production_canonical_ref_duplicate"
            )
        documents = [
            self._activate_compile_and_verify(
                canonical_artifact_ref=artifact_ref,
                context=context,
            )
            for artifact_ref in refs
        ]
        projections = self._projections.current_case(context=context)
        if not refs:
            if not projections:
                return _missing_canonical_result()
            documents = [
                self._current_projection_document(record, projection)
                for record, projection in projections
            ]
        canonical_coverage = self._projections.current_case_coverage(context=context)
        gate4_fact_set = self._gate4.current_fact_set(context=context)
        facts = gate4_fact_set["facts"]
        source_contract_blockers = (
            gate4_fact_set["blockers"]
            if canonical_coverage["status"] == "complete"
            else []
        )
        assessment = self._gate5.assess(
            methodology_ref=_methodology_ref(),
            context=context,
        )
        available = self._gate5.assemble_available(
            methodology_ref=_methodology_ref(),
            context=context,
        )
        calculations = available["fifo_calculations"]
        blockers = available["blockers"]
        execution_status = "completed"
        terminal = "gate5_source_facts_consumed"
        if canonical_coverage["status"] != "complete":
            execution_status = "source_evidence_insufficient"
            terminal = (
                "ordinary_trade_declaration_canonical_projection_missing"
                if canonical_coverage["status"] == "missing_projection"
                else "ordinary_trade_declaration_canonical_relevant_unmapped"
            )
        elif source_contract_blockers:
            execution_status = "source_contract_missing"
            terminal = str(source_contract_blockers[0]["reason_code"])
        elif blockers:
            execution_status = (
                "source_evidence_partially_available"
                if calculations
                else "source_evidence_insufficient"
            )
            terminal = str(blockers[0]["reason_code"])
        elif not calculations:
            execution_status = "open_position_not_tax_activated"
            terminal = "ordinary_trade_closed_disposal_absent"

        facts_sha256 = _sha256_json(facts)
        fact_types = [str(item.get("financial_type") or "") for item in facts]
        product_status = {
            "source_evidence_insufficient": "PREPARATION_INCOMPLETE",
            "source_evidence_partially_available": (
                "ANALYSIS_READY_WITH_OPEN_ITEMS"
            ),
            "source_contract_missing": "PREPARATION_INCOMPLETE",
            "open_position_not_tax_activated": "OPEN_POSITION_RETAINED",
        }.get(execution_status, "SOURCE_FACTS_CONSUMED")
        declaration = None
        preparation = None
        if (
            canonical_coverage["status"] == "complete"
            and not source_contract_blockers
        ):
            if self._declaration is not None:
                try:
                    preparation = self._declaration.prepare(
                        context=context,
                        canonical_coverage=canonical_coverage,
                    )
                    product_status = preparation["status"]
                    terminal = preparation["terminal"]
                    declaration = preparation.get("declaration")
                except OrdinaryTradeDeclarationMvpError as exc:
                    execution_status = "declaration_blocked"
                    product_status = "PREPARATION_INCOMPLETE"
                    terminal = exc.code
            elif execution_status == "completed":
                execution_status = "declaration_blocked"
                product_status = "PREPARATION_INCOMPLETE"
                terminal = "ordinary_trade_declaration_authority_owners_required"
        product = {
            "schema_version": "broker_reports_current_pipeline_result_v1",
            "status": product_status,
            "terminal": terminal,
            "declaration_ready": declaration is not None,
            "xml_created": declaration is not None,
            "pdf_created": False,
            "legacy_fallback_used": False,
            "semantic_fallback_used": False,
            "route_owner": ORDINARY_TRADE_PRODUCTION_ROUTE_ID,
            "gate4": {
                "status": "candidate_projection_facts",
                **(
                    {
                        "source_contract_status": gate4_fact_set["status"],
                        "source_contract_blockers": source_contract_blockers,
                    }
                    if source_contract_blockers
                    else {}
                ),
                "facts_total": len(facts),
                "security_facts_total": sum(
                    item in {"SECURITY_PURCHASE", "SECURITY_DISPOSAL"}
                    for item in fact_types
                ),
                "transaction_charge_facts_total": fact_types.count(
                    "TRANSACTION_CHARGE"
                ),
            },
            "gate5": {
                "execution_status": execution_status,
                "security_tax_input_status": (
                    "SOURCE_EVIDENCE_INSUFFICIENT"
                    if canonical_coverage["status"] != "complete"
                    or source_contract_blockers
                    or (blockers and not calculations)
                    else "CLOSED_POSITION_CALCULATION_WITH_SOURCE_GAPS"
                    if blockers
                    else "CLOSED_POSITION_CALCULATION_AVAILABLE"
                    if calculations
                    else assessment["security_tax_input_status"]
                ),
                "security_fact_counts": assessment["security_fact_counts"],
                "security_facts": assessment["security_facts"],
                "operation_period_observation": available[
                    "operation_period_observation"
                ],
                "security_groups": available["security_groups"],
                "fifo_calculations": calculations,
                "blocker_reason_codes": sorted(
                    {
                        str(item["reason_code"])
                        for item in blockers
                    }
                    | {
                        str(item["reason_code"])
                        for item in source_contract_blockers
                    }
                    | (
                        {terminal}
                        if terminal
                        in {
                            "ordinary_trade_declaration_canonical_projection_missing",
                            "ordinary_trade_declaration_canonical_relevant_unmapped",
                        }
                        else set()
                    )
                ),
            },
            "preparation": (
                {
                    **preparation,
                    "terminals": [preparation["terminal"]],
                    "declaration_readiness": {
                        "ready": preparation["declaration_ready"]
                    },
                    "gap_closure": {
                        "user_facing_required_actions": preparation["user_actions"],
                        "internal_owner_required_actions": preparation[
                            "internal_blockers"
                        ],
                    },
                }
                if preparation is not None
                else {
                    "status": product_status,
                    "terminals": [terminal],
                    "declaration_readiness": {"ready": False},
                    "final_note": {
                        "schema_version": "broker_reports_ordinary_trade_case_note_v1",
                        "source_completeness_status": (
                            str(canonical_coverage["status"]).upper()
                            if canonical_coverage["status"] != "complete"
                            else (
                                "ACTIVE_SECURITY_POSITION_SOURCE_CONTRACT_MISSING"
                            )
                            if source_contract_blockers
                            else "SOURCE_EVIDENCE_PARTIALLY_AVAILABLE"
                            if blockers and calculations
                            else "SOURCE_EVIDENCE_INSUFFICIENT"
                            if blockers
                            else "COMPLETE_FOR_OBSERVED_SECURITY_FACTS"
                        ),
                        "position_evaluation_status": (
                            "NOT_EVALUATED_SOURCE_CONTRACT_MISSING"
                            if source_contract_blockers
                            else "EVALUATED_FROM_SOURCE_FACTS"
                            if available["security_groups"]
                            else "NOT_EVALUATED_SOURCE_FACTS_UNAVAILABLE"
                        ),
                        "selected_tax_period": None,
                        "detected_operation_years": available[
                            "operation_period_observation"
                        ]["observed_operation_years"],
                        "profile": {
                            "support": (
                                "NOT_EVALUATED_SOURCE_COVERAGE_INCOMPLETE"
                                if canonical_coverage["status"] != "complete"
                                else "NOT_EVALUATED_DECLARATION_OWNER_UNAVAILABLE"
                            ),
                            "mismatch_mode": None,
                            "form_version": None,
                            "xsd_name": None,
                            "methodology_version": None,
                        },
                        "positions": [
                            {
                                "asset": item["asset"],
                                "state": item["position_scope"]["state"],
                                "open_long_quantity": item["position_scope"][
                                    "open_long_quantity"
                                ],
                                "proven_open_short_quantity": item[
                                    "position_scope"
                                ]["proven_open_short_quantity"],
                            }
                            for item in available["security_groups"]
                        ],
                        "calculated_disposal_fact_ids": sorted(
                            str(item["disposal_fact_id"])
                            for item in calculations
                        ),
                        "required_checks": [terminal],
                        "filing_eligible": False,
                        "xml_created": False,
                    },
                    "gap_closure": {
                        "user_facing_required_actions": [],
                        "internal_owner_required_actions": [
                            *source_contract_blockers,
                            *(
                                [{"reason_code": terminal}]
                                if not source_contract_blockers
                                else []
                            ),
                        ],
                    },
                }
            ),
        }
        return {
            "schema_version": ORDINARY_TRADE_PRODUCTION_RUN_SCHEMA_VERSION,
            "enabled": True,
            "status": "completed",
            "route_owner": ORDINARY_TRADE_PRODUCTION_ROUTE_ID,
            "candidate_activated": True,
            "documents_total": len(projections),
            "provider_calls_total": 0,
            "semantic_fallback_used": False,
            "legacy_fallback_used": False,
            "broker_or_year_special_profiles": 0,
            "canonical_version_ids": [
                projection["canonical_binding"]["canonical_version_id"]
                for _record, projection in projections
            ],
            "canonical_root_sha256": [
                projection["canonical_binding"]["canonical_root_sha256"]
                for _record, projection in projections
            ],
            "projection_artifact_ids": [
                record.artifact_id for record, _projection in projections
            ],
            "documents": documents,
            "system_identity": {
                "projection_sha256": [
                    projection["projection_sha256"]
                    for _record, projection in projections
                ],
                "observation_ids_sha256": _sha256_json(
                    [
                        item["observation_id"]
                        for _record, projection in projections
                        for item in projection["source_observations"]
                    ]
                ),
                "runtime_records_sha256": _sha256_json(
                    [
                        item
                        for _record, projection in projections
                        for item in projection["runtime_records"]
                    ]
                ),
                "gate4_facts_sha256": facts_sha256,
                "gate4_fact_ids_sha256": _sha256_json(
                    [item["fact_id"] for item in facts]
                ),
                "gate5_inputs_sha256": facts_sha256,
                "canonical_coverage_sha256": canonical_coverage[
                    "coverage_sha256"
                ],
            },
            "product": product,
            "declaration": declaration,
        }

    def validate_current_declaration(
        self, *, result: dict[str, Any], context: ArtifactAccessContext
    ) -> dict[str, Any]:
        if self._declaration is None:
            raise OrdinaryTradeProductionError(
                "ordinary_trade_declaration_runtime_not_configured"
            )
        return self._declaration.validate_current(
            result=result,
            context=context,
            canonical_coverage=self._projections.current_case_coverage(
                context=context
            ),
        )

    def normalize_declaration_action(
        self,
        *,
        request_publication_ref: str,
        answer: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        if self._declaration is None:
            raise OrdinaryTradeProductionError(
                "ordinary_trade_declaration_runtime_not_configured"
            )
        return self._declaration.normalize_action(
            request_publication_ref=request_publication_ref,
            answer=answer,
            context=context,
        )

    def publish_declaration_change_action(
        self,
        *,
        fact_key: str,
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        if self._declaration is None:
            raise OrdinaryTradeProductionError(
                "ordinary_trade_declaration_runtime_not_configured"
            )
        return self._declaration.publish_change_action(
            context=context,
            canonical_coverage=self._projections.current_case_coverage(
                context=context
            ),
            fact_key=fact_key,
        )

    @staticmethod
    def _current_projection_document(
        record: Any, projection: dict[str, Any]
    ) -> dict[str, Any]:
        """Expose owner-read current projections to source-free chat resumes."""

        return {
            "document_id": str(record.document_id),
            "canonical_version_id": projection["canonical_binding"][
                "canonical_version_id"
            ],
            "projection_artifact_id": record.artifact_id,
            "activation_receipt": None,
            "runtime_ready_observations": sum(
                item["disposition"] == "RUNTIME_READY"
                for item in projection["source_observations"]
            ),
            "relevant_unmapped_observations": sum(
                item["disposition"] == "RELEVANT_UNMAPPED"
                for item in projection["source_observations"]
            ),
            "matched_qualified_tables": sum(
                int(item["matched_tables"])
                for item in projection["mapping_matches"]
            ),
        }

    def _activate_compile_and_verify(
        self,
        *,
        canonical_artifact_ref: str,
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        if not isinstance(canonical_artifact_ref, str) or not canonical_artifact_ref:
            raise OrdinaryTradeProductionError(
                "ordinary_trade_production_canonical_ref_required"
            )
        selected = self._reader.read_envelope(canonical_artifact_ref, context)
        if selected.version_status not in {"VALIDATED", "ACTIVE"}:
            raise OrdinaryTradeProductionError(
                "ordinary_trade_production_canonical_not_ready"
            )
        active_versions = [
            item
            for item in self._reader.history(selected.document_id, context)
            if item.status == "ACTIVE"
        ]
        if len(active_versions) > 1:
            raise OrdinaryTradeProductionError(
                "ordinary_trade_production_multiple_active_versions"
            )
        previous = active_versions[0].canonical_version_id if active_versions else None
        activation = None
        if selected.version_status == "VALIDATED":
            activation = self._reader.activate(
                canonical_version_id=selected.canonical_version_id,
                expected_previous_version_id=previous,
                context=context,
                actor=ORDINARY_TRADE_PRODUCTION_ROUTE_ID,
                reason="ordinary_trade_automatic_semantic_mapping_compilation",
            )
        elif previous != selected.canonical_version_id:
            raise OrdinaryTradeProductionError(
                "ordinary_trade_production_selected_version_not_active"
            )
        before = self._reader.read_active_envelope(selected.document_id, context)
        if before.canonical_version_id != selected.canonical_version_id:
            raise OrdinaryTradeProductionError(
                "ordinary_trade_production_activation_binding_mismatch"
            )
        projection_record = self._projections.compile_and_save(
            document_id=selected.document_id,
            context=context,
        )
        projection = self._projections.read(
            artifact_id=projection_record.artifact_id,
            context=context,
        )
        after = self._reader.read_active_envelope(selected.document_id, context)
        if (
            after.canonical_version_id != before.canonical_version_id
            or after.canonical_root_sha256 != before.canonical_root_sha256
            or after.artifact != before.artifact
        ):
            raise OrdinaryTradeProductionError(
                "ordinary_trade_production_canonical_mutated"
            )
        return {
            "document_id": selected.document_id,
            "canonical_version_id": selected.canonical_version_id,
            "projection_artifact_id": projection_record.artifact_id,
            "activation_receipt": (
                activation.to_safe_dict() if activation is not None else None
            ),
            "runtime_ready_observations": sum(
                item["disposition"] == "RUNTIME_READY"
                for item in projection["source_observations"]
            ),
            "relevant_unmapped_observations": sum(
                item["disposition"] == "RELEVANT_UNMAPPED"
                for item in projection["source_observations"]
            ),
            "matched_qualified_tables": sum(
                int(item["matched_tables"]) for item in projection["mapping_matches"]
            ),
        }


def _apply_mapping_terminal(
    *, result: dict[str, Any], mapping_turn: dict[str, Any]
) -> None:
    status = str(mapping_turn.get("status") or "")
    public = mapping_turn.get("public_state")
    public = public if isinstance(public, dict) else {}
    terminals = {
        "CLARIFICATION_REQUIRED": (
            "INPUT_REQUIRED",
            "ordinary_trade_mapping_clarification_required",
            "mapping_clarification_required",
        ),
        "CONFIRMATION_REQUIRED": (
            "INPUT_REQUIRED",
            "ordinary_trade_mapping_confirmation_required",
            "mapping_confirmation_required",
        ),
        "MAPPING_REQUIRED": (
            "INPUT_REQUIRED",
            "ordinary_trade_mapping_resume_required",
            "mapping_resume_required",
        ),
        "PROVIDER_UNAVAILABLE": (
            "PREPARATION_INCOMPLETE",
            "ordinary_trade_mapping_provider_unavailable",
            "mapping_provider_unavailable",
        ),
        "UNSUPPORTED": (
            "PREPARATION_INCOMPLETE",
            "ordinary_trade_mapping_unsupported_financial_meaning",
            "mapping_unsupported",
        ),
        "SPECIALIST_REVIEW_REQUIRED": (
            "PREPARATION_INCOMPLETE",
            "ordinary_trade_mapping_specialist_review_required",
            "mapping_specialist_review_required",
        ),
        "SOURCE_CONTEXT_LIMIT": (
            "PREPARATION_INCOMPLETE",
            "ordinary_trade_mapping_source_context_limit",
            "mapping_source_context_limit",
        ),
        "MAPPING_OUTPUT_INVALID": (
            "PREPARATION_INCOMPLETE",
            "ordinary_trade_mapping_output_invalid",
            "mapping_output_invalid",
        ),
    }
    product_status, terminal, execution_status = terminals.get(
        status,
        (
            "PREPARATION_INCOMPLETE",
            "ordinary_trade_mapping_state_invalid",
            "mapping_state_invalid",
        ),
    )
    product = result["product"]
    product["status"] = product_status
    product["terminal"] = terminal
    product["declaration_ready"] = False
    product["xml_created"] = False
    product["gate5"]["execution_status"] = execution_status
    product["gate5"]["security_tax_input_status"] = (
        "SOURCE_MAPPING_INCOMPLETE"
    )
    product["gate5"]["blocker_reason_codes"] = [terminal]
    preparation = product["preparation"]
    preparation["status"] = product_status
    preparation["terminals"] = [terminal]
    preparation["declaration_readiness"] = {"ready": False}
    preparation["gap_closure"] = {
        "user_facing_required_actions": (
            [
                {
                    "kind": "MAPPING_CLARIFICATION",
                    "question": public.get("question"),
                    "confirmation_message": public.get(
                        "confirmation_message"
                    ),
                    "confirmation_option_ref": public.get(
                        "confirmation_option_ref"
                    ),
                }
            ]
            if status in {"CLARIFICATION_REQUIRED", "CONFIRMATION_REQUIRED"}
            else []
        ),
        "internal_owner_required_actions": (
            []
            if status in {"CLARIFICATION_REQUIRED", "CONFIRMATION_REQUIRED"}
            else [{"reason_code": terminal}]
        ),
    }
    final_note = preparation.get("final_note")
    if isinstance(final_note, dict):
        final_note["source_completeness_status"] = status
        final_note["required_checks"] = [terminal]
        final_note["filing_eligible"] = False
        final_note["xml_created"] = False


def _methodology_ref() -> dict[str, str]:
    return {
        "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
        "methodology_id": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
        "methodology_version": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    }


def _missing_canonical_result() -> dict[str, Any]:
    terminal = "ordinary_trade_canonical_evidence_missing"
    empty_sha256 = _sha256_json([])
    return {
        "schema_version": ORDINARY_TRADE_PRODUCTION_RUN_SCHEMA_VERSION,
        "enabled": True,
        "status": "blocked",
        "route_owner": ORDINARY_TRADE_PRODUCTION_ROUTE_ID,
        "candidate_activated": True,
        "documents_total": 0,
        "provider_calls_total": 0,
        "semantic_fallback_used": False,
        "legacy_fallback_used": False,
        "broker_or_year_special_profiles": 0,
        "canonical_version_ids": [],
        "canonical_root_sha256": [],
        "projection_artifact_ids": [],
        "documents": [],
        "system_identity": {
            "projection_sha256": [],
            "observation_ids_sha256": empty_sha256,
            "runtime_records_sha256": empty_sha256,
            "gate4_facts_sha256": empty_sha256,
            "gate4_fact_ids_sha256": empty_sha256,
            "gate5_inputs_sha256": empty_sha256,
        },
        "product": {
            "schema_version": "broker_reports_current_pipeline_result_v1",
            "status": "PREPARATION_INCOMPLETE",
            "terminal": terminal,
            "declaration_ready": False,
            "xml_created": False,
            "pdf_created": False,
            "legacy_fallback_used": False,
            "semantic_fallback_used": False,
            "route_owner": ORDINARY_TRADE_PRODUCTION_ROUTE_ID,
            "gate4": {
                "status": "canonical_evidence_missing",
                "facts_total": 0,
                "security_facts_total": 0,
                "transaction_charge_facts_total": 0,
            },
            "gate5": {
                "execution_status": "not_started_without_canonical",
                "security_tax_input_status": "SOURCE_EVIDENCE_INSUFFICIENT",
                "security_fact_counts": {
                    "total": 0,
                    "ready": 0,
                    "source_evidence_insufficient": 0,
                },
                "blocker_reason_codes": [terminal],
            },
            "preparation": {
                "status": "PREPARATION_INCOMPLETE",
                "terminals": [terminal],
                "declaration_readiness": {"ready": False},
                "final_note": {
                    "schema_version": "broker_reports_ordinary_trade_case_note_v1",
                    "source_completeness_status": "CANONICAL_EVIDENCE_MISSING",
                    "position_evaluation_status": (
                        "NOT_EVALUATED_SOURCE_FACTS_UNAVAILABLE"
                    ),
                    "selected_tax_period": None,
                    "detected_operation_years": [],
                    "profile": {
                        "support": "NOT_EVALUATED_SOURCE_COVERAGE_INCOMPLETE",
                        "mismatch_mode": None,
                        "form_version": None,
                        "xsd_name": None,
                        "methodology_version": None,
                    },
                    "positions": [],
                    "calculated_disposal_fact_ids": [],
                    "required_checks": [terminal],
                    "filing_eligible": False,
                    "xml_created": False,
                },
                "gap_closure": {
                    "user_facing_required_actions": [],
                    "internal_owner_required_actions": [
                        {"reason_code": terminal}
                    ],
                },
            },
        },
    }


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "ORDINARY_TRADE_PRODUCTION_ROUTE_ID",
    "ORDINARY_TRADE_PRODUCTION_RUN_SCHEMA_VERSION",
    "OrdinaryTradeProductionError",
    "OrdinaryTradeProductionRuntime",
    "OrdinaryTradeProductionRuntimeFactory",
]
