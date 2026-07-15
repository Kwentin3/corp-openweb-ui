from __future__ import annotations

import base64
import copy
import hashlib
import math
import re
from dataclasses import dataclass, field
from typing import Any

from .artifact_lifecycle import lifecycle_for_visibility
from .artifact_models import ArtifactAccessContext, ArtifactRecord, RetentionPolicy
from .artifact_resolver import ArtifactResolver
from .artifact_store import SqliteArtifactStoreAdapter, new_artifact_id
from .file_processing_outcomes import FileProcessingOutcomeFactory
from .pdf_continuation_discovery import PdfContinuationDiscoveryFactory
from .pdf_dual_oracle_contracts import PdfDualOracleContractFactory
from .pdf_hybrid_contracts import sha256_json
from .pdf_parser_geometry import PdfParserGeometryFactory
from .pdf_semantic_header_projection import (
    PdfSemanticHeaderProjectionError,
    PdfSemanticHeaderProjectionFactory,
)
from .pdf_structural_repair_runtime import (
    PdfStructuralRepairRuntimeConfig,
    PdfStructuralRepairRuntimeFactory,
)
from .pdf_table_intake_contracts import PdfTableIntakeContractFactory
from .pdf_table_raster import PdfTableRasterConfig, PdfTableRasterFactory
from .pdf_visual_topology import PdfVisualTopologyFactory
from .pdf_vlm_region_binding import PdfVlmRegionBindingFactory


PDF_STRUCTURAL_REPAIR_SHADOW_SUMMARY_SCHEMA = (
    "broker_reports_pdf_structural_repair_shadow_summary_v1"
)
PDF_STRUCTURAL_REPAIR_TARGET_STATE_SCHEMA = (
    "broker_reports_pdf_structural_repair_target_state_v1"
)
PDF_VLM_GUIDED_CANDIDATE_INTAKE_RESULT_SCHEMA = (
    "broker_reports_pdf_vlm_guided_candidate_intake_result_v1"
)
PDF_VLM_GUIDED_CANDIDATE_INTAKE_SAFE_SUMMARY_SCHEMA = (
    "broker_reports_pdf_vlm_guided_candidate_intake_safe_summary_v1"
)
PDF_VLM_GUIDED_PAGE_INTAKE_RESULT_SCHEMA = (
    "broker_reports_pdf_vlm_guided_page_intake_result_v1"
)
PDF_VLM_GUIDED_PAGE_INTAKE_SAFE_SUMMARY_SCHEMA = (
    "broker_reports_pdf_vlm_guided_page_intake_safe_summary_v1"
)

FACTORY_REQUIRED = (
    "PdfStructuralRepairShadowFactory.create is the only production entrypoint "
    "for structural-repair shadow orchestration; guided intake decisions must "
    "route through PdfTableIntakeContractFactory.create"
)
FORBIDDEN = (
    "Callers must not invoke structural stages or providers directly, retry or "
    "fail over invisibly, expose private target/provider data, mutate the base "
    "normalization, change production Gate 2 selection, or derive technical "
    "processability from morphology metadata"
)

_FACTORY_TOKEN = object()
_SAFE_FILE_REF = re.compile(
    r"^(?:file|doc|brdoc|document|artifact|upload)_[A-Za-z0-9]"
    r"[A-Za-z0-9._:-]{0,119}$"
)
_SAFE_SEMANTIC_REASON = re.compile(r"^pdf_semantic_header_[a-z0-9_]{1,96}$")
_SEMANTIC_REASON_COUNT_LIMIT = 16
_SEMANTIC_REASON_TRUNCATED = "pdf_semantic_header_reason_codes_truncated"


@dataclass(frozen=True)
class PdfStructuralRepairShadowConfig:
    enabled: bool = False
    vlm_guided_intake_enabled: bool = False
    semantic_header_shadow_enabled: bool = False
    maximum_tables: int = 8
    table_allowlist: tuple[str, ...] = ()
    page_allowlist: tuple[str, ...] = ()


@dataclass
class _DocumentProgress:
    document_ref: str
    file_ref: str
    candidates_discovered: int = 0
    targets_selected: int = 0
    targets_accepted: int = 0
    targets_failed: int = 0
    targets_skipped_limit: int = 0
    requires_manual_review_partial: bool = False
    failures: list[tuple[str, str, Any | None]] = field(default_factory=list)


class PdfStructuralRepairShadowError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class _TargetExecutionError(PdfStructuralRepairShadowError):
    def __init__(
        self,
        code: str,
        *,
        private_cause: BaseException,
        target_state_ref: str,
        runtime_result: dict[str, Any] | None = None,
        repeat_history_ref: str | None = None,
    ) -> None:
        self.private_cause = private_cause
        self.target_state_ref = target_state_ref
        self.runtime_result = copy.deepcopy(runtime_result)
        self.repeat_history_ref = repeat_history_ref
        super().__init__(code)


class _UnavailableProviderBoundary:
    """Factory-owned terminal provider used when resolution produced no adapter."""

    def qualify(self) -> dict[str, Any]:
        raise PdfStructuralRepairShadowError(
            "pdf_structural_repair_shadow_provider_unavailable"
        )

    def count_tokens(self, **kwargs: Any) -> dict[str, Any]:
        raise PdfStructuralRepairShadowError(
            "pdf_structural_repair_shadow_provider_unavailable"
        )

    def invoke(self, **kwargs: Any) -> dict[str, Any]:
        raise PdfStructuralRepairShadowError(
            "pdf_structural_repair_shadow_provider_unavailable"
        )


class PdfStructuralRepairShadowFactory:
    def __init__(
        self,
        config: PdfStructuralRepairShadowConfig | None = None,
        *,
        runtime_config: PdfStructuralRepairRuntimeConfig | None = None,
    ) -> None:
        self.config = config or PdfStructuralRepairShadowConfig()
        self.runtime_config = runtime_config

    def create(self, *, provider: Any | None) -> "PdfStructuralRepairShadowRuntime":
        if (
            not isinstance(self.config.enabled, bool)
            or not isinstance(self.config.vlm_guided_intake_enabled, bool)
            or not isinstance(self.config.semantic_header_shadow_enabled, bool)
            or not _positive_integer(self.config.maximum_tables)
            or not isinstance(self.config.table_allowlist, tuple)
            or any(
                not isinstance(item, str) or not item or len(item) > 256
                for item in self.config.table_allowlist
            )
            or len(self.config.table_allowlist)
            != len(set(self.config.table_allowlist))
            or not isinstance(self.config.page_allowlist, tuple)
            or any(
                not isinstance(item, str) or not item or len(item) > 256
                for item in self.config.page_allowlist
            )
            or len(self.config.page_allowlist)
            != len(set(self.config.page_allowlist))
            or (
                self.config.page_allowlist
                and not self.config.vlm_guided_intake_enabled
            )
        ):
            raise PdfStructuralRepairShadowError(
                "pdf_structural_repair_shadow_config_invalid"
            )
        if not self.config.enabled:
            return PdfStructuralRepairShadowRuntime(
                config=self.config,
                continuation_discovery=None,
                contracts=None,
                geometry=None,
                raster=None,
                visual=None,
                vlm_region_binding=None,
                intake_contracts=None,
                structural_runtime=None,
                semantic_projection=None,
                _factory_token=_FACTORY_TOKEN,
            )
        resolved_provider = (
            provider if provider is not None else _UnavailableProviderBoundary()
        )
        structural_runtime = PdfStructuralRepairRuntimeFactory(
            self.runtime_config
        ).create(provider=resolved_provider)
        return PdfStructuralRepairShadowRuntime(
            config=self.config,
            continuation_discovery=(
                PdfContinuationDiscoveryFactory().create()
            ),
            contracts=PdfDualOracleContractFactory().create(),
            geometry=PdfParserGeometryFactory().create(),
            raster=PdfTableRasterFactory(
                PdfTableRasterConfig(padding_points=0.0)
            ).create(),
            visual=PdfVisualTopologyFactory().create(),
            vlm_region_binding=(
                PdfVlmRegionBindingFactory().create()
                if self.config.vlm_guided_intake_enabled
                else None
            ),
            intake_contracts=(
                PdfTableIntakeContractFactory().create()
                if self.config.vlm_guided_intake_enabled
                else None
            ),
            structural_runtime=structural_runtime,
            semantic_projection=(
                PdfSemanticHeaderProjectionFactory().create()
                if self.config.semantic_header_shadow_enabled
                else None
            ),
            _factory_token=_FACTORY_TOKEN,
        )


