# OpenWebUI Broker Reports: implementation-ready дизайн compact/hybrid PDF table pipeline

Дата: 2026-07-13

Режим: architecture research, contract design, implementation planning

Репозиторий: `corp-openweb-ui`

Production/runtime changes in this task: **none**
OpenWebUI core changes: **none**

## 1. Исполнительный вердикт

Целевая архитектура готова к реализации ограниченными срезами:

```text
process=false original PDF in private ArtifactStore
→ temporary pypdf/pdfplumber text + layout working state
→ deterministic table-region detection and coverage ledger
→ deterministic reconstruction attempt
→ versioned observable table classifier
   ├─ deterministic_simple → compact deterministic table
   ├─ hybrid_complex / hybrid_after_deterministic_block
   │  → reproducible crop + exact table-local source candidates
   │  → strict multimodal candidate binding
   │  → deterministic materialization and validation
   └─ unsupported / unresolved → explicit human-review case
→ broker_reports_pdf_compact_canonical_document_v1
→ compact-to-v0 compatibility adapter
→ existing broker_reports_normalized_table_projection_v0
→ existing Gate 2 package, segmentation, context v2, candidate binding,
  source-fact validation and deterministic stitch
→ broker_reports_pdf_normalization_acceptance_v1
→ observable delete / compressed TTL / review hold of working evidence
```

Роли путей:

- primary для простых таблиц — compact deterministic reconstruction после строгой структурной приёмки;
- primary для сложных или deterministic-blocked таблиц — raster + exact source candidates, где модель выбирает только candidate ids и структуру;
- fallback — bounded same-evidence provider attempt; DPI escalation создаёт новую evidence revision и не маскируется под retry;
- human review — при отсутствии точных candidates, несовместимых DPI/crop/structure, невалидном output после bounded attempts или неоднозначной provenance;
- raster-only, direct whole-PDF и plain-text — только challenge/audit/reviewer aids, вне authoritative acceptance path.

Главная миграционная граница: Gate 2 не реконструирует PDF и не меняет fact contracts. Новый адаптер выпускает существующий `broker_reports_normalized_table_projection_v0`; единственное необходимое изменение на стороне Gate 2 boundary — разрешить `Gate2InputReadiness` принимать validator-passed projection от compact artifact без обязательного существования полного PDF full-source unit. Все downstream validators остаются без изменений.

Accuracy baseline остаётся provisional: adaptive hybrid дал 823/831 = 99,04% exact cells, 322/325 = 99,08% numeric-like, 9/9 exact structures и 9/9 headers, но actual human sign-off отсутствует. Эти числа разрешают проектирование и shadow implementation, но не production rollout.

## 2. Scope, invariants и non-goals

Неподвижные invariants:

1. Каждый принятый non-empty cell разрешается в существующие `source_value_ref` и `word_ref`; модель не создаёт значение.
2. Empty cell — явная позиция grid, а не пропуск.
3. Все detected table refs имеют ровно одно решение: accepted deterministic, accepted hybrid, blocked, rejected/unsupported или review.
4. HTTP 2xx, valid JSON и высокая visual similarity по отдельности не означают accepted table.
5. Gate 2 получает ту же structural boundary и не получает crop, full PDF, glyph universe или provider response.
6. `semantic_table_truth_claimed=false`, `source_facts_extracted=false`, `tax_meaning_inferred=false` сохраняются.
7. Private artifacts остаются в ArtifactStore, не попадают в Knowledge/RAG/vector storage; intake остаётся `process=false`.
8. Нет silent truncation, hidden retry, hidden provider failover и validator weakening.

Non-goals:

- business-domain classification, tax calculation или final source-fact extraction в table VLM call;
- OCR для image-only PDF в первом implementation slice;
- opaque ML router;
- замена OpenWebUI core или native file pipeline;
- немедленное удаление текущих forensic artifacts до dual-write equivalence;
- production deployment в рамках этого отчёта.

## 3. Current implementation impact map

### 3.1 Текущая фактическая цепочка

- `Gate1Normalizer.normalize` создаёт `FullSourceArtifactFactory`, затем `NormalizedTableProjectionFactory` (`services/broker-reports-gate1-proof/broker_reports_gate1/normalizer.py:45`, `:80`, `:87`, `:178-204`).
- `FullSourceArtifactBuilder._build_pdf_document` запускает pypdf page-text и pdfplumber layout, после чего вкладывает char/bbox/word/line/vector/table inventories в один `private_normalized_source_payload_v0` (`full_source.py:585-726`, `:1010-1110`, `:1114-1186`).
- `PdfPlumberLayoutAdapter` владеет layout parse и candidate detection (`pdf_layout.py:92-470`); `PdfLayoutUnitBuilder` материализует word/source-value refs и PDF source units (`pdf_layout_units.py:66-1006`).
- `PdfTableCandidateProjectionBuilder` одновременно читает полный parent payload, проверяет geometry, материализует cells/private values/source index и выдаёт v0 projection (`table_projection.py:334-618`).
- `Gate2TablePackageBuilder` уже принимает validator-passed v0 projection и строит `table_row_window` без повторной table reconstruction (`table_projection.py:739-983`).
- `Gate2InputReadiness` сейчас подменяет full-source unit проекцией только если full unit существует (`gate2_input_readiness.py:449-646`). Это единственная несовместимость с удалением постоянной full geometry.
- `gate2_handoff.py` сохраняет full payload, units и projections с одной run retention policy (`gate2_handoff.py:177-330`).
- `ArtifactStore` умеет TTL expiry/purge и private JSON payload, но artifact taxonomy и lifecycle не различают permanent compact и temporary geometry/crop/provider evidence (`artifact_models.py:51-100`, `artifact_store.py:211-315`, `artifact_retention.py:8-63`).

### 3.2 Решение по компонентам

| Компонент | Текущий владелец | Решение | Точное изменение |
|---|---|---|---|
| PDF identity/checksum и page text | `pdf_text_layer.py`, `PdfTextLayerParserFactory`, `PypdfParserAdapter` | keep unchanged | Сохраняются parser/version/config refs, page checksums, text-layer readiness и no-OCR fail-closed semantics. |
| pdfplumber layout extraction | `pdf_layout.py`, `PdfPlumberLayoutAdapter` | revise persistence; parser stays | Вывод становится `broker_reports_pdf_working_geometry_v1`: temporary/private, reproducible, cleanup-owned; больше не permanent canonical payload. |
| Table candidate detection | `PdfPlumberLayoutAdapter._find_table_candidates`, `pdf_layout_units.py` | revise/wrap | Алгоритм v0 сохраняется первым detector; новый compact detection ledger хранит только candidate/table/page/bbox/strategy/coverage decision, full hypotheses — debug TTL. |
| Word/source-value minting | `PdfLayoutUnitBuilder`, `resolve_pdf_layout_unit_source_value` | revise | Identity/checksum policy сохраняется; новый evidence index materializes только table-local selected spans с reversible `source_value_ref`/`word_ref` mapping. |
| Deterministic table reconstruction | `PdfTableCandidateProjectionBuilder` | wrap, then deprecate monolith | Выделить attempt/result/acceptance; builder больше не решает одновременно reconstruction, persistence и Gate 2 projection. Старый path остаётся dual-write oracle до Phase 6. |
| PDF table classifier | отсутствует | new component required | `pdf_table_classification.py`; только deterministic observable signals, versioned policy, no business semantics. |
| Raster/crop rendering | только research harness `local_pdf_table_approach_experiment.py:554-581` | new production component required | `pdf_table_raster.py`: renderer pin, coordinate transform, rotation, padding, DPI, dimension/byte checks, crop hash. |
| Hybrid evidence package | только experiment `_word_candidates`/`_run_hybrid_call` (`:584-625`, `:713-777`) | new component required | `pdf_hybrid_evidence.py`; no parallel tokenizer; selected production refs only; compact model view + private reversible dictionary. |
| Provider boundary | research direct OpenWebUI call; Gate 2 adapters are business-runtime-owned | new component required | `pdf_hybrid_provider.py`; own factory, capability profile, strict schema projection and attempt ledger. Gate 2 request builder/client are unchanged and are not called by table reconstruction. |
| Hybrid materialization/validation | experiment-local | new component required | `pdf_hybrid_materialization.py`, `pdf_table_validation.py`; resolve ids, build full grid, fail closed, never accept free values. |
| Normalized source payload | `private_normalized_source_payload_v0`, `full_source.py` | PDF: temporary/debug then deprecate as permanent; non-PDF unchanged | During dual-write keep current v0. Phase 6 splits working geometry from permanent compact doc. No in-place mutation of historical artifacts. |
| Normalized source units | `private_normalized_source_unit_v0`, `pdf_layout_units.py` | PDF candidates temporary; non-PDF unchanged | PDF layout units feed classifier/materializer while working state exists. Compact artifact, not full unit universe, becomes permanent PDF source authority. |
| Compact canonical PDF artifact | отсутствует; experiment only | new component required | `pdf_compact_canonical.py`, schema v1, one permanent document with all table decisions and compact source evidence. |
| Normalized table projection | `table_projection.py`, schema v0 | keep public contract; add compatibility adapter | `pdf_compact_gate2_adapter.py` maps accepted compact table to existing v0 fields and runs unchanged `TableProjectionValidator`. |
| Source-value index | payload/unit/projection `source_value_index` | keep identity; revise storage projection | Compact doc stores exact selected entries and checksums; adapter reproduces current projection index/private paths without minting new source authority. |
| Gate 2 input readiness | `gate2_input_readiness.py` | narrow revision | Feature-flagged direct selection of validated compact-derived v0 projections when no PDF full-source units remain; require compact doc checksum/coverage ledger. |
| Gate 2 table/package builder | `Gate2TablePackageFactory`, `Gate2TablePackageBuilder` | keep unchanged | Continues emitting `table_row_window`, explicit rows/cells/headers/source refs and no-fact coverage. |
| Gate 2 segmentation | `gate2_source_unit_segmentation.py` | keep unchanged | Existing selected-row partition and narrowed values remain authoritative. |
| Gate 2 LLM-friendly context v2 | `gate2_llm_context.py` | keep unchanged | Existing 48k chars / 64 candidate context budget applies after table reconstruction, not to hybrid table package. |
| Gate 2 candidate binding | `gate2_candidate_binding.py`, `gate2_candidate_binding_runtime.py` | keep unchanged | Business candidate discovery and binding happen later from normalized table cells. Do not reuse for visual table placement. |
| Gate 2 fact validator/stitcher | `gate2_source_fact_validation.py`, `gate2_source_fact_stitching.py` | keep unchanged | Existing allowed refs, invented-value checks, exact coverage ownership and deterministic stitch remain final authority. |
| ArtifactStore persistence | `artifact_models.py`, `artifact_store.py`, `gate2_handoff.py` | revise behind existing factory | Add v1 artifact types, per-artifact lifecycle class, binary/private payload support for crops, checksum/size metrics, cleanup receipts. No direct filesystem access from pipes. |
| Lifecycle/cleanup | `artifact_lifecycle.py`, `artifact_retention.py` | revise | Add role-specific terminal disposition and cleanup job/receipt; run retention no longer forces geometry and compact result to share retention. |
| Existing proof scripts | layout/text/table/direct/live scripts under `scripts/` | keep as regression/challenge; deprecate direct as authority | Add contract, dual-write, cleanup, hybrid shadow and Gate 2 compatibility proofs; direct PDF scripts never enter acceptance path. |
| OpenWebUI bundled actions | `openwebui_actions/*_bundled.py` | revise only in runtime phases | Regenerate from source after implementation; prove bundle SHA/live parity. No hand-edit and no OpenWebUI core patch. |

