from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

from .full_source import FullSourceArtifactFactory, validate_full_source_unit
from .logical_row_table_recovery import (
    LogicalRowTableFactory,
    LogicalRowTableRecoveryResult,
    logical_table_block_id,
)
from .managed_document_contracts_v2 import (
    ManagedDocumentContractV2Validator,
    ManagedDocumentV2,
)
from .managed_whole_table_projection import (
    _ManagedWholeTableProjectionResult,
    _project_sealed_adjudicated_managed_document,
)
from .pdf_document_visual_adjudication import (
    PdfDocumentVisualAdjudicationFactory,
    PdfDocumentVisualAdjudicationResult,
)
from .pdf_text_layer import (
    validate_pdf_source_unit,
    validate_pdf_text_layer_payload,
)


MANAGED_PDF_V2_BUILDER_VERSION = (
    "broker_reports_managed_pdf_document_v2_builder_v1"
)
SAFE_BUILD_DIAGNOSTICS_SCHEMA_VERSION = (
    "broker_reports_managed_pdf_document_v2_build_safe_v1"
)
PRIVATE_BUILD_DIAGNOSTICS_SCHEMA_VERSION = (
    "broker_reports_managed_pdf_document_v2_build_private_v1"
)
_SOURCE_BOUND_RECOVERY_ONLY_SOURCE_PART_FIELDS = frozenset(
    {
        "source_bound_scope_ref",
        "source_bound_binding_status",
        "source_bound_structural_authority",
        "source_bound_proposal_sha256",
        "source_bound_raster_manifest_hash",
        "source_bound_receipt_title_word_refs",
        "source_bound_receipt_header_word_ref_groups",
        "source_bound_receipt_body_word_refs",
        "source_bound_title_word_refs",
        "source_bound_header_status",
        "source_bound_header_word_ref_groups",
        "source_bound_body_word_refs",
    }
)

FACTORY_REQUIRED = (
    "ManagedPdfDocumentV2Factory.create preserves the legacy route; "
    "ManagedPdfDocumentV2Factory.create_adjudicated_for_openwebui is the sole "
    "inactive reviewed PDF to Managed Document v2 orchestration route"
)
FORBIDDEN = (
    "The v2 builder must not read PdfLayoutUnitBuilder units, historical grid "
    "owners, public raw scopes/results/receipts/plans, visual gold, product "
    "routes, Canonical/fact owners, or generated bundles"
)


class ManagedPdfDocumentV2Error(ValueError):
    """Raised when the inactive v2 document cannot be assembled exactly."""


@dataclass(frozen=True)
class ManagedPdfDocumentV2Config:
    created_at: str = "2026-08-02T00:00:00Z"
    profile_id: str = "broker_reports_managed_document_v2"


@dataclass(frozen=True)
class ManagedPdfDocumentV2BuildResult:
    status: str
    managed_document: ManagedDocumentV2
    safe_diagnostics: dict[str, Any]
    private_diagnostics: dict[str, Any]


@dataclass(frozen=True)
class ManagedPdfDocumentV2AdjudicatedBuildResult:
    status: str
    managed_document: ManagedDocumentV2 | None
    safe_diagnostics: dict[str, Any]
    private_diagnostics: dict[str, Any]
    whole_table_projections: tuple[dict[str, Any], ...]
    whole_table_projection_diagnostics: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _ManagedPdfDocumentV2CanonicalHandoff:
    result: ManagedPdfDocumentV2AdjudicatedBuildResult
    source_document: dict[str, Any] | None
    source_payloads: tuple[dict[str, Any], ...]
    source_units: tuple[dict[str, Any], ...]
    source_artifact_ref: str


class ManagedPdfDocumentV2Factory:
    """Compose the established FullSource, recovery and v2 contract owners."""

    def __init__(
        self,
        config: ManagedPdfDocumentV2Config | None = None,
    ) -> None:
        self.config = config or ManagedPdfDocumentV2Config()

    def create(self, schema: Mapping[str, Any]) -> "ManagedPdfDocumentV2Builder":
        if not self.config.created_at or not self.config.profile_id:
            raise ManagedPdfDocumentV2Error(
                "managed_pdf_v2_config_invalid"
            )
        return ManagedPdfDocumentV2Builder(
            config=self.config,
            schema_json=_validated_schema_json(schema),
        )

    def create_adjudicated_for_openwebui(
        self,
        schema: Mapping[str, Any],
        request: Any,
    ) -> "_ManagedPdfDocumentV2AdjudicatedBuilder":
        if not self.config.created_at or not self.config.profile_id:
            raise ManagedPdfDocumentV2Error(
                "managed_pdf_v2_config_invalid"
            )
        return _ManagedPdfDocumentV2AdjudicatedBuilder(
            config=self.config,
            schema_json=_validated_schema_json(schema),
            _adjudicator=(
                PdfDocumentVisualAdjudicationFactory().create_for_openwebui(
                    request
                )
            ),
        )


