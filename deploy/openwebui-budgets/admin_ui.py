"""Prepared budget editor. Native prompt transport carries proposals, never authority."""

from html import escape
import json


_EXPENSE_FIELDS = ("expense_status", "known_subtotal_usd", "expense_as_of",
                   "expense_window_start", "expense_window_end_exclusive")


def _text(value, missing="нет данных"):
    return escape(missing if value is None else str(value), quote=True)


def _script_json(value):
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            .replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def _expense_markup(value):
    """Render caller-qualified status/strings; never classify or total ledger rows."""
    state = value.get("expense_status")
    if state is None:
        return None
    label = "Расход неизвестен." if state == "unknown" else "Полнота данных о расходе не подтверждена."
    parts = [f'<span role="status"><strong>{label}</strong></span>']
    if state == "unknown":
        parts.append('<small>В истории есть запросы без данных о расходе.</small>')
    parts.append(f'<small>По данным учёта: {_text(value.get("spend_usd"))} USD. '
                 'Эта сумма не подтверждает итоговый расход.</small>')
    if value.get("known_subtotal_usd") is not None:
        parts.append(f'<small>Подтверждённая часть расхода: {_text(value["known_subtotal_usd"])} USD. '
                     'Итог не подтверждён.</small>')
    if value.get("expense_as_of") is not None:
        parts.append(f'<small>Наблюдение на: {_text(value["expense_as_of"])}.</small>')
    start, end = value.get("expense_window_start"), value.get("expense_window_end_exclusive")
    if start is not None or end is not None:
        parts.append(f'<small>Диапазон наблюдения: с {_text(start)} (включительно) до {_text(end)} (не включается).</small>')
    return ''.join(parts)


def _bootstrap_panels(template, pending):
    """Project only server-provided public suggestions; drafts never create authority."""
    panels, data = [], {}
    if template is not None:
        public = {key: template.get(key) for key in ("revision", "budget_usd", "budget_duration")}
        public["shares"] = [{key: model.get(key) for key in ("id", "label", "share_percent")}
                            for model in template["shares"]]
        data["template"] = public
        shares = []
        for index, model in enumerate(public["shares"]):
            shares.append(f'<tr><th scope="row"><label for="template-share-{index}">{_text(model["label"])}</label>'
                f'<small>{_text(model["id"])}</small></th><td>{_text(model["share_percent"])}</td>'
                f'<td><input id="template-share-{index}" data-template-model="{_text(model["id"])}" '
                f'inputmode="decimal" maxlength="128" value="{_text(model["share_percent"], "")}" '
                f'aria-label="Доля шаблона для {_text(model["label"])}, процентов"> %</td></tr>')
        panels.append('<aside aria-labelledby="template-heading"><h2 id="template-heading">Шаблон для новых сотрудников</h2>'
            '<p>Период: календарный месяц. Сохранение шаблона не меняет существующие бюджеты '
            'и не создаёт новые автоматически.</p>'
            f'<p>Текущий бюджет шаблона: {_text(public["budget_usd"], "не установлен")} USD.</p>'
            '<form id="template-editor"><label for="template-budget">Новый бюджет шаблона, USD</label> '
            f'<input id="template-budget" inputmode="decimal" maxlength="128" value="{_text(public["budget_usd"], "")}" '
            'placeholder="не установлен"><table><thead><tr><th>Модель</th><th>Текущая доля, %</th>'
            '<th>Новая доля</th></tr></thead><tbody>' + ''.join(shares) + '</tbody></table>'
            '<button type="button" id="save-template">Сохранить шаблон</button></form>'
            '<p id="template-feedback" role="alert" aria-live="polite"></p>'
            '<pre id="template-preview" aria-label="Шаблон: было → станет" aria-live="polite"></pre></aside>')
    if pending is not None:
        public = [{key: row.get(key) for key in ("user_id", "name", "email", "revision", "state", "code",
                   "suggested_budget_usd")} | {"models": [
            {key: model.get(key) for key in ("id", "label")} for model in row["models"]],
            "suggested_shares": None if row.get("suggested_shares") is None else {
                model["id"]: row["suggested_shares"].get(model["id"]) for model in row["models"]}}
            for row in pending]
        data["pending"] = public
        employees = []
        for index, row in enumerate(public):
            heading = (f'<article data-pending-index="{index}"><h3>{_text(row["name"])}</h3>'
                       f'<p>{_text(row["email"])} · ID: {_text(row["user_id"])}</p>')
            if row["state"] != "absent":
                message = ('Назначение бюджета неполное.' if row["state"] == "incomplete"
                           else 'Обнаружен конфликт назначения бюджета.')
                employees.append(heading + f'<p>{message} Создание недоступно; требуется проверка.</p>'
                                 f'<small>Код: {_text(row["code"])}</small></article>')
                continue
            shares = []
            suggestions = row["suggested_shares"] or {}
            for number, model in enumerate(row["models"]):
                field_id = f"pending-share-{index}-{number}"
                shares.append(f'<tr><th scope="row"><label for="{field_id}">{_text(model["label"])}</label>'
                    f'<small>{_text(model["id"])}</small></th><td><input id="{field_id}" '
                    f'data-pending-model="{_text(model["id"])}" inputmode="decimal" maxlength="128" '
                    f'value="{_text(suggestions.get(model["id"]), "")}" placeholder="нет данных" '
                    f'aria-label="Начальная доля для {_text(row["name"])}: {_text(model["label"])}, процентов"> %</td></tr>')
            employees.append(heading + f'<label><input type="checkbox" data-initialize="{index}"> Создать бюджет</label>'
                '<p>Бюджет не создан. Расход: нет данных. Значения ниже — предложение; '
                'проверьте их и явно выберите сотрудника.</p>'
                f'<label for="pending-budget-{index}">Начальный личный бюджет, USD</label> '
                f'<input id="pending-budget-{index}" data-pending-budget inputmode="decimal" maxlength="128" '
                f'value="{_text(row["suggested_budget_usd"], "")}" placeholder="не установлен">'
                '<table><thead><tr><th>Модель</th><th>Начальная доля</th></tr></thead><tbody>'
                + ''.join(shares) + '</tbody></table></article>')
        panels.append('<aside aria-labelledby="pending-heading"><h2 id="pending-heading">Неподготовленные бюджеты</h2>'
            '<p>Создание выполняется отдельно от сохранения шаблона. В запрос попадут только отмеченные сотрудники.</p>'
            '<form id="pending-editor">' + (''.join(employees) if public else '<p>Неподготовленных бюджетов нет.</p>')
            + '<button type="button" id="initialize-budgets"'
            + ('' if any(row["state"] == "absent" for row in public) else ' disabled')
            + '>Создать выбранные бюджеты</button></form><p id="pending-feedback" role="alert" aria-live="polite"></p>'
            '<pre id="pending-preview" aria-label="Создание: было → станет" aria-live="polite"></pre></aside>')
    return ''.join(panels), data


