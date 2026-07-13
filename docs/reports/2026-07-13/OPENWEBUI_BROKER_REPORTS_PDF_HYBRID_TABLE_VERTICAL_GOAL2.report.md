# Broker Reports: candidate-bound hybrid PDF table vertical, Goal 2

Дата: 2026-07-13

Режим: Implementation Goal 2 of 4, private shadow
Итог: вертикаль работает, но остаётся `PARTIAL`; production Gate 2 не переключён

## Итог

Реализован полный shadow-контур:

```text
точные production PDF words + table bbox
-> deterministic classifier
-> private lossless crop
-> bounded candidate package
-> Gemini native image + structured output
-> candidate-id binding
-> deterministic full-grid materialization
-> fail-closed independent validation
-> private shadow decision
```

На том же six-page PDF классифицированы 14/14 таблиц: 9 остались `deterministic_simple` без VLM, пять текущих blocked tables направлены в hybrid. Primary conservative matrix дала 1 `accepted_shadow`, 2 `human_review_required`, 1 `blocked` из-за non-repeatability и 1 `blocked_context_budget`. Ошибка одной таблицы не удалила evidence соседних.

Контур остаётся неавторитетным: `authority_state=non_authoritative`, `production_ready=false`, `production_gate2_selection_changed=false`. Goal 1 compact не мутировался; создана только proposed revision. OCR, whole-PDF provider transport, Knowledge/RAG/vector writes, OpenWebUI core patch и cleanup не использовались.

## Реализованные модули и контракты

| Модуль | Назначение |
|---|---|
| `pdf_table_classification.py` | Deterministic policy, measured signals, immutable identity and typed routing. |
| `pdf_table_raster.py` | PyMuPDF 1.26.5, fixed bbox/padding/transform, lossless PNG, 150/typed 200 DPI and hard image budgets. |
| `pdf_hybrid_evidence.py` | Table-local production-word candidates, reversible private dictionary, component accounting and hard context guard. |
| `pdf_hybrid_provider.py` | Provider-neutral factory and Gemini native image/JSON-schema adapter through OpenWebUI Connection. |
| `pdf_hybrid_materialization.py` | Full rectangular grid, exact source resolution, stable refs, package and placement checksums. |
| `pdf_table_validation.py` | Contract, identity, provenance, grid, empty, duplicate, header, accounting, signal, placement and repeatability gates. |
| `pdf_hybrid_shadow.py` | Factory-only orchestration, ArtifactStore persistence, isolation by table and proposed compact revision. |
| `local_pdf_hybrid_goal2_proof.py` | Controlled qualification, live matrix, provisional scoring, DPI and repeatability evidence. |

Versioned contracts:

- `broker_reports_pdf_table_classification_v1`;
- `broker_reports_pdf_hybrid_evidence_package_v1`;
- `broker_reports_pdf_hybrid_binding_output_v1`;
- `broker_reports_pdf_provider_attempt_v1`;
- `broker_reports_pdf_table_materialization_result_v1`;
- `broker_reports_pdf_table_validation_v1`.

Canonical descriptions:

- `docs/stage2/contracts/BROKER_REPORTS_PDF_HYBRID_TABLE_VERTICAL.v1.md`;
- `docs/stage2/implementation/BROKER_REPORTS_PDF_HYBRID_SHADOW_MIGRATION.v1.md`.

## Classifier: все 14 таблиц

| Table key | Path | Причина |
|---|---|---|
| 1:1 | `deterministic_simple` | current deterministic projection validated |
| 1:2 | `deterministic_simple` | current deterministic projection validated |
| 1:3 | `hybrid_after_deterministic_block` | current column structure blocker |
| 2:1 | `deterministic_simple` | current deterministic projection validated |
| 2:2 | `deterministic_simple` | current deterministic projection validated |
| 3:1 | `deterministic_simple` | current deterministic projection validated |
| 3:2 | `hybrid_after_deterministic_block` | current column structure blocker |
| 4:1 | `hybrid_after_deterministic_block` | current column structure blocker |
| 4:2 | `hybrid_after_deterministic_block` | current column structure blocker |
| 4:3 | `deterministic_simple` | current deterministic projection validated |
| 5:1 | `deterministic_simple` | current deterministic projection validated |
| 5:2 | `deterministic_simple` | current deterministic projection validated |
| 5:3 | `hybrid_after_deterministic_block` | current column structure blocker |
| 5:4 | `deterministic_simple` | current deterministic projection validated |