class ManagedPdfDocumentV2Builder:
    __slots__ = ("config", "_schema_json")

    def __init__(
        self,
        *,
        config: ManagedPdfDocumentV2Config,
        schema_json: bytes,
    ) -> None:
        self.config = config
        self._schema_json = schema_json

    def build(
        self,
        content_bytes: bytes,
        *,
        source_artifact_ref: str | None = None,
    ) -> ManagedPdfDocumentV2BuildResult:
        return self._build_owned_source(
            content_bytes=content_bytes,
            source_artifact_ref=source_artifact_ref,
        )

    def _build_adjudicated(
        self,
        content_bytes: bytes,
        *,
        source_artifact_ref: str | None = None,
        task_id: str,
        dpi: int,
        adjudicator: Any,
        return_canonical_handoff: bool = False,
    ) -> ManagedPdfDocumentV2AdjudicatedBuildResult | _ManagedPdfDocumentV2CanonicalHandoff:
        adjudicator._assert_authority()
        return self._build_owned_source(
            content_bytes=content_bytes,
            source_artifact_ref=source_artifact_ref,
            task_id=_adjudication_task_id(task_id),
            dpi=_adjudication_dpi(dpi),
            adjudicator=adjudicator,
            return_canonical_handoff=return_canonical_handoff,
        )

    def _build_owned_source(
        self,
        *,
        content_bytes: bytes,
        source_artifact_ref: str | None,
        task_id: str | None = None,
        dpi: int = 150,
        adjudicator: Any = None,
        return_canonical_handoff: bool = False,
    ) -> (
        ManagedPdfDocumentV2BuildResult
        | ManagedPdfDocumentV2AdjudicatedBuildResult
        | _ManagedPdfDocumentV2CanonicalHandoff
    ):
        if not isinstance(content_bytes, bytes) or not content_bytes:
            raise ManagedPdfDocumentV2Error(
                "managed_pdf_v2_source_bytes_invalid"
        )
        private_ref = _private_source_ref(source_artifact_ref)
        document_id = _identifier(
            "document_pdf",
            ["private_source_artifact_identity", private_ref],
        )
        source_checksum = hashlib.sha256(content_bytes).hexdigest()
        full_source = FullSourceArtifactFactory().create().build(
            normalization_run_id=f"normrun_doc6_{source_checksum[:24]}",
            document_id=document_id,
            profile_id=self.config.profile_id,
            container_format="pdf",
            content_bytes=content_bytes,
            source_checksum_sha256=source_checksum,
        )
        payload = _sole_complete_pdf_payload(full_source)
        projection = payload.get("pdf_text_layer_projection")
        if not isinstance(projection, Mapping):
            raise ManagedPdfDocumentV2Error(
                "managed_pdf_v2_full_source_projection_missing"
            )
        adjudication: PdfDocumentVisualAdjudicationResult | None = None
        if task_id is None:
            recovered = LogicalRowTableFactory().create().recover(
                projection,
                source_checksum_sha256=source_checksum,
                private_evidence_ref=private_ref,
            )
        else:
            adjudication = adjudicator.adjudicate(
                task_id=task_id,
                pdf_bytes=content_bytes,
                full_source_payload=payload,
                source_checksum_sha256=source_checksum,
                private_evidence_ref=private_ref,
                dpi=dpi,
            )
            if adjudication.status != "COVERAGE_COMPLETE":
                partial = _partial_adjudicated_result(
                    adjudication=adjudication,
                    document_id=document_id,
                    source_checksum=source_checksum,
                    private_ref=private_ref,
                    full_source=full_source,
                    payload=payload,
                )
                if return_canonical_handoff:
                    return _canonical_handoff(
                        result=partial,
                        source_checksum=source_checksum,
                        document_id=document_id,
                        private_ref=private_ref,
                        full_source=full_source,
                    )
                return partial
            recovered = adjudication.recovery
        recovered, reviewed_plan = _managed_document_recovery_projection(
            recovered,
            allow_reviewed=adjudication is not None,
        )
        candidate, assembly = _assemble_document(
            projection=projection,
            recovered=recovered,
            document_id=document_id,
            content_size=len(content_bytes),
            source_checksum_sha256=source_checksum,
            private_source_ref=private_ref,
            created_at=self.config.created_at,
        )
        if (
            adjudication is not None
            and candidate["quality"]["status"] != "COMPLETE"
        ):
            partial = _partial_adjudicated_result(
                adjudication=adjudication,
                document_id=document_id,
                source_checksum=source_checksum,
                private_ref=private_ref,
                full_source=full_source,
                payload=payload,
                detail_code="managed_pdf_v2_candidate_partial",
            )
            if return_canonical_handoff:
                return _canonical_handoff(
                    result=partial,
                    source_checksum=source_checksum,
                    document_id=document_id,
                    private_ref=private_ref,
                    full_source=full_source,
                )
            return partial
        source_unit_ledger_plan: tuple[dict[str, Any], ...] = ()
        if adjudication is not None:
            try:
                source_unit_ledger_plan = _bind_source_unit_ledger(
                    candidate=candidate,
                    full_source=full_source,
                    source_checksum_sha256=source_checksum,
                )
            except ManagedPdfDocumentV2Error as exc:
                partial = _partial_adjudicated_result(
                    adjudication=adjudication,
                    document_id=document_id,
                    source_checksum=source_checksum,
                    private_ref=private_ref,
                    full_source=full_source,
                    payload=payload,
                    detail_code=str(exc),
                )
                if return_canonical_handoff:
                    return _canonical_handoff(
                        result=partial,
                        source_checksum=source_checksum,
                        document_id=document_id,
                        private_ref=private_ref,
                        full_source=full_source,
                    )
                return partial
        validator = ManagedDocumentContractV2Validator(
            json.loads(self._schema_json.decode("utf-8"))
        )
        managed_document = (
            validator._seal_adjudicated_source_unit_ledger(
                candidate,
                expected_reviewed_source_bound=reviewed_plan,
                expected_source_unit_ledger=source_unit_ledger_plan,
            )
            if adjudication is not None
            else validator._seal_reviewed_source_bound(
                candidate,
                expected_reviewed_source_bound=reviewed_plan,
            )
            if reviewed_plan
            else validator.seal(candidate)
        )
        whole_table_projection: _ManagedWholeTableProjectionResult | None = None
        if adjudication is not None:
            whole_table_projection = (
                _project_sealed_adjudicated_managed_document(
                    managed_document,
                    expected_source_unit_ledger=source_unit_ledger_plan,
                )
            )
        status = str(managed_document.payload["quality"]["status"])
        safe_diagnostics = {
            "schema_version": SAFE_BUILD_DIAGNOSTICS_SCHEMA_VERSION,
            "builder_version": MANAGED_PDF_V2_BUILDER_VERSION,
            "status": status,
            "pages_total": assembly["pages_total"],
            "source_words_total": assembly["source_words_total"],
            "logical_tables_total": assembly["logical_tables_total"],
            "logical_rows_total": assembly["logical_rows_total"],
            "paragraph_blocks_total": assembly["paragraph_blocks_total"],
            "table_words_total": assembly["table_words_total"],
            "paragraph_words_total": assembly["paragraph_words_total"],
            "unowned_words_total": 0,
            "multiple_word_owners_total": 0,
            "paragraph_table_overlap_total": 0,
            "factory_route": (
                [
                    "ManagedPdfDocumentV2Factory.create",
                    "FullSourceArtifactFactory.create",
                    "LogicalRowTableFactory.create",
                    "ManagedDocumentContractV2Validator.seal",
                ]
                if adjudication is None
                else [
                    (
                        "ManagedPdfDocumentV2Factory."
                        "create_adjudicated_for_openwebui"
                    ),
                    "FullSourceArtifactFactory.create",
                    (
                        "PdfDocumentVisualAdjudicationFactory."
                        "create_for_openwebui"
                    ),
                    "LogicalRowTableFactory.create",
                    "ManagedDocumentContractV2Validator.seal",
                ]
            ),
            "canonical_projection_field": (
                "FullSourceBuildResult.payloads[0]."
                "pdf_text_layer_projection"
            ),
            "pdf_layout_units_consumed": 0,
            "grid_owner_calls": 0,
            "provider_calls_total": (
                0
                if adjudication is None
                else adjudication.provider_accounting[
                    "provider_http_calls"
                ]
            ),
            **(
                {
                    "provider_http_calls": adjudication.provider_accounting[
                        "provider_http_calls"
                    ],
                    "model_generation_calls": (
                        adjudication.provider_accounting[
                            "model_generation_calls"
                        ]
                    ),
                    "count_tokens_http_calls": (
                        adjudication.provider_accounting[
                            "count_tokens_http_calls"
                        ]
                    ),
                    "same_raster_binding": adjudication.provider_accounting[
                        "same_raster_binding"
                    ],
                    "managed_document_created": True,
                    "whole_table_projection_status": (
                        whole_table_projection.status
                    ),
                    "whole_table_projections_total": len(
                        whole_table_projection.projections
                    ),
                    "canonical_artifacts_created": 0,
                    "facts_published": 0,
                }
                if adjudication is not None
                else {}
            ),
            "product_route_connected": False,
            "generated_bundle_connected": False,
            "private_values_included": False,
            "managed_document_schema_canonical_sha256": (
                validator.schema_canonical_sha256
            ),
            "managed_document_integrity_sha256": (
                managed_document.integrity_sha256
            ),
        }
        private_diagnostics = {
            "schema_version": PRIVATE_BUILD_DIAGNOSTICS_SCHEMA_VERSION,
            "builder_version": MANAGED_PDF_V2_BUILDER_VERSION,
            "document_id": document_id,
            "source_checksum_sha256": source_checksum,
            "private_source_ref": private_ref,
            "full_source_payload_ref": payload.get("source_payload_ref"),
            "full_source_summary": copy.deepcopy(
                getattr(full_source, "summary", {})
            ),
            "recovery_schema_version": recovered.schema_version,
            "recovery_policy_version": recovered.recovery_policy_version,
            "recovery_diagnostics": copy.deepcopy(recovered.diagnostics),
            "paragraph_owned_word_refs": list(
                recovered.paragraph_owned_word_refs
            ),
            "unowned_word_refs": list(recovered.unowned_word_refs),
            "table_ids": [
                str(table["table_id"]) for table in recovered.tables
            ],
            "managed_document_integrity_sha256": (
                managed_document.integrity_sha256
            ),
            **(
                {
                    "adjudication_status": adjudication.status,
                    "adjudication_provider_accounting": copy.deepcopy(
                        adjudication.provider_accounting
                    ),
                    "adjudication_page_coverage": copy.deepcopy(
                        list(adjudication.page_coverage)
                    ),
                    "adjudication_issues": copy.deepcopy(
                        list(adjudication.issues)
                    ),
                    "whole_table_projection_status": (
                        whole_table_projection.status
                    ),
                    "whole_table_projection_issues": copy.deepcopy(
                        list(whole_table_projection.issues)
                    ),
                }
                if adjudication is not None
                else {}
            ),
        }
        if adjudication is not None:
            result = ManagedPdfDocumentV2AdjudicatedBuildResult(
                status=status,
                managed_document=managed_document,
                safe_diagnostics=safe_diagnostics,
                private_diagnostics=private_diagnostics,
                whole_table_projections=whole_table_projection.projections,
                whole_table_projection_diagnostics={
                    "status": whole_table_projection.status,
                    "issues": copy.deepcopy(list(whole_table_projection.issues)),
                },
            )
            if return_canonical_handoff:
                return _canonical_handoff(
                    result=result,
                    source_checksum=source_checksum,
                    document_id=document_id,
                    private_ref=private_ref,
                    full_source=full_source,
                )
            return result
        return ManagedPdfDocumentV2BuildResult(
            status=status,
            managed_document=managed_document,
            safe_diagnostics=safe_diagnostics,
            private_diagnostics=private_diagnostics,
        )


