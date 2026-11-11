# GOAL #584: бюджеты сотрудников и стоимость чата

Актуальная запись на 11.11.2026. **Backend принят; выполняется минимальный GUI и продуктовая приёмка на стенде.**
Предыдущая поставка исходников/стенда принята на3095c506; production не менялся.
Источник: [issue #584](https://github.com/Kwentin3/corp-openweb-ui/issues/584).
[Ограниченный аудит](../reports/2026-11-09/GOAL584_KISS_AUDIT.md).
[Установка и откат](employee-budgets-installation.md).

## Текущий этап: минимальный GUI и продуктовая приёмка

Согласованный результат: администратор из чата открывает управление бюджетами,
видит текущие настройки, меняет лимиты и подтверждает сохранение. Сотрудник видит
свой месячный бюджет, учтённый расход, остаток, период и блокировки, стоимость
выбранного ответа и чата. Неизвестный расход и отказ объясняются явно.

Границы: прежний принятый backend `84dace32`, stock OpenWebUI0.12.2, существующие
Tools/Actions/Event API и единственный финансовый owner LiteLLM. Сначала используются
готовые интерфейсы; добавляется только отсутствующее отображение. Новые core patches,
финансовые механизмы и тестовая инфраструктура не нужны. Production, платные внешние
API, реальные лимиты и глобальная реформа тестов не входят.

DELIVERY остаётся прежней рабочей копией; ветка `agent/goal584-gui-product` от
`84dace32`. MAIN и независимые WIP сохраняются. Проверки прежних владельцев
переиспользуются при совпадении исходников и условий. Приёмка GUI отдельно от API:
настоящий браузер, native роли/подтверждение, backend counters и реальный маршрут
в изолированном стенде с synthetic provider, без платных запросов.

Готовность: пройден путь admin → форма → изменение → подтверждение → повторное
чтение, employee → личный бюджет/стоимость ответа/чата → понятный отказ, включая
Office с вспомогательной моделью; суммы сверены с LiteLLM, чужой доступ запрещён.
Кандидат и среда связаны с evidence; свои временные ресурсы убраны. Успех только
API либо component checks не закрывает продуктовый этап.

| Обязательный остаток | Состояние / следующий шаг |
|---|---|
| Сверка принятых исходников/существующих GUI | База84dace32 подтверждена, DELIVERY чистая до новой ветки. Штатные admin Tool/Rich UI и cost Action сохраняются; source seam review PASS |
| Личный месячный просмотр | Добавлен раздел в существующий cost Action через общий public Event.read_monthly; без iframe auth/fetch, новых credentials/mounts и финансовой логики.30 focused checks PASS1.99s |
| Admin/стоимость/отказы/Office | Конечный gui-product профиль готов: native login/form/confirm/cancel/change/denial/recovery, три self monthly/Details снимка. Неизменённый Office money/helper путь переиспользуется по предыдущей приёмке; новый Office build/full matrix не нужны |
| Приёмка/сверка/уборка | Actual42971394155@bf09b7b4 остановился на inherited сравнении карточки после отмены: изменились только expense_as_of; exact native finance unchanged PASS. Исправляется driver, product/backend прежние. Cleanup0/image removed подтверждены; полный GUI PASS ожидается |

Личный бюджет — снимок в том же native message embed: нужен существующий собственный
ответ; отдельная страница до первого ответа не создаётся. При намеренной публикации
чата публикуется и снимок, о чём карточка сообщает. Email/UUID сотрудника не выводятся.
Это не разрешение свежего чужого чтения: GET/Action сохраняют native self/admin права.
Недоступный monthly reader не подменяется нулём и не ломает независимое отображение
расхода ответа/чата; отозванная роль запрещает выдачу всего снимка.

Actual GUI run: [42971394155](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/42971394155),
кандидат `bf09b7b4e5ab089ef6cdffa59cab60efc33c3a0d`, завершён FAIL проверки сравнения
свежих timestamps; ресурсы убраны. Только профиль `gui-product`; повтор после
адресной поправки driver. [Отчёт этапа](../reports/2026-11-11/GOAL584_GUI_PRODUCT_ACCEPTANCE.md).

## Предыдущий принятый этап: закрытие функциональных долгов backend

Пользователь утвердил две законченные серверные операции: администратор устанавливает
или меняет бюджет существующим способом; сотрудник смотрит собственные месячные
лимиты, расход, остаток, период и блокировки, администратор — выбранного сотрудника.
Неизвестный расход обозначается явно. GUI-прогон начинается после этого этапа.

Результат и готовность: адресно проверить backend, реализовать минимально недостающий
просмотр, закрыть известные обязательные функциональные разрывы, подтвердить обе
операции и права через серверные API. LiteLLM сохраняет финансовое состояние;
новые журналы, расчёт расходов, financial services и тестовая инфраструктура не нужны.
Вопрос оставшегося неклассифицированного подключения входит в проверку маршрутов.
Production-переключение, платные API, реальные финансовые изменения, GUI и глобальная
реформа тестов не входят. Подготовленные upstream-обращения и сопровождение патчей
сохраняются как отдельные известные эксплуатационные задачи.

Рабочая копия прежняя DELIVERY, ветка `agent/goal584-backend-closeout` от `e2d7bb73`.
MAIN и независимые WIP/worktrees сохранены; новая копия/сборочная инфраструктура не
создавалась. Принятый native DB42863840738 и предыдущие checks переиспользуются
только для неизменённых владельцев, без полной повторной матрицы.

Текущая карта границ: native WebUI auth/User → серверный просмотр одного разрешённого
пользователя → existing BudgetAdminClient/readback → native LiteLLM counters/SpendLogs
→ существующая публичная проекция → будущий GUI. Изменение лимитов остаётся у
существующего admin Tool/policy и native management API. Новый GET не инициализирует
назначения и не выполняет финансовых записей.

| Обязательный остаток | Состояние / следующий шаг |
|---|---|
| Адресный аудит backend / native read seam | Выбран штатный Event/API seam OpenWebUI0.12.2. Найдена и исправлена лишняя зависимость admin platform card от chat Pipe target для OCR-only конфигурации |
| Просмотр собственного/выбранного бюджета | Реализован native authenticated GET, повторная self/admin проверка, существующие native readers/projection и общий unknown witness reader; source reviews PASS |
| Подключение3 | Подтверждено одним bounded read-only metadata query: официальный DeepSeek, CC, enabled, dynamic discovery; provider calls/config writes0. Managed projection обязана учитывать его каталог, отключения нет |
| API-приёмка | Локально95 focused tests PASS3.95s; actual native API42872143425 PASS: real JWT self/admin/foreign/pending/demotion, native set/read20→30 и12/8→18/12, native period, GET nonmutating, inference0 |
| Закрытие этапа | Candidate28c35d20 принят:38 Git source hashes,5 mounted modules,2 native Function sources,5 healthy service images; owned containers/volumes/networks0 и generated image удалён |

Кандидат `28c35d20`, принят ограниченный native API smoke
[42872143425](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/42872143425).
Проверены artifacts и фактические значения/отказы, а не только CI status. Worker6.01s;
provider dispatch0. Unknown witness/in-flight revocation подтверждены адресными
component checks и прежним native evidence; новый smoke не фабрикует историю.
Известных незакрытых обязательных функциональных долгов backend после этого
адресного аудита нет. Следующий этап — GUI-интеграция/продуктовая приёмка на
согласованной среде. Production cutover, реальные тарифы/лимиты и эксплуатационные
upstream/test-infrastructure задачи остаются отдельно.

[Итог backend closeout](../reports/2026-11-10/GOAL584_BACKEND_CLOSEOUT.md).

## Предыдущий принятый этап: ревью и минимальный рефакторинг backend

Поручение пользователя: все управляемые модельные вызовы, включая Responses,
Office/помощников и фоновые задачи, должны использовать LiteLLM; workflow не
содержит своего учёта денег и не получает обход через прямой provider fallback.
Сохраняются native финансовое состояние, права, полный контекст, Tools, reasoning
и выдача ответа. Проверяется готовность серверных данных личного лимита, расхода,
остатка и unknown; новый пользовательский интерфейс сюда не входит.

Поставка: исходники/конфигурация на изолированном стенде, компактный реестр патчей,
подготовленные upstream-обращения, адресная уборка выявленных дублей и устаревших
обходов, отчёт о реальных ограничениях. Production/read-only допускается в прежних
границах; deployment, переключение рабочих маршрутов, платные API и реальные
финансовые настройки отдельно согласуются. Продуктовый GUI-прогон будет после
этого этапа; глобальная реформа тестовой инфраструктуры остаётся отдельным backlog.

Рабочая ветка agent/goal584-single-gateway от3095c506 в прежнем чистом DELIVERY.
MAIN и независимые WIP/worktrees сохраняются. Старые принятые результаты ниже
переиспользуются только на неизменённых границах; новую широкую матрицу не запускать.

| Срез | Состояние и следующий шаг |
|---|---|
| Маршруты/credentials/fallback | Source review и bounded runtime inventory завершены: прямой Responses, active OCR, inactive Broker. Source managed projection и signing OCR готовы; production не переключался |
| Финансовый owner и права | Второго денежного owner в budget обвязке не найдено. Native данные баланса есть; employee-self monthly endpoint пока не реализован, UI отдельно |
| Реестр патчей/upstream | [Реестр](patch-registry.md) готов, existing manifests не дублируются; известные official issue/PR проверены, safe drafts подготовлены без публикации |
| Минимальные исправления/чистка | Managed mode существующего prepare_google_gateway.py готов; убраны legacy-only stream policy и скрытые credentials inactive slot. Responses config ограничен фактически квалифицированным buffered-upstream профилем |
| Приёмка | Config9/33negative, OCR/Pipe86, auth50+1optional skip, selected native guard6 PASS; source reviews PASS. Actual file-service native DB42863840738 принят, identity32Git hashes и cleanup подтверждены. Full-PDF native transform PASS; GUI исключён |

Решение пользователя: active OCR оплачивает отдельный служебный бюджет платформы.
Запустивший OCR пользователь остаётся actor для native проверки прав на файл
(владелец, администратор или разрешённая запись); file ID — реальная resource scope,
а не chat/answer ID. Личный бюджет сотрудника не используется для оплаты OCR.
Non-chat OCR подключён через существующие service provenance/common binding в
кандидате `befedb20`; raw Responses/PDF и File ACL сохранены. Пройдены локальные
проверки OCR/service Pipe, auth/provenance и выбранные native Usage guard проверки.
Первый native DB прогон42862513323 подтвердил known Usage/стоимость0.166 и точную
platform/File/actor связь, затем driver завершился AttributeError. Уборка подтверждена:
containers/volumes/networks0, image удалён. В driver исправлена source-proven ошибка
чтения nullable spend_logs_metadata в native unscoped rows; конкретный кадр первого
падения не сохранён. Native auth/финансовый runtime не менялись после befedb20.
Ограниченный native DB прогон
[42863840738](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/42863840738) на91717eb6
принят по receipt и фактическим assertions:0.166USD/known Usage платформе с точными
actor/File/model/key IDs; cap denial до provider dispatch; raw absent Usage →
блокировка только нужного platform/model key → повторный401 без dispatch.
Личные расходы/ключи сотрудника и контрольная модель сохранены. Всего2 synthetic
provider dispatch; провайдер завершён, controls не менялись. Оба CI завершены;
owned containers/volumes/networks0, generated images удалены. Сверены32 Git LF
source hashes, manifest/native image identity и четыре healthy service images.
Отдельный no-network replay actual WebUI converter/Form → native LiteLLM Responses
transform сохранил полный двухстраничный PDF, instruction/schema/metadata/output
limit/store/stream без изменений. Это проверка транспорта, не качества распознавания.
Обязательного остатка в согласованном source/stand этапе нет. Следующий этап —
продуктовая GUI-приёмка на согласованной среде; production cutover отдельно.
Исходная принятая configuration-подготовка сохранена на3f3a9270; исторический blocked
checkpoint0918d27b относится к уже снятому продуктовому вопросу. Повторно его не задавать.
Неподписанный OCR останавливается до provider dispatch. Новый подписанный service
scope использует реальный file ID и common service configuration; новая граница
проверяется отдельно от прежних принятых сценариев. При неизвестном расходе блокируется соответствующий
native ключ модели служебного плательщика; личные ключи сотрудника не затрагиваются.
Неизвестный connection3 подлежит классификации перед реальным включением;
managed preparation уже отклоняет неоднозначные active entries.
Продолжение после6cf74f71: обнаружен B3 — одного mode=responses/набора callbacks
недостаточно: без supports_native_streaming=false native Responses policy отмечала
проверку not_run. Подготовка теперь требует прежний принятый OpenAI buffered profile,
не меняя request payload, WebUI stream или runtime callback. Прежние квалифицированные
SDK/DB доказательства применимы к этому же профилю; новую broad-матрицу не запускать.

[Итог backend-этапа](../reports/2026-11-10/GOAL584_SINGLE_GATEWAY_BACKEND_REVIEW.md).
Служебные обзоры находятся в local/goal584/single-gateway/; это evidence, не второй план.

## Предыдущая принятая поставка

## Согласованный результат и границы

LiteLLM — единственный владелец расходов, денежных лимитов, резервирования и SpendLogs.
Общая серверная интеграция связывает вызов с сотрудником, чатом и ответом, включая
вызовы помощников. Новый конвейер, использующий этот общий путь, не добавляет свою
финансовую логику. Служебные задачи используют отдельного плательщика.

Сотрудник видит стоимость ответа и накопленную стоимость чата на момент чтения.
Администратор меняет месячные лимиты и распределение по моделям через готовую
форму в чате с серверной проверкой прав и штатным подтверждением.
Если Usage отсутствует, расход неизвестен и блокируется только соответствующая
модель данного сотрудника. Подтверждённый ноль отличается от неизвестного расхода.

Разрешены исходники, рефакторинг и изолированный стенд. Пользователь отдельно
разрешил узкую поправку исходной Usage/завершения потока только на стенде, без
deployment, новых журналов и новой тестовой инфраструктуры. Ранее разрешённый
calendar-floor patch двух функций сохраняется отдельно и без изменений.
Production, платные API, реальные тарифы/лимиты и изменения рабочих маршрутов
требуют отдельного согласования. Office/Tasks/Skills/Files/STT, полный контекст
модели, reasoning, права и данные сохраняются.

## Принятая реализация

| Граница | Владелец |
|---|---|
| Деньги и лимиты | Штатные LiteLLM users, virtual keys, reservation, pricing и SpendLogs |
| Общая принадлежность вызова | Серверный Filter/provenance и gateway auth; employee/chat/answer/helper |
| Отображение | Чтение native ledger, статус ответа и штатное действие «Стоимость: детали» |
| Управление | Native Tool/Rich UI, проверка текущих прав, точное изменение и подтверждение |
| Неизвестная Usage | Общая policy блокирует native employee/model key; отдельного ledger нет |

Удалена финансовая эвристика по имени Tool/наличию делегирования. Тарифы не
пересчитываются в конвейерах. Интерфейс показывает начисленное на текущий момент,
а не обещает окончательную стоимость ещё продолжающейся работы.

Для LiteLLM 1.105.1/OpenAI SDK 2.33.0 подготовлен version/hash-bound стендовый
streaming patch. Он сохраняет исходный признак Usage до нормализации и передаёт
отмену из фактического CC generator в существующий общий cleanup/callback.
Содержимое, Tools, параметры вызова, сборка потока и расчёт денег остаются штатными.
Исходный floor patch и его независимая проверка сохранены. Установка не выполнялась.

## Приёмка и доказательства

Независимая приёмка использует согласованный source/stand объём и применимые
старые результаты; повтор всей прежней матрицы не является условием готовности.

| Требование | Результат и evidence |
|---|---|
| R1. Один денежный владелец | PASS: source audit и native ownership; своего счётчика списаний/финансовой БД нет |
| R2. Общий путь и helpers | PASS: actual42792989666 — Sol1.20 + Terra0.12 = employee/answer/chat1.32; служебный вызов отдельно0.20 |
| R3. Две видимые суммы, real0/Details/reload/чужой доступ | PASS: actual42792989666 UI1.32/1.32 и actual42784099623 known0; неизменённые UI owners |
| R4. Форма/права/подтверждение, отказ/восстановление | PASS: Native48 actual41718501504 и неизменённые native write/admission owners |
| R5. Stream/error/cancel, unknown и адресная блокировка | PASS: actual42807487227 SDK/component + actual42825996133 native DB/auth/reader |
| R6. KISS/native и контекст | PASS: source review, actual SDK request/context и delegated reasoning/Tools; версии и исходники связаны хэшами |
| R7. Install/rollback package | PASS как исходный стендовый комплект: native Compose actual42811133630, прежние сервисы/data/security/limits |
| R8. Уборка и сохранение WIP | PASS: все CI terminal/cleanup0; fixtures сохранены и убраны, quota worktree и последний local source context закрыты; независимый WIP сохранён |

Последний необходимый сценарий:
[run42825996133](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/42825996133),
коммит `0ddd9a327e26dfaf733a565cb71ef7b4d212b035`, SUCCESS13:38:29UTC.
Один запрос отменён после provider HTTP200 до первого chunk/Usage. Native ledger
сохранил одну failure row с employee/key/model/deployment/root/call/session binding.
Restricted reader вернул `usage_unavailable`, модель сотрудника заблокирована,
повторный запрос получил401 без второго provider dispatch. Лимиты, назначения
и контрольная модель сохранены. Provider control восстановлен, terminal подтверждён;
контейнеры, volumes, networks и созданный образ удалены.

Artifact13769411928,10563B/9members,
SHA256 `8a1bfe5909353664b93f36f0b85d2f2c5b5346633fc7af8e3975f583592a5e5f`.
Root сверил32 Git-LF source pins,4 native targets и8 SDK files.
Composite proxy SHA256 `3586258e788671353fea94d216568852cfb2eae76bcc13bec71bd9fdbd9cbf4f`;
stream manifest Git-LF SHA256 `2684957a6ba64bed66f4cb7a5b879e7d33b23d213cd0a4f569fe9cf2c0509feb`.
Raw SQL dump не сохранялся: это actual native receipt/source-bound readback,
а не независимый повтор SQL-запросов.

Предыдущие неуспешные прогоны сохранены как evidence. Они выявили ошибки запуска
стенда, невозможное условие downstream200 до первого chunk, проверку соседнего
generator вместо реального CC caller и пропуск уже предусмотренной настройки
`missing_session_id: omit`. Эти ошибки исправлены; их FAIL не переименованы в PASS.
В actual42792989666 finance/context assertions прошли до отдельного DOCX checker
failure; сам DOCX checker исправлен по сохранённым артефактам, Office product не менялся.
Отдельный Terra quota-negative был SKIPPED и не выдаётся за наблюдённый PASS:
применимость обоснована native enforcement и фактической привязкой child к тому же key.

## Поставка, уборка и дальнейшая установка

Поставка находится в отдельной ветке `agent/goal584-budget-ui`, опубликованной
как `agent/goal584-reasoning-continuity`. MAIN и независимые WIP/worktrees сохранены.
Исходники, native build recipe, opt-in Compose overlay, Functions/Tool и инструкция
установки/отката подготовлены. Новые серверы учёта, журналы и test frameworks не созданы.

Последний локальный source-only контекст удалён:
`local/goal584/kiss-refactor-2026-11-10/stream-usage-fix/cc-native-owner-final-context`.
Рекурсивное удаление отклонено automatic approval review до запуска.
Более узкая разрешённая операция удалила21 проверенный regular file и14 только EMPTY
директорий без Recurse/Force. Receipt cc-native-owner-context-cleanup.safe.json:
stage=complete, remaining=false; root Test-Path=false. Все18 исходных cached/committed
baseline hashes до/после совпали. Первоначальная ошибка UTF8 guard остановилась
до удаления и исправлена явным чтением UTF8. Архивов-дубликатов не создано.

Подробные локальные receipts, source review и исторический снимок записи сохранены
в `local/goal584/kiss-refactor-2026-11-10/`; это evidence, не параллельный план.
Прежние pytest fixtures сохранены в проверенном ZIP перед безопасной уборкой;
Office и прочие деревья с независимым WIP не очищались.

Перед отдельно разрешённой установкой нужны exact target images, существующие
DB/Redis, native control-plane identities, каталог/цены/лимиты и сохранённые Valves/ACL.
Холодные импорты admin aliases и фактическая установка на выбранный target ещё не
заявлены. Read-only проверка production10.11 обнаружила прямой Responses маршрут
к провайдеру: общий бюджетный контур там пока не активирован. Все согласованные
маршруты потребуется подключить при отдельно согласованном cutover и проверить
один целевой сквозной сценарий. Это следующий этап, исключённый из текущего GOAL.

## Политика, сохранённая для продолжения

- Существующий компонент → штатная возможность → тонкая адаптация → новый код только при доказанном разрыве.
- Один владелец финансового состояния; обновляемое ядро; без финансовой логики в конвейерах.
- Проверки соразмерны изменению; принятые результаты повторяются только при новых значимых входах/свидетельствах.
- Production и реальные деньги не входят в стендовое разрешение.
- Разрастание тестовой инфраструктуры отдельно зафиксировано в глобальный backlog; это не условие текущей поставки.
