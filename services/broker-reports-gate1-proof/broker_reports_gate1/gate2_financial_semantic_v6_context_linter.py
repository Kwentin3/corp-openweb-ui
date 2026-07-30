from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, replace
from typing import Any

from .gate2_economy_budget import (
    TOKEN_ESTIMATOR_ID,
    estimate_gate2_request_input_tokens,
)
from .gate2_financial_evidence_materialization import (
    Gate2FinancialEvidenceSourcePackage,
)
from .gate2_financial_evidence_materialization_contracts import sha256_json
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_semantic_v6_bundle import (
    Gate2FinancialEvidenceBundle,
)
from .gate2_financial_semantic_v6_candidate_compiler import (
    Gate2FinancialCandidateCompilation,
)
from .gate2_financial_semantic_v6_choice import (
    Gate2FinancialSemanticV6ChoiceContract,
    Gate2FinancialSemanticV6ChoiceError,
    Gate2FinancialSemanticV6TypeFirstResponseProfile,
    normalize_financial_semantic_v6_local_choice,
    validate_financial_semantic_v6_choice_contract,
    validate_financial_semantic_v6_type_first_response_profile,
)
from .gate2_financial_semantic_v6_expansion import (
    Gate2FinancialSemanticV6DecisionExpansionFactory,
)
from .gate2_financial_semantic_v6_packet import (
    CONTEXT_V2_1_POLICY_VERSION,
    SEMANTIC_PACKET_AMBIGUITY_RULE,
    SLIM_VIEW_BLOCKS,
    SLIM_VIEW_UNCLASSIFIED_REASONS,
    TYPE_FIRST_BLOCKS,
    TYPE_FIRST_CONTEXT_PROFILE,
    TYPE_FIRST_DECISION_POLICY_VERSION,
    TYPE_FIRST_FORBIDDEN_FIELDS,
    TYPE_FIRST_TASK,
    Gate2FinancialSemanticV6Packet,
    Gate2FinancialSemanticV6ContextV21MappingReceipt,
    Gate2FinancialSemanticV6SlimAliasReceipt,
    Gate2FinancialSemanticV6TypeFirstCandidate,
    Gate2FinancialSemanticV6TypeFirstMappingReceipt,
    validate_financial_semantic_v6_packet,
)
from .gate2_financial_semantic_v6_prompt import (
    V6_SEMANTIC_PROMPT_HASH,
    V6_SEMANTIC_PROMPT_VERSION,
    V6_SEMANTIC_SYSTEM_PROMPT,
)
from .gate2_financial_semantic_v6_totality import (
    Gate2FinancialSemanticV6TotalMaterializerFactory,
)
from .gate2_model_requests import (
    FINANCIAL_SEMANTIC_V6_CONTEXT_LINT_PASSED,
    FINANCIAL_SEMANTIC_V6_CONTEXT_LINT_POLICY_VERSION,
    FINANCIAL_SEMANTIC_V6_CONTEXT_LINT_RECEIPT_SCHEMA_VERSION,
    FINANCIAL_SEMANTIC_V6_CONTEXT_TOKEN_ESTIMATOR_ID,
    FINANCIAL_SEMANTIC_V6_SLIM_LINTED_REQUEST_PROFILE,
    FINANCIAL_SEMANTIC_V6_TYPE_FIRST_LOCAL_PROOF_REQUEST_PROFILE,
    FINANCIAL_SEMANTIC_V6_TYPE_FIRST_SEALED_REQUEST_RECEIPT_SCHEMA_VERSION as TYPE_FIRST_SEALED_REQUEST_RECEIPT_SCHEMA_VERSION,
    FINANCIAL_SEMANTIC_V6_TYPE_FIRST_SEALED_REQUEST_STATUS_PASSED as TYPE_FIRST_SEALED_REQUEST_STATUS_PASSED,
    Gate2FinancialSemanticV6ContextLintReceipt,
    Gate2FinancialSemanticV6TypeFirstSealedRequest,
    Gate2FinancialSemanticV6TypeFirstSealedRequestReceipt,
    Gate2OpenWebUIRequestBuilder,
    _issue_type_first_request_builder_seal,
    financial_semantic_v6_model_visible_utf8_bytes,
    financial_semantic_v6_slim_model_visible_projection,
)


CONTEXT_LINT_TOTALITY_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v6_context_totality_v1"
)
CONTEXT_LINT_TOTALITY_POLICY_VERSION = (
    "broker_reports_gate2_llm_semantic_context_linter_v1"
)
CONTEXT_V2_1_SEALED_REQUEST_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate2_llm_semantic_context_v2_1_"
    "sealed_request_receipt_v1"
)
CONTEXT_V2_1_SEALED_REQUEST_PROFILE = (
    "broker_reports_gate2_financial_semantic_v6_request_v2_1_candidate"
)
CONTEXT_V2_1_SEALED_REQUEST_MAX_UTF8_BYTES = 4_500
CONTEXT_V2_1_SEALED_REQUEST_STATUS_PASSED = "passed"
TYPE_FIRST_LOCAL_PROOF_REQUEST_PROFILE = (
    FINANCIAL_SEMANTIC_V6_TYPE_FIRST_LOCAL_PROOF_REQUEST_PROFILE
)
TYPE_FIRST_LOGICAL_REQUEST_MAX_UTF8_BYTES = 2_500
FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV6ContextLinterFactory is the only V6 complete "
    "request lint-and-seal authority for the historical Slim request and "
    "the non-active Context V2.1 or Type-First provider-neutral request"
)
FORBIDDEN = (
    "No V6 Slim request may reach the transport builder without one exact "
    "passed request-bound lint receipt; Context V2.1 and Type-First must "
    "remain non-active and provider-neutral; the linter must not repair "
    "context, aliases, model choices, canonical bindings or materialized "
    "records"
)

_FORBIDDEN_MODEL_FIELDS = frozenset(
    {
        "active_packet_hash",
        "artifact_ref",
        "association_ref",
        "bundle_id",
        "candidate_compilation_integrity_hash",
        "choice_schema_hash",
        "content_hash",
        "document_ref",
        "evidence_ref",
        "input_type_id",
        "integrity_hash",
        "normalization_run_ref",
        "option_id",
        "packet_hash",
        "path",
        "prompt_hash",
        "provenance",
        "provenance_ref",
        "provider_metadata",
        "provider_response_id",
        "receipt_hash",
        "repository_path",
        "return_id",
        "schema_hash",
        "scope_ref",
        "source_package_ref",
        "source_scope_ref",
        "source_value_ref",
        "storage_id",
        "typed_option_id",
        "view_hash",
    }
)
_STRUCTURAL_KINDS = frozenset(
    {"section", "table", "row", "text segment", "evidence group"}
)
_STRUCTURAL_FIELDS = frozenset(
    {
        "alias",
        "kind",
        "children",
        "values",
        "label",
        "section_role",
        "row_role",
    }
)
_VALUE_FIELDS = frozenset({"alias", "meaning", "value", "type", "label"})
_TYPE_CARD_FIELDS = frozenset(
    {"alias", "meaning", "distinctions", "unclassified_when"}
)
_DISTINCTION_FIELDS = frozenset({"against", "rule"})
_CHOICE_FIELDS = frozenset({"alias", "type", "bindings"})
_ALIAS_PATTERNS = {
    "section": re.compile(r"s[1-9][0-9]*"),
    "table": re.compile(r"t[1-9][0-9]*"),
    "row": re.compile(r"r[1-9][0-9]*"),
    "text segment": re.compile(r"seg[1-9][0-9]*"),
    "evidence group": re.compile(r"g[1-9][0-9]*"),
    "value": re.compile(r"v[1-9][0-9]*"),
    "type": re.compile(r"T[1-9][0-9]*"),
    "choice": re.compile(r"[A-Z]+"),
}
_ALLOWED_CHILDREN = {
    "document": _STRUCTURAL_KINDS,
    "section": _STRUCTURAL_KINDS,
    "table": frozenset({"row", "text segment", "evidence group"}),
    "row": frozenset({"text segment", "evidence group"}),
    "text segment": frozenset({"evidence group"}),
    "evidence group": frozenset(),
}


class Gate2FinancialSemanticV6ContextLintError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2FinancialSemanticV6ContextLintedPrompt:
    version: str
    content: str
    hash: str
    packet_hash: str
    choice_schema_hash: str
    context_lint_receipt: Gate2FinancialSemanticV6ContextLintReceipt


@dataclass(frozen=True)
class Gate2FinancialSemanticV6LintedRequest:
    prompt: Gate2FinancialSemanticV6ContextLintedPrompt
    package: dict[str, Any]
    response_format: dict[str, Any]
    canonical_request: dict[str, Any]
    lint_receipt: Gate2FinancialSemanticV6ContextLintReceipt

    def safe_summary(self) -> dict[str, Any]:
        return {
            "request_profile": (
                FINANCIAL_SEMANTIC_V6_SLIM_LINTED_REQUEST_PROFILE
            ),
            "model_visible_request_hash": (
                self.lint_receipt.model_visible_request_hash
            ),
            "model_visible_utf8_bytes": (
                self.lint_receipt.model_visible_utf8_bytes
            ),
            "estimated_input_tokens": (
                self.lint_receipt.estimated_input_tokens
            ),
            "context_lint_receipt": self.lint_receipt.to_safe_dict(),
            "provider_calls_total": 0,
            "contains_source_literals": False,
            "contains_exact_refs": False,
        }


@dataclass(frozen=True)
class Gate2FinancialSemanticV6ContextV21SealedRequestReceipt:
    schema_version: str
    policy_version: str
    request_profile: str
    mapping_receipt_integrity_hash: str
    context_view_hash: str
    system_prompt_version: str
    system_prompt_hash: str
    local_response_profile_identity: str
    response_schema_hash: str
    response_format_hash: str
    model_visible_request_hash: str
    model_visible_utf8_bytes: int
    token_estimator_id: str
    estimated_input_tokens: int
    invariant_counters: dict[str, int]
    status: str
    provider_calls_total: int
    integrity_hash: str

    def integrity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "request_profile": self.request_profile,
            "mapping_receipt_integrity_hash": (
                self.mapping_receipt_integrity_hash
            ),
            "context_view_hash": self.context_view_hash,
            "system_prompt_version": self.system_prompt_version,
            "system_prompt_hash": self.system_prompt_hash,
            "local_response_profile_identity": (
                self.local_response_profile_identity
            ),
            "response_schema_hash": self.response_schema_hash,
            "response_format_hash": self.response_format_hash,
            "model_visible_request_hash": (
                self.model_visible_request_hash
            ),
            "model_visible_utf8_bytes": self.model_visible_utf8_bytes,
            "token_estimator_id": self.token_estimator_id,
            "estimated_input_tokens": self.estimated_input_tokens,
            "invariant_counters": copy.deepcopy(
                self.invariant_counters
            ),
            "status": self.status,
            "provider_calls_total": self.provider_calls_total,
        }

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            **self.integrity_payload(),
            "integrity_hash": self.integrity_hash,
        }


