# Broker Reports: аналитика закрытия restricted scope, блокеры и предложения

Дата среза: 2026-07-20

Статус программы: **NOT_CLOSED**

Основание статуса: не выполнен точный инвариант `visual_scopes_canonical_11_of_11`.

## 1. Резюме для принятия решения

Основной объем инженерной работы завершен и подтвержден на actual corpus. Полностью закрыты цели 0, 1, 2 и 5. Цель 4 закрыта для всех принятых областей с явно сохраненным ограничением цели 3. Из 11 заявленных материальных визуальных областей канонизированы 10; они дали 17 валидных таблиц и 623 ячейки. Все 17 визуальных пакетов прошли Gate 2.

Программа остается в статусе `NOT_CLOSED` по одной конкретной причине: одиннадцатая заявленная материальная область указывает на страницу 8 из 19, которая в двух точных копиях исходного PDF не содержит ни потока данных, ни текста, ни изображений, ни графики, ни видимых пикселей. Восстановление таблицы из имеющихся байтов невозможно без выдумывания фактов. Это корректное fail-closed ограничение, а не незакрытый дефект OCR или профиля таблиц.

Отдельно существует внешний долг приемки Sber: нет ни одного авторизованного genuine unseen same-family positive holdout. Он не отменяет доказанную работу на 14 actual-corpus регионах и не должен блокировать уже закрытые независимые цели. Он блокирует только утверждение об обобщении профиля и включение релизного клапана, который сейчас корректно выключен.

Краткое решение:

1. Не ослаблять критерий `11/11` и не исключать пустую страницу из знаменателя.
2. Запросить у владельца источника исправленный авторизованный PDF с видимым содержимым целевой страницы.
3. Параллельно запросить у заказчика один авторизованный unseen same-family Sber PDF.
4. До получения этих входов оставить Sber-клапан выключенным, а принятые контуры эксплуатировать только в явно подтвержденных границах.
5. Не начинать широкую переработку архитектуры: текущие блокеры не указывают на системный дефект реализации.

## 2. Как читать текущий статус

Оставшиеся ограничения относятся к разным уровням и требуют разных владельцев.

| Уровень | Текущий статус | Что блокирует | Владелец |
| --- | --- | --- | --- |
| Инженерное закрытие exact scope | Заблокировано | Точный критерий визуальных областей `11/11` | Владелец исходного документа |
| Готовность принятых actual-corpus контуров | Подтверждена с одним явным ограничением | Только непринятая пустая визуальная область | Команда продукта контролирует fail-closed режим |
| Обобщение Sber-профиля | Не доказано | Заявление о работе на unseen same-family документе | Заказчик, предоставляющий holdout |
| Релиз Sber-профиля | Заблокирован клапаном | Включение профиля в live-контуре | Владелец релиза после приемки holdout |
| Клиентская приемка | Не выполнена | Формальное утверждение customer acceptance | Заказчик |

Такое разделение важно: формулировка «два блокера программы» технически верна для сводного реестра, но недостаточна для управления. Пустая визуальная область — единственный блокер точного инженерного критерия закрытия. Sber holdout — внешний acceptance/release debt; он не является дефектом текущей реализации.

## 3. Контур доказательства

```text
104 source records / 80 logical documents
        |
        +-- 24 ZIP containers --> lineage only --> 48 promoted members
        |
        +-- CSV / HTML / supported PDF --> Gate 1 document memory
        |
        +-- 24 FNS XML --> typed adapter --> 24 outputs / 351 facts
        |
        +-- visual-only scopes --> bounded recovery --> 17 accepted tables
        |                                          --> 1 blocked empty scope
        v
Gate 2 source-local packages --> validation --> stage bundle parity / smoke
        |
        +-- Sber profile remains behind disabled release valve
```

Доказательство строилось по закрытому контуру: source-local обработка, фабричные маршруты, неизменяемый ArtifactStore, нулевые provider calls, отсутствие Knowledge/RAG и векторизации. В safe-отчеты не выгружались значения клиента, приватные пути, имена файлов и сырые идентификаторы источников.

