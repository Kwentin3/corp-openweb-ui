from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SERVICE_ROOT / "scripts/live_gate5_openwebui_product_path_control.py"
BROWSER_GOAL_PATH = SERVICE_ROOT / "scripts/live_issue306_openwebui_browser_goal.js"


def _load_control_module():
    spec = importlib.util.spec_from_file_location("issue306_live_control", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    assert safe_state["status"] == "prepared"
    assert safe_state["temporary_users"] == 2
    assert safe_state["legacy_function_inactive"] is True
    assert private_state["original_legacy_function_active"] is True
    assert legacy["is_active"] is False


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


def test_issue306_supported_source_has_owner_visible_direct_expense() -> None:
    fixture = SERVICE_ROOT / "tests/fixtures/issue306_supported_ordinary_trade.csv"
    with fixture.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 2
    disposal = next(row for row in rows if row["Вид"] == "Продажа")
    assert disposal["Комиссия Брокера"] == "1.00"
    assert disposal["Комиссия Биржи"] == "0.00"
