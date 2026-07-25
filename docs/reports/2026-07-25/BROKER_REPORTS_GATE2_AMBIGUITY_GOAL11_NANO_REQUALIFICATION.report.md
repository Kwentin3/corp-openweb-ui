# Broker Reports — Gate 2 ambiguity discipline, Goal 11

Дата: 2026-07-25

Статус: `TERMINAL_FAILED`

## Outcome

Выполнена ровно одна live qualification attempt для exact model
`gpt-5.4-nano-2026-03-17` на замороженном successor workload v2.

Модель не квалифицирована:

- cases passed: `10/12`;
- cases failed: `2/12`;
- four dispositions represented: `false`;
- final qualification status: `failed`.

Эта exact revision повторно не запускается. Prompt, contract, fixture и provider
projection после attempt не менялись.

## Exact attempt boundary

- repository revision:
  `eb5c6011066a524d97aad9ac3b07d2d969f3db87`;
- benchmark:
  `gate2_financial_successor_v2`;
- benchmark canonical hash:
  `430bea21d0a36e993bc50184d971f36dfc75a1d2be12bcf5e43fba7436797d66`;
- prompt:
  `broker_reports_gate2_financial_evidence_successor_prompt_v3`;
- prompt SHA-256:
  `30c823d2c509294d4634eac1a4084da9b95056b260bdd64e41d5a5598937d9ae`;
- provider projection:
  `broker_reports_gate2_financial_evidence_provider_projection_v3`;
- qualification authorization SHA-256:
  `7180e9f163e519f9c27b5e6b496e9b9b17c4d791a7ae870420c05720e6dcf154`;
- provider route revision:
  `4232f7b089fec08326548bf4c70bb33fef0ce603c23d78d6110a9c9a8aec5929`.

Local Q0/Q1 and all `12/12` schema dry-builds passed before the live attempt.
The model was present in the published stage inventory.

## Results

Observed terminal dispositions:

- `typed_input`: `3`;
- `unclassified_financial_input`: `8`;
- `no_financial_input`: `0`;
- `unsupported`: `1`.

Failed cases:

1. `syn_successor_v2_unique_printed_total`
   - expected: `typed_input / printed_financial_metric_v1`;
   - observed: `unclassified_financial_input`;
   - canonical validation and materialization passed;
   - failure class: conservative under-typing.

2. `syn_successor_v2_repeated_header`
   - expected: `no_financial_input`;
   - observed: `unclassified_financial_input`;
   - canonical validation and materialization passed;
   - failure class: header/layout disposition mismatch.

There was no unsafe typed input. The rejection is caused by exact product
expectation mismatches and absence of the required `no_financial_input`
disposition.

## Product invariants

- canonical validation: passed for `12/12`;
- deterministic materialization: passed for `12/12`;
- literal loss: `0`;
- inventions: `0`;
- duplicate bindings: `0`;
- cross-scope bindings: `0`;
- terminal ownership gaps: `0`;
- compatibility reads: `12/12`;
- artifact family v2: passed;
- production write admitted: `false`;
- product expectation check: failed.

## Economy and latency

- provider calls: `12`;
- input tokens: `16,484`;
- output tokens: `2,308`;
- actual cost: `$0.006181800`;
- provider duration sum: `38,159 ms`;
- min/average/max case duration:
  `1,797 / 3,179.92 / 4,953 ms`.

Execution exclusions:

- fallback: `0`;
- repair: `0`;
- hidden retry: `0`;
- source model calls: `0`;
- domain model calls: `0`;
- expensive model calls: `0`;
- paid tools: `0`;
- customer calls: `0`;
- production routing/persistence: `0`.

## Evidence and privacy

The complete safe checkpoint receipt remains under ignored `local/`.
Its SHA-256 is:

`39f6a990d233926d7493056570730bdfa82f29df9a63d3f8f9d6cfa0e47dc641`.

The committed receipt is an aggregate/value-free projection. Privacy scan:

- raw provider output: absent;
- source groups/literals/value refs: absent;
- customer data: absent;
- expected model output: absent.

## Repository boundary

- base:
  `eb5c6011066a524d97aad9ac3b07d2d969f3db87`;
- branch:
  `codex/broker-reports-gate2-ambiguity-goal11-nano-requalification`;
- PR:
  `https://github.com/Kwentin3/corp-openweb-ui/pull/138`;
- code changes: `0`;
- provider calls after terminal attempt: `0`;
- production admission: false.

## Acceptance

- `FINANCIAL_MODEL: REJECTED_FOR_EXACT_SUCCESSOR_WORKLOAD`
- `AMBIGUITY_DISCIPLINE: FAILED_2_OF_12`
- `FOUR_DISPOSITIONS: FAILED`
- `EXACT_ATTEMPT: TERMINAL`

Следующий разрешённый шаг — отдельный Goal и отдельный PR для другого
опубликованного дешёвого candidate. Повтор Nano или скрытый prompt tweak
запрещены.
