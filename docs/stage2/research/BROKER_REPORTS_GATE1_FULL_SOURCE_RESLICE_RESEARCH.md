# Broker Reports Gate 1 full-source reslice research

Дата: 2026-07-10
Статус: implemented and proof-backed, full case package remains partial

## Вывод

Gate 1 preview slices нельзя использовать как доказательство полного покрытия. Для Gate 2 добавлены отдельные private artifacts:

- `private_normalized_source_payload_v0` — нормализованный payload одного parser logical unit;
- `private_normalized_source_unit_v0` — resolver-gated extraction unit с refs, checksum и полным учётом объявленного диапазона;
- старые `private_normalized_table_slice_v0` и `private_normalized_text_slice_v0` остаются preview/backward-compatible artifacts.

Gate 2 теперь выбирает full-source unit при наличии. Legacy preview допускается только как bounded proof fallback и всегда даёт `limited_primary_expansion_ready=false`.

## Где возникала старая усечённость

| Формат | Старый preview bound | Характер ограничения | Новый статус |
|---|---:|---|---|
| CSV | первые 5 строк | preview-only; stdlib CSV уже читал все строки | complete в пределах declared budgets |
| HTML table | первые 10 строк | preview-only; старый extractor смешивал строки нескольких таблиц | отдельный logical unit на таблицу, complete в budget |
| TXT/HTML text | первые 20 строк и 2000 символов | preview-only | complete plain text / outside-table HTML text в budget |
| XLSX | первые 5 строк × 5 колонок видимого sheet | preview-only для простого sheet; formulas, oversized members и неполная структура — реальные ограничения | complete только non-formula resolved sheets в budget; иначе partial/blocked |
| PDF text | первые 2000 символов | preview плюс реальный heuristic parser cap/неполнота операторов и stream decoding | explicit partial; full-source unit не создаётся |
| DOCX text | первые 20 paragraphs / 2000 символов | preview плюс неполное структурное покрытие tables/headers/auxiliary parts | explicit partial; full-source unit не создаётся |

OCR/VLM не добавлялся.

## Контрактные границы

### Preview slice

Небольшая private проекция для profiling, taxonomy и backward compatibility. `truncated=true` означает, что она не является whole-source authority.

### Full-source normalized payload

Private parser output для одного logical unit. Содержит parser/source/payload checksum refs, normalized projection, inventories, source-value index, coverage index и `parser_completeness_status`. Если budget превышен, projection не обрезается молча: payload становится `partial`, а materialization помечается `omitted_budget_exceeded`.

### Extraction source unit

Resolver-gated unit, построенный только из `complete` payload. Содержит row/cell/text/source-value provenance. `source_slice_truncated=false` относится к declared logical range; `parent_remainder_status=not_applicable_parent_complete` запрещает старую ложную неопределённость.

### Derived source unit и Gate 2 package

Segmentation детерминированно делит refs полного parent unit. Derived unit не mint-ит новые source-value refs и содержит narrowed private projection. Domain package получает только выбранные refs/values и issue context; весь документ модели не отправляется.

## ArtifactStore и retention

Оба новых artifact type сохраняются как:

- visibility: `private_case`;
- backend: `project_artifact_payload`;
- access: `requires_gate2_resolver=true`;
- retention/purge: та же policy и cascade, что у других private case artifacts;
- Knowledge/RAG/vector backend: запрещён.

Chat-visible report получает только counts/statuses. Raw rows, text, filenames, file ids и private paths туда не попадают.

## Provenance и coverage

Existing `NormalizedSliceProvenanceFactory` остаётся единственной authority для row/cell/text/source-value refs. Новый full-source factory подаёт ему полный logical projection и добавляет parent payload/unit checksum refs.

Validator сохраняет прежние проверки:

- recomputation refs;
- source-value path и checksum reproduction;
- selected/accounted equality;
- unique refs;
- issue carry-forward;
- strict private resolution.

