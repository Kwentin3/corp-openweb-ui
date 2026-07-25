# Broker Reports — Gate 2 v4, Goal 5a: financial shape diagnostic harness

Дата: 2026-07-25

Статус: `COMPLETED`

## Результат

Добавлен qualification-only runner для ровно одного Gemini 3.1 case:
`unclassified_financial_input`.

Runner:

- использует production factories и maintained Gemini route;
- допускает максимум один provider call;
- до вызова атомарно создаёт `.safe.json`;
- сохраняет только root/decision keys, JSON types и binding item keys;
- не сохраняет literal values, source refs или raw provider output;
- отдельно запускает unchanged canonical parser;
- фиксирует missing/extra keys и canonical rejection code;
- сопоставляет результат с canonical/adapted schema branch shapes;
- запрещает repair/fallback.

Provider calls в Goal 5a: `0`.

## Git

- execution revision:
  `5076a676a4616d3ca47a2646ba950648d965c527`;
- branch:
  `codex/broker-reports-gate2-v4-goal5a-financial-shape-diagnostic-harness`;
- PR: [#121](https://github.com/Kwentin3/corp-openweb-ui/pull/121).

## Preflight evidence

- exact model published: `true`;
- exact model: `models/gemini-3.1-flash-lite`;
- workload: `gate2_financial_evidence`;
- authorization:
  `5c723cf8b49cd6ea216f166361c1bc927e4cb921f009612ae194fb39b10cdc46`;
- canonical schema:
  `3b4a6204d15acee98c444eb5a196ee023e78e53d0dee1b223f39e7b5d9f11a42`;
- adapted schema:
  `c34971081249a19f0ea0098aa2c2d0d950ec07a63e36a1f59dc391998b419ea1`;
- schema transforms: `8`;
- canonical disposition enum present: `true`;
- adapted disposition enum present: `false`;
- provider calls: `0`.

Preflight доказывает projection gap, но не назначает окончательного owner до
one-call response-shape evidence.

## Contracts changed

Только новый diagnostic script и focused tests.

Production runner, prompt, adapter, schema и canonical validator не менялись.

## Contracts explicitly unchanged

- Financial Evidence Registry;
- four-disposition decision contract;
- canonical parser/validator;
- deterministic materializer;
- Gemini adapter and provider route;
- production workload routing/admissions;
- Gate 1 visual behavior;
- stage Functions/Pipes/Prompts;
- Knowledge/RAG/vectorization;
- Gate 3.

## Tests

- focused: `65 passed in 1.24s`;
- full: `1400 passed, 20 skipped, 5 existing warnings in 90.47s`;
- Ruff format/check: passed;
- raw-value exclusion: passed;
- atomic receipt/no BOM/no temp residue: passed;
- no vendor SDK/direct URL bypass: passed.

## Required terminal accounting

- provider calls: `0`;
- customer calls: `0`;
- tokens: `0`;
- cost: `USD 0`;
- fallback calls: `0`;
- repair attempts: `0`;
- expensive model calls: `0`;
- stage mutations: `0`.

## Privacy

`PASSED`.

- customer corpus read: `false`;
- raw provider output in Git: `false`;
- literal/source values in receipt: `false`;
- secrets in Git: `false`.

## Next permitted goal

Goal 5 evidence branch from accepted `main`:

1. one Gemini 3.1 unclassified diagnostic call;
2. exact owner classification;
3. Gemini 3.5 four-disposition qualification;
4. no adapter correction unless the diagnostic independently proves it.
