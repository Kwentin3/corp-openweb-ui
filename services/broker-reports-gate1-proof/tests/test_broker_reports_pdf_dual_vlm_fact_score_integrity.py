from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = SERVICE_ROOT / "scripts"
MANIFEST_PATH = SERVICE_ROOT / "benchmarks" / "pdf_dual_vlm_fact_v1" / "manifest.json"
sys.path.insert(0, str(SCRIPT_DIR))

import local_pdf_dual_vlm_fact_benchmark_score as SCORE  # noqa: E402
import pdf_dual_vlm_fact_contracts as CONTRACTS  # noqa: E402
import pdf_dual_vlm_fact_evidence as EVIDENCE  # noqa: E402


def test_detection_denominator_includes_reference_case_missing_from_terminal() -> None:
    bbox = [0.1, 0.1, 0.5, 0.5]
    terminal = {
        "cases": [
            {
                "case_id": "case_a",
                "detection": {
                    "status": "completed",
                    "contract_errors": [],
                    "output": {
                        "candidates": [
                            {
                                "candidate_id": "candidate_a",
                                "state": "present",
                                "bbox": bbox,
                            }
                        ]
                    },
                },
                "crops": [
                    {
                        "candidate": {"candidate_id": "candidate_a"},
                        "crop_reproducibility": {"byte_identical": True},
                        "same_crop_sha256_for_both_extractors": True,
                    }
                ],
            }
        ]
    }
    reference = {
        "cases": [
            {"case_id": "case_a", "regions": [_region("region_a", bbox)]},
            {"case_id": "case_b", "regions": [_region("region_b", bbox)]},
        ]
    }
    manifest = {"scoring_policy": {"detection_iou_threshold": 0.5}}

    result = SCORE._score_detection(terminal, reference, manifest)

    assert result["reference_tables"] == 2
    assert result["found_reference_tables"] == 1
    assert result["recall"] == 0.5
    assert result["missed_regions"] == [
        {"case_id": "case_b", "reference_region_id": "region_b"}
    ]


def test_frozen_manifest_rejects_threshold_or_model_drift() -> None:
    manifest = _manifest()
    SCORE._validate_frozen_manifest(manifest)

    threshold_drift = copy.deepcopy(manifest)
    threshold_drift["scoring_policy"]["accepted_fact_recall_minimum"] = 0.1
    with pytest.raises(SCORE.ScoreError) as threshold_error:
        SCORE._validate_frozen_manifest(threshold_drift)
    assert (
        threshold_error.value.code
        == "dual_vlm_terminal_manifest_scoring_policy_invalid"
    )

    model_drift = copy.deepcopy(manifest)
    model_drift["provider_contracts"]["openai_extraction"]["model_id"] = "gpt-drift"
    with pytest.raises(SCORE.ScoreError) as model_error:
        SCORE._validate_frozen_manifest(model_drift)
    assert model_error.value.code == "dual_vlm_terminal_manifest_provider_invalid"


def test_human_reference_rejects_duplicate_case_ids_and_ai_reviewer() -> None:
    manifest = _manifest()
    manifest_sha = CONTRACTS.sha256_json(manifest)
    reference = _reference_shell(manifest_sha, reviewer_identity="Roman")
    reference["cases"] = [
        {
            "case_id": "betterment_p02",
            "document_id": "betterment_p02",
            "pdf_sha256": "0" * 64,
            "page_number": 2,
            "page_sha256": "1" * 64,
            "expected_kind": "negative",
            "regions": [],
            "negative_review": None,
        }
        for _ in SCORE.FROZEN_CASE_IDS
    ]
    seal = _reference_seal(reference, manifest_sha)
    with pytest.raises(SCORE.ScoreError) as duplicate:
        SCORE._validate_human_reference(
            reference,
            seal,
            reference_sha="2" * 64,
            reference_size=123,
            manifest_sha=manifest_sha,
            manifest=manifest,
        )
    assert duplicate.value.code == "dual_vlm_human_reference_cases_invalid"

    ai_reference = _reference_shell(manifest_sha, reviewer_identity="Codex reviewer")
    ai_seal = _reference_seal(ai_reference, manifest_sha)
    with pytest.raises(SCORE.ScoreError) as ai_reviewer:
        SCORE._validate_human_reference(
            ai_reference,
            ai_seal,
            reference_sha="2" * 64,
            reference_size=123,
            manifest_sha=manifest_sha,
            manifest=manifest,
        )
    assert ai_reviewer.value.code == "dual_vlm_human_reviewer_invalid"