В ходе real proof устранены два performance defect без ослабления checks:

1. per-ref lookup был O(N²); теперь validator строит один index и выполняет те же path/checksum проверки за O(N);
2. segmentation deep-copy полного parent package на каждый derived cluster заменён на narrow-copy только нужной проекции и малых metadata.

## Форматы: текущая матрица

| Формат | Full payload | Complete unit | Expansion authority |
|---|---|---|---|
| CSV | да | да, если ≤ 10 000 rows и ≤ 100 000 cells на logical unit | да |
| TXT | да | да, если ≤ 200 000 chars | да |
| HTML | да, outside-table text + отдельные tables | да в budget | да |
| XLSX | да | только resolved non-formula sheet в member/unit budgets | условно |
| PDF | partial capability record | нет | нет |
| DOCX | partial body projection | нет | нет |
| ZIP/image/XLS | нет | нет | нет |

## Backward compatibility

Legacy ArtifactStore records не изменяются. Gate 2:

1. ищет `private_normalized_source_unit_v0` в том же resolver scope;
2. если complete units есть, использует только их;
3. иначе читает legacy slices и явно ставит `legacy_bounded_preview_fallback`;
4. legacy fallback никогда не делает limited primary expansion ready.

## Proof

### Synthetic

Synthetic CSV: 13 rows против старого preview 5. Доказано 13/13 coverage, стабильные row/source-value refs, ArtifactStore private persistence, resolver preference и segmentation без pending parent remainder. Full suite: 122/122.

### case_group_002 selected source

Controlled `process=false` re-intake одного hash-verified primary CSV:

- case: `customer_case_group_002_process_false_gate1_20260710174758`;
- full payloads/units: 1/1;
- legacy truncated preview: 1;
- complete unit selected refs: 1342/1342;
- derived units: 344; unaccounted/duplicate refs: 0/0;
- complete `position_snapshot` targets: 14;
- upload cleanup: 1/1;
- document/Knowledge/vector deltas: 0/0/0.

Одна real typed vertical дала 1 validator-passed `position_snapshot`, complete stitch, coverage 1/1, validation errors 0, parent truncation 0, parent remainder `not_applicable_parent_complete`.

### Full 16-document package

Пакет содержит 2 CSV, 4 HTML, 2 XLSX и 8 PDF. Два live 300-second attempts и controlled local package run показали, что whole-package re-slice не укладывается в текущий operational budget; PDF всё равно остаётся partial. Поэтому whole-case status — `GATE1_FULL_SOURCE_RESLICE_PARTIAL`.

## Решение об expansion

Безопасна только limited primary expansion для выбранного complete CSV document: complete unit доказан, pending parent remainder отсутствует, typed vertical passed, source-ready reconciliation passed, issue refs не потеряны (для выбранного документа их 0).

Full primary expansion по всем 16 документам не запускалась и не разрешена этим proof. Следующий инженерный срез — streaming/chunked full-source units и performance proof для whole package, отдельно от OCR/PDF work.

## Статусы

- `GATE1_FULL_SOURCE_RESLICE_RESEARCH_READY`
- `GATE1_FULL_SOURCE_PROVENANCE_READY`
- `GATE1_FULL_SOURCE_SYNTHETIC_PASSED`
- `CASE_GROUP_002_TYPED_VERTICAL_FROM_COMPLETE_SOURCE_UNIT_PASSED`
- `CASE_GROUP_002_VECTOR_GUARD_PASSED`
- `CASE_GROUP_002_KNOWLEDGE_GUARD_PASSED`
- `READY_FOR_CASE_GROUP_002_GATE2_LIMITED_PRIMARY_EXPANSION`
- `GATE1_FULL_SOURCE_RESLICE_PARTIAL`
- blocker: `whole_case_package_not_within_current_runtime_budget_and_pdf_parser_completeness_partial`
