#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import fitz
import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from direct_pdf_experiment_contracts import (  # noqa: E402
    TABLE_SCHEMA_VERSION,
    canonical_bytes,
    normalize_cell,
    score_tables,
)
from direct_pdf_experiment_transports import (  # noqa: E402
    PROVIDER_SPECS,
    NativePdfTransport,
    connections_from_openwebui_config,
)
from direct_pdf_plain_text_experiment_contracts import (  # noqa: E402
    EXPERIMENT_VERSION,
    PROMPT_VERSION,
    REPEAT_TARGET_KEYS,
    TARGET_PROMPT_VERSION,
    TARGET_KEYS,
    assess_explanation,
    assess_inventory,
    explanation_prompt,
    inventory_prompt,
    parse_inventory_text,
    parse_table_text,
    prompt_hash,
    score_selected_reference,
    transcription_prompt,
)
from live_no_rag_source_intake_smoke import _base_url, _read_env, _signin, _url  # noqa: E402


SAFE_SCHEMA = "broker_reports_direct_pdf_plain_text_experiment_safe_v1"
PRIVATE_SCHEMA = "broker_reports_direct_pdf_plain_text_experiment_private_v1"
MANUAL_HEADER_ROWS = {
    "1:1": 3,
    "1:2": 2,
    "1:3": 3,
    "2:2": 2,
    "3:2": 2,
    "4:1": 0,
    "4:2": 3,
    "5:3": 2,
    "5:4": 2,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Direct whole-PDF plain-text multi-provider research experiment")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--reference",
        default=str(
            REPO_ROOT
            / "local/stage2/broker_reports_pdf_normalization_acceptance_2026-07-12/experiment/private/reference.private.json"
        ),
    )
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--max-output-tokens", type=int, default=32768)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--providers", default="openai,google,anthropic")
    parser.add_argument("--resume-only", action="store_true")
    args = parser.parse_args()

    if args.max_output_tokens < 1024:
        raise ValueError("max_output_tokens_too_small")
    requested_providers = tuple(value.strip() for value in args.providers.split(",") if value.strip())
    supported_providers = {spec.provider for spec in PROVIDER_SPECS}
    if not requested_providers or set(requested_providers) - supported_providers:
        raise ValueError("providers_invalid")

    pdf_path = Path(args.pdf).resolve()
    reference_path = Path(args.reference).resolve()
    output_dir = Path(args.output_dir).resolve()
    private_dir = output_dir / "private"
    private_dir.mkdir(parents=True, exist_ok=True)
    pdf_bytes = pdf_path.read_bytes()
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
    document = fitz.open(pdf_path)
    page_count = len(document)
    full_reference, table_bboxes = _full_reference(document)
    selected_reference, reference_status = _selected_reference(reference_path, pdf_hash)
    if set(selected_reference) != set(TARGET_KEYS):
        raise ValueError("selected_reference_keys_mismatch")

    jobs = _jobs(requested_providers, args.max_output_tokens)
    journal_path = private_dir / "journal.private.json"
    journal = _read_list(journal_path)
    completed = {_job_key(item.get("safe", {})) for item in journal}

    env = _read_env(Path(args.env_file))
    base_url = _base_url(env)
    session = requests.Session()
    _signin(session, base_url, env)
    config_response = session.get(_url(base_url, "/openai/config"), timeout=30)
    config_response.raise_for_status()
    connections = connections_from_openwebui_config(config_response.json())

    qualifications: dict[str, dict[str, Any]] = {}
    transports: dict[str, NativePdfTransport] = {}
    for spec in PROVIDER_SPECS:
        if spec.provider not in requested_providers:
            continue
        connection = connections.get(spec.provider)
        if connection is None:
            qualifications[spec.provider] = {
                "status": "blocked",
                "failure_class": "openwebui_connection_missing",
                "model": spec.model,
                "transport": spec.transport,
            }
            continue
        transport = NativePdfTransport(connection, timeout=args.timeout)
        transports[spec.provider] = transport
        try:
            result = transport.qualify_models()
            present = _model_present(spec.model, result["model_ids"])
            qualifications[spec.provider] = {
                "status": "passed" if present and result["http_status"] == 200 else "blocked",
                "model": spec.model,
                "transport": spec.transport,
                "native_model_list_http_status": result["http_status"],
                "native_model_list_response_hash": result["response_hash"],
                "native_model_count": len(result["model_ids"]),
                "model_present": present,
            }
        except Exception as exc:
            qualifications[spec.provider] = {
                "status": "blocked",
                "failure_class": type(exc).__name__,
                "model": spec.model,
                "transport": spec.transport,
            }

    journal_lock = threading.Lock()

    def run_lane(provider: str) -> None:
        spec = next(item for item in PROVIDER_SPECS if item.provider == provider)
        for job in [item for item in jobs if item["provider"] == provider]:
            if _job_key(job) in completed:
                continue
            transport = transports.get(provider)
            if transport is None or qualifications[provider]["status"] != "passed":
                outcome = _failed_outcome(job, spec.model, spec.transport, "capability_qualification_blocked")
            else:
                prompt = _prompt(job)
                try:
                    private, safe = transport.invoke_plain_text(
                        spec=spec,
                        pdf_bytes=pdf_bytes,
                        filename="document.pdf",
                        prompt=prompt,
                        max_output_tokens=job["max_output_tokens"],
                    )
                    safe.update(
                        _safe_identity(
                            job,
                            spec.model,
                            spec.transport,
                            pdf_hash,
                            len(pdf_bytes),
                            page_count,
                            prompt,
                        )
                    )
                    outcome = {"private": {**private, **job}, "safe": safe}
                except Exception as exc:
                    outcome = _failed_outcome(job, spec.model, spec.transport, type(exc).__name__)
                    outcome["safe"].update(
                        _safe_identity(
                            job,
                            spec.model,
                            spec.transport,
                            pdf_hash,
                            len(pdf_bytes),
                            page_count,
                            prompt,
                        )
                    )
            _evaluate_outcome(outcome, document, full_reference, selected_reference, table_bboxes)
            with journal_lock:
                journal.append(outcome)
                journal.sort(key=lambda item: _job_sort_key(item.get("safe", {})))
                _write_json(journal_path, journal)

    if not args.resume_only:
        active_lanes = [provider for provider in requested_providers if any(
            _job_key(job) not in completed for job in jobs if job["provider"] == provider
        )]
        with ThreadPoolExecutor(max_workers=max(1, min(args.workers, len(active_lanes) or 1))) as executor:
            list(executor.map(run_lane, active_lanes))

    journal = _read_list(journal_path)
    for item in journal:
        _evaluate_outcome(item, document, full_reference, selected_reference, table_bboxes)
    journal.sort(key=lambda item: _job_sort_key(item.get("safe", {})))
    _write_json(journal_path, journal)
    safe_runs = [dict(item.get("safe", {})) for item in journal]
    safe_runs = [item for item in safe_runs if item.get("provider") in requested_providers]
    terminal = len(safe_runs) == len(jobs)
    artifact_failures = sum(item.get("artifact_status") != "accepted" for item in safe_runs)

    private_result = {
        "schema_version": PRIVATE_SCHEMA,
        "experiment_version": EXPERIMENT_VERSION,
        "journal": journal,
        "selected_reference": selected_reference,
        "full_reference": full_reference,
        "reference_status": reference_status,
    }
    private_path = private_dir / "experiment.private.json"
    _write_json(private_path, private_result)
    safe_result = {
        "schema_version": SAFE_SCHEMA,
        "experiment_version": EXPERIMENT_VERSION,
        "prompt_versions": {
            "explanation_inventory_monolithic": PROMPT_VERSION,
            "targeted": TARGET_PROMPT_VERSION,
        },
        "status": (
            "partial"
            if not terminal
            else "passed"
            if artifact_failures == 0
            else "completed_with_failures"
        ),
        "source": {
            "pdf_sha256": pdf_hash,
            "pdf_bytes": len(pdf_bytes),
            "pages": page_count,
            "identical_original_bytes_for_all_jobs": all(item.get("input_pdf_sha256") == pdf_hash for item in safe_runs),
        },
        "reference_status": {
            "table_reference": reference_status,
            "authoritative_accuracy_claims_allowed": reference_status == "human_reviewed_signed_off",
            "selected_tables": len(selected_reference),
            "full_engine_tables": len(full_reference),
        },
        "qualifications": qualifications,
        "job_contract": {
            "providers": list(requested_providers),
            "jobs_expected": len(jobs),
            "jobs_terminal": len(safe_runs),
            "arms_are_scored_separately": True,
            "target_keys": list(TARGET_KEYS),
            "repeat_target_keys": list(REPEAT_TARGET_KEYS),
            "silent_retry": False,
            "hidden_failover": False,
        },
        "discarded_preflight": _discarded_preflight(
            private_dir / "journal.pre_target_header_fix.private.json"
        ),
        "runs": safe_runs,
        "aggregates": _aggregates(safe_runs),
        "hybrid_control": _hybrid_control(
            REPO_ROOT
            / "local/stage2/broker_reports_pdf_normalization_acceptance_2026-07-12/experiment/experiment.safe.json"
        ),
        "guards": {
            "production_pdf_pipeline_changed": False,
            "gate2_validators_changed": False,
            "openwebui_core_changed": False,
            "crop_sent": False,
            "locally_extracted_text_sent": False,
            "normalized_geometry_sent": False,
            "table_projection_sent": False,
            "source_value_candidates_sent": False,
            "knowledge_rag_vector_file_search_used": False,
            "hidden_provider_failover_used": False,
            "silent_retry_used": False,
            "fuzzy_scoring_used": False,
            "raw_customer_data_in_safe_output": False,
        },
    }
    safe_path = output_dir / "experiment.safe.json"
    _write_json(safe_path, safe_result)
    safe_result["storage"] = {
        "journal_private_bytes": journal_path.stat().st_size,
        "journal_private_gzip_bytes": len(gzip.compress(journal_path.read_bytes())),
        "experiment_private_bytes": private_path.stat().st_size,
        "experiment_safe_bytes_before_storage_field": safe_path.stat().st_size,
    }
    _write_json(safe_path, safe_result)
    print(json.dumps(safe_result, ensure_ascii=False, indent=2, sort_keys=True))
    document.close()
    return 0 if terminal else 2


