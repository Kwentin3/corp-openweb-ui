#!/usr/bin/env python3
"""Proxy-side native observations/config for two real ordinary-browser chats.

Only the existing disposable native fixture is accepted. Browser chat actions
trigger tasks; this coordinator never calls inference or edits application DBs.
Baseline and signed task contexts are paired after native parameter owners.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re

import capture_webui_auth as capture
from employee_budget_admin_contract import BudgetAdminError
from provenance import validate_persisted_scope, validate_persisted_service_scope
from prove_native_budgets import amount, close_amount
from prove_service_tasks import (FUNCTION_ID, PARAMS, SOURCE, budgets, canonical, no_secrets,
                                 provider, response, semantic, task_config_evidence)
from provision_webui import (MODELS, OPERATOR_STATE, TASK_FLAGS, WebUI, native_client,
                             read_private, write_private, require, ProofError)
from provision_cost_display import STATE, model_body, secret_values, source_hash


TASKS = ("title_generation", "tags_generation", "follow_up_generation")
TASK_ENABLES = ("ENABLE_TITLE_GENERATION", "ENABLE_TAGS_GENERATION", "ENABLE_FOLLOW_UP_GENERATION")
USAGE = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
UNION = {"title": "Proof", "tags": ["Proof"], "follow_ups": ["Proof"]}
MAX_BYTES = 4 * 1024 * 1024
PROVIDER_OPTIONALS = ("native_tasks_mode", "response_status", "after_first_chunk_delay_ms")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def capture_state():
    with capture.capture_lock():
        result = capture._read_locked()
    require(len(result["requests"]) <= 8, "Background capture exceeded eight planned attempts")
    return no_secrets(result)


def project_budget(budget):
    def convert(value):
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, dict):
            return {key: convert(child) for key, child in value.items()}
        if isinstance(value, (tuple, list)):
            return [convert(child) for child in value]
        return value
    return convert(asdict(budget))


def project_row(row, budget):
    """Validate native persisted scope and emit only money/identity evidence."""
    metadata = row.get("metadata")
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    scope = (metadata.get("spend_logs_metadata") or {}).get("owui_budget") if isinstance(metadata, dict) else None
    require(isinstance(scope, dict), "Positive native background history lacks scope")
    scope = (validate_persisted_service_scope(scope) if scope.get("category") == "service"
             else validate_persisted_scope(scope))
    matches = [key for key in budget.models if key.model == scope["model"]]
    require(len(matches) == 1 and row.get("api_key") == matches[0].key_hash
            and row.get("user") == scope["user_id"] == budget.user_id
            and row.get("model_group") == scope["model"] and row.get("status") == "success"
            and Decimal(str(row.get("spend"))) > 0,
            "Native background history identity/assignment/status differs")
    expected_session = "owui-service:" + scope["chat_id"] if scope["category"] == "service" else scope["chat_id"]
    require(row.get("session_id") == expected_session, "Native background history session differs")
    identifier = row.get("request_id")
    require(isinstance(identifier, str) and re.fullmatch(r"chatcmpl-goal584-[0-9a-f]{32}", identifier),
            "Native background history request identity differs")
    usage = {key: row.get(key) for key in USAGE}
    require(all(type(value) is int and value >= 0 for value in usage.values())
            and usage["prompt_tokens"] + usage["completion_tokens"] == usage["total_tokens"],
            "Native background history usage differs")
    return {"request_id": identifier, "user_id": budget.user_id, "key_hash": row["api_key"],
            "model": scope["model"], "session_id": row["session_id"], "status": row["status"],
            "spend_usd": str(Decimal(str(row["spend"]))), "usage": usage, "scope": scope}


def snapshot(webui, state):
    payer = canonical(state["service_fixture"]["payer_id"])
    personal, service = asyncio.run(budgets(state, payer))
    accounts = [*personal, service]
    native = native_client(state)
    rows, zero_ids = [], {}
    for budget in accounts:
        zero_ids[budget.user_id] = []
        for row in native.logs(budget.user_id):
            spend = Decimal(str(row.get("spend", 0)))
            require(spend.is_finite() and spend >= 0, "Native background history has invalid spend")
            if spend > 0:
                rows.append(project_row(row, budget))
            else:
                identifier = row.get("request_id")
                require(isinstance(identifier, str) and 0 < len(identifier) <= 512,
                        "Unqualified zero-cost native row identity unavailable")
                zero_ids[budget.user_id].append(identifier)
        require(len(zero_ids[budget.user_id]) == len(set(zero_ids[budget.user_id])),
                "Unqualified zero-cost native row identity duplicated")
        zero_ids[budget.user_id].sort()
    require(len({row["request_id"] for row in rows}) == len(rows), "Native background history duplicated request IDs")
    return no_secrets({"budgets": sorted([project_budget(budget) for budget in accounts], key=lambda item: item["user_id"]),
        "rows": sorted(rows, key=lambda item: item["request_id"]), "unqualified_zero_request_ids": zero_ids,
        "models": {model: model_body(webui.model(state["admin"]["token"], model))
                   for model in (*MODELS, FUNCTION_ID)}})


def verify_finance(before, after, actor, payer, *, primary_count, service_count):
    require(before["models"] == after["models"], "Background tasks changed native model profiles")
    previous_zero, current_zero = before["unqualified_zero_request_ids"], after["unqualified_zero_request_ids"]
    require(previous_zero.keys() == current_zero.keys()
            and all(set(ids) <= set(current_zero[uid]) for uid, ids in previous_zero.items()),
            "Background tasks removed pre-existing unqualified zero-cost native row identities")
    old = {entry["user_id"]: entry for entry in before["budgets"]}
    current = {entry["user_id"]: entry for entry in after["budgets"]}
    require(len(old) == len(before["budgets"]) == len(current) == len(after["budgets"]) == 5
            and set(old) == set(current) and actor != payer and {actor, payer} <= set(old),
            "Background native payer set differs")
    for uid, previous in old.items():
        updated = copy.deepcopy(current[uid])
        delta = Decimal(".20") * (primary_count if uid == actor else service_count if uid == payer else 0)
        expected_spend = amount(previous["spend"]) + delta
        require(close_amount(updated["spend"], expected_spend) if delta else amount(updated["spend"]) == expected_spend,
                "Background native payer spend delta differs")
        updated["spend"] = previous["spend"]
        require(len(updated["models"]) == len(previous["models"]), "Background assignment count changed")
        for prior_key, key in zip(previous["models"], updated["models"]):
            expected = delta if key["model"] == MODELS[0] else 0
            expected_spend = amount(prior_key["spend"]) + expected
            require(close_amount(key["spend"], expected_spend) if expected else amount(key["spend"]) == expected_spend,
                    "Background native per-model key spend delta differs")
            key["spend"] = prior_key["spend"]
        require(updated == previous, "Background task changed cap/reset/key identity or other native budget state")
    old_rows = {row["request_id"]: row for row in before["rows"]}
    new_rows = {row["request_id"]: row for row in after["rows"]}
    require(len(old_rows) == len(before["rows"]) and len(new_rows) == len(after["rows"])
            and old_rows.keys() <= new_rows.keys()
            and all(new_rows[identifier] == row for identifier, row in old_rows.items()),
            "Background tasks altered existing native financial history")
    added = [row for identifier, row in new_rows.items() if identifier not in old_rows]
    require(len(added) == primary_count + service_count
            and sum(row["user_id"] == actor for row in added) == primary_count
            and sum(row["user_id"] == payer for row in added) == service_count
            and all(row["model"] == MODELS[0] and Decimal(row["spend_usd"]) == Decimal(".20")
                    and row["usage"] == USAGE for row in added), "Background new native calls/usage/cost differ")
    for budget in after["budgets"]:
        own = [row for row in after["rows"] if row["user_id"] == budget["user_id"]]
        expected_spend = sum((Decimal(row["spend_usd"]) for row in own), Decimal(0))
        require(close_amount(budget["spend"], expected_spend) if expected_spend > 0 else amount(budget["spend"]) == 0,
                "Background native total payer counter differs from full positive history")
        for key in budget["models"]:
            expected_spend = sum((Decimal(row["spend_usd"]) for row in own if row["key_hash"] == key["key_hash"]), Decimal(0))
            require(close_amount(key["spend"], expected_spend) if expected_spend > 0 else amount(key["spend"]) == 0,
                    "Background native total key counter differs from full positive history")
    return added


def counter_ready(actual, previous, delta):
    """Existing native float tolerance only for an expected positive change."""
    observed, expected = amount(actual), amount(previous) + delta
    if delta == 0:
        require(observed == expected, "Unchanged background native counter changed while settling")
        return True
    if close_amount(observed, expected):
        return True
    require(observed < expected, "Background native counter exceeded expected spend while settling")
    return False


def text(value):
    if isinstance(value, str):
        return value
    require(isinstance(value, list) and all(isinstance(part, dict) and set(part) == {"type", "text"}
            and part["type"] == "text" and isinstance(part["text"], str) for part in value),
            "Background fixture content has an unexpected native shape")
    return "".join(part["text"] for part in value)


def saved_evidence(saved, actor, chat_id, answer_id, *, signed):
    require(saved.get("id") == chat_id and saved.get("user_id") == actor, "Background native Chat owner differs")
    messages = ((saved.get("chat") or {}).get("history") or {}).get("messages")
    require(isinstance(messages, dict) and len(messages) == 2, "Background proof requires one fresh native Hi turn")
    answer = messages.get(answer_id)
    users = [message for message in messages.values() if message.get("role") == "user"]
    require(len(users) == 1 and text(users[0].get("content")) == "Hi" and users[0].get("parentId") is None
            and isinstance(answer, dict) and answer.get("role") == "assistant" and answer.get("done") is True
            and not answer.get("error") and answer.get("content") == "Proof" and answer.get("model") == MODELS[0]
            and answer.get("parentId") == users[0].get("id"), "Background native saved messages differ")
    statuses = [item for item in answer.get("statusHistory", []) if item.get("action") == "employee_budget_cost"]
    require(statuses and "Ответ: $0.20 · Чат: $0.20" in statuses[-1].get("description", ""),
            "Background service spend leaked into native personal answer/chat cost")
    title, tags, followups = saved.get("title"), (saved.get("meta") or {}).get("tags", []), answer.get("followUps", [])
    require(title == ("Proof" if signed else "Hi") and tags == (["proof"] if signed else [])
            and followups == (["Proof"] if signed else []), "Background native title/tags/follow-ups differ")
    return {"chat_id": chat_id, "answer_id": answer_id, "user_message_id": canonical(users[0]["id"]),
            "title": title, "tags": tags, "follow_ups": followups, "content": "Proof",
            "done": True, "cost_status": statuses[-1]["description"]}


def grouped_context(records):
    require(len(records) == 4, "Background chat did not produce one primary plus three native task attempts")
    groups = {}
    for record in records:
        task = record.get("task") or "primary"
        require(task in (*TASKS, "primary") and task not in groups, "Background task attempt duplicated or unknown")
        require("body_after_auth" in record and record["body"] == record["body_after_auth"],
                "Background native authentication changed semantic model context")
        groups[task] = record
    require(set(groups) == {*TASKS, "primary"}, "Background task context omitted an expected task")
    return groups


def verify_context(baseline, signed, physical, added, actor, payer, chats):
    left, right = grouped_context(baseline), grouped_context(signed)
    require(len(physical) == 5 and len({row["id"] for row in physical}) == 5,
            "Background phase must contain exactly five unique physical calls")
    native = {row["request_id"]: row for row in added}
    require(set(native) == {row["id"] for row in physical}, "Background native/provider request identities differ")
    by_task, call_ids = {}, set()
    for task in ("primary", *TASKS):
        a, b = left[task], right[task]
        require(a["user_id"] == b["user_id"] == actor and a["body"] == b["body"],
                "Background baseline/service full semantic context differs")
        require(b.get("provenance_removed_after") is True and b.get("attestation_present_before") is True
                and "auth_failure" not in b, "Background signed provenance was not consumed")
        if task != "primary":
            require(a.get("attestation_present_before") is False and "native_auth_user_id" not in a
                    and "verified_cost_scope" not in a and a.get("auth_failure") == {
                        "scope": "custom_auth", "status_code": 403, "code": "invalid_signed_budget_provenance"},
                    "Background unsigned task did not reach the intended custom-auth 403 guard")
            require(all(b["body"].get(key) == value for key, value in PARAMS.items())
                    and b["body"].get("stream") is False and b.get("native_stream_usage_patch") == {},
                    "Background native task parameters differ")
        for index, record in enumerate((a, b) if task == "primary" else (b,)):
            scope = record.get("verified_cost_scope")
            scope = (validate_persisted_scope(scope) if task == "primary" else validate_persisted_service_scope(scope))
            chat = chats[index] if task == "primary" else chats[1]
            require(scope["chat_id"] == chat["chat_id"] and scope["model"] == MODELS[0]
                    and scope["call_id"] not in call_ids and record.get("native_auth_user_id") == scope["user_id"],
                    "Background signed scope identity/model/nonce differs")
            call_ids.add(scope["call_id"])
            if task == "primary":
                require(scope["user_id"] == actor and scope["answer_id"] == scope["root_answer_id"] == chat["answer_id"]
                        and scope["root_chat_id"] == chat["chat_id"], "Background primary paid root differs")
                require(record.get("attestation_present_before") is True and record.get("provenance_removed_after") is True
                        and "auth_failure" not in record and record["body"].get("stream") is True,
                        "Background primary authentication/stream differs")
                users = [message for message in record["body"].get("messages", []) if message.get("role") == "user"]
                require(len(users) == 1 and text(users[0].get("content")) == "Hi"
                        and all(message.get("role") in ("system", "user") for message in record["body"]["messages"]),
                        "Background primary full context is not a fresh Hi turn")
            else:
                require(scope["user_id"] == payer and scope["actor_id"] == actor and scope["task"] == task,
                        "Background native service actor/payer/task differs")
            rows = [row for row in added if row["scope"] == scope]
            require(len(rows) == 1, "Background gateway scope lacks one exact native ledger row")
            row = rows[0]
            request, = [entry for entry in physical if entry["id"] == row["request_id"]]
            require(request.get("usage") == USAGE and request.get("lifecycle", {}).get("terminal") is True
                    and request["lifecycle"].get("outcome") == "completed"
                    and not any(key in request["body"] for key in ("metadata", "litellm_metadata", "owui_budget_provenance")),
                    "Background provider lifecycle/usage/private metadata differs")
            expected = semantic({**copy.deepcopy(record["body"]), **record["native_stream_usage_patch"], "model": "goal584-fake-a"})
            if task != "primary":
                require(expected.pop("stream") is False and "stream" not in request["body"],
                        "Background native nonstream provider normalization differs")
            require(semantic(request["body"]) == expected, "Background actual provider full semantic context differs")
            if task != "primary":
                actual_response = request.get("response")
                require(isinstance(actual_response, dict) and actual_response.get("id") == request["id"]
                        and actual_response.get("model") == "goal584-fake-a" and actual_response.get("usage") == USAGE,
                        "Background actual retained provider response identity/usage differs")
                choices = actual_response.get("choices", [])
                require(len(choices) == 1 and choices[0].get("finish_reason") == "stop"
                        and choices[0].get("message", {}).get("role") == "assistant"
                        and json.loads(choices[0].get("message", {}).get("content", "null")) == UNION,
                        "Background actual provider response does not supply usable native results")
                output = json.loads(choices[0]["message"]["content"])
                saved_output = {"title_generation": chats[1]["title"], "tags_generation": chats[1]["tags"],
                                "follow_up_generation": chats[1]["follow_ups"]}[task]
                expected_output = (output["title"] if task == "title_generation" else
                                   [tag.replace(" ", "_").lower() for tag in output["tags"]]
                                   if task == "tags_generation" else output["follow_ups"])
                require(saved_output == expected_output, "Background saved native output differs from actual provider response")
                by_task[task] = request
            elif index == 1:
                by_task["primary"] = request
    title_messages = right["title_generation"]["body"].get("messages", [])
    histories = [match.group(1).strip() for message in title_messages for match in
                 re.finditer(r"<chat_history>(.*?)</chat_history>", text(message.get("content")), re.S)]
    require(len(histories) == 1 and histories[0] in ("USER: Hi", "USER: Hi\nASSISTANT:"),
            "Background initial title did not use the observed pre-output Hi history")
    require(by_task["title_generation"]["lifecycle"]["started_monotonic"]
            < by_task["primary"]["lifecycle"]["terminal_monotonic"],
            "Background initial title did not arrive before the observed primary terminal stage")
    return {"task_context_sha256": {task: digest(right[task]["body"]) for task in right},
            "initial_title_history": histories[0], "initial_title_before_primary_terminal": True,
            "custom_auth_unsigned_403_count": 3, "physical_calls": 5, "personal_cost_usd": "0.40",
            "service_cost_usd": "0.60", "total_cost_usd": "1.00",
            "full_baseline_service_provider_context_equal": True, "actual_provider_results_match_saved_native_outputs": True}


def configure(webui, state, target):
    fixture = state["background_fixture"]
    expected = copy.deepcopy(fixture["original_task_config"])
    expected.update({flag: False for flag in TASK_FLAGS})
    expected.update({flag: True for flag in TASK_ENABLES})
    expected.update(TASK_MODEL=target, TASK_MODEL_EXTERNAL=target, TASK_MODEL_PARAMS=copy.deepcopy(PARAMS))
    admin = state["admin"]
    fixture["task_config_restored"] = False
    webui.session(admin, "admin")
    webui.ok("POST", "/api/v1/tasks/config/update", token=admin["token"], body=expected)
    require(webui.ok("GET", "/api/v1/tasks/config", token=admin["token"]) == expected,
            "Background native task config readback differs")
    return expected


def prepare(webui, state):
    require("background_fixture" not in state and state.get("service_fixture", {}).get("stage") == "qualified_direct_title"
            and state["service_fixture"].get("task_config_restored") is True, "Background proof requires a fresh post-title fixture")
    admin = state["admin"]
    webui.session(admin, "admin")
    webui.session(state["users"][0], "user")
    installed = webui.ok("GET", "/api/v1/functions/id/" + FUNCTION_ID, token=admin["token"])
    require(installed.get("is_active") is True and installed.get("user_id") == admin["id"]
            and source_hash(installed.get("content", "")) == source_hash(SOURCE.read_text(encoding="utf-8")),
            "Background installed Pipe source/owner/activation differs")
    require(webui.ok("GET", "/api/v1/functions/id/" + FUNCTION_ID + "/valves", token=admin["token"])
            == {"target_model_id": MODELS[0]}, "Background Pipe target differs")
    original = webui.ok("GET", "/api/v1/tasks/config", token=admin["token"])
    before = snapshot(webui, state)
    service = next(row for row in before["budgets"] if row["user_id"] == state["service_fixture"]["payer_id"])
    require(close_amount(service["spend"], Decimal(".20")) and Decimal(service["max_budget"]) == 20,
            "Background proof requires the qualified single direct-title service balance")
    state["background_fixture"] = {"stage": "preparing_baseline", "original_task_config": copy.deepcopy(original),
        "original_provider_control": copy.deepcopy(provider()["control"]), "provider_controls_restored": True,
        "before": before, "pipe_sha256": source_hash(installed["content"]), "task_config_restored": True}


def restore_controls(webui, state):
    """Attempt both existing owners, even if restoring either owner fails."""
    fixture, admin = state["background_fixture"], state["admin"]
    original, control = fixture.get("original_task_config"), fixture.get("original_provider_control")
    require(isinstance(original, dict) and isinstance(control, dict), "Background original configuration unavailable for restoration")
    fixture.update(task_config_restored=False, provider_controls_restored=False)
    failures = []
    try:
        webui.session(admin, "admin")
        webui.ok("POST", "/api/v1/tasks/config/update", token=admin["token"], body=original)
        require(webui.ok("GET", "/api/v1/tasks/config", token=admin["token"]) == original,
                "Background full native task config restoration failed")
        fixture["task_config_restored"] = True
    except Exception:
        failures.append("task_config")
    try:
        payload = {**copy.deepcopy(control), **{key: None for key in PROVIDER_OPTIONALS if key not in control}}
        provider("POST", "/__proof/control", payload)
        require(provider()["control"] == control, "Background provider control restoration readback differs")
        fixture["provider_controls_restored"] = True
    except Exception:
        failures.append("provider_controls")
    require(not failures, "Background configuration restoration failed: " + ",".join(failures))


def observe(webui, state, chat_id, answer_id, *, signed):
    fixture, actor, payer = state["background_fixture"], state["users"][0], state["service_fixture"]["payer_id"]
    def settled():
        contexts, physical = capture_state(), provider()
        expected_attempts, expected_calls = (8, 5) if signed else (4, 1)
        require(len(contexts["requests"]) <= expected_attempts and len(physical["requests"]) <= expected_calls,
                "Background native task/provider count exceeded the planned phase")
        if len(contexts["requests"]) != expected_attempts or len(physical["requests"]) != expected_calls:
            return None
        if not all("body_after_auth" in row for row in contexts["requests"]) or not all(
                row.get("lifecycle", {}).get("terminal") is True for row in physical["requests"]):
            return None
        status, tasks = response(webui, "GET", "/api/tasks/chat/" + chat_id, actor["token"])
        require(status == 200 and isinstance(tasks.get("task_ids"), list), "Background native task readback failed")
        if tasks["task_ids"]:
            return None
        current = snapshot(webui, state)
        previous = {row["user_id"]: row for row in fixture["before"]["budgets"]}
        # Spend logs and counters are separate native asynchronous writes. A
        # completed provider response alone is not settlement readiness.
        ready = True
        for budget in current["budgets"]:
            delta = Decimal(".20") * ((2 if signed else 1) if budget["user_id"] == actor["id"]
                                      else 3 if signed and budget["user_id"] == payer else 0)
            prior = previous.get(budget["user_id"])
            require(prior is not None, "Background native payer set changed while settling")
            if not counter_ready(budget["spend"], prior["spend"], delta):
                ready = False
            old_keys = {key["model"]: key for key in prior["models"]}
            for key in budget["models"]:
                require(key["model"] in old_keys, "Background native assignment changed while settling")
                if not counter_ready(key["spend"], old_keys[key["model"]]["spend"], delta if key["model"] == MODELS[0] else Decimal(0)):
                    ready = False
        if not ready or len(current["rows"]) < len(fixture["before"]["rows"]) + expected_calls:
            return None
        added = verify_finance(fixture["before"], current, actor["id"], payer,
                               primary_count=2 if signed else 1, service_count=3 if signed else 0)
        status, saved = response(webui, "GET", "/api/v1/chats/" + chat_id, actor["token"])
        require(status == 200, "Background native saved Chat readback failed")
        saved_chat = saved_evidence(saved, actor["id"], chat_id, answer_id, signed=signed)
        return contexts, physical, current, added, saved_chat
    return native_client(state).poll("automatic background tasks and native accounting", settled)


def run_phase(webui, state, args):
    phase = args.phase
    if phase == "baseline-prepare":
        prepare(webui, state)
        # Persist restoration authority before the first config write/control.
        write_private(args.private_state, state)
        config = configure(webui, state, MODELS[0])
        state["background_fixture"]["provider_controls_restored"] = False
        provider("POST", "/__proof/reset", {})
        provider("POST", "/__proof/control", {"native_tasks_mode": True, "delay_ms": 1500})
        capture.save({"schema": 1, "requests": []})
        state["background_fixture"].update(stage="baseline_ready", baseline_config=copy.deepcopy(config))
    elif phase == "service-prepare":
        fixture = state["background_fixture"]
        require(fixture["stage"] == "baseline_verified", "Background signed phase requires verified baseline")
        config = configure(webui, state, FUNCTION_ID)
        require({k: v for k, v in config.items() if k not in ("TASK_MODEL", "TASK_MODEL_EXTERNAL")}
                == {k: v for k, v in fixture["baseline_config"].items() if k not in ("TASK_MODEL", "TASK_MODEL_EXTERNAL")},
                "Background paired native config changed beyond task-model selection")
        fixture.update(stage="service_ready", service_config=copy.deepcopy(config))
    elif phase in ("baseline-observe", "verify"):
        fixture = state["background_fixture"]
        signed = phase == "verify"
        require(fixture["stage"] == ("service_ready" if signed else "baseline_ready"), "Background observation phase is out of order")
        chat_id, answer_id = canonical(args.chat_id), canonical(args.answer_id)
        contexts, physical, current, added, chat = observe(webui, state, chat_id, answer_id, signed=signed)
        if signed:
            require(chat["chat_id"] != fixture["baseline_chat"]["chat_id"], "Background paired phase reused a Chat")
            result = verify_context(fixture["baseline_context"]["requests"], contexts["requests"][4:],
                                    physical["requests"], added, state["users"][0]["id"],
                                    state["service_fixture"]["payer_id"], [fixture["baseline_chat"], chat])
            fixture.update(stage="events_verified", result=result, service_chat=chat, after=current, added_rows=added)
        else:
            groups = grouped_context(contexts["requests"])
            require(all(groups[task].get("auth_failure") == {"scope": "custom_auth", "status_code": 403,
                    "code": "invalid_signed_budget_provenance"} for task in TASKS),
                    "Background baseline did not reach three intended custom-auth 403 guards")
            fixture.update(stage="baseline_verified", baseline_context=contexts, baseline_chat=chat, baseline_native=current)
    elif phase == "restore":
        fixture = state.get("background_fixture")
        require(isinstance(fixture, dict), "Background original native config is unavailable for restoration")
        restore_controls(webui, state)
        if fixture["stage"] == "events_verified":
            fixture["stage"] = "qualified_automatic_background"
    elif phase != "snapshot":
        raise ProofError("Unknown bounded background phase")
    write_private(args.private_state, state)
    fixture = state["background_fixture"]
    result = {"phase": phase, "stage": fixture["stage"], "task_config_restored": fixture["task_config_restored"],
              "provider_controls_restored": fixture["provider_controls_restored"],
              "provider_control_observations": {"original": fixture["original_provider_control"]},
              "actor_id": state["users"][0]["id"], "payer_id": state["service_fixture"]["payer_id"],
              "pipe_sha256": fixture["pipe_sha256"],
              "task_config_observations": {name: task_config_evidence(fixture[name])
                  for name in ("original_task_config", "baseline_config", "service_config") if name in fixture}}
    for field in ("before", "baseline_native", "after", "added_rows", "baseline_chat", "service_chat", "result"):
        if field in fixture:
            result[field] = fixture[field]
    if phase == "snapshot":
        result["observed_native"] = snapshot(webui, state)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("baseline-prepare", "baseline-observe", "service-prepare", "verify", "restore", "snapshot"), required=True)
    for name in ("private-state", "receipt", "context-receipt", "provider-receipt"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("chat-id", "answer-id"):
        parser.add_argument("--" + name)
    args = parser.parse_args()
    receipt = {"schema": 1, "proof": "goal584-native-automatic-background", "phase": args.phase, "passed": False,
               "started_at_utc": datetime.now(timezone.utc).isoformat(),
               "not_qualified": ["multi_model", "arena", "automation", "shared_chat", "temporary_chat",
                                 "standalone_auxiliary_endpoints", "embeddings", "production", "paid_provider"]}
    state, output_valid = {}, False
    try:
        require(args.private_state.resolve() == STATE.resolve(), "Background proof requires fixed disposable private state")
        paths = [args.private_state, args.receipt, args.context_receipt, args.provider_receipt, OPERATOR_STATE, capture.CAPTURE]
        require(len({path.resolve() for path in paths}) == len(paths), "Background private evidence paths must be distinct")
        output_valid = True
        state = read_private(args.private_state)
        require(state.get("stage") == "setup_complete" and len(state.get("users", [])) == 2,
                "Background proof requires the completed isolated native fixture")
        receipt.update(run_phase(WebUI(), state, args), passed=True)
    except ProofError as error:
        receipt["failure"] = str(error)
    except BudgetAdminError as error:
        receipt["failure"] = "Background native client failed: " + error.code
    except Exception as error:
        receipt["failure"] = "Background proof failed: " + type(error).__name__
    fixture = state.get("background_fixture", {})
    if output_valid and fixture:
        write_private(args.private_state, state)
    receipt.update(stage=fixture.get("stage", "not_prepared"), task_config_restored=fixture.get("task_config_restored", False),
                   provider_controls_restored=fixture.get("provider_controls_restored", False),
                   finished_at_utc=datetime.now(timezone.utc).isoformat())
    secrets = secret_values(state) + [os.environ.get("OWUI_BUDGET_GATEWAY_SECRET", "")]
    if state:
        secrets.append(read_private(OPERATOR_STATE).get("operator_token", ""))
    if output_valid:
        receipt["retained_observations"] = {}
        for label, path, observe_evidence in (("context", args.context_receipt, capture_state),
                                              ("provider", args.provider_receipt, provider)):
            try:
                observed = no_secrets(observe_evidence(), secrets)
                write_private(path, observed)
                receipt["retained_observations"][label] = {"saved": True, "records": len(observed["requests"])}
            except Exception:
                receipt["retained_observations"][label] = {"saved": False}
    try:
        no_secrets(receipt, secrets)
    except ProofError:
        receipt = {"schema": 1, "proof": "goal584-native-automatic-background", "passed": False,
                   "failure": "Credential-bearing background receipt suppressed"}
    if output_valid:
        write_private(args.receipt, receipt)
    print(json.dumps(receipt, indent=2, allow_nan=False))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
