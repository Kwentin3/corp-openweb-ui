# PDF Structural Repair: итог рефакторинга

> Historical snapshot. The `accepted_unique_consensus` wording below records
> deprecated v1 artifact names and does not prove global uniqueness. Current
> supplied-hypothesis semantics are defined by
> `docs/stage2/contracts/BROKER_REPORTS_PDF_STRUCTURAL_REPAIR_CONSENSUS.v2.md`;
> current readiness is in the 2026-07-15 structural-and-semantic closeout.

Дата: 2026-07-14

Итоговый статус: **PARTIAL**.

- Реализация автоматического контура: готова.
- Безопасные ошибки для пользователя и LLM: готовы.
- Локальные тесты, live canary и repo/live parity: пройдены.
- Точность на новом независимом наборе: не пройдена, `0/3`.
- Включение результата в production Gate 2 selection: не разрешено.

## Коротко простыми словами

Старый подход «parser уже решил, где строки и колонки, а LLM только переставляет ячейки» убран из нового пути.

Теперь parser сохраняет точные слова и координаты, а модель независимо смотрит на картинку таблицы и предлагает только её геометрию. После этого обычный детерминированный код проверяет обе версии, собирает таблицу и принимает её лишь при единственном непротиворечивом результате.

Механизм теперь действительно автоматический: сам считает бюджет, делает ровно две независимые попытки, умеет разбивать большие таблицы на окна, соединять продолжение на соседней странице, сохранять историю конфликтов и объяснять безопасную причину отказа. Но на трёх новых реальных таблицах он пока не смог принять ни одну. Поэтому механика исправна, а качество ещё не доказано.

## Что реализовано

### 1. Независимые parser и visual oracle

Модель получает crop и анонимные атомы `id + bbox + order`. Она не получает значения, готовую parser-сетку, эталонный ответ или source refs.

Parser хранит точные значения, координаты, порядок и provenance, но не назначает финальные строки и колонки. Детерминированный assembler и solver:

- проверяют границы, spans и иерархию заголовков;
- требуют ровно одного владельца для каждого атома;
- не разрешают придумывать или исправлять значения;
- возвращают typed terminal вместо «лучшего похожего» ответа.

### 2. Реальные provider calls без скрытой магии

Для одной обычной таблицы runtime делает:

1. `countTokens`;
2. generate attempt 1;
3. `countTokens`;
4. generate attempt 2;
5. детерминированный consensus и materialization.

Скрытые retries, provider failover и дополнительный вызов при continuation запрещены и проверяются журналом.

### 3. Лимит `1000` и вертикальные окна

- `1..192` атома: таблица обрабатывается целиком, `2 + 2` provider calls;
- `193..1000`: полные по ширине вертикальные окна максимум по `192` owner-атома;
- больше `1000` или небезопасный разрез: typed block.

Для `W` окон разрешено ровно `2W` `countTokens` и `2W` generate calls. Окна склеиваются только внутри одной попытки; attempt 1 и attempt 2 смешивать нельзя. Все owner-наборы обязаны без пропусков и дублей покрыть исходный порядок атомов.

Сохранены прежние предохранители на каждое окно: `48 KiB` model JSON, `18,000` static tokens, `20,000` counted input tokens, `8 MiB` изображения и `8,192` output tokens.

### 4. Широкие, многострочные и продолжающиеся таблицы

Локально доказана таблица `3 x 12` с многострочными значениями и точным владением атомами.

Continuation discovery использует только parser/geometry и принимает сейчас ровно два соседних фрагмента. Оба фрагмента сначала обязаны независимо пройти consensus. После этого join:

- не вызывает LLM повторно;
- сохраняет порядок строк и subtotal;
- не удаляет строку на границе без разрешённой repeated-header политики;
- корректно сдвигает headers и spans;
- повторно проверяет provenance, ownership и отсутствие придуманных значений.

### 5. Ошибка по каждому файлу видна человеку и LLM

