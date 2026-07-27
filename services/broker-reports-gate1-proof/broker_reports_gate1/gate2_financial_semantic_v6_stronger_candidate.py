from __future__ import annotations

import copy
from typing import Any

from .gate2_financial_evidence_materialization_contracts import sha256_json
from .gate2_financial_semantic_v6_execution_identity import (
    V6_EXACT_MODEL_ID,
    V6_QUALIFICATION_REQUEST_PROFILE,
)
from .gate2_financial_semantic_v6_qualification import (
    V6_QUALIFICATION_PUBLICATION_HASH,
    Gate2FinancialSemanticV6QualificationFixture,
    Gate2FinancialSemanticV6QualificationPreflightFactory,
)


V6_GOAL12_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v6_goal12_candidate_v1"
)
V6_GOAL12_POLICY_VERSION = (
    "broker_reports_gate2_financial_semantic_v6_one_stronger_candidate_v1"
)
V6_GOAL12_EXACT_MODEL_ID = "claude-haiku-4-5-20251001"
V6_GOAL12_PROVIDER_PROFILE_ID = "anthropic_claude"

FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV6StrongerCandidatePreflightFactory.create is the "
    "only Goal 12 candidate-selection and zero-call preflight entrypoint"
)
FORBIDDEN = (
    "Goal 12 must not change V6 Prompt content, Pack, benchmark, candidate "
    "compiler, validator, materializer, retry, fallback, repair, production "
    "admissions or more than one exact candidate"
)


class Gate2FinancialSemanticV6StrongerCandidateError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def financial_semantic_v6_goal12_candidate_program() -> dict[str, Any]:
    return {
        "schema_version": V6_GOAL12_SCHEMA_VERSION,
        "policy_version": V6_GOAL12_POLICY_VERSION,
        "prerequisite_product_gate": "MODEL_NOT_SAFE_FOR_SHADOW",
        "architecture": "FROZEN",
        "variable_changed": "exact_candidate",
        "candidates_total": 1,
        "exact_model_id": V6_GOAL12_EXACT_MODEL_ID,
        "provider_profile_id": V6_GOAL12_PROVIDER_PROFILE_ID,
        "request_profile": V6_QUALIFICATION_REQUEST_PROFILE,
        "same_v6_workload": True,
        "base_v6_publication_hash": V6_QUALIFICATION_PUBLICATION_HASH,
        "provider_attempts_total": 1,
        "semantic_provider_calls_total": 10,
        "technical_provider_calls_total": 0,
        "fallback_total": 0,
        "repair_total": 0,
        "hidden_retry_total": 0,
        "production_admissions": [],
    }


V6_GOAL12_CANDIDATE_PROGRAM_HASH = sha256_json(
    financial_semantic_v6_goal12_candidate_program()
)


class Gate2FinancialSemanticV6StrongerCandidatePreflightFactory:
    def create(
        self,
        *,
        fixture: Gate2FinancialSemanticV6QualificationFixture,
        repository_revision: str,
        stage_action: dict[str, Any],
        published_model_ids: set[str],
        nano_terminal_receipt: dict[str, Any],
    ) -> dict[str, Any]:
        _validate_nano_prerequisite(nano_terminal_receipt)
        base = Gate2FinancialSemanticV6QualificationPreflightFactory().create(
            fixture=fixture,
            repository_revision=repository_revision,
            stage_action=stage_action,
            published_model_ids=published_model_ids,
            exact_model_id=V6_GOAL12_EXACT_MODEL_ID,
            provider_profile_id=V6_GOAL12_PROVIDER_PROFILE_ID,
        )
        identity = base["exact_identity"]
        if (
            identity["model_provider"]["exact_model_id"]
            != V6_GOAL12_EXACT_MODEL_ID
            or identity["model_provider"]["provider_profile_id"]
            != V6_GOAL12_PROVIDER_PROFILE_ID
            or identity.get("candidate_experiment")
            != {
                "architecture": "FROZEN",
                "variable_changed": "exact_candidate",
                "same_v6_workload": True,
                "base_v6_publication_hash": V6_QUALIFICATION_PUBLICATION_HASH,
            }
            or base["authorization"]["exact_model_id"]
            != V6_GOAL12_EXACT_MODEL_ID
        ):
            _fail("financial_semantic_v6_goal12_candidate_identity_invalid")

        receipt: dict[str, Any] = {
            "schema_version": V6_GOAL12_SCHEMA_VERSION,
            "policy_version": V6_GOAL12_POLICY_VERSION,
            "status": "passed",
            "preflight_only": True,
            "acceptance": {
                "architecture": "FROZEN",
                "one_new_candidate": "EXACT",
                "model_comparison": "SAME_V6_WORKLOAD",
                "provider_calls": "ZERO",
            },
            "candidate_program": financial_semantic_v6_goal12_candidate_program(),
            "candidate_program_hash": V6_GOAL12_CANDIDATE_PROGRAM_HASH,
            "nano_prerequisite": {
                "product_gate": nano_terminal_receipt["product_gate"],
                "terminal_receipt_integrity": (
                    nano_terminal_receipt["integrity_sha256"]
                ),
                "attempts_total": nano_terminal_receipt[
                    "attempt_accounting"
                ]["provider_attempts_total"],
                "hidden_retry_total": nano_terminal_receipt[
                    "attempt_accounting"
                ]["hidden_retry_total"],
            },
            "exact_identity": copy.deepcopy(identity),
            "authorization": copy.deepcopy(base["authorization"]),
            "stage": copy.deepcopy(base["stage"]),
            "routes": copy.deepcopy(base["routes"]),
            "budget": copy.deepcopy(base["budget"]),
            "evidence_contract": copy.deepcopy(base["evidence_contract"]),
            "case_preflights": copy.deepcopy(base["case_preflights"]),
            "execution_accounting": copy.deepcopy(
                base["execution_accounting"]
            ),
            "production_admissions_total": 0,
        }
        receipt["integrity_sha256"] = sha256_json(receipt)
        return receipt


def _validate_nano_prerequisite(receipt: dict[str, Any]) -> None:
    material = {
        key: value for key, value in receipt.items() if key != "integrity_sha256"
    }
    accounting = receipt.get("attempt_accounting") or {}
    identity = receipt.get("exact_identity") or {}
    model_provider = identity.get("model_provider") or {}
    if (
        receipt.get("execution_state") != "terminal"
        or receipt.get("product_gate") != "MODEL_NOT_SAFE_FOR_SHADOW"
        or receipt.get("integrity_sha256") != sha256_json(material)
        or accounting.get("provider_attempts_total") != 1
        or accounting.get("hidden_retry_total") != 0
        or model_provider.get("exact_model_id") != V6_EXACT_MODEL_ID
        or receipt.get("production_admissions_total") != 0
    ):
        _fail("financial_semantic_v6_goal12_nano_prerequisite_invalid")


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV6StrongerCandidateError(code)
