"""Thin NDFL workflow handoff from active Gate 2 canonical to Gate 3."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .artifact_models import ArtifactAccessContext
from .artifact_models import CanonicalActivationReceipt
from .canonical_store import CanonicalReadEnvelope, CanonicalReaderFactory
from .gate3_chunk_batch_labeling import (
    GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION,
    Gate3ChunkBatchLabelingFactory,
    Gate3ChunkBatchLabelingResult,
)
from .gate3_financial_annotations_persistence import (
    Gate3FinancialAnnotationsPersistenceFactory,
)
from .gate3_financial_role_pack import (
    GATE3_ROLE_PACK_ID,
    GATE3_ROLE_PACK_CURRENT_VERSION,
)
from .gate3_role_labeling import Gate3RoleLabelingError
NDFL_WORKFLOW_STABLE_ID = "broker-reports-ndfl"
NDFL_WORKFLOW_DISPLAY_NAME = "NDFL"
NDFL_WORKSPACE_MODEL_STABLE_ID = NDFL_WORKFLOW_STABLE_ID
NDFL_OPENWEBUI_BASE_PIPE_ID = "broker_reports_gate1_pipe"
NDFL_PROVIDER_PROFILE_ID = "google_gemini"
NDFL_PROVIDER_MODEL_ID = "models/gemini-3.5-flash"
NDFL_PRODUCT_BINDING_SCHEMA_VERSION = "broker_reports_ndfl_product_binding_v1"
NDFL_GATE3_HANDOFF_SCHEMA_VERSION = "broker_reports_ndfl_gate3_handoff_v1"
NDFL_DICTIONARY_ID = "broker-reports-financial-labels"
NDFL_DICTIONARY_SEMANTIC_VERSION = "2.0.0"
NDFL_DICTIONARY_SKILL_ID = "broker-reports-financial-labels"
NDFL_DICTIONARY_TOOL_ID = "broker_reports_financial_label_dictionary"
NDFL_DICTIONARY_TOOL_METHOD = "load_financial_label_dictionary"
NDFL_ROLE_PACK_ID = GATE3_ROLE_PACK_ID
NDFL_ROLE_PACK_SEMANTIC_VERSION = GATE3_ROLE_PACK_CURRENT_VERSION
FACTORY_REQUIRED = (
    "NdflWorkflowFactory.create is the only NDFL Gate 2 to Gate 3 decision "
    "owner; Gate 3 must receive only document identity and authenticated access"
)
FORBIDDEN = (
    "The NDFL workflow must not copy CanonicalArtifactV1, pass text between "
    "pipes or chats, bypass CanonicalReaderFactory, persist incomplete Gate 3 "
    "results, route by display name, retry or start Gate 4"
)


class NdflWorkflowError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.safe_details = copy.deepcopy(safe_details or {})


def ndfl_product_binding_snapshot() -> dict[str, Any]:
    """Return the one stable-ID product topology; names are presentation only."""

    return {
        "schema_version": NDFL_PRODUCT_BINDING_SCHEMA_VERSION,
        "workspace_model_id": NDFL_WORKSPACE_MODEL_STABLE_ID,
        "base_pipe_id": NDFL_OPENWEBUI_BASE_PIPE_ID,
        "workflow_id": NDFL_WORKFLOW_STABLE_ID,
        "provider_profile_id": NDFL_PROVIDER_PROFILE_ID,
        "provider_model_id": NDFL_PROVIDER_MODEL_ID,
        "dictionary_id": NDFL_DICTIONARY_ID,
        "dictionary_semantic_version": NDFL_DICTIONARY_SEMANTIC_VERSION,
        "role_pack_id": NDFL_ROLE_PACK_ID,
        "role_pack_semantic_version": NDFL_ROLE_PACK_SEMANTIC_VERSION,
        "skill_id": NDFL_DICTIONARY_SKILL_ID,
        "tool_id": NDFL_DICTIONARY_TOOL_ID,
        "tool_method": NDFL_DICTIONARY_TOOL_METHOD,
        "prompt_id": None,
        "knowledge_ids": [],
    }


@dataclass(frozen=True)
class NdflGate3Handoff:
    schema_version: str
    workflow_id: str
    decision: str
    document_id: str
    canonical_version_id: str

    def to_dict(self) -> dict[str, str]:
        return {
            "schema_version": self.schema_version,
            "workflow_id": self.workflow_id,
            "decision": self.decision,
            "document_id": self.document_id,
            "canonical_version_id": self.canonical_version_id,
        }


@dataclass(frozen=True)
class NdflGate3Execution:
    handoff: NdflGate3Handoff
    batch_result: Gate3ChunkBatchLabelingResult
    annotations_artifact_id: str
    annotations_payload: dict[str, Any]


@dataclass(frozen=True)
class NdflProductExecution:
    canonical_artifact_ref: str
    activation_receipt: CanonicalActivationReceipt | None
    canonical_before_gate3: CanonicalReadEnvelope
    gate3: NdflGate3Execution
    canonical_after_gate3: CanonicalReadEnvelope


class NdflWorkflowFactory:
    def __init__(
        self,
        *,
        store: Any,
        read_enabled: bool,
        model_client: Any,
        model_id: str,
        provider_profile_id: str,
    ) -> None:
        self._store = store
        self._read_enabled = read_enabled
        self._model_client = model_client
        self._model_id = model_id
        self._provider_profile_id = provider_profile_id

    def create(self) -> "NdflWorkflow":
        return NdflWorkflow(
            store=self._store,
            read_enabled=self._read_enabled,
            model_client=self._model_client,
            model_id=self._model_id,
            provider_profile_id=self._provider_profile_id,
        )


class NdflWorkflow:
    """Connect existing owners without creating a second stage runtime."""

    def __init__(
        self,
        *,
        store: Any,
        read_enabled: bool,
        model_client: Any,
        model_id: str,
        provider_profile_id: str,
    ) -> None:
        self._store = store
        self._read_enabled = read_enabled
        self._model_client = model_client
        self._model_id = model_id
        self._provider_profile_id = provider_profile_id

    def decide_gate3(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
    ) -> NdflGate3Handoff:
        if not isinstance(document_id, str) or not document_id:
            raise NdflWorkflowError("ndfl_gate3_document_id_required")
        envelope = CanonicalReaderFactory(
            store=self._store,
            read_enabled=self._read_enabled,
        ).create().read_active_envelope(document_id, context)
        if envelope.version_status != "ACTIVE":
            raise NdflWorkflowError("ndfl_gate2_canonical_not_active")
        return NdflGate3Handoff(
            schema_version=NDFL_GATE3_HANDOFF_SCHEMA_VERSION,
            workflow_id=NDFL_WORKFLOW_STABLE_ID,
            decision="RUN_GATE3",
            document_id=document_id,
            canonical_version_id=envelope.canonical_version_id,
        )

    async def run_gate3(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
    ) -> NdflGate3Execution:
        handoff = self.decide_gate3(document_id=document_id, context=context)
        try:
            batch_result = await Gate3ChunkBatchLabelingFactory(
                store=self._store,
                read_enabled=self._read_enabled,
                model_client=self._model_client,
                model_id=self._model_id,
            ).create(
                document_id=document_id,
                context=context,
            )
        except Gate3RoleLabelingError as exc:
            if exc.code == "gate3_role_canonical_binding_stale":
                raise NdflWorkflowError(
                    "ndfl_gate3_canonical_changed_during_labeling"
                ) from exc
            raise
        expected_binding = {
            "document_id": handoff.document_id,
            "canonical_version_id": handoff.canonical_version_id,
        }
        if (
            batch_result.document_status != "complete"
            or batch_result.selection_mode != "full_document"
            or batch_result.merged_output is None
        ):
            failed_outcomes = [
                _safe_failed_outcome(outcome)
                for outcome in batch_result.outcomes
                if outcome.terminal_status not in {
                    "validated",
                    "validated_with_local_rejections",
                }
            ]
            raise NdflWorkflowError(
                "ndfl_gate3_document_incomplete",
                safe_details={
                    "document_status": batch_result.document_status,
                    "selection_mode": batch_result.selection_mode,
                    "chunks_total": int(
                        batch_result.metrics.get("chunks_total") or 0
                    ),
                    "chunks_validated": int(
                        batch_result.metrics.get("chunks_validated") or 0
                    ),
                    "chunks_rejected": int(
                        batch_result.metrics.get("chunks_rejected") or 0
                    ),
                    "chunks_provider_failed": int(
                        batch_result.metrics.get("chunks_provider_failed") or 0
                    ),
                    "failed_outcomes": failed_outcomes,
                },
            )
        if batch_result.merged_output.get("canonical_binding") != expected_binding:
            raise NdflWorkflowError(
                "ndfl_gate3_canonical_changed_during_labeling"
            )
        current = self.decide_gate3(
            document_id=document_id,
            context=context,
        )
        if current.canonical_version_id != handoff.canonical_version_id:
            raise NdflWorkflowError(
                "ndfl_gate3_canonical_changed_during_labeling"
            )
        document_result = {
            "schema_version": GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION,
            "semantic_scope": copy.deepcopy(batch_result.semantic_scope),
            "selected_chunk_ordinals": list(
                batch_result.selected_chunk_ordinals
            ),
            "selection_mode": batch_result.selection_mode,
            "document_status": batch_result.document_status,
            "metrics": copy.deepcopy(batch_result.metrics),
            "merged_output": copy.deepcopy(batch_result.merged_output),
        }
        persistence = Gate3FinancialAnnotationsPersistenceFactory(
            store=self._store,
            read_enabled=self._read_enabled,
        ).create()
        record = persistence.save(
            document_id=document_id,
            context=context,
            validated_document_result=document_result,
            provider_profile_id=self._provider_profile_id,
        )
        payload = persistence.read(
            artifact_id=record.artifact_id,
            context=context,
        )
        if payload.get("canonical_binding") != expected_binding:
            raise NdflWorkflowError("ndfl_gate3_persisted_binding_mismatch")
        return NdflGate3Execution(
            handoff=handoff,
            batch_result=batch_result,
            annotations_artifact_id=record.artifact_id,
            annotations_payload=copy.deepcopy(payload),
        )

    async def run_product_path(
        self,
        *,
        canonical_artifact_ref: str,
        context: ArtifactAccessContext,
    ) -> NdflProductExecution:
        """Activate one exact Gate 2 candidate, then label it through Gate 3."""

        if context.workspace_model_id != NDFL_WORKSPACE_MODEL_STABLE_ID:
            raise NdflWorkflowError("ndfl_workspace_model_identity_required")
        if not isinstance(canonical_artifact_ref, str) or not canonical_artifact_ref:
            raise NdflWorkflowError("ndfl_canonical_artifact_ref_required")
        reader = CanonicalReaderFactory(
            store=self._store,
            read_enabled=self._read_enabled,
        ).create()
        selected = reader.read_envelope(canonical_artifact_ref, context)
        if selected.version_status not in {"VALIDATED", "ACTIVE"}:
            raise NdflWorkflowError("ndfl_gate2_canonical_not_ready")

        active_versions = [
            version
            for version in reader.history(selected.document_id, context)
            if version.status == "ACTIVE"
        ]
        if len(active_versions) > 1:
            raise NdflWorkflowError("ndfl_gate2_multiple_active_versions")
        current_active_id = (
            active_versions[0].canonical_version_id if active_versions else None
        )
        activation_receipt = None
        if selected.version_status == "VALIDATED":
            activation_receipt = reader.activate(
                canonical_version_id=selected.canonical_version_id,
                expected_previous_version_id=current_active_id,
                context=context,
                actor=NDFL_WORKFLOW_STABLE_ID,
                reason="ndfl_gate2_candidate_ready_for_gate3",
            )
        elif current_active_id != selected.canonical_version_id:
            raise NdflWorkflowError("ndfl_gate2_selected_version_not_active")

        canonical_before = reader.read_active_envelope(
            selected.document_id,
            context,
        )
        if canonical_before.canonical_version_id != selected.canonical_version_id:
            raise NdflWorkflowError("ndfl_gate2_activation_binding_mismatch")
        gate3 = await self.run_gate3(
            document_id=selected.document_id,
            context=context,
        )
        canonical_after = reader.read_active_envelope(
            selected.document_id,
            context,
        )
        if (
            canonical_after.canonical_version_id
            != canonical_before.canonical_version_id
            or canonical_after.canonical_root_sha256
            != canonical_before.canonical_root_sha256
            or canonical_after.artifact != canonical_before.artifact
        ):
            raise NdflWorkflowError("ndfl_gate2_canonical_mutated_by_gate3")
        return NdflProductExecution(
            canonical_artifact_ref=canonical_artifact_ref,
            activation_receipt=activation_receipt,
            canonical_before_gate3=canonical_before,
            gate3=gate3,
            canonical_after_gate3=canonical_after,
        )


_SAFE_ROLE_RESPONSE_DIAGNOSTIC_KEYS = (
    "raw_model_output_chars",
    "raw_output_kind",
    "raw_output_json_decodable",
    "raw_output_top_level_contract_match",
    "raw_output_schema_version_match",
    "raw_output_facts_list",
    "raw_output_facts_total",
    "raw_output_fact_shape_contract_match",
    "provider_finish_reason",
    "requested_max_tokens",
)


def _safe_failed_outcome(outcome: Any) -> dict[str, Any]:
    result = {
        "chunk_ordinal": int(outcome.chunk["ordinal"]),
        "terminal_status": outcome.terminal_status,
        "failed_phase": outcome.failed_phase,
        "error_code": outcome.error_code,
    }
    role_attempt = outcome.role_attempt
    if role_attempt is None:
        return result
    metrics = role_attempt.metrics if isinstance(role_attempt.metrics, dict) else {}
    diagnostics = {
        key: copy.deepcopy(metrics[key])
        for key in _SAFE_ROLE_RESPONSE_DIAGNOSTIC_KEYS
        if key in metrics
    }
    metadata = role_attempt.execution_metadata
    if metadata is not None:
        for source, target in (
            ("input_tokens", "provider_input_tokens"),
            ("output_tokens", "provider_output_tokens"),
            ("duration_ms", "provider_duration_ms"),
        ):
            value = getattr(metadata, source, None)
            if isinstance(value, int) and value >= 0:
                diagnostics[target] = value
    if diagnostics:
        result["role_response_diagnostics"] = diagnostics
    return result


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "NDFL_GATE3_HANDOFF_SCHEMA_VERSION",
    "NDFL_OPENWEBUI_BASE_PIPE_ID",
    "NDFL_PRODUCT_BINDING_SCHEMA_VERSION",
    "NDFL_PROVIDER_MODEL_ID",
    "NDFL_PROVIDER_PROFILE_ID",
    "NDFL_ROLE_PACK_ID",
    "NDFL_ROLE_PACK_SEMANTIC_VERSION",
    "NDFL_WORKFLOW_DISPLAY_NAME",
    "NDFL_WORKFLOW_STABLE_ID",
    "NDFL_WORKSPACE_MODEL_STABLE_ID",
    "NdflGate3Execution",
    "NdflGate3Handoff",
    "NdflProductExecution",
    "NdflWorkflow",
    "NdflWorkflowError",
    "NdflWorkflowFactory",
    "ndfl_product_binding_snapshot",
]
