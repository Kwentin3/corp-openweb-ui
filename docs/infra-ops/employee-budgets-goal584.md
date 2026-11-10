# GOAL #584: бюджеты сотрудников и стоимость чата

Текущая редакция после согласования KISS, 10.11.2026. Аудит завершён;
пользователь разрешил доводку общего механизма. **Весь продукт ещё не принят.**
Источник задачи — [issue #584](https://github.com/Kwentin3/corp-openweb-ui/issues/584).
[Отчёт ограниченного аудита](../reports/2026-11-09/GOAL584_KISS_AUDIT.md).

## Результат и границы

LiteLLM — единственный владелец учёта денег, денежных лимитов и SpendLogs.
Общая серверная интеграция автоматически связывает вызов с сотрудником, чатом
и ответом, включая вызовы помощников. Новый конвейер на общем пути обращения
к моделям не требует своего финансового кода. Сотрудник видит стоимость ответа
и накопленную стоимость чата; администратор меняет лимиты через готовую форму
в чате с серверной проверкой прав и подтверждением.
Согласованные месячные бюджеты, доли на модели и отдельный служебный расход
сохраняются; сокращение обвязки не отменяет эти функции.

При отсутствии Usage расход неизвестен; блокируется соответствующая модель
для конкретного сотрудника. Подтверждённый нулевой расход должен отличаться
от неизвестного. Стоимость ответа включает относящиеся к нему вызовы моделей
и помощников; суммы читает штатный ledger, второй калькулятор не создаётся.

Разрешены изменения исходников и проверки на изолированном стенде. Production,
платные API, реальные тарифы/лимиты, deployment и изменение рабочих маршрутов
требуют отдельного согласования. Новые патчи ядра не подразумеваются.
Рабочие Office/Tasks/Skills/Files/STT, контекст модели, reasoning, права и данные
сохраняются. Отключение потокового ответа не считается заменой рабочего Tools.

## Политика рефакторинга

- Существующий компонент → штатная возможность → тонкая адаптация → новый код
  только при доказанном разрыве. Сохранять обновляемость ядра и одного владельца.
- Проверки выбирать по изменению и продуктовому результату. Старые fixtures,
  golden IDs и proof gates — свидетельства, не автоматически новый договор.
  Применимые принятые проверки не повторять без изменения входов или оснований.
- Подробные receipts хранить в артефактах; обновлять эту запись, не создавать
  параллельные планы. Независимые содержательные срезы делегировать ограниченно.
- После GOAL отдельно разобрать разрастание тестовой инфраструктуры: глобальный
  backlog, без превращения этого разбора в условие текущей поставки.

## Проверенное состояние

Аудит09.11: собственный продуктовый код около4066строк против35677строк tests
и26337строк proof/CI. Native LiteLLM владеет spend/reservation/quotas; общий
Filter/Auth/reader добавляет привязку и отображение. Второго ledger нет.
Общий root/actor/call контракт уже существует; отдельный billing framework
для конвейеров не нужен. Не относящийся к задаче WIP сохранён.

Изменения10.11, DELIVERY branch `agent/goal584-budget-ui`, исходники `d63e3bf0`:

- Status «Ответ / Чат» — снимок начисленного на указанное время. Убраны
  has_delegation и просмотр названий tools; pending определяется состоянием учёта.
  Девять выбранных существующих проверок PASS; запрос/auth/stream не менялись.
- Known0 проходит через существующие snapshot/SpendLogs/reader. Native cost0,
  полные Usage, guard success и protected explicit rates обязательны; отсутствие
  audit descriptor само по себе больше не запрещает0. Default/missing/unpriced0
  остаётся UNKNOWN; cost-map-only без explicit protected rates пока UNKNOWN.
  Два ограниченных batch по4existing tests PASS, ABI положительного пути сохранён.
- Денежный proof читает native request_id как opaque ID и связывает строку по
  полному проверенному scope/call_id. Убрана ошибочная зависимость от формата
  provider ID; native owner/key/model/deployment/Usage/spend/caps проверки сохранены.
  Двенадцать целевых случаев PASS. Actual Office этим ещё не принят.
- Known0 browser-профиль добавлен в существующий workflow; unrelated Office
  inference phases пропускаются. Семь offline checks и genuine CC composition
  через Router/Logging/guard/native cost/publisher/reader PASS. Это не приёмка GUI.

Фактический сервер10.11 проверен только чтением: WebUI0.12.2, LiteLLM1.105.1.
Responses connection0 настроен прямо к провайдеру; CC1/2/4 — к текущему LiteLLM,
connection3 другой/не классифицирован. Наши budget Functions не установлены;
у LiteLLM не настроены database/custom_auth/callbacks. Единый бюджетный контур
сейчас не активирован. Финансовый ущерб этим не установлен. Маршруты, бюджеты
и сервисы не менялись, model calls не выполнялись; открытие native browser
выполнило только обычную синхронизацию timezone.

## Последняя стендовая проверка и следующий шаг

Known0 run42774556410 завершился до inference из-за неверного private handoff;
consumer исправлен на существующий webui-state users, без нового файла.
Следующий [run42777661683](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/42777661683)
на точном `d63e3bf0d6c8ce1cd0d66a85c4ed1fa043850397` также завершён FAIL:
native pre-call budget отказал с Current0 / Estimated32.61 / Max0.4, HTTP422.
Нулевой provider response, запись расходов, Details и reload не приняты.
Provider control восстановлен, provider terminal; cleanup подтверждает отсутствие
принадлежащих запуску containers/volumes/networks/images. Artifact13745561195,
634152B, SHA256 e5c3f9d8acc3bf736af86ef2ed8ff0ceee4187f95f3bb9b11b7a1624b3fab9fe.
ZIP скачан один раз; private download URL удалён.

Разобрано несоответствие fixture: saved max_tokens уже5, но native builtin Tools
включены по умолчанию даже при пустом tool_ids. Срез +6строк вызывает существующий
plainchat только для disposable Known0 моделей; проверяет capability=false/cap5.
Production/default Office и лимиты не меняются. Compile/остальной AST/diff PASS.
Точная разбивка3251 input tokens в прошлом запросе не экспортирована и не заявлена.
Ближайший шаг — actual DB/UI/reload на исправленном no-tools профиле.
Лимиты и резервирование не обходить.
Повтор неизменённого кандидата и параллельный конфликтующий запуск не делать.
Для следующего оправданного запуска остаются bounds55min, acceptance8min,
body4min, cleanup2min, ≥12min headroom перед acceptance; native stop —
`gh run cancel <exact_run> --repo Kwentin3/corp-openweb-ui`.
На исправленном `7ea2ed13325b3a9a63d7beb3866016369664ab18` запущен один
[run42780335933](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/42780335933),
08:08:41UTC; manual cancel08:53:41UTC/hard09:03:41UTC.13sourcepins/clean/remoteFF
сверены, предыдущий run terminal/cleanup0. Пока build; runtime не принят.

## Обязательное до завершения

Подготовка поставки: добавлен только `budget_runtime.py` (20строк), который
регистрирует существующий UnknownUsageGuard с native operator key из protected
environment. Missing/invalid format запрещает регистрацию; master fallback и
proof imports отсутствуют. Compile/source import graph проверены; actual image,
права ключа, DB/Redis и установка ещё не приняты. Compose/generator не менялись.
Карта существующих владельцев/import aliases — `release-owner-map.md` в local evidence.
До установки: сохранить image/config/env и native connection/resource/Valves/ACL;
подготовить native DB/Redis, реальные цены и operator/viewer identities до включения
auth; установить Functions/Tool штатными API с source/ACL readback. При откате
сохранить native бюджеты/keys/SpendLogs, вернуть согласованные image/config/resources;
не удалять финансовые volumes и не открывать обход proxy автоматически.

1. Доказать Known0 на настоящих DB/UI/Details/reload, сохранив UNKNOWN и права.
2. Закрыть общую unknown policy на согласованных протоколах. Для CC streaming
   raw Usage теряет происхождение счётчиков; nonstream отключает native Tools.
   Готового установленного native решения пока нет; новый core patch не сделан.
3. Принять достаточный сквозной сценарий: форма лимита → учёт/отображение →
   отказ/восстановление, включая два модельных вызова одного ответа и делегирование
   через общий механизм. Прежние Office81/Native48 применимы в своих границах;
   Office106 proofFAIL не считается ошибкой денег или полной приёмкой.
4. Подготовить единую поставку, конкретный профиль общих маршрутов, установку
   и откат с сохранением данных; production cutover согласовать отдельно.
5. Сохранить полезный WIP/evidence и безопасно убрать свои временные ресурсы.

Подробности10.11: `local/goal584/kiss-refactor-2026-11-10/` (status, known-zero,
zero-native, ledger-scope-proof, runtime-known-zero-retry, runtime-config.safe.json,
cc-usage-native-seam.md, upstream-usage.md). Аудит: `local/goal584/kiss-audit-2026-11-09/`.
Прежняя подробная история сохранена в Git до этой редакции (`d63e3bf0`) и в
указанных артефактах; исторические gates не являются текущим планом.
