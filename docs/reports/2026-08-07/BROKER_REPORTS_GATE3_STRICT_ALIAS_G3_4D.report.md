# Broker Reports G3.4D strict labeling output contract and live closeout

Status: `PARTIALLY_COMPLETED_INACTIVE_LIVE_BLOCKED`

Date: 2026-08-07

## Outcome

The proven G3.4C defect was fixed at the model-facing contract boundary only.
The existing response schema still owns `^t[0-9]{3,}$` and now describes the
field as an exact bare alias: `[t123]` in the document means JSON value `t123`.
Instruction `broker-reports-bounded-semantic-labeling@1.0.1` repeats that rule
in two short sentences. The existing validator was not relaxed and contains no
bracket stripping, Markdown stripping, regex extraction or best-effort parser.

The mandatory live closeout is not proven. Three clean execution preflights
stopped before transport with `exact_model_not_published`. An independent
eight-read model-catalog probe observed the exact approved Gemini model in
seven reads and absent in one, demonstrating an unstable OpenWebUI catalog.
Provider submissions and responses were both zero. No unapproved model,
alternate provider, retry, fallback or route change was used.

Consequently `GOAL_G3_4D = PARTIALLY_COMPLETED`,
`STRICT_ALIAS_CONTRACT = NOT_PROVEN` at the required live boundary, and
`G3_4_STATUS = NOT_READY`.

## Minimal implementation

The canonical response schema adds only one `description`; its regex and
response shape are unchanged. The current Gemini adapter preserves that exact
description only for the existing Gate 3 request profile. This is necessary
because Gemini documents `description` as supported model guidance but does
not list string `pattern` in its supported structured-output subset. The
canonical pattern remains enforced by the deterministic validator. See the
[official Gemini structured-output contract](https://ai.google.dev/gemini-api/docs/generate-content/structured-output?hl=en).

No alias values are enumerated in schema. Membership remains a post-response
exact lookup against the current chunk mapping. The dictionary, nine labels,
G3.4B module/hash, 60,000-character bound, context envelope, batching, merge,
canonical targets and financial semantics are unchanged.

## Deterministic contract evidence

The local seam proves:

- known bare alias plus known label: accepted;
- unknown bare alias: rejected as unknown;
- unknown label: rejected as unknown;
- `[t001]`, `` `t001` ``, `target=t001`, `alias: t001` and `<t001>`:
  rejected as contract-invalid;
- duplicate pairs, malformed JSON and unexpected fields: rejected;
- dictionary is injected exactly once;
- provider-visible Gemini schema retains the exact canonical description and
  contains no alias enum;
- no alias normalizer, parser or repair branch exists.

The complete matrix is in
[negative contract evidence](../../stage2/research/g3_4d/02_negative_contract_matrix.safe.csv).

## Frozen live plan and blocker

The frozen plan contained exactly two sequential calls:

1. the complete one-chunk compact document that failed in G3.4C;
2. the already proven large-CSV chunk 3 as a bounded regression.

Both selected shapes reproduced the G3.4C character counts, target counts and
row boundaries before transport. Previously adjudicated positive specimens for
`ACCRUED_COUPON_COMPONENT` and `SECURITIES_LENDING_INCOME` were not available
in the active authorized canonical store, so both remain `NOT_MEASURED` and no
synthetic evidence was created.

The three stopped preflights each preserved the exact instruction, dictionary,
canonical response schema and selected chunks outside Git. They do not contain
a final live provider input, raw model output or validation result because the
stop occurred before client transport. Therefore
`EXACT_MODEL_EVIDENCE = PARTIAL`.

## Verification

- targeted Ruff: passed;
- Gate 3 contract, projection, chunking, dictionary, labeling, batching,
  strict-live-plan and model-client tests: 86 passed;
- architecture and KT1 guards after deterministic bundle rebuild: 47 passed,
  with one unrelated existing deprecation warning;
- compile, CLI load, schema-copy/hash, frozen G3.4B hash, generated bundle
  parity and closed-world projections: passed;
- local tests use the real schema, adapter, validator, chunker and batch core;
  only the external network boundary is substituted.

## Evidence and privacy

- [safe receipt](./BROKER_REPORTS_GATE3_STRICT_ALIAS_G3_4D.receipt.safe.json);
- [exact public contract fragment](../../stage2/research/g3_4d/01_strict_alias_contract.safe.md);
- [live blocker](../../stage2/research/g3_4d/03_live_blocker.safe.json);
- [private evidence manifest](../../stage2/research/g3_4d/PRIVATE_EVIDENCE_MANIFEST_G3_4D.safe.json).

Each of the three non-Git preflight evidence sets contains eight files and
734,743 bytes; each manifest file has SHA-256
`e976f24ac2f830ff066b56aced7b5178b25c817b02be2df4ecb2f6056a67e446`.
No customer values, document IDs, canonical IDs, raw payloads or private paths
are present in safe evidence.

## KISS check

1. Only the observed decorated-alias ambiguity was addressed: `YES`.
2. Alias normalizer or repair added: `NO`.
3. Second alias grammar owner added: `NO`.
4. Current aliases enumerated in schema: `NO`.
5. Chunking, dictionary, semantics or merge changed: `NO`.
6. One-sentence fix: the model is told to return exactly bare alias `t123`,
   and every other value remains rejected.

The architecture remains one schema, one instruction owner, the existing
provider adapter, the existing validator and the existing batch coordinator.

## Required closeout fields

```text
GOAL_G3_4D = PARTIALLY_COMPLETED
STRICT_ALIAS_CONTRACT = NOT_PROVEN
PREVIOUSLY_FAILED_COMPACT_CASE = NOT_RUN
LIVE_CHUNK_REGRESSION = NOT_RUN
ALIAS_REPAIR_LAYER = NONE
ALIAS_AUTHORITY_COUNT = 1
COMPLETE_REAL_DOCUMENT = NOT_PROVEN
ACCRUED_COUPON_POSITIVE = NOT_MEASURED
SECURITIES_LENDING_POSITIVE = NOT_MEASURED
SEMANTIC_FAILURES = NOT_MEASURED_NO_LIVE_OUTPUT
EXACT_MODEL_EVIDENCE = PARTIAL
G3_4_STATUS = NOT_READY
KISS_CHECK = PASS_FOR_IMPLEMENTATION__LIVE_ACCEPTANCE_BLOCKED
NEXT_ALLOWED_GOAL = G3.5_AFTER_HUMAN_REVIEW
```

The next-goal name does not authorize transition while G3.4 is not ready.
G3.5 was not started.
