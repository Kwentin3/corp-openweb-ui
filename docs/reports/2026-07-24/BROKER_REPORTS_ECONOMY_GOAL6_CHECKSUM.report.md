# Broker Reports — Economy Goal 6: Gate 2 checksum

Дата: 2026-07-24

Терминальный статус: `NOT_CLOSED`.

## Результат

Checksum answering run не начат. `Gate2FinancialContextChecksumRunnerFactory`
теперь сам применяет economy selection для workload
`gate2_financial_checksum`. Текущая policy не содержит qualified/active
model, поэтому factory завершился typed blocker:

`gate2_economy_no_qualified_model`.

Blocker возник до загрузки Gate 2 context в answering call и до provider
execution:

- provider calls: `0`;
- input/output tokens: `0 / 0`;
- fallback: `0`;
- hidden repair: `0`;
- expensive answering-model calls: `0`.

Control vector `3/3` дешёвой моделью не переподтверждён и не объявляется
успешным.

## Boundary enforcement

Checksum runner больше не принимает произвольный answering model как
достаточную production configuration. Model/provider config может только
сузить qualified economy allowlist.

Проверены два fail-closed случая:

- пустой qualified allowlist — `gate2_economy_no_qualified_model`;
- явный `gpt-5.6-sol` — `economy_model_not_registered`.

Оба завершаются до вызова model client. Для checksum policy запрещает
fallback (`maximum_fallback_calls = 0`).

Неизменёнными остались:

- model-facing package содержит только
  `broker_reports_gate2_financial_context_v1` и три metric requests;
- PDF, crop, Gate 1, sealed expected values и Gate 3 context запрещены;
- comparator проверяет value, currency/unit, sign, period, source binding,
  duplicates, invented metrics и arithmetic reconciliation;
- sealed expected vector используется только после model response.

## Control identity и baseline

Предыдущая repository-safe checksum receipt имеет SHA-256:
`dc43b0b0129c40d9fa40e37169df35bb7455622e0465b4864e31506e70e7cb82`.

Предыдущий принятый baseline:

- answering model: `gpt-5.6-sol` — теперь запрещён;
- calls: `1`;
- metrics: `3/3`;
- source bindings: `3/3`;
- arithmetic reconciliation: `1/1`;
- fallback/repair: `0/0`.

Это comparison baseline, а не economy proof. Его результат не переносится на
дешёвую модель.

## Provider gaps

- OpenAI Nano exact IDs: `UNAVAILABLE`,
  `stage_models_endpoint_model_absent`, owner `openai_gpt`; запрещены Mini,
  Sol, full GPT и o-series.
- Gemini `models/gemini-3.1-flash-lite`: `NOT_QUALIFIED`,
  `financial_evidence_decision_unclassified_shape_invalid`, owner Gemini
  schema/prompt boundary; запрещены обычный Flash и Pro.
- Gemini `models/gemini-3.5-flash-lite`: `UNSUPPORTED_CONTRACT`,
  `financial_qualification_not_exposed_by_capability_probe_route`, owner
  qualification harness; запрещены обычный Flash и Pro.
- Anthropic `claude-haiku-4-5-20251001`: `UNSUPPORTED_CONTRACT`,
  `gate2_model_schema_response_format_rejected`, owner Anthropic
  adapter/connection; запрещены Sonnet и Opus.

Узкий следующий шаг — квалифицировать хотя бы один exact economy model на
financial contract, активировать его отдельным policy receipt и только затем
повторить изолированный checksum.

## Проверки

- checksum + selection + budget focused suite: `34 passed`;
- full regression suite: `1330 passed, 20 skipped`;
- no-qualified и explicit expensive-ID tests подтверждают `0` model calls;
- checksum isolation/strict comparator tests остаются зелёными;
- customer values, private refs и provider raw output в Git: `0`.

## Acceptance

- `ECONOMY_ANSWER_MODEL`: `NOT_QUALIFIED_OR_UNAVAILABLE`;
- `CONTROL_VECTOR`: `NOT_RUN`;
- `EXPENSIVE_ANSWER_MODEL`: `ZERO`;
- `GOAL_6_ECONOMY_CHECKSUM`: `NOT_CLOSED`.
