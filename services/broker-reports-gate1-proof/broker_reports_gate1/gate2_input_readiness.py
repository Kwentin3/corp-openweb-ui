from __future__ import annotations

import copy
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from .artifact_models import ArtifactAccessContext, ArtifactRecord, utc_now_iso
from .artifact_resolver import ArtifactResolver
from .artifact_store import ArtifactStoreError, SqliteArtifactStoreAdapter
from .contracts import stable_digest
from .full_source import SOURCE_UNIT_SCHEMA_VERSION, validate_full_source_unit
from .pdf_text_layer import validate_pdf_source_unit
from .pdf_layout_units import resolve_pdf_layout_unit_source_value
from .source_provenance import (
    NormalizedSliceProvenanceFactory,
    resolve_source_value,
    resolve_source_values,
    validate_normalized_slice_provenance,
)


FACTORY_REQUIRED = (
    "Gate2InputReadinessFactory.create is the only production Gate 2 dry-run package builder entrypoint"
)
FORBIDDEN = (
    "Control checks, smoke scripts and callers must not read ArtifactStore payloads or mint Gate 2 package refs directly"
)

INPUT_READINESS_SCHEMA_VERSION = "gate2_input_readiness_validation_v0"
DRY_RUN_PACKAGE_SCHEMA_VERSION = "broker_reports_source_fact_package_v0"
SAFE_REPORT_SCHEMA_VERSION = "gate2_input_readiness_safe_report_v0"

SOURCE_READY_BUCKETS = (
    "primary_source_extraction_refs",
    "secondary_source_extraction_refs",
    "duplicate_or_non_primary_refs",
)
CONTEXT_BUCKETS = (
    "cross_check_refs",
    "declaration_support_refs",
    "audit_reference_refs",
)

FORBIDDEN_PACKAGE_FIELD_NAMES = {
    "file_id",
    "openwebui_file_id",
    "filename",
    "raw_filename",
    "raw_file_id",
    "private_path",
    "path",
    "chat_text",
    "account_number",
    "personal_data",
    "secret",
    "env_value",
}


class Gate2InputReadinessError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Gate2InputReadinessConfig:
    allow_legacy_slice_provenance_upgrade: bool = True
    prefer_full_source_units: bool = True


@dataclass(frozen=True)
class Gate2InputReadinessResult:
    packages: list[dict[str, Any]]
    validation: dict[str, Any]
    safe_report: dict[str, Any]


class Gate2InputReadinessFactory:
    def __init__(
        self,
        *,
        store: SqliteArtifactStoreAdapter,
        config: Gate2InputReadinessConfig | None = None,
    ) -> None:
        self.store = store
        self.config = config or Gate2InputReadinessConfig()

    def create(self) -> "Gate2InputReadinessService":
        return Gate2InputReadinessService(
            store=self.store,
            resolver=ArtifactResolver(self.store),
            config=self.config,
        )


