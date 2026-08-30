from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping

from .canonical_artifact import (
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
)
from .managed_pdf_document_v2 import (
    ManagedPdfDocumentV2AdjudicatedBuildResult,
    ManagedPdfDocumentV2Factory,
)
from .gate2_model_clients import Gate2StructuredModelClientFactory
from .gate2_model_contracts import (
    Gate2SourceFactRuntimeError,
    Gate2StructuredModelClientConfig,
)
from .gate2_model_requests import (
    MANAGED_DOCUMENT_SEMANTIC_CRITIC_REQUEST_PROFILE,
    MANAGED_DOCUMENT_SEMANTIC_PROPOSAL_REQUEST_PROFILE,
)
from .ordinary_trade_semantic_mapping import (
    OrdinaryTradeSemanticMappingError,
    _build_managed_document_semantic_evidence_from_owned_canonical,
    _managed_semantic_critic_model_request,
    _managed_semantic_evidence_scope_ref,
    _managed_semantic_proposal,
    _managed_semantic_proposal_model_request,
    _review_owned_managed_document_semantic_evidence,
)


MANAGED_PDF_TO_CANONICAL_SCHEMA_VERSION = (
    "broker_reports_managed_pdf_to_canonical_route_v1"
)
FACTORY_REQUIRED = (
    "ManagedPdfToCanonicalFactory.create_for_openwebui is the only inactive "
    "same-call coordinator from adjudicated Managed PDF v2 to CanonicalArtifactV1"
)
FORBIDDEN = (
    "The route must not accept caller-supplied source payloads, source units, "
    "Managed payloads, table projections, Canonical artifacts, bindings, "
    "semantic evidence, ledgers, receipts, product routes, facts, stores or "
    "runtime publication callbacks"
)


@dataclass(frozen=True)
class ManagedPdfToCanonicalBuildResult:
    status: str
    managed_result: ManagedPdfDocumentV2AdjudicatedBuildResult
    canonical_artifact: dict[str, Any] | None
    safe_diagnostics: dict[str, Any]
    private_diagnostics: dict[str, Any]


@dataclass(frozen=True)
class ManagedPdfToCanonicalSemanticEvidenceBuildResult:
    status: str
    canonical_result: ManagedPdfToCanonicalBuildResult
    semantic_evidence: dict[str, Any] | None


@dataclass(frozen=True)
class ManagedPdfToCanonicalSemanticReviewContractBuildResult:
    status: str
    evidence_result: ManagedPdfToCanonicalSemanticEvidenceBuildResult
    semantic_review_contract: dict[str, Any] | None
    reason_code: str | None


@dataclass(frozen=True)
class ManagedPdfToCanonicalSemanticProviderReviewBuildResult:
    status: str
    evidence_result: ManagedPdfToCanonicalSemanticEvidenceBuildResult
    semantic_review_contract: dict[str, Any] | None
    execution_receipt: dict[str, Any]
    reason_code: str | None


class ManagedPdfToCanonicalFactory:
    def create_for_openwebui(
        self,
        schema: Mapping[str, Any],
        request: Any,
        *,
        normalizer_config: CanonicalNormalizerConfig,
    ) -> "_ManagedPdfToCanonicalBuilder":
        return _ManagedPdfToCanonicalBuilder(
            schema=dict(schema),
            request=request,
            normalizer_config=normalizer_config,
        )

    def create_semantic_review_for_openwebui(
        self,
        schema: Mapping[str, Any],
        request: Any,
        user: Any,
        *,
        normalizer_config: CanonicalNormalizerConfig,
        provider_profile_id: str,
    ) -> "_ManagedPdfSemanticReviewProviderBuilder":
        base = self.create_for_openwebui(
            schema,
            request,
            normalizer_config=normalizer_config,
        )
        return _ManagedPdfSemanticReviewProviderBuilder(
            base_builder=base,
            request=request,
            user=user,
            provider_profile_id=provider_profile_id,
        )


