from __future__ import annotations

import copy
import inspect
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Protocol

from .artifact_lifecycle import lifecycle_for_visibility
from .artifact_models import ArtifactAccessContext, ArtifactRecord, RetentionPolicy, utc_now_iso
from .artifact_resolver import ArtifactResolver
from .artifact_store import SqliteArtifactStoreAdapter, new_artifact_id
from .contracts import stable_digest
from .gate2_candidate_binding import (
    BINDING_VALIDATION_SCHEMA_VERSION,
    CANDIDATE_SET_SCHEMA_VERSION,
    RELATION_SET_SCHEMA_VERSION,
)
from .gate2_domain_contracts import (
    DOMAIN_SOURCE_FACTS_SCHEMA_VERSION,
    build_domain_source_facts_wrapper,
    domain_source_facts_response_format,
)
from .gate2_domain_packages import (
    DOMAIN_PACKAGE_SCHEMA_VERSION,
    Gate2DomainPackageBuilderConfig,
    Gate2DomainPackageBuilderFactory,
)
from .gate2_candidate_binding_runtime import (
    Gate2CandidateBindingRuntimeFactory,
    candidate_binding_response_format,
    candidate_binding_schema_hash,
    parse_candidate_binding_model_output,
)
from .gate2_domain_finalization import Gate2DomainCandidateFinalizerFactory
from .gate2_domain_routing import (
    ROUTE_SCHEMA_VERSION,
    Gate2SourceUnitRouterFactory,
)
from .gate2_input_readiness import (
    Gate2InputReadinessConfig,
    Gate2InputReadinessFactory,
)
from .gate2_model_contracts import (
    Gate2SourceFactRuntimeError,
    Gate2StructuredModelClient,
    Gate2StructuredModelResult,
)
from .gate2_source_fact_contracts import (
    RAW_OUTPUT_SCHEMA_VERSION,
    SOURCE_FACTS_SCHEMA_VERSION,
    VALIDATION_SCHEMA_VERSION,
    Gate2ManagedPrompt,
    Gate2PromptError,
    Gate2PromptUserContext,
    model_call_audit_metadata,
    parse_source_facts_model_output,
    source_facts_provider_schema_hash,
    source_facts_schema_hash,
)
from .gate2_source_fact_stitching import (
    STITCH_RESULT_SCHEMA_VERSION,
    Gate2SourceFactStitcherFactory,
    render_domain_compact_russian_summary,
)
from .gate2_source_unit_segmentation import (
    DERIVED_SOURCE_UNIT_SCHEMA_VERSION,
    SEGMENTATION_PLAN_SCHEMA_VERSION,
    Gate2SourceUnitSegmenterConfig,
    Gate2SourceUnitSegmenterFactory,
    mark_segmentation_selection,
)
from .gate2_source_fact_validation import Gate2SourceFactValidatorFactory


DOMAIN_RUN_SCHEMA_VERSION = "broker_reports_domain_source_fact_extraction_run_v0"
DOMAIN_SUMMARY_SCHEMA_VERSION = "broker_reports_domain_source_fact_extraction_summary_v0"

FACTORY_REQUIRED = (
    "Gate2DomainSourceFactRuntimeFactory.create is the only production domain extraction runtime entrypoint"
)
FORBIDDEN = (
    "Pipes and scripts must not route, call domain models, validate, stitch or persist accepted facts outside this runtime"
)


class Gate2DomainPromptResolver(Protocol):
    def resolve(
        self, domain: str, user_context: Gate2PromptUserContext
    ) -> Gate2ManagedPrompt:
        ...


@dataclass(frozen=True)
class Gate2DomainSourceFactRuntimeConfig:
    model_id: str
    wave: str = "primary"
    run_mode: str = "customer"
    document_batch_start: int = 0
    document_batch_limit: int | None = 1
    source_unit_start: int = 0
    source_unit_limit: int | None = 1
    segmentation_enabled: bool = True
    source_segment_start: int = 0
    source_segment_limit: int | None = 1
    table_segment_max_refs: int = 8
    text_segment_max_refs: int = 12
    domain_allowlist: tuple[str, ...] = ()
    max_repair_attempts: int = 1
    table_max_rows: int = 40
    text_max_chars: int = 6000
    prefer_table_projections: bool = False
    candidate_binding_enabled: bool = False


@dataclass(frozen=True)
class Gate2DomainSourceFactRuntimeResult:
    extraction_run_ref: str
    extraction_run_id: str
    terminal_status: str
    summary_ref: str
    route_refs: list[str]
    segmentation_plan_refs: list[str]
    derived_source_unit_refs: list[str]
    domain_package_refs: list[str]
    source_value_candidate_set_refs: list[str]
    candidate_relation_set_refs: list[str]
    candidate_binding_validation_refs: list[str]
    source_facts_refs: list[str]
    domain_source_facts_refs: list[str]
    validation_refs: list[str]
    raw_output_refs: list[str]
    stitch_result_refs: list[str]
    safe_summary: dict[str, Any]
    compact_russian_summary: str


class Gate2DomainSourceFactRuntimeFactory:
    def __init__(
        self,
        *,
        store: SqliteArtifactStoreAdapter,
        prompt_resolver: Gate2DomainPromptResolver,
        model_client: Gate2StructuredModelClient,
        config: Gate2DomainSourceFactRuntimeConfig,
    ) -> None:
        self.store = store
        self.prompt_resolver = prompt_resolver
        self.model_client = model_client
        self.config = config

    def create(self) -> "Gate2DomainSourceFactRuntimeService":
        if not self.config.model_id:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_unavailable", "Gate 2 domain model id is required"
            )
        if self.config.wave not in {"primary", "non_primary", "all"}:
            raise Gate2SourceFactRuntimeError(
                "gate2_wave_invalid", "Unsupported Gate 2 domain wave"
            )
        if self.config.run_mode not in {"customer", "synthetic"}:
            raise Gate2SourceFactRuntimeError(
                "gate2_run_mode_invalid", "Unsupported Gate 2 domain run mode"
            )
        if self.config.max_repair_attempts not in {0, 1}:
            raise Gate2SourceFactRuntimeError(
                "gate2_repair_policy_invalid", "At most one repair attempt is allowed"
            )
        if self.config.document_batch_start < 0 or (
            self.config.document_batch_limit is not None
            and self.config.document_batch_limit <= 0
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_document_batch_invalid", "Domain document batch is invalid"
            )
        if self.config.source_unit_start < 0 or (
            self.config.source_unit_limit is not None and self.config.source_unit_limit <= 0
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_source_unit_limit_invalid", "Domain source-unit limit is invalid"
            )
        if self.config.source_segment_start < 0 or (
            self.config.source_segment_limit is not None
            and self.config.source_segment_limit <= 0
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_source_segment_limit_invalid",
                "Domain source-segment limit is invalid",
            )
        if (
            self.config.table_segment_max_refs <= 0
            or self.config.text_segment_max_refs <= 0
        ):
            raise Gate2SourceFactRuntimeError(
                "gate2_source_segmentation_budget_invalid",
                "Domain source-segmentation budget is invalid",
            )
        return Gate2DomainSourceFactRuntimeService(
            store=self.store,
            prompt_resolver=self.prompt_resolver,
            model_client=self.model_client,
            config=self.config,
        )


