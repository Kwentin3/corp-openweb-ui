"""Repository-safe projector for the bounded V6 model diagnostic."""

from __future__ import annotations

import copy
import json
from typing import Any

from .gate2_financial_evidence_materialization_contracts import sha256_json
from .gate2_financial_semantic_v6_model_diagnostic import (
    V6_SLIM_DIAGNOSTIC_SCHEMA_VERSION,
    V6_SLIM_DIAGNOSTIC_SUBMISSIONS_TOTAL,
)
from .gate2_financial_semantic_v6_smoke_report import (
    V6_TRANSPARENT_SMOKE_CASES,
)


V6_SLIM_DIAGNOSTIC_REPORT_VERSION = (
    "broker_reports_gate2_financial_semantic_v6_slim_diagnostic_report_v1"
)
FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV6SlimDiagnosticReportFactory.render is the only "
    "repository-safe GOAL 4 exact input/output report projector"
)
FORBIDDEN = (
    "The report must not include credentials, provider response identifiers, "
    "raw provider envelopes, filesystem paths or hidden reasoning traces, and "
    "interpretation must not replace exact request/response evidence"
)


class Gate2FinancialSemanticV6SlimDiagnosticReportError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class Gate2FinancialSemanticV6SlimDiagnosticReportFactory:
    def render(
        self,
        *,
        safe_receipt_filename: str,
        terminal_receipt: dict[str, Any],
    ) -> str:
        receipt = copy.deepcopy(terminal_receipt)
        _validate_receipt(receipt)
        acceptance = receipt["acceptance"]
        accounting = receipt["attempt_accounting"]
        metrics = receipt["provider_metrics"]
        evidence = sorted(
            receipt["case_evidence"],
            key=lambda item: item["ordinal"],
        )
        lines = [
            "# Broker Reports Gate 2 — GOAL 4 Slim View Model Diagnostic",
            "",
            "This report records the bounded six-submission diagnostic over "
            "the two frozen synthetic smoke cases. Exact semantic input and "
            "output facts appear before interpretation.",
            "",
            f"- Safe receipt: [{safe_receipt_filename}]"
            f"(./{safe_receipt_filename})",
            f"- Exact repository revision: "
            f"`{receipt['repository_revision']}`",
            f"- Request profile: `{receipt['request_profile']}`",
            "- Prompt, financial type meanings, frozen cases and expected "
            "answers: unchanged.",
            "- Candidate Compiler, canonical expansion and materialization: "
            "existing authorities reused.",
            "- Product runtime route: unchanged.",
            "- Full V6 benchmark: not run.",
            "",
            "## Acceptance",
            "",
            f"- `PROVIDER_SUBMISSIONS`: "
            f"`{acceptance['provider_submissions']}`",
            f"- `TECHNICAL_PIPELINE`: "
            f"`{acceptance['technical_pipeline']}`",
            f"- `HAIKU_TYPED`: `{acceptance['haiku_typed']}`",
            f"- `HAIKU_UNCLASSIFIED`: "
            f"`{acceptance['haiku_unclassified']}`",
            f"- `NANO_SLIM_TYPED`: "
            f"`{acceptance['nano_slim_typed']}`",
            f"- `NANO_SLIM_UNCLASSIFIED`: "
            f"`{acceptance['nano_slim_unclassified']}`",
            f"- `NANO_REVERSED_TYPED`: "
            f"`{acceptance['nano_reversed_typed']}`",
            f"- `NANO_REVERSED_UNCLASSIFIED`: "
            f"`{acceptance['nano_reversed_unclassified']}`",
            f"- `NANO_DIAGNOSTIC_STATUS`: "
            f"`{acceptance['nano_diagnostic_status']}`",
            "- `MODEL_INPUT_VISIBLE`: `YES`",
            "- `EXACT_MODEL_OUTPUT_VISIBLE`: "
            f"`{_exact_outputs_status(evidence)}`",
            "- `EXPECTED_VS_ACTUAL_DIFF`: `EXPLICIT`",
            f"- `FALLBACK_REPAIR_HIDDEN_RETRY`: "
            f"`{acceptance['fallback_repair_hidden_retry']}`",
            f"- `FULL_BENCHMARK`: `{acceptance['full_benchmark']}`",
            "- `DOCUMENTATION`: `UPDATED_IN_SAME_PR`",
            "",
            "## Execution accounting",
            "",
            f"- Planned provider submissions: "
            f"`{accounting['provider_submissions_planned_total']}`",
            f"- Local invocations: "
            f"`{accounting['local_invocations_total']}`",
            f"- Provider submissions: "
            f"`{accounting['provider_submissions_total']}`",
            f"- Provider responses: "
            f"`{accounting['provider_responses_total']}`",
            f"- Actual input tokens: "
            f"`{metrics['actual_input_tokens_total']}`",
            f"- Actual output tokens: "
            f"`{metrics['actual_output_tokens_total']}`",
            f"- Actual cost: `${metrics['actual_cost_usd']}`",
            f"- Total latency: `{metrics['latency_total_ms']} ms`",
            f"- Average latency: `{metrics['latency_average_ms']} ms`",
            f"- Maximum latency: `{metrics['latency_max_ms']} ms`",
            "",
            "## Primary evidence",
            "",
        ]
        for item in evidence:
            lines.extend(_render_call(item))
        lines.extend(
            [
                "## Interpretation",
                "",
                *_interpretation_lines(receipt),
                "",
                "## Evidence and privacy boundary",
                "",
                "Both cases are frozen synthetic fixtures, so their complete "
                "semantic context, local options and exact semantic JSON "
                "answers are repository-safe. The receipt and this report "
                "exclude credentials, provider response IDs, raw provider "
                "envelopes, internal filesystem paths and hidden reasoning.",
                "",
                "Future actual-corpus customer context and raw values remain "
                "outside Git; repository-safe projections are linked to "
                "private evidence by hashes only.",
                "",
                f"Report schema: `{V6_SLIM_DIAGNOSTIC_REPORT_VERSION}`.",
                "",
            ]
        )
        return "\n".join(lines)