class Gate2InputReadinessService:
    def __init__(
        self,
        *,
        store: SqliteArtifactStoreAdapter,
        resolver: ArtifactResolver,
        config: Gate2InputReadinessConfig,
    ) -> None:
        self.store = store
        self.resolver = resolver
        self.config = config
        self.provenance = NormalizedSliceProvenanceFactory().create()

    def audit_and_build(
        self,
        *,
        domain_context_packet_ref: str,
        context: ArtifactAccessContext,
    ) -> Gate2InputReadinessResult:
        if not context.allow_private:
            raise Gate2InputReadinessError(
                "gate2_private_access_not_requested",
                "Gate 2 input readiness requires explicit private artifact access",
            )
        records_before = [
            record
            for record in self.store.list_by_run(context.normalization_run_id)
            if _record_matches_context_scope(record, context)
        ]
        dcp_resolved = self.resolver.resolve(domain_context_packet_ref, context)
        dcp_record = dcp_resolved["record"]
        if dcp_record.artifact_type != "domain_context_packet_v0":
            raise Gate2InputReadinessError(
                "gate2_domain_context_packet_type_mismatch",
                "Canonical Gate 2 input ref is not a domain context packet",
            )
        dcp = _object(dcp_resolved["payload"])
        if dcp.get("schema_version") != "domain_context_packet_v0":
            raise Gate2InputReadinessError(
                "gate2_domain_context_packet_schema_mismatch",
                "Domain context packet schema is not supported",
            )

        errors: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        resolved_scope_records: list[str] = [dcp_record.artifact_id]
        records = records_before
        duc = self._resolve_single_payload(
            records=records,
            artifact_type="document_usage_classification_v0",
            context=context,
            resolved_scope_records=resolved_scope_records,
            errors=errors,
        )
        issue_ledger = self._resolve_single_payload(
            records=records,
            artifact_type="gate1_issue_ledger_v0",
            context=context,
            resolved_scope_records=resolved_scope_records,
            errors=errors,
        )
        passports_by_document = self._resolve_passports(
            records=records,
            context=context,
            resolved_scope_records=resolved_scope_records,
            errors=errors,
        )
        handoff_audit = self._audit_handoff(
            records=records,
            dcp=dcp,
            context=context,
            resolved_scope_records=resolved_scope_records,
            errors=errors,
            warnings=warnings,
        )
        slices_by_document, slice_audit = self._resolve_private_slices(
            records=records,
            context=context,
            resolved_scope_records=resolved_scope_records,
            errors=errors,
        )

        next_stage_refs = _object(dcp.get("next_stage_refs"))
        source_ready_refs = _string_list(next_stage_refs.get("source_fact_ready_refs"))
        duc_ready_refs = sorted(
            str(entry.get("document_ref"))
            for entry in _entries(duc)
            if _object(entry.get("readiness_by_stage")).get("source_fact_extraction")
            in {"ready", "ready_with_issues"}
            and entry.get("document_ref")
        )
        if sorted(source_ready_refs) != duc_ready_refs:
            errors.append(
                _error(
                    "gate2_source_ready_refs_mismatch",
                    ",".join(sorted(set(source_ready_refs) ^ set(duc_ready_refs))),
                )
            )
        if _string_list(next_stage_refs.get("dropped_source_ready_refs")):
            errors.append(_error("gate2_dropped_source_ready_refs_not_empty", "dcp"))

        usage_by_document = {
            str(entry.get("document_ref")): entry
            for entry in _entries(duc)
            if entry.get("document_ref")
        }
        issues_by_id = {
            str(entry.get("issue_id")): entry
            for entry in _entries(issue_ledger)
            if entry.get("issue_id")
        }
        document_issue_refs = _object(dcp.get("document_issue_refs"))

        packages: list[dict[str, Any]] = []
        package_validations: list[dict[str, Any]] = []
        packageable_document_refs: set[str] = set()
        unpackageable_document_refs: set[str] = set()
        issue_scope_counts: Counter[str] = Counter()

        for document_ref in source_ready_refs:
            document_slices = slices_by_document.get(document_ref, [])
            if not document_slices:
                errors.append(_error("gate2_source_ready_document_has_no_private_slice", document_ref))
                unpackageable_document_refs.add(document_ref)
                continue
            bucket_roles = _document_bucket_roles(next_stage_refs, document_ref)
            document_package_validations = []
            for slice_record, private_slice, provenance_validation in document_slices:
                if provenance_validation.get("validator_status") != "passed":
                    errors.extend(copy.deepcopy(provenance_validation.get("errors") or []))
                    document_package_validations.append(
                        {
                            "validator_status": "failed",
                            "errors": copy.deepcopy(provenance_validation.get("errors") or []),
                        }
                    )
                    continue
                issue_context = _build_issue_context(
                    issue_refs=_string_list(document_issue_refs.get(document_ref)),
                    issues_by_id=issues_by_id,
                    private_slice=private_slice,
                    document_units_total=len(document_slices),
                    errors=errors,
                )
                issue_scope_counts.update(item["scope"] for item in issue_context)
                package = _build_dry_run_package(
                    dcp=dcp,
                    context=context,
                    document_ref=document_ref,
                    bucket_roles=bucket_roles,
                    usage_entry=usage_by_document.get(document_ref) or {},
                    passport=passports_by_document.get(document_ref),
                    slice_record=slice_record,
                    private_slice=private_slice,
                    issue_context=issue_context,
                )
                validation = validate_dry_run_source_fact_package(
                    package=package,
                    private_slice=private_slice,
                    allowed_document_issue_refs=_string_list(document_issue_refs.get(document_ref)),
                )
                packages.append(package)
                package_validations.append(validation)
                document_package_validations.append(validation)
            if document_package_validations and all(
                item.get("validator_status") == "passed"
                for item in document_package_validations
            ):
                packageable_document_refs.add(document_ref)
            else:
                unpackageable_document_refs.add(document_ref)

        if set(source_ready_refs) != packageable_document_refs | unpackageable_document_refs:
            errors.append(_error("gate2_source_ready_decision_coverage_incomplete", "dcp"))
        if unpackageable_document_refs:
            errors.append(
                _error(
                    "gate2_source_ready_documents_not_packageable",
                    ",".join(sorted(unpackageable_document_refs)),
                )
            )

        errors.extend(
            error
            for validation in package_validations
            for error in validation.get("errors") or []
        )
        records_after = [
            record
            for record in self.store.list_by_run(context.normalization_run_id)
            if _record_matches_context_scope(record, context)
        ]
        store_unchanged = [record.artifact_id for record in records_before] == [
            record.artifact_id for record in records_after
        ]
        if not store_unchanged:
            errors.append(_error("gate2_dry_run_mutated_artifactstore", context.normalization_run_id))
        knowledge_records = sum(
            1 for record in records_after if record.storage_backend == "openwebui_knowledge"
        )
        if knowledge_records:
            errors.append(_error("gate2_knowledge_storage_regression", str(knowledge_records)))

        error_codes = Counter(str(item.get("code") or "unknown") for item in errors)
        warning_codes = Counter(str(item.get("code") or "unknown") for item in warnings)
        validation_status = "passed" if not errors else "failed"
        validation = {
            "schema_version": INPUT_READINESS_SCHEMA_VERSION,
            "normalization_run_id": context.normalization_run_id,
            "domain_context_packet_ref": domain_context_packet_ref,
            "validator_status": validation_status,
            "passed": validation_status == "passed",
            "errors_count": len(errors),
            "errors": errors,
            "error_code_counts": dict(sorted(error_codes.items())),
            "warnings_count": len(warnings),
            "warnings": warnings,
            "warning_code_counts": dict(sorted(warning_codes.items())),
            "source_ready_refs_total": len(source_ready_refs),
            "packageable_document_refs": sorted(packageable_document_refs),
            "unpackageable_document_refs": sorted(unpackageable_document_refs),
            "packages_total": len(packages),
            "packages_passed": sum(
                1 for item in package_validations if item.get("validator_status") == "passed"
            ),
            "resolved_scope_records_total": len(set(resolved_scope_records)),
            "artifactstore_unchanged": store_unchanged,
            "knowledge_records": knowledge_records,
            "handoff_audit": handoff_audit,
            "slice_audit": slice_audit,
        }
        safe_report = _render_safe_report(
            validation=validation,
            packages=packages,
            source_ready_refs=source_ready_refs,
            next_stage_refs=next_stage_refs,
            issue_scope_counts=issue_scope_counts,
            vector_knowledge_guard=_object(dcp.get("vector_knowledge_guard")),
        )
        return Gate2InputReadinessResult(
            packages=packages,
            validation=validation,
            safe_report=safe_report,
        )

    def _resolve_single_payload(
        self,
        *,
        records: list[ArtifactRecord],
        artifact_type: str,
        context: ArtifactAccessContext,
        resolved_scope_records: list[str],
        errors: list[dict[str, str]],
    ) -> dict[str, Any]:
        candidates = [record for record in records if record.artifact_type == artifact_type]
        if len(candidates) != 1:
            errors.append(_error("gate2_required_artifact_count_invalid", artifact_type))
            return {}
        try:
            resolved = self.resolver.resolve(candidates[0].artifact_id, context)
        except ArtifactStoreError as exc:
            errors.append(_error(f"gate2_{exc.code}", artifact_type))
            return {}
        resolved_scope_records.append(candidates[0].artifact_id)
        return _object(resolved["payload"])

    def _resolve_passports(
        self,
        *,
        records: list[ArtifactRecord],
        context: ArtifactAccessContext,
        resolved_scope_records: list[str],
        errors: list[dict[str, str]],
    ) -> dict[str, dict[str, Any]]:
        result = {}
        for record in records:
            if record.artifact_type != "document_metadata_passport_v0":
                continue
            try:
                resolved = self.resolver.resolve(record.artifact_id, context)
            except ArtifactStoreError as exc:
                errors.append(_error(f"gate2_{exc.code}", record.document_id or "passport"))
                continue
            resolved_scope_records.append(record.artifact_id)
            if record.document_id:
                result[str(record.document_id)] = _object(resolved["payload"])
        return result

    def _resolve_private_slices(
        self,
        *,
        records: list[ArtifactRecord],
        context: ArtifactAccessContext,
        resolved_scope_records: list[str],
        errors: list[dict[str, str]],
    ) -> tuple[
        dict[str, list[tuple[ArtifactRecord, dict[str, Any], dict[str, Any]]]],
        dict[str, Any],
    ]:
        legacy_by_document: dict[
            str, list[tuple[ArtifactRecord, dict[str, Any], dict[str, Any]]]
        ] = defaultdict(list)
        full_units_by_document: dict[
            str, list[tuple[ArtifactRecord, dict[str, Any], dict[str, Any]]]
        ] = defaultdict(list)
        legacy_upgrade_total = 0
        table_total = 0
        text_total = 0
        full_source_units_total = 0
        parent_payloads_by_ref: dict[str, dict[str, Any]] = {}
        for record in records:
            if record.artifact_type != "private_normalized_source_payload_v0":
                continue
            try:
                resolved = self.resolver.resolve(record.artifact_id, context)
            except ArtifactStoreError as exc:
                errors.append(_error(f"gate2_{exc.code}", record.artifact_id))
                continue
            payload = _object(resolved.get("payload"))
            payload_ref = str(payload.get("source_payload_ref") or "")
            if payload_ref:
                parent_payloads_by_ref[payload_ref] = payload
                resolved_scope_records.append(record.artifact_id)
        for record in records:
            if record.artifact_type not in {
                "private_normalized_table_slice_v0",
                "private_normalized_text_slice_v0",
                SOURCE_UNIT_SCHEMA_VERSION,
            }:
                continue
            try:
                resolved = self.resolver.resolve(record.artifact_id, context)
            except ArtifactStoreError as exc:
                errors.append(_error(f"gate2_{exc.code}", record.artifact_id))
                continue
            payload = _object(resolved["payload"])
            document_id = str(record.document_id or payload.get("document_id") or "")
            checksum = str((record.source_file_ref or {}).get("file_hash_sha256") or "")
            if not document_id or not checksum:
                errors.append(_error("gate2_private_slice_scope_or_checksum_missing", record.artifact_id))
                continue
            if record.artifact_type == SOURCE_UNIT_SCHEMA_VERSION:
                provenance_validation = validate_full_source_unit(
                    unit=payload,
                    normalization_run_id=context.normalization_run_id,
                    document_id=document_id,
                    source_checksum_sha256=checksum,
                )
                if payload.get("pdf_unit_type"):
                    parent_payload = parent_payloads_by_ref.get(
                        str(payload.get("parent_payload_ref") or "")
                    )
                    pdf_errors = validate_pdf_source_unit(
                        payload,
                        parent_payload=parent_payload,
                        require_parent_payload=True,
                    )
                    if pdf_errors:
                        provenance_validation = {
                            **provenance_validation,
                            "validator_status": "failed",
                            "passed": False,
                            "errors": [
                                *copy.deepcopy(provenance_validation.get("errors") or []),
                                *pdf_errors,
                            ],
                        }
                        provenance_validation["errors_count"] = len(
                            provenance_validation["errors"]
                        )
                full_source_units_total += 1
            else:
                legacy = payload.get("source_unit_schema_version") != "source_unit_provenance_v0"
                if legacy:
                    if not self.config.allow_legacy_slice_provenance_upgrade:
                        errors.append(_error("gate2_legacy_slice_provenance_not_allowed", record.artifact_id))
                        continue
                    payload = self.provenance.enrich_slice(
                        normalization_run_id=context.normalization_run_id,
                        document_id=document_id,
                        source_checksum_sha256=checksum,
                        private_slice=payload,
                    )
                    legacy_upgrade_total += 1
                provenance_validation = validate_normalized_slice_provenance(
                    private_slice=payload,
                    normalization_run_id=context.normalization_run_id,
                    document_id=document_id,
                    source_checksum_sha256=checksum,
                )
            resolved_scope_records.append(record.artifact_id)
            target = (
                full_units_by_document
                if record.artifact_type == SOURCE_UNIT_SCHEMA_VERSION
                else legacy_by_document
            )
            target[document_id].append((record, payload, provenance_validation))
            if payload.get("slice_type") == "table_rows":
                table_total += 1
            elif payload.get("slice_type") == "text_excerpt":
                text_total += 1
        selected_by_document: dict[
            str, list[tuple[ArtifactRecord, dict[str, Any], dict[str, Any]]]
        ] = {}
        full_source_documents_total = 0
        legacy_fallback_documents_total = 0
        for document_id in sorted(set(legacy_by_document) | set(full_units_by_document)):
            full_units = full_units_by_document.get(document_id, [])
            if self.config.prefer_full_source_units and full_units:
                selected_by_document[document_id] = full_units
                full_source_documents_total += 1
            else:
                selected_by_document[document_id] = legacy_by_document.get(document_id, [])
                if selected_by_document[document_id]:
                    legacy_fallback_documents_total += 1
        return selected_by_document, {
            "private_slices_total": table_total + text_total,
            "table_slices_total": table_total,
            "text_slices_total": text_total,
            "full_source_units_total": full_source_units_total,
            "full_source_documents_total": full_source_documents_total,
            "legacy_fallback_documents_total": legacy_fallback_documents_total,
            "input_priority": "full_source_unit_then_legacy_preview",
            "legacy_provenance_upgrade_total": legacy_upgrade_total,
        }

    def _audit_handoff(
        self,
        *,
        records: list[ArtifactRecord],
        dcp: dict[str, Any],
        context: ArtifactAccessContext,
        resolved_scope_records: list[str],
        errors: list[dict[str, str]],
        warnings: list[dict[str, str]],
    ) -> dict[str, Any]:
        candidates = [record for record in records if record.artifact_type == "gate2_handoff_v0"]
        if len(candidates) != 1:
            errors.append(_error("gate2_handoff_artifact_count_invalid", str(len(candidates))))
            return {"status": "failed"}
        record = candidates[0]
        _validate_record_scope(record, context, errors)
        dcp_summary = _object(dcp.get("next_stage_ref_summary"))
        handoff_summary = _object(record.safe_metadata.get("next_stage_ref_summary"))
        if dcp_summary != handoff_summary:
            errors.append(_error("gate2_handoff_dcp_summary_mismatch", record.artifact_id))
        try:
            resolved = self.resolver.resolve(record.artifact_id, context)
        except ArtifactStoreError as exc:
            if (
                exc.code == "artifact_blocked"
                and _object(dcp.get("stage_readiness")).get("source_fact_extraction")
                in {"ready", "ready_with_issue_context"}
            ):
                warnings.append(
                    _error("gate2_legacy_handoff_compatibility_blocked", record.artifact_id)
                )
                return {
                    "status": "legacy_compatibility_blocked",
                    "resolver_readable": False,
                    "dcp_summary_matches_safe_metadata": dcp_summary == handoff_summary,
                }
            errors.append(_error(f"gate2_{exc.code}", record.artifact_id))
            return {"status": "failed", "resolver_readable": False}
        resolved_scope_records.append(record.artifact_id)
        payload = _object(resolved["payload"])
        if _object(payload.get("next_stage_refs")) != _object(dcp.get("next_stage_refs")):
            errors.append(_error("gate2_handoff_dcp_next_stage_refs_mismatch", record.artifact_id))
        return {
            "status": "passed",
            "resolver_readable": True,
            "dcp_summary_matches_safe_metadata": dcp_summary == handoff_summary,
            "next_stage_refs_match": _object(payload.get("next_stage_refs"))
            == _object(dcp.get("next_stage_refs")),
        }


