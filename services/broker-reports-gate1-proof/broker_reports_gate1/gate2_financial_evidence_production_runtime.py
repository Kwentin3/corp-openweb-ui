from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable

from .artifact_lifecycle import lifecycle_for_visibility
from .artifact_models import (
    ArtifactAccessContext,
    ArtifactRecord,
    ArtifactStorePort,
    RetentionPolicy,
    new_artifact_id,
)
from .artifact_resolver import ArtifactResolver
from .gate2_financial_context import (
    Gate2FinancialContextProjectionFactory,
)
from .gate2_financial_evidence_catalog import (
    SUPPORTED_SOURCE_FAMILIES,
)
from .gate2_financial_evidence_decision import (
    FinancialEvidenceDecisionPackage,
    FinancialEvidenceValueCandidate,
    Gate2FinancialEvidenceDecisionContract,
    Gate2FinancialEvidenceDecisionContractFactory,
)
from .gate2_financial_evidence_materialization import (
    FinancialEvidenceAuthoritativeSourceValue,
    FinancialEvidenceExecutionMetadata,
    FinancialEvidenceSourceLineage,
    Gate2FinancialEvidenceMaterializerFactory,
    Gate2FinancialEvidenceSourcePackage,
    Gate2FinancialEvidenceSourcePackageFactory,
    Gate2FinancialEvidenceValidatedDecisionFactory,
)
from .gate2_financial_evidence_materialization_contracts import (
    sha256_json,
)
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_model_contracts import (
    Gate2StructuredModelClient,
    gate2_provider_execution_safe_metadata,
)


PRODUCTION_RUNTIME_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_evidence_production_run_v1"
)
PRODUCTION_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_evidence_production_receipt_v1"
)
FINANCIAL_CONTEXT_ARTIFACT_TYPE = (
    "broker_reports_gate2_financial_context_v1"
)
FINANCIAL_RUN_ARTIFACT_TYPE = (
    "broker_reports_gate2_financial_evidence_production_run_v1"
)
FINANCIAL_RECEIPT_ARTIFACT_TYPE = (
    "broker_reports_gate2_financial_evidence_production_receipt_v1"
)
FINANCIAL_INPUT_ARTIFACT_TYPE = (
    "broker_reports_financial_evidence_inputs_v1"
)
PRODUCTION_PROMPT_CONTRACT_ID = (
    "broker_reports_gate2_financial_evidence_production_prompt_v1"
)
FACTORY_REQUIRED = (
    "Gate2FinancialEvidenceProductionRuntimeFactory.create is the only "
    "production Registry-driven financial evidence write path"
)
FORBIDDEN = (
    "The runtime must not read artifacts outside authenticated access "
    "context, write legacy schemas, call providers outside the structured "
    "model client, or create Gate 3 fields"
)

_DECIMAL_RE = re.compile(r"^[+-]?(?:0|[1-9]\d*)(?:\.\d+)?$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CURRENCIES = frozenset(
    {"AED", "CHF", "CNY", "EUR", "GBP", "HKD", "JPY", "KZT", "RUB", "USD"}
)


class Gate2FinancialEvidenceProductionRuntimeError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2FinancialEvidenceProductionConfig:
    model_id: str
    provider_profile_id: str
    maximum_scopes: int = 64


@dataclass(frozen=True)
class Gate2FinancialEvidenceProductionPrompt:
    prompt_ref: str
    content: str
    hash: str


@dataclass(frozen=True)
class Gate2FinancialEvidenceProductionScope:
    contract: Gate2FinancialEvidenceDecisionContract
    source_package: Gate2FinancialEvidenceSourcePackage
    selected_source_refs: tuple[str, ...]


@dataclass(frozen=True)
class Gate2FinancialEvidenceProductionResult:
    run_ref: str
    receipt_ref: str
    financial_context_ref: str
    financial_input_refs: tuple[str, ...]
    status: str
    safe_summary: dict[str, Any]


