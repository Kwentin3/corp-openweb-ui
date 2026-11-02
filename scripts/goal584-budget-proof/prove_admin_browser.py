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
from html.parser import HTMLParser
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright
from prove_webui_browser import Fixture, chat, login, require, safe_failure, same_money, text_content, write_json


INTENT = "Давай настроим лимиты"
MODELS = ("goal584-a", "goal584-b")
SERVER_TITLE = "Изменение бюджетов сотрудников"
MARKER = 'data-budget-editor="v1"'


class FormParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.current = False
        self.blocks = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("id") == "budget-data":
            self.current = True
            self.blocks.append("")

    def handle_data(self, data):
        if self.current:
            self.blocks[-1] += data

    def handle_endtag(self, tag):
        if tag == "script":
            self.current = False


def editor_rows(html):
    require(isinstance(html, str) and MARKER in html, "Native editor embed is missing")
    require(not re.search(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|(?:sk-|gw-)[A-Za-z0-9_-]{16,}", html),
            "Native editor contains a credential-shaped value")
    parser = FormParser(html)
    require(len(parser.blocks) == 1, "Native editor has an ambiguous data block")
    rows = json.loads(parser.blocks[0])
    require(isinstance(rows, list) and len(rows) == 2 and len({r["user_id"] for r in rows}) == 2,
            "Native editor must show the two actual employees")
    return rows


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
    user_fields = ("user_id", "max_budget_usd", "spend_usd", "budget_duration", "budget_reset_at")
    key_fields = ("user_id", "model", "key_alias", "max_budget_usd", "spend_usd", "budget_duration", "budget_reset_at")
    users = [{key: row[key] for key in user_fields} for row in snapshot["users"] if row["user_id"] in staff_ids]
    keys = [{key: row[key] for key in key_fields} for row in snapshot["keys"] if row["user_id"] in staff_ids]
    require(len(users) == 2 and {r["user_id"] for r in users} == set(staff_ids)
            and len(keys) == 4 and {(r["user_id"], r["model"]) for r in keys}
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


def admin_login(browser, base, account):
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
    expect(release).to_be_visible(timeout=15_000)
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


def wait_editor(page, base, token, chat_id, sent, admin_id, model_id, text, output, label, *, status=None):
    deadline = time.monotonic() + 60
    while True:
        stored = chat_read(page, base, token, chat_id)
        message = ((stored.get("chat") or {}).get("history", {}).get("messages") or {}).get(sent["id"], {})
        embeds = [e for e in (message.get("embeds") or []) if isinstance(e, str) and MARKER in e]
        tasks = page.context.request.get(base + "/api/tasks/chat/" + chat_id,
            headers={"Authorization": "Bearer " + token}, timeout=10_000)
        require(tasks.status == 200 and isinstance(tasks.json().get("task_ids"), list), "Native admin task owner unavailable")
        if message.get("done") is True and not tasks.json()["task_ids"] and embeds:
            break
        require(time.monotonic() < deadline, "Native admin task/editor did not complete")
        page.wait_for_timeout(250)
    message, proof = verify_parent(stored, sent, admin_id, model_id, expected_text=text)
    require(not message.get("error"), "Native admin answer completed with an error")
    html = embeds[0]
    rows = editor_rows(html)
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
                 sandbox_same_origin=False, backend_status=status)
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


def submit_plan(page, frame, plan, base, output, label, *, approve):
    text = json.dumps(plan, ensure_ascii=False, separators=(",", ":"))
    expected_diff = diff_lines(json.loads(frame.locator("#budget-data").text_content()), plan)
    fill_plan(frame, plan)
    frame.get_by_role("button", name="Применить изменения", exact=True).click()
    prompt = page.get_by_role("dialog", name="Confirm Prompt from Embed", exact=True)
    expect(prompt).to_be_visible()
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
        sent_cancel, cancel_chat, cancel_text = submit_plan(page, frame, plan, args.base_url, args.output, "admin-canceled", approve=False)
        frame, cancel_rows, canceled = wait_editor(page, args.base_url, token, cancel_chat, sent_cancel, admin["id"], model_id,
            cancel_text, args.output, "admin-canceled", status="Изменения отменены.")
        after_cancel = fixture.snapshot()
        require(staff_projection(before, staff_ids) == staff_projection(after_cancel, staff_ids),
                "Canceled server confirmation changed native employee caps/spend/reset/identity")
        require(cancel_rows == rows, "Canceled form no longer shows actual unchanged employee state")
        retry = planned_changes(cancel_rows, staff_ids)
        require(retry == plan, "Canceled plan unexpectedly changed its original values/revisions")
        sent_apply, apply_chat, apply_text = submit_plan(page, frame, retry, args.base_url, args.output, "admin-applied", approve=True)
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
        after_quota = fixture.snapshot()
        quota_after = staff_projection(after_quota, staff_ids)
        verify_inference_delta(after_apply, after_quota, staff_ids, [(staff_ids[0], MODELS[0]), (staff_ids[1], MODELS[1])])
        recovery = planned_changes(saved_rows, staff_ids, second_budget="0.8")
        require(len(recovery["changes"]) == 1 and recovery["changes"][0]["user_id"] == staff_ids[1],
                "Recovery form must change only employee two")
        sent_recovery, recovery_chat, recovery_text = submit_plan(page, saved_frame, recovery, args.base_url,
            args.output, "admin-recovered", approve=True)
        _, recovered_rows, recovered = wait_editor(page, args.base_url, token, recovery_chat, sent_recovery,
            admin["id"], model_id, recovery_text, args.output, "admin-recovered", status="Изменения применены.")
        after_recovery = fixture.snapshot()
        verify_saved(after_quota, after_recovery, recovered_rows, staff_ids, second_budget="0.8")
        _, employee_page, employee_token = employee_contexts[1]
        resumed = chat(employee_page, args.base_url, employee_token, staff_ids[1], MODELS[1], "success",
                       "admin-staff-recovered", args.output)
        resumed.update(user_id=staff_ids[1], phase="after_admin_recovery")
        receipt["calls"].append(resumed)
        final = fixture.snapshot()
        receipt["final_native_receipt"] = "admin-native-%02d.json" % fixture.sequence
        verify_inference_delta(after_recovery, final, staff_ids, [(staff_ids[1], MODELS[1])])
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