class Gate2DomainSourceFactRuntimeService:
    def __init__(self, *, store, prompt_resolver, model_client, config) -> None:
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
    ) -> Gate2DomainSourceFactRuntimeResult:
        if not context.allow_private or not context.require_source_available:
            raise Gate2SourceFactRuntimeError(
                "gate2_private_resolver_context_required",
                "Gate 2 domain runtime requires private source-available access",
            )
        if prompt_user_context.user_id != context.user_id:
            raise Gate2SourceFactRuntimeError(
                "gate2_authenticated_user_scope_mismatch",
                "Prompt and artifact user contexts differ",
            )
        dcp_record = self.resolver.resolve(domain_context_packet_ref, context)["record"]
        retention_policy = dcp_record.retention_policy
        started_at = utc_now_iso()
        extraction_run_id = f"sfdrun_{stable_digest([context.normalization_run_id, self.config.wave, started_at, new_artifact_id()], length=24)}"
        extraction_run_ref = new_artifact_id()
        run_payload = self._new_run_payload(
            extraction_run_id=extraction_run_id,
            domain_context_packet_ref=domain_context_packet_ref,
            context=context,
            started_at=started_at,
        )
        self._put_record(
            artifact_id=extraction_run_ref,
            artifact_type=DOMAIN_RUN_SCHEMA_VERSION,
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
            readiness = Gate2InputReadinessFactory(
                store=self.store,
                config=Gate2InputReadinessConfig(
                    prefer_table_projections=self.config.prefer_table_projections
                ),
            ).create().audit_and_build(
                domain_context_packet_ref=domain_context_packet_ref,
                context=context,
            )
            if readiness.validation.get("validator_status") != "passed":
                raise Gate2SourceFactRuntimeError(
                    "gate2_input_readiness_failed", "Gate 2 input readiness failed"
                )
        except Gate2SourceFactRuntimeError as exc:
            return self._blocked_result(
                error_code=exc.code,
                extraction_run_ref=extraction_run_ref,
                extraction_run_id=extraction_run_id,
                run_payload=run_payload,
                context=context,
                retention_policy=retention_policy,
            )

        base_packages = [
            copy.deepcopy(package)
            for package in readiness.packages
            if _package_selected(package, self.config.wave)
        ]
        document_refs = sorted(
            {str(item.get("document_ref") or "") for item in base_packages}
        )
        batch_end = (
            None
            if self.config.document_batch_limit is None
            else self.config.document_batch_start + self.config.document_batch_limit
        )
        selected_document_refs = set(
            document_refs[self.config.document_batch_start : batch_end]
        )
        unit_candidates = [
            item
            for item in base_packages
            if str(item.get("document_ref") or "") in selected_document_refs
        ]
        unit_end = (
            None
            if self.config.source_unit_limit is None
            else self.config.source_unit_start + self.config.source_unit_limit
        )
        selected_base_packages = unit_candidates[self.config.source_unit_start : unit_end]
        refs: defaultdict[str, list[str]] = defaultdict(list)
        segmentation_stats: Counter[str] = Counter()
        execution_packages: list[dict[str, Any]] = []
        for package in selected_base_packages:
            package["extraction_run_id"] = extraction_run_id
            package["created_at"] = started_at
            if not self.config.segmentation_enabled:
                execution_packages.append(package)
                continue
            parent_route = Gate2SourceUnitRouterFactory().create().route(package)
            segmentation = Gate2SourceUnitSegmenterFactory(
                Gate2SourceUnitSegmenterConfig(
                    table_max_selected_refs=self.config.table_segment_max_refs,
                    text_max_selected_refs=self.config.text_segment_max_refs,
                )
            ).create().segment(base_package=package, parent_route=parent_route)
            segment_end = (
                None
                if self.config.source_segment_limit is None
                else self.config.source_segment_start
                + self.config.source_segment_limit
            )
            selected_derived = segmentation.derived_packages[
                self.config.source_segment_start : segment_end
            ]
            selected_segment_refs = [
                str(_object(item.get("segmentation")).get("segment_ref") or "")
                for item in selected_derived
            ]
            plan = mark_segmentation_selection(
                segmentation.plan, selected_segment_refs
            )
            plan_ref = new_artifact_id()
            self._persist_segmentation_plan(
                plan_ref=plan_ref,
                plan=plan,
                context=context,
                retention_policy=retention_policy,
            )
            refs["segmentation_plan_refs"].append(plan_ref)
            plan_coverage = _object(plan.get("coverage"))
            segmentation_stats["parent_units_total"] += 1
            segmentation_stats["derived_units_total"] += len(
                segmentation.derived_packages
            )
            segmentation_stats["selected_derived_units_total"] += len(
                selected_derived
            )
            segmentation_stats["deferred_derived_units_total"] += int(
                plan_coverage.get("deferred_derived_units_total") or 0
            )
            if plan.get("parent_source_slice_truncated") is True:
                segmentation_stats["parent_truncated_units_total"] += 1
            if plan_coverage.get("parent_remainder_status") == "pending_gate1_reslice":
                segmentation_stats["pending_parent_remainder_total"] += 1
            for derived in selected_derived:
                derived_ref = new_artifact_id()
                derived["package_artifact_ref"] = derived_ref
                derived["segmentation_plan_artifact_ref"] = plan_ref
                self._persist_derived_source_unit(
                    derived_ref=derived_ref,
                    package=derived,
                    context=context,
                    retention_policy=retention_policy,
                )
                refs["derived_source_unit_refs"].append(derived_ref)
                execution_packages.append(derived)

        accepted_counts: Counter[str] = Counter()
        rejected_counts: Counter[str] = Counter()
        fact_counts: Counter[str] = Counter()
        stitch_results: list[dict[str, Any]] = []
        all_outcomes: list[dict[str, Any]] = []

        for base_package in execution_packages:
            route = Gate2SourceUnitRouterFactory().create().route(base_package)
            route_ref = new_artifact_id()
            self._put_record(
                artifact_id=route_ref,
                artifact_type=ROUTE_SCHEMA_VERSION,
                context=context,
                retention_policy=retention_policy,
                document_id=str(base_package.get("document_ref") or "") or None,
                source_file_ref=None,
                visibility="safe_internal",
                storage_backend="project_artifact_store",
                validation_status="validated",
                payload=route,
                safe_metadata={
                    "route_id": route.get("route_id"),
                    "source_unit_ref": route.get("source_unit_ref"),
                    "selected_total": _object(route.get("coverage")).get("selected_total"),
                    "ambiguous_total": _object(route.get("coverage")).get("ambiguous_total"),
                    "unknown_total": _object(route.get("coverage")).get("unknown_total"),
                },
            )
            refs["route_refs"].append(route_ref)
            domain_packages = Gate2DomainPackageBuilderFactory(
                Gate2DomainPackageBuilderConfig(
                    candidate_binding_enabled=self.config.candidate_binding_enabled
                )
            ).create().build(
                base_package=base_package,
                route=route,
                route_artifact_ref=route_ref,
            )
            if self.config.domain_allowlist:
                domain_packages = [
                    item
                    for item in domain_packages
                    if item.get("extractor_domain") in self.config.domain_allowlist
                ]
            accepted_outputs: list[dict[str, Any]] = []
            rejected_outputs: list[dict[str, Any]] = []
            for domain_package in domain_packages:
                outcome = await self._run_domain_package(
                    package=domain_package,
                    prompt_user_context=prompt_user_context,
                    context=context,
                    retention_policy=retention_policy,
                )
                all_outcomes.append(outcome)
                for key, value in outcome.get("refs", {}).items():
                    refs[key].extend(value)
                if outcome["status"] == "accepted":
                    accepted_counts[outcome["extractor_domain"]] += 1
                    accepted_outputs.append(outcome["stitch_input"])
                    for fact_type, count in outcome["fact_counts"].items():
                        fact_counts[fact_type] += count
                else:
                    rejected_counts[outcome["extractor_domain"]] += 1
                    rejected_outputs.append(outcome["stitch_input"])

            stitch = Gate2SourceFactStitcherFactory().create().stitch(
                extraction_run_id=extraction_run_id,
                route_ref=route_ref,
                route=route,
                accepted_domain_outputs=accepted_outputs,
                rejected_domain_outputs=rejected_outputs,
            )
            stitch_ref = new_artifact_id()
            self._put_record(
                artifact_id=stitch_ref,
                artifact_type=STITCH_RESULT_SCHEMA_VERSION,
                context=context,
                retention_policy=retention_policy,
                document_id=str(base_package.get("document_ref") or "") or None,
                source_file_ref=None,
                visibility="safe_internal",
                storage_backend="project_artifact_store",
                validation_status="validated",
                payload=stitch,
                safe_metadata={
                    "coverage_status": _object(stitch.get("coverage")).get("coverage_status"),
                    "selected_total": _object(stitch.get("coverage")).get("selected_total"),
                    "conflict_total": _object(stitch.get("coverage")).get("conflict_total"),
                    "uncovered_total": _object(stitch.get("coverage")).get("uncovered_total"),
                },
            )
            refs["stitch_result_refs"].append(stitch_ref)
            stitch_results.append(stitch)

        total_rejected = sum(rejected_counts.values())
        has_conflicts = any(item.get("conflicts") for item in stitch_results)
        has_uncovered = any(item.get("uncovered_refs") for item in stitch_results)
        terminal_status = (
            "blocked"
            if not execution_packages
            else "completed_with_rejections"
            if total_rejected or has_conflicts or has_uncovered
            else "completed"
        )
        summary = self._build_summary(
            extraction_run_id=extraction_run_id,
            terminal_status=terminal_status,
            document_refs=document_refs,
            selected_document_refs=selected_document_refs,
            selected_parent_units=len(selected_base_packages),
            selected_units=len(execution_packages),
            truncated_units=sum(
                1
                for item in execution_packages
                if _object(item.get("source_unit")).get("source_slice_truncated") is True
            ),
            parent_truncated_units=sum(
                1
                for item in execution_packages
                if _object(item.get("source_unit")).get(
                    "parent_source_slice_truncated"
                )
                is True
            ),
            bounded_units=sum(
                1
                for item in execution_packages
                if _object(item.get("source_unit")).get("coverage_scope")
                == "complete_within_parent_projection"
            ),
            segmentation_stats=dict(segmentation_stats),
            accepted_counts=accepted_counts,
            rejected_counts=rejected_counts,
            fact_counts=fact_counts,
            stitch_results=stitch_results,
            refs=refs,
        )
        summary_ref = new_artifact_id()
        self._put_record(
            artifact_id=summary_ref,
            artifact_type=DOMAIN_SUMMARY_SCHEMA_VERSION,
            context=context,
            retention_policy=retention_policy,
            document_id=None,
            source_file_ref=None,
            visibility="chat_visible",
            storage_backend="project_artifact_store",
            validation_status="validated",
            payload=summary,
            safe_metadata={
                "terminal_status": terminal_status,
                "accepted_packages": sum(accepted_counts.values()),
                "rejected_packages": total_rejected,
                "facts_total": sum(fact_counts.values()),
            },
        )
        run_payload.update(
            {
                "run_status": terminal_status,
                "segmentation_plan_refs": refs["segmentation_plan_refs"],
                "derived_source_unit_refs": refs["derived_source_unit_refs"],
                "route_refs": refs["route_refs"],
                "domain_package_refs": refs["domain_package_refs"],
                "source_value_candidate_set_refs": refs[
                    "source_value_candidate_set_refs"
                ],
                "candidate_relation_set_refs": refs["candidate_relation_set_refs"],
                "candidate_binding_validation_refs": refs[
                    "candidate_binding_validation_refs"
                ],
                "raw_output_refs": refs["raw_output_refs"],
                "validation_refs": refs["validation_refs"],
                "source_facts_refs": refs["source_facts_refs"],
                "domain_source_facts_refs": refs["domain_source_facts_refs"],
                "stitch_result_refs": refs["stitch_result_refs"],
                "summary_ref": summary_ref,
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
                "selected_parent_units": len(selected_base_packages),
                "selected_units": len(execution_packages),
                "accepted_packages": sum(accepted_counts.values()),
                "rejected_packages": total_rejected,
            },
        )
        compact = render_domain_compact_russian_summary(
            stitch_results=stitch_results,
            accepted_domains=dict(accepted_counts),
            rejected_packages=total_rejected,
            bounded_units=sum(
                1
                for item in execution_packages
                if _object(item.get("source_unit")).get("coverage_scope")
                == "complete_within_parent_projection"
            ),
            pending_parent_remainders=int(
                segmentation_stats.get("pending_parent_remainder_total") or 0
            ),
        )
        return Gate2DomainSourceFactRuntimeResult(
            extraction_run_ref=extraction_run_ref,
            extraction_run_id=extraction_run_id,
            terminal_status=terminal_status,
            summary_ref=summary_ref,
            route_refs=list(refs["route_refs"]),
            segmentation_plan_refs=list(refs["segmentation_plan_refs"]),
            derived_source_unit_refs=list(refs["derived_source_unit_refs"]),
            domain_package_refs=list(refs["domain_package_refs"]),
            source_value_candidate_set_refs=list(
                refs["source_value_candidate_set_refs"]
            ),
            candidate_relation_set_refs=list(refs["candidate_relation_set_refs"]),
            candidate_binding_validation_refs=list(
                refs["candidate_binding_validation_refs"]
            ),
            source_facts_refs=list(refs["source_facts_refs"]),
            domain_source_facts_refs=list(refs["domain_source_facts_refs"]),
            validation_refs=list(refs["validation_refs"]),
            raw_output_refs=list(refs["raw_output_refs"]),
            stitch_result_refs=list(refs["stitch_result_refs"]),
            safe_summary=summary,
            compact_russian_summary=compact,
        )

    async def _run_domain_package(
        self,
        *,
        package: dict[str, Any],
        prompt_user_context: Gate2PromptUserContext,
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
    ) -> dict[str, Any]:
        domain = str(package.get("extractor_domain") or "")
        package_ref = new_artifact_id()
        package["package_artifact_ref"] = package_ref
        package["expected_source_facts_set_id"] = f"sfset_{stable_digest([package.get('extraction_run_id'), package_ref], length=24)}"
        binding_contract_refs = self._persist_candidate_binding_contracts(
            package=package,
            package_ref=package_ref,
            context=context,
            retention_policy=retention_policy,
        )
        try:
            prompt = self.prompt_resolver.resolve(domain, prompt_user_context)
        except Gate2PromptError as exc:
            package["prompt_contract"]["resolution_error_code"] = exc.code
            self._persist_domain_package(
                package_ref=package_ref,
                package=package,
                context=context,
                retention_policy=retention_policy,
                validation_status="blocked",
                warning_codes=[exc.code],
            )
            return {
                "status": "rejected",
                "extractor_domain": domain,
                "fact_counts": {},
                "refs": {
                    "domain_package_refs": [package_ref],
                    **binding_contract_refs,
                },
                "stitch_input": {
                    "extractor_domain": domain,
                    "domain_package_ref": package_ref,
                    "validation_ref": None,
                    "candidate_source_refs": package.get("candidate_source_refs") or [],
                    "error_codes": [exc.code],
                },
            }
        package["prompt_contract"] = prompt.snapshot()
        package["model_id"] = self.config.model_id
        package["expected_candidate_audit"] = model_call_audit_metadata(
            prompt=prompt,
            model_id=self.config.model_id,
            raw_output_artifact_ref=None,
            extraction_attempt_ordinal=1,
            repair_attempt_count=0,
            created_at=str(package.get("created_at") or utc_now_iso()),
        )
        package["expected_repair_candidate_audit"] = model_call_audit_metadata(
            prompt=prompt,
            model_id=self.config.model_id,
            raw_output_artifact_ref=None,
            extraction_attempt_ordinal=2,
            repair_attempt_count=1,
            created_at=str(package.get("created_at") or utc_now_iso()),
        )
        package["output_schema"].update(
            {
                "output_schema_hash": source_facts_schema_hash(),
                "provider_response_schema_hash": source_facts_provider_schema_hash(),
                "provider_union_keyword": "anyOf",
                "schema_validation_required": True,
            }
        )
        package_response_schema_hash = (
            candidate_binding_schema_hash(package)
            if package.get("candidate_binding_mode")
            else source_facts_provider_schema_hash(package)
        )
        package["output_schema"]["package_response_schema_hash"] = package_response_schema_hash
        repair_package = copy.deepcopy(package)
        repair_package["expected_candidate_audit"] = copy.deepcopy(
            package["expected_repair_candidate_audit"]
        )
        package["output_schema"]["repair_package_response_schema_hash"] = (
            candidate_binding_schema_hash(repair_package)
            if repair_package.get("candidate_binding_mode")
            else source_facts_provider_schema_hash(repair_package)
        )
        budget_error = _package_budget_error(package, self.config)
        self._persist_domain_package(
            package_ref=package_ref,
            package=package,
            context=context,
            retention_policy=retention_policy,
            validation_status="blocked" if budget_error else "validated",
            warning_codes=[budget_error] if budget_error else [],
        )
        refs: defaultdict[str, list[str]] = defaultdict(list)
        refs["domain_package_refs"].append(package_ref)
        for key, values in binding_contract_refs.items():
            refs[key].extend(values)
        if budget_error:
            return {
                "status": "rejected",
                "extractor_domain": domain,
                "fact_counts": {},
                "refs": refs,
                "stitch_input": {
                    "extractor_domain": domain,
                    "domain_package_ref": package_ref,
                    "validation_ref": None,
                    "candidate_source_refs": package.get("candidate_source_refs") or [],
                    "error_codes": [budget_error],
                },
            }

        finalized = None
        validation: dict[str, Any] = {}
        validation_ref = ""
        raw_output_ref = ""
        repair_errors: list[dict[str, str]] = []
        for attempt in range(self.config.max_repair_attempts + 1):
            attempt_package = copy.deepcopy(package)
            if attempt == 1:
                attempt_package["expected_candidate_audit"] = copy.deepcopy(
                    package["expected_repair_candidate_audit"]
                )
                attempt_package["repair_context"] = {
                    "schema_version": "gate2_domain_source_fact_repair_context_v0",
                    "repair_attempt_count": 1,
                    "validation_errors": repair_errors,
                    "instructions": (
                        "Regenerate only this domain candidate from the unchanged narrow package. "
                        "Use only allowed refs and do not change routing, issues or assumptions."
                    ),
                }
            response_format = (
                candidate_binding_response_format(attempt_package)
                if attempt_package.get("candidate_binding_mode")
                else domain_source_facts_response_format(attempt_package)
            )
            schema_hash_field = (
                "repair_package_response_schema_hash"
                if attempt == 1
                else "package_response_schema_hash"
            )
            raw_output_ref, raw_payload = await self._execute_model_attempt(
                prompt=prompt,
                package=attempt_package,
                package_ref=package_ref,
                response_format=response_format,
                package_response_schema_hash=_object(package.get("output_schema")).get(schema_hash_field),
                repair_attempt_count=attempt,
                context=context,
                retention_policy=retention_policy,
            )
            refs["raw_output_refs"].append(raw_output_ref)
            validation_ref = new_artifact_id()
            if raw_payload["model_call_status"] == "passed":
                try:
                    if attempt_package.get("candidate_binding_mode"):
                        selection = parse_candidate_binding_model_output(
                            raw_payload["raw_output"]
                        )
                        binding_outcome = (
                            Gate2CandidateBindingRuntimeFactory()
                            .create()
                            .validate_and_materialize(
                                selection=selection,
                                package=attempt_package,
                            )
                        )
                        binding_validation_ref = new_artifact_id()
                        self._persist_candidate_binding_validation(
                            binding_validation_ref=binding_validation_ref,
                            binding_validation=binding_outcome.validation,
                            package=package,
                            package_ref=package_ref,
                            raw_output_ref=raw_output_ref,
                            repair_attempt_count=attempt,
                            context=context,
                            retention_policy=retention_policy,
                        )
                        refs["candidate_binding_validation_refs"].append(
                            binding_validation_ref
                        )
                        if binding_outcome.legacy_candidate is None:
                            validation = _binding_failed_validation(
                                package=package,
                                package_ref=package_ref,
                                binding_validation=binding_outcome.validation,
                            )
                            candidate = None
                        else:
                            candidate = binding_outcome.legacy_candidate
                    else:
                        candidate = parse_source_facts_model_output(
                            raw_payload["raw_output"]
                        )
                    if candidate is None:
                        outcome = None
                    else:
                        candidate = Gate2DomainCandidateFinalizerFactory().create().finalize(
                            candidate=candidate,
                            package=attempt_package,
                        )
                        outcome = Gate2SourceFactValidatorFactory(
                            resolver=self.resolver, context=context
                        ).create().validate(
                            candidate=candidate,
                            package=package,
                            package_artifact_ref=package_ref,
                            raw_output_artifact_ref=raw_output_ref,
                            validation_artifact_ref=validation_ref,
                            prompt=prompt,
                            model_id=self.config.model_id,
                            expected_candidate_audit=_object(
                                attempt_package.get("expected_candidate_audit")
                            ),
                        )
                    if outcome is not None:
                        validation = outcome.validation
                        finalized = outcome.finalized_source_facts
                except (Gate2PromptError, ValueError) as exc:
                    validation = _failed_validation(
                        package,
                        package_ref,
                        str(getattr(exc, "code", str(exc) or "candidate_binding_schema_mismatch")),
                    )
            else:
                validation = _failed_validation(
                    package, package_ref, str(raw_payload.get("error_code") or "gate2_model_call_failed")
                )
            self._persist_validation(
                validation_ref=validation_ref,
                validation=validation,
                package=package,
                context=context,
                retention_policy=retention_policy,
                repair_attempt_count=attempt,
            )
            refs["validation_refs"].append(validation_ref)
            if finalized is not None or raw_payload["model_call_status"] != "passed":
                break
            repair_errors = [
                {
                    "code": str(item.get("code") or "unknown"),
                    "subject": str(item.get("subject") or ""),
                }
                for item in _dict_list(validation.get("errors"))
            ]

        if finalized is None:
            return {
                "status": "rejected",
                "extractor_domain": domain,
                "fact_counts": {},
                "refs": refs,
                "stitch_input": {
                    "extractor_domain": domain,
                    "domain_package_ref": package_ref,
                    "validation_ref": validation_ref,
                    "candidate_source_refs": package.get("candidate_source_refs") or [],
                    "error_codes": sorted(
                        {
                            str(item.get("code") or "unknown")
                            for item in _dict_list(validation.get("errors"))
                        }
                    ),
                },
            }

        source_facts_ref = new_artifact_id()
        self._put_record(
            artifact_id=source_facts_ref,
            artifact_type=SOURCE_FACTS_SCHEMA_VERSION,
            context=context,
            retention_policy=retention_policy,
            document_id=str(package.get("document_ref") or "") or None,
            source_file_ref=None,
            visibility="private_case",
            storage_backend="project_artifact_payload",
            validation_status="validated",
            payload=finalized,
            safe_metadata={
                "extractor_domain": domain,
                "facts_total": len(_dict_list(finalized.get("facts"))),
                "fact_types": sorted(
                    {
                        str(item.get("fact_type") or "unknown")
                        for item in _dict_list(finalized.get("facts"))
                    }
                ),
            },
        )
        refs["source_facts_refs"].append(source_facts_ref)
        wrapper = build_domain_source_facts_wrapper(
            package=package,
            domain_package_ref=package_ref,
            source_facts_ref=source_facts_ref,
            validation_ref=validation_ref,
            finalized_source_facts=finalized,
        )
        wrapper_ref = new_artifact_id()
        self._put_record(
            artifact_id=wrapper_ref,
            artifact_type=DOMAIN_SOURCE_FACTS_SCHEMA_VERSION,
            context=context,
            retention_policy=retention_policy,
            document_id=str(package.get("document_ref") or "") or None,
            source_file_ref=None,
            visibility="safe_internal",
            storage_backend="project_artifact_store",
            validation_status="validated",
            payload=wrapper,
            safe_metadata={
                "extractor_domain": domain,
                "facts_total": len(wrapper["fact_ids"]),
                "validator_status": "passed",
            },
        )
        refs["domain_source_facts_refs"].append(wrapper_ref)
        counts = Counter(
            str(item.get("fact_type") or "unknown")
            for item in _dict_list(finalized.get("facts"))
        )
        return {
            "status": "accepted",
            "extractor_domain": domain,
            "fact_counts": dict(counts),
            "refs": refs,
            "stitch_input": {
                "wrapper_schema_version": DOMAIN_SOURCE_FACTS_SCHEMA_VERSION,
                "validator_status": "passed",
                "extractor_domain": domain,
                "source_facts_ref": source_facts_ref,
                "validation_ref": validation_ref,
                "source_facts": finalized,
            },
        }

    async def _execute_model_attempt(
        self,
        *,
        prompt,
        package,
        package_ref,
        response_format,
        package_response_schema_hash,
        repair_attempt_count,
        context,
        retention_policy,
    ) -> tuple[str, dict[str, Any]]:
        raw_ref = new_artifact_id()
        try:
            result = self.model_client.extract(
                prompt=prompt,
                package=copy.deepcopy(package),
                model_id=self.config.model_id,
                response_format=response_format,
            )
            if inspect.isawaitable(result):
                result = await result
            if not isinstance(result, Gate2StructuredModelResult):
                raise Gate2SourceFactRuntimeError(
                    "gate2_model_invalid_response", "Invalid domain model result"
                )
            raw_payload = {
                "schema_version": RAW_OUTPUT_SCHEMA_VERSION,
                "extraction_run_id": package.get("extraction_run_id"),
                "package_ref": package_ref,
                "document_ref": package.get("document_ref"),
                "source_unit_ref": _object(package.get("source_unit")).get("unit_id"),
                "model_call_status": "passed",
                "error_code": None,
                "raw_output": result.content,
                "structured_output_mode": result.structured_output_mode,
                "response_format_type": result.response_format_type,
                "response_format_schema_mode": result.response_format_schema_mode,
                "fallback_used": result.fallback_used,
                "repair_attempt_count": repair_attempt_count,
                "extraction_attempt_ordinal": repair_attempt_count + 1,
                "provider_response_schema_hash": source_facts_provider_schema_hash(),
                "package_response_schema_hash": package_response_schema_hash,
                "provider_union_keyword": "anyOf",
                "prompt_snapshot": prompt.snapshot(),
                "model_id": self.config.model_id,
                "extractor_domain": package.get("extractor_domain"),
                "created_at": utc_now_iso(),
            }
        except Exception as exc:
            raw_payload = {
                "schema_version": RAW_OUTPUT_SCHEMA_VERSION,
                "extraction_run_id": package.get("extraction_run_id"),
                "package_ref": package_ref,
                "document_ref": package.get("document_ref"),
                "source_unit_ref": _object(package.get("source_unit")).get("unit_id"),
                "model_call_status": "failed",
                "error_code": str(getattr(exc, "code", f"gate2_model_call_failed_{exc.__class__.__name__}")),
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
                "extractor_domain": package.get("extractor_domain"),
                "created_at": utc_now_iso(),
            }
        self._put_record(
            artifact_id=raw_ref,
            artifact_type=RAW_OUTPUT_SCHEMA_VERSION,
            context=context,
            retention_policy=retention_policy,
            document_id=str(package.get("document_ref") or "") or None,
            source_file_ref=None,
            visibility="private_case",
            storage_backend="project_artifact_payload",
            validation_status="validated",
            payload=raw_payload,
            safe_metadata={
                "model_call_status": raw_payload["model_call_status"],
                "error_code": raw_payload["error_code"],
                "extractor_domain": package.get("extractor_domain"),
                "repair_attempt_count": repair_attempt_count,
                "fallback_used": raw_payload["fallback_used"],
            },
        )
        return raw_ref, raw_payload

    def _persist_segmentation_plan(
        self, *, plan_ref, plan, context, retention_policy
    ):
        coverage = _object(plan.get("coverage"))
        self._put_record(
            artifact_id=plan_ref,
            artifact_type=SEGMENTATION_PLAN_SCHEMA_VERSION,
            context=context,
            retention_policy=retention_policy,
            document_id=str(plan.get("document_ref") or "") or None,
            source_file_ref=None,
            visibility="safe_internal",
            storage_backend="project_artifact_store",
            validation_status="validated",
            payload=plan,
            safe_metadata={
                "plan_id": plan.get("plan_id"),
                "parent_source_slice_truncated": plan.get(
                    "parent_source_slice_truncated"
                ),
                "derived_units_total": len(_dict_list(plan.get("segments"))),
                "selected_for_extraction_total": coverage.get(
                    "selected_for_extraction_total"
                ),
                "deferred_derived_units_total": coverage.get(
                    "deferred_derived_units_total"
                ),
                "parent_remainder_status": coverage.get(
                    "parent_remainder_status"
                ),
            },
        )

    def _persist_derived_source_unit(
        self, *, derived_ref, package, context, retention_policy
    ):
        source_unit = _object(package.get("source_unit"))
        slice_record = self.store.get_record_unchecked(
            str(source_unit.get("private_slice_artifact_ref") or "")
        )
        source_file_ref = (
            copy.deepcopy(slice_record.source_file_ref) if slice_record else None
        )
        coverage = _object(package.get("coverage_expectation"))
        self._put_record(
            artifact_id=derived_ref,
            artifact_type=DERIVED_SOURCE_UNIT_SCHEMA_VERSION,
            context=context,
            retention_policy=retention_policy,
            document_id=str(package.get("document_ref") or "") or None,
            source_file_ref=source_file_ref,
            visibility="private_case",
            storage_backend="project_artifact_payload",
            validation_status="validated",
            payload=package,
            safe_metadata={
                "derived_source_unit_ref": source_unit.get("unit_id"),
                "segment_kind": _object(package.get("segmentation")).get(
                    "segment_kind"
                ),
                "selected_total": coverage.get("required_accounting_total"),
                "parent_source_slice_truncated": source_unit.get(
                    "parent_source_slice_truncated"
                ),
                "source_slice_truncated": source_unit.get(
                    "source_slice_truncated"
                ),
                "parent_remainder_status": source_unit.get(
                    "parent_remainder_status"
                ),
            },
        )

    def _persist_candidate_binding_contracts(
        self, *, package, package_ref, context, retention_policy
    ) -> dict[str, list[str]]:
        if not package.get("candidate_binding_mode"):
            return {}
        candidate_set = copy.deepcopy(
            _object(package.get("source_value_candidate_set"))
        )
        relation_set = copy.deepcopy(_object(package.get("candidate_relation_set")))
        candidate_set_ref = new_artifact_id()
        relation_set_ref = new_artifact_id()
        package["source_value_candidate_set_artifact_ref"] = candidate_set_ref
        package["candidate_relation_set_artifact_ref"] = relation_set_ref
        candidate_set["package_artifact_ref"] = package_ref
        relation_set["package_artifact_ref"] = package_ref
        source_unit = _object(package.get("source_unit"))
        slice_record = self.store.get_record_unchecked(
            str(source_unit.get("private_slice_artifact_ref") or "")
        )
        source_file_ref = (
            copy.deepcopy(slice_record.source_file_ref) if slice_record else None
        )
        candidate_kind_counts = dict(
            sorted(
                Counter(
                    str(item.get("candidate_kind") or "unknown")
                    for item in _dict_list(candidate_set.get("candidates"))
                ).items()
            )
        )
        relation_kind_counts = dict(
            sorted(
                Counter(
                    str(item.get("relation_kind") or "unknown")
                    for item in _dict_list(relation_set.get("relations"))
                ).items()
            )
        )
        self._put_record(
            artifact_id=candidate_set_ref,
            artifact_type=CANDIDATE_SET_SCHEMA_VERSION,
            context=context,
            retention_policy=retention_policy,
            document_id=str(package.get("document_ref") or "") or None,
            source_file_ref=source_file_ref,
            visibility="private_case",
            storage_backend="project_artifact_payload",
            validation_status="validated",
            payload=candidate_set,
            safe_metadata={
                "candidate_set_id": candidate_set.get("candidate_set_id"),
                "extractor_domain": package.get("extractor_domain"),
                "candidates_total": len(_dict_list(candidate_set.get("candidates"))),
                "candidate_kind_counts": candidate_kind_counts,
                "validation_status": candidate_set.get("validation_status"),
            },
        )
        self._put_record(
            artifact_id=relation_set_ref,
            artifact_type=RELATION_SET_SCHEMA_VERSION,
            context=context,
            retention_policy=retention_policy,
            document_id=str(package.get("document_ref") or "") or None,
            source_file_ref=source_file_ref,
            visibility="private_case",
            storage_backend="project_artifact_payload",
            validation_status="validated",
            payload=relation_set,
            safe_metadata={
                "relation_set_id": relation_set.get("relation_set_id"),
                "extractor_domain": package.get("extractor_domain"),
                "relations_total": len(_dict_list(relation_set.get("relations"))),
                "relation_kind_counts": relation_kind_counts,
                "validation_status": relation_set.get("validation_status"),
            },
        )
        return {
            "source_value_candidate_set_refs": [candidate_set_ref],
            "candidate_relation_set_refs": [relation_set_ref],
        }

    def _persist_candidate_binding_validation(
        self,
        *,
        binding_validation_ref,
        binding_validation,
        package,
        package_ref,
        raw_output_ref,
        repair_attempt_count,
        context,
        retention_policy,
    ) -> None:
        payload = copy.deepcopy(binding_validation)
        payload.update(
            {
                "package_artifact_ref": package_ref,
                "raw_output_artifact_ref": raw_output_ref,
                "repair_attempt_count": repair_attempt_count,
            }
        )
        self._put_record(
            artifact_id=binding_validation_ref,
            artifact_type=BINDING_VALIDATION_SCHEMA_VERSION,
            context=context,
            retention_policy=retention_policy,
            document_id=str(package.get("document_ref") or "") or None,
            source_file_ref=None,
            visibility="private_case",
            storage_backend="project_artifact_payload",
            validation_status="validated",
            payload=payload,
            safe_metadata={
                "validator_status": binding_validation.get("validator_status"),
                "extractor_domain": package.get("extractor_domain"),
                "errors_count": binding_validation.get("errors_count"),
                "error_code_counts": copy.deepcopy(
                    binding_validation.get("error_code_counts") or {}
                ),
                "repair_attempt_count": repair_attempt_count,
            },
        )

    def _persist_domain_package(self, *, package_ref, package, context, retention_policy, validation_status, warning_codes):
        source_unit = _object(package.get("source_unit"))
        slice_record = self.store.get_record_unchecked(
            str(source_unit.get("private_slice_artifact_ref") or "")
        )
        source_file_ref = copy.deepcopy(slice_record.source_file_ref) if slice_record else None
        self._put_record(
            artifact_id=package_ref,
            artifact_type=DOMAIN_PACKAGE_SCHEMA_VERSION,
            context=context,
            retention_policy=retention_policy,
            document_id=str(package.get("document_ref") or "") or None,
            source_file_ref=source_file_ref,
            visibility="private_case",
            storage_backend="project_artifact_payload",
            validation_status=validation_status,
            payload=package,
            safe_metadata={
                "package_id": package.get("package_id"),
                "extractor_domain": package.get("extractor_domain"),
                "candidate_refs_total": len(_string_list(package.get("candidate_source_refs"))),
                "allowed_fact_types": copy.deepcopy(package.get("allowed_fact_types") or []),
                "budget_status": "passed" if not warning_codes else "blocked",
            },
            warning_codes=warning_codes,
        )

    def _persist_validation(self, *, validation_ref, validation, package, context, retention_policy, repair_attempt_count):
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
                "extractor_domain": package.get("extractor_domain"),
                "accepted_facts_total": len(_string_list(validation.get("accepted_fact_ids"))),
                "rejected_facts_total": len(_string_list(validation.get("rejected_fact_ids"))),
                "error_code_counts": dict(
                    Counter(
                        str(item.get("code") or "unknown")
                        for item in _dict_list(validation.get("errors"))
                    )
                ),
                "repair_attempt_count": repair_attempt_count,
            },
        )

    def _new_run_payload(self, *, extraction_run_id, domain_context_packet_ref, context, started_at):
        return {
            "schema_version": DOMAIN_RUN_SCHEMA_VERSION,
            "extraction_run_id": extraction_run_id,
            "normalization_run_id": context.normalization_run_id,
            "case_id": context.case_id,
            "chat_id": context.chat_id,
            "workspace_model_id": context.workspace_model_id,
            "domain_context_packet_ref": domain_context_packet_ref,
            "run_status": "created",
            "wave": self.config.wave,
            "document_batch": {
                "start": self.config.document_batch_start,
                "limit": self.config.document_batch_limit,
                "source_unit_limit": self.config.source_unit_limit,
                "source_unit_start": self.config.source_unit_start,
            },
            "segmentation": {
                "enabled": self.config.segmentation_enabled,
                "source_segment_start": self.config.source_segment_start,
                "source_segment_limit": self.config.source_segment_limit,
                "table_segment_max_refs": self.config.table_segment_max_refs,
                "text_segment_max_refs": self.config.text_segment_max_refs,
                "policy": "gate2_source_unit_segmentation_v0",
            },
            "domain_allowlist": list(self.config.domain_allowlist),
            "prefer_table_projections": self.config.prefer_table_projections,
            "candidate_binding_enabled": self.config.candidate_binding_enabled,
            "router_policy": "gate2_source_unit_domain_routing_v1",
            "package_policy": "gate2_domain_package_projection_v0",
            "stitch_policy": "gate2_source_fact_stitching_v0",
            "model_id": self.config.model_id,
            "structured_output_policy": {
                "required_mode": "json_schema",
                "strict": True,
                "customer_fallback": "none",
                "max_repair_attempts": self.config.max_repair_attempts,
            },
            "broad_extractor_policy": {
                "customer_default": False,
                "compatibility_or_synthetic_only": True,
            },
            "artifactstore_policy": {
                "system_of_record": True,
                "knowledge_backend_forbidden": True,
                "vectorization_forbidden": True,
            },
            "route_refs": [],
            "segmentation_plan_refs": [],
            "derived_source_unit_refs": [],
            "domain_package_refs": [],
            "source_value_candidate_set_refs": [],
            "candidate_relation_set_refs": [],
            "candidate_binding_validation_refs": [],
            "raw_output_refs": [],
            "validation_refs": [],
            "source_facts_refs": [],
            "domain_source_facts_refs": [],
            "stitch_result_refs": [],
            "summary_ref": None,
            "started_at": started_at,
            "finished_at": None,
        }

    def _build_summary(
        self,
        *,
        extraction_run_id,
        terminal_status,
        document_refs,
        selected_document_refs,
        selected_parent_units,
        selected_units,
        truncated_units,
        parent_truncated_units,
        bounded_units,
        segmentation_stats,
        accepted_counts,
        rejected_counts,
        fact_counts,
        stitch_results,
        refs,
    ):
        coverage = Counter()
        conflict_total = 0
        for item in stitch_results:
            current = _object(item.get("coverage"))
            for field in (
                "selected_total",
                "accepted_fact_owned_total",
                "unknown_total",
                "no_fact_total",
                "conflict_total",
                "uncovered_total",
            ):
                coverage[field] += int(current.get(field) or 0)
            conflict_total += len(_dict_list(item.get("conflicts")))
        typed_facts_total = sum(
            count
            for fact_type, count in fact_counts.items()
            if fact_type != "unknown_source_row"
        )
        pending_parent_remainder_total = int(
            segmentation_stats.get("pending_parent_remainder_total") or 0
        )
        complete_source_scope = (
            truncated_units == 0
            and parent_truncated_units == 0
            and pending_parent_remainder_total == 0
        )
        expansion_ready = (
            terminal_status == "completed"
            and selected_units > 0
            and typed_facts_total > 0
            and complete_source_scope
            and int(coverage.get("uncovered_total") or 0) == 0
            and int(coverage.get("conflict_total") or 0) == 0
        )
        return {
            "schema_version": DOMAIN_SUMMARY_SCHEMA_VERSION,
            "extraction_run_id": extraction_run_id,
            "terminal_status": terminal_status,
            "wave": self.config.wave,
            "candidate_binding_enabled": self.config.candidate_binding_enabled,
            "documents": {
                "wave_total": len(document_refs),
                "selected_total": len(selected_document_refs),
                "deferred_total": len(document_refs) - len(selected_document_refs),
            },
            "source_units": {
                "selected_parent_total": selected_parent_units,
                "selected_total": selected_units,
                "stitched_total": len(stitch_results),
                "truncated_total": truncated_units,
                "parent_truncated_total": parent_truncated_units,
                "bounded_complete_total": bounded_units,
            },
            "segmentation": dict(sorted(segmentation_stats.items())),
            "domain_packages": {
                "total": sum(accepted_counts.values()) + sum(rejected_counts.values()),
                "accepted": sum(accepted_counts.values()),
                "rejected": sum(rejected_counts.values()),
                "accepted_by_domain": dict(sorted(accepted_counts.items())),
                "rejected_by_domain": dict(sorted(rejected_counts.items())),
            },
            "facts_by_type": dict(sorted(fact_counts.items())),
            "facts_total": sum(fact_counts.values()),
            "typed_facts_total": typed_facts_total,
            "coverage": dict(coverage),
            "conflicts_total": conflict_total,
            "artifact_refs": {
                key: len(values) for key, values in sorted(refs.items())
            },
            "gate3_handoff_ready": expansion_ready,
            "ready_for_primary_expansion": expansion_ready,
            "no_tax_declaration_xlsx_work": True,
            "vector_knowledge_guard": {
                "knowledge_rag_used": False,
                "vectorization_performed": False,
                "ordinary_upload_used": False,
                "document_store_write_performed": False,
            },
            "created_at": utc_now_iso(),
        }

    def _blocked_result(self, *, error_code, extraction_run_ref, extraction_run_id, run_payload, context, retention_policy):
        summary = {
            "schema_version": DOMAIN_SUMMARY_SCHEMA_VERSION,
            "extraction_run_id": extraction_run_id,
            "terminal_status": "blocked",
            "error_code": error_code,
            "candidate_binding_enabled": self.config.candidate_binding_enabled,
            "domain_packages": {"total": 0, "accepted": 0, "rejected": 0},
            "facts_total": 0,
            "coverage": {},
            "gate3_handoff_ready": False,
            "ready_for_primary_expansion": False,
            "no_tax_declaration_xlsx_work": True,
            "vector_knowledge_guard": {
                "knowledge_rag_used": False,
                "vectorization_performed": False,
                "ordinary_upload_used": False,
                "document_store_write_performed": False,
            },
            "created_at": utc_now_iso(),
        }
        summary_ref = new_artifact_id()
        self._put_record(
            artifact_id=summary_ref,
            artifact_type=DOMAIN_SUMMARY_SCHEMA_VERSION,
            context=context,
            retention_policy=retention_policy,
            document_id=None,
            source_file_ref=None,
            visibility="chat_visible",
            storage_backend="project_artifact_store",
            validation_status="validated",
            payload=summary,
            safe_metadata={"terminal_status": "blocked", "error_code": error_code},
        )
        run_payload.update({"run_status": "blocked", "summary_ref": summary_ref, "finished_at": utc_now_iso()})
        self._replace_run_record(
            artifact_id=extraction_run_ref,
            payload=run_payload,
            context=context,
            retention_policy=retention_policy,
            safe_metadata={"run_status": "blocked", "error_code": error_code, "wave": self.config.wave},
        )
        return Gate2DomainSourceFactRuntimeResult(
            extraction_run_ref=extraction_run_ref,
            extraction_run_id=extraction_run_id,
            terminal_status="blocked",
            summary_ref=summary_ref,
            route_refs=[],
            segmentation_plan_refs=[],
            derived_source_unit_refs=[],
            domain_package_refs=[],
            source_value_candidate_set_refs=[],
            candidate_relation_set_refs=[],
            candidate_binding_validation_refs=[],
            source_facts_refs=[],
            domain_source_facts_refs=[],
            validation_refs=[],
            raw_output_refs=[],
            stitch_result_refs=[],
            safe_summary=summary,
            compact_russian_summary="Gate 2 заблокирован: безопасное извлечение не начато.",
        )

    def _replace_run_record(self, *, artifact_id, payload, context, retention_policy, safe_metadata):
        self._put_record(
            artifact_id=artifact_id,
            artifact_type=DOMAIN_RUN_SCHEMA_VERSION,
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

    def _put_record(self, *, artifact_id, artifact_type, context, retention_policy, document_id, source_file_ref, visibility, storage_backend, validation_status, payload, safe_metadata, warning_codes=None) -> ArtifactRecord:
        return self.store.put_record(
            ArtifactRecord(
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
                    visibility=visibility, validation_status=validation_status
                ),
                payload_kind="json_file" if storage_backend == "project_artifact_payload" else "inline_json",
                payload=payload,
                safe_metadata=safe_metadata,
                warning_codes=warning_codes or [],
            )
        )


