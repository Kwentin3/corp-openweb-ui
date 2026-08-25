#!/usr/bin/env node
/* Browser-only acceptance driver for Issue #306.
 *
 * The driver reads only the bounded control credentials, the user-visible
 * synthetic truth card and the source file. It interacts with OpenWebUI through
 * rendered controls and user-visible links; it never calls an application API.
 */

const crypto = require('crypto');
const childProcess = require('child_process');
const fs = require('fs');
const path = require('path');

const playwrightModule = process.env.ISSUE306_PLAYWRIGHT_MODULE || 'playwright';
const { chromium } = require(playwrightModule);

const MODAL_TITLE = 'Данные для 3-НДФЛ';
const CONTINUE = 'Продолжить';
const PUBLIC_SOURCE_SAMPLE_ID = 'g537_tbank_public_pdf_purchase';

function sha256Bytes(value) {
  return crypto.createHash('sha256').update(value).digest('hex');
}

function canonicalSha256(value) {
  function canonical(item) {
    if (Array.isArray(item)) return item.map(canonical);
    if (item !== null && typeof item === 'object') {
      return Object.fromEntries(
        Object.keys(item).sort().map((key) => [key, canonical(item[key])]),
      );
    }
    return item;
  }
  return sha256Bytes(JSON.stringify(canonical(value)));
}

function receipt(value) {
  return { ...value, receipt_sha256: canonicalSha256(value) };
}

function gitBlobSha256(repoRoot, testedCommit, filePath) {
  const relative = path.relative(repoRoot, filePath).split(path.sep).join('/');
  if (!relative || relative.startsWith('../')) throw new Error('proof_file_outside_repo');
  const blob = childProcess.execFileSync(
    'git', ['show', `${testedCommit}:${relative}`],
    { cwd: repoRoot, encoding: null, maxBuffer: 16 * 1024 * 1024 },
  );
  return sha256Bytes(blob);
}

function loadProofBinding(statePath, control) {
  const repoRoot = path.resolve(__dirname, '../../..');
  const dirty = childProcess.execFileSync(
    'git', ['status', '--porcelain', '--untracked-files=no'],
    { cwd: repoRoot, encoding: 'utf8' },
  ).trim();
  if (dirty) throw new Error('tested_tracked_tree_not_clean');
  const testedCommit = childProcess.execFileSync(
    'git', ['rev-parse', 'HEAD'], { cwd: repoRoot, encoding: 'utf8' },
  ).trim();
  if (!/^[0-9a-f]{40}$/.test(testedCommit)) throw new Error('tested_commit_invalid');
  const bundlePath = path.resolve(
    __dirname, '../openwebui_actions/broker_reports_gate1_pipe_bundled.py',
  );
  const bundleSha256 = sha256Bytes(fs.readFileSync(bundlePath));
  if (bundleSha256 !== control.deployed_bundle_sha256) {
    throw new Error('installed_bundle_not_current_tested_bytes');
  }
  const preparedPath = path.join(path.dirname(statePath), 'control-prepared.safe.json');
  const prepared = JSON.parse(fs.readFileSync(preparedPath, 'utf8'));
  const preparedBase = { ...prepared };
  delete preparedBase.receipt_sha256;
  if (prepared.receipt_sha256 !== canonicalSha256(preparedBase)) {
    throw new Error('control_prepared_receipt_invalid');
  }
  if (prepared.status !== 'prepared' || prepared.deployed_bundle_sha256 !== bundleSha256) {
    throw new Error('control_prepared_not_bound_to_bundle');
  }
  return {
    tested_commit: testedCommit,
    generated_bundle_sha256: bundleSha256,
    browser_driver_sha256: gitBlobSha256(repoRoot, testedCommit, __filename),
    control_script_sha256: gitBlobSha256(
      repoRoot,
      testedCommit,
      path.resolve(__dirname, 'live_gate5_openwebui_product_path_control.py'),
    ),
    control_prepared_receipt_sha256: prepared.receipt_sha256,
  };
}

function loadPublicRepresentativeSource(sourcePath) {
  const corpusPath = path.resolve(
    __dirname, '../tests/fixtures/g537_coverage_corpus.v0.json',
  );
  const corpus = JSON.parse(fs.readFileSync(corpusPath, 'utf8'));
  const samples = Array.isArray(corpus.samples) ? corpus.samples : [];
  const matches = samples.filter((item) => item.sample_id === PUBLIC_SOURCE_SAMPLE_ID);
  if (matches.length !== 1) throw new Error('public_source_owner_record_invalid');
  const owner = matches[0];
  const origin = owner.evidence_origin;
  if (
    owner.source_or_broker !== 'T-Bank'
    || owner.document_format !== 'pdf'
    || !origin
    || origin.kind !== 'official_public_broker_sample'
    || typeof origin.source_url !== 'string'
  ) {
    throw new Error('public_source_owner_contract_invalid');
  }
  const bytes = fs.readFileSync(sourcePath);
  const contentSha256 = sha256Bytes(bytes);
  if (contentSha256 !== owner.content_sha256) {
    throw new Error('public_source_bytes_not_owner_pinned');
  }
  return {
    upload: {
      name: path.basename(sourcePath),
      mimeType: 'application/pdf',
      buffer: bytes,
    },
    receipt: {
      sample_id: PUBLIC_SOURCE_SAMPLE_ID,
      content_sha256: contentSha256,
      size_bytes: bytes.length,
      source_url: origin.source_url,
    },
  };
}

