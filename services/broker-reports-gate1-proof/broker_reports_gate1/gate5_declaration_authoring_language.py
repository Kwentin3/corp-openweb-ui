"""Versioned semantic authoring language for independent Declaration Definitions."""

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

from .gate5_clean_context_declaration_trial import (
    Gate5CleanContextDeclarationTrialFactory,
)
from .gate5_declaration_projection import (
    GATE5_DECLARATION_PROJECTION_SECTION2_EVIDENCE_RESOURCE,
    GATE5_DECLARATION_PROJECTION_SECTION2_EVIDENCE_RESOURCE_SHA256,
    GATE5_DECLARATION_PROJECTION_SECTION2_ID,
    GATE5_DECLARATION_PROJECTION_SECTION2_SPEC_RESOURCE_SHA256,
    GATE5_DECLARATION_PROJECTION_SECTION2_VERSION,
    GATE5_DECLARATION_PROJECTION_V1_FRAGMENT_SCHEMA_VERSION,
    GATE5_DECLARATION_PROJECTION_V1_INPUT_SCHEMA_VERSION,
    Gate5DeclarationProjectionRuntimeV1Factory,
)
from .gate5_published_typed_behavior import (
    GATE5_PUBLISHED_BEHAVIOR_REF_SCHEMA_VERSION,
    GATE5_PUBLISHED_TYPED_BEHAVIOR_CAPABILITY_ID,
    Gate5PublishedTypedBehaviorError,
    Gate5PublishedTypedBehaviorRegistryFactory,
)
from .gate5_runtime_capabilities import (
    Gate5RuntimeCapabilityContractV2Factory,
    Gate5RuntimeCapabilityContractV3Factory,
)
from .gate5_trusted_methodology import (
    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
    GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
    Gate5TrustedMethodologyAuthorityFactory,
)


GATE5_DECLARATION_AUTHORING_LANGUAGE_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_authoring_language_v2"
)
GATE5_DECLARATION_AUTHORING_LANGUAGE_PAYLOAD_RESOURCE = (
    "gate5_declaration_authoring_language.primary.v2.payload.json"
)
GATE5_DECLARATION_AUTHORING_LANGUAGE_PAYLOAD_RESOURCE_SHA256 = (
    "90294e3cbecb8c273db51271646dbc9b6281e4db8f2a8d62bcf16a3571633787"
)
GATE5_DECLARATION_AUTHORING_LANGUAGE_TRIAL_ID = "g5.21-primary-2026-08-10-001"
GATE5_DECLARATION_AUTHORING_LANGUAGE_G522_PAYLOAD_RESOURCE = (
    "gate5_declaration_authoring_language.primary.g522.payload.json"
)
GATE5_DECLARATION_AUTHORING_LANGUAGE_G522_PAYLOAD_RESOURCE_SHA256 = (
    "cd186b746aabbe699820e4ec58bd08a8cfd1e7041de373af0d4d2ee971267736"
)
GATE5_DECLARATION_AUTHORING_LANGUAGE_G522_TRIAL_ID = (
    "g5.22-history-free-replay-2026-08-10-001"
)
GATE5_DECLARATION_AUTHORING_LANGUAGE_G523_PAYLOAD_RESOURCE = (
    "gate5_declaration_authoring_language.primary.g523.payload.json"
)
GATE5_DECLARATION_AUTHORING_LANGUAGE_G523_PAYLOAD_RESOURCE_SHA256 = (
    "62fde21f4bc75d32deebf3ac9c650b4506d5f269d3392c6ba97c3af3695a7a9d"
)
GATE5_DECLARATION_AUTHORING_LANGUAGE_G523_TRIAL_ID = (
    "g5.23-history-free-replay-2026-08-10-001"
)
GATE5_DECLARATION_AUTHORING_LANGUAGE_G524_PAYLOAD_RESOURCE = (
    "gate5_declaration_authoring_language.primary.g524.payload.json"
)
GATE5_DECLARATION_AUTHORING_LANGUAGE_G524_PAYLOAD_RESOURCE_SHA256 = (
    "c69a096ad656ccb0c843930977f7ed12b0e148cd5467528dca06ea6fe08241f3"
)
GATE5_DECLARATION_AUTHORING_LANGUAGE_G524_TRIAL_ID = (
    "g5.24-history-free-replay-2026-08-10-001"
)

FACTORY_REQUIRED = (
    "Gate5DeclarationAuthoringLanguageV2Factory.create is the sole v2 payload, "
    "semantic validator and deterministic compiler entrypoint",
    "v1 official evidence, capabilities and inventory are reused through "
    "Gate5CleanContextDeclarationTrialFactory.create",
    "published behavior details resolve through "
    "Gate5PublishedTypedBehaviorRegistryFactory.create",
    "create_g522_replay, create_g523_replay and create_g524_replay preserve each "
    "earlier frozen payload",
)
FORBIDDEN = (
    "previous model candidate, validator errors, expected gap or roadmap in input",
    "model-authored wrapper contracts, implementation signatures or executable code",
    "manual candidate repair, retry, fallback or candidate normalization",
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
    "g5.19",
    "g5.20",
    "previous candidate",
    "validator error",
    "expected gap",
    "first missing capability",
    "appendix8_expense_to_section2_gap",
    "section2_calculation_behavior_gap",
    "group-level tax base",
    "group tax base",
    "line 060",
    "следующий шаг",
)
_G522_BIAS_TERMS = (
    "g5.16",
    "g5.17",
    "g5.18",
    "g5.19",
    "g5.20",
    "g5.21",
    "g5.22",
    "previous candidate",
    "validator error",
    "expected gap",
    "first missing capability",
    "section2_calculation_behavior_missing",
    "section2_projection_artifact_missing",
    "full_electronic_contract_incompatible",
    "следующий шаг",
)
_G523_BIAS_TERMS = (
    "g5.16",
    "g5.17",
    "g5.18",
    "g5.19",
    "g5.20",
    "g5.21",
    "g5.22",
    "g5.23",
    "previous candidate",
    "validator error",
    "expected gap",
    "first missing capability",
    "gap.singleton_category_aggregation",
    "singleton_category_aggregation",
    "следующий шаг",
)
_G524_BIAS_TERMS = (
    "g5.16",
    "g5.17",
    "g5.18",
    "g5.19",
    "g5.20",
    "g5.21",
    "g5.22",
    "g5.23",
    "g5.24",
    "previous candidate",
    "validator error",
    "expected gap",
    "first missing capability",
    "section2_validated_projection_artifact_missing",
    "section2_projection_contract_incompatible",
    "следующий шаг",
)