@dataclass(frozen=True)
class Gate2FinancialSemanticV6ContextV21SealedRequest:
    active: bool
    transport_eligible: bool
    serialized_context: str
    response_format: dict[str, Any]
    model_visible_request: dict[str, Any]
    sealed_request_receipt: (
        Gate2FinancialSemanticV6ContextV21SealedRequestReceipt
    )

    def safe_summary(self) -> dict[str, Any]:
        return {
            "request_profile": CONTEXT_V2_1_SEALED_REQUEST_PROFILE,
            "active": self.active,
            "transport_eligible": self.transport_eligible,
            "model_visible_request_hash": (
                self.sealed_request_receipt.model_visible_request_hash
            ),
            "model_visible_utf8_bytes": (
                self.sealed_request_receipt.model_visible_utf8_bytes
            ),
            "estimated_input_tokens": (
                self.sealed_request_receipt.estimated_input_tokens
            ),
            "sealed_request_receipt": (
                self.sealed_request_receipt.to_safe_dict()
            ),
            "provider_calls_total": 0,
            "contains_source_literals": False,
            "contains_exact_refs": False,
        }


@dataclass(frozen=True)
class Gate2FinancialSemanticV6ContextTotalityReceipt:
    schema_version: str
    policy_version: str
    lint_receipt_integrity_hash: str
    exact_replay: bool
    local_outputs_total: int
    typed_outputs_total: int
    unclassified_outputs_total: int
    total_materializations_total: int
    validated_but_unmaterializable_total: int
    outcome_integrity_hashes: tuple[str, ...]
    provider_calls_total: int
    integrity_hash: str

    def integrity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "lint_receipt_integrity_hash": (
                self.lint_receipt_integrity_hash
            ),
            "exact_replay": self.exact_replay,
            "local_outputs_total": self.local_outputs_total,
            "typed_outputs_total": self.typed_outputs_total,
            "unclassified_outputs_total": (
                self.unclassified_outputs_total
            ),
            "total_materializations_total": (
                self.total_materializations_total
            ),
            "validated_but_unmaterializable_total": (
                self.validated_but_unmaterializable_total
            ),
            "outcome_integrity_hashes": list(
                self.outcome_integrity_hashes
            ),
            "provider_calls_total": self.provider_calls_total,
        }

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            **self.integrity_payload(),
            "integrity_hash": self.integrity_hash,
        }


@dataclass(frozen=True)
class _VisibleContext:
    structural_aliases: tuple[str, ...]
    value_records: tuple[dict[str, Any], ...]
    type_aliases: tuple[str, ...]
    choice_aliases: tuple[str, ...]
    choice_type_aliases: tuple[str, ...]
    binding_aliases: tuple[str, ...]


