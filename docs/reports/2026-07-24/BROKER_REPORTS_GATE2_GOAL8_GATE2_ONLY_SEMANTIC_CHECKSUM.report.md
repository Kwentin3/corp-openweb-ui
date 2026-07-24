# Broker Reports Gate 2 — Goal 8: Gate 2-only semantic checksum

Дата: 2026-07-24

Статус: `COMPLETED`

## Итог

Запечатанный source-only control vector прошёл проверку целостности до запуска. Все три контрольные метрики восстановлены одним вызовом `gpt-5.6-sol` через существующую OpenWebUI completion/provider boundary только из `broker_reports_gate2_financial_context_v1`.

Acceptance Goal 8 выполнен:

- Gate 1 content в model-facing test context: 0;
- control vector: 3/3;
- amount, currency, unit, sign и period: 3/3;
- source binding: 3/3;
- semantic visual-table-derived metrics: 3/3;
- duplicate rows: 0;
- invented metrics: 0;
- deterministic arithmetic reconciliation: 1/1;
- provider/schema failures, fallback и repair: 0.
- full Broker Reports suite: 1267 passed, 20 skipped.

Безопасная квитанция: `BROKER_REPORTS_GATE2_GOAL8_GATE2_ONLY_SEMANTIC_CHECKSUM.receipt.safe.json`.

## Реализованный контур

`Gate2SemanticVisualFinancialContextFactory` детерминированно превращает validated semantic-visual source tables в row-scoped Gate 2 financial evidence:

1. Заголовок, описание и одна source row материализуются как один source-local scope.
2. Каждое source value получает стабильный ref и полную document/page/table/row/cell lineage.
3. Неоднозначное финансовое содержимое сохраняется как `unclassified_financial_input`; свободная типизация моделью не выполняется.
4. Явные document-level dimensions нормализуются кодом: ISO currency token или однозначный `$` и явный `thousands`.
5. Конфликт валют закрывается fail-closed.
6. В answering-model payload остаётся только каноническая Gate 2 projection. Raw table container, PDF, crop и Gate 1 artifact metadata туда не входят.

`Gate2FinancialContextChecksumContractFactory` создаёт изолированный strict-schema контракт. Comparator независимо проверяет identity, amount, currency/unit, sign, period, Gate 2 binding, дубли и выдуманные метрики. Sealed expected values используются только после ответа модели.

## История квалификации

История не скрыта:

1. Исходная 39-scope shadow projection сохранила суммы, но не содержала явных currency/unit literals и не давала устойчивой row-level связи для одной контрольной метрики. Попытка не принята.
2. Row-scoped materialization восстановила amount/sign/period/source binding 3/3, но без deterministic dimension normalization currency и один unit не совпали. Попытка не принята.
3. После общего source-driven dimension normalization итоговая проверка прошла полностью.

Обе неуспешные попытки и provider output сохранены только в ignored private evidence. В Git находятся лишь код, тесты, этот отчёт и обезличенная safe receipt.

## Изоляция

Answering LLM не получил:

- PDF или изображения страниц;
- crops;
- Gate 1 document memory;
- Gate 1 semantic-table containers;
- sealed expected values;
- customer methodology;
- Gate 3 instructions;
- tax skills;
- Knowledge/RAG/vector context.

Три requested metric identity переданы как задача поиска; контрольные значения, ожидаемые dimensions и comparator evidence в prompt не передавались.

## Арифметическая сверка

Для одной метрики sealed source vector содержит однозначные operands. Детерминированный comparator подтвердил:

- все operands присутствуют в Gate 2 context;
- сумма operands совпадает с printed source metric;
- Gate 2 reconstructed value совпадает с printed metric;
- LLM answer совпадает с тем же значением.

Результат: `PASSED`, 1/1.

## Ограничения

Initial Registry остаётся намеренно узким. Все 28 row-scoped checksum inputs сохранены как `unclassified_financial_input`, а не фиктивно типизированы. Source values, dimensions и provenance доступны downstream LLM; ограничение не мешает использовать финансовый контекст, но запрещает утверждать, что эти строки получили canonical financial input type.

Gate 3, налоговая методика, расчёт декларации и browser handoff не реализованы и остаются вне scope.

## Приватная доказательная база

- sealed reference SHA-256: `2cdd51bb4235dadb10634c9853b56c95815bf06b6612676e362606d85a503aab`;
- Gate 2 context integrity: `d16955a041e460d9b632419eff31f20f821d952540b400cbc0ccbccc15251817`;
- private output SHA-256: `c13f760895d46cff8e40c6a6f6e0990310e2ce0f21f16ffd783cfa24373c0f79`;
- safe receipt integrity: `1d7957101b5dc6a4cfb94d38839dfc4424d54c6ddac73b62c631395c330a4411`.

Private labels, customer values, runtime filenames и raw provider output в Git отсутствуют.
