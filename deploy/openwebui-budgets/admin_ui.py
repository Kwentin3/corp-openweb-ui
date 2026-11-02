"""Prepared budget editor. Native prompt transport carries proposals, never authority."""

from html import escape
import json


def _text(value, missing="нет данных"):
    return escape(missing if value is None else str(value), quote=True)


def _script_json(value):
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            .replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def render_editor(rows: list[dict], *, as_of: str, status: str = "") -> str:
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
    return ('''<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Бюджеты сотрудников</title>
<style>body{font:14px system-ui;margin:16px;color:#222;background:white}main{max-width:100%}section{border:1px solid #ccc;padding:12px;margin:14px 0;overflow:auto}table{border-collapse:collapse;width:100%;margin-top:12px}td,th{text-align:left;padding:7px;border-bottom:1px solid #ddd}small{display:block;font-weight:normal}input{font:inherit;width:12em;max-width:85%;padding:5px}button{font:inherit;padding:8px;margin:8px 8px 8px 0}input:focus,button:focus{outline:2px solid #2365bd;outline-offset:2px}pre{white-space:pre-wrap;overflow-wrap:anywhere}[role=alert]{color:#a20}p{line-height:1.5}</style></head><body>
<main data-budget-editor="v1"><h1>Бюджеты сотрудников</h1>'''
        + f'<p>Данные на: <time>{_text(as_of)}</time>.</p><p>{_text(status, "")}</p>'
        + '<p>Правки действуют только в этом экране и не сохраняются при обновлении. '
          'Применение отправит JSON в чат через штатное подтверждение. Затем сервер заново проверит '
          'права и данные и отдельно запросит подтверждение изменения бюджета.</p>'
        + '<button type="button" id="refresh">Обновить данные</button><form id="editor">'
        + empty + "".join(sections)
        + '<button type="button" id="apply"' + (' disabled' if not public else '')
        + '>Применить изменения</button></form><p id="feedback" role="alert" aria-live="polite"></p>'
          '<pre id="preview" aria-label="Было → станет" aria-live="polite"></pre></main>'
        + '<script id="budget-data" type="application/json">' + _script_json(public) + '</script>'
        + _PROGRAM + '</body></html>')


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