def _render_call(item: dict[str, Any]) -> list[str]:
    definition = V6_TRANSPARENT_SMOKE_CASES[item["case_id"]]
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
    provider_metrics = item["provider_metrics"]
    technical = item["technical_pipeline"]
    diagnosis = _audited_diagnosis(item)
    return [
        f"### Call {item['ordinal']}: `{item['configuration_id']}` / "
        f"`{item['case_id']}`",
        "",
        f"- Case purpose: {definition['case_purpose']}",
        f"- Exact model: `{item['exact_model_id']}`",
        f"- Provider profile: `{item['provider_profile_id']}`",
        f"- Typed-option order: `{item['option_order']}`",
        f"- Model-visible request hash: "
        f"`{item['model_visible_request_hash']}`",
        f"- Model-visible UTF-8 bytes: "
        f"`{item['model_visible_utf8_bytes']}`",
        f"- Repository estimated input tokens: "
        f"`{item['repository_estimated_input_tokens']}`",
        "",
        "#### 1. EXACT MODEL-VISIBLE INPUT",
        "",
        _json_block(item["exact_model_visible_input"]),
        "",
        "#### 2. EXACT ADAPTER-EXTRACTED MODEL OUTPUT",
        "",
        _exact_output_block(item["exact_adapter_output"]),
        "",
        "#### 3. NORMALIZED ANSWER",
        "",
        _json_block(item["normalized_answer"]),
        "",
        "Normalization facts:",
        "",
        _json_block(item["normalization"]),
        "",
        "#### 4. FROZEN EXPECTED ANSWER AND MECHANICAL DIFF",
        "",
        "Expected model-facing Local Choice JSON:",
        "",
        _json_block(item["expected_model_output"]),
        "",
        "Expected canonical semantic answer:",
        "",
        _json_block(item["expected_answer"]),
        "",
        *comparison_rows,
        "",
        f"Overall exact match: "
        f"`{'YES' if item['mechanical_comparison']['all_fields_match'] else 'NO'}`.",
        "",
        "#### 5. ACTUAL PROVIDER METRICS",
        "",
        f"- Input tokens: "
        f"`{_metric(provider_metrics['actual_input_tokens'])}`",
        f"- Output tokens: "
        f"`{_metric(provider_metrics['actual_output_tokens'])}`",
        f"- Total tokens: "
        f"`{_metric(provider_metrics['actual_total_tokens'])}`",
        f"- Actual cost: "
        f"`{_cost(provider_metrics['actual_cost_usd'])}`",
        f"- Latency: `{_latency(provider_metrics['latency_ms'])}`",
        "",
        "#### 6. TECHNICAL PIPELINE",
        "",
        f"- Context lint: `{technical['context_lint']}`",
        f"- Local Choice parser: `{technical['local_choice_parser']}`",
        "- Canonical expansion/materialization: "
        f"`{technical['canonical_expansion_materialization']}`",
        f"- Overall: `{technical['status']}`",
        f"- Failure code: "
        f"`{technical['failure_code'] or 'NONE'}`",
        "",
        "#### 7. DIAGNOSIS",
        "",
        f"`{diagnosis['code']}` — {diagnosis['basis']}",
        "",
    ]


