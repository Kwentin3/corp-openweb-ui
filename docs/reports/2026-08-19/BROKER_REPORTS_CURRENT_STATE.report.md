# Broker Reports → 3‑НДФЛ: текущее состояние

Дата снимка: 2026-08-19

Ревизия репозитория: `c1602276655d0fbf375b01b40896fa258a05dc76`

Серверный release: `broker-reports-91df75d2a4f1`

Класс документа: `STATUS SNAPSHOT / NOT ARCHITECTURE AUTHORITY`

Этот отчёт фиксирует фактическое состояние после серии исследований и
внедрения source-bound нормализации PDF-таблиц. Он не меняет контракты, не
активирует Gate 5 и не открывает следующий GOAL.

## Коротко: семь ответов

1. **Проблему таблиц решили?** Для проверенного класса текстовых PDF — да:
   модель только указывает границы таблиц, а структуру и исходные символы берёт
   pdfplumber. На неподдержанном документе система останавливается и не выдаёт
   неполный Canonical за правильный.
2. **Что реально работает на сервере?** Приём файла, Canonical, новый
   source-bound путь PDF-таблиц и Gate 3. Путь приватный, не глобальная Function.
3. **Что получает пользователь сейчас?** Нормализованный Canonical и результат
   Gate 3. Автоматического продолжения до расчёта, XML или PDF 3‑НДФЛ нет.
4. **Проверен ли целый документ глазами?** Да: полностью проверены один реальный
   шестистраничный и один публичный девятистраничный поддержанный отчёт. Это не
   гарантия для любого PDF.
5. **Есть ли честный полный прогон на реальных отчётах?** Есть прежний прогон
   четырёх реальных PDF от активного Canonical до Gate 5, но он не перестраивал
   Canonical новым финальным PDF-механизмом и остановился до расчётов.
6. **Где сейчас главный разрыв?** Финальный PDF-механизм и downstream Gate 3–5
   доказаны по отдельности, но ещё не соединены одним свежим реальным прогоном.
7. **Готов ли продукт «отчёты → 3‑НДФЛ»?** Нет. Нормализация таблиц стала
   рабочей и production-active; готовая декларация остаётся inactive и не
   квалифицирована на текущем реальном кейсе.

## Текущий путь PDF

```text
целая страница PDF
    ↓
VLM: только один box_2d для каждой видимой самостоятельной таблицы
    ↓
детерминированный перевод координат в PDF points
    ↓
pdfplumber: сетка, строки, столбцы, ячейки и исходные символы
    ↓
штатный валидатор табличной проекции
    ↓
Canonical с TABLE, source refs, merged spans и continuation metadata
```

VLM не возвращает текст, числа, строки, ячейки, настройки парсера или
финансовый смысл. Физические сегменты на разных страницах не склеиваются:
между ними сохраняется только проверяемая связь продолжения.

Если VLM увидела таблицу, а pdfplumber не смог построить подтверждённую
структуру, срабатывает `pdf_table_normalization_incomplete`: Canonical для этого
документа не публикуется, downstream блокируется, legacy не включается.

Canonical-контракт также принимает HTML, CSV и XLSX. Новая квалификация в этом
отчёте относится именно к PDF и не создаёт дополнительных заявлений о качестве
остальных форматов.

## Полнота по целым PDF

Статус: **PROVEN в пределах двух полностью проверенных поддержанных документов;
PARTIAL для произвольного корпуса**.

- Реальный отчёт, 6 страниц: 14 из 14 областей стали 14 физическими `TABLE`,
  представляющими 12 логических таблиц; 2 032 ячейки, 32 объединённые, 2 032 из
  2 032 source refs разрешены; 5 307 из 5 307 проверенных слов и чисел найдены
  на привязанной странице; все страницы сверены визуально.
- Публичный положительный отчёт, 9 страниц: 2 из 2 проекций, 72 ячейки, 72 из
  72 source refs и 146 из 146 проверенных исходных токенов; все страницы
  просмотрены, пропущенных таблиц не найдено.
- Публичный отрицательный отчёт: VLM нашла 3 области, pdfplumber подтвердил 0;
  опубликовано 0 версий Canonical, причина записана явно, legacy не применён.
- Cross-report holdout: 2 документа, 5 выбранных страниц, 3 из 3 положительных
  таблиц и 0 ложных таблиц на 2 отрицательных страницах. Это не полностью
  невиданный корпус; repeatability не проверялась; rotation не поддерживается.

