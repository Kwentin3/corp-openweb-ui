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
import signal
import subprocess
import time
from urllib.parse import urlencode, urlsplit

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, expect, sync_playwright
from prove_webui_browser import Fixture, chat, login, require, safe_failure, same_money, text_content, write_json
from verify_admin_calls import MARKER, FormParser, editor_rows


INTENT = "Давай поработаем с лимитами"
MODELS = ("goal584-a", "goal584-b")
SERVER_TITLE = "Изменение бюджетов сотрудников"
def same_editor_state(before, after):
    """Cancellation preserves all fields except fresh expense observation times."""
    def state(rows):
        return [{**{key: value for key, value in row.items() if key != "expense_as_of"},
                 "models": [{key: value for key, value in model.items() if key != "expense_as_of"}
                            for model in row["models"]]} for row in rows]
    return state(before) == state(after)


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
    def public_prices(self, *, restore=False):
        phase = "public-prices-restore" if restore else "public-prices-up"
        result = subprocess.run(self.command + ["exec", "-T", "proxy", "python", "-B", "/proof/provision_admin.py",
            "--phase", phase, "--private-state", "/proof-private/webui-state.private.json",
            "--receipt", "/proof-private/" + phase + ".safe.json"], capture_output=True, text=True, timeout=75)
        try:
            data = json.loads(result.stdout)
        except ValueError:
            raise AssertionError("Public price fixture did not return safe native readback") from None
        require(result.returncode == 0 and data.get("passed") is True and isinstance(data.get("public_prices"), dict),
                "Native public price update/restore failed")
        proof = data["public_prices"]
        require(proof.get("financial_history_unchanged") is True and proof.get("inference_calls") == 0
                and proof.get("variant") == ("S1" if restore else "S2")
                and proof.get("scheduled") is (not restore), "Public price lifecycle evidence differs")
        write_json(self.output / (phase + ".json"), data)
        return proof

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
    account["name"] = session.get("name") or account["id"]
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
                expected_count=2, observer=None):
    deadline = time.monotonic() + 60
    method = "open_budget_form" if text == INTENT else "apply_budget_form"
    while True:
        stored = chat_read(page, base, token, chat_id)
        message = ((stored.get("chat") or {}).get("history", {}).get("messages") or {}).get(sent["id"], {})
        embeds = editor_embeds(message, method)
        tasks = page.context.request.get(base + "/api/tasks/chat/" + chat_id,
            headers={"Authorization": "Bearer " + token}, timeout=10_000)
        require(tasks.status == 200 and isinstance(tasks.json().get("task_ids"), list), "Native admin task owner unavailable")
        if observer is not None:
            observer(stored, tasks.json())
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
    images = capture_editor(page, frame, output, label, editor_source(html, "message-" + sent["id"]))
    proof.update(editor_rows=rows, terminal_persisted=True, native_embed_count=len(embeds),
                 editor_source="function_call_output.embeds", sandbox_same_origin=False, backend_status=status,
                 diagnostic_source=editor_source(html, "message-" + sent["id"]), images=images)
    write_json(output / (label + ".json"), proof)
    return frame, rows, proof


def fill_plan(frame, plan):
    for change in plan["changes"]:
        section = frame.locator('tr[data-employee-id="' + change["user_id"] + '"]')
        section.locator('[data-field="budget_usd"]').fill(change["budget_usd"])
        exact = section.locator("details.exact-shares")
        if exact.get_attribute("open") is None:
            exact.locator("summary").click()
        for model, amount in change["shares"].items():
            section.locator('input[data-model-id="' + model + '"]:not([type="range"])').fill(amount)
        exact.locator("summary").click()


def review_plan(frame):
    review = frame.locator("#plan-review")
    expect(review).to_be_visible()
    if review.get_attribute("open") is None:
        review.locator("summary").click()
    expect(frame.locator("#preview")).to_be_visible()
    return frame.locator("#preview")


