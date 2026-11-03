#!/usr/bin/env python3
"""Independent post-admin GUI phase: defaults and an entirely absent new hire.

No native budget writes outside the visible confirmed form. Existing admin proof
receipts remain separate. All provider traffic terminates in the synthetic stub.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import ipaddress
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright
from prove_admin_browser import (FormParser, INTENT, MODELS, acknowledgement, admin_login,
                                 wait_editor)
from prove_webui_browser import Fixture, chat, login, require, safe_failure, same_money, text_content, write_json


def bootstrap_data(html):
    parser = FormParser(html, "budget-bootstrap-data")
    require(len(parser.blocks) == 1, "Native bootstrap form data is missing or ambiguous")
    value = json.loads(parser.blocks[0])
    require(isinstance(value, dict) and set(value) == {"template", "pending"}
            and isinstance(value["template"], dict) and isinstance(value["pending"], list),
            "Native bootstrap form data has an unexpected shape")
    return value


def template_plan(data):
    revision = data["template"].get("revision")
    require(isinstance(revision, str) and re.fullmatch(r"[0-9a-f]{64}", revision), "Missing native template revision")
    return {"schema": 1, "type": "employee_budget_template", "expected_revision": revision,
            "budget_usd": "0.8", "shares": {MODELS[0]: "100", MODELS[1]: "0"}, "budget_duration": "1mo"}


def initialize_plan(data, user_id):
    pending = [entry for entry in data["pending"] if entry.get("user_id") == user_id]
    require(len(pending) == 1 and pending[0].get("state") == "absent", "Expected one genuinely absent native identity")
    row = pending[0]
    require({model["id"] for model in row["models"]} == set(MODELS)
            and isinstance(row.get("revision"), str) and re.fullmatch(r"[0-9a-f]{64}", row["revision"]),
            "Pending employee model ACL/revision is incomplete")
    return {"schema": 1, "type": "employee_budget_initialize", "changes": [{
        "user_id": user_id, "expected_revision": row["revision"], "budget_usd": "0.8",
        "shares": {MODELS[0]: "100", MODELS[1]: "0"}}]}


def verify_newhire(snapshot, user_id, *, spend):
    state = snapshot["bootstrap"]
    require(state["kind"] == "ready" and state["user_id"] == user_id,
            "Initialized employee is not native-ready")
    users, keys = state["users"], state["keys"]
    require(len(users) == 1 and users[0]["user_id"] == user_id and len(keys) == 2
            and {key["model"] for key in keys} == set(MODELS)
            and len({key["key_alias"] for key in keys}) == 2, "Native new-hire assignments are incomplete")
    user = users[0]
    require(same_money(user["max_budget_usd"], Decimal(".8")) and same_money(user["spend_usd"], spend)
            and user["budget_duration"] == "1mo" and user["budget_reset_at"], "Native personal cap/spend/period differs")
    for key in keys:
        expected = Decimal(".8") if key["model"] == MODELS[0] else Decimal(0)
        require(key["user_id"] == user_id and same_money(key["max_budget_usd"], expected)
                and same_money(key["spend_usd"], spend if key["model"] == MODELS[0] else Decimal(0))
                and key["budget_duration"] == "1mo" and key["budget_reset_at"] == user["budget_reset_at"],
                "Native model cap/spend/reset differs from the confirmed initialization")


class BootstrapFixture(Fixture):
    def snapshot(self):
        self.sequence += 1
        result = subprocess.run(self.command + ["exec", "-T", "proxy", "python", "-B", "/proof/provision_admin.py",
            "--phase", "bootstrap-snapshot", "--private-state", "/proof-private/webui-state.private.json",
            "--receipt", "/proof-private/bootstrap-observed.safe.json"], capture_output=True, text=True, timeout=75)
        receipt = json.loads(result.stdout)
        write_json(self.output / ("bootstrap-native-%02d.json" % self.sequence), receipt)
        require(result.returncode == 0 and receipt.get("passed") is True, "Native bootstrap observation failed")
        return receipt


def form_data(frame):
    # This is readback of a displayed server embed, never authorization/state.
    return bootstrap_data('<script id="budget-bootstrap-data">' + frame.locator("#budget-bootstrap-data").text_content() + '</script>')


def submit(page, frame, plan, base, output, label, *, approve):
    if plan["type"] == "employee_budget_template":
        frame.locator("#template-budget").fill(plan["budget_usd"])
        for model, share in plan["shares"].items():
            frame.locator('input[data-template-model="' + model + '"]').fill(share)
        frame.locator("#save-template").click()
    else:
        change = plan["changes"][0]
        data = form_data(frame)
        index = next(index for index, row in enumerate(data["pending"]) if row["user_id"] == change["user_id"])
        article = frame.locator('article[data-pending-index="' + str(index) + '"]')
        article.locator('[data-initialize="' + str(index) + '"]').check()
        article.locator("[data-pending-budget]").fill(change["budget_usd"])
        for model, share in change["shares"].items():
            article.locator('input[data-pending-model="' + model + '"]').fill(share)
        frame.locator("#initialize-budgets").click()
    prompt = page.get_by_role("dialog", name="Confirm Prompt from Embed", exact=True)
    expect(prompt).to_be_visible()
    expect(prompt).to_contain_text(plan["type"])
    with page.expect_response(lambda response: urlsplit(response.url).path == "/api/chat/completions"
                              and response.request.method == "POST", timeout=45_000) as pending:
        prompt.get_by_role("button", name="Confirm", exact=True).click()
    sent, chat_id = acknowledgement(pending.value)
    text = text_content(sent["user_message"]["content"])
    require(text == json.dumps(plan, ensure_ascii=False, separators=(",", ":")),
            "Displayed bootstrap plan string changed before native submission")
    # The proposal's exact serialized string is preserved for history/provider comparison.
    server = page.get_by_role("dialog").filter(has=page.get_by_role("button", name="Confirm", exact=True)).last
    expect(server).to_be_visible(timeout=60_000)
    expect(server).to_contain_text("0.8")
    for model in MODELS:
        expect(server).to_contain_text(model)
    visible = server.inner_text()
    page.screenshot(path=str(output / (label + "-server-confirm.png")))
    server.get_by_role("button", name="Confirm" if approve else "Cancel", exact=True).click()
    write_json(output / (label + "-submitted.json"), {"assistant_id": sent["id"], "chat_id": chat_id,
        "parent_user_id": sent["user_message"]["id"], "text": text, "server_diff_visible": visible,
        "native_embed_confirmation": True, "native_server_confirmation": approve})
    return sent, chat_id, text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("admin-accounts", "employee-account", "env-file", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    target = urlsplit(args.base_url)
    require(target.scheme == "http" and target.port == 8080 and target.path in ("", "/")
            and not target.username and not target.password and not target.query and not target.fragment
            and isinstance(ipaddress.ip_address(target.hostname), ipaddress.IPv4Address)
            and ipaddress.ip_address(target.hostname).is_private, "Bootstrap target must be disposable private IPv4:8080")
    for private in (args.admin_accounts, args.employee_account, args.env_file):
        require(args.output.resolve() not in private.resolve().parents, "Private handoff cannot be uploaded")
    args.output.mkdir(exist_ok=True)
    handoff = json.loads(args.admin_accounts.read_text(encoding="utf-8"))
    employee_handoff = json.loads(args.employee_account.read_text(encoding="utf-8"))
    require(handoff.get("schema") == employee_handoff.get("schema") == 1
            and handoff.get("model_id") == employee_handoff.get("model_id") == "goal584-budget-admin",
            "Bootstrap native account handoff differs")
    admin, employee, model_id = handoff["admin"], employee_handoff["user"], handoff["model_id"]
    fixture = BootstrapFixture(args.env_file, args.output)
    receipt = {"schema": 1, "proof": "goal584-native-bootstrap-browser", "passed": False, "calls": [],
               "started_at_utc": datetime.now(timezone.utc).isoformat(),
               "not_qualified": ["production", "paid_provider", "concurrent_initialization", "calendar_rollover", "partial_recovery"]}
    browser = page = None
    playwright = sync_playwright().start()
    try:
        before = fixture.snapshot()
        require(before["bootstrap"]["kind"] == "absent", "Bootstrap GUI proof requires true native absence")
        receipt["baseline_positive_request_ids"] = sorted(row["request_id"] for row in before["attributed_spend_logs"])
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        page, token = admin_login(browser, args.base_url, admin, first_login=False)
        page.locator('button[id^="model-selector-"][aria-haspopup="listbox"]').first.click()
        page.locator('button[data-value="' + model_id + '"]').click()
        page.locator("#chat-input").fill(INTENT)
        with page.expect_response(lambda response: urlsplit(response.url).path == "/api/chat/completions"
                                  and response.request.method == "POST") as pending:
            page.locator("#send-message-button").click()
        sent, chat_id = acknowledgement(pending.value)
        frame, _, opened = wait_editor(page, args.base_url, token, chat_id, sent, admin["id"], model_id,
                                       INTENT, args.output, "bootstrap-opened")
        data = form_data(frame)
        initialize_plan(data, employee["id"])
        require(not frame.locator("[data-initialize]").is_checked(), "New employee was automatically selected for initialization")
        proposal = template_plan(data)
        sent, chat_id, text = submit(page, frame, proposal, args.base_url, args.output, "bootstrap-template", approve=True)
        frame, _, saved = wait_editor(page, args.base_url, token, chat_id, sent, admin["id"], model_id, text,
                                      args.output, "bootstrap-template")
        after_template = fixture.snapshot()
        require(after_template["bootstrap"] == before["bootstrap"] and after_template["default_template"] == {
            "budget_usd": "0.8", "shares": {MODELS[0]: "100", MODELS[1]: "0"}, "budget_duration": "1mo"},
            "Template save changed employee state or failed native configuration readback")
        initialization = initialize_plan(form_data(frame), employee["id"])
        sent, chat_id, text = submit(page, frame, initialization, args.base_url, args.output, "bootstrap-canceled", approve=False)
        frame, _, canceled = wait_editor(page, args.base_url, token, chat_id, sent, admin["id"], model_id, text,
                                         args.output, "bootstrap-canceled", status="Изменения отменены.")
        after_cancel = fixture.snapshot()
        require(after_cancel["bootstrap"] == before["bootstrap"]
                and after_cancel["default_template"] == after_template["default_template"],
                "Canceled initialization created native state or changed the template")
        require(initialize_plan(form_data(frame), employee["id"]) == initialization, "Cancellation changed absence revision")
        sent, chat_id, text = submit(page, frame, initialization, args.base_url, args.output, "bootstrap-initialized", approve=True)
        _, rows, initialized = wait_editor(page, args.base_url, token, chat_id, sent, admin["id"], model_id, text,
                                          args.output, "bootstrap-initialized", expected_count=3)
        created = fixture.snapshot()
        verify_newhire(created, employee["id"], spend=Decimal(0))
        require(len([row for row in rows if row["user_id"] == employee["id"]]) == 1,
                "Initialized native employee is missing from the displayed ready rows")
        _, employee_page, employee_token = login(browser, args.base_url, employee)
        for model, outcome in ((MODELS[0], "success"), (MODELS[1], "budget_blocked")):
            call = chat(employee_page, args.base_url, employee_token, employee["id"], model, outcome,
                        "bootstrap-employee-" + outcome, args.output)
            call["user_id"] = employee["id"]
            receipt["calls"].append(call)
        final = fixture.snapshot()
        verify_newhire(final, employee["id"], spend=Decimal(".20"))
        fixture.provider()
        fixture.context()
        receipt.update(passed=True, admin_id=admin["id"], employee_id=employee["id"], model_id=model_id,
            opened=opened, template_saved=saved, canceled=canceled, initialized=initialized,
            template_proposal=proposal, initialization_proposal=initialization,
            canceled_native_identity_absent=True, existing_employee_native_state_unchanged=True,
            final_native_receipt="bootstrap-native-%02d.json" % fixture.sequence,
            native_snapshots={"before": before["bootstrap"], "template": after_template["bootstrap"],
                "canceled": after_cancel["bootstrap"], "created": created["bootstrap"], "final": final["bootstrap"]})
    except Exception as error:
        receipt["failure"] = re.sub(r"(?:sk-|gw-)[A-Za-z0-9_-]{16,}", "[credential-redacted]", safe_failure(error, [admin, employee]))
        for observe in (fixture.provider, fixture.context):
            try:
                observe()
            except Exception:
                pass
        if page is not None:
            try:
                if page.locator("#password").count() == 0:
                    page.screenshot(path=str(args.output / "bootstrap-failure.png"))
            except Exception:
                pass
    finally:
        if browser is not None:
            browser.close()
        playwright.stop()
    receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(args.output / "bootstrap-browser.json", receipt)
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
