from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = SERVICE_ROOT / "scripts"
sys.path.insert(0, str(SCRIPT_ROOT))

import live_publish_ndfl_workspace_model as publisher  # noqa: E402

from broker_reports_gate1.gate3_ndfl_workflow import (  # noqa: E402
    NDFL_OPENWEBUI_BASE_PIPE_ID,
    NDFL_PROVIDER_MODEL_ID,
    NDFL_PROVIDER_PROFILE_ID,
    NDFL_WORKFLOW_STABLE_ID,
    NDFL_WORKSPACE_MODEL_STABLE_ID,
    ndfl_product_binding_snapshot,
)


def _legacy_model() -> dict:
    return {
        "id": "test",
        "base_model_id": NDFL_OPENWEBUI_BASE_PIPE_ID,
        "name": "test display",
        "meta": {
            "capabilities": {
                "file_upload": True,
                "file_context": False,
                "citations": True,
            },
            "tags": [],
        },
        "params": {},
        "access_grants": [],
        "is_active": True,
    }


def test_product_binding_snapshot_uses_only_stable_machine_ids() -> None:
    assert ndfl_product_binding_snapshot() == {
        "schema_version": "broker_reports_ndfl_product_binding_v1",
        "workspace_model_id": NDFL_WORKSPACE_MODEL_STABLE_ID,
        "base_pipe_id": NDFL_OPENWEBUI_BASE_PIPE_ID,
        "workflow_id": NDFL_WORKFLOW_STABLE_ID,
        "provider_profile_id": NDFL_PROVIDER_PROFILE_ID,
        "provider_model_id": NDFL_PROVIDER_MODEL_ID,
        "dictionary_id": "broker-reports-financial-labels",
        "dictionary_semantic_version": "2.0.0",
        "role_pack_id": "broker-reports-financial-roles",
        "role_pack_semantic_version": "3.0.0",
        "skill_id": "broker-reports-financial-labels",
        "tool_id": "broker_reports_financial_label_dictionary",
        "tool_method": "load_financial_label_dictionary",
        "prompt_id": None,
        "knowledge_ids": [],
    }


def test_ndfl_workspace_model_is_a_facade_without_knowledge_or_tools() -> None:
    desired = publisher.desired_ndfl_model(
        previous=None,
        legacy=_legacy_model(),
    )
    check = publisher.evaluate_ndfl_model(desired)
    assert check["routing_passed"] is True
    assert check["display_name_match"] is True
    assert check["managed_tags_match"] is True
    assert desired["base_model_id"] == NDFL_OPENWEBUI_BASE_PIPE_ID
    assert desired["access_grants"] == [publisher.ORDINARY_USER_READ_GRANT]
    assert desired["meta"]["knowledge"] == []
    assert desired["meta"]["toolIds"] == []
    assert desired["meta"]["skillIds"] == []


def test_ndfl_workspace_model_presents_a_user_task_without_internal_stages() -> None:
    desired = publisher.desired_ndfl_model(previous=None, legacy=_legacy_model())
    meta = desired["meta"]

    assert "3-НДФЛ" in meta["description"]
    assert "брокерский отчёт" in meta["description"]
    assert "Gate" not in meta["description"]
    assert "workflow" not in meta["description"].lower()
    assert [item["content"] for item in meta["suggestion_prompts"]] == [
        "Помогите подготовить 3-НДФЛ по брокерскому отчёту.",
        "Проверьте брокерский отчёт и объясните, какие операции можно рассчитать.",
    ]


def test_ndfl_product_keeps_facade_and_technical_pipe_ids_strictly_separate() -> None:
    desired = publisher.desired_ndfl_model(
        previous=None,
        legacy=_legacy_model(),
    )

    assert NDFL_WORKSPACE_MODEL_STABLE_ID == "broker-reports-ndfl"
    assert NDFL_OPENWEBUI_BASE_PIPE_ID == "broker_reports_gate1_pipe"
    assert publisher.FUNCTION_ID == NDFL_OPENWEBUI_BASE_PIPE_ID
    assert NDFL_OPENWEBUI_BASE_PIPE_ID != NDFL_WORKSPACE_MODEL_STABLE_ID
    assert desired["id"] == NDFL_WORKSPACE_MODEL_STABLE_ID
    assert desired["base_model_id"] == NDFL_OPENWEBUI_BASE_PIPE_ID
    assert publisher._is_managed_ndfl(desired) is True
    assert publisher.evaluate_visible_routes(
        [{"id": NDFL_WORKSPACE_MODEL_STABLE_ID}]
    )["passed"] is True