## 4. Статус целей

| Цель | Статус | Фактический результат | Остаток |
| --- | --- | --- | --- |
| Goal 0 — Sber freeze, debt, release isolation | **completed** | Профиль и валидатор зафиксированы; долг формализован; клапан по умолчанию выключен | Один внешний positive holdout до доказательства обобщения и релиза |
| Goal 1 — ZIP lineage handoff | **completed** | 24/24 ZIP остаются контейнерами lineage-only; 48 членов продвинуты без потерь | Нет |
| Goal 2 — FNS typed adapter и parity | **completed** | 24/24 XML дали терминальные типизированные результаты; parity детерминированно пройдена | Нет |
| Goal 3 — visual recovery | **NOT_CLOSED, correctly restricted** | 10/11 областей приняты; 17 таблиц интегрированы; одна область доказанно пуста | Исправленный авторизованный источник |
| Goal 4 — readiness reconciliation | **completed for accepted scopes** | 29 исторических ошибок классифицированы; текущие Gate 2 errors/warnings и unexplained errors равны нулю | Полное безусловное закрытие зависит от Goal 3 |
| Goal 5 — delivery, live alignment, hygiene | **completed** | Bundle/prompt parity, stage smokes, тесты и Git-гигиена пройдены | Нет |

## 5. Аналитика actual corpus

### 5.1. Учет источников

| Метрика | Значение |
| --- | ---: |
| Source records | 104 |
| Logical documents | 80 |
| CSV | 2 |
| HTML | 4 |
| PDF | 50 |
| XML | 24 |
| ZIP | 24 |
| Lineage-only containers | 24 |
| Promoted archive members | 48 |
| Source-ready / packageable documents | 75 / 75 |
| Unexplained readiness errors | 0 |

Разница между 104 source records и 80 logical documents объясняется контейнерной и дубликатной семантикой, а не потерями. Все 104 записи прошли учет, 24 ZIP не были ошибочно превращены в source-fact пакеты, а их 48 продвинутых членов сохранили lineage.

### 5.2. Базовая подготовка Gate 2

| Метрика | Значение |
| --- | ---: |
| Построено и принято пакетов | 681 |
| Документов с пакетами | 75 |
| Минимум / среднее / максимум пакетов на документ | 1 / 9,08 / 65 |
| Full source unit packages | 667 |
| Canonical table projection packages | 14 |
| Validator errors / warnings | 0 / 0 |
| Duplicate package IDs | 0 |
| Provider calls / tokens / cost | 0 / 0 / 0 |

Распределение выбранных областей:

| Scope | Количество |
| --- | ---: |
| `canonical_projection_anchor` | 14 |
| `canonical_table` | 55 |
| `neutral_structure` | 24 |
| `text` | 602 |

В базовом Gate 2 срезе 180 неканонических table candidates были корректно заблокированы, а 63 visual candidates отложены из-за отсутствия потребителя в этом конкретном baseline-прогоне. Это не противоречит более позднему визуальному доказательству: принятые visual result refs были переданы явно и дали 17 валидных пакетов на disposable clone. Складывать 681 и 17 в одну метрику одного прогона некорректно, поскольку это разные доказательные срезы.

### 5.3. FNS 2-НДФЛ

| Метрика | Значение |
| --- | ---: |
| XML packages | 24/24 |
| Terminal typed outputs | 24/24 |
| Typed facts | 351 |
| Structural variants | 17 |
| Paired representation groups | 24/24 |
| Deterministic replays | 24/24 |
| Preserved PDF candidates | 180 |
| Unmatched material errors | 0 |

Состав 351 типизированного факта:

| Семейство фактов | Количество |
| --- | ---: |
| `certificate_metadata` | 24 |
| `deduction_source_row` | 70 |
| `income_source_row` | 119 |
| `recipient_identity` | 24 |
| `source_certificate_identity` | 24 |
| `tax_agent_identity` | 24 |
| `tax_summary_source_fact` | 66 |