class Gate5DeclarationAuthoringLanguageError(ValueError):
    def __init__(self, code: str, field: str = "") -> None:
        self.code = code
        self.field = field
        super().__init__(code if not field else f"{code}:{field}")


@dataclass(frozen=True)
class _PublishedArtifactV2:
    key: tuple[str, str, str]
    capability_ids: frozenset[str]


class Gate5DeclarationAuthoringLanguageV2Factory:
    @staticmethod
    def create() -> "Gate5DeclarationAuthoringLanguageV2":
        return _create_language(
            built_payload=_build_model_payload_v2(),
            resource_name=GATE5_DECLARATION_AUTHORING_LANGUAGE_PAYLOAD_RESOURCE,
            resource_sha256=(
                GATE5_DECLARATION_AUTHORING_LANGUAGE_PAYLOAD_RESOURCE_SHA256
            ),
            trial_id=GATE5_DECLARATION_AUTHORING_LANGUAGE_TRIAL_ID,
            bias_terms=_BIAS_TERMS,
        )

    @staticmethod
    def create_g522_replay() -> "Gate5DeclarationAuthoringLanguageV2":
        return _create_language(
            built_payload=_build_model_payload_g522(),
            resource_name=(GATE5_DECLARATION_AUTHORING_LANGUAGE_G522_PAYLOAD_RESOURCE),
            resource_sha256=(
                GATE5_DECLARATION_AUTHORING_LANGUAGE_G522_PAYLOAD_RESOURCE_SHA256
            ),
            trial_id=GATE5_DECLARATION_AUTHORING_LANGUAGE_G522_TRIAL_ID,
            bias_terms=_G522_BIAS_TERMS,
        )

    @staticmethod
    def create_g523_replay() -> "Gate5DeclarationAuthoringLanguageV2":
        return _create_language(
            built_payload=_build_model_payload_g523(),
            resource_name=(GATE5_DECLARATION_AUTHORING_LANGUAGE_G523_PAYLOAD_RESOURCE),
            resource_sha256=(
                GATE5_DECLARATION_AUTHORING_LANGUAGE_G523_PAYLOAD_RESOURCE_SHA256
            ),
            trial_id=GATE5_DECLARATION_AUTHORING_LANGUAGE_G523_TRIAL_ID,
            bias_terms=_G523_BIAS_TERMS,
        )

    @staticmethod
    def create_g524_replay() -> "Gate5DeclarationAuthoringLanguageV2":
        return _create_language(
            built_payload=_build_model_payload_g524(),
            resource_name=(GATE5_DECLARATION_AUTHORING_LANGUAGE_G524_PAYLOAD_RESOURCE),
            resource_sha256=(
                GATE5_DECLARATION_AUTHORING_LANGUAGE_G524_PAYLOAD_RESOURCE_SHA256
            ),
            trial_id=GATE5_DECLARATION_AUTHORING_LANGUAGE_G524_TRIAL_ID,
            bias_terms=_G524_BIAS_TERMS,
            resource_has_terminal_lf=True,
        )


def _create_language(
    *,
    built_payload: dict[str, Any],
    resource_name: str,
    resource_sha256: str,
    trial_id: str,
    bias_terms: tuple[str, ...],
    resource_has_terminal_lf: bool = False,
) -> "Gate5DeclarationAuthoringLanguageV2":
    raw = _read_resource_bytes(resource_name)
    if resource_sha256 == "TO_BE_FROZEN":
        _fail("gate5_declaration_authoring_language_payload_hash_not_frozen")
    if hashlib.sha256(raw).hexdigest() != resource_sha256:
        _fail("gate5_declaration_authoring_language_payload_hash_mismatch")
    expected_raw = _canonical_json(built_payload) + (
        b"\n" if resource_has_terminal_lf else b""
    )
    if raw != expected_raw:
        _fail("gate5_declaration_authoring_language_payload_drift")
    try:
        payload: Any = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Gate5DeclarationAuthoringLanguageError(
            "gate5_declaration_authoring_language_payload_json_invalid"
        ) from exc
    if payload != built_payload:
        _fail("gate5_declaration_authoring_language_payload_drift")

    bias_audit = _bias_audit(payload, terms=bias_terms)
    capability_index = _capability_index(payload["runtime_capabilities"])
    artifact_index = _artifact_index(payload["published_artifact_inventory"])
    evidence_refs = _evidence_refs(payload["official_evidence"])
    _validate_output_schema(payload["output_schema"])
    return Gate5DeclarationAuthoringLanguageV2(
        payload=copy.deepcopy(payload),
        payload_bytes=raw,
        bias_audit=copy.deepcopy(bias_audit),
        capability_index=capability_index,
        artifact_index=artifact_index,
        evidence_refs=evidence_refs,
        trial_id=trial_id,
    )


