from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from .gate2_financial_domain_catalog import (
    Gate2FinancialDomainCatalogFactory,
)
from .gate2_financial_domain_contracts import FinancialDomainAccessContext
from .gate2_financial_domain_persistence import (
    Gate2FinancialDomainPersistenceFactory,
)
from .gate2_financial_evidence_materialization_contracts import sha256_json
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_semantic_v6_context_linter import (
    Gate2FinancialSemanticV6ContextLinterFactory,
    validate_financial_semantic_v6_context_v2_1_sealed_request,
)
from .gate2_financial_semantic_v6_evidence import (
    Gate2FinancialSemanticV6DecisionEvidenceFactory,
    replay_financial_semantic_v6_context_v2_1_decision,
    restore_financial_semantic_v6_context_v2_1_private_evidence,
    serialize_financial_semantic_v6_context_v2_1_private_evidence,
)
from .gate2_financial_semantic_v6_prompt import V6_SEMANTIC_SYSTEM_PROMPT
from .gate2_financial_semantic_v6_smoke_report import (
    CONTEXT_V2_1_PROVIDER_PROOF_CASES,
    CONTEXT_V2_1_PROVIDER_PROOF_PROFILES,
    Gate2FinancialSemanticV6ContextV21ReportCaseEvidence,
    Gate2FinancialSemanticV6TransparentSmokeReportFactory,
    _issue_context_v2_1_provider_case_evidence,
)
from .gate2_model_contracts import gate2_provider_profile
from .gate2_model_requests import (
    FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_LOCAL_PROOF_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)
from .gate2_provider_adapters import (
    CONTEXT_V2_1_LOCAL_SCHEMA_PROJECTION_POLICY_VERSION,
    Gate2ProviderAdapterFactory,
)


CONTEXT_V2_1_PROVIDER_PROOF_SCHEMA_VERSION = (
    "broker_reports_gate2_context_v2_1_provider_case_proof_v1"
)
CONTEXT_V2_1_PROVIDER_PROOF_POLICY_VERSION = (
    "broker_reports_gate2_context_v2_1_three_provider_zero_call_v1"
)
CONTEXT_V2_1_LOCAL_PROJECTION_MODEL_IDS = {
    "openai_gpt": "local-proof-openai-profile-v1",
    "anthropic_claude": "local-proof-anthropic-profile-v1",
    "google_gemini": "local-proof-google-profile-v1",
}
FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV6ContextV21ProviderProofFactory.create_case "
    "composes the existing linter, request builder, provider adapter, Choice, "
    "expansion, materializer, persistence and transparent-report authorities"
)
FORBIDDEN = (
    "The Context V2.1 provider proof must not call provider transport, repair "
    "semantic output, retry, fall back, activate runtime or mint a second "
    "Packet, Choice, materialization, persistence or report authority"
)

_CREATED_AT = "2026-07-29T00:00:00+00:00"
_ACCOUNTING = {
    "provider_calls_total": 0,
    "semantic_repair_total": 0,
    "fallback_total": 0,
    "retry_total": 0,
}


