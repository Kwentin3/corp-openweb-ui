#!/usr/bin/env python3
"""Real native Tool/chat/regeneration/UserValves cost-display qualification.

Run only against the disposable stock WebUI. Model calls go to the existing
synthetic provider. Browser login and mutations use visible native controls;
fixture APIs only observe/configure the isolated model/provider environment.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import ipaddress
import json
from pathlib import Path
import subprocess
import time
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

from capture_webui_auth import FIELDS as SEMANTIC_FIELDS
from prove_webui_browser import (Fixture, chat, login, require, safe_failure,
                                same_money, text_content, write_json)


FILTER_ID = "employee_budget_cost"
MODELS = ("goal584-a", "goal584-b")


class CostFixture(Fixture):
    def observe_cost(self, expected_total=None):
        deadline = time.monotonic() + 60
        while True:
            self.sequence += 1
            result = subprocess.run(self.command + ["exec", "-T", "proxy", "python", "-B",
                "/proof/provision_cost_display.py", "--phase", "snapshot", "--private-state",
                "/proof-private/webui-state.private.json", "--receipt", "/proof-private/cost-observed.safe.json"],
                capture_output=True, text=True, timeout=75)
            receipt = json.loads(result.stdout)
            write_json(self.output / ("cost-native-%02d.json" % self.sequence), receipt)
            require(result.returncode == 0 and receipt.get("passed") is True, "Native cost fixture readback failed")
            count = len(receipt["attributed_spend_logs"])
            if expected_total is None or count == expected_total:
                return receipt
            require(count < expected_total and time.monotonic() < deadline,
                    "Native attributed logs did not reach actual completed model calls")
            time.sleep(.5)

    def enable_tool_round(self):
        script = ('import urllib.request; opener=urllib.request.build_opener(urllib.request.ProxyHandler({})); '
            'request=urllib.request.Request("http://127.0.0.1:8000/__proof/control", '
            'data=b\'{"tool_round":true}\', headers={"Content-Type":"application/json"}); '
            'print(opener.open(request, timeout=3).read().decode())')
        result = subprocess.run(self.command + ["exec", "-T", "provider", "python", "-c", script],
                                capture_output=True, text=True, timeout=15)
        require(result.returncode == 0 and json.loads(result.stdout).get("tool_round") is True,
                "Synthetic provider tool-round control did not persist")


def chat_state(page, base_url, token, chat_id):
    response = page.context.request.get(base_url + "/api/v1/chats/" + chat_id,
        headers={"Authorization": "Bearer " + token}, timeout=10_000)
    require(response.status == 200, "Native private-chat readback failed")
    return response.json()["chat"]["history"]["messages"]


def set_display(page, base_url, token, enabled, output):
    # Exact stock 0.12.2 Controls -> Valves -> Functions -> selected Function.
    section = page.get_by_role("button", name="Valves", exact=True)
    if section.count() == 0:
        page.locator('button[aria-label="Controls"]').click()
    expect(section).to_be_visible()
    if section.get_attribute("aria-expanded") != "true":
        section.click()
    page.locator('select:has(option[value="functions"])').select_option("functions")
    page.locator('select:has(option[value="' + FILTER_ID + '"])').select_option(FILTER_ID)
    fields = page.locator(".chat-control-valves")
    expect(fields).to_be_visible()
    switch = fields.get_by_role("switch")
    if switch.count() == 0:
        fields.get_by_role("button", name="Default", exact=True).click()
    expect(switch).to_be_visible()
    current = switch.get_attribute("aria-checked") == "true"
    require(current != enabled, "Native preference fixture was already in the requested state")
    path = "/api/v1/functions/id/" + FILTER_ID + "/valves/user/update"
    with page.expect_response(lambda response: urlsplit(response.url).path == path
            and response.request.method == "POST"
            and response.request.post_data_json.get("enabled") is enabled, timeout=30_000) as pending:
        switch.click()
    require(pending.value.status == 200, "Native UserValves update failed")
    observed = page.context.request.get(base_url + path.removesuffix("/update"),
        headers={"Authorization": "Bearer " + token}, timeout=10_000)
    require(observed.status == 200 and observed.json().get("enabled") is enabled,
            "Native persisted UserValves differs from the visible switch")
    page.screenshot(path=str(output / ("display-%s.png" % ("on" if enabled else "off"))))
    page.locator('button[aria-label="Controls"]').click()


def verify(result, provider, context, before, final):
    calls = result["calls"]
    require(len(calls) == 6, "Cost scenario must complete six visible replies")
    calls_by_answer = {call["message_id"]: call for call in calls}
    require(len(calls_by_answer) == len(calls), "Visible replies reused an assistant message ID")
    requests = provider["requests"]
    require(provider.get("synthetic") is True and len(requests) == 8,
            "Cost scenario must dispatch exactly eight physical model calls")
    ids = {request["id"] for request in requests}
    require(len(ids) == 8, "Duplicate physical provider IDs")
    rows = [row for row in final["attributed_spend_logs"] if row["request_id"] in ids]
    require(len(rows) == 8 and {row["request_id"] for row in rows} == ids,
            "Actual cost scenario provider/native rows differ")
    for row in rows:
        scope = row["owui_budget"]
        call = calls_by_answer.get(scope.get("answer_id"))
        # This ordinary-chat scenario has no delegated children: actual and
        # root IDs must both be the exact browser-observed chat/answer. Check
        # hidden calls too; compensating wrong roots can preserve chat totals.
        require(call is not None and row.get("user_id") == call["user_id"]
                and scope.get("user_id") == call["user_id"]
                and row.get("session_id") == call["chat_id"]
                and scope.get("chat_id") == scope.get("root_chat_id") == call["chat_id"]
                and scope.get("answer_id") == scope.get("root_answer_id") == call["message_id"]
                and scope.get("model") == call["model"],
                "Native cost scope differs from its actual browser user/chat/answer/model")
    by_answer = Counter(row["owui_budget"]["root_answer_id"] for row in rows)
    expected_counts = [2, 1, 1, 1, 2, 1]
    for call, count in zip(calls, expected_counts):
        require(by_answer[call["message_id"]] == count, "Native tool/root model-call grouping differs")
    chat_id = calls[0]["chat_id"]
    require(all(call["chat_id"] == chat_id for call in [*calls[:4], calls[5]])
            and calls[4]["chat_id"] != chat_id, "Native chat/new-chat identity differs")
    first_chat_rows = [row for row in rows if row["owui_budget"]["root_chat_id"] == chat_id]
    require(sum(Decimal(row["spend_usd"]) for row in first_chat_rows) == Decimal("1.20"),
            "Whole-chat spend lost a regenerated/hidden/tool branch")
    before_users = {row["user_id"]: row for row in before["users"]}
    for user in final["users"]:
        expected = Decimal(before_users[user["user_id"]]["spend_usd"])
        if user["user_id"] == calls[0]["user_id"]:
            expected += Decimal("1.60")
        require(same_money(user["spend_usd"], expected), "Native user spend differs from physical cost scenario calls")
    observations = context["requests"]
    signed = [row for row in observations if row.get("verified_cost_scope")]
    require(len(signed) == 8, "Every physical cost model call needs one verified server scope")
    ledger_scopes = {row["owui_budget"]["call_id"]: row["owui_budget"] for row in rows}
    logs_by_nonce = {row["owui_budget"]["call_id"]: row for row in rows}
    provider_by_id = {request["id"]: request for request in requests}
    require(len(ledger_scopes) == 8 and {row["verified_cost_scope"]["call_id"] for row in signed} == set(ledger_scopes),
            "Gateway call nonces do not bind the native ledger rows")
    for row in signed:
        scope = row["verified_cost_scope"]
        call = calls_by_answer.get(scope.get("answer_id"))
        require(call is not None and row.get("user_id") == call["user_id"] and row.get("task") == ""
                and row["body"].get("model") == call["model"],
                "Signed gateway identity/model differs from its actual browser call")
        require(row["attestation_present_before"] is True and row["provenance_removed_after"] is True
                and row["body"] == row["body_after_auth"], "Attribution changed model-facing context or leaked its token")
        require(row["verified_cost_scope"] == ledger_scopes[row["verified_cost_scope"]["call_id"]],
                "Persisted scope differs from the verified auth owner output")
        physical = provider_by_id[logs_by_nonce[row["verified_cost_scope"]["call_id"]]["request_id"]]["body"]
        patch = row.get("native_stream_usage_patch")
        require(isinstance(patch, dict)
                and set(patch) <= {"stream_options", "_litellm_strip_stream_usage"}
                and ("_litellm_strip_stream_usage" not in patch
                     or type(patch["_litellm_strip_stream_usage"]) is bool)
                and ("stream_options" not in patch
                     or isinstance(patch["stream_options"], dict)
                     and patch["stream_options"].get("include_usage") is True),
                "Captured native stream-usage patch has an unsupported shape")
        expected_body = {**row["body"], **patch}
        # Exact native _stream_usage_tracking_updates output is captured by the
        # diagnostic owner. Auth must remain unchanged; only this native patch
        # and the configured alias -> physical model mapping may differ later.
        for field in SEMANTIC_FIELDS:
            if field == "model":
                continue
            require(physical.get(field) == expected_body.get(field),
                    "Final provider parameters differ from captured native normalization: " + field)
    by_id = {row["request_id"]: row for row in rows}
    for request in requests:
        body = request["body"]
        scope = by_id[request["id"]]["owui_budget"]
        require(body["model"] == {"goal584-a": "goal584-fake-a", "goal584-b": "goal584-fake-b"}[scope["model"]],
                "Native wire/provider model attribution differs")
        require(body.get("stream") is True and body.get("max_tokens", body.get("max_completion_tokens")) == 5,
                "Cost scenario stream/output cap differs")
        require(not any(key in body for key in ("metadata", "litellm_metadata", "owui_budget_provenance")),
                "Log-only scope reached the provider")
        require(request["usage"] == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
                and Decimal(by_id[request["id"]]["spend_usd"]) == Decimal(".20"), "Native/provider usage or charge differs")
    followups = [request for request in requests if any(message.get("role") == "tool" for message in request["body"]["messages"])]
    require(len(followups) >= 2 and all(any("proof-tool-result" in text_content(message.get("content", ""))
                for message in request["body"]["messages"] if message.get("role") == "tool") for request in followups),
            "Actual native tool result is missing from provider follow-up context")
    return {"passed": True, "visible_replies": 6, "physical_model_calls": 8, "tool_rounds": 2,
            "cost_scenario_usd": "1.60", "first_chat_usd": "1.20", "unexpected_provider_calls": 0,
            "native_preference_ui": True, "regenerated_branch_retained": True,
            "provider_scope_excluded": True, "actual_context_before_after_equal": True,
            "native_stream_usage_normalization_verified": True}


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
            and ipaddress.ip_address(target.hostname).is_private, "Cost browser target must be the disposable container")
    args.output.mkdir(exist_ok=True)
    require(args.output.resolve() not in args.accounts.resolve().parents, "Private accounts cannot be uploaded")
    accounts = json.loads(args.accounts.read_text(encoding="utf-8"))["users"]
    require(len(accounts) == 2, "Expected two synthetic employees")
    fixture = CostFixture(args.env_file, args.output)
    result = {"schema": 1, "proof": "goal584-native-cost-browser", "passed": False, "calls": [],
              "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "not_qualified": ["management_GUI", "delegation_settlement", "service_tasks", "nonstream_errors",
                                "failure_recovery", "converted_Responses_runtime", "production", "paid_provider"]}
    browser = page = None
    playwright = sync_playwright().start()
    try:
        before = fixture.observe_cost()
        baseline_count = len(before["attributed_spend_logs"])
        fixture.enable_tool_round()
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        result["browser_version"] = browser.version
        _, page, token = login(browser, args.base_url, accounts[0])
        user_id = accounts[0]["id"]
        def send(model, label, *, start_new=False, regenerate=None, costs=None):
            call = chat(page, args.base_url, token, user_id, model, "success", label, args.output,
                start_new=start_new, regenerate_message_id=regenerate, expected_costs=costs)
            call["user_id"] = user_id
            result["calls"].append(call)
            return call
        first = send(MODELS[0], "cost-01-tool", start_new=True, costs=("0.40", "0.40"))
        fixture.observe_cost(baseline_count + 2)
        second = send(MODELS[1], "cost-02-switch", costs=("0.20", "0.60"))
        third = send(MODELS[1], "cost-03-regenerate", regenerate=second["message_id"], costs=("0.20", "0.80"))
        messages = chat_state(page, args.base_url, token, first["chat_id"])
        require(messages[second["message_id"]]["parentId"] == messages[third["message_id"]]["parentId"]
                and second["message_id"] != third["message_id"], "Native regeneration did not retain both sibling answers")
        set_display(page, args.base_url, token, False, args.output)
        send(MODELS[1], "cost-04-hidden", costs=None)
        page.reload(wait_until="domcontentloaded")
        expect(page.locator("#chat-input")).to_be_visible()
        # Stored historical statuses are shared native message state, not retroactive preferences.
        expect(page.locator("#message-" + first["message_id"])).to_contain_text("Ответ: $0.40 · Чат: $0.40")
        result["historical_status_retained_when_disabled"] = True
        send(MODELS[0], "cost-05-hidden-new-model-chat", start_new=True, costs=None)
        fixture.observe_cost(baseline_count + 7)
        set_display(page, args.base_url, token, True, args.output)
        page.goto(args.base_url + "/c/" + first["chat_id"], wait_until="domcontentloaded")
        send(MODELS[1], "cost-06-restored", costs=("0.20", "1.20"))
        final = fixture.observe_cost(baseline_count + 8)
        _, foreign_page, foreign_token = login(browser, args.base_url, accounts[1])
        denied = foreign_page.context.request.get(args.base_url + "/api/v1/chats/" + first["chat_id"],
            headers={"Authorization": "Bearer " + foreign_token}, timeout=10_000)
        require(denied.status == 401, "Another employee can read the private chat/cost scope")
        raw = page.context.request.post(args.base_url + "/openai/chat/completions",
            headers={"Authorization": "Bearer " + token}, data={"model": MODELS[0],
                "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5,
                "litellm_metadata": {"spend_logs_metadata": {"owui_budget": {"user_id": accounts[1]["id"]}}}})
        require(raw.status == 403 and "provenance" in json.dumps(raw.json()).lower(),
                "Unsigned raw call was not rejected by the provenance owner")
        result["foreign_chat_denial"] = denied.status
        result["unsigned_raw_denial"] = raw.status
        boundary = verify(result, fixture.provider(), fixture.context(), before, final)
        write_json(args.output / "cost-provider-boundary.json", boundary)
        result["passed"] = True
    except Exception as error:
        result["failure"] = safe_failure(error, accounts)
        for observe in (fixture.provider, fixture.context):
            try:
                observe()
            except Exception:
                pass
        if page is not None:
            try:
                if page.locator("#password").count() == 0:
                    page.screenshot(path=str(args.output / "cost-failure.png"))
            except Exception:
                pass
    finally:
        if browser:
            browser.close()
        playwright.stop()
    result["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(args.output / "cost-browser.json", result)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
