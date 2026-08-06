# DOC19 — Gate 1 → Gate 3 financial fact sufficiency

Дата: 2026-08-04  
Статус: `BLOCKED_MISSING_GATE3_CONTRACT`

## Итог

DOC19 остановлен до freeze и до первого provider call. В репозитории нет существующего Gate 3 financial fact extractor-контракта, который принимает только DOC15 Gate 1 structured JSON. Создавать такой extractor или новый финансовый pipeline внутри DOC19 прямо запрещено контрактом задачи.

Это не означает, что финансовых контрактов нет вообще. Найдены четыре близких механизма, но ни один не совместим с требуемым маршрутом:

1. `gate3_context_manifest.py` создаёт проверенный индекс ссылок и сам помечает его как не являющийся Gate 3 business logic.
2. `gate3_financial_domain_context.py` является consumer boundary для `Gate2FinancialDomainQuery`; он прямо запрещает чтение Gate 1 payloads, источников и provider output.
3. `gate2_domain_runtime.py` содержит существующий source-fact extractor, но это Gate 2 runtime с обязательным `domain_context_packet_ref`, а не Gate 3 extractor для DOC15 JSON.
4. `pdf_dual_vlm_fact_providers.py` реализует исследовательское извлечение фактов из изображения crop. Передача ему DOC15 JSON потребовала бы нового prompt/input route.

Архитектурный тест также требует, чтобы финансовый Gate 3 successor зависел от `gate2_financial_domain_query` и не импортировал Gate 1 private implementation.

## Сохранённая входная база

- Все 24 таблицы DOC15 обнаружены.
- Оба image-only arm доступны: `google_flash_lite` — 24/24, `anthropic_opus` — 24/24.
- Классы DOC16 сохранены без изменения: 12 clean, 7 clipped, 5 contaminated.
- Ни один crop, Gate 1 JSON или продуктовый модуль не изменён.

Эта проверка подтверждает доступность входов, но не является freeze экспериментального протокола: hard stop наступил раньше выбора extractor/verifier.

## Accounting

- План extraction calls: 48.
- План verifier calls: 48.
- План base calls: 96.
- Выполнено: 0/96.
- Retry/fallback/repair/adjudication: 0/0/0/0.
- Исключённых таблиц: 0.

Нулевой call count — следствие обязательного pre-call stop, а не успешное выполнение acceptance accounting.

## Что нельзя заключить

Financial fact recall, precision, coverage-классы, crop-class effect, harmless defects, destructive context losses и root causes не измерялись. Пустой список critical context losses означает `NOT_EVALUATED`, а не отсутствие потерь.

Поэтому нельзя ни продолжить, ни остановить crop research на основании DOC19; казуальные правила для отдельных обрезанных строк не вводились.

## Проверяемые границы

- `services/broker-reports-gate1-proof/broker_reports_gate1/gate3_context_manifest.py:139`: manifest сам маркируется как не являющийся Gate 3 business logic.
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_domain_context.py:24`: Gate 1 payload прямо запрещён; consumer начинается на строке 73 и не является extractor.
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_domain_runtime.py:166`: существующая extractor factory относится к Gate 2; вызов требует `domain_context_packet_ref` на строке 256.
- `services/broker-reports-gate1-proof/broker_reports_gate1/pdf_dual_vlm_fact_providers.py:302`: существующий research extractor принимает visual input; image body находится на строке 470.
- `docs/stage2/contracts/BROKER_REPORTS_CSV_PRE_GATE3_CONTEXT.v1.md:11`: manifest не является Gate 3 business output и не реализует business logic.
- `services/broker-reports-gate1-proof/tests/test_broker_reports_gate_architecture.py:1399`: Gate 3 financial successor ограничен Gate 2 query boundary.

## Terminal decision

```text
DOC19_EXPERIMENT=BLOCKED
DOC19_RESULT=BLOCKED_MISSING_GATE3_CONTRACT
GATE1_FINANCIAL_SUFFICIENCY=INCONCLUSIVE
BEST_GATE1_ARTIFACT=NOT_EVALUATED
CROP_RESEARCH_POLICY=INCONCLUSIVE
```