def validate_dry_run_source_fact_package(
    *,
    package: dict[str, Any],
    private_slice: dict[str, Any],
    allowed_document_issue_refs: list[str],
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    package_id = str(package.get("package_id") or "")
    if package.get("schema_version") != DRY_RUN_PACKAGE_SCHEMA_VERSION:
        errors.append(_error("gate2_package_schema_mismatch", package_id))
    for field in (
        "package_id",
        "extraction_run_id",
        "normalization_run_id",
        "document_ref",
        "source_unit",
        "allowed_evidence_refs",
        "allowed_source_value_refs",
        "issue_context",
        "coverage_expectation",
        "privacy_policy",
        "created_at",
    ):
        if field not in package:
            errors.append(_error("gate2_package_required_field_missing", field))
    forbidden_paths = _find_forbidden_fields(package)
    errors.extend(_error("gate2_package_forbidden_field", path) for path in forbidden_paths)
    source_unit = _object(package.get("source_unit"))
    if source_unit.get("document_ref") != package.get("document_ref"):
        errors.append(_error("gate2_package_document_scope_mismatch", package_id))
    if source_unit.get("slice_ref") != private_slice.get("slice_id"):
        errors.append(_error("gate2_package_slice_scope_mismatch", package_id))

    unit_refs = _source_unit_refs(private_slice)
    allowed_evidence_refs = set(_string_list(package.get("allowed_evidence_refs")))
    allowed_source_value_refs = set(_string_list(package.get("allowed_source_value_refs")))
    generic_source_value_refs = set(_string_list(private_slice.get("source_value_refs")))
    layout_source_value_refs = set(
        _string_list(private_slice.get("pdf_layout_source_value_refs"))
    )
    expected_source_value_refs = generic_source_value_refs | layout_source_value_refs
    if not allowed_evidence_refs or not allowed_evidence_refs <= unit_refs:
        errors.append(_error("gate2_package_evidence_ref_out_of_scope", package_id))
    if allowed_source_value_refs != expected_source_value_refs:
        errors.append(_error("gate2_package_source_value_refs_mismatch", package_id))
    try:
        resolve_source_values(private_slice, sorted(generic_source_value_refs))
        for source_value_ref in sorted(layout_source_value_refs):
            resolve_pdf_layout_unit_source_value(private_slice, source_value_ref)
    except ValueError as exc:
        errors.append(_error(str(exc), package_id))

    issue_refs = {
        str(item.get("issue_ref"))
        for item in package.get("issue_context") or []
        if isinstance(item, dict) and item.get("issue_ref")
    }
    if issue_refs != set(_string_list(package.get("allowed_issue_refs"))):
        errors.append(_error("gate2_package_issue_ref_whitelist_mismatch", package_id))
    if not issue_refs <= set(allowed_document_issue_refs):
        errors.append(_error("gate2_package_issue_ref_out_of_scope", package_id))

    coverage_expectation = _object(package.get("coverage_expectation"))
    layout_unit = private_slice.get("pdf_unit_type") in {
        "pdf_line_cluster_unit",
        "pdf_table_candidate_unit",
    }
    coverage = _object(
        private_slice.get("pdf_layout_coverage")
        if layout_unit
        else private_slice.get("coverage")
    )
    if coverage_expectation.get("selected_source_refs") != coverage.get("selected_source_refs"):
        errors.append(_error("gate2_package_coverage_refs_mismatch", package_id))
    if coverage.get("all_selected_refs_accounted") is not True:
        errors.append(_error("gate2_package_source_unit_coverage_incomplete", package_id))
    source_input_mode = source_unit.get("source_input_mode")
    expansion_readiness = _object(package.get("expansion_readiness"))
    if source_input_mode == "full_source_unit":
        if source_unit.get("source_slice_truncated") is not False:
            errors.append(_error("gate2_full_source_unit_truncated", package_id))
        if source_unit.get("parent_remainder_status") != "not_applicable_parent_complete":
            errors.append(_error("gate2_full_source_unit_parent_remainder_pending", package_id))
        if expansion_readiness.get("limited_primary_expansion_ready") is not True:
            errors.append(_error("gate2_full_source_unit_expansion_readiness_false", package_id))
        if source_unit.get("pdf_unit_type"):
            if source_unit.get("text_layer_projection_status") != "complete":
                errors.append(_error("gate2_pdf_text_layer_projection_not_complete", package_id))
            if source_unit.get("ocr_vlm_used") is not False:
                errors.append(_error("gate2_pdf_ocr_guard_failed", package_id))
            if source_unit.get("page_rendering_used_for_extraction") is not False:
                errors.append(_error("gate2_pdf_rendering_guard_failed", package_id))
            if layout_unit:
                if source_unit.get("layout_projection_status") != "complete":
                    errors.append(_error("gate2_pdf_layout_projection_not_complete", package_id))
                if source_unit.get("pdf_layout_coverage") != private_slice.get(
                    "pdf_layout_coverage"
                ):
                    errors.append(_error("gate2_pdf_layout_coverage_not_preserved", package_id))
                if source_unit.get("pdf_layout_source_value_refs") != _string_list(
                    private_slice.get("pdf_layout_source_value_refs")
                ):
                    errors.append(_error("gate2_pdf_layout_value_refs_not_preserved", package_id))
                if private_slice.get("pdf_unit_type") == "pdf_table_candidate_unit":
                    for field in (
                        "table_candidate_ref",
                        "table_strategy_ref",
                        "geometry_confidence",
                        "table_bbox_ref",
                        "table_row_refs",
                        "table_cell_refs",
                        "table_contributing_word_refs",
                        "table_fallback_text_refs",
                        "table_fallback_source_value_refs",
                        "table_reconstruction_reason_codes",
                    ):
                        if source_unit.get(field) != private_slice.get(field):
                            errors.append(
                                _error("gate2_pdf_table_candidate_metadata_not_preserved", field)
                            )
                    if source_unit.get("table_reconstruction_status") != "candidate":
                        errors.append(_error("gate2_pdf_table_candidate_status_invalid", package_id))
    elif source_input_mode == "legacy_bounded_preview_fallback":
        if expansion_readiness.get("limited_primary_expansion_ready") is not False:
            errors.append(_error("gate2_legacy_preview_claims_expansion_readiness", package_id))
    else:
        errors.append(_error("gate2_source_input_mode_invalid", package_id))
    guards = _object(package.get("privacy_policy"))
    for key in (
        "raw_filenames_in_package",
        "raw_file_ids_in_package",
        "private_paths_in_package",
        "chat_text_in_package",
        "knowledge_rag_used",
        "vectorization_performed",
        "ocr_vlm_used",
        "page_rendering_used_for_extraction",
    ):
        if guards.get(key) is not False:
            errors.append(_error("gate2_package_privacy_guard_not_false", key))
    return {
        "schema_version": "broker_reports_source_fact_package_validation_v0",
        "package_id": package_id,
        "validator_status": "passed" if not errors else "failed",
        "passed": not errors,
        "errors_count": len(errors),
        "errors": errors,
        "source_value_refs_reproduced_total": len(allowed_source_value_refs) if not errors else 0,
        "coverage_selected_total": int(coverage.get("selected_total") or 0),
        "coverage_accounted_total": int(coverage.get("accounted_total") or 0),
    }


def _build_dry_run_package(
    *,
    dcp: dict[str, Any],
    context: ArtifactAccessContext,
    document_ref: str,
    bucket_roles: list[str],
    usage_entry: dict[str, Any],
    passport: dict[str, Any] | None,
    slice_record: ArtifactRecord,
    private_slice: dict[str, Any],
    issue_context: list[dict[str, Any]],
) -> dict[str, Any]:
    slice_ref = str(private_slice.get("slice_id") or "")
    full_source_input = private_slice.get("schema_version") == SOURCE_UNIT_SCHEMA_VERSION
    package_id = f"sfpkg_{stable_digest([context.normalization_run_id, document_ref, slice_ref], length=20)}"
    pdf_unit_type = private_slice.get("pdf_unit_type")
    layout_unit = pdf_unit_type in {
        "pdf_line_cluster_unit",
        "pdf_table_candidate_unit",
    }
    coverage = _object(
        private_slice.get("pdf_layout_coverage")
        if layout_unit
        else private_slice.get("coverage")
    )
    if pdf_unit_type == "pdf_line_cluster_unit":
        unit_kind = "pdf_line_cluster"
    elif pdf_unit_type == "pdf_table_candidate_unit":
        unit_kind = "pdf_table_candidate"
    elif pdf_unit_type == "pdf_page_text_unit":
        unit_kind = "pdf_page_text"
    else:
        unit_kind = (
            "table_row_window"
            if private_slice.get("slice_type") == "table_rows"
            else "text_slice"
        )
    unit_payload = {
        "cells": copy.deepcopy(private_slice.get("cells") or [])
    } if unit_kind == "table_row_window" else {
        "text": str(private_slice.get("text") or "")
    }
    source_unit = {
        "unit_id": private_slice.get("unit_ref")
        or private_slice.get("table_ref")
        or (_string_list(private_slice.get("text_segment_refs")) or [slice_ref])[0],
        "unit_kind": unit_kind,
        "private_slice_artifact_ref": slice_record.artifact_id,
        "private_source_unit_artifact_ref": (
            slice_record.artifact_id if full_source_input else None
        ),
        "source_input_mode": (
            "full_source_unit" if full_source_input else "legacy_bounded_preview_fallback"
        ),
        "slice_ref": slice_ref,
        "document_ref": document_ref,
        "source_checksum_ref": private_slice.get("source_checksum_ref"),
        "parser_ref": private_slice.get("parser_ref"),
        "table_ref": private_slice.get("table_ref"),
        "row_refs": _string_list(private_slice.get("row_refs")),
        "row_range_ref": private_slice.get("row_range_ref"),
        "cell_refs": _string_list(private_slice.get("cell_refs")),
        "cell_value_refs": _string_list(private_slice.get("cell_value_refs")),
        "text_segment_refs": _string_list(private_slice.get("text_segment_refs")),
        "section_refs": _string_list(private_slice.get("section_refs")),
        "page_refs": _string_list(private_slice.get("page_refs")),
        "page_range_ref": private_slice.get("page_range_ref"),
        "character_span_refs": _string_list(private_slice.get("character_span_refs")),
        "source_value_refs": _string_list(private_slice.get("source_value_refs")),
        "normalized_header_descriptors": copy.deepcopy(
            private_slice.get("normalized_header_descriptors") or []
        ),
        "row_provenance": copy.deepcopy(private_slice.get("row_provenance") or []),
        "cell_provenance": copy.deepcopy(private_slice.get("cell_provenance") or []),
        "segment_provenance": copy.deepcopy(private_slice.get("segment_provenance") or []),
        "safe_section_labels": _string_list(private_slice.get("safe_section_labels")),
        "source_value_index": copy.deepcopy(private_slice.get("source_value_index") or []),
        "source_value_projection_policy": private_slice.get("source_value_projection_policy"),
        "source_unit_schema_version": private_slice.get("source_unit_schema_version"),
        "normalized_source_projection": unit_payload,
        "model_source_projection": _build_model_source_projection(
            private_slice=private_slice,
            unit_kind=unit_kind,
        ),
        "slice_payload_checksum_ref": private_slice.get("slice_payload_checksum_ref"),
        "parent_source_payload_ref": private_slice.get("parent_payload_ref"),
        "payload_checksum_ref": private_slice.get("payload_checksum_ref"),
        "source_unit_checksum_ref": private_slice.get("source_unit_checksum_ref"),
        "coverage_ref": coverage.get("coverage_ref"),
        "coverage_scope": private_slice.get("coverage_scope")
        or "bounded_legacy_preview_projection",
        "source_slice_truncated": bool(
            private_slice.get("source_slice_truncated")
            if "source_slice_truncated" in private_slice
            else private_slice.get("truncated")
        ),
        "parent_source_slice_truncated": (
            private_slice.get("parent_source_slice_truncated")
            if full_source_input
            else bool(private_slice.get("truncated"))
        ),
        "parent_remainder_status": private_slice.get("parent_remainder_status")
        or (
            "not_applicable_parent_complete"
            if not private_slice.get("truncated")
            else "pending_gate1_reslice"
        ),
        "remaining_unit_refs": _string_list(private_slice.get("remaining_unit_refs")),
        "next_unit_refs": _string_list(private_slice.get("next_unit_refs")),
        "pdf_unit_type": private_slice.get("pdf_unit_type"),
        "pdf_projection_schema_version": private_slice.get(
            "pdf_projection_schema_version"
        ),
        "declared_page_refs": _string_list(private_slice.get("declared_page_refs")),
        "pdf_text_fragment_refs": _string_list(
            private_slice.get("pdf_text_fragment_refs")
        ),
        "layout_word_refs": _string_list(private_slice.get("layout_word_refs")),
        "layout_line_refs": _string_list(private_slice.get("layout_line_refs")),
        "layout_bbox_refs": _string_list(private_slice.get("layout_bbox_refs")),
        "layout_parser_ref": private_slice.get("layout_parser_ref"),
        "layout_parser_config_ref": private_slice.get("layout_parser_config_ref"),
        "layout_projection_status": private_slice.get("layout_projection_status"),
        "pdf_layout_coverage": copy.deepcopy(
            private_slice.get("pdf_layout_coverage") or {}
        ),
        "pdf_layout_source_value_refs": _string_list(
            private_slice.get("pdf_layout_source_value_refs")
        ),
        "pdf_layout_source_value_index": copy.deepcopy(
            private_slice.get("pdf_layout_source_value_index") or []
        ),
        "table_reconstruction_status": private_slice.get(
            "table_reconstruction_status"
        ),
        "table_candidate_ref": private_slice.get("table_candidate_ref"),
        "table_strategy_ref": private_slice.get("table_strategy_ref"),
        "geometry_confidence": private_slice.get("geometry_confidence"),
        "confidence_bucket": private_slice.get("confidence_bucket"),
        "table_bbox_ref": private_slice.get("table_bbox_ref"),
        "table_row_refs": _string_list(private_slice.get("table_row_refs")),
        "table_cell_refs": _string_list(private_slice.get("table_cell_refs")),
        "table_contributing_word_refs": _string_list(
            private_slice.get("table_contributing_word_refs")
        ),
        "table_fallback_text_refs": _string_list(
            private_slice.get("table_fallback_text_refs")
        ),
        "table_fallback_source_value_refs": _string_list(
            private_slice.get("table_fallback_source_value_refs")
        ),
        "table_reconstruction_reason_codes": _string_list(
            private_slice.get("table_reconstruction_reason_codes")
        ),
        "semantic_table_truth_claimed": private_slice.get(
            "semantic_table_truth_claimed", False
        ),
        "text_layer_projection_status": private_slice.get(
            "text_layer_projection_status"
        ),
        "visible_content_coverage_status": private_slice.get(
            "visible_content_coverage_status"
        ),
        "semantic_reconstruction_status": private_slice.get(
            "semantic_reconstruction_status"
        ),
        "ocr_vlm_used": private_slice.get("ocr_vlm_used", False),
        "page_rendering_used_for_extraction": private_slice.get(
            "page_rendering_used_for_extraction", False
        ),
    }
    passport_projection = {}
    if isinstance(passport, dict):
        passport_projection = {
            "passport_id": passport.get("passport_id"),
            "passport_status": passport.get("passport_status"),
            "validator_status": passport.get("validator_status"),
            "document_kind_candidate": passport.get("document_kind_candidate"),
            "content_kind": passport.get("content_kind"),
            "sections_detected": copy.deepcopy(passport.get("sections_detected") or []),
            "tables_detected": copy.deepcopy(passport.get("tables_detected") or []),
        }
    return {
        "schema_version": DRY_RUN_PACKAGE_SCHEMA_VERSION,
        "package_mode": (
            "gate2_full_source_unit_input_readiness_no_model_call"
            if full_source_input
            else "gate2_legacy_preview_bounded_proof_no_model_call"
        ),
        "package_id": package_id,
        "extraction_run_id": f"sf_dryrun_{stable_digest([context.normalization_run_id], length=20)}",
        "normalization_run_id": context.normalization_run_id,
        "case_id": context.case_id,
        "document_ref": document_ref,
        "source_bucket_roles": bucket_roles,
        "document_context": {
            "usage_modes": _string_list(usage_entry.get("usage_modes")),
            "readiness_by_stage": copy.deepcopy(usage_entry.get("readiness_by_stage") or {}),
            "passport": passport_projection,
        },
        "source_unit": source_unit,
        "allowed_evidence_refs": sorted(_source_unit_refs(private_slice)),
        "allowed_source_value_refs": [
            *_string_list(private_slice.get("source_value_refs")),
            *_string_list(private_slice.get("pdf_layout_source_value_refs")),
        ],
        "issue_context": issue_context,
        "allowed_issue_refs": sorted(
            str(item.get("issue_ref"))
            for item in issue_context
            if item.get("issue_ref")
        ),
        "forbidden_assumptions": _string_list(dcp.get("forbidden_assumptions")),
        "coverage_expectation": {
            "coverage_ref": coverage.get("coverage_ref"),
            "selected_source_refs": copy.deepcopy(coverage.get("selected_source_refs") or []),
            "ignorable_header_refs": copy.deepcopy(coverage.get("header_candidate_refs") or []),
            "ignorable_blank_refs": copy.deepcopy(coverage.get("blank_refs") or []),
            "layout_candidate_refs": copy.deepcopy(coverage.get("layout_candidate_refs") or []),
            "mandatory_no_fact_results": [
                *[
                    {"source_ref": ref, "reason_code": "header_row"}
                    for ref in coverage.get("header_candidate_refs") or []
                ],
                *[
                    {"source_ref": ref, "reason_code": "blank_row"}
                    for ref in coverage.get("blank_refs") or []
                ],
                *[
                    {"source_ref": ref, "reason_code": "layout_only"}
                    for ref in coverage.get("layout_candidate_refs") or []
                ],
            ],
            "fact_candidate_refs": copy.deepcopy(
                coverage.get("fact_candidate_refs")
                or coverage.get("text_candidate_refs")
                or coverage.get("owned_word_refs")
                or []
            ),
            "required_accounting_total": int(coverage.get("selected_total") or 0),
            "coverage_policy_id": "gate2_source_unit_coverage_v0",
            "source_input_mode": source_unit["source_input_mode"],
            "whole_parent_source_coverage_claimed": (
                full_source_input and not layout_unit
            ),
            "collective_parent_layout_coverage_ref": (
                coverage.get("coverage_ref") if layout_unit else None
            ),
        },
        "expansion_readiness": {
            "limited_primary_expansion_ready": (
                full_source_input
                and source_unit["source_slice_truncated"] is False
                and source_unit["parent_remainder_status"]
                == "not_applicable_parent_complete"
            ),
            "reason_code": (
                "complete_bounded_pdf_layout_unit"
                if layout_unit
                else "complete_full_source_unit"
                if full_source_input
                else "legacy_bounded_preview_fallback"
            ),
        },
        "prompt_contract": {
            "prompt_contract_id": "broker_reports_source_fact_prompt_v0",
            "model_call_performed": False,
        },
        "output_schema": {
            "output_schema_version": "broker_reports_source_facts_v0",
            "schema_validation_performed": False,
        },
        "privacy_policy": {
            "raw_filenames_in_package": False,
            "raw_file_ids_in_package": False,
            "private_paths_in_package": False,
            "chat_text_in_package": False,
            "knowledge_rag_used": False,
            "vectorization_performed": False,
            "ocr_vlm_used": False,
            "page_rendering_used_for_extraction": False,
        },
        "created_at": utc_now_iso(),
    }


def _build_model_source_projection(
    *,
    private_slice: dict[str, Any],
    unit_kind: str,
) -> dict[str, Any]:
    if unit_kind in {"pdf_line_cluster", "pdf_table_candidate"}:
        selected_refs = set(
            _string_list(
                _object(private_slice.get("pdf_layout_coverage")).get(
                    "selected_source_refs"
                )
            )
        )
        segments = []
        for item in _dict_list(private_slice.get("pdf_layout_source_value_index")):
            source_ref = str(item.get("source_object_ref") or "")
            source_value_ref = str(item.get("source_value_ref") or "")
            if source_ref not in selected_refs or not source_value_ref:
                continue
            segments.append(
                {
                    "text_segment_ref": source_ref,
                    "segment_kind": (
                        "pdf_layout_word"
                        if source_ref.startswith("pdfword_")
                        else "pdf_layout_line"
                    ),
                    "page_ref": (_string_list(private_slice.get("page_refs")) or [None])[0],
                    "source_value_ref": source_value_ref,
                    "value": resolve_pdf_layout_unit_source_value(
                        private_slice, source_value_ref
                    ),
                    "table_candidate_ref": private_slice.get("table_candidate_ref"),
                    "semantic_role": "not_claimed",
                }
            )
        return {
            "schema_version": "gate2_model_pdf_layout_projection_v0",
            "projection_kind": unit_kind,
            "segments": segments,
            "table_reconstruction_status": private_slice.get(
                "table_reconstruction_status"
            ),
            "semantic_table_truth_claimed": False,
        }
    if unit_kind == "table_row_window":
        cells = private_slice.get("cells")
        cells = cells if isinstance(cells, list) else []
        headers = {
            int(item.get("column_ordinal") or 0): str(
                item.get("normalized_label") or "unknown"
            )
            for item in private_slice.get("normalized_header_descriptors") or []
            if isinstance(item, dict) and item.get("column_ordinal")
        }
        cell_by_position = {
            (
                int(item.get("row_ordinal") or 0),
                int(item.get("column_ordinal") or 0),
            ): item
            for item in private_slice.get("cell_provenance") or []
            if isinstance(item, dict)
        }
        fact_candidate_refs = set(
            _string_list(
                _object(private_slice.get("coverage")).get("fact_candidate_refs")
            )
        )
        rows = []
        for row in private_slice.get("row_provenance") or []:
            if not isinstance(row, dict):
                continue
            if str(row.get("row_ref") or "") not in fact_candidate_refs:
                continue
            row_ordinal = int(row.get("row_ordinal") or 0)
            values = (
                cells[row_ordinal - 1]
                if row_ordinal > 0
                and row_ordinal <= len(cells)
                and isinstance(cells[row_ordinal - 1], list)
                else []
            )
            projected_cells = []
            for column_ordinal, value in enumerate(values, start=1):
                provenance = _object(
                    cell_by_position.get((row_ordinal, column_ordinal))
                )
                projected_cells.append(
                    {
                        "column_ordinal": column_ordinal,
                        "header_label": headers.get(column_ordinal, "unknown"),
                        "cell_ref": provenance.get("cell_ref"),
                        "source_value_ref": provenance.get("source_value_ref"),
                        "value": value,
                    }
                )
            rows.append(
                {
                    "row_ref": row.get("row_ref"),
                    "row_kind": row.get("row_kind"),
                    "fact_type_hint": _table_row_fact_type_hint(projected_cells),
                    "fact_type_hint_policy": "exact_visible_operation_label_v0",
                    "cells": projected_cells,
                }
            )
        return {
            "schema_version": "gate2_model_table_projection_v0",
            "rows": rows,
        }

    text = str(private_slice.get("text") or "")
    segments = []
    text_candidate_refs = set(
        _string_list(
            _object(private_slice.get("coverage")).get("text_candidate_refs")
        )
    )
    for item in private_slice.get("segment_provenance") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("text_segment_ref") or "") not in text_candidate_refs:
            continue
        start = int(item.get("character_start") or 0)
        end = int(item.get("character_end") or 0)
        segments.append(
            {
                "text_segment_ref": item.get("text_segment_ref"),
                "section_ref": item.get("section_ref"),
                "page_ref": item.get("page_ref"),
                "character_span_ref": item.get("character_span_ref"),
                "segment_kind": item.get("segment_kind"),
                "source_value_ref": item.get("source_value_ref"),
                "value": text[start:end],
            }
        )
    return {
        "schema_version": "gate2_model_text_projection_v0",
        "segments": segments,
    }


