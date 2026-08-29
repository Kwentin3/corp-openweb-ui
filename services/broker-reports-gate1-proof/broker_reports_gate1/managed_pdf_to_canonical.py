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
from .ordinary_trade_semantic_mapping import (
    _build_managed_document_semantic_evidence_from_owned_canonical,
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
