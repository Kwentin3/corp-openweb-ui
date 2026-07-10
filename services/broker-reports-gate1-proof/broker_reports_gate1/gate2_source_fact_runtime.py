from __future__ import annotations

import copy
import inspect
from collections import Counter
from dataclasses import dataclass
from typing import Any, Protocol

from .artifact_lifecycle import lifecycle_for_visibility
from .artifact_models import ArtifactAccessContext, ArtifactRecord, RetentionPolicy, utc_now_iso
from .artifact_resolver import ArtifactResolver
from .artifact_store import SqliteArtifactStoreAdapter, new_artifact_id
from .contracts import stable_digest
from .gate2_input_readiness import Gate2InputReadinessFactory
from .gate2_source_fact_contracts import (
    EXTRACTION_RUN_SCHEMA_VERSION,
    ISSUE_LINKAGE_SCHEMA_VERSION,
    OUTPUT_SCHEMA_ID,
    PACKAGE_SCHEMA_VERSION,
    RAW_OUTPUT_SCHEMA_VERSION,
    SOURCE_FACTS_SCHEMA_VERSION,
    SUMMARY_SCHEMA_VERSION,
    VALIDATION_SCHEMA_VERSION,
    Gate2ManagedPrompt,
    Gate2PromptResolver,
    Gate2PromptUserContext,
    Gate2PromptError,
    model_call_audit_metadata,
    parse_source_facts_model_output,
    source_facts_response_format,
    source_facts_provider_schema_hash,
    source_facts_schema_hash,
)
from .gate2_source_fact_validation import Gate2SourceFactValidatorFactory


FACTORY_REQUIRED = (
    "Gate2SourceFactRuntimeFactory.create is the only production Gate 2 extraction runtime entrypoint"
)
FORBIDDEN = (
    "Pipes and smoke scripts must not call models, persist source facts or finalize validation outside this factory-backed runtime"
)

ALLOWED_WAVES = {"primary", "non_primary", "all"}


