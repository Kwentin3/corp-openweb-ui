# GOAL: единый native-вход для двух Office workflow

Дата: 07.11.2026. Статус: в работе. Основание — согласованный в диалоге GOAL.

## Текущий проверенный срез

Текущий выпущенный код: commit `19ecfaae`, draft PR #588; required CI `42358402350` PASS.
Native Filter `fdb32101…02ca95`, общий root `77c6707b…343f363` (12495 символов),
version `26e71d53-7b1e-4b30-869d-bc05602e38d1`. Последний root выпущен narrow API/CAS,
metadata/grants сохранены, restart не выполнялся.

| Native model ID | Целевая роль | Обычный Office | Корпоративный DOCX |
| --- | --- | --- | --- |
| models/gemini-4-argon | admin | DOCX create/edit/continue PASS | ещё не принят |
| gpt-6-luna | user/admin | DOCX create/edit/continue PASS после stop-rule repeat | discovery/fact collection/fill/continue artifacts PASS; actual initial child context не записан |
| gpt-5.4-mini | user/admin | XLSX create/edit/continue, formulas/caches/native HTML visual/UI-download PASS | ещё не принят |
| models/gemini-3.5-flash-lite | user/admin | ещё не принят | author publication + interrupted Continue PASS; natural fill routing FAIL, контролируемый child probe в работе |
| gpt-6.1-sol | user/admin | PPTX create/edit/continue artifacts/render/UI PASS; старое создание использовало неправильное делегирование, edit guard его блокирует | ещё не принят |
| gpt-6.1-terra | user/admin | create/edit DOCX content/UI PASS; create Task lifecycle FAIL, continue приостановлен до исправления | ещё не принят в новом охвате |
| deepseek-flash | user/admin | ещё не принят в новом охвате | ещё не принят |
| models/gemini-3.5-flash | user/admin | ещё не принят | ещё не принят |
| models/gemini-3.6-flash | user/admin | ещё не принят | ещё не принят |

Выпущенный Filter 2.2.1 исправляет доказанное сокращение Skill
при handoff: SHA `fdb32101856ef91a9f2a1c49b48e4441ec31b57b009a02ffbe40efe15302ca95`,
root `77c6707b43aba5d22f0d8b5d96a296b3f686dd2e9fe3e12b86636dcc6343f363` (12495).
158 unit checks и независимое source/data-ownership review PASS; 87 exact-native
replay checks PASS, включая view_skill/pin → binder/guard → действующий community
extractor и full Skill ровно один раз. AST взят из deployed Tool source
`790de1a…45fbe`. CI и release PASS; повтор actual child boundary остаётся обязательным.

На новом natural GeminiLite regenerate root присутствовал полностью ровно один
раз, delegate schema доступна, Skill прочитан полностью. Модель обошла delegation:
direct apply к опубликованному оригиналу оставил незаполненными repeat subject и
footer organization. Новый файл не принят; проблема подтверждена artifact comparison,
а не предположением о контексте. Проверяется узкий guard прямой записи в original
из прочитанного pinned published Skill; обычные файлы и продолжение заполненной
копии должны остаться доступными. Контролируемый specialist probe проверяет только
handoff; он не заменяет повтор natural routing после исправления. Контролируемый
запрос также пошёл direct: все ограничения пользователя сохранились в actual
payload, Office guide находился в role=tool, более приоритетного приказа обойти
делегирование не найдено. Передача полного Skill в actual child пока не доказана.

Terra regular create: источник/содержание DOCX, рендер и UI-download корректны;
Tasks созданы до записи, но native `update_task` получил `task_id` вместо `id`.
Схема и ошибка присутствовали в actual payload; модель завершила ответ с открытым
планом. Это argument/recovery failure. Общий root дополнен двумя предложениями
про returned `id` и проверку состояния после ошибки; alias-wrapper не добавляется.
Невыпущенный root: 12684 символа, SHA
`0886ff701d5c22d0241538821f536ff4531f7adf0df3ce491eeba3d9d04e0044`.
При review нового direct-original guard также выявлены обязательные границы:
authoring по прочитанному authorized native authoring Skill сохраняет прямую
правку копии; unrelated unavailable pins не должны блокировать обычный Office.
Финальный кандидат Filter 2.2.2: SHA
`5596a73f80c4fd8f5e88e827957ed34e509da603bec0832d3e2e35edd6bf9b53`.
171 focused checks и 107 exact-native replay checks PASS, включая authoring
ACL/active/historical pin, inactive/unavailable unrelated pins, raw OpenAPI
binder/rebinder, worker scope, direct-original rejection и filled-copy edits.
Исполняется native `get_skill_snapshot`: missing historical version даёт native
404 и не предоставляет authoring exemption. Source contract review PASS;
CI, release и повтор live routing/Task lifecycle ещё обязательны.

Незавершённая строка не считается исключением или квалифицированной моделью.
Presets, ACL-negative cases, невалидный источник, общий review, merge и безопасная
уборка остаются обязательными. Доказательства и временные QA IDs — в ignored
`local/office-unified-native-20261107/`; бизнес-документы и raw payload в Git не входят.

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

