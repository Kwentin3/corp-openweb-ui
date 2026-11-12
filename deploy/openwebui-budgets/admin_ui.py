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
    overview = overview or {}
    prices = {row["id"]: row for row in overview.get("prices", [])}
    catalog = catalog | {key: row.get("label", key) for key, row in prices.items() if key not in catalog}
    legend = []
    for key, label in catalog.items():
        price = prices.get(key, {})
        source = {"remote": "Каталог LiteLLM", "local": "Встроенный каталог LiteLLM"}.get(price.get("source"), "Нет данных")
        badge = '<b class="new-model">новая</b>' if key in new_models else ''
        changed = '<b class="price-changed">цена изменена</b>' if price.get("changed") is True else ''
        legend.append(f'<details class="legend-price"><summary><i data-color-model="{_text(key)}"></i>'
            f'{_text(label)} {badge} · {_money(price.get("input_per_million"))} / '
            f'{_money(price.get("output_per_million"))} {changed}</summary>'
            f'<small>Кэш: {_money(price.get("cache_per_million"))} · '
            f'Источник: {source} · На: <time data-date>{_text(price.get("as_of"))}</time></small></details>')
    accounts = [f'<p class="account-refusal" role="status">{_text(account.get("label"))}: '
        '<strong>Финансовый отказ</strong> · Наблюдение: '
        f'<time data-date>{_text(account.get("event_at"))}</time>. '
        'Событие запроса, не текущий баланс.</p>'
        for account in overview.get("accounts", []) if account.get("status") == "financial_refusal"]
    if overview.get("complete") is False:
        accounts.append('<p class="account-refusal" role="status">Не удалось полностью проверить '
                        'финансовые отказы провайдеров. Обновите данные.</p>')
    return ''.join(legend), ''.join(accounts)