PDF candidates сохранены как recovery-deferred и не были ложно канонизированы. Это консервативное решение: XML обеспечивает проверенное материальное покрытие, а недоказанная PDF-реконструкция не повышается до источника фактов.

### 5.4. Визуальные таблицы

| Метрика | Значение |
| --- | ---: |
| Claimed material scopes | 11 |
| Accepted unique scopes | 10 |
| Accepted canonical regions/tables | 17 |
| Accepted cells | 623 |
| Immutable result artifacts | 18 |
| Accepted / blocked artifacts | 17 / 1 |
| Gate 2 visual packages passed | 17/17 |
| Documents with canonical visual input | 5 |
| Model canonical authority | false |
| Whole-document provider uploads | 0 |

Одна детерминированная область и девять reviewed visual областей приняты. Сложный layout дал пять принятых регионов. Negative non-table проверка не дала ложных повышений. Один blocked artifact не потерян и не скрыт: он сохраняет терминальное ограничение для пустой страницы.

## 6. Readiness и качество

Исторические 29 readiness errors полностью разложены по причинам:

- 24 ошибки `missing representation` устранены восстановлением правильного порядка «document memory до usage classification»;
- 4 ложных объявления visual-only документов как source-ready устранены контрактным ограничением;
- 1 агрегатная ошибка packageability устранена полным Gate 2 validator;
- 17 визуальных canonical handoff-проблем закрыты явной интеграцией immutable visual results;
- 1 сложный layout-профиль закрыт проверенным reviewed visual результатом;
- необъясненных текущих ошибок — 0.

Контроль качества:

| Проверка | Результат |
| --- | ---: |
| Bundle tests | 28 passed |
| Focused visual/readiness tests | 43 passed |
| Full regression | 968 passed |
| Dependency deprecation warnings | 5 |
| Ruff на затронутых Python-файлах | passed |
| Restricted stage smoke | 15 passed |
| Approved `process=false` chat smoke | 30 passed |

Пять предупреждений относятся к dependency deprecations и не представлены как ошибки продукта. Их стоит учитывать как плановый технический долг, но они не являются текущим блокером программы.

## 7. Производительность и ресурсный профиль

| Контур | Wall time | Peak RSS | Комментарий |
| --- | ---: | ---: | --- |
| Gate 1 normalization | 1 190,18 с | — | Основная стоимость нормализации actual corpus |
| Gate 1 actual proof | 1 374,29 с | 7 434 231 808 B, около 6,92 GiB | Самый тяжелый по памяти подтвержденный прогон |
| Broker PDF actual full replay | 1 304 с | 4 995 956 736 B, около 4,65 GiB | Полный профильный replay |
| Gate 2 package preparation v3 | 111,96 с | 4 011 618 304 B, около 3,74 GiB | 681 пакет, provider latency 0 |
| Visual recovery + integrated Gate 2 | 513,04 с | 4 122 152 960 B, около 3,84 GiB | 17 принятых visual packages, один fail-closed scope |
| FNS adapter, два прохода | 0,629 с | — | 24 результата, около 76 outputs/s |

### Наблюдения

1. По корректности контур устойчив: timeout, truncation, duplicate payload reads и per-ref full index scan не обнаружены.
2. Gate 2 прочитал около 1,37 GB с диска и записал около 11,1 MB. Нагрузка преимущественно read/CPU-bound, а не provider-bound.
3. В Gate 2 45 PDF parent validation были переиспользованы через 532 cache hits. Это подтверждает, что повторная полная валидация родительского PDF на каждую ссылку устранена.
4. Из 111,96 секунды Gate 2 около 67,40 секунды, или 60%, занимает reconciliation; около 42,16 секунды, или 38%, — построение и валидация пакетов. Если оптимизация понадобится, начинать следует с reconciliation, не с provider-кода.
5. Текущий Gate 2 v3 в 2,11 раза медленнее зафиксированного предыдущего значения 53,15 секунды. Это наблюдение нельзя автоматически объявлять регрессией: отсутствует подтверждение идентичности workload fingerprint, ревизии и условий измерения. Нужен контролируемый повтор на одном железе.
6. Пиковая память Gate 2 и visual-контура находится около 4 GiB, Gate 1 — около 7 GiB. Это приемлемо на доказательной машине с 34 GB RAM, но не доказывает безопасную плотность параллельных production workers.

