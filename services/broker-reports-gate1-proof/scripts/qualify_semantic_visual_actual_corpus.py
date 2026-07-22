#!/usr/bin/env python3
"""Qualify the frozen semantic visual-table contract on the actual corpus."""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCRIPT_PATH = Path(__file__).resolve()
SERVICE_ROOT = SCRIPT_PATH.parent.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
DEFAULT_MANIFEST = (
    SERVICE_ROOT / "benchmarks" / "semantic_visual_actual_corpus_v1" / "manifest.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "2026-07-22"
    / "BROKER_REPORTS_SEMANTIC_ACTUAL_CORPUS_QUALIFICATION_EVIDENCE"
)

sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(SCRIPT_PATH.parent))

from broker_reports_gate1.pdf_dual_vlm_canonical_table_contracts import (  # noqa: E402
    canonical_json_bytes,
)
from broker_reports_gate1.pdf_dual_vlm_runtime import (  # noqa: E402
    PdfDualVlmRuntimeConfig,
    PdfDualVlmRuntimeFactory,
    sha256_json,
)
from broker_reports_gate1.semantic_visual_actual_corpus import (  # noqa: E402
    EXPECTED_ACCEPTED_TABLES,
    EXPECTED_CORPUS_TABLES,
    build_semantic_source_reference,
)
from broker_reports_gate1.semantic_visual_table_contracts import (  # noqa: E402
    SEMANTIC_TABLE_TRANSCRIPTION_PROMPT,
    SEMANTIC_TABLE_TRANSCRIPTION_PROMPT_VERSION,
    SEMANTIC_TABLE_TRANSCRIPTION_SCHEMA_VERSION,
    semantic_table_transcription_model_view,
    semantic_table_transcription_schema,
)
from broker_reports_gate1.semantic_visual_table_hypothesis import (  # noqa: E402
    SEMANTIC_ACTUAL_CORPUS_REFERENCE_SCHEMA,
    compare_material_repeatability,
    public_score_summary,
    score_semantic_response,
    validate_source_reference,
)
from broker_reports_gate1.semantic_visual_table_validator import (  # noqa: E402
    validate_semantic_visual_table_response,
)
from evaluate_pdf_dual_vlm_actual_corpus import prepare_candidates  # noqa: E402
from qualify_semantic_visual_three_table import _openwebui_request  # noqa: E402


MANIFEST_SCHEMA = "broker_reports_semantic_actual_corpus_manifest_v1"
PRIVATE_TERMINAL_SCHEMA = (
    "broker_reports_semantic_actual_corpus_qualification_terminal_v1_private"
)
SAFE_RECEIPT_SCHEMA = (
    "broker_reports_semantic_actual_corpus_qualification_receipt_v1_safe"
)
EXPECTED_GEMINI_EXECUTIONS = 18
EXPECTED_OPENAI_EXECUTIONS = 9
EXPECTED_ACCEPTED_GEMINI_EXECUTIONS = 16


class SemanticActualCorpusQualificationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--rescore-existing",
        action="store_true",
        help="Rescore preserved raw responses without provider calls.",
    )
    args = parser.parse_args(argv)
    if args.rescore_existing:
        receipt = rescore_existing(
            manifest_path=args.manifest.resolve(),
            output_dir=args.output_dir.resolve(),
        )
    else:
        receipt = run(
            manifest_path=args.manifest.resolve(),
            env_path=args.env_file.resolve(),
            output_dir=args.output_dir.resolve(),
        )
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if receipt["status"] == "COMPLETED" else 1


