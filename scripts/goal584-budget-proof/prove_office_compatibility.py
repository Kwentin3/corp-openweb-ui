"""Finite Office compatibility assertions, awaiting isolated native wiring.

This module performs no provisioning, HTTP, Office execution or model/tool loop.
The existing NativeProof, WebUI/browser fixture, Session Tool Server and Office
service must collect the private arguments. Passing component assertions is not
native Office acceptance. Do not install this module in production.
"""
from __future__ import annotations

import ast
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
CONTINUATION_REQUEST = "Keep the attached file and report its native file ID without calling tools."
SAVED_HISTORY_ATOMS = ("native_saved_join_match", "native_saved_has_eight_items",
                       "saved_reasoning_matches_provider", "native_reasoning_matches_provider",
                       "provider_has_three_reasoning_items")
SOURCE = "# GOAL584 Office compatibility\nBEGIN-G584-OFFICE\n" + (
    "\u041f\u0435\u0440\u0432\u044b\u0439 \u0430\u0431\u0437\u0430\u0446: \u0441\u0443\u043c\u043c\u0430 9 000 \u20bd; "
    "\u0441\u0440\u043e\u043a \u2014 5 \u0440\u0430\u0431\u043e\u0447\u0438\u0445 \u0434\u043d\u0435\u0439.\n\n"
    "| \u0423\u0441\u043b\u0443\u0433\u0430 | \u041a\u043e\u043b\u0438\u0447\u0435\u0441\u0442\u0432\u043e | \u0426\u0435\u043d\u0430 | \u0421\u0443\u043c\u043c\u0430 |\n"
    "|---|---:|---:|---:|\n| Alpha | 2 | 1500 | 3000 |\n| Beta | 3 | 2000 | 6000 |\n\n"
    "- \u0410\u0432\u0430\u043d\u0441: 50%.\n- \u041f\u043e\u0434\u043f\u0438\u0441\u044c: ____________________\nEND-G584-OFFICE")
SOURCE_SHA256 = "18ba1fbae3d19d00cb717ce3203b6045ab54456ebec2da3fdb33ef7edae0bd0a"
TABLE = (("\u0423\u0441\u043b\u0443\u0433\u0430", "\u041a\u043e\u043b\u0438\u0447\u0435\u0441\u0442\u0432\u043e", "\u0426\u0435\u043d\u0430", "\u0421\u0443\u043c\u043c\u0430"),
         ("Alpha", "2", "1500", "3000"), ("Beta", "3", "2000", "6000"))
PARAGRAPHS = ("GOAL584 Office compatibility", "BEGIN-G584-OFFICE " + SOURCE.splitlines()[2],
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
SERVICE_BINDING_ATOMS = frozenset({"scope_equal", "payer", "actor", "chat", "model", "task", "category",
    "decoded_provider", "decoded_model", "decoded_response", "decoded_model_present", "decoded_provider_present",
    "row_id_is_raw_provider", "row_model_matches_deployment", "scope_call_equal", "native_id_binding", "opaque_log_id"})


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


def office_instruction(source):
    """Read the complete instruction from the already pinned Auto Attach owner."""
    require(isinstance(source, bytes), "office_instruction_source")
    source = source.replace(b"\r\n", b"\n")
    require(sha256(source).hexdigest() ==
            "9edf90bfa7bab3c75d7d8d794ea39761dff3b4b14c7d985270b47b15235affe1",
            "office_instruction_source")
    names = {"OFFICECLI_INSTRUCTION_MARKER", "OFFICECLI_INSTRUCTION"}
    nodes = [n for n in ast.parse(source).body if isinstance(n, ast.Assign)
             and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id in names]
    require(len(nodes) == 2, "office_instruction_source")
    namespace = {"__builtins__": {}}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "pinned-office-instruction", "exec"), namespace)
    return namespace["OFFICECLI_INSTRUCTION"]


