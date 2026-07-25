from __future__ import annotations

import copy

import pytest

from scripts.gate2_successor_ambiguity_audit import (
    ATTEMPT_V1_RECEIPT_SHA256,
    ATTEMPT_V2_RECEIPT_SHA256,
    DISPUTED_CASE_IDS,
    FACTORY_REQUIRED,
    FORBIDDEN,
    PROMPT_V1_CONTRACT_ID,
    PROMPT_V1_CONTENT,
    PROMPT_V1_HASH,
    Gate2SuccessorAmbiguityAuditError,
    build_failure_evidence,
    prompt_hash,
    recover_exact_decision,
    write_evidence_bundle,
)
from scripts.live_gate2_financial_successor_qualification import (
    build_successor_qualification_fixture,
    successor_qualification_contract_identity,
)


_CASE_EVIDENCE = {
    "attempt_v1": {
        "syn_successor_multiple_hypotheses": {
            "status": "passed",
            "observed_disposition": "unclassified_financial_input",
            "observed_input_type_id": None,
            "model_input_hash": (
                "fe2dda6aca91f87780f0001020891e72de5b2da63db62a1d3086b89ef469f62d"
            ),
            "materialized_artifact_integrity_hash": (
                "1b5cf2cc56ded64106cb112797b6cce3b4ab7278a06b8d4805b1bd7b8d381863"
            ),
        },
        "syn_successor_explicit_unclassified": {
            "status": "passed",
            "observed_disposition": "unclassified_financial_input",
            "observed_input_type_id": None,
            "model_input_hash": (
                "97f141020fc2a8099037ecb235cb5997d3209233dccba676061fde90075b9262"
            ),
            "materialized_artifact_integrity_hash": (
                "4d0a133af8548eda06a4792375ea9e06e65441a10901e01eece0e260ba6d0796"
            ),
        },
    },
    "attempt_v2": {
        "syn_successor_multiple_hypotheses": {
            "status": "failed",
            "observed_disposition": "typed_input",
            "observed_input_type_id": "cash_balance_snapshot_v1",
            "model_input_hash": (
                "fe2dda6aca91f87780f0001020891e72de5b2da63db62a1d3086b89ef469f62d"
            ),
            "materialized_artifact_integrity_hash": (
                "07cead48679298790533b42db676b1c84d261106596cc39372a380889bdbec92"
            ),
        },
        "syn_successor_explicit_unclassified": {
            "status": "failed",
            "observed_disposition": "typed_input",
            "observed_input_type_id": "cash_balance_snapshot_v1",
            "model_input_hash": (
                "97f141020fc2a8099037ecb235cb5997d3209233dccba676061fde90075b9262"
            ),
            "materialized_artifact_integrity_hash": (
                "7fb2759b7071d622dcb9003549456dd3bf50c8dffded178f88c0484a653b91e5"
            ),
        },
    },
}


def _receipt(*, attempt_id: str) -> dict:
    fixture = build_successor_qualification_fixture()
    identity = successor_qualification_contract_identity(
        fixture=fixture
    ).to_dict()
    if attempt_id == "attempt_v1":
        identity["prompt_version"] = (
            PROMPT_V1_CONTRACT_ID + ":" + PROMPT_V1_HASH
        )
        identity["successor_prompt_contract"] = (
            PROMPT_V1_CONTRACT_ID
        )
    cases = []
    for case_id in DISPUTED_CASE_IDS:
        case = next(
            item for item in fixture.cases if item.case_id == case_id
        )
        evidence = _CASE_EVIDENCE[attempt_id][case_id]
        cases.append(
            {
                "case_id": case_id,
                "status": evidence["status"],
                "expected_disposition": case.expected_disposition,
                "expected_input_type_id": case.expected_input_type_id,
                "observed_disposition": evidence[
                    "observed_disposition"
                ],
                "observed_input_type_id": evidence[
                    "observed_input_type_id"
                ],
                "model_input_hash": evidence["model_input_hash"],
                "materialized_artifact_integrity_hash": evidence[
                    "materialized_artifact_integrity_hash"
                ],
                "provider_generated_output": True,
                "canonical_validation_ran": True,
                "raw_provider_output_included": False,
            }
        )
    return {
        "status": "failed",
        "qualification_subject": {
            "exact_model_id": "gpt-5.4-nano-2026-03-17",
            "provider_profile_id": "openai_gpt",
        },
        "qualification_identity": identity,
        "qualification": {
            "raw_provider_output_included": False,
            "cases": cases,
        },
    }