def _money(value, missing="нет данных"):
    # Exact public strings; browser formatting changes representation only.
    return f'<span data-money="{_text(value, "")}" title="{_text(value, missing)} USD">{_text(value, missing)}</span>'


def _spend_cell(row):
    if row.get("expense_status") == "unknown":
        return '<strong class="unknown" title="Итоговый расход неизвестен">Неизвестен</strong><small>учтено ' + _money(row.get("spend_usd")) + '</small>'
    return _money(row.get("spend_usd"))


def _overview_markup(overview, catalog, new_models):
    """Represent supplied prices and account observations without deriving state."""
    if overview is None:
        return ''.join(f'<span class="legend-item"><i data-color-model="{_text(key)}"></i>{_text(label)}'
            + (' <b class="new-model">новая</b>' if key in new_models else '')
            + '</span>' for key, label in catalog.items()), '', []
    prices = {row["id"]: row for row in overview.get("prices", [])}
    catalog = catalog | {key: row.get("label", key) for key, row in prices.items() if key not in catalog}
    legend = []
    for key, label in catalog.items():
        price = prices.get(key, {})
        source = {"remote": "Каталог LiteLLM", "local": "Встроенный каталог LiteLLM"}.get(price.get("source"), "Нет данных")
        badge = '<b class="new-model">новая</b>' if key in new_models else ''
        changed = '<b class="price-changed">цена изменена</b>' if price.get("changed") is True else ''
        legend.append(f'<details class="legend-price"><summary title="Вход / выход, USD за 1 млн токенов"><i data-color-model="{_text(key)}"></i>'
            f'{_text(label)} {badge} · вх. {_money(price.get("input_per_million"))} / '
            f'вых. {_money(price.get("output_per_million"))} $/1M {changed}</summary>'
            f'<small>Тарифы за 1 млн токенов, USD. Кэш: {_money(price.get("cache_per_million"))} · '
            f'Источник: {source} · На: <time data-date>{_text(price.get("as_of"))}</time></small></details>')
    accounts, public = [], []
    labels = {"financial_refusal": "Финансовый отказ", "success": "Успешный запрос", "unknown": "Нет данных"}
    for index, account in enumerate(overview.get("accounts", [])):
        balance = account.get("balance")
        public.append({key: account.get(key) for key in ("id", "revision")})
        snapshot = '<p>Баланс: нет данных.</p>'
        if balance is not None:
            source = {"manual": "вручную", "api": "API"}.get(balance.get("source"), "нет данных")
            snapshot = (f'<p>Последний известный баланс: {_text(balance.get("amount"))} {_text(balance.get("currency"))} · '
                f'<time data-date>{_text(balance.get("observed_at"))}</time></p>'
                f'<small>Источник: {source} · Автор: {_text(balance.get("actor"))}</small>')
        current = balance or {}
        accounts.append(f'<details class="account-state" data-account-index="{index}"><summary>'
            f'{_text(account.get("label"))}: <strong class="account-{_text(account.get("status"))}">'
            f'{labels.get(account.get("status"), labels["unknown"])}</strong> · '
            f'<time data-date>{_text(account.get("event_at"))}</time></summary><div class="account-content">'
            + snapshot + '<details class="balance-editor"><summary>Указать баланс вручную</summary>'
            f'<div class="balance-fields"><label for="balance-amount-{index}">Сумма</label>'
            f'<input id="balance-amount-{index}" data-balance-field="amount" inputmode="decimal" maxlength="128" value="{_text(current.get("amount"), "")}">'
            f'<label for="balance-currency-{index}">Валюта</label>'
            f'<input id="balance-currency-{index}" data-balance-field="currency" maxlength="12" value="{_text(current.get("currency"), "USD")}">'
            f'<label for="balance-observed-{index}">Проверено в ЛК</label>'
            f'<input id="balance-observed-{index}" type="datetime-local" step="60" title="Местное время" data-balance-field="observed_at" data-observed-at="{_text(current.get("observed_at"), "")}">'
            '<button type="button" data-submit-balance>Передать баланс</button></div>'
            '<p data-balance-feedback role="alert" aria-live="polite"></p></details></div></details>')
    account_row = ('<tr class="accounts-row"><th colspan="5"><div class="account-states">'
                   + ''.join(accounts) + '</div></th></tr>') if accounts else ''
    return ''.join(legend), account_row, public