class PdfStructuralRepairShadowRuntime:
    def __init__(
        self,
        *,
        config: PdfStructuralRepairShadowConfig,
        continuation_discovery: Any | None = None,
        contracts: Any | None,
        geometry: Any | None,
        raster: Any | None,
        visual: Any | None,
        vlm_region_binding: Any | None = None,
        intake_contracts: Any | None = None,
        structural_runtime: Any | None,
        semantic_projection: Any | None = None,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise PdfStructuralRepairShadowError(
                "pdf_structural_repair_shadow_factory_required"
            )
        self.config = config
        self.continuation_discovery = continuation_discovery
        self.contracts = contracts
        self.geometry = geometry
        self.raster = raster
        self.visual = visual
        self.vlm_region_binding = vlm_region_binding
        self.intake_contracts = intake_contracts
        self.structural_runtime = structural_runtime
        self.semantic_projection = semantic_projection
        self.outcomes = FileProcessingOutcomeFactory().create()

    def run(
        self,
        *,
        store: SqliteArtifactStoreAdapter,
        package: dict[str, Any],
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
        pdf_bytes_by_sha256: dict[str, bytes],
    ) -> dict[str, Any]:
        if not self.config.enabled:
            summary = _base_summary(
                enabled=False,
                vlm_guided_intake_enabled=False,
                semantic_header_shadow_enabled=False,
            )
            summary["summary_checksum"] = sha256_json(summary)
            return {
                "enabled": False,
                "artifact_refs": [],
                "private_target_state_refs": [],
                "runtime_result_refs": [],
                "private_diagnostic_refs": [],
                "repeat_history_refs": [],
                "continuation_discovery_refs": [],
                "continuation_result_refs": [],
                "continuation_materialization_refs": [],
                "semantic_projection_refs": [],
                "semantic_diagnostic_refs": [],
                "summary_ref": None,
                "summary": summary,
                "file_processing_outcomes": None,
            }
        if (
            not isinstance(package, dict)
            or not isinstance(pdf_bytes_by_sha256, dict)
            or self.continuation_discovery is None
            or self.structural_runtime is None
            or self.contracts is None
            or self.geometry is None
            or self.raster is None
            or self.visual is None
            or (
                self.config.vlm_guided_intake_enabled
                and self.vlm_region_binding is None
            )
            or (
                self.config.semantic_header_shadow_enabled
                and self.semantic_projection is None
            )
        ):
            raise PdfStructuralRepairShadowError(
                "pdf_structural_repair_shadow_input_invalid"
            )

        refs: list[str] = []
        target_state_refs: list[str] = []
        runtime_refs: list[str] = []
        diagnostic_refs: list[str] = []
        repeat_history_refs: list[str] = []
        continuation_discovery_refs: list[str] = []
        continuation_result_refs: list[str] = []
        continuation_materialization_refs: list[str] = []
        semantic_projection_refs: list[str] = []
        semantic_diagnostic_refs: list[str] = []
        semantic_projection_status_counts: dict[str, int] = {}
        semantic_projection_reason_counts: dict[str, int] = {}
        target_summaries: list[dict[str, Any]] = []
        terminal_counts: dict[str, int] = {}
        completed_fragments_by_table: dict[str, dict[str, Any]] = {}
        documents, descriptors = self._discover(package)

        selected: list[dict[str, Any]] = []
        for descriptor in descriptors:
            progress = documents[descriptor["document_ref"]]
            progress.candidates_discovered += 1
            if (
                descriptor.get("target_scope") != "page_level"
                and self.config.table_allowlist
                and (
                descriptor["table_ref"] not in self.config.table_allowlist
                )
            ):
                continue
            if len(selected) >= self.config.maximum_tables:
                progress.targets_skipped_limit += 1
                continue
            selected.append(descriptor)
            progress.targets_selected += 1

        qualification: dict[str, Any] | None = None
        qualification_error: BaseException | None = None
        if selected:
            try:
                qualification = self.structural_runtime.qualify_provider()
            except Exception as exc:  # provider boundary is intentionally isolated
                qualification_error = exc

        if qualification_error is not None:
            selected_by_document: dict[str, list[dict[str, Any]]] = {}
            for descriptor in selected:
                selected_by_document.setdefault(
                    descriptor["document_ref"], []
                ).append(descriptor)
            for document_ref, current in sorted(selected_by_document.items()):
                progress = documents[document_ref]
                progress.targets_failed += len(current)
                diagnostic = self.outcomes.private_diagnostic(
                    file_ref=progress.file_ref,
                    stage="provider_call",
                    exception=qualification_error,
                    private_context={
                        "operation": "provider_qualification",
                        "targets_blocked": len(current),
                    },
                )
                diagnostic_ref = self._try_put_diagnostic(
                    store=store,
                    context=context,
                    retention_policy=retention_policy,
                    document_id=document_ref,
                    target_id=None,
                    reason_code="provider_temporarily_unavailable",
                    diagnostic=diagnostic.snapshot(),
                )
                if diagnostic_ref:
                    diagnostic_refs.append(diagnostic_ref)
                    refs.append(diagnostic_ref)
                progress.failures.append(
                    (
                        "provider_temporarily_unavailable",
                        "provider_call",
                        diagnostic,
                    )
                )
                for descriptor in current:
                    semantic_status = (
                        "not_projected_structural_terminal"
                        if self.config.semantic_header_shadow_enabled
                        else "disabled"
                    )
                    target_summary = _target_summary(
                        target_id=descriptor["target_id"],
                        terminal_status="provider_not_qualified",
                        reason_code="provider_temporarily_unavailable",
                        count_token_calls=0,
                        generate_calls=0,
                        target_state_persisted=False,
                        runtime_result_persisted=False,
                        repeat_history_persisted=False,
                        repeat_history_ever_conflicted=False,
                        semantic_projection_status=semantic_status,
                        semantic_projection_persisted=False,
                    )
                    target_summaries.append(target_summary)
                    _increment(terminal_counts, "provider_not_qualified")
                    _increment(
                        semantic_projection_status_counts,
                        semantic_status,
                    )
                    _increment_semantic_reasons(
                        semantic_projection_reason_counts,
                        _semantic_reasons_for_status(semantic_status),
                    )
        else:
            assert qualification is not None or not selected
            for descriptor in selected:
                progress = documents[descriptor["document_ref"]]
                try:
                    (
                        result,
                        state_ref,
                        runtime_ref,
                        repeat_history_ref,
                        repeat_history,
                        fragment_context,
                    ) = self._run_target(
                        store=store,
                        package_descriptor=descriptor,
                        qualification=qualification or {},
                        context=context,
                        retention_policy=retention_policy,
                        pdf_bytes_by_sha256=pdf_bytes_by_sha256,
                    )
                    target_state_refs.append(state_ref)
                    runtime_refs.append(runtime_ref)
                    refs.extend((state_ref, runtime_ref))
                    if repeat_history_ref is not None:
                        repeat_history_refs.append(repeat_history_ref)
                        refs.append(repeat_history_ref)
                    safe_runtime = _object(result.get("safe_summary"))
                    terminal = str(
                        result.get("runtime_terminal_status")
                        or "no_valid_consensus"
                    )
                    history_conflicted = (
                        repeat_history.get("ever_conflicted") is True
                    )
                    (
                        semantic_status,
                        semantic_ref,
                        semantic_reasons,
                        semantic_diagnostic_ref,
                    ) = (
                        self._maybe_project_semantic_header(
                            store=store,
                            context=context,
                            retention_policy=retention_policy,
                            document_id=descriptor["document_ref"],
                            target_id=descriptor["target_id"],
                            result=result,
                            history_conflicted=history_conflicted,
                        )
                    )
                    if semantic_ref is not None:
                        semantic_projection_refs.append(semantic_ref)
                        refs.append(semantic_ref)
                    if semantic_diagnostic_ref is not None:
                        semantic_diagnostic_refs.append(
                            semantic_diagnostic_ref
                        )
                        diagnostic_refs.append(semantic_diagnostic_ref)
                        refs.append(semantic_diagnostic_ref)
                    _increment(
                        semantic_projection_status_counts,
                        semantic_status,
                    )
                    _increment_semantic_reasons(
                        semantic_projection_reason_counts,
                        semantic_reasons,
                    )
                    if (
                        terminal
                        in {
                            "accepted_supplied_consensus",
                            "accepted_physical_structure",
                        }
                        and not history_conflicted
                    ):
                        progress.targets_accepted += 1
                        reason_code = None
                        if terminal == "accepted_supplied_consensus":
                            completed_fragments_by_table[
                                descriptor["table_ref"]
                            ] = {
                                **fragment_context,
                                "repeat_history_ever_conflicted": False,
                            }
                    elif terminal in {"no_table_proposed", "proposal_absent"}:
                        # A proved negative detection is a normal terminal,
                        # not a parser/provider failure.
                        reason_code = None
                    else:
                        progress.targets_failed += 1
                        if history_conflicted:
                            reason_code, stage = (
                                "consensus_not_reached",
                                "oracle_consensus",
                            )
                            terminal = "historical_conflict_manual_review"
                            progress.requires_manual_review_partial = True
                        elif terminal == "proposal_ambiguous":
                            reason_code, stage = (
                                "consensus_not_reached",
                                "oracle_consensus",
                            )
                            progress.requires_manual_review_partial = True
                        else:
                            reason_code, stage = _outcome_reason_from_runtime(
                                result
                            )
                        diagnostic = self.outcomes.private_diagnostic(
                            file_ref=progress.file_ref,
                            stage=stage,
                            private_context={
                                "operation": "structural_repair_terminal",
                                "target_id": descriptor["target_id"],
                                "runtime_result_ref": runtime_ref,
                                "runtime_terminal_status": terminal,
                                "repeat_history_ref": repeat_history_ref,
                                "repeat_history_ever_conflicted": (
                                    history_conflicted
                                ),
                                "runtime_reason_codes": copy.deepcopy(
                                    safe_runtime.get("reason_codes") or []
                                ),
                            },
                        )
                        diagnostic_ref = self._try_put_diagnostic(
                            store=store,
                            context=context,
                            retention_policy=retention_policy,
                            document_id=descriptor["document_ref"],
                            target_id=descriptor["target_id"],
                            reason_code=reason_code,
                            diagnostic=diagnostic.snapshot(),
                        )
                        if diagnostic_ref:
                            diagnostic_refs.append(diagnostic_ref)
                            refs.append(diagnostic_ref)
                        progress.failures.append(
                            (reason_code, stage, diagnostic)
                        )
                    target_summaries.append(
                        _target_summary(
                            target_id=descriptor["target_id"],
                            terminal_status=terminal,
                            reason_code=reason_code,
                            count_token_calls=_strict_nonnegative_int(
                                result.get("new_provider_count_token_calls")
                            ),
                            generate_calls=_strict_nonnegative_int(
                                result.get("new_provider_generate_calls")
                            ),
                            target_state_persisted=True,
                            runtime_result_persisted=True,
                            repeat_history_persisted=(
                                repeat_history_ref is not None
                            ),
                            repeat_history_ever_conflicted=history_conflicted,
                            semantic_projection_status=semantic_status,
                            semantic_projection_persisted=(
                                semantic_ref is not None
                            ),
                        )
                    )
                    _increment(terminal_counts, terminal)
                except Exception as exc:
                    progress.targets_failed += 1
                    reason_code, stage = _outcome_reason_from_exception(exc)
                    private_exc = (
                        exc.private_cause
                        if isinstance(exc, _TargetExecutionError)
                        else exc
                    )
                    persisted_state_ref = (
                        exc.target_state_ref
                        if isinstance(exc, _TargetExecutionError)
                        else None
                    )
                    partial_result = (
                        _object(exc.runtime_result)
                        if isinstance(exc, _TargetExecutionError)
                        else {}
                    )
                    if persisted_state_ref:
                        target_state_refs.append(persisted_state_ref)
                        refs.append(persisted_state_ref)
                    persisted_history_ref = (
                        exc.repeat_history_ref
                        if isinstance(exc, _TargetExecutionError)
                        else None
                    )
                    if persisted_history_ref:
                        repeat_history_refs.append(persisted_history_ref)
                        refs.append(persisted_history_ref)
                    if "repeat_history" in str(getattr(exc, "code", "")):
                        progress.requires_manual_review_partial = True
                    diagnostic = self.outcomes.private_diagnostic(
                        file_ref=progress.file_ref,
                        stage=stage,
                        exception=private_exc,
                        private_context={
                            "operation": "structural_repair_target",
                            "target_id": descriptor["target_id"],
                        },
                    )
                    diagnostic_ref = self._try_put_diagnostic(
                        store=store,
                        context=context,
                        retention_policy=retention_policy,
                        document_id=descriptor["document_ref"],
                        target_id=descriptor["target_id"],
                        reason_code=reason_code,
                        diagnostic=diagnostic.snapshot(),
                    )
                    if diagnostic_ref:
                        diagnostic_refs.append(diagnostic_ref)
                        refs.append(diagnostic_ref)
                    progress.failures.append((reason_code, stage, diagnostic))
                    terminal = _safe_exception_terminal(exc)
                    provider_calls_known = not (
                        isinstance(exc, _TargetExecutionError)
                        and exc.code
                        == "pdf_structural_repair_shadow_provider_execution_failed"
                        and not partial_result
                    )
                    semantic_status = (
                        "not_projected_structural_failure"
                        if self.config.semantic_header_shadow_enabled
                        else "disabled"
                    )
                    target_summaries.append(
                        _target_summary(
                            target_id=descriptor["target_id"],
                            terminal_status=terminal,
                            reason_code=reason_code,
                            count_token_calls=(
                                _strict_nonnegative_int(
                                    partial_result.get(
                                        "new_provider_count_token_calls"
                                    )
                                )
                                if provider_calls_known
                                else None
                            ),
                            generate_calls=(
                                _strict_nonnegative_int(
                                    partial_result.get(
                                        "new_provider_generate_calls"
                                    )
                                )
                                if provider_calls_known
                                else None
                            ),
                            target_state_persisted=bool(persisted_state_ref),
                            runtime_result_persisted=False,
                            repeat_history_persisted=bool(
                                persisted_history_ref
                            ),
                            repeat_history_ever_conflicted=False,
                            semantic_projection_status=semantic_status,
                            semantic_projection_persisted=False,
                        )
                    )
                    _increment(terminal_counts, terminal)
                    _increment(
                        semantic_projection_status_counts,
                        semantic_status,
                    )
                    _increment_semantic_reasons(
                        semantic_projection_reason_counts,
                        _semantic_reasons_for_status(semantic_status),
                    )

        continuation_progress = self._run_continuation_groups(
            store=store,
            selected=[
                item
                for item in selected
                if item.get("target_scope") != "page_level"
            ],
            completed_fragments_by_table=completed_fragments_by_table,
            documents=documents,
            context=context,
            retention_policy=retention_policy,
        )
        refs.extend(continuation_progress["artifact_refs"])
        diagnostic_refs.extend(continuation_progress["diagnostic_refs"])
        continuation_discovery_refs.extend(
            continuation_progress["discovery_refs"]
        )
        continuation_result_refs.extend(
            continuation_progress["runtime_refs"]
        )
        continuation_materialization_refs.extend(
            continuation_progress["materialization_refs"]
        )
        semantic_projection_refs.extend(
            continuation_progress["semantic_projection_refs"]
        )
        semantic_diagnostic_refs.extend(
            continuation_progress["semantic_diagnostic_refs"]
        )
        _merge_counts(
            semantic_projection_status_counts,
            continuation_progress["semantic_status_counts"],
        )
        _merge_counts(
            semantic_projection_reason_counts,
            continuation_progress["semantic_reason_counts"],
        )
        file_records = [
            self._file_outcome(progress)
            for _, progress in sorted(documents.items())
        ]
        file_processing_outcomes = (
            self.outcomes.batch(file_records).model_context()
            if file_records
            else None
        )
        summary = _base_summary(
            enabled=True,
            vlm_guided_intake_enabled=(
                self.config.vlm_guided_intake_enabled
            ),
            semantic_header_shadow_enabled=(
                self.config.semantic_header_shadow_enabled
            ),
        )
        summary.update(
            {
                "files_total": len(documents),
                "tables_discovered": sum(
                    item.candidates_discovered for item in documents.values()
                ),
                "tables_selected": sum(
                    item.targets_selected for item in documents.values()
                ),
                "accepted_supplied_consensus_tables": terminal_counts.get(
                    "accepted_supplied_consensus", 0
                ),
                "accepted_physical_structure_tables": terminal_counts.get(
                    "accepted_physical_structure", 0
                ),
                "tables_failed": sum(
                    item.targets_failed for item in documents.values()
                ),
                "tables_skipped_by_limit": sum(
                    item.targets_skipped_limit for item in documents.values()
                ),
                "tables_skipped_by_allowlist": max(
                    0,
                    sum(
                        item.candidates_discovered
                        - item.targets_selected
                        - item.targets_skipped_limit
                        for item in documents.values()
                    ),
                ),
                "terminal_outcomes": dict(sorted(terminal_counts.items())),
                "target_outcomes": sorted(
                    target_summaries,
                    key=lambda item: str(item.get("target_id") or ""),
                ),
                "file_processing_outcomes": copy.deepcopy(
                    file_processing_outcomes
                ),
                "private_target_states_persisted": len(target_state_refs),
                "private_runtime_results_persisted": len(runtime_refs),
                "private_diagnostics_persisted": len(diagnostic_refs),
                "private_repeat_histories_persisted": len(
                    repeat_history_refs
                ),
                "continuation_groups_discovered": continuation_progress[
                    "groups_discovered"
                ],
                "continuation_groups_accepted": continuation_progress[
                    "groups_accepted"
                ],
                "continuation_groups_failed": continuation_progress[
                    "groups_failed"
                ],
                "continuation_descriptors_not_grouped": continuation_progress[
                    "not_grouped_total"
                ],
                "continuation_manual_review_required": continuation_progress[
                    "manual_review_required"
                ],
                "continuation_group_outcomes": copy.deepcopy(
                    continuation_progress["group_outcomes"]
                ),
                "private_continuation_discoveries_persisted": len(
                    continuation_discovery_refs
                ),
                "private_continuation_results_persisted": len(
                    continuation_result_refs
                ),
                "private_continuation_materializations_persisted": len(
                    continuation_materialization_refs
                ),
                "semantic_projection_status_counts": dict(
                    sorted(semantic_projection_status_counts.items())
                ),
                "semantic_projection_reason_counts": dict(
                    sorted(semantic_projection_reason_counts.items())
                ),
                "private_semantic_projections_persisted": len(
                    semantic_projection_refs
                ),
                "private_semantic_diagnostics_persisted": len(
                    semantic_diagnostic_refs
                ),
            }
        )
        summary["summary_checksum"] = sha256_json(summary)
        summary_ref = self._put_record(
            store=store,
            context=context,
            retention_policy=retention_policy,
            document_id=None,
            artifact_type="broker_reports_pdf_structural_repair_shadow_summary_v1",
            visibility="safe_internal",
            storage_backend="project_artifact_store",
            validation_status="validated",
            payload=summary,
            safe_metadata=copy.deepcopy(summary),
        )
        refs.append(summary_ref)
        return {
            "enabled": True,
            "artifact_refs": refs,
            "private_target_state_refs": target_state_refs,
            "runtime_result_refs": runtime_refs,
            "private_diagnostic_refs": diagnostic_refs,
            "repeat_history_refs": repeat_history_refs,
            "continuation_discovery_refs": continuation_discovery_refs,
            "continuation_result_refs": continuation_result_refs,
            "continuation_materialization_refs": (
                continuation_materialization_refs
            ),
            "semantic_projection_refs": semantic_projection_refs,
            "semantic_diagnostic_refs": semantic_diagnostic_refs,
            "summary_ref": summary_ref,
            "summary": summary,
            "file_processing_outcomes": file_processing_outcomes,
        }

    def _maybe_project_semantic_header(
        self,
        *,
        store: SqliteArtifactStoreAdapter,
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
        document_id: str,
        target_id: str,
        result: dict[str, Any],
        history_conflicted: bool,
    ) -> tuple[str, str | None, list[str], str | None]:
        if not self.config.semantic_header_shadow_enabled:
            return "disabled", None, [], None
        if result.get("schema_version") == PDF_VLM_GUIDED_PAGE_INTAKE_RESULT_SCHEMA:
            return (
                "not_projected_structural_terminal",
                None,
                ["pdf_semantic_header_not_projected_structural_terminal"],
                None,
            )
        terminal = str(result.get("runtime_terminal_status") or "")
        if terminal == "ambiguous_multiple_consensus":
            return (
                "not_projected_physical_ambiguity",
                None,
                ["pdf_semantic_header_not_projected_physical_ambiguity"],
                None,
            )
        if history_conflicted:
            return (
                "not_projected_historical_conflict",
                None,
                ["pdf_semantic_header_not_projected_historical_conflict"],
                None,
            )
        if terminal not in {
            "accepted_supplied_consensus",
            "accepted_physical_structure",
        }:
            return (
                "not_projected_structural_terminal",
                None,
                ["pdf_semantic_header_not_projected_structural_terminal"],
                None,
            )
        return self._project_semantic_materialization(
            store=store,
            context=context,
            retention_policy=retention_policy,
            document_id=document_id,
            target_id=target_id,
            structural_result_checksum=str(result.get("result_checksum") or ""),
            materialization=_object(result.get("materialization")),
            projection_scope="fragment",
        )

    def _project_semantic_materialization(
        self,
        *,
        store: SqliteArtifactStoreAdapter,
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
        document_id: str,
        target_id: str,
        structural_result_checksum: str,
        materialization: dict[str, Any],
        projection_scope: str,
    ) -> tuple[str, str | None, list[str], str | None]:
        try:
            if self.semantic_projection is None:
                raise PdfSemanticHeaderProjectionError(
                    "pdf_semantic_header_projection_runtime_missing"
                )
            physical_alternative = _semantic_physical_alternative(
                materialization
            )
            projection = self.semantic_projection.project(
                structural_result_checksum=structural_result_checksum,
                physical_topology_status="accepted_supplied_consensus",
                physical_alternatives=[physical_alternative],
            )
            projected_alternatives = _dicts(
                projection.get("physical_alternatives")
            )
            semantic_fields_total = sum(
                len(_dicts(item.get("semantic_fields")))
                for item in projected_alternatives
            )
            qualifiers_total = sum(
                len(_dicts(item.get("qualifiers")))
                for item in projected_alternatives
            )
            projection_ref = self._put_record(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_id=document_id,
                artifact_type=(
                    "broker_reports_pdf_semantic_header_projection_v1"
                ),
                visibility="private_case",
                storage_backend="project_artifact_payload",
                validation_status="validated",
                payload=projection,
                safe_metadata={
                    "schema_version": projection.get("schema_version"),
                    "target_id": target_id,
                    "projection_scope": projection_scope,
                    "projection_status": projection.get(
                        "projection_status"
                    ),
                    "semantic_equivalence_status": projection.get(
                        "semantic_equivalence_status"
                    ),
                    "physical_topology_status": projection.get(
                        "physical_topology_status"
                    ),
                    "physical_alternatives_total": len(
                        projected_alternatives
                    ),
                    "semantic_fields_total": semantic_fields_total,
                    "qualifiers_total": qualifiers_total,
                    "reason_codes": _safe_semantic_reason_codes(
                        projection.get("reason_codes")
                    ),
                    "configuration_schema_version": _object(
                        projection.get("configuration")
                    ).get("schema_version"),
                    "configuration_checksum": projection.get(
                        "configuration_checksum"
                    ),
                    "projection_checksum": projection.get(
                        "projection_checksum"
                    ),
                    "structural_result_checksum": projection.get(
                        "structural_result_checksum"
                    ),
                    "input_hash": projection.get("input_hash"),
                    "authority_state": "non_authoritative",
                    "production_ready": False,
                    "production_gate2_selection_changed": False,
                },
            )
            return (
                str(projection.get("projection_status") or "incomplete"),
                projection_ref,
                _safe_semantic_reason_codes(projection.get("reason_codes")),
                None,
            )
        except Exception as exc:
            reason_code = (
                exc.code
                if isinstance(exc, PdfSemanticHeaderProjectionError)
                else "pdf_semantic_header_projection_failed"
            )
            safe_reason = _safe_semantic_reason_codes([reason_code])[0]
            diagnostic_ref = self._try_put_semantic_diagnostic(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_id=document_id,
                target_id=target_id,
                projection_scope=projection_scope,
                reason_code=safe_reason,
                exception=exc,
            )
            return "projection_failed", None, [safe_reason], diagnostic_ref

    def _try_put_semantic_diagnostic(
        self,
        *,
        store: SqliteArtifactStoreAdapter,
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
        document_id: str,
        target_id: str,
        projection_scope: str,
        reason_code: str,
        exception: BaseException,
    ) -> str | None:
        payload = {
            "schema_version": (
                "broker_reports_pdf_semantic_header_private_diagnostic_v1"
            ),
            "target_id": target_id,
            "projection_scope": projection_scope,
            "reason_code": reason_code,
            "private_error_type": type(exception).__name__,
            "private_error_message": str(exception),
            "authority_state": "non_authoritative",
            "production_ready": False,
            "production_gate2_selection_changed": False,
        }
        try:
            return self._put_record(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_id=document_id,
                artifact_type=(
                    "broker_reports_pdf_semantic_header_private_diagnostic_v1"
                ),
                visibility="private_case",
                storage_backend="project_artifact_payload",
                validation_status="blocked",
                payload=payload,
                safe_metadata={
                    "schema_version": payload["schema_version"],
                    "target_id": target_id,
                    "projection_scope": projection_scope,
                    "reason_code": reason_code,
                    "authority_state": "non_authoritative",
                    "production_ready": False,
                    "production_gate2_selection_changed": False,
                },
            )
        except Exception:
            return None

    def _run_continuation_groups(
        self,
        *,
        store: SqliteArtifactStoreAdapter,
        selected: list[dict[str, Any]],
        completed_fragments_by_table: dict[str, dict[str, Any]],
        documents: dict[str, _DocumentProgress],
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
    ) -> dict[str, Any]:
        progress = {
            "artifact_refs": [],
            "discovery_refs": [],
            "runtime_refs": [],
            "materialization_refs": [],
            "diagnostic_refs": [],
            "semantic_projection_refs": [],
            "semantic_diagnostic_refs": [],
            "semantic_status_counts": {},
            "semantic_reason_counts": {},
            "groups_discovered": 0,
            "groups_accepted": 0,
            "groups_failed": 0,
            "not_grouped_total": 0,
            "manual_review_required": False,
            "group_outcomes": [],
        }
        if not selected:
            return progress
        pages_by_document: dict[str, set[int]] = {}
        for descriptor in selected:
            pages_by_document.setdefault(
                str(descriptor.get("document_ref") or ""), set()
            ).add(_strict_nonnegative_int(descriptor.get("page_number")))
        if not any(len(pages) >= 2 for pages in pages_by_document.values()):
            return progress
        descriptors = [_continuation_descriptor(item) for item in selected]
        try:
            discovery = self.continuation_discovery.discover(
                descriptors=descriptors
            )
            validation_errors = self.continuation_discovery.validate(discovery)
            if validation_errors:
                raise PdfStructuralRepairShadowError(validation_errors[0])
            discovery_ref = self._put_record(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_id=None,
                artifact_type="broker_reports_pdf_continuation_discovery_v1",
                visibility="private_case",
                storage_backend="project_artifact_payload",
                validation_status="validated",
                payload=discovery,
                safe_metadata={
                    "schema_version": discovery.get("schema_version"),
                    "status": discovery.get("status"),
                    "groups_total": len(
                        _dicts(discovery.get("continuation_groups"))
                    ),
                    "not_grouped_total": len(
                        _dicts(discovery.get("not_grouped"))
                    ),
                    "manual_review_required": discovery.get(
                        "manual_review_required"
                    )
                    is True,
                    "deterministic_geometry_only": True,
                    "text_or_values_used": False,
                    "vlm_used": False,
                    "authority_state": "non_authoritative",
                    "production_ready": False,
                    "production_gate2_selection_changed": False,
                },
            )
            progress["artifact_refs"].append(discovery_ref)
            progress["discovery_refs"].append(discovery_ref)
        except Exception:
            for document_ref in sorted(
                {str(item.get("document_ref") or "") for item in selected}
            ):
                document_progress = documents.get(document_ref)
                if document_progress is not None:
                    _mark_continuation_partial(document_progress)
            progress["groups_failed"] = 1
            progress["manual_review_required"] = True
            semantic_status = (
                "not_projected_structural_failure"
                if self.config.semantic_header_shadow_enabled
                else "disabled"
            )
            semantic_reasons = _semantic_reasons_for_status(semantic_status)
            _increment(progress["semantic_status_counts"], semantic_status)
            _increment_semantic_reasons(
                progress["semantic_reason_counts"], semantic_reasons
            )
            progress["group_outcomes"].append(
                _continuation_group_outcome(
                    continuation_group_id=None,
                    status="partial",
                    fragment_count=0,
                    row_count=None,
                    column_count=None,
                    reason_codes=[
                        "pdf_structural_repair_continuation_discovery_failed"
                    ],
                    semantic_projection_status=semantic_status,
                    semantic_projection_persisted=False,
                    semantic_reason_codes=semantic_reasons,
                )
            )
            return progress

        groups = _dicts(discovery.get("continuation_groups"))
        not_grouped = _dicts(discovery.get("not_grouped"))
        progress["groups_discovered"] = len(groups)
        progress["not_grouped_total"] = len(not_grouped)
        progress["manual_review_required"] = (
            discovery.get("manual_review_required") is True
        )
        for decision in not_grouped:
            if decision.get("manual_review_required") is not True:
                continue
            document_progress = documents.get(
                str(decision.get("document_ref") or "")
            )
            if document_progress is not None:
                _mark_continuation_partial(document_progress)

        for group in groups:
            group_id = str(group.get("continuation_group_id") or "")
            fragment_descriptors = sorted(
                _dicts(group.get("fragments")),
                key=lambda item: int(item.get("fragment_order") or 0),
            )
            fragment_inputs = [
                completed_fragments_by_table.get(
                    str(item.get("table_ref") or "")
                )
                for item in fragment_descriptors
            ]
            document_ref = str(group.get("document_ref") or "")
            document_progress = documents.get(document_ref)
            if (
                len(fragment_descriptors) != 2
                or any(item is None for item in fragment_inputs)
            ):
                progress["groups_failed"] += 1
                semantic_status = (
                    "not_projected_structural_failure"
                    if self.config.semantic_header_shadow_enabled
                    else "disabled"
                )
                semantic_reasons = _semantic_reasons_for_status(
                    semantic_status
                )
                _increment(
                    progress["semantic_status_counts"], semantic_status
                )
                _increment_semantic_reasons(
                    progress["semantic_reason_counts"], semantic_reasons
                )
                if document_progress is not None:
                    _mark_continuation_partial(document_progress)
                progress["group_outcomes"].append(
                    _continuation_group_outcome(
                        continuation_group_id=group_id,
                        status="partial",
                        fragment_count=len(fragment_descriptors),
                        row_count=None,
                        column_count=None,
                        reason_codes=[
                            "pdf_structural_repair_continuation_fragment_unavailable"
                        ],
                        semantic_projection_status=semantic_status,
                        semantic_projection_persisted=False,
                        semantic_reason_codes=semantic_reasons,
                    )
                )
                continue
            try:
                continuation_result = (
                    self.structural_runtime.run_continuation_group(
                        continuation_group_id=group_id,
                        fragments=[
                            copy.deepcopy(item)
                            for item in fragment_inputs
                            if isinstance(item, dict)
                        ],
                    )
                )
                safe = _object(continuation_result.get("safe_summary"))
                terminal = str(
                    continuation_result.get("runtime_terminal_status")
                    or "no_valid_consensus"
                )
                accepted = bool(
                    terminal == "accepted_supplied_consensus"
                    and isinstance(
                        continuation_result.get("materialization"), dict
                    )
                )
                runtime_ref = self._put_record(
                    store=store,
                    context=context,
                    retention_policy=retention_policy,
                    document_id=document_ref,
                    artifact_type=(
                        "broker_reports_pdf_structural_repair_continuation_result_v1"
                    ),
                    visibility="private_case",
                    storage_backend="project_artifact_payload",
                    validation_status="validated" if accepted else "blocked",
                    payload=continuation_result,
                    safe_metadata={
                        "schema_version": continuation_result.get(
                            "schema_version"
                        ),
                        "terminal_status": terminal,
                        "fragment_count": safe.get("fragment_count"),
                        "row_count": safe.get("row_count"),
                        "column_count": safe.get("column_count"),
                        "all_candidates_accounted": safe.get(
                            "all_candidates_accounted"
                        ),
                        "model_invented_values_total": safe.get(
                            "model_invented_values_total"
                        ),
                        "new_provider_count_token_calls": 0,
                        "new_provider_generate_calls": 0,
                        "authority_state": "non_authoritative",
                        "production_ready": False,
                        "production_gate2_selection_changed": False,
                    },
                )
                progress["artifact_refs"].append(runtime_ref)
                progress["runtime_refs"].append(runtime_ref)
                materialization = _object(
                    continuation_result.get("materialization")
                )
                if materialization:
                    materialization_ref = self._put_record(
                        store=store,
                        context=context,
                        retention_policy=retention_policy,
                        document_id=document_ref,
                        artifact_type=(
                            "broker_reports_pdf_continuation_materialization_v1"
                        ),
                        visibility="private_case",
                        storage_backend="project_artifact_payload",
                        validation_status="validated",
                        payload=materialization,
                        safe_metadata={
                            "schema_version": materialization.get(
                                "schema_version"
                            ),
                            "row_count": materialization.get("row_count"),
                            "column_count": materialization.get(
                                "column_count"
                            ),
                            "candidate_ownership_exact": materialization.get(
                                "candidate_ownership_exact"
                            ),
                            "model_invented_values_total": materialization.get(
                                "model_invented_values_total"
                            ),
                            "authority_state": "non_authoritative",
                            "production_ready": False,
                            "production_gate2_selection_changed": False,
                        },
                    )
                    progress["artifact_refs"].append(materialization_ref)
                    progress["materialization_refs"].append(
                        materialization_ref
                    )
                semantic_status = "disabled"
                semantic_ref = None
                semantic_diagnostic_ref = None
                semantic_reasons: list[str] = []
                if self.config.semantic_header_shadow_enabled and accepted:
                    (
                        semantic_status,
                        semantic_ref,
                        semantic_reasons,
                        semantic_diagnostic_ref,
                    ) = self._project_semantic_materialization(
                        store=store,
                        context=context,
                        retention_policy=retention_policy,
                        document_id=document_ref,
                        target_id=group_id,
                        structural_result_checksum=str(
                            continuation_result.get("result_checksum") or ""
                        ),
                        materialization=materialization,
                        projection_scope="joined_continuation",
                    )
                elif self.config.semantic_header_shadow_enabled:
                    semantic_status = "not_projected_structural_terminal"
                    semantic_reasons = [
                        "pdf_semantic_header_not_projected_structural_terminal"
                    ]
                if semantic_ref is not None:
                    progress["artifact_refs"].append(semantic_ref)
                    progress["semantic_projection_refs"].append(semantic_ref)
                if semantic_diagnostic_ref is not None:
                    progress["artifact_refs"].append(
                        semantic_diagnostic_ref
                    )
                    progress["diagnostic_refs"].append(
                        semantic_diagnostic_ref
                    )
                    progress["semantic_diagnostic_refs"].append(
                        semantic_diagnostic_ref
                    )
                _increment(progress["semantic_status_counts"], semantic_status)
                _increment_semantic_reasons(
                    progress["semantic_reason_counts"],
                    semantic_reasons,
                )
                if accepted:
                    progress["groups_accepted"] += 1
                    status = "success"
                else:
                    progress["groups_failed"] += 1
                    status = "partial"
                    if document_progress is not None:
                        _mark_continuation_partial(document_progress)
                progress["group_outcomes"].append(
                    _continuation_group_outcome(
                        continuation_group_id=group_id,
                        status=status,
                        fragment_count=int(safe.get("fragment_count") or 0),
                        row_count=_optional_nonnegative_int(
                            safe.get("row_count")
                        ),
                        column_count=_optional_nonnegative_int(
                            safe.get("column_count")
                        ),
                        reason_codes=[
                            str(item)
                            for item in safe.get("reason_codes") or []
                            if isinstance(item, str) and item
                        ],
                        semantic_projection_status=semantic_status,
                        semantic_projection_persisted=(
                            semantic_ref is not None
                        ),
                        semantic_reason_codes=semantic_reasons,
                    )
                )
            except Exception as exc:
                progress["groups_failed"] += 1
                semantic_status = (
                    "not_projected_structural_failure"
                    if self.config.semantic_header_shadow_enabled
                    else "disabled"
                )
                semantic_reasons = _semantic_reasons_for_status(
                    semantic_status
                )
                _increment(
                    progress["semantic_status_counts"], semantic_status
                )
                _increment_semantic_reasons(
                    progress["semantic_reason_counts"], semantic_reasons
                )
                diagnostic_ref = None
                if document_progress is not None:
                    _mark_continuation_partial(document_progress)
                    diagnostic = self.outcomes.private_diagnostic(
                        file_ref=document_progress.file_ref,
                        stage="oracle_consensus",
                        exception=exc,
                        private_context={
                            "operation": "structural_repair_continuation",
                            "continuation_group_id": group_id,
                        },
                    )
                    diagnostic_ref = self._try_put_diagnostic(
                        store=store,
                        context=context,
                        retention_policy=retention_policy,
                        document_id=document_ref,
                        target_id=group_id,
                        reason_code="consensus_not_reached",
                        diagnostic=diagnostic.snapshot(),
                    )
                if diagnostic_ref:
                    progress["artifact_refs"].append(diagnostic_ref)
                    progress["diagnostic_refs"].append(diagnostic_ref)
                progress["group_outcomes"].append(
                    _continuation_group_outcome(
                        continuation_group_id=group_id,
                        status="partial",
                        fragment_count=len(fragment_descriptors),
                        row_count=None,
                        column_count=None,
                        reason_codes=[
                            "pdf_structural_repair_continuation_execution_failed"
                        ],
                        semantic_projection_status=semantic_status,
                        semantic_projection_persisted=False,
                        semantic_reason_codes=semantic_reasons,
                    )
                )
        return progress

    def _discover(
        self, package: dict[str, Any]
    ) -> tuple[dict[str, _DocumentProgress], list[dict[str, Any]]]:
        inventory = _object(package.get("document_inventory"))
        source_payloads = {
            str(item.get("document_ref") or ""): item
            for item in _dicts(package.get("private_normalized_source_payloads"))
            if item.get("document_ref")
        }
        documents: dict[str, _DocumentProgress] = {}
        descriptors: list[dict[str, Any]] = []
        pdf_documents = sorted(
            (
                item
                for item in _dicts(inventory.get("documents"))
                if item.get("container_format") == "pdf"
            ),
            key=lambda item: str(item.get("document_id") or ""),
        )
        page_ref_owners: dict[str, set[str]] = {}
        for document in pdf_documents:
            owner = str(document.get("document_id") or "")
            owner_projection = _object(
                _object(source_payloads.get(owner)).get(
                    "pdf_text_layer_projection"
                )
            )
            for page in _dicts(owner_projection.get("page_inventory")):
                page_ref = str(page.get("page_ref") or "")
                if owner and page_ref:
                    page_ref_owners.setdefault(page_ref, set()).add(owner)
        for document in pdf_documents:
            document_ref = str(document.get("document_id") or "")
            if not document_ref:
                continue
            progress = _DocumentProgress(
                document_ref=document_ref,
                file_ref=_outcome_file_ref(document_ref),
            )
            documents[document_ref] = progress
            source_payload = _object(source_payloads.get(document_ref))
            projection = _object(
                source_payload.get("pdf_text_layer_projection")
            )
            pages = {
                str(item.get("page_ref") or ""): item
                for item in _dicts(projection.get("page_inventory"))
            }
            bboxes = {
                str(item.get("bbox_ref") or ""): copy.deepcopy(
                    item.get("bbox")
                )
                for item in _dicts(projection.get("bbox_inventory"))
            }
            candidates = sorted(
                _dicts(projection.get("table_candidate_inventory")),
                key=lambda item: (
                    _strict_nonnegative_int(
                        _object(pages.get(str(item.get("page_ref") or ""))).get(
                            "page_number"
                        )
                    ),
                    _strict_nonnegative_int(item.get("parser_ordinal")),
                    str(item.get("table_candidate_ref") or ""),
                ),
            )
            page_candidates: dict[str, list[dict[str, Any]]] = {}
            for candidate in candidates:
                page_candidates.setdefault(
                    str(candidate.get("page_ref") or ""), []
                ).append(candidate)
            pdf_sha256 = str(document.get("sha256") or "")
            page_allowlist = set(self.config.page_allowlist)
            selected_page_refs = (
                {
                    page_ref
                    for page_ref in pages
                    if (
                        f"{document_ref}::{page_ref}" in page_allowlist
                        or (
                            page_ref in page_allowlist
                            and page_ref_owners.get(page_ref)
                            == {document_ref}
                        )
                    )
                }
                if self.config.vlm_guided_intake_enabled
                else set()
            )
            for page_ref in sorted(
                selected_page_refs,
                key=lambda ref: (
                    _strict_nonnegative_int(
                        _object(pages.get(ref)).get("page_number")
                    ),
                    ref,
                ),
            ):
                page = _object(pages.get(page_ref))
                page_number = _strict_nonnegative_int(
                    page.get("page_number")
                )
                identity = {
                    "document_ref": document_ref,
                    "pdf_sha256": pdf_sha256,
                    "page_ref": page_ref,
                    "page_number": page_number,
                    "table_ref": "page_scope_"
                    + hashlib.sha256(
                        f"{document_ref}:{page_ref}:{page_number}".encode(
                            "utf-8"
                        )
                    ).hexdigest()[:24],
                    "candidate_ordinal": 0,
                }
                target_id = "structshadow_" + hashlib.sha256(
                    repr(sorted(identity.items())).encode("utf-8")
                ).hexdigest()[:24]
                descriptors.append(
                    {
                        **identity,
                        "target_id": target_id,
                        "target_scope": "page_level",
                        "table_bbox": [
                            0.0,
                            0.0,
                            page.get("layout_page_width"),
                            page.get("layout_page_height"),
                        ],
                        "page_width": page.get("layout_page_width"),
                        "page_height": page.get("layout_page_height"),
                        "table_strategy_ref": None,
                        "geometry_confidence": None,
                        "rows_total": None,
                        "columns_total": None,
                        "candidate_rank_on_page": 0,
                        "candidates_on_page": len(
                            page_candidates.get(page_ref) or []
                        ),
                        "pdf_text_layer_projection": projection,
                    }
                )
            for ordinal, candidate in enumerate(candidates, start=1):
                table_ref = str(candidate.get("table_candidate_ref") or "")
                page_ref = str(candidate.get("page_ref") or "")
                if page_ref in selected_page_refs:
                    continue
                page = _object(pages.get(page_ref))
                page_number = _strict_nonnegative_int(page.get("page_number"))
                table_bbox = copy.deepcopy(
                    bboxes.get(str(candidate.get("bbox_ref") or ""))
                )
                current_page_candidates = page_candidates.get(page_ref) or []
                candidate_rank_on_page = next(
                    (
                        index
                        for index, current in enumerate(
                            current_page_candidates, start=1
                        )
                        if current is candidate
                    ),
                    0,
                )
                identity = {
                    "document_ref": document_ref,
                    "pdf_sha256": pdf_sha256,
                    "page_ref": page_ref,
                    "page_number": page_number,
                    "table_ref": table_ref,
                    "candidate_ordinal": ordinal,
                }
                target_id = "structshadow_" + hashlib.sha256(
                    repr(sorted(identity.items())).encode("utf-8")
                ).hexdigest()[:24]
                descriptors.append(
                    {
                        **identity,
                        "target_id": target_id,
                        "target_scope": "candidate_crop",
                        "table_bbox": table_bbox,
                        "page_width": page.get("layout_page_width"),
                        "page_height": page.get("layout_page_height"),
                        "table_strategy_ref": candidate.get(
                            "table_strategy_ref"
                        ),
                        "geometry_confidence": candidate.get(
                            "geometry_confidence"
                        ),
                        "rows_total": candidate.get("rows_total"),
                        "columns_total": candidate.get("columns_total"),
                        "candidate_rank_on_page": candidate_rank_on_page,
                        "candidates_on_page": len(current_page_candidates),
                        "pdf_text_layer_projection": projection,
                    }
                )
        descriptors.sort(
            key=lambda item: (
                item["document_ref"],
                item["page_number"],
                item["candidate_ordinal"],
                item["table_ref"],
            )
        )
        return documents, descriptors

    def _run_target(
        self,
        *,
        store: SqliteArtifactStoreAdapter,
        package_descriptor: dict[str, Any],
        qualification: dict[str, Any],
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
        pdf_bytes_by_sha256: dict[str, bytes],
    ) -> tuple[
        dict[str, Any],
        str,
        str,
        str | None,
        dict[str, Any],
        dict[str, Any],
    ]:
        if package_descriptor.get("target_scope") == "page_level":
            return self._run_page_target(
                store=store,
                package_descriptor=package_descriptor,
                qualification=qualification,
                context=context,
                retention_policy=retention_policy,
                pdf_bytes_by_sha256=pdf_bytes_by_sha256,
            )
        document_ref = str(package_descriptor["document_ref"])
        pdf_sha256 = str(package_descriptor["pdf_sha256"])
        page_ref = str(package_descriptor["page_ref"])
        page_number = _strict_nonnegative_int(package_descriptor["page_number"])
        table_ref = str(package_descriptor["table_ref"])
        table_bbox = package_descriptor.get("table_bbox")
        projection = _object(
            package_descriptor.get("pdf_text_layer_projection")
        )
        pdf_bytes = pdf_bytes_by_sha256.get(pdf_sha256)
        if (
            not table_ref
            or not page_ref
            or page_number < 1
            or not isinstance(table_bbox, list)
            or not isinstance(pdf_bytes, bytes)
        ):
            raise PdfStructuralRepairShadowError(
                "pdf_structural_repair_shadow_target_input_invalid"
            )
        parser_observation = self.contracts.build_parser_observation_from_word_atoms(
            document_ref=document_ref,
            pdf_sha256=pdf_sha256,
            page_ref=page_ref,
            page_number=page_number,
            table_ref=table_ref,
            table_bbox=table_bbox,
            pdf_text_layer_projection=projection,
        )
        geometry_observation = self.geometry.build_observation(
            document_ref=document_ref,
            pdf_sha256=pdf_sha256,
            page_ref=page_ref,
            page_number=page_number,
            table_ref=table_ref,
            table_bbox=table_bbox,
            pdf_text_layer_projection=projection,
        )
        guided_intake = self.config.vlm_guided_intake_enabled
        execution_mode = (
            "guided_candidate_crop"
            if guided_intake
            else self.structural_runtime.execution_mode(parser_observation)
        )
        window_plan = (
            self.structural_runtime.plan_windowed_target(parser_observation)
            if not guided_intake and execution_mode == "vertical_atom_windows"
            else None
        )
        rendered = self.raster.render(
            pdf_bytes=pdf_bytes,
            pdf_sha256=pdf_sha256,
            document_ref=document_ref,
            page_number=page_number,
            table_ref=table_ref,
            table_bbox=table_bbox,
            dpi=150,
        )
        png_bytes = base64.b64decode(
            str(rendered.get("private_png_base64") or ""), validate=True
        )
        if not guided_intake and execution_mode == "vertical_atom_windows":
            visual_package = self.structural_runtime.build_windowed_ledger_package(
                parser_observation=parser_observation,
                crop_manifest=_object(rendered.get("manifest")),
            )
        else:
            visual_package = (
                self.visual.build_region_proposal_package(
                    proposal_scope="candidate_crop",
                    parser_observation=parser_observation,
                    crop_manifest=_object(rendered.get("manifest")),
                )
                if guided_intake
                else self.visual.build_package(
                    parser_observation=parser_observation,
                    crop_manifest=_object(rendered.get("manifest")),
                )
            )
        intake_decisions: dict[str, Any] | None = None
        if guided_intake:
            if self.intake_contracts is None:
                raise PdfStructuralRepairShadowError(
                    "pdf_structural_repair_shadow_intake_factory_missing"
                )
            intake_decisions = self._build_guided_intake_decisions(
                package_descriptor=package_descriptor,
                parser_observation=parser_observation,
                rendered=rendered,
                visual_package=visual_package,
                png_bytes=png_bytes,
            )
        private_window_rasters: list[dict[str, Any]] = []
        window_inputs: list[dict[str, Any]] = []
        if window_plan is not None:
            for window in _dicts(window_plan.get("windows")):
                window_rendered = self.raster.render(
                    pdf_bytes=pdf_bytes,
                    pdf_sha256=pdf_sha256,
                    document_ref=document_ref,
                    page_number=page_number,
                    table_ref=table_ref,
                    table_bbox=copy.deepcopy(window["crop_bbox"]),
                    dpi=150,
                )
                window_png_bytes = base64.b64decode(
                    str(window_rendered.get("private_png_base64") or ""),
                    validate=True,
                )
                window_package = self.visual.build_window_package(
                    parser_observation=parser_observation,
                    full_package=visual_package,
                    window_plan=window_plan,
                    window=window,
                    crop_manifest=_object(window_rendered.get("manifest")),
                )
                private_window_rasters.append(
                    {
                        "window_id": window["window_id"],
                        "rendered": window_rendered,
                    }
                )
                window_inputs.append(
                    {
                        "window_id": window["window_id"],
                        "window_package": window_package,
                        "png_bytes": window_png_bytes,
                    }
                )
        repeat_history_scope = (
            {}
            if guided_intake
            else self._repeat_history_scope(
                parser_observation=parser_observation,
                crop_manifest=_object(rendered.get("manifest")),
                execution_mode=execution_mode,
                window_plan=window_plan,
            )
        )
        prior_history, prior_history_ref = (
            ({}, None)
            if guided_intake
            else self._load_repeat_history(
                store=store,
                context=context,
                scope=repeat_history_scope,
            )
        )
        target_state = {
            "schema_version": PDF_STRUCTURAL_REPAIR_TARGET_STATE_SCHEMA,
            "target_id": package_descriptor["target_id"],
            "parser_observation": parser_observation,
            "parser_geometry_observation": geometry_observation,
            "private_raster": rendered,
            "visual_package": visual_package,
            "execution_mode": execution_mode,
            "vlm_guided_intake_enabled": guided_intake,
            "provider_qualification": copy.deepcopy(qualification),
            "repeat_history_scope": repeat_history_scope,
            "prior_repeat_history_ref": prior_history_ref,
            "prior_repeat_history_checksum": _object(prior_history).get(
                "history_checksum"
            ),
            "authority_state": "non_authoritative",
            "production_ready": False,
            "production_gate2_selection_changed": False,
        }
        if intake_decisions is not None:
            target_state["intake_decisions"] = copy.deepcopy(
                intake_decisions
            )
        if window_plan is not None:
            target_state["window_plan"] = copy.deepcopy(window_plan)
            target_state["private_window_rasters"] = copy.deepcopy(
                private_window_rasters
            )
            target_state["window_packages"] = [
                copy.deepcopy(item["window_package"])
                for item in window_inputs
            ]
        state_ref: str | None = None
        if not guided_intake:
            state_ref = self._persist_target_state(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_ref=document_ref,
                target_state=target_state,
                visual_package=visual_package,
                intake_decisions=None,
            )
        if intake_decisions is not None and _object(
            intake_decisions.get("processability")
        ).get("decision") != "processable":
            state_ref = self._persist_target_state(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_ref=document_ref,
                target_state=target_state,
                visual_package=visual_package,
                intake_decisions=intake_decisions,
            )
            intake_error = PdfStructuralRepairShadowError(
                "pdf_structural_repair_shadow_intake_unsupported"
            )
            raise _TargetExecutionError(
                intake_error.code,
                private_cause=intake_error,
                target_state_ref=state_ref,
            )
        candidate_proposal: dict[str, Any] | None = None
        candidate_binding: dict[str, Any] | None = None
        candidate_region_manifests: dict[str, dict[str, Any]] = {}
        try:
            if guided_intake:
                result = self.structural_runtime.run_candidate_once(
                    target_id=package_descriptor["target_id"],
                    parser_observation=parser_observation,
                    parser_geometry_observation=geometry_observation,
                    visual_package=visual_package,
                    png_bytes=png_bytes,
                    provider_qualification=qualification,
                )
                (
                    candidate_proposal,
                    candidate_binding,
                    candidate_region_manifests,
                ) = self._bind_candidate_proposal(
                    package_descriptor=package_descriptor,
                    pdf_bytes=pdf_bytes,
                    pdf_text_layer_projection=projection,
                    parent_bbox=table_bbox,
                    parent_manifest=_object(rendered.get("manifest")),
                    visual_package=visual_package,
                    proposal_result=result,
                )
            elif window_plan is None:
                result = self.structural_runtime.run_target(
                    target_id=package_descriptor["target_id"],
                    parser_observation=parser_observation,
                    parser_geometry_observation=geometry_observation,
                    visual_package=visual_package,
                    png_bytes=png_bytes,
                    provider_qualification=qualification,
                )
            else:
                result = self.structural_runtime.run_windowed_target(
                    target_id=package_descriptor["target_id"],
                    parser_observation=parser_observation,
                    parser_geometry_observation=geometry_observation,
                    visual_package=visual_package,
                    window_plan=window_plan,
                    window_inputs=window_inputs,
                    provider_qualification=qualification,
                )
        except Exception as exc:
            if guided_intake and intake_decisions is not None:
                finalized_intake = self.intake_contracts.finalize_decisions(
                    decisions=intake_decisions,
                    upstream_failure_reason_codes=[
                        "pdf_vlm_guided_intake_runtime_execution_failed"
                    ],
                )
                target_state["intake_decisions"] = copy.deepcopy(
                    finalized_intake
                )
                state_ref = self._persist_target_state(
                    store=store,
                    context=context,
                    retention_policy=retention_policy,
                    document_ref=document_ref,
                    target_state=target_state,
                    visual_package=visual_package,
                    intake_decisions=finalized_intake,
                )
            if state_ref is None:
                raise PdfStructuralRepairShadowError(
                    "pdf_structural_repair_shadow_target_state_missing"
                ) from exc
            raise _TargetExecutionError(
                "pdf_structural_repair_shadow_provider_execution_failed",
                private_cause=exc,
                target_state_ref=state_ref,
            ) from exc
        if guided_intake and intake_decisions is not None:
            (
                actual_counted_tokens,
                upstream_reasons,
                detection_decision,
                detection_reasons,
            ) = (
                _guided_runtime_intake_observations(result)
            )
            finalized_intake = self.intake_contracts.finalize_decisions(
                decisions=intake_decisions,
                actual_counted_input_tokens=actual_counted_tokens,
                upstream_failure_reason_codes=upstream_reasons,
                detection_decision=detection_decision,
                detection_reason_codes=detection_reasons,
            )
            target_state["intake_decisions"] = copy.deepcopy(
                finalized_intake
            )
            state_ref = self._persist_target_state(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_ref=document_ref,
                target_state=target_state,
                visual_package=visual_package,
                intake_decisions=finalized_intake,
            )
            result = self._candidate_intake_result(
                target_id=str(package_descriptor["target_id"]),
                table_ref=table_ref,
                page_ref=page_ref,
                page_number=page_number,
                parent_bbox=table_bbox,
                parent_manifest=_object(rendered.get("manifest")),
                pdf_text_layer_projection=projection,
                visual_package=visual_package,
                proposal_result=result,
                proposal=candidate_proposal,
                binding_result=candidate_binding,
                region_crop_manifests=candidate_region_manifests,
                finalized_intake_decisions=finalized_intake,
            )
        if state_ref is None:
            raise PdfStructuralRepairShadowError(
                "pdf_structural_repair_shadow_target_state_missing"
            )
        terminal = result.get("runtime_terminal_status")
        if (
            not guided_intake
            and self.structural_runtime.validate_result(result)
        ):
            raise PdfStructuralRepairShadowError(
                "pdf_structural_repair_shadow_runtime_result_invalid"
            )
        if terminal == "accepted_supplied_consensus" and (
            result.get("new_provider_count_token_calls")
            != _expected_runtime_calls(result)
            or result.get("new_provider_generate_calls")
            != _expected_runtime_calls(result)
            or _object(result.get("safe_summary")).get("hidden_retry") is not False
            or _object(result.get("safe_summary")).get("provider_failover") is not False
        ):
            raise PdfStructuralRepairShadowError(
                "pdf_structural_repair_shadow_provider_accounting_invalid"
            )
        if terminal == "accepted_physical_structure" and (
            result.get("new_provider_count_token_calls") != 1
            or result.get("new_provider_generate_calls") != 1
            or _object(result.get("safe_summary")).get("hidden_retry") is not False
            or _object(result.get("safe_summary")).get("provider_failover") is not False
        ):
            raise PdfStructuralRepairShadowError(
                "pdf_structural_repair_shadow_provider_accounting_invalid"
            )
        repeat_history: dict[str, Any] = {}
        repeat_history_ref: str | None = None
        if not guided_intake:
            try:
                repeat_history = self._append_repeat_history(
                    prior_history=prior_history,
                    scope=repeat_history_scope,
                    result=result,
                )
                repeat_history_ref = self._put_record(
                    store=store,
                    context=context,
                    retention_policy=retention_policy,
                    document_id=document_ref,
                    artifact_type="broker_reports_pdf_dual_oracle_repeat_history_v1",
                    visibility="private_case",
                    storage_backend="project_artifact_payload",
                    validation_status="validated",
                    payload=repeat_history,
                    safe_metadata={
                        "target_id": package_descriptor["target_id"],
                        "runtime_run_id": result.get("run_id"),
                        "scope_checksum": repeat_history.get("scope_checksum"),
                        "events_total": len(
                            _dicts(repeat_history.get("events"))
                        ),
                        "ever_conflicted": repeat_history.get(
                            "ever_conflicted"
                        ),
                        "authority_state": "non_authoritative",
                        "production_ready": False,
                        "production_gate2_selection_changed": False,
                    },
                )
            except Exception as exc:
                raise _TargetExecutionError(
                    "pdf_structural_repair_shadow_repeat_history_persistence_failed",
                    private_cause=exc,
                    target_state_ref=state_ref,
                    runtime_result=result,
                ) from exc
        try:
            runtime_ref = self._put_record(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_id=document_ref,
                artifact_type=(
                    PDF_VLM_GUIDED_CANDIDATE_INTAKE_RESULT_SCHEMA
                    if guided_intake
                    else "broker_reports_pdf_structural_repair_runtime_result_v1"
                ),
                visibility="private_case",
                storage_backend="project_artifact_payload",
                validation_status=(
                    "validated"
                    if terminal
                    in {
                        "accepted_supplied_consensus",
                        "accepted_physical_structure",
                    }
                    else "blocked"
                ),
                payload=result,
                safe_metadata={
                    **copy.deepcopy(_object(result.get("safe_summary"))),
                    "authority_state": "non_authoritative",
                    "production_ready": False,
                    "production_gate2_selection_changed": False,
                },
            )
        except Exception as exc:
            raise _TargetExecutionError(
                "pdf_structural_repair_shadow_runtime_persistence_failed",
                private_cause=exc,
                target_state_ref=state_ref,
                runtime_result=result,
                repeat_history_ref=repeat_history_ref,
            ) from exc
        return (
            result,
            state_ref,
            runtime_ref,
            repeat_history_ref,
            repeat_history,
            {
                "target_id": package_descriptor["target_id"],
                "parser_observation": parser_observation,
                "visual_package": visual_package,
                "runtime_result": result,
            },
        )

    def _persist_target_state(
        self,
        *,
        store: SqliteArtifactStoreAdapter,
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
        document_ref: str,
        target_state: dict[str, Any],
        visual_package: dict[str, Any],
        intake_decisions: dict[str, Any] | None,
    ) -> str:
        sealed_state = copy.deepcopy(target_state)
        sealed_state.pop("target_state_checksum", None)
        sealed_state["target_state_checksum"] = sha256_json(sealed_state)
        page_state = sealed_state.get("target_scope") == "page_level"
        return self._put_record(
            store=store,
            context=context,
            retention_policy=retention_policy,
            document_id=document_ref,
            artifact_type=PDF_STRUCTURAL_REPAIR_TARGET_STATE_SCHEMA,
            visibility="private_case",
            storage_backend="project_artifact_payload",
            validation_status="validated",
            payload=sealed_state,
            safe_metadata={
                "schema_version": sealed_state["schema_version"],
                "target_id": sealed_state["target_id"],
                **(
                    {
                        "target_scope": "page_level",
                        "full_page_identity_verified": (
                            sealed_state.get("full_page_identity_verified")
                            is True
                        ),
                    }
                    if page_state
                    else {}
                ),
                "candidate_atoms": _object(
                    visual_package.get("component_accounting")
                ).get("atom_count"),
                "dpi": 150,
                "padding_points": 0.0,
                "authority_state": "non_authoritative",
                "production_ready": False,
                "production_gate2_selection_changed": False,
                **(
                    _safe_intake_metadata(intake_decisions)
                    if intake_decisions is not None
                    else {}
                ),
            },
        )

    def _persist_page_upstream_state(
        self,
        *,
        store: SqliteArtifactStoreAdapter,
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
        document_ref: str,
        target_state: dict[str, Any],
        visual_package: dict[str, Any],
        intake_decisions: dict[str, Any],
        reason_code: str,
        actual_counted_input_tokens: int | None = None,
    ) -> str:
        finalized = self.intake_contracts.finalize_decisions(
            decisions=intake_decisions,
            actual_counted_input_tokens=actual_counted_input_tokens,
            upstream_failure_reason_codes=[reason_code],
        )
        target_state["intake_decisions"] = copy.deepcopy(finalized)
        return self._persist_target_state(
            store=store,
            context=context,
            retention_policy=retention_policy,
            document_ref=document_ref,
            target_state=target_state,
            visual_package=visual_package,
            intake_decisions=finalized,
        )

    def _bind_candidate_proposal(
        self,
        *,
        package_descriptor: dict[str, Any],
        pdf_bytes: bytes,
        pdf_text_layer_projection: dict[str, Any],
        parent_bbox: list[float],
        parent_manifest: dict[str, Any],
        visual_package: dict[str, Any],
        proposal_result: dict[str, Any],
    ) -> tuple[
        dict[str, Any] | None,
        dict[str, Any] | None,
        dict[str, dict[str, Any]],
    ]:
        journal = _dicts(proposal_result.get("journal"))
        raw_proposal = (
            _object(journal[0].get("topology_response"))
            if len(journal) == 1
            else {}
        )
        if not raw_proposal:
            return None, None, {}
        try:
            proposal = self.visual.parse_region_proposal_response(
                raw_proposal,
                expected_package_id=str(visual_package.get("package_id") or ""),
                expected_proposal_scope="candidate_crop",
            )
        except ValueError:
            return None, None, {}
        manifests: dict[str, dict[str, Any]] = {}
        if proposal.get("table_presence") == "present":
            for region in _dicts(proposal.get("regions")):
                region_key = str(region.get("region_key") or "")
                source_bbox = _source_bbox_from_normalized(
                    region.get("bbox"),
                    parent_bbox,
                )
                if source_bbox == [float(item) for item in parent_bbox]:
                    manifest = copy.deepcopy(parent_manifest)
                else:
                    rendered = self.raster.render(
                        pdf_bytes=pdf_bytes,
                        pdf_sha256=str(package_descriptor["pdf_sha256"]),
                        document_ref=str(package_descriptor["document_ref"]),
                        page_number=_strict_nonnegative_int(
                            package_descriptor["page_number"]
                        ),
                        table_ref=str(package_descriptor["table_ref"]),
                        table_bbox=source_bbox,
                        dpi=150,
                    )
                    manifest = copy.deepcopy(_object(rendered.get("manifest")))
                manifests[region_key] = manifest
        binding = self.vlm_region_binding.bind(
            proposal_package=visual_package,
            proposal=proposal,
            pdf_text_layer_projection=pdf_text_layer_projection,
            parent_source_bbox=parent_bbox,
            region_crop_manifests=manifests,
        )
        anchor_errors = self.vlm_region_binding.validate_result_against_inputs(
            binding,
            proposal_package=visual_package,
            proposal=proposal,
            pdf_text_layer_projection=pdf_text_layer_projection,
            parent_source_bbox=parent_bbox,
            region_crop_manifests=manifests,
        )
        if anchor_errors:
            raise PdfStructuralRepairShadowError(anchor_errors[0])
        return proposal, binding, manifests

    def _candidate_intake_result(
        self,
        *,
        target_id: str,
        table_ref: str,
        page_ref: str,
        page_number: int,
        parent_bbox: list[float],
        parent_manifest: dict[str, Any],
        pdf_text_layer_projection: dict[str, Any],
        visual_package: dict[str, Any],
        proposal_result: dict[str, Any],
        proposal: dict[str, Any] | None,
        binding_result: dict[str, Any] | None,
        region_crop_manifests: dict[str, dict[str, Any]],
        finalized_intake_decisions: dict[str, Any],
    ) -> dict[str, Any]:
        proposal_safe = _object(proposal_result.get("safe_summary"))
        if binding_result is not None:
            terminal = str(
                binding_result.get("runtime_terminal_status")
                or "validation_blocked"
            )
            reasons = [
                str(item) for item in binding_result.get("reason_codes") or []
            ]
        else:
            terminal = str(
                proposal_result.get("runtime_terminal_status")
                or "validation_blocked"
            )
            reasons = [
                str(item)
                for item in proposal_safe.get("reason_codes") or []
                if isinstance(item, str) and item
            ]
        accepted_regions = [
            item
            for item in _dicts(
                _object(binding_result).get("region_results")
            )
            if item.get("runtime_terminal_status")
            == "accepted_physical_structure"
        ]
        materialization = (
            copy.deepcopy(_object(accepted_regions[0].get("materialization")))
            if terminal == "accepted_physical_structure"
            and len(accepted_regions) == 1
            else None
        )
        safe_summary = {
            "schema_version": (
                PDF_VLM_GUIDED_CANDIDATE_INTAKE_SAFE_SUMMARY_SCHEMA
            ),
            "target_id": target_id,
            "execution_mode": "guided_candidate_crop",
            "runtime_terminal_status": terminal,
            "reason_codes": sorted(set(reasons)),
            "table_presence": _object(proposal).get("table_presence"),
            "regions_proposed": len(
                _dicts(_object(proposal).get("regions"))
            ),
            "regions_accepted": _strict_nonnegative_int(
                _object(_object(binding_result).get("source_accounting")).get(
                    "regions_accepted"
                )
            ),
            "count_token_calls": proposal_result.get(
                "new_provider_count_token_calls"
            ),
            "generate_calls": proposal_result.get(
                "new_provider_generate_calls"
            ),
            "hidden_retry": proposal_safe.get("hidden_retry"),
            "provider_failover": proposal_safe.get("provider_failover"),
            "default_enabled": False,
            "production_authority": False,
        }
        result = {
            "schema_version": PDF_VLM_GUIDED_CANDIDATE_INTAKE_RESULT_SCHEMA,
            "target_id": target_id,
            "proposal_scope": "candidate_crop",
            "candidate_identity": {
                "document_ref": visual_package.get("document_ref"),
                "pdf_sha256": visual_package.get("pdf_sha256"),
                "page_ref": page_ref,
                "page_number": page_number,
                "table_ref": table_ref,
                "parent_source_bbox": copy.deepcopy(parent_bbox),
                "parent_manifest_hash": parent_manifest.get("manifest_hash"),
                "parent_crop_sha256": parent_manifest.get("png_sha256"),
                "projection_checksum": sha256_json(
                    pdf_text_layer_projection
                ),
            },
            "parent_crop_manifest": copy.deepcopy(parent_manifest),
            "visual_package": copy.deepcopy(visual_package),
            "proposal_result": copy.deepcopy(proposal_result),
            "proposal": copy.deepcopy(proposal),
            "binding_result": copy.deepcopy(binding_result),
            "region_crop_manifests": copy.deepcopy(
                region_crop_manifests
            ),
            "finalized_intake_decisions": copy.deepcopy(
                finalized_intake_decisions
            ),
            "materialization": materialization,
            "runtime_terminal_status": terminal,
            "reason_codes": sorted(set(reasons)),
            "new_provider_count_token_calls": proposal_result.get(
                "new_provider_count_token_calls"
            ),
            "new_provider_generate_calls": proposal_result.get(
                "new_provider_generate_calls"
            ),
            "safe_summary": safe_summary,
            "authority_state": "shadow_non_authoritative",
            "default_enabled": False,
            "production_ready": False,
            "production_gate2_selection_changed": False,
        }
        result["result_checksum"] = sha256_json(result)
        errors = self._validate_candidate_intake_result(
            result,
            expected_pdf_text_layer_projection=pdf_text_layer_projection,
            expected_parent_crop_manifest=parent_manifest,
        )
        if errors:
            raise PdfStructuralRepairShadowError(errors[0])
        return result

    def _validate_candidate_intake_result(
        self,
        value: Any,
        *,
        expected_pdf_text_layer_projection: dict[str, Any],
        expected_parent_crop_manifest: dict[str, Any],
    ) -> list[str]:
        expected_keys = {
            "schema_version", "target_id", "proposal_scope",
            "candidate_identity", "parent_crop_manifest", "visual_package",
            "proposal_result", "proposal", "binding_result",
            "region_crop_manifests", "finalized_intake_decisions",
            "materialization", "runtime_terminal_status", "reason_codes",
            "new_provider_count_token_calls", "new_provider_generate_calls",
            "safe_summary", "authority_state", "default_enabled",
            "production_ready", "production_gate2_selection_changed",
            "result_checksum",
        }
        if not isinstance(value, dict) or set(value) != expected_keys:
            return ["pdf_vlm_guided_candidate_intake_result_keys_invalid"]
        data = copy.deepcopy(value)
        errors: list[str] = []
        identity = _object(data.get("candidate_identity"))
        package = _object(data.get("visual_package"))
        proposal_result = _object(data.get("proposal_result"))
        proposal = data.get("proposal")
        binding = data.get("binding_result")
        manifests = _object(data.get("region_crop_manifests"))
        parent_manifest = _object(data.get("parent_crop_manifest"))
        finalized = _object(data.get("finalized_intake_decisions"))
        if (
            data.get("schema_version")
            != PDF_VLM_GUIDED_CANDIDATE_INTAKE_RESULT_SCHEMA
            or data.get("proposal_scope") != "candidate_crop"
            or self.structural_runtime.validate_result(proposal_result)
        ):
            errors.append(
                "pdf_vlm_guided_candidate_intake_proposal_result_invalid"
            )
        journal = _dicts(proposal_result.get("journal"))
        raw_proposal = (
            _object(journal[0].get("topology_response"))
            if len(journal) == 1
            else {}
        )
        parsed: dict[str, Any] | None = None
        if isinstance(proposal, dict):
            try:
                parsed = self.visual.parse_region_proposal_response(
                    proposal,
                    expected_package_id=str(package.get("package_id") or ""),
                    expected_proposal_scope="candidate_crop",
                )
            except ValueError:
                errors.append(
                    "pdf_vlm_guided_candidate_intake_proposal_invalid"
                )
            if parsed != proposal or raw_proposal != proposal:
                errors.append(
                    "pdf_vlm_guided_candidate_intake_proposal_anchor_invalid"
                )
        elif raw_proposal:
            errors.append(
                "pdf_vlm_guided_candidate_intake_proposal_missing"
            )
        if (
            parent_manifest != expected_parent_crop_manifest
            or identity.get("parent_manifest_hash")
            != parent_manifest.get("manifest_hash")
            or identity.get("parent_crop_sha256")
            != parent_manifest.get("png_sha256")
            or identity.get("parent_source_bbox")
            != parent_manifest.get("declared_table_bbox")
            or identity.get("parent_source_bbox")
            != parent_manifest.get("rendered_bbox")
            or identity.get("projection_checksum")
            != sha256_json(expected_pdf_text_layer_projection)
            or identity.get("document_ref") != package.get("document_ref")
            or identity.get("pdf_sha256") != package.get("pdf_sha256")
            or identity.get("page_ref") != package.get("page_ref")
            or identity.get("page_number") != package.get("page_number")
            or identity.get("table_ref") != package.get("table_ref")
        ):
            errors.append(
                "pdf_vlm_guided_candidate_intake_identity_invalid"
            )
        if self.intake_contracts.validate_decisions(finalized):
            errors.append(
                "pdf_vlm_guided_candidate_intake_decisions_invalid"
            )
        if isinstance(binding, dict) and isinstance(parsed, dict):
            anchor_errors = (
                self.vlm_region_binding.validate_result_against_inputs(
                    binding,
                    proposal_package=package,
                    proposal=parsed,
                    pdf_text_layer_projection=(
                        expected_pdf_text_layer_projection
                    ),
                    parent_source_bbox=identity.get(
                        "parent_source_bbox"
                    ),
                    region_crop_manifests=manifests,
                )
            )
            if anchor_errors:
                errors.append(
                    "pdf_vlm_guided_candidate_intake_binding_anchor_invalid"
                )
            expected_terminal = binding.get("runtime_terminal_status")
            expected_reasons = binding.get("reason_codes")
            accepted_regions = [
                item
                for item in _dicts(binding.get("region_results"))
                if item.get("runtime_terminal_status")
                == "accepted_physical_structure"
            ]
            expected_materialization = (
                _object(accepted_regions[0].get("materialization"))
                if expected_terminal == "accepted_physical_structure"
                and len(accepted_regions) == 1
                else None
            )
        else:
            expected_terminal = proposal_result.get(
                "runtime_terminal_status"
            )
            expected_reasons = _object(
                proposal_result.get("safe_summary")
            ).get("reason_codes") or []
            expected_materialization = None
        if (
            data.get("runtime_terminal_status") != expected_terminal
            or data.get("reason_codes") != expected_reasons
            or data.get("materialization") != expected_materialization
            or (
                isinstance(binding, dict)
                and "pdf_vlm_guided_intake_region_reselection_required"
                in data.get("reason_codes", [])
            )
        ):
            errors.append(
                "pdf_vlm_guided_candidate_intake_terminal_invalid"
            )
        proposal_safe = _object(proposal_result.get("safe_summary"))
        safe = _object(data.get("safe_summary"))
        if (
            data.get("new_provider_count_token_calls") != 1
            or data.get("new_provider_generate_calls") not in {0, 1}
            or safe.get("runtime_terminal_status")
            != data.get("runtime_terminal_status")
            or safe.get("reason_codes") != data.get("reason_codes")
            or safe.get("count_token_calls")
            != data.get("new_provider_count_token_calls")
            or safe.get("generate_calls")
            != data.get("new_provider_generate_calls")
            or safe.get("hidden_retry")
            is not proposal_safe.get("hidden_retry")
            or safe.get("provider_failover")
            is not proposal_safe.get("provider_failover")
            or safe.get("default_enabled") is not False
            or safe.get("production_authority") is not False
            or data.get("authority_state") != "shadow_non_authoritative"
            or data.get("default_enabled") is not False
            or data.get("production_ready") is not False
            or data.get("production_gate2_selection_changed") is not False
        ):
            errors.append(
                "pdf_vlm_guided_candidate_intake_authority_invalid"
            )
        unsigned = dict(data)
        stored = unsigned.pop("result_checksum", None)
        if stored != sha256_json(unsigned):
            errors.append(
                "pdf_vlm_guided_candidate_intake_checksum_invalid"
            )
        return sorted(set(errors))

    def _run_page_target(
        self,
        *,
        store: SqliteArtifactStoreAdapter,
        package_descriptor: dict[str, Any],
        qualification: dict[str, Any],
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
        pdf_bytes_by_sha256: dict[str, bytes],
    ) -> tuple[
        dict[str, Any],
        str,
        str,
        None,
        dict[str, Any],
        dict[str, Any],
    ]:
        document_ref = str(package_descriptor.get("document_ref") or "")
        pdf_sha256 = str(package_descriptor.get("pdf_sha256") or "")
        page_ref = str(package_descriptor.get("page_ref") or "")
        page_number = _strict_nonnegative_int(
            package_descriptor.get("page_number")
        )
        target_id = str(package_descriptor.get("target_id") or "")
        projection = _object(
            package_descriptor.get("pdf_text_layer_projection")
        )
        parent_bbox = _page_bbox(package_descriptor)
        pdf_bytes = pdf_bytes_by_sha256.get(pdf_sha256)
        if (
            not document_ref
            or not pdf_sha256
            or not page_ref
            or page_number < 1
            or parent_bbox is None
            or not isinstance(pdf_bytes, bytes)
            or self.vlm_region_binding is None
            or self.intake_contracts is None
        ):
            raise PdfStructuralRepairShadowError(
                "pdf_structural_repair_shadow_page_target_input_invalid"
            )

        rendered = self.raster.render_full_page(
            pdf_bytes=pdf_bytes,
            pdf_sha256=pdf_sha256,
            document_ref=document_ref,
            page_ref=page_ref,
            page_number=page_number,
            expected_page_bbox=parent_bbox,
            dpi=150,
        )
        parent_manifest = _object(rendered.get("manifest"))
        png_bytes = base64.b64decode(
            str(rendered.get("private_png_base64") or ""), validate=True
        )
        visual_package = self.visual.build_region_proposal_package(
            proposal_scope="page_level",
            crop_manifest=parent_manifest,
        )
        verified_word_bbox_records, exact_word_projection = _page_word_bboxes(
            projection=projection,
            page_ref=page_ref,
            parent_bbox=parent_bbox,
        )
        projection_checksum = sha256_json(projection)
        page_evidence = _page_evidence(
            visual_package=visual_package,
            projection_checksum=projection_checksum,
            verified_word_bbox_records=verified_word_bbox_records,
        )
        full_page_identity_verified = _full_page_manifest_identity_verified(
            parent_manifest=parent_manifest,
            visual_package=visual_package,
            page_ref=page_ref,
            page_number=page_number,
            parent_bbox=parent_bbox,
            expected_png_sha256=hashlib.sha256(png_bytes).hexdigest(),
        )
        intake_decisions = self.intake_contracts.build_decisions(
            document_ref=document_ref,
            pdf_sha256=pdf_sha256,
            page_ref=page_ref,
            page_number=page_number,
            scope_ref=target_id,
            table_ref=None,
            evidence_checksum=str(page_evidence.get("evidence_checksum") or ""),
            assessor_stage="guided_page_preflight",
            scope="page",
            detection_decision="plausible",
            holdout_decision="not_evaluated",
            page_bbox=parent_bbox,
            candidate_bbox=None,
            # Page proposals intentionally expose zero text atoms to the
            # provider.  The source word coordinates are verified above and
            # consumed only by the provider-free region binder after a
            # proposal exists.
            coordinate_bboxes=[
                copy.deepcopy(_object(record).get("bbox"))
                for record in verified_word_bbox_records
            ],
            provenance_verified=exact_word_projection,
            crop_identity_verified=full_page_identity_verified,
            exact_ownership_verified=exact_word_projection,
            atom_count=0,
            model_json_bytes=_strict_nonnegative_int(
                _object(visual_package.get("component_accounting")).get(
                    "model_json_bytes"
                )
            ),
            counted_input_tokens=None,
            image_count=1,
            crop_count=0,
            pdf_count=0,
            image_bytes=len(png_bytes),
            metadata={
                "routing": {
                    "source": "explicit_page_ref_allowlist",
                    "candidate_count_on_page": _strict_nonnegative_int(
                        package_descriptor.get("candidates_on_page")
                    ),
                }
            },
        )
        target_state = {
            "schema_version": PDF_STRUCTURAL_REPAIR_TARGET_STATE_SCHEMA,
            "target_id": target_id,
            "target_scope": "page_level",
            "parser_observation": None,
            "parser_geometry_observation": None,
            "private_raster": rendered,
            "visual_package": visual_package,
            "page_evidence": copy.deepcopy(page_evidence),
            "full_page_identity_verified": full_page_identity_verified,
            "execution_mode": "guided_page_level",
            "vlm_guided_intake_enabled": True,
            "intake_decisions": copy.deepcopy(intake_decisions),
            "provider_qualification": copy.deepcopy(qualification),
            "repeat_history_scope": {},
            "prior_repeat_history_ref": None,
            "prior_repeat_history_checksum": None,
            "authority_state": "non_authoritative",
            "production_ready": False,
            "production_gate2_selection_changed": False,
        }
        state_ref: str | None = None
        if _object(intake_decisions.get("processability")).get(
            "decision"
        ) != "processable":
            state_ref = self._persist_target_state(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_ref=document_ref,
                target_state=target_state,
                visual_package=visual_package,
                intake_decisions=intake_decisions,
            )
            intake_error = PdfStructuralRepairShadowError(
                "pdf_structural_repair_shadow_intake_unsupported"
            )
            raise _TargetExecutionError(
                intake_error.code,
                private_cause=intake_error,
                target_state_ref=state_ref,
            )

        try:
            proposal_result = self.structural_runtime.run_page_proposal_once(
                target_id=target_id,
                visual_package=visual_package,
                png_bytes=png_bytes,
                provider_qualification=qualification,
            )
        except Exception as exc:
            state_ref = self._persist_page_upstream_state(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_ref=document_ref,
                target_state=target_state,
                visual_package=visual_package,
                intake_decisions=intake_decisions,
                reason_code="pdf_vlm_guided_page_runtime_execution_failed",
            )
            raise _TargetExecutionError(
                "pdf_structural_repair_shadow_provider_execution_failed",
                private_cause=exc,
                target_state_ref=state_ref,
            ) from exc
        if self.structural_runtime.validate_result(proposal_result):
            runtime_error = PdfStructuralRepairShadowError(
                "pdf_structural_repair_shadow_runtime_result_invalid"
            )
            state_ref = self._persist_page_upstream_state(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_ref=document_ref,
                target_state=target_state,
                visual_package=visual_package,
                intake_decisions=intake_decisions,
                reason_code="pdf_vlm_guided_page_runtime_result_invalid",
            )
            raise _TargetExecutionError(
                runtime_error.code,
                private_cause=runtime_error,
                target_state_ref=state_ref,
            )

        proposal_journal = _dicts(proposal_result.get("journal"))
        counted_tokens = _object(
            proposal_journal[0].get("count_tokens")
            if proposal_journal
            else None
        ).get("total_tokens")
        actual_counted_tokens = (
            counted_tokens
            if isinstance(counted_tokens, int)
            and not isinstance(counted_tokens, bool)
            and counted_tokens >= 0
            else None
        )

        proposal = _object(proposal_result.get("proposal"))
        region_crop_manifests: dict[str, dict[str, Any]] = {}
        binding_result: dict[str, Any] | None = None
        proposal_is_unambiguous = bool(
            proposal_result.get("runtime_terminal_status")
            == "proposal_persisted"
            and proposal.get("alternatives_complete") is True
            and not proposal.get("uncertainty_codes")
            and proposal.get("table_presence") in {"present", "absent"}
        )
        try:
            if proposal_is_unambiguous:
                if proposal.get("table_presence") == "present":
                    for region in _dicts(proposal.get("regions")):
                        region_key = str(region.get("region_key") or "")
                        source_bbox = _source_bbox_from_normalized(
                            region.get("bbox"), parent_bbox
                        )
                        region_rendered = self.raster.render(
                            pdf_bytes=pdf_bytes,
                            pdf_sha256=pdf_sha256,
                            document_ref=document_ref,
                            page_number=page_number,
                            table_ref="vlm_region_"
                            + hashlib.sha256(
                                f"{target_id}:{region_key}".encode("utf-8")
                            ).hexdigest()[:24],
                            table_bbox=source_bbox,
                            dpi=150,
                        )
                        region_crop_manifests[region_key] = copy.deepcopy(
                            _object(region_rendered.get("manifest"))
                        )
                binding_result = self.vlm_region_binding.bind(
                    proposal_package=visual_package,
                    proposal=proposal,
                    pdf_text_layer_projection=projection,
                    parent_source_bbox=parent_bbox,
                    region_crop_manifests=region_crop_manifests,
                )
        except Exception as exc:
            state_ref = self._persist_page_upstream_state(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_ref=document_ref,
                target_state=target_state,
                visual_package=visual_package,
                intake_decisions=intake_decisions,
                reason_code="pdf_vlm_guided_page_binding_execution_failed",
                actual_counted_input_tokens=actual_counted_tokens,
            )
            raise _TargetExecutionError(
                "pdf_structural_repair_shadow_page_binding_failed",
                private_cause=exc,
                target_state_ref=state_ref,
            ) from exc
        upstream_reasons = (
            [
                str(item)
                for item in _object(
                    proposal_result.get("safe_summary")
                ).get("reason_codes")
                or []
            ]
            if proposal_result.get("runtime_terminal_status")
            != "proposal_persisted"
            else None
        )
        detection_decision, detection_reasons = (
            _detection_from_table_presence(
                proposal_result.get("table_presence")
            )
        )
        finalized_intake_decisions = self.intake_contracts.finalize_decisions(
            decisions=intake_decisions,
            actual_counted_input_tokens=actual_counted_tokens,
            upstream_failure_reason_codes=upstream_reasons,
            detection_decision=detection_decision,
            detection_reason_codes=detection_reasons,
        )
        target_state["intake_decisions"] = copy.deepcopy(
            finalized_intake_decisions
        )
        state_ref = self._persist_target_state(
            store=store,
            context=context,
            retention_policy=retention_policy,
            document_ref=document_ref,
            target_state=target_state,
            visual_package=visual_package,
            intake_decisions=finalized_intake_decisions,
        )

        result = self._page_intake_result(
            target_id=target_id,
            page_ref=page_ref,
            page_number=page_number,
            parent_bbox=parent_bbox,
            parent_manifest=parent_manifest,
            pdf_text_layer_projection=projection,
            page_evidence=page_evidence,
            visual_package=visual_package,
            proposal_result=proposal_result,
            binding_result=binding_result,
            region_crop_manifests=region_crop_manifests,
            finalized_intake_decisions=finalized_intake_decisions,
        )
        runtime_ref = self._put_record(
            store=store,
            context=context,
            retention_policy=retention_policy,
            document_id=document_ref,
            artifact_type=PDF_VLM_GUIDED_PAGE_INTAKE_RESULT_SCHEMA,
            visibility="private_case",
            storage_backend="project_artifact_payload",
            validation_status=(
                "validated"
                if result.get("runtime_terminal_status")
                in {"accepted_physical_structure", "no_table_proposed"}
                else "blocked"
            ),
            payload=result,
            safe_metadata={
                **copy.deepcopy(_object(result.get("safe_summary"))),
                "authority_state": "non_authoritative",
                "production_ready": False,
                "production_gate2_selection_changed": False,
            },
        )
        return (
            result,
            state_ref,
            runtime_ref,
            None,
            {},
            {
                "target_id": target_id,
                "parser_observation": None,
                "visual_package": visual_package,
                "runtime_result": result,
            },
        )

    def _page_intake_result(
        self,
        *,
        target_id: str,
        page_ref: str,
        page_number: int,
        parent_bbox: list[float],
        parent_manifest: dict[str, Any],
        pdf_text_layer_projection: dict[str, Any],
        page_evidence: dict[str, Any],
        visual_package: dict[str, Any],
        proposal_result: dict[str, Any],
        binding_result: dict[str, Any] | None,
        region_crop_manifests: dict[str, dict[str, Any]],
        finalized_intake_decisions: dict[str, Any],
    ) -> dict[str, Any]:
        projection_checksum = sha256_json(pdf_text_layer_projection)
        full_page_identity_verified = _full_page_manifest_identity_verified(
            parent_manifest=parent_manifest,
            visual_package=visual_package,
            page_ref=page_ref,
            page_number=page_number,
            parent_bbox=parent_bbox,
            expected_png_sha256=str(parent_manifest.get("png_sha256") or ""),
        )
        proposal = _object(proposal_result.get("proposal"))
        proposal_terminal = str(
            proposal_result.get("runtime_terminal_status") or ""
        )
        if binding_result is not None:
            terminal = str(
                binding_result.get("runtime_terminal_status")
                or "validation_blocked"
            )
            reasons = [str(item) for item in binding_result.get("reason_codes") or []]
        elif proposal_terminal == "proposal_persisted":
            terminal = "proposal_ambiguous"
            reasons = ["pdf_vlm_guided_page_proposal_ambiguous"]
        else:
            terminal = "proposal_blocked"
            reasons = [
                str(item)
                for item in _object(proposal_result.get("safe_summary")).get(
                    "reason_codes"
                )
                or []
            ]
            if not reasons:
                reasons = ["pdf_vlm_guided_page_proposal_blocked"]
        regions_proposed = len(_dicts(proposal.get("regions")))
        regions_accepted = (
            _strict_nonnegative_int(
                _object(binding_result.get("source_accounting")).get(
                    "regions_accepted"
                )
            )
            if binding_result is not None
            else 0
        )
        proposal_safe = _object(proposal_result.get("safe_summary"))
        safe_summary = {
            "schema_version": PDF_VLM_GUIDED_PAGE_INTAKE_SAFE_SUMMARY_SCHEMA,
            "target_id": target_id,
            "execution_mode": "guided_page_level",
            "runtime_terminal_status": terminal,
            "reason_codes": sorted(set(reasons)),
            "table_presence": proposal_result.get("table_presence"),
            "regions_proposed": regions_proposed,
            "regions_accepted": regions_accepted,
            "count_token_calls": proposal_result.get(
                "new_provider_count_token_calls"
            ),
            "generate_calls": proposal_result.get(
                "new_provider_generate_calls"
            ),
            "hidden_retry": proposal_safe.get("hidden_retry"),
            "provider_failover": proposal_safe.get("provider_failover"),
            "full_page_identity_verified": full_page_identity_verified,
            "default_enabled": False,
            "production_authority": False,
        }
        result = {
            "schema_version": PDF_VLM_GUIDED_PAGE_INTAKE_RESULT_SCHEMA,
            "target_id": target_id,
            "proposal_scope": "page_level",
            "page_identity": {
                "document_ref": visual_package.get("document_ref"),
                "pdf_sha256": visual_package.get("pdf_sha256"),
                "page_ref": page_ref,
                "page_number": page_number,
                "parent_source_bbox": copy.deepcopy(parent_bbox),
                "parent_manifest_hash": parent_manifest.get("manifest_hash"),
                "parent_crop_sha256": parent_manifest.get("png_sha256"),
                "projection_checksum": projection_checksum,
                "full_page_identity_verified": full_page_identity_verified,
            },
            "parent_manifest": copy.deepcopy(parent_manifest),
            "page_evidence": copy.deepcopy(page_evidence),
            "visual_package": copy.deepcopy(visual_package),
            "proposal_result": copy.deepcopy(proposal_result),
            "binding_result": copy.deepcopy(binding_result),
            "region_crop_manifests": copy.deepcopy(region_crop_manifests),
            "finalized_intake_decisions": copy.deepcopy(
                finalized_intake_decisions
            ),
            "runtime_terminal_status": terminal,
            "reason_codes": sorted(set(reasons)),
            "new_provider_count_token_calls": proposal_result.get(
                "new_provider_count_token_calls"
            ),
            "new_provider_generate_calls": proposal_result.get(
                "new_provider_generate_calls"
            ),
            "safe_summary": safe_summary,
            "authority_state": "shadow_non_authoritative",
            "default_enabled": False,
            "production_ready": False,
            "production_gate2_selection_changed": False,
        }
        result["result_checksum"] = sha256_json(result)
        errors = self._validate_page_intake_result(
            result,
            expected_pdf_text_layer_projection=pdf_text_layer_projection,
            expected_parent_manifest=parent_manifest,
        )
        if errors:
            raise PdfStructuralRepairShadowError(errors[0])
        return result

    def _validate_page_intake_result(
        self,
        value: Any,
        *,
        expected_pdf_text_layer_projection: dict[str, Any] | None = None,
        expected_parent_manifest: dict[str, Any] | None = None,
    ) -> list[str]:
        data = _object(value)
        expected_keys = {
            "schema_version", "target_id", "proposal_scope", "page_identity",
            "parent_manifest", "page_evidence", "visual_package",
            "proposal_result", "binding_result",
            "region_crop_manifests", "finalized_intake_decisions",
            "runtime_terminal_status", "reason_codes",
            "new_provider_count_token_calls", "new_provider_generate_calls",
            "safe_summary", "authority_state", "default_enabled",
            "production_ready", "production_gate2_selection_changed",
            "result_checksum",
        }
        if set(data) != expected_keys:
            return ["pdf_vlm_guided_page_intake_result_keys_invalid"]
        errors: list[str] = []
        package = _object(data.get("visual_package"))
        proposal_result = _object(data.get("proposal_result"))
        binding = data.get("binding_result")
        manifests = _object(data.get("region_crop_manifests"))
        identity = _object(data.get("page_identity"))
        parent_manifest = _object(data.get("parent_manifest"))
        page_evidence = _object(data.get("page_evidence"))
        safe = _object(data.get("safe_summary"))
        finalized_intake = _object(data.get("finalized_intake_decisions"))
        if (
            expected_parent_manifest is not None
            and parent_manifest != expected_parent_manifest
        ):
            errors.append(
                "pdf_vlm_guided_page_intake_parent_manifest_anchor_invalid"
            )
        if (
            data.get("schema_version") != PDF_VLM_GUIDED_PAGE_INTAKE_RESULT_SCHEMA
            or data.get("proposal_scope") != "page_level"
            or self.visual.validate_region_proposal_package(package)
            or self.structural_runtime.validate_result(proposal_result)
        ):
            errors.append("pdf_vlm_guided_page_intake_contract_invalid")
        if self.intake_contracts.validate_decisions(finalized_intake):
            errors.append("pdf_vlm_guided_page_intake_decisions_invalid")
        if (
            data.get("target_id") != proposal_result.get("target_id")
            or proposal_result.get("package_id") != package.get("package_id")
            or proposal_result.get("package_hash") != package.get("package_hash")
        ):
            errors.append("pdf_vlm_guided_page_intake_proposal_binding_invalid")
        if binding is not None:
            if (
                not isinstance(binding, dict)
                or self.vlm_region_binding.validate_result(binding)
                or set(manifests)
                != {
                    str(item.get("region_key") or "")
                    for item in _dicts(
                        _object(proposal_result.get("proposal")).get("regions")
                    )
                }
            ):
                errors.append("pdf_vlm_guided_page_intake_binding_invalid")
            else:
                proposal = _object(proposal_result.get("proposal"))
                if (
                    expected_pdf_text_layer_projection is not None
                    and self.vlm_region_binding.validate_result_against_inputs(
                        binding,
                        proposal_package=package,
                        proposal=proposal,
                        pdf_text_layer_projection=(
                            expected_pdf_text_layer_projection
                        ),
                        parent_source_bbox=_object(
                            data.get("page_identity")
                        ).get("parent_source_bbox"),
                        region_crop_manifests=manifests,
                    )
                ):
                    errors.append(
                        "pdf_vlm_guided_page_intake_binding_anchor_invalid"
                    )
                if (
                    binding.get("proposal_package_id")
                    != package.get("package_id")
                    or binding.get("proposal_package_hash")
                    != package.get("package_hash")
                    or binding.get("proposal_checksum")
                    != sha256_json(proposal)
                    or binding.get("proposal_scope") != "page_level"
                    or binding.get("document_ref")
                    != identity.get("document_ref")
                    or binding.get("pdf_sha256") != identity.get("pdf_sha256")
                    or binding.get("page_ref") != identity.get("page_ref")
                    or binding.get("page_number") != identity.get("page_number")
                    or binding.get("parent_source_bbox")
                    != identity.get("parent_source_bbox")
                    or binding.get("projection_checksum")
                    != identity.get("projection_checksum")
                    or binding.get("table_presence")
                    != proposal.get("table_presence")
                    or binding.get("alternatives_complete")
                    is not proposal.get("alternatives_complete")
                ):
                    errors.append(
                        "pdf_vlm_guided_page_intake_binding_identity_invalid"
                    )
                for region_result in _dicts(binding.get("region_results")):
                    region_key = str(region_result.get("region_key") or "")
                    manifest = _object(manifests.get(region_key))
                    if (
                        region_result.get("crop_manifest_hash")
                        != manifest.get("manifest_hash")
                        or region_result.get("crop_sha256")
                        != manifest.get("png_sha256")
                        or region_result.get("source_bbox")
                        != manifest.get("declared_table_bbox")
                        or region_result.get("source_bbox")
                        != manifest.get("rendered_bbox")
                        or region_result.get("table_ref")
                        != manifest.get("table_ref")
                        or manifest.get("document_ref")
                        != identity.get("document_ref")
                        or manifest.get("pdf_sha256")
                        != identity.get("pdf_sha256")
                        or manifest.get("page_number")
                        != identity.get("page_number")
                        or manifest.get("padding_points") != 0.0
                    ):
                        errors.append(
                            "pdf_vlm_guided_page_intake_region_crop_binding_invalid"
                        )
        elif manifests:
            errors.append("pdf_vlm_guided_page_intake_orphan_crop_invalid")
        manifest_identity_verified = _full_page_manifest_identity_verified(
            parent_manifest=parent_manifest,
            visual_package=package,
            page_ref=str(identity.get("page_ref") or ""),
            page_number=_strict_nonnegative_int(identity.get("page_number")),
            parent_bbox=identity.get("parent_source_bbox"),
            expected_png_sha256=str(identity.get("parent_crop_sha256") or ""),
        )
        if (
            set(identity)
            != {
                "document_ref", "pdf_sha256", "page_ref", "page_number",
                "parent_source_bbox", "parent_manifest_hash",
                "parent_crop_sha256", "projection_checksum",
                "full_page_identity_verified",
            }
            or identity.get("document_ref") != package.get("document_ref")
            or identity.get("pdf_sha256") != package.get("pdf_sha256")
            or identity.get("page_ref") != package.get("page_ref")
            or identity.get("page_number") != package.get("page_number")
            or identity.get("parent_source_bbox")
            != _object(package.get("crop_identity")).get("declared_table_bbox")
            or identity.get("parent_manifest_hash")
            != _object(package.get("crop_identity")).get("manifest_hash")
            or identity.get("parent_manifest_hash")
            != parent_manifest.get("manifest_hash")
            or identity.get("parent_crop_sha256")
            != _object(package.get("crop_identity")).get("crop_sha256")
            or identity.get("parent_crop_sha256")
            != parent_manifest.get("png_sha256")
            or not isinstance(identity.get("projection_checksum"), str)
            or re.fullmatch(
                r"[0-9a-f]{64}", identity.get("projection_checksum") or ""
            )
            is None
            or (
                expected_pdf_text_layer_projection is not None
                and identity.get("projection_checksum")
                != sha256_json(expected_pdf_text_layer_projection)
            )
            or identity.get("full_page_identity_verified")
            is not manifest_identity_verified
            or not manifest_identity_verified
        ):
            errors.append("pdf_vlm_guided_page_intake_page_identity_invalid")
        evidence_records = page_evidence.get("verified_word_bbox_records")
        expected_evidence_records: list[dict[str, Any]] | None = None
        expected_records_verified = False
        if expected_pdf_text_layer_projection is not None:
            expected_evidence_records, expected_records_verified = (
                _page_word_bboxes(
                    projection=expected_pdf_text_layer_projection,
                    page_ref=str(identity.get("page_ref") or ""),
                    parent_bbox=identity.get("parent_source_bbox"),
                )
            )
        evidence_material = {
            "visual_package": package,
            "projection_checksum": page_evidence.get("projection_checksum"),
            "verified_word_bbox_records": evidence_records,
        }
        evidence_records_structurally_valid = _word_bbox_records_valid(
            evidence_records,
            parent_bbox=identity.get("parent_source_bbox"),
        )
        evidence_records_anchor_verified = bool(
            evidence_records_structurally_valid
            and (
                expected_pdf_text_layer_projection is None
                or (
                    expected_records_verified
                    and evidence_records == expected_evidence_records
                )
            )
        )
        if (
            set(page_evidence)
            != {
                "visual_package_hash",
                "projection_checksum",
                "verified_word_bbox_records",
                "evidence_checksum",
            }
            or page_evidence.get("visual_package_hash")
            != package.get("package_hash")
            or page_evidence.get("projection_checksum")
            != identity.get("projection_checksum")
            or not evidence_records_anchor_verified
            or page_evidence.get("evidence_checksum")
            != sha256_json(evidence_material)
        ):
            errors.append("pdf_vlm_guided_page_intake_page_evidence_invalid")
        intake_facts = _object(finalized_intake.get("technical_facts"))
        intake_binding = _object(
            _object(finalized_intake.get("processability")).get(
                "evidence_binding"
            )
        )
        journal = _dicts(proposal_result.get("journal"))
        counted_tokens = _object(
            journal[0].get("count_tokens") if journal else None
        ).get("total_tokens")
        expected_counted_tokens = (
            counted_tokens
            if isinstance(counted_tokens, int)
            and not isinstance(counted_tokens, bool)
            and counted_tokens >= 0
            else None
        )
        if (
            intake_binding.get("document_ref") != identity.get("document_ref")
            or intake_binding.get("pdf_sha256") != identity.get("pdf_sha256")
            or intake_binding.get("page_ref") != identity.get("page_ref")
            or intake_binding.get("page_number") != identity.get("page_number")
            or intake_binding.get("scope_ref") != data.get("target_id")
            or intake_binding.get("table_ref") is not None
            or intake_binding.get("evidence_checksum")
            != page_evidence.get("evidence_checksum")
            or intake_binding.get("assessor_stage") != "guided_page_preflight"
            or intake_facts.get("scope") != "page"
            or intake_facts.get("page_bbox")
            != identity.get("parent_source_bbox")
            or intake_facts.get("coordinate_bboxes_total")
            != len(evidence_records if isinstance(evidence_records, list) else [])
            or intake_facts.get("atom_count") != 0
            or intake_facts.get("provenance_verified")
            is not evidence_records_anchor_verified
            or intake_facts.get("exact_ownership_verified")
            is not evidence_records_anchor_verified
            or intake_facts.get("crop_identity_verified")
            is not manifest_identity_verified
            or intake_facts.get("counted_input_tokens")
            != expected_counted_tokens
        ):
            errors.append("pdf_vlm_guided_page_intake_evidence_binding_invalid")
        upstream_reasons = intake_facts.get("upstream_failure_reason_codes")
        expected_detection = {
            "present": "plausible",
            "absent": "implausible",
            "uncertain": "uncertain",
        }.get(proposal_result.get("table_presence"))
        actual_detection = _object(finalized_intake.get("detection")).get(
            "decision"
        )
        if upstream_reasons:
            if actual_detection != "absent_due_to_upstream_failure":
                errors.append(
                    "pdf_vlm_guided_page_intake_detection_binding_invalid"
                )
        elif expected_detection is not None and actual_detection != expected_detection:
            errors.append("pdf_vlm_guided_page_intake_detection_binding_invalid")
        expected_safe_keys = {
            "schema_version", "target_id", "execution_mode",
            "runtime_terminal_status", "reason_codes", "table_presence",
            "regions_proposed", "regions_accepted", "count_token_calls",
            "generate_calls", "hidden_retry", "provider_failover",
            "full_page_identity_verified", "default_enabled",
            "production_authority",
        }
        proposal = _object(proposal_result.get("proposal"))
        if isinstance(binding, dict):
            expected_terminal = binding.get("runtime_terminal_status")
            expected_reasons = binding.get("reason_codes")
            expected_regions_accepted = _object(
                binding.get("source_accounting")
            ).get("regions_accepted")
        elif proposal_result.get("runtime_terminal_status") == "proposal_persisted":
            expected_terminal = "proposal_ambiguous"
            expected_reasons = ["pdf_vlm_guided_page_proposal_ambiguous"]
            expected_regions_accepted = 0
        else:
            expected_terminal = "proposal_blocked"
            expected_reasons = _object(
                proposal_result.get("safe_summary")
            ).get("reason_codes") or ["pdf_vlm_guided_page_proposal_blocked"]
            expected_regions_accepted = 0
        if (
            set(safe) != expected_safe_keys
            or safe.get("schema_version")
            != PDF_VLM_GUIDED_PAGE_INTAKE_SAFE_SUMMARY_SCHEMA
            or safe.get("target_id") != data.get("target_id")
            or safe.get("runtime_terminal_status")
            != data.get("runtime_terminal_status")
            or safe.get("reason_codes") != data.get("reason_codes")
            or safe.get("count_token_calls")
            != data.get("new_provider_count_token_calls")
            or safe.get("generate_calls")
            != data.get("new_provider_generate_calls")
            or safe.get("table_presence")
            != proposal_result.get("table_presence")
            or safe.get("regions_proposed")
            != len(_dicts(proposal.get("regions")))
            or safe.get("regions_accepted") != expected_regions_accepted
            or safe.get("hidden_retry") is not False
            or safe.get("provider_failover") is not False
            or safe.get("full_page_identity_verified")
            is not manifest_identity_verified
            or not manifest_identity_verified
            or safe.get("default_enabled") is not False
            or safe.get("production_authority") is not False
        ):
            errors.append("pdf_vlm_guided_page_intake_safe_summary_invalid")
        if (
            data.get("new_provider_count_token_calls") != 1
            or data.get("new_provider_generate_calls") not in {0, 1}
            or data.get("new_provider_count_token_calls")
            != proposal_result.get("new_provider_count_token_calls")
            or data.get("new_provider_generate_calls")
            != proposal_result.get("new_provider_generate_calls")
            or data.get("runtime_terminal_status") != expected_terminal
            or data.get("reason_codes") != expected_reasons
            or data.get("authority_state") != "shadow_non_authoritative"
            or data.get("default_enabled") is not False
            or data.get("production_ready") is not False
            or data.get("production_gate2_selection_changed") is not False
        ):
            errors.append("pdf_vlm_guided_page_intake_authority_invalid")
        unsigned = dict(data)
        stored = unsigned.pop("result_checksum", None)
        if stored != sha256_json(unsigned):
            errors.append("pdf_vlm_guided_page_intake_checksum_invalid")
        return sorted(set(errors))

    def _build_guided_intake_decisions(
        self,
        *,
        package_descriptor: dict[str, Any],
        parser_observation: dict[str, Any],
        rendered: dict[str, Any],
        visual_package: dict[str, Any],
        png_bytes: bytes,
    ) -> dict[str, Any]:
        candidates = _dicts(parser_observation.get("candidates"))
        coordinate_bboxes = [
            copy.deepcopy(candidate.get("bbox"))
            for candidate in candidates
        ]
        construction = _object(
            parser_observation.get("candidate_construction")
        )
        accounting = _object(visual_package.get("component_accounting"))
        crop_identity = _object(visual_package.get("crop_identity"))
        crop_manifest = _object(rendered.get("manifest"))
        neutral_map = _object(
            visual_package.get("neutral_atom_to_candidate_id")
        )
        candidate_ids = [
            str(candidate.get("candidate_id") or "")
            for candidate in candidates
        ]
        provenance_verified = not self.contracts.validate_parser_observation(
            parser_observation
        )
        crop_identity_verified = bool(
            crop_identity.get("crop_sha256")
            and crop_identity.get("crop_sha256")
            == crop_manifest.get("png_sha256")
            and crop_identity.get("manifest_hash")
            == crop_manifest.get("manifest_hash")
            and crop_identity.get("declared_table_bbox")
            == crop_manifest.get("declared_table_bbox")
            and crop_identity.get("rendered_bbox")
            == crop_manifest.get("rendered_bbox")
            and crop_identity.get("png_bytes") == len(png_bytes)
        )
        exact_ownership_verified = bool(
            construction.get("kind") == "raw_word_atoms"
            and construction.get("semantic_grid_dependency") is False
            and construction.get("word_atoms_exactly_once") is True
            and accounting.get("atom_count") == len(candidates)
            and len(neutral_map) == len(candidates)
            and set(neutral_map.values()) == set(candidate_ids)
            and len(candidate_ids) == len(set(candidate_ids))
            and all(candidate_ids)
        )
        return self.intake_contracts.build_decisions(
            document_ref=str(package_descriptor.get("document_ref") or ""),
            pdf_sha256=str(package_descriptor.get("pdf_sha256") or ""),
            page_ref=str(package_descriptor.get("page_ref") or ""),
            page_number=_strict_nonnegative_int(
                package_descriptor.get("page_number")
            ),
            scope_ref=str(package_descriptor.get("target_id") or ""),
            table_ref=str(package_descriptor.get("table_ref") or ""),
            evidence_checksum=str(visual_package.get("package_hash") or ""),
            assessor_stage="guided_intake_preflight",
            scope="candidate_crop",
            detection_decision="plausible",
            holdout_decision="not_evaluated",
            page_bbox=_page_bbox(package_descriptor),
            candidate_bbox=copy.deepcopy(
                package_descriptor.get("table_bbox")
            ),
            coordinate_bboxes=coordinate_bboxes,
            provenance_verified=provenance_verified,
            crop_identity_verified=crop_identity_verified,
            exact_ownership_verified=exact_ownership_verified,
            atom_count=_strict_nonnegative_int(
                accounting.get("atom_count")
            ),
            model_json_bytes=_strict_nonnegative_int(
                accounting.get("model_json_bytes")
            ),
            counted_input_tokens=None,
            image_count=1,
            crop_count=1,
            pdf_count=0,
            image_bytes=len(png_bytes),
            metadata=_intake_morphology_metadata(package_descriptor),
        )

    def _repeat_history_scope(
        self,
        *,
        parser_observation: dict[str, Any],
        crop_manifest: dict[str, Any],
        execution_mode: str,
        window_plan: dict[str, Any] | None,
    ) -> dict[str, Any]:
        runtime_config = self.structural_runtime.config
        provider_config_hash = sha256_json(
            {
                "provider_profile": runtime_config.provider_profile,
                "provider_name": runtime_config.provider_name,
                "model_id": runtime_config.model_id,
                "maximum_counted_input_tokens": (
                    runtime_config.maximum_counted_input_tokens
                ),
                "maximum_output_tokens": runtime_config.maximum_output_tokens,
            }
        )
        return {
            "parser_observation_checksum": str(
                parser_observation.get("observation_checksum") or ""
            ),
            "provider": str(runtime_config.provider_name),
            "model": str(runtime_config.model_id),
            "configuration_hash": provider_config_hash,
            "crop_manifest_hash": str(
                crop_manifest.get("manifest_hash") or ""
            ),
            "solver_version": str(
                self.structural_runtime.solver.config.policy_version
            ),
            "runtime_policy_version": str(runtime_config.policy_version),
            "execution_mode": execution_mode,
            "window_policy_version": (
                str(self.structural_runtime.windowing.config.policy_version)
                if window_plan is not None
                else "not_applicable"
            ),
            "window_plan_hash": (
                str(window_plan.get("plan_hash") or "")
                if window_plan is not None
                else "not_applicable"
            ),
        }

    def _load_repeat_history(
        self,
        *,
        store: SqliteArtifactStoreAdapter,
        context: ArtifactAccessContext,
        scope: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str | None]:
        if not context.case_id:
            return None, None
        scope_checksum = sha256_json(
            {key: scope[key] for key in sorted(scope)}
        )
        candidates = [
            record
            for record in store.list_by_case(context.case_id)
            if record.artifact_type
            == "broker_reports_pdf_dual_oracle_repeat_history_v1"
            and record.user_id == context.user_id
            and record.workspace_model_id == context.workspace_model_id
            and _object(record.safe_metadata).get("scope_checksum")
            == scope_checksum
        ]
        if not candidates:
            return None, None
        latest = candidates[-1]
        try:
            historical_context = ArtifactAccessContext(
                user_id=context.user_id,
                normalization_run_id=latest.normalization_run_id,
                case_id=context.case_id,
                chat_id=context.chat_id,
                workspace_model_id=context.workspace_model_id,
                allow_private=True,
            )
            payload = ArtifactResolver(store).resolve(
                latest.artifact_id,
                historical_context,
            )["payload"]
        except Exception as exc:
            raise PdfStructuralRepairShadowError(
                "pdf_structural_repair_shadow_repeat_history_invalid"
            ) from exc
        errors = self.contracts.validate_repeat_history(payload)
        if errors or _object(payload).get("scope") != {
            key: scope[key] for key in sorted(scope)
        }:
            raise PdfStructuralRepairShadowError(
                "pdf_structural_repair_shadow_repeat_history_invalid"
            )
        return copy.deepcopy(payload), latest.artifact_id

    def _append_repeat_history(
        self,
        *,
        prior_history: dict[str, Any] | None,
        scope: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        history = (
            self.contracts.create_repeat_history(scope=scope)
            if prior_history is None
            else copy.deepcopy(prior_history)
        )
        validation_errors = self.contracts.validate_repeat_history(history)
        if validation_errors:
            raise PdfStructuralRepairShadowError(
                "pdf_structural_repair_shadow_repeat_history_invalid"
            )
        repeat_attempts = {
            str(item.get("attempt_id") or ""): item
            for item in _dicts(
                _object(result.get("repeatability")).get("attempt_history")
            )
        }
        journals = [
            item
            for item in _dicts(result.get("journal"))
            if item.get("provider_generate_call_performed") is True
            and _object(item.get("provider_attempt")).get("attempt_id")
            and isinstance(item.get("assembly"), dict)
        ]
        run_id = str(result.get("run_id") or "")
        if not run_id:
            raise PdfStructuralRepairShadowError(
                "pdf_structural_repair_shadow_repeat_history_runtime_invalid"
            )
        for journal in journals:
            provider_attempt = _object(journal.get("provider_attempt"))
            source_attempt_id = str(
                journal.get("composite_attempt_id")
                or provider_attempt.get("attempt_id")
                or ""
            )
            repeat_attempt = _object(repeat_attempts.get(source_attempt_id))
            valid_checksums = [
                str(item)
                for item in repeat_attempt.get(
                    "valid_canonical_grid_checksums"
                )
                or []
                if isinstance(item, str) and item
            ]
            terminal_status = (
                "accepted_supplied_consensus"
                if len(valid_checksums) == 1
                else "ambiguous_multiple_consensus"
                if len(valid_checksums) > 1
                else "no_valid_consensus"
            )
            next_sequence = len(_dicts(history.get("events"))) + 1
            durable_attempt_id = (
                f"{run_id}:{source_attempt_id}:s{next_sequence}"
            )
            history = self.contracts.append_repeat_history_event(
                history=history,
                attempt_id=durable_attempt_id,
                attempt_number=next_sequence,
                evidence_revision=str(
                    journal.get("evidence_revision") or ""
                ),
                canonical_grid_checksum=(
                    valid_checksums[0] if len(valid_checksums) == 1 else None
                ),
                topology_checksum=str(
                    repeat_attempt.get("alternative_set_checksum") or ""
                )
                or None,
                terminal_status=terminal_status,
                expected_prior_history_checksum=str(
                    history.get("history_checksum") or ""
                ),
            )
        if (
            result.get("runtime_terminal_status")
            == "accepted_supplied_consensus"
            and len(journals) != 2
        ):
            raise PdfStructuralRepairShadowError(
                "pdf_structural_repair_shadow_repeat_history_attempts_invalid"
            )
        errors = self.contracts.validate_repeat_history(history)
        if errors:
            raise PdfStructuralRepairShadowError(
                "pdf_structural_repair_shadow_repeat_history_invalid"
            )
        if (
            prior_history is not None
            and prior_history.get("ever_conflicted") is True
            and history.get("ever_conflicted") is not True
        ):
            raise PdfStructuralRepairShadowError(
                "pdf_structural_repair_shadow_repeat_history_conflict_erased"
            )
        return history

    def _file_outcome(self, progress: _DocumentProgress) -> Any:
        if progress.targets_skipped_limit and not progress.failures:
            return self.outcomes.partial(
                file_ref=progress.file_ref,
                stage="processing",
                reason_code="partial_result_available",
            )
        if not progress.failures:
            return self.outcomes.success(file_ref=progress.file_ref)
        reason_code, stage, diagnostic = progress.failures[0]
        if progress.requires_manual_review_partial:
            return self.outcomes.partial(
                file_ref=progress.file_ref,
                stage="oracle_consensus",
                reason_code="consensus_not_reached",
                private_diagnostic=(
                    diagnostic if stage == "oracle_consensus" else None
                ),
            )
        if progress.targets_accepted:
            if _partial_reason_supported(reason_code):
                return self.outcomes.partial(
                    file_ref=progress.file_ref,
                    stage=stage,
                    reason_code=reason_code,
                    private_diagnostic=diagnostic,
                )
            return self.outcomes.partial(
                file_ref=progress.file_ref,
                stage="processing",
                reason_code="partial_result_available",
                private_diagnostic=None,
            )
        return self.outcomes.failed(
            file_ref=progress.file_ref,
            stage=stage,
            reason_code=reason_code,
            private_diagnostic=diagnostic,
        )

    def _try_put_diagnostic(
        self,
        *,
        store: SqliteArtifactStoreAdapter,
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
        document_id: str,
        target_id: str | None,
        reason_code: str,
        diagnostic: dict[str, Any],
    ) -> str | None:
        try:
            return self._put_record(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_id=document_id,
                artifact_type=(
                    "broker_reports_pdf_structural_repair_private_diagnostic_v1"
                ),
                visibility="private_case",
                storage_backend="project_artifact_payload",
                validation_status="blocked",
                payload=diagnostic,
                safe_metadata={
                    "target_id": target_id,
                    "reason_code": reason_code,
                    "authority_state": "non_authoritative",
                    "production_ready": False,
                    "production_gate2_selection_changed": False,
                },
            )
        except Exception:
            return None

    @staticmethod
    def _put_record(
        *,
        store: SqliteArtifactStoreAdapter,
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
        document_id: str | None,
        artifact_type: str,
        visibility: str,
        storage_backend: str,
        validation_status: str,
        payload: Any,
        safe_metadata: dict[str, Any],
    ) -> str:
        access_policy = {
            "requires_user_id": True,
            "requires_case_or_chat": True,
            "requires_workspace_model_id_when_present": bool(
                context.workspace_model_id
            ),
            "requires_gate2_resolver": visibility == "private_case",
        }
        record = ArtifactRecord(
            artifact_id=new_artifact_id(),
            artifact_type=artifact_type,
            case_id=context.case_id,
            chat_id=context.chat_id,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=context.normalization_run_id,
            document_id=document_id,
            source_file_ref=None,
            visibility=visibility,
            storage_backend=storage_backend,
            retention_policy=retention_policy,
            access_policy=access_policy,
            validation_status=validation_status,
            lifecycle_status=lifecycle_for_visibility(
                visibility=visibility,
                validation_status=validation_status,
            ),
            payload_kind=(
                "json_file"
                if storage_backend == "project_artifact_payload"
                else "inline_json"
            ),
            payload=payload,
            safe_metadata=safe_metadata,
        )
        return store.put_record(record).artifact_id


def _semantic_physical_alternative(
    materialization: dict[str, Any],
) -> dict[str, Any]:
    return {
        "grid_checksum": (
            materialization.get("canonical_joined_grid_checksum")
            or materialization.get("placement_checksum")
        ),
        "row_count": materialization.get("row_count"),
        "column_count": materialization.get("column_count"),
        "header_rows": copy.deepcopy(
            materialization.get("header_rows") or []
        ),
        "header_hierarchy": [
            {
                "parent_row": relation.get("parent_row"),
                "parent_column": relation.get("parent_column"),
                "child_start_column": relation.get(
                    "child_start_column"
                ),
                "child_end_column": relation.get("child_end_column"),
            }
            for relation in _dicts(materialization.get("header_hierarchy"))
        ],
        "spans": [
            {
                "start_row": span.get("start_row"),
                "end_row": span.get("end_row"),
                "start_column": span.get("start_column"),
                "end_column": span.get("end_column"),
                "relation": span.get("relation"),
            }
            for span in _dicts(materialization.get("spans"))
        ],
        "rows": [
            {
                "row_ordinal": row.get("row_ordinal"),
                "row_kind": row.get("row_kind"),
            }
            for row in _dicts(materialization.get("rows"))
        ],
        "cells": [
            {
                "cell_ref": cell.get("cell_ref"),
                "row_ordinal": cell.get("row_ordinal"),
                "column_ordinal": cell.get("column_ordinal"),
                "candidate_ids": copy.deepcopy(
                    cell.get("candidate_ids") or []
                ),
                "exact_values": copy.deepcopy(
                    cell.get("resolved_source_values") or []
                ),
            }
            for cell in _dicts(materialization.get("cells"))
        ],
    }


def _base_summary(
    *,
    enabled: bool,
    vlm_guided_intake_enabled: bool,
    semantic_header_shadow_enabled: bool,
) -> dict[str, Any]:
    return {
        "schema_version": PDF_STRUCTURAL_REPAIR_SHADOW_SUMMARY_SCHEMA,
        "enabled": enabled,
        "vlm_guided_intake_enabled": (
            enabled and vlm_guided_intake_enabled
        ),
        "files_total": 0,
        "tables_discovered": 0,
        "tables_selected": 0,
        "accepted_supplied_consensus_tables": 0,
        "accepted_physical_structure_tables": 0,
        "tables_failed": 0,
        "tables_skipped_by_limit": 0,
        "tables_skipped_by_allowlist": 0,
        "terminal_outcomes": {},
        "target_outcomes": [],
        "file_processing_outcomes": None,
        "private_target_states_persisted": 0,
        "private_runtime_results_persisted": 0,
        "private_diagnostics_persisted": 0,
        "private_repeat_histories_persisted": 0,
        "continuation_groups_discovered": 0,
        "continuation_groups_accepted": 0,
        "continuation_groups_failed": 0,
        "continuation_descriptors_not_grouped": 0,
        "continuation_manual_review_required": False,
        "continuation_group_outcomes": [],
        "private_continuation_discoveries_persisted": 0,
        "private_continuation_results_persisted": 0,
        "private_continuation_materializations_persisted": 0,
        "semantic_header_shadow_enabled": (
            enabled and semantic_header_shadow_enabled
        ),
        "semantic_projection_status_counts": {},
        "semantic_projection_reason_counts": {},
        "private_semantic_projections_persisted": 0,
        "private_semantic_diagnostics_persisted": 0,
        "authority_state": "non_authoritative",
        "production_ready": False,
        "production_gate2_selection_changed": False,
        "base_normalization_mutated": False,
        "knowledge_rag_used": False,
        "customer_values_included": False,
        "crop_bytes_included": False,
        "raw_provider_response_included": False,
        "private_diagnostics_included": False,
    }


def _target_summary(
    *,
    target_id: str,
    terminal_status: str,
    reason_code: str | None,
    count_token_calls: int | None,
    generate_calls: int | None,
    target_state_persisted: bool,
    runtime_result_persisted: bool,
    repeat_history_persisted: bool,
    repeat_history_ever_conflicted: bool,
    semantic_projection_status: str = "disabled",
    semantic_projection_persisted: bool = False,
) -> dict[str, Any]:
    return {
        "target_id": target_id,
        "terminal_status": terminal_status,
        "reason_code": reason_code,
        "count_token_calls": count_token_calls,
        "generate_calls": generate_calls,
        "hidden_retry": False,
        "provider_failover": False,
        "target_state_persisted": target_state_persisted,
        "runtime_result_persisted": runtime_result_persisted,
        "repeat_history_persisted": repeat_history_persisted,
        "repeat_history_ever_conflicted": (
            repeat_history_ever_conflicted
        ),
        "semantic_projection_status": semantic_projection_status,
        "semantic_projection_persisted": semantic_projection_persisted,
        "authority_state": "non_authoritative",
        "production_ready": False,
        "production_gate2_selection_changed": False,
    }


def _outcome_reason_from_runtime(result: dict[str, Any]) -> tuple[str, str]:
    codes = _object(result.get("safe_summary")).get("reason_codes")
    code = str(codes[0]) if isinstance(codes, list) and codes else ""
    return _map_internal_code(code)


def _outcome_reason_from_exception(exc: BaseException) -> tuple[str, str]:
    return _map_internal_code(str(getattr(exc, "code", "")))


def _map_internal_code(code: str) -> tuple[str, str]:
    if "intake_unsupported" in code or "intake_factory" in code:
        return "parser_failed", "parsing"
    if "atom_budget" in code:
        return "atom_budget_exceeded", "visual_topology"
    if "counted_input_budget" in code or "token_budget" in code:
        return "model_input_budget_exceeded", "input_budget"
    if "count_tokens" in code or "not_qualified" in code:
        return "provider_temporarily_unavailable", "provider_call"
    if any(
        item in code
        for item in (
            "provider_attempt",
            "provider_lineage",
            "provider_accounting",
            "provider_execution",
            "topology_invalid",
            "response_invalid",
        )
    ):
        return "provider_response_invalid", "provider_call"
    if any(item in code for item in ("consensus", "unsupported", "ambiguous", "uncertain")):
        return "consensus_not_reached", "oracle_consensus"
    if "window_" in code and any(
        item in code
        for item in ("boundary", "column", "span", "alternative", "safe_cut")
    ):
        return "consensus_not_reached", "oracle_consensus"
    if "repeat_history" in code:
        return "consensus_not_reached", "oracle_consensus"
    if "materialization" in code or "validation" in code:
        return "table_validation_failed", "output_validation"
    if any(
        item in code
        for item in (
            "parser",
            "raster",
            "target_input",
            "scope_empty",
            "scope_incomplete",
        )
    ):
        return "parser_failed", "parsing"
    return "internal_processing_failed", "processing"


def _partial_reason_supported(reason_code: str) -> bool:
    return reason_code in {
        "atom_budget_exceeded",
        "model_input_budget_exceeded",
        "provider_temporarily_unavailable",
        "provider_rate_limited",
        "provider_response_invalid",
        "consensus_not_reached",
        "table_validation_failed",
    }


def _safe_exception_terminal(exc: BaseException) -> str:
    code = str(getattr(exc, "code", ""))
    allowed = {
        "pdf_visual_topology_atom_budget_exceeded",
        "pdf_visual_topology_model_json_budget_exceeded",
        "pdf_visual_topology_static_token_budget_exceeded",
        "pdf_table_raster_dimension_budget_exceeded",
        "pdf_table_raster_encoded_budget_exceeded",
        "pdf_structural_repair_shadow_intake_unsupported",
        "pdf_structural_repair_shadow_target_input_invalid",
        "pdf_structural_repair_shadow_repeat_history_invalid",
        "pdf_structural_repair_shadow_repeat_history_conflict_erased",
    }
    return code if code in allowed else "structural_repair_target_failed"


def _page_bbox(descriptor: dict[str, Any]) -> list[float] | None:
    width = descriptor.get("page_width")
    height = descriptor.get("page_height")
    if not _positive_finite_number(width) or not _positive_finite_number(
        height
    ):
        return None
    return [0.0, 0.0, float(width), float(height)]


def _page_word_bboxes(
    *,
    projection: dict[str, Any],
    page_ref: str,
    parent_bbox: list[float],
) -> tuple[list[dict[str, Any]], bool]:
    bbox_by_ref: dict[str, list[float]] = {}
    valid = True
    for item in _dicts(projection.get("bbox_inventory")):
        bbox_ref = str(item.get("bbox_ref") or "")
        bbox = item.get("bbox")
        if (
            not bbox_ref
            or bbox_ref in bbox_by_ref
            or not isinstance(bbox, list)
            or len(bbox) != 4
            or not all(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(float(value))
                for value in bbox
            )
            or float(bbox[0]) > float(bbox[2])
            or float(bbox[1]) > float(bbox[3])
        ):
            valid = False
            continue
        bbox_by_ref[bbox_ref] = [float(value) for value in bbox]
    word_refs: set[str] = set()
    bbox_refs: set[str] = set()
    result: list[dict[str, Any]] = []
    for word in _dicts(projection.get("word_inventory")):
        if word.get("page_ref") != page_ref:
            continue
        word_ref = str(word.get("word_ref") or "")
        bbox_ref = str(word.get("bbox_ref") or "")
        bbox = bbox_by_ref.get(bbox_ref)
        if (
            not word_ref
            or word_ref in word_refs
            or not bbox_ref
            or bbox_ref in bbox_refs
            or bbox is None
            or not _bbox_contained(bbox, parent_bbox)
        ):
            valid = False
            continue
        word_refs.add(word_ref)
        bbox_refs.add(bbox_ref)
        result.append(
            {
                "word_ref": word_ref,
                "bbox_ref": bbox_ref,
                "bbox": copy.deepcopy(bbox),
            }
        )
    return result, bool(valid and result)


def _page_evidence(
    *,
    visual_package: dict[str, Any],
    projection_checksum: str,
    verified_word_bbox_records: list[dict[str, Any]],
) -> dict[str, Any]:
    material = {
        "visual_package": visual_package,
        "projection_checksum": projection_checksum,
        "verified_word_bbox_records": verified_word_bbox_records,
    }
    return {
        "visual_package_hash": visual_package.get("package_hash"),
        "projection_checksum": projection_checksum,
        "verified_word_bbox_records": copy.deepcopy(
            verified_word_bbox_records
        ),
        "evidence_checksum": sha256_json(material),
    }


def _word_bbox_records_valid(
    value: Any,
    *,
    parent_bbox: Any,
) -> bool:
    if (
        not isinstance(value, list)
        or not value
        or not isinstance(parent_bbox, list)
        or len(parent_bbox) != 4
    ):
        return False
    word_refs: set[str] = set()
    bbox_refs: set[str] = set()
    for record in value:
        item = _object(record)
        word_ref = item.get("word_ref")
        bbox_ref = item.get("bbox_ref")
        bbox = item.get("bbox")
        if (
            set(item) != {"word_ref", "bbox_ref", "bbox"}
            or not isinstance(word_ref, str)
            or not word_ref
            or word_ref in word_refs
            or not isinstance(bbox_ref, str)
            or not bbox_ref
            or bbox_ref in bbox_refs
            or not isinstance(bbox, list)
            or len(bbox) != 4
            or not all(
                isinstance(coordinate, (int, float))
                and not isinstance(coordinate, bool)
                and math.isfinite(float(coordinate))
                for coordinate in bbox
            )
            or not _bbox_contained(bbox, parent_bbox)
        ):
            return False
        word_refs.add(word_ref)
        bbox_refs.add(bbox_ref)
    return True


def _full_page_manifest_identity_verified(
    *,
    parent_manifest: dict[str, Any],
    visual_package: dict[str, Any],
    page_ref: str,
    page_number: int,
    parent_bbox: Any,
    expected_png_sha256: str,
) -> bool:
    manifest = _object(parent_manifest)
    package = _object(visual_package)
    crop = _object(package.get("crop_identity"))
    if (
        not isinstance(parent_bbox, list)
        or len(parent_bbox) != 4
        or not all(
            isinstance(coordinate, (int, float))
            and not isinstance(coordinate, bool)
            and math.isfinite(float(coordinate))
            for coordinate in parent_bbox
        )
        or not isinstance(page_ref, str)
        or not page_ref
        or page_number < 1
        or not isinstance(expected_png_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected_png_sha256) is None
    ):
        return False
    unsigned_manifest = copy.deepcopy(manifest)
    stored_manifest_hash = unsigned_manifest.pop("manifest_hash", None)
    try:
        manifest_checksum_valid = bool(
            isinstance(stored_manifest_hash, str)
            and re.fullmatch(r"[0-9a-f]{64}", stored_manifest_hash)
            and stored_manifest_hash == sha256_json(unsigned_manifest)
        )
    except (TypeError, ValueError):
        manifest_checksum_valid = False
    return bool(
        manifest_checksum_valid
        and manifest.get("document_ref") == package.get("document_ref")
        and manifest.get("pdf_sha256") == package.get("pdf_sha256")
        and manifest.get("page_ref") == page_ref == package.get("page_ref")
        and manifest.get("page_number") == page_number == package.get("page_number")
        and manifest.get("render_scope") == "full_page"
        and manifest.get("actual_page_bbox") == parent_bbox
        and manifest.get("declared_table_bbox") == parent_bbox
        and manifest.get("rendered_bbox") == parent_bbox
        and manifest.get("padding_points") == 0.0
        and manifest.get("page_rotation") == 0
        and manifest.get("applied_rotation") == 0
        and manifest.get("full_page_identity_verified") is True
        and manifest.get("png_sha256") == expected_png_sha256
        and crop.get("manifest_hash") == stored_manifest_hash
        and crop.get("crop_sha256") == expected_png_sha256
        and crop.get("declared_table_bbox") == parent_bbox
        and crop.get("rendered_bbox") == parent_bbox
        and crop.get("padding_points") == 0.0
    )


def _bbox_contained(inner: list[float], outer: list[float]) -> bool:
    return bool(
        len(inner) == 4
        and len(outer) == 4
        and float(outer[0]) <= float(inner[0]) <= float(inner[2]) <= float(outer[2])
        and float(outer[1]) <= float(inner[1]) <= float(inner[3]) <= float(outer[3])
    )


def _guided_runtime_intake_observations(
    result: dict[str, Any],
) -> tuple[
    int | None,
    list[str] | None,
    str | None,
    list[str] | None,
]:
    journal = _dicts(result.get("journal"))
    counted_tokens = _object(
        journal[0].get("count_tokens") if journal else None
    ).get("total_tokens")
    actual_counted_tokens = (
        counted_tokens
        if isinstance(counted_tokens, int)
        and not isinstance(counted_tokens, bool)
        and counted_tokens >= 0
        else None
    )
    terminal = str(result.get("runtime_terminal_status") or "")
    upstream_reasons: list[str] | None = None
    if terminal in {"preflight_blocked", "provider_failed"}:
        upstream_reasons = [
            str(item)
            for item in _object(result.get("safe_summary")).get(
                "reason_codes"
            )
            or []
            if isinstance(item, str) and item
        ]
        if not upstream_reasons:
            upstream_reasons = ["pdf_vlm_guided_intake_upstream_failed"]
    if actual_counted_tokens is None and upstream_reasons is None:
        raise PdfStructuralRepairShadowError(
            "pdf_structural_repair_shadow_counted_tokens_missing"
        )
    detection_decision, detection_reasons = _detection_from_table_presence(
        {
            "proposal_absent": "absent",
            "proposal_ambiguous": "uncertain",
        }.get(terminal, "present" if upstream_reasons is None else None)
    )
    return (
        actual_counted_tokens,
        upstream_reasons,
        detection_decision,
        detection_reasons,
    )


def _detection_from_table_presence(
    value: Any,
) -> tuple[str | None, list[str] | None]:
    if value == "present":
        return "plausible", []
    if value == "absent":
        return "implausible", ["vlm_table_presence_absent"]
    if value == "uncertain":
        return "uncertain", ["vlm_table_presence_uncertain"]
    return None, None


def _source_bbox_from_normalized(
    value: Any, parent_bbox: list[float]
) -> list[float]:
    if (
        not isinstance(value, list)
        or len(value) != 4
        or not all(
            isinstance(item, (int, float))
            and not isinstance(item, bool)
            and math.isfinite(float(item))
            and 0.0 <= float(item) <= 1.0
            for item in value
        )
        or float(value[0]) >= float(value[2])
        or float(value[1]) >= float(value[3])
    ):
        raise PdfStructuralRepairShadowError(
            "pdf_structural_repair_shadow_page_region_bbox_invalid"
        )
    width = parent_bbox[2] - parent_bbox[0]
    height = parent_bbox[3] - parent_bbox[1]
    return [
        round(parent_bbox[0] + float(value[0]) * width, 6),
        round(parent_bbox[1] + float(value[1]) * height, 6),
        round(parent_bbox[0] + float(value[2]) * width, 6),
        round(parent_bbox[1] + float(value[3]) * height, 6),
    ]


def _intake_morphology_metadata(
    descriptor: dict[str, Any],
) -> dict[str, Any]:
    morphology: dict[str, Any] = {}
    for key in (
        "table_strategy_ref",
        "geometry_confidence",
        "rows_total",
        "columns_total",
        "candidate_rank_on_page",
        "candidates_on_page",
    ):
        value = descriptor.get(key)
        if isinstance(value, str) and len(value) <= 128:
            morphology[key] = value
        elif isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            morphology[key] = value
        elif isinstance(value, float) and math.isfinite(value):
            morphology[key] = value
        elif value is None:
            morphology[key] = None
    return {"parser_morphology": morphology}


def _safe_intake_metadata(value: dict[str, Any]) -> dict[str, Any]:
    detection = _object(value.get("detection"))
    processability = _object(value.get("processability"))
    holdout = _object(value.get("holdout"))
    return {
        "intake_contract_checksum": value.get("contract_checksum"),
        "intake_detection_decision": detection.get("decision"),
        "intake_detection_reason_codes": copy.deepcopy(
            detection.get("reason_codes") or []
        ),
        "intake_processability_decision": processability.get("decision"),
        "intake_processability_reason_codes": copy.deepcopy(
            processability.get("reason_codes") or []
        ),
        "intake_holdout_decision": holdout.get("decision"),
        "intake_holdout_reason_codes": copy.deepcopy(
            holdout.get("reason_codes") or []
        ),
    }


def _positive_finite_number(value: Any) -> bool:
    return bool(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and float(value) > 0.0
    )


def _outcome_file_ref(value: str) -> str:
    if _SAFE_FILE_REF.fullmatch(value) and ".." not in value:
        return value
    return "document_" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _increment(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1


def _merge_counts(target: dict[str, int], source: dict[str, int]) -> None:
    for key, count in source.items():
        target[key] = target.get(key, 0) + count


def _safe_semantic_reason_codes(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        code = (
            item
            if isinstance(item, str) and _SAFE_SEMANTIC_REASON.fullmatch(item)
            else "pdf_semantic_header_projection_failed"
        )
        if code not in result:
            result.append(code)
    return sorted(result)


def _increment_semantic_reasons(
    counts: dict[str, int],
    reasons: list[str],
) -> None:
    for reason in _safe_semantic_reason_codes(reasons):
        key = reason
        if key not in counts and len(counts) >= _SEMANTIC_REASON_COUNT_LIMIT - 1:
            key = _SEMANTIC_REASON_TRUNCATED
        counts[key] = counts.get(key, 0) + 1


def _semantic_reasons_for_status(status: str) -> list[str]:
    reason_by_status = {
        "not_projected_physical_ambiguity": (
            "pdf_semantic_header_not_projected_physical_ambiguity"
        ),
        "not_projected_historical_conflict": (
            "pdf_semantic_header_not_projected_historical_conflict"
        ),
        "not_projected_structural_terminal": (
            "pdf_semantic_header_not_projected_structural_terminal"
        ),
        "not_projected_structural_failure": (
            "pdf_semantic_header_not_projected_structural_failure"
        ),
    }
    reason = reason_by_status.get(status)
    return [reason] if reason is not None else []


def _continuation_descriptor(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "document_ref": value.get("document_ref"),
        "pdf_sha256": value.get("pdf_sha256"),
        "page_ref": value.get("page_ref"),
        "page_number": value.get("page_number"),
        "table_ref": value.get("table_ref"),
        "page_width": value.get("page_width"),
        "page_height": value.get("page_height"),
        "table_bbox": copy.deepcopy(value.get("table_bbox")),
        "columns_total": value.get("columns_total"),
        "table_strategy_ref": value.get("table_strategy_ref"),
        "geometry_confidence": value.get("geometry_confidence"),
    }


def _mark_continuation_partial(progress: _DocumentProgress) -> None:
    if progress.targets_accepted < 1:
        return
    progress.requires_manual_review_partial = True
    if not any(
        reason == "consensus_not_reached" and stage == "oracle_consensus"
        for reason, stage, _ in progress.failures
    ):
        progress.failures.append(
            ("consensus_not_reached", "oracle_consensus", None)
        )


def _continuation_group_outcome(
    *,
    continuation_group_id: str | None,
    status: str,
    fragment_count: int,
    row_count: int | None,
    column_count: int | None,
    reason_codes: list[str],
    semantic_projection_status: str = "disabled",
    semantic_projection_persisted: bool = False,
    semantic_reason_codes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "continuation_group_id": continuation_group_id,
        "status": status,
        "fragment_count": fragment_count,
        "row_count": row_count,
        "column_count": column_count,
        "reason_codes": sorted(set(reason_codes)),
        "semantic_projection_status": semantic_projection_status,
        "semantic_projection_persisted": semantic_projection_persisted,
        "semantic_reason_codes": sorted(set(semantic_reason_codes or [])),
    }


def _optional_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _positive_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _strict_nonnegative_int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _expected_runtime_calls(result: dict[str, Any]) -> int:
    plan = _object(result.get("window_plan"))
    if result.get("execution_mode") == "vertical_atom_windows":
        return 2 * _strict_nonnegative_int(plan.get("window_count"))
    return 2


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