class Gate2FinancialSemanticV6ContextV21ProviderProofError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2FinancialSemanticV6ContextV21ProviderCaseProof:
    schema_version: str
    policy_version: str
    active: bool
    transport_eligible: bool
    case_id: str
    taxonomy_state: str
    provider_profile_id: str
    provider_adapter_id: str
    provider_adapter_version: str
    local_projection_model_id: str
    schema_projection_policy_version: str
    adapter_canonical_schema_hash: str
    adapter_adapted_schema_hash: str
    sealed_request: dict[str, Any]
    exact_final_provider_request: dict[str, Any]
    provider_visible_response_schema: dict[str, Any]
    simulated_provider_response: dict[str, Any]
    adapter_extracted_output: Any
    normalized_canonical_answer: dict[str, Any]
    expected_answer: dict[str, Any]
    total_materialization: dict[str, Any]
    serialized_private_evidence_hash: str
    restored_private_evidence_hash: str
    replay_materialized_artifact_hash: str
    serialized_snapshot: str
    restored_snapshot_integrity_hash: str
    replay_snapshot_integrity_hash: str
    restore_exact: bool
    replay_exact: bool
    transparent_report_case_evidence: (
        Gate2FinancialSemanticV6ContextV21ReportCaseEvidence | None
    ) = field(repr=False, compare=False)
    transparent_report_projection: dict[str, Any]
    execution_accounting: dict[str, int]
    integrity_hash: str

    def integrity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "active": self.active,
            "transport_eligible": self.transport_eligible,
            "case_id": self.case_id,
            "taxonomy_state": self.taxonomy_state,
            "provider_profile_id": self.provider_profile_id,
            "provider_adapter_id": self.provider_adapter_id,
            "provider_adapter_version": self.provider_adapter_version,
            "local_projection_model_id": self.local_projection_model_id,
            "schema_projection_policy_version": (
                self.schema_projection_policy_version
            ),
            "adapter_canonical_schema_hash": (
                self.adapter_canonical_schema_hash
            ),
            "adapter_adapted_schema_hash": (
                self.adapter_adapted_schema_hash
            ),
            "sealed_request": copy.deepcopy(self.sealed_request),
            "exact_final_provider_request": copy.deepcopy(
                self.exact_final_provider_request
            ),
            "provider_visible_response_schema": copy.deepcopy(
                self.provider_visible_response_schema
            ),
            "simulated_provider_response": copy.deepcopy(
                self.simulated_provider_response
            ),
            "adapter_extracted_output": copy.deepcopy(
                self.adapter_extracted_output
            ),
            "normalized_canonical_answer": copy.deepcopy(
                self.normalized_canonical_answer
            ),
            "expected_answer": copy.deepcopy(self.expected_answer),
            "total_materialization": copy.deepcopy(
                self.total_materialization
            ),
            "serialized_private_evidence_hash": (
                self.serialized_private_evidence_hash
            ),
            "restored_private_evidence_hash": (
                self.restored_private_evidence_hash
            ),
            "replay_materialized_artifact_hash": (
                self.replay_materialized_artifact_hash
            ),
            "serialized_snapshot": self.serialized_snapshot,
            "restored_snapshot_integrity_hash": (
                self.restored_snapshot_integrity_hash
            ),
            "replay_snapshot_integrity_hash": (
                self.replay_snapshot_integrity_hash
            ),
            "restore_exact": self.restore_exact,
            "replay_exact": self.replay_exact,
            "transparent_report_projection": copy.deepcopy(
                self.transparent_report_projection
            ),
            "execution_accounting": copy.deepcopy(
                self.execution_accounting
            ),
        }

    def to_private_dict(self) -> dict[str, Any]:
        return {
            **self.integrity_payload(),
            "integrity_hash": self.integrity_hash,
        }

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "active": self.active,
            "transport_eligible": self.transport_eligible,
            "case_id": self.case_id,
            "taxonomy_state": self.taxonomy_state,
            "provider_profile_id": self.provider_profile_id,
            "provider_adapter_id": self.provider_adapter_id,
            "provider_adapter_version": self.provider_adapter_version,
            "schema_projection_policy_version": (
                self.schema_projection_policy_version
            ),
            "adapter_canonical_schema_hash": (
                self.adapter_canonical_schema_hash
            ),
            "adapter_adapted_schema_hash": (
                self.adapter_adapted_schema_hash
            ),
            "sealed_request_hash": sha256_json(self.sealed_request),
            "final_provider_request_hash": sha256_json(
                self.exact_final_provider_request
            ),
            "provider_visible_schema_hash": sha256_json(
                self.provider_visible_response_schema
            ),
            "materialized_artifact_hash": (
                self.total_materialization["canonical_artifact_hash"]
            ),
            "serialized_private_evidence_hash": (
                self.serialized_private_evidence_hash
            ),
            "restored_private_evidence_hash": (
                self.restored_private_evidence_hash
            ),
            "replay_materialized_artifact_hash": (
                self.replay_materialized_artifact_hash
            ),
            "restored_snapshot_integrity_hash": (
                self.restored_snapshot_integrity_hash
            ),
            "replay_snapshot_integrity_hash": (
                self.replay_snapshot_integrity_hash
            ),
            "restore_exact": self.restore_exact,
            "replay_exact": self.replay_exact,
            "execution_accounting": copy.deepcopy(
                self.execution_accounting
            ),
            "integrity_hash": self.integrity_hash,
        }


