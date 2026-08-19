"""Validate one bounded LLM-authored Declaration Definition candidate."""

from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
from importlib import resources
import json
import re
from typing import Any

from .gate5_declaration_projection import (
    GATE5_DECLARATION_PROJECTION_FRAGMENT_SCHEMA_VERSION,
    GATE5_DECLARATION_PROJECTION_SPEC_RESOURCE,
    Gate5DeclarationProjectionRuntimeFactory,
)
from .gate5_runtime_capabilities import (
    GATE5_RUNTIME_CAPABILITY_REF_SCHEMA_VERSION,
    Gate5RuntimeCapabilityContractFactory,
    Gate5RuntimeCapabilityResolverFactory,
)
from .gate5_securities_disposal_tax_model import (
    GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION,
    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_SCHEMA_VERSION,
)
from .gate5_trusted_methodology import (
    GATE5_TRUSTED_CALCULATION_RESULT_SCHEMA_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
    Gate5TrustedMethodologyAuthorityFactory,
)


GATE5_DECLARATION_DEFINITION_CONTEXT_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_definition_authoring_context_v0"
)
GATE5_DECLARATION_DEFINITION_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_definition_v0"
)
GATE5_DECLARATION_DEFINITION_VALIDATION_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_definition_validation_v0"
)
GATE5_DECLARATION_DEFINITION_CONTEXT_RESOURCE = (
    "gate5_declaration_definition_authoring_context.v0.json"
)
GATE5_DECLARATION_DEFINITION_CONTEXT_RESOURCE_SHA256 = (
    "84c0258a371c02427c28809546d673a9687aec88f3cbf19640c4ccc1b1be0428"
)
GATE5_DECLARATION_DEFINITION_CANDIDATE_RESOURCE = (
    "gate5_declaration_definition_candidate.ru_3ndfl_2025_securities.v0.json"
)
GATE5_DECLARATION_DEFINITION_CANDIDATE_RESOURCE_SHA256 = (
    "04dbf40a413343e25870ffcb045df3d5ec2baa15dee4c0ca8a4b20c91df50f4a"
)

FACTORY_REQUIRED = (
    "Gate5DeclarationDefinitionAuthoringFactory.create is the only context, "
    "inventory and validator construction entrypoint",
    "candidate capability references resolve only through "
    "Gate5RuntimeCapabilityResolverFactory.create",
    "published methodology and projection references are checked through "
    "their existing reviewed owners",
)
FORBIDDEN = (
    "case-time research, model calls, production calculation or declaration execution",
    "dynamic action, step, expression, formula, script, command or tool fields",
    "unknown capability fallback, generated capability, generated methodology behavior",
    "workflow engine, rules DSL, plugin registry, database, XML, PDF, GUI or activation",
)

