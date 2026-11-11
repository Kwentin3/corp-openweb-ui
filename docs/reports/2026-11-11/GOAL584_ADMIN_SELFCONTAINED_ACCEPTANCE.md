# GOAL584: модели, публичные цены и состояние оплаты

11.11.2026. База `2c4ae3ab`, ветка `agent/goal584-admin-table`.
Каноническое состояние: [GOAL584](../../infra-ops/employee-budgets-goal584.md).
**GUI native PASS; последний backend срез требует исправления. Production не менялся.**

Кандидат `d7d1205e642536a2522d383332343d8b904f337f`,
[actual 43010403326](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/43010403326):
общий FAIL только на последнем `model-expansion`/financial-refusal срезе.
`admin-boundary.json` PASS: 5 admin turns, 10 admin physical calls, 3 staff successes,
3 quota denials, 16 signed attempts/13 physical, phase 3.00 USD (admin2.40/staff0.60).
Public S1→S2→S1, native расписание/restore, точный stored JSON/Skill/history,
старые суммы и две новые строки по 0.40 USD подтверждены. Ручной снимок/автор/
revision/новая карточка и неизменённые employee finances подтверждены.

Root просмотрел actual general и balance-visible PNG; независимый reviewer
проверил 61 source pin, 6 mounts и 14 PNG hashes. Компонентные 12-row PNG
квалифицируют переполнение отдельно от native двухстрочной таблицы.
Actual financial-refusal остался unconfirmed20s; rows ошибки не экспортированы,
startup log начинается уже в середине опроса. SDK + точный native router formatter
в локальном replay выявил реальный дефект: literal body с дописанным suffix не
читается прежним parser. Единственная причина actual timeout пока не доказана.
Первый FAIL сохраняется. Cleanup подтвердил отсутствие owned containers/volumes/
networks и удаление derivative image. Следующий шаг — узкая поправка parser,
safe failure projection и повтор конечного профиля без расширения матрицы.

Повтор `2d429fc1`/[43012712144](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/43012712144)
снова подтвердил GUI/context/цены/manual; финальный backend FAIL сохранил точную
safe форму: native row failure, model_id B, cache False, APIError, code402,
provider present, native user/model spend0, message173 без JSON/literal.
Это выявило дополнительную границу: native SDK сохраняет общий Payment Required,
но теряет подробный provider code. Точечная поправка распознаёт такой native402
как финансовый отказ; generic429/native422 и отсутствие provider не подходят.
Сумма баланса из ошибки не выводится. 59 readback tests PASS; требуется final actual.

Третий actual `d7447546`/[43014154602](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/43014154602)
снова GUI/context/reconcile PASS; финансовый отказ402 распознан. Проба восстановления
остановилась на503 UsageGuard: прямой native key не передал обязательный подписанный
personal scope. Source `_personal_scope` отвергает это до проверки Usage, поэтому
nonstream regression из этой пробы не следует. Исправляется только вызов пробы:
существующие shared gateway headers/provenance и qualified CC-stream.
Отдельно проверяется обнаруженная source коллизия: pre-stream APIError402 не должен
создавать unknown-usage block; исключение ограничено typed native provider error
до stream response. Существующие неизвестные расходы и midstream failures не
ослабляются. Ресурсы третьего запуска удалены; общий GOAL пока не закрыт.

## Реализация

- Native каталог WebUI/connection/ACL заменяет ручной список. Совпадающие wire
  aliases объединяются без изменения прав. Новая модель — pending с долей 0,
  а не выдуманным нулевым native расходом. Подтверждённое применение создаёт
  только отсутствующий key с hard cap 0 и расширяет native user.models явно.
- Существующий Filter включается как global, с ограничением на общий LiteLLM.
  Native dedup не запускает его повторно на прикреплённых моделях. Контекст
  primary/subagent сохраняется, foreign/Pipe/native auxiliary scope пропускается.
- Цены читает `/model/info`, происхождение/время — `/model/cost_map/source`.
  Managed preparation исключает денежные overrides; обновление/расписание штатные.
  Сравнение текущей цены с native ставками до последней загрузки каталога даёт
  отметку изменения. Собственного каталога/калькулятора нет.
- Существующие SpendLogs дают ограниченное наблюдение финансового отказа и
  последующего оплаченного успеха. Generic 429, кеш, fallback и неподтверждённая
  идентичность не доказывают восстановление. Полное тело ошибки не покидает сервер.
- Ручной снимок проходит прежний stored JSON/Tool/native confirmation путь и
  хранится в protected Functions Valves. Источник/автор назначаются сервером;
  source/role/config/revision перепроверяются. Финансовые таблицы не изменяются.
- Шапка содержит компактные цены/состояния; подробности и статистика сотрудника
  раскрываются. Дата ЛК вводится штатным полем местного времени, хранится в UTC.
  Последствия правок не добавляют новых предупреждений.

## Ограничения

Нет универсального native API денежных остатков. Поддержка balance API конкретного
провайдера пока не квалифицирована; используется ручная проверка ЛК. Наблюдение
событий ограничено семью днями/200 строками/пятью секундами; неполнота означает
неизвестное состояние. Объединение моделей в общий счёт и lifecycle native
deployment IDs задаются защищённой конфигурацией, а не угадываются по семейству.
Нативные Valves не дают CAS для параллельных администраторов. Подробности —
[в инструкции](../../infra-ops/employee-budgets-installation.md).

Прежняя строгая квалификация native zero сохранена: свободная модель с public
ценой 0 без explicit protected rates не получает нового подтверждения нулевой
стоимости только по этому обновлению. Неизвестное не маскируется бесплатностью.
Новые live-сценарии Office/всех мультимодальных тарифов не заявляются.

## Проверки перед native запуском

Переиспользованы существующие tests/venvs и один `gui-product` профиль, без новых
framework/services. Адресные проверки native client/policy, Tool, readback,
global Filter, public preparation, synthetic provider/verifier и sandbox Chrome
прошли. Исходные ошибки устаревших markup assertions и одной новой test-name
ссылки исправлены адресно; финансовые требования не ослаблены.

Компонентные PNG: `local/goal584/admin-selfcontained/ui/`. При 820 px строки
остаются 63 px, шапка закреплена; точные значения сохраняются в data/title,
визуальное форматирование не меняет отправляемые суммы.

Обязательный остаток: зафиксированный кандидат, native GUI с сохранением ручного
баланса и публичной сменой S1→S2→S1 в существующем пятом admin turn; отдельный
native pending→hard-zero assignment и 402→успех на disposable плательщике;
осмотр actual PNG/источника/финансовых результатов и cleanup. До этого общий PASS
не выставляется.
