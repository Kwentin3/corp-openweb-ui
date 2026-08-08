#!/usr/bin/env python3
"""Run the explicitly authorized G3.4 one-attempt real-corpus proof."""

from __future__ import annotations

import argparse
import asyncio
import copy
from dataclasses import asdict, is_dataclass
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    CanonicalReaderFactory,
    Gate3BoundedLabelingFactory,
    Gate3FinancialLabelDictionaryFactory,
    Gate3ProjectionFactory,
)
from broker_reports_gate1.gate2_model_clients import (  # noqa: E402
    Gate2StructuredModelClientFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2StructuredModelClientConfig,
    gate2_provider_profile,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    GATE3_BOUNDED_LABELING_REQUEST_PROFILE,
)
from broker_reports_gate1.gate3_bounded_labeling import (  # noqa: E402
    GATE3_LABELING_INSTRUCTION,
)
from live_gate2_economy_contract_qualification import (  # noqa: E402
    _completion_boundary,
    _published_model_ids,
    _request_context,
)
from live_gate2_synthetic_extraction_smoke import _current_user  # noqa: E402
from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _read_env,
    _signin,
    _url,
)


FACTORY_REQUIRED = (
    "Gate3BoundedLabelingFactory.create and the existing "
    "Gate2StructuredModelClientFactory.create are the only live execution "
    "path; CanonicalReaderFactory supplies private audit evidence"
)
FORBIDDEN = (
    "This proof must not retry, repair, fall back, slice canonical documents, "
    "persist annotations, mutate ArtifactStore, activate a product route or "
    "write private evidence inside Git"
)

