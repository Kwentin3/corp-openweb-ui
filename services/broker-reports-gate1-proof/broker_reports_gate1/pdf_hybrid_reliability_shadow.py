from __future__ import annotations

import base64
import copy
from dataclasses import asdict, dataclass
from typing import Any

from .artifact_lifecycle import lifecycle_for_visibility
from .artifact_models import ArtifactAccessContext, ArtifactRecord, RetentionPolicy
from .artifact_store import SqliteArtifactStoreAdapter, new_artifact_id
from .pdf_hybrid_budget import (
    PdfHybridBudgetConfig,
    PdfHybridBudgetError,
    PdfHybridBudgetFactory,
)
from .pdf_hybrid_compaction import (
    PdfHybridCompactionError,
    PdfHybridCompactionFactory,
)
from .pdf_hybrid_contracts import sha256_json
from .pdf_hybrid_materialization import (
    PdfHybridMaterializationError,
    PdfHybridMaterializationFactory,
)
from .pdf_hybrid_provider import GeminiHybridProviderAdapter, PdfHybridProviderError
from .pdf_hybrid_reliability import PdfHybridReliabilityFactory
from .pdf_hybrid_structure import PdfHybridStructureFactory
from .pdf_hybrid_windows import (
    PdfHybridWindowConfig,
    PdfHybridWindowError,
    PdfHybridWindowFactory,
)
from .pdf_table_classification import PdfTableClassifierConfig, PdfTableClassifierFactory
from .pdf_table_raster import PdfTableRasterConfig, PdfTableRasterError, PdfTableRasterFactory
from .pdf_table_validation import PdfTableValidationFactory


PDF_HYBRID_RELIABILITY_SUMMARY_SCHEMA = (
    "broker_reports_pdf_hybrid_reliability_summary_v2"
)
FACTORY_REQUIRED = (
    "PdfHybridReliabilityShadowFactory.create is the only Goal 3 private shadow runtime entrypoint"
)
FORBIDDEN = (
    "The reliability runtime must not select production Gate 2 input, publish evidence, retry invisibly, "
    "or choose between conflicting revisions"
)


@dataclass(frozen=True)
class PdfHybridReliabilityShadowConfig:
    enabled: bool = False
    primary_dpi: int = 150
    escalation_dpi: int = 200
    table_allowlist: tuple[str, ...] = ()
    repeat_structurally_valid_tables: bool = True


class PdfHybridReliabilityShadowFactory:
    def __init__(
        self,
        config: PdfHybridReliabilityShadowConfig | None = None,
        *,
        classifier_config: PdfTableClassifierConfig | None = None,
        raster_config: PdfTableRasterConfig | None = None,
        budget_config: PdfHybridBudgetConfig | None = None,
        window_config: PdfHybridWindowConfig | None = None,
    ) -> None:
        self.config = config or PdfHybridReliabilityShadowConfig()
        self.classifier_config = classifier_config
        self.raster_config = raster_config
        self.budget_config = budget_config
        self.window_config = window_config

    def create(
        self,
        *,
        provider: GeminiHybridProviderAdapter | None,
        initial_repeatability_ledger: dict[str, Any] | None = None,
    ) -> "PdfHybridReliabilityShadowRuntime":
        classifier_config = self.classifier_config or PdfTableClassifierConfig(
            shadow_allowlist=self.config.table_allowlist
        )
        budget = PdfHybridBudgetFactory(self.budget_config).create()
        return PdfHybridReliabilityShadowRuntime(
            config=self.config,
            provider=provider,
            classifier=PdfTableClassifierFactory(classifier_config).create(),
            raster=PdfTableRasterFactory(self.raster_config).create(),
            compactor=PdfHybridCompactionFactory().create(),
            budget=budget,
            windows=PdfHybridWindowFactory(self.window_config).create(budget=budget),
            materializer=PdfHybridMaterializationFactory().create(),
            validator=PdfTableValidationFactory().create(),
            structure=PdfHybridStructureFactory().create(),
            reliability=PdfHybridReliabilityFactory().create(
                initial_repeatability_ledger=initial_repeatability_ledger
            ),
        )


