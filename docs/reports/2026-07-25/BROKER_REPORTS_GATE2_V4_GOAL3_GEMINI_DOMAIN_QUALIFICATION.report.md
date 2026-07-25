# Broker Reports — Gate 2 v4, Goal 3: Gemini domain qualification

Дата: 2026-07-25

Статус: `COMPLETED_WITH_EXPLICIT_GAPS`

## Результат

Обе exact Gemini-кандидатуры были последовательно запущены на frozen
non-customer corpus для workload `gate2_domain`:

1. `models/gemini-3.1-flash-lite`;
2. `models/gemini-3.5-flash-lite`.

Stage access log подтверждает по пять успешных HTTP 200 provider responses
для каждой модели. Однако итоговый safe JSON обоих локальных runner-процессов
не был сохранён: первый вывод превысил канал возврата инструмента, второй
завершился после закрытия родительского stdout pipe.

Fail-closed итог:

- `GEMINI_3_1_DOMAIN: NOT_QUALIFIED`;
- `GEMINI_3_5_DOMAIN: NOT_QUALIFIED`;
- terminal code: `qualification_safe_receipt_unavailable`;
- failure layer: `local_runner_output_capture`;
- `REPAIR: ZERO`;
- `FALLBACK: ZERO`.

Это не доказанный model-quality failure. Это отсутствие достаточного
terminal evidence. Ни одна модель не добавлена в production admissions.

## Git

- execution revision:
  `7997d7c67b8bf3d0fdccf7a8348f26cbbc2fb75a`;
- branch:
  `codex/broker-reports-gate2-v4-goal3-gemini-domain-qualification`;