### Практическая рекомендация по ресурсам

До отдельного capacity test разумно резервировать не менее 10 GiB RAM на один изолированный тяжелый worker либо ограничивать одновременные тяжелые прогоны. Это не новый контракт и не основание менять timeout; это консервативный эксплуатационный запас поверх измеренного пика 6,92 GiB.

## 8. Блокер №1: byte-uniform visual source

### Факты

| Проверка | Результат |
| --- | ---: |
| Source identity records | 2 |
| Exact source binary copies | 2 |
| Unique source binary hash | 1 |
| Target page | 8 из 19 |
| Contentful other pages | 18 |
| Content streams / bytes | 0 / 0 |
| Text characters | 0 |
| Images / XObjects | 0 / 0 |
| Drawings / links / annotations | 0 / 0 / 0 |
| Non-white pixels | 0 |
| Pixel standard deviation | 0,0 |

PyMuPDF 1.26.5 и pypdf 6.7.5 дают согласованный результат. Рендеры PyMuPDF на 72, 144, 288 и 300 DPI белые; MediaBox и CropBox совпадают; alpha-render не содержит видимых пикселей. Два нормализованных ArtifactStore render пиксельно совпадают с независимым source render.

### Анализ причины

Корневая причина находится до программного контура: авторизованный исходник не содержит заявленного визуального материала. Увеличение DPI, смена OCR, другой crop, ротация, иной renderer или LLM не создадут отсутствующие байты. Восстановление по соседним страницам было бы генерацией неподтвержденных фактов.

### Почему ограничение корректно

- область остается заявленной материальной и не исключена из знаменателя;
- модель не имеет canonical authority;
- adjacent-page inference запрещен;
- ArtifactStore не изменялся;
- blocked terminal artifact сохранен;
- exact invariant остается ложным, а не маскируется частичным успехом.

### Владелец и минимальное действие

Владелец: авторизованный владелец источника.

Минимальное действие: подтвердить происхождение и заменить исходный PDF на авторизованную версию, где целевая страница содержит видимый материал. Простое подтверждение того, что страница действительно пуста, объяснит расхождение, но не позволит получить таблицу и не закроет `11/11`.

### Критерии приемки замены

1. Подтверждена авторизованная identity нового источника.
2. Целевая страница содержит видимое source evidence.
3. Перестроены source hash и page-render lineage.
4. Bounded visual recovery дважды дает идентичный результат.
5. Canonical-table validator проходит без ошибок.
6. Gate 2 visual-package validator проходит без ошибок.
7. Итоговый счетчик становится ровно `11/11`, без изменения знаменателя.

## 9. Блокер №2: Sber positive holdout

### Факты

| Проверка | Результат |
| --- | ---: |
| Actual-corpus canonical regions | 14 |
| Profile | `supported_broker_pdf_neutral_table_profile_v1` |
| Статус на actual corpus | implemented and validated |
| Authorized unseen same-family holdouts | 0 |
| Release valve | `broker_pdf_neutral_table_profile_v1_enabled=false` |

### Анализ границы

Текущий corpus доказывает реализацию на известных actual-corpus входах, но не независимое обобщение на unseen same-family документе. Синтетический файл, публичный фрагмент изображения или повторно использованный известный PDF не являются заменой holdout, потому что не проверяют заявленный риск переобучения правил под текущий корпус.

### Владелец и минимальное действие

Владелец: заказчик.

Минимальное действие: предоставить один авторизованный genuine unseen same-family Sber PDF через существующий приватный intake-контур.

### Критерии приемки holdout