def test_reference_fact_accepts_explicitly_confirmed_header_absence() -> None:
    crop_sha = "a" * 64
    fact = _complete_reference_fact(crop_sha=crop_sha)
    fact["header_path"] = []
    fact["source_regions"]["header"] = []
    fact["uncertainty"] = ["header_not_present_in_source"]

    SCORE._validate_reference_fact(fact, crop_sha=crop_sha)


def test_reference_fact_rejects_unclassified_empty_header_path() -> None:
    crop_sha = "a" * 64
    fact = _complete_reference_fact(crop_sha=crop_sha)
    fact["header_path"] = []
    fact["source_regions"]["header"] = []

    with pytest.raises(SCORE.ScoreError) as error:
        SCORE._validate_reference_fact(fact, crop_sha=crop_sha)

    assert error.value.code == "dual_vlm_human_reference_fact_source_incomplete"


def test_headerless_reference_support_does_not_enable_runtime_evidence() -> None:
    runtime_fact = {
        "observed": {
            "row_label_exact": "Cash",
            "header_path_exact": [],
            "source_regions": {
                "row_label_bbox": [0.1, 0.2, 0.3, 0.3],
                "value_bbox": [0.7, 0.2, 0.9, 0.3],
                "header_bboxes": [],
            },
        },
        "interpreted": {"period": "2025"},
        "evidence_request": {"requested_text": {"period_exact": "2025"}},
    }

    assert CONTRACTS._fact_evidence_prerequisites(runtime_fact) is False
    assert CONTRACTS._source_regions_compatible(runtime_fact, runtime_fact) is False


def test_crop_validation_replays_consensus_and_checks_provider_identity() -> None:
    manifest_case, case_input, candidate, crop = _valid_crop_fixture()
    SCORE._validate_terminal_crop(crop, candidate, manifest_case, case_input)

    forged_consensus = copy.deepcopy(crop)
    forged_consensus["consensus"]["summary"]["both_models_unknown"] = 0
    _rechecksum(forged_consensus["consensus"], "consensus_checksum")
    with pytest.raises(SCORE.ScoreError) as consensus_error:
        SCORE._validate_terminal_crop(
            forged_consensus, candidate, manifest_case, case_input
        )
    assert consensus_error.value.code == "dual_vlm_terminal_consensus_replay_mismatch"

    replayed_provider = copy.deepcopy(crop)
    replayed_provider["openai"]["operation"]["attempt"]["provider"] = "google"
    with pytest.raises(SCORE.ScoreError) as provider_error:
        SCORE._validate_terminal_crop(
            replayed_provider, candidate, manifest_case, case_input
        )
    assert provider_error.value.code == "dual_vlm_terminal_provider_operation_invalid"