@dataclass(frozen=True, slots=True)
class _ManagedPdfToCanonicalBuilder:
    schema: dict[str, Any]
    request: Any
    normalizer_config: CanonicalNormalizerConfig

    def build(
        self,
        content_bytes: bytes,
        *,
        tenant_id: str,
        artifact_version: int,
        source_artifact_ref: str,
        task_id: str,
        dpi: int = 150,
        created_at: str | None = None,
        previous_version_ref: str | None = None,
    ) -> ManagedPdfToCanonicalBuildResult:
        handoff = (
            ManagedPdfDocumentV2Factory()
            .create_adjudicated_for_openwebui(self.schema, self.request)
            ._build_owned_source_for_canonical(
                content_bytes,
                source_artifact_ref=source_artifact_ref,
                task_id=task_id,
                dpi=dpi,
            )
        )
        managed_result = handoff.result
        if (
            managed_result.status != "COMPLETE"
            or managed_result.managed_document is None
            or handoff.source_document is None
            or not managed_result.whole_table_projections
        ):
            return _blocked_result(
                managed_result,
                code="managed_pdf_to_canonical_managed_not_ready",
            )

        artifact = (
            CanonicalNormalizerFactory(self.normalizer_config)
            .create()
            ._build_pdf_from_managed_whole_table_projections(
                tenant_id=tenant_id,
                artifact_version=artifact_version,
                document=copy.deepcopy(handoff.source_document),
                source_artifact_ref=handoff.source_artifact_ref,
                source_payloads=list(copy.deepcopy(handoff.source_payloads)),
                source_units=list(copy.deepcopy(handoff.source_units)),
                managed_document_payload=copy.deepcopy(
                    managed_result.managed_document.payload
                ),
                managed_whole_table_projections=copy.deepcopy(
                    managed_result.whole_table_projections
                ),
                created_at=created_at,
                previous_version_ref=previous_version_ref,
            )
        )
        return ManagedPdfToCanonicalBuildResult(
            status="COMPLETE",
            managed_result=managed_result,
            canonical_artifact=artifact,
            safe_diagnostics={
                "schema_version": MANAGED_PDF_TO_CANONICAL_SCHEMA_VERSION,
                "status": "COMPLETE",
                "factory_route": [
                    "ManagedPdfToCanonicalFactory.create_for_openwebui",
                    "ManagedPdfDocumentV2Factory.create_adjudicated_for_openwebui",
                    "CanonicalNormalizerFactory.create",
                ],
                "managed_document_status": managed_result.status,
                "whole_table_projection_status": (
                    managed_result.whole_table_projection_diagnostics["status"]
                ),
                "canonical_artifacts_created": 1,
                "product_route_connected": False,
                "facts_published": 0,
                "private_values_included": False,
            },
            private_diagnostics={
                "schema_version": MANAGED_PDF_TO_CANONICAL_SCHEMA_VERSION,
                "status": "COMPLETE",
                "managed_document_integrity_sha256": (
                    managed_result.managed_document.integrity_sha256
                ),
                "canonical_artifact_id": artifact["artifact_id"],
            },
        )

    def build_with_semantic_evidence(
        self,
        content_bytes: bytes,
        *,
        tenant_id: str,
        artifact_version: int,
        source_artifact_ref: str,
        task_id: str,
        user_scope_sha256: str,
        dpi: int = 150,
        created_at: str | None = None,
        previous_version_ref: str | None = None,
    ) -> ManagedPdfToCanonicalSemanticEvidenceBuildResult:
        """Build inactive evidence before the same-call Canonical escapes."""

        result = self.build(
            content_bytes,
            tenant_id=tenant_id,
            artifact_version=artifact_version,
            source_artifact_ref=source_artifact_ref,
            task_id=task_id,
            dpi=dpi,
            created_at=created_at,
            previous_version_ref=previous_version_ref,
        )
        artifact = result.canonical_artifact
        managed_document = result.managed_result.managed_document
        if (
            result.status != "COMPLETE"
            or artifact is None
            or managed_document is None
        ):
            return ManagedPdfToCanonicalSemanticEvidenceBuildResult(
                status="BLOCKED",
                canonical_result=result,
                semantic_evidence=None,
            )
        source = artifact["source"]
        binding = {
            "document_id": str(managed_document.payload["document_id"]),
            "canonical_version_id": str(artifact["artifact_id"]),
            "canonical_root_sha256": str(artifact["canonical_root_hash"]),
            "source_artifact_ref": str(source["source_artifact_ref"]),
            "source_sha256": str(source["source_sha256"]),
        }
        evidence = _build_managed_document_semantic_evidence_from_owned_canonical(
            canonical=artifact,
            canonical_binding=binding,
            user_scope_sha256=user_scope_sha256,
        )
        return ManagedPdfToCanonicalSemanticEvidenceBuildResult(
            status="COMPLETE",
            canonical_result=result,
            semantic_evidence=evidence,
        )

    def build_with_semantic_review_contract(
        self,
        content_bytes: bytes,
        *,
        tenant_id: str,
        artifact_version: int,
        source_artifact_ref: str,
        task_id: str,
        user_scope_sha256: str,
        proposal_response: Any,
        critic_response: Any,
        dpi: int = 150,
        created_at: str | None = None,
        previous_version_ref: str | None = None,
    ) -> ManagedPdfToCanonicalSemanticReviewContractBuildResult:
        """Validate two raw inactive phases over one same-call evidence build."""

        evidence_result = self.build_with_semantic_evidence(
            content_bytes,
            tenant_id=tenant_id,
            artifact_version=artifact_version,
            source_artifact_ref=source_artifact_ref,
            task_id=task_id,
            user_scope_sha256=user_scope_sha256,
            dpi=dpi,
            created_at=created_at,
            previous_version_ref=previous_version_ref,
        )
        canonical = evidence_result.canonical_result.canonical_artifact
        evidence = evidence_result.semantic_evidence
        if evidence_result.status != "COMPLETE" or canonical is None or evidence is None:
            return ManagedPdfToCanonicalSemanticReviewContractBuildResult(
                status="BLOCKED",
                evidence_result=evidence_result,
                semantic_review_contract=None,
                reason_code="SEMANTIC_EVIDENCE_NOT_READY",
            )
        try:
            review = _review_owned_managed_document_semantic_evidence(
                canonical=canonical,
                canonical_binding=evidence["canonical_binding"],
                user_scope_sha256=user_scope_sha256,
                evidence=evidence,
                proposal_response=proposal_response,
                critic_response=critic_response,
            )
        except OrdinaryTradeSemanticMappingError:
            return ManagedPdfToCanonicalSemanticReviewContractBuildResult(
                status="BLOCKED",
                evidence_result=evidence_result,
                semantic_review_contract=None,
                reason_code="SEMANTIC_REVIEW_RESPONSE_INVALID",
            )
        return ManagedPdfToCanonicalSemanticReviewContractBuildResult(
            status=review["review_status"],
            evidence_result=evidence_result,
            semantic_review_contract=review,
            reason_code=None,
        )