def verify_instruction(wire, expected_instruction):
    # Native reasoning-model preprocessing moves the first system message to
    # developer before Responses conversion. Inspect only priority channels;
    # an instruction quoted in a user message or tool result cannot satisfy it.
    require(isinstance(expected_instruction, str) and bool(expected_instruction), "office_system_context")
    texts = [wire["instructions"]] if isinstance(wire.get("instructions"), str) else []
    for item in wire.get("input", []):
        if item.get("type") == "message" and item.get("role") in ("developer", "system"):
            texts.extend(block["text"] for block in item.get("content", [])
                         if isinstance(block, dict) and block.get("type") == "input_text"
                         and isinstance(block.get("text"), str))
    require(any(expected_instruction in text for text in texts), "office_system_context")


def provider_transport_from_profile(profile=None):
    """Select a finite proof mode from a source-bound native config observation."""
    if profile is None:
        return "native"
    require(isinstance(profile, dict) and set(profile) == {"primary", "service"}
            and isinstance(profile["service"], dict), "office_buffered_profile")
    service_streaming = profile["service"].get("supports_native_streaming")
    require(profile["primary"] == {"model_name": MODEL, "provider_model": "openai/goal584-fake-office",
                "deployment_id": "goal584-office-primary", "mode": "responses", "supports_native_streaming": False}
            and profile["primary"].get("supports_native_streaming") is False
            and (service_streaming is None or service_streaming is True)
            and profile["service"] == {"model_name": "gpt-6-luna", "provider_model": "openai/goal584-fake-office-service",
                "deployment_id": "goal584-office-service", "mode": "responses", "supports_native_streaming": service_streaming},
            "office_buffered_profile")
    return "buffered"


def verify_buffered_provider_profile(models):
    """Project actual native /model/info; credentials and price state stay private."""
    require(isinstance(models, list) and all(isinstance(row, dict) for row in models), "office_buffered_profile")
    profile = {}
    for name, model in (("primary", MODEL), ("service", "gpt-6-luna")):
        rows = [row for row in models if row.get("model_name") == model]
        require(len(rows) == 1 and isinstance(rows[0].get("model_info"), dict)
                and isinstance(rows[0].get("litellm_params"), dict), "office_buffered_profile")
        row = rows[0]; info = row["model_info"]
        profile[name] = {"model_name": model, "provider_model": row["litellm_params"].get("model"),
            "deployment_id": info.get("id"), "mode": info.get("mode"),
            "supports_native_streaming": info.get("supports_native_streaming")}
    provider_transport_from_profile(profile)
    return profile


def expected_provider_body(wire, wire_model, *, provider_transport="native"):
    """The declared native transport changes only model and, when buffered, stream."""
    require(type(provider_transport) is str and provider_transport in ("native", "buffered"),
            "office_provider_transport")
    expected = {**copy.deepcopy(wire), "model": wire_model}
    if provider_transport == "buffered":
        require(wire.get("stream") is True, "office_buffered_client_stream")
        expected.pop("stream")
    return expected


def verify_calls(calls, *, actor, key_hash, chat_id, answer_id, wire_model, native_specs,
                 exported, png, native_responses_payload, expected_instruction, provider_transport="native"):
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
        native_responses_payload=native_responses_payload, expected_instruction=expected_instruction,
        provider_transport=provider_transport)


