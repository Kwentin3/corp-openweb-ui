from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .artifact_lifecycle import lifecycle_for_visibility
from .artifact_models import ArtifactAccessContext, ArtifactRecord, ArtifactStorePort
from .artifact_resolver import ArtifactResolver
from .contracts import stable_digest
from .gate1_public_contracts import (
    CSV_SUPPORTED_PROFILE_ID,
    DOMAIN_CONTEXT_PACKET_SCHEMA_VERSION,
    ISSUE_LEDGER_SCHEMA_VERSION,
)
from .gate2_domain_contracts import (
    DOMAIN_RUN_SCHEMA_VERSION,
    DOMAIN_SOURCE_FACTS_SCHEMA_VERSION,
    DOMAIN_SUMMARY_SCHEMA_VERSION,
)
from .gate2_domain_packages import DOMAIN_PACKAGE_SCHEMA_VERSION
from .gate2_domain_routing import ROUTE_SCHEMA_VERSION
from .gate2_candidate_binding import (
    BINDING_VALIDATION_SCHEMA_VERSION,
    CANDIDATE_SET_SCHEMA_VERSION,
    RELATION_SET_SCHEMA_VERSION,
)
from .gate2_source_fact_contracts import (
    RAW_OUTPUT_SCHEMA_VERSION,
    SOURCE_FACTS_SCHEMA_VERSION,
    VALIDATION_SCHEMA_VERSION,
)
from .gate2_source_fact_selection import (
    SOURCE_FACT_SELECTION_VALIDATION_SCHEMA_VERSION,
)
from .gate2_source_fact_stitching import (
    STITCH_RESULT_SCHEMA_VERSION,
    validate_source_fact_stitch_result,
)
from .gate2_source_unit_segmentation import (
    DERIVED_SOURCE_UNIT_SCHEMA_VERSION,
    SEGMENTATION_PLAN_SCHEMA_VERSION,
    validate_source_unit_segmentation,
)


GATE3_CONTEXT_MANIFEST_SCHEMA_VERSION = "broker_reports_gate3_context_manifest_v0"
GATE3_CONTEXT_MANIFEST_POLICY_VERSION = "broker_reports_gate3_context_manifest_policy_v0"
FACTORY_REQUIRED = (
    "Gate3ContextManifestFactory.create is the only production Gate 3 context-manifest build and resolution entrypoint"
)
FORBIDDEN = (
    "Gate 3 callers must not use raw CSV, DCP, one extraction run or inherited readiness booleans as the root input"
)


def gate3_context_manifest_ref_for_run(
    *, extraction_run_ref: str, normalization_run_id: str
) -> str:
    if not extraction_run_ref or not normalization_run_id:
        raise Gate3ContextManifestError("gate3_context_run_identity_missing")
    return "gate3ctx_" + stable_digest(
        [
            GATE3_CONTEXT_MANIFEST_SCHEMA_VERSION,
            normalization_run_id,
            extraction_run_ref,
        ],
        length=24,
    )


class Gate3ContextManifestError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate3ContextManifestResult:
    manifest_ref: str
    manifest_id: str
    gate3_input_status: str
    reason_codes: list[str]
    safe_summary: dict[str, Any]


class Gate3ContextManifestFactory:
    def __init__(self, *, store: ArtifactStorePort) -> None:
        self.store = store

    def create(self) -> "Gate3ContextManifestService":
        return Gate3ContextManifestService(self.store)


