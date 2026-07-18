# Broker Reports Global Gate 1 — Multi-Format Document Memory Closure v1

Дата: 2026-07-18

Репозиторий: `Kwentin3/corp-openweb-ui`

Runtime-ревизия: `47255bf`

Proof/docs-ревизия перед этим отчётом: `79e2da9`

Итог: `NOT_CLOSED`

## 1. Вывод простыми словами

Техническое ядро Gate 1 собрано в одну систему. CSV, статический HTML и PDF с
полноценным текстовым слоем теперь проходят через общий профиль, сохраняются
как связная память документа и передаются в Gate 2 через один публичный
контракт. Gate 2 больше не должен знать, каким парсером был прочитан исходный
файл.

Код, тесты, синтетический mixed-format proof внутри stage-контейнера и
repo/live parity прошли. Но продуктовый Gate 1 пока нельзя честно назвать
закрытым: доступный реальный stage proof содержит только CSV. Исходные байты
разрешённых HTML и PDF из реестра сейчас недоступны, поэтому не выполнены
обязательный реальный смешанный прогон и операторское сравнение нормализованной
памяти с оригиналами.

Это не скрытая ошибка реализации CSV/HTML/PDF. Это незакрытый обязательный
контур доказательства и приёмки.

## 2. Зафиксированный профиль v1

Профиль: `broker_reports_gate1_source_evidence_profile_v1`.

| Формат | Поддержанный вариант | Что создаёт Gate 1 | Статус реализации |
| --- | --- | --- | --- |
| CSV | строгий CSV v1; UTF-8/BOM/CP1251; `,`, `;`, tab, `|`; документ в пределах versioned limits | private whole-source payload, row-window units, единая validated table projection | реализовано и протестировано |
| HTML | статический текст и ненестированные таблицы; UTF-8/BOM/CP1251 | ordered text/table payloads и units, единая validated table projection | реализовано и протестировано; scripts/media/nested tables дают явный review |
| PDF | text-only PDF с пригодным text layer и полным layout/page accounting | page/text payload, layout/line/table-candidate units, validated common table projection либо review с text fallback | реализовано и протестировано |

`complete` выдаётся только после проверки полного declared scope и accounting.
`review_required` разрешён только когда сама память и fallback lineage полны, но
структура, например геометрия PDF-таблицы, остаётся неоднозначной. `partial`,
`blocked`, `unsupported` и `unreadable` не допускаются в Gate 2 memory.

Полные лимиты и правила зафиксированы в
`BROKER_REPORTS_GATE1_SUPPORTED_PILOT_PROFILE.v1.md` и продублированы в runtime
profile authority `document_memory.py`.

## 3. Что явно не входит в v1

| Класс | Причина исключения | Безопасное поведение |
| --- | --- | --- |
| XLSX | Два workbook из approved pool имеют по 20 листов и формулы, но реестр относит их к methodology/output, а не source evidence. Formula/cached-value/merge/object memory не закрыта. | явный `unsupported`, Gate 2 blocked |
| ZIP | 24 архива имеют conditional status; их members не promoted в source evidence | только inventory/review, не document memory |
| image-only и mixed-image PDF | canonical OCR/VL memory не закрыта | `partial`/review, но не `complete` |
| DOCX | текущая body-only projection частична | не принимается |
| TXT, XML, XLS | обязательного source-evidence класса в approved pool нет | `unsupported` |

Если любой из этих классов станет обязательным для пилота, потребуется новая
версия профиля и отдельное доказательство полного scope/accounting. Текущий v1
не маскирует такое расширение общей формулировкой «поддерживаем документы».

## 4. Единая память документа

Новый safe root — `broker_reports_gate1_document_memory_manifest_v1`.

```text
case
  -> source file
     -> logical document
        -> private normalized payload refs
        -> private source-unit refs
        -> private normalized-table refs
        -> scope/counts
        -> issue refs
        -> completeness/accounting
```

Для v1 действует правило «один физический файл — один логический документ».
Root хранит только безопасные refs, hashes, counts, scope, статусы и issue ids.
Исходные и нормализованные клиентские значения остаются в `private_case`.

Validator пересобирает ожидаемый root из maintained package graph и проверяет:

- уникальность source/logical/artifact refs;
- parent-связи payload -> unit;
- совпадение declared и persisted payload/unit counts;
- отсутствие unaccounted и duplicate refs;
- полноту native CSV/HTML table projections;
- rows/cells/text-character accounting;
- PDF page accounting;
- integrity hash и отсутствие private fields в safe root.

При любом accounting-разрыве документ не может остаться `complete` или
`review_required`: он понижается до `partial`, а Gate 2 блокируется.

## 5. Gate 1 -> Gate 2

DCP содержит `document_memory_boundary`. Gate 2 получает DCP ref и access
context, разрешает root через `ArtifactResolver`, проверяет его через
`gate1_public_contracts.py` и строит формат-независимые bounded packages.

Gate 2 не импортирует CSV/HTML/PDF parsers, layout modules, spreadsheet
internals или конкретный SQLite adapter. Архитектурный тест считает
`document_memory.py` приватной реализацией Gate 1 и запрещает обход публичной
границы.

Gate 2 execution не меняет ранее созданные Gate 1 artifacts. Store остаётся
append-only; wrong user/case/chat/workspace/run/lifecycle context закрывается с
ошибкой.

## 6. Автоматическое доказательство

### Локально

Полный набор сервиса: `898 passed`, 5 dependency deprecation warnings, ошибок
нет.

Смешанный factory proof использовал безопасные синтетические CSV + HTML + PDF
в одном case:

| Проверка | Результат |
| --- | ---: |
| source files / logical documents | 3 / 3 |
| normalized artifacts | 12 |
| accepted terminal states | `complete: 3` |
| Gate 2 packages | 5 |
| duplicate refs | 0 |
| zero silent loss | passed for all accepted documents |
| Knowledge/RAG/vector records | 0 |
| wrong-context denial | `artifact_access_denied` |
| Gate 1 artifacts after Gate 2 | unchanged |
| source-delete private cascade | passed |
| case-purge denial | `artifact_purged` |

### В stage-контейнере

`live_gate1_document_memory_v1_synthetic_proof.py` выполнил тот же bundled
factory path внутри контейнера `openwebui`. Результат снова `passed` со всеми
показателями выше.

Proof намеренно сохраняет честные признаки:

- `customer_documents_used=false`;
- `operator_acceptance_performed=false`;
- `product_representative_stage_proof=false`.

Поэтому этот прогон подтверждает bundle/runtime/dependency mechanics, но не
заменяет требуемую продуктовую приёмку на реальном пуле.

## 7. Repo/live delivery

Maintained update scripts поставили три Function bundles. Последующая read-only
проверка завершилась `status=passed`:

| Function | Repo/live SHA-256 |
| --- | --- |
| `broker_reports_gate1_pipe` | `7d584553ccd41f53c288e6e0b3182c267c25edb59a86bad9d9efdf1b13147cef` |
| `broker_reports_gate2_source_fact_pipe` | `1ec573b36f31ebd040c6b6ce3be23f4d5f03564a3bcedb9b2c20c5791e9d58db` |
| `broker_reports_gate2_domain_source_fact_pipe` | `8f8d02f9f956a5e4af3070bb697788a56786acfddcb334494e310d6912d7ba08` |

Managed Prompts: `12/12` совпадают. Required `fitz=1.26.5`, PDF Table Intake
valves и disabled research shadows проверены. Перед созданием отчёта
`HEAD == origin/main == 79e2da9`; последующий report commit является docs-only
и не требует повторной Function-поставки.

## 8. Почему Gate 1 всё ещё не закрыт

Approved safe registry содержит 63 позиции:

- 2 CSV;
- 4 static HTML;
- 31 PDF;
- 2 XLSX;
- 24 ZIP.

В обязательный source-evidence subset входят 24 документа: 2 CSV + 4 HTML +
18 PDF. Все 18 PDF имеют text layer, не требуют OCR по зарегистрированному
профилю и суммарно содержат 449 страниц. Это именно тот фактический контур, на
котором профиль v1 был определён.

Но private registry сейчас даёт `63` записей и `0` существующих source paths:
все `63` пути отсутствуют в текущем workspace. Safe registry намеренно не
публикует private payload paths и не может заменить исходные байты.

Сохранённый реальный stage proof
`customer_case_group_002_process_false_gate1_20260717204732` содержит только
один CSV. Он доказывает CSV vertical, но не mixed CSV + HTML + PDF document
memory. Доступного реального mixed run с новым root нет.