Для каждого входного файла создаётся закрытый safe outcome:

- стадия сбоя;
- безопасный reason code;
- можно ли повторить;
- что делать дальше;
- короткое русское сообщение пользователю.

Тот же safe outcome входит в passport-контекст LLM. Поэтому при ошибке DOC/PDF модель может объяснить, что именно произошло. В этот контекст не попадают raw exceptions, пути, customer values, crop bytes или ответы провайдера — они остаются private diagnostics.

### 6. История повторов и конфликтов

Repeat history стала append-only в точном scope parser/crop/model/runtime/window/solver. Номер события монотонный. Если когда-либо был конфликт, `ever_conflicted=true` нельзя стереть последующим удачным запуском. Подмена scope или checksum блокирует выполнение.

### 7. Границы production сохранены

- OpenWebUI core не менялся.
- Knowledge/RAG и OCR не добавлялись.
- Production Gate 2 selection и authority не менялись.
- Новый Gate 1 structural shadow по умолчанию выключен.
- Gate 2 bundles обновлены только до repo/live parity; live domain proof подтвердил `candidate_binding_enabled=false`.

## Независимая проверка качества

### Исторический replay

Запечатанные development-ответы дали `3/3` принятых таблицы, `147/147` точных диагностических ячеек и `178/178` атомов ровно по одному разу. Новых provider calls не было. Это доказывает работоспособность assembler/solver на известных примерах, но не обобщение.

### Fresh holdout v2

Первый оконный fresh run обнаружил дефект протокола: одна ранняя семантически неверная оконная реакция останавливала оставшееся расписание. Runtime исправлен так, чтобы после generate-ошибки закончить все заранее разрешённые окна и попытки; budget/preflight block по-прежнему останавливается до generate.

### Fresh holdout v3

Семь новых официальных PDF не дали ни одной parser-only цели, подходящей под заранее замороженную eligibility policy. Ручная подмена удобной страницы не выполнялась, provider не вызывался. Этот набор не использовался как доказательство точности.

### Финальный fresh holdout v4