def render_editor(rows: list[dict], *, as_of: str, status: str = "",
                  template: dict | None = None, pending: list[dict] | None = None,
                  service: dict | None = None, overview: dict | None = None) -> str:
    # Caller retains policy, ledger qualification and revision ownership.
    public = [{key: row.get(key) for key in ("user_id", "name", "email", "department", "revision",
               "budget_usd", "spend_usd", "remaining_usd")}
        | {key: row[key] for key in _EXPENSE_FIELDS if key in row} | {"models": [
        {key: model.get(key) for key in ("id", "label", "cap_usd", "spend_usd", "share_percent")}
        | {key: model[key] for key in ("remaining_usd", "new", "pending") if key in model}
        | {key: model[key] for key in _EXPENSE_FIELDS if key in model}
        for model in row["models"]]} for row in rows]
    employee_rows, catalog, new_models = [], {}, set()
    for index, row in enumerate(public):
        models, segments, handles, flags = [], [], [], []
        for number, model in enumerate(row["models"]):
            catalog.setdefault(model["id"], model["label"])
            if model.get("new") is True or model.get("pending") is True:
                new_models.add(model["id"])
            field_id = f"share-{index}-{number}"
            blocked = rows[index]["models"][number].get("blocked")
            block_label = "Заблокирована" if blocked is True else "Не заблокирована" if blocked is False else "Нет данных"
            segments.append(f'<span class="segment" data-segment="{number}" data-color-model="{_text(model["id"])}">'
                            f'<span data-segment-label>{_text(model["label"])}</span><b class="segment-percent" data-segment-percent></b></span>')
            if number < len(row["models"]) - 1:
                handles.append(f'<input type="range" min="0" max="100" step="1" value="0" data-share-slider="{number}" '
                    f'aria-label="Граница {_text(model["label"])} / {_text(row["models"][number+1]["label"])} для {_text(row["name"])}">')
            if blocked is True:
                flags.append(f'<span class="blocked" title="{_text(model["label"])}: заблокирована">{_text(model["label"])}: блок</span>')
            if model.get("expense_status") == "unknown":
                flags.append(f'<span class="unknown">{_text(model["label"])}: расход неизвестен</span>')
            models.append(f'<div class="exact-model"><label for="{field_id}">{_text(model["label"])}</label>'
                f'<input id="{field_id}" data-model-id="{_text(model["id"])}" '
                f'inputmode="decimal" maxlength="128" value="{_text(model["share_percent"], "")}" '
                f'aria-label="Доля для {_text(row["name"])}: {_text(model["label"])}, процентов" placeholder="нет данных"> %'
                f'<small>План: <output data-allocation="{number}">нет данных</output> USD · '
                f'Лимит сейчас: {_money(model["cap_usd"], "не установлен")} USD</small>'
                f'<small>Учтено: {_money(model["spend_usd"])} USD</small>'
                + (_expense_markup(model) or '') +
                f'<small data-model-status>{block_label}</small></div>')
        model_summary = ''.join(f'<div class="employee-model"><strong>{_text(model["label"])}</strong>'
            + (' <b class="new-model">новая</b>' if model.get("new") is True or model.get("pending") is True else '')
            + f'<small>Учтено: {_money(model.get("spend_usd"))} USD · Лимит: {_money(model.get("cap_usd"), "не установлен")} USD · '
            f'Остаток по учёту: {_money(model.get("remaining_usd"))} USD</small>'
            + ('<small class="unknown">Расход неизвестен.</small>' if model.get("expense_status") == "unknown" else '')
            + '</div>' for model in row["models"])
        employee_rows.append(f'<tr data-employee-id="{_text(row["user_id"])}" data-index="{index}">'
            f'<th scope="row"><details class="employee-info"><summary>{_text(row["name"])}</summary>'
            f'<small>{_text(row["email"])}</small><small>{_text(row["department"], "Без отдела")}</small>'
            + (_expense_markup(row) or '') + '<div class="employee-models">' + model_summary + '</div></details><span data-draft-label></span></th>'
            f'<td><label class="sr-only" for="budget-{index}">Личный бюджет для {_text(row["name"])}, USD</label>'
            f'<input id="budget-{index}" data-field="budget_usd" inputmode="decimal" maxlength="128" '
            f'value="{_text(row["budget_usd"], "")}" placeholder="не установлен"></td>'
            f'<td>{_spend_cell(row)}</td><td title="Остаток по зарегистрированным расходам; итог и доступность запроса не гарантированы">{_money(row["remaining_usd"])}</td>'
            f'<td class="distribution"><div class="allocation-bar" aria-label="Распределение 100% лимита">'
            f'<div class="segments">{"".join(segments)}</div>{"".join(handles)}</div>'
            f'<div class="row-meta"><span class="row-flags">{" · ".join(flags)}</span>'
            f'<details class="exact-shares"><summary>Доли</summary><div class="exact-fields">{"".join(models)}'
            '<small>Границы меняют две соседние доли. Точная сумма должна быть 100%.</small></div></details></div>'
            '<small class="share-total" data-share-total aria-live="polite"></small></td></tr>')
    departments = sorted({str(row["department"]) for row in public if row["department"]})
    options = ''.join(f'<option value="{_text(d)}">{_text(d)}</option>' for d in departments)
    legend, account_row, accounts = _overview_markup(overview, catalog, new_models)
    bootstrap_html, bootstrap = _bootstrap_panels(template, pending)
    if bootstrap_html:
        bootstrap_html = '<details class="optional"><summary>Новые сотрудники и шаблон</summary>' + bootstrap_html + '</details>'
    service_html = ''
    if service is not None:
        service_html = ('<details class="optional"><summary>Служебные расходы</summary><aside data-service-budget="v1">'
            f'<p>{_text(service.get("label"))}. Этот расход не уменьшает личные бюджеты сотрудников.</p>'
            f'<p>Бюджет: <span data-service-cap>{_money(service.get("budget_usd"), "не установлен")}</span> USD · '
            f'Расход: <span data-service-spend>{_money(service.get("spend_usd"))}</span> USD · '
            f'Остаток: <span data-service-remaining>{_money(service.get("remaining_usd"))}</span> USD</p>'
            f'<p>Следующее обновление бюджета: <time data-date>{_text(service.get("budget_reset_at"))}</time>.</p></aside></details>')
    program = _PROGRAM
    if bootstrap:
        program = program.replace('const height=()=>', _BOOTSTRAP_PROGRAM + '\nconst height=()=>', 1)
    if accounts:
        program = program.replace('const height=()=>', _BALANCE_PROGRAM + '\nconst height=()=>', 1)
    return ('''<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Бюджеты сотрудников</title>
<style>
*{box-sizing:border-box}body{font:13px system-ui;margin:12px;color:#263445;background:white}h1{font-size:20px;margin:0}p{line-height:1.4;margin:6px 0}small{display:block;font-size:11px;font-weight:400;color:#637084;line-height:1.4}button,input,select{font:inherit;color:inherit}button{cursor:pointer;padding:6px 10px;border:1px solid #c7d1df;border-radius:5px;background:white}button:disabled{cursor:default;opacity:.45}.primary{background:#245dc1;color:white;border-color:#245dc1}input:not([type=range]):not([type=checkbox]),select{padding:5px 6px;border:1px solid #c0ccdb;border-radius:4px;background:white;max-width:100%}input[data-field]{width:74px}input[data-model-id]{width:77px}input[type=checkbox]{margin:0 4px 0 0}header{display:flex;gap:12px;align-items:center;justify-content:space-between;margin-bottom:9px}.table-scroll{max-height:520px;overflow:auto;border:1px solid #d8e0eb;border-radius:6px}table{border-collapse:separate;border-spacing:0;table-layout:fixed;width:100%;min-width:760px}th,td{text-align:left;padding:8px 10px;vertical-align:middle;border-bottom:1px solid #e3e8ef}thead th{position:sticky;top:0;z-index:5;background:#f2f5f9;vertical-align:top;font-size:12px;border-bottom:1px solid #bdcadb}thead th:nth-child(1){width:23%}thead th:nth-child(2){width:12%}thead th:nth-child(3){width:11%}thead th:nth-child(4){width:20%}thead th:nth-child(5){width:34%}th[scope=row]{font-weight:500}.header-controls{display:flex;gap:4px;margin-top:6px}.header-controls input{min-width:0;width:55%}.header-controls select{min-width:0;width:45%;font-size:11px}#remaining-filter{width:100%;margin-top:6px;font-size:11px}.sort-button{padding:0;border:0;background:none;font-size:12px;font-weight:600;text-align:left;white-space:nowrap}.sort-button[aria-pressed=true]{color:#215cb9}.legend{display:flex;flex-wrap:wrap;gap:3px 10px;font-size:11px;font-weight:400;margin-top:5px}.legend-item{display:inline-flex;gap:4px;align-items:center}.legend i{width:9px;height:9px;border-radius:2px}.allocation-bar{position:relative;height:27px;margin:0 6px}.segments{display:flex;height:100%;width:100%;border-radius:4px;overflow:hidden;background:#e4e9f1}.segment{display:flex;align-items:center;justify-content:center;gap:3px;container-type:inline-size;container-name:segment;overflow:hidden;white-space:nowrap;color:white;font-size:10px;min-width:0;padding:0}.segment>[data-segment-label]{overflow:hidden;text-overflow:ellipsis;min-width:0;margin-left:5px}.segment-percent{font-weight:500;flex-shrink:0;margin-right:5px}@container segment (max-width:32px){.segment>[data-segment-label]{display:none}.segment-percent{display:none}}.allocation-bar input[type=range]{appearance:none;-webkit-appearance:none;position:absolute;inset:0;width:calc(100% + 12px);margin:0 -6px;height:27px;background:transparent;pointer-events:none;outline:none}.allocation-bar input[type=range]::-webkit-slider-runnable-track{height:0;background:transparent}.allocation-bar input[type=range]::-webkit-slider-thumb{appearance:none;-webkit-appearance:none;pointer-events:auto;width:12px;height:23px;margin-top:-11px;border-radius:3px;border:2px solid white;background:#24374f;box-shadow:0 0 0 1px #7a8da7;cursor:ew-resize}.allocation-bar input[type=range]::-moz-range-track{height:0;background:transparent}.allocation-bar input[type=range]::-moz-range-thumb{pointer-events:auto;width:9px;height:20px;border:2px solid white;border-radius:3px;background:#24374f;cursor:ew-resize}.allocation-bar input:disabled::-webkit-slider-thumb{visibility:hidden}.allocation-bar input:disabled::-moz-range-thumb{visibility:hidden}.allocation-bar input:focus-visible::-webkit-slider-thumb{outline:3px solid #6399ed;outline-offset:2px}.allocation-bar[data-valid=false] .segments{opacity:.4}.row-meta{display:flex;justify-content:space-between;align-items:start;gap:8px;min-height:16px;font-size:10px;margin-top:3px}.row-flags{font-size:10px}.blocked,.unknown,.invalid{color:#a33d20}.unknown{font-size:11px}.share-total{color:#a33d20}.share-total:empty{display:none}summary{cursor:pointer}.employee-info>summary{list-style:none;overflow-wrap:anywhere}.employee-info>summary:after{content:' ⓘ';color:#71839a;font-size:10px}.employee-info>summary::-webkit-details-marker{display:none}.exact-shares{margin-left:auto}.exact-shares>summary{font-size:10px;color:#43648d;white-space:nowrap}.exact-shares[open]{width:100%}.exact-fields{padding:8px;background:#f7f9fc;border:1px solid #d5deea;border-radius:4px;margin-top:5px}.exact-model{display:grid;grid-template-columns:1fr auto auto;align-items:center;gap:4px;margin-bottom:8px}.exact-model>small,.exact-model>span{grid-column:1/-1}.actions{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-top:9px}.actions label{font-size:12px;margin-right:auto}#changed-count{font-size:12px;white-space:nowrap}[data-draft-label]{font-size:10px;color:#245dc1}tr[data-changed=true]{background:#f2f7ff}[hidden]{display:none!important}.optional{margin-top:10px;border-top:1px solid #e0e6ee;padding-top:8px}.optional>summary{font-size:12px;color:#53677f}#plan-review{margin-top:9px;font-size:12px;color:#43648d}#plan-review[hidden]{display:none}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f6fa;padding:9px;font-size:11px;border-radius:4px}#feedback{color:#9b3b22;font-size:12px}#feedback:empty{display:none}:focus-visible{outline:2px solid #598beb;outline-offset:2px}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}@media(max-width:600px){body{margin:8px}header{align-items:start}.table-scroll{max-height:480px}.actions{gap:6px}.actions button{padding:6px 8px}header small{max-width:180px}}
thead{position:sticky;top:0;z-index:5}thead th{position:static}.legend-price{width:100%;font-weight:400}.legend-price>summary{line-height:1.5;overflow-wrap:anywhere}.legend-price i{display:inline-block;margin-right:4px}.legend-price[open]>small{padding:5px;background:#fff;border:1px solid #d8e0eb;border-radius:4px}.new-model,.price-changed{font-size:10px;font-weight:500;color:#53677f}.accounts-row>th{padding:5px 10px;font-weight:400;font-size:11px;background:#f2f5f9}.account-states{display:flex;flex-wrap:wrap;gap:4px 18px}.account-state>summary{line-height:1.5}.account-state time{white-space:nowrap}.account-financial_refusal{color:#a33d20}.account-success{color:#25634c}.account-unknown{color:#637084}.account-state[open]{width:100%}.account-content{padding:7px 0;max-width:640px}.balance-editor{margin-top:8px}.balance-fields{display:grid;grid-template-columns:minmax(100px,auto) minmax(120px,1fr);gap:7px;align-items:center;padding:8px 0;max-width:520px}.balance-fields button{grid-column:2;justify-self:start}.employee-models{margin-top:8px}.employee-model{margin:6px 0;font-size:11px}.employee-model>strong{font-weight:500}[data-balance-feedback]{color:#9b3b22;font-size:12px}[data-balance-feedback]:empty{display:none}
.legend{max-height:120px;overflow:auto}
</style></head><body>
<main data-budget-editor="v1"><header><h1>Бюджеты сотрудников</h1>'''
        + f'<small>USD · Месячные лимиты · <time data-date>{_text(as_of)}</time></small></header>'
        + (f'<p>{_text(status)}</p>' if status else '')
        + '<form id="editor"><div class="table-scroll"><table id="employee-table"><caption class="sr-only">Личные бюджеты и распределение по моделям</caption>'
          '<thead><tr><th scope="col"><button type="button" class="sort-button" data-sort="name" aria-pressed="true">Сотрудник ↑</button>'
          '<div class="header-controls"><input id="search" type="search" aria-label="Поиск по имени или email" title="Имя или email" placeholder="Поиск">'
          '<select id="department" aria-label="Отдел" title="Все отделы"><option value="">Отдел</option>' + options + '</select></div></th>'
          '<th scope="col" title="Общий личный лимит в USD">Лимит, USD</th>'
          '<th scope="col" title="Зарегистрированный расход. Данные могут быть неполными и появляться с задержкой.">'
          '<button type="button" class="sort-button" data-sort="spend" aria-pressed="false">Учтено ↓ ⓘ</button></th>'
          '<th scope="col" title="Остаток по зарегистрированным расходам. Итог и доступность запроса не гарантированы.">'
          '<button type="button" class="sort-button" data-sort="remaining" aria-pressed="false">Остаток по учёту ↑ ⓘ</button>'
          '<select id="remaining-filter" aria-label="Фильтр остатка по учёту"><option value="all">Любой остаток</option>'
          '<option value="low">Мало: до 10%</option><option value="exhausted">Исчерпан: ≤ 0</option></select></th>'
          '<th scope="col" title="Вся полоса — 100% личного лимита. Двигайте границы между соседними моделями.">Распределение · 100%'
          '<div class="legend">' + legend + '</div></th></tr>' + account_row + '</thead><tbody id="employee-rows">'
        + ''.join(employee_rows) + '</tbody></table></div>'
        + '<p id="empty-result"' + (' hidden' if public else '') + '>Сотрудники для этого представления не найдены. Измените фильтры.</p>'
          '<div class="actions"><label><input id="only-changed" type="checkbox"> Только изменённые</label>'
          '<strong id="changed-count" aria-live="polite">Изменено: 0</strong>'
          '<button type="button" id="reset-drafts" disabled>Сбросить правки</button>'
          '<button type="button" id="apply" class="primary" disabled>Применить изменения</button>'
          '<button type="button" id="refresh">Обновить данные</button>'
          '</div></form>'
          '<p id="feedback" role="alert" aria-live="polite"></p>'
          '<details id="plan-review" hidden><summary>Посмотреть изменения</summary><pre id="preview" aria-label="Было → станет" aria-live="polite"></pre></details>'
        + bootstrap_html + service_html + '</main>'
        + '<script id="budget-data" type="application/json">' + _script_json(public) + '</script>'
        + ('<script id="budget-bootstrap-data" type="application/json">' + _script_json(bootstrap) + '</script>' if bootstrap else '')
        + ('<script id="budget-account-data" type="application/json">' + _script_json(accounts) + '</script>' if accounts else '')
        + program + '</body></html>')