class PdfHybridReliabilityShadowRuntime:
    def __init__(
        self,
        *,
        config: PdfHybridReliabilityShadowConfig,
        provider: GeminiHybridProviderAdapter | None,
        classifier: Any,
        raster: Any,
        compactor: Any,
        budget: Any,
        windows: Any,
        materializer: Any,
        validator: Any,
        structure: Any,
        reliability: Any,
    ) -> None:
        self.config = config
        self.provider = provider
        self.classifier = classifier
        self.raster = raster
        self.compactor = compactor
        self.budget = budget
        self.windows = windows
        self.materializer = materializer
        self.validator = validator
        self.structure = structure
        self.reliability = reliability

    def run(
        self,
        *,
        store: SqliteArtifactStoreAdapter,
        package: dict[str, Any],
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
        pdf_bytes_by_sha256: dict[str, bytes],
        signal_overrides_by_table: dict[str, dict[str, Any]] | None = None,
        continuation_contracts: list[dict[str, Any]] | None = None,
        dpi_escalation_reasons_by_table: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if not self.config.enabled:
            return {"enabled": False, "artifact_refs": [], "summary": None}
        signal_overrides_by_table = signal_overrides_by_table or {}
        continuation_contracts = continuation_contracts or []
        dpi_escalation_reasons_by_table = dpi_escalation_reasons_by_table or {}
        refs: list[str] = []
        states: dict[str, dict[str, Any]] = {}
        source_payloads = {
            str(item.get("document_ref") or ""): item
            for item in _dicts(package.get("private_normalized_source_payloads"))
        }
        projections = {
            str(item.get("table_ref") or ""): item
            for item in _dicts(package.get("private_normalized_table_projections"))
        }
        documents = {
            str(item.get("document_id") or ""): item
            for item in _dicts(_object(package.get("document_inventory")).get("documents"))
        }
        for document_ref, source_payload in sorted(source_payloads.items()):
            document = documents.get(document_ref, {})
            if document.get("container_format") != "pdf":
                continue
            pdf_sha256 = str(document.get("sha256") or "")
            pdf_bytes = pdf_bytes_by_sha256.get(pdf_sha256)
            projection = _object(source_payload.get("pdf_text_layer_projection"))
            pages = {
                str(item.get("page_ref") or ""): item
                for item in _dicts(projection.get("page_inventory"))
            }
            bboxes = {
                str(item.get("bbox_ref") or ""): list(item.get("bbox") or [])
                for item in _dicts(projection.get("bbox_inventory"))
            }
            for candidate in sorted(
                _dicts(projection.get("table_candidate_inventory")),
                key=lambda item: (
                    _page_number(pages, str(item.get("page_ref") or "")),
                    int(item.get("parser_ordinal") or 0),
                ),
            ):
                table_ref = str(candidate.get("table_candidate_ref") or "")
                if self.config.table_allowlist and table_ref not in self.config.table_allowlist:
                    continue
                page_ref = str(candidate.get("page_ref") or "")
                page_number = _page_number(pages, page_ref)
                deterministic = projections.get(table_ref, {})
                classification = self.classifier.classify(
                    document_ref=document_ref,
                    document_checksum=pdf_sha256,
                    page_ref=page_ref,
                    page_number=page_number,
                    table_candidate=candidate,
                    deterministic_projection=deterministic,
                    signals=signal_overrides_by_table.get(table_ref),
                )
                classification_ref = self._put_private(
                    store=store,
                    context=context,
                    retention_policy=retention_policy,
                    document_id=document_ref,
                    artifact_type="broker_reports_pdf_table_classification_v1",
                    payload=classification,
                    validation_status="validated",
                    safe_metadata={
                        "table_ref": table_ref,
                        "classification_id": classification.get("classification_id"),
                        "selected_path": classification.get("selected_path"),
                        "reason_codes": classification.get("reason_codes"),
                        "authoritative": False,
                    },
                )
                refs.append(classification_ref)
                if pdf_bytes is None:
                    states[table_ref] = self._failure_state(
                        table_ref=table_ref,
                        classification=classification,
                        deterministic=deterministic,
                        code="pdf_hybrid_reliability_source_pdf_unavailable",
                    )
                    continue
                state, new_refs = self._process_table(
                    store=store,
                    context=context,
                    retention_policy=retention_policy,
                    document_ref=document_ref,
                    pdf_sha256=pdf_sha256,
                    pdf_bytes=pdf_bytes,
                    pdf_projection=projection,
                    table_candidate=candidate,
                    table_bbox=bboxes.get(str(candidate.get("bbox_ref") or ""), []),
                    page_ref=page_ref,
                    page_number=page_number,
                    classification=classification,
                    deterministic=deterministic,
                    dpi_escalation_reason=dpi_escalation_reasons_by_table.get(table_ref),
                )
                refs.extend(new_refs)
                states[table_ref] = state

        continuation_by_table: dict[str, dict[str, Any]] = {}
        for contract in continuation_contracts:
            contract_ref = self._put_private(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_id=None,
                artifact_type="broker_reports_pdf_hybrid_continuation_contract_v2",
                payload=contract,
                validation_status="validated",
                safe_metadata={
                    "schema_version": contract.get("schema_version"),
                    "continuation_group_id": contract.get("continuation_group_id"),
                    "shared_column_count": contract.get("shared_column_count"),
                    "fragment_count": len(contract.get("fragments") or []),
                    "authoritative": False,
                },
            )
            refs.append(contract_ref)
            fragment_states = [
                states.get(str(item.get("table_ref") or ""), {})
                for item in _dicts(contract.get("fragments"))
            ]
            continuation = self.structure.validate_continuation(
                contract=contract,
                fragment_results=[
                    {
                        "compact_ledger": item.get("compact_ledger"),
                        "materialization": _object(item.get("primary")).get(
                            "materialization"
                        ),
                        "structural_validation": _object(item.get("primary")).get(
                            "structural_validation"
                        ),
                    }
                    for item in fragment_states
                ],
            )
            continuation_ref = self._put_private(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_id=None,
                artifact_type="broker_reports_pdf_hybrid_continuation_validation_v2",
                payload=continuation,
                validation_status="validated" if continuation["passed"] else "blocked",
                safe_metadata={
                    key: copy.deepcopy(continuation.get(key))
                    for key in (
                        "schema_version",
                        "continuation_group_id",
                        "passed",
                        "reason_codes",
                        "shared_column_count",
                        "fragment_count",
                        "fragment_coverage",
                        "joined_coverage",
                        "authoritative",
                    )
                },
            )
            refs.append(continuation_ref)
            for fragment in _dicts(contract.get("fragments")):
                continuation_by_table[str(fragment.get("table_ref") or "")] = {
                    "required": True,
                    **copy.deepcopy(continuation),
                    "artifact_ref": continuation_ref,
                }

        arbitrations = []
        for table_ref, state in sorted(states.items()):
            primary = _object(state.get("primary"))
            escalation = _object(state.get("escalation"))
            repeatability = _object(state.get("repeatability")) or {
                "required": False,
                "passed": True,
                "ever_conflicted": False,
                "reason_codes": [],
            }
            hybrid_150 = {
                "supported": self.provider is not None,
                "context_budget_passed": primary.get("context_budget_passed") is True,
                "provider_passed": primary.get("provider_passed") is True,
                "binding_status": primary.get("binding_status"),
                "package_count": len(primary.get("packages") or []),
                "placement_checksum": _object(primary.get("materialization")).get(
                    "placement_checksum"
                ),
                "reason_codes": list(primary.get("reason_codes") or []),
            }
            hybrid_200 = {
                "required": bool(state.get("dpi_escalation_reason")),
                "status": escalation.get("status") or "not_run",
                "placement_checksum_match": (
                    bool(_object(primary.get("materialization")).get("placement_checksum"))
                    and _object(primary.get("materialization")).get("placement_checksum")
                    == _object(escalation.get("materialization")).get("placement_checksum")
                ),
                "reason_codes": list(escalation.get("reason_codes") or []),
            }
            structural = _object(primary.get("structural_validation")) or {
                "passed": False,
                "reason_codes": ["pdf_hybrid_structural_validation_unavailable"],
            }
            continuation = continuation_by_table.get(
                table_ref,
                {"required": False, "passed": True, "reason_codes": []},
            )
            arbitration = self.reliability.arbitrate(
                table_ref=table_ref,
                deterministic_signal={
                    "projection_status": _object(state.get("deterministic")).get(
                        "projection_status"
                    ),
                    "selected_path": _object(state.get("classification")).get(
                        "selected_path"
                    ),
                },
                hybrid_150_signal=hybrid_150,
                hybrid_200_signal=hybrid_200,
                structural_signal=structural,
                continuation_signal=continuation,
                repeatability_signal=repeatability,
            )
            arbitration_ref = self._put_private(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_id=None,
                artifact_type="broker_reports_pdf_hybrid_shadow_arbitration_v2",
                payload=arbitration,
                validation_status=(
                    "validated"
                    if arbitration["terminal_status"] == "accepted_shadow"
                    else "blocked"
                ),
                safe_metadata=_safe_arbitration(arbitration),
            )
            refs.append(arbitration_ref)
            arbitration["artifact_ref"] = arbitration_ref
            arbitrations.append(arbitration)

        repeatability_ledger = self.reliability.ledger()
        ledger_ref = self._put_private(
            store=store,
            context=context,
            retention_policy=retention_policy,
            document_id=None,
            artifact_type="broker_reports_pdf_hybrid_repeatability_ledger_v2",
            payload=repeatability_ledger,
            validation_status=(
                "blocked"
                if repeatability_ledger.get("conflicted_task_keys")
                else "validated"
            ),
            safe_metadata={
                "schema_version": repeatability_ledger.get("schema_version"),
                "records": len(repeatability_ledger.get("records") or []),
                "conflicted_tasks": len(
                    repeatability_ledger.get("conflicted_task_keys") or []
                ),
                "monotonic_conflict_memory": True,
                "later_agreement_can_clear_conflict": False,
            },
        )
        refs.append(ledger_ref)
        summary = self._summary(states, arbitrations, ledger_ref)
        summary_ref = self._put_safe(
            store=store,
            context=context,
            retention_policy=retention_policy,
            artifact_type="broker_reports_pdf_hybrid_reliability_summary_v2",
            payload=summary,
        )
        refs.append(summary_ref)
        return {
            "enabled": True,
            "artifact_refs": refs,
            "states": states,
            "arbitrations": arbitrations,
            "repeatability_ledger": repeatability_ledger,
            "repeatability_ledger_ref": ledger_ref,
            "summary": summary,
            "summary_ref": summary_ref,
        }

    def _process_table(
        self,
        *,
        store: SqliteArtifactStoreAdapter,
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
        document_ref: str,
        pdf_sha256: str,
        pdf_bytes: bytes,
        pdf_projection: dict[str, Any],
        table_candidate: dict[str, Any],
        table_bbox: list[float],
        page_ref: str,
        page_number: int,
        classification: dict[str, Any],
        deterministic: dict[str, Any],
        dpi_escalation_reason: str | None,
    ) -> tuple[dict[str, Any], list[str]]:
        refs: list[str] = []
        table_ref = str(table_candidate.get("table_candidate_ref") or "")
        signals = _object(classification.get("measured_signals"))
        try:
            ledger = self.compactor.compact(
                document_ref=document_ref,
                pdf_sha256=pdf_sha256,
                page_ref=page_ref,
                page_number=page_number,
                table_candidate=table_candidate,
                pdf_text_layer_projection=pdf_projection,
                header_depth=int(signals.get("header_depth") or 0),
            )
            plan = self.windows.plan(compact_ledger=ledger)
        except (PdfHybridCompactionError, PdfHybridWindowError) as exc:
            return (
                self._failure_state(
                    table_ref=table_ref,
                    classification=classification,
                    deterministic=deterministic,
                    code=exc.code,
                ),
                refs,
            )
        ledger_ref = self._put_private(
            store=store,
            context=context,
            retention_policy=retention_policy,
            document_id=document_ref,
            artifact_type="broker_reports_pdf_hybrid_compact_ledger_v2",
            payload=ledger,
            validation_status="validated",
            safe_metadata={
                "schema_version": ledger.get("schema_version"),
                "ledger_id": ledger.get("ledger_id"),
                "table_ref": table_ref,
                "row_count": ledger.get("row_count"),
                "column_count": ledger.get("column_count"),
                "header_depth": ledger.get("header_depth"),
                **copy.deepcopy(ledger.get("source_accounting") or {}),
            },
        )
        plan_ref = self._put_private(
            store=store,
            context=context,
            retention_policy=retention_policy,
            document_id=document_ref,
            artifact_type="broker_reports_pdf_hybrid_row_window_plan_v2",
            payload=plan,
            validation_status="validated",
            safe_metadata={
                "schema_version": plan.get("schema_version"),
                "logical_table_id": plan.get("logical_table_id"),
                "table_ref": table_ref,
                "row_count": plan.get("row_count"),
                "column_count": plan.get("column_count"),
                "window_count": len(plan.get("windows") or []),
                "candidate_count": plan.get("candidate_count"),
                "exactly_once_candidate_ownership": True,
                "column_split_performed": False,
                "silent_truncation_performed": False,
            },
        )
        refs.extend([ledger_ref, plan_ref])
        primary, primary_refs = self._build_and_invoke_revision(
            store=store,
            context=context,
            retention_policy=retention_policy,
            document_ref=document_ref,
            pdf_bytes=pdf_bytes,
            pdf_sha256=pdf_sha256,
            table_bbox=table_bbox,
            classification=classification,
            ledger=ledger,
            plan=plan,
            dpi=self.config.primary_dpi,
            dpi_revision_reason=None,
        )
        refs.extend(primary_refs)
        repeatability = {
            "required": False,
            "passed": True,
            "ever_conflicted": False,
            "reason_codes": [],
        }
        if (
            self.config.repeat_structurally_valid_tables
            and _object(primary.get("structural_validation")).get("passed") is True
        ):
            repeatability, repeat_refs = self._repeat_revision(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_ref=document_ref,
                classification=classification,
                ledger=ledger,
                plan=plan,
                primary=primary,
            )
            refs.extend(repeat_refs)
        escalation = {}
        if dpi_escalation_reason and primary.get("materialization"):
            escalation, escalation_refs = self._build_and_invoke_revision(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_ref=document_ref,
                pdf_bytes=pdf_bytes,
                pdf_sha256=pdf_sha256,
                table_bbox=table_bbox,
                classification=classification,
                ledger=ledger,
                plan=plan,
                dpi=self.config.escalation_dpi,
                dpi_revision_reason=dpi_escalation_reason,
            )
            refs.extend(escalation_refs)
        return (
            {
                "table_ref": table_ref,
                "classification": classification,
                "deterministic": deterministic,
                "compact_ledger": ledger,
                "window_plan": plan,
                "primary": primary,
                "repeatability": repeatability,
                "escalation": escalation,
                "dpi_escalation_reason": dpi_escalation_reason,
                "artifact_refs": {
                    "compact_ledger": ledger_ref,
                    "window_plan": plan_ref,
                },
            },
            refs,
        )

    def _build_and_invoke_revision(
        self,
        *,
        store: SqliteArtifactStoreAdapter,
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
        document_ref: str,
        pdf_bytes: bytes,
        pdf_sha256: str,
        table_bbox: list[float],
        classification: dict[str, Any],
        ledger: dict[str, Any],
        plan: dict[str, Any],
        dpi: int,
        dpi_revision_reason: str | None,
    ) -> tuple[dict[str, Any], list[str]]:
        refs: list[str] = []
        packages = []
        png_by_package: dict[str, bytes] = {}
        for window in _dicts(plan.get("windows")):
            try:
                rendered = self.raster.render(
                    pdf_bytes=pdf_bytes,
                    pdf_sha256=pdf_sha256,
                    document_ref=document_ref,
                    page_number=int(ledger.get("page_number") or 0),
                    table_ref=str(ledger.get("table_ref") or ""),
                    table_bbox=list(window.get("crop_bbox") or table_bbox),
                    dpi=dpi,
                    escalation_reason=dpi_revision_reason,
                )
            except PdfTableRasterError as exc:
                return self._revision_failure(exc.code), refs
            crop_ref = self._put_private(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_id=document_ref,
                artifact_type="broker_reports_pdf_table_crop_v1",
                payload=rendered,
                validation_status="validated",
                safe_metadata={
                    key: rendered["manifest"].get(key)
                    for key in (
                        "schema_version",
                        "crop_id",
                        "table_ref",
                        "dpi",
                        "width",
                        "height",
                        "pixels",
                        "png_bytes",
                        "png_sha256",
                        "renderer",
                        "renderer_version",
                        "dpi_revision_reason",
                    )
                }
                | {
                    "window_id": window.get("window_id"),
                    "row_start": window.get("row_start"),
                    "row_end": window.get("row_end"),
                },
            )
            refs.append(crop_ref)
            try:
                evidence = self.windows.build_package(
                    compact_ledger=ledger,
                    plan=plan,
                    window=window,
                    crop_manifest=rendered["manifest"],
                    private_crop_artifact_ref=crop_ref,
                )
            except (PdfHybridWindowError, PdfHybridBudgetError) as exc:
                return self._revision_failure(exc.code, context_budget_passed=False), refs
            packages.append(evidence)
            png_by_package[evidence["package_id"]] = base64.b64decode(
                rendered["private_png_base64"]
            )
        revision, invoke_refs = self._invoke_packages(
            store=store,
            context=context,
            retention_policy=retention_policy,
            document_ref=document_ref,
            classification=classification,
            ledger=ledger,
            plan=plan,
            packages=packages,
            png_by_package=png_by_package,
            attempt_number=1,
            attempt_lineage_by_package={},
            dpi=dpi,
        )
        refs.extend(invoke_refs)
        revision["packages"] = packages
        revision["png_by_package"] = png_by_package
        revision["dpi"] = dpi
        return revision, refs

    def _invoke_packages(
        self,
        *,
        store: SqliteArtifactStoreAdapter,
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
        document_ref: str,
        classification: dict[str, Any],
        ledger: dict[str, Any],
        plan: dict[str, Any],
        packages: list[dict[str, Any]],
        png_by_package: dict[str, bytes],
        attempt_number: int,
        attempt_lineage_by_package: dict[str, list[str]],
        dpi: int,
    ) -> tuple[dict[str, Any], list[str]]:
        refs: list[str] = []
        if self.provider is None:
            return self._revision_failure("pdf_hybrid_provider_not_configured"), refs
        bindings = []
        attempts = []
        calibrations = []
        for evidence in packages:
            package_id = str(evidence.get("package_id") or "")
            png = png_by_package[package_id]
            accounting = copy.deepcopy(evidence.get("component_accounting") or {})
            try:
                counted = self.provider.count_tokens(
                    evidence_package=evidence,
                    png_bytes=png,
                )
                accounting = self.budget.apply_provider_count(
                    accounting,
                    counted_input_tokens=int(counted["total_tokens"]),
                    modality_token_counts=counted.get("prompt_tokens_details"),
                )
                self.budget.require_provider_count(accounting)
            except (PdfHybridProviderError, PdfHybridBudgetError) as exc:
                evidence_ref = self._persist_evidence(
                    store=store,
                    context=context,
                    retention_policy=retention_policy,
                    document_ref=document_ref,
                    evidence=evidence,
                )
                refs.append(evidence_ref)
                return (
                    self._revision_failure(
                        exc.code,
                        context_budget_passed=False,
                        packages=packages,
                    ),
                    refs,
                )
            try:
                provider_result = self.provider.invoke(
                    evidence_package=evidence,
                    png_bytes=png,
                    attempt_number=attempt_number,
                    attempt_lineage=attempt_lineage_by_package.get(package_id, []),
                )
            except PdfHybridProviderError as exc:
                return self._revision_failure(exc.code, packages=packages), refs
            attempt = provider_result["attempt"]
            actual = _object(attempt.get("usage")).get("input_tokens")
            calibration = self.budget.reconcile_actual(
                accounting,
                actual_input_tokens=actual if isinstance(actual, int) else None,
            )
            calibration["count_tokens_request_hash"] = counted.get("request_hash")
            calibration["count_tokens_response_hash"] = counted.get("response_hash")
            calibration["package_id"] = package_id
            calibration["attempt_number"] = attempt_number
            calibration["dpi"] = dpi
            token_ref = self._put_private(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_id=document_ref,
                artifact_type="broker_reports_pdf_hybrid_provider_token_count_v2",
                payload=calibration,
                validation_status=(
                    "validated"
                    if calibration.get("estimator_calibration_passed")
                    else "blocked"
                ),
                safe_metadata=copy.deepcopy(calibration),
            )
            refs.append(token_ref)
            raw_ref = self._put_private(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_id=document_ref,
                artifact_type="broker_reports_pdf_hybrid_raw_response_v1",
                payload=provider_result["raw_private_response"],
                validation_status="pending",
                safe_metadata={
                    "response_bytes": provider_result["response_bytes"],
                    "response_hash": provider_result["response_hash"],
                    "attempt_number": attempt_number,
                    "package_id": package_id,
                    "window_id": _object(evidence.get("window")).get("window_id"),
                },
            )
            refs.append(raw_ref)
            attempt["raw_private_response_ref"] = raw_ref
            attempt["provider_token_calibration_ref"] = token_ref
            attempt["component_profile"] = calibration
            attempt_ref = self._put_private(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_id=document_ref,
                artifact_type="broker_reports_pdf_provider_attempt_v1",
                payload=attempt,
                validation_status=(
                    "validated" if attempt.get("validation_result") == "passed" else "blocked"
                ),
                safe_metadata=_safe_attempt(attempt, evidence, calibration),
            )
            refs.append(attempt_ref)
            evidence_ref = self._persist_evidence(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_ref=document_ref,
                evidence=evidence,
            )
            refs.append(evidence_ref)
            binding = provider_result.get("binding_output")
            if not isinstance(binding, dict):
                return (
                    self._revision_failure(
                        "pdf_hybrid_provider_binding_unavailable",
                        packages=packages,
                        attempts=[*attempts, attempt],
                        calibrations=[*calibrations, calibration],
                    ),
                    refs,
                )
            binding_ref = self._put_private(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_id=document_ref,
                artifact_type="broker_reports_pdf_hybrid_binding_output_v1",
                payload=binding,
                validation_status="validated",
                safe_metadata={
                    "schema_version": binding.get("schema_version"),
                    "package_id": binding.get("package_id"),
                    "decision": binding.get("decision"),
                    "row_count": binding.get("row_count"),
                    "column_count": binding.get("column_count"),
                    "binding_output_hash": sha256_json(binding),
                    "attempt_number": attempt_number,
                },
            )
            refs.append(binding_ref)
            bindings.append(binding)
            attempts.append(attempt)
            calibrations.append(calibration)
            if binding.get("decision") != "bound":
                return (
                    {
                        **self._revision_failure(
                            "pdf_hybrid_window_binding_not_bound",
                            packages=packages,
                            attempts=attempts,
                            calibrations=calibrations,
                        ),
                        "binding_status": binding.get("decision"),
                    },
                    refs,
                )
        try:
            logical_evidence, joined_binding = self.windows.join(
                compact_ledger=ledger,
                plan=plan,
                packages=packages,
                bindings=bindings,
            )
            materialization = self.materializer.materialize(
                evidence_package=logical_evidence,
                binding_output=joined_binding,
            )
            structural = self.structure.validate_placement(
                compact_ledger=ledger,
                materialization=materialization,
            )
            validation = self.validator.validate(
                evidence_package=logical_evidence,
                binding_output=joined_binding,
                materialization=materialization,
                classification=classification,
                independent_structural_validation=structural,
            )
        except (PdfHybridWindowError, PdfHybridMaterializationError) as exc:
            return (
                self._revision_failure(
                    exc.code,
                    packages=packages,
                    attempts=attempts,
                    calibrations=calibrations,
                ),
                refs,
            )
        material_ref = self._put_private(
            store=store,
            context=context,
            retention_policy=retention_policy,
            document_id=document_ref,
            artifact_type="broker_reports_pdf_table_materialization_result_v1",
            payload=materialization,
            validation_status="validated",
            safe_metadata=_safe_materialization(materialization, attempt_number, dpi),
        )
        structure_ref = self._put_private(
            store=store,
            context=context,
            retention_policy=retention_policy,
            document_id=document_ref,
            artifact_type="broker_reports_pdf_hybrid_structural_placement_validation_v2",
            payload=structural,
            validation_status="validated" if structural["passed"] else "blocked",
            safe_metadata={
                key: copy.deepcopy(structural.get(key))
                for key in (
                    "schema_version",
                    "validation_id",
                    "table_ref",
                    "passed",
                    "reason_codes",
                    "metrics",
                    "source_authenticity_implied",
                    "independently_checkable",
                    "authoritative",
                )
            },
        )
        validation_ref = self._put_private(
            store=store,
            context=context,
            retention_policy=retention_policy,
            document_id=document_ref,
            artifact_type="broker_reports_pdf_table_validation_v1",
            payload=validation,
            validation_status=(
                "validated" if validation["aggregate_result"] == "accepted_shadow" else "blocked"
            ),
            safe_metadata={
                "schema_version": validation.get("schema_version"),
                "aggregate_result": validation.get("aggregate_result"),
                "reason_codes": validation.get("reason_codes"),
                "metrics": validation.get("metrics"),
                "source_authenticity_validated": validation.get(
                    "source_authenticity_validated"
                ),
                "structural_placement_validated": validation.get(
                    "structural_placement_validated"
                ),
                "authoritative": False,
            },
        )
        refs.extend([material_ref, structure_ref, validation_ref])
        return (
            {
                "status": "completed",
                "context_budget_passed": True,
                "provider_passed": True,
                "binding_status": "bound",
                "reason_codes": sorted(
                    set(structural.get("reason_codes") or [])
                    | set(validation.get("reason_codes") or [])
                ),
                "packages": packages,
                "bindings": bindings,
                "attempts": attempts,
                "calibrations": calibrations,
                "logical_evidence": logical_evidence,
                "joined_binding": joined_binding,
                "materialization": materialization,
                "structural_validation": structural,
                "full_grid_validation": validation,
                "artifact_refs": {
                    "materialization": material_ref,
                    "structural_validation": structure_ref,
                    "full_grid_validation": validation_ref,
                },
            },
            refs,
        )

    def _repeat_revision(
        self,
        *,
        store: SqliteArtifactStoreAdapter,
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
        document_ref: str,
        classification: dict[str, Any],
        ledger: dict[str, Any],
        plan: dict[str, Any],
        primary: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str]]:
        packages = list(primary.get("packages") or [])
        attempts = list(primary.get("attempts") or [])
        lineage = {
            str(package.get("package_id") or ""): [
                str(attempt.get("attempt_id") or "")
            ]
            for package, attempt in zip(packages, attempts)
        }
        provider_config_hash = sha256_json(asdict(self.provider.config))
        task_key = self.reliability.task_key(
            evidence_package_hashes=[str(item.get("package_hash") or "") for item in packages],
            provider="google",
            model=self.provider.config.model_id,
            provider_config_hash=provider_config_hash,
            output_schema_hashes=[sha256_json(item.get("output_schema") or {}) for item in packages],
        )
        primary_checksum = _object(primary.get("materialization")).get("placement_checksum")
        self.reliability.record(
            task_key=task_key,
            placement_checksum=str(primary_checksum or ""),
            attempt_number=1,
            evidence_revision=f"dpi-{primary.get('dpi') or 150}",
        )
        repeated, refs = self._invoke_packages(
            store=store,
            context=context,
            retention_policy=retention_policy,
            document_ref=document_ref,
            classification=classification,
            ledger=ledger,
            plan=plan,
            packages=packages,
            png_by_package=dict(primary.get("png_by_package") or {}),
            attempt_number=2,
            attempt_lineage_by_package=lineage,
            dpi=int(primary.get("dpi") or 150),
        )
        repeated_checksum = _object(repeated.get("materialization")).get(
            "placement_checksum"
        )
        if repeated_checksum:
            self.reliability.record(
                task_key=task_key,
                placement_checksum=str(repeated_checksum),
                attempt_number=2,
                evidence_revision=f"dpi-{primary.get('dpi') or 150}",
            )
        result = self.reliability.result(task_key, required=True)
        result["task_key"] = task_key
        result["primary_placement_checksum"] = primary_checksum
        result["repeat_placement_checksum"] = repeated_checksum
        result["repeat_revision"] = repeated
        return result, refs

    @staticmethod
    def _revision_failure(
        code: str,
        *,
        context_budget_passed: bool = True,
        packages: list[dict[str, Any]] | None = None,
        attempts: list[dict[str, Any]] | None = None,
        calibrations: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {
            "status": "blocked",
            "context_budget_passed": context_budget_passed,
            "provider_passed": False,
            "binding_status": None,
            "reason_codes": [code],
            "packages": packages or [],
            "attempts": attempts or [],
            "calibrations": calibrations or [],
        }

    @staticmethod
    def _failure_state(
        *,
        table_ref: str,
        classification: dict[str, Any],
        deterministic: dict[str, Any],
        code: str,
    ) -> dict[str, Any]:
        return {
            "table_ref": table_ref,
            "classification": classification,
            "deterministic": deterministic,
            "primary": PdfHybridReliabilityShadowRuntime._revision_failure(code),
            "repeatability": {
                "required": False,
                "passed": True,
                "ever_conflicted": False,
                "reason_codes": [],
            },
        }

    @staticmethod
    def _summary(
        states: dict[str, dict[str, Any]],
        arbitrations: list[dict[str, Any]],
        repeatability_ledger_ref: str,
    ) -> dict[str, Any]:
        packages = [
            package
            for state in states.values()
            for package in _object(state.get("primary")).get("packages") or []
        ]
        calibrations = [
            item
            for state in states.values()
            for item in _object(state.get("primary")).get("calibrations") or []
        ]
        ledger_candidates = [
            int(_object(state.get("window_plan")).get("candidate_count") or 0)
            for state in states.values()
        ]
        max_window_candidates = max(
            (
                int(_object(package.get("component_accounting")).get("candidate_count") or 0)
                for package in packages
            ),
            default=0,
        )
        result = {
            "schema_version": PDF_HYBRID_RELIABILITY_SUMMARY_SCHEMA,
            "tables_total": len(states),
            "terminal_outcomes": _counts(
                str(item.get("terminal_status") or "") for item in arbitrations
            ),
            "table_results": [
                {
                    "table_ref": item.get("table_ref"),
                    "terminal_status": item.get("terminal_status"),
                    "reason_codes": item.get("reason_codes"),
                    "arbitration_checksum": item.get("arbitration_checksum"),
                }
                for item in arbitrations
            ],
            "context": {
                "logical_candidates_total": sum(ledger_candidates),
                "model_packages": len(packages),
                "maximum_candidates_per_model_package": max_window_candidates,
                "maximum_model_facing_text_bytes": max(
                    (
                        int(_object(package.get("component_accounting")).get("model_facing_text_bytes") or 0)
                        for package in packages
                    ),
                    default=0,
                ),
                "maximum_provider_counted_input_tokens": max(
                    (int(item.get("provider_counted_input_tokens") or 0) for item in calibrations),
                    default=0,
                ),
                "maximum_provider_actual_input_tokens": max(
                    (int(item.get("provider_actual_input_tokens") or 0) for item in calibrations),
                    default=0,
                ),
                "maximum_counted_to_actual_error_ratio": max(
                    (float(item.get("counted_to_actual_error_ratio") or 0) for item in calibrations),
                    default=0,
                ),
                "all_provider_counts_within_guard": all(
                    item.get("provider_counted_budget_passed") is True for item in calibrations
                )
                if calibrations
                else False,
                "all_estimator_calibrations_passed": all(
                    item.get("estimator_calibration_passed") is True for item in calibrations
                )
                if calibrations
                else False,
            },
            "repeatability_ledger_ref": repeatability_ledger_ref,
            "authority_state": "non_authoritative",
            "production_ready": False,
            "production_gate2_selection_changed": False,
            "private_shadow_artifacts_only": True,
            "customer_values_included": False,
            "crop_bytes_included": False,
            "raw_provider_response_included": False,
            "private_paths_included": False,
            "ocr_used": False,
            "knowledge_rag_used": False,
        }
        result["summary_checksum"] = sha256_json(result)
        return result

    def _persist_evidence(
        self,
        *,
        store: SqliteArtifactStoreAdapter,
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
        document_ref: str,
        evidence: dict[str, Any],
    ) -> str:
        return self._put_private(
            store=store,
            context=context,
            retention_policy=retention_policy,
            document_id=document_ref,
            artifact_type="broker_reports_pdf_hybrid_window_evidence_v2",
            payload=evidence,
            validation_status="validated",
            safe_metadata={
                "schema_version": evidence.get("schema_version"),
                "package_id": evidence.get("package_id"),
                "logical_table_id": evidence.get("logical_table_id"),
                "table_ref": evidence.get("table_ref"),
                "window_id": _object(evidence.get("window")).get("window_id"),
                "row_start": _object(evidence.get("window")).get("row_start"),
                "row_end": _object(evidence.get("window")).get("row_end"),
                "package_hash": evidence.get("package_hash"),
                **copy.deepcopy(evidence.get("component_accounting") or {}),
            },
        )

    @staticmethod
    def _put_private(
        *,
        store: SqliteArtifactStoreAdapter,
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
        document_id: str | None,
        artifact_type: str,
        payload: Any,
        validation_status: str,
        safe_metadata: dict[str, Any],
    ) -> str:
        record = _record(
            context=context,
            retention_policy=retention_policy,
            document_id=document_id,
            artifact_type=artifact_type,
            visibility="private_case",
            storage_backend="project_artifact_payload",
            validation_status=validation_status,
            payload=payload,
            safe_metadata=safe_metadata,
        )
        return store.put_record(record).artifact_id

    @staticmethod
    def _put_safe(
        *,
        store: SqliteArtifactStoreAdapter,
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
        artifact_type: str,
        payload: dict[str, Any],
    ) -> str:
        record = _record(
            context=context,
            retention_policy=retention_policy,
            document_id=None,
            artifact_type=artifact_type,
            visibility="safe_internal",
            storage_backend="project_artifact_store",
            validation_status="validated",
            payload=payload,
            safe_metadata=copy.deepcopy(payload),
        )
        return store.put_record(record).artifact_id


def _record(
    *,
    context: ArtifactAccessContext,
    retention_policy: RetentionPolicy,
    document_id: str | None,
    artifact_type: str,
    visibility: str,
    storage_backend: str,
    validation_status: str,
    payload: Any,
    safe_metadata: dict[str, Any],
) -> ArtifactRecord:
    return ArtifactRecord(
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
        access_policy={
            "requires_user_id": True,
            "requires_case_or_chat": True,
            "requires_workspace_model_id_when_present": bool(context.workspace_model_id),
            "requires_gate2_resolver": visibility == "private_case",
        },
        validation_status=validation_status,
        lifecycle_status=lifecycle_for_visibility(
            visibility=visibility, validation_status=validation_status
        ),
        payload_kind=(
            "json_file" if storage_backend == "project_artifact_payload" else "inline_json"
        ),
        payload=payload,
        safe_metadata=safe_metadata,
    )


def _safe_attempt(
    attempt: dict[str, Any],
    evidence: dict[str, Any],
    calibration: dict[str, Any],
) -> dict[str, Any]:
    return {
        key: copy.deepcopy(attempt.get(key))
        for key in (
            "same_evidence_task_id",
            "attempt_number",
            "attempt_lineage",
            "provider",
            "provider_profile",
            "model_requested",
            "model_resolved",
            "adapter_identity",
            "transport_identity",
            "duration_ms",
            "http_status",
            "usage",
            "finish_reason",
            "parse_result",
            "validation_result",
            "terminal_failure_class",
        )
    } | {
        "package_id": evidence.get("package_id"),
        "table_ref": evidence.get("table_ref"),
        "window_id": _object(evidence.get("window")).get("window_id"),
        "provider_counted_input_tokens": calibration.get(
            "provider_counted_input_tokens"
        ),
        "provider_actual_input_tokens": calibration.get(
            "provider_actual_input_tokens"
        ),
        "counted_to_actual_error_ratio": calibration.get(
            "counted_to_actual_error_ratio"
        ),
        "estimator_calibration_passed": calibration.get(
            "estimator_calibration_passed"
        ),
    }


def _safe_materialization(
    materialization: dict[str, Any], attempt_number: int, dpi: int
) -> dict[str, Any]:
    return {
        "schema_version": materialization.get("schema_version"),
        "materialization_checksum": materialization.get("materialization_checksum"),
        "placement_checksum": materialization.get("placement_checksum"),
        "row_count": materialization.get("row_count"),
        "column_count": materialization.get("column_count"),
        "grid_positions": materialization.get("grid_positions"),
        "selected_candidates": len(materialization.get("selected_candidate_ids") or []),
        "omitted_candidates": len(materialization.get("omitted_candidate_ids") or []),
        "explicit_empty_count": len(materialization.get("explicit_empty_positions") or []),
        "source_value_refs_count": len(materialization.get("source_value_refs") or []),
        "word_refs_count": len(materialization.get("word_refs") or []),
        "model_invented_values_total": materialization.get("model_invented_values_total"),
        "attempt_number": attempt_number,
        "dpi": dpi,
    }


def _safe_arbitration(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": value.get("schema_version"),
        "table_ref": value.get("table_ref"),
        "terminal_status": value.get("terminal_status"),
        "reason_codes": value.get("reason_codes"),
        "best_looking_result_selection_used": False,
        "silent_revision_selection_used": False,
        "authority_state": "non_authoritative",
        "production_gate2_selection_changed": False,
    }


def _page_number(pages: dict[str, dict[str, Any]], page_ref: str) -> int:
    return int(_object(pages.get(page_ref)).get("page_number") or 0)


def _counts(values: Any) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        result[str(value)] = result.get(str(value), 0) + 1
    return dict(sorted(result.items()))


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)] if isinstance(value, list) else []
