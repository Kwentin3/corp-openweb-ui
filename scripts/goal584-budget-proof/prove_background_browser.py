#!/usr/bin/env python3
"""Two visible fresh Hi chats; actual native automatic background lifecycle.

Host-only Playwright driver for the disposable private WebUI. Proxy companion
owns bounded config/readback; all inference begins at ordinary visible Send.
"""
import argparse
from datetime import datetime, timezone
import ipaddress
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

from prove_webui_browser import Fixture, chat, login, require, safe_failure, write_json


MODEL = "goal584-a"
TASKS = {"title_generation": True, "tags_generation": True, "follow_up_generation": True}


class BackgroundFixture(Fixture):
    def phase(self, phase, call=None):
        self.sequence += 1
        command = self.command + ["exec", "-T", "proxy", "python", "-B", "/proof/prove_background_tasks.py",
            "--phase", phase, "--private-state", "/proof-private/webui-state.private.json",
            "--receipt", "/proof-private/background-phase.safe.json",
            "--context-receipt", "/proof-private/background-context.safe.json",
            "--provider-receipt", "/proof-private/background-provider.safe.json"]
        if call is not None:
            command += ["--chat-id", call["chat_id"], "--answer-id", call["message_id"]]
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
        try:
            receipt = json.loads(result.stdout)
        except ValueError:
            raise AssertionError("Background native phase did not return safe JSON: " + phase) from None
        write_json(self.output / ("background-native-%02d-%s.json" % (self.sequence, phase)), receipt)
        self.last_receipt = receipt
        require(result.returncode == 0 and receipt.get("passed") is True, "Background native phase failed: " + phase)
        return receipt


def check_submission(sent):
    require(isinstance(sent, dict) and sent.get("model") == MODEL and not sent.get("models")
            and sent.get("background_tasks") == TASKS, "Browser did not request exactly the three native automatic tasks")
    user = sent.get("user_message")
    require(isinstance(user, dict) and user.get("role") == "user" and user.get("content") == "Hi"
            and user.get("parentId") is None, "Browser background proof did not submit one fresh Hi turn")
    return {"model": sent["model"], "background_tasks": sent["background_tasks"],
            "fresh_user_message": True, "ordinary_native_main_path": True}


