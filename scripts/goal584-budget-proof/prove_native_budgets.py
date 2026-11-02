#!/usr/bin/env python3
"""Qualify native LiteLLM 1.105.1 scalar budgets against a disposable local fixture.

Requires PROOF_MASTER_KEY (or GOAL584_MASTER_KEY) and --base-url (or
GOAL584_BASE_URL). The isolated Compose fixture mounts this driver into proxy:
docker compose --env-file <protected-env> -f compose/goal584.native-budget-proof.yml
exec -T proxy python -B /proof/prove_native_budgets.py --base-url http://127.0.0.1:4000

The fixture must route goal584-a/b exclusively to its deterministic mock provider:
10 prompt + 5 completion tokens, input $0.01/token, output $0.02/token.
Only stdlib is required. This driver creates synthetic users and virtual keys and
leaves them in the disposable database for inspection. It never writes credentials
or response texts into receipts. It does not qualify a trusted key-selection
adapter, production integration, Responses, concurrency, or a GUI.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import uuid


VERSION = "1.105.1"
# Pinned litellm/__init__.py:409; BudgetExceededError and auth conversion preserve it.
BUDGET_EXCEEDED_STATUS = 422
MODELS = ("goal584-a", "goal584-b")
PROMPT_TOKENS = 10
COMPLETION_TOKENS = 5
CALL_COST = Decimal("0.20")
TOLERANCE = Decimal("0.00000001")


class ProofError(Exception):
    """An explicitly safe error message suitable for the receipt."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProofError(message)


def amount(value: Any) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ProofError("Native amount is missing or invalid") from None
    require(result.is_finite(), "Native amount is not finite")
    return result


def close_amount(actual: Any, expected: Decimal) -> bool:
    return abs(amount(actual) - expected) <= TOLERANCE


def loopback_url(value: str) -> str:
    parsed = urlsplit(value)
    require(parsed.scheme == "http", "Proof target must use local HTTP")
    require(not parsed.username and not parsed.password, "Credentials in base URL are forbidden")
    require(not parsed.query and not parsed.fragment and parsed.path in ("", "/"),
            "Proof base URL must contain only scheme, loopback host and port")
    try:
        local = parsed.hostname == "localhost" or ipaddress.ip_address(parsed.hostname or "").is_loopback
        port = parsed.port
    except ValueError:
        raise ProofError("Proof target must be a loopback address") from None
    require(local and port is not None, "Proof target must be loopback with an explicit port")
    return value.rstrip("/")


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProofError("HTTP redirect refused")


