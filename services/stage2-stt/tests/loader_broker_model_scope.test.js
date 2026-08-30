const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const loaderPath = path.resolve(
  __dirname,
  '../../../deploy/openwebui-static/loader.js'
);
const loaderSource = fs.readFileSync(loaderPath, 'utf8');

const brokerSourceId = 'br-00000000-0000-4000-8000-000000000001';
const declarationMetadataSourceId = 'br-dm-00000000-0000-4000-8000-000000000002';
function deferred() {
  let resolve;
  const promise = new Promise((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function modelCatalog() {
  return [
    {
      id: 'test',
      name: 'Broker Reports user-friendly alias',
      info: { base_model_id: 'broker_reports_gate1_pipe', meta: {} },
    },
    {
      id: 'deepseek-chat',
      name: 'DeepSeek',
      info: { base_model_id: null, meta: {} },
    },
  ];
}

function memoryStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem: (key) => (values.has(key) ? values.get(key) : null),
    key: (index) => Array.from(values.keys())[index] ?? null,
    get length() {
      return values.size;
    },
    removeItem: (key) => values.delete(key),
    setItem: (key, value) => values.set(key, String(value)),
  };
}

class FakeElement {
  constructor(tagName) {
    this.tagName = String(tagName).toUpperCase();
    this.dataset = {};
    this.style = {};
    this.children = [];
    this.attributes = new Map();
    this.listeners = new Map();
    this.disabled = false;
    this.files = [];
    this.isConnected = true;
    this.removed = false;
  }

  addEventListener(type, callback, options = {}) {
    const listeners = this.listeners.get(type) ?? [];
    listeners.push({ callback, once: options?.once === true });
    this.listeners.set(type, listeners);
  }

  append(...children) {
    this.children.push(...children);
  }

  appendChild(child) {
    this.children.push(child);
    return child;
  }

  async emit(type) {
    const listeners = [...(this.listeners.get(type) ?? [])];
    for (const listener of listeners) {
      await listener.callback({ preventDefault() {}, stopPropagation() {} });
      if (listener.once) {
        this.listeners.set(
          type,
          (this.listeners.get(type) ?? []).filter((item) => item !== listener)
        );
      }
    }
  }

  click() {
    return this.emit('click');
  }

  focus() {}

  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }

  querySelector() {
    return null;
  }

  querySelectorAll() {
    return [];
  }

  remove() {
    this.removed = true;
    this.isConnected = false;
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
}

function loaderRuntime(selectedModels, options = {}) {
  const calls = [];
  const catalog = modelCatalog();
  if (options.brokerName) {
    catalog[0].name = options.brokerName;
  }
  if (options.duplicateBrokerName) {
    catalog.push({
      id: 'ordinary-model-with-duplicate-name',
      name: catalog[0].name,
      info: { base_model_id: null, meta: {} },
    });
  }
  const sessionStorage = memoryStorage(
    selectedModels === null
      ? {}
      : { selectedModels: JSON.stringify(selectedModels) }
  );
  let modelLabels = [...(options.modelLabels ?? [])];
  const animationFrames = [];
  const mutationCallbacks = [];
  const brokerPanels = [];
  const metadataPanels = [];
  let lastFilePicker = null;
  const messageInputRoot = {
    appendChild: (element) => {
      if (element.dataset?.declarationMetadataPanel === '1') {
        metadataPanels.push(element);
      }
    },
    querySelector: (selector) => {
      if (selector === '[data-broker-gate1-composer-panel="1"]') {
        return brokerPanels.find((panel) => !panel.removed) ?? null;
      }
      if (selector === '[data-declaration-metadata-panel="1"]') {
        return metadataPanels.find((panel) => !panel.removed) ?? null;
      }
      return null;
    },
    querySelectorAll: (selector) => {
      if (selector.includes('[data-broker-gate1-panel="1"]')) {
        return [
          ...brokerPanels.filter((panel) => !panel.removed),
          ...metadataPanels.filter((panel) => !panel.removed),
        ];
      }
      return [];
    },
  };
  const originalFetch = async (input, init) => {
    const url = String(input && input.url ? input.url : input);
    calls.push({ input, init, url });
    if (url === '/api/models') {
      return new Response(JSON.stringify({ data: catalog }), {
        status: options.modelsStatus ?? 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    if (url === '/static/stage2-stt-normalization.json') {
      return Response.json({});
    }
    if (url === '/api/v1/broker-reports/intake') {
      return Response.json({
        source_id: brokerSourceId,
        size_bytes: 4,
      });
    }
    if (url === '/api/v1/broker-reports/declaration-metadata-intake') {
      if (options.metadataResponsePromise) {
        return options.metadataResponsePromise;
      }
      return Response.json(options.metadataPayload ?? {
        schema_version: 'broker_reports_declaration_metadata_receipt_v2',
        source_id: declarationMetadataSourceId,
        source_sha256: 'a'.repeat(64),
        slot_checksum: 'b'.repeat(64),
        size_bytes: 4,
        intake_slot: 'DECLARATION_METADATA_INPUT',
        slot_owner: 'SERVER_FIXED_DECLARATION_METADATA_INTAKE_V2',
      }, { status: options.metadataStatus ?? 200 });
    }
    if (url.includes('/api/v1/files/')) {
      return Response.json({
        id: 'native-file-id',
        filename: 'statement.pdf',
        meta: { content_type: 'application/pdf', size: 4 },
      });
    }
    return Response.json({});
  };
  const window = {
    __stage2SttFetchPatched: false,
    crypto: { randomUUID: () => '00000000-0000-4000-8000-000000000000' },
    fetch: originalFetch,
    location: {
      origin: 'https://openwebui.test',
      pathname: '/',
      search: '',
    },
    requestAnimationFrame: (callback) => {
      animationFrames.push(callback);
      return animationFrames.length;
    },
    sessionStorage,
    localStorage: memoryStorage(),
  };
  const document = {
    addEventListener: () => {},
    createElement: (tagName) => {
      const element = new FakeElement(tagName);
      if (String(tagName).toLowerCase() === 'input') {
        lastFilePicker = element;
      }
      return element;
    },
    documentElement: {},
    querySelector: (selector) => (
      selector === '#message-input-container' ? messageInputRoot : null
    ),
    querySelectorAll: (selector) => {
      if (selector === 'button[id^="model-selector-"][aria-haspopup="listbox"]') {
        return modelLabels.map((label, index) => ({
          id: `model-selector-${index}-button`,
          innerText: label,
          textContent: label,
        }));
      }
      return [];
    },
    readyState: options.observeUi ? 'complete' : 'loading',
  };
  const context = {
    Blob,
    File,
    FormData,
    Headers,
    InputEvent: class InputEvent {},
    MutationObserver: class MutationObserver {
      constructor(callback) {
        mutationCallbacks.push(callback);
      }

      observe() {}
    },
    Request,
    Response,
    URL,
    URLSearchParams,
    clearTimeout,
    console,
    document,
    navigator: {},
    setTimeout,
    window,
  };
  Object.defineProperty(context, 'fetch', {
    configurable: true,
    get: () => window.fetch,
    set: (value) => {
      window.fetch = value;
    },
  });
  vm.runInNewContext(loaderSource, context, { filename: loaderPath });
  return {
    calls,
    flushScans: async () => {
      while (animationFrames.length) {
        const callback = animationFrames.shift();
        await callback();
      }
    },
    seedBrokerUi: () => {
      const panel = {
        removed: false,
        remove() {
          this.removed = true;
        },
      };
      brokerPanels.push(panel);
      return panel;
    },
    metadataButton: () => (
      metadataPanels.find((panel) => !panel.removed)?.children[0] ?? null
    ),
    metadataStatus: () => (
      metadataPanels.find((panel) => !panel.removed)?.children[1] ?? null
    ),
    lastFilePicker: () => lastFilePicker,
    setModelLabels: (labels) => {
      modelLabels = [...labels];
      for (const callback of mutationCallbacks) {
        callback([]);
      }
    },
    setSelectedModels: (ids) => sessionStorage.setItem('selectedModels', JSON.stringify(ids)),
    window,
  };
}

function documentUpload(name = 'statement.pdf', type = 'application/pdf') {
  const body = new FormData();
  body.append('file', new File(['safe'], name, { type }));
  return body;
}

async function upload(window, name, type) {
  return window.fetch('/api/v1/files/', {
    method: 'POST',
    body: documentUpload(name, type),
  });
}

function uploadRoutes(calls) {
  return calls
    .filter(({ init }) => String(init?.method ?? 'GET').toUpperCase() === 'POST')
    .map(({ url }) => url)
    .filter((url) => [
      '/api/v1/files/',
      '/api/v1/broker-reports/intake',
      '/api/v1/broker-reports/declaration-metadata-intake',
    ].includes(url));
}

test('Workspace Model backed by the Broker Gate 1 Pipe uses private intake', async () => {
  const { calls, window } = loaderRuntime(['test']);

  const response = await upload(window);
  const payload = await response.json();

  assert.deepEqual(uploadRoutes(calls), ['/api/v1/broker-reports/intake']);
  assert.equal(payload.id, brokerSourceId);
  const intake = calls.find(({ url }) => url === '/api/v1/broker-reports/intake');
  assert.match(intake.init.headers.get('Idempotency-Key'), /^broker-ui-/);
});

test('NDFL metadata action sends one file to the fixed endpoint', async () => {
  const runtime = loaderRuntime(['test'], { observeUi: true });
  await runtime.flushScans();

  const button = runtime.metadataButton();
  const status = runtime.metadataStatus();
  assert.ok(button);
  assert.equal(button.tagName, 'BUTTON');
  assert.equal(button.getAttribute('aria-busy'), 'false');
  assert.equal(status.getAttribute('role'), 'status');
  await button.emit('click');
  const picker = runtime.lastFilePicker();
  picker.files = [new File(['safe'], 'details.pdf', { type: 'application/pdf' })];
  await picker.emit('change');

  const call = runtime.calls.find(
    ({ url }) => url === '/api/v1/broker-reports/declaration-metadata-intake'
  );
  assert.ok(call);
  assert.deepEqual(Array.from(call.init.body.keys()), ['file']);
  assert.deepEqual(Array.from(call.init.headers.keys()), ['idempotency-key']);
  assert.match(
    call.init.headers.get('Idempotency-Key'),
    /^declaration-metadata-ui-/
  );
  assert.equal(button.disabled, false);
  assert.equal(button.getAttribute('aria-busy'), 'false');
  assert.equal(status.dataset.declarationMetadataStatus, 'success');
  assert.match(status.textContent, /details\.pdf/);
});

test('cancelled metadata picker leaves the next ordinary upload unchanged', async () => {
  const runtime = loaderRuntime(['test'], { observeUi: true });
  await runtime.flushScans();

  await runtime.metadataButton().emit('click');
  await runtime.lastFilePicker().emit('change');
  await upload(runtime.window, 'statement.pdf', 'application/pdf');

  assert.deepEqual(uploadRoutes(runtime.calls), [
    '/api/v1/broker-reports/intake',
  ]);
});

test('model switch while picker is open blocks fixed metadata intake', async () => {
  const runtime = loaderRuntime(['test'], { observeUi: true });
  await runtime.flushScans();

  await runtime.metadataButton().emit('click');
  const picker = runtime.lastFilePicker();
  runtime.setSelectedModels(['deepseek-chat']);
  picker.files = [new File(['safe'], 'details.pdf', { type: 'application/pdf' })];
  await picker.emit('change');

  assert.deepEqual(uploadRoutes(runtime.calls), []);
  assert.equal(
    runtime.metadataStatus().dataset.declarationMetadataStatus,
    'error'
  );
});

test('metadata action stays disabled while loading and rejects a second click', async () => {
  const response = deferred();
  const runtime = loaderRuntime(['test'], {
    observeUi: true,
    metadataResponsePromise: response.promise,
  });
  await runtime.flushScans();

  const button = runtime.metadataButton();
  await button.emit('click');
  const picker = runtime.lastFilePicker();
  picker.files = [new File(['safe'], 'details.pdf', { type: 'application/pdf' })];
  const pending = picker.emit('change');
  await Promise.resolve();
  await Promise.resolve();

  assert.equal(button.disabled, true);
  assert.equal(button.getAttribute('aria-busy'), 'true');
  const originalPicker = runtime.lastFilePicker();
  await button.emit('click');
  assert.equal(runtime.lastFilePicker(), originalPicker);

  response.resolve(Response.json({
    schema_version: 'broker_reports_declaration_metadata_receipt_v2',
    source_id: declarationMetadataSourceId,
    source_sha256: 'a'.repeat(64),
    slot_checksum: 'b'.repeat(64),
    size_bytes: 4,
    intake_slot: 'DECLARATION_METADATA_INPUT',
    slot_owner: 'SERVER_FIXED_DECLARATION_METADATA_INTAKE_V2',
  }));
  await pending;
  assert.equal(button.disabled, false);
});

test('malformed metadata receipt is shown as error, never success', async () => {
  const runtime = loaderRuntime(['test'], {
    observeUi: true,
    metadataPayload: { source_id: declarationMetadataSourceId },
  });
  await runtime.flushScans();

  await runtime.metadataButton().emit('click');
  const picker = runtime.lastFilePicker();
  picker.files = [new File(['safe'], 'details.pdf', { type: 'application/pdf' })];
  await picker.emit('change');

  assert.equal(
    runtime.metadataStatus().dataset.declarationMetadataStatus,
    'error'
  );
  assert.doesNotMatch(runtime.metadataStatus().textContent, /added|добавлен/i);
});

test('display alias does not control Broker Gate 1 ownership', async () => {
  const { calls, window } = loaderRuntime(null, {
    brokerName: 'Renamed display alias',
    modelLabels: ['Renamed display alias'],
  });

  await upload(window);

  assert.deepEqual(uploadRoutes(calls), ['/api/v1/broker-reports/intake']);
});

test('ordinary model preserves the native OpenWebUI document upload', async () => {
  const { calls, window } = loaderRuntime(['deepseek-chat']);

  const response = await upload(window);
  const payload = await response.json();

  assert.deepEqual(uploadRoutes(calls), ['/api/v1/files/']);
  assert.equal(payload.id, 'native-file-id');
});

test('declared Broker document formats share the same model boundary', async () => {
  const broker = loaderRuntime(['test']);
  const native = loaderRuntime(['deepseek-chat']);
  const documents = [
    ['statement.pdf', 'application/pdf'],
    ['operations.csv', 'text/csv'],
    ['operations.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
    ['statement.html', 'text/html'],
  ];

  for (const [name, type] of documents) {
    await upload(broker.window, name, type);
    await upload(native.window, name, type);
  }

  assert.deepEqual(uploadRoutes(broker.calls), documents.map(() => '/api/v1/broker-reports/intake'));
  assert.deepEqual(uploadRoutes(native.calls), documents.map(() => '/api/v1/files/'));
});

test('model switching changes routing in both directions without stale scope', async () => {
  const { calls, setSelectedModels, window } = loaderRuntime(['deepseek-chat']);

  await upload(window);
  setSelectedModels(['test']);
  await upload(window);
  setSelectedModels(['deepseek-chat']);
  await upload(window);

  assert.deepEqual(uploadRoutes(calls), [
    '/api/v1/files/',
    '/api/v1/broker-reports/intake',
    '/api/v1/files/',
  ]);
});

test('native OpenWebUI selector owns routing and removes Broker UI after a model switch', async () => {
  const runtime = loaderRuntime(null, {
    modelLabels: ['Broker Reports user-friendly alias'],
    observeUi: true,
  });

  await runtime.flushScans();
  assert.ok(runtime.metadataButton());
  await upload(runtime.window);
  const cardPanel = runtime.seedBrokerUi();
  const composerPanel = runtime.seedBrokerUi();

  runtime.setModelLabels(['DeepSeek']);
  await runtime.flushScans();
  await upload(runtime.window);

  assert.deepEqual(uploadRoutes(runtime.calls), [
    '/api/v1/broker-reports/intake',
    '/api/v1/files/',
  ]);
  assert.equal(cardPanel.removed, true);
  assert.equal(composerPanel.removed, true);
  assert.equal(runtime.metadataButton(), null);
});

test('mixed-model selection fails closed to native OpenWebUI upload', async () => {
  const { calls, window } = loaderRuntime(['test', 'deepseek-chat']);

  await upload(window);

  assert.deepEqual(uploadRoutes(calls), ['/api/v1/files/']);
});

test('ambiguous display alias fails closed to native OpenWebUI upload', async () => {
  const { calls, window } = loaderRuntime(null, {
    duplicateBrokerName: true,
    modelLabels: ['Broker Reports user-friendly alias'],
  });

  await upload(window);

  assert.deepEqual(uploadRoutes(calls), ['/api/v1/files/']);
});

test('unavailable model catalog fails closed to native OpenWebUI upload', async () => {
  const { calls, window } = loaderRuntime(null, {
    modelLabels: ['Broker Reports user-friendly alias'],
    modelsStatus: 503,
  });

  await upload(window);

  assert.deepEqual(uploadRoutes(calls), ['/api/v1/files/']);
});