Actual GeminiLite consumer поймал отдельный разрыв: ведущая полностью прочитала
Skill 1621 символ, но передала prompt 874 символа. В пяти реальных child requests
worker→Terra root был полный, все 14 OfficeCLI tools доступны, но полного Skill
не было. Данные и простая копия получились верными, однако полнота handoff не
принята. Community автоматически переносит только SYSTEM Skill tags, а native
`view_skill` хранит текст в tool result и pin — в `chat_context.skill_versions`.

Кандидат 2.2.1 материализует pinned snapshot через существующие authorized_skill,
get_skill_snapshot и native formatter только во временных `__messages__`
corporate-owned Tool. Parent history и prompt не меняются, community/worker
сохранены. При нескольких шаблонах нужен точный ID, без выбора «последнего»;
неполнота, конфликт и отсутствие READ/pin останавливают запуск. Отдельной
регистрации Skill/context/store не добавлено. В обычном Sol PPTX модель также
пыталась вызвать corporate Tool; новый no-template guard не допускает такой
маршрут и указывает прямые OfficeCLI Tools. Этот ordinary repeat ещё нужен.

Диагностический owner также проверен: community child имеет `task=sub_agent`;
для его capture нужен существующий `--include-task sub_agent`, одного native
subagents flag недостаточно. Нового логгера не добавляли.

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
Luna: создание/правка проверены; continuation принят после точечного stop-rule
повтора ниже. Ordinary роль: auth/root Skill 200,
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
65 native replay checks и независимое review минимальности PASS.
CI commit `2462e7aaf5f5424444d726bea942711fc3aeff50`, run `42352618921` PASS;
narrow root Skill release/readback PASS, version `3733d74f-1472-4817-87e4-55c57107fdef`.
В чистом повторе модель прочитала authoring Skill целиком (4864 символа, SHA
`d09cc56ca3e46a23f6d1ae0cf4e69d54aee8903ddc20b42a2104e914fa3784f2`),
осмотрела DOCX и предложила карту. Capture расположен перед HTTP send и не
доказывает фактическую доставку upstream. Пустой persisted output во время
streaming не доказывает отсутствия Tool side effects: после Stop около десяти
минут ожидания сохранились create_skill, guard-failed publish, create_tasks и
incomplete publish. Original уже добавлен в Knowledge, Skill ещё private.
Адресный native Continue использовал те же IDs и получил `status=published`;
один Skill, один Original binding и одно membership, без повторного создания.
Root и полный authoring Skill сохранены в resume payload, tool pairing корректен,
авторизационных ошибок нет, Tasks completed. Прежние ресурсы сохранены.
Baseline существующей
библиотеки снят до наблюдаемой QA-публикации: два прежних File ID и шесть Skills.

Luna continuation сохранил данные и выдал последний File ID, но сделал второй
successful apply ради отступа 6 pt. Необходимость косметического прохода не
доказана; этот stop criterion не принят. Финальная копия скачана, значения
проверены, render читаем. Кандидат общего stop-rule уточнён: общие style warnings
и необязательные советы не требуют новой версии после проверки согласованных
критериев. Root SHA256 `52b3d9dfd47209ad38d2acb64a1a04a7848f67e1148fea18c9c2981b8d11f1bc`,
12345 символов; 65 native checks PASS. CI `42353759357` и narrow root release PASS.
Повтор с того же F2 и тем же заданием: первый apply guard-blocked без File,
затем Tasks → один успешный apply; отступ включён сразу в add, post-render writes
нет. UI-download, literal/XML/style preservation, final render и независимый
review PASS. Во всех восьми outbound root полный и ровно один раз.

Mini XLSX create/edit: UI downloads и literal/formula/header-bold проверки PASS;
создание содержит cached 300/600/900, после single-cell edit некоторые cached
values пусты, формулы сохранены, native inspect вычисляет 600/600/1200.
Не выдавать вычисленные expectations за сохранённые значения Excel. В финальном
продолжении фактически сохранены caches 600/600/1200, формулы/стили/все ячейки
проверены; latest chain и Tasks guard подтверждены. Три screenshot вызова при
создании вернули 409 render-slot busy; причину владельца lock это не доказывает.
Точный native HTML последней версии извлечён с совпадением SHA и визуально
проверен в браузере: все данные читаемы. Временный localhost preview helper
остановлен, его временная директория удалена. UI-downloads всех трёх файлов PASS.

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

Следующий шаг: завершить review/replay и выпуск narrow direct-original guard и
общей Task-инструкции, повторить natural corporate routing и Terra lifecycle;
принять actual corporate worker packet и заполненную копию другим
пользователем, затем завершить явную матрицу моделей/форматов/ролей, negative
cases, независимую общую приёмку и Git-доставку. Heavy renders проверять
последовательно с учётом существующего единственного render_slot.
GOAL не завершён; пройдённый Argon DOCX не заменяет остальные обязательные срезы.
