from __future__ import annotations

import base64
import copy
import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from .artifact_lifecycle import lifecycle_for_visibility
from .artifact_models import ArtifactAccessContext, ArtifactRecord, RetentionPolicy
from .artifact_store import SqliteArtifactStoreAdapter, new_artifact_id
from .file_processing_outcomes import FileProcessingOutcomeFactory
from .pdf_continuation_discovery import PdfContinuationDiscoveryFactory
from .pdf_dual_oracle_contracts import PdfDualOracleContractFactory
from .pdf_hybrid_contracts import sha256_json
from .pdf_parser_geometry import PdfParserGeometryFactory
from .pdf_structural_repair_runtime import (
    PdfStructuralRepairRuntimeConfig,
    PdfStructuralRepairRuntimeFactory,
)
from .pdf_table_raster import PdfTableRasterConfig, PdfTableRasterFactory
from .pdf_visual_topology import PdfVisualTopologyFactory


PDF_STRUCTURAL_REPAIR_SHADOW_SUMMARY_SCHEMA = (
    "broker_reports_pdf_structural_repair_shadow_summary_v1"
)
PDF_STRUCTURAL_REPAIR_TARGET_STATE_SCHEMA = (
    "broker_reports_pdf_structural_repair_target_state_v1"
)

FACTORY_REQUIRED = (
    "PdfStructuralRepairShadowFactory.create is the only production entrypoint "
    "for structural-repair shadow orchestration"
)
FORBIDDEN = (
    "Callers must not invoke structural stages or providers directly, retry or "
    "fail over invisibly, expose private target/provider data, mutate the base "
    "normalization, or change production Gate 2 selection"
)

_FACTORY_TOKEN = object()
_SAFE_FILE_REF = re.compile(
    r"^(?:file|doc|brdoc|document|artifact|upload)_[A-Za-z0-9]"
    r"[A-Za-z0-9._:-]{0,119}$"
)


