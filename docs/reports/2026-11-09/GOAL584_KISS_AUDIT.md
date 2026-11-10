# GOAL584: аудит после уточнения продуктовой цели

09.11.2026. **Аудит завершён; продукт и рефакторинг не приняты.** Только чтение
исходников, конфигурации и существующих результатов. Новые тесты, CI, модели,
Docker/SSH и изменения реализации не запускались. Скачан один уже существующий
артефакт Office106, прочитаны его безопасные квитанции. Production не обследован.

Опора: MAIN `b45181917d743371295aecb00d002d5f0c583121`, DELIVERY
`b745cd8f1745cd1964a73a83a9c23862f4b7c449`; pinned Open WebUI 0.12.2 и LiteLLM
1.105.1. Источник задачи — [issue584](https://github.com/Kwentin3/corp-openweb-ui/issues/584),
с учётом более позднего согласования в чате: общий механизм для всех конвейеров,
один финансовый владелец, два счётчика и готовая форма. Старые proof gates сами
по себе не являются требованиями новой редакции. Это не отменяет ранее явно
согласованных продуктовых правил: месяцы/доли, отдельные служебные расходы,
неизвестный расход и права доступа нельзя молча убрать ради сокращения кода.

## Основной вывод

**Переписывать учёт денег с нуля оснований нет.** В просмотренном продуктовом
пути LiteLLM уже владеет стоимостью вызова, балансами, квотами и SpendLogs.
Отдельной финансовой БД или второго калькулятора списаний наша обвязка не создаёт.
Главное разрастание — проверочные стенды и их индивидуальные ожидания. При этом
есть конкретные общие интеграционные пробелы и небольшие зависимости от имён tools.

Гипотеза «весь действующий трафик уже идёт через один бюджетный кран» **не доказана**.
В tracked release-подготовке LiteLLM обслуживает CC connections 1/2/4, а Responses
connection0 сохраняется. Это факт исходников; актуальные сохранённые настройки
сервера, URL, секреты и наличие бюджетной БД — **НЕ ПРОВЕРЕНО**.
Стенд с PostgreSQL не доказывает такую же production-конфигурацию.

## Что фактически реализовано

| Ответственность | Владелец и evidence | Вывод |
|---|---|---|
| Цена, расход, общий и модельный лимит | Native LiteLLM Logging, users/virtual keys, budget reservation, DB spend writer/SpendLogs; общий bridge [litellm_auth.py](../../../deploy/openwebui-budgets/litellm_auth.py#L252) | Сохранить штатный механизм. Key на пару user/model — native assignment, не отдельный баланс приложения. |
| Сотрудник, чат, ответ и дочерний вызов | Native WebUI User/Chat/Model → [cost_filter.request](../../../deploy/openwebui-budgets/cost_filter.py#L128) → [provenance](../../../deploy/openwebui-budgets/provenance.py#L115) → gateway logging metadata | Нужен один общий серверный контракт. Он подписывает принадлежность, не считает деньги. |
| Два счётчика | [cost_readback](../../../deploy/openwebui-budgets/cost_readback.py#L223) читает native `/spend/logs/session/ui`, группирует по root answer/chat, суммирует сохранённый spend; [Filter outlet](../../../deploy/openwebui-budgets/cost_filter.py#L233) и [Details](../../../deploy/openwebui-budgets/cost_action.py#L83) используют тот же reader | Основа уже соответствует цели. ACL, pagination, неизвестный расход и задержка записи — полезная общая обвязка, не новый биллинг. |
| Управление бюджетом | [admin_tools](../../../deploy/openwebui-budgets/admin_tools.py#L257), [admin_ui](../../../deploy/openwebui-budgets/admin_ui.py#L199), [admin_policy](../../../deploy/openwebui-budgets/admin_policy.py#L251), [admin_client](../../../deploy/openwebui-budgets/admin_client.py#L405) | Native Tool/Rich UI/Chat и management API LiteLLM; нет отдельного сервера админки. JS предлагает JSON, сервер заново проверяет роль, исходное состояние и подтверждение. |
| Неизвестный Usage | [unknown_usage_guard](../../../deploy/openwebui-budgets/unknown_usage_guard.py#L195) использует native block/readback и telemetry, не назначает сумму | Сохранить согласованную политику, но явно ограничить доказанный охват протоколов. |
| Дополнительное описание тарифа | [pricing_snapshot](../../../deploy/openwebui-budgets/pricing_snapshot.py#L284) копирует native rates/descriptor в ту же запись; spend не пересчитывает | Для положительных двух счётчиков полный custom descriptor не нужен. Разделить необходимый native факт и расширенные тарифно-аудиторские требования. |

Обычному новому конвейеру не нужен собственный финансовый алгоритм. Он должен
использовать общий управляемый native dispatch и унаследовать серверный root context.
Создание нового конвейера и подключение новой модели/нового протокола — разные вещи:
новой модели всё равно нужны обычные настройки маршрута, цены, доступа и лимита.

## Где именно возникла лишняя сложность

Tracked diff MAIN…DELIVERY: **141 файл, +72 404/-57 строк**. Физические строки
включают комментарии и пустые строки; ignored evidence и незакоммиченный WIP сюда
не входят. Независимый inventory сохранён в supporting note.

| Часть | Добавлено строк |
|---|---:|
| Бюджетный product code, 16 файлов | 4 066 (5,6%) |
| Все component/proof tests | 35 677 |
| Proof-драйверы/fixtures и CI/Compose | 26 337 |
| Документы | 5 901 |
| Native patch/package и прочее | 423 |

Пять админских модулей занимают 1 573 строки из продуктовых 4 066. Проверка данных,
прав и подтверждения здесь не лишняя «вторая финансовая система». Проблема —
смешение готовности продукта с завершением расширяющегося набора стендовых сценариев.

Последний [Office106](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/42657055754)
завершён на exact b745cd8f: steps1–14 SUCCESS, step15 FAIL, negative16 SKIPPED,
diagnostics/cleanup/upload SUCCESS. Квитанция отказа теперь точная:
`office_row_dispatch_binding_kind_native` в
[proof verifier](../../../scripts/goal584-budget-proof/prove_office_compatibility.py#L690).
Она проверяет предполагаемую форму provider/native ID. Продуктовый reader такую
дешифровку не выполняет: использует native row identity и доверенный root/call scope.
По этому отказу **нельзя заключить, что LiteLLM неправильно списал деньги**;
также нельзя объявить полностью принятой двухмодельную стоимость. Приватные
операнды отказа не опубликованы, точную причину формы ID аудит не устанавливал.
Существующие native component logs:47 guard +22 auth PASS; это не новая приёмка.
Actual cleanup квитанция:0 оставшихся containers/volumes/networks/images.

## Конкретные места для упрощения и обязательные пробелы

1. **Единый маршрут ещё нужно подтвердить.**
   [prepare_google_gateway.py:201–234](../../../deploy/openwebui-upgrade-0122/prepare_google_gateway.py#L201)
   сохраняет Responses0 и переводит только выбранные CC подключения. Release gateway
   получает внешние protected config/env; шаблон [не задаёт бюджетную БД](../../../compose/openwebui.release-0122.google.compose.yml#L12).
   RAG и STT имеют отдельные URL/key owners. Это не доказанные текущие обходы,
   а границы, которые нельзя закрыть результатом синтетического Office-стенда.
   STT audio provider отдельно от LLM-вызова на подготовленном transcript.
2. **Не наращивать общую семантику под имена конкретных tools.**
   [has_delegation](../../../deploy/openwebui-budgets/cost_filter.py#L59) содержит
   три имени для provisional-показа; gateway и Filter отдельно распознают task
   `sub_agent`. Эти места не считают деньги. Ветка sub_agent адаптирует один общий
   entrypoint делегирования; она сама по себе не является финансовым кодом Office.
   Необходимость добавлять новую такую ветку для каждого конвейера аудитом не
   установлена. Нужен общий контракт root/actor/call; endpoint-specific адаптация
   допустима там, где native действительно теряет контекст.
   UI уже умеет честный снимок «начислено на момент», поэтому расширять список tools
   ради заявления о финальности не требуется. Новый settlement-журнал не предлагается.
3. **Подтверждённый ноль ещё не доведён.**
   [cost_readback._row](../../../deploy/openwebui-budgets/cost_readback.py#L251)
   в DELIVERY отвергает spend0/total0. Простое снятие проверки неверно: native writer
   может записать default0 при отсутствии данных. Шесть файлов Known0 в отдельном
   дереве получили source/component review, но не интегрированы и не приняты на
   actual DB/GUI/reload. Отдельный runtime collector там прерван и незавершён.
4. **«Все вызовы через proxy» не означает полный unknown-Usage policy.**
   [Guard:76–81/130–138](../../../deploy/openwebui-budgets/unknown_usage_guard.py#L76)
   помечает streaming CC и native Responses вне buffered-профиля как allow/not_run.
   Native spend при этом может работать. Доказанными нельзя считать блокировку и
   различение unknown/zero для всех таких путей. Проверять это нужно по общим
   протокольным границам, а не строить новый финансовый сценарий для каждого pipeline.
5. **Одна обозримая поставка отсутствует.**
   PR585 draft/open имеет head dc9b96d0, а DELIVERY — b745cd8f; четыре отдельных
   дерева сохраняют21 dirty файл и различающиеся source slices. До их сверки
   нельзя обещать готовый установочный комплект. Полезный WIP не удалялся.

## Предлагаемый следующий этап — до реализации согласовать

**Один ограниченный рефакторинг общей интеграции, а не переписывание биллинга.**

1. Зафиксировать одну целевую конфигурацию managed proxy и общий контракт
   employee/chat/answer/call для main и delegated native вызовов. Сверить этот
   контракт с текущими native owners; сохранить обоснованную security/ACL-защиту.
   Актуальный route/config inventory получить read-only до отдельного решения
   о production cutover. Раздельные служебные вызовы сохранить по согласованной политике.
2. В этой общей границе упростить name-based UI-подсказки, завершить unknown/known0
   на согласованных протоколах и сохранить один reader с native status/Details.
   Полный custom tariff descriptor и несовместимые экспериментальные source slices
   не включать автоматически; сначала отделить действительно нужные части.
   Нельзя удалять native price/rate facts, месяцы/доли или guard без замены их смысла.
3. Выбрать одну coherent поставку и короткую приёмку: форма/подтверждение →
   запрос → две суммы из native ledger → model/total refusal → изменение лимита →
   восстановление; один delegated вызов проверяет наследование общего контекста.
   Отдельно на той же общей границе — known0/unknown, чужой доступ и сохранение
   сумм после reload. Использовать применимые прежние результаты. Не требовать
   повторения фиксированных Office call counts/полного набора исторических gates.

Это предложение объёма, **не начало рефакторинга**. Конкретный diff и проверки
определяются после согласования вывода аудита; удаление файлов/WIP, запуск CI,
deployment и изменения реальных тарифов/лимитов сейчас не выполнялись.

## Источники и сохранённое состояние

Подробности независимых частей:
[traffic/native owners](../../../local/goal584/kiss-audit-2026-11-09/traffic-and-native-owners.md),
[cost/display](../../../local/goal584/kiss-audit-2026-11-09/cost-and-display.md),
[admin/inventory/WIP](../../../local/goal584/kiss-audit-2026-11-09/admin-and-proof-scope.md).
Эти local supporting notes — evidence, не параллельные GOAL-планы.
Actual GitHub metadata и только выбранные safe Office106 receipts сохранены рядом.
Artifact13693731745:1494701bytes/104unique/SHA256
`6041417b29c3a29d9ac2d9e0b559404c60f606c78e3860417e6bc58601359314`;
private download URL удалён. Новых long-running процессов не создано.