@dataclass(frozen=True, slots=True)
class _ManagedPdfDocumentV2AdjudicatedBuilder:
    config: ManagedPdfDocumentV2Config
    schema_json: bytes
    _adjudicator: Any

    def build(
        self,
        content_bytes: bytes,
        *,
        source_artifact_ref: str | None = None,
        task_id: str,
        dpi: int = 150,
    ) -> ManagedPdfDocumentV2AdjudicatedBuildResult:
        return ManagedPdfDocumentV2Builder(
            config=self.config,
            schema_json=self.schema_json,
        )._build_adjudicated(
            content_bytes,
            source_artifact_ref=source_artifact_ref,
            task_id=task_id,
            dpi=dpi,
            adjudicator=self._adjudicator,
        )

    def _build_owned_source_for_canonical(
        self,
        content_bytes: bytes,
        *,
        source_artifact_ref: str | None = None,
        task_id: str,
        dpi: int = 150,
    ) -> _ManagedPdfDocumentV2CanonicalHandoff:
        return ManagedPdfDocumentV2Builder(
            config=self.config,
            schema_json=self.schema_json,
        )._build_adjudicated(
            content_bytes,
            source_artifact_ref=source_artifact_ref,
            task_id=task_id,
            dpi=dpi,
            adjudicator=self._adjudicator,
            return_canonical_handoff=True,
        )


def _validated_schema_json(schema: Mapping[str, Any]) -> bytes:
    validated_schema = copy.deepcopy(dict(schema))
    ManagedDocumentContractV2Validator(validated_schema)
    return json.dumps(
        validated_schema,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _adjudication_task_id(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 180
    ):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_adjudication_task_id_invalid"
        )
    return value


def _adjudication_dpi(value: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 72
        or value > 300
    ):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_adjudication_dpi_invalid"
        )
    return value


def _partial_adjudicated_result(
    *,
    adjudication: PdfDocumentVisualAdjudicationResult,
    document_id: str,
    source_checksum: str,
    private_ref: str,
    full_source: Any,
    payload: Mapping[str, Any],
    detail_code: str | None = None,
) -> ManagedPdfDocumentV2AdjudicatedBuildResult:
    accounting = copy.deepcopy(adjudication.provider_accounting)
    safe_diagnostics = {
        "schema_version": SAFE_BUILD_DIAGNOSTICS_SCHEMA_VERSION,
        "builder_version": MANAGED_PDF_V2_BUILDER_VERSION,
        "status": "PARTIAL",
        "factory_route": [
            "ManagedPdfDocumentV2Factory.create_adjudicated_for_openwebui",
            "FullSourceArtifactFactory.create",
            "PdfDocumentVisualAdjudicationFactory.create_for_openwebui",
            "LogicalRowTableFactory.create",
        ],
        "provider_calls_total": accounting["provider_http_calls"],
        "provider_http_calls": accounting["provider_http_calls"],
        "model_generation_calls": accounting["model_generation_calls"],
        "count_tokens_http_calls": accounting["count_tokens_http_calls"],
        "same_raster_binding": accounting["same_raster_binding"],
        "managed_document_created": False,
        "whole_table_projection_status": "NOT_READY",
        "whole_table_projections_total": 0,
        "canonical_artifacts_created": 0,
        "facts_published": 0,
        "product_route_connected": False,
        "generated_bundle_connected": False,
        "private_values_included": False,
    }
    private_diagnostics = {
        "schema_version": PRIVATE_BUILD_DIAGNOSTICS_SCHEMA_VERSION,
        "builder_version": MANAGED_PDF_V2_BUILDER_VERSION,
        "document_id": document_id,
        "source_checksum_sha256": source_checksum,
        "private_source_ref": private_ref,
        "full_source_payload_ref": payload.get("source_payload_ref"),
        "full_source_summary": copy.deepcopy(
            getattr(full_source, "summary", {})
        ),
        "adjudication_status": adjudication.status,
        "adjudication_provider_accounting": accounting,
        "adjudication_page_coverage": copy.deepcopy(
            list(adjudication.page_coverage)
        ),
        "adjudication_observation_coverage": copy.deepcopy(
            list(adjudication.observation_coverage)
        ),
        "adjudication_parser_candidate_coverage": copy.deepcopy(
            list(adjudication.parser_candidate_coverage)
        ),
        "adjudication_issues": copy.deepcopy(list(adjudication.issues)),
        "recovery_diagnostics": copy.deepcopy(
            adjudication.recovery.diagnostics
        ),
        **({"detail_code": detail_code} if detail_code is not None else {}),
    }
    return ManagedPdfDocumentV2AdjudicatedBuildResult(
        status="PARTIAL",
        managed_document=None,
        safe_diagnostics=safe_diagnostics,
        private_diagnostics=private_diagnostics,
        whole_table_projections=(),
        whole_table_projection_diagnostics={
            "status": "NOT_READY",
            "issues": [
                {"code": "managed_whole_table_projection_managed_missing"}
            ],
        },
    )


def _canonical_handoff(
    *,
    result: ManagedPdfDocumentV2AdjudicatedBuildResult,
    source_checksum: str,
    document_id: str,
    private_ref: str,
    full_source: Any,
) -> _ManagedPdfDocumentV2CanonicalHandoff:
    return _ManagedPdfDocumentV2CanonicalHandoff(
        result=result,
        source_document={
            "container_format": "pdf",
            "sha256": source_checksum,
            "declared_mime_type": "application/pdf",
            "document_id": document_id,
        },
        source_payloads=tuple(copy.deepcopy(full_source.payloads)),
        source_units=tuple(copy.deepcopy(full_source.units)),
        source_artifact_ref=private_ref,
    )


def _private_source_ref(value: str | None) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 180
    ):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_private_source_ref_required"
        )
    return value