def test_unmatched_and_raster_auto_acceptances_fail_safety_gate() -> None:
    correct_entry = _consensus_entry("consensus_correct", "cash", "1")
    invented_entry = _consensus_entry("consensus_invented", "invented", "999")
    terminal = {
        "cases": [
            {
                "case_id": "matched",
                "crops": [_scoring_crop(correct_entry, "text_layer")],
            },
            {
                "case_id": "false_positive",
                "crops": [_scoring_crop(invented_entry, "raster")],
            },
        ]
    }
    reference = {
        "cases": [
            {
                "case_id": "matched",
                "regions": [
                    {
                        "region_id": "reference_region",
                        "evidence_medium": "text_layer",
                        "facts": [
                            {
                                "accepted_for_scoring": True,
                                "fact": _reference_fact("cash", "1"),
                            }
                        ],
                    }
                ],
            },
            {"case_id": "false_positive", "regions": []},
        ]
    }
    detection = {
        "matches": [
            {
                "case_id": "matched",
                "crop_index": 0,
                "reference_region_id": "reference_region",
                "reference_evidence_medium": "text_layer",
            }
        ]
    }

    facts = SCORE._score_facts(terminal, reference, detection)

    accepted = facts["consensus_plus_evidence"]
    assert accepted["accepted_facts"] == 2
    assert accepted["false_accepted_facts"] == 1
    assert accepted["unsupported_auto_acceptances"] == 1
    assert facts["raster_separate"]["automatic_acceptance_eligible"] == 1
    assert SCORE._evidence_gate(facts, _manifest()) is False


def test_best_single_comparison_does_not_hide_openai_perfection() -> None:
    facts = {
        "gemini_alone": _provider_score(precision=0.5, recall=1.0, false_positive=1),
        "openai_alone": _provider_score(precision=1.0, recall=1.0, false_positive=0),
        "canonical_consensus": {"predicted_facts": 1},
        "consensus_plus_evidence": {
            "precision": 1.0,
            "recall": 1.0,
            "false_positive_facts": 0,
        },
    }

    assert (
        SCORE._best_single_provider(facts["gemini_alone"], facts["openai_alone"])[
            "provider"
        ]
        == "openai"
    )
    assert SCORE._material_improvement(facts, _manifest()) is False


def test_operational_metrics_use_attempted_call_accounting_and_models() -> None:
    manifest = _manifest()
    operation = {
        "kind": "table_region_detection",
        "image_bytes": 100,
        "model_view_bytes": 20,
        "schema_bytes": 30,
        "count_tokens": None,
        "attempt": None,
        "failure_code": "count_failed",
        "call_accounting": {
            "count_or_preflight_calls_attempted": 1,
            "count_or_preflight_calls_completed": 0,
            "generate_calls_attempted": 0,
            "generate_calls_completed": 0,
        },
    }
    terminal = {
        "cases": [
            {
                "detection": {"status": "contract_invalid", "operation": operation},
                "crops": [],
            }
        ],
        "parser_accounting": {},
    }

    result = SCORE._operational_metrics(terminal, manifest)["detection"]

    assert result["provider"] == "google"
    assert result["model_requested"] == "models/gemini-3.5-flash"
    assert result["count_or_preflight_calls"] == 1
    assert result["count_or_preflight_calls_completed"] == 0
    assert result["generate_calls"] == 0
    assert result["transport_failures"] == 1
    assert result["execution_contract_passed"] is False


def test_currency_code_reference_allows_explicit_visible_literal() -> None:
    reference = {
        "case_id": "case",
        "crop_index": 0,
        "canonical": SCORE._canonical_reference_fact(
            {**_reference_fact("cash", "1"), "currency": "USD"}
        ),
    }
    prediction = {
        "case_id": "case",
        "crop_index": 0,
        "canonical": {
            **reference["canonical"],
            "currency_literal": "$",
            "currency_code": "USD",
        },
    }

    result = SCORE._fact_metrics([reference], [prediction])

    assert result["true_positive_facts"] == 1
    assert result["precision"] == 1.0


def test_score_run_rechecks_both_reference_files() -> None:
    source = Path(SCORE.__file__).read_text(encoding="utf-8")
    assert source.count("reference_path.read_bytes()") >= 2
    assert source.count("reference_seal_path.read_bytes()") >= 2


