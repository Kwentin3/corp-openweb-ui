#!/usr/bin/env python3
"""Reconstruct Nano V3/V4 decision evidence without provider calls."""

from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
import subprocess
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Iterable

from broker_reports_gate1.gate2_economy_budget import (
    estimate_gate2_request_input_tokens,
)
from broker_reports_gate1.gate2_financial_evidence_decision import (
    NO_FINANCIAL_REASON_CODES,
    TYPED_REASON_CODES,
    UNCLASSIFIED_REASON_CODES,
    UNSUPPORTED_REASON_CODES,
)
from broker_reports_gate1.gate2_financial_evidence_materialization import (
    FinancialEvidenceExecutionMetadata,
    Gate2FinancialEvidenceMaterializerFactory,
    Gate2FinancialEvidenceValidatedDecisionFactory,
)
from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (
    sha256_json,
)
from broker_reports_gate1.gate2_financial_evidence_successor import (
    Gate2FinancialEvidenceSuccessorConfig,
    Gate2FinancialEvidenceSuccessorRunnerFactory,
)
from broker_reports_gate1.gate2_financial_evidence_successor_projection import (
    Gate2FinancialEvidenceSuccessorProviderProjectionFactory,
)
from broker_reports_gate1.gate2_model_requests import (
    Gate2OpenWebUIRequestBuilder,
)
from scripts.live_gate2_financial_successor_qualification_v2 import (
    DEFAULT_MANIFEST_PATH,
    EXACT_MODEL_ID,
    build_successor_qualification_fixture_v2,
)


V3_REVISION = "eb5c6011066a524d97aad9ac3b07d2d969f3db87"
V4_REVISION = "2b451e7a1168165b1b1902c0c635b7b8bf246715"
V4_TERMINAL_REVIEW_REVISION = (
    "6a68cd6ae890742363af1a5a644f35d25189f6c3"
)
V3_RECEIPT_SHA256 = (
    "39f6a990d233926d7493056570730bdfa82f29df9a63d3f8f9d6cfa0e47dc641"
)
V4_RECEIPT_SHA256 = (
    "c371262b9c9d6911b2bb250f441f1f158e5ed1259e93d2d3eefa6df5280f5426"
)
PROVIDER_PROFILE_ID = "openai_gpt"
V3_MODEL_INPUT_SCHEMA = (
    "broker_reports_gate2_financial_evidence_successor_model_input_v3"
)
V4_MODEL_INPUT_SCHEMA = (
    "broker_reports_gate2_financial_evidence_successor_model_input_v4"
)
V3_PROMPT_CONTRACT = (
    "broker_reports_gate2_financial_evidence_successor_prompt_v3"
)
V4_PROMPT_CONTRACT = (
    "broker_reports_gate2_financial_evidence_managed_prompt_v1"
)
V3_REQUEST_PROFILE = "financial_evidence_successor_qualification_v2"
V4_REQUEST_PROFILE = "financial_evidence_successor_qualification_v3"
AUDIT_SCHEMA_VERSION = (
    "broker_reports_gate2_nano_semantic_decision_evidence_audit_v1"
)
SNAPSHOT_SCHEMA_VERSION = (
    "broker_reports_gate2_nano_revision_evidence_snapshot_v1"
)

FACTORY_REQUIRED = (
    "build_successor_qualification_fixture_v2, "
    "Gate2FinancialEvidenceSuccessorRunnerFactory.create, "
    "Gate2OpenWebUIRequestBuilder.build, "
    "Gate2FinancialEvidenceValidatedDecisionFactory.create and "
    "Gate2FinancialEvidenceMaterializerFactory.create are the only "
    "evidence reconstruction route"
)
FORBIDDEN = (
    "The audit must not create a provider client, call a model, change a "
    "fixture or product contract, infer raw response bytes, or commit "
    "source literals and source refs"
)


class Gate2NanoSemanticEvidenceAuditError(ValueError):
    pass


class _NoCallClient:
    async def extract(self, **_kwargs: Any) -> Any:
        raise AssertionError("nano_semantic_audit_provider_call_forbidden")


def _fail(code: str) -> None:
    raise Gate2NanoSemanticEvidenceAuditError(code)


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _compact_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return copy.deepcopy(value)


