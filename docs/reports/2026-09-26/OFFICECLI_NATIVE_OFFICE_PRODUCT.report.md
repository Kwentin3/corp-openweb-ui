# OfficeCLI: Native для DOCX, XLSX и PPTX

Дата: 2026-09-26. Исправление проходит через существующий глобальный Filter,
единственный Tool Server `officecli` и штатные Files/ACL OpenWebUI.
Продуктовая матрица: **12 профилей, 48 успешных DOCX/PPTX-результатов**.
Дополнительно проверены исходная анкета, Excel и продолжение после reload/model switch.
Исходный read-only снимок: [контекст и аудит](OFFICECLI_DOCX_PPTX_CONTEXT_AUDIT.report.md).

## Причина и изменение

В проблемном чате DOCX оставался доступен в Files: это не потеря исходного файла.
Filter 0.9.1 подключал OfficeCLI, но автоматически выбирал Native только при двух
XLSX. На OpenWebUI 0.9.6 незаданный режим означает старое однократное планирование.
Gemini выбирал инспектор XLSX для DOCX и не переходил к корректной правке;
GPT 6 Luna просил повторную загрузку доступного документа.

Filter 1.0.0 выбирает Native через общий `metadata.params.function_calling`
для каждого основного запроса разрешённого профиля, включая создание без файлов,
одиночные вложения и смесь форматов. Именно этот объект читает установленный
OpenWebUI после inlet; изменение `body.params` на этом этапе не выбирает маршрут.
Список разрешённых моделей теперь один — `target_model_ids`.
Вспомогательные tasks, специализированные модели и явно переданный `tools`
сохраняют прежний контракт. Это общий режим OfficeCLI-профилей, включая обычные
сообщения без файлов; эвристика по словам пользовательского задания не вводится.

Исключение `reasoning_effort=none` для текущего Chat Completions у GPT 5.6 Luna,
GPT 6 Luna и GPT 6 Sol применяется ко всем Office-операциям. Явный несовместимый
effort вызывает объяснимую ошибку до изменения запроса; скрытого снижения нет.
`multi_xlsx_no_reasoning_model_ids` перенесён в `no_reasoning_model_ids`, оба
прежних `multi_xlsx_*` valve удалены. Excel-инструкция по нескольким источникам сохранена.

Короткая общая инструкция указывает корректные DOCX/XLSX/PPTX inspect-операции,
штатные file IDs и различие create/apply. Готовность первого файла больше не
запрещает создание остальных заказанных файлов в том же ответе.
Проверка байтов выявила отдельный дефект Gemini: буквальные `\\n` в DOCX вместо
абзацев. Для простого DOCX теперь используется официальное `add paragraph`
с `props.text`, по одному элементу на абзац. Содержание проверяется, а не
объявляется правильным по успешному JSON. Отрицательный файл и причина сохранены
в [g35-before.json](artifacts/officecli-native-office/g35-before.json).

Новый клиент провайдера, реестр файлов, proxy, модель-дубликат и изменение ядра
не потребовались. OfficeCLI-адаптер, fixed-form normalizer и лимиты batch не менялись.

## Продуктовая проверка

Каждый профиль через обычный интерфейс чата создал DOCX и PPTX без исходных файлов,
затем исправил два загруженных синтетических шаблона. Создание повторено на
окончательной инструкции с отдельными абзацами. Ранее выполненная правка шаблонов
использует тот же неизменившийся inspect/apply-контракт; финальная замена примера
команды затрагивает создание DOCX. Это различие отражено в acceptance index.

| Профиль | Роль | Создание DOCX/PPTX | Правка DOCX/PPTX |
| --- | --- | --- | --- |
| `claude-opus-5` | user | PASS / PASS | PASS / PASS |
| `claude-sonnet-4-6` | user | PASS / PASS | PASS / PASS |
| `gpt-5.4-mini` | user | PASS / PASS | PASS / PASS |
| `gpt-5.6-luna` | user | PASS / PASS | PASS / PASS |
| `models/gemini-3.5-flash` | user | PASS / PASS | PASS / PASS |
| `models/gemini-3.6-flash` | user | PASS / PASS | PASS / PASS |
| `models/gemini-3.1-flash-lite` | user | PASS / PASS | PASS / PASS |
| `models/gemini-3.5-flash-lite` | user | PASS / PASS | PASS / PASS |
| `office-documents` | user | PASS / PASS | PASS / PASS |
| `gpt-6-luna` | admin | PASS / PASS | PASS / PASS |
| `gpt-6-sol` | admin | PASS / PASS | PASS / PASS |
| `claude-opus-5-5` | admin | PASS / PASS | PASS / PASS |

Три последних профиля отсутствуют в каталоге обычного пользователя. Их access
grants и видимость не расширялись. Antigravity и специализированные Pipe/TTS/Arena
не включены: они не входят в квалифицированный OfficeCLI-контракт.

Успех каждого результата включает native вызов, `result_file_id`, два штатных
вложения, доступное скачивание под автором чата, соответствующий MIME, совпадение
SHA-256 скачанных байтов и tool result, отсутствие CLI batch/schema ошибок в
успешном результате и непустой итоговый ответ. Результаты первого и второго
форматов не подменяют друг друга.

DOCX проверяется по заданным текстам и по сравнению с исходным шаблоном:
таблица, колонтитулы, жирное начертание, размер шрифта, стили и остальные части
пакета сохранены. PPTX содержит ровно два заданных слайда; при правке сохранены
геометрия, форматирование, второй слайд, masters/layouts/theme и остальные части.
Сравнение XML игнорирует порядок атрибутов, отступы сериализации, технические
paragraph IDs, пустое `pPr` и служебное `OfficeCLI.LastModified`.
Оно сохраняет текст и значения свойств оформления; добавление custom-properties
допускается только для двух известных свойств OfficeCLI.