def _jobs(providers: tuple[str, ...], max_output_tokens: int) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for provider in providers:
        jobs.extend(
            [
                {"provider": provider, "arm": "explanation", "page": 0, "order": 0, "repeat": 1, "max_output_tokens": min(max_output_tokens, 8192)},
                {"provider": provider, "arm": "inventory", "page": 0, "order": 0, "repeat": 1, "max_output_tokens": min(max_output_tokens, 8192)},
                {"provider": provider, "arm": "monolithic", "page": 0, "order": 0, "repeat": 1, "max_output_tokens": max_output_tokens},
            ]
        )
        for key in TARGET_KEYS:
            page, order = (int(value) for value in key.split(":"))
            jobs.append(
                {"provider": provider, "arm": "targeted", "page": page, "order": order, "repeat": 1, "max_output_tokens": min(max_output_tokens, 16384)}
            )
        for key in REPEAT_TARGET_KEYS:
            page, order = (int(value) for value in key.split(":"))
            jobs.append(
                {"provider": provider, "arm": "targeted", "page": page, "order": order, "repeat": 2, "max_output_tokens": min(max_output_tokens, 16384)}
            )
    return jobs


def _prompt(job: dict[str, Any]) -> str:
    if job["arm"] == "explanation":
        return explanation_prompt()
    if job["arm"] == "inventory":
        return inventory_prompt()
    if job["arm"] == "monolithic":
        return transcription_prompt()
    return transcription_prompt(page=int(job["page"]), order=int(job["order"]))


