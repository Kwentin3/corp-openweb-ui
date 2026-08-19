"""One bounded LLM adapter for the frozen minimal metadata contract."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace
from datetime import datetime
import hashlib
import json
import re
from typing import Any

from .artifact_models import ArtifactAccessContext
from .artifact_resolver import ArtifactResolver
from .canonical_artifact import validate_canonical_artifact
from .canonical_store import CanonicalReaderFactory
from .gate3_metadata_source_facts import (
    GATE3_METADATA_SOURCE_FACT_COLLECTION_SCHEMA_VERSION,
    GATE3_METADATA_SOURCE_FACT_SCHEMA_VERSION,
    GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
    GATE3_MINIMAL_METADATA_FACT_TYPES,
)


GATE3_LLM_METADATA_INSTRUCTION_ID = (
    "broker-reports-minimal-person-document-metadata-adapter"
)
GATE3_LLM_METADATA_INSTRUCTION_VERSION = "1.2.0"
GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION = "broker_reports_metadata_context_policy_v4"
GATE3_LLM_METADATA_PROPOSAL_SCHEMA_VERSION = "broker_reports_llm_metadata_proposal_v2"
GATE3_LLM_METADATA_CONTEXT_SCHEMA_VERSION = "broker_reports_llm_metadata_context_v2"
GATE3_LLM_METADATA_BINDING_REGISTRY_SCHEMA_VERSION = (
    "broker_reports_llm_metadata_binding_registry_v2"
)
GATE3_LLM_METADATA_VALIDATED_TERMINAL = "LLM_METADATA_PROPOSAL_CANONICAL_VALIDATED"

GATE3_LLM_METADATA_INSTRUCTION = """You are the single Broker Reports Minimal Person and Document Metadata adapter for contract 1.0.0.

You receive opaque Canonical region aliases with source text or small table rows. Extract only explicit source assertions for the 11 allowed fact types. Every proposed fact requires positive source evidence for both its value and its semantic role. If the source does not explicitly assign the requested role to the value or value-bearing structure, omit the fact. Value shape or repetition alone is never role evidence.

PARTY_NAME requires an explicit assertion that the natural person is the current report or account subject. PERSON_BIRTH_DATE, TAXPAYER_TAX_IDENTIFIER and PERSON_CITIZENSHIP each require an explicit source assertion assigning that role to the person. DOCUMENT_TYPE, DOCUMENT_NUMBER, DOCUMENT_DATE and STATEMENT_PERIOD each require an explicit assertion about the current report; a statement period requires both source boundaries. BROKER_LEGAL_NAME requires an explicit assertion that the legal entity acts as broker or issuer of the current report. ACCOUNT_IDENTIFIER requires an explicit assertion that the designation is a broker or investment account. ACCOUNT_CONTRACT_IDENTIFIER requires an explicit assertion that the designation is the current account's contract or agreement.

For each fact, copy only the exact source-authored value into source_literal, excluding its role label, delimiter and surrounding description. Select exactly one source_target_alias containing that value and exactly one role_evidence_target_alias containing the source assertion of the role. The two aliases may be the same when one region states both role and value, or different when structural context such as a table header states the role. For STATEMENT_PERIOD also copy the exact start and end boundary literals. Preserve every independent account identifier and statement period. Do not infer, complete, translate, repair, reconcile or add unsupported metadata. If positive role evidence is absent or ambiguous, omit the fact; an empty facts array is valid.

