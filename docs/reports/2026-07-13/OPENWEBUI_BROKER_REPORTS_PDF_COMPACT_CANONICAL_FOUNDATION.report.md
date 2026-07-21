# Broker Reports: compact canonical PDF foundation

Дата: 2026-07-13

Режим: Implementation Goal 1 of 4, dual-write shadow
Результат: готово для Goal 2, без переключения production Gate 2

## Итог

Реализован компактный канонический PDF-контур рядом с текущим forensic-контуром. Старый путь остаётся авторитетным. Новый путь включается только флагом `pdf_compact_canonical_dual_write`; его default — `false`.

На controlled six-page PDF доказано:

- представлены все 14 table decisions ровно по одному разу;
- сохранены 9 accepted и 5 explicit blocked решений;
- 96 строк, 572 current cells и все явные empty cells сохранены;
- 1 045/1 045 accepted source refs учтены, 0 потеряно, 0 unaccounted;
- compact-to-v0 mapping сравнил 14/14 решений, а 9 accepted-проекций принял существующий `TableProjectionValidator` без изменения валидатора;
- compact JSON — 538 781 B, gzip — 150 666 B;
- steady-state envelope original + compact + acceptance core — 721 166 B, ниже инженерной цели 750 000 B;
- acceptance — `accepted_with_explicit_blocked_tables`, `approval_required=false`;
- старые артефакты не удалены, Gate 2 selection не изменён, Knowledge/RAG/vector/OCR/VLM/provider PDF transport не использовались.

## Реализованные контракты

1. `broker_reports_pdf_compact_canonical_document_v1`
   - identity исходного PDF и реальный `source_file_ref_v0` artifact ref;
   - parser/layout manifest и config/policy refs;
   - page manifest без full glyph/char/word/vector universe;
   - один table decision на каждый detected table;
   - packed rows/cells/selected evidence, header model, spans и explicit empty-cell flags;
   - deterministic `source_value_ref -> evidence ordinal` index;
   - table/source coverage checksums и no-semantic/no-RAG guards.

2. `broker_reports_pdf_normalization_acceptance_v1`
   - восемь независимых gates;
   - JSON/gzip/component byte accounting;
   - permanent/temporary/migration roles;
   - решения `accepted_complete`, `accepted_with_explicit_blocked_tables`, `human_review_required`, `blocked`.

3. `broker_reports_pdf_compact_build_failure_v1`
   - typed shadow failure;
   - `current_normalization_available=true`;
   - `partial_compact_accepted=false`;
   - Gate 2 selection остаётся прежним.

Канонические описания:

- `docs/stage2/contracts/BROKER_REPORTS_PDF_COMPACT_CANONICAL_DOCUMENT.v1.md`;
- `docs/stage2/contracts/BROKER_REPORTS_PDF_NORMALIZATION_ACCEPTANCE.v1.md`;
- `docs/stage2/implementation/BROKER_REPORTS_PDF_COMPACT_DUAL_WRITE_MIGRATION.v1.md`.

## Изменённые модули

| Модуль | Назначение |
|---|---|
| `broker_reports_gate1/pdf_compact_canonical.py` | Factory, deterministic builder, strict validator, packed evidence/cell schema, private source resolver. |
| `broker_reports_gate1/pdf_normalization_acceptance.py` | Acceptance builder/validator, восемь gates, storage/lifecycle accounting. |
| `broker_reports_gate1/pdf_compact_gate2_adapter.py` | Локальный research mapping в v0 и differential validator; production selection не использует его. |
| `broker_reports_gate1/gate2_handoff.py` | Dual-write после сохранения текущих artifacts и получения реального original artifact ref; typed failure policy. |
| `broker_reports_gate1/artifact_models.py` | Три новых artifact types. |
| `openwebui_actions/broker_reports_gate1_pipe.py` | Admin Valve с default `false`. |
| `scripts/build_openwebui_pipe_bundle.py` | Новые closed-world modules; `--target gate1` позволяет не перегенерировать Gate 2 bundles. |
| `openwebui_actions/broker_reports_gate1_pipe_bundled.py` | Обновлённый самостоятельный Gate 1 runtime artifact. |
| `scripts/local_pdf_compact_canonical_proof.py` | Factory-routed controlled proof без raw values/paths/filenames в safe evidence. |

## Dual-write и граница Gate 2

Фактический порядок при включённом флаге:

```text
Gate1Normalizer
-> current full payload/source units/table projections
-> current ArtifactStore persistence
-> real source_file_ref_v0 artifact id
-> compact factory + validation + deterministic rerun
-> local v0 mapping validation
-> acceptance validation
-> compact + acceptance persistence
```

`gate2_handoff_v0` не содержит compact/acceptance keys или refs. Compact не добавляется в `private_slice_refs`, acceptance не добавляется в `safe_refs`. Оба Gate 2 bundled-файла остались без diff.

Feature-off и non-PDF regression доказали отсутствие shadow artifacts. При намеренно удалённом source payload persistence записала typed failure, сохранила текущую table projection и не сохранила partial compact.

## Controlled PDF: storage

| Компонент | JSON bytes | gzip bytes | Роль в Goal 1 |
|---|---:|---:|---|
| Original PDF | 176 458 | не применяется | permanent source evidence |
| Visible text UTF-8 | 29 743 | не применяется | измерение, не отдельная копия в compact |
| Full forensic payload | 22 185 588 | 3 596 457 | temporary working/debug state |
| Current normalized source units | 2 121 984 | 448 741 | temporary working/debug state |
| Current table projections | 1 771 052 | 324 558 | authoritative/permanent during migration |
| Compact canonical | 538 781 | 150 666 | intended permanent canonical artifact |
| Acceptance core | 5 927 | не применяется | permanent decision metadata |

