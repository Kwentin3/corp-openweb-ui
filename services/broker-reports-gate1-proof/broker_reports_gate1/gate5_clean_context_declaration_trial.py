"""Prepare and validate one frozen clean-context declaration authoring trial."""

from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
from importlib import resources
import json
import re
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from .gate5_declaration_definition import (
    Gate5DeclarationDefinitionAuthoringFactory,
)
from .gate5_declaration_projection import Gate5DeclarationProjectionRuntimeFactory
from .gate5_published_typed_behavior import (
    GATE5_PUBLISHED_BEHAVIOR_REF_SCHEMA_VERSION,
    GATE5_PUBLISHED_TYPED_BEHAVIOR_CAPABILITY_ID,
    Gate5PublishedTypedBehaviorError,
    Gate5PublishedTypedBehaviorRegistryFactory,
)
from .gate5_runtime_capabilities import Gate5RuntimeCapabilityContractV1Factory
from .gate5_trusted_methodology import (
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
    Gate5TrustedMethodologyAuthorityFactory,
)


GATE5_CLEAN_CONTEXT_TRIAL_ID = "g5.19-primary-2026-08-10-002"
GATE5_INDEPENDENT_AUTHORING_CAPTURE_FAILURE_TRIAL_ID = "g5.20-primary-2026-08-10-001"
GATE5_INDEPENDENT_AUTHORING_TRIAL_ID = "g5.20-primary-2026-08-10-002"
GATE5_CLEAN_CONTEXT_DEFINITION_SCHEMA_VERSION = (
    "broker_reports_gate5_clean_context_declaration_definition_v1"
)
GATE5_CLEAN_CONTEXT_PAYLOAD_RESOURCE = (
    "gate5_clean_context_declaration_trial.primary.v1.payload.json"
)
GATE5_CLEAN_CONTEXT_PAYLOAD_RESOURCE_SHA256 = (
    "a3ad620016c93eff08a7f79cdb24f86cdcc81b0dd16ce7a68be2660d760fac46"
)

FACTORY_REQUIRED = (
    "Gate5CleanContextDeclarationTrialFactory.create is the sole payload and "
    "neutral-validator construction entrypoint",
    "runtime capabilities come from Gate5RuntimeCapabilityContractV1Factory.create",
    "published behavior pairs resolve through "
    "Gate5PublishedTypedBehaviorRegistryFactory.create",
    "published artifacts resolve through their existing authority owners",
)
FORBIDDEN = (
    "previous candidate, Gate reports, roadmap or expected gap in model-visible input",
    "manual response repair, retry, fallback or candidate normalization",
    "free-form action, step, expression, formula, code, command or tool fields",
    "new capability, behavior, artifact, methodology, runtime or product activation",
)

_MODEL_PAYLOAD_SECTION_NAMES = (
    "system_instructions",
    "research_policy",
    "runtime_capabilities",
    "published_artifact_inventory",
    "official_evidence",
    "output_schema",
)
_BIAS_TERMS = (
    "g5.16",
    "g5.17",
    "g5.18",
    "roadmap",
    "expected gap",
    "first missing capability",
    "group-level tax base",
    "group tax base",
    "line 060",
    "следующий шаг",
)
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")


class Gate5CleanContextDeclarationTrialError(ValueError):
    def __init__(self, code: str, field: str = "") -> None:
        self.code = code
        self.field = field
        super().__init__(code if not field else f"{code}:{field}")


@dataclass(frozen=True)
class _PublishedArtifact:
    key: tuple[str, str, str]
    behavior_id: str | None
    capability_ids: frozenset[str]


class Gate5CleanContextDeclarationTrialFactory:
    @staticmethod
    def create() -> "Gate5CleanContextDeclarationTrial":
        built_payload = _build_model_payload()
        raw = _read_resource_bytes(GATE5_CLEAN_CONTEXT_PAYLOAD_RESOURCE)
        if GATE5_CLEAN_CONTEXT_PAYLOAD_RESOURCE_SHA256 == "TO_BE_FROZEN":
            _fail("gate5_clean_context_payload_hash_not_frozen")
        if (
            hashlib.sha256(raw).hexdigest()
            != GATE5_CLEAN_CONTEXT_PAYLOAD_RESOURCE_SHA256
        ):
            _fail("gate5_clean_context_payload_hash_mismatch")
        if raw != _canonical_json(built_payload):
            _fail("gate5_clean_context_payload_drift")
        try:
            frozen_payload: Any = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Gate5CleanContextDeclarationTrialError(
                "gate5_clean_context_payload_json_invalid"
            ) from exc
        if frozen_payload != built_payload:
            _fail("gate5_clean_context_payload_drift")

        bias_audit = _bias_audit(frozen_payload)
        capability_index = _capability_index(frozen_payload["runtime_capabilities"])
        artifact_index = _artifact_index(frozen_payload["published_artifact_inventory"])
        evidence_refs = _evidence_refs(frozen_payload["official_evidence"])
        _validate_output_schema(frozen_payload["output_schema"])
        return Gate5CleanContextDeclarationTrial(
            payload=copy.deepcopy(frozen_payload),
            bias_audit=copy.deepcopy(bias_audit),
            capability_index=capability_index,
            artifact_index=artifact_index,
            evidence_refs=evidence_refs,
        )


