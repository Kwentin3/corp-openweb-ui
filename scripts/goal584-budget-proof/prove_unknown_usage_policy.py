"""Finite personal nonstream Responses primitive; no WebUI chat/browser claim.

Existing native keys, provider receipts and restricted cost reader own state.
Unknown native zero is never a free/final monetary result. No reset or unblock.
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
import re
import sys
from types import SimpleNamespace
from uuid import uuid4
from aiohttp import ClientSession
from employee_budget_admin_client import BudgetAdminClient
from employee_budget_admin_contract import BudgetAdminError
from employee_budget_assignment import assignment_matches, assignment_metadata
from employee_budget_cost_readback import CostReadError, SESSION_ROUTE, read_cost_snapshot
from litellm_auth import PROVENANCE_FIELD, TASK_HEADER, USER_ID_HEADER
from provenance import decode_call, encode_call, validate_persisted_scope
import provision_webui as fixture
from prove_native_budgets import ProofError, close_amount, protected_r, require
from prove_pricing_snapshots import encoded, no_credentials, private_credentials
from prove_service_tasks import provider

PROOF = "goal584-unknown-usage-policy"
ALIASES = ("goal584-usage", "goal584-usage-absent", "goal584-usage-null")
WIRES = tuple(name.replace("goal584-", "goal584-fake-", 1) for name in ALIASES)
RAW_USAGE = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
             "input_tokens_details": {"cached_tokens": 6}, "output_tokens_details": {"reasoning_tokens": 2}}
STATE = Path("/proof-private/unknown-usage-policy.private.json")
RECEIPT = Path("/proof-private/unknown-usage-policy.safe.json")
WEBUI_STATE = Path("/proof-private/webui-state.private.json")
MOUNTED_SOURCES = {n: Path("/proof") / n for n in ("usage_guard_fixture.py", "unknown_usage_guard.py")}
BLOCK_MESSAGE = "Authentication Error, Key is blocked. Update via `/key/unblock` if you're an admin."
KNOWN_COST = Decimal(".166")
digest = lambda value: sha256(encoded(value)).hexdigest()


def source_modules():
    return (__name__, fixture.__name__, BudgetAdminClient.__module__, BudgetAdminError.__module__, assignment_matches.__module__,
            fixture.write_private.__module__, encode_call.__module__, protected_r.__module__, no_credentials.__module__,
            provider.__module__, read_cost_snapshot.__module__, "litellm_auth",
            read_cost_snapshot.__globals__["validate_persisted_scope"].__module__)


def failure_diagnostic(error, context):
    """Only bounded attempt slots and owned source coordinates; no error text."""
    value = {"error_class": "ProofError" if isinstance(error, ProofError) else
                            "BudgetAdminError" if isinstance(error, BudgetAdminError) else "unexpected"}
    if type(context.get("attempt")) is int and 1 <= context["attempt"] <= 7: value["attempt"] = context["attempt"]
    if context.get("actor") in ("A", "B"): value["actor"] = context["actor"]
    if type(context.get("model")) is int and 1 <= context["model"] <= 3: value["model"] = context["model"]
    owned = {}
    for name in source_modules():
        filename = getattr(sys.modules.get(name), "__file__", None)
        if isinstance(filename, str):
            try: path = Path(filename).resolve(strict=True)
            except OSError: continue
            owned[path] = path.name
    frames, trace = [], error.__traceback__
    while trace is not None:
        code, line = trace.tb_frame.f_code, trace.tb_lineno
        try: path = Path(code.co_filename).resolve(strict=True)
        except OSError: path = None
        if path in owned and code.co_name != "require" and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", code.co_name) \
                and type(line) is int and 1 <= line <= 1000000:
            frame = (path, {"module": owned[path], "function": code.co_name, "line": line})
            if frames and frames[-1][0] == path: frames[-1] = frame
            else: frames.append(frame)
        trace = trace.tb_next
    value["origin"] = [frame for _, frame in frames[-2:]]
    return value


def known_proxy_usage(value):
    # Native typed serialization adds nullable defaults. Provider wire Usage
    # remains exact in physical(); this check only validates its proxy projection.
    return isinstance(value, dict) and all(type(value.get(k)) is int and value[k] == RAW_USAGE[k]
        for k in ("input_tokens", "output_tokens", "total_tokens")) and all(isinstance(value.get(k), dict)
        and type(value[k].get(field)) is int and value[k][field] == RAW_USAGE[k][field]
        for k, field in (("input_tokens_details", "cached_tokens"), ("output_tokens_details", "reasoning_tokens")))


def routing(native):
    data = native.ok("GET", "/model/info").get("data")
    require(isinstance(data, list), "unknown_model_info")
    selected = []
    for alias, wire in zip(ALIASES, WIRES):
        found = [r for r in data if r.get("model_name") == alias]
        require(len(found) == 1, "unknown_ambiguous_deployment")
        params, info = found[0].get("litellm_params", {}), found[0].get("model_info", {})
        rates = {"input_cost_per_token": .01, "output_cost_per_token": .02,
                 "cache_read_input_token_cost": .001, "output_cost_per_reasoning_token": .03}
        require(params.get("model") == "openai/" + wire and params.get("api_base") == "http://provider:8000/v1"
                and info.get("id") == alias + "-v1" and info.get("mode") == "responses"
                and all(type(info.get(k)) in (int, float) and info[k] == v for k, v in rates.items()),
                "unknown_non_synthetic_route_or_rates")
        selected.append({"alias": alias, "wire": params["model"], "base": params["api_base"],
                         "id": info["id"], "rates": rates})
    return digest(selected)


def metadata(row):
    value = row.get("metadata")
    if value is None and row.get("status") == "failure": return {}
    if isinstance(value, str): value = json.loads(value)
    require(isinstance(value, dict), "unknown_row_metadata")
    return value


def snapshot(native, budget):
    user, keys = native.user_info(budget.user_id), {}
    require(not user.get("teams") and user.get("user_role") == "internal_user", "unknown_employee_owner")
    for model in budget.models:
        payload = native.ok("GET", "/key/info", query={"key": model.key_hash})
        key = payload.get("info")
        require(isinstance(key, dict) and payload.get("key") == model.key_hash
                and assignment_matches(SimpleNamespace(**key), budget.user_id, model.model), "unknown_assignment")
        value = key.get("metadata")
        if isinstance(value, str): value = json.loads(value)
        require(value == assignment_metadata(model.model) and key.get("team_id") is None
                and key.get("team_metadata") in (None, {}), "unknown_assignment_admin_optout_or_pricing_override")
        keys[model.model] = key
    rows = native.logs(budget.user_id)
    require(len(rows) <= 1000 and len({r["request_id"] for r in rows}) == len(rows), "unknown_history_bound")
    return {"user": user, "keys": keys, "rows": sorted(rows, key=lambda r: r["request_id"])}


def protected(observation):
    return {name: protected_r(observation["user"], key) for name, key in observation["keys"].items()}


def history(before, after, keys, calls):
    old = {r["request_id"]: r for r in before}
    current = {r["request_id"]: r for r in after}
    require(all(current.get(k) == v for k, v in old.items()), "unknown_old_history_changed")
    denied, audits = sum(c["status"] == 401 for c in calls), 0
    scopes = [c["scope"] for c in calls if c["status"] == 200]
    require(all(sum(metadata(r).get("spend_logs_metadata", {}).get("owui_budget") == scope for r in after) == 1
                for scope in scopes), "unknown_physical_row_cardinality")
    for row in after:
        matched = metadata(row).get("spend_logs_metadata", {}).get("owui_budget") in scopes
        if not matched:
            audits += 1
            require(row.get("status") == "failure" and close_amount(row.get("spend"), Decimal(0))
                    and audits <= denied, "unknown_unattributed_history")
        if row["request_id"] not in old:
            require(row.get("api_key") == keys.get(row.get("model_group")), "unknown_foreign_history")


def physical(previous, current, alias):
    require(current.get("synthetic") is True and current.get("control") == previous.get("control")
            and isinstance(current.get("requests"), list), "unknown_provider_control")
    rows, old = current["requests"], previous["requests"]
    require(len(rows) == len(old) + 1 and rows[:-1] == old, "unknown_provider_prefix_or_count")
    record = rows[-1];index = ALIASES.index(alias)
    expected = {"model": WIRES[index], "input": "Hi", "max_output_tokens": 16, "store": False, "stream": False}
    require(record.get("body") == expected and record.get("route") == "/v1/responses"
            and isinstance(record.get("id"), str) and record.get("id_kind") == "provider_response",
            "unknown_provider_context")
    life, response = record.get("lifecycle", {}), record.get("response", {})
    require(life.get("response_status") == 200, "unknown_provider_http_status")
    if life.get("terminal") is not True: return None
    require(life.get("outcome") == "completed"
            and response.get("id") == record["id"] and response.get("model") == WIRES[index]
            and response.get("object") == "response" and response.get("status") == "completed"
            and response.get("error") is None, "unknown_provider_terminal")
    require(record.get("usage") == (RAW_USAGE if index == 0 else None)
            and ((response.get("usage") == RAW_USAGE) if index == 0 else
                 ("usage" not in response) if index == 1 else ("usage" in response and response["usage"] is None)),
            "unknown_provider_raw_usage")
    return record


def settled(native, budget, scope, key_hash, unknown, previous, calls):
    observation = snapshot(native, budget)
    policy = copy.deepcopy(protected(previous))
    target = observation["keys"][scope["model"]].get("blocked")
    require(type(target) is bool and (unknown or target == policy[scope["model"]]["key"]["blocked"]),
            "unknown_block_flags_changed")
    if unknown: policy[scope["model"]]["key"]["blocked"] = target
    require(protected(observation) == policy, "unknown_caps_or_policy_changed")
    retained = {r["request_id"]: r for r in observation["rows"]}
    require(all(retained.get(r["request_id"]) == r for r in previous["rows"]), "unknown_old_history_changed")
    found = [r for r in observation["rows"] if metadata(r).get("spend_logs_metadata", {}).get("owui_budget") == scope]
    if not found: return None
    require(len(found) == 1, "unknown_duplicate_call_nonce")
    row = found[0];actual = validate_persisted_scope(metadata(row)["spend_logs_metadata"]["owui_budget"])
    require(actual == scope and row.get("user") == budget.user_id and row.get("api_key") == key_hash
            and row.get("model_group") == scope["model"] and row.get("model_id") == scope["model"] + "-v1",
            "unknown_native_row_binding")
    records = metadata(row).get("guardrail_information")
    require(isinstance(records, list), "unknown_native_guardrail_missing")
    own = [r for r in records if isinstance(r, dict) and r.get("guardrail_name") == "owui_budget_usage"]
    require(len(own) == 1 and own[0].get("guardrail_action") == ("block" if unknown else "allow")
            and own[0].get("violation_categories") == (["usage_unavailable"] if unknown else []), "unknown_native_guardrail_telemetry")
    fee = own[0].get("guardrail_cost")
    require((fee is None or type(fee) in (int, float) and fee == 0)
            and own[0].get("guardrail_usage") is None, "unknown_guardrail_added_fee")
    if unknown:
        require(close_amount(row.get("spend"), Decimal(0)), "unknown_unexpected_native_amount")
    else:
        require(row.get("status") == "success" and close_amount(row.get("spend"), KNOWN_COST)
                and {k: row.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
                    == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}, "unknown_positive_row")
    history(previous["rows"], observation["rows"], {m.model: m.key_hash for m in budget.models}, calls)
    if unknown and target is not True: return None
    delta = Decimal(0) if unknown else KNOWN_COST
    if not close_amount(observation["user"].get("spend"), budget.spend + delta): return None
    if not all(close_amount(observation["keys"][m.model].get("spend"),
                            m.spend + (delta if m.model == scope["model"] else 0)) for m in budget.models): return None
    return observation, row


async def execute(receipt, *, diagnostic=None):
    require(not STATE.exists() and len({STATE, RECEIPT, fixture.OPERATOR_STATE, WEBUI_STATE}) == 4,
            "unknown_requires_fresh_private_state")
    operator, webui = fixture.read_private(fixture.OPERATOR_STATE), fixture.read_private(WEBUI_STATE)
    secret, viewer = os.environ.get("OWUI_BUDGET_GATEWAY_SECRET", ""), webui.get("cost_reader", {})
    require(bool(secret) and secret != operator.get("operator_token") and isinstance(viewer.get("key"), str),
            "unknown_private_authority")
    native = fixture.native_client();route = routing(native)
    info = native.ok("GET", "/key/info", query={"key": sha256(viewer["key"].encode()).hexdigest()}).get("info", {})
    require(info.get("user_id") == viewer.get("user_id") and info.get("allowed_routes") == [SESSION_ROUTE]
            and native.user_info(viewer["user_id"]).get("user_role") == "proxy_admin_viewer", "unknown_restricted_viewer")
    state = {"schema": 1, "proof": PROOF, "calls": [], "snapshots": [],
             "user_ids": {label: str(uuid4()) for label in ("A", "B")}};baseline_provider = provider();current_provider = baseline_provider
    def save(stage):
        receipt["stage"] = stage;state["stage"] = stage;encoded(state);fixture.write_private(STATE, state)
    save("preflight")
    async with ClientSession(trust_env=False) as session:
        admin = BudgetAdminClient(session, fixture.PROXY_URL, operator["operator_token"])
        async def before_write(): require(routing(native) == route, "unknown_route_drift")
        expected, initial, last = {}, {}, {}
        for label in ("A", "B"):
            budget = await admin.initialize_employee(state["user_ids"][label], tuple((a, Decimal(2)) for a in ALIASES), Decimal(6), secret,
                                                     before_write=before_write)
            expected[label] = budget;initial[label] = last[label] = snapshot(native, budget)
            require(not initial[label]["rows"], "unknown_fresh_history")
        state["initial"] = copy.deepcopy(initial);save("initialized")
        chats = {(label, alias): str(uuid4()) for label in expected for alias in ALIASES}
        for label, alias, denied in (("A", ALIASES[0], False), ("A", ALIASES[1], False), ("A", ALIASES[1], True),
                                    ("A", ALIASES[2], False), ("A", ALIASES[2], True), ("A", ALIASES[0], False), ("B", ALIASES[1], False)):
            if diagnostic is not None:
                diagnostic.update(attempt=len(state["calls"]) + 1, actor=label, model=ALIASES.index(alias) + 1)
            await before_write();budget = expected[label];unknown = alias != ALIASES[0]
            answer, chat = str(uuid4()), chats[label, alias]
            token = encode_call(secret, user_id=budget.user_id, model=alias, chat_id=chat, answer_id=answer,
                                root_chat_id=chat, root_answer_id=answer)
            claims = decode_call(token, secret, user_id=budget.user_id, model=alias)
            scope = {"schema": 1, "user_id": budget.user_id, "model": alias, "chat_id": chat, "answer_id": answer,
                     "root_chat_id": chat, "root_answer_id": answer, "call_id": claims["jti"], "category": "personal"}
            body = {"model": alias, "input": "Hi", "max_output_tokens": 16, "store": False, "stream": False}
            call = {"scope": scope, "body": body, "status": None, "response": None};state["calls"].append(call)
            save("dispatching")
            status, response, _ = native.request("POST", "/v1/responses", token=secret, body={**body,
                "litellm_metadata": {PROVENANCE_FIELD: token}}, extra_headers={USER_ID_HEADER: budget.user_id, TASK_HEADER: ""})
            call.update(status=status, response=response)
            save("response_received")
            key_hash = next(m.key_hash for m in budget.models if m.model == alias)
            if denied:
                require(status == 401 and response.get("error", {}).get("type") == "auth_error"
                        and response["error"].get("message") == BLOCK_MESSAGE, "unknown_fresh_denial")
                require(provider() == current_provider, "unknown_denial_dispatched")
            else:
                require(status == 200 and not response.get("error") and (response.get("usage") is None if unknown
                        else known_proxy_usage(response.get("usage"))), "unknown_response_usage")
                observed = provider();call["provider_observation"] = observed;save("provider_observed")
                def provider_ready():
                    current = provider();record = physical(current_provider, current, alias)
                    return (current, record) if record is not None else None
                observed, record = native.poll("unknown provider terminal", provider_ready);current_provider = observed
                call["provider"] = record
                observed_rows, row = native.poll("unknown Usage row", lambda: settled(native, budget, scope, key_hash, unknown,
                    last[label], [c for c in state["calls"] if c["scope"]["user_id"] == budget.user_id]))
                call["row_sha256"] = digest(row)
                models = tuple(replace(m, spend=m.spend + (0 if unknown else KNOWN_COST), blocked=True if unknown else m.blocked)
                               if m.model == alias else m for m in budget.models)
                expected[label] = replace(budget, spend=budget.spend + (0 if unknown else KNOWN_COST), models=models)
                try:
                    value = await read_cost_snapshot(session, base_url=fixture.PROXY_URL, read_key=viewer["key"],
                        user_id=budget.user_id, root_chat_id=chat, root_answer_id=answer, observed_call_ids=[scope["call_id"]])
                except CostReadError as error:
                    require(unknown and error.code == "usage_unavailable", "unknown_viewer_wrong_failure")
                else:
                    require(not unknown and value.complete and close_amount(value.answer.spend, KNOWN_COST)
                            and close_amount(value.chat.spend, expected[label].spend), "unknown_viewer_confirmed_unknown_or_wrong_amount")
            snapshots = {name: snapshot(native, value) for name, value in expected.items()}
            for name, value in expected.items():
                require(await admin.read_employee(value.user_id, ALIASES) == value, "unknown_budget_or_assignment_changed")
                policy = copy.deepcopy(protected(initial[name]))
                for m in value.models: policy[m.model]["key"]["blocked"] = m.blocked
                require(protected(snapshots[name]) == policy, "unknown_caps_or_policy_changed")
                history(last[name]["rows"], snapshots[name]["rows"], {m.model: m.key_hash for m in value.models},
                        [c for c in state["calls"] if c["scope"]["user_id"] == value.user_id])
            last = snapshots;state["snapshots"].append(snapshots);save("observed_attempt")
    require(len(state["calls"]) == 7 and len(current_provider["requests"]) == len(baseline_provider["requests"]) + 5,
            "unknown_final_attempts_or_dispatches")
    save("complete")
    candidate = dict(receipt, provider_dispatches=5, inference_attempts=7, known_positive_costs=[".166", ".166"],
        known_positive_total=".332", blocked_assignments=3, unknown_cost_finality=False, explicit_zero_runtime_qualified=False,
        browser_or_chat_ancestry_qualified=False, route_sha256=route, rows_sha256={n: digest(v["rows"]) for n, v in last.items()})
    modules = source_modules()
    candidate["source_sha256"] = {Path(sys.modules[n].__file__).name: sha256(Path(sys.modules[n].__file__).read_bytes()).hexdigest() for n in modules}
    candidate["mounted_source_sha256"] = {n: sha256(path.read_bytes()).hexdigest() for n, path in MOUNTED_SOURCES.items()}
    no_credentials(candidate, [secret, viewer["key"], *private_credentials(operator), *private_credentials(webui)])
    receipt.update(candidate, passed=True)
    return receipt


def main():
    receipt = {"schema": 1, "proof": PROOF, "passed": False, "stage": "preflight",
               "worker_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}
    available = not RECEIPT.exists() and not RECEIPT.is_symlink()
    diagnostic = {}
    try:
        require(available, "unknown_requires_new_safe_receipt");asyncio.run(execute(receipt, diagnostic=diagnostic))
    except ProofError as error:
        code = str(error)
        receipt.update(passed=False, failure=code if len(code) <= 128 and re.fullmatch(r"unknown_[a-z_]+", code)
                       else "unknown_native_contract_failed")
        receipt["diagnostic"] = failure_diagnostic(error, diagnostic)
    except BudgetAdminError as error:
        code = error.code
        receipt.update(passed=False, failure="unknown_native_" + code if isinstance(code, str) and len(code) <= 96
                       and re.fullmatch(r"[a-z][a-z0-9_]*", code) else "unknown_native_contract_failed")
        receipt["diagnostic"] = failure_diagnostic(error, diagnostic)
    except Exception as error:
        receipt.update(passed=False, failure="unknown_usage_unexpected_failure")
        receipt["diagnostic"] = failure_diagnostic(error, diagnostic)
    no_credentials(receipt)
    if available: fixture.write_private(RECEIPT, receipt)
    print(json.dumps(receipt, indent=2, allow_nan=False))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__": raise SystemExit(main())
