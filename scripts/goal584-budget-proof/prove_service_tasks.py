#!/usr/bin/env python3
"""One actual native direct-title service event in the disposable GOAL584 fixture.

Run inside proxy after prior browser receipts have been retained. Native WebUI
and LiteLLM APIs own configuration, identity, assignment and money. The script
never calls a paid destination, writes application tables or fabricates an answer
ID. Automatic background tasks and embeddings remain unqualified.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, ProxyHandler, build_opener
from uuid import UUID, uuid4

from aiohttp import ClientSession

from capture_webui_auth import CAPTURE, FIELDS, save as save_capture
from employee_budget_admin_client import BudgetAdminClient
from employee_budget_admin_contract import BudgetAdminError
from provenance import validate_persisted_service_scope
from provision_webui import (MODELS, OPERATOR_STATE, PROXY_URL, TASK_FLAGS, WEBUI_URL, WebUI,
                             native_client, read_private, write_private, NoRedirects, ProofError, require)
from provision_cost_display import FILTER_ID, STATE, secret_values, source_hash, model_body, grant_set
from provision_admin import model_grant_changes, normalize, positive_logs


FUNCTION_ID = "employee_budget_service"
SOURCE = Path("/proof/budgets/service_pipe.py")
TITLE_PATH = "/api/v1/tasks/title/completions"
PROVIDER_URL = "http://provider:8000"
TASK = "title_generation"
PARAMS = {"max_tokens": 5, "temperature": 0, "response_format": {"type": "json_object"}}
MAX_BYTES = 4 * 1024 * 1024
UNSIGNED_REASON = "Invalid signed budget provenance"


def canonical(value):
    try:
        valid = isinstance(value, str) and str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        valid = False
    require(valid, "Noncanonical native service fixture identity")
    return value


def response(webui, method, path, token, body=None):
    require(path.startswith("/") and not path.startswith("//"), "Invalid native service API path")
    request = Request(WEBUI_URL + path, method=method,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        data=None if body is None else json.dumps(body, allow_nan=False).encode("utf-8"))
    try:
        result = webui.opener.open(request, timeout=30)
    except HTTPError as error:
        result = error
    except (URLError, TimeoutError, OSError):
        raise ProofError("Native service WebUI transport failed") from None
    with result:
        status, raw = result.code, result.read(MAX_BYTES + 1)
    require(len(raw) <= MAX_BYTES, "Native service response exceeded bound")
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError):
        raise ProofError("Native service response was not JSON") from None
    require(isinstance(data, (dict, list)), "Native service response had unexpected shape")
    return status, data


def provider(method="GET", path="/__proof/requests", body=None):
    require(path in ("/__proof/requests", "/__proof/reset", "/__proof/control"), "Invalid synthetic provider control")
    request = Request(PROVIDER_URL + path, method=method, headers={"Content-Type": "application/json"},
                      data=None if body is None else json.dumps(body, allow_nan=False).encode())
    opener = build_opener(ProxyHandler({}), NoRedirects())
    try:
        with opener.open(request, timeout=10) as result:
            require(result.code == 200, "Synthetic title provider control failed")
            raw = result.read(MAX_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError):
        raise ProofError("Synthetic title provider unavailable") from None
    require(len(raw) <= MAX_BYTES, "Synthetic title receipt exceeded bound")
    data = json.loads(raw)
    require(isinstance(data, dict), "Synthetic title receipt was not an object")
    return data


def semantic(body):
    require(isinstance(body, dict), "Native title body is missing")
    return {field: copy.deepcopy(body[field]) for field in FIELDS if field in body}


def no_secrets(value, secrets=()):
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    require(not any(secret and secret in encoded for secret in secrets)
            and re.search(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|(?:sk-|gw-)[A-Za-z0-9_-]{16,}", encoded) is None,
            "Credential-bearing service evidence suppressed")
    return value


def owned_source(webui, account):
    status, listing = response(webui, "GET", "/api/v1/chats/list?page=1", account["token"])
    require(status == 200 and isinstance(listing, list) and 0 < len(listing) <= 60, "Native saved Chat list is unavailable")
    for entry in listing[:10]:
        chat_id = canonical(entry.get("id"))
        status, saved = response(webui, "GET", "/api/v1/chats/" + chat_id, account["token"])
        require(status == 200 and isinstance(saved, dict) and saved.get("id") == chat_id
                and saved.get("user_id") == account["id"], "Native Chat owner differs from the service actor")
        messages = ((saved.get("chat") or {}).get("history") or {}).get("messages")
        require(isinstance(messages, dict), "Native saved Chat history is unavailable")
        found = [message for message in messages.values() if isinstance(message, dict)
                 and message.get("role") == "user" and message.get("content") == "Hi"
                 and (message.get("user_id") or saved["user_id"]) == account["id"]]
        if found:
            source_id = canonical(found[0].get("id"))
            return {"model": MODELS[0], "chat_id": chat_id, "messages": [{"role": "user", "content": "Hi"}]}, source_id
    raise ProofError("No bounded fixture-owned native Hi source was found")


async def budgets(state, payer=None):
    accounts = [*state["users"], state["admin"]]
    if state.get("bootstrap_fixture", {}).get("employee"):
        accounts.append(state["bootstrap_fixture"]["employee"])
    async with ClientSession(trust_env=False) as session:
        client = BudgetAdminClient(session, PROXY_URL, read_private(OPERATOR_STATE)["operator_token"])
        personal = [await client.read_employee(account["id"], tuple(MODELS)) for account in accounts]
        service = await client.read_employee(payer, (MODELS[0],)) if payer is not None else None
    return personal, service


def register_pipe_model(webui, state):
    """A native Function also needs a registered, actor-readable Workspace Model."""
    admin, actor = state["admin"], state["users"][0]
    before = {model: model_body(webui.model(admin["token"], model)) for model in MODELS}
    requested = {"id": FUNCTION_ID, "base_model_id": None, "name": "GOAL584 service title",
        "params": {}, "meta": {"capabilities": {"builtin_tools": False}, "filterIds": [], "toolIds": [], "skillIds": []},
        "is_active": True, "access_grants": [{"principal_type": "user", "principal_id": actor["id"], "permission": "read"}]}
    webui.session(admin, "admin")
    created = webui.ok("POST", "/api/v1/models/create", token=admin["token"], body=requested)
    expected = model_body(created)
    require(created.get("user_id") == admin["id"]
            and all(expected[field] == requested[field] for field in ("id", "base_model_id", "name", "params", "is_active"))
            and all(expected["meta"].get(field) == value for field, value in requested["meta"].items())
            and all(value is None for field, value in expected["meta"].items() if field not in requested["meta"])
            and grant_set(expected) == grant_set(requested) and len(expected["access_grants"]) == 1,
            "Native service Workspace Model creation changed source configuration or grants")
    actual = webui.model(admin["token"], FUNCTION_ID)
    require(actual.get("user_id") == admin["id"] and not model_grant_changes(expected, model_body(actual)),
            "Native service Workspace Model readback differs")
    require({model: model_body(webui.model(admin["token"], model)) for model in MODELS} == before,
            "Service Workspace Model registration changed ordinary models")
    state["service_fixture"]["workspace_model"] = model_body(actual)
    state["service_fixture"]["ordinary_model_profiles_unchanged"] = True


def install(webui, state, path):
    require("service_fixture" not in state, "Service proof requires fresh isolated service state")
    admin, payer = state["admin"], str(uuid4())
    require(payer not in {account["id"] for account in [*state["users"], admin]}, "Service payer collided with actor identity")
    source = SOURCE.read_text(encoding="utf-8")
    require(0 < len(source.encode()) <= 128 * 1024, "Service Pipe source exceeded bound")
    common_path = "/api/v1/functions/id/" + FILTER_ID + "/valves"
    common = webui.ok("GET", common_path, token=admin["token"])
    require(common.get("service_payer_id") in (None, ""), "Existing service configuration must not be overwritten")
    state["service_fixture"] = {"stage": "installing", "payer_id": payer, "pipe_sha256": source_hash(source)}
    write_private(path, state)
    async def initialize():
        async def authorize():
            webui.session(admin, "admin")
        async with ClientSession(trust_env=False) as session:
            client = BudgetAdminClient(session, PROXY_URL, read_private(OPERATOR_STATE)["operator_token"])
            return await client.initialize_employee(payer, ((MODELS[0], Decimal(20)),), Decimal(20),
                os.environ.get("OWUI_BUDGET_GATEWAY_SECRET", ""), before_write=authorize)
    created = asyncio.run(initialize())
    state["service_fixture"]["key_hash"] = created.models[0].key_hash
    write_private(path, state)
    function_path = "/api/v1/functions/id/" + FUNCTION_ID
    webui.ok("POST", "/api/v1/functions/create", token=admin["token"], body={
        "id": FUNCTION_ID, "name": "GOAL584 service title", "content": source, "meta": {}})
    webui.ok("POST", function_path + "/valves/update", token=admin["token"], body={"target_model_id": MODELS[0]})
    webui.ok("POST", function_path + "/toggle", token=admin["token"])
    register_pipe_model(webui, state)
    expected = {**copy.deepcopy(common), "service_payer_id": payer}
    webui.session(admin, "admin")
    require(webui.ok("GET", common_path, token=admin["token"]) == common, "Common Function configuration changed during setup")
    webui.ok("POST", common_path + "/update", token=admin["token"], body=expected)
    require(webui.ok("GET", common_path, token=admin["token"]) == expected, "Common Function Valves were not preserved")
    actual = webui.ok("GET", function_path, token=admin["token"])
    require(actual.get("id") == FUNCTION_ID and actual.get("user_id") == admin["id"]
            and actual.get("type") == "pipe" and actual.get("is_active") is True
            and actual.get("is_global") is False and source_hash(actual.get("content", "")) == source_hash(source),
            "Installed service Function differs from its native source/owner/activation")
    require(webui.ok("GET", function_path + "/valves", token=admin["token"]) == {"target_model_id": MODELS[0]},
            "Service Pipe target Valves differ")
    status, catalog = response(webui, "GET", "/api/models?refresh=true", state["users"][0]["token"])
    require(status == 200 and isinstance(catalog, dict) and isinstance(catalog.get("data"), list)
            and {MODELS[0], FUNCTION_ID} <= {model.get("id") for model in catalog["data"]},
            "Native actor catalog did not expose the configured task Pipe and target")
    state["service_fixture"]["stage"] = "setup_complete"
    write_private(path, state)
    return payer


def task_config(webui, admin, original, target):
    expected = copy.deepcopy(original)
    expected.update({flag: False for flag in TASK_FLAGS})
    expected.update(ENABLE_TITLE_GENERATION=True, TASK_MODEL=target, TASK_MODEL_EXTERNAL=target,
                    TASK_MODEL_PARAMS=copy.deepcopy(PARAMS))
    webui.session(admin, "admin")
    webui.ok("POST", "/api/v1/tasks/config/update", token=admin["token"], body=expected)
    require(webui.ok("GET", "/api/v1/tasks/config", token=admin["token"]) == expected,
            "Native task configuration readback differs")
    return expected


def captured():
    data = json.loads(CAPTURE.read_text(encoding="utf-8"))
    require(data.get("schema") == 1 and isinstance(data.get("requests"), list) and len(data["requests"]) <= 8,
            "Service gateway observation exceeded bound")
    return data


def denied(status, data, code=None):
    require(isinstance(data, dict) and (status >= 400 or bool(data.get("error"))), "Service negative was not a terminal rejection")
    if code is not None:
        require(code in json.dumps(data, ensure_ascii=False), "Service negative did not reach its intended native guard")


def unsigned_denied(status, data):
    require(status == 403 and isinstance(data, dict) and UNSIGNED_REASON in json.dumps(data, ensure_ascii=False),
            "Unsigned service negative did not reach the signed-provenance 403 guard")
    return {"http_status": 403, "native_guard": "invalid_signed_budget_provenance", "message": UNSIGNED_REASON}


def ordinary_pipe_request(source):
    # Native main treats a saved chat_id as a request to insert/continue a turn,
    # which requires real message IDs. Its supported stateless synchronous path
    # needs neither a saved chat_id nor invented message IDs for this spoof test.
    return {"model": FUNCTION_ID, "messages": copy.deepcopy(source["messages"]), "stream": False,
            "background_tasks": {"title_generation": False, "tags_generation": False, "follow_up_generation": False},
            "metadata": {"task": TASK}}


def negative_diagnostic(case, status, data, expected):
    encoded = json.dumps(data, ensure_ascii=False, sort_keys=True, allow_nan=False)
    known = {"unsupported_task": "unsupported_task", "chat_access_denied": "chat_access_denied",
             "invalid_signed_budget_provenance": UNSIGNED_REASON,
             "invalid_message_id": "Message already exists or has an invalid ID.",
             "model_unregistered": "model_unregistered"}
    return {"case": case, "http_status": status, "expected_guard": expected,
            "observed_known_codes": [code for code, marker in known.items() if marker in encoded],
            "response_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
            "response_shape": "object" if isinstance(data, dict) else "list",
            "guard_verified": False, "provider_ids_unchanged": None}


def service_scope(row, payer, actor, chat_id, key_hash):
    metadata = row.get("metadata")
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    require(isinstance(metadata, dict), "Native service spend metadata is missing")
    scope = validate_persisted_service_scope((metadata.get("spend_logs_metadata") or {}).get("owui_budget"))
    require(scope["user_id"] == payer and scope["actor_id"] == actor and scope["chat_id"] == chat_id
            and scope["model"] == MODELS[0] and scope["task"] == TASK
            and row.get("user") == payer and row.get("api_key") == key_hash
            and row.get("session_id") == "owui-service:" + chat_id and row.get("model_group") == MODELS[0]
            and row.get("status") == "success" and Decimal(str(row.get("spend"))) == Decimal(".20")
            and [row.get(field) for field in ("prompt_tokens", "completion_tokens", "total_tokens")] == [10, 5, 15],
            "Native service attribution, assignment, usage or cost differs")
    return scope


def verify_context(observed, provider_data, row, result, payer, actor, chat_id, key_hash):
    calls = observed["requests"]
    require(len(calls) == 4, "Expected unsigned baseline, signed service, and two raw negative gateway attempts")
    baseline, service, raw_title, raw_unknown = calls
    require(baseline["user_id"] == service["user_id"] == actor and baseline["task"] == service["task"] == TASK
            and baseline["attestation_present_before"] is False and service["attestation_present_before"] is True
            and "native_auth_user_id" not in baseline and "verified_cost_scope" not in baseline
            and service.get("native_auth_user_id") == payer, "Actual native title baseline/service authority differs")
    require(baseline["body"] == baseline["body_after_auth"] == service["body"] == service["body_after_auth"],
            "Actual native title semantic input changed between baseline, signed path or authentication")
    body = service["body"]
    require(body.get("model") == MODELS[0] and body.get("stream") is False
            and body.get("max_tokens") == 5 and body.get("temperature") == 0
            and body.get("response_format") == {"type": "json_object"}, "Actual native task generation parameters differ")
    require(service.get("provenance_removed_after") is True and service.get("native_stream_usage_patch") == {},
            "Service token or unexpected stream transformation remained")
    for call, task in ((raw_title, TASK), (raw_unknown, "tags_generation")):
        require(call["task"] == task and call["user_id"] == actor and call["attestation_present_before"] is False
                and "native_auth_user_id" not in call and "verified_cost_scope" not in call,
                "Unsigned raw negative unexpectedly obtained a service identity")
    requests = provider_data.get("requests")
    require(provider_data.get("synthetic") is True and isinstance(requests, list) and len(requests) == 1,
            "Title phase dispatched beyond its single synthetic service call")
    physical = requests[0]
    require(physical["id"] == row.get("request_id") == result.get("id")
            and physical.get("usage") == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "Title response/provider/native request identity or usage differs")
    expected = {**body, "model": "goal584-fake-a"}
    require(semantic(physical.get("body")) == expected, "Actual provider context differs from actual native task input")
    require(not any(field in physical["body"] for field in ("metadata", "litellm_metadata", "owui_budget_provenance")),
            "Log-only scope or signed token reached the provider")
    no_secrets(physical)
    scope = service_scope(row, payer, actor, chat_id, key_hash)
    require(service.get("verified_cost_scope") == scope, "Native ledger scope differs from gateway-validated scope")
    content = result.get("choices", [{}])[0].get("message", {}).get("content")
    require(isinstance(content, str) and json.loads(content) == {"title": "Proof"}, "Native title result is unusable")
    return {"scope": scope, "request_id": row["request_id"], "native_semantic_body": body,
            "native_semantic_sha256": hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()}


def run(webui, state, args, receipt=None):
    admin, actor = state["admin"], state["users"][0]
    webui.session(admin, "admin")
    webui.session(actor, "user")
    source, source_id = owned_source(webui, actor)
    foreign, _ = owned_source(webui, state["users"][1])
    personal_before, _ = asyncio.run(budgets(state))
    native = native_client(state)
    personal_ids = {budget.user_id: sorted(row["request_id"] for row in native.logs(budget.user_id)
                    if Decimal(str(row.get("spend", 0))) > 0) for budget in personal_before}
    payer = install(webui, state, args.private_state)
    _, before = asyncio.run(budgets(state, payer))
    require(before.spend == 0 and before.max_budget == 20, "Service payer is not a fresh native budget")
    original = webui.ok("GET", "/api/v1/tasks/config", token=admin["token"])
    state["service_fixture"]["original_task_config"] = copy.deepcopy(original)
    write_private(args.private_state, state)
    receipt = {} if receipt is None else receipt
    receipt.update({"actor_id": actor["id"], "payer_id": payer, "chat_id": source["chat_id"],
               "native_source_message_id": source_id, "source_kind": "persisted_fixture_owned_Hi",
               "pipe_source_sha256": state["service_fixture"]["pipe_sha256"], "stage": "installed", "negatives": []})
    try:
        provider("POST", "/__proof/reset", {})
        provider("POST", "/__proof/control", {"title_mode": True})
        save_capture({"schema": 1, "requests": []})
        baseline_config = task_config(webui, admin, original, MODELS[0])
        status, baseline = response(webui, "POST", TITLE_PATH, actor["token"], source)
        receipt["baseline_observation"] = negative_diagnostic("unsigned_native_title", status, baseline,
                                                               "invalid_signed_budget_provenance")
        receipt["baseline_denial"] = unsigned_denied(status, baseline)
        require(len(captured()["requests"]) == 1 and provider()["requests"] == [], "Unsigned native title reached provider or bypassed native gateway")
        receipt["baseline_observation"].update(guard_verified=True, provider_ids_unchanged=True, provider_call_count=0)
        receipt["stage"] = state["service_fixture"]["stage"] = "unsigned_baseline_verified"
        service_config = task_config(webui, admin, original, FUNCTION_ID)
        status, result = response(webui, "POST", TITLE_PATH, actor["token"], source)
        require(status == 200 and isinstance(result, dict) and not result.get("error"), "Signed native service title failed")
        identifiers = [entry["id"] for entry in provider()["requests"]]
        require(len(identifiers) == 1, "Native title did not dispatch exactly once")
        receipt["positive_title_provider_ids"] = identifiers
        receipt["stage"] = state["service_fixture"]["stage"] = "signed_title_returned"
        write_private(args.private_state, state)
        tests = [("ordinary_selected_pipe", "/api/chat/completions", ordinary_pipe_request(source), "unsupported_task"),
                 ("raw_forged_title", "/openai/chat/completions", {"model": MODELS[0], "messages": source["messages"],
                    "stream": False, "max_tokens": 5, "metadata": {"task": TASK, "chat_id": source["chat_id"]}}, None),
                 ("raw_unknown_task", "/openai/chat/completions", {"model": MODELS[0], "messages": source["messages"],
                    "stream": False, "max_tokens": 5, "metadata": {"task": "tags_generation", "chat_id": source["chat_id"]}}, None),
                 ("foreign_chat", TITLE_PATH, {**source, "chat_id": foreign["chat_id"]}, "chat_access_denied")]
        for label, path, body, code in tests:
            status, rejected = response(webui, "POST", path, actor["token"], body)
            diagnostic = negative_diagnostic(label, status, rejected, code or "invalid_signed_budget_provenance")
            receipt["negatives"].append(diagnostic)
            receipt["stage"], receipt["current_negative_case"] = "negative_observed", label
            observed_ids = [entry["id"] for entry in provider()["requests"]]
            diagnostic.update(provider_ids_unchanged=observed_ids == identifiers, provider_call_count=len(observed_ids))
            if label.startswith("raw_"):
                rejection = unsigned_denied(status, rejected)
            else:
                denied(status, rejected, code)
                rejection = {"http_status": status, "native_guard": code}
            require(diagnostic["provider_ids_unchanged"],
                    "Rejected service path reached provider: " + label)
            diagnostic.update(rejection, guard_verified=True)
        receipt["stage"] = state["service_fixture"]["stage"] = "negative_guards_verified"
        def persisted():
            personal_after, service_after = asyncio.run(budgets(state, payer))
            require(personal_after == personal_before, "Service task changed personal caps/spend/reset/assignment")
            rows = [row for row in native.logs(payer) if Decimal(str(row.get("spend", 0))) > 0]
            require(len(rows) <= 1, "Service task created extra positive native rows")
            if len(rows) != 1 or service_after.spend != Decimal(".20") or service_after.models[0].spend != Decimal(".20"):
                return None
            require(service_after.max_budget == before.max_budget and service_after.budget_duration == before.budget_duration
                    and service_after.budget_reset_at == before.budget_reset_at
                    and {**asdict(service_after.models[0]), "spend": Decimal(0)} == asdict(before.models[0]),
                    "Service task changed cap/reset/key identity")
            return rows[0], service_after
        row, after = native.poll("direct title service accounting", persisted)
        for budget in personal_before:
            require(sorted(entry["request_id"] for entry in native.logs(budget.user_id)
                    if Decimal(str(entry.get("spend", 0))) > 0) == personal_ids[budget.user_id], "Service event added personal spend history")
        observed, provider_data = captured(), provider()
        verified = verify_context(observed, provider_data, row, result, payer, actor["id"], source["chat_id"], state["service_fixture"]["key_hash"])
        no_secrets(observed)
        write_private(args.context_receipt, observed)
        write_private(args.provider_receipt, provider_data)
        receipt.update(verified, unsigned_baseline_denied=True, physical_calls=1, service_cost_usd="0.20",
            pipe_workspace_model=state["service_fixture"]["workspace_model"],
            ordinary_model_profiles_unchanged=state["service_fixture"]["ordinary_model_profiles_unchanged"],
            service_cap_usd=str(after.max_budget), service_spend_usd=str(after.spend),
            service_key_spend_usd=str(after.models[0].spend), service_budget_duration=after.budget_duration,
            service_budget_reset_at=after.budget_reset_at, personal_native_state_unchanged=True,
            personal_positive_history_unchanged=True, full_native_baseline_service_provider_context_equal=True,
            task_config_only_model_selection_changed={key: value for key, value in baseline_config.items()
                if key not in ("TASK_MODEL", "TASK_MODEL_EXTERNAL")} == {key: value for key, value in service_config.items()
                if key not in ("TASK_MODEL", "TASK_MODEL_EXTERNAL")})
        state["service_fixture"]["stage"] = "event_verified"
        receipt["stage"] = "event_verified"
        write_private(args.private_state, state)
        return receipt
    finally:
        webui.session(admin, "admin")
        webui.ok("POST", "/api/v1/tasks/config/update", token=admin["token"], body=original)
        restored = webui.ok("GET", "/api/v1/tasks/config", token=admin["token"])
        require(restored == original, "Original native task configuration restoration failed")
        state["service_fixture"]["task_config_restored"] = True
        if state["service_fixture"]["stage"] == "event_verified":
            state["service_fixture"]["stage"] = "qualified_direct_title"
        write_private(args.private_state, state)


def admin_snapshot(webui, state):
    """Read-only counters/ledger for the separate paid admin footer view."""
    fixture = state.get("service_fixture") or {}
    require(fixture.get("stage") == "qualified_direct_title" and fixture.get("task_config_restored") is True,
            "Admin service view requires the completed restored direct-title phase")
    webui.session(state["admin"], "admin")
    personal, service = asyncio.run(budgets(state, canonical(fixture.get("payer_id"))))
    rows, unknown = positive_logs(native_client(state), state)
    return {"personal": normalize(personal), "service": normalize([service]),
            "positive_spend_logs": rows, "unqualified_zero_row_count": unknown,
            "admin_id": state["admin"]["id"], "service_payer_id": service.user_id,
            "source_endpoints": ["/user/info", "/key/list", "/spend/logs/v2"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("title", "admin-snapshot"), default="title")
    for name in ("private-state", "receipt"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("context-receipt", "provider-receipt"):
        parser.add_argument("--" + name, type=Path)
    args = parser.parse_args()
    receipt = {"schema": 1, "proof": "goal584-native-direct-title-service", "passed": False,
               "started_at_utc": datetime.now(timezone.utc).isoformat(),
               "not_qualified": ["automatic_background_tasks", "embeddings", "production", "paid_provider"]}
    state, output_valid = {}, False
    try:
        require(args.private_state.resolve() == STATE.resolve(), "Service proof requires the fixed disposable private state")
        require(args.phase == "admin-snapshot" or (args.context_receipt is not None and args.provider_receipt is not None),
                "Title phase requires separate provider and context output paths")
        paths = [args.private_state, args.receipt, OPERATOR_STATE, CAPTURE]
        paths.extend(path for path in (args.context_receipt, args.provider_receipt) if path is not None)
        require(len({path.resolve() for path in paths}) == len(paths), "Service private state and evidence paths must be distinct")
        output_valid = True
        state = read_private(args.private_state)
        require(state.get("stage") == "setup_complete" and len(state.get("users", [])) == 2
                and state.get("admin_fixture", {}).get("stage") == "setup_complete"
                and state.get("bootstrap_fixture", {}).get("stage") == "setup_complete", "Prior native fixture phases are incomplete")
        if args.phase == "admin-snapshot":
            receipt["proof"] = "goal584-service-admin-native-snapshot"
            receipt.update(admin_snapshot(WebUI(), state))
        else:
            receipt.update(run(WebUI(), state, args, receipt))
        receipt.update(passed=True, task_config_restored=state["service_fixture"].get("task_config_restored") is True)
    except ProofError as error:
        receipt["failure"] = str(error)
    except BudgetAdminError as error:
        receipt["failure"] = "Native service budget client: " + error.code
    except Exception as error:
        receipt["failure"] = "Native service proof failed: " + type(error).__name__
    receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    receipt["task_config_restored"] = state.get("service_fixture", {}).get("task_config_restored") is True
    secrets = secret_values(state) + [os.environ.get("OWUI_BUDGET_GATEWAY_SECRET", "")]
    if state:
        secrets.append(read_private(OPERATOR_STATE).get("operator_token", ""))
    try:
        no_secrets(receipt, secrets)
    except ProofError:
        receipt = {"schema": 1, "proof": "goal584-native-direct-title-service", "passed": False,
                   "failure": "Credential-bearing service receipt suppressed"}
    if output_valid:
        write_private(args.receipt, receipt)
        # Retain actual bounded observations even if qualification failed.
        for target, observe in ((args.context_receipt, captured), (args.provider_receipt, provider)) if args.phase == "title" else ():
            try:
                if target is not None:
                    write_private(target, no_secrets(observe(), secrets))
            except Exception:
                pass
    print(json.dumps(receipt, indent=2, allow_nan=False))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
