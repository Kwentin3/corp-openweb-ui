#!/usr/bin/env python3
"""Run the frozen three-table semantic visual-table hypothesis test."""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import requests


SCRIPT_PATH = Path(__file__).resolve()
SERVICE_ROOT = SCRIPT_PATH.parent.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
DEFAULT_MANIFEST = (
    SERVICE_ROOT / "benchmarks" / "semantic_visual_three_table_v1" / "manifest.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "2026-07-22"
    / "BROKER_REPORTS_SEMANTIC_THREE_TABLE_HYPOTHESIS_EVIDENCE"
)

sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.pdf_dual_vlm_runtime import (  # noqa: E402
    PdfDualVlmRuntimeConfig,
    PdfDualVlmRuntimeFactory,
    sha256_json,
)
from broker_reports_gate1.semantic_visual_table_contracts import (  # noqa: E402
    SEMANTIC_TABLE_TRANSCRIPTION_PROMPT,
    SEMANTIC_TABLE_TRANSCRIPTION_PROMPT_VERSION,
    SEMANTIC_TABLE_TRANSCRIPTION_SCHEMA_VERSION,
    semantic_table_transcription_model_view,
    semantic_table_transcription_schema,
)
from broker_reports_gate1.semantic_visual_table_hypothesis import (  # noqa: E402
    compare_material_repeatability,
    evaluate_three_table_gate,
    public_score_summary,
    score_semantic_response,
    validate_source_reference,
)


MANIFEST_SCHEMA = "broker_reports_semantic_three_table_hypothesis_manifest_v1"
PRIVATE_TERMINAL_SCHEMA = (
    "broker_reports_semantic_three_table_hypothesis_terminal_v1_private"
)
SAFE_RECEIPT_SCHEMA = (
    "broker_reports_semantic_three_table_hypothesis_receipt_v1_safe"
)


class SemanticThreeTableQualificationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--source-pack", type=Path)
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--rescore-existing",
        action="store_true",
        help="Recompute diagnostics from preserved responses without provider calls.",
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
            source_pack_override=(
                args.source_pack.resolve() if args.source_pack is not None else None
            ),
            env_path=args.env_file.resolve(),
            output_dir=args.output_dir.resolve(),
        )
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if receipt["status"] == "COMPLETED" else 1


