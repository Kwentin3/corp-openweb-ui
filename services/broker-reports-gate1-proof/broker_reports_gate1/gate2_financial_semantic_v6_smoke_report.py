from __future__ import annotations

import copy
import hashlib
import json
from typing import Any


V6_TRANSPARENT_SMOKE_CASE_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v6_transparent_smoke_case_v1"
)
V6_TRANSPARENT_SMOKE_REPORT_VERSION = (
    "broker_reports_gate2_financial_semantic_v6_transparent_smoke_report_v1"
)
CONTEXT_V2_1_PROVIDER_PROOF_CASE_SCHEMA_VERSION = (
    "broker_reports_gate2_context_v2_1_provider_proof_case_v1"
)
CONTEXT_V2_1_PROVIDER_PROOF_REPORT_SCHEMA_VERSION = (
    "broker_reports_gate2_context_v2_1_three_provider_local_proof_v1"
)
CONTEXT_V2_1_PROVIDER_PROOF_CASES = {
    "syn_successor_v2_unique_cash": "typed_safe_1",
    "syn_successor_v2_no_registry_type": "no_type_0",
    "syn_successor_v2_multiple_compatible": "ambiguous_type_2plus",
    "syn_successor_v2_detail_vs_subtotal": (
        "single_type_no_safe_record"
    ),
}
CONTEXT_V2_1_PROVIDER_PROOF_PROFILES = (
    "openai_gpt",
    "anthropic_claude",
    "google_gemini",
)
CONTEXT_V2_1_PROVIDER_PROOF_PROFILE_AUTHORITY = {
    "openai_gpt": {
        "provider_id": "openai",
        "adapter_id": "openai_response_format",
        "adapter_version": "1.1.0",
        "structured_output_mode": (
            "openwebui_response_format_json_schema"
        ),
        "local_projection_model_id": "local-proof-openai-profile-v1",
    },
    "anthropic_claude": {
        "provider_id": "anthropic",
        "adapter_id": "anthropic_native_messages",
        "adapter_version": "1.2.0",
        "structured_output_mode": (
            "openwebui_anthropic_output_config_json_schema"
        ),
        "local_projection_model_id": (
            "local-proof-anthropic-profile-v1"
        ),
    },
    "google_gemini": {
        "provider_id": "google",
        "adapter_id": "gemini_response_format",
        "adapter_version": "1.5.0",
        "structured_output_mode": (
            "openwebui_response_format_json_schema"
        ),
        "local_projection_model_id": "local-proof-google-profile-v1",
    },
}
CONTEXT_V2_1_PROVIDER_PROOF_EXPECTED_ANSWERS = {
    "syn_successor_v2_unique_cash": {
        "disposition": "typed_input",
        "typed_option_id": (
            "financial-typed-option:ddcf7fde28240dc392c4f143abb40d3f"
        ),
    },
    "syn_successor_v2_no_registry_type": {
        "disposition": "unclassified_financial_input",
        "reason_code": "no_registry_type",
    },
    "syn_successor_v2_multiple_compatible": {
        "disposition": "unclassified_financial_input",
        "reason_code": "ambiguous_registry_type",
    },
    "syn_successor_v2_detail_vs_subtotal": {
        "disposition": "unclassified_financial_input",
        "reason_code": "single_registry_type_no_safe_record",
    },
}
CONTEXT_V2_1_PROVIDER_PROOF_EXTRACTED_OUTPUTS = {
    "syn_successor_v2_unique_cash": {"choice": "choice_2"},
    "syn_successor_v2_no_registry_type": {
        "choice": "unclassified",
        "reason": "no_registry_type",
    },
    "syn_successor_v2_multiple_compatible": {
        "choice": "unclassified",
        "reason": "ambiguous_registry_type",
    },
    "syn_successor_v2_detail_vs_subtotal": {
        "choice": "unclassified",
        "reason": "single_registry_type_no_safe_record",
    },
}
CONTEXT_V2_1_PROVIDER_PROOF_USER_CONTENT_SHA256 = {
    "syn_successor_v2_unique_cash": (
        "9068537cd35e7ca5f503f5f167440b44ba79f240e442f4c8ede8742c7de8e714"
    ),
    "syn_successor_v2_no_registry_type": (
        "8475b9ce840a4801b4792a347306a5ba85a40a8d10e08e9cfcd80d5b914b1007"
    ),
    "syn_successor_v2_multiple_compatible": (
        "4dd76de2e81a18d12af9c9a96702f975602fc1bece7ddaccc93aabef769984c2"
    ),
    "syn_successor_v2_detail_vs_subtotal": (
        "bfbe343eff9f269cdbe87b677cd8a1657c75c4d7d4fb199c6edb83a79020eba0"
    ),
}
CONTEXT_V2_1_PROVIDER_PROOF_MODEL_VISIBLE_REQUEST_SHA256 = {
    "syn_successor_v2_unique_cash": (
        "68b9ca4e89e39a2ebca45867761d54bc1ed1afbe9d1994ddedd04e55b0982c3e"
    ),
    "syn_successor_v2_no_registry_type": (
        "b2edde39e5ae1b9f1a871db49bdfb619dc5f7c719169ccd42231187cc0963a6a"
    ),
    "syn_successor_v2_multiple_compatible": (
        "303681e6f94e012ba6891950fde6128dd533e23c5783f25a33b4e14efa54a161"
    ),
    "syn_successor_v2_detail_vs_subtotal": (
        "c6f53bdf45df0ccbc26b67c71f48cc9b638d70132ed0f4f156b6e994c6a72116"
    ),
}
CONTEXT_V2_1_PROVIDER_PROOF_SYSTEM_MESSAGE_SHA256 = (
    "a73c8b85514ec2310882b4b03101253233108e0c99d5dcdfd3830256179f6210"
)
V6_TRANSPARENT_SMOKE_CASES = {
    "syn_successor_v2_unique_cash": {
        "smoke_role": "typed",
        "case_purpose": (
            "Verify that the unambiguous synthetic cash-balance context selects "
            "the prebound cash_balance_snapshot_v1 typed option."
        ),
    },
    "syn_successor_v2_no_registry_type": {
        "smoke_role": "unclassified",
        "case_purpose": (
            "Verify that the synthetic broker-fee context, unsupported by every "
            "available registry type card, selects unclassified with "
            "no_registry_type."
        ),
    },
}
V6_TRANSPARENT_SMOKE_DIAGNOSES = {
    "MODEL_SEMANTIC_ERROR",
    "SOURCE_CONTEXT_INSUFFICIENT",
    "TYPE_CARD_AMBIGUOUS",
    "TYPED_OPTIONS_AMBIGUOUS",
    "UNCLASSIFIED_RULE_UNCLEAR",
    "EXPECTED_ANSWER_QUESTIONABLE",
    "TECHNICAL_PIPELINE_ERROR",
}
FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV6TransparentSmokeReportFactory.create_case and "
    "render_report are the only repository-safe transparent smoke projection "
    "entrypoints"
)
FORBIDDEN = (
    "The transparent projector must not alter semantic authorities, expose "
    "provider response identifiers, raw provider envelopes, credentials, "
    "filesystem paths or hidden reasoning, or project actual-corpus values"
)

