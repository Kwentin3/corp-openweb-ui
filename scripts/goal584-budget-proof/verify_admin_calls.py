"""Reconcile the bounded native admin browser phase with actual provider/log data."""
import argparse
import ast
from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
from uuid import UUID

from capture_webui_auth import FIELDS

MODELS = ("goal584-a", "goal584-b")
PHYSICAL = {"goal584-a": "goal584-fake-a", "goal584-b": "goal584-fake-b"}
SCOPE_FIELDS = {"schema", "user_id", "chat_id", "answer_id", "root_chat_id", "root_answer_id", "model", "call_id", "category"}


def require(value, message):
    if not value:
        raise AssertionError(message)


def uuid(value):
    require(isinstance(value, str) and str(UUID(value)) == value, "Noncanonical observed UUID")


def text(value):
    if isinstance(value, str):
        return value
    require(isinstance(value, list) and all(isinstance(part, dict) and set(part) == {"type", "text"}
            and part["type"] == "text" and isinstance(part["text"], str) for part in value),
            "Unexpected nontext model content")
    return "".join(part["text"] for part in value)


def literal(path, name):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return ast.literal_eval(next(node.value for node in tree.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)))


def source_contract():
    here = Path(__file__).resolve().parent
    skill = literal(here / "provision_admin.py", "SKILL")
    intent = literal(here / "prove_admin_browser.py", "INTENT")
    owner = here.parents[1] / "deploy/openwebui-budgets/admin_tools.py"
    strings = {node.value for node in ast.walk(ast.parse(owner.read_text(encoding="utf-8")))
               if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    def message(prefix):
        matches = [s for s in strings if s.startswith(prefix)]
        require(len(matches) == 1, "Ambiguous native Tool result source")
        return matches[0]
    results = {"opened": {"status": "success", "message": message("Budget form opened.")},
               "canceled": {"status": "cancelled", "message": message("Изменения отменены.")},
               "applied": {"status": "success", "message": message("Изменения применены.")}}
    results["recovered"] = results["applied"]
    return skill, intent, results


def safe_body(body):
    encoded = json.dumps(body, ensure_ascii=False).lower()
    require(not any(marker in encoded for marker in ("<!doctype", "<html", "<script", "<main", "data-budget-editor",
        "data-budget-cost-details", "ledger_read_key", "ledger_admin_key", "operator_key", "owui_budget_provenance")),
        "HTML or server-only data reached model context")
    require(not re.search(r"eyj[a-z0-9_-]+\.[a-z0-9_-]+\.[a-z0-9_-]+|(?:sk-|gw-)[a-z0-9_-]{16,}", encoded),
            "Credential-shaped data reached model context")


def tool_schemas(body):
    tools = body.get("tools")
    require(isinstance(tools, list) and len(tools) == 2, "Both native admin Tool schemas are required")
    resolved = {}
    for tool in tools:
        require(isinstance(tool, dict) and tool.get("type") == "function", "Nonfunction admin Tool schema")
        function = tool["function"]
        suffixes = [suffix for suffix in ("open_budget_form", "apply_budget_form") if function["name"].endswith(suffix)]
        require(len(suffixes) == 1 and suffixes[0] not in resolved, "Ambiguous native admin Tool names")
        suffix = suffixes[0]
        parameters = function.get("parameters") or {}
        properties = parameters.get("properties") or {}
        require(parameters.get("type") == "object" and isinstance(function.get("description"), str)
                and bool(function["description"]), "Native Tool schema/description is missing")
        require(properties == {} if suffix == "apply_budget_form" else
                set(properties) == {"view_json"} and properties["view_json"].get("type") == "string",
                "Native admin Tool acquired business arguments or lost its view schema")
        require(not parameters.get("required"), "Native admin Tool unexpectedly requires model arguments")
        resolved[suffix] = function["name"]
    return resolved


def compare_provider(capture, provider, model):
    before, after = capture["body"], capture["body_after_auth"]
    require(before == after and capture.get("attestation_present_before") is True
            and capture.get("provenance_removed_after") is True, "Auth changed model context or failed to remove attestation")
    safe_body(before)
    if provider is None:
        return
    physical = provider["body"]
    safe_body(physical)
    patch = capture.get("native_stream_usage_patch")
    require(isinstance(patch, dict) and set(patch) <= {"stream_options", "_litellm_strip_stream_usage"}
            and ("_litellm_strip_stream_usage" not in patch or type(patch["_litellm_strip_stream_usage"]) is bool)
            and ("stream_options" not in patch or patch["stream_options"] == {"include_usage": True}),
            "Unsupported native stream-usage patch")
    expected = {**before, **patch}
    for field in FIELDS:
        if field != "model":
            require(physical.get(field) == expected.get(field), "Provider semantics changed: " + field)
    require(before.get("model") == model and physical.get("model") == PHYSICAL[model]
            and physical.get("stream") is True, "Actual model mapping/stream differs")
    require(not any(field in physical for field in ("metadata", "litellm_metadata", "owui_budget_provenance")),
            "Log-only metadata reached provider")
    require(provider["usage"] == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "Actual provider usage differs")


def accounting_totals_ready(users, keys, rows, identities, *, history_complete=True):
    """Compare one complete native history; only a valid counter deficit can wait.

    While the expected journal rows are still arriving, validate all identities,
    shapes and amounts without treating an ahead-of-journal counter as surplus.
    """
    identities = set(identities)
    require(isinstance(users, list) and isinstance(keys, list) and isinstance(rows, list)
            and bool(identities) and all(isinstance(entry, dict) for entry in [*users, *keys, *rows]),
            "Native accounting observations have an invalid shape")
    require(len(users) == len(identities) and {user["user_id"] for user in users} == identities,
            "Native payer accounting is incomplete")
    require(len(keys) == len(identities) * len(MODELS)
            and {(key["user_id"], key["model"]) for key in keys}
            == {(uid, model) for uid in identities for model in MODELS},
            "Native payer/model key accounting is incomplete")
    require(all(isinstance(row.get("request_id"), str) and 0 < len(row["request_id"]) <= 512
                and row.get("user_id") in identities and row.get("model_group") in MODELS for row in rows)
            and len({row["request_id"] for row in rows}) == len(rows), "Native accounting history identity is invalid or duplicated")
    def spend(value):
        require(type(value) in (str, int, float, Decimal), "Native accounting amount is invalid")
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise AssertionError("Native accounting amount is invalid") from None
        require(result.is_finite() and result >= 0, "Native accounting amount is invalid")
        return result
    actual = [spend(entry.get("spend_usd")) for entry in [*users, *keys]]
    costs = [spend(row.get("spend_usd")) for row in rows]
    require(all(cost > 0 for cost in costs), "Native accounting history contains a nonpositive row")
    if not history_complete:
        return False
    ready = True
    for entry, observed in zip([*users, *keys], actual):
        expected = sum((cost for row, cost in zip(rows, costs) if row["user_id"] == entry["user_id"]
                        and ("model" not in entry or row["model_group"] == entry["model"])), Decimal(0))
        require(observed == 0 if expected == 0 else observed - expected <= Decimal(".000000001"),
                "Native payer/key spend exceeds the same persisted ledger")
        if expected - observed > Decimal(".000000001"):
            ready = False
    return ready


def verify_accounting_totals(users, keys, rows, identities):
    """Strict final verification; a pending native counter is not accepted."""
    require(accounting_totals_ready(users, keys, rows, identities),
            "Native payer/key spend differs from the same persisted ledger")


def verify(browser, provider, context, native):
    require(browser.get("passed") is True and native.get("passed") is True and provider.get("synthetic") is True,
            "Browser/native/synthetic proof did not pass")
    admin, staff = browser["admin_id"], browser["staff_ids"]
    for uid in [admin, *staff]:
        uuid(uid)
    require(len(staff) == 2 and len({admin, *staff}) == 3 and browser["model_id"] == "goal584-budget-admin",
            "Native admin/employee identities differ")
    skill, intent, results = source_contract()
    labels = ("opened", "canceled", "applied", "recovered")
    turns = [browser[label] for label in labels]
    turn_texts = [turn["stored_parent_text"] for turn in turns]
    require(turn_texts[0] == intent and turn_texts[1] == turn_texts[2]
            and json.loads(turn_texts[1]) == browser["original_proposal"]
            and json.loads(turn_texts[3]) == browser["recovery_proposal"], "Stored original/recovery proposal changed")
    expected = {}
    require(len({t["chat_id"] for t in turns}) == 1 and len({t["parent_user_id"] for t in turns}) == 4,
            "Admin turns lost their single chat/distinct source parents")
    for index, turn in enumerate(turns):
        for field in ("chat_id", "assistant_id", "parent_user_id"):
            uuid(turn[field])
        require(turn["admin_id"] == turn["parent_author_id"] == admin
                and turn["model_id"] == browser["model_id"] and turn["exact_submitted_and_stored_strings"] is True
                and turn["terminal_persisted"] is True and turn["sandbox_same_origin"] is False,
                "Browser parent/model/actor evidence differs")
        expected[turn["assistant_id"]] = (admin, MODELS[0], turn["chat_id"], 2, index)
    calls = browser["calls"]
    wanted = [(staff[0], MODELS[1], "budget_blocked"), (staff[0], MODELS[0], "success"),
              (staff[1], MODELS[0], "budget_blocked"), (staff[1], MODELS[1], "success"),
              (staff[1], MODELS[1], "budget_blocked"), (staff[1], MODELS[1], "success")]
    require([(c["user_id"], c["model"], c["outcome"]) for c in calls] == wanted
            and len({c["chat_id"] for c in calls}) == 6, "Employee quota/recovery browser scenario differs")
    for call in calls:
        uuid(call["message_id"])
        uuid(call["chat_id"])
        require(call["message_id"] not in expected and call["terminal_persisted"] is True, "Duplicate/nonterminal browser attempt")
        expected[call["message_id"]] = (call["user_id"], call["model"], call["chat_id"], int(call["outcome"] == "success"), None)
    require(len(expected) == 10, "Admin/employee assistant IDs collided")
    requests = provider["requests"]
    physical = {r["id"]: r for r in requests}
    require(len(physical) == len(requests) == 11, "Expected exactly eleven physical calls after reset")
    rows = native["attributed_spend_logs"]
    ledger = {r["request_id"]: r for r in rows}
    baseline = browser["baseline_positive_request_ids"]
    require(len(ledger) == len(rows) and len(set(baseline)) == len(baseline)
            and set(baseline) <= set(ledger) and not set(baseline) & set(physical)
            and set(ledger) - set(baseline) == set(physical), "Phase native/provider delta has missing or extra positive rows")
    by_nonce = {r["owui_budget"]["call_id"]: r for r in rows if r["request_id"] in physical}
    require(len(by_nonce) == 11, "Physical rows reused a signed nonce")
    observations = context["requests"]
    require(len(observations) == 14 and all(r.get("verified_cost_scope") for r in observations),
            "Expected fourteen signed attempts and no raw/unbound extras")
    grouped, nonces = {}, set()
    for observation in observations:
        scope = observation["verified_cost_scope"]
        require(set(scope) == SCOPE_FIELDS and type(scope["schema"]) is int and scope["schema"] == 1
                and scope["category"] == "personal", "Shared validated scope shape/category differs")
        for field in ("user_id", "chat_id", "answer_id", "root_chat_id", "root_answer_id", "call_id"):
            uuid(scope[field])
        require(scope["call_id"] not in nonces, "Signed attempt nonce repeated")
        nonces.add(scope["call_id"])
        owner, model, chat_id, count, _ = expected[scope["answer_id"]]
        require(scope["user_id"] == observation["user_id"] == owner and scope["model"] == model
                and scope["chat_id"] == scope["root_chat_id"] == chat_id
                and scope["answer_id"] == scope["root_answer_id"] and observation.get("task") == ""
                and observation["body"].get("model") == model, "Signed scope differs from actual browser actor/chat/root/model")
        row = by_nonce.get(scope["call_id"])
        require((row is not None) == bool(count), "Denied/completed signed attempt acquired the wrong ledger outcome")
        if not count:
            require(scope["call_id"] not in {r["owui_budget"]["call_id"] for r in rows},
                    "Denied nonce overlaps existing positive ledger history")
        provider_row = None
        if row is not None:
            require(row["owui_budget"] == scope and row["user_id"] == owner and row["session_id"] == chat_id
                    and row["model_group"] == model and Decimal(row["spend_usd"]) == Decimal(".20")
                    and [row[f] for f in ("prompt_tokens", "completion_tokens", "total_tokens")] == [10, 5, 15],
                    "Native row differs from signed attribution/cost/usage")
            provider_row = physical[row["request_id"]]
        compare_provider(observation, provider_row, model)
        grouped.setdefault(scope["answer_id"], []).append(observation)
    for answer_id, (owner, model, chat_id, count, turn_index) in expected.items():
        group = grouped.get(answer_id, [])
        require(len(group) == (2 if owner == admin else 1), "Logical browser attempt has unexpected model rounds")
        if owner != admin:
            messages = group[0]["body"].get("messages")
            require(isinstance(messages, list) and len(messages) == 1 and messages[0].get("role") == "user"
                    and text(messages[0].get("content")) == "Hi", "Employee provider context differs from actual fresh Hi")
            continue
        for round_index, observation in enumerate(group):
            body = observation["body"]
            names = tool_schemas(body)
            messages = body["messages"]
            require(any(m.get("role") in ("system", "developer") and skill.strip() in text(m.get("content", ""))
                        for m in messages), "Configured full Skill instructions are missing or demoted")
            user_texts = [text(m.get("content")) for m in messages if m.get("role") == "user"]
            require(user_texts == turn_texts[:turn_index + 1], "Original stored JSON/admin history was rewritten, omitted or reordered")
            current_user = max(i for i, m in enumerate(messages) if m.get("role") == "user")
            current_calls = [call for m in messages[current_user + 1:] for call in m.get("tool_calls", [])]
            current_results = [m for m in messages[current_user + 1:] if m.get("role") == "tool"]
            require(len(current_calls) == len(current_results) == round_index, "Admin native Tool round boundary differs")
            all_results = [json.loads(text(m.get("content"))) for m in messages if m.get("role") == "tool"]
            require(all_results == [results[label] for label in labels[:turn_index + round_index]],
                    "Actual Tool result/history differs from the short owner status/context")
            if round_index:
                call, result = current_calls[0], current_results[0]
                suffix = "open_budget_form" if turn_index == 0 else "apply_budget_form"
                require(call.get("type") == "function" and result.get("tool_call_id") == call.get("id")
                        and call["function"]["name"] == names[suffix]
                        and json.loads(call["function"]["arguments"]) == ({"view_json": "{}"} if turn_index == 0 else {}),
                        "Native Tool name/correlation/arguments rewrote business authority")
    all_users = native["users"] + native["admin_accounting"]["users"]
    all_keys = native["keys"] + native["admin_accounting"]["keys"]
    verify_accounting_totals(all_users, all_keys, rows, {admin, *staff})
    admin_rows = [r for r in rows if r["user_id"] == admin]
    require(len(admin_rows) == 8 and all(r["model_group"] == MODELS[0] and r["request_id"] in physical for r in admin_rows),
            "Admin inference was billed to a staff identity, wrong model or extra history")
    return {"passed": True, "admin_logical_turns": 4, "admin_physical_calls": 8, "staff_successes": 3,
            "staff_budget_denials": 3, "signed_attempts": 14, "physical_calls": 11, "extra_provider_calls": 0,
            "phase_cost_usd": "2.20", "admin_cost_usd": "1.60", "staff_cost_usd": "0.60",
            "exact_stored_json_to_provider": True, "native_apply_arguments_empty": True,
            "short_owner_tool_results": True, "html_excluded": True, "full_skill_in_system_context": True,
            "skill_sha256": hashlib.sha256(skill.encode()).hexdigest(),
            "coverage": "This synthetic phase and native positive spend projection; zero/failure row content is not qualified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("browser", "provider", "context", "native", "receipt"):
        parser.add_argument("--" + argument, type=Path, required=True)
    args = parser.parse_args()
    paths = {name: getattr(args, name) for name in ("browser", "provider", "context", "native")}
    result = verify(**{name: json.loads(path.read_text(encoding="utf-8")) for name, path in paths.items()})
    result["input_sha256"] = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}
    rendered = json.dumps(result, indent=2) + "\n"
    args.receipt.write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
