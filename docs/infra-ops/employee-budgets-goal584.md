# GOAL #584: бюджеты сотрудников и стоимость чата

Актуальная запись на 11.11.2026. **Стендовая поставка принята. Внедрение в production разрешено, но не завершено; включение ожидает решения о защите при неизвестном расходе Claude/Gemini.**
Принятый table-кандидат `8ae015a5` от базы`592a4534`; предыдущий GUI-кандидат`0138b6d2`.
Источник: [issue #584](https://github.com/Kwentin3/corp-openweb-ui/issues/584).
[Ограниченный аудит](../reports/2026-11-09/GOAL584_KISS_AUDIT.md).
[Установка и откат](employee-budgets-installation.md).

## Активный этап: внедрение всего продукта в production

Разрешён пользователем 11.11.2026 от `dffab57e`, в существующей DELIVERY/ветке.
Цель: работающие учёт LLM-расходов, бюджеты сотрудников, компактная админка и
отображение стоимости ответа/чата и личного бюджета в рабочем Open WebUI.
Стендовая база — runtime `1ebf2b64`, actual `43018788862`; новый GOAL не заменяет
приёмку артефактом другого checkout. Текущие MAIN WIP и worktrees сохраняются.

Границы поставки: точная сборка и существующий Compose overlay, native DB/Redis,
control-plane credentials/roles, routing всех согласованных моделей через общий
LiteLLM с сохранением Responses/CC/контекста/tools, native Functions/Tools/Models/
Skill и Valves/ACL, public prices/provider status/manual snapshots, реестр прежних
patches и откат с сохранением данных. Персональное бюджетирование 1С исключено;
действующая API-интеграция должна сохранить работоспособность. Не создавать
обходной финансовый owner или неподписанный скрытый маршрут для совместимости.

Полномочия включают подготовку и deployment этого продукта. Нет полномочий
терять данные, править финансовые counters напрямую или выполнять clean builds/
rehearsals на production VPS. До переключения — конкретный source/image/config,
проверенная резервная копия/откат и пределы ресурсов. Новых framework, журналов
денег, прокси и массовых тестовых прогонов не добавлять; повторять только
затронутые проверки при новых значимых входах.

Проверенное сейчас: база DELIVERY `dffab57e`; MAIN `b4518191` с независимым WIP.
Bounded SSH preflight подтвердил здоровые WebUI/LiteLLM без budget Functions,
отсутствие PG/Redis у gateway, stock1.105.1 с тем же pinned base digest,
свободные ~5 GB RAM/~35 GB disk и native admin API access. Неизвестное подключение
идентифицировано как official DeepSeek. Никаких model calls не сделано.
Release source/runtime reviews подтвердили61 LF source pins и необходимость
Git-LF экспорта. Accepted image после стенда удалён; off-prod rebuild сохранён
в [image-only run43029553258](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/43029553258),
все полные proof jobs SKIPPED. Прямой dispatch нового workflow получил404 до его
регистрации на default branch; existing manual workflow теперь вызывает его
через reuse. Это image packaging, не новый test framework.
Native persistence overlay применён только к новым PG/Redis: actual Compose
merge, закрытая сеть, persistent volumes и health PASS. Исходные сервисы сохранены.
Protected backup phase создана с image/config/Compose/env snapshot. SQLite backup
первая попытка остановлена по времени; повтор дошёл до SQLITE_DONE, но callback
слишком поздно применил тот же предел. Полученная копия635068416 B затем отдельно
прошла readonly SQLite quick_check=ok и SHA256; повторного копирования не было.
Архив image445921052 B доставлен прямо с Actions на сервер, SHA256 GitHub artifact
и все внутренние checksums/source1ebf2b64 подтверждены. Зависшее скачивание через
Windows адресно остановлено, незавершённых download процессов нет. Рабочие
routes/сервисы не переключены.
API source review доказал, что сохранение fake chat не годится: меняется история
и HTTP streaming. Минимальная совместимость готовится в прежних signature/gateway/
guard owners: signed API operation существующего владельца ключа, без выдуманных
chat IDs, новых payer/ledger/расчёта денег. Персональный учёт сотрудников1С исключён.

Обязательный остаток: финальный managed каталог/публичные цены и применение
начальных бюджетов; protected config/control-plane roles и operational rollback;
разрешение конкретных несовместимостей;
установка, native readback, один ограниченный admin→staff→расход→отказ→увеличение→
восстановление GUI/PNG сценарий; независимая приёмка, документация и safe cleanup.
Следующий шаг: завершить текущий upstream review и обсудить с пользователем
реакцию на неизвестный расход/расширение patch. Независимая подготовка API/config
допустима; общий cutover до решения coverage gap не выполнять.

Уточнения пользователя: стартовый месячный лимит каждого сотрудника20 USD,
равные доли доступных моделей; отдельный общий platform/OCR/tasks budget20 USD.
Потоковый режим действующей1С пока неизвестен. API source candidate(+91/−15
production LOC,194 строки в существующих tests) прошёл адресные проверки и
независимый source review; runtime/реальная1С ещё не приняты.
PG/Redis уже установлены и healthy, с persistent volumes и без published ports;
исходные WebUI/gateway containers и routes не менялись. Image load на Docker29
дал другой target ID; source config SHA256 совпал с builder IID, все layer diff IDs
и runtime config совпали с архивом. Source/target identity receipt сохранён.

Перед общим включением обнаружен реальный coverage gap: current CC Usage guard
читает raw witness только OpenAI leaf, native Anthropic/Gemini идут другими путями
и могут получить ложный unknown block после успешного ответа. Учитывать это как
непринятый production provider path; прежний OpenAI fixture PASS его не закрывает.
Подготовлен, но НЕ применён concrete draft54 строки на два native parser targets
в existing stream patch package; callback может использовать уже существующий
iterator hook без нового parser/счётчика. Пользователь выбрал сначала обсудить
компромисс; core draft не применять, общий cutover не выполнять до решения.

По просьбе пользователя11.11 выполнен targeted upstream read-only поиск:
[issue50124](https://github.com/BerriAI/litellm/issues/50124) открыт: missing/malformed
Usage может не списывать native key budget; [issue37992](https://github.com/BerriAI/litellm/issues/37992)
открыт: explicit0 подменяется estimates на disconnect. [Feature29680](https://github.com/BerriAI/litellm/issues/29680)
предлагает usage_source, закрыт stale/not_planned; связанный [PR29704](https://github.com/BerriAI/litellm/pull/29704)
открыт, merged=false, mergeable=false по live PR readback. Просмотренный diff
определяет upstream/missing по наличию response_obj.usage; происхождение данных
после нормализации им не доказано, нашей блокировки он не реализует. Это не
квалифицированная замена raw-presence witness до нормализации.
[Issue47332](https://github.com/BerriAI/litellm/issues/47332) закрыт без изменения
поведения после обсуждения отсутствующего final Usage; closure comment прямо
сохраняет graceful completion, а не добавляет финансовый fail-closed. Наличие issues не доказывает
исправления в нашей1.105.1 или готовности полного fail-closed режима из коробки.
Новых core изменений, CI/provider/model calls и upstream messages в этом поиске нет.

Независимая подготовка после upstream review: четыре API owner hashes сверены
с independent source review без повторного запуска принятых tests. API candidate
сохраняется отдельной source поставкой; vendor draft по-прежнему не применяется.
Read-only pricing preflight14:24UTC нашёл public entries для16/16 native base models,
включая DeepSeek и Gemini image model; source SHA5406310d…dc3e6. Это prospective
public-map membership, а не доказательство applied rates/мультимодального биллинга.
Текущий native `/model/cost_map/source` вернул200; первый metadata subprocess ранее
завершился ошибкой, её причина не установлена, raw diagnostic сохранён. Ни одного
LLM request не выполнено. Applied rates и сохранение image/API profiles проверить
при final config/приёмке, без выдуманных overrides или нулевых цен.
API source candidate зафиксирован и опубликован как `a35b2033`; рабочее дерево
DELIVERY чистое, независимый MAIN WIP сохранён. Новых тестовых запусков не было.
Независимая безопасная подготовка текущего этапа завершена. Решение по core delta
остаётся открытым после исходного обсуждения, upstream review и сохранения
API/pricing подготовки. Без него нельзя выбрать окончательную сборку и включить
все provider paths, сохранив прежнюю строгую политику. Не выполнять speculative
core patch, частичный cutover или незаметное ослабление блокировки; следующий шаг
— решение пользователя, затем конкретная final config/runtime/product приёмка.

## Текущий этап: самодостаточное управление моделями, ценами и состоянием оплаты

Принят в работу 11.11.2026 от `2c4ae3ab`, в прежней DELIVERY/ветке.
Результат: автоматический native каталог с ACL и нулевой долей новой модели,
сохранение прежних назначений; публичные цены LiteLLM с компактной легендой и
временем обновления, неизменяемой историей расходов; информационная отметка
последнего подтверждённого финансового отказа/последующего реального успеха
того же оплачивающего подключения; достоверный API или ручной снимок баланса
с валютой/временем/источником/автором; раскрываемая статистика сотрудника.
Нет подсказок последствий, групповых действий, платных фоновых проб,
нового финансового журнала, core patches или расширения тестового framework.
Production/deployment и платные API исключены. Отметка отказа не блокирует
запросы и не означает точного нулевого баланса; кеш/fallback не доказывает
восстановление. Приоритет — штатные владельцы и минимальная адаптация.

Границы смыслов: WebUI native MODELS/ACL/connection → управляемые wire IDs → Tool;
LiteLLM native model/cost map → применяемые публичные ставки → легенда;
native SpendLogs/request metadata → наблюдение оплаты → информационная шапка;
native protected Functions Valves → ручной снимок → шапка. Cap/spend/расчёт
и история сохраняют прежнего владельца LiteLLM. UI — только представление.

Проверенное состояние: финальный кандидат `1ebf2b6412aa206976cc9b88ce027cc653993060`,
[native run 43018788862](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/43018788862)
SUCCESS. Пройдены source/адресные owners проверки, native guard и настоящий чат.
Шапка содержит цены/состояния и раскрываемые ручные сведения; строка
сотрудника раскрывает статистику. Native каталог/ACL заменяет ручной список;
новые назначения создаются при подтверждении, начиная с hard cap 0. Global scope
существующего Filter обеспечивает подхват новых моделей; native dedup и сохранение
primary/subagent контекста проверены адресно. По независимому source review
исправлена повторная проверка config/ACL перед native POST. Новых core patches нет;
прежние LiteLLM patches сохранены, Open WebUI core не менялся.

Обязательный объём этапа выполнен: native баланс/публичный S1→S2→S1/история,
pending→hard-zero назначение, отказ оплаты→оплаченный успех через общий signed
gateway, actual PNG/source/image/mount readback и cleanup. Browser phase: 13 вызовов/
synthetic 3.00 USD, отдельная API-only recovery phase: 2 вызова/0.20 USD; платных API нет.
Контейнеры/volumes/networks удалены, derivative image удалён. Подробности и границы
проверки — [отчёт приёмки](../reports/2026-11-11/GOAL584_ADMIN_SELFCONTAINED_ACCEPTANCE.md).
Установка на production — отдельный, не начатый этап. Неподдержанный универсальный
balance API заменяет явно датированный ручной снимок; карточка обновляется по запросу.

### История ограниченной диагностики до финальной приёмки

Кандидат `d7d1205e642536a2522d383332343d8b904f337f` зафиксирован и отправлен;
[actual run 43010403326](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/43010403326)
завершился: GUI/context/reconcile PASS (5 admin turns, 13 physical calls,
16 signed attempts, synthetic phase 3.00 USD, S1→S2→S1/расписание восстановлены).
Последний native backend срез FAIL: финансовый отказ не распознан за 20 секунд.
Native SDK/router replay подтвердил дефект парсинга literal body с добавленным
router suffix; точные failure rows первого запуска не сохранены, поэтому это
не доказательство единственной причины. Исправляется только этот разбор и
ограниченный safe readback при ошибке прогона. Общий native PASS не заявляется.
Cleanup первого запуска: containers/volumes/networks 0, derivative image удалён.
Повторный кандидат `2d429fc193964b88129b2a7de4d894095cb436fe`,
[run 43012712144](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/43012712144)
выполняется: parser удаляет только точный pinned router suffix; остальные
проверки и UI сохранены. 58 readback tests PASS, native SDK/formatter replay
False→True подтверждён; при новом timeout сохранится ограниченная safe проекция
row/schema/cache/code без тела ошибки и credentials. Следующий шаг — actual readback.
Повтор `43012712144`: GUI/context/reconcile снова PASS, final backend FAIL.
Safe actual row подтвердил failure/model_id B/cache False/APIError/native code402/
provider present/spend0; тело не содержит JSON/literal. Поэтому SDK потерял
подробный код, и одного исправления suffix недостаточно. Добавлено точное
распознавание native provider402 как финансового отказа; 429/422/нет provider
не подходят, баланс 0 не выводится. 59 readback tests PASS. Следующий шаг —
финальный конечный профиль; UI и финансовый backend caps/spend не менялись.
Кандидат `d7447546cda2339bfc9ab6a5f7a8bdaa016ea4ba`,
[run 43014154602](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/43014154602)
выполняется. Предыдущие два запуска terminal; их owned resources удалены.
`43014154602` завершён: GUI/context/reconcile PASS; native402 теперь распознан.
Recovery-проба получила503: она использовала raw key без обязательного signed
personal scope, и прежний UsageGuard отказал до проверки Usage. Это дефект пробы,
а не доказанный nonstream regression продукта. Проба приводится к существующему
shared gateway/provenance и CC-stream профилю, без изменения проверки scope.
Source review также выявил необходимое узкое исключение в existing failure callback:
подтверждённый native provider APIError402 до получения stream response должен
сохранить отказ оплаты, не блокируя модель как unknown Usage. Midstream/500/429/
отмена остаются под прежней защитой. Никакого нового zero-cost доказательства нет.
Cleanup третьего запуска подтверждён0; следующий шаг — адресные проверки и actual.
Поправка ограничена существующим failure callback; signed SDK-проба использует
shared gateway, свежий nonce и штатный CC-stream. Локальный SDK replay подтвердил
402→200/Usage15/два вызова; patched-native guard локально не запускался. В прежний
`gui-product` preflight включены только две затронутые native проверки: pre-stream402
и сохранение блокировки для429/500/midstream402. Новый framework не добавлен.
Actual `a9c9d321`/[43018428780](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/43018428780)
остановился на новом preflight assertion: вызванный прежний helper намеренно
ожидает blocked=True, хотя новый pre-stream402 обязан оставить blocked=False.
До assertion уже подтверждены исходный402/нет admin writes/нет block; второй
native429/500/midstream402 тест PASS. Меняется только новая проверка на точное
равенство user/key исходному состоянию. Cleanup0; продуктовый GUI не запускался.
Пределы: job 25 минут, браузер 330 секунд; наблюдение через GitHub Actions,
адресная остановка через `gh run cancel <id>`, штатный always-cleanup Compose.
Профиль использует только существующий synthetic provider/public catalog, без
новых services/framework и платных вызовов.

## Принятые уточнения: внешние балансы и цены

Решение от 11.11.2026: индивидуальные/договорные тарифы исключены из продуктовой
схемы; используются публичные цены. Автоматическое обновление применяемых цен и
их легенда в шапке остаются последующим объёмом, а не частью принятого GUI PASS.

Внешний баланс относится к оплачивающему счёту провайдера и может быть общим
для нескольких моделей. Не все подключения дают API чтения такого баланса.
Если API нет, администратор сверяет сумму в ЛК вручную; перенесённые сведения
должны содержать источник, валюту и время проверки и называться последним
известным балансом. Неизвестный баланс не заменяется нулём или расчётом по
SpendLogs. Остаток личного лимита не гарантирует наличие денег у провайдера.

Ручной ввод снимков и строка состояния реализованы в текущем source и ожидают
новой native приёмки. Универсальное чтение внешнего денежного остатка API не
квалифицировано; используется проверка ЛК. Подробные правила
и границы реализации — в разделе
[«Баланс провайдера и лимиты сотрудников»](employee-budgets-installation.md#баланс-провайдера-и-лимиты-сотрудников).

## Завершённый текущий этап: удобная интерактивная таблица индивидуальных лимитов

Администратор пишет «Давай поработаем с лимитами» и получает один рабочий экран:
сотрудники, месячный бюджет, учтённый расход/остаток, распределение и состояния
моделей. Локальные поиск, фильтры и сортировки фокусируют выборку без нового
модельного вызова. После просмотра первого PNG пользователь отверг высокие строки,
отдельные model cards и повторяющиеся инженерные пояснения. Принято уточнение:
плотная таблица с закреплённой шапкой, где находятся управление столбцами и легенда;
поиск/отдел, сортировка и фильтр остатка встроены в соответствующие заголовки.
Почта и подробности доступны по запросу, учтённые деньги видны сразу.

В каждой строке одна составная полоса100% лимита; сегменты — модели с цветом,
названием/процентом и подсказкой суммы. ДляN моделей — N−1 подвижная граница;
движение меняет только две соседние доли и сохраняет сумму100%. Точные поля
доступны отдельно. Невалидные исходные доли не нормализуются молча. Используются
native HTML range и CSS без новой библиотеки. Деньги форматируются для чтения,
отправляемые значения точные. Повторный PNG нужен на2 и12+ сотрудниках, включая
прокрутку для проверки закрепления шапки.

Черновик сохраняется в DOM карточки при поиске/фильтрах/сортировке: выделение и
счётчик индивидуальных правок, «Только изменённые», сброс. Подробное «Было → станет»
доступно перед применением и обязательно показано в native business confirmation.
Кнопка отправляет только изменённые индивидуальные строки через
прежние exact JSON/native подтверждения/backend policy. После сохранения показано
фактическое состояние; ошибки и неопределённый/неполный расход не маскируются нулём.
Обновление с черновиком не должно молча терять правки.

Групповые операции/массовое назначение/новые шаблоны — отдельный backlog. Одна
кнопка может применить несколько отдельно отредактированных строк. Прежние
backend/bootstrap возможности сохраняются; служебные панели не загромождают
основную таблицу. Сокращение двух подтверждений исследуется только штатно, без
ослабления прав/source/revision checks и без патча core.

Границы: DELIVERY прежняя, ветка `agent/goal584-admin-table` от`592a4534`; MAIN и
независимые WIP/worktrees сохраняются. Новых datagrid libraries, финансовых
readers/writers, credentials, журналов, тестовых frameworks и core patches нет.
Production, платные API, реальные финансовые настройки и глобальная реформа тестов
не входят. Изменяются представление и ограниченный existing browser driver;
LiteLLM остаётся единственным финансовым owner.

Готовность: компонентная репетиция реальной HTML-карточки, затем конечный
native WebUI browser-прогон на прежнем изолированном стенде. Обязателен осмотр
PNG, а не только DOM/JSON: общий вид, фильтрованная выборка/пустой результат,
ползунки и черновик, подтверждение, сохранение и ошибка. Проверить читаемость,
переполнение/обрезку, прокрутку, фокус/клавиатуру и основные состояния. Финальный
кандидат связан с native суммами, source/runtime identity и cleanup своих ресурсов.
Прежняя приёмка неизменённых финансовых/Office owners переиспользуется адресно.

| Срез | Принятый результат |
|---|---|
| UI таблицы/черновика | Первый PNG отклонён и заменён плотной версией:63px строки, sticky header с управлением/легендой, одна segmented bar с N−1 границами. Root просмотрел2/12/3-model PNG при820px, без overflow; source review PASS, schema/policy прежние |
| Нативный путь подтверждения | Pinned WebUI0.12.2 проверен: прямого авторизованного iframe→Tool RPC нет. Сохраняются оба подтверждения без изменения доверия и прав |
| Browser/PNG | Компонентный Chrome и root N3 pointer replay PASS;2/12/scrolled/N3 PNG просмотрены при820px, header top49 при scroll240. Actual42989620455 PASS67.11s:6 локальных этапов/12 PNG, native open/cancel/apply/recovery; root просмотрел реальные general/filtered/draft/error/preview/confirm/saved PNG |
| Приёмка/поставка/уборка | Actual8ae015a5 принят:61Git pins/6mounts/4extension sources/5images,15 прежних financial owners/4stand/verifier файла; native local controls0prompt/provider/finance effects, точный JSON/Skill/context сохранён. Независимый R1–R5 PASS; resources0/image removed. Первый dispatcher FAIL сохранён |

Actual компактного GUI: [42988211059](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/42988211059),
`263c243f921dcc1a55f5cd872cf797cb29ee2afe`, завершён FAIL: выбран обычный synthetic
ответ вместо вызова Tool из-за неполного тестового intent matcher. Исправлен только
mock dispatcher после replay actual payload; product/UI не менялись. Cleanup0,
generated image удалён. Параллельных повторов нет.
[Отчёт](../reports/2026-11-11/GOAL584_ADMIN_TABLE_ACCEPTANCE.md).

Повтор: [42989620455](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/42989620455),
`8ae015a57027e501084d0507deb5e5445e8ad47b`, SUCCESS; та же UI версияa98d92cf. Дополнительная
source-bound pointer репетиция: настоящий drag N3 дал20/30/50→35/15/50→35/60/5;
пересечение соседа ограничено95/0/5, другие доли сохранены, page errors/prompt posts0.
Это компонентная проверка, отдельно от принятого actual native результата.

Обязательного остатка table source/stand этапа нет. Сохранены два штатных
подтверждения; результат приходит новым сообщением со свежей карточкой. Групповые
действия остаются backlog; production, реальные провайдеры/лимиты, upstream и
глобальная реформа тестов не входят в этот PASS. Следующий этап отдельно согласуется.

## Предыдущий принятый этап: минимальный GUI и продуктовая приёмка

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

| Срез | Принятый результат |
|---|---|
| Сверка принятых исходников/существующих GUI | База84dace32 подтверждена, DELIVERY чистая до новой ветки. Штатные admin Tool/Rich UI и cost Action сохраняются; source seam review PASS |
| Личный месячный просмотр | Добавлен раздел в существующий cost Action через общий public Event.read_monthly; без iframe auth/fetch, новых credentials/mounts и финансовой логики.30 focused checks PASS1.99s |
| Admin/стоимость/отказы/Office | Actual native browser: open/cancel/apply/recovery, точный JSON и оба диалога; три employee self monthly/Details снимка, reload, foreign403, native counters/period и read без finance/provider effects PASS. Office/helper переиспользуется по предыдущей приёмке на неизменённых owners |
| Приёмка/сверка/уборка | Actual42972451676@0138b6d2 SUCCESS, browser58.94s. Root readback61Git pins/6mounts/4extension sources/5images PASS; independent R1–R5 PASS. Owned containers/volumes/networks0, generated image удалён. Первый42971394155 FAIL старой timestamp-проверки сохранён; исправлен только driver |

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

Повтор: [42972451676](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/42972451676),
`0138b6d2f58ad83c2520a414d113755f953a3a25`, принят по actual browser/native/context/
source/cleanup artifacts. Product/backend совпадают с первым кандидатом; изменены
только проверка timestamps и документация. Админские вызовы оплачиваются его native
бюджетом: отмена правки не обещает бесплатного модельного запроса. Личный снимок
показал0.4/0.2/0.2 →0.4/0.4/0 →0.8/≈0.6/≈0.2USD; raw native float strings сохранены
без форматирующего округления. Это известная косметическая шероховатость.

Обязательного остатка GUI source/stand этапа нет. Production cutover, реальные
провайдеры/тарифы/лимиты, upstream публикация и глобальная реформа тестов не входят
в этот PASS. Следующий этап отдельно согласуется; автоматического deployment нет.

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