function requireMatch(text, regex, code) {
  const match = text.match(regex);
  if (!match) throw new Error(code);
  return match;
}

function readTruth(truthPath) {
  const text = fs.readFileSync(truthPath, 'utf8');
  const fullName = requireMatch(text, /^ФИО:\s*(.+)$/m, 'truth_name_missing')[1].trim();
  const nameParts = fullName.split(/\s+/);
  if (nameParts.length !== 3) throw new Error('truth_name_shape_invalid');
  return {
    lastName: nameParts[0],
    firstName: nameParts[1],
    middleName: nameParts[2],
    inn: requireMatch(text, /^ИНН:\s*([0-9]{12})$/m, 'truth_inn_missing')[1],
    present: requireMatch(text, /^Присутствие в РФ:\s*(.+)$/m, 'truth_presence_missing')[1].trim(),
    absent: requireMatch(text, /^Отсутствие в РФ:\s*(.+)$/m, 'truth_absence_missing')[1].trim(),
    declarationDate: requireMatch(text, /^Дата декларации:\s*(.+)$/m, 'truth_date_missing')[1].trim(),
    destination: requireMatch(text, /^Налоговый орган:\s*([0-9]{4})$/m, 'truth_destination_missing')[1],
    oktmo: requireMatch(text, /^ОКТМО:\s*([0-9]{8}(?:[0-9]{3})?)$/m, 'truth_oktmo_missing')[1],
  };
}

async function login(context, baseUrl, user) {
  const page = await context.newPage();
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.locator('input[type=email]').fill(user.email);
  await page.locator('input[type=password]').fill(user.password);
  await page.locator('button[type=submit]').click();
  await page.locator('#chat-input').waitFor({ state: 'visible', timeout: 60000 });
  return page;
}

async function selectNdfl(page) {
  const ndfl = page.locator('button[aria-label$="NDFL"]');
  await ndfl.first().waitFor({ state: 'visible', timeout: 60000 });
  await ndfl.first().click();
  await page.waitForTimeout(500);
  await page.locator('button[aria-label$="NDFL"]').last().click();
}

async function rememberTurnBoundary(page) {
  const items = page.locator('[role="listitem"]');
  const count = await items.count();
  page.__issue310TurnBoundary = {
    count,
    text: count ? await items.last().innerText() : '',
  };
}

async function sendMessage(page, message) {
  await rememberTurnBoundary(page);
  const input = page.locator('#chat-input');
  await input.waitFor({ state: 'visible', timeout: 90000 });
  await input.fill(message);
  const send = page.locator('#send-message-button');
  await send.waitFor({ state: 'visible', timeout: 10000 });
  await send.click();
  await page.waitForTimeout(250);
}

async function waitForTurn(page) {
  const boundary = page.__issue310TurnBoundary || { count: 0, text: '' };
  await page.waitForFunction(
    ({ previousCount, previousText }) => {
      const items = [...document.querySelectorAll('[role="listitem"]')];
      const last = items.at(-1);
      if (!last) return false;
      const text = (last.innerText || '').trim();
      const advanced = items.length > previousCount || text !== previousText.trim();
      return advanced && /Расчёт остановлен|Расчётный черновик готов|3-НДФЛ XML подготовлен|Подготовка остановлена|Подготовка приостановлена|Анализ завершён|Продажа найдена|В отчёте есть позиция|Не удалось|Готов только анализ|Неподаваемый черновик/.test(text);
    },
    { previousCount: boundary.count, previousText: boundary.text },
    { timeout: 120000 },
  );
  page.__issue310TurnBoundary = null;
  const terminalMessage = page.locator('[role="listitem"]').last();
  await page.locator('#chat-input').waitFor({ state: 'visible', timeout: 30000 });
  let body = await terminalMessage.innerText();
  let stableTicks = 0;
  while (stableTicks < 5) {
    await page.waitForTimeout(250);
    const current = await terminalMessage.innerText();
    if (current === body) {
      stableTicks += 1;
    } else {
      body = current;
      stableTicks = 0;
    }
  }
  await page.locator('#stop-response-button').waitFor({
    state: 'hidden',
    timeout: 30000,
  });
  const forbidden = [
    /fact_key/i,
    /ArtifactStore/i,
    /request_publication_ref/i,
    /handoff mode/i,
    /run normrun_/i,
    /brjob_/i,
    /technical link/i,
    /exact status/i,
    /terminal:/i,
    /reason codes/i,
    /case note/i,
    /source completeness/i,
    /[A-Z][A-Z0-9]+(?:_[A-Z0-9]+){2,}/,
  ];
  if (forbidden.some((pattern) => pattern.test(body))) {
    throw new Error('hidden_architecture_leaked_into_chat');
  }
  return body;
}

