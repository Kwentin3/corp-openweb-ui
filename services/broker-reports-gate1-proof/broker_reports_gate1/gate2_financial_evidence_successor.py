from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from typing import Any

from .gate2_deterministic_financial_scopes import (
    DETERMINISTIC_FINANCIAL_SCOPE_SCHEMA_VERSION_V2,
    Gate2DeterministicFinancialScope,
    validate_deterministic_financial_scope_any,
)
from .gate2_financial_evidence_decision import DECISION_SCHEMA_VERSION
from .gate2_financial_evidence_materialization import (
    FinancialEvidenceExecutionMetadata,
    FinancialEvidenceValidatedDecision,
    Gate2FinancialEvidenceMaterializerFactory,
    Gate2FinancialEvidenceValidatedDecisionFactory,
)
from .gate2_financial_evidence_materialization_contracts import sha256_json
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_evidence_source_context import (
    SOURCE_CONTEXT_POLICY_VERSION,
    SOURCE_CONTEXT_SCHEMA_VERSION,
    Gate2FinancialEvidenceSourceContext,
    validate_financial_evidence_source_context,
)
from .gate2_financial_semantic_model_assets import (
    PACK_INTEGRITY_SHA256,
    SEMANTIC_MODEL_ASSET_SCHEMA_VERSION,
    load_gate2_financial_semantic_model_assets,
)
from .gate2_financial_evidence_successor_projection import (
    SUCCESSOR_PROVIDER_PROJECTION_POLICY_VERSION,
    SUCCESSOR_PROVIDER_PROJECTION_SCHEMA_VERSION,
    Gate2FinancialEvidenceSuccessorProviderProjectionFactory,
)
from .gate2_model_contracts import (
    GATE2_STRICT_STRUCTURED_OUTPUT_MODES,
    Gate2StructuredModelClient,
    gate2_provider_execution_safe_metadata,
)


SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_evidence_successor_model_input_v1"
)
SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V2 = (
    "broker_reports_gate2_financial_evidence_successor_model_input_v2"
)
SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V3 = (
    "broker_reports_gate2_financial_evidence_successor_model_input_v3"
)
SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V4 = (
    "broker_reports_gate2_financial_evidence_successor_model_input_v4"
)
SUCCESSOR_RESULT_SCHEMA_VERSION_V2 = (
    "broker_reports_gate2_financial_evidence_successor_result_v2"
)
SUCCESSOR_RESULT_SCHEMA_VERSION_V3 = (
    "broker_reports_gate2_financial_evidence_successor_result_v3"
)
SUCCESSOR_RESULT_SCHEMA_VERSION_V4 = (
    "broker_reports_gate2_financial_evidence_successor_result_v4"
)
SUCCESSOR_PROMPT_CONTRACT_ID = (
    "broker_reports_gate2_financial_evidence_successor_prompt_v2"
)
SUCCESSOR_PROMPT_CONTRACT_ID_V3 = (
    "broker_reports_gate2_financial_evidence_successor_prompt_v3"
)
SUCCESSOR_PROMPT_CONTRACT_ID_V4 = (
    "broker_reports_gate2_financial_evidence_managed_prompt_v1"
)
MAX_PROVIDER_COUNTEREXAMPLES = 3
MAX_PROVIDER_COUNTEREXAMPLE_CHARS = 240
FORBIDDEN_MODEL_INPUT_FIELDS = frozenset(
    {
        "audit",
        "association_group",
        "candidate_graph",
        "cell_ref",
        "completeness",
        "confidence",
        "document_ref",
        "document_id",
        "expected_answer",
        "fact_paths",
        "file_id",
        "filename",
        "gate3_methodology",
        "integrity_hash",
        "internal_graph",
        "issue_refs",
        "lineage",
        "normalization_run_ref",
        "ownership",
        "package_ref",
        "page_ref",
        "path",
        "provenance",
        "provenance_graph",
        "raw_output",
        "relation_graph",
        "restriction_codes",
        "row_ref",
        "segment_ref",
        "source_evidence_refs",
        "source_family_id",
        "source_ref",
        "source_scope_ref",
        "system_audit",
        "table_ref",
        "uncertainty",
    }
)

