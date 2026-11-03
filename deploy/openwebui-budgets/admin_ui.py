"""Prepared budget editor. Native prompt transport carries proposals, never authority."""

from html import escape
import json


def _text(value, missing="нет данных"):
    return escape(missing if value is None else str(value), quote=True)


def _script_json(value):
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            .replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


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


def render_editor(rows: list[dict], *, as_of: str, status: str = "",
                  template: dict | None = None, pending: list[dict] | None = None,
                  service: dict | None = None) -> str:
    # Only the public presentation contract enters HTML; caller owns policy/order.
    public = [{key: row.get(key) for key in ("user_id", "name", "email", "department", "revision",
               "budget_usd", "spend_usd", "remaining_usd")} | {"models": [
        {key: model.get(key) for key in ("id", "label", "cap_usd", "spend_usd", "share_percent")}
        for model in row["models"]]} for row in rows]
    sections, department = [], None
    for index, row in enumerate(public):
        if row["department"] and row["department"] != department:
            department = row["department"]
            sections.append(f'<h2 data-department="{_text(department)}">{_text(department)}</h2>')
        models = []
        for number, model in enumerate(row["models"]):
            field_id = f"share-{index}-{number}"
            models.append(f'<tr><th scope="row"><label for="{field_id}">{_text(model["label"])}</label>'
                f'<small>{_text(model["id"])}</small></th><td>{_text(model["cap_usd"], "не установлен")}</td>'
                f'<td>{_text(model["spend_usd"])}</td><td><input id="{field_id}" data-model-id="{_text(model["id"])}" '
                f'inputmode="decimal" maxlength="128" value="{_text(model["share_percent"], "")}" '
                f'aria-label="Доля для {_text(model["label"])}, процентов" placeholder="нет данных"> %</td></tr>')
        sections.append(f'<section data-employee-id="{_text(row["user_id"])}"><h3>{_text(row["name"])}</h3>'
            f'<p>{_text(row["email"])} · ID: {_text(row["user_id"])}</p>'
            f'<p>Расход: {_text(row["spend_usd"])} USD · Остаток: {_text(row["remaining_usd"])} USD</p>'
            f'<label for="budget-{index}">Личный бюджет, USD</label> '
            f'<input id="budget-{index}" data-field="budget_usd" inputmode="decimal" maxlength="128" '
            f'value="{_text(row["budget_usd"], "")}" placeholder="не установлен">'
            '<table><thead><tr><th>Модель</th><th>Текущий лимит, USD</th><th>Расход, USD</th>'
            '<th>Новая доля</th></tr></thead><tbody>' + "".join(models) + '</tbody></table></section>')
    empty = '<p>Сотрудники для этого представления не найдены.</p>' if not public else ""
    bootstrap_html, bootstrap = _bootstrap_panels(template, pending)
    service_html = ""
    if service is not None:
        service_html = ('<aside data-service-budget="v1"><h2>Служебные расходы</h2>'
            f'<p>{_text(service.get("label"))}. Этот расход не уменьшает личные бюджеты сотрудников.</p>'
            f'<p>Бюджет: <span data-service-cap>{_text(service.get("budget_usd"), "не установлен")}</span> USD · '
            f'Расход: <span data-service-spend>{_text(service.get("spend_usd"))}</span> USD · '
            f'Остаток: <span data-service-remaining>{_text(service.get("remaining_usd"))}</span> USD</p>'
            f'<p>Следующее обновление бюджета: {_text(service.get("budget_reset_at"))}.</p></aside>')
    program = _PROGRAM
    if bootstrap:
        program = program.replace("const height=()=>", _BOOTSTRAP_PROGRAM + "\nconst height=()=>", 1)
    return ('''<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Бюджеты сотрудников</title>
<style>body{font:14px system-ui;margin:16px;color:#222;background:white}main{max-width:100%}section{border:1px solid #ccc;padding:12px;margin:14px 0;overflow:auto}table{border-collapse:collapse;width:100%;margin-top:12px}td,th{text-align:left;padding:7px;border-bottom:1px solid #ddd}small{display:block;font-weight:normal}input{font:inherit;width:12em;max-width:85%;padding:5px}button{font:inherit;padding:8px;margin:8px 8px 8px 0}input:focus,button:focus{outline:2px solid #2365bd;outline-offset:2px}pre{white-space:pre-wrap;overflow-wrap:anywhere}[role=alert]{color:#a20}p{line-height:1.5}</style></head><body>
<main data-budget-editor="v1"><h1>Бюджеты сотрудников</h1>'''
        + f'<p>Данные на: <time>{_text(as_of)}</time>.</p><p>{_text(status, "")}</p>'
        + '<p>Недавние расходы могут появиться с небольшой задержкой.</p>'
        + '<p>Правки действуют только в этом экране и не сохраняются при обновлении. '
          'Применение отправит JSON в чат через штатное подтверждение. Затем сервер заново проверит '
          'права и данные и отдельно запросит подтверждение изменения бюджета.</p>'
        + '<button type="button" id="refresh">Обновить данные</button><form id="editor">'
        + empty + "".join(sections)
        + '<button type="button" id="apply"' + (' disabled' if not public else '')
        + '>Применить изменения</button></form><p id="feedback" role="alert" aria-live="polite"></p>'
          '<pre id="preview" aria-label="Было → станет" aria-live="polite"></pre>'
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
const sum100=values=>{
 const scale=Math.max(...values.map(v=>(v.split('.')[1]||'').length),0);
 return values.reduce((sum,v)=>{const [whole,fraction='']=v.split('.');
  return sum+BigInt(whole+fraction.padEnd(scale,'0'));},0n)===100n*10n**BigInt(scale);
};
const send=text=>parent.postMessage({type:'input:prompt:submit',text},'*');
form.addEventListener('input',()=>{apply.disabled=rows.length===0;feedback.textContent='';preview.textContent='';});
apply.addEventListener('click',event=>{
 event.preventDefault(); if(apply.disabled)return;
 const changes=[], lines=[];
 try{
  const sections=form.querySelectorAll('section[data-employee-id]');
  rows.forEach((row,index)=>{
   const section=sections[index], budget=section.querySelector('[data-field="budget_usd"]').value;
   const values=[...section.querySelectorAll('input[data-model-id]')].map(input=>input.value);
   const changed=budget!==original(row.budget_usd)||values.some((v,i)=>v!==original(row.models[i].share_percent));
   if(!changed)return;
   if(!decimal(budget))throw new Error('Укажите бюджет десятичной строкой без пробелов, со знаком точки.');
   if(!values.length||!values.every(decimal)||!sum100(values))throw new Error('Доли моделей должны быть десятичными строками с суммой 100%.');
   const shares=Object.fromEntries(row.models.map((model,i)=>[model.id,values[i]]));
   changes.push({user_id:row.user_id,expected_revision:row.revision,budget_usd:budget,shares});
   lines.push(String(row.name||row.user_id)+': бюджет '+(row.budget_usd===null?'не установлен':row.budget_usd)+' → '+budget+' USD');
   row.models.forEach((model,i)=>lines.push('  '+model.label+': '+(model.share_percent===null?'нет данных':model.share_percent)+' → '+values[i]+'%'));
  });
  if(!changes.length)throw new Error('Нет изменений для отправки.');
  preview.textContent=lines.join('\n');
  send(JSON.stringify({schema:1,type:'employee_budget_plan',changes}));
  apply.disabled=true;
  feedback.textContent='План передан на штатное подтверждение отправки в чат. Бюджеты ещё не изменены. Для повторной отправки измените поле или обновите данные.';
 }catch(error){feedback.textContent=error.message;preview.textContent='';}
});
document.getElementById('refresh').addEventListener('click',()=>send('Обнови управление бюджетами'));
const height=()=>parent.postMessage({type:'iframe:height',height:document.documentElement.scrollHeight},'*');
new ResizeObserver(height).observe(document.documentElement);addEventListener('load',height);height();
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