`quality=high` сам по себе не даёт deterministic acceptance. Все решения содержат policy/config hash и measured signals.

## Controlled proof: пять blocked tables

| Table | Structural case | Terminal | Grid | Empty | Source/word refs | Strict provisional diagnostic |
|---|---|---|---:|---:|---:|---|
| 1:3 | wide, multi-row header | `human_review_required` | 20x18, 360 cells | 119 | 369/369 | cells 233/360; numeric 78/78; empty 119/246; headers exact; structure not exact; 127 extra non-empty |
| 3:2 | wide, multiline header | `blocked_context_budget` | 0 | 0 | 0/0 | no provider call; 708 candidates exceed hard limit 512 |
| 4:1 | cross-page continuation | `human_review_required` | 25x16, 400 cells | 57 | 401/401 | cells 207/400; numeric 70/70; empty 57/250; headers exact; structure not exact; 193 extra non-empty |
| 4:2 | grouped header, sparse totals | `blocked` | 7x11, 77 cells | 42 | 60/60 | strict score 75/77, но explicit same-evidence repeat дал другой placement/materialization checksum |
| 5:3 | tax/summary merged section | `accepted_shadow` | 5x8, 40 cells | 16 | 69/69 | cells 40/40; numeric 15/15; empty 16/16; headers/structure exact |

Для всех materialized tables `model_invented_values_total=0`; unknown candidate ids, duplicate use, payload-integrity mismatch и неполные grids отсутствуют. Четыре primary materializations разрешили 899 table-local source-value-ref bindings и 899 word-ref bindings через private candidate dictionaries. Единственный accepted result содержит 69/69 таких bindings.

Wide и continuation не приняты только на основании provenance и rectangularity. Их deterministic column geometry была заблокирована, поэтому independent-placement gate возвращает `human_review_required`. Это устраняет ложный вывод «источник настоящий, значит ячейка правильная».

Reference остаётся `agent_visual_reviewed_pending_human_signoff`; это diagnostic evidence, не production accuracy и не signed truth.

## Scoring

Primary all-scheduled score считает terminal non-accepted cases неуспешными:

| Metric | All 5 scheduled | 1 accepted only | All 4 materialized diagnostic |
|---|---:|---:|---:|
| Exact cells | 40/613 (6.5253%) | 40/40 (100%) | 555/877 (63.2839%) |
| Exact numeric-like | 15/259 (5.7915%) | 15/15 (100%) | 180/180 (100%) |
| Exact explicit empties | 16/122 (13.1148%) | 16/16 (100%) | 233/554 (42.0578%) |
| Exact structures | 1/5 | 1/1 | 2/4 |
| Exact headers | 1/5 | 1/1 | 4/4 |

Высокий numeric-like diagnostic у wide tables не компенсирует неправильное размещение и empty-cell ошибки.

## Context guard

Все component profiles рассчитаны до provider call. Table 3:2 была остановлена с `pdf_hybrid_candidate_count_budget_exceeded`:

- 708 candidates при hard limit 512;
- candidate JSON 77,869 B;
- image 330,456 B, 1627x1193;
- estimated input 20,169 tokens;
- grid 768 positions;
- model-facing text amplification 30.372246x;
- provider attempts: 0.

Largest permitted 150-DPI package — continuation 4:1:

- 343 candidates; candidate JSON 37,566 B; candidate text 2,303 characters;
- image 165,259 B, 1627x622;
- task/header/schema: 381/41/2,100 B;
- model-facing text 38,270 B versus 1,286 B unique visible text: 29.758942x;
- estimated input 10,093; actual provider input 23,544 tokens;
- output 4,219 tokens; requested hard cap 16,384;
- provider-token amplification 73.118012x.