def run(*, manifest_path: Path, env_path: Path, output_dir: Path) -> dict[str, Any]:
    _require_report_output(output_dir)
    _require_fresh_directory(output_dir)
    manifest_bytes = manifest_path.read_bytes()
    manifest = _json_object(
        manifest_bytes, "semantic_actual_corpus_manifest_invalid"
    )
    _validate_manifest(manifest)
    inputs = _load_inputs(manifest)
    reference, unsupported = build_semantic_source_reference(
        inputs["delegated_reference"],
        inputs["delegated_reference_seal"],
        inputs["semantic_reference_supplement"],
    )
    reference_bytes = canonical_json_bytes(reference)
    if _sha256_bytes(reference_bytes) != manifest["inputs"][
        "projected_semantic_reference"
    ]["canonical_sha256"]:
        raise SemanticActualCorpusQualificationError(
            "semantic_actual_corpus_projected_reference_hash_mismatch"
        )
    candidates = prepare_candidates(
        manifest=inputs["corpus_manifest"],
        detection=inputs["detection_terminal"],
        corpus_root=inputs["corpus_root"],
    )
    _verify_candidates(candidates, manifest)
    frozen_contract = _contract_snapshot(manifest)

    output_dir.mkdir(parents=True, exist_ok=False)
    started_at = datetime.now(timezone.utc).isoformat()
    request = _openwebui_request(env_path)
    records: list[dict[str, Any]] = []

    diagnostic_runtime = PdfDualVlmRuntimeFactory(
        PdfDualVlmRuntimeConfig(
            enabled=True,
            execution_mode="diagnostic_control",
            openai_invocation_policy="diagnostic_control",
            gemini_model_id=manifest["provider_contracts"]["gemini"]["model_id"],
            openai_model_id=manifest["provider_contracts"]["openai"]["model_id"],
            maximum_candidates=8,
        )
    ).create_for_openwebui(request)
    for chunk in _chunks(candidates, 8):
        records.extend(
            _collect_records(
                diagnostic_runtime.run(chunk),
                gemini_run="gemini_run_a",
                openai_run="openai_control",
            )
        )
    if _contract_snapshot(manifest) != frozen_contract:
        raise SemanticActualCorpusQualificationError(
            "semantic_actual_corpus_contract_changed_after_diagnostic_run"
        )

    repeat_runtime = PdfDualVlmRuntimeFactory(
        PdfDualVlmRuntimeConfig(
            enabled=True,
            gemini_model_id=manifest["provider_contracts"]["gemini"]["model_id"],
            openai_model_id=manifest["provider_contracts"]["openai"]["model_id"],
            maximum_candidates=8,
        )
    ).create_for_openwebui(request)
    for chunk in _chunks(candidates, 8):
        records.extend(
            _collect_records(
                repeat_runtime.run(chunk),
                gemini_run="gemini_run_b",
                openai_run=None,
            )
        )
    if _contract_snapshot(manifest) != frozen_contract:
        raise SemanticActualCorpusQualificationError(
            "semantic_actual_corpus_contract_changed_after_provider_execution"
        )

    _verify_execution_freeze(records, manifest)
    reference_by_id = {table["table_id"]: table for table in reference["tables"]}
    for record in records:
        reference_table = reference_by_id.get(record["candidate_ref"])
        if reference_table is None:
            record["score"] = None
            record["unsupported_schema_validation"] = (
                validate_semantic_visual_table_response(
                    record["parsed_response"],
                    raw_json_text=record["raw_response_text"],
                    require_raw_json=True,
                )
            )
        else:
            record["score"] = score_semantic_response(
                reference_table,
                record["parsed_response"],
                raw_json_text=record["raw_response_text"],
            )
            record["unsupported_schema_validation"] = None
    records.sort(key=_record_sort_key)
    repeatability = _repeatability(records, manifest)
    gate = _evaluate_gate(records, repeatability, unsupported, manifest)
    ended_at = datetime.now(timezone.utc).isoformat()
    terminal = {
        "schema_version": PRIVATE_TERMINAL_SCHEMA,
        "status": "COMPLETED",
        "qualification_gate_status": gate["status"],
        "experiment_id": manifest["experiment_id"],
        "started_at": started_at,
        "ended_at": ended_at,
        "manifest_sha256": _sha256_bytes(manifest_bytes),
        "source_reference_sha256": _sha256_bytes(reference_bytes),
        "frozen_contract": frozen_contract,
        "records": [_terminal_record(record) for record in records],
        "repeatability": repeatability,
        "unsupported_layouts": copy.deepcopy(unsupported),
        "gate": gate,
        "source_reference_available_to_providers": False,
        "provider_outputs_used_as_reference_truth": False,
        "provider_consensus_used_as_reference_truth": False,
        "provider_merge_performed": False,
        "provider_repair_performed": False,
        "hidden_retry_performed": False,
        "geometric_metrics_used": False,
        "production_default_activation_performed": False,
        "stage_mutation_performed": False,
    }
    terminal["terminal_hash"] = sha256_json(terminal)
    receipt = _safe_receipt(terminal, records, manifest)
    _write_evidence(
        output_dir=output_dir,
        manifest_bytes=manifest_bytes,
        reference_bytes=reference_bytes,
        candidates=candidates,
        records=records,
        terminal=terminal,
        receipt=receipt,
    )
    return receipt


