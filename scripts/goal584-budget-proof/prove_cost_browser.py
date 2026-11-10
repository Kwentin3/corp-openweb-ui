#!/usr/bin/env python3
"""Real native Tool/chat/regeneration/UserValves cost-display qualification.

Run only against the disposable stock WebUI. Model calls go to the existing
synthetic provider. Browser login and mutations use visible native controls;
fixture APIs only observe/configure the isolated model/provider environment.
"""

import argparse
import copy
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import ipaddress
import json
from pathlib import Path
import subprocess
import signal
import time
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

from capture_webui_auth import FIELDS as SEMANTIC_FIELDS
from prove_native_budgets import expected_budget_message
from prove_webui_browser import (Fixture, chat, login, require, safe_failure,
                                same_money, text_content, write_json)


FILTER_ID = "employee_budget_cost"
ACTION_ID = "employee_budget_cost_details"
ACTION_LABEL = "Стоимость: детали"
MODELS = ("goal584-a", "goal584-b")


class CostFixture(Fixture):
    def phase(self, phase, *, chat_id=None, answer_id=None, request_id=None, call_id=None):
        self.sequence += 1
        command = self.command + ["exec", "-T", "proxy", "python", "-B",
            "/proof/provision_cost_display.py", "--phase", phase, "--private-state",
            "/proof-private/webui-state.private.json", "--receipt", "/proof-private/cost-phase.safe.json"]
        for flag, value in (("chat-id", chat_id), ("answer-id", answer_id),
                            ("request-id", request_id), ("call-id", call_id)):
            if value is not None:
                command += ["--" + flag, value]
        result = subprocess.run(command, capture_output=True, text=True, timeout=75)
        receipt = json.loads(result.stdout)
        write_json(self.output / ("cost-native-%02d-%s.json" % (self.sequence, phase)), receipt)
        require(result.returncode == 0 and receipt.get("passed") is True,
                "Native cost fixture phase failed: " + phase)
        return receipt

    def provider_control(self, control):
        script = ('import urllib.request; request=urllib.request.Request('
            '"http://127.0.0.1:8000/__proof/control", data=' + repr(json.dumps(control).encode()) +
            ', headers={"Content-Type":"application/json"}); '
            'print(urllib.request.urlopen(request,timeout=3).read().decode())')
        result = subprocess.run(self.command + ["exec", "-T", "provider", "python", "-c", script],
                                capture_output=True, text=True, timeout=15)
        require(result.returncode == 0, "Known0 provider control failed")
        return json.loads(result.stdout)

    def context(self):
        # The native owner returns an empty observation before its first call;
        # read under its lock rather than creating/resetting a capture file.
        script = ('import json,capture_webui_auth as owner\n'
                  'with owner.capture_lock():\n'
                  ' print(json.dumps(owner._read_locked()))')
        result = subprocess.run(self.command + ["exec", "-T", "proxy", "python", "-c", script],
                                capture_output=True, text=True, timeout=15)
        require(result.returncode == 0, "Cannot read the native cost context observation")
        data = json.loads(result.stdout)
        write_json(self.output / "webui-gateway-context.json", data)
        return data

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


