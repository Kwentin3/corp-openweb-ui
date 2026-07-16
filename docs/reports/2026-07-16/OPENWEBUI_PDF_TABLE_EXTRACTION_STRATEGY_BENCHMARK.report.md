# OpenWebUI PDF Table Extraction Strategy Benchmark

Дата: 2026-07-16
Статус: завершённый development benchmark, результат provisional
Финальный вывод: `CURRENT_APPROACH_NOT_JUSTIFIED`

## Короткий вердикт

Ни один из трёх вариантов пока нельзя делать production authority.

- Strategy B лучше всех обнаруживает таблицы: найдены все 9 из 9 эталонных таблиц, один false positive на странице содержания, F1 `0.947368`.
- Strategy C даёт лучшую provenance/safety: из 132 проверенных непустых ячеек 96 приняты с уникальным source trace, 25 отклонены, 11 отправлены на review, false accepted values — 0.
- Но A, B и C дали 0 из 9 полностью точных физических таблиц и `0.0` exact numeric accuracy в ожидаемой физической позиции.
- Поэтому benchmark не оправдывает ни дальнейшее наращивание общего deterministic table constructor, ни немедленный переход production на VLM-first.

Практическое решение: production pipeline и Gate 2 оставить без изменений. Для следующего узкого research slice использовать гипотезу `VLM detection/extraction + deterministic evidence gate`, а parser не развивать дальше как универсальный реконструктор авторского замысла.

## Что именно проверялось

Один и тот же замороженный корпус, модель, provider route, temperature, схемы, scoring policy и ценовой профиль использовались для трёх стратегий:

1. A — прямая extraction со всего изображения страницы.
2. B — отдельная VLM detection, затем crop и отдельная VLM extraction.
3. C — точный replay результата B плюс parser evidence validation. C не делала дополнительных model calls и не меняла значения или topology B.

Физическая структура отделена от semantic projection. Контракт допускает unknown и явные alternatives; пустые ячейки должны присутствовать явно. Symbol-to-ISO inference запрещён.

Parser в C использовал только raw `layout_words`, координаты и parser ordinals. Он не создавал строки, колонки, ячейки или merged regions.

## Корпус

Принятый run содержит 8 страниц и 9 эталонных таблиц:

| Case | Broker | Основные свойства |
|---|---|---|
| `betterment_p02` | Betterment | отрицательный TOC control |
| `betterment_p04` | Betterment | financial table, currency/physical-semantic collision |
| `drivewealth_p07` | DriveWealth | borderless, alignment-based |
| `drivewealth_p09` | DriveWealth | sparse, currency qualifier collision |
| `moomoo_annual_p14` | Moomoo | compound page, multi-row header, raster/image table |
| `moomoo_midyear_p10` | Moomoo | compound, mixed text/raster |
| `ibkr_annual_p11` | IBKR | ruled dense-text table |
| `ibkr_midyear_p03` | IBKR | long borderless financial table |

Reference создан из ранее зафиксированных cells/spans и отдельной visual bbox-проверки. Поле `human_reviewed=false`, поэтому все сравнительные числа и архитектурный вывод provisional. Это достаточная граница для отказа от production migration, но не достаточная для утверждения production readiness.

## Замороженная модель и стоимость

Provider/model: `google_gemini`, `models/gemini-3.5-flash`, temperature 0, thinking level minimal. Live qualification подтвердила exact model match, image input, structured output и лимиты `1,048,576` input / `65,536` output tokens. Модель и возможности описаны в [официальной карточке Gemini 3.5 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash).

Стоимость зафиксирована на дату запуска по [официальной странице Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing): `$1.50 / 1M` input tokens и `$9.00 / 1M` output tokens, включая thinking output.

## Принятые evidence artifacts

Основной run:

- runner commit: `4172a07d3803db0acc3859439142b65c558f7f8f`;
- scorer-fix commit: `d4cc1ae1df547a41b419d0ca983a808170c511f1`;
- manifest semantic SHA-256: `ddbde26c1eb49baeb8e25d35bd8ded97dc9af4e5d0ab37bd211cc7550e4a54ca`;
- terminal SHA-256: `d899bfbb16621350f8ffea4e46066d2529e469bea6e2bfcaaeda83a3a8bfd238`;
- reference SHA-256: `0865544f42aac951f11809173e1035f7237058684ef6f793a2b546a89c181a66`;
- accepted score v2 file SHA-256: `b7b10d0af52efc59522d2d8652f78606a08aecfce2f24afe388ac95120d1e265`;
- scorer implementation SHA-256: `f22384d3737fc5948e515edde8596dc09fc179a67cf79334e2fc1451b9c5e9bf`;
- contracts implementation SHA-256: `5349446e53357d46a0d3505d1d413f8aa6f229fca2907fba3b6ee62884814df7`.

Локальные пути:

- terminal: `local/stage2/broker_reports_pdf_table_strategy_benchmark_2026-07-16/run2-gate/run/terminal.private.json`;
- seal: `local/stage2/broker_reports_pdf_table_strategy_benchmark_2026-07-16/run2-gate/run/terminal.private.sha256.json`;
- process evidence: `local/stage2/broker_reports_pdf_table_strategy_benchmark_2026-07-16/run2-gate/gate_processes.safe.json`;
- принятый score: `local/stage2/broker_reports_pdf_table_strategy_benchmark_2026-07-16/run2-gate/score.rescored-v2.json`.

Run завершился без case failures. Terminal был записан и sealed до запуска отдельного scorer process; reference argument не передавался runner, terminal повторно проверен после scoring и не изменился.

## Сводные результаты

| Метрика | A: direct | B: detect + crop | C: B + evidence |
|---|---:|---:|---:|
| Detection precision | 0.8333 | **0.9000** | **0.9000** |
| Detection recall | 0.5556 | **1.0000** | **1.0000** |
| Detection F1 | 0.6667 | **0.9474** | **0.9474** |
| Exact physical tables | 0/9 | 0/9 | 0/9 |
| Row-count accuracy | 0.2222 | **0.6667** | **0.6667** |
| Column-count accuracy | **0.4444** | 0.1111 | 0.1111 |
| Exact cell accuracy | 0.0900 | **0.0948** | **0.0948** |
| Exact numeric accuracy at expected cell | 0.0000 | 0.0000 | 0.0000 |
| Exact semantic tables | 1/9 | **3/9** | **3/9** |
| Currency relation precision / recall | 1.000 / 0.500 | **1.000 / 0.625** | **1.000 / 0.625** |
| Unique provenance coverage | — | — | **0.7273** |
| Human review rate among checked cells | — | — | 0.0833 |
| Rejected cells | — | — | 25 |
| False accepted values | — | — | **0** |
| Malformed contract outputs/cases | 4 | 3 | 0 собственных |
| Safety passed | нет | нет | **да** |
| Model calls | 8 | 18 | 18 reused from B |
| Additional model calls | 8 | 18 | **0** |
| Estimated cost | `$0.377355` | `$0.388694` | `$0.388694` |
| Aggregate latency | 175.694 s | 215.884 s | 233.532 s |
| Frozen complexity units | **1** | 3 | 4 |

`Exact numeric accuracy` здесь означает точное значение в правильной физической ячейке. Ноль не означает, что VLM не прочитала ни одной цифры; он означает, что переносы между 2- и 3-column interpretations, пропуски и несовпадения topology не дали ни одного полного exact numeric placement против reference.

## Что показала Strategy A

A имеет минимальную сложность и на 3% меньшую оценочную стоимость, чем B, но результат недостаточен:

- только 5 из 9 таблиц засчитаны detection после strict contract validation;
- четыре case outputs нарушили контракт;
- 24 invented visible atoms и 4 mutated atoms по reference;
- ни одной exact physical table;
- одна exact semantic table из девяти.

Простой direct prompt полезен как baseline, но не как authority.

## Что показала Strategy B

Разделение detection и extraction резко улучшило именно поиск областей:

- 9/9 таблиц найдены;
- один false positive — TOC на `betterment_p02`;
- mean matched IoU `0.931469`;
- detection precision `0.9`, recall `1.0`.

Но хороший crop не решил extraction:

- три case outputs нарушили strict rectangular/reference contract;
- 0/9 exact physical tables;
- column count exact только для 1/9 таблиц;
- merged span recall 0;
- 2 mutated atoms;
- exact semantic result 3/9.

Следовательно, гипотеза «сначала найти таблицу, затем дать чистый crop» подтверждена для detection, но не подтверждена для полного table understanding.

## Что показала Strategy C

C не улучшает extraction B и не должна этого делать. Она проверяет, что можно безопасно принять:

- 132 непустые ячейки были проверены;
- 113 значений существуют в parser evidence;
- 96 имеют уникальный trace и приняты;
- 25 отклонены как not found в согласованной source region;
- 11 имеют неоднозначный trace и направлены на review;
- false accepted values — 0;
- unique provenance coverage — `72.73%`;
- три case не дошли до C из-за invalid upstream extraction.

C — единственная стратегия, прошедшая safety policy, но это не компенсирует 0/9 exact physical tables. Evidence gate хорошо ограничивает ущерб, но не делает слабую extraction правильной.

## Currency/header collision

На `drivewealth_p09` A и B независимо вернули физическую сетку `description | $ | amount` из трёх колонок. Semantic projection при этом свела её к description + monetary amount и связала currency qualifier с amount. `normalized_code` остался `null`; `USD` не выводился из символа `$`.

Это важный положительный результат:

- VLM понимает qualifier relationship;
- semantic projection действительно может сохранить одно значение при разных физических layouts;
- отдельное deterministic правило «символ `$` всегда отдельная колонка» или «никогда не отдельная колонка» будет слишком жёстким.

Но reference для этой страницы содержит 2-column physical layout, поэтому физическая точность не засчитана. Так как reference не прошёл human review, этот конкретный physical verdict остаётся provisional; semantic вывод и отсутствие hardcoded currency inference доказаны надёжнее.

## Где parser лучше, а где VLM лучше

Parser лучше VLM в том, что он реально доказал в этом run:

- точное существование source text;
- source coordinates и parser ordinals;
- unique/ambiguous/not-found distinction;
- fail-closed rejection без изменения VLM values;
- стабильная provenance на text-layer cells.

VLM лучше deterministic parser в том, что он реально доказал:

- visual region discovery, включая borderless и compound pages;
- 9/9 detection recall без parser table construction;
- работа с визуальными/raster regions, где обычный text layer неполон;
- semantic currency-to-amount relationship без symbol-to-ISO hardcode.

Benchmark не запускал старый deterministic constructor как четвёртую стратегию, поэтому нельзя честно утверждать, что его end-to-end accuracy ниже конкретного числа A/B/C. Но VLM failures не являются аргументом продолжать добавлять collision rules: они показывают, что table construction остаётся нерешённым независимо от того, кто угадывает topology.

## Ответы на обязательные вопросы

1. **Лучшая accuracy:** B, а C наследует ту же extraction. Преимущество относится прежде всего к detection и частично к semantics; production-level physical accuracy не достигнута.
2. **Лучшая provenance:** C. Она единственная дала source-trace coverage и ноль false accepted values.
3. **Минимальная сложность:** A, objective complexity 1. Низкая сложность не компенсирует плохую accuracy/safety.
4. **Где deterministic parsing лучше VLM:** source existence, coordinates, traceability и reject/review policy на text layer.
5. **Где VLM лучше deterministic parsing:** visual detection, compound/borderless/raster region understanding и qualifier semantics.
6. **Оправдана ли текущая hybrid architecture:** нет как production migration и нет как дальнейшее наращивание constructor/repair engine. Evidence-validation часть полезна; extraction authority пока недостаточна.
7. **Parser — constructor или evidence layer:** для следующего research slice — evidence layer. Это не разрешение удалить текущий production constructor до нового проходного gate.
8. **Нужен ли OCR:** отдельный OCR не нужен, чтобы VLM увидела raster table, но text-layer provenance для таких cells неполна. Если policy требует текстовый source trace, понадобится OCR или эквивалентный pixel-region evidence path. Этот run OCR не выполнял и не доказывает качество конкретного OCR.
9. **Минимальная production architecture:** сейчас — без изменений. Минимальная экспериментальная кандидатура: page render → VLM detection → crop → strict VLM extraction → deterministic evidence gate → accept/reject/review. Никаких parser-created rows/columns и никаких скрытых repair retries.

## Почему финальный enum не C

C прошла safety, но recommendation policy требует хотя бы одну безопасную exact physical table. Таких таблиц 0. Выбирать C только за provenance означало бы принять хорошо проверенную, но структурно неверную таблицу. Поэтому корректный enum — не `STRATEGY_C_HYBRID_EVIDENCE_PREFERRED`, а `CURRENT_APPROACH_NOT_JUSTIFIED`.

## Отклонённые/исправленные benchmark artifacts

Первый live run на commit `82313d8` сохранён в `run1-gate`, но исключён из сравнения. Его prompts/schema не называли порядок bbox достаточно явно, и все detection outputs систематически использовали `[y0,x0,y1,x1]`. Это был defect benchmark contract, а не доказательство detection failure.

Commit `4172a07` изменил только versioned bbox contract: prompts, model-view rules и schema description явно требуют `[x0,y0,x1,y1]`. Corpus, provider, token budgets, reference и IoU policy не менялись.

Первичный `run2-gate/score.json` также superseded: scorer ошибочно обнулял валидную B detection, если последующая crop extraction была invalid. Commit `d4cc1ae` отделил detection scoring от extraction scoring и добавил malformed accounting. Provider terminal/seal не перезапускались и не менялись; accepted artifact — `score.rescored-v2.json`.

Это не hidden retry: отклонённый run и superseded score сохранены, причины версионированы, а принятый terminal остаётся неизменным.

## Проверки реализации

- focused benchmark tests: `20 passed`;
- adjacent provider/parser/semantic tests до coordinate repair: `78 passed`;
- полный service suite после harness v1: `722 passed`;
- полный service suite после bbox v2: `723 passed`;
- полный service suite после scorer v2: `724 passed`;
- Ruff и `py_compile`: passed;
- separate runner/scorer processes: passed;
- terminal sealed before reference access: passed;
- hidden retry/provider failover: 0/0;
- OCR/RAG: false/false;
- production authority/Gate 2 changed: false/false;
- worktree на момент accepted live run: clean;
- accepted live runner commit: `4172a07`.

Изменены только research benchmark fixtures/scripts/tests и этот отчёт. Production PDF pipeline, Gate 2 selection, validators и deploy artifacts не менялись; deploy не требуется.

## Финальный ответ

Не продолжать строить общий deterministic PDF table reconstruction engine через новые collision rules. Но и не переводить production на VLM-first сейчас.

Следующий допустимый шаг — узкий research slice по strict VLM topology/cell contract поверх уже доказанной B detection, с parser только как evidence gate. Production остаётся как есть до benchmark, где появятся безопасные exact physical tables на human-reviewed reference.

`CURRENT_APPROACH_NOT_JUSTIFIED`