def _table_row_fact_type_hint(cells: list[dict[str, Any]]) -> str | None:
    operation = next(
        (
            str(item.get("value") or "").strip().lower().replace("-", "_").replace(" ", "_")
            for item in cells
            if item.get("header_label") == "operation"
        ),
        "",
    )
    mappings = {
        "trade_operation": {
            "buy",
            "sell",
            "redemption",
            "transfer",
            "corporate_action",
        },
        "income": {"dividend", "coupon", "interest", "sale_proceeds"},
        "withholding_tax": {"withholding", "withholding_tax", "tax_withheld"},
        "fee_commission": {
            "broker_commission",
            "exchange_fee",
            "custody_fee",
            "commission",
        },
        "cash_movement": {
            "cash_deposit",
            "cash_withdrawal",
            "cash_credit",
            "cash_debit",
            "deposit",
            "withdrawal",
        },
        "currency_fx": {"explicit_fx_rate", "fx_rate", "currency_conversion"},
        "position_snapshot": {"position_snapshot", "security_position", "cash_position"},
        "document_summary_evidence": {"source_summary", "document_summary"},
        "unknown_source_row": {
            "unclassified_source_row",
            "unknown",
            "unsupported",
            "ambiguous",
        },
    }
    return next(
        (fact_type for fact_type, labels in mappings.items() if operation in labels),
        None,
    )