## 4. Contract conventions

Все десять новых contracts используют:

- exact `schema_version`; version mismatch is terminal, never best-effort;
- deterministic opaque ids from stable canonical identity inputs, not raw filename;
- SHA-256 for raw bytes and canonical JSON; hash policy/version is explicit;
- ordered arrays where source order matters; uniqueness and coverage checked independently;
- `private_case` + `project_artifact_payload`; safe metadata contains only refs/counts/status/reason codes;
- `created_at` is audit metadata and не входит в reproducibility hash;
- issue/reason codes are typed lowercase identifiers;
- unknown enum or missing required field means blocked artifact;
- every artifact includes `normalization_run_id`, `document_ref`, `source_checksum_ref`, `contract_config_hash` where applicable.

## 5. Contract set

### 5.1 `broker_reports_pdf_normalization_acceptance_v1`

Purpose: final independent decision for one PDF normalization run. It does not overwrite per-table validation.

| Field | Type | Requirement/invariant |
|---|---|---|
| `schema_version` | literal | `broker_reports_pdf_normalization_acceptance_v1` |
| `acceptance_id` | string | Stable over document checksum + canonical/config hashes + ordered table decisions. |
| `normalization_run_id`, `document_ref`, `pdf_artifact_ref` | string | Same private scope; original must resolve and not be expired. |
| `source_checksum_sha256`, `source_checksum_ref`, `source_bytes` | string/string/int | Recomputed checksum equals original; bytes > 0. |
| `parser_manifest` | object | pypdf/pdfplumber/renderer versions, policy ids, config hashes, platform-independent canonicalization version. |
| `page_readiness` | object | `pages_total`, text/layout complete/partial/blocked counts, rotation decisions, no-OCR status. |
| `table_accounting` | object | detected/accepted deterministic/accepted hybrid/blocked/review/unsupported counts and exact ordered table refs. Sum of terminal decisions equals detected total. |
| `source_ref_accounting` | object | registered/accounted/duplicate/unaccounted refs and `all_registered_refs_accounted`; accepted requires no duplicate/unaccounted accepted refs. |
| `artifact_bytes` | object | original, compact permanent, temporary geometry, crops, provider raw, debug compressed, total permanent/temporary. |
| `retention` | object | artifact ids, disposition, TTL/hold reason, expires/deleted timestamps and cleanup receipt refs. |
| `validation_gates` | object | separate `output_contract`, `structure`, `provenance`, `storage`, `reproducibility`, `cleanup`; each has status/reasons/evidence refs. |
| `reproducibility` | object | rerun id, same-input/config hashes, compared artifact hashes, result `exact|equivalent|different|not_run`. |
| `cleanup_terminal_state` | enum | `completed`, `pending_ttl`, `retained_for_review`, `incident_or_legal_hold`, `failed`. |
| `final_decision` | enum | `accepted_complete`, `accepted_with_explicit_blocked_tables`, `blocked`, `human_review_required`. |
| `reason_codes`, `issue_refs` | string[] | Sorted unique; no free-form decision repair. |

Acceptance rule: `accepted_complete` requires all detected tables terminal-accepted, every independent gate passed and cleanup `completed|pending_ttl` with a scheduled observable expiry. `accepted_with_explicit_blocked_tables` permits sibling outputs to persist and shadow Gate 2 work, but cannot be reported as complete and cannot silently drop blocked tables.

### 5.2 `broker_reports_pdf_compact_canonical_document_v1`

Purpose: permanent private source-facing authority after migration.

| Area/field | Type | Requirement/invariant |
|---|---|---|
| Envelope | object | `schema_version`, `canonical_document_id`, run/document/pdf artifact refs, source checksum/bytes, builder policy/config hash, canonical checksum. |
| `page_manifest` | object[] | Ordered `page_ref`, ordinal, media/crop box, rotation, page text/layout checksum refs and readiness; no full page char inventory. |
| `table_decisions` | object[] | One entry per detected table: `table_ref`, detection/classification/materialization/validation refs, path, status, reason codes. |
| Table location | object | ordered `page_refs`, page-local `table_bbox`, coordinate space/version, optional continuation group/order. |
| Structure | object | row/column counts and ordered refs, header row refs, repeated/multi-row hierarchy, spans/merged groups, deterministic structural checksum. |
| `cells` | object[] | Every grid position including empty: row/column refs+ordinals, spans, `empty_cell`, ordered candidate/source refs, exact private value path/checksum, proven bbox refs, issues. |
| `selected_source_evidence` | object[] | Only evidence used by accepted cells/headers: compact span id, exact private text, `word_ref[]`, `source_value_ref[]`, page/table-local bbox, checksum. |
| `source_value_index` | object[] | Exact one-to-one ref→private path/checksum/source object mapping for selected permanent values. |
| `blocked_table_decisions` | object[] | Table ref/location, attempted paths, terminal status, reasons, review ref; no invented grid. |
| `coverage_ledger` | object | detected/decided refs, accepted cell refs, selected evidence refs, fallback/rejected/blocked refs, duplicates/unaccounted, coverage checksum/status. |
| Guards | booleans | `semantic_table_truth_claimed=false`, `source_facts_extracted=false`, `tax_meaning_inferred=false`, `knowledge_rag_used=false`, `vectorization_performed=false`. |

Forbidden permanent content: full glyph/char universe, all bbox/vector primitives, duplicate page-level text copies, rejected grid hypotheses, unselected word inventory, base64 crops, raw provider requests/responses. A compact document may reference TTL forensic artifacts without embedding them.

### 5.3 `broker_reports_pdf_table_classification_v1`

Purpose: deterministic, auditable structural route decision; no broker-domain semantics.

Required fields:

| Field | Type | Requirement |
|---|---|---|
| `classification_id`, `policy_version`, `policy_config_hash` | string | Stable for table evidence + policy. |
| `table_ref`, `page_refs`, `table_bbox_ref`, `detection_ref` | string/string[] | Exact detected table scope. |
| `signals` | object | `ruled_signal`, `aligned_text_signal`, row/column confidence, row/column counts, width ratio, multi-row/merged header, continuation, empty/multiline density, source-word completeness, crop/readability/tiny-font indicators. |
| `deterministic_attempt` | object | attempt/result refs, status, reconstruction quality, header/grid/coverage/provenance statuses and reason codes. |
| `allowlist_decision` | object | policy allowlist id/match; cannot override missing provenance into accepted. |
| `selected_path` | enum | `deterministic_simple`, `hybrid_complex`, `hybrid_after_deterministic_block`, `unsupported_image_or_text_layer`, `human_review_required`. |
| `reason_codes`, `decision_hash` | string[]/string | Complete ordered evidence for replay. |

### 5.4 `broker_reports_pdf_hybrid_evidence_package_v1`

Purpose: immutable model-facing package for one crop revision and one bounded table/window task.