def _evaluate_outcome(
    outcome: dict[str, Any],
    document: fitz.Document,
    full_reference: dict[str, dict[str, Any]],
    selected_reference: dict[str, dict[str, Any]],
    table_bboxes: dict[str, tuple[float, float, float, float]],
) -> None:
    private = outcome.get("private") if isinstance(outcome.get("private"), dict) else {}
    safe = outcome.get("safe") if isinstance(outcome.get("safe"), dict) else {}
    text = private.get("text")
    arm = str(safe.get("arm") or private.get("arm") or "")
    response = private.get("response") if isinstance(private.get("response"), dict) else {}
    safe.update(_usage_details(str(safe.get("provider") or ""), response, safe))
    safe["finish_reason"] = _finish_reason(str(safe.get("provider") or ""), response)
    safe["output_truncated"] = _output_truncated(str(safe.get("provider") or ""), response)
    transport_ok = safe.get("provider_status") == "passed" and isinstance(text, str) and bool(text.strip())
    if arm == "explanation":
        safe["explanation_assessment"] = assess_explanation(text, len(document))
        safe["artifact_status"] = "accepted" if transport_ok else "failed"
    elif arm == "inventory":
        parsed = parse_inventory_text(text)
        private["parsed"] = parsed
        safe["inventory_assessment"] = assess_inventory(full_reference, parsed)
        safe["artifact_status"] = "accepted" if transport_ok and parsed["parse_status"] == "valid" else "failed"
        safe["artifact_validation_error"] = parsed.get("validation_error")
    elif arm in {"monolithic", "targeted"}:
        parsed = parse_table_text(text)
        private["parsed"] = parsed
        safe["raw_prefix_diagnostic"] = {
            "parse_status": parsed.get("parse_status"),
            "complete_table_blocks_before_failure": len(parsed.get("tables", [])),
            "complete_table_identities_before_failure": [
                f"{table['page']}:{table['order_on_page']}" for table in parsed.get("tables", [])
            ],
            "last_table_at_failure": parsed.get("last_complete_table"),
            "last_row_at_failure": parsed.get("last_row_seen"),
            "trailing_content_present": parsed.get("trailing_content") is not None,
        }
        key = f"{safe.get('page')}:{safe.get('order')}"
        full_scope = full_reference if arm == "monolithic" else {key: full_reference[key]} if key in full_reference else {}
        selected_scope = selected_reference if arm == "monolithic" else {key: selected_reference[key]} if key in selected_reference else {}
        safe["full_engine_score"] = score_tables(full_scope, _as_structured(parsed))
        safe["selected_reference_score"] = score_selected_reference(selected_scope, parsed)
        relocation_safe, relocation_private = _assess_relocation(document, parsed, table_bboxes)
        safe["provenance_assessment"] = relocation_safe
        private["posthoc_exact_relocation"] = relocation_private
        accepted_parse = parsed["parse_status"] in {"valid", "valid_empty"}
        target_identity_ok = arm != "targeted" or parsed["parse_status"] == "valid_empty" or (
            len(parsed.get("tables", [])) == 1
            and parsed["tables"][0]["page"] == safe.get("page")
            and parsed["tables"][0]["order_on_page"] == safe.get("order")
        )
        safe["artifact_status"] = "accepted" if transport_ok and accepted_parse and target_identity_ok else "failed"
        safe["artifact_validation_error"] = (
            "target_identity_or_cardinality_mismatch"
            if accepted_parse and not target_identity_ok
            else parsed.get("validation_error")
        )
        safe["artifact_hash"] = hashlib.sha256(canonical_bytes(parsed)).hexdigest() if accepted_parse else None
        safe["last_table_at_parse_terminal"] = parsed.get("last_complete_table")
        safe["last_row_at_parse_terminal"] = parsed.get("last_row_seen")
    else:
        safe["artifact_status"] = "failed"
        safe["artifact_validation_error"] = "arm_unknown"
    if not transport_ok and not safe.get("failure_class"):
        safe["failure_class"] = "provider_plain_text_response_invalid"
    elif transport_ok and safe.get("artifact_status") != "accepted":
        safe["failure_class"] = "plain_text_artifact_malformed"
    private["arm"] = arm
    outcome["private"] = private
    outcome["safe"] = safe


