#!/usr/bin/env python3
"""Provision/read back only the disposable stock WebUI + native budget fixture.

Run inside proxy with native sibling modules mounted at /proof. WebUI is fixed
to http://webui:8080 and LiteLLM to loopback:4000; neither redirects nor ambient
HTTP proxies are accepted. No inference is issued here. The browser owns chat
actions. Administrative cap updates here do not qualify a management GUI.

Private handoff schema 1: admin/users contain id,email,password,token;
native_keys contain user_id,model,key,key_alias. Credentials are saved only in
the private 0600 state, never in stdout or safe receipts.
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener
import uuid

from prove_native_budgets import (
    CALL_COST, COMPLETION_TOKENS, MODELS, PROMPT_TOKENS, NativeProof,
    NoRedirects, ProofError, amount, close_amount, require,
)
from prove_gateway_auth import read_private, write_private
from litellm_auth import TASK_HEADER, USER_ID_HEADER, assignment_alias, assignment_metadata


WEBUI_URL = "http://webui:8080"
PROXY_URL = "http://127.0.0.1:4000"
OPERATOR_STATE = Path("/proof-private/gateway-state.private.json")
TASK_FLAGS = (
    "ENABLE_TITLE_GENERATION", "ENABLE_TAGS_GENERATION", "ENABLE_FOLLOW_UP_GENERATION",
    "ENABLE_AUTOCOMPLETE_GENERATION", "ENABLE_SEARCH_QUERY_GENERATION",
    "ENABLE_RETRIEVAL_QUERY_GENERATION", "ENABLE_VOICE_MODE_PROMPT",
)
DELEGATION_TOOL_ID = "corporate_document_delegation"
DELEGATION_TOOL_SHA256 = "790de1a09eea5467ad7f87568f20c00099f7ca8c8ef1b946e55799d742c45fbe"
DELEGATION_PROFILES_SHA256 = "a263c69f1fae32c7eed7d1dbfcd7b3a720dc631e18717d17b543c4d8a0af5232"
DELEGATION_VALVES = {"DEFAULT_MODEL": "corporate-office-worker", "AVAILABLE_TOOL_IDS": "server:officecli",
    "EXCLUDED_TOOL_IDS": "", "MAX_ITERATIONS": 12, "MAX_PARALLEL_AGENTS": 1,
    "APPLY_INLET_FILTERS": True, "ENABLE_CONTEXT_COMPACTION": False, "LARGE_TOOL_RESULT_MODE": "raw",
    "ITERATION_NOTE_ROLE": "user", "DEBUG": False, "ENABLE_FILE_TOOLS": True,
    "ENABLE_KNOWLEDGE_TOOLS": True, "ENABLE_SKILLS_TOOLS": True}


class WebUI:
    def __init__(self):
        self.opener = build_opener(ProxyHandler({}), NoRedirects())
        self.server_second = None

    def ok(self, method: str, path: str, *, token: str | None = None,
           body: dict | None = None) -> dict:
        require(path.startswith("/") and not path.startswith("//"), "Invalid fixture API path")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        request = Request(WEBUI_URL + path, method=method, headers=headers,
                          data=None if body is None else json.dumps(body, allow_nan=False).encode("utf-8"))
        self.server_second = None  # Never reuse a prior response's clock.
        try:
            response = self.opener.open(request, timeout=20)
        except HTTPError as error:
            response = error
        except (URLError, TimeoutError, OSError):
            raise ProofError("WebUI fixture transport failed at " + path.split("?")[0]) from None
        with response:
            status = response.code
            raw = response.read(4 * 1024 * 1024 + 1)
            try:
                server_date = parsedate_to_datetime(response.headers.get("Date"))
                if server_date.tzinfo is not None:
                    self.server_second = int(server_date.timestamp())
            except (TypeError, ValueError, OverflowError, AttributeError):
                pass
        require(status == 200, "Unexpected WebUI HTTP " + str(status) + " at " + path.split("?")[0])
        require(len(raw) <= 4 * 1024 * 1024, "WebUI fixture response exceeded size bound")
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError):
            raise ProofError("WebUI fixture returned non-JSON") from None
        require(isinstance(data, dict), "WebUI fixture returned non-object JSON")
        return data

    def session(self, account: dict, role: str) -> dict:
        info = self.ok("GET", "/api/v1/auths/", token=account["token"])
        require(info.get("id") == account["id"] and info.get("role") == role,
                "Native WebUI account identity/role readback mismatch")
        return info

    def catalog(self, account: dict) -> dict:
        session = self.session(account, "user")
        payload = self.ok("GET", "/api/models?refresh=true", token=account["token"])
        data = payload.get("data")
        require(isinstance(data, list) and all(isinstance(model, dict) for model in data),
                "Native WebUI model catalog is malformed")
        ids = [model.get("id") for model in data]
        require(len(ids) == len(MODELS) and set(ids) == set(MODELS),
                "Ordinary WebUI user does not see exactly the configured native models")
        capabilities = [builtin_tool_capability({
            "id": model["id"], "meta": (model.get("info") or {}).get("meta") or {},
        }) for model in data]
        return {"model_ids": sorted(ids), "role": session["role"], "model_capabilities": capabilities}

    def model(self, admin_token: str, model_id: str) -> dict:
        record = self.ok("GET", "/api/v1/models/model?" + urlencode({"id": model_id}), token=admin_token)
        require(record.get("id") == model_id and record.get("write_access") is True,
                "Native model readback did not return the writable fixture model")
        return record

    def upload_delegated_source(self, token: str, raw: bytes) -> dict:
        """One finite multipart upload through native Files, never a storage write."""
        require(isinstance(raw, bytes) and 0 < len(raw) <= 128 * 1024, "Delegated source outside bound")
        boundary = "goal584-" + uuid.uuid4().hex
        body = ("--" + boundary + '\r\nContent-Disposition: form-data; name="file"; '
            'filename="goal584-delegated-source.docx"\r\nContent-Type: '
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document\r\n\r\n").encode()
        body += raw + ("\r\n--" + boundary + "--\r\n").encode()
        request = Request(WEBUI_URL + "/api/v1/files/?process=false", method="POST", data=body,
            headers={"Authorization": "Bearer " + token, "Content-Type": "multipart/form-data; boundary=" + boundary})
        with self.opener.open(request, timeout=20) as response:
            encoded = response.read(4 * 1024 * 1024 + 1)
            require(response.code == 200 and len(encoded) <= 4 * 1024 * 1024, "Delegated native upload failed")
        result = json.loads(encoded)
        require(isinstance(result, dict), "Delegated native File malformed")
        return result

    def file_content(self, token: str, file_id: str) -> bytes:
        require(str(uuid.UUID(file_id)) == file_id, "Delegated native File ID malformed")
        request = Request(WEBUI_URL + "/api/v1/files/" + file_id + "/content",
                          headers={"Authorization": "Bearer " + token})
        with self.opener.open(request, timeout=20) as response:
            raw = response.read(4 * 1024 * 1024 + 1)
            require(response.code == 200 and 0 < len(raw) <= 4 * 1024 * 1024, "Delegated native download failed")
        return raw


def builtin_tool_capability(record: dict) -> dict:
    meta = record.get("meta") or {}
    capabilities = meta.get("capabilities") or {}
    require(isinstance(capabilities, dict), "Native model capabilities are malformed")
    explicit = "builtin_tools" in capabilities
    value = capabilities.get("builtin_tools")
    require(not explicit or isinstance(value, bool), "Native built-in tool capability is ambiguous")
    return {"model_id": record["id"], "builtin_tools": value,
            "builtin_tools_effective": value if explicit else True,
            "builtin_tools_source": "explicit" if explicit else "native_default",
            "max_tokens": (record.get("params") or {}).get("max_tokens")}


def account_from_response(response: dict, email: str, password: str, role: str) -> dict:
    user_id, token = response.get("id"), response.get("token")
    try:
        canonical = str(uuid.UUID(user_id))
    except (ValueError, TypeError, AttributeError):
        raise ProofError("Native WebUI account did not return a UUID") from None
    require(user_id == canonical and response.get("role") == role
            and isinstance(token, str) and bool(token),
            "Native WebUI account did not return expected identity/role/session")
    return {"id": user_id, "email": email, "password": password, "token": token}


def native_admin_created_at(webui: WebUI, account: dict, controller: dict) -> int:
    record = webui.ok("GET", "/api/v1/users/" + account["id"], token=controller["token"])
    created = record.get("created_at")
    require(record.get("id") == account["id"] and record.get("role") == "admin"
            and type(created) is int and created > 0, "Native admin creation timestamp is unavailable")
    return created


def wait_after_controller_creation(webui: WebUI, controller: dict, *, timeout: float = 5.0) -> dict:
    """Wait on this WebUI server's Date, not the runner's wall clock.

    Native first-user ordering breaks second-resolution ties by UUID. Creating
    the regular owner only in a later server second removes that random tie.
    """
    deadline, created = time.monotonic() + timeout, None
    while True:
        actual = native_admin_created_at(webui, controller, controller)
        require(created is None or actual == created, "Native controller creation timestamp changed")
        created = actual
        second = webui.server_second
        require(type(second) is int and second > 0, "Native WebUI HTTP Date is unavailable")
        if second > created:
            return {"controller_created_at": created, "server_second_before_owner_create": second}
        remaining = deadline - time.monotonic()
        require(remaining > 0, "Native WebUI clock did not advance beyond controller creation")
        time.sleep(min(.1, remaining))


def read_admin_creation_order(webui: WebUI, state: dict) -> dict:
    controller, owner = state["role_probe_control"], state["admin"]
    expected = state.get("admin_creation_order")
    require(controller["id"] != owner["id"] and isinstance(expected, dict), "Fixture admin ordering evidence is missing")
    control_created = native_admin_created_at(webui, controller, controller)
    owner_created = native_admin_created_at(webui, owner, controller)
    second = expected.get("server_second_before_owner_create")
    require(type(second) is int and control_created == expected.get("controller_created_at")
            and control_created < second <= owner_created
            and ("owner_created_at" not in expected or owner_created == expected["owner_created_at"]),
            "Native controller must be strictly older than the regular admin")
    return {"controller_created_at": control_created, "owner_created_at": owner_created,
            "server_second_before_owner_create": second}


def native_client(state: dict | None = None) -> NativeProof:
    operator = read_private(OPERATOR_STATE).get("operator_token")
    require(isinstance(operator, str) and operator.startswith("sk-"), "Native operator state is missing")
    native = NativeProof(PROXY_URL, operator, 45, {})
    if state is not None:
        native.users = [account["id"] for account in state["users"]]
        native.started_at = datetime.fromisoformat(state["started_at_utc"]) - timedelta(minutes=1)
        native.keys = {(entry["user_id"], entry["model"]): {
            "token": entry["key"], "alias": entry["key_alias"],
        } for entry in state["native_keys"]}
    return native


def configure_webui(webui: WebUI, state: dict, gateway_secret: str) -> None:
    admin = state["admin"]["token"]
    expected_config = {
        "ENABLE_OPENAI_API": True,
        "OPENAI_API_BASE_URLS": ["http://proxy:4000/v1"],
        "OPENAI_API_KEYS": [gateway_secret],
        "OPENAI_API_CONFIGS": {"0": {
            "enable": True, "auth_type": "bearer", "model_ids": list(MODELS),
            "headers": {USER_ID_HEADER: "{{USER_ID}}", TASK_HEADER: "{{TASK}}"},
        }},
    }
    webui.ok("POST", "/openai/config/update", token=admin, body=expected_config)
    actual = webui.ok("GET", "/openai/config", token=admin)
    require(all(actual.get(key) == value for key, value in expected_config.items()),
            "Native WebUI connection configuration readback differs")
    tasks = webui.ok("GET", "/api/v1/tasks/config", token=admin)
    require(all(flag in tasks for flag in TASK_FLAGS), "Native task configuration fields are missing")
    tasks.update({flag: False for flag in TASK_FLAGS})
    webui.ok("POST", "/api/v1/tasks/config/update", token=admin, body=tasks)
    actual_tasks = webui.ok("GET", "/api/v1/tasks/config", token=admin)
    require(all(actual_tasks.get(flag) is False for flag in TASK_FLAGS),
            "Native auxiliary task disable flags were not persisted")
    for model in MODELS:
        created = webui.ok("POST", "/api/v1/models/create", token=admin, body={
            "id": model, "base_model_id": None, "name": model, "meta": {},
            "params": {"max_tokens": COMPLETION_TOKENS}, "is_active": True,
            "access_grants": [{"principal_type": "user", "principal_id": user["id"],
                               "permission": "read"} for user in state["users"]],
        })
        grants = created.get("access_grants")
        require(created.get("id") == model and created.get("params", {}).get("max_tokens") == COMPLETION_TOKENS
                and isinstance(grants, list) and len(grants) == len(state["users"])
                and {(grant.get("principal_type"), grant.get("principal_id"), grant.get("permission"))
                     for grant in grants} == {("user", user["id"], "read") for user in state["users"]},
                "Native model output cap/read grants did not match the fixture")


def setup(args, webui: WebUI) -> dict:
    require(not args.private_state.exists(), "Setup requires a new private WebUI state file")
    require(webui.ok("GET", "/api/version").get("version") == "0.12.2",
            "WebUI fixture is not the pinned 0.12.2")
    gateway = os.environ.get("OWUI_BUDGET_GATEWAY_SECRET")
    require(isinstance(gateway, str) and bool(gateway), "OWUI_BUDGET_GATEWAY_SECRET is required")
    native = native_client()
    native.schema()
    run_id = "goal584-webui-" + uuid.uuid4().hex[:12]
    state = {"schema": 1, "stage": "setup_in_progress", "run_id": run_id,
             "started_at_utc": datetime.now(timezone.utc).isoformat(), "users": [], "native_keys": []}
    email = "control-" + run_id + "@example.com"
    password = "Aa1!" + secrets.token_urlsafe(32)
    response = webui.ok("POST", "/api/v1/auths/signup", body={
        "name": "Proof primary control", "email": email, "password": password,
    })
    # Stock0.12.2 protects the primary admin from demotion. Keep that account
    # only as a fixture controller; the actual Tool owner is a normal admin.
    state["role_probe_control"] = account_from_response(response, email, password, "admin")
    write_private(args.private_state, state)
    state["admin_creation_order"] = wait_after_controller_creation(webui, state["role_probe_control"])
    write_private(args.private_state, state)
    email = "admin-" + run_id + "@example.com"
    password = "Aa1!" + secrets.token_urlsafe(32)
    response = webui.ok("POST", "/api/v1/auths/add", token=state["role_probe_control"]["token"], body={
        "name": "Proof administrator", "email": email, "password": password, "role": "admin",
    })
    state["admin"] = account_from_response(response, email, password, "admin")
    require(state["admin"]["id"] != state["role_probe_control"]["id"], "Fixture admins must be separate")
    write_private(args.private_state, state)
    state["admin_creation_order"] = read_admin_creation_order(webui, state)
    webui.session(state["admin"], "admin")
    write_private(args.private_state, state)
    for index in (1, 2):
        email = "user" + str(index) + "-" + run_id + "@example.com"
        password = "Aa1!" + secrets.token_urlsafe(32)
        response = webui.ok("POST", "/api/v1/auths/add", token=state["admin"]["token"], body={
            "name": "Proof user " + str(index), "email": email, "password": password, "role": "user",
        })
        account = account_from_response(response, email, password, "user")
        require(account["id"] not in {entry["id"] for entry in state["users"] + [state["admin"], state["role_probe_control"]]},
                "Native WebUI generated duplicate account IDs")
        webui.session(account, "user")
        state["users"].append(account)
        write_private(args.private_state, state)
        native.ok("POST", "/user/new", body={
            "user_id": account["id"], "user_role": "internal_user", "models": list(MODELS),
            "max_budget": 0.80, "budget_duration": "30d", "auto_create_key": False,
            "send_invite_email": False,
        })
        for model in MODELS:
            alias = assignment_alias(account["id"], model)
            generated = native.ok("POST", "/key/generate", body={
                "user_id": account["id"], "models": [model], "key_alias": alias,
                "metadata": assignment_metadata(model), "max_budget": 0.40,
                "budget_duration": "30d", "allowed_routes": ["llm_api_routes"],
            })
            key = generated.get("key")
            require(isinstance(key, str) and key.startswith("sk-"), "Native assignment key was not returned")
            state["native_keys"].append({"user_id": account["id"], "model": model,
                                         "key": key, "key_alias": alias})
            write_private(args.private_state, state)
    configure_webui(webui, state, gateway)
    state["stage"] = "setup_complete"
    write_private(args.private_state, state)
    return state


def snapshot(webui: WebUI, state: dict) -> dict:
    require(state.get("stage") == "setup_complete" and len(state.get("users", [])) == 2
            and len(state.get("native_keys", [])) == 4, "Private WebUI fixture setup is incomplete")
    require(webui.ok("GET", "/api/version").get("version") == "0.12.2", "WebUI fixture version changed")
    admin_session = webui.session(state["admin"], "admin")
    admin_order = read_admin_creation_order(webui, state)
    require(admin_order == state["admin_creation_order"], "Fixture admin ordering changed")
    catalogs = {user["id"]: webui.catalog(user) for user in state["users"]}
    webui_models = [builtin_tool_capability(webui.model(state["admin"]["token"], model)) for model in MODELS]
    native = native_client(state)

    def consistent_readback():
        from litellm.proxy.utils import hash_token

        observed = {"users": [], "keys": [], "positive_spend_logs": [],
                    "observed_at_utc": datetime.now(timezone.utc).isoformat()}
        for user in state["users"]:
            user_id = user["id"]
            rows = native.logs(user_id)
            key_infos = {model: native.key_info(user_id, model) for model in MODELS}
            by_hash = {hash_token(native.keys[user_id, model]["token"]): model for model in MODELS}
            costs = {model: Decimal("0") for model in MODELS}
            seen = set()
            for row in rows:
                cost = amount(row.get("spend", 0))
                if cost == 0:
                    continue
                require(cost > 0 and close_amount(cost, CALL_COST), "Native WebUI spend differs from fixture pricing")
                model = by_hash.get(row.get("api_key"))
                require(model in MODELS and row.get("model_group") == model,
                        "WebUI spend is attributed to an unexpected native key/model")
                require(row.get("prompt_tokens") == PROMPT_TOKENS
                        and row.get("completion_tokens") == COMPLETION_TOKENS and row.get("total_tokens") == 15,
                        "Native WebUI persisted usage differs from deterministic provider")
                request_id = row.get("request_id")
                suffix = request_id.removeprefix("chatcmpl-goal584-") if isinstance(request_id, str) else ""
                require(isinstance(request_id, str) and request_id.startswith("chatcmpl-goal584-")
                        and len(suffix) == 32 and all(char in "0123456789abcdef" for char in suffix)
                        and request_id not in seen, "Native WebUI provider request ID is missing or duplicated")
                seen.add(request_id)
                costs[model] += cost
                observed["positive_spend_logs"].append({
                    "request_id": request_id, "user": user_id, "model_group": row["model_group"],
                    "spend_usd": str(cost), "prompt_tokens": row["prompt_tokens"],
                    "completion_tokens": row["completion_tokens"], "total_tokens": row["total_tokens"],
                })
            info = native.user_info(user_id)
            require(info.get("user_id") == user_id and info.get("user_role") == "internal_user"
                    and not info.get("teams") and len(info.get("keys", [])) == 2,
                    "Native user owner/role/key scope differs from WebUI account")
            if not close_amount(info.get("spend"), sum(costs.values(), Decimal("0"))):
                return None
            observed["users"].append({
                "user_id": user_id, "spend_usd": str(amount(info["spend"])),
                "max_budget_usd": str(amount(info.get("max_budget"))), "native_role": info["user_role"],
                "webui_role": catalogs[user_id]["role"], "model_ids": catalogs[user_id]["model_ids"],
                "model_capabilities": catalogs[user_id]["model_capabilities"],
                "budget_duration": info.get("budget_duration"), "budget_reset_at": info.get("budget_reset_at"),
            })
            for model, key_info in key_infos.items():
                metadata = key_info.get("metadata")
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)
                require(isinstance(metadata, dict) and all(metadata.get(key) == value
                        for key, value in assignment_metadata(model).items()), "Native assignment metadata changed")
                require(key_info.get("key_alias") == assignment_alias(user_id, model),
                        "Native assignment alias changed")
                if not close_amount(key_info.get("spend"), costs[model]):
                    return None
                observed["keys"].append({
                    "user_id": user_id, "model": model, "key_alias": key_info["key_alias"],
                    "spend_usd": str(amount(key_info["spend"])),
                    "max_budget_usd": str(amount(key_info.get("max_budget"))),
                    "budget_duration": key_info["budget_duration"], "budget_reset_at": key_info["budget_reset_at"],
                })
        return observed

    result = native.poll("WebUI/native spend reconciliation", consistent_readback)
    result.update(webui_admin_role=admin_session["role"], task_generation_disabled=True,
                  primary_control_strictly_earlier=True,
                  primary_admin_creation_order=admin_order,
                  webui_models=webui_models,
                  native_catalog_owner="OpenWebUI connection model_ids and native model read grants")
    actual_tasks = webui.ok("GET", "/api/v1/tasks/config", token=state["admin"]["token"])
    require(all(actual_tasks.get(flag) is False for flag in TASK_FLAGS), "Native task disable configuration changed")
    return result


def plainchat(webui: WebUI, state: dict) -> list[dict]:
    """Scope this fixture to plain chat through native model metadata, not budget changes."""
    admin = state["admin"]["token"]
    preserved = []

    def grants(record):
        return {(grant["principal_type"], grant["principal_id"], grant["permission"])
                for grant in record["access_grants"]}

    fields = ("id", "base_model_id", "name", "meta", "params", "access_grants", "is_active")
    for model in MODELS:
        before = webui.model(admin, model)
        require(all(field in before for field in fields), "Native editable model fields are missing")
        body = {field: copy.deepcopy(before[field]) for field in fields}
        capabilities = body["meta"].get("capabilities")
        require(capabilities is None or isinstance(capabilities, dict), "Native model capabilities are malformed")
        body["meta"]["capabilities"] = {**(capabilities or {}), "builtin_tools": False}
        # The exact native update route reads ModelForm.id from JSON, not a query parameter.
        webui.ok("POST", "/api/v1/models/model/update", token=admin, body=body)
        after = webui.model(admin, model)
        require(all(after.get(field) == body[field] for field in fields if field != "access_grants")
                and grants(after) == grants(before),
                "Native plain-chat update changed fields beyond built-in tool capability")
        capability = builtin_tool_capability(after)
        require(capability["builtin_tools"] is False, "Native plain-chat capability update did not persist")
        preserved.append({**capability, "other_model_fields_and_grants_preserved": True})
    # Refresh both ordinary users through the native model catalog after model updates.
    for user in state["users"]:
        catalog = webui.catalog(user)
        require(all(model["builtin_tools"] is False for model in catalog["model_capabilities"]),
                "Ordinary-user native catalog did not reflect plain-chat model capabilities")
    return preserved


def raise_caps(state: dict) -> None:
    native = native_client(state)
    user_id = state["users"][0]["id"]
    native.ok("POST", "/user/update", body={"user_id": user_id, "max_budget": 1.20})
    key = next(entry for entry in state["native_keys"] if entry["user_id"] == user_id and entry["model"] == MODELS[0])
    native.ok("POST", "/key/update", body={"key": key["key"], "max_budget": 0.80})

    def changed():
        return True if close_amount(native.user_info(user_id).get("max_budget"), Decimal("1.20")) \
            and close_amount(native.key_info(user_id, MODELS[0]).get("max_budget"), Decimal("0.80")) \
            and close_amount(native.key_info(user_id, MODELS[1]).get("max_budget"), Decimal("0.40")) else None
    native.poll("native administrative cap update readback", changed)


def office_setup(webui: WebUI, common: dict, path: Path) -> dict:
    """Finite stand setup only; keep common handoff and existing model bodies intact.

    The host supplies the mounted accepted Filter and actual synthetic aliases.
    Every POST has a private pre-mutation journal; failed partial setup is neither
    retried nor repaired. No inference, task configuration or service payer setup.
    """
    import asyncio
    from dataclasses import asdict
    from aiohttp import ClientSession
    from employee_budget_admin_client import BudgetAdminClient
    from employee_budget_admin_contract import BudgetAdminError
    from prove_office_compatibility import VALVES
    from prove_service_tasks import response
    from provision_cost_display import FILTER_ID, add_model_meta, grant_set, source_hash

    require(common.get("stage") == "setup_complete" and not path.exists(), "Office setup requires a fresh separate handoff")
    admin, primary, target = common["admin"], "gpt-5.4-mini", "gpt-6-luna"
    auto_id = "officecli_auto_attach_filter"
    webui.session(admin, "admin")
    gateway = os.environ.get("OWUI_BUDGET_GATEWAY_SECRET", "")
    require(isinstance(gateway, str) and bool(gateway) and not any(c.isspace() for c in gateway), "Office gateway prerequisite missing")
    with Path("/proof/officecli_auto_attach_filter.py").open("rb") as handle: source = handle.read(128 * 1024 + 1).decode("utf8")
    require(source_hash(source) == "0916704e50c29fd41c949a87b4dae9ecf4d3a90e72b213355e725f680acdcdd7", "Office Filter source prerequisite differs")
    cost = webui.ok("GET", "/api/v1/functions/id/" + FILTER_ID, token=admin["token"])
    require(cost.get("is_active") is True and cost.get("type") == "filter"
            and source_hash(cost.get("content", "")) == source_hash(Path("/proof/budgets/cost_filter.py").read_text(encoding="utf8")),
            "Office budget Filter prerequisite differs")
    require(webui.ok("GET", "/api/v1/functions/id/" + FILTER_ID + "/valves", token=admin["token"]).get("ledger_base_url")
            == "http://proxy:4000", "Office budget Filter gateway prerequisite differs")
    native = native_client()
    info = native.ok("GET", "/model/info").get("data")
    require(isinstance(info, list) and all(isinstance(row, dict) for row in info), "Office native alias prerequisite malformed")
    for alias in (primary, target):
        rows = [row for row in info if row.get("model_name") == alias]
        require(len(rows) == 1, "Office native alias missing or duplicated")
        params, rates = rows[0].get("litellm_params", {}), rows[0].get("model_info", {})
        require(params.get("api_base") == "http://provider:8000/v1" and rates.get("mode") == "responses"
                and isinstance(params.get("model"), str) and params["model"].startswith("openai/goal584-fake-")
                and (alias != primary or params["model"] == "openai/goal584-fake-office"
                    and close_amount(rates.get("input_cost_per_token"), Decimal(".01"))
                    and close_amount(rates.get("output_cost_per_token"), Decimal(".02"))), "Office native alias route/pricing differs")
    connections = webui.ok("GET", "/openai/config", token=admin["token"])
    urls, keys, configs = (connections[k] for k in ("OPENAI_API_BASE_URLS", "OPENAI_API_KEYS", "OPENAI_API_CONFIGS"))
    require(connections.get("ENABLE_OPENAI_API") is True and isinstance(urls, list) and isinstance(keys, list)
            and len(urls) == len(keys) > 0 and all(isinstance(value, str) for value in [*urls, *keys])
            and isinstance(configs, dict) and set(configs) == {str(i) for i in range(len(urls))}
            and all(isinstance(value, dict) for value in configs.values()), "Office connection remap requires explicit native indices")
    actors = [admin, *common["users"]]
    def catalogs():
        result = {}
        for account in actors:
            webui.session(account, "admin" if account is admin else "user")
            rows = webui.ok("GET", "/api/models?refresh=true", token=account["token"]).get("data")
            require(isinstance(rows, list) and all(isinstance(r, dict) and isinstance(r.get("id"), str) for r in rows)
                    and len({r["id"] for r in rows}) == len(rows), "Office old native catalog malformed")
            result[account["id"]] = rows
        return result
    old_catalogs = catalogs()
    for model in (primary, target):
        require(response(webui, "GET", "/api/v1/models/model?" + urlencode({"id": model}), admin["token"])[0] == 404,
                "Office Workspace Model already exists or absence unavailable")
    servers = webui.ok("GET", "/api/v1/configs/tool_servers", token=admin["token"])
    require(isinstance(servers.get("TOOL_SERVER_CONNECTIONS"), list)
            and all((s.get("info") or {}).get("id") != "officecli" for s in servers["TOOL_SERVER_CONNECTIONS"]), "Office Tool Server already exists")
    status, functions = response(webui, "GET", "/api/v1/functions/export?include_valves=true", admin["token"])
    require(status == 200 and isinstance(functions, list) and all(isinstance(f, dict) and f.get("id") != auto_id for f in functions),
            "Office Filter already exists or native export unavailable")
    tasks = webui.ok("GET", "/api/v1/tasks/config", token=admin["token"])
    chat_config = webui.ok("GET", "/api/v1/chats/config", token=admin["token"])
    require(chat_config.get("ENABLE_CONTEXT_COMPACTION") is False, "Office native context compaction must be disabled")
    handoff = {"schema": 1, "stage": "office_setup_in_progress", "admin": copy.deepcopy(admin), "users": [], "native_keys": [],
        "office_setup": {"journal": [], "source_sha256": source_hash(source), "before": {"connections": connections,
            "catalogs": old_catalogs, "tool_servers": servers, "functions": functions, "tasks": tasks, "chat_config": chat_config, "native_models": info}}}
    def journal(stage, body=None):
        webui.session(admin, "admin")
        entry = {"stage": stage, "body": copy.deepcopy(body), "returned": False}
        handoff["office_setup"]["journal"].append(entry)
        write_private(path, handoff)
        return entry
    def post(route, body=None):
        entry = journal(route, body)
        result = webui.ok("POST", route, token=admin["token"], body=body)
        entry.update(returned=True, response=result)
        write_private(path, handoff)
        return result
    email, password = "office-" + uuid.uuid4().hex + "@example.com", "Aa1!" + secrets.token_urlsafe(32)
    actor = account_from_response(post("/api/v1/auths/add", {"name": "Office proof employee", "email": email,
        "password": password, "role": "user"}), email, password, "user")
    require(actor["id"] not in {a["id"] for a in actors}, "Office actor collided with an existing fixture account")
    handoff["users"] = [actor]
    webui.session(actor, "user")
    write_private(path, handoff)
    requested = copy.deepcopy(connections)
    requested.update(OPENAI_API_BASE_URLS=["http://proxy:4000/v1", *urls], OPENAI_API_KEYS=[gateway, *keys],
        OPENAI_API_CONFIGS={"0": {"enable": True, "auth_type": "bearer", "api_type": "responses", "model_ids": [primary, target],
            "headers": {USER_ID_HEADER: "{{USER_ID}}", TASK_HEADER: "{{TASK}}"}},
            **{str(int(k) + 1): copy.deepcopy(v) for k, v in configs.items()}})
    post("/openai/config/update", requested)
    require(webui.ok("GET", "/openai/config", token=admin["token"]) == requested, "Office native connection remap readback differs")
    models = {}
    for model, params in ((primary, {"function_calling": "native", "max_tokens": 1024,
            "custom_params": {"parallel_tool_calls": False, "store": False,
                "include": ["reasoning.encrypted_content"]}}),
            (target, {})):
        body = {"id": model, "name": model, "base_model_id": None, "is_active": True, "params": params,
            "meta": {"capabilities": {"builtin_tools": False}},
            "access_grants": [{"principal_type": "user", "principal_id": actor["id"], "permission": "read"}]}
        post("/api/v1/models/create", body)
        record = webui.model(admin["token"], model)
        require(all(record.get(k) == body[k] for k in ("id", "base_model_id", "params", "is_active"))
                and record.get("user_id") == admin["id"] and record.get("name") == model
                and grant_set(record) == grant_set(body) and len(record["access_grants"]) == 1
                and record.get("meta", {}).get("capabilities") == body["meta"]["capabilities"], "Office native model body differs")
        models[model] = record
        if model == primary:
            entry = journal("attach-existing-budget-filter", {"model": model, "filter": FILTER_ID})
            models[model] = add_model_meta(webui, handoff, model, "filterIds", FILTER_ID)
            entry["returned"] = True
        write_private(path, handoff)
    server = {"url": "http://office:8080", "path": "openapi.json", "type": "openapi", "auth_type": "session", "key": "",
        "forward_cookies": False, "headers": {"X-OpenWebUI-Chat-Id": "{{CHAT_ID}}", "X-OpenWebUI-Message-Id": "{{MESSAGE_ID}}"},
        "info": {"id": "officecli", "name": "OfficeCLI"}, "config": {"enable": True, "function_name_filter_list": "",
            "access_grants": [{"principal_type": "user", "principal_id": "*", "permission": "read"}]}}
    wanted_servers = {"TOOL_SERVER_CONNECTIONS": [*servers["TOOL_SERVER_CONNECTIONS"], server]}
    post("/api/v1/configs/tool_servers", wanted_servers)
    actual_servers = webui.ok("GET", "/api/v1/configs/tool_servers", token=admin["token"])
    require(actual_servers == wanted_servers, "Office native Session Tool Server readback differs")
    schema = post("/api/v1/configs/tool_servers/verify", server)
    require(all(p in schema.get("paths", {}) for p in ("/v1/officecli/documents/export-answer", "/v1/officecli/render")),
            "Office native schema discovery incomplete")
    post("/api/v1/functions/create", {"id": auto_id, "name": "OfficeCLI Auto Attach", "content": source, "meta": {}})
    function_path = "/api/v1/functions/id/" + auto_id
    defaults = webui.ok("GET", function_path + "/valves", token=admin["token"])
    wanted_valves = {**defaults, **VALVES}
    post(function_path + "/valves/update", wanted_valves)
    post(function_path + "/toggle")
    post(function_path + "/toggle/global")
    function = webui.ok("GET", function_path, token=admin["token"])
    actual_valves = webui.ok("GET", function_path + "/valves", token=admin["token"])
    require(function.get("id") == auto_id and function.get("user_id") == admin["id"] and function.get("type") == "filter"
            and function.get("is_active") is True and function.get("is_global") is True
            and source_hash(function.get("content", "")) == source_hash(source) and actual_valves == wanted_valves,
            "Office native Filter source/Valves/scope readback differs")
    after_catalogs = catalogs()
    for uid, rows in old_catalogs.items():
        after = {r["id"]: r for r in after_catalogs[uid]}
        require({r["id"] for r in rows} <= set(after), "Office setup removed an existing visible model")
        for row in rows:
            current = after[row["id"]]
            require(current.get("info") == row.get("info"), "Office setup changed an existing native model body")
            if row.get("owned_by") == "openai" and not row.get("pipe"):
                old_idx, new_idx = row.get("urlIdx"), current.get("urlIdx")
                require(type(old_idx) is int and 0 <= old_idx < len(urls) and new_idx == old_idx + 1
                        and (urls[old_idx], keys[old_idx], configs[str(old_idx)]) == (requested["OPENAI_API_BASE_URLS"][new_idx],
                            requested["OPENAI_API_KEYS"][new_idx], requested["OPENAI_API_CONFIGS"][str(new_idx)]), "Office old logical connection changed")
    status, tools = response(webui, "GET", "/api/v1/tools/", actor["token"])
    require(status == 200 and isinstance(tools, list) and sum(t.get("id") == "server:officecli" for t in tools) == 1,
            "Office actor cannot discover the native Session Tool Server")
    actor_catalog = webui.ok("GET", "/api/models?refresh=true", token=actor["token"]).get("data")
    require(isinstance(actor_catalog, list) and all(sum(r.get("id") == m and r.get("urlIdx") == 0 and r.get("owned_by") == "openai"
        and not r.get("pipe") for r in actor_catalog) == 1 for m in (primary, target)), "Office actor primary/target native route differs")
    async def initialize():
        # Synthetic fixture cap must cover all 14 tools + 1024-token native
        # reservation. Adequacy still requires the real estimator rehearsal.
        async def guard():
            webui.session(actor, "user")
            require(webui.model(admin["token"], primary) == models[primary], "Office primary changed before budget initialization")
            journal("native-budget-initialize-post", {"user_id": actor["id"], "models": [primary], "total_cap": "1000", "key_cap": "1000"})
        async with ClientSession(trust_env=False) as session:
            client = BudgetAdminClient(session, PROXY_URL, read_private(OPERATOR_STATE)["operator_token"])
            created = await client.initialize_employee(actor["id"], ((primary, Decimal(1000)),), Decimal(1000), gateway, before_write=guard)
            require(await client.read_employee(actor["id"], (primary,)) == created, "Office native budget final readback changed")
        return json.loads(json.dumps(asdict(created), default=str))
    try: budget = asyncio.run(initialize())
    except BudgetAdminError as error: raise ProofError("Office budget initialization failed: " + error.code) from None
    for entry in handoff["office_setup"]["journal"]:
        if entry["stage"] == "native-budget-initialize-post": entry["returned"] = True
    status, after_functions = response(webui, "GET", "/api/v1/functions/export?include_valves=true", admin["token"])
    require(status == 200 and isinstance(after_functions, list) and len(after_functions) == len(functions) + 1
            and {f["id"]: f for f in after_functions if f.get("id") != auto_id} == {f["id"]: f for f in functions}
            and webui.ok("GET", "/api/v1/tasks/config", token=admin["token"]) == tasks
            and webui.ok("GET", "/api/v1/chats/config", token=admin["token"]) == chat_config, "Office setup changed unrelated Functions/tasks/chat config")
    handoff["office_setup"].update(models=models, connections=requested, tool_servers=actual_servers, function=function,
        valves=actual_valves, openapi=schema, actor_tools=tools, actor_catalog=actor_catalog, after_catalogs=after_catalogs, budget=budget)
    handoff["stage"] = "setup_complete"
    write_private(path, handoff)
    return {"office_setup": {"status": "readback_ready", "native_office_accepted": False, "inference_issued": False,
        "actor_id": actor["id"], "source_sha256": source_hash(source), "handoff_sha256": sha256(path.read_bytes()).hexdigest()}}


def delegated_source_docx() -> bytes:
    """Finite synthetic data; native Files/Office own persistence and editing."""
    from io import BytesIO
    from zipfile import ZipFile, ZipInfo
    parts = {
        '[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/></Types>',
        '_rels/.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
        'word/document.xml': '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body>'
            '<w:p><w:r><w:t>Employee: {{employee}}</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>Case: {{case}}</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>FIXED CLAUSE: preserve this sentence.</w:t></w:r></w:p>'
            '<w:tbl><w:tblPr/><w:tblGrid><w:gridCol w:w="4000"/></w:tblGrid>'
            '<w:tr><w:tc><w:tcPr/><w:p><w:r><w:t>FIXED TABLE</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
            '<w:sectPr><w:footerReference w:type="default" r:id="rIdFooter"/></w:sectPr></w:body></w:document>',
        'word/_rels/document.xml.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rIdFooter" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/></Relationships>',
        'word/footer1.xml': '<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:p><w:r><w:t>FIXED FOOTER: GOAL584 synthetic only.</w:t></w:r></w:p></w:ftr>',
    }
    stream = BytesIO()
    with ZipFile(stream, 'w') as package:
        for name, content in parts.items():
            package.writestr(ZipInfo(name, (2020, 1, 1, 0, 0, 0)), content.encode('utf-8'))
    return stream.getvalue()


def delegated_skill_content(file_id: str, source_sha256: str) -> str:
    require(str(uuid.UUID(file_id)) == file_id and len(source_sha256) == 64
            and all(c in '0123456789abcdef' for c in source_sha256), 'Delegated source binding malformed')
    return ("# GOAL584 synthetic two-field Office copy\n\n"
        "This is the COMPLETE synthetic template instruction. No other fields or business facts exist.\n"
        f"Native source File ID: {file_id}\nNative source SHA256: {source_sha256}\n\n"
        "Required field map (each occurs exactly once):\n"
        "- employee: paragraph with exact text Employee: {{employee}}. Replace with Employee: Ada Example.\n"
        "- case: paragraph with exact text Case: {{case}}. Replace with Case: G584-2026.\n\n"
        "Load the installed word guide once. Inspect the actual original and discover its real paragraph paths. "
        "Edit a COPY with apply_office_batch; never recreate or overwrite the source. "
        "Preserve FIXED CLAUSE: preserve this sentence., the FIXED TABLE and its structure, and "
        "FIXED FOOTER: GOAL584 synthetic only. No omitted/repeated fields or substitutions are allowed. "
        "Inspect the result: both exact values, fixed text/table/footer, no placeholders. "
        "Render the actual result_file_id as docx/grid2 and assess the actual image. "
        "Return that native result_file_id/download_url and honest checks. No binary/base64 belongs in this Skill.\n")


def office_delegation_setup(webui, state, path, *, tool_source: Path, profiles_source: Path) -> dict:
    """Explicit synthetic phase; no inference or replacement model-history owner."""
    import asyncio
    from dataclasses import asdict
    from aiohttp import ClientSession
    from employee_budget_admin_client import BudgetAdminClient
    from provision_cost_display import FILTER_ID, add_model_meta, grant_set
    from prove_service_tasks import response

    require(state.get('stage') == 'setup_complete' and state.get('office_setup')
            and 'office_delegation_setup' not in state, 'Delegated setup requires fresh Office state')
    require(0 < tool_source.stat().st_size <= 4 * 1024 * 1024
            and 0 < profiles_source.stat().st_size <= 128 * 1024, 'Delegated source input exceeds existing bounds')
    tool = tool_source.read_bytes()
    raw_profiles = profiles_source.read_bytes().replace(b'\r\n', b'\n')
    require(sha256(tool).hexdigest() == DELEGATION_TOOL_SHA256
            and sha256(raw_profiles).hexdigest() == DELEGATION_PROFILES_SHA256, 'Delegated Tool/profile source differs')
    profiles = {v['id']: v for v in json.loads(raw_profiles)}
    parent, worker = copy.deepcopy(profiles['corporate-documents']), copy.deepcopy(profiles['corporate-office-worker'])
    parent['base_model_id'] = 'gpt-6.1-sol'
    require(parent['params']['max_tokens'] == 12000 and worker['params']['max_tokens'] == 6000
            and worker['base_model_id'] == 'gpt-6.1-terra', 'Delegated profile parameters differ')
    admin = state['admin']; webui.session(admin, 'admin')
    native = native_client(); info = native.ok('GET', '/model/info')['data']
    for alias, wire, deployment, output, rate_in, rate_out in (
            ('gpt-6.1-sol', 'goal584-fake-delegated-parent', 'goal584-delegated-parent', 12000, '.01', '.02'),
            ('gpt-6.1-terra', 'goal584-fake-delegated-worker', 'goal584-delegated-worker', 6000, '.001', '.002')):
        rows = [r for r in info if r.get('model_name') == alias]
        require(len(rows) == 1, 'Delegated native alias missing/ambiguous')
        params, desc = rows[0]['litellm_params'], rows[0]['model_info']
        require(params.get('model') == 'openai/' + wire and params.get('api_base') == 'http://provider:8000/v1'
                and desc.get('id') == deployment and desc.get('mode') == 'responses'
                and desc.get('supports_native_streaming') is False and desc.get('max_input_tokens') == 32768
                and desc.get('max_output_tokens') == output and desc.get('max_tokens') == 32768 + output
                and desc.get('supports_reasoning') is True and desc.get('supports_function_calling') is True
                and close_amount(desc.get('input_cost_per_token'), Decimal(rate_in))
                and close_amount(desc.get('output_cost_per_token'), Decimal(rate_out)), 'Delegated native descriptor differs')
    connections = webui.ok('GET', '/openai/config', token=admin['token'])
    requested = copy.deepcopy(connections); config = requested['OPENAI_API_CONFIGS']['0']
    require(requested['OPENAI_API_BASE_URLS'][0] == 'http://proxy:4000/v1'
            and config['api_type'] == 'responses' and config['auth_type'] == 'bearer'
            and not set(('gpt-6.1-sol', 'gpt-6.1-terra')) & set(config['model_ids']), 'Delegated managed connection differs')
    gateway = os.environ.get('OWUI_BUDGET_GATEWAY_SECRET', '')
    require(gateway and gateway == requested['OPENAI_API_KEYS'][0], 'Delegated gateway authority differs')
    status, tools = response(webui, 'GET', '/api/v1/tools/', admin['token'])
    require(status == 200 and isinstance(tools, list) and all(t.get('id') != DELEGATION_TOOL_ID for t in tools),
            'Delegated Tool already installed/unavailable')
    for profile in (parent, worker):
        status, _ = response(webui, 'GET', '/api/v1/models/model?' + urlencode({'id': profile['id']}), admin['token'])
        require(status in (401, 404), 'Delegated Workspace Model already exists')
    current = copy.deepcopy(state)
    selected = {'stage': 'preparing', 'journal': [], 'tool_source_sha256': DELEGATION_TOOL_SHA256,
                'profiles_source_sha256': DELEGATION_PROFILES_SHA256}
    current['office_delegation_setup'] = selected
    write_private(path, current)
    def before(stage, body=None):
        selected['journal'].append({'stage': stage, 'body': copy.deepcopy(body), 'returned': False})
        write_private(path, current)
    def post(route, body):
        webui.session(admin, 'admin'); before(route, body)
        result = webui.ok('POST', route, token=admin['token'], body=body)
        selected['journal'][-1].update(returned=True, response=copy.deepcopy(result)); write_private(path, current)
        return result
    email, password = 'delegated-' + uuid.uuid4().hex + '@example.invalid', 'Aa1!' + secrets.token_urlsafe(32)
    actor = account_from_response(post('/api/v1/auths/add', {'name': 'Synthetic delegated employee',
        'email': email, 'password': password, 'role': 'user'}), email, password, 'user')
    require(actor['id'] not in {u['id'] for u in [admin, *state['users']]}, 'Delegated actor collision')
    selected['actor'] = actor
    write_private(path, current)
    config['model_ids'].extend(('gpt-6.1-sol', 'gpt-6.1-terra'))
    post('/openai/config/update', requested)
    require(webui.ok('GET', '/openai/config', token=admin['token']) == requested, 'Delegated connection readback differs')
    selected['models'] = {}
    for profile in (parent, worker):
        profile['access_grants'] = [{'principal_type': 'user', 'principal_id': actor['id'], 'permission': 'read'}]
        post('/api/v1/models/create', profile)
        saved = webui.model(admin['token'], profile['id'])
        require(all(saved.get(k) == profile[k] for k in ('id', 'base_model_id', 'params', 'meta', 'is_active'))
                and grant_set(saved) == grant_set(profile), 'Delegated native profile differs')
        before('attach-mandatory-budget-filter', {'model': profile['id']})
        selected['models'][profile['id']] = add_model_meta(webui, current, profile['id'], 'filterIds', FILTER_ID)
        selected['journal'][-1]['returned'] = True
    post('/api/v1/tools/create', {'id': DELEGATION_TOOL_ID, 'name': 'Synthetic corporate delegation',
        'content': tool.decode('utf-8'), 'meta': {}, 'access_grants': [
            {'principal_type': 'user', 'principal_id': actor['id'], 'permission': 'read'}]})
    route = '/api/v1/tools/id/' + DELEGATION_TOOL_ID
    defaults = webui.ok('GET', route + '/valves', token=admin['token'])
    valves = {k: False if k.startswith('ENABLE_') else v for k, v in defaults.items()}; valves.update(DELEGATION_VALVES)
    post(route + '/valves/update', valves)
    actual = webui.ok('GET', route, token=admin['token'])
    require(sha256(actual['content'].encode()).hexdigest() == DELEGATION_TOOL_SHA256
            and webui.ok('GET', route + '/valves', token=admin['token']) == valves, 'Delegated Tool source/Valves differ')
    source = delegated_source_docx(); before('upload-native-synthetic-source')
    file = webui.upload_delegated_source(actor['token'], source)
    selected['source_file'] = file; write_private(path, current)
    require(file.get('user_id') == actor['id'] and webui.file_content(actor['token'], file['id']) == source,
            'Delegated native source owner/bytes differ')
    selected['journal'][-1]['returned'] = True
    body = {'id': 'goal584-delegated-' + uuid.uuid4().hex, 'name': 'GOAL584 synthetic two-field template',
        'description': 'Complete synthetic two-field Office template; native source and fixed content.',
        'content': delegated_skill_content(file['id'], sha256(source).hexdigest()), 'is_active': True,
        'access_grants': [{'principal_type': 'user', 'principal_id': actor['id'], 'permission': 'read'}]}
    skill = post('/api/v1/skills/create', body)
    readable = webui.ok('GET', '/api/v1/skills/id/' + skill['id'], token=actor['token'])
    require(readable.get('content') == body['content'] and readable.get('version_id') == skill.get('version_id')
            and bool(readable.get('version_id')) and readable.get('is_active') is True, 'Delegated complete Skill/version differs')
    selected.update(skill=readable, source_sha256=sha256(source).hexdigest(), tool_valves=valves)
    async def initialize():
        async def guard():
            webui.session(admin, 'admin')
            require(webui.ok('GET', '/openai/config', token=admin['token']) == requested, 'Delegated connection changed before budget write')
            require(native.ok('GET', '/model/info')['data'] == info
                    and all(webui.model(admin['token'], name) == saved for name, saved in selected['models'].items()),
                    'Delegated native model changed before budget write')
            before('initialize-two-personal-assignments')
        async with ClientSession(trust_env=False) as session:
            client = BudgetAdminClient(session, PROXY_URL, read_private(OPERATOR_STATE)['operator_token'])
            result = await client.initialize_employee(actor['id'], (('gpt-6.1-sol', Decimal(1000)),
                ('gpt-6.1-terra', Decimal(1000))), Decimal(2000), gateway, before_write=guard)
            require(await client.read_employee(actor['id'], ('gpt-6.1-sol', 'gpt-6.1-terra')) == result,
                    'Delegated two-assignment readback differs')
            return json.loads(json.dumps(asdict(result), default=str))
    selected['budget'] = asyncio.run(initialize())
    for entry in selected['journal']:
        if entry['stage'] == 'initialize-two-personal-assignments': entry['returned'] = True
    selected['stage'] = 'readback_ready'; write_private(path, current)
    return {'office_delegation_setup': {'status': 'readback_ready', 'inference_issued': False,
        'native_office_accepted': False, 'tool_source_sha256': DELEGATION_TOOL_SHA256,
        'source_sha256': selected['source_sha256'], 'skill_content_sha256': sha256(readable['content'].encode()).hexdigest(),
        'handoff_sha256': sha256(path.read_bytes()).hexdigest()}}


def office_service_readback(webui: WebUI, state: dict, path: Path, phase: str) -> dict:
    """Read prepared native configuration; no inference or configuration writes.

    Full observations stay in the existing private state. A baseline is captured
    once; current may be refreshed only after the existing pure owner accepts
    fresh GETs against that baseline and the independently mounted Pipe source.
    The host still owns source/mount provenance and full Office profile admission.
    """
    baseline_phase = phase == "office-service-baseline"
    require(phase in ("office-service-baseline", "office-service-current")
            and state.get("stage") == "setup_complete", "Office service readback requires prepared private state")
    saved = state.get("office_service_readback", {})
    require(isinstance(saved, dict), "Office service private readback is malformed")
    require("baseline" not in saved if baseline_phase else isinstance(saved.get("baseline"), dict),
            "Office service baseline already exists or is required")
    admin, actor = state["admin"], state["users"][0]
    webui.session(admin, "admin")
    webui.session(actor, "user")
    observed = {"task_config": webui.ok("GET", "/api/v1/tasks/config", token=admin["token"]),
                "target_model": webui.model(admin["token"], "gpt-6-luna")}
    catalog = webui.ok("GET", "/api/models?refresh=true", token=actor["token"]).get("data")
    require(isinstance(catalog, list) and all(isinstance(row, dict) for row in catalog),
            "Office service native actor catalog is malformed")
    targets = [row for row in catalog if row.get("id") == "gpt-6-luna"]
    require(len(targets) == 1, "Office service native actor target is missing or duplicated")
    observed["target_catalog"] = targets[0]
    if baseline_phase:
        config, target, entry = observed["task_config"], observed["target_model"], targets[0]
        require(all(config.get(k) == "gpt-6-luna" for k in ("TASK_MODEL", "TASK_MODEL_EXTERNAL"))
                and target.get("is_active") is True and isinstance(target.get("params"), dict)
                and isinstance(target.get("user_id"), str) and bool(target["user_id"])
                and entry.get("owned_by") == "openai" and not entry.get("pipe") and not entry.get("arena"),
                "Office service baseline native route differs")
        source_hash = None
    else:
        observed.update(function=webui.ok("GET", "/api/v1/functions/id/employee_budget_service", token=admin["token"]),
            valves=webui.ok("GET", "/api/v1/functions/id/employee_budget_service/valves", token=admin["token"]),
            workspace_model=webui.model(admin["token"], "employee_budget_service"))
        try:
            from prove_office_compatibility import _verify_service_tasks
            with Path("/proof/budgets/service_pipe.py").open("rb") as handle:
                raw = handle.read(128 * 1024 + 1)
            require(0 < len(raw) <= 128 * 1024, "Office service trusted source exceeded bound")
            source = raw.decode("utf8")
        except (ImportError, OSError, UnicodeError):
            raise ProofError("Office service validator/source unavailable") from None
        _verify_service_tasks(saved["baseline"], observed, source)
        source_hash = sha256(source.replace("\r\n", "\n").encode("utf8")).hexdigest()
    # Serialize/hash before the atomic private writer; invalid API JSON must not
    # overwrite a valid baseline/current or discard unrelated fixture credentials.
    observation_hash = sha256(json.dumps(observed, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode("utf8")).hexdigest()
    updated = copy.deepcopy(state)
    updated.setdefault("office_service_readback", {})["baseline" if baseline_phase else "current"] = observed
    write_private(path, updated)
    return {"office_service_readback": {"status": "baseline_collected" if baseline_phase else "current_contract_checked",
        "readback_only": True, "native_office_accepted": False, "observation_sha256": observation_hash,
        "trusted_source_sha256": source_hash}}


def office_service_setup(webui: WebUI, state: dict, path: Path) -> dict:
    """Prepare one explicit stand baseline, then reuse native installation/readback.

    This phase changes task settings; Office setup does not. A persisted partial
    marker forbids implicit retries. It does not dispatch or accept a follow-up.
    """
    from prove_office_compatibility import digest
    from prove_service_tasks import SOURCE, install
    from provision_cost_display import FILTER_ID, source_hash
    require(state.get("stage") == "setup_complete" and isinstance(state.get("office_setup"), dict)
            and all(k not in state for k in ("office_service_setup", "office_service_readback", "service_fixture")),
            "Office service setup requires a fresh prepared Office handoff")
    admin, actor = state["admin"], state["users"][0]
    webui.session(admin, "admin")
    webui.session(actor, "user")
    prepared = state["office_setup"].get("models", {})
    def unchanged_models():
        require(all(m in prepared and webui.model(admin["token"], m) == prepared[m]
            for m in ("gpt-5.4-mini", "gpt-6-luna")) and prepared["gpt-6-luna"].get("params") == {}
            and prepared["gpt-6-luna"].get("is_active") is True, "Office service prepared model changed")
    unchanged_models()
    with SOURCE.open("rb") as handle: source = handle.read(128 * 1024 + 1)
    require(0 < len(source) <= 128 * 1024, "Office service source exceeded bound")
    pipe_hash = source_hash(source.decode("utf8"))
    cost = webui.ok("GET", "/api/v1/functions/id/" + FILTER_ID, token=admin["token"])
    with Path("/proof/budgets/cost_filter.py").open("r", encoding="utf8") as handle: cost_source = handle.read(128 * 1024 + 1)
    require(0 < len(cost_source.encode("utf8")) <= 128 * 1024 and cost.get("is_active") is True
            and cost.get("type") == "filter" and source_hash(cost.get("content", "")) == source_hash(cost_source),
            "Office service budget Filter source differs")
    valves = webui.ok("GET", "/api/v1/functions/id/" + FILTER_ID + "/valves", token=admin["token"])
    require(valves.get("ledger_base_url") == "http://proxy:4000" and valves.get("service_payer_id") in (None, ""),
            "Office service budget Filter configuration is not fresh")
    original = webui.ok("GET", "/api/v1/tasks/config", token=admin["token"])
    baseline = copy.deepcopy(original)
    params = baseline.get("TASK_MODEL_PARAMS")
    require(params is None or isinstance(params, dict), "Office task params malformed")
    params = copy.deepcopy(params or {})
    custom = params.get("custom_params")
    require(custom is None or isinstance(custom, dict), "Office task custom params malformed")
    custom = copy.deepcopy(custom or {})
    require(custom.get("reasoning_effort") is None, "Office task legacy reasoning override is unsupported")
    reasoning = custom.get("reasoning")
    require(reasoning is None or isinstance(reasoning, dict), "Office task reasoning params malformed")
    custom["reasoning"] = {**(reasoning or {}), "effort": "none"}
    params.update(reasoning_effort=None, custom_params=custom)
    baseline.update(TASK_MODEL="gpt-6-luna", TASK_MODEL_EXTERNAL="gpt-6-luna", TASK_MODEL_PARAMS=params,
        ENABLE_FOLLOW_UP_GENERATION=True)
    state["office_service_setup"] = {"stage": "service_setup_in_progress", "original_tasks": original,
        "baseline_tasks": baseline, "pipe_source_sha256": pipe_hash, "journal": []}
    write_private(path, state)
    def post_tasks(body, label):
        webui.session(admin, "admin")
        unchanged_models()
        current = read_private(path)
        entry = {"stage": label, "body": copy.deepcopy(body), "returned": False}
        current["office_service_setup"]["journal"].append(entry)
        write_private(path, current)
        webui.ok("POST", "/api/v1/tasks/config/update", token=admin["token"], body=body)
        observed = webui.ok("GET", "/api/v1/tasks/config", token=admin["token"])
        require(observed == body, "Office service task config readback differs")
        entry.update(returned=True, readback=observed)
        write_private(path, current)
    post_tasks(baseline, "direct_task_baseline")
    before = office_service_readback(webui, read_private(path), path, "office-service-baseline")
    current = read_private(path)  # Collector writes a copy; never reuse stale state.
    install(webui, current, path, target_model="gpt-6-luna", cap=Decimal(1000))
    current = read_private(path)
    require(current["service_fixture"].get("pipe_sha256") == pipe_hash
            and webui.ok("GET", "/api/v1/tasks/config", token=admin["token"]) == baseline,
            "Office service installation changed task/source baseline")
    post_tasks({**baseline, "TASK_MODEL": "employee_budget_service", "TASK_MODEL_EXTERNAL": "employee_budget_service"}, "service_task_selectors")
    after = office_service_readback(webui, read_private(path), path, "office-service-current")
    current = read_private(path)
    unchanged_models()
    current["office_service_setup"]["stage"] = "readback_ready"
    write_private(path, current)
    return {"office_service_setup": {"status": "readback_ready", "inference_issued": False,
        "actual_followup_accepted": False, "native_office_accepted": False, "original_tasks_sha256": digest(original),
        "baseline_sha256": before["office_service_readback"]["observation_sha256"],
        "current_sha256": after["office_service_readback"]["observation_sha256"]}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("setup", "snapshot", "raise", "plainchat",
        "office-service-baseline", "office-service-current", "office-setup", "office-service-setup", "office-delegation-setup"))
    parser.add_argument("--private-state", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--office-state", type=Path)
    parser.add_argument("--delegation-tool-source", type=Path)
    parser.add_argument("--delegation-profiles-source", type=Path)
    args = parser.parse_args()
    receipt = {"schema": 1, "proof": "goal584-real-webui-native-provisioning", "phase": args.phase,
               "passed": False, "not_qualified": ["management_GUI", "service_classification", "paid_provider"],
               "started_at_utc": datetime.now(timezone.utc).isoformat()}
    if args.phase in ("office-service-baseline", "office-service-current"):
        receipt.update(readback_only=True, native_office_accepted=False)
    if args.phase in ("office-setup", "office-service-setup", "office-delegation-setup"):
        receipt.update(inference_issued=False, native_office_accepted=False)
    receipt_path_valid = False
    try:
        require(len({args.private_state.resolve(), args.receipt.resolve(), OPERATOR_STATE.resolve()}) == 3,
                "Private credential state, operator state and safe receipt must be separate")
        receipt_path_valid = True
        if args.phase == "office-setup":
            require(args.office_state is not None and len({args.private_state.resolve(), args.receipt.resolve(),
                OPERATOR_STATE.resolve(), args.office_state.resolve()}) == 4, "Office setup requires a separate new private handoff")
        webui = WebUI()
        state = setup(args, webui) if args.phase == "setup" else read_private(args.private_state)
        if args.phase == "office-delegation-setup":
            require(args.delegation_tool_source is not None and args.delegation_profiles_source is not None,
                    "Delegated setup requires exact source inputs")
        if args.phase == "raise":
            raise_caps(state)
        if args.phase == "plainchat":
            receipt["plainchat_control"] = plainchat(webui, state)
        observed = (office_delegation_setup(webui, state, args.private_state,
                tool_source=args.delegation_tool_source, profiles_source=args.delegation_profiles_source)
            if args.phase == "office-delegation-setup" else
            office_setup(webui, state, args.office_state) if args.phase == "office-setup" else
            office_service_setup(webui, state, args.private_state) if args.phase == "office-service-setup" else
            office_service_readback(webui, state, args.private_state, args.phase)
            if args.phase in ("office-service-baseline", "office-service-current") else snapshot(webui, state))
        if args.phase == "plainchat":
            require(all(model["builtin_tools"] is False for model in observed["webui_models"]),
                    "Plain-chat capability readback differs from native model configuration")
        if args.phase == "setup":
            require(all(close_amount(user["spend_usd"], Decimal("0"))
                        and close_amount(user["max_budget_usd"], Decimal("0.80")) for user in observed["users"])
                    and all(close_amount(key["max_budget_usd"], Decimal("0.40")) for key in observed["keys"]),
                    "Native initial user/key caps do not match the fixture contract")
        receipt.update(observed)
        receipt["passed"] = True
    except ProofError as error:
        receipt["failure"] = str(error)
    except Exception as error:
        receipt["failure"] = "Unexpected WebUI fixture error: " + type(error).__name__
    receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    if receipt_path_valid:
        write_private(args.receipt, receipt)
    print(json.dumps(receipt, indent=2, allow_nan=False))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
