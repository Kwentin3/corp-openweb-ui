from __future__ import annotations

# ruff: noqa: E402

import argparse
import copy
import hashlib
import json
import sys
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterator


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SERVICE_ROOT.parents[1]
REPORT_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "reports"
    / "2026-07-30"
    / "BROKER_REPORTS_GATE2_TYPE_FIRST_INACTIVE_IMPLEMENTATION_GOAL17.report.md"
)
SAFE_RECEIPT_PATH = REPORT_PATH.with_name(
    "BROKER_REPORTS_GATE2_TYPE_FIRST_INACTIVE_IMPLEMENTATION_GOAL17"
    ".receipt.safe.json"
)
CONTRACT_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_GATE2_TYPE_FIRST_INACTIVE_IMPLEMENTATION.v1.json"
)
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.gate2_deterministic_financial_scopes import (
    Gate2DeterministicFinancialScopeFromGate1V2Factory,
)
from broker_reports_gate1.gate2_economy_budget import (
    Gate2EconomyBudgetSessionFactory,
)
from broker_reports_gate1.gate2_financial_domain_catalog import (
    Gate2FinancialDomainCatalogFactory,
)
from broker_reports_gate1.gate2_financial_domain_contracts import (
    FinancialDomainAccessContext,
)
from broker_reports_gate1.gate2_financial_domain_persistence import (
    Gate2FinancialDomainPersistenceFactory,
)
from broker_reports_gate1.gate2_financial_evidence_materialization import (
    Gate2FinancialEvidenceMaterializerFactory,
)
from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (
    FinancialEvidenceExecutionMetadata,
    sha256_json,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_evidence_source_package import (
    Gate2FinancialEvidenceSourcePackageFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_bundle import (
    Gate2FinancialEvidenceBundleFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_candidate_compiler import (
    Gate2FinancialCandidateCompilerFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_choice import (
    Gate2FinancialSemanticV6ChoiceContractFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_context_linter import (
    Gate2FinancialSemanticV6ContextLinterFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_evidence import (
    Gate2FinancialSemanticV6DecisionEvidenceFactory,
    replay_financial_semantic_v6_type_first_decision,
    restore_financial_semantic_v6_type_first_private_evidence,
    serialize_financial_semantic_v6_type_first_private_evidence,
)
from broker_reports_gate1.gate2_financial_semantic_v6_expansion import (
    Gate2FinancialSemanticV6DecisionExpansionFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_packet import (
    Gate2FinancialSemanticV6PacketFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_prompt import (
    V6_SEMANTIC_SYSTEM_PROMPT,
)
from broker_reports_gate1.gate2_model_contracts import (
    gate2_provider_profile,
)
from broker_reports_gate1.gate2_model_requests import (
    FINANCIAL_SEMANTIC_V6_TYPE_FIRST_LOCAL_PROOF_REQUEST_PROFILE,
    financial_semantic_v6_type_first_local_proof_request,
)
from broker_reports_gate1.gate2_provider_adapters import (
    Gate2ProviderAdapterFactory,
)
from broker_reports_gate1.gate2_successor_local_proof import (
    _fixture_package,
)


MANIFEST_PATH = (
    SERVICE_ROOT
    / "benchmarks"
    / "gate2_financial_successor_v2"
    / "manifest.json"
)
MODEL_ID = "type-first-local-simulator-v1"
SNAPSHOT_AUTHORITY_KEY = (
    b"goal17-type-first-zero-call-snapshot-authority-key"
)
CREATED_AT = "2026-07-30T00:00:00Z"
E2E_SCHEMA_VERSION = (
    "broker_reports_gate2_type_first_zero_call_local_e2e_v1"
)
QUALIFICATION_COUNTERS = (
    "plausible_type_set_exact_total",
    "false_empty_total",
    "false_singleton_total",
    "false_superset_total",
    "wrong_singleton_type_total",
    "false_singleton_typed_total",
    "unsafe_typed_total",
    "safe_under_typing_total",
    "invalid_response_total",
)

SUCCESS_ACCOUNTING = {
    "maximum_provider_calls_per_operation": 1,
    "maximum_fallback_calls_per_operation": 0,
    "provider_calls_authorized_total": 0,
    "fallback_calls_authorized_total": 0,
    "provider_submissions_total": 0,
    "provider_calls_total": 0,
    "provider_responses_total": 0,
    "transport_invocations_total": 0,
    "simulated_terminal_envelopes_total": 1,
    "repair_total": 0,
    "semantic_repair_total": 0,
    "fallback_total": 0,
    "retry_total": 0,
}
FAILURE_ACCOUNTING = {
    **SUCCESS_ACCOUNTING,
    "simulated_terminal_envelopes_total": 0,
}


class TypeFirstZeroCallE2EError(RuntimeError):
    pass


@dataclass(frozen=True)
class _Authorities:
    registry: Any
    source_package: Any
    evidence_bundle: Any
    compilation: Any
    packet: Any
    type_first_candidate: Any
    mapping_receipt: Any
    choice_contract: Any
    response_profile: Any
    sealed_request: Any
    prepared_request: Any
    adapter: Any
    economy_accounting_receipt: dict[str, Any]


@dataclass(frozen=True)
class _SuccessCase:
    case_id: str
    fixture_shape: str
    observed: tuple[str, ...]
    oracle: tuple[str, ...]
    expected_disposition: str
    expected_reason_code: str | None
    expected_counters: dict[str, int]


@dataclass(frozen=True)
class _ParserFailureCase:
    case_id: str
    invalid_input: Any
    expected_error_code: str


SUCCESS_CASES = (
    _SuccessCase(
        case_id="goal17_true_empty",
        fixture_shape="zero",
        observed=(),
        oracle=(),
        expected_disposition="unclassified_financial_input",
        expected_reason_code="no_registry_type",
        expected_counters={
            "plausible_type_set_exact_total": 1,
        },
    ),
    _SuccessCase(
        case_id="goal17_true_singleton_zero_options",
        fixture_shape="zero",
        observed=("type_1",),
        oracle=("type_1",),
        expected_disposition="unclassified_financial_input",
        expected_reason_code="single_registry_type_no_safe_record",
        expected_counters={
            "plausible_type_set_exact_total": 1,
        },
    ),
    _SuccessCase(
        case_id="goal17_true_singleton_one_option",
        fixture_shape="one",
        observed=("type_1",),
        oracle=("type_1",),
        expected_disposition="typed_input",
        expected_reason_code=None,
        expected_counters={
            "plausible_type_set_exact_total": 1,
        },
    ),
    _SuccessCase(
        case_id="goal17_true_singleton_multiple_options",
        fixture_shape="multiple",
        observed=("type_1",),
        oracle=("type_1",),
        expected_disposition="unclassified_financial_input",
        expected_reason_code="single_registry_type_no_safe_record",
        expected_counters={
            "plausible_type_set_exact_total": 1,
        },
    ),
    _SuccessCase(
        case_id="goal17_true_multiple_types",
        fixture_shape="one",
        observed=("type_1", "type_2"),
        oracle=("type_1", "type_2"),
        expected_disposition="unclassified_financial_input",
        expected_reason_code="ambiguous_registry_type",
        expected_counters={
            "plausible_type_set_exact_total": 1,
        },
    ),
    _SuccessCase(
        case_id="goal17_false_empty",
        fixture_shape="one",
        observed=(),
        oracle=("type_1",),
        expected_disposition="unclassified_financial_input",
        expected_reason_code="no_registry_type",
        expected_counters={
            "false_empty_total": 1,
            "safe_under_typing_total": 1,
        },
    ),
    _SuccessCase(
        case_id="goal17_false_singleton",
        fixture_shape="one",
        observed=("type_1",),
        oracle=("type_1", "type_2"),
        expected_disposition="typed_input",
        expected_reason_code=None,
        expected_counters={
            "false_singleton_total": 1,
            "false_singleton_typed_total": 1,
            "unsafe_typed_total": 1,
        },
    ),
    _SuccessCase(
        case_id="goal17_false_singleton_from_true_empty",
        fixture_shape="one",
        observed=("type_1",),
        oracle=(),
        expected_disposition="typed_input",
        expected_reason_code=None,
        expected_counters={
            "false_singleton_total": 1,
            "false_superset_total": 1,
            "false_singleton_typed_total": 1,
            "unsafe_typed_total": 1,
        },
    ),
    _SuccessCase(
        case_id="goal17_false_superset",
        fixture_shape="one",
        observed=("type_1", "type_2"),
        oracle=("type_1",),
        expected_disposition="unclassified_financial_input",
        expected_reason_code="ambiguous_registry_type",
        expected_counters={
            "false_superset_total": 1,
            "safe_under_typing_total": 1,
        },
    ),
    _SuccessCase(
        case_id="goal17_wrong_singleton",
        fixture_shape="one",
        observed=("type_1",),
        oracle=("type_2",),
        expected_disposition="typed_input",
        expected_reason_code=None,
        expected_counters={
            "wrong_singleton_type_total": 1,
            "unsafe_typed_total": 1,
        },
    ),
)

PARSER_FAILURE_CASES = (
    _ParserFailureCase(
        "goal17_unknown_type",
        {"plausible_types": ["type_9"]},
        "unknown_type_key",
    ),
    _ParserFailureCase(
        "goal17_duplicate_type",
        {"plausible_types": ["type_1", "type_1"]},
        "duplicate_type_key",
    ),
    _ParserFailureCase(
        "goal17_out_of_order",
        {"plausible_types": ["type_2", "type_1"]},
        "out_of_order_type_keys",
    ),
    _ParserFailureCase(
        "goal17_malformed_json",
        '{"plausible_types":[}',
        "malformed_json",
    ),
    _ParserFailureCase(
        "goal17_duplicate_root",
        '{"plausible_types":[],"plausible_types":["type_1"]}',
        "duplicate_response_field",
    ),
    _ParserFailureCase(
        "goal17_missing_root_field",
        {},
        "missing_plausible_types",
    ),
    _ParserFailureCase(
        "goal17_extra_root_field",
        {"plausible_types": [], "extra": True},
        "extra_response_field",
    ),
    _ParserFailureCase(
        "goal17_null_plausible_types",
        {"plausible_types": None},
        "plausible_types_null",
    ),
    _ParserFailureCase(
        "goal17_non_array",
        {"plausible_types": "type_1"},
        "plausible_types_not_array",
    ),
    _ParserFailureCase(
        "goal17_backend_id",
        {"plausible_types": ["cash_balance_snapshot_v1"]},
        "backend_type_id_forbidden",
    ),
    _ParserFailureCase(
        "goal17_non_object_root",
        [],
        "response_root_not_object",
    ),
    _ParserFailureCase(
        "goal17_non_string_key",
        {"plausible_types": [1]},
        "unknown_type_key",
    ),
)


def build_type_first_zero_call_e2e_evidence() -> dict[str, Any]:
    authorities = {
        shape: _build_authorities(shape)
        for shape in ("zero", "one", "multiple")
    }
    fixture_option_counts = {
        shape: _matching_complete_options_total(
            value,
            type_key="type_1",
        )
        for shape, value in authorities.items()
    }
    _require(
        fixture_option_counts == {"zero": 0, "one": 1, "multiple": 2},
        "real_compiler_fixture_counts_invalid",
    )

    transport_attempts: list[str] = []
    success_summaries: list[dict[str, Any]] = []
    success_evidence: dict[str, Any] = {}
    with _forbid_transport(
        authorities["one"].adapter,
        attempts=transport_attempts,
    ):
        for case in SUCCESS_CASES:
            summary, evidence = _run_success_case(
                authorities[case.fixture_shape],
                case,
            )
            success_summaries.append(summary)
            success_evidence[case.case_id] = evidence

        failure_summaries = [
            _run_technical_failure_case(
                authorities["one"],
                case_id=case.case_id,
                failure_stage="response_parser",
                exact_invalid_input=case.invalid_input,
                expected_error_code=case.expected_error_code,
            )
            for case in PARSER_FAILURE_CASES
        ]
        failure_summaries.append(
            _run_request_sealing_failure(authorities["one"])
        )
        binding_drift_failure = _prove_resealed_binding_drift(
            authorities["one"]
        )
        pack_projection_failure = _prove_pack_projection_drift(
            authorities["one"]
        )
        restoration_failure = _prove_exact_option_restoration_mismatch(
            authorities["one"],
            evidence=success_evidence[
                "goal17_true_singleton_one_option"
            ],
        )
        failure_summaries.extend(
            (
                binding_drift_failure,
                pack_projection_failure,
                restoration_failure,
            )
        )

    _require(not transport_attempts, "transport_boundary_invoked")
    semantic_adversarial_total = sum(
        case.case_id
        in {
            "goal17_false_empty",
            "goal17_false_singleton",
            "goal17_false_singleton_from_true_empty",
            "goal17_false_superset",
            "goal17_wrong_singleton",
        }
        for case in SUCCESS_CASES
    )
    technical_adversarial_total = len(failure_summaries)
    qualification_counter_totals = {
        counter: sum(
            item["qualification_counters"][counter]
            for item in success_summaries
        )
        + (
            sum(
                item["invalid_response_total"]
                for item in failure_summaries
            )
            if counter == "invalid_response_total"
            else 0
        )
        for counter in QUALIFICATION_COUNTERS
    }
    material = {
        "schema_version": E2E_SCHEMA_VERSION,
        "status": "passed",
        "real_compiler_fixture_matching_complete_options": (
            fixture_option_counts
        ),
        "success_cases": success_summaries,
        "technical_failure_cases": failure_summaries,
        "qualification_counter_totals": (
            qualification_counter_totals
        ),
        "repository_authorities": _repository_authorities(),
        "binding_drift_error_code": binding_drift_failure[
            "exact_error_code"
        ],
        "pack_projection_drift_error_code": (
            pack_projection_failure["exact_error_code"]
        ),
        "exact_option_restoration_error_code": restoration_failure[
            "exact_error_code"
        ],
        "counts": {
            "success_cases_total": len(success_summaries),
            "true_semantic_cases_total": (
                len(success_summaries)
                - semantic_adversarial_total
            ),
            "semantic_adversarial_cases_total": (
                semantic_adversarial_total
            ),
            "parser_adversarial_cases_total": len(
                PARSER_FAILURE_CASES
            ),
            "request_sealing_adversarial_cases_total": 1,
            "binding_drift_adversarial_cases_total": 1,
            "pack_projection_drift_adversarial_cases_total": 1,
            "exact_option_restoration_adversarial_cases_total": 1,
            "adversarial_cases_total": (
                semantic_adversarial_total
                + technical_adversarial_total
            ),
            "success_evidence_serialize_restore_replay_total": len(
                success_summaries
            ),
            "technical_failure_serialize_restore_replay_total": len(
                failure_summaries
            ),
            "simulated_terminal_envelopes_total": len(
                success_summaries
            ),
            "simulated_terminal_envelopes_per_success_case": 1,
            "canonical_decisions_total": len(success_summaries),
            "materialized_records_total": len(success_summaries),
            "financial_domain_snapshots_total": len(
                success_summaries
            ),
            "invalid_responses_total": len(PARSER_FAILURE_CASES),
        },
        "execution_accounting": {
            "maximum_provider_calls_per_operation": 1,
            "maximum_fallback_calls_per_operation": 0,
            "provider_calls_authorized_total": 0,
            "fallback_calls_authorized_total": 0,
            "provider_submissions_total": 0,
            "provider_calls_total": 0,
            "provider_responses_total": 0,
            "transport_invocations_total": len(transport_attempts),
            "simulated_terminal_envelopes_total": len(
                success_summaries
            ),
            "repair_total": 0,
            "semantic_repair_total": 0,
            "fallback_total": 0,
            "retry_total": 0,
        },
        "privacy": {
            "private_evidence_returned": False,
            "raw_envelopes_returned": False,
            "source_literals_returned": False,
            "source_refs_returned": False,
        },
        "runtime_activation": False,
        "production_admission": False,
    }
    result = {
        **material,
        "integrity_sha256": sha256_json(material),
    }
    _validate_aggregate(result)
    return result


def _build_authorities(shape: str) -> _Authorities:
    case_id = {
        "zero": "syn_successor_v2_repeated_header",
        "one": "syn_successor_v2_unique_cash",
        "multiple": "syn_successor_v2_forbidden_neighbour",
    }.get(shape)
    _require(case_id is not None, "fixture_shape_unknown")
    case = copy.deepcopy(_manifest_cases()[case_id])
    fixture = _fixture_package(case)
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    payload = fixture.payload
    if shape == "multiple":
        neighbour_ref = f"row:{case_id}:neighbour"
        payload["allowed_evidence_refs"].append(neighbour_ref)
        payload["coverage_expectation"]["selected_source_refs"].append(
            neighbour_ref
        )
    scopes = (
        Gate2DeterministicFinancialScopeFromGate1V2Factory(
            registry=registry
        )
        .create(gate1_packages=(payload,))
        .scopes
    )
    if shape == "multiple":
        _require(len(scopes) == 2, "multiple_fixture_scope_count_invalid")
        primary_scope = next(
            (
                scope
                for scope in scopes
                if any(
                    ":primary:" in value.source_value_ref
                    for value in scope.source_package.source_values
                )
            ),
            None,
        )
        _require(
            primary_scope is not None,
            "multiple_fixture_primary_scope_missing",
        )
        primary = primary_scope.source_package
        source_package = Gate2FinancialEvidenceSourcePackageFactory(
            package_ref=primary.package_ref,
            normalization_run_ref=primary.normalization_run_ref,
            document_ref=primary.document_ref,
            source_scope_ref=primary.source_scope_ref,
            source_family_id=primary.source_family_id,
            source_values=tuple(
                sorted(
                    (
                        value
                        for scope in scopes
                        for value in scope.source_package.source_values
                        if not value.source_value_ref.endswith(
                            ":printed-label"
                        )
                    ),
                    key=lambda value: value.source_value_ref,
                )
            ),
            source_evidence_refs=tuple(
                sorted(
                    {
                        item
                        for scope in scopes
                        for item in (
                            scope.source_package.source_evidence_refs
                        )
                    }
                )
            ),
            completeness=primary.completeness,
            restriction_codes=primary.restriction_codes,
            issue_refs=primary.issue_refs,
        ).create()
    else:
        _require(len(scopes) == 1, "fixture_scope_count_invalid")
        source_package = scopes[0].source_package

    evidence_bundle = Gate2FinancialEvidenceBundleFactory().create(
        source_package=source_package,
        gate1_packages=(payload,),
    )
    compilation = Gate2FinancialCandidateCompilerFactory(
        registry=registry
    ).create(
        evidence_bundle=evidence_bundle,
        source_package=source_package,
    )
    packet_factory = Gate2FinancialSemanticV6PacketFactory(
        registry=registry
    )
    packet = packet_factory.create(
        evidence_bundle=evidence_bundle,
        source_package=source_package,
        compilation=compilation,
    )
    type_first_candidate, mapping_receipt = (
        packet_factory.create_type_first_candidate(
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
        )
    )
    choice_factory = Gate2FinancialSemanticV6ChoiceContractFactory(
        registry=registry
    )
    choice_contract = choice_factory.create(
        packet=packet,
        evidence_bundle=evidence_bundle,
        source_package=source_package,
        compilation=compilation,
    )
    response_profile = choice_factory.create_type_first_response_profile(
        packet=packet,
        type_first_candidate=type_first_candidate,
        mapping_receipt=mapping_receipt,
        evidence_bundle=evidence_bundle,
        source_package=source_package,
        compilation=compilation,
    )
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "strict": True,
            "schema": response_profile.canonical_schema(),
        },
    }
    serialized_context = json.dumps(
        type_first_candidate.payload,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    sealed_request = Gate2FinancialSemanticV6ContextLinterFactory(
        registry=registry
    ).create_type_first(
        packet=packet,
        choice_contract=choice_contract,
        type_first_candidate=type_first_candidate,
        response_profile=response_profile,
        evidence_bundle=evidence_bundle,
        source_package=source_package,
        compilation=compilation,
        system_message=V6_SEMANTIC_SYSTEM_PROMPT,
        serialized_context=serialized_context,
        response_format=response_format,
        mapping_receipt=mapping_receipt,
    )
    form_data = financial_semantic_v6_type_first_local_proof_request(
        sealed_request=sealed_request,
        model_id=MODEL_ID,
    )
    adapter = Gate2ProviderAdapterFactory(
        profile=gate2_provider_profile("openai_gpt")
    ).create()
    prepared_request = adapter.prepare_form_data(
        form_data=form_data,
        response_format=sealed_request.response_format,
    )
    economy_accounting_receipt = (
        Gate2EconomyBudgetSessionFactory()
        .create(
            request_profile=(
                FINANCIAL_SEMANTIC_V6_TYPE_FIRST_LOCAL_PROOF_REQUEST_PROFILE
            )
        )
        .type_first_accounting_receipt()
    )
    return _Authorities(
        registry=registry,
        source_package=source_package,
        evidence_bundle=evidence_bundle,
        compilation=compilation,
        packet=packet,
        type_first_candidate=type_first_candidate,
        mapping_receipt=mapping_receipt,
        choice_contract=choice_contract,
        response_profile=response_profile,
        sealed_request=sealed_request,
        prepared_request=prepared_request,
        adapter=adapter,
        economy_accounting_receipt=economy_accounting_receipt,
    )


def _run_success_case(
    authorities: _Authorities,
    case: _SuccessCase,
) -> tuple[dict[str, Any], Any]:
    answer = {"plausible_types": list(case.observed)}
    envelope = _terminal_envelope(answer, case_id=case.case_id)
    extracted = authorities.adapter.extract_prepared_content(
        envelope,
        prepared_request=authorities.prepared_request,
    )
    expansion = Gate2FinancialSemanticV6DecisionExpansionFactory(
        registry=authorities.registry
    ).create_from_type_first_candidate(
        model_output=extracted,
        response_profile=authorities.response_profile,
        type_first_candidate=authorities.type_first_candidate,
        mapping_receipt=authorities.mapping_receipt,
        choice_contract=authorities.choice_contract,
        packet=authorities.packet,
        evidence_bundle=authorities.evidence_bundle,
        source_package=authorities.source_package,
        compilation=authorities.compilation,
    )
    decision = expansion.validated_decision.decision
    observed_reason = (
        getattr(decision, "reason_code", None)
        if expansion.disposition == "unclassified_financial_input"
        else None
    )
    _require(
        expansion.disposition == case.expected_disposition,
        f"{case.case_id}:disposition_mismatch",
    )
    _require(
        observed_reason == case.expected_reason_code,
        f"{case.case_id}:reason_code_mismatch",
    )

    execution_metadata = FinancialEvidenceExecutionMetadata(
        execution_ref=f"execution:{case.case_id}",
        decision_validation_ref=f"validation:{case.case_id}",
    )
    materialized_artifact = (
        Gate2FinancialEvidenceMaterializerFactory(
            registry=authorities.registry,
            source_package=authorities.source_package,
            execution_metadata=execution_metadata,
        )
        .create()
        .materialize(
            validated_decision=expansion.validated_decision
        )
    )
    access_context = FinancialDomainAccessContext(
        user_ref="user:goal17-type-first-local",
        case_ref=f"case:{case.case_id}",
    )
    snapshot = Gate2FinancialDomainCatalogFactory(
        registry=authorities.registry,
        snapshot_authority_key=SNAPSHOT_AUTHORITY_KEY,
    ).create(
        materialized_artifacts=(materialized_artifact,),
        source_packages=(authorities.source_package,),
        access_context=access_context,
        created_at=CREATED_AT,
        expires_at=None,
    )
    persistence = Gate2FinancialDomainPersistenceFactory(
        snapshot_authority_key=SNAPSHOT_AUTHORITY_KEY
    )
    serialized_snapshot = persistence.serialize(snapshot=snapshot)
    _require(
        persistence.restore(serialized=serialized_snapshot) == snapshot,
        f"{case.case_id}:snapshot_restore_mismatch",
    )
    evidence = Gate2FinancialSemanticV6DecisionEvidenceFactory(
        registry=authorities.registry
    ).create_type_first_candidate(
        case_id=case.case_id,
        provider_profile_id="openai_gpt",
        local_projection_model_id=MODEL_ID,
        economy_accounting_receipt=(
            authorities.economy_accounting_receipt
        ),
        sealed_request=authorities.sealed_request,
        prepared_request=authorities.prepared_request,
        simulated_provider_envelope=envelope,
        adapter_extracted_output=extracted,
        type_first_candidate=authorities.type_first_candidate,
        mapping_receipt=authorities.mapping_receipt,
        response_profile=authorities.response_profile,
        choice_contract=authorities.choice_contract,
        packet=authorities.packet,
        evidence_bundle=authorities.evidence_bundle,
        source_package=authorities.source_package,
        compilation=authorities.compilation,
        expansion=expansion,
        execution_metadata=execution_metadata,
        materialized_artifact=materialized_artifact,
        snapshot=snapshot,
        serialized_snapshot=serialized_snapshot,
        snapshot_authority_key=SNAPSHOT_AUTHORITY_KEY,
        access_context=access_context,
        created_at=CREATED_AT,
        expires_at=None,
        oracle_plausible_type_keys=case.oracle,
    )
    _require(
        evidence.private_evidence["execution_accounting"]
        == SUCCESS_ACCOUNTING,
        f"{case.case_id}:success_accounting_invalid",
    )
    _require(
        evidence.safe_receipt["status"]
        == "EXACT_ZERO_CALL_LOCAL_PROOF",
        f"{case.case_id}:safe_receipt_status_invalid",
    )
    _require(
        evidence.parsed_response
        == {"plausible_type_keys": case.observed},
        f"{case.case_id}:parsed_response_mismatch",
    )
    for counter, expected in case.expected_counters.items():
        _require(
            evidence.qualification_counters[counter] == expected,
            f"{case.case_id}:{counter}_mismatch",
        )
    serialized_evidence = (
        serialize_financial_semantic_v6_type_first_private_evidence(
            private_evidence=evidence.private_evidence
        )
    )
    restored_evidence = (
        restore_financial_semantic_v6_type_first_private_evidence(
            serialized=serialized_evidence
        )
    )
    _require(
        restored_evidence == evidence.private_evidence,
        f"{case.case_id}:private_evidence_restore_mismatch",
    )
    replay = replay_financial_semantic_v6_type_first_decision(
        private_evidence=restored_evidence,
        expected_sealed_request=authorities.sealed_request,
        type_first_candidate=authorities.type_first_candidate,
        mapping_receipt=authorities.mapping_receipt,
        response_profile=authorities.response_profile,
        choice_contract=authorities.choice_contract,
        packet=authorities.packet,
        evidence_bundle=authorities.evidence_bundle,
        source_package=authorities.source_package,
        compilation=authorities.compilation,
        registry=authorities.registry,
        snapshot_authority_key=SNAPSHOT_AUTHORITY_KEY,
    )
    _require(
        replay.status == "EXACT"
        and replay.provider_calls_total == 0
        and replay.retry_total == 0
        and replay.repair_total == 0
        and replay.fallback_total == 0,
        f"{case.case_id}:success_replay_invalid",
    )
    _require(
        len(envelope["choices"]) == 1
        and envelope["choices"][0]["finish_reason"] == "stop",
        f"{case.case_id}:terminal_envelope_invalid",
    )
    return (
        {
            "case_id": case.case_id,
            "fixture_shape": case.fixture_shape,
            "observed_plausible_types_total": len(case.observed),
            "oracle_plausible_types_total": len(case.oracle),
            "decision_disposition": expansion.disposition,
            "reason_code": observed_reason,
            "matching_complete_options_total": (
                evidence.safe_receipt["counts"][
                    "matching_complete_options_total"
                ]
            ),
            "qualification_counters": copy.deepcopy(
                evidence.qualification_counters
            ),
            "terminal_envelopes_total": 1,
            "provider_calls_total": 0,
            "replay_status": replay.status,
        },
        evidence,
    )


def _run_technical_failure_case(
    authorities: _Authorities,
    *,
    case_id: str,
    failure_stage: str,
    exact_invalid_input: Any,
    expected_error_code: str,
) -> dict[str, Any]:
    evidence = Gate2FinancialSemanticV6DecisionEvidenceFactory(
        registry=authorities.registry
    ).create_type_first_technical_failure(
        case_id=case_id,
        failure_stage=failure_stage,
        exact_error_code=expected_error_code,
        exact_invalid_input=exact_invalid_input,
        economy_accounting_receipt=(
            authorities.economy_accounting_receipt
        ),
        response_profile=authorities.response_profile,
        type_first_candidate=authorities.type_first_candidate,
        mapping_receipt=authorities.mapping_receipt,
        choice_contract=authorities.choice_contract,
        packet=authorities.packet,
        evidence_bundle=authorities.evidence_bundle,
        source_package=authorities.source_package,
        compilation=authorities.compilation,
    )
    _require(
        evidence.private_evidence["execution_accounting"]
        == FAILURE_ACCOUNTING,
        f"{case_id}:failure_accounting_invalid",
    )
    _require(
        evidence.safe_receipt["status"]
        == "EXACT_ZERO_CALL_TECHNICAL_FAILURE",
        f"{case_id}:failure_status_invalid",
    )
    serialized = serialize_financial_semantic_v6_type_first_private_evidence(
        private_evidence=evidence.private_evidence
    )
    restored = restore_financial_semantic_v6_type_first_private_evidence(
        serialized=serialized
    )
    _require(
        restored == evidence.private_evidence,
        f"{case_id}:failure_restore_mismatch",
    )
    replay = replay_financial_semantic_v6_type_first_decision(
        private_evidence=restored,
        expected_sealed_request=None,
        type_first_candidate=authorities.type_first_candidate,
        mapping_receipt=authorities.mapping_receipt,
        response_profile=authorities.response_profile,
        choice_contract=authorities.choice_contract,
        packet=authorities.packet,
        evidence_bundle=authorities.evidence_bundle,
        source_package=authorities.source_package,
        compilation=authorities.compilation,
        registry=authorities.registry,
        snapshot_authority_key=SNAPSHOT_AUTHORITY_KEY,
    )
    expected_invalid_response_total = int(
        failure_stage == "response_parser"
    )
    _require(
        replay.status == "EXACT_TECHNICAL_FAILURE"
        and replay.exact_error_code == expected_error_code
        and replay.invalid_response_total
        == expected_invalid_response_total
        and replay.canonical_decision_total == 0
        and replay.materialized_record_total == 0
        and replay.financial_domain_snapshot_total == 0
        and replay.provider_calls_total == 0
        and replay.retry_total == 0
        and replay.repair_total == 0
        and replay.fallback_total == 0,
        f"{case_id}:failure_replay_invalid",
    )
    return {
        "case_id": case_id,
        "failure_stage": failure_stage,
        "exact_error_code": expected_error_code,
        "invalid_response_total": expected_invalid_response_total,
        "canonical_decision_total": 0,
        "materialized_record_total": 0,
        "financial_domain_snapshot_total": 0,
        "provider_calls_total": 0,
        "replay_status": replay.status,
    }


def _run_request_sealing_failure(
    authorities: _Authorities,
) -> dict[str, Any]:
    invalid_input = {
        "system_message": V6_SEMANTIC_SYSTEM_PROMPT,
        "serialized_context": (
            authorities.sealed_request.serialized_context + " "
        ),
        "response_format": copy.deepcopy(
            authorities.sealed_request.response_format
        ),
    }
    return _run_technical_failure_case(
        authorities,
        case_id="goal17_request_source_hash_drift",
        failure_stage="request_sealing",
        exact_invalid_input=invalid_input,
        expected_error_code="source_hash_drift",
    )


def _prove_resealed_binding_drift(
    authorities: _Authorities,
) -> dict[str, Any]:
    original = authorities.mapping_receipt
    first, second = original.visible_type_card_order
    swapped = {
        first: original.local_to_canonical_type_ids[second],
        second: original.local_to_canonical_type_ids[first],
    }
    draft = replace(
        original,
        local_to_canonical_type_ids=swapped,
        integrity_sha256="",
    )
    drifted = replace(
        draft,
        integrity_sha256=sha256_json(draft.integrity_payload()),
    )
    serialized = json.dumps(
        drifted.to_private_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    restored_payload = json.loads(serialized)
    restored_payload["visible_type_card_order"] = tuple(
        restored_payload["visible_type_card_order"]
    )
    restored = type(original)(**restored_payload)
    _require(
        restored == drifted,
        "binding_drift_restore_mismatch",
    )
    return _run_technical_failure_case(
        authorities,
        case_id="goal17_mapping_receipt_drift",
        failure_stage="binding_validation",
        exact_invalid_input={
            "model_output": {"plausible_types": [first]},
            "response_profile": asdict(authorities.response_profile),
            "type_first_candidate": asdict(
                authorities.type_first_candidate
            ),
            "mapping_receipt": asdict(restored),
        },
        expected_error_code="mapping_receipt_mismatch",
    )


def _prove_pack_projection_drift(
    authorities: _Authorities,
) -> dict[str, Any]:
    original = authorities.mapping_receipt
    semantic_pack_identity = copy.deepcopy(
        original.semantic_pack_identity
    )
    semantic_pack_identity["integrity_sha256"] = "0" * 64
    draft = replace(
        original,
        semantic_pack_identity=semantic_pack_identity,
        integrity_sha256="",
    )
    drifted = replace(
        draft,
        integrity_sha256=sha256_json(draft.integrity_payload()),
    )
    return _run_technical_failure_case(
        authorities,
        case_id="goal17_pack_projection_drift",
        failure_stage="binding_validation",
        exact_invalid_input={
            "model_output": {"plausible_types": ["type_1"]},
            "response_profile": asdict(authorities.response_profile),
            "type_first_candidate": asdict(
                authorities.type_first_candidate
            ),
            "mapping_receipt": asdict(drifted),
        },
        expected_error_code="pack_projection_drift",
    )


def _prove_exact_option_restoration_mismatch(
    authorities: _Authorities,
    *,
    evidence: Any,
) -> dict[str, Any]:
    selected = evidence.expansion.selected_typed_option_id
    replacement = next(
        (
            option.typed_option_id
            for option in authorities.compilation.typed_options
            if option.typed_option_id != selected
        ),
        None,
    )
    _require(
        selected is not None and replacement is not None,
        "restoration_fixture_options_invalid",
    )
    return _run_technical_failure_case(
        authorities,
        case_id="goal17_exact_option_restoration_mismatch",
        failure_stage="decision_expansion",
        exact_invalid_input={
            "model_output": {"plausible_types": ["type_1"]},
            "supplied_selected_typed_option_id": replacement,
        },
        expected_error_code="exact_code_owned_typed_option_mismatch",
    )


def _matching_complete_options_total(
    authorities: _Authorities,
    *,
    type_key: str,
) -> int:
    input_type_id = (
        authorities.mapping_receipt.local_to_canonical_type_ids[
            type_key
        ]
    )
    return sum(
        1
        for option in authorities.compilation.typed_options
        if (
            option.input_type_id == input_type_id
            and option.materializability_receipt.status
            == "materializable"
            and option.materializability_receipt.typed_inputs_total == 1
            and option.materializability_receipt.unclassified_inputs_total
            == 0
        )
    )


def _terminal_envelope(
    answer: dict[str, Any],
    *,
    case_id: str,
) -> dict[str, Any]:
    return {
        "id": f"simulated:{case_id}",
        "model": MODEL_ID,
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        answer,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        allow_nan=False,
                    ),
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }


@contextmanager
def _forbid_transport(
    adapter: Any,
    *,
    attempts: list[str],
) -> Iterator[None]:
    adapter_type = type(adapter)
    original = adapter_type.invoke_native_once

    def _forbidden(*_args, **_kwargs):
        attempts.append("invoke_native_once")
        raise TypeFirstZeroCallE2EError("transport_boundary_invoked")

    adapter_type.invoke_native_once = _forbidden
    try:
        yield
    finally:
        adapter_type.invoke_native_once = original


def _manifest_cases() -> dict[str, dict[str, Any]]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    cases = payload.get("cases") if isinstance(payload, dict) else None
    _require(isinstance(cases, list), "manifest_cases_invalid")
    result = {
        item["case_id"]: item
        for item in cases
        if isinstance(item, dict)
        and isinstance(item.get("case_id"), str)
    }
    _require(len(result) == len(cases), "manifest_case_ids_invalid")
    return result


def _repository_authorities() -> dict[str, Any]:
    owner_files = {
        "packet": "gate2_financial_semantic_v6_packet.py",
        "choice": "gate2_financial_semantic_v6_choice.py",
        "context_linter": (
            "gate2_financial_semantic_v6_context_linter.py"
        ),
        "request_builder": "gate2_model_requests.py",
        "economy": "gate2_economy_budget.py",
        "expansion": "gate2_financial_semantic_v6_expansion.py",
        "evidence": "gate2_financial_semantic_v6_evidence.py",
        "qualification_declaration": (
            "gate2_financial_semantic_v6_context_v2_1_budget_smoke.py"
        ),
    }
    bundle_files = {
        "gate1": "broker_reports_gate1_pipe_bundled.py",
        "gate2_source": (
            "broker_reports_gate2_source_fact_pipe_bundled.py"
        ),
        "gate2_domain": (
            "broker_reports_gate2_domain_source_fact_pipe_bundled.py"
        ),
    }
    return {
        "contract_integrity_sha256": _load_contract_integrity(
            CONTRACT_PATH
        ),
        "owner_source_sha256": {
            owner: _sha256_file(
                SERVICE_ROOT / "broker_reports_gate1" / filename
            )
            for owner, filename in owner_files.items()
        },
        "generated_bundle_sha256": {
            bundle: _sha256_file(
                SERVICE_ROOT / "openwebui_actions" / filename
            )
            for bundle, filename in bundle_files.items()
        },
    }


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_contract_integrity(path: Path) -> str:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise TypeFirstZeroCallE2EError(
                    "contract_json_duplicate_member"
                )
            result[key] = value
        return result

    def reject_non_finite(value: str) -> None:
        raise TypeFirstZeroCallE2EError(
            "contract_json_non_finite:" + value
        )

    try:
        contract = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_non_finite,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TypeFirstZeroCallE2EError(
            "contract_json_invalid"
        ) from exc
    _require(isinstance(contract, dict), "contract_root_invalid")
    supplied = contract.get("integrity_sha256")
    material = {
        key: copy.deepcopy(value)
        for key, value in contract.items()
        if key != "integrity_sha256"
    }
    actual = sha256_json(material)
    _require(
        isinstance(supplied, str)
        and len(supplied) == 64
        and supplied == actual,
        "contract_integrity_mismatch",
    )
    return actual


def _validate_aggregate(value: dict[str, Any]) -> None:
    integrity = value.get("integrity_sha256")
    material = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "integrity_sha256"
    }
    _require(
        value.get("schema_version") == E2E_SCHEMA_VERSION
        and value.get("status") == "passed"
        and integrity == sha256_json(material),
        "aggregate_integrity_invalid",
    )
    accounting = value.get("execution_accounting")
    _require(
        accounting
        == {
            "maximum_provider_calls_per_operation": 1,
            "maximum_fallback_calls_per_operation": 0,
            "provider_calls_authorized_total": 0,
            "fallback_calls_authorized_total": 0,
            "provider_submissions_total": 0,
            "provider_calls_total": 0,
            "provider_responses_total": 0,
            "transport_invocations_total": 0,
            "simulated_terminal_envelopes_total": len(SUCCESS_CASES),
            "repair_total": 0,
            "semantic_repair_total": 0,
            "fallback_total": 0,
            "retry_total": 0,
        },
        "aggregate_execution_accounting_invalid",
    )
    _require(
        value["counts"]["adversarial_cases_total"] >= 15
        and value["counts"][
            "simulated_terminal_envelopes_per_success_case"
        ]
        == 1
        and value["runtime_activation"] is False
        and value["production_admission"] is False,
        "aggregate_contract_invalid",
    )
    _require(
        value["qualification_counter_totals"]
        == {
            "plausible_type_set_exact_total": 5,
            "false_empty_total": 1,
            "false_singleton_total": 2,
            "false_superset_total": 2,
            "wrong_singleton_type_total": 1,
            "false_singleton_typed_total": 2,
            "unsafe_typed_total": 3,
            "safe_under_typing_total": 2,
            "invalid_response_total": 12,
        },
        "aggregate_qualification_counters_invalid",
    )
    forbidden_keys = {
        "exact_private_invalid_input",
        "exact_prepared_request",
        "exact_sealed_request",
        "literal_value",
        "materialized_artifact",
        "simulated_provider_envelope",
        "source_value_ref",
    }
    _require(
        not any(
            forbidden_keys.intersection(item)
            for item in _walk_dicts(value)
        ),
        "aggregate_private_key_present",
    )


def _walk_dicts(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk_dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_dicts(item)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise TypeFirstZeroCallE2EError(code)


def serialize_type_first_zero_call_safe_receipt(
    result: dict[str, Any],
) -> str:
    _validate_aggregate(result)
    return (
        json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )


def render_type_first_goal17_report(
    result: dict[str, Any],
) -> str:
    _validate_aggregate(result)
    counts = result["counts"]
    accounting = result["execution_accounting"]
    counters = result["qualification_counter_totals"]
    fixtures = result[
        "real_compiler_fixture_matching_complete_options"
    ]
    authorities = result["repository_authorities"]
    bundles = authorities["generated_bundle_sha256"]
    return "\n".join(
        (
            "# Broker Reports Gate 2 Type-First inactive implementation — GOAL 17",
            "",
            "Status: **LOCAL IMPLEMENTATION PROOF PASSED; INACTIVE; NOT ADMITTED**.",
            "",
            "This report proves the additive, fail-closed, zero-provider-call local "
            "implementation only. It does not qualify a provider model, activate "
            "runtime behavior, or create a production admission.",
            "",
            "## Exact proof route",
            "",
            "Packet candidate/private mapping → Choice response profile → Context "
            "Linter/sealed request → sealed-only Request Builder → generic OpenAI "
            "prepare/schema binding → one simulated terminal envelope → generic "
            "extraction → parser/Expansion → canonical validator/materializer → "
            "Financial Domain Catalog/Persistence → private Evidence → "
            "serialize/restore/exact replay.",
            "",
            "No native transport, model-client execute method, provider call, "
            "retry, repair, fallback, runtime valve, product consumer or admission "
            "is present in that route.",
            "",
            "## Result counts",
            "",
            "| Measure | Total |",
            "| --- | ---: |",
            f"| Successful full chains | {counts['success_cases_total']} |",
            f"| Exact success replays | {counts['success_evidence_serialize_restore_replay_total']} |",
            f"| Adversarial cases | {counts['adversarial_cases_total']} |",
            f"| Exact technical-failure replays | {counts['technical_failure_serialize_restore_replay_total']} |",
            f"| Parser-invalid responses | {counts['invalid_responses_total']} |",
            f"| Canonical decisions/materializations/snapshots | "
            f"{counts['canonical_decisions_total']} / "
            f"{counts['materialized_records_total']} / "
            f"{counts['financial_domain_snapshots_total']} |",
            "",
            "Real compiler fixtures prove singleton-type cardinalities "
            f"`0 / 1 / 2` as `{fixtures['zero']} / {fixtures['one']} / "
            f"{fixtures['multiple']}` complete validly prebound options.",
            "",
            "Exact technical codes include "
            f"`{result['binding_drift_error_code']}`, "
            f"`{result['pack_projection_drift_error_code']}` and "
            f"`{result['exact_option_restoration_error_code']}`.",
            "",
            "## Comparator diagnostics",
            "",
            "| Counter | Total |",
            "| --- | ---: |",
            *(
                f"| `{name}` | {counters[name]} |"
                for name in QUALIFICATION_COUNTERS
            ),
            "",
            "The adversarial corpus intentionally demonstrates the unresolved "
            "false-singleton hazard: "
            f"`false_singleton_typed_total = {counters['false_singleton_typed_total']}` "
            f"and `unsafe_typed_total = {counters['unsafe_typed_total']}`. "
            "The comparator records this after the "
            "product decision and performs no repair. Therefore these diagnostic "
            "hard-gate values are not an activation pass; production admission "
            "remains empty.",
            "",
            "## Zero-call accounting",
            "",
            "| Counter | Total |",
            "| --- | ---: |",
            f"| Provider calls authorized | {accounting['provider_calls_authorized_total']} |",
            f"| Provider submissions | {accounting['provider_submissions_total']} |",
            f"| Provider responses | {accounting['provider_responses_total']} |",
            f"| Transport invocations | {accounting['transport_invocations_total']} |",
            f"| Retry / repair / semantic repair / fallback | "
            f"{accounting['retry_total']} / {accounting['repair_total']} / "
            f"{accounting['semantic_repair_total']} / "
            f"{accounting['fallback_total']} |",
            f"| Simulated terminal envelopes | "
            f"{accounting['simulated_terminal_envelopes_total']} "
            f"({counts['simulated_terminal_envelopes_per_success_case']} per "
            "successful case) |",
            "",
            "## Repository authority",
            "",
            f"- Contract integrity: `{authorities['contract_integrity_sha256']}`",
            f"- Safe receipt integrity: `{result['integrity_sha256']}`",
            f"- Gate 1 generated bundle: `{bundles['gate1']}`",
            f"- Gate 2 source generated bundle: `{bundles['gate2_source']}`",
            f"- Gate 2 domain generated bundle: `{bundles['gate2_domain']}`",
            "",
            "The three bundle changes are deterministic closed-world copies of "
            "the maintained Broker Reports owner/support modules. Bundle topology "
            "and product consumer count remain unchanged.",
            "",
            "## Reproduction",
            "",
            "From `services/broker-reports-gate1-proof`:",
            "",
            "```text",
            "python scripts/build_type_first_zero_call_e2e_evidence.py --check",
            "python -m pytest -q tests/test_broker_reports_gate2_type_first_e2e.py",
            "```",
            "",
            "The safe receipt contains only allowlisted identities, hashes, "
            "counts, outcome/error classes and zero-call accounting. Private "
            "requests, simulated envelopes, source refs, literals, snapshots and "
            "authority keys are not written to Git.",
            "",
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    result = build_type_first_zero_call_e2e_evidence()
    expected_receipt = serialize_type_first_zero_call_safe_receipt(
        result
    )
    expected_report = render_type_first_goal17_report(result)
    outputs = {
        SAFE_RECEIPT_PATH: expected_receipt,
        REPORT_PATH: expected_report,
    }
    if args.check:
        for path, expected in outputs.items():
            _require(
                path.is_file()
                and path.read_text(encoding="utf-8") == expected,
                f"{path.name}:generated_output_stale",
            )
    else:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        for path, expected in outputs.items():
            path.write_text(expected, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
