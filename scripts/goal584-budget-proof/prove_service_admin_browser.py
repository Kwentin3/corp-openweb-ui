#!/usr/bin/env python3
"""One ordinary admin form view, billed separately from the service title event."""
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
from prove_admin_browser import INTENT, acknowledgement, admin_login, wait_editor
from prove_webui_browser import Fixture, require, safe_failure, same_money, write_json
from verify_admin_calls import accounting_totals_ready, compare_provider, source_contract, text, tool_schemas, uuid, verify_accounting_totals


MODEL = "goal584-budget-admin"


def verify_unknown_render(accounts, rows, visible, native_keys):
    """Presentation only; native collectors own marker/counter/finance truth."""
    from verify_admin_calls import literal
    aliases = literal(Path(__file__).with_name("prove_unknown_usage_policy.py"), "ALIASES")
    require(accounts.get("schema") == 1 and accounts.get("model_id") == MODEL
            and accounts.get("tool_id") == "employee_budget_admin"
            and accounts.get("skill_id") == "goal584-budget-admin-guide"
            and accounts.get("managed_model_ids") == list(aliases), "Unknown admin handoff/source differs")
    identities = accounts.get("employee_ids")
    require(isinstance(identities, list) and identities and len(set(identities)) == len(identities),
            "Unknown admin prepared employee roster differs")
    for identity in [accounts["admin"]["id"], accounts["actor_id"], *identities]: uuid(identity)
    require(accounts["admin"]["id"] not in identities and accounts["actor_id"] in identities
            and len(rows) == len(identities) and {r["user_id"] for r in rows} == set(identities),
            "Unknown admin rendered a different employee roster")
    actor, = [r for r in rows if r["user_id"] == accounts["actor_id"]]
    require(actor.get("expense_status") == "unknown" and actor.get("known_subtotal_usd") is None
            and visible["employee_primary"] == "Расход неизвестен."
            and "Остаток не подтверждён." in visible["employee_summary"],
            "Employee unknown is not the primary expense state")
    expected = {alias: "unknown" if index else "unavailable" for index, alias in enumerate(aliases)}
    require(len(actor["models"]) == len(aliases) and {m["id"] for m in actor["models"]} == set(aliases)
            and set(visible["models"]) == set(aliases) and set(native_keys) == set(aliases),
            "Unknown admin model identities differ")
    values = [(actor, visible["employee_summary"], visible["employee_primary"])]
    for model in actor["models"]:
        alias = model["id"]; rendered = visible["models"][alias]
        require(model.get("expense_status") == expected[alias] and model.get("known_subtotal_usd") is None,
                "Unknown marker was cleared or false presence became known")
        blocked = native_keys[alias].get("blocked")
        require(type(blocked) is bool and rendered["blocked"] == ("Заблокирована" if blocked else "Не заблокирована"),
                "Rendered block differs from native assignment readback")
        values.append((model, rendered["expense"], rendered["primary"]))
    for value, rendered, primary in values:
        label = "Расход неизвестен." if value["expense_status"] == "unknown" else "Полнота данных о расходе не подтверждена."
        require(primary == label and f'По данным учёта: {value["spend_usd"]} USD.' in rendered
                and "Эта сумма не подтверждает итоговый расход." in rendered
                and "Подтверждённая часть расхода:" not in rendered,
                "Native counter was presented as a final expense/subtotal")
        if value["expense_status"] == "unknown":
            require("В истории есть запросы без данных о расходе." in rendered,
                    "Unknown expense lost its historical witness qualification")
    return {"employee_unknown_primary": True, "unknown_models": list(aliases[1:]),
            "native_counters_not_final": True, "known_subtotal_present": False,
            "native_block_labels_match": True}


