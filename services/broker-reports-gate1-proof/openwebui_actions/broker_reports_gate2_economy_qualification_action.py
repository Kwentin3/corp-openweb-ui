"""
title: Broker Reports Gate 2 Economy Qualification Policy
author: Alpha Soft
version: 1.2.0
required_open_webui_version: 0.9.6
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any


ACTION_ID = "broker_reports_gate2_economy_qualification_action"
FACTORY_REQUIRED = (
    "The repository Gate2EconomyQualificationPolicyFactory snapshot is "
    "the only source for this qualification-only Action"
)
FORBIDDEN = (
    "This Action must not call providers, admit production models, enable "
    "paid tools, fallback or repair, or change Gate 1 visual behavior"
)

POLICY_SNAPSHOT: dict[str, Any] = {
    "schema_version": ("broker_reports_gate2_economy_qualification_policy_v1"),
    "scope": "qualification_only",
    "model_policy": {
        "policy_id": "broker_reports_economy_model_policy_v1",
        "policy_version": "1.5.0",
        "policy_schema_version": ("broker_reports_economy_model_policy_v2"),
        "policy_hash": (
            "467ce6050a69ff96f1a3cae4e2f37d8c4c62fb2dd69c757208d9ee9813698714"
        ),
    },
    "workload_policy": {
        "policy_id": "broker_reports_gate2_economy_workload_policy_v2",
        "policy_version": "1.5.0",
        "policy_schema_version": ("broker_reports_gate2_economy_workload_policy_v2"),
        "policy_hash": (
            "08449e2b11951f7c303885d29504b06171d739a5bc85e44037575600fac414a2"
        ),
    },
    "model_controls": {
        "gpt-5.4-nano-2026-03-17": {
            "provider_profile_id": "openai_gpt",
            "reasoning_policy": "disabled",
            "paid_tools_allowed": False,
        },
        "models/gemini-3.1-flash-lite": {
            "provider_profile_id": "google_gemini",
            "reasoning_policy": "minimal",
            "paid_tools_allowed": False,
        },
        "models/gemini-3.5-flash-lite": {
            "provider_profile_id": "google_gemini",
            "reasoning_policy": "minimal",
            "paid_tools_allowed": False,
        },
        "claude-haiku-4-5-20251001": {
            "provider_profile_id": "anthropic_claude",
            "reasoning_policy": "disabled",
            "paid_tools_allowed": False,
        },
    },
    "workload_routes": {
        "gate2_source": {
            "qualification_candidate_exact_model_ids": [
                "models/gemini-3.1-flash-lite",
                "models/gemini-3.5-flash-lite",
            ],
            "production_admissions": [],
        },
        "gate2_domain": {
            "qualification_candidate_exact_model_ids": [
                "models/gemini-3.1-flash-lite",
                "models/gemini-3.5-flash-lite",
            ],
            "production_admissions": [],
        },
        "gate2_financial_evidence": {
            "qualification_candidate_exact_model_ids": [
                "gpt-5.4-nano-2026-03-17",
                "claude-haiku-4-5-20251001",
                "models/gemini-3.1-flash-lite",
                "models/gemini-3.5-flash-lite",
            ],
            "production_admissions": [],
        },
        "gate2_financial_checksum": {
            "qualification_candidate_exact_model_ids": [
                "claude-haiku-4-5-20251001",
                "gpt-5.4-nano-2026-03-17",
                "models/gemini-3.1-flash-lite",
                "models/gemini-3.5-flash-lite",
            ],
            "production_admissions": [],
        },
    },
    "qualification_controls": {
        "receipt_identity_fields": [
            "provider_route_revision",
            "input_contract_version",
            "output_contract_version",
            "prompt_version",
            "adapter_projection_revision",
            "canonical_validator_revision",
        ],
        "fallback_calls_allowed": 0,
        "repair_attempts_allowed": 0,
        "paid_tools_allowed": False,
    },
    "qualification_policy_hash": (
        "49531f672018665d0fed4fafb4ff1c4cf4d29c2ef6a47a3c1171a766d09cab34"
    ),
}

V6_QUALIFICATION_SNAPSHOT: dict[str, Any] = {
    "schema_version": (
        "broker_reports_gate2_financial_semantic_v6_qualification_preflight_v1"
    ),
    "policy_version": "broker_reports_gate2_financial_semantic_v6_one_attempt_v1",
    "scope": "qualification_only",
    "workload_identity": "financial_semantic_v6_qualification_v1",
    "exact_model_id": "gpt-5.4-nano-2026-03-17",
    "provider_profile_id": "openai_gpt",
    "attempts_total": 1,
    "semantic_provider_calls_total": 10,
    "technical_provider_calls_total": 0,
    "fallback_total": 0,
    "repair_total": 0,
    "hidden_retry_total": 0,
    "production_admissions": [],
}
V6_QUALIFICATION_SNAPSHOT_HASH = hashlib.sha256(
    json.dumps(
        V6_QUALIFICATION_SNAPSHOT,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
).hexdigest()


class Action:
    """Read-only policy publication boundary for controlled qualification."""

    async def action(
        self,
        body: dict,
        __id__: str | None = None,
        __event_emitter__=None,
        **_kwargs,
    ) -> dict[str, Any]:
        if __id__ not in {None, ACTION_ID}:
            raise ValueError("economy_qualification_action_id_mismatch")
        await self._emit(
            __event_emitter__,
            "Qualification-only economy policy verified.",
        )
        return {
            "content": (
                "Broker Reports Gate 2 qualification-only policy 1.5.0 "
                "is live. Production admissions remain empty."
            ),
            "broker_reports_gate2_economy_qualification_policy": (
                copy.deepcopy(POLICY_SNAPSHOT)
            ),
            "broker_reports_gate2_financial_semantic_v6_qualification": (
                copy.deepcopy(V6_QUALIFICATION_SNAPSHOT)
            ),
            "broker_reports_gate2_financial_semantic_v6_qualification_hash": (
                V6_QUALIFICATION_SNAPSHOT_HASH
            ),
        }

    async def _emit(self, emitter, description: str) -> None:
        if emitter is not None:
            await emitter(
                {
                    "type": "status",
                    "data": {
                        "description": description,
                        "done": True,
                        "hidden": False,
                    },
                }
            )
