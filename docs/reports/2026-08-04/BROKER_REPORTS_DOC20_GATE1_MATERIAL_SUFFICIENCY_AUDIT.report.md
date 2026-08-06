# DOC20 — Gate 1 material financial context sufficiency audit

Дата: 2026-08-04  
Статус: `BLOCKED_VERIFIER_ADAPTER_MODEL_INCOMPATIBILITY`

## Итог

DOC20 корректно заморозил все входы и выполнил ровно одну попытку для каждого из 48 случаев, но не получил ни одного содержательного verifier verdict. Все 48 запросов были отклонены OpenAI HTTP 400 до генерации: существующий frozen visual provider adapter передал `temperature=0`, а выбранный `gpt-5.6-sol` этот параметр не поддерживает.

После первого вызова контракт DOC20 запрещал менять adapter, model, prompt или schema. Retry, fallback, repair и смена verifier не выполнялись. Поэтому transport failure не преобразован в вывод о качестве Gate 1.

## Замороженные материалы

- 24 таблицы DOC15 без исключений;
- 48 существующих image-only Gate 1 JSON: 24 `google_flash_lite` и 24 `anthropic_opus`;
- 24 полные PDF-страницы с тонким evaluator-only target overlay;
- crop classes DOC16: 12 clean, 7 clipped, 5 contaminated;
- единый research-only prompt и audit schema;
- control sample: все 48 случаев, то есть 100%;
- verifier: OpenAI `gpt-5.6-sol`, exact model resolution до freeze, native image input и strict structured output;
- frozen цена: $5.00 input / $0.50 cached input / $30.00 output за 1M tokens.

## Архитектурная граница

Вызовы прошли только через существующий путь `PdfDualVlmFactProviderFactory.create_for_openwebui -> OpenAIResponsesVisionAdapter.invoke` (`services/broker-reports-gate1-proof/broker_reports_gate1/pdf_dual_vlm_fact_providers.py:101`, `:302`). Новый provider client не создавался. `FACTORY_REQUIRED` и `FORBIDDEN` сохранены (`:48`, `:52`).

DOC20 не создавал Gate 3 contract, financial fact extractor, financial ontology, ArtifactStore, cropper или product route. Gate 1 JSON, crops и product modules не изменялись.

## Failure attribution

Frozen request body существующего adapter содержит `temperature: 0` (`services/broker-reports-gate1-proof/broker_reports_gate1/pdf_dual_vlm_fact_providers.py:486`). Каждый из 48 terminal receipts содержит одинаковый safe failure class:

```text
HTTP_STATUS=400
FAILURE_CLASS=FROZEN_ADAPTER_MODEL_PARAMETER_INCOMPATIBILITY
UNSUPPORTED_PARAMETER=temperature
RAW_VERDICT=None
```

Model qualification до freeze прошла exact-ID проверку, но GET qualification не проверяла совместимость generation parameters. Исправление adapter после freeze стало бы изменением протокола и скрытым repair.

## Accounting

- Expected base calls: 48.
- Started / attempted / accounted: 48 / 48 / 48.
- Content-completed / structured-valid / raw verdicts: 0 / 0 / 0.
- HTTP 400 failures: 48.
- Retry / fallback / repair: 0 / 0 / 0.
- Adjudication provider calls: 0.
- Failed cases excluded: 0.
- Estimated provider cost: $0.00.

`ALL_BASE_CALLS_ACCOUNTED=TRUE` означает только полное terminal accounting; это не означает успешное выполнение content audit.

## Что нельзя заключить

Нельзя посчитать SUFFICIENT/NONCRITICAL/CRITICAL/AMBIGUOUS, sufficiency rate, critical-loss rate, crop-class effect или сравнение Google против Opus. Adjudication невозможна без raw verdict. Пустые critical-loss и minimum-contract массивы означают `NOT_EVALUATED`, а не отсутствие потерь.

Нельзя определить безвредные либо опасные дефекты Gate 1 и нельзя менять crop research policy. Казуальные правила для отдельных строк не вводились.

## Следующая допустимая граница

Новый запуск потребует отдельного явного решения до нового freeze: либо совместимый verifier/model route, либо изменение существующего adapter contract. Текущий DOC20 повторять или ремонтировать нельзя.

## Terminal decision

```text
DOC20_EXPERIMENT=BLOCKED
DOC20_RESULT=BLOCKED_VERIFIER_ADAPTER_MODEL_INCOMPATIBILITY
GATE1_MATERIAL_SUFFICIENCY=INCONCLUSIVE
BEST_GATE1_ARTIFACT=NOT_EVALUATED
CROP_RESEARCH_POLICY=INCONCLUSIVE
```
