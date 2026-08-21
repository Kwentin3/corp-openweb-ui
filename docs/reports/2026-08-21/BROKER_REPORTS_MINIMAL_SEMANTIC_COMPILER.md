# Broker Reports — минимальный Semantic Compiler

Дата: 2026-08-21

Статус: `NO_STABLE_SEMANTIC_BOUNDARY_FOUND`

Режим: research-only; current Gate 3–5 и production не менялись.

## Короткий вывод

Идея mapping не провалилась. Наоборот, её самое узкое ядро сработало очень хорошо: модель три раза подряд одинаково и правильно перевела все 16 заголовков торговой таблицы в нормализованные роли. Для этого хватило одних заголовков; название таблицы ничего не улучшило.

Но весь Semantic Compiler пока не доказан. Остались две нестабильные границы:

1. перевод исходных значений направления сделки в `PURCHASE/DISPOSAL` не прошёл строгий контракт ни разу;
2. closed residual extractor на свободном тексте ни разу не дал полностью правильные 9 из 9 строк во всех трёх запусках.

Поэтому честный terminal отрицательный. Полезное зерно при этом сильное: структура таблицы уже может читаться через маленький schema mapping, а не через свободную генерацию всех typed records.

## Что проверяли

Frozen corpus:

- Canonical root: `bbf20e4ea5cd706398d459716fdab60812ef48ed6b0cd2d0264a778a77ab079d`;
- 12 выбранных source rows из 3 логических таблиц;
- 20 ожидаемых typed facts;
- 75 runtime role values;
- один и тот же frozen input во всех запусках.

Каждый вариант запускался три раза. Не было retry, repair, best-of-N, ручной правки ответа или передачи модели ожидаемой taxonomy по строкам.

Проверяемый путь:

```text
immutable Canonical
  → exact schema fingerprint
  → small table/header mapping
  → deterministic source-shaped event
  → deterministic Gate 5 adapter

free-text residual only
  → closed semantic codes/spans
  → deterministic values + provenance
```

Первый preflight закончился TLS timeout на `/health` до любого модельного вызова и исключён из результата. После подтверждённого `HTTP 200` выполнена одна чистая серия из 18 вызовов. Позднее сохранённые ответы были пересчитаны без новых вызовов после fail-closed исправления валидатора: несовместимый с типом таблицы residual code больше не может попасть в materializer.

## Результаты H1–H8

| Гипотеза | Факт | Вывод |
|---|---|---|
| H1. Header mapping — маленькая стабильная задача | 16/16 ролей, один hash, 3/3 exact | Подтверждена на торговой таблице |
| H2. Минимальный контекст | `headers only` и `title + headers` одинаково exact; title добавил токены без улучшения | Минимум — только headers |
| H3. Строки после mapping материализуются кодом | 3 trade rows → 3 `SECURITY_TRADE` → 10 Gate 5 facts; 10/10 exact, без дублей | Подтверждено при frozen полном mapping; автоматическое получение value bindings не доказано |
| H4. Source-shaped dialect | 3 trade events детерминированно раскрываются в 10 fact-centric records и полностью удовлетворяют текущему Gate 5 контракту | Source-shaped вариант проще и предпочтителен внутри compiler, но отдельный новый Gate 5 dialect не обязателен |
| H5. LLM только для residual free text | residual: один rejected run; два одинаковых run дали 8/9 строк | Направление верное, стабильная граница ещё не найдена |
| H6. Exact fingerprint reuse | exact input принят; 5/5 мутаций отвергнуты: rename, reorder, count, identity, continuation | Локальный fail-closed механизм подтверждён; перенос между другими отчётами не проверен |
| H7. Joint или split | joint `headers only` — 3/3 exact; split type→columns — 0/3 strict-valid | На этом corpus joint контракт меньше и устойчивее |
| H8. Frozen direct comparator | direct projection: 3 разных hash; только 3/20 exact records; current Gate 3 baseline менялся 13/20 → 11/20 → 10/20 | Маленький mapping заметно стабильнее прямой генерации, но полный новый pipeline пока не победил |

## Где именно осталась свобода модели

### Schema mapping