FACTORY_REQUIRED = (
    "Gate2FinancialEvidenceSuccessorRunnerFactory.create is the only "
    "deterministic-scope Financial Evidence decision integration entrypoint"
)
FORBIDDEN = (
    "The successor runner must not invoke source/domain models, create a "
    "second decision contract, expose system fields to the model, repair "
    "output, use fallback or bypass the existing materializer"
)


class Gate2FinancialEvidenceSuccessorError(ValueError):
    def __init__(
        self,
        code: str,
        *,
        provider_execution: dict[str, Any] | None = None,
        economy_budget_receipt: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.provider_execution = copy.deepcopy(provider_execution or {})
        self.economy_budget_receipt = copy.deepcopy(
            economy_budget_receipt
        )


@dataclass(frozen=True)
class Gate2FinancialEvidenceSuccessorConfig:
    model_id: str
    provider_profile_id: str
    model_input_schema_version: str = (
        SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION
    )
    prompt_contract_id: str = SUCCESSOR_PROMPT_CONTRACT_ID


@dataclass(frozen=True)
class Gate2FinancialEvidenceSuccessorPrompt:
    prompt_ref: str
    content: str
    hash: str


@dataclass(frozen=True)
class Gate2FinancialEvidenceSuccessorResult:
    validated_decision: FinancialEvidenceValidatedDecision
    materialized_artifact: dict[str, Any]
    provider_execution: dict[str, Any]
    economy_budget_receipt: dict[str, Any] | None
    model_input_hash: str
    safe_summary: dict[str, Any]


class Gate2FinancialEvidenceSuccessorPromptFactory:
    def create(
        self,
        *,
        prompt_contract_id: str = SUCCESSOR_PROMPT_CONTRACT_ID,
    ) -> Gate2FinancialEvidenceSuccessorPrompt:
        if prompt_contract_id == SUCCESSOR_PROMPT_CONTRACT_ID:
            content = (
                "Make the bounded Gate 2 Financial Evidence decision. Use only "
                "eligible Registry definitions and package values. Return one "
                "strict disposition. Use unsupported only for "
                "a declared unsupported source shape or profile the strict "
                "contract cannot express. Use no_financial_input when there is no "
                "source-stated financial value, including headers, repeated "
                "headers and layout-only content. Use typed_input only when one "
                "eligible definition and every required role are explicit. "
                "cash_balance_snapshot_v1 requires an explicit source label that "
                "identifies an ordinary cash balance. "
                "printed_financial_metric_v1 requires an explicit source-printed "
                "total or metric label. Role eligibility or a matching literal "
                "alone is not semantic evidence. For equal literals, follow "
                "explicit label, date, currency and scope associations; never use "
                "an adjacent unrelated reference. Use "
                "unclassified_financial_input only for actual financial values "
                "that cannot be safely typed; bind every package value exactly "
                "once. Bind only listed source_value_ref values to allowed roles. "
                "Never invent, calculate or transform values. Return no system, "
                "confidence, provenance or audit metadata; only the strict schema "
                "object.\n{{financial_evidence_successor_input_json}}"
            )
        elif prompt_contract_id == SUCCESSOR_PROMPT_CONTRACT_ID_V3:
            content = (
                "Make one bounded Gate 2 Financial Evidence decision using "
                "only the eligible Registry guidance and source groups. "
                "Code-owned typed admission has already limited the strict "
                "response schema; this instruction cannot add or widen a "
                "typed branch. The presence of a typed branch is not an "
                "instruction to choose it. Choose typed_input only when the "
                "Registry definition and explicit source meaning uniquely "
                "support it and the listed counterexamples do not apply. "
                "When source-stated financial values cannot be safely typed, "
                "unclassified_financial_input is the normal safe outcome; "
                "preserve every package value with exact allowed-role "
                "bindings. Source-group nesting is the only allowed value "
                "association. A deterministic-reference value with a null "
                "literal is binding evidence, not semantic evidence. Use "
                "no_financial_input only when no source-stated financial "
                "value exists. Use unsupported only for an unrepresentable "
                "source shape. Never invent, calculate, transform, repair or "
                "return system, confidence, provenance or audit metadata. "
                "Return only the strict schema object.\n"
                "{{financial_evidence_successor_input_json}}"
            )
        elif prompt_contract_id == SUCCESSOR_PROMPT_CONTRACT_ID_V4:
            assets = load_gate2_financial_semantic_model_assets()
            content = str(assets["prompt_content"])
            return Gate2FinancialEvidenceSuccessorPrompt(
                prompt_ref=str(assets["prompt_ref"]),
                content=content,
                hash=str(assets["prompt_git_blob_sha256"]),
            )
        else:
            _fail("financial_evidence_successor_prompt_contract_invalid")
        digest = hashlib.sha256(
            (
                content
                + "\ncontract:"
                + prompt_contract_id
                + "\ndecision:"
                + DECISION_SCHEMA_VERSION
            ).encode("utf-8")
        ).hexdigest()
        return Gate2FinancialEvidenceSuccessorPrompt(
            prompt_ref="code:" + prompt_contract_id,
            content=content,
            hash=digest,
        )


class Gate2FinancialEvidenceSuccessorRunnerFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
        model_client: Gate2StructuredModelClient,
        config: Gate2FinancialEvidenceSuccessorConfig,
    ) -> None:
        self.registry = registry
        self.model_client = model_client
        self.config = config

    def create(self) -> "Gate2FinancialEvidenceSuccessorRunner":
        version_prompt_pairs = {
            SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION: (
                SUCCESSOR_PROMPT_CONTRACT_ID
            ),
            SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V2: (
                SUCCESSOR_PROMPT_CONTRACT_ID
            ),
            SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V3: (
                SUCCESSOR_PROMPT_CONTRACT_ID_V3
            ),
            SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V4: (
                SUCCESSOR_PROMPT_CONTRACT_ID_V4
            ),
        }
        if (
            not self.config.model_id
            or not self.config.provider_profile_id
            or self.config.model_input_schema_version
            not in version_prompt_pairs
            or self.config.prompt_contract_id
            != version_prompt_pairs.get(
                self.config.model_input_schema_version
            )
        ):
            _fail("financial_evidence_successor_config_invalid")
        return Gate2FinancialEvidenceSuccessorRunner(
            registry=self.registry,
            model_client=self.model_client,
            config=self.config,
            prompt=Gate2FinancialEvidenceSuccessorPromptFactory().create(
                prompt_contract_id=self.config.prompt_contract_id
            ),
        )


