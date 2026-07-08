# Broker Reports Gate 1 User Friendly Report UX

Status: GATE1_USER_FRIENDLY_REPORT_UX_READY
Date: 2026-07-08
Scope: primary OpenWebUI chat output for Broker Reports Gate 1.

## 1. Decision

The primary chat output must be compact Russian business text, not the full developer JSON package.

Full JSON can remain available for tests, debug logs, artifact inspection or a later "show technical details" action. It should not be the first thing a business user sees in OpenWebUI.

## 2. User-Facing Goals

The chat answer should tell the user:

- whether Gate 1 completed, completed with warnings, or is blocked;
- how many files were processed;
- which formats/classes were recognized;
- which blockers require attention;
- whether the next step is allowed;
- where to click or what to confirm next.

The answer should not expose:

- private normalized slices;
- raw local paths;
- raw OpenWebUI file ids;
- raw filenames by default;
- extracted table rows/text;
- internal schema names as the main wording;
- environment values or secrets.

## 3. MVP Chat Template

Use this shape for a completed run with warnings:

```text
Нормализация завершена с предупреждениями.

Обработано файлов: 5

Форматы:
- CSV: 2
- TXT: 1
- HTML: 1
- неизвестный формат: 1

Найденные типы документов:
- Таблицы операций: 2
- Брокерские отчеты: 2
- Требует проверки: 1

Предупреждения:
- Найден дубликат документа. Проверьте, оба ли файла нужны.
- Один файл имеет неподдерживаемый формат и не будет передан на следующий шаг.

Следующий шаг:
Проверьте предупреждения и подтвердите переход к извлечению фактов.
```

Use this shape for a clean ready run:

```text
Нормализация завершена.

Обработано файлов: 4

Все файлы доступны для следующего шага.

Следующий шаг:
Можно переходить к извлечению фактов из брокерских отчетов.
```

Use this shape for a blocked run:

```text
Нормализация остановлена.

Причина:
Не удалось получить содержимое загруженных файлов.

Что сделать:
Загрузите файлы еще раз или обратитесь к администратору OpenWebUI.
```

## 4. Status Wording

| Internal state | Russian heading |
|---|---|
| `completed` | `Нормализация завершена.` |
| `completed_with_blockers` | `Нормализация завершена с предупреждениями.` |
| `blocked` | `Нормализация остановлена.` |
| `privacy_failed` | `Нормализация остановлена: отчет требует технической проверки.` |

## 5. Blocker Wording

| Blocker code | User wording |
|---|---|
| `no_files` | `Файлы не найдены. Прикрепите документы к сообщению.` |
| `bytes_unavailable` | `Не удалось прочитать содержимое загруженного файла.` |
| `unsupported_format` | `Формат файла пока не поддерживается для следующего шага.` |
| `corrupt_file` | `Файл поврежден или не читается.` |
| `encrypted_file` | `Файл защищен паролем. Загрузите версию без пароля.` |
| `raster_requires_ocr_or_review` | `Файл похож на скан. Для него нужен OCR или ручная проверка.` |
| `zip_requires_review` | `Архив требует отдельной проверки состава файлов.` |
| `duplicate_review` | `Найден возможный дубликат документа.` |
| `unknown_role` | `Тип документа не распознан уверенно.` |
| `privacy_violation` | `Безопасный отчет не прошел проверку приватности.` |

## 6. Next-Step Wording

| Condition | Next step |
|---|---|
| No files | `Прикрепите файлы брокерского отчета и отправьте сообщение еще раз.` |
| Byte access failed | `Загрузите файлы еще раз или попросите администратора проверить доступ к uploads.` |
| Unsupported files only | `Замените файлы на поддерживаемый формат или отправьте их на ручную проверку.` |
| Some blockers | `Проверьте предупреждения. Подтвердите, какие файлы можно передавать дальше.` |
| Ready | `Можно переходить к извлечению фактов из брокерских отчетов.` |
| Privacy failed | `Передайте результат разработчику: безопасная проекция отчета заблокирована.` |

## 7. Technical Details Placement

Allowed secondary details:

- `normalization_run_id`;
- safe artifact refs;
- validation status;
- safe blocker codes;
- safe counts;
- readiness label.

Display these only after the primary business summary or behind a later details action. Do not lead with JSON.

Example footer:

```text
Техническая ссылка: run nr_20260708_...
```

Do not include private artifact refs in ordinary chat unless the ref is explicitly opaque and unusable without server-side access checks.

## 8. API And Test Implications

The implementation may keep a structured object internally, but `render_chat_content` should return the compact Russian message by default.

Tests should assert:

- no private slice text in chat;
- no raw path in chat;
- no raw customer rows in chat;
- no full JSON as primary content;
- status and blockers are still machine-checkable through ArtifactStore or safe debug output.
