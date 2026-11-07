# GOAL: единый native-вход для двух Office workflow

Дата: 07.11.2026. Статус: в работе. Основание — согласованный в диалоге GOAL.

## Текущий проверенный срез

Текущий выпущенный код: commit `5e693ae99a39bd08679c325b21e35e6052793a46`, draft PR #588;
required CI `42371200603` PASS. Native Filter `5596a73f…bf9b53`, общий root
`2c2797cf…3647ae2e` (13386 символов), version `4813f66b-f32e-40af-ae69-8548379adbeb`.
Последний root выпущен narrow API/CAS,
metadata/grants сохранены, restart не выполнялся.

| Native model ID | Целевая роль | Обычный Office | Корпоративный DOCX |
| --- | --- | --- | --- |
| models/gemini-4-argon | admin | DOCX create/edit/continue PASS | ещё не принят |
| gpt-6-luna | user/admin | DOCX create/edit/continue PASS после stop-rule repeat | natural discovery/facts/fill PASS: actual full template/worker context, source/fields/style/render/UI, parent done + 3 Tasks completed; evidence: corporate-luna-boundary.safe.json и corporate-luna-offline-review.safe.json; continue artifacts принят отдельно ранее |
| gpt-5.4-mini | user/admin | XLSX create/edit/continue, formulas/caches/native HTML visual/UI-download PASS | natural discovery/facts/fill PASS: actual full template/worker context, source/fields/style/render/UI, parent done + 3 Tasks completed; evidence: corporate-mini-verdict.safe.json и corporate-mini-offline-review.safe.json |
| models/gemini-3.5-flash-lite | user/admin | DOCX create/edit/continue content/preservation/render/UI/Tasks PASS после native Continue recovery; initial empty completion без файла — FAIL, причина неизвестна; evidence: gemini-lite-lifecycle-verdict.safe.json и gemini-lite-offline-review.safe.json | author publication + interrupted Continue, natural reader/full worker context/fields/style/render/UI/Tasks PASS |
| gpt-6.1-sol | user/admin | fresh PPTX create/edit/continue content/preservation/all-slide render/UI/Tasks PASS; первая ошибочная попытка корпоративного делегирования заблокирована guard, модель восстановилась сама; evidence: sol-scope-offline-review.safe.json | ещё не принят |
| gpt-6.1-terra | user/admin | repeat DOCX create/edit/continue, content/preservation/render/UI/Tasks PASS | ещё не принят в новом охвате |
| deepseek-flash | user/admin | create/edit/continue content/preservation/render/UI/Tasks PASS; repeat после root9bc — один write без косметического повторения | ещё не принят |
| models/gemini-3.5-flash | user/admin | DOCX create/edit/continue content/preservation/render/UI/Tasks PASS; point-repeat после da44 без Task calls, changed artifact review в работе | ещё не принят |
| models/gemini-3.6-flash | user/admin | DOCX create/edit/continue content/preservation/render/UI/Tasks PASS; atomic edit без Task calls; evidence: gemini36-offline-review.safe.json | ещё не принят |

Предыдущий выпуск Filter 2.2.1 исправляет доказанное сокращение Skill
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
делегирование не найдено. После выпуска 2.2.2 natural regenerate первого запроса
достиг actual worker: corporate-office-worker → gpt-6.1-terra; root 12684 и полный
template Skill 1621 переданы ровно по одному разу до первой записи. Native output
`b9654b5e…` прошёл независимую сверку всех полей/повторов/footer/optional row и
сохранности исходника/формы; UI-download SHA `f03d3c2f…05a999c`, 38638 bytes.
Actual worker render из capture декодирован и просмотрен, все данные читаемы;
нового render для приёмки не создавали. Parent Tasks 3/3 completed. В этом
запуске parent direct write не пытался выполнять; runtime direct gate ещё не
упражнялся live, exact-native binding/rebinding покрыт 107-check replay.

Terra regular create: источник/содержание DOCX, рендер и UI-download корректны;
Tasks созданы до записи, но native `update_task` получил `task_id` вместо `id`.
Схема и ошибка присутствовали в actual payload; модель завершила ответ с открытым
планом. Это argument/recovery failure. Общий root дополнен двумя предложениями
про returned `id` и проверку состояния после ошибки; alias-wrapper не добавляется.
Выпущенный root: 12684 символа, SHA
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
CI и narrow release PASS; worker/Valves/presets/grants сохранены. Защищённый
rollback snapshot сохранён в native data. Повтор live artifact/Task lifecycle
ещё обязателен.