_PROGRAM = r'''<script>(()=>{
"use strict";
const rows=JSON.parse(document.getElementById('budget-data').textContent);
const form=document.getElementById('editor'), apply=document.getElementById('apply');
const feedback=document.getElementById('feedback'), preview=document.getElementById('preview');
const original=value=>value===null?'':String(value);
const decimal=value=>value.length<=128&&/^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/.test(value);
const scaled=value=>{const [whole,fraction='']=value.split('.');return {n:BigInt(whole+fraction),scale:fraction.length};};
const exact=(n,scale)=>{const digits=n.toString().padStart(scale+1,'0');return scale?digits.slice(0,-scale)+'.'+digits.slice(-scale):digits;};
const total=values=>{
 const scale=Math.max(...values.map(v=>(v.split('.')[1]||'').length),0);
 return {n:values.reduce((sum,v)=>{const x=scaled(v);return sum+x.n*10n**BigInt(scale-x.scale);},0n),scale};
};
const sum100=values=>{const t=total(values);return t.n===100n*10n**BigInt(t.scale);};
const signed=value=>{
 if(value===null||value===undefined||!/^\-?(?:\d+(?:\.\d+)?|\.\d+)$/.test(String(value)))return null;
 const text=String(value),negative=text.startsWith('-'),x=scaled((negative?text.slice(1):text).replace(/^\./,'0.'));
 return {n:negative?-x.n:x.n,scale:x.scale};
};
const compare=(a,b)=>{const scale=Math.max(a.scale,b.scale),x=a.n*10n**BigInt(scale-a.scale),y=b.n*10n**BigInt(scale-b.scale);return x<y?-1:x>y?1:0;};
const send=text=>parent.postMessage({type:'input:prompt:submit',text},'*');
const numberFormat=new Intl.NumberFormat('ru-RU',{maximumFractionDigits:8});
const percentFormat=new Intl.NumberFormat('ru-RU',{maximumFractionDigits:2});
const money=value=>{
 if(value===null||value===undefined||value==='')return 'нет данных';
 const text=String(value); if(!/^-?(?:\d+(?:\.\d+)?|\.\d+)$/.test(text))return text;
 const nonzero=/[1-9]/.test(text), negative=text.startsWith('-'), n=Number(text);
 if(nonzero&&Math.abs(n)<0.00000001)return negative?'−(< 0,00000001)':'< 0,00000001';
 return numberFormat.format(text);
};
document.querySelectorAll('[data-money]').forEach(el=>{if(el.dataset.money!=='')el.textContent=money(el.dataset.money);});
document.querySelectorAll('time[data-date]').forEach(el=>{const date=new Date(el.textContent);if(!Number.isNaN(date.valueOf())){el.title=el.textContent;el.textContent=new Intl.DateTimeFormat('ru-RU',{dateStyle:'medium',timeStyle:'short'}).format(date);}});
const colors=['#336da8','#6d55a1','#178072','#ad6c26','#a34c70','#687d32'];
const colorIds=[...new Set([...document.querySelectorAll('[data-color-model]')].map(el=>el.dataset.colorModel))].sort();
document.querySelectorAll('[data-color-model]').forEach(el=>{el.style.backgroundColor=colors[colorIds.indexOf(el.dataset.colorModel)%colors.length];});
const entries=rows.map((row,index)=>({row,index,el:form.querySelector('[data-index="'+index+'"]')}));
const valuesOf=entry=>[...entry.el.querySelectorAll('input[data-model-id]')].map(input=>input.value);
const budgetOf=entry=>entry.el.querySelector('[data-field="budget_usd"]').value;
const changed=entry=>budgetOf(entry)!==original(entry.row.budget_usd)||valuesOf(entry).some((v,i)=>v!==original(entry.row.models[i].share_percent));
const reset=document.getElementById('reset-drafts');
let prepared=null;
let sortBy='name';
const clearPreview=()=>{prepared=null;preview.textContent='';document.getElementById('plan-review').hidden=true;feedback.textContent='';feedback.dataset.state='';};
const filters=()=>{
 const query=document.getElementById('search').value.trim().toLocaleLowerCase('ru');
 const department=document.getElementById('department').value, kind=document.getElementById('remaining-filter').value;
 document.getElementById('department').title=department||'Все отделы';
 const only=document.getElementById('only-changed').checked;
 let count=0;
 entries.forEach(entry=>{
  const row=entry.row, remaining=signed(row.remaining_usd), budget=signed(row.budget_usd);
  const match=(!query||[row.name,row.email].some(v=>String(v||'').toLocaleLowerCase('ru').includes(query)))&&(!department||row.department===department)&&(!only||changed(entry))&&
   (kind==='all'||remaining!==null&&(kind==='exhausted'?remaining.n<=0n:remaining.n>0n&&budget!==null&&budget.n>0n&&compare({n:remaining.n*10n,scale:remaining.scale},budget)<=0));
  entry.el.hidden=!match;if(match)count++;
 });
 const order=sortBy;
 const sorted=[...entries].sort((a,b)=>{
  if(order==='name')return String(a.row.name||'').localeCompare(String(b.row.name||''),'ru')||a.index-b.index;
  const key=order==='spend'?'spend_usd':'remaining_usd';
  const amount=entry=>signed(entry.row[key]);
  const x=amount(a),y=amount(b);if(x===null)return y===null?a.index-b.index:1;
  if(y===null)return -1;return (order==='spend'?compare(y,x):compare(x,y))||a.index-b.index;
 });
 const body=document.getElementById('employee-rows');sorted.forEach((entry,index)=>{if(body.children[index]!==entry.el)body.insertBefore(entry.el,body.children[index]||null);});
 document.getElementById('empty-result').hidden=count!==0;
};
const updateRow=entry=>{
 const values=valuesOf(entry), budget=budgetOf(entry), valid=values.length&&values.every(decimal), complete=valid&&sum100(values);
 const sum=entry.el.querySelector('[data-share-total]');
 sum.textContent=complete?'':valid?'Сумма '+money(exact(total(values).n,total(values).scale))+'%; нужно 100%':'Задайте доли: сумма 100%';
 entry.el.dataset.changed=String(changed(entry));entry.el.querySelector('[data-draft-label]').textContent=changed(entry)?'Изменён':'';
 entry.el.querySelector('.allocation-bar').dataset.valid=String(Boolean(complete));
 entry.el.querySelectorAll('[data-share-slider]').forEach(slider=>{
  const i=Number(slider.dataset.shareSlider),t=valid?total(values.slice(0,i+1)):null,value=t?exact(t.n,t.scale):'0';
  slider.disabled=!complete;slider.value=value;slider.setAttribute('aria-valuetext',complete?'Граница '+value+' процентов':'Сначала задайте доли с суммой 100%');
 });
 entry.el.querySelectorAll('[data-segment]').forEach(segment=>{const i=Number(segment.dataset.segment),value=values[i];segment.style.flex=complete?'0 0 '+Number(value)+'%':'1';segment.querySelector('[data-segment-label]').textContent=entry.row.models[i].label;segment.querySelector('[data-segment-percent]').textContent=complete?percentFormat.format(value)+'%':'';});
 entry.el.querySelectorAll('[data-allocation]').forEach(output=>{
  const value=values[Number(output.dataset.allocation)];let amount=null;
  if(decimal(budget)&&decimal(value)){const b=scaled(budget),v=scaled(value);amount=exact(b.n*v.n,b.scale+v.scale+2);}
  output.textContent=money(amount);output.title=amount===null?'нет данных':amount+' USD';
  entry.el.querySelector('[data-segment="'+output.dataset.allocation+'"]').title=entry.row.models[Number(output.dataset.allocation)].label+': '+(value||'нет данных')+'% · '+(amount===null?'нет данных':amount+' USD');
 });
};
const update=()=>{entries.forEach(updateRow);const count=entries.filter(changed).length;document.getElementById('changed-count').textContent='Изменено: '+count;reset.disabled=count===0;apply.disabled=count===0;filters();prepare();};
form.addEventListener('submit',event=>event.preventDefault());
form.addEventListener('input',event=>{
 if(!event.target.matches('[data-share-slider],[data-field="budget_usd"],input[data-model-id]'))return;
 const slider=event.target.closest('[data-share-slider]');
 if(slider){const entry=entries.find(e=>e.el===slider.closest('[data-employee-id]')),inputs=[...entry.el.querySelectorAll('input[data-model-id]')],i=Number(slider.dataset.shareSlider);
  const values=inputs.map(input=>input.value);if(!values.every(decimal)||!sum100(values))return;
  const lower=total(values.slice(0,i)),upper=total(values.slice(0,i+2)),candidate=scaled(slider.value);
  const scale=Math.max(lower.scale,upper.scale,candidate.scale),lo=lower.n*10n**BigInt(scale-lower.scale),hi=upper.n*10n**BigInt(scale-upper.scale);
  const desired=candidate.n*10n**BigInt(scale-candidate.scale),boundary=desired<lo?lo:desired>hi?hi:desired;
  inputs[i].value=exact(boundary-lo,scale);inputs[i+1].value=exact(hi-boundary,scale);
 }
 clearPreview();update();
});
['search','department','remaining-filter','only-changed'].forEach(id=>document.getElementById(id).addEventListener('input',filters));
document.querySelectorAll('[data-sort]').forEach(button=>button.addEventListener('click',()=>{sortBy=button.dataset.sort;document.querySelectorAll('[data-sort]').forEach(item=>item.setAttribute('aria-pressed',String(item===button)));filters();}));
reset.addEventListener('click',()=>{entries.forEach(entry=>{entry.el.querySelector('[data-field="budget_usd"]').value=original(entry.row.budget_usd);entry.el.querySelectorAll('input[data-model-id]').forEach((input,i)=>input.value=original(entry.row.models[i].share_percent));});clearPreview();update();});
const prepare=()=>{
 prepared=null;preview.textContent='';document.getElementById('plan-review').hidden=true;
 const changes=[],lines=[];
 try{
  entries.forEach(entry=>{
   if(!changed(entry))return;const row=entry.row,budget=budgetOf(entry),values=valuesOf(entry);
   if(!decimal(budget))throw new Error(String(row.name||'Сотрудник')+': укажите бюджет десятичной строкой без пробелов, со знаком точки.');
   if(!values.length||!values.every(decimal)||!sum100(values))throw new Error(String(row.name||'Сотрудник')+': доли моделей должны быть десятичными строками с суммой 100%.');
   changes.push({user_id:row.user_id,expected_revision:row.revision,budget_usd:budget,shares:Object.fromEntries(row.models.map((model,i)=>[model.id,values[i]]))});
   lines.push(String(row.name||row.email||'Сотрудник')+': бюджет '+(row.budget_usd===null?'не установлен':row.budget_usd)+' → '+budget+' USD');
   row.models.forEach((model,i)=>lines.push('  '+model.label+': '+(model.share_percent===null?'нет данных':model.share_percent)+' → '+values[i]+'%'));
  });
  if(!changes.length)return;
  prepared={schema:1,type:'employee_budget_plan',changes};preview.textContent='Будут переданы все изменённые сотрудники, включая скрытых фильтрами.\n\n'+lines.join('\n');
  document.getElementById('plan-review').hidden=false;
 }catch(error){preview.textContent=error.message;document.getElementById('plan-review').hidden=false;}
};
apply.addEventListener('click',()=>{
 if(apply.disabled)return;prepare();
 if(!prepared){feedback.textContent=preview.textContent||'Нет изменений для отправки.';return;}
 apply.disabled=true;feedback.dataset.state='';feedback.textContent='Передаём план на подтверждение…';
 try{send(JSON.stringify(prepared));feedback.textContent='План передан на штатное подтверждение отправки в чат. Бюджеты ещё не изменены. Результат сохранения появится в ответе сервера. Если отправка отменена, измените поле или сбросьте правки для повтора.';}
 catch(error){feedback.textContent='Не удалось передать план: '+error.message;apply.disabled=false;}
});
const refresh=()=>{send('Обнови управление бюджетами');feedback.textContent='Запрос обновления передан в чат. Дождитесь нового экрана.';};
document.getElementById('refresh').addEventListener('click',()=>{
 const extraDirty=[...document.querySelectorAll('#template-editor input,#pending-editor input')].some(input=>input.type==='checkbox'?input.checked:input.value!==input.defaultValue);
 if(entries.some(changed)||extraDirty){feedback.textContent='Есть несохранённые правки. Примените или сбросьте их перед обновлением.';return;}refresh();
});
update();
const height=()=>parent.postMessage({type:'iframe:height',height:document.documentElement.scrollHeight},'*');
new ResizeObserver(height).observe(document.documentElement);addEventListener('load',height);height();
})();</script>'''