_CONTEXT_KEYS = {
    "schema_version",
    "context_id",
    "context_version",
    "status",
    "system_instructions",
    "research_policy",
    "published_artifact_inventory",
    "official_evidence",
    "output_schema",
}
_DEFINITION_KEYS = {
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
}
_TARGET_KEYS = {
    "jurisdiction",
    "tax_period",
    "form",
    "knd",
    "order",
    "electronic_format_version",
    "xsd",
}
_SCOPE_KEYS = {"domain", "taxpayer_profile", "operation_profile", "boundary"}
_REQUIREMENT_KEYS = {
    "requirement_id",
    "official_requirement",
    "evidence_refs",
    "semantic_output",
    "declared_inputs",
    "capability_refs",
    "artifact_refs",
    "preconditions",
    "completion_criteria",
    "status",
    "gap_refs",
}
_SEMANTIC_OUTPUT_KEYS = {"semantic_id", "contract", "contract_status"}
_DECLARED_INPUT_KEYS = {"input_name", "contract", "required", "source"}
_ARTIFACT_REF_KEYS = {
    "artifact_kind",
    "artifact_id",
    "artifact_version",
    "role",
}
_GAP_KEYS = {
    "gap_id",
    "requirement_id",
    "gap_type",
    "required_semantic",
    "runtime_user_pain",
    "related_capability_refs",
    "missing_artifact_kind",
    "evidence_refs",
}
_FINDINGS_KEYS = {
    "supported_fragment_requirement_ids",
    "first_runtime_composition_gap_id",
    "first_downstream_declaration_gap_id",
}
_AUTHORING_KEYS = {
    "phase",
    "model_role",
    "case_time_research_assumed",
    "prompt_bias_check",
    "trial_independence",
}
_INVENTORY_KEYS = {
    "schema_version",
    "inventory_id",
    "inventory_version",
    "artifacts",
    "published_reference_artifacts",
}
_INVENTORY_ARTIFACT_KEYS = {
    "artifact_ref",
    "behavior_id",
    "semantic_output_contract",
    "capability_uses",
}
_INVENTORY_ARTIFACT_REF_KEYS = {
    "artifact_kind",
    "artifact_id",
    "artifact_version",
}
_CAPABILITY_USE_KEYS = {"capability_id", "role"}
_OFFICIAL_EVIDENCE_KEYS = {
    "schema_version",
    "verified_on",
    "declaration",
    "sources",
    "requirements",
}
_SOURCE_KEYS = {
    "source_ref",
    "authority_kind",
    "url",
    "content_sha256",
}
_EVIDENCE_REQUIREMENT_KEYS = {
    "evidence_ref",
    "source_refs",
    "locator",
    "claim",
}
_FORBIDDEN_CANDIDATE_KEYS = {
    "action",
    "actions",
    "step",
    "steps",
    "expression",
    "formula",
    "script",
    "command",
    "tool",
    "tools",
    "code",
}
_DEFINITION_STATUSES = {"compilable", "partially_compilable", "not_compilable"}
_REQUIREMENT_STATUSES = {"compilable", "not_compilable", "evidence_missing"}
_GAP_TYPES = {
    "missing_runtime_capability",
    "missing_published_behavior",
    "missing_input_type",
    "missing_artifact",
    "missing_evidence",
}
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_PROMPT_BIAS_TERMS = (
    "section 2",
    "раздел 2",
    "line 060",
    "строк 060",
    "group tax base",
    "group-level tax base",
)
_MODEL_PAYLOAD_SECTION_NAMES = (
    "system_instructions",
    "research_policy",
    "runtime_capabilities",
    "published_artifact_inventory",
    "official_evidence",
    "output_schema",
)
_KNOWN_METHODOLOGY_OUTPUTS = {
    "security_disposal_net_result_v0": GATE5_TRUSTED_CALCULATION_RESULT_SCHEMA_VERSION,
    "securities_disposal_tax_model_v0": (
        GATE5_SECURITIES_DISPOSAL_TAX_MODEL_SCHEMA_VERSION
    ),
    "securities_disposal_operation_tax_model_v0": (
        GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION
    ),
}


class Gate5DeclarationDefinitionError(ValueError):
    def __init__(self, code: str, field: str = "") -> None:
        self.code = code
        self.field = field
        super().__init__(code if not field else f"{code}:{field}")


@dataclass(frozen=True)
class _PublishedArtifact:
    key: tuple[str, str, str]
    capability_uses: frozenset[tuple[str, str]]


class Gate5DeclarationDefinitionAuthoringFactory:
    @staticmethod
    def create() -> "Gate5DeclarationDefinitionAuthoring":
        context = _read_hash_pinned_resource(
            GATE5_DECLARATION_DEFINITION_CONTEXT_RESOURCE,
            GATE5_DECLARATION_DEFINITION_CONTEXT_RESOURCE_SHA256,
            "gate5_declaration_definition_context",
        )
        capability_contract = Gate5RuntimeCapabilityContractFactory.create()
        capability_snapshot = capability_contract.snapshot()
        capability_index = {
            item["capability_id"]: item for item in capability_snapshot["capabilities"]
        }
        _validate_context(context)
        artifact_index = _validate_artifact_inventory(
            context["published_artifact_inventory"], capability_index
        )
        evidence_refs = _validate_official_evidence(context["official_evidence"])
        return Gate5DeclarationDefinitionAuthoring(
            context=copy.deepcopy(context),
            capability_contract=capability_contract,
            capability_index=capability_index,
            artifact_index=artifact_index,
            evidence_refs=evidence_refs,
        )