def test_display_name_rename_does_not_change_behavioral_binding() -> None:
    desired = publisher.desired_ndfl_model(
        previous=None,
        legacy=_legacy_model(),
    )
    renamed = copy.deepcopy(desired)
    renamed["name"] = "Renamed human-facing title"
    check = publisher.evaluate_ndfl_model(renamed)
    assert check["display_name_match"] is False
    assert check["routing_passed"] is True
    assert (
        renamed["meta"]["broker_reports_product_binding"]
        == desired["meta"]["broker_reports_product_binding"]
    )


def test_only_legacy_technical_pipe_overrides_are_inactive() -> None:
    assert NDFL_OPENWEBUI_BASE_PIPE_ID not in publisher.HIDDEN_TECHNICAL_PIPE_IDS
    for pipe_id in publisher.HIDDEN_TECHNICAL_PIPE_IDS:
        desired = publisher.desired_hidden_pipe_model(
            pipe_id,
            previous=None,
        )
        check = publisher.evaluate_hidden_pipe_model(desired, pipe_id)
        assert all(check.values())
        assert desired["base_model_id"] is None
        assert desired["is_active"] is False

    legacy_override = publisher.desired_hidden_pipe_model(
        publisher.LEGACY_PIPE_IDS[0],
        previous=None,
    )
    assert legacy_override["access_grants"] == []

    existing_acl_override = {
        "id": publisher.HIDDEN_TECHNICAL_PIPE_IDS[0],
        "base_model_id": None,
        "name": "human title",
        "meta": {
            "profile_image_url": None,
            "description": None,
            "capabilities": None,
        },
        "params": {},
    }
    assert publisher._is_safe_existing_pipe_override(
        existing_acl_override,
        publisher.HIDDEN_TECHNICAL_PIPE_IDS[0],
    )
    assert publisher.evaluate_base_pipe_override(None) == {
        "absent": True,
        "passed": True,
    }


def test_required_runtime_base_function_is_fail_closed() -> None:
    base_function = {
        "id": NDFL_OPENWEBUI_BASE_PIPE_ID,
        "type": "pipe",
        "is_active": True,
        "is_global": False,
    }

    assert (
        publisher.evaluate_required_base_function(base_function)["passed"]
        is True
    )
    inactive_function = {**base_function, "is_active": False}
    global_function = {**base_function, "is_global": True}
    assert (
        publisher.evaluate_required_base_function(inactive_function)["passed"]
        is False
    )
    assert (
        publisher.evaluate_required_base_function(global_function)["passed"]
        is False
    )


def test_facade_acl_preserves_custom_grants_and_adds_ordinary_user_read() -> None:
    previous = publisher.desired_ndfl_model(
        previous=None,
        legacy=_legacy_model(),
    )
    previous["access_grants"] = [
        {
            "principal_type": "group",
            "principal_id": "accountants",
            "permission": "read",
        }
    ]

    desired = publisher.desired_ndfl_model(previous=previous, legacy=None)

    assert desired["access_grants"] == [
        {
            "principal_type": "group",
            "principal_id": "accountants",
            "permission": "read",
        },
        publisher.ORDINARY_USER_READ_GRANT,
    ]
    assert publisher.evaluate_ndfl_model(desired)["routing_passed"] is True


def test_existing_binding_meaning_is_preserved_during_topology_repair() -> None:
    previous = publisher.desired_ndfl_model(previous=None, legacy=_legacy_model())
    previous["meta"]["broker_reports_product_binding"].update(
        {
            "provider_profile_id": "existing-provider-profile",
            "provider_model_id": "existing-provider-model",
            "dictionary_semantic_version": "1.0.0",
        }
    )

    desired = publisher.desired_ndfl_model(previous=previous, legacy=None)
    binding = desired["meta"]["broker_reports_product_binding"]

    assert binding["provider_profile_id"] == "existing-provider-profile"
    assert binding["provider_model_id"] == "existing-provider-model"
    assert binding["dictionary_semantic_version"] == "1.0.0"
    assert binding["workspace_model_id"] == NDFL_WORKSPACE_MODEL_STABLE_ID
    assert binding["base_pipe_id"] == NDFL_OPENWEBUI_BASE_PIPE_ID
    assert publisher.evaluate_ndfl_model(desired)["routing_passed"] is True


