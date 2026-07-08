# Broker Reports OpenWebUI Document Normalization UX

Status: GATE1_UX_FLOW_READY
Date: 2026-07-06
Scope: Stage 2 Broker Reports / XLS NDFL, Gate 1 user workflow

## 1. UX Goal

Пользователь остаётся в OpenWebUI.

Он создаёт чат или проект клиента, загружает документы, явно запускает нормализацию и получает безопасный отчёт в этом же чате. Отдельный пользовательский sidecar UI не нужен.

Gate 1 помогает понять состав пакета и готовность к следующему разбору. Он не считает НДФЛ, не извлекает source facts через LLM, не делает декларацию и не генерирует XLS/XLSX.

## 2. Recommended UX

Рекомендуемый UX:

```text
Action/Tool-triggered normalization from chat
with slash prompt as fallback
```

То есть основной путь должен быть явным действием "Нормализовать документы" в чате или tool-trigger внутри Workspace Model. Slash prompt нужен как запасной способ запуска:

```text
/broker_gate1_normalize
```

Скрытый "магический" запуск по обычному сообщению не должен быть единственным UX.

## 3. User Flow

1. Пользователь создаёт чат/проект клиента в OpenWebUI.
2. Пользователь загружает документы клиента в этот чат.
3. Пользователь запускает команду или действие "Нормализовать документы".
4. OpenWebUI показывает progress/status.
5. Backend-only normalizer читает approved file refs/bytes.
6. Normalizer создаёт safe/private artifacts.
7. Пользователь получает safe normalization report в этом же чате.
8. Пользователь видит доступные `case_group`.
9. Пользователь выбирает `case_group`.
10. Пользователь переходит к следующему гейту: "Извлечь факты из выбранного кейса".

## 4. What User Sees

В безопасном отчёте пользователь видит:

- сколько файлов загружено;
- какие контейнеры распознаны: PDF, XLSX, CSV, TXT/HTML, ZIP, image, unknown;
- какие документы выглядят как source evidence candidates;
- какие документы похожи на calculation/output artifacts;
- какие ZIP/raster/unknown требуют review;
- какие дубликаты найдены по hash;
- какие `case_group` доступны;
- какой `case_group` рекомендован для следующего шага;
- почему пакет пока готов только к review/proof, а не к расчёту.

Пользователь не видит:

- raw customer filenames, если они могут содержать PII;
- private local paths;
- account numbers;
- passport/ID data;
- addresses, phones, emails;
- full financial operation rows;
- secrets, keys or environment values.

## 5. Progress And Status States

Минимальные статусы:

| Status | User-visible meaning |
| --- | --- |
| `queued` | Нормализация поставлена в очередь. |
| `reading_files` | Проверяю доступ к загруженным файлам. |
| `profiling_documents` | Определяю типы файлов и техническую читаемость. |
| `building_slices` | Готовлю приватные text/table slices для следующего гейта. |
| `classifying_documents` | Назначаю taxonomy candidates. |
| `checking_blockers` | Проверяю ZIP/raster/unsupported/review blockers. |
| `reporting` | Формирую safe report для чата. |
| `completed` | Gate 1 завершён. |
| `completed_with_blockers` | Gate 1 завершён, но есть blockers для review. |
| `failed_safe` | Gate 1 остановлен без публикации небезопасных данных. |

## 6. Example Chat Transcript

```text
User:
Нормализуй документы клиента

Assistant/tool:
Запускаю Gate 1 normalization.
Проверяю загруженные файлы, техническую читаемость и безопасные document_id.

Assistant:
Gate 1 normalization completed_with_blockers.

Найдено 63 файла.

Распознанные контейнеры:
- PDF: 31
- CSV: 2
- XLSX: 2
- TXT/HTML: 4
- ZIP: 24

Предварительная классификация:
- 7 брокерских отчётов
- 8 таблиц операций
- 7 отчётов по дивидендам
- 2 отчёта по комиссиям
- 5 расчётных/output artifacts
- 2 calculation templates
- 32 требуют review или уточнения

Blockers:
- 24 ZIP требуют unpack/review policy
- 4 raster PDF требуют OCR/review
- unknown_or_needs_review документы не пойдут в source-fact extraction без review

Доступные case_group:
- case_group_001: needs_review
- case_group_002: needs_review, лучший кандидат для следующего proof slice
- case_group_003: needs_review
- case_group_004: partial
- case_group_005: needs_review
- case_group_006: needs_review

Рекомендуемый следующий шаг:
выбрать case_group_002 и запустить "Извлечь факты из выбранного кейса" только после подтверждения review scope.

Важно:
Gate 1 не выполнял налоговый расчёт, не создавал декларацию, не генерировал XLS/XLSX и не извлекал source facts через LLM.
```

The transcript uses safe aggregate counts and safe ids only.

## 7. Trigger Options

| Trigger | UX role | Fit | Notes |
| --- | --- | --- | --- |
| Slash prompt | Fallback command | Good fallback | Easy to document; weak if it cannot access file ids directly. |
| Action button | Preferred explicit UX | Strong if file refs are available | Best user affordance for "Normalize Documents". |
| Tool call | Good model-mediated path | Strong with admin policy | Workspace Model can call a normalizer tool after user intent is clear. |
| Workspace Model instruction | Safety and routing layer | Required | Defines boundaries and prevents tax/extraction overreach. |
| OpenAPI Tool Server call | Backend helper boundary | Strong | Best when parser dependencies live outside OpenWebUI image. |

Recommended route for proof:

```text
Action button or Tool call
-> OpenAPI Tool Server/helper if needed
-> same-chat safe report
```

## 8. Case Group Selection UX

After normalization, the chat report should show case groups as safe choices:

```text
Выберите case_group для следующего гейта:

case_group_001 - needs_review
case_group_002 - needs_review, recommended proof candidate
case_group_003 - needs_review
case_group_004 - partial
case_group_005 - needs_review
case_group_006 - needs_review
```

Selection must use `case_group_id`, not raw filenames or raw account labels.

The next user action can be:

```text
Извлечь факты из выбранного кейса: case_group_002
```

This starts the next gate, not Gate 1.

## 9. Error And Blocker UX

Gate 1 should fail safe.

Examples:

| Condition | Chat-visible response |
| --- | --- |
| Action cannot see file ids | "Не удалось получить refs загруженных файлов. Нужен другой trigger path." |
| File bytes unavailable | "Файлы видны в чате, но original bytes недоступны normalizer under approved boundary." |
| Parser fails | "Документ добавлен в blockers как parser_failed." |
| Raster PDF | "Документ требует OCR/review; source-fact extraction blocked until review." |
| ZIP archive | "ZIP requires explicit unpack/review policy." |
| Privacy violation detected | "Report generation stopped because safe-output rules failed." |

No failure response should print private paths, raw filenames or raw extracted rows.

## 10. Acceptance UX Signals

UX is acceptable when:

- user starts and finishes Gate 1 inside OpenWebUI;
- trigger is explicit;
- progress/status is visible enough for a long package;
- safe report appears in the same chat;
- report shows counts, document roles, blockers and case groups;
- report clearly says Gate 1 did not calculate tax or generate declaration/XLSX;
- next action is a selected `case_group_id`;
- no separate customer-facing UI is required.

## 11. Status

```text
GATE1_UX_FLOW_READY
OPENWEBUI_NATIVE_UX_RECOMMENDED
ACTION_OR_TOOL_TRIGGER_RECOMMENDED
SLASH_PROMPT_FALLBACK_ACCEPTED
SEPARATE_USER_FACING_SIDECAR_UI_REJECTED
```