_BALANCE_PROGRAM = r'''
const accounts=JSON.parse(document.getElementById('budget-account-data').textContent);
document.querySelectorAll('[data-account-index]').forEach(editor=>{
 const account=accounts[Number(editor.dataset.accountIndex)];
 const button=editor.querySelector('[data-submit-balance]'), feedback=editor.querySelector('[data-balance-feedback]');
 const observed=editor.querySelector('[data-balance-field="observed_at"]');
 const initial=observed.dataset.observedAt?new Date(observed.dataset.observedAt):new Date();
 if(!Number.isNaN(initial.valueOf())){
  const pad=value=>String(value).padStart(2,'0');
  observed.value=initial.getFullYear()+'-'+pad(initial.getMonth()+1)+'-'+pad(initial.getDate())+'T'+pad(initial.getHours())+':'+pad(initial.getMinutes());
 }
 editor.addEventListener('input',()=>{button.disabled=false;feedback.textContent='';});
 button.addEventListener('click',()=>{
  if(button.disabled)return;
  const extraDirty=[...document.querySelectorAll('#template-editor input,#pending-editor input')].some(input=>input.type==='checkbox'?input.checked:input.value!==input.defaultValue);
  if(entries.some(changed)||extraDirty){feedback.textContent='Есть несохранённые правки бюджетов. Примените или сбросьте их перед передачей баланса.';return;}
  const field=name=>editor.querySelector('[data-balance-field="'+name+'"]').value;
  const amount=field('amount'), currency=field('currency'), observedDate=new Date(field('observed_at'));
  if(amount.length>128||!/^\-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/.test(amount)){feedback.textContent='Укажите сумму десятичной строкой без пробелов, со знаком точки.';return;}
  if(!currency.trim()||Number.isNaN(observedDate.valueOf())){feedback.textContent='Укажите валюту и время проверки в ЛК.';return;}
  const observed_at=observedDate.toISOString();
  button.disabled=true;
  try{
   send(JSON.stringify({schema:1,type:'provider_balance_snapshot',account_id:account.id,expected_revision:account.revision,amount,currency,observed_at}));
   feedback.textContent='Баланс передан на штатное подтверждение отправки в чат. Запись ещё не сохранена. Результат появится в ответе сервера. Для повторной отправки измените поле.';
  }catch(error){button.disabled=false;feedback.textContent='Не удалось передать баланс: '+error.message;}
 });
});
'''


