"""Budget proposal rules; native LiteLLM remains the cap/spend state owner.

New meaning: validate explicit percentages and derive proposed scalar caps.
No tariffs, spend accounting, provider calls, database or credential storage.
The native Tool owns authorization and confirmation; this module never accepts
an LLM's rewritten business arguments or treats a revision as authorization.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, Inexact, localcontext
import hashlib
from html import escape
import json
import math
import re
from uuid import UUID

from employee_budget_admin_contract import BudgetAdminError, EmployeeBudget


def require(condition, code):
    if not condition:
        raise BudgetAdminError(code)


def number(value):
    """Plain exact decimal input; reject bool/numeric JSON, exponents and NaN."""
    require(type(value) is str and len(value) <= 32
            and re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value) is not None, "invalid_amount")
    result = Decimal(value)
    require(result.is_finite() and result >= 0, "invalid_amount")
    return result


def native_cap(value):
    native = float(value)
    # Native cap fields are Float. Do not silently discard a user's precision
    # or accept a nonzero readback for a requested hard zero.
    require(math.isfinite(native) and Decimal(str(native)) == value,
            "unsupported_amount_precision")
    return Decimal(str(native))


def monthly(state):
    periods = {"1mo", "30d", "monthly"}
    require(state.budget_duration in periods and state.budget_reset_at is not None
            and all(model.budget_duration in periods and model.budget_reset_at is not None
                    for model in state.models), "unsupported_budget_period")


def money(value):
    if value is None:
        return None
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_field")
        result[key] = value
    return result


def _json(text):
    require(type(text) is str and 0 < len(text.encode("utf-8")) <= 64 * 1024, "invalid_json")
    try:
        return json.loads(text, object_pairs_hook=_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(BudgetAdminError("invalid_json")))
    except (ValueError, TypeError, RecursionError):
        raise BudgetAdminError("invalid_json") from None


def _shares(value):
    require(isinstance(value, dict) and 1 <= len(value) <= 100
            and all(type(model) is str and 0 < len(model) <= 256
                    and all(ord(c) >= 32 for c in model) for model in value), "invalid_models")
    parsed = tuple(sorted((model, number(amount)) for model, amount in value.items()))
    with localcontext() as context:
        context.prec = 128
        context.traps[Inexact] = True
        require(all(share <= 100 for _, share in parsed)
                and sum((share for _, share in parsed), Decimal(0)) == 100, "shares_must_total_100")
    return parsed


def allocation(budget, shares):
    with localcontext() as context:
        context.prec = 128
        context.traps[Inexact] = True
        caps = tuple((model, budget * share / 100) for model, share in shares)
        require(sum((cap for _, cap in caps), Decimal(0)) == budget
                and all(0 <= cap <= budget for _, cap in caps), "invalid_allocation")
    native_cap(budget)
    for _, cap in caps:
        native_cap(cap)
    return caps


@dataclass(frozen=True)
class BudgetChange:
    user_id: str
    expected_revision: str
    budget_usd: Decimal
    shares: tuple[tuple[str, Decimal], ...]


@dataclass(frozen=True)
class PreparedChange:
    user_id: str
    before: EmployeeBudget
    budget_usd: Decimal
    new_caps: tuple[tuple[str, Decimal], ...]
    expected_revision: str


def parse_plan(text):
    value = _json(text)
    require(isinstance(value, dict) and set(value) == {"schema", "type", "changes"}
            and type(value["schema"]) is int and value["schema"] == 1
            and value["type"] == "employee_budget_plan", "invalid_plan")
    changes = value["changes"]
    require(isinstance(changes, list) and 1 <= len(changes) <= 100, "invalid_plan")
    result, ids = [], set()
    for item in changes:
        require(isinstance(item, dict) and set(item) == {
            "user_id", "expected_revision", "budget_usd", "shares"}, "invalid_plan")
        user_id = item["user_id"]
        try:
            valid = type(user_id) is str and str(UUID(user_id)) == user_id
        except (ValueError, TypeError, AttributeError):
            valid = False
        require(valid and user_id not in ids, "invalid_employee")
        ids.add(user_id)
        rev = item["expected_revision"]
        require(type(rev) is str and re.fullmatch(r"[0-9a-f]{64}", rev) is not None, "invalid_revision")
        parsed = _shares(item["shares"])
        result.append(BudgetChange(user_id, rev, number(item["budget_usd"]), parsed))
    return tuple(result)


def revision(state):
    # Spend changes during ordinary inference and is deliberately not a config
    # revision. Key identity/access/period/caps are bound to actual owner output.
    value = {"schema": 1, "user_id": state.user_id, "cap": money(state.max_budget),
             "duration": state.budget_duration, "reset_at": state.budget_reset_at,
             "models": [{"model": model.model, "key": model.key_hash, "alias": model.key_alias,
                         "cap": money(model.max_budget), "duration": model.budget_duration,
                         "reset_at": model.budget_reset_at, "blocked": model.blocked}
                        for model in sorted(state.models, key=lambda item: item.model)]}
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                    separators=(",", ":")).encode()).hexdigest()


def prepare_change(change, state):
    require(change.user_id == state.user_id, "invalid_employee")
    monthly(state)
    require(change.expected_revision == revision(state), "stale_snapshot")
    models = [model.model for model in state.models]
    require(len(models) == len(set(models)) and set(models) == {model for model, _ in change.shares},
            "invalid_models")
    caps = allocation(change.budget_usd, change.shares)
    return PreparedChange(state.user_id, state, change.budget_usd, caps, change.expected_revision)


def submission_kind(text):
    value = _json(text)
    require(isinstance(value, dict) and value.get("type") in (
        "employee_budget_plan", "employee_budget_template", "employee_budget_initialize"), "invalid_plan")
    return value["type"]


def parse_initialization(text):
    value = _json(text)
    require(isinstance(value, dict) and value.get("type") == "employee_budget_initialize", "invalid_plan")
    # Reuse the exact bounded employee/change grammar, including duplicate keys.
    value["type"] = "employee_budget_plan"
    return parse_plan(json.dumps(value, ensure_ascii=True, separators=(",", ":")))


def template_value(value, models):
    if value is None:
        return None
    require(isinstance(value, dict) and set(value) == {"budget_usd", "shares", "budget_duration"}
            and value["budget_duration"] == "1mo", "invalid_template")
    budget, shares = number(value["budget_usd"]), _shares(value["shares"])
    require({model for model, _ in shares} == set(models), "template_models_changed")
    allocation(budget, shares)
    return {"budget_usd": money(budget), "shares": {model: money(share) for model, share in shares},
            "budget_duration": "1mo"}


def template_revision(value, models):
    public = {"schema": 1, "template": template_value(value, models), "models": sorted(models)}
    return hashlib.sha256(json.dumps(public, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def parse_template_plan(text, current, models):
    value = _json(text)
    require(isinstance(value, dict) and set(value) == {
        "schema", "type", "expected_revision", "budget_usd", "shares", "budget_duration"}
        and type(value["schema"]) is int and value["schema"] == 1
        and value["type"] == "employee_budget_template", "invalid_template")
    require(value["expected_revision"] == template_revision(current, models), "stale_template")
    return template_value({key: value[key] for key in ("budget_usd", "shares", "budget_duration")}, models)


def template_public(value, labels):
    actual = template_value(value, labels)
    return {"revision": template_revision(actual, labels),
            "budget_usd": actual["budget_usd"] if actual else None, "budget_duration": "1mo",
            "shares": [{"id": model, "label": labels[model],
                        "share_percent": actual["shares"][model] if actual else ""} for model in sorted(labels)]}


def absence_revision(user_id, models, template_rev):
    value = {"schema": 1, "user_id": user_id, "models": sorted(models),
             "state": "absent", "template_revision": template_rev}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def public_pending(identity, inspection, template, labels):
    value = template_value(template, labels)
    models = identity["models"]
    matches = value is not None and set(value["shares"]) == set(models)
    return {"user_id": identity["user_id"], "name": identity["name"], "email": identity["email"],
            "revision": absence_revision(identity["user_id"], models, template_revision(value, labels)),
            "state": inspection.kind, "code": inspection.code,
            "models": [{"id": model, "label": labels[model]} for model in models],
            "suggested_budget_usd": value["budget_usd"] if matches else None,
            "suggested_shares": value["shares"] if matches else None}


def prepare_initialization(change, inspection, identity, template, labels):
    require(inspection.kind == "absent" and inspection.user_id == identity["user_id"] == change.user_id,
            "employee_not_absent")
    require(change.expected_revision == absence_revision(change.user_id, identity["models"],
                template_revision(template, labels)), "stale_snapshot")
    require(set(inspection.allowed_wire_models) == set(identity["models"])
            == {model for model, _ in change.shares}, "invalid_models")
    return allocation(change.budget_usd, change.shares)


def _same_native(actual, expected):
    return actual is not None and actual == native_cap(expected)


async def apply_prepared(client, prepared):
    """Order cap-only writes conservatively, then verify native readback.

    Native APIs do not offer a multi-key transaction. On an error the Tool must
    reread and report actual state, not claim atomicity or overwrite a concurrent
    writer with an automatic rollback. No spend/reset/identity field is written.
    """
    before = prepared.before
    current = await client.read_employee(prepared.user_id, tuple(model.model for model in before.models))
    require(revision(current) == prepared.expected_revision, "stale_snapshot")
    caps = dict(prepared.new_caps)
    lowered = set()
    for model in before.models:
        cap = caps[model.model]
        if model.max_budget is None or cap < model.max_budget:
            await client.set_model_cap(model.key_hash, cap)
            lowered.add(model.model)
    raised_user = before.max_budget is not None and prepared.budget_usd > before.max_budget
    if raised_user:
        await client.set_user_cap(before.user_id, prepared.budget_usd)
    for model in before.models:
        if model.model not in lowered and model.max_budget != caps[model.model]:
            await client.set_model_cap(model.key_hash, caps[model.model])
    if not raised_user and before.max_budget != prepared.budget_usd:
        await client.set_user_cap(before.user_id, prepared.budget_usd)
    after = await client.read_employee(before.user_id, tuple(model.model for model in before.models))
    require(after.user_id == before.user_id and _same_native(after.max_budget, prepared.budget_usd)
            and after.budget_duration == before.budget_duration
            and after.budget_reset_at == before.budget_reset_at, "write_unconfirmed")
    original = {model.model: model for model in before.models}
    require(len(after.models) == len(original) and {model.model for model in after.models} == set(original),
            "write_unconfirmed")
    for model in after.models:
        old = original[model.model]
        require(_same_native(model.max_budget, caps[model.model])
                and (model.key_hash, model.key_alias, model.budget_duration, model.budget_reset_at, model.blocked)
                == (old.key_hash, old.key_alias, old.budget_duration, old.budget_reset_at, old.blocked),
                "write_unconfirmed")
    return after


def public_employee(identity, state):
    require(identity["user_id"] == state.user_id, "invalid_employee")
    monthly(state)
    shares = {}
    if (state.max_budget is not None and state.max_budget > 0
            and all(model.max_budget is not None for model in state.models)
            and abs(sum((model.max_budget for model in state.models), Decimal(0)) - state.max_budget)
                <= state.max_budget * Decimal("1e-12")):
        with localcontext() as context:
            context.prec = 128
            models = sorted(state.models, key=lambda item: item.model)
            for model in models[:-1]:
                shares[model.model] = (model.max_budget * 100 / state.max_budget).quantize(Decimal(".0001"), rounding="ROUND_DOWN")
            if models:
                shares[models[-1].model] = 100 - sum(shares.values(), Decimal(0))
    labels = identity.get("model_labels") or {}
    return {"user_id": state.user_id, "name": identity["name"], "email": identity["email"],
            "department": identity.get("department", ""), "revision": revision(state),
            "budget_usd": money(state.max_budget), "spend_usd": money(state.spend),
            "remaining_usd": money(state.max_budget - state.spend) if state.max_budget is not None else None,
            "models": [{"id": model.model, "label": labels.get(model.model, model.model),
                        "cap_usd": money(model.max_budget), "spend_usd": money(model.spend),
                        "share_percent": money(shares[model.model]) if model.model in shares else ""}
                       for model in sorted(state.models, key=lambda item: item.model)]}


def parse_view(text="{}"):
    value = _json(text)
    require(isinstance(value, dict) and set(value) <= {"remaining_below_percent", "sort_by", "group_by"},
            "invalid_view")
    require(value.get("sort_by", "name") in ("name", "remaining")
            and value.get("group_by", "none") in ("none", "department"), "invalid_view")
    threshold = value.get("remaining_below_percent")
    if threshold is not None:
        threshold = number(threshold)
        require(threshold <= 100, "invalid_view")
    return {"remaining_below_percent": threshold, "sort_by": value.get("sort_by", "name"),
            "group_by": value.get("group_by", "none")}


def filter_view(rows, view):
    selected = list(rows)
    threshold = view["remaining_below_percent"]
    if threshold is not None:
        selected = [row for row in selected if row["budget_usd"] is not None
                    and Decimal(row["budget_usd"]) > 0
                    and Decimal(row["remaining_usd"]) * 100 < Decimal(row["budget_usd"]) * threshold]
    if view["sort_by"] == "remaining":
        selected.sort(key=lambda row: (row["remaining_usd"] is None,
                                      Decimal(row["remaining_usd"]) if row["remaining_usd"] is not None else 0,
                                      row["user_id"]))
    else:
        selected.sort(key=lambda row: (row["name"].casefold(), row["user_id"]))
    if view["group_by"] == "department":
        selected.sort(key=lambda row: row.get("department", "").casefold())
    return selected


def plain_label(value):
    return " ".join(str(value).split())[:256]


def markdown_text(value):
    return re.sub(r"([\\`*_{}\[\]()#+.!|~\-])", r"\\\1", escape(str(value), quote=True))


def confirmation_text(changes, identities):
    def line(value):
        # Native ConfirmDialog interprets Markdown. Directory names and labels
        # are user-controlled text, never formatting for a financial diff.
        value = escape(plain_label(value), quote=True)
        return re.sub(r"([\\`*_{}\[\]()#+.!|~\-])", r"\\\1", value)
    def amount(value):
        return money(value) if value is not None else "не установлен"
    result = ["Применить эти изменения месячных бюджетов?", ""]
    for change in changes:
        identity = identities[change.user_id]
        result += [f'{line(identity["name"])} <{line(identity["email"])}>',
                   f"Бюджет USD: {amount(change.before.max_budget)} → {money(change.budget_usd)}"]
        old = {model.model: model for model in change.before.models}
        for model, cap in change.new_caps:
            label = (identity.get("model_labels") or {}).get(model, model)
            result.append(f"  {line(label)}: {amount(old[model].max_budget)} → {money(cap)} USD")
            if old[model].spend >= cap:
                result.append("    Лимит не выше начисленного расхода: новые запросы к модели будут отклоняться.")
        if change.before.spend >= change.budget_usd:
            result.append("Новый бюджет ниже начисленного расхода: новые запросы будут отклоняться.")
        result.append("")
    return "\n".join(result)