| Field | Type | Requirement/invariant |
|---|---|---|
| Identity | object | package/task/document/PDF/page/table/crop ids; source, crop, candidate dictionary and package hashes. |
| `crop` | object | artifact ref, bytes hash, page-local bbox, normalized coordinate transform, width/height, DPI, renderer/version, rotation, padding, color mode. |
| `model_candidates` | object[] | Short id `c0..cN`, candidate class, exact readable text, compact normalized bbox `[0..10000]`, optional local line/group index. |
| `private_candidate_dictionary` | object[] | Same short id → permanent span id, `source_value_ref[]`, `word_ref[]`, source bbox/checksum/private exact value path. Never safe/chat-visible. |
| `shared_header_evidence` | object[] | Header candidates represented once and referenced by id from row windows. |
| `task` | object | `reconstruct_table_structure_from_candidates`, expected table/page/window, allowed row kinds, continuation constraints. |
| `structural_constraints` | object | required exactly-once package coverage, explicit empties, source order, max grid, no free values. |
| `budgets` | object | candidate/count/byte/token/row/column/crop limits, observed values, split lineage, `truncated=false`. |
| `response_contract` | object | schema id/hash, strict structured output, candidate enum/hash, allowed terminal decisions. |
| `material_parser_issues` | object[] | Only table-local typed issues; no unrelated document/business metadata. |

Forbidden: full 22 MB payload, free-form financial output, whole-PDF text, unrelated page metadata, a second tokenizer's unbound words, silent candidate omission.

### 5.5 `broker_reports_pdf_hybrid_binding_output_v1`

The model returns placement, not values.

Required exact top-level fields:

- `schema_version`, `package_id`, `package_hash`, `crop_hash`, `candidate_dictionary_hash`;
- `decision=bound|unsupported|ambiguous` and typed `uncertainty_codes`;
- `table_shape={row_count,column_count}` within package budgets;
- `header_rows[]` with ordered row ordinal and hierarchy/group relations;
- `rows[]`, each with exact ordinal and exactly `column_count` cells;
- each cell: `row_ordinal`, `column_ordinal`, `candidate_ids[]`, `empty`, optional span/group ids and typed uncertainty;
- `package_coverage={window_ref,covered_once}`.

Invariants: ids must be members of the package dictionary; `empty=true` requires no candidates; non-empty requires at least one candidate; every grid position occurs exactly once; duplicate candidate use is forbidden unless the package explicitly marks a spanning/multiline reuse group; output contains no `value`, `amount`, `tax`, `currency_value` or arbitrary text field.

### 5.6 `broker_reports_pdf_table_materialization_result_v1`

| Field | Type | Requirement |
|---|---|---|
| Identity | object | materialization id, package/output/crop/candidate hashes, deterministic materializer version. |
| `selected_candidate_ids` | string[] | Ordered unique accounting, including allowed span reuse annotations. |
| `resolved_source_values` | object[] | Candidate id → exact private text/value, source refs, word refs, checksums; all resolved before cell acceptance. |
| `rows`, `columns`, `cells` | object[] | Deterministic refs/ordinals, full rectangular grid, explicit empties, header/spans. |
| `omitted_candidate_ids`, `extra_candidate_ids` | string[] | Explicit accounting; extras are terminal invalid. Omission may be valid only for non-table candidates and must be classified. |
| `structural_conflicts`, `provenance_conflicts` | object[] | Typed, independently validated. |
| `model_invented_values_total` | int | Must equal zero; derived structurally because output has no value fields. |
| `materialization_status` | enum | `materialized`, `blocked_candidate_resolution`, `blocked_structure`, `unsupported`. |

### 5.7 `broker_reports_pdf_table_validation_v1`

Independent gates, each `{status: passed|failed|not_applicable, reason_codes[], evidence_refs[]}`:

1. `output_contract` — exact schema/keys/types/package hashes.
2. `candidate_identity` — enum membership and dictionary hash.
3. `exact_source_value_binding` — every accepted non-empty cell resolves checksums and refs.
4. `row_width_consistency` — complete rectangular positions including empties.
5. `header_hierarchy` — ordered, non-cyclic, no silent flattening.
6. `empty_cell_coverage` — explicit and non-conflicting with candidates.
7. `duplicate_candidate_use` — only declared spans/groups may reuse.
8. `source_ref_accounting` — accepted/unused/non-table/blocked exact partition.
9. `crop_table_identity` — document/page/bbox/crop/package hashes match.
10. `unresolved_ambiguity` — none for accepted result.
11. `deterministic_signal_consistency` — conflict must be explained, never silently ignored.

Envelope fields: validation id, table/materialization/classification refs, validator version/config hash, gate map, aggregate status `accepted|blocked|human_review_required`, issue refs and checksum. Aggregate accepted requires every applicable gate passed.

### 5.8 `broker_reports_pdf_provider_attempt_v1`

| Field | Type | Requirement |
|---|---|---|
| `attempt_id`, `same_evidence_task_id`, `parent_attempt_id` | string | Lineage explicit; attempt 1 has null parent. |
| `attempt_number`, `max_attempts` | int | Initial limit 2 for identical evidence; no unbounded retry. |
| Provider identity | object | provider/profile/model requested+resolved, adapter id/version, capability qualification ref. |
| Evidence identity | object | package/crop/candidate hashes; must equal same-evidence task hashes. |
| Request identity | object | canonical/adapted schema hashes, request envelope hash, image wrapper kind; raw base64 is not duplicated in permanent metadata. |
| Execution | object | start/end, duration, HTTP status, provider response id, usage, finish reason, rate-limit metadata. |
| `raw_private_response_artifact_ref` | string/null | Private TTL/hold artifact, bounded before parsing. |
| `parse_result`, `validation_result` | object | Status/reasons/output hash; HTTP success is orthogonal. |
| `terminal_status` | enum | `accepted_for_materialization`, `provider_timeout`, `rate_limited`, `provider_error`, `response_budget_exceeded`, `invalid_json`, `schema_invalid`, `model_mismatch`, `blocked`. |

No hidden retry, no hidden failover, no evidence expansion. A 150→200 DPI escalation mints a new package and `same_evidence_task_id`; it links through `escalated_from_task_id`, not `parent_attempt_id`.

### 5.9 `broker_reports_pdf_artifact_lifecycle_v1`

Required fields: lifecycle id, artifact id/type/scope/checksum/bytes, artifact role, sensitivity, created/validated timestamps, parent refs, retention policy id, TTL/expiry, hold type/reason, intended disposition, current state, transition ledger, cleanup owner/job/receipt, deletion verification and terminal state.

Artifact roles and default disposition:

| Role | Default | Exception |
|---|---|---|
| Original PDF | `retained_permanently` under case policy | source/case deletion cascade or legal policy |
| Compact canonical + acceptance | `retained_permanently` under case policy | same cascade |
| Detailed geometry/full words/vectors | `deleted_after_acceptance` | gzip TTL 24h–7d on failure/review; incident/legal hold explicit |
| Raster crops | delete after accepted validation | TTL with review case |
| Raw provider request/output | compact attempt metadata permanent; raw payload delete after acceptance | TTL on invalid/disagreement/review |
| Rejected hypotheses/debug | delete | compressed TTL or explicit hold |

States: `created`, `validated`, `eligible_for_cleanup`, `compressed_ttl`, `retained_for_human_review`, `retained_by_incident_or_legal_hold`, `delete_pending`, `deleted`, `cleanup_failed`. `deleted` is terminal; a redacted tombstone/receipt may remain. Cleanup completion must verify payload absence and tombstone checksum/bytes metadata.

### 5.10 `broker_reports_pdf_human_review_case_v1`

Required fields:

- case/reviewer queue identity, document/table/page/crop refs and priority/SLA metadata;
- trigger enum: `raster_candidate_disagreement`, `dpi_structural_disagreement`, `bounded_attempts_exhausted`, `missing_source_candidates`, `ambiguous_duplicate_value`, `crop_uncertain`, `unsupported_structure`, `non_repeatable_output`;
- original page/table crop refs, proposed materialized structure and validation gates;
- candidate-bound values with exact refs/checksums; private values remain resolver-gated;
- alternative interpretations with their candidate ids, not free values;
- reviewer actions: `accept_proposal`, `accept_alternative`, `adjust_structure_using_candidates`, `reject_table`, `request_new_crop`, `mark_unsupported`;
- exact decision, reviewer identity/time, reason codes, resulting canonical decision ref and lifecycle updates.

Reviewer UI/API must prevent typing a new authoritative financial value. A correction may only choose/reposition existing candidates; missing source evidence sends the case back to parser/candidate remediation.

## 6. Исполняемая последовательность и ownership