- PR: [#116](https://github.com/Kwentin3/corp-openweb-ui/pull/116).

## Qualification identity

| Contract | Revision |
|---|---|
| exact workload | `gate2_domain` |
| provider profile | `google_gemini` |
| provider route | `997bc0306756ddc127bf7d87b2a8e495af88f6fe03814414d1bf289eacdeeeba` |
| input | `broker_reports_gate2_domain_qualification_manifest_v1:ee6a8ac0b364ab5abe4ce81472b6db7973813c89598cd0e9ae078d4783a89b1f` |
| output | `broker_reports_candidate_binding_output_v0` |
| prompt | `broker_reports_gate2_domain_economy_qualification_prompt_v1` |
| adapter projection | `gemini_response_format:1.5.0:997bc0306756ddc127bf7d87b2a8e495af88f6fe03814414d1bf289eacdeeeba` |
| canonical comparator | `broker_reports_gate2_domain_qualification_comparator_v1:46b0b0302969184bec311b181e7e3d5dbc4e2840371662e135b6a03f109e3fa9` |

Authorization SHA-256:

- Gemini 3.1:
  `e5cd2fc1b17e64a229aa1c84b7d986d7ff1617a28f12f8705ae902dfa53be3b5`;
- Gemini 3.5:
  `d2cb2266b45fedc69d82be78071e4de8385f0f919adda391d1145ae4fbaa116c`.

## Frozen corpus

Пять cases:

- `syn_domain_equal_value_exact_owner`;
- `syn_domain_adjacent_fx_exact_ownership`;
- `syn_domain_multiple_hypotheses`;
- `syn_domain_forbidden_neighbour_ref`;
- `syn_domain_explicit_unclassified`.

Corpus содержит:

- несколько domain hypotheses;
- соседние похожие значения;
- ambiguous labels;
- allowed и forbidden refs;
- exact ownership;
- explicit unclassified.

Customer data и expected selections модели не передавались.

## Execution evidence

Gemini 3.1:

- provider calls: `5`;
- HTTP responses: `5 × 200`;
- UTC interval: `2026-07-25T10:32:55.762Z` —
  `2026-07-25T10:33:08.254Z`;
- provider generated output: `true`;
- canonical validation ran: `true`;
- terminal safe result retained: `false`;
- tokens and cost: `unavailable`;
- terminal classification: `NOT_QUALIFIED`.

Gemini 3.5:

- provider calls: `5`;
- HTTP responses: `5 × 200`;
- UTC interval: `2026-07-25T10:37:07.526Z` —
  `2026-07-25T10:37:20.049Z`;
- provider generated output: `true`;
- canonical validation ran: `true`;
- terminal safe result retained: `false`;
- tokens and cost: `unavailable`;
- terminal classification: `NOT_QUALIFIED`.

`canonical validation ran: true` следует из порядка runner: следующий
provider call выполняется только после canonical validation предыдущего
case; после пятого case процесс дошёл до terminal serialization. Конкретный
pass/fail результат validation не восстанавливается и не заявляется.

Aggregate:

- provider calls: `10`;
- customer calls: `0`;
- input/output tokens: `unavailable`;
- actual cost: `unavailable`;
- expensive model calls: `0`;
- fallback calls: `0`;
- repair attempts: `0`;
- paid tools: `0`;
- stage mutations: `0`;
- Knowledge/RAG/vector writes: `0`;
- Gate 3 executions: `0`.

## Contracts changed

Добавлены только qualification-only элементы:

- additive request profile `domain_qualification_v1`;
- frozen synthetic manifest
  `benchmarks/gate2_domain_qualification_v1/manifest.json`;
- bounded runner
  `scripts/live_gate2_domain_economy_qualification.py`;
- focused tests runner/profile/fixture/canonical comparison.

`domain_qualification_v1` не включён в production request-profile tuple.

## Contracts explicitly unchanged

Без изменений:

- production admissions и production workload routing;
- canonical production parser/validator;
- Gate 2 domain package and finalization contracts;
- provider profile and route;
- Registry и four-disposition contract;
- source, financial evidence and checksum workloads;
- Gate 1 visual behavior, model IDs, valves and prompts;
- stage Functions, Pipes and Prompts;
- Knowledge/RAG/vectorization boundary;
- Gate 3.

## Failed qualification boundary

Exact model:

- `models/gemini-3.1-flash-lite`;
- `models/gemini-3.5-flash-lite`.

Exact workload: `gate2_domain`.

Exact terminal code:
`qualification_safe_receipt_unavailable`.

Failure layer:
локальный qualification runner / terminal output capture, после provider
transport.

Provider generated an output: `true`.

Canonical validation ran: `true`, но его terminal result не сохранён.

Narrowest corrective slice:
отдельный PR добавляет обязательный atomic safe receipt path и per-case
checkpointing до любого нового live qualification call. После локальных
тестов обе exact модели могут быть повторены один раз уже под новой
qualification identity.

Явно запрещены:

- объявление модели qualified по HTTP 200;
- восстановление предполагаемого результата из provider logs;
- reuse потерянного receipt;
- weakening canonical validator;
- free JSON;
- repair или fallback;
- expensive model;
- production admission;
- переход к Goal 4 до закрытия corrective Goal 3a.

## Tests

Focused:

- `48 passed in 1.14s`.

Full service suite:

- `1393 passed`;
- `20 skipped`;
- `5` existing SWIG warnings;
- `96.21s`.

Дополнительно:

- Ruff check: passed;
- manifest JSON parse: passed;
- manifest UTF-8 without BOM: passed;
- stage preflight for both exact models: passed;
- provider calls during preflight: `0`.

## Privacy

`PASSED`.

- frozen corpus synthetic and non-customer;
- customer corpus read: `false`;
- raw provider output in Git: `false`;
- response bodies in report/receipt: `false`;
- secrets in report/receipt: `false`.

## Stage

- stage mutation count: `0`;
- Function/Pipe/Prompt writes: `0`;
- production admission changes: `0`.

## Next permitted goal

Только отдельный corrective Goal 3a:
persisted safe receipt + one bounded requalification per exact Gemini model.

Goal 4 пока не разрешён.
