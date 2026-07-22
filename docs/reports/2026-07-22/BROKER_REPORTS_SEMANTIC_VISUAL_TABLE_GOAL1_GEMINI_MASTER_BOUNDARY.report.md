# Broker Reports Semantic Visual Table Goal 1 Report

Date: 2026-07-22

Status: `GOAL_1_GEMINI_MASTER_BOUNDARY: COMPLETED`

## Outcome

The maintained visual-table runtime now asks the model only for semantic table
content: `description` and `rows`. The work refactors the existing provider and
runtime factories; it creates no new provider stack, crop pipeline, storage
subsystem, review framework, or Markdown dependency.

## Acceptance evidence

- `GEMINI_MASTER_DEFAULT: PASSED` — the default provider order contains only
  Gemini and the selected provider is Gemini after a valid response.
- `GEMINI_ATTEMPTS_PER_OPERATION: ONE` — execution records require attempt one
  and empty attempt lineage; there is no runtime retry loop.
- `HIDDEN_RETRIES: ZERO` — runtime and provider contracts remain fail-closed.
- `DEFAULT_OPENAI_CALLS_AFTER_VALID_GEMINI: ZERO` — the default factory does not
  construct the OpenAI adapter and tests observe zero OpenAI qualification,
  count, and generation calls.
- `OPENAI_FALLBACK_POLICY: EXPLICIT_AND_VERSIONED` — OpenAI is allowed only by
  `pdf_semantic_vlm_openai_policy_v1` as explicit fallback or diagnostic
  control.
- `PROVIDER_OUTPUT_MERGE: ZERO` — fallback retains OpenAI identity; diagnostic
  control cannot overwrite valid Gemini; no comparison or merge is performed.
- `SEMANTIC_RESPONSE_PARSE: STRICT` — extra fields, malformed rows, and invalid
  cell types remain terminal; application code returns a deep copy without
  repair or normalization.
- `MODEL_SYSTEM_METADATA_FIELDS: ZERO` — the model view contains only the task;
  the closed response schema contains only `description` and `rows`.

## Boundary and compatibility

The runtime reuses the immutable crop identity, native transports, credential
resolver, provider profiles, and execution metadata. System lineage and
provider metadata are added after the response by application code. Logical
grid materialization is deliberately deferred to Goal 2.

The historical dual-provider geometric decision validator is isolated as a
read-only compatibility contract for existing review evidence. The maintained
semantic runtime does not import the legacy canonical-table model contract.

## Verification

- Ruff: passed for all changed Python files.
- Python compile: passed for changed packages and entrypoints.
- Focused provider/runtime/contract/review/release tests: passed.
- Full service suite: 1049 passed, 20 skipped. The five warnings are existing
  SWIG deprecation warnings.
- Future Gate 1, Gate 2, and Gate 2 Domain bundles: rendered and loaded from
  maintained source in memory under the closed module order.
- Generated bundle and stage files: unchanged by design until Goal 7.
- New production dependencies: zero.
