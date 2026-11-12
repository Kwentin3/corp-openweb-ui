#!/usr/bin/env python3
"""Finite real stock-WebUI monthly GET + native cap readback; zero inference.

Run in the existing disposable proxy/WebUI fixture after gateway bootstrap.
Native auth, Functions, Users, counters and assignments remain their owners.
The existing policy set is a backend readback, not a new set API or GUI proof.
All accounts/config are synthetic and owned by the project cleanup; credentials
remain in memory and the existing protected bootstrap state only.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import sys
import time
import traceback
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request

from aiohttp import ClientSession, ClientTimeout

from prove_gateway_auth import read_private
from prove_native_budgets import MODELS, NativeProof, ProofError, protected_r, require
import provision_webui as native_webui


ROUTE = "/api/v1/employee-budgets/monthly"
EVENT_ID = "employee_budget_monthly_view"
COST_ID = "employee_budget_cost"
BUDGETS = Path("/proof/budgets")
PUBLIC_EVIDENCE = ("user_id", "budget_usd", "spend_usd", "remaining_usd", "budget_duration",
                   "budget_reset_at", "models", "expense_status", "expense_observation_scope")


def bounded_opener(opener, deadline):
    def bounded(request, timeout=5):
        remaining = deadline - time.monotonic()
        require(remaining > 0, "monthly_api_deadline")
        return opener.open(request, timeout=min(timeout, 5, remaining))
    return SimpleNamespace(open=bounded)


async def run(args, receipt):
    # Existing mounted policy source and shared DTO/client aliases; no new reader.
    sys.path.insert(0, str(BUDGETS))
    import admin_policy as policy
    from employee_budget_admin_client import BudgetAdminClient

    require(args.webui_url == "http://webui:8080" and args.ledger_base_url == "http://proxy:4000",
            "monthly_api_requires_owned_service_urls")
    state = read_private(args.private_state)
    require(state.get("stage") == "bootstrap_complete", "monthly_api_requires_bootstrap")
    operator = state.get("operator_token")
    gateway = os.environ.get("OWUI_BUDGET_GATEWAY_SECRET")
    require(isinstance(operator, str) and operator.startswith("sk-") and bool(gateway) and gateway != operator,
            "monthly_api_requires_existing_distinct_credentials")
    deadline = time.monotonic() + 90
    native = NativeProof(args.base_url, operator, 5, {})
    native.opener = bounded_opener(native.opener, deadline)
    native_webui.WEBUI_URL = args.webui_url
    webui = native_webui.WebUI()
    webui.opener = bounded_opener(webui.opener, deadline)
    private_values = [operator, gateway]
    receipt.update(stage="preflight", aliases=list(MODELS), model_inference_requested=False,
                   limits={"phase_seconds": 90, "http_seconds": 5})

    def safe(payload):
        encoded = json.dumps(payload, sort_keys=True)
        require(not any(value and value in encoded for value in private_values), "monthly_api_secret_disclosure")
        require(not any(field in encoded for field in ('"key"', '"key_hash"', '"key_alias"', '"api_key"',
                    '"token"', '"password"', 'ledger_admin_key', 'ledger_read_key', 'sk-', 'http://',
                    'https://')), "monthly_api_private_field_disclosure")

    def get(account=None, target=None, expected=200):
        url = args.webui_url + ROUTE + ("?" + urlencode({"user_id": target}) if target else "")
        headers = {"Authorization": "Bearer " + account["token"]} if account else {}
        try:
            response = webui.opener.open(Request(url, headers=headers), timeout=5)
        except HTTPError as error:
            response = error
        except (URLError, TimeoutError, OSError):
            raise ProofError("monthly_api_get_transport") from None
        with response:
            raw = response.read(2 * 1024 * 1024 + 1)
            require(len(raw) <= 2 * 1024 * 1024, "monthly_api_response_bound")
            require(response.code == expected, "monthly_api_unexpected_status_" + str(response.code))
            require("application/json" in response.headers.get("Content-Type", ""), "monthly_api_hit_non_json_route")
            require(expected != 200 or response.headers.get("Cache-Control") == "no-store", "monthly_api_missing_no_store")
            payload = json.loads(raw)
        require(isinstance(payload, dict), "monthly_api_invalid_object")
        safe(payload)
        return payload

    def install(function_id, filename, kind):
        source = (BUDGETS / filename).read_text(encoding="utf-8")
        made = webui.ok("POST", "/api/v1/functions/create", token=controller["token"], body={
            "id": function_id, "name": function_id, "content": source, "meta": {}})
        require(made.get("id") == function_id and made.get("type") == kind and made.get("is_active") is False,
                "monthly_api_function_creation")
        stored = webui.ok("GET", "/api/v1/functions/id/" + function_id, token=controller["token"])
        require(stored.get("content") == source, "monthly_api_function_source_changed")
        return sha256(source.encode()).hexdigest()

    def account(role, label, signup=False):
        email, password = label + "-" + native.run_id + "@example.com", "Aa1!" + secrets.token_urlsafe(24)
        body = {"name": "Monthly proof " + label, "email": email, "password": password}
        if not signup:
            body["role"] = role
        created = webui.ok("POST", "/api/v1/auths/signup" if signup else "/api/v1/auths/add",
                           token=None if signup else controller["token"], body=body)
        value = native_webui.account_from_response(created, email, password, role)
        private_values.extend((password, value["token"]))
        return value

    def compare(payload, account, budget):
        require(payload.get("user_id") == account["id"] and payload.get("email") == account["email"],
                "monthly_api_target_identity")
        require(payload.get("budget_usd") == policy.money(budget.max_budget)
                and payload.get("spend_usd") == policy.money(budget.spend)
                and payload.get("remaining_usd") == policy.money(budget.max_budget - budget.spend)
                and payload.get("budget_duration") == budget.budget_duration
                and payload.get("budget_reset_at") == budget.budget_reset_at,
                "monthly_api_native_total_or_period")
        rows = payload.get("models")
        require(isinstance(rows, list) and len(rows) == len(budget.models)
                and {row.get("id") for row in rows} == set(MODELS), "monthly_api_model_scope")
        for model in budget.models:
            row = next(row for row in rows if row["id"] == model.model)
            require(all(row.get(field) == value for field, value in {
                "cap_usd": policy.money(model.max_budget), "spend_usd": policy.money(model.spend),
                "remaining_usd": policy.money(model.max_budget - model.spend),
                "budget_duration": model.budget_duration, "budget_reset_at": model.budget_reset_at,
                "blocked": model.blocked, "expense_status": "unavailable"}.items()), "monthly_api_native_model_or_unknown")
        require(payload.get("expense_status") == "unavailable" and payload.get("expense_observation_scope") == "assignment_history",
                "monthly_api_empty_history_is_not_known_zero")

    async def provider(session):
        async with session.get("http://provider:8000/__proof/requests", allow_redirects=False) as response:
            require(response.status == 200, "monthly_api_provider_observation")
            raw = await response.content.read(2 * 1024 * 1024 + 1)
            require(len(raw) <= 2 * 1024 * 1024, "monthly_api_provider_bound")
            return json.loads(raw)

    async def guard():
        require(time.monotonic() < deadline, "monthly_api_deadline")
        webui.session(controller, "admin")

    async with asyncio.timeout(90), ClientSession(trust_env=False, timeout=ClientTimeout(total=5)) as session:
        client = BudgetAdminClient(session, args.base_url, operator)
        receipt["stage"] = "native_auth_setup"
        require(webui.ok("GET", "/api/version").get("version") == "0.12.2", "monthly_api_webui_version")
        native.schema()
        receipt["native_schema_checks"] = native.receipt["checks"]
        controller = account("admin", "controller", signup=True)
        native_webui.wait_after_controller_creation(webui, controller, timeout=5)
        administrator = account("admin", "admin")
        employees = [account("user", "employee1"), account("user", "employee2")]
        pending = account("pending", "pending")
        receipt["users"] = {"employees": [user["id"] for user in employees], "administrator": administrator["id"]}
        receipt["stage"] = "native_budget_setup"
        budgets = {}
        for employee in employees:
            budgets[employee["id"]] = await asyncio.wait_for(client.initialize_employee(employee["id"],
                ((MODELS[0], Decimal(12)), (MODELS[1], Decimal(8))), Decimal(20), gateway, before_write=guard), timeout=5)

        receipt["stage"] = "event_install"
        receipt["function_source_sha256"] = {COST_ID: install(COST_ID, "cost_filter.py", "filter"),
            EVENT_ID: install(EVENT_ID, "monthly_view.py", "event")}
        path = "/api/v1/functions/id/" + COST_ID + "/valves"
        webui.ok("POST", path + "/update", token=controller["token"], body={
            "ledger_base_url": args.ledger_base_url, "ledger_admin_key": operator})
        observed = webui.ok("GET", path, token=controller["token"])
        require(observed.get("ledger_base_url") == args.ledger_base_url and observed.get("ledger_admin_key") == operator,
                "monthly_api_common_configuration")
        enabled = webui.ok("POST", "/api/v1/functions/id/" + EVENT_ID + "/toggle", token=controller["token"])
        require(enabled.get("is_active") is True, "monthly_api_event_not_active")

        def snapshot():
            result = {}
            for employee in employees:
                uid = employee["id"]
                user = native.user_info(uid)
                keys = {model.model: native.ok("GET", "/key/info", query={"key": model.key_hash})["info"]
                        for model in budgets[uid].models}
                for model in budgets[uid].models:
                    private_values.append(model.key_hash)
                    protected_r(user, keys[model.model])
                result[uid] = {"user": user, "keys": keys, "logs": native.logs(uid)}
            return result

        receipt["stage"] = "authenticated_gets"
        before, physical_before = snapshot(), await provider(session)
        require(physical_before.get("synthetic") is True and physical_before.get("requests") == [], "monthly_api_provider_not_fresh")
        for employee in employees:
            for target in (None, employee["id"]):
                payload = get(employee, target)
                compare(payload, employee, budgets[employee["id"]])
                if employee is employees[0] and target is None:
                    receipt["self_initial"] = {field: payload[field] for field in PUBLIC_EVIDENCE}
                other = next(user for user in employees if user["id"] != employee["id"])
                require(other["id"] not in json.dumps(payload) and other["email"] not in json.dumps(payload),
                        "monthly_api_cross_user_disclosure")
            compare(get(administrator, employee["id"]), employee, budgets[employee["id"]])
        get(employees[0], employees[1]["id"], expected=403)
        get(expected=401)
        get(pending, expected=401)
        require(snapshot() == before and await provider(session) == physical_before, "monthly_api_get_mutated_native_state")
        receipt.update(self_and_admin_views=True, cross_user_denied=True, anonymous_pending_denied=True,
                       zero_and_unavailable_distinct=True, native_period_and_model_fields=True, get_nonmutating=True)

        receipt["stage"] = "existing_policy_set_readback"
        employee = employees[0]
        current = budgets[employee["id"]]
        change = policy.BudgetChange(employee["id"], policy.revision(current), Decimal(30),
                                     ((MODELS[0], Decimal(60)), (MODELS[1], Decimal(40))))
        await guard()
        changed = await asyncio.wait_for(policy.apply_prepared(client, policy.prepare_change(change, current)), timeout=5)
        budgets[employee["id"]] = changed
        updated = get(employee)
        compare(updated, employee, changed)
        receipt["self_after_set"] = {field: updated[field] for field in PUBLIC_EVIDENCE}
        compare(get(administrator, employee["id"]), employee, changed)
        require(changed.spend == 0 and all(model.spend == 0 for model in changed.models), "monthly_api_set_changed_spend")
        receipt["native_policy_set_readback"] = {"total_cap": "30", "model_caps": ["18", "12"],
            "authority_scope": "existing native cap policy only; prior Tool confirmation/rights evidence retained"}

        receipt["stage"] = "demotion_and_final_preservation"
        baseline = snapshot()
        webui.ok("POST", "/api/v1/users/" + administrator["id"] + "/update", token=controller["token"], body={"role": "user"})
        webui.session(administrator, "user")
        get(administrator, employees[0]["id"], expected=403)
        require(snapshot() == baseline and await provider(session) == physical_before, "monthly_api_final_state_changed")
        receipt.update(stage="verified", demoted_admin_denied=True, secrets_not_disclosed=True,
                       provider_dispatches=0, native_get_preservation=True,
                       unknown_case="existing component/native witness evidence; no synthetic history or inference inserted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-state", type=Path, default=Path("/proof-private/gateway-state.private.json"))
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:4000")
    parser.add_argument("--webui-url", default="http://webui:8080")
    parser.add_argument("--ledger-base-url", default="http://proxy:4000")
    args = parser.parse_args()
    receipt = {"proof": "goal584-monthly-native-api", "passed": False,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "not_qualified": ["GUI", "provider billing", "new set API/Tool authority", "production"]}
    try:
        require(args.private_state.resolve() != args.receipt.resolve(), "monthly_api_private_receipt_collision")
        asyncio.run(run(args, receipt))
        receipt["passed"] = True
    except ProofError as error:
        receipt["failure"] = str(error)
    except Exception as error:
        receipt["failure"] = "monthly_api_" + type(error).__name__
        receipt["failure_frames"] = [{"file": Path(frame.filename).name, "function": frame.name, "line": frame.lineno}
            for frame in traceback.extract_tb(error.__traceback__)[-5:]]
    receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    rendered = json.dumps(receipt, indent=2, allow_nan=False)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