1. Подтверждены авторизация и отсутствие файла в обучающем/настроечном корпусе.
2. Замороженные profile/reconstruction/validator rules не меняются до первого результата.
3. Maintained private path выполняется дважды с идентичным терминальным результатом.
4. Проверяются headers, rows, columns, totals, annotations и continuations.
5. Gate 2 accounting и validators проходят без ошибок.
6. После сборки подтверждается repository/live parity.
7. Только после положительного результата принимается отдельное решение о включении клапана.

## 10. Риски

| Риск | Вероятность | Влияние | Текущий контроль | Предложение |
| --- | --- | --- | --- | --- |
| Исправленный visual source не будет предоставлен | Средняя | Высокое для exact closure | Fail-closed `10/11` | Формальный intake-запрос с шестью техническими критериями |
| Holdout окажется не unseen или не same-family | Средняя | Высокое для валидности приемки | Release valve выключен | Проверка provenance до запуска; не менять frozen rules |
| Попытка «закрыть» пустую область соседними данными | Низкая при текущих guards | Высокое для достоверности | Model authority false; denominator неизменен | CI-инвариант против reclassification и adjacent inference |
| Недостаток RAM при параллельных тяжелых прогонах | Средняя | Среднее/высокое эксплуатационное | Измерены пики 3,74–6,92 GiB | Capacity test и лимит concurrency |
| Ошибочная трактовка 111,96 с как доказанной регрессии | Средняя | Среднее | Есть phase metrics и fingerprint | Три сопоставимых прогона на одном окружении |
| Расхождение repository/live после будущих изменений | Низкая | Высокое | Exact bundle/prompt parity | Сохранять parity как обязательный release gate |
| Попадание private evidence в Git или отчет | Низкая | Высокое | Safe projections, privacy checks | Оставить автоматическую проверку путей, payload и media |
| Dependency deprecations накопятся до несовместимости | Средняя на горизонте обновлений | Среднее | 5 warnings видимы в regression | Отдельный плановый upgrade без смешивания с blocker closure |

## 11. Предложения по приоритетам

### P0 — закрыть входные блокеры без изменения реализации

1. **Visual source correction intake.** Отправить владельцу источника короткий запрос: идентификатор заявленной области, факт пустоты страницы, требование авторизованной замены и критерии приемки. Не передавать в запросе customer values или внутренние пути.
2. **Sber holdout intake.** Запросить один файл с явным подтверждением `authorized`, `genuine`, `unseen`, `same-family`. До его получения не менять профиль и не включать клапан.
3. **Разделить статусы.** В сводных отчетах хранить отдельно `program_exact_scope_closure`, `actual_corpus_readiness`, `same_family_generalization`, `release_activation` и `customer_acceptance`. Это устранит ложное впечатление, что внешний holdout обесценивает закрытые цели.

### P1 — усилить повторяемость и эксплуатационную уверенность

1. **Controlled benchmark.** Трижды повторить Gate 2 v3 на одинаковом workload fingerprint, ревизии, Python/SQLite и железе. Сравнивать медиану wall time, p95 phase time, peak RSS, bytes read и package throughput.
2. **Capacity envelope.** Проверить один и два параллельных тяжелых worker; до результата оставить ограничение concurrency и запас памяти.
3. **Автоматический closure receipt.** При появлении нового visual source или holdout автоматически формировать safe receipt: provenance, два replay, validator result, store immutability, provider accounting и bundle parity.
4. **Invariant regression guards.** Зафиксировать тестами: ZIP container не становится fact package; visual denominator нельзя уменьшить; пустая область не канонизируется; Sber valve по умолчанию false; модель proposal-only.

### P2 — плановый технический долг

1. Разобрать 5 dependency deprecation warnings отдельным изменением после blocker closure.
2. Сохранить phase profiling Gate 2 и оптимизировать reconciliation только если controlled benchmark подтвердит устойчивое ухудшение.
3. Периодически проверять, что safe-report projection не расширилась customer values, source identities, raw hashes или private paths.

## 12. Что делать не следует