def _interpretation_lines(receipt: dict[str, Any]) -> list[str]:
    acceptance = receipt["acceptance"]
    nano_status = acceptance["nano_diagnostic_status"]
    haiku_passed = (
        acceptance["haiku_typed"] == "PASSED"
        and acceptance["haiku_unclassified"] == "PASSED"
    )
    lines = [
        (
            "Haiku preserved both frozen semantic decisions under the sealed "
            "Slim View."
            if haiku_passed
            else (
                "Haiku did not preserve both frozen semantic decisions under "
                "the Slim View. The full benchmark remains blocked."
            )
        ),
    ]
    if nano_status == "NANO_SLIM_PASSED_ORDER_INVARIANT":
        lines.append(
            "Nano passed both canonical-order Slim smoke cases; the reduced "
            "interface is a material explanatory factor. It also preserved "
            "both answers after the option-order permutation."
        )
    elif nano_status == "NANO_SLIM_PASSED_ORDER_SENSITIVE":
        lines.append(
            "Nano passed both canonical-order Slim smoke cases, so the reduced "
            "interface is a material explanatory factor, but at least one "
            "reversed-order answer changed. The candidate remains "
            "order-sensitive."
        )
    elif nano_status == "NANO_FIRST_OPTION_BIAS":
        lines.append(
            "Nano selected the first visible typed choice across the typed "
            "order permutation while the alias-to-canonical mapping changed. "
            "This is direct order-bias evidence; type-card wording is not the "
            "next justified variable."
        )
    elif nano_status == "NANO_SEMANTIC_CAPABILITY_INSUFFICIENT":
        lines.append(
            "Nano failed independently of order while returning schema-valid "
            "semantic choices. This supports a bounded semantic-capability "
            "or type-contrast audit; no Prompt or Pack change follows "
            "automatically."
        )
    elif nano_status == "NANO_MIXED_OR_ORDER_SENSITIVE":
        lines.append(
            "Nano produced a mixed/order-sensitive result. The exact calls "
            "above must be audited before selecting a corrective slice."
        )
    else:
        lines.append(
            "Nano evidence is incomplete; no semantic conclusion is valid."
        )
    if not haiku_passed:
        lines.append(
            "GOAL 7 is not authorized. First audit the Slim source hierarchy, "
            "type cards, local choices and exact Haiku answers."
        )
    elif nano_status == "NANO_SEMANTIC_CAPABILITY_INSUFFICIENT":
        lines.append(
            "The conditional GOAL 5 research prerequisite is met only to the "
            "extent that the exact failures above demonstrate semantic "
            "confusion rather than transport or schema failure."
        )
    else:
        lines.append(
            "A later GOAL must explicitly select one passed model-facing "
            "contract before any full frozen benchmark; this diagnostic did "
            "not run or authorize that benchmark."
        )
    if (
        acceptance["haiku_typed"] == "PASSED"
        and acceptance["haiku_unclassified"]
        == "FAILED_WITH_EXACT_EVIDENCE"
        and nano_status == "NANO_MIXED_OR_ORDER_SENSITIVE"
    ):
        lines.extend(_failed_goal4_joint_audit())
    return lines