def test_missing_reference_is_blocked_only_after_full_terminal_validation(
    tmp_path: Path,
) -> None:
    manifest = _manifest()
    terminal = _valid_failed_terminal(manifest)
    terminal_path, seal_path = _write_terminal(tmp_path, terminal)
    missing_reference = tmp_path / "missing-reference.json"
    missing_reference_seal = tmp_path / "missing-reference-seal.json"

    blocked = SCORE.score_run(
        terminal_path=terminal_path,
        seal_path=seal_path,
        reference_path=missing_reference,
        reference_seal_path=missing_reference_seal,
    )

    assert blocked["scoring_status"] == "blocked_human_reference_required"
    assert blocked["terminal_contract_verified_before_reference_access"] is True

    invalid = copy.deepcopy(terminal)
    invalid["cases"] = invalid["cases"][:-1]
    invalid["execution_call_accounting"] = {
        "provider_operations": 0,
        "count_or_preflight_calls_attempted": 0,
        "count_or_preflight_calls_completed": 0,
        "generate_calls_attempted": 0,
        "generate_calls_completed": 0,
    }
    invalid_path, invalid_seal_path = _write_terminal(tmp_path / "invalid", invalid)
    with pytest.raises(SCORE.ScoreError) as invalid_terminal:
        SCORE.score_run(
            terminal_path=invalid_path,
            seal_path=invalid_seal_path,
            reference_path=missing_reference,
            reference_seal_path=missing_reference_seal,
        )
    assert invalid_terminal.value.code == "dual_vlm_terminal_cases_invalid"


def _manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _valid_failed_terminal(manifest: dict[str, Any]) -> dict[str, Any]:
    qualification: dict[str, Any] = {}
    for role, profile, model in (
        ("detector", "google_gemini", "models/gemini-3.5-flash"),
        ("gemini", "google_gemini", "models/gemini-3.5-flash"),
        ("openai", "openai_gpt", "gpt-5.4-mini-2026-03-17"),
    ):
        qualification[role] = {
            "status": "qualified",
            "provider_profile": profile,
            "requested_model_id": model,
            "resolved_model_id": model,
            "exact_model_match": True,
            "image_input_supported": True,
            "structured_output_supported": True,
            "native_provider_transport": True,
            "credentials_from_openwebui_connection": True,
            "hidden_retry": False,
            "provider_failover": False,
        }
    cases = []
    failures = []
    for case in manifest["cases"]:
        code = "synthetic_terminal_case_failure"
        cases.append(
            {
                "case_id": case["case_id"],
                "broker": case["broker"],
                "categories": case["category_tags"],
                "input": None,
                "detection": {
                    "status": "failed",
                    "output": None,
                    "contract_errors": [code],
                    "operation": None,
                },
                "crops": [],
                "terminal_status": "failed",
                "failure_code": code,
            }
        )
        failures.append({"case_id": case["case_id"], "code": code})
    return {
        "schema_version": SCORE.TERMINAL_SCHEMA_VERSION,
        "runner": {"reference_argument_supported": False},
        "reference_accessed": False,
        "human_reference_available_to_runner": False,
        "production_authority": False,
        "production_pipeline_changed": False,
        "production_gate1_changed": False,
        "production_gate2_changed": False,
        "openwebui_core_changed": False,
        "knowledge_or_rag_used": False,
        "ocr_performed": False,
        "hidden_retry": False,
        "provider_failover": False,
        "third_llm_arbiter_used": False,
        "manifest_sha256": CONTRACTS.sha256_json(manifest),
        "target_manifest": manifest,
        "source_revision": {
            "repository_commit_sha": "a" * 40,
            "worktree_clean": True,
            "branch": "test",
        },
        "provider_qualification": qualification,
        "cases": cases,
        "failures": failures,
        "run_status": "completed_with_failures",
        "execution_call_accounting": {
            "provider_operations": 0,
            "count_or_preflight_calls_attempted": 0,
            "count_or_preflight_calls_completed": 0,
            "generate_calls_attempted": 0,
            "generate_calls_completed": 0,
        },
    }


def _write_terminal(directory: Path, terminal: dict[str, Any]) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    payload = CONTRACTS.canonical_json_bytes(terminal)
    terminal_path = directory / "terminal.private.json"
    terminal_path.write_bytes(payload)
    seal = {
        "schema_version": SCORE.SEAL_SCHEMA_VERSION,
        "terminal_sha256": hashlib.sha256(payload).hexdigest(),
        "terminal_size_bytes": len(payload),
        "reference_accessed": False,
    }
    seal_path = directory / "terminal.private.sha256.json"
    seal_path.write_bytes(CONTRACTS.canonical_json_bytes(seal))
    return terminal_path, seal_path


