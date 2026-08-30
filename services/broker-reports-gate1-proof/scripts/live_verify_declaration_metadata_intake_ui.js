'use strict';

// Real Chromium + actual loader.js, but a synthetic OpenWebUI DOM/server.
// This is intentionally not a full OpenWebUI/authenticated product E2E.

const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const playwrightModule = process.env.BROKER_REPORTS_PLAYWRIGHT_MODULE || 'playwright';
let chromium;
try {
  ({ chromium } = require(playwrightModule));
} catch (error) {
  throw new Error(
    `playwright_dependency_missing: set BROKER_REPORTS_PLAYWRIGHT_MODULE (${error.message})`
  );
}

const repoRoot = path.resolve(__dirname, '../../..');
const loaderPath = path.resolve(
  process.argv[2] || path.join(repoRoot, 'deploy/openwebui-static/loader.js')
);
const loaderSource = fs.readFileSync(loaderPath, 'utf8');
const loaderSha256 = crypto.createHash('sha256').update(loaderSource).digest('hex');

const baseUrl = 'http://synthetic-openwebui.test';
const fixedPath = '/api/v1/broker-reports/declaration-metadata-intake';
const genericPath = '/api/v1/broker-reports/intake';
const nativeUploadPath = '/api/v1/files/';
const fixedSourceId = 'br-dm-00000000-0000-4000-8000-000000000101';
const genericSourceId = 'br-00000000-0000-4000-8000-000000000102';
const sourceSha256 = 'a'.repeat(64);
const slotChecksum = 'b'.repeat(64);
const metadataFileBytes = Buffer.from('%PDF-1.4\nsynthetic metadata\n');

function successReceipt() {
  return {
    schema_version: 'broker_reports_declaration_metadata_receipt_v2',
    intake_schema_version: 'broker_reports_declaration_metadata_intake_v2',
    source_id: fixedSourceId,
    receipt_id: 'c'.repeat(64),
    owner_user_id: 'synthetic-user',
    source_sha256: sourceSha256,
    slot_checksum: slotChecksum,
    size_bytes: 28,
    intake_slot: 'DECLARATION_METADATA_INPUT',
    slot_owner: 'SERVER_FIXED_DECLARATION_METADATA_INTAKE_V2',
    process: false,
    eligible: true,
    replayed: false,
  };
}

function deferred() {
  let resolve;
  const promise = new Promise((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function multipartFieldNames(request) {
  const body = request.postDataBuffer();
  assert.ok(body, 'fixed request must contain multipart bytes');
  return Array.from(
    body.toString('latin1').matchAll(/content-disposition: form-data; name="([^"]+)"/gi),
    (match) => match[1]
  );
}

function assertExactMultipartFile(request) {
  const body = request.postDataBuffer();
  assert.ok(body, 'fixed request must contain multipart bytes');
  const rawBody = body.toString('latin1');
  const disposition = rawBody.match(
    /content-disposition: form-data; name="file"; filename="([^"]+)"/i
  );
  assert.ok(disposition, 'fixed multipart file disposition is required');
  const mediaType = rawBody.match(/content-type: ([^\r\n]+)/i);
  assert.ok(mediaType, 'fixed multipart file content type is required');
  assert.equal(disposition[1], 'details.pdf');
  assert.equal(mediaType[1].trim().toLowerCase(), 'application/pdf');
  const headerEnd = body.indexOf(Buffer.from('\r\n\r\n'), disposition.index);
  assert.notEqual(headerEnd, -1, 'fixed multipart file headers must terminate');
  const payloadStart = headerEnd + 4;
  const payloadEnd = body.indexOf(Buffer.from('\r\n--'), payloadStart);
  assert.notEqual(payloadEnd, -1, 'fixed multipart file payload must terminate');
  assert.deepEqual(body.subarray(payloadStart, payloadEnd), metadataFileBytes);
  return {
    fields: multipartFieldNames(request),
    filename: disposition[1],
    media_type: mediaType[1].trim().toLowerCase(),
    file_sha256: crypto.createHash('sha256').update(metadataFileBytes).digest('hex'),
  };
}

