"""Production composition root for exact-qualified ordinary security trades."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from .artifact_models import ArtifactAccessContext, ArtifactStorePort
from .canonical_store import CanonicalReaderFactory
from .gate4_ordinary_trade_candidate import (
    Gate4OrdinaryTradeCandidateRuntimeFactory,
)
from .gate5_deterministic_source_fact_consumption import (
    Gate5DeterministicSourceFactConsumptionError,
)
from .gate5_trusted_methodology import (
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
)
from .ordinary_trade_candidate_runtime import OrdinaryTradeCandidateRuntimeFactory
from .ordinary_trade_projection import OrdinaryTradeProjectionFactory
from .ordinary_trade_qualified_mappings import (
    OrdinaryTradeQualifiedMappingAuthorityFactory,
)


ORDINARY_TRADE_PRODUCTION_RUN_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_production_run_v1"
)
ORDINARY_TRADE_PRODUCTION_ROUTE_ID = "ordinary_trade_exact_fingerprint_v1"
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
    ) -> None:
        self._store = store
        self._read_enabled = read_enabled

    def create(self) -> "OrdinaryTradeProductionRuntime":
        return OrdinaryTradeProductionRuntime(
            store=self._store,
            read_enabled=self._read_enabled,
        )


class OrdinaryTradeProductionRuntime:
    def __init__(self, *, store: ArtifactStorePort, read_enabled: bool) -> None:
        self._store = store
        self._reader = CanonicalReaderFactory(
            store=store,
            read_enabled=read_enabled,
        ).create()
        self._projections = OrdinaryTradeProjectionFactory(
            store=store,
            read_enabled=read_enabled,
        ).create()
        self._mappings = (
            OrdinaryTradeQualifiedMappingAuthorityFactory.create().list_mappings()
        )
        self._gate4 = Gate4OrdinaryTradeCandidateRuntimeFactory(
            store=store,
            read_enabled=read_enabled,
        ).create()
        self._gate5 = OrdinaryTradeCandidateRuntimeFactory(
            store=store,
            read_enabled=read_enabled,
        ).create()

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
        if not refs and not self._projections.current_case(context=context):
            return _missing_canonical_result()

        facts = self._gate4.list_facts(context=context)
        assessment = self._gate5.assess(
            methodology_ref=_methodology_ref(),
            context=context,
        )
        available = self._gate5.assemble_available(
            methodology_ref=_methodology_ref(),
            context=context,
        )
        execution_status = "completed"
        terminal = "gate5_source_facts_consumed"
        try:
            consumed = self._gate5.run(
                methodology_ref=_methodology_ref(),
                context=context,
            )
            terminal = str((consumed.get("terminals") or [terminal])[-1])
        except Gate5DeterministicSourceFactConsumptionError as exc:
            execution_status = "source_evidence_insufficient"
            terminal = exc.code

        facts_sha256 = _sha256_json(facts)
        fact_types = [str(item.get("financial_type") or "") for item in facts]
        product_status = (
            "PREPARATION_INCOMPLETE"
            if execution_status == "source_evidence_insufficient"
            else "SOURCE_FACTS_CONSUMED"
        )
        product = {
            "schema_version": "broker_reports_current_pipeline_result_v1",
            "status": product_status,
            "terminal": terminal,
            "declaration_ready": False,
            "xml_created": False,
            "pdf_created": False,
            "legacy_fallback_used": False,
            "semantic_fallback_used": False,
            "route_owner": ORDINARY_TRADE_PRODUCTION_ROUTE_ID,
            "gate4": {
                "status": "candidate_projection_facts",
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
                "security_tax_input_status": assessment["security_tax_input_status"],
                "security_fact_counts": assessment["security_fact_counts"],
                "blocker_reason_codes": sorted(
                    {str(item["reason_code"]) for item in available["blockers"]}
                ),
            },
            "preparation": {
                "status": product_status,
                "terminals": [terminal],
                "declaration_readiness": {"ready": False},
                "gap_closure": {
                    "user_facing_required_actions": [],
                    "internal_owner_required_actions": [{"reason_code": terminal}],
                },
            },
        }
        projections = self._projections.current_case(context=context)
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
            },
            "product": product,
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
                reason="ordinary_trade_exact_fingerprint_compilation",
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
            mappings=self._mappings,
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