Все 24 успешные apply-операции привязаны к точным SHA исходных fixture DOCX/PPTX;
`source_bytes_preserved=true`. В [source-binding.json](artifacts/officecli-native-office/source-binding.json)
сохранена также неуспешная попытка модели, поэтому число записей 25, а успешных 24.
Ошибки отдельных native tool calls не скрываются: модель может исправить
следующий вызов; это не дополнительный retry/fallback в Filter или адаптере.

Матрица и скачанные **синтетические** файлы находятся в
[acceptance.json](artifacts/officecli-native-office/acceptance.json).
Повторная проверка без провайдеров:

```powershell
python docs/reports/2026-09-26/artifacts/officecli-native-office/verify_matrix.py
```

## История и регрессии

Штатная копия проблемного чата `3ae7c644-68a9-4857-8d3b-4476f3e14a7e`
продолжена на Gemini с тем же исходным DOCX ID, без повторной загрузки.
Получен DOCX с вымышленными ответами. Сохранены 178 абзацев OOXML, 10 таблиц,
50 строк, 129 ячеек, 47 нетронутых первых ячеек строк, вопросы и заголовки,
оформление ячеек, styles/theme/settings/numbering/media и колонтитулы.
Три изменённые первые ячейки являются полями ответов: имя, дата интервью и оценка.
Первый batch откатился атомарно на несуществующем пути; следующий native вызов
модели исправил его и вернул результат. Оригинальный чат и исходные байты сохранены.
В Git находятся только [обезличенные проверки](artifacts/officecli-native-office/real-chat-regression.json),
а не частная анкета, ответы или полная история.

После обновления страницы и переключения `models/gemini-3.5-flash` → `gpt-5.4-mini`
под обычным пользователем отредактированы оба ранее созданных файла без загрузок.
Использованы исходные native IDs и пути, наблюдавшиеся в сохранённых результатах
create. Скачанные пакеты сравнили с соответствующими исходными артефактами:
[history-switch.json](artifacts/officecli-native-office/history-switch.json).

GPT 5.6 Luna под обычным пользователем прочитал два XLSX и создал результат с
точными исходными данными, листами Янв26/Фев26, формулами B2*C2, B3*C3,
SUM(D2:D3), пустыми B4/C4 и независимо рассчитанными итогами 350/550.
Это проверка формул и независимый расчёт, а не пересчёт Microsoft Excel:
[xlsx-regression-user.json](artifacts/officecli-native-office/xlsx-regression-user.json).
Другой обычный пользователь не получил частный файл администратора: HTTP 404.

Границы: матрица покрывает простое создание, правку и смешанные DOCX/PPTX-вложения.
Она не обещает произвольное объединение сложных шаблонов со всеми связями,
анимациями, диаграммами или вложенными объектами. Preview/WYSIWYG PPTX (#473)
и тяжёлый старый чат с 29 XLSX/OOM (#527) остаются отдельными задачами.

## Проверки и release

Локально **126 passed**: Filter, OfficeCLI-адаптер/normalizer и существующий
Google protocol overlay. Регрессии проверяют все 12 профилей независимо от
формата/числа файлов, tasks/caller-owned tools, неизменность ссылок,
идемпотентность и явный несовместимый reasoning. `git diff --check` пройден.
Обязательный `broker-reports-ci` проверяется на точном head PR перед merge.

Live Function Active/Global, версия `1.0.0-native-office`, LF SHA-256:
`0cf225ff80feda14820fe600294a2f5b37d2c1363c7ad3d8566f1e8bc5cb3d04`.
Runtime OpenWebUI **0.9.6**, прежний образ
`corp-openwebui/openwebui:officecli-all-models-release-20260926`, image ID
`sha256:095f1a356b38d2461265b58a8b9fbc6d97063b41d68712193a5c08c94bb04097`,
overlay V2 и OfficeCLI **1.0.148** сохранены. Ручной restart, замена образа,
изменение ресурсов, прав моделей и доменных Pipe не выполнялись.

Административная миграция и откат source+valves вместе описаны в
[runbook](../../infra-ops/officecli-openapi-docx-release.md).
Изменения изолированы от dirty Broker worktree. Runtime canaries, fixture uploads,
временный пользователь и частные локальные проверочные файлы удалены. Удалены 25 тестовых
чатов и 98 файлов; исходный чат и документ доступны (HTTP 200).
[Cleanup receipt](artifacts/officecli-native-office/cleanup.json). IDs в evidence относятся
к моменту квалификации; тестовые API-объекты после уборки больше не доступны.
Обезличенные receipts и синтетические OOXML остаются воспроизводимым evidence.

## Первичные источники

- [OpenWebUI: разработка tools](https://docs.openwebui.com/features/extensibility/plugin/tools/development/):
  рекомендован Native. У актуальной документации Native уже default; для
  установленного 0.9.6 выбор проверен по его собственному middleware/router source.
- [OfficeCLI: command reference](https://github.com/iOfficeAI/OfficeCLI/wiki/command-reference):
  штатные read/create/edit/batch для DOCX/XLSX/PPTX.
- [OfficeCLI: основной skill](https://github.com/iOfficeAI/OfficeCLI/blob/main/SKILL.md)
  и [PPTX skill](https://github.com/iOfficeAI/OfficeCLI/blob/main/skills/officecli-pptx/SKILL.md):
  опора на реальные DOM paths и help для неизвестных свойств. Для команды paragraph
  дополнительно проверен help именно установленного OfficeCLI 1.0.148.