class Gate5DeclarationDefinitionAuthoring:
    def __init__(
        self,
        *,
        context: dict[str, Any],
        capability_contract: Any,
        capability_index: dict[str, dict[str, Any]],
        artifact_index: dict[tuple[str, str, str], _PublishedArtifact],
        evidence_refs: frozenset[str],
    ) -> None:
        self._context = context
        self._capability_contract = capability_contract
        self._capability_index = capability_index
        self._artifact_index = artifact_index
        self._evidence_refs = evidence_refs

    def model_payload(self) -> dict[str, Any]:
        return {
            "system_instructions": copy.deepcopy(self._context["system_instructions"]),
            "research_policy": copy.deepcopy(self._context["research_policy"]),
            "runtime_capabilities": self._capability_contract.model_projection(),
            "published_artifact_inventory": copy.deepcopy(
                self._context["published_artifact_inventory"]
            ),
            "official_evidence": copy.deepcopy(self._context["official_evidence"]),
            "output_schema": copy.deepcopy(self._context["output_schema"]),
        }

    def model_payload_bytes(self) -> bytes:
        return _canonical_json(self.model_payload())

    def section_metrics(self) -> dict[str, Any]:
        payload = self.model_payload()
        sections = []
        for name in _MODEL_PAYLOAD_SECTION_NAMES:
            raw = _canonical_json(payload[name])
            sections.append(
                {
                    "section": name,
                    "utf8_bytes": len(raw),
                    "unicode_lexical_tokens": len(
                        re.findall(r"\w+|[^\w\s]", raw.decode("utf-8"))
                    ),
                }
            )
        return {
            "token_metric": "unicode_lexical_tokens_v0_not_model_tokenizer",
            "sections": sections,
            "enveloped_payload_utf8_bytes": len(self.model_payload_bytes()),
        }

    def candidate(self) -> dict[str, Any]:
        candidate = _read_hash_pinned_resource(
            GATE5_DECLARATION_DEFINITION_CANDIDATE_RESOURCE,
            GATE5_DECLARATION_DEFINITION_CANDIDATE_RESOURCE_SHA256,
            "gate5_declaration_definition_candidate",
        )
        self.validate_candidate(candidate)
        return copy.deepcopy(candidate)

    def validate_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        return _validate_candidate(
            candidate=copy.deepcopy(candidate),
            target=self._context["official_evidence"]["declaration"],
            capability_index=self._capability_index,
            artifact_index=self._artifact_index,
            evidence_refs=self._evidence_refs,
        )


def _validate_context(context: Any) -> None:
    _keys(context, _CONTEXT_KEYS, "gate5_declaration_definition_context_invalid")
    if (
        context["schema_version"] != GATE5_DECLARATION_DEFINITION_CONTEXT_SCHEMA_VERSION
        or not _identifier(context["context_id"])
        or not _clean(context["context_version"])
        or context["status"] != "inactive_proof"
    ):
        _fail("gate5_declaration_definition_context_invalid")

    system = context["system_instructions"]
    _keys(system, {"task", "rules"}, "gate5_declaration_definition_context_invalid")
    research = context["research_policy"]
    _keys(
        research,
        {
            "authority_order",
            "allowed_authoring_tools",
            "case_time_tools",
            "evidence_rules",
        },
        "gate5_declaration_definition_context_invalid",
    )
    if research["case_time_tools"] != []:
        _fail("gate5_declaration_definition_case_time_research_forbidden")
    prompt_text = json.dumps(
        {"system_instructions": system, "research_policy": research},
        ensure_ascii=False,
    ).lower()
    if any(term in prompt_text for term in _PROMPT_BIAS_TERMS):
        _fail("gate5_declaration_definition_prompt_bias_detected")

    schema = context["output_schema"]
    _keys(
        schema,
        {
            "schema_version",
            "closed",
            "root_fields",
            "requirement_fields",
            "gap_fields",
            "allowed_definition_statuses",
            "allowed_requirement_statuses",
            "allowed_gap_types",
            "composition_rule",
        },
        "gate5_declaration_definition_output_schema_invalid",
    )
    if (
        schema["schema_version"]
        != "broker_reports_gate5_declaration_definition_output_schema_v0"
        or schema["closed"] is not True
        or set(schema["root_fields"]) != _DEFINITION_KEYS
        or set(schema["requirement_fields"]) != _REQUIREMENT_KEYS
        or set(schema["gap_fields"]) != _GAP_KEYS
        or set(schema["allowed_definition_statuses"]) != _DEFINITION_STATUSES
        or set(schema["allowed_requirement_statuses"]) != _REQUIREMENT_STATUSES
        or set(schema["allowed_gap_types"]) != _GAP_TYPES
    ):
        _fail("gate5_declaration_definition_output_schema_invalid")