def _managed_document_recovery_projection(
    recovered: LogicalRowTableRecoveryResult,
    *,
    allow_reviewed: bool,
) -> tuple[LogicalRowTableRecoveryResult, tuple[dict[str, Any], ...]]:
    """Adapt same-call receipt transport into inspectable v2 provenance."""

    if _recovery_contains_ready_reviewed_evidence(recovered):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_ready_reviewed_evidence_forbidden"
        )
    if not allow_reviewed and _recovery_contains_source_bound_fields(recovered):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_reviewed_source_bound_legacy_forbidden"
        )
    tables = copy.deepcopy(recovered.tables)
    anchor_by_id = {
        str(anchor.get("anchor_id") or ""): anchor
        for anchor in recovered.anchors
        if isinstance(anchor, dict)
    }
    for table in tables:
        reviewed_refs_by_role = {
            "TABLE_TITLE": set(),
            "COLUMN_HEADER": set(),
            "DATA": set(),
        }
        for source_part in table.get("source_parts") or []:
            if not isinstance(source_part, dict):
                continue
            scope_ref = source_part.get("source_bound_scope_ref")
            binding_status = source_part.get("source_bound_binding_status")
            proposal_sha256 = source_part.get("source_bound_proposal_sha256")
            raster_sha256 = source_part.get(
                "source_bound_raster_manifest_hash"
            )
            title_refs = list(
                source_part.get("source_bound_receipt_title_word_refs") or []
            )
            header_groups = list(
                source_part.get("source_bound_receipt_header_word_ref_groups")
                or []
            )
            header_refs = [ref for group in header_groups for ref in group]
            body_refs = list(
                source_part.get("source_bound_receipt_body_word_refs") or []
            )
            accepted_structural = (
                source_part.get("source_bound_structural_authority") is True
                and binding_status == "BOUND"
                and source_part.get("source_bound_header_status") == "PRESENT"
                and list(
                    source_part.get("source_bound_header_word_ref_groups")
                    or []
                )
                == header_groups
                and list(source_part.get("source_bound_body_word_refs") or [])
                == body_refs
                and list(source_part.get("source_bound_title_word_refs") or [])
                == title_refs
            )
            if all(
                isinstance(value, str) and value
                for value in (scope_ref, proposal_sha256, raster_sha256)
            ):
                evidence = {
                    "binding_status": binding_status,
                    "scope_receipt_ref": scope_ref,
                    "proposal_sha256": proposal_sha256,
                    "raster_manifest_sha256": raster_sha256,
                    "title_word_refs": title_refs,
                    "header_word_refs": header_refs,
                    "body_word_refs": body_refs,
                }
                if accepted_structural:
                    source_part["reviewed_source_bound_evidence"] = {
                        "origin": "REVIEWED_SOURCE_BOUND",
                        **evidence,
                    }
                    reviewed_refs_by_role["TABLE_TITLE"].update(title_refs)
                    reviewed_refs_by_role["COLUMN_HEADER"].update(header_refs)
                    reviewed_refs_by_role["DATA"].update(body_refs)
                else:
                    source_part["source_bound_audit_evidence"] = {
                        "structural_authority": False,
                        **evidence,
                    }
            for field in _SOURCE_BOUND_RECOVERY_ONLY_SOURCE_PART_FIELDS:
                source_part.pop(field, None)
        for row in table.get("ordered_rows") or []:
            if not isinstance(row, dict):
                continue
            role = str(row.get("role") or "")
            reviewed_refs = reviewed_refs_by_role.get(role, set())
            row_word_refs = _row_word_refs(row, anchor_by_id=anchor_by_id)
            if reviewed_refs and row_word_refs and row_word_refs <= reviewed_refs:
                row["role_origin"] = "REVIEWED_SOURCE_BOUND"
                for entry in row.get("entries") or []:
                    if isinstance(entry, dict):
                        entry["origin"] = "REVIEWED_SOURCE_BOUND"
    return replace(recovered, tables=tables), _reviewed_source_bound_plan(tables)


def _recovery_contains_source_bound_fields(
    recovered: LogicalRowTableRecoveryResult,
) -> bool:
    return any(
        isinstance(part, Mapping)
        and any(str(key).startswith("source_bound_") for key in part)
        for table in recovered.tables
        for part in table.get("source_parts") or []
    )


def _recovery_contains_ready_reviewed_evidence(
    recovered: LogicalRowTableRecoveryResult,
) -> bool:
    return any(
        (
            isinstance(part, Mapping)
            and (
                "reviewed_source_bound_evidence" in part
                or "source_bound_audit_evidence" in part
            )
        )
        for table in recovered.tables
        for part in table.get("source_parts") or []
    ) or any(
        row.get("role_origin") == "REVIEWED_SOURCE_BOUND"
        or any(
            entry.get("origin") == "REVIEWED_SOURCE_BOUND"
            for entry in row.get("entries") or []
        )
        for table in recovered.tables
        for row in table.get("ordered_rows") or []
    )


def _reviewed_source_bound_plan(
    tables: list[dict[str, Any]],
) -> tuple[dict[str, Any], ...]:
    plan: list[dict[str, Any]] = []
    for table in tables:
        rows = list(table.get("ordered_rows") or [])
        row_ordinal = {
            str(row.get("row_id") or ""): index
            for index, row in enumerate(rows)
        }
        for part in table.get("source_parts") or []:
            evidence = part.get("reviewed_source_bound_evidence")
            if not isinstance(evidence, dict):
                continue
            first = row_ordinal[str(part["first_row_id"])]
            last = row_ordinal[str(part["last_row_id"])]
            reviewed_rows = [
                {
                    "row_id": row["row_id"],
                    "role": row["role"],
                    "role_origin": row["role_origin"],
                    "entries": [
                        {
                            "entry_id": entry["entry_id"],
                            "origin": entry["origin"],
                        }
                        for entry in row["entries"]
                    ],
                }
                for row in rows[first : last + 1]
                if row["role_origin"] == "REVIEWED_SOURCE_BOUND"
            ]
            plan.append(
                {
                    "table_id": table["table_id"],
                    "source_part_id": part["source_part_id"],
                    "evidence": copy.deepcopy(evidence),
                    "reviewed_rows": reviewed_rows,
                }
            )
    return tuple(plan)


def _row_word_refs(
    row: Mapping[str, Any],
    *,
    anchor_by_id: Mapping[str, Mapping[str, Any]],
) -> set[str]:
    refs: set[str] = set()
    for anchor_id in row.get("source_anchor_ids") or []:
        anchor = anchor_by_id.get(str(anchor_id))
        locator = anchor.get("locator") if isinstance(anchor, Mapping) else None
        if isinstance(locator, Mapping) and locator.get("source_block_ref"):
            refs.add(str(locator["source_block_ref"]))
    return refs