def rescore_existing(
    *, manifest_path: Path, output_dir: Path
) -> dict[str, Any]:
    """Recompute scores from preserved evidence; never call a provider."""

    _require_report_output(output_dir)
    if not output_dir.is_dir():
        raise SemanticActualCorpusQualificationError(
            "semantic_actual_corpus_existing_evidence_missing"
        )
    manifest_bytes = manifest_path.read_bytes()
    if (output_dir / "frozen_manifest.json").read_bytes() != manifest_bytes:
        raise SemanticActualCorpusQualificationError(
            "semantic_actual_corpus_rescore_manifest_mismatch"
        )
    manifest = _json_object(
        manifest_bytes, "semantic_actual_corpus_manifest_invalid"
    )
    _validate_manifest(manifest)
    reference_bytes = (output_dir / "source_reference.private.json").read_bytes()
    reference = validate_source_reference(
        _json_object(
            reference_bytes, "semantic_actual_corpus_preserved_reference_invalid"
        ),
        expected_table_count=EXPECTED_ACCEPTED_TABLES,
        expected_schema_version=SEMANTIC_ACTUAL_CORPUS_REFERENCE_SCHEMA,
    )
    if _sha256_bytes(reference_bytes) != manifest["inputs"][
        "projected_semantic_reference"
    ]["canonical_sha256"]:
        raise SemanticActualCorpusQualificationError(
            "semantic_actual_corpus_preserved_reference_hash_mismatch"
        )
    previous_terminal = _json_object(
        (output_dir / "terminal.private.json").read_bytes(),
        "semantic_actual_corpus_preserved_terminal_invalid",
    )
    previous_status = {
        (record["candidate_ref"], record["run"]): record["decision_status"]
        for record in previous_terminal["records"]
    }
    records: list[dict[str, Any]] = []
    for case in manifest["cases"]:
        table_dir = output_dir / case["candidate_ref"]
        for run_name, provider in (
            ("gemini_run_a", "gemini"),
            ("gemini_run_b", "gemini"),
            ("openai_control", "openai"),
        ):
            raw_text = (table_dir / f"{run_name}.raw.json").read_text(
                encoding="utf-8"
            )
            records.append(
                {
                    "candidate_ref": case["candidate_ref"],
                    "crop_sha256": case["crop_sha256"],
                    "provider": provider,
                    "run": run_name,
                    "decision_status": previous_status[
                        (case["candidate_ref"], run_name)
                    ],
                    "execution": _json_object(
                        (table_dir / f"{run_name}.execution.safe.json").read_bytes(),
                        "semantic_actual_corpus_preserved_execution_invalid",
                    ),
                    "raw_provider_response": json.loads(
                        (
                            table_dir
                            / f"{run_name}.adapter_response.private.json"
                        ).read_bytes()
                    ),
                    "raw_response_text": raw_text,
                    "parsed_response": json.loads(
                        (
                            table_dir / f"{run_name}.parsed.private.json"
                        ).read_bytes()
                    ),
                }
            )
    _verify_execution_freeze(records, manifest)
    reference_by_id = {table["table_id"]: table for table in reference["tables"]}
    for record in records:
        reference_table = reference_by_id.get(record["candidate_ref"])
        if reference_table is None:
            record["score"] = None
            record["unsupported_schema_validation"] = (
                validate_semantic_visual_table_response(
                    record["parsed_response"],
                    raw_json_text=record["raw_response_text"],
                    require_raw_json=True,
                )
            )
        else:
            record["score"] = score_semantic_response(
                reference_table,
                record["parsed_response"],
                raw_json_text=record["raw_response_text"],
            )
            record["unsupported_schema_validation"] = None
    records.sort(key=_record_sort_key)
    repeatability = _repeatability(records, manifest)
    unsupported = copy.deepcopy(previous_terminal["unsupported_layouts"])
    gate = _evaluate_gate(records, repeatability, unsupported, manifest)
    terminal = copy.deepcopy(previous_terminal)
    terminal.pop("terminal_hash", None)
    terminal.update(
        {
            "qualification_gate_status": gate["status"],
            "records": [_terminal_record(record) for record in records],
            "repeatability": repeatability,
            "gate": gate,
            "rescored_at": datetime.now(timezone.utc).isoformat(),
            "scoring_revision": "literal_semantic_rows_v1_1",
            "scoring_revision_reason": (
                "currency marker spacing and apostrophe glyph equivalence only; "
                "exact-label completeness remains separately measured"
            ),
            "provider_executions_repeated_for_rescore": False,
            "raw_provider_evidence_unchanged": True,
        }
    )
    terminal["terminal_hash"] = sha256_json(terminal)
    receipt = _safe_receipt(terminal, records, manifest)
    for record in records:
        table_dir = output_dir / record["candidate_ref"]
        if record["score"] is not None:
            _write_json(
                table_dir / f"{record['run']}.score.private.json",
                record["score"],
            )
        else:
            _write_json(
                table_dir / f"{record['run']}.unsupported_validation.private.json",
                record["unsupported_schema_validation"],
            )
    _write_json(output_dir / "terminal.private.json", terminal)
    _write_json(output_dir / "receipt.safe.json", receipt)
    (output_dir / "ANALYSIS.report.md").write_text(
        _render_private_report(receipt), encoding="utf-8"
    )
    return receipt