def _full_reference(
    document: fitz.Document,
) -> tuple[dict[str, dict[str, Any]], dict[str, tuple[float, float, float, float]]]:
    reference: dict[str, dict[str, Any]] = {}
    bboxes: dict[str, tuple[float, float, float, float]] = {}
    for page_index, page in enumerate(document):
        for table_index, table in enumerate(page.find_tables().tables):
            key = f"{page_index + 1}:{table_index + 1}"
            rows = [[str(value or "") for value in row] for row in table.extract()]
            columns = max((len(row) for row in rows), default=0)
            reference[key] = {
                "cells": [row + [""] * (columns - len(row)) for row in rows],
                "header_rows": MANUAL_HEADER_ROWS.get(key),
            }
            bboxes[key] = tuple(float(value) for value in table.bbox)
    return reference, bboxes


def _selected_reference(path: Path, pdf_hash: str) -> tuple[dict[str, dict[str, Any]], str]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if value.get("pdf_sha256") != pdf_hash:
        raise ValueError("selected_reference_pdf_hash_mismatch")
    reference = {
        str(table["table_key"]): {
            "cells": [[str(cell or "") for cell in row] for row in table["cells"]],
            "header_rows": table.get("header_rows"),
        }
        for table in value.get("tables", [])
        if isinstance(table, dict) and table.get("table_key")
    }
    return reference, str(value.get("human_review_status") or "unknown")


def _as_structured(parsed: dict[str, Any]) -> dict[str, Any]:
    if parsed.get("parse_status") not in {"valid", "valid_empty"}:
        return {}
    return {
        "schema_version": TABLE_SCHEMA_VERSION,
        "document_status": "completed",
        "tables": [
            {
                **table,
                "boundary": [],
                "continuation_page": 0,
                "continuation_order_on_page": 0,
                "uncertainty": [],
            }
            for table in parsed.get("tables", [])
        ],
        "warnings": [],
    }


