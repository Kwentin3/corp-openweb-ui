from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "openwebui_actions" / "goal391_mapping_lab_pipe.py"
BUNDLE = ROOT / "openwebui_actions" / "goal391_mapping_lab_pipe_bundled.py"


def _load_source_module():
    spec = importlib.util.spec_from_file_location("goal391_native_lab_pipe", SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _clear_broker_reports_modules() -> None:
    for name in list(sys.modules):
        if name == "broker_reports_gate1" or name.startswith("broker_reports_gate1."):
            del sys.modules[name]


def _load_bundle_module():
    _clear_broker_reports_modules()
    spec = importlib.util.spec_from_file_location("goal391_native_lab_bundle", BUNDLE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ordinary_user():
    return {"id": "ordinary-test-user", "role": "user"}


def test_native_lab_pipe_has_no_direct_storage_or_product_owners():
    source = SOURCE.read_text(encoding="utf-8")

    assert "import sqlite3" not in source
    assert "ArtifactStore" not in source
    assert "CanonicalStore" not in source
    assert "RightBank" not in source
    assert "Declaration" not in source
    assert "generate_chat_completion" in source
    assert "OrdinaryTradeMappingPromptResolverFactory" in source
    assert "OrdinaryTradeSemanticMappingFactory" in source
    assert "Gate2StructuredModelClientFactory" in source
    assert "__goal391_lab_case_loader__" in source


def test_auxiliary_task_is_terminal_and_never_resolves_user_or_case_loader():
    module = _load_source_module()
    pipe = module.Pipe()
    loader_calls = []

    def loader(**_kwargs):
        loader_calls.append(True)
        return []

    result = asyncio.run(
        pipe.pipe(
            {},
            __user__=_ordinary_user(),
            __request__=object(),
            __task__="title_generation",
            __goal391_lab_case_loader__=loader,
        )
    )

    receipt = json.loads(result)
    assert receipt["status"] == "BLOCKED"
    assert receipt["terminal_error"] == "goal391_lab_auxiliary_task_forbidden"
    assert receipt["corpus"]["provider_calls_started_total"] == 0
    assert loader_calls == []


def test_injected_request_and_selected_ordinary_user_are_required_before_prompt_or_cases():
    module = _load_source_module()
    pipe = module.Pipe()
    pipe.valves.ordinary_test_user_id = "ordinary-test-user"
    loader_calls = []

    def loader(**_kwargs):
        loader_calls.append(True)
        return []

    missing_request = json.loads(
        asyncio.run(
            pipe.pipe(
                {},
                __user__=_ordinary_user(),
                __goal391_lab_case_loader__=loader,
            )
        )
    )
    assert missing_request["terminal_error"] == "goal391_lab_request_required"

    wrong_user = json.loads(
        asyncio.run(
            pipe.pipe(
                {},
                __user__={"id": "ordinary-test-user", "role": "admin"},
                __request__=object(),
                __goal391_lab_case_loader__=loader,
            )
        )
    )
    assert wrong_user["terminal_error"] == "goal391_lab_access_denied"
    assert loader_calls == []


def test_pipe_accepts_normal_chat_body_but_refuses_lab_payloads_without_provider_work():
    module = _load_source_module()
    pipe = module.Pipe()
    pipe.valves.ordinary_test_user_id = "ordinary-test-user"

    body_input = json.loads(
        asyncio.run(pipe.pipe({"canonical": "untrusted"}, __user__=_ordinary_user(), __request__=object()))
    )
    no_loader = json.loads(
        asyncio.run(
            pipe.pipe(
                {"model": "goal391_mapping_lab", "messages": [{"role": "user", "content": "run"}]},
                __user__=_ordinary_user(),
                __request__=object(),
            )
        )
    )

    assert body_input["terminal_error"] == "goal391_lab_body_input_forbidden"
    assert no_loader["terminal_error"] == "goal391_lab_case_loader_unavailable"
    assert body_input["corpus"]["provider_calls_started_total"] == 0
    assert no_loader["corpus"]["provider_calls_started_total"] == 0


@pytest.mark.parametrize(
    "form_data",
    [
        {"chat_id": "forbidden"},
        {"parent_id": "forbidden"},
        {"message_id": "forbidden"},
        {"metadata": {"chat_id": "forbidden"}},
        {"metadata": {"parent_id": "forbidden"}},
    ],
)
def test_inner_completion_refuses_all_chat_identifiers(form_data):
    module = _load_source_module()

    with pytest.raises(module.Goal391MappingLabPipeError) as exc:
        module.Pipe._require_stateless_form(form_data)

    assert exc.value.code == "goal391_lab_chat_identifier_forbidden"


def test_preflight_rejects_wrong_exact_case_count_before_completion_boundary(monkeypatch):
    module = _load_source_module()
    pipe = module.Pipe()
    pipe.valves.ordinary_test_user_id = "ordinary-test-user"
    prompt_resolved = []

    def resolve_prompt(_user):
        prompt_resolved.append(True)
        return SimpleNamespace()

    monkeypatch.setattr(pipe, "_resolve_prompt", resolve_prompt)

    receipt = json.loads(
        asyncio.run(
            pipe.pipe(
                {},
                __user__=_ordinary_user(),
                __request__=object(),
                __goal391_lab_case_loader__=lambda **_kwargs: [],
            )
        )
    )

    assert prompt_resolved == [True]
    assert receipt["status"] == "BLOCKED"
    assert receipt["terminal_error"] == "goal391_lab_case_count_invalid"
    assert receipt["corpus"]["provider_calls_started_total"] == 0


def test_safe_receipt_excludes_canonical_prompt_and_model_content():
    module = _load_source_module()
    receipt = module.Pipe()._blocked_receipt("goal391_lab_access_denied")
    serialized = json.dumps(receipt, ensure_ascii=False, sort_keys=True)

    assert set(receipt) == {"schema_version", "status", "corpus", "constraints", "terminal_error"}
    assert "canonical_root" not in serialized
    assert "source_artifact_ref" not in serialized
    assert "prompt" not in serialized
    assert "content" not in serialized
    assert receipt["constraints"] == {
        "retries": 0,
        "best_of_n": False,
        "manual_output_repair": False,
        "chat_persistence": "forbidden",
        "artifact_store_mutation": False,
        "canonical_mutation": False,
        "right_bank_mutation": False,
        "xml_mutation": False,
    }


def test_unexpected_owner_error_is_reduced_to_one_value_free_terminal_code():
    module = _load_source_module()

    class PrivateProviderFailure(RuntimeError):
        pass

    assert (
        module.Pipe._safe_error_code(PrivateProviderFailure("private source/key/prompt"))
        == "goal391_lab_internal_failure"
    )


def test_generated_bundle_is_closed_world_and_contains_only_adapter_not_product_flow():
    maintained_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "broker_reports_gate1" or name.startswith("broker_reports_gate1.")
    }
    try:
        bundle = _load_bundle_module()
        source = BUNDLE.read_text(encoding="utf-8")
        assert bundle._BUNDLED_PACKAGE_VERSION == "goal391_native_mapping_lab_v1"
        assert "ordinary_trade_semantic_mapping" in bundle._BUNDLED_MODULES
        assert "ordinary_trade_mapping_prompt" in bundle._BUNDLED_MODULES
        assert "goal391_mapping_lab_pipe.py" in source
        assert "__goal391_lab_case_loader__" in source
        assert "import sqlite3" not in source.split("# Begin maintainable source adapter:", 1)[1]
        assert hasattr(bundle.Pipe(), "last_safe_receipt")
    finally:
        _clear_broker_reports_modules()
        sys.modules.update(maintained_modules)