def load_pinned_json(
    *,
    path: Path,
    expected_sha256: str,
) -> tuple[dict[str, Any], str]:
    payload_bytes = path.read_bytes()
    observed_sha256 = _sha256_bytes(payload_bytes)
    if observed_sha256 != expected_sha256:
        _fail("nano_semantic_audit_receipt_hash_mismatch")
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail("nano_semantic_audit_receipt_json_invalid")
    if not isinstance(payload, dict):
        _fail("nano_semantic_audit_receipt_shape_invalid")
    return payload, observed_sha256


def _git_revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _mode_contract(mode: str) -> dict[str, str]:
    if mode == "v3":
        return {
            "revision": V3_REVISION,
            "receipt_sha256": V3_RECEIPT_SHA256,
            "model_input_schema": V3_MODEL_INPUT_SCHEMA,
            "prompt_contract": V3_PROMPT_CONTRACT,
            "request_profile": V3_REQUEST_PROFILE,
            "execution_prefix": "successor-v2-qualification",
        }
    if mode == "v4":
        return {
            "revision": V4_REVISION,
            "receipt_sha256": V4_RECEIPT_SHA256,
            "model_input_schema": V4_MODEL_INPUT_SCHEMA,
            "prompt_contract": V4_PROMPT_CONTRACT,
            "request_profile": V4_REQUEST_PROFILE,
            "execution_prefix": "managed-shadow-qualification",
        }
    _fail("nano_semantic_audit_mode_invalid")


def _runner(*, fixture: Any, mode: str) -> Any:
    contract = _mode_contract(mode)
    return Gate2FinancialEvidenceSuccessorRunnerFactory(
        registry=fixture.registry,
        model_client=_NoCallClient(),
        config=Gate2FinancialEvidenceSuccessorConfig(
            model_id=EXACT_MODEL_ID,
            provider_profile_id=PROVIDER_PROFILE_ID,
            model_input_schema_version=contract["model_input_schema"],
            prompt_contract_id=contract["prompt_contract"],
        ),
    ).create()


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
        _fail("nano_semantic_audit_case_receipt_missing")
    case = matches[0]
    if (
        case.get("provider_generated_output") is not True
        or case.get("canonical_validation_ran") is not True
        or case.get("raw_provider_output_included") is not False
    ):
        _fail("nano_semantic_audit_case_receipt_invalid")
    return copy.deepcopy(case)


def _preflight_case(
    *,
    receipt: dict[str, Any],
    case_id: str,
) -> dict[str, Any]:
    matches = [
        item
        for item in receipt.get("preflight_cases", [])
        if item.get("case_id") == case_id
    ]
    if len(matches) != 1:
        _fail("nano_semantic_audit_preflight_case_missing")
    return copy.deepcopy(matches[0])


def _decision_candidates(
    *,
    case: Any,
    observed_disposition: str,
    observed_input_type_id: str | None,
) -> Iterable[dict[str, Any]]:
    contract = case.scope.decision_contract
    if observed_disposition == "typed_input":
        if not observed_input_type_id:
            _fail("nano_semantic_audit_observed_type_missing")
        declaration = contract.registry.get(observed_input_type_id)
        choices: list[tuple[str, tuple[str | None, ...]]] = []
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
            choices.append((role_id, refs))
        for selected in itertools.product(*(item[1] for item in choices)):
            bindings = {
                choices[index][0]: value
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
    if observed_disposition == "unclassified_financial_input":
        candidates = contract.package.candidates
        role_options = [
            (None, *item.allowed_roles) for item in candidates
        ]
        for selected_roles in itertools.product(*role_options):
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
        return
    reason_codes = (
        NO_FINANCIAL_REASON_CODES
        if observed_disposition == "no_financial_input"
        else (
            UNSUPPORTED_REASON_CODES
            if observed_disposition == "unsupported"
            else ()
        )
    )
    for reason_code in reason_codes:
        yield {
            "decision": {
                "disposition": observed_disposition,
                "reason_code": reason_code,
            }
        }


def recover_exact_decision(
    *,
    case: Any,
    observed_disposition: str,
    observed_input_type_id: str | None,
    target_artifact_hash: str,
    execution_prefix: str,
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
                        f"execution:{execution_prefix}:{case.case_id}"
                    ),
                    decision_validation_ref=(
                        f"validation:{execution_prefix}:{case.case_id}"
                    ),
                ),
            ).create().materialize(validated_decision=validated)
        except ValueError:
            continue
        if artifact["integrity_hash"] == target_artifact_hash:
            matches.append(copy.deepcopy(decision))
    if len(matches) != 1:
        _fail(
            "nano_semantic_audit_decision_recovery_not_unique:"
            f"{case.case_id}:{len(matches)}"
        )
    return {
        "decision": matches[0],
        "decision_sha256": sha256_json(matches[0]),
        "candidates_evaluated": evaluated,
        "matching_candidates": 1,
        "recovery_basis": (
            "unique canonical validation and deterministic materialization "
            "match to the recorded terminal artifact integrity hash"
        ),
    }