def _load_inputs(manifest: dict[str, Any]) -> dict[str, Any]:
    specs = manifest["inputs"]
    result: dict[str, Any] = {}
    for name in (
        "corpus_manifest",
        "detection_terminal",
        "detection_seal",
        "delegated_reference",
        "delegated_reference_seal",
        "semantic_reference_supplement",
        "prior_low_level_baseline",
    ):
        spec = specs[name]
        path = (REPO_ROOT / spec["repository_relative_path"]).resolve()
        payload = path.read_bytes()
        expected_hash = spec.get("file_sha256") or spec.get("sha256")
        if _sha256_bytes(payload) != expected_hash:
            raise SemanticActualCorpusQualificationError(
                f"semantic_actual_corpus_{name}_hash_mismatch"
            )
        if name != "prior_low_level_baseline":
            result[name] = _json_object(
                payload, f"semantic_actual_corpus_{name}_invalid"
            )
    result["corpus_root"] = (
        REPO_ROOT / specs["corpus_root_repository_relative"]
    ).resolve()
    if not result["corpus_root"].is_dir():
        raise SemanticActualCorpusQualificationError(
            "semantic_actual_corpus_corpus_root_missing"
        )
    return result


def _validate_manifest(manifest: dict[str, Any]) -> None:
    cases = manifest.get("cases")
    if (
        manifest.get("schema_version") != MANIFEST_SCHEMA
        or manifest.get("frozen_before_provider_execution") is not True
        or not isinstance(cases, list)
        or len(cases) != EXPECTED_CORPUS_TABLES
        or len({case.get("candidate_ref") for case in cases})
        != EXPECTED_CORPUS_TABLES
        or sum(
            case.get("disposition") == "accepted_numeric_profile_candidate"
            for case in cases
        )
        != EXPECTED_ACCEPTED_TABLES
        or sum(case.get("disposition") == "unsupported_layout" for case in cases)
        != 1
        or manifest.get("provider_contracts", {})
        .get("gemini", {})
        .get("executions")
        != EXPECTED_GEMINI_EXECUTIONS
        or manifest.get("provider_contracts", {})
        .get("openai", {})
        .get("executions")
        != EXPECTED_OPENAI_EXECUTIONS
        or manifest.get("gate", {}).get("gemini_execution_count")
        != EXPECTED_ACCEPTED_GEMINI_EXECUTIONS
    ):
        raise SemanticActualCorpusQualificationError(
            "semantic_actual_corpus_manifest_invalid"
        )