| # | Stage / owner | Input → output | Failure terminal | Retry/idempotency | Coverage / persistence |
|---:|---|---|---|---|---|
| 1 | Register PDF / ArtifactStore intake | `process=false` source ref + bytes → original artifact record, checksum, document ref | `pdf_source_unavailable`, `pdf_checksum_mismatch` | Put is idempotent by source checksum + scope; no provider retry | Owns original bytes; permanent under case policy. |
| 2 | Extract working geometry / PDF parser service | Original PDF → page text + layout `broker_reports_pdf_working_geometry_v1` | `text_layer_blocked`, `layout_partial`, `parser_budget_exceeded` | Deterministic rerun only with same parser manifest; changed version creates new run | Owns all parser refs exactly once; temporary/private. |
| 3 | Detect table regions / detector | Working geometry → compact detection ledger | `table_detection_unresolved`; document may continue with explicit page outcome | Same config/hash yields same ids; alternate detector is a new version, not retry | Every detected region and every page gets accounting; ledger permanent inside canonical doc, hypotheses temporary. |
| 4 | Build compact source evidence / evidence indexer | Table bbox + production words/source index → table-local spans and reversible dictionary | `source_candidates_missing`, `source_candidate_ambiguity` | Deterministic; no tokenizer fallback that mints unbound values | Selected/non-table/blocked word refs partitioned; selected compact evidence permanent, full inventory temporary. |
| 5 | Deterministic reconstruction / deterministic reconstructor | Candidate + working geometry → deterministic attempt/result | Typed grid/header/ownership/budget reasons | Pure/idempotent by evidence+config hash | Does not drop refs; result/decision permanent, detailed attempt debug TTL. |
| 6 | Structural acceptance / table validator | Deterministic result → independent validation gates | `deterministic_table_not_accepted` | No retry without changed evidence/config | Owns accepted/blocked decision, never promotes medium visual plausibility. |
| 7 | Route / classifier | Signals + deterministic validation → `classification_v1` | unsupported/review route | Pure versioned replay; policy change creates new classification | Exactly one path per table; classification permanent. |
| 8a | Render crop / rasterizer | Original PDF + canonical table bbox + DPI policy → crop artifact/contract | crop/rotation/dimension/readability error | Same inputs byte-reproducible; 200 DPI is linked evidence escalation | Crop hash and transform permanent metadata; bytes temporary. |
| 8b | Build hybrid package / evidence packager | Crop + exact candidates + constraints → package v1 | candidate/byte/token/grid budget exceeded | Deterministic split, never truncation | Every candidate classified included/non-table/deferred; package temporary or review TTL. |
| 8c | Invoke model / hybrid provider client | Immutable package + strict schema + qualified provider → attempt v1 | typed provider/parse/schema/model mismatch | At most one same-evidence retry; no failover. Sibling tables continue. | Attempt metadata permanent; raw payload temporary/review TTL. |
| 8d | Materialize / materializer | Valid binding ids + private dictionary → result v1 | candidate resolution/grid conflict | Pure/idempotent; no model call | Full cell grid and candidate ownership accounted; accepted compact cells permanent. |
| 8e | Validate / independent table validator | Classification, package, attempt, materialization, deterministic signals → validation v1 | blocked/review | Deterministic; repeat only after new artifact revision | All gates explicit; result permanent. |
| 9 | Persist canonical decision / compact builder | All table decisions → compact canonical document v1 | canonical coverage/checksum failure | Atomic compare-and-put by canonical checksum | One terminal decision per detected table; permanent. |
| 10 | Gate 2 projection / compatibility adapter | Accepted compact table → existing normalized table projection v0 | `compact_projection_incompatible`, current validator error | Pure; same compact hash → same projection hash | Preserves rows/cells/empties/headers/source refs/issues; projection permanent. |
| 11 | Register blocks/review / review service | Blocked validation → issue + human review case | queue/storage failure; normalization remains blocked | Idempotent by table+validation hash | No silent loss; review evidence TTL/hold. |
| 12 | Final acceptance / acceptance service | Original, compact, projections, lifecycle states → acceptance v1 | `normalization_acceptance_blocked` or review | Re-evaluate after terminal transitions; no mutation of prior acceptance | Document/table/ref/storage accounting; permanent. |
| 13 | Cleanup / lifecycle worker | Acceptance + lifecycle policies → delete/compress/retain and receipt | `cleanup_failed` | Idempotent deletion; retry observable with bounded backoff | Temporary bytes must reach terminal disposition; tombstone/receipt permanent. |

Sibling policy: a failed table does not prevent detection/reconstruction of other tables. It does prevent claiming full-document acceptance. Accepted sibling projections may run in shadow or an explicitly reduced Gate 2 subset, carrying blocked table issues and never satisfying complete document coverage by omission.

## 7. Первая безопасная table-class policy

Policy id: `broker_reports_pdf_table_class_policy_v1`. Все thresholds входят в `policy_config_hash`; изменение threshold создаёт новую decision revision.

### 7.1 Deterministic acceptance

Маршрут `deterministic_simple` допустим только когда одновременно:

1. candidate detection identity, page/table bbox и ordered contributing words complete;
2. row/column grid полный, rectangular с явными empty positions;
3. `row_count>=2`, `column_count>=2`, одинаковая width либо spans объясняют разницу;
4. header model `mapped`, hierarchy не flatten silently, нет unresolved merge/split;
5. все non-empty cells имеют existing `source_value_ref` и `word_ref`, checksum воспроизводится;
6. нет duplicate word/candidate ownership, unexpected или unaccounted refs;
7. continuation absent либо deterministic continuation group/order proven exactly;
8. `ambiguous_cell_boundary=false` для всех cells;
9. no serialized/grid/candidate budget overflow;
10. independent table validation passed.

Текущие `high|medium` geometry quality недостаточны сами по себе. В v1 accepted deterministic должен удовлетворять всем hard gates; confidence — diagnostic, не override.

### 7.2 Hybrid route

`hybrid_complex` или `hybrid_after_deterministic_block` выбирается при одном observable signal:

- multi-row/merged header или header-to-column mapping ambiguous;
- wide table: первичный conservative threshold `column_count > 10` или crop width/table width signal выше policy threshold;
- cross-page continuation;
- `pdf_table_geometry_column_structure_insufficient`;
- empty-cell density `> 0.20` или multiline-cell density `> 0.15`;
- conflicting deterministic grid hypotheses;
- tiny-font/readability signal, когда 150 DPI still within render limits;
- explicit versioned allowlist entry for a proven class.

Эти числа — начальные routing thresholds, а не accuracy claims. Их требуется заморозить в Phase 0 fixtures и менять только через новую policy revision.

### 7.3 Human review / unsupported

Немедленный review/unsupported route:

- text layer не даёт точные candidates для видимых значений;
- crop/table boundary неуверен или захватывает соседнюю таблицу;
- raster structure и exact candidate inventory materially disagree;
- 150/200 DPI дают несовместимые структуры, и deterministic validator не выбирает одну;
- invalid structured output после максимум двух attempts одного package;
- одинаковые candidate values не разрешаются координатами/word refs;
- output остаётся ambiguous/unsupported;
- image-only/scanned table без approved OCR candidate-source contract.

Classifier не использует слова `trade`, `tax`, `income`, `fee` и не маршрутизирует по business domain.

## 8. Raster и DPI contract

### 8.1 Reproducible render

- renderer: initial implementation pin `PyMuPDF==1.26.5` and `pdf_table_raster_policy_v1`; это версия текущего experiment environment, но её требуется оформить прямой service dependency; version/config входит в crop identity;
- source coordinate space: unrotated PDF points in page crop-box coordinates; explicit affine transform to rendered pixels;
- rotation: normalize page `/Rotate` into visual orientation; record original and applied rotation;
- crop: detector bbox + 2 PDF-point padding on each side, clipped to page crop box; padding is config, not heuristic hidden state;
- primary DPI: 150;
- escalation DPI: 200 only after a typed structural/readability failure;
- format: lossless RGB PNG, `alpha=false`; JPEG forbidden for authoritative candidates because compression can change tiny glyphs/lines;
- grayscale is an optional challenge revision only; primary remains RGB to avoid losing colored separators;
- checksum: SHA-256 of exact PNG bytes plus separate render-spec hash;
- maximum: 4096×4096 pixels, 8 MiB encoded crop, 16 megapixels; oversize table is split deterministically or sent to review;
- tiny-font signal: estimated rendered median glyph height `< 8 px` or fifth percentile `< 6 px` at 150 DPI triggers 200 DPI if within limits;
- provider capability record must declare supported MIME, max bytes/dimensions and strict structured output before call.

### 8.2 A versus B

| Policy | Accuracy evidence | Calls/cost | Observability | Risk |
|---|---|---|---|---|
| A: 200 DPI all complex | Wide `1:3` recovered at 200 DPI | One call per table | Simpler | 200 DPI introduced an extra empty column in continuation `4:1`; larger images; no corpus proof that all cases improve. |
| B: 150 primary → structural check → 200 escalation | 8/9 primary hybrid cases were exact at 150; one wide failure recovered at 200 | Extra call only on typed failure | Best: both render specs, hashes and validator reasons explicit | More orchestration, but deterministic and bounded. |

Recommendation: **B**. It лучше соответствует имеющимся evidence и не объявляет 200 DPI универсально superior. 200 DPI call uses a new crop/package hash; same-evidence retry may occur separately only for provider/JSON failure. До human sign-off это engineering policy for shadow validation, не production accuracy guarantee.

## 9. Candidate evidence compaction и budgets

### 9.1 Reversible compaction

