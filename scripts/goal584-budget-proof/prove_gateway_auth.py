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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("bootstrap", "run", "restart"))
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
        require(bool(master), "PROOF_MASTER_KEY is required")
        if args.phase == "bootstrap":
            bootstrap(args, master, receipt)
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
