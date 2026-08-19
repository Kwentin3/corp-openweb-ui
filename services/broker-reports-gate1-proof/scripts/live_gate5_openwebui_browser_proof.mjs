#!/usr/bin/env node
/* Real-browser G5.36 proof over OpenWebUI's native auth/chat/file APIs. */

import crypto from "node:crypto";
import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.G536_PLAYWRIGHT_MODULE || "playwright");

const requiredEnv = [
  "G536_BASE_URL",
  "G536_USER_A_EMAIL",
  "G536_USER_A_PASSWORD",
  "G536_USER_B_EMAIL",
  "G536_USER_B_PASSWORD",
  "G536_SOURCE_PATH",
  "G536_MISSING_SOURCE_PATH",
  "G536_FACTS_PATH",
  "G536_OUTPUT_DIR",
];
for (const key of requiredEnv) {
  if (!process.env[key]) throw new Error(`missing_environment:${key}`);
}

const baseUrl = process.env.G536_BASE_URL.replace(/\/$/, "");
const outputDir = path.resolve(process.env.G536_OUTPUT_DIR);
fs.mkdirSync(outputDir, { recursive: true });
const sourceBytes = fs.readFileSync(process.env.G536_SOURCE_PATH);
const missingSourceBytes = fs.readFileSync(process.env.G536_MISSING_SOURCE_PATH);
const sourceFilename = process.env.G536_SOURCE_FILENAME || path.basename(process.env.G536_SOURCE_PATH);
const sourceMimeType = process.env.G536_SOURCE_MIME_TYPE || "text/csv";
const missingSourceFilename =
  process.env.G536_MISSING_SOURCE_FILENAME || path.basename(process.env.G536_MISSING_SOURCE_PATH);
const missingSourceMimeType = process.env.G536_MISSING_SOURCE_MIME_TYPE || "text/csv";
const completeFacts = JSON.parse(fs.readFileSync(process.env.G536_FACTS_PATH, "utf8"));
const partialFacts = structuredClone(completeFacts);
const declarationDate = partialFacts.filing_and_party_identity.filing_instance.declaration_date;
delete partialFacts.filing_and_party_identity.filing_instance.declaration_date;

const sha256 = (bytes) => crypto.createHash("sha256").update(bytes).digest("hex");
const browser = await chromium.launch({ headless: true });

async function login(context, email, password) {
  const page = await context.newPage();
  await page.goto(`${baseUrl}/auth`, { waitUntil: "domcontentloaded" });
  const emailInput = page.locator('input[type="email"], input[name="email"]').first();
  const passwordInput = page.locator('input[type="password"], input[name="password"]').first();
  await emailInput.waitFor({ state: "visible", timeout: 30000 });
  await emailInput.fill(email);
  await passwordInput.fill(password);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForFunction(() => !location.pathname.startsWith("/auth"), null, {
    timeout: 30000,
  });
  return page;
}

async function api(page, urlPath, options = {}) {
  return await page.evaluate(
    async ({ urlPath, options }) => {
      const response = await fetch(urlPath, {
        ...options,
        headers: {
          Accept: "application/json",
          ...(options.headers || {}),
        },
      });
      const contentType = response.headers.get("content-type") || "";
      const body = contentType.includes("json")
        ? await response.json()
        : await response.text();
      return { status: response.status, body };
    },
    { urlPath, options },
  );
}

async function upload(page, bytes, filename, mimeType) {
  const result = await page.evaluate(
    async ({ encoded, filename, mimeType }) => {
      const raw = atob(encoded);
      const bytes = new Uint8Array(raw.length);
      for (let index = 0; index < raw.length; index += 1) bytes[index] = raw.charCodeAt(index);
      const form = new FormData();
      form.append("file", new File([bytes], filename, { type: mimeType }));
      const response = await fetch("/api/v1/files/?process=false", {
        method: "POST",
        body: form,
      });
      return { status: response.status, body: await response.json() };
    },
    { encoded: bytes.toString("base64"), filename, mimeType },
  );
  if (result.status !== 200 || !result.body?.id) throw new Error("native_upload_failed");
  return {
    id: result.body.id,
    filename,
    name: filename,
    mime_type: mimeType,
    content_type: mimeType,
    size: bytes.length,
  };
}

function newMessage(role, content, parentId, model = null) {
  const id = crypto.randomUUID();
  return {
    id,
    parentId,
    childrenIds: [],
    role,
    content,
    ...(model ? { model } : {}),
    timestamp: Date.now(),
  };
}