Return only broker_reports_llm_metadata_proposal_v2 under the strict response schema."""

SMALL_TABLE_NONEMPTY_CELLS_MAX = 64
PROPOSAL_FACTS_MAX = 32

FACTORY_REQUIRED = (
    "Gate3LlmMetadataAdapterFactory.create consumes ArtifactResolver.catalog_case, "
    "CanonicalReaderFactory.create and the configured Gate 2 factory client"
)
FORBIDDEN = (
    "source-file reads, broker or layout branches, semantic context selection, "
    "human-language regex or synonym vocabulary, retry, best-of-N, output "
    "repair, tax meaning, persistence, Gate 4 reads or G5.60 owner mutation"
)

_ALIAS = re.compile(r"^m[0-9]{3,}$")
_CATEGORY_BY_FACT_TYPE = {
    "PARTY_NAME": "PERSON_IDENTITY",
    "PERSON_BIRTH_DATE": "PERSON_IDENTITY",
    "TAXPAYER_TAX_IDENTIFIER": "PERSON_IDENTITY",
    "PERSON_CITIZENSHIP": "PERSON_IDENTITY",
    "DOCUMENT_TYPE": "DOCUMENT_IDENTITY",
    "DOCUMENT_NUMBER": "DOCUMENT_IDENTITY",
    "DOCUMENT_DATE": "DOCUMENT_IDENTITY",
    "STATEMENT_PERIOD": "DOCUMENT_IDENTITY",
    "BROKER_LEGAL_NAME": "ISSUER_IDENTITY",
    "ACCOUNT_IDENTIFIER": "ACCOUNT_IDENTITY",
    "ACCOUNT_CONTRACT_IDENTIFIER": "ACCOUNT_IDENTITY",
}


class Gate3LlmMetadataAdapterError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _DuplicateJsonKeyError(ValueError):
    pass


@dataclass(frozen=True)
class Gate3LlmMetadataAttempt:
    context_package: dict[str, Any] = field(repr=False)
    binding_registry: dict[str, Any] = field(repr=False)
    model_visible_request: dict[str, Any] = field(repr=False)
    final_provider_request: dict[str, Any] = field(repr=False)
    raw_provider_response: dict[str, Any] = field(repr=False)
    raw_model_output: Any = field(repr=False)
    validated_output: dict[str, Any] | None = field(repr=False)
    validation_status: str
    validation_error_code: str | None
    execution_metadata: Any
    metrics: dict[str, Any]


class Gate3LlmMetadataAdapterFactory:
    """Read one unambiguous Canonical artifact and make one LLM proposal."""

    def __init__(
        self,
        *,
        store: Any,
        read_enabled: bool,
        model_client: Any,
        model_id: str,
    ) -> None:
        self._resolver = ArtifactResolver(store)
        self._reader = CanonicalReaderFactory(
            store=store,
            read_enabled=read_enabled,
        ).create()
        self._model_client = model_client
        self._model_id = model_id

    async def create(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
    ) -> Gate3LlmMetadataAttempt:
        if not isinstance(document_id, str) or not document_id:
            raise Gate3LlmMetadataAdapterError(
                "gate3_llm_metadata_document_id_required"
            )
        if not isinstance(self._model_id, str) or not self._model_id:
            raise Gate3LlmMetadataAdapterError("gate3_llm_metadata_model_id_required")
        records = [
            record
            for record in self._resolver.catalog_case(context)
            if record.artifact_type == "broker_reports_canonical_artifact_v1"
            and record.document_id == document_id
        ]
        if len(records) != 1:
            raise Gate3LlmMetadataAdapterError(
                "gate3_llm_metadata_canonical_record_ambiguous"
            )
        record = records[0]
        artifact = self._reader.read(
            record.artifact_id,
            replace(
                context,
                normalization_run_id=record.normalization_run_id,
            ),
        )
        canonical_version_id = str(artifact.get("artifact_id") or "")
        if (
            not canonical_version_id
            or not validate_canonical_artifact(artifact)["passed"]
        ):
            raise Gate3LlmMetadataAdapterError("gate3_llm_metadata_canonical_invalid")
        context_package, binding_registry = build_metadata_context_package(
            artifact=artifact,
            document_id=document_id,
            canonical_version_id=canonical_version_id,
        )
        response_schema = metadata_proposal_response_schema()
        model_visible_request = compose_metadata_model_visible_request(
            context_package=context_package,
            response_schema=response_schema,
        )
        model_result = await self._model_client.propose_gate3_metadata_once(
            model_visible_request=model_visible_request,
            canonical_schema=response_schema,
            model_id=self._model_id,
        )
        final_provider_request = copy.deepcopy(model_result.prepared_request.form_data)
        _audit_final_provider_request(
            final_provider_request=final_provider_request,
            model_visible_request=model_visible_request,
            model_id=self._model_id,
        )
        raw_model_output = copy.deepcopy(model_result.adapter_extracted_output)
        validation_status = "validated"
        validation_error_code = None
        try:
            validated_output = validate_metadata_proposal(
                raw_model_output=raw_model_output,
                artifact=artifact,
                context_package=context_package,
                binding_registry=binding_registry,
                model_id=self._model_id,
            )
        except Gate3LlmMetadataAdapterError as exc:
            validated_output = None
            validation_status = "rejected"
            validation_error_code = exc.code
        return Gate3LlmMetadataAttempt(
            context_package=copy.deepcopy(context_package),
            binding_registry=copy.deepcopy(binding_registry),
            model_visible_request=copy.deepcopy(model_visible_request),
            final_provider_request=final_provider_request,
            raw_provider_response=copy.deepcopy(model_result.raw_provider_response),
            raw_model_output=raw_model_output,
            validated_output=validated_output,
            validation_status=validation_status,
            validation_error_code=validation_error_code,
            execution_metadata=model_result.execution_metadata,
            metrics=_attempt_metrics(
                context_package=context_package,
                final_provider_request=final_provider_request,
                raw_model_output=raw_model_output,
                validated_output=validated_output,
                execution_metadata=model_result.execution_metadata,
            ),
        )


def metadata_proposal_response_schema() -> dict[str, Any]:
    nullable_literal = {
        "anyOf": [
            {"type": "string", "minLength": 1, "maxLength": 128},
            {"type": "null"},
        ]
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "facts"],
        "properties": {
            "schema_version": {
                "type": "string",
                "enum": [GATE3_LLM_METADATA_PROPOSAL_SCHEMA_VERSION],
            },
            "facts": {
                "type": "array",
                "maxItems": PROPOSAL_FACTS_MAX,
                "uniqueItems": True,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "fact_type",
                        "source_target_alias",
                        "role_evidence_target_alias",
                        "source_literal",
                        "period_start_literal",
                        "period_end_literal",
                    ],
                    "properties": {
                        "fact_type": {
                            "type": "string",
                            "enum": list(GATE3_MINIMAL_METADATA_FACT_TYPES),
                        },
                        "source_target_alias": {
                            "type": "string",
                            "pattern": "^m[0-9]{3,}$",
                        },
                        "role_evidence_target_alias": {
                            "type": "string",
                            "pattern": "^m[0-9]{3,}$",
                        },
                        "source_literal": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 256,
                        },
                        "period_start_literal": copy.deepcopy(nullable_literal),
                        "period_end_literal": copy.deepcopy(nullable_literal),
                    },
                },
            },
        },
    }


def build_metadata_context_package(
    *,
    artifact: dict[str, Any],
    document_id: str,
    canonical_version_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if (
        not isinstance(artifact, dict)
        or not validate_canonical_artifact(artifact)["passed"]
        or str(artifact.get("artifact_id") or "") != canonical_version_id
        or not isinstance(document_id, str)
        or not document_id
    ):
        raise Gate3LlmMetadataAdapterError(
            "gate3_llm_metadata_context_canonical_invalid"
        )
    candidates: list[dict[str, Any]] = []
    for node_ordinal, node in enumerate(artifact.get("nodes") or []):
        if node.get("node_type") == "TEXT":
            candidates.extend(
                _text_line_candidates(
                    node=node,
                    node_ordinal=node_ordinal,
                )
            )
        elif node.get("node_type") == "TABLE":
            candidates.extend(
                _small_table_row_candidates(
                    node=node,
                    node_ordinal=node_ordinal,
                )
            )

    selected = candidates
    rendered_chars = sum(len(candidate["content"]) for candidate in selected)
    excluded_large_table_nodes = sum(
        node.get("node_type") == "TABLE" and _is_large_table(node)
        for node in artifact.get("nodes") or []
    )

    regions: list[dict[str, str]] = []
    bindings: dict[str, dict[str, Any]] = {}
    for ordinal, candidate in enumerate(selected, start=1):
        alias = f"m{ordinal:03d}"
        regions.append(
            {
                "target_alias": alias,
                "region_kind": candidate["region_kind"],
                "target_content": candidate["target_content"],
                "content": candidate["content"],
                "source_field_path": candidate["fragments"][0]["field_path"],
            }
        )
        bindings[alias] = {
            "document_id": document_id,
            "canonical_version_id": canonical_version_id,
            "node_id": candidate["node_id"],
            "region_kind": candidate["region_kind"],
            "content": candidate["target_content"],
            "fragments": copy.deepcopy(candidate["fragments"]),
            "source_refs": copy.deepcopy(candidate["source_refs"]),
            "structural_address": copy.deepcopy(candidate["structural_address"]),
        }

    package = {
        "schema_version": GATE3_LLM_METADATA_CONTEXT_SCHEMA_VERSION,
        "contract_version": GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
        "context_policy_version": GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION,
        "regions": regions,
        "metrics": {
            "candidate_targets": len(candidates),
            "selected_targets": len(regions),
            "rendered_context_chars": rendered_chars,
            "target_limit_reached": False,
            "position_cutoff_applied": False,
            "all_structural_candidates_selected": True,
            "excluded_large_table_nodes": excluded_large_table_nodes,
        },
    }
    registry = {
        "schema_version": GATE3_LLM_METADATA_BINDING_REGISTRY_SCHEMA_VERSION,
        "canonical_binding": {
            "document_id": document_id,
            "canonical_version_id": canonical_version_id,
        },
        "targets": bindings,
    }
    return package, registry


def compose_metadata_model_visible_request(
    *,
    context_package: dict[str, Any],
    response_schema: dict[str, Any],
) -> dict[str, Any]:
    if (
        context_package.get("schema_version")
        != GATE3_LLM_METADATA_CONTEXT_SCHEMA_VERSION
        or context_package.get("contract_version")
        != GATE3_MINIMAL_METADATA_CONTRACT_VERSION
        or context_package.get("context_policy_version")
        != GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION
        or not isinstance(context_package.get("regions"), list)
    ):
        raise Gate3LlmMetadataAdapterError("gate3_llm_metadata_context_invalid")
    contract = {
        "contract_version": GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
        "allowed_fact_types": list(GATE3_MINIMAL_METADATA_FACT_TYPES),
        "output_schema_version": GATE3_LLM_METADATA_PROPOSAL_SCHEMA_VERSION,
    }
    model_context = {
        "context_policy_version": GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION,
        "regions": copy.deepcopy(context_package["regions"]),
    }
    return {
        "messages": [
            {"role": "system", "content": GATE3_LLM_METADATA_INSTRUCTION},
            {
                "role": "user",
                "content": json.dumps(
                    contract,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    model_context,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": GATE3_LLM_METADATA_PROPOSAL_SCHEMA_VERSION,
                "strict": True,
                "schema": copy.deepcopy(response_schema),
            },
        },
    }


def validate_metadata_proposal(
    *,
    raw_model_output: Any,
    artifact: dict[str, Any],
    context_package: dict[str, Any],
    binding_registry: dict[str, Any],
    model_id: str,
) -> dict[str, Any]:
    response = _decode_response(raw_model_output)
    if (
        set(response) != {"schema_version", "facts"}
        or response.get("schema_version") != GATE3_LLM_METADATA_PROPOSAL_SCHEMA_VERSION
        or not isinstance(response.get("facts"), list)
        or len(response["facts"]) > PROPOSAL_FACTS_MAX
    ):
        raise Gate3LlmMetadataAdapterError(
            "gate3_llm_metadata_response_contract_invalid"
        )
    canonical_binding = binding_registry.get("canonical_binding")
    targets = binding_registry.get("targets")
    if (
        binding_registry.get("schema_version")
        != GATE3_LLM_METADATA_BINDING_REGISTRY_SCHEMA_VERSION
        or not isinstance(canonical_binding, dict)
        or set(canonical_binding) != {"document_id", "canonical_version_id"}
        or not isinstance(targets, dict)
        or str(artifact.get("artifact_id") or "")
        != canonical_binding.get("canonical_version_id")
        or not validate_canonical_artifact(artifact)["passed"]
        or context_package.get("contract_version")
        != GATE3_MINIMAL_METADATA_CONTRACT_VERSION
    ):
        raise Gate3LlmMetadataAdapterError(
            "gate3_llm_metadata_binding_registry_invalid"
        )

    publication_groups: dict[str, dict[str, Any]] = {}
    for proposal in response["facts"]:
        if not isinstance(proposal, dict) or set(proposal) != {
            "fact_type",
            "source_target_alias",
            "role_evidence_target_alias",
            "source_literal",
            "period_start_literal",
            "period_end_literal",
        }:
            raise Gate3LlmMetadataAdapterError(
                "gate3_llm_metadata_response_contract_invalid"
            )
        fact_type = proposal.get("fact_type")
        alias = proposal.get("source_target_alias")
        role_alias = proposal.get("role_evidence_target_alias")
        source_literal = proposal.get("source_literal")
        start_literal = proposal.get("period_start_literal")
        end_literal = proposal.get("period_end_literal")
        if (
            fact_type not in GATE3_MINIMAL_METADATA_FACT_TYPES
            or not isinstance(alias, str)
            or _ALIAS.fullmatch(alias) is None
            or not isinstance(role_alias, str)
            or _ALIAS.fullmatch(role_alias) is None
            or not isinstance(source_literal, str)
            or not source_literal
            or source_literal != source_literal.strip()
            or len(source_literal) > 256
        ):
            raise Gate3LlmMetadataAdapterError(
                "gate3_llm_metadata_response_contract_invalid"
            )
        binding = targets.get(alias)
        if not isinstance(binding, dict):
            raise Gate3LlmMetadataAdapterError("gate3_llm_metadata_target_unknown")
        if (
            binding.get("document_id") != canonical_binding["document_id"]
            or binding.get("canonical_version_id")
            != canonical_binding["canonical_version_id"]
            or not _binding_exists_in_canonical(
                artifact=artifact,
                binding=binding,
            )
        ):
            raise Gate3LlmMetadataAdapterError(
                "gate3_llm_metadata_target_binding_invalid"
            )
        role_binding = targets.get(role_alias)
        if not isinstance(role_binding, dict):
            raise Gate3LlmMetadataAdapterError(
                "gate3_llm_metadata_role_target_unknown"
            )
        if (
            role_binding.get("document_id") != canonical_binding["document_id"]
            or role_binding.get("canonical_version_id")
            != canonical_binding["canonical_version_id"]
            or not _binding_exists_in_canonical(
                artifact=artifact,
                binding=role_binding,
            )
        ):
            raise Gate3LlmMetadataAdapterError(
                "gate3_llm_metadata_role_target_binding_invalid"
            )
        if source_literal not in binding["content"]:
            raise Gate3LlmMetadataAdapterError(
                "gate3_llm_metadata_literal_not_in_target"
            )
        matching_fragments = [
            fragment
            for fragment in binding["fragments"]
            if source_literal in fragment["literal"]
        ]
        if len(matching_fragments) != 1:
            raise Gate3LlmMetadataAdapterError(
                "gate3_llm_metadata_literal_binding_ambiguous"
            )
        structural_relation = _direct_structural_relation(
            value_binding=binding,
            role_binding=role_binding,
        )
        if structural_relation is None:
            raise Gate3LlmMetadataAdapterError(
                "gate3_llm_metadata_role_value_relation_invalid"
            )
        value = _normalized_value(
            fact_type=fact_type,
            source_literal=source_literal,
            start_literal=start_literal,
            end_literal=end_literal,
            target_content=binding["content"],
        )
        fragment = matching_fragments[0]
        source_refs = sorted(set(binding["source_refs"]))
        role_source_refs = sorted(set(role_binding["source_refs"]))
        if not source_refs or not role_source_refs:
            raise Gate3LlmMetadataAdapterError("gate3_llm_metadata_source_refs_missing")
        role_evidence_binding = {
            "document_id": canonical_binding["document_id"],
            "canonical_version_id": canonical_binding["canonical_version_id"],
            "node_id": role_binding["node_id"],
            "field_path": role_binding["fragments"][0]["field_path"],
            "context_field_paths": [role_binding["fragments"][0]["field_path"]],
            "binding_kind": "llm_metadata_role_evidence_address",
            "source_target_alias": role_alias,
            "source_refs": role_source_refs,
            "structural_address": copy.deepcopy(
                role_binding["structural_address"]
            ),
            "value_relation": structural_relation,
        }
        source_binding = {
            "document_id": canonical_binding["document_id"],
            "canonical_version_id": canonical_binding["canonical_version_id"],
            "node_id": binding["node_id"],
            "field_path": fragment["field_path"],
            "context_field_paths": [
                item["field_path"] for item in binding["fragments"]
            ],
            "binding_kind": "llm_metadata_canonical_address",
            "source_target_alias": alias,
            "source_refs": source_refs,
            "structural_address": copy.deepcopy(binding["structural_address"]),
            "matched_source_sha256": hashlib.sha256(
                source_literal.encode("utf-8")
            ).hexdigest(),
            "role_evidence_binding": role_evidence_binding,
        }
        base = {
            "schema_version": GATE3_METADATA_SOURCE_FACT_SCHEMA_VERSION,
            "semantic_kind": "normalized_source_fact",
            "fact_type": fact_type,
            "category": _CATEGORY_BY_FACT_TYPE[fact_type],
            "value": value,
            "tax_meaning_assigned": False,
        }
        semantic_key = _sha256(
            {
                "document_id": source_binding["document_id"],
                "canonical_version_id": source_binding["canonical_version_id"],
                "fact_type": fact_type,
                "value": value,
            }
        )
        source_meaning_key = _source_meaning_key(
            artifact=artifact,
            binding=binding,
            fragment=fragment,
        )
        publication_key = _sha256(
            {
                "semantic_key": semantic_key,
                "source_meaning_key": source_meaning_key,
            }
        )
        evidence_key = _sha256(
            {
                "document_id": source_binding["document_id"],
                "canonical_version_id": source_binding["canonical_version_id"],
                "node_id": source_binding["node_id"],
                "field_path": source_binding["field_path"],
                "source_target_alias": source_binding["source_target_alias"],
            }
        )
        group = publication_groups.get(publication_key)
        if group is None:
            publication_groups[publication_key] = {
                "base": base,
                "evidence_bindings": [source_binding],
                "evidence_keys": {evidence_key},
            }
        else:
            if evidence_key in group["evidence_keys"]:
                raise Gate3LlmMetadataAdapterError(
                    "gate3_llm_metadata_duplicate_assertion"
                )
            group["evidence_keys"].add(evidence_key)
            group["evidence_bindings"].append(source_binding)

    facts: list[dict[str, Any]] = []
    collapsed_repeated_assertions = 0
    for group in publication_groups.values():
        evidence_bindings = sorted(
            group["evidence_bindings"],
            key=_source_binding_order,
        )
        collapsed_repeated_assertions += len(evidence_bindings) - 1
        primary_binding = copy.deepcopy(evidence_bindings[0])
        primary_binding["evidence_locations"] = copy.deepcopy(evidence_bindings)
        base = {
            **group["base"],
            "source_binding": primary_binding,
        }
        facts.append({**base, "fact_id": "g3metadata_" + _sha256(base)[:32]})
    facts.sort(key=lambda fact: _source_binding_order(fact["source_binding"]))

    category_counts = {
        category: sum(fact["category"] == category for fact in facts)
        for category in (
            "PERSON_IDENTITY",
            "DOCUMENT_IDENTITY",
            "ISSUER_IDENTITY",
            "ACCOUNT_IDENTITY",
        )
    }
    return {
        "schema_version": GATE3_METADATA_SOURCE_FACT_COLLECTION_SCHEMA_VERSION,
        "status": "metadata_source_facts_available",
        "terminals": [GATE3_LLM_METADATA_VALIDATED_TERMINAL],
        "documents": [
            {
                "document_id": canonical_binding["document_id"],
                "canonical_version_id": canonical_binding["canonical_version_id"],
                "metadata_facts": len(facts),
            }
        ],
        "metadata_facts": facts,
        "coverage": {
            "metadata_category_counts": category_counts,
            "typed_metadata_facts": len(facts),
            "raw_validated_assertions": len(response["facts"]),
            "collapsed_repeated_assertions": collapsed_repeated_assertions,
            "published_metadata_facts": len(facts),
            "provenance_complete": all(
                bool(fact["source_binding"]["source_refs"])
                and bool(fact["source_binding"]["evidence_locations"])
                and bool(
                    fact["source_binding"]["role_evidence_binding"]["source_refs"]
                )
                for fact in facts
            ),
            "invented_source_facts": 0,
            "unsupported_entity_role_inferences": 0,
        },
        "adapter_identity": {
            "contract_version": GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
            "instruction_id": GATE3_LLM_METADATA_INSTRUCTION_ID,
            "instruction_version": GATE3_LLM_METADATA_INSTRUCTION_VERSION,
            "context_policy_version": (GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION),
            "proposal_schema_version": (GATE3_LLM_METADATA_PROPOSAL_SCHEMA_VERSION),
            "model_id": model_id,
        },
        "tax_meaning_assigned": False,
        "persistence": "none_new",
    }


def _text_line_candidates(
    *,
    node: dict[str, Any],
    node_ordinal: int,
) -> list[dict[str, Any]]:
    content = node.get("content") or {}
    lines = str(content.get("text") or "").splitlines()
    node_refs = _source_refs(node)
    candidates: list[dict[str, Any]] = []
    for line_index, line in enumerate(lines):
        literal = line.strip()
        if not literal:
            continue
        fragment = {
            "field_path": f"content.text.lines[{line_index}]",
            "literal": literal,
            "source_refs": node_refs,
        }
        candidates.append(
            {
                "candidate_order": (node_ordinal, line_index),
                "node_id": str(node.get("node_id") or ""),
                "region_kind": "TEXT_LINE",
                "target_content": literal,
                "content": f"L{line_index}: {literal}",
                "fragments": [fragment],
                "source_refs": node_refs,
                "structural_address": {
                    "kind": "text_line",
                    "line": line_index,
                },
            }
        )
    return candidates


def _small_table_row_candidates(
    *,
    node: dict[str, Any],
    node_ordinal: int,
) -> list[dict[str, Any]]:
    cells = (node.get("content") or {}).get("cells") or []
    nonempty: list[tuple[int, dict[str, Any], str]] = []
    for index, cell in enumerate(cells):
        literal = _cell_text(cell)
        if literal:
            nonempty.append((index, cell, literal))
    if not nonempty or len(nonempty) > SMALL_TABLE_NONEMPTY_CELLS_MAX:
        return []
    rows: dict[int, list[tuple[int, int, dict[str, Any], str]]] = {}
    for cell_index, cell, literal in nonempty:
        row = cell.get("row")
        column = cell.get("column")
        if (
            isinstance(row, int)
            and not isinstance(row, bool)
            and row >= 1
            and isinstance(column, int)
            and not isinstance(column, bool)
            and column >= 1
        ):
            rows.setdefault(row, []).append((column, cell_index, cell, literal))
    if not rows:
        return []
    node_refs = _source_refs(node)
    header_row = _canonical_table_header_row(node=node, rows=rows)
    candidates: list[dict[str, Any]] = []
    for row in sorted(rows):
        target_rows = (
            (header_row, row)
            if header_row is not None and row != header_row
            else (row,)
        )
        rendered: list[str] = []
        for target_row in target_rows:
            cells_rendered: list[str] = []
            for column, cell_index, cell, literal in sorted(rows[target_row]):
                cells_rendered.append(f"C{column}: {literal}")
            prefix = "H" if target_row == header_row else "R"
            rendered.append(
                f"{prefix}{target_row}: " + " | ".join(cells_rendered)
            )
        region_kind = (
            "SMALL_TABLE_ROW_WITH_HEADER"
            if header_row is not None
            else "SMALL_TABLE_ROW"
        )
        for column, cell_index, cell, literal in sorted(rows[row]):
            refs = sorted({*node_refs, *_source_refs(cell)})
            candidates.append(
                {
                    "candidate_order": (node_ordinal, row, column),
                    "node_id": str(node.get("node_id") or ""),
                    "region_kind": region_kind,
                    "target_content": literal,
                    "content": "\n".join(rendered),
                    "fragments": [
                        {
                            "field_path": f"content.cells[{cell_index}]",
                            "literal": literal,
                            "source_refs": refs,
                        }
                    ],
                    "source_refs": refs,
                    "structural_address": {
                        "kind": "table_cell",
                        "row": row,
                        "column": column,
                        "header_row": header_row,
                    },
                }
            )
    return candidates


def _canonical_table_header_row(
    *,
    node: dict[str, Any],
    rows: dict[int, list[tuple[int, int, dict[str, Any], str]]],
) -> int | None:
    header = (node.get("content") or {}).get("header")
    if not isinstance(header, list) or not header:
        return None
    expected = [" ".join(str(item).split()) for item in header]
    if not any(expected):
        return None
    for row, row_cells in sorted(rows.items()):
        actual_by_column = {
            column: " ".join(literal.split())
            for column, _cell_index, _cell, literal in row_cells
        }
        actual = [actual_by_column.get(index, "") for index in range(1, len(expected) + 1)]
        if actual == expected:
            return row
    return None


def _source_meaning_key(
    *,
    artifact: dict[str, Any],
    binding: dict[str, Any],
    fragment: dict[str, Any],
) -> dict[str, Any]:
    nodes = [
        node
        for node in artifact.get("nodes") or []
        if str(node.get("node_id") or "") == binding.get("node_id")
    ]
    if len(nodes) != 1:
        raise Gate3LlmMetadataAdapterError(
            "gate3_llm_metadata_source_meaning_context_invalid"
        )
    node = nodes[0]
    if binding.get("region_kind") == "TEXT_LINE":
        return {
            "unit_kind": "CANONICAL_TEXT_LINE",
            "source_context": " ".join(fragment["literal"].split()),
        }
    if binding.get("region_kind") not in {
        "SMALL_TABLE_ROW",
        "SMALL_TABLE_ROW_WITH_HEADER",
    }:
        raise Gate3LlmMetadataAdapterError(
            "gate3_llm_metadata_source_meaning_context_invalid"
        )
    match = re.fullmatch(r"content\.cells\[([0-9]+)\]", fragment["field_path"])
    cells = (node.get("content") or {}).get("cells") or []
    if match is None or int(match.group(1)) >= len(cells):
        raise Gate3LlmMetadataAdapterError(
            "gate3_llm_metadata_source_meaning_context_invalid"
        )
    matched_cell = cells[int(match.group(1))]
    column = matched_cell.get("column")
    row = matched_cell.get("row")
    if (
        not isinstance(column, int)
        or isinstance(column, bool)
        or column < 1
        or not isinstance(row, int)
        or isinstance(row, bool)
        or row < 1
    ):
        raise Gate3LlmMetadataAdapterError(
            "gate3_llm_metadata_source_meaning_context_invalid"
        )
    table_rows: dict[int, list[tuple[int, int, dict[str, Any], str]]] = {}
    for index, cell in enumerate(cells):
        if not isinstance(cell, dict) or not _cell_text(cell):
            continue
        cell_row = cell.get("row")
        cell_column = cell.get("column")
        if isinstance(cell_row, int) and isinstance(cell_column, int):
            table_rows.setdefault(cell_row, []).append(
                (cell_column, index, cell, _cell_text(cell))
            )
    header_row = _canonical_table_header_row(node=node, rows=table_rows)
    if header_row is None:
        row_context = [
            {
                "column": cell.get("column"),
                "literal": " ".join(_cell_text(cell).split()),
            }
            for cell in cells
            if isinstance(cell, dict)
            and cell.get("row") == row
            and _cell_text(cell)
        ]
        row_context.sort(key=lambda item: item["column"])
        if not row_context:
            raise Gate3LlmMetadataAdapterError(
                "gate3_llm_metadata_source_meaning_context_invalid"
            )
        return {
            "unit_kind": "CANONICAL_TABLE_ROW",
            "column": column,
            "row_context": row_context,
        }
    header_context = [
        {
            "column": cell.get("column"),
            "literal": " ".join(_cell_text(cell).split()),
        }
        for cell in cells
        if isinstance(cell, dict)
        and cell.get("row") == header_row
        and _cell_text(cell)
    ]
    header_context.sort(key=lambda item: item["column"])
    if not header_context:
        raise Gate3LlmMetadataAdapterError(
            "gate3_llm_metadata_source_meaning_context_invalid"
        )
    return {
        "unit_kind": "CANONICAL_TABLE_COLUMN_WITH_HEADER",
        "column": column,
        "header_context": header_context,
    }


def _direct_structural_relation(
    *,
    value_binding: dict[str, Any],
    role_binding: dict[str, Any],
) -> str | None:
    if (
        value_binding.get("document_id") != role_binding.get("document_id")
        or value_binding.get("canonical_version_id")
        != role_binding.get("canonical_version_id")
        or value_binding.get("node_id") != role_binding.get("node_id")
    ):
        return None
    value_address = value_binding.get("structural_address")
    role_address = role_binding.get("structural_address")
    if not isinstance(value_address, dict) or not isinstance(role_address, dict):
        return None
    if value_address == role_address:
        return "SAME_ATOMIC_ADDRESS"
    if value_address.get("kind") != "table_cell" or role_address.get("kind") != "table_cell":
        return None
    if value_address.get("row") == role_address.get("row"):
        return "SAME_TABLE_ROW"
    header_row = value_address.get("header_row")
    if (
        isinstance(header_row, int)
        and role_address.get("header_row") == header_row
        and role_address.get("row") == header_row
        and value_address.get("row") != header_row
        and value_address.get("column") == role_address.get("column")
    ):
        return "TABLE_HEADER_LINEAGE"
    return None


def _source_binding_order(binding: dict[str, Any]) -> tuple[int, str, str]:
    alias = str(binding.get("source_target_alias") or "")
    alias_order = int(alias[1:]) if _ALIAS.fullmatch(alias) else 10**9
    return (
        alias_order,
        str(binding.get("node_id") or ""),
        str(binding.get("field_path") or ""),
    )


def _is_large_table(node: dict[str, Any]) -> bool:
    cells = (node.get("content") or {}).get("cells") or []
    return sum(bool(_cell_text(cell)) for cell in cells) > (
        SMALL_TABLE_NONEMPTY_CELLS_MAX
    )


def _binding_exists_in_canonical(
    *,
    artifact: dict[str, Any],
    binding: dict[str, Any],
) -> bool:
    if set(binding) != {
        "document_id",
        "canonical_version_id",
        "node_id",
        "region_kind",
        "content",
        "fragments",
        "source_refs",
        "structural_address",
    }:
        return False
    nodes = [
        node
        for node in artifact.get("nodes") or []
        if str(node.get("node_id") or "") == binding.get("node_id")
    ]
    if len(nodes) != 1 or not isinstance(binding.get("fragments"), list):
        return False
    node = nodes[0]
    actual_refs: set[str] = set()
    for fragment in binding["fragments"]:
        if not isinstance(fragment, dict) or set(fragment) != {
            "field_path",
            "literal",
            "source_refs",
        }:
            return False
        actual = _canonical_fragment(node, fragment["field_path"])
        if actual is None or actual[0] != fragment["literal"]:
            return False
        if actual[1] != fragment["source_refs"]:
            return False
        actual_refs.update(actual[1])
    if sorted(actual_refs) != binding.get("source_refs"):
        return False
    address = binding.get("structural_address")
    if not isinstance(address, dict) or len(binding["fragments"]) != 1:
        return False
    field_path = binding["fragments"][0]["field_path"]
    if address.get("kind") == "text_line":
        match = re.fullmatch(r"content\.text\.lines\[([0-9]+)\]", field_path)
        return (
            node.get("node_type") == "TEXT"
            and match is not None
            and address == {"kind": "text_line", "line": int(match.group(1))}
        )
    if address.get("kind") == "table_cell":
        match = re.fullmatch(r"content\.cells\[([0-9]+)\]", field_path)
        cells = (node.get("content") or {}).get("cells") or []
        if match is None or int(match.group(1)) >= len(cells):
            return False
        cell = cells[int(match.group(1))]
        rows: dict[int, list[tuple[int, int, dict[str, Any], str]]] = {}
        for index, candidate in enumerate(cells):
            if not isinstance(candidate, dict) or not _cell_text(candidate):
                continue
            row = candidate.get("row")
            column = candidate.get("column")
            if isinstance(row, int) and isinstance(column, int):
                rows.setdefault(row, []).append(
                    (column, index, candidate, _cell_text(candidate))
                )
        return address == {
            "kind": "table_cell",
            "row": cell.get("row"),
            "column": cell.get("column"),
            "header_row": _canonical_table_header_row(node=node, rows=rows),
        }
    return False


def _canonical_fragment(
    node: dict[str, Any],
    field_path: Any,
) -> tuple[str, list[str]] | None:
    if not isinstance(field_path, str):
        return None
    line_match = re.fullmatch(r"content\.text\.lines\[([0-9]+)\]", field_path)
    if line_match and node.get("node_type") == "TEXT":
        lines = str((node.get("content") or {}).get("text") or "").splitlines()
        index = int(line_match.group(1))
        if index >= len(lines) or not lines[index].strip():
            return None
        return lines[index].strip(), _source_refs(node)
    cell_match = re.fullmatch(r"content\.cells\[([0-9]+)\]", field_path)
    if cell_match and node.get("node_type") == "TABLE":
        cells = (node.get("content") or {}).get("cells") or []
        index = int(cell_match.group(1))
        if index >= len(cells) or not isinstance(cells[index], dict):
            return None
        literal = _cell_text(cells[index])
        if not literal:
            return None
        return literal, sorted({*_source_refs(node), *_source_refs(cells[index])})
    return None


def _normalized_value(
    *,
    fact_type: str,
    source_literal: str,
    start_literal: Any,
    end_literal: Any,
    target_content: str,
) -> dict[str, Any]:
    if fact_type == "STATEMENT_PERIOD":
        if (
            not isinstance(start_literal, str)
            or not isinstance(end_literal, str)
            or not start_literal
            or not end_literal
            or start_literal not in source_literal
            or end_literal not in source_literal
            or start_literal not in target_content
            or end_literal not in target_content
        ):
            raise Gate3LlmMetadataAdapterError(
                "gate3_llm_metadata_period_evidence_invalid"
            )
        start = _date(start_literal)
        end = _date(end_literal)
        if start is None or end is None or start > end:
            raise Gate3LlmMetadataAdapterError(
                "gate3_llm_metadata_period_evidence_invalid"
            )
        return {"kind": "period", "start": start, "end": end}
    if start_literal is not None or end_literal is not None:
        raise Gate3LlmMetadataAdapterError(
            "gate3_llm_metadata_nonperiod_boundaries_forbidden"
        )
    if fact_type in {"DOCUMENT_DATE", "PERSON_BIRTH_DATE"}:
        value = _date(source_literal)
        if value is None:
            raise Gate3LlmMetadataAdapterError(
                "gate3_llm_metadata_date_literal_invalid"
            )
        return {"kind": "date", "date": value}
    normalized = " ".join(source_literal.split()).strip(" ,;:-")
    if not normalized or len(normalized) > 256:
        raise Gate3LlmMetadataAdapterError("gate3_llm_metadata_text_literal_invalid")
    return {"kind": "text", "normalized": normalized}


def _date(value: str) -> str | None:
    for pattern in (
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
        "%d.%m.%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _source_refs(value: dict[str, Any]) -> list[str]:
    return sorted(
        {
            str(item)
            for item in value.get("source_refs") or []
            if isinstance(item, str) and item
        }
    )


def _cell_text(cell: dict[str, Any]) -> str:
    value = cell.get("displayed_value")
    if value is None:
        value = cell.get("value")
    return "" if value is None else str(value).strip()


def _decode_response(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if not isinstance(value, str):
        raise Gate3LlmMetadataAdapterError(
            "gate3_llm_metadata_response_contract_invalid"
        )
    try:
        decoded = json.loads(
            value,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except (ValueError, json.JSONDecodeError) as exc:
        raise Gate3LlmMetadataAdapterError(
            "gate3_llm_metadata_response_contract_invalid"
        ) from exc
    if not isinstance(decoded, dict):
        raise Gate3LlmMetadataAdapterError(
            "gate3_llm_metadata_response_contract_invalid"
        )
    return decoded


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKeyError(key)
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(value)


def _audit_final_provider_request(
    *,
    final_provider_request: dict[str, Any],
    model_visible_request: dict[str, Any],
    model_id: str,
) -> None:
    messages = final_provider_request.get("messages")
    system = final_provider_request.get("system")
    if system is None:
        parts = (
            [item.get("content") for item in messages]
            if isinstance(messages, list)
            and all(isinstance(item, dict) for item in messages)
            else []
        )
    else:
        parts = (
            [system, *[item.get("content") for item in messages]]
            if isinstance(system, str)
            and isinstance(messages, list)
            and all(isinstance(item, dict) for item in messages)
            else []
        )
    expected = [item["content"] for item in model_visible_request["messages"]]
    if (
        final_provider_request.get("model") != model_id
        or parts != expected
        or "metadata" in final_provider_request
    ):
        raise Gate3LlmMetadataAdapterError(
            "gate3_llm_metadata_model_input_audit_failed"
        )


def _attempt_metrics(
    *,
    context_package: dict[str, Any],
    final_provider_request: dict[str, Any],
    raw_model_output: Any,
    validated_output: dict[str, Any] | None,
    execution_metadata: Any,
) -> dict[str, Any]:
    final_json = json.dumps(
        final_provider_request,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    raw_json = (
        raw_model_output
        if isinstance(raw_model_output, str)
        else json.dumps(
            raw_model_output,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    )
    return {
        **copy.deepcopy(context_package["metrics"]),
        "instruction_chars": len(GATE3_LLM_METADATA_INSTRUCTION),
        "final_model_input_chars": len(final_json),
        "final_model_input_bytes": len(final_json.encode("utf-8")),
        "raw_model_output_chars": len(raw_json),
        "raw_model_output_bytes": len(raw_json.encode("utf-8")),
        "input_tokens": getattr(execution_metadata, "input_tokens", None),
        "output_tokens": getattr(execution_metadata, "output_tokens", None),
        "total_tokens": getattr(execution_metadata, "total_tokens", None),
        "duration_ms": getattr(execution_metadata, "duration_ms", None),
        "provider_submissions": 1,
        "retries": 0,
        "best_of_n": False,
        "manual_output_repair": False,
        "validated_facts": (
            len(validated_output["metadata_facts"])
            if validated_output is not None
            else 0
        ),
    }


def _sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE3_LLM_METADATA_CONTEXT_POLICY_VERSION",
    "GATE3_LLM_METADATA_INSTRUCTION",
    "GATE3_LLM_METADATA_INSTRUCTION_ID",
    "GATE3_LLM_METADATA_INSTRUCTION_VERSION",
    "GATE3_LLM_METADATA_PROPOSAL_SCHEMA_VERSION",
    "GATE3_LLM_METADATA_VALIDATED_TERMINAL",
    "Gate3LlmMetadataAdapterError",
    "Gate3LlmMetadataAdapterFactory",
    "Gate3LlmMetadataAttempt",
    "build_metadata_context_package",
    "compose_metadata_model_visible_request",
    "metadata_proposal_response_schema",
    "validate_metadata_proposal",
]