Модель стабильно решила 16 структурных соответствий торговой таблицы. Добавление representative rows не помогло: все три joint запуска и все три split запуска были отвергнуты из-за недопустимого literal в `side` value binding.

Это важное разделение результатов:

- `header → normalized_role` доказан;
- `source side literal → PURCHASE/DISPOSAL` не доказан;
- mapping двух остальных таблиц использовался только как заранее frozen control, а не как результат этого модельного теста.

### Residual free text

Всего residual extractor получил 9 строк. Он должен был выбирать только закрытые semantic codes и короткие spans; date, amount и основную currency переносил код.

- Run 1: rejected — одной cash-строке назначен code итога торгов, несовместимый с типом таблицы.
- Runs 2–3: одинаковые, но 8/9 exact — в `NOT_RELEVANT` строке модель оставила лишний currency span.
- Compound coupon/withholding строки были распознаны без выдумывания суммы удержания.

Ошибка узкая и понятная, но repeatability неправильного ответа не является успехом.

## Semantic surface area

| Метрика | Direct projection | Кандидат compiler |
|---|---:|---:|
| Потенциальные semantic decisions | 107 | 46 |
| Schema column decisions | — | 27 |
| Schema value decisions | — | 2 |
| Residual semantic decisions | — | 17 |
| Runtime role values | 75 | 75 |
| Значения, привязанные чистым кодом | — | 69/75 (92%) |
| Source rows без row-level LLM | — | 3/12 (25%) |
| Source rows с residual LLM | 12/12 | 9/12 (75%) |

46 — это архитектурная поверхность полного frozen control для трёх таблиц. В живом эксперименте модельно доказаны только 16 header decisions одной таблицы; остальные mappings нельзя выдавать за подтверждённые.

## Fidelity, provenance и downstream

При frozen правильном mapping и frozen правильных residual decisions детерминированный assembler дал:

- 12/12 source dispositions;
- 20/20 exact typed facts;
- 0 missing и 0 extra facts;
- provenance для каждого runtime value;
- 20 records после первого и повторного SQL materialization, 0 дублей;
- достаточный набор полей для текущих Gate 5 consumers.

В живых ответах только runs 2–3 дошли до тех же 20/20 после материализации; run 1 был fail-closed. Это не даёт требуемой repeatability 3/3.

## Стоимость

Исследование выполнило 18 модельных вызовов: по шесть на каждый независимый run. Полные usage metadata сохранились для 9 вызовов:

- не менее 6 825 input tokens;
- не менее 2 823 output tokens;
- оставшиеся 9 вызовов не включены в token total, поэтому это только нижняя граница;
- денежная стоимость провайдером в доступном receipt не сообщалась.

Для возможного runtime это не означает 6 вызовов на документ. Целевой KISS-путь — один mapping только для нового exact fingerprint и один residual call на документ. Но такую стоимость пока нельзя обещать: cross-document reuse и полный mapping не доказаны.

## Архитектурный вывод

Не нужно возвращаться к прямому `Canonical → LLM → все typed records`. Там модель заново решает структуру, типы и значения каждой строки, из-за чего меняется итог.

Также рано внедрять весь исследованный compiler. Доказанная граница уже:

```text
Canonical headers → normalized column roles
```

Недоказанная граница ещё:

```text
source value semantics + residual wording → stable closed decisions
```

Canonical остаётся неизменяемым источником правды. Mapping и typed SQL projection должны быть отдельными перестраиваемыми sidecar/runtime артефактами.

## Следующий разрешённый узкий GOAL

Не расширять ontology и не улучшать direct comparator. Отдельно проверить две оставшиеся атомарные задачи:

1. `side literal → PURCHASE/DISPOSAL` как самостоятельный closed contract, не смешанный с header mapping;
2. residual extractor с контрактом владения spans: `currency_span` разрешён только для code, которому он нужен, а terminal codes обязаны иметь пустые spans.

Если обе задачи дадут 3/3 exact на frozen input, повторить end-to-end один раз и только тогда обсуждать runtime-интеграцию.

Машиночитаемый безопасный receipt: [BROKER_REPORTS_MINIMAL_SEMANTIC_COMPILER.receipt.json](./BROKER_REPORTS_MINIMAL_SEMANTIC_COMPILER.receipt.json)