async function createHarness(browser, mode = 'success') {
  const context = await browser.newContext();
  await context.addInitScript(() => {
    window.sessionStorage.setItem('selectedModels', JSON.stringify(['test']));
  });
  const page = await context.newPage();
  const fixedRequests = [];
  const genericRequests = [];
  const firstFixedRequestObserved = deferred();
  let fixedMode = mode;
  let fixedBarrier = null;

  await page.route('**/*', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname === '/') {
      await route.fulfill({
        status: 200,
        contentType: 'text/html',
        body: [
          '<!doctype html><html><body>',
          '<button id="model-selector-0-button" aria-haspopup="listbox">Broker Reports</button>',
          '<div id="message-input-container"></div>',
          '</body></html>',
        ].join(''),
      });
      return;
    }
    if (url.pathname === '/api/models') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: [
            {
              id: 'test',
              name: 'Broker Reports',
              info: { base_model_id: 'broker_reports_gate1_pipe' },
            },
            {
              id: 'deepseek-chat',
              name: 'DeepSeek',
              info: { base_model_id: null },
            },
          ],
        }),
      });
      return;
    }
    if (url.pathname === '/static/stage2-stt-normalization.json') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
      return;
    }
    if (url.pathname === fixedPath) {
      fixedRequests.push(request);
      firstFixedRequestObserved.resolve();
      if (fixedBarrier) {
        await fixedBarrier.promise;
      }
      if (fixedMode === 'error') {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: { code: 'synthetic_fixed_error' } }),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(fixedMode === 'malformed' ? { source_id: fixedSourceId } : successReceipt()),
      });
      return;
    }
    if (url.pathname === genericPath) {
      genericRequests.push(request);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ source_id: genericSourceId, size_bytes: 4 }),
      });
      return;
    }
    if (url.pathname === nativeUploadPath) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'native-file-id',
          filename: 'ordinary.pdf',
          meta: { content_type: 'application/pdf', size: 4 },
        }),
      });
      return;
    }
    await route.fulfill({ status: 404, body: 'synthetic route absent' });
  });

  await page.goto(`${baseUrl}/`);
  await page.addScriptTag({ content: loaderSource });
  const button = page.locator('[data-declaration-metadata-action="1"]');
  await button.waitFor({ state: 'visible' });

  return {
    page,
    button,
    fixedRequests,
    genericRequests,
    setFixedMode(value) {
      fixedMode = value;
    },
    blockFixedRequest() {
      fixedBarrier = deferred();
      return fixedBarrier;
    },
    waitForFixedRequest() {
      return firstFixedRequestObserved.promise;
    },
    async close() {
      await context.close();
    },
  };
}

async function chooseWithKeyboard(harness, file = true) {
  await harness.button.focus();
  assert.equal(
    await harness.page.evaluate(() => document.activeElement?.dataset.declarationMetadataAction),
    '1'
  );
  const chooserPromise = harness.page.waitForEvent('filechooser');
  await harness.button.press('Enter');
  const chooser = await chooserPromise;
  await chooser.setFiles(
    file
      ? {
          name: 'details.pdf',
          mimeType: 'application/pdf',
          buffer: metadataFileBytes,
        }
      : []
  );
}

async function verifySuccessAndMultipart(browser) {
  const harness = await createHarness(browser);
  try {
    await chooseWithKeyboard(harness);
    const status = harness.page.locator('[data-declaration-metadata-status="success"]');
    await status.waitFor({ state: 'attached' });
    assert.match(await status.textContent(), /details\.pdf/);
    assert.equal(harness.fixedRequests.length, 1);
    const multipart = assertExactMultipartFile(harness.fixedRequests[0]);
    assert.deepEqual(multipart.fields, ['file']);
    const headers = harness.fixedRequests[0].headers();
    assert.match(headers['idempotency-key'], /^declaration-metadata-ui-/);
    assert.equal(headers.role, undefined);
    assert.equal(headers.purpose, undefined);
    assert.equal(headers['source-policy'], undefined);
    assert.equal(await harness.button.getAttribute('aria-busy'), 'false');
    assert.equal(await harness.button.isEnabled(), true);
    assert.equal(
      await harness.page.evaluate(() => document.activeElement?.dataset.declarationMetadataAction),
      '1'
    );
    return {
      fixed_posts: 1,
      multipart_fields: multipart.fields,
      filename: multipart.filename,
      media_type: multipart.media_type,
      file_sha256: multipart.file_sha256,
      focus_returned: true,
    };
  } finally {
    await harness.close();
  }
}

async function verifyCancelHasNoLeak(browser) {
  const harness = await createHarness(browser);
  try {
    await chooseWithKeyboard(harness, false);
    assert.equal(harness.fixedRequests.length, 0);
    await harness.page.evaluate(async () => {
      const body = new FormData();
      body.append('file', new File(['safe'], 'ordinary.pdf', { type: 'application/pdf' }));
      await window.fetch('/api/v1/files/', { method: 'POST', body });
    });
    assert.equal(harness.fixedRequests.length, 0);
    assert.equal(harness.genericRequests.length, 1);
    return { fixed_posts: 0, next_ordinary_route: genericPath };
  } finally {
    await harness.close();
  }
}

