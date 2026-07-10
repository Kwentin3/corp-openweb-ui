# OpenWebUI Broker Reports Gate 1 full-source reslice coverage report

Дата: 2026-07-10
Repository: `corp-openweb ui`
Scope: Gate 1 / Gate 1.5 full-source artifacts and one limited Gate 2 typed proof

## Итог

Preview и extraction-grade source truth разделены. Gate 1 теперь создаёт
`private_normalized_source_payload_v0` и
`private_normalized_source_unit_v0`; Gate 2 предпочитает complete units через
resolver и использует legacy preview только как bounded fallback без expansion
readiness.

Synthetic proof прошёл. На `case_group_002` выбранный primary CSV был заново
принят через `process=false`, получил complete source unit, после чего одна
реальная `position_snapshot` vertical прошла validator и stitch без pending
parent remainder.

Whole 16-document reslice не объявляется готовым: 1 из 16 прежних parent
targets доказан complete в новых live artifacts; 15 ещё не доказаны в этом
срезе. В пакете есть 8 PDF с heuristic-only parser, а whole-package controlled
run не уложился в текущий operational budget. Поэтому full-case status остаётся
partial, но limited expansion для уже доказанного selected CSV безопасна.

## Почему старые slices были truncated

- CSV: `rows[:5]`;
- HTML tables: `table_rows[:10]`;
- TXT/HTML text: первые 20 lines и 2000 chars;
- XLSX: первые 5 rows × 5 columns;
- PDF: первые 2000 extracted chars;
- DOCX: первые 20 paragraphs / 2000 chars.

CSV/TXT/HTML preview bounds не были parser limits. PDF heuristic extraction и
неполная DOCX structure являются реальными completeness limits. XLSX complete
возможен только для resolved non-formula sheets в member/unit budgets.

## Что добавлено

### Code

- factory-first full-source payload/unit builder;
- parser completeness и explicit materialization budgets;
- stable payload/unit/checksum/provenance/value refs;
- ArtifactStore persistence для двух новых `private_case` types;
- Gate 2 full-unit preference и legacy fallback mode;
- full-parent segmentation semantics без `pending_gate1_reslice`;
- O(N) batch source-value validation вместо O(N²);
- narrow derived-copy вместо deepcopy полного parent package;
- compact report counts/status wording;
- local controlled private re-intake proof script;
- live selected-source and audit-only proof modes.

### Contracts

- `BROKER_REPORTS_GATE1_FULL_SOURCE_NORMALIZED_PAYLOAD.v0.md`;
- `BROKER_REPORTS_GATE1_EXTRACTION_SOURCE_UNITS.v0.md`;
- обновлены normalization, pipeline mapping, Gate 2 extraction/facts/domain
  extractors/routing и artifact lifecycle contracts.

## Preview vs extraction-grade unit

| Artifact | Purpose | Whole-source claim |
|---|---|---|
| legacy private table/text slice | profiling/preview/backward compatibility | запрещён при truncation |
| full-source normalized payload | private parser logical projection + completeness status | только `complete` |
| extraction source unit | resolver-gated refs/values/coverage for complete payload | да, для declared logical range |
| derived source unit | narrow deterministic segment | complete only inside selected parent partition |
| Gate 2 package | model input for selected refs | не содержит весь document |

## ArtifactStore safety

New payload/unit records:

- visibility: `private_case`;
- storage: `project_artifact_payload`;
- access: `requires_gate2_resolver=true` plus exact owner/run/case/workspace;
- retention: explicit `customer_approved_test` in live proof;
- purge/cascade: existing private lifecycle;
- Knowledge/RAG/vector: not used.

Safe chat/report exposes counts and status only. Raw rows/text, filenames, file
ids, private paths and personal/account values were not emitted.

## Format status

| Format | Current status | Reason |
|---|---|---|
| CSV | supported complete in row/cell budgets | real and synthetic proof passed |
| TXT | supported complete in char budget | full decode available |
| HTML | supported complete per outside-text/table logical unit in budgets | tables separated, no old 10-row bound |
| XLSX | conditional complete | formulas, unresolved/oversized members or unit budgets produce partial/blocked |
| PDF | partial | heuristic parser cannot prove full text coverage; no OCR/VLM |
| DOCX | partial | body projection does not prove tables/headers/auxiliary parts |
| ZIP/image/XLS | unsupported/blocked | no extraction-grade full-source parser in scope |

Configured logical-unit budgets: 10 000 rows, 100 000 cells, 200 000 text
characters, 5 000 000 bytes per XLSX member. Overflow is explicit partial;
there is no silent first-N truncation.

## Synthetic proof

Fixture: 13-row CSV, which exceeds the old 5-row preview bound.

Results:

- preview: 5 rows, `truncated=true`;
- full payload: 13 rows, `complete`;
- extraction unit: 13/13 refs accounted;
- stable row/source-value refs across repeated normalization;
- value beyond preview reproduced from ref/checksum;
- ArtifactStore payload/unit persisted private and resolver-gated;
- Gate 2 selected `full_source_unit`;
- segmentation parent remainder: `not_applicable_parent_complete`;
- PDF heuristic control remained partial and minted no complete unit.

Tests: `122 passed`.

## case_group_002 selected reslice proof

Live case:
`customer_case_group_002_process_false_gate1_20260710174758`

Selected scope: one hash-verified primary CSV, safe registry ordinal 1.

Gate 1 / ArtifactStore:

- source payloads: 1;
- complete source units: 1;
- legacy preview slices: 1, truncated;
- previous parent targets proven complete in this slice: 1/16;
- source-ready documents: 1;
- primary refs: 1;
- dropped source-ready refs: 0;
- ArtifactStore records: 16;
- private records: 3 (preview + payload + unit);
- Knowledge backend records: 0;
- upload cleanup: 1/1;
- uploads left by timed-out whole-package diagnostics: 16/16 deleted, 0 remain;
- document/Knowledge/vector delta after cleanup: 0/0/0.

Readiness/segmentation:

- source input mode: `full_source_unit`;
- parent selected/accounted refs: 1342/1342;
- derived source units: 344;
- duplicate/unaccounted refs: 0/0;
- parent truncation: false;
- parent remainder: `not_applicable_parent_complete`;
- complete high-confidence `position_snapshot` targets: 14.

## Real typed vertical from complete source unit

Model: `gpt-5.4-mini-2026-03-17`
Run: `sfdrun_37373e72cbadbb31c889a87c`

Results:

- selected primary documents/parent units/segments: 1/1/1;
- selected refs: 1;
- accepted domain packages: 1/1;
- validator-passed facts: 1 `position_snapshot`;
- stitch: 1 complete;
- uncovered/conflict/unknown refs: 0/0/0;
- provenance/completeness/coverage/issue errors: 0;
- raw output: strict JSON schema, private, no fallback;
- parent truncation: 0;
- parent remainder: `not_applicable_parent_complete`;
- Knowledge/vector/document/file deltas: 0/0/0/0;
- primary expansion batch executed: false.

The selected source had zero unresolved issue refs, so issue reconciliation is
complete by empty set; nothing was silently dropped.

## Whole-package blocker

The registry package contains 2 CSV, 4 HTML, 2 XLSX and 8 PDF. Two early live
whole-package attempts hit the 300-second client timeout. During refinement,
two O(N²)/deep-copy performance defects were found and fixed. The selected CSV
then normalized in 5.671 seconds, but a controlled whole-package audit still
remained CPU/memory heavy and was stopped after five minutes without an
aggregate result. In addition, all 8 PDF remain parser-partial by contract.

Specific blocker:

`whole_case_package_not_within_current_runtime_budget_and_pdf_parser_completeness_partial`

Next code slice: streaming/chunked logical units with exact sibling/range
accounting, plus a bounded whole-package performance proof. It must not turn PDF
heuristic output into complete coverage and does not require OCR in this scope.

## Expansion decision

`READY_FOR_CASE_GROUP_002_GATE2_LIMITED_PRIMARY_EXPANSION`

This applies only to the selected complete CSV document and similarly proven
complete units. Criteria are met: complete parent, no pending remainder, typed
fact passed, source-ready refs reconciled, issue set reconciled, strict private
outputs and no-RAG guards passed.

Full primary expansion across all 16 documents is not ready and was not run.

## Final statuses

```text
GATE1_FULL_SOURCE_RESLICE_RESEARCH_READY
GATE1_FULL_SOURCE_PAYLOAD_CONTRACT_READY
GATE1_EXTRACTION_SOURCE_UNITS_CONTRACT_READY
GATE1_FULL_SOURCE_PROVENANCE_READY
GATE1_FULL_SOURCE_SYNTHETIC_PASSED
CASE_GROUP_002_TYPED_VERTICAL_FROM_COMPLETE_SOURCE_UNIT_PASSED
CASE_GROUP_002_VECTOR_GUARD_PASSED
CASE_GROUP_002_KNOWLEDGE_GUARD_PASSED
READY_FOR_CASE_GROUP_002_GATE2_LIMITED_PRIMARY_EXPANSION
GATE1_FULL_SOURCE_RESLICE_PARTIAL
whole_case_package_not_within_current_runtime_budget_and_pdf_parser_completeness_partial
```

Not claimed: `CASE_GROUP_002_FULL_SOURCE_RESLICE_READY`.
