from __future__ import annotations

import base64
import copy
from dataclasses import dataclass
from typing import Any

from .artifact_lifecycle import lifecycle_for_visibility
from .artifact_models import ArtifactAccessContext, ArtifactRecord, RetentionPolicy
from .artifact_store import SqliteArtifactStoreAdapter, new_artifact_id
from .pdf_hybrid_contracts import (
    PDF_HYBRID_BINDING_OUTPUT_SCHEMA,
    PDF_HYBRID_PROPOSED_COMPACT_REVISION_SCHEMA,
    PDF_HYBRID_SHADOW_DECISION_SCHEMA,
    sha256_json,
)
from .pdf_hybrid_evidence import (
    PdfHybridEvidenceConfig,
    PdfHybridEvidenceError,
    PdfHybridEvidenceFactory,
)
from .pdf_hybrid_materialization import (
    PdfHybridMaterializationError,
    PdfHybridMaterializationFactory,
)
from .pdf_hybrid_provider import (
    GeminiHybridProviderAdapter,
    PdfHybridProviderError,
)
from .pdf_table_classification import (
    PdfTableClassifierConfig,
    PdfTableClassifierFactory,
)
from .pdf_table_raster import PdfTableRasterConfig, PdfTableRasterError, PdfTableRasterFactory
from .pdf_table_validation import PdfTableValidationFactory


PDF_HYBRID_SHADOW_SUMMARY_SCHEMA = "broker_reports_pdf_hybrid_shadow_summary_v1"
FACTORY_REQUIRED = "PdfHybridShadowFactory.create is the only hybrid shadow orchestration entrypoint"
FORBIDDEN = (
    "Pipes must not call hybrid stages directly, select hybrid output for Gate 2, delete artifacts, "
    "write Knowledge, retry invisibly, or fail over providers"
)


@dataclass(frozen=True)
class PdfHybridShadowConfig:
    enabled: bool = False
    primary_dpi: int = 150
    escalation_dpi: int = 200
    maximum_same_evidence_attempts: int = 2
    table_allowlist: tuple[str, ...] = ()


class PdfHybridShadowFactory:
    def __init__(
        self,
        config: PdfHybridShadowConfig | None = None,
        *,
        classifier_config: PdfTableClassifierConfig | None = None,
        raster_config: PdfTableRasterConfig | None = None,
        evidence_config: PdfHybridEvidenceConfig | None = None,
    ) -> None:
        self.config = config or PdfHybridShadowConfig()
        self.classifier_config = classifier_config
        self.raster_config = raster_config
        self.evidence_config = evidence_config

    def create(
        self,
        *,
        provider: GeminiHybridProviderAdapter | None,
    ) -> "PdfHybridShadowRuntime":
        classifier_config = self.classifier_config or PdfTableClassifierConfig(
            shadow_allowlist=self.config.table_allowlist
        )
        return PdfHybridShadowRuntime(
            config=self.config,
            classifier=PdfTableClassifierFactory(classifier_config).create(),
            raster=PdfTableRasterFactory(self.raster_config).create(),
            evidence=PdfHybridEvidenceFactory(self.evidence_config).create(),
            provider=provider,
        )


