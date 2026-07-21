# Broker Reports: Compact JSON Matrix vs CSV Grid Experiment v2

Дата: 2026-07-13

Режим: controlled private research, без production Gate 2 changes

Итог: компактная JSON-матрица имеет реальное преимущество по бюджету ответа, но пока не имеет достаточной надежности для замены текущего binding JSON. Candidate CSV сжимает ответ еще сильнее, но объективного преимущества для production-пути не показал.

## Вердикт

Повторный прогон был оправдан: v1 сравнивал schema-constrained JSON с unconstrained `text/plain` CSV и повторно использовал пять JSON-результатов из более раннего запуска. v2 устранил оба перекоса.

На одном model/crop/candidate corpus выполнены заново:

- A — текущий verbose candidate-bound JSON с `responseJsonSchema`;
- A2 — новый compact candidate-bound JSON `{"g":[...]}` с `responseJsonSchema`;
- C — candidate-id CSV через `text/plain`;
- B — свободный visual CSV challenge без сообщенных размеров.

Результат decision gate:

- A2 compact JSON: не прошел;
- C candidate CSV: не прошел;
- topology stage: корректно не запускался.

Текущий verbose JSON остается наиболее надежным candidate-bound представлением на этом корпусе: 12/12 primary packages прошли контракт против 11/12 у compact JSON и 9/12 у candidate CSV. Но и он не решает всю задачу: wide table 1:3 не повторился, а три сложные таблицы остались в `human_review_required`.

Практический вывод: проблема не сводится к синтаксису JSON против CSV. Главный остаточный дефект — визуальная сегментация широкой/многоуровневой таблицы и различие physical parser grid против logical reference grid.

## Что именно исправлено в методике

Stage 1 содержит только grid placement. Topology, merged headers и continuation metadata не смешиваются с grid output.

Для A/A2/C использованы одни и те же:

- шесть таблиц;
- 12 window crops;
- candidate dictionaries;
- declared row/column dimensions;
- модель `models/gemini-3.5-flash`;
- `temperature=0`, `thinkingLevel=minimal`;
- primary/repeat schedule.

Repeat schedule:

- по две попытки: 1:2, 1:3, 3:2, 4:1, 4:2;
- одна попытка: 5:3.

Итого Stage 1: 80 live attempts:

- A verbose JSON: 23;
- A2 compact JSON: 23;
- C candidate CSV: 23;
- B free CSV: 11.

Все 80 canonical live2 attempts завершились provider `STOP`. Terminal provider failures, hidden retries и failovers отсутствовали.

Для free CSV отдельно измеряются:

- dialect validity;
- rectangularity;
- natural shape;
- parser-shape agreement;
- logical-reference-shape agreement.

Если размеры модели не сообщались, shape mismatch больше не считается malformed CSV.

## Корпус и границы доказательства

PDF SHA-256: `79af73d5be78df446f768f516ed6eaebd5a9d4bfc6f98c98a4a53a5b5131f37d`.

Reference остается provisional: `agent_visual_reviewed_pending_human_signoff`. Числа ниже — controlled diagnostic, а не окончательная customer truth.

| Table | Case | Parser shape | Reference shape | Candidates | Windows |
|---|---|---:|---:|---:|---:|
| 1:2 | simple control | 10x3 | 10x3 | 30 | 1 |
| 1:3 | wide multi-row header | 20x18 | 8x18 | 241 | 2 |
| 3:2 | wide header, continuation fragment 1 | 48x16 | 12x16 | 708 | 4 |
| 4:1 | continuation fragment 2 | 25x16 | 10x16 | 343 | 3 |
| 4:2 | grouped/merged header | 7x11 | 7x11 | 35 | 1 |
| 5:3 | tax summary | 5x8 | 5x8 | 24 | 1 |

## Основные результаты

Primary attempts only:

| Arm | Valid packages | Scorable grids | Repeat tables | Input tokens | Output tokens | Visible output bytes |
|---|---:|---:|---:|---:|---:|---:|
| A verbose JSON | 12/12 | 6/6 | 4/5 | 75,010 | 19,950 | 53,317 |
| A2 compact JSON matrix | 11/12 | 5/6 | 4/5 | 70,321 | 5,605 | 9,987 |
| C candidate CSV | 9/12 | 4/6 | 3/5 | 73,230 | 3,747 | 4,248 |

Относительно A:

- A2: input tokens −6.25%, output tokens −71.90%, visible output bytes −81.27%;
- C: input tokens −2.37%, output tokens −81.22%, visible output bytes −92.03%.

Следовательно, у compact JSON есть не косметическое, а материальное бюджетное преимущество. Оно действует и на input leg: compact model view плюс малая schema заняли 3,106 schema bytes против 25,527 у verbose JSON. Candidate CSV не передает response schema вообще.

Но бюджет не компенсировал надежность:

- compact JSON: один malformed primary package, два malformed ответа с учетом repeat;
- candidate CSV: три malformed primary packages, шесть с учетом repeat;
- verbose JSON: zero malformed packages во всех 23 попытках.

Все malformed ответы имели provider `STOP`; это не truncation и не transport failure. Fail-closed validators обнаружили геометрически неверный, но завершенный output.

## Где именно сломались компактные форматы

| Arm | Table | Failure | Наблюдение |
|---|---|---|---|
| A2 compact JSON | 1:3, window 2 | `pdf_grid_column_count_mismatch` | все 10 строк имели 20–21 поле вместо 18; тот же failure повторился |
| C candidate CSV | 1:3, window 1 | `pdf_csv_column_count_mismatch` | 10 строк, ширина 18 или 20 |
| C candidate CSV | 1:3, window 2 | `pdf_csv_column_count_mismatch` | 10 строк, ширина 19 или 22 |
| C candidate CSV | 4:2 | `pdf_csv_column_count_mismatch` | одна из семи строк имела 10 полей вместо 11 |

Compact JSON был schema-constrained, но Gemini projection не удерживает `maxItems`; exact dimensions все равно обеспечиваются canonical post-validation. Это важный результат: structured output снижает syntax risk, но не гарантирует row width, если provider projection не может выразить верхнюю границу массива.

На 1:3 обе компактные формы повторили failure. Это не случайное повреждение quoting. Модель устойчиво видит в многоуровневом заголовке больше визуальных колонок, чем declared 18.

## Per-table аналитика

| Table | A verbose JSON | A2 compact JSON | C candidate CSV | B free CSV challenge |
|---|---|---|---|---|
| 1:2 | exact 30/30, repeat | exact 30/30, repeat | exact 30/30, repeat | exact 30/30, 10x3, repeat |
| 1:3 | grid valid, 233/360, 78/78 numeric, repeat conflict | one window width-failed, repeat failed | both windows width-failed | dialect-valid ragged 18–20 columns, 78/78 numeric, repeat conflict |
| 3:2 | grid valid, 228/768, 79/79 numeric | same score, repeat | same score, repeat, structural review | rectangular 48x16, 79/79 numeric, repeat; logical reference is 12x16 |
| 4:1 | grid valid, 207/400, 70/70 numeric, structural review | same score, repeat | same score, repeat | dialect-valid ragged 16–18 columns, 70/70 numeric, repeat |
| 4:2 | 75/77, 17/17 numeric, structural review | 77/77 and all empties exact, repeat, but topology still unresolved | width-failed, repeat failed | 76/77, 17/17 numeric, 7x11, repeat |
| 5:3 | exact 40/40 | exact 40/40 | exact 40/40 | exact 40/40 |

Здравое зерно у A2 видно на 4:2: compact matrix улучшила сам grid с 75/77 до 77/77. Но merged-header relation отсутствует, поэтому таблица правильно не стала authoritative. Grid и topology — разные задачи.

## Free CSV: объективная польза есть, но другая

Free CSV не доказал право быть production representation. Он не имеет candidate provenance и не должен подменять binding.

Как challenge/auditor он полезен:

- 6/6 dialect-valid CSV documents;
- 0 malformed syntax outputs;
- 4/6 rectangular natural grids;
- 4/6 parser-shape matches;
- 3/6 logical-reference-shape matches;
- 270/270 numeric-like reference values;
- 4/5 repeat matches.

1:3 и 4:1 были валидным, но ragged CSV. Это теперь не ошибочно называется malformed. Расхождение формы показывает отдельный structural signal:

- на 1:3 signal нестабилен между repeats;
- на 4:1 ragged shape повторяется, то есть visual grouping устойчиво отличается от fixed parser columns;
- на 3:2 visual output совпадает с physical parser shape 48x16, но не с logical reference 12x16.

Поэтому free CSV стоит сохранить как non-authoritative visual countercheck для numeric recall и shape disagreement. Он не должен попадать в source-fact authority.

## Decision gate

Кандидат мог перейти к Stage 2 только если одновременно:

- malformed packages не больше, чем у compact JSON;
- candidate ownership = 100%;
- placement и empties не хуже compact JSON;
- required repeats совпадают;
- output token reduction не меньше 50%;
- input token increase не больше 5%.

A2 прошел compression/input/relative-placement checks, но провалил ownership и repeatability из-за 1:3.

C прошел только compression и input checks. Он провалил ownership, malformed comparison, placement/empties и repeatability.

Eligible arms отсутствуют. Поэтому четыре возможных topology-only вызова не были сделаны. Это не незавершенность: conditional gate сработал как спроектировано.

## Что это означает для наших болей

### 1. Output budget действительно можно уменьшить

Verbose binding JSON дорог. Compact JSON снимает около 72% output tokens без роста input. Этот резерв реален и достоин продолжения исследования.

### 2. CSV не устраняет основную input-нагрузку

Candidate dictionary, crop и instructions остаются. Candidate CSV экономит почти только ответ. При этом отсутствие schema увеличивает число invalid grids.