Неподдержанные классы сейчас: таблица только как изображение, область без
достаточно явной структуры для строгого pdfplumber-сборщика и повёрнутые
страницы. Перенос внутри длинной ячейки может остаться несколькими физическими
строками; система не склеивает их по смыслу.

Основные доказательства: [итог внедрения](BROKER_REPORTS_CANONICAL_TABLE_CONTEXT_IMPLEMENTATION.report.md),
[аудит исходного реального PDF](BROKER_REPORTS_REAL_PDF_CANONICAL_AUDIT.report.md),
[holdout](BROKER_REPORTS_G5104_TABLE_INSTANCE_HOLDOUT.report.md) и
[контракт PDF-маршрута](../../stage2/contracts/BROKER_REPORTS_PDF_SOURCE_BOUND_TABLE_NORMALIZATION.v1.md).

## Матрица текущего конвейера

Статусы ниже означают не формальное закрытие исследовательского этапа, а
честную готовность текущего продукта. В архитектурной карте Gate 1–4 формально
закрыты, Gate 3 активен в NDFL, Gate 5 product status — inactive.

| Этап | Статус | Что доказано | Чего ещё нет |
|---|---|---|---|
| Gate 1: custody/intake | PROVEN | Источник принимается и привязывается без смыслового разбора | Не является OCR для image-only таблиц |
| Gate 2: Canonical | PARTIAL | Контракт, исходные ссылки и финальный PDF-табличный путь доказаны на квалифицированных документах | Не покрыты все классы PDF; неподдержанные документы fail closed |
| Adaptive Context | PARTIAL | Штатный владелец использовался в реальном четырёхдокументном replay | Не повторён после финального PDF-внедрения тем же полным прогоном |
| Gate 3: source semantics | PARTIAL | Активен; в реальном replay дал 391 аннотацию без retry/repair/fallback | Есть неполные роли и локальный нерешённый класс foreign-tax adjustment |
| Gate 4: normalized facts | PROVEN | Детерминированно материализовал 391 факт и сохранил неполноту без выдумывания | Полнота зависит от доказательств Gate 3 и источника |
| Gate 5: methodology/calculation | PARTIAL | Ограниченные детерминированные механизмы расчёта существуют и проверены отдельно | На текущем реальном replay 0 расчётов; product path inactive |
| Declaration Semantics | NOT ACTIVE | Синтетический sealed proof существует | Реальный кейс не sealed; пользовательские данные не собраны |
| Release | BLOCKED | Fail-closed граница работает | Текущий реальный кейс не готов к выпуску; live release port не активирован |
| XML projection | NOT ACTIVE | Синтетический XSD-valid proof существует | Не является текущим пользовательским результатом |
| PDF 3‑НДФЛ | NOT QUALIFIED | — | Текущего квалифицированного генератора и реального E2E-доказательства нет |

Владельцы и границы зафиксированы в
[Architecture Authorities](../../stage2/contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md),
[Pipeline Gates](../../stage2/contracts/BROKER_REPORTS_PIPELINE_GATES.v1.md),
[Canonical Artifact](../../stage2/contracts/BROKER_REPORTS_CANONICAL_ARTIFACT.v1.md),
[Gate 2 exit](../../stage2/contracts/BROKER_REPORTS_GATE2_EXIT_CONTRACT.v1.md) и
[Gate 4 handoff](../../stage2/contracts/BROKER_REPORTS_GATE4_HANDOFF.v1.md).

## Последний честный реальный E2E

Последний сохранённый replay —
[G5.76 от 2026-08-16](../2026-08-16/BROKER_REPORTS_FULL_CURRENT_CASE_END_TO_END_REPLAY_G5_76.report.md).
Он проверил четыре реальных PDF через активные Canonical, но **не перестраивал
Gate 1/Canonical с нуля** и предшествует финальному PDF-механизму от 2026-08-19.

Цепочка дала:

- 4 из 4 документов обработаны Gate 3 за 15 Gemini-вызовов, без retry,
  repair, fallback или ручного исправления;
- 391 аннотацию/факт;
- Gate 4: 329 role-complete и 62 incomplete;
- 96 security facts: 80 готовы, 16 имеют недостаточные исходные доказательства;
- Gate 5: 25 требований, из них 9 активны и все 9 заблокированы;
- 0 расчётов и 0 FIFO-результатов;
- Declaration Semantic Input — `NOT_SEALED`;
- release заблокирован, projection не запускался, XML и PDF не созданы.