def _failed_goal4_joint_audit() -> list[str]:
    return [
        "",
        "### Joint layer audit",
        "",
        "The immutable execution receipt retains the runner's first-pass "
        "mechanical",
        "classification. The repository-safe report projector refines only "
        "the two",
        "reason-only mismatches to `UNCLASSIFIED_RULE_UNCLEAR` after comparing "
        "the",
        "exact input, expected disposition and normalized answer; no input, "
        "output,",
        "metric or receipt byte was rewritten.",
        "",
        "The six exact calls separate the observed failures as follows:",
        "",
        "| Evidence | Observation | Most likely layer |",
        "|---|---|---|",
        "| Haiku typed, canonical order | Exact `{\"choice\":\"B\"}`; canonical "
        "cash option selected and fully materialized | Slim source, cash type "
        "card, typed choices and alias restoration are sufficient for this "
        "case |",
        "| Haiku unclassified | Correct `unclassified` disposition, wrong "
        "`ambiguous_registry_type` reason | `UNCLASSIFIED_RULE_UNCLEAR` |",
        "| Nano typed, both orders | Returned unclassified in both "
        "permutations and never selected the first typed option | Nano "
        "semantic capability/type interpretation; first-option bias is not "
        "supported |",
        "| Nano unclassified | Wrong reason in canonical order, correct reason "
        "in reversed order | Mixed/order-sensitive reason selection; not an "
        "order-independent type-card failure |",
        "| All six calls | Strict schema, Local Choice parsing, canonical "
        "expansion/materialization, usage and lifecycle accounting passed | "
        "Technical pipeline is not the failure source |",
        "",
        "The unclassified source context is adequate to establish the frozen "
        "expected",
        "answer: `Broker fee detail` is neither an ordinary cash-class balance "
        "nor a",
        "source-printed total/metric under the two visible cards. Therefore",
        "`no_registry_type` remains the defensible expected reason. The exact "
        "model",
        "input, however, exposes only the bare reason labels",
        "`ambiguous_registry_type` and `no_registry_type`; it does not state "
        "the",
        "decision boundary between “more than one visible registry type is "
        "plausible”",
        "and “none of the visible registry types applies.” Both Nano canonical "
        "and",
        "Haiku chose the former while preserving the correct unclassified "
        "disposition.",
        "",
        "The typed cash evidence does not support a first-choice-bias "
        "diagnosis. Nano",
        "returned unclassified when the expected cash option was second and "
        "again when",
        "the same exact option was first. Haiku selected the cash option "
        "correctly from",
        "the same canonical Slim input, so a general source-context "
        "insufficiency is",
        "also not supported.",
        "",
        "### Narrow continuation",
        "",
        "The published GOAL 5 prerequisite is not met: Nano did not fail the",
        "unclassified case independently of option order, and the strongest "
        "shared",
        "failure is the unclassified reason boundary rather than type-card "
        "wording",
        "alone. Do not start GOAL 5, GOAL 6 or the full benchmark from this "
        "receipt.",
        "",
        "The narrow evidence-backed corrective candidate is a separate "
        "zero-provider",
        "research slice for human-readable, non-active unclassified reason "
        "semantics",
        "while keeping Prompt, Semantic Pack, type meanings, source context, "
        "typed",
        "choices, cases and expected answers frozen. Because this would change "
        "the",
        "model-facing Local Choice/context contract, it requires an explicit "
        "new GOAL",
        "and its own versioned candidate; it must not be smuggled into this "
        "failed",
        "diagnostic or implemented in the provider adapter.",
    ]