1. Select only production words whose bbox center lies inside table bbox or intersects a declared boundary tolerance; outside words go to an accounted non-table bucket.
2. Group adjacent words into exact source spans only when same page/line, monotonic coordinates, bounded gap and no ref overlap. Span stores ordered constituent refs and exact join policy.
3. Represent each shared header span once. Row windows reference header ids; no repeated header text/dictionary.
4. Model-facing ids are dense `c0..cN`; UUID-like production refs remain only in the private dictionary.
5. Coordinates are integer table-local `[x0,y0,x1,y1]` in `[0,10000]`; permanent evidence additionally retains exact source bbox refs/transform.
6. Keep only `id`, class, exact text, compact bbox and optional line/group in the prompt. Parser diagnostics, checksums and production refs stay outside model view.
7. Candidate classes: `numeric_like`, `date_like`, `currency_code`, `short_text`, `long_text`, `header_text`, `symbol`; classification is lexical/mechanical, not business semantic.
8. Deterministic neighborhood filtering may split by row bands but cannot discard a candidate inside the declared table window. Deferred candidates belong to a different exactly-once window.

Reversibility invariant:

```text
model candidate id
→ private candidate dictionary entry
→ ordered exact span
→ one-or-more existing source_value_ref + word_ref
→ private exact value path + checksum
```

### 9.2 Initial measurable limits

| Budget | Initial hard limit | Terminal behavior |
|---|---:|---|
| Candidates per package | 512 | Split by deterministic row windows; never truncate. |
| Candidate JSON bytes visible to model | 128 KiB | Compact/group then split; blocked if one indivisible row exceeds. |
| Estimated evidence tokens | 32,000, target ≤24,000 | Estimate by UTF-8 chars/4 plus adapter-specific measured count when available; no call above hard limit. |
| Estimated binding-output tokens | target ≤12,000, hard 16,384 | Pre-call structural estimate; reduce row window before call. Provider-qualified lower limit overrides and causes a smaller deterministic window. |
| Rows per package | 64 | Ordered row-window split with shared immutable header ref. |
| Columns per package | 24 | Columns are not split independently in v1; oversized structure → review/unsupported. |
| Grid positions | 1,536 | Must equal rows×columns including empties. |
| Header depth | 8 | Deeper/ambiguous hierarchy → review. |
| Crop | 4096×4096, 16 MP, 8 MiB PNG | Deterministic row-band crop split only when continuation rules can preserve one table identity; otherwise review. |
| Provider raw response | 512 KiB | `response_budget_exceeded`; raw prefix/hash retained by policy, never parse partial as accepted. |
| Same-evidence attempts | 2 total | Exhaustion → review; no provider failover. |

Split contract: `parent_table_task_id`, ordered `window_ref`, `row_start/end`, shared header/crop refs, candidate partition checksum and `windows_total`. Windows must cover each non-header table-local candidate exactly once; header refs may be shared explicitly. A deterministic join validates identical column/header identity before materialization. There is no column-wise split in v1 because it weakens structural observability.

Budgets are intentionally separate from Gate 2 context v2 (`max_candidates=64`, `max_context_chars=48000` in current code). Hybrid candidates reconstruct structure; Gate 2 candidates classify business facts later. Их нельзя смешивать или считать одним LLM budget.

## 10. Provider-neutral boundary

### 10.1 Canonical flow

```text
HybridEvidencePackageFactory
→ CanonicalHybridRequest {task, crop_ref/hash, model_view, strict_schema}
→ PdfHybridProviderAdapterFactory
→ provider-specific image wrapper + schema projection
→ exactly one transport invocation
→ ProviderAttempt v1
→ strict canonical binding parser
```

Initial allowlisted candidate: `google_gemini` / `models/gemini-3.5-flash`, because current controlled hybrid evidence was obtained through that multimodal path. This is not automatic qualification: Phase 4 must create `pdf_table_multimodal_strict_v1` capability evidence for exact model id, image transport, schema adapter, response budget, resolved-model match and repeatability.

Provider contract:

- canonical request is provider-neutral and contains image by immutable artifact ref/hash, strict schema and compact candidate view;
- adapter alone creates OpenAI/Gemini/Anthropic image/document wrapper and provider schema projection;
- canonical and adapted schema hashes plus transform count are recorded;
- supported capabilities: multimodal image, strict structured output, resolved model identity, token/byte budgets, temperature/control semantics;
- error classes: configuration, capability, auth, rate limit, timeout, HTTP, response budget, invalid/malformed content, schema, model mismatch, non-repeatability;
- no hidden failover. A different provider/model is a new task revision requiring explicit policy/allowlist and cannot repair the same acceptance record invisibly.

`Gate2OpenWebUIRequestBuilder` and `Gate2StructuredModelClientFactory` stay business-runtime-owned. В первом срезе не следует создавать speculative generic transport refactor: отдельный small PDF hybrid adapter is safer. A shared provider substrate may be extracted later only after both callers demonstrate stable duplicated mechanics, while preserving both factories and public contracts.

Direct whole-PDF/plain-text remains `broker_reports_pdf_direct_challenge_v1` outside normalization acceptance. Его output may create a discrepancy/review issue, but cannot produce accepted canonical cells or source facts.

## 11. Gate 2 compatibility design

### 11.1 Adapter boundary

New `PdfCompactGate2ProjectionAdapterFactory.create()` consumes only an accepted table decision from `broker_reports_pdf_compact_canonical_document_v1` and emits `broker_reports_normalized_table_projection_v0`. It then runs the existing `TableProjectionValidator`; no adapter-specific bypass is allowed.

| Compact field | Existing v0 projection | Rule |
|---|---|---|
| canonical document/table ids | `source_document_ref`, `parent_payload_ref`, `source_unit_ref`, `table_ref` | Preserve compact ids; do not mint alternate table authority. |
| accepted path | `table_origin`, `reconstruction_strategy`, `reconstruction_reason_codes` | `reconstructed_candidate`; strategy `compact_deterministic_v1|candidate_bound_hybrid_v1`. |
| ordered rows/columns | `row_refs`, `column_refs`, `rows`, counts | Exact order; deterministic stable refs from compact table checksum/ordinals. |
| full grid | `cells`, `cell_refs`, `cell_value_refs`, counts | Every position including empty; exact spans and ambiguity flags. |
| header hierarchy | `header_model` | Preserve header/repeated header refs, multi-row flag, labels and source refs; no flattening. |
| selected evidence | `private_values`, `source_value_refs`, `source_value_index` | Rebase private paths into projection while retaining source refs/checksums. |
| page/table bbox | `page_refs`, `table_bbox_ref`, optional compact `geometry` metadata | Crop is not passed to Gate 2. |
| validation/issues | `quality`, `reconstruction_quality`, reason codes and issue refs in package | Only accepted tables may be ready; blocked tables have no fake projection. |
| coverage ledger | `coverage` v0 | Exact selected/table-owned/fallback/rejected partition; duplicates/unaccounted empty. |
| guards | existing booleans | All semantic/business/tax/RAG flags false. |

Compatibility checksum rule: `table_projection_checksum_ref` covers the v0 projection; it also stores `compact_canonical_checksum_ref` and `compact_table_validation_ref` in an additive `compatibility_origin` object. Current validator must be extended only to allow and verify this known additive object, or the origin refs remain in ArtifactStore safe metadata if strict unknown-key policy requires zero schema change. The safer Phase 0 choice is safe metadata plus existing v0 fields, followed by an explicit v0.1 contract only if consumers need in-payload origin.

### 11.2 Narrow readiness change

Current `Gate2InputReadiness._resolve_private_slices` ignores standalone table projections when full-source units are absent. Add a feature-flagged branch:

```text
prefer_compact_pdf_table_projections=true
AND validated compact canonical artifact resolves in same scope
AND projection safe metadata binds compact document/table/checksum
AND existing TableProjectionValidator passes
AND projection coverage is complete
→ select ordered v0 projections directly
```

Otherwise current priority remains unchanged. Rollback is flag-off; old full-source path remains during dual-write. This is a boundary adapter, not a Gate 2 rewrite.

### 11.3 Downstream proof obligations

- normalized rows/cells/empties: `Gate2TablePackageBuilder` serializes the complete grid and explicit row roles;
- header hierarchy: v0 `header_model` becomes `normalized_header_descriptors`, repeated headers and mandatory no-fact coverage;
- source candidates: existing `Gate2CandidateBindingKernel` discovers candidates only from resolvable projection `source_value_index`;
- refs/checksums: `allowed_source_value_refs`, `allowed_evidence_refs`, source/slice/unit/projection checksums remain bounded;
- issues: compact validation/review issues link through existing package `issue_context`/`allowed_issue_refs`;
- segmentation: existing segmenter partitions selected row refs and narrows values without deep-copying the full document;
- LLM context v2: existing compact projection builds `broker_reports_gate2_llm_context_package_v2` within its own budget;
- business candidate binding: unchanged response contract selects existing Gate 2 candidate/relation ids;
- source-fact validator: unchanged invented-value and allowed-ref checks;
- deterministic stitch: unchanged exactly-once source-ref ownership and complete/blocked coverage.

The table VLM call ends before all of these business stages. It must not receive extractor domain, business roles, tax rules or final fact schema.

## 12. Storage and retention projection

### 12.1 Measured baseline

| Component for controlled six-page PDF | Bytes | Gzip | Retention role |
|---|---:|---:|---|
| Original PDF | 176,458 | already compressed | permanent under case policy |
| Visible extracted text | about 29,748 | n/a | content signal, not separate permanent requirement |
| Current full normalized payload | 22,185,586 | 3,596,493 | temporary/debug target; currently disproportional permanent candidate |
| Compact deterministic experiment | 155,180 | 37,855 | measured compact lower-complexity representation |
| Compact hybrid experiment | 465,549 | 112,748 | measured candidate-bound representation |
| Shared experimental crop PNGs | 776,888 | n/a | temporary |

