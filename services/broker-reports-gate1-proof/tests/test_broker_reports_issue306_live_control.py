from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SERVICE_ROOT / "scripts/live_gate5_openwebui_product_path_control.py"
BROWSER_GOAL_PATH = SERVICE_ROOT / "scripts/live_issue306_openwebui_browser_goal.js"
RECEIPT_BUILDER_PATH = (
    SERVICE_ROOT / "scripts/build_issue306_safe_interaction_receipt.py"
)


def _load_control_module():
    spec = importlib.util.spec_from_file_location("issue306_live_control", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _receipt_sha256(value: dict) -> str:
    base = {key: item for key, item in value.items() if key != "receipt_sha256"}
    encoded = json.dumps(
        base, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_prepare_uses_current_release_owned_valves(monkeypatch, tmp_path: Path) -> None:
    control = _load_control_module()
    release_contracts = importlib.import_module(
        "scripts.broker_reports_atomic_stage_release_contracts"
    )
    accepted_keys = {
        *release_contracts.GATE1_RELEASE_VALVES,
        "ndfl_gate3_private_audit_enabled",
        "ndfl_gate3_private_audit_id",
    }
    captured: dict[str, object] = {}
    monkeypatch.setattr(control.secrets, "token_hex", lambda _size: "a" * 32)

    monkeypatch.setattr(control, "_read_env", lambda _path: {})
    monkeypatch.setattr(control, "_admin_session", lambda _env, _url: object())
    monkeypatch.setattr(
        control,
        "_get_function",
        lambda _session, _url: {"id": control.FUNCTION_ID, "is_global": True},
    )
    legacy = {"id": control.LEGACY_FUNCTION_ID, "is_active": True}
    monkeypatch.setattr(
        control,
        "_get_legacy_function",
        lambda _session, _url: dict(legacy),
    )

    def toggle_function_active(_session, _url, function_id):
        assert function_id == control.LEGACY_FUNCTION_ID
        legacy["is_active"] = not legacy["is_active"]
        return dict(legacy)

    monkeypatch.setattr(control, "_toggle_function_active", toggle_function_active)
    monkeypatch.setattr(control, "_get_valves", lambda _session, _url: {})
    monkeypatch.setattr(
        control,
        "_get_model",
        lambda _session, _url: {
            "id": control.MODEL_ID,
            "access_grants": [],
        },
    )
    monkeypatch.setattr(
        control,
        "_deploy_bundle",
        lambda _session, _url, _function: ("previous-sha", "deployed-sha"),
    )
    monkeypatch.setattr(
        control,
        "_create_user",
        lambda _session, _url, *, suffix, role: {
            "id": f"user-{suffix}",
            "email": f"issue306-{suffix}@example.invalid",
            "password": f"password-{suffix}",
            "role": role,
        },
    )
    monkeypatch.setattr(
        control,
        "_update_model_grants",
        lambda _session, _url, grants: {
            "id": control.MODEL_ID,
            "access_grants": grants,
        },
    )
    monkeypatch.setattr(
        control,
        "_user_model_visibility",
        lambda _url, email, _password: "-a@" in email,
    )
    monkeypatch.setattr(
        control,
        "_delete_user",
        lambda _session, _url, _user_id: None,
    )

    def update_valves(_session, _url, valves):
        captured["submitted_valves"] = dict(valves)
        return {key: value for key, value in valves.items() if key in accepted_keys}

    monkeypatch.setattr(control, "_update_valves", update_valves)

    output_dir = tmp_path / "control"
    args = SimpleNamespace(
        env_file=str(tmp_path / "unused.env"),
        base_url="http://issue306.invalid",
        output_dir=str(output_dir),
        audit_id="",
    )

    assert control._prepare(args) == 0
    submitted = captured["submitted_valves"]
    assert isinstance(submitted, dict)
    for key, expected in release_contracts.GATE1_RELEASE_VALVES.items():
        assert submitted[key] == expected
    assert not (set(submitted) & set(release_contracts.GATE1_RETIRED_VALVE_KEYS))

    private_state = json.loads(
        (output_dir / "control.private.json").read_text(encoding="utf-8")
    )
    safe_state = json.loads(
        (output_dir / "control-prepared.safe.json").read_text(encoding="utf-8")
    )
    assert private_state["deployed_bundle_sha256"] == "deployed-sha"
    assert private_state["control_prepared_receipt_sha256"] == safe_state[
        "receipt_sha256"
    ]
    assert safe_state["status"] == "prepared"
    assert safe_state["control_run_id"] == "a" * 32
    assert private_state["control_run_id"] == safe_state["control_run_id"]
    assert safe_state["temporary_users"] == 2
    assert safe_state["legacy_function_inactive"] is True
    assert private_state["original_legacy_function_active"] is True
    assert legacy["is_active"] is False
    assert safe_state["receipt_sha256"] == _receipt_sha256(safe_state)
    assert safe_state["predecessor_control_prepared_receipt_sha256"] is None

    second_state = dict(private_state, control_run_id="b" * 32)
    second_safe = control._safe_result(second_state, status="prepared")
    assert second_safe["receipt_sha256"] != safe_state["receipt_sha256"]


def test_browser_goal_driver_cannot_bypass_rendered_openwebui_boundaries() -> None:
    source = BROWSER_GOAL_PATH.read_text(encoding="utf-8")

    assert "chromium.launch" in source
    assert "input[type=file]" in source
    assert "#chat-input" in source
    assert "Скачать XML" in source
    assert "page.evaluate" not in source
    assert ".request." not in source
    assert "fetch(" not in source
    assert "/api/chat" not in source
    assert "getAttribute('href')" in source
    assert "ISSUE306_SOURCE_SMOKE_ONLY" in source
    assert "representative_source_blocked_before_declaration" in source
    assert "hidden_architecture_leaked_into_chat" in source
    assert "broker_reports_issue306_browser_run_receipt_v2" in source
    assert "installed_bundle_not_current_tested_bytes" in source
    assert "unanswered_tab_closed_and_second_case_admitted" in source
    assert "final_summary_verified" in source
    assert "answer = 'INITIAL'" not in source
    assert "answer = 'SELF'" not in source
    assert "answer = 'PAYMENT'" not in source
    assert "answer = 'individual_not_ip_not_private_practice'" not in source
    assert "childProcess.execFileSync" in source
    assert "page.close()" in source


def test_issue306_receipt_builder_uses_owner_xml_and_rejects_tampering(
    tmp_path: Path,
) -> None:
    spec = importlib.util.spec_from_file_location(
        "issue306_receipt_builder", RECEIPT_BUILDER_PATH
    )
    assert spec is not None and spec.loader is not None
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    receipt = {
        "schema_version": "broker_reports_issue306_browser_run_receipt_v2",
        "run_id": "run-a",
        "events": [],
    }
    receipt["receipt_sha256"] = builder._sha_json(receipt)
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")

    assert builder._read_receipt(path)["run_id"] == "run-a"
    receipt["run_id"] = "run-b"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    try:
        builder._read_receipt(path)
    except builder.Issue306ReceiptError as exc:
        assert str(exc) == "issue306_receipt_hash_invalid"
    else:
        raise AssertionError("tampered receipt must fail closed")

    source = RECEIPT_BUILDER_PATH.read_text(encoding="utf-8")
    assert "Gate5FullTargetXmlProjectionRuntimeFactory" in source
    assert "issue306_visible_xml_values_mismatch" in source
    assert "issue306_clean_run_xml_bytes_differ" in source


def test_issue306_supported_source_has_owner_visible_direct_expense() -> None:
    fixture = SERVICE_ROOT / "tests/fixtures/issue306_supported_ordinary_trade.csv"
    with fixture.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 2
    disposal = next(row for row in rows if row["Вид"] == "Продажа")
    assert disposal["Комиссия Брокера"] == "1.00"
    assert disposal["Комиссия Биржи"] == "0.00"
