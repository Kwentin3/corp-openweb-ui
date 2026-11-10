#!/usr/bin/env python3
"""Qualify the exact gateway hook with real native APIs in the disposable fixture.

Run bootstrap with stock auth, then run/restart with the configured hook. The
runtime mounts litellm_auth.py beside this driver. Headers simulate a trusted
OpenWebUI boundary; this is not WebUI, service exemption or ingress acceptance.
Raw virtual keys are written only to --private-state (0600 in a private directory).
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import stat
import sys

from prove_native_budgets import (
    CALL_COST, COMPLETION_TOKENS, MODELS, NativeProof, ProofError, VERSION,
    close_amount, require,
)


OPERATOR_ROUTES = [
    "/openapi.json", "/user/new", "/user/update", "/user/info", "/user/list",
    "/key/generate", "/key/update", "/key/block", "/key/info", "/key/list", "/spend/logs/v2",
    "/model/info",
]


def management_schema(proof: NativeProof) -> None:
    """Assert the actual served native request contracts before provisioning."""
    spec = proof.ok("GET", "/openapi.json")

    def fields(node: dict) -> set[str]:
        if "$ref" in node:
            target = spec
            for part in node["$ref"].removeprefix("#/").split("/"):
                target = target[part]
            return fields(target)
        result = set(node.get("properties", {}))
        for union in ("allOf", "anyOf", "oneOf"):
            for child in node.get(union, []):
                result.update(fields(child))
        return result

    for endpoint, required_fields in {
        "/user/new": {"user_role", "auto_create_key", "user_id"},
        "/key/generate": {"allowed_routes", "metadata", "key_alias", "user_id", "models"},
        "/key/block": {"key"},
    }.items():
        node = spec["paths"][endpoint]["post"]["requestBody"]["content"]["application/json"]["schema"]
        require(required_fields <= fields(node), "Native operator/assignment schema missing at " + endpoint)
    route = spec["paths"].get("/model/info", {})
    require(isinstance(route.get("get"), dict)
            and not ({"post", "put", "patch", "delete"} & route.keys()),
            "Native model-info route must remain read-only")
    proof.check("served_native_operator_and_assignment_schema")


def private_parent(path: Path) -> None:
    require(not path.is_symlink(), "Private state must not be a symlink")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(not path.parent.is_symlink() and
            stat.S_IMODE(path.parent.stat().st_mode) & 0o077 == 0,
            "Private state directory must have mode 0700 or stricter")


def write_private(path: Path, state: dict) -> None:
    private_parent(path)
    temporary = path.with_name(path.name + ".tmp-" + secrets.token_hex(6))
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def read_private(path: Path) -> dict:
    private_parent(path)
    require(path.is_file() and stat.S_IMODE(path.stat().st_mode) & 0o077 == 0,
            "Private state must exist with mode 0600 or stricter")
    state = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(state, dict) and state.get("schema") == 1,
            "Unsupported private proof state")
    return state


def bootstrap(args, master: str, receipt: dict) -> None:
    private_parent(args.private_state)
    require(not args.private_state.exists(), "Bootstrap requires a new private state file")
    proof = NativeProof(args.base_url, master, args.timeout, receipt)
    proof.schema()
    management_schema(proof)
    operator_user = proof.run_id + "-operator"
    operator_alias = proof.run_id + "-operator-management"
    proof.ok("POST", "/user/new", body={
        "user_id": operator_user, "user_role": "proxy_admin", "models": [],
        "auto_create_key": False, "send_invite_email": False,
    })
    generated = proof.ok("POST", "/key/generate", body={
        "user_id": operator_user, "key_alias": operator_alias,
        "models": [], "allowed_routes": OPERATOR_ROUTES,
    })
    token = generated.get("key")
    require(isinstance(token, str) and token.startswith("sk-"),
            "Native operator provisioning did not return a virtual key")
    user = proof.ok("GET", "/user/info", token=token,
                    query={"user_id": operator_user}).get("user_info", {})
    info = proof.ok("GET", "/key/info", token=token, query={"key": token}).get("info", {})
    require(user.get("user_role") == "proxy_admin" and user.get("user_id") == operator_user,
            "Operator role was not read back from the native user owner")
    require(info.get("user_id") == operator_user and info.get("allowed_routes") == OPERATOR_ROUTES,
            "Native operator key owner/route scope differs from provisioning")
    write_private(args.private_state, {
        "schema": 1, "stage": "bootstrap_complete", "run_id": proof.run_id,
        "users": proof.users, "started_at": proof.started_at.isoformat(),
        "operator_user": operator_user, "operator_alias": operator_alias,
        "operator_token": token,
    })
    proof.check("native_proxy_admin_operator_provisioned_and_read_back",
                user_id=operator_user, allowed_routes=OPERATOR_ROUTES)


class GatewayProof(NativeProof):
    def __init__(self, args, state: dict, gateway: str, actual_master: str, receipt: dict):
        # Operator is an actual generated native vkey, never a constructed auth role.
        super().__init__(args.base_url, state["operator_token"], args.timeout, receipt)
        from litellm_auth import USER_ID_HEADER, TASK_HEADER, assignment_alias, assignment_metadata
        self.user_header, self.task_header = USER_ID_HEADER, TASK_HEADER
        self.assignment_alias, self.assignment_metadata = assignment_alias, assignment_metadata
        self.gateway, self.actual_master, self.state = gateway, actual_master, state
        self.run_id, self.users = state["run_id"], state["users"]
        self.started_at = datetime.fromisoformat(state["started_at"])
        self.expected = state.get("expected", {})
        self.keys = {(entry["user"], entry["model"]): {**entry, "cap": Decimal(entry["cap"])}
                     for entry in state.get("keys", [])}
        self.receipt.update(run_id=self.run_id, users=self.users,
                            calls=state.get("calls", []), extra_denials=[])

    def request(self, method, path, *, token=None, body=None, query=None, extra_headers=None):
        if path == "/v1/chat/completions":
            owners = [user for (user, _), key in self.keys.items() if key["token"] == token]
            require(len(owners) == 1, "Gateway inference must select one known synthetic assignment")
            token = self.gateway
            extra_headers = {self.user_header: owners[0], self.task_header: ""}
        return super().request(method, path, token=token, body=body, query=query,
                               extra_headers=extra_headers)

    def schema(self):
        super().schema()
        management_schema(self)

    def operator_readback(self):
        user = self.ok("GET", "/user/info", query={"user_id": self.state["operator_user"]})["user_info"]
        info = self.ok("GET", "/key/info", query={"key": self.master_key})["info"]
        require(user.get("user_role") == "proxy_admin" and info.get("user_id") == user.get("user_id"),
                "Actual native operator identity was not preserved through the hook")
        require(info.get("allowed_routes") == OPERATOR_ROUTES,
                "Native operator allowed_routes changed")
        self.check("native_operator_management_auth_after_hook", user_id=user["user_id"])

    def setup(self):
        self.operator_readback()
        for user in self.users:
            self.ok("POST", "/user/new", body={
                "user_id": user, "user_role": "internal_user", "models": list(MODELS),
                "max_budget": float(4 * CALL_COST), "budget_duration": "30d",
                "auto_create_key": False, "send_invite_email": False,
            })
            for model in MODELS:
                alias = self.assignment_alias(user, model)
                generated = self.ok("POST", "/key/generate", body=self.assignment_body(user, model))
                token = generated.get("key")
                require(isinstance(token, str) and token.startswith("sk-"), "Native assignment key missing")
                self.keys[user, model] = {"token": token, "alias": alias,
                    "hash": hashlib.sha256(token.encode()).hexdigest(), "cap": 3 * CALL_COST}
                info = self.key_info(user, model)
                metadata = info.get("metadata") or {}
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)
                require(info.get("key_alias") == alias and isinstance(metadata, dict) and
                        all(metadata.get(k) == v for k, v in self.assignment_metadata(model).items()),
                        "Native canonical assignment metadata/alias readback differs")
        self.persisted()
        for user in self.users:
            info = self.user_info(user)
            require(len(info.get("keys", [])) == 2 and close_amount(info.get("max_budget"), 4 * CALL_COST),
                    "Synthetic personal cap or exact two-key assignment count differs")
        self.check("four_canonical_native_user_model_assignments")
        self.auth_denials()

    def assignment_body(self, user, model):
        return {"user_id": user, "models": [model],
                "key_alias": self.assignment_alias(user, model), "metadata": self.assignment_metadata(model),
                "max_budget": float(3 * CALL_COST), "budget_duration": "30d",
                "allowed_routes": ["llm_api_routes"]}

    def denied(self, name, *, token, headers=None, path="/v1/chat/completions", method="POST", body=None, query=None):
        if body is None and method == "POST":
            body = {"model": MODELS[0], "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": COMPLETION_TOKENS, "stream": False}
        status, _, _ = NativeProof.request(self, method, path, token=token, extra_headers=headers,
                                           body=body, query=query)
        require(status in (401, 403), "Expected authentication/authorization denial for " + name + "; HTTP " + str(status))
        self.receipt["extra_denials"].append({"name": name, "http_status": status, "outcome": "denied"})
        self.persisted()

    def auth_denials(self):
        user = self.users[0]
        headers = {self.user_header: user, self.task_header: ""}
        self.denied("wrong_gateway_secret", token="wrong-synthetic-gateway-bearer", headers=headers)
        self.denied("missing_task_header", token=self.gateway, headers={self.user_header: user})
        self.denied("nonempty_task_header", token=self.gateway,
                    headers={**headers, self.task_header: "title_generation"})
        self.denied("unassigned_user", token=self.gateway,
                    headers={**headers, self.user_header: self.run_id + "-unassigned"})
        self.denied("employee_vkey_cannot_manage", token=self.keys[user, MODELS[0]]["token"],
                    path="/user/update", body={"user_id": user, "max_budget": 99})
        self.denied("operator_vkey_cannot_infer", token=self.master_key)
        self.denied("shared_gateway_cannot_manage", token=self.gateway, headers=headers,
                    path="/user/update", body={"user_id": user, "max_budget": 99})
        self.denied("actual_stock_master_rejected", token=self.actual_master, method="GET",
                    path="/user/info", query={"user_id": user})
        require(close_amount(self.user_info(user).get("max_budget"), 4 * CALL_COST),
                "A forbidden management request changed the personal cap")
        before = len(self.user_info(user).get("keys", []))
        status, payload, _ = self.request("POST", "/key/generate", body=self.assignment_body(user, MODELS[0]))
        error = payload.get("error") or {}
        require(status == 400 and "already exists" in str(error.get("message", "")),
                "Expected native duplicate-alias provisioning rejection")
        require(len(self.user_info(user).get("keys", [])) == before == 2,
                "Duplicate provisioning changed the native assignment count")
        self.receipt["extra_denials"].append({"name": "native_duplicate_assignment_creation_rejected",
                                              "http_status": status, "outcome": "denied"})
        self.persisted()

    def private_state(self):
        return {**self.state, "stage": "run_complete", "expected": self.expected,
                "calls": self.receipt["calls"], "keys": [
                    {**key, "user": user, "model": model, "cap": str(key["cap"])}
                    for (user, model), key in self.keys.items()]}

    def restart(self):
        self.schema()
        self.operator_readback()
        require(len(self.expected) == 7, "Cold restart requires seven previously qualified calls")
        self.persisted()
        for user, cap in zip(self.users, (Decimal("1.20"), Decimal("0.80"))):
            require(close_amount(self.user_info(user).get("max_budget"), cap),
                    "Native personal cap did not survive cold restart")
        original_calls = self.receipt["calls"]
        self.receipt["calls"] = []
        try:
            self.infer(self.users[0], MODELS[1], blocked_scope="user")
            self.receipt["restart_denials"] = self.receipt["calls"]
        finally:
            self.receipt["calls"] = original_calls
        self.check("cold_restart_preserves_native_spend_keys_logs_and_cap", successful_calls=7)


async def stream_ledger(args, state, gateway, receipt):
    """One actual header-only cancellation; native APIs/storage remain owners."""
    import asyncio
    import time
    from dataclasses import replace
    from uuid import uuid4
    from aiohttp import ClientSession, ClientTimeout
    from employee_budget_admin_client import BudgetAdminClient
    from employee_budget_cost_readback import CostReadError, SESSION_ROUTE, read_cost_snapshot
    from litellm_auth import PROVENANCE_FIELD, TASK_HEADER, USER_ID_HEADER
    from provenance import decode_call, encode_call
    from prove_native_budgets import protected_r

    native = NativeProof(args.base_url, state["operator_token"], 5, receipt)
    native.poll_deadline = time.monotonic() + 90
    user, chat, answer = (str(uuid4()) for _ in range(3))
    receipt.update(users=[user], stage="preflight", scope="actual_native_stream_cancellation_storage_no_WebUI",
                   provider_boundary="actual_lifecycle_and_context_observed_by_this_phase")
    task = baseline = None
    async with ClientSession(trust_env=False, timeout=ClientTimeout(total=5)) as session:
        async def provider(body=None):
            async with session.request("GET" if body is None else "POST", "http://provider:8000/__proof/" +
                    ("requests" if body is None else "control"), json=body, allow_redirects=False) as response:
                raw = await response.content.read(2 * 1024 * 1024 + 1)
                require(response.status == 200 and len(raw) <= 2 * 1024 * 1024, "stream_ledger_provider_transport")
                return json.loads(raw)
        def routing():
            rows = native.ok("GET", "/model/info").get("data", [])
            for model, wire in zip(MODELS, ("goal584-fake-a", "goal584-fake-b")):
                found = [row for row in rows if row.get("model_name") == model]
                require(len(found) == 1, "stream_ledger_ambiguous_route")
                params, info = found[0].get("litellm_params", {}), found[0].get("model_info", {})
                require(params.get("model") == "openai/" + wire and params.get("api_base") == "http://provider:8000/v1"
                        and info.get("id") == "goal584-deployment-" + model[-1] and info.get("mode") == "chat"
                        and info.get("input_cost_per_token") == .01 and info.get("output_cost_per_token") == .02,
                        "stream_ledger_route_or_rates")
        async def before_write(): routing()
        def snapshot():
            return native.user_info(user), {m.model: native.ok("GET", "/key/info", query={"key": m.key_hash})["info"] for m in budget.models}
        def body_for(answer_id):
            token = encode_call(gateway, user_id=user, chat_id=chat, answer_id=answer_id,
                                root_chat_id=chat, root_answer_id=answer, model=MODELS[0])
            return {"model": MODELS[0], "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5,
                    "stream": True, "litellm_metadata": {PROVENANCE_FIELD: token}}, decode_call(token, gateway, user_id=user, model=MODELS[0])
        try:
            async with asyncio.timeout(90):
                native.schema();routing()
                require(native.user_info(state["operator_user"]).get("user_role") == "proxy_admin", "stream_ledger_operator")
                admin = BudgetAdminClient(session, args.base_url, state["operator_token"])
                budget = await admin.initialize_employee(user, tuple((m, Decimal(1)) for m in MODELS), Decimal(2), gateway, before_write=before_write)
                before_user, before_keys = snapshot()
                require(not native.logs(user), "stream_ledger_fresh_history")
                viewer = str(uuid4())
                native.ok("POST", "/user/new", body={"user_id": viewer, "user_role": "proxy_admin_viewer", "models": [], "auto_create_key": False})
                read_key = native.ok("POST", "/key/generate", body={"user_id": viewer, "models": [], "allowed_routes": [SESSION_ROUTE]})["key"]
                require(native.user_info(viewer).get("user_role") == "proxy_admin_viewer" and
                        native.ok("GET", "/key/info", query={"key": read_key})["info"].get("allowed_routes") == [SESSION_ROUTE], "stream_ledger_reader_scope")
                baseline = await provider();require(baseline.get("synthetic") is True and baseline.get("requests") == [], "stream_ledger_fresh_provider")
                await provider({"before_first_chunk_delay_ms": 10000})
                body, claims = body_for(answer)
                headers = {"Authorization": "Bearer " + gateway, USER_ID_HEADER: user, TASK_HEADER: ""}
                receipt.update(stage="dispatching", call_id=claims["jti"], user_id=user, root_chat_id=chat, root_answer_id=answer, model=MODELS[0])
                task = asyncio.ensure_future(session.post(args.base_url + "/v1/chat/completions", json=body, headers=headers,
                                                         allow_redirects=False, timeout=ClientTimeout(total=20)))
                receipt["last_window_observation"] = {"provider_requests": None, "lifecycle": None,
                    "downstream_headers_seen": False, "downstream_http_status": None}
                async with asyncio.timeout(8):
                    while True:
                        observation = await provider();records = observation.get("requests", [])
                        ready = task.done() and not task.cancelled() and task.exception() is None
                        receipt["last_window_observation"] = {"provider_requests": len(records),
                            "lifecycle": {k: records[0].get("lifecycle", {}).get(k) for k in
                                ("headers_sent", "chunks_sent", "usage_sent", "terminal", "response_status")} if records else None,
                            "downstream_headers_seen": ready, "downstream_http_status": task.result().status if ready else None}
                        require(len(records) <= 1, "stream_ledger_duplicate_dispatch")
                        if records and records[0].get("lifecycle", {}).get("headers_sent") is True: break
                        await asyncio.sleep(.05)
                life = records[0]["lifecycle"]
                wire = records[0].get("body", {})
                require(wire.get("model") == "goal584-fake-a" and wire.get("messages") == body["messages"]
                        and wire.get("max_tokens") == 5 and wire.get("stream") is True and not wire.get("tools"), "stream_ledger_provider_context")
                require(life.get("response_status") == 200 and life.get("chunks_sent") == 0 and life.get("usage_sent") is False and life.get("terminal") is False,
                        "stream_ledger_cancel_window")
                receipt.update(downstream_headers_seen=receipt["last_window_observation"]["downstream_headers_seen"],
                               downstream_http_status=receipt["last_window_observation"]["downstream_http_status"])
                if task.done():
                    require(task.result().status == 200, "stream_ledger_dispatch_http_" + str(task.result().status))
                    task.result().close()
                else: task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                receipt.update(stage="cancelled", cancelled_after_headers_before_chunk=True,
                    provider_at_cancel={k: life.get(k) for k in ("headers_sent", "chunks_sent", "usage_sent", "terminal", "response_status")})
                key_hash = next(m.key_hash for m in budget.models if m.model == MODELS[0])
                async with asyncio.timeout(min(args.timeout, 30)):
                    while True:
                        after_user, after_keys = snapshot();rows = native.logs(user)
                        found = []
                        for row in rows:
                            metadata = row.get("metadata") or {}
                            if isinstance(metadata, str): metadata = json.loads(metadata)
                            scope = metadata.get("spend_logs_metadata", {}).get("owui_budget", {})
                            if scope.get("call_id") == claims["jti"]: found.append((row, metadata, scope))
                        receipt["last_storage_observation"] = {"native_rows": len(rows), "matching_rows": len(found),
                            "statuses": [row.get("status") for row in rows],
                            "target_blocked": after_keys[MODELS[0]].get("blocked"),
                            "control_blocked": after_keys[MODELS[1]].get("blocked")}
                        if found and after_keys[MODELS[0]].get("blocked") is True: break
                        await asyncio.sleep(1)
                require(len(found) == 1, "stream_ledger_duplicate_row")
                row, metadata, scope = found[0]
                require(row.get("status") == "failure" and row.get("user") == user and row.get("api_key") == key_hash
                        and row.get("model_group") == MODELS[0] and row.get("model_id") == "goal584-deployment-a"
                        and scope == {"schema": 1, "user_id": user, "chat_id": chat, "answer_id": answer, "root_chat_id": chat,
                                      "root_answer_id": answer, "call_id": claims["jti"], "model": MODELS[0], "category": "personal"}, "stream_ledger_failure_row_binding")
                own = [g for g in (metadata.get("guardrail_information") or []) if isinstance(g, dict) and g.get("guardrail_name") == "owui_budget_usage"]
                require(not own or len(own) == 1 and own[0].get("guardrail_action") == "block" and own[0].get("violation_categories") == ["usage_unavailable"], "stream_ledger_unknown_marker")
                receipt.update(target_key_hash=key_hash, native_unknown_marker_present=bool(own), native_failure_row_sha256=hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest())
                try:
                    await read_cost_snapshot(session, base_url=args.base_url, read_key=read_key, user_id=user,
                        root_chat_id=chat, root_answer_id=answer, observed_call_ids=[claims["jti"]], wait_seconds=0)
                except CostReadError as error:
                    require(error.code in ("usage_unavailable", "accounting_unavailable"), "stream_ledger_reader_wrong_failure")
                    receipt["reader_error"] = error.code
                else: require(False, "stream_ledger_unknown_became_amount")
                denied_body, _ = body_for(str(uuid4()))
                status, denied, _ = native.request("POST", "/v1/chat/completions", token=gateway, body=denied_body,
                                                  extra_headers={USER_ID_HEADER: user, TASK_HEADER: ""})
                require(status == 401 and denied.get("error", {}).get("type") == "auth_error", "stream_ledger_fresh_denial")
                require(len((await provider())["requests"]) == 1, "stream_ledger_denial_dispatched")
                after_user, after_keys = snapshot()
                for model in MODELS:
                    expected = protected_r(before_user, before_keys[model])
                    if model == MODELS[0]: expected["key"]["blocked"] = True
                    require(protected_r(after_user, after_keys[model]) == expected, "stream_ledger_caps_or_control_changed")
                observed = await admin.read_employee(user, MODELS)
                target = next(m for m in observed.models if m.model == MODELS[0])
                require(observed.spend >= budget.spend and target.spend >= next(m.spend for m in budget.models if m.model == MODELS[0]), "stream_ledger_native_counters_decreased")
                require(observed == replace(budget, spend=observed.spend, models=tuple(
                    replace(m, blocked=True, spend=target.spend) if m.model == MODELS[0] else m for m in budget.models)), "stream_ledger_native_assignment_or_control_changed")
                receipt.update(stage="verified", failure_row_bound=True, target_blocked=True, caps_and_control_preserved=True,
                               unknown_never_zero=True, denied_http=status, provider_dispatches=1)
        finally:
            async with asyncio.timeout(12):
                if task is not None:
                    if task.done() and not task.cancelled() and task.exception() is None: task.result().close()
                    else: task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                if baseline is not None:
                    await provider({"before_first_chunk_delay_ms": baseline["control"].get("before_first_chunk_delay_ms")})
                    while True:
                        final = await provider()
                        if all(r.get("lifecycle", {}).get("terminal") is True for r in final.get("requests", [])): break
                        await asyncio.sleep(.1)
                    require(final["control"] == baseline["control"], "stream_ledger_provider_restore")
                    receipt.update(provider_control_restored=True, provider_terminal=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("bootstrap", "run", "restart", "stream-ledger"))
    parser.add_argument("--private-state", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:4000")
    parser.add_argument("--timeout", type=float, default=45)
    args = parser.parse_args()
    receipt = {"proof": "goal584-gateway-auth", "phase": args.phase, "passed": False,
               "scope": "native_gateway_with_simulated_trusted_owui_headers",
               "expected_litellm_version": VERSION,
               "not_qualified": ["actual_WebUI", "GUI", "ingress_provenance", "service_exemption",
                                 "model_discovery", "concurrency", "duplicate_DB_corruption_recovery",
                                 "gateway_multiple_assignment_lookup_guard"],
               "provider_boundary": "separate actual-provider receipt comparison required",
               "started_at_utc": datetime.now(timezone.utc).isoformat()}
    try:
        require(math.isfinite(args.timeout) and 1 <= args.timeout <= 120, "Invalid persistence timeout")
        require(args.private_state.resolve() != args.receipt.resolve(), "Private state and safe receipt must differ")
        master = os.environ.get("PROOF_MASTER_KEY")
        require(bool(master) or args.phase == "stream-ledger", "PROOF_MASTER_KEY is required")
        if args.phase == "bootstrap":
            bootstrap(args, master, receipt)
        elif args.phase == "stream-ledger":
            import asyncio
            state = read_private(args.private_state)
            require(state.get("stage") == "bootstrap_complete", "Private proof state has the wrong phase")
            gateway = os.environ.get("OWUI_BUDGET_GATEWAY_SECRET")
            require(bool(gateway) and gateway != state.get("operator_token"), "A distinct gateway secret is required")
            asyncio.run(stream_ledger(args, state, gateway, receipt))
        else:
            state = read_private(args.private_state)
            required_stage = "bootstrap_complete" if args.phase == "run" else "run_complete"
            require(state.get("stage") == required_stage, "Private proof state has the wrong phase")
            gateway = os.environ.get("OWUI_BUDGET_GATEWAY_SECRET")
            require(bool(gateway) and gateway != master, "A distinct OWUI_BUDGET_GATEWAY_SECRET is required")
            proof = GatewayProof(args, state, gateway, master, receipt)
            if args.phase == "run":
                proof.run()
                require(len(proof.expected) == 7, "Expected seven native gateway successes")
                write_private(args.private_state, proof.private_state())
            else:
                proof.restart()
        receipt["passed"] = True
    except ProofError as error:
        receipt["failure"] = str(error)
    except Exception as error:
        # Never render arbitrary API, URL, local-state or exception data containing keys.
        receipt["failure"] = "Unexpected gateway proof error: " + type(error).__name__
    receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    rendered = json.dumps(receipt, indent=2, allow_nan=False)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