_SEMANTIC_FIELDS = ("disposition", "typed_option_id", "reason_code")
_PACKET_FIELDS = (
    "task",
    "source_context",
    "available_type_cards",
    "typed_options",
)
_CONTEXT_V2_1_REPORT_CASE_AUTHORITY = object()


class Gate2FinancialSemanticV6TransparentSmokeReportError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class Gate2FinancialSemanticV6ContextV21ReportCaseEvidence:
    __slots__ = ("__serialized_projection",)

    def __init__(
        self,
        *,
        serialized_projection: str,
        authority: object,
    ) -> None:
        if authority is not _CONTEXT_V2_1_REPORT_CASE_AUTHORITY:
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "provider_report_case_evidence_invalid"
            )
        object.__setattr__(
            self,
            "_Gate2FinancialSemanticV6ContextV21ReportCaseEvidence"
            "__serialized_projection",
            serialized_projection,
        )

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(
            "Gate2FinancialSemanticV6ContextV21ReportCaseEvidence "
            "is immutable"
        )

    def to_dict(self) -> dict[str, Any]:
        try:
            projection = json.loads(self.__serialized_projection)
        except (TypeError, ValueError) as exc:
            raise Gate2FinancialSemanticV6TransparentSmokeReportError(
                "financial_semantic_v6_context_v2_1_"
                "provider_report_case_evidence_invalid"
            ) from exc
        if not _context_v2_1_case_projection_is_valid(projection):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "provider_report_case_evidence_invalid"
            )
        return copy.deepcopy(projection)


def _issue_context_v2_1_provider_case_evidence(
    *,
    validated_projection: dict[str, Any],
) -> Gate2FinancialSemanticV6ContextV21ReportCaseEvidence:
    if not _context_v2_1_case_projection_is_valid(validated_projection):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "provider_report_case_evidence_invalid"
        )
    return Gate2FinancialSemanticV6ContextV21ReportCaseEvidence(
        serialized_projection=json.dumps(
            validated_projection,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ),
        authority=_CONTEXT_V2_1_REPORT_CASE_AUTHORITY,
    )


