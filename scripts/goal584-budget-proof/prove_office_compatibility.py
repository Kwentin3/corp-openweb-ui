"""Finite Office compatibility assertions, awaiting isolated native wiring.

This module performs no provisioning, HTTP, Office execution or model/tool loop.
The existing NativeProof, WebUI/browser fixture, Session Tool Server and Office
service must collect the private arguments. Passing component assertions is not
native Office acceptance. Do not install this module in production.
"""
from __future__ import annotations

import copy
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from capture_webui_auth import responses_projection
from prove_native_budgets import ProofError, close_amount, protected_r, require

MODEL = "gpt-5.4-mini"
OUTPUT_NAME = "goal584-office.docx"
EXPORT_ARGUMENTS = {"output_name": OUTPUT_NAME, "source_message": "previous_assistant", "commands": []}
USER_REQUEST = "Export the complete previous answer to goal584-office.docx, render every page, and attach the native file."
SOURCE = "# GOAL584 Office compatibility\nBEGIN-G584-OFFICE\n" + (
    "\u041f\u0435\u0440\u0432\u044b\u0439 \u0430\u0431\u0437\u0430\u0446: \u0441\u0443\u043c\u043c\u0430 9 000 \u20bd; "
    "\u0441\u0440\u043e\u043a \u2014 5 \u0440\u0430\u0431\u043e\u0447\u0438\u0445 \u0434\u043d\u0435\u0439.\n\n"
    "| \u0423\u0441\u043b\u0443\u0433\u0430 | \u041a\u043e\u043b\u0438\u0447\u0435\u0441\u0442\u0432\u043e | \u0426\u0435\u043d\u0430 | \u0421\u0443\u043c\u043c\u0430 |\n"
    "|---|---:|---:|---:|\n| Alpha | 2 | 1500 | 3000 |\n| Beta | 3 | 2000 | 6000 |\n\n"
    "- \u0410\u0432\u0430\u043d\u0441: 50%.\n- \u041f\u043e\u0434\u043f\u0438\u0441\u044c: ____________________\nEND-G584-OFFICE")
SOURCE_SHA256 = "18ba1fbae3d19d00cb717ce3203b6045ab54456ebec2da3fdb33ef7edae0bd0a"
TABLE = (("\u0423\u0441\u043b\u0443\u0433\u0430", "\u041a\u043e\u043b\u0438\u0447\u0435\u0441\u0442\u0432\u043e", "\u0426\u0435\u043d\u0430", "\u0421\u0443\u043c\u043c\u0430"),
         ("Alpha", "2", "1500", "3000"), ("Beta", "3", "2000", "6000"))
PARAGRAPHS = ("GOAL584 Office compatibility", "BEGIN-G584-OFFICE", SOURCE.splitlines()[2],
              *(v for row in TABLE for v in row), "\u0410\u0432\u0430\u043d\u0441: 50%.",
              "\u041f\u043e\u0434\u043f\u0438\u0441\u044c: ____________________", "END-G584-OFFICE")
TARGETS = "gpt-5.4-mini,models/gemini-3.5-flash,models/gemini-3.6-flash,gpt-5.6-luna,models/gemini-3.1-flash-lite,models/gemini-3.5-flash-lite,gpt-6-luna,gpt-6-sol,claude-haiku-5-5,claude-sonnet-5,gpt-6.1-sol,deepseek-flash,gpt-6.1-terra"
VALVES = {"priority": 0, "target_model_ids": TARGETS, "no_reasoning_model_ids": "gpt-5.6-luna,gpt-6-sol",
          "terminal_transfer_tool_id": "terminal_file_transfer", "artifact_workflow_skill_id": "artifact-workflow",
          "default_terminal_id": "office-linux"}