Следовательно, сейчас нельзя проверить на фактическом разнообразии:

- начало/середину/конец HTML и PDF;
- сохранность material table context и page/layout provenance;
- корректность review-состояний реальных PDF-таблиц;
- отсутствие необъяснённой потери во всех 24 source-evidence документах;
- операторскую пригодность памяти для дальнейшей интерпретации.

Это материально, потому что задача прямо запрещает заменять heterogeneous
representative stage proof набором изолированных synthetic fixtures.

## 9. Acceptance matrix

| Критерий | Состояние |
| --- | --- |
| Explicit versioned supported profile | passed |
| CSV/HTML/text-layer PDF implementation | passed |
| One document-memory contract family | passed |
| Cohesion and public Gate 2 handoff | passed in automated proof |
| Code isolation | passed |
| ArtifactStore/resolver/lifecycle/immutability | passed in automated proof |
| Zero silent loss | passed for synthetic declared profile; not proven on actual 24-doc subset |
| Mixed-format stage mechanics | passed synthetically inside stage container |
| Representative actual mixed-format stage proof | not performed |
| Operator acceptance | not performed |
| Repository/live Function and Prompt parity | passed |

## 10. Узкая оставшаяся работа

1. Восстановить approved private bytes для фактического пула либо создать новый
   approved stage case минимум с одним реальным CSV, одним реальным static HTML
   и одним реальным text-layer PDF с material table context. Синтетика не
   подходит для этого пункта.
2. Запустить maintained `process=false` Gate 1 path на уже поставленном bundle и
   сохранить safe aggregate evidence нового document-memory root.
3. Выполнить чек-лист
   `BROKER_REPORTS_GATE1_DOCUMENT_MEMORY_OPERATOR_ACCEPTANCE.v1.md`: сравнить
   source с resolver-доступной private memory без публикации значений.
4. Зафиксировать per-document verdict, mixed-case zero-loss, stage run/case ids
   и повторную repo/live parity. Если все документы приняты, заменить статус
   этого отчёта на closure status отдельным подтверждённым коммитом.

Новые адаптеры или изменение архитектуры для этих четырёх шагов не требуются,
если фактические документы соответствуют объявленным вариантам v1. Если
реальный файл выявит image-only/mixed-image PDF либо обязательный XLSX, это уже
не proof-only работа, а новый versioned profile slice.

## 11. Обязательный финальный статус

```text
BROKER_REPORTS_GLOBAL_GATE_1:
NOT_CLOSED

EXACT_UNSUPPORTED_REQUIRED_SOURCE_CLASS:
NO IMPLEMENTATION-UNSUPPORTED CLASS INSIDE DECLARED PROFILE V1.
THE CLOSURE-BLOCKING REQUIRED PROOF CLASSES ARE APPROVED ACTUAL STATIC HTML
AND TEXT-LAYER PDF SOURCE BYTES; THEY ARE NOT AVAILABLE IN THE CURRENT
WORKSPACE OR CURRENT REAL STAGE CASE.

EXACT_CONTRACT_OR_IMPLEMENTATION_GAP:
THE REQUIRED REPRESENTATIVE ACTUAL MIXED-FORMAT STAGE PROOF AND OPERATOR
ACCEPTANCE HAVE NOT BEEN PERFORMED. SYNTHETIC STAGE PROOF CANNOT SATISFY THIS
PRODUCT ACCEPTANCE CONDITION.

MATERIAL_EVIDENCE:
THE APPROVED SOURCE-EVIDENCE SUBSET IS 2 CSV + 4 HTML + 18 TEXT-LAYER PDF
(449 PDF PAGES). THE PRIVATE REGISTRY HAS 63 ENTRIES BUT 0 EXISTING SOURCE
PATHS. THE AVAILABLE REAL STAGE CASE CONTAINS ONLY ONE CSV.

NARROWEST_REMAINING_WORK:
RESTORE OR RE-APPROVE ACCESSIBLE ACTUAL HTML/PDF BYTES; RUN ONE MIXED
PROCESS=FALSE STAGE CASE THROUGH THE DEPLOYED GATE 1; COMPLETE THE OPERATOR
CHECKLIST; RECORD ZERO-LOSS AND REPO/LIVE PARITY EVIDENCE.
```