class Gate2FinancialSemanticV6TransparentSmokeReportFactory:
    def create_context_v2_1_provider_case(
        self,
        *,
        case_id: str,
        provider_profile: Any,
        sealed_request: Any,
        prepared_request: Any,
        canonical_schema: dict[str, Any],
        local_projection_model_id: str,
        adapter_extracted_output: Any,
        normalized_answer: dict[str, Any],
        expected_answer: dict[str, Any],
        materialized_artifact_hash: str,
        serialized_private_evidence_hash: str,
        restored_private_evidence_hash: str,
        replay_materialized_artifact_hash: str,
        persisted_snapshot_hash: str,
        replay_snapshot_integrity_hash: str,
        restore_exact: bool,
        replay_exact: bool,
    ) -> dict[str, Any]:
        taxonomy_state = CONTEXT_V2_1_PROVIDER_PROOF_CASES.get(case_id)
        profile_id = getattr(provider_profile, "profile_id", None)
        profile_authority = (
            CONTEXT_V2_1_PROVIDER_PROOF_PROFILE_AUTHORITY.get(
                profile_id
            )
        )
        expected_truth = (
            CONTEXT_V2_1_PROVIDER_PROOF_EXPECTED_ANSWERS.get(case_id)
        )
        model_visible_request = getattr(
            sealed_request,
            "model_visible_request",
            None,
        )
        final_request = getattr(prepared_request, "form_data", None)
        provider_schema = getattr(
            prepared_request,
            "provider_visible_schema",
            None,
        )
        prepared_schema_binding_valid = bool(
            getattr(
                prepared_request,
                "schema_binding_is_valid",
                lambda: False,
            )()
        )
        prepared_canonical_binding_valid = bool(
            isinstance(canonical_schema, dict)
            and getattr(
                prepared_request,
                "context_v2_1_contract_is_bound",
                lambda **_kwargs: False,
            )(
                canonical_schema=canonical_schema,
                provider_profile=provider_profile,
                model_visible_request=model_visible_request,
                local_projection_model_id=(
                    local_projection_model_id
                ),
            )
        )
        messages = (
            model_visible_request.get("messages")
            if isinstance(model_visible_request, dict)
            else None
        )
        if (
            taxonomy_state is None
            or profile_id not in CONTEXT_V2_1_PROVIDER_PROOF_PROFILES
            or not isinstance(profile_authority, dict)
            or getattr(provider_profile, "provider_id", None)
            != profile_authority["provider_id"]
            or getattr(provider_profile, "adapter_id", None)
            != profile_authority["adapter_id"]
            or getattr(provider_profile, "adapter_version", None)
            != profile_authority["adapter_version"]
            or local_projection_model_id
            != profile_authority["local_projection_model_id"]
            or not isinstance(final_request, dict)
            or not isinstance(provider_schema, dict)
            or not prepared_schema_binding_valid
            or not prepared_canonical_binding_valid
            or getattr(
                prepared_request,
                "provider_adapter_id",
                None,
            )
            != getattr(provider_profile, "adapter_id", None)
            or final_request.get("model")
            != local_projection_model_id
            or not isinstance(messages, list)
            or len(messages) != 2
            or not all(isinstance(item, dict) for item in messages)
            or messages[0].get("role") != "system"
            or messages[1].get("role") != "user"
            or not isinstance(messages[0].get("content"), str)
            or not isinstance(messages[1].get("content"), str)
            or _sha256_text_value(messages[0]["content"])
            != CONTEXT_V2_1_PROVIDER_PROOF_SYSTEM_MESSAGE_SHA256
            or _sha256_text_value(messages[1]["content"])
            != CONTEXT_V2_1_PROVIDER_PROOF_USER_CONTENT_SHA256[
                case_id
            ]
            or _sha256_model_visible_request(model_visible_request)
            != CONTEXT_V2_1_PROVIDER_PROOF_MODEL_VISIBLE_REQUEST_SHA256[
                case_id
            ]
            or not _context_v2_1_answer_is_valid(normalized_answer)
            or normalized_answer != expected_truth
            or expected_answer != expected_truth
            or not _context_v2_1_extracted_output_is_exact(
                case_id=case_id,
                value=adapter_extracted_output,
            )
            or not _sha256_text(materialized_artifact_hash)
            or not _sha256_text(serialized_private_evidence_hash)
            or not _sha256_text(restored_private_evidence_hash)
            or not _sha256_text(replay_materialized_artifact_hash)
            or replay_materialized_artifact_hash
            != materialized_artifact_hash
            or not _sha256_text(persisted_snapshot_hash)
            or not _sha256_text(replay_snapshot_integrity_hash)
            or not isinstance(
                getattr(
                    prepared_request,
                    "projection_policy_version",
                    None,
                ),
                str,
            )
            or restore_exact is not True
            or replay_exact is not True
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "provider_report_authority_invalid"
            )
        comparison = _mechanical_comparison(
            expected=expected_answer,
            actual=normalized_answer,
        )
        draft = {
            "schema_version": (
                CONTEXT_V2_1_PROVIDER_PROOF_CASE_SCHEMA_VERSION
            ),
            "case_id": case_id,
            "taxonomy_state": taxonomy_state,
            "provider": {
                "provider_id": getattr(provider_profile, "provider_id", None),
                "provider_profile_id": profile_id,
                "adapter_id": getattr(provider_profile, "adapter_id", None),
                "adapter_version": getattr(
                    provider_profile,
                    "adapter_version",
                    None,
                ),
                "schema_projection_policy_version": getattr(
                    prepared_request,
                    "projection_policy_version",
                    None,
                ),
                "adapted_schema_hash": getattr(
                    prepared_request,
                    "adapted_schema_hash",
                    None,
                ),
                "canonical_schema_hash": getattr(
                    prepared_request,
                    "canonical_schema_hash",
                    None,
                ),
            },
            "exact_final_model_visible_request": copy.deepcopy(
                final_request
            ),
            "exact_system_message": messages[0]["content"],
            "exact_user_content": messages[1]["content"],
            "exact_provider_visible_response_schema": copy.deepcopy(
                provider_schema
            ),
            "exact_adapter_extracted_output": copy.deepcopy(
                adapter_extracted_output
            ),
            "normalized_canonical_answer": copy.deepcopy(
                normalized_answer
            ),
            "expected_answer": copy.deepcopy(expected_answer),
            "field_level_diff": comparison,
            "pipeline": {
                "materialized_artifact_hash": materialized_artifact_hash,
                "serialized_private_evidence_hash": (
                    serialized_private_evidence_hash
                ),
                "restored_private_evidence_hash": (
                    restored_private_evidence_hash
                ),
                "replay_materialized_artifact_hash": (
                    replay_materialized_artifact_hash
                ),
                "persisted_snapshot_hash": persisted_snapshot_hash,
                "replay_snapshot_integrity_hash": (
                    replay_snapshot_integrity_hash
                ),
                "restore_exact": restore_exact,
                "replay_exact": replay_exact,
            },
            "actual_metrics": {
                "input_tokens": None,
                "output_tokens": None,
                "cost_usd": None,
                "latency_ms": None,
                "status": "NOT_APPLICABLE_NO_PROVIDER_CALL",
            },
            "execution_accounting": {
                "provider_calls_total": 0,
                "semantic_repair_total": 0,
                "fallback_total": 0,
                "retry_total": 0,
            },
        }
        projection = {
            **draft,
            "integrity_hash": _sha256_json(draft),
        }
        return copy.deepcopy(projection)

    def create_context_v2_1_provider_report(
        self,
        *,
        case_evidence: list[Any],
    ) -> dict[str, Any]:
        if not isinstance(case_evidence, list):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "provider_report_cases_invalid"
            )
        if any(
            type(item)
            is not Gate2FinancialSemanticV6ContextV21ReportCaseEvidence
            for item in case_evidence
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "provider_report_cases_invalid"
            )
        try:
            validated = [item.to_dict() for item in case_evidence]
        except Gate2FinancialSemanticV6TransparentSmokeReportError:
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "provider_report_cases_invalid"
            )
        ordered = sorted(
            (copy.deepcopy(item) for item in validated),
            key=lambda item: (
                item["provider"]["provider_profile_id"],
                item["case_id"],
            ),
        )
        expected_pairs = {
            (profile_id, case_id)
            for profile_id in CONTEXT_V2_1_PROVIDER_PROOF_PROFILES
            for case_id in CONTEXT_V2_1_PROVIDER_PROOF_CASES
        }
        observed_pairs = {
            (
                item.get("provider", {}).get("provider_profile_id"),
                item.get("case_id"),
            )
            for item in ordered
        }
        if (
            observed_pairs != expected_pairs
            or len(ordered) != len(expected_pairs)
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "provider_report_cases_invalid"
            )
        return {
            "schema_version": (
                CONTEXT_V2_1_PROVIDER_PROOF_REPORT_SCHEMA_VERSION
            ),
            "status": "passed",
            "active": False,
            "provider_profiles_total": 3,
            "semantic_fixtures_total": 4,
            "provider_case_paths_total": 12,
            "cases": ordered,
            "execution_accounting": {
                "provider_calls_total": 0,
                "semantic_repair_total": 0,
                "fallback_total": 0,
                "retry_total": 0,
            },
        }

    def create_case(
        self,
        *,
        case: Any,
        packet: Any,
        choice_contract: Any,
        exact_model_answer: Any,
        normalized_answer: dict[str, Any] | None,
        technical_pipeline_passed: bool,
        failure_code: str | None = None,
    ) -> dict[str, Any]:
        case_id = str(getattr(case, "case_id", ""))
        definition = V6_TRANSPARENT_SMOKE_CASES.get(case_id)
        payload = getattr(packet, "payload", None)
        expected_answer = getattr(case, "expected_model_choice", None)
        if (
            definition is None
            or not isinstance(payload, dict)
            or tuple(payload) != _PACKET_FIELDS
            or not isinstance(expected_answer, dict)
            or getattr(case, "route", None) != "semantic_model"
        ):
            _fail("financial_semantic_v6_transparent_smoke_authority_invalid")

        unclassified_reason_codes = tuple(
            getattr(choice_contract, "unclassified_reason_codes", ())
        )
        available_dispositions = tuple(
            getattr(choice_contract, "available_provider_dispositions", ())
        )
        if (
            "unclassified_financial_input" not in available_dispositions
            or not unclassified_reason_codes
        ):
            _fail(
                "financial_semantic_v6_transparent_smoke_unclassified_invalid"
            )

        normalized = (
            copy.deepcopy(normalized_answer)
            if isinstance(normalized_answer, dict)
            else None
        )
        comparison = _mechanical_comparison(
            expected=expected_answer,
            actual=normalized,
        )
        diagnosis = _diagnosis(
            technical_pipeline_passed=technical_pipeline_passed,
            comparison=comparison,
            failure_code=failure_code,
        )
        exact_answer = _semantic_json_object(exact_model_answer)
        if technical_pipeline_passed and exact_answer is None:
            _fail(
                "financial_semantic_v6_transparent_smoke_exact_answer_missing"
            )

        return {
            "schema_version": V6_TRANSPARENT_SMOKE_CASE_SCHEMA_VERSION,
            "case_id": case_id,
            "smoke_role": definition["smoke_role"],
            "case_purpose": definition["case_purpose"],
            "what_the_model_saw": {
                "task_instruction": copy.deepcopy(payload["task"]),
                "source_context": copy.deepcopy(payload["source_context"]),
                "available_financial_type_cards": copy.deepcopy(
                    payload["available_type_cards"]
                ),
                "typed_options": copy.deepcopy(payload["typed_options"]),
                "unclassified_selection": {
                    "disposition": "unclassified_financial_input",
                    "reason_codes": list(unclassified_reason_codes),
                },
            },
            "expected_answer": copy.deepcopy(expected_answer),
            "exact_model_answer": exact_answer,
            "normalized_answer": normalized,
            "mechanical_comparison": comparison,
            "technical_pipeline": {
                "status": (
                    "PASSED" if technical_pipeline_passed else "FAILED"
                ),
                "failure_code": (
                    None if technical_pipeline_passed else failure_code
                ),
            },
            "diagnosis": diagnosis,
        }

    def render_report(
        self,
        *,
        exact_model_id: str,
        safe_receipt_filename: str,
        terminal_receipt: dict[str, Any],
        case_evidence: list[dict[str, Any]],
        interrupted_receipt_filename: str | None = None,
    ) -> str:
        ordered = _ordered_case_evidence(case_evidence)
        accounting = terminal_receipt.get("attempt_accounting") or {}
        provider_submissions = accounting.get("provider_submissions_total")
        provider_responses = accounting.get("provider_responses_total")
        technical_pipeline_passed = (
            provider_submissions == 2
            and provider_responses == 2
            and all(
                item["technical_pipeline"]["status"] == "PASSED"
                for item in ordered
            )
        )
        semantic_passed = all(
            item["mechanical_comparison"]["all_fields_match"] is True
            for item in ordered
        )
        acceptance = terminal_receipt.get("acceptance") or {}
        lines = [
            "# Broker Reports — Gate 2 V6 Strong Model Semantic Smoke",
            "",
            f"- Exact model: `{exact_model_id}`",
            "- Scope: the two frozen synthetic smoke cases only.",
            "- Semantic Pack, Prompt, Semantic Packet, Candidate Compiler, "
            "Typed Options, Choice schema, expected answers, validator, "
            "materializer and smoke cases: unchanged.",
            f"- Safe receipt: [{safe_receipt_filename}]"
            f"(./{safe_receipt_filename})",
            "- Qualification benchmark: not run.",
            "",
        ]
        if interrupted_receipt_filename is not None:
            lines.extend(
                [
                    "## Execution continuity",
                    "",
                    "The first execute process checkpointed one successful "
                    "typed provider response, then stopped locally because the "
                    "new report projector rejected the adapter-extracted JSON "
                    "string before rendering it as an object. The provider "
                    "answer, normalized Choice, materialization and replay had "
                    "already passed and were preserved.",
                    "",
                    f"- Interrupted one-case checkpoint: "
                    f"[{interrupted_receipt_filename}]"
                    f"(./{interrupted_receipt_filename})",
                    "- The continuation validated that checkpoint and current "
                    "frozen-authority parity, skipped the completed typed case, "
                    "and submitted only the missing unclassified case.",
                    "- This was one bounded continuation, not a retry of either "
                    "provider submission.",
                    "",
                ]
            )
        lines.extend(
            [
                "## Acceptance",
                "",
            f"- `PROVIDER_SUBMISSIONS`: "
            f"`{'TWO' if provider_submissions == 2 else 'FAILED'}`",
            f"- `TECHNICAL_PIPELINE`: "
            f"`{'PASSED' if technical_pipeline_passed else 'FAILED'}`",
            f"- `TYPED_SMOKE`: "
            f"`{_report_smoke_status(acceptance.get('typed_smoke'))}`",
            f"- `UNCLASSIFIED_SMOKE`: "
            f"`{_report_smoke_status(acceptance.get('unclassified_smoke'))}`",
            "- `MODEL_INPUT_VISIBLE`: `YES`",
            "- `EXACT_MODEL_OUTPUT_VISIBLE`: "
            f"`{'YES' if all(item['exact_model_answer'] is not None for item in ordered) else 'NO'}`",
            "- `EXPECTED_VS_ACTUAL_DIFF`: `EXPLICIT`",
            f"- `FALLBACK_REPAIR_HIDDEN_RETRY`: "
            f"`{_zero_attempt_status(accounting)}`",
            "- `DOCUMENTATION`: `UPDATED_IN_SAME_PR`",
            "",
            ]
        )
        for item in ordered:
            lines.extend(_render_case(item))

        lines.extend(
            [
                "## Continuation",
                "",
                (
                    "Both semantic smoke cases passed. The exact model is "
                    "eligible for a separately authorized full V6 qualification "
                    "benchmark; that benchmark was not run here."
                    if semantic_passed and technical_pipeline_passed
                    else (
                        "At least one smoke case did not pass. The full V6 "
                        "qualification benchmark was not run. The next action is "
                        "a joint audit of source context, type cards, typed "
                        "options and the exact model answer; no Prompt or "
                        "Semantic Pack change is authorized by this report."
                    )
                ),
                "",
                "## Evidence boundary",
                "",
                "The full context below is repository-safe because both cases "
                "are synthetic. No credentials, provider response identifiers, "
                "raw provider envelope, filesystem path or hidden reasoning "
                "trace is included. Future actual-corpus exact context and raw "
                "values remain outside Git and are linked only by safe hashes.",
                "",
                f"Report schema: `{V6_TRANSPARENT_SMOKE_REPORT_VERSION}`.",
                "",
            ]
        )
        return "\n".join(lines)