def _validate_artifact_inventory(
    inventory: Any,
    capability_index: dict[str, dict[str, Any]],
) -> dict[tuple[str, str, str], _PublishedArtifact]:
    _keys(inventory, _INVENTORY_KEYS, "gate5_declaration_definition_inventory_invalid")
    if (
        inventory["schema_version"]
        != "broker_reports_gate5_published_artifact_inventory_v0"
        or not _identifier(inventory["inventory_id"])
        or not _clean(inventory["inventory_version"])
        or inventory["published_reference_artifacts"] != []
        or not isinstance(inventory["artifacts"], list)
        or not inventory["artifacts"]
    ):
        _fail("gate5_declaration_definition_inventory_invalid")

    authority = Gate5TrustedMethodologyAuthorityFactory.create()
    index: dict[tuple[str, str, str], _PublishedArtifact] = {}
    for position, artifact in enumerate(inventory["artifacts"]):
        field = f"published_artifact_inventory.artifacts[{position}]"
        _keys(
            artifact,
            _INVENTORY_ARTIFACT_KEYS,
            "gate5_declaration_definition_inventory_invalid",
            field,
        )
        ref = artifact["artifact_ref"]
        _keys(
            ref,
            _INVENTORY_ARTIFACT_REF_KEYS,
            "gate5_declaration_definition_inventory_invalid",
            field,
        )
        key = (ref["artifact_kind"], ref["artifact_id"], ref["artifact_version"])
        if (
            not _identifier(key[0])
            or not _identifier(key[1])
            or not _clean(key[2])
            or key in index
            or not _identifier(artifact["semantic_output_contract"])
        ):
            _fail("gate5_declaration_definition_inventory_invalid", field)

        uses: set[tuple[str, str]] = set()
        if not isinstance(artifact["capability_uses"], list):
            _fail("gate5_declaration_definition_inventory_invalid", field)
        for use in artifact["capability_uses"]:
            _keys(
                use,
                _CAPABILITY_USE_KEYS,
                "gate5_declaration_definition_inventory_invalid",
                field,
            )
            pair = (use["capability_id"], use["role"])
            if (
                pair[0] not in capability_index
                or not _identifier(pair[1])
                or pair in uses
            ):
                _fail("gate5_declaration_definition_inventory_invalid", field)
            uses.add(pair)

        if key[0] == "trusted_methodology":
            resolved = authority.resolve(
                {
                    "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
                    "methodology_id": key[1],
                    "methodology_version": key[2],
                }
            )
            methodology = resolved["methodology"]
            behavior = methodology.get("calculation") or methodology.get("behavior")
            if not isinstance(behavior, dict):
                _fail("gate5_declaration_definition_inventory_drift", field)
            behavior_id = behavior.get("behavior_id")
            if (
                artifact["behavior_id"] != behavior_id
                or _KNOWN_METHODOLOGY_OUTPUTS.get(behavior_id)
                != artifact["semantic_output_contract"]
            ):
                _fail("gate5_declaration_definition_inventory_drift", field)
        elif key[0] == "validated_declaration_projection":
            if artifact["behavior_id"] is not None:
                _fail("gate5_declaration_definition_inventory_invalid", field)
            Gate5DeclarationProjectionRuntimeFactory.create()
            spec = _read_unpinned_resource(GATE5_DECLARATION_PROJECTION_SPEC_RESOURCE)
            if (
                spec.get("spec_id") != key[1]
                or spec.get("spec_version") != key[2]
                or artifact["semantic_output_contract"]
                != GATE5_DECLARATION_PROJECTION_FRAGMENT_SCHEMA_VERSION
            ):
                _fail("gate5_declaration_definition_inventory_drift", field)
        else:
            _fail("gate5_declaration_definition_inventory_invalid", field)

        index[key] = _PublishedArtifact(key=key, capability_uses=frozenset(uses))
    return index


def _validate_official_evidence(evidence: Any) -> frozenset[str]:
    _keys(
        evidence,
        _OFFICIAL_EVIDENCE_KEYS,
        "gate5_declaration_definition_evidence_invalid",
    )
    _keys(
        evidence["declaration"],
        _TARGET_KEYS,
        "gate5_declaration_definition_evidence_invalid",
    )
    if (
        evidence["schema_version"]
        != "broker_reports_gate5_declaration_authoring_evidence_v0"
        or evidence["verified_on"] != "2026-08-10"
    ):
        _fail("gate5_declaration_definition_evidence_invalid")

    source_refs: set[str] = set()
    for source in evidence["sources"]:
        _keys(source, _SOURCE_KEYS, "gate5_declaration_definition_evidence_invalid")
        source_ref = source["source_ref"]
        digest = source["content_sha256"]
        if (
            not _identifier(source_ref)
            or source_ref in source_refs
            or not _clean(source["authority_kind"])
            or not isinstance(source["url"], str)
            or not source["url"].startswith("https://")
            or (
                digest is not None
                and (not isinstance(digest, str) or _SHA256.fullmatch(digest) is None)
            )
        ):
            _fail("gate5_declaration_definition_evidence_invalid")
        source_refs.add(source_ref)

    evidence_refs: set[str] = set()
    for item in evidence["requirements"]:
        _keys(
            item,
            _EVIDENCE_REQUIREMENT_KEYS,
            "gate5_declaration_definition_evidence_invalid",
        )
        ref = item["evidence_ref"]
        if (
            not _identifier(ref)
            or ref in evidence_refs
            or not _string_list(item["source_refs"])
            or not set(item["source_refs"]).issubset(source_refs)
            or not _clean(item["locator"])
            or not _clean(item["claim"])
        ):
            _fail("gate5_declaration_definition_evidence_invalid")
        evidence_refs.add(ref)
    return frozenset(evidence_refs)