ACL-negative: существующий private admin QA File недоступен обычному пользователю
(auth 200, Files content 404); actual Office inspect вернул ошибку, записей и
придуманного содержания нет. Общий Office HTTP502 сам по себе не выдаётся за
ACL-доказательство. Дополнительная liveness-проверка DeepSeek: native ответ
сохранён за 3 секунды, но новый UI оставался busy; открытие сохранённого чата
восстановило ответ без повторной генерации. Причина UI-расхождения не установлена;
это не основание исключать модель или объявлять provider hang.

Invalid-source negative PASS: uploaded synthetic PPTX точно совпал с fixture;
из второго слайда удалён required p:cSld. Первой Office-операцией был native
validate, вернувший конкретную schema error. Lead назвал part/path и предложил
исправный источник либо согласованный ремонт копии. Create/apply/delegation,
новых файлов и молчаливой пересборки нет. Root 0886 полный однократно в 6/6
actual payload, источник и его байты сохранены.

Terra repeat: create правильно использовал returned Task IDs и завершил 2/2;
single-set edit прошёл без нового плана. Continuation создал новый план до двух
add и продолжил последний File ID: `4354d561…` → `b21db690…` → `15ddea9c…`.
Независимая XML/semantic проверка всех трёх DOCX PASS; сохранность source text,
таблицы, styles/section params и точные два новых абзаца подтверждены. Все три
UI-downloads совпали с native SHA; create/continue renders просмотрены, читаемы.
Continuation before-write/post-file/postrender context записан; лимит capture20
исчерпан перед последними provider rounds. Final Task completion подтверждён
native persisted trace и DB (2/2), не объявлен захваченным за пределами лимита.

DeepSeek regular lifecycle: `9588f4d6…` → `1d8f5176…` → `cc8068f7…` → `0ae6c7a4…`.
Все native Tasks завершены, lead сохранён, native Files и UI-downloads совпали;
независимая проверка полного содержимого/формы PASS. Однако первый continuation
уже был полным и читаемым, а второй изменил только before=10pt нового абзаца.
Это необязательная косметическая версия, не исправление ошибочного счётчика
5 paragraphs / 6 body elements. Stop-rule не принят по этому прогону.
Общий root уточнён только в строке 53: оформление новых объектов выбирается
до записи и входит в тот же batch; новый выпуск — для конкретного дефекта
задания; косметика уже читаемого результата остаётся для отдельного запроса.
Кандидат root 12887 / SHA
`9bc3f6ba5735905b70f75a7259e02727d578fefe19fedc9c8b4ad9a61186e699`;
Filter/Tools/Task state не меняются. Independent semantic review PASS; exact
native formatter в обоих режимах передаёт весь root без усечения. На actual
failed input перед косметикой заменён только SYSTEM root once; 63 items,
26 tool results, images, history и schemas сохранены. Required CI и narrow
root-only release PASS; Filter/Valves/Models не обновлялись. Исходный DeepSeek
continuation повторён с тем же parent/source и без новых подсказок пользователя;
actual выполнение stop-rule проверено: на том же исходном запросе и ancestry
получен единственный write `1d8f5176…` → `0916d035…`; оформление включено сразу в
первый batch. После render новых записей нет; Tasks 2/2 completed. Root 9bc
передан ровно один раз в 8/8 actual requests. Независимый semantic/XML review,
UI-download и визуальная проверка grid2 PASS; новый SHA `74e6a3b3…b3e0a8d`,
5916 bytes. Предыдущая ошибочная ветка не попала в повторный provider context.

Gemini 3.5 Flash regular: native create/one-set edit/2-add continuation завершены,
все Tasks закрыты, выбранный lead сохранён, лишних версий и скрытого worker нет.
Content verification/UI-download PASS. На однооперационной правке модель
добровольно создала Tasks, хотя guard их не требовал: это расходится с решением
пользователя «точечная правка — без плана». Root step4 уточнён императивно:
single-object edit/verbatim export выполняется без нового плана; осмотр,
validate/render не превращают точечную правку в многооперационную. Создание и
реальные многооперационные изменения сохраняют Tasks; existing state не меняется.
Кандидат root 12970 / SHA
`da44d7812d05e68b404623d0c939c42e358633eb62832ba01745a4dd262d438c`.
Independent source review и proportional actual-input/native-formatter rehearsal
PASS: заменён только SYSTEM root before optional Tasks, остальные 25 items,
9 tool results, images/IDs/schema и приоритеты сохранены. Formatter передаёт
весь root без offset в обоих native режимах. Required CI и narrow root-only
release PASS. Исходный single-set edit повторён без подсказки пользователя про
Tasks: actual root da44 полный однократно в 6/6 requests; один SET c2, Task calls
0, старые Task IDs/statuses остались completed. Native/UI File `607c2fa9…`,
5800 bytes, SHA `635e2d4e…39096097`; semantic verification PASS. Changed artifact
preservation review ещё закрывается. Create/continue native PNG независимо
просмотрены полностью; header/title/metadata/table читаемы. Подозрение на crop
при первичном просмотре не подтвердилось после сверки SHA и original-pixel crop;
renderer-дефект не заявляется.

