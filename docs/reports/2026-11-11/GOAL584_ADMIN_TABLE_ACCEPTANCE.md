# GOAL584: компактная таблица индивидуальных лимитов

11.11.2026. База `592a4534`, ветка `agent/goal584-admin-table`.
Каноническая задача: [employee-budgets-goal584.md](../../infra-ops/employee-budgets-goal584.md).
**Компонентный GUI готов; native приёмка на стенде ожидается.**

Первый эскиз с высокими строками, отдельными ползунками и повторяющимися
пояснениями пользователь отверг после просмотра PNG. Принята плотная таблица:
закреплённая шапка одновременно содержит названия/единицы, управление и легенду;
одна составная полоса100% на сотрудника, N−1 граница между моделями.

## Реализация и границы

Изменён существующий `admin_ui.py`: native HTML table/range/details, CSS и локальный
JS; новых библиотек, mounts, endpoints, credentials, финансовых owners и core patches
нет. Перемещение границы с шагом1% меняет только две соседние доли, точные десятичные
поля сохраняются отдельно. Invalid/нулевые суммарные доли не исправляются молча.
Поиск/отдел, сортировки и фильтр остатка работают по учтённым данным; квалификация
расхода не выдаётся за итог/допуск. Черновик хранится в существующих row DOM nodes,
не теряется при скрытии/перестановке, в план попадают все изменённые индивидуальные
строки с прежними `schema:1`, `type`, `user_id`, `expected_revision`, `budget_usd`,
`shares`. Полные суммы и статусы остаются у backend/LiteLLM.

Краткий footer содержит счётчик/сброс/применение; preview раскрывается по запросу,
обязательный human-readable diff остаётся в native business confirmation.
Подтверждён pinned0.12.2 путь Tool→HTMLResponse→opaque iframe→native embed prompt→
stored user JSON→Tool→fresh server confirmation/write. Эквивалентного прямого
авторизованного iframe RPC нет; оба native подтверждения сохранены. Existing
bootstrap/service панели свёрнуты; групповые действия и новые шаблоны вне этапа.

## Проверенное состояние

Реальные компонентные Chrome PNG проверены на2 и12 сотрудниках при ширине820px:
строки63px, отсутствие горизонтального переполнения, header top49px при прокрутке
внутреннего списка240px. Отдельный PNG показывает3 модели/две границы и0/100/0.
Процент в коротком сегменте имеет приоритет над сокращённым именем; очень узкий
сегмент не показывает обрезанное число. Полные значения доступны в title/«Доли».
Данные эскиза искусственные; это отдельно от native browser/finance приёмки.

Source review границ/безопасности: PASS. В существующем UI suite первоначально
25/26 PASS; один новый assert ошибочно требовал generated `1/99` вместо корректно
сохранённого scale `1.00/99.00`. Исправлена только проверка представления, affected
N2 case PASS; финальный N3/label/boundary case PASS. Логи первого FAIL сохранены.
Предшествующие неизменённые контракты и financial/Office evidence переиспользуются
по source identity; старые полные матрицы не запускаются.

Existing `gui-product` driver дополнен локальными сценариями таблицы, PNG viewport/
редактора/диалогов и сверкой отсутствия prompt/provider/financial effects до Apply.
Два synthetic native пользователя получили разные department через существующий
self info API; тестовая фраза синхронизирована с «Давай поработаем с лимитами».
Native profile по-прежнему использует пять прежних сервисов, job25min/browser6min,
synthetic provider и always-cleanup. Workflow и финансовый verifier не менялись.

Первый actual [42988211059](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/42988211059)
на `263c243f` остановился до Tool/карточки: synthetic `pending_admin_tool` распознавал
старые глаголы «настроить/обновить», но не approved фразу «Давай поработаем с лимитами».
Переданный provider payload и PNG подтверждают обычный ответ Proof, не ошибку UI.
В dispatcher добавлен только привязанный literal intent, прежние controls сохранены.
Actual payload replay через реальный AST-фрагмент выбирает `open_budget_form`;
настройка/обновление, ordinary Hi и apply с пустыми business arguments проверены.
Продуктовый код не менялся. Seed native0.20 прошёл, но GUI PASS этим не заявляется.
Always-cleanup: containers/volumes/networks0, generated image удалён. Первый FAIL
и actual artifacts сохраняются, повтор выполняется только после этой узкой поправки.

Обязательный остаток: actual browser/native/context/PNG/source/image/mount/cleanup
приёмка итогового кандидата. Production/deployment, платные API, реальные лимиты,
новые групповые операции и глобальная реформа тестовой инфраструктуры не входят.