WEBUI_IMAGE = "sha256:6cc2c633a09e325b31c03acf57a5c846e381577e98ab43a993c932c599044139"
OFFICE_IMAGE = "sha256:df3acf071d04215006950e53738f20065b9174ef49d5f1c18864f061f18d16c3"
OFFICE_BINARY_SHA256 = "e54d3c1d248372365f0634aac56d6f1918bd04d6e71afc792ad50e075f56cfe9"
WEBUI_MODULES = {
    "config.py": "2c9b6fb4cb448405cf821fc4f86b491b987c2fd198ee1cefd1316c913228ae0a",
    "utils/middleware.py": "d0c6eb1d111db4f977da98d14f2f0f668b828729f304469cebb9d11d8cf35201",
    "routers/openai.py": "0039f04db833b705f2e64b9ed168efdcd93bb07b699a96e5ebb898f75960a829",
    "utils/payload.py": "c4fa395b43f0cdfd1fa95461749dfa283f0ae9b780acffd53e86046eed018fdb",
    "routers/terminals.py": "b6feaaf3d5b23243d04e9c30ff0d78052697837b6c43d6f16fada29d1930d73c",
    "utils/tools.py": "7f1ab18422adbd1443bbb47bcc9f25433503cd0e91d7f0ee7d212bf1e4022f1b"}
OFFICE_MODULES = {
    "app.py": "67f90e6a3a237143826b461ec63ad5e8445e27db7c44c151f8c6afd7e0ec20db",
    "openwebui_client.py": "80c4d45f8210d94a21c6ac95b32cd7d110d3f500b822d739d34a479a9801e7cf",
    "rendering.py": "e6a54796d53b4d003f1c97bfc09797d2f1adc5fa763baf623b532f5c2d27e007",
    "config.py": "69e8c8e5f5078701c0de64b1667ef72c0ceac43d10c6baf57c4f6c86f04f7b11",
    "officecli.py": "d946ce1ef90df5d56d3e5b922fe418d0d597be22b96ff81835c158a55b12f6dd"}
USAGE = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
         "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}}


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                             allow_nan=False).encode("utf8")).hexdigest()


def built_images(receipt, expected_revision, running):
    """Pure join of existing builder output and independent same-job readback.

    The source-bound host must supply clean checkout GITHUB_SHA independently,
    the successful builder's actual receipt, Docker Config.Image/Image/platform,
    in-container modules/version/binary and frontend receipt/manifest hash plus
    actual verify_frontend_artifact.py stdout. It owns topology/mount and source
    binding. These arguments are not external user receipts or crypto-attestation;
    checksums/self-consistent JSON alone cannot establish their origin.
    """
    require(isinstance(receipt, dict) and isinstance(running, dict) and set(running) == {"webui", "office"}
            and isinstance(expected_revision, str) and re.fullmatch("[0-9a-f]{40}", expected_revision), "office_build_binding")
    inputs = receipt.get("inputs"); identity = receipt.get("build_identity")
    require(type(receipt.get("schema")) is int and receipt["schema"] == 1 and receipt.get("native_office_accepted") is False
            and receipt.get("source_commit") == expected_revision and isinstance(inputs, dict)
            and inputs.get("source_commit") == expected_revision, "office_build_revision")
    # Representation of build-inputs.json emitted by the existing builder.write.
    require(isinstance(identity, str) and re.fullmatch("[0-9a-f]{64}", identity)
            and all(isinstance(inputs.get(k), str) and re.fullmatch("[0-9a-f]{64}", inputs[k])
                for k in ("source_archive_sha256", "git_inputs_sha256", "frontend_sources_sha256"))
            and sha256((json.dumps(inputs, indent=2, sort_keys=True) + "\n").encode()).hexdigest() == identity,
            "office_build_identity")
    images = receipt.get("images")
    require(isinstance(images, dict) and set(images) == {"frontend", "webui", "office"}
            and all(isinstance(images[n], dict) and isinstance(images[n].get("id"), str)
                and re.fullmatch("sha256:[0-9a-f]{64}", images[n]["id"]) for n in images), "office_build_images")
    for name in ("webui", "office"):
        live, built = running[name], receipt.get(name)
        require(isinstance(live, dict) and isinstance(built, dict)
                and live.get("image_ref") == live.get("image_id") == images[name]["id"]
                and live.get("os") == "linux" and live.get("architecture") == "amd64"
                and isinstance(built.get("modules"), dict) and live.get("modules") == built["modules"], "office_build_live_image")
    webui, office = running["webui"], running["office"]
    require(set(webui["modules"]) == set(WEBUI_MODULES) | {"utils/misc.py", "routers/files.py", "storage/provider.py"}
            and all(isinstance(v, str) and re.fullmatch("[0-9a-f]{64}", v) for v in webui["modules"].values())
            and isinstance(office.get("binary_sha256"), str) and re.fullmatch("[0-9a-f]{64}", office["binary_sha256"])
            and office.get("binary_sha256") == receipt["office"].get("binary_sha256")
            and office.get("version") == receipt["office"].get("version") == "1.0.152", "office_build_sources")
    require(webui.get("build_hash") == webui.get("version") == receipt["webui"].get("build_hash")
            == receipt["webui"].get("version") == identity, "office_build_frontend_identity")
    frontend = webui.get("frontend_receipt")
    require(isinstance(frontend, dict) and frontend.get("build_identity") == frontend.get("input_receipt_sha256") == identity
            and frontend.get("upstream_commit") == inputs.get("upstream_commit") == "6a18585ff4c2e5f6805f682222cfbc46dc669ef8"
            and frontend.get("source_archive_sha256") == inputs.get("source_archive_sha256")
            and frontend.get("frontend_sources_sha256") == inputs.get("frontend_sources_sha256")
            and isinstance(receipt.get("frontend_manifest_sha256"), str)
            and re.fullmatch("[0-9a-f]{64}", receipt["frontend_manifest_sha256"])
            and webui.get("frontend_manifest_sha256") == frontend.get("build_files_manifest_sha256") == receipt["frontend_manifest_sha256"]
            and type(frontend.get("build_files")) is int and frontend["build_files"] > 0
            and isinstance(webui.get("frontend_result"), dict) and type(webui["frontend_result"].get("frontend_files")) is int
            and webui.get("frontend_result") == {"frontend_files": frontend["build_files"],
                "native_build_hash": identity, "complete_manifest": "verified"}, "office_build_frontend")
    return images["webui"]["id"], images["office"]["id"]