class Gate5CleanContextDeclarationTrial:
    def __init__(
        self,
        *,
        payload: dict[str, Any],
        bias_audit: dict[str, Any],
        capability_index: dict[str, dict[str, Any]],
        artifact_index: dict[tuple[str, str, str], _PublishedArtifact],
        evidence_refs: frozenset[str],
    ) -> None:
        self._payload = payload
        self._bias_audit = bias_audit
        self._capability_index = capability_index
        self._artifact_index = artifact_index
        self._evidence_refs = evidence_refs

    def model_payload(self) -> dict[str, Any]:
        return copy.deepcopy(self._payload)

    def model_payload_bytes(self) -> bytes:
        return _canonical_json(self._payload)

    def output_schema(self) -> dict[str, Any]:
        return copy.deepcopy(self._payload["output_schema"])

    def bias_audit(self) -> dict[str, Any]:
        return copy.deepcopy(self._bias_audit)

    def section_metrics(self) -> dict[str, Any]:
        sections = []
        for name in _MODEL_PAYLOAD_SECTION_NAMES:
            raw = _canonical_json(self._payload[name])
            sections.append(
                {
                    "section": name,
                    "utf8_bytes": len(raw),
                    "unicode_lexical_tokens": len(
                        re.findall(r"\w+|[^\w\s]", raw.decode("utf-8"))
                    ),
                }
            )
        payload_bytes = self.model_payload_bytes()
        return {
            "token_metric": "unicode_lexical_tokens_v0_not_model_tokenizer",
            "sections": sections,
            "enveloped_payload_utf8_bytes": len(payload_bytes),
            "utf8_bytes_div_4_token_proxy": (len(payload_bytes) + 3) // 4,
        }

    def pre_inference_record(self) -> dict[str, Any]:
        schema_bytes = _canonical_json(self._payload["output_schema"])
        payload_bytes = self.model_payload_bytes()
        return {
            "schema_version": "broker_reports_gate5_clean_context_trial_plan_v0",
            "trial_id": GATE5_CLEAN_CONTEXT_TRIAL_ID,
            "status": "frozen_before_inference",
            "application_messages": [
                {
                    "role": "user",
                    "content_binding": "exact_frozen_payload_bytes",
                    "content_sha256": hashlib.sha256(payload_bytes).hexdigest(),
                    "content_utf8_bytes": len(payload_bytes),
                }
            ],
            "conversation_history": "none",
            "payload_sha256": hashlib.sha256(payload_bytes).hexdigest(),
            "output_schema_sha256": hashlib.sha256(schema_bytes).hexdigest(),
            "section_metrics": self.section_metrics(),
            "bias_audit": self.bias_audit(),
            "invocation_profile": {
                "provider": "openai_codex_cli",
                "client_version": "codex-cli 0.147.0-alpha.6.5",
                "model": "gpt-5.6-sol",
                "reasoning_effort": "high",
                "structured_output": "strict_json_schema",
                "conversation_mode": "ephemeral_new_session",
                "workspace": "empty_temporary_directory",
                "sandbox": "read-only",
                "user_config": "ignored",
                "exec_rules": "ignored",
                "retry_limit": 0,
                "response_repair": "forbidden",
            },
        }

    def independent_pre_inference_record(self) -> dict[str, Any]:
        """Freeze the G5.20 plain-JSON experiment without changing semantics."""
        schema_bytes = _canonical_json(self._payload["output_schema"])
        payload_bytes = self.model_payload_bytes()
        return {
            "schema_version": (
                "broker_reports_gate5_independent_authoring_trial_plan_v1"
            ),
            "trial_id": GATE5_INDEPENDENT_AUTHORING_TRIAL_ID,
            "status": "frozen_before_inference",
            "application_messages": [
                {
                    "role": "user",
                    "content_binding": "exact_frozen_payload_bytes",
                    "content_sha256": hashlib.sha256(payload_bytes).hexdigest(),
                    "content_utf8_bytes": len(payload_bytes),
                }
            ],
            "conversation_history": "none",
            "payload_sha256": hashlib.sha256(payload_bytes).hexdigest(),
            "model_visible_output_schema_sha256": hashlib.sha256(
                schema_bytes
            ).hexdigest(),
            "section_metrics": self.section_metrics(),
            "bias_audit": self.bias_audit(),
            "invocation_profile": {
                "provider": "openai_codex_cli",
                "client_version": "codex-cli 0.147.0-alpha.6.5",
                "model": "gpt-5.6-sol",
                "reasoning_effort": "high",
                "provider_output_schema": "none",
                "final_message_capture": "output_last_message_file",
                "candidate_parser": "one_utf8_json_object_no_repair_v1",
                "conversation_mode": "ephemeral_new_session",
                "workspace": "empty_temporary_directory",
                "sandbox": "read-only",
                "user_config": "ignored",
                "exec_rules": "ignored",
                "retry_limit": 0,
                "response_repair": "forbidden",
            },
        }

    def parse_candidate_response(self, response_bytes: bytes) -> dict[str, Any]:
        """Parse exactly one UTF-8 JSON object; do not extract or repair text."""
        if not isinstance(response_bytes, bytes) or not response_bytes:
            _fail("gate5_clean_context_candidate_response_empty")
        try:
            candidate: Any = json.loads(response_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Gate5CleanContextDeclarationTrialError(
                "gate5_clean_context_candidate_response_invalid"
            ) from exc
        if not isinstance(candidate, dict):
            _fail("gate5_clean_context_candidate_response_not_object")
        return copy.deepcopy(candidate)

    def validate_candidate_response(self, response_bytes: bytes) -> dict[str, Any]:
        return self.validate_candidate(self.parse_candidate_response(response_bytes))

    def validate_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        try:
            Draft202012Validator(self._payload["output_schema"]).validate(candidate)
        except ValidationError as exc:
            field = ".".join(str(part) for part in exc.absolute_path)
            raise Gate5CleanContextDeclarationTrialError(
                "gate5_clean_context_candidate_schema_invalid", field
            ) from exc
        return _validate_candidate_semantics(
            candidate=copy.deepcopy(candidate),
            target=self._payload["official_evidence"]["declaration"],
            capability_index=self._capability_index,
            artifact_index=self._artifact_index,
            evidence_refs=self._evidence_refs,
        )


def build_unfrozen_model_payload_for_freeze() -> dict[str, Any]:
    """Build the deterministic payload before its first and only freeze."""
    return _build_model_payload()


def _build_model_payload() -> dict[str, Any]:
    official_evidence = (
        Gate5DeclarationDefinitionAuthoringFactory.create().model_payload()[
            "official_evidence"
        ]
    )
    capability_contract = Gate5RuntimeCapabilityContractV1Factory.create()
    payload = {
        "system_instructions": {
            "task": (
                "Using only the supplied official evidence, runtime capability "
                "contract and published artifact inventory, determine which relevant "
                "2025 3-NDFL securities-disposal declaration requirements are "
                "expressible. Return one machine-readable declaration definition "
                "covering supported or conditionally supported units and unsupported "
                "requirements."
            ),
            "rules": [
                "Use only supplied official evidence for declaration claims.",
                "Use only proven capability identities and published artifact identities present in the supplied sections.",
                "Do not invent a capability, behavior, artifact, value kind, evidence source, tax rule or executable formula.",
                "Classify a unit as conditionally compilable when its declared boundary inputs are required but no current case evidence is supplied.",
                "Do not treat a declared boundary input as automatically available from current case evidence.",
                "Return a gap when the supplied runtime and artifacts cannot express an official requirement.",
                "Do not emit free-form actions, code, commands, tools, XML, PDF, tax payable or chain-of-thought.",
                "Return exactly one object conforming to the supplied closed output schema.",
            ],
        },
        "research_policy": {
            "authoritative_evidence": [
                "supplied official FNS order and attachments",
                "supplied official FNS electronic format and XSD bindings",
                "repository-published hash-bound methodology and projection identities",
            ],
            "evidence_rules": [
                "Bind every declaration requirement to supplied official evidence_ref values.",
                "Do not use model memory, prior project reports or repository history as declaration authority.",
                "Separate missing evidence from missing runtime, behavior, artifact, value-kind and contract support.",
                "Official requirements describe required semantics but do not themselves publish executable runtime behavior.",
            ],
            "authoring_tools": [],
            "case_time_tools": [],
        },
        "runtime_capabilities": capability_contract.model_projection(),
        "published_artifact_inventory": _published_artifact_inventory(),
        "official_evidence": official_evidence,
        "output_schema": _output_schema(),
    }
    if tuple(payload) != _MODEL_PAYLOAD_SECTION_NAMES:
        _fail("gate5_clean_context_payload_sections_invalid")
    _bias_audit(payload)
    _capability_index(payload["runtime_capabilities"])
    _artifact_index(payload["published_artifact_inventory"])
    _evidence_refs(payload["official_evidence"])
    _validate_output_schema(payload["output_schema"])
    return payload


def _published_artifact_inventory() -> dict[str, Any]:
    artifacts = [
        _methodology_artifact(
            artifact_id="ru-ndfl-securities-proof",
            artifact_version="2026.0-experimental",
            behavior_id="security_disposal_net_result_v0",
            semantic_input_contract="broker_reports_gate5_no_additional_behavior_input_v1",
            semantic_input_meaning="No additional behavior payload beyond trusted case context and resolved methodology requirements.",
            semantic_output_contract="broker_reports_gate5_trusted_calculation_result_v0",
            semantic_output_meaning="One provenance-bound securities disposal net-result calculation.",
            registered=True,
            capability_uses=[
                {
                    "capability_id": GATE5_PUBLISHED_TYPED_BEHAVIOR_CAPABILITY_ID,
                    "role": "registered_typed_execution",
                }
            ],
            reference_ids=["rf-tax-code-214.1-10", "federal-law-281-fz-article-2"],
        ),
        _methodology_artifact(
            artifact_id="ru-ndfl-securities-tax-model-proof",
            artifact_version="2026.0-experimental",
            behavior_id="securities_disposal_tax_model_v0",
            semantic_input_contract="broker_reports_gate5_securities_disposal_resolved_inputs_v0",
            semantic_input_meaning="Resolved securities-disposal money values plus closed applicability and expense-evidence context.",
            semantic_output_contract="broker_reports_gate5_securities_disposal_tax_model_v0",
            semantic_output_meaning="One securities-disposal tax model whose completeness assertion is part of the operation input.",
            registered=False,
            capability_uses=[],
            reference_ids=["rf-tax-code-214.1-10", "federal-law-281-fz-article-2"],
        ),
        _methodology_artifact(
            artifact_id="ru-ndfl-securities-tax-model-proof",
            artifact_version="2026.1-experimental",
            behavior_id="securities_disposal_operation_tax_model_v0",
            semantic_input_contract="broker_reports_gate5_securities_disposal_resolved_inputs_v0",
            semantic_input_meaning="Resolved securities-disposal money values plus closed applicability and expense-evidence context for one operation.",
            semantic_output_contract="broker_reports_gate5_securities_disposal_operation_tax_model_v0",
            semantic_output_meaning="One complete source-tagged securities-disposal operation model accepted as an aggregation member.",
            registered=True,
            capability_uses=[
                {
                    "capability_id": GATE5_PUBLISHED_TYPED_BEHAVIOR_CAPABILITY_ID,
                    "role": "registered_typed_execution",
                },
                {
                    "capability_id": "aggregate_complete_category_scope_v0",
                    "role": "accepted_operation_member",
                },
            ],
            reference_ids=["rf-tax-code-214.1-10", "federal-law-281-fz-article-2"],
        ),
        {
            "artifact_ref": {
                "artifact_kind": "validated_declaration_projection",
                "artifact_id": "ru-3ndfl-2025-appendix8-securities-proof",
                "artifact_version": "2026.0-proof",
            },
            "publication_status": "published_hash_bound_inactive_proof",
            "behavior_id": None,
            "semantic_input_contract": "broker_reports_gate5_declaration_projection_proof_input_v0",
            "semantic_input_meaning": (
                "Five stable Appendix 8 semantics: operation category, category gross "
                "income, related expenses, allowable expenses and loss treatment."
            ),
            "semantic_output_contract": "broker_reports_gate5_declaration_projection_fragment_v0",
            "semantic_output_meaning": "One deterministic declaration-shaped Appendix 8 securities occurrence.",
            "typed_execution_binding": None,
            "capability_uses": [
                {
                    "capability_id": "project_validated_declaration_fragment_v0",
                    "role": "validated_projection",
                },
                {
                    "capability_id": "aggregate_complete_category_scope_v0",
                    "role": "nested_projection_for_complete_scope",
                },
            ],
            "authority_binding": {
                "resource_sha256": "348e22da283bc8ff2a42c04f1fe45923b330840380466790f39670156a7970de",
                "projection_sha256": "36d301bb9666d0f61213ccce95b016e7a674d30d1e0841cea0d8ebc59977f4d7",
                "reference_ids": [
                    "appendix8_form_lines_010_050",
                    "appendix8_procedure_paragraphs_97_98",
                    "appendix8_operation_code_01",
                    "appendix8_format_table_4_46",
                    "appendix8_xsd_contract",
                ],
            },
        },
    ]
    return {
        "schema_version": "broker_reports_gate5_published_artifact_inventory_v1",
        "inventory_id": "gate5-relevant-published-tax-artifacts",
        "inventory_version": "2026.1-proof",
        "status": "repository_truth_snapshot",
        "artifacts": artifacts,
    }


def _methodology_artifact(
    *,
    artifact_id: str,
    artifact_version: str,
    behavior_id: str,
    semantic_input_contract: str,
    semantic_input_meaning: str,
    semantic_output_contract: str,
    semantic_output_meaning: str,
    registered: bool,
    capability_uses: list[dict[str, str]],
    reference_ids: list[str],
) -> dict[str, Any]:
    authority = Gate5TrustedMethodologyAuthorityFactory.create()
    resolved = authority.resolve(
        {
            "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
            "methodology_id": artifact_id,
            "methodology_version": artifact_version,
        }
    )
    authority_binding = resolved["authority_binding"]
    behavior_ref = {
        "schema_version": GATE5_PUBLISHED_BEHAVIOR_REF_SCHEMA_VERSION,
        "methodology_id": artifact_id,
        "methodology_version": artifact_version,
        "behavior_id": behavior_id,
    }
    registry = Gate5PublishedTypedBehaviorRegistryFactory.create()
    typed_binding: dict[str, Any] | None
    try:
        described = registry.describe(behavior_ref)
    except Gate5PublishedTypedBehaviorError as exc:
        if registered or exc.code != "gate5_published_typed_behavior_unsupported":
            raise
        typed_binding = None
    else:
        if not registered:
            _fail("gate5_clean_context_inventory_registration_drift")
        typed_binding = {
            "execution_capability_id": GATE5_PUBLISHED_TYPED_BEHAVIOR_CAPABILITY_ID,
            "behavior_ref": behavior_ref,
            "input_contract_id": described["input_contract_id"],
            "output_contract_id": described["output_contract_id"],
        }
        if (
            described["input_contract_id"] != semantic_input_contract
            or described["output_contract_id"] != semantic_output_contract
        ):
            _fail("gate5_clean_context_inventory_contract_drift")

    return {
        "artifact_ref": {
            "artifact_kind": "trusted_methodology",
            "artifact_id": artifact_id,
            "artifact_version": artifact_version,
        },
        "publication_status": "published_hash_bound_inactive_proof",
        "behavior_id": behavior_id,
        "semantic_input_contract": semantic_input_contract,
        "semantic_input_meaning": semantic_input_meaning,
        "semantic_output_contract": semantic_output_contract,
        "semantic_output_meaning": semantic_output_meaning,
        "typed_execution_binding": typed_binding,
        "capability_uses": copy.deepcopy(capability_uses),
        "authority_binding": {
            "resource_sha256": authority_binding["resource_sha256"],
            "projection_sha256": authority_binding["projection_sha256"],
            "reference_ids": copy.deepcopy(reference_ids),
        },
    }


def _output_schema() -> dict[str, Any]:
    identifier = {"type": "string", "pattern": "^[a-z][a-z0-9_.-]{0,127}$"}
    contract_id = {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"}
    artifact_ref = {
        "type": "object",
        "additionalProperties": False,
        "required": ["artifact_kind", "artifact_id", "artifact_version", "role"],
        "properties": {
            "artifact_kind": copy.deepcopy(identifier),
            "artifact_id": copy.deepcopy(identifier),
            "artifact_version": {"type": "string", "minLength": 1, "maxLength": 64},
            "role": copy.deepcopy(identifier),
        },
    }
    behavior_ref = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "methodology_id",
            "methodology_version",
            "behavior_id",
            "input_contract_id",
            "output_contract_id",
        ],
        "properties": {
            "schema_version": {"const": GATE5_PUBLISHED_BEHAVIOR_REF_SCHEMA_VERSION},
            "methodology_id": copy.deepcopy(identifier),
            "methodology_version": {"type": "string", "minLength": 1, "maxLength": 64},
            "behavior_id": copy.deepcopy(identifier),
            "input_contract_id": copy.deepcopy(contract_id),
            "output_contract_id": copy.deepcopy(contract_id),
        },
    }
    boundary_input = {
        "type": "object",
        "additionalProperties": False,
        "required": ["input_name", "contract_id", "availability", "source_class"],
        "properties": {
            "input_name": copy.deepcopy(identifier),
            "contract_id": copy.deepcopy(contract_id),
            "availability": {
                "enum": [
                    "available_via_declared_capability",
                    "required_at_boundary",
                    "not_available",
                ]
            },
            "source_class": {
                "enum": [
                    "current_financial_case",
                    "same_run_user_fact",
                    "user_verified_fact",
                    "external_authoritative_evidence",
                    "methodology_derived_result",
                    "declared_boundary_input",
                    "not_available",
                ]
            },
        },
    }
    capability_binding = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "capability_id",
            "declared_input_contracts",
            "declared_output_contract",
            "registered_behavior",
            "artifact_refs",
        ],
        "properties": {
            "capability_id": copy.deepcopy(identifier),
            "declared_input_contracts": {
                "type": "array",
                "items": copy.deepcopy(contract_id),
            },
            "declared_output_contract": copy.deepcopy(contract_id),
            "registered_behavior": {
                "anyOf": [copy.deepcopy(behavior_ref), {"type": "null"}]
            },
            "artifact_refs": {
                "type": "array",
                "items": copy.deepcopy(artifact_ref),
            },
        },
    }
    requirement = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "requirement_id",
            "official_requirement",
            "evidence_refs",
            "semantic_outputs",
            "availability",
            "end_to_end_available_from_current_case_evidence",
            "boundary_inputs",
            "capability_bindings",
            "gap_refs",
        ],
        "properties": {
            "requirement_id": copy.deepcopy(identifier),
            "official_requirement": {
                "type": "string",
                "minLength": 1,
                "maxLength": 1200,
            },
            "evidence_refs": {
                "type": "array",
                "minItems": 1,
                "items": copy.deepcopy(identifier),
            },
            "semantic_outputs": {
                "type": "array",
                "minItems": 1,
                "items": copy.deepcopy(identifier),
            },
            "availability": {
                "enum": [
                    "compilable",
                    "conditionally_compilable",
                    "not_compilable",
                    "evidence_missing",
                ]
            },
            "end_to_end_available_from_current_case_evidence": {"type": "boolean"},
            "boundary_inputs": {"type": "array", "items": boundary_input},
            "capability_bindings": {"type": "array", "items": capability_binding},
            "gap_refs": {
                "type": "array",
                "items": copy.deepcopy(identifier),
            },
        },
    }
    gap = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "gap_id",
            "requirement_id",
            "gap_type",
            "required_semantic",
            "related_capability_ids",
            "related_artifact_refs",
            "missing_behavior_id",
            "missing_contract_id",
            "missing_artifact_kind",
            "evidence_refs",
            "explanation",
        ],
        "properties": {
            "gap_id": copy.deepcopy(identifier),
            "requirement_id": copy.deepcopy(identifier),
            "gap_type": {
                "enum": [
                    "missing_runtime_capability",
                    "missing_published_behavior",
                    "missing_artifact",
                    "unsupported_value_kind",
                    "missing_evidence",
                    "incompatible_contract",
                ]
            },
            "required_semantic": {"type": "string", "minLength": 1, "maxLength": 1200},
            "related_capability_ids": {
                "type": "array",
                "items": copy.deepcopy(identifier),
            },
            "related_artifact_refs": {
                "type": "array",
                "items": copy.deepcopy(artifact_ref),
            },
            "missing_behavior_id": {
                "anyOf": [copy.deepcopy(identifier), {"type": "null"}]
            },
            "missing_contract_id": {
                "anyOf": [copy.deepcopy(contract_id), {"type": "null"}]
            },
            "missing_artifact_kind": {
                "anyOf": [copy.deepcopy(identifier), {"type": "null"}]
            },
            "evidence_refs": {
                "type": "array",
                "items": copy.deepcopy(identifier),
            },
            "explanation": {"type": "string", "minLength": 1, "maxLength": 1200},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "definition_id",
            "definition_version",
            "status",
            "target",
            "scope",
            "requirements",
            "gaps",
            "findings",
            "authoring",
        ],
        "properties": {
            "schema_version": {"const": GATE5_CLEAN_CONTEXT_DEFINITION_SCHEMA_VERSION},
            "definition_id": copy.deepcopy(identifier),
            "definition_version": {"type": "string", "minLength": 1, "maxLength": 64},
            "status": {
                "enum": ["compilable", "partially_compilable", "not_compilable"]
            },
            "target": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "jurisdiction",
                    "tax_period",
                    "form",
                    "knd",
                    "order",
                    "electronic_format_version",
                    "xsd",
                ],
                "properties": {
                    "jurisdiction": {"type": "string", "minLength": 1},
                    "tax_period": {"type": "string", "minLength": 1},
                    "form": {"type": "string", "minLength": 1},
                    "knd": {"type": "string", "minLength": 1},
                    "order": {"type": "string", "minLength": 1},
                    "electronic_format_version": {"type": "string", "minLength": 1},
                    "xsd": {"type": "string", "minLength": 1},
                },
            },
            "scope": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "domain",
                    "taxpayer_profile",
                    "operation_profile",
                    "boundary",
                ],
                "properties": {
                    "domain": {"type": "string", "minLength": 1, "maxLength": 500},
                    "taxpayer_profile": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 500,
                    },
                    "operation_profile": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 500,
                    },
                    "boundary": {"type": "string", "minLength": 1, "maxLength": 1000},
                },
            },
            "requirements": {
                "type": "array",
                "minItems": 1,
                "maxItems": 20,
                "items": requirement,
            },
            "gaps": {"type": "array", "maxItems": 20, "items": gap},
            "findings": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "supported_requirement_ids",
                    "unsupported_requirement_ids",
                    "first_blocking_gap_id",
                    "limitations",
                ],
                "properties": {
                    "supported_requirement_ids": {
                        "type": "array",
                        "minItems": 1,
                        "items": copy.deepcopy(identifier),
                    },
                    "unsupported_requirement_ids": {
                        "type": "array",
                        "minItems": 1,
                        "items": copy.deepcopy(identifier),
                    },
                    "first_blocking_gap_id": {
                        "anyOf": [copy.deepcopy(identifier), {"type": "null"}]
                    },
                    "limitations": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1, "maxLength": 1000},
                    },
                },
            },
            "authoring": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "supplied_evidence_only",
                    "prior_project_context_used",
                    "manual_candidate_repair_allowed",
                    "notes",
                ],
                "properties": {
                    "supplied_evidence_only": {"type": "boolean"},
                    "prior_project_context_used": {"type": "boolean"},
                    "manual_candidate_repair_allowed": {"type": "boolean"},
                    "notes": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1, "maxLength": 1000},
                    },
                },
            },
        },
    }