class Gate5DeclarationAuthoringLanguageV2:
    def __init__(
        self,
        *,
        payload: dict[str, Any],
        payload_bytes: bytes,
        bias_audit: dict[str, Any],
        capability_index: dict[str, dict[str, Any]],
        artifact_index: dict[tuple[str, str, str], _PublishedArtifactV2],
        evidence_refs: frozenset[str],
        trial_id: str,
    ) -> None:
        self._payload = payload
        self._payload_bytes = payload_bytes
        self._bias_audit = bias_audit
        self._capability_index = capability_index
        self._artifact_index = artifact_index
        self._evidence_refs = evidence_refs
        self._trial_id = trial_id

    def model_payload(self) -> dict[str, Any]:
        return copy.deepcopy(self._payload)

    def model_payload_bytes(self) -> bytes:
        return bytes(self._payload_bytes)

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
        payload_bytes = self.model_payload_bytes()
        schema_bytes = _canonical_json(self._payload["output_schema"])
        return {
            "schema_version": (
                "broker_reports_gate5_declaration_authoring_language_trial_plan_v2"
            ),
            "trial_id": self._trial_id,
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
            "derived_metadata_policy": {
                "capability_io_contracts": "deterministic_resolver",
                "behavior_io_contracts": "deterministic_registry",
                "definition_status": "deterministic_compiler",
                "case_input_assessment": "not_evaluated_no_case_evidence",
            },
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
        if not isinstance(response_bytes, bytes) or not response_bytes:
            _fail("gate5_declaration_authoring_language_candidate_response_empty")
        try:
            candidate: Any = json.loads(response_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Gate5DeclarationAuthoringLanguageError(
                "gate5_declaration_authoring_language_candidate_response_invalid"
            ) from exc
        if not isinstance(candidate, dict):
            _fail("gate5_declaration_authoring_language_candidate_response_not_object")
        return copy.deepcopy(candidate)

    def validate_candidate_response(self, response_bytes: bytes) -> dict[str, Any]:
        return self.validate_candidate(self.parse_candidate_response(response_bytes))

    def validate_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        try:
            Draft202012Validator(self._payload["output_schema"]).validate(candidate)
        except ValidationError as exc:
            field = ".".join(str(part) for part in exc.absolute_path)
            raise Gate5DeclarationAuthoringLanguageError(
                "gate5_declaration_authoring_language_candidate_schema_invalid",
                field,
            ) from exc
        return _compile_candidate(
            candidate=copy.deepcopy(candidate),
            target=self._payload["official_evidence"]["declaration"],
            capability_index=self._capability_index,
            artifact_index=self._artifact_index,
            evidence_refs=self._evidence_refs,
        )


def build_unfrozen_declaration_authoring_language_payload_v2() -> dict[str, Any]:
    """Build the deterministic v2 payload before its one semantic freeze."""
    return _build_model_payload_v2()


def build_unfrozen_declaration_authoring_language_payload_g522() -> dict[str, Any]:
    """Build the additive G5.22 replay inventory before freezing it."""
    return _build_model_payload_g522()


def build_unfrozen_declaration_authoring_language_payload_g523() -> dict[str, Any]:
    """Build the G5.23 replay payload before freezing its exact bytes."""
    return _build_model_payload_g523()


def build_unfrozen_declaration_authoring_language_payload_g524() -> dict[str, Any]:
    """Build the G5.24 replay payload before freezing its exact bytes."""
    return _build_model_payload_g524()


def _build_model_payload_v2() -> dict[str, Any]:
    base = Gate5CleanContextDeclarationTrialFactory.create().model_payload()
    payload = {
        "system_instructions": {
            "task": (
                "Using only the supplied official evidence, runtime capabilities "
                "and published artifacts, author one machine-readable Declaration "
                "Definition for the supported and unsupported 2025 3-NDFL "
                "securities-disposal declaration surface."
            ),
            "language_semantics": [
                "The target object owns form, order, period and electronic-format identity; requirements contain only declaration semantics whose production must be assessed.",
                "runtime_support states whether supplied runtime capabilities and published artifacts can produce the requirement semantic; it does not claim that case-time input values are currently present.",
                "No case evidence is supplied in this authoring context. The deterministic compiler records case-input availability as not evaluated instead of asking the author to guess it.",
                "A composition names only semantic capability identity, optional published behavior identity and published artifact identities. Exact capability and behavior input/output contracts are resolved by ordinary code.",
                "An unsupported requirement may retain compositions for supported sub-semantics and must link the remaining unsupported semantic to one or more typed gaps.",
                "A gap describes the required semantic, its taxonomy class and relevant existing identities. Do not invent an identifier for an absent behavior, capability, artifact, input kind or contract.",
                "Order requirements by dependency. first_blocking_gap_id must belong to the first unsupported or evidence-missing requirement in that order.",
            ],
            "rules": [
                "Use only supplied official evidence for declaration claims.",
                "Use only capability, behavior and artifact identities present in the supplied sections.",
                "Do not invent a capability, behavior, artifact, value kind, evidence source, tax rule or executable formula.",
                "Do not treat required case-time inputs as currently available.",
                "Do not emit actions, steps, code, commands, tools, XML, PDF, tax payable or chain-of-thought.",
                "Return exactly one object conforming to the supplied closed output schema.",
            ],
        },
        "research_policy": copy.deepcopy(base["research_policy"]),
        "runtime_capabilities": copy.deepcopy(base["runtime_capabilities"]),
        "published_artifact_inventory": copy.deepcopy(
            base["published_artifact_inventory"]
        ),
        "official_evidence": copy.deepcopy(base["official_evidence"]),
        "output_schema": _output_schema_v2(),
    }
    if tuple(payload) != _MODEL_PAYLOAD_SECTION_NAMES:
        _fail("gate5_declaration_authoring_language_payload_sections_invalid")
    _bias_audit(payload)
    _capability_index(payload["runtime_capabilities"])
    _artifact_index(payload["published_artifact_inventory"])
    _evidence_refs(payload["official_evidence"])
    _validate_output_schema(payload["output_schema"])
    return payload


def _build_model_payload_g522() -> dict[str, Any]:
    payload = _build_model_payload_v2()
    inventory = payload["published_artifact_inventory"]
    inventory["inventory_version"] = "2026.2-proof"
    inventory["artifacts"].append(_income_group_tax_base_inventory_artifact())
    _bias_audit(payload, terms=_G522_BIAS_TERMS)
    _artifact_index(inventory)
    return payload


def _build_model_payload_g523() -> dict[str, Any]:
    payload = _build_model_payload_g522()
    payload["runtime_capabilities"] = (
        Gate5RuntimeCapabilityContractV2Factory.create().model_projection()
    )
    payload["system_instructions"]["language_semantics"].append(
        "Every listed composition must be an executable supported sub-semantic and include every required suitable published artifact. If no suitable artifact is supplied, omit that composition and describe the unsupported semantic only in a typed gap."
    )
    _bias_audit(payload, terms=_G523_BIAS_TERMS)
    _capability_index(payload["runtime_capabilities"])
    _artifact_index(payload["published_artifact_inventory"])
    return payload


def _build_model_payload_g524() -> dict[str, Any]:
    payload = _build_model_payload_g523()
    payload["runtime_capabilities"] = (
        Gate5RuntimeCapabilityContractV3Factory.create().model_projection()
    )
    inventory = payload["published_artifact_inventory"]
    inventory["inventory_version"] = "2026.3-proof"
    appendix8 = next(
        artifact
        for artifact in inventory["artifacts"]
        if artifact["artifact_ref"]
        == {
            "artifact_kind": "validated_declaration_projection",
            "artifact_id": "ru-3ndfl-2025-appendix8-securities-proof",
            "artifact_version": "2026.0-proof",
        }
    )
    appendix8["capability_uses"] = [
        {
            "capability_id": "project_validated_declaration_fragment_v1",
            "role": "validated_projection",
        },
        {
            "capability_id": "aggregate_complete_category_scope_v0",
            "role": "nested_projection_for_complete_scope",
        },
    ]
    appendix8["semantic_output_contract"] = (
        GATE5_DECLARATION_PROJECTION_V1_FRAGMENT_SCHEMA_VERSION
    )
    appendix8["semantic_output_meaning"] = (
        "One deterministic declaration-shaped Appendix 8 securities occurrence "
        "in the common versioned fragment envelope."
    )
    inventory["artifacts"].append(_section2_projection_inventory_artifact())
    _bias_audit(payload, terms=_G524_BIAS_TERMS)
    _capability_index(payload["runtime_capabilities"])
    _artifact_index(inventory)
    return payload


def _section2_projection_inventory_artifact() -> dict[str, Any]:
    Gate5DeclarationProjectionRuntimeV1Factory.create()
    evidence = _decode_resource_json(
        GATE5_DECLARATION_PROJECTION_SECTION2_EVIDENCE_RESOURCE
    )
    return {
        "artifact_ref": {
            "artifact_kind": "validated_declaration_projection",
            "artifact_id": GATE5_DECLARATION_PROJECTION_SECTION2_ID,
            "artifact_version": GATE5_DECLARATION_PROJECTION_SECTION2_VERSION,
        },
        "authority_binding": {
            "resource_sha256": (
                GATE5_DECLARATION_PROJECTION_SECTION2_SPEC_RESOURCE_SHA256
            ),
            "projection_sha256": (
                GATE5_DECLARATION_PROJECTION_SECTION2_EVIDENCE_RESOURCE_SHA256
            ),
            "reference_ids": [
                claim["evidence_ref"] for claim in evidence["claims"]
            ],
        },
        "behavior_id": None,
        "capability_uses": [
            {
                "capability_id": "project_validated_declaration_fragment_v1",
                "role": "validated_projection",
            }
        ],
        "publication_status": "published_hash_bound_inactive_proof",
        "semantic_input_contract": (
            GATE5_DECLARATION_PROJECTION_V1_INPUT_SCHEMA_VERSION
        ),
        "semantic_input_meaning": (
            "One complete owner-validated stable income-group Tax Model for the "
            "registered resident securities and derivatives non-IIS semantic."
        ),
        "semantic_output_contract": (
            GATE5_DECLARATION_PROJECTION_V1_FRAGMENT_SCHEMA_VERSION
        ),
        "semantic_output_meaning": (
            "One group-bound declaration-shaped Section 2 lines 001-060 partial "
            "fragment; no tax, full XML or full-document claim."
        ),
        "typed_execution_binding": None,
    }


def _decode_resource_json(resource_name: str) -> dict[str, Any]:
    try:
        value: Any = json.loads(_read_resource_bytes(resource_name).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Gate5DeclarationAuthoringLanguageError(
            "gate5_declaration_authoring_language_payload_resource_invalid"
        ) from exc
    if not isinstance(value, dict):
        _fail("gate5_declaration_authoring_language_payload_resource_invalid")
    return value


def _income_group_tax_base_inventory_artifact() -> dict[str, Any]:
    methodology_ref = {
        "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
        "methodology_id": GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
        "methodology_version": (
            GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_VERSION
        ),
    }
    resolved = Gate5TrustedMethodologyAuthorityFactory.create().resolve(methodology_ref)
    behavior = resolved["methodology"]["behavior"]
    described = Gate5PublishedTypedBehaviorRegistryFactory.create().describe(
        {
            "schema_version": GATE5_PUBLISHED_BEHAVIOR_REF_SCHEMA_VERSION,
            "methodology_id": methodology_ref["methodology_id"],
            "methodology_version": methodology_ref["methodology_version"],
            "behavior_id": behavior["behavior_id"],
        }
    )
    authority = resolved["authority_binding"]
    return {
        "artifact_ref": {
            "artifact_kind": "trusted_methodology",
            "artifact_id": methodology_ref["methodology_id"],
            "artifact_version": methodology_ref["methodology_version"],
        },
        "authority_binding": {
            "resource_sha256": authority["resource_sha256"],
            "projection_sha256": authority["projection_sha256"],
            "reference_ids": [
                item["evidence_ref"]
                for item in resolved["methodology"]["legal_evidence"]
            ],
        },
        "behavior_id": behavior["behavior_id"],
        "capability_uses": [
            {
                "capability_id": GATE5_PUBLISHED_TYPED_BEHAVIOR_CAPABILITY_ID,
                "role": "registered_typed_execution",
            }
        ],
        "publication_status": "published_hash_bound_inactive_proof",
        "semantic_input_contract": described["input_contract_id"],
        "semantic_input_meaning": (
            "One validated complete category Tax Model plus explicit user-verified "
            "whole-group income, expense, non-taxable and deduction values with "
            "an exact input-bound completeness assertion."
        ),
        "semantic_output_contract": described["output_contract_id"],
        "semantic_output_meaning": (
            "One provenance-retaining stable income-group total income, taxable "
            "income, accepted expenses and tax-base model without form projection."
        ),
        "typed_execution_binding": {
            "execution_capability_id": (GATE5_PUBLISHED_TYPED_BEHAVIOR_CAPABILITY_ID),
            "behavior_ref": {
                "schema_version": GATE5_PUBLISHED_BEHAVIOR_REF_SCHEMA_VERSION,
                "methodology_id": methodology_ref["methodology_id"],
                "methodology_version": methodology_ref["methodology_version"],
                "behavior_id": behavior["behavior_id"],
            },
            "input_contract_id": described["input_contract_id"],
            "output_contract_id": described["output_contract_id"],
        },
    }


def _output_schema_v2() -> dict[str, Any]:
    identifier = {"type": "string", "pattern": "^[a-z][a-z0-9_.-]{0,127}$"}
    artifact_ref = {
        "type": "object",
        "additionalProperties": False,
        "required": ["artifact_kind", "artifact_id", "artifact_version"],
        "properties": {
            "artifact_kind": copy.deepcopy(identifier),
            "artifact_id": copy.deepcopy(identifier),
            "artifact_version": {"type": "string", "minLength": 1, "maxLength": 64},
        },
    }
    behavior_ref = {
        "type": "object",
        "additionalProperties": False,
        "required": ["methodology_id", "methodology_version", "behavior_id"],
        "properties": {
            "methodology_id": copy.deepcopy(identifier),
            "methodology_version": {
                "type": "string",
                "minLength": 1,
                "maxLength": 64,
            },
            "behavior_id": copy.deepcopy(identifier),
        },
    }
    composition = {
        "type": "object",
        "additionalProperties": False,
        "required": ["capability_id", "behavior_ref", "artifact_refs"],
        "properties": {
            "capability_id": copy.deepcopy(identifier),
            "behavior_ref": {"anyOf": [copy.deepcopy(behavior_ref), {"type": "null"}]},
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
            "runtime_support",
            "compositions",
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
            "runtime_support": {
                "enum": ["supported", "unsupported", "evidence_missing"]
            },
            "compositions": {"type": "array", "items": composition},
            "gap_refs": {"type": "array", "items": copy.deepcopy(identifier)},
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
            "required_semantic": {
                "type": "string",
                "minLength": 1,
                "maxLength": 1200,
            },
            "related_capability_ids": {
                "type": "array",
                "items": copy.deepcopy(identifier),
            },
            "related_artifact_refs": {
                "type": "array",
                "items": copy.deepcopy(artifact_ref),
            },
            "evidence_refs": {
                "type": "array",
                "minItems": 1,
                "items": copy.deepcopy(identifier),
            },
            "explanation": {
                "type": "string",
                "minLength": 1,
                "maxLength": 1200,
            },
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
            "target",
            "scope",
            "requirements",
            "gaps",
            "first_blocking_gap_id",
        ],
        "properties": {
            "schema_version": {
                "type": "string",
                "const": GATE5_DECLARATION_AUTHORING_LANGUAGE_SCHEMA_VERSION,
            },
            "definition_id": copy.deepcopy(identifier),
            "definition_version": {
                "type": "string",
                "minLength": 1,
                "maxLength": 64,
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
                    "electronic_format_version": {
                        "type": "string",
                        "minLength": 1,
                    },
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
                    "boundary": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 1000,
                    },
                },
            },
            "requirements": {
                "type": "array",
                "minItems": 1,
                "maxItems": 20,
                "items": requirement,
            },
            "gaps": {"type": "array", "maxItems": 20, "items": gap},
            "first_blocking_gap_id": {
                "anyOf": [copy.deepcopy(identifier), {"type": "null"}]
            },
        },
    }


def _validate_output_schema(schema: Any) -> None:
    if not isinstance(schema, dict):
        _fail("gate5_declaration_authoring_language_output_schema_invalid")
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise Gate5DeclarationAuthoringLanguageError(
            "gate5_declaration_authoring_language_output_schema_invalid"
        ) from exc
    rendered = json.dumps(schema, ensure_ascii=False).lower()
    if any(term in rendered for term in _BIAS_TERMS):
        _fail("gate5_declaration_authoring_language_output_schema_bias_detected")


def _bias_audit(
    payload: Any,
    *,
    terms: tuple[str, ...] = _BIAS_TERMS,
) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != set(
        _MODEL_PAYLOAD_SECTION_NAMES
    ):
        _fail("gate5_declaration_authoring_language_payload_sections_invalid")
    disallowed_hits: list[dict[str, str]] = []
    official_hits: list[dict[str, str]] = []
    for section in _MODEL_PAYLOAD_SECTION_NAMES:
        for path, value in _strings(payload[section], section):
            lowered = value.lower()
            for term in terms:
                if term in lowered:
                    hit = {"term": term, "path": path}
                    if section == "official_evidence":
                        official_hits.append(hit)
                    else:
                        disallowed_hits.append(hit)
    if disallowed_hits:
        _fail("gate5_declaration_authoring_language_payload_bias_detected")
    return {
        "schema_version": "broker_reports_gate5_declaration_authoring_bias_audit_v2",
        "status": "passed",
        "policy": "no_history_error_or_expected_gap_outside_official_evidence_v2",
        "forbidden_terms": list(terms),
        "disallowed_hits": disallowed_hits,
        "official_evidence_allowed_hits": official_hits,
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
    capabilities = (
        projection.get("capabilities") if isinstance(projection, dict) else None
    )
    if not isinstance(capabilities, list):
        _fail("gate5_declaration_authoring_language_capability_projection_invalid")
    index: dict[str, dict[str, Any]] = {}
    for capability in capabilities:
        capability_id = (
            capability.get("capability_id") if isinstance(capability, dict) else None
        )
        if (
            not isinstance(capability_id, str)
            or capability_id in index
            or capability.get("implementation_status") != "proven"
            or capability.get("execution_phase") != "case_time"
        ):
            _fail("gate5_declaration_authoring_language_capability_projection_invalid")
        index[capability_id] = copy.deepcopy(capability)
    if len(index) != 5 or GATE5_PUBLISHED_TYPED_BEHAVIOR_CAPABILITY_ID not in index:
        _fail("gate5_declaration_authoring_language_capability_projection_invalid")
    return index


def _artifact_index(
    inventory: Any,
) -> dict[tuple[str, str, str], _PublishedArtifactV2]:
    if (
        not isinstance(inventory, dict)
        or not isinstance(inventory.get("artifacts"), list)
        or inventory.get("schema_version")
        != "broker_reports_gate5_published_artifact_inventory_v1"
        or inventory.get("status") != "repository_truth_snapshot"
    ):
        _fail("gate5_declaration_authoring_language_inventory_invalid")
    artifacts = inventory["artifacts"]
    index: dict[tuple[str, str, str], _PublishedArtifactV2] = {}
    for artifact in artifacts:
        ref = artifact.get("artifact_ref") if isinstance(artifact, dict) else None
        uses = artifact.get("capability_uses") if isinstance(artifact, dict) else None
        if not isinstance(ref, dict) or not isinstance(uses, list):
            _fail("gate5_declaration_authoring_language_inventory_invalid")
        key = (
            ref.get("artifact_kind"),
            ref.get("artifact_id"),
            ref.get("artifact_version"),
        )
        if (
            not all(isinstance(part, str) and part for part in key)
            or key in index
            or not all(
                isinstance(use, dict) and isinstance(use.get("capability_id"), str)
                for use in uses
            )
        ):
            _fail("gate5_declaration_authoring_language_inventory_invalid")
        index[key] = _PublishedArtifactV2(
            key=key,
            capability_ids=frozenset(use["capability_id"] for use in uses),
        )
    return index


def _evidence_refs(evidence: Any) -> frozenset[str]:
    requirements = evidence.get("requirements") if isinstance(evidence, dict) else None
    if not isinstance(requirements, list) or not requirements:
        _fail("gate5_declaration_authoring_language_official_evidence_invalid")
    refs = [item.get("evidence_ref") for item in requirements if isinstance(item, dict)]
    if (
        len(refs) != len(requirements)
        or any(not isinstance(ref, str) for ref in refs)
        or len(set(refs)) != len(refs)
    ):
        _fail("gate5_declaration_authoring_language_official_evidence_invalid")
    return frozenset(refs)


def _compile_candidate(
    *,
    candidate: dict[str, Any],
    target: dict[str, Any],
    capability_index: dict[str, dict[str, Any]],
    artifact_index: dict[tuple[str, str, str], _PublishedArtifactV2],
    evidence_refs: frozenset[str],
) -> dict[str, Any]:
    if candidate["target"] != target:
        _fail("gate5_declaration_authoring_language_candidate_target_mismatch")

    requirements: dict[str, dict[str, Any]] = {}
    compiled_requirements: list[dict[str, Any]] = []
    for position, requirement in enumerate(candidate["requirements"]):
        field = f"requirements[{position}]"
        requirement_id = requirement["requirement_id"]
        if requirement_id in requirements:
            _fail("gate5_declaration_authoring_language_duplicate_requirement", field)
        _require_unique_nonempty_strings(requirement["evidence_refs"], field)
        _require_unique_nonempty_strings(requirement["semantic_outputs"], field)
        _require_unique_nonempty_strings(requirement["gap_refs"], field)
        if not set(requirement["evidence_refs"]).issubset(evidence_refs):
            _fail("gate5_declaration_authoring_language_evidence_unknown", field)

        support = requirement["runtime_support"]
        if support == "supported":
            if requirement["gap_refs"] or not requirement["compositions"]:
                _fail(
                    "gate5_declaration_authoring_language_supported_unit_invalid",
                    field,
                )
            case_input_status = "not_evaluated_no_case_evidence"
        else:
            if not requirement["gap_refs"]:
                _fail(
                    "gate5_declaration_authoring_language_unsupported_unit_invalid",
                    field,
                )
            case_input_status = "not_applicable_until_runtime_support"

        compiled_compositions = []
        composition_keys: set[tuple[str, str, str, str]] = set()
        for composition_position, composition in enumerate(requirement["compositions"]):
            composition_field = f"{field}.compositions[{composition_position}]"
            compiled = _resolve_composition(
                composition=composition,
                capability_index=capability_index,
                artifact_index=artifact_index,
                field=composition_field,
            )
            behavior = composition["behavior_ref"] or {}
            key = (
                composition["capability_id"],
                behavior.get("methodology_id", ""),
                behavior.get("methodology_version", ""),
                behavior.get("behavior_id", ""),
            )
            if key in composition_keys:
                _fail(
                    "gate5_declaration_authoring_language_duplicate_composition",
                    composition_field,
                )
            composition_keys.add(key)
            compiled_compositions.append(compiled)

        requirements[requirement_id] = requirement
        compiled_requirements.append(
            {
                "requirement_id": requirement_id,
                "runtime_support": support,
                "case_input_status": case_input_status,
                "resolved_compositions": compiled_compositions,
            }
        )

    gaps: dict[str, dict[str, Any]] = {}
    for position, gap in enumerate(candidate["gaps"]):
        field = f"gaps[{position}]"
        gap_id = gap["gap_id"]
        requirement = requirements.get(gap["requirement_id"])
        if gap_id in gaps or requirement is None:
            _fail("gate5_declaration_authoring_language_gap_reference_invalid", field)
        _require_unique_nonempty_strings(gap["related_capability_ids"], field)
        _require_unique_nonempty_strings(gap["evidence_refs"], field)
        if not set(gap["related_capability_ids"]).issubset(capability_index):
            _fail("gate5_declaration_authoring_language_capability_unknown", field)
        if not set(gap["evidence_refs"]).issubset(evidence_refs):
            _fail("gate5_declaration_authoring_language_evidence_unknown", field)
        _resolve_artifact_refs(gap["related_artifact_refs"], artifact_index, field)
        support = requirement["runtime_support"]
        if support == "evidence_missing" and gap["gap_type"] != "missing_evidence":
            _fail("gate5_declaration_authoring_language_gap_type_inconsistent", field)
        if support == "unsupported" and gap["gap_type"] == "missing_evidence":
            _fail("gate5_declaration_authoring_language_gap_type_inconsistent", field)
        gaps[gap_id] = gap

    for requirement in requirements.values():
        for gap_ref in requirement["gap_refs"]:
            if (
                gap_ref not in gaps
                or gaps[gap_ref]["requirement_id"] != requirement["requirement_id"]
            ):
                _fail("gate5_declaration_authoring_language_gap_reference_invalid")
    for gap_id, gap in gaps.items():
        if gap_id not in requirements[gap["requirement_id"]]["gap_refs"]:
            _fail("gate5_declaration_authoring_language_gap_reference_invalid")

    first_unsupported = next(
        (
            requirement
            for requirement in candidate["requirements"]
            if requirement["runtime_support"] != "supported"
        ),
        None,
    )
    first_gap_id = candidate["first_blocking_gap_id"]
    if first_unsupported is None:
        if gaps or first_gap_id is not None:
            _fail("gate5_declaration_authoring_language_first_blocker_invalid")
    elif first_gap_id not in first_unsupported["gap_refs"]:
        _fail("gate5_declaration_authoring_language_first_blocker_invalid")

    supported_total = sum(
        requirement["runtime_support"] == "supported"
        for requirement in candidate["requirements"]
    )
    unsupported_total = len(candidate["requirements"]) - supported_total
    definition_status = (
        "partially_compilable"
        if supported_total and unsupported_total
        else "compilable"
        if supported_total
        else "not_compilable"
    )
    return {
        "schema_version": "broker_reports_gate5_declaration_definition_compilation_v2",
        "status": "passed",
        "definition_id": candidate["definition_id"],
        "definition_status": definition_status,
        "case_input_assessment": {
            "status": "not_evaluated",
            "reason": "no_case_evidence_in_authoring_context",
        },
        "requirements": compiled_requirements,
        "gaps": copy.deepcopy(candidate["gaps"]),
        "first_blocking_gap_id": first_gap_id,
        "requirements_total": len(candidate["requirements"]),
        "supported_requirements_total": supported_total,
        "unsupported_requirements_total": unsupported_total,
        "gaps_total": len(gaps),
        "resolved_compositions_total": sum(
            len(item["resolved_compositions"]) for item in compiled_requirements
        ),
        "manual_repairs_total": 0,
    }


def _resolve_composition(
    *,
    composition: dict[str, Any],
    capability_index: dict[str, dict[str, Any]],
    artifact_index: dict[tuple[str, str, str], _PublishedArtifactV2],
    field: str,
) -> dict[str, Any]:
    capability_id = composition["capability_id"]
    capability = capability_index.get(capability_id)
    if capability is None:
        _fail("gate5_declaration_authoring_language_capability_unknown", field)
    artifacts = _resolve_artifact_refs(
        composition["artifact_refs"], artifact_index, field
    )
    eligible_artifacts_exist = any(
        capability_id in artifact.capability_ids for artifact in artifact_index.values()
    )
    if eligible_artifacts_exist and not artifacts:
        _fail("gate5_declaration_authoring_language_artifact_missing", field)
    if any(capability_id not in artifact.capability_ids for artifact in artifacts):
        _fail("gate5_declaration_authoring_language_artifact_role_mismatch", field)

    behavior = composition["behavior_ref"]
    resolved_behavior: dict[str, Any] | None = None
    if capability_id == GATE5_PUBLISHED_TYPED_BEHAVIOR_CAPABILITY_ID:
        if behavior is None:
            _fail("gate5_declaration_authoring_language_behavior_missing", field)
        full_ref = {
            "schema_version": GATE5_PUBLISHED_BEHAVIOR_REF_SCHEMA_VERSION,
            **behavior,
        }
        try:
            described = Gate5PublishedTypedBehaviorRegistryFactory.create().describe(
                full_ref
            )
        except Gate5PublishedTypedBehaviorError as exc:
            raise Gate5DeclarationAuthoringLanguageError(
                "gate5_declaration_authoring_language_behavior_unknown", field
            ) from exc
        methodology_key = (
            "trusted_methodology",
            behavior["methodology_id"],
            behavior["methodology_version"],
        )
        if not any(artifact.key == methodology_key for artifact in artifacts):
            _fail(
                "gate5_declaration_authoring_language_behavior_artifact_missing",
                field,
            )
        resolved_behavior = {
            "behavior_ref": full_ref,
            "input_contract_id": described["input_contract_id"],
            "output_contract_id": described["output_contract_id"],
        }
    elif behavior is not None:
        _fail("gate5_declaration_authoring_language_behavior_unexpected", field)

    return {
        "capability_id": capability_id,
        "capability_inputs": copy.deepcopy(capability["inputs"]),
        "capability_output_contract": capability["output"]["contract"],
        "behavior_binding": resolved_behavior,
        "artifact_refs": copy.deepcopy(composition["artifact_refs"]),
    }


def _resolve_artifact_refs(
    refs: list[dict[str, Any]],
    artifact_index: dict[tuple[str, str, str], _PublishedArtifactV2],
    field: str,
) -> list[_PublishedArtifactV2]:
    resolved = []
    seen: set[tuple[str, str, str]] = set()
    for ref in refs:
        key = (ref["artifact_kind"], ref["artifact_id"], ref["artifact_version"])
        artifact = artifact_index.get(key)
        if artifact is None:
            _fail("gate5_declaration_authoring_language_artifact_unknown", field)
        if key in seen:
            _fail("gate5_declaration_authoring_language_duplicate_artifact", field)
        seen.add(key)
        resolved.append(artifact)
    return resolved


def _require_unique_nonempty_strings(values: list[str], field: str) -> None:
    if len(set(values)) != len(values):
        _fail("gate5_declaration_authoring_language_duplicate_reference", field)


def _read_resource_bytes(name: str) -> bytes:
    try:
        return resources.files(__package__).joinpath(name).read_bytes()
    except (FileNotFoundError, OSError) as exc:
        raise Gate5DeclarationAuthoringLanguageError(
            "gate5_declaration_authoring_language_resource_unavailable", name
        ) from exc


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _fail(code: str, field: str = "") -> None:
    raise Gate5DeclarationAuthoringLanguageError(code, field)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_DECLARATION_AUTHORING_LANGUAGE_PAYLOAD_RESOURCE",
    "GATE5_DECLARATION_AUTHORING_LANGUAGE_PAYLOAD_RESOURCE_SHA256",
    "GATE5_DECLARATION_AUTHORING_LANGUAGE_G522_PAYLOAD_RESOURCE",
    "GATE5_DECLARATION_AUTHORING_LANGUAGE_G522_PAYLOAD_RESOURCE_SHA256",
    "GATE5_DECLARATION_AUTHORING_LANGUAGE_G522_TRIAL_ID",
    "GATE5_DECLARATION_AUTHORING_LANGUAGE_G523_PAYLOAD_RESOURCE",
    "GATE5_DECLARATION_AUTHORING_LANGUAGE_G523_PAYLOAD_RESOURCE_SHA256",
    "GATE5_DECLARATION_AUTHORING_LANGUAGE_G523_TRIAL_ID",
    "GATE5_DECLARATION_AUTHORING_LANGUAGE_G524_PAYLOAD_RESOURCE",
    "GATE5_DECLARATION_AUTHORING_LANGUAGE_G524_PAYLOAD_RESOURCE_SHA256",
    "GATE5_DECLARATION_AUTHORING_LANGUAGE_G524_TRIAL_ID",
    "GATE5_DECLARATION_AUTHORING_LANGUAGE_SCHEMA_VERSION",
    "GATE5_DECLARATION_AUTHORING_LANGUAGE_TRIAL_ID",
    "Gate5DeclarationAuthoringLanguageError",
    "Gate5DeclarationAuthoringLanguageV2",
    "Gate5DeclarationAuthoringLanguageV2Factory",
    "build_unfrozen_declaration_authoring_language_payload_v2",
    "build_unfrozen_declaration_authoring_language_payload_g522",
    "build_unfrozen_declaration_authoring_language_payload_g523",
    "build_unfrozen_declaration_authoring_language_payload_g524",
]