def _verify_service_tasks(baseline, current, source):
    """Join independent native API observations; the trusted host owns origin.

    baseline/current contain complete GET /api/v1/tasks/config and
    WebUI.model('gpt-6-luna') results, plus that target's entry from a fresh
    ordinary actor /api/models?refresh=true catalog. current additionally has
    GET /api/v1/functions/id/employee_budget_service, its /valves and
    WebUI.model('employee_budget_service'). source is independently read from
    the trusted same-job service_pipe.py, never from the observed Function.
    No timestamp, checksum or jointly invented JSON authenticates these inputs.
    """
    require(isinstance(baseline, dict) and isinstance(current, dict)
            and set(baseline) == {"task_config", "target_model", "target_catalog"}
            and set(current) == set(baseline) | {"function", "valves", "workspace_model"}
            and all(isinstance(v, dict) for v in [*baseline.values(), *current.values()])
            and isinstance(source, str) and 0 < len(source.encode("utf8")) <= 128 * 1024,
            "office_service_readback")
    before, after = baseline["task_config"], current["task_config"]
    selectors = ("TASK_MODEL", "TASK_MODEL_EXTERNAL")
    params = before.get("TASK_MODEL_PARAMS")
    require(all(before.get(k) == "gpt-6-luna" for k in selectors)
            and isinstance(params, dict) and params.get("reasoning_effort") is None
            and isinstance(params.get("custom_params"), dict)
            and isinstance(params["custom_params"].get("reasoning"), dict)
            and params["custom_params"]["reasoning"].get("effort") == "none"
            and after == {**before, **dict.fromkeys(selectors, "employee_budget_service")},
            "office_service_task_config")
    target, catalog = baseline["target_model"], baseline["target_catalog"]
    require(target.get("id") == "gpt-6-luna" and target.get("write_access") is True
            and target.get("is_active") is True and isinstance(target.get("params"), dict)
            and isinstance(target.get("user_id"), str) and bool(target["user_id"])
            and catalog.get("id") == "gpt-6-luna" and catalog.get("owned_by") == "openai"
            and not catalog.get("pipe") and not catalog.get("arena")
            and current["target_model"] == target and current["target_catalog"] == catalog,
            "office_service_target")
    function, workspace = current["function"], current["workspace_model"]
    require(function.get("id") == "employee_budget_service" and function.get("type") == "pipe"
            and function.get("user_id") == target["user_id"] and function.get("is_active") is True
            and function.get("is_global") is False and isinstance(function.get("content"), str)
            and function["content"].replace("\r\n", "\n") == source.replace("\r\n", "\n")
            and current["valves"] == {"target_model_id": "gpt-6-luna"}, "office_service_function")
    meta = workspace.get("meta")
    require(workspace.get("id") == "employee_budget_service" and workspace.get("user_id") == target["user_id"]
            and workspace.get("write_access") is True and workspace.get("is_active") is True
            and "base_model_id" in workspace and workspace["base_model_id"] is None
            and workspace.get("params") == {} and isinstance(meta, dict)
            and meta.get("capabilities") == {"builtin_tools": False}
            and all(meta.get(k) == [] for k in ("filterIds", "toolIds", "skillIds"))
            and all(v is None for k, v in meta.items() if k not in
                {"capabilities", "filterIds", "toolIds", "skillIds"}), "office_service_workspace")