async function waitForQuestion(page) {
  const title = page.getByText(MODAL_TITLE, { exact: true });
  await title.waitFor({ state: 'visible', timeout: 120000 });
  const body = await page.locator('body').innerText();
  const marker = body.lastIndexOf(MODAL_TITLE);
  const question = marker >= 0 ? body.slice(marker) : body;
  const forbidden = [
    /fact_key/i,
    /ArtifactStore/i,
    /request_publication_ref/i,
    /\bINITIAL\b/,
    /\bCORRECTION\b/,
    /\bSELF\b/,
    /\bREPRESENTATIVE\b/,
    /\bPAYMENT\b/,
    /individual_not_ip_not_private_practice/i,
    /Choose initial filing/i,
    /State whether the taxpayer/i,
  ];
  if (forbidden.some((pattern) => pattern.test(question))) {
    throw new Error('hidden_architecture_leaked_into_question');
  }
  return question;
}

function classifyQuestion(question) {
  const rules = [
    ['tax_period', /\u043d\u0430\u043b\u043e\u0433\u043e\u0432\u044b\u0439 \u043f\u0435\u0440\u0438\u043e\u0434/i],
    ['profile_mode', /нет точного профиля декларации/i],
    ['residency', /периоды присутствия и отсутствия в России/i],
    ['capacity', /ваш статус за 2025 год/i],
    ['zero_scope', /нет других доходов той же категории/i],
    ['identity', /ИНН и ФИО/i],
    ['filing', /вид декларации за 2025 год/i],
    ['date', /дату подписания декларации/i],
    ['destination', /код налоговой инспекции/i],
    ['signer', /кто подписывает декларацию/i],
    ['budget', /итог декларации для бюджета/i],
    ['oktmo', /код ОКТМО/i],
  ];
  const found = rules.find(([, regex]) => regex.test(question));
  if (!found) throw new Error('visible_question_not_understood');
  return found[0];
}

async function answerQuestion(page, answer) {
  const textarea = page.locator('textarea:visible').last();
  if (answer === true) {
    if (await textarea.count()) throw new Error('confirmation_rendered_as_text_input');
  } else {
    await textarea.waitFor({ state: 'visible', timeout: 10000 });
    await textarea.fill(answer);
  }
  await rememberTurnBoundary(page);
  await page.getByRole('button', { name: 'Подтвердить', exact: true }).last().click();
  await page.getByText(MODAL_TITLE, { exact: true }).waitFor({
    state: 'hidden',
    timeout: 30000,
  });
  return waitForTurn(page);
}

function downloadLinks(page) {
  return page.locator('a', { hasText: 'Скачать XML' });
}

