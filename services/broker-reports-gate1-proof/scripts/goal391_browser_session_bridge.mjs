#!/usr/bin/env node
/*
 * Private Goal #391 lab transport. It deliberately keeps browser credentials
 * inside the existing ordinary-user Chrome session. One JSON request is read
 * from stdin and one result is written to stdout. A fresh process for each
 * request gives the coordinator an OS-enforced timeout boundary; neither
 * credentials nor private values are logged.
 */
import { createRequire } from 'node:module';

const { chromium } = createRequire(import.meta.url)('playwright');

const forbidden = new Set(['chat_id', 'parent_id', 'id', 'user_message', 'files']);
const endpoint = process.env.GOAL391_BROWSER_CDP_ENDPOINT || 'http://127.0.0.1:9222';
const completionTimeoutMs = 120000;
function pageFor(browser) {
  const page = browser.contexts().flatMap((context) => context.pages())
    .find((candidate) => candidate.url().startsWith('https://gpt.alpha-soft.ru'));
  if (!page) throw new Error('goal391_browser_page_unavailable');
  return page;
}

async function get(page, path) {
  return page.evaluate(async (value) => {
    const response = await fetch(value, { credentials: 'same-origin' });
    const text = await response.text();
    try { return { status: response.status, body: JSON.parse(text) }; }
    catch { throw new Error(`goal391_browser_non_json_response_${response.status}`); }
  }, path);
}

async function dispatch(page, message) {
  if (message.op === 'preflight') {
    const [auth, models, prompt, chats] = await Promise.all([
      get(page, '/api/v1/auths/'), get(page, '/api/models'), get(page, `/api/v1/prompts/id/${message.prompt_id}`), get(page, '/api/v1/chats/?page=1'),
    ]);
    if (
      auth.status !== 200 || auth.body?.role !== 'user' || models.status !== 200
      || !Array.isArray(models.body?.data)
      || !models.body.data.some((model) => model?.id === 'models/gemini-3.5-flash')
      || prompt.status !== 200 || !Array.isArray(chats.body)
    ) {
      throw new Error('goal391_browser_preflight_rejected');
    }
    const history = await get(page, `/api/v1/prompts/id/${message.prompt_id}/history/${prompt.body.version_id}`);
    if (history.status !== 200) throw new Error('goal391_browser_prompt_history_unavailable');
    // The coordinator needs a user identity, the selected Prompt snapshot, and
    // counts only. Do not copy browser credentials, profile data, model
    // definitions, or chat records out of Chrome merely to prove preflight.
    return {
      auth: { id: auth.body.id, role: auth.body.role },
      model_available: Array.isArray(models.body?.data)
        && models.body.data.some((model) => model?.id === 'models/gemini-3.5-flash'),
      prompt: prompt.body,
      history: history.body,
      chat_count: chats.body.length,
    };
  }
  if (message.op === 'chat_count') {
    const chats = await get(page, '/api/v1/chats/?page=1');
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

const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
let browser;
try {
  const message = JSON.parse(chunks.join(''));
  browser = await chromium.connectOverCDP(endpoint);
  const value = await dispatch(pageFor(browser), message);
  process.stdout.write(`${JSON.stringify({ ok: true, value })}\n`);
} catch (error) {
  process.stdout.write(`${JSON.stringify({ ok: false, code: error?.message || 'goal391_browser_bridge_error' })}\n`);
} finally {
  if (browser) await browser.close();
}