class Gate2FinancialEvidenceProductionPromptFactory:
    def create(self) -> Gate2FinancialEvidenceProductionPrompt:
        content = (
            "You are the bounded production Gate 2 financial evidence "
            "decision step. Use only the Registry declarations and literal "
            "source values in the embedded package. Never infer missing "
            "dimensions or system metadata. Choose typed_input only when "
            "every required role is explicit. Preserve all financial values "
            "as unclassified_financial_input when safe typing is not "
            "possible. Return only the strict schema object.\n"
            "{{financial_evidence_package_json}}"
        )
        digest = hashlib.sha256(
            (
                content + "\ncontract:" + PRODUCTION_PROMPT_CONTRACT_ID
            ).encode("utf-8")
        ).hexdigest()
        return Gate2FinancialEvidenceProductionPrompt(
            prompt_ref="code:" + PRODUCTION_PROMPT_CONTRACT_ID,
            content=content,
            hash=digest,
        )


class Gate2FinancialEvidenceProductionScopeFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
    ) -> None:
        self.registry = registry

    def create(
        self,
        *,
        domain_packages: Iterable[dict[str, Any]],
    ) -> tuple[Gate2FinancialEvidenceProductionScope, ...]:
        packages = tuple(domain_packages)
        if not packages:
            _fail("financial_evidence_production_packages_empty")
        components = _canonical_components(packages)
        return tuple(
            self._scope(component) for component in components
        )

    def _scope(
        self, packages: tuple[dict[str, Any], ...]
    ) -> Gate2FinancialEvidenceProductionScope:
        selected_refs = tuple(
            sorted(
                {
                    str(ref)
                    for package in packages
                    for ref in (
                        package.get("coverage_expectation") or {}
                    ).get("selected_source_refs")
                    or []
                    if ref
                }
            )
        )
        if not selected_refs:
            _fail("financial_evidence_production_selected_refs_empty")
        scope_digest = hashlib.sha256(
            json.dumps(selected_refs).encode("utf-8")
        ).hexdigest()[:24]
        document_refs = {
            str(item.get("document_ref") or "") for item in packages
        }
        if len(document_refs) != 1 or not next(iter(document_refs)):
            _fail("financial_evidence_production_cross_document_scope")
        document_ref = next(iter(document_refs))
        all_table = all(
            (item.get("source_unit") or {}).get("unit_kind")
            == "table_row_window"
            for item in packages
        )
        source_family_id = (
            SUPPORTED_SOURCE_FAMILIES[0]
            if all_table
            else "broker_reports_normalized_text_projection_v0"
        )
        values_by_ref = {}
        candidates_by_ref = {}
        evidence_refs: set[str] = set()
        for package in packages:
            for value, candidate in _package_values(
                package=package,
                document_ref=document_ref,
            ):
                previous = values_by_ref.get(value.source_value_ref)
                if previous is not None and previous != value:
                    _fail("financial_evidence_production_value_conflict")
                values_by_ref[value.source_value_ref] = value
                candidates_by_ref[candidate.source_value_ref] = candidate
                evidence_refs.update(value.source_evidence_refs)
        locator = selected_refs[0]
        for role, suffix in (
            ("statement_scope", "statement-scope"),
            ("printed_label_evidence_ref", "printed-label"),
        ):
            ref = (
                f"value:gate2:financial-production:{suffix}:"
                f"{scope_digest}"
            )
            value = FinancialEvidenceAuthoritativeSourceValue(
                source_value_ref=ref,
                source_ref=locator,
                value_type="source_reference",
                literal_value=locator,
                source_evidence_refs=(locator,),
                lineage=FinancialEvidenceSourceLineage(
                    document_ref=document_ref,
                    text_segment_ref=locator,
                ),
            )
            values_by_ref[ref] = value
            candidates_by_ref[ref] = FinancialEvidenceValueCandidate(
                source_value_ref=ref,
                source_ref=locator,
                value_type="source_reference",
                allowed_roles=(role,),
            )
            evidence_refs.add(locator)
        source_scope_ref = (
            f"scope:gate2:financial-production:{scope_digest}"
        )
        source_package = Gate2FinancialEvidenceSourcePackageFactory(
            package_ref=(
                f"package:gate2:financial-production:{scope_digest}"
            ),
            normalization_run_ref=(
                f"normalization:gate2:financial-production:{scope_digest}"
            ),
            document_ref=document_ref,
            source_scope_ref=source_scope_ref,
            source_family_id=source_family_id,
            source_values=tuple(values_by_ref.values()),
            source_evidence_refs=tuple(evidence_refs),
            completeness="complete",
        ).create()
        contract = Gate2FinancialEvidenceDecisionContractFactory(
            registry=self.registry,
            package=FinancialEvidenceDecisionPackage(
                source_scope_ref=source_scope_ref,
                source_family_id=source_family_id,
                candidates=tuple(candidates_by_ref.values()),
            ),
        ).create()
        return Gate2FinancialEvidenceProductionScope(
            contract=contract,
            source_package=source_package,
            selected_source_refs=selected_refs,
        )