class Gate2SourceFactRuntimeError(RuntimeError):
    def __init__(self, code: str, message: str, *, raw_output: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.raw_output = raw_output


@dataclass(frozen=True)
class Gate2StructuredModelResult:
    content: Any
    structured_output_mode: str = "openwebui_response_format_json_schema"
    response_format_type: str = "json_schema"
    response_format_schema_mode: str | None = "strict_json_schema"
    fallback_used: bool = False
    repair_attempt_count: int = 0


class Gate2StructuredModelClient(Protocol):
    async def extract(
        self,
        *,
        prompt: Gate2ManagedPrompt,
        package: dict[str, Any],
        model_id: str,
        response_format: dict[str, Any],
    ) -> Gate2StructuredModelResult:
        ...


@dataclass(frozen=True)
class Gate2SourceFactRuntimeConfig:
    model_id: str
    wave: str = "primary"
    run_mode: str = "customer"
    table_max_rows: int = 40
    text_max_chars: int = 6000
    max_estimated_input_tokens: int = 12000
    model_call_concurrency_limit: int = 1
    max_repair_attempts: int = 1
    enable_exact_fact_type_hints: bool = True
    document_batch_start: int = 0
    document_batch_limit: int | None = None


@dataclass(frozen=True)
class Gate2SourceFactRuntimeResult:
    extraction_run_ref: str
    extraction_run_id: str
    terminal_status: str
    summary_ref: str
    source_facts_refs: list[str]
    validation_refs: list[str]
    raw_output_refs: list[str]
    package_refs: list[str]
    safe_summary: dict[str, Any]
    compact_russian_summary: str


class Gate2SourceFactRuntimeFactory:
    def __init__(
        self,
        *,
        store: SqliteArtifactStoreAdapter,
        prompt_resolver: Gate2PromptResolver,
        model_client: Gate2StructuredModelClient,
        config: Gate2SourceFactRuntimeConfig,
    ) -> None:
        self.store = store
        self.prompt_resolver = prompt_resolver
        self.model_client = model_client
        self.config = config

    def create(self) -> "Gate2SourceFactRuntimeService":
        if self.config.wave not in ALLOWED_WAVES:
            raise Gate2SourceFactRuntimeError("gate2_wave_invalid", "Unsupported Gate 2 wave")
        if not self.config.model_id:
            raise Gate2SourceFactRuntimeError("gate2_model_unavailable", "Gate 2 model id is required")
        if self.config.run_mode not in {"customer", "synthetic"}:
            raise Gate2SourceFactRuntimeError("gate2_run_mode_invalid", "Unsupported Gate 2 run mode")
        if self.config.max_repair_attempts not in {0, 1}:
            raise Gate2SourceFactRuntimeError(
                "gate2_repair_policy_invalid",
                "Gate 2 supports at most one repair attempt",
            )
        if self.config.document_batch_start < 0 or (
            self.config.document_batch_limit is not None
            and self.config.document_batch_limit <= 0
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_document_batch_invalid",
                "Gate 2 document batch window is invalid",
            )
        return Gate2SourceFactRuntimeService(
            store=self.store,
            prompt_resolver=self.prompt_resolver,
            model_client=self.model_client,
            config=self.config,
        )


class Gate2SourceFactRuntimeService:
    def __init__(
        self,
        *,
        store: SqliteArtifactStoreAdapter,
        prompt_resolver: Gate2PromptResolver,
        model_client: Gate2StructuredModelClient,
        config: Gate2SourceFactRuntimeConfig,
    ) -> None:
        self.store = store
        self.prompt_resolver = prompt_resolver
        self.model_client = model_client
        self.config = config
        self.resolver = ArtifactResolver(store)

    async def run(
        self,
        *,
        domain_context_packet_ref: str,
        context: ArtifactAccessContext,
        prompt_user_context: Gate2PromptUserContext,
    ) -> Gate2SourceFactRuntimeResult:
        if not context.allow_private or not context.require_source_available:
            raise Gate2SourceFactRuntimeError(
                "gate2_private_resolver_context_required",
                "Gate 2 requires private and source-available resolver checks",
            )
        if prompt_user_context.user_id != context.user_id:
            raise Gate2SourceFactRuntimeError(
                "gate2_authenticated_user_scope_mismatch",
                "Prompt and artifact user contexts differ",
            )
        dcp_resolved = self.resolver.resolve(domain_context_packet_ref, context)
        dcp_record = dcp_resolved["record"]
        retention_policy = dcp_record.retention_policy
        started_at = utc_now_iso()
        extraction_run_id = f"sfrun_{stable_digest([context.normalization_run_id, self.config.wave, started_at, new_artifact_id()], length=24)}"
        extraction_run_ref = new_artifact_id()
        input_refs = _input_artifact_refs(
            records=[
                record
                for record in self.store.list_by_run(context.normalization_run_id)
                if _record_matches_context_scope(record, context)
            ],
            dcp_ref=domain_context_packet_ref,
        )
        run_payload = self._new_run_payload(
            extraction_run_id=extraction_run_id,
            context=context,
            input_refs=input_refs,
            started_at=started_at,
        )
        self._put_record(
            artifact_id=extraction_run_ref,
            artifact_type=EXTRACTION_RUN_SCHEMA_VERSION,
            context=context,
            retention_policy=retention_policy,
            document_id=None,
            source_file_ref=None,
            visibility="safe_internal",
            storage_backend="project_artifact_store",
            validation_status="validated",
            payload=run_payload,
            safe_metadata={"run_status": "created", "wave": self.config.wave},
        )

        try:
            readiness = Gate2InputReadinessFactory(store=self.store).create().audit_and_build(
                domain_context_packet_ref=domain_context_packet_ref,
                context=context,
            )
            if readiness.validation.get("validator_status") != "passed":
                raise Gate2SourceFactRuntimeError(
                    "gate2_input_readiness_failed",
                    "Gate 2 input readiness validation failed",
                )
            prompt = self.prompt_resolver.resolve(prompt_user_context)
        except (Gate2SourceFactRuntimeError, Gate2PromptError) as exc:
            run_payload["run_status"] = "blocked"
            run_payload["terminal_error_code"] = exc.code
            run_payload["finished_at"] = utc_now_iso()
            self._replace_run_record(
                artifact_id=extraction_run_ref,
                payload=run_payload,
                context=context,
                retention_policy=retention_policy,
                safe_metadata={"run_status": "blocked", "error_code": exc.code, "wave": self.config.wave},
            )
            summary = self._blocked_summary(extraction_run_id, exc.code)
            summary_ref = self._persist_summary(
                summary=summary,
                context=context,
                retention_policy=retention_policy,
            )
            return _runtime_result(
                extraction_run_ref=extraction_run_ref,
                extraction_run_id=extraction_run_id,
                terminal_status="blocked",
                summary_ref=summary_ref,
                summary=summary,
                refs={},
            )

        all_packages = [
            self._bind_runtime_package(
                dry_package=package,
                extraction_run_id=extraction_run_id,
                prompt=prompt,
            )
            for package in readiness.packages
        ]
        wave_packages = [
            package
            for package in all_packages
            if _package_selected(package, self.config.wave)
        ]
        wave_document_refs = sorted(
            {str(package.get("document_ref") or "") for package in wave_packages}
        )
        batch_end = (
            None
            if self.config.document_batch_limit is None
            else self.config.document_batch_start + self.config.document_batch_limit
        )
        batch_document_refs = set(
            wave_document_refs[self.config.document_batch_start : batch_end]
        )
        selected_packages = [
            package
            for package in wave_packages
            if str(package.get("document_ref") or "") in batch_document_refs
        ]
        source_decisions = _source_ready_decisions(
            all_packages,
            selected_packages,
            self.config.wave,
            batching_enabled=self.config.document_batch_limit is not None,
        )
        run_payload.update(
            {
                "run_status": "inputs_validated",
                "source_ready_ref_decisions": source_decisions,
                "prompt_snapshot": prompt.snapshot(),
                "output_schema_hash": source_facts_schema_hash(),
                "model_id": self.config.model_id,
                "document_batch": {
                    "start": self.config.document_batch_start,
                    "limit": self.config.document_batch_limit,
                    "wave_documents_total": len(wave_document_refs),
                    "selected_documents_total": len(batch_document_refs),
                    "has_more": (
                        self.config.document_batch_limit is not None
                        and self.config.document_batch_start + len(batch_document_refs)
                        < len(wave_document_refs)
                    ),
                },
            }
        )

        refs: dict[str, list[str]] = {
            "package_refs": [],
            "raw_output_refs": [],
            "source_facts_refs": [],
            "validation_refs": [],
        }
        package_outcomes: list[dict[str, Any]] = []
        issue_fact_links: list[dict[str, str]] = []
        fact_type_counts: Counter[str] = Counter()
        completeness_counts: Counter[str] = Counter()
        coverage_totals: Counter[str] = Counter()
        issue_linked_facts_total = 0

        for package in selected_packages:
            package_artifact_ref = new_artifact_id()
            package["package_artifact_ref"] = package_artifact_ref
            package["expected_source_facts_set_id"] = f"sfset_{stable_digest([extraction_run_id, package_artifact_ref], length=24)}"
            package["expected_repair_candidate_audit"] = model_call_audit_metadata(
                prompt=prompt,
                model_id=self.config.model_id,
                raw_output_artifact_ref=None,
                extraction_attempt_ordinal=2,
                repair_attempt_count=1,
                created_at=str(package.get("created_at") or utc_now_iso()),
            )
            package_response_schema_hash = source_facts_provider_schema_hash(package)
            package["output_schema"]["package_response_schema_hash"] = package_response_schema_hash
            repair_schema_package = copy.deepcopy(package)
            repair_schema_package["expected_candidate_audit"] = copy.deepcopy(
                package["expected_repair_candidate_audit"]
            )
            repair_package_response_schema_hash = source_facts_provider_schema_hash(
                repair_schema_package
            )
            package["output_schema"][
                "repair_package_response_schema_hash"
            ] = repair_package_response_schema_hash
            response_format = source_facts_response_format(package)
            source_unit = _object(package.get("source_unit"))
            slice_record = self.store.get_record_unchecked(
                str(source_unit.get("private_slice_artifact_ref") or "")
            )
            source_file_ref = copy.deepcopy(slice_record.source_file_ref) if slice_record else None
            budget_error = _package_budget_error(package, self.config)
            package_validation_status = "blocked" if budget_error else "validated"
            self._put_record(
                artifact_id=package_artifact_ref,
                artifact_type=PACKAGE_SCHEMA_VERSION,
                context=context,
                retention_policy=retention_policy,
                document_id=str(package.get("document_ref") or "") or None,
                source_file_ref=source_file_ref,
                visibility="private_case",
                storage_backend="project_artifact_payload",
                validation_status=package_validation_status,
                payload=package,
                safe_metadata={
                    "package_id": package.get("package_id"),
                    "document_ref": package.get("document_ref"),
                    "unit_kind": source_unit.get("unit_kind"),
                    "wave": self.config.wave,
                    "source_values_total": len(_string_list(package.get("allowed_source_value_refs"))),
                    "coverage_selected_total": int(_object(package.get("coverage_expectation")).get("required_accounting_total") or 0),
                    "budget_status": "blocked" if budget_error else "passed",
                    "package_response_schema_hash": package_response_schema_hash,
                },
                warning_codes=[budget_error] if budget_error else [],
            )
            refs["package_refs"].append(package_artifact_ref)
            if budget_error:
                package_outcomes.append(
                    {
                        "package_ref": package_artifact_ref,
                        "document_ref": package.get("document_ref"),
                        "status": "blocked",
                        "error_code": budget_error,
                        "facts_total": 0,
                    }
                )
                continue

            finalized = None
            validation: dict[str, Any] = {}
            validation_ref = ""
            raw_output_ref = ""
            attempt_raw_refs: list[str] = []
            attempt_validation_refs: list[str] = []
            repair_errors: list[dict[str, str]] = []
            for repair_attempt_count in range(
                self.config.max_repair_attempts + 1
            ):
                attempt_package = copy.deepcopy(package)
                attempt_response_format = response_format
                attempt_schema_hash = package_response_schema_hash
                if repair_attempt_count == 1:
                    attempt_package["expected_candidate_audit"] = copy.deepcopy(
                        package["expected_repair_candidate_audit"]
                    )
                    attempt_package["repair_context"] = {
                        "schema_version": "gate2_source_fact_repair_context_v0",
                        "repair_attempt_count": 1,
                        "validation_errors": copy.deepcopy(repair_errors),
                        "instructions": (
                            "Regenerate the whole candidate from the same package. "
                            "Fix only these validator code/path findings; do not add refs, "
                            "values or assumptions and do not relax any rule."
                        ),
                    }
                    attempt_response_format = source_facts_response_format(
                        attempt_package
                    )
                    attempt_schema_hash = repair_package_response_schema_hash

                raw_output_ref, raw_payload = await self._execute_model_attempt(
                    prompt=prompt,
                    package=attempt_package,
                    response_format=attempt_response_format,
                    package_response_schema_hash=attempt_schema_hash,
                    repair_attempt_count=repair_attempt_count,
                    extraction_run_id=extraction_run_id,
                    package_artifact_ref=package_artifact_ref,
                    source_unit=source_unit,
                    source_file_ref=source_file_ref,
                    context=context,
                    retention_policy=retention_policy,
                )
                refs["raw_output_refs"].append(raw_output_ref)
                attempt_raw_refs.append(raw_output_ref)

                validation_ref = new_artifact_id()
                if raw_payload["model_call_status"] == "passed":
                    try:
                        candidate = parse_source_facts_model_output(
                            raw_payload["raw_output"]
                        )
                        outcome = Gate2SourceFactValidatorFactory(
                            resolver=self.resolver,
                            context=context,
                        ).create().validate(
                            candidate=candidate,
                            package=package,
                            package_artifact_ref=package_artifact_ref,
                            raw_output_artifact_ref=raw_output_ref,
                            validation_artifact_ref=validation_ref,
                            prompt=prompt,
                            model_id=self.config.model_id,
                            expected_candidate_audit=_object(
                                attempt_package.get("expected_candidate_audit")
                            ),
                        )
                        validation = outcome.validation
                        finalized = outcome.finalized_source_facts
                    except Gate2PromptError as exc:
                        validation = _failed_validation(
                            package=package,
                            package_ref=package_artifact_ref,
                            code=exc.code,
                        )
                        finalized = None
                else:
                    validation = _failed_validation(
                        package=package,
                        package_ref=package_artifact_ref,
                        code=str(raw_payload["error_code"]),
                    )
                    finalized = None

                self._persist_validation_attempt(
                    validation_ref=validation_ref,
                    validation=validation,
                    package=package,
                    source_file_ref=source_file_ref,
                    repair_attempt_count=repair_attempt_count,
                    context=context,
                    retention_policy=retention_policy,
                )
                refs["validation_refs"].append(validation_ref)
                attempt_validation_refs.append(validation_ref)
                if finalized is not None or raw_payload["model_call_status"] != "passed":
                    break
                if repair_attempt_count >= self.config.max_repair_attempts:
                    break
                repair_errors = [
                    {
                        "code": str(item.get("code") or "unknown"),
                        "subject": str(item.get("subject") or ""),
                    }
                    for item in _dict_list(validation.get("errors"))
                ]

            source_facts_ref = None
            if finalized is not None:
                source_facts_ref = new_artifact_id()
                self._put_record(
                    artifact_id=source_facts_ref,
                    artifact_type=SOURCE_FACTS_SCHEMA_VERSION,
                    context=context,
                    retention_policy=retention_policy,
                    document_id=str(package.get("document_ref") or "") or None,
                    source_file_ref=source_file_ref,
                    visibility="private_case",
                    storage_backend="project_artifact_payload",
                    validation_status="validated",
                    payload=finalized,
                    safe_metadata=_source_facts_safe_metadata(finalized),
                )
                refs["source_facts_refs"].append(source_facts_ref)
                for fact in _dict_list(finalized.get("facts")):
                    fact_type_counts[str(fact.get("fact_type") or "unknown")] += 1
                    completeness_counts[str(fact.get("completeness") or "unknown")] += 1
                    linked = _string_list(fact.get("linked_issue_refs"))
                    if linked:
                        issue_linked_facts_total += 1
                    for issue_ref in linked:
                        issue_fact_links.append(
                            {
                                "issue_ref": issue_ref,
                                "fact_id": str(fact.get("fact_id") or ""),
                                "source_facts_ref": source_facts_ref,
                            }
                        )
                coverage = _object(finalized.get("coverage"))
                coverage_totals["selected"] += len(_string_list(coverage.get("selected_source_refs")))
                coverage_totals["fact_covered"] += len(_string_list(coverage.get("fact_covered_refs")))
                coverage_totals["no_fact"] += len(_dict_list(coverage.get("no_fact_results")))
                coverage_totals["pending"] += len(_string_list(coverage.get("pending_refs")))
                coverage_totals["rejected"] += len(_string_list(coverage.get("rejected_refs")))

            package_outcomes.append(
                {
                    "package_ref": package_artifact_ref,
                    "document_ref": package.get("document_ref"),
                    "status": "accepted" if finalized is not None else "rejected",
                    "validation_ref": validation_ref,
                    "raw_output_ref": raw_output_ref,
                    "validation_refs": attempt_validation_refs,
                    "raw_output_refs": attempt_raw_refs,
                    "repair_attempt_count": max(len(attempt_raw_refs) - 1, 0),
                    "source_facts_ref": source_facts_ref,
                    "facts_total": len(_dict_list(finalized.get("facts"))) if finalized else 0,
                }
            )

        linkage_ref = self._persist_issue_linkage(
            extraction_run_id=extraction_run_id,
            links=issue_fact_links,
            context=context,
            retention_policy=retention_policy,
        )
        accepted_packages = sum(1 for item in package_outcomes if item["status"] == "accepted")
        rejected_packages = sum(1 for item in package_outcomes if item["status"] == "rejected")
        blocked_packages = sum(1 for item in package_outcomes if item["status"] == "blocked")
        truncated_source_units_total = sum(
            1
            for package in selected_packages
            if _object(package.get("source_unit")).get("source_slice_truncated") is True
        )
        terminal_status = "completed" if rejected_packages == 0 and blocked_packages == 0 else "completed_with_rejections"
        gate3_handoff_ready = (
            terminal_status == "completed"
            and accepted_packages > 0
            and truncated_source_units_total == 0
        )
        summary = {
            "schema_version": SUMMARY_SCHEMA_VERSION,
            "extraction_run_id": extraction_run_id,
            "terminal_status": terminal_status,
            "wave": self.config.wave,
            "document_batch": copy.deepcopy(run_payload.get("document_batch") or {}),
            "documents": {
                "source_ready_total": len(source_decisions),
                "selected_total": sum(1 for item in source_decisions if str(item.get("decision") or "").startswith("selected_")),
                "deferred_total": sum(1 for item in source_decisions if item.get("decision") == "deferred_context_only"),
                "blocked_total": sum(1 for item in source_decisions if item.get("decision") == "blocked_with_reason"),
            },
            "packages": {
                "total": len(package_outcomes),
                "accepted": accepted_packages,
                "rejected": rejected_packages,
                "blocked": blocked_packages,
            },
            "facts_by_type": dict(sorted(fact_type_counts.items())),
            "facts_by_completeness": dict(sorted(completeness_counts.items())),
            "facts_total": sum(fact_type_counts.values()),
            "issue_linked_facts_total": issue_linked_facts_total,
            "truncated_source_units_total": truncated_source_units_total,
            "coverage": dict(coverage_totals),
            "source_fact_refs_total": len(refs["source_facts_refs"]),
            "validation_refs_total": len(refs["validation_refs"]),
            "raw_output_refs_total": len(refs["raw_output_refs"]),
            "issue_fact_linkage_ref": linkage_ref,
            "gate3_handoff_ready": gate3_handoff_ready,
            "safe_next_step": _safe_next_step(
                self.config.wave,
                terminal_status,
                truncated_source_units_total=truncated_source_units_total,
            ),
            "no_tax_declaration_xlsx_work": True,
            "vector_knowledge_guard": {
                "knowledge_rag_used": False,
                "vectorization_performed": False,
                "ordinary_upload_used": False,
            },
            "created_at": utc_now_iso(),
        }
        summary_ref = self._persist_summary(
            summary=summary,
            context=context,
            retention_policy=retention_policy,
        )
        run_payload.update(
            {
                "run_status": terminal_status,
                "package_refs": refs["package_refs"],
                "raw_output_refs": refs["raw_output_refs"],
                "source_facts_refs": refs["source_facts_refs"],
                "validation_refs": refs["validation_refs"],
                "issue_fact_linkage_ref": linkage_ref,
                "summary_ref": summary_ref,
                "coverage_summary": dict(coverage_totals),
                "finished_at": utc_now_iso(),
            }
        )
        self._replace_run_record(
            artifact_id=extraction_run_ref,
            payload=run_payload,
            context=context,
            retention_policy=retention_policy,
            safe_metadata={
                "run_status": terminal_status,
                "wave": self.config.wave,
                "packages_total": len(package_outcomes),
                "accepted_packages": accepted_packages,
                "rejected_packages": rejected_packages,
                "blocked_packages": blocked_packages,
                "facts_total": sum(fact_type_counts.values()),
            },
        )
        return _runtime_result(
            extraction_run_ref=extraction_run_ref,
            extraction_run_id=extraction_run_id,
            terminal_status=terminal_status,
            summary_ref=summary_ref,
            summary=summary,
            refs=refs,
        )

    def _new_run_payload(
        self,
        *,
        extraction_run_id: str,
        context: ArtifactAccessContext,
        input_refs: dict[str, Any],
        started_at: str,
    ) -> dict[str, Any]:
        return {
            "schema_version": EXTRACTION_RUN_SCHEMA_VERSION,
            "extraction_run_id": extraction_run_id,
            "normalization_run_id": context.normalization_run_id,
            "case_id": context.case_id,
            "chat_id": context.chat_id,
            "workspace_model_id": context.workspace_model_id,
            "run_status": "created",
            "input_refs": input_refs,
            "selection_policy": {
                "policy_id": "gate2_source_fact_selection_v0",
                "wave": self.config.wave,
                "cross_check_context_only": True,
                "declaration_support_context_only": True,
                "audit_context_only": True,
                "document_batch_start": self.config.document_batch_start,
                "document_batch_limit": self.config.document_batch_limit,
            },
            "source_ready_ref_decisions": [],
            "package_policy": {
                "table_max_rows": self.config.table_max_rows,
                "text_max_chars": self.config.text_max_chars,
                "max_estimated_input_tokens": self.config.max_estimated_input_tokens,
                "data_row_overlap": 0,
                "header_context_repeated": True,
                "silent_truncation_forbidden": True,
                "model_call_concurrency_limit": self.config.model_call_concurrency_limit,
            },
            "prompt_snapshot": None,
            "output_schema_id": OUTPUT_SCHEMA_ID,
            "output_schema_hash": source_facts_schema_hash(),
            "provider_response_schema_hash": source_facts_provider_schema_hash(),
            "provider_union_keyword": "anyOf",
            "model_id": self.config.model_id,
            "structured_output_policy": {
                "required_mode": "json_schema",
                "strict": True,
                "customer_fallback": "none",
                "synthetic_json_object_fallback_allowed": False,
                "max_repair_attempts": self.config.max_repair_attempts,
                "validator_is_final_authority": True,
            },
            "package_refs": [],
            "raw_output_refs": [],
            "source_facts_refs": [],
            "validation_refs": [],
            "issue_fact_linkage_ref": None,
            "summary_ref": None,
            "coverage_summary": {},
            "artifactstore_policy": {
                "system_of_record": True,
                "private_payload_backend": "project_artifact_payload",
                "knowledge_backend_forbidden": True,
            },
            "vector_knowledge_guard": {
                "knowledge_rag_used": False,
                "vectorization_performed": False,
                "ordinary_upload_used": False,
            },
            "terminal_error_code": None,
            "started_at": started_at,
            "finished_at": None,
        }

    def _bind_runtime_package(
        self,
        *,
        dry_package: dict[str, Any],
        extraction_run_id: str,
        prompt: Gate2ManagedPrompt,
    ) -> dict[str, Any]:
        package = copy.deepcopy(dry_package)
        if not self.config.enable_exact_fact_type_hints:
            projection = _object(
                _object(package.get("source_unit")).get("model_source_projection")
            )
            for row in _dict_list(projection.get("rows")):
                row["fact_type_hint"] = None
        created_at = utc_now_iso()
        package["package_mode"] = "runtime_strict_json_schema"
        package["extraction_run_id"] = extraction_run_id
        package["prompt_contract"] = prompt.snapshot()
        package["output_schema"] = {
            "output_schema_id": OUTPUT_SCHEMA_ID,
            "output_schema_version": SOURCE_FACTS_SCHEMA_VERSION,
            "output_schema_hash": source_facts_schema_hash(),
            "provider_response_schema_hash": source_facts_provider_schema_hash(),
            "provider_union_keyword": "anyOf",
            "schema_validation_required": True,
        }
        package["expected_candidate_audit"] = model_call_audit_metadata(
            prompt=prompt,
            model_id=self.config.model_id,
            raw_output_artifact_ref=None,
            created_at=created_at,
        )
        package["model_id"] = self.config.model_id
        package["structured_output_policy"] = {
            "required_mode": "json_schema",
            "strict": True,
            "fallback": "none",
            "repair_attempts": self.config.max_repair_attempts,
        }
        package["created_at"] = created_at
        return package

    async def _execute_model_attempt(
        self,
        *,
        prompt: Gate2ManagedPrompt,
        package: dict[str, Any],
        response_format: dict[str, Any],
        package_response_schema_hash: str,
        repair_attempt_count: int,
        extraction_run_id: str,
        package_artifact_ref: str,
        source_unit: dict[str, Any],
        source_file_ref: dict[str, Any] | None,
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
    ) -> tuple[str, dict[str, Any]]:
        raw_output_ref = new_artifact_id()
        try:
            model_result = await self.model_client.extract(
                prompt=prompt,
                package=copy.deepcopy(package),
                model_id=self.config.model_id,
                response_format=response_format,
            )
            if inspect.isawaitable(model_result):
                model_result = await model_result
            if not isinstance(model_result, Gate2StructuredModelResult):
                raise Gate2SourceFactRuntimeError(
                    "gate2_model_invalid_response",
                    "Structured model client returned an invalid result",
                )
            raw_payload = {
                "schema_version": RAW_OUTPUT_SCHEMA_VERSION,
                "extraction_run_id": extraction_run_id,
                "package_ref": package_artifact_ref,
                "document_ref": package.get("document_ref"),
                "source_unit_ref": source_unit.get("unit_id"),
                "model_call_status": "passed",
                "error_code": None,
                "raw_output": model_result.content,
                "structured_output_mode": model_result.structured_output_mode,
                "response_format_type": model_result.response_format_type,
                "response_format_schema_mode": model_result.response_format_schema_mode,
                "fallback_used": model_result.fallback_used,
                "repair_attempt_count": repair_attempt_count,
                "extraction_attempt_ordinal": repair_attempt_count + 1,
                "provider_response_schema_hash": source_facts_provider_schema_hash(),
                "package_response_schema_hash": package_response_schema_hash,
                "provider_union_keyword": "anyOf",
                "prompt_snapshot": prompt.snapshot(),
                "model_id": self.config.model_id,
                "created_at": utc_now_iso(),
            }
        except Exception as exc:
            error_code = getattr(
                exc,
                "code",
                f"gate2_model_call_failed_{exc.__class__.__name__}",
            )
            raw_payload = {
                "schema_version": RAW_OUTPUT_SCHEMA_VERSION,
                "extraction_run_id": extraction_run_id,
                "package_ref": package_artifact_ref,
                "document_ref": package.get("document_ref"),
                "source_unit_ref": source_unit.get("unit_id"),
                "model_call_status": "failed",
                "error_code": str(error_code),
                "raw_output": copy.deepcopy(getattr(exc, "raw_output", None)),
                "structured_output_mode": "openwebui_response_format_json_schema",
                "response_format_type": "json_schema",
                "response_format_schema_mode": "strict_json_schema",
                "fallback_used": False,
                "repair_attempt_count": repair_attempt_count,
                "extraction_attempt_ordinal": repair_attempt_count + 1,
                "provider_response_schema_hash": source_facts_provider_schema_hash(),
                "package_response_schema_hash": package_response_schema_hash,
                "provider_union_keyword": "anyOf",
                "prompt_snapshot": prompt.snapshot(),
                "model_id": self.config.model_id,
                "created_at": utc_now_iso(),
            }
        self._put_record(
            artifact_id=raw_output_ref,
            artifact_type=RAW_OUTPUT_SCHEMA_VERSION,
            context=context,
            retention_policy=retention_policy,
            document_id=str(package.get("document_ref") or "") or None,
            source_file_ref=source_file_ref,
            visibility="private_case",
            storage_backend="project_artifact_payload",
            validation_status="validated",
            payload=raw_payload,
            safe_metadata={
                "model_call_status": raw_payload["model_call_status"],
                "error_code": raw_payload["error_code"],
                "structured_output_mode": raw_payload["structured_output_mode"],
                "response_format_type": raw_payload["response_format_type"],
                "fallback_used": raw_payload["fallback_used"],
                "repair_attempt_count": repair_attempt_count,
                "extraction_attempt_ordinal": repair_attempt_count + 1,
                "model_id": self.config.model_id,
                "prompt_ref": prompt.prompt_ref,
                "prompt_hash": prompt.hash,
                "output_schema_hash": source_facts_schema_hash(),
                "provider_response_schema_hash": source_facts_provider_schema_hash(),
                "package_response_schema_hash": package_response_schema_hash,
                "provider_union_keyword": "anyOf",
            },
        )
        return raw_output_ref, raw_payload

    def _persist_validation_attempt(
        self,
        *,
        validation_ref: str,
        validation: dict[str, Any],
        package: dict[str, Any],
        source_file_ref: dict[str, Any] | None,
        repair_attempt_count: int,
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
    ) -> None:
        self._put_record(
            artifact_id=validation_ref,
            artifact_type=VALIDATION_SCHEMA_VERSION,
            context=context,
            retention_policy=retention_policy,
            document_id=str(package.get("document_ref") or "") or None,
            source_file_ref=None,
            visibility="safe_internal",
            storage_backend="project_artifact_store",
            validation_status="validated",
            payload=validation,
            safe_metadata={
                "validator_status": validation.get("validator_status"),
                "accepted_facts_total": len(
                    _string_list(validation.get("accepted_fact_ids"))
                ),
                "rejected_facts_total": len(
                    _string_list(validation.get("rejected_fact_ids"))
                ),
                "error_code_counts": dict(
                    Counter(
                        str(item.get("code") or "unknown")
                        for item in _dict_list(validation.get("errors"))
                    )
                ),
                "privacy_status": validation.get("privacy_status"),
                "boundary_status": validation.get("boundary_status"),
                "repair_attempt_count": repair_attempt_count,
                "extraction_attempt_ordinal": repair_attempt_count + 1,
            },
        )

    def _put_record(
        self,
        *,
        artifact_id: str,
        artifact_type: str,
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
        document_id: str | None,
        source_file_ref: dict[str, Any] | None,
        visibility: str,
        storage_backend: str,
        validation_status: str,
        payload: Any,
        safe_metadata: dict[str, Any],
        warning_codes: list[str] | None = None,
    ) -> ArtifactRecord:
        record = ArtifactRecord(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            case_id=context.case_id,
            chat_id=context.chat_id,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=context.normalization_run_id,
            document_id=document_id,
            source_file_ref=source_file_ref,
            visibility=visibility,
            storage_backend=storage_backend,
            retention_policy=retention_policy,
            access_policy={
                "requires_user_id": True,
                "requires_case_or_chat": True,
                "requires_workspace_model_id_when_present": bool(context.workspace_model_id),
            },
            validation_status=validation_status,
            lifecycle_status=lifecycle_for_visibility(
                visibility=visibility,
                validation_status=validation_status,
            ),
            payload_kind="json_file" if storage_backend == "project_artifact_payload" else "inline_json",
            payload=payload,
            safe_metadata=safe_metadata,
            warning_codes=warning_codes or [],
        )
        return self.store.put_record(record)

    def _replace_run_record(
        self,
        *,
        artifact_id: str,
        payload: dict[str, Any],
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
        safe_metadata: dict[str, Any],
    ) -> None:
        self._put_record(
            artifact_id=artifact_id,
            artifact_type=EXTRACTION_RUN_SCHEMA_VERSION,
            context=context,
            retention_policy=retention_policy,
            document_id=None,
            source_file_ref=None,
            visibility="safe_internal",
            storage_backend="project_artifact_store",
            validation_status="validated",
            payload=payload,
            safe_metadata=safe_metadata,
        )

    def _persist_issue_linkage(
        self,
        *,
        extraction_run_id: str,
        links: list[dict[str, str]],
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
    ) -> str:
        artifact_ref = new_artifact_id()
        payload = {
            "schema_version": ISSUE_LINKAGE_SCHEMA_VERSION,
            "extraction_run_id": extraction_run_id,
            "links": links,
            "links_total": len(links),
            "created_at": utc_now_iso(),
        }
        self._put_record(
            artifact_id=artifact_ref,
            artifact_type=ISSUE_LINKAGE_SCHEMA_VERSION,
            context=context,
            retention_policy=retention_policy,
            document_id=None,
            source_file_ref=None,
            visibility="safe_internal",
            storage_backend="project_artifact_store",
            validation_status="validated",
            payload=payload,
            safe_metadata={
                "links_total": len(links),
                "issues_total": len({item["issue_ref"] for item in links}),
                "facts_total": len({item["fact_id"] for item in links}),
            },
        )
        return artifact_ref

    def _persist_summary(
        self,
        *,
        summary: dict[str, Any],
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
    ) -> str:
        artifact_ref = new_artifact_id()
        self._put_record(
            artifact_id=artifact_ref,
            artifact_type=SUMMARY_SCHEMA_VERSION,
            context=context,
            retention_policy=retention_policy,
            document_id=None,
            source_file_ref=None,
            visibility="chat_visible",
            storage_backend="project_artifact_store",
            validation_status="validated",
            payload=summary,
            safe_metadata={
                "terminal_status": summary.get("terminal_status"),
                "wave": summary.get("wave"),
                "facts_total": summary.get("facts_total", 0),
                "packages": copy.deepcopy(summary.get("packages") or {}),
            },
        )
        return artifact_ref

    def _blocked_summary(self, extraction_run_id: str, error_code: str) -> dict[str, Any]:
        return {
            "schema_version": SUMMARY_SCHEMA_VERSION,
            "extraction_run_id": extraction_run_id,
            "terminal_status": "blocked",
            "wave": self.config.wave,
            "error_code": error_code,
            "documents": {"source_ready_total": 0, "selected_total": 0, "deferred_total": 0, "blocked_total": 0},
            "packages": {"total": 0, "accepted": 0, "rejected": 0, "blocked": 0},
            "facts_by_type": {},
            "facts_by_completeness": {},
            "facts_total": 0,
            "issue_linked_facts_total": 0,
            "coverage": {"selected": 0, "fact_covered": 0, "no_fact": 0, "pending": 0, "rejected": 0},
            "source_fact_refs_total": 0,
            "validation_refs_total": 0,
            "raw_output_refs_total": 0,
            "issue_fact_linkage_ref": None,
            "gate3_handoff_ready": False,
            "safe_next_step": "Исправить входной или runtime-блокер и повторить Gate 2.",
            "no_tax_declaration_xlsx_work": True,
            "vector_knowledge_guard": {
                "knowledge_rag_used": False,
                "vectorization_performed": False,
                "ordinary_upload_used": False,
            },
            "created_at": utc_now_iso(),
        }


def _runtime_result(
    *,
    extraction_run_ref: str,
    extraction_run_id: str,
    terminal_status: str,
    summary_ref: str,
    summary: dict[str, Any],
    refs: dict[str, list[str]],
) -> Gate2SourceFactRuntimeResult:
    return Gate2SourceFactRuntimeResult(
        extraction_run_ref=extraction_run_ref,
        extraction_run_id=extraction_run_id,
        terminal_status=terminal_status,
        summary_ref=summary_ref,
        source_facts_refs=list(refs.get("source_facts_refs") or []),
        validation_refs=list(refs.get("validation_refs") or []),
        raw_output_refs=list(refs.get("raw_output_refs") or []),
        package_refs=list(refs.get("package_refs") or []),
        safe_summary=copy.deepcopy(summary),
        compact_russian_summary=render_compact_russian_summary(summary),
    )


def render_compact_russian_summary(summary: dict[str, Any]) -> str:
    packages = _object(summary.get("packages"))
    facts_total = int(summary.get("facts_total") or 0)
    coverage = _object(summary.get("coverage"))
    status = str(summary.get("terminal_status") or "blocked")
    if status == "completed" and int(summary.get("truncated_source_units_total") or 0) > 0:
        lead = "Gate 2 завершён по доступным фрагментам; полное покрытие источников не доказано."
    elif status == "completed":
        lead = "Gate 2 завершён: исходные факты извлечены и прошли проверку."
    elif status == "completed_with_rejections":
        lead = "Gate 2 завершён с отклонёнными или заблокированными пакетами."
    else:
        lead = "Gate 2 заблокирован до извлечения подтверждённых исходных фактов."
    return "\n".join(
        [
            lead,
            (
                f"Пакеты: принято {int(packages.get('accepted') or 0)}, "
                f"отклонено {int(packages.get('rejected') or 0)}, "
                f"заблокировано {int(packages.get('blocked') or 0)}."
            ),
            f"Подтверждённых фактов: {facts_total}.",
            (
                f"Покрытие: {int(coverage.get('fact_covered') or 0)} фактовых и "
                f"{int(coverage.get('no_fact') or 0)} нефактовых строк/сегментов."
            ),
            "Расчёт налогов, декларация и XLS/XLSX не выполнялись.",
            str(summary.get("safe_next_step") or ""),
        ]
    ).strip()


def _source_ready_decisions(
    all_packages: list[dict[str, Any]],
    selected_packages: list[dict[str, Any]],
    wave: str,
    batching_enabled: bool = False,
) -> list[dict[str, Any]]:
    by_document: dict[str, list[dict[str, Any]]] = {}
    selected_documents = {str(item.get("document_ref") or "") for item in selected_packages}
    for package in all_packages:
        by_document.setdefault(str(package.get("document_ref") or ""), []).append(package)
    decisions = []
    for document_ref, packages in sorted(by_document.items()):
        roles = sorted({role for package in packages for role in _string_list(package.get("source_bucket_roles"))})
        if document_ref in selected_documents:
            if "primary_source_extraction_refs" in roles:
                decision = "selected_primary"
            elif "secondary_source_extraction_refs" in roles:
                decision = "selected_secondary"
            else:
                decision = "selected_duplicate_or_non_primary"
            reason_codes = [f"wave_{wave}"]
        else:
            decision = "deferred_context_only"
            reason_codes = [
                f"not_selected_in_{wave}_{'batch' if batching_enabled else 'wave'}"
            ]
        decisions.append(
            {
                "document_ref": document_ref,
                "next_stage_buckets": roles,
                "decision": decision,
                "reason_codes": reason_codes,
                "issue_refs": sorted({ref for package in packages for ref in _string_list(package.get("allowed_issue_refs"))}),
                "private_slice_refs_count": len(packages),
            }
        )
    return decisions


def _package_selected(package: dict[str, Any], wave: str) -> bool:
    roles = set(_string_list(package.get("source_bucket_roles")))
    if wave == "primary":
        return "primary_source_extraction_refs" in roles
    if wave == "non_primary":
        return bool(roles & {"secondary_source_extraction_refs", "duplicate_or_non_primary_refs"})
    return bool(roles & {"primary_source_extraction_refs", "secondary_source_extraction_refs", "duplicate_or_non_primary_refs"})


def _package_budget_error(
    package: dict[str, Any],
    config: Gate2SourceFactRuntimeConfig,
) -> str | None:
    unit = _object(package.get("source_unit"))
    projection = _object(unit.get("normalized_source_projection"))
    if unit.get("unit_kind") == "table_row_window":
        rows = projection.get("cells") if isinstance(projection.get("cells"), list) else []
        if len(rows) > config.table_max_rows:
            return "gate2_table_package_budget_exceeded"
    else:
        if len(str(projection.get("text") or "")) > config.text_max_chars:
            return "gate2_text_package_budget_exceeded"
    return None


def _input_artifact_refs(
    *,
    records: list[ArtifactRecord],
    dcp_ref: str,
) -> dict[str, Any]:
    by_type: dict[str, list[str]] = {}
    for record in records:
        by_type.setdefault(record.artifact_type, []).append(record.artifact_id)
    return {
        "domain_context_packet_ref": dcp_ref,
        "document_usage_classification_ref": _single_ref(by_type, "document_usage_classification_v0"),
        "gate1_issue_ledger_ref": _single_ref(by_type, "gate1_issue_ledger_v0"),
        "gate2_handoff_ref": _single_ref(by_type, "gate2_handoff_v0"),
        "gate1_validation_ref": _single_ref(by_type, "validation_result_v0"),
        "document_metadata_passport_refs": list(by_type.get("document_metadata_passport_v0") or []),
    }


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


def _single_ref(by_type: dict[str, list[str]], artifact_type: str) -> str | None:
    values = by_type.get(artifact_type) or []
    return values[0] if len(values) == 1 else None


def _source_facts_safe_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    facts = _dict_list(payload.get("facts"))
    return {
        "source_facts_set_id": payload.get("source_facts_set_id"),
        "validator_status": payload.get("validator_status"),
        "facts_total": len(facts),
        "fact_type_counts": dict(sorted(Counter(str(item.get("fact_type") or "unknown") for item in facts).items())),
        "completeness_counts": dict(sorted(Counter(str(item.get("completeness") or "unknown") for item in facts).items())),
        "issue_linked_facts_total": sum(1 for item in facts if item.get("linked_issue_refs")),
        "coverage_status": _object(payload.get("coverage")).get("coverage_status"),
    }


def _failed_validation(
    *,
    package: dict[str, Any],
    package_ref: str,
    code: str,
) -> dict[str, Any]:
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "validation_id": f"sfval_{stable_digest([package_ref, code], length=20)}",
        "extraction_run_id": package.get("extraction_run_id"),
        "package_ref": package_ref,
        "document_ref": package.get("document_ref"),
        "source_unit_ref": _object(package.get("source_unit")).get("unit_id"),
        "validator_status": "failed",
        "accepted_fact_ids": [],
        "rejected_fact_ids": [],
        "errors": [{"code": code, "subject": package_ref}],
        "warnings": [],
        "coverage": {
            "selected_total": int(_object(package.get("coverage_expectation")).get("required_accounting_total") or 0),
            "fact_covered_total": 0,
            "no_fact_total": 0,
            "rejected_total": 0,
            "pending_total": int(_object(package.get("coverage_expectation")).get("required_accounting_total") or 0),
            "coverage_status": "blocked",
        },
        "issue_carry_forward": {
            "allowed_issue_refs": _string_list(package.get("allowed_issue_refs")),
            "issue_linked_facts_total": 0,
        },
        "privacy_status": "passed",
        "boundary_status": "passed",
        "prompt_schema_model_audit": copy.deepcopy(package.get("expected_candidate_audit") or {}),
        "validated_at": utc_now_iso(),
    }


def _safe_next_step(
    wave: str,
    terminal_status: str,
    *,
    truncated_source_units_total: int = 0,
) -> str:
    if terminal_status != "completed":
        return "Проверить отклонённые пакеты; неподтверждённые ответы не передавать дальше."
    if truncated_source_units_total > 0:
        return "Gate 1 должен выпустить полные private slices; до этого Gate 3 не считать готовым."
    if wave == "primary":
        return "Можно запускать контролируемую вторую волну для вторичных и непервичных источников."
    return "Подтверждённые refs готовы для проектирования промежуточного реестра Gate 3."


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)] if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value or [] if item is not None and str(item)] if isinstance(value, list) else []