def _build_issue_context(
    *,
    issue_refs: list[str],
    issues_by_id: dict[str, dict[str, Any]],
    private_slice: dict[str, Any],
    document_units_total: int,
    errors: list[dict[str, str]],
) -> list[dict[str, Any]]:
    result = []
    unit_refs = _source_unit_refs(private_slice)
    for issue_ref in issue_refs:
        issue = issues_by_id.get(issue_ref)
        if issue is None:
            errors.append(_error("gate2_document_issue_ref_not_found", issue_ref))
            continue
        evidence_refs = set(_string_list(issue.get("evidence_refs")))
        matching_evidence_refs = sorted(evidence_refs & unit_refs)
        evidence_binding = "direct_ref_match" if matching_evidence_refs else "document_scope"
        if (
            not matching_evidence_refs
            and evidence_refs
            and document_units_total == 1
            and private_slice.get("schema_version") == SOURCE_UNIT_SCHEMA_VERSION
            and private_slice.get("coverage_scope") == "complete_parser_logical_unit"
        ):
            coverage_ref = str(
                _object(private_slice.get("coverage")).get("coverage_ref") or ""
            )
            if coverage_ref:
                matching_evidence_refs = [coverage_ref]
                evidence_binding = "legacy_preview_contained_by_single_complete_source_unit"
        result.append(
            {
                "issue_ref": issue_ref,
                "issue_type": issue.get("issue_type"),
                "status": issue.get("status"),
                "scope": "source_unit" if matching_evidence_refs else "document",
                "impact": _issue_impact(issue),
                "criticality": issue.get("criticality"),
                "affected_stage": issue.get("affected_stage"),
                "blocked_stages": _string_list(issue.get("blocked_stages")),
                "stages_that_may_continue": _string_list(issue.get("stages_that_may_continue")),
                "evidence_refs": matching_evidence_refs,
                "evidence_binding": evidence_binding,
                "reason_codes": _string_list(issue.get("reason_codes")),
                "forbidden_assumption_codes": _string_list(
                    issue.get("forbidden_assumption_codes")
                ),
            }
        )
    return result