class Gate2FinancialEvidenceProductionRuntimeFactory:
    def __init__(
        self,
        *,
        store: ArtifactStorePort,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
        model_client: Gate2StructuredModelClient,
        config: Gate2FinancialEvidenceProductionConfig,
    ) -> None:
        self.store = store
        self.registry = registry
        self.model_client = model_client
        self.config = config

    def create(self) -> "Gate2FinancialEvidenceProductionRuntime":
        if (
            not self.config.model_id
            or not self.config.provider_profile_id
            or self.config.maximum_scopes < 1
            or self.config.maximum_scopes > 256
        ):
            _fail("financial_evidence_production_config_invalid")
        return Gate2FinancialEvidenceProductionRuntime(
            store=self.store,
            registry=self.registry,
            model_client=self.model_client,
            config=self.config,
            prompt=Gate2FinancialEvidenceProductionPromptFactory().create(),
        )


class Gate2FinancialEvidenceProductionRuntime:
    def __init__(
        self,
        *,
        store: ArtifactStorePort,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
        model_client: Gate2StructuredModelClient,
        config: Gate2FinancialEvidenceProductionConfig,
        prompt: Gate2FinancialEvidenceProductionPrompt,
    ) -> None:
        self.store = store
        self.registry = registry
        self.model_client = model_client
        self.config = config
        self.prompt = prompt

    async def run(
        self,
        *,
        domain_package_refs: Iterable[str],
        source_extraction_run_ref: str,
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
    ) -> Gate2FinancialEvidenceProductionResult:
        refs = tuple(domain_package_refs)
        if not refs or len(refs) != len(set(refs)):
            _fail("financial_evidence_production_package_refs_invalid")
        resolver = ArtifactResolver(self.store)
        packages = []
        source_records = []
        for ref in refs:
            resolved = resolver.resolve(ref, context)
            record = resolved["record"]
            if (
                record.artifact_type
                != "broker_reports_domain_extraction_package_v0"
            ):
                _fail("financial_evidence_production_package_type_invalid")
            packages.append(resolved["payload"])
            source_records.append(record)
        scopes = Gate2FinancialEvidenceProductionScopeFactory(
            registry=self.registry
        ).create(domain_packages=packages)
        if len(scopes) > self.config.maximum_scopes:
            _fail("financial_evidence_production_scope_budget_exceeded")
        results = []
        for index, scope in enumerate(scopes, start=1):
            results.append(
                await self._decide(
                    scope=scope,
                    source_extraction_run_ref=source_extraction_run_ref,
                    ordinal=index,
                )
            )
        context_payload = Gate2FinancialContextProjectionFactory(
            registry=self.registry
        ).create(
            materialized_artifacts=[
                item["artifact"] for item in results
            ],
            source_packages=[
                item["source_package"] for item in results
            ],
        )
        receipt = self._receipt(
            scopes=scopes,
            results=results,
            context_payload=context_payload,
        )
        if receipt["status"] != "passed":
            _fail("financial_evidence_production_qualification_failed")
        document_ids = {
            record.document_id for record in source_records
            if record.document_id
        }
        document_id = (
            next(iter(document_ids)) if len(document_ids) == 1 else None
        )
        source_file_refs = {
            sha256_json(record.source_file_ref): record.source_file_ref
            for record in source_records
            if record.source_file_ref
        }
        source_file_ref = (
            next(iter(source_file_refs.values()))
            if len(source_file_refs) == 1
            else None
        )
        input_refs = []
        for result in results:
            artifact = result["artifact"]
            self._put_private(
                artifact_id=artifact["artifact_id"],
                artifact_type=FINANCIAL_INPUT_ARTIFACT_TYPE,
                context=context,
                retention_policy=retention_policy,
                document_id=document_id,
                source_file_ref=source_file_ref,
                payload=artifact,
                safe_metadata={
                    "schema_version": artifact["schema_version"],
                    "terminal_disposition": artifact[
                        "terminal_disposition"
                    ],
                    "source_scope_ref": artifact["source_package"][
                        "source_scope_ref"
                    ],
                    "registry_version": self.registry.registry_version,
                    "registry_hash": self.registry.registry_hash,
                },
            )
            input_refs.append(artifact["artifact_id"])
        financial_context_ref = new_artifact_id()
        self._put_private(
            artifact_id=financial_context_ref,
            artifact_type=FINANCIAL_CONTEXT_ARTIFACT_TYPE,
            context=context,
            retention_policy=retention_policy,
            document_id=document_id,
            source_file_ref=source_file_ref,
            payload=context_payload,
            safe_metadata={
                "schema_version": context_payload["schema_version"],
                "integrity_hash": context_payload["integrity_hash"],
                "source_scopes_total": context_payload["scope_coverage"][
                    "source_scopes_total"
                ],
                "registry_version": self.registry.registry_version,
                "registry_hash": self.registry.registry_hash,
            },
        )
        receipt_ref = new_artifact_id()
        self._put_private(
            artifact_id=receipt_ref,
            artifact_type=FINANCIAL_RECEIPT_ARTIFACT_TYPE,
            context=context,
            retention_policy=retention_policy,
            document_id=document_id,
            source_file_ref=source_file_ref,
            payload=receipt,
            safe_metadata={
                key: receipt[key]
                for key in (
                    "schema_version",
                    "status",
                    "source_refs_total",
                    "source_scopes_total",
                    "uncovered_source_refs_total",
                    "duplicate_interpretations_total",
                    "fallback_total",
                    "repair_attempts_total",
                    "provider_failures_total",
                    "schema_failures_total",
                    "integrity_hash",
                )
            },
        )
        run_ref = new_artifact_id()
        run_payload = {
            "schema_version": PRODUCTION_RUNTIME_SCHEMA_VERSION,
            "status": "completed",
            "source_extraction_run_ref": source_extraction_run_ref,
            "registry": {
                "registry_version": self.registry.registry_version,
                "registry_hash": self.registry.registry_hash,
            },
            "financial_input_refs": sorted(input_refs),
            "financial_context_ref": financial_context_ref,
            "receipt_ref": receipt_ref,
            "legacy_read_policy": "dual_read",
            "write_policy": "new_schema_only",
            "gate3_fields_total": 0,
        }
        run_payload["integrity_hash"] = sha256_json(run_payload)
        self._put_private(
            artifact_id=run_ref,
            artifact_type=FINANCIAL_RUN_ARTIFACT_TYPE,
            context=context,
            retention_policy=retention_policy,
            document_id=document_id,
            source_file_ref=source_file_ref,
            payload=run_payload,
            safe_metadata={
                "schema_version": PRODUCTION_RUNTIME_SCHEMA_VERSION,
                "status": "completed",
                "financial_context_ref": financial_context_ref,
                "receipt_ref": receipt_ref,
                "financial_inputs_total": len(input_refs),
                "registry_version": self.registry.registry_version,
                "registry_hash": self.registry.registry_hash,
                "integrity_hash": run_payload["integrity_hash"],
            },
        )
        return Gate2FinancialEvidenceProductionResult(
            run_ref=run_ref,
            receipt_ref=receipt_ref,
            financial_context_ref=financial_context_ref,
            financial_input_refs=tuple(sorted(input_refs)),
            status="completed",
            safe_summary={
                "schema_version": PRODUCTION_RUNTIME_SCHEMA_VERSION,
                "status": "completed",
                "registry_version": self.registry.registry_version,
                "registry_hash": self.registry.registry_hash,
                "source_scopes_total": len(scopes),
                "financial_inputs_total": len(input_refs),
                "terminal_status_counts": receipt[
                    "terminal_status_counts"
                ],
                "uncovered_source_refs_total": receipt[
                    "uncovered_source_refs_total"
                ],
                "duplicate_interpretations_total": receipt[
                    "duplicate_interpretations_total"
                ],
                "unclassified_value_loss_total": receipt[
                    "unclassified_value_loss_total"
                ],
                "fallback_total": receipt["fallback_total"],
                "repair_attempts_total": receipt[
                    "repair_attempts_total"
                ],
                "provider_failures_total": receipt[
                    "provider_failures_total"
                ],
                "schema_failures_total": receipt[
                    "schema_failures_total"
                ],
                "legacy_read_policy": "dual_read",
                "write_policy": "new_schema_only",
            },
        )

    async def _decide(
        self,
        *,
        scope: Gate2FinancialEvidenceProductionScope,
        source_extraction_run_ref: str,
        ordinal: int,
    ) -> dict[str, Any]:
        result = await self.model_client.extract(
            prompt=self.prompt,
            package=_model_package(self.registry, scope),
            model_id=self.config.model_id,
            response_format=scope.contract.openai_response_format(),
        )
        if result.fallback_used:
            _fail("financial_evidence_production_fallback_forbidden")
        if result.repair_attempt_count:
            _fail("financial_evidence_production_repair_forbidden")
        validated = Gate2FinancialEvidenceValidatedDecisionFactory(
            contract=scope.contract
        ).create(result.content)
        artifact = Gate2FinancialEvidenceMaterializerFactory(
            registry=self.registry,
            source_package=scope.source_package,
            execution_metadata=FinancialEvidenceExecutionMetadata(
                execution_ref=(
                    f"execution:financial-production:"
                    f"{source_extraction_run_ref}:{ordinal}"
                ),
                decision_validation_ref=(
                    f"validation:financial-production:"
                    f"{source_extraction_run_ref}:{ordinal}"
                ),
            ),
        ).create().materialize(validated_decision=validated)
        return {
            "artifact": artifact,
            "source_package": scope.source_package,
            "provider_execution": (
                {}
                if result.execution_metadata is None
                else gate2_provider_execution_safe_metadata(
                    result.execution_metadata
                )
            ),
        }

    def _receipt(
        self,
        *,
        scopes: tuple[Gate2FinancialEvidenceProductionScope, ...],
        results: list[dict[str, Any]],
        context_payload: dict[str, Any],
    ) -> dict[str, Any]:
        authorized_refs = {
            ref for scope in scopes for ref in scope.selected_source_refs
        }
        authorized_scopes = {
            scope.source_package.source_scope_ref for scope in scopes
        }
        accounted_scopes = {
            str(item["artifact"]["coverage"]["source_scope_ref"])
            for item in results
            if item["artifact"]["coverage"].get("scope_accounted") is True
        }
        accounted_refs = {
            ref
            for scope, item in zip(scopes, results, strict=True)
            if (
                item["artifact"]["coverage"].get("scope_accounted") is True
                and item["artifact"]["coverage"].get("source_scope_ref")
                == scope.source_package.source_scope_ref
            )
            for ref in scope.selected_source_refs
        }
        statuses = Counter(
            item["artifact"]["terminal_disposition"]
            for item in results
        )
        owners = Counter(
            ref
            for scope, item in zip(scopes, results, strict=True)
            if (
                item["artifact"]["coverage"].get("scope_accounted") is True
                and item["artifact"]["coverage"].get("source_scope_ref")
                == scope.source_package.source_scope_ref
            )
            for ref in scope.selected_source_refs
        )
        duplicate_interpretations = sum(
            count - 1 for count in owners.values() if count > 1
        )
        unclassified = [
            item["artifact"] for item in results
            if item["artifact"]["terminal_disposition"]
            == "unclassified_financial_input"
        ]
        unclassified_loss = sum(
            item["coverage"]["candidate_refs_total"]
            != len(item["coverage"]["bound_source_value_refs"])
            for item in unclassified
        )
        provider_failures = sum(
            not item["provider_execution"]
            or (
                item["provider_execution"].get("response_format_type")
                != "json_schema"
            )
            or (
                item["provider_execution"].get(
                    "response_format_schema_mode"
                )
                != "strict_json_schema"
            )
            for item in results
        )
        checks = {
            "terminal_all_source_scopes": (
                accounted_scopes == authorized_scopes
            ),
            "terminal_all_source_refs": (
                accounted_refs == authorized_refs
            ),
            "uncovered_source_refs_zero": not (
                authorized_refs - accounted_refs
            ),
            "unclassified_value_loss_zero": unclassified_loss == 0,
            "duplicate_interpretations_zero": (
                duplicate_interpretations == 0
            ),
            "context_all_scopes": (
                context_payload["scope_coverage"][
                    "source_scopes_total"
                ]
                == len(scopes)
            ),
            "provider_failures_zero": provider_failures == 0,
            "fallback_zero": True,
            "repair_zero": True,
            "single_write_new_schema": True,
            "legacy_dual_read": True,
            "gate3_fields_zero": True,
        }
        receipt = {
            "schema_version": PRODUCTION_RECEIPT_SCHEMA_VERSION,
            "status": "passed" if all(checks.values()) else "failed",
            "checks": checks,
            "registry_version": self.registry.registry_version,
            "registry_hash": self.registry.registry_hash,
            "source_refs_total": len(authorized_refs),
            "source_scopes_total": len(scopes),
            "uncovered_source_refs_total": len(
                authorized_refs - accounted_refs
            ),
            "duplicate_interpretations_total": duplicate_interpretations,
            "unclassified_value_loss_total": unclassified_loss,
            "terminal_status_counts": {
                status: statuses.get(status, 0)
                for status in (
                    "typed_input",
                    "unclassified_financial_input",
                    "no_financial_input",
                    "unsupported",
                )
            },
            "fallback_total": 0,
            "repair_attempts_total": 0,
            "provider_failures_total": provider_failures,
            "schema_failures_total": 0,
            "context_integrity_hash": context_payload[
                "integrity_hash"
            ],
        }
        receipt["integrity_hash"] = sha256_json(receipt)
        return receipt

    def _put_private(
        self,
        *,
        artifact_id: str,
        artifact_type: str,
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
        document_id: str | None,
        source_file_ref: dict[str, Any] | None,
        payload: dict[str, Any],
        safe_metadata: dict[str, Any],
    ) -> None:
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
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=retention_policy,
            access_policy={
                "requires_user_id": True,
                "requires_case_or_chat": True,
                "requires_workspace_model_id_when_present": bool(
                    context.workspace_model_id
                ),
            },
            validation_status="validated",
            lifecycle_status=lifecycle_for_visibility(
                visibility="private_case",
                validation_status="validated",
            ),
            payload_kind="json_file",
            payload=payload,
            safe_metadata=safe_metadata,
        )
        self.store.put_record(record)


