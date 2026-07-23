# Broker Reports — Native UI Private Intake Correction

Date: 2026-07-23

Branch: `codex/broker-reports-native-ui-private-intake-correction-v1`

Implementation status: `PASSED`

Live release status: `PENDING_AFTER_MERGE`

## Trigger

The first native browser audit proved that the OpenWebUI attachment control
sent a Broker Reports PDF through ordinary `/api/v1/files/` processing and the
visible button called the proof-only global normalizer Action. Native document
processing created a vector collection before cleanup, while the UI displayed
a completed state.

Primary trigger evidence:
[browser audit](./BROKER_REPORTS_NATIVE_BROWSER_CLICKTHROUGH_NOT_CLOSED.report.md).

## Narrow correction

Only the deployed static loader and its maintained contract tests changed.

For a supported Broker Reports document selected with the existing OpenWebUI
attachment input, the loader now:

1. preserves the native `FormData` selected by the user;
2. routes it to the existing server-authoritative
   `/api/v1/broker-reports/intake`;
3. attaches a fresh, stable-per-File `Idempotency-Key`;
4. adapts the safe private-intake response to the attachment response shape
   expected by OpenWebUI;
5. retains the reserved private source id;
6. exposes a visible `Broker Reports` button;
7. invokes only
   `/api/chat/actions/broker_reports_private_intake_action`.

The legacy `broker_reports_gate1_normalizer_action` no longer appears in this
UI route. No extraction, receipt validation or document-domain decision moved
into the browser; the loader emits user intent and renders server outcomes.

Unchanged:

- private-intake server contract and Action;
- Gate 1 and Gate 2 Functions;
- semantic JSON `description + rows`;
- Gemini master and provider policies;
- prompts, crops, OCR and parsing;
- ArtifactStore and answer-context contracts;
- Knowledge/RAG/vector prohibition.

## UI integrity

Primary action: verify the attached Broker Reports source before processing.

States:

- empty: no button when no supported attached source exists;
- ready: private intake accepted and ready to verify;
- loading: button disabled, busy cursor and visible verification status;
- success: verified source and explicit next step;
- error: visible stable error text and re-enabled retry button.

The button is a semantic `button`, has keyboard focus styling, exposes a
descriptive title and cannot be double-clicked while busy. Every click has
immediate and terminal feedback.

UI integrity status: `PASS`.

## Verification

Focused loader/private-intake/Gate 1 tests:

```text
63 passed
```

Complete Stage2 STT/loader suite:

```text
108 passed
0 failed
```

Complete Broker Reports service suite:

```text
collected: 1154
passed: 1134
failed: 0
skipped: 20
xfailed/xpassed: 0
warnings: 5
duration: 91.72 s
```

All skips are the declared offline private benchmark cases.

Additional checks:

- loader JavaScript syntax: passed;
- Ruff on changed Python test: passed;
- repository privacy guard: `3 passed` within the full suite;
- `git diff --check`: passed.

## Real browser behavioral proof before release

Playwright served the corrected local loader in place of `/static/loader.js`
while using the real live OpenWebUI UI and backend.

- real UI file input used: yes;
- upload route: `/api/v1/broker-reports/intake`;
- upload status: `200`;
- reserved private source id: yes;
- visible Action clicked: yes;
- protected private-intake Action status: `200`;
- legacy Action invoked: no;
- visible states: ready, running, completed;
- answer run started: no;
- test source cleanup status: `200`;
- Knowledge/RAG/vector delta: `0`;
- all eight runtime counters equal to baseline: yes.

Private behavioral receipt SHA-256:
`7292e1f6e22307ff3e97cbf8485edff1e1c70c021b0d4798357d26ac6bb6b2b5`.

No screenshot, DOM dump, source path, customer value or provider response was
persisted.

## Deterministic delivery identities

Two consecutive Function bundle generations were byte-identical and unchanged:

| Artifact | SHA-256 |
|---|---|
| Gate 1 Function bundle | `a042ff14d0bc26a4c207db9b49d10ca3be4e3b2483e60e21a479e1e8f2f70519` |
| Gate 2 source Function bundle | `a6df7853e7cf40676fd4483feeac0d8d136b2121967e6f0df39f8d85324df32a` |
| Gate 2 domain Function bundle | `1bb11d428cb9082edec388109839e7f2f3117447daefe9470129bc2413ed1499` |
| Corrected loader | `5d9d7acef0c7206bc2e5f65624a14b794437d40d1e2a2ff81286cba800223d7f` |

Stage mutation in this implementation branch: `0`.

After merge, the exact approved `main` revision must be atomically released
with rollback/readback proof before the browser clickthrough is repeated.