def run_unknown_presence(browser, fixture, base_url, build_receipt, expected_revision, accounts):
    """One ordinary admin Send. Native collectors retain all financial authority."""
    import base64
    import hashlib
    from prove_admin_browser import chat_read
    from prove_gateway_auth import private_parent, write_private
    from prove_pricing_browser import MAX_BYTES, no_credentials

    running = fixture.running_readback(base_url, build_receipt, expected_revision)
    admin = accounts["admin"]
    require(accounts.get("schema") == 1 and accounts.get("model_id") == MODEL
            and isinstance(accounts.get("employee_ids"), list) and accounts["employee_ids"],
            "Unknown admin browser handoff unavailable")
    paths = {"packet": fixture.private / "admin-unknown-browser.private.json",
             "html": fixture.private / "admin-unknown-opened.html",
             "opened_receipt": fixture.private / "admin-unknown-opened.json",
             "page_screenshot": fixture.private / "admin-unknown-opened.png",
             "employee_screenshot": fixture.private / "admin-unknown-employee.png"}
    require(all(not p.exists() and not p.is_symlink() and p.resolve().parent == fixture.private.resolve()
                for p in paths.values()), "Unknown admin private evidence already exists or escaped")
    private_parent(paths["packet"])
    packet = {"schema": 1, "admin_id": admin["id"], "actor_id": accounts["actor_id"], "model_id": MODEL,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "binding": {"source_commit": expected_revision, "running": running},
              "paths": {name: str(path) for name, path in paths.items()}}

    def snapshot(label):
        argv = ["exec", "-T", "proxy", "python", "-B", "/proof/provision_admin.py", "--phase", "unknown-snapshot",
            "--private-state", "/proof-private/webui-state.private.json", "--office-state", "/proof-private/office-state.private.json",
            "--unknown-state", "/proof-private/unknown-usage-gui-state.private.json",
            "--admin-unknown-state", "/proof-private/admin-unknown-state.private.json",
            "--receipt", "/proof-private/admin-unknown-snapshot.safe.json"]
        receipt = fixture.command_json(argv, "admin_unknown_" + label, timeout=90)
        require(receipt.get("passed") is True and receipt.get("phase") == "unknown-snapshot"
                and receipt.get("admin_id") == admin["id"] and receipt.get("actor_id") == accounts["actor_id"],
                "Unknown admin native snapshot identity differs")
        _, state = fixture._office_private("admin-unknown-state.private.json")
        require(state.get("schema") == 1 and state.get("stage") == "setup_complete"
                and state["observation"]["unknown"]["budget"]["user_id"] == accounts["actor_id"],
                "Unknown admin native private snapshot unavailable")
        packet["snapshot_" + label] = state
        write_private(paths["packet"], packet)
        return state["observation"]

    contexts = set(browser.contexts)
    try:
        snapshot("before")
        page, token = admin_login(browser, base_url, admin, first_login=True)
        page.locator('button[id^="model-selector-"][aria-haspopup="listbox"]').first.click()
        page.locator('button[data-value="' + MODEL + '"]').click()
        page.locator("#chat-input").fill(INTENT)
        with page.expect_response(lambda r: urlsplit(r.url).path == "/api/chat/completions"
                and r.request.method == "POST", timeout=45_000) as pending:
            page.locator("#send-message-button").click()
        response = pending.value
        raw_submission, raw_ack = response.request.post_data, response.body()
        require(isinstance(raw_submission, str) and 0 < len(raw_submission.encode()) <= MAX_BYTES
                and isinstance(raw_ack, bytes) and 0 < len(raw_ack) <= MAX_BYTES,
                "Unknown admin native Send/ACK exceeded bound")
        submitted, chat_id = acknowledgement(response)
        acknowledgement_body = json.loads(raw_ack)
        require(json.loads(raw_submission) == submitted, "Unknown admin raw/native submission differs")
        packet.update(submitted=submitted, raw_submission=raw_submission, http_status=response.status,
            acknowledgement=acknowledgement_body, raw_acknowledgement_base64=base64.b64encode(raw_ack).decode("ascii"))
        write_private(paths["packet"], packet)
        frame, rows, opened = wait_editor(page, base_url, token, chat_id, submitted, admin["id"], MODEL, INTENT,
            fixture.private, "admin-unknown-opened", expected_count=len(accounts["employee_ids"]))
        stored = chat_read(page, base_url, token, chat_id)
        tasks = page.context.request.get(base_url + "/api/tasks/chat/" + chat_id,
            headers={"Authorization": "Bearer " + token}, timeout=10_000)
        require(tasks.status == 200 and tasks.json().get("task_ids") == [], "Unknown admin native tasks remain active")
        html = paths["html"].read_text(encoding="utf8")
        require(len(html.encode()) <= MAX_BYTES and len(json.dumps(stored).encode()) <= MAX_BYTES,
                "Unknown admin persisted context exceeded bound")
        packet.update(opened=opened, rows=rows, html=html, html_sha256=hashlib.sha256(html.encode()).hexdigest(),
                      stored_chat=stored, task_ids=[])
        write_private(paths["packet"], packet)
        actor = frame.locator('section[data-employee-id="' + accounts["actor_id"] + '"]')
        expect(actor).to_have_count(1)
        summary = actor.locator(":scope > p").nth(1)
        visible = {"employee_summary": summary.inner_text(), "employee_primary": summary.locator("strong").inner_text(), "models": {}}
        for alias in accounts["managed_model_ids"]:
            row = actor.locator('tr:has(input[data-model-id="' + alias + '"])')
            expect(row).to_have_count(1)
            cells = row.locator("td")
            visible["models"][alias] = {"primary": cells.nth(1).locator("strong").inner_text(),
                "expense": cells.nth(1).inner_text(), "blocked": cells.nth(2).inner_text()}
        packet["visible"] = visible
        write_private(paths["packet"], packet)
        after = snapshot("after")
        checked = verify_unknown_render(accounts, rows, visible, after["unknown"]["native"]["keys"])
        actor.screenshot(path=str(paths["employee_screenshot"]))
        page.screenshot(path=str(paths["page_screenshot"]))
        require(all(0 < paths[name].stat().st_size <= MAX_BYTES for name in ("page_screenshot", "employee_screenshot")),
                "Unknown admin screenshot exceeded bound")
        packet["presentation"] = checked
        packet["screenshot_sha256"] = {name: hashlib.sha256(paths[name].read_bytes()).hexdigest()
            for name in ("page_screenshot", "employee_screenshot")}
        safe = {"schema": 1, "status": "browser_observed", "admin_id": admin["id"], "actor_id": accounts["actor_id"],
            "model_id": MODEL, "chat_id": chat_id, "answer_id": submitted["id"], "ordinary_sends": 1,
            "tasks_empty": True, "terminal_persisted": True, "html_sha256": packet["html_sha256"],
            "screenshot_sha256": packet["screenshot_sha256"],
            "native_accounting_accepted": False, "provider_dispatch_accepted": False, "whole_goal_accepted": False, **checked}
        no_credentials(safe, [*fixture.secrets, admin["password"], token])
        write_private(paths["packet"], packet)
        return safe, packet
    except Exception as error:
        packet["failure"] = {"error_class": type(error).__name__}
        write_private(paths["packet"], packet)
        raise
    finally:
        for context in set(browser.contexts) - contexts: context.close()