def _context_v2_1_case_projection_is_valid(
    projection: Any,
) -> bool:
    if not isinstance(projection, dict):
        return False
    material = copy.deepcopy(projection)
    integrity_hash = material.pop("integrity_hash", None)
    if (
        not _sha256_text(integrity_hash)
        or _sha256_json(material) != integrity_hash
    ):
        return False
    case_id = projection.get("case_id")
    provider = projection.get("provider")
    profile_id = (
        provider.get("provider_profile_id")
        if isinstance(provider, dict)
        else None
    )
    expected_answer = (
        CONTEXT_V2_1_PROVIDER_PROOF_EXPECTED_ANSWERS.get(case_id)
    )
    profile_authority = (
        CONTEXT_V2_1_PROVIDER_PROOF_PROFILE_AUTHORITY.get(profile_id)
    )
    final_request = projection.get(
        "exact_final_model_visible_request"
    )
    provider_schema = projection.get(
        "exact_provider_visible_response_schema"
    )
    system_message = projection.get("exact_system_message")
    user_content = projection.get("exact_user_content")
    normalized_answer = projection.get(
        "normalized_canonical_answer"
    )
    pipeline = projection.get("pipeline")
    actual_metrics = projection.get("actual_metrics")
    execution_accounting = projection.get("execution_accounting")
    zero_accounting = {
        "provider_calls_total": 0,
        "semantic_repair_total": 0,
        "fallback_total": 0,
        "retry_total": 0,
    }
    if (
        set(projection)
        != {
            "schema_version",
            "case_id",
            "taxonomy_state",
            "provider",
            "exact_final_model_visible_request",
            "exact_system_message",
            "exact_user_content",
            "exact_provider_visible_response_schema",
            "exact_adapter_extracted_output",
            "normalized_canonical_answer",
            "expected_answer",
            "field_level_diff",
            "pipeline",
            "actual_metrics",
            "execution_accounting",
            "integrity_hash",
        }
        or projection.get("schema_version")
        != CONTEXT_V2_1_PROVIDER_PROOF_CASE_SCHEMA_VERSION
        or projection.get("taxonomy_state")
        != CONTEXT_V2_1_PROVIDER_PROOF_CASES.get(case_id)
        or not isinstance(profile_authority, dict)
        or not isinstance(provider, dict)
        or set(provider)
        != {
            "provider_id",
            "provider_profile_id",
            "adapter_id",
            "adapter_version",
            "schema_projection_policy_version",
            "adapted_schema_hash",
            "canonical_schema_hash",
        }
        or provider.get("provider_id")
        != profile_authority["provider_id"]
        or provider.get("adapter_id")
        != profile_authority["adapter_id"]
        or provider.get("adapter_version")
        != profile_authority["adapter_version"]
        or provider.get("schema_projection_policy_version")
        != "broker_reports_gate2_context_v2_1_local_schema_projection_v1"
        or not _sha256_text(provider.get("adapted_schema_hash"))
        or not _sha256_text(provider.get("canonical_schema_hash"))
        or not isinstance(final_request, dict)
        or not isinstance(provider_schema, dict)
        or provider["adapted_schema_hash"]
        != _sha256_json(provider_schema)
        or _sha256_text_value(system_message)
        != CONTEXT_V2_1_PROVIDER_PROOF_SYSTEM_MESSAGE_SHA256
        or _sha256_text_value(user_content)
        != CONTEXT_V2_1_PROVIDER_PROOF_USER_CONTENT_SHA256.get(
            case_id
        )
        or projection.get("expected_answer") != expected_answer
        or normalized_answer != expected_answer
        or not _context_v2_1_answer_is_valid(normalized_answer)
        or not _context_v2_1_extracted_output_is_exact(
            case_id=case_id,
            value=projection.get(
                "exact_adapter_extracted_output"
            ),
        )
        or projection.get("field_level_diff")
        != _mechanical_comparison(
            expected=expected_answer,
            actual=normalized_answer,
        )
        or projection["field_level_diff"]["all_fields_match"]
        is not True
        or not isinstance(pipeline, dict)
        or set(pipeline)
        != {
            "materialized_artifact_hash",
            "serialized_private_evidence_hash",
            "restored_private_evidence_hash",
            "replay_materialized_artifact_hash",
            "persisted_snapshot_hash",
            "replay_snapshot_integrity_hash",
            "restore_exact",
            "replay_exact",
        }
        or any(
            not _sha256_text(pipeline.get(field))
            for field in (
                "materialized_artifact_hash",
                "serialized_private_evidence_hash",
                "restored_private_evidence_hash",
                "replay_materialized_artifact_hash",
                "persisted_snapshot_hash",
                "replay_snapshot_integrity_hash",
            )
        )
        or pipeline["replay_materialized_artifact_hash"]
        != pipeline["materialized_artifact_hash"]
        or pipeline.get("restore_exact") is not True
        or pipeline.get("replay_exact") is not True
        or not isinstance(actual_metrics, dict)
        or set(actual_metrics)
        != {
            "input_tokens",
            "output_tokens",
            "cost_usd",
            "latency_ms",
            "status",
        }
        or actual_metrics
        != {
            "input_tokens": None,
            "output_tokens": None,
            "cost_usd": None,
            "latency_ms": None,
            "status": "NOT_APPLICABLE_NO_PROVIDER_CALL",
        }
        or not isinstance(execution_accounting, dict)
        or set(execution_accounting) != set(zero_accounting)
        or execution_accounting != zero_accounting
    ):
        return False
    return _context_v2_1_final_request_is_consistent(
        profile_id=profile_id,
        profile_authority=profile_authority,
        final_request=final_request,
        provider_schema=provider_schema,
        system_message=system_message,
        user_content=user_content,
    )


