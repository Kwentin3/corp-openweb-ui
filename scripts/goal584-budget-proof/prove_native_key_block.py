"""Finite proxy worker: one synthetic signed call, native key/block, denial.

Requires the already attested disposable stand and existing operator handoff.
No bootstrap, host driver, retries, unblock, finance reset or unknown-Usage policy.
"""
from __future__ import annotations

import asyncio
import copy
from dataclasses import replace
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4

from aiohttp import ClientSession

from employee_budget_admin_client import BudgetAdminClient
from employee_budget_admin_contract import BudgetAdminError
from employee_budget_assignment import assignment_matches
from litellm_auth import PROVENANCE_FIELD, TASK_HEADER, USER_ID_HEADER
from provenance import decode_call, encode_call, validate_persisted_scope
import provision_webui as fixture
from prove_native_budgets import CALL_COST, ProofError, close_amount, protected_r, require
from prove_pricing_snapshots import encoded, no_credentials, private_credentials
from prove_service_tasks import provider

PROOF = "goal584-native-key-block"
MODEL = "goal584-a"
CAP = Decimal("2")
STATE = Path("/proof-private/native-key-block.private.json")
RECEIPT = Path("/proof-private/native-key-block.safe.json")
BODY = {"model": MODEL, "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5, "stream": False}
USAGE = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
BLOCK_MESSAGE = "Authentication Error, Доступ заблокирован. Обратитесь к администратору."


def digest(value):
    return sha256(encoded(value)).hexdigest()


def routing(native):
    rows = native.ok("GET", "/model/info").get("data")
    require(isinstance(rows, list), "block_model_info_missing")
    selected = [row for row in rows if row.get("model_name") == MODEL]
    require(len(selected) == 1, "block_model_deployment_ambiguous")
    row = selected[0]
    params, info = row.get("litellm_params", {}), row.get("model_info", {})
    require(params.get("model") == "openai/goal584-fake-a"
            and params.get("api_base") == "http://provider:8000/v1"
            and info.get("id") == "goal584-deployment-a"
            and info.get("input_cost_per_token") == .01
            and info.get("output_cost_per_token") == .02, "block_non_synthetic_route_or_rates")
    return digest({"model": params["model"], "api_base": params["api_base"],
                   "id": info["id"], "input": info["input_cost_per_token"], "output": info["output_cost_per_token"]})


def snapshot(native, uid, key_hash):
    user = native.user_info(uid)
    payload = native.ok("GET", "/key/info", query={"key": key_hash})
    key = payload.get("info")  # Native endpoint removes info.token and echoes the lookup at top level.
    require(isinstance(key, dict) and payload.get("key") == key_hash
            and assignment_matches(SimpleNamespace(**key), uid, MODEL), "block_assignment_readback")
    rows = native.logs(uid)  # Existing paginated raw native SpendLogs owner.
    require(len(rows) <= 1000, "block_history_bound")
    encoded({"user": user, "key": key, "rows": rows})
    return {"user": user, "key": key, "rows": rows}


def call(native, secret, uid):
    chat, answer = str(uuid4()), str(uuid4())
    token = encode_call(secret, user_id=uid, model=MODEL, chat_id=chat, answer_id=answer,
                        root_chat_id=chat, root_answer_id=answer)
    claims = decode_call(token, secret, user_id=uid, model=MODEL)
    expected = {"schema": 1, "user_id": uid, "model": MODEL, "chat_id": chat, "answer_id": answer,
                "root_chat_id": chat, "root_answer_id": answer, "call_id": claims["jti"], "category": "personal"}
    status, response, _ = native.request("POST", "/v1/chat/completions", token=secret,
        extra_headers={USER_ID_HEADER: uid, TASK_HEADER: ""},
        body={**copy.deepcopy(BODY), "litellm_metadata": {PROVENANCE_FIELD: token}})
    return status, response, expected


def positive_rows(observation, uid, key_hash, scope):
    rows = observation["rows"]
    if not rows:
        return None
    require(len(rows) == 1, "block_positive_history_scope")
    row = rows[0]
    meta = row.get("metadata")
    if isinstance(meta, str):
        meta = json.loads(meta)
    actual = validate_persisted_scope((meta or {}).get("spend_logs_metadata", {}).get("owui_budget"))
    require(actual == scope and row.get("user") == uid and row.get("api_key") == key_hash
            and row.get("model_group") == MODEL and row.get("model_id") == "goal584-deployment-a"
            and row.get("status") == "success" and close_amount(row.get("spend"), CALL_COST)
            and {k: row.get(k) for k in USAGE} == USAGE, "block_positive_native_row")
    if not all(close_amount(observation[k].get("spend"), CALL_COST) for k in ("user", "key")):
        return None
    return observation


async def execute(receipt):
    require(not STATE.exists() and STATE != RECEIPT and STATE != fixture.OPERATOR_STATE,
            "block_requires_new_private_handoff")
    operator = fixture.read_private(fixture.OPERATOR_STATE)
    secret = os.environ.get("OWUI_BUDGET_GATEWAY_SECRET", "")
    require(bool(secret) and secret != operator.get("operator_token"), "block_distinct_gateway_required")
    native = fixture.native_client()
    uid = str(uuid4())
    receipt.update(user_id=uid, model=MODEL)
    state = {"schema": 1, "proof": PROOF, "user_id": uid}
    def save(stage, **facts):
        receipt["stage"] = stage
        state.update(stage=stage, **facts)
        encoded(state)
        fixture.write_private(STATE, state)
    save("preflight")
    route = routing(native)  # Must precede every native mutation.
    baseline_provider = provider()["requests"]
    async with ClientSession(trust_env=False) as session:
        admin = BudgetAdminClient(session, fixture.PROXY_URL, operator["operator_token"])
        async def before_write():
            require(routing(native) == route, "block_route_changed_before_write")
        created = await admin.initialize_employee(uid, ((MODEL, CAP),), CAP, secret, before_write=before_write)
        require(created.user_id == uid and created.max_budget == CAP and created.spend == 0
                and len(created.models) == 1 and created.models[0].model == MODEL
                and created.models[0].blocked is False, "block_initial_assignment")
        key_hash = created.models[0].key_hash
        receipt["key_hash"] = key_hash
        before = snapshot(native, uid, key_hash)
        require(not before["rows"] and before["key"].get("blocked") is False, "block_fresh_history")
        policy = protected_r(before["user"], before["key"])
        save("initialized", key_hash=key_hash, before=before)
        require(routing(native) == route, "block_route_changed_before_call")
        status, response, scope = call(native, secret, uid)
        require(status == 200 and response.get("usage") == USAGE and not response.get("error"),
                "block_positive_call_failed")
        positive = native.poll("key-block positive settlement", lambda: positive_rows(
            snapshot(native, uid, key_hash), uid, key_hash, scope))
        require(protected_r(positive["user"], positive["key"]) == policy, "block_positive_policy_changed")
        physical = provider()["requests"]
        expected_body = {k: v for k, v in BODY.items() if k != "stream"} | {"model": "goal584-fake-a"}
        require(len(physical) == len(baseline_provider) + 1 and physical[:-1] == baseline_provider
                and physical[-1]["id"] == response.get("id") and physical[-1]["body"] == expected_body
                and physical[-1]["usage"] == USAGE, "block_positive_provider_context")
        settled = await admin.read_employee(uid, (MODEL,))
        require(settled == replace(created, spend=CALL_COST,
                models=(replace(created.models[0], spend=CALL_COST),)), "block_positive_budget_readback")
        save("positive_settled", positive=positive, scope=scope, provider_id=response["id"])
        await before_write()
        await admin.block_model_key(key_hash)  # Real native public operator API; never reset/unblock.
        blocked = await admin.read_employee(uid, (MODEL,))
        require(blocked == replace(settled, models=(replace(settled.models[0], blocked=True),)),
                "block_commit_readback_or_finance_changed")
        committed = snapshot(native, uid, key_hash)
        expected_policy = copy.deepcopy(policy); expected_policy["key"]["blocked"] = True
        require(committed["key"].get("blocked") is True
                and protected_r(committed["user"], committed["key"]) == expected_policy
                and committed["rows"] == positive["rows"], "block_commit_history_or_policy_changed")
        save("blocked", blocked=committed)
        require(routing(native) == route, "block_route_changed_before_denial")
        status, response, denied_scope = call(native, secret, uid)
        require(status == 401 and response.get("error", {}).get("type") == "auth_error"
                and response["error"].get("message") == BLOCK_MESSAGE, "block_expected_native_denial")
        require(provider()["requests"] == physical, "block_denial_dispatched_provider")
        after = snapshot(native, uid, key_hash)
        require(protected_r(after["user"], after["key"]) == expected_policy
                and all(close_amount(after[k].get("spend"), CALL_COST) for k in ("user", "key"))
                and all(row in after["rows"] for row in positive["rows"]), "block_denial_finance_or_history_changed")
        new_rows = [row for row in after["rows"] if row not in positive["rows"]]
        require(all(close_amount(row.get("spend"), Decimal(0)) and row.get("status") == "failure"
                    for row in new_rows), "block_denial_added_charge")
        require(await admin.read_employee(uid, (MODEL,)) == blocked, "block_final_budget_changed")
        save("complete", after=after, denied_scope=denied_scope)
    candidate = dict(receipt, user_id=uid, model=MODEL, key_hash=key_hash, blocked=True,
        positive_cost_usd=".20", denied_http_status=status, provider_dispatches=1,
        route_sha256=route, positive_rows_sha256=digest(positive["rows"]),
        final_rows_sha256=digest(after["rows"]), policy_before_sha256=digest(policy),
        policy_after_sha256=digest(expected_policy), native_log_request_id_sha256=digest(positive["rows"][0]["request_id"]),
        caps_and_spend_preserved=True, positive_history_preserved=True,
        l1_cache_warm_proven=False, non_admin_management_tested=False, unknown_usage_policy_qualified=False)
    owners = (__name__, fixture.__name__, BudgetAdminClient.__module__, BudgetAdminError.__module__,
              fixture.write_private.__module__, assignment_matches.__module__,
              encode_call.__module__, protected_r.__module__, no_credentials.__module__, provider.__module__, "litellm_auth")
    candidate["source_sha256"] = {Path(sys.modules[name].__file__).name:
        sha256(Path(sys.modules[name].__file__).read_bytes()).hexdigest() for name in owners}
    no_credentials(candidate, [secret, *private_credentials(operator)])
    receipt.update(candidate, passed=True)
    return receipt


def main():
    receipt = {"schema": 1, "proof": PROOF, "passed": False, "stage": "preflight",
               "worker_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
               "scope": "Disposable native block/admission primitive only; no unknown-Usage finality or product guardrail."}
    output_available = not RECEIPT.exists() and not RECEIPT.is_symlink()
    try:
        require(output_available, "block_requires_new_safe_receipt")
        asyncio.run(execute(receipt))
    except (ProofError, BudgetAdminError) as error:
        receipt.update(passed=False, failure=str(error))
    except Exception:
        receipt.update(passed=False, failure="block_unexpected_worker_failure")
    no_credentials(receipt)
    if output_available:
        fixture.write_private(RECEIPT, receipt)
    print(json.dumps(receipt, indent=2, allow_nan=False))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