def _region(region_id: str, bbox: list[float]) -> dict[str, Any]:
    return {
        "region_id": region_id,
        "bbox_normalized": bbox,
        "evidence_medium": "text_layer",
        "review": {"decision": "approve"},
    }


def _reference_shell(manifest_sha: str, *, reviewer_identity: str) -> dict[str, Any]:
    return {
        "schema_version": SCORE.FINAL_REFERENCE_SCHEMA,
        "benchmark_id": "pdf_dual_vlm_fact_v1",
        "manifest_sha256": manifest_sha,
        "human_reviewed": True,
        "reviewer": {
            "kind": "human",
            "identity": reviewer_identity,
            "reviewed_at": "2026-07-16T12:00:00+03:00",
        },
        "lineage": {
            "proposed_reference_sha256": "3" * 64,
            "review_index_sha256": "4" * 64,
            "review_decisions_sha256": "5" * 64,
            "decision_ledger_tail_sha256": "6" * 64,
        },
        "cases": [],
    }


def _reference_seal(reference: dict[str, Any], manifest_sha: str) -> dict[str, Any]:
    seal = {
        "schema_version": SCORE.FINAL_REFERENCE_SEAL_SCHEMA,
        "reference_filename": "reference.human-reviewed.private.json",
        "reference_sha256": "2" * 64,
        "reference_size_bytes": 123,
        "human_reviewed": True,
        "reviewer_identity": reference["reviewer"]["identity"],
        "reviewed_at": reference["reviewer"]["reviewed_at"],
        "manifest_sha256": manifest_sha,
        "proposed_reference_sha256": "3" * 64,
        "review_index_sha256": "4" * 64,
        "review_decisions_sha256": "5" * 64,
    }
    seal["seal_sha256"] = CONTRACTS.sha256_json(seal)
    return seal


def _valid_crop_fixture() -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]
]:
    manifest_case = copy.deepcopy(_manifest()["cases"][1])
    case_id = str(manifest_case["case_id"])
    page_sha = "7" * 64
    crop_sha = "8" * 64
    candidate = {
        "candidate_id": "candidate_1",
        "bbox": [0.1, 0.1, 0.5, 0.5],
        "state": "present",
        "reason_codes": [],
    }
    contract = {
        "schema_version": CONTRACTS.CROP_CONTRACT_VERSION,
        "document_id": case_id,
        "pdf_sha256": manifest_case["pdf_sha256"],
        "page_number": manifest_case["page_number"],
        "page_image_sha256": page_sha,
        "crop_id": "crop_1",
        "source_bbox_points": [61.2, 79.2, 306.0, 396.0],
        "rendered_bbox_points": [61.2, 79.2, 306.0, 396.0],
        "normalized_bbox": candidate["bbox"],
        "source_to_pixel_transform": {
            "scale_x": 1.0,
            "scale_y": 1.0,
            "translate_source_x": 0.0,
            "translate_source_y": 0.0,
        },
        "render_dpi": 150,
        "dimensions": {"width": 510, "height": 660},
        "rendered_image_bytes": 1234,
        "rendered_image_sha256": crop_sha,
        "renderer": "test",
        "renderer_version": "1",
        "padding_points": 0,
        "lossless": True,
        "silent_resize_performed": False,
        "raster_manifest_hash": "9" * 64,
    }
    contract["contract_checksum"] = CONTRACTS.sha256_json(contract)
    identity = {
        "document_id": case_id,
        "page_number": manifest_case["page_number"],
        "crop_id": "crop_1",
        "crop_sha256": crop_sha,
    }
    gemini_output = _no_fact_output(identity)
    openai_output = _no_fact_output(identity)
    consensus = CONTRACTS.compare_provider_facts(gemini_output, openai_output)
    evidence = (
        EVIDENCE.PdfDualVlmFactEvidenceFactory()
        .create()
        .verify(
            consensus_facts=[],
            word_inventory=[],
            crop_contract=contract,
            page_width=612.0,
            page_height=792.0,
            medium="text_layer",
        )
    )
    model_view = CONTRACTS.fact_model_view(**identity)
    schema = CONTRACTS.financial_fact_schema()
    crop = {
        "candidate": candidate,
        "crop_contract": contract,
        "crop_reproducibility": {
            "renders": 2,
            "byte_identical": True,
            "first_sha256": crop_sha,
            "second_sha256": crop_sha,
        },
        "same_crop_sha256_for_both_extractors": True,
        "evidence_medium": "text_layer",
        "gemini": {
            "status": "completed",
            "output": gemini_output,
            "contract_errors": [],
            "operation": _operation(
                output=gemini_output,
                provider="google",
                model="models/gemini-3.5-flash",
                kind="gemini_crop_financial_fact_extraction",
                crop_sha=crop_sha,
                model_view=model_view,
                schema=schema,
            ),
        },
        "openai": {
            "status": "completed",
            "output": openai_output,
            "contract_errors": [],
            "operation": _operation(
                output=openai_output,
                provider="openai",
                model="gpt-5.4-mini-2026-03-17",
                kind="openai_crop_financial_fact_extraction",
                crop_sha=crop_sha,
                model_view=model_view,
                schema=schema,
            ),
        },
        "consensus": consensus,
        "evidence": evidence,
        "terminal_status": "completed",
    }
    case_input = {"page_png_sha256": page_sha}
    return manifest_case, case_input, candidate, crop


