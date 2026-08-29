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


MANAGED_PDF_TO_CANONICAL_SCHEMA_VERSION = (
    "broker_reports_managed_pdf_to_canonical_route_v1"
)
FACTORY_REQUIRED = (
    "ManagedPdfToCanonicalFactory.create_for_openwebui is the only inactive "
    "same-call coordinator from adjudicated Managed PDF v2 to CanonicalArtifactV1"
)
FORBIDDEN = (
    "The route must not accept caller-supplied source payloads, source units, "
    "Managed payloads, table projections, product routes, facts, stores or "
    "runtime publication callbacks"
)


@dataclass(frozen=True)
class ManagedPdfToCanonicalBuildResult:
    status: str
    managed_result: ManagedPdfDocumentV2AdjudicatedBuildResult
    canonical_artifact: dict[str, Any] | None
    safe_diagnostics: dict[str, Any]
    private_diagnostics: dict[str, Any]


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