def _validate_output_schema(schema: Any) -> None:
    if not isinstance(schema, dict):
        _fail("gate5_clean_context_output_schema_invalid")
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise Gate5CleanContextDeclarationTrialError(
            "gate5_clean_context_output_schema_invalid"
        ) from exc
    rendered = json.dumps(schema, ensure_ascii=False).lower()
    if any(
        term in rendered
        for term in (
            "section 2",
            "line 060",
            "group tax base",
            "group-level tax base",
            "securities_disposal_group_tax_base",
        )
    ):
        _fail("gate5_clean_context_output_schema_bias_detected")


def _bias_audit(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != set(
        _MODEL_PAYLOAD_SECTION_NAMES
    ):
        _fail("gate5_clean_context_payload_sections_invalid")
    disallowed_hits: list[dict[str, str]] = []
    allowed_official_hits: list[dict[str, str]] = []
    for section in _MODEL_PAYLOAD_SECTION_NAMES:
        for path, text in _strings(payload[section], section):
            lowered = text.lower()
            for term in _BIAS_TERMS:
                if term in lowered:
                    hit = {"term": term, "path": path}
                    if section == "official_evidence":
                        allowed_official_hits.append(hit)
                    else:
                        disallowed_hits.append(hit)
    if disallowed_hits:
        _fail("gate5_clean_context_payload_bias_detected")
    return {
        "schema_version": "broker_reports_gate5_clean_context_bias_audit_v0",
        "status": "passed",
        "policy": "forbidden_terms_outside_official_evidence_v0",
        "forbidden_terms": list(_BIAS_TERMS),
        "disallowed_hits": disallowed_hits,
        "official_evidence_allowed_hits": allowed_official_hits,
    }


def _strings(value: Any, path: str):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _strings(item, f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(item, f"{path}.{key}")


def _capability_index(projection: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(projection, dict) or not isinstance(
        projection.get("capabilities"), list
    ):
        _fail("gate5_clean_context_capability_projection_invalid")
    index: dict[str, dict[str, Any]] = {}
    for capability in projection["capabilities"]:
        capability_id = (
            capability.get("capability_id") if isinstance(capability, dict) else None
        )
        if (
            not isinstance(capability_id, str)
            or capability_id in index
            or capability.get("implementation_status") != "proven"
            or capability.get("execution_phase") != "case_time"
        ):
            _fail("gate5_clean_context_capability_projection_invalid")
        index[capability_id] = copy.deepcopy(capability)
    if len(index) != 5 or GATE5_PUBLISHED_TYPED_BEHAVIOR_CAPABILITY_ID not in index:
        _fail("gate5_clean_context_capability_projection_invalid")
    return index


def _artifact_index(inventory: Any) -> dict[tuple[str, str, str], _PublishedArtifact]:
    if (
        not isinstance(inventory, dict)
        or inventory.get("schema_version")
        != "broker_reports_gate5_published_artifact_inventory_v1"
        or inventory.get("status") != "repository_truth_snapshot"
        or not isinstance(inventory.get("artifacts"), list)
    ):
        _fail("gate5_clean_context_inventory_invalid")
    Gate5DeclarationProjectionRuntimeFactory.create()
    index: dict[tuple[str, str, str], _PublishedArtifact] = {}
    for artifact in inventory["artifacts"]:
        ref = artifact.get("artifact_ref") if isinstance(artifact, dict) else None
        if not isinstance(ref, dict):
            _fail("gate5_clean_context_inventory_invalid")
        key = (
            ref.get("artifact_kind"),
            ref.get("artifact_id"),
            ref.get("artifact_version"),
        )
        if (
            not all(isinstance(part, str) and part for part in key)
            or key in index
            or artifact.get("publication_status")
            != "published_hash_bound_inactive_proof"
        ):
            _fail("gate5_clean_context_inventory_invalid")
        uses = artifact.get("capability_uses")
        if not isinstance(uses, list) or not all(
            isinstance(use, dict)
            and isinstance(use.get("capability_id"), str)
            and isinstance(use.get("role"), str)
            for use in uses
        ):
            _fail("gate5_clean_context_inventory_invalid")
        index[key] = _PublishedArtifact(
            key=key,
            behavior_id=artifact.get("behavior_id"),
            capability_ids=frozenset(use["capability_id"] for use in uses),
        )
    return index


def _evidence_refs(evidence: Any) -> frozenset[str]:
    requirements = evidence.get("requirements") if isinstance(evidence, dict) else None
    if not isinstance(requirements, list) or not requirements:
        _fail("gate5_clean_context_official_evidence_invalid")
    refs = [item.get("evidence_ref") for item in requirements if isinstance(item, dict)]
    if len(refs) != len(requirements) or any(not isinstance(ref, str) for ref in refs):
        _fail("gate5_clean_context_official_evidence_invalid")
    if len(set(refs)) != len(refs):
        _fail("gate5_clean_context_official_evidence_invalid")
    return frozenset(refs)


def _validate_candidate_semantics(
    *,
    candidate: dict[str, Any],
    target: dict[str, Any],
    capability_index: dict[str, dict[str, Any]],
    artifact_index: dict[tuple[str, str, str], _PublishedArtifact],
    evidence_refs: frozenset[str],
) -> dict[str, Any]:
    if candidate["target"] != target:
        _fail("gate5_clean_context_candidate_target_mismatch")
    if candidate["authoring"] != {
        "supplied_evidence_only": True,
        "prior_project_context_used": False,
        "manual_candidate_repair_allowed": False,
        "notes": candidate["authoring"]["notes"],
    }:
        _fail("gate5_clean_context_candidate_authoring_boundary_invalid")

    requirements: dict[str, dict[str, Any]] = {}
    supported: set[str] = set()
    unsupported: set[str] = set()
    for position, requirement in enumerate(candidate["requirements"]):
        field = f"requirements[{position}]"
        requirement_id = requirement["requirement_id"]
        if requirement_id in requirements:
            _fail("gate5_clean_context_candidate_duplicate_requirement", field)
        if not set(requirement["evidence_refs"]).issubset(evidence_refs):
            _fail("gate5_clean_context_candidate_evidence_unknown", field)
        if requirement["end_to_end_available_from_current_case_evidence"] is not False:
            _fail("gate5_clean_context_candidate_case_evidence_overclaim", field)

        availability = requirement["availability"]
        if availability in {"compilable", "conditionally_compilable"}:
            if requirement["gap_refs"] or not requirement["capability_bindings"]:
                _fail("gate5_clean_context_candidate_supported_unit_invalid", field)
            supported.add(requirement_id)
        else:
            if not requirement["gap_refs"]:
                _fail("gate5_clean_context_candidate_unsupported_unit_invalid", field)
            unsupported.add(requirement_id)
        for binding_position, binding in enumerate(requirement["capability_bindings"]):
            _validate_capability_binding(
                binding=binding,
                capability_index=capability_index,
                artifact_index=artifact_index,
                field=f"{field}.capability_bindings[{binding_position}]",
            )
        requirements[requirement_id] = requirement

    gaps: dict[str, dict[str, Any]] = {}
    published_behavior_ids = {
        artifact.behavior_id
        for artifact in artifact_index.values()
        if artifact.behavior_id
    }
    for position, gap in enumerate(candidate["gaps"]):
        field = f"gaps[{position}]"
        gap_id = gap["gap_id"]
        if gap_id in gaps or gap["requirement_id"] not in requirements:
            _fail("gate5_clean_context_candidate_gap_reference_invalid", field)
        if not set(gap["evidence_refs"]).issubset(evidence_refs):
            _fail("gate5_clean_context_candidate_evidence_unknown", field)
        if not set(gap["related_capability_ids"]).issubset(capability_index):
            _fail("gate5_clean_context_candidate_gap_capability_unknown", field)
        for ref in gap["related_artifact_refs"]:
            _resolve_candidate_artifact(ref, artifact_index, field)
        if gap["gap_type"] == "missing_published_behavior":
            missing = gap["missing_behavior_id"]
            if missing is None or missing in published_behavior_ids:
                _fail("gate5_clean_context_candidate_gap_type_inconsistent", field)
        elif gap["missing_behavior_id"] is not None:
            _fail("gate5_clean_context_candidate_gap_type_inconsistent", field)
        if gap["gap_type"] == "missing_artifact":
            if gap["missing_artifact_kind"] is None:
                _fail("gate5_clean_context_candidate_gap_type_inconsistent", field)
        elif gap["missing_artifact_kind"] is not None:
            _fail("gate5_clean_context_candidate_gap_type_inconsistent", field)
        gaps[gap_id] = gap

    for requirement in requirements.values():
        for gap_ref in requirement["gap_refs"]:
            if (
                gap_ref not in gaps
                or gaps[gap_ref]["requirement_id"] != requirement["requirement_id"]
            ):
                _fail("gate5_clean_context_candidate_gap_reference_invalid")
    for gap_id, gap in gaps.items():
        if gap_id not in requirements[gap["requirement_id"]]["gap_refs"]:
            _fail("gate5_clean_context_candidate_gap_reference_invalid")

    findings = candidate["findings"]
    if (
        set(findings["supported_requirement_ids"]) != supported
        or set(findings["unsupported_requirement_ids"]) != unsupported
        or (
            findings["first_blocking_gap_id"] is not None
            and findings["first_blocking_gap_id"] not in gaps
        )
    ):
        _fail("gate5_clean_context_candidate_findings_invalid")
    expected_status = (
        "partially_compilable"
        if supported and unsupported
        else "compilable"
        if supported
        else "not_compilable"
    )
    if candidate["status"] != expected_status or not supported or not unsupported:
        _fail("gate5_clean_context_candidate_status_invalid")
    return {
        "schema_version": "broker_reports_gate5_clean_context_candidate_validation_v0",
        "status": "passed",
        "definition_id": candidate["definition_id"],
        "requirements_total": len(requirements),
        "supported_requirements_total": len(supported),
        "unsupported_requirements_total": len(unsupported),
        "gaps_total": len(gaps),
        "capability_bindings_total": sum(
            len(requirement["capability_bindings"])
            for requirement in requirements.values()
        ),
        "manual_repairs_total": 0,
    }


def _validate_capability_binding(
    *,
    binding: dict[str, Any],
    capability_index: dict[str, dict[str, Any]],
    artifact_index: dict[tuple[str, str, str], _PublishedArtifact],
    field: str,
) -> None:
    capability = capability_index.get(binding["capability_id"])
    if capability is None:
        _fail("gate5_clean_context_candidate_capability_unknown", field)
    expected_inputs = {item["contract"] for item in capability["inputs"]}
    if set(binding["declared_input_contracts"]) != expected_inputs:
        _fail("gate5_clean_context_candidate_input_contract_mismatch", field)
    if binding["declared_output_contract"] != capability["output"]["contract"]:
        _fail("gate5_clean_context_candidate_output_contract_mismatch", field)
    resolved_artifacts = [
        _resolve_candidate_artifact(ref, artifact_index, field)
        for ref in binding["artifact_refs"]
    ]
    if any(
        binding["capability_id"] not in artifact.capability_ids
        for artifact in resolved_artifacts
    ):
        _fail("gate5_clean_context_candidate_artifact_role_mismatch", field)

    behavior = binding["registered_behavior"]
    if binding["capability_id"] == GATE5_PUBLISHED_TYPED_BEHAVIOR_CAPABILITY_ID:
        if behavior is None:
            _fail("gate5_clean_context_candidate_behavior_binding_missing", field)
        behavior_ref = {
            key: behavior[key]
            for key in (
                "schema_version",
                "methodology_id",
                "methodology_version",
                "behavior_id",
            )
        }
        try:
            described = Gate5PublishedTypedBehaviorRegistryFactory.create().describe(
                behavior_ref
            )
        except Gate5PublishedTypedBehaviorError as exc:
            raise Gate5CleanContextDeclarationTrialError(
                "gate5_clean_context_candidate_behavior_unknown", field
            ) from exc
        if (
            behavior["input_contract_id"] != described["input_contract_id"]
            or behavior["output_contract_id"] != described["output_contract_id"]
        ):
            _fail("gate5_clean_context_candidate_behavior_contract_mismatch", field)
        artifact_key = (
            "trusted_methodology",
            behavior["methodology_id"],
            behavior["methodology_version"],
        )
        if not any(artifact.key == artifact_key for artifact in resolved_artifacts):
            _fail("gate5_clean_context_candidate_behavior_artifact_missing", field)
    elif behavior is not None:
        _fail("gate5_clean_context_candidate_behavior_binding_unexpected", field)


def _resolve_candidate_artifact(
    ref: dict[str, Any],
    artifact_index: dict[tuple[str, str, str], _PublishedArtifact],
    field: str,
) -> _PublishedArtifact:
    key = (ref["artifact_kind"], ref["artifact_id"], ref["artifact_version"])
    artifact = artifact_index.get(key)
    if artifact is None:
        _fail("gate5_clean_context_candidate_artifact_unknown", field)
    return artifact


def _read_resource_bytes(name: str) -> bytes:
    try:
        return resources.files(__package__).joinpath(name).read_bytes()
    except (FileNotFoundError, OSError) as exc:
        raise Gate5CleanContextDeclarationTrialError(
            "gate5_clean_context_resource_unavailable", name
        ) from exc


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _fail(code: str, field: str = "") -> None:
    raise Gate5CleanContextDeclarationTrialError(code, field)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_CLEAN_CONTEXT_DEFINITION_SCHEMA_VERSION",
    "GATE5_CLEAN_CONTEXT_PAYLOAD_RESOURCE",
    "GATE5_CLEAN_CONTEXT_PAYLOAD_RESOURCE_SHA256",
    "GATE5_CLEAN_CONTEXT_TRIAL_ID",
    "GATE5_INDEPENDENT_AUTHORING_TRIAL_ID",
    "GATE5_INDEPENDENT_AUTHORING_CAPTURE_FAILURE_TRIAL_ID",
    "Gate5CleanContextDeclarationTrial",
    "Gate5CleanContextDeclarationTrialError",
    "Gate5CleanContextDeclarationTrialFactory",
    "build_unfrozen_model_payload_for_freeze",
]