@dataclass(frozen=True, slots=True)
class _ManagedPdfSemanticReviewProviderBuilder:
    base_builder: _ManagedPdfToCanonicalBuilder
    request: Any
    user: Any
    provider_profile_id: str

    async def build_with_semantic_provider_review(
        self,
        content_bytes: bytes,
        *,
        tenant_id: str,
        artifact_version: int,
        source_artifact_ref: str,
        task_id: str,
        user_scope_sha256: str,
        proposal_model_id: str,
        critic_model_id: str,
        dpi: int = 150,
        created_at: str | None = None,
        previous_version_ref: str | None = None,
    ) -> ManagedPdfToCanonicalSemanticProviderReviewBuildResult:
        """Run exactly one proposal and one critic over same-call PDF evidence."""

        evidence_result = self.base_builder.build_with_semantic_evidence(
            content_bytes,
            tenant_id=tenant_id,
            artifact_version=artifact_version,
            source_artifact_ref=source_artifact_ref,
            task_id=task_id,
            user_scope_sha256=user_scope_sha256,
            dpi=dpi,
            created_at=created_at,
            previous_version_ref=previous_version_ref,
        )
        canonical = evidence_result.canonical_result.canonical_artifact
        evidence = evidence_result.semantic_evidence
        accounting = {
            "local_invocations": 0,
            "provider_submissions": 0,
            "provider_responses": 0,
        }
        executions: list[dict[str, Any]] = []
        if evidence_result.status != "COMPLETE" or canonical is None or evidence is None:
            return _semantic_provider_result(
                evidence_result=evidence_result,
                status="BLOCKED",
                reason_code="SEMANTIC_EVIDENCE_NOT_READY",
                accounting=accounting,
                executions=executions,
            )

        proposal_client = self._client(MANAGED_DOCUMENT_SEMANTIC_PROPOSAL_REQUEST_PROFILE)
        prompt, package, response_format = _managed_semantic_proposal_model_request(
            evidence
        )
        proposal_raw, failure = await self._call_once(
            client=proposal_client,
            phase="PROPOSAL",
            prompt=prompt,
            package=package,
            model_id=proposal_model_id,
            response_format=response_format,
            accounting=accounting,
            executions=executions,
        )
        if failure is not None:
            return _semantic_provider_result(
                evidence_result=evidence_result,
                status="BLOCKED",
                reason_code=failure,
                accounting=accounting,
                executions=executions,
            )
        try:
            scope_ref = _managed_semantic_evidence_scope_ref(
                evidence["evidence_sha256"]
            )
            options, proposal_ref, _ = _managed_semantic_proposal(
                canonical=canonical,
                canonical_binding=evidence["canonical_binding"],
                evidence=evidence,
                evidence_scope_ref=scope_ref,
                response=proposal_raw,
            )
        except OrdinaryTradeSemanticMappingError:
            return _semantic_provider_result(
                evidence_result=evidence_result,
                status="BLOCKED",
                reason_code="PROPOSAL_RESPONSE_INVALID",
                accounting=accounting,
                executions=executions,
            )

        critic_client = self._client(MANAGED_DOCUMENT_SEMANTIC_CRITIC_REQUEST_PROFILE)
        prompt, package, response_format = _managed_semantic_critic_model_request(
            evidence=evidence,
            options=options,
            proposal_ref=proposal_ref,
        )
        critic_raw, failure = await self._call_once(
            client=critic_client,
            phase="CRITIC",
            prompt=prompt,
            package=package,
            model_id=critic_model_id,
            response_format=response_format,
            accounting=accounting,
            executions=executions,
        )
        if failure is not None:
            return _semantic_provider_result(
                evidence_result=evidence_result,
                status="BLOCKED",
                reason_code=failure,
                accounting=accounting,
                executions=executions,
            )
        try:
            review = _review_owned_managed_document_semantic_evidence(
                canonical=canonical,
                canonical_binding=evidence["canonical_binding"],
                user_scope_sha256=user_scope_sha256,
                evidence=evidence,
                proposal_response=proposal_raw,
                critic_response=critic_raw,
            )
        except OrdinaryTradeSemanticMappingError:
            return _semantic_provider_result(
                evidence_result=evidence_result,
                status="BLOCKED",
                reason_code="CRITIC_RESPONSE_INVALID",
                accounting=accounting,
                executions=executions,
            )
        if accounting != {
            "local_invocations": 2,
            "provider_submissions": 2,
            "provider_responses": 2,
        }:
            return _semantic_provider_result(
                evidence_result=evidence_result,
                status="BLOCKED",
                reason_code="SEMANTIC_PROVIDER_ACCOUNTING_INVALID",
                accounting=accounting,
                executions=executions,
            )
        return _semantic_provider_result(
            evidence_result=evidence_result,
            status=review["review_status"],
            reason_code=None,
            accounting=accounting,
            executions=executions,
            review=review,
        )

    def _client(self, request_profile: str):
        return Gate2StructuredModelClientFactory(
            config=Gate2StructuredModelClientConfig(
                request_profile=request_profile,
                provider_profile_id=self.provider_profile_id,
            ),
            user=self.user,
            request=self.request,
        ).create()

    @staticmethod
    async def _call_once(
        *, client, phase, prompt, package, model_id, response_format,
        accounting, executions,
    ) -> tuple[Any, str | None]:
        before = client.qualification_lifecycle_snapshot()
        try:
            result = await client.extract(
                prompt=prompt,
                package=package,
                model_id=model_id,
                response_format=response_format,
            )
        except Gate2SourceFactRuntimeError:
            after = client.qualification_lifecycle_snapshot()
            _merge_semantic_lifecycle(accounting, before, after)
            return None, f"{phase}_PROVIDER_FAILED"
        after = client.qualification_lifecycle_snapshot()
        delta = _merge_semantic_lifecycle(accounting, before, after)
        if delta != {
            "local_invocations": 1,
            "provider_submissions": 1,
            "provider_responses": 1,
        }:
            return None, f"{phase}_PROVIDER_FAILED"
        metadata = result.execution_metadata
        if (
            metadata is None
            or result.structured_output_mode
            not in {
                "openwebui_response_format_json_schema",
                "openwebui_anthropic_output_config_json_schema",
            }
            or result.response_format_type != "json_schema"
            or result.response_format_schema_mode != "strict_json_schema"
            or result.fallback_used is not False
            or result.repair_attempt_count != 0
        ):
            return None, f"{phase}_PROVIDER_FAILED"
        executions.append(
            {
                "phase": phase,
                "fallback_used": False,
                "repair_attempt_count": 0,
                "provider_execution": metadata.snapshot(),
            }
        )
        return copy.deepcopy(result.content), None