class Gate2FinancialEvidenceSuccessorRunner:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
        model_client: Gate2StructuredModelClient,
        config: Gate2FinancialEvidenceSuccessorConfig,
        prompt: Gate2FinancialEvidenceSuccessorPrompt,
    ) -> None:
        self.registry = registry
        self.model_client = model_client
        self.config = config
        self.prompt = prompt

    async def run(
        self,
        *,
        scope: Gate2DeterministicFinancialScope,
        execution_ref: str,
        decision_validation_ref: str,
        source_context: (
            Gate2FinancialEvidenceSourceContext | None
        ) = None,
    ) -> Gate2FinancialEvidenceSuccessorResult:
        validate_deterministic_financial_scope_any(scope)
        if (
            scope.decision_contract.registry.registry_version
            != self.registry.registry_version
            or scope.decision_contract.registry.registry_hash
            != self.registry.registry_hash
        ):
            _fail("financial_evidence_successor_registry_mismatch")
        model_input = self.model_input(
            scope=scope,
            source_context=source_context,
        )
        provider_projection = None
        response_format = scope.decision_contract.openai_response_format()
        if self.config.model_input_schema_version in {
            SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V3,
            SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V4,
        }:
            provider_projection = (
                Gate2FinancialEvidenceSuccessorProviderProjectionFactory()
                .create(contract=scope.decision_contract)
            )
            response_format = provider_projection.response_format
        result = await self.model_client.extract(
            prompt=self.prompt,
            package=model_input,
            model_id=self.config.model_id,
            response_format=response_format,
        )
        if result.fallback_used:
            _fail("financial_evidence_successor_fallback_forbidden")
        if result.repair_attempt_count:
            _fail("financial_evidence_successor_repair_forbidden")
        if result.execution_metadata is None:
            _fail("financial_evidence_successor_execution_metadata_missing")
        provider_execution = gate2_provider_execution_safe_metadata(
            result.execution_metadata
        )
        self._validate_execution(
            result=result,
            provider_execution=provider_execution,
        )
        try:
            validated = Gate2FinancialEvidenceValidatedDecisionFactory(
                contract=scope.decision_contract
            ).create(result.content)
            artifact = Gate2FinancialEvidenceMaterializerFactory(
                registry=self.registry,
                source_package=scope.source_package,
                execution_metadata=FinancialEvidenceExecutionMetadata(
                    execution_ref=execution_ref,
                    decision_validation_ref=decision_validation_ref,
                ),
            ).create().materialize(validated_decision=validated)
        except ValueError as exc:
            raise Gate2FinancialEvidenceSuccessorError(
                getattr(
                    exc,
                    "code",
                    "financial_evidence_successor_validation_failed",
                ),
                provider_execution=provider_execution,
                economy_budget_receipt=result.economy_budget_receipt,
            ) from exc
        summary = {
            "schema_version": (
                SUCCESSOR_RESULT_SCHEMA_VERSION_V4
                if self.config.model_input_schema_version
                == SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V4
                else (
                    SUCCESSOR_RESULT_SCHEMA_VERSION_V3
                    if self.config.model_input_schema_version
                    == SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V3
                    else (
                        SUCCESSOR_RESULT_SCHEMA_VERSION_V2
                        if self.config.model_input_schema_version
                        == SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V2
                        else (
                            "broker_reports_gate2_financial_evidence_"
                            "successor_result_v1"
                        )
                    )
                )
            ),
            "status": "passed",
            "decision_schema_version": DECISION_SCHEMA_VERSION,
            "model_input_schema_version": (
                self.config.model_input_schema_version
            ),
            "model_input_hash": sha256_json(model_input),
            "prompt_hash": self.prompt.hash,
            "prompt_contract_id": self.config.prompt_contract_id,
            "registry_version": self.registry.registry_version,
            "registry_hash": self.registry.registry_hash,
            "eligible_registry_types_total": len(
                scope.decision_contract.eligible_type_ids
            ),
            "package_source_values_total": len(
                scope.source_package.source_values
            ),
            "terminal_disposition": artifact["terminal_disposition"],
            "materialized_artifact_integrity_hash": artifact[
                "integrity_hash"
            ],
            "requested_model_id": provider_execution[
                "requested_model_id"
            ],
            "resolved_model_id": provider_execution[
                "resolved_model_id"
            ],
            "provider_profile_id": provider_execution[
                "provider_profile_id"
            ],
            "response_format_type": provider_execution[
                "response_format_type"
            ],
            "response_format_schema_mode": provider_execution[
                "response_format_schema_mode"
            ],
            "provider_calls_total": 1,
            "source_model_calls_total": 0,
            "domain_model_calls_total": 0,
            "fallback_total": 0,
            "repair_attempts_total": 0,
            "materializer": "Gate2FinancialEvidenceMaterializerFactory",
        }
        if source_context is not None:
            summary.update(
                {
                    "source_context_schema_version": (
                        SOURCE_CONTEXT_SCHEMA_VERSION
                    ),
                    "source_context_policy_version": (
                        SOURCE_CONTEXT_POLICY_VERSION
                    ),
                    "source_context_integrity_hash": (
                        source_context.integrity_hash
                    ),
                    "source_context_groups_total": len(
                        source_context.groups
                    ),
                }
            )
        if (
            self.config.model_input_schema_version
            == SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V4
        ):
            assets = load_gate2_financial_semantic_model_assets()
            summary.update(
                {
                    "semantic_model_asset_schema_version": (
                        SEMANTIC_MODEL_ASSET_SCHEMA_VERSION
                    ),
                    "semantic_pack_integrity_sha256": (
                        PACK_INTEGRITY_SHA256
                    ),
                    "semantic_pack_types_total": len(
                        assets["semantic_pack"][
                            "full_compact_snapshot"
                        ]
                    ),
                    "semantic_selection_owner": "llm",
                    "duplicate_semantic_authorities_total": 0,
                }
            )
        if provider_projection is not None:
            summary.update(
                {
                    "provider_projection_schema_version": (
                        SUCCESSOR_PROVIDER_PROJECTION_SCHEMA_VERSION
                    ),
                    "provider_projection_policy_version": (
                        SUCCESSOR_PROVIDER_PROJECTION_POLICY_VERSION
                    ),
                    "provider_response_format_hash": (
                        provider_projection.response_format_hash
                    ),
                    "provider_disposition_order": list(
                        provider_projection.disposition_order
                    ),
                }
            )
        return Gate2FinancialEvidenceSuccessorResult(
            validated_decision=validated,
            materialized_artifact=artifact,
            provider_execution=provider_execution,
            economy_budget_receipt=copy.deepcopy(
                result.economy_budget_receipt
            ),
            model_input_hash=summary["model_input_hash"],
            safe_summary=summary,
        )

    def model_input(
        self,
        *,
        scope: Gate2DeterministicFinancialScope,
        source_context: (
            Gate2FinancialEvidenceSourceContext | None
        ) = None,
    ) -> dict[str, Any]:
        validate_deterministic_financial_scope_any(scope)
        candidates = {
            item.source_value_ref: item
            for item in scope.decision_contract.package.candidates
        }
        declarations = [
            declaration
            for declaration in self.registry.declarations
            if declaration.input_type_id
            in scope.decision_contract.eligible_type_ids
        ]
        include_counterexamples = (
            self.config.model_input_schema_version
            == SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V3
        )
        eligible_types = [
            {
                "input_type_id": declaration.input_type_id,
                "definition": declaration.definition,
                "required_roles": list(
                    declaration.required_roles
                ),
                "optional_roles": list(
                    declaration.optional_roles
                ),
                "role_specs": [
                    {
                        "role_id": role.role_id,
                        "value_type": role.value_type,
                        "cardinality": role.cardinality,
                    }
                    for role in declaration.role_specs
                    if role.role_id
                    in (
                        declaration.required_roles
                        + declaration.optional_roles
                    )
                ],
                "date_period_requirement": (
                    declaration.date_period_requirement
                ),
                "currency_unit_requirement": (
                    declaration.currency_unit_requirement
                ),
                **(
                    {
                        "counterexamples": _provider_counterexamples(
                            declaration.counterexamples
                        )
                    }
                    if include_counterexamples
                    else {}
                ),
            }
            for declaration in declarations
        ]
        if (
            self.config.model_input_schema_version
            == SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION
        ):
            if source_context is not None:
                _fail(
                    "financial_evidence_successor_v1_context_forbidden"
                )
            model_input = {
                "eligible_types": eligible_types,
                "source_values": [
                    {
                        "source_value_ref": value.source_value_ref,
                        "value_type": value.value_type,
                        "literal_value": value.literal_value,
                        "allowed_roles": list(
                            candidates[
                                value.source_value_ref
                            ].allowed_roles
                        ),
                    }
                    for value in scope.source_package.source_values
                ],
            }
            validate_financial_evidence_successor_model_input(
                model_input=model_input,
                scope=scope,
                registry=self.registry,
            )
            return model_input
        if source_context is None:
            _fail("financial_evidence_successor_v2_context_required")
        if (
            scope.package.get("schema_version")
            != DETERMINISTIC_FINANCIAL_SCOPE_SCHEMA_VERSION_V2
        ):
            _fail("financial_evidence_successor_v2_scope_required")
        validate_financial_evidence_source_context(
            context=source_context,
            source_scope_ref=scope.source_package.source_scope_ref,
            source_values=scope.source_package.source_values,
            candidates=scope.decision_contract.package.candidates,
        )
        if (
            self.config.model_input_schema_version
            == SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V4
        ):
            assets = load_gate2_financial_semantic_model_assets()
            model_input = {
                "managed_assets": copy.deepcopy(
                    assets["managed_assets"]
                ),
                "semantic_pack": copy.deepcopy(
                    assets["semantic_pack"]
                ),
                "structural_scope": {
                    "eligible_type_ids": list(
                        scope.decision_contract.eligible_type_ids
                    ),
                    "allowed_role_ref_combinations": [
                        {
                            "source_value_ref": candidate.source_value_ref,
                            "allowed_roles": list(
                                candidate.allowed_roles
                            ),
                        }
                        for candidate in (
                            scope.decision_contract.package.candidates
                        )
                    ],
                },
                "source_groups": _model_source_groups_v4(
                    source_context
                ),
            }
            validate_financial_evidence_successor_model_input_v4(
                model_input=model_input,
                scope=scope,
                source_context=source_context,
            )
            return model_input
        model_input = {
            "eligible_types": eligible_types,
            "source_groups": source_context.provider_groups(),
        }
        if include_counterexamples:
            validate_financial_evidence_successor_model_input_v3(
                model_input=model_input,
                scope=scope,
                registry=self.registry,
                source_context=source_context,
            )
        else:
            validate_financial_evidence_successor_model_input_v2(
                model_input=model_input,
                scope=scope,
                registry=self.registry,
                source_context=source_context,
            )
        return model_input

    def _validate_execution(
        self,
        *,
        result: Any,
        provider_execution: dict[str, Any],
    ) -> None:
        if (
            provider_execution.get("requested_model_id")
            != self.config.model_id
            or provider_execution.get("provider_profile_id")
            != self.config.provider_profile_id
            or provider_execution.get("structured_output_mode")
            not in GATE2_STRICT_STRUCTURED_OUTPUT_MODES
            or provider_execution.get("response_format_type")
            != "json_schema"
            or provider_execution.get("response_format_schema_mode")
            != "strict_json_schema"
            or result.structured_output_mode
            not in GATE2_STRICT_STRUCTURED_OUTPUT_MODES
            or result.response_format_type != "json_schema"
            or result.response_format_schema_mode
            != "strict_json_schema"
        ):
            raise Gate2FinancialEvidenceSuccessorError(
                "financial_evidence_successor_execution_contract_invalid",
                provider_execution=provider_execution,
            )