class Gate2FinancialSemanticV6ContextLinterFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
    ) -> None:
        self.registry = registry

    def create(
        self,
        *,
        packet: Gate2FinancialSemanticV6Packet,
        choice_contract: Gate2FinancialSemanticV6ChoiceContract,
        evidence_bundle: Gate2FinancialEvidenceBundle,
        source_package: Gate2FinancialEvidenceSourcePackage,
        compilation: Gate2FinancialCandidateCompilation,
        candidate_payload: dict[str, Any],
        response_schema: dict[str, Any],
        alias_receipt: Gate2FinancialSemanticV6SlimAliasReceipt,
        exact_model_id: str,
    ) -> Gate2FinancialSemanticV6LintedRequest:
        validate_financial_semantic_v6_packet(
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            registry=self.registry,
        )
        validate_financial_semantic_v6_choice_contract(
            contract=choice_contract,
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            registry=self.registry,
        )
        if not isinstance(exact_model_id, str) or not exact_model_id:
            _fail("financial_semantic_v6_context_lint_model_invalid")
        if not isinstance(alias_receipt, Gate2FinancialSemanticV6SlimAliasReceipt):
            _fail("financial_semantic_v6_context_lint_receipt_invalid")

        exact_payload = copy.deepcopy(candidate_payload)
        exact_schema = copy.deepcopy(response_schema)
        null_fields_total = _count_nulls(
            {
                "prompt": V6_SEMANTIC_SYSTEM_PROMPT,
                "payload": exact_payload,
                "response_schema": exact_schema,
            }
        )
        if null_fields_total:
            _fail("financial_semantic_v6_context_lint_null_field")

        forbidden_fields_total = _count_forbidden_fields(
            {
                "payload": exact_payload,
                "response_schema": exact_schema,
            }
        )
        if forbidden_fields_total:
            _fail("financial_semantic_v6_context_lint_forbidden_field")
        visible = _validate_visible_context(exact_payload)

        (
            alias_collisions_total,
            unmapped_aliases_total,
            orphan_aliases_total,
        ) = _alias_metrics(
            visible=visible,
            alias_receipt=alias_receipt,
        )
        if alias_collisions_total:
            _fail("financial_semantic_v6_context_lint_alias_collision")
        if unmapped_aliases_total:
            _fail("financial_semantic_v6_context_lint_alias_unmapped")
        if orphan_aliases_total:
            _fail("financial_semantic_v6_context_lint_alias_orphan")

        (
            semantic_literals_total,
            semantic_literals_covered_total,
            duplicate_literals_total,
        ) = _semantic_literal_metrics(
            payload=exact_payload,
            response_schema=exact_schema,
            evidence_bundle=evidence_bundle,
            visible=visible,
            alias_receipt=alias_receipt,
        )
        if semantic_literals_covered_total != semantic_literals_total:
            _fail("financial_semantic_v6_context_lint_literal_missing")
        if duplicate_literals_total:
            _fail("financial_semantic_v6_context_lint_literal_duplicate")

        _validate_exact_option_coverage(
            visible=visible,
            payload=exact_payload,
            response_schema=exact_schema,
            alias_receipt=alias_receipt,
            choice_contract=choice_contract,
            compilation=compilation,
        )
        _validate_alias_receipt_integrity(
            alias_receipt=alias_receipt,
            packet=packet,
        )

        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "semantic_choice",
                "strict": True,
                "schema": copy.deepcopy(exact_schema),
            },
        }
        projection_prompt = _ProjectionPrompt(
            version=V6_SEMANTIC_PROMPT_VERSION,
            content=V6_SEMANTIC_SYSTEM_PROMPT,
            hash=V6_SEMANTIC_PROMPT_HASH,
            packet_hash=packet.slim_candidate.view_hash,
            choice_schema_hash=(
                choice_contract.local_candidate.response_schema_hash
            ),
        )
        projection = financial_semantic_v6_slim_model_visible_projection(
            prompt=projection_prompt,
            package=exact_payload,
            response_format=response_format,
        )
        opaque_ids_total = _opaque_ids_total(
            projection=projection,
            packet=packet,
            choice_contract=choice_contract,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            alias_receipt=alias_receipt,
        )
        if opaque_ids_total:
            _fail("financial_semantic_v6_context_lint_opaque_id")
        if (
            exact_payload != packet.slim_candidate.payload
            or sha256_json(exact_payload) != packet.slim_candidate.view_hash
            or exact_schema
            != choice_contract.local_candidate.response_schema
            or sha256_json(exact_schema)
            != choice_contract.local_candidate.response_schema_hash
        ):
            _fail("financial_semantic_v6_context_lint_authority_mismatch")

        draft_receipt = Gate2FinancialSemanticV6ContextLintReceipt(
            schema_version=(
                FINANCIAL_SEMANTIC_V6_CONTEXT_LINT_RECEIPT_SCHEMA_VERSION
            ),
            policy_version=FINANCIAL_SEMANTIC_V6_CONTEXT_LINT_POLICY_VERSION,
            status=FINANCIAL_SEMANTIC_V6_CONTEXT_LINT_PASSED,
            request_profile=(
                FINANCIAL_SEMANTIC_V6_SLIM_LINTED_REQUEST_PROFILE
            ),
            prompt_version=V6_SEMANTIC_PROMPT_VERSION,
            prompt_hash=V6_SEMANTIC_PROMPT_HASH,
            slim_view_hash=packet.slim_candidate.view_hash,
            local_choice_schema_hash=(
                choice_contract.local_candidate.response_schema_hash
            ),
            alias_receipt_integrity_hash=alias_receipt.integrity_hash,
            model_visible_request_hash=sha256_json(projection),
            model_visible_utf8_bytes=(
                financial_semantic_v6_model_visible_utf8_bytes(projection)
            ),
            token_estimator_id=TOKEN_ESTIMATOR_ID,
            estimated_input_tokens=(
                estimate_gate2_request_input_tokens(projection)
            ),
            semantic_literals_total=semantic_literals_total,
            semantic_literals_covered_total=(
                semantic_literals_covered_total
            ),
            duplicate_literals_total=duplicate_literals_total,
            null_fields_total=null_fields_total,
            opaque_ids_total=opaque_ids_total,
            unmapped_aliases_total=unmapped_aliases_total,
            orphan_aliases_total=orphan_aliases_total,
            alias_collisions_total=alias_collisions_total,
            structural_nodes_total=len(visible.structural_aliases),
            choices_total=len(visible.choice_aliases),
            semantic_literal_coverage_complete=True,
            structural_hierarchy_valid=True,
            exact_option_coverage=True,
            alias_receipt_integrity_valid=True,
            provider_calls_total=0,
            integrity_hash="",
        )
        receipt = replace(
            draft_receipt,
            integrity_hash=sha256_json(draft_receipt.integrity_payload()),
        )
        if receipt.token_estimator_id != (
            FINANCIAL_SEMANTIC_V6_CONTEXT_TOKEN_ESTIMATOR_ID
        ):
            _fail("financial_semantic_v6_context_lint_estimator_invalid")
        prompt = Gate2FinancialSemanticV6ContextLintedPrompt(
            version=V6_SEMANTIC_PROMPT_VERSION,
            content=V6_SEMANTIC_SYSTEM_PROMPT,
            hash=V6_SEMANTIC_PROMPT_HASH,
            packet_hash=packet.slim_candidate.view_hash,
            choice_schema_hash=(
                choice_contract.local_candidate.response_schema_hash
            ),
            context_lint_receipt=receipt,
        )
        canonical_request = Gate2OpenWebUIRequestBuilder(
            request_profile=(
                FINANCIAL_SEMANTIC_V6_SLIM_LINTED_REQUEST_PROFILE
            )
        ).build(
            prompt=prompt,
            package=exact_payload,
            model_id=exact_model_id,
            response_format=response_format,
        )
        if {
            "messages": canonical_request.get("messages"),
            "response_format": canonical_request.get("response_format"),
        } != projection:
            _fail("financial_semantic_v6_context_lint_request_drift")
        return Gate2FinancialSemanticV6LintedRequest(
            prompt=prompt,
            package=copy.deepcopy(exact_payload),
            response_format=copy.deepcopy(response_format),
            canonical_request=copy.deepcopy(canonical_request),
            lint_receipt=receipt,
        )

    def create_context_v2_1(
        self,
        *,
        packet: Gate2FinancialSemanticV6Packet,
        choice_contract: Gate2FinancialSemanticV6ChoiceContract,
        evidence_bundle: Gate2FinancialEvidenceBundle,
        source_package: Gate2FinancialEvidenceSourcePackage,
        compilation: Gate2FinancialCandidateCompilation,
        system_message: str,
        serialized_context: str,
        response_format: dict[str, Any],
        mapping_receipt: (
            Gate2FinancialSemanticV6ContextV21MappingReceipt
        ),
    ) -> Gate2FinancialSemanticV6ContextV21SealedRequest:
        validate_financial_semantic_v6_packet(
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            registry=self.registry,
        )
        validate_financial_semantic_v6_choice_contract(
            contract=choice_contract,
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            registry=self.registry,
        )
        candidate = packet.context_v2_candidate
        response_profile = (
            choice_contract.context_v2_1_response_profile
        )
        if (
            not isinstance(
                mapping_receipt,
                Gate2FinancialSemanticV6ContextV21MappingReceipt,
            )
            or mapping_receipt != packet.context_v2_mapping_receipt
            or mapping_receipt.provider_calls_total != 0
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "mapping_receipt_invalid"
            )
        if (
            candidate.active is not False
            or candidate.transport_eligible is not False
            or candidate.provider_calls_total != 0
            or response_profile.active is not False
            or response_profile.transport_eligible is not False
            or response_profile.provider_calls_total != 0
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "non_active_boundary_invalid"
            )
        expected_context = _model_json_text(candidate.payload)
        if (
            not isinstance(system_message, str)
            or system_message != V6_SEMANTIC_SYSTEM_PROMPT
            or sha256_json(system_message) != V6_SEMANTIC_PROMPT_HASH
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "system_message_invalid"
            )
        if (
            not isinstance(serialized_context, str)
            or serialized_context != expected_context
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "serialized_context_invalid"
            )
        exact_schema = copy.deepcopy(response_profile.response_schema)
        expected_response_format = {
            "type": "json_schema",
            "json_schema": {
                "strict": True,
                "schema": copy.deepcopy(exact_schema),
            },
        }
        if (
            not isinstance(response_format, dict)
            or response_format != expected_response_format
            or _model_json_bytes(response_format)
            != _model_json_bytes(expected_response_format)
            or response_profile.response_schema_hash
            != sha256_json(exact_schema)
            or response_profile.mapping_receipt_integrity_hash
            != mapping_receipt.integrity_hash
            or response_profile.context_view_hash != candidate.view_hash
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "response_format_invalid"
            )

        exact_response_format = copy.deepcopy(response_format)
        projection_prompt = _ProjectionPrompt(
            version=V6_SEMANTIC_PROMPT_VERSION,
            content=system_message,
            hash=V6_SEMANTIC_PROMPT_HASH,
            packet_hash=candidate.view_hash,
            choice_schema_hash=response_profile.response_schema_hash,
        )
        model_visible_request = (
            financial_semantic_v6_slim_model_visible_projection(
                prompt=projection_prompt,
                package=copy.deepcopy(candidate.payload),
                response_format=copy.deepcopy(exact_response_format),
            )
        )
        if (
            model_visible_request["messages"][1]["content"]
            != serialized_context
            or model_visible_request["response_format"]
            != exact_response_format
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "request_projection_drift"
            )
        model_visible_utf8_bytes = (
            validate_financial_semantic_v6_context_v2_1_request_budget(
                model_visible_request
            )
        )
        opaque_global_ids = _context_v2_1_opaque_global_ids_total(
            model_visible_request=model_visible_request,
            packet=packet,
            choice_contract=choice_contract,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            mapping_receipt=mapping_receipt,
            registry=self.registry,
        )
        backend_hashes = _context_v2_1_backend_hashes_total(
            model_visible_request=model_visible_request,
            packet=packet,
            choice_contract=choice_contract,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            mapping_receipt=mapping_receipt,
            registry=self.registry,
        )
        (
            semantic_literals_total,
            semantic_literals_covered_total,
            duplicate_literals,
        ) = _context_v2_1_semantic_literal_metrics(
            system_message=system_message,
            payload=candidate.payload,
            response_format=exact_response_format,
            evidence_bundle=evidence_bundle,
            mapping_receipt=mapping_receipt,
        )
        null_fields = _count_nulls(
            {
                "system_message": system_message,
                "payload": candidate.payload,
                "response_format": exact_response_format,
            }
        )
        unused_or_orphan_keys = (
            _context_v2_1_unused_or_orphan_keys_total(
                payload=candidate.payload,
                response_schema=exact_schema,
            )
        )
        unexplained_reason_codes = (
            _context_v2_1_unexplained_reason_codes_total(
                payload=candidate.payload,
                response_schema=exact_schema,
                expected_reason_codes=(
                    response_profile.unclassified_reason_codes
                ),
            )
        )
        (
            mapping_rows_total,
            mapping_rows_covered_total,
        ) = _context_v2_1_mapping_coverage_metrics(
            payload=candidate.payload,
            mapping_receipt=mapping_receipt,
            evidence_bundle=evidence_bundle,
            compilation=compilation,
        )
        invariant_counters = {
            "opaque_global_ids": opaque_global_ids,
            "backend_hashes": backend_hashes,
            "duplicate_literals": duplicate_literals,
            "null_fields": null_fields,
            "unused_or_orphan_keys": unused_or_orphan_keys,
            "unexplained_reason_codes": unexplained_reason_codes,
            "semantic_literals_total": semantic_literals_total,
            "semantic_literals_covered_total": (
                semantic_literals_covered_total
            ),
            "mapping_rows_total": mapping_rows_total,
            "mapping_rows_covered_total": (
                mapping_rows_covered_total
            ),
        }
        if opaque_global_ids:
            _fail(
                "financial_semantic_v6_context_v2_1_opaque_global_id"
            )
        if backend_hashes:
            _fail("financial_semantic_v6_context_v2_1_backend_hash")
        if duplicate_literals:
            _fail("financial_semantic_v6_context_v2_1_literal_duplicate")
        if null_fields:
            _fail("financial_semantic_v6_context_v2_1_null_field")
        if unused_or_orphan_keys:
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "unused_or_orphan_key"
            )
        if unexplained_reason_codes:
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "unexplained_reason_code"
            )
        if semantic_literals_covered_total != semantic_literals_total:
            _fail("financial_semantic_v6_context_v2_1_literal_missing")
        if mapping_rows_covered_total != mapping_rows_total:
            _fail("financial_semantic_v6_context_v2_1_mapping_incomplete")

        draft_receipt = (
            Gate2FinancialSemanticV6ContextV21SealedRequestReceipt(
                schema_version=(
                    CONTEXT_V2_1_SEALED_REQUEST_RECEIPT_SCHEMA_VERSION
                ),
                policy_version=CONTEXT_V2_1_POLICY_VERSION,
                request_profile=CONTEXT_V2_1_SEALED_REQUEST_PROFILE,
                mapping_receipt_integrity_hash=(
                    mapping_receipt.integrity_hash
                ),
                context_view_hash=candidate.view_hash,
                system_prompt_version=V6_SEMANTIC_PROMPT_VERSION,
                system_prompt_hash=V6_SEMANTIC_PROMPT_HASH,
                local_response_profile_identity=(
                    response_profile.schema_version
                ),
                response_schema_hash=(
                    response_profile.response_schema_hash
                ),
                response_format_hash=_model_hash(
                    exact_response_format
                ),
                model_visible_request_hash=_model_hash(
                    model_visible_request
                ),
                model_visible_utf8_bytes=model_visible_utf8_bytes,
                token_estimator_id=TOKEN_ESTIMATOR_ID,
                estimated_input_tokens=(
                    estimate_gate2_request_input_tokens(
                        model_visible_request
                    )
                ),
                invariant_counters=copy.deepcopy(invariant_counters),
                status=CONTEXT_V2_1_SEALED_REQUEST_STATUS_PASSED,
                provider_calls_total=0,
                integrity_hash="",
            )
        )
        receipt = replace(
            draft_receipt,
            integrity_hash=sha256_json(
                draft_receipt.integrity_payload()
            ),
        )
        return Gate2FinancialSemanticV6ContextV21SealedRequest(
            active=False,
            transport_eligible=False,
            serialized_context=serialized_context,
            response_format=copy.deepcopy(exact_response_format),
            model_visible_request=copy.deepcopy(model_visible_request),
            sealed_request_receipt=receipt,
        )

    def create_type_first(
        self,
        *,
        packet: Gate2FinancialSemanticV6Packet,
        choice_contract: Gate2FinancialSemanticV6ChoiceContract,
        type_first_candidate: (
            Gate2FinancialSemanticV6TypeFirstCandidate
        ),
        response_profile: (
            Gate2FinancialSemanticV6TypeFirstResponseProfile
        ),
        evidence_bundle: Gate2FinancialEvidenceBundle,
        source_package: Gate2FinancialEvidenceSourcePackage,
        compilation: Gate2FinancialCandidateCompilation,
        system_message: str,
        serialized_context: str,
        response_format: dict[str, Any],
        mapping_receipt: (
            Gate2FinancialSemanticV6TypeFirstMappingReceipt
        ),
    ) -> Gate2FinancialSemanticV6TypeFirstSealedRequest:
        try:
            validate_financial_semantic_v6_type_first_response_profile(
                profile=response_profile,
                type_first_candidate=type_first_candidate,
                mapping_receipt=mapping_receipt,
                choice_contract=choice_contract,
                packet=packet,
                evidence_bundle=evidence_bundle,
                source_package=source_package,
                compilation=compilation,
                registry=self.registry,
            )
        except Gate2FinancialSemanticV6ChoiceError as exc:
            raise Gate2FinancialSemanticV6ContextLintError(
                exc.code
            ) from exc
        if (
            not isinstance(system_message, str)
            or system_message != V6_SEMANTIC_SYSTEM_PROMPT
            or sha256_json(system_message) != V6_SEMANTIC_PROMPT_HASH
        ):
            _fail("context_profile_schema_hash_mismatch")
        expected_context = _model_json_text(
            type_first_candidate.payload
        )
        if (
            not isinstance(serialized_context, str)
            or serialized_context != expected_context
        ):
            _fail("source_hash_drift")
        exact_schema = response_profile.canonical_schema()
        expected_response_format = {
            "type": "json_schema",
            "json_schema": {
                "strict": True,
                "schema": copy.deepcopy(exact_schema),
            },
        }
        if (
            not isinstance(response_format, dict)
            or response_format != expected_response_format
            or response_profile.response_schema_sha256
            != sha256_json(exact_schema)
        ):
            _fail("context_profile_schema_hash_mismatch")
        logical_request = {
            "response_schema": copy.deepcopy(exact_schema),
            "user_context": copy.deepcopy(
                type_first_candidate.payload
            ),
        }
        logical_request_bytes = _model_json_bytes(logical_request)
        validate_financial_semantic_v6_type_first_logical_request_budget(
            response_schema=exact_schema,
            user_context=type_first_candidate.payload,
        )
        projection_prompt = _ProjectionPrompt(
            version=V6_SEMANTIC_PROMPT_VERSION,
            content=system_message,
            hash=V6_SEMANTIC_PROMPT_HASH,
            packet_hash=type_first_candidate.context_view_sha256,
            choice_schema_hash=(
                response_profile.response_schema_sha256
            ),
        )
        model_visible_request = (
            financial_semantic_v6_slim_model_visible_projection(
                prompt=projection_prompt,
                package=copy.deepcopy(
                    type_first_candidate.payload
                ),
                response_format=copy.deepcopy(response_format),
            )
        )
        if (
            tuple(model_visible_request) != (
                "messages",
                "response_format",
            )
            or model_visible_request["messages"]
            != [
                {"role": "system", "content": system_message},
                {"role": "user", "content": serialized_context},
            ]
            or model_visible_request["response_format"]
            != response_format
        ):
            _fail("context_profile_schema_hash_mismatch")
        private_literals = {
            *mapping_receipt.local_to_canonical_type_ids.values(),
            *(item.typed_option_id for item in compilation.typed_options),
            packet.packet_hash,
            evidence_bundle.integrity_hash,
            compilation.integrity_hash,
            mapping_receipt.integrity_sha256,
        }
        visible_strings = tuple(
            _walk_strings(model_visible_request)
        )
        invariant_counters = {
            "model_visible_root_fields_total": len(
                type_first_candidate.payload
            ),
            "visible_type_cards_total": len(
                type_first_candidate.payload["type_cards"]
            ),
            "mapping_rows_total": len(
                mapping_receipt.local_to_canonical_type_ids
            ),
            "mapping_rows_covered_total": sum(
                item in mapping_receipt.local_to_canonical_type_ids
                for item in response_profile.type_keys
            ),
            "null_fields": _count_nulls(model_visible_request),
            "forbidden_fields": sum(
                len(TYPE_FIRST_FORBIDDEN_FIELDS.intersection(item))
                for item in _walk_dicts_local(model_visible_request)
            ),
            "private_identity_literals": sum(
                item in private_literals for item in visible_strings
            ),
        }
        if (
            invariant_counters["model_visible_root_fields_total"]
            != len(TYPE_FIRST_BLOCKS)
            or tuple(type_first_candidate.payload)
            != TYPE_FIRST_BLOCKS
            or type_first_candidate.payload["task"] != TYPE_FIRST_TASK
            or invariant_counters["visible_type_cards_total"]
            != invariant_counters["mapping_rows_total"]
            or invariant_counters["mapping_rows_total"]
            != invariant_counters["mapping_rows_covered_total"]
            or invariant_counters["null_fields"] != 0
            or invariant_counters["forbidden_fields"] != 0
            or invariant_counters["private_identity_literals"] != 0
        ):
            _fail("mapping_receipt_mismatch")
        draft = Gate2FinancialSemanticV6TypeFirstSealedRequestReceipt(
            schema_version=(
                TYPE_FIRST_SEALED_REQUEST_RECEIPT_SCHEMA_VERSION
            ),
            policy_version=TYPE_FIRST_DECISION_POLICY_VERSION,
            request_profile=TYPE_FIRST_LOCAL_PROOF_REQUEST_PROFILE,
            context_profile=TYPE_FIRST_CONTEXT_PROFILE,
            context_view_sha256=(
                type_first_candidate.context_view_sha256
            ),
            source_projection_sha256=(
                type_first_candidate.source_projection_sha256
            ),
            response_profile=response_profile.schema_version,
            response_schema_sha256=(
                response_profile.response_schema_sha256
            ),
            system_prompt_version=V6_SEMANTIC_PROMPT_VERSION,
            system_prompt_sha256=V6_SEMANTIC_PROMPT_HASH,
            mapping_receipt_integrity_sha256=(
                mapping_receipt.integrity_sha256
            ),
            logical_request_sha256=hashlib.sha256(
                logical_request_bytes
            ).hexdigest(),
            logical_request_utf8_bytes=len(logical_request_bytes),
            model_visible_request_sha256=_model_hash(
                model_visible_request
            ),
            model_visible_request_utf8_bytes=len(
                _model_json_bytes(model_visible_request)
            ),
            token_estimator_id=TOKEN_ESTIMATOR_ID,
            estimated_input_tokens=estimate_gate2_request_input_tokens(
                model_visible_request
            ),
            invariant_counters=copy.deepcopy(invariant_counters),
            status=TYPE_FIRST_SEALED_REQUEST_STATUS_PASSED,
            provider_calls_total=0,
            integrity_sha256="",
        )
        receipt = replace(
            draft,
            integrity_sha256=sha256_json(
                draft.integrity_payload()
            ),
        )
        return Gate2FinancialSemanticV6TypeFirstSealedRequest(
            active=False,
            transport_eligible=False,
            serialized_context=serialized_context,
            response_format=copy.deepcopy(response_format),
            model_visible_request=copy.deepcopy(
                model_visible_request
            ),
            sealed_request_receipt=receipt,
            _request_builder_seal=(
                _issue_type_first_request_builder_seal(
                    receipt=receipt
                )
            ),
        )

    def prove_local_totality(
        self,
        *,
        linted_request: Gate2FinancialSemanticV6LintedRequest,
        packet: Gate2FinancialSemanticV6Packet,
        choice_contract: Gate2FinancialSemanticV6ChoiceContract,
        evidence_bundle: Gate2FinancialEvidenceBundle,
        source_package: Gate2FinancialEvidenceSourcePackage,
        compilation: Gate2FinancialCandidateCompilation,
    ) -> Gate2FinancialSemanticV6ContextTotalityReceipt:
        validate_financial_semantic_v6_linted_request(
            linted_request=linted_request,
            packet=packet,
            choice_contract=choice_contract,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            registry=self.registry,
        )
        local_outputs = [
            {"choice": alias}
            for alias in choice_contract.local_candidate.choice_aliases
        ]
        local_outputs.extend(
            {
                "choice": "unclassified",
                "reason": reason,
            }
            for reason in (
                choice_contract.local_candidate.unclassified_reason_codes
            )
        )
        outcome_hashes: list[str] = []
        typed_outputs_total = 0
        unclassified_outputs_total = 0
        validated_but_unmaterializable_total = 0
        expansion_factory = Gate2FinancialSemanticV6DecisionExpansionFactory(
            registry=self.registry
        )
        totality_factory = Gate2FinancialSemanticV6TotalMaterializerFactory(
            registry=self.registry
        )
        for local_output in local_outputs:
            canonical_choice = normalize_financial_semantic_v6_local_choice(
                model_output=local_output,
                choice_contract=choice_contract,
                packet=packet,
            )
            expansion = expansion_factory.create_from_local_candidate(
                model_output=local_output,
                choice_contract=choice_contract,
                packet=packet,
                evidence_bundle=evidence_bundle,
                source_package=source_package,
                compilation=compilation,
            )
            total = totality_factory.create(
                expansion=expansion,
                model_output=canonical_choice,
                choice_contract=choice_contract,
                packet=packet,
                evidence_bundle=evidence_bundle,
                source_package=source_package,
                compilation=compilation,
            )
            if canonical_choice["disposition"] == "typed_input":
                typed_outputs_total += 1
            else:
                unclassified_outputs_total += 1
            validated_but_unmaterializable_total += int(
                total.validated_but_unmaterializable
            )
            outcome_hashes.append(
                sha256_json(
                    {
                        "local_output_hash": sha256_json(local_output),
                        "canonical_choice_hash": sha256_json(
                            canonical_choice
                        ),
                        "expansion_integrity_hash": expansion.integrity_hash,
                        "totality_integrity_hash": total.integrity_hash,
                        "canonical_artifact_hash": (
                            total.canonical_artifact_hash
                        ),
                    }
                )
            )
        if (
            not local_outputs
            or validated_but_unmaterializable_total
            or len(outcome_hashes) != len(local_outputs)
        ):
            _fail("financial_semantic_v6_context_totality_failed")
        draft = Gate2FinancialSemanticV6ContextTotalityReceipt(
            schema_version=CONTEXT_LINT_TOTALITY_SCHEMA_VERSION,
            policy_version=CONTEXT_LINT_TOTALITY_POLICY_VERSION,
            lint_receipt_integrity_hash=(
                linted_request.lint_receipt.integrity_hash
            ),
            exact_replay=True,
            local_outputs_total=len(local_outputs),
            typed_outputs_total=typed_outputs_total,
            unclassified_outputs_total=unclassified_outputs_total,
            total_materializations_total=len(outcome_hashes),
            validated_but_unmaterializable_total=0,
            outcome_integrity_hashes=tuple(outcome_hashes),
            provider_calls_total=0,
            integrity_hash="",
        )
        return replace(
            draft,
            integrity_hash=sha256_json(draft.integrity_payload()),
        )


