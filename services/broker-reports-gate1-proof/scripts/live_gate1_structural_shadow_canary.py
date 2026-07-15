#!/usr/bin/env python3
"""Canary Gate 1 structural and semantic shadows with exact rollback state."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

import requests
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]
SERVICE_ROOT = ROOT / "services" / "broker-reports-gate1-proof"
BUNDLE_PATH = SERVICE_ROOT / "openwebui_actions/broker_reports_gate1_pipe_bundled.py"
FUNCTION_ID = "broker_reports_gate1_pipe"
MODEL_ID = "test"
REQUIRED_MARKERS = (
    "PdfGridExperimentProviderFactory",
    "PdfStructuralRepairRuntimeFactory",
    "PdfStructuralRepairShadowFactory",
    "PdfSemanticHeaderProjectionFactory",
    "pdf_structural_repair_runtime_policy_v1",
    "pdf_vlm_guided_intake_shadow_enabled",
    "pdf_vlm_guided_intake_shadow_page_allowlist",
    "run_candidate_once",
    "broker_reports_pdf_vlm_guided_intake_result_v1",
    "broker_reports_pdf_semantic_header_projection_v1",
    "pdf_semantic_header_projection_policy_v1",
)
EXPECTED_FRAGMENT_RUNTIME_RECORDS = 2
EXPECTED_SEMANTIC_PROJECTION_RECORDS = 2
EXPECTED_COUNT_TOKEN_CALLS_PER_FRAGMENT = 1
EXPECTED_GENERATE_CALLS_PER_FRAGMENT = 1
EXPECTED_PROVIDER_PROFILE = "google_gemini"
EXPECTED_PROVIDER_MODEL = "models/gemini-3.5-flash"
MAX_COUNTED_INPUT_TOKENS = 20_000
MAX_PROVIDER_OUTPUT_TOKENS = 8_192
MAX_SEMANTIC_CONTEXT_BYTES = 48 * 1024
EXPECTED_SEMANTIC_CONFIGURATION_SCHEMA = (
    "broker_reports_pdf_semantic_header_projection_configuration_v1"
)
ARTIFACT_QUIESCENCE_INTERVALS_SECONDS = (5.0, 15.0, 30.0)
PROVIDER_ORDER_EVIDENCE_BOUNDARY = (
    "runtime_journal_co_recorded_without_count_tokens_timestamp"
)
MAX_COMPACT_REPORT_CHARS = 12_000
FUNCTION_CONTROL_KEYS = (
    "id",
    "name",
    "meta",
    "is_active",
    "is_global",
)

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import FileInput, Gate1Normalizer  # noqa: E402
from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _capabilities as _workspace_model_capabilities,
    _default_ssh_target,
    _extract_content,
    _get_model as _get_workspace_model,
    _knowledge_attachments_count,
    _read_env,
    _safe_counter_view as _base_safe_counter_view,
    _signin,
    _url,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--ssh-target", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--chat-timeout", type=int, default=1500)
    args = parser.parse_args()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else ROOT
        / "local"
        / "stage2"
        / f"broker_reports_gate1_structural_shadow_canary_{timestamp}"
    ).resolve()
    if output_dir.exists():
        raise RuntimeError("canary_output_exists")
    private_dir = output_dir / "private"
    private_dir.mkdir(parents=True, exist_ok=False)

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

    bundle_source = BUNDLE_PATH.read_text(encoding="utf-8")
    bundle_sha = _text_sha(bundle_source)
    missing = [marker for marker in REQUIRED_MARKERS if marker not in bundle_source]
    if missing:
        raise RuntimeError("canary_bundle_markers_missing:" + ",".join(missing))

    before_function = _get_function(session, base_url)
    before_valves = _get_valves(session, base_url)
    before_workspace_model = _get_workspace_model(session, base_url, MODEL_ID)
    _assert_live_preflight(
        valves=before_valves,
        workspace_model=before_workspace_model,
    )
    before_function_sha = _text_sha(str(before_function.get("content") or ""))
    before_valves_sha = _json_sha(before_valves)
    before_workspace_model_sha = _json_sha(before_workspace_model)
    backup = {
        "schema_version": "broker_reports_gate1_function_rollback_v1",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "function_id": FUNCTION_ID,
        "name": before_function.get("name"),
        "meta": before_function.get("meta")
        if isinstance(before_function.get("meta"), dict)
        else {},
        "content": str(before_function.get("content") or ""),
        "content_sha256": before_function_sha,
        "valves": before_valves,
        "valves_sha256": before_valves_sha,
        "workspace_model_id": MODEL_ID,
        "workspace_model_sha256": before_workspace_model_sha,
    }
    backup.update(_function_control_view(before_function))
    _write_json(private_dir / "function.before.private.json", backup)

    case_id = "case_gate1_structural_shadow_canary_" + hashlib.sha256(
        f"{timestamp}|{bundle_sha}".encode("utf-8")
    ).hexdigest()[:16]
    upload_filename = f"structural-shadow-canary-{case_id[-16:]}.pdf"
    pdf_bytes = _two_fragment_guided_intake_pdf()
    pdf_path = private_dir / f"{upload_filename}.private"
    pdf_path.write_bytes(pdf_bytes)
    candidate_refs = _candidate_refs(pdf_bytes)
    if len(candidate_refs) != EXPECTED_FRAGMENT_RUNTIME_RECORDS:
        raise RuntimeError(f"canary_candidate_count_invalid:{len(candidate_refs)}")

    before_runtime = _runtime_snapshot_strict(ssh_target)
    upload: dict[str, Any] | None = None
    function_update_attempted = False
    body_passed = False
    body_error: BaseException | None = None
    chat_content = ""
    artifact_summary: dict[str, Any] = {}
    after_upload: dict[str, Any] | None = None
    after_chat: dict[str, Any] | None = None
    after_delete: dict[str, Any] | None = None
    try:
        function_update_attempted = True
        _update_function_with_timeout_recovery(
            session,
            base_url,
            function=before_function,
            content=bundle_source,
            expected_sha=bundle_sha,
        )
        live_function = _get_function(session, base_url)
        if _text_sha(str(live_function.get("content") or "")) != bundle_sha:
            raise RuntimeError("canary_live_bundle_sha_mismatch")
        if any(
            marker not in str(live_function.get("content") or "")
            for marker in REQUIRED_MARKERS
        ):
            raise RuntimeError("canary_live_bundle_marker_missing")
        fitz_version = _fitz_version(ssh_target)
        if fitz_version != "1.26.5":
            raise RuntimeError(f"canary_fitz_version_mismatch:{fitz_version}")

        upload = _upload_pdf_process_false(
            session,
            base_url,
            pdf_path,
            upload_filename=upload_filename,
        )
        after_upload = _runtime_snapshot_strict(ssh_target)
        canary_valves = _canary_valves(before_valves, candidate_refs)
        _update_valves(session, base_url, canary_valves)
        if _get_valves(session, base_url) != canary_valves:
            raise RuntimeError("canary_valves_roundtrip_mismatch")

        chat_content = _run_chat(
            session,
            base_url,
            upload=upload,
            case_id=case_id,
            timeout=args.chat_timeout,
        )
        after_chat = _runtime_snapshot_strict(ssh_target)
        artifact_summary = _artifact_case_summary(
            ssh_target,
            case_id,
            bundle_source,
        )
        _assert_canary(
            chat_content=chat_content,
            artifacts=artifact_summary,
            before=before_runtime,
            after_upload=after_upload,
            after_chat=after_chat,
        )
        body_passed = True
    except BaseException as exc:
        body_error = exc
    finally:
        try:
            finalization = _finalize_canary(
                session=session,
                base_url=base_url,
                ssh_target=ssh_target,
                function_update_attempted=function_update_attempted,
                body_passed=body_passed,
                before_function=before_function,
                before_valves=before_valves,
                before_valves_sha=before_valves_sha,
                before_workspace_model=before_workspace_model,
                before_workspace_model_sha=before_workspace_model_sha,
                bundle_source=bundle_source,
                bundle_sha=bundle_sha,
                case_id=case_id,
                upload=upload,
                upload_filename=upload_filename,
                before_runtime=before_runtime,
            )
        except BaseException as finalize_exc:
            terminal_errors = (
                _restore_old_runtime_state(
                    session=session,
                    base_url=base_url,
                    before_function=before_function,
                    before_valves=before_valves,
                    before_valves_sha=before_valves_sha,
                    stage_prefix="outer_terminal_restore",
                )
                if function_update_attempted
                else []
            )
            if terminal_errors:
                raise RuntimeError(
                    "canary_outer_terminal_restore_failed:"
                    + "|".join(terminal_errors)
                ) from finalize_exc
            raise
        after_delete = finalization["after_delete"]

    cleanup_errors = finalization["cleanup_errors"]
    if body_error is not None:
        if cleanup_errors:
            raise RuntimeError(
                "canary_failed_and_cleanup_failed:"
                + "|".join(cleanup_errors)
            ) from body_error
        raise body_error
    if cleanup_errors:
        raise RuntimeError("canary_cleanup_failed:" + "|".join(cleanup_errors))
    if not body_passed or after_delete is None:
        raise RuntimeError("canary_failed_without_terminal")
    if finalization["function_retained"] is not True:
        raise RuntimeError("canary_function_not_retained")

    safe = {
        "schema_version": "broker_reports_gate1_structural_shadow_canary_safe_v1",
        "status": "passed",
        "case_id": case_id,
        "function": {
            "previous_sha256": before_function_sha,
            "deployed_sha256": bundle_sha,
            "live_sha256": finalization["final_function_sha256"],
            "new_content_retained": finalization["function_retained"],
            "old_state_restored_before_slow_cleanup": finalization[
                "safety_barrier_completed"
            ],
            "terminal_state_verified": finalization[
                "terminal_state_restored"
            ],
        },
        "valves": {
            "previous_sha256": before_valves_sha,
            "restored_sha256": finalization["final_valves_sha256"],
            "restored_exactly": finalization["valves_restored_exactly"],
        },
        "workspace_model": {
            "model_id": MODEL_ID,
            "previous_sha256": before_workspace_model_sha,
            "restored_sha256": finalization["final_workspace_model_sha256"],
            "restored_exactly": finalization[
                "workspace_model_restored_exactly"
            ],
        },
        "input": {
            "synthetic_only": True,
            "pages": 1,
            "allowlisted_tables": len(candidate_refs),
            "uploaded_with_process_false": True,
            "upload_id_absent_after_cleanup": finalization[
                "upload_id_absent"
            ],
            "upload_alias_absent_after_cleanup": finalization[
                "upload_alias_absent"
            ],
            "knowledge_rag_used": False,
        },
        "artifact_cleanup": finalization["artifact_cleanup"],
        "provider": {
            "fragment_runtime_records": len(
                artifact_summary.get("fragment_runtime_records") or []
            ),
            "count_token_calls": artifact_summary.get("count_token_calls"),
            "generate_calls": artifact_summary.get("generate_calls"),
            "guided_result_records": int(
                (artifact_summary.get("type_counts") or {}).get(
                    "broker_reports_pdf_vlm_guided_intake_result_v1"
                )
                or 0
            ),
            "semantic_count_token_calls": artifact_summary.get(
                "semantic_new_provider_count_token_calls"
            ),
            "semantic_generate_calls": artifact_summary.get(
                "semantic_new_provider_generate_calls"
            ),
            "hidden_retry": artifact_summary.get("hidden_retry"),
            "provider_failover": artifact_summary.get("provider_failover"),
            "independent_call_order_proven": False,
            "call_order_evidence_boundary": (
                PROVIDER_ORDER_EVIDENCE_BOUNDARY
            ),
        },
        "structural_shadow": artifact_summary,
        "runtime_counters": {
            "before": _safe_counter_view_strict(before_runtime),
            "after_upload": _safe_counter_view_strict(after_upload or {}),
            "after_chat": _safe_counter_view_strict(after_chat or {}),
            "after_delete": _safe_counter_view_strict(after_delete),
        },
        "chat": {
            "compact_russian_report_present": "PDF" in chat_content,
            "private_markers_absent": True,
            "raw_json_absent": "```json" not in chat_content,
        },
        "rollback_artifact": str(
            _safe_output_path(private_dir / "function.before.private.json")
        ),
    }
    try:
        _write_json(output_dir / "canary.safe.json", safe)
        print(json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True))
    except BaseException as exc:
        rollback_errors = _rollback_retained_function_after_terminal_failure(
            session=session,
            base_url=base_url,
            before_function=before_function,
            before_valves=before_valves,
            before_valves_sha=before_valves_sha,
        )
        try:
            _write_json(
                output_dir / "canary.safe.json",
                {
                    "schema_version": (
                        "broker_reports_gate1_structural_shadow_canary_safe_v1"
                    ),
                    "status": "rolled_back_after_output_failure",
                    "function_restored": not rollback_errors,
                    "error_type": type(exc).__name__,
                },
            )
        except Exception as report_exc:
            rollback_errors.append(_cleanup_error("failure_report", report_exc))
        if rollback_errors:
            raise RuntimeError(
                "canary_output_failed_and_rollback_failed:"
                + "|".join(rollback_errors)
            ) from exc
        raise
    return 0


def _get_function(session: requests.Session, base_url: str) -> dict[str, Any]:
    response = session.get(
        _url(base_url, f"/api/v1/functions/id/{FUNCTION_ID}"), timeout=30
    )
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict):
        raise RuntimeError("canary_function_response_invalid")
    return value


def _get_valves(session: requests.Session, base_url: str) -> dict[str, Any]:
    response = session.get(
        _url(base_url, f"/api/v1/functions/id/{FUNCTION_ID}/valves"), timeout=30
    )
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict):
        raise RuntimeError("canary_valves_response_invalid")
    return value


def _canary_valves(
    before_valves: dict[str, Any], candidate_refs: list[str]
) -> dict[str, Any]:
    return {
        **before_valves,
        "pdf_structural_repair_shadow_enabled": True,
        "pdf_vlm_guided_intake_shadow_enabled": True,
        "pdf_vlm_guided_intake_shadow_page_allowlist": "",
        "pdf_semantic_header_shadow_enabled": True,
        "pdf_structural_repair_max_tables": EXPECTED_FRAGMENT_RUNTIME_RECORDS,
        "pdf_structural_repair_shadow_table_allowlist": ",".join(
            candidate_refs
        ),
        "pdf_structural_repair_provider_profile": EXPECTED_PROVIDER_PROFILE,
        "pdf_structural_repair_model_id": EXPECTED_PROVIDER_MODEL,
    }


def _assert_live_preflight(
    *,
    valves: dict[str, Any],
    workspace_model: dict[str, Any],
) -> None:
    if valves.get("pdf_structural_repair_shadow_enabled", False) is not False:
        raise RuntimeError("canary_shadow_initially_enabled")
    if valves.get("pdf_vlm_guided_intake_shadow_enabled", False) is not False:
        raise RuntimeError("canary_guided_intake_shadow_initially_enabled")
    if str(
        valves.get("pdf_vlm_guided_intake_shadow_page_allowlist") or ""
    ).strip():
        raise RuntimeError("canary_guided_page_allowlist_initially_nonempty")
    if valves.get("pdf_semantic_header_shadow_enabled", False) is not False:
        raise RuntimeError("canary_semantic_shadow_initially_enabled")
    if workspace_model.get("id") != MODEL_ID:
        raise RuntimeError("canary_workspace_model_identity_invalid")
    active = workspace_model.get("is_active")
    if active is not True and not (
        isinstance(active, int) and not isinstance(active, bool) and active == 1
    ):
        raise RuntimeError("canary_workspace_model_inactive")
    capabilities = _workspace_model_capabilities(workspace_model)
    if capabilities.get("file_upload") is not True:
        raise RuntimeError("canary_workspace_model_file_upload_disabled")
    if capabilities.get("file_context") is not False:
        raise RuntimeError("canary_workspace_model_file_context_enabled")
    if _knowledge_attachments_count(workspace_model) != 0:
        raise RuntimeError("canary_workspace_model_knowledge_attached")


def _assert_workspace_model_unchanged(
    *,
    before: dict[str, Any],
    before_sha: str,
    after: dict[str, Any],
) -> None:
    if (
        before != after
        or _json_sha(before) != before_sha
        or _json_sha(after) != before_sha
    ):
        raise RuntimeError("canary_workspace_model_state_mismatch")


def _update_function(
    session: requests.Session,
    base_url: str,
    *,
    function: dict[str, Any],
    content: str,
    timeout: int,
) -> None:
    response = session.post(
        _url(base_url, f"/api/v1/functions/id/{FUNCTION_ID}/update"),
        json={
            "id": FUNCTION_ID,
            "name": function.get("name") or "Broker Reports Gate 1",
            "meta": function.get("meta")
            if isinstance(function.get("meta"), dict)
            else {},
            "content": content,
        },
        timeout=timeout,
    )
    response.raise_for_status()


def _update_function_with_timeout_recovery(
    session: requests.Session,
    base_url: str,
    *,
    function: dict[str, Any],
    content: str,
    expected_sha: str,
) -> None:
    try:
        _update_function(
            session,
            base_url,
            function=function,
            content=content,
            timeout=360,
        )
    except requests.Timeout:
        time.sleep(3)
        live_sha = _text_sha(
            str(_get_function(session, base_url).get("content") or "")
        )
        if live_sha != expected_sha:
            raise


def _update_valves(
    session: requests.Session, base_url: str, valves: dict[str, Any]
) -> None:
    response = session.post(
        _url(base_url, f"/api/v1/functions/id/{FUNCTION_ID}/valves/update"),
        json=valves,
        timeout=60,
    )
    response.raise_for_status()


def _function_control_view(function: dict[str, Any]) -> dict[str, Any]:
    return {
        key: function.get(key)
        for key in FUNCTION_CONTROL_KEYS
        if key in function
    }


def _expected_deployed_function(
    before_function: dict[str, Any], bundle_source: str
) -> dict[str, Any]:
    expected = _function_control_view(before_function)
    bundle_manifest = _bundle_frontmatter_manifest(bundle_source)
    if bundle_manifest is not None:
        meta = dict(
            before_function.get("meta")
            if isinstance(before_function.get("meta"), dict)
            else {}
        )
        meta["manifest"] = bundle_manifest
        expected["meta"] = meta
    expected["content"] = bundle_source
    return expected


def _bundle_frontmatter_manifest(content: str) -> dict[str, str] | None:
    required_keys = (
        "title",
        "author",
        "version",
        "required_open_webui_version",
        "requirements",
    )
    lines = content.splitlines()
    if not lines or lines[0].strip() != '"""':
        return None
    manifest: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == '"""':
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key in required_keys:
            manifest[key] = value.strip()
    return manifest if set(manifest) == set(required_keys) else None


