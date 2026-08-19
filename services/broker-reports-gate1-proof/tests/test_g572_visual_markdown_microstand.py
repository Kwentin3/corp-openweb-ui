from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SERVICE_ROOT / "scripts" / "live_g572_visual_markdown_microstand.py"
SPEC = importlib.util.spec_from_file_location("live_g572_visual_markdown_microstand", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
G572 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(G572)


def test_transcription_view_is_semantically_blind() -> None:
    visible = json.dumps(G572.transcription_model_view(), ensure_ascii=False).lower()
    forbidden = {
        "metadata",
        "account_identifier",
        "party_name",
        "statement_period",
        "broker_legal_name",
        "contract_identifier",
    }

    assert not any(token in visible for token in forbidden)
    assert "markdown" in visible
    assert set(G572.transcription_response_schema()["properties"]) == {
        "schema_version",
        "markdown",
    }


def test_semantic_request_is_identical_before_model_binding() -> None:
    request = G572.semantic_model_visible_request("| Label | Value |\n|---|---|\n| A | B |")

    assert [item["role"] for item in request["messages"]] == [
        "system",
        "user",
        "user",
    ]
    assert "model" not in request
    assert request["response_format"]["json_schema"]["schema"] == (
        G572.metadata_proposal_response_schema()
    )


def test_human_audit_is_terminal_and_never_repairs_markdown() -> None:
    result = _transcription_result()
    digest = _sha256_json_bytes(result)
    audit = _clean_audit(result, digest)

    qualified = G572.validate_human_audit(
        transcription_result=result,
        transcription_result_sha256=digest,
        audit=audit,
    )

    assert [item["markdown"] for item in qualified] == [
        run["raw_output"]["markdown"] for run in result["runs"]
    ]


def test_human_audit_blocks_text_loss_before_classification() -> None:
    result = _transcription_result()
    digest = _sha256_json_bytes(result)
    audit = _clean_audit(result, digest)
    audit["cases"][0]["lost_source_text"] = 1
    audit["cases"][0]["qualified"] = False

    with pytest.raises(G572.G572Error, match="visual_markdown_intermediate_not_reliable"):
        G572.validate_human_audit(
            transcription_result=result,
            transcription_result_sha256=digest,
            audit=audit,
        )


def test_human_audit_rejects_markdown_hash_substitution() -> None:
    result = _transcription_result()
    digest = _sha256_json_bytes(result)
    audit = _clean_audit(result, digest)
    audit["cases"][1]["markdown_sha256"] = "0" * 64

    with pytest.raises(G572.G572Error, match="human_audit_case_invalid"):
        G572.validate_human_audit(
            transcription_result=result,
            transcription_result_sha256=digest,
            audit=audit,
        )


def test_repeatability_requires_clean_initial_arm(tmp_path: Path) -> None:
    prior = {
        "schema_version": G572.CLASSIFICATION_RESULT_PRIVATE_VERSION,
        "runs": [
            {"arm": arm, "case_id": case_id, "semantic_exact": arm == "strong"}
            for arm in ("gemini", "strong")
            for case_id in G572.DEVELOPMENT_CASE_IDS
        ],
    }
    path = tmp_path / "prior.json"
    path.write_text(json.dumps(prior), encoding="utf-8")

    runs = G572._repeatability_runs(
        prior_result_path=path,
        candidate_arms=["strong"],
        arms=[copy.deepcopy(G572.GEMINI_ARM), copy.deepcopy(G572.STRONG_ARM)],
    )

    assert len(runs) == 6
    assert {item["case_id"] for item in runs} == {"case_b", "case_f"}
    with pytest.raises(G572.G572Error, match="candidate_not_clean"):
        G572._repeatability_runs(
            prior_result_path=path,
            candidate_arms=["gemini"],
            arms=[copy.deepcopy(G572.GEMINI_ARM), copy.deepcopy(G572.STRONG_ARM)],
        )


def test_factory_anchors_forbid_direct_transport() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "PdfGridExperimentProviderFactory(" in source
    assert "Gate2StructuredModelClientFactory(" in source
    assert "PdfDualVlmFactProviderFactory(" in source
    assert "FACTORY_REQUIRED" in source
    assert "FORBIDDEN" in source
    assert "urllib.request" not in source
    assert "httpx." not in source


def test_strong_transport_replay_requires_pre_output_failures(tmp_path: Path) -> None:
    prior = {
        "schema_version": G572.CLASSIFICATION_RESULT_PRIVATE_VERSION,
        "runs": [
            {
                "arm": "strong",
                "case_id": case_id,
                "transport_failure": 1,
                "raw_output": None,
            }
            for case_id in G572.DEVELOPMENT_CASE_IDS
        ],
    }
    path = tmp_path / "prior.json"
    path.write_text(json.dumps(prior), encoding="utf-8")

    runs = G572._strong_transport_replay_runs(
        prior_result_path=path,
        candidate_arms=[],
    )

    assert len(runs) == 3
    assert {item["arm"] for item in runs} == {"strong"}


def test_safe_transcription_reads_nested_provider_usage() -> None:
    safe = G572._safe_transcription_run(
        {
            "case_id": "case_b",
            "crop_sha256": "a" * 64,
            "raw_output": {"markdown": "faithful"},
            "attempt": {"usage": {"total_tokens": 123}, "duration_ms": 7},
            "transport_failure": 0,
            "contract_errors": [],
        }
    )

    assert safe["total_tokens"] == 123
    assert safe["duration_ms"] == 7


def _transcription_result() -> dict:
    cases = []
    runs = []
    for case_id in G572.DEVELOPMENT_CASE_IDS:
        markdown = f"| label | value |\n|---|---|\n| {case_id} | visible |"
        cases.append(
            {
                "case_id": case_id,
                "role": "control",
                "crop_sha256": hashlib.sha256(case_id.encode()).hexdigest(),
                "human_transcription": f"{case_id} visible",
                "truth": [],
                "non_contract_observations": [],
            }
        )
        runs.append(
            {
                "case_id": case_id,
                "raw_output": {
                    "schema_version": G572.TRANSCRIPTION_SCHEMA_VERSION,
                    "markdown": markdown,
                },
            }
        )
    return {
        "schema_version": G572.TRANSCRIPTION_RESULT_PRIVATE_VERSION,
        "technically_valid": True,
        "cases": cases,
        "runs": runs,
    }


def _clean_audit(result: dict, digest: str) -> dict:
    return {
        "schema_version": G572.HUMAN_AUDIT_SCHEMA_VERSION,
        "transcription_result_sha256": digest,
        "auditor": "HUMAN_VISUAL_COMPARISON",
        "cases": [
            {
                "case_id": run["case_id"],
                "markdown_sha256": hashlib.sha256(
                    run["raw_output"]["markdown"].encode("utf-8")
                ).hexdigest(),
                "lost_source_text": 0,
                "invented_text": 0,
                "semantic_rewrites": 0,
                "broken_label_value_relations": 0,
                "broken_row_column_relations": 0,
                "changed_value_boundaries": 0,
                "qualified": True,
                "classification": "FAITHFUL_VISUAL_MARKDOWN",
                "notes": "visual comparison completed",
            }
            for run in result["runs"]
        ],
    }


def _sha256_json_bytes(value: dict) -> str:
    raw = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