def verify_profile(profile, *, build_receipt=None, expected_revision=None, running=None,
                   service_tasks=None, service_baseline=None, service_source=None):
    """Retained default; service selectors require all independent opt-in inputs."""
    images = (WEBUI_IMAGE, OFFICE_IMAGE)
    if any(value is not None for value in (build_receipt, expected_revision, running)):
        images = built_images(build_receipt, expected_revision, running)
        require(profile["webui_modules"] == {k: running["webui"]["modules"][k] for k in WEBUI_MODULES}
                and profile["office_modules"] == running["office"]["modules"]
                and profile["office_binary_sha256"] == running["office"]["binary_sha256"], "office_build_profile_readback")
    require(profile["webui_image"] == images[0] and profile["office_image"] == images[1]
            and profile["webui_modules"] == WEBUI_MODULES and profile["office_modules"] == OFFICE_MODULES
            and profile["office_binary_sha256"] == OFFICE_BINARY_SHA256, "office_profile_sources")
    require(profile["office_valves"] == VALVES and profile["model"] == MODEL
            and profile["active"] is True and profile["function_calling"] == "native"
            and type(profile["connection_index"]) is int and profile["connection_index"] == 0
            and profile["api_type"] == "responses", "office_profile_route")
    require(profile["session_tool_server"] == {"id": "officecli", "enabled": True, "auth_type": "session",
        "access_grants": [{"principal_type": "user", "principal_id": "*", "permission": "read"}],
        "custom_header_names": ["X-OpenWebUI-Chat-Id", "X-OpenWebUI-Message-Id"],
        "function_name_filter_list": ""}, "office_profile_session")
    task_model = "gpt-6-luna"
    if any(value is not None for value in (service_tasks, service_baseline, service_source)):
        _verify_service_tasks(service_baseline, service_tasks, service_source)
        task_model = "employee_budget_service"
    require(profile["reasoning_settings"] == {"context_compaction_enabled": False,
        "responses_stateful_env": "false", "task_model_default": task_model, "task_model_external": task_model,
        "task_model_reasoning_effort": None, "task_custom_reasoning_effort": "none"}, "office_profile_reasoning")


def verify_schemas(tools, native_specs):
    """native_specs must come from actual served OpenAPI + native get_tools owners.

    Do not replace discovery with hand-built export/render specifications. The
    full context comparison below preserves every other exposed native tool.
    """
    require(isinstance(native_specs, list) and len(native_specs) > 2, "office_native_discovery")
    require(isinstance(tools, list) and len({v.get("name") for v in tools}) == len(tools), "office_tool_names")
    actual = {v.get("name"): v for v in tools}
    for spec in native_specs:
        expected = {"type": "function", **copy.deepcopy(spec), "strict": spec.get("strict", False)}
        # Native OpenAPI combines required fields via set union. Only this
        # schema/discovery comparison ignores order of that unordered keyword.
        found = copy.deepcopy(actual.get(spec.get("name")))
        for value in (expected, found):
            if isinstance(value, dict) and isinstance(value.get("parameters"), dict):
                required = value["parameters"].get("required")
                if isinstance(required, list):
                    value["parameters"]["required"] = sorted(required)
        require(found == expected, "office_schema_incomplete")
    require({"export_answer_to_word", "render_office_file"} <= set(actual), "office_schema_operations")


def verify_budget_boundary(before, after, *, decode_call, secret, actor):
    """Use existing authenticated provenance owner immediately while token is live."""
    left, right = copy.deepcopy(before), copy.deepcopy(after)
    original, carrier = left.pop("litellm_metadata", None), right.pop("litellm_metadata", None)
    require(left == right and isinstance(carrier, dict), "office_budget_context")
    expected = dict(original or {})
    expected.pop("spend_logs_metadata", None)
    token = carrier.get("owui_budget_provenance")
    expected["owui_budget_provenance"] = token
    require(carrier == expected and isinstance(token, str) and token, "office_budget_metadata")
    return decode_call(token, secret, user_id=actor, model=MODEL)