class Gate2FinancialSemanticV6ContextV21ProviderProofFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
        snapshot_authority_key: bytes,
    ) -> None:
        self.registry = registry
        self._snapshot_authority_key = bytes(snapshot_authority_key)

    def create_case(
        self,
        *,
        case: Any,
        provider_profile_id: str,
        expected_answer: dict[str, Any],
        simulated_provider_response: dict[str, Any],
    ) -> Gate2FinancialSemanticV6ContextV21ProviderCaseProof:
        proof = self._create_unissued_case(
            case=case,
            provider_profile_id=provider_profile_id,
            expected_answer=copy.deepcopy(expected_answer),
            simulated_provider_response=copy.deepcopy(
                simulated_provider_response
            ),
        )
        recomputed = self._create_unissued_case(
            case=case,
            provider_profile_id=provider_profile_id,
            expected_answer=copy.deepcopy(expected_answer),
            simulated_provider_response=copy.deepcopy(
                simulated_provider_response
            ),
        )
        if proof != recomputed:
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "proof_integrity_invalid"
            )
        report_case_evidence = (
            _issue_context_v2_1_provider_case_evidence(
                validated_projection=proof.transparent_report_projection,
            )
        )
        if (
            report_case_evidence.to_dict()
            != proof.transparent_report_projection
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "proof_integrity_invalid"
            )
        return replace(
            proof,
            transparent_report_case_evidence=report_case_evidence,
        )

    def _create_unissued_case(
        self,
        *,
        case: Any,
        provider_profile_id: str,
        expected_answer: dict[str, Any],
        simulated_provider_response: dict[str, Any],
    ) -> Gate2FinancialSemanticV6ContextV21ProviderCaseProof:
        case_id = str(getattr(case, "case_id", ""))
        taxonomy_state = CONTEXT_V2_1_PROVIDER_PROOF_CASES.get(case_id)
        if (
            taxonomy_state is None
            or provider_profile_id
            not in CONTEXT_V2_1_PROVIDER_PROOF_PROFILES
            or getattr(case, "route", None) != "semantic_model"
            or not isinstance(expected_answer, dict)
            or not isinstance(simulated_provider_response, dict)
        ):
            _fail("financial_semantic_v6_context_v2_1_proof_input_invalid")
        result = self._run_once(
            case=case,
            provider_profile_id=provider_profile_id,
            expected_answer=copy.deepcopy(expected_answer),
            simulated_provider_response=copy.deepcopy(
                simulated_provider_response
            ),
        )
        profile = result["profile"]
        totality = result["totality"]
        persisted_snapshot_hash = sha256_json(
            json.loads(result["serialized_snapshot"])
        )
        report = (
            Gate2FinancialSemanticV6TransparentSmokeReportFactory()
            .create_context_v2_1_provider_case(
                case_id=case_id,
                provider_profile=profile,
                sealed_request=result["sealed_request"],
                prepared_request=result["prepared_request"],
                canonical_schema=(
                    case.choice_contract.context_v2_1_response_profile
                    .canonical_schema()
                ),
                local_projection_model_id=(
                    result["prepared_request"].form_data["model"]
                ),
                adapter_extracted_output=result["extracted_output"],
                normalized_answer=result["normalized_answer"],
                expected_answer=expected_answer,
                materialized_artifact_hash=(
                    totality.canonical_artifact_hash
                ),
                serialized_private_evidence_hash=(
                    result["serialized_private_evidence_hash"]
                ),
                restored_private_evidence_hash=(
                    result["restored_private_evidence_hash"]
                ),
                replay_materialized_artifact_hash=(
                    result["replay_materialized_artifact_hash"]
                ),
                persisted_snapshot_hash=persisted_snapshot_hash,
                replay_snapshot_integrity_hash=(
                    result["replay_snapshot_integrity_hash"]
                ),
                restore_exact=result["restore_exact"],
                replay_exact=result["replay_exact"],
            )
        )
        draft = Gate2FinancialSemanticV6ContextV21ProviderCaseProof(
            schema_version=CONTEXT_V2_1_PROVIDER_PROOF_SCHEMA_VERSION,
            policy_version=CONTEXT_V2_1_PROVIDER_PROOF_POLICY_VERSION,
            active=False,
            transport_eligible=False,
            case_id=case_id,
            taxonomy_state=taxonomy_state,
            provider_profile_id=profile.profile_id,
            provider_adapter_id=profile.adapter_id,
            provider_adapter_version=profile.adapter_version,
            local_projection_model_id=(
                CONTEXT_V2_1_LOCAL_PROJECTION_MODEL_IDS[profile.profile_id]
            ),
            schema_projection_policy_version=(
                result["prepared_request"].projection_policy_version
            ),
            adapter_canonical_schema_hash=(
                result["prepared_request"].canonical_schema_hash
            ),
            adapter_adapted_schema_hash=(
                result["prepared_request"].adapted_schema_hash
            ),
            sealed_request=asdict(result["sealed_request"]),
            exact_final_provider_request=copy.deepcopy(
                result["prepared_request"].form_data
            ),
            provider_visible_response_schema=copy.deepcopy(
                result["prepared_request"].provider_visible_schema
            ),
            simulated_provider_response=copy.deepcopy(
                simulated_provider_response
            ),
            adapter_extracted_output=copy.deepcopy(
                result["extracted_output"]
            ),
            normalized_canonical_answer=copy.deepcopy(
                result["normalized_answer"]
            ),
            expected_answer=copy.deepcopy(expected_answer),
            total_materialization=totality.to_private_dict(),
            serialized_private_evidence_hash=(
                result["serialized_private_evidence_hash"]
            ),
            restored_private_evidence_hash=(
                result["restored_private_evidence_hash"]
            ),
            replay_materialized_artifact_hash=(
                result["replay_materialized_artifact_hash"]
            ),
            serialized_snapshot=result["serialized_snapshot"],
            restored_snapshot_integrity_hash=(
                result["restored_snapshot_integrity_hash"]
            ),
            replay_snapshot_integrity_hash=(
                result["replay_snapshot_integrity_hash"]
            ),
            restore_exact=result["restore_exact"],
            replay_exact=result["replay_exact"],
            transparent_report_case_evidence=None,
            transparent_report_projection=report,
            execution_accounting=copy.deepcopy(_ACCOUNTING),
            integrity_hash="",
        )
        return replace(
            draft,
            integrity_hash=sha256_json(draft.integrity_payload()),
        )

    def _run_once(
        self,
        *,
        case: Any,
        provider_profile_id: str,
        expected_answer: dict[str, Any],
        simulated_provider_response: dict[str, Any],
    ) -> dict[str, Any]:
        evidence_bundle = getattr(case, "evidence_bundle", None)
        compilation = getattr(case, "compilation", None)
        packet = getattr(case, "packet", None)
        choice_contract = getattr(case, "choice_contract", None)
        source_package = getattr(getattr(case, "scope", None), "source_package", None)
        if any(
            value is None
            for value in (
                evidence_bundle,
                compilation,
                packet,
                choice_contract,
                source_package,
            )
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "proof_authority_missing"
            )
        response_profile = choice_contract.context_v2_1_response_profile
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "strict": True,
                "schema": response_profile.canonical_schema(),
            },
        }
        serialized_context = json.dumps(
            packet.context_v2_candidate.payload,
            ensure_ascii=False,
            sort_keys=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        sealed_request = Gate2FinancialSemanticV6ContextLinterFactory(
            registry=self.registry
        ).create_context_v2_1(
            packet=packet,
            choice_contract=choice_contract,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            system_message=V6_SEMANTIC_SYSTEM_PROMPT,
            serialized_context=serialized_context,
            response_format=response_format,
            mapping_receipt=packet.context_v2_mapping_receipt,
        )
        validate_financial_semantic_v6_context_v2_1_sealed_request(
            sealed_request=sealed_request,
            packet=packet,
            choice_contract=choice_contract,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            registry=self.registry,
            system_message=V6_SEMANTIC_SYSTEM_PROMPT,
            mapping_receipt=packet.context_v2_mapping_receipt,
        )
        model_id = CONTEXT_V2_1_LOCAL_PROJECTION_MODEL_IDS[
            provider_profile_id
        ]
        form_data = Gate2OpenWebUIRequestBuilder(
            request_profile=(
                FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_LOCAL_PROOF_REQUEST_PROFILE
            )
        ).build_from_sealed_context_v2_1(
            model_visible_request=sealed_request.model_visible_request,
            model_id=model_id,
        )
        profile = gate2_provider_profile(provider_profile_id)
        adapter = Gate2ProviderAdapterFactory(profile=profile).create()
        prepared_request = adapter.prepare_form_data(
            form_data=form_data,
            response_format=sealed_request.response_format,
        )
        if (
            prepared_request.projection_policy_version
            != CONTEXT_V2_1_LOCAL_SCHEMA_PROJECTION_POLICY_VERSION
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "proof_projection_policy_invalid"
            )
        extracted_output = (
            adapter.extract_context_v2_1_prepared_content(
                copy.deepcopy(simulated_provider_response),
                prepared_request=prepared_request,
                canonical_schema=response_profile.canonical_schema(),
                model_visible_request=(
                    sealed_request.model_visible_request
                ),
                local_projection_model_id=model_id,
            )
        )
        exact_evidence = Gate2FinancialSemanticV6DecisionEvidenceFactory(
            registry=self.registry
        ).create_context_v2_1_candidate(
            case_id=case.case_id,
            provider_profile_id=profile.profile_id,
            provider_adapter_id=profile.adapter_id,
            provider_adapter_version=profile.adapter_version,
            local_projection_model_id=model_id,
            sealed_request=sealed_request,
            prepared_request=prepared_request,
            adapter_extracted_output=extracted_output,
            choice_contract=choice_contract,
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
        )
        normalized_answer = exact_evidence.normalized_semantic_choice
        if normalized_answer != expected_answer:
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "proof_expected_answer_mismatch"
            )
        totality = exact_evidence.total_materialization
        serialized_private_evidence = (
            serialize_financial_semantic_v6_context_v2_1_private_evidence(
                private_evidence=exact_evidence.private_evidence,
            )
        )
        restored_private_evidence = (
            restore_financial_semantic_v6_context_v2_1_private_evidence(
                serialized=serialized_private_evidence,
            )
        )
        restore_exact = (
            restored_private_evidence
            == exact_evidence.private_evidence
        )
        if not restore_exact:
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "proof_evidence_restore_mismatch"
            )
        replay = replay_financial_semantic_v6_context_v2_1_decision(
            private_evidence=restored_private_evidence,
            expected_provider_profile_id=profile.profile_id,
            expected_provider_adapter_id=profile.adapter_id,
            expected_provider_adapter_version=profile.adapter_version,
            expected_local_projection_model_id=model_id,
            expected_sealed_request=sealed_request,
            expected_prepared_request=prepared_request,
            choice_contract=choice_contract,
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            registry=self.registry,
        )
        if (
            replay.status != "EXACT"
            or replay.provider_calls_total != 0
            or replay.normalized_semantic_choice != normalized_answer
            or replay.expansion != exact_evidence.expansion
            or replay.total_materialization != totality
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "proof_evidence_replay_mismatch"
            )
        serialized_private_evidence_hash = sha256_json(
            json.loads(serialized_private_evidence)
        )
        access_context = FinancialDomainAccessContext(
            user_ref="user:synthetic-context-v2-1-provider-proof",
            case_ref=f"case:{case.case_id}",
            workspace_ref="workspace:synthetic-context-v2-1-provider-proof",
        )
        snapshot = Gate2FinancialDomainCatalogFactory(
            registry=self.registry,
            snapshot_authority_key=self._snapshot_authority_key,
        ).create(
            materialized_artifacts=(totality.canonical_artifact,),
            source_packages=(source_package,),
            access_context=access_context,
            created_at=_CREATED_AT,
            expires_at=None,
        )
        persistence = Gate2FinancialDomainPersistenceFactory(
            snapshot_authority_key=self._snapshot_authority_key
        )
        serialized_snapshot = persistence.serialize(snapshot=snapshot)
        restored_snapshot = persistence.restore(
            serialized=serialized_snapshot
        )
        if restored_snapshot != snapshot:
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "proof_persistence_mismatch"
            )
        replay_snapshot = Gate2FinancialDomainCatalogFactory(
            registry=self.registry,
            snapshot_authority_key=self._snapshot_authority_key,
        ).create(
            materialized_artifacts=(
                replay.total_materialization.canonical_artifact,
            ),
            source_packages=(source_package,),
            access_context=access_context,
            created_at=_CREATED_AT,
            expires_at=None,
        )
        replay_exact = (
            replay_snapshot == restored_snapshot
            and replay.materialized_artifact_hash
            == totality.canonical_artifact_hash
            and replay.private_evidence_hash
            == restored_private_evidence["private_evidence_hash"]
        )
        if not replay_exact:
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "proof_replay_snapshot_mismatch"
            )
        return {
            "profile": profile,
            "sealed_request": sealed_request,
            "prepared_request": prepared_request,
            "extracted_output": copy.deepcopy(extracted_output),
            "normalized_answer": copy.deepcopy(normalized_answer),
            "expansion": exact_evidence.expansion,
            "totality": totality,
            "serialized_private_evidence_hash": (
                serialized_private_evidence_hash
            ),
            "restored_private_evidence_hash": (
                restored_private_evidence["private_evidence_hash"]
            ),
            "replay_materialized_artifact_hash": (
                replay.materialized_artifact_hash
            ),
            "serialized_snapshot": serialized_snapshot,
            "restored_snapshot_integrity_hash": (
                restored_snapshot.integrity_sha256
            ),
            "replay_snapshot_integrity_hash": (
                replay_snapshot.integrity_sha256
            ),
            "restore_exact": restore_exact,
            "replay_exact": replay_exact,
        }