def _merge_semantic_lifecycle(
    accounting: dict[str, int], before: Mapping[str, int], after: Mapping[str, int]
) -> dict[str, int]:
    keys = {
        "local_invocations": "local_invocations_total",
        "provider_submissions": "provider_submissions_total",
        "provider_responses": "provider_responses_total",
    }
    delta_by_target = {}
    for target, source in keys.items():
        delta = after[source] - before[source]
        if delta not in {0, 1}:
            raise RuntimeError("managed_semantic_provider_accounting_invalid")
        accounting[target] += delta
        delta_by_target[target] = delta
    if not (
        accounting["provider_responses"]
        <= accounting["provider_submissions"]
        <= accounting["local_invocations"]
        <= 2
    ):
        raise RuntimeError("managed_semantic_provider_accounting_invalid")
    return delta_by_target


def _semantic_provider_result(
    *, evidence_result, status, reason_code, accounting, executions, review=None
) -> ManagedPdfToCanonicalSemanticProviderReviewBuildResult:
    receipt = {
        "schema_version": "managed_document_semantic_provider_execution_v1",
        "semantic_calls_limit": 2,
        "retry_count": 0,
        **copy.deepcopy(accounting),
        "executions": copy.deepcopy(executions),
        "facts_published": 0,
        "record_candidates_created": 0,
    }
    return ManagedPdfToCanonicalSemanticProviderReviewBuildResult(
        status=status,
        evidence_result=evidence_result,
        semantic_review_contract=copy.deepcopy(review),
        execution_receipt=receipt,
        reason_code=reason_code,
    )


def _blocked_result(
    managed_result: ManagedPdfDocumentV2AdjudicatedBuildResult,
    *,
    code: str,
) -> ManagedPdfToCanonicalBuildResult:
    return ManagedPdfToCanonicalBuildResult(
        status="BLOCKED",
        managed_result=managed_result,
        canonical_artifact=None,
        safe_diagnostics={
            "schema_version": MANAGED_PDF_TO_CANONICAL_SCHEMA_VERSION,
            "status": "BLOCKED",
            "reason_code": code,
            "managed_document_status": managed_result.status,
            "canonical_artifacts_created": 0,
            "product_route_connected": False,
            "facts_published": 0,
            "private_values_included": False,
        },
        private_diagnostics={
            "schema_version": MANAGED_PDF_TO_CANONICAL_SCHEMA_VERSION,
            "status": "BLOCKED",
            "reason_code": code,
        },
    )