def test_admin_model_catalog_does_not_claim_ordinary_user_visibility() -> None:
    assert publisher.evaluate_visible_routes(
        [
            {"id": NDFL_WORKSPACE_MODEL_STABLE_ID},
            {"id": "unrelated-model"},
        ]
    ) == {
        "visible_product_route_ids": [NDFL_WORKSPACE_MODEL_STABLE_ID],
        "admin_visible_internal_runtime_base_ids": [],
        "user_facing_ndfl_models": 1,
        "admin_visible_legacy_or_competing_route_ids": [],
        "passed": True,
        "ordinary_user_visibility_proof": "browser_acceptance_required",
    }
    assert publisher.evaluate_visible_routes(
        [{"id": NDFL_WORKSPACE_MODEL_STABLE_ID}]
    )["passed"] is True
    assert publisher.evaluate_visible_routes(
        [
            {"id": NDFL_WORKSPACE_MODEL_STABLE_ID},
            {"id": NDFL_OPENWEBUI_BASE_PIPE_ID},
        ]
    ) == {
        "visible_product_route_ids": [NDFL_WORKSPACE_MODEL_STABLE_ID],
        "admin_visible_internal_runtime_base_ids": [NDFL_OPENWEBUI_BASE_PIPE_ID],
        "user_facing_ndfl_models": 1,
        "admin_visible_legacy_or_competing_route_ids": [NDFL_OPENWEBUI_BASE_PIPE_ID],
        "passed": True,
        "ordinary_user_visibility_proof": "browser_acceptance_required",
    }
    assert publisher.evaluate_visible_routes(
        [
            {"id": NDFL_WORKSPACE_MODEL_STABLE_ID},
            {"id": publisher.LEGACY_NDFL_MODEL_ID},
        ]
    )["passed"] is True


def test_publish_deletes_only_the_managed_same_id_base_override(monkeypatch, capsys) -> None:
    facade = publisher.desired_ndfl_model(previous=None, legacy=_legacy_model())
    managed_base_override = publisher.desired_hidden_pipe_model(
        NDFL_OPENWEBUI_BASE_PIPE_ID,
        previous=None,
    )
    legacy_overrides = {
        pipe_id: publisher.desired_hidden_pipe_model(pipe_id, previous=None)
        for pipe_id in publisher.HIDDEN_TECHNICAL_PIPE_IDS
    }
    previous_by_id = {
        NDFL_WORKSPACE_MODEL_STABLE_ID: facade,
        NDFL_OPENWEBUI_BASE_PIPE_ID: managed_base_override,
        publisher.LEGACY_NDFL_MODEL_ID: None,
        publisher.LEGACY_WORKSPACE_MODEL_ID: None,
        **legacy_overrides,
    }
    current_by_id = copy.deepcopy(previous_by_id)
    reads: dict[str, int] = {}
    deleted: list[str] = []

    class _Session:
        def __init__(self) -> None:
            self.headers: dict[str, str] = {}

    def fake_get_model(_session, _base_url, stable_id):
        reads[stable_id] = reads.get(stable_id, 0) + 1
        source = previous_by_id if reads[stable_id] == 1 else current_by_id
        return copy.deepcopy(source[stable_id])

    def fake_delete_model(_session, _base_url, *, stable_id):
        assert stable_id == NDFL_OPENWEBUI_BASE_PIPE_ID
        assert publisher._is_managed_hidden_route(
            previous_by_id[stable_id], stable_id
        )
        current_by_id[stable_id] = None
        deleted.append(stable_id)
        return "deleted"

    monkeypatch.setattr(publisher.requests, "Session", _Session)
    monkeypatch.setattr(publisher, "_read_env", lambda _path: {})
    monkeypatch.setattr(publisher, "_base_url", lambda _env: "https://invalid")
    monkeypatch.setattr(publisher, "_signin", lambda *_args: "token")
    monkeypatch.setattr(publisher, "_get_model", fake_get_model)
    monkeypatch.setattr(
        publisher,
        "_get_function",
        lambda *_args: {
            "id": NDFL_OPENWEBUI_BASE_PIPE_ID,
            "type": "pipe",
            "is_active": True,
            "is_global": False,
        },
    )
    monkeypatch.setattr(
        publisher,
        "_publish_model",
        lambda *_args, **_kwargs: pytest.fail("base override must not be republished"),
    )
    monkeypatch.setattr(publisher, "_delete_model", fake_delete_model)
    monkeypatch.setattr(
        publisher,
        "_get_visible_models",
        lambda *_args: [{"id": NDFL_WORKSPACE_MODEL_STABLE_ID}],
    )
    monkeypatch.setattr(sys, "argv", ["publisher", "--publish"])

    assert publisher.main() == 0

    result = json.loads(capsys.readouterr().out)
    assert deleted == [NDFL_OPENWEBUI_BASE_PIPE_ID]
    assert result["actions"][NDFL_OPENWEBUI_BASE_PIPE_ID] == "deleted"
    assert result["checks"]["base_model_override"] == {
        "absent": True,
        "passed": True,
    }
    assert result["checks"]["required_base_function"]["passed"] is True
    assert result["checks"]["ndfl_workspace_model"]["routing_passed"] is True
    assert result["checks"]["visible_routes"]["passed"] is True