def _request_projection_bytes(form_data: dict[str, Any]) -> int:
    return len(
        _compact_bytes(
            {
                "messages": form_data.get("messages"),
                "response_format": form_data.get("response_format"),
            }
        )
    )


def _component_bytes(value: Any) -> int:
    return len(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    )


def request_token_anatomy(
    *,
    mode: str,
    prompt: Any,
    package: dict[str, Any],
    response_format: dict[str, Any],
    form_data: dict[str, Any],
    recorded_input_tokens: int,
) -> dict[str, Any]:
    marker = (
        "{{financial_semantic_matching_input_json}}"
        if mode == "v4"
        else "{{financial_evidence_successor_input_json}}"
    )
    if marker not in prompt.content:
        _fail("nano_semantic_audit_prompt_marker_missing")
    prompt_static = prompt.content.replace(marker, "")
    system_content = str(form_data["messages"][0]["content"])
    user_content = str(form_data["messages"][1]["content"])
    components = {
        "prompt_static_utf8_bytes": len(prompt_static.encode("utf-8")),
        "skill_content_transmitted_utf8_bytes": 0,
        "package_embedded_json_utf8_bytes": _component_bytes(package),
        "source_context_utf8_bytes": _component_bytes(
            package.get("source_groups", [])
        ),
        "structural_scope_utf8_bytes": _component_bytes(
            package.get("structural_scope", {})
        ),
        "semantic_pack_utf8_bytes": _component_bytes(
            package.get("semantic_pack", {})
        ),
        "managed_asset_identity_utf8_bytes": _component_bytes(
            package.get("managed_assets", {})
        ),
        "eligible_registry_guidance_utf8_bytes": _component_bytes(
            package.get("eligible_types", [])
        ),
        "user_message_utf8_bytes": len(user_content.encode("utf-8")),
        "response_schema_utf8_bytes": _component_bytes(response_format),
        "system_message_utf8_bytes": len(system_content.encode("utf-8")),
        "request_projection_utf8_bytes": _request_projection_bytes(form_data),
    }
    components["semantic_pack_share_of_system_message"] = round(
        (
            components["semantic_pack_utf8_bytes"]
            / components["system_message_utf8_bytes"]
        )
        if components["system_message_utf8_bytes"]
        else 0.0,
        6,
    )
    return {
        "measurement_method": (
            "exact UTF-8 bytes of the deterministic request projection; "
            "component bytes are not provider tokenizer counts"
        ),
        "repository_estimator_id": (
            "compact_request_utf8_bytes_div_4_plus_64_v1"
        ),
        "repository_estimated_input_tokens": (
            estimate_gate2_request_input_tokens(form_data)
        ),
        "provider_recorded_input_tokens": recorded_input_tokens,
        "provider_token_component_allocation_available": False,
        "components": components,
    }


def _binding_count(decision: dict[str, Any]) -> int:
    bindings = decision["decision"].get("value_bindings", [])
    if isinstance(bindings, dict):
        return sum(value is not None for value in bindings.values())
    return len(bindings)


def _reason_code(decision: dict[str, Any]) -> str:
    return str(decision["decision"]["reason_code"])


def _skill_snapshot(*, mode: str, service_root: Path) -> dict[str, Any]:
    if mode != "v4":
        return {
            "applicable": False,
            "content_transmitted": False,
            "content": None,
            "sha256": None,
        }
    path = (
        service_root
        / "managed_assets"
        / "skills"
        / "broker_reports_financial_domain_skill.v1.md"
    )
    content = path.read_text(encoding="utf-8")
    return {
        "applicable": True,
        "content_transmitted": False,
        "content": content,
        "sha256": _sha256_bytes(content.encode("utf-8")),
        "evidence": (
            "request form contains only Skill identity metadata; "
            "the Skill body is not embedded in either message"
        ),
    }


