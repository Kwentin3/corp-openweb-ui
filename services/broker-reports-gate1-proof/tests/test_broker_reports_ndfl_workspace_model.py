from __future__ import annotations

import copy
from pathlib import Path
import sys


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
        "dictionary_semantic_version": "1.0.0",
        "role_pack_id": "broker-reports-financial-roles",
        "role_pack_semantic_version": "1.0.0",
        "skill_id": "broker-reports-financial-labels",
        "tool_id": "broker_reports_financial_label_dictionary",
        "tool_method": "load_financial_label_dictionary",
        "prompt_id": None,
        "knowledge_ids": [],
    }


def test_ndfl_workspace_model_reuses_existing_pipe_without_knowledge_or_tools() -> None:
    desired = publisher.desired_ndfl_model(
        previous=None,
        legacy=_legacy_model(),
    )
    check = publisher.evaluate_ndfl_model(desired)
    assert check["routing_passed"] is True
    assert check["display_name_match"] is True
    assert check["managed_tags_match"] is True
    assert desired["base_model_id"] == NDFL_OPENWEBUI_BASE_PIPE_ID
    assert desired["meta"]["knowledge"] == []
    assert desired["meta"]["toolIds"] == []
    assert desired["meta"]["skillIds"] == []


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


def test_technical_pipe_overrides_keep_only_required_runtime_base_active() -> None:
    for pipe_id in publisher.TECHNICAL_PIPE_IDS:
        desired = publisher.desired_hidden_pipe_model(
            pipe_id,
            previous=None,
        )
        check = publisher.evaluate_hidden_pipe_model(desired, pipe_id)
        assert all(check.values())
        assert desired["base_model_id"] is None
        assert desired["is_active"] is (
            pipe_id == NDFL_OPENWEBUI_BASE_PIPE_ID
        )

    existing_acl_override = {
        "id": NDFL_OPENWEBUI_BASE_PIPE_ID,
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
        NDFL_OPENWEBUI_BASE_PIPE_ID,
    )


def test_visible_route_acceptance_requires_ndfl_and_its_internal_base() -> None:
    assert publisher.evaluate_visible_routes(
        [
            {"id": NDFL_WORKSPACE_MODEL_STABLE_ID},
            {"id": NDFL_OPENWEBUI_BASE_PIPE_ID},
            {"id": "unrelated-model"},
        ]
    ) == {
        "visible_product_route_ids": [NDFL_WORKSPACE_MODEL_STABLE_ID],
        "visible_internal_runtime_base_ids": [NDFL_OPENWEBUI_BASE_PIPE_ID],
        "user_facing_ndfl_models": 1,
        "legacy_or_competing_routes_visible": [],
        "passed": True,
    }
    assert publisher.evaluate_visible_routes(
        [{"id": NDFL_WORKSPACE_MODEL_STABLE_ID}]
    )["passed"] is False


def test_publisher_routes_by_id_and_does_not_mutate_runtime_or_meaning() -> None:
    source = (
        SCRIPT_ROOT / "live_publish_ndfl_workspace_model.py"
    ).read_text(encoding="utf-8")
    assert "/api/v1/models/model?id={stable_id}" in source
    assert "/api/v1/models/model/update" in source
    assert "/api/v1/models/create" in source
    assert "get_by_name" not in source
    assert "find_model_by_name" not in source
    assert '"provider_calls": 0' in source
    assert "FACTORY_REQUIRED" in source
    assert "FORBIDDEN" in source
