# G5.69 — Frozen LLM Semantic Reliability & Model-Capability Benchmark

Дата: 2026-08-16

Статус: `CLOSED_REPEATABILITY_PROVEN_COMPARISON_UNAVAILABLE`

## Terminal

```text
LLM_METADATA_REPEATABILITY_BENCHMARK_COMPLETE
SAME_INPUT_OUTPUT_VARIANCE_MEASURED
NO_BENCHMARK_RESULT_SELECTION
COMPARISON_MODEL_NOT_AVAILABLE_ON_SAME_CONTRACT
FLASH_SINGLE_SHOT_STOCHASTIC
FINANCIAL_GENERALIZATION_PRESERVED
```

`MODEL_CAPABILITY_COMPARISON_COMPLETE` не объявлен: выбранная stronger model остановлена двумя deterministic policy gates до provider submission. Её semantic capability этим Goal не измерена.

## Freeze before calls

До первого G5.69 semantic result заморожены:

- Case F: известный `CLIENT_CODE -> ACCOUNT_IDENTIFIER` failure;
- Case C: clean G5.68 control;
- Flash: `google_gemini / models/gemini-3.5-flash`;
- comparison: `anthropic_claude / claude-opus-5`.

Model-visible request SHA-256:

- Case F: `2d541f11a4e8eb9193980c8f4de4bacb483584a95d5dbd7d11526bc239278033`;
- Case C: `c84f02ccb95177634109de8990550a3f2c12b9de5572ef6ad2bc911c4c790048`.

Оба fingerprints точно совпали с историческим G5.68 request, но исторический result не включался в статистические пять. Внутри каждого case все пять G5.69 fingerprints одинаковы. Temperature/seed overrides отсутствуют.

Contract `1.0.0`, instruction `1.2.0`, context policy v4, context/binding schemas, proposal schema и validator не менялись. Production semantic changes: `0`.

## Flash repeatability

Выполнено ровно `5 x 2 = 10` независимых single-shot submissions через существующий factory/OpenWebUI route. Получено 10 semantic results, transport failures: `0`. Retry, выбор лучшего, voting, repair и повтор плохого run: `0`.

| Case | Classification | Distinct raw sets | Semantic exact | Structural outcome |
|---|---|---:|---:|---|
| F | `STOCHASTIC` | 4 | 0/5 | rejected 5/5 |
| C | `STOCHASTIC` | 3 | 3/5 | exact and validated 1/5 |

Case F во всех runs сохранил три oracle facts, но добавлял разные extras. Диагностическая ошибка `CLIENT_CODE -> ACCOUNT_IDENTIFIER` возникла в `3/5` runs; в тех же `3/5` модель выбрала direct role/value relation. Это не stable wrong, а стохастическое semantic решение.

Case C дал exact raw semantic set в `3/5` runs. Только один из них одновременно прошёл structural validation; в двух остальных raw semantic set был точным, но три non-direct relations были fail-closed отклонены.

Суммы по десяти независимым runs:

| Metric | Total |
|---|---:|
| correct | 59 |
| missed | 1 |
| semantic extras | 9 |
| wrong roles | 3 |
| wrong value boundary | 0 |
| structural rejections | 14 |
| invented literals | 0 |
| invalid provenance | 0 |
| duplicates | 0 |

Эти totals являются суммой run-level observations, а не числом уникальных facts. Private qualification сохраняет normalized raw/publishable semantic-set hashes и частоту каждого fact без публикации customer values.

Usage: `10` calls, `1,262,050` input tokens, `6,989` output tokens, `1,313,254` provider-reported total tokens, `258,344 ms` provider duration.

## Comparison model boundary

`claude-opus-5` был уже опубликован в OpenWebUI и выбран до любого G5.69 semantic result. Canonical и provider-visible strict schema fingerprints были совместимы.

Однако exact metadata one-attempt route остановил модель до provider submission:

1. normal qualification: `gate2_no_strict_structured_provider_available`;
2. capability-probe path: `gate2_model_request_profile_mismatch`, потому что frozen metadata client запрещает capability-probe execution.

Итого: comparison submissions `0`, semantic results `0`, transport failures `0`. Prompt, request, schema, client profile и production admission не менялись; другая модель не подбиралась. Это точно соответствует разрешённому terminal `COMPARISON_MODEL_NOT_AVAILABLE_ON_SAME_CONTRACT`.

Следовательно, G5.69 доказывает stochastic behavior Flash на обоих frozen inputs, но не локализует причину относительно более сильной модели. Optional full-corpus confirmation не разрешён и не выполнялся.

## Financial and architecture regression

`Gate4FinancialCaseRuntimeFactory.create().rebuild_case(...)`:

- `holdout_a`: `39`, before/after SHA-256 identical;
- `holdout_b`: `129`, before/after SHA-256 identical;
- оба: `CASE_COMPLETE_FOR_CURRENT_INPUT_SET`;
- source stores unchanged: `true`.

Verification:

- focused G5.68/G5.69 + metadata adapter/client: `63 passed`;
- G5.69 benchmark guards: `6 passed`;
- architecture/cross-gate/canonical/bundle: `55 passed`;
- failures: `0`;
- только прежние SWIG deprecation warnings.

## KISS and scope stop

Добавлены только private measurement harnesses, offline qualification, tests и безопасные docs. Pipeline, prompts, schemas, validator, financial logic и bundles не менялись ради G5.69.

Private source bytes, oracle values, raw provider payloads and journals remain outside Git. Product activation, commit, push, PR, runtime voting, tuning и следующий Goal не выполнялись.
