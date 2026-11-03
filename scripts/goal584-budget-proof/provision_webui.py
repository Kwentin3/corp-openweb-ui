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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("setup", "snapshot", "raise", "plainchat"))
    parser.add_argument("--private-state", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    receipt = {"schema": 1, "proof": "goal584-real-webui-native-provisioning", "phase": args.phase,
               "passed": False, "not_qualified": ["management_GUI", "service_classification", "paid_provider"],
               "started_at_utc": datetime.now(timezone.utc).isoformat()}
    receipt_path_valid = False
    try:
        require(len({args.private_state.resolve(), args.receipt.resolve(), OPERATOR_STATE.resolve()}) == 3,
                "Private credential state, operator state and safe receipt must be separate")
        receipt_path_valid = True
        webui = WebUI()
        state = setup(args, webui) if args.phase == "setup" else read_private(args.private_state)
        if args.phase == "raise":
            raise_caps(state)
        if args.phase == "plainchat":
            receipt["plainchat_control"] = plainchat(webui, state)
        observed = snapshot(webui, state)
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