Следовательно, нельзя складывать два разных доказательства в одно:

```text
финальный PDF → Canonical       доказан отдельно 2026-08-19
Canonical → Gate 3/4/5 blocker доказан отдельно 2026-08-16
единый свежий real E2E          ещё не выполнен
```

## Gate 5: что есть и чего нет

### Возможности в узкой области

- принимает только Gate 4 Fact v2 через штатный runtime;
- поддерживает ограниченный срез: налоговый период 2025, резидент, ценные
  бумаги вне ИИС на организованном рынке;
- группирует по точному активу и валюте, применяет FIFO по дате и
  пропорциональную стоимость приобретения;
- хранит комиссии по операциям и агрегаты раздельно, без скрытого смешивания;
- изолирует независимые группы: проблема одной группы не стирает готовые;
- имеет компоненты агрегации, расчёта налоговой базы и подготовки декларации;
- имеет синтетически доказанную XSD-проекцию XML.

### Жёсткие ограничения

- Gate 5 не читает PDF, Canonical или provider output напрямую;
- не вызывает LLM и не восстанавливает экономические связи догадкой;
- не считает неполные реальные группы «почти готовыми»;
- не распределяет частичную acquisition commission без методики;
- не имеет закрытой методики промежуточного округления non-RUB;
- не закрыты treaty-specific foreign tax credit и правила
  adjustment/refund/reversal/netting;
- не доказывает полноту сведений о налогоплательщике;
- не активен как полный продуктовый путь.

Контрактные опоры:
[deterministic source facts](../../stage2/contracts/BROKER_REPORTS_GATE5_DETERMINISTIC_SOURCE_FACT_CONSUMPTION.v0.md),
[real tax case](../../stage2/contracts/BROKER_REPORTS_GATE5_REAL_TAX_CASE_ASSEMBLY.v0.md),
[declaration preparation](../../stage2/contracts/BROKER_REPORTS_GATE5_DECLARATION_PREPARATION.v0.md),
[evidence/methodology bridge](../../stage2/contracts/BROKER_REPORTS_GATE5_EVIDENCE_TAX_METHODOLOGY_BRIDGE.v1.md),
[semantic input](../../stage2/contracts/BROKER_REPORTS_GATE5_DECLARATION_SEMANTIC_INPUT.v0.md) и
[full-target XML](../../stage2/contracts/BROKER_REPORTS_GATE5_FULL_TARGET_XML_PROJECTION.v0.md).

## Реальные блокеры и их область

| Блокер | Владелец/этап | Что именно блокирует |
|---|---|---|
| Image-only, повёрнутая или структурно неоднозначная PDF-таблица | Gate 2 | Только текущий неподдержанный документ; Canonical не публикуется |
| Нет единого свежего replay всех последних owners | E2E qualification | Только право заявлять текущий полный E2E; уже доказанные локальные свойства не отменяет |
| Недостаточные quantity/acquisition evidence | Gate 5 evidence demand | Только затронутую пару актив/валюта и зависимый FIFO |
| Неполная документная/фактовая роль | Gate 3 → Gate 4 | Только затронутые факты и зависимые расчётные группы |
| Невалидное decimal-значение | Gate 4 | Только затронутый факт и его потребителей |
| Резидентство и его интервалы | Пользователь/кейс → Gate 5 | Только методы, зависящие от резидентства |
| Идентичность налогоплательщика | Пользователь/кейс → declaration preparation | Полноту декларации, но не PDF-нормализацию и не независимый FIFO |
| Подписант и экземпляр подачи | Declaration Semantics/Release | Только выпуск декларации |
| Округление, частичная комиссия, treaty/foreign-tax adjustment | Gate 5 methodology | Только соответствующие расчётные группы |

Известный semantic gap не следует объявлять глобальной поломкой. В G5.90 он
локализован в foreign-tax adjustment. Неактивный кандидат G5.91 распознал
правильно 53 из 105 наблюдений, а 52 ошибочно назвал `DIVIDEND`; G5.92 ухудшил
результат до 26 из 105 и был отклонён. Текущие Dictionary 2.0.1 и Role Pack
3.0.0 не заменялись. Доказательства:
[G5.90](../2026-08-17/BROKER_REPORTS_FOREIGN_TAX_ADJUSTMENT_METHODOLOGY_G5_90.report.md),
[G5.91](../2026-08-17/BROKER_REPORTS_MINIMAL_TAX_OBSERVATION_SOURCE_CONTRACT_G5_91.report.md) и
[G5.92](../2026-08-17/BROKER_REPORTS_PREDECLARED_ATOMIC_ASSERTIONS_G5_92.report.md).