def _no_fact_output(identity: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": CONTRACTS.FACT_SCHEMA_VERSION,
        **identity,
        "status": "no_financial_facts",
        "table_context": {
            "table_title_exact": None,
            "period_context_exact": None,
            "currency_context_exact": None,
            "unit_scale_context_exact": None,
            "entity_context_exact": None,
            "uncertainty_codes": [],
        },
        "physical_cells": [],
        "facts": [],
        "uncertainty_codes": [],
    }


def _operation(
    *,
    output: dict[str, Any],
    provider: str,
    model: str,
    kind: str,
    crop_sha: str,
    model_view: dict[str, Any],
    schema: dict[str, Any],
) -> dict[str, Any]:
    schema_hash = CONTRACTS.sha256_json(schema)
    return {
        "kind": kind,
        "image_bytes": 1234,
        "model_view_bytes": len(CONTRACTS.canonical_json_bytes(model_view)),
        "schema_bytes": len(CONTRACTS.canonical_json_bytes(schema)),
        "count_tokens": {
            "total_tokens": 100,
            "within_hard_guard": True,
            "model_requested": model,
            "canonical_schema_hash": schema_hash,
        },
        "attempt": {
            "provider": provider,
            "model_requested": model,
            "model_resolved": model,
            "attempt_number": 1,
            "attempt_lineage": [],
            "crop_sha256": crop_sha,
            "model_view_hash": CONTRACTS.sha256_json(model_view),
            "canonical_schema_hash": schema_hash,
            "terminal_failure_class": None,
            "hidden_retry": False,
            "provider_failover": False,
        },
        "json_output": output,
        "call_accounting": {
            "count_or_preflight_calls_attempted": 1,
            "count_or_preflight_calls_completed": 1,
            "generate_calls_attempted": 1,
            "generate_calls_completed": 1,
        },
        "hidden_retry": False,
        "provider_failover": False,
        "provenance_verified": True,
        "provenance_errors": [],
    }


def _consensus_entry(consensus_id: str, row: str, value: str) -> dict[str, Any]:
    return {
        "consensus_id": consensus_id,
        "status": "models_exactly_agree",
        "canonical_fact": {
            "canonical_identity": {
                "fact_type": "total",
                "row": row,
                "header_path": ("amount",),
                "value_exact": value,
                "numeric_value": value,
                "sign": "positive",
                "period": None,
                "currency_literal": None,
                "currency_code": None,
                "unit": None,
                "scale": None,
                "entity": None,
                "qualifiers": (),
            }
        },
    }