def _validate_candidate(
    *,
    candidate: Any,
    target: dict[str, Any],
    capability_index: dict[str, dict[str, Any]],
    artifact_index: dict[tuple[str, str, str], _PublishedArtifact],
    evidence_refs: frozenset[str],
) -> dict[str, Any]:
    _reject_forbidden_candidate_keys(candidate)
    _keys(candidate, _DEFINITION_KEYS, "gate5_declaration_definition_candidate_invalid")
    if (
        candidate["schema_version"] != GATE5_DECLARATION_DEFINITION_SCHEMA_VERSION
        or not _identifier(candidate["definition_id"])
        or not _clean(candidate["definition_version"])
        or candidate["status"] not in _DEFINITION_STATUSES
    ):
        _fail("gate5_declaration_definition_candidate_invalid")
    _keys(
        candidate["target"],
        _TARGET_KEYS,
        "gate5_declaration_definition_candidate_invalid",
    )
    if candidate["target"] != target:
        _fail("gate5_declaration_definition_target_evidence_mismatch")
    _keys(
        candidate["scope"],
        _SCOPE_KEYS,
        "gate5_declaration_definition_candidate_invalid",
    )
    if any(not _identifier(value) for value in candidate["scope"].values()):
        _fail("gate5_declaration_definition_candidate_invalid")

    requirements = candidate["requirements"]
    if not isinstance(requirements, list) or not requirements:
        _fail("gate5_declaration_definition_candidate_invalid")
    requirement_index: dict[str, dict[str, Any]] = {}
    compilation_rows: list[dict[str, Any]] = []
    for position, requirement in enumerate(requirements):
        field = f"requirements[{position}]"
        _keys(
            requirement,
            _REQUIREMENT_KEYS,
            "gate5_declaration_definition_candidate_invalid",
            field,
        )
        requirement_id = requirement["requirement_id"]
        if not _identifier(requirement_id) or requirement_id in requirement_index:
            _fail("gate5_declaration_definition_candidate_invalid", field)
        requirement_index[requirement_id] = requirement
        _validate_requirement(
            requirement=requirement,
            field=field,
            capability_index=capability_index,
            artifact_index=artifact_index,
            evidence_refs=evidence_refs,
        )
        compilation_rows.append(_compilation_row(requirement))

    gaps = candidate["gaps"]
    if not isinstance(gaps, list):
        _fail("gate5_declaration_definition_candidate_invalid")
    gap_index: dict[str, dict[str, Any]] = {}
    for position, gap in enumerate(gaps):
        field = f"gaps[{position}]"
        _keys(gap, _GAP_KEYS, "gate5_declaration_definition_candidate_invalid", field)
        gap_id = gap["gap_id"]
        if not _identifier(gap_id) or gap_id in gap_index:
            _fail("gate5_declaration_definition_gap_invalid", field)
        _validate_gap(
            gap=gap,
            field=field,
            requirement_index=requirement_index,
            capability_index=capability_index,
            evidence_refs=evidence_refs,
        )
        gap_index[gap_id] = gap

    for requirement in requirements:
        linked = requirement["gap_refs"]
        if any(ref not in gap_index for ref in linked):
            _fail("gate5_declaration_definition_gap_unknown")
        if any(
            gap_index[ref]["requirement_id"] != requirement["requirement_id"]
            for ref in linked
        ):
            _fail("gate5_declaration_definition_gap_requirement_mismatch")
        if requirement["status"] == "compilable" and linked:
            _fail("gate5_declaration_definition_gap_status_inconsistent")
        if requirement["status"] != "compilable" and not linked:
            _fail("gate5_declaration_definition_gap_status_inconsistent")
    linked_gap_refs = {
        ref for requirement in requirements for ref in requirement["gap_refs"]
    }
    if linked_gap_refs != set(gap_index):
        _fail("gate5_declaration_definition_gap_status_inconsistent")

    statuses = {item["status"] for item in requirements}
    expected_status = (
        "partially_compilable"
        if "compilable" in statuses and statuses - {"compilable"}
        else "compilable"
        if statuses == {"compilable"}
        else "not_compilable"
    )
    if candidate["status"] != expected_status:
        _fail("gate5_declaration_definition_status_inconsistent")

    _validate_findings(candidate["findings"], requirement_index, gap_index)
    _keys(
        candidate["authoring"],
        _AUTHORING_KEYS,
        "gate5_declaration_definition_candidate_invalid",
    )
    authoring = candidate["authoring"]
    if (
        authoring["phase"] != "authoring_time"
        or authoring["model_role"] != "llm_research_synthesis"
        or authoring["case_time_research_assumed"] is not False
        or authoring["prompt_bias_check"]
        != "expected_gap_not_named_in_system_instructions_or_research_policy"
        or authoring["trial_independence"]
        != "structural_prompt_only_not_blind_to_governance_goal"
    ):
        _fail("gate5_declaration_definition_authoring_claim_invalid")

    return {
        "schema_version": GATE5_DECLARATION_DEFINITION_VALIDATION_SCHEMA_VERSION,
        "status": "validated",
        "definition_id": candidate["definition_id"],
        "definition_status": candidate["status"],
        "compilation_report": compilation_rows,
        "gap_count": len(gaps),
        "independence_claim": authoring["trial_independence"],
    }