## Что было проверено и отвергнуто

1. **Усиление parser-only эвристик.** Не давало устойчивой навигации по сложным
   таблицам. Сохранили pdfplumber как источник символов, но не как зрение.
2. **VLM как OCR и источник значений.** Структура лучше, литералы хуже.
   Оставили модели только координаты.
3. **Сетка поверх страницы.** Добавляла промежуточный язык и ошибки перевода,
   хотя pdfplumber уже понимает нативные PDF-координаты.
4. **Dual-VLM, best-of-N и semantic fallback.** Усложняли выбор authority и
   маскировали неповторяемость. В production они выключены.
5. **Breadcrumbs и прямое визуальное извлечение body.** Не сохраняли строгую
   адресуемость и источник каждого литерала.
6. **Predeclared assertions для tax adjustment.** Контролируемый тест стал хуже;
   гипотеза отклонена, текущий словарь не изменён.

## Архитектурные инварианты

Проверка `test_broker_reports_gate_architecture.py` на снимке: **31 passed**.

- Gate 2 не принимает финансовые решения.
- Gate 3 не применяет налоговую методику.
- Gate 4 не делает налоговых выводов.
- Детерминированные owners Gate 5 не читают PDF/Canonical и не вызывают LLM.
- Projection не рассуждает и не исправляет смысл.
- VLM не публикует литералы в Canonical.
- Производственный PDF-маршрут не содержит правил конкретного брокера или
  конкретной страницы.
- Новых схем, хранилищ, парсеров или владельцев смысла не создано.

`architecture_invariant_violations`: **нет**.

Известный неблокирующий долг: inactive proof-orchestrator
[`gate5_end_to_end_full_target_xml.py`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_end_to_end_full_target_xml.py)
физически лежит под `gate5_` и импортирует Canonical/provider для полного
proof-пути. Он явно allowlisted в Pipeline Gates как compatibility debt и не
является semantic owner Gate 5.

## Где что живёт

| Класс | Текущее содержимое |
|---|---|
| Research-only | Старые grid, dual-VLM, hybrid, breadcrumb, semantic visual и predeclared-assertion эксперименты |
| Maintained inactive | Gate 5 methodology/calculation, Declaration Semantics, release/projection/XML, полный product path |
| Public runtime code | Canonical/table route и NDFL Gate 3 factories |
| Production-active | Приватная `broker_reports_gate1_pipe`, Canonical write/read, Gate 3 и `pdf_table_intake_enabled` |

Read-only серверная проверка подтвердила release
`broker-reports-91df75d2a4f1`, точное совпадение bundle/runtime с ревизией
`91df75d2a4f143cce2ca05a18c73cde48c54fd29`, чистый контейнер и отсутствие
рестартов. Активные switches: Canonical write/read, Gate 3 и PDF table intake.
Выключены: `ndfl_full_product_enabled`, dual-VLM, hybrid, semantic visual table
downstream и structural repair shadow. Проверяющий скрипт:
[`live_verify_broker_reports_atomic_stage_release.py`](../../../services/broker-reports-gate1-proof/scripts/live_verify_broker_reports_atomic_stage_release.py).

## Сложность без прикрас

Рабочая цепочка всё ещё большая, но её владельцы разделены: custody, Canonical,
табличный locator, pdfplumber projection, Gate 3 labels, Gate 4 facts, Gate 5
методика, declaration definition и projection/XSD. Модель используется только
в двух ограниченных местах: VLM находит таблицы, LLM Gate 3 присваивает
source-semantic labels. После Gate 4 расчёт должен быть детерминированным.

Главный технический долг — множество старых выключенных флагов, imports и
research-путей рядом с активной Pipe. Они не участвуют в результате, но
усложняют чтение и сопровождение. Удалять их в рамках этой инвентаризации нельзя:
это отдельное изменение с отдельным доказательством.

## Итог

**Задача сохранения контекста таблиц решена для квалифицированных текстовых PDF
и новый механизм реально активен на сервере. Задача продукта «брокерские
отчёты → готовая 3‑НДФЛ» ещё не решена.**

Следующее решение должен принять пользователь: разрешить ли один отдельный
свежий replay реального кейса от сырых PDF через все последние owners до
честного terminal outcome. Этот отчёт такого GOAL не создаёт и ничего не
активирует.