def _issue_impact(issue: dict[str, Any]) -> str:
    blocked = set(_string_list(issue.get("blocked_stages")))
    if "source_fact_extraction" in blocked:
        return "blocks_fact"
    if issue.get("affected_stage") == "source_fact_extraction":
        return "limits_confirmation"
    if "consolidation" in blocked:
        return "blocks_consolidation"
    if "declaration_support" in blocked:
        return "blocks_declaration"
    return "warning"


def _render_safe_report(
    *,
    validation: dict[str, Any],
    packages: list[dict[str, Any]],
    source_ready_refs: list[str],
    next_stage_refs: dict[str, Any],
    issue_scope_counts: Counter[str],
    vector_knowledge_guard: dict[str, Any],
) -> dict[str, Any]:
    unit_kind_counts = Counter(
        str(_object(package.get("source_unit")).get("unit_kind") or "unknown")
        for package in packages
    )
    source_input_mode_counts = Counter(
        str(_object(package.get("source_unit")).get("source_input_mode") or "unknown")
        for package in packages
    )
    expansion_ready_packages_total = sum(
        1
        for package in packages
        if _object(package.get("expansion_readiness")).get(
            "limited_primary_expansion_ready"
        )
        is True
    )
    source_unit_refs_total = sum(
        len(_string_list(package.get("allowed_evidence_refs"))) for package in packages
    )
    source_value_refs_total = sum(
        len(_string_list(package.get("allowed_source_value_refs"))) for package in packages
    )
    coverage_selected_total = sum(
        int(_object(package.get("coverage_expectation")).get("required_accounting_total") or 0)
        for package in packages
    )
    bucket_counts = {
        bucket: len(_string_list(next_stage_refs.get(bucket)))
        for bucket in (*SOURCE_READY_BUCKETS, *CONTEXT_BUCKETS)
    }
    no_source_ready_loss = (
        validation.get("source_ready_refs_total")
        == len(validation.get("packageable_document_refs") or [])
        and not validation.get("unpackageable_document_refs")
    )
    guards_passed = (
        vector_knowledge_guard.get("customer_docs_loaded_to_knowledge") is False
        and vector_knowledge_guard.get("vectorization_performed") is False
        and validation.get("knowledge_records") == 0
        and validation.get("artifactstore_unchanged") is True
    )
    status = "passed" if validation.get("validator_status") == "passed" and guards_passed else "partial"
    return {
        "schema_version": SAFE_REPORT_SCHEMA_VERSION,
        "status": status,
        "normalization_run_id": validation.get("normalization_run_id"),
        "source_ready_documents_total": len(source_ready_refs),
        "packageable_documents_total": len(validation.get("packageable_document_refs") or []),
        "unpackageable_document_refs": copy.deepcopy(
            validation.get("unpackageable_document_refs") or []
        ),
        "packages_total": len(packages),
        "packages_passed": validation.get("packages_passed"),
        "unit_kind_counts": dict(sorted(unit_kind_counts.items())),
        "source_input_mode_counts": dict(sorted(source_input_mode_counts.items())),
        "expansion_ready_packages_total": expansion_ready_packages_total,
        "legacy_preview_fallback_blocks_expansion": bool(
            source_input_mode_counts.get("legacy_bounded_preview_fallback")
        ),
        "bucket_counts": bucket_counts,
        "source_unit_refs_total": source_unit_refs_total,
        "source_value_refs_total": source_value_refs_total,
        "coverage_selected_total": coverage_selected_total,
        "row_segment_coverage_ready": validation.get("validator_status") == "passed",
        "issue_scope_counts": dict(sorted(issue_scope_counts.items())),
        "resolved_scope_records_total": validation.get("resolved_scope_records_total"),
        "handoff_audit": copy.deepcopy(validation.get("handoff_audit") or {}),
        "slice_audit": copy.deepcopy(validation.get("slice_audit") or {}),
        "no_source_ready_document_loss": no_source_ready_loss,
        "error_code_counts": copy.deepcopy(validation.get("error_code_counts") or {}),
        "warning_code_counts": copy.deepcopy(validation.get("warning_code_counts") or {}),
        "vector_knowledge_guard": {
            "customer_docs_loaded_to_knowledge": False,
            "vectorization_performed": False,
            "rag_used": False,
            "artifactstore_knowledge_records": validation.get("knowledge_records"),
            "artifactstore_unchanged": validation.get("artifactstore_unchanged"),
        },
        "safety_flags": {
            "source_fact_llm_call_performed": False,
            "source_fact_extraction_performed": False,
            "tax_calculation_performed": False,
            "declaration_generated": False,
            "xlsx_generated": False,
            "ocr_vlm_performed": False,
            "ordinary_upload_used": False,
            "knowledge_rag_used": False,
        },
    }


