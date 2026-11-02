# GOAL #584: бюджеты сотрудников и стоимость чата

Текущая запись работы, 02.11.2026. Источник требований и полномочий —
[issue #584](https://github.com/Kwentin3/corp-openweb-ui/issues/584).
Заказчик согласовал начало работы в этом чате. Коммерческое описание —
[редакция 4](../commercial/planning/TOKEN_LIMITS_CUSTOMER_PROPOSAL_2026-10-20.md).

**Состояние:** GOAL в работе, продуктовая приёмка не выполнена. Native scalar
budget core отдельно проверен на изолированном стенде — результат ниже. Первичная проверка
штатных возможностей обнаружила отсутствие прямого авторизованного обмена
Rich UI iframe с Tool/Action на 0.12.2. До строительства обходного механизма
нужно решение владельца о пользовательском пути; варианты ниже. Адаптер отдельно
проверен с имитированными trusted headers. Кандидат следующего среза добавляет
stock WebUI и обычный браузерный чат двух синтетических сотрудников; runtime
этого среза ещё не выполнен. Платные вызовы не разрешены и в стенд не входят.

## Цель и ограничения

Из обычного чата открыть актуальное управление денежными бюджетами сотрудников,
подтвердить изменение и реально ограничить последующие API-вызовы. Сотрудник
видит стоимость ответа со всеми LLM-шагами и итог чата со всеми ветками.
Отключение отображения не отключает учёт. Служебные расходы учитываются отдельно;
история не пересчитывается при изменении тарифа и не исчезает с удалением чата.

Разрешены собственная ветка, ограниченный изолированный стенд, реализация,
локальные проверки и PR. Production, реальные тарифы и лимиты, платные API-вызовы
и изменения рабочих маршрутов требуют отдельного согласования. Ядро Open WebUI,
фронтенд, DOM/fetch и защиту iframe не изменяем. Не создаём второй каталог
сотрудников, журнал расходов, постоянную админ-платформу или sidecar.

## Проверенная исходная конфигурация

Read-only сверка 02.11.2026, 13:35 МСК; ключ SSH и адрес проверены по текущему
локальному указателю и DNS, host-key проверка не ослаблялась.

- Open WebUI: `/api/version` = `0.12.2`; runtime image
  `sha256:6cc2c633a09e325b31c03acf57a5c846e381577e98ab43a993c932c599044139`.
- LiteLLM: установленный пакет `1.105.1`, runtime image
  `sha256:b7b9e2c306343721802253d0dd9436b9634a2eb4e14da7c7cf06c5c7b7530802`.
  Нет `DATABASE_URL`; единственный mount — read-only `/app/config.yaml`.
  Это текущий транспорт, а не уже действующий постоянный бюджетный учёт.
- Native config прочитана из SQLite через `mode=ro`: connection 0 — прямой
  OpenAI Responses; 3 — прямой DeepSeek; 1/2/4 — LiteLLM. У всех пяти нет
  дополнительных connection headers. Другие способы передачи идентичности
  этим наблюдением не исключены.
- Оба контейнера healthy, `RestartCount=0`. Ничего не перезапускалось;
  чаты, пользователи, тарифы, лимиты, конфигурация и маршруты не изменялись.
- Локально есть Python 3.11, Node 22 и Chrome. Docker CLI не найден;
  пригодный Linux/Docker-стенд пока не подтверждён. Производственный VPS
  не используется для сборки или репетиции.

Защищённая локальная квитанция и read-only сборщик —
`local/goal584/runtime.safe.json` и `runtime_inventory.py` в рабочей копии GOAL.
Ключи, значения секретных переменных, реальные пользователи и переписки не
попадали в отчёт. Ошибка первого чтения `config.data` исправлена после проверки
схемы: текущая таблица содержит `key/value`, а не один общий JSON-документ.

## Матрица штатных возможностей и решений

Проверенные исходники: Open WebUI v0.12.2,
`6a18585ff4c2e5f6805f682222cfbc46dc669ef8`; LiteLLM v1.105.1,
`d665dc1a6315847fcad6cc2c1264ceb47c06abce`. Текущие docs используются как
указатель, а поведение сверяется с этими версиями.

| Требование | Штатная возможность | Подтверждение на версии | Недостающий минимум | Решение на текущем шаге |
| --- | --- | --- | --- | --- |
| Tool открывает Rich UI без HTML в контексте модели | `HTMLResponse` + короткий result context | Middleware отделяет embeds от текста результата [1] | Привязать к авторизованному чтению владельца расходов | Подходит для свежего снимка при вызове Tool; старый экран обозначать снимком |
| Форма читает свежие данные и сохраняет подтверждённое изменение | Iframe bridge: height/pong/payload; подтверждённая отправка prompt | Payload — свойство компонента; Tool embed его не задаёт. Прямого Tool/Action RPC нет; исполняемый replay подтвердил границу [2] | Требуется другой пользовательский путь либо поддерживаемая новая upstream-возможность | Критичный gap: выбор владельца между вариантами A/B ниже; custom bridge не строим |
| Серверные полномочия и подтверждение | Tool/Action получают `__user__`, `__request__`, `__event_call__` | Native Action проходит авторизацию и проверку чата; confirmation/input вызываются из Python [3] | Проверять текущую admin-роль, точные изменения и актуальность состояния после ожидания | Существующий владелец пользователей; подтверждение отправки prompt не считать подтверждением бюджета |
| Общий месячный бюджет и доли моделей | Scalar user/key budgets; отдельный `model_max_budget` | Native scalar core и adapter user/model проверены на actual image; per-model механизм относится к EE и устроен иначе [4] | Реальный WebUI, сумма долей, смена периода и параллельные вызовы | Один native user + ключ на user/model с отдельным scalar budget. Подбор ключа проверен с имитированными server headers; EE не обходится |
| Один журнал, историческая цена, принадлежность вызова | LiteLLM PostgreSQL spend logs и cost tracking | Есть стоимость события, provider-call ID, session/request metadata [5] | Зафиксированная версия тарифа/usage, полнота, неизвестная цена, служебные операции, durable recovery | Сохраняем одного владельца; отдельный ledger не создаём. Полная пригодность ещё не доказана |
| Стоимость ответа и всего чата со всеми ветками | Native usage merge и status events | Usage складывается по native tool rounds; outlet видит только выбранную ветку [6] | Читать итог по chat/answer из владельца расходов, а не суммировать только активную историю | Показ — отдельное расширение; стоимость из одного регистра |
| Штатное отключение отображения | Filter/UserValves; сохранённый `statusHistory` | Toggleable Filter отключает весь pipeline; UserValves может пропускать будущий status, но не скрывает сохранённые строки [7] | Обычная UI-проверка области сохранения и исторических статусов | Не размещать enforcement в отключаемом фильтре. Полное ретроспективное скрытие не обещаем |
| Охват платных маршрутов и LLM-контекста | Native custom header templates для CC и converted Responses | Есть user/chat/message/task; `MODEL_ID` на обычном пути пуст, root-call template нет; raw `/openai/responses` имеет иной путь [8] | Авторитетная привязка calls, два прямых подключения, provider clients внутри Tools/Pipes | Не переводить всё в CC. До выпуска доказать совместимость и полноту; клиентскую metadata не принимать за серверную принадлежность |

## Варианты пользовательского пути для решения владельца

**A. Rich UI как снимок, действия через новый ход чата.** Tool читает актуальные
данные и возвращает экран с временем и версией. Кнопка формы передаёт ограниченное
предложение через `input:prompt:submit`. Open WebUI спрашивает разрешение отправить
текст; затем модель может вызвать фиксированный Tool. Сервер заново читает
состояние, проверяет admin-роль, показывает точное «было → станет» штатным
confirmation и применяет изменение через владельца бюджетов после повторной
проверки. Обновление даёт новый экран. Это дополнительные ходы модели и,
возможно, два подтверждения; прямого RPC и гарантии выбора Tool моделью нет.

**B. Native Action и штатные диалоги, Rich UI для результата.** Tool открывает
снимок в чате. Кнопка Action под сообщением вызывает Python напрямую через
штатную авторизацию; ввод и точное подтверждение выполняются штатными диалогами.
Сервер повторно проверяет права/состояние и возвращает новый снимок/квитанцию.
Это более предсказуемый административный путь без выбора Tool моделью при записи,
но редактирование происходит в диалогах, а не внутри HTML-формы.

Оба варианта сохраняют sandbox и серверные полномочия, но меняют требуемое
редактирование в самой карточке. Если именно живая HTML-форма обязательна,
на 0.12.2 текущего штатного контракта недостаточно. Ослабление sandbox, инъекция
`execute` в родителя и незаявленная новая подсистема не являются альтернативами.
Ни один из вариантов пока не принят и не реализован.

## Владельцы и ближайший срез

Оставшиеся технические ограничения LiteLLM проверены по source, а не runtime:
`custom_auth` возвращает собственный auth-объект и сам по себе не доказывает
сохранение штатного scalar-key enforcement. Обнаружен существующий MIT-владелец
`authorize_internal_virtual_key`, который native Lens использует для проверки
серверного назначения ключа. Его результат нельзя просто вернуть из custom auth:
внешний auth-путь обнуляет поле reservation и может резервировать повторно.
Нужен один проверенный жизненный цикл проверки, резервирования, списания и
освобождения. Кандидат с model-specific keys остаётся возможным, но не выбран
как реализация. Native `model_max_budget` — отдельный EE-вариант, у которого в этой
версии также не доказана надёжность per-model счётчиков после cache miss и при
параллельной нагрузке. Покупка лицензии сама по себе эти вопросы не закрывает.

Более узкий кандидат для проверки: custom auth аутентифицирует доверенный
WebUI-вызов и выбирает серверное назначение ключа; `IdentityStore` и
`validate_resolved_virtual_key` выполняют штатную проверку без reservation;
внешний auth с `custom_auth_run_common_checks=true` единожды проверяет личный
бюджет и резервирует расход. Это внутренний seam точной версии, а не готовый
документированный продуктовый контракт. До принятия нужны проверка жизненного
цикла на pinned image, отказов/отмены/streaming, отсутствия orphan holds и
невозможности выбрать ключ другого пользователя. Производственный патч,
новый auth-владелец или обход EE для этого исследования не создавались.

Цена тоже требует отдельной проверки: default cost map изменяемый, блокировка
моделей без цены по умолчанию выключена, а отсутствие оценки может пропустить
reservation даже в строгом режиме. Есть штатные настройки заморозки map и
отклонения неизвестной цены. Их надо испытать на реальных категориях usage.
Raw `/spend/logs/v2` доступен в OSS; `/spend/report` относится к premium.

| Смысл → владелец → контракт → потребитель | Классификация |
| --- | --- |
| Пользователь и admin-роль → Open WebUI → native verified user / Tool/Action args → операция управления | Существующий владелец |
| Расход, допуск и остаток → LiteLLM → native auth/budget/spend API → управление и отображение | Предпочтительный существующий владелец; полнота пути проверяется |
| HTML, короткий контекст и видимый статус → штатные Tool/Action/Filter → embeds/context/status → пользователь чата | Тонкая адаптация представления; бюджетных вычислений не содержит |
| Последовательность чтение → предложение → подтверждение → проверка → запись → readback | Координатор; не владелец отдельного бюджета или регистра |

Следующий шаг — получить решение A/B либо требование сохранить исходную живую
форму. Затем проверить оставшийся бюджетный/авторизационный seam и подготовить
минимальный изолированный стенд с синтетическими пользователями и неоплачиваемым
provider stub. После содержательной проверки окончательного запроса и схемы
согласовать ограниченные реальные API-вызовы. Только сквозная обычная UI-приёмка
двух сотрудников, блокировки, восстановления, истории и существующих инструментов
позволит закрыть GOAL. Source replay и docs PR этого не заменяют.

## Воспроизведение и границы доказательств

### Независимый срез: штатный бюджетный core

Подготовлена ограниченная репетиция на закреплённом LiteLLM image без custom auth:
[Compose](../../compose/goal584.native-budget-proof.yml),
[HTTP driver](../../scripts/goal584-budget-proof/prove_native_budgets.py) и
[сверка полученных провайдером вызовов](../../scripts/goal584-budget-proof/verify_provider_calls.py).
[Узкий workflow](../../.github/workflows/goal584-native-budget-proof.yml) запускает
только этот срез на изолированном GitHub runner; существующий Active CI сохраняется.
Runtime proof прошёл в
[run 41435187180](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41435187180):
branch head `2044cb8995852365c4a0f3bffee5cde9c345c279`, испытанный merge
`2b2f015b80a37763cd4f5417b90e120e9aa5684a`. Артефакты прочитаны и независимо
приняты только для native scalar user/key core: 7 положительных spend rows и
7 совпавших provider response IDs, по 10/5 tokens и синтетическим $0.20 на вызов;
итоговые user spends $1.20/$0.20 совпадают с ключами и журналом. Два typed
budget denials не дошли до имитатора; повышение бюджетов восстановило доступ.
Подмена body user/metadata не изменила native владельца расхода. Фактические
образы и SHA-256 fixture файлов связаны с runtime receipt; после теста осталось
0 контейнеров и 0 volumes проекта. Локальная копия пяти квитанций —
`local/goal584/runtime-proof-41435187180/`; hosted artifact имеет retention 7 дней.
Это не приёмка GOAL целиком.

Сохранённые ошибки предыдущих попыток: в запуске
[41433766446](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41433766446)
четыре сервиса стали healthy и миграции завершились, но runner не смог обратиться
к опубликованному loopback-порту. Ошибка не доказывает дефект бюджета: API-вызовы
не начались. Следующий кандидат исполняет тот же standalone driver внутри
существующего proxy-контейнера через его native HTTP endpoint; защита сети и
авторизации сохраняется. Затем
[41434395675](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41434395675)
подтвердил первые три расхода и отказ по бюджету, но обнаружил ошибочную предпосылку
driver о HTTP 400/429: pinned `litellm.budget_exceeded_status_code` равен 422.
Проверка исправлена на точный 422 + `budget_exceeded` + native Key/User scope;
квоты и конфигурация ради зелёного результата не менялись.
Ранее workflow был отклонён до job из-за `runner` context
в job-level env; исправлено и проверено actionlint 1.7.12.
Продуктовая приёмка не подменяется этим тестом.

Четыре временных сервиса: LiteLLM, PostgreSQL, Redis и stdlib-имитатор провайдера
в том же pinned LiteLLM image. Образы закреплены digest, сеть internal, host ports
отсутствуют; платных провайдеров нет. Credentials генерируются
для каждого запуска. Проверка создаёт двух синтетических пользователей и четыре
single-model ключа, сопоставляет реальные native spend logs, суммы пользователя
и ключей, usage, модель и root-answer metadata с семью успешными вызовами. Два
дальнейших запроса должны быть отклонены по разным пределам без обращения к
имитатору. Изменение бюджетов через native API должно восстановить доступ.

Денежные суммы здесь синтетические: 10 input × $0.01 + 5 output × $0.02 = $0.20.
В тесте отдельные key caps намеренно в сумме превышают personal cap, чтобы
проверить оба независимых native ограничения. Это не допустимый шаблон долей
для конечного интерфейса: правило суммы 100% ещё предстоит реализовать и принять.
Также не приняты GUI, доверенный подбор ключа по WebUI-user/model, реальный тариф,
Responses, streaming/cancel/concurrency, смена месяца и полная история чата.
Перед внешним запуском проверены точные source/API/schema, локальный HTTP mock,
синтаксис, изоляция и независимое ревью. Сверка provider receipts отвергает
изменённые context/model/usage и лишний вызов.

Следующий независимый backend-срез — узкий native custom-auth adapter без изменения
LiteLLM source. Он должен выбирать существующий user/model key, передавать проверку
и единственный reservation native владельцам и сохранять management RBAC. Master
recovery и master-only routes требуют явной границы; ad-hoc admin auth не допускается.
Service-task exemption пока не включать: один shared gateway secret доказывает
происхождение соединения, но не достоверность всех TASK/CHAT/MESSAGE metadata.

Уточнение происхождения подтверждено по pinned source и replay: raw
`/openai/chat/completions` переносит клиентские TASK/CHAT_ID/MESSAGE_ID в headers,
тогда как USER_ID берёт из аутентифицированного пользователя. Raw Responses
оставляет клиентскую metadata в body и даёт пустые task/chat headers. Даже native
task endpoints принимают caller chat_id без проверки владельца. Поэтому не
освобождаем от личного бюджета произвольный nonempty TASK и не связываем сервисный
расход с чатом только по этому полю. Legacy function_calling и MOA также нельзя
автоматически считать служебными: это части пользовательского ответа.
Закрытие внешних raw-путей через существующий ingress — только условный кандидат,
требующий согласования совместимости и проверки всех обходных маршрутов, включая
generic proxy, Anthropic/Ollama/embedding paths. Рабочие маршруты не менялись.
Подробные URL и source replay — ignored
`local/goal584/cost-display/provenance-followup.md`.

Кандидат этого среза —
[litellm_auth.py](../../deploy/openwebui-budgets/litellm_auth.py), без изменения
LiteLLM source. Native key alias и metadata задают назначение user/model в
существующей таблице ключей; bounded lookup и native IdentityStore/validator
не ведут собственных расходов. Gateway-ветка требует server-held credential,
native USER_ID и присутствующий пустой TASK. Missing/nonempty TASK и model-less
discovery пока отклоняются, а не становятся бесплатным обходом. Management
работает через настоящий scoped proxy_admin virtual key, созданный stock API
до включения hook; master-only routes читаются из native enum, stock master
не подменяется. Для его восстановления требуется stock config.

[Qualifier](../../scripts/goal584-budget-proof/prove_gateway_auth.py) подготовлен
для bootstrap → hook-enabled run → cold proxy/Redis restart. Он повторно использует
native 7/2 сценарий с имитацией trusted WebUI headers, отдельно проверяет запреты
и native operator access. Сырые fixture-ключи остаются в private state 0600 вне
публикуемых квитанций. Повторный alias проверяется через native API rejection,
а не через внедрённый дубликат БД.
Actual-image runtime прошёл в
[run 41440455795](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41440455795):
head `0bbe61deb13e3ae682237f71d1155866d0255b51`, испытанный merge
`5bb26cbafb1d4c019c1ee7b5b87a6efdba05dbd4`. Source hashes сверены, 11 артефактов
прочитаны и независимо приняты только для этого среза. После bootstrap native
operator сохранил management role/allowed_routes; через gateway повторились
7 успехов и 2 бюджетных отказа. Девять дополнительных auth/provisioning отказов
не создали лишних provider calls. После cold restart proxy и Redis сохранились
users/keys/7 log rows и повторился personal-budget denial. Сверка actual provider
IDs/context/usage и cleanup подтвердила 0 лишних вызовов, 0 контейнеров/volumes.
Квитанции — `local/goal584/runtime-proof-41440455795/`.
Предварительно проверены точные symbols/signatures, исходные контракты, обычная
импортируемость mounted файлов, HTTP-пакет с присутствующим пустым TASK, YAML,
Bash, Python и независимое source review. Это не приёмка WebUI или lifecycle
резервирования при параллельных вызовах/сбоях. Единственность inflight hold отдельно
не измерялась; вывод о владельце reservation пока ограничен исходниковой делегацией
и проверенными завершёнными вызовами.

Следующий шаг — настоящий WebUI native model-discovery и пользовательский
chat-path с этим адаптером. Pinned source обнаружил более простой штатный путь:
непустой connection `model_ids` строит каталог внутри WebUI без upstream GET
`/models`; native Workspace model read grants задают доступ обычным сотрудникам.
Отдельный catalog principal не требуется. Native `/openai/verify` при этом всё
ещё вызывает gateway discovery и не поддерживается текущим hook.
Управление формой,
служебные задачи, ingress/provenance, price versions и полный chat/tool accounting
остаются отдельной незавершённой частью того же GOAL. Выбор A/B не сделан; обсуждение
временного JSON не является разрешением подменить исходный workflow.

### Кандидат настоящего WebUI-стенда

[Compose overlay](../../compose/goal584.webui-proof.yml) добавляет официальный
`v0.12.2-slim` с immutable index
`sha256:34db70a8e8f305dc996c4b459db0949b715400a489ca8a2d1a2a31ae5ddc67bb`.
Registry labels и `WEBUI_BUILD_HASH` совпадают с pinned source `6a18585…`.
У сервиса отдельный disposable volume, internal network и нет host ports.

[Provisioner](../../scripts/goal584-budget-proof/provision_webui.py) использует
native signup/admin-add, connection config, model grants и task config. Два
реальных WebUI UUID становятся LiteLLM user IDs; каждому назначаются $0.80 и
две доли по $0.40. Credentials хранятся вне публикуемых артефактов. Для этого
plain-chat среза генерация title/tags/follow-up и прочих auxiliary tasks выключена
штатной настройкой; это не решение их учёта и не настройка production.

[Browser qualifier](../../scripts/goal584-budget-proof/prove_webui_browser.py)
входит двумя обычными пользователями через форму и отправляет восемь свежих чатов
через native selector/input/send. Ожидаются шесть streamed ответов, два видимых
бюджетных отказа, сохранённый terminal outcome каждого чата, независимость второго
сотрудника и восстановление первого после fixture-увеличения user/key caps.
После каждого действия readback сверяет native user/key spend; provider IDs,
контекст, usage и число фактических dispatch сверяются отдельно. Увеличение
fixture caps через native API не считается приёмкой административной GUI.

Предварительные Python/YAML/actionlint и независимая source/schema проверка
прошли. Репетиция verifier отклонила лишний dispatch, лишний контекст, чужого
владельца, потерю output cap, пропавший отказ, изменённый usage и повторный chat ID.
Локально нет Docker; фактический запуск будет в том же ограниченном Actions job.
Ни эти проверки, ни registry metadata пока не доказывают runtime WebUI.

Первый [runtime 41446525429](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41446525429)
на head `97609bd3306bca126dcef3c61e4eaf5cbb00bea9` запустил healthy stock WebUI,
подтвердил image/source identity, native users/config/model grants/output cap и
обычный вход в Chrome `156.0.8078.47`. UI qualifier остановился на ошибочной
предпосылке `messages` в browser submit: свежий native чат передаёт `user_message`,
а сервер восстанавливает контекст. Дополнительно реальный шлюз отклонил первый
запрос с оценкой $32.61 при spend=0/cap=$0.40. Cleanup подтвердил 0 containers/volumes.
Артефакты сохранены в `local/goal584/runtime-proof-41446525429/`.

Наблюдаемая причина пока уточняется: source подтвердил, что пустая model meta
в реальной UI session включает native built-in tool schemas по умолчанию, даже
без selected tool IDs. Это расходится с заявленным plain-chat fixture. Кандидат
повторной проверки сначала воспроизводит такой запрос и записывает реальный
gateway context/native estimate через **стендовый** документированный custom-auth
delegate; затем native model capability `builtin_tools=false` переводит только
fixture в plain-chat режим. Caps/цены сохраняются. Проверка требует actual context
до/после, terminal отказа и исходного 6-success/2-denial сценария. Delegate
только наблюдает ограниченный синтетический контекст и вызывает тот же product
auth; ни user/key selection, ни резервирование он не заменяет. Production этот
диагностический delegate не использует.

Повторный [run 41448622582](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41448622582)
на `24aabaa1ad07c6f2fc34569af366ccc8d95f18e2` прошёл прежние native/adapter
контроли, но остановился при загрузке диагностического delegate, до WebUI-чата.
Pinned config loader загружает файл относительно YAML, не добавляя `/proof` в
`sys.path`; top-level sibling imports оказались неверной предпосылкой. Ошибка
воспроизведена локально **тем же** `get_instance_fn` из pinned source. Исправление
оставляет top-level зависимости stdlib и загружает product delegate через тот же
native config-relative loader; отдельные load-проверки wrapper/product прошли.
Это исправление стендовой диагностики, а не изменение product auth или бюджетов.

[Run 41449388745](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41449388745)
на `ff53345aa413eb494e4f58efd3e9266f019d49c5` прошёл загрузку и native model
update/readback. Реальный baseline context содержал один `Hi`, `max_tokens=5`
и **30 native tool schemas**; native estimator и сохранённая UI-ошибка совпали
на $32.61. Затем браузер подтвердил два ответа на A, terminal budget denial A
и успешный ответ на B. На сверке трёх расходов qualifier обнаружил ошибку своего
точного сравнения: native aggregate `0.6000000000000001` против Decimal `0.60`.
Необходима только tolerance для представления float; caps и расходы не меняются.
Исправленный comparator проверен на **этом фактическом snapshot**, принимает шум
до $1e-9 и отклоняет разницу $0.01/$0.20. Failure capture дополнен provider/context
readback, чтобы не терять последующие diagnostic rows. Cleanup прошёл; артефакты
— `local/goal584/runtime-proof-41449388745/`. Полный 6/2 сценарий ещё не принят.

### Rich UI sandbox

В Chrome `156.0.8078.76` дополнительно выполнена sandbox-репетиция с теми же
реальными обработчиками и фиктивным локальным cookie-auth backend. При
`sandbox="allow-scripts allow-downloads"` iframe имел origin `null`; чтение
parent DOM/storage, собственного storage и cookie завершалось `SecurityError`.
Родитель получил 200 с тестовой cookie, запрос iframe с credentials пришёл без
cookie и получил 401; ответ iframe прочитать не смог. Прямые Tool/Action/execute
сообщения не создали backend-вызовов; prompt отправился только после подтверждения.
Это настоящая браузерная проверка границы с fake backend, **не приёмка полного
Open WebUI**, серверных ролей или бюджетов. Квитанции —
`local/goal584/rich-ui/browser-sandbox-result.json` и `browser-cleanup.json`.
Тестовый сервер и принадлежащий проверке Chrome остановлены, слушателей не осталось.
Временный профиль остался в ignored-каталоге: автоматическая проверка отклонила
удаление (`blocked by policy`), в том числе после явной проверки пути и процессов.

Из рабочей копии репозитория:

```powershell
git clone --depth 1 --branch v0.12.2 https://github.com/open-webui/open-webui.git local/goal584/open-webui
git -C local/goal584/open-webui rev-parse HEAD
node scripts/prove-goal584-rich-ui.cjs local/goal584/open-webui
```

Скрипт проверяет полные SHA-256 двух upstream-файлов после нормализации CRLF→LF
и исполняет извлечённые реальные обработчики в Node VM с минимальными host stubs.
Проверены snapshot payload, отсутствие прямого Tool/Action/execute RPC, отказ
чужому opaque window и prompt submit только после подтверждения. Это не полный
WebUI, не проверка серверной авторизации и не изменение бюджета.

Дополнительный offline replay в `local/goal584/cost-display/` исполнил функции
headers/usage/history/Responses на синтетическом system/user/tool контексте:
два шага дали 30 input, 5 output, $0.03; выбранная ветка дала $0.03 при $0.05
со всеми ветками. `statusHistory` не вошёл в поля replay. Это наблюдение над
функциями pinned source, а не фактический оплаченный provider-call или приёмка
целостности runtime-контекста. При интеграции окончательный вход провайдера
предстоит сверить до/после существующей ограниченной наблюдаемостью.

Подробные source manifests и квитанции делегированных проверок сохранены в ignored
`local/goal584/{rich-ui,litellm,cost-display}`. Два исходных checkout сверены после
нормализации строк: Chat, FullHeightIframe и middleware совпали. Сторонние
runtime-пакеты не устанавливались. Production остался без изменений.

## Источники и опыт сообщества

1. [Разделение HTML и result context](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/backend/open_webui/utils/middleware.py#L1116-L1137), [официальный Rich UI](https://docs.openwebui.com/features/extensibility/plugin/development/rich-ui/).
2. [Полный iframe handler](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/src/lib/components/common/FullHeightIframe.svelte#L157-L181), [prompt bridge](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/src/lib/components/chat/Chat.svelte#L1732-L1811), [Tool embed без payload](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/src/lib/components/common/ToolCallDisplay.svelte#L183-L192).
3. [Авторизованный Action route](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/backend/open_webui/main.py#L2151-L2161), [Action context](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/backend/open_webui/utils/actions.py#L49-L122), [направление event_call: сервер → браузер](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/backend/open_webui/socket/main.py#L1500-L1538).
4. [Документация бюджетов](https://docs.litellm.ai/docs/proxy/users), [pinned auth](https://github.com/BerriAI/litellm/blob/d665dc1a6315847fcad6cc2c1264ceb47c06abce/litellm/proxy/auth/user_api_key_auth.py), [границы custom auth](https://docs.litellm.ai/docs/proxy/custom_auth), [календарь и часовой пояс](https://docs.litellm.ai/docs/proxy/budget_reset_and_tz). Custom auth не считать автоматически эквивалентом stock key-budget enforcement; выбор токена ещё не доказан.
   [Native internal key authorization](https://github.com/BerriAI/litellm/blob/d665dc1a6315847fcad6cc2c1264ceb47c06abce/litellm/proxy/auth/user_api_key_auth.py#L3938-L3977), [его Lens caller](https://github.com/BerriAI/litellm/blob/d665dc1a6315847fcad6cc2c1264ceb47c06abce/litellm/proxy/lens/billing.py#L29-L109) и [обнуление reservation во внешнем auth](https://github.com/BerriAI/litellm/blob/d665dc1a6315847fcad6cc2c1264ceb47c06abce/litellm/proxy/auth/user_api_key_auth.py#L3478-L3503) задают точную границу следующей проверки; это не доказательство невозможности адаптации.
5. [Cost tracking](https://docs.litellm.ai/docs/proxy/cost_tracking), [pinned Prisma schema](https://github.com/BerriAI/litellm/blob/d665dc1a6315847fcad6cc2c1264ceb47c06abce/litellm/proxy/schema.prisma#L703), [основная лицензия](https://github.com/BerriAI/litellm/blob/d665dc1a6315847fcad6cc2c1264ceb47c06abce/LICENSE), [Enterprise license](https://github.com/BerriAI/litellm/blob/d665dc1a6315847fcad6cc2c1264ceb47c06abce/enterprise/LICENSE.md). Собственная сборка не разрешает production-использование EE без соответствующих прав.
6. [Usage merge](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/backend/open_webui/utils/response.py#L50-L143), [outlet reconstruction](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/backend/open_webui/utils/middleware.py#L4177-L4202).
7. [Filter toggle](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/backend/open_webui/utils/filter.py#L63-L105), [сохранённые status rows](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/src/lib/components/chat/Messages/ResponseMessage/StatusHistory.svelte#L7-L46).
8. [Header templates](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/backend/open_webui/utils/headers.py#L133-L165), [native CC/Responses route](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/backend/open_webui/routers/openai.py#L1433-L1589), [отдельный raw Responses](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/backend/open_webui/routers/openai.py#L1789-L1874).

Проверены несколько независимых community-примеров:

- [Open WebUI discussion #20915](https://github.com/open-webui/open-webui/discussions/20915): custom MCP Apps bridge — обсуждение/сторонняя реализация, а не готовая штатная возможность 0.12.2.
- [Discussion #20235](https://github.com/open-webui/open-webui/discussions/20235): HTML/prompt bridge не доказывает обратный авторизованный Tool RPC.
- [Issue #32852](https://github.com/open-webui/open-webui/issues/32852): передача темы в sandbox — отдельный пробел, не доказательство авторизации backend.
- [Token Usage & Cost Display, commit 9895be7](https://github.com/SmetDenis/openwebui-token-usage-display/blob/9895be72e2d6b0771e8435e7451cd565d83faebc/usage_display.py#L1868-L1937): полезен status/UserValves-паттерн; итог только активной ветки и оценка старых ходов по текущей модели не соответствуют этому GOAL.
- [Quota Keeper, commit 096e4e2](https://github.com/xyonium/owui-quota/blob/096e4e238e583f31d838da1b3ef2819a09b02541/README.md#L11-L44): собственный ledger и passthrough middleware противоречат выбранным ограничениям. Полностью не переносим.
- [LiteLLM #35524](https://github.com/BerriAI/litellm/issues/35524): закрыт как not planned, что не означает исправление отсутствующей оценки в этой версии; pinned source сохраняет ранний выход без reservation. [#36999](https://github.com/BerriAI/litellm/issues/36999): открытое сообщение о неизвестной цене, полезное для проверки отказа при неполных тарифах. [#34732](https://github.com/BerriAI/litellm/issues/34732): открытая проблема session-budget concurrency; её нельзя автоматически переносить на scalar user/key budgets.

## Рабочая копия и доставка

Ветка `agent/goal584-budget-ui`, base `94cd7d4b185bda4eccaf21b5740cae0da1027aa7`.
[Draft PR #585](https://github.com/Kwentin3/corp-openweb-ui/pull/585) сохраняет
коммерческую редакцию, эту запись и воспроизводимую проверку границы Rich UI.
Рабочая копия — соседняя `corp-openweb-ui-goal584`. В неё скопирована собственная
согласованная редакция коммерческого предложения; исходная рабочая копия и её
два изменённых документа сохранены. PR этой стадии не закрывает #584 и не
означает поставку бюджетов. Рабочая копия и ignored evidence нужны для продолжения
GOAL; удаление после интеграции и решения по сохранению доказательств.