def _contract_snapshot(manifest: dict[str, Any]) -> dict[str, Any]:
    expected = manifest["semantic_contract"]
    snapshot = {
        "schema_version": SEMANTIC_TABLE_TRANSCRIPTION_SCHEMA_VERSION,
        "schema_sha256": sha256_json(semantic_table_transcription_schema()),
        "prompt_version": SEMANTIC_TABLE_TRANSCRIPTION_PROMPT_VERSION,
        "prompt_sha256": hashlib.sha256(
            SEMANTIC_TABLE_TRANSCRIPTION_PROMPT.encode("utf-8")
        ).hexdigest(),
        "model_view_sha256": sha256_json(
            semantic_table_transcription_model_view()
        ),
    }
    if any(expected.get(key) != value for key, value in snapshot.items()):
        raise SemanticActualCorpusQualificationError(
            "semantic_actual_corpus_frozen_contract_mismatch"
        )
    return snapshot


def _verify_candidates(candidates: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    expected = {case["candidate_ref"]: case for case in manifest["cases"]}
    if len(candidates) != EXPECTED_CORPUS_TABLES:
        raise SemanticActualCorpusQualificationError(
            "semantic_actual_corpus_candidate_count_invalid"
        )
    for candidate in candidates:
        candidate_manifest = candidate.get("manifest") or {}
        candidate_ref = candidate_manifest.get("candidate_ref")
        case = expected.get(candidate_ref)
        if case is None or any(
            candidate_manifest.get(source_key) != case[target_key]
            for source_key, target_key in (
                ("png_sha256", "crop_sha256"),
                ("width", "width"),
                ("height", "height"),
                ("page_number", "page_number"),
                ("pdf_sha256", "pdf_sha256"),
            )
        ):
            raise SemanticActualCorpusQualificationError(
                "semantic_actual_corpus_candidate_identity_mismatch"
            )


def _collect_records(
    outcome: Any, *, gemini_run: str, openai_run: str | None
) -> list[dict[str, Any]]:
    evidence_by_execution = {
        item.get("execution_hash"): item
        for item in outcome.private_provider_evidence
        if isinstance(item, dict)
    }
    result: list[dict[str, Any]] = []
    for decision in outcome.private_decisions:
        lineage = decision.get("source_lineage") or {}
        candidate_ref = lineage.get("candidate_ref")
        for execution in decision.get("executions") or []:
            provider = execution.get("provider")
            run_name = gemini_run if provider == "gemini" else openai_run
            if run_name is None:
                raise SemanticActualCorpusQualificationError(
                    "semantic_actual_corpus_unexpected_provider_execution"
                )
            evidence = evidence_by_execution.get(execution.get("execution_hash"))
            if not isinstance(evidence, dict):
                raise SemanticActualCorpusQualificationError(
                    "semantic_actual_corpus_private_evidence_missing"
                )
            result.append(
                {
                    "candidate_ref": candidate_ref,
                    "crop_sha256": lineage.get("crop_sha256"),
                    "provider": provider,
                    "run": run_name,
                    "decision_status": decision.get("status"),
                    "execution": copy.deepcopy(execution),
                    "raw_provider_response": copy.deepcopy(
                        evidence.get("raw_provider_response")
                    ),
                    "raw_response_text": evidence.get("raw_response_text"),
                    "parsed_response": copy.deepcopy(
                        evidence.get("parsed_semantic_response")
                    ),
                }
            )
    return result


def _verify_execution_freeze(
    records: list[dict[str, Any]], manifest: dict[str, Any]
) -> None:
    if (
        len(records) != EXPECTED_GEMINI_EXECUTIONS + EXPECTED_OPENAI_EXECUTIONS
        or sum(record["provider"] == "gemini" for record in records)
        != EXPECTED_GEMINI_EXECUTIONS
        or sum(record["provider"] == "openai" for record in records)
        != EXPECTED_OPENAI_EXECUTIONS
    ):
        raise SemanticActualCorpusQualificationError(
            "semantic_actual_corpus_execution_count_invalid"
        )
    expected_cases = {case["candidate_ref"]: case for case in manifest["cases"]}
    models = {
        provider: manifest["provider_contracts"][provider]["model_id"]
        for provider in ("gemini", "openai")
    }
    for record in records:
        execution = record["execution"]
        case = expected_cases.get(record["candidate_ref"])
        if (
            case is None
            or record["crop_sha256"] != case["crop_sha256"]
            or execution.get("prompt_hash")
            != manifest["semantic_contract"]["prompt_sha256"]
            or execution.get("canonical_schema_hash")
            != manifest["semantic_contract"]["schema_sha256"]
            or execution.get("requested_model_id") != models[record["provider"]]
            or execution.get("resolved_model_id") != models[record["provider"]]
            or execution.get("attempt_number") != 1
            or execution.get("attempt_lineage") != []
            or execution.get("hidden_retry") is not False
            or execution.get("provider_failover") is not False
            or execution.get("provider_switch") is not False
            or execution.get("whole_document_uploaded") is not False
            or execution.get("crop_sha256") != record["crop_sha256"]
        ):
            raise SemanticActualCorpusQualificationError(
                "semantic_actual_corpus_execution_freeze_invalid"
            )


def _repeatability(
    records: list[dict[str, Any]], manifest: dict[str, Any]
) -> list[dict[str, Any]]:
    result = []
    for case in manifest["cases"]:
        candidate_ref = case["candidate_ref"]
        pair = {
            record["run"]: record
            for record in records
            if record["candidate_ref"] == candidate_ref
            and record["provider"] == "gemini"
        }
        if set(pair) != {"gemini_run_a", "gemini_run_b"}:
            raise SemanticActualCorpusQualificationError(
                "semantic_actual_corpus_repeat_pair_invalid"
            )
        comparison = compare_material_repeatability(
            pair["gemini_run_a"]["parsed_response"],
            pair["gemini_run_b"]["parsed_response"],
        )
        comparison.update(
            {
                "candidate_ref": candidate_ref,
                "crop_sha256": case["crop_sha256"],
                "disposition": case["disposition"],
            }
        )
        result.append(comparison)
    return result


def _evaluate_gate(
    records: list[dict[str, Any]],
    repeatability: list[dict[str, Any]],
    unsupported: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    accepted_refs = {
        case["candidate_ref"]
        for case in manifest["cases"]
        if case["disposition"] == "accepted_numeric_profile_candidate"
    }
    gemini_scores = [
        record["score"]
        for record in records
        if record["provider"] == "gemini"
        and record["candidate_ref"] in accepted_refs
    ]
    unexplained = [
        record
        for record in records
        if record["decision_status"] != "semantic_transcription_valid"
        or record["execution"].get("terminal_provider_status") != "completed"
    ]
    checks = {
        "accepted_gemini_execution_count": len(gemini_scores)
        == EXPECTED_ACCEPTED_GEMINI_EXECUTIONS,
        "semantic_schema_valid": all(
            isinstance(score, dict) and score.get("semantic_schema_valid") is True
            for score in gemini_scores
        ),
        "amount_fidelity": all(
            score["amount_fidelity"]["rate"] == 1.0 for score in gemini_scores
        ),
        "row_value_binding": all(
            score["row_value_binding"]["rate"] == 1.0 for score in gemini_scores
        ),
        "zero_hallucinated_amounts": all(
            score["hallucinated_amounts"] == [] for score in gemini_scores
        ),
        "zero_unexplained_terminals": not unexplained,
        "unsupported_layout_fail_closed": (
            len(unsupported) == 1
            and unsupported[0]["candidate_ref"]
            not in {score["table_id"] for score in gemini_scores}
        ),
    }
    prior = manifest["inputs"]["prior_low_level_baseline"]
    gate = {
        "status": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "failed_invariants": [key for key, passed in checks.items() if not passed],
        "gemini_master_execution_count": len(gemini_scores),
        "unexplained_terminal_count": len(unexplained),
        "fallback_execution_count": sum(
            record["execution"].get("provider_failover") is True
            for record in records
        ),
        "diagnostic_openai_execution_count": sum(
            record["provider"] == "openai" for record in records
        ),
        "gemini_material_repeatability": {
            "matches": sum(
                item["materially_identical"]
                for item in repeatability
                if item["disposition"] == "accepted_numeric_profile_candidate"
            ),
            "opportunities": EXPECTED_ACCEPTED_TABLES,
        },
        "prior_low_level_baseline": {
            "contract_validity_rate": prior["contract_validity_rate"],
            "numeric_value_agreement_rate": prior[
                "numeric_value_agreement_rate"
            ],
            "row_binding_support_rate": prior["row_binding_support_rate"],
            "numeric_value_hallucination_rate": prior[
                "numeric_value_hallucination_rate"
            ],
            "structurally_useful_distinct_crops": prior[
                "structurally_useful_distinct_crops"
            ],
            "bounded_crop_count": prior["bounded_crop_count"],
        },
        "production_default_activation_authorized": False,
        "production_default_activation_requires_goal6": True,
        "scoring_equivalence": {
            "combined_currency_marker_with_or_without_space": True,
            "apostrophe_glyph_equivalent_for_row_binding": True,
            "apostrophe_glyph_variants_retained_in_exact_label_metric": True,
        },
        "provider_merge_performed": False,
        "provider_repair_performed": False,
        "geometric_metrics_used": False,
    }
    gate["gate_hash"] = sha256_json(gate)
    return gate


def _terminal_record(record: dict[str, Any]) -> dict[str, Any]:
    raw_text = record["raw_response_text"]
    return {
        "candidate_ref": record["candidate_ref"],
        "crop_sha256": record["crop_sha256"],
        "provider": record["provider"],
        "run": record["run"],
        "decision_status": record["decision_status"],
        "execution": copy.deepcopy(record["execution"]),
        "raw_response_text_sha256": (
            hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
            if isinstance(raw_text, str)
            else None
        ),
        "raw_provider_response_sha256": sha256_json(
            record["raw_provider_response"]
        ),
        "parsed_response_sha256": sha256_json(record["parsed_response"]),
        "score": copy.deepcopy(record["score"]),
        "unsupported_schema_validation": copy.deepcopy(
            record["unsupported_schema_validation"]
        ),
    }


def _safe_receipt(
    terminal: dict[str, Any],
    records: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    cases = {case["candidate_ref"]: case for case in manifest["cases"]}
    scores = [
        {
            "provider": record["provider"],
            "run": record["run"],
            "layout_families": copy.deepcopy(
                cases[record["candidate_ref"]]["layout_families"]
            ),
            **public_score_summary(record["score"]),
        }
        for record in records
        if isinstance(record["score"], dict)
    ]
    receipt = {
        "schema_version": SAFE_RECEIPT_SCHEMA,
        "status": terminal["status"],
        "qualification_gate_status": terminal["qualification_gate_status"],
        "experiment_id": terminal["experiment_id"],
        "started_at": terminal["started_at"],
        "ended_at": terminal["ended_at"],
        "manifest_sha256": terminal["manifest_sha256"],
        "source_reference_sha256": terminal["source_reference_sha256"],
        "frozen_contract": copy.deepcopy(terminal["frozen_contract"]),
        "execution_counts": {
            "bounded_tables": EXPECTED_CORPUS_TABLES,
            "accepted_numeric_tables": EXPECTED_ACCEPTED_TABLES,
            "unsupported_layouts": 1,
            "gemini": sum(record["provider"] == "gemini" for record in records),
            "openai_control": sum(
                record["provider"] == "openai" for record in records
            ),
        },
        "scores": scores,
        "repeatability": copy.deepcopy(terminal["repeatability"]),
        "unsupported_layouts": [
            {
                "candidate_ref": item["candidate_ref"],
                "crop_sha256": item["crop_sha256"],
                "layout_families": copy.deepcopy(item["layout_families"]),
            }
            for item in terminal["unsupported_layouts"]
        ],
        "gate": copy.deepcopy(terminal["gate"]),
        "crop_bytes_committed": False,
        "provider_output_values_committed": False,
        "private_evidence_retained": True,
        "provider_outputs_used_as_reference_truth": False,
        "provider_consensus_used_as_reference_truth": False,
        "provider_merge_performed": False,
        "provider_repair_performed": False,
        "geometric_metrics_used": False,
        "customer_acceptance_claimed": False,
        "stage_mutation_performed": False,
    }
    receipt["receipt_hash"] = sha256_json(receipt)
    return receipt


def _write_evidence(
    *,
    output_dir: Path,
    manifest_bytes: bytes,
    reference_bytes: bytes,
    candidates: list[dict[str, Any]],
    records: list[dict[str, Any]],
    terminal: dict[str, Any],
    receipt: dict[str, Any],
) -> None:
    (output_dir / "frozen_manifest.json").write_bytes(manifest_bytes)
    (output_dir / "source_reference.private.json").write_bytes(reference_bytes)
    for candidate in candidates:
        candidate_ref = candidate["manifest"]["candidate_ref"]
        table_dir = output_dir / candidate_ref
        table_dir.mkdir()
        png_bytes = base64.b64decode(candidate["private_png_base64"], validate=True)
        (table_dir / "crop.png").write_bytes(png_bytes)
        _write_json(table_dir / "crop.manifest.json", candidate["manifest"])
    for record in records:
        table_dir = output_dir / record["candidate_ref"]
        prefix = record["run"]
        raw_text = record["raw_response_text"]
        (table_dir / f"{prefix}.raw.json").write_text(
            raw_text if isinstance(raw_text, str) else "null", encoding="utf-8"
        )
        _write_json(
            table_dir / f"{prefix}.adapter_response.private.json",
            record["raw_provider_response"],
        )
        _write_json(
            table_dir / f"{prefix}.parsed.private.json",
            record["parsed_response"],
        )
        _write_json(
            table_dir / f"{prefix}.execution.safe.json", record["execution"]
        )
        if record["score"] is not None:
            _write_json(
                table_dir / f"{prefix}.score.private.json", record["score"]
            )
        else:
            _write_json(
                table_dir / f"{prefix}.unsupported_validation.private.json",
                record["unsupported_schema_validation"],
            )
    for item in terminal["repeatability"]:
        _write_json(
            output_dir / item["candidate_ref"] / "repeatability.safe.json", item
        )
    _write_json(output_dir / "terminal.private.json", terminal)
    _write_json(output_dir / "receipt.safe.json", receipt)
    (output_dir / "ANALYSIS.report.md").write_text(
        _render_private_report(receipt), encoding="utf-8"
    )


def _render_private_report(receipt: dict[str, Any]) -> str:
    lines = [
        "# Broker Reports — semantic actual-corpus qualification",
        "",
        f"Execution: `{receipt['status']}`; gate: "
        f"`{receipt['qualification_gate_status']}`.",
        "",
        "The private package retains byte-identical crops and raw provider JSON. "
        "The committed report must use only this safe receipt and aggregate facts.",
        "",
        "| Table | Provider/run | Labels | Amounts | Binding | Hallucinated amounts |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for score in receipt["scores"]:
        lines.append(
            "| {table} | {provider}/{run} | {labels:.1%} | {amounts:.1%} | "
            "{binding:.1%} | {hallucinations} |".format(
                table=score["table_id"],
                provider=score["provider"],
                run=score["run"],
                labels=score["label_completeness"]["rate"],
                amounts=score["amount_fidelity"]["rate"],
                binding=score["row_value_binding"]["rate"],
                hallucinations=score["hallucinated_amount_count"],
            )
        )
    return "\n".join(lines) + "\n"


def _record_sort_key(record: dict[str, Any]) -> tuple[str, int]:
    return (
        record["candidate_ref"],
        ("gemini_run_a", "gemini_run_b", "openai_control").index(record["run"]),
    )


def _chunks(values: list[Any], size: int) -> Iterable[list[Any]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def _require_report_output(path: Path) -> None:
    approved = (REPO_ROOT / "docs" / "reports").resolve()
    try:
        path.relative_to(approved)
    except ValueError as exc:
        raise SemanticActualCorpusQualificationError(
            "semantic_actual_corpus_output_path_invalid"
        ) from exc


def _require_fresh_directory(path: Path) -> None:
    if path.exists():
        raise SemanticActualCorpusQualificationError(
            "semantic_actual_corpus_output_exists"
        )


def _json_object(payload: bytes, failure: str) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SemanticActualCorpusQualificationError(failure) from exc
    if not isinstance(value, dict):
        raise SemanticActualCorpusQualificationError(failure)
    return value


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
