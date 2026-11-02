#!/usr/bin/env python3
"""Exercise stock WebUI login/chat; reconcile with the native spend owner.

All chat actions use visible controls. Native fixture API controls only provision,
observe and raise caps; this is not acceptance of the budget management GUI.
No request mocking, token injection, storage export, trace or paid destination.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright


MODELS = ("goal584-a", "goal584-b")
CALL_COST = Decimal("0.20")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def safe_failure(error, accounts):
    message = type(error).__name__ + ": " + str(error)
    for account in accounts:
        message = message.replace(account["password"], "[password-redacted]")
    message = re.sub(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[session-redacted]", message)
    message = re.sub(r"(?i)Bearer\s+[^\s'\"]+", "Bearer [redacted]", message)
    return message[:2000]


def text_content(value):
    if isinstance(value, str):
        return value
    require(isinstance(value, list) and all(isinstance(part, dict)
            and set(part) == {"type", "text"} and part["type"] == "text" for part in value),
            "Unexpected multimodal/tool content at the provider boundary")
    return "".join(part["text"] for part in value)


def verify_provider(browser, provider, observed):
    require(browser.get("passed") is True and observed.get("passed") is True,
            "Browser/native observation did not pass")
    require(provider.get("synthetic") is True, "Expected the synthetic provider boundary")
    successes = [call for call in browser["calls"] if call["outcome"] == "success"]
    denials = [call for call in browser["calls"] if call["outcome"] == "budget_blocked"]
    require(len(successes) == 6 and len(denials) == 2, "The real WebUI scenario must complete six calls and two denials")
    require(len({call["chat_id"] for call in browser["calls"]}) == 8,
            "Every fixture request must start a fresh native chat")
    logs = observed["positive_spend_logs"]
    require(len(logs) == 6, "Unexpected native WebUI spend log count")
    actual = {request["id"]: request for request in provider["requests"]}
    expected = {row["request_id"]: row for row in logs}
    require(len(actual) == len(provider["requests"]) and len(expected) == len(logs)
            and set(actual) == set(expected), "Actual provider dispatch differs from native WebUI spend")
    by_owner_model = {}
    for call in successes:
        pair = (call["user_id"], call["model"])
        by_owner_model[pair] = by_owner_model.get(pair, 0) + 1
    log_counts = {}
    for request_id, log in expected.items():
        body = actual[request_id]["body"]
        require(body["model"] == {"goal584-a": "goal584-fake-a", "goal584-b": "goal584-fake-b"}[log["model_group"]],
                "WebUI provider model differs from the native assignment")
        messages = body.get("messages")
        require(isinstance(messages, list) and len(messages) == 1 and messages[0].get("role") == "user"
                and text_content(messages[0].get("content")) == "Hi"
                and not (set(messages[0]) - {"role", "content"}),
                "Final provider context differs from the single synthetic UI input")
        require(body.get("stream") is True and body.get("max_tokens", body.get("max_completion_tokens")) == 5
                and not body.get("tools") and not body.get("functions"), "WebUI stream/output/tool contract changed")
        require(actual[request_id]["usage"] == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
                and Decimal(log["spend_usd"]) == CALL_COST, "Native/provider usage or pricing differs")
        pair = (log["user"], log["model_group"])
        log_counts[pair] = log_counts.get(pair, 0) + 1
    require(by_owner_model == log_counts, "Native costs differ from the browser's actual users/models")
    return {"passed": True, "successful_calls": 6, "visible_budget_rejections": 2,
            "unexpected_provider_calls": 0, "persisted_spend_usd": "1.20",
            "context": "Eight fresh chats, one Hi each; six streamed synthetic completions",
            "not_qualified": ["management_GUI", "chat_cost_display", "tool_rounds", "service_tasks", "paid_provider"]}


class Fixture:
    def __init__(self, env_file, output):
        self.command = ["docker", "compose", "--env-file", str(env_file), "-f",
                        "compose/goal584.native-budget-proof.yml", "-f", "compose/goal584.webui-proof.yml"]
        self.output = output
        self.sequence = 0

    def observe(self, phase="snapshot", expected_total=None):
        deadline = time.monotonic() + 60
        while True:
            receipt = self._observe_once(phase)
            count = len(receipt["positive_spend_logs"])
            if expected_total is None or count == expected_total:
                return receipt
            require(count < expected_total and time.monotonic() < deadline,
                    "Native spend logs did not reach the completed UI call count")
            time.sleep(0.5)

    def _observe_once(self, phase):
        self.sequence += 1
        result = subprocess.run(self.command + ["exec", "-T", "proxy", "python", "-B",
            "/proof/provision_webui.py", "--phase", phase, "--private-state", "/proof-private/webui-state.private.json",
            "--receipt", "/proof-private/webui-observed.safe.json"], capture_output=True, text=True, timeout=75)
        # stdout is explicitly the safe receipt; stderr may contain product diagnostics.
        try:
            receipt = json.loads(result.stdout)
        except ValueError:
            raise AssertionError("Native WebUI observation did not return its safe JSON receipt") from None
        write_json(self.output / ("webui-native-%02d-%s.json" % (self.sequence, phase)), receipt)
        require(result.returncode == 0 and receipt.get("passed") is True, "Native WebUI observation failed")
        return receipt

    def provider(self):
        result = subprocess.run(self.command + ["exec", "-T", "provider", "python", "-c",
            'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8000/__proof/requests", timeout=3).read().decode())'],
            capture_output=True, text=True, timeout=15)
        require(result.returncode == 0, "Cannot observe the real synthetic provider boundary")
        data = json.loads(result.stdout)
        write_json(self.output / "webui-provider-calls.json", data)
        return data


def reconcile(observed, expected_calls, users):
    require(len(observed["positive_spend_logs"]) == sum(expected_calls.values()),
            "Persisted spend count differs from completed UI calls")
    for user_id in users:
        expected = sum((CALL_COST * count for (owner, _), count in expected_calls.items() if owner == user_id), Decimal("0"))
        user = next(row for row in observed["users"] if row["user_id"] == user_id)
        require(Decimal(user["spend_usd"]) == expected and user["webui_role"] == "user"
                and set(user["model_ids"]) == set(MODELS), "Native employee identity/spend/catalog reconciliation failed")
        for model in MODELS:
            key = next(row for row in observed["keys"] if row["user_id"] == user_id and row["model"] == model)
            require(Decimal(key["spend_usd"]) == CALL_COST * expected_calls.get((user_id, model), 0),
                    "Native per-model key spend differs from completed UI calls")


def login(browser, base_url, account):
    context = browser.new_context(locale="en-US", viewport={"width": 1440, "height": 1000})
    page = context.new_page()
    page.set_default_timeout(30_000)
    page.goto(base_url + "/auth", wait_until="domcontentloaded")
    page.locator("#email").fill(account["email"])
    page.locator("#password").fill(account["password"])
    with page.expect_response(lambda response: urlsplit(response.url).path == "/api/v1/auths/signin"
                              and response.request.method == "POST") as pending:
        page.locator('form button[type="submit"]').click()
    response = pending.value
    require(response.status == 200, "Ordinary browser login failed")
    session = response.json()
    require(session.get("id") == account["id"] and session.get("role") == "user", "Browser login identity/role differs")
    expect(page.locator("#chat-input")).to_be_visible(timeout=45_000)
    return context, page, session["token"]


def chat(page, base_url, token, user_id, model, expected_outcome, label, output):
    page.goto(base_url + "/", wait_until="domcontentloaded")
    expect(page.locator("#chat-input")).to_be_visible()
    selector = page.locator('button[id^="model-selector-"][aria-haspopup="listbox"]').first
    selector.click()
    page.locator('button[data-value="%s"]' % model).click()
    expect(selector).to_have_attribute("aria-label", "Selected model: " + model)
    page.locator("#chat-input").fill("Hi")
    with page.expect_response(lambda response: urlsplit(response.url).path == "/api/chat/completions"
                              and response.request.method == "POST", timeout=45_000) as pending:
        page.locator("#send-message-button").click()
    response = pending.value
    sent = response.request.post_data_json
    require(sent.get("model") == model and text_content(sent["messages"][-1]["content"]) == "Hi",
            "Native browser submitted a different model/input")
    message_id = sent.get("id")
    require(isinstance(message_id, str) and re.fullmatch(r"[a-f0-9-]{36}", message_id), "Missing native assistant message ID")
    # A successful task acknowledgement is not a completed answer.
    require(response.status == 200, "WebUI rejected the chat before native task acknowledgement")
    acknowledgement = response.json()
    chat_id = acknowledgement.get("chat_id") or sent.get("chat_id")
    require(isinstance(chat_id, str) and re.fullmatch(r"[a-f0-9-]{36}", chat_id), "Missing persistent native chat ID")
    terminal = None
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        observed = page.context.request.get(base_url + "/api/v1/chats/" + chat_id,
                                             headers={"Authorization": "Bearer " + token}, timeout=10_000)
        require(observed.status == 200, "Native ordinary-user chat readback failed")
        stored = observed.json()
        require(stored.get("user_id") == user_id, "Native chat owner differs from the ordinary logged-in user")
        message = stored.get("chat", {}).get("history", {}).get("messages", {}).get(message_id, {})
        if message.get("done") is True:
            terminal = message
            break
        page.wait_for_timeout(250)
    require(terminal is not None, "No persisted native terminal chat outcome")
    card = page.locator("#message-" + message_id)
    if expected_outcome == "success":
        require(not terminal.get("error") and terminal.get("content") == "Proof", "Native chat completion content/error differs")
        expect(card.locator("#response-content-container")).to_contain_text("Proof")
    else:
        error = terminal.get("error")
        require(bool(error) and "budget" in json.dumps(error).lower() and terminal.get("content", "") != "Proof",
                "Native terminal denial is not an explicit budget failure")
        expect(card).to_contain_text(re.compile("budget", re.I))
    expect(page.locator("#chat-input")).to_be_visible()
    page.screenshot(path=str(output / (label + ".png")), full_page=False)
    return {"model": model, "chat_id": chat_id, "message_id": message_id, "outcome": expected_outcome,
            "terminal_persisted": True, "visible_feedback": True, "browser_chat_status": response.status}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--accounts", required=True, type=Path)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    target = urlsplit(args.base_url)
    require(target.scheme == "http" and target.port == 8080 and target.path in ("", "/")
            and not target.username and not target.password and not target.query and not target.fragment
            and isinstance(ipaddress.ip_address(target.hostname), ipaddress.IPv4Address)
            and ipaddress.ip_address(target.hostname).is_private, "Browser target must be the disposable container IPv4:8080")
    require(args.output.resolve() not in args.accounts.resolve().parents, "Private handoff cannot live in uploaded receipts")
    accounts = json.loads(args.accounts.read_text(encoding="utf-8"))["users"]
    require(len(accounts) == 2 and len({user["id"] for user in accounts}) == 2, "Expected two distinct synthetic employees")
    fixture = Fixture(args.env_file, args.output)
    receipt = {"schema": 1, "proof": "goal584-stock-webui-browser", "passed": False, "calls": [],
               "started_at_utc": datetime.now(timezone.utc).isoformat(),
               "not_qualified": ["management_GUI", "service_tasks", "chat_cost_display", "paid_provider"]}
    expected_calls = {}
    page = None
    browser = None
    playwright = sync_playwright().start()
    try:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        receipt["browser_version"] = browser.version
        contexts = []
        for account in accounts:
            context, active_page, token = login(browser, args.base_url, account)
            contexts.append((context, active_page, token))
        users = [account["id"] for account in accounts]
        observed = fixture.observe()
        reconcile(observed, expected_calls, users)
        # Fresh chat per action makes the final provider input representative and bounded.
        plan = [(0, 0, "success"), (0, 0, "success"), (0, 0, "budget_blocked"),
                (0, 1, "success"), (0, 1, "success"), (0, 1, "budget_blocked"),
                (1, 0, "success"), (0, 0, "success")]
        for index, (user_index, model_index, outcome) in enumerate(plan, 1):
            if index == 8:
                observed = fixture.observe("raise")
                reconcile(observed, expected_calls, users)
            _, page, token = contexts[user_index]
            call = chat(page, args.base_url, token, users[user_index], MODELS[model_index], outcome,
                        "webui-%02d-%s" % (index, outcome), args.output)
            call["user_id"] = users[user_index]
            receipt["calls"].append(call)
            pair = (users[user_index], MODELS[model_index])
            if outcome == "success":
                expected_calls[pair] = expected_calls.get(pair, 0) + 1
            observed = fixture.observe(expected_total=sum(expected_calls.values()))
            reconcile(observed, expected_calls, users)
        receipt["passed"] = True
        verified = verify_provider(receipt, fixture.provider(), observed)
        write_json(args.output / "webui-provider-boundary.json", verified)
    except Exception as error:
        receipt["passed"] = False
        # Playwright error strings can quote credentials entered in fields.
        receipt["failure"] = safe_failure(error, accounts)
        if page is not None:
            try:
                if page.locator("#password").count() == 0:
                    page.screenshot(path=str(args.output / "webui-failure.png"))
            except Exception:
                pass
    finally:
        if browser is not None:
            browser.close()
        playwright.stop()
    receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(args.output / "webui-browser.json", receipt)
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