class PdfHybridShadowRuntime:
    def __init__(
        self,
        *,
        config: PdfHybridShadowConfig,
        classifier: Any,
        raster: Any,
        evidence: Any,
        provider: GeminiHybridProviderAdapter | None,
    ) -> None:
        self.config = config
        self.classifier = classifier
        self.raster = raster
        self.evidence = evidence
        self.provider = provider
        self.materializer = PdfHybridMaterializationFactory().create()
        self.validator = PdfTableValidationFactory().create()

    def run(
        self,
        *,
        store: SqliteArtifactStoreAdapter,
        package: dict[str, Any],
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
        pdf_bytes_by_sha256: dict[str, bytes],
        signal_overrides_by_table: dict[str, dict[str, Any]] | None = None,
        repeatability_table_refs: set[str] | None = None,
        dpi_escalation_reasons_by_table: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if not self.config.enabled:
            return {
                "enabled": False,
                "artifact_refs": [],
                "summary": None,
            }
        signal_overrides_by_table = signal_overrides_by_table or {}
        repeatability_table_refs = repeatability_table_refs or set()
        dpi_escalation_reasons_by_table = dpi_escalation_reasons_by_table or {}
        refs: list[str] = []
        decisions: list[dict[str, Any]] = []
        classifications: list[dict[str, Any]] = []
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
            pdf_projection = _object(source_payload.get("pdf_text_layer_projection"))
            pages = {
                str(item.get("page_ref") or ""): item
                for item in _dicts(pdf_projection.get("page_inventory"))
            }
            bboxes = {
                str(item.get("bbox_ref") or ""): list(item.get("bbox") or [])
                for item in _dicts(pdf_projection.get("bbox_inventory"))
            }
            for candidate in sorted(
                _dicts(pdf_projection.get("table_candidate_inventory")),
                key=lambda item: (
                    _page_number(pages, str(item.get("page_ref") or "")),
                    int(item.get("parser_ordinal") or 0),
                ),
            ):
                table_ref = str(candidate.get("table_candidate_ref") or "")
                page_ref = str(candidate.get("page_ref") or "")
                page_number = _page_number(pages, page_ref)
                projection = projections.get(table_ref, {})
                classification = self.classifier.classify(
                    document_ref=document_ref,
                    document_checksum=pdf_sha256,
                    page_ref=page_ref,
                    page_number=page_number,
                    table_candidate=candidate,
                    deterministic_projection=projection,
                    signals=signal_overrides_by_table.get(table_ref),
                )
                classifications.append(classification)
                classification_ref = self._put_private(
                    store=store,
                    context=context,
                    retention_policy=retention_policy,
                    document_id=document_ref,
                    artifact_type="broker_reports_pdf_table_classification_v1",
                    payload=classification,
                    validation_status="validated",
                    safe_metadata={
                        "schema_version": classification["schema_version"],
                        "classification_id": classification["classification_id"],
                        "table_ref": table_ref,
                        "selected_path": classification["selected_path"],
                        "reason_codes": classification["reason_codes"],
                        "authoritative": False,
                    },
                )
                refs.append(classification_ref)
                if classification["selected_path"] == "deterministic_simple":
                    decisions.append(
                        self._decision(
                            classification=classification,
                            current_projection=projection,
                            terminal_status="deterministic_control_no_vlm",
                            artifact_refs={"classification": classification_ref},
                        )
                    )
                    continue
                if not classification["selected_path"].startswith("hybrid"):
                    decisions.append(
                        self._decision(
                            classification=classification,
                            current_projection=projection,
                            terminal_status=classification["selected_path"],
                            artifact_refs={"classification": classification_ref},
                        )
                    )
                    continue
                if pdf_bytes is None:
                    decisions.append(
                        self._decision(
                            classification=classification,
                            current_projection=projection,
                            terminal_status="blocked_source_pdf_bytes_unavailable",
                            artifact_refs={"classification": classification_ref},
                        )
                    )
                    continue
                decision, new_refs = self._run_hybrid_table(
                    store=store,
                    context=context,
                    retention_policy=retention_policy,
                    document_ref=document_ref,
                    pdf_sha256=pdf_sha256,
                    pdf_bytes=pdf_bytes,
                    pdf_projection=pdf_projection,
                    table_candidate=candidate,
                    table_bbox=bboxes.get(str(candidate.get("bbox_ref") or ""), []),
                    page_ref=page_ref,
                    page_number=page_number,
                    classification=classification,
                    classification_ref=classification_ref,
                    current_projection=projection,
                    require_repeatability=table_ref in repeatability_table_refs,
                    dpi=self.config.primary_dpi,
                    dpi_revision_reason=None,
                )
                refs.extend(new_refs)
                escalation_reason = dpi_escalation_reasons_by_table.get(table_ref)
                if escalation_reason and decision.get("hybrid_status") in {
                    "accepted_shadow",
                    "human_review_required",
                }:
                    revision, revision_refs = self._run_hybrid_table(
                        store=store,
                        context=context,
                        retention_policy=retention_policy,
                        document_ref=document_ref,
                        pdf_sha256=pdf_sha256,
                        pdf_bytes=pdf_bytes,
                        pdf_projection=pdf_projection,
                        table_candidate=candidate,
                        table_bbox=bboxes.get(str(candidate.get("bbox_ref") or ""), []),
                        page_ref=page_ref,
                        page_number=page_number,
                        classification=classification,
                        classification_ref=classification_ref,
                        current_projection=projection,
                        require_repeatability=False,
                        dpi=self.config.escalation_dpi,
                        dpi_revision_reason=escalation_reason,
                    )
                    refs.extend(revision_refs)
                    decision["dpi_revision_comparison"] = {
                        "primary_dpi": self.config.primary_dpi,
                        "escalation_dpi": self.config.escalation_dpi,
                        "typed_reason": escalation_reason,
                        "primary_terminal_status": decision.get("hybrid_status"),
                        "escalation_terminal_status": revision.get("hybrid_status"),
                        "crop_identity_changed": (
                            decision.get("crop_sha256") != revision.get("crop_sha256")
                        ),
                        "package_identity_changed": (
                            decision.get("package_id") != revision.get("package_id")
                        ),
                        "materialization_checksum_equal": (
                            bool(decision.get("materialization_checksum"))
                            and decision.get("materialization_checksum")
                            == revision.get("materialization_checksum")
                        ),
                        "placement_checksum_equal": (
                            bool(decision.get("placement_checksum"))
                            and decision.get("placement_checksum")
                            == revision.get("placement_checksum")
                        ),
                        "revision_artifact_refs": copy.deepcopy(
                            revision.get("artifact_refs") or {}
                        ),
                    }
                    decision["decision_checksum"] = sha256_json(
                        {key: value for key, value in decision.items() if key != "decision_checksum"}
                    )
                decisions.append(decision)
        decision_refs = []
        for decision in decisions:
            ref = self._put_private(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_id=str(decision.get("document_ref") or ""),
                artifact_type="broker_reports_pdf_hybrid_shadow_decision_v1",
                payload=decision,
                validation_status=(
                    "validated"
                    if decision.get("hybrid_status") in {
                        "accepted_shadow",
                        "deterministic_control_no_vlm",
                    }
                    else "blocked"
                ),
                safe_metadata=_safe_decision(decision),
            )
            refs.append(ref)
            decision_refs.append(ref)
        proposed = {
            "schema_version": PDF_HYBRID_PROPOSED_COMPACT_REVISION_SCHEMA,
            "normalization_run_id": context.normalization_run_id,
            "base_compact_schema": "broker_reports_pdf_compact_canonical_document_v1",
            "base_artifact_mutated": False,
            "proposed_table_decisions": [
                {
                    "table_ref": item.get("table_ref"),
                    "current_status": item.get("current_status"),
                    "proposed_status": item.get("hybrid_status"),
                    "shadow_decision_checksum": item.get("decision_checksum"),
                }
                for item in decisions
            ],
            "authority_state": "non_authoritative",
            "production_ready": False,
            "production_gate2_selection_changed": False,
        }
        proposed["revision_checksum"] = sha256_json(proposed)
        proposed_ref = self._put_private(
            store=store,
            context=context,
            retention_policy=retention_policy,
            document_id=None,
            artifact_type="broker_reports_pdf_hybrid_proposed_compact_revision_v1",
            payload=proposed,
            validation_status="validated",
            safe_metadata={
                "schema_version": proposed["schema_version"],
                "tables_total": len(decisions),
                "base_artifact_mutated": False,
                "authority_state": "non_authoritative",
                "production_ready": False,
            },
        )
        refs.append(proposed_ref)
        summary = self._summary(classifications, decisions, proposed_ref)
        summary_record = _record(
            context=context,
            retention_policy=retention_policy,
            document_id=None,
            artifact_type="broker_reports_pdf_hybrid_shadow_summary_v1",
            visibility="safe_internal",
            storage_backend="project_artifact_store",
            validation_status="validated",
            payload=summary,
            safe_metadata=copy.deepcopy(summary),
        )
        summary_ref = store.put_record(summary_record).artifact_id
        refs.append(summary_ref)
        return {
            "enabled": True,
            "artifact_refs": refs,
            "decision_refs": decision_refs,
            "proposed_compact_revision_ref": proposed_ref,
            "summary_ref": summary_ref,
            "summary": summary,
        }

    def _run_hybrid_table(
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
        classification_ref: str,
        current_projection: dict[str, Any],
        require_repeatability: bool,
        dpi: int,
        dpi_revision_reason: str | None,
    ) -> tuple[dict[str, Any], list[str]]:
        table_ref = str(table_candidate.get("table_candidate_ref") or "")
        artifact_refs = {"classification": classification_ref}
        refs: list[str] = []
        try:
            rendered = self.raster.render(
                pdf_bytes=pdf_bytes,
                pdf_sha256=pdf_sha256,
                document_ref=document_ref,
                page_number=page_number,
                table_ref=table_ref,
                table_bbox=table_bbox,
                dpi=dpi,
                escalation_reason=dpi_revision_reason,
            )
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
                },
            )
            refs.append(crop_ref)
            artifact_refs["crop"] = crop_ref
            signals = _object(classification.get("measured_signals"))
            evidence = self.evidence.build(
                document_ref=document_ref,
                pdf_sha256=pdf_sha256,
                page_ref=page_ref,
                page_number=page_number,
                table_candidate=table_candidate,
                pdf_text_layer_projection=pdf_projection,
                crop_manifest=rendered["manifest"],
                private_crop_artifact_ref=crop_ref,
                row_count_hint=int(signals.get("row_count_hint") or 0),
                column_count_hint=int(signals.get("column_count_hint") or 0),
                header_depth_hint=int(signals.get("header_depth") or 0),
            )
            evidence_ref = self._put_private(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_id=document_ref,
                artifact_type="broker_reports_pdf_hybrid_evidence_package_v1",
                payload=evidence,
                validation_status="validated",
                safe_metadata={
                    "schema_version": evidence["schema_version"],
                    "package_id": evidence["package_id"],
                    "table_ref": table_ref,
                    "package_hash": evidence["package_hash"],
                    "candidate_dictionary_hash": evidence["candidate_dictionary_hash"],
                    **copy.deepcopy(evidence["component_accounting"]),
                },
            )
            refs.append(evidence_ref)
            artifact_refs["evidence_package"] = evidence_ref
        except (PdfTableRasterError, PdfHybridEvidenceError) as exc:
            terminal = (
                "blocked_context_budget"
                if "budget" in exc.code
                else "blocked_candidate_evidence"
            )
            failure_evidence = {
                "component_accounting": copy.deepcopy(
                    getattr(exc, "component_accounting", {})
                )
            }
            return (
                self._decision(
                    classification=classification,
                    current_projection=current_projection,
                    terminal_status=terminal,
                    artifact_refs=artifact_refs,
                    blocker_codes=[exc.code],
                    evidence=failure_evidence,
                ),
                refs,
            )
        if self.provider is None:
            return (
                self._decision(
                    classification=classification,
                    current_projection=current_projection,
                    terminal_status="provider_not_configured",
                    artifact_refs=artifact_refs,
                    evidence=evidence,
                ),
                refs,
            )
        png_bytes = base64.b64decode(rendered["private_png_base64"])
        lineage: list[str] = []
        provider_result = None
        for attempt_number in range(1, self.config.maximum_same_evidence_attempts + 1):
            try:
                provider_result = self.provider.invoke(
                    evidence_package=evidence,
                    png_bytes=png_bytes,
                    attempt_number=attempt_number,
                    attempt_lineage=lineage,
                )
            except PdfHybridProviderError as exc:
                return (
                    self._decision(
                        classification=classification,
                        current_projection=current_projection,
                        terminal_status="provider_failed",
                        artifact_refs=artifact_refs,
                        blocker_codes=[exc.code],
                    ),
                    refs,
                )
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
                },
            )
            refs.append(raw_ref)
            attempt = provider_result["attempt"]
            attempt["raw_private_response_ref"] = raw_ref
            input_tokens = _object(attempt.get("usage")).get("input_tokens")
            unique_bytes = int(
                evidence["component_accounting"].get(
                    "unique_visible_table_text_bytes"
                )
                or 0
            )
            component_profile = copy.deepcopy(evidence["component_accounting"])
            component_profile["provider_token_amplification_ratio"] = (
                round(int(input_tokens) / max(1, (unique_bytes + 3) // 4), 6)
                if isinstance(input_tokens, int)
                else None
            )
            evidence["component_accounting"][
                "provider_token_amplification_ratio"
            ] = component_profile["provider_token_amplification_ratio"]
            attempt["component_profile"] = component_profile
            attempt_ref = self._put_private(
                store=store,
                context=context,
                retention_policy=retention_policy,
                document_id=document_ref,
                artifact_type="broker_reports_pdf_provider_attempt_v1",
                payload=attempt,
                validation_status=(
                    "validated" if attempt["validation_result"] == "passed" else "blocked"
                ),
                safe_metadata={
                    key: copy.deepcopy(attempt.get(key))
                    for key in (
                        "same_evidence_task_id",
                        "attempt_number",
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
                }
                | {
                    "table_ref": table_ref,
                    "package_id": evidence["package_id"],
                }
                | component_profile,
            )
            refs.append(attempt_ref)
            lineage.append(attempt["attempt_id"])
            artifact_refs.setdefault("provider_attempts", []).append(attempt_ref)
            if attempt["validation_result"] == "passed":
                break
        binding = provider_result.get("binding_output") if provider_result else None
        if not isinstance(binding, dict):
            return (
                self._decision(
                    classification=classification,
                    current_projection=current_projection,
                    terminal_status="provider_failed",
                    artifact_refs=artifact_refs,
                    blocker_codes=["pdf_hybrid_no_valid_binding_output"],
                    evidence=evidence,
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
            },
        )
        refs.append(binding_ref)
        artifact_refs["binding_output"] = binding_ref
        if binding.get("decision") != "bound":
            terminal = (
                "structurally_ambiguous"
                if binding.get("decision") == "ambiguous"
                else "unsupported"
            )
            return (
                self._decision(
                    classification=classification,
                    current_projection=current_projection,
                    terminal_status=terminal,
                    artifact_refs=artifact_refs,
                    evidence=evidence,
                ),
                refs,
            )
        try:
            materialization = self.materializer.materialize(
                evidence_package=evidence,
                binding_output=binding,
            )
        except PdfHybridMaterializationError as exc:
            return (
                self._decision(
                    classification=classification,
                    current_projection=current_projection,
                    terminal_status="blocked_materialization",
                    artifact_refs=artifact_refs,
                    blocker_codes=[exc.code],
                    evidence=evidence,
                ),
                refs,
            )
        materialization_ref = self._put_private(
            store=store,
            context=context,
            retention_policy=retention_policy,
            document_id=document_ref,
            artifact_type="broker_reports_pdf_table_materialization_result_v1",
            payload=materialization,
            validation_status="validated",
            safe_metadata={
                "schema_version": materialization["schema_version"],
                "materialization_checksum": materialization["materialization_checksum"],
                "placement_checksum": materialization["placement_checksum"],
                "row_count": materialization["row_count"],
                "column_count": materialization["column_count"],
                "grid_positions": materialization["grid_positions"],
                "explicit_empty_count": len(materialization["explicit_empty_positions"]),
                "source_value_refs_count": len(materialization["source_value_refs"]),
                "word_refs_count": len(materialization["word_refs"]),
                "model_invented_values_total": 0,
            },
        )
        refs.append(materialization_ref)
        artifact_refs["materialization"] = materialization_ref
        repeated_checksum = materialization["materialization_checksum"]
        if require_repeatability:
            first_attempt = _object(provider_result.get("attempt"))
            if first_attempt.get("attempt_number") != 1:
                repeated_checksum = None
            else:
                repeat = self.provider.invoke(
                    evidence_package=evidence,
                    png_bytes=png_bytes,
                    attempt_number=2,
                    attempt_lineage=[str(first_attempt.get("attempt_id") or "")],
                )
                repeat_raw_ref = self._put_private(
                    store=store,
                    context=context,
                    retention_policy=retention_policy,
                    document_id=document_ref,
                    artifact_type="broker_reports_pdf_hybrid_raw_response_v1",
                    payload=repeat["raw_private_response"],
                    validation_status="pending",
                    safe_metadata={
                        "response_bytes": repeat["response_bytes"],
                        "response_hash": repeat["response_hash"],
                        "attempt_number": 2,
                        "repeatability_probe": True,
                    },
                )
                refs.append(repeat_raw_ref)
                repeat_attempt = repeat["attempt"]
                repeat_attempt["raw_private_response_ref"] = repeat_raw_ref
                repeat_input_tokens = _object(repeat_attempt.get("usage")).get(
                    "input_tokens"
                )
                repeat_component_profile = copy.deepcopy(
                    evidence["component_accounting"]
                )
                repeat_component_profile["provider_token_amplification_ratio"] = (
                    round(
                        int(repeat_input_tokens)
                        / max(1, (unique_bytes + 3) // 4),
                        6,
                    )
                    if isinstance(repeat_input_tokens, int)
                    else None
                )
                repeat_attempt["component_profile"] = repeat_component_profile
                repeat_attempt_ref = self._put_private(
                    store=store,
                    context=context,
                    retention_policy=retention_policy,
                    document_id=document_ref,
                    artifact_type="broker_reports_pdf_provider_attempt_v1",
                    payload=repeat_attempt,
                    validation_status=(
                        "validated"
                        if repeat_attempt["validation_result"] == "passed"
                        else "blocked"
                    ),
                    safe_metadata={
                        key: copy.deepcopy(repeat_attempt.get(key))
                        for key in (
                            "same_evidence_task_id",
                            "attempt_number",
                            "attempt_lineage",
                            "provider",
                            "provider_profile",
                            "model_requested",
                            "model_resolved",
                            "duration_ms",
                            "usage",
                            "finish_reason",
                            "parse_result",
                            "validation_result",
                            "terminal_failure_class",
                        )
                    }
                    | {
                        "repeatability_probe": True,
                        "table_ref": table_ref,
                        "package_id": evidence["package_id"],
                    }
                    | repeat_component_profile,
                )
                refs.append(repeat_attempt_ref)
                artifact_refs.setdefault("provider_attempts", []).append(
                    repeat_attempt_ref
                )
                repeat_binding = repeat.get("binding_output")
                if isinstance(repeat_binding, dict):
                    repeat_binding_ref = self._put_private(
                        store=store,
                        context=context,
                        retention_policy=retention_policy,
                        document_id=document_ref,
                        artifact_type="broker_reports_pdf_hybrid_binding_output_v1",
                        payload=repeat_binding,
                        validation_status=(
                            "validated"
                            if repeat_attempt["validation_result"] == "passed"
                            else "blocked"
                        ),
                        safe_metadata={
                            "binding_output_hash": sha256_json(repeat_binding),
                            "attempt_number": 2,
                            "repeatability_probe": True,
                        },
                    )
                    refs.append(repeat_binding_ref)
                    try:
                        repeated = self.materializer.materialize(
                            evidence_package=evidence,
                            binding_output=repeat_binding,
                        )
                        repeated_checksum = repeated["materialization_checksum"]
                        repeated_ref = self._put_private(
                            store=store,
                            context=context,
                            retention_policy=retention_policy,
                            document_id=document_ref,
                            artifact_type="broker_reports_pdf_table_materialization_result_v1",
                            payload=repeated,
                            validation_status="validated",
                            safe_metadata={
                                "materialization_checksum": repeated_checksum,
                                "placement_checksum": repeated["placement_checksum"],
                                "attempt_number": 2,
                                "repeatability_probe": True,
                            },
                        )
                        refs.append(repeated_ref)
                    except PdfHybridMaterializationError:
                        repeated_checksum = None
                else:
                    repeated_checksum = None
        validation = self.validator.validate(
            evidence_package=evidence,
            binding_output=binding,
            materialization=materialization,
            classification=classification,
            repeated_materialization_checksum=repeated_checksum,
            require_repeatability=require_repeatability,
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
                "schema_version": validation["schema_version"],
                "aggregate_result": validation["aggregate_result"],
                "reason_codes": validation["reason_codes"],
                "metrics": validation["metrics"],
                "source_authenticity_validated": validation[
                    "source_authenticity_validated"
                ],
                "structural_placement_validated": validation[
                    "structural_placement_validated"
                ],
                "repeatability_required": validation["repeatability_required"],
                "repeatability_match": validation["repeatability_match"],
                "authoritative": False,
            },
        )
        refs.append(validation_ref)
        artifact_refs["validation"] = validation_ref
        return (
            self._decision(
                classification=classification,
                current_projection=current_projection,
                terminal_status=validation["aggregate_result"],
                artifact_refs=artifact_refs,
                evidence=evidence,
                materialization=materialization,
                validation=validation,
            ),
            refs,
        )

    @staticmethod
    def _decision(
        *,
        classification: dict[str, Any],
        current_projection: dict[str, Any],
        terminal_status: str,
        artifact_refs: dict[str, Any],
        blocker_codes: list[str] | None = None,
        evidence: dict[str, Any] | None = None,
        materialization: dict[str, Any] | None = None,
        validation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        materialization = materialization or {}
        validation = validation or {}
        evidence = evidence or {}
        decision = {
            "schema_version": PDF_HYBRID_SHADOW_DECISION_SCHEMA,
            "document_ref": classification.get("document_ref"),
            "table_ref": classification.get("table_ref"),
            "classification_id": classification.get("classification_id"),
            "selected_path": classification.get("selected_path"),
            "current_status": (
                "accepted"
                if current_projection.get("projection_status") == "ready"
                else "blocked"
            ),
            "hybrid_status": terminal_status,
            "current_shape": {
                "rows": int(current_projection.get("row_count") or 0),
                "columns": int(current_projection.get("column_count") or 0),
            },
            "hybrid_shape": {
                "rows": int(materialization.get("row_count") or 0),
                "columns": int(materialization.get("column_count") or 0),
            },
            "accepted_cell_count": len(materialization.get("cells") or []),
            "explicit_empty_count": len(
                materialization.get("explicit_empty_positions") or []
            ),
            "source_value_refs_count": len(
                materialization.get("source_value_refs") or []
            ),
            "word_refs_count": len(materialization.get("word_refs") or []),
            "validation_result": validation.get("aggregate_result"),
            "repeatability_required": validation.get("repeatability_required", False),
            "repeatability_match": validation.get("repeatability_match"),
            "blocker_codes": sorted(set(blocker_codes or validation.get("reason_codes") or [])),
            "component_accounting": copy.deepcopy(
                evidence.get("component_accounting") or {}
            ),
            "package_id": evidence.get("package_id"),
            "crop_sha256": _object(evidence.get("crop_identity")).get("crop_sha256"),
            "materialization_checksum": materialization.get("materialization_checksum"),
            "placement_checksum": materialization.get("placement_checksum"),
            "artifact_refs": copy.deepcopy(artifact_refs),
            "authority_state": "non_authoritative",
            "production_ready": False,
            "production_gate2_selection_changed": False,
            "knowledge_rag_used": False,
            "vectorization_performed": False,
            "ocr_used": False,
        }
        decision["decision_checksum"] = sha256_json(decision)
        return decision

    @staticmethod
    def _summary(
        classifications: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
        proposed_ref: str,
    ) -> dict[str, Any]:
        largest = max(
            decisions,
            key=lambda item: int(
                _object(item.get("component_accounting")).get("model_facing_text_bytes")
                or 0
            ),
            default={},
        )
        return {
            "schema_version": PDF_HYBRID_SHADOW_SUMMARY_SCHEMA,
            "tables_classified": len(classifications),
            "classifier_paths": _counts(
                str(item.get("selected_path") or "") for item in classifications
            ),
            "terminal_outcomes": _counts(
                str(item.get("hybrid_status") or "") for item in decisions
            ),
            "provider_attempted_tables": sum(
                bool(_object(item.get("artifact_refs")).get("provider_attempts"))
                for item in decisions
            ),
            "accepted_shadow_tables": sum(
                item.get("hybrid_status") == "accepted_shadow" for item in decisions
            ),
            "largest_package": {
                "table_ref": largest.get("table_ref"),
                **copy.deepcopy(largest.get("component_accounting") or {}),
            },
            "proposed_compact_revision_ref": proposed_ref,
            "authority_state": "non_authoritative",
            "production_ready": False,
            "production_gate2_selection_changed": False,
            "customer_values_included": False,
            "crop_bytes_included": False,
            "raw_provider_response_included": False,
            "private_paths_included": False,
        }

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
    access_policy = {
        "requires_user_id": True,
        "requires_case_or_chat": True,
        "requires_workspace_model_id_when_present": bool(context.workspace_model_id),
        "requires_gate2_resolver": visibility == "private_case",
    }
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
        access_policy=access_policy,
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


def _safe_decision(decision: dict[str, Any]) -> dict[str, Any]:
    safe = {
        key: copy.deepcopy(decision.get(key))
        for key in (
            "schema_version",
            "table_ref",
            "selected_path",
            "current_status",
            "hybrid_status",
            "current_shape",
            "hybrid_shape",
            "accepted_cell_count",
            "explicit_empty_count",
            "source_value_refs_count",
            "word_refs_count",
            "validation_result",
            "repeatability_required",
            "repeatability_match",
            "blocker_codes",
            "component_accounting",
            "dpi_revision_comparison",
            "authority_state",
            "production_ready",
            "production_gate2_selection_changed",
        )
    }
    comparison = _object(safe.get("dpi_revision_comparison"))
    if comparison:
        safe["dpi_revision_comparison"] = {
            key: copy.deepcopy(comparison.get(key))
            for key in (
                "primary_dpi",
                "escalation_dpi",
                "typed_reason",
                "primary_terminal_status",
                "escalation_terminal_status",
                "crop_identity_changed",
                "package_identity_changed",
                "materialization_checksum_equal",
                "placement_checksum_equal",
            )
        }
    return safe


def _page_number(pages: dict[str, dict[str, Any]], page_ref: str) -> int:
    return int(_object(pages.get(page_ref)).get("page_number") or 0)


def _counts(values: Any) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        result[value] = result.get(value, 0) + 1
    return dict(sorted(result.items()))


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)] if isinstance(value, list) else []
