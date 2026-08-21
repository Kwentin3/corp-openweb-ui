#!/usr/bin/env python3
"""Publish and prove one real NDFL Gate 1 -> Gate 2 -> Gate 3 path."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
BUNDLE_PATH = (
    SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate1_pipe_bundled.py"
)
FUNCTION_ID = "broker_reports_gate1_pipe"
WORKSPACE_MODEL_ID = "broker-reports-ndfl"
DEFAULT_SOURCE = (
    REPO_ROOT
    / "local"
    / "stage2"
    / "broker_reports_private_upload_packages"
    / "case_group_002_2026-07-08"
    / "files"
    / "01__brdoc_001_b874d956e33a.csv"
)
AUDIT_ID_RE = re.compile(r"^g3c5_[a-z0-9][a-z0-9_-]{7,63}$")

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.gate3_bounded_labeling import (  # noqa: E402
    GATE3_LABELING_INSTRUCTION,
)
from broker_reports_gate1.gate3_financial_label_dictionary import (  # noqa: E402
    GATE3_DICTIONARY_ID,
    GATE3_DICTIONARY_V1_FILE_SHA256,
    GATE3_DICTIONARY_V1_MODEL_VIEW_SHA256,
    GATE3_DICTIONARY_V1_VERSION,
)
from broker_reports_gate1.gate3_ndfl_workflow import (  # noqa: E402
    NDFL_PROVIDER_MODEL_ID,
    NDFL_PROVIDER_PROFILE_ID,
    ndfl_product_binding_snapshot,
)
from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _default_ssh_target,
    _delete_uploads,
    _extract_content,
    _read_env,
    _signin,
    _url,
)
from live_publish_ndfl_workspace_model import (  # noqa: E402
    _get_model,
    _get_visible_models,
)
from live_update_function_and_passport_prompt import (  # noqa: E402
    _get_function,
    _get_function_valves,
    _update_function,
    _update_function_valves,
)


class NdflProductProofError(RuntimeError):
    pass


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _ssh_prefix(target: str) -> list[str]:
    return [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "StrictHostKeyChecking=yes",
        target,
    ]


def _function_sha(function: dict[str, Any]) -> str:
    return _sha256(str(function.get("content") or "").encode("utf-8"))


def _desired_product_valves(
    current: dict[str, Any],
    *,
    audit_id: str,
) -> dict[str, Any]:
    desired = {
        **current,
        "canonical_gate2_write_enabled": True,
        "canonical_gate2_read_enabled": True,
        "ndfl_gate3_enabled": True,
        "ndfl_gate3_provider_profile_id": NDFL_PROVIDER_PROFILE_ID,
        "ndfl_gate3_model_id": NDFL_PROVIDER_MODEL_ID,
        "ndfl_gate3_private_audit_enabled": True,
        "ndfl_gate3_private_audit_root": (
            "/app/backend/data/broker_reports_gate1/gate3-product-proof"
        ),
        "ndfl_gate3_private_audit_id": audit_id,
    }
    desired.pop("canonical_gate2_compare_enabled", None)
    return desired


def _final_product_valves(current: dict[str, Any]) -> dict[str, Any]:
    desired = {
        **current,
        "canonical_gate2_write_enabled": True,
        "canonical_gate2_read_enabled": True,
        "ndfl_gate3_enabled": True,
        "ndfl_gate3_provider_profile_id": NDFL_PROVIDER_PROFILE_ID,
        "ndfl_gate3_model_id": NDFL_PROVIDER_MODEL_ID,
        "ndfl_gate3_private_audit_enabled": False,
        "ndfl_gate3_private_audit_id": "",
    }
    desired.pop("canonical_gate2_compare_enabled", None)
    return desired


def _assert_valves(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    required = {
        "canonical_gate2_write_enabled",
        "canonical_gate2_read_enabled",
        "ndfl_gate3_enabled",
        "ndfl_gate3_provider_profile_id",
        "ndfl_gate3_model_id",
        "ndfl_gate3_private_audit_enabled",
        "ndfl_gate3_private_audit_root",
        "ndfl_gate3_private_audit_id",
    }
    mismatches = sorted(
        key for key in required if actual.get(key) != expected.get(key)
    )
    if mismatches:
        raise NdflProductProofError(
            "ndfl_product_valve_readback_mismatch:" + ",".join(mismatches)
        )


def _upload_process_false(
    session: requests.Session,
    base_url: str,
    source: Path,
    timeout: int,
) -> dict[str, Any]:
    alias = "g3c5_authorized_document" + source.suffix.lower()
    mime_type = mimetypes.guess_type(alias)[0] or "application/octet-stream"
    with source.open("rb") as handle:
        response = session.post(
            _url(base_url, "/api/v1/files/?process=false"),
            files={"file": (alias, handle, mime_type)},
            timeout=timeout,
        )
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict) or not value.get("id"):
        raise NdflProductProofError("ndfl_process_false_upload_invalid")
    return {
        "id": str(value["id"]),
        "filename": alias,
        "mime_type": str(
            value.get("mime_type") or value.get("content_type") or mime_type
        ),
        "size": int(value.get("size") or source.stat().st_size),
    }


def _run_ndfl_chat(
    *,
    session: requests.Session,
    base_url: str,
    upload: dict[str, Any],
    case_id: str,
    timeout: int,
) -> str:
    file_value = {
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
    retention = {"mode": "customer_approved_test", "explicit": True}
    content = (
        "Обработай этот разрешённый брокерский документ внутри NDFL. "
        "Выполни внутренние Gate 1, Gate 2 и Gate 3. "
        "Не выполняй расчёт налога, FIFO, декларацию или Gate 4."
    )
    body = {
        "model": WORKSPACE_MODEL_ID,
        "parent_id": None,
        "case_id": case_id,
        "retention_policy": retention,
        "messages": [
            {"role": "user", "content": content, "files": [file_value]}
        ],
        "files": [file_value],
        "metadata": {
            "case_id": case_id,
            "retention_policy": retention,
            "broker_reports_gate1": {
                "source_intake": "process_false_private_upload",
                "customer_docs_loaded_to_knowledge": False,
                "tax_calculation": False,
                "declaration_generation": False,
                "gate4": False,
            },
        },
        "stream": False,
    }
    response = session.post(
        _url(base_url, "/api/chat/completions"),
        json=body,
        timeout=timeout,
    )
    response.raise_for_status()
    content_value = _extract_content(response.json())
    if not content_value or "Gate 3:" not in content_value:
        raise NdflProductProofError("ndfl_product_chat_completion_missing")
    if upload["id"] in content_value or upload["filename"] in content_value:
        raise NdflProductProofError("ndfl_product_chat_private_ref_leak")
    return content_value


def _remote_audit_summary(
    *,
    ssh_target: str,
    audit_id: str,
    case_id: str,
) -> dict[str, Any]:
    expected_binding = ndfl_product_binding_snapshot()
    instruction_sha256 = _sha256(GATE3_LABELING_INSTRUCTION.encode("utf-8"))
    code = f'''
import hashlib
import json
import sqlite3
from pathlib import Path

audit_id = {audit_id!r}
expected_binding = {expected_binding!r}
expected_instruction_sha256 = {instruction_sha256!r}
audit_dir = Path("/app/backend/data/broker_reports_gate1/gate3-product-proof") / audit_id
manifest_path = audit_dir / "manifest.safe.json"
if not manifest_path.is_file():
    raise RuntimeError("audit_manifest_missing")
manifest_bytes = manifest_path.read_bytes()
manifest = json.loads(manifest_bytes)
exact_files = sorted(audit_dir.glob("document_*.exact.json"))
if len(exact_files) != 1 or len(manifest.get("files") or []) != 1:
    raise RuntimeError("audit_document_count_invalid")
exact_bytes = exact_files[0].read_bytes()
if hashlib.sha256(exact_bytes).hexdigest() != manifest["files"][0]["sha256"]:
    raise RuntimeError("audit_exact_hash_mismatch")
audit = json.loads(exact_bytes)
if audit.get("product_binding") != expected_binding:
    raise RuntimeError("audit_product_binding_mismatch")
before = audit.get("canonical_before_gate3") or {{}}
after = audit.get("canonical_after_gate3") or {{}}
if (
    before.get("canonical_version_id") != after.get("canonical_version_id")
    or before.get("canonical_root_sha256") != after.get("canonical_root_sha256")
    or before.get("artifact") != after.get("artifact")
):
    raise RuntimeError("audit_gate2_mutation_detected")
attempts = audit.get("attempts") or []
if not attempts:
    raise RuntimeError("audit_attempts_missing")
validated_annotations = 0
for attempt in attempts:
    dictionary = attempt.get("dictionary") or {{}}
    identity = (attempt.get("dictionary_managed_binding") or {{}}).get(
        "dictionary_identity"
    ) or {{}}
    if (
        dictionary.get("dictionary_id") != {GATE3_DICTIONARY_ID!r}
        or dictionary.get("semantic_version") != {GATE3_DICTIONARY_V1_VERSION!r}
        or len(dictionary.get("labels") or []) != 9
        or identity.get("file_sha256") != {GATE3_DICTIONARY_V1_FILE_SHA256!r}
        or identity.get("model_view_sha256")
        != {GATE3_DICTIONARY_V1_MODEL_VIEW_SHA256!r}
    ):
        raise RuntimeError("audit_dictionary_binding_mismatch")
    instruction = str(attempt.get("instruction") or "")
    if hashlib.sha256(instruction.encode("utf-8")).hexdigest() != expected_instruction_sha256:
        raise RuntimeError("audit_instruction_mismatch")
    final_request = attempt.get("final_provider_request") or {{}}
    messages = final_request.get("messages") or []
    expected_messages = [
        instruction,
        str(attempt.get("dictionary_markdown") or ""),
        str(((attempt.get("projection") or {{}}).get("model_view") or {{}}).get("content") or ""),
    ]
    if [item.get("content") for item in messages] != expected_messages:
        raise RuntimeError("audit_final_model_input_mismatch")
    if not attempt.get("raw_provider_response") or attempt.get("raw_model_output") is None:
        raise RuntimeError("audit_raw_output_missing")
    validated = attempt.get("validated_output") or {{}}
    if attempt.get("validation_status") != "validated":
        raise RuntimeError("audit_validation_not_terminal")
    validated_annotations += len(validated.get("annotations") or [])
annotations = audit.get("financial_annotations_v1") or {{}}
if (
    annotations.get("schema_version") != "broker_reports_financial_annotations_v1"
    or annotations.get("canonical_binding")
    != {{
        "document_id": before.get("document_id"),
        "canonical_version_id": before.get("canonical_version_id"),
    }}
):
    raise RuntimeError("audit_annotations_binding_mismatch")

db = Path("/app/backend/data/broker_reports_gate1/artifacts.sqlite3")
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
versions = conn.execute(
    "select canonical_version_id, canonical_root_sha256, status, workspace_model_id "
    "from canonical_versions where canonical_version_id = ?",
    (before.get("canonical_version_id"),),
).fetchall()
records = conn.execute(
    "select artifact_id, artifact_type, validation_status, workspace_model_id, document_id "
    "from artifact_records where workspace_model_id = ? and chat_id = "
    "(select chat_id from canonical_versions where canonical_version_id = ?)",
    ({WORKSPACE_MODEL_ID!r}, before.get("canonical_version_id")),
).fetchall()
receipts = conn.execute(
    "select actor, reason, canonical_version_id from canonical_activation_receipts "
    "where canonical_version_id = ?",
    (before.get("canonical_version_id"),),
).fetchall()
conn.close()
annotations_records = [
    row for row in records
    if row["artifact_id"] == audit.get("annotations_artifact_id")
    and row["artifact_type"] == "broker_reports_financial_annotations_v1"
]
if (
    len(annotations_records) != 1
    or annotations_records[0]["validation_status"] != "validated"
    or annotations_records[0]["workspace_model_id"] != {WORKSPACE_MODEL_ID!r}
):
    raise RuntimeError("audit_annotations_record_invalid")
if (
    len(versions) != 1
    or versions[0]["canonical_version_id"] != before.get("canonical_version_id")
    or versions[0]["canonical_root_sha256"] != before.get("canonical_root_sha256")
    or versions[0]["status"] != "ACTIVE"
    or versions[0]["workspace_model_id"] != {WORKSPACE_MODEL_ID!r}
):
    raise RuntimeError("audit_canonical_version_invalid")
if (
    len(receipts) != 1
    or receipts[0]["actor"] != {WORKSPACE_MODEL_ID!r}
    or receipts[0]["reason"] != "ndfl_gate2_candidate_ready_for_gate3"
):
    raise RuntimeError("audit_activation_owner_invalid")
types = {{}}
for row in records:
    key = row["artifact_type"]
    types[key] = types.get(key, 0) + 1
result = {{
    "status": "passed",
    "audit_id": audit_id,
    "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
    "exact_file_sha256": hashlib.sha256(exact_bytes).hexdigest(),
    "exact_file_bytes": len(exact_bytes),
    "attempts_total": len(attempts),
    "validated_annotations_total": validated_annotations,
    "persisted_annotations_total": len(annotations.get("annotations") or []),
    "canonical_version_id": before.get("canonical_version_id"),
    "canonical_root_sha256": before.get("canonical_root_sha256"),
    "gate2_mutation": "none",
    "workspace_model_id": {WORKSPACE_MODEL_ID!r},
    "artifact_type_counts": types,
}}
print(json.dumps(result, sort_keys=True))
'''
    completed = subprocess.run(
        [
            *_ssh_prefix(ssh_target),
            "docker",
            "exec",
            "-i",
            "openwebui",
            "python",
            "-",
        ],
        cwd=REPO_ROOT,
        input=code,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=180,
    )
    value = json.loads(completed.stdout)
    if not isinstance(value, dict) or value.get("status") != "passed":
        raise NdflProductProofError("ndfl_remote_audit_receipt_invalid")
    return value


def _copy_private_audit(
    *,
    ssh_target: str,
    audit_id: str,
    private_root: Path,
    expected: dict[str, Any],
) -> Path:
    if AUDIT_ID_RE.fullmatch(audit_id) is None:
        raise NdflProductProofError("ndfl_private_audit_id_invalid")
    private_root = private_root.resolve()
    private_root.mkdir(parents=True, exist_ok=True)
    target = (private_root / audit_id).resolve()
    if target.parent != private_root or target.exists():
        raise NdflProductProofError("ndfl_local_private_audit_target_not_new")
    remote = (
        "/var/lib/docker/volumes/openwebui_data/_data/"
        "broker_reports_gate1/gate3-product-proof/" + audit_id
    )
    subprocess.run(
        [
            "scp",
            "-q",
            "-r",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "StrictHostKeyChecking=yes",
            f"{ssh_target}:{remote}",
            str(private_root),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
    )
    exact_files = list(target.glob("document_*.exact.json"))
    if (
        len(exact_files) != 1
        or _sha256(exact_files[0].read_bytes()) != expected["exact_file_sha256"]
        or _sha256((target / "manifest.safe.json").read_bytes())
        != expected["manifest_sha256"]
    ):
        raise NdflProductProofError("ndfl_local_private_audit_hash_mismatch")
    return target


def _visible_ndfl_topology(session: requests.Session, base_url: str) -> bool:
    relevant = {
        "broker-reports-ndfl",
        "test",
        "broker_reports_gate1_pipe",
        "broker_reports_gate2_source_fact_pipe",
        "broker_reports_gate2_domain_source_fact_pipe",
    }
    visible = {
        str(item.get("id"))
        for item in _get_visible_models(session, base_url)
        if str(item.get("id")) in relevant
    }
    return visible == {WORKSPACE_MODEL_ID, FUNCTION_ID}


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if not args.source.is_file():
        raise NdflProductProofError("ndfl_authorized_source_missing")
    if AUDIT_ID_RE.fullmatch(args.audit_id) is None:
        raise NdflProductProofError("ndfl_private_audit_id_invalid")
    env = _read_env(args.env_file)
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

    model = _get_model(session, base_url, WORKSPACE_MODEL_ID)
    if (
        model is None
        or model.get("base_model_id") != FUNCTION_ID
        or not _visible_ndfl_topology(session, base_url)
    ):
        raise NdflProductProofError("ndfl_workspace_model_binding_invalid")
    bundle = BUNDLE_PATH.read_text(encoding="utf-8")
    bundle_sha = _sha256(bundle.encode("utf-8"))
    before_function = _get_function(session, base_url)
    before_valves = _get_function_valves(session, base_url)
    uploaded: list[dict[str, Any]] = []
    published = False
    proof_passed = False
    case_id = "g3c5_ndfl_" + time.strftime("%Y%m%d%H%M%S")

    try:
        _update_function(session, base_url, before_function, bundle)
        published = True
        live_function = _get_function(session, base_url)
        if _function_sha(live_function) != bundle_sha:
            raise NdflProductProofError("ndfl_live_bundle_hash_mismatch")
        current_valves = _get_function_valves(session, base_url)
        proof_valves = _desired_product_valves(
            current_valves,
            audit_id=args.audit_id,
        )
        _update_function_valves(session, base_url, proof_valves)
        _assert_valves(
            _get_function_valves(session, base_url),
            proof_valves,
        )
        if not _visible_ndfl_topology(session, base_url):
            raise NdflProductProofError(
                "ndfl_workspace_model_missing_after_function_refresh"
            )

        upload = _upload_process_false(
            session,
            base_url,
            args.source,
            args.timeout,
        )
        uploaded.append(upload)
        chat_content = _run_ndfl_chat(
            session=session,
            base_url=base_url,
            upload=upload,
            case_id=case_id,
            timeout=args.timeout,
        )
        remote = _remote_audit_summary(
            ssh_target=ssh_target,
            audit_id=args.audit_id,
            case_id=case_id,
        )
        local_audit = _copy_private_audit(
            ssh_target=ssh_target,
            audit_id=args.audit_id,
            private_root=args.private_evidence_root,
            expected=remote,
        )
        final_valves = _final_product_valves(
            _get_function_valves(session, base_url)
        )
        _update_function_valves(session, base_url, final_valves)
        _assert_valves(
            _get_function_valves(session, base_url),
            final_valves,
        )
        proof_passed = True
        return {
            "schema_version": "broker_reports_ndfl_product_path_proof_v1",
            "status": "passed",
            "product_path": [
                "user",
                WORKSPACE_MODEL_ID,
                "gate1",
                "canonical_artifact_v1",
                "ndfl_gate3_decision",
                GATE3_DICTIONARY_ID + "@" + GATE3_DICTIONARY_V1_VERSION,
                NDFL_PROVIDER_MODEL_ID,
                "financial_annotations_v1",
            ],
            "stable_binding": ndfl_product_binding_snapshot(),
            "workspace_model_visible_owner_count": 1,
            "live_bundle_sha256": bundle_sha,
            "authorized_documents_total": 1,
            "authorized_source_bytes": args.source.stat().st_size,
            "source_upload_process": False,
            "chat_compact": len(chat_content) < 7000,
            "chat_private_refs_leaked": False,
            "remote_audit": remote,
            "private_audit_local": {
                "saved": True,
                "audit_id": args.audit_id,
                "path_disclosed_in_git": False,
                "exact_file_sha256": remote["exact_file_sha256"],
            },
            "gate2_mutation": "none",
            "knowledge_rag": "none",
            "gate4_performed": False,
            "runtime_after_proof": {
                "ndfl_gate3_enabled": True,
                "private_audit_enabled": False,
                "exact_private_evidence_retained": local_audit.is_dir(),
            },
        }
    finally:
        _delete_uploads(session, base_url, uploaded)
        if published and not proof_passed:
            rollback_function = _get_function(session, base_url)
            _update_function(
                session,
                base_url,
                rollback_function,
                str(before_function.get("content") or ""),
            )
            _update_function_valves(session, base_url, before_valves)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--ssh-target", default=None)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument(
        "--audit-id",
        default="g3c5_" + time.strftime("%Y%m%d_%H%M%S"),
    )
    parser.add_argument(
        "--private-evidence-root",
        type=Path,
        default=(
            Path.home()
            / ".codex"
            / "private-evidence"
            / "broker-reports-gate3"
        ),
    )
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    receipt = execute(args)
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