class ServiceAdminFixture(Fixture):
    def snapshot(self, *, expected_rows=None):
        deadline = time.monotonic() + 60
        while True:
            remaining = deadline - time.monotonic()
            require(remaining > 0, "Admin footer native accounting did not converge before the read deadline")
            self.sequence += 1
            result = subprocess.run(self.command + ["exec", "-T", "proxy", "python", "-B", "/proof/prove_service_tasks.py",
                "--phase", "admin-snapshot", "--private-state", "/proof-private/webui-state.private.json",
                "--receipt", "/proof-private/service-admin-observed.safe.json"], capture_output=True, text=True, timeout=min(75, remaining))
            data = json.loads(result.stdout)
            write_json(self.output / ("service-admin-native-%02d.json" % self.sequence), data)
            require(result.returncode == 0 and data.get("passed") is True, "Native service admin snapshot failed")
            count = len(data["positive_spend_logs"])
            require(expected_rows is None or count <= expected_rows, "Admin footer spend rows exceeded the expected two calls")
            personal = data["personal"]
            require(len(personal["users"]) == 4 and len(personal["keys"]) == 8,
                    "Admin footer requires all four personal payers and eight keys")
            ready = accounting_totals_ready(personal["users"], personal["keys"], data["positive_spend_logs"],
                [row["user_id"] for row in personal["users"]], history_complete=expected_rows is None or count == expected_rows)
            if ready:
                return data
            require(time.monotonic() < deadline, "Admin footer native accounting did not converge before the read deadline")
            time.sleep(.25)