def run(
    *,
    manifest_path: Path,
    source_pack_override: Path | None,
    env_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    _require_report_output(output_dir)
    _require_fresh_directory(output_dir)
    manifest_bytes = manifest_path.read_bytes()
    manifest = _json_object(manifest_bytes, "semantic_three_table_manifest_invalid")
    _validate_manifest(manifest)
    source_pack = source_pack_override or (
        REPO_ROOT / manifest["source_pack_repository_relative"]
    )
    source_pack = source_pack.resolve()
    reference_path = source_pack / manifest["source_reference"]["path"]
    reference_bytes = reference_path.read_bytes()
    if _sha256_bytes(reference_bytes) != manifest["source_reference"]["sha256"]:
        raise SemanticThreeTableQualificationError(
            "semantic_three_table_source_reference_hash_mismatch"
        )
    reference = validate_source_reference(
        _json_object(reference_bytes, "semantic_three_table_source_reference_invalid")
    )
    _verify_source_inputs(manifest, source_pack, reference)
    frozen_contract = _contract_snapshot(manifest)
    candidates = _candidates(manifest, source_pack)

    output_dir.mkdir(parents=True, exist_ok=False)
    started_at = datetime.now(timezone.utc).isoformat()
    request = _openwebui_request(env_path)
    gemini_model = manifest["provider_contracts"]["gemini"]["model_id"]
    openai_model = manifest["provider_contracts"]["openai"]["model_id"]

    diagnostic_runtime = PdfDualVlmRuntimeFactory(
        PdfDualVlmRuntimeConfig(
            enabled=True,
            execution_mode="diagnostic_control",
            openai_invocation_policy="diagnostic_control",
            gemini_model_id=gemini_model,
            openai_model_id=openai_model,
            maximum_candidates=3,
        )
    ).create_for_openwebui(request)
    diagnostic_outcome = diagnostic_runtime.run(candidates)
    if _contract_snapshot(manifest) != frozen_contract:
        raise SemanticThreeTableQualificationError(
            "semantic_three_table_contract_changed_after_first_execution"
        )

    repeat_runtime = PdfDualVlmRuntimeFactory(
        PdfDualVlmRuntimeConfig(
            enabled=True,
            gemini_model_id=gemini_model,
            openai_model_id=openai_model,
            maximum_candidates=3,
        )
    ).create_for_openwebui(request)
    repeat_outcome = repeat_runtime.run(candidates)
    if _contract_snapshot(manifest) != frozen_contract:
        raise SemanticThreeTableQualificationError(
            "semantic_three_table_contract_changed_after_provider_execution"
        )

    records = _collect_records(
        diagnostic_outcome,
        gemini_run="gemini_run_a",
        openai_run="openai_control",
    )
    records.extend(
        _collect_records(
            repeat_outcome,
            gemini_run="gemini_run_b",
            openai_run=None,
        )
    )
    _verify_execution_freeze(records, manifest)
    reference_by_crop = {
        table["crop_sha256"]: table for table in reference["tables"]
    }
    for record in records:
        record["score"] = score_semantic_response(
            reference_by_crop[record["crop_sha256"]],
            record["parsed_response"],
            raw_json_text=record["raw_response_text"],
        )

    records.sort(
        key=lambda item: (
            item["table_id"],
            ("gemini_run_a", "gemini_run_b", "openai_control").index(
                item["run"]
            ),
        )
    )
    repeatability = _repeatability(records)
    gate_executions = [
        {
            "provider": record["provider"],
            "run": record["run"],
            "crop_sha256": record["crop_sha256"],
            "score": record["score"],
        }
        for record in records
    ]
    gate = evaluate_three_table_gate(gate_executions, repeatability)
    ended_at = datetime.now(timezone.utc).isoformat()

    private_terminal = {
        "schema_version": PRIVATE_TERMINAL_SCHEMA,
        "status": gate["status"],
        "experiment_id": manifest["experiment_id"],
        "started_at": started_at,
        "ended_at": ended_at,
        "manifest_sha256": _sha256_bytes(manifest_bytes),
        "source_reference_sha256": _sha256_bytes(reference_bytes),
        "frozen_contract": frozen_contract,
        "transport_source_hashes": _transport_source_hashes(),
        "records": [_terminal_record(record) for record in records],
        "repeatability": copy.deepcopy(repeatability),
        "gate": copy.deepcopy(gate),
        "provider_merge_performed": False,
        "provider_repair_performed": False,
        "hidden_retry_performed": False,
        "geometric_metrics_used": False,
        "prompt_tuned_on_frozen_tables": False,
        "source_reference_available_to_providers": False,
        "customer_acceptance_claimed": False,
    }
    private_terminal["terminal_hash"] = sha256_json(private_terminal)
    receipt = _safe_receipt(private_terminal, records)
    _write_evidence_package(
        output_dir=output_dir,
        source_pack=source_pack,
        manifest=manifest,
        manifest_bytes=manifest_bytes,
        reference_bytes=reference_bytes,
        records=records,
        repeatability=repeatability,
        private_terminal=private_terminal,
        receipt=receipt,
    )
    return receipt


def rescore_existing(
    *, manifest_path: Path, output_dir: Path
) -> dict[str, Any]:
    """Rescore immutable evidence; this route has no credential/provider access."""

    _require_report_output(output_dir)
    if not output_dir.is_dir():
        raise SemanticThreeTableQualificationError(
            "semantic_three_table_existing_evidence_missing"
        )
    manifest_bytes = manifest_path.read_bytes()
    frozen_manifest_bytes = (output_dir / "frozen_manifest.json").read_bytes()
    if manifest_bytes != frozen_manifest_bytes:
        raise SemanticThreeTableQualificationError(
            "semantic_three_table_existing_manifest_mismatch"
        )
    manifest = _json_object(manifest_bytes, "semantic_three_table_manifest_invalid")
    _validate_manifest(manifest)
    _contract_snapshot(manifest)
    reference_bytes = (output_dir / "source_reference.private.json").read_bytes()
    if _sha256_bytes(reference_bytes) != manifest["source_reference"]["sha256"]:
        raise SemanticThreeTableQualificationError(
            "semantic_three_table_source_reference_hash_mismatch"
        )
    reference = validate_source_reference(
        _json_object(reference_bytes, "semantic_three_table_source_reference_invalid")
    )
    previous_terminal = _json_object(
        (output_dir / "terminal.private.json").read_bytes(),
        "semantic_three_table_existing_terminal_invalid",
    )
    previous_by_key = {
        (item.get("table_id"), item.get("run")): item
        for item in previous_terminal.get("records") or []
        if isinstance(item, dict)
    }
    records: list[dict[str, Any]] = []
    for case in manifest["cases"]:
        table_id = case["table_id"]
        table_dir = output_dir / table_id
        if _sha256_bytes((table_dir / "crop.png").read_bytes()) != case["crop_sha256"]:
            raise SemanticThreeTableQualificationError(
                "semantic_three_table_existing_crop_hash_mismatch"
            )
        for run_name, provider in (
            ("gemini_run_a", "gemini"),
            ("gemini_run_b", "gemini"),
            ("openai_control", "openai"),
        ):
            previous = previous_by_key.get((table_id, run_name))
            if not isinstance(previous, dict):
                raise SemanticThreeTableQualificationError(
                    "semantic_three_table_existing_record_missing"
                )
            raw_text = (table_dir / f"{run_name}.raw.json").read_text(
                encoding="utf-8"
            )
            raw_provider_response = _json_value(
                (table_dir / f"{run_name}.adapter_response.private.json").read_bytes(),
                "semantic_three_table_existing_adapter_response_invalid",
            )
            parsed_response = _json_value(
                (table_dir / f"{run_name}.parsed.private.json").read_bytes(),
                "semantic_three_table_existing_parsed_response_invalid",
            )
            execution = _json_object(
                (table_dir / f"{run_name}.execution.safe.json").read_bytes(),
                "semantic_three_table_existing_execution_invalid",
            )
            if (
                hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
                != previous.get("raw_response_text_sha256")
                or sha256_json(raw_provider_response)
                != previous.get("raw_provider_response_sha256")
                or sha256_json(parsed_response)
                != previous.get("parsed_response_sha256")
            ):
                raise SemanticThreeTableQualificationError(
                    "semantic_three_table_existing_provider_evidence_changed"
                )
            records.append(
                {
                    "table_id": table_id,
                    "crop_sha256": case["crop_sha256"],
                    "provider": provider,
                    "run": run_name,
                    "decision_status": previous.get("decision_status"),
                    "execution": execution,
                    "raw_provider_response": raw_provider_response,
                    "raw_response_text": raw_text,
                    "parsed_response": parsed_response,
                }
            )
    _verify_execution_freeze(records, manifest)
    reference_by_crop = {
        table["crop_sha256"]: table for table in reference["tables"]
    }
    for record in records:
        record["score"] = score_semantic_response(
            reference_by_crop[record["crop_sha256"]],
            record["parsed_response"],
            raw_json_text=record["raw_response_text"],
        )
    records.sort(
        key=lambda item: (
            item["table_id"],
            ("gemini_run_a", "gemini_run_b", "openai_control").index(
                item["run"]
            ),
        )
    )
    repeatability = _repeatability(records)
    gate = evaluate_three_table_gate(
        [
            {
                "provider": record["provider"],
                "run": record["run"],
                "crop_sha256": record["crop_sha256"],
                "score": record["score"],
            }
            for record in records
        ],
        repeatability,
    )
    terminal = copy.deepcopy(previous_terminal)
    terminal.update(
        {
            "status": gate["status"],
            "records": [_terminal_record(record) for record in records],
            "repeatability": repeatability,
            "gate": gate,
            "rescored_at": datetime.now(timezone.utc).isoformat(),
            "scoring_policy": "literal_semantic_rows_v1",
            "combined_currency_amount_cell_allowed": True,
            "raw_provider_evidence_unchanged": True,
            "provider_executions_repeated_for_rescore": False,
        }
    )
    terminal.pop("terminal_hash", None)
    terminal["terminal_hash"] = sha256_json(terminal)
    receipt = _safe_receipt(terminal, records)
    for record in records:
        _write_json(
            output_dir
            / record["table_id"]
            / f"{record['run']}.score.private.json",
            record["score"],
        )
    for comparison in repeatability:
        _write_json(
            output_dir / comparison["table_id"] / "repeatability.safe.json",
            comparison,
        )
    _write_json(output_dir / "terminal.private.json", terminal)
    _write_json(output_dir / "receipt.safe.json", receipt)
    (output_dir / "ANALYSIS.report.md").write_text(
        _render_report(receipt), encoding="utf-8"
    )
    return receipt


def _validate_manifest(manifest: dict[str, Any]) -> None:
    if (
        manifest.get("schema_version") != MANIFEST_SCHEMA
        or manifest.get("frozen_before_provider_execution") is not True
        or manifest.get("semantic_contract", {}).get(
            "tuning_on_selected_tables_allowed"
        )
        is not False
        or manifest.get("execution_policy", {}).get("provider_merge") is not False
        or manifest.get("execution_policy", {}).get("provider_repair") is not False
        or manifest.get("execution_policy", {}).get("geometric_metrics") is not False
        or manifest.get("execution_policy", {}).get("gemini_master") is not True
        or manifest.get("execution_policy", {}).get(
            "openai_control_non_authoritative"
        )
        is not True
    ):
        raise SemanticThreeTableQualificationError(
            "semantic_three_table_manifest_policy_invalid"
        )
    cases = manifest.get("cases")
    if not isinstance(cases, list) or len(cases) != 3:
        raise SemanticThreeTableQualificationError(
            "semantic_three_table_manifest_case_count_invalid"
        )
    if len({case.get("crop_sha256") for case in cases}) != 3:
        raise SemanticThreeTableQualificationError(
            "semantic_three_table_manifest_crop_identity_invalid"
        )
    providers = manifest.get("provider_contracts") or {}
    if (
        (providers.get("gemini") or {}).get("executions") != 6
        or (providers.get("gemini") or {}).get("hidden_retry") is not False
        or (providers.get("openai") or {}).get("executions") != 3
        or (providers.get("openai") or {}).get("role") != "diagnostic_control"
        or (providers.get("openai") or {}).get("hidden_retry") is not False
    ):
        raise SemanticThreeTableQualificationError(
            "semantic_three_table_manifest_execution_count_invalid"
        )


def _verify_source_inputs(
    manifest: dict[str, Any],
    source_pack: Path,
    reference: dict[str, Any],
) -> None:
    references = {table["table_id"]: table for table in reference["tables"]}
    for case in manifest["cases"]:
        crop_bytes = (source_pack / case["crop_path"]).read_bytes()
        manual_bytes = (source_pack / case["manual_reference_path"]).read_bytes()
        candidate_manifest = case["candidate_manifest"]
        unhashed = copy.deepcopy(candidate_manifest)
        actual_manifest_hash = unhashed.pop("manifest_hash", None)
        if (
            _sha256_bytes(crop_bytes) != case["crop_sha256"]
            or case["crop_sha256"] != candidate_manifest.get("png_sha256")
            or len(crop_bytes) != candidate_manifest.get("png_bytes")
            or sha256_json(unhashed) != actual_manifest_hash
            or _sha256_bytes(manual_bytes) != case["manual_reference_sha256"]
            or references.get(case["table_id"], {}).get("crop_sha256")
            != case["crop_sha256"]
        ):
            raise SemanticThreeTableQualificationError(
                "semantic_three_table_frozen_source_input_mismatch"
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
    for key, value in snapshot.items():
        if expected.get(key) != value:
            raise SemanticThreeTableQualificationError(
                "semantic_three_table_frozen_contract_mismatch"
            )
    return snapshot


def _candidates(
    manifest: dict[str, Any], source_pack: Path
) -> list[dict[str, Any]]:
    result = []
    for case in manifest["cases"]:
        png_bytes = (source_pack / case["crop_path"]).read_bytes()
        result.append(
            {
                "manifest": copy.deepcopy(case["candidate_manifest"]),
                "private_png_base64": base64.b64encode(png_bytes).decode("ascii"),
            }
        )
    return result


def _collect_records(
    outcome: Any,
    *,
    gemini_run: str,
    openai_run: str | None,
) -> list[dict[str, Any]]:
    evidence_by_execution = {
        item.get("execution_hash"): item
        for item in outcome.private_provider_evidence
        if isinstance(item, dict)
    }
    result: list[dict[str, Any]] = []
    for decision in outcome.private_decisions:
        lineage = decision.get("source_lineage") or {}
        for execution in decision.get("executions") or []:
            provider = execution.get("provider")
            run_name = gemini_run if provider == "gemini" else openai_run
            if run_name is None:
                raise SemanticThreeTableQualificationError(
                    "semantic_three_table_unexpected_provider_execution"
                )
            evidence = evidence_by_execution.get(execution.get("execution_hash"))
            if not isinstance(evidence, dict):
                raise SemanticThreeTableQualificationError(
                    "semantic_three_table_private_evidence_missing"
                )
            result.append(
                {
                    "table_id": _table_id_for_crop(lineage.get("crop_sha256")),
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
    if len(records) != 9:
        raise SemanticThreeTableQualificationError(
            "semantic_three_table_execution_count_invalid"
        )
    expected_prompt = manifest["semantic_contract"]["prompt_sha256"]
    expected_schema = manifest["semantic_contract"]["schema_sha256"]
    models = {
        "gemini": manifest["provider_contracts"]["gemini"]["model_id"],
        "openai": manifest["provider_contracts"]["openai"]["model_id"],
    }
    for record in records:
        execution = record["execution"]
        if (
            execution.get("prompt_hash") != expected_prompt
            or execution.get("canonical_schema_hash") != expected_schema
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
            raise SemanticThreeTableQualificationError(
                "semantic_three_table_execution_freeze_invalid"
            )


def _repeatability(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for table_id in ("table_01", "table_02", "table_03"):
        by_run = {
            record["run"]: record
            for record in records
            if record["table_id"] == table_id and record["provider"] == "gemini"
        }
        if set(by_run) != {"gemini_run_a", "gemini_run_b"}:
            raise SemanticThreeTableQualificationError(
                "semantic_three_table_gemini_repeat_pair_invalid"
            )
        comparison = compare_material_repeatability(
            by_run["gemini_run_a"]["parsed_response"],
            by_run["gemini_run_b"]["parsed_response"],
        )
        comparison["table_id"] = table_id
        comparison["crop_sha256"] = by_run["gemini_run_a"]["crop_sha256"]
        result.append(comparison)
    return result


def _terminal_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "table_id": record["table_id"],
        "crop_sha256": record["crop_sha256"],
        "provider": record["provider"],
        "run": record["run"],
        "decision_status": record["decision_status"],
        "execution": copy.deepcopy(record["execution"]),
        "raw_response_text_sha256": (
            hashlib.sha256(record["raw_response_text"].encode("utf-8")).hexdigest()
            if isinstance(record["raw_response_text"], str)
            else None
        ),
        "raw_provider_response_sha256": sha256_json(
            record["raw_provider_response"]
        ),
        "parsed_response_sha256": sha256_json(record["parsed_response"]),
        "score": copy.deepcopy(record["score"]),
    }


def _safe_receipt(
    terminal: dict[str, Any], records: list[dict[str, Any]]
) -> dict[str, Any]:
    receipt = {
        "schema_version": SAFE_RECEIPT_SCHEMA,
        "status": terminal["status"],
        "experiment_id": terminal["experiment_id"],
        "started_at": terminal["started_at"],
        "ended_at": terminal["ended_at"],
        "manifest_sha256": terminal["manifest_sha256"],
        "source_reference_sha256": terminal["source_reference_sha256"],
        "frozen_contract": copy.deepcopy(terminal["frozen_contract"]),
        "execution_counts": {
            "frozen_tables": 3,
            "gemini": sum(record["provider"] == "gemini" for record in records),
            "openai_control": sum(
                record["provider"] == "openai" for record in records
            ),
        },
        "scores": [
            {
                "provider": record["provider"],
                "run": record["run"],
                **public_score_summary(record["score"]),
            }
            for record in records
        ],
        "repeatability": copy.deepcopy(terminal["repeatability"]),
        "gate": copy.deepcopy(terminal["gate"]),
        "crop_bytes_committed": False,
        "provider_output_values_committed": False,
        "private_evidence_retained": True,
        "provider_merge_performed": False,
        "provider_repair_performed": False,
        "geometric_metrics_used": False,
        "customer_data_in_safe_receipt": False,
        "customer_acceptance_claimed": False,
        "scoring_policy": "literal_semantic_rows_v1",
        "combined_currency_amount_cell_allowed": True,
        "provider_executions_repeated_for_scoring": False,
    }
    receipt["receipt_hash"] = sha256_json(receipt)
    return receipt


def _write_evidence_package(
    *,
    output_dir: Path,
    source_pack: Path,
    manifest: dict[str, Any],
    manifest_bytes: bytes,
    reference_bytes: bytes,
    records: list[dict[str, Any]],
    repeatability: list[dict[str, Any]],
    private_terminal: dict[str, Any],
    receipt: dict[str, Any],
) -> None:
    (output_dir / "frozen_manifest.json").write_bytes(manifest_bytes)
    (output_dir / "source_reference.private.json").write_bytes(reference_bytes)
    for case in manifest["cases"]:
        table_dir = output_dir / case["table_id"]
        table_dir.mkdir()
        shutil.copyfile(source_pack / case["crop_path"], table_dir / "crop.png")
        shutil.copyfile(
            source_pack / case["manual_reference_path"],
            table_dir / "manual_reference.md",
        )
        _write_json(table_dir / "crop.manifest.json", case["candidate_manifest"])
    for record in records:
        table_dir = output_dir / record["table_id"]
        prefix = record["run"]
        raw_text = record["raw_response_text"]
        (table_dir / f"{prefix}.raw.json").write_text(
            raw_text if isinstance(raw_text, str) else "null",
            encoding="utf-8",
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
            table_dir / f"{prefix}.execution.safe.json",
            record["execution"],
        )
        _write_json(
            table_dir / f"{prefix}.score.private.json",
            record["score"],
        )
    for comparison in repeatability:
        _write_json(
            output_dir / comparison["table_id"] / "repeatability.safe.json",
            comparison,
        )
    _write_json(output_dir / "terminal.private.json", private_terminal)
    _write_json(output_dir / "receipt.safe.json", receipt)
    (output_dir / "ANALYSIS.report.md").write_text(
        _render_report(receipt), encoding="utf-8"
    )
    _verify_written_crops(output_dir, manifest)


def _render_report(receipt: dict[str, Any]) -> str:
    lines = [
        "# Broker Reports — frozen semantic three-table hypothesis",
        "",
        f"Status: `{receipt['status']}`",
        "",
        "The private package contains the three byte-identical crops, exact raw "
        "provider JSON, execution metadata, source-only references and scores. "
        "The required gate applies to the six Gemini master executions; the three "
        "OpenAI executions are non-authoritative controls.",
        "",
        "| Table | Provider run | JSON | Labels | Amounts | Markers | Binding | "
        "Hallucinations | Corrections |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for score in receipt["scores"]:
        hallucinations = (
            score["hallucinated_label_count"]
            + score["hallucinated_amount_count"]
            + score["hallucinated_marker_count"]
        )
        lines.append(
            "| {table} | {provider}/{run} | {json_ok} | {labels:.1%} | "
            "{amounts:.1%} | {markers:.1%} | {binding:.1%} | {hallucinations} | "
            "{corrections} |".format(
                table=score["table_id"],
                provider=score["provider"],
                run=score["run"],
                json_ok="yes" if score["json_parse_success"] else "no",
                labels=score["label_completeness"]["rate"],
                amounts=score["amount_fidelity"]["rate"],
                markers=score["currency_sign_parenthesis_fidelity"]["rate"],
                binding=score["row_value_binding"]["rate"],
                hallucinations=hallucinations,
                corrections=score["manual_correction_count"],
            )
        )
    lines.extend(
        [
            "",
            "Geometry, spans, physical coverage and provider consensus were not "
            "used as success metrics. No response was retried, merged or repaired.",
            "",
        ]
    )
    return "\n".join(lines)


def _openwebui_request(env_path: Path) -> Any:
    env = _read_env(env_path)
    host = str(
        env.get("OPENWEBUI_HOST")
        or env.get("OPENWEBUI_BASE_URL")
        or env.get("BASE_URL")
        or ""
    ).rstrip("/")
    email = str(
        env.get("WEBUI_ADMIN_EMAIL")
        or env.get("OPENWEBUI_ADMIN_EMAIL")
        or env.get("ADMIN_EMAIL")
        or ""
    )
    password = str(
        env.get("WEBUI_ADMIN_PASSWORD")
        or env.get("OPENWEBUI_ADMIN_PASSWORD")
        or env.get("ADMIN_PASSWORD")
        or ""
    )
    if not all((host, email, password)):
        raise SemanticThreeTableQualificationError(
            "semantic_three_table_openwebui_credentials_missing"
        )
    base_url = host if host.startswith(("http://", "https://")) else f"https://{host}"
    session = requests.Session()
    response = session.post(
        base_url + "/api/v1/auths/signin",
        json={"email": email, "password": password},
        timeout=30,
    )
    response.raise_for_status()
    token = str((response.json() or {}).get("token") or "")
    if not token:
        raise SemanticThreeTableQualificationError(
            "semantic_three_table_openwebui_token_missing"
        )
    session.headers.update({"Authorization": f"Bearer {token}"})
    config_response = session.get(base_url + "/openai/config", timeout=30)
    config_response.raise_for_status()
    config = config_response.json()
    if not isinstance(config, dict):
        raise SemanticThreeTableQualificationError(
            "semantic_three_table_openwebui_config_invalid"
        )
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                config=SimpleNamespace(
                    OPENAI_API_BASE_URLS=config.get("OPENAI_API_BASE_URLS"),
                    OPENAI_API_KEYS=config.get("OPENAI_API_KEYS"),
                    OPENAI_API_CONFIGS=config.get("OPENAI_API_CONFIGS"),
                )
            )
        )
    )


def _read_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise SemanticThreeTableQualificationError(
            "semantic_three_table_env_file_missing"
        )
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _transport_source_hashes() -> dict[str, str]:
    paths = {
        "runtime": SERVICE_ROOT / "broker_reports_gate1" / "pdf_dual_vlm_runtime.py",
        "provider_factory": (
            SERVICE_ROOT / "broker_reports_gate1" / "pdf_dual_vlm_fact_providers.py"
        ),
        "gemini_adapter": (
            SERVICE_ROOT / "broker_reports_gate1" / "pdf_grid_experiment_provider.py"
        ),
        "credential_resolver": (
            SERVICE_ROOT / "broker_reports_gate1" / "gate2_provider_adapters.py"
        ),
    }
    return {name: _sha256_bytes(path.read_bytes()) for name, path in paths.items()}


def _verify_written_crops(output_dir: Path, manifest: dict[str, Any]) -> None:
    if any(
        _sha256_bytes((output_dir / case["table_id"] / "crop.png").read_bytes())
        != case["crop_sha256"]
        for case in manifest["cases"]
    ):
        raise SemanticThreeTableQualificationError(
            "semantic_three_table_evidence_crop_copy_mismatch"
        )


def _require_report_output(path: Path) -> None:
    approved = (REPO_ROOT / "docs" / "reports").resolve()
    try:
        path.relative_to(approved)
    except ValueError as exc:
        raise SemanticThreeTableQualificationError(
            "semantic_three_table_output_routing_invalid"
        ) from exc


def _require_fresh_directory(path: Path) -> None:
    if path.exists():
        raise SemanticThreeTableQualificationError(
            "semantic_three_table_fresh_output_required"
        )


def _table_id_for_crop(value: Any) -> str:
    mapping = {
        "3ceb1b9fdc4ab135a93f06df31fc9765e13b7096e2ab918c6bd73de36edc1496": "table_01",
        "3555dee6305a121eab692bc22ea1ccf4b21bd6c544bb6c524bdbc27ffc7fc7e8": "table_02",
        "c58acddbd4fe1b458d4141fca46b0d04c37a1fd504521f404399c7c7914039ef": "table_03",
    }
    try:
        return mapping[value]
    except (KeyError, TypeError) as exc:
        raise SemanticThreeTableQualificationError(
            "semantic_three_table_execution_crop_unknown"
        ) from exc


def _json_object(payload: bytes, failure: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise SemanticThreeTableQualificationError(failure) from exc
    if not isinstance(value, dict):
        raise SemanticThreeTableQualificationError(failure)
    return value


def _json_value(payload: bytes, failure: str) -> Any:
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise SemanticThreeTableQualificationError(failure) from exc


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