def capture_editor(page, frame, output, label, source, *, dialog=None):
    """Keep actual pixels of both the native viewport and the readable editor."""
    files = []
    region = ("-dialog", dialog) if dialog is not None else ("-editor", frame.locator("main"))
    for suffix, target in (("", page), region):
        path = output / (label + suffix + ".png")
        target.screenshot(path=str(path))
        files.append({"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return {"source": source, "png": files}


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


def qualify_table(page, frame, rows, plan, fixture, source, browser_codes):
    """Finite local interactions on the actual sandbox; no extra model turn."""
    from verify_admin_calls import accounting_totals_ready

    output = fixture.output
    physical, context = fixture.provider()["requests"], fixture.context()["requests"]
    deadline = time.monotonic() + 60
    while True:
        before = fixture.snapshot()
        users = before["users"] + before["admin_accounting"]["users"]
        keys = before["keys"] + before["admin_accounting"]["keys"]
        if {item["id"] for item in physical} <= {item["request_id"] for item in before["attributed_spend_logs"]} and accounting_totals_ready(
                users, keys, before["attributed_spend_logs"], {item["user_id"] for item in users}):
            break
        require(time.monotonic() < deadline, "Local table baseline accounting did not settle")
        time.sleep(.25)
    diagnostic = admin_editor_diagnostic(page, frame, source, browser_codes)
    baseline_prompts = diagnostic["iframe"]["prompt_messages"]
    completion_posts = []
    def observe_request(request):
        if request.method == "POST" and urlsplit(request.url).path == "/api/chat/completions":
            completion_posts.append(1)
    page.on("request", observe_request)
    receipt = {"schema": 1, "proof": "goal584-local-admin-table", "passed": False, "source": source,
        "source_sha256": {"driver": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "admin_ui": hashlib.sha256((Path(__file__).resolve().parents[2] / "deploy/openwebui-budgets/admin_ui.py").read_bytes()).hexdigest()},
        "stages": []}
    def stage(name, **checked):
        observation = admin_editor_diagnostic(page, frame, source, browser_codes)
        require(observation["iframe"]["srcdoc_matches_saved"] and observation["iframe"]["inline_program_matches_saved"],
                "Local table changed its persisted editor source")
        require(observation["iframe"]["prompt_messages"] == baseline_prompts and not completion_posts,
                "Local table interaction submitted a native prompt")
        receipt["stages"].append({"stage": name, "checks": checked, "diagnostic": observation,
            "images": capture_editor(page, frame, output, "admin-table-" + name, source)})
        write_json(output / "admin-table.json", receipt)
    employee = frame.locator('tr[data-employee-id]')
    visible = frame.locator('tr[data-employee-id]:visible')
    def ids():
        return visible.evaluate_all("els=>els.map(el=>el.dataset.employeeId)")
    def row(uid):
        return frame.locator('tr[data-employee-id="' + uid + '"]')
    def values(uid):
        return row(uid).locator('input:not([type="range"])').evaluate_all("els=>els.map(el=>el.value)")
    def clear_filters():
        frame.locator("#search").fill("")
        frame.locator("#department").select_option("")
        frame.locator("#remaining-filter").select_option("all")
        frame.locator("#only-changed").uncheck()
    try:
        expect(employee).to_have_count(len(rows))
        require(set(ids()) == {item["user_id"] for item in rows}, "Employee table is incomplete")
        require(frame.locator("#editor table").count() == 1, "Employee editor is not one native HTML table")
        sticky = frame.locator(".table-scroll").evaluate("""el=>{
          const head=el.querySelector('thead th'),start=head.getBoundingClientRect().top;
          const overflow=el.scrollHeight>el.clientHeight+1;
          if(!overflow)return {overflow:false,qualified:false,reason:'finite fixture does not overflow'};
          el.scrollTop=Math.min(64,el.scrollHeight-el.clientHeight);
          const top=head.getBoundingClientRect().top,scrollTop=el.scrollTop;el.scrollTop=0;
          return {overflow:true,qualified:scrollTop>0&&Math.abs(top-start)<=1,scrollTop,header_delta:top-start};
        }""")
        require(not sticky["overflow"] or sticky["qualified"], "Scrollable employee header did not stay sticky")
        money = frame.locator("#employee-table [data-money]").evaluate_all(
            "els=>els.map(el=>({raw:el.dataset.money,display:el.textContent,title:el.title}))")
        require(money and all(item["raw"] == "" or item["title"] == item["raw"] + " USD" for item in money),
                "Readable money lost its exact native amount")
        for item in rows:
            raw = row(item["user_id"]).locator("[data-money]").evaluate_all("els=>els.map(el=>el.dataset.money)")
            expected_caps = [model["cap_usd"] for model in item["models"] if model["cap_usd"] is not None]
            require(all(amount in raw for amount in expected_caps), "Readable model cap differs from exact native data")
        stage("general", single_table=True, employee_count=len(rows), visible_money=money, sticky_header=sticky)
        first, second = rows[:2]
        frame.locator("#search").fill(first["email"])
        require(ids() == [first["user_id"]], "Local email search selected wrong employees")
        stage("filtered", email_search=True)
        frame.locator("#search").fill("goal584-no-employee-match")
        expect(visible).to_have_count(0)
        expect(frame.locator("#empty-result")).to_be_visible()
        stage("empty", no_matching_rows=True)
        clear_filters()
        require(first.get("department") and second.get("department") and first["department"] != second["department"],
                "Finite table fixture requires two distinct native employee departments")
        frame.locator("#department").select_option(first["department"])
        require(set(ids()) == {item["user_id"] for item in rows if item.get("department") == first["department"]},
                "Department filter selected wrong employees")
        clear_filters()
        statuses = ("low", "exhausted")
        for status in statuses:
            frame.locator("#remaining-filter").select_option(status)
            eligible = [item for item in rows if item["remaining_usd"] is not None and Decimal(item["remaining_usd"]).is_finite()]
            expected = {item["user_id"] for item in eligible if (Decimal(item["remaining_usd"]) <= 0 if status == "exhausted"
                else item["budget_usd"] is not None and Decimal(item["budget_usd"]) > 0
                    and 0 < Decimal(item["remaining_usd"]) <= Decimal(item["budget_usd"]) / 10)}
            require(set(ids()) == expected, "Remaining filter differs from registered native counters")
        clear_filters()
        orders = {}
        for direction in ("name", "spend", "remaining"):
            frame.locator('[data-sort="' + direction + '"]').click()
            expect(frame.locator('[data-sort="' + direction + '"]')).to_have_attribute("aria-pressed", "true")
            orders[direction] = ids()
            require(set(orders[direction]) == {item["user_id"] for item in rows}, "Sorting lost an employee")
            if direction != "name":
                field = "spend_usd" if direction == "spend" else "remaining_usd"
                numeric = [item for item in rows if item[field] is not None and Decimal(item[field]).is_finite()]
                expected = sorted(numeric, key=lambda item: Decimal(item[field]), reverse=direction == "spend")
                expected += [item for item in rows if item not in numeric]
                require(orders[direction] == [item["user_id"] for item in expected],
                        "Money sorting differs from registered native counters")
        frame.locator('[data-sort="name"]').click()
        require(ids() == [item["user_id"] for item in sorted(rows, key=lambda item: item["name"])],
                "Name sorting differs from the fixture employee order")
        slider = row(first["user_id"]).locator("input[data-share-slider]").first
        slider.focus()
        slider.press("Home")
        slider.press("ArrowRight")
        exact = row(first["user_id"]).locator('input[data-model-id]:not([type="range"])')
        require(exact.count() == 2 and [Decimal(value) for value in exact.evaluate_all("els=>els.map(el=>el.value)")] == [Decimal(1), Decimal(99)]
                and slider.evaluate("el=>document.activeElement===el"),
                "Two-model keyboard slider did not maintain an exact complementary share")
        frame.locator("#reset-drafts").click()
        original = {item["user_id"]: values(item["user_id"]) for item in rows}
        fill_plan(frame, plan)
        draft = {item["user_id"]: values(item["user_id"]) for item in rows}
        require(all(draft[change["user_id"]] != original[change["user_id"]] for change in plan["changes"]),
                "Individual employee drafts did not change")
        for change in plan["changes"]:
            expect(row(change["user_id"]).locator('[data-field="budget_usd"]')).to_have_value(change["budget_usd"])
            for model, share in change["shares"].items():
                expect(row(change["user_id"]).locator('input[data-model-id="' + model + '"]')).to_have_value(share)
        expect(frame.locator("#changed-count")).to_contain_text(str(len(plan["changes"])))
        frame.locator("#search").fill(first["email"])
        require(ids() == [first["user_id"]] and values(second["user_id"]) == draft[second["user_id"]],
                "Filtering discarded a hidden employee draft")
        expect(frame.locator("#changed-count")).to_contain_text(str(len(plan["changes"])))
        clear_filters()
        frame.locator('[data-sort="remaining"]').click()
        require(all(values(uid) == value for uid, value in draft.items()), "Sorting discarded an employee draft")
        frame.locator('[data-sort="name"]').click()
        frame.locator("#only-changed").check()
        require(set(ids()) == {item["user_id"] for item in plan["changes"]}, "Changed-only view lost drafts")
        stage("draft", changed_count=len(plan["changes"]), hidden_draft_preserved=True,
              exact_percent=True, keyboard_slider_complement=True, sort_orders=orders, status_options=statuses,
              department_scoped=True)
        frame.locator("#reset-drafts").click()
        expect(visible).to_have_count(0)
        require(all(values(uid) == value for uid, value in original.items()), "Reset did not restore original row inputs")
        clear_filters()
        fill_plan(frame, plan)
        invalid = row(first["user_id"]).locator('[data-field="budget_usd"]')
        invalid.fill("invalid-budget")
        # Invalid editing is local and must not produce a native confirmation.
        frame.locator("#apply").click()
        expect(frame.locator("#feedback")).not_to_be_empty()
        stage("error", invalid_budget_not_submitted=True)
        fill_plan(frame, plan)
        preview = review_plan(frame)
        expect(preview).to_contain_text("→")
        for change in plan["changes"]:
            original_row = next(item for item in rows if item["user_id"] == change["user_id"])
            old_budget = "не установлен" if original_row["budget_usd"] is None else original_row["budget_usd"]
            expect(preview).to_contain_text(original_row["name"] + ": бюджет " + old_budget + " → " + change["budget_usd"] + " USD")
            for model in original_row["models"]:
                old_share = "нет данных" if model["share_percent"] is None else model["share_percent"]
                expect(preview).to_contain_text(model["label"] + ": " + old_share + " → " + change["shares"][model["id"]] + "%")
        stage("preview", live_diff_before_submit=True, original_schema=plan["schema"], revisions_preserved=True)
        after = fixture.snapshot()
        require(all(before[field] == after[field] for field in ("users", "keys", "admin_accounting", "attributed_spend_logs")),
                "Local table interactions changed native finance")
        require(physical == fixture.provider()["requests"] and context == fixture.context()["requests"],
                "Local table interactions dispatched a provider/context request")
        receipt.update(passed=True, native_finance_unchanged=True, provider_unchanged=True, gateway_context_unchanged=True,
            native_prompt_messages=0, completion_posts=0, final_native_receipt="admin-native-%02d.json" % fixture.sequence)
        write_json(output / "admin-table.json", receipt)
        return receipt
    finally:
        page.remove_listener("request", observe_request)


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
    expect(review_plan(frame)).to_contain_text("→")
    preview_images = capture_editor(page, frame, output, label + "-preview", source)
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
    embed_images = capture_editor(page, frame, output, label + "-embed-confirm", source, dialog=prompt)
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
    server_images = capture_editor(page, frame, output, label + "-server-confirm", source, dialog=server)
    server.get_by_role("button", name="Confirm" if approve else "Cancel", exact=True).click()
    write_json(output / (label + "-submitted-plan.json"), {"model": sent["model"], "assistant_id": sent["id"],
        "chat_id": chat_id, "parent_user_id": sent["user_message"]["id"], "text": text,
        "native_embed_confirmation": True, "native_server_confirmation": approve,
        "server_diff_expected": expected_diff, "server_diff_visible": server_text,
        "images": {"preview": preview_images, "embed_confirmation": embed_images, "server_confirmation": server_images}})
    return sent, chat_id, text


def submit_balance(page, frame, output, *, source):
    """One visible manual snapshot through both existing native confirmations."""
    accounts = json.loads(frame.locator("#budget-account-data").text_content())
    require(isinstance(accounts, list) and bool(accounts), "Native provider account overview is missing")
    account = accounts[0]
    require(isinstance(account.get("id"), str) and re.fullmatch(r"[0-9a-f]{64}", account.get("revision", "")),
            "Native provider account identity/revision is missing")
    editor = frame.locator('[data-account-index="0"]')
    if editor.get_attribute("open") is None:
        editor.locator(":scope > summary").click()
    balance_editor = editor.locator("details.balance-editor")
    if balance_editor.get_attribute("open") is None:
        balance_editor.locator("summary").click()
    editor.locator('[data-balance-field="amount"]').fill("123.45")
    editor.locator('[data-balance-field="currency"]').fill("USD")
    observed = editor.locator('[data-balance-field="observed_at"]').evaluate("el=>new Date(el.value).toISOString()")
    plan = {"schema": 1, "type": "provider_balance_snapshot", "account_id": account["id"],
            "expected_revision": account["revision"], "amount": "123.45", "currency": "USD", "observed_at": observed}
    text = json.dumps(plan, ensure_ascii=False, separators=(",", ":"))
    preview = capture_editor(page, frame, output, "admin-balance-preview", source)
    editor.locator("[data-submit-balance]").click()
    prompt = page.get_by_role("dialog", name="Confirm Prompt from Embed", exact=True)
    expect(prompt).to_be_visible()
    for value in ("provider_balance_snapshot", account["id"], account["revision"], "123.45", observed):
        expect(prompt).to_contain_text(value)
    embed = capture_editor(page, frame, output, "admin-balance-embed-confirm", source, dialog=prompt)
    with page.expect_response(lambda r: urlsplit(r.url).path == "/api/chat/completions" and r.request.method == "POST",
                              timeout=45_000) as pending:
        prompt.get_by_role("button", name="Confirm", exact=True).click()
    sent, chat_id = acknowledgement(pending.value)
    require(text_content(sent["user_message"]["content"]) == text, "Balance JSON changed before native submission")
    server = page.get_by_role("dialog", name="Последний известный баланс провайдера", exact=True)
    expect(server).to_be_visible(timeout=60_000)
    expect(server).to_contain_text("123.45 USD")
    expect(server).to_contain_text("Проверено в ЛК")
    confirmation = capture_editor(page, frame, output, "admin-balance-server-confirm", source, dialog=server)
    server.get_by_role("button", name="Confirm", exact=True).click()
    write_json(output / "admin-balance-submitted-plan.json", {"model": sent["model"], "assistant_id": sent["id"],
        "chat_id": chat_id, "parent_user_id": sent["user_message"]["id"], "text": text,
        "native_embed_confirmation": True, "native_server_confirmation": True,
        "images": {"preview": preview, "embed_confirmation": embed, "server_confirmation": confirmation}})
    return sent, chat_id, text, plan


def monthly_details(page, token, foreign_page, foreign_token, base, call, fixture, staff_ids, label):
    """Read through the visible Action and authenticated existing monthly owner."""
    from prove_cost_browser import cost_details
    from verify_admin_calls import accounting_totals_ready

    physical = fixture.provider()["requests"]
    provider_ids = {row["id"] for row in physical}
    deadline = time.monotonic() + 60
    while True:
        before = fixture.snapshot()
        users = before["users"] + before["admin_accounting"]["users"]
        keys = before["keys"] + before["admin_accounting"]["keys"]
        rows = before["attributed_spend_logs"]
        if provider_ids <= {row["request_id"] for row in rows} and accounting_totals_ready(
                users, keys, rows, {row["user_id"] for row in users}):
            break
        require(time.monotonic() < deadline, "Monthly read baseline did not settle")
        time.sleep(.25)
    page.goto(base + "/c/" + call["chat_id"], wait_until="domcontentloaded")
    model = call["model"]
    details = cost_details(page, base, token, call, fixture, label,
        answer_spend=".20", answer_models={model: (1, 10, 5, 15, Decimal(".20"))},
        chat_spend=".20", chat_models={model: (1, 10, 5, 15, Decimal(".20"))})
    path = base + "/api/v1/employee-budgets/monthly"
    response = page.context.request.get(path, headers={"Authorization": "Bearer " + token}, timeout=10_000)
    require(response.status == 200 and response.headers.get("cache-control") == "no-store",
            "Authenticated monthly GET failed")
    monthly = response.json()
    uid = call["user_id"]
    require(monthly.get("user_id") == uid and uid in staff_ids and monthly.get("expense_status") == "unavailable"
            and monthly.get("expense_observation_scope") == "assignment_history", "Monthly self scope/status differs")
    native = next(row for row in before["users"] if row["user_id"] == uid)
    expected = {"budget_usd": native["max_budget_usd"], "spend_usd": native["spend_usd"],
        "remaining_usd": str(Decimal(native["max_budget_usd"]) - Decimal(native["spend_usd"]))}
    for field, amount in expected.items():
        require(same_money(monthly.get(field), Decimal(amount)), "Monthly total differs from native " + field)
    require(all(monthly.get(field) == native[field] for field in ("budget_duration", "budget_reset_at")),
            "Monthly native period/reset differs")
    card = page.locator("#message-" + call["message_id"])
    report = card.locator('iframe[srcdoc*="data-budget-cost-details"]').first.content_frame.locator(
        'aside[data-monthly-budget="v1"]')
    expect(report).to_be_visible()
    for field, name in (("budget_usd", "budget"), ("spend_usd", "spend"), ("remaining_usd", "remaining")):
        observed = report.locator('[data-monthly-field="' + name + '"]').inner_text().removesuffix(" USD")
        require(same_money(observed, Decimal(monthly[field])), "Visible monthly total differs from owner")
    expect(report).to_contain_text(monthly["budget_duration"])
    expect(report).to_contain_text(monthly["budget_reset_at"])
    require({row["id"] for row in monthly["models"]} == set(MODELS), "Monthly model scope differs")
    for item in monthly["models"]:
        key = next(row for row in before["keys"] if row["user_id"] == uid and row["model"] == item["id"])
        for public, source in (("cap_usd", "max_budget_usd"), ("spend_usd", "spend_usd")):
            require(same_money(item[public], Decimal(key[source])), "Monthly model counter differs from native")
        require(same_money(item["remaining_usd"], Decimal(key["max_budget_usd"]) - Decimal(key["spend_usd"]))
                and all(item[field] == key[field] for field in ("budget_duration", "budget_reset_at")),
                "Monthly model remaining/period differs")
        row = report.get_by_role("rowheader", name=item.get("label") or item["id"], exact=True).locator("..")
        expect(row).to_have_count(1)
        cells = row.locator("td")
        for index, field in enumerate(("cap_usd", "spend_usd", "remaining_usd")):
            require(same_money(cells.nth(index).inner_text().removesuffix(" USD"), Decimal(item[field])),
                    "Visible monthly model counter differs")
        expect(cells.nth(3)).to_contain_text(item["budget_duration"])
        expect(cells.nth(3)).to_contain_text(item["budget_reset_at"])
        expect(cells.nth(4)).to_have_text("Заблокирована" if item["blocked"] is True else
            "Не заблокирована" if item["blocked"] is False else "Нет данных")
        expect(cells.nth(5)).to_contain_text("Полнота данных о расходе не подтверждена")
    denied = foreign_page.context.request.get(path + "?" + urlencode({"user_id": uid}),
        headers={"Authorization": "Bearer " + foreign_token}, timeout=10_000)
    require(denied.status == 403, "Monthly foreign employee read was not denied")
    rendered = report.inner_text()
    require(all(value not in rendered for value in staff_ids), "Monthly GUI disclosed internal user IDs")
    page.reload(wait_until="domcontentloaded")
    expect(report).to_be_visible()
    require(report.inner_text() == rendered, "Reload changed the persisted monthly snapshot")
    after = fixture.snapshot()
    fields = ("users", "keys", "admin_accounting", "attributed_spend_logs")
    require(all(before[field] == after[field] for field in fields), "Monthly/Details reads changed native finance")
    require(physical == fixture.provider()["requests"], "Monthly/Details reads dispatched a model")
    page.screenshot(path=str(fixture.output / (label + "-monthly.png")))
    safe = {key: monthly[key] for key in ("budget_usd", "spend_usd", "remaining_usd", "budget_duration",
        "budget_reset_at", "models", "expense_status", "expense_observation_scope")}
    return {"details": details, "monthly": safe, "foreign_http_status": denied.status,
        "native_finance_unchanged": True, "provider_unchanged": True, "visible_native_counters_equal": True}


def seed_monthly(browser, base, staff, fixture, receipt):
    """One visible prior call preserves the existing admin quota fixture contract."""
    from prove_webui_browser import verify_context_row

    before = fixture.snapshot()
    require(all(Decimal(row["spend_usd"]) == 0 for row in before["users"]), "GUI product seed requires fresh users")
    session = login(browser, base, staff[1])
    _, page, token = session
    call = chat(page, base, token, staff[1]["id"], MODELS[0], "success", "monthly-seed", fixture.output)
    call.update(user_id=staff[1]["id"])
    after, settled = wait_inference_delta(fixture, before, [u["id"] for u in staff], [(staff[1]["id"], MODELS[0])])
    provider, context = fixture.provider(), fixture.context()
    require(provider.get("synthetic") is True and len(provider["requests"]) == len(context["requests"]) == 1,
            "GUI seed must issue one synthetic call")
    verify_context_row(context["requests"][0], call, builtin_tools=False)
    physical, captured = provider["requests"][0], context["requests"][0]
    rows = [row for row in after["attributed_spend_logs"] if row["request_id"] == physical["id"]]
    require(len(rows) == 1 and rows[0]["user_id"] == staff[1]["id"] and rows[0]["model_group"] == MODELS[0]
            and rows[0]["owui_budget"] == captured["verified_cost_scope"]
            and physical["body"]["model"] == "goal584-fake-a"
            and len(physical["body"]["messages"]) == 1
            and physical["body"]["messages"][0].get("role") == "user"
            and text_content(physical["body"]["messages"][0].get("content")) == "Hi"
            and not (set(physical["body"]["messages"][0]) - {"role", "content"})
            and physical["body"]["stream"] is True and not physical["body"].get("tools")
            and physical["body"].get("max_tokens", physical["body"].get("max_completion_tokens")) == 5
            and physical["usage"] == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "GUI seed provider/context/native identity differs")
    write_json(fixture.output / "monthly-seed-provider.json", provider)
    write_json(fixture.output / "monthly-seed-context.json", context)
    receipt["monthly_seed"] = {"call": call, "settlement": settled,
        "native_receipt": "admin-native-%02d.json" % fixture.sequence,
        "source_sha256": {Path(__file__).name: hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "physical_calls": 1, "spend_usd": ".20", "separate_before_admin_reset": True}
    reset = 'import urllib.request;urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8000/__proof/reset",data=b"{}",headers={"Content-Type":"application/json"}),timeout=3).read();urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8000/__proof/control",data=b\'{"admin_mode":true}\',headers={"Content-Type":"application/json"}),timeout=3).read()'
    subprocess.run(fixture.command + ["exec", "-T", "provider", "python", "-B", "-c", reset],
        check=True, capture_output=True, timeout=15)
    clear = 'import capture_webui_auth as c\nwith c.capture_lock(): c._write_locked({"schema":1,"requests":[]})'
    subprocess.run(fixture.command + ["exec", "-T", "proxy", "python", "-B", "-c", clear],
        check=True, capture_output=True, timeout=15)
    return session, call


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--admin-accounts", type=Path, required=True)
    parser.add_argument("--accounts", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--monthly", action="store_true", help="Finite GUI product view on the existing admin scenario")
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
    public_prices_touched = False
    playwright = sync_playwright().start()
    if args.monthly:
        def interrupted(signum, frame):
            raise TimeoutError("Finite GUI product browser phase stopped")
        signal.signal(signal.SIGTERM, interrupted)
        signal.signal(signal.SIGALRM, interrupted)
        signal.alarm(330)
    try:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        receipt["browser_version"] = browser.version
        seed_session = seed_call = None
        if args.monthly:
            seed_session, seed_call = seed_monthly(browser, args.base_url, staff, fixture, receipt)
        before = fixture.snapshot()
        receipt["baseline_positive_request_ids"] = sorted(row["request_id"] for row in before["attributed_spend_logs"])
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
        if args.monthly:
            receipt["admin_table"] = qualify_table(page, frame, rows, plan, fixture,
                opened["diagnostic_source"], browser_codes)
        sent_cancel, cancel_chat, cancel_text = submit_plan(page, frame, plan, args.base_url, args.output, "admin-canceled", approve=False,
            source=opened["diagnostic_source"], browser_codes=browser_codes)
        frame, cancel_rows, canceled = wait_editor(page, args.base_url, token, cancel_chat, sent_cancel, admin["id"], model_id,
            cancel_text, args.output, "admin-canceled", status="Изменения отменены.")
        after_cancel = fixture.snapshot()
        require(staff_projection(before, staff_ids) == staff_projection(after_cancel, staff_ids),
                "Canceled server confirmation changed native employee caps/spend/reset/identity")
        require(same_editor_state(rows, cancel_rows), "Canceled form no longer shows actual unchanged employee state")
        retry = planned_changes(cancel_rows, staff_ids)
        require(retry == plan, "Canceled plan unexpectedly changed its original values/revisions")
        sent_apply, apply_chat, apply_text = submit_plan(page, frame, retry, args.base_url, args.output, "admin-applied", approve=True,
            source=canceled["diagnostic_source"], browser_codes=browser_codes)
        saved_frame, saved_rows, applied = wait_editor(page, args.base_url, token, apply_chat, sent_apply, admin["id"], model_id,
            apply_text, args.output, "admin-applied", status="Изменения применены.")
        after_apply = fixture.snapshot()
        verify_saved(before, after_apply, saved_rows, staff_ids)
        employee_contexts = [login(browser, args.base_url, staff[0]),
            seed_session if seed_session is not None else login(browser, args.base_url, staff[1])]
        if args.monthly:
            receipt["monthly_views"] = {"after_apply": monthly_details(seed_session[1], seed_session[2],
                employee_contexts[0][1], employee_contexts[0][2], args.base_url, seed_call, fixture, staff_ids, "monthly-after-apply")}
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
        if args.monthly:
            own = next(call for call in receipt["calls"] if call["user_id"] == staff_ids[1] and call["outcome"] == "success")
            receipt["monthly_views"]["at_quota"] = monthly_details(employee_contexts[1][1], employee_contexts[1][2],
                employee_contexts[0][1], employee_contexts[0][2], args.base_url, own, fixture, staff_ids, "monthly-at-quota")
        recovery = planned_changes(saved_rows, staff_ids, second_budget="0.8")
        require(len(recovery["changes"]) == 1 and recovery["changes"][0]["user_id"] == staff_ids[1],
                "Recovery form must change only employee two")
        sent_recovery, recovery_chat, recovery_text = submit_plan(page, saved_frame, recovery, args.base_url,
            args.output, "admin-recovered", approve=True, source=applied["diagnostic_source"], browser_codes=browser_codes)
        recovered_frame, recovered_rows, recovered = wait_editor(page, args.base_url, token, recovery_chat, sent_recovery,
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
        if args.monthly:
            receipt["monthly_views"]["after_recovery"] = monthly_details(employee_contexts[1][1], employee_contexts[1][2],
                employee_contexts[0][1], employee_contexts[0][2], args.base_url, resumed, fixture, staff_ids, "monthly-after-recovery")
            final = fixture.snapshot()
            receipt["final_native_receipt"] = "admin-native-%02d.json" % fixture.sequence
            legends = recovered_frame.locator("details.legend-price")
            expect(legends).to_have_count(len(MODELS))
            for legend in legends.all():
                amounts = legend.locator("summary [data-money]")
                expect(amounts).to_have_count(2)
                for amount in amounts.all():
                    expect(amount).to_be_visible()
                require([Decimal(value) for value in amounts.evaluate_all("els=>els.map(el=>el.dataset.money)")]
                        == [Decimal("10000"), Decimal("20000")], "Initial visible rates differ from native S1")
                expect(legend).to_contain_text("$/1M")
            before_balance = staff_projection(final, staff_ids)
            public_prices_touched = True
            receipt["public_prices_up"] = fixture.public_prices()
            sent_balance, balance_chat, balance_text, balance_plan = submit_balance(page, recovered_frame,
                args.output, source=recovered["diagnostic_source"])
            balance_frame, _, balance_saved = wait_editor(page, args.base_url, token, balance_chat, sent_balance,
                admin["id"], model_id, balance_text, args.output, "admin-balance-saved", status="Ручной снимок баланса сохранён.")
            after_accounts = json.loads(balance_frame.locator("#budget-account-data").text_content())
            selected = [entry for entry in after_accounts if entry["id"] == balance_plan["account_id"]]
            require(len(selected) == 1 and selected[0]["revision"] != balance_plan["expected_revision"],
                    "Saved manual balance did not advance its native account revision")
            account_view = balance_frame.locator('[data-account-index="' + str(after_accounts.index(selected[0])) + '"]')
            account_view.locator(":scope > summary").click()
            expect(account_view).to_contain_text("Последний известный баланс: 123.45 USD")
            expect(account_view).to_contain_text("Источник: вручную")
            expect(account_view).to_contain_text("Автор: " + admin["name"])
            for wire, rates in receipt["public_prices_up"]["applied_rates"].items():
                legend = balance_frame.locator("details.legend-price").filter(
                    has=balance_frame.locator('[data-color-model="' + wire + '"]'))
                expect(legend).to_have_count(1)
                amounts = legend.locator("summary [data-money]")
                expect(amounts).to_have_count(2)
                for amount in amounts.all():
                    expect(amount).to_be_visible()
                require([Decimal(value) for value in amounts.evaluate_all("els=>els.map(el=>el.dataset.money)")]
                        == [Decimal(rates[field]) * 1_000_000 for field in
                            ("input_cost_per_token", "output_cost_per_token")],
                        "Visible applied rates differ from native public source")
                expect(legend).to_contain_text("$/1M")
                if wire == MODELS[0]:
                    expect(legend).to_contain_text("цена изменена")
            saved_html = (args.output / "admin-balance-saved.html").read_text(encoding="utf-8")
            require(receipt["public_prices_up"]["loaded_at"] in saved_html,
                    "Visible price timestamp differs from native public map load time")
            balance_saved["images"] = capture_editor(page, balance_frame, args.output, "admin-balance-visible",
                                                       balance_saved["diagnostic_source"])
            # Native cost writes are asynchronous. Observe the two actual S2
            # calls before restoring the catalog; never repeat inference.
            from verify_admin_calls import accounting_totals_ready
            old_rows = {row["request_id"]: row for row in final["attributed_spend_logs"]}
            deadline = time.monotonic() + 20
            while True:
                final = fixture.snapshot()
                current = {row["request_id"]: row for row in final["attributed_spend_logs"]}
                require(old_rows.keys() <= current.keys() and all(current[k] == v for k, v in old_rows.items()),
                        "Public price update changed earlier native financial rows")
                added = [row for key, row in current.items() if key not in old_rows]
                require(len(added) <= 2 and all(row["user_id"] == admin["id"] and row["model_group"] == MODELS[0]
                        and Decimal(row["spend_usd"]) == Decimal(".40") for row in added),
                        "Public S2 manual turn has unexpected native charges")
                settled = accounting_totals_ready(final["users"] + final["admin_accounting"]["users"],
                    final["keys"] + final["admin_accounting"]["keys"], final["attributed_spend_logs"],
                    {admin["id"], *staff_ids}, history_complete=len(added) == 2)
                if len(added) == 2 and settled:
                    break
                require(time.monotonic() < deadline, "Public S2 manual turn did not settle in native accounting")
                page.wait_for_timeout(250)
            require(staff_projection(final, staff_ids) == before_balance,
                    "Manual provider balance changed employee financial state")
            balance_saved.update(manual_snapshot_visible=True, native_staff_state_unchanged=True,
                                 provider_overview_visible=True, public_price_change_visible=True,
                                 public_native_source_load_matches=True, old_native_rows_unchanged=True)
            receipt.update(balance_saved=balance_saved, manual_balance_proposal=balance_plan)
            receipt["final_native_receipt"] = "admin-native-%02d.json" % fixture.sequence
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
        if args.monthly:
            signal.alarm(0)
        if public_prices_touched:
            try:
                receipt["public_prices_restore"] = fixture.public_prices(restore=True)
            except Exception:
                receipt.update(passed=False, public_price_restore_failed=True)
        if browser is not None:
            browser.close()
        playwright.stop()
    receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(args.output / "admin-browser.json", receipt)
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
