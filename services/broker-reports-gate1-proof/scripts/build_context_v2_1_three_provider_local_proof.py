from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (  # noqa: E402,E501
    sha256_json,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_context_v2_1_provider_proof import (  # noqa: E402,E501
    CONTEXT_V2_1_PROVIDER_PROOF_POLICY_VERSION,
    Gate2FinancialSemanticV6ContextV21ProviderProofFactory,
    validate_financial_semantic_v6_context_v2_1_provider_case_proof,
)
from broker_reports_gate1.gate2_financial_semantic_v6_outcome_audit import (  # noqa: E402,E501
    validate_financial_semantic_v6_outcome_audit,
)
from broker_reports_gate1.gate2_financial_semantic_v6_qualification import (  # noqa: E402,E501
    Gate2FinancialSemanticV6QualificationFixtureFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_smoke_report import (  # noqa: E402,E501
    Gate2FinancialSemanticV6TransparentSmokeReportFactory,
)
from broker_reports_gate1.gate2_provider_adapters import (  # noqa: E402
    CONTEXT_V2_1_LOCAL_SCHEMA_PROJECTION_POLICY_VERSION,
)


REPORT_ROOT = REPO_ROOT / "docs" / "reports" / "2026-07-29"
TRANSPARENT_REPORT_PATH = (
    REPORT_ROOT
    / "BROKER_REPORTS_GATE2_CONTEXT_V2_1_THREE_PROVIDER_LOCAL_PROOF_GOAL11.transparent.json"
)
SAFE_RECEIPT_PATH = (
    REPORT_ROOT
    / "BROKER_REPORTS_GATE2_CONTEXT_V2_1_THREE_PROVIDER_LOCAL_PROOF_GOAL11.receipt.safe.json"
)
MARKDOWN_REPORT_PATH = (
    REPORT_ROOT
    / "BROKER_REPORTS_GATE2_CONTEXT_V2_1_THREE_PROVIDER_LOCAL_PROOF_GOAL11.report.md"
)
SNAPSHOT_KEY = b"broker-reports-context-v2-1-provider-proof-key"
CONTINUATION_KEY = b"broker-reports-context-v2-1-provider-replay"

_CASE_IDS = (
    "syn_successor_v2_unique_cash",
    "syn_successor_v2_no_registry_type",
    "syn_successor_v2_multiple_compatible",
    "syn_successor_v2_detail_vs_subtotal",
)
_PROFILES = (
    "openai_gpt",
    "anthropic_claude",
    "google_gemini",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    transparent_report, safe_receipt, markdown_report = _build_outputs()
    outputs = {
        TRANSPARENT_REPORT_PATH: _json_text(transparent_report),
        SAFE_RECEIPT_PATH: _json_text(safe_receipt),
        MARKDOWN_REPORT_PATH: markdown_report,
    }
    for path, content in outputs.items():
        if arguments.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                raise SystemExit(f"context_v2_1_provider_proof_drift:{path.name}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
    return 0


def _build_outputs() -> tuple[dict[str, Any], dict[str, Any], str]:
    audit_manifest = _read_json(
        SERVICE_ROOT
        / "benchmarks"
        / "gate2_financial_semantic_v6_outcome_audit_v1"
        / "manifest.json"
    )
    historical_manifest = _read_json(
        SERVICE_ROOT
        / "benchmarks"
        / "gate2_financial_semantic_v6"
        / "manifest.json"
    )
    base_manifest = _read_json(
        SERVICE_ROOT
        / "benchmarks"
        / "gate2_financial_successor_v2"
        / "manifest.json"
    )
    semantic_pack = _read_json(
        SERVICE_ROOT
        / "semantic_packs"
        / "broker_reports_financial_semantic_pack.v1.json"
    )
    reason_catalog_v2 = _read_json(
        SERVICE_ROOT
        / "managed_assets"
        / "decision_reasons"
        / "broker_reports_gate2_financial_decision_reason_catalog.v2.json"
    )
    audit = validate_financial_semantic_v6_outcome_audit(
        manifest=audit_manifest,
        historical_manifest=historical_manifest,
        base_manifest=base_manifest,
        semantic_pack=semantic_pack,
        reason_catalog_v2=reason_catalog_v2,
    )
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    fixture = Gate2FinancialSemanticV6QualificationFixtureFactory(
        registry=registry,
        snapshot_authority_key=SNAPSHOT_KEY,
        continuation_key=CONTINUATION_KEY,
    ).create(
        manifest=historical_manifest,
        base_manifest=base_manifest,
    )
    audit_cases = {
        item["case_id"]: item for item in audit_manifest["cases"]
    }
    semantic_cases = {
        item.case_id: item for item in fixture.semantic_cases
    }
    active_choice_before = {
        case_id: (
            copy.deepcopy(
                semantic_cases[case_id].choice_contract.choice_schema
            ),
            semantic_cases[case_id].choice_contract.choice_schema_hash,
        )
        for case_id in _CASE_IDS
    }
    proof_factory = (
        Gate2FinancialSemanticV6ContextV21ProviderProofFactory(
            registry=registry,
            snapshot_authority_key=SNAPSHOT_KEY,
        )
    )
    proof_cases = []
    safe_cases = []
    proofs = []
    for case_id in _CASE_IDS:
        case = semantic_cases[case_id]
        expected = _expected_answer(
            case=case,
            audited_case=audit_cases[case_id],
        )
        local_output = _local_output(case=case, expected=expected)
        for profile_id in _PROFILES:
            response = _simulated_response(
                profile_id=profile_id,
                local_output=local_output,
            )
            proof = proof_factory.create_case(
                case=case,
                provider_profile_id=profile_id,
                expected_answer=expected,
                simulated_provider_response=response,
            )
            validate_financial_semantic_v6_context_v2_1_provider_case_proof(
                proof=proof,
                factory=proof_factory,
                case=case,
                expected_answer=expected,
                simulated_provider_response=response,
            )
            proofs.append(proof)
            proof_cases.append(
                proof.transparent_report_case_evidence
            )
            safe_cases.append(proof.safe_summary())
    transparent_report = (
        Gate2FinancialSemanticV6TransparentSmokeReportFactory()
        .create_context_v2_1_provider_report(case_evidence=proof_cases)
    )
    transparent_report_hash = sha256_json(transparent_report)
    execution_accounting = {
        key: sum(
            proof.execution_accounting[key]
            for proof in proofs
        )
        for key in (
            "provider_calls_total",
            "semantic_repair_total",
            "fallback_total",
            "retry_total",
        )
    }
    profile_projection_checks = {
        profile_id: all(
            proof.provider_profile_id == profile_id
            and proof.adapter_adapted_schema_hash
            == proof.transparent_report_projection["provider"][
                "adapted_schema_hash"
            ]
            and proof.adapter_canonical_schema_hash
            == proof.transparent_report_projection["provider"][
                "canonical_schema_hash"
            ]
            and proof.provider_visible_response_schema
            == proof.transparent_report_projection[
                "exact_provider_visible_response_schema"
            ]
            for proof in proofs
            if proof.provider_profile_id == profile_id
        )
        and sum(
            proof.provider_profile_id == profile_id
            for proof in proofs
        )
        == len(_CASE_IDS)
        for profile_id in _PROFILES
    }
    choice_reason_enums_preserved = all(
        _semantic_enums(proof.provider_visible_response_schema)
        == _semantic_enums(
            semantic_cases[
                proof.case_id
            ].choice_contract.context_v2_1_response_profile.response_schema
        )
        and set(_semantic_enums(proof.provider_visible_response_schema))
        == {"choice", "reason"}
        for proof in proofs
    )
    active_v6_choice_schema_unchanged = all(
        (
            semantic_cases[case_id].choice_contract.choice_schema,
            semantic_cases[case_id].choice_contract.choice_schema_hash,
        )
        == active_choice_before[case_id]
        for case_id in _CASE_IDS
    )
    checks = {
        "openai_projection_exact": profile_projection_checks[
            "openai_gpt"
        ],
        "anthropic_projection_exact": profile_projection_checks[
            "anthropic_claude"
        ],
        "google_projection_exact": profile_projection_checks[
            "google_gemini"
        ],
        "choice_reason_enums_preserved": (
            choice_reason_enums_preserved
        ),
        "schema_projection_policy_exact": all(
            proof.schema_projection_policy_version
            == CONTEXT_V2_1_LOCAL_SCHEMA_PROJECTION_POLICY_VERSION
            for proof in proofs
        ),
        "materialization_exact": all(
            proof.replay_materialized_artifact_hash
            == proof.total_materialization["canonical_artifact_hash"]
            for proof in proofs
        ),
        "persistence_restore_exact": all(
            proof.restore_exact
            and proof.restored_snapshot_integrity_hash
            == proof.replay_snapshot_integrity_hash
            for proof in proofs
        ),
        "offline_replay_exact": all(
            proof.replay_exact for proof in proofs
        ),
        "transparent_report_projection_exact": all(
            case["field_level_diff"]["all_fields_match"]
            for case in transparent_report["cases"]
        ),
        "active_v6_choice_schema_unchanged": (
            active_v6_choice_schema_unchanged
        ),
        "runtime_remained_inactive": all(
            proof.active is False
            and proof.transport_eligible is False
            and semantic_cases[
                proof.case_id
            ].choice_contract.context_v2_1_response_profile.active
            is False
            and semantic_cases[
                proof.case_id
            ].choice_contract.context_v2_1_response_profile.transport_eligible
            is False
            for proof in proofs
        ),
    }
    if (
        not proofs
        or not all(checks.values())
        or execution_accounting
        != {
            "provider_calls_total": 0,
            "semantic_repair_total": 0,
            "fallback_total": 0,
            "retry_total": 0,
        }
    ):
        raise ValueError("context_v2_1_provider_proof_checks_failed")
    safe_material = {
        "schema_version": (
            "broker_reports_gate2_context_v2_1_three_provider_"
            "local_proof_safe_receipt_v1"
        ),
        "policy_version": CONTEXT_V2_1_PROVIDER_PROOF_POLICY_VERSION,
        "status": "passed",
        "active": False,
        "transport_eligible": False,
        "contains_customer_data": False,
        "synthetic_evidence_only": True,
        "outcome_audit": audit.safe_summary(),
        "transparent_report_schema_version": transparent_report[
            "schema_version"
        ],
        "transparent_report_sha256": transparent_report_hash,
        "provider_profiles": list(_PROFILES),
        "semantic_fixtures": list(_CASE_IDS),
        "provider_case_paths_total": len(safe_cases),
        "case_safe_summaries": sorted(
            safe_cases,
            key=lambda item: (
                item["provider_profile_id"],
                item["case_id"],
            ),
        ),
        "checks": checks,
        "execution_accounting": execution_accounting,
    }
    safe_receipt = {
        **safe_material,
        "integrity_sha256": sha256_json(safe_material),
    }
    return (
        transparent_report,
        safe_receipt,
        _markdown_report(
            transparent_report_hash=transparent_report_hash,
            safe_receipt=safe_receipt,
        ),
    )


def _expected_answer(*, case: Any, audited_case: dict[str, Any]) -> dict[str, Any]:
    if audited_case["expected_disposition"] == "typed_input":
        expected = case.expected_model_choice
        matching_options = tuple(
            item
            for item in case.compilation.typed_options
            if item.typed_option_id == expected.get("typed_option_id")
        )
        if (
            expected.get("disposition") != "typed_input"
            or len(matching_options) != 1
            or matching_options[0].input_type_id
            != audited_case["expected_input_type_id"]
        ):
            raise ValueError("context_v2_1_provider_proof_typed_truth_invalid")
        return dict(expected)
    return {
        "disposition": "unclassified_financial_input",
        "reason_code": audited_case["expected_reason_code"],
    }


def _local_output(*, case: Any, expected: dict[str, Any]) -> dict[str, Any]:
    if expected["disposition"] == "unclassified_financial_input":
        return {
            "choice": "unclassified",
            "reason": expected["reason_code"],
        }
    row = next(
        item
        for item in case.packet.context_v2_mapping_receipt.choice_restoration
        if item["typed_option_id"] == expected["typed_option_id"]
    )
    return {"choice": row["choice_key"]}


def _simulated_response(
    *,
    profile_id: str,
    local_output: dict[str, Any],
) -> dict[str, Any]:
    visible_output = (
        {"broker_reports_gate2_choice": local_output}
        if profile_id == "openai_gpt"
        else local_output
    )
    encoded = json.dumps(
        visible_output,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    if profile_id == "openai_gpt":
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": encoded,
                    }
                }
            ]
        }
    if profile_id == "anthropic_claude":
        return {
            "content": [{"type": "text", "text": encoded}],
            "stop_reason": "end_turn",
        }
    if profile_id == "google_gemini":
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": encoded},
                }
            ],
        }
    raise ValueError("context_v2_1_provider_proof_profile_unknown")