def _bind_source_unit_ledger(
    *,
    candidate: dict[str, Any],
    full_source: Any,
    source_checksum_sha256: str,
) -> tuple[dict[str, Any], ...]:
    """Bind sealed table words to whole FullSource units in the same call."""

    units = getattr(full_source, "units", None)
    if not isinstance(units, list):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_source_unit_ledger_units_missing"
        )
    parent_payload = _sole_complete_pdf_payload(full_source)
    parent_validation = validate_pdf_text_layer_payload(parent_payload)
    if parent_validation.get("validator_status") != "passed":
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_source_unit_ledger_parent_payload_invalid"
        )
    document_id = str(candidate.get("document_id") or "")
    if parent_payload.get("document_ref") != document_id:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_source_unit_ledger_parent_document_mismatch"
        )
    expected_run_id = str(parent_payload.get("normalization_run_id") or "")
    extraction_unit_refs = list(parent_payload.get("extraction_unit_refs") or [])
    actual_unit_refs = [
        str(unit.get("unit_ref") or "")
        for unit in units
        if isinstance(unit, dict)
    ]
    if (
        not expected_run_id
        or not extraction_unit_refs
        or len(extraction_unit_refs) != len(set(extraction_unit_refs))
        or actual_unit_refs != extraction_unit_refs
    ):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_source_unit_ledger_unit_inventory_mismatch"
        )
    parent_page_refs = {
        str(page.get("page_ref") or "")
        for page in parent_payload["pdf_text_layer_projection"].get(
            "page_inventory"
        )
        or []
        if isinstance(page, Mapping)
    }
    eligible: dict[str, dict[str, Any]] = {}
    owners_by_word: dict[str, list[str]] = {}
    owners_by_cell: dict[str, list[str]] = {}
    for raw_unit in units:
        if not isinstance(raw_unit, dict):
            raise ManagedPdfDocumentV2Error(
                "managed_pdf_v2_source_unit_ledger_unit_invalid"
            )
        layout_coverage = raw_unit.get("pdf_layout_coverage")
        if not isinstance(layout_coverage, Mapping):
            continue
        owned_words = list(layout_coverage.get("owned_word_refs") or [])
        if not owned_words:
            continue
        validation = validate_full_source_unit(
            unit=raw_unit,
            normalization_run_id=expected_run_id,
            document_id=document_id,
            source_checksum_sha256=source_checksum_sha256,
        )
        parent_errors = validate_pdf_source_unit(
            raw_unit,
            parent_payload=parent_payload,
            parent_validation=parent_validation,
            require_parent_payload=True,
        )
        if (
            validation.get("validator_status") != "passed"
            or parent_errors
        ):
            raise ManagedPdfDocumentV2Error(
                "managed_pdf_v2_source_unit_ledger_unit_validation_failed"
            )
        unit_ref = str(raw_unit.get("unit_ref") or "")
        if not unit_ref or unit_ref in eligible:
            raise ManagedPdfDocumentV2Error(
                "managed_pdf_v2_source_unit_ledger_unit_ref_invalid"
            )
        if (
            len(owned_words) != len(set(owned_words))
            or layout_coverage.get("all_selected_refs_accounted") is not True
        ):
            raise ManagedPdfDocumentV2Error(
                "managed_pdf_v2_source_unit_ledger_word_coverage_invalid"
            )
        coverage = raw_unit.get("coverage")
        selected_atoms = (
            list(coverage.get("selected_source_refs") or [])
            if isinstance(coverage, Mapping)
            else []
        )
        if (
            not selected_atoms
            or len(selected_atoms) != len(set(selected_atoms))
            or coverage.get("all_selected_refs_accounted") is not True
        ):
            raise ManagedPdfDocumentV2Error(
                "managed_pdf_v2_source_unit_ledger_atom_coverage_invalid"
            )
        page_refs = list(raw_unit.get("page_refs") or [])
        if (
            len(page_refs) != 1
            or len(page_refs) != len(set(page_refs))
            or not set(page_refs) <= parent_page_refs
        ):
            raise ManagedPdfDocumentV2Error(
                "managed_pdf_v2_source_unit_ledger_page_refs_invalid"
            )
        if not all(
            isinstance(value, str) and value
            for value in (
                raw_unit.get("source_unit_checksum_ref"),
                raw_unit.get("parent_payload_ref"),
                *page_refs,
                *selected_atoms,
                *owned_words,
            )
        ):
            raise ManagedPdfDocumentV2Error(
                "managed_pdf_v2_source_unit_ledger_identity_invalid"
            )
        eligible[unit_ref] = raw_unit
        for word_ref in owned_words:
            owners_by_word.setdefault(str(word_ref), []).append(unit_ref)
        for cell_ref in raw_unit.get("table_cell_refs") or []:
            owners_by_cell.setdefault(str(cell_ref), []).append(unit_ref)

    projection = parent_payload["pdf_text_layer_projection"]
    bbox_by_ref = {
        str(item.get("bbox_ref") or ""): list(item.get("bbox") or [])
        for item in projection.get("bbox_inventory") or []
        if isinstance(item, Mapping)
    }
    source_cells: dict[str, dict[str, Any]] = {}
    for table_candidate in projection.get("table_candidate_inventory") or []:
        if not isinstance(table_candidate, Mapping):
            continue
        candidate_ref = str(table_candidate.get("table_candidate_ref") or "")
        for cell in table_candidate.get("cell_inventory") or []:
            if not isinstance(cell, Mapping):
                continue
            cell_ref = str(cell.get("cell_ref") or "")
            bbox_ref = str(cell.get("bbox_ref") or "")
            if (
                not cell_ref
                or cell_ref in source_cells
                or bbox_ref not in bbox_by_ref
            ):
                raise ManagedPdfDocumentV2Error(
                    "managed_pdf_v2_source_grid_cell_inventory_invalid"
                )
            source_cells[cell_ref] = {
                "cell_ref": cell_ref,
                "table_candidate_ref": candidate_ref,
                "page_ref": str(cell.get("page_ref") or ""),
                "row_ordinal": int(cell.get("row_ordinal") or 0),
                "column_ordinal": int(cell.get("column_ordinal") or 0),
                "row_span": int(cell.get("row_span") or 1),
                "column_span": int(cell.get("column_span") or 1),
                "bbox_ref": bbox_ref,
                "bbox": bbox_by_ref[bbox_ref],
                "word_refs": list(cell.get("word_refs") or []),
            }

    anchor_by_id = {
        str(item.get("anchor_id") or ""): item
        for item in candidate.get("anchors") or []
        if isinstance(item, Mapping)
    }
    document_unit_refs: list[str] = []
    document_atom_refs: list[str] = []
    document_word_refs: list[str] = []
    ledger_tables: list[dict[str, Any]] = []
    for block in candidate.get("blocks") or []:
        if not isinstance(block, dict) or block.get("block_type") != "TABLE":
            continue
        table = block.get("content")
        if not isinstance(table, dict):
            raise ManagedPdfDocumentV2Error(
                "managed_pdf_v2_source_unit_ledger_table_invalid"
            )
        rows = list(table.get("ordered_rows") or [])
        row_ordinal = {
            str(row.get("row_id") or ""): ordinal
            for ordinal, row in enumerate(rows)
            if isinstance(row, Mapping)
        }
        table_atoms: list[str] = []
        table_words: list[str] = []
        table_plan_parts: list[dict[str, Any]] = []
        for part in table.get("source_parts") or []:
            if not isinstance(part, dict):
                raise ManagedPdfDocumentV2Error(
                    "managed_pdf_v2_source_unit_ledger_source_part_invalid"
                )
            first = row_ordinal.get(str(part.get("first_row_id") or ""))
            last = row_ordinal.get(str(part.get("last_row_id") or ""))
            if first is None or last is None or first > last:
                raise ManagedPdfDocumentV2Error(
                    "managed_pdf_v2_source_unit_ledger_row_range_invalid"
                )
            part_words = sorted(
                {
                    str(locator["source_block_ref"])
                    for row in rows[first : last + 1]
                    for entry in row.get("entries") or []
                    for anchor_id in entry.get("source_anchor_ids") or []
                    for anchor in [anchor_by_id.get(str(anchor_id))]
                    for locator in [
                        anchor.get("locator")
                        if isinstance(anchor, Mapping)
                        else None
                    ]
                    if isinstance(locator, Mapping)
                    and locator.get("kind") == "PDF"
                    and locator.get("source_block_ref")
                }
            )
            part_row_ids = {
                str(row.get("row_id") or "")
                for row in rows[first : last + 1]
            }
            part_slot_records = [
                slot
                for slot in table.get("empty_grid_slots") or []
                if isinstance(slot, dict)
                and str(slot.get("row_id") or "") in part_row_ids
            ]
            part_empty_cells = sorted(
                str(slot.get("source_cell_ref") or "")
                for slot in part_slot_records
            )
            if (
                "" in part_empty_cells
                or len(part_empty_cells) != len(set(part_empty_cells))
            ):
                raise ManagedPdfDocumentV2Error(
                    "managed_pdf_v2_source_grid_cell_identity_invalid"
                )
            if not part_words:
                raise ManagedPdfDocumentV2Error(
                    "managed_pdf_v2_source_unit_ledger_part_words_missing"
                )
            owner_refs: set[str] = set()
            for word_ref in part_words:
                owners = owners_by_word.get(word_ref, [])
                if len(owners) != 1:
                    raise ManagedPdfDocumentV2Error(
                        "managed_pdf_v2_source_unit_ledger_word_owner_nonunique"
                    )
                owner_refs.add(owners[0])
            empty_cell_owner: dict[str, str] = {}
            for cell_ref in part_empty_cells:
                owners = owners_by_cell.get(cell_ref, [])
                if len(owners) != 1:
                    raise ManagedPdfDocumentV2Error(
                        "managed_pdf_v2_source_grid_cell_owner_nonunique"
                    )
                source_cell = source_cells.get(cell_ref)
                owner = eligible[owners[0]]
                if (
                    source_cell is None
                    or source_cell["table_candidate_ref"]
                    != owner.get("table_candidate_ref")
                    or source_cell["page_ref"] not in owner.get("page_refs", [])
                    or source_cell["row_span"] != 1
                    or source_cell["column_span"] != 1
                    or source_cell["word_refs"]
                    or len(
                        [
                            slot
                            for slot in part_slot_records
                            if slot.get("source_cell_ref") == cell_ref
                        ]
                    )
                    != 1
                ):
                    raise ManagedPdfDocumentV2Error(
                        "managed_pdf_v2_source_grid_cell_not_proven_empty"
                    )
                empty_cell_owner[cell_ref] = owners[0]
                owner_refs.add(owners[0])
            records: list[dict[str, Any]] = []
            contributed: list[str] = []
            for unit_ref in sorted(owner_refs):
                unit = eligible[unit_ref]
                owned_words = sorted(
                    str(ref)
                    for ref in unit["pdf_layout_coverage"]["owned_word_refs"]
                )
                if not set(owned_words) <= set(part_words):
                    raise ManagedPdfDocumentV2Error(
                        "managed_pdf_v2_source_unit_ledger_partial_unit_forbidden"
                    )
                atoms = sorted(
                    str(ref)
                    for ref in unit["coverage"]["selected_source_refs"]
                )
                record = {
                    "unit_ref": unit_ref,
                    "source_unit_checksum_ref": str(
                        unit["source_unit_checksum_ref"]
                    ),
                    "parent_payload_ref": str(unit["parent_payload_ref"]),
                    "page_refs": sorted(str(ref) for ref in unit["page_refs"]),
                    "selected_source_atom_refs": atoms,
                    "table_contributing_word_refs": owned_words,
                    "empty_grid_slots": [
                        {
                            **copy.deepcopy(source_cells[cell_ref]),
                            "table_cell_inventory_checksum_ref": str(
                                unit["table_cell_inventory_checksum_ref"]
                            ),
                        }
                        for cell_ref in part_empty_cells
                        if empty_cell_owner[cell_ref] == unit_ref
                    ],
                }
                records.append(record)
                contributed.extend(owned_words)
                table_atoms.extend(atoms)
                document_unit_refs.append(unit_ref)
            if sorted(contributed) != part_words:
                raise ManagedPdfDocumentV2Error(
                    "managed_pdf_v2_source_unit_ledger_part_partition_invalid"
                )
            for slot in part_slot_records:
                source_cell = source_cells[str(slot["source_cell_ref"])]
                expected = {
                    "source_cell_ref": source_cell["cell_ref"],
                    "table_candidate_ref": source_cell["table_candidate_ref"],
                    "page_ref": source_cell["page_ref"],
                    "source_row_ordinal": source_cell["row_ordinal"],
                    "source_column_ordinal": source_cell["column_ordinal"],
                    "row_span": source_cell["row_span"],
                    "column_span": source_cell["column_span"],
                    "bbox_ref": source_cell["bbox_ref"],
                    "bbox": source_cell["bbox"],
                    "word_refs": source_cell["word_refs"],
                }
                if any(slot.get(key) != value for key, value in expected.items()):
                    raise ManagedPdfDocumentV2Error(
                        "managed_pdf_v2_source_grid_cell_binding_stale"
                    )
                owner = eligible[empty_cell_owner[str(slot["source_cell_ref"])]]
                if slot.get("page") != part.get("page"):
                    raise ManagedPdfDocumentV2Error(
                        "managed_pdf_v2_source_grid_cell_page_mismatch"
                    )
                slot["table_cell_inventory_checksum_ref"] = str(
                    owner["table_cell_inventory_checksum_ref"]
                )
            part["covered_source_units"] = records
            table_words.extend(part_words)
            table_plan_parts.append(
                {
                    "source_part_id": str(part["source_part_id"]),
                    "covered_source_units": copy.deepcopy(records),
                }
            )
        if len(table_atoms) != len(set(table_atoms)):
            raise ManagedPdfDocumentV2Error(
                "managed_pdf_v2_source_unit_ledger_duplicate_atom_ref"
            )
        if len(table_words) != len(set(table_words)):
            raise ManagedPdfDocumentV2Error(
                "managed_pdf_v2_source_unit_ledger_duplicate_word_ref"
            )
        table["covered_source_atom_refs"] = sorted(table_atoms)
        table["covered_source_word_refs"] = sorted(table_words)
        document_atom_refs.extend(table_atoms)
        document_word_refs.extend(table_words)
        ledger_tables.append(
            {
                "table_id": str(table["table_id"]),
                "covered_source_atom_refs": sorted(table_atoms),
                "covered_source_word_refs": sorted(table_words),
                "source_parts": table_plan_parts,
            }
        )
    if (
        len(document_unit_refs) != len(set(document_unit_refs))
        or len(document_atom_refs) != len(set(document_atom_refs))
        or len(document_word_refs) != len(set(document_word_refs))
    ):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_source_unit_ledger_document_overlap"
        )
    document_coverage = {
        "schema_version": "broker_reports_managed_table_source_unit_coverage_v1",
        "covered_source_unit_refs": sorted(document_unit_refs),
        "covered_source_atom_refs": sorted(document_atom_refs),
        "covered_source_word_refs": sorted(document_word_refs),
        "duplicate_source_unit_refs": [],
        "duplicate_source_atom_refs": [],
        "duplicate_source_word_refs": [],
    }
    candidate["source"]["table_source_unit_coverage"] = document_coverage
    return (
        {
            "scope": "DOCUMENT",
            "coverage": copy.deepcopy(document_coverage),
        },
        *tuple(
            item
            for table in ledger_tables
            for item in (
                {
                    "scope": "TABLE",
                    "table_id": table["table_id"],
                    "covered_source_atom_refs": table[
                        "covered_source_atom_refs"
                    ],
                    "covered_source_word_refs": table[
                        "covered_source_word_refs"
                    ],
                },
                *(
                    {
                        "scope": "SOURCE_PART",
                        "table_id": table["table_id"],
                        "source_part_id": part["source_part_id"],
                        "covered_source_units": part["covered_source_units"],
                    }
                    for part in table["source_parts"]
                ),
            )
        ),
    )


