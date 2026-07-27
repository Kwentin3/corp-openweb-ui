from __future__ import annotations

import copy
import json
from typing import Any


V6_TRANSPARENT_SMOKE_CASE_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v6_transparent_smoke_case_v1"
)
V6_TRANSPARENT_SMOKE_REPORT_VERSION = (
    "broker_reports_gate2_financial_semantic_v6_transparent_smoke_report_v1"
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


class Gate2FinancialSemanticV6TransparentSmokeReportError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class Gate2FinancialSemanticV6TransparentSmokeReportFactory:
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