Репрезентативный большой ordinary DOCX проходит отдельную приёмку: cached-native
history/Skill/file-context/Responses projection — 13 checks PASS. В actual run
`a139d5b4…` выбранная Luna сохранилась; в 12 записанных outbound requests полный
assistant-источник 144102 символа и root 12970 присутствуют ровно по одному разу,
доступны 65 schemas, включая Tasks. Тот же загруженный File `3003bda6…` успешно
прошёл native inspect/validate с нулём ошибок. Два HTTP 502 относятся к вызовам
с ошибочно переписанным моделью File ID; после исправления inspect успешен,
auth failure этим не доказан. Кандидат `a28fa83d…` получил предварительный
semantic/structure PASS по всем 17 темам, решениям против предложений, неизвестным
полям и позднему отзыву срока. Большой запуск остановлен оператором и не принят:
последующие правки ради пагинации не устранили наложение в native PNG; точная копия
`8a3669be…` через установленный Terminal LibreOffice дала четыре страницы без
наложения. Это доказывает расхождение рендереров, но не Microsoft Word parity.
Уточнён только существующий error/recovery bullet общего artifact-workflow Skill:
до новой DOCX pagination repair проверить тот же result_file_id через штатные
stage_chat_file → LibreOffice/PDF → display_file, не публиковать неизменённый DOCX
ради проверки; при недоступности пути выдать копию с конкретной границей проверки.
Все три schemas доказаны в actual Large 65-tools input. Root 13386 chars,
SHA `2c2797cfd89e897cdd1c52db0a9b4f6ab4d19017b09272aa7a8339743647ae2e`:
11 local native formatter/Responses checks PASS на остановленном payload f708/010;
кроме одного полного root сохранены история, results, images/reasoning и schemas.
Это input-rehearsal, не behavioral acceptance. CI `42371200603` PASS; root выпущен
native CAS с metadata/flags/permissions readback, exclusive backup
`root-before-pagination.private.json` mode0600, без restart (`release-pagination.safe.txt`).
Новый Large-run `4d55f213…` идёт в свежем synthetic chat `5210efd8…`: в первых четырёх
actual requests source144102 и новый root13386 сохранены ровно по одному разу,
lead — Luna, schemas65 включают stage/run/display, приложен тот же File3003.
Новый запуск остановлен: после чтения опубликованного QA Skill ведущий вызвал
corporate worker для обычной загруженной формы, хотя prompt различал её и original
шаблона. Actual schema `run_sub_agent` содержала противоречивое общее требование
немедленной делегации задач с 3+ шагами; generic prompt description подтверждён
и в owned Tool metadata, community source `790de1a…45fbe` не менялся. Кандидат
Filter 2.2.3 уточняет только descriptions корпоративного resolved Tool/schema:
заполнение копии original опубликованного DOCX по прочитанному Skill и фактам;
ordinary forms — direct OfficeCLI. Callable, публичные аргументы, worker и root
не изменены; factory specs копируются без изменения исходных объектов. 182 focused
checks и 11 checks на actual failed payload PASS: изменены только два descriptions,
root13386/source144102/history/results/images/reasoning и 65 schema shapes сохранены.
Это устранение конфликтующей подсказки, не semantic enforcement; CI/release и
повторная продуктовая приёмка, включая ordinary transfer/render/display, впереди. Evidence:
ignored `representative-large-task/large-history-preflight.safe.json`,
`large-actual-boundary.safe.json`, `large-actual-inspect.safe.json`,
`large-candidate-a28fa83d-review.private.json`, `large-lo-comparison.safe.json`,
`large-terminal-schema-proof.safe.json`, `large-pagination-root-rehearsal.safe.json`,
`large-fresh-first-boundary.safe.json`, `large-fresh-delegation-schema.safe.json`,
`large-delegation-scope-rehearsal.safe.json`
внутри указанного ниже local-каталога.
Оставшаяся матрица, corporate/native UI/readback и optional author preset требуют
завершения; для оставшейся admin-проверки нужен штатный повторный вход владельца
в отдельной сессии, ordinary Maria session сохраняется. Required CI, независимый
общий review, Git-доставка и безопасная уборка остаются обязательными.

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

Следующий шаг: завершить оставшуюся явную
матрицу моделей/форматов/ролей и presets, независимую общую приёмку и Git-доставку.
Корпоративный worker packet и два negative cases уже приняты в своих границах.
Heavy renders проверять
последовательно с учётом существующего единственного render_slot.
GOAL не завершён; пройдённый Argon DOCX не заменяет остальные обязательные срезы.