async function createChat(page, userMessage, file) {
  const assistant = newMessage("assistant", "", userMessage.id, "broker-reports-ndfl");
  userMessage.childrenIds = [assistant.id];
  userMessage.files = [{ type: "file", file }];
  const chat = {
    title: "G5.36 synthetic 3-NDFL proof",
    models: ["broker-reports-ndfl"],
    params: {},
    history: {
      messages: { [userMessage.id]: userMessage, [assistant.id]: assistant },
      currentId: assistant.id,
    },
    messages: [userMessage, assistant],
    tags: [],
    timestamp: Date.now(),
  };
  const created = await api(page, "/api/v1/chats/new", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat }),
  });
  if (created.status !== 200 || !created.body?.id) throw new Error("native_chat_create_failed");
  return { id: created.body.id, chat, userMessage, assistant };
}

async function saveChat(page, state) {
  state.chat.messages = Object.values(state.chat.history.messages);
  const saved = await api(page, `/api/v1/chats/${state.id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat: state.chat }),
  });
  if (saved.status !== 200) throw new Error("native_chat_save_failed");
}

async function complete(page, state, file) {
  await saveChat(page, state);
  const fileValue = { type: "file", file };
  const result = await api(page, "/api/chat/completions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: "broker-reports-ndfl",
      parent_id: state.userMessage.id,
      messages: [{ role: "user", content: state.userMessage.content, files: [fileValue] }],
      files: [fileValue],
      metadata: {
        chat_id: state.id,
        session_id: state.id,
        message_id: state.assistant.id,
        files: [fileValue],
        retention_policy: { mode: "customer_approved_test", explicit: true },
      },
      retention_policy: { mode: "customer_approved_test", explicit: true },
      stream: false,
    }),
  });
  if (result.status !== 200 || result.body?.error) {
    throw new Error(
      `native_chat_completion_failed:${result.body?.error?.detail || result.body?.detail || result.status}`,
    );
  }
  const content = result.body?.choices?.[0]?.message?.content;
  if (typeof content !== "string" || !content) throw new Error("native_chat_content_missing");
  state.assistant.content = content;
  state.assistant.done = true;
  state.chat.history.currentId = state.assistant.id;
  await saveChat(page, state);
  return content;
}

async function appendTurn(page, state, content, file) {
  const userMessage = newMessage("user", content, state.assistant.id);
  const assistant = newMessage("assistant", "", userMessage.id, "broker-reports-ndfl");
  userMessage.childrenIds = [assistant.id];
  userMessage.files = [{ type: "file", file }];
  state.assistant.childrenIds = [userMessage.id];
  state.chat.history.messages[userMessage.id] = userMessage;
  state.chat.history.messages[assistant.id] = assistant;
  state.chat.history.currentId = assistant.id;
  state.userMessage = userMessage;
  state.assistant = assistant;
  return await complete(page, state, file);
}

const contextA = await browser.newContext({ acceptDownloads: true });
const pageA = await login(
  contextA,
  process.env.G536_USER_A_EMAIL,
  process.env.G536_USER_A_PASSWORD,
);

if (process.env.G538_OFFICIAL_SOURCE_PATH) {
  const officialBytes = fs.readFileSync(process.env.G538_OFFICIAL_SOURCE_PATH);
  const officialFilename =
    process.env.G538_OFFICIAL_SOURCE_FILENAME || path.basename(process.env.G538_OFFICIAL_SOURCE_PATH);
  const officialMimeType = process.env.G538_OFFICIAL_SOURCE_MIME_TYPE || "application/pdf";
  let official;
  let state;
  if (process.env.G538_RESUME_LATEST_CHAT === "1") {
    const listed = await api(pageA, "/api/v1/chats/?page=1");
    const rows = Array.isArray(listed.body) ? listed.body : listed.body?.chats;
    const latest = Array.isArray(rows)
      ? rows.find(
          (item) =>
            item?.title === "G5.36 synthetic 3-NDFL proof" ||
            item?.chat?.title === "G5.36 synthetic 3-NDFL proof",
        )
      : null;
    if (listed.status !== 200 || !latest?.id) throw new Error("g538_resume_chat_missing");
    const loaded = await api(pageA, `/api/v1/chats/${latest.id}`);
    if (loaded.status !== 200 || !loaded.body?.chat?.history?.currentId) {
      throw new Error("g538_resume_chat_invalid");
    }
    const chat = loaded.body.chat;
    const assistant = chat.history.messages[chat.history.currentId];
    const firstUser = Object.values(chat.history.messages).find(
      (item) => item?.role === "user" && Array.isArray(item.files) && item.files.length,
    );
    official = firstUser?.files?.[0]?.file;
    if (!official?.id) throw new Error("g538_resume_official_file_missing");
    state = { id: latest.id, chat, userMessage: firstUser, assistant };
    if (process.env.G538_INSPECT_LATEST === "1") {
      fs.mkdirSync(outputDir, { recursive: true });
      fs.writeFileSync(
        path.join(outputDir, "g538-latest-response.private.txt"),
        String(assistant?.content || ""),
        "utf8",
      );
      console.log(JSON.stringify({
        status: "latest_response_captured",
        chat_id: state.id,
        response_chars: String(assistant?.content || "").length,
      }));
      await contextA.close();
      await browser.close();
      process.exit(0);
    }
  } else {
    official = await upload(pageA, officialBytes, officialFilename, officialMimeType);
    const initial = newMessage("user", "Проверить документы для подготовки 3-НДФЛ", null);
    state = await createChat(pageA, initial, official);
    const purchaseOnlyResponse = await complete(pageA, state, official);
    if (purchaseOnlyResponse.includes("Скачать XML")) {
      throw new Error("purchase_only_invented_declaration");
    }
    if (process.env.G538_STOP_AFTER_OFFICIAL === "1") {
      const result = {
        schema_version: "broker_reports_gate5_row_bound_role_official_phase_v0",
        status: "official_gate3_phase_completed",
        native_chat_id: state.id,
        official_source_file_id: official.id,
        official_source_sha256: sha256(officialBytes),
        purchase_only_xml_created: false,
        provider_retry_merge_repair_total: 0,
        browser_engine: "chromium",
      };
      fs.writeFileSync(
        path.join(outputDir, "g538-official-phase.safe.json"),
        `${JSON.stringify(result, null, 2)}\n`,
        "utf8",
      );
      console.log(JSON.stringify(result));
      await contextA.close();
      await browser.close();
      process.exit(0);
    }
  }

  const controlledFacts = structuredClone(completeFacts);
  controlledFacts.supplemental_money = [];
  controlledFacts.securities_disposal.expense_evidence = {};
  controlledFacts.scope.scope_ref = "g538-first-real-economic-coverage";
  controlledFacts.tax_period_category.scope_ref = "g538-controlled-category";
  controlledFacts.tax_period_category.operation_ref = "g538-controlled-disposal";
  const controlledDisposal = await upload(
    pageA,
    sourceBytes,
    sourceFilename,
    sourceMimeType,
  );
  const finalResponse = await appendTurn(
    pageA,
    state,
    `3-НДФЛ факты: ${JSON.stringify(controlledFacts)}`,
    controlledDisposal,
  );
  if (!finalResponse.includes("Декларация сформирована") || !finalResponse.includes("Скачать XML")) {
    throw new Error(`g538_product_xml_terminal_missing:${finalResponse.slice(0, 500)}`);
  }
  const linkMatch = finalResponse.match(
    /\[Скачать XML\]\((\/api\/v1\/files\/([^/]+)\/content\?attachment=true)\)/,
  );
  if (!linkMatch) throw new Error("g538_product_download_link_invalid");
  const xmlFileId = linkMatch[2];

  await pageA.goto(`${baseUrl}/c/${state.id}`, { waitUntil: "domcontentloaded" });
  await pageA.getByText("Декларация сформирована", { exact: false }).last().waitFor({ timeout: 30000 });
  await pageA.screenshot({ path: path.join(outputDir, "g538-user-a-terminal.png"), fullPage: true });
  const downloadPromise = pageA.waitForEvent("download", { timeout: 30000 });
  await pageA.getByRole("link", { name: "Скачать XML" }).last().click();
  const download = await downloadPromise;
  const downloadedPath = path.join(outputDir, "g538-user-a-downloaded.xml");
  await download.saveAs(downloadedPath);
  const downloadedBytes = fs.readFileSync(downloadedPath);

  const contextB = await browser.newContext();
  const pageB = await login(
    contextB,
    process.env.G536_USER_B_EMAIL,
    process.env.G536_USER_B_PASSWORD,
  );
  const officialDenial = await api(pageB, `/api/v1/files/${official.id}/content`);
  const xmlDenial = await api(pageB, `/api/v1/files/${xmlFileId}/content?attachment=true`);
  const chatDenial = await api(pageB, `/api/v1/chats/${state.id}`);
  if (![401, 403, 404].includes(officialDenial.status)) throw new Error("user_b_official_acl_bypass");
  if (![401, 403, 404].includes(xmlDenial.status)) throw new Error("user_b_xml_acl_bypass");
  if (![401, 403, 404].includes(chatDenial.status)) throw new Error("user_b_chat_acl_bypass");

  const result = {
    schema_version: "broker_reports_gate5_first_real_economic_coverage_browser_proof_v0",
    status: "first_real_economic_coverage_product_path_completed",
    native_chat_id: state.id,
    official_source_file_id: official.id,
    controlled_disposal_file_id: controlledDisposal.id,
    xml_file_id: xmlFileId,
    official_source_sha256: sha256(officialBytes),
    controlled_disposal_sha256: sha256(sourceBytes),
    downloaded_xml_sha256: sha256(downloadedBytes),
    downloaded_xml_bytes: downloadedBytes.length,
    purchase_only_xml_created: false,
    controlled_disposal_explicitly_synthetic: true,
    supplemental_money_used: false,
    user_b_denials: {
      official_source_http_status: officialDenial.status,
      xml_http_status: xmlDenial.status,
      chat_http_status: chatDenial.status,
    },
    browser_engine: "chromium",
    browser_route: "OpenWebUI auth + two native file/chat turns + rendered XML download",
  };
  fs.writeFileSync(
    path.join(outputDir, "g538-browser-proof.safe.json"),
    `${JSON.stringify(result, null, 2)}\n`,
    "utf8",
  );
  console.log(JSON.stringify(result));
  await contextB.close();
  await contextA.close();
  await browser.close();
  process.exit(0);
}

const source = await upload(pageA, sourceBytes, sourceFilename, sourceMimeType);
const initial = newMessage("user", "Подготовить 3-НДФЛ", null);
const state = await createChat(pageA, initial, source);
const initialResponse = await complete(pageA, state, source);
if (!initialResponse.includes("структурированные факты")) throw new Error("initial_machine_blocker_missing");
if (process.env.G536_STOP_AFTER_INITIAL === "1") {
  const result = {
    schema_version: "broker_reports_gate5_openwebui_browser_provider_smoke_v0",
    status: "browser_live_provider_smoke_completed",
    native_chat_id: state.id,
    source_file_id: source.id,
    source_sha256: sha256(sourceBytes),
    initial_machine_blocker: true,
    browser_engine: "chromium",
  };
  fs.writeFileSync(
    path.join(outputDir, "browser-provider-smoke.safe.json"),
    `${JSON.stringify(result, null, 2)}\n`,
    "utf8",
  );
  console.log(JSON.stringify(result));
  await contextA.close();
  await browser.close();
  process.exit(0);
}

const partialResponse = await appendTurn(
  pageA,
  state,
  `3-НДФЛ факты: ${JSON.stringify(partialFacts)}`,
  source,
);
if (!partialResponse.includes("declaration_date") || partialResponse.includes("Скачать XML")) {
  throw new Error("mandatory_filing_fact_blocker_missing");
}

const finalResponse = await appendTurn(
  pageA,
  state,
  `3-НДФЛ факты: ${JSON.stringify({ filing_and_party_identity: { filing_instance: { declaration_date: declarationDate } } }, null, 2)}`,
  source,
);
if (!finalResponse.includes("Декларация сформирована") || !finalResponse.includes("Скачать XML")) {
  throw new Error("product_xml_terminal_missing");
}
const linkMatch = finalResponse.match(/\[Скачать XML\]\((\/api\/v1\/files\/([^/]+)\/content\?attachment=true)\)/);
if (!linkMatch) throw new Error("product_download_link_invalid");
const downloadPath = linkMatch[1];
const xmlFileId = linkMatch[2];

await pageA.goto(`${baseUrl}/c/${state.id}`, { waitUntil: "domcontentloaded" });
await pageA.getByText("Декларация сформирована", { exact: false }).last().waitFor({ timeout: 30000 });
await pageA.screenshot({ path: path.join(outputDir, "user-a-terminal.png"), fullPage: true });
const downloadPromise = pageA.waitForEvent("download", { timeout: 30000 });
await pageA.getByRole("link", { name: "Скачать XML" }).last().click();
const download = await downloadPromise;
const downloadedPath = path.join(outputDir, "user-a-downloaded.xml");
await download.saveAs(downloadedPath);
const downloadedBytes = fs.readFileSync(downloadedPath);

const replayResponse = await appendTurn(
  pageA,
  state,
  `3-НДФЛ факты: ${JSON.stringify({ filing_and_party_identity: { filing_instance: { declaration_date: declarationDate } } })}`,
  source,
);
const replayLinkMatch = replayResponse.match(
  /\[Скачать XML\]\((\/api\/v1\/files\/([^/]+)\/content\?attachment=true)\)/,
);
if (!replayResponse.includes("Декларация сформирована") || !replayLinkMatch) {
  throw new Error("deterministic_product_replay_terminal_missing");
}
await pageA.goto(`${baseUrl}/c/${state.id}`, { waitUntil: "domcontentloaded" });
await pageA.getByText("Декларация сформирована", { exact: false }).last().waitFor({ timeout: 30000 });
const replayDownloadPromise = pageA.waitForEvent("download", { timeout: 30000 });
await pageA.getByRole("link", { name: "Скачать XML" }).last().click();
const replayDownload = await replayDownloadPromise;
const replayDownloadedPath = path.join(outputDir, "user-a-replay-downloaded.xml");
await replayDownload.saveAs(replayDownloadedPath);
const replayDownloadedBytes = fs.readFileSync(replayDownloadedPath);
if (!downloadedBytes.equals(replayDownloadedBytes)) {
  throw new Error("deterministic_product_replay_bytes_mismatch");
}

const missingSource = await upload(
  pageA,
  missingSourceBytes,
  missingSourceFilename,
  missingSourceMimeType,
);
const negativeInitial = newMessage(
  "user",
  `3-НДФЛ факты: ${JSON.stringify(completeFacts)}`,
  null,
);
const negativeState = await createChat(pageA, negativeInitial, missingSource);
const missingSourceResponse = await complete(pageA, negativeState, missingSource);
if (!missingSourceResponse.includes("amount") || missingSourceResponse.includes("Скачать XML")) {
  throw new Error("missing_source_fail_closed_missing");
}

const contextB = await browser.newContext();
const pageB = await login(
  contextB,
  process.env.G536_USER_B_EMAIL,
  process.env.G536_USER_B_PASSWORD,
);
const sourceDenial = await api(pageB, `/api/v1/files/${source.id}/content`);
const xmlDenial = await api(pageB, `/api/v1/files/${xmlFileId}/content?attachment=true`);
const chatDenial = await api(pageB, `/api/v1/chats/${state.id}`);
if (![401, 403, 404].includes(sourceDenial.status)) throw new Error("user_b_source_acl_bypass");
if (![401, 403, 404].includes(xmlDenial.status)) throw new Error("user_b_xml_acl_bypass");
if (![401, 403, 404].includes(chatDenial.status)) throw new Error("user_b_chat_acl_bypass");

const result = {
  schema_version: "broker_reports_gate5_openwebui_browser_proof_v0",
  status: "browser_product_path_completed",
  authenticated_browser_users: 2,
  native_chat_id: state.id,
  source_file_id: source.id,
  xml_file_id: xmlFileId,
  replay_xml_file_id: replayLinkMatch[2],
  missing_source_file_id: missingSource.id,
  missing_source_chat_id: negativeState.id,
  source_sha256: sha256(sourceBytes),
  downloaded_xml_sha256: sha256(downloadedBytes),
  downloaded_xml_bytes: downloadedBytes.length,
  deterministic_replay_byte_identical: true,
  deterministic_replay_xml_sha256: sha256(replayDownloadedBytes),
  initial_machine_blocker: true,
  missing_filing_fact_blocker: true,
  missing_source_fail_closed: true,
  user_b_denials: {
    source_http_status: sourceDenial.status,
    xml_http_status: xmlDenial.status,
    chat_http_status: chatDenial.status,
  },
  browser_engine: "chromium",
  browser_route: "OpenWebUI auth + native chat/file APIs + rendered chat download",
};
fs.writeFileSync(
  path.join(outputDir, "browser-proof.safe.json"),
  `${JSON.stringify(result, null, 2)}\n`,
  "utf8",
);
console.log(JSON.stringify(result));

await contextB.close();
await contextA.close();
await browser.close();