def _sole_complete_pdf_payload(full_source: Any) -> dict[str, Any]:
    payloads = getattr(full_source, "payloads", None)
    if not isinstance(payloads, list) or len(payloads) != 1:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_full_source_payload_count_invalid"
        )
    payload = payloads[0]
    if not isinstance(payload, dict) or payload.get("container_format") != "pdf":
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_full_source_payload_invalid"
        )
    if (
        payload.get("parser_completeness_status") != "complete"
        or payload.get("text_layer_projection_status") != "complete"
        or payload.get("layout_projection_status") != "complete"
    ):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_full_source_projection_incomplete"
        )
    return payload


def _assemble_document(
    *,
    projection: Mapping[str, Any],
    recovered: LogicalRowTableRecoveryResult,
    document_id: str,
    content_size: int,
    source_checksum_sha256: str,
    private_source_ref: str,
    created_at: str,
) -> tuple[dict[str, Any], dict[str, int]]:
    pages = _dict_items(projection.get("page_inventory"))
    words = _dict_items(projection.get("word_inventory"))
    if not pages:
        raise ManagedPdfDocumentV2Error("managed_pdf_v2_pages_missing")
    page_numbers = [int(item.get("page_number") or 0) for item in pages]
    if sorted(page_numbers) != list(range(1, len(pages) + 1)):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_page_order_invalid"
        )
    page_by_ref = _unique_by_id(pages, "page_ref", "page")
    word_by_ref = _unique_by_id(words, "word_ref", "word")
    bbox_by_ref = _unique_by_id(
        _dict_items(projection.get("bbox_inventory")),
        "bbox_ref",
        "bbox",
    )

    recovery_anchors = copy.deepcopy(recovered.anchors)
    recovery_anchor_by_id = _unique_by_id(
        recovery_anchors,
        "anchor_id",
        "recovery_anchor",
    )
    table_word_refs, word_table_id = _table_word_partition(
        recovered=recovered,
        recovery_anchor_by_id=recovery_anchor_by_id,
        word_by_ref=word_by_ref,
    )
    paragraph_word_refs = set(recovered.paragraph_owned_word_refs)
    all_word_refs = set(word_by_ref)
    if set(recovered.unowned_word_refs):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_unowned_source_words"
        )
    if paragraph_word_refs & table_word_refs:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_paragraph_table_word_overlap"
        )
    if paragraph_word_refs | table_word_refs != all_word_refs:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_source_word_partition_invalid"
        )

    tables_by_id = _unique_by_id(
        copy.deepcopy(recovered.tables),
        "table_id",
        "table",
    )
    if set(tables_by_id) != set(word_table_id.values()):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_table_word_owner_missing"
        )
    table_blocks = {
        table_id: _table_block(table)
        for table_id, table in tables_by_id.items()
    }
    word_group, word_line = _word_source_groups(projection, word_by_ref)
    anchors = recovery_anchors
    blocks: list[dict[str, Any]] = []
    emitted_tables: set[str] = set()

    for page_number in sorted(page_numbers):
        page = next(
            item for item in pages if int(item["page_number"]) == page_number
        )
        boundary, boundary_anchor = _page_boundary(
            page,
            source_checksum_sha256=source_checksum_sha256,
            private_source_ref=private_source_ref,
        )
        anchors.append(boundary_anchor)
        blocks.append(boundary)

        current_key: str | None = None
        current_words: list[dict[str, Any]] = []

        def flush_paragraph() -> None:
            nonlocal current_key, current_words
            if not current_words:
                return
            block, anchor = _paragraph_block(
                page_number=page_number,
                source_group=current_key or "ungrouped",
                words=current_words,
                line_by_word_ref=word_line,
                bbox_by_ref=bbox_by_ref,
                source_checksum_sha256=source_checksum_sha256,
                private_source_ref=private_source_ref,
            )
            anchors.append(anchor)
            blocks.append(block)
            current_key = None
            current_words = []

        for word_ref in _ordered_page_word_refs(
            page,
            page_by_ref=page_by_ref,
            word_by_ref=word_by_ref,
        ):
            table_id = word_table_id.get(word_ref)
            if table_id is not None:
                flush_paragraph()
                if table_id not in emitted_tables:
                    blocks.append(table_blocks[table_id])
                    emitted_tables.add(table_id)
                continue
            if word_ref not in paragraph_word_refs:
                raise ManagedPdfDocumentV2Error(
                    "managed_pdf_v2_source_word_not_routable"
                )
            group = word_group[word_ref]
            if current_words and group != current_key:
                flush_paragraph()
            current_key = group
            current_words.append(word_by_ref[word_ref])
        flush_paragraph()

    if emitted_tables != set(tables_by_id):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_table_not_emitted"
        )
    for ordinal, block in enumerate(blocks):
        block["ordinal"] = ordinal

    anchor_by_id = _unique_by_id(anchors, "anchor_id", "anchor")
    del anchor_by_id
    issues = copy.deepcopy(recovered.issues)
    has_partial_table = any(
        table["completeness_status"] != "COMPLETE"
        for table in tables_by_id.values()
    )
    document = {
        "schema_version": "broker_reports_managed_document_v2",
        "document_id": document_id,
        "information_partition": {
            "CONTENT": ["/metadata", "/blocks/*/content"],
            "PROVENANCE": ["/source", "/anchors", "/relations"],
            "CONTROL": [
                "/information_partition",
                "/blocks/*/restoration",
                "/quality",
            ],
            "PRIVATE_SOURCE": [
                "/document_id",
                "/source/artifact",
                "/anchors/*/locator/private_locator",
                "/blocks/*/content/private_artifact",
                "/geometry_evidence",
                "/source_word_ownership",
            ],
        },
        "source": {
            "information_class": "PROVENANCE",
            "format": "PDF",
            "artifact": _private_ref(
                private_source_ref,
                source_checksum_sha256,
            ),
            "checksum_sha256": source_checksum_sha256,
            "mime_type": "application/pdf",
            "size_bytes": content_size,
            "source_part_count": len(pages),
            "normalizer": {
                "name": "FullSourceArtifactFactory",
                "version": str(projection.get("schema_version") or "unknown"),
            },
            "created_at": created_at,
            "source_details": {
                "kind": "PDF",
                "encrypted_status": "NOT_ENCRYPTED",
            },
        },
        "metadata": _unknown_metadata(),
        "anchors": anchors,
        "geometry_evidence": copy.deepcopy(recovered.geometry_evidence),
        "source_word_ownership": copy.deepcopy(
            recovered.source_word_ownership
        ),
        "blocks": blocks,
        "relations": [],
        "quality": {
            "information_class": "CONTROL",
            "status": "PARTIAL" if has_partial_table else "COMPLETE",
            "source_elements_total": len(blocks),
            "preserved_blocks_total": len(blocks),
            "unknown_blocks_total": 0,
            "unsupported_elements_total": 0,
            "known_losses_total": 0,
            "conflicts_total": 0,
            "unaccounted_context_loss_total": 0,
            "blocking_losses_total": 0,
            "issue_ledger": issues,
            "loss_ledger": [],
        },
    }
    return document, {
        "pages_total": len(pages),
        "source_words_total": len(words),
        "logical_tables_total": len(tables_by_id),
        "logical_rows_total": sum(
            len(table["ordered_rows"])
            for table in tables_by_id.values()
        ),
        "paragraph_blocks_total": sum(
            block["block_type"] == "PARAGRAPH" for block in blocks
        ),
        "table_words_total": len(table_word_refs),
        "paragraph_words_total": len(paragraph_word_refs),
    }