def _validate_requirement(
    *,
    requirement: dict[str, Any],
    field: str,
    capability_index: dict[str, dict[str, Any]],
    artifact_index: dict[tuple[str, str, str], _PublishedArtifact],
    evidence_refs: frozenset[str],
) -> None:
    if (
        not _clean(requirement["official_requirement"])
        or not _string_list(requirement["evidence_refs"])
        or not set(requirement["evidence_refs"]).issubset(evidence_refs)
        or requirement["status"] not in _REQUIREMENT_STATUSES
        or not _string_list(requirement["preconditions"])
        or not _string_list(requirement["completion_criteria"])
        or not isinstance(requirement["gap_refs"], list)
        or len(requirement["gap_refs"]) != len(set(requirement["gap_refs"]))
        or any(not _identifier(item) for item in requirement["gap_refs"])
    ):
        _fail("gate5_declaration_definition_requirement_invalid", field)

    semantic = requirement["semantic_output"]
    _keys(
        semantic,
        _SEMANTIC_OUTPUT_KEYS,
        "gate5_declaration_definition_requirement_invalid",
        field,
    )
    if (
        not _identifier(semantic["semantic_id"])
        or semantic["contract_status"]
        not in {"published", "published_input_only", "missing"}
        or (
            semantic["contract_status"] == "missing"
            and semantic["contract"] is not None
        )
        or (
            semantic["contract_status"] != "missing"
            and not _identifier(semantic["contract"])
        )
    ):
        _fail("gate5_declaration_definition_requirement_invalid", field)

    declared_inputs: dict[str, dict[str, Any]] = {}
    if not isinstance(requirement["declared_inputs"], list):
        _fail("gate5_declaration_definition_requirement_invalid", field)
    for item in requirement["declared_inputs"]:
        _keys(
            item,
            _DECLARED_INPUT_KEYS,
            "gate5_declaration_definition_requirement_invalid",
            field,
        )
        if (
            not _identifier(item["input_name"])
            or item["input_name"] in declared_inputs
            or not _identifier(item["contract"])
            or not isinstance(item["required"], bool)
            or item["source"] != "definition_boundary"
        ):
            _fail("gate5_declaration_definition_requirement_invalid", field)
        declared_inputs[item["input_name"]] = item

    capabilities = requirement["capability_refs"]
    if not isinstance(capabilities, list):
        _fail("gate5_declaration_definition_capability_invalid", field)
    capability_ids = [
        _validated_capability_ref(ref, capability_index, field) for ref in capabilities
    ]
    if len(capability_ids) != len(set(capability_ids)):
        _fail("gate5_declaration_definition_capability_invalid", field)

    artifact_refs = requirement["artifact_refs"]
    if not isinstance(artifact_refs, list):
        _fail("gate5_declaration_definition_artifact_invalid", field)
    seen_artifact_uses: set[tuple[tuple[str, str, str], str]] = set()
    for item in artifact_refs:
        _keys(
            item,
            _ARTIFACT_REF_KEYS,
            "gate5_declaration_definition_artifact_invalid",
            field,
        )
        key = (item["artifact_kind"], item["artifact_id"], item["artifact_version"])
        use = (key, item["role"])
        published = artifact_index.get(key)
        if (
            published is None
            or not _identifier(item["role"])
            or use in seen_artifact_uses
        ):
            _fail("gate5_declaration_definition_artifact_unresolvable", field)
        if not any(
            (capability_id, item["role"]) in published.capability_uses
            for capability_id in capability_ids
        ):
            _fail("gate5_declaration_definition_artifact_incompatible", field)
        seen_artifact_uses.add(use)

    if requirement["status"] == "compilable":
        if len(capability_ids) != 1 or semantic["contract_status"] != "published":
            _fail("gate5_declaration_definition_compilation_invalid", field)
        capability = capability_index[capability_ids[0]]
        if capability["output"]["contract"] != semantic["contract"]:
            _fail("gate5_declaration_definition_output_incompatible", field)
        contract_inputs = {item["name"]: item for item in capability["inputs"]}
        if set(declared_inputs) - set(contract_inputs):
            _fail("gate5_declaration_definition_input_incompatible", field)
        for name, item in declared_inputs.items():
            if contract_inputs[name]["contract"] != item["contract"]:
                _fail("gate5_declaration_definition_input_incompatible", field)
        if any(
            item["required"] and name not in declared_inputs
            for name, item in contract_inputs.items()
        ):
            _fail("gate5_declaration_definition_input_incompatible", field)
        if requirement["gap_refs"]:
            _fail("gate5_declaration_definition_gap_status_inconsistent", field)
    elif capability_ids:
        _fail("gate5_declaration_definition_uncompiled_plan_forbidden", field)


