"""Reconcile the independent new-hire phase; retain the prior11-call proof intact."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from verify_admin_calls import (MODELS, SCOPE_FIELDS, compare_provider, require, source_contract,
                                text, tool_schemas, uuid, verify_accounting_totals)


def verify(browser, provider, context, native):
    require(browser.get("passed") is True and native.get("passed") is True and provider.get("synthetic") is True,
            "Bootstrap browser/native/synthetic proof did not pass")
    admin, employee = browser["admin_id"], browser["employee_id"]
    uuid(admin)
    uuid(employee)
    require(admin != employee and browser["model_id"] == "goal584-budget-admin", "Bootstrap actor/model identity differs")
    require(native.get("existing_employee_native_state_unchanged") is True
            and browser.get("existing_employee_native_state_unchanged") is True
            and browser.get("canceled_native_identity_absent") is True, "Bootstrap changed existing identities or canceled creation")
    require(native.get("employee_function_valves_get_status") in (401, 403), "New employee could access administrator Function Valves")
    snapshots = browser["native_snapshots"]
    require(snapshots["before"] == snapshots["template"] == snapshots["canceled"]
            and snapshots["before"]["kind"] == "absent" and snapshots["before"]["user_id"] == employee,
            "Template save or cancellation created native state")
    require(native["bootstrap"] == snapshots["final"] and native["bootstrap"]["kind"] == "ready",
            "Final browser/native bootstrap projections differ")
    template = browser["template_proposal"]
    require(template["schema"] == 1 and template["type"] == "employee_budget_template"
            and {key: value for key, value in template.items() if key not in ("schema", "type", "expected_revision")}
            == native["default_template"] == {"budget_usd": "0.8", "budget_duration": "1mo",
                                             "shares": {MODELS[0]: "100", MODELS[1]: "0"}},
            "Saved native default template differs from the browser proposal")
    initialization = browser["initialization_proposal"]
    require(initialization["schema"] == 1 and initialization["type"] == "employee_budget_initialize"
            and len(initialization["changes"]) == 1 and initialization["changes"][0]["user_id"] == employee
            and initialization["changes"][0]["budget_usd"] == "0.8"
            and initialization["changes"][0]["shares"] == template["shares"], "Initialization proposal differs")
    baseline = browser["baseline_positive_request_ids"]
    all_rows = native["attributed_spend_logs"]
    require(len(set(baseline)) == len(baseline) and set(baseline) == set(native["baseline_positive_request_ids"])
            and set(baseline) <= {row["request_id"] for row in all_rows}, "Historical native rows were lost or reclassified")
    rows = [row for row in all_rows if row["request_id"] not in baseline]
    physical = {row["id"]: row for row in provider["requests"]}
    require(len(physical) == len(provider["requests"]) == len(rows) == 9
            and {row["request_id"] for row in rows} == set(physical), "Expected exactly9 new provider/native rows")
    require(len({row["request_id"] for row in all_rows}) == len(all_rows), "Duplicate native request ID")
    by_nonce = {row["owui_budget"]["call_id"]: row for row in rows}
    require(len(by_nonce) == len(rows), "Native signed nonce duplicated")
    skill, intent, results = source_contract()
    labels = ("opened", "template_saved", "canceled", "initialized")
    turns = [browser[label] for label in labels]
    turn_texts = [turn["stored_parent_text"] for turn in turns]
    require(turn_texts[0] == intent and json.loads(turn_texts[1]) == template
            and json.loads(turn_texts[2]) == json.loads(turn_texts[3]) == initialization,
            "Stored original bootstrap proposals changed")
    require(len({turn["chat_id"] for turn in turns}) == 1
            and len({turn["parent_user_id"] for turn in turns}) == 4, "Bootstrap lost single-chat distinct source parents")
    expected = {}
    for index, turn in enumerate(turns):
        for field in ("chat_id", "assistant_id", "parent_user_id"):
            uuid(turn[field])
        require(turn["admin_id"] == turn["parent_author_id"] == admin
                and turn["model_id"] == browser["model_id"] and turn["exact_submitted_and_stored_strings"] is True
                and turn["terminal_persisted"] is True and turn["sandbox_same_origin"] is False,
                "Bootstrap parent/model/actor evidence differs")
        expected[turn["assistant_id"]] = (admin, MODELS[0], turn["chat_id"], 2, index)
    calls = browser["calls"]
    require([(call["user_id"], call["model"], call["outcome"]) for call in calls]
            == [(employee, MODELS[0], "success"), (employee, MODELS[1], "budget_blocked")],
            "New-hire allowed/zero-cap scenario differs")
    for call in calls:
        uuid(call["message_id"])
        uuid(call["chat_id"])
        require(call["message_id"] not in expected and call["terminal_persisted"] is True,
                "Duplicate or nonterminal bootstrap employee attempt")
        expected[call["message_id"]] = (employee, call["model"], call["chat_id"], int(call["outcome"] == "success"), None)
    observations = context["requests"]
    require(len(observations) == 10 and len({row["verified_cost_scope"]["call_id"] for row in observations}) == 10,
            "Expected10 distinct signed attempts for4 admin turns and2 employee attempts")
    grouped = {}
    for observation in observations:
        scope = observation["verified_cost_scope"]
        require(set(scope) == SCOPE_FIELDS and scope["schema"] == 1 and scope["category"] == "personal",
                "Bootstrap signed scope contract differs")
        for field in ("user_id", "chat_id", "answer_id", "root_chat_id", "root_answer_id", "call_id"):
            uuid(scope[field])
        require(scope["answer_id"] in expected, "Unexpected inference outside the actual bootstrap browser attempts")
        owner, model, chat_id, count, _ = expected[scope["answer_id"]]
        require(scope["user_id"] == observation["user_id"] == owner and scope["model"] == model
                and scope["chat_id"] == scope["root_chat_id"] == chat_id
                and scope["answer_id"] == scope["root_answer_id"] and observation.get("task") == "",
                "Bootstrap signed attribution differs from actual browser identity/model")
        row = by_nonce.get(scope["call_id"])
        require((row is not None) == bool(count), "Denied/completed new-hire attempt acquired the wrong native outcome")
        if row is not None:
            require(row["owui_budget"] == scope and row["user_id"] == owner and row["session_id"] == chat_id
                    and row["model_group"] == model and Decimal(row["spend_usd"]) == Decimal(".20")
                    and [row[field] for field in ("prompt_tokens", "completion_tokens", "total_tokens")] == [10, 5, 15],
                    "Bootstrap ledger differs from signed usage/cost")
        compare_provider(observation, physical[row["request_id"]] if row else None, model)
        grouped.setdefault(scope["answer_id"], []).append(observation)
    statuses = [results["opened"], results["applied"], results["canceled"], results["applied"]]
    for answer_id, (owner, _, _, _, index) in expected.items():
        group = grouped.get(answer_id, [])
        require(len(group) == (2 if owner == admin else 1), "Bootstrap logical attempt has unexpected model rounds")
        if owner != admin:
            messages = group[0]["body"]["messages"]
            require(len(messages) == 1 and messages[0]["role"] == "user" and text(messages[0]["content"]) == "Hi",
                    "New-hire inference input differs from the fresh visible chat")
            continue
        for round_index, observation in enumerate(group):
            body = observation["body"]
            names, messages = tool_schemas(body), body["messages"]
            require(any(message.get("role") in ("system", "developer") and skill.strip() in text(message.get("content", ""))
                        for message in messages), "Full bootstrap Skill is missing or demoted")
            require([text(message["content"]) for message in messages if message.get("role") == "user"]
                    == turn_texts[:index + 1], "Original bootstrap JSON/history was rewritten, omitted or reordered")
            current = max(i for i, message in enumerate(messages) if message.get("role") == "user")
            tool_calls = [call for message in messages[current + 1:] for call in message.get("tool_calls", [])]
            outputs = [message for message in messages[current + 1:] if message.get("role") == "tool"]
            require(len(tool_calls) == len(outputs) == round_index
                    and [json.loads(text(message["content"])) for message in messages if message.get("role") == "tool"]
                    == statuses[:index + round_index], "Bootstrap Tool results/history differ from native owner statuses")
            if round_index:
                call, output = tool_calls[0], outputs[0]
                suffix = "open_budget_form" if index == 0 else "apply_budget_form"
                require(call["type"] == "function" and output["tool_call_id"] == call["id"]
                        and call["function"]["name"] == names[suffix]
                        and json.loads(call["function"]["arguments"]) == ({"view_json": "{}"} if index == 0 else {}),
                        "Bootstrap Tool arguments acquired model-supplied business values")
    final = native["bootstrap"]
    users, keys = final["users"], final["keys"]
    require(len(users) == 1 and users[0]["user_id"] == employee and len(keys) == 2
            and {(key["user_id"], key["model"]) for key in keys} == {(employee, model) for model in MODELS},
            "New-hire final native accounting is incomplete")
    require(Decimal(users[0]["spend_usd"]) == Decimal(".20") and Decimal(users[0]["max_budget_usd"]) == Decimal(".8")
            and users[0]["budget_duration"] == "1mo" and users[0]["budget_reset_at"], "New-hire personal accounting differs")
    for key in keys:
        require(Decimal(key["spend_usd"]) == (Decimal(".20") if key["model"] == MODELS[0] else 0)
                and Decimal(key["max_budget_usd"]) == (Decimal(".8") if key["model"] == MODELS[0] else 0)
                and key["budget_duration"] == "1mo" and key["budget_reset_at"] == users[0]["budget_reset_at"],
                "New-hire model cap/spend/calendar differs")
    require(Counter(row["user_id"] for row in rows) == {admin: 8, employee: 1}, "Bootstrap billed an unexpected payer")
    identities = {row["user_id"] for row in native["users"]} | {admin, employee}
    require(len(identities) == 4, "Bootstrap lacks the prior two distinct employee identities")
    verify_accounting_totals(native["users"] + native["admin_accounting"]["users"] + final["users"],
        native["keys"] + native["admin_accounting"]["keys"] + final["keys"], all_rows, identities)
    return {"passed": True, "physical_calls": 9, "signed_attempts": 10, "admin_physical_calls": 8,
            "new_employee_successes": 1, "new_employee_zero_cap_denials": 1, "phase_cost_usd": "1.80",
            "exact_saved_json_history": True, "full_skill_and_empty_apply_arguments": True,
            "canceled_identity_absent": True, "existing_employee_state_unchanged": True,
            "coverage": "Independent synthetic bootstrap phase; concurrent creation and calendar rollover are unqualified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("browser", "provider", "context", "native", "receipt"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    paths = {name: getattr(args, name) for name in ("browser", "provider", "context", "native")}
    result = verify(**{name: json.loads(path.read_text(encoding="utf-8")) for name, path in paths.items()})
    result["input_sha256"] = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}
    rendered = json.dumps(result, indent=2) + "\n"
    args.receipt.write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