def _table_word_partition(
    *,
    recovered: LogicalRowTableRecoveryResult,
    recovery_anchor_by_id: dict[str, dict[str, Any]],
    word_by_ref: dict[str, dict[str, Any]],
) -> tuple[set[str], dict[str, str]]:
    table_word_refs: set[str] = set()
    word_table_id: dict[str, str] = {}
    source_word_ids: set[str] = set()
    for owner in recovered.source_word_ownership:
        source_word_id = str(owner.get("source_word_id") or "")
        if not source_word_id or source_word_id in source_word_ids:
            raise ManagedPdfDocumentV2Error(
                "managed_pdf_v2_source_word_owner_id_invalid"
            )
        source_word_ids.add(source_word_id)
        if owner.get("owner_status") not in {"OWNED", "PROVEN_DUPLICATE"}:
            raise ManagedPdfDocumentV2Error(
                "managed_pdf_v2_unresolved_table_word_owner"
            )
        anchor = recovery_anchor_by_id.get(
            str(owner.get("source_anchor_id") or "")
        )
        locator = anchor.get("locator") if isinstance(anchor, dict) else None
        word_ref = (
            str(locator.get("source_block_ref") or "")
            if isinstance(locator, dict)
            else ""
        )
        if word_ref not in word_by_ref or word_ref in table_word_refs:
            raise ManagedPdfDocumentV2Error(
                "managed_pdf_v2_multiple_or_unknown_table_word_owner"
            )
        table_word_refs.add(word_ref)
        word_table_id[word_ref] = str(owner.get("table_id") or "")
    return table_word_refs, word_table_id


def _table_block(table: dict[str, Any]) -> dict[str, Any]:
    table_id = str(table["table_id"])
    source_anchor_ids = list(
        dict.fromkeys(
            str(part["region_anchor_id"])
            for part in table["source_parts"]
        )
    )
    if not source_anchor_ids:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_table_source_anchor_missing"
        )
    completeness = str(table["completeness_status"])
    if completeness == "BLOCKED":
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_blocked_table_not_sealable"
        )
    return {
        "block_id": logical_table_block_id(table_id),
        "ordinal": 0,
        "block_type": "TABLE",
        "content": table,
        "source_anchor_ids": source_anchor_ids,
        "restoration": {
            "information_class": "CONTROL",
            "status": "RESTORED" if completeness == "COMPLETE" else "PARTIAL",
            "classification_origin": "DETERMINISTIC_DERIVED",
            "issue_ids": list(table["issues"]),
        },
        "issue_ids": list(table["issues"]),
    }