def _context_v2_1_final_request_is_consistent(
    *,
    profile_id: str,
    profile_authority: dict[str, Any],
    final_request: dict[str, Any],
    provider_schema: dict[str, Any],
    system_message: str,
    user_content: str,
) -> bool:
    if (
        final_request.get("model")
        != profile_authority["local_projection_model_id"]
    ):
        return False
    if profile_id == "anthropic_claude":
        output_config = final_request.get("output_config")
        output_format = (
            output_config.get("format")
            if isinstance(output_config, dict)
            else None
        )
        return (
            set(final_request)
            == {
                "model",
                "max_tokens",
                "messages",
                "output_config",
                "system",
            }
            and final_request.get("max_tokens") == 32768
            and final_request.get("system") == system_message
            and final_request.get("messages")
            == [{"role": "user", "content": user_content}]
            and isinstance(output_config, dict)
            and set(output_config) == {"format"}
            and isinstance(output_format, dict)
            and set(output_format) == {"type", "schema"}
            and output_format.get("type") == "json_schema"
            and output_format.get("schema") == provider_schema
        )
    response_format = final_request.get("response_format")
    json_schema = (
        response_format.get("json_schema")
        if isinstance(response_format, dict)
        else None
    )
    metadata = final_request.get("metadata")
    expected_json_schema_fields = {"strict", "schema"}
    if profile_id == "openai_gpt":
        expected_json_schema_fields.add("name")
    return (
        set(final_request)
        == {"messages", "response_format", "model", "metadata"}
        and final_request.get("messages")
        == [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_content},
        ]
        and isinstance(response_format, dict)
        and set(response_format) == {"type", "json_schema"}
        and response_format.get("type") == "json_schema"
        and isinstance(json_schema, dict)
        and set(json_schema) == expected_json_schema_fields
        and json_schema.get("strict") is True
        and json_schema.get("schema") == provider_schema
        and (
            profile_id != "openai_gpt"
            or json_schema.get("name") == "broker_reports_gate2_choice"
        )
        and metadata
        == {
            "broker_reports_gate2": {
                "provider_profile_id": profile_id,
                "provider_adapter_id": profile_authority["adapter_id"],
                "provider_adapter_version": (
                    profile_authority["adapter_version"]
                ),
                "structured_output_mode": (
                    profile_authority["structured_output_mode"]
                ),
            }
        }
    )