def _validate_gap(
    *,
    gap: dict[str, Any],
    field: str,
    requirement_index: dict[str, dict[str, Any]],
    capability_index: dict[str, dict[str, Any]],
    evidence_refs: frozenset[str],
) -> None:
    if (
        gap["requirement_id"] not in requirement_index
        or gap["gap_type"] not in _GAP_TYPES
        or not _clean(gap["required_semantic"])
        or not _clean(gap["runtime_user_pain"])
        or not isinstance(gap["related_capability_refs"], list)
        or not isinstance(gap["evidence_refs"], list)
        or not set(gap["evidence_refs"]).issubset(evidence_refs)
    ):
        _fail("gate5_declaration_definition_gap_invalid", field)
    related = [
        _validated_capability_ref(ref, capability_index, field)
        for ref in gap["related_capability_refs"]
    ]
    if len(related) != len(set(related)):
        _fail("gate5_declaration_definition_gap_invalid", field)
    kind = gap["gap_type"]
    artifact_kind = gap["missing_artifact_kind"]
    if kind == "missing_runtime_capability" and (related or artifact_kind is not None):
        _fail("gate5_declaration_definition_gap_type_inconsistent", field)
    if kind == "missing_published_behavior" and (
        "execute_published_calculation_behavior_v0" not in related
        or artifact_kind != "methodology_behavior"
    ):
        _fail("gate5_declaration_definition_gap_type_inconsistent", field)
    if kind == "missing_input_type" and (
        "obtain_one_missing_money_input_v0" not in related or artifact_kind is not None
    ):
        _fail("gate5_declaration_definition_gap_type_inconsistent", field)
    if kind == "missing_artifact" and (
        not related or artifact_kind not in {"reference", "methodology", "projection"}
    ):
        _fail("gate5_declaration_definition_gap_type_inconsistent", field)
    if kind == "missing_evidence" and artifact_kind is not None:
        _fail("gate5_declaration_definition_gap_type_inconsistent", field)


def _validate_findings(
    findings: Any,
    requirement_index: dict[str, dict[str, Any]],
    gap_index: dict[str, dict[str, Any]],
) -> None:
    _keys(findings, _FINDINGS_KEYS, "gate5_declaration_definition_findings_invalid")
    supported = findings["supported_fragment_requirement_ids"]
    if (
        not _string_list(supported)
        or any(
            ref not in requirement_index
            or requirement_index[ref]["status"] != "compilable"
            for ref in supported
        )
        or findings["first_runtime_composition_gap_id"] not in gap_index
        or findings["first_downstream_declaration_gap_id"] not in gap_index
        or gap_index[findings["first_runtime_composition_gap_id"]]["gap_type"]
        != "missing_runtime_capability"
    ):
        _fail("gate5_declaration_definition_findings_invalid")


