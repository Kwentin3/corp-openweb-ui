#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

import fitz
import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from direct_pdf_experiment_contracts import (  # noqa: E402
    EXPERIMENT_VERSION,
    assess_business,
    business_prompt,
    business_schema,
    canonical_bytes,
    schema_hash,
    score_tables,
    table_prompt,
    table_schema,
    validate_business_output,
    validate_table_output,
)
from direct_pdf_experiment_transports import (  # noqa: E402
    PROVIDER_SPECS,
    NativePdfTransport,
    connections_from_openwebui_config,
    parse_provider_payload,
)
from live_no_rag_source_intake_smoke import _base_url, _read_env, _signin, _url  # noqa: E402


SAFE_SCHEMA = "broker_reports_direct_pdf_multi_provider_experiment_safe_v1"
PRIVATE_SCHEMA = "broker_reports_direct_pdf_multi_provider_experiment_private_v1"
MANUAL_HEADER_ROWS = {
    "1:1": 3, "1:2": 2, "1:3": 3, "2:2": 2, "3:2": 2,
    "4:1": 0, "4:2": 3, "5:3": 2, "5:4": 2,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Direct whole-PDF multi-provider research experiment")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--table-repeats", type=int, default=3)
    parser.add_argument("--max-output-tokens", type=int, default=32768)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--resume-only", action="store_true")
    args = parser.parse_args()

    pdf_path = Path(args.pdf).resolve()
    output_dir = Path(args.output_dir).resolve()
    private_dir = output_dir / "private"
    private_dir.mkdir(parents=True, exist_ok=True)
    pdf_bytes = pdf_path.read_bytes()
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()

    gridless_path = private_dir / "synthetic_gridless_fixture.pdf"
    if not gridless_path.exists():
        _create_gridless_fixture(gridless_path)
    gridless_bytes = gridless_path.read_bytes()
    gridless_hash = hashlib.sha256(gridless_bytes).hexdigest()

    table_contract = table_schema()
    business_contract = business_schema()
    jobs = _jobs(args.table_repeats)
    journal_path = private_dir / "journal.private.json"
    journal = _read_list(journal_path)
    journal = [_revalidate_checkpoint(item) for item in journal]
    _write_json(journal_path, journal)
    completed = {_job_key(item.get("safe", {})) for item in journal}

    env = _read_env(Path(args.env_file))
    base_url = _base_url(env)
    session = requests.Session()
    _signin(session, base_url, env)
    config_response = session.get(_url(base_url, "/openai/config"), timeout=30)
    config_response.raise_for_status()
    connections = connections_from_openwebui_config(config_response.json())

    qualifications = {}
    transports = {}
    for spec in PROVIDER_SPECS:
        connection = connections.get(spec.provider)
        if connection is None:
            qualifications[spec.provider] = {
                "status": "blocked", "failure_class": "openwebui_connection_missing", "model": spec.model,
            }
            continue
        transport = NativePdfTransport(connection, timeout=args.timeout)
        transports[spec.provider] = transport
        try:
            result = transport.qualify_models()
            qualifications[spec.provider] = {
                "status": "passed" if _model_present(spec.provider, spec.model, result["model_ids"]) else "blocked",
                "model": spec.model,
                "transport": spec.transport,
                "native_model_list_http_status": result["http_status"],
                "native_model_list_response_hash": result["response_hash"],
                "native_model_count": len(result["model_ids"]),
                "model_present": _model_present(spec.provider, spec.model, result["model_ids"]),
            }
        except Exception as exc:
            qualifications[spec.provider] = {
                "status": "blocked", "failure_class": type(exc).__name__, "model": spec.model, "transport": spec.transport,
            }

    if not args.resume_only:
        for job in jobs:
            if _job_key(job) in completed:
                continue
            spec = next(item for item in PROVIDER_SPECS if item.provider == job["provider"])
            transport = transports.get(spec.provider)
            if transport is None or qualifications[spec.provider]["status"] != "passed":
                outcome = _failed_outcome(job, spec.model, spec.transport, "capability_qualification_blocked")
            else:
                source_bytes = pdf_bytes if job["document"] == "broker_pdf" else gridless_bytes
                source_hash = pdf_hash if job["document"] == "broker_pdf" else gridless_hash
                prompt = table_prompt() if job["arm"] in {"tables", "gridless"} else business_prompt()
                schema = table_contract if job["arm"] in {"tables", "gridless"} else business_contract
                try:
                    private, safe = transport.invoke(
                        spec=spec,
                        pdf_bytes=source_bytes,
                        filename="document.pdf",
                        prompt=prompt,
                        schema=schema,
                        schema_name="direct_pdf_tables" if job["arm"] in {"tables", "gridless"} else "direct_pdf_business",
                        max_output_tokens=args.max_output_tokens,
                    )
                    validation_error = (
                        validate_table_output(private.get("parsed"))
                        if job["arm"] in {"tables", "gridless"}
                        else validate_business_output(private.get("parsed"))
                    )
                    if validation_error:
                        safe["provider_status"] = "failed"
                        safe["validation_error"] = validation_error
                    safe.update(_safe_identity(job, spec.model, spec.transport, source_bytes, source_hash, prompt, schema))
                    outcome = {"private": {**private, **job}, "safe": safe}
                except Exception as exc:
                    outcome = _failed_outcome(job, spec.model, spec.transport, type(exc).__name__)
                    outcome["safe"].update(_safe_identity(job, spec.model, spec.transport, source_bytes, source_hash, prompt, schema))
            journal.append(outcome)
            _write_json(journal_path, journal)

    reference = _table_reference(pdf_path)
    gridless_reference = _gridless_reference()
    document = fitz.open(pdf_path)
    page_texts = [page.get_text("text") for page in document]
    safe_runs = []
    for item in journal:
        private = item.get("private") if isinstance(item.get("private"), dict) else {}
        safe = dict(item.get("safe")) if isinstance(item.get("safe"), dict) else {}
        if safe.get("arm") == "tables":
            safe["score"] = score_tables(reference, private.get("parsed"))
            safe["raw_shape_diagnostic"] = _raw_table_shape_diagnostic(private.get("parsed"), reference)
        elif safe.get("arm") == "gridless":
            safe["score"] = score_tables(gridless_reference, private.get("parsed"))
        elif safe.get("arm") == "business":
            safe["assessment"] = assess_business(private.get("parsed"), page_texts)
            safe["raw_shape_diagnostic"] = _raw_business_shape_diagnostic(private.get("parsed"))
        safe_runs.append(safe)

    previous = _previous_arms(REPO_ROOT / "local/stage2/broker_reports_pdf_normalization_acceptance_2026-07-12/experiment/experiment.safe.json")
    private_result = {
        "schema_version": PRIVATE_SCHEMA,
        "experiment_version": EXPERIMENT_VERSION,
        "journal": journal,
        "reference": reference,
        "gridless_reference": gridless_reference,
    }
    _write_json(private_dir / "experiment.private.json", private_result)
    terminal = len(safe_runs) == len(jobs)
    all_passed = terminal and all(item.get("provider_status") == "passed" for item in safe_runs)
    safe_result = {
        "schema_version": SAFE_SCHEMA,
        "experiment_version": EXPERIMENT_VERSION,
        "status": "passed" if all_passed else "completed_with_failures" if terminal else "partial",
        "source": {
            "pdf_sha256": pdf_hash,
            "pdf_bytes": len(pdf_bytes),
            "pages": len(document),
            "identical_bytes_for_all_provider_jobs": all(
                item.get("input_pdf_sha256") in {pdf_hash, gridless_hash} for item in safe_runs
            ),
        },
        "gridless_fixture": {
            "kind": "controlled_synthetic_gridless_table",
            "sha256": gridless_hash,
            "bytes": len(gridless_bytes),
            "human_data": False,
        },
        "reference_status": {
            "table_reference": "agent_visual_reviewed_pending_human_signoff",
            "business_reference": "not_human_reviewed",
            "authoritative_accuracy_claims_allowed": False,
        },
        "qualifications": qualifications,
        "runs": safe_runs,
        "aggregates": _aggregates(safe_runs),
        "previous_arms": previous,
        "storage": _storage(private_result, safe_runs),
        "guards": {
            "production_pdf_pipeline_changed": False,
            "openwebui_core_changed": False,
            "knowledge_rag_vector_used": False,
            "normalized_geometry_sent": False,
            "table_projection_sent": False,
            "raster_crop_sent": False,
            "locally_extracted_text_sent": False,
            "provider_file_search_used": False,
            "hidden_failover_used": False,
            "raw_customer_data_in_safe_output": False,
        },
    }
    _write_json(output_dir / "experiment.safe.json", safe_result)
    print(json.dumps(safe_result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if terminal else 2


def _jobs(repeats: int) -> list[dict[str, Any]]:
    if repeats < 1:
        raise ValueError("table_repeats_invalid")
    jobs = []
    for spec in PROVIDER_SPECS:
        for ordinal in range(1, repeats + 1):
            jobs.append({"provider": spec.provider, "arm": "tables", "document": "broker_pdf", "repeat": ordinal})
        jobs.append({"provider": spec.provider, "arm": "business", "document": "broker_pdf", "repeat": 1})
        jobs.append({"provider": spec.provider, "arm": "gridless", "document": "gridless_fixture", "repeat": 1})
    return jobs


def _safe_identity(job: dict[str, Any], model: str, transport: str, pdf_bytes: bytes, pdf_hash: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
    identity = {
        **job,
        "model": model,
        "transport": transport,
        "experiment_version": EXPERIMENT_VERSION,
        "input_pdf_sha256": pdf_hash,
        "input_pdf_bytes": len(pdf_bytes),
        "input_mime_type": "application/pdf",
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "schema_sha256": schema_hash(schema),
        "page_removal": False,
        "crop": False,
        "raster_preprocessing": False,
        "local_text_attached": False,
        "normalized_payload_attached": False,
        "hidden_failover": False,
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
        "private": {**job, "parsed": None, "request": None, "response": None},
        "safe": {
            **job, "model": model, "transport": transport, "provider_status": "failed",
            "failure_class": failure, "http_status": None, "duration_seconds": 0,
            "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
        },
    }


def _table_reference(path: Path) -> dict[str, dict[str, Any]]:
    document = fitz.open(path)
    result = {}
    for page_index, page in enumerate(document):
        for table_index, table in enumerate(page.find_tables().tables):
            key = f"{page_index + 1}:{table_index + 1}"
            cells = [[str(value or "") for value in row] for row in table.extract()]
            columns = max((len(row) for row in cells), default=0)
            result[key] = {
                "cells": [row + [""] * (columns - len(row)) for row in cells],
                "header_rows": MANUAL_HEADER_ROWS.get(key),
            }
    return result


def _gridless_reference() -> dict[str, dict[str, Any]]:
    return {"1:1": {"header_rows": 1, "cells": [
        ["Asset", "Units", "Value"],
        ["Alpha", "10", "125.50"],
        ["Beta", "2", "40.00"],
        ["Total", "12", "165.50"],
    ]}}


def _create_gridless_fixture(path: Path) -> None:
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((72, 72), "Synthetic portfolio summary", fontsize=14)
    rows = _gridless_reference()["1:1"]["cells"]
    xs = (72, 260, 380)
    y = 120
    for row_index, row in enumerate(rows):
        for x, value in zip(xs, row):
            page.insert_text((x, y), value, fontsize=11)
        y += 28 if row_index == 0 else 24
    metadata = {"title": "Controlled gridless table fixture", "author": "Broker Reports research"}
    document.set_metadata(metadata)
    document.save(path, garbage=4, deflate=True)


def _aggregates(runs: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for provider in (spec.provider for spec in PROVIDER_SPECS):
        values = [item for item in runs if item.get("provider") == provider]
        table_values = [item for item in values if item.get("arm") == "tables"]
        hashes = {item.get("response_hash") for item in table_values if item.get("response_hash")}
        result[provider] = {
            "jobs": len(values),
            "passed_jobs": sum(item.get("provider_status") == "passed" for item in values),
            "table_repeats": len(table_values),
            "table_repeat_identical_response_hash": len(hashes) == 1 and len(table_values) > 1,
            "input_tokens": sum(int(item.get("input_tokens") or 0) for item in values),
            "output_tokens": sum(int(item.get("output_tokens") or 0) for item in values),
            "duration_seconds": round(sum(float(item.get("duration_seconds") or 0) for item in values), 3),
            "max_response_bytes": max((int(item.get("response_bytes") or 0) for item in values), default=0),
        }
    return result


def _previous_arms(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "unavailable"}
    value = json.loads(path.read_text(encoding="utf-8"))
    return {
        "status": "available",
        "deterministic": value.get("deterministic", {}).get("aggregate_score"),
        "raster": value.get("vlm_aggregates", {}).get("raster", {}).get("primary_score"),
        "hybrid": value.get("vlm_aggregates", {}).get("hybrid", {}).get("primary_score"),
    }


def _storage(private_result: dict[str, Any], safe_runs: list[dict[str, Any]]) -> dict[str, Any]:
    private_bytes = canonical_bytes(private_result)
    safe_bytes = canonical_bytes(safe_runs)
    return {
        "private_json_bytes": len(private_bytes),
        "private_gzip_bytes": len(gzip.compress(private_bytes)),
        "safe_runs_json_bytes": len(safe_bytes),
        "safe_runs_gzip_bytes": len(gzip.compress(safe_bytes)),
    }


def _revalidate_checkpoint(item: dict[str, Any]) -> dict[str, Any]:
    private = item.get("private") if isinstance(item.get("private"), dict) else {}
    safe = item.get("safe") if isinstance(item.get("safe"), dict) else {}
    provider = str(safe.get("provider") or private.get("provider") or "")
    response = private.get("response") if isinstance(private.get("response"), dict) else {}
    parsed, parse_error = parse_provider_payload(provider, response)
    private["parsed"] = parsed
    safe["parse_error"] = parse_error
    arm = str(safe.get("arm") or private.get("arm") or "")
    validation_error = (
        validate_business_output(parsed)
        if arm == "business"
        else validate_table_output(parsed)
    )
    safe["validation_error"] = validation_error
    safe["finish_reason"] = _finish_reason(provider, response)
    http_status = safe.get("http_status")
    safe["provider_status"] = (
        "passed"
        if isinstance(http_status, int) and 200 <= http_status < 300 and not parse_error and not validation_error
        else "failed"
    )
    return {"private": private, "safe": safe}


def _finish_reason(provider: str, response: dict[str, Any]) -> str:
    if provider == "openai":
        return str(response.get("status") or "")
    if provider == "google":
        candidates = response.get("candidates") if isinstance(response.get("candidates"), list) else []
        first = candidates[0] if candidates and isinstance(candidates[0], dict) else {}
        return str(first.get("finishReason") or "")
    if provider == "anthropic":
        return str(response.get("stop_reason") or "")
    return ""


def _raw_table_shape_diagnostic(value: Any, reference: dict[str, dict[str, Any]]) -> dict[str, Any]:
    tables = value.get("tables") if isinstance(value, dict) and isinstance(value.get("tables"), list) else []
    identities = {
        f"{item.get('page')}:{item.get('order_on_page')}"
        for item in tables
        if isinstance(item, dict)
        and isinstance(item.get("page"), int)
        and isinstance(item.get("order_on_page"), int)
    }
    row_mismatches = 0
    column_mismatches = 0
    for table in tables:
        if not isinstance(table, dict):
            continue
        rows = table.get("rows") if isinstance(table.get("rows"), list) else []
        row_mismatches += table.get("row_count") != len(rows)
        for row in rows:
            cells = row.get("cells") if isinstance(row, dict) and isinstance(row.get("cells"), list) else []
            column_mismatches += table.get("column_count") != len(cells)
    return {
        "returned_tables": len(tables),
        "unique_page_order_identities": len(identities),
        "reference_identities_matched": len(identities & set(reference)),
        "contains_all_reference_identities": set(reference).issubset(identities),
        "declared_row_count_mismatches": row_mismatches,
        "declared_column_count_mismatches": column_mismatches,
    }


def _raw_business_shape_diagnostic(value: Any) -> dict[str, Any]:
    domains = value.get("domains") if isinstance(value, dict) and isinstance(value.get("domains"), list) else []
    return {
        "returned_domains": len(domains),
        "unique_domain_ids": len({str(item.get("domain")) for item in domains if isinstance(item, dict)}),
        "returned_facts": sum(len(item.get("facts") or []) for item in domains if isinstance(item, dict)),
    }


def _model_present(provider: str, model: str, ids: list[str]) -> bool:
    candidates = {value.removeprefix("models/") for value in ids}
    target = model.removeprefix("models/")
    return target in candidates


def _job_key(value: dict[str, Any]) -> tuple[str, str, str, int]:
    return (
        str(value.get("provider")), str(value.get("arm")), str(value.get("document")), int(value.get("repeat") or 0),
    )


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