- Не объявлять `11/11`, меняя знаменатель или снимая materiality с пустой области без решения владельца источника.
- Не реконструировать отсутствующую таблицу по соседним страницам.
- Не давать модели canonical authority.
- Не считать известный, синтетический или публичный фрагмент положительным Sber holdout.
- Не включать release valve до терминальной приемки holdout и повторной live parity.
- Не запускать широкую архитектурную переработку ради двух входных ограничений.
- Не оптимизировать timeout или provider path: измеренная задержка находится в source-local reconciliation и validation.

## 13. Сценарии решения

| Вход | Результат по программе | Результат по Sber release |
| --- | --- | --- |
| Новых входов нет | Сохраняется `NOT_CLOSED`, Goal 3 остается `10/11` | Клапан остается выключенным |
| Получена только исправленная visual source | После полного replay может закрыться exact visual invariant и Goal 3; итоговый статус программы пересчитывается | Generalization по-прежнему awaiting customer holdout, клапан выключен |
| Получен только Sber holdout | Можно доказать или опровергнуть generalization; exact program closure все еще блокирует visual `10/11` | Включение возможно только при положительной приемке и отдельном release decision |
| Получены оба входа | Достижимо полное exact closure после всех validators и parity | Релиз возможен после положительного holdout и явного включения клапана |

Согласно исходной логике программы, внешний Sber debt должен быть зарегистрирован и release-gated, но не должен останавливать независимые цели. Поэтому после закрытия visual `11/11` сводный статус следует вычислять по формальному completion contract, не сохраняя `NOT_CLOSED` только из-за отсутствия клиентской активации. При этом `same_family_generalization` и `release_activation` могут законно оставаться отдельными незакрытыми статусами.

## 14. Рекомендуемая последовательность следующего прохода

1. Принять новый вход только через авторизованный private intake.
2. Зафиксировать provenance и проверить, что вход действительно новый и относится к нужному blocker ID.
3. Не менять frozen rules до первого терминального результата.
4. Выполнить два детерминированных replay.
5. Прогнать canonical, Gate 2, privacy и immutability validators.
6. Выполнить stage smoke и exact repository/live parity только для принятого результата.
7. Пересобрать safe status report и закрыть ровно тот статусный слой, который доказан.

## 15. Итоговое заключение

Реализация не находится в состоянии общего технического провала. Основные потоки actual corpus, архивный lineage, FNS typed adapter, accepted visual handoff, Gate 2 validation, stage delivery и очистка приватных данных подтверждены. Текущие ограничения узкие, наблюдаемые и корректно изолированы.

Единственный инженерный блокер точного закрытия программы — отсутствующее содержимое одной заявленной визуальной страницы. Единственный внешний блокер Sber generalization/release — отсутствие авторизованного unseen same-family holdout. Оба закрываются новыми входными данными и повторным доказательством; ни один не требует ослабления инвариантов или масштабной переработки системы.

## 16. Формальный статусный receipt

