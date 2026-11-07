# GOAL: единый native-вход для двух Office workflow

Дата: 07.11.2026. Статус: в работе. Основание — согласованный в диалоге GOAL.

## Результат и границы

Обычный чат сохраняет выбранную ведущую модель и автоматически получает нужные
возможности для двух отдельных сценариев: создание/правка/продолжение
DOCX/XLSX/PPTX; полный жизненный цикл корпоративного DOCX-шаблона
(подготовка, формализация, согласование, публикация, discovery другим читателем,
сбор фактов, заполнение копии). Специальный профиль не обязателен.

Переиспользуются существующие Filter, Skills, Tasks, Tools, фиксированный
корпоративный worker, OfficeCLI, Files/Knowledge/ACL. Общая методика имеет одного
владельца; специальные правила сценариев не копируются по моделям. Не входят
новый оркестратор/планировщик/хранилище, подмена выбранного lead, core changes,
новая система версий/публикации, универсальный production document engine,
расширение корпоративного пилота до любых семейств шаблонов. Несколько версий
допустимы при конкретных дефектах; счётчик файлов не является приёмкой.

## Источники и последняя принятая опора

- Родительский продуктовый контракт: issue #451, обычный чат без обязательного
  Office-профиля. Corporate pilot: PR #581; runbook corporate-template-library.
- Base origin/main `9d261a2145c4483e5841d45cc3878a19e2271400`.
- Собственная worktree `D:/Users/Roman/Desktop/Проекты/corp-openweb-ui-office-unified-native`,
  ветка `agent/office-unified-native`. Независимый STT/commercial WIP и чужие
  worktrees сохраняются.
- OpenWebUI 0.12.2; OfficeCLI 1.0.152. Действующие Function и Skill совпали с main:
  Filter LF SHA256 `18ba45a4b7d09fb6975fcfafec827d27d2fa3446f9dd4c3f5c43f805b5eaa001`;
  artifact-workflow `a741bd8cf92fdf7f1074c4d3cde1e531a8e5b587115d0071fda38992a33d7d61`.
- Диагностика основной рабочей копии: ignored
  `local/office-context-diagnostic-20261107/DIAGNOSIS.safe.md` и связанные snapshots.
  Новые два UI-прогона operator-stopped, не принятые финальные документы.

## Охват моделей и ролей

Источником охвата служит actual native user catalog для целевых ролей/групп,
а не только список провайдера, DB rows или Filter allowlist. Сейчас подтверждены
8 direct text ID у ordinary user: gpt-5.4-mini, gpt-6-luna, gpt-6.1-sol,
gpt-6.1-terra, deepseek-flash, models/gemini-3.5-flash,
models/gemini-3.6-flash, models/gemini-3.5-flash-lite. Все входят в Filter13.
Дополнительно native admin catalog содержит `models/gemini-4-argon`: требуется
проверить совместимость и включить в квалификацию, а не исключать по отсутствию
saved model row. Пять прочих configured ID неактивны/не видны обеим ролям;
`deepseek-v4-flash` также отсутствует в обоих каталогах. Их доступ не меняется.
Nano — image model. Arena — агрегатор с неоднородным текущим пулом, включая image
и специализированные профили; один случайный ответ не квалифицирует весь пул.
Специализированные presets проверяются по своей роли, не считаются отдельными
универсальными текстовыми моделями.

Нативные grants проверены для 3 admin, 30 user и 12 групп. Office/chat-права
департаментских групп эквивалентны: text models, OfficeCLI, reader Skills и
delegation доступны на READ user:*. Author Skill и publisher остаются у admin/
owner. UI-проверка admin не подменяет проверку ordinary reader. Evidence с точными
каталогами/группами хранится в ignored local/office-context-diagnostic-20261107.

Для каждой целевой модели требуется доказательство подключения/контекста и
исполнения обоих workflow; форматные и ошибочные границы покрываются явной
репрезентативной матрицей, без пропуска моделей или неподтверждённых исключений.
Author/publication остаются в действующих правах; reader получает только чтение
и заполнение копии. Проверки через admin не заменяют ordinary-user приёмку.

## Подтверждённые разрывы и принятые ограничения

- В 40 новых и 48 прежних captured payload полный root и timed-источник
  присутствуют ровно один раз. Доставка root в обычном маршруте уже исправлена.
- При одинаковом исходнике Luna создала Tasks первым вызовом, DeepSeek не создал
  в ограниченном прогоне. Наличие schemas/полной инструкции не доказывает исполнения.
  Общие пункты без перечня частей также не являются содержательной приёмкой.