async function runUserLoop({ page, source, truth, outputDir, trace }) {
  await selectNdfl(page);
  await page.locator('input[type=file]').first().setInputFiles(source);
  await page.getByText(path.basename(source), { exact: false }).waitFor({
    state: 'visible',
    timeout: 60000,
  });
  await page.waitForTimeout(7000);
  await sendMessage(page, 'Подготовь 3-НДФЛ по загруженному брокерскому отчёту.');

  const state = {
    taxPeriodSelected: false,
    invalidDate: false,
    invalidInn: false,
    identityDeferred: false,
    wrongDateAccepted: false,
    draftReady: false,
  };
  let firstXmlBody = '';
  for (let step = 0; step < 30; step += 1) {
    const visibleQuestion = await waitForQuestion(page);
    const kind = classifyQuestion(visibleQuestion);
    let answer;
    let expectedRejection = false;
    if (kind === 'tax_period') {
      answer = '2025';
      state.taxPeriodSelected = true;
    } else if (kind === 'residency') {
      answer = `Присутствие: ${truth.present}; отсутствие: ${truth.absent}; причины: нет`;
    } else if (kind === 'capacity') {
      answer = 'Обычное физическое лицо — не ИП и не лицо частной практики';
    } else if (kind === 'zero_scope') {
      answer = true;
    } else if (kind === 'identity' && !state.invalidInn) {
      answer = `Изменить: 123456789012; ${truth.lastName}; ${truth.firstName}; ${truth.middleName}`;
      state.invalidInn = true;
      expectedRejection = true;
    } else if (kind === 'identity' && !state.identityDeferred) {
      answer = 'Позже';
      state.identityDeferred = true;
    } else if (kind === 'identity') {
      answer = `Изменить: ${truth.inn}; ${truth.lastName}; ${truth.firstName}; ${truth.middleName}`;
    } else if (kind === 'filing') {
      answer = 'Первичная декларация';
    } else if (kind === 'date' && !state.invalidDate) {
      answer = '2025-99-99';
      state.invalidDate = true;
      expectedRejection = true;
    } else if (kind === 'date') {
      answer = '2026-08-23';
      state.wrongDateAccepted = true;
    } else if (kind === 'destination') {
      answer = truth.destination;
    } else if (kind === 'signer') {
      answer = 'Подписываю лично';
    } else if (kind === 'budget') {
      answer = 'Налог к уплате';
    } else if (kind === 'oktmo') {
      answer = truth.oktmo;
    }

    const body = await answerQuestion(page, answer);
    const rejected = body.includes('Ответ не принят и не сохранён');
    if (expectedRejection !== rejected) {
      throw new Error(expectedRejection ? 'invalid_answer_was_accepted' : 'valid_answer_was_rejected');
    }
    if (body.includes('Расчётный черновик готов. XML не создан.')) {
      state.draftReady = true;
    }
    if (body.includes('Расчёт остановлен на точной границе методики')) {
      throw new Error('internal_owner_blocker_visible');
    }
    trace.push({
      mode: 'user',
      event: 'question_answered',
      question_family: kind,
      accepted: !rejected,
      intentionally_invalid: expectedRejection,
      deferred: kind === 'identity' && answer === 'Позже',
    });
    if (body.includes('3-НДФЛ XML подготовлен и проверен по XSD.')) {
      firstXmlBody = body;
      break;
    }
    await sendMessage(page, CONTINUE);
  }

  if (!firstXmlBody) throw new Error('first_xml_not_reached');
  if (!state.draftReady) throw new Error('draft_ready_without_xml_not_observed');
  if (!state.taxPeriodSelected || !state.invalidInn || !state.invalidDate || !state.identityDeferred) {
    throw new Error('required_invalid_and_deferred_matrix_incomplete');
  }
  if (!state.wrongDateAccepted) throw new Error('date_correction_predecessor_missing');
  if (!firstXmlBody.includes('Изменить дату')) throw new Error('correction_help_not_visible');

  await sendMessage(page, `Изменить дату: ${truth.declarationDate}`);
  const correctedBody = await waitForTurn(page);
  if (!correctedBody.includes('3-НДФЛ XML подготовлен и проверен по XSD.')) {
    throw new Error('corrected_xml_not_ready');
  }
  const requiredSummarySections = [
    'Из отчёта:',
    'Рассчитано Tax Model и независимо сверено с XML:',
    'Определено по методике резидентства:',
    'Подтверждено вами:',
    'Перед подачей:',
  ];
  if (requiredSummarySections.some((marker) => !correctedBody.includes(marker))) {
    throw new Error('final_user_summary_sections_missing');
  }
  const methodologySection = correctedBody
    .split('Определено по методике резидентства:', 2)[1]
    .split('Подтверждено вами:', 1)[0];
  const userAttestedSection = correctedBody
    .split('Подтверждено вами:', 2)[1]
    .split('Перед подачей:', 1)[0];
  if (
    !/вывод методики/i.test(methodologySection)
    || /подтвержден[а-яё]*/i.test(methodologySection)
  ) {
    throw new Error('residency_methodology_provenance_invalid');
  }
  if (
    !/периоды присутствия и отсутствия/i.test(userAttestedSection)
    || !/специальные причины отсутствия/i.test(userAttestedSection)
    || /статус[^\n.;]{0,80}резидент/i.test(userAttestedSection)
  ) {
    throw new Error('residency_user_attested_provenance_invalid');
  }
  const visibleMatch = correctedBody.match(
    /Рассчитано Tax Model[^:]*:\s*доход\s+([0-9.]+)\s*₽;\s*принятые расходы\s+([0-9.]+)\s*₽;\s*налоговая база\s+([0-9.]+)\s*₽;\s*исчисленный налог\s+([0-9.]+)\s*₽;\s*к уплате\s+([0-9.]+)\s*₽/i,
  );
  if (!visibleMatch) throw new Error('visible_calculation_values_missing');
  const visibleValues = {
    total_income: visibleMatch[1],
    accepted_expenses: visibleMatch[2],
    tax_base: visibleMatch[3],
    calculated_tax: visibleMatch[4],
    tax_payable: visibleMatch[5],
  };
  trace.push({ mode: 'user', event: 'accepted_value_corrected', field: 'declaration_date' });
  trace.push({
    mode: 'user',
    event: 'final_summary_verified',
    required_sections_visible: true,
    methodology_residency_section_visible: true,
    user_residency_evidence_visible: true,
    user_residency_conclusion_absent: true,
    visible_values: visibleValues,
  });

  const links = downloadLinks(page);
  await links.last().waitFor({ state: 'visible', timeout: 60000 });
  const href = await links.last().getAttribute('href');
  if (!href || !href.includes('/content?attachment=true')) {
    throw new Error('private_download_link_invalid');
  }
  const downloadPromise = page.waitForEvent('download', { timeout: 60000 });
  await links.last().click();
  const download = await downloadPromise;
  const xmlPath = path.join(outputDir, '3-ndfl-2025.xml');
  await download.saveAs(xmlPath);
  const xmlBytes = fs.readFileSync(xmlPath);
  if (!xmlBytes.length) throw new Error('downloaded_xml_empty');
  trace.push({
    mode: 'user',
    event: 'private_xml_downloaded',
    bytes: xmlBytes.length,
    sha256: sha256Bytes(xmlBytes),
    private_download_url_sha256: sha256Bytes(href),
    chat_url_sha256: sha256Bytes(page.url()),
  });
  return { href, xmlPath, correctedBody, visibleValues };
}

async function startUnansweredCase({ context, baseUrl, source, screenshotPath }) {
  const page = await context.newPage();
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.locator('#chat-input').waitFor({ state: 'visible', timeout: 60000 });
  await selectNdfl(page);
  await page.locator('input[type=file]').first().setInputFiles(source);
  await page.getByText(path.basename(source), { exact: false }).waitFor({
    state: 'visible',
    timeout: 60000,
  });
  await page.waitForTimeout(7000);
  const started = Date.now();
  await sendMessage(page, 'Подготовь 3-НДФЛ по загруженному брокерскому отчёту.');
  await waitForQuestion(page);
  await page.screenshot({ path: screenshotPath, fullPage: true });
  return { page, elapsedMs: Date.now() - started };
}