@dataclass(frozen=True)
class _ProjectionPrompt:
    version: str
    content: str
    hash: str
    packet_hash: str
    choice_schema_hash: str


def validate_financial_semantic_v6_linted_request(
    *,
    linted_request: Gate2FinancialSemanticV6LintedRequest,
    packet: Gate2FinancialSemanticV6Packet,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    compilation: Gate2FinancialCandidateCompilation,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> None:
    if not isinstance(
        linted_request,
        Gate2FinancialSemanticV6LintedRequest,
    ):
        _fail("financial_semantic_v6_context_lint_replay_invalid")
    try:
        exact_model_id = linted_request.canonical_request["model"]
        response_schema = linted_request.response_format["json_schema"][
            "schema"
        ]
    except (KeyError, TypeError) as exc:
        raise Gate2FinancialSemanticV6ContextLintError(
            "financial_semantic_v6_context_lint_replay_invalid"
        ) from exc
    replayed = Gate2FinancialSemanticV6ContextLinterFactory(
        registry=registry
    ).create(
        packet=packet,
        choice_contract=choice_contract,
        evidence_bundle=evidence_bundle,
        source_package=source_package,
        compilation=compilation,
        candidate_payload=linted_request.package,
        response_schema=response_schema,
        alias_receipt=packet.slim_alias_receipt,
        exact_model_id=exact_model_id,
    )
    if replayed != linted_request:
        _fail("financial_semantic_v6_context_lint_replay_mismatch")


def validate_financial_semantic_v6_context_v2_1_request_budget(
    model_visible_request: dict[str, Any],
) -> int:
    if not isinstance(model_visible_request, dict):
        _fail(
            "financial_semantic_v6_context_v2_1_request_budget_invalid"
        )
    model_visible_utf8_bytes = len(
        _model_json_bytes(model_visible_request)
    )
    if (
        model_visible_utf8_bytes
        > CONTEXT_V2_1_SEALED_REQUEST_MAX_UTF8_BYTES
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_request_budget_exceeded"
        )
    return model_visible_utf8_bytes


def validate_financial_semantic_v6_type_first_logical_request_budget(
    *,
    response_schema: dict[str, Any],
    user_context: dict[str, Any],
) -> int:
    if (
        not isinstance(response_schema, dict)
        or not isinstance(user_context, dict)
    ):
        _fail("type_first_logical_request_budget_invalid")
    logical_request_utf8_bytes = len(
        _model_json_bytes(
            {
                "response_schema": copy.deepcopy(response_schema),
                "user_context": copy.deepcopy(user_context),
            }
        )
    )
    if (
        logical_request_utf8_bytes
        > TYPE_FIRST_LOGICAL_REQUEST_MAX_UTF8_BYTES
    ):
        _fail("type_first_logical_request_budget_exceeded")
    return logical_request_utf8_bytes


def validate_financial_semantic_v6_context_v2_1_sealed_request(
    *,
    sealed_request: (
        Gate2FinancialSemanticV6ContextV21SealedRequest
    ),
    packet: Gate2FinancialSemanticV6Packet,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    compilation: Gate2FinancialCandidateCompilation,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    system_message: str,
    mapping_receipt: Gate2FinancialSemanticV6ContextV21MappingReceipt,
) -> None:
    if not isinstance(
        sealed_request,
        Gate2FinancialSemanticV6ContextV21SealedRequest,
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_sealed_replay_invalid"
        )
    validate_financial_semantic_v6_context_v2_1_request_budget(
        sealed_request.model_visible_request
    )
    replayed = Gate2FinancialSemanticV6ContextLinterFactory(
        registry=registry
    ).create_context_v2_1(
        packet=packet,
        choice_contract=choice_contract,
        evidence_bundle=evidence_bundle,
        source_package=source_package,
        compilation=compilation,
        system_message=system_message,
        serialized_context=sealed_request.serialized_context,
        response_format=sealed_request.response_format,
        mapping_receipt=mapping_receipt,
    )
    if (
        _model_json_bytes(replayed.model_visible_request)
        != _model_json_bytes(sealed_request.model_visible_request)
        or replayed != sealed_request
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_sealed_replay_mismatch"
        )


def validate_financial_semantic_v6_type_first_sealed_request(
    *,
    sealed_request: Gate2FinancialSemanticV6TypeFirstSealedRequest,
    packet: Gate2FinancialSemanticV6Packet,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    type_first_candidate: Gate2FinancialSemanticV6TypeFirstCandidate,
    response_profile: Gate2FinancialSemanticV6TypeFirstResponseProfile,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    compilation: Gate2FinancialCandidateCompilation,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    system_message: str,
    mapping_receipt: Gate2FinancialSemanticV6TypeFirstMappingReceipt,
) -> None:
    if not isinstance(
        sealed_request,
        Gate2FinancialSemanticV6TypeFirstSealedRequest,
    ):
        _fail("type_first_sealed_replay_invalid")
    receipt = sealed_request.sealed_request_receipt
    if not isinstance(
        receipt,
        Gate2FinancialSemanticV6TypeFirstSealedRequestReceipt,
    ):
        _fail("type_first_sealed_replay_invalid")
    if (
        sealed_request.active is not False
        or sealed_request.transport_eligible is not False
        or receipt.schema_version
        != TYPE_FIRST_SEALED_REQUEST_RECEIPT_SCHEMA_VERSION
        or receipt.policy_version != TYPE_FIRST_DECISION_POLICY_VERSION
        or receipt.request_profile
        != TYPE_FIRST_LOCAL_PROOF_REQUEST_PROFILE
        or receipt.context_profile != TYPE_FIRST_CONTEXT_PROFILE
        or receipt.response_profile != response_profile.schema_version
        or receipt.system_prompt_version != V6_SEMANTIC_PROMPT_VERSION
        or receipt.system_prompt_sha256 != V6_SEMANTIC_PROMPT_HASH
        or receipt.status != TYPE_FIRST_SEALED_REQUEST_STATUS_PASSED
        or receipt.provider_calls_total != 0
        or receipt.integrity_sha256
        != sha256_json(receipt.integrity_payload())
    ):
        _fail("type_first_sealed_replay_invalid")
    if (
        receipt.context_view_sha256
        != type_first_candidate.context_view_sha256
        or receipt.source_projection_sha256
        != type_first_candidate.source_projection_sha256
    ):
        _fail("source_hash_drift")
    if (
        receipt.mapping_receipt_integrity_sha256
        != mapping_receipt.integrity_sha256
    ):
        _fail("mapping_receipt_mismatch")
    logical_request_bytes = _model_json_bytes(
        {
            "response_schema": response_profile.canonical_schema(),
            "user_context": copy.deepcopy(type_first_candidate.payload),
        }
    )
    validate_financial_semantic_v6_type_first_logical_request_budget(
        response_schema=response_profile.canonical_schema(),
        user_context=type_first_candidate.payload,
    )
    if (
        receipt.response_schema_sha256
        != response_profile.response_schema_sha256
        or receipt.logical_request_sha256
        != hashlib.sha256(logical_request_bytes).hexdigest()
        or receipt.logical_request_utf8_bytes
        != len(logical_request_bytes)
        or receipt.model_visible_request_sha256
        != _model_hash(sealed_request.model_visible_request)
        or receipt.model_visible_request_utf8_bytes
        != len(_model_json_bytes(sealed_request.model_visible_request))
    ):
        _fail("type_first_sealed_replay_mismatch")
    replayed = Gate2FinancialSemanticV6ContextLinterFactory(
        registry=registry
    ).create_type_first(
        packet=packet,
        choice_contract=choice_contract,
        type_first_candidate=type_first_candidate,
        response_profile=response_profile,
        evidence_bundle=evidence_bundle,
        source_package=source_package,
        compilation=compilation,
        system_message=system_message,
        serialized_context=sealed_request.serialized_context,
        response_format=sealed_request.response_format,
        mapping_receipt=mapping_receipt,
    )
    if (
        _model_json_bytes(replayed.model_visible_request)
        != _model_json_bytes(sealed_request.model_visible_request)
        or replayed != sealed_request
    ):
        _fail("type_first_sealed_replay_mismatch")


def _validate_visible_context(payload: Any) -> _VisibleContext:
    if (
        not isinstance(payload, dict)
        or tuple(payload) != SLIM_VIEW_BLOCKS
        or payload.get("task") != SEMANTIC_PACKET_AMBIGUITY_RULE
        or payload.get("unclassified")
        != list(SLIM_VIEW_UNCLASSIFIED_REASONS)
        or not isinstance(payload.get("source"), dict)
        or set(payload["source"]) != {"document"}
        or not isinstance(payload["source"]["document"], dict)
        or set(payload["source"]["document"]) != {"children"}
        or not isinstance(
            payload["source"]["document"]["children"],
            list,
        )
        or not payload["source"]["document"]["children"]
    ):
        _fail("financial_semantic_v6_context_lint_shape_invalid")

    structural_aliases: list[str] = []
    value_records: list[dict[str, Any]] = []

    def walk_node(node: Any, parent_kind: str) -> None:
        if (
            not isinstance(node, dict)
            or not {"alias", "kind"}.issubset(node)
            or not set(node).issubset(_STRUCTURAL_FIELDS)
            or node["kind"] not in _STRUCTURAL_KINDS
            or node["kind"] not in _ALLOWED_CHILDREN[parent_kind]
            or not isinstance(node["alias"], str)
            or _ALIAS_PATTERNS[node["kind"]].fullmatch(node["alias"])
            is None
        ):
            _fail("financial_semantic_v6_context_lint_hierarchy_invalid")
        for optional in ("label", "section_role", "row_role"):
            if optional in node and (
                not isinstance(node[optional], str) or not node[optional]
            ):
                _fail("financial_semantic_v6_context_lint_hierarchy_invalid")
        structural_aliases.append(node["alias"])
        children = node.get("children")
        values = node.get("values")
        if children is not None:
            if not isinstance(children, list) or not children:
                _fail("financial_semantic_v6_context_lint_hierarchy_invalid")
            for child in children:
                walk_node(child, node["kind"])
        if values is not None:
            if not isinstance(values, list) or not values:
                _fail("financial_semantic_v6_context_lint_hierarchy_invalid")
            for value in values:
                if (
                    not isinstance(value, dict)
                    or set(value)
                    not in (
                        {"alias", "meaning", "value", "type"},
                        {"alias", "meaning", "value", "type", "label"},
                    )
                    or not set(value).issubset(_VALUE_FIELDS)
                    or not all(
                        isinstance(value[field], str) and value[field]
                        for field in ("alias", "meaning", "value", "type")
                    )
                    or _ALIAS_PATTERNS["value"].fullmatch(value["alias"])
                    is None
                    or (
                        "label" in value
                        and (
                            not isinstance(value["label"], str)
                            or not value["label"]
                        )
                    )
                ):
                    _fail(
                        "financial_semantic_v6_context_lint_value_invalid"
                    )
                value_records.append(copy.deepcopy(value))
        if children is None and values is None:
            _fail("financial_semantic_v6_context_lint_hierarchy_invalid")

    for child in payload["source"]["document"]["children"]:
        walk_node(child, "document")

    type_cards = payload.get("type_cards")
    if not isinstance(type_cards, list):
        _fail("financial_semantic_v6_context_lint_type_card_invalid")
    type_aliases: list[str] = []
    for card in type_cards:
        if (
            not isinstance(card, dict)
            or set(card) != _TYPE_CARD_FIELDS
            or not all(
                isinstance(card[field], str) and card[field]
                for field in ("alias", "meaning", "unclassified_when")
            )
            or _ALIAS_PATTERNS["type"].fullmatch(card["alias"]) is None
            or not isinstance(card["distinctions"], list)
        ):
            _fail("financial_semantic_v6_context_lint_type_card_invalid")
        for distinction in card["distinctions"]:
            if (
                not isinstance(distinction, dict)
                or set(distinction) != _DISTINCTION_FIELDS
                or not all(
                    isinstance(distinction[field], str)
                    and distinction[field]
                    for field in _DISTINCTION_FIELDS
                )
            ):
                _fail(
                    "financial_semantic_v6_context_lint_type_card_invalid"
                )
        type_aliases.append(card["alias"])

    choices = payload.get("choices")
    if not isinstance(choices, list):
        _fail("financial_semantic_v6_context_lint_choice_invalid")
    choice_aliases: list[str] = []
    choice_type_aliases: list[str] = []
    binding_aliases: list[str] = []
    for choice in choices:
        if (
            not isinstance(choice, dict)
            or set(choice) != _CHOICE_FIELDS
            or not isinstance(choice["alias"], str)
            or _ALIAS_PATTERNS["choice"].fullmatch(choice["alias"]) is None
            or not isinstance(choice["type"], str)
            or not isinstance(choice["bindings"], list)
        ):
            _fail("financial_semantic_v6_context_lint_choice_invalid")
        for binding in choice["bindings"]:
            if (
                not isinstance(binding, str)
                or binding.count("=") != 1
                or not all(binding.split("=", 1))
            ):
                _fail("financial_semantic_v6_context_lint_binding_invalid")
            binding_aliases.append(binding.split("=", 1)[1])
        choice_aliases.append(choice["alias"])
        choice_type_aliases.append(choice["type"])

    return _VisibleContext(
        structural_aliases=tuple(structural_aliases),
        value_records=tuple(value_records),
        type_aliases=tuple(type_aliases),
        choice_aliases=tuple(choice_aliases),
        choice_type_aliases=tuple(choice_type_aliases),
        binding_aliases=tuple(binding_aliases),
    )


def _alias_metrics(
    *,
    visible: _VisibleContext,
    alias_receipt: Gate2FinancialSemanticV6SlimAliasReceipt,
) -> tuple[int, int, int]:
    visible_value_aliases = tuple(
        item["alias"] for item in visible.value_records
    )
    visible_namespaces = (
        visible.structural_aliases,
        visible_value_aliases,
        visible.type_aliases,
        visible.choice_aliases,
    )
    collisions = sum(
        len(items) - len(set(items)) for items in visible_namespaces
    )
    flattened = tuple(
        alias for namespace in visible_namespaces for alias in namespace
    )
    collisions += len(flattened) - len(set(flattened))
    receipt_namespaces = (
        tuple(alias_receipt.structural_aliases),
        tuple(alias_receipt.value_aliases),
        tuple(alias_receipt.type_aliases),
        tuple(alias_receipt.choice_aliases),
    )
    flattened_receipt = tuple(
        alias for namespace in receipt_namespaces for alias in namespace
    )
    collisions += len(flattened_receipt) - len(set(flattened_receipt))
    for mapping in (
        alias_receipt.value_aliases,
        alias_receipt.type_aliases,
        alias_receipt.choice_aliases,
    ):
        collisions += len(mapping) - len(set(mapping.values()))

    visible_structural = set(visible.structural_aliases)
    visible_values = set(visible_value_aliases)
    visible_types = set(visible.type_aliases)
    visible_choices = set(visible.choice_aliases)
    binding_targets = set(visible.binding_aliases)
    unmapped = sum(
        (
            len(visible_structural - set(alias_receipt.structural_aliases)),
            len(visible_values - set(alias_receipt.value_aliases)),
            len(visible_types - set(alias_receipt.type_aliases)),
            len(visible_choices - set(alias_receipt.choice_aliases)),
            len(binding_targets - (visible_structural | visible_values)),
            len(set(visible.choice_type_aliases) - visible_types),
        )
    )
    orphan = sum(
        (
            len(set(alias_receipt.structural_aliases) - visible_structural),
            len(set(alias_receipt.value_aliases) - visible_values),
            len(set(alias_receipt.type_aliases) - visible_types),
            len(set(alias_receipt.choice_aliases) - visible_choices),
            len(
                set(alias_receipt.evidence_only_aliases.values())
                - visible_structural
            ),
            len(
                set(alias_receipt.choice_role_bindings)
                - visible_choices
            ),
        )
    )
    return collisions, unmapped, orphan


def _semantic_literal_metrics(
    *,
    payload: dict[str, Any],
    response_schema: dict[str, Any],
    evidence_bundle: Gate2FinancialEvidenceBundle,
    visible: _VisibleContext,
    alias_receipt: Gate2FinancialSemanticV6SlimAliasReceipt,
) -> tuple[int, int, int]:
    semantic_values = tuple(
        value
        for value in evidence_bundle.source_values
        if value.value_type != "source_reference"
    )
    if not semantic_values:
        _fail("financial_semantic_v6_context_lint_literal_set_empty")
    values_by_ref = {
        value.source_value_ref: value for value in semantic_values
    }
    rendered_by_alias = {
        item["alias"]: item for item in visible.value_records
    }
    for alias, source_value_ref in alias_receipt.value_aliases.items():
        source = values_by_ref.get(source_value_ref)
        rendered = rendered_by_alias.get(alias)
        if source is None or rendered is None or (
            rendered["value"] != source.literal_value
        ):
            _fail("financial_semantic_v6_context_lint_literal_mapping_invalid")

    expected = Counter(value.literal_value for value in semantic_values)
    observed = Counter(
        value
        for value in _walk_strings(
            {
                "prompt": V6_SEMANTIC_SYSTEM_PROMPT,
                "payload": payload,
                "response_schema": response_schema,
            }
        )
        if value in expected
    )
    covered = sum(
        min(observed[literal], count)
        for literal, count in expected.items()
    )
    duplicates = sum(
        max(0, observed[literal] - count)
        for literal, count in expected.items()
    )
    return sum(expected.values()), covered, duplicates


def _validate_exact_option_coverage(
    *,
    visible: _VisibleContext,
    payload: dict[str, Any],
    response_schema: dict[str, Any],
    alias_receipt: Gate2FinancialSemanticV6SlimAliasReceipt,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    compilation: Gate2FinancialCandidateCompilation,
) -> None:
    if (
        response_schema
        != choice_contract.local_candidate.response_schema
        or tuple(visible.choice_aliases)
        != choice_contract.local_candidate.choice_aliases
        or tuple(visible.choice_aliases)
        != tuple(alias_receipt.choice_aliases)
        or set(alias_receipt.choice_aliases.values())
        != {
            option.typed_option_id for option in compilation.typed_options
        }
        or tuple(visible.type_aliases) != tuple(alias_receipt.type_aliases)
        or set(alias_receipt.type_aliases.values())
        != {
            option.input_type_id for option in compilation.typed_options
        }
        or payload["unclassified"]
        != list(choice_contract.local_candidate.unclassified_reason_codes)
    ):
        _fail("financial_semantic_v6_context_lint_option_coverage_invalid")

    options_by_id = {
        option.typed_option_id: option
        for option in compilation.typed_options
    }
    alias_by_source_ref = {
        source_value_ref: alias
        for alias, source_value_ref in alias_receipt.value_aliases.items()
    }
    alias_by_source_ref.update(alias_receipt.evidence_only_aliases)
    type_alias_by_id = {
        input_type_id: alias
        for alias, input_type_id in alias_receipt.type_aliases.items()
    }
    for choice in payload["choices"]:
        option_id = alias_receipt.choice_aliases.get(choice["alias"])
        option = options_by_id.get(option_id)
        if option is None:
            _fail(
                "financial_semantic_v6_context_lint_option_coverage_invalid"
            )
        try:
            expected_bindings = [
                (
                    f"{binding.role_id}="
                    f"{alias_by_source_ref[binding.source_value_ref]}"
                )
                for binding in option.role_bindings
            ]
            expected_type = type_alias_by_id[option.input_type_id]
        except KeyError as exc:
            raise Gate2FinancialSemanticV6ContextLintError(
                "financial_semantic_v6_context_lint_option_coverage_invalid"
            ) from exc
        if (
            choice["type"] != expected_type
            or choice["bindings"] != expected_bindings
            or alias_receipt.choice_role_bindings.get(choice["alias"])
            != [
                {
                    "role_id": binding.role_id,
                    "source_value_ref": binding.source_value_ref,
                }
                for binding in option.role_bindings
            ]
        ):
            _fail(
                "financial_semantic_v6_context_lint_option_coverage_invalid"
            )


def _validate_alias_receipt_integrity(
    *,
    alias_receipt: Gate2FinancialSemanticV6SlimAliasReceipt,
    packet: Gate2FinancialSemanticV6Packet,
) -> None:
    material = alias_receipt.to_private_dict()
    integrity_hash = material.pop("integrity_hash", None)
    if (
        alias_receipt != packet.slim_alias_receipt
        or integrity_hash != sha256_json(material)
        or alias_receipt.slim_view_hash != packet.slim_candidate.view_hash
        or alias_receipt.active_packet_hash != packet.packet_hash
        or alias_receipt.provider_calls_total != 0
    ):
        _fail("financial_semantic_v6_context_lint_receipt_integrity_invalid")


def _opaque_ids_total(
    *,
    projection: dict[str, Any],
    packet: Gate2FinancialSemanticV6Packet,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    compilation: Gate2FinancialCandidateCompilation,
    alias_receipt: Gate2FinancialSemanticV6SlimAliasReceipt,
) -> int:
    serialized = json.dumps(
        projection,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    opaque_values = {
        packet.packet_hash,
        packet.evidence_bundle_integrity_hash,
        packet.candidate_compilation_integrity_hash,
        packet.semantic_projection_hash,
        packet.slim_candidate.view_hash,
        alias_receipt.integrity_hash,
        choice_contract.choice_schema_hash,
        choice_contract.local_candidate.response_schema_hash,
        choice_contract.local_candidate.integrity_hash,
        compilation.integrity_hash,
        evidence_bundle.bundle_id,
        evidence_bundle.document_ref,
        evidence_bundle.normalization_run_ref,
        evidence_bundle.source_package_ref,
        evidence_bundle.source_scope_ref,
        source_package.integrity_hash,
        *alias_receipt.value_aliases.values(),
        *alias_receipt.type_aliases.values(),
        *alias_receipt.choice_aliases.values(),
    }
    for value in evidence_bundle.source_values:
        opaque_values.update(
            {
                value.source_value_ref,
                value.source_ref,
                value.association_ref,
                value.lineage.document_ref,
                value.lineage.page_ref,
                value.lineage.table_ref,
                value.lineage.row_ref,
                value.lineage.cell_ref,
                value.lineage.text_segment_ref,
                *value.source_evidence_refs,
            }
        )
    for option in compilation.typed_options:
        opaque_values.add(option.typed_option_id)
        opaque_values.add(option.input_type_id)
        opaque_values.update(
            binding.source_value_ref for binding in option.role_bindings
        )
    return sum(
        1
        for value in opaque_values
        if isinstance(value, str) and value and value in serialized
    )


def _context_v2_1_opaque_global_ids_total(
    *,
    model_visible_request: dict[str, Any],
    packet: Gate2FinancialSemanticV6Packet,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    compilation: Gate2FinancialCandidateCompilation,
    mapping_receipt: Gate2FinancialSemanticV6ContextV21MappingReceipt,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> int:
    serialized = _model_json_text(model_visible_request)
    opaque_values = {
        evidence_bundle.bundle_id,
        evidence_bundle.source_package_ref,
        evidence_bundle.normalization_run_ref,
        evidence_bundle.document_ref,
        evidence_bundle.source_scope_ref,
        evidence_bundle.source_family_id,
        source_package.package_ref,
        source_package.normalization_run_ref,
        source_package.document_ref,
        source_package.source_scope_ref,
        source_package.source_family_id,
        compilation.evidence_bundle_id,
        compilation.semantic_pack_id,
        compilation.semantic_pack_version,
        registry.registry_id,
        registry.registry_version,
        *evidence_bundle.issue_refs,
        *evidence_bundle.provenance_refs,
        *source_package.issue_refs,
        *source_package.source_evidence_refs,
        *choice_contract.typed_option_ids,
    }
    for value in evidence_bundle.source_values:
        opaque_values.update(
            {
                value.source_value_ref,
                value.source_ref,
                value.association_ref,
                value.lineage.document_ref,
                value.lineage.page_ref,
                value.lineage.table_ref,
                value.lineage.row_ref,
                value.lineage.cell_ref,
                value.lineage.text_segment_ref,
                *value.source_evidence_refs,
            }
        )
    for value in source_package.source_values:
        opaque_values.update(
            {
                value.source_value_ref,
                value.source_ref,
                value.lineage.document_ref,
                value.lineage.page_ref,
                value.lineage.table_ref,
                value.lineage.row_ref,
                value.lineage.cell_ref,
                value.lineage.text_segment_ref,
                *value.source_evidence_refs,
            }
        )
    for association in evidence_bundle.source_associations:
        opaque_values.update(
            {
                association.association_ref,
                *association.source_value_refs,
            }
        )
    for option in compilation.typed_options:
        opaque_values.update(
            {
                option.typed_option_id,
                option.input_type_id,
                *(
                    binding.source_value_ref
                    for binding in option.role_bindings
                ),
            }
        )
    for blocked in compilation.blocked_bindings:
        opaque_values.update(
            {
                blocked.association_ref,
                blocked.input_type_id,
            }
        )
    opaque_values.update(
        item.get("input_type_id")
        for item in mapping_receipt.type_mappings
    )
    opaque_values.update(
        item.get("typed_option_id")
        for item in mapping_receipt.choice_restoration
    )
    field_names = (
        _FORBIDDEN_MODEL_FIELDS
        - {
            "active_packet_hash",
            "candidate_compilation_integrity_hash",
            "choice_schema_hash",
            "content_hash",
            "integrity_hash",
            "packet_hash",
            "prompt_hash",
            "receipt_hash",
            "schema_hash",
            "view_hash",
        }
    )
    field_violations = _count_named_fields(
        model_visible_request,
        field_names,
    )
    return field_violations + sum(
        1
        for value in opaque_values
        if isinstance(value, str) and value and value in serialized
    )


def _context_v2_1_backend_hashes_total(
    *,
    model_visible_request: dict[str, Any],
    packet: Gate2FinancialSemanticV6Packet,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    compilation: Gate2FinancialCandidateCompilation,
    mapping_receipt: Gate2FinancialSemanticV6ContextV21MappingReceipt,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> int:
    serialized = _model_json_text(model_visible_request)
    known_hashes = {
        packet.packet_hash,
        packet.evidence_bundle_integrity_hash,
        packet.candidate_compilation_integrity_hash,
        packet.semantic_projection_hash,
        packet.context_v2_candidate.view_hash,
        mapping_receipt.integrity_hash,
        choice_contract.choice_schema_hash,
        choice_contract.local_candidate.response_schema_hash,
        choice_contract.local_candidate.integrity_hash,
        choice_contract.context_v2_1_response_profile.response_schema_hash,
        choice_contract.context_v2_1_response_profile.integrity_hash,
        evidence_bundle.integrity_hash,
        evidence_bundle.source_package_integrity_hash,
        source_package.integrity_hash,
        compilation.integrity_hash,
        compilation.evidence_bundle_integrity_hash,
        compilation.semantic_pack_integrity_sha256,
        registry.registry_hash,
    }
    hash_fields = {
        "active_packet_hash",
        "candidate_compilation_integrity_hash",
        "choice_schema_hash",
        "content_hash",
        "integrity_hash",
        "packet_hash",
        "prompt_hash",
        "receipt_hash",
        "schema_hash",
        "view_hash",
    }
    field_violations = _count_named_fields(
        model_visible_request,
        hash_fields,
    )
    observed_hashes = {
        item
        for item in re.findall(
            r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])",
            serialized,
        )
    }
    observed_hashes.update(
        value
        for value in known_hashes
        if isinstance(value, str) and value and value in serialized
    )
    return field_violations + len(observed_hashes)


def _context_v2_1_semantic_literal_metrics(
    *,
    system_message: str,
    payload: dict[str, Any],
    response_format: dict[str, Any],
    evidence_bundle: Gate2FinancialEvidenceBundle,
    mapping_receipt: Gate2FinancialSemanticV6ContextV21MappingReceipt,
) -> tuple[int, int, int]:
    semantic_values = tuple(
        value
        for value in evidence_bundle.source_values
        if value.value_type != "source_reference"
    )
    if not semantic_values:
        _fail(
            "financial_semantic_v6_context_v2_1_literal_set_empty"
        )
    expected_by_ref = {
        value.source_value_ref: value for value in semantic_values
    }
    for mapping in mapping_receipt.source_mappings.get(
        "occurrences",
        (),
    ):
        source = expected_by_ref.get(mapping.get("source_value_ref"))
        rendered = _json_pointer_get_optional(
            payload,
            mapping.get("json_pointer"),
        )
        if (
            source is None
            or not isinstance(rendered, dict)
            or rendered.get("literal") != source.literal_value
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "literal_mapping_invalid"
            )
    expected = Counter(
        value.literal_value for value in semantic_values
    )
    observed = Counter(
        value
        for value in _walk_strings(
            {
                "system_message": system_message,
                "payload": payload,
                "response_format": response_format,
            }
        )
        if value in expected
    )
    covered = sum(
        min(observed[literal], count)
        for literal, count in expected.items()
    )
    duplicates = sum(
        max(0, observed[literal] - count)
        for literal, count in expected.items()
    )
    return sum(expected.values()), covered, duplicates


def _context_v2_1_unused_or_orphan_keys_total(
    *,
    payload: dict[str, Any],
    response_schema: dict[str, Any],
) -> int:
    source_definitions = Counter(
        (key, value)
        for item in _walk_dicts_local(payload.get("source"))
        for key, value in item.items()
        if key in {"value_key", "structure_key"}
        and isinstance(value, str)
    )
    source_consumers = Counter(
        (key, value)
        for choice in payload.get("choices", ())
        if isinstance(choice, dict)
        for differentiator in choice.get("differentiators", ())
        if isinstance(differentiator, dict)
        for key, value in differentiator.items()
        if key in {"value_key", "structure_key"}
        and isinstance(value, str)
    )
    type_definitions = Counter(
        card.get("type_key")
        for card in payload.get("type_cards", ())
        if isinstance(card, dict)
        and isinstance(card.get("type_key"), str)
    )
    type_consumers = Counter(
        competitor.get("type_key")
        for card in payload.get("type_cards", ())
        if isinstance(card, dict)
        and isinstance(card.get("nearest_competitor"), dict)
        for competitor in (card["nearest_competitor"],)
        if isinstance(competitor.get("type_key"), str)
    )
    choice_definitions = Counter(
        choice.get("choice_key")
        for choice in payload.get("choices", ())
        if isinstance(choice, dict)
        and isinstance(choice.get("choice_key"), str)
    )
    choice_consumers = Counter(
        item
        for variant in response_schema.get("anyOf", ())
        if isinstance(variant, dict)
        for properties in (variant.get("properties"),)
        if isinstance(properties, dict)
        for choice_property in (properties.get("choice"),)
        if isinstance(choice_property, dict)
        for values in (choice_property.get("enum"),)
        if isinstance(values, list)
        for item in values
        if isinstance(item, str) and item != "unclassified"
    )
    return sum(
        (
            _counter_bijection_defects(
                source_definitions,
                source_consumers,
            ),
            _counter_bijection_defects(
                type_definitions,
                type_consumers,
            ),
            _counter_bijection_defects(
                choice_definitions,
                choice_consumers,
            ),
        )
    )


def _context_v2_1_unexplained_reason_codes_total(
    *,
    payload: dict[str, Any],
    response_schema: dict[str, Any],
    expected_reason_codes: tuple[str, ...],
) -> int:
    reason_rows = payload.get("unclassified_reasons")
    if not isinstance(reason_rows, list):
        return 1
    shape_defects = sum(
        not isinstance(row, dict)
        or set(row) != {"code", "title", "use_when"}
        or any(
            not isinstance(row.get(field), str) or not row.get(field)
            for field in ("code", "title", "use_when")
        )
        for row in reason_rows
    )
    defined = tuple(
        row.get("code")
        for row in reason_rows
        if isinstance(row, dict)
        and isinstance(row.get("code"), str)
    )
    schema_codes = tuple(
        item
        for variant in response_schema.get("anyOf", ())
        if isinstance(variant, dict)
        for properties in (variant.get("properties"),)
        if isinstance(properties, dict)
        and "reason" in properties
        for reason_property in (properties.get("reason"),)
        if isinstance(reason_property, dict)
        for values in (reason_property.get("enum"),)
        if isinstance(values, list)
        for item in values
        if isinstance(item, str)
    )
    return sum(
        (
            shape_defects,
            int(defined != expected_reason_codes),
            int(schema_codes != expected_reason_codes),
            _counter_bijection_defects(
                Counter(defined),
                Counter(expected_reason_codes),
            ),
            _counter_bijection_defects(
                Counter(schema_codes),
                Counter(expected_reason_codes),
            ),
        )
    )


def _context_v2_1_mapping_coverage_metrics(
    *,
    payload: dict[str, Any],
    mapping_receipt: Gate2FinancialSemanticV6ContextV21MappingReceipt,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    compilation: Gate2FinancialCandidateCompilation,
) -> tuple[int, int]:
    semantic_values = tuple(
        value
        for value in evidence_bundle.source_values
        if value.value_type != "source_reference"
    )
    expected_by_ref = {
        value.source_value_ref: value for value in semantic_values
    }
    source_structures_total = sum(
        isinstance(item.get("kind"), str)
        for item in _walk_dicts_local(payload.get("source"))
    )
    type_mappings_total = len(payload.get("type_cards", ()))
    choice_mappings_total = len(payload.get("choices", ()))

    source_occurrences_covered = 0
    seen_source_pointers: set[str] = set()
    for row in mapping_receipt.source_mappings.get(
        "occurrences",
        (),
    ):
        pointer = row.get("json_pointer")
        target = _json_pointer_get_optional(payload, pointer)
        source = expected_by_ref.get(row.get("source_value_ref"))
        if (
            isinstance(pointer, str)
            and pointer not in seen_source_pointers
            and isinstance(target, dict)
            and source is not None
            and target.get("literal") == source.literal_value
        ):
            seen_source_pointers.add(pointer)
            source_occurrences_covered += 1

    source_structures_covered = 0
    seen_structure_pointers: set[str] = set()
    model_kind_by_private_kind = {
        "table": "table",
        "row": "row",
        "text_segment": "text segment",
    }
    for row in mapping_receipt.source_mappings.get(
        "structures",
        (),
    ):
        pointer = row.get("json_pointer")
        target = _json_pointer_get_optional(payload, pointer)
        node_identity = row.get("node_identity")
        private_kind = (
            node_identity.get("kind")
            if isinstance(node_identity, dict)
            else None
        )
        if (
            isinstance(pointer, str)
            and pointer not in seen_structure_pointers
            and isinstance(target, dict)
            and target.get("kind")
            == model_kind_by_private_kind.get(private_kind)
        ):
            seen_structure_pointers.add(pointer)
            source_structures_covered += 1

    type_mappings_covered = 0
    seen_type_pointers: set[str] = set()
    for row in mapping_receipt.type_mappings:
        pointer = row.get("json_pointer")
        target = _json_pointer_get_optional(payload, pointer)
        if (
            isinstance(pointer, str)
            and pointer not in seen_type_pointers
            and isinstance(target, dict)
            and target.get("type_key") == row.get("type_key")
            and isinstance(row.get("input_type_id"), str)
        ):
            seen_type_pointers.add(pointer)
            type_mappings_covered += 1

    options_by_id = {
        option.typed_option_id: option
        for option in compilation.typed_options
    }
    choice_mappings_covered = 0
    seen_choice_pointers: set[str] = set()
    choice_key_by_option_id: dict[str, str] = {}
    for row in mapping_receipt.choice_restoration:
        pointer = row.get("json_pointer")
        target = _json_pointer_get_optional(payload, pointer)
        option = options_by_id.get(row.get("typed_option_id"))
        expected_role_bindings = (
            [
                {
                    "role_id": binding.role_id,
                    "source_value_ref": binding.source_value_ref,
                }
                for binding in option.role_bindings
            ]
            if option is not None
            else None
        )
        if (
            isinstance(pointer, str)
            and pointer not in seen_choice_pointers
            and isinstance(target, dict)
            and target.get("choice_key") == row.get("choice_key")
            and option is not None
            and row.get("input_type_id") == option.input_type_id
            and row.get("role_bindings") == expected_role_bindings
        ):
            seen_choice_pointers.add(pointer)
            choice_mappings_covered += 1
            choice_key_by_option_id[option.typed_option_id] = row[
                "choice_key"
            ]

    expected_bindings = Counter(
        (
            choice_key_by_option_id.get(option.typed_option_id),
            binding.role_id,
            binding.source_value_ref,
        )
        for option in compilation.typed_options
        for binding in option.role_bindings
    )
    observed_bindings = Counter(
        (
            row.get("choice_key"),
            row.get("role_id"),
            row.get("source_value_ref"),
        )
        for partition_name in (
            "visible_differentiators",
            "backend_only_bindings",
        )
        for row in mapping_receipt.binding_partition.get(
            partition_name,
            (),
        )
        if isinstance(row, dict)
    )
    binding_rows_total = sum(expected_bindings.values())
    binding_rows_covered = sum(
        (expected_bindings & observed_bindings).values()
    )
    mapping_rows_total = sum(
        (
            len(semantic_values),
            source_structures_total,
            type_mappings_total,
            choice_mappings_total,
            binding_rows_total,
        )
    )
    mapping_rows_covered_total = sum(
        (
            source_occurrences_covered,
            source_structures_covered,
            type_mappings_covered,
            choice_mappings_covered,
            binding_rows_covered,
        )
    )
    return mapping_rows_total, mapping_rows_covered_total


def _counter_bijection_defects(
    definitions: Counter,
    consumers: Counter,
) -> int:
    keys = set(definitions) | set(consumers)
    return (
        sum(
            abs(definitions[key] - consumers[key])
            for key in keys
        )
        + sum(max(0, count - 1) for count in definitions.values())
        + sum(max(0, count - 1) for count in consumers.values())
    )


def _json_pointer_get_optional(value: Any, pointer: Any) -> Any:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        return None
    current = value
    try:
        for raw_part in pointer[1:].split("/"):
            part = raw_part.replace("~1", "/").replace("~0", "~")
            if isinstance(current, list):
                current = current[int(part)]
            elif isinstance(current, dict):
                current = current[part]
            else:
                return None
    except (IndexError, KeyError, TypeError, ValueError):
        return None
    return current


def _walk_dicts_local(value: Any):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk_dicts_local(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_dicts_local(item)


def _count_named_fields(value: Any, field_names: set[str]) -> int:
    if isinstance(value, dict):
        return sum(
            int(key in field_names)
            + _count_named_fields(item, field_names)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return sum(
            _count_named_fields(item, field_names) for item in value
        )
    return 0


def _model_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise Gate2FinancialSemanticV6ContextLintError(
            "financial_semantic_v6_context_v2_1_serialization_invalid"
        ) from exc


def _model_json_text(value: Any) -> str:
    return _model_json_bytes(value).decode("utf-8")


def _model_hash(value: Any) -> str:
    return hashlib.sha256(_model_json_bytes(value)).hexdigest()


def _count_nulls(value: Any) -> int:
    if value is None:
        return 1
    if isinstance(value, dict):
        return sum(_count_nulls(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return sum(_count_nulls(item) for item in value)
    return 0


def _count_forbidden_fields(value: Any) -> int:
    if isinstance(value, dict):
        return sum(
            int(key in _FORBIDDEN_MODEL_FIELDS)
            + _count_forbidden_fields(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return sum(_count_forbidden_fields(item) for item in value)
    return 0


def _walk_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_strings(item)


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV6ContextLintError(code)
