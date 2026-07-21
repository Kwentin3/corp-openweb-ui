#!/usr/bin/env python3
"""Prove the server-authoritative Broker Reports private-intake boundary live."""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]
ACTION_ID = "broker_reports_private_intake_action"
SYNTHETIC_BYTES = (
    b"broker_reports_private_intake_synthetic_v1\n"
    b"account=SYNTHETIC-ONLY\nvalue=123.45\n"
)

sys.path.insert(0, str(SCRIPT_DIR))

from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _default_ssh_target,
    _delta,
    _read_env,
    _runtime_snapshot,
    _safe_counter_view,
    _signin,
    _url,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--ssh-target", default=None)
    args = parser.parse_args()

    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    ssh_target = args.ssh_target or env.get("OPENWEBUI_SSH_TARGET") or _default_ssh_target(env)
    session = _authenticated_session(base_url, env)
    session.get(_url(base_url, "/health"), timeout=20).raise_for_status()

    initial = _runtime_snapshot(ssh_target)
    private_source_id = ""
    generic_source_id = ""
    knowledge_id = ""
    cleanup: dict[str, bool] = {}
    case_suffix = str(int(time.time()))
    idempotency_key = f"broker-private-live-{case_suffix}"

    try:
        first = _private_intake(session, base_url, idempotency_key, SYNTHETIC_BYTES)
        private_source_id = str(first.get("source_id") or "")
        if not private_source_id:
            raise RuntimeError("private_intake_source_id_missing")

        reload_session = _authenticated_session(base_url, env)
        replay = _private_intake(
            reload_session, base_url, idempotency_key, SYNTHETIC_BYTES
        )
        receipt_response = reload_session.get(
            _url(
                base_url,
                f"/api/v1/broker-reports/intake/{private_source_id}/receipt",
            ),
            timeout=30,
        )
        receipt_response.raise_for_status()
        receipt = receipt_response.json()

        override = _private_intake_response(
            session,
            base_url,
            f"broker-override-{case_suffix}",
            SYNTHETIC_BYTES,
            query="?process=true",
        )
        conflict = _private_intake_response(
            session,
            base_url,
            idempotency_key,
            SYNTHETIC_BYTES + b"different",
        )
        generic_source_id = _generic_process_false_upload(
            session, base_url, SYNTHETIC_BYTES
        )
        generic_action = session.post(
            _url(base_url, f"/api/chat/actions/{ACTION_ID}"),
            json=_action_body(generic_source_id, case_suffix + "-generic"),
            timeout=60,
        )

        actor_response = session.get(_url(base_url, "/api/v1/auths/"), timeout=30)
        actor_response.raise_for_status()
        actor_id = str(_json_object(actor_response).get("id") or "")
        if not actor_id:
            raise RuntimeError("authenticated_actor_id_missing")
        knowledge_id = str(uuid.uuid4())
        _create_temporary_knowledge(
            ssh_target=ssh_target,
            knowledge_id=knowledge_id,
            owner_user_id=actor_id,
            case_suffix=case_suffix,
        )

        protected_before = _runtime_snapshot(ssh_target)
        file_response = session.get(
            _url(base_url, f"/api/v1/files/{private_source_id}"), timeout=30
        )
        file_response.raise_for_status()
        file_record = file_response.json()

        native_single = session.post(
            _url(base_url, "/api/v1/retrieval/process/file"),
            json={"file_id": private_source_id},
            timeout=60,
        )
        native_content_update = session.post(
            _url(
                base_url,
                f"/api/v1/files/{private_source_id}/data/content/update",
            ),
            json={"content": "forbidden synthetic native content"},
            timeout=60,
        )
        native_batch = session.post(
            _url(base_url, "/api/v1/retrieval/process/files/batch"),
            json={"files": [file_record], "collection_name": ""},
            timeout=60,
        )
        knowledge_add = session.post(
            _url(base_url, f"/api/v1/knowledge/{knowledge_id}/file/add"),
            json={"file_id": private_source_id},
            timeout=60,
        )
        knowledge_update = session.post(
            _url(base_url, f"/api/v1/knowledge/{knowledge_id}/file/update"),
            json={"file_id": private_source_id},
            timeout=60,
        )
        knowledge_batch = session.post(
            _url(base_url, f"/api/v1/knowledge/{knowledge_id}/files/batch/add"),
            json=[{"file_id": private_source_id}],
            timeout=60,
        )
        private_action = reload_session.post(
            _url(base_url, f"/api/chat/actions/{ACTION_ID}"),
            json=_action_body(private_source_id, case_suffix + "-private"),
            timeout=60,
        )

        protected_after = _runtime_snapshot(ssh_target)
        source_state = _source_state(ssh_target, private_source_id)
        private_action_data = _json_object(private_action)
        native_batch_data = _json_object(native_batch)
        protected_delta = {
            "knowledge_rows": (
                protected_after["db"]["knowledge_count"]
                - protected_before["db"]["knowledge_count"]
            ),
            "document_rows": (
                protected_after["db"]["document_count"]
                - protected_before["db"]["document_count"]
            ),
            "vector": _delta(
                protected_after["vector"], protected_before["vector"]
            ),
        }

        checks = {
            "server_intake_eligible": first.get("eligible") is True,
            "server_intake_process_false": first.get("process") is False,
            "server_intake_all_native_sinks_false": all(
                first.get(key) is False
                for key in (
                    "native_openwebui_document_processing",
                    "knowledge_allowed",
                    "rag_allowed",
                    "embeddings_allowed",
                    "vectorization_allowed",
                )
            ),
            "retry_same_source": replay.get("source_id") == private_source_id,
            "retry_same_receipt": replay.get("receipt_id") == first.get("receipt_id"),
            "retry_marked_replayed": replay.get("replayed") is True,
            "reload_receipt_same": receipt.get("receipt_id") == first.get("receipt_id"),
            "client_override_denied": override.status_code == 400,
            "idempotency_conflict_denied": conflict.status_code == 409,
            "generic_file_action_rejected": generic_action.status_code in {400, 409, 422},
            "native_single_rejected": native_single.status_code in {400, 409},
            "native_content_update_rejected": native_content_update.status_code in {400, 409},
            "native_batch_rejected": _batch_rejected(native_batch, native_batch_data),
            "knowledge_single_add_rejected": knowledge_add.status_code in {400, 409},
            "knowledge_single_update_rejected": knowledge_update.status_code in {400, 409},
            "knowledge_batch_add_rejected": knowledge_batch.status_code in {400, 409},
            "private_action_accepted": private_action.status_code == 200,
            "private_action_receipt_verified": (
                _nested(private_action_data, "broker_reports_private_intake", "run_status")
                == "receipt_verified"
            ),
            "private_action_hides_source_id": (
                private_source_id not in json.dumps(private_action_data, sort_keys=True)
            ),
            "persisted_data_empty": source_state.get("data_empty") is True,
            "persisted_receipt_present": source_state.get("receipt_present") is True,
            "persisted_forbidden_native_keys_zero": (
                source_state.get("forbidden_native_key_count") == 0
            ),
            "knowledge_links_zero": source_state.get("knowledge_link_count") == 0,
            "rag_document_rows_zero": source_state.get("document_row_count") == 0,
            "vector_metadata_refs_zero": source_state.get("vector_metadata_ref_count") == 0,
            "embedding_queue_refs_zero": source_state.get("embedding_queue_ref_count") == 0,
            "knowledge_delta_zero": protected_delta["knowledge_rows"] == 0,
            "rag_delta_zero": protected_delta["document_rows"] == 0,
            "vector_collection_delta_zero": (
                protected_delta["vector"]["collections_count"] == 0
            ),
        }
        if not all(checks.values()):
            raise RuntimeError(f"private_intake_live_invariant_failed:{checks}")

        proof = {
            "status": "passed",
            "synthetic_only": True,
            "customer_documents_used": False,
            "checks": checks,
            "http_status": {
                "client_override": override.status_code,
                "idempotency_conflict": conflict.status_code,
                "generic_action": generic_action.status_code,
                "native_single": native_single.status_code,
                "native_content_update": native_content_update.status_code,
                "native_batch": native_batch.status_code,
                "knowledge_single_add": knowledge_add.status_code,
                "knowledge_single_update": knowledge_update.status_code,
                "knowledge_batch_add": knowledge_batch.status_code,
                "private_action": private_action.status_code,
            },
            "protected_attempt_delta": protected_delta,
            "source_state": source_state,
            "before": _safe_counter_view(initial),
        }
    finally:
        if knowledge_id:
            cleanup["knowledge_deleted"] = _cleanup_call(
                lambda: _delete_temporary_knowledge(ssh_target, knowledge_id)
            )
        if generic_source_id:
            cleanup["generic_source_deleted"] = _cleanup_call(
                lambda: _delete(
                    session, _url(base_url, f"/api/v1/files/{generic_source_id}")
                )
            )
        if private_source_id:
            cleanup["private_source_deleted"] = _cleanup_call(
                lambda: _delete(
                    session, _url(base_url, f"/api/v1/files/{private_source_id}")
                )
            )

    final = _runtime_snapshot(ssh_target)
    final_source_state = (
        _source_state(ssh_target, private_source_id) if private_source_id else {}
    )
    cleanup_checks = {
        **cleanup,
        "private_file_row_absent": final_source_state.get("file_row_count") == 0,
        "private_storage_absent": final_source_state.get("storage_object_exists") is False,
        "private_knowledge_links_absent": final_source_state.get("knowledge_link_count") == 0,
        "private_vector_refs_absent": (
            final_source_state.get("vector_metadata_ref_count") == 0
            and final_source_state.get("embedding_queue_ref_count") == 0
        ),
        "knowledge_count_restored": (
            final["db"]["knowledge_count"] == initial["db"]["knowledge_count"]
        ),
        "document_count_restored": (
            final["db"]["document_count"] == initial["db"]["document_count"]
        ),
        "vector_collection_count_restored": (
            final["vector"]["collections_count"]
            == initial["vector"]["collections_count"]
        ),
    }
    proof["cleanup"] = cleanup_checks
    proof["after_cleanup"] = _safe_counter_view(final)
    proof["final_source_state"] = final_source_state
    if not all(cleanup_checks.values()):
        proof["status"] = "failed_cleanup"
        print(json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True))
        return 2
    print(json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _authenticated_session(
    base_url: str, env: dict[str, str]
) -> requests.Session:
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


def _private_intake(
    session: requests.Session,
    base_url: str,
    idempotency_key: str,
    payload: bytes,
) -> dict[str, Any]:
    response = _private_intake_response(
        session, base_url, idempotency_key, payload
    )
    response.raise_for_status()
    return _json_object(response)


def _private_intake_response(
    session: requests.Session,
    base_url: str,
    idempotency_key: str,
    payload: bytes,
    *,
    query: str = "",
) -> requests.Response:
    return session.post(
        _url(base_url, "/api/v1/broker-reports/intake" + query),
        headers={"Idempotency-Key": idempotency_key},
        files={
            "file": (
                "synthetic-private-intake.txt",
                io.BytesIO(payload),
                "text/plain",
            )
        },
        timeout=60,
    )


def _generic_process_false_upload(
    session: requests.Session, base_url: str, payload: bytes
) -> str:
    response = session.post(
        _url(base_url, "/api/v1/files/?process=false"),
        files={
            "file": (
                "synthetic-generic-ref.txt",
                io.BytesIO(payload),
                "text/plain",
            )
        },
        timeout=60,
    )
    response.raise_for_status()
    source_id = str(_json_object(response).get("id") or "")
    if not source_id:
        raise RuntimeError("generic_source_id_missing")
    return source_id


def _action_body(source_id: str, suffix: str) -> dict[str, Any]:
    model_id = "broker-private-intake-direct-smoke"
    return {
        "model": model_id,
        "model_item": {"id": model_id, "direct": True},
        "chat_id": "broker-private-intake-smoke-" + suffix,
        "id": "response-" + suffix,
        "session_id": "session-" + suffix,
        "files": [{"type": "file", "file": {"id": source_id}}],
    }


def _batch_rejected(
    response: requests.Response, data: dict[str, Any]
) -> bool:
    if response.status_code in {400, 409}:
        return True
    results = data.get("results") if isinstance(data.get("results"), list) else []
    errors = data.get("errors") if isinstance(data.get("errors"), list) else []
    return response.status_code == 200 and not results and len(errors) == 1


def _source_state(ssh_target: str, source_id: str) -> dict[str, Any]:
    remote_code = r'''
import json
import sqlite3
from pathlib import Path

source_id = __SOURCE_ID__
db_path = Path("/app/backend/data/webui.db")
state = {
    "file_row_count": 0,
    "data_empty": False,
    "receipt_present": False,
    "forbidden_native_key_count": 0,
    "knowledge_link_count": 0,
    "document_row_count": 0,
    "storage_object_exists": False,
    "vector_metadata_ref_count": 0,
    "embedding_queue_ref_count": 0,
}
with sqlite3.connect(db_path) as conn:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "select data, meta, path from file where id = ?", (source_id,)
    ).fetchall()
    state["file_row_count"] = len(rows)
    if rows:
        data = json.loads(rows[0]["data"] or "{}")
        meta = json.loads(rows[0]["meta"] or "{}")
        forbidden = {
            "collection_name", "content", "embedding", "embeddings",
            "knowledge_id", "status", "vector", "vectors",
        }
        state["data_empty"] = data == {}
        state["receipt_present"] = "broker_reports_intake" in meta
        state["forbidden_native_key_count"] = len(forbidden.intersection(data)) + len(
            forbidden.intersection(meta)
        )
        state["storage_object_exists"] = Path(str(rows[0]["path"] or "")).exists()
    state["knowledge_link_count"] = int(
        conn.execute(
            "select count(*) from knowledge_file where file_id = ?", (source_id,)
        ).fetchone()[0]
    )
    state["document_row_count"] = int(
        conn.execute(
            "select count(*) from document where collection_name in (?, ?)",
            (source_id, "file-" + source_id),
        ).fetchone()[0]
    )

vector_path = Path("/app/backend/data/vector_db/chroma.sqlite3")
if vector_path.exists():
    with sqlite3.connect(vector_path) as conn:
        state["vector_metadata_ref_count"] = int(
            conn.execute(
                "select count(*) from embedding_metadata where string_value = ?",
                (source_id,),
            ).fetchone()[0]
        )
        state["embedding_queue_ref_count"] = int(
            conn.execute(
                "select count(*) from embeddings_queue where metadata like ?",
                ("%" + source_id + "%",),
            ).fetchone()[0]
        )
print(json.dumps(state, sort_keys=True))
'''.replace("__SOURCE_ID__", json.dumps(source_id))
    completed = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            ssh_target,
            "docker",
            "exec",
            "-i",
            "openwebui",
            "python",
            "-",
        ],
        cwd=ROOT,
        input=remote_code,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    return json.loads(completed.stdout)


