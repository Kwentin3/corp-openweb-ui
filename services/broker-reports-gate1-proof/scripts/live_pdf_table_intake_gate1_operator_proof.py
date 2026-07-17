#!/usr/bin/env python3
"""Prove the supported PDF table detection/crop path through live OpenWebUI."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]
FUNCTION_ID = "broker_reports_gate1_pipe"
DEFAULT_WORKSPACE_MODEL_ID = "test"
ARTIFACT_DB = "/app/backend/data/broker_reports_gate1/artifacts.sqlite3"
PAYLOAD_ROOT = "/app/backend/data/broker_reports_gate1/payloads"

sys.path.insert(0, str(SCRIPT_DIR))

from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _default_ssh_target,
    _extract_content,
    _get_model,
    _read_env,
    _signin,
    _url,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--ssh-target", default=None)
    parser.add_argument(
        "--workspace-model-id", default=DEFAULT_WORKSPACE_MODEL_ID
    )
    parser.add_argument("--pdf", action="append", required=True)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--chat-timeout", type=int, default=2400)
    args = parser.parse_args()

    pdf_paths = [Path(value).resolve() for value in args.pdf]
    for path in pdf_paths:
        if not path.is_file() or path.suffix.lower() != ".pdf":
            raise RuntimeError(f"operator_pdf_invalid:{path}")
    revision = _repository_revision()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    case_id = f"case_pdf_table_intake_gate1_{timestamp.lower()}"
    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else ROOT
        / "local"
        / "stage2"
        / f"broker_reports_pdf_table_intake_gate1_operator_{timestamp}"
    )
    output_dir.mkdir(parents=True, exist_ok=False)

    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    ssh_target = (
        args.ssh_target
        or env.get("OPENWEBUI_SSH_TARGET")
        or _default_ssh_target(env)
    )
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})
    workspace_model = _get_model(session, base_url, args.workspace_model_id)
    if workspace_model.get("base_model_id") != FUNCTION_ID:
        raise RuntimeError("operator_workspace_model_function_mismatch")

    uploads: list[dict[str, Any]] = []
    chat_content = ""
    try:
        for ordinal, path in enumerate(pdf_paths, start=1):
            uploads.append(
                _upload_pdf(
                    session,
                    base_url,
                    path,
                    upload_filename=f"gate1-table-proof-{timestamp}-{ordinal}.pdf",
                )
            )
        chat_content = _run_chat(
            session,
            base_url,
            workspace_model_id=args.workspace_model_id,
            case_id=case_id,
            uploads=uploads,
            timeout=args.chat_timeout,
        )
        remote_evidence = _read_remote_evidence(
            ssh_target=ssh_target,
            case_id=case_id,
        )
        crop_evidence = _download_and_validate_candidates(
            ssh_target=ssh_target,
            output_dir=output_dir,
            candidates=remote_evidence.get("candidates") or [],
        )
        checks = _evaluate(
            remote_evidence=remote_evidence,
            crop_evidence=crop_evidence,
            chat_content=chat_content,
            uploads=uploads,
        )
        summary = {
            "schema_version": "broker_reports_pdf_table_intake_gate1_operator_proof_v1",
            "status": "passed" if all(checks.values()) else "failed",
            "repository_revision": revision,
            "case_id": case_id,
            "workspace_model_id": args.workspace_model_id,
            "function_id": FUNCTION_ID,
            "source_pdfs": [
                {
                    "name": path.name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "size_bytes": path.stat().st_size,
                }
                for path in pdf_paths
            ],
            "checks": checks,
            "run_summary": remote_evidence.get("run_summary"),
            "handoff": remote_evidence.get("handoff"),
            "candidate_artifacts": crop_evidence,
            "detection_attempts": remote_evidence.get("attempts"),
            "chat_compact": bool(chat_content.strip())
            and not chat_content.lstrip().startswith("{"),
            "operator_visual_review_required": True,
            "operator_visual_review_dir": str(output_dir),
        }
        (output_dir / "proof.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if summary["status"] == "passed" else 2
    finally:
        for upload in uploads:
            _delete_upload(session, base_url, str(upload.get("id") or ""))


def _repository_revision() -> str:
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if dirty:
        raise RuntimeError("operator_repository_tree_not_clean")
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _upload_pdf(
    session: requests.Session,
    base_url: str,
    path: Path,
    *,
    upload_filename: str,
) -> dict[str, Any]:
    with path.open("rb") as handle:
        response = session.post(
            _url(base_url, "/api/v1/files/?process=false"),
            files={"file": (upload_filename, handle, "application/pdf")},
            timeout=120,
        )
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict) or not value.get("id"):
        raise RuntimeError("operator_upload_response_invalid")
    return {
        "id": str(value["id"]),
        "filename": upload_filename,
        "mime_type": "application/pdf",
        "size": int(value.get("size") or path.stat().st_size),
    }


def _run_chat(
    session: requests.Session,
    base_url: str,
    *,
    workspace_model_id: str,
    case_id: str,
    uploads: list[dict[str, Any]],
    timeout: int,
) -> str:
    files = [
        {
            "type": "file",
            "file": {
                "id": upload["id"],
                "filename": upload["filename"],
                "name": upload["filename"],
                "mime_type": "application/pdf",
                "content_type": "application/pdf",
                "size": upload["size"],
            },
        }
        for upload in uploads
    ]
    response = session.post(
        _url(base_url, "/api/chat/completions"),
        json={
            "model": workspace_model_id,
            "stream": False,
            "case_id": case_id,
            "metadata": {"case_id": case_id, "files": files},
            "broker_reports_gate1": {
                "case_id": case_id,
                "retention_policy": {
                    "mode": "api_smoke",
                    "explicit": True,
                    "ttl_seconds": 24 * 60 * 60,
                },
                "customer_docs_loaded_to_knowledge": False,
                "source_fact_extraction": False,
                "ocr_vlm": False,
            },
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Gate 1 normalization. Run the supported PDF table "
                        "detection and crop path. Do not use Knowledge/RAG, "
                        "infer table cells, interpret financial values, or run Gate 2."
                    ),
                    "files": files,
                }
            ],
            "files": files,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    content = _extract_content(response.json())
    if not content:
        raise RuntimeError("operator_chat_content_missing")
    return content


def _read_remote_evidence(*, ssh_target: str, case_id: str) -> dict[str, Any]:
    code = r'''
import json
import pathlib
import sqlite3

db_path = __DB_PATH__
payload_root = pathlib.Path(__PAYLOAD_ROOT__)
case_id = __CASE_ID__
types = (
    "broker_reports_pdf_table_intake_run_v1",
    "broker_reports_pdf_table_candidate_v1",
    "broker_reports_pdf_table_detection_attempt_v1",
    "gate2_handoff_v0",
)
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
try:
    rows = conn.execute(
        "select * from artifact_records where case_id = ? and artifact_type in (?, ?, ?, ?) order by created_at asc",
        (case_id, *types),
    ).fetchall()
finally:
    conn.close()

def payload(row):
    if row["payload_ref"]:
        return json.loads((payload_root / row["payload_ref"]).read_text(encoding="utf-8"))
    return json.loads(row["payload_inline_json"] or "null")

result = {"run_summary": None, "candidates": [], "attempts": [], "handoff": None}
for row in rows:
    record = {
        "artifact_id": row["artifact_id"],
        "artifact_type": row["artifact_type"],
        "normalization_run_id": row["normalization_run_id"],
        "document_id": row["document_id"],
        "validation_status": row["validation_status"],
        "lifecycle_status": row["lifecycle_status"],
        "payload_ref": row["payload_ref"],
        "checksum_sha256": row["checksum_sha256"],
        "safe_metadata": json.loads(row["safe_metadata_json"]),
    }
    value = payload(row)
    if row["artifact_type"] == "broker_reports_pdf_table_intake_run_v1":
        result["run_summary"] = value
    elif row["artifact_type"] == "broker_reports_pdf_table_candidate_v1":
        result["candidates"].append(record)
    elif row["artifact_type"] == "broker_reports_pdf_table_detection_attempt_v1":
        result["attempts"].append({**record, "payload": value})
    elif row["artifact_type"] == "gate2_handoff_v0":
        result["handoff"] = value
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
'''
    code = (
        code.replace("__DB_PATH__", json.dumps(ARTIFACT_DB))
        .replace("__PAYLOAD_ROOT__", json.dumps(PAYLOAD_ROOT))
        .replace("__CASE_ID__", json.dumps(case_id))
    )
    completed = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "StrictHostKeyChecking=yes",
            ssh_target,
            "docker",
            "exec",
            "-i",
            "openwebui",
            "python",
            "-",
        ],
        check=True,
        capture_output=True,
        input=code,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("operator_remote_evidence_invalid")
    return value


def _download_and_validate_candidates(
    *,
    ssh_target: str,
    output_dir: Path,
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result = []
    for ordinal, record in enumerate(candidates, start=1):
        payload_ref = str(record.get("payload_ref") or "")
        if not payload_ref or "/" in payload_ref or "\\" in payload_ref:
            raise RuntimeError("operator_candidate_payload_ref_invalid")
        local_payload = output_dir / f"candidate-{ordinal:03d}.json"
        completed = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=10",
                "-o",
                "StrictHostKeyChecking=yes",
                ssh_target,
                "docker",
                "exec",
                "openwebui",
                "cat",
                f"{PAYLOAD_ROOT}/{payload_ref}",
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
        local_payload.write_bytes(completed.stdout)
        candidate = json.loads(local_payload.read_text(encoding="utf-8"))
        manifest = candidate.get("manifest") if isinstance(candidate, dict) else {}
        png = base64.b64decode(
            str(candidate.get("private_png_base64") or "").encode("ascii"),
            validate=True,
        )
        png_sha256 = hashlib.sha256(png).hexdigest()
        png_path = output_dir / f"candidate-{ordinal:03d}.png"
        png_path.write_bytes(png)
        result.append(
            {
                **{key: value for key, value in record.items() if key != "payload_ref"},
                "candidate_ref": manifest.get("candidate_ref"),
                "document_ref": manifest.get("document_ref"),
                "page_number": manifest.get("page_number"),
                "detected_bbox_normalized": manifest.get(
                    "detected_bbox_normalized"
                ),
                "rendered_bbox": manifest.get("rendered_bbox"),
                "width": manifest.get("width"),
                "height": manifest.get("height"),
                "png_bytes": len(png),
                "png_sha256": png_sha256,
                "manifest_png_sha256": manifest.get("png_sha256"),
                "png_hash_match": png_sha256 == manifest.get("png_sha256"),
                "horizontal_padding_fraction": manifest.get(
                    "horizontal_padding_fraction"
                ),
                "vertical_padding_fraction": manifest.get(
                    "vertical_padding_fraction"
                ),
                "local_png": str(png_path),
            }
        )
    return result


def _evaluate(
    *,
    remote_evidence: dict[str, Any],
    crop_evidence: list[dict[str, Any]],
    chat_content: str,
    uploads: list[dict[str, Any]],
) -> dict[str, bool]:
    summary = remote_evidence.get("run_summary")
    summary = summary if isinstance(summary, dict) else {}
    handoff = remote_evidence.get("handoff")
    handoff = handoff if isinstance(handoff, dict) else {}
    attempts = remote_evidence.get("attempts")
    attempts = attempts if isinstance(attempts, list) else []
    candidate_ids = [str(item.get("artifact_id") or "") for item in crop_evidence]
    handoff_candidate_ids = [
        str(item) for item in handoff.get("pdf_table_candidate_refs") or []
    ]
    return {
        "supported_function_boundary_used": bool(uploads),
        "chat_compact_and_private_safe": bool(chat_content.strip())
        and not chat_content.lstrip().startswith("{")
        and "private_png_base64" not in chat_content,
        "intake_status_completed": summary.get("status") == "completed",
        "gate2_boundary_ready": summary.get("gate2_boundary_ready") is True,
        "detector_exact_model_match": (
            (summary.get("detector_qualification") or {}).get("exact_model_match")
            is True
        ),
        "eight_percent_padding_configured": (
            summary.get("horizontal_padding_fraction") == 0.08
            and summary.get("vertical_padding_fraction") == 0.08
        ),
        "no_semantic_inference": summary.get("rows_columns_cells_inferred") is False
        and summary.get("financial_semantics_inferred") is False,
        "candidate_count_positive": bool(crop_evidence)
        and summary.get("candidates_total") == len(crop_evidence),
        "candidate_png_hashes_match": bool(crop_evidence)
        and all(item.get("png_hash_match") is True for item in crop_evidence),
        "candidate_artifacts_validated": bool(crop_evidence)
        and all(
            item.get("validation_status") == "validated"
            and item.get("lifecycle_status") == "private_ready"
            for item in crop_evidence
        ),
        "candidate_padding_matches_run": bool(crop_evidence)
        and all(
            item.get("horizontal_padding_fraction") == 0.08
            and item.get("vertical_padding_fraction") == 0.08
            for item in crop_evidence
        ),
        "detection_attempts_terminal": bool(attempts)
        and all(
            (item.get("payload") or {}).get("terminal_status") == "validated"
            and (item.get("payload") or {}).get("hidden_retry") is False
            and (item.get("payload") or {}).get("provider_failover") is False
            for item in attempts
        ),
        "handoff_candidate_refs_match": candidate_ids == handoff_candidate_ids,
    }


def _delete_upload(
    session: requests.Session, base_url: str, file_id: str
) -> None:
    if not file_id:
        return
    response = session.delete(_url(base_url, f"/api/v1/files/{file_id}"), timeout=30)
    if response.status_code not in {200, 204, 404}:
        response.raise_for_status()


if __name__ == "__main__":
    raise SystemExit(main())