def _source_unit_refs(private_slice: dict[str, Any]) -> set[str]:
    refs = {
        str(private_slice.get("slice_id") or ""),
        str(private_slice.get("table_ref") or ""),
        str(private_slice.get("row_range_ref") or ""),
        str(private_slice.get("parser_ref") or ""),
        str(private_slice.get("source_checksum_ref") or ""),
        str(private_slice.get("slice_payload_checksum_ref") or ""),
        str(_object(private_slice.get("coverage")).get("coverage_ref") or ""),
        str(private_slice.get("page_range_ref") or ""),
    }
    for key in (
        "row_refs",
        "cell_refs",
        "cell_value_refs",
        "source_value_refs",
        "text_segment_refs",
        "section_refs",
        "page_refs",
        "character_span_refs",
        "safe_coverage_refs",
        "layout_word_refs",
        "layout_line_refs",
        "layout_bbox_refs",
        "pdf_layout_source_value_refs",
        "table_row_refs",
        "table_cell_refs",
        "table_contributing_word_refs",
        "table_fallback_text_refs",
        "table_fallback_source_value_refs",
    ):
        refs.update(_string_list(private_slice.get(key)))
    refs.update(
        {
            str(private_slice.get("layout_parser_ref") or ""),
            str(private_slice.get("layout_parser_config_ref") or ""),
            str(private_slice.get("pdf_layout_unit_checksum_ref") or ""),
            str(private_slice.get("table_candidate_ref") or ""),
            str(private_slice.get("table_strategy_ref") or ""),
            str(private_slice.get("table_bbox_ref") or ""),
            str(_object(private_slice.get("pdf_layout_coverage")).get("coverage_ref") or ""),
        }
    )
    return {ref for ref in refs if ref}