- Обе модели пробовали отсутствующий officecli binary в отдельном Terminal;
  OfficeCLI доступен через API своего сервиса. Это транспортная неоднозначность.
- Корпоративные Tools сейчас привязаны к отдельным профилям; lead/worker Tasks
  явно выключены. Native resolver проверяет READ grants локальных Tools.
- Руководство Word содержит общие требования TOC/обложки; Filter явно ставит
  источник и tool schemas выше общих примеров. Причинность косметических циклов
  не доказана, приоритет/область инструкций необходимо сохранить согласованными.
- Невалидная форма имеет отдельную сохранённую проверку. Отказ validate уже
  изменённой копии сам по себе не устанавливает исходную причину.

## Текущие решения и независимые срезы

Основной агент владеет интеграцией, разрешениями, native UI/provider-boundary
приёмкой и выпуском. Независимые срезы: corporate Skills/profile prompts и
документация; Filter/tests; каталог/ACL и replay установленного native pipeline.

Минимальный кандидат: существующий Filter присоединяет уже имеющиеся corporate
Tools, native ACL исключает недоступные. Условная методика опубликованных DOCX
переносится из профильного prompt к единственному Skill-владельцу; профиль
остаётся необязательным preset. Пакет worker содержит фактически прочитанный
Skill целиком, подтверждённый source File ID и все согласованные факты.

Native Filter.request доступен после tools/context assembly и на продолжениях;
executable callables принадлежат shared metadata tools. Кандидат проверяет
сохранённые native Tasks непосредственно перед созданием Office-файла,
многооперационной правкой, корпоративным заполнением/публикацией и передачей
известной Office-копии в/из Terminal. Одиночный адресный set существующего объекта
и дословный export ответа обходятся без плана. Неизвестные файлы и обычный shell
не переопределяются. Содержательность плана принимается по реальному заданию,
наличие pending/in_progress само по себе её не доказывает.

Community delegation переносит system Skill tags и metadata родителя. Поэтому
общая методика явно различает lead и bounded worker, а request проверяет model
scope независимо от унаследованного marker. Корпоративный путь предоставляет
одиночный run_sub_agent; параллельный вариант того же Tool исключается из
provider schemas и executable map, остальные Tools сохраняются.

Пользователь отдельно подтвердил правило: создание и многошаговая работа с планом,
точечная правка без него. Кандидат этому соответствует.

Focused suite: 135 passed. Exact-native AST replay финального Filter LF SHA256
`fabc0b2f058c380d41b02f24afe376d3e2ee906b5e68c1d8a3707877a197c3b9`:
65 checks passed (binder/rebinder, Task creation/dispatch, Skill/history/provider
conversion, inherited worker marker, schema/executable parity). Внешние IO/DB —
fixtures, не UI-приёмка. Независимое ревью этого исходного/native-integration
milestone — PASS; live/model/product этапы остаются открытыми.
Невакуозные проверки подтверждают наличие guard, отказ без Tasks и raw preset ID
на request boundary; base mapping происходит позже у provider router.
Локальный полный suite: 343 passed, 3 skipped, 7 failed из-за Windows aiohttp
multipart tempfile serialization в неизменённом terminal_file_transfer. Одна
ошибка воспроизведена на base/main. Required Linux CI остаётся обязательным;
тесты и несвязанный Tool ради локальной платформы не ослабляются.

## Git, CI и выпуск кандидата

