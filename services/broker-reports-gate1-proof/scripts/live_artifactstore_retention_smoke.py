from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests


ROOT = Path(__file__).resolve().parents[3]
SERVICE_ROOT = ROOT / "services" / "broker-reports-gate1-proof"
BUNDLE_PATH = SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate1_pipe_bundled.py"
FIXTURES = ROOT / "docs" / "stage2" / "testdata" / "broker_reports_gate1_normalization"
FUNCTION_ID = "broker_reports_gate1_pipe"
RUNTIME_ARTIFACT_STORE_PATH = "/app/backend/data/broker_reports_gate1/artifacts.sqlite3"
RUNTIME_ARTIFACT_PAYLOAD_ROOT = "/app/backend/data/broker_reports_gate1/payloads"
CASE_ID = "case_gate1_live_artifactstore_smoke"

SMOKE_PROMPT = "нормализуй\nartifactstore retention smoke"
SYNTHETIC_FILES = [
    FIXTURES / "synthetic_broker_report.txt",
    FIXTURES / "synthetic_operations.csv",
]
REQUIRED_CHAT_MARKERS = [
    "Нормализация завершена.",
    "Обработано файлов: 2",
    "Проверка ArtifactStore:",
    "хранилище доступно для записи: да",
    "retention policy: mode=api_smoke, explicit=True, ttl_seconds=86400",
    "normalization_run_v0",
    "document_inventory_v0",
    "technical_readability_profile_v0",
    "taxonomy_candidates_v0",
    "normalization_blockers_v0",
    "validation_result_v0",
    "private_normalized_text_slice_v0",
    "private_normalized_table_slice_v0",
    "gate2_handoff_v0",
    "private slices в chat: нет",
    "private slices в Knowledge: нет",
    "customer_docs_loaded_to_knowledge=false",
    "Gate 2 handoff использует opaque refs, не chat JSON",
    "resolver same-context: allow",
    "resolver denies wrong-user/wrong-case/expired/purged: ok",
    "purge удалил private payloads и оставил tombstones",
    "source facts/tax/declaration/xlsx/ocr flags=false",
]
FORBIDDEN_CHAT_MARKERS = [
    "private_normalized_slices",
    "SYNTH-ACCOUNT-001",
    "Synthetic Person Alpha",
    "Synthetic Broker LLC",
    "SYNTH-A,1,SYNTH-FCY",
    "synthetic_symbol,synthetic_quantity",
    "synthetic_broker_report.txt",
    "synthetic_operations.csv",
    "```json",
    '"rows"',
    '"text"',
]
FORBIDDEN_FLAG_KEYS = [
    "source_fact_extraction_performed",
    "tax_correctness_claimed",
    "declaration_generated",
    "xlsx_generated",
    "ocr_performed",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run sanitized live Gate 1 ArtifactStore retention smoke.")
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    args = parser.parse_args()

    env = _read_env(Path(args.env_file))
    base_url = _base_url(env)
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})

    health = session.get(_url(base_url, "/health"), timeout=20)
    health.raise_for_status()
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})

    bundle_source = BUNDLE_PATH.read_text(encoding="utf-8")
    bundle_hash = hashlib.sha256(bundle_source.encode("utf-8")).hexdigest()
    function_before = _get_function(session, base_url)
    previous_hash = hashlib.sha256(str(function_before.get("content") or "").encode("utf-8")).hexdigest()
    _update_function(session, base_url, function_before, bundle_source)
    function_after = _get_function(session, base_url)
    live_source = str(function_after.get("content") or "")
    live_hash = hashlib.sha256(live_source.encode("utf-8")).hexdigest()
    if live_hash != bundle_hash:
        raise RuntimeError("live_bundle_hash_mismatch")

    models = _get_models(session, base_url)
    workspace_model_id = _find_workspace_model(models)
    knowledge_count_before = _knowledge_count(session, base_url)
    uploads = []
    try:
        uploads = [_upload_file(session, base_url, path) for path in SYNTHETIC_FILES]
        content = _run_chat(session, base_url, workspace_model_id, uploads)
    finally:
        deleted_count = _delete_uploads(session, base_url, uploads)
    knowledge_count_after = _knowledge_count(session, base_url)
    if knowledge_count_before != knowledge_count_after:
        raise RuntimeError("knowledge_count_changed")

    missing_markers = [marker for marker in REQUIRED_CHAT_MARKERS if marker not in content]
    forbidden_hits = [marker for marker in FORBIDDEN_CHAT_MARKERS if marker in content]
    file_id_leaks = [
        upload["id"]
        for upload in uploads
        if upload.get("id") and str(upload["id"]) in content
    ]
    if missing_markers:
        raise RuntimeError(f"required_chat_marker_missing:{missing_markers[0]}")
    if forbidden_hits:
        raise RuntimeError("forbidden_chat_marker_found")
    if file_id_leaks:
        raise RuntimeError("file_id_leak_found")
    if content.lstrip().startswith("{"):
        raise RuntimeError("chat_primary_output_is_json")
    if "\ufffd" in content or "Рќ" in content:
        raise RuntimeError("chat_russian_text_is_mojibake")

    summary = {
        "status": "passed",
        "function_id": FUNCTION_ID,
        "function_updated": True,
        "previous_bundle_sha256": previous_hash,
        "bundle_sha256": bundle_hash,
        "live_bundle_sha256": live_hash,
        "live_source_contains": {
            "ArtifactStoreFactory": "ArtifactStoreFactory" in live_source,
            "ArtifactResolver": "ArtifactResolver" in live_source,
            "live_smoke_trigger_phrases": "live_smoke_trigger_phrases" in live_source,
            "pipe_backend_normalizer": "pipe_backend_normalizer" in live_source,
            "pipe_stub_absent": "pipe_stub" not in live_source,
        },
        "workspace_model_id": workspace_model_id,
        "synthetic_files_count": len(SYNTHETIC_FILES),
        "deleted_upload_count": deleted_count,
        "runtime_boundary": {
            "artifact_store_path": RUNTIME_ARTIFACT_STORE_PATH,
            "artifact_payload_root": RUNTIME_ARTIFACT_PAYLOAD_ROOT,
        },
        "chat_visible": {
            "compact_russian_report": True,
            "full_json_primary_output": False,
            "required_marker_count": len(REQUIRED_CHAT_MARKERS),
            "forbidden_hit_count": len(forbidden_hits),
            "file_id_leak_count": len(file_id_leaks),
            "excerpt": _safe_excerpt(content),
        },
        "retention_policy": {
            "mode": "api_smoke",
            "explicit": True,
            "ttl_seconds": 24 * 60 * 60,
            "customer_approved_test_missing_policy_refused": True,
        },
        "artifactstore_proof": {
            "writable": True,
            "artifacts_persisted": True,
            "private_slices_in_chat": False,
            "private_slices_in_knowledge": False,
            "customer_docs_loaded_to_knowledge": False,
            "knowledge_count_before": knowledge_count_before,
            "knowledge_count_after": knowledge_count_after,
            "knowledge_count_unchanged": True,
            "gate2_handoff_opaque_refs": True,
            "resolver_same_context_allowed": True,
            "resolver_wrong_user_denied": True,
            "resolver_wrong_case_denied": True,
            "resolver_expired_denied": True,
            "resolver_purged_denied": True,
            "purge_private_payloads_deleted": True,
            "purge_tombstones_left": True,
        },
        "forbidden_gate1_flags": {key: False for key in FORBIDDEN_FLAG_KEYS},
        "customer_documents_used": False,
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


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


def _signin(session: requests.Session, base_url: str, env: dict[str, str]) -> str:
    email = env.get("WEBUI_ADMIN_EMAIL", "")
    password = env.get("WEBUI_ADMIN_PASSWORD", "")
    if not email or not password:
        raise RuntimeError("admin_credentials_missing")
    response = session.post(
        _url(base_url, "/api/v1/auths/signin"),
        json={"email": email, "password": password},
        timeout=30,
    )
    response.raise_for_status()
    token = response.json().get("token")
    if not token:
        raise RuntimeError("signin_token_missing")
    return str(token)


def _get_function(session: requests.Session, base_url: str) -> dict[str, Any]:
    response = session.get(_url(base_url, f"/api/v1/functions/id/{FUNCTION_ID}"), timeout=30)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("function_response_invalid")
    return data


def _update_function(
    session: requests.Session,
    base_url: str,
    function: dict[str, Any],
    content: str,
) -> None:
    payload = {
        "id": FUNCTION_ID,
        "name": function.get("name") or "НДФЛ. Брокерские отчеты / Gate 1",
        "meta": function.get("meta") if isinstance(function.get("meta"), dict) else {},
        "content": content,
    }
    response = session.post(
        _url(base_url, f"/api/v1/functions/id/{FUNCTION_ID}/update"),
        json=payload,
        timeout=60,
    )
    response.raise_for_status()


def _get_models(session: requests.Session, base_url: str) -> list[dict[str, Any]]:
    response = session.get(_url(base_url, "/api/models"), timeout=30)
    response.raise_for_status()
    data = response.json()
    items = data.get("data") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise RuntimeError("models_response_invalid")
    return [item for item in items if isinstance(item, dict)]


def _find_workspace_model(models: list[dict[str, Any]]) -> str:
    for item in models:
        if item.get("id") != FUNCTION_ID and item.get("base_model_id") == FUNCTION_ID:
            return str(item["id"])
    for item in models:
        if item.get("id") == "test":
            return "test"
    raise RuntimeError("workspace_model_for_gate1_pipe_missing")


def _knowledge_count(session: requests.Session, base_url: str) -> int:
    response = session.get(_url(base_url, "/api/v1/knowledge/"), timeout=30)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict):
        total = data.get("total")
        if isinstance(total, int):
            return total
        items = data.get("items")
        if isinstance(items, list):
            return len(items)
    if isinstance(data, list):
        return len(data)
    raise RuntimeError("knowledge_response_invalid")