def verify_wire_call(call, *, actor, key_hash, chat_id, answer_id, wire_model, native_specs,
                     expected_instruction, provider_transport="native"):
    """Shared single-call assertions at the existing auth/provider observation seam.

    The source-bound observer owns signed scope origin. This checks its complete
    projections and receipts, without creating a provider request or cost scope.
    """
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
    require(any(v.get("role") == "assistant" and any(n.get("text") == SOURCE for n in _nodes(v))
                for v in wire.get("input", []))
            and any(v.get("role") == "user" and any(n.get("text") == USER_REQUEST for n in _nodes(v))
                    for v in wire.get("input", [])), "office_source_context")
    verify_instruction(wire, expected_instruction)
    p = call["provider"]
    require({"id", "route", "body", "usage", "response", "lifecycle"} <= set(p)
            and isinstance(p["id"], str) and bool(p["id"]) and isinstance(p["response"], dict)
            and {"id", "model", "status", "usage", "output"} <= set(p["response"])
            and isinstance(p["response"]["output"], list)
            and all(isinstance(v, dict) for v in p["response"]["output"]), "office_provider_context")
    expected_body = expected_provider_body(wire, wire_model, provider_transport=provider_transport)
    require(p["body"] == expected_body
            and p["route"] == "/v1/responses" and p["usage"] == USAGE
            and p["response"]["id"] == p["id"] and p["response"]["model"] == wire_model
            and p["response"]["status"] == "completed" and p["response"]["usage"] == USAGE
            and p["lifecycle"] == {"terminal": True, "outcome": "completed"}, "office_provider_context")
    scope = call["verified_cost_scope"]
    require(scope.get("category") == "personal" and scope.get("model") == MODEL and scope.get("user_id") == actor
            and scope.get("chat_id") == scope.get("root_chat_id") == chat_id
            and scope.get("answer_id") == scope.get("root_answer_id") == answer_id
            and isinstance(scope.get("call_id"), str) and bool(scope["call_id"]), "office_call_scope")
    return wire


def verify_wire_calls(calls, *, actor, key_hash, chat_id, answer_id, wire_model, native_specs,
                      exported, png, native_responses_payload, expected_instruction, provider_transport="native"):
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
        wire = verify_wire_call(call, actor=actor, key_hash=key_hash, chat_id=chat_id, answer_id=answer_id,
            wire_model=wire_model, native_specs=native_specs, expected_instruction=expected_instruction,
            provider_transport=provider_transport)
        if index:
            original = responses_projection(calls[0]["wire_before_auth"])
            require({k: v for k, v in wire.items() if k != "input"} ==
                    {k: v for k, v in original.items() if k != "input"}, "office_continuation_parameters")
            previous = calls[index - 1]["wire_before_auth"]["input"]
            require(wire["input"][:len(previous)] == previous, "office_continuation_history")
        p = call["provider"]
        scope = call["verified_cost_scope"]
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


def _continuation_text(content):
    require(isinstance(content, str) or isinstance(content, list) and all(isinstance(part, dict)
            and set(part) == {'type', 'text'} and part['type'] == 'text' and isinstance(part['text'], str)
            for part in content), 'Unexpected multimodal/tool content at the provider boundary')
    return content if isinstance(content, str) else ''.join(part['text'] for part in content)


def verify_continuation_submission(sent, ack, *, http_status, chat_id, first_answer_id, prior_message_ids):
    """One pure owner for the browser and collector's observed ordinary Send.

    Raw/parsed request and ACK equality and their capture ordering belong to the
    existing IO caller. This checks the complete native submitted turn, never
    creates a request or assembles model history.
    """
    require(isinstance(sent, dict) and isinstance(ack, dict)
            and isinstance(sent.get('user_message'), dict),
            'Office continuation submission/acknowledgement schema differs')
    user = sent['user_message']; user_id, answer_id = user.get('id'), sent.get('id')
    for value in (user_id, answer_id):
        require(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', value),
                'Office native identifier unavailable')
    require(len({user_id, answer_id}) == 2 and not ({user_id, answer_id} & set(prior_message_ids))
            and sent.get('model') == MODEL and sent.get('chat_id') == chat_id
            and sent.get('parent_id') == first_answer_id and sent.get('stream') is True
            and sent.get('message_ids') == [{'model_id': MODEL, 'message_id': answer_id, 'modelIdx': 0}]
            and type(sent['message_ids'][0]['modelIdx']) is int
            and user.get('parentId') == first_answer_id and user.get('role') == 'user'
            and _continuation_text(user.get('content')) == CONTINUATION_REQUEST
            and isinstance(sent.get('background_tasks'), dict)
            and sent['background_tasks'].get('follow_up_generation') is True
            and type(http_status) is int and http_status == 200 and ack.get('chat_id', chat_id) == chat_id,
            'Office continuation submitted a different native turn')
    return user_id, answer_id