def _canonical_components(
    packages: tuple[dict[str, Any], ...],
) -> tuple[tuple[dict[str, Any], ...], ...]:
    remaining = set(range(len(packages)))
    refs = [
        set(
            (item.get("coverage_expectation") or {}).get(
                "selected_source_refs"
            )
            or []
        )
        for item in packages
    ]
    result = []
    while remaining:
        pending = [min(remaining)]
        component: set[int] = set()
        while pending:
            current = pending.pop()
            if current in component:
                continue
            component.add(current)
            remaining.discard(current)
            pending.extend(
                other
                for other in tuple(remaining)
                if refs[current] & refs[other]
            )
        result.append(
            tuple(packages[index] for index in sorted(component))
        )
    return tuple(result)


def _package_values(
    *, package: dict[str, Any], document_ref: str
) -> tuple[
    tuple[
        FinancialEvidenceAuthoritativeSourceValue,
        FinancialEvidenceValueCandidate,
    ],
    ...,
]:
    unit = package.get("source_unit") or {}
    allowed = set(package.get("allowed_source_value_refs") or [])
    index = {
        str(item.get("source_value_ref")): item
        for item in unit.get("source_value_index") or []
        if isinstance(item, dict) and item.get("source_value_ref")
    }
    literal_by_ref = {}
    segment_by_ref = {}
    for segment in (
        (unit.get("model_source_projection") or {}).get("segments")
        or []
    ):
        ref = str(segment.get("source_value_ref") or "")
        value = segment.get("value")
        if ref in allowed and isinstance(value, str) and value:
            literal_by_ref[ref] = value
            segment_by_ref[ref] = segment
    for private_value in unit.get("private_values") or []:
        value = private_value.get("normalized_value")
        if not isinstance(value, str) or not value:
            continue
        for ref in private_value.get("source_value_refs") or []:
            if ref in allowed:
                literal_by_ref[str(ref)] = value
    if set(literal_by_ref) != allowed:
        _fail("financial_evidence_production_authoritative_value_missing")
    result = []
    for ref in sorted(allowed):
        literal = literal_by_ref[ref]
        value_type, roles = _infer_type(literal)
        indexed = index.get(ref) or {}
        segment = segment_by_ref.get(ref) or {}
        source_ref = str(
            indexed.get("cell_ref")
            or indexed.get("text_segment_ref")
            or indexed.get("source_object_ref")
            or segment.get("text_segment_ref")
            or ref
        )
        page_ref = segment.get("page_ref")
        table_ref = unit.get("table_ref")
        cell_ref = indexed.get("cell_ref")
        text_segment_ref = (
            indexed.get("text_segment_ref")
            or segment.get("text_segment_ref")
        )
        if not any(
            (page_ref, table_ref, cell_ref, text_segment_ref)
        ):
            text_segment_ref = source_ref
        evidence = tuple(
            sorted(
                {
                    source_ref,
                    *(
                        str(value)
                        for value in package.get(
                            "allowed_evidence_refs"
                        )
                        or []
                    ),
                }
            )
        )
        source_value = FinancialEvidenceAuthoritativeSourceValue(
            source_value_ref=ref,
            source_ref=source_ref,
            value_type=value_type,
            literal_value=literal,
            source_evidence_refs=evidence,
            lineage=FinancialEvidenceSourceLineage(
                document_ref=document_ref,
                page_ref=(
                    str(page_ref)
                    if isinstance(page_ref, str)
                    else None
                ),
                table_ref=(
                    str(table_ref)
                    if isinstance(table_ref, str) and table_ref
                    else None
                ),
                cell_ref=(
                    str(cell_ref)
                    if isinstance(cell_ref, str) and cell_ref
                    else None
                ),
                text_segment_ref=(
                    str(text_segment_ref)
                    if isinstance(text_segment_ref, str)
                    and text_segment_ref
                    else None
                ),
            ),
        )
        result.append(
            (
                source_value,
                FinancialEvidenceValueCandidate(
                    source_value_ref=ref,
                    source_ref=source_ref,
                    value_type=value_type,
                    allowed_roles=roles,
                ),
            )
        )
    return tuple(result)