def _assess_relocation(
    document: fitz.Document,
    parsed: dict[str, Any],
    table_bboxes: dict[str, tuple[float, float, float, float]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    totals = {
        "returned_nonempty_cells": 0,
        "exact_relocated_cells": 0,
        "unique_exact_relocated_cells": 0,
        "ambiguous_exact_relocated_cells": 0,
        "unmatched_returned_cells": 0,
        "numeric_returned_cells": 0,
        "numeric_exact_relocated_cells": 0,
        "numeric_unique_exact_relocated_cells": 0,
    }
    bindings: list[dict[str, Any]] = []
    page_words_cache: dict[int, list[dict[str, Any]]] = {}
    if parsed.get("parse_status") != "valid":
        return _relocation_result(totals, parsed), {"bindings": bindings}
    for table in parsed.get("tables", []):
        page_number = int(table["page"])
        key = f"{page_number}:{table['order_on_page']}"
        if not 1 <= page_number <= len(document):
            continue
        if page_number not in page_words_cache:
            page_words_cache[page_number] = _page_words(document[page_number - 1], page_number)
        page_words = page_words_cache[page_number]
        bbox = table_bboxes.get(key)
        table_words = [word for word in page_words if bbox and _word_center_in_bbox(word, bbox)]
        for row_ordinal, row in enumerate(table.get("rows", []), 1):
            for column_ordinal, cell in enumerate(row.get("cells", []), 1):
                value = normalize_cell(cell)
                if not value:
                    continue
                totals["returned_nonempty_cells"] += 1
                numeric = _numeric(value)
                totals["numeric_returned_cells"] += numeric
                table_matches = _exact_word_matches(value, table_words)
                page_matches = _exact_word_matches(value, page_words)
                exact = bool(table_matches)
                unique = len(table_matches) == 1
                ambiguous = len(table_matches) > 1
                totals["exact_relocated_cells"] += exact
                totals["unique_exact_relocated_cells"] += unique
                totals["ambiguous_exact_relocated_cells"] += ambiguous
                totals["unmatched_returned_cells"] += not exact
                totals["numeric_exact_relocated_cells"] += numeric and exact
                totals["numeric_unique_exact_relocated_cells"] += numeric and unique
                bindings.append(
                    {
                        "table_key": key,
                        "row": row_ordinal,
                        "column": column_ordinal,
                        "table_exact_match_count": len(table_matches),
                        "page_exact_match_count": len(page_matches),
                        "unique_table_word_refs": table_matches[0] if unique else [],
                    }
                )
    return _relocation_result(totals, parsed), {"bindings": bindings}


def _relocation_result(totals: dict[str, int], parsed: dict[str, Any]) -> dict[str, Any]:
    returned = totals["returned_nonempty_cells"]
    numeric = totals["numeric_returned_cells"]
    strongest = 4 if totals["unique_exact_relocated_cells"] else 2 if parsed.get("parse_status") == "valid" else 0
    uniform = 4 if returned and totals["unique_exact_relocated_cells"] == returned else 2 if parsed.get("parse_status") == "valid" else 0
    return {
        **totals,
        "exact_relocation_rate": _ratio(totals["exact_relocated_cells"], returned),
        "unique_exact_relocation_rate": _ratio(totals["unique_exact_relocated_cells"], returned),
        "numeric_exact_relocation_rate": _ratio(totals["numeric_exact_relocated_cells"], numeric),
        "numeric_unique_exact_relocation_rate": _ratio(totals["numeric_unique_exact_relocated_cells"], numeric),
        "strongest_individual_provenance_level": strongest,
        "strongest_uniform_provenance_level": uniform,
        "page_table_row_column_identity_present": parsed.get("parse_status") == "valid",
        "provider_bbox_or_native_citation_present": False,
        "exact_independent_pdf_word_refs_created_for_unique_matches": totals["unique_exact_relocated_cells"],
        "fuzzy_matching_used": False,
        "authoritative_acceptance": "rejected",
    }


def _page_words(page: fitz.Page, page_number: int) -> list[dict[str, Any]]:
    words = sorted(page.get_text("words"), key=lambda item: (int(item[5]), int(item[6]), int(item[7])))
    return [
        {
            "ref": f"pdfword_{page_number}_{ordinal}",
            "text": str(word[4]),
            "bbox": (float(word[0]), float(word[1]), float(word[2]), float(word[3])),
        }
        for ordinal, word in enumerate(words, 1)
    ]


def _word_center_in_bbox(word: dict[str, Any], bbox: tuple[float, float, float, float]) -> bool:
    x0, y0, x1, y1 = word["bbox"]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return bbox[0] <= cx <= bbox[2] and bbox[1] <= cy <= bbox[3]


def _exact_word_matches(value: str, words: list[dict[str, Any]]) -> list[list[str]]:
    token_count = len(value.split())
    if token_count < 1:
        return []
    matches: list[list[str]] = []
    for index in range(0, len(words) - token_count + 1):
        candidate = normalize_cell(" ".join(word["text"] for word in words[index : index + token_count]))
        if candidate == value:
            matches.append([word["ref"] for word in words[index : index + token_count]])
    return matches


def _aggregates(runs: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for provider in sorted({str(item.get("provider")) for item in runs}):
        values = [item for item in runs if item.get("provider") == provider]
        inventory = next((item.get("inventory_assessment") for item in values if item.get("arm") == "inventory"), None)
        explanation = next((item.get("explanation_assessment") for item in values if item.get("arm") == "explanation"), None)
        monolithic = next((item for item in values if item.get("arm") == "monolithic"), None)
        primary_targets = [item for item in values if item.get("arm") == "targeted" and item.get("repeat") == 1]
        result[provider] = {
            "jobs": len(values),
            "transport_passed_jobs": sum(item.get("provider_status") == "passed" for item in values),
            "accepted_artifacts": sum(item.get("artifact_status") == "accepted" for item in values),
            "input_tokens": sum(int(item.get("input_tokens") or 0) for item in values),
            "output_tokens": sum(int(item.get("output_tokens") or 0) for item in values),
            "visible_output_tokens": sum(int(item.get("visible_output_tokens") or 0) for item in values),
            "reasoning_tokens": sum(int(item.get("reasoning_tokens") or 0) for item in values),
            "duration_seconds": round(sum(float(item.get("duration_seconds") or 0) for item in values), 3),
            "explanation": explanation,
            "inventory": inventory,
            "monolithic": _safe_monolithic_summary(monolithic),
            "targeted_selected_reference": _combine_scores(primary_targets, "selected_reference_score"),
            "targeted_selected_reference_accepted_only": _combine_scores(
                [item for item in primary_targets if item.get("artifact_status") == "accepted"],
                "selected_reference_score",
            ),
            "targeted_full_engine_structure": _combine_scores(primary_targets, "full_engine_score"),
            "targeted_provenance": _combine_provenance(primary_targets),
            "repeatability": _repeatability(values),
        }
    return result


def _safe_monolithic_summary(run: dict[str, Any] | None) -> dict[str, Any] | None:
    if not run:
        return None
    return {
        "artifact_status": run.get("artifact_status"),
        "finish_reason": run.get("finish_reason"),
        "output_truncated": run.get("output_truncated"),
        "input_tokens": run.get("input_tokens"),
        "output_tokens": run.get("output_tokens"),
        "visible_output_tokens": run.get("visible_output_tokens"),
        "reasoning_tokens": run.get("reasoning_tokens"),
        "full_engine_score": run.get("full_engine_score"),
        "selected_reference_score": run.get("selected_reference_score"),
        "provenance_assessment": run.get("provenance_assessment"),
        "last_table_at_parse_terminal": run.get("last_table_at_parse_terminal"),
        "last_row_at_parse_terminal": run.get("last_row_at_parse_terminal"),
    }


def _combine_scores(runs: list[dict[str, Any]], field: str) -> dict[str, Any]:
    scores = [item.get(field) for item in runs if isinstance(item.get(field), dict)]
    cells_exact = sum(int(item.get("cells_exact") or 0) for item in scores)
    cells_total = sum(int(item.get("cells_total") or 0) for item in scores)
    numeric_exact = sum(int(item.get("numeric_exact") or 0) for item in scores)
    numeric_total = sum(int(item.get("numeric_total") or 0) for item in scores)
    empty_exact = sum(int(item.get("empty_cells_exact") or 0) for item in scores)
    empty_total = sum(int(item.get("empty_cells_total") or 0) for item in scores)
    return {
        "tables_scheduled": len(runs),
        "accepted_artifacts": sum(item.get("artifact_status") == "accepted" for item in runs),
        "matched_tables": sum(int(item.get("matched_tables") or 0) for item in scores),
        "exact_structures": sum(int(item.get("exact_structures", item.get("exact_selected_prefix_structures")) or 0) for item in scores),
        "exact_headers": sum(int(item.get("exact_headers") or 0) for item in scores),
        "cells_exact": cells_exact,
        "cells_total": cells_total,
        "cell_accuracy": _ratio(cells_exact, cells_total),
        "numeric_exact": numeric_exact,
        "numeric_total": numeric_total,
        "numeric_accuracy": _ratio(numeric_exact, numeric_total),
        "empty_cells_exact": empty_exact,
        "empty_cells_total": empty_total,
        "empty_cell_accuracy": _ratio(empty_exact, empty_total),
        "hallucinated_nonempty_cells": sum(int(item.get("hallucinated_nonempty_cells") or 0) for item in scores),
        "omitted_nonempty_cells": sum(int(item.get("omitted_nonempty_cells") or 0) for item in scores),
    }


def _combine_provenance(runs: list[dict[str, Any]]) -> dict[str, Any]:
    values = [item.get("provenance_assessment") for item in runs if isinstance(item.get("provenance_assessment"), dict)]
    returned = sum(int(item.get("returned_nonempty_cells") or 0) for item in values)
    exact = sum(int(item.get("exact_relocated_cells") or 0) for item in values)
    unique = sum(int(item.get("unique_exact_relocated_cells") or 0) for item in values)
    numeric = sum(int(item.get("numeric_returned_cells") or 0) for item in values)
    numeric_exact = sum(int(item.get("numeric_exact_relocated_cells") or 0) for item in values)
    return {
        "returned_nonempty_cells": returned,
        "exact_relocated_cells": exact,
        "exact_relocation_rate": _ratio(exact, returned),
        "unique_exact_relocated_cells": unique,
        "unique_exact_relocation_rate": _ratio(unique, returned),
        "numeric_returned_cells": numeric,
        "numeric_exact_relocated_cells": numeric_exact,
        "numeric_exact_relocation_rate": _ratio(numeric_exact, numeric),
        "strongest_individual_provenance_level": 4 if unique else 2 if returned else 0,
        "strongest_uniform_provenance_level": 4 if returned and unique == returned else 2 if returned else 0,
        "authoritative_acceptance": "rejected",
    }


def _repeatability(runs: list[dict[str, Any]]) -> dict[str, Any]:
    groups = []
    for key in REPEAT_TARGET_KEYS:
        page, order = (int(value) for value in key.split(":"))
        pair = sorted(
            [item for item in runs if item.get("arm") == "targeted" and item.get("page") == page and item.get("order") == order],
            key=lambda item: int(item.get("repeat") or 0),
        )
        groups.append(
            {
                "table_key": key,
                "runs": len(pair),
                "both_artifacts_accepted": len(pair) == 2 and all(item.get("artifact_status") == "accepted" for item in pair),
                "identical_artifact_hash": len(pair) == 2 and bool(pair[0].get("artifact_hash")) and pair[0].get("artifact_hash") == pair[1].get("artifact_hash"),
                "identical_raw_response_hash": len(pair) == 2 and bool(pair[0].get("response_hash")) and pair[0].get("response_hash") == pair[1].get("response_hash"),
            }
        )
    return {
        "groups": groups,
        "groups_total": len(groups),
        "groups_with_two_accepted_artifacts": sum(item["both_artifacts_accepted"] for item in groups),
        "groups_with_identical_artifact_hash": sum(item["identical_artifact_hash"] for item in groups),
    }


def _hybrid_control(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "unavailable"}
    value = json.loads(path.read_text(encoding="utf-8"))
    runs = [
        item
        for item in value.get("vlm_runs", [])
        if item.get("arm") == "hybrid" and item.get("provider_status") == "passed"
    ]
    chosen = []
    for key in TARGET_KEYS:
        preferred_dpi = 200 if key == "1:3" else 150
        match = next(
            (item for item in runs if item.get("table_key") == key and item.get("dpi") == preferred_dpi),
            None,
        )
        if match:
            chosen.append(match["score"])
    cells_exact = sum(int(item.get("cells_exact") or 0) for item in chosen)
    cells_total = sum(int(item.get("cells_total") or 0) for item in chosen)
    numeric_exact = sum(int(item.get("numeric_exact") or 0) for item in chosen)
    numeric_total = sum(int(item.get("numeric_total") or 0) for item in chosen)
    return {
        "status": "available",
        "policy": "150_dpi_primary_with_200_dpi_for_1_3_structure_failure",
        "tables": len(chosen),
        "exact_structures": sum(bool(item.get("structure_exact")) for item in chosen),
        "exact_headers": sum(bool(item.get("header_structure_exact")) for item in chosen),
        "cells_exact": cells_exact,
        "cells_total": cells_total,
        "cell_accuracy": _ratio(cells_exact, cells_total),
        "numeric_exact": numeric_exact,
        "numeric_total": numeric_total,
        "numeric_accuracy": _ratio(numeric_exact, numeric_total),
        "hallucinated_nonempty_cells": sum(int(item.get("hallucinated_nonempty_cells") or 0) for item in chosen),
        "omitted_nonempty_cells": sum(int(item.get("omitted_nonempty_cells") or 0) for item in chosen),
        "strongest_provenance": "Level 4 candidate-bound",
        "reference_status": "agent_visual_reviewed_pending_human_signoff",
    }


def _discarded_preflight(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "absent", "jobs": 0}
    values = _read_list(path)
    targeted = [
        item.get("safe", {})
        for item in values
        if isinstance(item.get("safe"), dict) and item["safe"].get("arm") == "targeted"
    ]
    return {
        "status": "preserved_excluded_from_canonical_metrics",
        "reason": "targeted_prompt_example_identity_contradicted_requested_page_and_order",
        "jobs": len(targeted),
        "providers": {
            provider: sum(item.get("provider") == provider for item in targeted)
            for provider in ("openai", "google", "anthropic")
        },
        "raw_private_responses_retained": True,
        "silent_retry": False,
    }


def _safe_identity(
    job: dict[str, Any],
    model: str,
    transport: str,
    pdf_hash: str,
    pdf_bytes: int,
    pages: int,
    prompt: str,
) -> dict[str, Any]:
    identity = {
        **job,
        "model": model,
        "transport": transport,
        "experiment_version": EXPERIMENT_VERSION,
        "prompt_version": TARGET_PROMPT_VERSION if job["arm"] == "targeted" else PROMPT_VERSION,
        "prompt_sha256": prompt_hash(prompt),
        "input_pdf_sha256": pdf_hash,
        "input_pdf_bytes": pdf_bytes,
        "input_pdf_pages": pages,
        "input_mime_type": "application/pdf",
        "strict_json_schema_used": False,
        "output_format": "plain_text_line_oriented" if job["arm"] != "explanation" else "plain_text",
        "page_removal": False,
        "crop": False,
        "raster_preprocessing": False,
        "local_text_attached": False,
        "normalized_geometry_attached": False,
        "table_projection_attached": False,
        "source_value_candidates_attached": False,
        "knowledge_rag_vector_file_search": False,
        "hidden_failover": False,
        "silent_retry": False,
        "determinism_setting": (
            "provider_default_temperature_model_deprecates_parameter"
            if job["provider"] == "anthropic"
            else "temperature_0"
        ),
    }
    identity["request_identity"] = hashlib.sha256(canonical_bytes(identity)).hexdigest()
    return identity


def _failed_outcome(job: dict[str, Any], model: str, transport: str, failure: str) -> dict[str, Any]:
    return {
        "private": {**job, "request": None, "response": None, "text": None},
        "safe": {
            **job,
            "model": model,
            "transport": transport,
            "provider_status": "failed",
            "artifact_status": "failed",
            "failure_class": failure,
            "http_status": None,
            "duration_seconds": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        },
    }


def _finish_reason(provider: str, response: dict[str, Any]) -> str:
    if provider == "openai":
        details = response.get("incomplete_details") if isinstance(response.get("incomplete_details"), dict) else {}
        reason = str(details.get("reason") or "")
        return ":".join(value for value in (str(response.get("status") or ""), reason) if value)
    if provider == "google":
        candidates = response.get("candidates") if isinstance(response.get("candidates"), list) else []
        first = candidates[0] if candidates and isinstance(candidates[0], dict) else {}
        return str(first.get("finishReason") or "")
    if provider == "anthropic":
        return str(response.get("stop_reason") or "")
    return ""


def _usage_details(provider: str, response: dict[str, Any], safe: dict[str, Any]) -> dict[str, Any]:
    if provider == "google":
        usage = response.get("usageMetadata") if isinstance(response.get("usageMetadata"), dict) else {}
        reasoning = int(usage.get("thoughtsTokenCount") or 0)
        visible = int(usage.get("candidatesTokenCount") or safe.get("output_tokens") or 0)
    else:
        usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        details = usage.get("output_tokens_details") if isinstance(usage.get("output_tokens_details"), dict) else {}
        reasoning = int(details.get("reasoning_tokens", details.get("thinking_tokens")) or 0)
        visible = max(0, int(safe.get("output_tokens") or 0) - reasoning)
    return {
        "reasoning_tokens": reasoning,
        "visible_output_tokens": visible,
    }


def _output_truncated(provider: str, response: dict[str, Any]) -> bool:
    reason = _finish_reason(provider, response).lower()
    return "max_token" in reason or "max_output" in reason or "incomplete:max" in reason


def _model_present(model: str, ids: list[str]) -> bool:
    candidates = {value.removeprefix("models/") for value in ids}
    return model.removeprefix("models/") in candidates


def _job_key(value: dict[str, Any]) -> tuple[str, str, int, int, int]:
    return (
        str(value.get("provider")),
        str(value.get("arm")),
        int(value.get("page") or 0),
        int(value.get("order") or 0),
        int(value.get("repeat") or 0),
    )


def _job_sort_key(value: dict[str, Any]) -> tuple[int, int, int, int, int]:
    providers = {"openai": 0, "google": 1, "anthropic": 2}
    arms = {"explanation": 0, "inventory": 1, "monolithic": 2, "targeted": 3}
    return (
        providers.get(str(value.get("provider")), 99),
        arms.get(str(value.get("arm")), 99),
        int(value.get("page") or 0),
        int(value.get("order") or 0),
        int(value.get("repeat") or 0),
    )


def _numeric(value: str) -> bool:
    return bool(re.fullmatch(r"[+\-]?[\d\s]+(?:[.,]\d+)?", value))


def _ratio(left: int, right: int) -> float | None:
    return round(left / right, 6) if right else None


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


if __name__ == "__main__":
    raise SystemExit(main())