Hard budgets удержаны, но estimator недооценил реальный image-inclusive input примерно в 2.33 раза, а фактический input оказался всего на 456 tokens ниже target 24,000. Это отдельный Goal 3 blocker: image token estimation и candidate/span compaction нужно улучшить до расширения классов.

## Provider qualification and attempts

Live qualification через существующую OpenWebUI Connection:

- profile `google_gemini`;
- requested/resolved exact model: `models/gemini-3.5-flash`;
- native `generateContent` image transport;
- image input, structured output and maximum output 65,536 подтверждены;
- credentials получены из OpenWebUI Connection; duplicate Function secret отсутствует;
- hidden retry и provider failover: false;
- `thinkingLevel=minimal`;
- canonical/adapted schema hashes и три provider schema transforms записаны; локальный canonical validator сохраняет отброшенные provider constraints.

Официальные capability references: [Gemini 3.5 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash), [structured output](https://ai.google.dev/gemini-api/docs/generate-content/structured-output), [GenerateContent response metadata](https://ai.google.dev/api/generate-content), [thinking levels](https://ai.google.dev/gemini-api/docs/generate-content/thinking).

Primary matrix persisted seven visible attempts: four primary 150-DPI calls, two explicit same-evidence repeats and one 200-DPI package revision. A subsequent full controlled run added the required accepted tax/summary repeat. Все получили `STOP`, parsed contract-valid output и observable usage. HTTP 2xx сам по себе нигде не считался table acceptance.

Исторические диагностические runs не удалены. Они выявили две адаптации: Gemini отклонил nested `maxItems` в response schema, а verbose per-cell output достигал `MAX_TOKENS`. Provider projection теперь явно записывает schema transforms, canonical validation остаётся локально строгой, а binding использует компактные arrays of candidate ids; скрытых retries или failover не добавлено.

## DPI evidence

Continuation 4:1 сначала прошла at 150 DPI. По typed reason `pdf_hybrid_continuation_structure_sensitivity_check` создана отдельная 200-DPI crop/package revision.

- crop identity changed: true;
- package identity changed: true;
- package-scoped materialization checksum equal: false, что ожидаемо для нового package;
- package-independent `placement_checksum` equal: true;
- обе revisions дали одинаковые strict placement metrics: 207/400 cells, 70/70 numeric, 57/250 empty;
- 150-DPI usage: 23,544 input / 4,219 output tokens;
- 200-DPI usage: 23,542 input / 4,217 output tokens.

200 DPI не улучшил placement и не стал новым default.

## Repeatability

| Case | Repeat | Result |
|---|---|---|
| simple deterministic control | повторная нормализация/projection | identical checksum |
| difficult continuation 4:1 | explicit same-evidence attempt 2 | identical materialization checksum; class still requires review |
| grouped hybrid 4:2 | explicit same-evidence attempt 2 | checksum mismatch in primary matrix; class/model blocked |
| accepted tax/summary hybrid 5:3 | explicit same-evidence attempt 2 in the supplemental controlled run | identical materialization checksum |

Repeat calls имеют тот же evidence task id, model/config и явную lineage. DPI revision в repeatability не смешивается. Позднейшее совпадение grouped 4:2 в другом run не отменяет уже наблюдавшийся same-evidence failure; этот класс не считается repeatable.

## Storage and compact comparison

| Component | JSON payload bytes | Role |
|---|---:|---|
| Full forensic source payload | 22,185,587 | current temporary/debug state |
| Current source units | 2,121,963 | current temporary/debug state |
| Current table projections | 1,771,037 | current authoritative migration state |
| Goal 1 compact | 538,882 | non-authoritative compact dual-write |
| Goal 2 shadow artifacts total | 2,801,156 | private research/shadow state in the primary matrix |

Primary Goal 2 total includes 14 classifications, 6 crops, 5 valid bounded packages, 7 raw responses/attempts/bindings/materializations, 5 validations, 14 decisions, one proposed revision and one safe summary. Crops and raw responses are private; safe report contains neither bytes nor customer values.

Current compact still has 14 decisions, 9 accepted, 5 blocked and 1,045/1,045 existing accepted source refs accounted, with no duplicates or unaccounted refs. Explicit fields are present:

```text
acceptance_mode = shadow_dual_write
authority_state = non_authoritative
production_ready = false
```

The proposed revision compares current and hybrid decisions but `base_artifact_mutated=false`. `gate2_handoff_v0` does not select compact or hybrid results.

## Goal 1 and repository regressions

- Goal 1 compact builder deterministic; 14 decisions and 1,045/1,045 refs preserved.
- Feature-off: `pdf_hybrid_shadow_enabled=false`, zero Goal 2 refs/artifacts/provider calls.
- Goal 1 compact dual-write default remains false.
- Gate 2 handoff and selection unchanged.
- Gate 2 bundle SHA-256 unchanged:
  - source-fact bundle: `9E7E3FA0BE71C912FC4DE2B69D1B3447E90012B9FB89894E143C8A5EB8300F81`;
  - domain bundle: `220BA58A59F33CA2F536D3A61B6959662A5F12E88640236438DEAC5A9523C454`.
- Gate 1 closed-world bundle rebuilt with all hybrid modules and PyMuPDF pin.
- Non-PDF formats and `process=false` behavior unchanged.
- No forensic deletion, Knowledge/RAG/vector writes or OCR.

Verification:

- focused compact + hybrid + closed-world bundle suite: 34 passed;
- full service suite: 300 passed, 5 external SWIG deprecation warnings;
- controlled live proof: exit 0;
- `py_compile`: passed;
- `git diff --check`: passed, only existing Windows line-ending warnings.

## Repository/live status

Source revision: `7f88c7f66e0914772988a6eb3db474e89bc65c0a`; `HEAD == origin/main`. Worktree remains dirty because Goal 1, Goal 2 and pre-existing direct-PDF research are uncommitted; unrelated research files were preserved and not imported into the hybrid runtime.

The provider qualification and controlled calls were live through approved OpenWebUI Connection configuration. The Gate 1 bundle was rebuilt locally. No OpenWebUI deployment, commit, push or production activation was requested or performed.

## Blockers for Goal 3

1. Table 3:2 has 708 candidates and needs deterministic row-windowing or stronger span compaction; column splitting remains forbidden.
2. Wide 1:3 and continuation 4:1 lack independent column-placement proof and remain human review.
3. Grouped 4:2 has one provisional placement disagreement and an observed same-evidence non-repeatability failure; the class/model is blocked.
4. Reference still needs human signoff.
5. Actual image-inclusive tokens exceed the estimator by about 2.33x; the 73.118012x provider-token amplification needs reduction/qualification.
6. Goal 3 must define arbitration and compact-revision acceptance without changing Gate 2 until separately approved.

## Final statuses

```text
BROKER_REPORTS_PDF_TABLE_CLASSIFIER_READY
BROKER_REPORTS_PDF_HYBRID_RASTER_READY
BROKER_REPORTS_PDF_HYBRID_EVIDENCE_PACKAGE_READY
BROKER_REPORTS_PDF_HYBRID_CONTEXT_BUDGET_GUARD_READY
BROKER_REPORTS_PDF_HYBRID_PROVIDER_ADAPTER_READY
BROKER_REPORTS_PDF_HYBRID_PROVIDER_QUALIFIED
BROKER_REPORTS_PDF_HYBRID_BINDING_OUTPUT_READY
BROKER_REPORTS_PDF_HYBRID_MATERIALIZATION_READY
BROKER_REPORTS_PDF_HYBRID_TABLE_VALIDATION_READY
BROKER_REPORTS_PDF_HYBRID_SHADOW_PERSISTENCE_READY
BROKER_REPORTS_PDF_HYBRID_GOAL1_REGRESSION_PASSED
BROKER_REPORTS_PDF_HYBRID_CONTROLLED_PROOF_COMPLETED
BROKER_REPORTS_PDF_HYBRID_VERTICAL_PARTIAL
WIDE_CONTINUATION_PLACEMENT_REQUIRES_INDEPENDENT_VALIDATION
CANDIDATE_COUNT_BUDGET_EXCEEDED_708_GT_512
GROUPED_HEADER_CLASS_NON_REPEATABLE
IMAGE_INCLUSIVE_TOKEN_AMPLIFICATION_REQUIRES_REDUCTION
```