@dataclass(frozen=True)
class PdfStructuralRepairShadowConfig:
    enabled: bool = False
    maximum_tables: int = 8
    table_allowlist: tuple[str, ...] = ()


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
            or not _positive_integer(self.config.maximum_tables)
            or not isinstance(self.config.table_allowlist, tuple)
            or any(
                not isinstance(item, str) or not item or len(item) > 256
                for item in self.config.table_allowlist
            )
            or len(self.config.table_allowlist)
            != len(set(self.config.table_allowlist))
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
                structural_runtime=None,
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
            structural_runtime=structural_runtime,
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
        structural_runtime: Any | None,
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
        self.structural_runtime = structural_runtime
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
            summary = _base_summary(enabled=False)
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
        target_summaries: list[dict[str, Any]] = []
        terminal_counts: dict[str, int] = {}
        completed_fragments_by_table: dict[str, dict[str, Any]] = {}
        documents, descriptors = self._discover(package)

        selected: list[dict[str, Any]] = []
        for descriptor in descriptors:
            progress = documents[descriptor["document_ref"]]
            progress.candidates_discovered += 1
            if self.config.table_allowlist and (
                descriptor["table_ref"] not in self.config.table_allowlist
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
                    )
                    target_summaries.append(target_summary)
                    _increment(terminal_counts, "provider_not_qualified")
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
                    repeat_history_refs.append(repeat_history_ref)
                    refs.extend((state_ref, repeat_history_ref, runtime_ref))
                    safe_runtime = _object(result.get("safe_summary"))
                    terminal = str(
                        result.get("runtime_terminal_status")
                        or "no_valid_consensus"
                    )
                    history_conflicted = (
                        repeat_history.get("ever_conflicted") is True
                    )
                    if (
                        terminal == "accepted_unique_consensus"
                        and not history_conflicted
                    ):
                        progress.targets_accepted += 1
                        reason_code = None
                        completed_fragments_by_table[
                            descriptor["table_ref"]
                        ] = {
                            **fragment_context,
                            "repeat_history_ever_conflicted": False,
                        }
                    else:
                        progress.targets_failed += 1
                        if history_conflicted:
                            reason_code, stage = (
                                "consensus_not_reached",
                                "oracle_consensus",
                            )
                            terminal = "historical_conflict_manual_review"
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
                            repeat_history_persisted=True,
                            repeat_history_ever_conflicted=history_conflicted,
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
                        )
                    )
                    _increment(terminal_counts, terminal)

        continuation_progress = self._run_continuation_groups(
            store=store,
            selected=selected,
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
        file_records = [
            self._file_outcome(progress)
            for _, progress in sorted(documents.items())
        ]
        file_processing_outcomes = (
            self.outcomes.batch(file_records).model_context()
            if file_records
            else None
        )
        summary = _base_summary(enabled=True)
        summary.update(
            {
                "files_total": len(documents),
                "tables_discovered": sum(
                    item.candidates_discovered for item in documents.values()
                ),
                "tables_selected": sum(
                    item.targets_selected for item in documents.values()
                ),
                "accepted_unique_consensus_tables": sum(
                    item.targets_accepted for item in documents.values()
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
            "summary_ref": summary_ref,
            "summary": summary,
            "file_processing_outcomes": file_processing_outcomes,
        }

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
                    terminal == "accepted_unique_consensus"
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
                    )
                )
            except Exception as exc:
                progress["groups_failed"] += 1
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
            for ordinal, candidate in enumerate(candidates, start=1):
                table_ref = str(candidate.get("table_candidate_ref") or "")
                page_ref = str(candidate.get("page_ref") or "")
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
        str,
        dict[str, Any],
        dict[str, Any],
    ]:
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
        execution_mode = self.structural_runtime.execution_mode(
            parser_observation
        )
        window_plan = (
            self.structural_runtime.plan_windowed_target(parser_observation)
            if execution_mode == "vertical_atom_windows"
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
        if execution_mode == "vertical_atom_windows":
            visual_package = self.structural_runtime.build_windowed_ledger_package(
                parser_observation=parser_observation,
                crop_manifest=_object(rendered.get("manifest")),
            )
        else:
            visual_package = self.visual.build_package(
                parser_observation=parser_observation,
                crop_manifest=_object(rendered.get("manifest")),
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
        repeat_history_scope = self._repeat_history_scope(
            parser_observation=parser_observation,
            crop_manifest=_object(rendered.get("manifest")),
            execution_mode=execution_mode,
            window_plan=window_plan,
        )
        prior_history, prior_history_ref = self._load_repeat_history(
            store=store,
            context=context,
            scope=repeat_history_scope,
        )
        target_state = {
            "schema_version": PDF_STRUCTURAL_REPAIR_TARGET_STATE_SCHEMA,
            "target_id": package_descriptor["target_id"],
            "parser_observation": parser_observation,
            "parser_geometry_observation": geometry_observation,
            "private_raster": rendered,
            "visual_package": visual_package,
            "execution_mode": execution_mode,
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
        if window_plan is not None:
            target_state["window_plan"] = copy.deepcopy(window_plan)
            target_state["private_window_rasters"] = copy.deepcopy(
                private_window_rasters
            )
            target_state["window_packages"] = [
                copy.deepcopy(item["window_package"])
                for item in window_inputs
            ]
        target_state["target_state_checksum"] = sha256_json(target_state)
        state_ref = self._put_record(
            store=store,
            context=context,
            retention_policy=retention_policy,
            document_id=document_ref,
            artifact_type="broker_reports_pdf_structural_repair_target_state_v1",
            visibility="private_case",
            storage_backend="project_artifact_payload",
            validation_status="validated",
            payload=target_state,
            safe_metadata={
                "schema_version": target_state["schema_version"],
                "target_id": package_descriptor["target_id"],
                "candidate_atoms": _object(
                    visual_package.get("component_accounting")
                ).get("atom_count"),
                "dpi": 150,
                "padding_points": 0.0,
                "authority_state": "non_authoritative",
                "production_ready": False,
                "production_gate2_selection_changed": False,
            },
        )
        try:
            if window_plan is None:
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
            raise _TargetExecutionError(
                "pdf_structural_repair_shadow_provider_execution_failed",
                private_cause=exc,
                target_state_ref=state_ref,
            ) from exc
        terminal = result.get("runtime_terminal_status")
        if self.structural_runtime.validate_result(result):
            raise PdfStructuralRepairShadowError(
                "pdf_structural_repair_shadow_runtime_result_invalid"
            )
        if terminal == "accepted_unique_consensus" and (
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
                    "broker_reports_pdf_structural_repair_runtime_result_v1"
                ),
                visibility="private_case",
                storage_backend="project_artifact_payload",
                validation_status=(
                    "validated"
                    if terminal == "accepted_unique_consensus"
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
            and _object(record.safe_metadata).get("scope_checksum")
            == scope_checksum
        ]
        if not candidates:
            return None, None
        latest = candidates[-1]
        try:
            payload = store.read_payload(latest)
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
                "accepted_unique_consensus"
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
            == "accepted_unique_consensus"
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


def _base_summary(*, enabled: bool) -> dict[str, Any]:
    return {
        "schema_version": PDF_STRUCTURAL_REPAIR_SHADOW_SUMMARY_SCHEMA,
        "enabled": enabled,
        "files_total": 0,
        "tables_discovered": 0,
        "tables_selected": 0,
        "accepted_unique_consensus_tables": 0,
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
    if "consensus" in code or "unsupported" in code:
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
        "pdf_structural_repair_shadow_target_input_invalid",
        "pdf_structural_repair_shadow_repeat_history_invalid",
        "pdf_structural_repair_shadow_repeat_history_conflict_erased",
    }
    return code if code in allowed else "structural_repair_target_failed"


def _outcome_file_ref(value: str) -> str:
    if _SAFE_FILE_REF.fullmatch(value) and ".." not in value:
        return value
    return "document_" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _increment(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1


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
) -> dict[str, Any]:
    return {
        "continuation_group_id": continuation_group_id,
        "status": status,
        "fragment_count": fragment_count,
        "row_count": row_count,
        "column_count": column_count,
        "reason_codes": sorted(set(reason_codes)),
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
