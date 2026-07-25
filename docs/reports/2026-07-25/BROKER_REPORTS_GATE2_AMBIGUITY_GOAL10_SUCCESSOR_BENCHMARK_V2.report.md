# Broker Reports — Gate 2 ambiguity discipline, Goal 10

Дата: 2026-07-25

Статус: `COMPLETED`

## Outcome

Создан и заморожен successor benchmark v2 для exact ambiguity-discipline
stack:

- deterministic scope v2;
- typed admission v1;
- bounded source context v2;
- model input/prompt/provider projection v3;
- Financial Evidence decision/materializer v1;
- product-invariant comparator;
- artifact family v2.

Local Q0/Q1 proof проходит без provider calls.

До live-квалификации подготовлен отдельный fail-closed harness v2. Он
использует versioned request profile
`financial_evidence_successor_qualification_v2` и не меняет сохранённый
qualification harness v1.

## Frozen benchmark

- ID: `gate2_financial_successor_v2`;
- schema:
  `broker_reports_gate2_financial_successor_fixture_manifest_v2`;
- cases: `12`;
- customer data: `false`;
- manifest SHA-256:
  `430bea21d0a36e993bc50184d971f36dfc75a1d2be12bcf5e43fba7436797d66`.

Required families:

- uniquely typed;
- multiple compatible types;
- explicit no Registry type;
- missing discriminating evidence;
- sufficient discriminating evidence;
- repeated header;
- detail vs subtotal;
- adjacent equal values;
- adjacent FX values;
- optional missing dimensions;
- forbidden neighbouring refs;
- unsupported shape.

## Local Q0/Q1 proof

Q0:

- scope v2 deterministic;
- typed-admission integrity validated;
- source-context v2 integrity validated;
- model-input v3 exact;
- provider projection v3 exact;
- canonical branch validation retained;
- deterministic materialization/context;
- explicit compatibility read;
- complete coverage;
- all negative checks fail closed.

Q1:

- required families: `12/12`;
- typed available scopes: `4`;
- typed absent scopes: `8`;
- over-typing negative tests: `6/6`;
- unsafe typed branches: `0`;
- post-response conversion: `0`.

Terminal dispositions:

- `typed_input`: `4`;
- `unclassified_financial_input`: `6`;
- `no_financial_input`: `1`;
- `unsupported`: `1`.

Product invariants:

- source literals: `47/47`;
- literal loss: `0`;
- inventions: `0`;
- duplicate bindings: `0`;
- cross-scope bindings: `0`;
- terminal ownership gaps: `0`;
- forbidden neighbouring refs admitted: `0/4`;
- unaccounted source refs: `0`.

Exact local proof receipt SHA-256:
`ab1084d52a007d79c5c2f0dfa6731ccc4de95a583d16a62383eaf07662dc7dca`.

## Artifact family v2

New identities:

- `broker_reports_gate2_successor_package_artifact_v2`;
- `broker_reports_gate2_successor_run_artifact_v2`;
- `broker_reports_gate2_successor_execution_receipt_v2`;
- `gate2_successor_artifact_family_v2`.

Package artifact v2 pins:

- scope/admission integrity;
- source-context version/hash, without private context payload;
- decision schema/hash;
- model-input v3 hash;
- prompt v3 ID/hash;
- provider projection v3 response-format hash;
- provider execution identity;
- financial-input identity;
- explicit compatibility projection.

Legacy artifact v1 schemas remain immutable/readable. The compatibility reader
adds explicit dispatch for v2; it does not rewrite or silently upcast either
family. Production write remains blocked.

## Contracts changed

- frozen benchmark manifest v2;
- local Q0/Q1 proof/receipt v2;
- artifact family v2;
- explicit compatibility read dispatch for v2 schemas;
- exact qualification request profile/harness v2;
- closed-world bundle module order.

## Contracts explicitly unchanged

- Gate 1 contracts;
- Registry v1/type meanings;
- decision v1/four dispositions;
- typed-admission v1;
- deterministic scope v2;
- source context v2;
- prompt/model input/provider projection v3;
- canonical validator;
- deterministic materializer;
- financial context v1;
- legacy artifact v1 payloads;
- FNS specialized path;
- production routing/stage.

## Verification

- direct old/new qualification and Goal 10 tests:
  `33 passed in 10.14s`;
- focused benchmark/artifact/successor/bundle tests:
  `112 passed, 5 warnings in 17.54s`;
- full Broker Reports suite:
  `1520 passed, 20 skipped, 5 warnings in 114.41s`;
- Ruff on changed maintainable Python: passed;
- three generated bundles rebuilt deterministically;
- provider calls: `0`;
- customer calls: `0`;
- fallback/repair: `0/0`;
- persistence writes: `0`;
- stage mutations: `0`.

The five full-suite warnings are unchanged SWIG deprecation warnings.

Deterministic bundle SHA-256:

- Gate 1:
  `73e10186bdb2f921cd9b4ae56ff405b0d6f251790255ede0e0802eb687f0b1f8`;
- Gate 2 source:
  `fed33a2ddd8d1095630782e5deba4facc0b2f6bb9e49403621dd7ff22c0aa563`;
- Gate 2 domain:
  `5e6c41a496b0c43570f7948a7f5a1a14ca8a64f867b5acb6037e4d319d399d09`.

## Repository boundary

- base:
  `f7419e7353e28c030112b9a9d40f54bc7f73d04f`;
- branch:
  `codex/broker-reports-gate2-ambiguity-goal10-benchmark-v2`;
- PR:
  `https://github.com/Kwentin3/corp-openweb-ui/pull/137`;
- production admission: false.

## Acceptance

- `LOCAL_FIXTURES: PASSED`
- `OVERTYPING_NEGATIVE_TESTS: PASSED`
- `LITERAL_LOSS: ZERO`
- `PROVIDER_CALLS: ZERO`

Следующий разрешённый шаг только после merge Goal 10 PR:
Goal 11 one-attempt exact Nano requalification from the new `origin/main`.
