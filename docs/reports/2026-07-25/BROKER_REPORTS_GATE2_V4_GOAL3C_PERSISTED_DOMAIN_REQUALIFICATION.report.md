# Broker Reports — Gate 2 v4, Goal 3c: persisted domain requalification

Дата: 2026-07-25

Статус: `COMPLETED_WITH_EXPLICIT_GAPS`

## Результат

Обе exact Gemini-модели повторно и последовательно проверены для
`gate2_domain` на accepted qualification identity с атомарными safe
receipts:

1. `models/gemini-3.1-flash-lite`;
2. `models/gemini-3.5-flash-lite`.

Terminal result:

- `GEMINI_3_1_DOMAIN: NOT_QUALIFIED`;
- `GEMINI_3_5_DOMAIN: NOT_QUALIFIED`;
- runner status: `failed`;
- report terminal code:
  `domain_qualification_cases_failed`;
- repair: `0`;
- fallback: `0`.

Обе модели выполнили все пять cases. Ни одна не достигла exact expected
selection. Production admissions остаются пустыми.

## Git

- accepted execution revision:
  `0fe1c4b9d43ce6def9703b7bf7972556521a4571`;
- branch:
  `codex/broker-reports-gate2-v4-goal3c-persisted-domain-requalification`;
- PR: [#119](https://github.com/Kwentin3/corp-openweb-ui/pull/119).

## Exact qualification identity

| Contract | Revision |
|---|---|
| workload | `gate2_domain` |
| provider profile | `google_gemini` |
| provider route | `997bc0306756ddc127bf7d87b2a8e495af88f6fe03814414d1bf289eacdeeeba` |
| input | `broker_reports_gate2_domain_qualification_manifest_v1:edfba61488378154f7e6d37b6c532f2891a3339436d3fa107cce7ce3ba3678ca` |
| output | `broker_reports_candidate_binding_output_v0` |
| prompt | `broker_reports_gate2_domain_economy_qualification_prompt_v1` |
| adapter | `gemini_response_format:1.5.0:997bc0306756ddc127bf7d87b2a8e495af88f6fe03814414d1bf289eacdeeeba` |
| comparator | `broker_reports_gate2_domain_qualification_comparator_v1:c52a2da4d26f667b5daa841b1fd219e211e387eb6b8194f1909e47d006cffaba` |

Authorization:

- Gemini 3.1:
  `da3c4ec9a890cd76f619a40a7c9cd201c37382c6d781c75378bca39c7911f762`;
- Gemini 3.5:
  `29a1f31c4c35f151ce8e336ee203747c994348247d7bbd24b0d850ba2d201e55`.

## Gemini 3.1

- terminal status: `NOT_QUALIFIED`;
- cases executed: `5/5`;
- cases passed: `0/5`;
- canonical package acceptance: `5/5`;
- canonical selection acceptance: `3/5`;
- finalized package acceptance: `3/5`;
- exact expected selection: `0/5`;
- lost expected candidates: `1`;
- cross-row bindings: `0`;
- forbidden refs: `0`;
- invented candidate IDs: `0`;
- duplicate candidate bindings: `0`;
- provider calls: `5`;
- input tokens: `16342`;
- output tokens: `3178`;
- total tokens: `19520`;
- actual cost: `USD 0.008852500`;
- fallback: `0`;
- repair: `0`;
- persisted private safe receipt SHA-256:
  `fcaeddebf89eecd0d6585f7bebe1d0dd51b4bdcb660d88fe7179572b4100c8f1`.

## Gemini 3.5

- terminal status: `NOT_QUALIFIED`;
- cases executed: `5/5`;
- cases passed: `0/5`;
- canonical package acceptance: `5/5`;
- canonical selection acceptance: `3/5`;
- finalized package acceptance: `3/5`;
- exact expected selection: `0/5`;
- lost expected candidates: `1`;
- cross-row bindings: `0`;
- forbidden refs: `0`;
- invented candidate IDs: `0`;
- duplicate candidate bindings: `0`;
- provider calls: `5`;
- input tokens: `16342`;
- output tokens: `3064`;
- total tokens: `19406`;
- actual cost: `USD 0.012562600`;
- fallback: `0`;
- repair: `0`;
- persisted private safe receipt SHA-256:
  `e3e61690a16fca38cefdcdb369975182a447957c109cb756bd4256f47f6745ca`.

## Value-free failure localization

| Case | Gemini 3.1 | Gemini 3.5 |
|---|---|---|
| equal neighbouring values | extra/wrong binding fields and relation count | same family |
| adjacent FX ownership | field-path and subtype mismatch; canonical reject | field-path mismatch; canonical reject |
| multiple hypotheses | candidate/relation mismatch; one expected candidate lost | same family; one expected candidate lost |
| forbidden neighbour ref | relation-count mismatch; forbidden refs remain zero | same |
| explicit unclassified | confidence/completeness/uncertainty mismatch; canonical reject | same family; canonical reject |

Provider generated output: `true` for all ten calls.

Canonical validation ran: `true` for all ten cases.

Failure layer:

- unchanged exact-selection comparator for all cases;
- unchanged canonical selection/finalizer additionally rejected `2/5` cases
  per model.

## Aggregate accounting

- provider calls: `10`;
- customer calls: `0`;
- input tokens: `32684`;
- output tokens: `6242`;
- total tokens: `38926`;
- actual cost: `USD 0.021415100`;
- expensive model calls: `0`;
- fallback calls: `0`;
- repair attempts: `0`;
- paid tools: `0`;
- stage mutations: `0`;
- Knowledge/RAG/vector writes: `0`;
- Gate 3 executions: `0`.

## Contracts changed

`ZERO`.

Goal 3c добавляет только safe report/receipt. Runtime и stage не менялись.

## Contracts explicitly unchanged

- frozen manifest and five cases;
- prompt/schema/adapter/comparator;
- canonical production parser/validator/finalizer;
- provider route;
- production admissions and workload routing;
- Registry/four-disposition contract;
- Gate 1 visual behavior;
- stage Functions/Pipes/Prompts;
- Knowledge/RAG/vectorization;
- Gate 3.

## Failed qualification boundary

Exact terminal code:
`domain_qualification_cases_failed`.

Narrowest future corrective slice, только если domain qualification будет
открыта отдельной программой:

- value-free diagnosis общей candidate-binding семантики для extra binding,
  fact-field-path, relation completeness и explicit-unclassified dimensions;
- отдельный prompt/fixture PR до любого нового model call.

Явно запрещены:

- weakening comparator/canonical validator;
- передача expected selection модели;
- free JSON;
- repair/fallback;
- expensive model;
- production admission;
- перенос source/financial qualification;
- новый retry в Goal 3c.

## Tests

- focused: `67 passed in 1.18s`;
- full: `1395 passed, 20 skipped, 5 existing warnings in 92.39s`;
- raw provider output in receipts: `false`;
- terminal checkpoint state: `terminal`;
- cases persisted: `5` для каждой модели.

## Privacy

`PASSED`.

- synthetic non-customer corpus;
- customer corpus read: `false`;
- raw provider output in Git: `false`;
- private full safe receipts remain under ignored `local/`;
- committed receipt contains only aggregate/value-free evidence;
- secrets in Git: `false`.

## Next permitted goal

Goal 4 — `gpt-5.4-nano-2026-03-17` financial requalification after merge.