def _scoring_crop(entry: dict[str, Any], medium: str) -> dict[str, Any]:
    source_map = _source_map(str(entry["consensus_id"]), medium)
    return {
        "terminal_status": "completed",
        "evidence_medium": medium,
        "gemini": {"status": "completed", "output": {"facts": []}},
        "openai": {"status": "completed", "output": {"facts": []}},
        "consensus": {"entries": [entry]},
        "evidence": {"source_maps": [source_map]},
    }


def _source_map(fact_id: str, medium: str) -> dict[str, Any]:
    match = {
        "parser_ordinals": [1],
        "exact_source_text": "source",
        "claimed_exact_text": "source",
        "match_mode": "whitespace_only_token_join",
        "source_bbox": [1.0, 1.0, 2.0, 2.0],
        "atoms": [{"parser_ordinal": 1}],
    }
    value = {
        "schema_version": EVIDENCE.SOURCE_MAP_SCHEMA_VERSION,
        "fact_id": fact_id,
        "evidence_status": "parser_source_verified",
        "strongest_consensus_evidence_status": "parser_source_verified",
        "automatic_acceptance_eligible": True,
        "medium": medium,
        "source_identity": {
            "pdf_sha256": "a" * 64,
            "page_number": 1,
            "table_bbox": [0.0, 0.0, 10.0, 10.0],
            "crop_sha256": "b" * 64,
        },
        "relation_candidate_count": 1,
        "relation_candidates": [
            {
                "row_label": match,
                "value": match,
                "headers": [match],
                "qualifiers": {},
                "relation_proof": {
                    "row_value_same_row_compatible": True,
                    "headers_ordered_above_and_column_compatible": True,
                    "qualifier_scopes_compatible": True,
                },
            }
        ],
        "value_normalization_performed": False,
        "table_construction_performed": False,
    }
    value["source_map_checksum"] = CONTRACTS.sha256_json(value)
    return value


def _reference_fact(row: str, value: str) -> dict[str, Any]:
    return {
        "fact_id": f"fact_{row}",
        "fact_type": "total",
        "row_label": row,
        "normalized_row_identity": row,
        "header_path": ["amount"],
        "visible_value": value,
        "numeric_value": value,
        "sign": "positive",
        "period": None,
        "currency": None,
        "unit": None,
        "scale": None,
        "entity": None,
        "qualifiers": [],
        "source_regions": {},
    }


def _complete_reference_fact(*, crop_sha: str) -> dict[str, Any]:
    def locator(text: str, bbox: list[float]) -> dict[str, Any]:
        return {
            "artifact_sha256": crop_sha,
            "bbox_normalized": bbox,
            "visible_text": text,
        }

    return {
        "fact_id": "fact_cash",
        "fact_type": "monetary_balance",
        "row_label": "Cash",
        "normalized_row_identity": "cash",
        "header_path": ["Amount"],
        "visible_value": "$ 100",
        "numeric_value": "100",
        "sign": "positive",
        "period": None,
        "currency": None,
        "unit": None,
        "scale": None,
        "entity": None,
        "qualifiers": [],
        "source_regions": {
            "row_label": locator("Cash", [0.05, 0.2, 0.35, 0.3]),
            "header": [locator("Amount", [0.6, 0.05, 0.95, 0.15])],
            "value": locator("$ 100", [0.65, 0.2, 0.95, 0.3]),
            "context": [],
        },
        "uncertainty": [],
        "alternative_interpretation": None,
    }


def _provider_score(
    *, precision: float, recall: float, false_positive: int
) -> dict[str, Any]:
    return {
        "precision": precision,
        "recall": recall,
        "f1": precision,
        "false_positive_facts": false_positive,
    }


def _rechecksum(value: dict[str, Any], checksum_key: str) -> None:
    value.pop(checksum_key, None)
    value[checksum_key] = CONTRACTS.sha256_json(value)