def _validate_receipt_identity(
    *,
    receipt: dict[str, Any],
    mode: str,
    prompt: Any,
    fixture: Any,
) -> None:
    contract = _mode_contract(mode)
    subject = receipt.get("qualification_subject", {})
    identity = receipt.get("qualification_identity", {})
    if (
        receipt.get("status") != "failed"
        or subject.get("exact_model_id") != EXACT_MODEL_ID
        or identity.get("exact_model_id") != EXACT_MODEL_ID
        or identity.get("provider_profile_id") != PROVIDER_PROFILE_ID
        or identity.get("fixture_manifest_canonical_hash")
        != fixture.manifest_canonical_hash
        or identity.get("successor_model_input_schema")
        != contract["model_input_schema"]
        or identity.get("successor_prompt_contract")
        != contract["prompt_contract"]
        or identity.get("prompt_version")
        != f"{contract['prompt_contract']}:{prompt.hash}"
        or receipt.get("qualification", {}).get(
            "raw_provider_output_included"
        )
        is not False
    ):
        _fail("nano_semantic_audit_receipt_identity_invalid")


def build_revision_snapshot(
    *,
    mode: str,
    receipt: dict[str, Any],
    receipt_sha256: str,
    service_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    contract = _mode_contract(mode)
    fixture = build_successor_qualification_fixture_v2()
    runner = _runner(fixture=fixture, mode=mode)
    _validate_receipt_identity(
        receipt=receipt,
        mode=mode,
        prompt=runner.prompt,
        fixture=fixture,
    )
    manifest = json.loads(
        DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8")
    )
    manifest_cases = {
        item["case_id"]: item for item in manifest["cases"]
    }
    projection_factory = (
        Gate2FinancialEvidenceSuccessorProviderProjectionFactory()
    )
    request_builder = Gate2OpenWebUIRequestBuilder(
        request_profile=contract["request_profile"]
    )
    private_cases: list[dict[str, Any]] = []
    safe_cases: list[dict[str, Any]] = []
    for case in fixture.cases:
        recorded = _case_receipt(
            receipt=receipt,
            case_id=case.case_id,
        )
        preflight = _preflight_case(
            receipt=receipt,
            case_id=case.case_id,
        )
        model_input = runner.model_input(
            scope=case.scope,
            source_context=case.source_context,
        )
        model_input_hash = sha256_json(model_input)
        projection = projection_factory.create(
            contract=case.scope.decision_contract
        )
        form_data = request_builder.build(
            prompt=runner.prompt,
            package=model_input,
            model_id=EXACT_MODEL_ID,
            response_format=projection.response_format,
        )
        budget = recorded.get("economy_budget_receipt", {})
        provider_execution = recorded.get("provider_execution", {})
        if (
            model_input_hash != recorded.get("model_input_hash")
            or case.source_context.integrity_hash
            != recorded.get("source_context_integrity_hash")
            or projection.response_format_hash
            != recorded.get("provider_response_format_hash")
            or estimate_gate2_request_input_tokens(form_data)
            != preflight.get("schema_dry_build", {}).get(
                "estimated_input_tokens"
            )
            or budget.get("input_tokens")
            != provider_execution.get("input_tokens")
        ):
            _fail(
                "nano_semantic_audit_case_identity_mismatch:"
                + case.case_id
            )
        recovered = recover_exact_decision(
            case=case,
            observed_disposition=recorded["observed_disposition"],
            observed_input_type_id=recorded.get(
                "observed_input_type_id"
            ),
            target_artifact_hash=recorded[
                "materialized_artifact_integrity_hash"
            ],
            execution_prefix=contract["execution_prefix"],
        )
        anatomy = request_token_anatomy(
            mode=mode,
            prompt=runner.prompt,
            package=model_input,
            response_format=projection.response_format,
            form_data=form_data,
            recorded_input_tokens=int(budget["input_tokens"]),
        )
        private_cases.append(
            {
                "case_id": case.case_id,
                "feature_families": list(case.features),
                "manifest_case": copy.deepcopy(
                    manifest_cases[case.case_id]
                ),
                "structural_scope": _jsonable(case.scope),
                "source_context": _jsonable(case.source_context),
                "model_input": copy.deepcopy(model_input),
                "provider_response_format": copy.deepcopy(
                    projection.response_format
                ),
                "provider_request_form": copy.deepcopy(form_data),
                "expected_model_output": copy.deepcopy(
                    case.expected_model_output
                ),
                "recorded_case_receipt": recorded,
                "recovered_validated_provider_decision": recovered,
                "raw_provider_response": {
                    "available": False,
                    "receipt_declares_included": False,
                    "semantic_decision_uniquely_recovered": True,
                    "unrecoverable_fields": [
                        "original response bytes",
                        "JSON field order and whitespace",
                        "transport response envelope",
                    ],
                },
                "token_anatomy": anatomy,
            }
        )
        safe_cases.append(
            {
                "case_id": case.case_id,
                "feature_families": list(case.features),
                "expected_disposition": case.expected_disposition,
                "expected_input_type_id": case.expected_input_type_id,
                "observed_disposition": recorded[
                    "observed_disposition"
                ],
                "observed_input_type_id": recorded.get(
                    "observed_input_type_id"
                ),
                "status": recorded["status"],
                "risk": copy.deepcopy(recorded.get("risk")),
                "source_groups_total": len(case.source_context.groups),
                "source_values_total": len(
                    case.scope.source_package.source_values
                ),
                "eligible_registry_types_total": len(
                    case.scope.decision_contract.eligible_type_ids
                ),
                "typed_branch_available": bool(
                    case.scope.decision_contract.eligible_type_ids
                ),
                "eligible_type_ids": list(
                    case.scope.decision_contract.eligible_type_ids
                ),
                "model_input_hash": model_input_hash,
                "source_context_integrity_hash": (
                    case.source_context.integrity_hash
                ),
                "provider_response_format_hash": (
                    projection.response_format_hash
                ),
                "materialized_artifact_integrity_hash": recorded[
                    "materialized_artifact_integrity_hash"
                ],
                "recovered_decision_sha256": recovered[
                    "decision_sha256"
                ],
                "recovered_reason_code": _reason_code(
                    recovered["decision"]
                ),
                "recovered_bindings_total": _binding_count(
                    recovered["decision"]
                ),
                "recovery_candidates_evaluated": recovered[
                    "candidates_evaluated"
                ],
                "recovery_matches_total": 1,
                "provider_recorded_input_tokens": int(
                    budget["input_tokens"]
                ),
                "provider_recorded_output_tokens": int(
                    budget["output_tokens"]
                ),
                "provider_duration_ms": int(
                    provider_execution["duration_ms"]
                ),
                "repository_estimated_input_tokens": anatomy[
                    "repository_estimated_input_tokens"
                ],
                "token_components": anatomy["components"],
                "raw_provider_response_available": False,
                "semantic_decision_uniquely_recovered": True,
            }
        )
    private = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "evidence_class": "private_synthetic_exact_revision_snapshot",
        "mode": mode,
        "repository_revision": contract["revision"],
        "receipt_sha256": receipt_sha256,
        "provider_calls_created_by_audit": 0,
        "customer_calls_created_by_audit": 0,
        "receipt": copy.deepcopy(receipt),
        "prompt": {
            "contract_id": contract["prompt_contract"],
            "content": runner.prompt.content,
            "hash": runner.prompt.hash,
            "prompt_ref": runner.prompt.prompt_ref,
        },
        "skill": _skill_snapshot(
            mode=mode,
            service_root=service_root,
        ),
        "cases": private_cases,
    }
    safe = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "evidence_class": "repository_safe_value_free_revision_snapshot",
        "status": "passed",
        "mode": mode,
        "repository_revision": contract["revision"],
        "receipt_sha256": receipt_sha256,
        "cases_total": len(safe_cases),
        "provider_calls_created_by_audit": 0,
        "customer_calls_created_by_audit": 0,
        "raw_provider_output_included": False,
        "source_literals_included": False,
        "source_value_refs_included": False,
        "prompt_contract_id": contract["prompt_contract"],
        "prompt_hash": runner.prompt.hash,
        "model_input_schema": contract["model_input_schema"],
        "request_profile": contract["request_profile"],
        "fixture_manifest_canonical_hash": (
            fixture.manifest_canonical_hash
        ),
        "skill_content_transmitted": False,
        "cases": safe_cases,
        "checks": {
            "all_case_inputs_hash_match": True,
            "all_source_context_hashes_match": True,
            "all_provider_schemas_hash_match": True,
            "all_preflight_token_estimates_match": True,
            "all_semantic_decisions_uniquely_recovered": True,
            "raw_provider_response_absence_explicit": True,
            "provider_calls_zero": True,
        },
    }
    _validate_safe_payload(safe=safe, private=private)
    return private, safe