def test_unmanaged_same_id_base_override_fails_before_delete(monkeypatch) -> None:
    facade = publisher.desired_ndfl_model(previous=None, legacy=_legacy_model())
    previous_by_id = {
        NDFL_WORKSPACE_MODEL_STABLE_ID: facade,
        NDFL_OPENWEBUI_BASE_PIPE_ID: {
            "id": NDFL_OPENWEBUI_BASE_PIPE_ID,
            "base_model_id": None,
            "meta": {},
            "params": {},
        },
        publisher.LEGACY_NDFL_MODEL_ID: None,
        publisher.LEGACY_WORKSPACE_MODEL_ID: None,
        **{pipe_id: None for pipe_id in publisher.HIDDEN_TECHNICAL_PIPE_IDS},
    }

    class _Session:
        def __init__(self) -> None:
            self.headers: dict[str, str] = {}

    monkeypatch.setattr(publisher.requests, "Session", _Session)
    monkeypatch.setattr(publisher, "_read_env", lambda _path: {})
    monkeypatch.setattr(publisher, "_base_url", lambda _env: "https://invalid")
    monkeypatch.setattr(publisher, "_signin", lambda *_args: "token")
    monkeypatch.setattr(
        publisher,
        "_get_model",
        lambda _session, _base_url, stable_id: copy.deepcopy(previous_by_id[stable_id]),
    )
    monkeypatch.setattr(
        publisher,
        "_get_function",
        lambda *_args: {
            "id": NDFL_OPENWEBUI_BASE_PIPE_ID,
            "type": "pipe",
            "is_active": True,
            "is_global": False,
        },
    )
    monkeypatch.setattr(
        publisher,
        "_delete_model",
        lambda *_args, **_kwargs: pytest.fail("unmanaged override must not be deleted"),
    )
    monkeypatch.setattr(sys, "argv", ["publisher", "--publish"])

    with pytest.raises(
        publisher.NdflWorkspacePublishError,
        match="technical_route_override_id_collision:broker_reports_gate1_pipe",
    ):
        publisher.main()