### 12.2 Comparable-PDF projection

Decimal MB/GB; ArtifactStore record/index overhead is budgeted separately.

| Scenario | One PDF | 100 PDFs | Meaning |
|---|---:|---:|---|
| Current original + uncompressed full normalized | 22.36 MB | 2.236 GB | Must not be steady-state target. |
| Original + compact deterministic measured payload | 0.332 MB | 33.16 MB | If all tables are deterministic/simple. |
| Original + compact hybrid measured payload | 0.642 MB | 64.20 MB | Conservative measured permanent source-facing basis. |
| Planned successful steady-state envelope | ≤0.75 MB | ≤75 MB | Original + compact canonical + acceptance/lifecycle metadata; crops/geometry/raw responses removed. |
| Active debug TTL, measured components only | 5.02 MB | 501.54 MB | Original + hybrid compact + gzip geometry + shared crops; excludes bounded raw attempts. |
| Planned blocked/review active TTL envelope | ≤18 MB | ≤1.8 GB | Adds up to nine packages × two bounded 128 KiB request-evidence + 512 KiB responses, cleanup metadata and margin. Temporary only. |
| Hard per-document debug cap | 64 MiB | not an ordinary batch target | Further evidence creation blocks or requires explicit incident/review hold. |

Expected steady state: at most 0.75 MB per comparable successful PDF, about 75 MB for 100. A blocked PDF may temporarily occupy up to 18 MB under TTL; 100 simultaneously blocked comparable PDFs could reach about 1.8 GB during the active window, but not permanent retention.

Worst-case incident storage is governed, not inferred from typical size:

- `max_debug_bytes_per_document=64 MiB`;
- `max_debug_bytes_per_normalization_run=512 MiB`;
- any retention beyond TTL requires `incident_or_legal_hold` id, owner and reason;
- 100 documents each at the hard cap would be 6.25 GiB (about 6.71 decimal GB) and is permitted only as an explicit exceptional hold, never ordinary production retention;
- cleanup removes raw provider output, crops and geometry independently; one cleanup failure does not extend every artifact automatically.

Provider request storage must reference crop/package hashes rather than persisting duplicate base64 image copies. Attempt metadata is permanent and small; raw request/response is TTL or review hold.

## 13. Verification and corpus plan

### 13.1 Required corpus before production migration

1. Actual named human sign-off on current nine-table reference set; status changes from `agent_visual_reviewed_pending_human_signoff` only via a review artifact.
2. At least one real or explicitly approved controlled gridless table.
3. At least one wide cross-page continuation.
4. At least one multi-row/merged-header table.
5. At least one small-font dense table.
6. At least one intentionally ambiguous/unsupported table with expected review outcome.

Each case needs original checksum, page/table bbox, human reference grid including empties, header hierarchy, expected decision/path, exact cell/source refs where text layer exists, reviewer and sign-off timestamp. Synthetic cases may supplement but not replace approved real/controlled structural classes.

### 13.2 Hard metrics

| Metric | Definition | Initial rollout gate |
|---|---|---|
| Table detection recall | reference table identities detected / reference identities | 100%; zero silent loss |
| Exact structure | exact row count, column count, grid positions and spans | 100% accepted tables |
| Exact cell values | exact normalized accepted cell matches including omission/invention penalties | Threshold frozen after human sign-off; current provisional 99.04% is evidence, not gate. |
| Exact numeric-like values | exact numeric-like cells including empty/omission penalties | Zero invented financial values; numeric threshold frozen after sign-off. |
| Header accuracy | exact header rows, hierarchy and column mapping | 100% accepted tables |
| Empty-cell accuracy | exact empty positions / expected empties | 100% accepted tables |
| Hallucination count | value/candidate outside source evidence | 0 accepted |
| Omission count | expected non-empty cells absent | 0 accepted; otherwise blocked/review |
| Provenance coverage | accepted non-empty cells with fully resolved refs/checksums | 100% |
| Provider/schema failure rate | non-accepted provider attempts / attempts, by model/version | Measured and bounded; any result after exhausted attempts is review, never auto-accepted. |
| Repeatability | same input/config → identical materialized grid/checksum across approved reruns | 100% on acceptance corpus, or typed non-repeatability blocks class/model. |
| Storage | permanent, temporary peak, post-cleanup, compressed debug | ≤0.75 MB steady comparable PDF; no unexplained permanent geometry. |
| Processing time | per stage, per table, per provider attempt and total p50/p95 | Baseline in shadow; rollout budget approved before Phase 5. |
| Cleanup | temporary artifacts with terminal receipt before/at expiry | 100% |

Accuracy denominator includes failed/malformed provider attempts as omitted output for the scheduled case; accepted-only diagnostics are never rollout metrics.

### 13.3 Test layers

- contract fixtures: exact keys/enums/hashes, unknown fields, invalid refs and no free-value output;
- deterministic unit tests: classifier policy, crop transforms/rotation, span grouping, split/join, materialization, all validation gates, lifecycle transitions;
- property tests: every accepted grid position exactly once; candidate/source ref partitions; no candidate id outside enum; idempotent hashes/cleanup;
- golden corpus: human-approved structures/values/headers/empties and known blocked outcomes;
- dual-write differential tests: current v0 projection versus compact-derived v0 projection;
- provider contract tests: canonical/adapted schema, model identity, malformed JSON, max response, timeout/rate limit, no retry/failover;
- Gate 2 regression: current table projection, input readiness, segmentation, domain packages, context v2, candidate binding, source-fact validation/stitch suites unchanged;
- local E2E: original → compact → v0 projection → Gate 2 shadow with no production writes;
- live proof in runtime phases: process=false upload, private ArtifactStore resolution, managed bundle SHA parity, feature flag/allowlist, cleanup expiry and no Knowledge/vector delta.

## 14. Staged migration

| Phase | Entry | Change / flags | Exit evidence | Rollback / retained evidence | Repo/live parity |
|---|---|---|---|---|---|
| 0 — contracts/tests only | This design approved | Add schemas, validators, fixtures; all runtime flags absent/off | Contract tests + golden invalid cases; no production behavior change | Remove unused new modules; report/contracts retained | Repo tests only; no deploy. |
| 1 — dual-write compact | Phase 0 passed | `pdf_compact_canonical_dual_write=true`; keep current full artifacts authoritative | Same table inventory/ref accounting; compact checksum reproducible; storage measured | Flag off; old artifacts untouched | Source + bundled Gate 1 parity before live canary. |
| 2 — deterministic compact shadow | Dual-write stable | `pdf_compact_deterministic_shadow=true`; classifier records decisions but cannot accept runtime | Current accepted deterministic projections equivalent or differences explicitly blocked | Flag off; retain diff artifacts TTL | Local corpus then process=false live shadow. |
| 3 — hybrid only for current blocks | Human-approved provider capability and lifecycle cleanup ready | `pdf_hybrid_shadow=true`, class allowlist; no projection authority | Bounded attempts, candidate provenance 100%, all outcomes accepted-shadow or review | Flag off stops calls; retain attempts/crops by TTL | Provider/model/config + bundle SHA + live private evidence. |
| 4 — compare with current/human | Signed corpus exists | Differential scorer over current, compact deterministic, hybrid, human reference | Hard metrics and repeatability pass; every disagreement adjudicated | Continue current authority; preserve signed references/diffs | Repo full suite and controlled live repeat. |
| 5 — allowlisted accepted projection | Phase 4 gates passed | `pdf_hybrid_accept_enabled=true`, explicit corpus/table-class/provider/model allowlists, `prefer_compact_pdf_table_projections=true` | Gate 2 E2E equivalence, zero validator weakening, cleanup terminal, canary accepted | Disable accept/readiness flags; current v0 full path remains | HEAD/bundle/live SHA parity, managed prompt/function parity, process=false canary. |
| 6 — compact permanent, geometry temporary | Sustained Phase 5 evidence, incident rollback tested | `pdf_full_geometry_temporary=true`; role-specific TTL/cleanup | Dual-write equivalence window complete; post-cleanup Gate 2 reproducibility from original+compact proven | Re-enable forensic retention temporarily by explicit policy; never delete old records retroactively | Cleanup worker/live ArtifactStore parity and tombstone proof. |
| 7 — expand classes | Per-class signed evidence | Versioned class/provider allowlist expansion only | Each new class independently meets hard metrics | Remove class from allowlist; siblings unaffected | Same proof per expansion; no blanket enable. |

Do not delete existing forensic artifacts before Phase 6. Historical v0 artifacts are immutable. During rollback, new compact artifacts remain auditable but Gate 2 selection returns to the prior path.

Repository/live parity in phases with runtime change requires:

- clean intentional commit scope; full relevant test suites;
- regenerated bundled OpenWebUI functions from the same source state, not manual edits;
- source/bundle SHA recorded and equal to deployed managed function bundle;
- feature flags, provider profile/model and policy config hashes captured;
- process=false live canary; Knowledge/vector counters unchanged;
- ArtifactStore original/compact/projection/attempt/lifecycle refs resolvable in the same user/case scope;
- cleanup receipt after TTL probe;
- final `HEAD == origin/main` and clean tree when rollout is declared complete.

## 15. Failure modes и threat model