def cost_details(page, base_url, token, call, fixture, label, *, chat_spend, chat_models,
                 answer_spend=".40", answer_models=None):
    """Click the native Action; read visible Rich UI and persisted native embed."""
    provider_before = {request["id"] for request in fixture.provider()["requests"]}
    before = chat_state(page, base_url, token, call["chat_id"])[call["message_id"]]
    marker = "data-budget-cost-details"
    old_embeds = [embed for embed in (before.get("embeds") or []) if isinstance(embed, str) and marker in embed]
    card = page.locator("#message-" + call["message_id"])
    card.hover()
    path = "/api/chat/actions/" + ACTION_ID
    with page.expect_response(lambda response: urlsplit(response.url).path == path
            and response.request.method == "POST", timeout=30_000) as pending:
        card.locator('button[aria-label="' + ACTION_LABEL + '"]').click()
    response = pending.value
    # Native process_tool_result serializes context to str (middleware1304ff),
    # and the Action endpoint JSON-encodes that string again (actions129ff).
    # Decode precisely that native wire contract, not a fictional dict result.
    wire = response.json()
    require(response.status == 200 and isinstance(wire, str) and 0 < len(wire) < 512,
            "Native cost Action returned an unsupported wire result")
    context = json.loads(wire)
    require(isinstance(context, dict) and set(context) == {"status", "message"}
            and context["status"] == "success" and isinstance(context["message"], str)
            and "<" not in context["message"],
            "Native cost Action did not return an independent UI result")
    deadline = time.monotonic() + 30
    while True:
        saved = chat_state(page, base_url, token, call["chat_id"])[call["message_id"]]
        embeds = [embed for embed in (saved.get("embeds") or []) if isinstance(embed, str) and marker in embed]
        # Native UI/chat updates may retain or replace prior snapshots. The
        # requirement is a fresh owner-persisted report, not growing its count.
        if embeds and embeds[0] not in old_embeds:
            break
        if time.monotonic() >= deadline:
            write_json(fixture.output / (label + "-persist-failure.json"), {
                "prior_embed_count": len(old_embeds), "current_embed_count": len(embeds),
                "same_as_prior": [embed in old_embeds for embed in embeds],
                "http_status": response.status, "context": context,
            })
            raise AssertionError("Fresh native Action snapshot was not persisted")
        page.wait_for_timeout(200)
    require(saved.get("content") == before.get("content") == "Proof"
            and saved.get("output") == before.get("output"), "Details Action changed model history content")
    iframe = card.locator('iframe[srcdoc*="data-budget-cost-details"]').first
    expect(iframe).to_be_visible()
    require("allow-same-origin" not in (iframe.get_attribute("sandbox") or ""),
            "Details iframe relaxed the stock sandbox")
    report = iframe.content_frame.locator('main[data-budget-cost-details="v1"]')
    expect(report).to_be_visible()
    totals = {}
    for scope, expected_spend, expected_models in (
        ("answer", Decimal(answer_spend), answer_models if answer_models is not None else
         {MODELS[0]: (2, 20, 10, 30, Decimal(".40"))}),
        ("chat", Decimal(chat_spend), chat_models),
    ):
        section = report.locator('section[data-cost-scope="' + scope + '"]')
        amount = section.locator("[data-cost-usd]").get_attribute("data-cost-usd")
        require(Decimal(amount) == expected_spend, "Rich UI cost total differs from native ledger")
        observed = {}
        for row in section.locator("tr[data-model]").all():
            model = row.get_attribute("data-model")
            require(model not in observed, "Rich UI duplicated a model breakdown")
            counts = tuple(int(row.locator('td[data-field="' + field + '"]').inner_text())
                           for field in ("calls", "prompt_tokens", "completion_tokens", "total_tokens"))
            spend = Decimal(row.locator('td[data-field="spend_usd"]').inner_text())
            observed[model] = (*counts, spend)
        require(observed == expected_models, "Rich UI model/token breakdown differs from native ledger")
        totals[scope] = {"spend_usd": amount, "models": {
            model: {"calls": value[0], "prompt_tokens": value[1], "completion_tokens": value[2],
                    "total_tokens": value[3], "spend_usd": str(value[4])} for model, value in observed.items()}}
    timestamp = report.locator("time[datetime]").get_attribute("datetime")
    require(datetime.fromisoformat(timestamp).utcoffset().total_seconds() == 0,
            "Rich UI snapshot lacks a UTC timestamp")
    require(provider_before == {request["id"] for request in fixture.provider()["requests"]},
            "Details Action dispatched a model request")
    html = embeds[0]
    require("ledger_read_key" not in html and "owui_budget_provenance" not in html,
            "Rich UI leaked server configuration")
    (fixture.output / (label + ".html")).write_text(html, encoding="utf-8")
    write_json(fixture.output / (label + "-action-result.json"), {"wire_type": "json_string", "context": context})
    page.screenshot(path=str(fixture.output / (label + ".png")))
    return {"chat_id": call["chat_id"], "answer_id": call["message_id"], "timestamp": timestamp,
            "totals": totals, "content_unchanged": True, "provider_ids_unchanged": sorted(provider_before),
            "native_embed_count": len(embeds), "prior_native_embed_count": len(old_embeds),
            "snapshot_changed": True, "sandbox_same_origin": False}


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
    require(len(observations) == 10 and len(signed) == 9,
            "Expected eight completed, one signed denied and one unsigned raw attempt")
    denial = result["off_budget_denial"]
    denied_call = denial["call"]
    denied_signed = [row for row in signed if row["verified_cost_scope"].get("answer_id") == denied_call["message_id"]]
    require(len(denied_signed) == 1, "OFF budget denial lost or duplicated its signed attempt")
    attempt = denied_signed[0]
    scope = attempt["verified_cost_scope"]
    require(denied_call["chat_id"] not in {call["chat_id"] for call in calls}
            and denied_call["model"] == MODELS[1] and denied_call["outcome"] == "budget_blocked"
            and denied_call["user_id"] == calls[0]["user_id"] == attempt["user_id"] == scope["user_id"]
            and scope["chat_id"] == scope["root_chat_id"] == denied_call["chat_id"]
            and scope["answer_id"] == scope["root_answer_id"] == denied_call["message_id"]
            and scope["model"] == denied_call["model"] == attempt["body"].get("model")
            and attempt["task"] == "" and attempt["attestation_present_before"] is True
            and attempt["provenance_removed_after"] is True and attempt["body"] == attempt["body_after_auth"],
            "OFF denied attempt differs from its actual browser/server scope")
    require(denial["key_budget_feedback"] is True and denial["cost_status_absent"] is True
            and denial["friendly_budget_feedback"] is True and denied_call["friendly_budget_feedback"] is True
            and expected_budget_message(denial["budget_message"], scope="key") == denied_call["budget_message"]
            and len(denial["provider_ids_before"]) == 4
            and denial["provider_ids_before"] == denial["provider_ids_after"]
            and set(denial["provider_ids_before"]) <= ids,
            "OFF denial changed provider calls or lost native feedback")
    limited, observed, restored = denial["limit"], denial["native_observation"], denial["restored"]
    require(observed["chat_id"] == denied_call["chat_id"] and observed["answer_id"] == denied_call["message_id"]
            and [part["status"] for part in (limited, observed, restored)] == ["limited", "observed", "restored"]
            and observed["terminal_budget_failure"] is True and observed["cost_status_absent"] is True
            and all(part["user_id"] == denied_call["user_id"] and part["model"] == MODELS[1]
                    and part["key_alias"] == limited["key_alias"] for part in (limited, observed, restored))
            and same_money(limited["key_spend_usd"], Decimal(".80"))
            and same_money(limited["key_max_budget_usd"], Decimal(".80"))
            and same_money(observed["key_max_budget_usd"], Decimal(".80"))
            and all(same_money(part["key_spend_usd"], Decimal(".80"))
                    and same_money(part["user_spend_usd"], Decimal("1.80"))
                    and same_money(part["user_max_budget_usd"], Decimal("20")) for part in (limited, observed, restored))
            and same_money(restored["key_max_budget_usd"], Decimal(limited["prior_key_max_budget_usd"])),
            "OFF quota mutation/denial/restore changed native identity or spend")
    require(observed["total_rows"] == len(observed["rows"])
            and {row["request_id"] for row in observed["rows"]} <= {row["request_id"] for row in observed["new_user_rows"]},
            "OFF denial omitted native rows from its session/user readbacks")
    for row in observed["new_user_rows"]:
        require(row["request_id"] not in ids and row["user_id"] == denied_call["user_id"]
                and row["session_id"] in (None, denied_call["chat_id"])
                and (row["spend_usd"] is None or Decimal(row["spend_usd"]) == 0),
                "A denied request produced a physical call, foreign row or charge")
        if row["owui_budget"] is not None:
            require(row["owui_budget"] == scope, "Native denied-row scope differs from its signed attempt")
    completed = [row for row in signed if row is not attempt]
    ledger_scopes = {row["owui_budget"]["call_id"]: row["owui_budget"] for row in rows}
    logs_by_nonce = {row["owui_budget"]["call_id"]: row for row in rows}
    provider_by_id = {request["id"]: request for request in requests}
    require(len(completed) == len(ledger_scopes) == 8
            and scope["call_id"] not in ledger_scopes
            and {row["verified_cost_scope"]["call_id"] for row in completed} == set(ledger_scopes),
            "Gateway call nonces do not bind the native ledger rows")
    for row in completed:
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
        require("data-budget-cost-details" not in json.dumps(body)
                and "<!doctype" not in json.dumps(body).lower(), "Rich UI HTML reached the next model context")
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
    details = result["details"]
    require(len(details) == 2 and details[0]["answer_id"] == details[1]["answer_id"] == calls[0]["message_id"]
            and datetime.fromisoformat(details[1]["timestamp"]) > datetime.fromisoformat(details[0]["timestamp"])
            and all(entry["native_embed_count"] >= 1 and entry["snapshot_changed"] is True for entry in details),
            "Repeated details Action did not refresh the same answer's snapshot")
    for detail in details:
        snapshot_ids = set(detail["provider_ids_unchanged"])
        require(detail["chat_id"] == chat_id and snapshot_ids <= ids
                and detail["content_unchanged"] is True and detail["sandbox_same_origin"] is False,
                "Details Action changed ownership/content/sandbox/provider calls")
        for kind in ("answer", "chat"):
            visible_rows = [row for row in first_chat_rows if row["request_id"] in snapshot_ids
                            and (kind == "chat" or row["owui_budget"]["root_answer_id"] == detail["answer_id"])]
            projection = detail["totals"][kind]
            require(Decimal(projection["spend_usd"]) == sum(Decimal(row["spend_usd"]) for row in visible_rows),
                    "Details UI total differs from actual native rows at its snapshot")
            models = {row["owui_budget"]["model"] for row in visible_rows}
            require(set(projection["models"]) == models, "Details UI dropped a native model")
            for model in models:
                native = [row for row in visible_rows if row["owui_budget"]["model"] == model]
                shown = projection["models"][model]
                require(shown["calls"] == len(native)
                        and all(shown[field] == sum(row[field] for row in native)
                                for field in ("prompt_tokens", "completion_tokens", "total_tokens"))
                        and Decimal(shown["spend_usd"]) == sum(Decimal(row["spend_usd"]) for row in native),
                        "Details model/token amounts differ from actual native ledger")
    require(result["foreign_details_denial"] == 404 and result["forged_details_denial"] == 400,
            "Cost Action failed its native authorization boundaries")
    return {"passed": True, "visible_replies": 6, "physical_model_calls": 8, "tool_rounds": 2,
            "cost_scenario_usd": "1.60", "first_chat_usd": "1.20", "unexpected_provider_calls": 0,
            "native_preference_ui": True, "regenerated_branch_retained": True,
            "provider_scope_excluded": True, "actual_context_before_after_equal": True,
            "native_stream_usage_normalization_verified": True,
            "off_budget_denial_without_provider": True, "details_fresh_native_ui": True,
            "details_html_excluded_from_model_context": True,
            "denial_native_rows": observed["total_rows"], "denial_user_delta_rows": len(observed["new_user_rows"])}