def verify_continuation_history(before, after, actor, first_answer, user_id, answer_id, file_id):
    """Check the selected native chain; never assemble replacement history."""
    require(before.get('id') == after.get('id') and before.get('user_id') == after.get('user_id') == actor,
            'Office continuation native chat owner differs')
    old = before['chat']['history']['messages']; history = after['chat']['history']; messages = history['messages']
    require(before['chat']['history']['currentId'] == first_answer and old[first_answer].get('childrenIds') == []
            and before['chat']['models'] == after['chat']['models'] == [MODEL], 'Office continuation selected history differs')
    if user_id not in messages or answer_id not in messages: return None
    require(set(messages) == set(old) | {user_id, answer_id} and history['currentId'] == answer_id,
            'Office continuation changed native history membership')
    for key, original in old.items():
        expected = copy.deepcopy(original)
        if key == first_answer: expected['childrenIds'] = [user_id]
        require(messages[key] == expected, 'Office continuation changed a saved prior message')
    user, answer = messages[user_id], messages[answer_id]
    content = _continuation_text(user.get('content'))
    require(user.get('id') == user_id and user.get('role') == 'user' and user.get('parentId') == first_answer
            and content == CONTINUATION_REQUEST and user.get('childrenIds') == [answer_id]
            and answer.get('id') == answer_id and answer.get('role') == 'assistant' and answer.get('model') == MODEL
            and answer.get('parentId') == user_id, 'Office continuation saved parent/user/model differs')
    require(not answer.get('error'), 'Office native continuation failed')
    if answer.get('done') is not True: return None
    output = answer.get('output') or []
    reasoning = [v for v in output if v.get('type') == 'reasoning']
    text = [v for item in output if item.get('type') == 'message' for v in item.get('content', [])
            if v.get('type') == 'output_text']
    require(len(output) == 2 and len(reasoning) == len(text) == 1 and reasoning[0].get('encrypted_content')
            and '/api/v1/files/' + file_id + '/content' in text[0].get('text', ''),
            'Office continuation lost native reasoning or existing file')
    statuses = [v for v in answer.get('statusHistory', []) if v.get('action') == 'employee_budget_cost']
    ready = (statuses and statuses[-1].get('done') is True
        and statuses[-1].get('description', '').startswith('Ответ: $0.20 · Чат: $0.80 · ')
        and isinstance(answer.get('followUps'), list) and bool(answer['followUps'])
        and all(isinstance(v, str) and v.strip() for v in answer['followUps']))
    return answer if ready else None


