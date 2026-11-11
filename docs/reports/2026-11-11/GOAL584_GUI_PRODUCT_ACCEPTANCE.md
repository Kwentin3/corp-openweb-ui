# GOAL584: минимальный GUI и продуктовая приёмка

11.11.2026. База backend `84dace32`, ветка `agent/goal584-gui-product`.
Каноническая задача: [employee-budgets-goal584.md](../../infra-ops/employee-budgets-goal584.md).
**Source готов; фактическая браузерная приёмка ещё ожидается.**

## Изменение продукта

В существующее native действие **«Стоимость: детали»** добавлен раздел личного
месячного бюджета: лимит, учтённый расход, остаток, период/обновление и данные по
моделям. Повторное открытие читает свежий снимок. Уже готовые суммы ответа/чата,
admin Tool/форма/подтверждения и финансовые владельцы сохраняются.

GET и Action используют один public `Event.read_monthly` с native пользователем,
прежними правами, client/readback и публичной проекцией. Ключей и fetch в iframe нет;
отдельные credentials, module mounts, финансовые расчёты и core patches не добавлены.
Monthly unavailable отображается явно и не превращается в ноль; отозванные права
запрещают выдачу всего снимка. Exact native ноль, unlimited/отрицательный остаток и
неизвестный расход различаются. Расход/остаток не обещают допуск следующего запроса.

Использован штатный message embed: нужен существующий собственный ответ. При
намеренной публикации чата публикуется и снимок; карточка сообщает об этом и не
показывает email/UUID сотрудника. Это не разрешает свежего чтения чужого бюджета.

## Проверка и границы

30 адресных component/API checks PASS1.99s. Финансовые/конвейерные владельцы16
файлов совпадают с принятой backend базой; cost section AST сохраняется. Независимые
source reviews native seam и finite browser-профиля PASS. Эти проверки отдельно
от runtime/browser приёмки.

Используется один `gui-product` профиль существующего workflow: пять прежних
сервисов, prebuilt stock WebUI0.12.2, LiteLLM1.105.1 с двумя ранее принятыми патчами,
прежний браузерный driver. Job25min, browser6min/330s alarm; full suites, calendars,
pricing и Office rebuild не запускаются. План приёмки: native admin form/open,
cancel/apply/recovery и точный сохранённый JSON; employee self monthly/Details,
native counters/период, foreign403, reload и отсутствие финансовых/provider
эффектов от чтения; actual source/image/mount identity и cleanup.

Первый actual [42971394155](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/42971394155)
на `bf09b7b4` остановился после native отмены изменения: inherited driver сравнивал
карточки целиком, включая обновлённый `expense_as_of`. Actual HTML diff показал
только новые timestamps наблюдения на уровне сотрудника/моделей; exact native
сравнение лимитов/расходов сотрудников прошло. Исправлен только driver: из сравнения исключается
этот timestamp, все остальные поля и native финансовая проверка сохраняются.
Seed0.20/native settlement, реальное открытие формы и оба подтверждения отмены
прошли. Cleanup подтверждён: owned containers/volumes/networks0, image удалён.
Actual HTML replay подтверждает поправку: шесть различий timestamps допускаются,
изменения финансовых/идентификационных полей, models/order/count по-прежнему
отклоняются. Продуктовый/backend код после этого результата не меняется; полный
GUI PASS пока не заявляется. Модельные обращения администратора при работе с
формой учитываются отдельно; отмена не называется бесплатным LLM-вызовом.

Неизменённый Office/helper путь переиспользует ранее принятую scoped финансовую
приёмку: [42792989666](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/42792989666),
Sol1.20 + Terra0.12 = employee/answer/chat1.32; service0.20 отдельно. Это прежние
native assertions и browser evidence до отдельного DOCX-checker failure, который
разобран на предыдущем этапе; данный GUI-прогон не называется новым Office run.
Positive unknown используется из прежнего native evidence и адресного render check,
а не выдумывается из отсутствия witness. Production, платные API, реальные лимиты,
upstream публикация и глобальная реформа старых тестов остаются вне этого этапа.