def _actual_function_view(function: dict[str, Any]) -> dict[str, Any]:
    result = _function_control_view(function)
    result["content"] = str(function.get("content") or "")
    return result


def _restore_function_exact(
    session: requests.Session,
    base_url: str,
    *,
    before_function: dict[str, Any],
) -> None:
    _update_function(
        session,
        base_url,
        function=before_function,
        content=str(before_function.get("content") or ""),
        timeout=360,
    )
    restored = _get_function(session, base_url)
    if _actual_function_view(restored) != _actual_function_view(before_function):
        raise RuntimeError("rollback_function_state_mismatch")


def _restore_valves_exact(
    session: requests.Session,
    base_url: str,
    *,
    before_valves: dict[str, Any],
    before_valves_sha: str,
) -> None:
    _update_valves(session, base_url, before_valves)
    restored = _get_valves(session, base_url)
    if restored != before_valves or _json_sha(restored) != before_valves_sha:
        raise RuntimeError("rollback_valves_state_mismatch")


def _restore_old_runtime_state(
    *,
    session: requests.Session,
    base_url: str,
    before_function: dict[str, Any],
    before_valves: dict[str, Any],
    before_valves_sha: str,
    stage_prefix: str,
) -> list[str]:
    errors: list[str] = []
    actions = (
        (
            "valves",
            lambda: _restore_valves_exact(
                session,
                base_url,
                before_valves=before_valves,
                before_valves_sha=before_valves_sha,
            ),
        ),
        (
            "function",
            lambda: _restore_function_exact(
                session,
                base_url,
                before_function=before_function,
            ),
        ),
        (
            "valves_verify",
            lambda: _restore_valves_exact(
                session,
                base_url,
                before_valves=before_valves,
                before_valves_sha=before_valves_sha,
            ),
        ),
    )
    for stage, action in actions:
        try:
            action()
        except BaseException as exc:
            errors.append(_cleanup_error(f"{stage_prefix}_{stage}", exc))
    return errors