def test_postdelete_failure_restores_previous_managed_base_override(monkeypatch) -> None:
    previous_facade = publisher.desired_ndfl_model(
        previous=None,
        legacy=_legacy_model(),
    )
    previous_facade["name"] = "Previous title"
    desired_facade = publisher.desired_ndfl_model(
        previous=previous_facade,
        legacy=None,
    )
    retired_models = {
        pipe_id: publisher.desired_hidden_pipe_model(pipe_id, previous=None)
        for pipe_id in publisher.LEGACY_PIPE_IDS
    }
    previous_base_override = publisher.desired_hidden_pipe_model(
        NDFL_OPENWEBUI_BASE_PIPE_ID,
        previous=None,
    )
    previous_by_id = {
        NDFL_WORKSPACE_MODEL_STABLE_ID: previous_facade,
        NDFL_OPENWEBUI_BASE_PIPE_ID: previous_base_override,
        publisher.LEGACY_NDFL_MODEL_ID: None,
        publisher.LEGACY_WORKSPACE_MODEL_ID: None,
        **retired_models,
    }
    current_by_id = {
        **copy.deepcopy(previous_by_id),
        NDFL_WORKSPACE_MODEL_STABLE_ID: desired_facade,
    }
    reads: dict[str, int] = {}
    deleted: list[str] = []
    restored: list[tuple[str, dict | None]] = []

    class _Session:
        def __init__(self) -> None:
            self.headers: dict[str, str] = {}

    def fake_get_model(_session, _base_url, stable_id):
        reads[stable_id] = reads.get(stable_id, 0) + 1
        source = previous_by_id if reads[stable_id] == 1 else current_by_id
        return copy.deepcopy(source[stable_id])

    def fake_publish_model(_session, _base_url, *, desired, previous):
        assert desired["id"] == NDFL_WORKSPACE_MODEL_STABLE_ID
        current_by_id[desired["id"]] = copy.deepcopy(desired)
        return "updated"

    def fake_delete_model(_session, _base_url, *, stable_id):
        assert stable_id == NDFL_OPENWEBUI_BASE_PIPE_ID
        current_by_id[stable_id] = None
        deleted.append(stable_id)
        return "deleted"

    def fake_restore_model(
        _session,
        _base_url,
        *,
        stable_id,
        previous,
    ) -> None:
        restored.append((stable_id, previous))
        current_by_id[stable_id] = copy.deepcopy(previous)

    monkeypatch.setattr(publisher.requests, "Session", _Session)
    monkeypatch.setattr(publisher, "_read_env", lambda _path: {})
    monkeypatch.setattr(publisher, "_base_url", lambda _env: "https://invalid")
    monkeypatch.setattr(publisher, "_signin", lambda *_args: "token")
    monkeypatch.setattr(publisher, "_get_model", fake_get_model)
    monkeypatch.setattr(
        publisher,
        "_get_function",
        lambda *_args: {
            "id": NDFL_OPENWEBUI_BASE_PIPE_ID,
            "type": "pipe",
            "is_active": True,
            "is_global": False,
        },
    )
    monkeypatch.setattr(publisher, "_publish_model", fake_publish_model)
    monkeypatch.setattr(publisher, "_delete_model", fake_delete_model)
    monkeypatch.setattr(publisher, "_restore_model", fake_restore_model)
    monkeypatch.setattr(publisher, "_get_visible_models", lambda *_args: [])
    monkeypatch.setattr(sys, "argv", ["publisher", "--publish"])

    with pytest.raises(
        publisher.NdflWorkspacePublishError,
        match="postcondition_failed:rollback_errors=none",
    ):
        publisher.main()

    assert deleted == [NDFL_OPENWEBUI_BASE_PIPE_ID]
    assert restored == [
        (NDFL_OPENWEBUI_BASE_PIPE_ID, previous_base_override),
        (NDFL_WORKSPACE_MODEL_STABLE_ID, previous_facade),
    ]
    assert current_by_id[NDFL_OPENWEBUI_BASE_PIPE_ID] == previous_base_override
    assert current_by_id[NDFL_WORKSPACE_MODEL_STABLE_ID] == previous_facade


def test_publisher_routes_by_id_and_does_not_mutate_runtime_or_meaning() -> None:
    source = (
        SCRIPT_ROOT / "live_publish_ndfl_workspace_model.py"
    ).read_text(encoding="utf-8")
    assert "/api/v1/models/model?id={stable_id}" in source
    assert "/api/v1/models/model/update" in source
    assert "/api/v1/models/create" in source
    assert "/api/v1/models/model/delete" in source
    assert "get_by_name" not in source
    assert "find_model_by_name" not in source
    assert '"provider_calls": 0' in source
    assert "FACTORY_REQUIRED" in source
    assert "FORBIDDEN" in source