Sibling continuation below means the pipeline may process other tables, while document acceptance remains incomplete until the failed table is terminally resolved/accounted.

| Failure | Detection | Typed terminal / escalation | Evidence retained | Siblings |
|---|---|---|---|---|
| Wrong table crop | crop bbox outside detector bbox tolerance; candidate coverage/neighbor table refs conflict | `pdf_hybrid_crop_identity_mismatch` → new deterministic crop revision or review | page/table bbox, crop hash/image TTL, transform, detector refs | yes |
| Wrong page rotation | page rotation/render transform mismatch; text bbox vs pixel positions fail | `pdf_hybrid_page_rotation_mismatch` → rerender corrected explicit rotation once, else review | render spec, both crop hashes, page metadata | yes |
| DPI sensitivity | 150 fails structure/readability or 150/200 materializations differ | `pdf_hybrid_dpi_structural_disagreement` → 200 revision then review if conflict remains | both crops/packages/outputs/validations TTL | yes |
| Missed column | row-width/header/candidate x-cluster checks; reference/deterministic signal conflict | `pdf_table_column_omission` → 200 evidence or review | binding, candidate positions, grid conflicts | yes |
| Extra empty column | all-empty column, header mapping gap, 150/200 difference | `pdf_table_extra_empty_column` → reject attempt; alternate DPI does not auto-win without validation | same | yes |
| Merged-header ambiguity | cyclic/overlapping spans, header path not mapping exactly | `pdf_table_header_hierarchy_ambiguous` → review | proposed hierarchy, alternatives, refs | yes |
| Repeated identical values | same text/checksum with multiple word refs and unresolved geometry | `pdf_source_candidate_duplicate_ambiguous` → coordinate disambiguation or review | duplicate group, bboxes, refs | yes |
| Valid candidate in wrong cell | spatial order/neighborhood and deterministic signals disagree | `pdf_candidate_cell_placement_conflict` → reject/review; provenance alone is insufficient | selected ids, positions, validator conflict | yes |
| Missing production source refs | candidate dictionary entry cannot resolve/checksum | `pdf_source_candidate_provenance_missing` → parser remediation/review; no raster-only acceptance | source index diagnostics, crop, missing refs | yes |
| Malformed strict output | JSON/schema parser fails exact contract | `pdf_provider_output_invalid_json|schema_invalid`; one same-evidence retry, then review | raw response TTL, attempt lineage/hash | yes |
| Provider timeout/rate limit | transport classification | `pdf_provider_timeout|rate_limited`; one bounded same-evidence retry only if policy permits, no failover | request hash, timing, provider metadata | yes |
| Non-repeatable output | same package accepted materialization checksums differ | `pdf_provider_non_repeatable` → model/class blocked pending review | both attempts/results | yes |
| Model/version drift | resolved model/profile revision differs from allowlist | `pdf_provider_model_mismatch|capability_not_qualified`; no call/acceptance | execution metadata/profile hashes | yes |
| Parser/version drift | parser manifest/config differs; ids or compact result change | `pdf_parser_reproducibility_failed` → new normalization revision and differential review | both manifests/artifact hashes | yes |
| Cleanup failure | expiry passed but payload exists; transition/receipt absent | `pdf_artifact_cleanup_failed`; retry cleanup, alert/incident | lifecycle ledger, bytes, error; do not extend silently | processing yes; final acceptance no |
| Compact incompatible with Gate 2 | adapter or existing projection/package validator fails | `pdf_compact_gate2_projection_incompatible`; rollback selection to current path | compact, projected v0, validator errors | yes, old path while available |
| Provider response budget exceeded | byte limit crossed before full parse | `pdf_provider_response_budget_exceeded`; no partial acceptance | bounded prefix/hash/metadata by TTL | yes |
| Candidate/package budget exceeded | pre-call measured hard budget | `pdf_hybrid_evidence_budget_exceeded`; deterministic split or review | budget metrics, split plan | yes |
| Human-review backlog | queue age/size exceeds configured SLA/cap | `pdf_human_review_capacity_blocked`; stop new accepted expansion, keep explicit cases | compact review metadata; private evidence TTL extended explicitly | existing siblings yes; document incomplete |
| Cleanup removes needed evidence too early | dependency graph or active review ref exists | `pdf_artifact_cleanup_dependency_blocked`; cancel delete, correct lifecycle policy | dependency refs/transition ledger | yes |
| Prompt/provider injection from visible text | candidates contain instructions or schema-like text | strict ids-only output, exact enum, no free text; `pdf_hybrid_output_contract_violation` | package/output TTL | yes |
| Cross-document/cross-table ref leak | candidate ref scope/hash mismatch | `pdf_hybrid_candidate_scope_violation`; security/privacy block | redacted attempt metadata, audit issue | yes, affected run may privacy-block |

Operational threats:

- Treat crop and provider raw output as private customer data even when filenames are absent.
- Never log candidate exact text, base64 images, raw responses or API credentials to safe stdout/report.
- Model-facing candidates may contain hostile document text; strict schema and enum membership, not prompt wording, enforce the boundary.
- A provider/model allowlist is capability-specific. Gate 2 structured-output approval does not automatically approve multimodal table reconstruction.
- Review overrides are signed artifacts and cannot mutate prior model/parser evidence in place.

## 16. Ordered implementation backlog

### Slice 1 — Compact canonical artifact and normalization acceptance

- Goal: implement v1 schemas/builders/validators and deterministic ids without changing current authority.
- Modules: new `pdf_compact_canonical.py`, `pdf_normalization_acceptance.py`; additive `artifact_models.py`, `contracts.py`, `normalizer.py` integration under dual-write flag.
- Contracts: compact canonical, normalization acceptance, initial lifecycle metadata.
- Tests: contract fixtures, exact coverage/ref/hash/idempotency, forbidden full-geometry fields, invalid acceptance gates, non-PDF regression.
- Migration: flag off by default; dual-write only; current full payload/projection remains authoritative.
- Live proof: not required in first commit; local controlled PDF produces compact artifact and byte metrics.
- Acceptance status: ready to code after schema/flag naming approval.

### Slice 2 — Temporary geometry lifecycle and dual-write

- Goal: separate working geometry/crops/debug from permanent compact data and make cleanup observable without deleting current artifacts yet.
- Modules: new `pdf_working_artifacts.py`, lifecycle worker/receipt; revise `artifact_models.py`, `artifact_store.py`, `artifact_lifecycle.py`, `artifact_retention.py`, `gate2_handoff.py` behind factories.
- Contracts: artifact lifecycle v1; artifact roles, binary/private payload kind, per-artifact TTL/hold.
- Tests: state machine, binary checksum/read/delete, expiry/purge idempotency, dependency/hold, failed cleanup, source/chat/case cascades.
- Migration: current full payload still stored; new lifecycle is shadow/measurement until Phase 6.
- Live proof: process=false private crop/geometry write, expiry, payload absence+tombstone receipt, no Knowledge/vector delta.
- Acceptance status: design ready; production deletion remains disabled.

### Slice 3 — Classifier and deterministic acceptance strengthening

- Goal: turn current deterministic result into explicit attempt/validation/classification rather than `high|medium` implicit promotion.
- Modules: new `pdf_table_classification.py`, `pdf_table_validation.py`; refactor/wrap `pdf_layout_units.py` and `PdfTableCandidateProjectionBuilder` in `table_projection.py` without changing v0 output.
- Contracts: classification v1, deterministic subset of materialization/validation v1.
- Tests: simple/wide/header/continuation/empty/multiline/conflicting hypotheses, exact ref accounting, policy version replay.
- Migration: shadow classifier compares current 9 ready/5 blocked decisions; no path switch.
- Live proof: controlled PDF decision ledger and deterministic diff report.
- Acceptance status: ready to code; thresholds are initial and versioned.

### Slice 4 — Hybrid evidence, raster and provider attempt

- Goal: productionize reproducible crop, compact candidate package and provider-neutral bounded call.
- Modules: new `pdf_table_raster.py`, `pdf_hybrid_evidence.py`, `pdf_hybrid_provider.py`; reuse production word/source refs, not experiment tokenizer; research harness remains proof only.
- Contracts: hybrid evidence package, binding output, provider attempt.
- Tests: rotation/padding/hash, grouping/reversibility, budgets/splits, schema adapter, model mismatch, timeout/rate limit, malformed/oversized output, same-evidence lineage/no failover.
- Migration: hybrid shadow only for deterministic-blocked allowlisted tables; raw evidence TTL.
- Live proof: qualified Gemini model id, 150→typed 200 escalation, attempt artifacts, secret-safe stdout.
- Acceptance status: implementation-ready; automatic acceptance blocked by human corpus/sign-off.

### Slice 5 — Candidate-bound materializer and independent validator

- Goal: convert only valid candidate ids into full canonical grid and reject every provenance/structure ambiguity.
- Modules: new `pdf_hybrid_materialization.py`, complete `pdf_table_validation.py`, compact builder integration.
- Contracts: materialization result, table validation, human-review case trigger.
- Tests: invented key/value, invalid/duplicate ids, wrong placement, empty conflicts, header cycles, package/crop mismatch, exact source checksum resolution, deterministic repeatability.
- Migration: accepted-shadow result compared with human/current; no Gate 2 selection yet.
- Live proof: current nine-table controlled set plus required new structural cases after approval.
- Acceptance status: ready to code; rollout blocked by corpus.