def verify_browser_result(calls, verified, restored, final_snapshot, physical, context):
    require(len(calls) == 2 and calls[0]["chat_id"] != calls[1]["chat_id"]
            and all(call.get("user_id") == verified.get("actor_id")
                    and call.get("model") == MODEL and call.get("outcome") == "success"
                    and call.get("native_cost_status") is True and call.get("terminal_persisted") is True for call in calls),
            "Background browser did not complete two distinct ordinary costed replies")
    require(verified.get("stage") == "events_verified" and restored.get("stage") == "qualified_automatic_background"
            and restored.get("task_config_restored") is True and restored.get("provider_controls_restored") is True,
            "Background proof did not restore full native task/provider config")
    require(final_snapshot.get("observed_native") == verified.get("after")
            and physical.get("synthetic") is True and len(physical.get("requests", [])) == 5
            and physical.get("control") == verified["provider_control_observations"]["original"]
            and context.get("schema") == 1 and len(context.get("requests", [])) == 8,
            "Background final native/provider/capture observations changed after restoration")
    for field, call in (("baseline_chat", calls[0]), ("service_chat", calls[1])):
        require(verified[field]["chat_id"] == call["chat_id"] and verified[field]["answer_id"] == call["message_id"],
                "Background native observations belong to different browser replies")
    result = verified.get("result", {})
    require(result.get("physical_calls") == 5 and result.get("personal_cost_usd") == "0.40"
            and result.get("service_cost_usd") == "0.60" and result.get("custom_auth_unsigned_403_count") == 3
            and result.get("full_baseline_service_provider_context_equal") is True,
            "Background native context/accounting verification did not pass")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("base-url", "accounts", "env-file", "output"):
        parser.add_argument("--" + name, type=str if name == "base-url" else Path, required=True)
    args = parser.parse_args()
    target = urlsplit(args.base_url)
    require(target.scheme == "http" and target.port == 8080 and target.path in ("", "/")
            and not target.username and not target.password and not target.query and not target.fragment
            and ipaddress.ip_address(target.hostname).is_private, "Background browser target must be the isolated private WebUI")
    args.output.mkdir(exist_ok=True)
    require(not args.accounts.resolve().is_relative_to(args.output.resolve())
            and not args.output.resolve().is_relative_to(args.accounts.resolve().parent),
            "Background private account handoff overlaps uploaded output")
    accounts = json.loads(args.accounts.read_text(encoding="utf-8"))["users"]
    require(len(accounts) == 2, "Background proof requires existing two-employee handoff")
    fixture = BackgroundFixture(args.env_file, args.output)
    receipt = {"schema": 1, "proof": "goal584-native-automatic-background-browser", "passed": False, "calls": [],
               "started_at_utc": datetime.now(timezone.utc).isoformat(),
               "not_qualified": ["multi_model", "arena", "automation", "shared_chat", "temporary_chat",
                                 "standalone_auxiliary_endpoints", "embeddings", "production", "paid_provider"]}
    browser = playwright = None
    prepare_attempted, verified, restored = False, None, None
    final_snapshot, final_provider, final_context = {}, {}, {}
    try:
        prepare_attempted = True
        fixture.phase("baseline-prepare")
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        receipt["browser_version"] = browser.version
        _, page, token = login(browser, args.base_url, accounts[0])
        submissions = []
        def observe_request(request):
            if request.method == "POST" and urlsplit(request.url).path == "/api/chat/completions":
                submissions.append(request.post_data_json)
        page.on("request", observe_request)
        for label, phase in (("baseline", "baseline-observe"), ("service", "verify")):
            if label == "service":
                fixture.phase("service-prepare")
            before = len(submissions)
            call = chat(page, args.base_url, token, accounts[0]["id"], MODEL, "success",
                        "background-" + label, args.output, expected_costs=("0.20", "0.20"))
            require(len(submissions) == before + 1, "Background browser dispatched more than one main request")
            call.update(user_id=accounts[0]["id"], submission=check_submission(submissions[-1]))
            receipt["calls"].append(call)
            observation = fixture.phase(phase, call)
            if label == "service":
                verified = observation
                # Reload proves saved native presentation, independently of an
                # optimistic websocket event or the companion's expected JSON.
                page.reload(wait_until="domcontentloaded")
                card = page.locator("#message-" + call["message_id"])
                expect(card.get_by_role("button", name="Follow up: Proof", exact=True)).to_be_visible()
                expect(page.locator('a[href="/c/' + call["chat_id"] + '"]').filter(has_text="Proof").first).to_be_visible()
                expect(card).to_contain_text("Ответ: $0.20 · Чат: $0.20")
                page.screenshot(path=str(args.output / "background-service-saved-results.png"))
                receipt["saved_native_presentation"] = {"title_visible": True, "follow_up_visible": True,
                    "tags": observation["service_chat"]["tags"], "personal_answer_chat_cost_usd": "0.20"}
        fixture.provider()
        fixture.context()
    except Exception as error:
        receipt["failure"] = re.sub(r"(?:sk-|gw-)[A-Za-z0-9_-]{16,}", "[credential-redacted]", safe_failure(error, accounts))
    finally:
        if prepare_attempted:
            try:
                restored = fixture.phase("restore")
                receipt["task_config_restored"] = restored.get("task_config_restored") is True
                receipt["provider_controls_restored"] = restored.get("provider_controls_restored") is True
            except Exception:
                partial = getattr(fixture, "last_receipt", {})
                partial = partial if partial.get("phase") == "restore" else {}
                receipt["task_config_restored"] = partial.get("task_config_restored") is True
                receipt["provider_controls_restored"] = partial.get("provider_controls_restored") is True
                receipt["restoration_failure"] = "Full native task/provider config restoration failed"
        if verified is not None and restored is not None:
            try:
                final_snapshot = fixture.phase("snapshot")
            except Exception:
                receipt["final_snapshot_failure"] = "Post-restoration native snapshot unavailable"
        try:
            final_provider, final_context = fixture.provider(), fixture.context()
        except Exception:
            receipt["final_observation_failure"] = "Final native background observations unavailable"
        if browser is not None:
            browser.close()
        if playwright is not None:
            playwright.stop()
    if "failure" not in receipt and verified is not None and restored is not None:
        try:
            receipt.update(verify_browser_result(receipt["calls"], verified, restored, final_snapshot, final_provider, final_context), passed=True)
        except Exception as error:
            receipt["failure"] = safe_failure(error, accounts)
    receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(args.output / "background-browser.json", receipt)
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