Итоги:

- intended permanent total: 721 166 B;
- current temporary working-state total: 24 307 572 B;
- migration-retained total без временного forensic state: 2 486 291 B;
- compact/full JSON ratio: 0,024285;
- сокращение против full JSON: 97,57%;
- permanent/original ratio: 4,086899;
- permanent/visible-text ratio: 24,246579;
- duplicate-visible-text ratio: 0,0 на измеряемом page-text уровне.

Full 22 MB не считается permanent artifact.

Первый controlled shadow run корректно остановился с `pdf_compact_cell_grid_incomplete`: три current accepted projections являются sparse (не все позиции materialized). Контракт был исправлен без выдумывания empty cells или source refs: он сохраняет все current positions и все explicit current empty cells, проверяет уникальность и границы, но не создаёт отсутствующие cells. После этого storage gate выявил 1,58 MB дублирования refs; packed rows/cells/evidence и checksum-only coverage снизили compact до 538 781 B без потери required evidence.

## Differential equivalence

| Проверка | Результат |
|---|---|
| Table identities | 14/14, passed |
| Accepted/blocked statuses | 9/5, passed |
| Accepted rows/columns/cells | passed |
| Headers and repeated/multi-row model | passed |
| Explicit empty-cell flags | passed |
| Accepted source refs | 1 045 registered, 1 045 accounted, 0 unaccounted |
| Duplicate source ownership | 0; builder fails closed if introduced |
| Blocked tables | 5 explicit, rows/cells absent |
| Existing v0 validator | 9/9 mapped accepted projections passed |
| Production Gate 2 input | unchanged |

Safe proof artifact находится в ignored private evidence root; путь не публикуется. В репозиторий не записаны raw customer values, private paths или raw filenames.

## Acceptance gates

| Gate | Статус |
|---|---|
| Structural correctness | passed |
| Provenance correctness | passed |
| Source-ref accounting | passed |
| Storage proportionality | passed |
| Compact reproducibility | passed |
| LLM projection readiness | passed через локальный v0 mapping proof |
| Artifact classification | passed |
| Cleanup readiness | `deferred_dual_write_safety`; классификация готова, cleanup выключен |

Final decision: `accepted_with_explicit_blocked_tables`. Пять blocked tables не скрыты.

## Тесты и проверки

- Focused compact + bundled + PDF/table + ArtifactStore suite: `63 passed`.
- Full service suite: `277 passed`, 5 сторонних SWIG deprecation warnings.
- Controlled proof script: exit 0, `proof_status=passed`.
- `git diff --check`: passed; только штатные Windows line-ending warnings.
- `py_compile` для новых модулей, persistence, proof и bundle builder: passed.
- Closed-world bundle test загрузил Gate 1 bundle без repo package import и выполнил dual-write PDF run.

Тесты покрывают exact schema, unknown/forbidden fields, ordering/checksum/idempotency, accepted/blocked/sparse/empty/repeated-header cases, missing/duplicate/inconsistent refs и grid positions, differential mapping, storage/compression/roles, feature-off, non-PDF, typed failure, no Knowledge/RAG/vector и неизменный Gate 2 handoff.

## Repository status

Ветка: `main`, commit parity с `origin/main`; worktree dirty, commit/push не запрашивались и не выполнялись.

В worktree до этого Goal уже находились отдельные незакоммиченные direct-PDF experiment files и два отчёта от 2026-07-13. Они не удалялись и не включались в архитектуру compact foundation. Goal 1 добавляет новые модули, тесты, Gate 1 bundle и документы, перечисленные выше.

## Оставшиеся границы перед Goal 2

- production Gate 2 всё ещё читает только current table projections;
- compact-to-v0 adapter остаётся локальным proof path;
- feature flag остаётся выключенным по умолчанию;
- current forensic payload и source units физически не удаляются;
- cleanup/TTL activation относится к Goal 4;
- raster/crop, VLM/provider calls, direct-PDF transport и hybrid arbitration не реализованы и требуют отдельного Goal 2;
- никаких выводов о бизнес-семантике, налоговой корректности или declaration readiness этот Goal не делает.

## Final statuses

```text
BROKER_REPORTS_PDF_COMPACT_CANONICAL_CONTRACT_READY
BROKER_REPORTS_PDF_NORMALIZATION_ACCEPTANCE_CONTRACT_READY
BROKER_REPORTS_PDF_COMPACT_CANONICAL_BUILDER_READY
BROKER_REPORTS_PDF_COMPACT_DUAL_WRITE_READY
BROKER_REPORTS_PDF_TABLE_DECISION_EQUIVALENCE_PROVEN
BROKER_REPORTS_PDF_SOURCE_REF_EQUIVALENCE_PROVEN
BROKER_REPORTS_PDF_COMPACT_STORAGE_ACCOUNTING_PROVEN
BROKER_REPORTS_PDF_COMPACT_GATE2_MAPPING_PREPARED
BROKER_REPORTS_PDF_COMPACT_FOUNDATION_TESTS_PASSED
BROKER_REPORTS_PDF_COMPACT_FOUNDATION_READY_FOR_GOAL_2
```