def _validate_safe_payload(
    *,
    safe: dict[str, Any],
    private: dict[str, Any],
) -> None:
    safe_text = json.dumps(safe, ensure_ascii=False, sort_keys=True)
    if (
        '"source_value_ref"' in safe_text
        or safe.get("provider_calls_created_by_audit") != 0
        or not all(safe.get("checks", {}).values())
    ):
        _fail("nano_semantic_audit_safe_payload_invalid")
    for case in private["cases"]:
        for cell in case["manifest_case"].get("cells", []):
            literal = cell.get("literal")
            if (
                isinstance(literal, str)
                and literal
                and literal in safe_text
            ):
                _fail("nano_semantic_audit_literal_in_safe_payload")


def combine_revision_snapshots(
    *,
    v3_private: dict[str, Any],
    v3_safe: dict[str, Any],
    v4_private: dict[str, Any],
    v4_safe: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if (
        v3_safe.get("mode") != "v3"
        or v4_safe.get("mode") != "v4"
        or v3_safe.get("cases_total") != 12
        or v4_safe.get("cases_total") != 12
    ):
        _fail("nano_semantic_audit_snapshot_identity_invalid")
    by_v3 = {item["case_id"]: item for item in v3_safe["cases"]}
    by_v4 = {item["case_id"]: item for item in v4_safe["cases"]}
    if set(by_v3) != set(by_v4) or len(by_v3) != 12:
        _fail("nano_semantic_audit_case_set_mismatch")
    matrix: list[dict[str, Any]] = []
    changed = 0
    for case_id in by_v3:
        before = by_v3[case_id]
        after = by_v4[case_id]
        decision_changed = (
            before["observed_disposition"],
            before.get("observed_input_type_id"),
        ) != (
            after["observed_disposition"],
            after.get("observed_input_type_id"),
        )
        changed += int(decision_changed)
        matrix.append(
            {
                "case_id": case_id,
                "expected_disposition": after["expected_disposition"],
                "expected_input_type_id": after[
                    "expected_input_type_id"
                ],
                "v3_observed_disposition": before[
                    "observed_disposition"
                ],
                "v3_observed_input_type_id": before.get(
                    "observed_input_type_id"
                ),
                "v4_observed_disposition": after[
                    "observed_disposition"
                ],
                "v4_observed_input_type_id": after.get(
                    "observed_input_type_id"
                ),
                "decision_changed": decision_changed,
                "v3_eligible_registry_types_total": before[
                    "eligible_registry_types_total"
                ],
                "v4_eligible_registry_types_total": after[
                    "eligible_registry_types_total"
                ],
                "v3_provider_input_tokens": before[
                    "provider_recorded_input_tokens"
                ],
                "v4_provider_input_tokens": after[
                    "provider_recorded_input_tokens"
                ],
            }
        )
    private = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "evidence_class": "private_synthetic_cross_revision_annex",
        "provider_calls_created_by_audit": 0,
        "v3_snapshot": copy.deepcopy(v3_private),
        "v4_snapshot": copy.deepcopy(v4_private),
        "v3_v4_matrix": copy.deepcopy(matrix),
    }
    safe = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "evidence_class": "repository_safe_value_free_audit_receipt",
        "status": "evidence_reconstructed_with_raw_response_gap",
        "provider_calls_created_by_audit": 0,
        "customer_calls_created_by_audit": 0,
        "cases_total": 12,
        "case_level_completeness": {
            "exact_source_context": "private_annex_complete",
            "exact_model_input": "private_annex_complete",
            "exact_provider_request_form": "private_annex_complete",
            "exact_expected_decision": "private_annex_complete",
            "exact_semantic_provider_decision": (
                "uniquely_recovered_for_12_of_12"
            ),
            "raw_provider_response_bytes": "unavailable_0_of_12",
            "validator_materializer_hash_path": (
                "complete_for_12_of_12"
            ),
        },
        "v3_revision": V3_REVISION,
        "v4_revision": V4_REVISION,
        "v4_terminal_review_revision": V4_TERMINAL_REVIEW_REVISION,
        "v3_receipt_sha256": V3_RECEIPT_SHA256,
        "v4_receipt_sha256": V4_RECEIPT_SHA256,
        "decision_changes_total": changed,
        "v3_v4_matrix": matrix,
        "privacy": {
            "raw_provider_output_included": False,
            "source_literals_included": False,
            "source_value_refs_included": False,
            "customer_data_included": False,
            "private_paths_included": False,
        },
        "checks": {
            "twelve_case_sets_equal": True,
            "all_semantic_decisions_uniquely_recovered": True,
            "raw_response_gap_explicit": True,
            "provider_calls_zero": True,
            "runtime_product_changes_zero": True,
        },
    }
    return private, safe


