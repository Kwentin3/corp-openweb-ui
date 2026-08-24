#!/usr/bin/env python3
"""Build one mechanically verified, privacy-safe Issue #306 live receipt."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
SERVICE_ROOT = SCRIPT_PATH.parent.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
BUNDLE_PATH = SERVICE_ROOT / "openwebui_actions/broker_reports_gate1_pipe_bundled.py"
BROWSER_DRIVER_PATH = SCRIPT_PATH.parent / "live_issue306_openwebui_browser_goal.js"
CONTROL_PATH = SCRIPT_PATH.parent / "live_gate5_openwebui_product_path_control.py"

sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.gate5_full_target_xml_projection import (  # noqa: E402
    Gate5FullTargetXmlProjectionRuntimeFactory,
)


class Issue306ReceiptError(RuntimeError):
    pass


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_json(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return _sha_bytes(encoded)


def _read_receipt(path: Path, *, schema: str | None = None) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Issue306ReceiptError("issue306_receipt_not_object")
    receipt_sha256 = value.get("receipt_sha256")
    base = {key: copy.deepcopy(item) for key, item in value.items() if key != "receipt_sha256"}
    if receipt_sha256 != _sha_json(base):
        raise Issue306ReceiptError("issue306_receipt_hash_invalid")
    if schema is not None and value.get("schema_version") != schema:
        raise Issue306ReceiptError("issue306_receipt_schema_invalid")
    return value


def _event(receipt: dict[str, Any], event_code: str) -> list[dict[str, Any]]:
    events = receipt.get("events")
    if not isinstance(events, list):
        raise Issue306ReceiptError("issue306_browser_events_invalid")
    return [item for item in events if isinstance(item, dict) and item.get("event") == event_code]


def _validate_clean_run(receipt: dict[str, Any]) -> dict[str, str]:
    if (
        receipt.get("run_kind") != "clean_room"
        or receipt.get("browser_ui_only") is not True
        or receipt.get("hidden_refs_observed") is not False
        or receipt.get("document_contents_recorded") is not False
        or receipt.get("developer_intervention_during_user_run") is not False
    ):
        raise Issue306ReceiptError("issue306_clean_run_boundary_invalid")
    answers = _event(receipt, "question_answered")
    families = {str(item.get("question_family")) for item in answers}
    required = {
        "residency",
        "capacity",
        "zero_scope",
        "identity",
        "filing",
        "date",
        "destination",
        "signer",
        "budget",
        "oktmo",
    }
    if not required.issubset(families):
        raise Issue306ReceiptError("issue306_question_matrix_incomplete")
    if not any(
        item.get("question_family") == "identity"
        and item.get("intentionally_invalid") is True
        and item.get("accepted") is False
        for item in answers
    ):
        raise Issue306ReceiptError("issue306_invalid_inn_not_proven")
    if not any(
        item.get("question_family") == "date"
        and item.get("intentionally_invalid") is True
        and item.get("accepted") is False
        for item in answers
    ):
        raise Issue306ReceiptError("issue306_invalid_date_not_proven")
    if not any(
        item.get("question_family") == "identity" and item.get("deferred") is True
        for item in answers
    ):
        raise Issue306ReceiptError("issue306_deferred_answer_not_proven")
    summary = _event(receipt, "final_summary_verified")
    if len(summary) != 1 or summary[0].get("required_sections_visible") is not True:
        raise Issue306ReceiptError("issue306_final_summary_not_proven")
    visible = summary[0].get("visible_values")
    keys = {
        "total_income",
        "accepted_expenses",
        "tax_base",
        "calculated_tax",
        "tax_payable",
    }
    if not isinstance(visible, dict) or set(visible) != keys:
        raise Issue306ReceiptError("issue306_visible_values_invalid")
    downloads = _event(receipt, "private_xml_downloaded")
    if len(downloads) != 1:
        raise Issue306ReceiptError("issue306_private_download_not_proven")
    if len(_event(receipt, "accepted_value_corrected")) != 1:
        raise Issue306ReceiptError("issue306_correction_not_proven")
    retries = _event(receipt, "resume_and_concurrent_retry")
    if (
        len(retries) != 1
        or retries[0].get("reload_resumed") is not True
        or retries[0].get("logical_download_links_stable") is not True
    ):
        raise Issue306ReceiptError("issue306_retry_not_proven")
    denials = _event(receipt, "second_user_denied")
    if (
        len(denials) != 1
        or denials[0].get("private_file_denied") is not True
        or denials[0].get("case_denied") is not True
    ):
        raise Issue306ReceiptError("issue306_cross_user_denial_not_proven")
    return {key: str(visible[key]) for key in sorted(keys)}


def _validate_source_run(receipt: dict[str, Any]) -> None:
    if receipt.get("run_kind") != "representative_source":
        raise Issue306ReceiptError("issue306_source_run_kind_invalid")
    events = _event(receipt, "representative_source_blocked_before_declaration")
    if (
        len(events) != 1
        or events[0].get("xml_created") is not False
        or events[0].get("private_download_created") is not False
        or events[0].get("typed_blocker_visible") is not True
    ):
        raise Issue306ReceiptError("issue306_source_blocker_not_proven")


def _validate_binding(
    receipt: dict[str, Any], *, expected: dict[str, str]
) -> None:
    binding = receipt.get("proof_binding")
    if not isinstance(binding, dict):
        raise Issue306ReceiptError("issue306_proof_binding_missing")
    for key, value in expected.items():
        if binding.get(key) != value:
            raise Issue306ReceiptError("issue306_proof_binding_mismatch:" + key)
    tested_commit = binding.get("tested_commit")
    if not isinstance(tested_commit, str) or re.fullmatch(r"[0-9a-f]{40}", tested_commit) is None:
        raise Issue306ReceiptError("issue306_tested_commit_invalid")


def _owner_verify_xml(path: Path, visible: dict[str, str]) -> dict[str, Any]:
    xml_bytes = path.read_bytes()
    extracted = (
        Gate5FullTargetXmlProjectionRuntimeFactory.create()
        .extract_supported_profile_values(xml_bytes=xml_bytes)
    )
    if extracted.get("status") != "extracted" or extracted.get("xsd_valid") is not True:
        raise Issue306ReceiptError("issue306_xml_owner_rejected")
    income = extracted.get("values", {}).get("income_group")
    if not isinstance(income, dict):
        raise Issue306ReceiptError("issue306_xml_income_values_missing")
    actual = {key: str(income.get(key)) for key in visible}
    if actual != visible:
        raise Issue306ReceiptError("issue306_visible_xml_values_mismatch")
    if any(marker in xml_bytes for marker in (b"TODO", b"PLACEHOLDER", b"UNKNOWN")):
        raise Issue306ReceiptError("issue306_xml_placeholder_detected")
    return {
        "xml_sha256": _sha_bytes(xml_bytes),
        "xml_size_bytes": len(xml_bytes),
        "projection_owner_schema_version": extracted["schema_version"],
        "projection_owner_proof_sha256": extracted["proof_sha256"],
        "xsd_valid": True,
        "visible_values_match": True,
        "values": actual,
        "placeholders_total": 0,
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    clean_paths = [Path(value).resolve() for value in args.clean_run]
    xml_paths = [Path(value).resolve() for value in args.xml]
    restored_paths = [Path(value).resolve() for value in args.control_restored]
    if len(clean_paths) != 2 or len(xml_paths) != 2 or len(restored_paths) != 2:
        raise Issue306ReceiptError("issue306_two_clean_runs_required")
    clean = [
        _read_receipt(path, schema="broker_reports_issue306_browser_run_receipt_v2")
        for path in clean_paths
    ]
    source = _read_receipt(
        Path(args.source_run).resolve(),
        schema="broker_reports_issue306_browser_run_receipt_v2",
    )
    restored = [
        _read_receipt(path, schema="broker_reports_gate5_openwebui_control_v0")
        for path in restored_paths
    ]
    expected = {
        "generated_bundle_sha256": _sha_bytes(BUNDLE_PATH.read_bytes()),
        "browser_driver_sha256": _sha_bytes(BROWSER_DRIVER_PATH.read_bytes()),
        "control_script_sha256": _sha_bytes(CONTROL_PATH.read_bytes()),
    }
    for item in [*clean, source]:
        _validate_binding(item, expected=expected)
    if len({item["run_id"] for item in clean}) != 2:
        raise Issue306ReceiptError("issue306_clean_run_identity_not_independent")
    visible = [_validate_clean_run(item) for item in clean]
    _validate_source_run(source)
    close_events = [
        event
        for item in clean
        for event in _event(item, "unanswered_tab_closed_and_second_case_admitted")
    ]
    if not close_events:
        raise Issue306ReceiptError("issue306_close_tab_not_proven")
    if any(int(event.get("second_elapsed_ms", 30000)) >= 30000 for event in close_events):
        raise Issue306ReceiptError("issue306_close_tab_release_not_prompt")
    owner_verification = [
        _owner_verify_xml(path, shown) for path, shown in zip(xml_paths, visible)
    ]
    for item, verification in zip(clean, owner_verification):
        download = _event(item, "private_xml_downloaded")[0]
        if (
            download.get("sha256") != verification["xml_sha256"]
            or download.get("bytes") != verification["xml_size_bytes"]
        ):
            raise Issue306ReceiptError("issue306_browser_xml_binding_mismatch")
    if owner_verification[0]["xml_sha256"] != owner_verification[1]["xml_sha256"]:
        raise Issue306ReceiptError("issue306_clean_run_xml_bytes_differ")
    for item in restored:
        if item.get("status") != "restored" or item.get("state_restored") is not True:
            raise Issue306ReceiptError("issue306_control_not_restored")
        if item.get("deployed_bundle_sha256") != expected["generated_bundle_sha256"]:
            raise Issue306ReceiptError("issue306_restored_control_bundle_mismatch")
    prepared_receipts = {
        str(item.get("predecessor_control_prepared_receipt_sha256"))
        for item in restored
    }
    if len(prepared_receipts) != 2 or "None" in prepared_receipts:
        raise Issue306ReceiptError("issue306_control_prepared_restored_chain_invalid")
    for item in [*clean, source]:
        if (
            item["proof_binding"].get("control_prepared_receipt_sha256")
            not in prepared_receipts
        ):
            raise Issue306ReceiptError("issue306_browser_control_chain_invalid")
    tested_commits = sorted(
        {item["proof_binding"]["tested_commit"] for item in [*clean, source]}
    )
    base = {
        "schema_version": "broker_reports_issue306_safe_interaction_proof_v2",
        "exact_base_sha": args.base_sha,
        "tested_commits": tested_commits,
        "tested_code_manifest": {
            "generated_bundle_sha256": expected["generated_bundle_sha256"],
            "browser_driver_sha256": expected["browser_driver_sha256"],
            "control_script_sha256": expected["control_script_sha256"],
            "receipt_builder_sha256": _sha_bytes(SCRIPT_PATH.read_bytes()),
        },
        "user_mode": {
            "clean_room_runs": clean,
            "representative_source_run": source,
        },
        "verification_mode": {
            "owner_xml_verification": owner_verification,
            "downloaded_xml_byte_equal_between_runs": True,
            "control_restored_receipts": restored,
        },
        "developer_mode": {
            "diagnostic_intervention_during_clean_runs": False,
            "new_tax_source_or_identity_authority_added": False,
        },
        "privacy": {
            "pii_recorded": False,
            "secrets_recorded": False,
            "hidden_refs_recorded": False,
            "document_contents_recorded": False,
        },
    }
    return {**base, "receipt_sha256": _sha_json(base)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--clean-run", action="append", required=True)
    parser.add_argument("--xml", action="append", required=True)
    parser.add_argument("--source-run", required=True)
    parser.add_argument("--control-restored", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if re.fullmatch(r"[0-9a-f]{40}", args.base_sha) is None:
        raise Issue306ReceiptError("issue306_base_sha_invalid")
    result = build(args)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "passed", "output": str(output), "receipt_sha256": result["receipt_sha256"]}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "error_code": str(exc)[:200],
                }
            ),
            file=sys.stderr,
        )
        raise