class Gate3ContextManifestService:
    def __init__(self, store: ArtifactStorePort) -> None:
        self.store = store
        self.resolver = ArtifactResolver(store)

    def build_and_persist(
        self,
        *,
        extraction_run_ref: str,
        context: ArtifactAccessContext,
    ) -> Gate3ContextManifestResult:
        if not context.allow_private or not context.require_source_available:
            raise Gate3ContextManifestError(
                "gate3_context_private_source_available_context_required"
            )
        graph = self._inspect_graph(
            extraction_run_ref=extraction_run_ref,
            context=context,
        )
        manifest_id = gate3_context_manifest_ref_for_run(
            extraction_run_ref=extraction_run_ref,
            normalization_run_id=context.normalization_run_id,
        )
        payload = {
            "schema_version": GATE3_CONTEXT_MANIFEST_SCHEMA_VERSION,
            "policy_version": GATE3_CONTEXT_MANIFEST_POLICY_VERSION,
            "manifest_id": manifest_id,
            "normalization_run_id": context.normalization_run_id,
            "access_context": _safe_access_context(context),
            "declared_scope": graph["declared_scope"],
            "explicit_outside_scope": graph["explicit_outside_scope"],
            "artifact_roots": graph["artifact_roots"],
            "issue_context": graph["issue_context"],
            "terminal_gate2": graph["terminal_gate2"],
            "zero_loss_reconciliation": graph["zero_loss_reconciliation"],
            "retention": graph["retention"],
            "restrictions": {
                "root_input_contract": GATE3_CONTEXT_MANIFEST_SCHEMA_VERSION,
                "private_values_resolver_only": True,
                "cross_document_reconciliation_allowed": False,
                "duplicate_financial_event_resolution_allowed": False,
                "tax_calculation_allowed": False,
                "declaration_generation_allowed": False,
                "xls_xlsx_generation_allowed": False,
                "restriction_codes": [
                    "context_manifest_is_not_gate3_business_logic",
                    "declared_scope_only",
                    "private_facts_require_access_controlled_resolution",
                ],
            },
            "knowledge_vector_guard": {
                "knowledge_rag_used": False,
                "vectorization_performed": False,
                "ordinary_upload_used": False,
                "document_store_write_performed": False,
            },
            "decision_metrics": graph["decision_metrics"],
            "gate3_input_status": "blocked",
            "reason_codes": [],
            "created_at": graph["created_at"],
        }
        status, reasons = recompute_gate3_input_status(payload)
        payload["gate3_input_status"] = status
        payload["reason_codes"] = reasons
        payload["integrity_hash"] = _manifest_integrity_hash(payload)
        validate_gate3_context_manifest(payload)

        manifest_ref = manifest_id
        retention_policy = graph["retention_policy"]
        self.store.put_record(
            ArtifactRecord(
                artifact_id=manifest_ref,
                artifact_type=GATE3_CONTEXT_MANIFEST_SCHEMA_VERSION,
                case_id=context.case_id,
                chat_id=context.chat_id,
                user_id=context.user_id,
                workspace_model_id=context.workspace_model_id,
                normalization_run_id=context.normalization_run_id,
                document_id=None,
                source_file_ref=None,
                visibility="safe_internal",
                storage_backend="project_artifact_store",
                retention_policy=retention_policy,
                access_policy={
                    "requires_user_id": True,
                    "requires_case_or_chat": True,
                    "requires_workspace_model_id_when_present": bool(
                        context.workspace_model_id
                    ),
                    "gate3_root_only": True,
                },
                validation_status="validated",
                lifecycle_status=lifecycle_for_visibility(
                    visibility="safe_internal", validation_status="validated"
                ),
                payload_kind="inline_json",
                payload=payload,
                safe_metadata={
                    "manifest_id": manifest_id,
                    "gate3_input_status": status,
                    "csv_profile_id": CSV_SUPPORTED_PROFILE_ID,
                    "declared_scope_kind": graph["declared_scope"]["scope_kind"],
                    "documents_total": len(
                        graph["declared_scope"]["document_refs"]
                    ),
                    "selected_source_refs_total": graph["decision_metrics"][
                        "selected_source_refs_total"
                    ],
                    "typed_facts_total": graph["decision_metrics"][
                        "typed_facts_total"
                    ],
                    "rejected_packages_total": graph["decision_metrics"][
                        "rejected_packages_total"
                    ],
                    "uncovered_total": graph["decision_metrics"][
                        "uncovered_total"
                    ],
                    "conflict_total": graph["decision_metrics"][
                        "conflict_total"
                    ],
                },
                warning_codes=reasons,
            )
        )
        safe_summary = {
            "schema_version": "broker_reports_gate3_context_manifest_safe_summary_v0",
            "manifest_ref": manifest_ref,
            "gate3_input_status": status,
            "declared_scope_kind": graph["declared_scope"]["scope_kind"],
            "documents_total": len(graph["declared_scope"]["document_refs"]),
            "selected_source_refs_total": graph["decision_metrics"][
                "selected_source_refs_total"
            ],
            "typed_facts_total": graph["decision_metrics"]["typed_facts_total"],
            "rejected_packages_total": graph["decision_metrics"][
                "rejected_packages_total"
            ],
            "uncovered_total": graph["decision_metrics"]["uncovered_total"],
            "conflict_total": graph["decision_metrics"]["conflict_total"],
            "reason_codes": reasons,
            "private_values_in_summary": False,
        }
        return Gate3ContextManifestResult(
            manifest_ref=manifest_ref,
            manifest_id=manifest_id,
            gate3_input_status=status,
            reason_codes=reasons,
            safe_summary=safe_summary,
        )

    def resolve_for_gate3(
        self,
        *,
        manifest_ref: str,
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        if not context.allow_private or not context.require_source_available:
            raise Gate3ContextManifestError(
                "gate3_context_private_source_available_context_required"
            )
        resolved = self.resolver.resolve(manifest_ref, context)
        record = resolved["record"]
        if record.artifact_type != GATE3_CONTEXT_MANIFEST_SCHEMA_VERSION:
            raise Gate3ContextManifestError("gate3_context_manifest_type_mismatch")
        payload = _object(resolved["payload"])
        validate_gate3_context_manifest(payload)
        if payload.get("gate3_input_status") != "ready":
            raise Gate3ContextManifestError("gate3_context_manifest_not_ready")
        for ref in _manifest_descendant_refs(payload):
            self.resolver.resolve(ref, context)
        return copy.deepcopy(payload)

    def _inspect_graph(
        self,
        *,
        extraction_run_ref: str,
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        records: list[ArtifactRecord] = []

        def resolve(ref: str, artifact_type: str) -> dict[str, Any]:
            if not ref:
                raise Gate3ContextManifestError("gate3_context_artifact_ref_missing")
            resolved = self.resolver.resolve(ref, context)
            record = resolved["record"]
            if record.artifact_type != artifact_type:
                raise Gate3ContextManifestError(
                    "gate3_context_artifact_type_mismatch"
                )
            records.append(record)
            return _object(resolved["payload"])

        run = resolve(extraction_run_ref, DOMAIN_RUN_SCHEMA_VERSION)
        dcp_ref = str(run.get("domain_context_packet_ref") or "")
        dcp = resolve(dcp_ref, DOMAIN_CONTEXT_PACKET_SCHEMA_VERSION)
        summary_ref = str(run.get("summary_ref") or "")
        summary = resolve(summary_ref, DOMAIN_SUMMARY_SCHEMA_VERSION)

        segmentation_plan_refs = _strings(run.get("segmentation_plan_refs"))
        derived_source_unit_refs = _strings(run.get("derived_source_unit_refs"))
        route_refs = _strings(run.get("route_refs"))
        domain_package_refs = _strings(run.get("domain_package_refs"))
        source_value_candidate_set_refs = _strings(
            run.get("source_value_candidate_set_refs")
        )
        candidate_relation_set_refs = _strings(
            run.get("candidate_relation_set_refs")
        )
        candidate_binding_validation_refs = _strings(
            run.get("candidate_binding_validation_refs")
        )
        source_fact_selection_validation_refs = _strings(
            run.get("source_fact_selection_validation_refs")
        )
        raw_output_refs = _strings(run.get("raw_output_refs"))
        validation_refs = _strings(run.get("validation_refs"))
        source_facts_refs = _strings(run.get("source_facts_refs"))
        domain_source_facts_refs = _strings(run.get("domain_source_facts_refs"))
        stitch_result_refs = _strings(run.get("stitch_result_refs"))

        plans = [
            resolve(ref, SEGMENTATION_PLAN_SCHEMA_VERSION)
            for ref in segmentation_plan_refs
        ]
        derived_units = [
            resolve(ref, DERIVED_SOURCE_UNIT_SCHEMA_VERSION)
            for ref in derived_source_unit_refs
        ]
        routes = [resolve(ref, ROUTE_SCHEMA_VERSION) for ref in route_refs]
        packages = [
            resolve(ref, DOMAIN_PACKAGE_SCHEMA_VERSION)
            for ref in domain_package_refs
        ]
        candidate_sets = [
            resolve(ref, CANDIDATE_SET_SCHEMA_VERSION)
            for ref in source_value_candidate_set_refs
        ]
        relation_sets = [
            resolve(ref, RELATION_SET_SCHEMA_VERSION)
            for ref in candidate_relation_set_refs
        ]
        binding_validations = [
            resolve(ref, BINDING_VALIDATION_SCHEMA_VERSION)
            for ref in candidate_binding_validation_refs
        ]
        selection_validations = [
            resolve(ref, SOURCE_FACT_SELECTION_VALIDATION_SCHEMA_VERSION)
            for ref in source_fact_selection_validation_refs
        ]
        raws = [resolve(ref, RAW_OUTPUT_SCHEMA_VERSION) for ref in raw_output_refs]
        validations = [
            resolve(ref, VALIDATION_SCHEMA_VERSION) for ref in validation_refs
        ]
        facts_payloads = [
            resolve(ref, SOURCE_FACTS_SCHEMA_VERSION) for ref in source_facts_refs
        ]
        wrappers = [
            resolve(ref, DOMAIN_SOURCE_FACTS_SCHEMA_VERSION)
            for ref in domain_source_facts_refs
        ]
        stitches = [
            resolve(ref, STITCH_RESULT_SCHEMA_VERSION)
            for ref in stitch_result_refs
        ]

        errors: list[str] = []
        if run.get("schema_version") != DOMAIN_RUN_SCHEMA_VERSION:
            errors.append("gate3_context_run_schema_mismatch")
        if summary.get("schema_version") != DOMAIN_SUMMARY_SCHEMA_VERSION:
            errors.append("gate3_context_summary_schema_mismatch")
        candidate_binding_enabled = run.get("candidate_binding_enabled") is True
        if candidate_binding_enabled:
            if not (
                len(candidate_sets)
                == len(relation_sets)
                == len(binding_validations)
                == len(packages)
            ):
                errors.append("gate3_context_candidate_binding_graph_incomplete")
            if any(
                item.get("validation_status") != "passed"
                for item in [*candidate_sets, *relation_sets]
            ):
                errors.append("gate3_context_candidate_graph_validation_failed")
            if any(
                item.get("validator_status") != "passed"
                or int(item.get("errors_count") or 0) != 0
                or int(item.get("repair_attempt_count") or 0) != 0
                for item in binding_validations
            ):
                errors.append("gate3_context_candidate_binding_validation_failed")
        elif any(
            (
                source_value_candidate_set_refs,
                candidate_relation_set_refs,
                candidate_binding_validation_refs,
            )
        ):
            errors.append("gate3_context_candidate_binding_artifact_unexpected")
        semantic_selection_enabled = (
            run.get("semantic_selection_enabled") is True
        )
        if semantic_selection_enabled:
            if len(selection_validations) != len(packages):
                errors.append("gate3_context_semantic_selection_graph_incomplete")
            if any(
                item.get("validator_status") != "passed"
                or int(item.get("errors_count") or 0) != 0
                or int(item.get("repair_attempt_count") or 0) != 0
                or int(item.get("model_system_metadata_fields_total") or 0)
                != 0
                for item in selection_validations
            ):
                errors.append("gate3_context_semantic_selection_validation_failed")
        elif source_fact_selection_validation_refs:
            errors.append("gate3_context_semantic_selection_artifact_unexpected")
        for plan in plans:
            try:
                validate_source_unit_segmentation(plan, None)
            except ValueError as exc:
                errors.append(str(exc))
        for stitch in stitches:
            try:
                validate_source_fact_stitch_result(stitch)
            except ValueError as exc:
                errors.append(str(exc))

        selected_segments: list[dict[str, Any]] = []
        deferred_segment_refs: list[str] = []
        selected_source_refs: list[str] = []
        pending_parent_remainders = 0
        parent_truncated_total = 0
        for plan in plans:
            coverage = _object(plan.get("coverage"))
            if coverage.get("parent_remainder_status") != "not_applicable_parent_complete":
                pending_parent_remainders += 1
            if plan.get("parent_source_slice_truncated") is not False:
                parent_truncated_total += 1
            for segment in _dicts(plan.get("segments")):
                disposition = str(segment.get("execution_disposition") or "")
                if disposition == "selected_for_extraction":
                    selected_segments.append(segment)
                    selected_source_refs.extend(
                        _strings(segment.get("selected_source_refs"))
                    )
                elif disposition == "deferred_derived_unit":
                    deferred_segment_refs.append(str(segment.get("segment_ref") or ""))
                else:
                    errors.append("gate3_context_segment_disposition_invalid")
        if len(selected_source_refs) != len(set(selected_source_refs)):
            errors.append("gate3_context_selected_source_ref_duplicate")

        derived_segment_refs = {
            str(_object(item.get("segmentation")).get("segment_ref") or "")
            for item in derived_units
        }
        selected_segment_refs = {
            str(item.get("segment_ref") or "") for item in selected_segments
        }
        if derived_segment_refs != selected_segment_refs:
            errors.append("gate3_context_selected_segment_graph_mismatch")

        route_selected_refs = [
            ref for route in routes for ref in _strings(route.get("selected_source_refs"))
        ]
        if route_selected_refs != selected_source_refs:
            errors.append("gate3_context_route_scope_mismatch")
        ownership_refs = [
            str(item.get("source_ref") or "")
            for stitch in stitches
            for item in _dicts(stitch.get("ownership_map"))
        ]
        if ownership_refs != selected_source_refs:
            errors.append("gate3_context_stitch_scope_mismatch")

        package_by_ref = dict(zip(domain_package_refs, packages))
        raw_by_package: dict[str, list[dict[str, Any]]] = {}
        for raw in raws:
            raw_by_package.setdefault(str(raw.get("package_ref") or ""), []).append(raw)
        wrapper_by_package = {
            str(item.get("domain_package_ref") or ""): item for item in wrappers
        }
        validation_by_ref = dict(zip(validation_refs, validations))
        facts_by_ref = dict(zip(source_facts_refs, facts_payloads))

        provider_identities: list[dict[str, Any]] = []
        provider_failures = 0
        fallback_total = 0
        repair_total = 0
        schema_identity_missing = 0
        for package_ref, package in package_by_ref.items():
            package_raws = raw_by_package.get(package_ref, [])
            if len(package_raws) != 1:
                errors.append("gate3_context_exactly_one_model_attempt_required")
            wrapper = wrapper_by_package.get(package_ref)
            if wrapper is None:
                errors.append("gate3_context_package_not_terminally_accepted")
            for raw in package_raws:
                if raw.get("model_call_status") != "passed":
                    provider_failures += 1
                if raw.get("fallback_used") is not False:
                    fallback_total += 1
                if int(raw.get("repair_attempt_count") or 0) != 0:
                    repair_total += 1
                execution = _object(raw.get("provider_execution"))
                identity = {
                    "provider_id": execution.get("provider_id"),
                    "provider_profile_id": raw.get("provider_profile_id"),
                    "provider_profile_revision": execution.get(
                        "provider_profile_revision"
                    ),
                    "adapter_id": execution.get("adapter_id"),
                    "adapter_version": execution.get("adapter_version"),
                    "requested_model_id": execution.get("requested_model_id"),
                    "resolved_model_id": execution.get("resolved_model_id"),
                    "structured_output_mode": raw.get("structured_output_mode"),
                    "response_format_type": raw.get("response_format_type"),
                    "response_format_schema_mode": raw.get(
                        "response_format_schema_mode"
                    ),
                    "provider_response_schema_hash": raw.get(
                        "provider_response_schema_hash"
                    ),
                    "package_response_schema_hash": raw.get(
                        "package_response_schema_hash"
                    ),
                    "prompt_hash": _object(raw.get("prompt_snapshot")).get(
                        "prompt_hash"
                    ),
                }
                required_identity = (
                    "provider_id",
                    "provider_profile_id",
                    "provider_profile_revision",
                    "adapter_id",
                    "adapter_version",
                    "requested_model_id",
                    "resolved_model_id",
                    "provider_response_schema_hash",
                    "package_response_schema_hash",
                    "prompt_hash",
                )
                if any(not identity.get(key) for key in required_identity):
                    schema_identity_missing += 1
                if identity["requested_model_id"] != run.get("model_id"):
                    errors.append("gate3_context_requested_model_mismatch")
                if identity["provider_profile_id"] != run.get(
                    "provider_profile_id"
                ):
                    errors.append("gate3_context_provider_profile_mismatch")
                if identity["resolved_model_id"] not in {
                    identity["requested_model_id"],
                    None,
                } and not str(identity["resolved_model_id"] or "").startswith(
                    str(identity["requested_model_id"] or "") + "-"
                ):
                    errors.append("gate3_context_resolved_model_mismatch")
                if (
                    identity["response_format_type"] != "json_schema"
                    or identity["response_format_schema_mode"]
                    != "strict_json_schema"
                ):
                    errors.append("gate3_context_strict_schema_mode_required")
                provider_identities.append(identity)

            if wrapper is not None:
                validation_ref = str(wrapper.get("validation_ref") or "")
                validation = validation_by_ref.get(validation_ref)
                if validation is None or validation.get("validator_status") != "passed":
                    errors.append("gate3_context_validation_not_passed")
                facts_ref = str(wrapper.get("source_facts_ref") or "")
                if facts_ref not in facts_by_ref:
                    errors.append("gate3_context_source_facts_ref_missing")

        fact_types = [
            str(fact.get("fact_type") or "")
            for payload in facts_payloads
            for fact in _dicts(payload.get("facts"))
        ]
        typed_facts_total = sum(
            1 for fact_type in fact_types if fact_type != "unknown_source_row"
        )

        coverage_selected_total = 0
        uncovered_total = 0
        conflict_total = 0
        unknown_total = 0
        rejected_candidate_total = 0
        for stitch in stitches:
            coverage = _object(stitch.get("coverage"))
            coverage_selected_total += int(coverage.get("selected_total") or 0)
            uncovered_total += int(coverage.get("uncovered_total") or 0)
            conflict_total += len(_dicts(stitch.get("conflicts")))
            unknown_total += int(coverage.get("unknown_total") or 0)
            rejected_candidate_total += len(
                _dicts(stitch.get("rejected_candidate_refs"))
            )

        included_document_refs = sorted(
            {str(item.get("document_ref") or "") for item in packages}
        )
        ready_document_refs = sorted(
            set(_strings(_object(dcp.get("next_stage_refs")).get("source_fact_ready_refs")))
        )
        deferred_document_refs = sorted(
            set(ready_document_refs) - set(included_document_refs)
        )

        all_run_records = self.resolver.catalog_run(context)
        profile_records = [
            item
            for item in all_run_records
            if item.artifact_type == "technical_readability_profile_v0"
        ]
        profile_status = "missing"
        profile_ref = ""
        if len(profile_records) == 1:
            resolved_profile = self.resolver.resolve(
                profile_records[0].artifact_id, context
            )
            records.append(profile_records[0])
            profile_ref = profile_records[0].artifact_id
            matching_profiles = [
                item
                for item in resolved_profile["payload"] or []
                if isinstance(item, dict)
                and str(item.get("document_id") or "") in included_document_refs
            ]
            if matching_profiles and all(
                item.get("supported_csv_profile_id") == CSV_SUPPORTED_PROFILE_ID
                and item.get("supported_csv_profile_status") == "accepted"
                and item.get("container_format") == "csv"
                for item in matching_profiles
            ):
                profile_status = "accepted"

        issue_ledger_records = [
            item
            for item in all_run_records
            if item.artifact_type == ISSUE_LEDGER_SCHEMA_VERSION
        ]
        issue_ledger_ref = ""
        if len(issue_ledger_records) == 1:
            self.resolver.resolve(issue_ledger_records[0].artifact_id, context)
            records.append(issue_ledger_records[0])
            issue_ledger_ref = issue_ledger_records[0].artifact_id

        normalized_payload_refs = sorted(
            item.artifact_id
            for item in all_run_records
            if item.artifact_type == "private_normalized_source_payload_v0"
            and str(item.document_id or "") in included_document_refs
        )
        normalized_source_unit_refs = sorted(
            item.artifact_id
            for item in all_run_records
            if item.artifact_type == "private_normalized_source_unit_v0"
            and str(item.document_id or "") in included_document_refs
        )
        normalized_table_projection_refs = sorted(
            {
                str(_object(item.get("source_unit")).get("table_projection_artifact_ref") or "")
                for item in packages
                if _object(item.get("source_unit")).get(
                    "table_projection_artifact_ref"
                )
            }
        )
        used_normalized_roots = sorted(
            {
                str(_object(item.get("source_unit")).get("private_slice_artifact_ref") or "")
                for item in packages
                if _object(item.get("source_unit")).get(
                    "private_slice_artifact_ref"
                )
            }
        )
        for ref in sorted(
            set(normalized_payload_refs)
            | set(normalized_source_unit_refs)
            | set(normalized_table_projection_refs)
        ):
            resolved = self.resolver.resolve(ref, context)
            records.append(resolved["record"])

        deferred_source_unit_refs = sorted(
            set(normalized_source_unit_refs) - set(used_normalized_roots)
        )
        issue_refs = sorted(
            {
                str(item.get("issue_ref") or "")
                for package in packages
                for item in _dicts(package.get("issue_context"))
                if item.get("issue_ref")
            }
        )
        dcp_issue_refs = set(_strings(dcp.get("unresolved_issue_refs")))
        if not set(issue_refs) <= dcp_issue_refs:
            errors.append("gate3_context_issue_ref_out_of_scope")

        all_refs = sorted(
            {
                extraction_run_ref,
                dcp_ref,
                summary_ref,
                profile_ref,
                issue_ledger_ref,
                *segmentation_plan_refs,
                *derived_source_unit_refs,
                *route_refs,
                *domain_package_refs,
                *source_value_candidate_set_refs,
                *candidate_relation_set_refs,
                *candidate_binding_validation_refs,
                *source_fact_selection_validation_refs,
                *raw_output_refs,
                *validation_refs,
                *source_facts_refs,
                *domain_source_facts_refs,
                *stitch_result_refs,
                *normalized_payload_refs,
                *normalized_source_unit_refs,
                *normalized_table_projection_refs,
            }
            - {""}
        )
        resolved_record_refs = {item.artifact_id for item in records}
        if not set(all_refs) <= resolved_record_refs:
            errors.append("gate3_context_descendant_not_resolved")

        retention_policy = records[0].retention_policy
        retention_modes = {item.retention_policy.mode for item in records}
        expires_at_values = {item.expires_at for item in records}
        if len(retention_modes) != 1 or len(expires_at_values) != 1:
            errors.append("gate3_context_retention_horizon_mismatch")

        selected_total = len(selected_source_refs)
        if coverage_selected_total != selected_total:
            errors.append("gate3_context_coverage_count_mismatch")
        if _object(summary.get("coverage")).get("selected_total") != selected_total:
            errors.append("gate3_context_summary_coverage_mismatch")

        rejected_packages_total = max(
            int(_object(summary.get("domain_packages")).get("rejected") or 0),
            len(domain_package_refs) - len(wrapper_by_package),
            rejected_candidate_total,
        )
        decision_metrics = {
            "csv_profile_accepted": profile_status == "accepted",
            "run_terminal_completed": run.get("run_status") == "completed",
            "selected_source_refs_total": selected_total,
            "coverage_selected_total": coverage_selected_total,
            "typed_facts_total": typed_facts_total,
            "accepted_packages_total": len(wrapper_by_package),
            "rejected_packages_total": rejected_packages_total,
            "stitch_results_total": len(stitches),
            "uncovered_total": uncovered_total,
            "conflict_total": conflict_total,
            "unknown_total": unknown_total,
            "truncated_units_total": int(
                _object(summary.get("source_units")).get("truncated_total") or 0
            ),
            "parent_truncated_units_total": parent_truncated_total,
            "pending_parent_remainders_total": pending_parent_remainders,
            "provider_failures_total": provider_failures,
            "fallback_attempts_total": fallback_total,
            "repair_attempts_total": repair_total,
            "provider_schema_identity_missing_total": schema_identity_missing,
            "graph_validation_errors_total": len(set(errors)),
            "issue_context_valid": set(issue_refs) <= dcp_issue_refs,
            "retention_horizon_coherent": len(retention_modes) == 1
            and len(expires_at_values) == 1,
        }
        selected_hash = _hash_strings(selected_source_refs)
        ownership_hash = _hash_strings(ownership_refs)
        zero_loss = {
            "status": (
                "reconciled"
                if selected_source_refs == ownership_refs
                and selected_total == coverage_selected_total
                and len(selected_source_refs) == len(set(selected_source_refs))
                else "failed"
            ),
            "selected_source_refs_total": selected_total,
            "owned_source_refs_total": len(ownership_refs),
            "selected_source_refs_hash": selected_hash,
            "owned_source_refs_hash": ownership_hash,
            "duplicate_source_refs_total": len(selected_source_refs)
            - len(set(selected_source_refs)),
            "uncovered_total": uncovered_total,
            "conflict_total": conflict_total,
            "all_declared_refs_terminally_owned": selected_source_refs
            == ownership_refs,
        }
        if zero_loss["status"] != "reconciled":
            decision_metrics["graph_validation_errors_total"] += 1

        return {
            "declared_scope": {
                "scope_kind": "bounded_deterministic_csv_segments",
                "source_format": "csv",
                "csv_profile_id": CSV_SUPPORTED_PROFILE_ID,
                "csv_profile_status": profile_status,
                "document_refs": included_document_refs,
                "normalized_source_payload_refs": normalized_payload_refs,
                "normalized_source_unit_refs": normalized_source_unit_refs,
                "normalized_table_projection_refs": normalized_table_projection_refs,
                "used_normalized_root_refs": used_normalized_roots,
                "segmentation_plan_refs": segmentation_plan_refs,
                "derived_source_unit_refs": derived_source_unit_refs,
                "selected_segment_refs": sorted(selected_segment_refs),
                "selected_source_refs": selected_source_refs,
                "selected_source_refs_hash": selected_hash,
                "selected_source_refs_total": selected_total,
                "whole_parent_csv_normalization_complete": parent_truncated_total
                == 0
                and pending_parent_remainders == 0,
            },
            "explicit_outside_scope": {
                "deferred_document_refs": deferred_document_refs,
                "deferred_segment_refs": sorted(set(deferred_segment_refs) - {""}),
                "deferred_source_unit_refs": deferred_source_unit_refs,
                "blocked_refs": [],
                "failed_refs": [],
                "reason_codes": [
                    *(
                        ["documents_outside_declared_batch"]
                        if deferred_document_refs
                        else []
                    ),
                    *(
                        ["segments_outside_declared_bounded_scope"]
                        if deferred_segment_refs
                        else []
                    ),
                ],
            },
            "artifact_roots": {
                "domain_context_packet_ref": dcp_ref,
                "issue_ledger_ref": issue_ledger_ref,
                "technical_profile_ref": profile_ref,
                "terminal_gate2_run_refs": [extraction_run_ref],
                "gate2_summary_refs": [summary_ref],
                "route_refs": route_refs,
                "domain_package_refs": domain_package_refs,
                "source_value_candidate_set_refs": source_value_candidate_set_refs,
                "candidate_relation_set_refs": candidate_relation_set_refs,
                "candidate_binding_validation_refs": candidate_binding_validation_refs,
                "source_fact_selection_validation_refs": (
                    source_fact_selection_validation_refs
                ),
                "raw_output_refs": raw_output_refs,
                "validation_refs": validation_refs,
                "validated_source_fact_refs": source_facts_refs,
                "domain_source_fact_refs": domain_source_facts_refs,
                "stitch_result_refs": stitch_result_refs,
            },
            "issue_context": {
                "status": "linked" if issue_refs else "valid_empty",
                "issue_refs": issue_refs,
                "issues_total": len(issue_refs),
                "explicit_empty_set": not issue_refs,
            },
            "terminal_gate2": {
                "run_status": run.get("run_status"),
                "provider_identities": provider_identities,
                "provider_attempts_total": len(raws),
                "source_value_candidate_sets_total": len(candidate_sets),
                "candidate_relation_sets_total": len(relation_sets),
                "candidate_binding_validations_total": len(binding_validations),
                "source_fact_selection_validations_total": len(
                    selection_validations
                ),
                "facts_total": len(fact_types),
                "typed_facts_total": typed_facts_total,
                "fact_types": sorted(set(fact_types)),
                "accepted_packages_total": len(wrapper_by_package),
                "rejected_packages_total": rejected_packages_total,
                "stitch_results_total": len(stitches),
                "inherited_gate3_handoff_ready_ignored": True,
            },
            "zero_loss_reconciliation": zero_loss,
            "retention": {
                "mode": retention_policy.mode,
                "expires_at": retention_policy.expires_at,
                "source_delete_cascades": retention_policy.source_delete_cascades,
                "chat_delete_cascades": retention_policy.chat_delete_cascades,
                "coherent_descendant_horizon": len(retention_modes) == 1
                and len(expires_at_values) == 1,
                "descendant_artifacts_total": len(all_refs),
            },
            "decision_metrics": decision_metrics,
            "retention_policy": retention_policy,
            "created_at": str(run.get("finished_at") or run.get("started_at") or ""),
        }


def recompute_gate3_input_status(
    payload: dict[str, Any],
) -> tuple[str, list[str]]:
    metrics = _object(payload.get("decision_metrics"))
    checks = {
        "csv_profile_not_accepted": metrics.get("csv_profile_accepted") is True,
        "gate2_run_not_terminal_completed": metrics.get("run_terminal_completed")
        is True,
        "declared_scope_empty": int(metrics.get("selected_source_refs_total") or 0)
        > 0,
        "coverage_selected_count_mismatch": int(
            metrics.get("selected_source_refs_total") or 0
        )
        == int(metrics.get("coverage_selected_total") or -1),
        "typed_source_fact_required": int(metrics.get("typed_facts_total") or 0)
        > 0,
        "accepted_package_required": int(
            metrics.get("accepted_packages_total") or 0
        )
        > 0,
        "rejected_package_present": int(
            metrics.get("rejected_packages_total") or 0
        )
        == 0,
        "stitch_result_required": int(metrics.get("stitch_results_total") or 0)
        > 0,
        "uncovered_source_ref_present": int(metrics.get("uncovered_total") or 0)
        == 0,
        "source_ref_conflict_present": int(metrics.get("conflict_total") or 0)
        == 0,
        "unknown_source_ref_present": int(metrics.get("unknown_total") or 0)
        == 0,
        "truncated_source_unit_present": int(
            metrics.get("truncated_units_total") or 0
        )
        == 0,
        "truncated_parent_source_unit_present": int(
            metrics.get("parent_truncated_units_total") or 0
        )
        == 0,
        "pending_parent_remainder_present": int(
            metrics.get("pending_parent_remainders_total") or 0
        )
        == 0,
        "provider_failure_present": int(
            metrics.get("provider_failures_total") or 0
        )
        == 0,
        "provider_fallback_present": int(
            metrics.get("fallback_attempts_total") or 0
        )
        == 0,
        "repair_attempt_present": int(metrics.get("repair_attempts_total") or 0)
        == 0,
        "provider_schema_identity_incomplete": int(
            metrics.get("provider_schema_identity_missing_total") or 0
        )
        == 0,
        "graph_validation_failed": int(
            metrics.get("graph_validation_errors_total") or 0
        )
        == 0,
        "issue_context_invalid": metrics.get("issue_context_valid") is True,
        "retention_horizon_incoherent": metrics.get(
            "retention_horizon_coherent"
        )
        is True,
    }
    zero_loss = _object(payload.get("zero_loss_reconciliation"))
    checks["zero_loss_reconciliation_failed"] = (
        zero_loss.get("status") == "reconciled"
        and zero_loss.get("all_declared_refs_terminally_owned") is True
    )
    reasons = sorted(code for code, passed in checks.items() if not passed)
    return ("ready" if not reasons else "blocked"), reasons


def validate_gate3_context_manifest(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != GATE3_CONTEXT_MANIFEST_SCHEMA_VERSION:
        raise Gate3ContextManifestError("gate3_context_manifest_schema_mismatch")
    if payload.get("policy_version") != GATE3_CONTEXT_MANIFEST_POLICY_VERSION:
        raise Gate3ContextManifestError("gate3_context_manifest_policy_mismatch")
    if _manifest_integrity_hash(payload) != payload.get("integrity_hash"):
        raise Gate3ContextManifestError("gate3_context_manifest_integrity_mismatch")
    status, reasons = recompute_gate3_input_status(payload)
    if status != payload.get("gate3_input_status") or reasons != _strings(
        payload.get("reason_codes")
    ):
        raise Gate3ContextManifestError("gate3_context_manifest_status_mismatch")
    if _contains_private_copy_field(payload):
        raise Gate3ContextManifestError("gate3_context_manifest_private_copy_forbidden")
    guard = _object(payload.get("knowledge_vector_guard"))
    if any(value is not False for value in guard.values()):
        raise Gate3ContextManifestError("gate3_context_manifest_knowledge_guard_failed")
    restrictions = _object(payload.get("restrictions"))
    for field in (
        "cross_document_reconciliation_allowed",
        "duplicate_financial_event_resolution_allowed",
        "tax_calculation_allowed",
        "declaration_generation_allowed",
        "xls_xlsx_generation_allowed",
    ):
        if restrictions.get(field) is not False:
            raise Gate3ContextManifestError(
                "gate3_context_manifest_business_boundary_failed"
            )


def _manifest_integrity_hash(payload: dict[str, Any]) -> str:
    material = copy.deepcopy(payload)
    material.pop("integrity_hash", None)
    return hashlib.sha256(
        json.dumps(
            material,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _manifest_descendant_refs(payload: dict[str, Any]) -> list[str]:
    scope = _object(payload.get("declared_scope"))
    roots = _object(payload.get("artifact_roots"))
    values: list[str] = []
    for field in (
        "normalized_source_payload_refs",
        "normalized_source_unit_refs",
        "normalized_table_projection_refs",
        "segmentation_plan_refs",
        "derived_source_unit_refs",
    ):
        values.extend(_strings(scope.get(field)))
    for field, value in roots.items():
        if field.endswith("_ref") and value:
            values.append(str(value))
        elif field.endswith("_refs"):
            values.extend(_strings(value))
    return sorted(set(values))


def _contains_private_copy_field(value: Any) -> bool:
    forbidden = {
        "rows",
        "cells",
        "raw_output",
        "normalized_values",
        "extracted_fields",
        "original_value_refs",
        "original_filename",
        "filename",
        "private_path",
        "source_path",
    }
    if isinstance(value, dict):
        return any(
            str(key).lower() in forbidden or _contains_private_copy_field(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_private_copy_field(item) for item in value)
    return False


def _safe_access_context(context: ArtifactAccessContext) -> dict[str, Any]:
    return {
        "user_scope_ref": "userscope_"
        + stable_digest([context.user_id], length=16),
        "case_scope_ref": (
            "casescope_" + stable_digest([context.case_id], length=16)
            if context.case_id
            else None
        ),
        "chat_scope_ref": (
            "chatscope_" + stable_digest([context.chat_id], length=16)
            if context.chat_id
            else None
        ),
        "workspace_scope_ref": (
            "workspacescope_"
            + stable_digest([context.workspace_model_id], length=16)
            if context.workspace_model_id
            else None
        ),
        "same_user_required": True,
        "same_case_or_chat_required": True,
        "same_workspace_required_when_present": bool(context.workspace_model_id),
        "private_resolution_requires_explicit_access": True,
        "source_availability_required": True,
    }


def _record_matches_context(
    record: ArtifactRecord, context: ArtifactAccessContext
) -> bool:
    return (
        record.user_id == context.user_id
        and record.normalization_run_id == context.normalization_run_id
        and record.case_id == context.case_id
        and record.chat_id == context.chat_id
        and record.workspace_model_id == context.workspace_model_id
    )


def _hash_strings(values: list[str]) -> str:
    return hashlib.sha256(
        json.dumps(values, ensure_ascii=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return (
        [item for item in value or [] if isinstance(item, dict)]
        if isinstance(value, list)
        else []
    )


def _strings(value: Any) -> list[str]:
    return (
        [str(item) for item in value or [] if item is not None and str(item)]
        if isinstance(value, list)
        else []
    )