def _semantic_enums(
    value: Any,
) -> dict[str, tuple[tuple[Any, ...], ...]]:
    found: dict[str, dict[str, tuple[Any, ...]]] = {}

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            properties = node.get("properties")
            if isinstance(properties, dict):
                for name in ("choice", "reason"):
                    field = properties.get(name)
                    enum = (
                        field.get("enum")
                        if isinstance(field, dict)
                        else None
                    )
                    if isinstance(enum, list):
                        key = json.dumps(
                            enum,
                            ensure_ascii=True,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        found.setdefault(name, {})[key] = tuple(enum)
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return {
        name: tuple(enums[key] for key in sorted(enums))
        for name, enums in sorted(found.items())
    }


def _markdown_report(
    *,
    transparent_report_hash: str,
    safe_receipt: dict[str, Any],
) -> str:
    return "\n".join(
        (
            "# Broker Reports Gate 2 — Context V2.1 three-provider local proof",
            "",
            "## Verdict",
            "",
            "`PASSED` for the local, non-active, zero-provider-call scope.",
            "",
            "- OpenAI, Anthropic and Google adapter projections completed for "
            "all four governed semantic fixtures.",
            "- Adapter extraction, V2.1 Choice parsing, local-key restoration, "
            "canonical validation/materialization, persistence, restore and "
            "exact offline replay completed.",
            "- `choice` and `reason` enums remain present in every "
            "provider-visible schema.",
            "- The local schema projection is bound to "
            f"`{CONTEXT_V2_1_LOCAL_SCHEMA_PROJECTION_POLICY_VERSION}`; "
            "the canonical adapter versions are not relabelled.",
            "- Each prepared request is an exact rebuild from the sealed "
            "request and repository provider profile; full request shape, "
            "schema projection, wrapper, metadata and transform count match.",
            "- Every simulated provider response has exactly one governed "
            "terminal envelope before adapter extraction.",
            "- The proof leaves each active V6 Choice schema/hash unchanged; "
            "Context V2.1 remains inactive and transport-ineligible.",
            "- Provider calls, semantic repair, fallback and retry are all `0`.",
            "",
            "## Exact transparent evidence",
            "",
            "The exact synthetic request, system message, user content, "
            "provider-visible schema, adapter-extracted output, normalized "
            "answer, expected answer and field-level diff for each of the 12 "
            "provider/case paths are in the "
            "[transparent report]"
            "(./BROKER_REPORTS_GATE2_CONTEXT_V2_1_THREE_PROVIDER_LOCAL_PROOF_GOAL11.transparent.json).",
            "The public case projector returns only a raw closed projection "
            "and cannot mint evidence. ProviderProofFactory creates an "
            "unissued full proof, independently recomputes it, requires exact "
            "equality, and only then invokes the private authority that issues "
            "an opaque immutable case-evidence token. Independent full-proof "
            "validation follows; the aggregate accepts only the issued token, "
            "not raw or resealed proof dictionaries, and revalidates the "
            "frozen GOAL 10 baseline plus closed projection fields.",
            "",
            "Actual token counts, cost and latency are recorded as `null` with "
            "`NOT_APPLICABLE_NO_PROVIDER_CALL`; no live measurements are "
            "claimed.",
            "",
            f"- Transparent report SHA-256: `{transparent_report_hash}`",
            "- Privacy-safe aggregate: "
            "[safe receipt]"
            "(./BROKER_REPORTS_GATE2_CONTEXT_V2_1_THREE_PROVIDER_LOCAL_PROOF_GOAL11.receipt.safe.json)",
            f"- Safe receipt integrity: `{safe_receipt['integrity_sha256']}`",
            "",
            "## Boundary",
            "",
            "All exact payloads are synthetic repository fixtures. No "
            "customer data, credentials, provider response identifiers or "
            "provider calls are present. This proof qualifies local "
            "infrastructure only; it does not qualify a model and does not "
            "authorize GOAL 12 calls until this PR is reviewed, green and "
            "merged.",
            "",
        )
    )


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path}")
    return value


def _json_text(value: dict[str, Any]) -> str:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )


if __name__ == "__main__":
    raise SystemExit(main())