def verify_view(before, after, opened, context, provider):
    require(before.get("passed") is after.get("passed") is True and provider.get("synthetic") is True,
            "Admin service browser/native/provider observation failed")
    admin = before["admin_id"]
    uuid(admin)
    require(after["admin_id"] == opened["admin_id"] == opened["parent_author_id"] == admin
            and opened["stored_parent_text"] == INTENT and opened["model_id"] == MODEL
            and opened["terminal_persisted"] is True and opened["exact_submitted_and_stored_strings"] is True,
            "Actual admin view actor/source/model differs")
    for key in ("chat_id", "assistant_id", "parent_user_id"):
        uuid(opened[key])
    require(before["service"] == after["service"] and before["service_payer_id"] == after["service_payer_id"]
            and before["service_payer_id"] != admin, "Admin form changed the native service payer")
    service = after["service"]["users"]
    require(len(service) == 1 and service[0]["user_id"] == after["service_payer_id"]
            and Decimal(service[0]["max_budget_usd"]) == 20 and Decimal(service[0]["spend_usd"]) == Decimal(".2"),
            "Native service footer values differ from the qualified event")
    service_keys = after["service"]["keys"]
    require(len(service_keys) == 1 and service_keys[0]["user_id"] == after["service_payer_id"]
            and service_keys[0]["model"] == "goal584-a" and Decimal(service_keys[0]["max_budget_usd"]) == 20
            and Decimal(service_keys[0]["spend_usd"]) == Decimal(".2")
            and service_keys[0]["budget_reset_at"] == service[0]["budget_reset_at"], "Native service model counter/reset differs")
    require(len(before["personal"]["users"]) == 4 and len(before["personal"]["keys"]) == 8
            and admin in {row["user_id"] for row in before["personal"]["users"]}
            and after["service_payer_id"] not in {row["user_id"] for row in before["personal"]["users"]},
            "Admin/staff personal accounting is incomplete or includes the service payer")
    for snapshot in (before, after):
        verify_accounting_totals(snapshot["personal"]["users"], snapshot["personal"]["keys"],
                                 snapshot["positive_spend_logs"], [row["user_id"] for row in before["personal"]["users"]])
    for section in ("users", "keys"):
        key = lambda row: (row["user_id"], row.get("model", ""))
        previous = sorted(before["personal"][section], key=key)
        current = sorted(after["personal"][section], key=key)
        require(len(previous) == len(current), "Admin view changed native payer/assignment counts")
        for old, new in zip(previous, current):
            delta = Decimal(".4") if new["user_id"] == admin and (section == "users" or new["model"] == "goal584-a") else 0
            require(same_money(new["spend_usd"], Decimal(old["spend_usd"]) + delta)
                    and {field: value for field, value in old.items() if field != "spend_usd"}
                    == {field: value for field, value in new.items() if field != "spend_usd"},
                    "Admin viewing changed staff/service scope, cap/reset/identity or unexpected spend")
    old_ids = {row["request_id"] for row in before["positive_spend_logs"]}
    rows = after["positive_spend_logs"]
    require(len({row["request_id"] for row in rows}) == len(rows)
            and old_ids <= {row["request_id"] for row in rows}, "Prior native admin/staff rows were lost or duplicated")
    new = [row for row in rows if row["request_id"] not in old_ids]
    physical = {entry["id"]: entry for entry in provider["requests"]}
    captures = context["requests"]
    require(len(new) == len(physical) == len(provider["requests"]) == len(captures) == 2
            and set(physical) == {row["request_id"] for row in new}, "Expected exactly two separately billed admin calls")
    by_nonce = {row["owui_budget"]["call_id"]: row for row in new}
    require(len(by_nonce) == 2 and {row["verified_cost_scope"]["call_id"] for row in captures} == set(by_nonce),
            "Admin view signed nonces repeated or did not cover native rows")
    skill, intent, statuses = source_contract()
    for index, captured in enumerate(captures):
        scope = captured["verified_cost_scope"]
        require(scope["category"] == "personal" and scope["user_id"] == captured["user_id"] == admin
                and captured["task"] == "" and scope["model"] == "goal584-a"
                and scope["chat_id"] == scope["root_chat_id"] == opened["chat_id"]
                and scope["answer_id"] == scope["root_answer_id"] == opened["assistant_id"]
                and scope["call_id"] in by_nonce, "Admin report was billed as service or foreign context")
        row = by_nonce[scope["call_id"]]
        require(row["owui_budget"] == scope and row["user_id"] == admin and row["session_id"] == opened["chat_id"]
                and row["model_group"] == "goal584-a" and Decimal(row["spend_usd"]) == Decimal(".2")
                and [row[field] for field in ("prompt_tokens", "completion_tokens", "total_tokens")] == [10, 5, 15],
                "Admin reporting row differs from actual attribution/usage/cost")
        compare_provider(captured, physical[row["request_id"]], "goal584-a")
        names, messages = tool_schemas(captured["body"]), captured["body"]["messages"]
        require(any(message.get("role") in ("system", "developer") and skill.strip() in text(message.get("content", ""))
                    for message in messages), "Full admin Skill was omitted or demoted")
        require([text(message["content"]) for message in messages if message.get("role") == "user"] == [intent],
                "Original native view intent changed")
        calls = [call for message in messages for call in message.get("tool_calls", [])]
        outputs = [message for message in messages if message.get("role") == "tool"]
        require(len(calls) == len(outputs) == index, "Admin view executed an extra Tool round")
        if index:
            require(calls[0]["function"]["name"] == names["open_budget_form"]
                    and json.loads(calls[0]["function"]["arguments"]) == {"view_json": "{}"}
                    and outputs[0]["tool_call_id"] == calls[0]["id"]
                    and json.loads(text(outputs[0]["content"])) == statuses["opened"], "Native open arguments/result correlation changed")
    return {"admin_physical_calls": 2, "admin_reporting_cost_usd": "0.40", "service_spend_usd": "0.20",
            "service_counter_unchanged": True, "all_staff_state_unchanged": True,
            "full_skill_schemas_and_native_context_verified": True, "reporting_billed_to_admin_personal_identity": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    for name in ("admin-accounts", "env-file", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    target = urlsplit(args.base_url)
    require(target.scheme == "http" and target.port == 8080 and target.path in ("", "/")
            and not target.username and not target.password and not target.query and not target.fragment
            and isinstance(ipaddress.ip_address(target.hostname), ipaddress.IPv4Address)
            and ipaddress.ip_address(target.hostname).is_private, "Service admin browser target must be disposable private IPv4:8080")
    for private in (args.admin_accounts, args.env_file):
        require(args.output.resolve() not in private.resolve().parents, "Private account/config cannot be uploaded")
    args.output.mkdir(exist_ok=True)
    handoff = json.loads(args.admin_accounts.read_text(encoding="utf-8"))
    require(handoff.get("schema") == 1 and handoff.get("model_id") == MODEL, "Native admin handoff differs")
    admin, fixture = handoff["admin"], ServiceAdminFixture(args.env_file, args.output)
    receipt = {"schema": 1, "proof": "goal584-service-admin-browser", "passed": False,
               "not_qualified": ["automatic_background_tasks", "embeddings", "production", "paid_provider"],
               "started_at_utc": datetime.now(timezone.utc).isoformat()}
    browser = None
    playwright = sync_playwright().start()
    try:
        before = fixture.snapshot()
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        page, token = admin_login(browser, args.base_url, admin, first_login=False)
        page.locator('button[id^="model-selector-"][aria-haspopup="listbox"]').first.click()
        page.locator('button[data-value="' + MODEL + '"]').click()
        page.locator("#chat-input").fill(INTENT)
        with page.expect_response(lambda response: urlsplit(response.url).path == "/api/chat/completions"
                                  and response.request.method == "POST") as pending:
            page.locator("#send-message-button").click()
        sent, chat_id = acknowledgement(pending.value)
        frame, _, opened = wait_editor(page, args.base_url, token, chat_id, sent, admin["id"], MODEL, INTENT,
                                        args.output, "service-admin-opened", expected_count=3)
        panel = frame.locator('aside[data-service-budget="v1"]')
        expect(panel).to_have_count(1)
        expect(panel).to_be_visible()
        expect(panel.locator("[data-service-cap]")).to_have_text("20")
        expect(panel.locator("[data-service-spend]")).to_have_text("0.2")
        expect(panel.locator("[data-service-remaining]")).to_have_text("19.8")
        expect(panel).to_contain_text(before["service"]["users"][0]["budget_reset_at"])
        expect(panel.locator("input,button,select,textarea,form,[contenteditable]")).to_have_count(0)
        panel.screenshot(path=str(args.output / "service-admin-readonly-footer.png"))
        after = fixture.snapshot(expected_rows=len(before["positive_spend_logs"]) + 2)
        result = verify_view(before, after, opened, fixture.context(), fixture.provider())
        receipt.update(result, passed=True, opened=opened, visible_service_footer={"cap_usd": "20", "spend_usd": "0.2",
            "remaining_usd": "19.8", "read_only": True, "native_reset_visible": True},
            final_native_receipt="service-admin-native-%02d.json" % fixture.sequence)
    except Exception as error:
        receipt["failure"] = re.sub(r"(?:sk-|gw-)[A-Za-z0-9_-]{16,}", "[credential-redacted]", safe_failure(error, [admin]))
        for observe in (fixture.provider, fixture.context):
            try:
                observe()
            except Exception:
                pass
    finally:
        if browser is not None:
            browser.close()
        playwright.stop()
    receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(args.output / "service-admin-browser.json", receipt)
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