def run_known_zero(browser, fixture, base_url, accounts):
    """One actual native CC/nonstream Send; existing reader owns zero truth."""
    from prove_unknown_usage_browser import SETTINGS, read, setting, settings_preserved
    from prove_pricing_snapshots import no_credentials

    result = {"schema": 1, "proof": "goal584-known-zero-browser", "passed": False,
              "not_qualified": ["streaming_CC", "native_Tools", "Responses_zero", "Office", "production"]}
    prior = fixture.provider()
    require(all(row.get("lifecycle", {}).get("terminal") is True for row in prior["requests"]),
            "Known0 cannot overlap an unfinished provider request")
    capture_before = fixture.context()["requests"]
    require(len(capture_before) < 36 and len(json.dumps(capture_before).encode()) < 4 * 1024 * 1024 - 65536,
            "Known0 existing capture has insufficient headroom")
    original = copy.deepcopy(prior["control"])
    armed = {"prompt_tokens": 0, "completion_tokens": 0, "delay_ms": 0, "tool_round": False,
             "admin_mode": False, "title_mode": False, "native_tasks_mode": False,
             "response_status": 200, "after_first_chunk_delay_ms": 0}
    context = page = token = call = None
    submitted = []
    def timeout(_signum, _frame):
        raise TimeoutError("Known0 case exceeded four-minute bound")
    require(hasattr(signal, "SIGALRM"), "Known0 requires the existing Linux runner")
    old_signal = signal.signal(signal.SIGALRM, timeout)
    signal.alarm(240)
    try:
        fixture.provider_control(armed)
        require(fixture.provider()["control"] == {**original, **armed}, "Known0 provider arming differs")
        profile = fixture._observe_once("plainchat")["webui_models"]
        require(len(profile) == 2 and {model["model_id"] for model in profile} == set(MODELS)
                and all(model["builtin_tools"] is False and model["max_tokens"] == 5 for model in profile),
                "Known0 native plain-chat profile differs")
        result["fixture_profile"] = {"owner": "provision_webui.plainchat", "models": [
            {field: model[field] for field in ("model_id", "builtin_tools", "max_tokens")} for model in profile]}
        baseline = fixture.phase("known-zero")["known_zero"]
        context, page, token = login(browser, base_url, accounts[0])
        before_settings = read(context, base_url, token, SETTINGS)
        page.get_by_role("button", name="User menu", exact=True).first.click()
        page.get_by_role("button", name="Settings", exact=True).click()
        page.locator('#settings-tabs-container [role="tab"][aria-controls="tab-general"]').click()
        general = page.locator("#tab-general")
        general.get_by_role("button", name="Show", exact=True).click()
        stream = general.get_by_text("Stream Chat Response", exact=True).locator("..").get_by_role("button")
        for _ in range(3):
            if stream.inner_text().strip() == "Off":
                break
            stream.click()
        expect(stream).to_have_text("Off")
        with page.expect_response(lambda response: urlsplit(response.url).path == SETTINGS + "/update"
                and response.request.method == "POST") as saved:
            general.get_by_role("button", name="Save", exact=True).click()
        require(saved.value.status == 200, "Known0 native settings save failed")
        page.locator('#settings-tabs-container [role="tab"][aria-controls="tab-interface"]').click()
        for label in ("auto-generation-label", "follow-up-auto-generation-label", "chat-tags-label"):
            control = page.locator('#tab-interface [role="switch"][aria-labelledby="' + label + '"]')
            expect(control).to_be_visible()
            if control.get_attribute("aria-checked") == "true":
                with page.expect_response(lambda response: urlsplit(response.url).path == SETTINGS + "/update"
                        and response.request.method == "POST") as saved:
                    control.click()
                require(saved.value.status == 200, "Known0 automatic task settings save failed")
            expect(control).to_have_attribute("aria-checked", "false")
        page.locator("#settings-tabs-container").get_by_role("button", name="Back", exact=True).click()
        settings = read(context, base_url, token, SETTINGS)
        settings_preserved(before_settings, settings)
        require(setting(settings, "params.stream_response") is False and all(setting(settings, key) is False
                for key in ("title.auto", "autoTags", "autoFollowUps")), "Known0 effective native settings differ")
        page.on("request", lambda request: submitted.append(request.post_data_json)
                if urlsplit(request.url).path == "/api/chat/completions" and request.method == "POST" else None)
        call = chat(page, base_url, token, accounts[0]["id"], MODELS[1], "success", "known-zero-send",
                    fixture.output, expected_costs=("0.00", "0.00"))
        require(len(submitted) == 1 and submitted[0].get("stream") is False
                and all(not submitted[0].get(key) for key in ("tool_ids", "skill_ids", "tool_servers", "files")),
                "Known0 actual native submission is not ordinary nonstream")
        provider = fixture.provider()
        require(provider["requests"][:len(prior["requests"])] == prior["requests"]
                and len(provider["requests"]) == len(prior["requests"]) + 1, "Known0 provider prefix/suffix differs")
        physical = provider["requests"][-1]
        # The native OpenAI adapter omits stream:false; absence is nonstream.
        require(physical["body"].get("stream", False) is False and not physical["body"].get("tools")
                and physical["body"].get("model") == "goal584-fake-b"
                and physical["usage"] == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                and physical.get("response", {}).get("usage") == physical["usage"]
                and physical["lifecycle"].get("terminal") is True
                and physical["lifecycle"].get("outcome") == "completed"
                and physical["lifecycle"].get("usage_sent") is True, "Known0 actual provider outcome differs")
        capture = fixture.context()["requests"]
        require(capture[:len(capture_before)] == capture_before and len(capture) == len(capture_before) + 1,
                "Known0 captured prefix/suffix differs")
        captured = capture[-1]
        scope = captured.get("verified_cost_scope", {})
        require(captured.get("attestation_present_before") is True and captured.get("provenance_removed_after") is True
                and captured.get("native_auth_user_id") == accounts[0]["id"]
                and captured.get("task") in (None, "") and captured["body"].get("model") == MODELS[1]
                and scope.get("category") == "personal"
                and scope.get("root_chat_id") == scope.get("chat_id") == call["chat_id"]
                and scope.get("root_answer_id") == scope.get("answer_id") == call["message_id"]
                and scope.get("user_id") == accounts[0]["id"] and scope.get("model") == MODELS[1],
                "Known0 signed actual scope differs from native UI")
        for body in (captured["body"], captured["body_after_auth"], physical["body"]):
            require(body.get("stream", False) is False and not body.get("tools") and not body.get("functions")
                    and body.get("messages") == [{"role": "user", "content": "Hi"}], "Known0 actual model context differs")
        target = dict(chat_id=call["chat_id"], answer_id=call["message_id"],
                      request_id=physical["id"], call_id=scope["call_id"])
        observed = fixture.phase("known-zero", **target)["known_zero"]
        expected_rows = {**baseline["row_sha256"], physical["id"]: observed["row_sha256"][physical["id"]]}
        require(physical["id"] not in baseline["row_sha256"] and observed["row_sha256"] == expected_rows
                and observed["financial"] == baseline["financial"], "Known0 changed existing native rows/counters/caps")
        zero_models = {MODELS[1]: (1, 0, 0, 0, Decimal("0"))}
        details = [cost_details(page, base_url, token, call, fixture, "known-zero-details",
            answer_spend="0", answer_models=zero_models, chat_spend="0", chat_models=zero_models)]
        saved = copy.deepcopy(chat_state(page, base_url, token, call["chat_id"])[call["message_id"]])
        statuses = [status for status in saved.get("statusHistory", []) if status.get("action") == FILTER_ID]
        require(statuses and "начислено на сейчас" in statuses[-1].get("description", "")
                and " UTC" in statuses[-1]["description"], "Known0 status is not an accrued timestamped snapshot")
        page.goto(base_url + "/", wait_until="domcontentloaded")
        page.goto(base_url + "/c/" + call["chat_id"], wait_until="domcontentloaded")
        page.reload(wait_until="domcontentloaded")
        expect(page.locator("#message-" + call["message_id"])).to_contain_text("Ответ: $0.00 · Чат: $0.00")
        require(chat_state(page, base_url, token, call["chat_id"])[call["message_id"]] == saved,
                "Known0 reload changed the persisted native answer/status/embed")
        details.append(cost_details(page, base_url, token, call, fixture, "known-zero-details-reloaded",
            answer_spend="0", answer_models=zero_models, chat_spend="0", chat_models=zero_models))
        foreign, _, foreign_token = login(browser, base_url, accounts[1])
        denied = foreign.request.get(base_url + "/api/v1/chats/" + call["chat_id"],
            headers={"Authorization": "Bearer " + foreign_token}, timeout=10_000)
        action = foreign.request.post(base_url + "/api/chat/actions/" + ACTION_ID,
            headers={"Authorization": "Bearer " + foreign_token}, data={"model": MODELS[1],
                "chat_id": call["chat_id"], "id": call["message_id"], "session_id": "synthetic-negative", "messages": []},
            timeout=15_000)
        require(denied.status == 401 and action.status == 404, "Known0 foreign native ACL differs")
        final = fixture.phase("known-zero", **target)["known_zero"]
        require(final["financial"] == baseline["financial"] and final["row_sha256"] == expected_rows
                and fixture.provider()["requests"] == provider["requests"]
                and fixture.context()["requests"] == capture, "Known0 reload/Details/ACL changed native accounting or dispatch")
        result.update(call=call, native=final, details=details, foreign_chat_denial=denied.status,
                      foreign_details_denial=action.status, provider_id=physical["id"], reload_same_row=True, case_passed=True)
    except Exception as error:
        result["failure_class"] = type(error).__name__
        raise
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_signal)
        try:
            if page is not None and token and submitted:
                chat_id = call["chat_id"] if call is not None else submitted[0].get("chat_id")
                if chat_id:
                    path = base_url + "/api/tasks/chat/" + chat_id
                    headers = {"Authorization": "Bearer " + token}
                    active = context.request.get(path, headers=headers, timeout=10_000)
                    require(active.status == 200, "Known0 native task observation failed")
                    if active.json().get("task_ids"):
                        stopped = context.request.post(path + "/stop", headers=headers, timeout=10_000)
                        require(stopped.status == 200, "Known0 owned native task stop failed")
                    terminal = context.request.get(path, headers=headers, timeout=10_000)
                    require(terminal.status == 200 and terminal.json().get("task_ids") == [], "Known0 native tasks remain")
                    result["native_tasks_terminal"] = True
        finally:
            result["provider_control_restored"] = False
            try:
                fixture.provider_control({key: original.get(key) for key in set(original) | set(armed)})
                restored = fixture.provider()
                result["provider_control_restored"] = restored["control"] == original
                result["provider_terminal"] = all(row.get("lifecycle", {}).get("terminal") is True
                    for row in restored["requests"][len(prior["requests"]):])
            finally:
                result["passed"] = (result.get("case_passed") is True and result.get("native_tasks_terminal") is True
                                    and result["provider_control_restored"] and result.get("provider_terminal") is True)
                no_credentials(result, [account["password"] for account in accounts])
                write_json(fixture.output / "known-zero.safe.json", result)
            require(result["provider_control_restored"] and result["provider_terminal"],
                    "Known0 provider restoration/termination unconfirmed")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--accounts", required=True, type=Path)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--case", choices=("full", "known-zero"), default="full")
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
    if args.case == "known-zero":
        fixture.command += ["-f", "compose/goal584.office-proof.yml"]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            try:
                return 0 if run_known_zero(browser, fixture, args.base_url, accounts)["passed"] else 1
            finally:
                browser.close()
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
        result["details"] = [cost_details(page, args.base_url, token, first, fixture, "details-initial",
            chat_spend=".40", chat_models={MODELS[0]: (2, 20, 10, 30, Decimal(".40"))})]
        second = send(MODELS[1], "cost-02-switch", costs=("0.20", "0.60"))
        third = send(MODELS[1], "cost-03-regenerate", regenerate=second["message_id"], costs=("0.20", "0.80"))
        messages = chat_state(page, args.base_url, token, first["chat_id"])
        require(messages[second["message_id"]]["parentId"] == messages[third["message_id"]]["parentId"]
                and second["message_id"] != third["message_id"], "Native regeneration did not retain both sibling answers")
        set_display(page, args.base_url, token, False, args.output)
        limited = fixture.phase("off-limit")["off_denial"]
        provider_ids_before = sorted(request["id"] for request in fixture.provider()["requests"])
        require(len(provider_ids_before) == 4, "OFF quota test must follow four successful physical calls")
        off_call = chat(page, args.base_url, token, user_id, MODELS[1], "budget_blocked",
                        "cost-off-budget-denied", args.output, start_new=True, expected_costs=None)
        off_call["user_id"] = user_id
        saved_denial = chat_state(page, args.base_url, token, off_call["chat_id"])[off_call["message_id"]]
        denial_message = expected_budget_message(saved_denial.get("error"), scope="key")
        require(saved_denial.get("done") is True and off_call["budget_message"] == denial_message
                and off_call["friendly_budget_feedback"] is True
                and not any(status.get("action") == FILTER_ID for status in (saved_denial.get("statusHistory") or [])),
                "OFF attempt did not preserve the expected key-budget denial without a cost status")
        provider_ids_after = sorted(request["id"] for request in fixture.provider()["requests"])
        require(provider_ids_after == provider_ids_before, "OFF budget denial dispatched a provider call")
        denied_native = fixture.phase("off-denial-observe", chat_id=off_call["chat_id"])["off_denial"]
        require(same_money(denied_native["key_spend_usd"], Decimal(limited["key_spend_usd"]))
                and same_money(denied_native["user_spend_usd"], Decimal(limited["user_spend_usd"])),
                "OFF budget denial changed native user/key spend")
        restored = fixture.phase("off-restore")["off_denial"]
        result["off_budget_denial"] = {"call": off_call, "limit": limited, "native_observation": denied_native,
            "restored": restored, "provider_ids_before": provider_ids_before,
            "provider_ids_after": provider_ids_after, "key_budget_feedback": True, "cost_status_absent": True,
            "budget_message": denial_message, "friendly_budget_feedback": True}
        page.goto(args.base_url + "/c/" + first["chat_id"], wait_until="domcontentloaded")
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
        result["details"].append(cost_details(page, args.base_url, token, first, fixture, "details-refreshed",
            chat_spend="1.20", chat_models={MODELS[0]: (2, 20, 10, 30, Decimal(".40")),
                                           MODELS[1]: (4, 40, 20, 60, Decimal(".80"))}))
        _, foreign_page, foreign_token = login(browser, args.base_url, accounts[1])
        denied = foreign_page.context.request.get(args.base_url + "/api/v1/chats/" + first["chat_id"],
            headers={"Authorization": "Bearer " + foreign_token}, timeout=10_000)
        require(denied.status == 401, "Another employee can read the private chat/cost scope")
        action_body = {"model": MODELS[0], "chat_id": first["chat_id"], "id": first["message_id"],
                       "session_id": "synthetic-negative", "messages": []}
        action_denied = foreign_page.context.request.post(args.base_url + "/api/chat/actions/" + ACTION_ID,
            headers={"Authorization": "Bearer " + foreign_token}, data=action_body, timeout=15_000)
        # The native Action ownership gate hides private chats with404;
        # GET /api/v1/chats/{id} has a different401 contract (main2112ff).
        require(action_denied.status == 404, "Native cost Action did not hide the foreign chat")
        forged_action = page.context.request.post(args.base_url + "/api/chat/actions/" + ACTION_ID,
            headers={"Authorization": "Bearer " + token}, data={**action_body, "id": off_call["message_id"]}, timeout=15_000)
        require(forged_action.status == 400, "Cost details accepted an answer from a different owned chat")
        result["foreign_details_denial"] = action_denied.status
        result["forged_details_denial"] = forged_action.status
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