def _finalize_canary(
    *,
    session: requests.Session,
    base_url: str,
    ssh_target: str,
    function_update_attempted: bool,
    body_passed: bool,
    before_function: dict[str, Any],
    before_valves: dict[str, Any],
    before_valves_sha: str,
    before_workspace_model: dict[str, Any],
    before_workspace_model_sha: str,
    bundle_source: str,
    bundle_sha: str,
    case_id: str,
    upload: dict[str, Any] | None,
    upload_filename: str,
    before_runtime: dict[str, Any],
) -> dict[str, Any]:
    """Reach a terminal live state; any cleanup defect forces Function rollback."""

    cleanup_errors: list[str] = []
    after_delete: dict[str, Any] | None = None
    upload_id_absent = False
    upload_alias_absent = False
    initial_artifact_cleanup: dict[str, Any] = {}
    quiescence_evidence: dict[str, Any] = {}
    final_workspace_model_sha = ""
    workspace_model_restored_exactly = False
    safety_barrier_completed = not function_update_attempted
    terminal_state_restored = not function_update_attempted
    function_retained = False
    final_function_sha = _text_sha(str(before_function.get("content") or ""))

    if function_update_attempted:
        barrier_errors = _restore_old_runtime_state(
            session=session,
            base_url=base_url,
            before_function=before_function,
            before_valves=before_valves,
            before_valves_sha=before_valves_sha,
            stage_prefix="safety_barrier",
        )
        cleanup_errors.extend(barrier_errors)
        safety_barrier_completed = not barrier_errors

    try:
        upload_cleanup = _cleanup_upload_exactly(
            session,
            base_url,
            upload=upload,
            upload_filename=upload_filename,
        )
        upload_id_absent = upload_cleanup["upload_id_absent"]
        upload_alias_absent = upload_cleanup["upload_alias_absent"]
    except BaseException as exc:
        cleanup_errors.append(_cleanup_error("upload", exc))

    try:
        initial_artifact_cleanup = _purge_case_artifacts(
            ssh_target,
            case_id=case_id,
            bundle_source=bundle_source,
        )
        _assert_artifact_cleanup(
            initial_artifact_cleanup,
            require_records=body_passed,
        )
    except BaseException as exc:
        cleanup_errors.append(_cleanup_error("artifacts", exc))

    try:
        after_delete = _runtime_snapshot_strict(ssh_target)
        _assert_post_cleanup_runtime(
            before=before_runtime,
            after_delete=after_delete,
        )
    except BaseException as exc:
        cleanup_errors.append(_cleanup_error("snapshot", exc))

    try:
        quiescence_evidence, quiescent_snapshot = _bounded_terminal_quiescence(
            session=session,
            base_url=base_url,
            ssh_target=ssh_target,
            case_id=case_id,
            bundle_source=bundle_source,
            upload=upload,
            upload_filename=upload_filename,
            before_runtime=before_runtime,
        )
        if quiescent_snapshot is not None:
            after_delete = quiescent_snapshot
        _assert_bounded_quiescence(quiescence_evidence)
    except BaseException as exc:
        cleanup_errors.append(_cleanup_error("quiescence", exc))

    try:
        final_workspace_model = _get_workspace_model(
            session,
            base_url,
            MODEL_ID,
        )
        final_workspace_model_sha = _json_sha(final_workspace_model)
        _assert_workspace_model_unchanged(
            before=before_workspace_model,
            before_sha=before_workspace_model_sha,
            after=final_workspace_model,
        )
        workspace_model_restored_exactly = True
    except BaseException as exc:
        cleanup_errors.append(_cleanup_error("workspace_model", exc))

    if function_update_attempted and body_passed and not cleanup_errors:
        try:
            _update_function_with_timeout_recovery(
                session,
                base_url,
                function=before_function,
                content=bundle_source,
                expected_sha=bundle_sha,
            )
            _restore_valves_exact(
                session,
                base_url,
                before_valves=before_valves,
                before_valves_sha=before_valves_sha,
            )
            live_function = _get_function(session, base_url)
            final_function_sha = _text_sha(
                str(live_function.get("content") or "")
            )
            if (
                final_function_sha != bundle_sha
                or _actual_function_view(live_function)
                != _expected_deployed_function(before_function, bundle_source)
            ):
                raise RuntimeError("canary_final_function_state_mismatch")
            function_retained = True
            terminal_state_restored = True
        except BaseException as exc:
            cleanup_errors.append(_cleanup_error("terminal_deploy", exc))

    if function_update_attempted and not function_retained:
        terminal_errors = _restore_old_runtime_state(
            session=session,
            base_url=base_url,
            before_function=before_function,
            before_valves=before_valves,
            before_valves_sha=before_valves_sha,
            stage_prefix="terminal_restore",
        )
        cleanup_errors.extend(terminal_errors)
        terminal_state_restored = not terminal_errors
        if terminal_state_restored:
            final_function_sha = _text_sha(
                str(before_function.get("content") or "")
            )

    return {
        "after_delete": after_delete,
        "cleanup_errors": cleanup_errors,
        "function_retained": function_retained,
        "final_function_sha256": final_function_sha,
        "upload_id_absent": upload_id_absent,
        "upload_alias_absent": upload_alias_absent,
        "artifact_cleanup": {
            "initial": initial_artifact_cleanup,
            "quiescence": quiescence_evidence,
        },
        "final_workspace_model_sha256": final_workspace_model_sha,
        "workspace_model_restored_exactly": workspace_model_restored_exactly,
        "safety_barrier_completed": safety_barrier_completed,
        "terminal_state_restored": terminal_state_restored,
        "final_valves_sha256": before_valves_sha
        if terminal_state_restored
        else "",
        "valves_restored_exactly": terminal_state_restored,
    }


def _cleanup_error(stage: str, exc: BaseException) -> str:
    return f"{stage}:{type(exc).__name__}:{str(exc)[:80]}"


def _rollback_retained_function_after_terminal_failure(
    *,
    session: requests.Session,
    base_url: str,
    before_function: dict[str, Any],
    before_valves: dict[str, Any],
    before_valves_sha: str,
) -> list[str]:
    return _restore_old_runtime_state(
        session=session,
        base_url=base_url,
        before_function=before_function,
        before_valves=before_valves,
        before_valves_sha=before_valves_sha,
        stage_prefix="output_failure_restore",
    )


def _upload_pdf_process_false(
    session: requests.Session,
    base_url: str,
    path: Path,
    *,
    upload_filename: str,
) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            response = session.post(
                _url(base_url, "/api/v1/files/?process=false"),
                files={"file": (upload_filename, handle, "application/pdf")},
                timeout=120,
            )
    except (requests.Timeout, requests.ConnectionError):
        return _recover_ambiguous_upload(
            session,
            base_url,
            upload_filename=upload_filename,
            expected_size=path.stat().st_size,
        )
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict) or not value.get("id"):
        raise RuntimeError("canary_upload_response_invalid")
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
    upload: dict[str, Any],
    case_id: str,
    timeout: int,
) -> str:
    file_ref = {
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
    prompt = (
        "Gate 1 normalization. Synthetic structural and semantic shadow "
        "canary only. "
        "Do not use Knowledge/RAG, OCR, source-fact extraction, tax calculation, "
        "declaration generation or XLSX export. Return the compact Russian report."
    )
    response = session.post(
        _url(base_url, "/api/chat/completions"),
        json={
            "model": MODEL_ID,
            "stream": False,
            "case_id": case_id,
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
            "metadata": {"case_id": case_id, "files": [file_ref]},
            "messages": [
                {"role": "user", "content": prompt, "files": [file_ref]}
            ],
            "files": [file_ref],
        },
        timeout=timeout,
    )
    response.raise_for_status()
    content = _extract_content(response.json())
    if not content:
        raise RuntimeError("canary_chat_content_missing")
    return content


def _recover_ambiguous_upload(
    session: requests.Session,
    base_url: str,
    *,
    upload_filename: str,
    expected_size: int,
) -> dict[str, Any]:
    for attempt in range(3):
        matches = _find_uploads_by_filename(
            session,
            base_url,
            upload_filename=upload_filename,
        )
        if len(matches) == 1:
            recovered = matches[0]
            recovered_size = int(recovered.get("size") or expected_size)
            if recovered_size != expected_size:
                raise RuntimeError("canary_ambiguous_upload_size_mismatch")
            return {
                "id": str(recovered["id"]),
                "filename": upload_filename,
                "mime_type": "application/pdf",
                "size": recovered_size,
            }
        if len(matches) > 1:
            raise RuntimeError("canary_ambiguous_upload_duplicate_matches")
        if attempt < 2:
            time.sleep(1)
    raise RuntimeError("canary_ambiguous_upload_not_recovered")


def _list_uploads(
    session: requests.Session, base_url: str
) -> list[dict[str, Any]]:
    response = session.get(_url(base_url, "/api/v1/files/"), timeout=60)
    response.raise_for_status()
    value = response.json()
    if isinstance(value, list):
        rows = value
    elif isinstance(value, dict):
        rows = next(
            (
                value.get(key)
                for key in ("items", "files", "data")
                if isinstance(value.get(key), list)
            ),
            None,
        )
        if rows is None:
            raise RuntimeError("canary_file_list_response_invalid")
    else:
        raise RuntimeError("canary_file_list_response_invalid")
    return [item for item in rows if isinstance(item, dict) and item.get("id")]


def _upload_filename(item: dict[str, Any]) -> str:
    meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    return str(
        item.get("filename")
        or item.get("name")
        or meta.get("name")
        or meta.get("filename")
        or ""
    )


def _find_uploads_by_filename(
    session: requests.Session,
    base_url: str,
    *,
    upload_filename: str,
) -> list[dict[str, Any]]:
    return [
        item
        for item in _list_uploads(session, base_url)
        if _upload_filename(item) == upload_filename
    ]


def _upload_exists(
    session: requests.Session, base_url: str, file_id: str
) -> bool:
    response = session.get(
        _url(base_url, f"/api/v1/files/{file_id}"), timeout=60
    )
    if response.status_code == 404:
        return False
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict) or str(value.get("id") or "") != file_id:
        raise RuntimeError("canary_upload_identity_response_invalid")
    return True


def _delete_upload_exact(
    session: requests.Session, base_url: str, file_id: str
) -> None:
    response = session.delete(
        _url(base_url, f"/api/v1/files/{file_id}"), timeout=60
    )
    if response.status_code not in {200, 204, 404}:
        response.raise_for_status()
    if _upload_exists(session, base_url, file_id):
        raise RuntimeError("canary_upload_id_still_present")


def _cleanup_upload_exactly(
    session: requests.Session,
    base_url: str,
    *,
    upload: dict[str, Any] | None,
    upload_filename: str,
) -> dict[str, bool]:
    known_id = str((upload or {}).get("id") or "")
    ids = {known_id} if known_id else set()
    ids.update(
        str(item["id"])
        for item in _find_uploads_by_filename(
            session,
            base_url,
            upload_filename=upload_filename,
        )
    )
    for file_id in sorted(ids):
        _delete_upload_exact(session, base_url, file_id)
    upload_id_absent = not known_id or not _upload_exists(
        session, base_url, known_id
    )
    upload_alias_absent = not _find_uploads_by_filename(
        session,
        base_url,
        upload_filename=upload_filename,
    )
    if not upload_id_absent:
        raise RuntimeError("canary_upload_id_cleanup_unverified")
    if not upload_alias_absent:
        raise RuntimeError("canary_upload_alias_cleanup_unverified")
    return {
        "upload_id_absent": upload_id_absent,
        "upload_alias_absent": upload_alias_absent,
    }


def _purge_case_artifacts(
    ssh_target: str,
    *,
    case_id: str,
    bundle_source: str,
) -> dict[str, Any]:
    code = r'''
import hashlib
import json
from pathlib import Path

bundle_source = __BUNDLE_SOURCE__
case_id = __CASE_ID__
namespace = {"__name__": "broker_reports_gate1_structural_canary_purge_bundle"}
exec(
    compile(
        bundle_source,
        "<broker_reports_gate1_structural_canary_purge_bundle>",
        "exec",
    ),
    namespace,
)
from broker_reports_gate1 import ArtifactStoreConfig, ArtifactStoreFactory

payload_root = Path("/app/backend/data/broker_reports_gate1/payloads")
payload_root_resolved = payload_root.resolve()
store = ArtifactStoreFactory(
    ArtifactStoreConfig(
        mode="sqlite",
        sqlite_path=Path(
            "/app/backend/data/broker_reports_gate1/artifacts.sqlite3"
        ),
        payload_root=payload_root,
    )
).create()
before = store.list_by_case(case_id)
active_before = [
    record
    for record in before
    if record.purge_status != "purged" or record.lifecycle_status != "purged"
]
private_payload_refs_before = [
    record.payload_ref
    for record in active_before
    if record.visibility == "private_case" and record.payload_ref
]
payload_paths = []
for record in active_before:
    if not record.payload_ref:
        continue
    path = (payload_root / record.payload_ref).resolve()
    if payload_root_resolved not in path.parents:
        raise RuntimeError("canary_artifact_payload_path_invalid")
    payload_paths.append(path)
purged = store.purge_case(case_id=case_id)
after = store.list_by_case(case_id)
active_after = [
    record
    for record in after
    if record.purge_status != "purged" or record.lifecycle_status != "purged"
]
private_payload_refs_after = [
    record.payload_ref
    for record in after
    if record.visibility == "private_case" and record.payload_ref
]
tombstones = [
    record
    for record in after
    if record.purge_status == "purged"
    and record.lifecycle_status == "purged"
    and record.storage_backend == "none_tombstone"
    and not record.payload_ref
    and record.payload is None
]
result = {
    "performed": True,
    "records_before_total": len(before),
    "active_records_before_total": len(active_before),
    "private_payload_refs_before_total": len(private_payload_refs_before),
    "payload_files_before_total": len(payload_paths),
    "purged_records_total": len(purged),
    "records_after_total": len(after),
    "active_records_after_total": len(active_after),
    "private_payload_refs_after_total": len(private_payload_refs_after),
    "payload_files_absent": all(not path.exists() for path in payload_paths),
    "tombstone_records_after_total": len(tombstones),
    "all_records_tombstoned": len(tombstones) == len(after),
}
print(json.dumps(result, sort_keys=True))
'''
    code = code.replace(
        "__BUNDLE_SOURCE__",
        json.dumps(bundle_source, ensure_ascii=False),
    ).replace("__CASE_ID__", json.dumps(case_id, ensure_ascii=False))
    return _ssh_json(ssh_target, code, timeout=180)