def _failed_validation(package: dict[str, Any], package_ref: str, code: str) -> dict[str, Any]:
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
        "coverage": {},
        "issue_carry_forward": {"allowed_issue_refs": package.get("allowed_issue_refs") or []},
        "privacy_status": "passed",
        "boundary_status": "passed",
        "prompt_schema_model_audit": {},
        "validated_at": utc_now_iso(),
    }


def _binding_failed_validation(
    *,
    package: dict[str, Any],
    package_ref: str,
    binding_validation: dict[str, Any],
) -> dict[str, Any]:
    value = _failed_validation(
        package,
        package_ref,
        "candidate_binding_validation_failed",
    )
    value["errors"] = copy.deepcopy(
        _dict_list(binding_validation.get("errors"))
    ) or value["errors"]
    value["candidate_binding_validation"] = {
        "schema_version": binding_validation.get("schema_version"),
        "candidate_set_id": binding_validation.get("candidate_set_id"),
        "relation_set_id": binding_validation.get("relation_set_id"),
        "error_code_counts": copy.deepcopy(
            binding_validation.get("error_code_counts") or {}
        ),
    }
    return value


def _package_selected(package: dict[str, Any], wave: str) -> bool:
    roles = set(_string_list(package.get("source_bucket_roles")))
    if wave == "primary":
        return "primary_source_extraction_refs" in roles
    if wave == "non_primary":
        return bool(roles & {"secondary_source_extraction_refs", "duplicate_or_non_primary_refs"})
    return bool(roles & {"primary_source_extraction_refs", "secondary_source_extraction_refs", "duplicate_or_non_primary_refs"})


def _package_budget_error(package: dict[str, Any], config: Gate2DomainSourceFactRuntimeConfig) -> str | None:
    unit = _object(package.get("source_unit"))
    projection = _object(unit.get("normalized_source_projection"))
    if unit.get("unit_kind") == "table_row_window":
        rows = projection.get("cells") if isinstance(projection.get("cells"), list) else []
        if len(rows) > config.table_max_rows:
            return "gate2_domain_table_package_budget_exceeded"
    elif len(str(projection.get("text") or "")) > config.text_max_chars:
        return "gate2_domain_text_package_budget_exceeded"
    return None


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)] if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value or [] if item is not None and str(item)] if isinstance(value, list) else []