def _nodes(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _nodes(item)
    elif isinstance(value, list):
        for item in value:
            yield from _nodes(item)


def verify_calls(calls, *, actor, key_hash, chat_id, answer_id, wire_model, native_specs,
                 exported, png, native_responses_payload):
    """Component cost Filter pre/post bodies and exact native serialization.

    These component-only inputs must be collected at the actual Filter.request
    seam. verify_budget_boundary separately checks its live signed token. Never
    reconstruct before_budget/after_budget from auth or provider wire evidence.
    All shared auth/provider assertions remain mandatory in verify_wire_calls.
    """
    require(isinstance(calls, list) and len(calls) == 3, "office_physical_calls")
    for call in calls:
        wire = responses_projection(call["wire_before_auth"])
        converted = responses_projection(native_responses_payload(copy.deepcopy(call["after_budget"])))
        require(wire == converted and wire.get("model") == MODEL, "office_native_serialization")
        before, after = copy.deepcopy(call["before_budget"]), copy.deepcopy(call["after_budget"])
        before.pop("litellm_metadata", None); after.pop("litellm_metadata", None)
        require(before == after and before.get("model") == MODEL, "office_budget_context")
    return verify_wire_calls(calls, actor=actor, key_hash=key_hash, chat_id=chat_id, answer_id=answer_id,
        wire_model=wire_model, native_specs=native_specs, exported=exported, png=png,
        native_responses_payload=native_responses_payload)


def verify_wire_calls(calls, *, actor, key_hash, chat_id, answer_id, wire_model, native_specs,
                      exported, png, native_responses_payload):
    """Live auth/provider evidence: exactly export, render, final physical calls.

    Supply complete safe pre/post-auth wire projections, actual served/native
    schemas and provider receipts. The source-bound auth observer owns verified
    scope origin; these assertions reconcile its payer/root IDs and physical
    calls. This proves no live cost Filter pre/post body invariance. The pinned
    native converter is used only for provider reasoning continuation semantics.
    """
    require(isinstance(calls, list) and len(calls) == 3, "office_physical_calls")
    scopes, provider_ids = {}, []
    for index, call in enumerate(calls):
        require(isinstance(call, dict) and {"wire_before_auth", "wire_after_auth", "auth_user_id", "auth_key_hash",
            "attestation_present_before", "provenance_removed_after", "route", "verified_cost_scope", "provider"} <= set(call)
            and all(isinstance(call[k], dict) for k in ("wire_before_auth", "wire_after_auth", "verified_cost_scope", "provider")),
            "office_wire_packet")
        wire = responses_projection(call["wire_before_auth"])
        require(wire == responses_projection(call["wire_after_auth"]), "office_auth_context")
        require(wire.get("model") == MODEL and isinstance(wire.get("input"), list)
                and all(isinstance(v, dict) for v in wire["input"]), "office_native_serialization")
        require(call["auth_user_id"] == actor and call["auth_key_hash"] == key_hash
                and call["attestation_present_before"] is True and call["provenance_removed_after"] is True
                and call["route"] in ("/responses", "/v1/responses", "/openai/v1/responses")
                and not call.get("auth_failure"), "office_native_auth")
        require(wire.get("store") is False and not wire.get("previous_response_id")
                and wire.get("background", False) is False, "office_native_stateless_profile")
        verify_schemas(wire.get("tools"), native_specs)
        if index:
            original = responses_projection(calls[0]["wire_before_auth"])
            require({k: v for k, v in wire.items() if k != "input"} ==
                    {k: v for k, v in original.items() if k != "input"}, "office_continuation_parameters")
            previous = calls[index - 1]["wire_before_auth"]["input"]
            require(wire["input"][:len(previous)] == previous, "office_continuation_history")
        require(any(v.get("role") == "assistant" and any(n.get("text") == SOURCE for n in _nodes(v))
                    for v in wire.get("input", []))
                and any(v.get("role") == "user" and any(n.get("text") == USER_REQUEST for n in _nodes(v))
                        for v in wire.get("input", [])), "office_source_context")
        require(isinstance(wire.get("instructions"), str) and bool(wire["instructions"]), "office_system_context")
        p = call["provider"]
        require({"id", "route", "body", "usage", "response", "lifecycle"} <= set(p)
                and isinstance(p["id"], str) and bool(p["id"]) and isinstance(p["response"], dict)
                and {"id", "model", "status", "usage", "output"} <= set(p["response"])
                and isinstance(p["response"]["output"], list)
                and all(isinstance(v, dict) for v in p["response"]["output"]), "office_provider_context")
        require(p["body"] == {**copy.deepcopy(wire), "model": wire_model}
                and p["route"] == "/v1/responses" and p["usage"] == USAGE
                and p["response"]["id"] == p["id"] and p["response"]["model"] == wire_model
                and p["response"]["status"] == "completed" and p["response"]["usage"] == USAGE
                and p["lifecycle"] == {"terminal": True, "outcome": "completed"}, "office_provider_context")
        scope = call["verified_cost_scope"]
        require(scope.get("category") == "personal" and scope.get("model") == MODEL and scope.get("user_id") == actor
                and scope.get("chat_id") == scope.get("root_chat_id") == chat_id
                and scope.get("answer_id") == scope.get("root_answer_id") == answer_id
                and isinstance(scope.get("call_id"), str) and bool(scope["call_id"]), "office_call_scope")
        require(scope["call_id"] not in scopes and p["id"] not in provider_ids, "office_call_identity")
        scopes[scope["call_id"]] = scope; provider_ids.append(p["id"])
        output = p["response"]["output"]
        tool_calls = [v for v in output if v.get("type") == "function_call"]
        if index < 2:
            name = ("export_answer_to_word", "render_office_file")[index]
            arguments = EXPORT_ARGUMENTS if index == 0 else {"file_id": exported["result_file_id"], "format": "docx", "grid": 2}
            require(len(tool_calls) == 1 and tool_calls[0]["name"] == name
                    and json.loads(tool_calls[0]["arguments"]) == arguments, "office_requested_tool")
            following = calls[index + 1]["wire_before_auth"]["input"]
            pair = [v for v in following if v.get("call_id") == tool_calls[0]["call_id"]]
            reasoning = [v for v in output if v.get("type") == "reasoning"]
            expected_reasoning = (native_responses_payload({"messages": [{"role": "assistant", "output": reasoning}]})["input"]
                                  if reasoning else [])
            continuation = following[len(wire["input"]):]
            require(continuation[:len(expected_reasoning)] == expected_reasoning,
                    "office_continuation_reasoning")
            require(len(pair) == 2 and pair[0].get("type") == "function_call"
                    and all(pair[0].get(k) == tool_calls[0][k] for k in ("call_id", "name", "arguments"))
                    and pair[1].get("type") == "function_call_output", "office_tool_pair")
            if index == 0:
                result = pair[1]["output"]
                require(isinstance(result, str) and json.loads(result) == exported, "office_export_result_context")
            else:
                import base64
                result = pair[1]["output"]
                require(isinstance(result, list) and len(result) == 2
                        and result[0] == {"type": "input_text", "text": "render_office_file: Image file read successfully."}
                        and result[1] == {"type": "input_image", "image_url": "data:image/png;base64," + base64.b64encode(png).decode("ascii")},
                        "office_render_image_context")
            require(continuation == expected_reasoning + pair, "office_continuation_items")
        else:
            require(not tool_calls and any(v.get("type") == "message" and any(
                n.get("type") == "output_text" and exported["result_file_id"] in n.get("text", "")
                for n in _nodes(v)) for v in output), "office_final_attachment_context")
    return {p: c["verified_cost_scope"] for p, c in zip(provider_ids, calls)}


def verify_artifacts(*, source_message_id, exported, native_file_id, browser_file_id,
                     native_path, browser_path, png):
    # Existing Office owners own text and PNG validity; these are fixture-specific
    # extra assertions, not another Office writer/renderer or native Files store.
    from officecli_openapi_proof.docx_text import WORD, body_paragraphs, require_preserved_text
    from officecli_openapi_proof.rendering import checked_png
    native, downloaded = Path(native_path).read_bytes(), Path(browser_path).read_bytes()
    require(native and native == downloaded, "office_native_download_bytes")
    require(re.fullmatch(r"[A-Za-z0-9-]{1,128}", native_file_id or "") is not None
            and exported["result_file_id"] == exported["result_file"]["id"] == native_file_id == browser_file_id,
            "office_native_file_identity")
    require(exported["source_message_id"] == source_message_id and exported["source_content_sha256"] == SOURCE_SHA256
            and exported["source_text_preserved"] is True and exported["result_sha256"] == sha256(native).hexdigest()
            and exported["bounded_processes_completed"] is True and exported["auto_resident_disabled"] is True,
            "office_source_artifact")
    paragraphs = body_paragraphs(Path(native_path))
    require_preserved_text(PARAGRAPHS, paragraphs)
    require(paragraphs == PARAGRAPHS, "office_unexpected_document_text")
    with ZipFile(native_path) as package:
        body = ET.fromstring(package.read("word/document.xml")).find(WORD + "body")
    tables = body.findall(WORD + "tbl")
    require(len(tables) == 1, "office_table_count")
    cells = tuple(tuple("".join(n.text or "" for n in cell.iter(WORD + "t"))
                        for cell in row.findall(WORD + "tc")) for row in tables[0].findall(WORD + "tr"))
    require(cells == TABLE, "office_table_cells")
    require(checked_png(png) == png, "office_render_png")
    return {"docx_sha256": sha256(native).hexdigest(), "png_sha256": sha256(png).hexdigest()}


def verify_finance(before, after, *, calls_by_provider, actor, key_hash, chat_id, answer_id,
                   wire_model, deployment_id, validate_scope, validate_rates, decode_response_id):
    """Readback assertions only. SDK decoder/rate validator are existing owners.

    The isolated collector must pass ALL raw pages from NativeProof.logs, not
    positive-cost rows, and the full retained original payer state. No pricing
    calculation, new ledger, scheduler or budget allowance is implemented here.
    """
    require(before["old_payers"] and before["old_payers"] == after["old_payers"], "office_old_finance_changed")
    require(before["user"].get("user_id") == before["key"].get("user_id") == actor
            and before["key"].get("models") == [MODEL], "office_financial_owner")
    require(protected_r(before["user"], before["key"]) == protected_r(after["user"], after["key"]), "office_caps_changed")
    def keyed(rows):
        require(isinstance(rows, list) and all(isinstance(v, dict) and isinstance(v.get("request_id"), str)
                and v["request_id"] for v in rows), "office_raw_rows")
        result = {v["request_id"]: v for v in rows}
        require(len(result) == len(rows), "office_duplicate_row")
        return result
    old, new = keyed(before["rows"]), keyed(after["rows"])
    require(all(new.get(k) == v for k, v in old.items()), "office_old_row_changed")
    added = [v for k, v in new.items() if k not in old]
    require(len(added) == len(calls_by_provider) == 3, "office_row_count")
    observed = set()
    for row in added:
        metadata = json.loads(row["metadata"]) if isinstance(row.get("metadata"), str) else row["metadata"]
        spend = metadata["spend_logs_metadata"]
        scope = validate_scope(spend["owui_budget"])
        decoded = decode_response_id(row["request_id"])
        provider = decoded["response_id"]
        require(decoded["custom_llm_provider"] == "openai" and decoded["model_id"] == deployment_id
                and provider in calls_by_provider and provider not in observed and scope == calls_by_provider[provider],
                "office_row_dispatch_binding")
        observed.add(provider)
        require(scope["user_id"] == row.get("user") == actor and scope["model"] == row.get("model_group") == MODEL
                and scope["chat_id"] == scope["root_chat_id"] == row.get("session_id") == chat_id
                and scope["answer_id"] == scope["root_answer_id"] == answer_id and row.get("api_key") == key_hash
                and row.get("model") in (MODEL, wire_model, "openai/" + wire_model)
                and row.get("model_id") == deployment_id and row.get("status") == "success"
                and [row.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens")] == [10, 5, 15]
                and all(type(row.get(k)) is int for k in ("prompt_tokens", "completion_tokens", "total_tokens"))
                and close_amount(row.get("spend"), Decimal(".20")), "office_row_identity_usage_cost")
        rates = validate_rates(spend["owui_billed_token_rates"])["rates"]
        require(Decimal(str(rates["input_cost_per_token"])) == Decimal(".01")
                and Decimal(str(rates["output_cost_per_token"])) == Decimal(".02"), "office_row_rates")
    for owner in ("user", "key"):
        require(close_amount(Decimal(str(after[owner]["spend"])) - Decimal(str(before[owner]["spend"])),
                             Decimal(".60")), "office_native_spend_delta")
    return {"physical_calls": 3, "new_raw_rows": 3, "native_spend_delta_usd": ".60"}


def verify_service_finance(before, after, *, actor, payer, key_hash, chat_id, provider_id, verified_scope,
                           wire_model, deployment_id, descriptor, validate_scope, validate_rates, decode_response_id):
    """One native follow-up Responses row; fixed fixture totals, no price math.

    The collector supplies all raw pages and the actual auth/provider join.
    Descriptor expectations come from the source-bound prepared native config.
    This separate service payer must not be included among unchanged old payers.
    """
    require(actor != payer and before["user"].get("user_id") == before["key"].get("user_id") == payer
            and before["key"].get("models") == ["gpt-6-luna"], "office_service_owner")
    require(protected_r(before["user"], before["key"]) == protected_r(after["user"], after["key"]),
            "office_service_caps_changed")
    def keyed(rows):
        require(isinstance(rows, list) and all(isinstance(v, dict) and isinstance(v.get("request_id"), str)
                and v["request_id"] for v in rows), "office_service_raw_rows")
        result = {v["request_id"]: v for v in rows}
        require(len(result) == len(rows), "office_service_duplicate_row")
        return result
    old, new = keyed(before["rows"]), keyed(after["rows"])
    require(all(new.get(k) == v for k, v in old.items()), "office_service_old_row_changed")
    added = [v for k, v in new.items() if k not in old]
    require(len(added) == 1, "office_service_row_count")
    row = added[0]
    metadata = json.loads(row["metadata"]) if isinstance(row.get("metadata"), str) else row["metadata"]
    spend = metadata["spend_logs_metadata"]
    scope = validate_scope(spend["owui_budget"])
    decoded = decode_response_id(row["request_id"])
    require(scope == verified_scope and scope["user_id"] == payer and scope["actor_id"] == actor
            and scope["chat_id"] == chat_id and scope["model"] == "gpt-6-luna"
            and scope["task"] == "follow_up_generation" and scope["category"] == "service"
            and decoded["custom_llm_provider"] == "openai" and decoded["model_id"] == deployment_id
            and decoded["response_id"] == provider_id, "office_service_dispatch_binding")
    require(row.get("user") == payer and row.get("api_key") == key_hash
            and row.get("model_group") == "gpt-6-luna" and row.get("model_id") == deployment_id
            and row.get("model") in ("gpt-6-luna", wire_model, "openai/" + wire_model)
            and row.get("session_id") == "owui-service:" + chat_id and row.get("status") == "success"
            and all(type(row.get(k)) is int for k in ("prompt_tokens", "completion_tokens", "total_tokens"))
            and [row.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens")] == [10, 5, 15]
            and close_amount(row.get("spend"), Decimal(".20")), "office_service_row_identity_usage_cost")
    rates = validate_rates(spend["owui_billed_token_rates"])
    require(rates["rates"]["input_cost_per_token"] is not None and rates["rates"]["output_cost_per_token"] is not None
            and Decimal(str(rates["rates"]["input_cost_per_token"])) == Decimal(".01")
            and Decimal(str(rates["rates"]["output_cost_per_token"])) == Decimal(".02"), "office_service_rates")
    require(descriptor.get("deployment_id") == deployment_id
            and spend.get("owui_tariff_descriptor") == {"schema": 1, "availability": "available", "descriptor": descriptor},
            "office_service_tariff_source")
    for owner in ("user", "key"):
        require(close_amount(Decimal(str(after[owner]["spend"])) - Decimal(str(before[owner]["spend"])), Decimal(".20")),
                "office_service_native_spend_delta")
    return {"physical_calls": 1, "new_raw_rows": 1, "native_spend_delta_usd": ".20"}


def safe_component_result(check):
    """Never export raw contexts, JWTs, IDs, private output or exception prose."""
    try:
        check()
        return {"schema": 1, "component_assertions_passed": True, "native_office_accepted": False,
                "reasoning_continuity_qualified": False}
    except Exception as error:
        code = str(error) if isinstance(error, ProofError) and re.fullmatch(r"office_[a-z_]+", str(error)) else "office_component_failure"
        return {"schema": 1, "component_assertions_passed": False, "native_office_accepted": False,
                "failure_code": code}