def render_editor(rows: list[dict], *, as_of: str, status: str = "",
                  template: dict | None = None, pending: list[dict] | None = None,
                  service: dict | None = None, overview: dict | None = None) -> str:
    # Caller retains policy, ledger qualification and revision ownership.
    public = [{key: row.get(key) for key in ("user_id", "name", "email", "revision",
               "budget_usd", "spend_usd", "remaining_usd")}
        | {"groups": row.get("groups", [])}
        | {key: row[key] for key in _EXPENSE_FIELDS if key in row} | {"models": [
        {key: model.get(key) for key in ("id", "label", "cap_usd", "spend_usd", "share_percent")}
        | {key: model[key] for key in ("remaining_usd", "new", "pending") if key in model}
        | {key: model[key] for key in _EXPENSE_FIELDS if key in model}
        for model in row["models"]]} for row in rows]
    employee_rows, catalog, new_models = [], {}, set()
    for index, row in enumerate(public):
        models, segments, flags = [], [], []
        for number, model in enumerate(row["models"]):
            catalog.setdefault(model["id"], model["label"])
            if model.get("new") is True or model.get("pending") is True:
                new_models.add(model["id"])
            field_id = f"share-{index}-{number}"
            blocked = rows[index]["models"][number].get("blocked")
            segments.append(f'<span class="segment" data-segment="{number}" data-color-model="{_text(model["id"])}">'
                            f'<span data-segment-label>{_text(model["label"])}</span><b class="segment-percent" data-segment-percent></b></span>')
            if blocked is True:
                flags.append(f'<span class="blocked" title="{_text(model["label"])}: заблокирована">{_text(model["label"])}: блок</span>')
            if model.get("expense_status") == "unknown":
                flags.append(f'<span class="unknown">{_text(model["label"])}: расход неизвестен</span>')
            models.append(f'<div class="exact-model"><label for="{field_id}"><i data-color-model="{_text(model["id"])}"></i>{_text(model["label"])}</label>'
                f'<input type="range" min="0" max="100" step="1" value="0" data-share-slider="{number}" '
                f'aria-label="Доля {_text(model["label"])} для {_text(row["name"])}">'
                '<span class="percent-field">'
                f'<input id="{field_id}" data-model-id="{_text(model["id"])}" '
                f'inputmode="decimal" maxlength="128" value="{_text(model["share_percent"], "")}" '
                f'aria-label="Доля для {_text(row["name"])}: {_text(model["label"])}, процентов" placeholder="нет данных"> %</span>'
                f'<span class="allocation-amount"><output data-allocation="{number}">нет данных</output> USD</span>'
                '<details class="model-stats"><summary>Учёт</summary>'
                f'<small>Лимит: {_money(model["cap_usd"], "не установлен")} USD · '
                f'Учтено: {_money(model["spend_usd"])} USD · '
                f'Остаток по учёту: {_money(model.get("remaining_usd"))} USD</small>'
                + (_expense_markup(model) or '') +
                ('<small data-model-status class="blocked">Заблокирована</small>' if blocked is True else '')
                + '</details></div>')
        employee_rows.append(f'<tr data-employee-id="{_text(row["user_id"])}" data-index="{index}">'
            f'<th scope="row"><details class="employee-info"><summary>{_text(row["name"])}</summary>'
            f'<small>{_text(row["email"])}</small><small>{_text(", ".join(group["name"] for group in row["groups"]), "Без группы")}</small>'
            + (_expense_markup(row) or '') + '</details>'
            f'<button type="button" class="expand-editor" data-toggle-editor aria-expanded="false" aria-controls="employee-editor-{index}">Доли ▾</button>'
            '<span data-draft-label></span></th>'
            f'<td><label class="sr-only" for="budget-{index}">Личный бюджет для {_text(row["name"])}, USD</label>'
            f'<input id="budget-{index}" data-field="budget_usd" inputmode="decimal" maxlength="128" '
            f'value="{_text(row["budget_usd"], "")}" placeholder="не установлен"></td>'
            f'<td>{_spend_cell(row)}</td><td title="Остаток по зарегистрированным расходам; итог и доступность запроса не гарантированы">{_money(row["remaining_usd"])}</td>'
            f'<td class="distribution"><button type="button" class="allocation-bar" data-toggle-editor '
            f'aria-expanded="false" aria-controls="employee-editor-{index}" aria-label="Изменить доли для {_text(row["name"])}">'
            f'<span class="segments">{"".join(segments)}</span></button>'
            f'<small class="row-flags">{" · ".join(flags)}</small></td></tr>'
            f'<tr class="employee-editor" id="employee-editor-{index}" data-editor-index="{index}" hidden><td colspan="5">'
            '<div class="exact-fields">'
            f'<button type="button" data-equal-shares aria-label="Поровну для {_text(row["name"])}"'
            + (' disabled' if not row["models"] else '') + f'>Поровну</button>{"".join(models)}'
            '<small>При изменении доли остаток распределяется пропорционально между остальными включёнными моделями.</small>'
            '<small data-share-feedback role="status" aria-live="polite"></small>'
            '<small class="share-total" data-share-total aria-live="polite"></small></div></td></tr>')
    groups = {group["id"]: group["name"] for row in public for group in row["groups"]}
    options = ''.join(f'<option value="{_text(key)}">{_text(name)}</option>'
                      for key, name in sorted(groups.items(), key=lambda pair: (pair[1].casefold(), pair[0])))
    legend, account_notice = _overview_markup(overview, catalog, new_models)
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
    return ('''<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Бюджеты сотрудников</title>
<style>
*{box-sizing:border-box}body{font:13px system-ui;margin:12px;color:#263445;background:white}h1{font-size:20px;margin:0}p{line-height:1.4;margin:6px 0}small{display:block;font-size:11px;font-weight:400;color:#637084;line-height:1.4}button,input,select{font:inherit;color:inherit}button{cursor:pointer;padding:6px 10px;border:1px solid #c7d1df;border-radius:5px;background:white}button:disabled{cursor:default;opacity:.45}.primary{background:#245dc1;color:white;border-color:#245dc1}input:not([type=range]):not([type=checkbox]),select{padding:5px 6px;border:1px solid #c0ccdb;border-radius:4px;background:white;max-width:100%}input[data-field]{width:80px}input[data-model-id]{width:85px}input[type=checkbox]{margin:0 4px 0 0}header{display:flex;gap:12px;align-items:center;justify-content:space-between;margin-bottom:9px}
.tariffs{padding:8px 10px;background:#f2f5f9;border:1px solid #d8e0eb;border-radius:6px;margin-bottom:10px}.legend{display:flex;flex-wrap:wrap;align-items:start;gap:5px 20px;font-size:11px;font-weight:400;margin-top:4px}.legend-price{flex:0 1 auto;min-width:0}.legend-price>summary{line-height:1.6;overflow-wrap:anywhere}.legend-price i,.exact-model i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px}.legend-price>small{padding:5px 0;max-width:380px}.new-model,.price-changed{font-size:10px;font-weight:500;color:#53677f}.account-refusal{padding:8px 10px;border:1px solid #e6c4b8;border-radius:5px;color:#a33d20;margin-bottom:10px}
.table-scroll{max-height:520px;overflow:auto;border:1px solid #d8e0eb;border-radius:6px}table{border-collapse:separate;border-spacing:0;table-layout:fixed;width:100%;min-width:760px}th,td{text-align:left;padding:8px 10px;vertical-align:middle;border-bottom:1px solid #e3e8ef}thead{position:sticky;top:0;z-index:5}thead th{background:#f2f5f9;vertical-align:top;font-size:12px;border-bottom:1px solid #bdcadb}thead th:nth-child(1){width:23%}thead th:nth-child(2){width:12%}thead th:nth-child(3){width:11%}thead th:nth-child(4){width:20%}thead th:nth-child(5){width:34%}th[scope=row]{font-weight:500}.header-controls{display:flex;gap:4px;margin-top:6px}.header-controls input{min-width:0;width:55%}.header-controls select{min-width:0;width:45%;font-size:11px}#remaining-filter{width:100%;margin-top:6px;font-size:11px}.sort-button{padding:0;border:0;background:none;font-size:12px;font-weight:600;text-align:left;white-space:nowrap}.sort-button[aria-pressed=true]{color:#215cb9}
.allocation-bar{display:block;width:100%;height:27px;padding:0;border:0;border-radius:4px;background:none}.segments{display:flex;height:100%;width:100%;border-radius:4px;overflow:hidden;background:#e4e9f1}.segment{display:flex;align-items:center;justify-content:center;gap:3px;container-type:inline-size;container-name:segment;overflow:hidden;white-space:nowrap;color:white;font-size:10px;min-width:0;padding:0}.segment>[data-segment-label]{overflow:hidden;text-overflow:ellipsis;min-width:0;margin-left:5px}.segment-percent{font-weight:500;flex-shrink:0;margin-right:5px}@container segment (max-width:32px){.segment>[data-segment-label],.segment-percent{display:none}}.allocation-bar[data-valid=false] .segments{opacity:.4}.blocked,.unknown,.invalid,.share-total,[data-share-feedback]{color:#a33d20}.row-flags{font-size:10px}.row-flags:empty,.share-total:empty,[data-share-feedback]:empty{display:none}summary{cursor:pointer}.employee-info>summary{list-style:none;overflow-wrap:anywhere}.employee-info>summary:after{content:' \\24d8';color:#71839a;font-size:10px}.employee-info>summary::-webkit-details-marker{display:none}.expand-editor{display:inline-block;padding:1px 0;border:0;background:none;color:#43648d;font-size:11px;margin-top:3px}.employee-editor>td{padding:0}.exact-fields{padding:12px 14px;background:#f7f9fc;border-top:1px solid #d5deea}.exact-fields>[data-equal-shares]{margin-bottom:8px;font-size:11px}.exact-model{display:grid;grid-template-columns:minmax(100px,1.2fr) minmax(160px,2fr) 105px minmax(90px,1fr) 45px;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid #e3e8ef}.exact-model>label{overflow-wrap:anywhere}.exact-model input[type=range]{width:100%;min-width:0;accent-color:#336da8;cursor:pointer}.percent-field,.allocation-amount{white-space:nowrap}.model-stats{font-size:11px;min-width:0}.model-stats[open]{grid-column:1/-1}.model-stats>small{padding-top:5px}.exact-fields>small{margin-top:6px}
.actions{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-top:9px}.actions label{font-size:12px;margin-right:auto}#changed-count{font-size:12px;white-space:nowrap}[data-draft-label]{font-size:10px;color:#245dc1;margin-left:7px}tr[data-changed=true]{background:#f2f7ff}[hidden]{display:none!important}.optional{margin-top:10px;border-top:1px solid #e0e6ee;padding-top:8px}.optional>summary{font-size:12px;color:#53677f}#plan-review{margin-top:9px;font-size:12px;color:#43648d}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f6fa;padding:9px;font-size:11px;border-radius:4px}#feedback{color:#9b3b22;font-size:12px}#feedback:empty{display:none}:focus-visible{outline:2px solid #598beb;outline-offset:2px}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}@media(max-width:600px){body{margin:8px}header{align-items:start}.table-scroll{max-height:480px}.actions{gap:6px}.actions button{padding:6px 8px}header small{max-width:180px}}
</style></head><body>
<main data-budget-editor="v1"><header><h1>Бюджеты сотрудников</h1>'''
        + f'<small>USD · Месячные лимиты · <time data-date>{_text(as_of)}</time></small></header>'
        + (f'<p>{_text(status)}</p>' if status else '')
        + '<section class="tariffs" aria-label="Тарифы моделей"><small>USD / 1M токенов · вход / выход</small><div class="legend">' + legend + '</div></section>'
        + account_notice
        + '<form id="editor"><div class="table-scroll"><table id="employee-table"><caption class="sr-only">Личные бюджеты и распределение по моделям</caption>'
          '<thead><tr><th scope="col"><button type="button" class="sort-button" data-sort="name" aria-pressed="true">Сотрудник ↑</button>'
          '<div class="header-controls"><input id="search" type="search" aria-label="Поиск по имени или email" title="Имя или email" placeholder="Поиск">'
          '<select id="group" aria-label="Группа" title="Все группы"><option value="">Все группы</option>'
          + options + '<option value="__ungrouped__">Без группы</option></select></div></th>'
          '<th scope="col" title="Общий личный лимит в USD">Лимит, USD</th>'
          '<th scope="col" title="Зарегистрированный расход. Данные могут быть неполными и появляться с задержкой.">'
          '<button type="button" class="sort-button" data-sort="spend" aria-pressed="false">Учтено ↓ ⓘ</button></th>'
          '<th scope="col" title="Остаток по зарегистрированным расходам. Итог и доступность запроса не гарантированы.">'
          '<button type="button" class="sort-button" data-sort="remaining" aria-pressed="false">Остаток по учёту ↑ ⓘ</button>'
          '<select id="remaining-filter" aria-label="Фильтр остатка по учёту"><option value="all">Любой остаток</option>'
          '<option value="low">Мало: до 10%</option><option value="exhausted">Исчерпан: ≤ 0</option></select></th>'
          '<th scope="col" title="Вся полоса — 100% личного лимита. Нажмите для изменения долей.">Распределение · 100%</th></tr></thead><tbody id="employee-rows">'
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
const colors=['#336da8','#6d55a1','#178072','#ad6c26','#a34c70','#687d32','#357f94','#9d432f','#677084'];
const colorIds=[...new Set([...document.querySelectorAll('[data-color-model]')].map(el=>el.dataset.colorModel))].sort();
document.querySelectorAll('[data-color-model]').forEach(el=>{el.style.backgroundColor=colors[colorIds.indexOf(el.dataset.colorModel)%colors.length];});
const entries=rows.map((row,index)=>({row,index,el:form.querySelector('[data-index="'+index+'"]'),panel:form.querySelector('[data-editor-index="'+index+'"]')}));
const inputsOf=entry=>[...entry.panel.querySelectorAll('input[data-model-id]')];
const valuesOf=entry=>inputsOf(entry).map(input=>input.value);
const entryOf=element=>entries.find(entry=>entry.el.contains(element)||entry.panel.contains(element));
const budgetOf=entry=>entry.el.querySelector('[data-field="budget_usd"]').value;
const changed=entry=>budgetOf(entry)!==original(entry.row.budget_usd)||valuesOf(entry).some((v,i)=>v!==original(entry.row.models[i].share_percent));
const reset=document.getElementById('reset-drafts');
let prepared=null;
let sortBy='name';
const clearPreview=()=>{prepared=null;preview.textContent='';document.getElementById('plan-review').hidden=true;feedback.textContent='';feedback.dataset.state='';};
const filters=()=>{
 const query=document.getElementById('search').value.trim().toLocaleLowerCase('ru');
 const group=document.getElementById('group').value, kind=document.getElementById('remaining-filter').value;
 document.getElementById('group').title=document.getElementById('group').selectedOptions[0].textContent;
 const only=document.getElementById('only-changed').checked;
 let count=0;
 entries.forEach(entry=>{
  const row=entry.row, remaining=signed(row.remaining_usd), budget=signed(row.budget_usd);
  const match=(!query||[row.name,row.email].some(v=>String(v||'').toLocaleLowerCase('ru').includes(query)))&&(!group||(group==='__ungrouped__'?row.groups.length===0:row.groups.some(item=>item.id===group)))&&(!only||changed(entry))&&
   (kind==='all'||remaining!==null&&(kind==='exhausted'?remaining.n<=0n:remaining.n>0n&&budget!==null&&budget.n>0n&&compare({n:remaining.n*10n,scale:remaining.scale},budget)<=0));
  entry.el.hidden=!match;entry.panel.hidden=!match||entry.el.querySelector('[data-toggle-editor]').getAttribute('aria-expanded')!=='true';if(match)count++;
 });
 const order=sortBy;
 const sorted=[...entries].sort((a,b)=>{
  if(order==='name')return String(a.row.name||'').localeCompare(String(b.row.name||''),'ru')||a.index-b.index;
  const key=order==='spend'?'spend_usd':'remaining_usd';
  const amount=entry=>signed(entry.row[key]);
  const x=amount(a),y=amount(b);if(x===null)return y===null?a.index-b.index:1;
  if(y===null)return -1;return (order==='spend'?compare(y,x):compare(x,y))||a.index-b.index;
 });
 const body=document.getElementById('employee-rows');sorted.forEach((entry,index)=>{const at=index*2;if(body.children[at]!==entry.el)body.insertBefore(entry.el,body.children[at]||null);if(body.children[at+1]!==entry.panel)body.insertBefore(entry.panel,body.children[at+1]||null);});
 document.getElementById('empty-result').hidden=count!==0;
};
const updateRow=entry=>{
 const values=valuesOf(entry), budget=budgetOf(entry), valid=values.length&&values.every(decimal), complete=valid&&sum100(values);
 const sum=entry.panel.querySelector('[data-share-total]');
 sum.textContent=complete?'':valid?'Сумма '+money(exact(total(values).n,total(values).scale))+'%; нужно 100%':'Задайте доли: сумма 100%';
 entry.el.dataset.changed=String(changed(entry));entry.el.querySelector('[data-draft-label]').textContent=changed(entry)?'Изменён':'';
 entry.el.querySelector('.allocation-bar').dataset.valid=String(Boolean(complete));
 if(complete)entry.validShares=[...values];
 entry.panel.querySelectorAll('[data-share-slider]').forEach(slider=>{
  const value=values[Number(slider.dataset.shareSlider)];
  slider.disabled=!complete;slider.value=valid?value:'0';slider.setAttribute('aria-valuetext',complete?value+' процентов':'Сначала задайте доли с суммой 100%');
 });
 entry.el.querySelectorAll('[data-segment]').forEach(segment=>{const i=Number(segment.dataset.segment),value=values[i];segment.style.flex=complete?'0 0 '+Number(value)+'%':'1';segment.querySelector('[data-segment-label]').textContent=entry.row.models[i].label;segment.querySelector('[data-segment-percent]').textContent=complete?percentFormat.format(value)+'%':'';});
 entry.panel.querySelectorAll('[data-allocation]').forEach(output=>{
  const value=values[Number(output.dataset.allocation)];let amount=null;
  if(decimal(budget)&&decimal(value)){const b=scaled(budget),v=scaled(value);amount=exact(b.n*v.n,b.scale+v.scale+2);}
  output.textContent=money(amount);output.title=amount===null?'нет данных':amount+' USD';
  entry.el.querySelector('[data-segment="'+output.dataset.allocation+'"]').title=entry.row.models[Number(output.dataset.allocation)].label+': '+(value||'нет данных')+'% · '+(amount===null?'нет данных':amount+' USD');
 });
};
const update=()=>{entries.forEach(updateRow);const count=entries.filter(changed).length;document.getElementById('changed-count').textContent='Изменено: '+count;reset.disabled=count===0;apply.disabled=count===0;filters();prepare();};
form.addEventListener('submit',event=>event.preventDefault());
form.addEventListener('click',event=>{
 const toggle=event.target.closest('[data-toggle-editor]');if(toggle){const entry=entryOf(toggle),open=toggle.getAttribute('aria-expanded')!=='true';entry.el.querySelectorAll('[data-toggle-editor]').forEach(button=>{button.setAttribute('aria-expanded',String(open));});entry.el.querySelector('.expand-editor').textContent=open?'Доли ▴':'Доли ▾';entry.panel.hidden=!open;return;}
 const button=event.target.closest('[data-equal-shares]');if(!button||button.disabled)return;
 const entry=entryOf(button),inputs=inputsOf(entry);
 if(!inputs.length)return;const count=BigInt(inputs.length),share=1000000n/count;
 inputs.forEach((input,i)=>input.value=exact(i===inputs.length-1?1000000n-share*(count-1n):share,4));
 entry.panel.querySelector('[data-share-feedback]').textContent='';clearPreview();update();
});
// Retain the weights only for the current pointer gesture; fields remain the draft owner.
form.addEventListener('pointerdown',event=>{if(event.target.matches('[data-share-slider]')){const entry=entryOf(event.target);entry.dragShares=valuesOf(entry);}});
addEventListener('pointerup',()=>entries.forEach(entry=>{entry.dragShares=null;}));
addEventListener('pointercancel',()=>entries.forEach(entry=>{entry.dragShares=null;}));
const redistribute=(entry,index,candidate,baseline)=>{
 if(!baseline||!baseline.every(decimal)||!sum100(baseline)||!decimal(candidate))return;
 const amount=scaled(candidate);if(amount.n>100n*10n**BigInt(amount.scale))return;
 const others=baseline.map((value,i)=>i!==index&&scaled(value).n>0n?i:-1).filter(i=>i>=0);
 const inputs=inputsOf(entry),notice=entry.panel.querySelector('[data-share-feedback]');notice.textContent='';
 if(!others.length&&amount.n!==100n*10n**BigInt(amount.scale)){
  inputs[index].value=baseline[index];notice.textContent='Сначала задайте долю другой модели или выберите «Поровну»: нулевые доли не включаются автоматически.';return;
 }
 if(compare(amount,scaled(baseline[index]))===0){baseline.forEach((value,i)=>{if(i!==index)inputs[i].value=value;});return;}
 const scale=Math.max(4,amount.scale,...baseline.map(value=>scaled(value).scale)),unit=10n**BigInt(scale);
 const remaining=100n*unit-amount.n*10n**BigInt(scale-amount.scale),weights=others.map(i=>{const x=scaled(baseline[i]);return x.n*10n**BigInt(scale-x.scale);});
 const weight=weights.reduce((sum,n)=>sum+n,0n);let used=0n;
 others.forEach((i,position)=>{
  const n=position===others.length-1?remaining-used:remaining*weights[position]/weight;used+=n;
  const value=exact(n,scale),old=scaled(baseline[i]);
  inputs[i].value=compare({n,scale},old)===0?baseline[i]:value.replace(/\.?0+$/,'');
 });
};
form.addEventListener('input',event=>{
 if(!event.target.matches('[data-share-slider],[data-field="budget_usd"],input[data-model-id]'))return;
 const slider=event.target.closest('[data-share-slider]');
 const entry=entryOf(event.target);
 if(slider){const i=Number(slider.dataset.shareSlider);inputsOf(entry)[i].value=slider.value;redistribute(entry,i,slider.value,entry.dragShares||entry.validShares);}
 else if(event.target.matches('input[data-model-id]')){entry.dragShares=null;redistribute(entry,inputsOf(entry).indexOf(event.target),event.target.value,entry.validShares);}
 clearPreview();update();
});
['search','group','remaining-filter','only-changed'].forEach(id=>document.getElementById(id).addEventListener('input',filters));
document.querySelectorAll('[data-sort]').forEach(button=>button.addEventListener('click',()=>{sortBy=button.dataset.sort;document.querySelectorAll('[data-sort]').forEach(item=>item.setAttribute('aria-pressed',String(item===button)));filters();}));
reset.addEventListener('click',()=>{entries.forEach(entry=>{entry.dragShares=null;entry.panel.querySelector('[data-share-feedback]').textContent='';entry.el.querySelector('[data-field="budget_usd"]').value=original(entry.row.budget_usd);inputsOf(entry).forEach((input,i)=>input.value=original(entry.row.models[i].share_percent));});clearPreview();update();});
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
const height=()=>{
 const body=document.body,style=getComputedStyle(body);
 const pixels=Math.ceil(Math.max(body.scrollHeight,body.getBoundingClientRect().height)+(parseFloat(style.marginTop)||0)+(parseFloat(style.marginBottom)||0));
 parent.postMessage({type:'iframe:height',height:pixels},'*');
};
new ResizeObserver(height).observe(document.body);addEventListener('load',height);height();
})();</script>'''


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