def _document_bucket_roles(next_stage_refs: dict[str, Any], document_ref: str) -> list[str]:
    return [
        bucket
        for bucket in (*SOURCE_READY_BUCKETS, *CONTEXT_BUCKETS)
        if document_ref in _string_list(next_stage_refs.get(bucket))
    ]


def _validate_record_scope(
    record: ArtifactRecord,
    context: ArtifactAccessContext,
    errors: list[dict[str, str]],
) -> None:
    if record.user_id != context.user_id or record.normalization_run_id != context.normalization_run_id:
        errors.append(_error("gate2_artifact_scope_mismatch", record.artifact_id))
    if record.case_id != context.case_id or record.chat_id != context.chat_id:
        errors.append(_error("gate2_artifact_case_chat_scope_mismatch", record.artifact_id))
    if record.workspace_model_id != context.workspace_model_id:
        errors.append(_error("gate2_artifact_workspace_scope_mismatch", record.artifact_id))


def _record_matches_context_scope(
    record: ArtifactRecord,
    context: ArtifactAccessContext,
) -> bool:
    return (
        record.user_id == context.user_id
        and record.normalization_run_id == context.normalization_run_id
        and record.case_id == context.case_id
        and record.chat_id == context.chat_id
        and record.workspace_model_id == context.workspace_model_id
    )


def _find_forbidden_fields(value: object, *, prefix: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{prefix}.{key}"
            if key in FORBIDDEN_PACKAGE_FIELD_NAMES:
                findings.append(child_path)
            findings.extend(_find_forbidden_fields(child, prefix=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_find_forbidden_fields(child, prefix=f"{prefix}[{index}]"))
    return findings


def _entries(value: dict[str, Any]) -> list[dict[str, Any]]:
    entries = value.get("entries") if isinstance(value, dict) else []
    return [item for item in entries or [] if isinstance(item, dict)]


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value or [] if item is not None and str(item)] if isinstance(value, list) else []


def _error(code: str, subject: object) -> dict[str, str]:
    return {"code": code, "subject": str(subject or "")}
