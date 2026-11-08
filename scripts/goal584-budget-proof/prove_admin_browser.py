#!/usr/bin/env python3
"""Qualify the native admin form, both confirmations and stored JSON provenance.

Only visible controls submit/mutate. Native authenticated GETs and the disposable
fixture observe state. No session injection, request interception or paid target.
Final physical provider/context/ledger reconciliation belongs to the surrounding proof.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlsplit

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, expect, sync_playwright
from prove_webui_browser import Fixture, chat, login, require, safe_failure, same_money, text_content, write_json
from verify_admin_calls import MARKER, FormParser, editor_rows


INTENT = "Давай настроим лимиты"
MODELS = ("goal584-a", "goal584-b")
SERVER_TITLE = "Изменение бюджетов сотрудников"
def planned_changes(rows, staff_ids, *, second_budget="0.4"):
    require({row["user_id"] for row in rows} == set(staff_ids), "Native editor differs from fixture employees")
    changes = []
    for row in rows:
        require({m["id"] for m in row["models"]} == set(MODELS), "Native editor changed the managed model catalog")
        require(isinstance(row["revision"], str) and re.fullmatch(r"[0-9a-f]{64}", row["revision"]),
                "Native editor lacks a canonical current revision")
        first = row["user_id"] == staff_ids[0]
        change = {"user_id": row["user_id"], "expected_revision": row["revision"],
                  "budget_usd": "40" if first else second_budget,
                  "shares": {model["id"]: ("100" if model["id"] == MODELS[0] else "0")
                             if first else "50" for model in row["models"]}}
        if (change["budget_usd"] != row["budget_usd"] or any(
                change["shares"][m["id"]] != m["share_percent"] for m in row["models"])):
            changes.append(change)
    require(bool(changes), "Admin browser plan has no actual field changes")
    return {"schema": 1, "type": "employee_budget_plan", "changes": changes}


def verify_parent(stored, sent, admin_id, model_id, *, expected_text):
    require(stored.get("user_id") == admin_id, "Native admin chat owner differs")
    messages = (stored.get("chat") or {}).get("history", {}).get("messages", {})
    answer = messages.get(sent["id"], {})
    submitted = sent.get("user_message")
    require(isinstance(submitted, dict) and submitted.get("role") == "user"
            and text_content(submitted.get("content")) == expected_text and sent.get("model") == model_id,
            "Native browser submitted a rewritten proposal/model")
    parent = messages.get(answer.get("parentId"), {})
    require(answer.get("id") == sent["id"] and answer.get("role") == "assistant"
            and answer.get("model") == model_id and (answer.get("user_id") or stored["user_id"]) == admin_id
            and parent.get("id") == submitted.get("id") and parent.get("role") == "user"
            and parent.get("user_id") == admin_id and text_content(parent.get("content")) == expected_text,
            "Stored proposal is not the exact authenticated parent of this assistant")
    return answer, {"admin_id": admin_id, "chat_id": stored["id"], "assistant_id": answer["id"],
                    "parent_user_id": parent["id"], "parent_author_id": parent["user_id"],
                    "stored_parent_text": expected_text, "model_id": model_id,
                    "exact_submitted_and_stored_strings": True}


def staff_projection(snapshot, staff_ids):
    require(len(staff_ids) > 0 and len(set(staff_ids)) == len(staff_ids), "Native target employee set is ambiguous")
    user_fields = ("user_id", "max_budget_usd", "spend_usd", "budget_duration", "budget_reset_at")
    key_fields = ("user_id", "model", "key_alias", "max_budget_usd", "spend_usd", "budget_duration", "budget_reset_at")
    users = [{key: row[key] for key in user_fields} for row in snapshot["users"] if row["user_id"] in staff_ids]
    keys = [{key: row[key] for key in key_fields} for row in snapshot["keys"] if row["user_id"] in staff_ids]
    require(len(users) == len(staff_ids) and {r["user_id"] for r in users} == set(staff_ids)
            and len(keys) == len(staff_ids) * len(MODELS) and {(r["user_id"], r["model"]) for r in keys}
            == {(uid, model) for uid in staff_ids for model in MODELS}, "Native staff snapshot is incomplete")
    return {"users": sorted(users, key=lambda r: r["user_id"]),
            "keys": sorted(keys, key=lambda r: (r["user_id"], r["model"]))}


def verify_saved(before, after, rows, staff_ids, *, second_budget="0.4"):
    old, new = staff_projection(before, staff_ids), staff_projection(after, staff_ids)
    by_id = {row["user_id"]: row for row in rows}
    require(set(by_id) == set(staff_ids), "Saved editor employee ownership differs")
    for old_user, user in zip(old["users"], new["users"]):
        first = user["user_id"] == staff_ids[0]
        cap = Decimal("40") if first else Decimal(second_budget)
        require(same_money(user["max_budget_usd"], cap)
                and {k: v for k, v in old_user.items() if k != "max_budget_usd"}
                == {k: v for k, v in user.items() if k != "max_budget_usd"}, "Admin apply changed user spend/reset/identity")
        row = by_id[user["user_id"]]
        require(Decimal(row["budget_usd"]) == cap and same_money(row["spend_usd"], Decimal(user["spend_usd"]))
                and same_money(row["remaining_usd"], cap - Decimal(user["spend_usd"])),
                "Saved HTML budget/spend differs from native state")
    for old_key, key in zip(old["keys"], new["keys"]):
        first = key["user_id"] == staff_ids[0]
        cap = Decimal("40") if first and key["model"] == MODELS[0] else Decimal("0") if first else Decimal(second_budget) / 2
        require(same_money(key["max_budget_usd"], cap)
                and {k: v for k, v in old_key.items() if k != "max_budget_usd"}
                == {k: v for k, v in key.items() if k != "max_budget_usd"}, "Admin apply changed key spend/reset/identity")
        model = next(m for m in by_id[key["user_id"]]["models"] if m["id"] == key["model"])
        share = Decimal("100") if first and key["model"] == MODELS[0] else Decimal("0") if first else Decimal("50")
        require(Decimal(model["cap_usd"]) == cap and Decimal(model["share_percent"]) == share
                and same_money(model["spend_usd"], Decimal(key["spend_usd"])),
                "Saved HTML model cap/share differs from native state")


def verify_inference_delta(before, after, staff_ids, successful_pairs):
    old, new = staff_projection(before, staff_ids), staff_projection(after, staff_ids)
    counts = Counter(successful_pairs)
    for kind in ("users", "keys"):
        for previous, current in zip(old[kind], new[kind]):
            count = (sum(n for (uid, _), n in counts.items() if uid == current["user_id"])
                     if kind == "users" else counts[(current["user_id"], current["model"])])
            require(same_money(current["spend_usd"], Decimal(previous["spend_usd"]) + Decimal(".20") * count)
                    and {k: v for k, v in previous.items() if k != "spend_usd"}
                    == {k: v for k, v in current.items() if k != "spend_usd"},
                    "Employee inference changed cap/reset/identity or unexpected native spend")


def wait_inference_delta(fixture, before, staff_ids, successful_pairs, *, timeout=60, label="employee"):
    """Observe counters and exact new ledger rows; never repeat model work.

    Every snapshot is retained by its existing owner. Timeout is a nominal
    between-read budget; the existing 75-second snapshot read can overrun it.
    """
    targets, counts = tuple(staff_ids), Counter(successful_pairs)
    require(counts and all(uid in targets and model in MODELS for uid, model in counts),
            "Native settlement expected calls are outside the target employees/models")
    previous = staff_projection(before, targets)
    def selected_rows(snapshot):
        rows = [row for row in snapshot["attributed_spend_logs"] if row.get("user_id") in targets]
        require(all(isinstance(row.get("request_id"), str) and 0 < len(row["request_id"]) <= 512 for row in rows)
                and len({row["request_id"] for row in rows}) == len(rows), "Native settlement cost row identity duplicated or missing")
        return {row["request_id"]: row for row in rows}
    old_rows = selected_rows(before)
    started, observations = time.monotonic(), 0
    while True:
        snapshot = fixture.snapshot()
        observations += 1
        current = staff_projection(snapshot, targets)
        ready = True
        for kind in ("users", "keys"):
            for old, new in zip(previous[kind], current[kind]):
                require({key:value for key,value in old.items() if key != "spend_usd"}
                        == {key:value for key,value in new.items() if key != "spend_usd"},
                        "Native settlement changed employee identity/cap/period/alias")
                prior, actual = Decimal(old["spend_usd"]), Decimal(new["spend_usd"])
                require(prior.is_finite() and prior >= 0 and actual.is_finite() and actual >= 0,
                        "Native settlement counter is negative or nonfinite")
                count = (sum(number for (uid, _), number in counts.items() if uid == new["user_id"])
                         if kind == "users" else counts[(new["user_id"], new["model"])])
                expected = prior + Decimal(".20") * count
                if count == 0:
                    require(actual == prior, "Native settlement changed an unchanged employee/model counter")
                else:
                    require(actual >= prior or same_money(actual, prior), "Native settlement counter regressed")
                    require(actual <= expected or same_money(actual, expected), "Native settlement counter exceeded completed calls")
                    if not same_money(actual, expected):
                        ready = False
        rows = selected_rows(snapshot)
        require(old_rows.keys() <= rows.keys() and all(rows[identifier] == row for identifier,row in old_rows.items()),
                "Native settlement removed or changed existing employee cost rows")
        added = [row for identifier,row in rows.items() if identifier not in old_rows]
        actual_counts = Counter()
        for row in added:
            pair = (row["user_id"], row.get("model_group"))
            require(pair in counts and Decimal(row["spend_usd"]) == Decimal(".20"),
                    "Native settlement added an unexpected employee/model/cost row")
            actual_counts[pair] += 1
        require(all(number <= counts[pair] for pair,number in actual_counts.items()),
                "Native settlement observed an extra completed cost row")
        if ready and actual_counts == counts:
            return snapshot, {"observations": observations, "elapsed_seconds": time.monotonic() - started,
                "expected_successful_calls": sum(counts.values()), "matched_new_native_rows": len(added),
                "native_counter_and_ledger_converged": True}
        require(time.monotonic() - started < timeout, "Native " + label + " counters/ledger did not settle")
        time.sleep(.25)


class AdminFixture(Fixture):
    def snapshot(self):
        self.sequence += 1
        result = subprocess.run(self.command + ["exec", "-T", "proxy", "python", "-B", "/proof/provision_admin.py",
            "--phase", "snapshot", "--private-state", "/proof-private/webui-state.private.json",
            "--receipt", "/proof-private/admin-observed.safe.json"], capture_output=True, text=True, timeout=75)
        try:
            data = json.loads(result.stdout)
        except ValueError:
            raise AssertionError("Admin fixture did not return safe native readback") from None
        require(result.returncode == 0 and data.get("passed") is True, "Admin fixture native snapshot failed")
        write_json(self.output / ("admin-native-%02d.json" % self.sequence), data)
        return data


def admin_login(browser, base, account, *, first_login=True):
    context = browser.new_context(locale="en-US", viewport={"width": 1440, "height": 1000})
    page = context.new_page()
    page.set_default_timeout(30_000)
    page.goto(base + "/auth", wait_until="domcontentloaded")
    page.locator("#email").fill(account["email"])
    page.locator("#password").fill(account["password"])
    with page.expect_response(lambda r: urlsplit(r.url).path == "/api/v1/auths/signin" and r.request.method == "POST") as pending:
        page.locator('form button[type="submit"]').click()
    response = pending.value
    require(response.status == 200, "Ordinary admin browser sign-in failed")
    session = response.json()
    require(session.get("id") == account["id"] and session.get("role") == "admin", "Native signed-in admin identity differs")
    expect(page.locator("#chat-input")).to_be_visible(timeout=45_000)
    # This fixture signs its fresh admin into the GUI for the first time.
    # Acknowledge the stock release-notes modal through its visible control.
    release = page.get_by_role("button", name="Okay, Let's Go!", exact=True)
    if first_login:
        expect(release).to_be_visible(timeout=15_000)
    else:
        try:
            release.wait_for(state="visible", timeout=5_000)
        except PlaywrightTimeoutError:
            pass  # A previous ordinary sign-in may have persisted acknowledgment.
    if release.is_visible():
        release.click()
        expect(release).not_to_be_visible()
    return page, session["token"]


def chat_read(page, base, token, chat_id):
    response = page.context.request.get(base + "/api/v1/chats/" + chat_id,
        headers={"Authorization": "Bearer " + token}, timeout=10_000)
    require(response.status == 200, "Authenticated native admin chat read failed")
    return response.json()


def acknowledgement(response):
    require(response.status == 200, "Native admin chat did not acknowledge its task")
    sent, ack = response.request.post_data_json, response.json()
    chat_id = ack.get("chat_id") or sent.get("chat_id")
    require(isinstance(chat_id, str) and isinstance(sent.get("id"), str), "Native admin task IDs are absent")
    return sent, chat_id


def editor_embeds(message, method):
    # Pinned middleware.py6194..6201 persists Tool HTML on the correlated
    # function_call_output; top-level message.embeds belongs to other surfaces.
    output = message.get("output") or []
    calls = {item.get("call_id") for item in output if isinstance(item, dict)
             and item.get("type") == "function_call" and item.get("status") == "completed"
             and isinstance(item.get("name"), str) and item["name"].endswith(method)
             and isinstance(item.get("call_id"), str) and item["call_id"]}
    return [html for item in output if isinstance(item, dict)
            and item.get("type") == "function_call_output" and item.get("status") == "completed"
            and item.get("call_id") in calls for html in (item.get("embeds") or [])
            if isinstance(html, str) and MARKER in html]


def wait_editor(page, base, token, chat_id, sent, admin_id, model_id, text, output, label, *, status=None,
                expected_count=2):
    deadline = time.monotonic() + 60
    method = "open_budget_form" if text == INTENT else "apply_budget_form"
    while True:
        stored = chat_read(page, base, token, chat_id)
        message = ((stored.get("chat") or {}).get("history", {}).get("messages") or {}).get(sent["id"], {})
        embeds = editor_embeds(message, method)
        tasks = page.context.request.get(base + "/api/tasks/chat/" + chat_id,
            headers={"Authorization": "Bearer " + token}, timeout=10_000)
        require(tasks.status == 200 and isinstance(tasks.json().get("task_ids"), list), "Native admin task owner unavailable")
        if message.get("done") is True and not tasks.json()["task_ids"] and embeds:
            break
        if time.monotonic() >= deadline:
            # Technical state only; do not dump arbitrary native chat metadata.
            write_json(output / (label + "-pending.json"), {"assistant_id": sent["id"],
                "message_fields": sorted(message), "done": message.get("done"), "active_task_ids": tasks.json()["task_ids"],
                "top_embed_count": len(message.get("embeds") or []), "output": [{
                    "type": item.get("type"), "status": item.get("status"), "call_id": item.get("call_id"),
                    "embed_count": len(item.get("embeds") or [])} for item in (message.get("output") or [])
                    if isinstance(item, dict)]})
            raise AssertionError("Native admin task/editor did not complete")
        page.wait_for_timeout(250)
    message, proof = verify_parent(stored, sent, admin_id, model_id, expected_text=text)
    require(not message.get("error"), "Native admin answer completed with an error")
    require(len(embeds) == 1, "Current native admin Tool has an ambiguous editor result")
    html = embeds[0]
    rows = editor_rows(html, expected_count=expected_count)
    card = page.locator("#message-" + sent["id"])
    iframe = card.locator('iframe[srcdoc*="data-budget-editor"]').first
    expect(iframe).to_be_visible()
    require("allow-same-origin" not in (iframe.get_attribute("sandbox") or ""), "Admin editor relaxed native sandbox")
    frame = iframe.content_frame
    expect(frame.locator('main[data-budget-editor="v1"]')).to_be_visible()
    require(json.loads(frame.locator("#budget-data").text_content()) == rows, "Visible/native saved editor data differs")
    if status:
        expect(frame.locator("main")).to_contain_text(status)
        require(status in html, "Backend status is missing from persisted form")
    (output / (label + ".html")).write_text(html, encoding="utf-8")
    page.screenshot(path=str(output / (label + ".png")))
    proof.update(editor_rows=rows, terminal_persisted=True, native_embed_count=len(embeds),
                 editor_source="function_call_output.embeds", sandbox_same_origin=False, backend_status=status,
                 diagnostic_source=editor_source(html, "message-" + sent["id"]))
    write_json(output / (label + ".json"), proof)
    return frame, rows, proof


def fill_plan(frame, plan):
    for change in plan["changes"]:
        section = frame.locator('section[data-employee-id="' + change["user_id"] + '"]')
        section.locator('[data-field="budget_usd"]').fill(change["budget_usd"])
        for model, amount in change["shares"].items():
            section.locator('input[data-model-id="' + model + '"]').fill(amount)


def diff_lines(rows, plan):
    def money(value):
        if value is None:
            return "не установлен"
        text = format(Decimal(value), "f")
        return text.rstrip("0").rstrip(".") if "." in text else text
    by_id = {row["user_id"]: row for row in rows}
    lines = []
    for change in plan["changes"]:
        row = by_id[change["user_id"]]
        lines.append("Бюджет USD: " + money(row["budget_usd"]) + " → " + money(change["budget_usd"]))
        for model in sorted(row["models"], key=lambda value: value["id"]):
            proposed = Decimal(change["budget_usd"]) * Decimal(change["shares"][model["id"]]) / 100
            label = " ".join(model["label"].split())[:256]
            lines.append(label + ": " + money(model["cap_usd"]) + " → " + money(proposed) + " USD")
    return lines


def editor_source(html, card_id):
    programs = re.findall(r"<script>\(\(\)=>\{.*?</script>", html, re.DOTALL)
    return {"card_id": card_id, "srcdoc_sha256": hashlib.sha256(html.encode()).hexdigest(),
            "inline_program_sha256": hashlib.sha256(programs[0].encode()).hexdigest() if len(programs) == 1 else None}


def observe_admin_browser(page):
    """Bounded passive browser diagnostics; never retain raw console/messages."""
    counts = Counter()
    def console(message):
        text = message.text.lower()
        for code, present in (("console_csp", "content security policy" in text or "content-security-policy" in text),
                ("console_script_blocked", "blocked script execution" in text or "refused to execute inline script" in text),
                ("console_error", message.type == "error")):
            if present: counts[code] = min(counts[code] + 1, 1000)
    page.on("console", console)
    page.on("pageerror", lambda _: counts.update({"pageerror": int(counts["pageerror"] < 1000)}))
    page.evaluate("""() => {
      const state={card:null,frames:new WeakMap(),next:0,loads:0,sourceChanges:0,prompts:0,lastPrompt:null};
      window.__goal584AdminDiagnostics=state;
      window.addEventListener('message',event=>{
        if(event.data?.type!=='input:prompt:submit')return;
        state.prompts=Math.min(state.prompts+1,1000);
        const frame=document.getElementById(state.card)?.querySelector('iframe[srcdoc*="data-budget-editor"]');
        const text=typeof event.data.text==='string'?event.data.text:'';
        const record={source_matches_frame:!!frame&&event.source===frame.contentWindow,
          source_connected:!!frame?.isConnected,origin_kind:event.origin===window.origin?'same':event.origin==='null'?'opaque':'other',
          text_chars:Math.min(text.length,1048577),text_sha256:null};
        state.lastPrompt=record;
        if(text.length<=1048576&&crypto.subtle)crypto.subtle.digest('SHA-256',new TextEncoder().encode(text))
          .then(hash=>record.text_sha256=[...new Uint8Array(hash)].map(v=>v.toString(16).padStart(2,'0')).join('')).catch(()=>{});
      });
    }""")
    return counts


def admin_editor_diagnostic(page, frame, source, counts):
    """Observe one current iframe; no product action, readiness rule or API call."""
    source = source or {}
    outer = frame.owner.evaluate("""(element,card) => {
      const s=window.__goal584AdminDiagnostics;
      if(s){if(s.card!==card){s.card=card;s.prompts=0;s.lastPrompt=null;s.loads=0;s.sourceChanges=0;}if(!s.frames.has(element)){
        s.frames.set(element,++s.next);element.addEventListener('load',()=>s.loads=Math.min(s.loads+1,1000));
        new MutationObserver(()=>s.sourceChanges=Math.min(s.sourceChanges+1,1000)).observe(element,{attributes:true,attributeFilter:['srcdoc','sandbox']});}}
      return {srcdoc:element.getAttribute('srcdoc')||'',sandbox:element.getAttribute('sandbox')||'',
        card_matches:element.closest('[id^="message-"]')?.id===card,connected:element.isConnected,
        frame_instance:s?s.frames.get(element):null,observed_loads:s?s.loads:null,observed_source_changes:s?s.sourceChanges:null,
        prompt_messages:s?s.prompts:null,last_prompt:s?s.lastPrompt:null};
    }""", source.get("card_id"), timeout=500)
    html = outer.pop("srcdoc")
    actual = editor_source(html, "")
    outer["sandbox"] = sorted(set(outer["sandbox"].split()) & {
        "allow-scripts", "allow-forms", "allow-same-origin", "allow-popups", "allow-downloads"})
    outer.update(srcdoc_sha256=actual["srcdoc_sha256"], inline_program_sha256=actual["inline_program_sha256"],
        srcdoc_matches_saved=actual["srcdoc_sha256"] == source.get("srcdoc_sha256"),
        inline_program_matches_saved=actual["inline_program_sha256"] is not None
            and actual["inline_program_sha256"] == source.get("inline_program_sha256"))
    child = frame.locator("main").evaluate("""() => {
      const s=window.__goal584BudgetEditorProbe??={seq:0,inputs:0,clicks:0,lastInput:null,lastClick:null};
      if(!s.bound){s.bound=true;document.addEventListener('input',e=>{if(e.target.closest('#editor')){
        s.inputs=Math.min(s.inputs+1,1000);s.lastInput=s.seq=Math.min(s.seq+1,1000);}},true);
        document.addEventListener('click',e=>{if(e.target.closest('#apply')){
          s.clicks=Math.min(s.clicks+1,1000);s.lastClick=s.seq=Math.min(s.seq+1,1000);}},true);}
      return {ready_state:document.readyState,time_origin:performance.timeOrigin,apply_disabled:document.getElementById('apply')?.disabled??null,
        feedback:document.getElementById('feedback')?.textContent??'',preview:document.getElementById('preview')?.textContent??'',
        input_events:s.inputs,click_events:s.clicks,last_input_sequence:s.lastInput,last_click_sequence:s.lastClick};
    }""", timeout=500)
    for name in ("feedback", "preview"):
        value = child.pop(name)
        child[name] = {"chars": len(value), "sha256": hashlib.sha256(value.encode()).hexdigest()}
    return {"iframe": outer, "document": child, "browser_codes": {k: counts.get(k, 0) for k in
        ("console_csp", "console_script_blocked", "console_error", "pageerror")}, "native_client": {
        "stop_visible": page.locator('button[aria-label="Stop"],button[aria-label="Остановить"]').first.is_visible(),
        "send_visible": page.locator("#send-message-button").is_visible(),
        "composer_visible": page.locator("#chat-input").is_visible()}, "observation_only": True}


def submit_plan(page, frame, plan, base, output, label, *, approve, source=None, browser_codes=None):
    text = json.dumps(plan, ensure_ascii=False, separators=(",", ":"))
    expected_diff = diff_lines(json.loads(frame.locator("#budget-data").text_content()), plan)
    diagnostics = {"schema": 1, "proof": "goal584-admin-editor-observation", "observation_only": True, "stages": []}
    def observe(stage):
        try: snapshot = admin_editor_diagnostic(page, frame, source, browser_codes or {})
        except Exception as error:
            snapshot = {"capture_unavailable": True,
                        "capture_error_code": "timeout" if isinstance(error, PlaywrightTimeoutError) else "browser_error"}
        diagnostics["stages"].append({"stage": stage, **snapshot})
        try: write_json(output / (label + "-editor-diagnostic.json"), diagnostics)
        except Exception: pass  # Diagnostics cannot replace the original proof failure.
    observe("before_fill")
    fill_plan(frame, plan)
    observe("after_fill")
    frame.get_by_role("button", name="Применить изменения", exact=True).click()
    observe("after_click")
    prompt = page.get_by_role("dialog", name="Confirm Prompt from Embed", exact=True)
    try: expect(prompt).to_be_visible()
    except Exception:
        observe("missing_embed_confirmation")
        raise
    expect(prompt).to_contain_text("employee_budget_plan")
    for change in plan["changes"]:
        expect(prompt).to_contain_text(change["expected_revision"])
    page.screenshot(path=str(output / (label + "-embed-confirm.png")))
    with page.expect_response(lambda r: urlsplit(r.url).path == "/api/chat/completions" and r.request.method == "POST",
                              timeout=45_000) as pending:
        prompt.get_by_role("button", name="Confirm", exact=True).click()
    sent, chat_id = acknowledgement(pending.value)
    require(text_content(sent["user_message"]["content"]) == text, "Embed prompt strings changed before native submission")
    server = page.get_by_role("dialog", name=SERVER_TITLE, exact=True)
    expect(server).to_be_visible(timeout=60_000)
    for line in expected_diff:
        expect(server).to_contain_text(line)
    server_text = server.inner_text()
    page.screenshot(path=str(output / (label + "-server-confirm.png")))
    server.get_by_role("button", name="Confirm" if approve else "Cancel", exact=True).click()
    write_json(output / (label + "-submitted-plan.json"), {"model": sent["model"], "assistant_id": sent["id"],
        "chat_id": chat_id, "parent_user_id": sent["user_message"]["id"], "text": text,
        "native_embed_confirmation": True, "native_server_confirmation": approve,
        "server_diff_expected": expected_diff, "server_diff_visible": server_text})
    return sent, chat_id, text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--admin-accounts", type=Path, required=True)
    parser.add_argument("--accounts", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    target = urlsplit(args.base_url)
    require(target.scheme == "http" and target.port == 8080 and target.path in ("", "/")
            and not target.username and not target.password and not target.query and not target.fragment
            and isinstance(ipaddress.ip_address(target.hostname), ipaddress.IPv4Address)
            and ipaddress.ip_address(target.hostname).is_private, "Admin browser target must be disposable private IPv4:8080")
    for private in (args.accounts, args.admin_accounts, args.env_file):
        require(args.output.resolve() not in private.resolve().parents, "Private handoff cannot be uploaded")
    args.output.mkdir(exist_ok=True)
    handoff = json.loads(args.admin_accounts.read_text(encoding="utf-8"))
    require(handoff.get("schema") == 1 and handoff.get("model_id") == "goal584-budget-admin",
            "Expected the native disposable admin preset handoff")
    admin = handoff["admin"]
    model_id = handoff["model_id"]
    staff = json.loads(args.accounts.read_text(encoding="utf-8"))["users"]
    require(len(staff) == 2 and len({u["id"] for u in staff}) == 2 and admin["id"] not in {u["id"] for u in staff},
            "Expected separate native admin and two employees")
    staff_ids = [u["id"] for u in staff]
    fixture = AdminFixture(args.env_file, args.output)
    receipt = {"schema": 1, "proof": "goal584-native-admin-browser", "passed": False, "calls": [],
               "started_at_utc": datetime.now(timezone.utc).isoformat(),
               "not_qualified": ["production", "paid_provider",
                                 "concurrency", "calendar_rollover", "tariff_versions", "full_route_coverage"]}
    browser = page = None
    playwright = sync_playwright().start()
    try:
        before = fixture.snapshot()
        receipt["baseline_positive_request_ids"] = sorted(row["request_id"] for row in before["attributed_spend_logs"])
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        receipt["browser_version"] = browser.version
        page, token = admin_login(browser, args.base_url, admin)
        browser_codes = observe_admin_browser(page)
        selector = page.locator('button[id^="model-selector-"][aria-haspopup="listbox"]').first
        selector.click()
        page.locator('button[data-value="' + model_id + '"]').click()
        page.locator("#chat-input").fill(INTENT)
        with page.expect_response(lambda r: urlsplit(r.url).path == "/api/chat/completions" and r.request.method == "POST") as pending:
            page.locator("#send-message-button").click()
        sent, chat_id = acknowledgement(pending.value)
        frame, rows, opened = wait_editor(page, args.base_url, token, chat_id, sent, admin["id"], model_id,
                                         INTENT, args.output, "admin-opened")
        plan = planned_changes(rows, staff_ids)
        sent_cancel, cancel_chat, cancel_text = submit_plan(page, frame, plan, args.base_url, args.output, "admin-canceled", approve=False,
            source=opened["diagnostic_source"], browser_codes=browser_codes)
        frame, cancel_rows, canceled = wait_editor(page, args.base_url, token, cancel_chat, sent_cancel, admin["id"], model_id,
            cancel_text, args.output, "admin-canceled", status="Изменения отменены.")
        after_cancel = fixture.snapshot()
        require(staff_projection(before, staff_ids) == staff_projection(after_cancel, staff_ids),
                "Canceled server confirmation changed native employee caps/spend/reset/identity")
        require(cancel_rows == rows, "Canceled form no longer shows actual unchanged employee state")
        retry = planned_changes(cancel_rows, staff_ids)
        require(retry == plan, "Canceled plan unexpectedly changed its original values/revisions")
        sent_apply, apply_chat, apply_text = submit_plan(page, frame, retry, args.base_url, args.output, "admin-applied", approve=True,
            source=canceled["diagnostic_source"], browser_codes=browser_codes)
        saved_frame, saved_rows, applied = wait_editor(page, args.base_url, token, apply_chat, sent_apply, admin["id"], model_id,
            apply_text, args.output, "admin-applied", status="Изменения применены.")
        after_apply = fixture.snapshot()
        verify_saved(before, after_apply, saved_rows, staff_ids)
        employee_contexts = [login(browser, args.base_url, account) for account in staff]
        # The fixture retains admin_mode=true: ordinary Hi gets one physical
        # completion, even when model A exposes the already-qualified echo Tool.
        sequence = [(0, 1, "budget_blocked"), (0, 0, "success"), (1, 0, "budget_blocked"),
                    (1, 1, "success"), (1, 1, "budget_blocked")]
        for index, (owner, model, outcome) in enumerate(sequence, 1):
            _, employee_page, employee_token = employee_contexts[owner]
            call = chat(employee_page, args.base_url, employee_token, staff_ids[owner], MODELS[model], outcome,
                        "admin-staff-%02d-%s" % (index, outcome), args.output)
            call.update(user_id=staff_ids[owner], phase="after_admin_apply")
            receipt["calls"].append(call)
        quota_pairs = [(staff_ids[0], MODELS[0]), (staff_ids[1], MODELS[1])]
        after_quota, quota_settlement = wait_inference_delta(fixture, after_apply, staff_ids, quota_pairs)
        receipt.setdefault("native_settlements", {})["after_quota"] = quota_settlement
        quota_after = staff_projection(after_quota, staff_ids)
        verify_inference_delta(after_apply, after_quota, staff_ids, quota_pairs)
        recovery = planned_changes(saved_rows, staff_ids, second_budget="0.8")
        require(len(recovery["changes"]) == 1 and recovery["changes"][0]["user_id"] == staff_ids[1],
                "Recovery form must change only employee two")
        sent_recovery, recovery_chat, recovery_text = submit_plan(page, saved_frame, recovery, args.base_url,
            args.output, "admin-recovered", approve=True, source=applied["diagnostic_source"], browser_codes=browser_codes)
        _, recovered_rows, recovered = wait_editor(page, args.base_url, token, recovery_chat, sent_recovery,
            admin["id"], model_id, recovery_text, args.output, "admin-recovered", status="Изменения применены.")
        after_recovery = fixture.snapshot()
        verify_saved(after_quota, after_recovery, recovered_rows, staff_ids, second_budget="0.8")
        _, employee_page, employee_token = employee_contexts[1]
        resumed = chat(employee_page, args.base_url, employee_token, staff_ids[1], MODELS[1], "success",
                       "admin-staff-recovered", args.output)
        resumed.update(user_id=staff_ids[1], phase="after_admin_recovery")
        receipt["calls"].append(resumed)
        recovery_pairs = [(staff_ids[1], MODELS[1])]
        final, recovery_settlement = wait_inference_delta(fixture, after_recovery, staff_ids, recovery_pairs)
        receipt["native_settlements"]["after_recovery"] = recovery_settlement
        receipt["final_native_receipt"] = "admin-native-%02d.json" % fixture.sequence
        verify_inference_delta(after_recovery, final, staff_ids, recovery_pairs)
        recovered_user = next(u for u in final["users"] if u["user_id"] == staff_ids[1])
        require(same_money(recovered_user["spend_usd"], Decimal(".60")), "Recovered employee native spend differs")
        fixture.provider()
        fixture.context()
        receipt.update(passed=True, model_id=model_id, admin_id=admin["id"], staff_ids=staff_ids,
            opened=opened, canceled=canceled, applied=applied, recovered=recovered,
            original_proposal=plan, recovery_proposal=recovery, canceled_native_state_unchanged=True,
            exact_stored_parent_json=True, actual_saved_form_and_native_caps=True,
            native_snapshots={"before": staff_projection(before, staff_ids),
                "canceled": staff_projection(after_cancel, staff_ids), "applied": staff_projection(after_apply, staff_ids),
                "after_quota": quota_after, "recovered": staff_projection(after_recovery, staff_ids),
                "final": staff_projection(final, staff_ids)})
    except Exception as error:
        failure = safe_failure(error, [admin, *staff])
        receipt["failure"] = re.sub(r"(?:sk-|gw-)[A-Za-z0-9_-]{16,}", "[credential-redacted]", failure)
        for observe in (fixture.provider, fixture.context):
            try:
                observe()
            except Exception:
                pass
        if page is not None:
            try:
                if page.locator("#password").count() == 0:
                    page.screenshot(path=str(args.output / "admin-failure.png"))
            except Exception:
                pass
    finally:
        if browser is not None:
            browser.close()
        playwright.stop()
    receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(args.output / "admin-browser.json", receipt)
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