async function proveCloseTabDoesNotHoldAdmission({ context, baseUrl, source, outputDir, trace }) {
  const first = await startUnansweredCase({
    context,
    baseUrl,
    source,
    screenshotPath: path.join(outputDir, 'close-tab-first-question.png'),
  });
  await first.page.close();
  const second = await startUnansweredCase({
    context,
    baseUrl,
    source,
    screenshotPath: path.join(outputDir, 'close-tab-second-question.png'),
  });
  if (second.elapsedMs >= 30000) {
    throw new Error('second_case_admission_not_prompt_after_close');
  }
  await second.page.close();
  trace.push({
    mode: 'user',
    event: 'unanswered_tab_closed_and_second_case_admitted',
    first_question_visible: true,
    first_tab_closed_without_answer: true,
    second_case_question_visible: true,
    first_elapsed_ms: first.elapsedMs,
    second_elapsed_ms: second.elapsedMs,
  });
}

async function retryAndResume(page, context, chatUrl, expectedHref, source, trace) {
  await page.reload({ waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.locator('#chat-input').waitFor({ state: 'visible', timeout: 60000 });
  if (!(await page.locator('body').innerText()).includes('Скачать XML')) {
    throw new Error('xml_result_missing_after_reload');
  }
  const resumedHref = await downloadLinks(page).last().getAttribute('href');
  if (resumedHref !== expectedHref) throw new Error('reload_selected_stale_logical_file');
  await page.locator('input[type=file]').first().setInputFiles(source);
  await page.getByText(path.basename(source), { exact: false }).last().waitFor({
    state: 'visible',
    timeout: 60000,
  });
  await page.waitForTimeout(7000);
  await sendMessage(
    page,
    'Я повторно добавил тот же брокерский отчёт. Проверь текущий результат.',
  );
  await waitForTurn(page);
  const reuploadedHref = await downloadLinks(page).last().getAttribute('href');
  if (reuploadedHref !== expectedHref) {
    throw new Error('same_source_reupload_created_new_logical_file');
  }
  const peer = await context.newPage();
  await peer.goto(chatUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await peer.locator('#chat-input').waitFor({ state: 'visible', timeout: 60000 });
  const retryHrefs = await Promise.all([
    (async () => {
      await sendMessage(page, CONTINUE);
      await waitForTurn(page);
      return downloadLinks(page).last().getAttribute('href');
    })(),
    (async () => {
      await sendMessage(peer, CONTINUE);
      await waitForTurn(peer);
      return downloadLinks(peer).last().getAttribute('href');
    })(),
  ]);
  if (retryHrefs.some((href) => href !== expectedHref)) {
    throw new Error('concurrent_retry_selected_stale_logical_file');
  }
  await peer.close();
  await page.reload({ waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.locator('#chat-input').waitFor({ state: 'visible', timeout: 60000 });
  const after = await downloadLinks(page).last().getAttribute('href');
  if (after !== expectedHref) {
    throw new Error('concurrent_retry_created_new_logical_file');
  }
  trace.push({
    mode: 'user',
    event: 'resume_and_concurrent_retry',
    reload_resumed: true,
    same_source_reupload_preserved_logical_file: true,
    logical_download_links_stable: true,
  });
}

async function proveSecondUserDenied(browser, baseUrl, user, fileHref, chatUrl, trace) {
  const context = await browser.newContext();
  const page = await login(context, baseUrl, user);
  if (await page.locator('button[aria-label$="NDFL"]').count()) {
    throw new Error('second_user_can_see_ndfl_model');
  }
  const fileResponse = await page.goto(new URL(fileHref, baseUrl).toString(), {
    waitUntil: 'domcontentloaded',
    timeout: 60000,
  });
  const fileDenied = !fileResponse || [401, 403, 404].includes(fileResponse.status())
    || page.url().includes('/auth');
  if (!fileDenied) throw new Error('second_user_private_file_access_not_denied');
  await page.goto(chatUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
  const chatDenied = !(await page.locator('body').innerText()).includes('Скачать XML');
  if (!chatDenied) throw new Error('second_user_case_access_not_denied');
  trace.push({
    mode: 'user',
    event: 'second_user_denied',
    model_hidden: true,
    private_file_denied: true,
    case_denied: true,
  });
  await context.close();
}

async function runRepresentativeSourceSmoke({ browser, control, source, outputDir }) {
  const context = await browser.newContext();
  const page = await login(context, control.base_url, control.users[0]);
  const sourceArtifact = loadPublicRepresentativeSource(source);
  await selectNdfl(page);
  await page.locator('input[type=file]').first().setInputFiles(sourceArtifact.upload);
  await page.getByText(path.basename(source), { exact: false }).waitFor({
    state: 'visible',
    timeout: 60000,
  });
  await page.waitForTimeout(7000);
  await sendMessage(page, 'Подготовь 3-НДФЛ по загруженному брокерскому отчёту.');
  const body = await waitForTurn(page);
  if (body.includes('3-НДФЛ XML подготовлен') || await downloadLinks(page).count()) {
    throw new Error('representative_source_unjustified_declaration_created');
  }
  if (!/Расчёт остановлен|Подготовка остановлена/.test(body)) {
    throw new Error('representative_source_typed_blocker_not_visible');
  }
  await page.screenshot({
    path: path.join(outputDir, 'representative-source-user-view.png'),
    fullPage: true,
  });
  await context.close();
  return {
    schema_version: 'broker_reports_issue306_safe_interaction_trace_v1',
    source_kind: 'public_representative_broker_report',
    source_artifact: sourceArtifact.receipt,
    browser_ui_only: true,
    hidden_refs_observed: false,
    document_contents_recorded: false,
    events: [{
      mode: 'user',
      event: 'representative_source_blocked_before_declaration',
      xml_created: false,
      private_download_created: false,
      typed_blocker_visible: true,
    }],
  };
}

async function runRepresentativeSourceBoundaryProof({ browser, control, source, outputDir }) {
  const context = await browser.newContext();
  const page = await login(context, control.base_url, control.users[0]);
  const sourceArtifact = loadPublicRepresentativeSource(source);
  await selectNdfl(page);
  await page.locator('input[type=file]').first().setInputFiles(sourceArtifact.upload);
  await page.getByText(path.basename(source), { exact: false }).waitFor({
    state: 'visible',
    timeout: 60000,
  });
  // OpenWebUI renders the file chip before its background extraction has
  // necessarily settled. Keep this browser-only proof behind that visible
  // upload boundary and prove below that the user message was really posted.
  await page.waitForTimeout(20000);
  await sendMessage(
    page,
    '\u041f\u043e\u0434\u0433\u043e\u0442\u043e\u0432\u044c 3-\u041d\u0414\u0424\u041b \u043f\u043e \u0437\u0430\u0433\u0440\u0443\u0436\u0435\u043d\u043d\u043e\u043c\u0443 \u0431\u0440\u043e\u043a\u0435\u0440\u0441\u043a\u043e\u043c\u0443 \u043e\u0442\u0447\u0451\u0442\u0443.',
  );
  const body = await waitForTurn(page);
  const required = [
    'Не удалось получить подтверждённый набор операций',
    'Итог по кейсу:',
    'годы не определены',
    'год ещё не выбран',
    'налоговый период ещё не выбран',
    'подтверждённые позиции пока не сформированы',
    'Рассчитанные закрытые продажи: 0',
    'Подаваемый XML на этом шаге не создан',
  ];
  const missing = required.filter((marker) => !body.includes(marker));
  if (missing.length) {
    throw new Error(
      `representative_source_exact_boundary_receipt_invalid:${missing.join('|')}`,
    );
  }
  const forbidden = [
    'ordinary_trade_canonical_evidence_missing',
    'gate5_source_fact_disposal_missing',
    'UNSUPPORTED_EXACT_YEAR_PROFILE',
    'DECLARATION_XML_READY',
  ];
  if (forbidden.some((marker) => body.includes(marker))) {
    throw new Error('representative_source_internal_state_visible');
  }
  if (await downloadLinks(page).count()) {
    throw new Error('representative_source_unjustified_declaration_created');
  }
  await page.screenshot({
    path: path.join(outputDir, 'representative-source-user-view.png'),
    fullPage: true,
  });
  await context.close();
  return {
    schema_version: 'broker_reports_issue308_safe_interaction_trace_v1',
    source_kind: 'public_representative_broker_report',
    source_artifact: sourceArtifact.receipt,
    browser_ui_only: true,
    hidden_refs_observed: false,
    document_contents_recorded: false,
    events: [{
      mode: 'user',
      event: 'representative_source_boundary_separation_proven',
      source_gap_explained_in_plain_language: true,
      next_action_visible: true,
      internal_status_hidden: true,
      xml_created: false,
      private_download_created: false,
    }],
  };
}

async function runIssue310NonFilingRoute({
  browser,
  control,
  source,
  outputDir,
  route,
}) {
  const expected = {
    open_long: [
      'открытая длинная позиция',
      'в налоговую базу не включена',
      'XML не создан',
    ],
    sale_only: [
      'историю позиции',
      'Добавьте отчёт с предшествующими операциями',
      'XML не создан',
    ],
  }[route];
  if (!expected) throw new Error('issue310_non_filing_route_invalid');
  const context = await browser.newContext();
  const page = await login(context, control.base_url, control.users[0]);
  await selectNdfl(page);
  await page.locator('input[type=file]').first().setInputFiles(source);
  await page.getByText(path.basename(source), { exact: false }).waitFor({
    state: 'visible',
    timeout: 60000,
  });
  await page.waitForTimeout(7000);
  await sendMessage(page, 'Проверь операции и подготовь результат для 3-НДФЛ.');
  const question = await waitForQuestion(page);
  if (classifyQuestion(question) !== 'tax_period') {
    throw new Error('issue310_tax_period_question_not_first');
  }
  const body = await answerQuestion(page, '2025');
  const missing = expected.filter((marker) => !body.includes(marker));
  if (missing.length) {
    throw new Error(`issue310_non_filing_explanation_missing:${missing.join('|')}`);
  }
  if (await downloadLinks(page).count()) {
    throw new Error('issue310_non_filing_route_created_download');
  }
  await page.screenshot({
    path: path.join(outputDir, `issue310-${route}-user-view.png`),
    fullPage: true,
  });
  await context.close();
  return {
    schema_version: 'broker_reports_issue310_safe_interaction_trace_v1',
    route,
    source_sha256: sha256Bytes(fs.readFileSync(source)),
    browser_ui_only: true,
    events: [{
      mode: 'user',
      event: 'non_filing_route_explained',
      first_question: 'tax_period',
      plain_language_explanation: true,
      next_action_visible: true,
      internal_status_hidden: true,
      xml_created: false,
      private_download_created: false,
    }],
  };
}

async function runIssue310UnsupportedProfileRoute({
  browser,
  control,
  source,
  outputDir,
  mode,
}) {
  const modes = {
    analysis: {
      answer: 'Только анализ',
      markers: ['Готов только анализ по выбранному периоду', 'XML не создавались'],
    },
    surrogate: {
      answer: 'Неподаваемый черновик',
      markers: [
        'Неподаваемый черновик (не подлежит подаче)',
        'Выбранный период: 2022',
        '3-НДФЛ за 2025 год',
        'электронный формат 5.20',
        'XML и файл для скачивания не созданы',
      ],
    },
    stop: {
      answer: 'Остановиться и продолжить позже',
      markers: ['Подготовка приостановлена', 'вернуться позже', 'XML не создан'],
    },
  };
  const expected = modes[mode];
  if (!expected) throw new Error('issue310_unsupported_mode_invalid');
  const context = await browser.newContext();
  const page = await login(context, control.base_url, control.users[0]);
  await selectNdfl(page);
  await page.locator('input[type=file]').first().setInputFiles(source);
  await page.getByText(path.basename(source), { exact: false }).waitFor({
    state: 'visible',
    timeout: 60000,
  });
  await page.waitForTimeout(7000);
  await sendMessage(page, 'Подготовь результат за 2022 год по этому отчёту.');
  const periodQuestion = await waitForQuestion(page);
  if (classifyQuestion(periodQuestion) !== 'tax_period') {
    throw new Error('issue310_tax_period_question_not_first');
  }
  await answerQuestion(page, '2022');
  await sendMessage(page, CONTINUE);
  const profileQuestion = await waitForQuestion(page);
  if (classifyQuestion(profileQuestion) !== 'profile_mode') {
    throw new Error('issue310_profile_mode_question_missing');
  }
  for (const marker of ['2022', '3-НДФЛ за 2025 год', '5.20']) {
    if (!profileQuestion.includes(marker)) {
      throw new Error(`issue310_profile_context_missing:${marker}`);
    }
  }
  const body = await answerQuestion(page, expected.answer);
  const missing = expected.markers.filter((marker) => !body.includes(marker));
  if (missing.length) {
    throw new Error(`issue310_unsupported_result_missing:${missing.join('|')}`);
  }
  if (await downloadLinks(page).count()) {
    throw new Error('issue310_unsupported_profile_created_download');
  }
  let periodRoundTrip = false;
  if (mode === 'stop') {
    await sendMessage(page, 'Изменить налоговый период: 2025');
    const supportedBody = await waitForTurn(page);
    if (!supportedBody.includes('для 2025 года доступен точный профиль')) {
      throw new Error('issue310_supported_period_not_visible_after_change');
    }
    const title = page.getByText(MODAL_TITLE, { exact: true });
    if (await title.isVisible()) {
      await page.keyboard.press('Escape');
      await title.waitFor({ state: 'hidden', timeout: 30000 });
    }
    await sendMessage(page, 'Изменить налоговый период: 2022');
    await waitForTurn(page);
    await sendMessage(page, CONTINUE);
    const returnedQuestion = await waitForQuestion(page);
    if (
      classifyQuestion(returnedQuestion) !== 'profile_mode'
      || !returnedQuestion.includes('2022')
    ) {
      throw new Error('issue310_period_round_trip_reused_stale_mode');
    }
    periodRoundTrip = true;
  }
  await page.screenshot({
    path: path.join(outputDir, `issue310-unsupported-${mode}-user-view.png`),
    fullPage: true,
  });
  await context.close();
  return {
    schema_version: 'broker_reports_issue310_safe_interaction_trace_v1',
    route: `unsupported_${mode}`,
    source_sha256: sha256Bytes(fs.readFileSync(source)),
    browser_ui_only: true,
    events: [{
      mode: 'user',
      event: 'unsupported_profile_choice_completed',
      selected_tax_period: '2022',
      available_profile_tax_period: '2025',
      available_profile_format: '5.20',
      selected_mode: mode,
      period_round_trip_2022_2025_2022: periodRoundTrip,
      internal_profile_id_hidden: true,
      xml_created: false,
      private_download_created: false,
    }],
  };
}

(async () => {
  const [statePath, truthPath, sourcePath, outputPath] = process.argv.slice(2);
  if (!statePath || !truthPath || !sourcePath || !outputPath) {
    throw new Error('usage: state truth source output_dir');
  }
  const control = JSON.parse(fs.readFileSync(statePath, 'utf8'));
  if (!Array.isArray(control.users) || control.users.length < 2) {
    throw new Error('bounded_control_users_required');
  }
  const userIndex = Number(process.env.ISSUE310_USER_INDEX || '0');
  if (
    !Number.isInteger(userIndex)
    || userIndex < 0
    || userIndex >= control.users.length
    || userIndex === 1
  ) {
    throw new Error('bounded_visible_proof_user_index_invalid');
  }
  const routeControl = {
    ...control,
    users: [control.users[userIndex], control.users[1]],
  };
  const truth = readTruth(truthPath);
  const startedAt = new Date().toISOString();
  const runId = crypto.randomUUID();
  const proofBinding = loadProofBinding(path.resolve(statePath), control);
  const source = path.resolve(sourcePath);
  const outputDir = path.resolve(outputPath);
  fs.mkdirSync(outputDir, { recursive: true });
  const trace = [];
  const browser = await chromium.launch({ headless: true });
  if (process.env.ISSUE306_SOURCE_SMOKE_ONLY === '1') {
    const safe = await runRepresentativeSourceBoundaryProof({
      browser,
      control: routeControl,
      source,
      outputDir,
    });
    await browser.close();
    const safePath = path.join(outputDir, 'interaction.safe.json');
    const boundSafe = receipt({
      ...safe,
      schema_version: 'broker_reports_issue306_browser_run_receipt_v2',
      run_id: runId,
      run_kind: 'representative_source',
      started_at: startedAt,
      finished_at: new Date().toISOString(),
      proof_binding: proofBinding,
    });
    fs.writeFileSync(safePath, JSON.stringify(boundSafe, null, 2) + '\n', 'utf8');
    process.stdout.write(JSON.stringify({ status: 'blocked_as_expected', safe_trace_path: safePath }));
    return;
  }
  const issue310Route = process.env.ISSUE310_NON_FILING_ROUTE || '';
  if (issue310Route) {
    const safe = await runIssue310NonFilingRoute({
      browser,
      control: routeControl,
      source,
      outputDir,
      route: issue310Route,
    });
    await browser.close();
    const safePath = path.join(outputDir, 'interaction.safe.json');
    const boundSafe = receipt({
      ...safe,
      schema_version: 'broker_reports_issue310_browser_run_receipt_v1',
      run_id: runId,
      run_kind: issue310Route,
      started_at: startedAt,
      finished_at: new Date().toISOString(),
      proof_binding: proofBinding,
    });
    fs.writeFileSync(safePath, JSON.stringify(boundSafe, null, 2) + '\n', 'utf8');
    process.stdout.write(JSON.stringify({ status: 'passed', safe_trace_path: safePath }));
    return;
  }
  const issue310UnsupportedMode = process.env.ISSUE310_UNSUPPORTED_MODE || '';
  if (issue310UnsupportedMode) {
    const safe = await runIssue310UnsupportedProfileRoute({
      browser,
      control: routeControl,
      source,
      outputDir,
      mode: issue310UnsupportedMode,
    });
    await browser.close();
    const safePath = path.join(outputDir, 'interaction.safe.json');
    const boundSafe = receipt({
      ...safe,
      schema_version: 'broker_reports_issue310_browser_run_receipt_v1',
      run_id: runId,
      run_kind: `unsupported_${issue310UnsupportedMode}`,
      started_at: startedAt,
      finished_at: new Date().toISOString(),
      proof_binding: proofBinding,
    });
    fs.writeFileSync(safePath, JSON.stringify(boundSafe, null, 2) + '\n', 'utf8');
    process.stdout.write(JSON.stringify({ status: 'passed', safe_trace_path: safePath }));
    return;
  }
  const context = await browser.newContext({ acceptDownloads: true });
  const page = await login(
    context,
    routeControl.base_url,
    routeControl.users[0],
  );
  if (process.env.ISSUE306_CLOSE_TAB_PROOF === '1') {
    await proveCloseTabDoesNotHoldAdmission({
      context,
      baseUrl: routeControl.base_url,
      source,
      outputDir,
      trace,
    });
  }
  const result = await runUserLoop({ page, source, truth, outputDir, trace });
  const chatUrl = page.url();
  await retryAndResume(page, context, chatUrl, result.href, source, trace);
  await proveSecondUserDenied(
    browser,
    routeControl.base_url,
    routeControl.users[1],
    result.href,
    chatUrl,
    trace,
  );
  await page.screenshot({ path: path.join(outputDir, 'final-user-view.png'), fullPage: true });
  await context.close();
  await browser.close();

  const safe = receipt({
    schema_version: 'broker_reports_issue306_browser_run_receipt_v2',
    run_id: runId,
    run_kind: 'clean_room',
    started_at: startedAt,
    finished_at: new Date().toISOString(),
    proof_binding: proofBinding,
    source_kind: 'synthetic_supported_fixture',
    browser_ui_only: true,
    hidden_refs_observed: false,
    document_contents_recorded: false,
    developer_intervention_during_user_run: false,
    events: trace,
  });
  fs.writeFileSync(
    path.join(outputDir, 'interaction.safe.json'),
    JSON.stringify(safe, null, 2) + '\n',
    'utf8',
  );
  process.stdout.write(JSON.stringify({
    status: 'passed',
    xml_path: result.xmlPath,
    safe_trace_path: path.join(outputDir, 'interaction.safe.json'),
  }));
})().catch((error) => {
  process.stderr.write(String(error && error.stack ? error.stack : error));
  process.exit(1);
});