def _delete(session: requests.Session, url: str) -> bool:
    try:
        response = session.delete(url, timeout=60)
    except requests.RequestException:
        return False
    return response.status_code in {200, 204}


def _create_temporary_knowledge(
    *,
    ssh_target: str,
    knowledge_id: str,
    owner_user_id: str,
    case_suffix: str,
) -> None:
    remote_code = r'''
import sqlite3
import time

knowledge_id = __KNOWLEDGE_ID__
owner_user_id = __OWNER_USER_ID__
name = __NAME__
now = int(time.time())
with sqlite3.connect("/app/backend/data/webui.db", timeout=5) as conn:
    conn.execute(
        "insert into knowledge(id,user_id,name,description,meta,created_at,updated_at,data) "
        "values(?,?,?,?,?,?,?,?)",
        (
            knowledge_id,
            owner_user_id,
            name,
            "Synthetic private-intake guard fixture; no embeddings.",
            "{}",
            now,
            now,
            "{}",
        ),
    )
    conn.commit()
'''
    replacements = {
        "__KNOWLEDGE_ID__": json.dumps(knowledge_id),
        "__OWNER_USER_ID__": json.dumps(owner_user_id),
        "__NAME__": json.dumps(f"Broker private intake synthetic {case_suffix}"),
    }
    for needle, replacement in replacements.items():
        remote_code = remote_code.replace(needle, replacement)
    _run_remote_python(ssh_target, remote_code)