def verify_saved_continuation(call, *, first_calls, saved_output, native_saved, native_final,
                              native_source_sha256, actor, key_hash, chat_id, answer_id, wire_model,
                              native_specs, exported, png, native_responses_payload, expected_instruction,
                              provider_transport="native"):
    """Reconcile one new call with already accepted first-turn observations.

    The collector supplies actual saved DB output and two existing native_context
    observations: that saved output and the last provider response's full output.
    Host artifact binding must attest both producers. The OpenAPI digest comes
    independently from served source-bound state, never from either packet.
    These joins compare observations; they never build history to send a model.
    """
    require(isinstance(first_calls, list) and len(first_calls) == 3, "office_physical_calls")
    first_answer = first_calls[0]["verified_cost_scope"].get("answer_id")
    require(isinstance(first_answer, str) and bool(first_answer) and isinstance(answer_id, str)
            and bool(answer_id) and answer_id != first_answer, "office_saved_answer_identity")
    prior = verify_wire_calls(first_calls, actor=actor, key_hash=key_hash, chat_id=chat_id, answer_id=first_answer,
        wire_model=wire_model, native_specs=native_specs, exported=exported, png=png,
        native_responses_payload=native_responses_payload, expected_instruction=expected_instruction,
        provider_transport=provider_transport)
    wire = verify_wire_call(call, actor=actor, key_hash=key_hash, chat_id=chat_id, answer_id=answer_id,
        wire_model=wire_model, native_specs=native_specs, expected_instruction=expected_instruction,
        provider_transport=provider_transport)
    require(call["provider"]["id"] not in prior and call["verified_cost_scope"]["call_id"] not in
            {scope["call_id"] for scope in prior.values()}, "office_call_identity")
    base = responses_projection(first_calls[0]["wire_before_auth"])
    require(base.get("include") == ["reasoning.encrypted_content"]
            and {k: v for k, v in wire.items() if k != "input"} ==
                {k: v for k, v in base.items() if k != "input"}, "office_continuation_parameters")
    modules = {k: WEBUI_MODULES[k] for k in ("utils/tools.py", "routers/openai.py", "utils/middleware.py")}
    modules["utils/misc.py"] = "9098c447441e2f6bfa529ae8506a03acab6400a8205c7942e86b004c07833068"
    require(isinstance(native_source_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", native_source_sha256)
            and isinstance(saved_output, list) and len(saved_output) == 8, "office_saved_native_source")
    final_output = first_calls[-1]["provider"]["response"]["output"]
    for packet, output in ((native_saved, saved_output), (native_final, final_output)):
        require(isinstance(packet, dict) and set(packet) == {"schema", "module_sha256", "source_body_sha256",
            "native_specs", "reasoning_cases", "saved_output_case"} and type(packet["schema"]) is int
            and packet["schema"] == 1 and packet["module_sha256"] == modules
            and packet["source_body_sha256"] == native_source_sha256
            and isinstance(packet["native_specs"], list) and len(packet["native_specs"]) == len(native_specs),
            "office_saved_native_source")
        verify_schemas(base["tools"], packet["native_specs"])
        cases = packet["reasoning_cases"]
        require(isinstance(cases, list) and 0 < len(cases) <= 4, "office_saved_native_reasoning")
        for case in cases:
            require(isinstance(case, dict) and set(case) == {"input_reasoning", "native_input"}
                    and isinstance(case["input_reasoning"], list) and all(isinstance(v, dict)
                        and v.get("type") == "reasoning" for v in case["input_reasoning"])
                    and case["native_input"] == native_responses_payload({"messages": [
                        {"role": "assistant", "output": case["input_reasoning"]}]})["input"],
                    "office_saved_native_reasoning")
        observed = packet["saved_output_case"]
        require(isinstance(observed, dict) and set(observed) == {"input_saved_output", "native_input"}
                and observed["input_saved_output"] == output and isinstance(observed["native_input"], list)
                and all(isinstance(v, dict) for v in observed["native_input"]), "office_saved_native_echo")
    require(native_saved["reasoning_cases"] == native_final["reasoning_cases"], "office_saved_native_reasoning")
    saved_input = native_saved["saved_output_case"]["native_input"]
    expected_saved = first_calls[-1]["wire_before_auth"]["input"][len(base["input"]):] + native_final["saved_output_case"]["native_input"]
    provider_reasoning = [[v for v in first["provider"]["response"]["output"] if v.get("type") == "reasoning"]
                          for first in first_calls]
    expected_reasoning = [v for reasoning in provider_reasoning for v in native_responses_payload(
        {"messages": [{"role": "assistant", "output": reasoning}]})["input"]]
    atoms = dict(zip(SAVED_HISTORY_ATOMS, (
        bool(saved_input == expected_saved),
        bool(len(saved_input) == 8),
        bool([v for v in saved_output if v.get("type") == "reasoning"] ==
             [v for reasoning in provider_reasoning for v in reasoning]),
        bool([v for v in saved_input if v.get("type") == "reasoning"] == expected_reasoning),
        bool(len(expected_reasoning) == 3))))
    try:
        require(all(atoms.values()), "office_saved_provider_history")
    except ProofError as error:
        error.office_saved_history_atoms = atoms
        raise
    question = {"type": "message", "role": "user", "content": [{"type": "input_text", "text": CONTINUATION_REQUEST}]}
    require(wire["input"] == base["input"] + saved_input + [question], "office_saved_full_context")
    output = call["provider"]["response"]["output"]
    require([v.get("type") for v in output] == ["reasoning", "message"]
            and isinstance(output[0].get("encrypted_content"), str) and bool(output[0]["encrypted_content"])
            and output[1].get("role") == "assistant" and output[1].get("content") == [{"type": "output_text",
                "text": "[Download](/api/v1/files/" + exported["result_file_id"] + "/content)", "annotations": []}],
            "office_saved_final_attachment")
    return {call["provider"]["id"]: call["verified_cost_scope"]}


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
                   wire_model, deployment_id, validate_scope, validate_rates, decode_response_id, expected_calls=3,
                   provider_transport="native", model=MODEL, expected_call_spend=Decimal('.20'),
                   input_rate=Decimal('.01'), output_rate=Decimal('.02'), user_spend_delta=None):
    """Readback assertions only. SDK decoder/rate validator are existing owners.

    The isolated collector must pass ALL raw pages from NativeProof.logs, not
    positive-cost rows, and the full retained original payer state. No pricing
    calculation, new ledger, scheduler or budget allowance is implemented here.
    """
    require(type(expected_calls) is int and expected_calls in (1, 3, 6), "office_expected_calls")
    require(type(provider_transport) is str and provider_transport in ("native", "buffered"), "office_provider_transport")
    require(isinstance(model, str) and 0 < len(model) <= 128
            and all(type(v) is Decimal and v.is_finite() and v > 0
                    for v in (expected_call_spend, input_rate, output_rate)), "office_finance_fixture_terms")
    expected_key_delta = expected_call_spend * expected_calls
    user_spend_delta = expected_key_delta if user_spend_delta is None else user_spend_delta
    require(type(user_spend_delta) is Decimal and user_spend_delta.is_finite()
            and user_spend_delta >= expected_key_delta, "office_finance_fixture_terms")
    expected_spend = format(expected_key_delta, 'f').lstrip('0')
    require(before["old_payers"] and before["old_payers"] == after["old_payers"], "office_old_finance_changed")
    require(before["user"].get("user_id") == before["key"].get("user_id") == actor
            and before["key"].get("models") == [model], "office_financial_owner")
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
    require(len(added) == len(calls_by_provider) == expected_calls, "office_row_count")
    observed = set()
    for row in added:
        metadata = json.loads(row["metadata"]) if isinstance(row.get("metadata"), str) else row["metadata"]
        spend = metadata["spend_logs_metadata"]
        scope = validate_scope(spend["owui_budget"])
        decoded = decode_response_id(row["request_id"])
        provider = decoded["response_id"]
        binding = (decoded["custom_llm_provider"] == "openai" and decoded["model_id"] == deployment_id
                   if provider_transport == "native" else decoded["custom_llm_provider"] is None
                   and decoded["model_id"] is None and row.get("model_id") == deployment_id)
        require(binding
                and provider in calls_by_provider and provider not in observed and scope == calls_by_provider[provider],
                "office_row_dispatch_binding")
        observed.add(provider)
        require(scope["user_id"] == row.get("user") == actor and scope["model"] == row.get("model_group") == model
                and scope["chat_id"] == scope["root_chat_id"] == row.get("session_id") == chat_id
                and scope["answer_id"] == scope["root_answer_id"] == answer_id and row.get("api_key") == key_hash
                and row.get("model") in (model, wire_model, "openai/" + wire_model)
                and row.get("model_id") == deployment_id and row.get("status") == "success"
                and [row.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens")] == [10, 5, 15]
                and all(type(row.get(k)) is int for k in ("prompt_tokens", "completion_tokens", "total_tokens"))
                and close_amount(row.get("spend"), expected_call_spend), "office_row_identity_usage_cost")
        rates = validate_rates(spend["owui_billed_token_rates"])["rates"]
        require(Decimal(str(rates["input_cost_per_token"])) == input_rate
                and Decimal(str(rates["output_cost_per_token"])) == output_rate, "office_row_rates")
    for owner in ("user", "key"):
        require(close_amount(Decimal(str(after[owner]["spend"])) - Decimal(str(before[owner]["spend"])),
                              user_spend_delta if owner == 'user' else expected_key_delta), "office_native_spend_delta")
    return {"physical_calls": expected_calls, "new_raw_rows": expected_calls, "native_spend_delta_usd": expected_spend}


def verify_service_finance(before, after, *, actor, payer, key_hash, chat_id, provider_id, verified_scope, dispatch,
                           wire_model, deployment_id, descriptor, validate_scope, validate_rates, decode_response_id):
    """One native follow-up Responses row; fixed fixture totals, no price math.

    The collector supplies all raw pages and its existing actual auth/provider
    call record, never a reconstructed dispatch DTO. The signed call nonce joins
    the native row to that physical call; native log IDs can be opaque.
    Descriptor expectations come from the source-bound prepared native config.
    This separate service payer must not be included among unchanged old payers.
    """
    require(actor != payer and before["user"].get("user_id") == before["key"].get("user_id") == payer
            and before["key"].get("models") == ["gpt-6-luna"], "office_service_owner")
    require(isinstance(dispatch, dict) and dispatch.get("verified_cost_scope") == verified_scope
            and dispatch.get("auth_user_id") == payer and dispatch.get("auth_key_hash") == key_hash
            and dispatch.get("attestation_present_before") is True and dispatch.get("provenance_removed_after") is True
            and not dispatch.get("auth_failure") and dispatch.get("route") in ("/responses", "/v1/responses", "/openai/v1/responses")
            and isinstance(dispatch.get("provider"), dict) and isinstance(dispatch["provider"].get("response"), dict)
            and dispatch.get("provider", {}).get("id") == provider_id
            and dispatch.get("provider", {}).get("response", {}).get("id") == provider_id,
            "office_service_dispatch_observation")
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
    opaque = decoded["custom_llm_provider"] is None and decoded["model_id"] is None
    native_id_binding = opaque or (decoded["custom_llm_provider"] == "openai"
        and decoded["model_id"] == deployment_id and decoded["response_id"] == provider_id)
    try:
        require(scope == verified_scope and scope["user_id"] == payer and scope["actor_id"] == actor
                and scope["chat_id"] == chat_id and scope["model"] == "gpt-6-luna"
                and scope["task"] == "follow_up_generation" and scope["category"] == "service"
                and native_id_binding, "office_service_dispatch_binding")
    except ProofError as error:
        # Fixed names and booleans reveal the failed assertion even when raw
        # operand redaction or private-state readback cannot safely complete.
        error.office_service_binding_atoms = {
            "scope_equal": scope == verified_scope, "payer": scope["user_id"] == payer,
            "actor": scope["actor_id"] == actor, "chat": scope["chat_id"] == chat_id,
            "model": scope["model"] == "gpt-6-luna", "task": scope["task"] == "follow_up_generation",
            "category": scope["category"] == "service", "decoded_provider": decoded["custom_llm_provider"] == "openai",
            "decoded_model": decoded["model_id"] == deployment_id, "decoded_response": decoded["response_id"] == provider_id,
            "decoded_model_present": decoded["model_id"] is not None,
            "decoded_provider_present": decoded["custom_llm_provider"] is not None,
            "row_id_is_raw_provider": row["request_id"] == provider_id,
            "row_model_matches_deployment": row.get("model_id") == deployment_id,
            "scope_call_equal": scope["call_id"] == verified_scope.get("call_id"),
            "native_id_binding": native_id_binding, "opaque_log_id": opaque}
        # Retain only this failed comparison's operands. Never attach the raw
        # financial row, API key, arbitrary metadata or model content.
        error.office_service_binding = {
            "scope": copy.deepcopy(scope), "verified_scope": copy.deepcopy(verified_scope),
            "request_id": row["request_id"],
            "decoded": {k: decoded.get(k) for k in ("custom_llm_provider", "model_id", "response_id")},
            "row": {k: row.get(k) for k in ("user", "model", "model_id", "model_group", "session_id", "status")},
            "expected": {"actor": actor, "payer": payer, "chat_id": chat_id,
                         "deployment_id": deployment_id, "provider_id": provider_id}}
        raise
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