def validate_financial_semantic_v6_context_v2_1_provider_case_proof(
    *,
    proof: Gate2FinancialSemanticV6ContextV21ProviderCaseProof,
    factory: Gate2FinancialSemanticV6ContextV21ProviderProofFactory,
    case: Any,
    expected_answer: dict[str, Any],
    simulated_provider_response: dict[str, Any],
) -> None:
    if not isinstance(
        proof,
        Gate2FinancialSemanticV6ContextV21ProviderCaseProof,
    ):
        _fail("financial_semantic_v6_context_v2_1_proof_invalid")
    expected = factory._create_unissued_case(
        case=case,
        provider_profile_id=proof.provider_profile_id,
        expected_answer=expected_answer,
        simulated_provider_response=simulated_provider_response,
    )
    if proof != expected:
        _fail("financial_semantic_v6_context_v2_1_proof_integrity_invalid")
    report_case_evidence = proof.transparent_report_case_evidence
    if (
        type(report_case_evidence)
        is not Gate2FinancialSemanticV6ContextV21ReportCaseEvidence
        or report_case_evidence.to_dict()
        != proof.transparent_report_projection
    ):
        _fail("financial_semantic_v6_context_v2_1_proof_integrity_invalid")


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV6ContextV21ProviderProofError(code)