def _assert_artifact_cleanup(
    cleanup: dict[str, Any],
    *,
    require_records: bool,
) -> None:
    integer_keys = (
        "records_before_total",
        "active_records_before_total",
        "private_payload_refs_before_total",
        "payload_files_before_total",
        "purged_records_total",
        "records_after_total",
        "active_records_after_total",
        "private_payload_refs_after_total",
        "tombstone_records_after_total",
    )
    if any(
        not isinstance(cleanup.get(key), int)
        or isinstance(cleanup.get(key), bool)
        or cleanup[key] < 0
        for key in integer_keys
    ):
        raise RuntimeError("canary_artifact_cleanup_unverified")
    records_before = cleanup["records_before_total"]
    active_before = cleanup["active_records_before_total"]
    records_after = cleanup["records_after_total"]
    if (
        cleanup.get("performed") is not True
        or (require_records and (records_before <= 0 or active_before <= 0))
        or cleanup["private_payload_refs_before_total"]
        > cleanup["payload_files_before_total"]
        or cleanup["purged_records_total"] != active_before
        or records_after != records_before
        or cleanup["active_records_after_total"] != 0
        or cleanup["private_payload_refs_after_total"] != 0
        or cleanup.get("payload_files_absent") is not True
        or cleanup["tombstone_records_after_total"] != records_after
        or cleanup.get("all_records_tombstoned") is not True
    ):
        raise RuntimeError("canary_artifact_cleanup_unverified")


def _wait_quiescence_interval(seconds: float) -> None:
    time.sleep(seconds)