DEFAULT_PROVIDER_PROFILE_ID = "google_gemini"
DEFAULT_MODEL_ID = "models/gemini-3.5-flash"
DEFAULT_DOCUMENT_IDS = (
    "brdoc_003_be6168a763cd",
    "brdoc_013_21c85fa3ff06",
    "brdoc_015_8b29ff7a464f",
    "brdoc_016_cee60e388015",
)
DEFAULT_CONTEXT = {
    "user_id": "doc29-approved-cohort-user",
    "case_id": "doc29-approved-cohort",
    "workspace_model_id": "doc29-canonical-shadow",
    "normalization_run_id": "normrun_046152421c699e38",
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run G3.4 real canonical labeling with no retry or persistence."
    )
    parser.add_argument("--execute-one-attempt-corpus", action="store_true")
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument(
        "--store-root",
        default=str(
            REPO_ROOT
            / "local"
            / "stage2"
            / "broker_reports_doc29_local_restore_2026-08-05"
        ),
    )
    parser.add_argument(
        "--private-evidence-dir",
        default=str(
            Path.home()
            / ".codex"
            / "private-evidence"
            / "broker-reports-g3.4-20260807-v1"
        ),
    )
    parser.add_argument(
        "--safe-receipt-path",
        default=str(
            REPO_ROOT
            / "docs"
            / "reports"
            / "2026-08-07"
            / "BROKER_REPORTS_GATE3_BOUNDED_LABELING_G3_4.receipt.safe.json"
        ),
    )
    parser.add_argument("--provider-profile-id", default=DEFAULT_PROVIDER_PROFILE_ID)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--maximum-projection-chars", type=int, default=500_000)
    parser.add_argument("--document-id", action="append", dest="document_ids")
    args = parser.parse_args()

    if not args.execute_one_attempt_corpus:
        raise SystemExit("explicit_execute_flag_required")
    if args.timeout_seconds < 1 or args.timeout_seconds > 600:
        raise SystemExit("timeout_out_of_bounds")

    private_root = Path(args.private_evidence_dir).resolve()
    safe_receipt_path = Path(args.safe_receipt_path).resolve()
    store_root = Path(args.store_root).resolve()
    if _is_within(private_root, REPO_ROOT.resolve()):
        raise SystemExit("private_evidence_must_be_outside_repository")
    if private_root.exists() and any(private_root.iterdir()):
        raise SystemExit("private_evidence_directory_must_be_new_or_empty")
    if not _is_within(safe_receipt_path, REPO_ROOT.resolve()):
        raise SystemExit("safe_receipt_must_be_inside_repository")
    if not (store_root / "artifacts.sqlite3").is_file():
        raise SystemExit("canonical_store_unavailable")

    provider_profile = gate2_provider_profile(args.provider_profile_id)
    if args.model_id not in provider_profile.approved_model_ids:
        raise SystemExit("exact_model_not_approved_for_provider_profile")
    document_ids = tuple(args.document_ids or DEFAULT_DOCUMENT_IDS)
    if not document_ids or len(document_ids) != len(set(document_ids)):
        raise SystemExit("document_selection_invalid")

    private_root.mkdir(parents=True, exist_ok=True)
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=store_root / "artifacts.sqlite3",
            payload_root=store_root / "payloads",
        )
    ).create()
    artifact_context = ArtifactAccessContext(
        user_id=DEFAULT_CONTEXT["user_id"],
        case_id=DEFAULT_CONTEXT["case_id"],
        chat_id=None,
        workspace_model_id=DEFAULT_CONTEXT["workspace_model_id"],
        normalization_run_id=DEFAULT_CONTEXT["normalization_run_id"],
        allow_private=True,
    )

    env = _read_env(Path(args.env_file))
    base_url = _base_url(env)
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    health = session.get(_url(base_url, "/health"), timeout=20)
    health.raise_for_status()
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})
    if args.model_id not in _published_model_ids(session, base_url):
        raise SystemExit("exact_model_not_published")
    live_user = _current_user(session, base_url)
    live_user_id = str(live_user.get("id") or "")
    if not live_user_id:
        raise SystemExit("authenticated_user_missing")

    submission_counter = {"count": 0}
    base_completion = _completion_boundary(
        session=session,
        base_url=base_url,
        timeout=args.timeout_seconds,
    )

    def one_attempt_completion(*, form_data, **kwargs):
        submission_counter["count"] += 1
        return base_completion(form_data=form_data, **kwargs)

    model_client = Gate2StructuredModelClientFactory(
        config=Gate2StructuredModelClientConfig(
            request_profile=GATE3_BOUNDED_LABELING_REQUEST_PROFILE,
            provider_profile_id=args.provider_profile_id,
            capability_probe=False,
            economy_budget_enforcement=False,
        ),
        user=SimpleNamespace(id=live_user_id),
        request=_request_context(session, base_url),
        completion_resolver=lambda _user_id: (
            one_attempt_completion,
            SimpleNamespace(id=live_user_id),
        ),
    ).create()
    factory = Gate3BoundedLabelingFactory(
        store=store,
        read_enabled=True,
        model_client=model_client,
        model_id=args.model_id,
    )
    reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
    dictionary_owner = Gate3FinancialLabelDictionaryFactory.create()
    dictionary = dictionary_owner.load_published("1.0.0")
    dictionary_markdown = dictionary_owner.render_model_markdown("1.0.0")
    preflight: dict[str, tuple[Any, dict[str, Any]]] = {}
    for document_id in document_ids:
        envelope = reader.read_active_envelope(document_id, artifact_context)
        projection = Gate3ProjectionFactory(
            store=store,
            read_enabled=True,
        ).create(document_id=document_id, context=artifact_context)
        if len(projection["model_view"]["content"]) > args.maximum_projection_chars:
            raise SystemExit("selected_projection_exceeds_bounded_input")
        preflight[document_id] = (envelope, projection)

    safe_attempts: list[dict[str, Any]] = []
    for index, document_id in enumerate(document_ids, start=1):
        before = _store_snapshot(store, reader, artifact_context, document_id)
        envelope, projection = preflight[document_id]
        submissions_before = submission_counter["count"]
        private_evidence: dict[str, Any] = {
            "schema_version": "broker_reports_gate3_labeling_private_evidence_v1",
            "attempt_index": index,
            "document_id": document_id,
            "canonical_envelope": _jsonable(envelope),
            "projection": copy.deepcopy(projection),
            "dictionary": copy.deepcopy(dictionary),
            "dictionary_markdown": dictionary_markdown,
            "instruction": GATE3_LABELING_INSTRUCTION,
            "provider_profile_id": args.provider_profile_id,
            "model_id": args.model_id,
        }
        status = "provider_failed"
        validation_status = None
        validation_error_code = None
        annotations_validated = 0
        labels: list[str] = []
        metrics: dict[str, Any] = {}
        execution_metadata = None
        error_code = None
        try:
            attempt = asyncio.run(
                factory.create(
                    document_id=document_id,
                    context=artifact_context,
                )
            )
            status = "completed"
            validation_status = attempt.validation_status
            validation_error_code = attempt.validation_error_code
            metrics = copy.deepcopy(attempt.metrics)
            execution_metadata = attempt.execution_metadata.snapshot()
            annotations = (
                attempt.validated_output.get("annotations") or []
                if attempt.validated_output is not None
                else []
            )
            annotations_validated = len(annotations)
            labels = sorted(
                {
                    str(item.get("financial_label") or "")
                    for item in annotations
                    if isinstance(item, dict)
                }
            )
            private_evidence.update(
                {
                    "model_visible_request": attempt.model_visible_request,
                    "final_provider_request": attempt.final_provider_request,
                    "raw_provider_response": attempt.raw_provider_response,
                    "raw_model_output": attempt.raw_model_output,
                    "validated_output": attempt.validated_output,
                    "validation_status": validation_status,
                    "validation_error_code": validation_error_code,
                    "execution_metadata": execution_metadata,
                    "metrics": metrics,
                }
            )
        except Exception as exc:  # terminal evidence, never retry
            error_code = str(getattr(exc, "code", exc.__class__.__name__))
            prepared = getattr(exc, "prepared_request", None)
            final_provider_request = (
                copy.deepcopy(prepared.form_data)
                if prepared is not None and hasattr(prepared, "form_data")
                else None
            )
            private_evidence.update(
                {
                    "model_visible_request": _sealed_view(final_provider_request),
                    "final_provider_request": final_provider_request,
                    "raw_provider_response": copy.deepcopy(
                        getattr(exc, "raw_provider_response", None)
                    ),
                    "raw_model_output": copy.deepcopy(
                        getattr(exc, "raw_output", None)
                    ),
                    "validated_output": None,
                    "validation_status": None,
                    "validation_error_code": None,
                    "execution_metadata": _jsonable(
                        getattr(exc, "execution_metadata", None)
                    ),
                    "metrics": {},
                    "terminal_error": {
                        "error_type": exc.__class__.__name__,
                        "error_code": error_code,
                        "error_args": _jsonable(exc.args),
                    },
                }
            )
        submissions = submission_counter["count"] - submissions_before
        after = _store_snapshot(store, reader, artifact_context, document_id)
        lifecycle_unchanged = before == after
        private_evidence["provider_submissions"] = submissions
        private_evidence["store_before"] = before
        private_evidence["store_after"] = after
        private_evidence["store_unchanged"] = lifecycle_unchanged
        evidence_bytes = _json_bytes(private_evidence)
        evidence_path = private_root / f"attempt-{index:02d}-{document_id}.private.json"
        _atomic_write(evidence_path, evidence_bytes)
        safe_attempts.append(
            {
                "attempt_index": index,
                "document_id": document_id,
                "canonical_version_id": envelope.canonical_version_id,
                "canonical_root_sha256": envelope.canonical_root_sha256,
                "source_format": str(
                    (envelope.artifact.get("source") or {}).get("source_format")
                    or ""
                ),
                "projection_chars": len(projection["model_view"]["content"]),
                "target_aliases": len(projection["target_mappings"]),
                "provider_submissions": submissions,
                "status": status,
                "validation_status": validation_status,
                "validation_error_code": validation_error_code,
                "error_code": error_code,
                "annotations_validated": annotations_validated,
                "labels_observed": labels,
                "dictionary_injection_count": metrics.get(
                    "dictionary_injection_count"
                ),
                "meaningful_context_parts": metrics.get(
                    "meaningful_context_parts"
                ),
                "input_tokens": (execution_metadata or {}).get("input_tokens"),
                "output_tokens": (execution_metadata or {}).get("output_tokens"),
                "total_tokens": (execution_metadata or {}).get("total_tokens"),
                "store_unchanged": lifecycle_unchanged,
                "private_evidence_sha256": hashlib.sha256(evidence_bytes).hexdigest(),
            }
        )

    receipt = {
        "schema_version": "broker_reports_gate3_bounded_labeling_safe_receipt_v1",
        "goal": "G3.4",
        "execution_policy": "one_attempt_no_retry_no_repair_no_fallback",
        "provider_profile_id": args.provider_profile_id,
        "model_id": args.model_id,
        "documents_planned": len(document_ids),
        "provider_submissions_total": submission_counter["count"],
        "private_evidence_available": True,
        "private_evidence_location_committed": False,
        "attempts": safe_attempts,
        "all_store_snapshots_unchanged": all(
            item["store_unchanged"] for item in safe_attempts
        ),
        "all_calls_single_submission": all(
            item["provider_submissions"] == 1 for item in safe_attempts
        ),
        "dictionary_injection_counts": sorted(
            {
                item["dictionary_injection_count"]
                for item in safe_attempts
                if item["dictionary_injection_count"] is not None
            }
        ),
        "meaningful_context_part_counts": sorted(
            {
                item["meaningful_context_parts"]
                for item in safe_attempts
                if item["meaningful_context_parts"] is not None
            }
        ),
    }
    _atomic_write(safe_receipt_path, _json_bytes(receipt))
    print(
        json.dumps(
            {
                "status": "finished",
                "documents_planned": len(document_ids),
                "provider_submissions_total": submission_counter["count"],
                "validated_attempts": sum(
                    item["validation_status"] == "validated"
                    for item in safe_attempts
                ),
                "rejected_attempts": sum(
                    item["validation_status"] == "rejected"
                    for item in safe_attempts
                ),
                "provider_failures": sum(
                    item["status"] == "provider_failed" for item in safe_attempts
                ),
                "all_store_snapshots_unchanged": receipt[
                    "all_store_snapshots_unchanged"
                ],
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


def _store_snapshot(store, reader, context, document_id: str) -> dict[str, Any]:
    envelope = reader.read_active_envelope(document_id, context)
    return {
        "canonical_version_id": envelope.canonical_version_id,
        "canonical_root_sha256": envelope.canonical_root_sha256,
        "canonical_versions_total": len(reader.history(document_id, context)),
        "run_artifact_records_total": len(
            store.list_by_run(context.normalization_run_id)
        ),
    }


def _sealed_view(final_provider_request: Any) -> dict[str, Any] | None:
    if not isinstance(final_provider_request, dict):
        return None
    if "system" in final_provider_request:
        messages = [
            {"role": "system", "content": final_provider_request["system"]},
            *copy.deepcopy(final_provider_request.get("messages") or []),
        ]
        response_format = copy.deepcopy(final_provider_request.get("output_config"))
    else:
        messages = copy.deepcopy(final_provider_request.get("messages"))
        response_format = copy.deepcopy(final_provider_request.get("response_format"))
    return {"messages": messages, "response_format": response_format}


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            _jsonable(value),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