_BOOTSTRAP_PROGRAM = r'''
const bootstrap=JSON.parse(document.getElementById('budget-bootstrap-data').textContent);
const validateDraft=(budget,values)=>{
 if(!decimal(budget))throw new Error('Укажите бюджет десятичной строкой без пробелов, со знаком точки.');
 if(!values.length||!values.every(decimal)||!sum100(values))throw new Error('Доли моделей должны быть десятичными строками с суммой 100%.');
};
if(bootstrap.template){
 const current=bootstrap.template, editor=document.getElementById('template-editor');
 const button=document.getElementById('save-template'), feedback=document.getElementById('template-feedback');
 const preview=document.getElementById('template-preview');
 editor.addEventListener('input',()=>{button.disabled=false;feedback.textContent='';preview.textContent='';});
 button.addEventListener('click',()=>{
  if(button.disabled)return;
  try{
   const budget=document.getElementById('template-budget').value;
   const values=[...editor.querySelectorAll('input[data-template-model]')].map(input=>input.value);
   validateDraft(budget,values);
   if(budget===original(current.budget_usd)&&values.every((v,i)=>v===original(current.shares[i].share_percent)))
    throw new Error('Нет изменений для отправки.');
   const shares=Object.fromEntries(current.shares.map((model,i)=>[model.id,values[i]]));
   preview.textContent=['Бюджет шаблона: '+(current.budget_usd===null?'не установлен':current.budget_usd)+' → '+budget+' USD',
    ...current.shares.map((model,i)=>model.label+': '+(model.share_percent===null?'нет данных':model.share_percent)+' → '+values[i]+'%')].join('\n');
   send(JSON.stringify({schema:1,type:'employee_budget_template',expected_revision:current.revision,
    budget_usd:budget,shares,budget_duration:'1mo'}));
   button.disabled=true;
   feedback.textContent='Шаблон передан на штатное подтверждение отправки в чат. Шаблон ещё не сохранён. Для повторной отправки измените поле или обновите данные.';
  }catch(error){feedback.textContent=error.message;preview.textContent='';}
 });
}
if(bootstrap.pending){
 const editor=document.getElementById('pending-editor'), button=document.getElementById('initialize-budgets');
 const feedback=document.getElementById('pending-feedback'), preview=document.getElementById('pending-preview');
 editor.addEventListener('input',()=>{
  button.disabled=!bootstrap.pending.some(row=>row.state==='absent');feedback.textContent='';preview.textContent='';
 });
 button.addEventListener('click',()=>{
  if(button.disabled)return;
  try{
   const changes=[], lines=[];
   bootstrap.pending.forEach((row,index)=>{
    if(row.state!=='absent')return;
    const article=editor.querySelector('[data-pending-index="'+index+'"]');
    if(!article.querySelector('input[data-initialize]').checked)return;
    const budget=article.querySelector('[data-pending-budget]').value;
    const values=[...article.querySelectorAll('input[data-pending-model]')].map(input=>input.value);
    validateDraft(budget,values);
    changes.push({user_id:row.user_id,expected_revision:row.revision,budget_usd:budget,
     shares:Object.fromEntries(row.models.map((model,i)=>[model.id,values[i]]))});
    lines.push(String(row.name||row.user_id)+': бюджет не создан → '+budget+' USD');
    row.models.forEach((model,i)=>lines.push('  '+model.label+': не установлен → '+values[i]+'%'));
   });
   if(!changes.length)throw new Error('Выберите сотрудников для создания бюджета.');
   preview.textContent=lines.join('\n');
   send(JSON.stringify({schema:1,type:'employee_budget_initialize',changes}));
   button.disabled=true;
   feedback.textContent='План создания передан на штатное подтверждение отправки в чат. Бюджеты ещё не созданы. Для повторной отправки измените поле или обновите данные.';
  }catch(error){feedback.textContent=error.message;preview.textContent='';}
 });
}
'''
