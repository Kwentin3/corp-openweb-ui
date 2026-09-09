#!/usr/bin/env node
/*
 * Private Goal #391 lab transport. It deliberately keeps browser credentials
 * inside the existing ordinary-user Chrome session. JSON Lines is used only
 * between the local lab coordinator and this process; it must never be logged.
 */
import readline from 'node:readline';
import { createRequire } from 'node:module';

const { chromium } = createRequire(import.meta.url)('playwright');

const forbidden = new Set(['chat_id', 'parent_id', 'id', 'user_message', 'files']);
const endpoint = process.env.GOAL391_BROWSER_CDP_ENDPOINT || 'http://127.0.0.1:9222';
const completionTimeoutMs = 120000;
const browser = await chromium.connectOverCDP(endpoint);
const page = browser.contexts().flatMap((context) => context.pages())
  .find((candidate) => candidate.url().startsWith('https://gpt.alpha-soft.ru'));
if (!page) throw new Error('goal391_browser_page_unavailable');

async function get(path) {
  return page.evaluate(async (value) => {
    const response = await fetch(value, { credentials: 'same-origin' });
    const text = await response.text();
    try { return { status: response.status, body: JSON.parse(text) }; }
    catch { throw new Error(`goal391_browser_non_json_response_${response.status}`); }
  }, path);
}

async function dispatch(message) {
  if (message.op === 'preflight') {
    const [auth, models, prompt, chats] = await Promise.all([
      get('/api/v1/auths/'), get('/api/models'), get(`/api/v1/prompts/id/${message.prompt_id}`), get('/api/v1/chats/?page=1'),
    ]);
    if (auth.status !== 200 || auth.body?.role !== 'user' || models.status !== 200 || prompt.status !== 200 || !Array.isArray(chats.body)) {
      throw new Error('goal391_browser_preflight_rejected');
    }
    const history = await get(`/api/v1/prompts/id/${message.prompt_id}/history/${prompt.body.version_id}`);
    if (history.status !== 200) throw new Error('goal391_browser_prompt_history_unavailable');
    return { auth: auth.body, models: models.body, prompt: prompt.body, history: history.body, chat_count: chats.body.length };
  }
  if (message.op === 'chat_count') {
    const chats = await get('/api/v1/chats/?page=1');
    if (chats.status !== 200 || !Array.isArray(chats.body)) throw new Error('goal391_browser_chat_count_unavailable');
    return { chat_count: chats.body.length };
  }
  if (message.op === 'complete') {
    if (!message.form_data || typeof message.form_data !== 'object' || message.form_data.stream !== false || Object.keys(message.form_data).some((key) => forbidden.has(key))) {
      throw new Error('goal391_browser_stateless_form_invalid');
    }
    return page.evaluate(async (formData) => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 120000);
      let response;
      try { response = await fetch('/api/chat/completions', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(formData),
        signal: controller.signal,
      }); }
      catch (error) { throw new Error(error?.name === 'AbortError' ? 'goal391_browser_completion_timeout' : 'goal391_browser_completion_transport_failed'); }
      finally { clearTimeout(timeout); }
      const text = await response.text();
      try { return { status: response.status, body: JSON.parse(text) }; }
      catch { throw new Error(`goal391_browser_non_json_response_${response.status}`); }
    }, message.form_data);
  }
  throw new Error('goal391_browser_operation_invalid');
}

const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of input) {
  try { process.stdout.write(`${JSON.stringify({ ok: true, value: await dispatch(JSON.parse(line)) })}\n`); }
  catch (error) { process.stdout.write(`${JSON.stringify({ ok: false, code: error?.message || 'goal391_browser_bridge_error' })}\n`); }
}
await browser.close();