def _delete_temporary_knowledge(ssh_target: str, knowledge_id: str) -> bool:
    remote_code = r'''
import json
import sqlite3

knowledge_id = __KNOWLEDGE_ID__
with sqlite3.connect("/app/backend/data/webui.db", timeout=5) as conn:
    link_count = int(
        conn.execute(
            "select count(*) from knowledge_file where knowledge_id = ?",
            (knowledge_id,),
        ).fetchone()[0]
    )
    conn.execute("delete from knowledge_file where knowledge_id = ?", (knowledge_id,))
    conn.execute("delete from knowledge where id = ?", (knowledge_id,))
    conn.commit()
    remaining = int(
        conn.execute(
            "select count(*) from knowledge where id = ?", (knowledge_id,)
        ).fetchone()[0]
    )
print(json.dumps({"link_count_before_cleanup": link_count, "remaining": remaining}))
'''.replace("__KNOWLEDGE_ID__", json.dumps(knowledge_id))
    result = _run_remote_python(ssh_target, remote_code)
    return result.get("remaining") == 0


def _run_remote_python(ssh_target: str, remote_code: str) -> dict[str, Any]:
    completed = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            ssh_target,
            "docker",
            "exec",
            "-i",
            "openwebui",
            "python",
            "-",
        ],
        cwd=ROOT,
        input=remote_code,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    output = completed.stdout.strip()
    return json.loads(output) if output else {}


def _cleanup_call(callback) -> bool:
    try:
        return bool(callback())
    except Exception:
        return False


def _json_object(response: requests.Response) -> dict[str, Any]:
    try:
        value = response.json()
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def _nested(value: dict[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "code": str(exc)[:240],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        raise