```text
BROKER_REPORTS_RESTRICTED_SCOPE_BLOCKERS_PROGRAM:
NOT_CLOSED

GOAL_0_CUSTOMER_DEBT_AND_RELEASE_ISOLATION:
COMPLETED

GOAL_1_ARCHIVE_LINEAGE_HANDOFF:
COMPLETED

GOAL_2_FNS_TYPED_ADAPTER_AND_PARITY:
COMPLETED

GOAL_3_VISUAL_NEUTRAL_TABLE_RECOVERY:
CORRECTLY_DEFERRED_ONE_BYTE_UNIFORM_SCOPE

GOAL_4_READINESS_RECONCILIATION:
COMPLETED_FOR_ACCEPTED_SCOPES_WITH_GOAL_3_RESTRICTION

GOAL_5_DELIVERY_LIVE_ALIGNMENT_AND_GIT_HYGIENE:
COMPLETED

SBER_BROKER_PROFILE_IMPLEMENTATION:
ACTUAL_CORPUS_PROVEN

SBER_BROKER_PROFILE_GENERALIZATION:
AWAITING_CUSTOMER_POSITIVE_HOLDOUT

SBER_BROKER_PROFILE_RELEASE:
GATED

ARCHIVE_LINEAGE_HANDOFF:
CORRECTED

ZIP_CONTAINER_SOURCE_FACT_ERRORS:
ZERO

FNS_2NDFL_TYPED_ADAPTER:
24_OF_24_COMPLETED

FNS_XML_PROVIDER_CALLS:
ZERO

XML_PDF_BIDIRECTIONAL_MATERIAL_PARITY:
PASSED

UNIQUE_MATERIAL_VISUAL_SCOPES:
11

VISUAL_SCOPES_CANONICAL:
10_OF_11

MODEL_CANONICAL_AUTHORITY:
ZERO

REMAINING_READINESS_ERRORS:
FULLY_CLASSIFIED

UNEXPLAINED_READINESS_ERRORS:
ZERO

ACTUAL_CORPUS_MATERIAL_SCOPE_ACCOUNTING:
PASSED_WITH_ONE_EXPLICIT_VISUAL_RESTRICTION

PACKAGE_PREPARATION_PROVIDER_CALLS:
ZERO

CORRECTNESS_ZERO_SILENT_LOSS_AND_PRIVACY:
PRESERVED

REGRESSION_AND_PERFORMANCE_REPROOF:
PASSED_IN_CURRENT_MEASURED_ENVELOPE

STAGE_DELIVERY:
PASSED_FOR_ACCEPTED_CAPABILITIES

REPOSITORY_LIVE_ALIGNMENT:
PROVEN

REPOSITORY_HYGIENE:
PROVEN

CUSTOMER_TEST_DEBT:
SBER_BROKER_PDF_POSITIVE_HOLDOUT_REGISTERED
```

Незакрытая часть Goal 3 имеет полный terminal record: exact scope — одна byte-uniform material visual область; failed invariant — `visual_scopes_canonical_11_of_11`; evidence — `10/11`, нулевое содержимое и нулевые видимые пиксели; owner — source owner; narrowest closing action — авторизованная замена источника и полный повтор acceptance chain.

Внешний Sber debt также имеет terminal record: exact scope — один unseen same-family positive holdout; failed acceptance invariant — `one_genuine_unseen_same_family_positive_holdout`; evidence — 14 actual-corpus регионов и 0 авторизованных holdout; owner — customer; narrowest action — предоставить один подходящий PDF и пройти frozen double replay.

## 17. Источники safe evidence

- [Финальный program closure](BROKER_REPORTS_FINAL_PROGRAM_CLOSURE.v1.safe.json)
- [Интегрированное actual-corpus closure](BROKER_REPORTS_ACTUAL_CORPUS_INTEGRATED_CLOSURE.v1.safe.json)
- [Gate 1 actual-corpus rerun](BROKER_REPORTS_GATE1_ACTUAL_CORPUS_RERUN.v4.safe.json)
- [Visual actual-corpus proof](BROKER_REPORTS_GATE1_VISUAL_NEUTRAL_TABLE_ACTUAL_CORPUS.v2.safe.json)
- [Visual source correction proof](BROKER_REPORTS_GATE1_VISUAL_SOURCE_CORRECTION_REQUIRED.v1.safe.json)
- [FNS 2-НДФЛ actual-corpus proof](BROKER_REPORTS_GATE2_FNS_2NDFL_ACTUAL_CORPUS.v1.safe.json)
- [Gate 2 package preparation v3](BROKER_REPORTS_GATE2_PACKAGE_PREPARATION_ACTUAL_RERUN.v3.safe.json)
- [Customer test debt contract](../../contracts/BROKER_REPORTS_CUSTOMER_TEST_DEBT.v1.md)
- [Frozen Sber neutral-table contract](../../contracts/BROKER_REPORTS_GATE1_BROKER_PDF_NEUTRAL_TABLES.v1.md)

Отчет не содержит customer values, клиентские документы, media, приватные пути, raw source identities или сырые приватные ссылки.