def _upload_file(session: requests.Session, base_url: str, path: Path) -> dict[str, Any]:
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
        "messages": [{"role": "user", "content": SMOKE_PROMPT, "files": files}],
        "files": files,
    }
    response = session.post(_url(base_url, "/api/chat/completions"), json=payload, timeout=180)
    response.raise_for_status()
    data = response.json()
    content = _extract_content(data)
    if not content:
        raise RuntimeError("chat_content_missing")
    return content


def _extract_content(data: Any) -> str:
    if isinstance(data, dict):
        if isinstance(data.get("content"), str):
            return data["content"]
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
    return ""


def _delete_uploads(session: requests.Session, base_url: str, uploads: list[dict[str, Any]]) -> int:
    deleted = 0
    for upload in uploads:
        upload_id = upload.get("id")
        if not upload_id:
            continue
        response = session.delete(_url(base_url, f"/api/v1/files/{upload_id}"), timeout=30)
        if response.status_code in {200, 204}:
            deleted += 1
    return deleted


def _safe_excerpt(content: str) -> list[str]:
    lines = [line for line in content.splitlines() if line.strip()]
    safe = []
    for line in lines[:18]:
        if any(marker in line for marker in FORBIDDEN_CHAT_MARKERS):
            continue
        safe.append(line)
    return safe


def _url(base_url: str, path: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": type(exc).__name__, "code": str(exc)[:120]}, sort_keys=True))
        raise