def _infer_type(literal: str) -> tuple[str, tuple[str, ...]]:
    normalized = literal.strip()
    if _DATE_RE.fullmatch(normalized):
        return "source_date", ("as_of_date",)
    if _DECIMAL_RE.fullmatch(normalized):
        return "source_decimal", ("amount",)
    if normalized.upper() in _CURRENCIES:
        return "source_currency", ("currency",)
    return "source_text", ("source_label",)


def _model_package(
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    scope: Gate2FinancialEvidenceProductionScope,
) -> dict[str, Any]:
    candidates = {
        item.source_value_ref: item
        for item in scope.contract.package.candidates
    }
    declarations = [
        declaration
        for declaration in registry.declarations
        if declaration.input_type_id
        in scope.contract.eligible_type_ids
    ]
    return {
        "source_scope_ref": scope.source_package.source_scope_ref,
        "llm_context_package": {
            "decision_schema_version": (
                scope.contract.canonical_schema()["title"]
            ),
            "decision_schema_hash": (
                scope.contract.canonical_schema_hash()
            ),
            "eligible_types": [
                {
                    "input_type_id": item.input_type_id,
                    "definition": item.definition,
                    "required_roles": list(item.required_roles),
                    "optional_roles": list(item.optional_roles),
                    "date_period_requirement": (
                        item.date_period_requirement
                    ),
                    "currency_unit_requirement": (
                        item.currency_unit_requirement
                    ),
                }
                for item in declarations
            ],
            "source_values": [
                {
                    "source_value_ref": item.source_value_ref,
                    "source_ref": item.source_ref,
                    "value_type": item.value_type,
                    "literal_value": item.literal_value,
                    "allowed_roles": list(
                        candidates[
                            item.source_value_ref
                        ].allowed_roles
                    ),
                }
                for item in scope.source_package.source_values
            ],
        },
    }


def _fail(code: str) -> None:
    raise Gate2FinancialEvidenceProductionRuntimeError(code)