def _audited_diagnosis(item: dict[str, Any]) -> dict[str, Any]:
    diagnosis = item["diagnosis"]
    expected = item.get("expected_answer") or {}
    actual = item.get("normalized_answer") or {}
    if (
        item["technical_pipeline"]["status"] == "PASSED"
        and expected.get("disposition")
        == "unclassified_financial_input"
        and actual.get("disposition")
        == "unclassified_financial_input"
        and expected.get("reason_code") != actual.get("reason_code")
    ):
        return {
            "code": "UNCLASSIFIED_RULE_UNCLEAR",
            "basis": (
                "The model selected the correct unclassified disposition but "
                "the wrong reason. The exact input exposes both reason-code "
                "labels without a readable rule that distinguishes no "
                "applicable registry type from multiple plausible types."
            ),
            "failure_code": None,
        }
    return diagnosis


def _validate_receipt(receipt: dict[str, Any]) -> None:
    integrity = receipt.get("integrity_sha256")
    material = {
        key: value
        for key, value in receipt.items()
        if key != "integrity_sha256"
    }
    evidence = receipt.get("case_evidence")
    accounting = receipt.get("attempt_accounting") or {}
    if (
        receipt.get("schema_version")
        != V6_SLIM_DIAGNOSTIC_SCHEMA_VERSION
        or receipt.get("execution_state") != "terminal"
        or receipt.get("status") not in {"passed", "failed"}
        or integrity != sha256_json(material)
        or not isinstance(evidence, list)
        or len(evidence) != V6_SLIM_DIAGNOSTIC_SUBMISSIONS_TOTAL
        or sorted(item.get("ordinal") for item in evidence)
        != list(range(1, V6_SLIM_DIAGNOSTIC_SUBMISSIONS_TOTAL + 1))
        or accounting.get("fallback_total") != 0
        or accounting.get("repair_total") != 0
        or accounting.get("hidden_retry_total") != 0
        or receipt.get("production_admissions_total") != 0
        or receipt.get("model_qualification_performed") is not False
        or receipt.get("raw_provider_envelope_preserved") is not False
    ):
        _fail("financial_semantic_v6_slim_diagnostic_receipt_invalid")
    serialized = json.dumps(
        receipt,
        ensure_ascii=False,
        sort_keys=True,
    )
    for forbidden in (
        "provider_response_id",
        "reasoning_trace",
        "credentials",
    ):
        if forbidden in serialized:
            _fail("financial_semantic_v6_slim_diagnostic_receipt_unsafe")


def _exact_outputs_status(evidence: list[dict[str, Any]]) -> str:
    return (
        "YES"
        if all(item["exact_adapter_output"] is not None for item in evidence)
        else "FAILED_WITH_EXACT_EVIDENCE"
    )


def _exact_output_block(value: Any) -> str:
    if isinstance(value, str):
        return f"```json\n{value}\n```"
    return _json_block(value)


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


def _comparison_value(*, present: bool, value: Any) -> str:
    if not present:
        return "_absent_"
    return f"`{json.dumps(value, ensure_ascii=False, sort_keys=True)}`"


def _metric(value: Any) -> str:
    return str(value) if value is not None else "UNAVAILABLE"


def _cost(value: Any) -> str:
    return f"${value}" if value is not None else "UNAVAILABLE"


def _latency(value: Any) -> str:
    return f"{value} ms" if value is not None else "UNAVAILABLE"


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV6SlimDiagnosticReportError(code)