class NativeProof:
    def __init__(self, base_url: str, master_key: str, timeout: float, receipt: dict):
        self.base_url = loopback_url(base_url)
        self.master_key = master_key
        self.timeout = timeout
        self.receipt = receipt
        self.opener = build_opener(ProxyHandler({}), NoRedirects())
        self.run_id = "goal584-" + uuid.uuid4().hex[:12]
        self.users = [self.run_id + "-u1", self.run_id + "-u2"]
        self.keys: dict[tuple[str, str], dict] = {}
        self.expected: dict[str, dict] = {}
        self.started_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        self.poll_deadline: float | None = None
        self.receipt.update(run_id=self.run_id, users=self.users, checks=[], calls=[])

    def request(self, method: str, path: str, *, token: str | None = None,
                body: dict | None = None, query: dict | None = None) -> tuple[int, dict, Any]:
        url = self.base_url + path + ("?" + urlencode(query) if query else "")
        headers = {"Authorization": "Bearer " + (token or self.master_key),
                   "Content-Type": "application/json"}
        data = None if body is None else json.dumps(body, allow_nan=False).encode("utf-8")
        req = Request(url, data=data, headers=headers, method=method)
        remaining = self.timeout if self.poll_deadline is None else self.poll_deadline - time.monotonic()
        require(remaining > 0, "Native persistence polling deadline expired")
        try:
            response = self.opener.open(req, timeout=min(remaining, 20))
        except HTTPError as exc:
            response = exc
        except (URLError, TimeoutError, OSError):
            raise ProofError("HTTP transport failed at " + path) from None
        with response:
            status = response.code
            response_headers = response.headers
            raw = response.read(4 * 1024 * 1024 + 1)
        require(len(raw) <= 4 * 1024 * 1024, "HTTP response exceeded proof size bound")
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeError):
            raise ProofError("Expected JSON at " + path) from None
        require(isinstance(payload, dict), "Expected JSON object at " + path)
        return status, payload, response_headers

    def ok(self, method: str, path: str, **kwargs) -> dict:
        status, payload, _ = self.request(method, path, **kwargs)
        require(status == 200, "Unexpected HTTP " + str(status) + " at " + path)
        return payload

    def check(self, name: str, **facts) -> None:
        self.receipt["checks"].append({"name": name, "passed": True, **facts})

    def poll(self, label: str, condition):
        deadline = time.monotonic() + self.timeout
        interval = 0.1
        previous_deadline = self.poll_deadline
        self.poll_deadline = deadline
        try:
            while True:
                result = condition()
                if result is not None:
                    return result
                remaining = deadline - time.monotonic()
                require(remaining > 0, "Timed out waiting for native " + label)
                # Condition-based bounded polling for async DB writes/cache invalidation.
                time.sleep(min(interval, remaining))
                interval = min(interval * 1.5, 1.0)
        finally:
            self.poll_deadline = previous_deadline

    def schema(self) -> None:
        spec = self.ok("GET", "/openapi.json")
        require(spec.get("info", {}).get("version") == VERSION,
                "Proxy OpenAPI version is not exactly " + VERSION)
        endpoints = {"/user/new": "post", "/user/update": "post",
                     "/key/generate": "post", "/key/update": "post",
                     "/key/info": "get", "/user/info": "get",
                     "/spend/logs/v2": "get", "/v1/chat/completions": "post"}
        for path, method in endpoints.items():
            require(method in spec.get("paths", {}).get(path, {}),
                    "Required native API missing: " + path)

        def fields(schema: dict) -> set[str]:
            if "$ref" in schema:
                target = spec
                for component in schema["$ref"].removeprefix("#/").split("/"):
                    target = target[component]
                return fields(target)
            result = set(schema.get("properties", {}))
            for keyword in ("allOf", "anyOf", "oneOf"):
                for child in schema.get(keyword, []):
                    result.update(fields(child))
            return result

        for path, required in {
            "/user/new": {"user_id", "models", "max_budget", "budget_duration", "auto_create_key"},
            "/key/generate": {"user_id", "models", "max_budget", "budget_duration", "key_alias"},
            "/key/update": {"key", "max_budget"},
            "/user/update": {"user_id", "max_budget"},
        }.items():
            schema = spec["paths"][path]["post"]["requestBody"]["content"]["application/json"]["schema"]
            require(required <= fields(schema), "Required native schema fields missing: " + path)
        self.check("exact_version_and_native_api_schema", version=VERSION)

    def setup(self) -> None:
        for user in self.users:
            self.ok("POST", "/user/new", body={
                "user_id": user, "user_role": "internal_user", "models": list(MODELS),
                "max_budget": float(4 * CALL_COST), "budget_duration": "30d",
                "auto_create_key": False, "send_invite_email": False,
            })
            for model in MODELS:
                alias = user + "-" + model
                created = self.ok("POST", "/key/generate", body={
                    "user_id": user, "models": [model], "key_alias": alias,
                    "max_budget": float(3 * CALL_COST), "budget_duration": "30d",
                    "allowed_routes": ["llm_api_routes"],
                })
                token = created.get("key")
                require(isinstance(token, str) and token.startswith("sk-"),
                        "Native generation did not return a virtual key")
                self.keys[user, model] = {"token": token, "alias": alias,
                                         "hash": hashlib.sha256(token.encode()).hexdigest(),
                                         "cap": 3 * CALL_COST}
        self.persisted()
        for user in self.users:
            info = self.user_info(user)
            require(len(info.get("keys", [])) == 2,
                    "Synthetic user has unexpected keys; auto-created key must be absent")
            require(close_amount(info.get("max_budget"), 4 * CALL_COST),
                    "Native personal cap was not persisted")
        self.check("native_users_and_single_model_keys_without_teams", users=2, keys=4)

    def user_info(self, user: str) -> dict:
        payload = self.ok("GET", "/user/info", query={"user_id": user})
        info = payload.get("user_info")
        require(isinstance(info, dict), "Native /user/info missing user_info")
        return {**info, "keys": payload.get("keys", [])}

    def key_info(self, user: str, model: str) -> dict:
        payload = self.ok("GET", "/key/info", query={"key": self.keys[user, model]["token"]})
        info = payload.get("info")
        require(isinstance(info, dict), "Native /key/info missing info")
        require(info.get("user_id") == user and info.get("models") == [model],
                "Native key owner or model allowlist mismatch")
        require(info.get("team_id") is None, "Synthetic key unexpectedly belongs to a team")
        require(not info.get("model_max_budget"), "Proof unexpectedly uses premium model_max_budget")
        require(info.get("budget_duration") == "30d" and info.get("budget_reset_at"),
                "Native key monthly reset was not persisted")
        return info

    def logs(self, user: str) -> list[dict]:
        rows = []
        page = 1
        while True:
            payload = self.ok("GET", "/spend/logs/v2", query={
                "user_id": user, "page": page, "page_size": 100,
                "start_date": self.started_at.strftime("%Y-%m-%d %H:%M:%S"),
                "end_date": (datetime.now(timezone.utc) + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S"),
            })
            data = payload.get("data")
            require(isinstance(data, list) and all(isinstance(row, dict) for row in data),
                    "Native spend log page is malformed")
            rows.extend(data)
            pages = payload.get("total_pages")
            require(isinstance(pages, int) and 0 <= pages <= 10,
                    "Native spend log page count exceeded synthetic proof bound")
            if page >= pages:
                break
            page += 1
        require(all(row.get("user") == user for row in rows), "Native spend API crossed user scope")
        return rows

    def persisted(self) -> None:
        def condition():
            observed = {"observed_at_utc": datetime.now(timezone.utc).isoformat(),
                        "source_endpoints": ["/user/info", "/key/info", "/spend/logs/v2"],
                        "users": [], "keys": [], "positive_spend_logs": []}
            for user in self.users:
                expected = {root: item for root, item in self.expected.items() if item["user"] == user}
                rows = self.logs(user)
                found = {}
                for row in rows:
                    if amount(row.get("spend", 0)) <= 0:
                        continue
                    meta = row.get("metadata") or {}
                    if isinstance(meta, str):
                        meta = json.loads(meta)
                    custom = meta.get("spend_logs_metadata") or {}
                    root = custom.get("root_answer_id")
                    require(root in expected, "Unexpected positive native spend row for synthetic user")
                    require(root not in found, "Native spend duplicated a root answer")
                    item = expected[root]
                    key = self.keys[user, item["model"]]
                    require(row.get("api_key") == key["hash"], "Spend row attributed to wrong native key")
                    require(row.get("model_group") == item["model"], "Spend row has wrong model alias")
                    require(custom.get("chat_id") == item["chat_id"] and custom.get("call_kind") == "synthetic_chat",
                            "Native spend metadata lineage mismatch")
                    require(row.get("prompt_tokens") == PROMPT_TOKENS and
                            row.get("completion_tokens") == COMPLETION_TOKENS and row.get("total_tokens") == 15,
                            "Persisted native usage differs from fixture usage")
                    require(close_amount(row.get("spend"), CALL_COST), "Native spend differs from declared fixture prices")
                    require(row.get("request_id") == item["provider_response_id"],
                            "Native spend request ID differs from synthetic provider response ID")
                    found[root] = row
                    observed["positive_spend_logs"].append({
                        "request_id": row["request_id"], "user": row["user"],
                        "key_alias": key["alias"], "model_group": row["model_group"],
                        "spend_usd": str(amount(row["spend"])),
                        "prompt_tokens": row["prompt_tokens"], "completion_tokens": row["completion_tokens"],
                        "total_tokens": row["total_tokens"],
                        "metadata": {"spend_logs_metadata": {
                            "chat_id": custom["chat_id"], "root_answer_id": custom["root_answer_id"],
                            "call_kind": custom["call_kind"]}},
                    })
                if len(found) != len(expected):
                    return None
                user_info = self.user_info(user)
                require(user_info.get("user_id") == user and not user_info.get("teams"),
                        "Native user identity/team scope mismatch")
                require(user_info.get("budget_duration") == "30d" and user_info.get("budget_reset_at"),
                        "Native user monthly reset was not persisted")
                if not close_amount(user_info.get("spend"), len(expected) * CALL_COST):
                    return None
                observed["users"].append({
                    "user_id": user_info["user_id"], "spend_usd": str(amount(user_info["spend"])),
                    "max_budget_usd": str(amount(user_info.get("max_budget"))),
                    "budget_duration": user_info["budget_duration"],
                    "budget_reset_at": user_info["budget_reset_at"],
                })
                for model in MODELS:
                    info = self.key_info(user, model)
                    count = sum(item["model"] == model for item in expected.values())
                    if not close_amount(info.get("spend"), count * CALL_COST):
                        return None
                    if not close_amount(info.get("max_budget"), self.keys[user, model]["cap"]):
                        return None
                    observed["keys"].append({
                        "key_alias": self.keys[user, model]["alias"], "user_id": info["user_id"],
                        "models": info["models"], "team_id": info.get("team_id"),
                        "spend_usd": str(amount(info["spend"])),
                        "max_budget_usd": str(amount(info["max_budget"])),
                        "budget_duration": info["budget_duration"], "budget_reset_at": info["budget_reset_at"],
                    })
            # Publish only a complete, verified readback; partial polling snapshots are not evidence.
            self.receipt["native_observed"] = observed
            return True
        self.poll("spend logs and user/key totals", condition)

    def infer(self, user: str, model: str, *, blocked_scope: str | None = None,
              forged_user: str | None = None) -> None:
        root = self.run_id + "-answer-" + uuid.uuid4().hex[:12]
        chat = user + "-chat"
        key = self.keys[user, model]
        body = {
            "model": model, "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": COMPLETION_TOKENS, "stream": False,
            "metadata": {"session_id": chat, "spend_logs_metadata": {
                "chat_id": chat, "root_answer_id": root, "call_kind": "synthetic_chat"}},
        }
        if forged_user:
            # Body 'user' may represent an end user; it must not replace the key owner.
            body["user"] = forged_user
            body["metadata"].update(user_id=forged_user, user_api_key_user_id=forged_user)
        status, payload, headers = self.request("POST", "/v1/chat/completions", token=key["token"], body=body)
        if blocked_scope:
            error = payload.get("error")
            require(status == BUDGET_EXCEEDED_STATUS and isinstance(error, dict) and error.get("type") == "budget_exceeded",
                    "Expected native budget rejection; received HTTP " + str(status))
            marker = "Key=" + key["alias"] if blocked_scope == "key" else "User=" + user
            require(marker in str(error.get("message", "")), "Budget rejection did not identify expected native scope")
            self.receipt["calls"].append({"user": user, "model": model, "outcome": "budget_blocked",
                                          "scope": blocked_scope, "http_status": status,
                                          "error_type": error["type"]})
        else:
            require(status == 200, "Native inference unexpectedly returned HTTP " + str(status))
            provider_response_id = payload.get("id")
            require(isinstance(provider_response_id, str) and provider_response_id.startswith("chatcmpl-goal584-")
                    and len(provider_response_id.removeprefix("chatcmpl-goal584-")) == 32
                    and all(char in "0123456789abcdef" for char in provider_response_id.removeprefix("chatcmpl-goal584-")),
                    "Native success did not return the synthetic provider response ID")
            require(all(item.get("provider_response_id") != provider_response_id for item in self.expected.values()),
                    "Native success duplicated a synthetic provider response ID")
            usage = payload.get("usage", {})
            require(usage.get("prompt_tokens") == PROMPT_TOKENS and
                    usage.get("completion_tokens") == COMPLETION_TOKENS and usage.get("total_tokens") == 15,
                    "Native response usage differs from deterministic fixture")
            cost_header = headers.get("x-litellm-response-cost")
            if cost_header not in (None, "", "None"):
                require(close_amount(cost_header, CALL_COST), "Native response cost header differs from fixture price")
            self.expected[root] = {"user": user, "model": model, "chat_id": chat,
                                   "provider_response_id": provider_response_id}
            self.receipt["calls"].append({"user": user, "model": model, "root_answer_id": root,
                                          "provider_response_id": provider_response_id,
                                          "outcome": "success", "prompt_tokens": PROMPT_TOKENS,
                                          "completion_tokens": COMPLETION_TOKENS,
                                          "expected_cost_usd": str(CALL_COST),
                                          "forged_body_identity_sent": forged_user is not None,
                                          "native_cost_header_present": cost_header not in (None, "", "None")})
        self.persisted()

    def run(self) -> None:
        self.schema()
        self.setup()
        user1, user2 = self.users
        self.infer(user1, MODELS[0], forged_user=user2)
        self.check("body_user_metadata_does_not_replace_native_key_owner")
        for _ in range(2):
            self.infer(user1, MODELS[0])
        self.infer(user1, MODELS[0], blocked_scope="key")
        self.infer(user1, MODELS[1])
        self.check("model_key_cap_blocks_a_while_b_works", model_cap_usd="0.60")
        self.infer(user1, MODELS[1], blocked_scope="user")
        self.infer(user2, MODELS[0])
        self.check("personal_cap_blocks_remaining_b_and_other_user_is_independent", personal_cap_usd="0.80")
        self.ok("POST", "/user/update", body={"user_id": user1, "max_budget": 1.20})
        key = self.keys[user1, MODELS[0]]
        self.ok("POST", "/key/update", body={"key": key["token"], "max_budget": 1.00})
        key["cap"] = Decimal("1.00")

        def updated_caps():
            user = self.user_info(user1)
            a = self.key_info(user1, MODELS[0])
            return True if close_amount(user.get("max_budget"), Decimal("1.20")) and close_amount(a.get("max_budget"), Decimal("1.00")) else None
        self.poll("native cap update readback", updated_caps)
        self.infer(user1, MODELS[0])
        self.infer(user1, MODELS[1])
        self.check("raising_native_caps_restores_requests")
        self.persisted()
        self.check("native_raw_logs_match_user_key_totals_usage_and_lineage", successful_calls=len(self.expected),
                   expected_user1_spend_usd="1.20", expected_user2_spend_usd="0.20")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("GOAL584_BASE_URL"))
    parser.add_argument("--receipt", type=Path, help="Write a safe JSON receipt; also printed to stdout")
    parser.add_argument("--timeout", type=float, default=45, help="Bound for each asynchronous persistence poll")
    args = parser.parse_args()
    receipt = {"proof": "goal584-native-scalar-budgets", "passed": False,
               "scope": "native_core_only", "expected_litellm_version": VERSION,
               "fixture_pricing": {"input_usd_per_token": "0.01", "output_usd_per_token": "0.02"},
               "not_qualified": ["trusted_key_selection_adapter", "production", "GUI", "Responses", "concurrency"],
               "started_at_utc": datetime.now(timezone.utc).isoformat()}
    try:
        require(bool(args.base_url), "--base-url or GOAL584_BASE_URL is required")
        key = os.environ.get("PROOF_MASTER_KEY") or os.environ.get("GOAL584_MASTER_KEY")
        require(bool(key), "PROOF_MASTER_KEY or GOAL584_MASTER_KEY is required")
        require(math.isfinite(args.timeout) and 1 <= args.timeout <= 120, "--timeout must be between 1 and 120 seconds")
        NativeProof(args.base_url, key, args.timeout, receipt).run()
        receipt["passed"] = True
    except ProofError as exc:
        receipt["failure"] = str(exc)
    except Exception as exc:
        # Do not stringify unexpected exceptions: urllib/context may contain a raw key.
        receipt["failure"] = "Unexpected driver error: " + type(exc).__name__
    receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    rendered = json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