def _bounded_terminal_quiescence(
    *,
    session: requests.Session,
    base_url: str,
    ssh_target: str,
    case_id: str,
    bundle_source: str,
    upload: dict[str, Any] | None,
    upload_filename: str,
    before_runtime: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    observations: list[dict[str, Any]] = []
    errors: list[str] = []
    late_writes_detected = False
    zero_artifact_observations = 0
    post_state_checks_total = 0
    upload_absence_checks_total = 0
    completed_wait_seconds = 0.0
    final_snapshot: dict[str, Any] | None = None
    records_after_total = 0

    for ordinal, wait_seconds in enumerate(
        ARTIFACT_QUIESCENCE_INTERVALS_SECONDS,
        start=1,
    ):
        observation: dict[str, Any] = {
            "ordinal": ordinal,
            "wait_seconds": wait_seconds,
            "active_records_before_purge": None,
            "purged_records_total": None,
            "active_records_after_purge": None,
            "private_payload_refs_after_total": None,
            "payload_files_absent": False,
            "upload_id_absent": False,
            "upload_alias_absent": False,
            "post_state_verified": False,
        }
        try:
            _wait_quiescence_interval(wait_seconds)
            completed_wait_seconds += wait_seconds
        except BaseException as exc:
            errors.append(_cleanup_error(f"quiescence_wait_{ordinal}", exc))

        try:
            upload_cleanup = _cleanup_upload_exactly(
                session,
                base_url,
                upload=upload,
                upload_filename=upload_filename,
            )
            observation["upload_id_absent"] = upload_cleanup[
                "upload_id_absent"
            ]
            observation["upload_alias_absent"] = upload_cleanup[
                "upload_alias_absent"
            ]
            if (
                upload_cleanup["upload_id_absent"]
                and upload_cleanup["upload_alias_absent"]
            ):
                upload_absence_checks_total += 1
        except BaseException as exc:
            errors.append(_cleanup_error(f"quiescence_upload_{ordinal}", exc))

        try:
            cleanup = _purge_case_artifacts(
                ssh_target,
                case_id=case_id,
                bundle_source=bundle_source,
            )
            _assert_artifact_cleanup(cleanup, require_records=False)
            active_before = cleanup["active_records_before_total"]
            purged_total = cleanup["purged_records_total"]
            active_after = cleanup["active_records_after_total"]
            records_after_total = cleanup["records_after_total"]
            observation.update(
                {
                    "active_records_before_purge": active_before,
                    "purged_records_total": purged_total,
                    "active_records_after_purge": active_after,
                    "private_payload_refs_after_total": cleanup[
                        "private_payload_refs_after_total"
                    ],
                    "payload_files_absent": cleanup[
                        "payload_files_absent"
                    ],
                }
            )
            if active_before > 0 or purged_total > 0:
                late_writes_detected = True
            if active_before == 0 and purged_total == 0 and active_after == 0:
                zero_artifact_observations += 1
        except BaseException as exc:
            errors.append(_cleanup_error(f"quiescence_artifacts_{ordinal}", exc))

        try:
            snapshot = _runtime_snapshot_strict(ssh_target)
            _assert_post_cleanup_runtime(
                before=before_runtime,
                after_delete=snapshot,
            )
            final_snapshot = snapshot
            observation["post_state_verified"] = True
            post_state_checks_total += 1
        except BaseException as exc:
            errors.append(_cleanup_error(f"quiescence_snapshot_{ordinal}", exc))
        observations.append(observation)

    required = len(ARTIFACT_QUIESCENCE_INTERVALS_SECONDS)
    verified = bool(
        not errors
        and not late_writes_detected
        and zero_artifact_observations == required
        and post_state_checks_total == required
        and upload_absence_checks_total == required
        and completed_wait_seconds
        == sum(ARTIFACT_QUIESCENCE_INTERVALS_SECONDS)
    )
    evidence = {
        "performed": True,
        "bounded_wait_seconds": completed_wait_seconds,
        "observation_count": len(observations),
        "required_zero_observations": required,
        "zero_artifact_observations": zero_artifact_observations,
        "post_state_checks_total": post_state_checks_total,
        "upload_absence_checks_total": upload_absence_checks_total,
        "late_writes_detected": late_writes_detected,
        "verified": verified,
        "evidence_boundary": (
            "no_late_writes_observed_within_bounded_quiescence_window"
            if verified
            else "bounded_quiescence_failed_or_late_writes_observed"
        ),
        "errors": errors,
        "observations": observations,
        "records_after_total": records_after_total,
    }
    return evidence, final_snapshot


def _assert_bounded_quiescence(evidence: dict[str, Any]) -> None:
    required = len(ARTIFACT_QUIESCENCE_INTERVALS_SECONDS)
    observations = evidence.get("observations")
    if (
        evidence.get("performed") is not True
        or evidence.get("verified") is not True
        or evidence.get("late_writes_detected") is not False
        or evidence.get("errors") != []
        or evidence.get("observation_count") != required
        or evidence.get("required_zero_observations") != required
        or evidence.get("zero_artifact_observations") != required
        or evidence.get("post_state_checks_total") != required
        or evidence.get("upload_absence_checks_total") != required
        or evidence.get("bounded_wait_seconds")
        != sum(ARTIFACT_QUIESCENCE_INTERVALS_SECONDS)
        or evidence.get("evidence_boundary")
        != "no_late_writes_observed_within_bounded_quiescence_window"
        or not isinstance(observations, list)
        or len(observations) != required
        or any(
            not isinstance(item, dict)
            or item.get("active_records_before_purge") != 0
            or item.get("purged_records_total") != 0
            or item.get("active_records_after_purge") != 0
            or item.get("private_payload_refs_after_total") != 0
            or item.get("payload_files_absent") is not True
            or item.get("upload_id_absent") is not True
            or item.get("upload_alias_absent") is not True
            or item.get("post_state_verified") is not True
            for item in observations
        )
    ):
        raise RuntimeError("canary_terminal_quiescence_unverified")


def _fitz_version(ssh_target: str) -> str:
    value = _ssh_json(
        ssh_target,
        "import fitz, json; print(json.dumps({'version': fitz.__version__}))",
        timeout=60,
    )
    return str(value.get("version") or "")


def _runtime_snapshot_strict(ssh_target: str) -> dict[str, Any]:
    code = r'''
import json
import os
import sqlite3
from pathlib import Path

def db_count(conn, table):
    try:
        quoted = str(table).replace('"', '""')
        return int(
            conn.execute(f'select count(*) from "{quoted}"').fetchone()[0]
        )
    except Exception:
        return 0

def tree_stats(path):
    root = Path(path)
    if not root.exists():
        return {
            'exists': False,
            'file_count': 0,
            'dir_count': 0,
            'size_bytes': 0,
            'collections_count': 0,
        }
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
    chroma = root / 'chroma.sqlite3'
    if chroma.exists():
        try:
            with sqlite3.connect(chroma) as conn:
                collections_count = db_count(conn, 'collections')
        except Exception:
            collections_count = 0
    return {
        'exists': True,
        'file_count': file_count,
        'dir_count': dir_count,
        'size_bytes': size_bytes,
        'collections_count': collections_count,
    }

db = {'file_count': 0, 'document_count': 0, 'knowledge_count': 0}
try:
    with sqlite3.connect('/app/backend/data/webui.db') as conn:
        db = {
            'file_count': db_count(conn, 'file'),
            'document_count': db_count(conn, 'document'),
            'knowledge_count': db_count(conn, 'knowledge'),
        }
except Exception:
    pass

artifact_store = {'record_count': 0}
artifact_db = Path('/app/backend/data/broker_reports_gate1/artifacts.sqlite3')
if artifact_db.exists():
    try:
        with sqlite3.connect(artifact_db) as conn:
            artifact_store['record_count'] = db_count(conn, 'artifact_records')
    except Exception:
        pass

vector_path = Path('/app/backend/data/vector_db/chroma.sqlite3')
vector_rag_rows = {'database_exists': vector_path.exists(), 'table_counts': {}}
if vector_path.exists():
    with sqlite3.connect(vector_path) as conn:
        tables = [
            row[0]
            for row in conn.execute(
                "select name from sqlite_master where type='table' order by name"
            ).fetchall()
            if isinstance(row[0], str)
        ]
        for table in tables:
            vector_rag_rows['table_counts'][table] = db_count(conn, table)

print(json.dumps({
    'db': db,
    'vector': tree_stats('/app/backend/data/vector_db'),
    'artifact_store': artifact_store,
    'vector_rag_rows': vector_rag_rows,
}, sort_keys=True))
'''
    return _ssh_json(ssh_target, code, timeout=60)


def _vector_rag_row_snapshot(ssh_target: str) -> dict[str, Any]:
    code = r'''
import json
import sqlite3
from pathlib import Path

path = Path("/app/backend/data/vector_db/chroma.sqlite3")
result = {"database_exists": path.exists(), "table_counts": {}}
if path.exists():
    with sqlite3.connect(path) as conn:
        conn.execute("pragma query_only = on")
        names = [
            str(row[0])
            for row in conn.execute(
                "select name from sqlite_master "
                "where type = 'table' and name not like 'sqlite_%' order by name"
            ).fetchall()
        ]
        for name in names:
            quoted = name.replace('"', '""')
            result["table_counts"][name] = int(
                conn.execute(f'select count(*) from "{quoted}"').fetchone()[0]
            )
print(json.dumps(result, sort_keys=True))
'''
    return _ssh_json(ssh_target, code, timeout=60)


def _safe_counter_view_strict(snapshot: dict[str, Any]) -> dict[str, Any]:
    result = _base_safe_counter_view(snapshot)
    vector_rag_rows = snapshot.get("vector_rag_rows")
    if not isinstance(vector_rag_rows, dict):
        raise RuntimeError("canary_vector_rag_snapshot_missing")
    table_counts = vector_rag_rows.get("table_counts")
    if not isinstance(table_counts, dict) or any(
        not isinstance(key, str)
        or not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
        for key, value in table_counts.items()
    ):
        raise RuntimeError("canary_vector_rag_table_counts_invalid")
    result["vector_rag_database_exists"] = (
        vector_rag_rows.get("database_exists") is True
    )
    result["vector_rag_table_counts"] = dict(sorted(table_counts.items()))
    result["vector_rag_rows_total"] = sum(table_counts.values())
    return result


def _assert_no_rag_counters_unchanged(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    phase: str,
) -> None:
    before_safe = _safe_counter_view_strict(before)
    after_safe = _safe_counter_view_strict(after)
    for key in (
        "document_rows",
        "knowledge_rows",
        "vector_file_count",
        "vector_dir_count",
        "vector_collections_count",
        "vector_size_bytes",
        "vector_rag_database_exists",
        "vector_rag_table_counts",
        "vector_rag_rows_total",
    ):
        if after_safe[key] != before_safe[key]:
            raise RuntimeError(f"canary_no_rag_delta_invalid:{phase}:{key}")


def _assert_post_cleanup_runtime(
    *,
    before: dict[str, Any],
    after_delete: dict[str, Any],
) -> None:
    if (
        _safe_counter_view_strict(after_delete)["file_rows"]
        != _safe_counter_view_strict(before)["file_rows"]
    ):
        raise RuntimeError("canary_upload_row_not_restored")
    _assert_no_rag_counters_unchanged(
        before=before,
        after=after_delete,
        phase="after_delete",
    )


def _artifact_case_summary(
    ssh_target: str,
    case_id: str,
    bundle_source: str,
) -> dict[str, Any]:
    code = r'''
import hashlib
import json
from collections import Counter
from pathlib import Path

bundle_source = __BUNDLE_SOURCE__
case_id = __CASE_ID__
namespace = {"__name__": "broker_reports_gate1_structural_canary_summary_bundle"}
exec(
    compile(
        bundle_source,
        "<broker_reports_gate1_structural_canary_summary_bundle>",
        "exec",
    ),
    namespace,
)
from broker_reports_gate1 import ArtifactStoreConfig, ArtifactStoreFactory

store = ArtifactStoreFactory(
    ArtifactStoreConfig(
        mode='sqlite',
        sqlite_path=Path(
            '/app/backend/data/broker_reports_gate1/artifacts.sqlite3'
        ),
        payload_root=Path('/app/backend/data/broker_reports_gate1/payloads'),
    )
).create()
rows = store.list_by_case(case_id)
types = Counter()
by_type = {}
for row in rows:
    kind = str(row.artifact_type or '')
    types[kind] += 1
    meta = row.safe_metadata
    if not isinstance(meta, dict):
        raise RuntimeError('canary_artifact_safe_metadata_invalid')
    by_type.setdefault(kind, []).append({
        'visibility': str(row.visibility or ''),
        'storage_backend': str(row.storage_backend or ''),
        'validation_status': str(row.validation_status or ''),
        'meta': meta,
        'record': row,
    })

def contract_view(kind):
    selected = by_type.get(kind, [])
    return {
        'count': len(selected),
        'visibility_counts': dict(sorted(Counter(item['visibility'] for item in selected).items())),
        'storage_backend_counts': dict(sorted(Counter(item['storage_backend'] for item in selected).items())),
        'validation_status_counts': dict(sorted(Counter(item['validation_status'] for item in selected).items())),
    }

def private_payload(item):
    value = store.read_payload(item['record'])
    if not isinstance(value, dict):
        raise RuntimeError('canary_artifact_payload_invalid')
    return value

def canonical_sha(value):
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(',', ':'),
        ).encode('utf-8')
    ).hexdigest()

def contains_provider_call_fields(value):
    forbidden = {
        'provider_count_token_call_performed',
        'provider_generate_call_performed',
        'count_token_calls',
        'generate_calls',
        'provider_attempt',
    }
    if isinstance(value, dict):
        return bool(forbidden.intersection(value)) or any(
            contains_provider_call_fields(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(contains_provider_call_fields(item) for item in value)
    return False

target_rows = sorted(
    by_type.get('broker_reports_pdf_structural_repair_target_state_v1', []),
    key=lambda item: str(item['meta'].get('target_id') or ''),
)
runtime_rows = sorted(
    by_type.get('broker_reports_pdf_vlm_guided_intake_result_v1', []),
    key=lambda item: str(item['meta'].get('target_id') or ''),
)
target_payloads = [private_payload(item) for item in target_rows]
runtime_payloads = [private_payload(item) for item in runtime_rows]
runtime = [item['meta'] for item in runtime_rows]
fragment_result_checksums = {
    str(item['meta'].get('target_id') or ''): str(payload.get('result_checksum') or '')
    for item, payload in zip(runtime_rows, runtime_payloads, strict=True)
}
provider_route_records = []
for fragment_ordinal, payload in enumerate(target_payloads, start=1):
    qualification = payload.get('provider_qualification')
    if not isinstance(qualification, dict):
        qualification = {}
    provider_route_records.append({
        'fragment_ordinal': fragment_ordinal,
        'status': qualification.get('status'),
        'provider_profile': qualification.get('provider_profile'),
        'requested_model_id': qualification.get('requested_model_id'),
        'resolved_model_id': qualification.get('resolved_model_id'),
        'exact_model_match': qualification.get('exact_model_match'),
        'native_provider_transport': qualification.get('native_provider_transport'),
        'credentials_from_openwebui_connection': qualification.get(
            'credentials_from_openwebui_connection'
        ),
        'hidden_retry': qualification.get('hidden_retry'),
        'provider_failover': qualification.get('provider_failover'),
    })

provider_journal_records = []
for fragment_ordinal, payload in enumerate(runtime_payloads, start=1):
    journal = payload.get('journal')
    if not isinstance(journal, list):
        journal = []
    entries = sorted(
        (item for item in journal if isinstance(item, dict)),
        key=lambda item: int(item.get('attempt_number') or 0),
    )
    for entry in entries:
        counted = entry.get('count_tokens')
        if not isinstance(counted, dict):
            counted = {}
        attempt = entry.get('provider_attempt')
        if not isinstance(attempt, dict):
            attempt = {}
        usage = attempt.get('usage')
        if not isinstance(usage, dict):
            usage = {}
        counted_input = counted.get('total_tokens')
        actual_input = usage.get('input_tokens')
        output_tokens = usage.get('output_tokens')
        count_performed = entry.get('provider_count_token_call_performed')
        generate_performed = entry.get('provider_generate_call_performed')
        count_tokens_observation_present = bool(
            count_performed is True
            and isinstance(counted_input, int)
            and not isinstance(counted_input, bool)
            and counted_input >= 0
            and counted.get('within_hard_guard') is True
            and counted.get('transport_identity')
            == 'gemini_count_tokens_generate_content_request'
        )
        generate_started_at_present = bool(
            generate_performed is True
            and isinstance(attempt.get('started_at'), str)
            and bool(attempt.get('started_at'))
            and attempt.get('transport_identity')
            == 'gemini_generate_content_native_table_crop_json_schema'
        )
        provider_journal_records.append({
            'fragment_ordinal': fragment_ordinal,
            'attempt_number': entry.get('attempt_number'),
            'count_token_call_performed': count_performed,
            'generate_call_performed': generate_performed,
            'count_tokens_observation_present': count_tokens_observation_present,
            'generate_started_at_present': generate_started_at_present,
            'independent_call_order_proven': False,
            'call_order_evidence_boundary': (
                'runtime_journal_co_recorded_without_count_tokens_timestamp'
            ),
            'counted_input_tokens': counted_input,
            'actual_input_tokens': actual_input,
            'output_tokens': output_tokens,
            'within_input_budget': bool(
                isinstance(counted_input, int)
                and not isinstance(counted_input, bool)
                and 0 <= counted_input <= 20000
            ),
            'within_output_budget': bool(
                isinstance(output_tokens, int)
                and not isinstance(output_tokens, bool)
                and 0 <= output_tokens <= 8192
            ),
            'provider_profile': attempt.get('provider_profile'),
            'model_requested': attempt.get('model_requested'),
            'model_resolved': attempt.get('model_resolved'),
            'finish_reason': attempt.get('finish_reason'),
            'hidden_retry': attempt.get('hidden_retry'),
            'provider_failover': attempt.get('provider_failover'),
        })

def strict_int_total(key):
    return sum(
        item[key]
        for item in provider_journal_records
        if isinstance(item.get(key), int) and not isinstance(item.get(key), bool)
    )

continuation_rows = by_type.get(
    'broker_reports_pdf_structural_repair_continuation_result_v1', []
)
continuation = [item['meta'] for item in continuation_rows]
discoveries = [
    item['meta']
    for item in by_type.get('broker_reports_pdf_continuation_discovery_v1', [])
]
materializations = [
    item['meta']
    for item in by_type.get('broker_reports_pdf_continuation_materialization_v1', [])
]
summaries = [
    item['meta']
    for item in by_type.get('broker_reports_pdf_structural_repair_shadow_summary_v1', [])
]
summary = summaries[0] if len(summaries) == 1 else {}
semantic_rows = sorted(
    by_type.get('broker_reports_pdf_semantic_header_projection_v1', []),
    key=lambda item: (
        str(item['meta'].get('projection_scope') or ''),
        str(item['meta'].get('target_id') or ''),
    ),
)
semantic_payloads = [private_payload(item) for item in semantic_rows]
semantic_records = []
for item, payload in zip(semantic_rows, semantic_payloads, strict=True):
    meta = item['meta']
    scope = str(meta.get('projection_scope') or '')
    target_id = str(meta.get('target_id') or '')
    expected_checksum = (
        fragment_result_checksums.get(target_id)
        if scope == 'fragment'
        else None
    )
    configuration = payload.get('configuration')
    configuration = configuration if isinstance(configuration, dict) else {}
    alternatives = payload.get('physical_alternatives')
    alternatives = alternatives if isinstance(alternatives, list) else []
    context_bytes = [
        alternative.get('context_bytes')
        for alternative in alternatives
        if isinstance(alternative, dict)
    ]
    semantic_records.append({
        'target_id_present': bool(target_id),
        'projection_scope': scope,
        'projection_status': payload.get('projection_status'),
        'semantic_equivalence_status': payload.get('semantic_equivalence_status'),
        'physical_topology_status': payload.get('physical_topology_status'),
        'reason_codes': payload.get('reason_codes'),
        'configuration_schema_version': configuration.get('schema_version'),
        'configuration_max_context_bytes': configuration.get('max_context_bytes'),
        'configuration_bytes': len(
            json.dumps(
                configuration,
                ensure_ascii=False,
                sort_keys=True,
                separators=(',', ':'),
            ).encode('utf-8')
        ),
        'configuration_checksum': payload.get('configuration_checksum'),
        'configuration_checksum_valid': bool(
            configuration
            and payload.get('configuration_checksum') == canonical_sha(configuration)
        ),
        'projection_checksum': payload.get('projection_checksum'),
        'input_hash': payload.get('input_hash'),
        'context_bytes': context_bytes,
        'structural_result_checksum': payload.get('structural_result_checksum'),
        'expected_structural_result_checksum': expected_checksum,
        'structural_result_checksum_bound': bool(
            expected_checksum
            and payload.get('structural_result_checksum') == expected_checksum
        ),
        'source_value_change_allowed': payload.get('source_value_change_allowed'),
        'geometry_change_allowed': payload.get('geometry_change_allowed'),
        'physical_cell_change_allowed': payload.get('physical_cell_change_allowed'),
        'reference_answer_used': payload.get('reference_answer_used'),
        'authority_state': payload.get('authority_state'),
        'production_gate2_selection_changed': payload.get(
            'production_gate2_selection_changed'
        ),
        'provider_call_fields_present': contains_provider_call_fields(payload),
        'safe_metadata_keys': sorted(meta),
        'safe_metadata_matches_payload': bool(
            meta.get('schema_version') == payload.get('schema_version')
            and meta.get('projection_status') == payload.get('projection_status')
            and meta.get('semantic_equivalence_status')
            == payload.get('semantic_equivalence_status')
            and meta.get('physical_topology_status')
            == payload.get('physical_topology_status')
            and meta.get('reason_codes') == payload.get('reason_codes')
            and meta.get('configuration_schema_version')
            == configuration.get('schema_version')
            and meta.get('configuration_checksum')
            == payload.get('configuration_checksum')
            and meta.get('projection_checksum') == payload.get('projection_checksum')
            and meta.get('structural_result_checksum')
            == payload.get('structural_result_checksum')
            and meta.get('input_hash') == payload.get('input_hash')
            and meta.get('authority_state') == payload.get('authority_state')
            and meta.get('production_ready') is False
            and meta.get('production_gate2_selection_changed') is False
        ),
    })
required_contract_types = [
    'broker_reports_pdf_structural_repair_target_state_v1',
    'broker_reports_pdf_vlm_guided_intake_result_v1',
    'broker_reports_pdf_semantic_header_projection_v1',
    'broker_reports_pdf_structural_repair_shadow_summary_v1',
    'broker_reports_pdf_dual_oracle_repeat_history_v1',
    'broker_reports_pdf_structural_repair_runtime_result_v1',
    'broker_reports_pdf_continuation_discovery_v1',
    'broker_reports_pdf_structural_repair_continuation_result_v1',
    'broker_reports_pdf_continuation_materialization_v1',
]
result = {
    'records_total': len(rows),
    'type_counts': dict(sorted(types.items())),
    'record_contracts': {
        kind: contract_view(kind) for kind in required_contract_types
    },
    'target_state_records': [
        {
            'target_id_present': bool(payload.get('target_id')),
            'execution_mode': payload.get('execution_mode'),
            'vlm_guided_intake_enabled': payload.get(
                'vlm_guided_intake_enabled'
            ),
            'repeat_history_scope_empty': payload.get('repeat_history_scope') == {},
            'prior_repeat_history_ref': payload.get('prior_repeat_history_ref'),
            'prior_repeat_history_checksum': payload.get(
                'prior_repeat_history_checksum'
            ),
            'authority_state': payload.get('authority_state'),
            'production_ready': payload.get('production_ready'),
            'production_gate2_selection_changed': payload.get(
                'production_gate2_selection_changed'
            ),
        }
        for payload in target_payloads
    ],
    'fragment_runtime_records': [
        {
            'schema_version': payload.get('schema_version'),
            'target_id_present': bool(meta.get('target_id')),
            'execution_contract': payload.get('execution_contract'),
            'proposal_decision': payload.get('proposal_decision'),
            'post_validation_passed': (
                payload.get('post_validation', {}).get('passed')
                if isinstance(payload.get('post_validation'), dict)
                else None
            ),
            'terminal_status': meta.get('runtime_terminal_status'),
            'count_token_calls': meta.get('count_token_calls'),
            'generate_calls': meta.get('generate_calls'),
            'all_candidates_accounted': meta.get('all_candidates_accounted'),
            'model_invented_values_total': meta.get('model_invented_values_total'),
            'hidden_retry': meta.get('hidden_retry'),
            'provider_failover': meta.get('provider_failover'),
            'authority_state': payload.get('authority_state'),
            'production_ready': payload.get('production_ready'),
            'production_gate2_selection_changed': payload.get(
                'production_gate2_selection_changed'
            ),
        }
        for meta, payload in zip(runtime, runtime_payloads, strict=True)
    ],
    'provider_route_records': provider_route_records,
    'provider_journal_records': provider_journal_records,
    'provider_token_totals': {
        'count_token_calls': sum(
            item.get('count_token_call_performed') is True
            for item in provider_journal_records
        ),
        'generate_calls': sum(
            item.get('generate_call_performed') is True
            for item in provider_journal_records
        ),
        'counted_input_tokens': strict_int_total('counted_input_tokens'),
        'actual_input_tokens': strict_int_total('actual_input_tokens'),
        'output_tokens': strict_int_total('output_tokens'),
    },
    'count_token_calls': sum(int(item.get('count_token_calls') or 0) for item in runtime),
    'generate_calls': sum(int(item.get('generate_calls') or 0) for item in runtime),
    'all_candidates_accounted': bool(runtime) and all(
        item.get('all_candidates_accounted') is True for item in runtime
    ),
    'model_invented_values_total': sum(
        int(item.get('model_invented_values_total') or 0) for item in runtime
    ),
    'hidden_retry': any(item.get('hidden_retry') is not False for item in runtime),
    'provider_failover': any(item.get('provider_failover') is not False for item in runtime),
    'distinct_fragment_target_ids': len({
        str(item.get('target_id')) for item in runtime if item.get('target_id')
    }),
    'semantic_projection_records': semantic_records,
    'semantic_new_provider_count_token_calls': (
        sum(
            item.get('count_token_call_performed') is True
            for item in provider_journal_records
        )
        - sum(int(item.get('count_token_calls') or 0) for item in runtime)
        - sum(
            int(item.get('new_provider_count_token_calls') or 0)
            for item in continuation
        )
    ),
    'semantic_new_provider_generate_calls': (
        sum(
            item.get('generate_call_performed') is True
            for item in provider_journal_records
        )
        - sum(int(item.get('generate_calls') or 0) for item in runtime)
        - sum(
            int(item.get('new_provider_generate_calls') or 0)
            for item in continuation
        )
    ),
    'continuation_records': [
        {
            'terminal_status': item.get('terminal_status'),
            'fragment_count': item.get('fragment_count'),
            'row_count': item.get('row_count'),
            'column_count': item.get('column_count'),
            'all_candidates_accounted': item.get('all_candidates_accounted'),
            'model_invented_values_total': item.get('model_invented_values_total'),
            'new_provider_count_token_calls': item.get('new_provider_count_token_calls'),
            'new_provider_generate_calls': item.get('new_provider_generate_calls'),
            'authority_state': item.get('authority_state'),
            'production_ready': item.get('production_ready'),
            'production_gate2_selection_changed': item.get('production_gate2_selection_changed'),
        }
        for item in continuation
    ],
    'discovery_records': [
        {
            'status': item.get('status'),
            'groups_total': item.get('groups_total'),
            'not_grouped_total': item.get('not_grouped_total'),
            'manual_review_required': item.get('manual_review_required'),
            'deterministic_geometry_only': item.get('deterministic_geometry_only'),
            'text_or_values_used': item.get('text_or_values_used'),
            'vlm_used': item.get('vlm_used'),
            'authority_state': item.get('authority_state'),
            'production_ready': item.get('production_ready'),
            'production_gate2_selection_changed': item.get('production_gate2_selection_changed'),
        }
        for item in discoveries
    ],
    'materialization_records': [
        {
            'row_count': item.get('row_count'),
            'column_count': item.get('column_count'),
            'candidate_ownership_exact': item.get('candidate_ownership_exact'),
            'model_invented_values_total': item.get('model_invented_values_total'),
            'authority_state': item.get('authority_state'),
            'production_ready': item.get('production_ready'),
            'production_gate2_selection_changed': item.get('production_gate2_selection_changed'),
        }
        for item in materializations
    ],
    'tables_selected': int(summary.get('tables_selected') or 0),
    'accepted_supplied_consensus_tables': int(summary.get('accepted_supplied_consensus_tables') or 0),
    'accepted_physical_structure_tables': int(summary.get('accepted_physical_structure_tables') or 0),
    'vlm_guided_intake_enabled': summary.get('vlm_guided_intake_enabled'),
    'private_repeat_histories_persisted': int(summary.get('private_repeat_histories_persisted') or 0),
    'continuation_groups_discovered': int(summary.get('continuation_groups_discovered') or 0),
    'continuation_groups_accepted': int(summary.get('continuation_groups_accepted') or 0),
    'continuation_groups_failed': int(summary.get('continuation_groups_failed') or 0),
    'continuation_descriptors_not_grouped': int(summary.get('continuation_descriptors_not_grouped') or 0),
    'continuation_manual_review_required': summary.get('continuation_manual_review_required'),
    'private_continuation_discoveries_persisted': int(summary.get('private_continuation_discoveries_persisted') or 0),
    'private_continuation_results_persisted': int(summary.get('private_continuation_results_persisted') or 0),
    'private_continuation_materializations_persisted': int(summary.get('private_continuation_materializations_persisted') or 0),
    'semantic_header_shadow_enabled': summary.get('semantic_header_shadow_enabled'),
    'semantic_projection_status_counts': summary.get('semantic_projection_status_counts'),
    'semantic_projection_reason_counts': summary.get('semantic_projection_reason_counts'),
    'private_semantic_projections_persisted': int(summary.get('private_semantic_projections_persisted') or 0),
    'private_semantic_diagnostics_persisted': int(summary.get('private_semantic_diagnostics_persisted') or 0),
    'base_normalization_mutated': summary.get('base_normalization_mutated'),
    'knowledge_rag_used': summary.get('knowledge_rag_used'),
    'customer_values_included': summary.get('customer_values_included'),
    'crop_bytes_included': summary.get('crop_bytes_included'),
    'raw_provider_response_included': summary.get('raw_provider_response_included'),
    'private_diagnostics_included': summary.get('private_diagnostics_included'),
    'authority_state': summary.get('authority_state'),
    'production_ready': summary.get('production_ready'),
    'production_gate2_selection_changed': summary.get('production_gate2_selection_changed'),
}
print(json.dumps(result, sort_keys=True))
'''
    code = code.replace(
        "__BUNDLE_SOURCE__",
        json.dumps(bundle_source, ensure_ascii=False),
    ).replace("__CASE_ID__", json.dumps(case_id, ensure_ascii=False))
    return _ssh_json(ssh_target, code, timeout=60)


def _ssh_json(
    ssh_target: str, code: str, *, timeout: int
) -> dict[str, Any]:
    proc = subprocess.run(
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
        input=code,
        text=True,
        capture_output=True,
        encoding="utf-8",
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError("canary_ssh_command_failed")
    value = json.loads(proc.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("canary_ssh_json_invalid")
    return value


def _assert_canary(
    *,
    chat_content: str,
    artifacts: dict[str, Any],
    before: dict[str, Any],
    after_upload: dict[str, Any],
    after_chat: dict[str, Any],
) -> None:
    if artifacts.get("tables_selected") != EXPECTED_FRAGMENT_RUNTIME_RECORDS:
        raise RuntimeError("canary_tables_selected_invalid")
    if (
        artifacts.get("vlm_guided_intake_enabled") is not True
        or artifacts.get("accepted_physical_structure_tables")
        != EXPECTED_FRAGMENT_RUNTIME_RECORDS
        or artifacts.get("accepted_supplied_consensus_tables") != 0
    ):
        raise RuntimeError("canary_guided_fragment_terminal_invalid")
    if (
        artifacts.get("private_repeat_histories_persisted") != 0
        or artifacts.get("continuation_groups_discovered") != 0
        or artifacts.get("continuation_groups_accepted") != 0
        or artifacts.get("continuation_groups_failed") != 0
        or artifacts.get("continuation_descriptors_not_grouped") != 0
        or artifacts.get("continuation_manual_review_required") is not False
        or artifacts.get("private_continuation_discoveries_persisted") != 0
        or artifacts.get("private_continuation_results_persisted") != 0
        or artifacts.get("private_continuation_materializations_persisted") != 0
    ):
        raise RuntimeError("canary_repeat_or_continuation_unexpected")
    if (
        artifacts.get("semantic_header_shadow_enabled") is not True
        or artifacts.get("private_semantic_projections_persisted")
        != EXPECTED_SEMANTIC_PROJECTION_RECORDS
        or artifacts.get("private_semantic_diagnostics_persisted") != 0
    ):
        raise RuntimeError("canary_semantic_summary_invalid")
    if any(
        artifacts.get(key) is not expected
        for key, expected in {
            "knowledge_rag_used": False,
            "customer_values_included": False,
            "crop_bytes_included": False,
            "raw_provider_response_included": False,
            "private_diagnostics_included": False,
            "base_normalization_mutated": False,
            "production_ready": False,
            "production_gate2_selection_changed": False,
        }.items()
    ) or artifacts.get("authority_state") != "non_authoritative":
        raise RuntimeError("canary_shadow_safety_summary_invalid")

    types = artifacts.get("type_counts") or {}
    required_types = {
        "broker_reports_pdf_structural_repair_target_state_v1": 2,
        "broker_reports_pdf_vlm_guided_intake_result_v1": 2,
        "broker_reports_pdf_semantic_header_projection_v1": (
            EXPECTED_SEMANTIC_PROJECTION_RECORDS
        ),
        "broker_reports_pdf_structural_repair_shadow_summary_v1": 1,
    }
    forbidden_types = (
        "broker_reports_pdf_dual_oracle_repeat_history_v1",
        "broker_reports_pdf_structural_repair_runtime_result_v1",
        "broker_reports_pdf_continuation_discovery_v1",
        "broker_reports_pdf_structural_repair_continuation_result_v1",
        "broker_reports_pdf_continuation_materialization_v1",
    )
    if any(int(types.get(key) or 0) != count for key, count in required_types.items()):
        raise RuntimeError("canary_structural_artifact_missing")
    if any(int(types.get(key) or 0) != 0 for key in forbidden_types):
        raise RuntimeError("canary_forbidden_artifact_present")
    if int(types.get("broker_reports_pdf_structural_repair_private_diagnostic_v1") or 0):
        raise RuntimeError("canary_private_diagnostic_unexpected")
    if int(types.get("broker_reports_pdf_semantic_header_private_diagnostic_v1") or 0):
        raise RuntimeError("canary_semantic_diagnostic_unexpected")

    contracts = artifacts.get("record_contracts")
    if not isinstance(contracts, dict):
        raise RuntimeError("canary_record_contracts_missing")
    private_types = set(required_types) - {
        "broker_reports_pdf_structural_repair_shadow_summary_v1"
    }
    for artifact_type, expected_count in required_types.items():
        contract = contracts.get(artifact_type)
        if not isinstance(contract, dict) or contract.get("count") != expected_count:
            raise RuntimeError("canary_record_contract_count_invalid")
        expected_visibility = (
            "safe_internal"
            if artifact_type
            == "broker_reports_pdf_structural_repair_shadow_summary_v1"
            else "private_case"
        )
        expected_backend = (
            "project_artifact_store"
            if artifact_type
            == "broker_reports_pdf_structural_repair_shadow_summary_v1"
            else "project_artifact_payload"
        )
        if (
            contract.get("visibility_counts")
            != {expected_visibility: expected_count}
            or contract.get("storage_backend_counts")
            != {expected_backend: expected_count}
            or contract.get("validation_status_counts")
            != {"validated": expected_count}
        ):
            raise RuntimeError("canary_record_contract_state_invalid")
        if artifact_type in private_types and expected_visibility != "private_case":
            raise RuntimeError("canary_private_record_visibility_invalid")
    for artifact_type in forbidden_types:
        contract = contracts.get(artifact_type)
        if not isinstance(contract, dict) or contract != {
            "count": 0,
            "visibility_counts": {},
            "storage_backend_counts": {},
            "validation_status_counts": {},
        }:
            raise RuntimeError("canary_forbidden_record_contract_invalid")

    target_records = artifacts.get("target_state_records")
    if (
        not isinstance(target_records, list)
        or len(target_records) != EXPECTED_FRAGMENT_RUNTIME_RECORDS
        or any(
            record
            != {
                "target_id_present": True,
                "execution_mode": "guided_candidate_crop",
                "vlm_guided_intake_enabled": True,
                "repeat_history_scope_empty": True,
                "prior_repeat_history_ref": None,
                "prior_repeat_history_checksum": None,
                "authority_state": "non_authoritative",
                "production_ready": False,
                "production_gate2_selection_changed": False,
            }
            for record in target_records
        )
    ):
        raise RuntimeError("canary_guided_target_state_invalid")

    semantic_records = artifacts.get("semantic_projection_records")
    if (
        not isinstance(semantic_records, list)
        or len(semantic_records) != EXPECTED_SEMANTIC_PROJECTION_RECORDS
        or [
            item.get("projection_scope")
            for item in semantic_records
            if isinstance(item, dict)
        ].count("fragment")
        != EXPECTED_FRAGMENT_RUNTIME_RECORDS
    ):
        raise RuntimeError("canary_semantic_artifact_set_invalid")
    expected_safe_metadata_keys = sorted(
        {
            "schema_version",
            "target_id",
            "projection_scope",
            "projection_status",
            "semantic_equivalence_status",
            "physical_topology_status",
            "physical_alternatives_total",
            "semantic_fields_total",
            "qualifiers_total",
            "reason_codes",
            "configuration_schema_version",
            "configuration_checksum",
            "projection_checksum",
            "structural_result_checksum",
            "input_hash",
            "authority_state",
            "production_ready",
            "production_gate2_selection_changed",
        }
    )
    derived_semantic_status_counts: dict[str, int] = {}
    derived_semantic_reason_counts: dict[str, int] = {}
    for record in semantic_records:
        context_bytes = record.get("context_bytes")
        configuration_checksum = record.get("configuration_checksum")
        projection_checksum = record.get("projection_checksum")
        input_hash = record.get("input_hash")
        structural_result_checksum = record.get(
            "structural_result_checksum"
        )
        projection_status = record.get("projection_status")
        reason_codes = record.get("reason_codes")
        if (
            record.get("target_id_present") is not True
            or projection_status not in {"projected", "incomplete"}
            or record.get("semantic_equivalence_status")
            != (
                "not_applicable"
                if projection_status == "projected"
                else "incomplete"
            )
            or record.get("physical_topology_status")
            != "accepted_supplied_consensus"
            or not isinstance(reason_codes, list)
            or any(
                not isinstance(reason, str)
                or not reason.startswith("pdf_semantic_header_")
                or len(reason) > 160
                for reason in reason_codes
            )
            or record.get("configuration_schema_version")
            != EXPECTED_SEMANTIC_CONFIGURATION_SCHEMA
            or record.get("configuration_max_context_bytes")
            != MAX_SEMANTIC_CONTEXT_BYTES
            or not isinstance(record.get("configuration_bytes"), int)
            or isinstance(record.get("configuration_bytes"), bool)
            or record.get("configuration_bytes") <= 0
            or record.get("configuration_bytes")
            > MAX_SEMANTIC_CONTEXT_BYTES
            or not isinstance(configuration_checksum, str)
            or len(configuration_checksum) != 64
            or any(
                character not in "0123456789abcdef"
                for character in configuration_checksum
            )
            or record.get("configuration_checksum_valid") is not True
            or not isinstance(projection_checksum, str)
            or len(projection_checksum) != 64
            or any(
                character not in "0123456789abcdef"
                for character in projection_checksum
            )
            or not isinstance(input_hash, str)
            or len(input_hash) != 64
            or any(
                character not in "0123456789abcdef"
                for character in input_hash
            )
            or not isinstance(context_bytes, list)
            or len(context_bytes) != 1
            or any(
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
                or value > MAX_SEMANTIC_CONTEXT_BYTES
                for value in context_bytes
            )
            or record.get("structural_result_checksum_bound") is not True
            or not isinstance(structural_result_checksum, str)
            or len(structural_result_checksum) != 64
            or any(
                character not in "0123456789abcdef"
                for character in structural_result_checksum
            )
            or structural_result_checksum
            != record.get("expected_structural_result_checksum")
            or record.get("source_value_change_allowed") is not False
            or record.get("geometry_change_allowed") is not False
            or record.get("physical_cell_change_allowed") is not False
            or record.get("reference_answer_used") is not False
            or record.get("authority_state") != "non_authoritative"
            or record.get("production_gate2_selection_changed") is not False
            or record.get("provider_call_fields_present") is not False
            or record.get("safe_metadata_keys") != expected_safe_metadata_keys
            or record.get("safe_metadata_matches_payload") is not True
        ):
            raise RuntimeError("canary_semantic_artifact_invalid")
        derived_semantic_status_counts[projection_status] = (
            derived_semantic_status_counts.get(projection_status, 0) + 1
        )
        for reason in set(reason_codes):
            derived_semantic_reason_counts[reason] = (
                derived_semantic_reason_counts.get(reason, 0) + 1
            )
    if (
        artifacts.get("semantic_projection_status_counts")
        != derived_semantic_status_counts
        or artifacts.get("semantic_projection_reason_counts")
        != derived_semantic_reason_counts
        or "projection_failed" in derived_semantic_status_counts
    ):
        raise RuntimeError("canary_semantic_summary_invalid")
    if (
        artifacts.get("semantic_new_provider_count_token_calls") != 0
        or artifacts.get("semantic_new_provider_generate_calls") != 0
    ):
        raise RuntimeError("canary_semantic_provider_call_invalid")

    fragment_records = artifacts.get("fragment_runtime_records")
    if (
        not isinstance(fragment_records, list)
        or len(fragment_records) != EXPECTED_FRAGMENT_RUNTIME_RECORDS
        or artifacts.get("distinct_fragment_target_ids")
        != EXPECTED_FRAGMENT_RUNTIME_RECORDS
    ):
        raise RuntimeError("canary_fragment_runtime_set_invalid")
    for record in fragment_records:
        if not isinstance(record, dict) or record != {
            "schema_version": "broker_reports_pdf_vlm_guided_intake_result_v1",
            "target_id_present": True,
            "execution_contract": "candidate_crop_one_call_v1",
            "proposal_decision": "bound",
            "post_validation_passed": True,
            "terminal_status": "accepted_physical_structure",
            "count_token_calls": EXPECTED_COUNT_TOKEN_CALLS_PER_FRAGMENT,
            "generate_calls": EXPECTED_GENERATE_CALLS_PER_FRAGMENT,
            "all_candidates_accounted": True,
            "model_invented_values_total": 0,
            "hidden_retry": False,
            "provider_failover": False,
            "authority_state": "non_authoritative",
            "production_ready": False,
            "production_gate2_selection_changed": False,
        }:
            raise RuntimeError("canary_fragment_runtime_accounting_invalid")

    provider_routes = artifacts.get("provider_route_records")
    if (
        not isinstance(provider_routes, list)
        or len(provider_routes) != EXPECTED_FRAGMENT_RUNTIME_RECORDS
    ):
        raise RuntimeError("canary_provider_route_invalid")
    for fragment_ordinal, record in enumerate(provider_routes, start=1):
        if record != {
            "fragment_ordinal": fragment_ordinal,
            "status": "qualified",
            "provider_profile": EXPECTED_PROVIDER_PROFILE,
            "requested_model_id": EXPECTED_PROVIDER_MODEL,
            "resolved_model_id": EXPECTED_PROVIDER_MODEL,
            "exact_model_match": True,
            "native_provider_transport": True,
            "credentials_from_openwebui_connection": True,
            "hidden_retry": False,
            "provider_failover": False,
        }:
            raise RuntimeError("canary_provider_route_invalid")

    provider_journal = artifacts.get("provider_journal_records")
    expected_provider_calls = (
        EXPECTED_FRAGMENT_RUNTIME_RECORDS
        * EXPECTED_COUNT_TOKEN_CALLS_PER_FRAGMENT
    )
    if (
        not isinstance(provider_journal, list)
        or len(provider_journal) != expected_provider_calls
    ):
        raise RuntimeError("canary_provider_token_accounting_invalid")
    expected_pairs = {
        (fragment_ordinal, attempt_number)
        for fragment_ordinal in range(1, EXPECTED_FRAGMENT_RUNTIME_RECORDS + 1)
        for attempt_number in range(
            1, EXPECTED_COUNT_TOKEN_CALLS_PER_FRAGMENT + 1
        )
    }
    observed_pairs: set[tuple[int, int]] = set()
    counted_input_total = 0
    actual_input_total = 0
    output_total = 0
    count_token_calls = 0
    generate_calls = 0
    for record in provider_journal:
        if not isinstance(record, dict):
            raise RuntimeError("canary_provider_token_accounting_invalid")
        pair = (record.get("fragment_ordinal"), record.get("attempt_number"))
        if pair not in expected_pairs or pair in observed_pairs:
            raise RuntimeError("canary_provider_token_accounting_invalid")
        observed_pairs.add(pair)
        counted_input = record.get("counted_input_tokens")
        actual_input = record.get("actual_input_tokens")
        output_tokens = record.get("output_tokens")
        if (
            not isinstance(counted_input, int)
            or isinstance(counted_input, bool)
            or counted_input < 0
            or counted_input > MAX_COUNTED_INPUT_TOKENS
            or not isinstance(actual_input, int)
            or isinstance(actual_input, bool)
            or actual_input != counted_input
            or not isinstance(output_tokens, int)
            or isinstance(output_tokens, bool)
            or output_tokens < 0
            or output_tokens > MAX_PROVIDER_OUTPUT_TOKENS
            or record.get("count_token_call_performed") is not True
            or record.get("generate_call_performed") is not True
            or record.get("count_tokens_observation_present") is not True
            or record.get("generate_started_at_present") is not True
            or record.get("independent_call_order_proven") is not False
            or record.get("call_order_evidence_boundary")
            != PROVIDER_ORDER_EVIDENCE_BOUNDARY
            or record.get("within_input_budget") is not True
            or record.get("within_output_budget") is not True
            or record.get("provider_profile") != EXPECTED_PROVIDER_PROFILE
            or record.get("model_requested") != EXPECTED_PROVIDER_MODEL
            or record.get("model_resolved") != EXPECTED_PROVIDER_MODEL
            or record.get("finish_reason") != "STOP"
            or record.get("hidden_retry") is not False
            or record.get("provider_failover") is not False
        ):
            raise RuntimeError("canary_provider_token_accounting_invalid")
        count_token_calls += 1
        generate_calls += 1
        counted_input_total += counted_input
        actual_input_total += actual_input
        output_total += output_tokens
    if observed_pairs != expected_pairs:
        raise RuntimeError("canary_provider_token_accounting_invalid")
    provider_totals = {
        "count_token_calls": count_token_calls,
        "generate_calls": generate_calls,
        "counted_input_tokens": counted_input_total,
        "actual_input_tokens": actual_input_total,
        "output_tokens": output_total,
    }
    if (
        artifacts.get("provider_token_totals") != provider_totals
        or artifacts.get("count_token_calls") != count_token_calls
        or artifacts.get("generate_calls") != generate_calls
    ):
        raise RuntimeError("canary_provider_token_accounting_invalid")

    discovery_records = artifacts.get("discovery_records")
    continuation_records = artifacts.get("continuation_records")
    materialization_records = artifacts.get("materialization_records")
    if (
        discovery_records != []
        or continuation_records != []
        or materialization_records != []
    ):
        raise RuntimeError("canary_continuation_record_unexpected")

    before_safe = _safe_counter_view_strict(before)
    upload_safe = _safe_counter_view_strict(after_upload)
    chat_safe = _safe_counter_view_strict(after_chat)
    if upload_safe["file_rows"] - before_safe["file_rows"] != 1:
        raise RuntimeError("canary_process_false_file_delta_invalid")
    if chat_safe["file_rows"] != upload_safe["file_rows"]:
        raise RuntimeError("canary_chat_file_row_delta_invalid")
    _assert_no_rag_counters_unchanged(
        before=before,
        after=after_upload,
        phase="after_upload",
    )
    _assert_no_rag_counters_unchanged(
        before=before,
        after=after_chat,
        phase="after_chat",
    )

    forbidden = (
        "```json",
        "```",
        "openwebui-file",
        "private-structural-canary",
        "provider_payload",
        "exact_source_span",
        "pdftablecand_",
        "broker_reports_pdf_",
        "schema_version",
        "safe_metadata",
        "continuation_group_id",
        "physical_columns",
        "semantic_fields",
        "structural_result_checksum",
        "projection_checksum",
        "pdfsemantic",
        "2026-01-01",
        "2026-01-02",
        "2026-01-03",
        "2026-01-04",
        "2026-01-05",
        "2026-01-06",
        "2026-01-07",
        "10.00",
        "20.00",
        "30.00",
        "40.00",
        "50.00",
        "60.00",
        "70.00",
        "USD",
        "EUR",
        "GBP",
        "CHF",
        "JPY",
        "CNY",
        "CAD",
    )
    if any(marker in chat_content for marker in forbidden):
        raise RuntimeError("canary_private_chat_marker_detected")
    if "Продолжения таблиц на соседней странице:" in chat_content:
        raise RuntimeError("canary_continuation_chat_unexpected")
    if (
        not chat_content.strip()
        or len(chat_content) > MAX_COMPACT_REPORT_CHARS
        or chat_content.lstrip().startswith(("{", "["))
        or "\ufffd" in chat_content
        or "Рќ" in chat_content
    ):
        raise RuntimeError("canary_compact_report_shape_invalid")
    required_chat_markers = (
        "Автоматическая проверка структуры PDF-таблиц",
        "Выбрано таблиц: 2",
        "согласовано двумя проверками в переданном наборе: 0",
        "основной результат Gate 2 не изменён",
        "Семантические заголовки",
        f"сохранено приватных проекций "
        f"{EXPECTED_SEMANTIC_PROJECTION_RECORDS}",
        "статусы:",
    )
    if any(marker not in chat_content for marker in required_chat_markers):
        raise RuntimeError("canary_compact_pdf_report_missing")
    rendered_semantic_counts = ", ".join(
        f"{key}: {int(value)}"
        for key, value in sorted(derived_semantic_status_counts.items())
    )
    if f"статусы: {rendered_semantic_counts}" not in chat_content:
        raise RuntimeError("canary_compact_semantic_status_missing")


def _candidate_refs(pdf_bytes: bytes) -> list[str]:
    result = Gate1Normalizer().normalize(
        [
            FileInput.from_bytes(
                private_ref="canary-private-file",
                filename="synthetic-guided-intake-fragments.pdf",
                content=pdf_bytes,
                mime_type="application/pdf",
            )
        ],
        entrypoint="structural_shadow_canary_prepare",
        trigger_type="synthetic_canary",
    )
    payloads = result.package.get("private_normalized_source_payloads") or []
    refs = [
        str(item.get("table_candidate_ref"))
        for payload in payloads
        if isinstance(payload, dict)
        for item in (
            payload.get("pdf_text_layer_projection", {}).get(
                "table_candidate_inventory", []
            )
        )
        if isinstance(item, dict) and item.get("table_candidate_ref")
    ]
    return sorted(set(refs))


def _two_fragment_guided_intake_pdf() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=320, height=320)
    font = writer._add_object(
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    operators = _table_operators(
        bottom=210,
        top=310,
        rows=(
            (295, "Date", "Amount", "Currency"),
            (270, "2026-01-01", "10.00", "USD"),
            (245, "2026-01-02", "20.00", "EUR"),
            (220, "2026-01-03", "30.00", "GBP"),
        ),
    )
    operators.extend(
        _table_operators(
            bottom=10,
            top=110,
            rows=(
                (95, "Date", "Amount", "Currency"),
                (70, "2026-01-04", "40.00", "CHF"),
                (45, "2026-01-05", "50.00", "JPY"),
                (20, "2026-01-06", "60.00", "CNY"),
            ),
        )
    )
    stream = DecodedStreamObject()
    stream.set_data("\n".join(operators).encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _table_operators(
    *,
    bottom: int,
    top: int,
    rows: tuple[tuple[int, str, str, str], ...],
) -> list[str]:
    operators = [
        f"BT /F1 8 Tf {x} {y} Td ({_pdf_escape(value)}) Tj ET"
        for y, left, middle, right in rows
        for x, value in ((25, left), (125, middle), (225, right))
    ]
    for y in range(bottom, top + 1, 25):
        operators.append(f"20 {y} m 300 {y} l S")
    for x in (20, 110, 210, 300):
        operators.append(f"{x} {bottom} m {x} {top} l S")
    return operators


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _text_sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _safe_output_path(path: Path) -> str:
    try:
        value = path.resolve().relative_to(ROOT.resolve())
    except ValueError:
        value = Path(path.name)
    return str(value).replace("\\", "/")


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "code": str(exc)[:160],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        raise