def _validated_capability_ref(
    ref: Any,
    capability_index: dict[str, dict[str, Any]],
    field: str,
) -> str:
    if (
        not isinstance(ref, dict)
        or set(ref) != {"schema_version", "capability_id"}
        or ref.get("schema_version") != GATE5_RUNTIME_CAPABILITY_REF_SCHEMA_VERSION
        or not _identifier(ref.get("capability_id"))
    ):
        _fail("gate5_declaration_definition_capability_invalid", field)
    capability_id = ref["capability_id"]
    capability = capability_index.get(capability_id)
    if capability is None:
        try:
            Gate5RuntimeCapabilityResolverFactory.create().resolve(ref)
        except ValueError as exc:
            raise Gate5DeclarationDefinitionError(
                "gate5_declaration_definition_capability_unsupported", field
            ) from exc
        _fail("gate5_declaration_definition_capability_unsupported", field)
    if (
        capability["implementation_status"] != "proven"
        or capability["execution_phase"] != "case_time"
    ):
        _fail("gate5_declaration_definition_capability_unproven", field)
    Gate5RuntimeCapabilityResolverFactory.create().resolve(ref)
    return capability_id


def _compilation_row(requirement: dict[str, Any]) -> dict[str, Any]:
    gaps = requirement["gap_refs"]
    status = "COMPILABLE" if requirement["status"] == "compilable" else "NOT_COMPILABLE"
    return {
        "requirement_id": requirement["requirement_id"],
        "needed_semantic_output": requirement["semantic_output"]["semantic_id"],
        "capability_ids": [
            ref["capability_id"] for ref in requirement["capability_refs"]
        ],
        "artifact_ids": [ref["artifact_id"] for ref in requirement["artifact_refs"]],
        "status": status,
        "gap_refs": copy.deepcopy(gaps),
    }


def _read_hash_pinned_resource(
    resource_name: str, expected_hash: str, prefix: str
) -> dict[str, Any]:
    raw = _read_resource_bytes(resource_name, prefix)
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        _fail(f"{prefix}_hash_mismatch")
    return _decode_json(raw, prefix)


def _read_unpinned_resource(resource_name: str) -> dict[str, Any]:
    return _decode_json(
        _read_resource_bytes(resource_name, "gate5_declaration_definition_artifact"),
        "gate5_declaration_definition_artifact",
    )


def _read_resource_bytes(resource_name: str, prefix: str) -> bytes:
    try:
        return resources.files(__package__).joinpath(resource_name).read_bytes()
    except (FileNotFoundError, OSError) as exc:
        raise Gate5DeclarationDefinitionError(f"{prefix}_unavailable") from exc


def _decode_json(raw: bytes, prefix: str) -> dict[str, Any]:
    try:
        value: Any = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Gate5DeclarationDefinitionError(f"{prefix}_json_invalid") from exc
    if not isinstance(value, dict):
        _fail(f"{prefix}_json_invalid")
    return value


def _reject_forbidden_candidate_keys(value: Any) -> None:
    if isinstance(value, dict):
        if set(value) & _FORBIDDEN_CANDIDATE_KEYS:
            _fail("gate5_declaration_definition_free_form_execution_forbidden")
        for item in value.values():
            _reject_forbidden_candidate_keys(item)
    elif isinstance(value, list):
        for item in value:
            _reject_forbidden_candidate_keys(item)


def _keys(value: Any, expected: set[str], code: str, field: str = "") -> None:
    if not isinstance(value, dict) or set(value) != expected:
        _fail(code, field)


def _string_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and len(value) == len(set(value))
        and all(_clean(item) for item in value)
    )


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _clean(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and value == value.strip()


def _canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise Gate5DeclarationDefinitionError(
            "gate5_declaration_definition_not_canonical"
        ) from exc


def _fail(code: str, field: str = "") -> None:
    raise Gate5DeclarationDefinitionError(code, field)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_DECLARATION_DEFINITION_CANDIDATE_RESOURCE",
    "GATE5_DECLARATION_DEFINITION_CANDIDATE_RESOURCE_SHA256",
    "GATE5_DECLARATION_DEFINITION_CONTEXT_RESOURCE",
    "GATE5_DECLARATION_DEFINITION_CONTEXT_RESOURCE_SHA256",
    "GATE5_DECLARATION_DEFINITION_CONTEXT_SCHEMA_VERSION",
    "GATE5_DECLARATION_DEFINITION_SCHEMA_VERSION",
    "GATE5_DECLARATION_DEFINITION_VALIDATION_SCHEMA_VERSION",
    "Gate5DeclarationDefinitionAuthoring",
    "Gate5DeclarationDefinitionAuthoringFactory",
    "Gate5DeclarationDefinitionError",
]
