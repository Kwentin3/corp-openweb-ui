# GOAL584: компактная таблица индивидуальных лимитов

11.11.2026. База `592a4534`, ветка `agent/goal584-admin-table`.
Каноническая задача: [employee-budgets-goal584.md](../../infra-ops/employee-budgets-goal584.md).
**Этап принят: исходники и native GUI на изолированном стенде.**
Actual кандидат `8ae015a57027e501084d0507deb5e5445e8ad47b`,
[run42989620455](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/42989620455)
SUCCESS. Обязательного остатка в этом этапе нет; production не менялся.

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

Перед финальной приёмкой оставались actual browser/native/context/PNG/source/
image/mount/cleanup проверки; они закрыты результатами ниже. Production/deployment, платные API, реальные лимиты,
новые групповые операции и глобальная реформа тестовой инфраструктуры не входят.

## Итог actual приёмки

Браузерная фаза67.11s: настоящий native signin администратора/двух сотрудников,
первый запрос «Давай поработаем с лимитами» открыл Tool/карточку. Локальные поиск,
отделы/остаток, сортировки, keyboard boundary1/99, точные индивидуальные правки,
скрытый черновик, «Только изменённые», сброс, inline validation и live diff прошли.
Actual `admin-table.json` содержит6 этапов: general/filtered/empty/draft/error/preview.
Native prompts и completion POSTs во время локальной работы0; provider/context,
users/keys/admin accounting/attributed rows до/после совпали.

Сохранилась прежняя конечная native последовательность:4 admin turns,8 admin
physical calls,3 employee successes и3 quota denials, восстановление после cap
increase. Всего14 signed attempts/11 physical calls, лишних provider calls0;
phase2.20 synthetic USD (admin1.60, staff0.60), отдельный исходный seed0.20 находится
в baseline и собственных provider/context/native receipts. Точные stored JSON
совпали с provider requests, apply arguments пусты, полный Skill сохранён в system
context, HTML/GUI/фильтры в model context не попали. Native отказы и foreign monthly403
подтверждены; ранее принятые role/unknown/Office владельцы переиспользованы, их новые
живые сценарии не заявляются.

После Apply native свежая карточка показала40/0/40USD для первого сотрудника и
0.4/0.2/0.2USD для второго; лимиты моделей соответствуют индивидуальному плану.
Отмена сохранила employee финансовое состояние. Финансовые компоненты15 файлов и
workflow/Compose/verifier4 файла совпали с базой592a4534.

Root и независимый reviewer просмотрели настоящие PNG редактора/viewport, включая
фильтр, черновик, ошибку, preview, business confirmation и сохранённую таблицу;
они находятся в `local/goal584/admin-table/run-42989620455/` и actual CI artifacts.
Root проверил61 Git-LF source pin,6 actual mounts,4 сохранённых extension sources,
5 healthy images и12 PNG hashes. Raw Windows UI SHAa98d92cf соответствует Git-LF
SHA7e315 после нормализации CRLF; native core/stream/OpenAI SDK maps прежние.
Итоговый независимый review R1–R5: PASS. Cleanup подтвердил0 owned containers/
volumes/networks; temporary derivative image удалён.

Дополнительный actual pointer replay N3 на source-bound компоненте:
20/30/50→35/15/50→35/60/5; попытка пересечь соседа ограничена95/0/5. Другие доли
сохранялись, JS errors/prompt posts0. Это компонентная проверка, отдельно от native
backend приёмки. Sticky проверен в12-row компоненте: header top49 при scroll240;
native2-row сценарий не выдаётся за новый overflowing native directory case.

Ограничения: две native модалки и новое сообщение со свежей карточкой после
сохранения сохраняются; coarse bar1%, точные поля доступны отдельно. В Linux CI
шрифт значка информации отличается от Windows preview; названия, суммы, controls
и title-подсказки читаемы. Установка production и реальный provider требуют отдельно
согласованного этапа. Первый FAIL тестового dispatcher сохранён, а не переименован
в PASS; продуктовая UI версия между двумя actual runs не менялась.