Кандидат сохранён в commit `bdbf725f121a86b97a84f15d09117b781022c301`,
[draft PR #588](https://github.com/Kwentin3/corp-openweb-ui/pull/588).
[Required Linux CI](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/42350958901)
PASS, включая native file transport/routing и installed OfficeCLI qualification.

Native Function/Skills и два необязательных presets обновлены штатными API без
restart. Worker byte/state-identical; owners, READ/WRITE семантика, остальные
params/Valves и flags сохранены. В Valves добавлен admin-visible Argon для
квалификации, что ещё не означает приёмку. Root SHA256
`c41bab1cf0f4f322041e2d2d648d54941d4cbd93b551089560df776310c34003`,
11777 символов. Help Skill синхронизирован с текущим candidate guide.
Before snapshots и release/readback receipt сохранены privately; rollback готов.

Первый выпуск автоматически откатился из-за слишком строгого сравнения grants:
native API пересоздаёт технические row ID/created_at. Readback исходных contents,
params/Valves, worker и семантики grants подтвердил восстановление. Release helper
исправлен: сравнивает resource/principal/permission, остальные поля exact;
rollback не перезаписывает чужую версию и проверяет восстановленный state.
Независимое review helper PASS; повторный native release/readback PASS.
Ordinary Argon DOCX в отдельном admin QA-чате принят: создание, одиночная правка,
продолжение с последней копии, все факты/таблица/два новых абзаца, XML/style
preservation, render и реальные UI-downloads. На каждый ход одна успешная
публикация. Первая multi-operation запись без активного плана заблокирована без
файла; затем модель создала Tasks и успешно продолжила с F2. Atomic edit прошёл
без нового плана. Независимое artifact/lifecycle review PASS.
Luna: создание и контекст до/после записи/рендера подтверждены, DOCX скачан и
проверен; правка/продолжение ещё в работе. Ordinary роль: auth/root Skill 200,
private author Skill/publisher Tool 401, то есть отказ именно в правах.

Corporate GeminiLite выявил отдельную подтверждённую semantic tool confusion:
во всех 12 requests root полный, доступны 72 schemas, включая native Skill tools
и publisher. Но модель вызвала `load_officecli_skill(skill="corporate-template-authoring")`
вместо `view_skill(id=...)`, получила Unknown skill, подготовила Terminal-инструкцию
и заявила публикацию без `create_skill`/`publish_template`. Все Tasks сразу
completed, поэтому guard правильно отклонил stage/Office publication. Результат
не принят. Общий root дополнен короткой картой владельцев Tools: Workspace Skill
vs OfficeCLI guide; Skill/library publication vs native attachment. Это не копия
авторской методики. Новый root: 12245 символов, SHA256
`df38299b5dcdad3c793a09ffc0e0d7ab00be9019558f7bad35079a5d1b7c615e`;
65 native replay checks и независимое review минимальности PASS. Ещё не выпущен;
повтор корпоративного сценария в чистом чате обязателен.

## Приёмка и обязательные оставшиеся шаги

Репрезентативные входы готовятся до платных прогонов. Синтетический DOCX имеет
таблицу, постоянные условия, header/footer, три обязательных поля, одно optional
и повторения двух полей; baseline SHA256 сохранён privately. Корпоративный цикл
проверяет подготовку и отдельное согласие на публикацию, discovery другим
пользователем без вложения/ID, запрос недостающей даты, заполнение и продолжение
с последней копии. Обычный сценарий проверяет создание, правку и продолжение;
DOCX/XLSX/PPTX распределяются по явной модельной матрице с отдельными проверками
формул, editable objects и сохранности оформления. Каждый включённый model ID
должен пройти оба workflow; проверки общих native ACL выполняются по классам
эквивалентных grants, а не бессодержательным произведением всех групп и моделей.
Это матрица приёмки; завершённые и непринятые срезы указаны выше.

1. Завершить model/role matrix, проверить native owners/ACL/вызовы и выбрать
   минимальные изменения без второго владельца состояния или методики.
2. Реализовать единый вход и согласованные инструкции, разделение OfficeCLI API /
   Terminal и native Tasks для больших задач; локально репетировать окончательный
   запрос/схемы на фактическом входе до платных прогонов.
3. Принять каждый целевой модельный маршрут и оба сценария в обычном UI. Проверить
   контекст до первой записи и после переходов, конкретные части Tasks, историю,
   tool results, отсутствие потерь/непредусмотренной двойной инъекции, полный
   worker packet, выбранный lead, native Task/file lifecycle и причины правок.
4. Проверить реальные артефакты: содержание и пропуски относительно источника,
   неизменность оригиналов, форму/формулы/объекты, финальный File ID, рендер и
   UI-download с совпадением байтов. Отдельно права публикации/чтения и отказ
   чужого источника; повреждённый исходник не заменять молча новой формой.
5. Required CI на цельном кандидате после содержательной проверки, независимое
   evidence-led ревью, narrow rollback и native release/readback. Не собирать
   production VPS; при необходимости runtime image готовится через CI.
6. Выключить bounded capture, завершить свои фоновые задачи, убрать свои тестовые
   ресурсы/временные worktrees после Git-доставки. Приватные данные не публиковать.

Следующий шаг: required CI и narrow native Skill release уточнения владельцев
Tools, повтор corporate GeminiLite в чистом чате; затем завершить явную матрицу
моделей/форматов/ролей, negative cases, независимую общую приёмку и Git-доставку.
GOAL не завершён; пройдённый Argon DOCX не заменяет остальные обязательные срезы.
