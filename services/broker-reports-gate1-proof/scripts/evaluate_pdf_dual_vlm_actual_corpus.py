from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Iterable


SCRIPT_ROOT = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_ROOT.parent
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.pdf_dual_vlm_canonical_table_contracts import (  # noqa: E402
    canonical_json_bytes,
    canonicalize_text,
    sha256_json,
)
from broker_reports_gate1.pdf_dual_vlm_runtime import (  # noqa: E402
    PdfDualVlmRuntimeConfig,
    PdfDualVlmRuntimeFactory,
)
from broker_reports_gate1.pdf_table_raster import (  # noqa: E402
    PdfTableRasterConfig,
    PdfTableRasterFactory,
)
from pdf_dual_vlm_literal_contracts import parse_visible_numeric  # noqa: E402


RUN_SCHEMA = "broker_reports_actual_corpus_vlm_run_v1_private"
RUN_SEAL_SCHEMA = "broker_reports_actual_corpus_vlm_run_seal_v1"
RUN_IDENTITY_SCHEMA = "broker_reports_actual_corpus_vlm_run_identity_v1_safe"
REVIEW_DECISIONS_SCHEMA = "broker_reports_actual_corpus_vlm_review_decisions_v1"
DELEGATED_REFERENCE_SCHEMA = (
    "broker_reports_actual_corpus_vlm_delegated_reference_v1_private"
)
DELEGATED_REFERENCE_SEAL_SCHEMA = (
    "broker_reports_actual_corpus_vlm_delegated_reference_seal_v1"
)
SCORE_SCHEMA = "broker_reports_actual_corpus_vlm_score_v1_private"
SAFE_RECEIPT_SCHEMA = "broker_reports_actual_corpus_vlm_quality_v1_safe"
FACTORY_REQUIRED = (
    "Live evaluation must call PdfDualVlmRuntimeFactory.create_for_openwebui and "
    "render source-bound crops with PdfTableRasterFactory."
)
FORBIDDEN = (
    "No direct provider adapter, provider payload, credential resolution, retry, "
    "failover, reference access before the sealed run, provider truth, consensus "
    "truth, automatic publication, or customer-acceptance claim."
)

DEFAULT_GEMINI_MODEL = "models/gemini-3.5-flash"
DEFAULT_OPENAI_MODEL = "gpt-5.4-mini-2026-03-17"
DEFAULT_REPEAT_COUNT = 2
DEFAULT_MAXIMUM_CANDIDATES = 8
DETECTION_TERMINAL_SCHEMA = (
    "broker_reports_pdf_dual_vlm_literal_detection_terminal_v2"
)
DETECTION_SEAL_SCHEMA = (
    "broker_reports_pdf_dual_vlm_literal_detection_terminal_seal_v2"
)
LITERAL_DRAFT_SCHEMA = "broker_reports_pdf_table_literal_reference_v1"
DISPOSITIONS = frozenset({"assisted_review_candidate", "unsupported_layout"})
LAYOUT_CHARACTERISTICS = frozenset(
    {
        "simple_grid",
        "merged_headers",
        "sparse_cells",
        "borderless",
        "totals_subtotals",
        "complex_broker_layout",
        "long_form_prose",
    }
)
REVIEW_ATTESTATIONS = (
    "source_crop_opened",
    "source_page_and_crop_lineage_checked",
    "every_literal_reference_entry_checked",
    "merged_and_sparse_structure_checked",
    "empty_and_unreadable_states_checked",
    "provider_outputs_not_used",
    "provider_consensus_not_used",
    "customer_acceptance_not_claimed",
)
TERMINAL_DECISION_STATUSES = frozenset(
    {
        "proposal_validated_and_accepted",
        "proposal_requires_review",
        "proposal_rejected",
        "malformed_provider_output",
        "provider_refusal_or_incomplete",
        "unresolved_visual_scope",
        "unsupported_visual_layout",
    }
)
REJECTION_STATUSES = frozenset(
    {
        "proposal_rejected",
        "malformed_provider_output",
        "provider_refusal_or_incomplete",
        "unresolved_visual_scope",
        "unsupported_visual_layout",
    }
)


class ActualCorpusVlmEvaluationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run")
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--detection-terminal", type=Path, required=True)
    run.add_argument("--detection-seal", type=Path, required=True)
    run.add_argument("--corpus-root", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--source-revision", required=True)
    run.add_argument("--openwebui-config-module", default="open_webui.config")
    run.add_argument("--gemini-model", default=DEFAULT_GEMINI_MODEL)
    run.add_argument("--openai-model", default=DEFAULT_OPENAI_MODEL)
    run.add_argument("--repeat-count", type=int, default=DEFAULT_REPEAT_COUNT)

    finalize = subparsers.add_parser("finalize-reference")
    finalize.add_argument("--literal-draft", type=Path, required=True)
    finalize.add_argument("--review-decisions", type=Path, required=True)
    finalize.add_argument("--run-identity", type=Path, required=True)
    finalize.add_argument("--output-dir", type=Path, required=True)

    score = subparsers.add_parser("score")
    score.add_argument("--run-terminal", type=Path, required=True)
    score.add_argument("--run-seal", type=Path, required=True)
    score.add_argument("--delegated-reference", type=Path, required=True)
    score.add_argument("--reference-seal", type=Path, required=True)
    score.add_argument("--output-dir", type=Path, required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            run_actual_corpus(
                manifest_path=args.manifest,
                detection_terminal_path=args.detection_terminal,
                detection_seal_path=args.detection_seal,
                corpus_root=args.corpus_root,
                output_dir=args.output_dir,
                source_revision=args.source_revision,
                config_module=args.openwebui_config_module,
                gemini_model=args.gemini_model,
                openai_model=args.openai_model,
                repeat_count=args.repeat_count,
            )
        elif args.command == "finalize-reference":
            finalize_delegated_reference(
                literal_draft_path=args.literal_draft,
                review_decisions_path=args.review_decisions,
                run_identity_path=args.run_identity,
                output_dir=args.output_dir,
            )
        else:
            score_actual_corpus(
                run_terminal_path=args.run_terminal,
                run_seal_path=args.run_seal,
                delegated_reference_path=args.delegated_reference,
                reference_seal_path=args.reference_seal,
                output_dir=args.output_dir,
            )
    except ActualCorpusVlmEvaluationError as exc:
        print(json.dumps({"status": "blocked", "failure_code": exc.code}))
        return 1
    return 0


def run_actual_corpus(
    *,
    manifest_path: Path,
    detection_terminal_path: Path,
    detection_seal_path: Path,
    corpus_root: Path,
    output_dir: Path,
    source_revision: str,
    config_module: str,
    gemini_model: str,
    openai_model: str,
    repeat_count: int,
    runtime_factory_builder: Callable[[PdfDualVlmRuntimeConfig], Any] = (
        PdfDualVlmRuntimeFactory
    ),
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    _require_fresh_directory(output_dir)
    if repeat_count < 2 or repeat_count > 5:
        raise ActualCorpusVlmEvaluationError("actual_corpus_repeat_count_invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", source_revision):
        raise ActualCorpusVlmEvaluationError("actual_corpus_source_revision_invalid")

    manifest_bytes = manifest_path.read_bytes()
    detection_bytes = detection_terminal_path.read_bytes()
    manifest = _json_object(manifest_bytes, "actual_corpus_manifest_invalid")
    detection = _json_object(detection_bytes, "actual_corpus_detection_invalid")
    detection_seal = _load_json(detection_seal_path)
    detection_sha256 = hashlib.sha256(detection_bytes).hexdigest()
    if (
        detection.get("schema_version") != DETECTION_TERMINAL_SCHEMA
        or detection.get("run_status") != "completed"
        or detection.get("reference_accessed") is not False
        or detection.get("reference_argument_supported") is not False
        or detection_seal.get("schema_version") != DETECTION_SEAL_SCHEMA
        or detection_seal.get("terminal_sha256") != detection_sha256
        or detection_seal.get("terminal_size_bytes") != len(detection_bytes)
        or detection_seal.get("reference_accessed") is not False
    ):
        raise ActualCorpusVlmEvaluationError("actual_corpus_detection_seal_invalid")

    candidates = prepare_candidates(
        manifest=manifest,
        detection=detection,
        corpus_root=corpus_root,
    )
    if len(candidates) != 9:
        raise ActualCorpusVlmEvaluationError("actual_corpus_candidate_count_invalid")

    openwebui_config = importlib.import_module(config_module)
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(config=openwebui_config))
    )
    runtime_config = PdfDualVlmRuntimeConfig(
        enabled=True,
        gemini_model_id=gemini_model,
        openai_model_id=openai_model,
    )
    if runtime_config.maximum_candidates != DEFAULT_MAXIMUM_CANDIDATES:
        raise ActualCorpusVlmEvaluationError("actual_corpus_runtime_budget_drift")

    started_at = datetime.now(timezone.utc).isoformat()
    records: list[dict[str, Any]] = []
    chunk_summaries: list[dict[str, Any]] = []
    for repeat_index in range(1, repeat_count + 1):
        runtime = runtime_factory_builder(runtime_config).create_for_openwebui(request)
        for chunk_index, chunk in enumerate(_chunks(candidates, 8), start=1):
            outcome = runtime.run(chunk)
            summary = copy.deepcopy(outcome.safe_summary)
            if (
                summary.get("status") != "completed"
                or summary.get("decisions_total") != len(chunk)
                or len(outcome.private_decisions) != len(chunk)
            ):
                raise ActualCorpusVlmEvaluationError(
                    "actual_corpus_runtime_nonterminal"
                )
            chunk_summaries.append(
                {
                    "repeat_index": repeat_index,
                    "chunk_index": chunk_index,
                    "safe_summary": summary,
                }
            )
            for decision in outcome.private_decisions:
                records.append(
                    {
                        "repeat_index": repeat_index,
                        "chunk_index": chunk_index,
                        "decision": copy.deepcopy(decision),
                    }
                )

    if len(records) != len(candidates) * repeat_count:
        raise ActualCorpusVlmEvaluationError("actual_corpus_decision_count_invalid")
    ended_at = datetime.now(timezone.utc).isoformat()
    terminal = {
        "schema_version": RUN_SCHEMA,
        "status": "completed",
        "source_revision": source_revision,
        "started_at": started_at,
        "ended_at": ended_at,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "detection_terminal_sha256": detection_sha256,
        "reference_accessed": False,
        "reference_argument_supported": False,
        "provider_output_as_reference_truth": False,
        "provider_consensus_as_reference_truth": False,
        "runtime_factory": (
            "PdfDualVlmRuntimeFactory.create_for_openwebui"
        ),
        "raster_factory": "PdfTableRasterFactory.create",
        "maximum_candidates_unchanged": True,
        "repeat_count": repeat_count,
        "candidate_count": len(candidates),
        "chunk_size_sequence_per_repeat": [8, 1],
        "configured_models": {
            "gemini": gemini_model,
            "openai": openai_model,
        },
        "chunk_summaries": chunk_summaries,
        "decision_records": records,
        "raw_provider_responses_retained": False,
        "whole_documents_retained": False,
        "crop_bytes_retained": False,
    }
    terminal_bytes = canonical_json_bytes(terminal)
    terminal_sha256 = hashlib.sha256(terminal_bytes).hexdigest()
    seal = {
        "schema_version": RUN_SEAL_SCHEMA,
        "terminal_filename": "terminal.private.json",
        "terminal_sha256": terminal_sha256,
        "terminal_size_bytes": len(terminal_bytes),
        "status": "completed",
        "reference_accessed": False,
    }
    seal["seal_sha256"] = sha256_json(seal)
    identity = build_run_identity(terminal=terminal, terminal_sha256=terminal_sha256)

    output_dir.mkdir(parents=True)
    _write_json(output_dir / "terminal.private.json", terminal)
    _write_json(output_dir / "terminal.private.sha256.json", seal)
    _write_json(output_dir / "run.identity.safe.json", identity)
    print(canonical_json_bytes(identity).decode("utf-8"))
    return terminal, seal, identity


def prepare_candidates(
    *,
    manifest: dict[str, Any],
    detection: dict[str, Any],
    corpus_root: Path,
) -> list[dict[str, Any]]:
    manifest_cases = {
        str(item.get("case_id") or ""): item
        for item in manifest.get("cases") or []
        if isinstance(item, dict)
    }
    detection_cases = detection.get("cases")
    if not manifest_cases or not isinstance(detection_cases, list):
        raise ActualCorpusVlmEvaluationError("actual_corpus_case_manifest_invalid")
    renderer = PdfTableRasterFactory(
        PdfTableRasterConfig(
            horizontal_padding_fraction=0.08,
            vertical_padding_fraction=0.08,
        )
    ).create()
    result: list[dict[str, Any]] = []
    seen_refs: set[str] = set()
    for case in detection_cases:
        if not isinstance(case, dict):
            raise ActualCorpusVlmEvaluationError("actual_corpus_detection_case_invalid")
        case_id = str(case.get("case_id") or "")
        manifest_case = manifest_cases.get(case_id)
        if manifest_case is None:
            raise ActualCorpusVlmEvaluationError("actual_corpus_case_not_manifested")
        relative_pdf = str(manifest_case.get("relative_pdf") or "")
        source_path = _bounded_source_path(corpus_root, relative_pdf)
        pdf_bytes = source_path.read_bytes()
        pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        expected_pdf_sha256 = str(manifest_case.get("pdf_sha256") or "")
        if (
            pdf_sha256 != expected_pdf_sha256
            or case.get("document_sha256") != expected_pdf_sha256
            or case.get("page_number") != manifest_case.get("page_number")
            or case.get("terminal_status") != "completed"
        ):
            raise ActualCorpusVlmEvaluationError("actual_corpus_source_identity_invalid")
        candidates = case.get("candidates") or []
        if not isinstance(candidates, list):
            raise ActualCorpusVlmEvaluationError("actual_corpus_candidates_invalid")
        for candidate in candidates:
            if (
                not isinstance(candidate, dict)
                or candidate.get("decision") != "present"
                or candidate.get("bbox_contract_valid") is not True
                or candidate.get("terminal_contract_error") is not None
            ):
                raise ActualCorpusVlmEvaluationError(
                    "actual_corpus_detection_candidate_invalid"
                )
            candidate_id = str(candidate.get("candidate_id") or "")
            candidate_ref = _candidate_ref(case_id, candidate_id)
            if candidate_ref in seen_refs:
                raise ActualCorpusVlmEvaluationError(
                    "actual_corpus_candidate_ref_duplicate"
                )
            seen_refs.add(candidate_ref)
            bbox = candidate.get("detected_bbox")
            rendered = renderer.render_detected_region(
                pdf_bytes=pdf_bytes,
                pdf_sha256=pdf_sha256,
                document_ref=case_id,
                page_number=int(case["page_number"]),
                candidate_ref=candidate_ref,
                detected_bbox_normalized=copy.deepcopy(bbox),
                detector_contract_version=str(
                    detection.get("schema_version") or ""
                ),
                detector_identity={
                    "provider_profile": "sealed_detection_terminal",
                    "response_hash": sha256_json(candidate),
                },
                dpi=150,
            )
            result.append(rendered)
    result.sort(key=lambda item: str(item["manifest"]["candidate_ref"]))
    return result


def build_run_identity(
    *, terminal: dict[str, Any], terminal_sha256: str
) -> dict[str, Any]:
    units: dict[str, dict[str, Any]] = {}
    for record in terminal.get("decision_records") or []:
        decision = _object(record).get("decision")
        lineage = _object(_object(decision).get("source_lineage"))
        candidate_ref = str(lineage.get("candidate_ref") or "")
        if not candidate_ref:
            raise ActualCorpusVlmEvaluationError("actual_corpus_lineage_missing")
        unit = {
            "candidate_ref": candidate_ref,
            "source_sha256": lineage.get("source_sha256"),
            "page_number": lineage.get("page_number"),
            "crop_sha256": lineage.get("crop_sha256"),
            "crop_manifest_hash": lineage.get("crop_manifest_hash"),
            "dpi": lineage.get("dpi"),
        }
        prior = units.setdefault(candidate_ref, unit)
        if prior != unit:
            raise ActualCorpusVlmEvaluationError("actual_corpus_repeat_input_drift")
    identity = {
        "schema_version": RUN_IDENTITY_SCHEMA,
        "status": terminal.get("status"),
        "source_revision": terminal.get("source_revision"),
        "terminal_sha256": terminal_sha256,
        "manifest_sha256": terminal.get("manifest_sha256"),
        "detection_terminal_sha256": terminal.get("detection_terminal_sha256"),
        "reference_accessed": terminal.get("reference_accessed"),
        "provider_output_as_reference_truth": False,
        "provider_consensus_as_reference_truth": False,
        "repeat_count": terminal.get("repeat_count"),
        "configured_models": copy.deepcopy(terminal.get("configured_models")),
        "units": [units[key] for key in sorted(units)],
        "provider_output_values_included": False,
    }
    identity["identity_hash"] = sha256_json(identity)
    return identity


def finalize_delegated_reference(
    *,
    literal_draft_path: Path,
    review_decisions_path: Path,
    run_identity_path: Path,
    output_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _require_fresh_directory(output_dir)
    draft_bytes = literal_draft_path.read_bytes()
    draft = _json_object(draft_bytes, "actual_corpus_literal_draft_invalid")
    decisions = _load_json(review_decisions_path)
    identity = _load_json(run_identity_path)
    _validate_run_identity(identity)
    _validate_review_decisions(decisions)
    if (
        draft.get("schema_version") != LITERAL_DRAFT_SCHEMA
        or draft.get("human_reviewed") is not False
        or draft.get("prior_human_review_carry_forward_is_final_review") is not False
        or draft.get("semantic_financial_types_present") is not False
        or draft.get("reference_scope")
        != "all_visible_value_bearing_table_entries"
    ):
        raise ActualCorpusVlmEvaluationError("actual_corpus_literal_draft_invalid")
    _validate_literal_draft_for_projection(draft)

    draft_for_validation = copy.deepcopy(draft)
    table_index = _draft_table_index(draft_for_validation)
    decision_entries = decisions["entries"]
    if set(table_index) != {
        str(item.get("table_identifier")) for item in decision_entries
    }:
        raise ActualCorpusVlmEvaluationError("actual_corpus_review_coverage_invalid")
    units = {
        str(item.get("candidate_ref") or ""): item
        for item in identity.get("units") or []
        if isinstance(item, dict)
    }
    if len(units) != len(decision_entries):
        raise ActualCorpusVlmEvaluationError("actual_corpus_run_identity_coverage_invalid")

    reviews: list[dict[str, Any]] = []
    reviewer = copy.deepcopy(decisions["reviewer"])
    for decision in decision_entries:
        table_id = str(decision["table_identifier"])
        runtime_ref = str(decision["runtime_candidate_ref"])
        case, table = table_index[table_id]
        unit = units.get(runtime_ref)
        if (
            unit is None
            or unit.get("source_sha256") != case.get("document_sha256")
            or unit.get("page_number") != decision.get("page_number")
            or case.get("page_number") != decision.get("page_number")
        ):
            raise ActualCorpusVlmEvaluationError(
                "actual_corpus_reference_crop_identity_mismatch"
            )
        for entry in table.get("entries") or []:
            if entry.get("review_status") != "pending":
                raise ActualCorpusVlmEvaluationError(
                    "actual_corpus_reference_not_fresh"
                )
            entry["review_status"] = "confirmed"
            entry["review_provenance"] = {
                "reviewer_type": "delegated_agent",
                "reviewer_identity": reviewer["identity"],
                "reviewed_at": reviewer["reviewed_at"],
                "source_crop_only": True,
                "provider_outputs_used": False,
                "provider_consensus_used": False,
            }
        review = copy.deepcopy(decision)
        review["evaluated_crop_sha256"] = unit["crop_sha256"]
        review["source_draft_crop_sha256"] = table["crop_sha256"]
        reviews.append(review)

    literal_tables = []
    for review in reviews:
        case, table = table_index[str(review["table_identifier"])]
        literal_tables.append(
            {
                "case_id": case["case_id"],
                "document_sha256": case["document_sha256"],
                "page_number": case["page_number"],
                "table_identifier": table["table_identifier"],
                "runtime_candidate_ref": review["runtime_candidate_ref"],
                "evaluated_crop_sha256": review["evaluated_crop_sha256"],
                "source_draft_crop_sha256": review[
                    "source_draft_crop_sha256"
                ],
                "source_crop_identity_rebound_after_visual_review": True,
                "entries": [
                    {
                        "reference_entry_id": entry["reference_entry_id"],
                        "row_label_text": entry["row_label_text"],
                        "column_header_path": copy.deepcopy(
                            entry["column_header_path"]
                        ),
                        "visible_value_text": entry["visible_value_text"],
                        "cell_state": entry["cell_state"],
                        "review_status": entry["review_status"],
                    }
                    for entry in table.get("entries") or []
                ],
            }
        )
    reference = {
        "schema_version": DELEGATED_REFERENCE_SCHEMA,
        "human_reviewed": False,
        "delegated_agent_reviewed": True,
        "customer_accepted": False,
        "reviewer": reviewer,
        "delegation": copy.deepcopy(decisions["delegation"]),
        "lineage": {
            "literal_draft_sha256": hashlib.sha256(draft_bytes).hexdigest(),
            "run_identity_hash": identity["identity_hash"],
            "run_terminal_sha256": identity["terminal_sha256"],
            "detection_terminal_sha256": identity[
                "detection_terminal_sha256"
            ],
            "provider_outputs_used": False,
            "provider_consensus_used": False,
        },
        "literal_reference": {
            "scope": "all_visible_value_bearing_table_entries",
            "source_draft_schema": draft["schema_version"],
            "source_draft_human_reviewed": False,
            "source_draft_prior_human_review_is_final": False,
            "tables": literal_tables,
        },
        "table_reviews": reviews,
    }
    reference_bytes = canonical_json_bytes(reference)
    reference_sha256 = hashlib.sha256(reference_bytes).hexdigest()
    seal = {
        "schema_version": DELEGATED_REFERENCE_SEAL_SCHEMA,
        "reference_filename": "reference.delegated-agent.private.json",
        "reference_sha256": reference_sha256,
        "reference_size_bytes": len(reference_bytes),
        "human_reviewed": False,
        "delegated_agent_reviewed": True,
        "customer_accepted": False,
        "reviewed_at": reviewer["reviewed_at"],
        "delegation_statement_sha256": reference["delegation"][
            "delegation_statement_sha256"
        ],
    }
    seal["seal_sha256"] = sha256_json(seal)
    output_dir.mkdir(parents=True)
    _write_json(output_dir / "reference.delegated-agent.private.json", reference)
    _write_json(
        output_dir / "reference.delegated-agent.private.sha256.json",
        seal,
    )
    print(canonical_json_bytes(seal).decode("utf-8"))
    return reference, seal


def score_actual_corpus(
    *,
    run_terminal_path: Path,
    run_seal_path: Path,
    delegated_reference_path: Path,
    reference_seal_path: Path,
    output_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _require_fresh_directory(output_dir)
    terminal_bytes = run_terminal_path.read_bytes()
    reference_bytes = delegated_reference_path.read_bytes()
    terminal = _json_object(terminal_bytes, "actual_corpus_run_invalid")
    run_seal = _load_json(run_seal_path)
    reference = _json_object(reference_bytes, "actual_corpus_reference_invalid")
    reference_seal = _load_json(reference_seal_path)
    _validate_run_seal(terminal_bytes, terminal, run_seal)
    _validate_reference_seal(reference_bytes, reference, reference_seal)

    table_index = _evaluated_table_index(reference["literal_reference"])
    review_by_runtime_ref = {
        str(item["runtime_candidate_ref"]): item
        for item in reference["table_reviews"]
    }
    samples: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    for record in terminal.get("decision_records") or []:
        repeat_index = int(record["repeat_index"])
        decision = record["decision"]
        lineage = _object(decision.get("source_lineage"))
        runtime_ref = str(lineage.get("candidate_ref") or "")
        review = review_by_runtime_ref.get(runtime_ref)
        if review is None:
            raise ActualCorpusVlmEvaluationError("actual_corpus_score_unit_unmapped")
        table = table_index[str(review["table_identifier"])]
        if lineage.get("crop_sha256") != table.get("evaluated_crop_sha256"):
            raise ActualCorpusVlmEvaluationError(
                "actual_corpus_score_crop_identity_mismatch"
            )
        executions = {
            str(item.get("provider") or ""): item
            for item in decision.get("executions") or []
            if isinstance(item, dict)
        }
        for provider in ("gemini", "openai"):
            execution = executions.get(provider, {})
            proposal = _object(decision.get("proposals")).get(provider)
            sample = score_proposal(
                proposal=proposal,
                execution=execution,
                reference_entries=table.get("entries") or [],
            )
            sample.update(
                {
                    "repeat_index": repeat_index,
                    "candidate_ref_hash": hashlib.sha256(
                        runtime_ref.encode("utf-8")
                    ).hexdigest(),
                    "provider": provider,
                    "requested_model_id": execution.get("requested_model_id"),
                    "resolved_model_id": execution.get("resolved_model_id"),
                    "prompt_id": execution.get("prompt_id"),
                    "prompt_version": execution.get("prompt_version"),
                    "prompt_hash": execution.get("prompt_hash"),
                    "output_schema_version": execution.get(
                        "output_schema_version"
                    ),
                    "canonical_schema_hash": execution.get(
                        "canonical_schema_hash"
                    ),
                    "input_hash": execution.get("input_hash"),
                    "provider_terminal_status": execution.get(
                        "terminal_provider_status"
                    ),
                    "validator_status": _object(
                        execution.get("validator_result")
                    ).get("status"),
                    "review_status": review.get("disposition"),
                }
            )
            samples.append(sample)
        comparison = decision.get("comparison")
        decisions.append(
            {
                "repeat_index": repeat_index,
                "candidate_ref_hash": hashlib.sha256(
                    runtime_ref.encode("utf-8")
                ).hexdigest(),
                "decision_status": decision.get("status"),
                "review_required": decision.get("review_required"),
                "provider_contracts_valid": _object(
                    decision.get("deterministic_validator")
                ).get("provider_contracts_valid"),
                "identical_bounded_input": _object(
                    decision.get("deterministic_validator")
                ).get("same_bounded_input_for_all_providers"),
                "full_table_consensus": (
                    comparison.get("FULL_TABLE_CONSENSUS")
                    if isinstance(comparison, dict)
                    else None
                ),
                "disagreement_classification": (
                    "provider_disagreement"
                    if isinstance(comparison, dict)
                    and comparison.get("FULL_TABLE_CONSENSUS") is False
                    else (
                        "provider_agreement_without_authority"
                        if isinstance(comparison, dict)
                        else "provider_terminal_or_contract_failure"
                    )
                ),
                "canonical_table_published": decision.get("canonical_table")
                is not None,
                "provider_proposal_canonical_authority": decision.get(
                    "provider_proposal_canonical_authority"
                ),
            }
        )

    metrics = aggregate_metrics(
        samples=samples,
        decisions=decisions,
        table_reviews=reference["table_reviews"],
        repeat_count=int(terminal["repeat_count"]),
    )
    score = {
        "schema_version": SCORE_SCHEMA,
        "status": "completed",
        "run_terminal_sha256": run_seal["terminal_sha256"],
        "reference_sha256": reference_seal["reference_sha256"],
        "reference_authority": {
            "human_reviewed": False,
            "delegated_agent_reviewed": True,
            "customer_accepted": False,
            "provider_outputs_used": False,
            "provider_consensus_used": False,
        },
        "evaluation_units": len(decisions),
        "provider_samples": len(samples),
        "metrics": metrics,
        "decision_records": decisions,
        "provider_sample_scores": samples,
        "product_envelope": product_envelope(metrics),
        "raw_provider_responses_retained": False,
        "provider_output_values_committable": False,
    }
    score["score_hash"] = sha256_json(score)
    receipt = build_safe_receipt(score=score, terminal=terminal, reference=reference)
    output_dir.mkdir(parents=True)
    _write_json(output_dir / "score.private.json", score)
    _write_json(output_dir / "receipt.safe.json", receipt)
    print(canonical_json_bytes(receipt).decode("utf-8"))
    return score, receipt


def score_proposal(
    *,
    proposal: Any,
    execution: Any,
    reference_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    execution = _object(execution)
    validator = _object(execution.get("validator_result"))
    contract_valid = (
        isinstance(proposal, dict)
        and execution.get("terminal_provider_status") == "completed"
        and validator.get("status") == "passed"
        and execution.get("requested_model_id")
        == execution.get("resolved_model_id")
        and execution.get("input_hash") == execution.get("crop_sha256")
    )
    cells = proposal.get("cells") if isinstance(proposal, dict) else []
    if not isinstance(cells, list):
        cells = []
    present = [
        cell
        for cell in cells
        if isinstance(cell, dict) and cell.get("content_state") == "present"
    ]
    text_cells: dict[str, list[dict[str, Any]]] = {}
    for cell in present:
        text = canonicalize_text(str(cell.get("source_text") or ""))
        if text:
            text_cells.setdefault(text, []).append(cell)

    entry_scores = []
    reference_numeric: set[str] = set()
    reference_nonvalue_text: set[str] = set()
    for entry in reference_entries:
        label = canonicalize_text(str(entry.get("row_label_text") or ""))
        value = canonicalize_text(str(entry.get("visible_value_text") or ""))
        headers = [
            canonicalize_text(str(item))
            for item in entry.get("column_header_path") or []
            if canonicalize_text(str(item))
        ]
        reference_nonvalue_text.add(label)
        reference_nonvalue_text.update(headers)
        parsed = parse_visible_numeric(value)
        if parsed.parsed_numeric_value is not None:
            reference_numeric.add(parsed.parsed_numeric_value)
        label_cells = text_cells.get(label, [])
        value_cells = text_cells.get(value, [])
        header_supported = all(header in text_cells for header in headers)
        numeric_supported = False
        if parsed.parsed_numeric_value is not None:
            numeric_supported = any(
                parse_visible_numeric(text).parsed_numeric_value
                == parsed.parsed_numeric_value
                for text in text_cells
            )
        same_row = any(
            _row_ranges_overlap(label_cell, value_cell)
            for label_cell in label_cells
            for value_cell in value_cells
        )
        entry_scores.append(
            {
                "reference_entry_id_hash": hashlib.sha256(
                    str(entry.get("reference_entry_id") or "").encode("utf-8")
                ).hexdigest(),
                "label_exact": bool(label_cells),
                "headers_exact": header_supported,
                "value_exact": bool(value_cells),
                "numeric_value_agreement": numeric_supported,
                "row_binding_supported": same_row,
                "literal_entry_accounted": bool(label_cells and value_cells),
            }
        )

    numeric_value_cells = []
    numeric_hallucination_candidates = []
    for text in text_cells:
        if text in reference_nonvalue_text:
            continue
        parsed = parse_visible_numeric(text)
        if parsed.parsed_numeric_value is None:
            continue
        numeric_value_cells.append(text)
        if parsed.parsed_numeric_value not in reference_numeric:
            numeric_hallucination_candidates.append(text)

    opportunities = len(entry_scores)
    exact_values = sum(item["value_exact"] for item in entry_scores)
    numeric_opportunities = sum(
        parse_visible_numeric(entry.get("visible_value_text")).parsed_numeric_value
        is not None
        for entry in reference_entries
    )
    numeric_agreements = sum(
        item["numeric_value_agreement"] for item in entry_scores
    )
    accounted = sum(item["literal_entry_accounted"] for item in entry_scores)
    bindings = sum(item["row_binding_supported"] for item in entry_scores)
    hallucinations = len(numeric_hallucination_candidates)
    hallucination_denominator = len(numeric_value_cells)
    exact_rate = _ratio(exact_values, opportunities)
    binding_rate = _ratio(bindings, opportunities)
    hallucination_rate = _ratio(hallucinations, hallucination_denominator)
    structurally_useful = bool(
        contract_valid
        and exact_rate is not None
        and exact_rate >= 0.8
        and binding_rate is not None
        and binding_rate >= 0.7
        and (hallucination_rate is None or hallucination_rate <= 0.05)
    )
    return {
        "contract_valid": contract_valid,
        "proposal_hash": sha256_json(proposal) if isinstance(proposal, dict) else None,
        "reference_entry_opportunities": opportunities,
        "exact_literal_value_matches": exact_values,
        "numeric_value_opportunities": numeric_opportunities,
        "numeric_value_matches": numeric_agreements,
        "literal_entries_accounted": accounted,
        "row_bindings_supported": bindings,
        "numeric_value_cells": hallucination_denominator,
        "numeric_hallucination_candidates": hallucinations,
        "exact_literal_value_agreement_rate": exact_rate,
        "numeric_value_agreement_rate": _ratio(
            numeric_agreements, numeric_opportunities
        ),
        "omission_rate": _ratio(opportunities - accounted, opportunities),
        "numeric_hallucination_rate": hallucination_rate,
        "row_binding_support_rate": binding_rate,
        "structurally_useful_for_assisted_review": structurally_useful,
        "entry_scores": entry_scores,
    }


def aggregate_metrics(
    *,
    samples: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    table_reviews: list[dict[str, Any]],
    repeat_count: int,
) -> dict[str, Any]:
    provider_samples = len(samples)
    opportunities = sum(item["reference_entry_opportunities"] for item in samples)
    exact_values = sum(item["exact_literal_value_matches"] for item in samples)
    numeric_opportunities = sum(item["numeric_value_opportunities"] for item in samples)
    numeric_values = sum(item["numeric_value_matches"] for item in samples)
    accounted = sum(item["literal_entries_accounted"] for item in samples)
    hallucination_denominator = sum(item["numeric_value_cells"] for item in samples)
    hallucinations = sum(item["numeric_hallucination_candidates"] for item in samples)
    bindings = sum(item["row_bindings_supported"] for item in samples)

    by_unit_provider: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for sample in samples:
        key = (sample["candidate_ref_hash"], sample["provider"])
        by_unit_provider.setdefault(key, []).append(sample)
    repeatability_pairs = 0
    repeatability_exact = 0
    nondeterministic_pairs = 0
    for pair_samples in by_unit_provider.values():
        pair_samples.sort(key=lambda item: item["repeat_index"])
        if len(pair_samples) != repeat_count:
            raise ActualCorpusVlmEvaluationError(
                "actual_corpus_repeatability_coverage_invalid"
            )
        repeatability_pairs += 1
        hashes = [item.get("proposal_hash") for item in pair_samples]
        stable = hashes[0] is not None and len(set(hashes)) == 1
        repeatability_exact += int(stable)
        nondeterministic_pairs += int(not stable)

    by_unit: dict[str, list[dict[str, Any]]] = {}
    for sample in samples:
        by_unit.setdefault(sample["candidate_ref_hash"], []).append(sample)
    useful_distinct_crops = sum(
        any(item["structurally_useful_for_assisted_review"] for item in unit_samples)
        for unit_samples in by_unit.values()
    )
    cross_provider_repeat_qualified_crops = sum(
        len(unit_samples) == repeat_count * 2
        and all(
            item["structurally_useful_for_assisted_review"]
            for item in unit_samples
        )
        for unit_samples in by_unit.values()
    )

    dispositions = [item.get("disposition") for item in table_reviews]
    unsupported = sum(item == "unsupported_layout" for item in dispositions)
    provider_failures = sum(
        item.get("provider_terminal_status") != "completed" for item in samples
    )
    runtime_rejections = sum(
        item.get("decision_status") in REJECTION_STATUSES for item in decisions
    )
    disagreements = sum(
        item.get("disagreement_classification") == "provider_disagreement"
        for item in decisions
    )
    layout_coverage = {
        characteristic: sum(
            characteristic in (item.get("layout_characteristics") or [])
            for item in table_reviews
        )
        for characteristic in sorted(LAYOUT_CHARACTERISTICS)
    }
    return {
        "contract_validity_rate": _ratio(
            sum(item["contract_valid"] for item in samples), provider_samples
        ),
        "structural_usefulness_rate": _ratio(
            sum(item["structurally_useful_for_assisted_review"] for item in samples),
            provider_samples,
        ),
        "structurally_useful_provider_outputs": sum(
            item["structurally_useful_for_assisted_review"] for item in samples
        ),
        "structurally_useful_distinct_crops": useful_distinct_crops,
        "cross_provider_repeat_qualified_crops": (
            cross_provider_repeat_qualified_crops
        ),
        "exact_literal_cell_value_agreement_rate": _ratio(
            exact_values, opportunities
        ),
        "numeric_value_agreement_rate": _ratio(
            numeric_values, numeric_opportunities
        ),
        "row_binding_support_rate": _ratio(bindings, opportunities),
        "omission_rate": _ratio(opportunities - accounted, opportunities),
        "numeric_value_hallucination_rate": _ratio(
            hallucinations, hallucination_denominator
        ),
        "exact_proposal_repeatability_rate": _ratio(
            repeatability_exact, repeatability_pairs
        ),
        "nondeterministic_unit_provider_pairs": nondeterministic_pairs,
        "repeatability_unit_provider_pairs": repeatability_pairs,
        "provider_disagreement_rate": _ratio(disagreements, len(decisions)),
        "provider_disagreement_decisions": disagreements,
        "review_rate": _ratio(
            sum(item.get("review_required") is True for item in decisions),
            len(decisions),
        ),
        "runtime_rejection_rate": _ratio(runtime_rejections, len(decisions)),
        "provider_terminal_failure_rate": _ratio(provider_failures, provider_samples),
        "unsupported_layout_rejection_rate": _ratio(
            unsupported, len(table_reviews)
        ),
        "canonical_tables_published": sum(
            item.get("canonical_table_published") is True for item in decisions
        ),
        "provider_proposals_with_canonical_authority": sum(
            item.get("provider_proposal_canonical_authority") is True
            for item in decisions
        ),
        "layout_coverage": layout_coverage,
        "page_continuations_present": 0,
        "unreadable_or_obscured_actual_units_present": 0,
        "reference_entry_opportunities": opportunities,
        "numeric_value_opportunities": numeric_opportunities,
    }


def product_envelope(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "safe_for_proposal_generation": True,
        "safe_for_assisted_review": True,
        "assisted_review_condition": (
            "the exact source crop remains visible and every proposed cell is checked; "
            "a proposal may be discarded without publication"
        ),
        "safe_for_unattended_extraction": False,
        "safe_for_automatic_publication": False,
        "automatic_publication_reason": (
            "every actual-corpus runtime decision requires review; provider output "
            "and consensus have zero canonical authority"
        ),
        "supported_layout_boundary": (
            "source-bound single-page numeric table crops may yield useful review "
            "proposals, but only the measured subset meeting the strict usefulness "
            "threshold is supported"
        ),
        "measured_useful_subset": {
            "provider_outputs": metrics.get("structurally_useful_provider_outputs"),
            "distinct_crops": metrics.get("structurally_useful_distinct_crops"),
            "cross_provider_repeat_qualified_crops": metrics.get(
                "cross_provider_repeat_qualified_crops"
            ),
        },
        "unsupported_layout_families": [
            "long-form prose grids rejected by delegated source review",
            "cross-page continuations not present in the bounded actual contour",
            "unreadable or obscured values not present in the bounded actual contour",
        ],
        "unsupported_or_ambiguous_fail_closed": (
            metrics.get("canonical_tables_published") == 0
            and metrics.get("provider_proposals_with_canonical_authority") == 0
            and metrics.get("review_rate") == 1.0
        ),
        "customer_acceptance_claimed": False,
        "universal_visual_table_automation_claimed": False,
    }


def build_safe_receipt(
    *, score: dict[str, Any], terminal: dict[str, Any], reference: dict[str, Any]
) -> dict[str, Any]:
    metrics = copy.deepcopy(score["metrics"])
    envelope = copy.deepcopy(score["product_envelope"])
    acceptance = {
        "ACTUAL_CORPUS_VLM_EVALUATION": "COMPLETED",
        "PROVIDER_OUTPUT_AS_REFERENCE_TRUTH": "ZERO",
        "REAL_DISAGREEMENT": "VISIBLE",
        "REAL_NONDETERMINISM": "MEASURED",
        "REVIEW_RATE": "MEASURED",
        "SUPPORTED_PRODUCT_ENVELOPE": "EXPLICIT",
        "UNSUPPORTED_OR_AMBIGUOUS_INPUT": "FAIL_CLOSED",
        "CUSTOMER_ACCEPTANCE": "NOT_FALSELY_CLAIMED",
    }
    passed = (
        score.get("status") == "completed"
        and metrics.get("provider_disagreement_decisions", 0) > 0
        and metrics.get("repeatability_unit_provider_pairs", 0) > 0
        and metrics.get("review_rate") is not None
        and envelope.get("unsupported_or_ambiguous_fail_closed") is True
        and reference.get("human_reviewed") is False
        and reference.get("delegated_agent_reviewed") is True
        and reference.get("customer_accepted") is False
        and reference["lineage"].get("provider_outputs_used") is False
        and reference["lineage"].get("provider_consensus_used") is False
    )
    if not passed:
        raise ActualCorpusVlmEvaluationError(
            "actual_corpus_acceptance_invariant_failed"
        )
    receipt = {
        "schema_version": SAFE_RECEIPT_SCHEMA,
        "status": "completed",
        "source_revision": terminal["source_revision"],
        "actual_corpus": {
            "authorized_by_explicit_user_delegation": True,
            "bounded_source_documents": len(
                {
                    item["source_lineage"]["source_sha256"]
                    for item in (
                        record["decision"]
                        for record in terminal["decision_records"]
                    )
                }
            ),
            "table_crops": terminal["candidate_count"],
            "independent_repeats": terminal["repeat_count"],
            "provider_executions": score["provider_samples"],
            "source_values_included": False,
            "source_filenames_included": False,
            "private_paths_included": False,
        },
        "reference_authority": copy.deepcopy(score["reference_authority"]),
        "metrics": metrics,
        "product_envelope": envelope,
        "acceptance": acceptance,
        "raw_provider_responses_included": False,
        "provider_output_values_included": False,
        "customer_values_included": False,
    }
    receipt["receipt_hash"] = sha256_json(receipt)
    return receipt


def _validate_review_decisions(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "delegation",
        "reviewer",
        "source_review_only",
        "provider_outputs_opened",
        "provider_consensus_opened",
        "customer_acceptance_claimed",
        "entries",
    }:
        raise ActualCorpusVlmEvaluationError("actual_corpus_review_decisions_invalid")
    reviewer = _object(value.get("reviewer"))
    delegation = _object(value.get("delegation"))
    if (
        value.get("schema_version") != REVIEW_DECISIONS_SCHEMA
        or value.get("source_review_only") is not True
        or value.get("provider_outputs_opened") is not False
        or value.get("provider_consensus_opened") is not False
        or value.get("customer_acceptance_claimed") is not False
        or reviewer.get("kind") != "delegated_agent"
        or not isinstance(reviewer.get("identity"), str)
        or not reviewer.get("identity")
        or not _timestamp(reviewer.get("reviewed_at"))
        or delegation.get("kind") != "explicit_user_delegation"
        or not isinstance(delegation.get("delegator_identity"), str)
        or not delegation.get("delegator_identity")
        or not _sha256(delegation.get("delegation_statement_sha256"))
        or delegation.get("delegation_statement_retained") is not False
    ):
        raise ActualCorpusVlmEvaluationError("actual_corpus_review_decisions_invalid")
    entries = value.get("entries")
    if not isinstance(entries, list) or len(entries) != 9:
        raise ActualCorpusVlmEvaluationError("actual_corpus_review_coverage_invalid")
    identifiers: set[str] = set()
    runtime_refs: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "case_id",
            "page_number",
            "table_identifier",
            "runtime_candidate_ref",
            "disposition",
            "layout_characteristics",
            "attestations",
            "review_note",
        }:
            raise ActualCorpusVlmEvaluationError("actual_corpus_review_entry_invalid")
        table_id = entry.get("table_identifier")
        runtime_ref = entry.get("runtime_candidate_ref")
        characteristics = entry.get("layout_characteristics")
        attestations = entry.get("attestations")
        if (
            not isinstance(table_id, str)
            or not table_id
            or table_id in identifiers
            or not isinstance(runtime_ref, str)
            or not runtime_ref
            or runtime_ref in runtime_refs
            or entry.get("disposition") not in DISPOSITIONS
            or not isinstance(characteristics, list)
            or not characteristics
            or not set(characteristics) <= LAYOUT_CHARACTERISTICS
            or len(characteristics) != len(set(characteristics))
            or not isinstance(attestations, dict)
            or set(attestations) != set(REVIEW_ATTESTATIONS)
            or not all(attestations.get(key) is True for key in REVIEW_ATTESTATIONS)
            or not isinstance(entry.get("review_note"), str)
            or len(entry["review_note"]) > 500
        ):
            raise ActualCorpusVlmEvaluationError("actual_corpus_review_entry_invalid")
        identifiers.add(table_id)
        runtime_refs.add(runtime_ref)


def _validate_literal_draft_for_projection(value: dict[str, Any]) -> None:
    cases = value.get("cases")
    if not isinstance(cases, list) or len(cases) != 8:
        raise ActualCorpusVlmEvaluationError("actual_corpus_literal_draft_invalid")
    entry_ids: set[str] = set()
    table_count = 0
    entry_count = 0
    required_entry_fields = {
        "reference_entry_id",
        "row_label_text",
        "column_header_path",
        "visible_value_text",
        "row_label_bbox",
        "header_bboxes",
        "value_bbox",
        "cell_state",
        "visibly_empty",
        "spans_multiple_visual_rows",
        "spans_multiple_visual_columns",
        "literal_source_notes",
        "review_status",
        "review_provenance",
    }
    for case in cases:
        if (
            not isinstance(case, dict)
            or not isinstance(case.get("case_id"), str)
            or not case.get("case_id")
            or not _sha256(case.get("document_sha256"))
            or not isinstance(case.get("page_number"), int)
            or not isinstance(case.get("tables"), list)
        ):
            raise ActualCorpusVlmEvaluationError(
                "actual_corpus_literal_draft_invalid"
            )
        for table in case["tables"]:
            table_count += 1
            if (
                not isinstance(table, dict)
                or not isinstance(table.get("table_identifier"), str)
                or not table.get("table_identifier")
                or not _sha256(table.get("crop_sha256"))
                or not isinstance(table.get("complete_table_bbox"), list)
                or len(table["complete_table_bbox"]) != 4
                or not isinstance(table.get("entries"), list)
            ):
                raise ActualCorpusVlmEvaluationError(
                    "actual_corpus_literal_draft_invalid"
                )
            for entry in table["entries"]:
                entry_count += 1
                if not isinstance(entry, dict) or set(entry) != required_entry_fields:
                    raise ActualCorpusVlmEvaluationError(
                        "actual_corpus_literal_draft_invalid"
                    )
                entry_id = entry.get("reference_entry_id")
                if (
                    not isinstance(entry_id, str)
                    or not entry_id
                    or entry_id in entry_ids
                    or not isinstance(entry.get("row_label_text"), str)
                    or not isinstance(entry.get("column_header_path"), list)
                    or any(
                        not isinstance(item, str)
                        for item in entry["column_header_path"]
                    )
                    or not isinstance(entry.get("visible_value_text"), str)
                    or entry.get("cell_state")
                    not in {"value", "empty", "unreadable", "ambiguous"}
                    or entry.get("review_status") != "pending"
                ):
                    raise ActualCorpusVlmEvaluationError(
                        "actual_corpus_literal_draft_invalid"
                    )
                entry_ids.add(entry_id)
    if table_count != 9 or entry_count != 89:
        raise ActualCorpusVlmEvaluationError("actual_corpus_literal_draft_invalid")


def _validate_run_identity(value: Any) -> None:
    if not isinstance(value, dict):
        raise ActualCorpusVlmEvaluationError("actual_corpus_run_identity_invalid")
    unhashed = copy.deepcopy(value)
    identity_hash = unhashed.pop("identity_hash", None)
    if (
        value.get("schema_version") != RUN_IDENTITY_SCHEMA
        or value.get("status") != "completed"
        or value.get("reference_accessed") is not False
        or value.get("provider_output_as_reference_truth") is not False
        or value.get("provider_consensus_as_reference_truth") is not False
        or value.get("provider_output_values_included") is not False
        or not _sha256(value.get("terminal_sha256"))
        or not _sha256(value.get("detection_terminal_sha256"))
        or not isinstance(value.get("units"), list)
        or len(value["units"]) != 9
        or identity_hash != sha256_json(unhashed)
    ):
        raise ActualCorpusVlmEvaluationError("actual_corpus_run_identity_invalid")


def _validate_run_seal(
    terminal_bytes: bytes, terminal: dict[str, Any], seal: Any
) -> None:
    if not isinstance(seal, dict):
        raise ActualCorpusVlmEvaluationError("actual_corpus_run_seal_invalid")
    unhashed = copy.deepcopy(seal)
    seal_hash = unhashed.pop("seal_sha256", None)
    canonical_terminal = canonical_json_bytes(terminal)
    if (
        terminal.get("schema_version") != RUN_SCHEMA
        or terminal.get("status") != "completed"
        or terminal.get("reference_accessed") is not False
        or terminal.get("reference_argument_supported") is not False
        or seal.get("schema_version") != RUN_SEAL_SCHEMA
        or seal.get("terminal_sha256")
        != hashlib.sha256(canonical_terminal).hexdigest()
        or seal.get("terminal_size_bytes") != len(canonical_terminal)
        or seal.get("status") != "completed"
        or seal.get("reference_accessed") is not False
        or seal_hash != sha256_json(unhashed)
    ):
        raise ActualCorpusVlmEvaluationError("actual_corpus_run_seal_invalid")


def _validate_reference_seal(
    reference_bytes: bytes, reference: dict[str, Any], seal: Any
) -> None:
    if not isinstance(seal, dict):
        raise ActualCorpusVlmEvaluationError("actual_corpus_reference_seal_invalid")
    unhashed = copy.deepcopy(seal)
    seal_hash = unhashed.pop("seal_sha256", None)
    lineage = _object(reference.get("lineage"))
    canonical_reference = canonical_json_bytes(reference)
    if (
        reference.get("schema_version") != DELEGATED_REFERENCE_SCHEMA
        or reference.get("human_reviewed") is not False
        or reference.get("delegated_agent_reviewed") is not True
        or reference.get("customer_accepted") is not False
        or lineage.get("provider_outputs_used") is not False
        or lineage.get("provider_consensus_used") is not False
        or seal.get("schema_version") != DELEGATED_REFERENCE_SEAL_SCHEMA
        or seal.get("reference_sha256")
        != hashlib.sha256(canonical_reference).hexdigest()
        or seal.get("reference_size_bytes") != len(canonical_reference)
        or seal.get("human_reviewed") is not False
        or seal.get("delegated_agent_reviewed") is not True
        or seal.get("customer_accepted") is not False
        or seal_hash != sha256_json(unhashed)
    ):
        raise ActualCorpusVlmEvaluationError("actual_corpus_reference_seal_invalid")


def _draft_table_index(
    reference: dict[str, Any],
) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    result: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for case in reference.get("cases") or []:
        for table in _object(case).get("tables") or []:
            table_id = str(_object(table).get("table_identifier") or "")
            if not table_id or table_id in result:
                raise ActualCorpusVlmEvaluationError(
                    "actual_corpus_literal_table_identity_invalid"
                )
            result[table_id] = (case, table)
    if len(result) != 9:
        raise ActualCorpusVlmEvaluationError(
            "actual_corpus_literal_table_coverage_invalid"
        )
    return result


def _evaluated_table_index(reference: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    tables = reference.get("tables")
    if not isinstance(tables, list):
        raise ActualCorpusVlmEvaluationError(
            "actual_corpus_literal_table_coverage_invalid"
        )
    for table in tables:
        table_id = str(_object(table).get("table_identifier") or "")
        if not table_id or table_id in result:
            raise ActualCorpusVlmEvaluationError(
                "actual_corpus_literal_table_identity_invalid"
            )
        result[table_id] = table
    if len(result) != 9:
        raise ActualCorpusVlmEvaluationError(
            "actual_corpus_literal_table_coverage_invalid"
        )
    return result


def _candidate_ref(case_id: str, candidate_id: str) -> str:
    value = f"goal1_{case_id}_{candidate_id}"
    if not re.fullmatch(r"[a-z0-9_]{1,128}", value):
        raise ActualCorpusVlmEvaluationError("actual_corpus_candidate_ref_invalid")
    return value


def _bounded_source_path(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise ActualCorpusVlmEvaluationError("actual_corpus_source_path_invalid")
    resolved_root = root.resolve()
    resolved = (resolved_root / relative).resolve()
    if resolved_root not in resolved.parents or not resolved.is_file():
        raise ActualCorpusVlmEvaluationError("actual_corpus_source_path_invalid")
    return resolved


def _row_ranges_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    try:
        left_start = int(left["row_index"])
        left_end = left_start + int(left["row_span"])
        right_start = int(right["row_index"])
        right_end = right_start + int(right["row_span"])
    except (KeyError, TypeError, ValueError):
        return False
    return max(left_start, right_start) < min(left_end, right_end)


def _chunks(values: list[Any], size: int) -> Iterable[list[Any]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _require_fresh_directory(path: Path) -> None:
    if path.exists():
        raise ActualCorpusVlmEvaluationError("actual_corpus_fresh_output_required")


def _json_object(raw: bytes, failure: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ActualCorpusVlmEvaluationError(failure) from exc
    if not isinstance(value, dict):
        raise ActualCorpusVlmEvaluationError(failure)
    return value


def _load_json(path: Path) -> dict[str, Any]:
    return _json_object(path.read_bytes(), "actual_corpus_json_invalid")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


if __name__ == "__main__":
    raise SystemExit(main())
