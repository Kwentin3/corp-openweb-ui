#!/usr/bin/env python3
"""Freeze and audit the two successor ambiguity decisions without model calls."""

from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from broker_reports_gate1.gate2_financial_evidence_decision import (
    DECISION_SCHEMA_VERSION,
    TYPED_REASON_CODES,
    UNCLASSIFIED_REASON_CODES,
)
from broker_reports_gate1.gate2_financial_evidence_materialization import (
    FinancialEvidenceExecutionMetadata,
    Gate2FinancialEvidenceMaterializerFactory,
    Gate2FinancialEvidenceValidatedDecisionFactory,
)
from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (
    FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION_V1,
    MATERIALIZATION_POLICY_VERSION_V1,
    sha256_json,
)
from broker_reports_gate1.gate2_financial_evidence_successor import (
    Gate2FinancialEvidenceSuccessorConfig,
    Gate2FinancialEvidenceSuccessorPromptFactory,
    Gate2FinancialEvidenceSuccessorRunnerFactory,
)
from scripts.live_gate2_financial_successor_qualification import (
    DEFAULT_MANIFEST_PATH,
    EXACT_MODEL_ID,
    PROVIDER_PROFILE_ID,
    build_successor_qualification_fixture,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
LOCAL_ROOT = SERVICE_ROOT / "local"
EVIDENCE_REPOSITORY_REVISION = (
    "ebf6d94d1c66bbe34a2790c192aa166d3b24f36c"
)
AUDIT_SCHEMA_VERSION = (
    "broker_reports_gate2_successor_ambiguity_failure_evidence_v1"
)
DISPUTED_CASE_IDS = (
    "syn_successor_multiple_hypotheses",
    "syn_successor_explicit_unclassified",
)
ATTEMPT_V1_RECEIPT_SHA256 = (
    "e2f68329f33e50acc3db8e149546041fcf47625074d1587f330932d685277a8f"
)
ATTEMPT_V2_RECEIPT_SHA256 = (
    "5332f99a2a3b10bc6d2594fc3aee0c93ce494ba4730eeeac6a9d58303d3b8271"
)
PROMPT_V1_CONTRACT_ID = (
    "broker_reports_gate2_financial_evidence_successor_prompt_v1"
)
PROMPT_V1_CONTENT = (
    "You are the bounded Gate 2 Financial Evidence decision step. "
    "Use only the eligible Registry definitions and package source "
    "values in the embedded input. Return exactly one of the four "
    "strict decision dispositions. Select only an eligible Registry "
    "input type and bind only listed source_value_ref values to their "
    "allowed roles. Never invent or transform literal values. Use "
    "unclassified_financial_input and preserve every package value "
    "when safe typing is not possible. Do not return IDs, paths, "
    "graphs, ownership, completeness, confidence, uncertainty, "
    "provenance or audit metadata. Return only the strict schema "
    "object.\n{{financial_evidence_successor_input_json}}"
)
PROMPT_V1_HASH = (
    "83f22755dd8380b4d91a5b143b1c991afdbed25afea959d9be3d882faee7f33b"
)

FACTORY_REQUIRED = (
    "build_successor_qualification_fixture, "
    "Gate2FinancialEvidenceSuccessorRunnerFactory.create, "
    "Gate2FinancialEvidenceValidatedDecisionFactory.create and "
    "Gate2FinancialEvidenceMaterializerFactory.create are the only "
    "failure-evidence reconstruction route"
)
FORBIDDEN = (
    "The audit must not call a provider, infer raw output from prose, "
    "change the frozen fixture, bypass canonical validation/materialization "
    "or include literals/source refs in the safe receipt"
)


class Gate2SuccessorAmbiguityAuditError(ValueError):
    pass


def _fail(code: str) -> None:
    raise Gate2SuccessorAmbiguityAuditError(code)


def prompt_hash(*, content: str, contract_id: str) -> str:
    return hashlib.sha256(
        (
            content
            + "\ncontract:"
            + contract_id
            + "\ndecision:"
            + DECISION_SCHEMA_VERSION
        ).encode("utf-8")
    ).hexdigest()


def load_pinned_receipt(
    *,
    path: Path,
    expected_sha256: str,
) -> tuple[dict[str, Any], str]:
    payload_bytes = path.read_bytes()
    observed_sha256 = hashlib.sha256(payload_bytes).hexdigest()
    if observed_sha256 != expected_sha256:
        _fail("ambiguity_audit_receipt_hash_mismatch")
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail("ambiguity_audit_receipt_json_invalid")
    if (
        not isinstance(payload, dict)
        or payload.get("status") != "failed"
        or payload.get("qualification_subject", {}).get("exact_model_id")
        != EXACT_MODEL_ID
        or payload.get("qualification_subject", {}).get(
            "provider_profile_id"
        )
        != PROVIDER_PROFILE_ID
        or payload.get("qualification", {}).get(
            "raw_provider_output_included"
        )
        is not False
    ):
        _fail("ambiguity_audit_receipt_contract_invalid")
    return payload, observed_sha256


def recover_exact_decision(
    *,
    case: Any,
    observed_disposition: str,
    observed_input_type_id: str | None,
    target_artifact_hash: str,
) -> dict[str, Any]:
    evaluated = 0
    matches: list[dict[str, Any]] = []
    for decision in _decision_candidates(
        case=case,
        observed_disposition=observed_disposition,
        observed_input_type_id=observed_input_type_id,
    ):
        evaluated += 1
        try:
            validated = Gate2FinancialEvidenceValidatedDecisionFactory(
                contract=case.scope.decision_contract
            ).create(decision)
            artifact = Gate2FinancialEvidenceMaterializerFactory(
                registry=case.scope.decision_contract.registry,
                source_package=case.scope.source_package,
                execution_metadata=FinancialEvidenceExecutionMetadata(
                    execution_ref=(
                        "execution:successor-qualification:"
                        + case.case_id
                    ),
                    decision_validation_ref=(
                        "validation:successor-qualification:"
                        + case.case_id
                    ),
                ),
            ).create().materialize(validated_decision=validated)
        except ValueError:
            continue
        if target_artifact_hash in {
            artifact["integrity_hash"],
            _legacy_v1_artifact_integrity_hash(artifact),
        }:
            matches.append(copy.deepcopy(decision))
    if len(matches) != 1:
        _fail(
            "ambiguity_audit_decision_recovery_not_unique:"
            f"{case.case_id}:{len(matches)}"
        )
    return {
        "decision": matches[0],
        "decision_sha256": sha256_json(matches[0]),
        "candidates_evaluated": evaluated,
        "matching_candidates": 1,
    }


def _legacy_v1_artifact_integrity_hash(
    artifact: dict[str, Any],
) -> str:
    """Reproduce the frozen v1 hash without admitting a v1 write."""

    payload = copy.deepcopy(artifact)
    payload["schema_version"] = (
        FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION_V1
    )
    payload["materialization_policy_version"] = (
        MATERIALIZATION_POLICY_VERSION_V1
    )
    payload.pop("semantic_pack", None)
    terminal_ids: list[str] = []
    for terminal in payload["typed_inputs"]:
        terminal.pop("semantic_pack_integrity_sha256", None)
        identity_roles = set(
            terminal["identity_policy"]["identity_roles"]
        )
        terminal["input_id"] = "finin_" + sha256_json(
            {
                "registry_hash": terminal["registry_hash"],
                "input_type_id": terminal["input_type_id"],
                "source_scope_ref": terminal["source_scope_ref"],
                "identity_values": [
                    {
                        "role_id": value["role_id"],
                        "source_value_ref": value["source_value_ref"],
                        "normalized_comparison_value": value[
                            "normalized_comparison_value"
                        ],
                    }
                    for value in terminal["source_values"]
                    if value["role_id"] in identity_roles
                ],
                "source_evidence_refs": terminal[
                    "source_evidence_refs"
                ],
            }
        )[:32]
        terminal.pop("integrity_hash", None)
        terminal["integrity_hash"] = sha256_json(terminal)
        terminal_ids.append(terminal["input_id"])
    for terminal in payload["unclassified_inputs"]:
        terminal.pop("semantic_pack_integrity_sha256", None)
        terminal["unclassified_input_id"] = "finun_" + sha256_json(
            {
                "registry_hash": terminal["registry_hash"],
                "source_scope_ref": terminal["source_scope_ref"],
                "source_values": [
                    {
                        "role_id": value["role_id"],
                        "source_value_ref": value["source_value_ref"],
                        "normalized_comparison_value": value[
                            "normalized_comparison_value"
                        ],
                    }
                    for value in terminal["source_values"]
                ],
                "source_evidence_refs": terminal[
                    "source_evidence_refs"
                ],
            }
        )[:32]
        terminal.pop("integrity_hash", None)
        terminal["integrity_hash"] = sha256_json(terminal)
        terminal_ids.append(terminal["unclassified_input_id"])
    payload["artifact_id"] = "finset_" + sha256_json(
        {
            "schema_version": payload["schema_version"],
            "registry_hash": payload["registry"]["registry_hash"],
            "source_package_integrity_hash": payload[
                "source_package"
            ]["integrity_hash"],
            "terminal_disposition": payload["terminal_disposition"],
            "terminal_ids": terminal_ids,
            "coverage_id": payload["coverage"]["coverage_id"],
        }
    )[:32]
    payload.pop("integrity_hash", None)
    return sha256_json(payload)


def _decision_candidates(
    *,
    case: Any,
    observed_disposition: str,
    observed_input_type_id: str | None,
) -> Iterable[dict[str, Any]]:
    contract = case.scope.decision_contract
    if observed_disposition == "typed_input":
        if not observed_input_type_id:
            _fail("ambiguity_audit_observed_type_missing")
        declaration = contract.registry.get(observed_input_type_id)
        role_choices: list[tuple[str, tuple[str | None, ...]]] = []
        for role_id in (
            declaration.required_roles + declaration.optional_roles
        ):
            spec = next(
                item
                for item in declaration.role_specs
                if item.role_id == role_id
            )
            refs: tuple[str | None, ...] = tuple(
                item.source_value_ref
                for item in contract.package.candidates
                if role_id in item.allowed_roles
                and item.value_type == spec.value_type
            )
            if role_id in declaration.optional_roles:
                refs = (None, *refs)
            if not refs:
                return
            role_choices.append((role_id, refs))
        for selected in itertools.product(
            *(item[1] for item in role_choices)
        ):
            bindings = {
                role_choices[index][0]: value
                for index, value in enumerate(selected)
            }
            for reason_code in TYPED_REASON_CODES:
                yield {
                    "decision": {
                        "disposition": "typed_input",
                        "input_type_id": observed_input_type_id,
                        "value_bindings": bindings,
                        "reason_code": reason_code,
                    }
                }
        return
    if observed_disposition != "unclassified_financial_input":
        _fail("ambiguity_audit_disposition_not_recoverable")
    candidates = contract.package.candidates
    selection_options = [
        (None, *item.allowed_roles) for item in candidates
    ]
    for selected_roles in itertools.product(*selection_options):
        if all(role_id is None for role_id in selected_roles):
            continue
        bindings = [
            {
                "role_id": role_id,
                "source_value_ref": candidate.source_value_ref,
            }
            for candidate, role_id in zip(candidates, selected_roles)
            if role_id is not None
        ]
        for reason_code in UNCLASSIFIED_REASON_CODES:
            yield {
                "decision": {
                    "disposition": "unclassified_financial_input",
                    "value_bindings": bindings,
                    "reason_code": reason_code,
                }
            }


def build_failure_evidence(
    *,
    attempt_v1: dict[str, Any],
    attempt_v1_sha256: str,
    attempt_v2: dict[str, Any],
    attempt_v2_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if prompt_hash(
        content=PROMPT_V1_CONTENT,
        contract_id=PROMPT_V1_CONTRACT_ID,
    ) != PROMPT_V1_HASH:
        _fail("ambiguity_audit_prompt_v1_snapshot_invalid")
    fixture = build_successor_qualification_fixture()
    manifest = json.loads(DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest_cases = {
        item["case_id"]: item for item in manifest["cases"]
    }
    cases = {item.case_id: item for item in fixture.cases}
    runner = Gate2FinancialEvidenceSuccessorRunnerFactory(
        registry=fixture.registry,
        model_client=object(),
        config=Gate2FinancialEvidenceSuccessorConfig(
            model_id=EXACT_MODEL_ID,
            provider_profile_id=PROVIDER_PROFILE_ID,
        ),
    ).create()
    prompt_v2 = Gate2FinancialEvidenceSuccessorPromptFactory().create()
    attempts = (
        ("attempt_v1", attempt_v1, attempt_v1_sha256),
        ("attempt_v2", attempt_v2, attempt_v2_sha256),
    )
    expected_prompt_versions = {
        "attempt_v1": PROMPT_V1_CONTRACT_ID + ":" + PROMPT_V1_HASH,
        "attempt_v2": prompt_v2.prompt_ref.removeprefix("code:")
        + ":"
        + prompt_v2.hash,
    }
    for attempt_id, receipt, _receipt_sha in attempts:
        if (
            receipt.get("qualification_identity", {}).get(
                "prompt_version"
            )
            != expected_prompt_versions[attempt_id]
        ):
            _fail("ambiguity_audit_prompt_identity_mismatch")

    private_cases: list[dict[str, Any]] = []
    safe_cases: list[dict[str, Any]] = []
    for case_id in DISPUTED_CASE_IDS:
        case = cases[case_id]
        model_input = runner.model_input(scope=case.scope)
        model_input_hash = sha256_json(model_input)
        case_private_attempts: list[dict[str, Any]] = []
        case_safe_attempts: list[dict[str, Any]] = []
        for attempt_id, receipt, receipt_sha in attempts:
            case_receipt = _case_receipt(receipt=receipt, case_id=case_id)
            if case_receipt.get("model_input_hash") != model_input_hash:
                _fail("ambiguity_audit_model_input_hash_mismatch")
            recovered = recover_exact_decision(
                case=case,
                observed_disposition=case_receipt[
                    "observed_disposition"
                ],
                observed_input_type_id=case_receipt.get(
                    "observed_input_type_id"
                ),
                target_artifact_hash=case_receipt[
                    "materialized_artifact_integrity_hash"
                ],
            )
            binding_count = _binding_count(recovered["decision"])
            covers_all = _covers_all_candidates(
                decision=recovered["decision"],
                case=case,
            )
            case_private_attempts.append(
                {
                    "attempt_id": attempt_id,
                    "receipt_sha256": receipt_sha,
                    "case_receipt": copy.deepcopy(case_receipt),
                    "recovered_provider_decision": recovered["decision"],
                    "decision_sha256": recovered["decision_sha256"],
                    "candidates_evaluated": recovered[
                        "candidates_evaluated"
                    ],
                    "matching_candidates": 1,
                }
            )
            case_safe_attempts.append(
                {
                    "attempt_id": attempt_id,
                    "receipt_sha256": receipt_sha,
                    "status": case_receipt["status"],
                    "expected_disposition": case_receipt[
                        "expected_disposition"
                    ],
                    "observed_disposition": case_receipt[
                        "observed_disposition"
                    ],
                    "observed_input_type_id": case_receipt.get(
                        "observed_input_type_id"
                    ),
                    "model_input_hash": model_input_hash,
                    "materialized_artifact_integrity_hash": case_receipt[
                        "materialized_artifact_integrity_hash"
                    ],
                    "decision_sha256": recovered["decision_sha256"],
                    "binding_count": binding_count,
                    "covers_all_candidates": covers_all,
                    "candidates_evaluated": recovered[
                        "candidates_evaluated"
                    ],
                    "matching_candidates": 1,
                    "canonical_validation_ran": case_receipt[
                        "canonical_validation_ran"
                    ],
                    "raw_provider_output_included": False,
                }
            )
        declarations = [
            asdict(fixture.registry.get(input_type_id))
            for input_type_id in case.scope.decision_contract.eligible_type_ids
        ]
        private_cases.append(
            {
                "case_id": case_id,
                "manifest_case": copy.deepcopy(manifest_cases[case_id]),
                "deterministic_scope": copy.deepcopy(case.scope.package),
                "registry_declarations": declarations,
                "canonical_decision_schema": (
                    case.scope.decision_contract.canonical_schema()
                ),
                "provider_projection": (
                    case.scope.decision_contract.openai_response_format()
                ),
                "model_input": model_input,
                "expected_model_output": copy.deepcopy(
                    case.expected_model_output
                ),
                "attempts": case_private_attempts,
            }
        )
        safe_cases.append(
            {
                "case_id": case_id,
                "expected_disposition": case.expected_disposition,
                "eligible_type_ids": list(
                    case.scope.decision_contract.eligible_type_ids
                ),
                "eligible_types_total": len(
                    case.scope.decision_contract.eligible_type_ids
                ),
                "source_values_total": len(
                    case.scope.source_package.source_values
                ),
                "model_input_hash": model_input_hash,
                "deterministic_scope_integrity_hash": case.scope.package[
                    "integrity_hash"
                ],
                "canonical_schema_hash": (
                    case.scope.decision_contract.canonical_schema_hash()
                ),
                "provider_schema_hash": (
                    case.scope.decision_contract.provider_schema_hash(
                        "openai"
                    )
                ),
                "attempts": case_safe_attempts,
            }
        )
    common_identity = _common_identity(
        attempt_v1=attempt_v1,
        attempt_v2=attempt_v2,
    )
    private = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "evidence_class": "private_synthetic_failure_evidence",
        "repository_revision": EVIDENCE_REPOSITORY_REVISION,
        "contains_customer_data": False,
        "provider_calls_created_by_audit": 0,
        "identity": common_identity,
        "prompt_snapshots": {
            "attempt_v1": {
                "contract_id": PROMPT_V1_CONTRACT_ID,
                "content": PROMPT_V1_CONTENT,
                "hash": PROMPT_V1_HASH,
            },
            "attempt_v2": {
                "contract_id": prompt_v2.prompt_ref.removeprefix("code:"),
                "content": prompt_v2.content,
                "hash": prompt_v2.hash,
            },
        },
        "cases": private_cases,
    }
    safe = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "evidence_class": "repository_safe_value_free_summary",
        "status": "passed",
        "repository_revision": EVIDENCE_REPOSITORY_REVISION,
        "contains_customer_data": False,
        "raw_provider_output_included": False,
        "source_literals_included": False,
        "source_value_refs_included": False,
        "provider_calls_created_by_audit": 0,
        "identity": common_identity,
        "prompt_versions": expected_prompt_versions,
        "receipt_sha256": {
            "attempt_v1": attempt_v1_sha256,
            "attempt_v2": attempt_v2_sha256,
        },
        "cases_total": len(safe_cases),
        "cases": safe_cases,
        "checks": {
            "failure_evidence_complete": True,
            "two_cases_exactly_recovered": True,
            "mixed_revisions_zero": True,
            "new_provider_calls_zero": True,
            "canonical_factory_route_used": True,
            "unique_decision_recovery": True,
        },
    }
    _validate_safe_payload(safe=safe, private=private)
    return private, safe


def _case_receipt(
    *,
    receipt: dict[str, Any],
    case_id: str,
) -> dict[str, Any]:
    matches = [
        item
        for item in receipt.get("qualification", {}).get("cases", [])
        if item.get("case_id") == case_id
    ]
    if len(matches) != 1:
        _fail("ambiguity_audit_case_receipt_missing")
    result = matches[0]
    if (
        result.get("provider_generated_output") is not True
        or result.get("canonical_validation_ran") is not True
        or result.get("raw_provider_output_included") is not False
    ):
        _fail("ambiguity_audit_case_receipt_invalid")
    return result


def _common_identity(
    *,
    attempt_v1: dict[str, Any],
    attempt_v2: dict[str, Any],
) -> dict[str, Any]:
    first = copy.deepcopy(attempt_v1["qualification_identity"])
    second = copy.deepcopy(attempt_v2["qualification_identity"])
    for prompt_derived_field in (
        "prompt_version",
        "successor_prompt_contract",
    ):
        first.pop(prompt_derived_field, None)
        second.pop(prompt_derived_field, None)
    if first != second:
        _fail("ambiguity_audit_mixed_qualification_identity")
    return first


def _binding_count(decision: dict[str, Any]) -> int:
    payload = decision["decision"]
    bindings = payload["value_bindings"]
    if isinstance(bindings, list):
        return len(bindings)
    return sum(value is not None for value in bindings.values())


def _covers_all_candidates(
    *,
    decision: dict[str, Any],
    case: Any,
) -> bool:
    payload = decision["decision"]
    bindings = payload["value_bindings"]
    if isinstance(bindings, list):
        bound = {item["source_value_ref"] for item in bindings}
    else:
        bound = {value for value in bindings.values() if value is not None}
    candidates = {
        item.source_value_ref
        for item in case.scope.decision_contract.package.candidates
    }
    return bound == candidates


def _validate_safe_payload(
    *,
    safe: dict[str, Any],
    private: dict[str, Any],
) -> None:
    safe_text = json.dumps(safe, ensure_ascii=False, sort_keys=True)
    for case in private["cases"]:
        for cell in case["manifest_case"].get("cells", []):
            literal = cell.get("literal")
            if isinstance(literal, str) and literal in safe_text:
                _fail("ambiguity_audit_literal_in_safe_payload")
    if (
        '"source_value_ref"' in safe_text
        or safe.get("provider_calls_created_by_audit") != 0
        or not all(safe["checks"].values())
    ):
        _fail("ambiguity_audit_safe_payload_invalid")


def write_evidence_bundle(
    *,
    private: dict[str, Any],
    safe: dict[str, Any],
    private_path: Path,
    safe_path: Path,
) -> dict[str, Any]:
    private_bytes = _json_bytes(private)
    private_sha256 = hashlib.sha256(private_bytes).hexdigest()
    safe_with_hash = copy.deepcopy(safe)
    safe_with_hash["private_evidence_sha256"] = private_sha256
    _atomic_write(path=private_path, payload=private_bytes)
    _atomic_write(path=safe_path, payload=_json_bytes(safe_with_hash))
    return safe_with_hash


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _atomic_write(*, path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--attempt-v1-receipt",
        type=Path,
        default=LOCAL_ROOT / "gate2_financial_successor_goal6.safe.json",
    )
    parser.add_argument(
        "--attempt-v2-receipt",
        type=Path,
        default=(
            LOCAL_ROOT
            / "gate2_financial_successor_goal6_prompt_v2.safe.json"
        ),
    )
    parser.add_argument(
        "--private-output",
        type=Path,
        default=(
            LOCAL_ROOT
            / "gate2_successor_ambiguity_goal0.private.json"
        ),
    )
    parser.add_argument(
        "--safe-output",
        type=Path,
        default=(
            LOCAL_ROOT
            / "gate2_successor_ambiguity_goal0.receipt.safe.json"
        ),
    )
    args = parser.parse_args()
    attempt_v1, attempt_v1_sha256 = load_pinned_receipt(
        path=args.attempt_v1_receipt,
        expected_sha256=ATTEMPT_V1_RECEIPT_SHA256,
    )
    attempt_v2, attempt_v2_sha256 = load_pinned_receipt(
        path=args.attempt_v2_receipt,
        expected_sha256=ATTEMPT_V2_RECEIPT_SHA256,
    )
    private, safe = build_failure_evidence(
        attempt_v1=attempt_v1,
        attempt_v1_sha256=attempt_v1_sha256,
        attempt_v2=attempt_v2,
        attempt_v2_sha256=attempt_v2_sha256,
    )
    written = write_evidence_bundle(
        private=private,
        safe=safe,
        private_path=args.private_output,
        safe_path=args.safe_output,
    )
    print(
        json.dumps(
            {
                "status": written["status"],
                "schema_version": written["schema_version"],
                "cases_total": written["cases_total"],
                "provider_calls_created_by_audit": 0,
                "private_evidence_sha256": written[
                    "private_evidence_sha256"
                ],
                "safe_output": str(args.safe_output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