Корпус состоял из семи новых официальных PDF и был отделён по SHA-256 от всех прежних наборов, включая [Alpaca](https://files.alpaca.markets/disclosures/library/Alpaca_Securities_062023_Public_08072023.pdf), [Robinhood](https://cdn.robinhood.com/assets/robinhood/legal/RHS-Audited-Statement-of-Financial-Condition.pdf), [Ameriprise](https://www.ameriprise.com/binaries/content/assets/ampcom/pdf/aeis-statement-of-financial-condition-_-december-31_-2025.pdf), [Edward Jones](https://www.edwardjones.com/sites/default/files/dam/yainnhfhs4/mpo-2170d-a-e-cc.pdf) и [Stifel](https://www.stifel.com/docs/pdf/disclosures/financialcondition/202512.pdf).

Parser-only pre-registration заранее выбрал три таблицы Edward Jones. Результат запечатанного запуска:

| Проверка | Результат |
|---|---:|
| `countTokens` | `6/6` |
| Generate calls | `6/6` |
| Hidden retries | `0` |
| Provider failovers | `0` |
| Придуманные значения | `0` |
| Принятый unique consensus | `0/3` |

После terminal seal человек независимо разметил все три crop как поддерживаемые таблицы: две простые и одну с двухуровневым merged header. Эталон не был доступен solver. Post-terminal scorer подтвердил неизменность terminal и показал:

- supported targets: `3`;
- доступные accepted bindings: `0`;
- точные topology: `0/3`.

Это главный результат исследования: автоматический контур честно работает и безопасно отказывается, но пока не распознаёт новые реальные таблицы с требуемой точностью.

Private evidence:

- preregistration, run, reference and score remain in the ignored private
  evidence root.

### Development regression после windowing

Цели `157`, `330` и `72` атома выполнили ровно `8/8` `countTokens` и `8/8` generate calls. Таблица `330` атомов прошла через два окна и дала две склеенные oracle-гипотезы. Все три результата остались `no_valid_consensus`, invented values — `0`.

Этот прогон дополнительно нашёл ошибку терминального валидатора: он отвергал законную склейку только attempt 2 после плохого ответа attempt 1. Условие исправлено без смешивания попыток; добавлен terminal test.

Evidence: ignored private development evidence root (path withheld).

## Live OpenWebUI

### Gate 1 structural canary

Успешный canary: ignored private evidence root (path withheld).

- Live bundle SHA: `4c5d5005bce561e41b2ca50df58b0d958a070b694c9c163471c66b22af1fb150`.
- Два synthetic фрагмента: `2/2 accepted_unique_consensus`.
- Вызовы: `4 countTokens + 4 generate`.
- Continuation: `1/1`, результат `8 x 3`, новых provider calls `0`.
- Candidate ownership exact, invented values `0`.
- Chroma/RAG table counts не изменились.
- Upload удалён по id и уникальному alias.
- Valves точно возвращены в исходное disabled-состояние.

Две ранние canary-попытки тоже сохранены как отрицательное доказательство: первая остановилась до мутации на временном SSH/SQLite timeout; вторая прошла тело, но ошибочно сравнивала новый frontmatter со старой manifest metadata, после чего точно откатила content SHA и valves. Проверка metadata исправлена и покрыта тестом.

### Общая parity и Gate 2

Финальный live verifier: `passed`.

| Function | Repo/live SHA |
|---|---|
| Gate 1 | `4c5d5005...fb150` |
| Gate 2 source fact | `c6594db1...b5953` |
| Gate 2 domain | `0ecfd182...3fe5b` |

Все 12 managed prompts совпали с репозиторием; `PyMuPDF 1.26.5` доступен; structural shadow disabled.

Gate 2 live smoke:

- full-union: `3/3` пакета, все 9 типов фактов, cleanup `43` записей;
- domain-routed: `9/9` пакетов, `candidate_binding_enabled=false`, cleanup `81` запись;
- typed segmentation: один complete private derived unit, точное partition coverage, cleanup `29` записей;
- во всех трёх: no RAG/vector/document/file delta, strict structured output, fallback не использовался.

Первый full-union smoke безопасно отверг устаревшую автоматически выбранную модель. Entry points переведены на общий Gate 2 provider registry; повтор использовал разрешённый `gpt-5.6-luna` и прошёл.

## Проверки кода

- `526 passed`, `5 warnings` за `43.73s`;
- `compileall` — успешно;
- Gate 1/Gate 2 bundles пересобираются детерминированно;
- closed-world Gate 2 bundle не импортирует новые Gate 1-only structural modules;
- factory bypass, hidden retry/failover, reference leakage и snapshot-only acceptance покрыты отрицательными тестами.

## Что остаётся

Нового инфраструктурного рефакторинга для запуска контура не требуется. Осталась именно задача качества:

1. Разобрать три fresh v4 failure по boundary/span/unsupported причинам, не используя значения как подсказку для topology.
2. Улучшить visual topology/assembly policy общим правилом, а не исключением под Edward Jones.
3. После новой source freeze собрать ещё один полностью неизвестный официальный корпус.
4. Сначала запечатать terminal, затем создать reference и потребовать точную topology на всех поддерживаемых целях.
5. До такого результата оставить shadow disabled и не подключать его к Gate 2 selection.

Отдельные будущие расширения — цепочки continuation длиннее двух страниц и empty merged region без source anchor. Они не должны смешиваться с текущей задачей точности.

## Финальный вывод

Цель «уйти от ручного запуска и дать LLM понятную ошибку» достигнута. Цель «автоматически собирать новые реальные PDF-таблицы достаточно надёжно для production» пока не достигнута.

Поэтому итог **PARTIAL**, а не `PRODUCTION_READY`: система теперь честно автоматизирована, наблюдаема и безопасна, но качество независимого fresh holdout равно `0/3`.
