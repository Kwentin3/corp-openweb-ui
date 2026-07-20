from __future__ import annotations

import argparse
import json
import mimetypes
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests


ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "docs" / "stage2" / "testdata" / "broker_reports_gate1_normalization"
DEFAULT_MODEL_ID = "test"
BASE_PIPE_ID = "broker_reports_gate1_pipe"
CASE_ID = "case_gate1_no_rag_source_intake_smoke"
PROCESS_STATUS_DEADLINE_SECONDS = 120.0
PROCESS_STATUS_REQUEST_TIMEOUT_SECONDS = 20.0
PROCESS_STATUS_POLL_INTERVAL_SECONDS = 1.0

SYNTHETIC_FILES = [
    FIXTURES / "synthetic_broker_report.txt",
    FIXTURES / "synthetic_operations.csv",
]

SYNTHETIC_MARKERS = [
    "Synthetic Person Alpha",
    "Synthetic Broker LLC",
    "SYNTH-ACCOUNT-001",
    "SYNTH-A,1",
    "synthetic_symbol,synthetic_quantity",
]

FORBIDDEN_CHAT_MARKERS = [
    *SYNTHETIC_MARKERS,
    "```json",
    '"rows"',
    '"text"',
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run synthetic live no-RAG source-intake smoke for Broker Reports Gate 1."
    )
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--workspace-model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--ssh-target", default="")
    parser.add_argument("--keep-model-config", action="store_true")
    args = parser.parse_args()

    env = _read_env(Path(args.env_file))
    base_url = _base_url(env)
    ssh_target = args.ssh_target.strip() or _default_ssh_target(env)

    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    health = session.get(_url(base_url, "/health"), timeout=20)
    health.raise_for_status()
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})

    original_model = _get_model(session, base_url, args.workspace_model_id)
    original_capabilities = _capabilities(original_model)
    uploads: list[dict[str, Any]] = []
    chat_content = ""
    model_restored = False
    model_config_changed = False
    model_after_update: dict[str, Any] | None = None

    before = _runtime_snapshot(ssh_target)
    try:
        updated_model = _with_capabilities(
            original_model,
            {
                **original_capabilities,
                "file_upload": True,
                "file_context": False,
            },
        )
        model_after_update = _update_model(session, base_url, updated_model)
        model_config_changed = True

        uploads = [_upload_file_default_processing(session, base_url, path) for path in SYNTHETIC_FILES]
        for upload in uploads:
            _wait_file_processed(session, base_url, upload["id"])
        after_processing = _runtime_snapshot(ssh_target)

        file_content_contains_extracted_text = any(
            _file_content_has_marker(session, base_url, upload["id"]) for upload in uploads
        )
        chat_content = _run_chat(session, base_url, args.workspace_model_id, uploads)
        after_chat = _runtime_snapshot(ssh_target)
    finally:
        deleted_upload_count = _delete_uploads(session, base_url, uploads)
        after_delete = _runtime_snapshot(ssh_target)
        if model_config_changed and not args.keep_model_config:
            _update_model(session, base_url, original_model)
            model_restored = True

    chat_forbidden_hits = [marker for marker in FORBIDDEN_CHAT_MARKERS if marker in chat_content]
    file_id_leaks = [
        upload["id"] for upload in uploads if upload.get("id") and str(upload["id"]) in chat_content
    ]
    chat_is_compact = bool(chat_content.strip()) and not chat_content.lstrip().startswith("{")
    pipe_received_opaque_refs = bool(uploads) and "no_files" not in chat_content

    vector_delta = _delta(after_processing["vector"], before["vector"])
    document_delta = after_processing["db"]["document_count"] - before["db"]["document_count"]
    knowledge_delta = after_processing["db"]["knowledge_count"] - before["db"]["knowledge_count"]
    file_delta = after_processing["db"]["file_count"] - before["db"]["file_count"]
    artifact_delta = after_chat["artifact_store"]["record_count"] - before["artifact_store"]["record_count"]

    native_no_rag_passed = (
        _capabilities(model_after_update or {}).get("file_upload") is True
        and _capabilities(model_after_update or {}).get("file_context") is False
        and knowledge_delta == 0
        and document_delta == 0
        and vector_delta["collections_count"] == 0
        and vector_delta["file_count"] == 0
        and not file_content_contains_extracted_text
        and chat_is_compact
        and not chat_forbidden_hits
        and not file_id_leaks
        and pipe_received_opaque_refs
        and artifact_delta > 0
    )

    summary = {
        "status": "passed" if native_no_rag_passed else "failed_native_candidate",
        "outcome": (
            "NATIVE_NO_RAG_MODE_FOUND"
            if native_no_rag_passed
            else "NATIVE_NO_RAG_MODE_NOT_FOUND"
        ),
        "recommendation": (
            "READY_FOR_CUSTOMER_APPROVED_TEST_PACKAGE"
            if native_no_rag_passed
            else "PROJECT_OWNED_PRIVATE_INTAKE_RECOMMENDED"
        ),
        "workspace_model": {
            "id": args.workspace_model_id,
            "base_model_id": original_model.get("base_model_id"),
            "original_capabilities": {
                "file_upload": original_capabilities.get("file_upload"),
                "file_context": original_capabilities.get("file_context"),
            },
            "tested_capabilities": {
                "file_upload": _capabilities(model_after_update or {}).get("file_upload"),
                "file_context": _capabilities(model_after_update or {}).get("file_context"),
            },
            "knowledge_attachments_count": _knowledge_attachments_count(model_after_update or original_model),
            "model_config_restored": model_restored,
        },
        "synthetic_files": {
            "count": len(SYNTHETIC_FILES),
            "roles": ["synthetic text-like broker report", "synthetic csv operations table"],
            "customer_documents_used": False,
        },
        "counters": {
            "before": _safe_counter_view(before),
            "after_processing": _safe_counter_view(after_processing),
            "after_chat": _safe_counter_view(after_chat),
            "after_delete": _safe_counter_view(after_delete),
            "deltas_after_processing": {
                "file_rows": file_delta,
                "document_rows": document_delta,
                "knowledge_rows": knowledge_delta,
                "vector": vector_delta,
            },
            "artifact_store_records_delta_after_chat": artifact_delta,
        },
        "proof": {
            "file_context_false_applied": _capabilities(model_after_update or {}).get("file_context")
            is False,
            "file_upload_true_applied": _capabilities(model_after_update or {}).get("file_upload")
            is True,
            "knowledge_attachments_zero": _knowledge_attachments_count(model_after_update or original_model)
            == 0,
            "vector_db_delta_for_case_zero": vector_delta["collections_count"] == 0
            and vector_delta["file_count"] == 0,
            "knowledge_delta_zero": knowledge_delta == 0,
            "document_delta_zero": document_delta == 0,
            "uploaded_file_data_contains_extracted_synthetic_text": file_content_contains_extracted_text,
            "pipe_received_opaque_refs": pipe_received_opaque_refs,
            "chat_compact_report": chat_is_compact,
            "chat_full_json_primary_output": chat_content.lstrip().startswith("{"),
            "chat_forbidden_marker_count": len(chat_forbidden_hits),
            "chat_file_id_leak_count": len(file_id_leaks),
            "artifactstore_records_delta_positive": artifact_delta > 0,
            "source_uploads_deleted_after_smoke": deleted_upload_count == len(uploads),
        },
        "forbidden_work": {
            "source_fact_extraction_performed": False,
            "tax_correctness_claimed": False,
            "declaration_generated": False,
            "xlsx_generated": False,
            "ocr_performed": False,
            "customer_bulk_upload_repeated": False,
            "global_rag_disabled": False,
            "openwebui_core_patched": False,
            "sidecar_ui_created": False,
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if native_no_rag_passed else 2


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _base_url(env: dict[str, str]) -> str:
    host = env.get("OPENWEBUI_HOST", "").strip().rstrip("/")
    if not host:
        raise RuntimeError("OPENWEBUI_HOST_missing")
    return host if host.startswith(("http://", "https://")) else f"https://{host}"


def _default_ssh_target(env: dict[str, str]) -> str:
    host = env.get("OPENWEBUI_HOST", "").strip()
    if not host:
        raise RuntimeError("OPENWEBUI_HOST_missing_for_ssh")
    return host if "@" in host else f"root@{host}"


def _signin(session: requests.Session, base_url: str, env: dict[str, str]) -> str:
    response = session.post(
        _url(base_url, "/api/v1/auths/signin"),
        json={"email": env.get("WEBUI_ADMIN_EMAIL", ""), "password": env.get("WEBUI_ADMIN_PASSWORD", "")},
        timeout=30,
    )
    response.raise_for_status()
    token = response.json().get("token")
    if not token:
        raise RuntimeError("signin_token_missing")
    return str(token)


def _get_model(session: requests.Session, base_url: str, model_id: str) -> dict[str, Any]:
    response = session.get(_url(base_url, f"/api/v1/models/model?id={model_id}"), timeout=30)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or data.get("id") != model_id:
        raise RuntimeError("workspace_model_response_invalid")
    return data


def _update_model(session: requests.Session, base_url: str, model: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "id": model["id"],
        "base_model_id": model.get("base_model_id"),
        "name": model.get("name") or model["id"],
        "meta": model.get("meta") if isinstance(model.get("meta"), dict) else {},
        "params": model.get("params") if isinstance(model.get("params"), dict) else {},
        "access_grants": model.get("access_grants"),
        "is_active": bool(model.get("is_active", True)),
    }
    response = session.post(_url(base_url, "/api/v1/models/model/update"), json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or data.get("id") != model["id"]:
        raise RuntimeError("workspace_model_update_response_invalid")
    return data


def _capabilities(model: dict[str, Any]) -> dict[str, Any]:
    meta = model.get("meta") if isinstance(model.get("meta"), dict) else {}
    capabilities = meta.get("capabilities") if isinstance(meta.get("capabilities"), dict) else {}
    return dict(capabilities)


def _with_capabilities(model: dict[str, Any], capabilities: dict[str, Any]) -> dict[str, Any]:
    updated = dict(model)
    meta = dict(updated.get("meta") if isinstance(updated.get("meta"), dict) else {})
    meta["capabilities"] = capabilities
    updated["meta"] = meta
    return updated


def _knowledge_attachments_count(model: dict[str, Any]) -> int:
    meta = model.get("meta") if isinstance(model.get("meta"), dict) else {}
    knowledge = meta.get("knowledge")
    return len(knowledge) if isinstance(knowledge, list) else 0


def _upload_file_default_processing(
    session: requests.Session, base_url: str, path: Path
) -> dict[str, Any]:
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    with path.open("rb") as handle:
        response = session.post(
            _url(base_url, "/api/v1/files/"),
            files={"file": (path.name, handle, mime_type)},
            timeout=60,
        )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or not data.get("id"):
        raise RuntimeError("upload_response_invalid")
    return {
        "id": str(data["id"]),
        "filename": str(data.get("filename") or data.get("name") or path.name),
        "mime_type": str(data.get("mime_type") or data.get("content_type") or mime_type),
        "size": data.get("size") or path.stat().st_size,
    }


def _wait_file_processed(session: requests.Session, base_url: str, file_id: str) -> None:
    deadline = time.monotonic() + PROCESS_STATUS_DEADLINE_SECONDS
    last_status = "pending"
    while time.monotonic() < deadline:
        try:
            response = session.get(
                _url(base_url, f"/api/v1/files/{file_id}/process/status"),
                timeout=PROCESS_STATUS_REQUEST_TIMEOUT_SECONDS,
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_status = f"transient_{type(exc).__name__}"
            time.sleep(PROCESS_STATUS_POLL_INTERVAL_SECONDS)
            continue
        response.raise_for_status()
        status = str(response.json().get("status") or "pending")
        last_status = status
        if status in {"completed", "failed"}:
            if status == "failed":
                raise RuntimeError("synthetic_file_processing_failed")
            return
        time.sleep(PROCESS_STATUS_POLL_INTERVAL_SECONDS)
    raise RuntimeError(f"synthetic_file_processing_timeout:{last_status}")


def _file_content_has_marker(session: requests.Session, base_url: str, file_id: str) -> bool:
    response = session.get(_url(base_url, f"/api/v1/files/{file_id}/data/content"), timeout=30)
    response.raise_for_status()
    content = str(response.json().get("content") or "")
    return any(marker in content for marker in SYNTHETIC_MARKERS)


def _run_chat(
    session: requests.Session,
    base_url: str,
    model_id: str,
    uploads: list[dict[str, Any]],
) -> str:
    files = [
        {
            "type": "file",
            "file": {
                "id": upload["id"],
                "filename": upload["filename"],
                "name": upload["filename"],
                "mime_type": upload["mime_type"],
                "content_type": upload["mime_type"],
                "size": upload["size"],
            },
        }
        for upload in uploads
    ]
    payload = {
        "model": model_id,
        "stream": False,
        "case_id": CASE_ID,
        "metadata": {"case_id": CASE_ID},
        "messages": [
            {
                "role": "user",
                "content": "Gate 1 normalization\nartifactstore retention smoke\nno-rag source intake smoke",
                "files": files,
            }
        ],
        "files": files,
    }
    response = session.post(_url(base_url, "/api/chat/completions"), json=payload, timeout=180)
    response.raise_for_status()
    content = _extract_content(response.json())
    if not content:
        raise RuntimeError("chat_content_missing")
    return content


def _extract_content(data: Any) -> str:
    if isinstance(data, dict):
        if isinstance(data.get("content"), str):
            return data["content"]
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            choice = choices[0]
            message = choice.get("message") if isinstance(choice, dict) else None
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
    return ""


def _delete_uploads(session: requests.Session, base_url: str, uploads: list[dict[str, Any]]) -> int:
    deleted = 0
    for upload in uploads:
        file_id = upload.get("id")
        if not file_id:
            continue
        response = session.delete(_url(base_url, f"/api/v1/files/{file_id}"), timeout=30)
        if response.status_code in {200, 204}:
            deleted += 1
    return deleted


def _runtime_snapshot(ssh_target: str) -> dict[str, Any]:
    code = r'''
import json
import os
import sqlite3
from pathlib import Path

def db_count(conn, table):
    try:
        return int(conn.execute(f"select count(*) from {table}").fetchone()[0])
    except Exception:
        return 0

def tree_stats(path):
    root = Path(path)
    if not root.exists():
        return {"exists": False, "file_count": 0, "dir_count": 0, "size_bytes": 0, "collections_count": 0}
    file_count = 0
    dir_count = 0
    size_bytes = 0
    for current, dirs, files in os.walk(root):
        dir_count += len(dirs)
        for name in files:
            file_count += 1
            try:
                size_bytes += (Path(current) / name).stat().st_size
            except OSError:
                pass
    collections_count = 0
    chroma = root / "chroma.sqlite3"
    if chroma.exists():
        try:
            with sqlite3.connect(chroma) as conn:
                collections_count = int(conn.execute("select count(*) from collections").fetchone()[0])
        except Exception:
            collections_count = 0
    return {
        "exists": True,
        "file_count": file_count,
        "dir_count": dir_count,
        "size_bytes": size_bytes,
        "collections_count": collections_count,
    }

db_path = "/app/backend/data/webui.db"
db = {"file_count": 0, "document_count": 0, "knowledge_count": 0}
try:
    with sqlite3.connect(db_path) as conn:
        db = {
            "file_count": db_count(conn, "file"),
            "document_count": db_count(conn, "document"),
            "knowledge_count": db_count(conn, "knowledge"),
        }
except Exception:
    pass

artifact_store = {"record_count": 0}
artifact_db = Path("/app/backend/data/broker_reports_gate1/artifacts.sqlite3")
if artifact_db.exists():
    try:
        with sqlite3.connect(artifact_db) as conn:
            artifact_store["record_count"] = db_count(conn, "artifact_records")
    except Exception:
        pass

print(json.dumps({
    "db": db,
    "vector": tree_stats("/app/backend/data/vector_db"),
    "artifact_store": artifact_store,
}, sort_keys=True))
'''
    proc = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "StrictHostKeyChecking=no",
            ssh_target,
            "docker",
            "exec",
            "-i",
            "openwebui",
            "python",
            "-",
        ],
        input=code,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError("runtime_snapshot_failed")
    return json.loads(proc.stdout)


def _safe_counter_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "file_rows": snapshot["db"]["file_count"],
        "document_rows": snapshot["db"]["document_count"],
        "knowledge_rows": snapshot["db"]["knowledge_count"],
        "vector_file_count": snapshot["vector"]["file_count"],
        "vector_dir_count": snapshot["vector"]["dir_count"],
        "vector_collections_count": snapshot["vector"]["collections_count"],
        "vector_size_bytes": snapshot["vector"]["size_bytes"],
        "artifactstore_record_count": snapshot["artifact_store"]["record_count"],
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, int]:
    keys = ["file_count", "dir_count", "collections_count", "size_bytes"]
    return {key: int(after.get(key, 0)) - int(before.get(key, 0)) for key in keys}


def _url(base_url: str, path: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "code": str(exc)[:120],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        raise