def _mechanical_comparison(
    *,
    expected: dict[str, Any],
    actual: dict[str, Any] | None,
) -> dict[str, Any]:
    actual_mapping = actual or {}
    field_rows = []
    for field in _SEMANTIC_FIELDS:
        expected_present = field in expected
        actual_present = field in actual_mapping
        if not expected_present and not actual_present:
            continue
        field_rows.append(
            {
                "field": field,
                "expected_present": expected_present,
                "expected_value": (
                    copy.deepcopy(expected.get(field))
                    if expected_present
                    else None
                ),
                "actual_present": actual_present,
                "actual_value": (
                    copy.deepcopy(actual_mapping.get(field))
                    if actual_present
                    else None
                ),
                "exact_match": (
                    expected_present
                    and actual_present
                    and expected[field] == actual_mapping[field]
                ),
            }
        )
    all_fields_match = (
        actual is not None
        and expected == actual
        and all(row["exact_match"] for row in field_rows)
    )
    return {
        "all_fields_match": all_fields_match,
        "fields": field_rows,
    }


def _sha256_text(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _sha256_text_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_model_visible_request(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(encoded).hexdigest()


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _context_v2_1_answer_is_valid(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    disposition = value.get("disposition")
    if disposition == "typed_input":
        return (
            set(value) == {"disposition", "typed_option_id"}
            and isinstance(value.get("typed_option_id"), str)
            and value["typed_option_id"].startswith(
                "financial-typed-option:"
            )
        )
    return (
        disposition == "unclassified_financial_input"
        and set(value) == {"disposition", "reason_code"}
        and value.get("reason_code")
        in {
            "no_registry_type",
            "ambiguous_registry_type",
            "single_registry_type_no_safe_record",
        }
    )


def _context_v2_1_extracted_output_is_exact(
    *,
    case_id: str,
    value: Any,
) -> bool:
    expected = CONTEXT_V2_1_PROVIDER_PROOF_EXTRACTED_OUTPUTS.get(
        case_id
    )
    if not isinstance(expected, dict):
        return False
    if isinstance(value, dict):
        return value == expected
    if not isinstance(value, str):
        return False
    return value == json.dumps(
        expected,
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def _semantic_json_object(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return None
        if isinstance(decoded, dict):
            return decoded
    return None


def _diagnosis(
    *,
    technical_pipeline_passed: bool,
    comparison: dict[str, Any],
    failure_code: str | None,
) -> dict[str, Any]:
    if not technical_pipeline_passed:
        return {
            "code": "TECHNICAL_PIPELINE_ERROR",
            "basis": (
                "The exact two-case path did not complete the parser, "
                "validator/materializer and exact offline replay chain."
            ),
            "failure_code": failure_code,
        }
    if comparison["all_fields_match"]:
        return {
            "code": "NONE",
            "basis": (
                "The normalized semantic answer exactly matches the frozen "
                "expected answer."
            ),
            "failure_code": None,
        }
    return {
        "code": "MODEL_SEMANTIC_ERROR",
        "basis": (
            "The frozen source context, type cards, typed options, Choice "
            "schema and expected answer reached the model unchanged; parsing, "
            "validation/materialization and exact offline replay passed, but "
            "the normalized semantic choice differs from expected."
        ),
        "failure_code": None,
    }


def _ordered_case_evidence(
    case_evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(case_evidence, list):
        _fail("financial_semantic_v6_transparent_smoke_cases_invalid")
    by_id = {
        str(item.get("case_id")): copy.deepcopy(item)
        for item in case_evidence
        if isinstance(item, dict)
    }
    if set(by_id) != set(V6_TRANSPARENT_SMOKE_CASES):
        _fail("financial_semantic_v6_transparent_smoke_cases_invalid")
    ordered = [by_id[case_id] for case_id in V6_TRANSPARENT_SMOKE_CASES]
    for item in ordered:
        if (
            item.get("schema_version")
            != V6_TRANSPARENT_SMOKE_CASE_SCHEMA_VERSION
        ):
            _fail("financial_semantic_v6_transparent_smoke_case_invalid")
    return ordered


def _render_case(item: dict[str, Any]) -> list[str]:
    comparison_rows = [
        "| Field | Expected | Normalized actual | Match |",
        "|---|---|---|---|",
    ]
    for row in item["mechanical_comparison"]["fields"]:
        comparison_rows.append(
            "| "
            + " | ".join(
                (
                    f"`{row['field']}`",
                    _comparison_value(
                        present=row["expected_present"],
                        value=row["expected_value"],
                    ),
                    _comparison_value(
                        present=row["actual_present"],
                        value=row["actual_value"],
                    ),
                    "`YES`" if row["exact_match"] else "`NO`",
                )
            )
            + " |"
        )
    diagnosis = item["diagnosis"]
    return [
        f"## Case: `{item['case_id']}`",
        "",
        "### 1. CASE PURPOSE",
        "",
        item["case_purpose"],
        "",
        "### 2. WHAT THE MODEL SAW",
        "",
        "#### Task instruction",
        "",
        _json_block(item["what_the_model_saw"]["task_instruction"]),
        "",
        "#### Source context",
        "",
        _json_block(item["what_the_model_saw"]["source_context"]),
        "",
        "#### Available financial type cards",
        "",
        _json_block(
            item["what_the_model_saw"]["available_financial_type_cards"]
        ),
        "",
        "#### All typed options",
        "",
        _json_block(item["what_the_model_saw"]["typed_options"]),
        "",
        "#### Unclassified selection",
        "",
        _json_block(item["what_the_model_saw"]["unclassified_selection"]),
        "",
        "### 3. EXPECTED ANSWER",
        "",
        _json_block(item["expected_answer"]),
        "",
        "### 4. EXACT MODEL ANSWER",
        "",
        _json_block(item["exact_model_answer"]),
        "",
        "### 5. NORMALIZED ANSWER",
        "",
        _json_block(item["normalized_answer"]),
        "",
        "### 6. MECHANICAL COMPARISON",
        "",
        *comparison_rows,
        "",
        f"Overall exact match: "
        f"`{'YES' if item['mechanical_comparison']['all_fields_match'] else 'NO'}`.",
        "",
        "### 7. DIAGNOSIS",
        "",
        f"`{diagnosis['code']}` — {diagnosis['basis']}",
        "",
        f"Technical pipeline: `{item['technical_pipeline']['status']}`.",
        "",
    ]


def _comparison_value(*, present: bool, value: Any) -> str:
    if not present:
        return "_absent_"
    return f"`{json.dumps(value, ensure_ascii=False, sort_keys=True)}`"


def _json_block(value: Any) -> str:
    return (
        "```json\n"
        + json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n```"
    )


def _report_smoke_status(value: Any) -> str:
    if value == "PASSED":
        return "PASSED"
    if value == "FAILED":
        return "FAILED_WITH_EXACT_EVIDENCE"
    return "FAILED_WITH_EXACT_EVIDENCE"


def _zero_attempt_status(accounting: dict[str, Any]) -> str:
    if all(
        accounting.get(field) == 0
        for field in (
            "fallback_total",
            "repair_total",
            "hidden_retry_total",
        )
    ):
        return "ZERO"
    return "FAILED"


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV6TransparentSmokeReportError(code)