def _page_boundary(
    page: dict[str, Any],
    *,
    source_checksum_sha256: str,
    private_source_ref: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    page_number = int(page["page_number"])
    page_ref = str(page["page_ref"])
    bbox = _page_bbox(page)
    anchor_id = _identifier("anchor_page", [page_ref, page_number])
    checksum = _sha256_json(
        [source_checksum_sha256, page_ref, page_number]
    )
    anchor = _pdf_anchor(
        anchor_id=anchor_id,
        page_number=page_number,
        source_block_ref=page_ref,
        bbox=bbox,
        checksum_sha256=checksum,
        private_source_ref=private_source_ref,
    )
    block = {
        "block_id": _identifier("block_page", [page_ref, page_number]),
        "ordinal": 0,
        "block_type": "BOUNDARY",
        "content": {
            "information_class": "CONTENT",
            "boundary_type": "PAGE",
            "source_part_index": page_number,
            "label": {
                "information_class": "CONTENT",
                "status": "PRESENT",
                "origin": "DETERMINISTIC_DERIVED",
                "value": f"Page {page_number}",
                "candidates": [],
                "evidence_anchor_ids": [anchor_id],
            },
        },
        "source_anchor_ids": [anchor_id],
        "restoration": {
            "information_class": "CONTROL",
            "status": "RESTORED",
            "classification_origin": "DETERMINISTIC_DERIVED",
            "issue_ids": [],
        },
        "issue_ids": [],
    }
    return block, anchor


def _paragraph_block(
    *,
    page_number: int,
    source_group: str,
    words: list[dict[str, Any]],
    line_by_word_ref: Mapping[str, str],
    bbox_by_ref: dict[str, dict[str, Any]],
    source_checksum_sha256: str,
    private_source_ref: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    word_refs = [str(word["word_ref"]) for word in words]
    texts = [str(word.get("text") or "") for word in words]
    if any(not text for text in texts):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_paragraph_word_text_missing"
        )
    physical_lines: list[list[str]] = []
    current_line_ref: str | None = None
    for word, word_text in zip(words, texts, strict=True):
        word_ref = str(word["word_ref"])
        line_ref = line_by_word_ref[word_ref]
        if line_ref != current_line_ref:
            physical_lines.append([])
            current_line_ref = line_ref
        physical_lines[-1].append(word_text)
    text = "\n".join(" ".join(line) for line in physical_lines).strip()
    bboxes = [
        _bbox_value(bbox_by_ref.get(str(word.get("bbox_ref") or "")))
        for word in words
    ]
    bbox = _merge_bboxes(bboxes)
    anchor_id = _identifier(
        "anchor_paragraph",
        [page_number, source_group, *word_refs],
    )
    checksum = _sha256_json(
        [source_checksum_sha256, page_number, word_refs, texts]
    )
    anchor = _pdf_anchor(
        anchor_id=anchor_id,
        page_number=page_number,
        source_block_ref=source_group,
        bbox=bbox,
        checksum_sha256=checksum,
        private_source_ref=private_source_ref,
    )
    block = {
        "block_id": _identifier(
            "block_paragraph",
            [page_number, source_group, *word_refs],
        ),
        "ordinal": 0,
        "block_type": "PARAGRAPH",
        "content": {
            "information_class": "CONTENT",
            "raw_text": text,
            "join_events": [],
        },
        "source_anchor_ids": [anchor_id],
        "restoration": {
            "information_class": "CONTROL",
            "status": "RESTORED",
            "classification_origin": "DETERMINISTIC_DERIVED",
            "issue_ids": [],
        },
        "issue_ids": [],
    }
    return block, anchor


def _pdf_anchor(
    *,
    anchor_id: str,
    page_number: int,
    source_block_ref: str,
    bbox: list[float],
    checksum_sha256: str,
    private_source_ref: str,
) -> dict[str, Any]:
    private_checksum = _sha256_json(
        [page_number, source_block_ref, bbox]
    )
    return {
        "information_class": "PROVENANCE",
        "anchor_id": anchor_id,
        "source_format": "PDF",
        "checksum_sha256": checksum_sha256,
        "locator": {
            "kind": "PDF",
            "source_part_index": page_number,
            "page": page_number,
            "source_block_ref": source_block_ref,
            "bbox": bbox,
            "private_locator": _private_ref(
                f"{private_source_ref}#{anchor_id}",
                private_checksum,
            ),
        },
    }


def _word_source_groups(
    projection: Mapping[str, Any],
    word_by_ref: dict[str, dict[str, Any]],
) -> tuple[dict[str, str], dict[str, str]]:
    line_owner: dict[str, str] = {}
    for line in _dict_items(projection.get("line_inventory")):
        line_ref = str(line.get("line_ref") or "")
        for word_ref in _strings(line.get("word_refs")):
            if word_ref in line_owner:
                raise ManagedPdfDocumentV2Error(
                    "managed_pdf_v2_multiple_line_word_owners"
                )
            line_owner[word_ref] = line_ref
    block_owner: dict[str, str] = {}
    line_to_block: dict[str, str] = {}
    for block in _dict_items(projection.get("block_inventory")):
        block_ref = str(block.get("block_ref") or "")
        for line_ref in _strings(block.get("line_refs")):
            if line_ref in line_to_block:
                raise ManagedPdfDocumentV2Error(
                    "managed_pdf_v2_multiple_block_line_owners"
                )
            line_to_block[line_ref] = block_ref
    for word_ref, line_ref in line_owner.items():
        block_owner[word_ref] = line_to_block.get(line_ref, line_ref)
    groups = {
        word_ref: block_owner.get(word_ref, f"word_group_{word_ref}")
        for word_ref in word_by_ref
    }
    lines = {
        word_ref: line_owner.get(word_ref, f"word_line_{word_ref}")
        for word_ref in word_by_ref
    }
    return groups, lines


def _ordered_page_word_refs(
    page: dict[str, Any],
    *,
    page_by_ref: dict[str, dict[str, Any]],
    word_by_ref: dict[str, dict[str, Any]],
) -> list[str]:
    page_ref = str(page["page_ref"])
    if page_ref not in page_by_ref:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_page_ref_invalid"
        )
    page_words = [
        word
        for word in word_by_ref.values()
        if str(word.get("page_ref") or "") == page_ref
    ]
    ordered = sorted(
        page_words,
        key=lambda word: (
            _integer_order(word.get("geometry_reading_order")),
            _integer_order(word.get("parser_ordinal")),
            str(word["word_ref"]),
        ),
    )
    return [str(word["word_ref"]) for word in ordered]


def _unknown_metadata() -> dict[str, Any]:
    field = {
        "information_class": "CONTENT",
        "status": "UNKNOWN",
        "origin": "UNKNOWN_ORIGIN",
        "value": None,
        "candidates": [],
        "evidence_anchor_ids": [],
    }
    return {
        "document_type": copy.deepcopy(field),
        "title": copy.deepcopy(field),
        "issuer": copy.deepcopy(field),
        "document_date": copy.deepcopy(field),
        "reporting_period": copy.deepcopy(field),
        "owner_or_account": copy.deepcopy(field),
        "language": copy.deepcopy(field),
        "primary_currency": copy.deepcopy(field),
        "additional": [],
    }


def _private_ref(ref: str, checksum: str) -> dict[str, Any]:
    return {
        "information_class": "PRIVATE_SOURCE",
        "status": "PRESENT",
        "ref": ref,
        "checksum_sha256": checksum,
    }


def _page_bbox(page: Mapping[str, Any]) -> list[float]:
    try:
        width = float(page.get("layout_page_width"))
        height = float(page.get("layout_page_height"))
    except (TypeError, ValueError) as exc:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_page_geometry_invalid"
        ) from exc
    if not math.isfinite(width) or not math.isfinite(height):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_page_geometry_invalid"
        )
    if width <= 0 or height <= 0:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_page_geometry_invalid"
        )
    return [0.0, 0.0, width, height]


def _bbox_value(value: dict[str, Any] | None) -> list[float]:
    raw = value.get("bbox") if isinstance(value, dict) else None
    if not isinstance(raw, list) or len(raw) != 4:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_word_bbox_invalid"
        )
    try:
        bbox = [float(item) for item in raw]
    except (TypeError, ValueError) as exc:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_word_bbox_invalid"
        ) from exc
    if any(not math.isfinite(item) for item in bbox):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_word_bbox_invalid"
        )
    if bbox[2] < bbox[0] or bbox[3] < bbox[1]:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_word_bbox_invalid"
        )
    return bbox


def _merge_bboxes(values: Sequence[list[float]]) -> list[float]:
    if not values:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_paragraph_bbox_missing"
        )
    return [
        min(value[0] for value in values),
        min(value[1] for value in values),
        max(value[2] for value in values),
        max(value[3] for value in values),
    ]


def _unique_by_id(
    values: list[dict[str, Any]],
    key: str,
    label: str,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for value in values:
        identifier = str(value.get(key) or "")
        if not identifier or identifier in result:
            raise ManagedPdfDocumentV2Error(
                f"managed_pdf_v2_{label}_id_invalid"
            )
        result[identifier] = value
    return result


def _dict_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_projection_list_invalid"
        )
    return [item for item in value if isinstance(item, dict)]


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None and str(item)]


def _integer_order(value: Any) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_word_order_invalid"
        ) from exc
    if result < 0:
        raise ManagedPdfDocumentV2Error(
            "managed_pdf_v2_word_order_invalid"
        )
    return result


def _identifier(prefix: str, parts: Sequence[Any]) -> str:
    digest = hashlib.sha256(_canonical_bytes(list(parts))).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