def write_bundle(
    *,
    private: dict[str, Any],
    safe: dict[str, Any],
    private_path: Path,
    safe_path: Path,
) -> dict[str, Any]:
    private_bytes = _json_bytes(private)
    written_safe = copy.deepcopy(safe)
    written_safe["private_annex_sha256"] = _sha256_bytes(private_bytes)
    private_path.parent.mkdir(parents=True, exist_ok=True)
    safe_path.parent.mkdir(parents=True, exist_ok=True)
    private_tmp = private_path.with_name(private_path.name + ".tmp")
    safe_tmp = safe_path.with_name(safe_path.name + ".tmp")
    private_tmp.write_bytes(private_bytes)
    safe_tmp.write_bytes(_json_bytes(written_safe))
    private_tmp.replace(private_path)
    safe_tmp.replace(safe_path)
    return written_safe


def _snapshot_command(args: argparse.Namespace) -> int:
    contract = _mode_contract(args.mode)
    revision = _git_revision()
    if revision != contract["revision"]:
        _fail("nano_semantic_audit_repository_revision_mismatch")
    receipt, receipt_sha256 = load_pinned_json(
        path=args.receipt,
        expected_sha256=contract["receipt_sha256"],
    )
    private, safe = build_revision_snapshot(
        mode=args.mode,
        receipt=receipt,
        receipt_sha256=receipt_sha256,
        service_root=Path.cwd().resolve(),
    )
    written = write_bundle(
        private=private,
        safe=safe,
        private_path=args.private_output,
        safe_path=args.safe_output,
    )
    print(
        json.dumps(
            {
                "status": written["status"],
                "mode": args.mode,
                "cases_total": written["cases_total"],
                "provider_calls_created_by_audit": 0,
                "private_annex_sha256": written[
                    "private_annex_sha256"
                ],
                "safe_output": str(args.safe_output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _combine_command(args: argparse.Namespace) -> int:
    v3_private = json.loads(
        args.v3_private.read_text(encoding="utf-8")
    )
    v3_safe = json.loads(args.v3_safe.read_text(encoding="utf-8"))
    v4_private = json.loads(
        args.v4_private.read_text(encoding="utf-8")
    )
    v4_safe = json.loads(args.v4_safe.read_text(encoding="utf-8"))
    private, safe = combine_revision_snapshots(
        v3_private=v3_private,
        v3_safe=v3_safe,
        v4_private=v4_private,
        v4_safe=v4_safe,
    )
    written = write_bundle(
        private=private,
        safe=safe,
        private_path=args.private_output,
        safe_path=args.safe_output,
    )
    print(
        json.dumps(
            {
                "status": written["status"],
                "cases_total": written["cases_total"],
                "decision_changes_total": written[
                    "decision_changes_total"
                ],
                "provider_calls_created_by_audit": 0,
                "private_annex_sha256": written[
                    "private_annex_sha256"
                ],
                "safe_output": str(args.safe_output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    snapshot = subparsers.add_parser("snapshot")
    snapshot.add_argument("--mode", choices=("v3", "v4"), required=True)
    snapshot.add_argument("--receipt", type=Path, required=True)
    snapshot.add_argument("--private-output", type=Path, required=True)
    snapshot.add_argument("--safe-output", type=Path, required=True)
    snapshot.set_defaults(handler=_snapshot_command)
    combine = subparsers.add_parser("combine")
    combine.add_argument("--v3-private", type=Path, required=True)
    combine.add_argument("--v3-safe", type=Path, required=True)
    combine.add_argument("--v4-private", type=Path, required=True)
    combine.add_argument("--v4-safe", type=Path, required=True)
    combine.add_argument("--private-output", type=Path, required=True)
    combine.add_argument("--safe-output", type=Path, required=True)
    combine.set_defaults(handler=_combine_command)
    args = parser.parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