### Slice 6 — Gate 2 compatibility and shadow E2E

- Goal: project accepted compact table into current v0 contract and prove entire existing Gate 2 chain unchanged.
- Modules: new `pdf_compact_gate2_adapter.py`; narrow feature-flag branch in `gate2_input_readiness.py`; additive persistence in `gate2_handoff.py`; no changes to segmentation/context/candidate binding/fact validators/stitch logic.
- Contracts: existing normalized table projection v0/package v0 plus compact-origin safe metadata.
- Tests: compact→v0 mapping, current `TableProjectionValidator`, package validation, segmentation, context v2, candidate binding, source-fact invented-value and stitch coverage regressions; differential equivalence.
- Migration: selection flag off, then allowlisted shadow, then Phase 5 canary; rollback flag selects current full-source path.
- Live proof: process=false compact-derived projection through Gate 2, bundle/runtime SHA parity, same source refs/checksums and zero validator changes.
- Acceptance status: compatibility designed; not runtime-proven yet.

### Slice 7 — Human review and rollout controls

- Goal: complete explicit unsupported/disagreement path, queue capacity and per-class/provider rollout.
- Modules: new `pdf_human_review.py` and resolver-gated review API/artifact projection; feature flags/allowlists, lifecycle dependency integration, safe operational summary.
- Contracts: human review v1, final normalization acceptance/lifecycle transitions.
- Tests: allowed reviewer actions, no typed financial values, alternative candidate mapping, SLA/backlog stop, hold/cleanup, acceptance re-evaluation.
- Migration: review first in shadow; enable accepted projections only after signed corpus and queue readiness.
- Live proof: one accepted correction, one unsupported decision, one TTL extension and one rollback canary.
- Acceptance status: design ready; exact reviewer product surface and operational owner require approval before rollout, not before core coding.

The seven slices are intentionally coherent. A generic provider framework, OCR source contract and broad review UI are deferred; none is needed to prove the compact candidate-bound path.

## 17. Proof surfaces and source-of-truth references

Existing regression/proof surfaces to preserve:

- PDF page text: `scripts/local_case_group_pdf_text_layer_slice1_proof.py`, `tests/test_broker_reports_pdf_text_layer_slice1.py`;
- layout/candidates: `scripts/local_case_group_pdf_layout_slice2_proof.py`, `scripts/live_pdf_layout_slice2_runtime_proof.py`, `tests/test_broker_reports_pdf_layout_slice2.py`;
- table projection: `scripts/local_case_group_table_projection_proof.py`, `scripts/local_table_projection_worker.py`, `tests/test_broker_reports_table_projection.py`;
- deterministic/raster/hybrid research: `scripts/local_pdf_table_approach_experiment.py`, `tests/test_broker_reports_pdf_table_experiment.py`;
- Gate 2 whole-document/table path: `scripts/live_single_pdf_whole_document_gate2_e2e.py` and existing Gate 2 input/domain/candidate/provider tests;
- lifecycle: `scripts/live_artifactstore_retention_smoke.py`, ArtifactStore tests;
- challenge only: `local_direct_pdf_multi_provider_experiment.py`, `local_direct_pdf_plain_text_experiment.py` and their tests.

Evidence source reports:

- `docs/reports/2026-07-12/OPENWEBUI_BROKER_REPORTS_PDF_NORMALIZATION_ACCEPTANCE_AUDIT.report.md`;
- `docs/reports/2026-07-12/OPENWEBUI_BROKER_REPORTS_PDF_TABLE_DETERMINISTIC_RASTER_HYBRID_EXPERIMENT.report.md`;
- `docs/reports/2026-07-12/OPENWEBUI_BROKER_REPORTS_DIRECT_PDF_MULTI_PROVIDER_EXPERIMENT.report.md`;
- `docs/reports/2026-07-13/OPENWEBUI_BROKER_REPORTS_DIRECT_PDF_PLAIN_TEXT_VS_HYBRID_EXPERIMENT.report.md`.

Authoritative current contracts retained at the boundary:

- `BROKER_REPORTS_PDF_TEXT_LAYER_PAYLOAD.v0.md` and `BROKER_REPORTS_PDF_TEXT_LAYER_SOURCE_UNITS.v0.md` during migration;
- `BROKER_REPORTS_NORMALIZED_TABLE_PROJECTION.v0.md` as the Gate 1→Gate 2 structural bridge;
- `BROKER_REPORTS_GATE2_SOURCE_UNIT_ROUTING.v0.md`, `BROKER_REPORTS_GATE2_SOURCE_VALUE_CANDIDATES.v0.md`, source-fact extraction/validation/stitch contracts downstream;
- `BROKER_REPORTS_ARTIFACT_LIFECYCLE_CONTRACT.v0.md` as current lifecycle baseline to version, not mutate silently.

## 18. Blockers and decisions

### Before coding

No evidence blocker prevents Phase 0–3 implementation. Required merge-time decisions:

1. approve exact schema/module/feature-flag names and whether compact origin remains ArtifactStore safe metadata or creates additive normalized-table v0.1;
2. approve ArtifactStore binary/private payload API and per-artifact retention override while preserving the factory boundary;
3. assign cleanup worker ownership and initial TTL/default caps;
4. approve initial routing/budget thresholds as versioned shadow defaults, not accuracy guarantees.

These are bounded contract decisions; they do not require a new experiment before coding.

### Before provider-backed coding/live shadow

- capability-qualified Gemini image + strict schema transport for the exact model/profile revision;
- secret-safe environment and approved controlled corpus access;
- lifecycle storage/cleanup support for private crop/raw response.

### Before production rollout

1. Actual human sign-off on current nine-table reference set.
2. Required gridless, continuation, merged-header, dense-small-font and unsupported cases.
3. Hard metrics and repeatability passed on the signed corpus.
4. Compact→v0→Gate 2 E2E proof with all existing validators unchanged.
5. Cleanup terminal-state proof and steady-state storage budget.
6. Provider/model capability qualification, drift/rollback test and explicit allowlists.
7. Human-review owner, queue/SLA/capacity and evidence-retention policy.
8. Repo/bundle/live parity and process=false/no-Knowledge proof.

## 19. Final recommendation

Implement the compact canonical document first, not the VLM call first. The contract/lifecycle boundary removes the active 22 MB permanent-artifact risk and gives both deterministic and hybrid results one accountable destination. Затем strengthen deterministic acceptance/classification, add hybrid as a candidate-bound shadow path, and only then connect accepted compact tables to the existing normalized-table boundary.

Exact target choices:

- permanent: original PDF, compact canonical document, table decisions/validation, compact selected source evidence, v0 projections, acceptance/lifecycle receipts and small provider attempt metadata;
- temporary/TTL: full geometry, full words/vectors, crops, raw provider payloads, rejected hypotheses;
- simple primary: deterministic accepted only under all hard gates;
- complex primary: candidate-bound hybrid;
- fallback: one same-evidence retry; 150→200 is explicit new evidence;
- review: missing candidates, structural disagreement, bounded failure or unsupported source;
- initial provider role: Gemini multimodal structural binding after exact capability qualification, not business fact extraction;
- DPI: policy B, 150 primary and typed 200 escalation;
- candidate control: table-local exact spans, shared headers, short ids, private reversible dictionary, 512 candidates/128 KiB/32k estimated tokens/64×24 grid, deterministic row-window split;
- Gate 1 change boundary: parser output lifecycle, compact builder/classifier/raster/evidence/provider/materializer/validator/adapter;
- Gate 2 change boundary: one feature-flagged input-readiness selection branch; package, segmentation, context v2, business candidate binding, source-fact validation and stitch unchanged;
- storage: expected ≤0.75 MB permanent per comparable successful PDF, ≤75 MB/100; debug/review storage TTL-controlled and capped;
- rollout: seven phases with dual-write and shadow comparison before any geometry deletion or hybrid authority.

## 20. Final statuses

Supported by this repository-grounded design:

- `BROKER_REPORTS_PDF_HYBRID_TARGET_ARCHITECTURE_READY`
- `BROKER_REPORTS_PDF_HYBRID_CONTRACT_SET_READY`
- `BROKER_REPORTS_PDF_COMPACT_CANONICAL_MIGRATION_READY`
- `BROKER_REPORTS_PDF_TABLE_CLASS_POLICY_READY`
- `BROKER_REPORTS_PDF_HYBRID_EVIDENCE_PACKAGE_READY`
- `BROKER_REPORTS_PDF_HYBRID_BINDING_AND_VALIDATION_READY`
- `BROKER_REPORTS_PDF_PROVIDER_ATTEMPT_CONTRACT_READY`
- `BROKER_REPORTS_PDF_ARTIFACT_LIFECYCLE_READY`
- `BROKER_REPORTS_PDF_GATE2_COMPATIBILITY_DESIGNED`
- `BROKER_REPORTS_PDF_STORAGE_PROJECTION_READY`
- `BROKER_REPORTS_PDF_HYBRID_MIGRATION_PLAN_READY`
- `BROKER_REPORTS_PDF_HYBRID_IMPLEMENTATION_BACKLOG_READY`

Not claimed:

- production implementation complete;
- human-signed reference accuracy;
- provider/model production qualification;
- compact/hybrid live Gate 2 parity;
- production rollout readiness;
- current full geometry cleanup complete.