def validate_financial_evidence_successor_model_input(
    *,
    model_input: dict[str, Any],
    scope: Gate2DeterministicFinancialScope,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> None:
    if set(model_input) != {"eligible_types", "source_values"}:
        _fail("financial_evidence_successor_model_input_shape_invalid")
    forbidden = {
        key
        for item in _walk_dicts(model_input)
        for key in item
        if key in FORBIDDEN_MODEL_INPUT_FIELDS
    }
    if forbidden:
        _fail("financial_evidence_successor_model_system_field_forbidden")
    eligible_types = model_input.get("eligible_types")
    source_values = model_input.get("source_values")
    if not isinstance(eligible_types, list) or not isinstance(
        source_values,
        list,
    ):
        _fail("financial_evidence_successor_model_input_type_invalid")
    expected_type_ids = list(scope.decision_contract.eligible_type_ids)
    if [
        item.get("input_type_id")
        for item in eligible_types
        if isinstance(item, dict)
    ] != expected_type_ids:
        _fail("financial_evidence_successor_registry_projection_invalid")
    for item in eligible_types:
        if not isinstance(item, dict) or set(item) != {
            "input_type_id",
            "definition",
            "required_roles",
            "optional_roles",
            "role_specs",
            "date_period_requirement",
            "currency_unit_requirement",
        }:
            _fail("financial_evidence_successor_registry_type_shape_invalid")
        declaration = registry.get(str(item["input_type_id"]))
        if (
            item["definition"] != declaration.definition
            or item["required_roles"]
            != list(declaration.required_roles)
            or item["optional_roles"]
            != list(declaration.optional_roles)
        ):
            _fail(
                "financial_evidence_successor_registry_type_projection_invalid"
            )
    expected_candidates = {
        item.source_value_ref: item
        for item in scope.decision_contract.package.candidates
    }
    expected_values = {
        item.source_value_ref: item
        for item in scope.source_package.source_values
    }
    if [
        item.get("source_value_ref")
        for item in source_values
        if isinstance(item, dict)
    ] != sorted(expected_values):
        _fail("financial_evidence_successor_source_value_refs_invalid")
    for item in source_values:
        if not isinstance(item, dict) or set(item) != {
            "source_value_ref",
            "value_type",
            "literal_value",
            "allowed_roles",
        }:
            _fail("financial_evidence_successor_source_value_shape_invalid")
        ref = str(item["source_value_ref"])
        value = expected_values.get(ref)
        candidate = expected_candidates.get(ref)
        if (
            value is None
            or candidate is None
            or item["value_type"] != value.value_type
            or item["literal_value"] != value.literal_value
            or item["allowed_roles"] != list(candidate.allowed_roles)
        ):
            _fail("financial_evidence_successor_source_value_projection_invalid")


def validate_financial_evidence_successor_model_input_v2(
    *,
    model_input: dict[str, Any],
    scope: Gate2DeterministicFinancialScope,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    source_context: Gate2FinancialEvidenceSourceContext,
) -> None:
    if set(model_input) != {"eligible_types", "source_groups"}:
        _fail("financial_evidence_successor_model_input_v2_shape_invalid")
    forbidden = {
        key
        for item in _walk_dicts(model_input)
        for key in item
        if key in FORBIDDEN_MODEL_INPUT_FIELDS
    }
    if forbidden:
        _fail("financial_evidence_successor_model_system_field_forbidden")
    eligible_types = model_input.get("eligible_types")
    source_groups = model_input.get("source_groups")
    if not isinstance(eligible_types, list) or not isinstance(
        source_groups,
        list,
    ):
        _fail("financial_evidence_successor_model_input_v2_type_invalid")
    expected_type_ids = list(scope.decision_contract.eligible_type_ids)
    if [
        item.get("input_type_id")
        for item in eligible_types
        if isinstance(item, dict)
    ] != expected_type_ids:
        _fail("financial_evidence_successor_registry_projection_invalid")
    for item in eligible_types:
        if not isinstance(item, dict) or set(item) != {
            "input_type_id",
            "definition",
            "required_roles",
            "optional_roles",
            "role_specs",
            "date_period_requirement",
            "currency_unit_requirement",
        }:
            _fail("financial_evidence_successor_registry_type_shape_invalid")
        declaration = registry.get(str(item["input_type_id"]))
        if (
            item["definition"] != declaration.definition
            or item["required_roles"]
            != list(declaration.required_roles)
            or item["optional_roles"]
            != list(declaration.optional_roles)
        ):
            _fail(
                "financial_evidence_successor_registry_type_projection_invalid"
            )
    validate_financial_evidence_source_context(
        context=source_context,
        source_scope_ref=scope.source_package.source_scope_ref,
        source_values=scope.source_package.source_values,
        candidates=scope.decision_contract.package.candidates,
    )
    if source_groups != source_context.provider_groups():
        _fail("financial_evidence_successor_source_context_projection_invalid")


def validate_financial_evidence_successor_model_input_v3(
    *,
    model_input: dict[str, Any],
    scope: Gate2DeterministicFinancialScope,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    source_context: Gate2FinancialEvidenceSourceContext,
) -> None:
    compatibility_input = copy.deepcopy(model_input)
    eligible_types = compatibility_input.get("eligible_types")
    if not isinstance(eligible_types, list):
        _fail("financial_evidence_successor_model_input_v3_type_invalid")
    for item in eligible_types:
        if (
            not isinstance(item, dict)
            or "counterexamples" not in item
        ):
            _fail(
                "financial_evidence_successor_counterexamples_missing"
            )
        input_type_id = str(item.get("input_type_id") or "")
        declaration = registry.get(input_type_id)
        if item["counterexamples"] != _provider_counterexamples(
            declaration.counterexamples
        ):
            _fail(
                "financial_evidence_successor_counterexamples_invalid"
            )
        item.pop("counterexamples")
    validate_financial_evidence_successor_model_input_v2(
        model_input=compatibility_input,
        scope=scope,
        registry=registry,
        source_context=source_context,
    )


def validate_financial_evidence_successor_model_input_v4(
    *,
    model_input: dict[str, Any],
    scope: Gate2DeterministicFinancialScope,
    source_context: Gate2FinancialEvidenceSourceContext,
) -> None:
    if set(model_input) != {
        "managed_assets",
        "semantic_pack",
        "structural_scope",
        "source_groups",
    }:
        _fail("financial_evidence_successor_model_input_v4_shape_invalid")
    forbidden = {
        key
        for item in _walk_dicts(model_input)
        for key in item
        if key in FORBIDDEN_MODEL_INPUT_FIELDS
    }
    if forbidden:
        _fail("financial_evidence_successor_model_system_field_forbidden")

    assets = load_gate2_financial_semantic_model_assets()
    if model_input.get("managed_assets") != assets["managed_assets"]:
        _fail("financial_evidence_successor_managed_asset_identity_invalid")
    semantic_pack = model_input.get("semantic_pack")
    if semantic_pack != assets["semantic_pack"]:
        _fail("financial_evidence_successor_semantic_pack_incomplete")
    if (
        not isinstance(semantic_pack, dict)
        or semantic_pack.get("integrity_sha256")
        != PACK_INTEGRITY_SHA256
    ):
        _fail("financial_evidence_successor_semantic_pack_identity_invalid")
    snapshot = semantic_pack.get("full_compact_snapshot")
    if not isinstance(snapshot, list) or not snapshot:
        _fail("financial_evidence_successor_semantic_pack_incomplete")
    pack_type_ids = [
        item.get("input_type_id")
        for item in snapshot
        if isinstance(item, dict)
    ]
    if (
        len(pack_type_ids) != len(snapshot)
        or len(pack_type_ids) != len(set(pack_type_ids))
    ):
        _fail("financial_evidence_successor_semantic_pack_type_ids_invalid")

    structural_scope = model_input.get("structural_scope")
    if not isinstance(structural_scope, dict) or set(
        structural_scope
    ) != {
        "eligible_type_ids",
        "allowed_role_ref_combinations",
    }:
        _fail("financial_evidence_successor_structural_scope_invalid")
    expected_type_ids = list(scope.decision_contract.eligible_type_ids)
    if (
        structural_scope["eligible_type_ids"] != expected_type_ids
        or any(item not in pack_type_ids for item in expected_type_ids)
    ):
        _fail("financial_evidence_successor_structural_types_invalid")
    expected_combinations = [
        {
            "source_value_ref": candidate.source_value_ref,
            "allowed_roles": list(candidate.allowed_roles),
        }
        for candidate in scope.decision_contract.package.candidates
    ]
    if (
        structural_scope["allowed_role_ref_combinations"]
        != expected_combinations
        or any(
            not item["allowed_roles"]
            or len(item["allowed_roles"])
            != len(set(item["allowed_roles"]))
            for item in expected_combinations
        )
    ):
        _fail("financial_evidence_successor_role_ref_combinations_invalid")

    validate_financial_evidence_source_context(
        context=source_context,
        source_scope_ref=scope.source_package.source_scope_ref,
        source_values=scope.source_package.source_values,
        candidates=scope.decision_contract.package.candidates,
    )
    if model_input.get("source_groups") != _model_source_groups_v4(
        source_context
    ):
        _fail("financial_evidence_successor_source_context_projection_invalid")

    non_pack_input = {
        key: value
        for key, value in model_input.items()
        if key != "semantic_pack"
    }
    if any(
        "definition" in item
        or "synonyms" in item
        or "counterexamples" in item
        or "semantic_distinctions" in item
        or "ambiguity_guidance" in item
        for item in _walk_dicts(non_pack_input)
    ):
        _fail("financial_evidence_successor_duplicate_semantic_authority")


def _model_source_groups_v4(
    source_context: Gate2FinancialEvidenceSourceContext,
) -> list[dict[str, Any]]:
    groups = source_context.provider_groups()
    for group in groups:
        for value in group["values"]:
            value.pop("allowed_roles")
    return groups


def _provider_counterexamples(
    counterexamples: tuple[str, ...],
) -> list[str]:
    if (
        not counterexamples
        or len(counterexamples) > MAX_PROVIDER_COUNTEREXAMPLES
        or any(
            not isinstance(item, str)
            or not item
            or len(item) > MAX_PROVIDER_COUNTEREXAMPLE_CHARS
            for item in counterexamples
        )
    ):
        _fail("financial_evidence_successor_counterexample_limit_invalid")
    return list(counterexamples)


def _walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _fail(code: str) -> None:
    raise Gate2FinancialEvidenceSuccessorError(code)
