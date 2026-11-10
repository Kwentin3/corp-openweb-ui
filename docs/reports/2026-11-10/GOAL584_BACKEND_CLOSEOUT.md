# GOAL584: завершение backend перед GUI

10.11.2026. **Backend этап принят; обязательного функционального остатка нет.**
Каноническая задача: [employee-budgets-goal584.md](../../infra-ops/employee-budgets-goal584.md).
База `e2d7bb73`, ветка `agent/goal584-backend-closeout`.

## Что изменено

- Новый native Event [monthly_view.py](../../../deploy/openwebui-budgets/monthly_view.py)
  добавляет `GET /api/v1/employee-budgets/monthly`. Без параметра возвращает собственный
  бюджет; `?user_id=<UUID>` другого сотрудника доступен действующему администратору.
  Штатная аутентификация WebUI и свежая проверка Users выполняются до финансового
  чтения и перед выдачей. Event проверяет активность, использует native cache/lifecycle
  и регистрирует route перед SPA; upstream core не меняется.
- Использованы existing `BudgetAdminClient.read_service`, native pooled session и
  common `employee_budget_cost` Valves. Метод читает только выбранного пользователя;
  не обходит каталог сотрудников, не создаёт назначения и не выполняет POST к LiteLLM.
- Единственная публичная проекция `admin_policy.public_employee` дополнена native
  user/model period/reset и остатком по модели. Суммы и остаток — десятичные строки;
  nullable cap, ноль и отрицательный остаток сохраняются. Финансовое состояние,
  допуск запросов, резервы и расход принадлежат LiteLLM.
- Bounded композиция unknown witness извлечена из admin Tool в общий
  `cost_readback.read_unknown_presence`; оба consumers используют одного владельца.
  True witness означает unknown; отсутствие/сбой поиска означает unavailable, не
  known/zero. Поиск истории текущего назначения не объявляется полной историей месяца.
- Устранена лишняя зависимость readonly platform card от `employee_budget_service`
  target: OCR-only platform payer больше не блокирует открытие/применение employee
  admin формы. Native payer/monthly checks, chat signer и mutation confirmation/rights
  остаются у прежних владельцев. Нового API изменения бюджета не создано.

## Маршруты и границы данных

Одним owner-checked read-only запросом native SQLite подтверждено: connection3 —
официальный DeepSeek, enabled, Chat Completions, с динамическим каталогом моделей.
Конфигурация не менялась; provider calls0. Старое `other` было ограничением allowlist
диагностического helper, а не доказательством неизвестного/ненужного сервиса.
Managed preparation по-прежнему должна включать этот enabled slot и потребовать
однозначный эффективный каталог/approved aliases перед production переключением.

API показывает зарегистрированные native counters. `remaining_usd` не является
гарантией допуска запроса с учётом reservations и неизвестного расхода. Period/reset
передаются как native поля без календарного пересчёта. Ответ явно содержит
`expense_observation_scope=assignment_history`; unknown свидетельствует о найденном
неизвестном расходе, unavailable не доказывает его отсутствие. Native keys, aliases,
management credentials и private URLs в публичный JSON не выдаются. Ответ no-store.

## Проверки и фактическая приёмка

95 адресных component/API tests PASS за3.95s: existing admin/policy/readback и новая
Event route вместе в одном процессе; fresh-role/foreign-user denial, zero/unknown,
native period/remaining, lifecycle/cache, readonly и OCR-only admin regression.
Native auth/Users/HTTP IO в component tests явно заменены fixtures; это не настоящая
JWT/DB приёмка. Независимые source reviews API/shared owners: PASS.

Синтаксис workflow,34 inline Python blocks и CLI import closure проверены. Подготовлен
один finite monthly-api профиль существующего стенда: четыре backend services плюс
prebuilt stock WebUI0.12.2, без browser/frontend build и model inference. Пределы:
job25min, worker90s, HTTP5s; полный workflow/pricing/calendar jobs пропускаются.
[Actual run42872143425](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/42872143425)
на `28c35d20a6e5d0bf1b4bf2b65a7729aa9c1dd7ca` прошёл с первой попытки.
API worker6.01s; model inference/provider dispatch0. Проверены сами artifacts:

- Native JWT сотрудника возвращает только его бюджет; действующий администратор
  читает выбранного сотрудника. Чужой доступ403, anonymous/pending401; после
  реального понижения администратора чужой бюджет снова403.
- Первый GET вернул20USD и model caps12/8, spend0 и остатки20/12/8. Existing native
  cap policy изменила лимиты на30 и18/12; тот же HTTP GET сотрудника/администратора
  вернул новые значения с прежним native reset `2026-12-01T00:00:00Z`/`1mo`.
- Native user/key/SpendLogs snapshots и provider observations до/после GET совпали;
  credentials/key hashes/aliases в JSON отсутствовали, ответ no-store.
- Подтверждены38 Git source hashes,5 фактически смонтированных helper hashes,
  source readback двух native Functions и pinned/native identity пяти healthy
  сервисов. Always-cleanup: containers/volumes/networks0, generated image удалён.

Новый smoke использует empty native history: zero counters остаются0, статус
unknown evidence — unavailable. Положительный unknown witness и потеря роли
внутри ожидающего запроса покрыты адресными component checks и прежним native
evidence; новая история/расход не фабриковались. Этот прогон не называется GUI
или новой Tool-confirmation приёмкой. Независимые source/artifact reviews: PASS.

Прежние native billing, limits, unknown block, Office/Tools/reasoning доказательства
переиспользуются на неизменённых владельцах. Продуктовый GUI-прогон, deployment,
платные provider calls, отправка upstream drafts и глобальная реформа тестовой
инфраструктуры этим этапом не выполняются. Новых core patches не добавлено;
[реестр патчей](../../infra-ops/patch-registry.md) остаётся актуальным.