async function verifyModelRaceFailsClosed(browser) {
  const harness = await createHarness(browser);
  try {
    const statusHandle = await harness.page.locator('[data-declaration-metadata-status]').elementHandle();
    const terminalStatus = statusHandle.evaluate(
      (element) =>
        new Promise((resolve) => {
          const readStatus = () => element.dataset.declarationMetadataStatus;
          if (readStatus() === 'error') {
            resolve('error');
            return;
          }
          const observer = new MutationObserver(() => {
            if (readStatus() === 'error') {
              observer.disconnect();
              resolve('error');
            }
          });
          observer.observe(element, {
            attributes: true,
            attributeFilter: ['data-declaration-metadata-status'],
          });
        })
    );
    const chooserPromise = harness.page.waitForEvent('filechooser');
    await harness.button.press('Enter');
    const chooser = await chooserPromise;
    await harness.page.evaluate(() => {
      window.sessionStorage.setItem('selectedModels', JSON.stringify(['deepseek-chat']));
      document.querySelector('button[id^="model-selector-"]')?.remove();
    });
    await chooser.setFiles({
      name: 'details.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.4\nrace\n'),
    });
    assert.equal(await terminalStatus, 'error');
    assert.equal(harness.fixedRequests.length, 0);
    assert.equal(
      await statusHandle.evaluate((element) => element.dataset.declarationMetadataStatus),
      'error'
    );
    return { fixed_posts: 0, status: 'error' };
  } finally {
    await harness.close();
  }
}

async function verifyBusyAndDoubleClick(browser) {
  const harness = await createHarness(browser);
  const barrier = harness.blockFixedRequest();
  try {
    const choosePromise = chooseWithKeyboard(harness);
    await harness.page.waitForFunction(() => {
      const button = document.querySelector('[data-declaration-metadata-action="1"]');
      return button?.disabled === true && button.getAttribute('aria-busy') === 'true';
    });
    await harness.waitForFixedRequest();
    assert.equal(harness.fixedRequests.length, 1);
    await harness.button.press('Enter');
    assert.equal(harness.fixedRequests.length, 1);
    barrier.resolve();
    await choosePromise;
    await harness.page.locator('[data-declaration-metadata-status="success"]').waitFor();
    assert.equal(await harness.button.isEnabled(), true);
    return { fixed_posts: 1, duplicate_post_blocked: true };
  } finally {
    barrier.resolve();
    await harness.close();
  }
}

async function verifyTerminalError(browser, mode) {
  const harness = await createHarness(browser, mode);
  try {
    await chooseWithKeyboard(harness);
    await harness.page.locator('[data-declaration-metadata-status="error"]').waitFor();
    assert.equal(harness.fixedRequests.length, 1);
    assert.equal(
      await harness.page.locator('[data-declaration-metadata-status]').getAttribute(
        'data-declaration-metadata-status'
      ),
      'error'
    );
    assert.equal(await harness.button.isEnabled(), true);
    assert.equal(await harness.button.getAttribute('aria-busy'), 'false');
    assert.equal(
      await harness.page.evaluate(() => document.activeElement?.dataset.declarationMetadataAction),
      '1'
    );
    return {
      fixed_posts: 1,
      status: 'error',
      action_reenabled: true,
      focus_returned: true,
    };
  } finally {
    await harness.close();
  }
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  try {
    const receipt = {
      schema_version: 'broker_reports_declaration_metadata_ui_browser_proof_v1',
      proof_scope: 'synthetic_openwebui_real_chromium_actual_loader',
      synthetic_openwebui: true,
      full_openwebui_e2e: false,
      loader_sha256: loaderSha256,
      keyboard_filechooser_success: await verifySuccessAndMultipart(browser),
      cancel_no_leak: await verifyCancelHasNoLeak(browser),
      model_switch_race: await verifyModelRaceFailsClosed(browser),
      busy_and_double_click: await verifyBusyAndDoubleClick(browser),
      http_error: await verifyTerminalError(browser, 'error'),
      malformed_receipt: await verifyTerminalError(browser, 'malformed'),
      verdict: 'PASS',
    };
    process.stdout.write(`${JSON.stringify(receipt, null, 2)}\n`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exitCode = 1;
});