### 3. Широкий многоуровневый header — корневая проблема

На 1:3 текущий JSON валиден, но не repeatable; compact JSON и CSV не удерживают declared width; free visual CSV тоже ragged и non-repeatable. Замена разделителя не исправит visual column segmentation.

### 4. Physical и logical grid нельзя смешивать в одной метрике

Для 1:3, 3:2 и 4:1 parser rows существенно больше reference rows. Aggregate cell accuracy имеет разные знаменатели при success/failure и не годится как единственный ranking. Нужны отдельные signed references для physical placement и logical table reconstruction.

### 5. Topology правильно отделена от grid

One-shot CSV+sidecar v1 ломал валидный grid из-за sidecar. В v2 topology не владеет grid и не может его стереть. Но до нее нельзя переходить, пока базовый grid не проходит gate.

### 6. Current JSON пока безопаснее, но не является конечным решением

Zero malformed packages — сильный аргумент оставить его current control. Repeat conflict на 1:3 и `human_review_required` на сложных структурах запрещают объявлять проблему закрытой.

## Рекомендуемый следующий узкий тест

Не повторять v2 на тех же четырех форматах.

Следующий разумный кандидат — schema-constrained candidate-to-cell ordinal vector:

```json
{"p":[0,0,18,19]}
```

Значение в позиции `i` — cell ordinal для candidate `i` в уже объявленной `rows x columns` сетке. Полная rectangular grid строится детерминированно локально; несколько candidates могут указывать на одну cell; все неуказанные позиции становятся explicit empty cells после materialization.

Почему этот ракурс лучше:

- модель больше не генерирует row widths и не может добавить 19-ю/20-ю колонку;
- ownership остается exact: vector length и candidate order проверяются локально;
- source provenance сохраняется;
- topology по-прежнему отдельно;
- output должен остаться существенно компактнее verbose binding.

Первый bounded corpus для v3:

- 1:2 simple control;
- 1:3 wide-header failure;
- 4:2 grouped-header case.

Сравнивать vector только с current verbose JSON и compact matrix, по две попытки на package. Free CSV и topology на этом шаге не нужны.

Stop rule: если ordinal vector также не удержит placement на 1:3, дальнейший format research прекратить. Следующая работа тогда должна быть про crop/header segmentation, window context и signed physical/logical reference, а не про JSON/CSV serialization.

## Реализация и guardrails

Добавлены research-only boundaries:

- `pdf_grid_experiment.py` — compact grid/topology contracts и fail-closed validators;
- `pdf_grid_experiment_provider.py` — Gemini JSON-schema adapter через canonical OpenWebUI connection resolver;
- protocol `v2` в существующем local experiment entrypoint;
- focused contract/provider tests.

Production Gate 2 pipeline, selection policy и deployed bundles не изменены. В business layer не добавлены provider-specific request formats. Live calls проходят только через factories; соседние scripts не импортируются; `python -I ... --help` проходит.

## Проверка и evidence

Canonical live run: ignored private evidence root (path withheld).

Live1 исключен до анализа: первый старт обнаружил pre-request различие hash field у full/window crop; после исправления частичный restart встретил TLS `BAD_RECORD_MAC`. Для canonical comparison создан свежий live2. В live2 транспортных terminal failures нет.

Evidence после journal-only recomputation без provider calls:

- source revision: `045df5bd689d3d0852e499dd57bddc8328b8b98d`;
- safe summary SHA-256: `0FE7AA8E1A7DE101E4CB1E069368DF1DD5EFB06A5C128212B6347A16CED8F7B5`;
- private journal SHA-256: `40CB459F47F1282C8CB42A8D71457FFED478DC85681DF9700A586EF3C7296A16`;
- Stage 1 accounting: 80 expected, 80 terminal;
- resume evidence: `journal_only_no_provider_calls`;
- focused CSV/grid/hybrid contracts: 37 passed;
- full pytest service suite: 324 passed, 5 external PyMuPDF SWIG deprecation warnings;
- isolated CLI import check: passed;
- `git diff --check`: passed;
- Gate 2 source-fact bundle SHA-256: `9E7E3FA0BE71C912FC4DE2B69D1B3447E90012B9FB89894E143C8A5EB8300F81`;
- Gate 2 domain bundle SHA-256: `220BA58A59F33CA2F536D3A61B6959662A5F12E88640236438DEAC5A9523C454`.

## Финальное решение

Production refactor на CSV не делать.

Compact JSON matrix не выбрасывать: она доказала значительную экономию и локальное улучшение 4:2. Но promotion запрещен до zero-malformed ownership и repeatability на 1:3.

Free CSV оставить только как visual challenge/auditor.

Если продолжать research, делать один узкий v3 с candidate-to-cell ordinal vector. Это проверяет уже не разделитель, а более вероятную гипотезу: можно ли убрать генерируемую моделью ширину строки, сохранив provenance и полный deterministic grid.