def test_prompt_v1_snapshot_is_exact():
    assert (
        prompt_hash(
            content=PROMPT_V1_CONTENT,
            contract_id=PROMPT_V1_CONTRACT_ID,
        )
        == PROMPT_V1_HASH
    )


def test_live_artifact_hashes_uniquely_recover_both_attempt_decisions():
    fixture = build_successor_qualification_fixture()
    cases = {item.case_id: item for item in fixture.cases}

    for attempt_id, by_case in _CASE_EVIDENCE.items():
        for case_id, evidence in by_case.items():
            recovered = recover_exact_decision(
                case=cases[case_id],
                observed_disposition=evidence[
                    "observed_disposition"
                ],
                observed_input_type_id=evidence[
                    "observed_input_type_id"
                ],
                target_artifact_hash=evidence[
                    "materialized_artifact_integrity_hash"
                ],
            )
            assert recovered["matching_candidates"] == 1
            assert (
                recovered["decision"]["decision"]["disposition"]
                == evidence["observed_disposition"]
            )


def test_failure_evidence_freeze_is_value_free_and_records_attempt_diff():
    private, safe = build_failure_evidence(
        attempt_v1=_receipt(attempt_id="attempt_v1"),
        attempt_v1_sha256=ATTEMPT_V1_RECEIPT_SHA256,
        attempt_v2=_receipt(attempt_id="attempt_v2"),
        attempt_v2_sha256=ATTEMPT_V2_RECEIPT_SHA256,
    )

    assert safe["status"] == "passed"
    assert safe["provider_calls_created_by_audit"] == 0
    assert safe["checks"]["two_cases_exactly_recovered"] is True
    assert len(private["cases"]) == len(safe["cases"]) == 2
    for case in safe["cases"]:
        assert [item["observed_disposition"] for item in case["attempts"]] == [
            "unclassified_financial_input",
            "typed_input",
        ]
        assert all(
            item["matching_candidates"] == 1
            for item in case["attempts"]
        )


def test_tampered_materialized_hash_fails_closed():
    fixture = build_successor_qualification_fixture()
    case = next(
        item
        for item in fixture.cases
        if item.case_id == "syn_successor_multiple_hypotheses"
    )

    with pytest.raises(
        Gate2SuccessorAmbiguityAuditError,
        match="decision_recovery_not_unique",
    ):
        recover_exact_decision(
            case=case,
            observed_disposition="typed_input",
            observed_input_type_id="cash_balance_snapshot_v1",
            target_artifact_hash="0" * 64,
        )


def test_non_prompt_identity_difference_fails_closed():
    attempt_v2 = copy.deepcopy(_receipt(attempt_id="attempt_v2"))
    attempt_v2["qualification_identity"]["registry_hash"] = "0" * 64

    with pytest.raises(
        Gate2SuccessorAmbiguityAuditError,
        match="mixed_qualification_identity",
    ):
        build_failure_evidence(
            attempt_v1=_receipt(attempt_id="attempt_v1"),
            attempt_v1_sha256=ATTEMPT_V1_RECEIPT_SHA256,
            attempt_v2=attempt_v2,
            attempt_v2_sha256=ATTEMPT_V2_RECEIPT_SHA256,
        )


def test_written_safe_receipt_has_private_hash_but_no_private_content(
    tmp_path,
):
    private, safe = build_failure_evidence(
        attempt_v1=_receipt(attempt_id="attempt_v1"),
        attempt_v1_sha256=ATTEMPT_V1_RECEIPT_SHA256,
        attempt_v2=_receipt(attempt_id="attempt_v2"),
        attempt_v2_sha256=ATTEMPT_V2_RECEIPT_SHA256,
    )
    private_path = tmp_path / "evidence.private.json"
    safe_path = tmp_path / "evidence.receipt.safe.json"

    written = write_evidence_bundle(
        private=private,
        safe=safe,
        private_path=private_path,
        safe_path=safe_path,
    )

    assert private_path.exists()
    assert safe_path.exists()
    assert len(written["private_evidence_sha256"]) == 64
    safe_text = safe_path.read_text(encoding="utf-8")
    for case in private["cases"]:
        for cell in case["manifest_case"]["cells"]:
            assert cell["literal"] not in safe_text
    assert '"source_value_ref"' not in safe_text


def test_anti_drift_contract_forbids_provider_and_factory_bypass():
    assert "Gate2FinancialEvidenceSuccessorRunnerFactory.create" in (
        FACTORY_REQUIRED
    )
    assert "must not call a provider" in FORBIDDEN
    assert "bypass canonical validation/materialization" in FORBIDDEN
