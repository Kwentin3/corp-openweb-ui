# Broker Reports Gate 5 — Single-Input Human Loop (G5.6)

Date: 2026-08-09

Goal status: `G5.6_CLOSED`

Proof outcome: `PROVEN`

Product status: `INACTIVE`

## Ответ на вопрос GOAL

Да. Gate 5 может провести один missing money input через LLM с strict
structured output, принять один человеческий ответ, детерминированно проверить
proposal, сохранить результат через существующий G5.3 boundary и после нового
чтения получить G5.5 `satisfied`.

LLM не получает trusted scope, не выбирает binding и не сохраняет факт.

## Минимальный seam

```text
G5.5 missing
-> Gate5SingleInputHumanLoopRuntime.ask
-> existing Gate2StructuredModelClientFactory.create
-> strict structured question
-> one human answer
-> strict structured proposal
-> deterministic evidence validation
-> unchanged G5.3 put
-> unchanged G5.5 recheck
```

Добавлен один orchestration adapter:

```text
Gate5SingleInputHumanLoopRuntimeFactory.create
```

Он композирует существующие owners и не читает Gate 4, ArtifactStore payload,
SQL, broker reports, CanonicalArtifact или Gate 3 напрямую.

## Representative proof

Исходное machine requirement:

```text
financial_type = SECURITY_DISPOSAL
value_key = acquisition_cost
```

Начальное состояние G5.5:

```text
requirement = missing
```

LLM сформировал strict structured question с `action = ask_user`.

В роли человека был передан делегированный ответ:

```text
Покупал за 70 000 рублей
```

LLM вернул strict structured proposal:

```json
{
  "schema_version": "broker_reports_gate5_single_input_proposal_v0",
  "action": "propose_fact",
  "amount": "70000.00",
  "currency": "RUB"
}
```

Локальная проверка независимо нашла в human answer ровно одну сумму и одну
валюту, нормализовала их и потребовала точного совпадения с proposal. Только
после `validation = passed` был вызван G5.3.

Результат:

```text
supplemental records = 1
requirement = satisfied
source_kind = supplemental_fact
```

Новое открытие ArtifactStore и новый G5.5 runtime получили тот же persistent
fact и тот же provenance. Financial Case до и после структурно равен и не
содержит добавленного `acquisition_cost`.

## Model-visible boundary

В question phase модель видит только:

```json
{
  "phase": "ask",
  "missing_input": {
    "financial_type": "SECURITY_DISPOSAL",
    "value_key": "acquisition_cost",
    "value_kind": "money",
    "currency_required": true
  }
}
```

В interpretation phase добавляется только `human_answer`.

Модель не видит:

- `user_id`, `case_id`, `normalization_run_id`, `workspace_model_id`;
- `requirement_id`, `subject_ref` и artifact refs;
- Financial Case, полную methodology или G5.5 result;
- supplemental payload/provenance и storage metadata.

Оба ответа закрыты отдельными strict JSON Schemas. Proposal schema требует
canonical amount с двумя знаками и uppercase трёхбуквенный currency code.
Fallback, repair и retry отсутствуют.

## Fail-closed proof

Контрольный ответ:

```text
Покупал примерно за 70 000 или 80 000 рублей
```

В тесте model boundary намеренно предложил `70000.00 RUB`, несмотря на две
суммы. Детерминированный validator вернул:

```text
status = rejected
error = human_answer_amount_ambiguous
supplemental_fact_ref = null
```

После reopen supplemental artifact отсутствует, а requirement остаётся
`missing`. Отсутствие значения не превращается в придуманное значение.

## Model/provider evidence

Exact-boundary automated proof использует реальные:

- G5.6 runtime/factory;
- G5.5 discovery и combined check;
- G5.3 persistence и ArtifactStore;
- Gate 4 official runtime;
- `Gate2StructuredModelClientFactory`, request builder, provider adapter и
  response parser.

Заменена только внешняя OpenWebUI completion boundary. Тест дополнительно
сравнивает полный model-visible payload и strict response formats.

Отдельный live model-adequacy diagnostic выполнен с approved profile
`openai_gpt` и моделью `gpt-5.6-sol` через настроенный provider endpoint.
Прошли две strict schema calls; итог — `70000.00 RUB`, один persistent fact и
G5.5 `satisfied`.

Этот diagnostic не добавлен в runtime и ничего не сохранил в repository. Для
прямого provider wire из OpenWebUI form были диагностически удалены только
OpenWebUI metadata, а JSON-string response приведён к обычной форме completion
boundary `dict`. Налоговый model-visible payload и response schema не
изменялись.

Текущий OpenWebUI model catalog не публикует approved `gpt-5.6-*` model ID,
поэтому exact live OpenWebUI product-route запуск не выполнялся. Allowlist не
ослаблялся. Это deployment/catalog limitation, а не обход в G5.6 code;
product status остаётся `INACTIVE`.

## KISS

Добавлены:

- один маленький factory-backed runtime;
- один bounded request profile в существующем request builder;
- две strict output schemas;
- один versioned contract;
- три focused tests, authority/CI routing и этот отчёт.

Не добавлены TaxInterviewEngine, TaxAgent, Tax Case, workflow state, registry,
PromptEngine, новая provider abstraction, БД/таблица, generic input engine,
multi-input interview, tax calculation, cross-run framework или следующий
Gate 5 slice.

## Verification

Focused G5.6:

```text
3 passed
```

Model client + G5.2–G5.6 contour:

```text
38 passed
```

Расширенный generated bundles/ArtifactStore/lifecycle/architecture/Gate
4/G5.2–G5.6/privacy набор:

```text
135 passed, 5 dependency deprecation warnings
```

Три OpenWebUI bundles пересобраны штатным генератором. Все десять managed
generator checks прошли. Successor hashes для изменённых request-builder и
authority-map bytes обновлены существующим fail-closed механизмом.

## Evidence files

- [G5.6 contract](../../stage2/contracts/BROKER_REPORTS_GATE5_SINGLE_INPUT_HUMAN_LOOP.v0.md)
- [G5.6 runtime](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_single_input_human_loop.py)
- [G5.6 tests](../../../services/broker-reports-gate1-proof/tests/test_broker_reports_gate5_single_input_human_loop.py)
- [Architecture authorities](../../stage2/contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md)

## Stop condition

`G5.6_CLOSED`, результат `PROVEN`, product status `INACTIVE`.

Следующий slice не начат и этим отчётом не авторизуется.
